#!/home/zhongwenyu/data/anaconda3/bin/python3
"""
Generalizable Two-Stage High-Distinctiveness Identity & Set Asset Rebuilder (`trainer/rebuild_identity_assets.py` v3.1).

Prevents "AI stock-face homogenization" across ALL genres/dramas without overfitting:
  1. Slices a native-resolution (720p/1080p) 46s inspection clip from `source_mp4` AND builds a 36-tile
     timestamp-stamped clean contact sheet (`contact_sheet_36.jpg`, pre-cropping top watermarks & bottom subtitles)
     so `gemini-4-argon-medium` scans EVERY close-up across the entire 46s timeline rather than stopping at t=1s!
  2. Locates per character:
     - `face_cu_frame_s` + `face_cu_bbox_norm`: Largest-pixel-area calm/closed-lip CLOSE-UP frame;
     - `second_angle_frame_s` + `second_angle_bbox_norm`: Complementary clean calm angle of the SAME actor;
     - `bust_frame_s` + `bust_bbox_norm`: Waist/chest-up frame showing full hair silhouette + collar/outfit;
     - `distinctive_facial_traits_en`: Objective bone ratios, chin/jaw taper, eye/canthus tilt, eyelid/aegyo-sal,
       nose contour, beauty marks/moles, lip Cupid's-bow shape, makeup undertone, bang strand sparsity, earrings/glasses.
  3. Two-Stage `Spark MiniMax H3 Image` at calibrated native `steps=6` (`euler + simple, cfg=1.0` — avoiding
     12-step over-baked wet-hair artifacts!):
     - Stage A (`{CHR}_face_cu_1k.png`, `1:1` 1024x1024): Reconstructs 100% of distinctive close-up facial
       geometry, clean dry silky hair, and exact collar from `[cu_crop, second_crop, bust_crop]`.
     - Stage B (`{CHR}_side45_neutral_1k.png` `1:1` + `{CHR}_front_1k.png` `9:16`): Anchored on `{CHR}_face_cu_1k.png`
       preserving exact collar/outfit and facial distinctiveness, then composited into `{CHR}_neutral_multiview_1k.png`!
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

from PIL import Image, ImageDraw

TRAIN_ROOT = Path("/home/zhongwenyu/project/ai-director-train")
BENCH_ROOT = TRAIN_ROOT / "corpus" / "video_bench"

for p in (
    str(TRAIN_ROOT / "trainer"),
    str(TRAIN_ROOT / "judge"),
    str(TRAIN_ROOT / ".agents" / "skills" / "hit-video" / "scripts"),
):
    if p not in sys.path:
        sys.path.insert(0, p)

import native_video_engine as NVE  # noqa: E402
import prepare_video_bench as PVB  # noqa: E402
import video_arena_judge as VAJ  # noqa: E402
from spark_h3_image import generate_spark_h3_image  # noqa: E402

SOURCE_MAP: Dict[str, Dict[str, Any]] = {s["case_id"]: s for s in PVB.BENCH_SOURCES}

LOCATE_V3_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "scene_frame_s": {"type": "number"},
        "character_profiles": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "role_id": {"type": "string"},
                    "face_cu_frame_s": {"type": "number"},
                    "face_cu_bbox_norm": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 4,
                        "maxItems": 4,
                    },
                    "second_angle_frame_s": {"type": "number"},
                    "second_angle_bbox_norm": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 4,
                        "maxItems": 4,
                    },
                    "bust_frame_s": {"type": "number"},
                    "bust_bbox_norm": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 4,
                        "maxItems": 4,
                    },
                    "distinctive_facial_traits_en": {"type": "string"},
                },
                "required": [
                    "role_id",
                    "face_cu_frame_s",
                    "face_cu_bbox_norm",
                    "second_angle_frame_s",
                    "second_angle_bbox_norm",
                    "bust_frame_s",
                    "bust_bbox_norm",
                    "distinctive_facial_traits_en",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["scene_frame_s", "character_profiles"],
    "additionalProperties": False,
}


def _extract_frame_png(mp4_path: Path, t_sec: float, out_png: Path) -> Path:
    out_png.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-ss", f"{max(0.0, t_sec):.3f}", "-i", str(mp4_path), "-frames:v", "1", str(out_png)],
        check=True,
    )
    return out_png


def _crop_clean_box(frame_png: Path, bbox: List[float], out_png: Path, min_y_top: float = 0.09, max_y_bot: float = 0.83) -> Path:
    im = Image.open(frame_png).convert("RGB")
    w, h = im.size
    x1, y1, x2, y2 = [float(v) for v in bbox]
    x1 = max(0.0, min(0.82, x1))
    y1 = max(min_y_top, min(0.70, y1))  # Strictly exclude top title watermark!
    x2 = max(x1 + 0.16, min(1.0, x2))
    y2 = max(y1 + 0.18, min(max_y_bot, y2))  # Strictly exclude bottom burned-in subtitles!
    im.crop((int(x1 * w), int(y1 * h), int(x2 * w), int(y2 * h))).save(out_png, format="PNG")
    return out_png


def _build_contact_sheet_36(mp4_path: Path, vid_dur: float, out_jpg: Path) -> Path:
    """Build a 6x6 timestamped contact sheet across the full duration so the locator sees ALL close-ups!"""
    cols, rows = 6, 6
    n = cols * rows
    tw, th = 360, 210
    sheet = Image.new("RGB", (cols * tw, rows * th), (16, 16, 16))
    draw = ImageDraw.Draw(sheet)
    tmp_dir = out_jpg.parent / "_cs_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        t = round((i + 0.35) * (vid_dur / n), 2)
        fp = _extract_frame_png(mp4_path, t, tmp_dir / f"f_{i:02d}.png")
        im = Image.open(fp).convert("RGB")
        w, h = im.size
        # Pre-strip top 9% watermark & bottom 17% subtitle band on tile preview
        im_c = im.crop((0, int(h * 0.09), w, int(h * 0.83))).resize((tw - 4, th - 4), getattr(Image, "LANCZOS", 1))
        cx, cy = (i % cols) * tw + 2, (i // cols) * th + 2
        sheet.paste(im_c, (cx, cy))
        label = f"t={t:.1f}s"
        draw.rectangle([cx + 4, cy + 4, cx + 88, cy + 26], fill=(0, 0, 0))
        draw.text((cx + 8, cy + 7), label, fill=(255, 235, 60))
        fp.unlink(missing_ok=True)
    try:
        tmp_dir.rmdir()
    except OSError:
        pass
    sheet.save(out_jpg, format="JPEG", quality=90)
    return out_jpg


def rebuild_case_assets(spec_path: Path, force: bool = False, rebuild_scene: bool = False) -> Dict[str, Any]:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    cid = spec["case_id"]
    case_dir = spec_path.parent
    gold_dir = case_dir / "gold_sealed"
    crops_dir = gold_dir / "_crops_v3"
    assets_dir = case_dir / "assets"
    marker = assets_dir / ".identity_rebuilt_v31_facefirst"
    if marker.is_file() and not force:
        print(f"[skip] {cid} already rebuilt with v3.1 face-first pipeline")
        return {"case_id": cid, "status": "skipped"}

    crops_dir.mkdir(parents=True, exist_ok=True)

    src_cfg = SOURCE_MAP.get(cid)
    inspect_mp4 = crops_dir / "native_res_inspect.mp4"
    if src_cfg and Path(src_cfg["source_mp4"]).is_file():
        w_st = max(0.0, float(src_cfg["window_start"]) - 4.0)
        w_dur = 46.0
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error",
                "-ss", f"{w_st:.2f}", "-t", f"{w_dur:.2f}",
                "-i", src_cfg["source_mp4"],
                "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
                "-an", str(inspect_mp4),
            ],
            check=True,
        )
    else:
        inspect_mp4 = gold_dir / "window_25s.mp4"

    pr = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_format", "-of", "json", str(inspect_mp4)], text=True))
    vid_dur = max(1.0, float(pr["format"]["duration"]) - 0.15)
    cs_jpg = _build_contact_sheet_36(inspect_mp4, vid_dur, crops_dir / "contact_sheet_36.jpg")

    char_desc_lines = [
        f"- `{c['role_id']}`（{c['display_name']}，{c.get('gender', '')}）：{c['neutral_visual_bio']}"
        for c in spec.get("characters", [])
    ]
    locate_prompt = (
        f"请结合 36 格时间戳索引图 `Contact_Sheet_36.jpg` 与完整高清源视频 `Native_Source.mp4`（总长 {vid_dur:.1f}s，请务必扫完整个 0s~{vid_dur:.1f}s 全程，绝不允许偷懒只看前 2 秒远景！），精准提取每位角色的**标志性个人骨相五官辨识度特征**与**最清晰的特写参考帧**：\n\n"
        f"【场景环境】：{spec.get('setting_summary', '')}\n"
        f"【座位/站位关系】：{spec.get('initial_blocking', '')}\n"
        "【角色清单】：\n" + "\n".join(char_desc_lines) + "\n\n"
        "【硬性提取要求（必须保留极强的演员个人辨识度，严禁退化成网红大众脸！）】：\n"
        "1. `face_cu_frame_s` + `face_cu_bbox_norm`：从全片 `0s~末秒` 中挑选该角色**单人特写（CU）或中近景（MCU）中脸部像素占比最大、对焦最清晰、且嘴唇自然闭合或平静（严禁选张嘴说话、露齿笑或闭眼瞬间！）的最佳特写帧**！注意 `bbox_norm` `[x1,y1,x2,y2]` 为原始完整画幅归一化坐标（`0~1`），**必须严密只框选该角色本人头部与衣领，绝对禁止把邻座其他角色的脸部、肩膀或深浅色衣服框入画面造成串衣**，并避开顶部 `y < 0.09` 水印与底部 `y > 0.83` 字幕。\n"
        "2. `second_angle_frame_s` + `second_angle_bbox_norm`：挑选同一角色在另一秒的清晰平静正脸或微侧角度特写/近景帧（若第 1 帧眼神偏侧，第 2 帧优先选正视前方或互补角度），用于交叉锁定真实三维骨相！\n"
        "3. `bust_frame_s` + `bust_bbox_norm`：挑选能完整看清该角色发型轮廓与上半身衣领/外套款式的清晰半身帧。\n"
        "4. `distinctive_facial_traits_en`（英文，50~90词）：客观如实描写该演员在源片中的真实个体外貌特征（严禁套用美颜模板或固定审美词汇！）——涵盖真实年龄感与肤色肤质（无论白皙、小麦色、粗粝沧桑、皱纹或疤痕均如实保留）、面部骨骼轮廓比例、眼型眉型与眼神气质、鼻唇形态、面部标志性细节（若有痣、胡茬、酒窝、眼镜、耳饰等如实写出，无则不写）以及真实发型发际线结构！"
    )

    loc = VAJ.call_argon_multimodal(
        locate_prompt,
        [
            {"kind": "image", "path": cs_jpg, "anon_name": "Contact_Sheet_36.jpg", "caption": "全片36格时间戳预览表（先看此表锁定每位角色的最大单人特写秒数！）"},
            {"kind": "video", "path": inspect_mp4, "anon_name": "Native_Source.mp4", "caption": "原生高清源视频"},
        ],
        schema=LOCATE_V3_SCHEMA,
        effort="medium",
        timeout=360,
    )
    (crops_dir / "locate_v31.json").write_text(json.dumps(loc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    ar = spec.get("aspect_ratio", "16:9")
    if rebuild_scene or not (assets_dir / "scene_clean_1k.png").is_file():
        sc_t = min(vid_dur, max(0.05, float(loc.get("scene_frame_s", 1.0))))
        sc_raw = _extract_frame_png(inspect_mp4, sc_t, crops_dir / "scene_frame.png")
        sc_crop = _crop_clean_box(sc_raw, [0.0, 0.09, 1.0, 0.83], crops_dir / "scene_nosub.png", min_y_top=0.09, max_y_bot=0.83)
        sc_out = assets_dir / "scene_clean_1k.png"
        sc_tmp = assets_dir / "scene.raw.png"
        sc_prompt = (
            "The architecture, furniture layout, and cinema lighting in <Picture 1> are <Subject 1>. "
            f"The target image shows an empty photorealistic 35mm cinema set plate ({ar}) of <Subject 1> ({spec.get('setting_summary', '')}), "
            "with all people and text removed. Zero people, zero text, zero watermarks."
        )
        generate_spark_h3_image(prompt=sc_prompt, out_path=sc_tmp, ref_images=[sc_crop], aspect_ratio=ar, seed=202700, steps=6, out_1k_path=sc_out)
        sc_tmp.unlink(missing_ok=True)

    prof_map = {item["role_id"]: item for item in loc.get("character_profiles", [])}
    traits_summary: Dict[str, str] = {}
    for idx, ch in enumerate(spec.get("characters", []), 1):
        rid = ch["role_id"]
        prof = prof_map.get(rid)
        if not prof:
            continue
        ft_cu = min(vid_dur, max(0.05, float(prof["face_cu_frame_s"])))
        ft_s2 = min(vid_dur, max(0.05, float(prof["second_angle_frame_s"])))
        ft_bu = min(vid_dur, max(0.05, float(prof["bust_frame_s"])))
        f_cu_raw = _extract_frame_png(inspect_mp4, ft_cu, crops_dir / f"{rid}_cu_full.png")
        f_s2_raw = _extract_frame_png(inspect_mp4, ft_s2, crops_dir / f"{rid}_s2_full.png")
        f_bu_raw = _extract_frame_png(inspect_mp4, ft_bu, crops_dir / f"{rid}_bust_full.png")
        cu_crop = _crop_clean_box(f_cu_raw, prof["face_cu_bbox_norm"], crops_dir / f"{rid}_face_cu_crop.png")
        s2_crop = _crop_clean_box(f_s2_raw, prof["second_angle_bbox_norm"], crops_dir / f"{rid}_second_crop.png")
        bu_crop = _crop_clean_box(f_bu_raw, prof["bust_bbox_norm"], crops_dir / f"{rid}_bust_crop.png")

        traits = str(prof["distinctive_facial_traits_en"]).strip()
        traits_summary[rid] = traits
        g_word = "woman" if ch.get("gender") == "female" else ("man" if ch.get("gender") == "male" else "person")

        # Stage A: 1:1 High-Token-Density Face Close-Up Anchor at native calibrated `steps=6`!
        cu_out = assets_dir / f"{rid}_face_cu_1k.png"
        cu_tmp = assets_dir / f"{rid}_face_cu.raw.png"
        cu_prompt = (
            f"The {g_word} in <Picture 1>, <Picture 2>, and <Picture 3> is <Subject 1>. "
            "The target image shows a photorealistic 35mm cinema head-and-collar close-up front studio portrait of <Subject 1> looking straight forward into the camera on pure solid white background RGB(255,255,255); "
            f"<Subject 1> is 100% faithfully preserved from <Picture 1> and <Picture 2> in exact individual facial bone geometry, true age and natural skin texture/complexion, eye/brow/nose/lip proportions, and authentic hair structure ({traits}), "
            f"wearing the exact collar and outfit from <Picture 3> ({ch.get('neutral_visual_bio', '')}), "
            "with natural dry hair texture (zero artificial wet clumping), a calm 0% neutral expression, and gently closed lips. Soft even studio portrait lighting, pure white background, zero text."
        )
        print(f"  [spark-v3.1-cu] {cid} :: {rid} (cu_t={ft_cu:.2f}s, s2_t={ft_s2:.2f}s, bust_t={ft_bu:.2f}s)", flush=True)
        generate_spark_h3_image(prompt=cu_prompt, out_path=cu_tmp, ref_images=[cu_crop, s2_crop, bu_crop], aspect_ratio="1:1", seed=202810 + idx * 10 + 1, steps=6, out_1k_path=cu_out)
        cu_tmp.unlink(missing_ok=True)

        # Stage B1: 1:1 45-degree Three-Quarter Side Close-Up anchored on `cu_out` + `cu_crop` + `bu_crop` (`steps=6`, keeping collar!)
        side_out = assets_dir / f"{rid}_side45_neutral_1k.png"
        side_tmp = assets_dir / f"{rid}_side45.raw.png"
        side_prompt = (
            f"The {g_word} in <Picture 1> and <Picture 2> is <Subject 1>. "
            "The target image shows a photorealistic 45-degree three-quarter head-and-collar studio close-up portrait of <Subject 1> on pure solid white background RGB(255,255,255); "
            f"<Subject 1> is 100% preserved from <Picture 1> in exact individual facial bone structure, jawline/profile contour, true age and natural skin texture, eye/nose/lip geometry, hair structure ({traits}), and exact collar/shoulder outfit ({ch.get('neutral_visual_bio', '')}), "
            "with a calm 0% neutral expression and gently closed lips. Pure white background, soft studio lighting, zero text."
        )
        generate_spark_h3_image(prompt=side_prompt, out_path=side_tmp, ref_images=[cu_out, cu_crop], aspect_ratio="1:1", seed=202810 + idx * 10 + 2, steps=6, out_1k_path=side_out)
        side_tmp.unlink(missing_ok=True)

        # Stage B2: 9:16 Waist-Up Front Portrait anchored on `cu_out` + `bu_crop` (`steps=6`)
        front_out = assets_dir / f"{rid}_front_1k.png"
        front_tmp = assets_dir / f"{rid}_front.raw.png"
        front_prompt = (
            f"The {g_word} in <Picture 1> (exact close-up face) and <Picture 2> (exact outfit) is <Subject 1>. "
            "The target image shows a photorealistic waist-up front studio portrait of <Subject 1> standing upright facing straight forward on pure solid white background RGB(255,255,255); "
            f"<Subject 1> is 100% preserved from <Picture 1> in exact individual facial identity, true age, and hair structure ({traits}) and from <Picture 2> in exact outfit ({ch.get('neutral_visual_bio', '')}), "
            "with a calm 0% neutral expression and gently closed lips. Pure white background, soft studio lighting, zero text."
        )
        generate_spark_h3_image(prompt=front_prompt, out_path=front_tmp, ref_images=[cu_out, bu_crop], aspect_ratio="9:16", seed=202810 + idx * 10 + 3, steps=6, out_1k_path=front_out)
        front_tmp.unlink(missing_ok=True)

        # Stage C: Compose 1024x1024 3-panel Neutral Multi-View (`[Left: Waist-Up | TR: 1:1 High-Res Face CU | BR: 1:1 45° Face CU]`)
        mv_out = assets_dir / f"{rid}_neutral_multiview_1k.png"
        mv_out.unlink(missing_ok=True)
        NVE._compose_multiview_sheet(front_out, cu_out, side_out, mv_out)

    (assets_dir / "distinctive_traits.json").write_text(json.dumps(traits_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if inspect_mp4.name == "native_res_inspect.mp4":
        inspect_mp4.unlink(missing_ok=True)
    marker.write_text("ok\n", encoding="utf-8")
    print(f"[REBUILT-V3.1] {cid} high-distinctiveness face-first character sheets complete!", flush=True)
    return {"case_id": cid, "status": "rebuilt_v31"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="Comma-separated case_ids or split names")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    filters = {x.strip() for x in args.only.split(",") if x.strip()}
    spec_paths = sorted(BENCH_ROOT.glob("*/*/beat_spec.json"))
    targets = [
        sp for sp in spec_paths
        if not filters or sp.parent.name in filters or sp.parent.parent.name in filters
    ]
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        for f in cf.as_completed([ex.submit(rebuild_case_assets, sp, args.force) for sp in targets]):
            print(" ->", f.result(), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
