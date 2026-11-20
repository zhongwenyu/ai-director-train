#!/usr/bin/env python3
"""Execute MiniMax H3 Pika (Pika-H3-Flex) 480p video generation with strict <=1K image check, zero-appearance prompt linting, voice reference binding, and vo_split."""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from PIL import Image

HERE = Path(__file__).resolve().parent
from compress_1k import compress_image_to_1k  # noqa: E402

STUDIO_BRIDGE = Path("/home/zhongwenyu/project/playlets-studio/skills/studio-bridge/scripts")
if str(STUDIO_BRIDGE) not in sys.path:
    sys.path.insert(0, str(STUDIO_BRIDGE))
import vo_split  # noqa: E402

API_5090_URL = os.environ.get("PIKA_5090_URL", "http://127.0.0.1:8090/v2/video_generation")
API_5090_KEY_FILE = Path(os.environ.get("PIKA_5090_KEY_FILE", "/home/zhongwenyu/project/h3-uncensored-20261011/api-key"))

# Forbidden character appearance / garment tokens in video prompts (Zero-Appearance Rule)
FORBIDDEN_APPEARANCE_RE = re.compile(
    r"\b("
    r"shirt|t-shirt|tee|blouse|suit|blazer|jacket|coat|hoodie|sweater|cardigan|"
    r"dress|skirt|trousers|pants|jeans|shorts|apron|vest|tie|neckerchief|scarf|"
    r"chef\s+hat|toque|glasses|spectacles|sneakers|heels|loafers|boots|"
    r"ponytail|twintails|braid|bun|bangs|fringe|curly\s+hair|short\s+hair|long\s+hair|"
    r"middle-aged|elderly|teenage|twenty-one-year-old|21-year-old|26-year-old"
    r")\b",
    re.IGNORECASE,
)


def lint_zero_appearance(prompt: str, shot_id: str) -> list:
    issues = []
    for m in FORBIDDEN_APPEARANCE_RE.finditer(prompt):
        snippet = prompt[max(0, m.start() - 25):min(len(prompt), m.end() + 25)].replace("\n", " ")
        issues.append(f"[{shot_id}] Forbidden character appearance/garment word '{m.group(0)}' in: ...{snippet}...")
    # Also forbid stage-direction parentheses or speaker prefixes inside <d>...</d> (causes TTS to read speaker names aloud!)
    for dm in re.finditer(r"<d>(.*?)</d>", prompt, re.S):
        inner = dm.group(1)
        body = re.sub(r"^\s*\[[A-Za-z]+\]\s*", "", inner)
        if re.match(r"^\s*[\(（]", body) or "in Picture" in body or "speaks" in body:
            issues.append(f"[{shot_id}] Forbidden stage direction / speaker name inside <d>...</d>: {inner[:60]!r} (move English speaker/emotion direction OUTSIDE <d>!)")
    return issues


def mix_vo_upgraded(base_mp4: Path, vo_low_mp4: Path, windows: list, out_mp4: Path, mode: str = "demucs_duck"):
    """Mix VO into silent-mouth master with broadband-noise ducking or direct window crossfade."""
    tmp = out_mp4.with_suffix(".tmp.mp4")
    if mode == "splice_window" and len(windows) == 1:
        s, e = windows[0]
        fade = 0.15
        # Duck base to 0 inside [s+fade, e-fade] and crossfade native VO audio window cleanly
        filt = (
            f"[0:a]aresample=48000,volume='if(between(t,{s:.3f},{e:.3f}),0.15,1.0)':eval=frame[base];"
            f"[1:a]aresample=48000,atrim={s:.3f}:{e:.3f},asetpts=PTS-STARTPTS,"
            f"afade=t=in:d={fade},afade=t=out:st={max(0.0, e - s - fade):.3f}:d={fade},"
            f"volume=1.25,adelay={int(s * 1000)}:all=1[vo];"
            f"[base][vo]amix=inputs=2:duration=first:normalize=0[a]"
        )
        subprocess.run([
            "ffmpeg", "-v", "error", "-y", "-i", str(base_mp4), "-i", str(vo_low_mp4),
            "-filter_complex", filt, "-map", "0:v", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(tmp)
        ], check=True)
        tmp.replace(out_mp4)
        return

    vocals = out_mp4.with_suffix(".vocals.wav")
    vo_split.demucs_vocals(vo_low_mp4, vocals)
    duck_expr = "+".join([f"between(t,{s:.3f},{e:.3f})" for s, e in windows])
    parts, labels = [], []
    fade = 0.10
    for i, (s, e) in enumerate(windows):
        parts.append(
            f"[1:a]aresample=48000,atrim={s:.3f}:{e:.3f},asetpts=PTS-STARTPTS,"
            f"afade=t=in:d={fade},afade=t=out:st={max(0.0, e - s - fade):.3f}:d={fade},"
            f"volume=1.85,adelay={int(s * 1000)}:all=1[v{i}]"
        )
        labels.append(f"[v{i}]")
    filt = (
        ";".join(parts)
        + f";[0:a]aresample=48000,volume='if(gt({duck_expr},0),0.38,1.0)':eval=frame[base];"
        + f"[base]{''.join(labels)}amix=inputs={len(windows) + 1}:duration=first:normalize=0[a]"
    )
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-i", str(base_mp4), "-i", str(vocals),
        "-filter_complex", filt, "-map", "0:v", "-map", "[a]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(tmp)
    ], check=True)
    tmp.replace(out_mp4)


def place_vo_segments(
    base_mp4: Path,
    vo_mp4: Path,
    segments: list,
    out_mp4: Path,
    base_duck: float = 0.30,
    vo_gain: float = 1.85,
    raw_slice: bool = False,
):
    """Place [(src_start, src_end, dst_start), ...] from vo_mp4 onto base_mp4 with ducking (Demucs vocals or direct raw slice)."""
    tmp = out_mp4.with_suffix(".tmp.mp4")
    if raw_slice:
        vo_src = vo_mp4
    else:
        vocals = vo_mp4.with_suffix(".vocals.wav")
        if not vocals.is_file():
            vo_split.demucs_vocals(vo_mp4, vocals)
        vo_src = vocals
    duck_terms = []
    parts, labels = [], []
    fade = 0.08
    for i, (ss, se, ds) in enumerate(segments):
        dur = max(0.05, se - ss)
        de = ds + dur
        duck_terms.append(f"between(t,{ds:.3f},{de:.3f})")
        parts.append(
            f"[1:a]aresample=48000,atrim={ss:.3f}:{se:.3f},asetpts=PTS-STARTPTS,"
            f"afade=t=in:d={fade},afade=t=out:st={max(0.0, dur - fade):.3f}:d={fade},"
            f"volume={vo_gain},adelay={int(round(ds * 1000))}:all=1[v{i}]"
        )
        labels.append(f"[v{i}]")
    duck_expr = "+".join(duck_terms)
    filt = (
        ";".join(parts)
        + f";[0:a]aresample=48000,volume='if(gt({duck_expr},0),{base_duck},1.0)':eval=frame[base];"
        + f"[base]{''.join(labels)}amix=inputs={len(segments) + 1}:duration=first:normalize=0[a]"
    )
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-i", str(base_mp4), "-i", str(vo_src),
        "-filter_complex", filt, "-map", "0:v", "-map", "[a]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(tmp)
    ], check=True)
    tmp.replace(out_mp4)


def ensure_1k_image(path: Path, cache_dir: Path) -> Path:
    path = Path(path)
    with Image.open(path) as im:
        w, h = im.size
    if max(w, h) <= 1024:
        return path
    dst = cache_dir / f"{path.stem}_1k.png"
    if not dst.is_file():
        compress_image_to_1k(path, dst, max_side=1024)
    with Image.open(dst) as im2:
        assert max(im2.size) <= 1024, f"Image still > 1K: {dst} {im2.size}"
    return dst


def call_pika_5090(out_mp4: Path, prompt: str, duration: int, seed: int, ratio: str,
                   resolution: str, ref_images: list, ref_audios: list) -> dict:
    out_mp4 = Path(out_mp4)
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    part = out_mp4.with_suffix(".mp4.part")
    key = API_5090_KEY_FILE.read_text(encoding="utf-8").strip()

    for img in ref_images:
        with Image.open(img) as im:
            if max(im.size) > 1024:
                raise ValueError(f"Refusing to upload >1K image to video model: {img} ({im.size})")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        hdr = tmp_dir / "auth.hdr"
        hdr.touch(mode=0o600)
        hdr.write_text(f"Authorization: Bearer {key}\n", encoding="utf-8")
        pfile = tmp_dir / "prompt.txt"
        pfile.write_text(prompt, encoding="utf-8")
        resp_hdr = tmp_dir / "resp.hdr"

        cmd = [
            "curl", "-sS", "--max-time", "1800",
            "-H", f"@{hdr}",
            "-D", str(resp_hdr),
            "-o", str(part),
            "-w", "%{http_code}",
            "-F", "model=MiniMax-H3",
            "-F", f"prompt=<{pfile}",
            "-F", f"duration={duration}",
            "-F", f"seed={seed}",
            "-F", f"resolution={resolution}",
            "-F", f"ratio={ratio}",
            "-F", "turbo=false",
        ]
        for r in ref_images:
            cmd += ["-F", f"reference_image=@{r}"]
        for a in ref_audios:
            cmd += ["-F", f"reference_audio=@{a}"]
        cmd.append(API_5090_URL)

        t0 = time.time()
        proc = subprocess.run(cmd, capture_output=True, text=True)
        elapsed = round(time.time() - t0, 2)
        headers = {}
        if resp_hdr.is_file():
            for line in resp_hdr.read_text(encoding="utf-8", errors="replace").splitlines():
                k, sep, v = line.partition(":")
                if sep and k.lower().startswith("x-"):
                    headers[k.strip()] = v.strip()

    code = proc.stdout.strip()
    if code != "200":
        err_body = part.read_text(encoding="utf-8", errors="replace")[:500] if part.is_file() else ""
        part.unlink(missing_ok=True)
        raise RuntimeError(f"Pika 5090 HTTP {code}: {err_body} {proc.stderr[-300:]}")

    model_hdr = next((v for k, v in headers.items() if k.lower() == "x-model"), "")
    if model_hdr != "Pika-H3-Flex":
        raise RuntimeError(f"Expected X-Model=Pika-H3-Flex, got {model_hdr!r}")

    part.replace(out_mp4)
    probe = json.loads(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(out_mp4)],
        text=True,
    ))
    vstream = next(s for s in probe["streams"] if s["codec_type"] == "video")
    has_audio = any(s["codec_type"] == "audio" for s in probe["streams"])
    meta = {
        "headers": headers,
        "elapsed_s": elapsed,
        "seed": seed,
        "requested_duration": duration,
        "actual_duration": round(float(probe["format"]["duration"]), 3),
        "width": vstream["width"],
        "height": vstream["height"],
        "has_audio": has_audio,
        "ref_images_1k": [str(p) for p in ref_images],
        "ref_audios": [str(p) for p in ref_audios],
    }
    out_mp4.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def run_shot(spec: dict, outdir: Path, cache_1k: Path, resolution: str = "480p", force: bool = False) -> dict:
    sid = spec["id"]
    shot_dir = outdir / sid
    shot_dir.mkdir(parents=True, exist_ok=True)
    final_mp4 = shot_dir / "video.mp4"
    final_meta = shot_dir / "video.json"

    if final_mp4.is_file() and final_meta.is_file() and not force:
        print(f"[skip] {sid} already generated -> {final_mp4}", flush=True)
        return json.loads(final_meta.read_text(encoding="utf-8"))

    # Lint prompts for zero character appearance descriptions
    issues = lint_zero_appearance(spec["prompt"], sid)
    if spec.get("vo_split") and spec["vo_split"].get("prompt_novo"):
        issues.extend(lint_zero_appearance(spec["vo_split"]["prompt_novo"], f"{sid}:novo"))
    if issues:
        raise ValueError("\n".join(issues))

    refs_1k = [ensure_1k_image(Path(p), cache_1k) for p in spec["ref_images"]]
    audios = [Path(p) for p in spec.get("ref_audios", [])]
    ratio = spec.get("aspect_ratio", "9:16")
    duration = int(spec["duration"])
    seed = int(spec["seed"])

    if spec.get("vo_split"):
        vs = spec["vo_split"]
        novo_mp4 = shot_dir / "video_novo.mp4"
        vo_low_mp4 = shot_dir / "vo_368p.mp4"
        print(f"[start+vo_split] {sid} ({duration}s, {resolution}, {ratio}, refs={len(refs_1k)}, audios={len(audios)})", flush=True)
        old_ckpt = vo_split.LOWRES_CHECKPOINT
        vo_split.LOWRES_CHECKPOINT = ""  # Use 4070 default Pika-H3-Flex
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                if novo_mp4.is_file() and novo_mp4.with_suffix(".json").is_file() and not force:
                    fut_main = pool.submit(lambda: json.loads(novo_mp4.with_suffix(".json").read_text(encoding="utf-8")))
                else:
                    fut_main = pool.submit(
                        call_pika_5090, novo_mp4, vs["prompt_novo"], duration, seed, ratio, resolution, refs_1k, []
                    )
                fut_vo = pool.submit(
                    vo_split.h3_lowres, vo_low_mp4, spec["prompt"], duration, seed, ratio, "reference", refs_1k, None, None, audios
                )
                meta = fut_main.result()
                vo_meta = fut_vo.result()
        finally:
            vo_split.LOWRES_CHECKPOINT = old_ckpt

        mix_vo_upgraded(novo_mp4, vo_low_mp4, vs["windows"], final_mp4, mode=vs.get("mode", "demucs_duck"))
        meta["vo_split_applied"] = True
        meta["vo_windows"] = vs["windows"]
        meta["vo_368p_headers"] = vo_meta
        final_meta.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[done+vo_split] {sid} in {meta['elapsed_s']}s -> {meta['width']}x{meta['height']} ({meta['actual_duration']}s)", flush=True)
        return meta

    print(f"[start] {sid} ({duration}s, {resolution}, {ratio}, refs={len(refs_1k)}, audios={len(audios)})", flush=True)
    meta = call_pika_5090(final_mp4, spec["prompt"], duration, seed, ratio, resolution, refs_1k, audios)
    print(f"[done] {sid} in {meta['elapsed_s']}s -> {meta['width']}x{meta['height']} ({meta['actual_duration']}s)", flush=True)
    return meta


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("plan_json", type=Path, help="JSON list of shot generation specs")
    ap.add_argument("--outdir", required=True, type=Path)
    ap.add_argument("--resolution", default="480p", choices=("368p", "480p", "512p", "768p"))
    ap.add_argument("--only", action="append", default=[], help="Run only specified shot IDs")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--lint-only", action="store_true")
    args = ap.parse_args()

    specs = json.loads(args.plan_json.read_text(encoding="utf-8"))
    if args.only:
        only_set = set(args.only)
        specs = [s for s in specs if s["id"] in only_set]

    all_issues = []
    for s in specs:
        all_issues.extend(lint_zero_appearance(s["prompt"], s["id"]))
        if s.get("vo_split") and s["vo_split"].get("prompt_novo"):
            all_issues.extend(lint_zero_appearance(s["vo_split"]["prompt_novo"], f"{s['id']}:novo"))
    if all_issues:
        for iss in all_issues:
            print("LINT ERROR:", iss, file=sys.stderr)
        sys.exit(2)
    if args.lint_only:
        print(f"LINT OK: {len(specs)} shots passed zero-appearance check.")
        return

    cache_1k = args.outdir / "inputs_1k"
    cache_1k.mkdir(parents=True, exist_ok=True)
    summary = {}
    for s in specs:
        summary[s["id"]] = run_shot(s, args.outdir, cache_1k, resolution=args.resolution, force=args.force)
    (args.outdir / "run_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"ALL DONE: {len(summary)} shots completed.")


if __name__ == "__main__":
    main()
