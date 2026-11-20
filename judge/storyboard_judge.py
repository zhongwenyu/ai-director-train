#!/usr/bin/env python3
"""Cross-Family Storyboard & Camera Movement Judge powered by codex (gpt-6.1-sol, effort=medium).

Evaluates:
1. Single-Episode / Multi-Episode Storyboard Quality against Source Screenplay (100-pt strict directorial rubric)
2. Swapped Double-Blind Pairwise Arena (`(A,B)` & `(B,A)` run concurrently via ThreadPoolExecutor!)
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import re
import sys
from pathlib import Path
from typing import Any

TRAIN_ROOT = Path("/home/zhongwenyu/project/ai-director-train")
sys.path.insert(0, str(TRAIN_ROOT / "trainer"))
import llm_clients as L  # noqa: E402

STORYBOARD_SCORE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "director_gut_verdict": {
            "type": "string",
            "description": "总导演一针见血的审片直觉（100字内，直指镜头张力、运镜呼吸感与AI视频可拍性，不讲客套话）",
        },
        "camera_and_staging_flaws": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": [
                            "unmotivated_or_spam_camera_move",
                            "compound_camera_chaos",
                            "dead_cctv_static_dialogue",
                            "missing_move_trigger_or_landing",
                            "axis_or_eyeline_jump",
                            "seam_same_angle_hard_cut",
                            "speech_duration_mismatch",
                            "ai_unrenderable_complex_action",
                            "plot_or_line_omission",
                            "flat_opening_or_cliffhanger_shot",
                        ],
                    },
                    "shot_id_or_quote": {"type": "string"},
                    "fix_direction": {"type": "string"},
                },
                "required": ["category", "shot_id_or_quote", "fix_direction"],
                "additionalProperties": False,
            },
        },
        "dimensions": {
            "type": "object",
            "properties": {
                "camera_movement_choreography": {
                    "type": "object",
                    "properties": {
                        "score": {"type": "number", "minimum": 0, "maximum": 25},
                        "critique": {"type": "string"},
                    },
                    "required": ["score", "critique"],
                    "additionalProperties": False,
                },
                "narrative_hook_and_payoff_staging": {
                    "type": "object",
                    "properties": {
                        "score": {"type": "number", "minimum": 0, "maximum": 20},
                        "critique": {"type": "string"},
                    },
                    "required": ["score", "critique"],
                    "additionalProperties": False,
                },
                "shot_scale_axis_and_editing_rhythm": {
                    "type": "object",
                    "properties": {
                        "score": {"type": "number", "minimum": 0, "maximum": 20},
                        "critique": {"type": "string"},
                    },
                    "required": ["score", "critique"],
                    "additionalProperties": False,
                },
                "ai_video_executability_and_seam_lock": {
                    "type": "object",
                    "properties": {
                        "score": {"type": "number", "minimum": 0, "maximum": 20},
                        "critique": {"type": "string"},
                    },
                    "required": ["score", "critique"],
                    "additionalProperties": False,
                },
                "micro_acting_sound_and_fidelity": {
                    "type": "object",
                    "properties": {
                        "score": {"type": "number", "minimum": 0, "maximum": 15},
                        "critique": {"type": "string"},
                    },
                    "required": ["score", "critique"],
                    "additionalProperties": False,
                },
            },
            "required": [
                "camera_movement_choreography",
                "narrative_hook_and_payoff_staging",
                "shot_scale_axis_and_editing_rhythm",
                "ai_video_executability_and_seam_lock",
                "micro_acting_sound_and_fidelity",
            ],
            "additionalProperties": False,
        },
        "top_strengths": {"type": "array", "items": {"type": "string"}},
        "actionable_skill_fixes": {
            "type": "array",
            "description": "可沉淀进分镜与运镜Skill的通用方法论改进建议（不带具体剧目人名）",
            "items": {"type": "string"},
        },
    },
    "required": [
        "director_gut_verdict",
        "camera_and_staging_flaws",
        "dimensions",
        "top_strengths",
        "actionable_skill_fixes",
    ],
    "additionalProperties": False,
}

PAIRWISE_SB_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "winner": {"type": "string", "enum": ["A", "B", "TIE"]},
        "margin": {"type": "string", "enum": ["decisive", "clear", "narrow"]},
        "dimension_winners": {
            "type": "object",
            "properties": {
                "camera_movement_mastery": {"type": "string", "enum": ["A", "B", "TIE"]},
                "visual_tension_and_hooks": {"type": "string", "enum": ["A", "B", "TIE"]},
                "editing_flow_and_axis": {"type": "string", "enum": ["A", "B", "TIE"]},
                "ai_video_renderability": {"type": "string", "enum": ["A", "B", "TIE"]},
            },
            "required": [
                "camera_movement_mastery",
                "visual_tension_and_hooks",
                "editing_flow_and_axis",
                "ai_video_renderability",
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

STORYBOARD_JUDGE_PROMPT = """你是红果爆款 AI 短剧总导演兼摄影指导（DP），精通竖屏/横屏短剧视听叙事、摄影机运动调度与 AI 视频模型（H3 / Seedance / Kling）生成边界。
请对照【输入定稿剧本】，严苛评审下方【待评审分镜表】。

### 核心审片法则（基于 166 部、7,670 集红果真实爆款实证规律）
1. **运镜必须“动静相生、师出有名”（`camera_movement_choreography`，0-25分，头号核心！）**：
   - 真爆款绝不是监控摄像头死拍（0%运镜），也绝不是每镜乱推乱晃的炫技垃圾（>40%滥用运镜）！实证真爆款约 **75%～88% 镜头以精准固定机位配剪辑切镜推进**，将 **12%～25% 的主动运镜** 精准压在**叙事承重拍**（权力翻转、底牌揭露、情绪决断、决绝离场背影跟拍、画外变数入场、集尾钩子）！
   - **主动运镜四要素缺一不可**：必须写清 **①触发动作/节点**（什么动作触发移动，而非空喊“气氛紧张”）→ **②路径与幅度**（如从中近景前推至面部特写 / 侧面并行跟拍）→ **③速度**（缓/中/快，只取一档）→ **④落点新信息**（停在哪、观众多看清了什么证据或微反应）。
   - **严禁复合运镜灾难**：单镜内同时叠加“推近+环绕”“横移+变焦”“边推边摇”会导致 AI 视频空间彻底扭曲，发现必重扣！固定镜在关键对峙处也应体现为何固定（如压迫凝视、留白呼吸）。
2. **开局抓力、信息差物证与集尾定格（`narrative_hook_and_payoff_staging`，0-20分）**：
   - 前 5 秒首镜是否直接用视觉异常/反差动作抓人（而非无聊空镜开场）？
   - 核心底牌与反转是否拆出了“施压物证特写 → 对手微反应 → 旁观错愕 → 主角冷定”的细腻视听层次？
   - 集尾最后一镜是否精准停在悬念未破、动势将落未落的定格画面？
3. **景别呼吸、180°轴线与切镜衔接（`shot_scale_axis_and_editing_rhythm`，0-20分）**：
   - 是否符合短剧紧致景别规律（近景/中近景/特写/过肩占主导 ~70%+，全景严格克制在场首空间建立或孤立收尾）？
   - 场景是否明确锁死 **180°主轴线（左A右B）** 且正反打视线方向一致？
   - 段内与跨组接缝是否遵循换机位/跳景别法则（严禁跨组同景别同角度硬接导致画面跳帧）？
4. **5-15秒生成组与 AI 视频可拍性（`ai_video_executability_and_seam_lock`，0-20分）**：
   - 同场连续镜头合成 **5～15 整数秒生成组**，组内子镜之和精确等于组时长，台词字数与单镜时长匹配（约 4.5～5 字/秒 + 气口，不吞字不跨组腰斩）。
   - 单镜单动量、动作三态（起始→执行→落定）清晰、有背景刚体锚点；组末是否有具体可画面的 **末态与首帧静态锚点**（杜绝“严格继承上镜”空话）？
5. **微表情外化、声画分离与剧本忠实度（`micro_acting_sound_and_fidelity`，0-15分）**：
   - 100% 忠实覆盖原剧本台词与关键 `△` 动作（不擅改台词或漏场）；
   - 说话人正常露脸且有明确视线落点；`[画外VO]` 时明确标注画内人物闭口；善用 J-cut/L-cut 声音先入与实物音效增强临场感。

### 严苛打分标尺（拒绝水分！平庸AI分镜给 50-62 分，机械套模板给 58-68 分，真正兼具导演运镜美感与AI可拍性的精品才给 75-88+ 分）

---
### 【输入定稿剧本】
{screenplay_text}

### 【客观物理体检摘要】
{stats_summary}

### 【待评审分镜表】
{storyboard_text}
"""

PAIRWISE_SB_PROMPT = """你是红果爆款 AI 短剧总导演兼摄影指导。现在对同一集定稿剧本拆出的**两份分镜方案（版本 A 与版本 B）**进行正反双盲对比裁决！
请完全从**“哪一份分镜拍出来更具爆款短剧的镜头抓力、运镜呼吸感、人物情绪穿透力，且喂给 AI 视频模型（H3/Seedance）最稳、最不崩画面”**出发做出裁决！

### 四大核心对决判据
1. **运镜含金量 vs 滥动/死板**：谁的运镜真正做到了“平时稳得住、承重拍动得准（有明确动作触发、单一清晰路径速度、落点揭示新信息）”？谁犯了“全片死机位监控拍对话”或“不分轻重每镜乱推乱摇/叠复合运镜炫技”的毛病？
2. **视觉讲故事与钩子分拍**：谁把剧本里的信息差、关键物证、人物潜台词外化成了抓人的特写切入、过肩压迫与反应切镜？谁只是把剧本文字机械抄进表格单元格？
3. **180°轴线、景别跳跃与段缝丝滑度**：谁的场景空间坐标、左右视线轴线、跨组换机位接缝与末态静态锚点写得让 AI 零记忆也能无缝拍出成片？
4. **时长节奏与声画真实感**：谁的单镜时长与台词字数呼吸自然匹配、画内口型与画外VO边界清晰？谁把30字长句硬塞进2秒镜头或靠无意义空镜凑整数秒？

---
### 【对照原剧本】
{screenplay_text}

---
### 【版本 A】
{sb_a}

---
### 【版本 B】
{sb_b}
"""


def strip_notes(md: str) -> str:
    return re.split(r"\n##\s*返修记录", md, maxsplit=1)[0].strip()


def score_storyboard(
    storyboard_text: str,
    screenplay_text: str,
    *,
    stats_summary: str = "",
    out_path: Path | None = None,
) -> dict[str, Any]:
    prompt = STORYBOARD_JUDGE_PROMPT.format(
        screenplay_text=screenplay_text.strip()[:12000],
        stats_summary=stats_summary.strip() or "（无附加体检表）",
        storyboard_text=strip_notes(storyboard_text)[:28000],
    )
    res = L.call_codex_json(prompt, STORYBOARD_SCORE_SCHEMA, timeout=600)
    dims = res["dimensions"]
    res["total_score"] = round(
        sum(
            float(dims[k]["score"])
            for k in (
                "camera_movement_choreography",
                "narrative_hook_and_payoff_staging",
                "shot_scale_axis_and_editing_rhythm",
                "ai_video_executability_and_seam_lock",
                "micro_acting_sound_and_fidelity",
            )
        ),
        2,
    )
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return res


def pairwise_compare_storyboards(
    label_left: str,
    sb_left: str,
    label_right: str,
    sb_right: str,
    screenplay_text: str,
    *,
    swap_debias: bool = True,
    out_path: Path | None = None,
) -> dict[str, Any]:
    s_left = strip_notes(sb_left)[:24000]
    s_right = strip_notes(sb_right)[:24000]
    sp_clean = screenplay_text.strip()[:9000]

    prompt_fwd = PAIRWISE_SB_PROMPT.format(screenplay_text=sp_clean, sb_a=s_left, sb_b=s_right)
    if swap_debias:
        prompt_rev = PAIRWISE_SB_PROMPT.format(screenplay_text=sp_clean, sb_a=s_right, sb_b=s_left)
        with cf.ThreadPoolExecutor(max_workers=2) as pool:
            f1 = pool.submit(L.call_codex_json, prompt_fwd, PAIRWISE_SB_SCHEMA, timeout=600)
            f2 = pool.submit(L.call_codex_json, prompt_rev, PAIRWISE_SB_SCHEMA, timeout=600)
            raw1 = f1.result()
            raw2 = f2.result()

        map1 = {"A": label_left, "B": label_right, "TIE": "TIE"}
        map2 = {"A": label_right, "B": label_left, "TIE": "TIE"}
        w1 = map1[raw1["winner"]]
        w2 = map2[raw2["winner"]]
        res: dict[str, Any] = {
            "left": label_left,
            "right": label_right,
            "winner_label": w1 if w1 == w2 else "TIE",
            "margin": raw1["margin"] if w1 == w2 else "narrow",
            "dimension_winners": {k: map1[v] for k, v in raw1["dimension_winners"].items()},
            "why_winner_wins": raw1["why_winner_wins"],
            "why_loser_loses": raw1["why_loser_loses"],
            "swap_check": {
                "pass1_winner": w1,
                "pass2_winner": w2,
                "consistent": w1 == w2,
            },
        }
    else:
        raw1 = L.call_codex_json(prompt_fwd, PAIRWISE_SB_SCHEMA, timeout=600)
        map1 = {"A": label_left, "B": label_right, "TIE": "TIE"}
        res = {
            "left": label_left,
            "right": label_right,
            "winner_label": map1[raw1["winner"]],
            "margin": raw1["margin"],
            "dimension_winners": {k: map1[v] for k, v in raw1["dimension_winners"].items()},
            "why_winner_wins": raw1["why_winner_wins"],
            "why_loser_loses": raw1["why_loser_loses"],
        }

    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return res
