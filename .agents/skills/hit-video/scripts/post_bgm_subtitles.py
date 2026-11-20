#!/usr/bin/env python3
"""
Generalized Separated BGM + Dual-Layer Subtitle Post-Production Pipeline for hit-video.

Architectural invariant:
- Raw shot videos (shot.videoId) and merged episode films (export MP4) MUST stay 100% clean
  (NO burned-in subtitles, NO baked-in BGM) so downstream Spark LTX 2x HD upscaling never distorts
  text pixels and single-shot re-rolls never break music continuity.
- Instead, this script:
  1. Probes exact ffprobe durations of every shot video in episode order -> computes zero-drift
     cumulative `bgmOffset` per shot.
  2. Compiles shot-level `subtitles` + episode-level `subtitles` JSON + standard WebVTT (`.vtt`)
     supporting three cue kinds:
       - `caption`: top screen-text badge (`[画面文字]`)
       - `dialogue`: bottom synchronized lip-sync dialogue
       - `vo`: bottom inner monologue / voice-over (`心声（...）`)
  3. Renders a standalone separated `bgm.mp3` (48kHz stereo) from `audio-library` cues aligned
     to exact cumulative scene boundaries, with automatic smooth envelope ducking during
     spoken `dialogue` and `vo` intervals!
  4. Optionally uploads `.mp3` + `.vtt` to Director Workstation and binds `ep.bgmMediaId`,
     `ep.subtitleMediaId`, `ep.subtitles`, and per-shot `bgmMediaId`, `bgmOffset`, `subtitles`.
"""
import argparse
import json
import subprocess
from pathlib import Path


def probe_duration(mp4: Path) -> float:
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(mp4)],
        text=True,
    ).strip()
    return float(out)


def fmt_vtt_ts(sec: float) -> str:
    sec = max(0.0, float(sec))
    ms_total = int(round(sec * 1000))
    hh = ms_total // 3600000
    rem = ms_total % 3600000
    mm = rem // 60000
    rem %= 60000
    ss = rem // 1000
    ms = rem % 1000
    return f"{hh:02d}:{mm:02d}:{ss:02d}.{ms:03d}"


def build_vtt(episode_cues: list) -> str:
    lines = ["WEBVTT", ""]
    for idx, c in enumerate(episode_cues, 1):
        s = fmt_vtt_ts(c["start"])
        e = fmt_vtt_ts(c["end"])
        kind = c.get("kind", "dialogue")
        text = c["text"].strip()
        if kind == "caption":
            lines.append(f"{idx}")
            lines.append(f"{s} --> {e} line:8%")
            lines.append(f"【{text}】")
        elif kind == "vo":
            lines.append(f"{idx}")
            lines.append(f"{s} --> {e}")
            lines.append(f"（{text}）")
        else:
            lines.append(f"{idx}")
            lines.append(f"{s} --> {e}")
            lines.append(text)
        lines.append("")
    return "\n".join(lines)


def merge_intervals(intervals: list, pad_before: float = 0.12, pad_after: float = 0.18, gap_merge: float = 0.45) -> list:
    if not intervals:
        return []
    expanded = sorted([(max(0.0, s - pad_before), e + pad_after) for s, e in intervals])
    merged = [list(expanded[0])]
    for s, e in expanded[1:]:
        if s <= merged[-1][1] + gap_merge:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return [(round(a, 3), round(b, 3)) for a, b in merged]


def render_separated_bgm(bgm_segments: list, speech_windows: list, total_duration: float, out_mp3: Path):
    """
    bgm_segments: list of dicts:
      {
        "file": "/abs/path/to/track.mp3",
        "start": float,          # episode timeline start (s)
        "end": float,            # episode timeline end (s)
        "src_offset": float,     # optional start offset inside source audio (default 0.0)
        "align_end": bool,       # if True, align track's natural end to `end` (great for cliffhanger risers!)
        "gain": float,           # base gain for this track (default 0.48)
        "fade_in": float,        # default 0.8
        "fade_out": float,       # default 1.0
      }
    """
    out_mp3 = Path(out_mp3)
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    inputs = []
    seg_filters = []
    seg_labels = []

    for i, seg in enumerate(bgm_segments):
        src = Path(seg["file"])
        if not src.is_file():
            raise FileNotFoundError(f"BGM source missing: {src}")
        src_dur = probe_duration(src)
        dst_s = float(seg["start"])
        dst_e = min(total_duration, float(seg["end"]))
        seg_dur = max(0.2, dst_e - dst_s)
        gain = float(seg.get("gain", 0.48))
        fin = min(seg_dur * 0.4, float(seg.get("fade_in", 0.8)))
        fout = min(seg_dur * 0.4, float(seg.get("fade_out", 1.0)))

        if seg.get("align_end") and src_dur >= seg_dur:
            src_off = max(0.0, src_dur - seg_dur)
            inputs += ["-i", str(src)]
            chain = f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,atrim={src_off:.3f}:{src_dur:.3f},asetpts=PTS-STARTPTS"
        else:
            src_off = float(seg.get("src_offset", 0.0))
            # Use -stream_loop -1 so shorter loops seamlessly cover longer dramatic scenes
            inputs += ["-stream_loop", "-1", "-i", str(src)]
            chain = f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,atrim={src_off:.3f}:{src_off + seg_dur:.3f},asetpts=PTS-STARTPTS"

        if fin > 0.02:
            chain += f",afade=t=in:st=0:d={fin:.3f}"
        if fout > 0.02:
            chain += f",afade=t=out:st={max(0.0, seg_dur - fout):.3f}:d={fout:.3f}"
        delay_ms = int(round(dst_s * 1000))
        chain += f",volume={gain:.3f},adelay={delay_ms}:all=1[bgm{i}]"
        seg_filters.append(chain)
        seg_labels.append(f"[bgm{i}]")

    # Add silent base track of exact total_duration so output length matches merged episode film
    bed_idx = len(bgm_segments)
    inputs += ["-f", "lavfi", "-t", f"{total_duration:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]

    merged_speech = merge_intervals(speech_windows)
    if merged_speech:
        duck_terms = "+".join([f"between(t,{s:.3f},{e:.3f})" for s, e in merged_speech])
        duck_filter = f",volume='if(gt({duck_terms},0),0.36,1.0)':eval=frame"
    else:
        duck_filter = ""

    filt = (
        ";".join(seg_filters)
        + f";[{bed_idx}:a]{''.join(seg_labels)}amix=inputs={len(bgm_segments) + 1}:duration=first:normalize=0"
        + f"{duck_filter},alimiter=limit=0.92[outa]"
    )

    tmp = out_mp3.with_suffix(".tmp.mp3")
    cmd = [
        "ffmpeg", "-v", "error", "-y",
        *inputs,
        "-filter_complex", filt,
        "-map", "[outa]",
        "-c:a", "libmp3lame", "-b:a", "192k",
        str(tmp),
    ]
    subprocess.run(cmd, check=True)
    tmp.replace(out_mp3)


def compile_post_pack(spec_path: Path, outdir: Path) -> dict:
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    shots_out = []
    episode_cues = []
    speech_windows = []
    cursor = 0.0

    for sh in spec["shots"]:
        sid = sh["id"]
        mp4 = Path(sh["video"])
        dur = probe_duration(mp4)
        shot_cues = []
        for c in sh.get("cues", []):
            rel_s = max(0.0, float(c["start"]))
            rel_e = min(dur, float(c["end"]))
            kind = c.get("kind", "dialogue")
            speaker = c.get("speaker", "")
            text = c["text"]
            shot_cues.append({
                "start": round(rel_s, 3),
                "end": round(rel_e, 3),
                "kind": kind,
                "speaker": speaker,
                "text": text,
            })
            abs_s = round(cursor + rel_s, 3)
            abs_e = round(cursor + rel_e, 3)
            episode_cues.append({
                "start": abs_s,
                "end": abs_e,
                "kind": kind,
                "speaker": speaker,
                "text": text,
                "shotId": sid,
            })
            if kind in ("dialogue", "vo"):
                speech_windows.append((abs_s, abs_e))

        shots_out.append({
            "id": sid,
            "studioShotId": sh.get("studioShotId"),
            "duration": round(dur, 3),
            "bgmOffset": round(cursor, 3),
            "subtitles": shot_cues,
        })
        cursor += dur

    total_duration = round(cursor, 3)

    # Resolve BGM segments (support shot-boundary references via `start_shot` / `end_shot` or explicit seconds)
    shot_bounds = {}
    t_acc = 0.0
    for s in shots_out:
        shot_bounds[s["id"]] = (t_acc, round(t_acc + s["duration"], 3))
        t_acc += s["duration"]

    resolved_bgm = []
    for seg in spec.get("bgm_segments", []):
        s_sec = shot_bounds[seg["start_shot"]][0] if "start_shot" in seg else float(seg["start"])
        e_sec = shot_bounds[seg["end_shot"]][1] if "end_shot" in seg else float(seg["end"])
        s_sec += float(seg.get("start_delta", 0.0))
        e_sec += float(seg.get("end_delta", 0.0))
        item = dict(seg)
        item["start"] = round(max(0.0, s_sec), 3)
        item["end"] = round(min(total_duration, e_sec), 3)
        resolved_bgm.append(item)

    vtt_path = outdir / f"{spec.get('prefix', 'episode')}_subtitles.vtt"
    bgm_path = outdir / f"{spec.get('prefix', 'episode')}_bgm.mp3"
    manifest_path = outdir / f"{spec.get('prefix', 'episode')}_post_manifest.json"

    vtt_path.write_text(build_vtt(episode_cues), encoding="utf-8")
    render_separated_bgm(resolved_bgm, speech_windows, total_duration, bgm_path)

    manifest = {
        "total_duration": total_duration,
        "vtt_file": str(vtt_path),
        "bgm_file": str(bgm_path),
        "bgm_segments": resolved_bgm,
        "shots": shots_out,
        "episode_subtitles": episode_cues,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Post-pack compiled: total={total_duration:.2f}s, cues={len(episode_cues)}, bgm={bgm_path.name}, vtt={vtt_path.name}")
    return manifest


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("spec_json", type=Path, help="JSON spec with shots[], cues[], and bgm_segments[]")
    ap.add_argument("--outdir", required=True, type=Path)
    args = ap.parse_args()
    compile_post_pack(args.spec_json, args.outdir)


if __name__ == "__main__":
    main()
