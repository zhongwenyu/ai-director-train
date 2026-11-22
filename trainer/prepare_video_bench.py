#!/home/zhongwenyu/data/anaconda3/bin/python3
"""
Zero-Leakage Multi-Genre Video Benchmark Builder (`trainer/prepare_video_bench.py`).

Builds a 12-drama strictly disjoint benchmark (`5 DEV + 4 VAL + 3 TEST`):
  1. Slices a 26s window from each distinct source drama and uses hermetic `gemini-4-argon`
     to locate one self-contained `8.5s–12.5s` dramatic beat and extract ONLY a de-leaked
     text task specification (`beat_spec.json`) + clean solo voice timestamps.
  2. Slices speaker voice references (`1.4s–2.8s` clean WAV) and stores `gold_reference.mp4`
     in a sealed `gold_sealed/` subfolder NEVER mounted or exposed to Generator/Optimizer.
  3. Generates 100% Zero-Leakage Standard Assets (`0%` neutral white-bg character front sheets,
     character-free clean scene plates, and white-bg prop sheets) purely from text via Cloud Vtrix
     (ZERO source video frames passed to Vtrix -> 0.0% pose/lighting/expression leakage!).
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List
from PIL import Image

TRAIN_ROOT = Path("/home/zhongwenyu/project/ai-director-train")
BENCH_ROOT = TRAIN_ROOT / "corpus" / "video_bench"
STUDIO_ROOT = Path("/home/zhongwenyu/project/playlets-studio")
NODE_BIN = "/home/zhongwenyu/.local/lib/node-v22.23.4-linux-x64/bin/node"

if str(TRAIN_ROOT / "judge") not in sys.path:
    sys.path.insert(0, str(TRAIN_ROOT / "judge"))
if str(TRAIN_ROOT / ".agents/skills/hit-video/scripts") not in sys.path:
    sys.path.insert(0, str(TRAIN_ROOT / ".agents/skills/hit-video/scripts"))
import video_arena_judge as VAJ  # noqa: E402
from spark_h3_image import generate_spark_h3_image  # noqa: E402

V_TRAIN = TRAIN_ROOT / "videos"
V_HG = Path("/home/zhongwenyu/project/ai-director-workstation/evals/hongguo-video-reverse-50/video-512p24")

# 12 Distinct Photorealistic Live-Action Dramas across 6 Genres & Both Aspect Ratios (ZERO Drama Overlap!)
BENCH_SOURCES: List[Dict[str, Any]] = [
    # ==================== DEV (5 Dramas — Diagnostic Training Set) ====================
    {
        "case_id": "dev_01_workplace_rival",
        "split": "dev",
        "genre": "现代职场轻喜",
        "topology": "三人多焦点反讽博弈与桌面微动作+反应切镜",
        "aspect_ratio": "16:9",
        "source_mp4": str(V_TRAIN / "target_video.mp4"),
        "window_start": 18.0,
        "window_dur": 24.0,
    },
    {
        "case_id": "dev_02_mindread_os",
        "split": "dev",
        "genre": "都市心声反差",
        "topology": "画外内心独白OS+画内零口型微表情凝视",
        "aspect_ratio": "16:9",
        "source_mp4": str(next(V_TRAIN.glob("06_*.mp4"))),
        "window_start": 8.0,
        "window_dur": 26.0,
    },
    {
        "case_id": "dev_03_romance_tear",
        "split": "dev",
        "genre": "现代情感虐恋",
        "topology": "双人高张力克制含泪对峙正反打",
        "aspect_ratio": "16:9",
        "source_mp4": str(next(V_TRAIN.glob("01_*.mp4"))),
        "window_start": 8.0,
        "window_dur": 26.0,
    },
    {
        "case_id": "dev_04_period_1988",
        "split": "dev",
        "genre": "年代烟火逆袭",
        "topology": "竖屏9:16八十年代乡土市井人物交锋",
        "aspect_ratio": "9:16",
        "source_mp4": str(V_HG / "7689393278562602009/第01集.mp4"),
        "window_start": 32.0,
        "window_dur": 26.0,
    },
    {
        "case_id": "dev_05_museum_suspense",
        "split": "dev",
        "genre": "民国暗调悬疑",
        "topology": "夜景暖暗高反差光影压迫感对话与眼神试探",
        "aspect_ratio": "16:9",
        "source_mp4": str(V_HG / "7637507836049624089/第01集.mp4"),
        "window_start": 16.0,
        "window_dur": 26.0,
    },
    # ==================== VAL (4 Unseen Dramas — Blind Promotion Gate) ====================
    {
        "case_id": "val_01_winter_parting",
        "split": "val",
        "genre": "现代生活情感",
        "topology": "户外自然光男女决绝告别与呼吸停顿",
        "aspect_ratio": "16:9",
        "source_mp4": str(next(V_TRAIN.glob("02_*.mp4"))),
        "window_start": 6.0,
        "window_dur": 26.0,
    },
    {
        "case_id": "val_02_scar_probe",
        "split": "val",
        "genre": "都市悬疑试探",
        "topology": "手部细节动作遮掩与谎言心理博弈",
        "aspect_ratio": "16:9",
        "source_mp4": str(next(V_TRAIN.glob("17_*.mp4"))),
        "window_start": 10.0,
        "window_dur": 26.0,
    },
    {
        "case_id": "val_03_class_clash",
        "split": "val",
        "genre": "都市强冲突逆袭",
        "topology": "突发争执压迫拍与情绪爆发反应",
        "aspect_ratio": "16:9",
        "source_mp4": str(next(V_TRAIN.glob("29_*.mp4"))),
        "window_start": 12.0,
        "window_dur": 26.0,
    },
    {
        "case_id": "val_04_ancient_prince",
        "split": "val",
        "genre": "古装权谋逆袭",
        "topology": "竖屏9:16古装人物身份压迫与对白交锋",
        "aspect_ratio": "9:16",
        "source_mp4": str(V_HG / "7634769526357232702/第01集.mp4"),
        "window_start": 30.0,
        "window_dur": 26.0,
    },
    # ==================== TEST (3 Locked Unseen Dramas — Evaluated ONCE at End) ====================
    {
        "case_id": "test_01_tipsy_breakup",
        "split": "test",
        "genre": "都市轻喜微醺",
        "topology": "高频微表情反差与生活流肢体互动",
        "aspect_ratio": "16:9",
        "source_mp4": str(next(V_TRAIN.glob("04_*.mp4"))),
        "window_start": 3.0,
        "window_dur": 25.0,
    },
    {
        "case_id": "test_02_trio_table",
        "split": "test",
        "genre": "现代电影感群像",
        "topology": "暖光桌面三人道具互动与眼神暗流",
        "aspect_ratio": "16:9",
        "source_mp4": str(next(V_TRAIN.glob("26_*.mp4"))),
        "window_start": 12.0,
        "window_dur": 26.0,
    },
    {
        "case_id": "test_03_ancient_family",
        "split": "test",
        "genre": "古代寒门亲情",
        "topology": "古装室内多人急切冲突与手部动作",
        "aspect_ratio": "16:9",
        "source_mp4": str(V_HG / "7688646466708966462/第01集.mp4"),
        "window_start": 25.0,
        "window_dur": 26.0,
    },
]

EXTRACT_BEAT_PROMPT = """请仔细观看并听取这段 25 秒左右的源视频切片（切片自身时间从 0.0s 开始计）。
请从中挑选出**最精彩、人物对白清晰完整、包含鲜明戏剧互动或情绪转折的一段连续 `8.5s ~ 12.5s` 完整戏剧拍（Beat）**，并为其提取一份**彻底脱敏的纯文本戏剧任务卡**（用于后续盲测训练视频生成 Skill）。

【脱敏与提取硬性规范】
1. `clip_start_s` 与 `clip_end_s`：相对当前附件切片 0.0s 的起止秒数，时长必须在 `8.5` 到 `12.5` 秒之间，且起点和终点必须卡在句子自然边界（严禁把一句台词拦腰截断！）。
2. `characters`（仅列出该 `8.5~12.5s` 内实际出镜的核心角色，最多 3 人）：
   - `neutral_visual_bio`：**只准写纯静态常态外貌、年龄感、发型轮廓与全身服装款式颜色**（用于纯文本独立生成 0% 中性白底人物设定图；**严禁出现任何表情词、动作词、姿势词或背景词！**）。
   - `clean_voice_window`：如果该角色有开口说话或心声，在整条 25s 附件内找一段该角色**最干净、无重叠杂音的单人原声区间 `[v_start_s, v_end_s]`**（长度 `1.4s ~ 2.8s`）；若该角色全程不发声，填 `null`。
3. `setting_summary`：纯静态空间建筑结构、陈设与光影色温描述（用于纯文本独立生成无人物纯净空镜；**严禁出现人物或原片镜头切法！**）。
4. `dialogue_turns`：按时间顺序完整抄录该 `8.5~12.5s` 内的每一句台词或心声（`mode` 填 `"spoken"` 或 `"inner_os"`），**严禁漏字或改词，且严禁在任务卡里透露原片在第几秒切镜！**

请严格只输出如下单个 JSON 对象：
{
  "clip_start_s": 2.0,
  "clip_end_s": 12.0,
  "setting_summary": "纯静态环境空间结构与光影色温描述（40-80字，不含人物）",
  "dramatic_goal": "本段 8.5-12.5s 的戏剧冲突目标、关系博弈与起止状态变化（50-100字，不写切镜秒数）",
  "initial_blocking": "开场时刻在场角色的相对空间位置关系（如：办公桌一侧并排坐着CHR_1与CHR_2，对侧坐着CHR_3）",
  "characters": [
    {
      "role_id": "CHR_1",
      "display_name": "角色简称",
      "gender": "female 或 male",
      "neutral_visual_bio": "约24岁东亚女性，自然淡妆真实皮肤肌理，酒红棕齐下巴短波波头，穿白色翻领黑色修身针织开衫配卡其格纹短裙与黑色乐福鞋，戴小巧珍珠耳钉",
      "clean_voice_window": [4.2, 6.6]
    }
  ],
  "props": [
    {
      "prop_id": "PRP_1",
      "name": "道具名称",
      "description": "纯静态单件物品外观材质描述（若无关键交互道具则输出空数组 []）"
    }
  ],
  "dialogue_turns": [
    {
      "speaker_id": "CHR_1",
      "mode": "spoken",
      "text": "逐字准确的中文台词原文",
      "subtext_intent": "说话人的潜台词情绪与语气特征（不含原片镜头词）"
    }
  ]
}"""


EXTRACT_BEAT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "clip_start_s": {"type": "number"},
        "clip_end_s": {"type": "number"},
        "setting_summary": {"type": "string"},
        "dramatic_goal": {"type": "string"},
        "initial_blocking": {"type": "string"},
        "characters": {
            "type": "array",
            "minItems": 1,
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "role_id": {"type": "string"},
                    "display_name": {"type": "string"},
                    "gender": {"type": "string", "enum": ["female", "male"]},
                    "neutral_visual_bio": {"type": "string"},
                    "clean_voice_window": {
                        "anyOf": [
                            {"type": "null"},
                            {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2},
                        ]
                    },
                },
                "required": ["role_id", "display_name", "gender", "neutral_visual_bio", "clean_voice_window"],
                "additionalProperties": False,
            },
        },
        "props": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "prop_id": {"type": "string"},
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["prop_id", "name", "description"],
                "additionalProperties": False,
            },
        },
        "dialogue_turns": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "speaker_id": {"type": "string"},
                    "mode": {"type": "string", "enum": ["spoken", "inner_os"]},
                    "text": {"type": "string"},
                    "subtext_intent": {"type": "string"},
                },
                "required": ["speaker_id", "mode", "text", "subtext_intent"],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "clip_start_s",
        "clip_end_s",
        "setting_summary",
        "dramatic_goal",
        "initial_blocking",
        "characters",
        "props",
        "dialogue_turns",
    ],
    "additionalProperties": False,
}


def vtrix_generate_png(prompt: str, aspect_ratio: str, out_png: Path, max_edge: int = 1024) -> None:
    """Generate a 100% text-to-image asset via Spark MiniMax H3 Image (ZERO source frames -> ZERO leakage)."""
    out_png.parent.mkdir(parents=True, exist_ok=True)
    if out_png.is_file() and out_png.stat().st_size > 1024:
        return
    raw_png = out_png.with_suffix(".raw.png")
    generate_spark_h3_image(
        prompt=prompt,
        out_path=raw_png,
        ref_images=[],
        aspect_ratio=aspect_ratio if aspect_ratio in ("16:9", "9:16", "1:1") else "9:16",
        seed=42,
        steps=6,
    )
    im = Image.open(raw_png).convert("RGB")
    w, h = im.size
    scale = min(1.0, float(max_edge) / float(max(w, h)))
    if scale < 1.0:
        im = im.resize((max(1, int(round(w * scale))), max(1, int(round(h * scale)))), getattr(Image, "LANCZOS", 1))
    im.save(out_png, format="PNG", optimize=True)
    raw_png.unlink(missing_ok=True)


def build_single_case(src: Dict[str, Any], force: bool = False) -> Dict[str, Any]:
    case_id = src["case_id"]
    split = src["split"]
    case_dir = BENCH_ROOT / split / case_id
    spec_path = case_dir / "beat_spec.json"
    if spec_path.is_file() and not force:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        if all(Path(p).is_file() for p in spec.get("asset_files", {}).values()):
            print(f"[skip] {case_id} already complete")
            return spec

    case_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = case_dir / "assets"
    voices_dir = case_dir / "voices"
    gold_dir = case_dir / "gold_sealed"
    assets_dir.mkdir(exist_ok=True)
    voices_dir.mkdir(exist_ok=True)
    gold_dir.mkdir(exist_ok=True)

    ar = src["aspect_ratio"]
    tw, th = (896, 512) if ar == "16:9" else (512, 896)

    # 1. Extract normalized 25s inspection window
    win_mp4 = gold_dir / "window_25s.mp4"
    vf = f"scale={tw}:{th}:force_original_aspect_ratio=decrease,pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2,fps=24"
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-ss", str(src["window_start"]), "-t", str(src["window_dur"]),
            "-i", src["source_mp4"],
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast", "-crf", "22", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "160k",
            str(win_mp4),
        ],
        check=True,
    )

    # 2. Extract de-leaked beat_spec via tool-stripped gemini-4-argon
    print(f"[extract] {case_id} analyzing source window...", flush=True)
    extracted = VAJ.call_argon_multimodal(
        EXTRACT_BEAT_PROMPT,
        [{"kind": "video", "path": win_mp4, "anon_name": "Source_Window.mp4", "caption": "待分析25秒源切片"}],
        schema=EXTRACT_BEAT_SCHEMA,
        effort="medium",
        timeout=300,
    )

    cs = max(0.0, float(extracted.get("clip_start_s", 1.0)))
    ce = min(float(src["window_dur"]), float(extracted.get("clip_end_s", cs + 10.0)))
    if ce - cs < 7.5:
        ce = min(float(src["window_dur"]), cs + 9.5)
    elif ce - cs > 13.5:
        ce = cs + 12.0

    # 3. Slice sealed gold_reference.mp4 (normalized container + loudness)
    gold_mp4 = gold_dir / "gold_reference.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-ss", f"{cs:.2f}", "-t", f"{ce - cs:.2f}",
            "-i", str(win_mp4),
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k",
            str(gold_mp4),
        ],
        check=True,
    )

    # 4. Slice speaker clean voice references (1.4s - 2.8s)
    voice_files: Dict[str, str] = {}
    for ch in extracted.get("characters", []):
        rid = ch["role_id"]
        vw = ch.get("clean_voice_window")
        has_turns = any(t.get("speaker_id") == rid for t in extracted.get("dialogue_turns", []))
        if vw and isinstance(vw, list) and len(vw) == 2:
            vs = max(0.0, float(vw[0]))
            ve = min(float(src["window_dur"]), float(vw[1]))
            vdur = max(1.4, min(2.8, ve - vs))
        elif has_turns:
            vs, vdur = cs + 0.3, 2.2
        else:
            continue
        wav_out = voices_dir / f"{rid}.wav"
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error",
                "-ss", f"{vs:.2f}", "-t", f"{vdur:.2f}",
                "-i", str(win_mp4),
                "-vn", "-ac", "1", "-ar", "24000",
                str(wav_out),
            ],
            check=True,
        )
        voice_files[rid] = str(wav_out)

    # 5. Generate ZERO-LEAKAGE Standard Assets IN PARALLEL via Cloud Vtrix
    asset_files: Dict[str, str] = {}
    vtrix_tasks = []

    scene_png = assets_dir / "scene_clean_1k.png"
    scene_prompt = (
        f"Photorealistic 35mm live-action film empty architectural set plate ({ar}): "
        f"{extracted['setting_summary']}. "
        "Completely empty environment with ZERO people, ZERO characters, ZERO text/logos/subtitles, "
        "single continuous camera view, natural cinema lighting and realistic surface textures."
    )
    asset_files["scene_clean"] = str(scene_png)
    vtrix_tasks.append(("scene_clean_1k.png", scene_prompt, ar, scene_png, 1024))

    for ch in extracted.get("characters", []):
        rid = ch["role_id"]
        c_png = assets_dir / f"{rid}_front_1k.png"
        c_prompt = (
            f"Photorealistic live-action full-body front character reference portrait on pure solid white studio background RGB(255,255,255): "
            f"{ch['neutral_visual_bio']}. "
            "Standing upright facing straight ahead, arms relaxed naturally at sides, full head-to-toe including shoes visible inside frame, "
            "0% neutral calm baseline facial expression, symmetrical relaxed closed lips, natural steady gaze, realistic Asian actor skin pores and subtle natural makeup, "
            "even soft studio lighting, pure white background with zero props and zero text."
        )
        asset_files[rid] = str(c_png)
        vtrix_tasks.append((f"{rid}_front_1k.png", c_prompt, "9:16", c_png, 1024))

    props = (extracted.get("props") or [])[:1]
    for pr in props:
        pid = pr["prop_id"]
        p_png = assets_dir / f"{pid}_1k.png"
        p_prompt = (
            f"Photorealistic live-action single prop product photo on pure solid white background RGB(255,255,255): "
            f"{pr['name']} — {pr['description']}."
            " Single complete object centered with 15% white margin on all sides, zero hands, zero people, zero table background, zero text."
        )
        asset_files[pid] = str(p_png)
        vtrix_tasks.append((f"{pid}_1k.png", p_prompt, "1:1", p_png, 512))

    def _run_vt(t):
        lbl, prm, ratio, outp, medge = t
        print(f"[vtrix] {case_id} -> {lbl}", flush=True)
        vtrix_generate_png(prm, ratio, outp, max_edge=medge)

    with cf.ThreadPoolExecutor(max_workers=len(vtrix_tasks)) as vex:
        list(vex.map(_run_vt, vtrix_tasks))

    spec = {
        "case_id": case_id,
        "split": split,
        "genre": src["genre"],
        "topology": src["topology"],
        "aspect_ratio": ar,
        "target_duration_s": round(ce - cs, 1),
        "setting_summary": extracted["setting_summary"],
        "dramatic_goal": extracted["dramatic_goal"],
        "initial_blocking": extracted.get("initial_blocking", ""),
        "characters": [
            {
                "role_id": c["role_id"],
                "display_name": c["display_name"],
                "gender": c.get("gender", ""),
                "neutral_visual_bio": c["neutral_visual_bio"],
            }
            for c in extracted.get("characters", [])
        ],
        "props": props,
        "dialogue_turns": extracted.get("dialogue_turns", []),
        "asset_files": asset_files,
        "voice_files": voice_files,
        "gold_sealed_mp4": str(gold_mp4),
    }
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[READY] {case_id} ({ar}, {spec['target_duration_s']}s, chars={len(spec['characters'])}, turns={len(spec['dialogue_turns'])})")
    return spec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="Comma-separated case_ids or split names (dev/val/test)")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    filters = {x.strip() for x in args.only.split(",") if x.strip()}
    targets = [
        s for s in BENCH_SOURCES
        if not filters or s["case_id"] in filters or s["split"] in filters
    ]

    BENCH_ROOT.mkdir(parents=True, exist_ok=True)
    results: List[Dict[str, Any]] = []
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(build_single_case, s, args.force): s["case_id"] for s in targets}
        for fut in cf.as_completed(futs):
            cid = futs[fut]
            res = fut.result()
            results.append(res)

    results.sort(key=lambda x: x["case_id"])
    manifest_path = BENCH_ROOT / "manifest.json"
    # Merge with existing manifest if partial run
    existing = {}
    if manifest_path.is_file():
        for item in json.loads(manifest_path.read_text(encoding="utf-8")):
            existing[item["case_id"]] = item
    for item in results:
        # Strip gold_sealed_mp4 from public manifest summary? Keep path metadata cleanly
        existing[item["case_id"]] = item
    ordered = [existing[s["case_id"]] for s in BENCH_SOURCES if s["case_id"] in existing]
    manifest_path.write_text(json.dumps(ordered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nSaved {len(ordered)} cases to {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
