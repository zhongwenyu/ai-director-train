#!/usr/bin/env python3
"""Extract timestamped high-density contact sheets + audio stats/WAV from generated MP4s for multimodal video inspection."""
import argparse
import json
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw

RESAMPLE = getattr(Image, "Resampling", Image).LANCZOS


def inspect_mp4(mp4_path: Path, out_dir: Path, fps: float = 1.5, cols: int = 4) -> dict:
    mp4_path = Path(mp4_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    probe = json.loads(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(mp4_path)],
        text=True,
    ))
    vstream = next(s for s in probe["streams"] if s["codec_type"] == "video")
    astream = next((s for s in probe["streams"] if s["codec_type"] == "audio"), None)
    duration = float(probe["format"]["duration"])

    frames_dir = out_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    for old in frames_dir.glob("*.jpg"):
        old.unlink()

    subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(mp4_path), "-vf", f"fps={fps}", "-q:v", "2", str(frames_dir / "f_%04d.jpg")],
        check=True,
    )
    frame_files = sorted(frames_dir.glob("f_*.jpg"))
    cell_w, cell_h = 270, 500
    rows = (len(frame_files) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), (20, 20, 24))
    draw = ImageDraw.Draw(sheet)

    timestamps = []
    for idx, ff in enumerate(frame_files):
        t_sec = round(idx / fps, 2)
        timestamps.append(t_sec)
        with Image.open(ff) as im:
            im_c = im.convert("RGB")
            im_c.thumbnail((cell_w - 12, cell_h - 36), RESAMPLE)
            cx = (idx % cols) * cell_w + (cell_w - im_c.width) // 2
            cy = (idx // cols) * cell_h + 6
            sheet.paste(im_c, (cx, cy))
            draw.text(((idx % cols) * cell_w + 8, (idx // cols) * cell_h + cell_h - 26), f"t={t_sec:.2f}s", fill=(240, 220, 120))

    sheet_path = out_dir / "contact_sheet.jpg"
    sheet.save(sheet_path, quality=92)

    audio_wav = None
    mean_vol = None
    max_vol = None
    if astream:
        audio_wav = out_dir / "audio_16k.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(mp4_path), "-vn", "-ac", "1", "-ar", "16000", str(audio_wav)],
            check=True,
        )
        vol = subprocess.run(
            ["ffmpeg", "-i", str(mp4_path), "-af", "volumedetect", "-f", "null", "-"],
            capture_output=True, text=True,
        ).stderr
        for line in vol.splitlines():
            if "mean_volume:" in line:
                mean_vol = line.split("mean_volume:")[1].strip()
            elif "max_volume:" in line:
                max_vol = line.split("max_volume:")[1].strip()

    report = {
        "video": str(mp4_path),
        "width": vstream["width"],
        "height": vstream["height"],
        "duration_s": round(duration, 3),
        "nb_frames": vstream.get("nb_frames"),
        "has_audio": bool(astream),
        "audio_sample_rate": astream.get("sample_rate") if astream else None,
        "mean_volume": mean_vol,
        "max_volume": max_vol,
        "sampled_timestamps": timestamps,
        "contact_sheet": str(sheet_path),
        "audio_wav": str(audio_wav) if audio_wav else None,
    }
    (out_dir / "inspect.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mp4", type=Path)
    ap.add_argument("--outdir", required=True, type=Path)
    ap.add_argument("--fps", type=float, default=1.5)
    args = ap.parse_args()
    rep = inspect_mp4(args.mp4, args.outdir, fps=args.fps)
    print(json.dumps(rep, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
