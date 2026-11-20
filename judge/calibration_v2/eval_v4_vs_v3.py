#!/usr/bin/env python3
"""
Blind Swap-Debiased Arena Evaluation: `hit-short-drama v4` vs `v3` on 4 diverse
50-65 char ultra-short seeds from the benchmark (`P01`, `P02`, `P04`, `P08`)!
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import sys
from pathlib import Path

TRAIN_ROOT = Path("/home/zhongwenyu/project/ai-director-train")
sys.path.insert(0, str(TRAIN_ROOT / "runs/candidates/v4/scripts"))

import audience_agent as AA  # noqa: E402
import write_drama as WD_V4  # noqa: E402

BENCH_DIR = TRAIN_ROOT / "judge/calibration_v2/benchmark"
ARENA_DIR = TRAIN_ROOT / "judge/calibration_v2/v4_vs_v3_arena"
V4_SKILL_DIR = TRAIN_ROOT / "runs/candidates/v4"


def eval_seed(pair_item: dict) -> dict:
    pid = pair_item["pair_id"]
    idea = pair_item["idea"]
    v3_script = Path(pair_item["neg_path"]).read_text(encoding="utf-8")

    v4_out = ARENA_DIR / pid / "v4_gen"
    v4_comb = v4_out / "combined_1-3.md"
    if not v4_comb.is_file():
        print(f"[arena] Running v4 on {pid} ({len(idea)}-char seed)...", flush=True)
        WD_V4.run_pipeline(idea, v4_out, episodes_spec="1-3", batch_size=3, skill_dir=V4_SKILL_DIR, force=True)
    v4_script = v4_comb.read_text(encoding="utf-8")

    pk_v3 = AA.compare_blind_pair("V4_NEW", v4_script, "V3_OLD", v3_script, backend="codex")
    (ARENA_DIR / pid / "pk_v4_vs_v3.json").write_text(json.dumps(pk_v3, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"  [arena {pid}] v4 vs v3 -> winner={pk_v3['winner']} (consistent={pk_v3['swap_consistent']}) "
        f"| {pk_v3['forward_detail']['decisive_reason'][:70]}",
        flush=True,
    )
    return {
        "pair_id": pid,
        "idea": idea,
        "v4_vs_v3_winner": pk_v3["winner"],
        "swap_consistent": pk_v3["swap_consistent"],
        "reason": pk_v3["forward_detail"]["decisive_reason"],
    }


def main() -> None:
    ARENA_DIR.mkdir(parents=True, exist_ok=True)
    pairs = json.loads((BENCH_DIR / "pairs_manifest.json").read_text(encoding="utf-8"))
    target_ids = {"P01_013_antique", "P02_097_gaokao93", "P04_145_bnb_sell", "P08_085_hotpot_10m"}
    selected = [p for p in pairs if p["pair_id"] in target_ids]

    rows = []
    with cf.ThreadPoolExecutor(max_workers=2) as pool:
        for r in pool.map(eval_seed, selected):
            rows.append(r)

    wins = sum(1 for r in rows if r["v4_vs_v3_winner"] == "V4_NEW" and r["swap_consistent"])
    summary = {"total": len(rows), "v4_strict_wins": wins, "rows": rows}
    (ARENA_DIR / "arena_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"=== V4 vs V3 ARENA SUMMARY: {wins}/{len(rows)} strict swap-consistent wins! ===", flush=True)


if __name__ == "__main__":
    main()
