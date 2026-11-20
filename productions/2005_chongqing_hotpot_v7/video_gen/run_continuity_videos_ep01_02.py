#!/usr/bin/env python3
"""
Execute Episode 1 & Episode 2 Scene-Master-Plate continuity video regeneration:
  1. Concurrently on Spark `MiniMax H3 Image`: fix `2-1-04` (left palm extended toward screen-left)
     and `2-1-11` (standing upright posture matching `2-1_post_watch_master`).
  2. Concurrently on Local 5090 `Pika-H3-Flex` (`480p` `9:16`):
     - Promote verified `1-3-09_master_anchored.mp4` -> `takes_ep01/1-3-09/video.mp4`
     - Regenerate Ep 1 shots: `1-1-04`, `1-1-10`, `1-1-13`, `1-3-15`, `1-3-18`, `1-3-21` (reusing verified `vo_short_vocals.wav` `[0.28..4.94s]`)
     - Regenerate Ep 2 shots: `2-3-11`, then (once Spark thread finishes) `2-1-04`, `2-1-08`, `2-1-11`, `2-1-14`
  3. Render `0.5s` diagnostic strips + `ep01_transitions_v2.jpg` & `ep02_transitions_v2.jpg` side-by-side sheets.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from PIL import Image, ImageDraw

SKILL_SCRIPTS = Path("/home/zhongwenyu/project/ai-director-train/.agents/skills/hit-video/scripts")
WORK_DIR = Path("/home/zhongwenyu/project/ai-director-train/productions/2005_chongqing_hotpot_v7/video_gen")
for p in (str(SKILL_SCRIPTS), str(WORK_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import check_transitions  # noqa: E402
import pika_runner  # noqa: E402
from build_and_run_ep01_03_v7 import make_half_sec_strip  # noqa: E402
from spark_h3_image import generate_spark_h3_image  # noqa: E402

KF_2K = WORK_DIR / "keyframes_2k"
KF_1K = WORK_DIR / "keyframes_1k"
CACHE_1K = WORK_DIR / "cache_1k"
TAKES_EP1 = WORK_DIR / "takes_ep01"
TAKES_EP2 = WORK_DIR / "takes_ep02"
DIAG_DIR = WORK_DIR / "diag_strips"
AUDIT_DIR = WORK_DIR / "transition_audit"


def fix_spark_2104_2111() -> Path:
    amap = json.loads((WORK_DIR / "asset_map.json").read_text(encoding="utf-8"))
    c_ye = amap["叶寻"]["front_1k"]
    c_lin = amap["林双双"]["front_1k"]
    c_chu = amap["楚南"]["front_1k"]
    staged: set[str] = set()

    print("[spark-fix] Regenerating 2-1-04 (left palm extended toward screen-left) ...", flush=True)
    generate_spark_h3_image(
        prompt=(
            "The weathered wooden shop doorway, two flat grey stone steps, and sunlit Chongqing bluestone lane in <Picture 1> are <Subject 1>. "
            "The young woman in <Picture 2> is <Subject 2>. The young man with army-green canvas backpack in <Picture 3> is <Subject 3>. "
            "The target image shows a medium close-up framed from the exact doorway blocking of <Picture 1>; "
            "<Subject 1> is partially preserved, keeping the exact weathered wooden door panels behind <Subject 2>; "
            "<Subject 2> and <Subject 3> are fully preserved in appearance and outfit. "
            "Standing upright on the upper stone step on screen-right facing screen-left toward <Subject 3>, "
            "<Subject 2> grips <Subject 3>'s taut army-green canvas backpack strap at shoulder height with her right hand on the left edge of the frame, "
            "while extending her open left hand forward toward screen-left (palm facing up between her and <Subject 3> on screen-left, never reaching toward screen-right) "
            "with a haughty lifted chin. Crisp 35mm live-action cinema photography, zero text or signboards."
        ),
        out_path=KF_2K / "2-1-04_2k.png",
        out_1k_path=KF_1K / "2-1-04_1k.png",
        ref_images=[KF_2K / "2-1-01_2k.png", c_lin, c_ye],
        aspect_ratio="9:16",
        seed=2144,
        steps=6,
        staged_cache=staged,
    )
    print("[spark-fix] DONE 2-1-04", flush=True)

    print("[spark-fix] Regenerating 2-1-11 (standing upright on upper stone step) ...", flush=True)
    generate_spark_h3_image(
        prompt=(
            "The weathered wooden shop doorway in <Picture 1> is <Subject 1>. "
            "The young woman standing upright in <Picture 2> is <Subject 2>. "
            "The young man in floral shirt and dark blazer leaning at the right doorframe in <Picture 3> is <Subject 3>. "
            "The target image shows a waist-up standing medium close-up of <Subject 2> standing tall on her feet in front of <Subject 1> "
            "with <Subject 3> softly blurred leaning at the right-rear wooden doorframe; "
            "<Subject 1> is partially preserved in wooden doorway background and midday light; "
            "<Subject 2> and <Subject 3> are fully preserved in facial features, hairstyle, and outfit. "
            "Standing fully upright (never sitting or crouching, skirt hanging straight while standing), <Subject 2> clutches the small black plastic digital wristwatch "
            "against her chest with her left hand while turning her head urgently over her right shoulder to look up at <Subject 3>. "
            "Crisp 35mm live-action cinema photography, zero text or signboards."
        ),
        out_path=KF_2K / "2-1-11_2k.png",
        out_1k_path=KF_1K / "2-1-11_1k.png",
        ref_images=[KF_2K / "2-1_post_watch_master_2k.png", c_lin, c_chu],
        aspect_ratio="9:16",
        seed=2119,
        steps=6,
        staged_cache=staged,
    )
    print("[spark-fix] DONE 2-1-11", flush=True)

    sheet = Image.new("RGB", (720, 640), (18, 18, 18))
    draw = ImageDraw.Draw(sheet)
    for i, stem in enumerate(["2-1-04", "2-1-11"]):
        im = Image.open(KF_2K / f"{stem}_2k.png").convert("RGB").resize((360, 640))
        sheet.paste(im, (i * 360, 0))
        draw.rectangle([i * 360, 0, i * 360 + 160, 28], fill=(0, 0, 0))
        draw.text((i * 360 + 8, 6), f"{stem} (fixed)", fill=(120, 255, 120))
    out = AUDIT_DIR / "spark_fix_2104_2111_sheet.jpg"
    sheet.save(out, quality=92)
    return out


def backup_take(takes_dir: Path, sid: str) -> None:
    bdir = AUDIT_DIR / "backup_v1_takes" / sid
    sdir = takes_dir / sid
    if sdir.is_dir() and not bdir.exists():
        bdir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(sdir, bdir)


def run_1_3_21_with_verified_vo(spec: dict) -> None:
    sid = "1-3-21"
    backup_take(TAKES_EP1, sid)
    sdir = TAKES_EP1 / sid
    base_mp4 = sdir / "video_base.mp4"
    final_mp4 = sdir / "video.mp4"
    final_meta = sdir / "video.json"
    vo_vocals = sdir / "vo_short_vocals.wav"
    if not vo_vocals.is_file():
        raise FileNotFoundError(f"Missing verified VO vocals: {vo_vocals}")

    refs_1k = [pika_runner.ensure_1k_image(Path(p), CACHE_1K) for p in spec["ref_images"]]
    audios = [Path(p) for p in spec.get("ref_audios", [])]
    print(f"[5090] Regenerating {sid} base video (15s 480p) + muxing verified VO [0.28..4.94s] ...", flush=True)
    meta = pika_runner.call_pika_5090(
        base_mp4, spec["prompt"], int(spec["duration"]), int(spec["seed"]), "9:16", "480p", refs_1k, audios
    )

    ss, se = 0.28, 4.94
    ratio = 1.10
    eff_dur = (se - ss) / ratio
    dst_start = 3.00
    duck_lvl = 0.22
    start_mute = dst_start - 0.08
    end_mute = dst_start + eff_dur + 0.12
    tmp = final_mp4.with_suffix(".tmp.mp4")
    filt = (
        f"[0:a]aresample=48000,volume='if(between(t,{start_mute:.3f},{end_mute:.3f}),{duck_lvl:.2f},1.0)':eval=frame[base];"
        f"[1:a]aresample=48000,atrim={ss:.3f}:{se:.3f},asetpts=PTS-STARTPTS,atempo={ratio:.3f},"
        f"afade=t=in:d=0.06,afade=t=out:st={max(0.0, eff_dur - 0.08):.3f}:d=0.08,"
        f"volume=1.85,adelay={int(round(dst_start * 1000))}:all=1[vo];"
        f"[base][vo]amix=inputs=2:duration=first:normalize=0[a]"
    )
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-y", "-i", str(base_mp4), "-i", str(vo_vocals),
            "-filter_complex", filt, "-map", "0:v", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(tmp),
        ],
        check=True,
    )
    tmp.replace(final_mp4)
    meta["vo_custom_applied"] = {"src": [ss, se], "atempo": ratio, "eff_dur": round(eff_dur, 3), "dst_start": dst_start}
    final_meta.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    make_half_sec_strip(final_mp4, sid, DIAG_DIR / f"{sid}_0.5s.jpg")
    print(f"[5090] DONE {sid}", flush=True)


def render_pair_grid(videos: list[tuple[str, Path]], out_jpg: Path) -> None:
    """Render compact 3-column [Shot_N END | Shot_N+1 START] grid matching ep01_transitions.jpg."""
    pairs = len(videos) - 1
    cols = 3
    rows = (pairs + cols - 1) // cols
    pw, ph = 300, 534
    cell_w, cell_h = pw * 2 + 12, ph + 34
    canvas = Image.new("RGB", (cols * cell_w, rows * cell_h), (14, 14, 18))
    draw = ImageDraw.Draw(canvas)
    resample = getattr(Image, "Resampling", Image).LANCZOS

    for idx in range(pairs):
        id_a, mp4_a = videos[idx]
        id_b, mp4_b = videos[idx + 1]
        dur_a = check_transitions.probe_duration(mp4_a)
        fa = AUDIT_DIR / f"_tmp_v2_{id_a}_end.png"
        fb = AUDIT_DIR / f"_tmp_v2_{id_b}_start.png"
        check_transitions.extract_frame(mp4_a, max(0.0, dur_a - 0.08), fa)
        check_transitions.extract_frame(mp4_b, 0.05, fb)

        r, c = divmod(idx, cols)
        ox, oy = c * cell_w, r * cell_h
        draw.text((ox + 8, oy + 8), f"{idx + 1}. {id_a} END  -->  {id_b} START", fill=(255, 220, 100))
        with Image.open(fa) as ima, Image.open(fb) as imb:
            canvas.paste(ima.convert("RGB").resize((pw, ph), resample), (ox + 3, oy + 30))
            canvas.paste(imb.convert("RGB").resize((pw, ph), resample), (ox + pw + 7, oy + 30))
        draw.line([(ox + pw + 5, oy + 30), (ox + pw + 5, oy + 30 + ph)], fill=(255, 80, 80), width=2)
        fa.unlink(missing_ok=True)
        fb.unlink(missing_ok=True)

    canvas.save(out_jpg, quality=92)
    print(f"Saved compact pair transition grid -> {out_jpg}", flush=True)


def main() -> int:
    ep1_plan = {s["id"]: s for s in json.loads((WORK_DIR / "ep01_v7_plan.json").read_text(encoding="utf-8"))}
    ep2_plan = {s["id"]: s for s in json.loads((WORK_DIR / "ep02_v7_plan.json").read_text(encoding="utf-8"))}

    with ThreadPoolExecutor(max_workers=1) as spark_pool:
        spark_fut = spark_pool.submit(fix_spark_2104_2111)

        # 0. Promote already verified 1-3-09_master_anchored.mp4
        backup_take(TAKES_EP1, "1-3-09")
        shutil.copy2(AUDIT_DIR / "1-3-09_master_anchored.mp4", TAKES_EP1 / "1-3-09" / "video.mp4")
        shutil.copy2(AUDIT_DIR / "1-3-09_master_anchored.json", TAKES_EP1 / "1-3-09" / "video.json")
        make_half_sec_strip(TAKES_EP1 / "1-3-09" / "video.mp4", "1-3-09", DIAG_DIR / "1-3-09_0.5s.jpg")
        print("[promote] 1-3-09_master_anchored.mp4 -> takes_ep01/1-3-09/video.mp4", flush=True)

        # 1. Run Ep 1 non-VO continuity shots on 5090
        for sid in ["1-1-04", "1-1-10", "1-1-13", "1-3-15", "1-3-18"]:
            backup_take(TAKES_EP1, sid)
            print(f"[5090] Regenerating Ep1 {sid} ...", flush=True)
            pika_runner.run_shot(ep1_plan[sid], TAKES_EP1, CACHE_1K, resolution="480p", force=True)
            make_half_sec_strip(TAKES_EP1 / sid / "video.mp4", sid, DIAG_DIR / f"{sid}_0.5s.jpg")

        # 2. Run 1-3-21 on 5090 + verified VO mux
        run_1_3_21_with_verified_vo(ep1_plan["1-3-21"])

        # 3. Run Ep 2 2-3-11 (keyframe already verified)
        backup_take(TAKES_EP2, "2-3-11")
        print("[5090] Regenerating Ep2 2-3-11 ...", flush=True)
        pika_runner.run_shot(ep2_plan["2-3-11"], TAKES_EP2, CACHE_1K, resolution="480p", force=True)
        make_half_sec_strip(TAKES_EP2 / "2-3-11" / "video.mp4", "2-3-11", DIAG_DIR / "2-3-11_0.5s.jpg")

        # 4. Wait for Spark 2-1-04 & 2-1-11 fixes, then run Ep 2 2-1 shots on 5090
        fix_sheet = spark_fut.result()
        print(f"[spark-fix] Verified sheet ready: {fix_sheet}", flush=True)

        for sid in ["2-1-04", "2-1-08", "2-1-11", "2-1-14"]:
            backup_take(TAKES_EP2, sid)
            print(f"[5090] Regenerating Ep2 {sid} ...", flush=True)
            pika_runner.run_shot(ep2_plan[sid], TAKES_EP2, CACHE_1K, resolution="480p", force=True)
            make_half_sec_strip(TAKES_EP2 / sid / "video.mp4", sid, DIAG_DIR / f"{sid}_0.5s.jpg")

    # 5. Build full Episode 1 & Episode 2 v2 transition sheets
    ep1_vids = [(sid, TAKES_EP1 / sid / "video.mp4") for sid in ep1_plan]
    ep2_vids = [(sid, TAKES_EP2 / sid / "video.mp4") for sid in ep2_plan]
    render_pair_grid(ep1_vids, AUDIT_DIR / "ep01_transitions_v2.jpg")
    render_pair_grid(ep2_vids, AUDIT_DIR / "ep02_transitions_v2.jpg")
    check_transitions.build_transition_sheet(ep1_vids, AUDIT_DIR / "ep01_transitions_4col_v2.jpg")
    check_transitions.build_transition_sheet(ep2_vids, AUDIT_DIR / "ep02_transitions_4col_v2.jpg")
    print("ALL EP1 & EP2 CONTINUITY VIDEOS + V2 TRANSITION SHEETS COMPLETE!", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
