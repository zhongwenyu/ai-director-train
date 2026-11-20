#!/home/zhongwenyu/data/anaconda3/bin/python
"""
Generalizable, noise-invariant audio & dialogue integrity gate using neural Voice Activity Detection
(`silero_vad.onnx` at 16 kHz, 32 ms hop) — ZERO hardcoded dB room-noise thresholds.

Checks every generated shot MP4 against its scheduled speech timeline (`<d>...</d>` + `vo_custom`):
  1. `SPEECH_TRUNCATED`: Neural human-voice probability remains active near the clip's hard end
     (`t >= duration - 0.22s`), catching mid-sentence / tail-syllable cut-offs regardless of ambient noise.
  2. `MISSING_SCHEDULED_SPEECH`: A scheduled `<d>` / VO window has near-zero neural speech activity.
  3. `UNSCHEDULED_VOCAL_NOISE`: Strong human vocal bursts (`>= 0.22s`) appear outside scheduled dialogue/VO
     windows (catching unintended grunts, coughs, or trailing gibberish even in quiet or noisy scenes).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import wave
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import onnxruntime as ort

DEFAULT_VAD_ONNX = Path("/home/zhongwenyu/.paseo/models/local-speech/silero-vad/silero_vad.onnx")
SR = 16000
HOP = 512  # 32 ms at 16 kHz


def extract_pcm16k(mp4_path: Path) -> Tuple[np.ndarray, float]:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", str(mp4_path), "-ac", "1", "-ar", str(SR), tmp.name],
            check=True,
        )
        with wave.open(tmp.name, "rb") as wf:
            n = wf.getnframes()
            raw = wf.readframes(n)
    pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    return pcm, len(pcm) / float(SR)


def run_silero_vad(sess: ort.InferenceSession, pcm: np.ndarray) -> np.ndarray:
    n_frames = len(pcm) // HOP
    if n_frames == 0:
        return np.zeros(0, dtype=np.float32)
    h = np.zeros((2, 1, 64), dtype=np.float32)
    c = np.zeros((2, 1, 64), dtype=np.float32)
    probs = np.empty(n_frames, dtype=np.float32)
    for i in range(n_frames):
        chunk = pcm[i * HOP : (i + 1) * HOP].reshape(1, HOP)
        prob, h, c = sess.run(None, {"x": chunk, "h": h, "c": c})
        probs[i] = float(prob[0, 0])
    return probs


def probs_to_segments(probs: np.ndarray, threshold: float = 0.52, min_dur: float = 0.18, merge_gap: float = 0.16) -> List[Tuple[float, float, float]]:
    dt = HOP / float(SR)
    raw: List[List[float]] = []
    in_seg = False
    s_idx = 0
    for idx, p in enumerate(probs):
        if p >= threshold and not in_seg:
            in_seg = True
            s_idx = idx
        elif p < threshold and in_seg:
            in_seg = False
            raw.append([s_idx * dt, idx * dt, float(probs[s_idx:idx].max())])
    if in_seg:
        raw.append([s_idx * dt, len(probs) * dt, float(probs[s_idx:].max())])

    merged: List[List[float]] = []
    for seg in raw:
        if merged and seg[0] - merged[-1][1] <= merge_gap:
            merged[-1][1] = seg[1]
            merged[-1][2] = max(merged[-1][2], seg[2])
        else:
            merged.append(seg)
    return [(round(s, 3), round(e, 3), round(pk, 3)) for s, e, pk in merged if (e - s) >= min_dur]


def parse_scheduled_windows(spec: Dict[str, Any], actual_dur: float) -> List[Tuple[float, float, str]]:
    windows: List[Tuple[float, float, str]] = []
    prompt = spec.get("prompt", "")
    for line in prompt.splitlines():
        if "<d>" not in line:
            continue
        m_win = re.search(r"\((\d+(?:\.\d+)?)s\s*-\s*(\d+(?:\.\d+)?)s\)", line)
        m_txt = re.search(r"<d>(.*?)</d>", line)
        txt = re.sub(r"^\s*\[[A-Za-z]+\]\s*", "", m_txt.group(1)).strip() if m_txt else ""
        if m_win:
            windows.append((float(m_win.group(1)), float(m_win.group(2)), txt))
        else:
            windows.append((0.0, actual_dur, txt))
    vc = spec.get("vo_custom")
    if vc:
        s = float(vc.get("dst_start", 0.0))
        e = min(actual_dur, s + float(vc.get("max_len", 4.5)) + 0.6)
        windows.append((s, e, f"[VO] {vc.get('text', '')}"))
    return windows


def audit_shot_audio(sess: ort.InferenceSession, mp4_path: Path, spec: Dict[str, Any]) -> Dict[str, Any]:
    pcm, dur = extract_pcm16k(mp4_path)
    probs = run_silero_vad(sess, pcm)
    segs = probs_to_segments(probs)
    sched = parse_scheduled_windows(spec, dur)
    issues: List[Dict[str, Any]] = []

    # 1. Tail speech truncation check (speech ends within 0.30s of hard clip end or active in tail)
    tail_frames = max(1, int(round(0.28 / (HOP / SR))))
    last_seg_end = segs[-1][1] if segs else 0.0
    if (len(probs) >= tail_frames and float(probs[-tail_frames:].mean()) >= 0.38) or (segs and dur - last_seg_end < 0.25):
        issues.append({
            "type": "SPEECH_TRUNCATED",
            "at": [round(min(dur - 0.28, last_seg_end), 2), round(dur, 2)],
            "detail": f"Speech runs right into hard clip end (last_speech_end={last_seg_end:.2f}s / dur={dur:.2f}s)",
        })

    # 2. Scheduled dialogue coverage check
    for ws, we, txt in sched:
        overlap = sum(max(0.0, min(we + 0.6, se) - max(max(0.0, ws - 0.4), ss)) for ss, se, _ in segs)
        if overlap < 0.25:
            issues.append({
                "type": "MISSING_SCHEDULED_SPEECH",
                "at": [round(ws, 2), round(we, 2)],
                "detail": f"No neural speech detected for scheduled line [{ws:.1f}s-{we:.1f}s]: {txt!r}",
            })

    # 3. Unscheduled vocal burst check (grunts / cough-speech / trailing gibberish)
    for ss, se, pk in segs:
        if pk < 0.65 or (se - ss) < 0.24:
            continue
        covered = any(
            min(we + 0.85, se) - max(max(0.0, ws - 0.55), ss) >= 0.45 * (se - ss)
            for ws, we, _ in sched
        )
        if not covered:
            issues.append({
                "type": "UNSCHEDULED_VOCAL_NOISE",
                "at": [ss, se],
                "detail": f"Unscheduled vocal sound [{ss:.2f}s-{se:.2f}s] (peak_vad={pk:.2f}) outside dialogue windows",
            })

    return {
        "id": spec["id"],
        "duration_s": round(dur, 3),
        "status": "FAIL" if issues else "PASS",
        "vad_segments": segs,
        "scheduled_windows": sched,
        "issues": issues,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Neural VAD audio/dialogue integrity checker (zero dB overfitting)")
    ap.add_argument("--plan-json", required=True, type=Path)
    ap.add_argument("--takes-dir", required=True, type=Path)
    ap.add_argument("--out-json", type=Path, default=None)
    ap.add_argument("--vad-onnx", type=Path, default=DEFAULT_VAD_ONNX)
    args = ap.parse_args()

    sess = ort.InferenceSession(str(args.vad_onnx))
    plan = json.loads(args.plan_json.read_text(encoding="utf-8"))
    results = []
    fails = 0
    for sp in plan:
        mp4 = args.takes_dir / sp["id"] / "video.mp4"
        res = audit_shot_audio(sess, mp4, sp)
        results.append(res)
        if res["status"] != "PASS":
            fails += 1
            print(f"[FAIL] {sp['id']} ({res['duration_s']}s): {res['issues']}", flush=True)
        else:
            print(f"[PASS] {sp['id']} ({res['duration_s']}s) vad={[(s, e) for s, e, _ in res['vad_segments']]}", flush=True)

    if args.out_json:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Summary: {len(results) - fails}/{len(results)} PASS, {fails} FAIL", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
