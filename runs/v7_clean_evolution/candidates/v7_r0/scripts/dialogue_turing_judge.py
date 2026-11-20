#!/usr/bin/env python3
"""
Pure-Dialogue Stripped Turing Judge & Swap-Debiased Pairwise Arena (`dialogue_turing_judge.py`).

Why whole-script judges miss stiff AI dialogue:
When an LLM judge sees full screenplay Markdown (`△` visual descriptions + plot structure + ASR typos),
clean plot structure masks stiff, stagey, AI-written dialogue ("是你习惯了把别人的付出当免费义务").

How `dialogue_turing_judge.py` isolates 100% pure spoken-voice quality:
  1. `extract_pure_dialogue_view(script_md)` strips out ALL `**人物**` lists, ALL `△` visual/clothing/camera
     descriptions, and ALL `(咬牙切齿)` parenthetical tags (which differ between ASR transcripts and drafts),
     leaving ONLY `[第N集 · 场景 N-M 地点]` + normalized `角色：台词` / `[内心OS] 角色：台词`, plus objective
     prosodic rhythm metrics (`short_line_ratio <= 7 chars`, `twin_clause_symmetry_ratio`, `len_stdev`).
  2. Context-isolated `agy` (`--model gemini-4-carbon-medium --sandbox --disable-slash-commands`) evaluates
     purely by EAR: does this sound like real living people talking/arguing in a hit short drama, or like
     an AI writing neat 16-character twin-clause slogans, essay summaries, and textbook jargon?
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

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
JUDGE_MODEL = os.environ.get("DIALOGUE_JUDGE_MODEL", "gemini-4-carbon-medium")
JUDGE_EFFORT = os.environ.get("DIALOGUE_JUDGE_EFFORT", "medium")

RE_EP_HEADER = re.compile(r"^#{1,2}\s*第\s*(\d+)\s*集[　\s:：—\-]*(.*)$", re.M)
RE_SCENE_HEADER = re.compile(r"^##\s*(\d+-\d+)\s+(.+)$")
RE_META = re.compile(r"^\*\*(?:人物|预估时长)\*\*[：:]")
RE_VO_BRACKET = re.compile(r"^\[(?:VO|OS)\]\s*([^：:\n]+?)(?:（[^）\n]*）|\([^)\n]*\))?[：:]\s*(.+)$")
RE_DIALOGUE = re.compile(
    r"^(?![#△\[\-\*])([^：:\n]{1,24}?)(?:（([^）\n]*)）|\(([^)\n]*)\))?[：:]\s*(.+)$"
)


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
    raise ValueError(f"No valid JSON found: {text[:300]!r}")


def _clean_speaker(raw: str) -> str:
    return re.sub(r"（.*?）|\(.*?\)", "", raw).strip()


def extract_pure_dialogue_view(script_md: str) -> Dict[str, Any]:
    """Strip all `△` descriptions and parentheticals so BOTH real ASR GT and generated scripts
    appear in an identical, formatting-neutral pure-dialogue transcript."""
    ep_matches = list(RE_EP_HEADER.finditer(script_md))
    blocks = []
    if ep_matches:
        for i, m in enumerate(ep_matches):
            ep_no = int(m.group(1))
            start = m.end()
            end = ep_matches[i + 1].start() if i + 1 < len(ep_matches) else len(script_md)
            blocks.append((ep_no, script_md[start:end].strip()))
    else:
        blocks.append((1, script_md.strip()))

    out_lines: List[str] = []
    line_lengths: List[int] = []
    twin_clause_cnt = 0
    short_reaction_cnt = 0
    total_spoken = 0

    for ep_no, body in blocks:
        out_lines.append(f"=== 第 {ep_no} 集（纯对白盲听稿） ===")
        for raw_ln in body.splitlines():
            ln = raw_ln.strip()
            if not ln or RE_META.match(ln) or ln == "【本集完】" or ln.startswith("△") or ln.startswith("[画面文字]"):
                continue
            ms = RE_SCENE_HEADER.match(ln)
            if ms:
                out_lines.append(f"\n[场景 {ms.group(1)}　{ms.group(2).strip()}]")
                continue

            mvo = RE_VO_BRACKET.match(ln)
            if mvo:
                spk = _clean_speaker(mvo.group(1))
                content = mvo.group(2).strip()
                out_lines.append(f"[心声OS] {spk}：{content}")
                clen = len(re.sub(r"[^\w\u4e00-\u9fff]", "", content))
                line_lengths.append(clen)
                total_spoken += 1
                if clen <= 7:
                    short_reaction_cnt += 1
                if re.match(r"^[^，。！？]{5,11}，[^，。！？]{5,11}[。！？]?$", content):
                    twin_clause_cnt += 1
                continue

            mdlg = RE_DIALOGUE.match(ln)
            if mdlg:
                raw_spk = mdlg.group(1).strip()
                if raw_spk in ("人物", "**人物**", "预估时长", "**预估时长**"):
                    continue
                paren = (mdlg.group(2) or mdlg.group(3) or "").strip()
                content = mdlg.group(4).strip()
                spk = _clean_speaker(raw_spk)
                is_os = paren.upper() in ("OS", "VO") or "内心" in paren
                is_bg = "画外" in paren or "电话" in paren or "电子" in paren
                prefix = "[心声OS] " if is_os else ("[画外/电话] " if is_bg else "")
                out_lines.append(f"{prefix}{spk}：{content}")

                clen = len(re.sub(r"[^\w\u4e00-\u9fff]", "", content))
                line_lengths.append(clen)
                total_spoken += 1
                if clen <= 7:
                    short_reaction_cnt += 1
                # Detect monotonous AI 2-clause symmetry: e.g. 7-10 chars + comma + 7-10 chars
                if re.match(r"^[^，。！？]{6,11}，[^，。！？]{6,11}[。！？]?$", content):
                    twin_clause_cnt += 1

        out_lines.append("")

    short_ratio = round(short_reaction_cnt / total_spoken, 3) if total_spoken else 0.0
    twin_ratio = round(twin_clause_cnt / total_spoken, 3) if total_spoken else 0.0
    mean_len = round(statistics.mean(line_lengths), 1) if line_lengths else 0.0
    stdev_len = round(statistics.pstdev(line_lengths), 1) if len(line_lengths) >= 2 else 0.0

    return {
        "dialogue_markdown": "\n".join(out_lines).strip() + "\n",
        "metrics": {
            "total_lines": total_spoken,
            "mean_char_len": mean_len,
            "char_len_stdev": stdev_len,
            "short_reaction_ratio_le7": short_ratio,
            "twin_clause_symmetry_ratio": twin_ratio,
        },
    }


DIALOGUE_TURING_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "ear_test_impression": {
            "type": "string",
            "description": "闭眼听这段纯对白的第一听感：像不像短视频里真实活人张嘴吵架/唠嗑，还是像AI端着写的工整话剧/网文金句？（120字内）",
        },
        "ai_voice_defects": {
            "type": "array",
            "description": "检出的具体『AI味/书面腔/不接地气』台词病灶（必须引用原文具体句子！若整体自然鲜活像真人说话，返回空数组 []）",
            "items": {
                "type": "object",
                "properties": {
                    "quote": {"type": "string", "description": "生硬或AI味重的原句"},
                    "defect_type": {
                        "type": "string",
                        "enum": [
                            "essay_thesis_or_psychology_summary",
                            "monotonous_twin_clause_cadence",
                            "stagey_slogan_or_wuxia_boast",
                            "pedantic_jargon_or_outline_patch",
                            "homogenized_character_voices",
                            "era_or_region_register_mismatch",
                        ],
                    },
                    "how_real_person_would_say_it": {
                        "type": "string",
                        "description": "同一个意思，真实活人在该处境下张嘴会怎么说",
                    },
                },
                "required": ["quote", "defect_type", "how_real_person_would_say_it"],
                "additionalProperties": False,
            },
        },
        "scores": {
            "type": "object",
            "properties": {
                "spoken_naturalness": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 10,
                    "description": "上口度与活人烟火气（零公众号总结金句、零掉书袋术语、零替大纲硬报设定）",
                },
                "conversational_bite_and_rhythm": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 10,
                    "description": "话咬话交锋感与长短句呼吸错落（有顶针反问、2～6字短促反应、停顿重复与语气词，绝非全员整齐16字双分句）",
                },
                "character_voice_distinction": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 10,
                    "description": "人物声纹区分度与身份年代贴脸度（长辈、街坊、势利者、年幼者、古人等各说各的话，不串味不千人一面）",
                },
                "subtext_and_micro_specificity": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 10,
                    "description": "落到具体小事与潜台词张力（只算眼前具体账、具体物件与体面借口，不喊干瘪口号）",
                },
            },
            "required": [
                "spoken_naturalness",
                "conversational_bite_and_rhythm",
                "character_voice_distinction",
                "subtext_and_micro_specificity",
            ],
            "additionalProperties": False,
        },
        "verdict": {"type": "string", "enum": ["PASS_HUMAN_NATURAL", "REJECT_AI_STAGEY"]},
    },
    "required": ["ear_test_impression", "ai_voice_defects", "scores", "verdict"],
    "additionalProperties": False,
}

PAIRWISE_DIALOGUE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "candidate_a_voice_analysis": {"type": "string"},
        "candidate_b_voice_analysis": {"type": "string"},
        "more_human_and_grounded": {"type": "string", "enum": ["A", "B"]},
        "decisive_examples": {
            "type": "string",
            "description": "直接引用双方最典型2～3句台词对比，说明为什么胜出方更像真实活人张嘴说话、落败方更像AI端着写台词",
        },
    },
    "required": [
        "candidate_a_voice_analysis",
        "candidate_b_voice_analysis",
        "more_human_and_grounded",
        "decisive_examples",
    ],
    "additionalProperties": False,
}

DIALOGUE_TURING_PROMPT = """你是一位专门给红果爆款短剧做**「台词盲听图灵测试」**的配音总导演兼方言口语顾问。
现在已隐去所有剧本排版与镜头动作描写，只给你看**纯对白盲听稿**。请你**完全抛开剧情宏大结构，只用耳朵听角色张嘴说的话像不像真实世界里的活人**！

### 重点揪出以下 6 种典型的「AI 端着说话 / 不接地气假台词」：

1. **替编剧总结中心思想 / 情感公众号金句（`essay_thesis_or_psychology_summary`）**
   - ❌ 假台词：“是你习惯了把别人的付出当免费义务。”“开店靠留住食客的胃，光靠噱头撑不过三个月。”
   - ✅ 真人话：吵架只抓眼前具体人、钱、事反问（“你家连亏半年求我来，合着我倒贴方子白干活，还得谢谢你赏饭？”）。
2. **全员清一色 14～18 字工整双分句电报腔（`monotonous_twin_clause_cadence`）**
   - ❌ 假台词：句句都是“前半句七八字，后半句七八字”的对偶工整句，没有一句短促反应，没有口语停顿、重复或语气词，像机器按字数切出来的台词。
   - ✅ 真人话：长短句错落极大！有 1～6 字的本能短反应（“2000？”“你说啥？”“好，给。”“不去。”“这……”），有话咬话的顶针反问（对方说“那是两码事”→立刻顶回去“两码事？当年是谁……”），有急眼或敷衍时的口语重复与语气词（“啊、嘛、喏、得了吧、哭哭哭就知道哭”）。
3. **武侠打擂台口号 / 男频宣言式 OS（`stagey_slogan_or_wuxia_boast`）**
   - ❌ 假台词：现代人说“借一口铁锅一斤牛油，一小时后灶上见真章！”或 OS 喊口号“上辈子负了青梅情分，这辈子换我护着夏家！”
4. **吵架掉书袋背术语 / 替大纲硬报设定补丁（`pedantic_jargon_or_outline_patch`）**
   - ❌ 假台词：街边吵架背科普词“牛排淌的是肌红蛋白还是血水”；或进自家门无端向家人汇报背景“其实街口酒楼抢客，半年后又涨租，店里也难熬”。
5. **千人一面没有声纹区分（`homogenized_character_voices`）**
   - 大学生、农村大婶、势利富二代、餐馆老师傅、孩童，张嘴全是同一种冷静工整的书面语调。
6. **时代/地域语感错位（`era_or_region_register_mismatch`）**
   - 现代剧蹦出“拿乔、置喙、一个时辰”，或古装剧混入违和现代公文词（注：古装/修仙喜剧若故意设计反差人设如文白相间吐槽，只要符合该剧喜剧调性且自然好懂，不判错位）。

### 裁决纪律
- 注意：真实爆款短剧的转写稿偶尔会有个别同音字或口语碎词，**只要说话语气、节奏、长短呼吸和心理潜台词像活生生的人，绝不因个别口语碎词扣分**，`ai_voice_defects` 必须返回 `[]`，判 `PASS_HUMAN_NATURAL`！
- 反之，若整篇对白工整却端着、充斥总结金句、口号与匀称双分句，哪怕没有错别字也必须判 `REJECT_AI_STAGEY`！
"""

PAIRWISE_DIALOGUE_PROMPT = """你是一位专门给红果爆款短剧做**「纯对白图灵盲测」**的配音总导演兼一线观众。
下面 **候选 A** 与 **候选 B** 均已剥离动作与排版，只保留纯角色对白。请**忽略故事题材差异与个别同音转写小瑕疵，100% 凭耳朵盲听「哪一边的台词更接地气、更像真实活人张嘴说出来的话」**！

评判铁律（越靠前权重越高）：
1. **活人日常烟火气 vs AI 公众号总结腔/口号腔**：真人说话只盯眼前具体小事（多少钱、哪件衣服、谁帮的忙）、会顺嘴甩锅或护短；AI 喜欢让角色总结道理（“你把付出当义务”“商业靠口碑留胃”）或喊擂台口号（“一小时见真章”“这辈子换我护她”）。
2. **真实对话的“话咬话”交锋与长短呼吸感 vs 全员 16 字对称双分句**：真人对话有大量 2～6 字短促反应（“你说啥？”“好，给。”“不去。”）、顶针追问、口语重复（“这么丑，做了两晚还这么丑”）和自然语气词（“嘛、啊、喏、哎”）；AI 台词往往句句都是十几个字逗号对半开的整齐书面句。
3. **各色人物声纹鲜明 vs 千人一面话剧腔**：偏心长辈、市井街坊、傲慢前任、年轻学生、古装人物是否各自符合身份年龄，一耳朵听得出是谁在说话，且零掉书袋科普词、零生硬报大纲设定。

请选出台词更接地气、更像真人爆款短剧的一方（`A` 或 `B`）。
"""


def call_isolated_agy(prompt: str, schema: Dict[str, Any], timeout: int = 420) -> Dict[str, Any]:
    sfx = "\n\n【系统执行约束：严禁调用任何文件读写或终端工具！请直接按 JSON Schema 一次性返回结构化结果。】"
    last_err = ""
    for attempt in range(1, 4):
        with tempfile.TemporaryDirectory(prefix="iso-dlgturing-agy-") as empty_dir:
            sp = Path(empty_dir) / "schema.json"
            sp.write_text(json.dumps(schema, ensure_ascii=False), encoding="utf-8")
            cmd = [
                AGY_BIN,
                "--model",
                JUDGE_MODEL,
                "--effort",
                JUDGE_EFFORT,
                "--sandbox",
                "--disable-slash-commands",
                "--output-format",
                "json",
                "--input-format",
                "text",
                "--json-schema",
                str(sp),
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
    raise RuntimeError(f"Isolated agy dialogue judge ({JUDGE_MODEL}) failed: {last_err}")


def audit_dialogue_turing(script_md: str, *, genre_hint: str = "") -> Dict[str, Any]:
    view = extract_pure_dialogue_view(script_md)
    m = view["metrics"]
    prompt_parts = [DIALOGUE_TURING_PROMPT]
    if genre_hint.strip():
        prompt_parts.append(f"# 题材语境提示：{genre_hint.strip()}")
    prompt_parts.append("# 待盲听纯对白文本\n\n" + view["dialogue_markdown"])

    rep = call_isolated_agy("\n\n".join(prompt_parts), DIALOGUE_TURING_SCHEMA)
    sc = rep["scores"]
    total = round(
        (
            sc["spoken_naturalness"]
            + sc["conversational_bite_and_rhythm"]
            + sc["character_voice_distinction"]
            + sc["subtext_and_micro_specificity"]
        )
        * 2.5,
        2,
    )
    rep["total_score"] = total
    rep["rhythm_metrics"] = m
    min_dim = min(sc.values())
    if len(rep["ai_voice_defects"]) >= 2 or total < 80.0 or min_dim < 7.2:
        rep["verdict"] = "REJECT_AI_STAGEY"
    else:
        rep["verdict"] = "PASS_HUMAN_NATURAL"
    return rep


def compare_swap_debiased_dialogue(
    label_1: str,
    script_1_md: str,
    label_2: str,
    script_2_md: str,
    *,
    genre_hint: str = "",
    parallel_swaps: bool = True,
) -> Dict[str, Any]:
    v1 = extract_pure_dialogue_view(script_1_md)
    v2 = extract_pure_dialogue_view(script_2_md)
    g_block = f"\n\n# 题材语境：{genre_hint.strip()}\n" if genre_hint.strip() else ""

    p_fwd = (
        PAIRWISE_DIALOGUE_PROMPT
        + g_block
        + "\n\n==================== 候选 A ====================\n\n"
        + v1["dialogue_markdown"]
        + "\n\n==================== 候选 B ====================\n\n"
        + v2["dialogue_markdown"]
    )
    p_rev = (
        PAIRWISE_DIALOGUE_PROMPT
        + g_block
        + "\n\n==================== 候选 A ====================\n\n"
        + v2["dialogue_markdown"]
        + "\n\n==================== 候选 B ====================\n\n"
        + v1["dialogue_markdown"]
    )

    if parallel_swaps:
        with cf.ThreadPoolExecutor(max_workers=2) as pool:
            f1 = pool.submit(call_isolated_agy, p_fwd, PAIRWISE_DIALOGUE_SCHEMA, 420)
            f2 = pool.submit(call_isolated_agy, p_rev, PAIRWISE_DIALOGUE_SCHEMA, 420)
            r_fwd = f1.result()
            r_rev = f2.result()
    else:
        r_fwd = call_isolated_agy(p_fwd, PAIRWISE_DIALOGUE_SCHEMA, 420)
        r_rev = call_isolated_agy(p_rev, PAIRWISE_DIALOGUE_SCHEMA, 420)

    pick_fwd = label_1 if r_fwd["more_human_and_grounded"] == "A" else label_2
    pick_rev = label_2 if r_rev["more_human_and_grounded"] == "A" else label_1
    consistent = pick_fwd == pick_rev
    return {
        "winner": pick_fwd if consistent else "TIE",
        "swap_consistent": consistent,
        "forward_pick": pick_fwd,
        "reverse_pick": pick_rev,
        "metrics_1": v1["metrics"],
        "metrics_2": v2["metrics"],
        "forward_detail": r_fwd,
        "reverse_detail": r_rev,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("script_md", type=Path)
    ap.add_argument("--genre", default="")
    ap.add_argument("--compare-to", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    s1 = args.script_md.read_text(encoding="utf-8")
    if args.compare_to:
        s2 = args.compare_to.read_text(encoding="utf-8")
        rep = compare_swap_debiased_dialogue(args.script_md.stem, s1, args.compare_to.stem, s2, genre_hint=args.genre)
    else:
        rep = audit_dialogue_turing(s1, genre_hint=args.genre)
    txt = json.dumps(rep, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
