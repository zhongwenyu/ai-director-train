#!/usr/bin/env python3
"""Cross-family Judge & Blind Pairwise Arena powered by codex (gpt-6.1-sol, effort=medium).

Evaluates:
1. Full-drama Outline (from 200-500 char creative brief -> 40-120 ep blueprint & beat chain)
2. Episode Scripts (Audience retention simulation, drop-off point detection, anti-AI-stiffness)
3. Blind Pairwise Arena (Randomized A/B comparison to prevent score inflation & reward hacking)
"""
from __future__ import annotations

import concurrent.futures as cf
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

TRAIN_ROOT = Path("/home/zhongwenyu/project/ai-director-train")
sys.path.insert(0, str(TRAIN_ROOT / "trainer"))
import llm_clients as L  # noqa: E402

EPISODE_SCORE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "viewer_gut_reaction": {
            "type": "string",
            "description": "模拟真实红果短剧观众刷到这几集的第一直觉（100字内，直白犀利，不讲客套话）",
        },
        "dropoff_points": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "episode": {"type": "integer"},
                    "quote_or_moment": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["episode", "quote_or_moment", "reason"],
                "additionalProperties": False,
            },
        },
        "ai_smell_flags": {
            "type": "array",
            "description": "检出的AI味/机械感病灶（如独处自言自语报数字、路人甲广播解说人设、强行凑肢体冲突、书面套话、车轱辘话重复）",
            "items": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": [
                            "self_talk_exposition",
                            "npc_mouthpiece",
                            "forced_fake_conflict",
                            "greasy_webnovel_cliche",
                            "ai_cliche_prose",
                            "repetitive_dialogue",
                            "flat_hook",
                            "logic_break",
                        ],
                    },
                    "quote": {"type": "string"},
                    "fix_direction": {"type": "string"},
                },
                "required": ["category", "quote", "fix_direction"],
                "additionalProperties": False,
            },
        },
        "dimensions": {
            "type": "object",
            "properties": {
                "opening_grip": {
                    "type": "object",
                    "properties": {
                        "score": {"type": "number", "minimum": 0, "maximum": 20},
                        "critique": {"type": "string"},
                    },
                    "required": ["score", "critique"],
                    "additionalProperties": False,
                },
                "tension_and_payoff": {
                    "type": "object",
                    "properties": {
                        "score": {"type": "number", "minimum": 0, "maximum": 25},
                        "critique": {"type": "string"},
                    },
                    "required": ["score", "critique"],
                    "additionalProperties": False,
                },
                "human_dialogue_and_persona": {
                    "type": "object",
                    "properties": {
                        "score": {"type": "number", "minimum": 0, "maximum": 25},
                        "critique": {"type": "string"},
                    },
                    "required": ["score", "critique"],
                    "additionalProperties": False,
                },
                "cliffhanger_addiction": {
                    "type": "object",
                    "properties": {
                        "score": {"type": "number", "minimum": 0, "maximum": 20},
                        "critique": {"type": "string"},
                    },
                    "required": ["score", "critique"],
                    "additionalProperties": False,
                },
                "visual_pacing_and_craft": {
                    "type": "object",
                    "properties": {
                        "score": {"type": "number", "minimum": 0, "maximum": 10},
                        "critique": {"type": "string"},
                    },
                    "required": ["score", "critique"],
                    "additionalProperties": False,
                },
            },
            "required": [
                "opening_grip",
                "tension_and_payoff",
                "human_dialogue_and_persona",
                "cliffhanger_addiction",
                "visual_pacing_and_craft",
            ],
            "additionalProperties": False,
        },
        "top_strengths": {"type": "array", "items": {"type": "string"}},
        "actionable_skill_fixes": {
            "type": "array",
            "description": "针对编剧方法论层面的通用改进建议（不要针对单部剧具体人名，要能沉淀进编剧Skill规则）",
            "items": {"type": "string"},
        },
    },
    "required": [
        "viewer_gut_reaction",
        "dropoff_points",
        "ai_smell_flags",
        "dimensions",
        "top_strengths",
        "actionable_skill_fixes",
    ],
    "additionalProperties": False,
}

OUTLINE_SCORE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "planned_total_episodes": {"type": "integer"},
        "engine_verdict": {"type": "string"},
        "dimensions": {
            "type": "object",
            "properties": {
                "info_gap_and_premise_hook": {"type": "number", "minimum": 0, "maximum": 25},
                "character_contrast_and_agency": {"type": "number", "minimum": 0, "maximum": 20},
                "long_arc_escalation_40_120": {"type": "number", "minimum": 0, "maximum": 25},
                "episode_hook_chain_density": {"type": "number", "minimum": 0, "maximum": 30},
            },
            "required": [
                "info_gap_and_premise_hook",
                "character_contrast_and_agency",
                "long_arc_escalation_40_120",
                "episode_hook_chain_density",
            ],
            "additionalProperties": False,
        },
        "weaknesses": {"type": "array", "items": {"type": "string"}},
        "skill_level_suggestions": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "planned_total_episodes",
        "engine_verdict",
        "dimensions",
        "weaknesses",
        "skill_level_suggestions",
    ],
    "additionalProperties": False,
}

PAIRWISE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "winner": {"type": "string", "enum": ["A", "B", "TIE"]},
        "margin": {"type": "string", "enum": ["decisive", "clear", "narrow"]},
        "dimension_winners": {
            "type": "object",
            "properties": {
                "opening_attraction": {"type": "string", "enum": ["A", "B", "TIE"]},
                "dialogue_humanity": {"type": "string", "enum": ["A", "B", "TIE"]},
                "tension_and_payoff": {"type": "string", "enum": ["A", "B", "TIE"]},
                "ending_cliffhanger": {"type": "string", "enum": ["A", "B", "TIE"]},
            },
            "required": [
                "opening_attraction",
                "dialogue_humanity",
                "tension_and_payoff",
                "ending_cliffhanger",
            ],
            "additionalProperties": False,
        },
        "why_winner_wins": {"type": "string"},
        "why_loser_loses": {"type": "string"},
    },
    "required": [
        "winner",
        "margin",
        "dimension_winners",
        "why_winner_wins",
        "why_loser_loses",
    ],
    "additionalProperties": False,
}

EPISODE_JUDGE_PROMPT = """你是红果短剧平台总编审兼资深爆款制片人，审过上千部日消耗破千万的竖屏/横屏短剧。
你的唯一评判标准是：**真实观众刷到这部剧时，会不会前5秒停住手指、全程憋着一口气或嘴角上扬看完、并在集尾最后一秒迫不及待点下一集！**

### 严厉甄别“2026真爆款质感” vs “两类劣质AI伪爆款”
打分时必须擦亮眼睛！观众刷走AI剧本，往往是因为以下两类致命臭毛病（一旦出现必须在对应维度重扣！）：

1. **古早油腻网文套路与脸谱化泼妇风（`greasy_webnovel_cliche`，头号劝退毒药！）**：
   - **浮夸符号堆砌**：村口必停“劳斯莱斯幻影”、男主必“剑眉星目气质矜贵、嘴角勾起玩味冷笑”、受气女主必“端盘子脚下一滑把菜汤溅到两千块裙子上”、围观群众必“全场哗然！炸开了锅！全场死寂！”
   - **反派低幼脸谱化自爆**：反派毫无生活逻辑地把恶毒心思挂嘴边喊（如“等你在城里钓上富二代咱家就飞黄腾达了”“你个丧门星死鬼亲妈”“也不撒泡尿照照自己”）。
   - **对照真爆款质感**：真爆款的偏心与羞辱是**刺痛人心的真实生活细节**（比如亲手擀的荷包蛋寿面被父亲不耐烦挥手赶回厨房；瘫痪婆婆隔间里藏着32双磨平鞋底的40码鞋；女儿心爱的小夜灯被抢走还挨一巴掌），底牌靠**视觉实物静默展示**（拉开破双肩包露出整排金条），绝不靠特助扯嗓子喊“顾总您可是百亿集团董事长”！
2. **独处自言自语报设定/报数字（`self_talk_exposition`）**：角色一个人在屋里把内心算计或账户金额大声念成台词（如“转卖名表一次到账八十万元！”）。真短剧只用精炼 `[VO]` 或实物画面展示，绝不对着空气播报！
3. **路人甲/特助充当百度百科广播员（`npc_mouthpiece`）**：配角说出不像熟人说的话硬塞设定（如“顾总，您可是百亿盛世集团董事长！”“女大学生林皎月，直接占了初弦的位置？”）。
4. **无脑硬凑假肢体冲突（`forced_fake_conflict`）**：不顾题材基调，开场第1秒生硬抓手腕推人、喊空洞死线。
5. **车轱辘话凑时长与提前泄底（`repetitive_dialogue` / `flat_hook`）**：同一层意思换词吵三轮无筹码变化；或者在50-100集长剧的第1集结尾把本该留作第2集揭晓的核心悬念直接用大白话喊破（真断章应当卡在“等一下！”或门推开看见真相但尚未说破的那一秒，留足好奇心缺口！）。

### 五维严苛打分标尺（总分100分，拒绝水分！平庸AI稿应给50-65分，机械八股稿给55-68分，真正抓人好剧才给80+分）
1. **`opening_grip`（0-20分）开局抓力与好奇心缺口**：
   - 17-20：前5-10秒瞬间立住强信息差、高概念悬念、鲜活反差人设或切肤冲突，让人立刻想知道“接下来怎么收场”；续集前5秒丝滑接住上集悬念并翻出新变数。
   - 11-16：能看懂冲突但切入套路化，或为了冲突而硬演假冲突。
   - 0-10：铺垫拖沓、人物自报家门，或开场莫名其妙不知所云。
2. **`tension_and_payoff`（0-25分）戏剧张力、信息差与爽点含金量**：
   - 21-25：观众与角色之间有极佳的信息差或情绪蓄压（委屈戳心、扮猪吃虎暗爽、智商碾压利落），筹码每30-45秒发生实质位移，爽点/反转既出人意料又合情合理。
   - 14-20：有基本冲突与反击，但压迫流于表面口水仗，或爽点来得太轻易、缺少围观反应与实质收获。
   - 0-13：干瘪流水账，或光吵架不推进实质事件。
3. **`human_dialogue_and_persona`（0-25分）活人感台词、潜台词与人设魅力**：
   - 21-25：台词短促地道、句句带钩子或潜台词，遮住名字也能听出身份脾气；动作反应克制精准；无任何自言自语报设定或广播腔。
   - 14-20：大体顺畅，但偶有1-2处工具人解说台词、直白喊口号或书面AI腔。
   - 0-13：充斥独白报菜名、路人播报身份、全员说话一个味或生硬八股感。
4. **`cliffhanger_addiction`（0-20分）集尾断章成瘾度**：
   - 17-20：每集都精准卡在“靴子落地前一秒 / 底牌刚掀开一角 / 更大危机或反转突然降临”的最高张力点，让人抓心挠肝必须点下一集。
   - 11-16：有钩子但切点偏晚（已经演完结果才断）或只靠一句空泛狠话“你等着”收尾。
   - 0-10：平淡收尾，看完毫无点下一集的冲动。
5. **`visual_pacing_and_craft`（0-10分）视听可拍性与1-3分钟节奏呼吸**：
   - 8-10：单集戏量饱满且节奏张弛有度（1-3分钟自然浮动），`△` 动作具体可演、道具细节亮眼，格式干净。
   - 5-7：偶有抽象心理词、动作堆砌或单集过短/过水。
   - 0-4：不可拍、严重注水或格式混乱。

---
### 待评审材料
{context_header}

#### 待评审分集剧本正文
{script_text}
"""

OUTLINE_JUDGE_PROMPT = """你是红果短剧总编审。请评审以下由「200-500字简单创意」生成的《全剧故事引擎与分集大纲》。

### 评审核心标准（满分100分，严苛打分）
1. **`info_gap_and_premise_hook`（0-25分）**：是否把简单创意升级成了极具吸引力的**核心信息差矩阵**（观众知道什么底牌、反派误判什么、核心情绪钩子是什么）？
2. **`character_contrast_and_agency`（0-20分）**：主角是否有极强的主动性与独特魅力（而非纯挨打木偶）？反派是否有具体利益动机与阶段层次（而非纯降智复读机）？人物说话底色是否鲜明？
3. **`long_arc_escalation_40_120`（0-25分）**：总集数是否合理落在 **40～120集** 区间？是否规划了清晰的**阶段换挡升级阶梯**（小闭环打脸 -> 第10-15集大卡点翻盘 -> 中段换地图/更高维对手 -> 终局高潮），避免写到20集后原地踏步水剧情？
4. **`episode_hook_chain_density`（0-30分）**：已展开的分集细纲表是否做到了**集集有实质筹码/关系变化、单集时长按戏量在1-3分钟合理浮动、集尾钩子环环相扣不重样**？

---
### 原始简单创意
{idea_text}

### 待评审全剧大纲
{outline_text}
"""

PAIRWISE_ARENA_PROMPT = """你是红果短剧平台总编审。现在对同一题材/赛道的**两份分集剧本（版本 A 与版本 B）**进行双盲对比评审。
请你完全从**“哪一版更像真正能跑出高留存、高完播的优秀短剧，更让你想追看下一集”**出发做出裁决！

### 重点对比维度
1. **真实生活痛感 vs 古早网文油腻套路**：谁用的是扎心的生活细节与实物信息差（如一碗被嫌弃的亲手寿面、拉开旧包见金条、磨平的鞋底）？谁在堆砌“劳斯莱斯幻影、百亿董事长特助广播、端菜脚滑洒裙子、钓富二代、撒泡尿照照、嘴角玩味冷笑、全场哗然/全场死寂”等让人脚趾抠地的廉价网文套路？（凡堆砌廉价网文套路者必须重判负！）
2. **活人感台词 vs AI广播/八股味**：谁的人物说话像真实活人、克制带刺有潜台词？谁犯了“独处自言自语报数字 / 特助路人广播头衔 / 全员排队复读羞辱”的AI毛病？
3. **戏剧张力与信息差铺垫**：谁的筹码变化与情绪递进更扎实可信，而非靠反派无脑降智自爆？
4. **长剧集尾断章留白（Curiosity Gap）**：作为一部40-120集短剧，谁停在“悬念刚拉满、真相呼之欲出却未说破”的最佳钩子位，而非把下集底牌提前直白喊完或平淡收束？

---
{topic_context}

### 【版本 A】
{script_a}

---
### 【版本 B】
{script_b}
"""


def strip_author_notes(script_md: str) -> str:
    """Strip trailing author/compiler notes (`## 编剧附注`, etc.) so blind evaluation has zero leakage."""
    text = re.split(r"\n#{1,3}\s*编剧附注", script_md, maxsplit=1)[0]
    return text.strip()


def score_episodes(
    script_text: str,
    *,
    idea_text: str = "",
    outline_excerpt: str = "",
    stats_summary: str = "",
    out_path: Path | None = None,
) -> dict[str, Any]:
    clean_script = strip_author_notes(script_text)
    ctx_parts = []
    if idea_text:
        ctx_parts.append(f"**原始简单创意**：\n{idea_text.strip()}")
    if outline_excerpt:
        ctx_parts.append(f"**对应分集大纲摘录**：\n{outline_excerpt.strip()[:4000]}")
    if stats_summary:
        ctx_parts.append(f"**客观物理体检摘要**：\n{stats_summary.strip()}")
    context_header = "\n\n".join(ctx_parts) if ctx_parts else "（盲测模式：仅根据剧本正文评判观众留存吸引力）"

    prompt = EPISODE_JUDGE_PROMPT.format(
        context_header=context_header,
        script_text=clean_script,
    )
    res = L.call_codex_json(prompt, EPISODE_SCORE_SCHEMA, timeout=600)
    dims = res["dimensions"]
    total = round(
        sum(
            float(dims[k]["score"])
            for k in (
                "opening_grip",
                "tension_and_payoff",
                "human_dialogue_and_persona",
                "cliffhanger_addiction",
                "visual_pacing_and_craft",
            )
        ),
        2,
    )
    res["total_score"] = total
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return res


def score_outline(
    idea_text: str,
    outline_text: str,
    *,
    out_path: Path | None = None,
) -> dict[str, Any]:
    prompt = OUTLINE_JUDGE_PROMPT.format(
        idea_text=idea_text.strip(),
        outline_text=outline_text.strip()[:24000],
    )
    res = L.call_codex_json(prompt, OUTLINE_SCORE_SCHEMA, timeout=600)
    dims = res["dimensions"]
    res["total_score"] = round(sum(float(v) for v in dims.values()), 2)
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return res


def pairwise_compare(
    label_left: str,
    script_left: str,
    label_right: str,
    script_right: str,
    *,
    topic_context: str = "",
    swap_debias: bool = False,
    out_path: Path | None = None,
) -> dict[str, Any]:
    """Run blind A/B comparison. Deterministic hash randomizes slot A/B to prevent position bias."""
    s_left = strip_author_notes(script_left)
    s_right = strip_author_notes(script_right)

    h = int(hashlib.md5((label_left + "::" + label_right).encode("utf-8")).hexdigest()[:8], 16)
    flipped = (h % 2 == 1) if not swap_debias else False

    if not flipped:
        map_ab = {"A": label_left, "B": label_right, "TIE": "TIE"}
        prompt = PAIRWISE_ARENA_PROMPT.format(
            topic_context=topic_context, script_a=s_left, script_b=s_right
        )
    else:
        map_ab = {"A": label_right, "B": label_left, "TIE": "TIE"}
        prompt = PAIRWISE_ARENA_PROMPT.format(
            topic_context=topic_context, script_a=s_right, script_b=s_left
        )

    if swap_debias:
        prompt_fwd = PAIRWISE_ARENA_PROMPT.format(
            topic_context=topic_context, script_a=s_left, script_b=s_right
        )
        prompt_rev = PAIRWISE_ARENA_PROMPT.format(
            topic_context=topic_context, script_a=s_right, script_b=s_left
        )
        with cf.ThreadPoolExecutor(max_workers=2) as pool:
            f_fwd = pool.submit(L.call_codex_json, prompt_fwd, PAIRWISE_SCHEMA, timeout=600)
            f_rev = pool.submit(L.call_codex_json, prompt_rev, PAIRWISE_SCHEMA, timeout=600)
            raw = f_fwd.result()
            raw_rev = f_rev.result()

        map_ab = {"A": label_left, "B": label_right, "TIE": "TIE"}
        map_rev = {"A": label_right, "B": label_left, "TIE": "TIE"}
        w1 = map_ab[raw["winner"]]
        w2 = map_rev[raw_rev["winner"]]
        result = {
            "left": label_left,
            "right": label_right,
            "slot_A": map_ab["A"],
            "slot_B": map_ab["B"],
            "winner_label": w1 if w1 == w2 else "TIE",
            "margin": raw["margin"] if w1 == w2 else "narrow",
            "dimension_winners": {k: map_ab[v] for k, v in raw["dimension_winners"].items()},
            "why_winner_wins": raw["why_winner_wins"],
            "why_loser_loses": raw["why_loser_loses"],
            "swap_check": {
                "pass1_winner": w1,
                "pass2_winner": w2,
                "consistent": w1 == w2,
            },
        }
    else:
        raw = L.call_codex_json(prompt, PAIRWISE_SCHEMA, timeout=600)
        result = {
            "left": label_left,
            "right": label_right,
            "slot_A": map_ab["A"],
            "slot_B": map_ab["B"],
            "winner_label": map_ab[raw["winner"]],
            "margin": raw["margin"],
            "dimension_winners": {k: map_ab[v] for k, v in raw["dimension_winners"].items()},
            "why_winner_wins": raw["why_winner_wins"],
            "why_loser_loses": raw["why_loser_loses"],
        }

    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result
