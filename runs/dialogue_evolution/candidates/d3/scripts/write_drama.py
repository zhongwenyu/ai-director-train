#!/usr/bin/env python3
"""
End-to-end driver for `hit-short-drama v6` (100% isolated `agy` `gemini-4-carbon-medium` sub-agents, zero `codex`):
  Any Seed Granularity (1-sentence seed ~ multi-paragraph original brief) across ANY genre
    -> Stage 0: Premise-Fidelity, Timepoint-Motivation & Serial-Span Contract (`00_premise_lock.json`, audited by isolated Critic)
    -> Stage 1: Full-Drama Story Engine & Multi-Episode Serial Outline (`01_outline.md`, ~4-6 eps per complete event stage)
    -> Stage 2: High-Tension Unhurried Continuous Episode Scripts (`episodes/epXXX-YYY.md`, 20-30 spoken lines/ep)
    -> Stage 3: Generalized Seed-Fidelity, Motivation, Tension & Screen-Clarity Gate (`general_arena_judge.py`)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SKILL_DIR = Path(__file__).resolve().parent.parent
TRAIN_ROOT = SKILL_DIR.parent.parent
for p in (str(SKILL_DIR / "scripts"), str(TRAIN_ROOT / "judge"), str(TRAIN_ROOT / "trainer")):
    if p not in sys.path:
        sys.path.insert(0, p)

import script_check as SC  # noqa: E402
import strip_to_screen as STS  # noqa: E402
import general_arena_judge as GJ  # noqa: E402
import dialogue_turing_judge as DTJ  # noqa: E402

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
AGY_MODEL = os.environ.get("HIT_DRAMA_AGY_MODEL", "gemini-4-carbon-medium")
AGY_EFFORT = os.environ.get("HIT_DRAMA_AGY_EFFORT", "medium")

MARKDOWN_DOC_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "markdown": {
            "type": "string",
            "description": "完整的 Markdown 正文（严禁调用任何读写文件或终端工具，直接在此字段返回完整 Markdown 文本）",
        }
    },
    "required": ["markdown"],
    "additionalProperties": False,
}

PREMISE_LOCK_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "genre_and_world": {
            "type": "string",
            "description": "本剧原生题材、年代与世界观语境（忠于原创意，不强套固定模板，40字内）",
        },
        "seed_explicit_invariants": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 2,
            "maxItems": 8,
            "description": "从用户原始创意中逐条提炼的不可篡改事实锚点（明确给出的人物身份、核心人物关系、关键设定、平行对照线与终局目标；原创意有的必须100%保留，严禁魔改或丢弃！）",
        },
        "core_conflict_and_tracks": {
            "type": "string",
            "description": "本剧的核心戏剧矛盾与主副线推进结构（若有平行对照线则写清双方对照演进，若为单线闯关/复仇/种田/甜宠则写清核心阻力递进，110字内）",
        },
        "timepoint_motivation_map": {
            "type": "string",
            "description": "全员分时动机自洽验算：在开局起点（T=0）及后续阶段，主角、对手/前任、盟友各自凭什么认知边界、利益诉求或人性惯性做出选择？（严防时间线自相矛盾与脸谱化无脑降智，130字内）",
        },
        "native_emotional_payoff_arc": {
            "type": "string",
            "description": "本剧原生的核心情绪钩子与爽点兑现递进（识别本剧自身最抓人的情绪点——如撤回偏爱后的傲慢→膨胀→硬撑→悔恨、或身份掉马、护短反杀、绝境逆袭等，严禁堆砌枯燥财税法务流水账，110字内）",
        },
        "stage1_multi_episode_event": {
            "type": "string",
            "description": "第1～5集共同承载的开局第1个完整戏剧事件总述（遵循红果4～6集共载一事规律，75字内）",
        },
        "ep1_to_3_serial_beats": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 3,
            "maxItems": 3,
            "description": "前3集从容连载分幕规划（每集1～2个实质回合，铺清人物关系称谓，演绎情绪暗流与冲突升级，集尾卡在紧绷悬念处）",
        },
    },
    "required": [
        "title",
        "genre_and_world",
        "seed_explicit_invariants",
        "core_conflict_and_tracks",
        "timepoint_motivation_map",
        "native_emotional_payoff_arc",
        "stage1_multi_episode_event",
        "ep1_to_3_serial_beats",
    ],
    "additionalProperties": False,
}

PREMISE_AUDIT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "ok": {"type": "boolean"},
        "issues": {
            "type": "array",
            "items": {"type": "string"},
            "description": "逐条核查：1.是否篡改或丢弃了用户原始创意里的明确人物身份、关系或关键对照路线？2.是否存在时间线或当期人物动机自相矛盾？3.是否前3集塞入过多阶段快进速通？4.是否把戏剧爽点写成了枯燥财税法务说明书或生造违和套路？完全保真自洽从容则返回空数组 []",
        },
    },
    "required": ["ok", "issues"],
    "additionalProperties": False,
}


def strip_fence(text: str) -> str:
    s = text.strip()
    m = re.match(r"^```[a-zA-Z0-9_-]*\s*\n(.*)\n```\s*$", s, re.S)
    return m.group(1).strip() if m else s


def extract_json_obj(text: str) -> Dict[str, Any]:
    s = strip_fence(text)
    dec = json.JSONDecoder()
    for i, ch in enumerate(s):
        if ch == "{":
            try:
                obj, _ = dec.raw_decode(s[i:])
                if isinstance(obj, dict):
                    return obj
            except ValueError:
                continue
    raise ValueError(f"No JSON object found in: {text[:300]!r}")


def run_isolated_agy(
    prompt: str,
    *,
    schema: Optional[Dict[str, Any]] = None,
    timeout: int = 480,
    retries: int = 3,
    check_fn=None,
    error_feedback_fn=None,
) -> str:
    """Spawn a fresh, zero-history, sandboxed `agy` sub-agent (`gemini-4-carbon-medium`) in an empty `/tmp` dir."""
    use_md_wrapper = schema is None
    eff_schema = MARKDOWN_DOC_SCHEMA if use_md_wrapper else schema
    base_suffix = (
        "\n\n【系统执行约束：严禁调用任何读写文件或终端工具！请直接将完整 Markdown 正文填入 JSON 的 `markdown` 字段一次性返回。】"
        if use_md_wrapper
        else "\n\n【系统执行约束：严禁调用任何读写文件或终端工具！请直接按 JSON Schema 一次性返回结构化结果。】"
    )
    last_err = ""
    retry_feedback = ""
    for attempt in range(1, retries + 2):
        eff_prompt = (
            prompt
            + (f"\n\n【上一版校验未通过，必须修正以下硬伤后重写】：\n{retry_feedback}" if retry_feedback else "")
            + base_suffix
        )
        with tempfile.TemporaryDirectory(prefix="hit-drama-v6-agy-") as cwd:
            sp = Path(cwd) / "schema.json"
            sp.write_text(json.dumps(eff_schema, ensure_ascii=False), encoding="utf-8")
            cmd = [
                AGY_BIN,
                "--model",
                AGY_MODEL,
                "--effort",
                AGY_EFFORT,
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
                    cmd, cwd=cwd, input=eff_prompt, capture_output=True, text=True, timeout=timeout
                )
            except subprocess.TimeoutExpired:
                last_err = f"timeout {timeout}s (attempt {attempt})"
                time.sleep(2 * attempt)
                continue
        if proc.returncode != 0:
            last_err = f"exit {proc.returncode}: {(proc.stderr or proc.stdout)[-600:]}"
            time.sleep(2 * attempt)
            continue
        try:
            env = json.loads(proc.stdout)
            so = (env or {}).get("structured_output") if isinstance(env, dict) else None
            if isinstance(so, dict):
                parsed = so
            else:
                raw = (env or {}).get("response") if isinstance(env, dict) else proc.stdout
                parsed = raw if isinstance(raw, dict) else extract_json_obj(str(raw or ""))
            text = strip_fence(str(parsed.get("markdown") or "")) if use_md_wrapper else json.dumps(parsed, ensure_ascii=False)
        except Exception as exc:
            last_err = f"json parse error: {exc}"
            time.sleep(2 * attempt)
            continue
        if not text.strip():
            last_err = "empty response"
            time.sleep(2 * attempt)
            continue
        if error_feedback_fn is not None:
            fb = error_feedback_fn(text)
            if fb:
                retry_feedback = fb
                last_err = f"validation feedback: {fb}"
                continue
        if check_fn and not check_fn(text):
            last_err = f"failed validation (len={len(text)}): {text[:240]!r}"
            time.sleep(2 * attempt)
            continue
        return text
    raise RuntimeError(f"Isolated agy sub-agent ({AGY_MODEL}) failed: {last_err}")


def generate_premise_lock(
    idea_text: str,
    out_dir: Path,
    *,
    skill_dir: Path = SKILL_DIR,
    force: bool = False,
) -> Dict[str, Any]:
    lock_path = out_dir / "00_premise_lock.json"
    if lock_path.is_file() and not force:
        return json.loads(lock_path.read_text(encoding="utf-8"))

    tmpl = (skill_dir / "prompts/stage0_premise_lock.md").read_text(encoding="utf-8")
    feedback = ""
    lock_obj: Dict[str, Any] = {}
    for r in range(1, 4):
        prompt = tmpl + "\n\n# 用户输入的原始创意\n\n" + idea_text.strip()
        if feedback:
            prompt += f"\n\n# 上一轮立项审查驳回意见（必须逐条修正！）\n\n{feedback}"
        raw = run_isolated_agy(prompt, schema=PREMISE_LOCK_SCHEMA, timeout=360)
        lock_obj = extract_json_obj(raw)

        audit_prompt = (
            "你是一位零题材偏见的红果爆款短剧立项总审。\n"
            "请对照【用户原始创意】严格审查以下《Stage 0 立项锁》：\n"
            "1. 原创意保真：用户原话明确给出的人物身份（如大学生/猎户/王妃/律师/末世者等）、人物关系、核心设定或平行对照路线，是否被擅自篡改或遗漏？（若用户只给了一句话未提姓名细节，合理补齐人名与情境属正常扩写，不判篡改）；\n"
            "2. 分时动机自洽：各角色在开局 T=0 与前史/后续阶段的选择是否符合真实人性与知情边界？有无“前世相伴多年、回到早期却无故深恶痛绝赶人”等时间线悖论？\n"
            "3. 情绪张力纯粹度：是否抓准了该创意的原生情绪爽点，有无堆砌枯燥财税公文术语或硬塞违和模板套路？\n"
            "4. 跨集连载节奏：前 3 集是否从容聚焦开局第 1 个核心事件的前三幕（约 4～6 集共载一事），有无把四五个大阶段硬塞进前 3 集速通？\n"
            "完全合格返回 ok=true, issues=[]；否则返回 ok=false 并指出具体修改要求。\n\n"
            "【用户原始创意】：\n" + idea_text.strip() + "\n\n"
            "【待审立项锁】：\n" + json.dumps(lock_obj, ensure_ascii=False, indent=2)
        )
        audit_raw = run_isolated_agy(audit_prompt, schema=PREMISE_AUDIT_SCHEMA, timeout=300)
        audit = extract_json_obj(audit_raw)
        if audit.get("ok") and not audit.get("issues"):
            print(f"[stage0] Premise Lock PASSED on round {r}: {lock_obj['title']}", flush=True)
            break
        feedback = "\n".join(audit.get("issues") or [])
        print(f"[stage0] Premise Lock rejected on round {r}: {feedback}", flush=True)

    out_dir.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps(lock_obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return lock_obj


def pick_genre_examples(skill_dir: Path, text_hint: str) -> str:
    ex_dir = skill_dir / "examples"
    if not ex_dir.is_dir():
        return ""
    if any(k in text_hint for k in ("修仙", "灵葫", "空间", "末日", "末世", "系统", "异界", "灵气", "丧尸")):
        target = "fantasy_system_hit.md"
    elif any(k in text_hint for k in ("皇", "朝廷", "世子", "王妃", "乱世", "穿越", "流放", "县令", "古", "太子")):
        target = "ancient_hit.md"
    elif any(k in text_hint for k in ("七零", "八零", "九零", "1958", "1977", "1983", "93", "供销社", "赶海", "赶山", "村", "知青", "猎")):
        target = "rural_era_hit.md"
    else:
        target = "urban_hit.md"
    p = ex_dir / target
    if not p.is_file():
        files = sorted(ex_dir.glob("*.md"))
        if not files:
            return ""
        p = files[0]
    return p.read_text(encoding="utf-8")[:16000]


def generate_outline(
    idea_text: str,
    premise_lock: Dict[str, Any],
    out_dir: Path,
    *,
    skill_dir: Path = SKILL_DIR,
    plan_up_to_ep: int = 15,
    force: bool = False,
) -> Path:
    outline_path = out_dir / "01_outline.md"
    if outline_path.is_file() and not force:
        return outline_path

    tmpl = (skill_dir / "prompts/stage1_outline.md").read_text(encoding="utf-8")
    story_engine = (skill_dir / "references/story-engine.md").read_text(encoding="utf-8")
    playbooks = (skill_dir / "references/playbooks.md").read_text(encoding="utf-8")

    ep_range_str = f"第 1～{plan_up_to_ep} 集"
    prompt = "\n\n".join([
        tmpl.format(episode_plan_range=ep_range_str),
        "# 参考资料 1：全剧故事引擎法则\n\n" + story_engine,
        "# 参考资料 2：多赛道情绪承诺与阻力参考\n\n" + playbooks,
        "# 已锁死的《Stage 0 原创意保真与分时动机立项锁》（必须 100% 忠实执行！）\n\n"
        + json.dumps(premise_lock, ensure_ascii=False, indent=2),
        "# 用户输入的原始创意\n\n" + idea_text.strip(),
    ])

    text = run_isolated_agy(
        prompt,
        timeout=600,
        check_fn=lambda t: (
            len(t) >= 1200
            and bool(re.search(r"第\s*0*1\s*集", t))
            and bool(re.search(rf"第\s*0*{min(5, plan_up_to_ep)}\s*集", t))
        ),
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    outline_path.write_text(text + "\n", encoding="utf-8")
    return outline_path


def update_ledger_heuristic(
    prev_ledger: Dict[str, Any], batch_eps: List[int], script_md: str
) -> Dict[str, Any]:
    blocks = list(SC.RE_EP_HEADER.finditer(script_md))
    last_ep_tail = ""
    if blocks:
        last_body = script_md[blocks[-1].start():].strip()
        lines = [ln for ln in last_body.splitlines() if ln.strip()]
        last_ep_tail = "\n".join(lines[-16:])
    completed = sorted(set(prev_ledger.get("completed_episodes", []) + batch_eps))
    return {
        "completed_episodes": completed,
        "last_episode": batch_eps[-1],
        "last_episode_tail": last_ep_tail,
    }


def generate_episode_batch(
    idea_text: str,
    premise_lock: Dict[str, Any],
    outline_text: str,
    batch_eps: List[int],
    out_dir: Path,
    *,
    skill_dir: Path = SKILL_DIR,
    prev_tail: str = "",
    prior_script: str = "",
    force: bool = False,
) -> Tuple[Path, Dict[str, Any]]:
    ep_dir = out_dir / "episodes"
    ep_dir.mkdir(parents=True, exist_ok=True)
    tag = f"ep{batch_eps[0]:03d}-{batch_eps[-1]:03d}"
    script_path = ep_dir / f"{tag}.md"
    stats_path = ep_dir / f"{tag}.check.json"

    if script_path.is_file() and not force:
        rep = SC.analyze_script(script_path.read_text(encoding="utf-8"), batch_eps)
        return script_path, rep

    tmpl = (skill_dir / "prompts/stage2_episodes.md").read_text(encoding="utf-8")
    craft = (skill_dir / "references/episode-craft.md").read_text(encoding="utf-8")
    anti = (skill_dir / "references/anti-patterns.md").read_text(encoding="utf-8")
    genre_ref = pick_genre_examples(skill_dir, idea_text + "\n" + premise_lock.get("genre_and_world", ""))

    batch_str = (
        f"第 {batch_eps[0]} 集"
        if len(batch_eps) == 1
        else f"第 {batch_eps[0]}～{batch_eps[-1]} 集（共 {len(batch_eps)} 集连续连载）"
    )
    parts = [
        tmpl.format(batch_range=batch_str),
        "# 核心分集工艺法则\n\n" + craft,
        "# 严禁出现的病灶对照表\n\n" + anti,
    ]
    if genre_ref:
        parts.append(
            "# 同赛道红果真实爆款「3集连续连载」质感标杆（学习其从容连载节奏、鲜活短句与情绪拉扯，严禁抄袭人名剧情！）\n\n"
            + genre_ref
        )
    parts.append("# 用户原始创意（确保核心人物关系与原生爽点不走样！）\n\n" + idea_text.strip())
    parts.append(
        "# 已锁死的《Stage 0 原创意保真与分时动机立项锁》\n\n"
        + json.dumps(premise_lock, ensure_ascii=False, indent=2)
    )
    parts.append("# 本剧《全剧故事引擎与分集大纲》\n\n" + outline_text.strip())
    if prior_script.strip():
        parts.append("# 前序已定稿剧集正文\n\n" + prior_script.strip()[-14000:])
    elif prev_tail.strip():
        parts.append("# 上一批最后一集结尾实况\n\n" + prev_tail.strip())

    parts.append(
        f"# 本次写作任务硬性指令\n\n"
        f"请严格写出 **{batch_str}** 的完整分集剧本正文（集号依次为 {batch_eps}），每集以 `【本集完】` 结束。\n"
        f"- **情绪张力与原味保真**：忠于原创意人物身份与关系，用鲜活的人情潜台词与心理反差拉满戏剧张力，严禁写成枯燥算账或公文说明书！\n"
        f"- **从容连载节奏**：每集写 **20～28 句自然有声对话+心声**（每集台词总字数 340～520 字，预估时长 **105～155 秒**，严禁超过 185 秒），每集 `1～3` 个场景，把出场人物关系与当期动机演透，集尾卡在紧绷未决的钩子处！\n"
        f"- **鲜活口语短句**：句均字数 **<= 22 字**，单句不超过 **50 字**！"
    )

    def batch_err_fb(txt: str) -> Optional[str]:
        rep = SC.analyze_script(txt, batch_eps)
        if not rep["ok"]:
            msg = "；".join(rep["hard_errors"])
            print(f"  [script_check reject] {msg}", flush=True)
            return msg
        return None

    script_md = run_isolated_agy("\n\n".join(parts), timeout=600, retries=3, error_feedback_fn=batch_err_fb)
    script_path.write_text(script_md + "\n", encoding="utf-8")
    rep = SC.analyze_script(script_md, batch_eps)
    stats_path.write_text(json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return script_path, rep


def polish_episode_dialogue(
    draft_md: str,
    premise_lock: Dict[str, Any],
    batch_eps: List[int],
    *,
    skill_dir: Path = SKILL_DIR,
    idea_text: str = "",
) -> str:
    """Stage 2.5: Dedicated Colloquial Dialogue Doctor (`stage2_5_dialogue_polish.md` + `dialogue-voice.md`).
    Locks episode/scene structure, actions, and plot facts 100%, rewriting stiff AI twin-clause/summary lines into
    grounded, character-specific human speech."""
    polish_p = skill_dir / "prompts/stage2_5_dialogue_polish.md"
    voice_p = skill_dir / "references/dialogue-voice.md"
    if not polish_p.is_file() or not voice_p.is_file():
        return draft_md

    polish_tmpl = polish_p.read_text(encoding="utf-8")
    voice_guide = voice_p.read_text(encoding="utf-8")
    genre_ref = pick_genre_examples(skill_dir, idea_text + "\n" + premise_lock.get("genre_and_world", ""))
    pure_dlg_benchmark = ""
    if genre_ref:
        pure_dlg_benchmark = DTJ.extract_pure_dialogue_view(genre_ref)["dialogue_markdown"][:6500]

    orig_scenes = [m.group(1) for m in SC.RE_SCENE_HEADER.finditer(draft_md)]

    parts = [
        polish_tmpl,
        "# 红果爆款真人口语声纹法则\n\n" + voice_guide,
    ]
    if pure_dlg_benchmark:
        parts.append(
            "# 同赛道红果爆款原片「纯对白听感标杆」（体会其长短句呼吸、话咬话反问、2～6字短反应与生活毛边，严禁抄袭具体人名剧情！）\n\n"
            + pure_dlg_benchmark
        )
    parts.append(
        "# 本剧世界观与人物身份锚点\n\n"
        + json.dumps(
            {
                "title": premise_lock.get("title"),
                "genre_and_world": premise_lock.get("genre_and_world"),
                "core_conflict_and_tracks": premise_lock.get("core_conflict_and_tracks"),
                "timepoint_motivation_map": premise_lock.get("timepoint_motivation_map"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    parts.append("# 待去 AI 味口语打磨的初稿剧本（严禁改动场次结构与核心剧情事实，只把假台词换成活人真话！）\n\n" + draft_md.strip())

    def polish_err_fb(txt: str) -> Optional[str]:
        rep = SC.analyze_script(txt, batch_eps)
        if not rep["ok"]:
            msg = "；".join(rep["hard_errors"])
            print(f"  [stage2.5 script_check reject] {msg}", flush=True)
            return msg
        new_scenes = [m.group(1) for m in SC.RE_SCENE_HEADER.finditer(txt)]
        if orig_scenes and new_scenes != orig_scenes:
            msg = f"Stage 2.5 严禁增删场次编号：原场次 {orig_scenes}，当前 {new_scenes}"
            print(f"  [stage2.5 scene_lock reject] {msg}", flush=True)
            return msg
        return None

    return run_isolated_agy("\n\n".join(parts), timeout=600, retries=3, error_feedback_fn=polish_err_fb)


def rewrite_batch_from_general_gate(
    idea_text: str,
    premise_lock: Dict[str, Any],
    outline_text: str,
    batch_eps: List[int],
    prior_script: str,
    current_batch_md: str,
    gate_report: Dict[str, Any],
    *,
    skill_dir: Path = SKILL_DIR,
) -> str:
    craft = (skill_dir / "references/episode-craft.md").read_text(encoding="utf-8")
    anti = (skill_dir / "references/anti-patterns.md").read_text(encoding="utf-8")
    batch_str = f"第 {batch_eps[0]}～{batch_eps[-1]} 集"
    prompt = "\n\n".join([
        f"# Stage 4：根据「通用原味保真·动机·张力·节奏总审」报告重构 {batch_str}\n\n"
        "独立盲审检出了以下影响爆款成色的硬伤，请逐条根治重写：\n"
        "1. 若检出 `seed_distortion_or_dropped_core_hook`：立即恢复用户原始创意中的真实人物身份、关系与核心冲突路线！\n"
        "2. 若检出 `timeline_or_motivation_paradox`：理顺各角色在当前时间点的真实动机与人性心理层次（杜绝未卜先知、无故提前厌恶或弱智送人头）！\n"
        "3. 若检出 `flat_emotion_or_dry_audit_filler`：删掉枯燥财务法务术语，补足人物之间的傲慢、试探、失衡、护短或追悔等鲜活情绪交锋！\n"
        "4. 若检出 `rushed_fast_forward_cramming` 或 `unintroduced_relation_or_telepathy`：放慢到单集 1～2 个回合（20～28 句口语短句，预估时长 105～155 秒），自然带出人物称谓，严守 `[VO]` 旁人听不见边界！\n"
        f"5. 直接输出集号依次为 {batch_eps}、每集以 `【本集完】` 结尾的标准剧本 Markdown 正文。",
        "# 用户原始创意\n\n" + idea_text.strip(),
        "# 《Stage 0 立项锁》\n\n" + json.dumps(premise_lock, ensure_ascii=False, indent=2),
        "# 核心工艺与病灶红线\n\n" + craft + "\n\n" + anti,
        "# 大纲参考\n\n" + outline_text.strip(),
        "# 前序已定稿剧集正文\n\n" + (prior_script.strip()[-12000:] if prior_script.strip() else "（无前序剧集）"),
        "# 被驳回的本批原稿\n\n" + current_batch_md.strip(),
        "# 独立盲审检出的具体问题与修改方向\n\n"
        + json.dumps(
            {
                "native_engine_and_comprehension": gate_report.get("native_engine_and_comprehension"),
                "distinct_major_events_in_3eps": gate_report.get("distinct_major_events_in_3eps"),
                "scores": gate_report.get("scores"),
                "flaws": gate_report.get("flaws"),
            },
            ensure_ascii=False,
            indent=2,
        ),
    ])

    def batch_err_fb(txt: str) -> Optional[str]:
        rep = SC.analyze_script(txt, batch_eps)
        if not rep["ok"]:
            msg = "；".join(rep["hard_errors"])
            print(f"  [rewrite script_check reject] {msg}", flush=True)
            return msg
        return None

    return run_isolated_agy(prompt, timeout=600, retries=3, error_feedback_fn=batch_err_fb)


def parse_ep_range(spec: str) -> List[int]:
    eps: List[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            eps.extend(range(int(a), int(b) + 1))
        else:
            eps.append(int(part))
    return sorted(set(eps))


def run_pipeline(
    idea_text: str,
    out_dir: Path,
    episodes_spec: str = "1-3",
    *,
    batch_size: int = 3,
    skill_dir: Path = SKILL_DIR,
    force: bool = False,
) -> Dict[str, Any]:
    target_eps = parse_ep_range(episodes_spec)
    max_ep = max(target_eps) if target_eps else 3
    plan_up_to = max(12, max_ep)

    premise_lock = generate_premise_lock(idea_text, out_dir, skill_dir=skill_dir, force=force)
    outline_p = generate_outline(
        idea_text, premise_lock, out_dir, skill_dir=skill_dir, plan_up_to_ep=plan_up_to, force=force
    )
    outline_txt = outline_p.read_text(encoding="utf-8")

    ledger_p = out_dir / "state_ledger.json"
    ledger: Dict[str, Any] = (
        json.loads(ledger_p.read_text(encoding="utf-8"))
        if ledger_p.is_file() and not force
        else {"completed_episodes": [], "last_episode": 0, "last_episode_tail": ""}
    )

    batches: List[List[int]] = []
    cur: List[int] = []
    for ep in target_eps:
        if not cur or (ep == cur[-1] + 1 and len(cur) < batch_size):
            cur.append(ep)
        else:
            batches.append(cur)
            cur = [ep]
    if cur:
        batches.append(cur)

    batch_outputs = []
    combined_md_parts = []
    max_gate_rounds = int(os.environ.get("HIT_DRAMA_GATE_ROUNDS", "2"))

    for b in batches:
        prev_tail = ledger.get("last_episode_tail", "") if b[0] == ledger.get("last_episode", 0) + 1 else ""
        prior_script = "\n\n".join(combined_md_parts)
        sp, rep = generate_episode_batch(
            idea_text,
            premise_lock,
            outline_txt,
            b,
            out_dir,
            skill_dir=skill_dir,
            prev_tail=prev_tail,
            prior_script=prior_script,
            force=force,
        )
        md = sp.read_text(encoding="utf-8")
        tag = f"ep{b[0]:03d}-{b[-1]:03d}"
        enable_polish = os.environ.get("HIT_DRAMA_DIALOGUE_POLISH", "1") != "0"
        draft_backup = out_dir / "episodes" / f"{tag}.draft.md"
        if enable_polish and (force or not draft_backup.is_file()):
            draft_backup.write_text(md, encoding="utf-8")
            print(f"[stage2.5] Polishing colloquial dialogue for batch {b}...", flush=True)
            md = polish_episode_dialogue(md, premise_lock, b, skill_dir=skill_dir, idea_text=idea_text)
            sp.write_text(md + "\n", encoding="utf-8")
            rep = SC.analyze_script(md, b)
            (out_dir / "episodes" / f"{tag}.check.json").write_text(
                json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )

        gate_rep: Dict[str, Any] = {}
        for r_idx in range(1, max_gate_rounds + 1):
            print(f"[general-gate] Auditing batch {b} (round {r_idx}/{max_gate_rounds}, model={AGY_MODEL})...", flush=True)
            gate_rep = GJ.audit_drama_general(
                md,
                seed=idea_text,
                outline_md=(outline_txt if b[0] == 1 else ""),
            )
            gate_path = out_dir / "episodes" / f"{tag}.general_gate_r{r_idx}.json"
            gate_path.write_text(json.dumps(gate_rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            if gate_rep["verdict"] == "PASS_HIT_READY":
                print(
                    f"[general-gate] PASS_HIT_READY on batch {b} (round {r_idx}, score={gate_rep['total_score']}, events={gate_rep['distinct_major_events_in_3eps']})!",
                    flush=True,
                )
                break
            flaw_summary = [f["flaw_type"] for f in gate_rep.get("flaws", [])]
            print(
                f"[general-gate] REJECT_REWRITE on batch {b} (round {r_idx}, score={gate_rep['total_score']}, flaws={flaw_summary}) -> rewriting...",
                flush=True,
            )
            if r_idx < max_gate_rounds:
                md = rewrite_batch_from_general_gate(
                    idea_text, premise_lock, outline_txt, b, prior_script, md, gate_rep, skill_dir=skill_dir
                )
                sp.write_text(md + "\n", encoding="utf-8")
                rep = SC.analyze_script(md, b)
                (out_dir / "episodes" / f"{tag}.check.json").write_text(
                    json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )

        combined_md_parts.append(md.strip())
        ledger = update_ledger_heuristic(ledger, b, md)
        ledger_p.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        batch_outputs.append({"batch": b, "path": str(sp), "check": rep, "general_gate": gate_rep})

    combined_path = out_dir / f"combined_{episodes_spec.replace(',', '_')}.md"
    combined_path.write_text("\n\n".join(combined_md_parts) + "\n", encoding="utf-8")
    return {
        "premise_lock_path": str(out_dir / "00_premise_lock.json"),
        "outline_path": str(outline_p),
        "combined_script_path": str(combined_path),
        "batches": batch_outputs,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--idea", help="Inline simple idea text")
    ap.add_argument("--idea-file", help="Path to file containing simple idea")
    ap.add_argument("--out-dir", required=True, help="Output directory")
    ap.add_argument("--episodes", default="1-3", help="Episode range to write, e.g. 1-3 or 1-5")
    ap.add_argument("--batch-size", type=int, default=3)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    if args.idea_file:
        idea_text = Path(args.idea_file).read_text(encoding="utf-8")
    elif args.idea:
        idea_text = args.idea
    else:
        raise SystemExit("Must provide --idea or --idea-file")

    res = run_pipeline(
        idea_text,
        Path(args.out_dir),
        args.episodes,
        batch_size=args.batch_size,
        force=args.force,
    )
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
