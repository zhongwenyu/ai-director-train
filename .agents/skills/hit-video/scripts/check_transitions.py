#!/usr/bin/env python3
"""
Extract exact cut-point transition strips across all consecutive shots (Shot N -> Shot N+1)
of an episode: [Shot N -1.0s | Shot N last frame || Shot N+1 first frame | Shot N+1 +1.0s],
producing a single visual Transition Audit Sheet to catch prop teleports, costume jumps,
pre-action causality inversions, or spatial discontinuities before publishing.
"""
from __future__ import annotations
import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw


def probe_duration(mp4: Path) -> float:
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(mp4)],
        text=True,
    )
    return float(json.loads(out)["format"]["duration"])


def extract_frame(mp4: Path, t_sec: float, out_png: Path):
    t_sec = max(0.0, t_sec)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-ss", f"{t_sec:.3f}", "-i", str(mp4), "-frames:v", "1", str(out_png)],
        check=True,
    )


def build_transition_sheet(videos: list[tuple[str, Path]], out_jpg: Path):
    if len(videos) < 2:
        raise ValueError("Need at least 2 shots to audit transitions")
    tw, th = 240, 426
    cols = 4
    rows = len(videos) - 1
    canvas = Image.new("RGB", (cols * tw + 24, rows * (th + 38)), (16, 16, 22))
    draw = ImageDraw.Draw(canvas)
    resample = getattr(Image, "Resampling", Image).LANCZOS

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        for i in range(rows):
            id_a, mp4_a = videos[i]
            id_b, mp4_b = videos[i + 1]
            dur_a = probe_duration(mp4_a)
            dur_b = probe_duration(mp4_b)
            pts = [
                (mp4_a, max(0.0, dur_a - 1.1), f"{id_a} (-1.0s)"),
                (mp4_a, max(0.0, dur_a - 0.08), f"{id_a} (END {dur_a:.1f}s)"),
                (mp4_b, 0.04, f"{id_b} (START 0.0s)"),
                (mp4_b, min(dur_b - 0.08, 1.1), f"{id_b} (+1.0s)"),
            ]
            y = i * (th + 38)
            draw.text((12, y + 6), f"CUT {i+1}: {id_a}  ===>  {id_b}", fill=(255, 220, 120))
            for c, (src, ts, lbl) in enumerate(pts):
                fp = tmp / f"r{i}_c{c}.png"
                extract_frame(src, ts, fp)
                x = c * tw + (16 if c >= 2 else 4)
                with Image.open(fp) as im:
                    fit = im.convert("RGB").resize((tw - 6, th - 6), resample)
                canvas.paste(fit, (x, y + 30))
                draw.rectangle([x, y + 30, x + tw - 7, y + 30 + 22], fill=(0, 0, 0))
                draw.text((x + 6, y + 34), lbl, fill=(235, 240, 255))
            # Draw vertical cut divider line between END and START
            div_x = 2 * tw + 9
            draw.line([(div_x, y + 28), (div_x, y + th + 28)], fill=(255, 90, 90), width=3)

    out_jpg.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_jpg, quality=92)
    print(f"Saved Transition Audit Sheet ({rows} cuts) -> {out_jpg}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--takes-dir", required=True)
    ap.add_argument("--plan-json", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    takes = Path(args.takes_dir)
    plan = json.loads(Path(args.plan_json).read_text(encoding="utf-8"))
    vids = [(sp["id"], takes / sp["id"] / "video.mp4") for sp in plan]
    build_transition_sheet(vids, Path(args.out))


if __name__ == "__main__":
    main()
