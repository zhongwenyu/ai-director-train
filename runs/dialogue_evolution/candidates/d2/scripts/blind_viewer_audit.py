#!/usr/bin/env python3
"""
Physically isolated Sequential Blind-Viewer Audit (`blind_viewer_audit.py`).

Key invariant:
- NEVER reads `00_creative_brief.md`, `01_outline.md`, `state_ledger.json`, or character bibles.
- Spawns a clean isolated `agy` session in an empty temp directory for each episode `k = start_ep .. end_ep`,
  passing ONLY the raw screenplay text of Episodes `1 .. k` (what is actually filmed and seen by the audience).
- Enforces hard gate: any `unexplained_leaps`, `timeline_glitches`, `cringe_or_ad_moments`, or `forced_hooks`
  automatically forces `verdict = "BLOCK"`.
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

AGY_BIN = (
    os.environ.get("TRAIN_AGY_BIN")
    or ("/home/zhongwenyu/.config/paseo/antigravity-bin/agy"
        if Path("/home/zhongwenyu/.config/paseo/antigravity-bin/agy").is_file()
        else None)
    or shutil.which("agy")
    or "agy"
)
# Use stronger reasoning model by default for critical blind-viewer comprehension gate
BLIND_MODEL = os.environ.get("HIT_DRAMA_BLIND_MODEL", "gemini-4-carbon-medium")
BLIND_EFFORT = os.environ.get("HIT_DRAMA_BLIND_EFFORT", "medium")


def split_episodes_map(script_md: str) -> dict[int, str]:
    headers = list(SC.RE_EP_HEADER.finditer(script_md))
    ep_map: dict[int, str] = {}
    for i, m in enumerate(headers):
        ep_no = int(m.group(1))
        start = m.start()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(script_md)
        ep_map[ep_no] = script_md[start:end].strip()
    return ep_map


def extract_json_obj(raw: str) -> dict[str, Any]:
    s = raw.strip()
    m = re.match(r"^```[a-zA-Z0-9_-]*\s*\n(.*)\n```\s*$", s, re.S)
    if m:
        s = m.group(1).strip()
    j_start = s.find("{")
    j_end = s.rfind("}")
    if j_start >= 0 and j_end > j_start:
        s = s[j_start:j_end + 1]
    obj = json.loads(s)
    # Enforce programmatic hard gate so LLM cannot say PASS while listing defects
    defect_count = sum(
        len(obj.get(k) or [])
        for k in ("unexplained_leaps", "timeline_glitches", "cringe_or_ad_moments", "forced_hooks")
    )
    score = float(obj.get("viewer_hook_score") or 0.0)
    if defect_count > 0 or score < 8.5:
        obj["verdict"] = "BLOCK"
    else:
        obj["verdict"] = "PASS"
    obj["defect_count"] = defect_count
    return obj


def audit_single_episode_blind(visible_eps_md: str, current_ep: int, timeout: int = 360) -> dict[str, Any]:
    tmpl = (SKILL_DIR / "prompts" / "stage3_blind_viewer.md").read_text(encoding="utf-8")
    prompt = tmpl.format(current_ep=current_ep, visible_episodes_text=visible_eps_md.strip())

    last_err = ""
    for attempt in range(1, 4):
        # Empty temporary directory guarantees ZERO file leakage from outline/ledger!
        with tempfile.TemporaryDirectory(prefix=f"blind-viewer-ep{current_ep:03d}-") as empty_cwd:
            cmd = [
                AGY_BIN,
                "--model", BLIND_MODEL,
                "--effort", BLIND_EFFORT,
                "--disable-slash-commands",
                "--output-format", "json",
                "--input-format", "text",
            ]
            try:
                proc = subprocess.run(
                    cmd, cwd=empty_cwd, input=prompt, capture_output=True, text=True, timeout=timeout
                )
            except subprocess.TimeoutExpired:
                last_err = f"timeout {timeout}s (attempt {attempt})"
                time.sleep(2 * attempt)
                continue
        if proc.returncode != 0:
            last_err = f"exit {proc.returncode}: {(proc.stderr or proc.stdout)[-400:]}"
            time.sleep(2 * attempt)
            continue
        try:
            env = json.loads(proc.stdout)
            resp_txt = (env or {}).get("response") or proc.stdout
            return extract_json_obj(resp_txt)
        except Exception as exc:
            last_err = f"JSON parse error: {exc}"
            time.sleep(2 * attempt)
    raise RuntimeError(f"Blind viewer audit failed on Ep {current_ep}: {last_err}")


def audit_sequential(script_md: str, eval_eps: list[int] | None = None) -> dict[str, Any]:
    ep_map = split_episodes_map(script_md)
    if not ep_map:
        raise ValueError("No episodes found in script markdown")
    all_sorted = sorted(ep_map.keys())
    targets = sorted(eval_eps) if eval_eps else all_sorted

    reports = []
    blocked_eps = []
    for ep_no in targets:
        visible_nums = [n for n in all_sorted if n <= ep_no]
        visible_md = "\n\n".join(ep_map[n] for n in visible_nums)
        rep = audit_single_episode_blind(visible_md, ep_no)
        reports.append(rep)
        if rep["verdict"] != "PASS":
            blocked_eps.append(ep_no)

    return {
        "ok": len(blocked_eps) == 0,
        "verdict": "PASS" if len(blocked_eps) == 0 else "BLOCK",
        "blocked_episodes": blocked_eps,
        "episodes": reports,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("script_md", type=Path, help="Combined or batch episode markdown (ONLY screenplay text)")
    ap.add_argument("--episodes", default="", help="Optional episode subset to audit, e.g. 1-3")
    ap.add_argument("--out", type=Path, default=None, help="Optional JSON report output path")
    args = ap.parse_args()

    eval_eps: list[int] | None = None
    if args.episodes.strip():
        eval_eps = []
        for p in args.episodes.split(","):
            p = p.strip()
            if "-" in p:
                a, b = p.split("-", 1)
                eval_eps.extend(range(int(a), int(b) + 1))
            elif p:
                eval_eps.append(int(p))

    res = audit_sequential(args.script_md.read_text(encoding="utf-8"), eval_eps)
    out_str = json.dumps(res, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(out_str + "\n", encoding="utf-8")
    print(out_str)
    if not res["ok"]:
        sys.exit(2)


if __name__ == "__main__":
    main()
