#!/usr/bin/env python3
"""
Multi-Episode Pacing, Clarity & Causal Logic Judge (`judge/pacing_arena_judge.py`).

100% powered by isolated `agy` sub-agents (`--model gemini-4-carbon-medium --sandbox --disable-slash-commands`)
running in an empty temporary directory (`num_turns == 1`, ZERO workspace/file/history leakage).

Grounded in the empirical findings from 105 Hongguo hit dramas (`corpus/pacing_event_span_report.md`):
  - A single complete dramatic event spans a median of **5.56 episodes** (NOT 0.3 or 1 episode!).
  - Episode 1 is `setup` in **90.1%** of hits; `Ep1->Ep2` continues the exact same scene/event in **62.2%**.
  - Evaluates ONLY `strip_to_screen.py` de-authored transcripts so authorial `**人物**` crutches cannot hide
    unexplained relationships, mute protagonists, or rushed plot leaps!
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

TRAIN_ROOT = Path("/home/zhongwenyu/project/ai-director-train")
SKILL_SCRIPTS = TRAIN_ROOT / ".agents" / "skills" / "hit-short-drama" / "scripts"
for p in (str(TRAIN_ROOT / "trainer"), str(SKILL_SCRIPTS)):
    if p not in sys.path:
        sys.path.insert(0, p)

import strip_to_screen as STS  # noqa: E402
import llm_clients as L  # noqa: E402

AGY_BIN = L.AGY_BIN
JUDGE_MODEL = os.environ.get("PACING_JUDGE_MODEL", "gemini-4-carbon-medium")
JUDGE_EFFORT = os.environ.get("PACING_JUDGE_EFFORT", "medium")

SINGLE_ARC_AUDIT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "viewer_comprehension_summary": {
            "type": "string",
            "description": "仅凭裸看屏幕实况：观众能否完全看懂每个人的关系、前情起因和当前争点？哪里清楚、哪里莫名其妙？（100字内）",
        },
        "distinct_major_events_counted": {
            "type": "integer",
            "description": "这3集里一共硬塞了多少个跨场景/跨阶段的大事件？（真实爆款前3集通常只围绕1~2个核心事件层层推进；快进烂剧会塞5~10个大事件）",
        },
        "pacing_diagnosis": {
            "type": "string",
            "enum": [
                "UNHURRIED_IMMERSIVE_SERIAL",
                "RUSHED_FAST_FORWARD_OUTLINE",
                "DRAGGING_NPC_DETOUR",
            ],
        },
        "flaws": {
            "type": "array",
            "description": "检出的剧情过快跳跃、前情关系没说清、前世今生时间线悖论、读心术、无条件送股份慈善或物理常识硬伤；若完全从容清晰自洽则填空数组 []",
            "items": {
                "type": "object",
                "properties": {
                    "episode": {"type": "integer"},
                    "flaw_type": {
                        "type": "string",
                        "enum": [
                            "rushed_unexplained_jump",
                            "unintroduced_relationship_or_context",
                            "timeline_branch_paradox",
                            "telepathy_or_mute_protagonist",
                            "irrational_charity_or_magic_prop",
                            "identity_dissonance_or_npc_detour",
                            "stiff_corporate_or_slogan_dialogue",
                        ],
                    },
                    "quote": {"type": "string"},
                    "why_baffling_to_viewer": {"type": "string"},
                    "slow_down_or_logic_fix": {"type": "string"},
                },
                "required": [
                    "episode",
                    "flaw_type",
                    "quote",
                    "why_baffling_to_viewer",
                    "slow_down_or_logic_fix",
                ],
                "additionalProperties": False,
            },
        },
        "scores": {
            "type": "object",
            "properties": {
                "unhurried_event_depth": {"type": "number", "minimum": 0, "maximum": 10},
                "context_and_relation_clarity": {"type": "number", "minimum": 0, "maximum": 10},
                "causal_and_human_logic": {"type": "number", "minimum": 0, "maximum": 10},
                "natural_dialogue_and_hooks": {"type": "number", "minimum": 0, "maximum": 10},
            },
            "required": [
                "unhurried_event_depth",
                "context_and_relation_clarity",
                "causal_and_human_logic",
                "natural_dialogue_and_hooks",
            ],
            "additionalProperties": False,
        },
        "verdict": {"type": "string", "enum": ["PASS_IMMERSIVE", "REJECT_REWRITE"]},
    },
    "required": [
        "viewer_comprehension_summary",
        "distinct_major_events_counted",
        "pacing_diagnosis",
        "flaws",
        "scores",
        "verdict",
    ],
    "additionalProperties": False,
}

PAIRWISE_PACING_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "script_a_event_count_and_clarity": {
            "type": "string",
            "description": "剧本A前3集承载了几个事件？人物关系、前因后果和情绪拉扯是否铺垫得从容清晰，还是像快进提纲一样莫名其妙？（110字内）",
        },
        "script_b_event_count_and_clarity": {
            "type": "string",
            "description": "剧本B前3集承载了几个事件？人物关系、前因后果和情绪拉扯是否铺垫得从容清晰，还是像快进提纲一样莫名其妙？（110字内）",
        },
        "script_a_flaws": {"type": "array", "items": {"type": "string"}},
        "script_b_flaws": {"type": "array", "items": {"type": "string"}},
        "preferred": {"type": "string", "enum": ["A", "B"]},
        "decisive_reason": {
            "type": "string",
            "description": "决定A与B高下的最核心原因（聚焦：多集连载讲透同一事件 vs 快进塞剧情没说清、时间线与人性逻辑自洽度、活人对话质感，90字内）",
        },
    },
    "required": [
        "script_a_event_count_and_clarity",
        "script_b_event_count_and_clarity",
        "script_a_flaws",
        "script_b_flaws",
        "preferred",
        "decisive_reason",
    ],
    "additionalProperties": False,
}

SINGLE_ARC_PROMPT = """你是一位零背景信息、只看屏幕实况的**资深短剧观众兼叙事节奏总审**。
以下是一部短剧 **前 3 集** 的《屏幕裸看实况版》（已剥离作者偷写的 `**人物**` 设定行，并标注了旁人听不见的 `[内心独白VO/OS]`）。

### 核心铁律：短剧「快节奏」≠「快进塞事件」！
红果真实爆款大数据证明：**1 集（2分钟）根本承载不了 1 个完整戏剧事件！真实爆款是用 3～6 集连载共同承载 1 个完整戏剧事件**（例如：连续 3 集都在同一顿年夜饭桌上从敬酒、漏发女儿红包、退掉36万养老金演到掀翻桌子；或连续 3 集围绕被锁在门外的同一套借住房层层撕开换锁、撕协议、逼签赠与书）。
正因为 **3 集只深挖 1～2 个紧咬相连的场面**，每集 25～35 句活人对话，才能把「每个人是谁、过去发生了什么、反派怎么虚伪得寸进尺、主角为什么寒心反击」交代得明明白白、丝丝入扣！

请重点审查以下 **七大必打回病灶**：
1. **快进赶进度、多事件塞成提纲（`rushed_unexplained_jump`）**：
   - 3 集之内硬塞 5～10 个跨阶段大转折（例如第 1 集刚重生就一口气演完退婚、撕方、晒单、辞工、过街结盟、签五五分账、断油、抢单、骑车进货；第 2～3 集直接演完宴席、举报快检、当街盲测把对手招牌都摘了）！导致每件事只有两三句话，毫无铺垫和谈判过程，观众看得莫名其妙！
2. **前情与人物关系没说清（`unintroduced_relationship_or_context`）**：
   - 注意：角色通过“嫂子/哥/爸/妈/叔/许董”等亲属或职务称呼明确建立关系的，属于完全清晰！只有当关键角色直到整集结束既无姓名也无任何关系称谓、导致观众完全猜不出他是谁时，才判此项。
3. **前世今生/隐忍多年时间线悖论（`timeline_branch_paradox`）**：
   - 若主角前世替反派卖命十年（如2005干到2015），结果重回2005年开场主角还没反抗，反派就已经嫌弃赶他走、主动退婚——那前世怎么可能留下来干十年？！（合法逻辑必须是：当年反派表面在温情画饼稳住主角骗底牌，前世主角信了才被吸血，今生主角主动识破掀桌才翻脸；或者当天本就是前世屈服让出通知书的转折日）。
4. **读心术跨空知情 & 哑巴工具人主角（`telepathy_or_mute_protagonist`）**：
   - 仅抓确凿硬伤：把旁人听不见的 `[内心独白VO]` 当成对方已听见的信息来回应；或主角走进陌生/合作店铺全程 0 句有声台词，对方却自动替他写好五五分账合同摁手印！（正常隐忍沉默几秒后开口反击、或提前拍照留存自家合同证据属于合理行为，严禁误判！）。
5. **无条件送股份慈善 / 围裙百宝箱 / 几十秒瞬移公章（`irrational_charity_or_magic_prop`）**：
   - 仅抓确凿荒唐硬伤：不谈任何条件风险就白送外人 50% 店铺股份；端火锅的油围裙里凭空掏出一铁盒 48 张汇款单；同一场戏几十秒内拿着客户刚重签盖章的大单瞬移堵门；街边小店口嗨“封杀全城原料”。（自己在手机里提前拍下自家协议照片、或打电话退回自己昨天刚代缴的款项属于正常生活逻辑，严禁误判！）。
6. **身份违和或路人支线注水（`identity_dissonance_or_npc_detour`）**：
   - 985名校在读大学生毫无理由去街边当底层厨工；或第2集丢开核心仇人去跟一次性路人临时工扯皮一整集、救场后盟友冷脸审讯内耗。
7. **书面汇报/口号式假台词（`stiff_corporate_or_slogan_dialogue`）**：
   - 满嘴法务财务报表术语、连报四五个零碎金额数字，或每句话都是喊大纲口号。

### 裁决标准（四项子分均为 0～10 分制，满分 40 分）
- **严禁没病硬挑**：如果前 3 集像真实爆款那样只围绕 1～2 个紧咬相连的核心事件层层剥笋、人物关系通过称呼自然清晰、逻辑基本自洽，则 `flaws` **必须填空数组 `[]`**，总分给 32～39 分，`verdict` 判 `PASS_IMMERSIVE`！
- 只有当确凿存在「快进塞入 5 个以上大事件像提纲」「时间线自相矛盾」「哑巴签约白送股份」「985学生当厨工/路人支线注水」等致命硬伤时，才列入 `flaws` 并判 `REJECT_REWRITE`！
"""

PAIRWISE_PACING_PROMPT = """你是一位阅片无数的**红果爆款短剧主编兼普通观众代表**。
下面给你盲测对比两部短剧的 **前 3 集《屏幕裸看实况版》**（**剧本 A** vs **剧本 B**，均已剥离作者偷写的 `**人物**` 名单，还原真实观众裸看屏幕的信息量）。

请只回答一个核心问题：**哪一部的叙事节奏从容扎实、前因后果与人物关系交代得一清二楚、情绪层层递进让人欲罢不能；哪一部犯了“快进赶进度塞事件、前情没说清莫名其妙、逻辑悖论或AI假爽八股”的毛病？**

### 铁律判准（按优先级排序！）
1. **【头号准则】多集连载讲透一事的真实戏剧沉浸感 > 快进塞满十件事的提纲速通感！**
   - **千万不要被“前3集打脸次数多、开店摘牌进度快”骗了！** 真实爆款短剧 **1 集根本装不下 1 个完整事件**，往往用 **3～5 集** 把同一个核心场面（如年夜饭偏心→退养老金→掀桌、上门收房被换锁→发现丈夫撕协议→长辈逼签赠与书、婚车被抢座→逼骑单车→寒心决裂）演得入木三分！每一句来龙去脉、每一个亲属称呼、每一次虚伪拉扯都清清楚楚，集尾停在同一现场最抓人的悬念点，下一集无缝接上一秒！
   - 相反，如果一部剧为了“快爽”，在 3 集里像放八倍速预告片一样硬塞进“决裂+晒单+跨街合伙签五五分账+断油+抢大席+快检举报+盲测摘牌”七八件大事，或者满嘴“法务核档、监管户、净落几百差几千”说明书台词——观众连人物关系和前因后果都没看明白就跳到下一关了，只会觉得莫名其妙、一眼假！
2. **【AI塑料定制巧合与掉书袋一票否决】**：
   - 真实高留存短剧用的全是**老百姓一秒听懂的家常物件与普世痛点**（如漏发两千红包、换门锁撕借住条、电机掉颗螺丝卡住齿轮、熬汤火候焦苦 vs 清亮醇香）！
   - 凡是出现**“刚从A废品里精准拆出某冷门进口型号配件（如德国依维柯高压喷油泵），一出门恰好撞见同型号外贸车坏在仇人门口急求该配件”这种AI定制巧合爽文套路**，或满嘴“法务核档、公证锁死、银行监管户、精密工业参数”掉书袋台词的，一律重扣判负！
3. **【逻辑与常识硬伤排查】**：
   - 检查是否存在：前世今生时间线自相矛盾（当年就已经嫌弃赶人，前世怎么干十年？）、关键角色整集没人叫出身份关系、主角当哑巴配角读心术白送一半股份、围裙里掏铁盒存根、985在校生无故当厨工、第2集打无关路人支线、救场后盟友冷脸审讯内耗。
4. **【活人对话质感】**：
   - 真爆款说大白话短句（句均10~18字），句句带人情世故与潜台词；烂剧念口号、报账本、总结陈词。

严格按 JSON Schema 输出盲测判决，在 `preferred` 中选出真正从容清晰、让人信服上头的 `A` 或 `B`！
"""


def call_isolated_agy_subagent(prompt: str, schema: Dict[str, Any], timeout: int = 480) -> Dict[str, Any]:
    """Spawn a fresh, zero-history, sandboxed agy sub-agent (`gemini-4-carbon-medium`) in an empty `/tmp` dir."""
    last_err = ""
    for attempt in range(1, 4):
        with tempfile.TemporaryDirectory(prefix="iso-judge-agy-") as empty_dir:
            schema_path = Path(empty_dir) / "schema.json"
            schema_path.write_text(json.dumps(schema, ensure_ascii=False), encoding="utf-8")
            cmd = [
                AGY_BIN,
                "--model", JUDGE_MODEL,
                "--effort", JUDGE_EFFORT,
                "--sandbox",
                "--disable-slash-commands",
                "--output-format", "json",
                "--input-format", "text",
                "--json-schema", str(schema_path),
            ]
            try:
                proc = subprocess.run(
                    cmd, cwd=empty_dir, input=prompt, capture_output=True, text=True, timeout=timeout
                )
            except subprocess.TimeoutExpired:
                last_err = f"timeout {timeout}s (attempt {attempt})"
                time.sleep(2 * attempt)
                continue
            if proc.returncode != 0:
                last_err = f"exit {proc.returncode}: {(proc.stderr or proc.stdout)[-500:]}"
                time.sleep(2 * attempt)
                continue
            try:
                env = json.loads(proc.stdout)
                raw = env.get("response", proc.stdout) if isinstance(env, dict) else proc.stdout
                obj = raw if isinstance(raw, dict) else L.extract_first_json(str(raw))
                return obj
            except Exception as exc:
                last_err = str(exc)
                time.sleep(2 * attempt)
                continue
    raise RuntimeError(f"Isolated agy sub-agent ({JUDGE_MODEL}) failed: {last_err}")


def audit_three_episode_arc(script_md: str) -> Dict[str, Any]:
    stripped = STS.strip_script_to_screen(script_md)
    prompt = SINGLE_ARC_PROMPT + "\n\n# 待审前 3 集《屏幕裸看实况版》\n\n" + stripped["screen_markdown"]
    rep = call_isolated_agy_subagent(prompt, SINGLE_ARC_AUDIT_SCHEMA)
    sc = rep["scores"]
    total = round(
        (
            sc["unhurried_event_depth"]
            + sc["context_and_relation_clarity"]
            + sc["causal_and_human_logic"]
            + sc["natural_dialogue_and_hooks"]
        )
        * 2.5,
        2,
    )
    rep["total_score"] = total
    rep["screen_diagnostics"] = stripped["episodes"]
    if (
        rep["flaws"]
        or rep["pacing_diagnosis"] != "UNHURRIED_IMMERSIVE_SERIAL"
        or total < 78.0
    ):
        rep["verdict"] = "REJECT_REWRITE"
    else:
        rep["verdict"] = "PASS_IMMERSIVE"
    return rep


def compare_swap_debiased_arcs(
    label_1: str,
    script_1_md: str,
    label_2: str,
    script_2_md: str,
    *,
    parallel_swaps: bool = True,
) -> Dict[str, Any]:
    s1_screen = STS.strip_script_to_screen(script_1_md)["screen_markdown"]
    s2_screen = STS.strip_script_to_screen(script_2_md)["screen_markdown"]

    p_fwd = (
        PAIRWISE_PACING_PROMPT
        + "\n\n==================== 剧本 A（屏幕裸看实况版） ====================\n\n"
        + s1_screen
        + "\n\n==================== 剧本 B（屏幕裸看实况版） ====================\n\n"
        + s2_screen
    )
    p_rev = (
        PAIRWISE_PACING_PROMPT
        + "\n\n==================== 剧本 A（屏幕裸看实况版） ====================\n\n"
        + s2_screen
        + "\n\n==================== 剧本 B（屏幕裸看实况版） ====================\n\n"
        + s1_screen
    )

    if parallel_swaps:
        with cf.ThreadPoolExecutor(max_workers=2) as pool:
            f_fwd = pool.submit(call_isolated_agy_subagent, p_fwd, PAIRWISE_PACING_SCHEMA, 420)
            f_rev = pool.submit(call_isolated_agy_subagent, p_rev, PAIRWISE_PACING_SCHEMA, 420)
            r_fwd = f_fwd.result()
            r_rev = f_rev.result()
    else:
        r_fwd = call_isolated_agy_subagent(p_fwd, PAIRWISE_PACING_SCHEMA, 420)
        r_rev = call_isolated_agy_subagent(p_rev, PAIRWISE_PACING_SCHEMA, 420)

    pick_fwd = label_1 if r_fwd["preferred"] == "A" else label_2
    pick_rev = label_2 if r_rev["preferred"] == "A" else label_1
    consistent = pick_fwd == pick_rev
    return {
        "winner": pick_fwd if consistent else "TIE",
        "swap_consistent": consistent,
        "forward_pick": pick_fwd,
        "reverse_pick": pick_rev,
        "forward_detail": r_fwd,
        "reverse_detail": r_rev,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("script_md", type=Path)
    ap.add_argument("--compare-to", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    s1 = args.script_md.read_text(encoding="utf-8")
    if args.compare_to:
        s2 = args.compare_to.read_text(encoding="utf-8")
        rep = compare_swap_debiased_arcs(args.script_md.stem, s1, args.compare_to.stem, s2)
    else:
        rep = audit_three_episode_arc(s1)

    txt = json.dumps(rep, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
