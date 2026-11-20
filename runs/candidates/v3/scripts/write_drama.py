#!/usr/bin/env python3
"""End-to-end driver for the `hit-short-drama` skill using agy (gemini-4-carbon-low).

Pipeline:
  Simple Idea (200-500 chars)
    -> Stage 1: Full-Drama Story Engine & 40-120 Ep Master Outline (`01_outline.md`)
    -> Stage 2: Rolling-Window Episode Scripts (`episodes/epXXX-YYY.md`) + `state_ledger.json`
    -> Stage 3: Physical timing & clean delivery check (`script_check.py`)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

SKILL_DIR = Path(__file__).resolve().parent.parent
import sys

sys.path.insert(0, str(SKILL_DIR / "scripts"))
import script_check as SC  # noqa: E402

AGY_BIN = (
    os.environ.get("TRAIN_AGY_BIN")
    or ("/home/zhongwenyu/.config/paseo/antigravity-bin/agy"
        if Path("/home/zhongwenyu/.config/paseo/antigravity-bin/agy").is_file()
        else None)
    or shutil.which("agy")
    or "agy"
)
AGY_MODEL = os.environ.get("HIT_DRAMA_AGY_MODEL", "gemini-4-carbon-low")
AGY_EFFORT = os.environ.get("HIT_DRAMA_AGY_EFFORT", "low")


def strip_fence(text: str) -> str:
    s = text.strip()
    m = re.match(r"^```[a-zA-Z0-9_-]*\s*\n(.*)\n```\s*$", s, re.S)
    return m.group(1).strip() if m else s


def run_agy(prompt: str, timeout: int = 900, retries: int = 4, check_fn=None) -> str:
    last_err = ""
    for attempt in range(1, retries + 2):
        with tempfile.TemporaryDirectory(prefix="hit-drama-agy-") as cwd:
            cmd = [
                AGY_BIN,
                "--model", AGY_MODEL,
                "--effort", AGY_EFFORT,
                "--disable-slash-commands",
                "--output-format", "json",
                "--input-format", "text",
            ]
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
            text = (env or {}).get("response") or ""
        except ValueError:
            text = proc.stdout or ""
        text = strip_fence(text)
        if not text.strip():
            last_err = "empty response"
            time.sleep(2 * attempt)
            continue
        if check_fn and not check_fn(text):
            last_err = f"failed validation (len={len(text)})"
            time.sleep(2 * attempt)
            continue
        return text
    raise RuntimeError(f"agy failed: {last_err}")


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
    return p.read_text(encoding="utf-8")[:9500]


def generate_outline(
    idea_text: str,
    out_dir: Path,
    *,
    skill_dir: Path = SKILL_DIR,
    plan_up_to_ep: int = 15,
    force: bool = False,
) -> Path:
    outline_path = out_dir / "01_outline.md"
    if outline_path.is_file() and not force:
        return outline_path

    tmpl = (skill_dir / "prompts" / "stage1_outline.md").read_text(encoding="utf-8")
    story_engine = (skill_dir / "references" / "story-engine.md").read_text(encoding="utf-8")
    playbooks = (skill_dir / "references" / "playbooks.md").read_text(encoding="utf-8")

    ep_range_str = f"第 1～{plan_up_to_ep} 集"
    prompt = "\n\n".join(
        [
            tmpl.format(episode_plan_range=ep_range_str),
            "# 参考资料 1：全剧故事引擎法则\n\n" + story_engine,
            "# 参考资料 2：赛道专属打法\n\n" + playbooks,
            "# 用户输入的简单创意\n\n" + idea_text.strip(),
        ]
    )

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
    """Maintain lightweight rolling context + exact tail of last episode for seamless hook handoff."""
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

    tmpl = (skill_dir / "prompts" / "stage2_episodes.md").read_text(encoding="utf-8")
    craft = (skill_dir / "references" / "episode-craft.md").read_text(encoding="utf-8")
    anti = (skill_dir / "references" / "anti-patterns.md").read_text(encoding="utf-8")
    playbooks = (skill_dir / "references" / "playbooks.md").read_text(encoding="utf-8")
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
            "# 同赛道真实爆款剧本质感参考（仅学习其对白呼吸感、信息差推进与断章切点，严禁抄袭其人名或剧情！）\n\n"
            + example_md
        )
    parts.append("# 本剧原始创意\n\n" + idea_text.strip())
    parts.append("# 本剧《全剧故事引擎与分集大纲》\n\n" + outline_text.strip())
    if prior_script.strip():
        parts.append(
            "# 前序已定稿剧集正文（本批涉及的公司行业、道具去向、金额数字、人物知情状态必须与前序剧集 100% 严丝合缝，严禁前后吃书或重复演同一幕！）\n\n"
            + prior_script.strip()[-12000:]
        )
    elif prev_tail.strip():
        parts.append(
            "# 上一批最后一集结尾实况（本批首集开场前5秒必须无缝接住这一幕！）\n\n" + prev_tail.strip()
        )
    parts.append(
        f"# 本次写作任务指令\n\n"
        f"请严格写出 **{batch_str}** 的完整分集剧本正文（集号必须依次为 {batch_eps}），每集以 `【本集完】` 结束。\n"
        f"- **节奏与时长硬约束**：单集时长自然落在 **1～3 分钟**（均值约 2 分钟，建议单集台词总字数控制在 260～650 字之间，切忌把商战/律政写成冗长开会汇报！）。\n"
        f"- **连续性铁律**：若已有前序剧集，本批首集前5秒无缝承接上一集结尾钩子，且所有实物道具、金额、设定细节绝对一致。"
    )

    full_prompt = "\n\n".join(parts)

    def valid_batch(txt: str) -> bool:
        rep = SC.analyze_script(txt, batch_eps)
        return rep["ok"]

    script_md = run_agy(full_prompt, timeout=900, retries=2, check_fn=valid_batch)
    script_path.write_text(script_md + "\n", encoding="utf-8")
    rep = SC.analyze_script(script_md, batch_eps)
    stats_path.write_text(json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return script_path, rep


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
    episodes_spec: str = "1-5",
    *,
    batch_size: int = 3,
    skill_dir: Path = SKILL_DIR,
    force: bool = False,
) -> dict[str, Any]:
    target_eps = parse_ep_range(episodes_spec)
    max_ep = max(target_eps) if target_eps else 5
    plan_up_to = max(15, max_ep)

    outline_p = generate_outline(
        idea_text, out_dir, skill_dir=skill_dir, plan_up_to_ep=plan_up_to, force=force
    )
    outline_txt = outline_p.read_text(encoding="utf-8")

    ledger_p = out_dir / "state_ledger.json"
    ledger: dict[str, Any] = (
        json.loads(ledger_p.read_text(encoding="utf-8"))
        if ledger_p.is_file() and not force
        else {"completed_episodes": [], "last_episode": 0, "last_episode_tail": ""}
    )

    # Group contiguous episodes into batches of `batch_size`
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
    for b in batches:
        prev_tail = ledger.get("last_episode_tail", "") if b[0] == ledger.get("last_episode", 0) + 1 else ""
        prior_script = "\n\n".join(combined_md_parts)
        sp, rep = generate_episode_batch(
            idea_text,
            outline_txt,
            b,
            out_dir,
            skill_dir=skill_dir,
            prev_tail=prev_tail,
            prior_script=prior_script,
            force=force,
        )
        md = sp.read_text(encoding="utf-8")
        combined_md_parts.append(md.strip())
        ledger = update_ledger_heuristic(ledger, b, md)
        ledger_p.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        batch_outputs.append({"batch": b, "path": str(sp), "check": rep})

    combined_path = out_dir / f"combined_{episodes_spec.replace(',', '_')}.md"
    combined_path.write_text("\n\n".join(combined_md_parts) + "\n", encoding="utf-8")
    return {
        "outline_path": str(outline_p),
        "combined_script_path": str(combined_path),
        "batches": batch_outputs,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate AI short drama outline & scripts from a simple idea")
    ap.add_argument("--idea", help="Inline simple idea text")
    ap.add_argument("--idea-file", help="Path to file containing simple idea (200-500 chars)")
    ap.add_argument("--out-dir", required=True, help="Output directory")
    ap.add_argument("--episodes", default="1-5", help="Episode range to write, e.g. 1-5 or 1-3,11-12")
    ap.add_argument("--batch-size", type=int, default=3, help="Episodes per generation call (default 3)")
    ap.add_argument("--force", action="store_true", help="Regenerate even if files exist")
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
