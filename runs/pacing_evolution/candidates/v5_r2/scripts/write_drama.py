#!/usr/bin/env python3
"""
End-to-end driver for `hit-short-drama v5` (100% isolated `agy` `gemini-4-carbon-medium` sub-agents, zero `codex`):
  Ultra-short / Simple Idea (1 sentence ~ 500 chars)
    -> Stage 0.5: Multi-Episode Event-Span & Causal Branch Lock (`00_premise_lock.json`, audited by isolated Critic sub-agent)
    -> Stage 1: Full-Drama Story Engine & Multi-Episode Serial Outline (`01_outline.md`, ~5 eps per complete event stage)
    -> Stage 2: Unhurried Continuous Episode Scripts (`episodes/epXXX-YYY.md`, 22-35 spoken lines/ep, clear context & relationships)
    -> Stage 3: Screen-Stripped Pacing, Clarity & Causal Logic Hard Gate (`pacing_arena_judge.py` on `strip_to_screen.py` output)
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
import pacing_arena_judge as PJ  # noqa: E402

AGY_BIN = (
    os.environ.get("TRAIN_AGY_BIN")
    or ("/home/zhongwenyu/.config/paseo/antigravity-bin/agy"
        if Path("/home/zhongwenyu/.config/paseo/antigravity-bin/agy").is_file()
        else None)
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
        "track_type": {
            "type": "string",
            "enum": ["FAMILY_ETHICS_COUNTERATTACK", "CRAFT_BUSINESS_REBIRTH"],
            "description": "本剧属于家庭伦理亲情反击局，还是手艺创业重生商战局",
        },
        "protagonist_grounded_identity": {
            "type": "string",
            "description": "主角的具体接地气出身与日常处境（严禁985在校大学生无故当街边厨工/学徒！70字内）",
        },
        "past_life_or_backstory_causal_equation": {
            "type": "string",
            "description": "因果分叉方程：过往/前世为何会隐忍付出多年（当年对方如何温情画饼/立约发誓稳住他）vs 今日/今生为何当场翻脸（主角重生主动识破掀桌，或对方期满毁约越过底线，严禁时间线自相矛盾！90字内）",
        },
        "rational_stakes_and_everyday_anchors": {
            "type": "string",
            "description": "各方理性底牌与生活化筹码：对手敢嚣张的误判依据（如偷撕协议/自恃独苗/偷瞄四年自以为学会方子）+ 主角朴素可信的反制筹码或与盟友权责对等的对赌条件（严禁音视频云端公证等科幻商务词、严禁家庭剧硬塞对门律师合伙、严禁无条件白送股份！90字内）",
        },
        "stage1_five_episode_event_unit": {
            "type": "string",
            "description": "第1~5集共同承载的第1个完整戏剧事件单元总述（遵守红果5.56集/事件实证规律，严禁前3集速通四五个阶段！70字内）",
        },
        "ep1_to_3_unhurried_serial_plan": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 3,
            "maxItems": 3,
            "description": "前3集从容连载分幕：第1集（设局蓄压，铺清全部人物称谓关系与前情，停在刺破假面或冲突引爆瞬间原场切集）；第2集（原场下一秒无缝续接，剥开虚伪旧账与对方误判底牌）；第3集（矛盾升级到公开摊牌或谈妥对赌迎击首波封锁，悬置第4~5集正面总清算）",
        },
    },
    "required": [
        "title",
        "track_type",
        "protagonist_grounded_identity",
        "past_life_or_backstory_causal_equation",
        "rational_stakes_and_everyday_anchors",
        "stage1_five_episode_event_unit",
        "ep1_to_3_unhurried_serial_plan",
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
            "description": "若存在：1.前三集塞入过多阶段快进速通（如第1集就签完合营断完油、第3集就摘掉对手招牌）；2.前世今生时间线自相矛盾；3.无条件白送股份或身份违和；4.路人支线或盟友猜忌内耗，则逐条列出问题；完全从容清晰自洽则填空数组 []",
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
    """Spawn a fresh, zero-history, sandboxed `agy` sub-agent (`gemini-4-carbon-medium`) in an empty `/tmp` dir.

    Always passes `--json-schema` (wrapping Markdown outputs in `MARKDOWN_DOC_SCHEMA` when `schema is None`)
    so the sub-agent completes in `num_turns == 1` and NEVER attempts interactive `write_file` tool calls!
    """
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
        eff_prompt = prompt + (f"\n\n【上一版校验未通过，必须修正以下硬伤后重写】：\n{retry_feedback}" if retry_feedback else "") + base_suffix
        with tempfile.TemporaryDirectory(prefix="hit-drama-v5-agy-") as cwd:
            sp = Path(cwd) / "schema.json"
            sp.write_text(json.dumps(eff_schema, ensure_ascii=False), encoding="utf-8")
            cmd = [
                AGY_BIN,
                "--model", AGY_MODEL,
                "--effort", AGY_EFFORT,
                "--sandbox",
                "--disable-slash-commands",
                "--output-format", "json",
                "--input-format", "text",
                "--json-schema", str(sp),
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
        prompt = tmpl + "\n\n# 用户输入的简短创意\n\n" + idea_text.strip()
        if feedback:
            prompt += f"\n\n# 上一轮立项审查驳回意见（必须彻底放慢节奏、修补因果！）\n\n{feedback}"
        raw = run_isolated_agy(prompt, schema=PREMISE_LOCK_SCHEMA, timeout=360)
        lock_obj = extract_json_obj(raw)

        audit_prompt = (
            "你是一位严格遵循红果爆款实证规律（1个完整戏剧事件横跨4~6集连载，绝不快进塞事件）的短剧立项总审。\n"
            "请审查以下《短剧立项锁》是否踩中任何一条红线：\n"
            "1. 前3集推进过快、硬塞四五个阶段（例如第1集就把决裂+过街签合营+断油抢单全演完，或第3集就把反派老店摘牌演完大结局！前3集必须只从容连载第1个核心事件的前三幕，Ep1->Ep2最好同场无缝续接）；\n"
            "2. 前世今生时间线自相矛盾（当年反派本就嫌弃赶人，前世怎么可能留下来替反派干十年？必须是当年笑脸画大饼哄骗，今生主角主动识破掀桌）；\n"
            "3. 无条件白送50%股份慈善（缺乏主角亲口提出的对赌军令状）或反派口嗨封杀全城原料；\n"
            "4. 家庭婚姻/房产亲情剧强行画蛇添足生造“走廊偶遇对门律师合伙签分成军令状”或“音视频云端公证书、实时连线政务办锁死”等塑料AI八股（家庭剧前3集必须扎根家庭修罗场内部，用手机照片、撤回转账、撕毁逼签协议等朴素日常筹码）；\n"
            "5. 身份违和（如985在校大学生无故当街边厨工）、第2集路人支线注水或盟友猜忌内耗。\n"
            "全部从容合理则返回 ok=true, issues=[]；否则返回 ok=false 并指出具体修改要求。\n\n"
            + json.dumps(lock_obj, ensure_ascii=False, indent=2)
        )
        audit_raw = run_isolated_agy(audit_prompt, schema=PREMISE_AUDIT_SCHEMA, timeout=300)
        audit = extract_json_obj(audit_raw)
        if audit.get("ok") and not audit.get("issues"):
            print(f"[stage0.5] Premise Lock PASSED on round {r}: {lock_obj['title']}", flush=True)
            break
        feedback = "\n".join(audit.get("issues") or [])
        print(f"[stage0.5] Premise Lock rejected on round {r}: {feedback}", flush=True)

    out_dir.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps(lock_obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return lock_obj


def pick_genre_examples(skill_dir: Path, text_hint: str) -> str:
    ex_dir = skill_dir / "examples"
    if not ex_dir.is_dir():
        return ""
    if any(k in text_hint for k in ("七零", "八零", "九零", "1958", "1977", "1983", "93", "2000", "2005", "供销社", "赶海", "赶山", "村", "知青", "学徒", "老街")):
        target = "rural_era_hit.md"
    elif any(k in text_hint for k in ("皇", "朝廷", "世子", "王妃", "乱世", "穿越", "流放", "县令")):
        target = "ancient_hit.md"
    elif any(k in text_hint for k in ("修仙", "灵葫", "空间", "末日", "末世", "系统", "异界")):
        target = "fantasy_system_hit.md"
    else:
        target = "urban_hit.md"
    p = ex_dir / target
    if not p.is_file():
        files = sorted(ex_dir.glob("*.md"))
        if not files:
            return ""
        p = files[0]
    # Keep full 3-episode continuous gold example (~13-17KB) intact so model sees Ep1 -> Ep2 -> Ep3 continuity!
    return p.read_text(encoding="utf-8")[:18500]


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
        "# 参考资料 2：赛道专属打法\n\n" + playbooks,
        "# 已锁死的《Stage 0.5 跨集连载与因果立项锁》（必须 100% 严格执行，严禁压缩跳步赶进度！）\n\n"
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
    urban_3ep_ref = (skill_dir / "examples/urban_hit.md").read_text(encoding="utf-8")[:15000]
    genre_ref = pick_genre_examples(skill_dir, idea_text + "\n" + outline_text[:1000])

    batch_str = (
        f"第 {batch_eps[0]} 集"
        if len(batch_eps) == 1
        else f"第 {batch_eps[0]}～{batch_eps[-1]} 集（共 {len(batch_eps)} 集连续连载）"
    )
    parts = [
        tmpl.format(batch_range=batch_str),
        "# 核心工艺法则\n\n" + craft,
        "# 严禁出现的 AI 病灶对照表\n\n" + anti,
        "# 红果真实爆款「3集连续连载同一核心事件」节奏标杆（重点学习其 3 集深挖同一现场、每集 25~35 句把人物关系与前情拉扯演透、集间同场下一秒无缝续接的从容节奏！严禁抄袭人名剧情！）\n\n"
        + urban_3ep_ref,
    ]
    if genre_ref and genre_ref[:200] != urban_3ep_ref[:200]:
        parts.append(
            "# 同赛道真实爆款活人短句质感参考\n\n" + genre_ref[:12000]
        )
    parts.append(
        "# 已锁死的《Stage 0.5 跨集连载与因果立项锁》（必须严格按 ep1_to_3_unhurried_serial_plan 的慢工连载进度执行，严禁快进跳步！）\n\n"
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
        f"- **反快进慢工铁律**：每集写 **20～28 句自然有声对话+心声**（每集台词总字数 340～500 字，预估时长 **105～155 秒**，严禁超过 185 秒！），每集最多 **1～3 个场景**，把每个出场人物的关系称谓、前世/过往受骗真相、反派虚伪画饼与主角主导谈判的条件 **100% 说清楚演明白**！\n"
        f"- **跨集连载咬合**：集尾卡在同一现场冲突最紧绷的瞬间，下一集第 1 行在原场景下一秒无缝续接！\n"
        f"- **活人大白话短句**：句均字数 **<= 22 字**，单句不超过 **50 字**！"
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


def rewrite_batch_from_pacing_gate(
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
        f"# Stage 4：根据「裸看屏幕节奏与因果总审」驳回报告彻底重构 {batch_str}\n\n"
        "一名完全没看过大纲、只看《屏幕裸看实况版》的独立评审打回了本批剧本！\n"
        "**重构铁律**：\n"
        "1. **如果存在快进塞事件/跳跃突兀（`rushed_unexplained_jump`）**：立刻砍掉超前塞进来的后续阶段事件，放慢节奏用 3 集连载把第 1 个核心事件的前因后果、虚伪画饼和谈判细节一层层演透，集与集之间同场下一秒无缝续接！\n"
        "2. **如果存在人物关系未交代、读心术或哑巴主角**：确保每个关键人物出场前两句自然叫出称谓（爸/叔/师兄/厂长），主角在所有交锋与结盟场次亲口主导条件并立下对赌军令状！\n"
        "3. **如果存在前世今生时间线悖论**：确保第 1 集开场演明前世受骗真相，且回到当年时反派先笑脸画饼稳住主角、由重生主角主动掀桌才翻脸！\n"
        "4. 每集写 **20～28 句** 通俗活人短句（每集台词总字数 340～500 字，句均 <= 22 字，单句 <= 50 字，单集预估时长 105～155 秒，严禁超过 185 秒！）。\n"
        f"5. 直接输出集号依次为 {batch_eps}、每集以 `【本集完】` 结尾的标准剧本 Markdown 正文，不要任何解释。",
        "# 《Stage 0.5 跨集连载立项锁》\n\n" + json.dumps(premise_lock, ensure_ascii=False, indent=2),
        "# 核心工艺与病灶红线\n\n" + craft + "\n\n" + anti,
        "# 大纲参考\n\n" + outline_text.strip(),
        "# 前序已定稿剧集正文\n\n" + (prior_script.strip()[-12000:] if prior_script.strip() else "（无前序剧集）"),
        "# 被驳回的本批原稿\n\n" + current_batch_md.strip(),
        "# 独立评审检出的具体病灶与修复要求（必须逐条根治！）\n\n"
        + json.dumps(
            {
                "viewer_comprehension_summary": gate_report.get("viewer_comprehension_summary"),
                "distinct_major_events_counted": gate_report.get("distinct_major_events_counted"),
                "pacing_diagnosis": gate_report.get("pacing_diagnosis"),
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
    plan_up_to = max(8, max_ep)

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
    max_gate_rounds = int(os.environ.get("HIT_DRAMA_GATE_ROUNDS", "3"))

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
        gate_rep: Dict[str, Any] = {}
        for r_idx in range(1, max_gate_rounds + 1):
            print(f"[pacing-clarity-gate] Auditing batch {b} (round {r_idx}/{max_gate_rounds}, model={AGY_MODEL})...", flush=True)
            gate_rep = PJ.audit_three_episode_arc(md)
            gate_path = out_dir / "episodes" / f"{tag}.pacing_gate_r{r_idx}.json"
            gate_path.write_text(json.dumps(gate_rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            if gate_rep["verdict"] == "PASS_IMMERSIVE":
                print(
                    f"[pacing-clarity-gate] PASS_IMMERSIVE on batch {b} (round {r_idx}, score={gate_rep['total_score']}, events={gate_rep['distinct_major_events_counted']})!",
                    flush=True,
                )
                break
            flaw_summary = [f["flaw_type"] for f in gate_rep.get("flaws", [])]
            print(
                f"[pacing-clarity-gate] REJECT_REWRITE on batch {b} (round {r_idx}, events={gate_rep['distinct_major_events_counted']}, flaws={flaw_summary}) -> rewriting...",
                flush=True,
            )
            if r_idx < max_gate_rounds:
                md = rewrite_batch_from_pacing_gate(
                    premise_lock, outline_txt, b, prior_script, md, gate_rep, skill_dir=skill_dir
                )
                sp.write_text(md + "\n", encoding="utf-8")
                rep = SC.analyze_script(md, b)
                (out_dir / "episodes" / f"{tag}.check.json").write_text(
                    json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )

        combined_md_parts.append(md.strip())
        ledger = update_ledger_heuristic(ledger, b, md)
        ledger_p.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        batch_outputs.append({"batch": b, "path": str(sp), "check": rep, "pacing_gate": gate_rep})

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
