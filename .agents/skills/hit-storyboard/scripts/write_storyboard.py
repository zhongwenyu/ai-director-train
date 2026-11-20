#!/usr/bin/env python3
"""Parallel Episode Storyboard Driver for `hit-storyboard` using agy (gemini-4-carbon-low).

Splits an input multi-episode or single-episode screenplay into per-episode tasks,
generates 14-column director storyboards concurrently via ThreadPoolExecutor,
verifies physical & group-duration invariants via `storyboard_check.py` (with auto-repair retry if needed),
and merges into a clean multi-episode storyboard file.
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
from typing import Any

SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR / "scripts"))
import storyboard_check as SBC  # noqa: E402

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
AGY_MODEL = os.environ.get("HIT_SB_AGY_MODEL", "gemini-4-carbon-medium")
AGY_EFFORT = os.environ.get("HIT_SB_AGY_EFFORT", "medium")


def strip_fence(text: str) -> str:
    s = text.strip()
    m = re.match(r"^```[a-zA-Z0-9_-]*\s*\n(.*)\n```\s*$", s, re.S)
    return m.group(1).strip() if m else s


MARKDOWN_DOC_SCHEMA = {
    "type": "object",
    "properties": {
        "markdown": {
            "type": "string",
            "description": "完整的导演分镜表 Markdown 正文（严禁调用任何读写文件或终端工具，直接在此字段一次性返回完整 Markdown）",
        }
    },
    "required": ["markdown"],
    "additionalProperties": False,
}


def run_agy_once(prompt: str, timeout: int = 600) -> str:
    eff_prompt = prompt + "\n\n【系统执行约束：严禁调用任何读写文件或终端工具！直接将完整的导演分镜表 Markdown 正文填入 JSON 的 `markdown` 字段一次性返回。】"
    with tempfile.TemporaryDirectory(prefix="hit-sb-agy-") as cwd:
        sp = Path(cwd) / "schema.json"
        sp.write_text(json.dumps(MARKDOWN_DOC_SCHEMA, ensure_ascii=False), encoding="utf-8")
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
        proc = subprocess.run(
            cmd, cwd=cwd, input=eff_prompt, capture_output=True, text=True, timeout=timeout
        )
    if proc.returncode != 0:
        raise RuntimeError(f"agy exit {proc.returncode}: {(proc.stderr or proc.stdout)[-500:]}")
    env = json.loads(proc.stdout)
    raw = (env or {}).get("response") if isinstance(env, dict) else proc.stdout
    if isinstance(raw, dict):
        txt = str(raw.get("markdown") or "")
    else:
        parsed = json.loads(str(raw or "{}"))
        txt = str(parsed.get("markdown") or "")
    txt = strip_fence(txt)
    if not txt.strip():
        raise RuntimeError("agy returned empty response")
    return txt


def split_screenplay_by_episode(screenplay_md: str) -> dict[int, str]:
    matches = list(SBC.EP_RE.finditer(screenplay_md))
    out: dict[int, str] = {}
    for i, m in enumerate(matches):
        ep_no = int(m.group(1))
        end = matches[i + 1].start() if i + 1 < len(matches) else len(screenplay_md)
        out[ep_no] = screenplay_md[m.start():end].strip()
    return out


def pick_storyboard_example(skill_dir: Path) -> str:
    ex_dir = skill_dir / "examples"
    if not ex_dir.is_dir():
        return ""
    files = sorted(ex_dir.glob("*.md"))
    if not files:
        return ""
    return files[0].read_text(encoding="utf-8")[:9000]


def generate_one_episode_storyboard(
    ep_no: int,
    ep_script: str,
    out_dir: Path,
    *,
    skill_dir: Path = SKILL_DIR,
    aspect_ratio: str = "9:16 竖屏",
    assets_doc: str = "",
    prev_ep_tail: str = "",
    force: bool = False,
) -> tuple[Path, dict[str, Any]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    sb_path = out_dir / f"ep{ep_no:03d}_storyboard.md"
    chk_path = out_dir / f"ep{ep_no:03d}_storyboard.check.json"

    if sb_path.is_file() and not force:
        rep = SBC.analyze_storyboard(
            sb_path.read_text(encoding="utf-8"),
            screenplay_md=ep_script,
            expected_eps=[ep_no],
        )
        if rep["ok"]:
            return sb_path, rep

    tmpl = (skill_dir / "prompts" / "generate_storyboard.md").read_text(encoding="utf-8")
    cam_ref = (skill_dir / "references" / "camera-choreography.md").read_text(encoding="utf-8")
    grp_ref = (skill_dir / "references" / "grouping-and-continuity.md").read_text(encoding="utf-8")
    anti_ref = (skill_dir / "references" / "storyboard-anti-patterns.md").read_text(encoding="utf-8")
    ex_md = pick_storyboard_example(skill_dir)

    parts = [
        tmpl.format(episode_range=f"第 {ep_no} 集", aspect_ratio=aspect_ratio),
        "# 参考 1：运镜调度核心法则\n\n" + cam_ref,
        "# 参考 2：生成组、180°轴线与跨组接缝规程\n\n" + grp_ref,
        "# 参考 3：严禁出现的分镜病灶对照\n\n" + anti_ref,
    ]
    if ex_md:
        parts.append(
            "# 参考 4：真实红果爆款实拍分镜格式与运镜质感示范（仅学习其14列结构、承重拍运镜四要素与组末接续锚点，严禁抄袭其剧情人名！）\n\n"
            + ex_md
        )
    if assets_doc.strip():
        parts.append("# 本项目统一角色／场景／道具资产编码表（资产绑定列严格引用此表编码！）\n\n" + assets_doc.strip()[:8000])
    if prev_ep_tail.strip():
        parts.append("# 上一集末尾状态参考（确保跨集开场服装、伤妆、持物与空间状态连续）\n\n" + prev_ep_tail.strip()[-1500:])
    parts.append(f"# 待拆解定稿剧本（第 {ep_no} 集）\n\n" + ep_script.strip())

    base_prompt = "\n\n".join(parts)
    last_txt = ""
    last_rep: dict[str, Any] = {}

    for attempt in range(1, 5):
        prompt = base_prompt
        if attempt > 1 and last_txt:
            err_msg = "；".join(last_rep.get("hard_errors", []) + last_rep.get("warnings", [])[:3])
            prompt = (
                base_prompt
                + f"\n\n# 【自动返修指令 - 第 {attempt} 次尝试】\n"
                + f"你上一次生成的分镜表未通过物理校验，存在以下问题：**{err_msg}**。\n"
                + "请基于下方草稿完整修正所有组时长加总、14列格式、漏拆台词或运镜问题，直接输出修正后的完整第 "
                + f"{ep_no} 集 Markdown 分镜表（标题必须为 `# 第 {ep_no} 集 ...`）：\n\n"
                + last_txt[:22000]
            )
        try:
            txt = run_agy_once(prompt, timeout=900)
        except Exception as exc:
            time.sleep(2 * attempt)
            last_rep = {"ok": False, "hard_errors": [str(exc)], "warnings": []}
            continue

        rep = SBC.analyze_storyboard(txt, screenplay_md=ep_script, expected_eps=[ep_no])
        last_txt, last_rep = txt, rep
        if rep["ok"]:
            sb_path.write_text(txt + "\n", encoding="utf-8")
            chk_path.write_text(json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return sb_path, rep
        time.sleep(1.5 * attempt)

    # Save best-effort even if minor hard error remained on final attempt, or raise if empty
    if not last_txt:
        raise RuntimeError(f"Episode {ep_no} storyboard generation failed: {last_rep}")
    sb_path.write_text(last_txt + "\n", encoding="utf-8")
    chk_path.write_text(json.dumps(last_rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return sb_path, last_rep


def parse_ep_spec(spec: str, available: list[int]) -> list[int]:
    if not spec or spec.strip().lower() == "all":
        return sorted(available)
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
    return [e for e in sorted(set(eps)) if e in available]


def run_storyboard_pipeline(
    screenplay_path: Path,
    out_dir: Path,
    *,
    episodes_spec: str = "all",
    aspect_ratio: str = "9:16 竖屏",
    assets_path: Path | None = None,
    skill_dir: Path = SKILL_DIR,
    workers: int = 4,
    force: bool = False,
) -> dict[str, Any]:
    sp_md = screenplay_path.read_text(encoding="utf-8")
    ep_map = split_screenplay_by_episode(sp_md)
    target_eps = parse_ep_spec(episodes_spec, list(ep_map.keys()))
    if not target_eps:
        raise ValueError(f"No matching episodes for spec={episodes_spec!r} in {screenplay_path}")

    assets_doc = assets_path.read_text(encoding="utf-8") if assets_path and assets_path.is_file() else ""
    ep_out_dir = out_dir / "episodes"
    ep_out_dir.mkdir(parents=True, exist_ok=True)

    results: dict[int, tuple[Path, dict[str, Any]]] = {}
    with cf.ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futs = {}
        for ep in target_eps:
            prev_tail = ep_map.get(ep - 1, "")[-1000:] if (ep - 1) in ep_map else ""
            futs[
                pool.submit(
                    generate_one_episode_storyboard,
                    ep,
                    ep_map[ep],
                    ep_out_dir,
                    skill_dir=skill_dir,
                    aspect_ratio=aspect_ratio,
                    assets_doc=assets_doc,
                    prev_ep_tail=prev_tail,
                    force=force,
                )
            ] = ep
        for f in cf.as_completed(futs):
            ep = futs[f]
            results[ep] = f.result()

    merged_parts = []
    checks = []
    for ep in target_eps:
        p, rep = results[ep]
        merged_parts.append(p.read_text(encoding="utf-8").strip())
        checks.append(rep)

    tag = f"{target_eps[0]}-{target_eps[-1]}" if len(target_eps) > 1 else f"{target_eps[0]}"
    combined_path = out_dir / f"combined_storyboard_{tag}.md"
    combined_path.write_text("\n\n---\n\n".join(merged_parts) + "\n", encoding="utf-8")
    return {
        "combined_storyboard_path": str(combined_path),
        "episodes": target_eps,
        "all_ok": all(c["ok"] for c in checks),
        "checks": checks,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Parallel AI short drama storyboard generator")
    ap.add_argument("--screenplay", required=True, help="Input screenplay markdown path")
    ap.add_argument("--out-dir", required=True, help="Output directory")
    ap.add_argument("--episodes", default="all", help="Episode range, e.g. 1-5 or all")
    ap.add_argument("--aspect-ratio", default="9:16 竖屏", help="9:16 竖屏 or 16:9 横屏")
    ap.add_argument("--assets", help="Optional assets markdown path")
    ap.add_argument("--workers", type=int, default=4, help="Parallel episode workers")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    res = run_storyboard_pipeline(
        Path(args.screenplay),
        Path(args.out_dir),
        episodes_spec=args.episodes,
        aspect_ratio=args.aspect_ratio,
        assets_path=Path(args.assets) if args.assets else None,
        workers=args.workers,
        force=args.force,
    )
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
