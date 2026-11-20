#!/usr/bin/env python3
"""
Run rigorous swap-debiased blind calibration of `audience_agent.py` across all 12 pairs
in `judge/calibration_v2/benchmark/pairs_manifest.json` (8 de-styled Real Hit vs v3 from
60-char ultra-short seeds + 4 controlled Poison-Pill pairs including `hotpot_v2`),
and verify single-script `audit_viewer_retention` on `2005_chongqing_hotpot_v2`!

Target acceptance gate: >= 85% (at least 11/12) strict swap-consistent accuracy!
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import sys
from pathlib import Path

TRAIN_ROOT = Path("/home/zhongwenyu/project/ai-director-train")
sys.path.insert(0, str(TRAIN_ROOT / ".agents/skills/hit-short-drama/scripts"))

import audience_agent as AA  # noqa: E402

BENCH_DIR = TRAIN_ROOT / "judge/calibration_v2/benchmark"
OUT_DIR = TRAIN_ROOT / "judge/calibration_v2/results"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="codex", choices=("codex", "agy"))
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pairs = json.loads((BENCH_DIR / "pairs_manifest.json").read_text(encoding="utf-8"))

    # 1. Unit-check single-script audit on actual 2005_chongqing_hotpot_v2 Ep 1-2!
    print("[calib] Testing single-script audit on actual 2005_chongqing_hotpot_v2 Ep 1-2...", flush=True)
    hotpot_v2_txt = Path(TRAIN_ROOT / "productions/2005_chongqing_hotpot_v2/episodes/ep001-003.md").read_text(encoding="utf-8")
    hotpot_single = AA.audit_viewer_retention(hotpot_v2_txt, eval_eps=[1, 2], backend=args.backend)
    (OUT_DIR / f"hotpot_v2_single_{args.backend}.json").write_text(
        json.dumps(hotpot_single, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"[calib] hotpot_v2 single-audit verdict={hotpot_single['verdict']}, blocked={hotpot_single['blocked_episodes']}",
        flush=True,
    )

    # 2. Swap-debiased blind pairwise evaluation across all 12 pairs
    def eval_one(item: dict):
        pid = item["pair_id"]
        pos_txt = Path(item["pos_path"]).read_text(encoding="utf-8")
        neg_txt = Path(item["neg_path"]).read_text(encoding="utf-8")
        res = AA.compare_blind_pair("POS_GOLD", pos_txt, "NEG_GEN", neg_txt, backend=args.backend)
        out_f = OUT_DIR / f"{pid}_{args.backend}.json"
        out_f.write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        ok = res["winner"] == "POS_GOLD" and res["swap_consistent"]
        print(
            f"  [{pid}] ({item['kind']}) -> winner={res['winner']} (consistent={res['swap_consistent']}) "
            f"| reason={res['forward_detail']['decisive_reason'][:70]}",
            flush=True,
        )
        return {
            "pair_id": pid,
            "kind": item["kind"],
            "correct_and_consistent": ok,
            "winner": res["winner"],
            "swap_consistent": res["swap_consistent"],
            "forward_reason": res["forward_detail"]["decisive_reason"],
            "neg_flaws_caught": res["forward_detail"]["script_b_fatal_flaws"],
        }

    rows = []
    with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = [pool.submit(eval_one, p) for p in pairs]
        for f in cf.as_completed(futs):
            rows.append(f.result())

    rows.sort(key=lambda r: r["pair_id"])
    total = len(rows)
    wins = sum(1 for r in rows if r["correct_and_consistent"])
    real_rows = [r for r in rows if r["kind"] == "real_vs_v3_short_seed"]
    poison_rows = [r for r in rows if r["kind"] == "poison_pill"]
    real_wins = sum(1 for r in real_rows if r["correct_and_consistent"])
    poison_wins = sum(1 for r in poison_rows if r["correct_and_consistent"])
    acc = round(100.0 * wins / max(1, total), 2)

    summary = {
        "backend": args.backend,
        "total_pairs": total,
        "strict_swap_consistent_wins": wins,
        "accuracy_pct": acc,
        "real_vs_v3_wins": f"{real_wins}/{len(real_rows)}",
        "poison_pill_wins": f"{poison_wins}/{len(poison_rows)}",
        "hotpot_v2_single_verdict": hotpot_single["verdict"],
        "hotpot_v2_blocked_episodes": hotpot_single["blocked_episodes"],
        "details": rows,
    }
    (OUT_DIR / f"summary_{args.backend}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("=" * 65, flush=True)
    print(
        f"CALIBRATION RESULT ({args.backend}): {wins}/{total} ({acc}%) "
        f"[Real-vs-v3: {real_wins}/{len(real_rows)}, Poison-Pill: {poison_wins}/{len(poison_rows)}]",
        flush=True,
    )
    sys.exit(0 if acc >= 85.0 else 2)


if __name__ == "__main__":
    main()
