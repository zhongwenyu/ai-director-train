#!/home/zhongwenyu/data/anaconda3/bin/python3
"""
Controlled A/B/C Experiment (`trainer/exp_expression_multiview_ab.py`):
Does fusing shot-specific non-neutral character expressions into a Character Multi-View Sheet
improve facial expression accuracy in MiniMax H3 Video, and what side effects occur?

Tests 3 contrasting dramatic beats (Playful Irony, Smug->Shock Transition, Tearful Grief) x 3 Conditions:
  - Cond_A (`Neutral_Sheet`): Standard 0% neutral portrait (`CHR_x_front_1k.png`)
  - Cond_B (`Unconstrained_Expr_Multiview`): 3-panel composite `[0% Neutral | Expressive CU (incl. open mouth) | 45° Expressive]`
  - Cond_C (`ClosedLip_OcularExpr_Multiview`): 3-panel composite `[0% Neutral | Eye/Brow Expressive CU (lips closed) | Transition/45° View (lips closed)]`

All 3 conditions share the EXACT same random seed, H3 video prompt, duration, and voice reference!
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

from PIL import Image

TRAIN_ROOT = Path("/home/zhongwenyu/project/ai-director-train")
EXP_DIR = TRAIN_ROOT / "runs" / "ab_expr_multiview_exp"

for p in (
    str(TRAIN_ROOT / "judge"),
    str(TRAIN_ROOT / ".agents" / "skills" / "hit-video" / "scripts"),
    "/home/zhongwenyu/project/ai-director-workstation/skills/storyboard-video-gen/scripts",
):
    if p not in sys.path:
        sys.path.insert(0, p)

import h3_native_runner as H3R  # noqa: E402
import native_video_engine as NVE  # noqa: E402
import video_arena_judge as VAJ  # noqa: E402
from spark_h3_image import generate_spark_h3_image  # noqa: E402


def compose_three_panel_sheet(left_neutral: Path, top_right: Path, bot_right: Path, out_png: Path) -> Path:
    """Compose Studio-style 1024x1024 3-panel sheet: Left (512x1024 neutral) | Top-Right (512x512) | Bottom-Right (512x512)."""
    canvas = Image.new("RGB", (1024, 1024), (255, 255, 255))

    def _fit_panel(im: Image.Image, tw: int, th: int) -> Image.Image:
        w, h = im.size
        scale = max(tw / max(1, w), th / max(1, h))
        nw, nh = int(round(w * scale)), int(round(h * scale))
        resized = im.resize((nw, nh), getattr(Image, "LANCZOS", 1))
        x0 = max(0, (nw - tw) // 2)
        y0 = max(0, int((nh - th) * 0.20))
        return resized.crop((x0, y0, x0 + tw, y0 + th))

    im_l = _fit_panel(Image.open(left_neutral).convert("RGB"), 508, 1024)
    im_tr = _fit_panel(Image.open(top_right).convert("RGB"), 508, 508)
    im_br = _fit_panel(Image.open(bot_right).convert("RGB"), 508, 508)

    canvas.paste(im_l, (0, 0))
    canvas.paste(im_tr, (516, 0))
    canvas.paste(im_br, (516, 516))
    out_png.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_png, format="PNG", optimize=True)
    return out_png


BEATS: List[Dict[str, Any]] = [
    {
        "beat_id": "beat1_playful_irony",
        "title": "现代职场轻喜：弯眼甜笑藏锋反讽（单一持续情绪）",
        "case_path": "corpus/video_bench/dev/dev_01_workplace_rival",
        "role_id": "CHR_1",
        "gender": "woman",
        "duration_s": 4,
        "gold_window": (9.0, 12.0),
        "open_expr_tr": "front close-up portrait on pure white background showing a bright playful curved-eye sweet smile with parted laughing lips and a slightly raised knowing eyebrow",
        "open_expr_br": "45-degree three-quarter close-up portrait on pure white background tilting head playfully with a sharp teasing grin and visible teeth",
        "closed_expr_tr": "front close-up portrait on pure white background showing sparkling curved crescent eyes, a subtly arched playful eyebrow, and a knowing sweet closed-lip smile (lips gently closed)",
        "closed_expr_br": "45-degree three-quarter close-up portrait on pure white background with a slight playful head tilt, lively teasing eyes, and relaxed closed lips",
        "kf_prompt": "Medium close-up of <Subject 2> seated at her light-wood office desk inside <Subject 1> facing 15 degrees front-right across the frosted glass monitor divider, leaning slightly forward with hands lightly clasped in front of her chest and lively attentive eyes.",
        "h3_action": (
            "[Shot 1] Subtle push-in medium close-up from <Picture 1>. Seated at her desk, <Subject 1> (S1) leans forward slightly with bright curved-eye playful warmth concealing a sharp edge, "
            "lightly clasping her hands before tilting her head and arching one eyebrow on the second clause. "
            "<Subject 1> (S1) speaks (0.16s-3.35s): <d>[Chinese] 知道的是开玩笑，不知道的，还以为您打压新人呢。</d> "
            "with crisp syllable-accurate lip-sync, finishing with a sweet knowing closed-lip smile."
        ),
    },
    {
        "beat_id": "beat2_smug_to_shock",
        "title": "都市读心反差：得意微哂瞬间转瞳孔地震（句内强情绪反转！）",
        "case_path": "corpus/video_bench/dev/dev_02_mindread_os",
        "role_id": "CHR_2",
        "gender": "man",
        "duration_s": 3,
        "gold_window": (7.2, 10.2),
        "open_expr_tr": "front close-up portrait on pure white background with eyes blown wide open in utter shock and jaw dropped wide open in disbelief",
        "open_expr_br": "45-degree three-quarter close-up portrait on pure white background recoiling backward with startled wide eyes and open gasping mouth",
        "closed_expr_tr": "front close-up portrait on pure white background with a relaxed confident wry smirk and calm amused eyes, lips closed",
        "closed_expr_br": "45-degree three-quarter close-up portrait on pure white background with eyes widened sharply in sudden stunned disbelief and tense closed lips",
        "kf_prompt": "Medium close-up of <Subject 2> seated at the outdoor night barbecue table inside <Subject 1> facing front-right under warm lantern bokeh, starting with a residual relaxed half-smile just before being stunned.",
        "h3_action": (
            "[Shot 1] Static medium close-up from <Picture 1>. From 0.0s to 0.7s, <Subject 1> (S1) holds a lingering amused half-smile, then at 0.7s his smile freezes and vanishes as his eyes snap wide open in stunned disbelief, recoiling his chin slightly. "
            "<Subject 1> (S1) speaks in shocked realization (0.95s-2.45s): <d>[Chinese] 你居然真的会读心？</d> "
            "with sharp urgent lip-sync and raised astonished brows."
        ),
    },
    {
        "beat_id": "beat3_tearful_grief",
        "title": "现代情感虐恋：红眼眶隐忍含泪倾诉（细腻悲情微张力）",
        "case_path": "corpus/video_bench/dev/dev_03_romance_tear",
        "role_id": "CHR_2",
        "gender": "man",
        "duration_s": 4,
        "gold_window": (0.0, 4.5),
        "open_expr_tr": "front close-up portrait on pure white background crying bitterly with furrowed brows, red wet eyes, and anguished parted lips",
        "open_expr_br": "45-degree three-quarter close-up portrait on pure white background with tearful glistening eyes and pained open mouth",
        "closed_expr_tr": "front close-up portrait on pure white background with subtly reddened glistening tearful eyes, a vulnerable aching brow, and trembling tightly closed lips holding back grief",
        "closed_expr_br": "45-degree three-quarter close-up portrait on pure white background with misty red-rimmed eyes, pained tender gaze, and closed lips",
        "kf_prompt": "Over-the-shoulder medium close-up inside <Subject 1> under warm sunset backlight, looking past a blurred foreground shoulder at <Subject 2> standing facing front-right with misty reddened eyes and restrained heartache.",
        "h3_action": (
            "[Shot 1] Slow emotional push-in medium close-up from <Picture 1>. Standing in warm sunset backlight, <Subject 1> (S1) gazes steadily ahead with reddened, glistening eyes and subtle throat swallow of suppressed grief, "
            "<Subject 1> (S1) speaks with quiet trembling vulnerability (0.18s-3.55s): <d>[Chinese] 有没有可能，我也遇上了更好的，可我还是选择了你。</d> "
            "with accurate lip-sync, his brows drawing together tenderly on the final words before his lips close softly."
        ),
    },
]


def generate_panel_spark(base_char_png: Path, gender: str, desc: str, out_png: Path, seed: int) -> Path:
    if out_png.is_file() and out_png.stat().st_size > 1024:
        return out_png
    raw = out_png.with_suffix(".raw.png")
    prompt = (
        f"The {gender} in <Picture 1> is <Subject 1>. "
        f"The target image shows a photorealistic live-action {desc}; "
        "<Subject 1> is 100% preserved in exact facial bone structure, eye shape, nose, hairstyle, and clothing collar from <Picture 1>. "
        "Pure solid white studio background RGB(255,255,255), soft studio portrait lighting, authentic Asian skin pores, zero text, zero watermarks."
    )
    generate_spark_h3_image(prompt=prompt, out_path=raw, ref_images=[base_char_png], aspect_ratio="1:1", seed=seed, steps=6, out_1k_path=out_png)
    raw.unlink(missing_ok=True)
    return out_png


def run_single_condition(beat: Dict[str, Any], cond_name: str, char_ref_sheet: Path, bdir: Path, seed: int) -> Path:
    cdir = bdir / cond_name
    cdir.mkdir(parents=True, exist_ok=True)
    out_mp4 = cdir / "clip.mp4"
    if out_mp4.is_file() and out_mp4.stat().st_size > 10000:
        return out_mp4

    case_dir = TRAIN_ROOT / beat["case_path"]
    bs = json.loads((case_dir / "beat_spec.json").read_text(encoding="utf-8"))
    scene_plate = Path(bs["asset_files"]["scene_clean"])
    voice_wav = Path(bs["voice_files"][beat["role_id"]])

    # 1. Generate shot keyframe from `scene_plate` (<Picture 1>) + `char_ref_sheet` (<Picture 2>) with SAME seed!
    kf_png = cdir / "keyframe_1k.png"
    if not kf_png.is_file():
        kf_raw = cdir / "kf.raw.png"
        kf_prompt = (
            "The interior/exterior architecture and cinema lighting in <Picture 1> are <Subject 1>. "
            f"The {beat['gender']} in <Picture 2> is <Subject 2>. "
            "The target image shows a photorealistic 35mm live-action medium close-up cinema frame; "
            "<Subject 1> is preserved in lighting and background bokeh; "
            "<Subject 2> preserves exact facial identity, hairstyle, and outfit from <Picture 2>. "
            + beat["kf_prompt"]
            + " Crisp 35mm cinema photography, zero text, zero subtitles."
        )
        generate_spark_h3_image(
            prompt=kf_prompt, out_path=kf_raw, ref_images=[scene_plate, char_ref_sheet],
            aspect_ratio="16:9", seed=seed, steps=6, out_1k_path=kf_png,
        )
        kf_raw.unlink(missing_ok=True)

    # 2. Render H3 Video on 5090 with SAME seed, SAME prompt, varying ONLY `<Picture 1>` (derived KF) & `<Picture 2>` (`char_ref_sheet`)!
    h3_prompt = (
        "subject_definitions:\n"
        "<Picture 1> is the opening medium close-up cinema frame.\n"
        f"<Subject 1> (S1) is the {beat['gender']} matching the facial identity and expression references in <Picture 2>.\n"
        "<Audio 1> is the voice-timbre reference for <Subject 1> (S1).\n\n"
        "summary:\n"
        "[keyframe completion + reference generation + audio reference] Expressive 35mm live-action medium close-up starting from <Picture 1>.\n\n"
        "retention_analysis:\n"
        "<Picture 1> (opening frame): fully_preserved - anchor opening composition and lighting.\n"
        "<Subject 1>: fully_preserved - retain exact facial identity, hair, outfit, and authentic expression morphology from <Picture 2>.\n"
        "<Audio 1>: reference - guides <Subject 1>'s voice timbre and accurate lip-sync.\n\n"
        "detailed_description:\n"
        "Live-action 35mm cinema photography, authentic human facial expressions and crisp syllable-accurate lip-sync, without any text or captions.\n"
        + beat["h3_action"] + "\n\n"
        "overall_soundscape:\n"
        "Quiet controlled location acoustics; clean close-mic vocals and subtle cloth movement only, zero music.\n\n"
        "non_diegetic_music:\n"
        "N/A"
    )
    (cdir / "h3_prompt.txt").write_text(h3_prompt, encoding="utf-8")
    H3R.run_comfy_5090(
        out_mp4,
        prompt=h3_prompt,
        ref_images=[kf_png, char_ref_sheet],
        ref_audios=[voice_wav],
        ratio="16:9",
        resolution="512p",
        duration=beat["duration_s"],
        seed=seed,
        unet_name=H3R.DEFAULT_REF_UNET,
        steps=14,
        use_pika_lora=False,
        lock_frame0=True,
    )
    return out_mp4


BLIND_EVAL_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "observations": {
            "type": "object",
            "properties": {"V1": {"type": "string"}, "V2": {"type": "string"}, "V3": {"type": "string"}},
            "required": ["V1", "V2", "V3"],
            "additionalProperties": False,
        },
        "scores": {
            "type": "object",
            "properties": {
                "V1": {
                    "type": "object",
                    "properties": {
                        "expression_accuracy": {"type": "number"},
                        "transition_naturalness": {"type": "number"},
                        "lip_sync_cleanliness": {"type": "number"},
                        "identity_fidelity": {"type": "number"},
                    },
                    "required": ["expression_accuracy", "transition_naturalness", "lip_sync_cleanliness", "identity_fidelity"],
                    "additionalProperties": False,
                },
                "V2": {
                    "type": "object",
                    "properties": {
                        "expression_accuracy": {"type": "number"},
                        "transition_naturalness": {"type": "number"},
                        "lip_sync_cleanliness": {"type": "number"},
                        "identity_fidelity": {"type": "number"},
                    },
                    "required": ["expression_accuracy", "transition_naturalness", "lip_sync_cleanliness", "identity_fidelity"],
                    "additionalProperties": False,
                },
                "V3": {
                    "type": "object",
                    "properties": {
                        "expression_accuracy": {"type": "number"},
                        "transition_naturalness": {"type": "number"},
                        "lip_sync_cleanliness": {"type": "number"},
                        "identity_fidelity": {"type": "number"},
                    },
                    "required": ["expression_accuracy", "transition_naturalness", "lip_sync_cleanliness", "identity_fidelity"],
                    "additionalProperties": False,
                },
            },
            "required": ["V1", "V2", "V3"],
            "additionalProperties": False,
        },
        "ranking": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 3},
    },
    "required": ["observations", "scores", "ranking"],
    "additionalProperties": False,
}


def main() -> int:
    EXP_DIR.mkdir(parents=True, exist_ok=True)
    summary_rows = []

    for idx, beat in enumerate(BEATS, 1):
        bid = beat["beat_id"]
        bdir = EXP_DIR / bid
        bdir.mkdir(parents=True, exist_ok=True)
        case_dir = TRAIN_ROOT / beat["case_path"]
        bs = json.loads((case_dir / "beat_spec.json").read_text(encoding="utf-8"))
        neutral_png = Path(bs["asset_files"][beat["role_id"]])

        print(f"\n=== [{bid}] Building Expression Multi-View Sheets on Spark ===", flush=True)
        open_tr = generate_panel_spark(neutral_png, beat["gender"], beat["open_expr_tr"], bdir / "panels/open_tr.png", 8800 + idx * 10 + 1)
        open_br = generate_panel_spark(neutral_png, beat["gender"], beat["open_expr_br"], bdir / "panels/open_br.png", 8800 + idx * 10 + 2)
        sheet_b = compose_three_panel_sheet(neutral_png, open_tr, open_br, bdir / "sheet_B_open_expr_multiview.png")

        closed_tr = generate_panel_spark(neutral_png, beat["gender"], beat["closed_expr_tr"], bdir / "panels/closed_tr.png", 8800 + idx * 10 + 3)
        closed_br = generate_panel_spark(neutral_png, beat["gender"], beat["closed_expr_br"], bdir / "panels/closed_br.png", 8800 + idx * 10 + 4)
        sheet_c = compose_three_panel_sheet(neutral_png, closed_tr, closed_br, bdir / "sheet_C_closed_ocular_multiview.png")

        seed = 77000 + idx * 100
        print(f"=== [{bid}] Rendering A / B / C Videos on 5090 (same seed={seed}) ===", flush=True)
        mp4_a = run_single_condition(beat, "Cond_A_Neutral", neutral_png, bdir, seed)
        mp4_b = run_single_condition(beat, "Cond_B_OpenExpr_Multiview", sheet_b, bdir, seed)
        mp4_c = run_single_condition(beat, "Cond_C_ClosedLip_DualExpr_Multiview", sheet_c, bdir, seed)

        # Render 3-way side-by-side comparison MP4 `[A: Neutral | B: Open-Expr Multiview | C: Closed-Lip Dual-Expr Multiview]`
        grid_mp4 = bdir / f"{bid}_ABC_comparison.mp4"
        fc = (
            "[0:v]scale=480:270,fps=24[v0];"
            "[1:v]scale=480:270,fps=24[v1];"
            "[2:v]scale=480:270,fps=24[v2];"
            "[v0][v1][v2]hstack=inputs=3,format=yuv420p[vout]"
        )
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error", "-i", str(mp4_a), "-i", str(mp4_b), "-i", str(mp4_c),
                "-filter_complex", fc, "-map", "[vout]", "-map", "2:a",
                "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-c:a", "aac", "-b:a", "160k", "-shortest",
                str(grid_mp4),
            ],
            check=True,
        )

        # Blind evaluation via Argon (`V1=B, V2=C, V3=A` scrambled!)
        eval_prompt = (
            f"请盲审对比以下同一场戏的 3 条候选视频（`V1.mp4`, `V2.mp4`, `V3.mp4`）与角色标准五官图 `Ref_Identity.png`：\n"
            f"- 戏剧与表情目标：{beat['title']} ｜ {beat['h3_action']}\n"
            "请从 4 个维度（每项 0–25 分，严禁迎合，实事求是抓副作用！）打分：\n"
            "1. `expression_accuracy`：目标潜台词情绪（笑意/震惊/红眼含泪）到位程度；\n"
            "2. `transition_naturalness`：起止表情变化是否自然演进（若还未触发转折就提前锁死表情，或全程僵在一个夸张表情上，重扣分！）；\n"
            "3. `lip_sync_cleanliness`：未说话时嘴唇是否自然闭合、说话时口型是否干净闭合准确（若因张嘴习惯导致未开口先张嘴或闭不上嘴，重扣分！）；\n"
            "4. `identity_fidelity`：五官骨相与 `Ref_Identity.png` 是否一致、有无二次重绘变形显老。"
        )
        blind_res = VAJ.call_argon_multimodal(
            eval_prompt,
            [
                {"kind": "image", "path": neutral_png, "anon_name": "Ref_Identity.png", "caption": "角色0%中性真身基准图"},
                {"kind": "video", "path": mp4_b, "anon_name": "V1.mp4", "caption": "匿名候选 V1"},
                {"kind": "video", "path": mp4_c, "anon_name": "V2.mp4", "caption": "匿名候选 V2"},
                {"kind": "video", "path": mp4_a, "anon_name": "V3.mp4", "caption": "匿名候选 V3"},
            ],
            schema=BLIND_EVAL_SCHEMA,
            effort="medium",
        )
        map_back = {"A_Neutral": blind_res["scores"]["V3"], "B_OpenExpr_MV": blind_res["scores"]["V1"], "C_ClosedLip_MV": blind_res["scores"]["V2"]}
        obs_back = {"A_Neutral": blind_res["observations"]["V3"], "B_OpenExpr_MV": blind_res["observations"]["V1"], "C_ClosedLip_MV": blind_res["observations"]["V2"]}
        inv_v = {"V1": "B_OpenExpr_MV", "V2": "C_ClosedLip_MV", "V3": "A_Neutral"}
        row = {
            "beat_id": bid,
            "title": beat["title"],
            "ranking": [inv_v.get(x, x) for x in blind_res["ranking"]],
            "totals": {k: sum(v.values()) for k, v in map_back.items()},
            "scores": map_back,
            "observations": obs_back,
            "grid_mp4": str(grid_mp4),
        }
        summary_rows.append(row)
        print(f"  -> [{bid}] Totals: {row['totals']} | Ranking: {row['ranking']}", flush=True)

    out_json = EXP_DIR / "ab_experiment_report.json"
    out_json.write_text(json.dumps(summary_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nSaved full A/B/C report to {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
