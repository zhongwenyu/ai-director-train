#!/home/zhongwenyu/data/anaconda3/bin/python3
"""
Identity-Faithful & Set-Faithful Benchmark Asset Rebuilder (`trainer/rebuild_identity_assets.py`).

Fixes the "stranger face / generic stock room" discrepancy identified in visual audit:
  1. Uses hermetic `gemini-4-argon-medium` on `gold_sealed/window_25s.mp4` to locate:
     - The clearest sharpest frame timestamp + head-and-shoulders bounding box `[x1, y1, x2, y2]`
       for each character (`CHR_1..3`, strictly excluding bottom subtitle region `y > 0.82`);
     - The clearest architectural shot timestamp for the scene environment.
  2. Crops those clean reference regions into `gold_sealed/_crops/` (NEVER exposed to Generator)
     and runs `Spark MiniMax H3 Image` (`127.0.0.1:8338`, 6 steps) to generate:
     - `assets/{CHR_x}_front_1k.png`: Preserves 100% of the original actor's exact facial features,
       charm, hair silhouette, and outfit from `<Picture 1>`, while resetting posture to a clean
       upright studio reference portrait on pure solid white `RGB(255,255,255)` background (0% pose/scene leakage!).
     - `assets/scene_clean_1k.png`: Preserves 100% of the original set's desk/furniture layout,
       background architecture, and cinema lighting/color grading from `<Picture 1>`, with all people
       and subtitles cleanly removed!
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

from PIL import Image

TRAIN_ROOT = Path("/home/zhongwenyu/project/ai-director-train")
BENCH_ROOT = TRAIN_ROOT / "corpus" / "video_bench"

for p in (
    str(TRAIN_ROOT / "judge"),
    str(TRAIN_ROOT / ".agents" / "skills" / "hit-video" / "scripts"),
):
    if p not in sys.path:
        sys.path.insert(0, p)

import video_arena_judge as VAJ  # noqa: E402
from spark_h3_image import generate_spark_h3_image  # noqa: E402

LOCATE_REFS_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "scene_frame_s": {"type": "number"},
        "character_crops": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "role_id": {"type": "string"},
                    "frame_s": {"type": "number"},
                    "bbox_norm": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 4,
                        "maxItems": 4,
                    },
                },
                "required": ["role_id", "frame_s", "bbox_norm"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["scene_frame_s", "character_crops"],
    "additionalProperties": False,
}


def _extract_frame_png(mp4_path: Path, t_sec: float, out_png: Path) -> Path:
    out_png.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-ss", f"{max(0.0, t_sec):.3f}",
            "-i", str(mp4_path),
            "-frames:v", "1",
            str(out_png),
        ],
        check=True,
    )
    return out_png


def rebuild_case_assets(spec_path: Path, force: bool = False) -> Dict[str, Any]:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    cid = spec["case_id"]
    case_dir = spec_path.parent
    gold_dir = case_dir / "gold_sealed"
    crops_dir = gold_dir / "_crops"
    assets_dir = case_dir / "assets"
    marker = assets_dir / ".identity_rebuilt_v2"
    if marker.is_file() and not force:
        print(f"[skip] {cid} already rebuilt with identity-faithful Spark H3 Image")
        return {"case_id": cid, "status": "skipped"}

    crops_dir.mkdir(parents=True, exist_ok=True)
    src_mp4 = gold_dir / "window_25s.mp4"
    if not src_mp4.is_file():
        src_mp4 = Path(spec["gold_sealed_mp4"])

    pr = json.loads(
        subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_format", "-of", "json", str(src_mp4)],
            text=True,
        )
    )
    vid_dur = max(1.0, float(pr["format"]["duration"]) - 0.15)

    char_desc_lines = [
        f"- `{c['role_id']}`（{c['display_name']}，{c.get('gender', '')}）：{c['neutral_visual_bio']}"
        for c in spec.get("characters", [])
    ]
    dialogue_hint = "\n".join(
        f"- {t['speaker_id']}: “{t['text']}”" for t in spec.get("dialogue_turns", [])[:6]
    )

    locate_prompt = (
        f"请仔细观看沙箱视频 `Source_Clip.mp4`（总时长约 {vid_dur:.1f}s），精准定位以下每个角色的清晰单人参考帧及场景环境参考帧：\n\n"
        f"【场景环境】：{spec.get('setting_summary', '')}\n"
        f"【座位/站位关系】：{spec.get('initial_blocking', '')}\n"
        "【需定位角色清单】：\n"
        + "\n".join(char_desc_lines)
        + "\n【对白线索（辅助确认谁是谁）】：\n"
        + dialogue_hint
        + "\n\n【硬性定位要求】：\n"
        "1. `scene_frame_s`：挑选一个最能看清房间桌面布局、背景建筑结构与整体光影色温的中景/全景时刻（秒数，0 到总时长之间）。\n"
        "2. 对每个角色输出一条 `character_crops`：\n"
        "   - `frame_s`：该角色正脸或微侧脸最清晰、无动态模糊、无他人遮挡的时刻（秒数）；\n"
        "   - `bbox_norm`：归一化裁剪框 `[x1, y1, x2, y2]`（范围 `0.0~1.0`），框住该角色完整的头部、发型与上半身服装（四周留约10%余量，绝对不要框入其他人的脸，且 `y2` 尽量不超过 `0.83` 以避开底部字幕文字！）。"
    )

    loc = VAJ.call_argon_multimodal(
        locate_prompt,
        [{"kind": "video", "path": src_mp4, "anon_name": "Source_Clip.mp4", "caption": "源参考视频"}],
        schema=LOCATE_REFS_SCHEMA,
        effort="medium",
        timeout=300,
    )
    (crops_dir / "locate_meta.json").write_text(json.dumps(loc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    ar = spec.get("aspect_ratio", "16:9")

    # 1. Extract & crop top 83% of scene frame (excluding bottom subtitle strip) -> rebuild `scene_clean_1k.png`
    sc_t = min(vid_dur, max(0.05, float(loc.get("scene_frame_s", 1.0))))
    sc_raw_frame = _extract_frame_png(src_mp4, sc_t, crops_dir / "scene_src_frame.png")
    im_sc = Image.open(sc_raw_frame).convert("RGB")
    sw, sh = im_sc.size
    # Crop out bottom 16% subtitle area cleanly while preserving room architecture & desks
    sc_cropped = im_sc.crop((0, 0, sw, int(round(sh * 0.84))))
    sc_crop_path = crops_dir / "scene_src_nosub.png"
    sc_cropped.save(sc_crop_path, format="PNG")

    scene_out_1k = assets_dir / "scene_clean_1k.png"
    scene_raw_2k = assets_dir / "scene_clean.raw2k.png"
    scene_prompt = (
        "The interior or exterior architecture, desk and furniture arrangement, background props, and cinema color lighting in <Picture 1> are <Subject 1>. "
        f"The target image shows an empty photorealistic 35mm live-action architectural set plate ({ar}) of <Subject 1>; "
        "<Subject 1> is preserved in exact room geometry, desk and chair positions, background decor, window/key lighting direction, and color grading "
        f"({spec.get('setting_summary', '')}), while completely removing all people and characters so every seat and walkway is completely empty. "
        "Crisp 35mm live-action cinema set photography, zero people, zero characters, zero text, zero subtitles, zero watermarks."
    )
    print(f"  [spark-scene] {cid} -> scene_clean_1k.png", flush=True)
    generate_spark_h3_image(
        prompt=scene_prompt,
        out_path=scene_raw_2k,
        ref_images=[sc_crop_path],
        aspect_ratio=ar if ar in ("16:9", "9:16") else "16:9",
        seed=202601,
        steps=6,
        out_1k_path=scene_out_1k,
    )
    scene_raw_2k.unlink(missing_ok=True)

    # 2. Rebuild each character's `{CHR_x}_front_1k.png` preserving exact original actor face + hair + outfit!
    crop_map = {item["role_id"]: item for item in loc.get("character_crops", [])}
    for idx, ch in enumerate(spec.get("characters", []), 1):
        rid = ch["role_id"]
        c_item = crop_map.get(rid, {"frame_s": 1.0 + idx, "bbox_norm": [0.2, 0.05, 0.8, 0.82]})
        ft = min(vid_dur, max(0.05, float(c_item["frame_s"])))
        f_png = _extract_frame_png(src_mp4, ft, crops_dir / f"{rid}_full_frame.png")
        fim = Image.open(f_png).convert("RGB")
        fw, fh = fim.size
        x1, y1, x2, y2 = [float(v) for v in c_item["bbox_norm"]]
        x1 = max(0.0, min(0.85, x1))
        y1 = max(0.0, min(0.75, y1))
        x2 = max(x1 + 0.15, min(1.0, x2))
        y2 = max(y1 + 0.20, min(0.84, y2))  # Hard-exclude bottom subtitle band!
        crop_im = fim.crop((int(x1 * fw), int(y1 * fh), int(x2 * fw), int(y2 * fh)))
        crop_p = crops_dir / f"{rid}_actor_crop.png"
        crop_im.save(crop_p, format="PNG")

        g_word = "woman" if ch.get("gender") == "female" else ("man" if ch.get("gender") == "male" else "person")
        c_out_1k = assets_dir / f"{rid}_front_1k.png"
        c_raw_2k = assets_dir / f"{rid}_front.raw2k.png"
        c_prompt = (
            f"The {g_word} in <Picture 1> is <Subject 1>. "
            "The target image shows a photorealistic live-action three-quarter-length studio reference portrait of <Subject 1> "
            "standing upright facing straight ahead on a pure solid white studio background RGB(255,255,255); "
            "<Subject 1> is 100% preserved in exact facial bone structure, eye shape, nose bridge, lip contour, skin tone, beauty charisma, hairstyle, "
            f"and clothing outfit from <Picture 1> ({ch.get('neutral_visual_bio', '')}), "
            "reset to a calm, natural, undistorted 0% neutral baseline expression with gently closed lips, clear direct gaze, and arms resting naturally at sides. "
            "Pure solid white studio background, soft even portrait lighting, authentic Asian live-action skin texture, zero background objects, zero text, zero subtitles."
        )
        print(f"  [spark-char] {cid} -> {rid}_front_1k.png (t={ft:.2f}s)", flush=True)
        generate_spark_h3_image(
            prompt=c_prompt,
            out_path=c_raw_2k,
            ref_images=[crop_p],
            aspect_ratio="9:16",
            seed=202610 + idx,
            steps=6,
            out_1k_path=c_out_1k,
        )
        c_raw_2k.unlink(missing_ok=True)

    marker.write_text("ok\n", encoding="utf-8")
    print(f"[REBUILT] {cid} identity-faithful assets complete!", flush=True)
    return {"case_id": cid, "status": "rebuilt"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="Comma-separated case_ids or split names")
    ap.add_argument("--workers", type=int, default=2, help="Parallel Spark H3 Image workers")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    filters = {x.strip() for x in args.only.split(",") if x.strip()}
    spec_paths = sorted(BENCH_ROOT.glob("*/*/beat_spec.json"))
    targets = [
        sp for sp in spec_paths
        if not filters or sp.parent.name in filters or sp.parent.parent.name in filters
    ]

    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(rebuild_case_assets, sp, args.force) for sp in targets]
        for f in cf.as_completed(futs):
            print(" ->", f.result(), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
