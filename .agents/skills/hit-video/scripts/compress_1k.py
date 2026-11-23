#!/usr/bin/env python3
"""Compress reference images proportionally so max(width, height) <= 1024 (1K) without modifying 2K originals."""
import argparse
import json
import os
import threading
from pathlib import Path
from PIL import Image

RESAMPLE = getattr(Image, "Resampling", Image).LANCZOS


def compress_image_to_1k(src_path: Path, dst_path: Path, max_side: int = 1024) -> dict:
    src_path = Path(src_path)
    dst_path = Path(dst_path)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_dst = dst_path.with_name(f".{dst_path.stem}.tmp.{os.getpid()}.{threading.get_ident()}{dst_path.suffix}")
    with Image.open(src_path) as im:
        orig_w, orig_h = im.size
        mode = "RGBA" if im.mode in ("RGBA", "LA") else "RGB"
        work = im.convert(mode)
        if max(orig_w, orig_h) > max_side:
            scale = max_side / float(max(orig_w, orig_h))
            new_w = max(1, int(round(orig_w * scale)))
            new_h = max(1, int(round(orig_h * scale)))
            work = work.resize((new_w, new_h), RESAMPLE)
        else:
            new_w, new_h = orig_w, orig_h
        if dst_path.suffix.lower() in (".jpg", ".jpeg"):
            if work.mode == "RGBA":
                bg = Image.new("RGB", work.size, (255, 255, 255))
                bg.paste(work, mask=work.split()[3])
                work = bg
            work.save(tmp_dst, quality=95, optimize=True)
        else:
            work.save(tmp_dst, format="PNG", optimize=True)
    os.replace(tmp_dst, dst_path)
    assert max(new_w, new_h) <= max_side, f"Failed 1K limit: {new_w}x{new_h}"
    return {
        "src": str(src_path),
        "dst": str(dst_path),
        "orig_size": [orig_w, orig_h],
        "new_size": [new_w, new_h],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("inputs", nargs="+", type=Path, help="Source image files or directories")
    ap.add_argument("--outdir", required=True, type=Path, help="Output directory for <=1K images")
    ap.add_argument("--max-side", type=int, default=1024)
    args = ap.parse_args()

    records = []
    exts = {".png", ".jpg", ".jpeg", ".webp"}
    for item in args.inputs:
        if item.is_dir():
            for f in sorted(item.iterdir()):
                if f.is_file() and f.suffix.lower() in exts:
                    records.append(compress_image_to_1k(f, args.outdir / (f.stem + ".png"), args.max_side))
        elif item.is_file():
            records.append(compress_image_to_1k(item, args.outdir / (item.stem + ".png"), args.max_side))
    manifest_path = args.outdir / "1k_manifest.json"
    manifest_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Compressed {len(records)} images to <= {args.max_side}px -> {args.outdir}")


if __name__ == "__main__":
    main()
