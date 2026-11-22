#!/home/zhongwenyu/data/anaconda3/bin/python3
"""
Objective Target-Video Signal Alignment & Visual Triptych Verifier (`trainer/verify_against_target.py`).

Cross-validates multimodal blind arena scores with deterministic physical signal probes comparing
each evolved candidate (`v0`, `v1`, `v2`, ...) directly against the sealed Target Reference Video
(`gold_sealed/gold_reference.mp4`, including `target_video.mp4`):
  1. Cut-Rate & Average Shot Length (ASL) alignment vs Target Video;
  2. Neural `Silero-VAD` speech completeness, speech density alignment, and zero-truncation rate;
  3. Micro-motion liveness & anti-freeze / anti-whip-pan stability;
  4. Target Parity Ratio (`Cand_Score / Target_Gold_Score * 100%`) across all 6 cinematic dimensions;
  5. Synchronized 3-way Triptych Comparison MP4 (`[v0 Baseline | Evolved Champion | Target Video]`).
"""
from __future__ import annotations

import json
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

TRAIN_ROOT = Path("/home/zhongwenyu/project/ai-director-train")
if str(TRAIN_ROOT / "judge") not in sys.path:
    sys.path.insert(0, str(TRAIN_ROOT / "judge"))
import video_arena_judge as VAJ  # noqa: E402


def compute_signal_alignment_report(
    cases: Sequence[Dict[str, Any]],
    cand_videos: Dict[str, Path],
    vs_gold_arena: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compare candidate MP4s directly against sealed Target Reference MP4s on physical signals."""
    rows: List[Dict[str, Any]] = []
    for c in cases:
        cid = c["case_id"]
        if cid not in cand_videos or not Path(cand_videos[cid]).is_file():
            continue
        has_spk = any(t.get("mode") != "inner_os" for t in c.get("dialogue_turns", []))
        cand_sig = VAJ.probe_video_signals(Path(cand_videos[cid]), has_spoken_dialogue=has_spk)
        gold_sig = VAJ.probe_video_signals(Path(c["gold_sealed_mp4"]), has_spoken_dialogue=has_spk)

        cand_shots = max(1, cand_sig["approx_cuts"] + 1)
        gold_shots = max(1, gold_sig["approx_cuts"] + 1)
        cand_asl = round(cand_sig["duration_s"] / cand_shots, 2)
        gold_asl = round(gold_sig["duration_s"] / gold_shots, 2)

        rows.append(
            {
                "case_id": cid,
                "genre": c.get("genre", ""),
                "cand_duration_s": cand_sig["duration_s"],
                "gold_duration_s": gold_sig["duration_s"],
                "cand_shots": cand_shots,
                "gold_shots": gold_shots,
                "cand_asl_s": cand_asl,
                "gold_asl_s": gold_asl,
                "asl_abs_gap_s": round(abs(cand_asl - gold_asl), 2),
                "cand_speech_s": cand_sig["speech_total_s"],
                "gold_speech_s": gold_sig["speech_total_s"],
                "cand_tail_truncated": cand_sig["tail_truncated"],
                "cand_frozen": cand_sig["frozen_slideshow"],
                "cand_median_motion": cand_sig["median_motion"],
                "gold_median_motion": gold_sig["median_motion"],
            }
        )

    zero_trunc_rate = round(
        sum(1 for r in rows if not r["cand_tail_truncated"]) / max(1, len(rows)), 4
    )
    zero_freeze_rate = round(
        sum(1 for r in rows if not r["cand_frozen"]) / max(1, len(rows)), 4
    )
    mean_cand_asl = round(statistics.mean(r["cand_asl_s"] for r in rows), 2) if rows else 0.0
    mean_gold_asl = round(statistics.mean(r["gold_asl_s"] for r in rows), 2) if rows else 0.0
    mean_asl_gap = round(statistics.mean(r["asl_abs_gap_s"] for r in rows), 2) if rows else 0.0

    parity_pct = None
    dim_parity_pct: Dict[str, float] = {}
    if vs_gold_arena and vs_gold_arena.get("ref_mean_score", 0) > 0:
        parity_pct = round(
            100.0 * float(vs_gold_arena["cand_mean_score"]) / float(vs_gold_arena["ref_mean_score"]), 2
        )
        for k in VAJ.DIM_KEYS:
            gv = float(vs_gold_arena["ref_dim_means"].get(k, 0.0))
            cv = float(vs_gold_arena["cand_dim_means"].get(k, 0.0))
            dim_parity_pct[k] = round(100.0 * cv / gv, 1) if gv > 0 else 100.0

    return {
        "evaluated_cases": len(rows),
        "zero_tail_truncation_rate": zero_trunc_rate,
        "zero_freeze_rate": zero_freeze_rate,
        "mean_cand_asl_s": mean_cand_asl,
        "mean_target_gold_asl_s": mean_gold_asl,
        "mean_asl_abs_gap_s": mean_asl_gap,
        "target_parity_overall_pct": parity_pct,
        "target_parity_by_dim_pct": dim_parity_pct,
        "per_case_signals": rows,
    }


def render_triptych_comparison(
    v0_mp4: Path,
    champ_mp4: Path,
    target_mp4: Path,
    out_mp4: Path,
    *,
    aspect_ratio: str = "16:9",
) -> Path:
    """Render synchronized 3-column comparison video `[Left: v0 | Mid: Evolved | Right: Target]` (audio from Mid)."""
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    cw, ch = (480, 270) if aspect_ratio == "16:9" else (320, 568)
    fc = (
        f"[0:v]scale={cw}:{ch}:force_original_aspect_ratio=decrease,pad={cw}:{ch}:(ow-iw)/2:(oh-ih)/2,fps=24[v0];"
        f"[1:v]scale={cw}:{ch}:force_original_aspect_ratio=decrease,pad={cw}:{ch}:(ow-iw)/2:(oh-ih)/2,fps=24[v1];"
        f"[2:v]scale={cw}:{ch}:force_original_aspect_ratio=decrease,pad={cw}:{ch}:(ow-iw)/2:(oh-ih)/2,fps=24[v2];"
        "[v0][v1][v2]hstack=inputs=3,format=yuv420p[vout]"
    )
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-i", str(v0_mp4),
            "-i", str(champ_mp4),
            "-i", str(target_mp4),
            "-filter_complex", fc,
            "-map", "[vout]", "-map", "1:a",
            "-c:v", "libx264", "-preset", "fast", "-crf", "21",
            "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "160k",
            "-shortest",
            str(out_mp4),
        ],
        check=True,
    )
    return out_mp4


if __name__ == "__main__":
    print("verify_against_target module loaded successfully.")
