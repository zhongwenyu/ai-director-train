#!/usr/bin/env python3
"""
Self-contained Multi-Episode Pacing, Clarity & Causal Logic Judge (`pacing_arena_judge.py`).

100% powered by isolated `agy` sub-agents (`--model gemini-4-carbon-medium --sandbox --disable-slash-commands`)
running in an empty temporary directory (`num_turns == 1`, ZERO workspace/file/history leakage).
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import strip_to_screen as STS  # noqa: E402

AGY_BIN = (
    os.environ.get("TRAIN_AGY_BIN")
    or ("/home/zhongwenyu/.config/paseo/antigravity-bin/agy"
        if Path("/home/zhongwenyu/.config/paseo/antigravity-bin/agy").is_file()
        else None)
    or shutil.which("agy")
    or "agy"
)
JUDGE_MODEL = os.environ.get("PACING_JUDGE_MODEL", "gemini-4-carbon-medium")
JUDGE_EFFORT = os.environ.get("PACING_JUDGE_EFFORT", "medium")


def _extract_first_json(text: str) -> Any:
    s = text.strip()
    m = re.match(r"^```[a-zA-Z0-9_-]*\s*\n(.*)\n```\s*$", s, re.S)
    if m:
        s = m.group(1).strip()
    dec = json.JSONDecoder()
    for idx, ch in enumerate(s):
        if ch in "{[":
            try:
                obj, _ = dec.raw_decode(s[idx:])
                return obj
            except json.JSONDecodeError:
                continue
    raise ValueError(f"No valid JSON object found: {text[:300]!r}")


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
        "script_a_event_count_and_clarity": {"type": "string"},
        "script_b_event_count_and_clarity": {"type": "string"},
        "script_a_flaws": {"type": "array", "items": {"type": "string"}},
        "script_b_flaws": {"type": "array", "items": {"type": "string"}},
        "preferred": {"type": "string", "enum": ["A", "B"]},
        "decisive_reason": {"type": "string"},
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
红果真实爆款大数据证明：**1 集（2分钟）根本承载不了 1 个完整戏剧事件！真实爆款是用 3～6 集连载共同承载 1 个完整戏剧事件**。
正因为 **3 集只深挖 1～2 个紧咬相连的场面**，每集 20～30 句活人对话，才能把「每个人是谁、过去发生了什么、反派怎么虚伪得寸进尺、主角为什么寒心反击」交代得明明白白、丝丝入扣！

请重点审查以下 **七大必打回病灶**：
1. **快进赶进度、多事件塞成提纲（`rushed_unexplained_jump`）**：
   - 3 集之内硬塞 5～10 个跨阶段大转折，或同一场十几分钟内连塞七八个制裁打脸动作，导致每件事只有两三句话、缺乏情绪递进与谈判过程，观众看得莫名其妙！
2. **前情与人物关系没说清（`unintroduced_relationship_or_context`）**：
   - 注意：角色通过“嫂子/哥/爸/妈/叔/师兄/厂长/林叔”等亲属或职务称呼明确建立关系的，属于完全清晰！只有当关键角色直到整集结束既无姓名也无任何关系称谓、导致观众完全猜不出他是谁时，才判此项。
3. **前世今生/隐忍多年时间线悖论（`timeline_branch_paradox`）**：
   - 若主角前世替反派卖命十年（如2005干到2015），结果重回2005年开场主角还没反抗，反派就已经嫌弃赶他走、主动退婚——那前世怎么可能留下来干十年？！（合法逻辑必须是：当年反派表面在温情画饼稳住主角骗底牌，前世主角信了才被吸血，今生主角主动识破掀桌才翻脸）。
4. **读心术跨空知情 & 哑巴工具人主角（`telepathy_or_mute_protagonist`）**：
   - 把旁人听不见的 `[内心独白VO]` 当成对方已听见的信息来回应；或主角走进陌生/合作店铺全程 0 句有声台词，对方却自动替他写好五五分账合同摁手印。
5. **无条件送股份慈善 / 围裙百宝箱 / 几十秒瞬移公章（`irrational_charity_or_magic_prop`）**：
   - 不谈任何条件风险就白送外人 50% 店铺股份；端火锅的油围裙里凭空掏出一铁盒 48 张汇款单；几十秒内拿着客户刚重签盖章的大单瞬移堵门；街边小店口嗨“封杀全城原料”。
6. **身份违和或路人支线注水（`identity_dissonance_or_npc_detour`）**：
   - 985名校在读大学生毫无理由去街边当底层厨工；或第2集丢开核心仇人去跟一次性路人临时工扯皮一整集、救场后盟友冷脸审讯内耗。
7. **书面汇报/口号式假台词（`stiff_corporate_or_slogan_dialogue`）**：
   - 满嘴法务财务报表术语、连报四五个零碎金额数字，或每句话都是喊大纲口号。

### 裁决标准（四项子分均为 0～10 分制）
- **严禁没病硬挑**：如果前 3 集只围绕 1～2 个紧咬相连的核心事件层层剥笋、人物关系通过称呼自然清晰、因果与人性逻辑完全自洽，则 `flaws` **必须填空数组 `[]`**，`verdict` 判 `PASS_IMMERSIVE`！
- 只有当确凿存在上述致命硬伤时，才列入 `flaws` 并判 `REJECT_REWRITE`！
"""

PAIRWISE_PACING_PROMPT = """你是一位阅片无数的**红果爆款短剧主编兼普通观众代表**。
下面给你盲测对比两部短剧的 **前 3 集《屏幕裸看实况版》**（**剧本 A** vs **剧本 B**，均已剥离作者偷写的 `**人物**` 名单）。
请严格按以下优先级选出真正从容清晰、让人信服上头的 `A` 或 `B`：
1. **多集连载讲透一事的真实戏剧沉浸感 > 快进塞满多件事的提纲速通感**（严惩假连载真快进、同一场塞七八个制裁动作、跨空间瞬移）。
2. **真生活家常痛点 > AI塑料定制巧合与商务法务掉书袋**。
3. **时间线因果与人性自利 100% 自洽**（禁前世今生时间线悖论、禁未交代称谓、禁哑巴签约白送股份、禁围裙掏铁盒、禁985学生当厨工与路人支线内耗）。
4. **活人大白话短句质感**。
"""


def call_isolated_agy_subagent(prompt: str, schema: Dict[str, Any], timeout: int = 420) -> Dict[str, Any]:
    sfx = "\n\n【系统执行约束：严禁调用任何文件读写或终端工具！请直接按 JSON Schema 一次性返回结构化结果。】"
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
                    cmd, cwd=empty_dir, input=prompt + sfx, capture_output=True, text=True, timeout=timeout
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
                return raw if isinstance(raw, dict) else _extract_first_json(str(raw))
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
