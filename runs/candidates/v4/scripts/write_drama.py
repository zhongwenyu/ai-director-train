#!/usr/bin/env python3
"""
End-to-end driver for `hit-short-drama v4`:
  Ultra-short / Simple Idea (1 sentence ~ 500 chars)
    -> Stage 0.5: Premise Common-Sense & Zero-Detour Dopamine Lock (`00_premise_lock.json`, audited by cross-family Critic)
    -> Stage 1: Full-Drama Story Engine & 40-120 Ep Master Outline (`01_outline.md`)
    -> Stage 2: Crisp Human-Speech Episode Scripts (`episodes/epXXX-YYY.md`, avg line <= 28 chars, single line <= 56 chars)
    -> Stage 3: Isolated Cross-Family Mobile Viewer Swipe-Away Hard Gate (`audience_agent.py`: `BINGE_NEXT` vs `SWIPE_AWAY`)
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
from typing import Any

SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR / "scripts"))
import script_check as SC  # noqa: E402
import audience_agent as AA  # noqa: E402

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

PREMISE_LOCK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "protagonist_identity_and_why_this_job": {
            "type": "string",
            "description": "主角的具体接地气出身与干这行的天然理由（严禁名校大学生无故当底层厨工/杂工！必须符合现实常识且自带付出痛感，60字内）",
        },
        "betrayal_core_wound": {
            "type": "string",
            "description": "第1集开局最扎心的一件事（主角曾为反派付出什么核心底牌/青春/金钱，反派如何忘恩负义当众羞辱切割，60字内）",
        },
        "same_root_ep2_crisis_by_main_villain": {
            "type": "string",
            "description": "第2集盟友/新阵地遭遇的危机如何直接由第1集核心反派打压/截胡造成（严禁手伤巧合或无关路人临时工勒索！60字内）",
        },
        "ally_instant_trust_anchor": {
            "type": "string",
            "description": "盟友/女主为何毫不猜忌、当场痛快信任主角并肩作战（严禁救场后冷脸审问主角是不是赌气！50字内）",
        },
        "ep1_to_3_uninterrupted_payoff_chain": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 3,
            "maxItems": 3,
            "description": "第1集、第2集、第3集咬死同一批核心反派的三连击爽点推进链（零支线路人注水）",
        },
    },
    "required": [
        "title",
        "protagonist_identity_and_why_this_job",
        "betrayal_core_wound",
        "same_root_ep2_crisis_by_main_villain",
        "ally_instant_trust_anchor",
        "ep1_to_3_uninterrupted_payoff_chain",
    ],
    "additionalProperties": False,
}

PREMISE_AUDIT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "ok": {"type": "boolean"},
        "issues": {
            "type": "array",
            "items": {"type": "string"},
            "description": "若存在身份违和（如985学生当厨工）、巧合假危机、路人支线或盟友猜忌内耗则列出具体问题；完全自洽爽快则填空数组 []",
        },
    },
    "required": ["ok", "issues"],
    "additionalProperties": False,
}


def strip_fence(text: str) -> str:
    s = text.strip()
    m = re.match(r"^```[a-zA-Z0-9_-]*\s*\n(.*)\n```\s*$", s, re.S)
    return m.group(1).strip() if m else s


def run_agy(
    prompt: str,
    *,
    schema: dict[str, Any] | None = None,
    timeout: int = 900,
    retries: int = 4,
    check_fn=None,
) -> str:
    last_err = ""
    for attempt in range(1, retries + 2):
        with tempfile.TemporaryDirectory(prefix="hit-drama-v4-") as cwd:
            cmd = [
                AGY_BIN,
                "--model", AGY_MODEL,
                "--effort", AGY_EFFORT,
                "--disable-slash-commands",
                "--output-format", "json",
                "--input-format", "text",
            ]
            if schema is not None:
                sp = Path(cwd) / "schema.json"
                sp.write_text(json.dumps(schema, ensure_ascii=False), encoding="utf-8")
                cmd += ["--json-schema", str(sp)]
            try:
                proc = subprocess.run(
                    cmd, cwd=cwd, input=prompt, capture_output=True, text=True, timeout=timeout
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
            text = json.dumps(raw, ensure_ascii=False) if isinstance(raw, dict) else str(raw or "")
        except ValueError:
            text = proc.stdout or ""
        text = strip_fence(text)
        if not text.strip():
            last_err = "empty response"
            time.sleep(2 * attempt)
            continue
        if check_fn and not check_fn(text):
            last_err = f"failed validation (len={len(text)}): {text[:240]!r}"
            time.sleep(2 * attempt)
            continue
        return text
    raise RuntimeError(f"agy failed: {last_err}")


def generate_premise_lock(
    idea_text: str,
    out_dir: Path,
    *,
    skill_dir: Path = SKILL_DIR,
    force: bool = False,
) -> dict[str, Any]:
    lock_path = out_dir / "00_premise_lock.json"
    if lock_path.is_file() and not force:
        return json.loads(lock_path.read_text(encoding="utf-8"))

    tmpl = (skill_dir / "prompts/stage0_premise_lock.md").read_text(encoding="utf-8")
    feedback = ""
    lock_obj: dict[str, Any] = {}
    for r in range(1, 4):
        prompt = tmpl + "\n\n# 用户输入的简短创意\n\n" + idea_text.strip()
        if feedback:
            prompt += f"\n\n# 上一轮立项常识与爽点审查驳回意见（必须彻底修正！）\n\n{feedback}"
        raw = run_agy(prompt, schema=PREMISE_LOCK_SCHEMA, timeout=300)
        lock_obj = AA._extract_json(raw)

        audit_prompt = (
            "你是一位极其挑剔的短剧总编兼普通观众代表。请严格审查以下《短剧立项锁》是否踩中任何一条红线：\n"
            "1. 主角社会身份/学历与所干手艺活违背现实常识（如985重点大学在校生无故去街边颠勺当厨工/学徒）；\n"
            "2. 第2集危机靠扭伤手腕、临时工勒索等假巧合硬凑，而不是直接源于第1集核心反派的打压截胡；\n"
            "3. 前3集混入一次性路人反派分散主线仇恨；\n"
            "4. 盟友/女主在主角救场后搞猜忌审讯内耗。\n"
            "若全部自洽且爽感一气呵成，返回 ok=true, issues=[]；否则返回 ok=false 并指出具体槽点。\n\n"
            + json.dumps(lock_obj, ensure_ascii=False, indent=2)
        )
        audit = AA.call_isolated_llm(audit_prompt, PREMISE_AUDIT_SCHEMA, backend="codex")
        if audit["ok"] and not audit["issues"]:
            print(f"[stage0.5] Premise Lock PASSED on round {r}: {lock_obj['title']}", flush=True)
            break
        feedback = "\n".join(audit["issues"])
        print(f"[stage0.5] Premise Lock rejected on round {r}: {feedback}", flush=True)

    out_dir.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps(lock_obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return lock_obj


def pick_genre_examples(skill_dir: Path, text_hint: str) -> str:
    ex_dir = skill_dir / "examples"
    if not ex_dir.is_dir():
        return ""
    if any(k in text_hint for k in ("七零", "八零", "九零", "1958", "1977", "1983", "93", "供销社", "赶海", "赶山", "村", "知青")):
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
    return p.read_text(encoding="utf-8")[:8500]


def generate_outline(
    idea_text: str,
    premise_lock: dict[str, Any],
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
        "# 已锁死的《Stage 0.5 常识动机与前三集连环爽点立项锁》（必须 100% 严格遵守，严禁篡改人设出身、严禁加路人支线或盟友猜忌！）\n\n"
        + json.dumps(premise_lock, ensure_ascii=False, indent=2),
        "# 用户输入的原始创意\n\n" + idea_text.strip(),
    ])

    text = run_agy(
        prompt,
        timeout=600,
        check_fn=lambda t: (
            len(t) >= 1000
            and bool(re.search(r"第\s*0*1\s*集", t))
            and bool(re.search(rf"第\s*0*{min(5, plan_up_to_ep)}\s*集", t))
        ),
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    outline_path.write_text(text + "\n", encoding="utf-8")
    return outline_path


def update_ledger_heuristic(
    prev_ledger: dict[str, Any], batch_eps: list[int], script_md: str
) -> dict[str, Any]:
    blocks = list(SC.RE_EP_HEADER.finditer(script_md))
    last_ep_tail = ""
    if blocks:
        last_body = script_md[blocks[-1].start():].strip()
        lines = [ln for ln in last_body.splitlines() if ln.strip()]
        last_ep_tail = "\n".join(lines[-14:])
    completed = sorted(set(prev_ledger.get("completed_episodes", []) + batch_eps))
    return {
        "completed_episodes": completed,
        "last_episode": batch_eps[-1],
        "last_episode_tail": last_ep_tail,
    }


def generate_episode_batch(
    idea_text: str,
    premise_lock: dict[str, Any],
    outline_text: str,
    batch_eps: list[int],
    out_dir: Path,
    *,
    skill_dir: Path = SKILL_DIR,
    prev_tail: str = "",
    prior_script: str = "",
    force: bool = False,
) -> tuple[Path, dict[str, Any]]:
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
    playbooks = (skill_dir / "references/playbooks.md").read_text(encoding="utf-8")
    example_md = pick_genre_examples(skill_dir, idea_text + "\n" + outline_text[:1000])

    batch_str = (
        f"第 {batch_eps[0]} 集"
        if len(batch_eps) == 1
        else f"第 {batch_eps[0]}～{batch_eps[-1]} 集（共 {len(batch_eps)} 集）"
    )
    parts = [
        tmpl.format(batch_range=batch_str),
        "# 核心工艺法则\n\n" + craft,
        "# 严禁出现的 AI 病灶对照表\n\n" + anti,
        "# 赛道专属打法\n\n" + playbooks,
    ]
    if example_md:
        parts.append(
            "# 同赛道真实爆款剧本质感参考（仅学习其短促如刀的活人台词与爽点切点，严禁抄袭人名剧情！）\n\n"
            + example_md
        )
    parts.append(
        "# 已锁死的《Stage 0.5 立项锁》（身份动机、同源危机、零支线路人、盟友痛快信任不可违背！）\n\n"
        + json.dumps(premise_lock, ensure_ascii=False, indent=2)
    )
    parts.append("# 本剧《全剧故事引擎与分集大纲》\n\n" + outline_text.strip())
    if prior_script.strip():
        parts.append("# 前序已定稿剧集正文\n\n" + prior_script.strip()[-12000:])
    elif prev_tail.strip():
        parts.append("# 上一批最后一集结尾实况\n\n" + prev_tail.strip())

    parts.append(
        f"# 本次写作任务硬性指令\n\n"
        f"请严格写出 **{batch_str}** 的完整分集剧本正文（集号依次为 {batch_eps}），每集以 `【本集完】` 结束。\n"
        f"- **活人短句硬红线**：每集句均字数必须 **<= 26 字**，任何单句台词或 VO 严禁超过 **52 字**！严禁口播三四个财务数字或复述背景履历！\n"
        f"- **节奏硬红线**：单集预估时长控制在 **85～150 秒**（每集台词总字数 280～480 字），刀刀见血、秒入主线！"
    )

    def valid_batch(txt: str) -> bool:
        rep = SC.analyze_script(txt, batch_eps)
        if not rep["ok"]:
            print(f"  [script_check reject] {rep['hard_errors']}", flush=True)
        return rep["ok"]

    script_md = run_agy("\n\n".join(parts), timeout=900, retries=3, check_fn=valid_batch)
    script_path.write_text(script_md + "\n", encoding="utf-8")
    rep = SC.analyze_script(script_md, batch_eps)
    stats_path.write_text(json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return script_path, rep


def rewrite_batch_from_audience_gate(
    premise_lock: dict[str, Any],
    outline_text: str,
    batch_eps: list[int],
    prior_script: str,
    current_batch_md: str,
    audience_report: dict[str, Any],
    *,
    skill_dir: Path = SKILL_DIR,
) -> str:
    craft = (skill_dir / "references/episode-craft.md").read_text(encoding="utf-8")
    anti = (skill_dir / "references/anti-patterns.md").read_text(encoding="utf-8")
    batch_str = f"第 {batch_eps[0]}～{batch_eps[-1]} 集"
    prompt = "\n\n".join([
        f"# Stage 4：根据「零上下文手机小白观众」划走弃剧报告（`SWIPE_AWAY`）彻底重构 {batch_str}\n\n"
        "一名完全没看过大纲的真实手机短剧观众在刷到本批剧本时点击了 **划走弃剧（`SWIPE_AWAY`）**！\n"
        "**重构铁律**：\n"
        "1. **从源头换掉出戏/拖沓桥段，绝不靠加解释台词打补丁**！\n"
        "2. 砍掉所有财务算账报数与背景复述长句，确保每集**句均字数 <= 26 字、单句 <= 52 字、单集预估时长 85～150 秒**！\n"
        "3. 严格遵守《Stage 0.5 立项锁》的身份常识自洽、同源反派危机与盟友痛快信任，让观众一秒代入、爽感不断档！\n"
        f"4. 直接输出集号依次为 {batch_eps}、每集以 `【本集完】` 结尾的标准剧本 Markdown 正文，不要任何解释。",
        "# 《Stage 0.5 立项锁》\n\n" + json.dumps(premise_lock, ensure_ascii=False, indent=2),
        "# 核心工艺与病灶红线\n\n" + craft + "\n\n" + anti,
        "# 大纲参考（观众不可见，一切因果必须在画面与短促交锋里自然成立）\n\n" + outline_text.strip(),
        "# 前序已定稿剧集正文\n\n" + (prior_script.strip()[-12000:] if prior_script.strip() else "（无前序剧集）"),
        "# 被观众划走弃剧的本批原稿\n\n" + current_batch_md.strip(),
        "# 观众即时弹幕与弃剧原因报告（必须逐条根治！）\n\n" + json.dumps(audience_report, ensure_ascii=False, indent=2),
    ])

    def valid_batch(txt: str) -> bool:
        rep = SC.analyze_script(txt, batch_eps)
        if not rep["ok"]:
            print(f"  [rewrite script_check reject] {rep['hard_errors']}", flush=True)
        return rep["ok"]

    return run_agy(prompt, timeout=900, retries=3, check_fn=valid_batch)


def parse_ep_range(spec: str) -> list[int]:
    eps: list[int] = []
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
) -> dict[str, Any]:
    target_eps = parse_ep_range(episodes_spec)
    max_ep = max(target_eps) if target_eps else 3
    plan_up_to = max(15, max_ep)

    premise_lock = generate_premise_lock(idea_text, out_dir, skill_dir=skill_dir, force=force)
    outline_p = generate_outline(
        idea_text, premise_lock, out_dir, skill_dir=skill_dir, plan_up_to_ep=plan_up_to, force=force
    )
    outline_txt = outline_p.read_text(encoding="utf-8")

    ledger_p = out_dir / "state_ledger.json"
    ledger: dict[str, Any] = (
        json.loads(ledger_p.read_text(encoding="utf-8"))
        if ledger_p.is_file() and not force
        else {"completed_episodes": [], "last_episode": 0, "last_episode_tail": ""}
    )

    batches: list[list[int]] = []
    cur: list[int] = []
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
    max_aud_rounds = int(os.environ.get("HIT_DRAMA_AUDIENCE_ROUNDS", "3"))
    aud_backend = os.environ.get("AUDIENCE_BACKEND", "codex")

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
        aud_rep: dict[str, Any] = {}
        for r_idx in range(1, max_aud_rounds + 1):
            visible_so_far = (prior_script + "\n\n" + md.strip()).strip()
            print(f"[audience-gate] Auditing batch {b} (round {r_idx}/{max_aud_rounds}, backend={aud_backend})...", flush=True)
            aud_rep = AA.audit_viewer_retention(visible_so_far, eval_eps=b, backend=aud_backend)
            aud_path = out_dir / "episodes" / f"{tag}.audience_r{r_idx}.json"
            aud_path.write_text(json.dumps(aud_rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            if aud_rep["ok"]:
                print(f"[audience-gate] BINGE_NEXT PASS on batch {b} (round {r_idx})!", flush=True)
                break
            print(
                f"[audience-gate] SWIPE_AWAY on episodes {aud_rep['blocked_episodes']} (round {r_idx}) -> rewriting batch {b}...",
                flush=True,
            )
            if r_idx < max_aud_rounds:
                md = rewrite_batch_from_audience_gate(
                    premise_lock, outline_txt, b, prior_script, md, aud_rep, skill_dir=skill_dir
                )
                sp.write_text(md + "\n", encoding="utf-8")
                rep = SC.analyze_script(md, b)
                (out_dir / "episodes" / f"{tag}.check.json").write_text(
                    json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )

        combined_md_parts.append(md.strip())
        ledger = update_ledger_heuristic(ledger, b, md)
        ledger_p.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        batch_outputs.append({"batch": b, "path": str(sp), "check": rep, "audience_audit": aud_rep})

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
