#!/usr/bin/env python3
"""
Reusable client for Spark `MiniMax H3 Image` ComfyUI service (`minimax-h3-image-comfy-v2.service`
listening at `http://127.0.0.1:8338` on SSH host `sol-spark-benchmark`).

Supports:
  - 0..K reference images mapped to `<Picture 1>` .. `<Picture K>` in `MiniMaxH3ImageConditioning`
    (when editing from a Scene Master Plate, pass the Scene Master Plate as `ref_images[0]` = `<Picture 1>`
    and character `#front` / prop references as `<Picture 2..K>`).
  - Automatic SCP upload to Spark ComfyUI `input/`, remote no-proxy queue submission & polling,
    SCP download of the generated PNG, and optional Lanczos `<= 1024px` (`1K`) companion export.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from compress_1k import compress_image_to_1k

DEFAULT_SSH_HOST = "sol-spark-benchmark"
REMOTE_COMFY_DIR = "/home/admin/minimax-h3-image/ComfyUI"
REMOTE_PORT = 8338

ASPECT_BUCKETS = {
    "9:16": (768, 1344),
    "9:16_hd": (1088, 1920),
    "16:9": (1344, 768),
    "16:9_hd": (1920, 1088),
    "1:1": (1024, 1024),
    "3:4": (896, 1152),
    "4:3": (1152, 896),
}


def _stage_ref_on_spark(local_path: Path, ssh_host: str, staged_cache: set[str]) -> str:
    digest = hashlib.sha1(f"{local_path.resolve()}:{local_path.stat().st_mtime_ns}".encode("utf-8")).hexdigest()[:12]
    remote_name = f"h3ref_{digest}_{local_path.name}"
    if remote_name not in staged_cache:
        subprocess.run(
            ["scp", "-q", str(local_path), f"{ssh_host}:{REMOTE_COMFY_DIR}/input/{remote_name}"],
            check=True,
            timeout=60,
        )
        staged_cache.add(remote_name)
    return remote_name


def generate_spark_h3_image(
    prompt: str,
    out_path: Path,
    ref_images: Optional[List[Path | str]] = None,
    aspect_ratio: str = "9:16",
    width: Optional[int] = None,
    height: Optional[int] = None,
    seed: int = 42,
    steps: int = 6,
    out_1k_path: Optional[Path] = None,
    ssh_host: str = DEFAULT_SSH_HOST,
    staged_cache: Optional[set[str]] = None,
) -> Path:
    """Generate or edit an image via Spark `MiniMax H3 Image` (`MiniMaxH3ImageConditioning`)."""
    refs = [Path(p) for p in (ref_images or [])]
    for p in refs:
        if not p.is_file():
            raise FileNotFoundError(f"Reference image not found: {p}")

    if width is None or height is None:
        if aspect_ratio not in ASPECT_BUCKETS:
            raise ValueError(f"Unsupported aspect_ratio={aspect_ratio!r}; choose from {sorted(ASPECT_BUCKETS)}")
        width, height = ASPECT_BUCKETS[aspect_ratio]

    cache = staged_cache if staged_cache is not None else set()
    remote_refs = [_stage_ref_on_spark(p, ssh_host=ssh_host, staged_cache=cache) for p in refs]

    prefix = f"h3img_{out_path.stem}_{seed}"
    cond_inputs: dict = {
        "clip": ["2", 0],
        "vae": ["3", 0],
        "prompt": prompt,
        "width": int(width),
        "height": int(height),
    }
    graph: dict = {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": "minimax_h3_image_pruned_int8_convrot.safetensors", "weight_dtype": "default"},
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "qwen3vl_32b_minimax_h3_int8_convrot.safetensors",
                "type": "minimax",
                "device": "default",
            },
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "minimax_h3_image_vae_fp16.safetensors"},
        },
        "4": {"class_type": "MiniMaxH3ImageConditioning", "inputs": cond_inputs},
        "5": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["4", 0]}},
        "6": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "positive": ["4", 0],
                "negative": ["5", 0],
                "latent_image": ["4", 1],
                "seed": int(seed),
                "steps": int(steps),
                "cfg": 1.0,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 1.0,
            },
        },
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["3", 0]}},
        "8": {"class_type": "SaveImage", "inputs": {"images": ["7", 0], "filename_prefix": prefix}},
    }

    for idx, rname in enumerate(remote_refs, start=1):
        nid = str(100 + idx)
        graph[nid] = {"class_type": "LoadImage", "inputs": {"image": rname}}
        cond_inputs[f"images.image_{idx}"] = [nid, 0]

    remote_runner = f"""
import json, sys, time, urllib.request
opener = urllib.request.build_opener(urllib.request.ProxyHandler({{}}))
payload = json.loads(sys.stdin.read())
req = urllib.request.Request(
    "http://127.0.0.1:{REMOTE_PORT}/prompt",
    data=json.dumps({{"prompt": payload}}).encode("utf-8"),
    headers={{"Content-Type": "application/json"}},
)
resp = json.loads(opener.open(req, timeout=30).read().decode("utf-8"))
pid = resp["prompt_id"]
deadline = time.time() + 420
while time.time() < deadline:
    hist = json.loads(opener.open(f"http://127.0.0.1:{REMOTE_PORT}/history/{{pid}}", timeout=15).read().decode("utf-8"))
    if pid in hist:
        entry = hist[pid]
        status = entry.get("status", {{}})
        if status.get("status_str") == "error":
            raise RuntimeError(f"ComfyUI execution error: {{status}}")
        outputs = entry.get("outputs", {{}})
        if "8" in outputs and outputs["8"].get("images"):
            img_info = outputs["8"]["images"][0]
            print(json.dumps(img_info))
            sys.exit(0)
    time.sleep(1.5)
raise TimeoutError(f"Timed out waiting for Spark H3 Image prompt_id={{pid}}")
"""
    proc = subprocess.run(
        ["ssh", ssh_host, "python3", "-c", remote_runner],
        input=json.dumps(graph),
        text=True,
        capture_output=True,
        check=True,
        timeout=480,
    )
    last_line = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()][-1]
    img_info = json.loads(last_line)
    sub = img_info.get("subfolder", "").strip("/")
    rel = f"{sub}/{img_info['filename']}" if sub else img_info["filename"]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["scp", "-q", f"{ssh_host}:{REMOTE_COMFY_DIR}/output/{rel}", str(out_path)],
        check=True,
        timeout=60,
    )
    if out_1k_path is not None:
        compress_image_to_1k(out_path, out_1k_path, max_side=1024)
    return out_path


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate/edit keyframes via Spark MiniMax H3 Image")
    ap.add_argument("--prompt", required=True, help="3-part English H3 Image prompt referencing <Picture 1..K>")
    ap.add_argument("--out", required=True, type=Path, help="Output PNG path")
    ap.add_argument("--out-1k", type=Path, default=None, help="Optional <=1024px output path")
    ap.add_argument("--ref", action="append", default=[], help="Reference image path (repeatable, <Picture 1..K>)")
    ap.add_argument("--aspect", default="9:16", choices=sorted(ASPECT_BUCKETS))
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--steps", type=int, default=6)
    ap.add_argument("--ssh-host", default=DEFAULT_SSH_HOST)
    args = ap.parse_args()

    res = generate_spark_h3_image(
        prompt=args.prompt,
        out_path=args.out,
        ref_images=args.ref,
        aspect_ratio=args.aspect,
        seed=args.seed,
        steps=args.steps,
        out_1k_path=args.out_1k,
        ssh_host=args.ssh_host,
    )
    print(f"OK -> {res}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
