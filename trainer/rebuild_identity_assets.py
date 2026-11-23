#!/home/zhongwenyu/data/anaconda3/bin/python3
"""
Generalizable Primary-Character `Vtrix gpt-image-2.6` Asset Aligner (`trainer/rebuild_identity_assets.py` v4.1).

Strictly upgrades ONLY Primary/Lead Characters (`主要角色`) across the corpus via `Vtrix gpt-image-2.6`
(`gpt_image_2_6_sunburst_edit`), skipping Secondary/Minor Characters (`次要角色`: background bystanders,
vendors, sidekicks `idx >= 2` unless explicitly marked `role_tier == "primary"`).

Zero-Overfitting Guarantees:
  1. Zero drama-specific or archetype-specific beauty/feature words — prompts strictly instruct 1:1 visual
     fidelity to the reference actor frames (`参考图是唯一人物面部骨相、真实年龄肤质、五官比例、妆造发型与服装依据`).
  2. Supports `--out-subdir` (e.g., `assets_vtrix_v4`) for safe non-disruptive staging & visual QA before
     promoting into live `assets/`.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

from PIL import Image, ImageDraw

TRAIN_ROOT = Path("/home/zhongwenyu/project/ai-director-train")
BENCH_ROOT = TRAIN_ROOT / "corpus" / "video_bench"
WORKSTATION_ASSET_SCRIPTS = Path("/home/zhongwenyu/project/ai-director-workstation/skills/asset-image-gen/scripts")

for p in (
    str(TRAIN_ROOT / "trainer"),
    str(TRAIN_ROOT / "judge"),
    str(TRAIN_ROOT / ".agents" / "skills" / "hit-video" / "scripts"),
    str(WORKSTATION_ASSET_SCRIPTS),
):
    if p not in sys.path:
        sys.path.insert(0, p)

from compress_1k import compress_image_to_1k  # noqa: E402
import native_video_engine as NVE  # noqa: E402
import prepare_video_bench as PVB  # noqa: E402
import video_arena_judge as VAJ  # noqa: E402
from vtrix_image import generate_with_fallback as vtrix_generate_with_fallback  # noqa: E402

SOURCE_MAP: Dict[str, Dict[str, Any]] = {s["case_id"]: s for s in PVB.BENCH_SOURCES}

LOCATE_V4_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "character_profiles": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "role_id": {"type": "string"},
                    "face_cu_frame_s": {"type": "number"},
                    "face_cu_bbox_norm": {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4},
                    "second_angle_frame_s": {"type": "number"},
                    "second_angle_bbox_norm": {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4},
                    "bust_frame_s": {"type": "number"},
                    "bust_bbox_norm": {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4},
                },
                "required": [
                    "role_id",
                    "face_cu_frame_s",
                    "face_cu_bbox_norm",
                    "second_angle_frame_s",
                    "second_angle_bbox_norm",
                    "bust_frame_s",
                    "bust_bbox_norm",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["character_profiles"],
    "additionalProperties": False,
}


def is_primary_character(ch: Dict[str, Any], idx: int) -> bool:
    """Primary/Lead roles (`主要角色`) vs Secondary/Minor roles (`次要角色`)."""
    tier = str(ch.get("role_tier") or "").strip().lower()
    if tier in ("primary", "lead", "main"):
        return True
    if tier in ("secondary", "minor", "supporting", "extra"):
        return False
    return idx < 2


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
    y1 = max(min_y_top, min(0.70, y1))
    x2 = max(x1 + 0.16, min(1.0, x2))
    y2 = max(y1 + 0.18, min(max_y_bot, y2))
    im.crop((int(x1 * w), int(y1 * h), int(x2 * w), int(y2 * h))).save(out_png, format="PNG")
    return out_png


def _build_contact_sheet_36(mp4_path: Path, vid_dur: float, out_jpg: Path) -> Path:
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
        im_c = im.crop((0, int(h * 0.09), w, int(h * 0.83))).resize((tw - 4, th - 4), getattr(Image, "LANCZOS", 1))
        cx, cy = (i % cols) * tw + 2, (i // cols) * th + 2
        sheet.paste(im_c, (cx, cy))
        draw.rectangle([cx + 4, cy + 4, cx + 88, cy + 26], fill=(0, 0, 0))
        draw.text((cx + 8, cy + 7), f"t={t:.1f}s", fill=(255, 235, 60))
        fp.unlink(missing_ok=True)
    try:
        tmp_dir.rmdir()
    except OSError:
        pass
    sheet.save(out_jpg, format="JPEG", quality=90)
    return out_jpg


def _vtrix_1k(prompt: str, ref_files: List[Path], aspect_ratio: str, out_1k_png: Path, prefix: str) -> Path:
    raw_png = out_1k_png.with_suffix(".vtrix_raw.png")
    vtrix_generate_with_fallback(
        prompt=prompt,
        out_path=raw_png,
        ref_files=[str(p) for p in ref_files],
        aspect_ratio=aspect_ratio,
        resolution="1K",
        quality="high",
        complexity="high",
        prefix=prefix,
    )
    compress_image_to_1k(raw_png, out_1k_png, max_side=1024)
    raw_png.unlink(missing_ok=True)
    return out_1k_png


def _rebuild_single_character_vtrix(cid: str, ch: Dict[str, Any], cu_crop: Path, s2_crop: Path, bu_crop: Path, out_assets_dir: Path) -> str:
    rid = ch["role_id"]
    bio = ch.get("neutral_visual_bio", "")

    cu_out = out_assets_dir / f"{rid}_face_cu_1k.png"
    cu_prompt = (
        "真人影视实拍定妆摄影。图1与图2是该演员的面部特写参考，图3是同一角色的发型/头饰与上衣领口参考。"
        "参考图是唯一的人物身份、面部骨相与服装依据：请100%精准还原图1与图2中这位真人演员本人的精确脸型骨相比例、下颌与下巴轮廓、"
        "真实年龄感与原生皮肤纹理肤色（无论年轻、年迈沧桑、皱纹、胡茬均100%如实保留，严禁美颜磨皮换脸！）、眼型眉型与眼神气质、"
        "鼻梁与鼻头真实形态、嘴唇轮廓、原有妆造发型发际线/冠帽头饰与耳饰眼镜细节（严禁替换成其他大众脸！），"
        f"并穿着图3中完全一致的领口与上衣（{bio}）。"
        "输出单人正脸含颈肩近景特写：头、鼻尖与脸严格正对镜头，双眼平视镜头，嘴唇自然闭合呈平静常态表情；"
        "纯白背景（RGB 255,255,255），柔和均匀电影级棚拍光，真实高清摄影质感，不拼贴，无任何文字或水印。"
    )
    print(f"  [vtrix-lead-cu] {cid} :: {rid} ({ch.get('display_name', '')})", flush=True)
    _vtrix_1k(cu_prompt, [cu_crop, s2_crop, bu_crop], "1:1", cu_out, prefix=f"{cid}_{rid}_cu")

    side_out = out_assets_dir / f"{rid}_side45_neutral_1k.png"
    side_prompt = (
        "真人影视实拍定妆摄影。图1是该演员的正脸含颈特写定妆基准图，图2是原片面部参考。"
        "参考图1是唯一的人物身份、真实年龄肤质、五官骨相、头饰发型与服装依据：100%保持完全同一位真人演员的精确脸型轮廓、真实年龄肤质、眼鼻唇形态、发型头饰、配饰与衣领上衣，绝不改变五官或年龄。"
        "输出同一人物头部向画面左侧旋转45度的左向四分之三侧面含颈肩近景特写（双眼均清晰可见，远侧眼略窄于近侧眼，鼻尖在脸颊轮廓线以内，非90度纯侧面），"
        "嘴唇自然闭合呈平静常态表情；纯白背景（RGB 255,255,255），柔和均匀棚拍光，单张人像不拼图，无文字无水印。"
    )

    front_out = out_assets_dir / f"{rid}_front_1k.png"
    front_prompt = (
        "真人影视实拍定妆摄影。图1是该演员的正脸特写定妆基准图（唯一面部、年龄与发型头饰依据），图2是同一角色的半身服装参考。"
        f"请100%严格保持图1中完全同一张真人面孔（精确骨相轮廓、真实年龄肤质、眼鼻唇比例、发型头饰与配饰丝毫不差）与图2中的完全一致服装款式材质（{bio}）。"
        "输出单人正面腰部以上半身定妆照：身体与脸严格正对镜头，双眼平视，自然站立，双臂自然下垂不遮挡服装，嘴唇闭合呈平静常态表情；"
        "纯白背景（RGB 255,255,255），柔和均匀棚拍光，单张人像不拼图，无文字无水印。"
    )

    with cf.ThreadPoolExecutor(max_workers=2) as sub_ex:
        fs = sub_ex.submit(_vtrix_1k, side_prompt, [cu_out, cu_crop], "1:1", side_out, f"{cid}_{rid}_side45")
        ff = sub_ex.submit(_vtrix_1k, front_prompt, [cu_out, bu_crop], "9:16", front_out, f"{cid}_{rid}_front")
        fs.result()
        ff.result()

    mv_out = out_assets_dir / f"{rid}_neutral_multiview_1k.png"
    mv_out.unlink(missing_ok=True)
    NVE._compose_multiview_sheet(front_out, cu_out, side_out, mv_out)
    print(f"  [vtrix-lead-done] {cid} :: {rid} -> {mv_out.name}", flush=True)
    return rid


def rebuild_case_assets(spec_path: Path, force: bool = False, out_subdir: str = "assets") -> Dict[str, Any]:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    cid = spec["case_id"]
    case_dir = spec_path.parent
    gold_dir = case_dir / "gold_sealed"
    crops_dir = gold_dir / "_crops_v4_leads"
    out_assets_dir = case_dir / out_subdir
    marker = out_assets_dir / ".identity_rebuilt_v41_vtrix_leads"
    if marker.is_file() and not force:
        print(f"[skip] {cid} primary roles already aligned in {out_subdir}")
        return {"case_id": cid, "status": "skipped"}

    crops_dir.mkdir(parents=True, exist_ok=True)
    out_assets_dir.mkdir(parents=True, exist_ok=True)

    all_chars = spec.get("characters", [])
    lead_chars = [ch for idx, ch in enumerate(all_chars) if is_primary_character(ch, idx)]
    minor_chars = [ch for idx, ch in enumerate(all_chars) if not is_primary_character(ch, idx)]
    for mch in minor_chars:
        print(f"  [skip-minor] {cid} :: {mch['role_id']} ({mch.get('display_name', '')}) -> secondary role skipped", flush=True)

    # Reuse existing v3 crops if already extracted cleanly (e.g. dev_01)
    legacy_crops = gold_dir / "_crops_v3"
    if legacy_crops.is_dir() and all(
        (legacy_crops / f"{ch['role_id']}_face_cu_crop.png").is_file()
        and (legacy_crops / f"{ch['role_id']}_second_crop.png").is_file()
        and (legacy_crops / f"{ch['role_id']}_bust_crop.png").is_file()
        for ch in lead_chars
    ):
        for ch in lead_chars:
            for suf in ("face_cu_crop.png", "second_crop.png", "bust_crop.png"):
                src_f = legacy_crops / f"{ch['role_id']}_{suf}"
                dst_f = crops_dir / f"{ch['role_id']}_{suf}"
                if not dst_f.is_file():
                    shutil.copyfile(src_f, dst_f)

    loc_path = crops_dir / "locate_v4_leads.json"
    need_locate = any(
        not (crops_dir / f"{ch['role_id']}_face_cu_crop.png").is_file()
        or not (crops_dir / f"{ch['role_id']}_second_crop.png").is_file()
        or not (crops_dir / f"{ch['role_id']}_bust_crop.png").is_file()
        for ch in lead_chars
    )

    if need_locate:
        src_cfg = SOURCE_MAP.get(cid)
        inspect_mp4 = crops_dir / "native_res_inspect.mp4"
        if src_cfg and Path(src_cfg["source_mp4"]).is_file():
            w_st = max(0.0, float(src_cfg["window_start"]) - 4.0)
            subprocess.run(
                [
                    "ffmpeg", "-y", "-v", "error",
                    "-ss", f"{w_st:.2f}", "-t", "46.00",
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
            for c in lead_chars
        ]
        locate_prompt = (
            f"请结合 36 格时间戳索引图 `Contact_Sheet_36.jpg` 与高清源视频 `Native_Source.mp4`（总长 {vid_dur:.1f}s，必须扫完 0s~{vid_dur:.1f}s 全程），仅为以下【主要角色】定位最清晰的单人参考帧：\n\n"
            f"【场景环境】：{spec.get('setting_summary', '')}\n"
            f"【座位/站位关系】：{spec.get('initial_blocking', '')}\n"
            "【待提取主要角色清单】：\n" + "\n".join(char_desc_lines) + "\n\n"
            "【提取硬约束】：\n"
            "1. `face_cu_frame_s` + `face_cu_bbox_norm`：全片中该主角单人特写（CU）或中近景（MCU）里脸部像素占比最大、对焦最锐利、嘴唇自然闭合或平静的帧（严禁选张大嘴说话/大笑/闭眼模糊帧！）；`bbox_norm` `[x1,y1,x2,y2]` 严密只框选该角色本人头部与衣领（绝对禁止把旁边其他角色的脸、手或衣服框进来！），并避开顶部 `y < 0.09` 水印与底部 `y > 0.83` 字幕。\n"
            "2. `second_angle_frame_s` + `second_angle_bbox_norm`：同一角色另一秒清晰正脸或互补角度单人近景帧（严禁框入他人）。\n"
            "3. `bust_frame_s` + `bust_bbox_norm`：能完整看清该角色本人发型头饰与上衣领口款式的清晰单人半身帧。"
        )
        loc = VAJ.call_argon_multimodal(
            locate_prompt,
            [
                {"kind": "image", "path": cs_jpg, "anon_name": "Contact_Sheet_36.jpg", "caption": "全片36格时间戳预览表"},
                {"kind": "video", "path": inspect_mp4, "anon_name": "Native_Source.mp4", "caption": "原生高清源视频"},
            ],
            schema=LOCATE_V4_SCHEMA,
            effort="medium",
            timeout=360,
        )
        loc_path.write_text(json.dumps(loc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        prof_map = {item["role_id"]: item for item in loc.get("character_profiles", [])}
        for ch in lead_chars:
            rid = ch["role_id"]
            prof = prof_map.get(rid)
            if not prof:
                raise RuntimeError(f"Locator missed primary role {rid} in {cid}")
            f_cu_raw = _extract_frame_png(inspect_mp4, min(vid_dur, max(0.05, float(prof["face_cu_frame_s"]))), crops_dir / f"{rid}_cu_full.png")
            f_s2_raw = _extract_frame_png(inspect_mp4, min(vid_dur, max(0.05, float(prof["second_angle_frame_s"]))), crops_dir / f"{rid}_s2_full.png")
            f_bu_raw = _extract_frame_png(inspect_mp4, min(vid_dur, max(0.05, float(prof["bust_frame_s"]))), crops_dir / f"{rid}_bust_full.png")
            _crop_clean_box(f_cu_raw, prof["face_cu_bbox_norm"], crops_dir / f"{rid}_face_cu_crop.png")
            _crop_clean_box(f_s2_raw, prof["second_angle_bbox_norm"], crops_dir / f"{rid}_second_crop.png")
            _crop_clean_box(f_bu_raw, prof["bust_bbox_norm"], crops_dir / f"{rid}_bust_crop.png")

        if inspect_mp4.name == "native_res_inspect.mp4":
            inspect_mp4.unlink(missing_ok=True)

    with cf.ThreadPoolExecutor(max_workers=min(2, max(1, len(lead_chars)))) as cex:
        futs = [
            cex.submit(
                _rebuild_single_character_vtrix,
                cid,
                ch,
                crops_dir / f"{ch['role_id']}_face_cu_crop.png",
                crops_dir / f"{ch['role_id']}_second_crop.png",
                crops_dir / f"{ch['role_id']}_bust_crop.png",
                out_assets_dir,
            )
            for ch in lead_chars
        ]
        for f in cf.as_completed(futs):
            f.result()

    marker.write_text("ok\n", encoding="utf-8")
    print(f"[ALIGNED-V4.1-VTRIX-LEADS] {cid} ({[c['role_id'] for c in lead_chars]}) -> {out_subdir}", flush=True)
    return {"case_id": cid, "leads": [c["role_id"] for c in lead_chars], "skipped_minors": [c["role_id"] for c in minor_chars]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="Comma-separated case_ids or split names")
    ap.add_argument("--out-subdir", default="assets_vtrix_v4", help="Target asset subdirectory inside each case")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    filters = {x.strip() for x in args.only.split(",") if x.strip()}
    spec_paths = sorted(BENCH_ROOT.glob("*/*/beat_spec.json"))
    targets = [
        sp for sp in spec_paths
        if not filters or sp.parent.name in filters or sp.parent.parent.name in filters
    ]
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        for f in cf.as_completed([ex.submit(rebuild_case_assets, sp, args.force, args.out_subdir) for sp in targets]):
            print(" ->", f.result(), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
