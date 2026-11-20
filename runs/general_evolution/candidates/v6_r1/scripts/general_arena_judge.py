#!/usr/bin/env python3
"""
Generalized Multi-Genre Story-Tension, Seed-Fidelity, Motivation & Pacing Judge (`general_arena_judge.py`).

100% powered by context-isolated `agy` sub-agents (`--model gemini-4-carbon-medium --sandbox --disable-slash-commands`)
running in an empty `/tmp` directory (`num_turns == 1`, ZERO workspace/file/history leakage, ZERO `codex`).

Evaluates across ANY short-drama genre (urban, era/rural, ancient, fantasy/sci-fi, suspense, etc.) and ANY seed
granularity (1-sentence seed or multi-paragraph creative brief) on 4 universal orthogonal pillars:
  1. `seed_fidelity_and_hook` (0-10): Preserves explicit seed identities/relations/threads without template hijacking; amplifies native hook.
  2. `motivation_and_logic` (0-10): Every character's action at each timepoint is grounded in believable human psychology & info boundaries.
  3. `dramatic_tension_and_emotion` (0-10): High interpersonal pull-and-push, emotional expectation & payoff curves; zero dry accounting/audit filler.
  4. `serial_pacing_and_clarity` (0-10): ~4-6 eps per complete event stage, 1-2 turns/ep, clear screen relationships, crisp mid-tension hooks.
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
from typing import Any, Dict, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import strip_to_screen as STS  # noqa: E402

AGY_BIN = (
    os.environ.get("TRAIN_AGY_BIN")
    or (
        "/home/zhongwenyu/.config/paseo/antigravity-bin/agy"
        if Path("/home/zhongwenyu/.config/paseo/antigravity-bin/agy").is_file()
        else None
    )
    or shutil.which("agy")
    or "agy"
)
JUDGE_MODEL = os.environ.get("GENERAL_JUDGE_MODEL", "gemini-4-carbon-medium")
JUDGE_EFFORT = os.environ.get("GENERAL_JUDGE_EFFORT", "medium")


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


GENERAL_AUDIT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "native_engine_and_comprehension": {
            "type": "string",
            "description": "概括本剧的原生戏剧冲突与情绪爽点引擎，以及裸看屏幕实况时人物关系、前因后果与张力是否清晰抓人（120字内）",
        },
        "distinct_major_events_in_3eps": {
            "type": "integer",
            "description": "前3集一共塞入了多少个跨阶段大事件？（真实红果爆款前3集通常只围绕1～2个紧密咬合的核心事件层层递进；快进烂剧会塞4～10个大事件）",
        },
        "flaws": {
            "type": "array",
            "description": "检出的真实致命病灶；若原味保真、动机自洽、情绪张力饱满且节奏从容清晰，必须填空数组 []！",
            "items": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "如 大纲 / 第1集 / 第2集 / 第3集"},
                    "flaw_type": {
                        "type": "string",
                        "enum": [
                            "seed_distortion_or_dropped_core_hook",
                            "timeline_or_motivation_paradox",
                            "flat_emotion_or_dry_audit_filler",
                            "rushed_fast_forward_cramming",
                            "unintroduced_relation_or_telepathy",
                            "contrived_prop_or_irrational_charity",
                        ],
                    },
                    "evidence": {"type": "string"},
                    "fix_direction": {"type": "string"},
                },
                "required": ["location", "flaw_type", "evidence", "fix_direction"],
                "additionalProperties": False,
            },
        },
        "scores": {
            "type": "object",
            "properties": {
                "seed_fidelity_and_hook": {"type": "number", "minimum": 0, "maximum": 10},
                "motivation_and_logic": {"type": "number", "minimum": 0, "maximum": 10},
                "dramatic_tension_and_emotion": {"type": "number", "minimum": 0, "maximum": 10},
                "serial_pacing_and_clarity": {"type": "number", "minimum": 0, "maximum": 10},
            },
            "required": [
                "seed_fidelity_and_hook",
                "motivation_and_logic",
                "dramatic_tension_and_emotion",
                "serial_pacing_and_clarity",
            ],
            "additionalProperties": False,
        },
        "verdict": {"type": "string", "enum": ["PASS_HIT_READY", "REJECT_REWRITE"]},
    },
    "required": [
        "native_engine_and_comprehension",
        "distinct_major_events_in_3eps",
        "flaws",
        "scores",
        "verdict",
    ],
    "additionalProperties": False,
}

PAIRWISE_GENERAL_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "candidate_a_strengths_and_flaws": {"type": "string"},
        "candidate_b_strengths_and_flaws": {"type": "string"},
        "preferred": {"type": "string", "enum": ["A", "B"]},
        "decisive_reason": {"type": "string"},
    },
    "required": [
        "candidate_a_strengths_and_flaws",
        "candidate_b_strengths_and_flaws",
        "preferred",
        "decisive_reason",
    ],
    "additionalProperties": False,
}

GENERAL_AUDIT_PROMPT = """你是一位横跨都市、年代、古装、玄幻、悬疑全赛道的**红果爆款短剧总编审兼盲测观众**。
请对待审方案（含原始创意种子、可选全剧大纲、以及前 3 集《屏幕裸看实况版》——已剥离作者偷写的 `**人物**` 设定行并标注旁人听不见的 `[内心独白VO/OS]`）进行严格、客观、**零题材偏见**的通用审查。

### 四大通用评审准则（适用于任何题材与任何长度的创意种子）

1. **原创意保真与原生卖点放大（`seed_fidelity_and_hook`）**
   - 若提供了【原始创意种子】：大纲与剧本必须**忠实保留**种子里明确给出的人物身份、核心人物关系、关键路线/设定与核心爽点弧线，**严禁拿外部套路模板篡改主角身份或删掉原创意的核心对照线/感情线**！（注：若种子只给了一句话且未指定人名，自拟合理人名与契合该题材的具体情境属于正常扩写，不判篡改；只有违背或丢弃种子核心设定/爽点才判 `seed_distortion_or_dropped_core_hook`）。

2. **全员当期动机与人性渐变自洽（`motivation_and_logic`）**
   - 任何题材中，正反派在每一个时间节点的选择都必须符合其**当下的认知边界、利益诉求与人性心理渐变**。
   - 严查时间线与动机悖论（`timeline_or_motivation_paradox`）：例如背景设定两人曾相守合作多年，结果回到早期节点主角还没反抗，对方就已经无故深恶痛绝赶主角走；或角色明知必死/必亏却无任何心理惯性（如傲慢赌气、虚假甜头诱惑、好面子硬撑）地降智送人头。
   - 严查信息差越界与伪常识（`unintroduced_relation_or_telepathy` / `contrived_prop_or_irrational_charity`）：把旁人听不见的 `[VO]` 当公开台词接话、关键人物整集无称谓致观众看不懂关系、无条件白送巨额股份、跨空间几十秒瞬移、凭空预设奇葩夺产文书。

3. **戏剧张力与人物情绪拉扯浓度（`dramatic_tension_and_emotion`）**
   - 真正让人上头的短剧靠的是**人与人之间的利益碰撞、情感错位、体面拉扯、预期反转与层层递进的情绪兑现**（无论该剧原生爽点是追悔火葬场、身份掉马、护短立威、种田逆袭还是智斗反杀）。
   - 严查“把戏剧写成财税法务审计说明书”（`flat_emotion_or_dry_audit_filler`）：若大纲或台词堆满枯燥的法规文号、零碎流水台账、产权公证术语，挤占了鲜活的人物交锋与心理落差；或者全员只会干瘪喊口号骂街而无实质处境/情绪变化，必须重罚！

4. **多集连载节奏与裸看清晰度（`serial_pacing_and_clarity`）**
   - 实证规律：1 集（约 2 分钟）承载不了 1 个完整大事件，真实爆款平均 `4～6 集` 共同承载 1 个完整阶段事件。前 3 集只需围绕开局第 1 个核心事件走稳 `1～2` 个扎实的戏剧回合（每集 20～32 句自然口语对白），把前因后果与人物张力演透，集尾卡在紧绷未决的悬念钩子上。
   - 严查同场八倍速塞满七八个制裁动作或三集跑完四五个大阶段的快进提纲病（`rushed_fast_forward_cramming`）。

### 裁决纪律
- **实事求是，零没病硬挑**：若作品忠于创意灵魂、人物动机真实可信、情感拉扯有劲、连载节奏从容清晰，则 `flaws` **必须返回空数组 `[]`**，`verdict` 判 `PASS_HIT_READY`！
- 若确有上述致命硬伤，准确引用原文证据指出并判 `REJECT_REWRITE`。
"""

PAIRWISE_GENERAL_PROMPT = """你是一位阅片无数的**红果短剧总编审兼真实付费观众代表**。
请在不带任何题材偏见的前提下，盲测对比 **候选 A** 与 **候选 B**，选出真正更有爆款追更吸引力的一方：

优先级准则：
1. **忠于原创意灵魂并把原生戏剧张力拉满 > 套模板魔改或丢掉核心爽点**（若提供了原始创意种子，优先核对谁真正写出了种子里最抓人的人物关系与核心爽点）。
2. **鲜活的人性心理博弈与情绪拉扯感 > 枯燥的财税法务说明书或干瘪喊口号**（人物有真实的傲慢、侥幸、失衡、护短、试探或震动，台词自然接地气）。
3. **时间线、信息边界与当期动机 100% 自洽**（无时间线悖论、无读心术、无塑料巧合或无脑送股份）。
4. **多集从容连载的沉浸追更感 > 八倍速塞事件的提纲快进感**（屏幕裸看人物关系清楚，集尾钩子让人抓心挠肝想点下一集）。
"""


def call_isolated_agy(prompt: str, schema: Dict[str, Any], timeout: int = 420) -> Dict[str, Any]:
    sfx = "\n\n【系统执行约束：严禁调用任何文件读写或终端工具！请直接按 JSON Schema 一次性返回结构化结果。】"
    last_err = ""
    for attempt in range(1, 4):
        with tempfile.TemporaryDirectory(prefix="iso-genjudge-agy-") as empty_dir:
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
                so = env.get("structured_output") if isinstance(env, dict) else None
                if isinstance(so, dict):
                    return so
                raw = env.get("response", proc.stdout) if isinstance(env, dict) else proc.stdout
                return raw if isinstance(raw, dict) else _extract_first_json(str(raw))
            except Exception as exc:
                last_err = str(exc)
                time.sleep(2 * attempt)
                continue
    raise RuntimeError(f"Isolated agy judge ({JUDGE_MODEL}) failed: {last_err}")


def audit_drama_general(
    script_md: str,
    *,
    seed: str = "",
    outline_md: str = "",
) -> Dict[str, Any]:
    stripped = STS.strip_script_to_screen(script_md)
    parts = [GENERAL_AUDIT_PROMPT]
    if seed.strip():
        parts.append("# 原始创意种子（核对核心人物关系、设定与原生情绪爽点是否保真并放大）\n\n" + seed.strip())
    if outline_md.strip():
        parts.append("# 全剧故事大纲（核对长线戏剧张力、阶段节奏与情绪弧线，严防写成枯燥审计报告）\n\n" + outline_md.strip()[:8000])
    parts.append("# 前 3 集《屏幕裸看实况版》\n\n" + stripped["screen_markdown"])

    rep = call_isolated_agy("\n\n".join(parts), GENERAL_AUDIT_SCHEMA)
    sc = rep["scores"]
    total = round(
        (
            sc["seed_fidelity_and_hook"]
            + sc["motivation_and_logic"]
            + sc["dramatic_tension_and_emotion"]
            + sc["serial_pacing_and_clarity"]
        )
        * 2.5,
        2,
    )
    rep["total_score"] = total
    rep["screen_diagnostics"] = stripped["episodes"]
    min_dim = min(sc.values())
    if rep["flaws"] or total < 80.0 or min_dim < 7.0:
        rep["verdict"] = "REJECT_REWRITE"
    else:
        rep["verdict"] = "PASS_HIT_READY"
    return rep


def compare_swap_debiased_general(
    label_1: str,
    script_1_md: str,
    label_2: str,
    script_2_md: str,
    *,
    seed: str = "",
    outline_1_md: str = "",
    outline_2_md: str = "",
    parallel_swaps: bool = True,
) -> Dict[str, Any]:
    s1_screen = STS.strip_script_to_screen(script_1_md)["screen_markdown"]
    s2_screen = STS.strip_script_to_screen(script_2_md)["screen_markdown"]

    seed_block = f"\n\n# 原始创意种子\n\n{seed.strip()}\n" if seed.strip() else ""
    has_both_outlines = bool(outline_1_md.strip() and outline_2_md.strip())

    def pack_cand(tag: str, out_md: str, scr_md: str) -> str:
        body = ""
        if has_both_outlines:
            body += f"### 候选 {tag} · 全剧大纲节选\n{out_md.strip()[:5500]}\n\n"
        body += f"### 候选 {tag} · 前 3 集《屏幕裸看实况版》\n{scr_md}"
        return body

    p_fwd = (
        PAIRWISE_GENERAL_PROMPT
        + seed_block
        + "\n\n==================== 候选 A ====================\n\n"
        + pack_cand("A", outline_1_md, s1_screen)
        + "\n\n==================== 候选 B ====================\n\n"
        + pack_cand("B", outline_2_md, s2_screen)
    )
    p_rev = (
        PAIRWISE_GENERAL_PROMPT
        + seed_block
        + "\n\n==================== 候选 A ====================\n\n"
        + pack_cand("A", outline_2_md, s2_screen)
        + "\n\n==================== 候选 B ====================\n\n"
        + pack_cand("B", outline_1_md, s1_screen)
    )

    if parallel_swaps:
        with cf.ThreadPoolExecutor(max_workers=2) as pool:
            f_fwd = pool.submit(call_isolated_agy, p_fwd, PAIRWISE_GENERAL_SCHEMA, 420)
            f_rev = pool.submit(call_isolated_agy, p_rev, PAIRWISE_GENERAL_SCHEMA, 420)
            r_fwd = f_fwd.result()
            r_rev = f_rev.result()
    else:
        r_fwd = call_isolated_agy(p_fwd, PAIRWISE_GENERAL_SCHEMA, 420)
        r_rev = call_isolated_agy(p_rev, PAIRWISE_GENERAL_SCHEMA, 420)

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
    ap.add_argument("--seed-file", type=Path, default=None)
    ap.add_argument("--outline", type=Path, default=None)
    ap.add_argument("--compare-to", type=Path, default=None)
    ap.add_argument("--compare-outline", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    s1 = args.script_md.read_text(encoding="utf-8")
    seed = args.seed_file.read_text(encoding="utf-8") if args.seed_file and args.seed_file.is_file() else ""
    o1 = args.outline.read_text(encoding="utf-8") if args.outline and args.outline.is_file() else ""

    if args.compare_to:
        s2 = args.compare_to.read_text(encoding="utf-8")
        o2 = args.compare_outline.read_text(encoding="utf-8") if args.compare_outline and args.compare_outline.is_file() else ""
        rep = compare_swap_debiased_general(
            args.script_md.stem, s1, args.compare_to.stem, s2, seed=seed, outline_1_md=o1, outline_2_md=o2
        )
    else:
        rep = audit_drama_general(s1, seed=seed, outline_md=o1)

    txt = json.dumps(rep, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
