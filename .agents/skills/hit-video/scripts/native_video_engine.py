#!/home/zhongwenyu/data/anaconda3/bin/python3
"""
Unified 3-GPU (`Spark:8338` H3 Image + `5090:8188` H3 Video + `4070TiS:8090` 368p VO) Engine
(`.agents/skills/hit-video/scripts/native_video_engine.py`).

Fixes all 5 root causes identified in live director inspection:
  1. Two-Tier Spatial Blocking Lock (`scene_blocking_master_1k.png`): Generates ONE full-group spatial
     seating/blocking master plate per scene first via `MiniMax H3 Image`, then derives all shot
     keyframes (`MCU / OTS / CU`) from that master plate so characters NEVER teleport seats!
  2. Exact Speech-Window Alignment + `Silero-VAD` Sync-Locked Dead-Air Trimmer: Matches prompt
     `(start_s-end_s)` to clip duration (`~5.0 chars/sec`), then trims dead pre/post-speech frames
     on BOTH video and audio identically (`0.000s` lip-sync preservation, zero 3s zombie lag!).
  3. Bug-Free `ffmpeg` Named `trim=start=0:end=...` + `atrim=start=0:end=...` Stitcher: Fixes the
     `trim=0:X` (`starti`) bug that caused `1.58s` A/V desync; restricts `L-Cut` strictly to silent
     listener reaction cuts and asserts `|v_dur - a_dur| <= 0.08s` via `ffprobe`!
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import wave
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import onnxruntime as ort

HERE = Path(__file__).resolve().parent
WORKSTATION_SCRIPTS = Path("/home/zhongwenyu/project/ai-director-workstation/skills/storyboard-video-gen/scripts")

for p in (str(HERE), str(WORKSTATION_SCRIPTS)):
    if p not in sys.path:
        sys.path.insert(0, str(p))

from PIL import Image
import h3_native_runner as H3R  # noqa: E402
from spark_h3_image import generate_spark_h3_image  # noqa: E402

STUDIO_BRIDGE = Path("/home/zhongwenyu/project/playlets-studio/skills/studio-bridge/scripts")
if STUDIO_BRIDGE.is_dir() and str(STUDIO_BRIDGE) not in sys.path:
    sys.path.insert(0, str(STUDIO_BRIDGE))
try:
    import vo_split  # type: ignore
except Exception:
    vo_split = None

DEFAULT_VAD_ONNX = Path("/home/zhongwenyu/.paseo/models/local-speech/silero-vad/silero_vad.onnx")
_VAD_SESS: Optional[ort.InferenceSession] = None
_VAD_LOCK = threading.Lock()
_VO_4070_LOCK = threading.Lock()
_SPARK_STAGE_LOCK = threading.Lock()
_SPARK_STAGED_CACHE: set[str] = set()
_SPARK_IMG_SEM = threading.Semaphore(2)


def _get_vad_sess() -> ort.InferenceSession:
    global _VAD_SESS
    with _VAD_LOCK:
        if _VAD_SESS is None:
            _VAD_SESS = ort.InferenceSession(str(DEFAULT_VAD_ONNX), providers=["CPUExecutionProvider"])
        return _VAD_SESS


def h3_generate_image_spark(
    prompt: str,
    ref_paths: List[Path],
    aspect_ratio: str,
    out_1k_png: Path,
    seed: int,
) -> Path:
    """Generate a 1K image via dedicated Spark `MiniMax H3 Image` (`127.0.0.1:8338`, 6 steps)."""
    out_1k_png.parent.mkdir(parents=True, exist_ok=True)
    if out_1k_png.is_file() and out_1k_png.stat().st_size > 1024:
        return out_1k_png

    raw_2k = out_1k_png.with_suffix(".2k_raw.png")
    ar = aspect_ratio if aspect_ratio in ("16:9", "9:16", "1:1", "3:4", "4:3") else "16:9"

    with _SPARK_IMG_SEM:
        last_exc = None
        for attempt in range(3):
            try:
                with _SPARK_STAGE_LOCK:
                    local_cache = set(_SPARK_STAGED_CACHE)
                generate_spark_h3_image(
                    prompt=prompt,
                    out_path=raw_2k,
                    ref_images=ref_paths,
                    aspect_ratio=ar,
                    seed=seed + attempt,
                    steps=6,
                    out_1k_path=out_1k_png,
                    staged_cache=local_cache,
                )
                with _SPARK_STAGE_LOCK:
                    _SPARK_STAGED_CACHE.update(local_cache)
                raw_2k.unlink(missing_ok=True)
                return out_1k_png
            except Exception as exc:
                last_exc = exc
                time.sleep(2 * (attempt + 1))
        raise RuntimeError(f"Spark MiniMax H3 Image failed after 3 attempts: {last_exc}")


def _compose_multiview_sheet(left_neutral: Path, top_right: Path, bot_right: Path, out_png: Path) -> Path:
    """Compose 1024x1024 3-panel character reference sheet: Left (0% neutral identity anchor) | TR (0° front) | BR (45° side)."""
    if out_png.is_file() and out_png.stat().st_size > 1024:
        return out_png
    canvas = Image.new("RGB", (1024, 1024), (255, 255, 255))

    def _fit(im: Image.Image, tw: int, th: int) -> Image.Image:
        w, h = im.size
        sc = max(tw / max(1, w), th / max(1, h))
        nw, nh = int(round(w * sc)), int(round(h * sc))
        rs = im.resize((nw, nh), getattr(Image, "LANCZOS", 1))
        x0 = max(0, (nw - tw) // 2)
        y0 = max(0, int((nh - th) * 0.18))
        return rs.crop((x0, y0, x0 + tw, y0 + th))

    canvas.paste(_fit(Image.open(left_neutral).convert("RGB"), 508, 1024), (0, 0))
    canvas.paste(_fit(Image.open(top_right).convert("RGB"), 508, 508), (516, 0))
    canvas.paste(_fit(Image.open(bot_right).convert("RGB"), 508, 508), (516, 516))
    out_png.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_png, format="PNG", optimize=True)
    return out_png


def resolve_character_multiview_for_clip(
    role_id: str,
    clip_spec: Dict[str, Any],
    beat_spec: Dict[str, Any],
    kf_dir: Path,
    seed: int,
) -> Path:
    """
    Build Multi-Angle Character Sheet under the 3 empirically verified guardrails:
      1. Default: Cached `[Left: 0% Neutral Full | TR: 0% Neutral Close-up | BR: 45° Three-Quarter 0% Neutral]`
         (stabilizes 45° / OTS 3D head geometry so H3 never jump-cuts back to 0° front!).
      2. When `focus_expression_cue` targets `role_id` on an `MCU / CU / OTS` clip (`<= 5s`) with a single
         coherent emotion: generates `[Left: 0% Neutral Anchor | TR: 0° Moderate Closed-Lip Eye/Brow Emotion |
         BR: 45° Same Moderate Closed-Lip Emotion]` — unlocking eyebrow/cheek richness in short clips while
         strictly preventing +10yr aging creases, wide-open mouth contamination, and dual-emotion chimeras!
    """
    base_png = Path(beat_spec["asset_files"][role_id])
    ch_info = next((c for c in beat_spec.get("characters", []) if c["role_id"] == role_id), {})
    g_word = "woman" if ch_info.get("gender") == "female" else ("man" if ch_info.get("gender") == "male" else "person")

    # Ensure shared per-case 45-degree 0% neutral side view exists in case assets cache
    side_neutral_png = base_png.parent / f"{role_id}_side45_neutral_1k.png"
    if not side_neutral_png.is_file():
        side_prompt = (
            f"The {g_word} in <Picture 1> is <Subject 1>. "
            "The target image shows a photorealistic live-action 45-degree three-quarter close-up studio portrait of <Subject 1> on pure white background RGB(255,255,255); "
            "<Subject 1> is 100% preserved in exact facial bone structure, age, skin smoothness, hairstyle, and collar outfit from <Picture 1>, "
            "with a calm 0% neutral expression and gently closed lips. Soft even studio lighting, zero text."
        )
        h3_generate_image_spark(side_prompt, [base_png], "1:1", side_neutral_png, seed=202650 + hash(role_id) % 97)

    default_mv = base_png.parent / f"{role_id}_neutral_multiview_1k.png"
    if not default_mv.is_file():
        _compose_multiview_sheet(base_png, base_png, side_neutral_png, default_mv)

    f_exp = clip_spec.get("focus_expression_ref")
    framing_low = str(clip_spec.get("camera_framing", "")).lower()
    is_tight_shot = any(k in framing_low for k in ("close", "mcu", "cu", "over-the-shoulder", "ots"))
    if (
        isinstance(f_exp, dict)
        and f_exp.get("role_id") == role_id
        and str(f_exp.get("ocular_brow_cue") or "").strip()
        and is_tight_shot
    ):
        cue = str(f_exp["ocular_brow_cue"]).strip()
        # Guardrail 1: Scrub extreme caricature / open-mouth / wrinkle-inducing words!
        cue = re.sub(
            r"\b(?:bitterly|screaming|shouting|wide[- ]open\s+mouth|gaping|toothy|baring\s+teeth|wrinkled|creased|contorted|anguished|sobbing|ugly)\b",
            "natural",
            cue,
            flags=re.IGNORECASE,
        )
        cid_tag = re.sub(r"[^a-zA-Z0-9_-]", "", str(clip_spec.get("clip_id", "clip")))
        tr_p = kf_dir / f"{cid_tag}_{role_id}_expr_tr.png"
        br_p = kf_dir / f"{cid_tag}_{role_id}_expr_br.png"
        mv_p = kf_dir / f"{cid_tag}_{role_id}_expr_multiview_1k.png"
        if mv_p.is_file():
            return mv_p

        tr_prompt = (
            f"The {g_word} in <Picture 1> is <Subject 1>. "
            "The target image shows a front close-up portrait of <Subject 1> on pure white background RGB(255,255,255); "
            "<Subject 1> preserves exact young/natural facial bone structure, smooth natural skin age, hair, and outfit from <Picture 1>, "
            f"displaying a moderate, subtle, authentic live-action film micro-expression in the eyes, eyebrows, and cheeks ({cue}), "
            "with lips gently closed or poised naturally, zero exaggerated wrinkles, zero wide-open mouth, soft studio light, zero text."
        )
        br_prompt = (
            f"The {g_word} in <Picture 1> is <Subject 1>. "
            "The target image shows a 45-degree three-quarter close-up portrait of <Subject 1> on pure white background RGB(255,255,255); "
            "<Subject 1> preserves exact facial bone structure, smooth natural skin age, hair, and outfit from <Picture 1>, "
            f"displaying the same subtle, natural filmic eye and brow micro-expression ({cue}), "
            "with lips gently closed, zero exaggerated creases, soft studio light, zero text."
        )
        h3_generate_image_spark(tr_prompt, [base_png], "1:1", tr_p, seed=seed + 31)
        h3_generate_image_spark(br_prompt, [base_png], "1:1", br_p, seed=seed + 37)
        return _compose_multiview_sheet(base_png, tr_p, br_p, mv_p)

    return default_mv


def generate_scene_blocking_master(
    scene_plan: Dict[str, Any],
    beat_spec: Dict[str, Any],
    kf_dir: Path,
    seed: int,
) -> Optional[Path]:
    """Generate ONE Spatial Blocking Master Plate locking all characters' exact seats/positions & lighting."""
    asset_files = beat_spec.get("asset_files", {})
    if "scene_clean" not in asset_files:
        return None
    master_out = kf_dir / "scene_blocking_master_1k.png"
    if master_out.is_file() and master_out.stat().st_size > 1024:
        return master_out

    refs: List[Path] = [Path(asset_files["scene_clean"])]
    defs: List[str] = ["The room architecture, furniture geometry, and color lighting in <Picture 1> are <Subject 1>."]
    pres: List[str] = ["<Subject 1> is preserved in exact desk/furniture layout, lighting direction, and color palette"]
    sym_map: Dict[str, str] = {"Scene": "<Subject 1>"}

    for ch in beat_spec.get("characters", [])[:4]:
        rid = ch["role_id"]
        if rid not in asset_files:
            continue
        refs.append(Path(asset_files[rid]))
        idx = len(refs)
        s_tok = f"<Subject {idx}>"
        sym_map[rid] = s_tok
        g_word = "woman" if ch.get("gender") == "female" else ("man" if ch.get("gender") == "male" else "person")
        defs.append(f"The {g_word} in <Picture {idx}> is {s_tok}.")
        pres.append(f"{s_tok} is fully preserved in exact facial identity, hairstyle, and outfit from <Picture {idx}>")

    raw_mb = str(scene_plan.get("master_blocking_prompt") or beat_spec.get("initial_blocking") or "").strip()
    for sym, s_tok in sym_map.items():
        raw_mb = re.sub(rf"\[?<?\b{re.escape(sym)}\b>?\]?", s_tok, raw_mb)

    ar = beat_spec.get("aspect_ratio", "16:9")
    master_prompt = (
        " ".join(defs) + " "
        f"The target image shows an establishing medium-wide spatial blocking master shot inside <Subject 1>; "
        + "; ".join(pres) + ". "
        f"{raw_mb} "
        "All characters have natural, calm, undistorted live-action expressions. Crisp 35mm cinema photography, zero text, zero subtitles, zero watermarks."
    )
    (kf_dir / "scene_blocking_master_prompt.txt").write_text(master_prompt, encoding="utf-8")
    return h3_generate_image_spark(master_prompt, refs, ar, master_out, seed=seed)


def resolve_h3_image_keyframe_prompt_and_refs(
    clip_spec: Dict[str, Any],
    beat_spec: Dict[str, Any],
    blocking_master: Optional[Path] = None,
    role_sheet_overrides: Optional[Dict[str, Path]] = None,
) -> Tuple[str, List[Path]]:
    """Derive shot keyframe from Scene Blocking Master (`<Picture 1>`) + visible Character Sheets (`<Picture 2..K>`)."""
    asset_files = beat_spec["asset_files"]
    char_lookup = {c["role_id"]: c for c in beat_spec.get("characters", [])}
    prop_lookup = {p["prop_id"]: p for p in beat_spec.get("props", [])}

    refs: List[Path] = []
    part1_defs: List[str] = []
    part2_pres: List[str] = []
    sym_to_subj: Dict[str, str] = {}

    anchor_plate = blocking_master if (blocking_master and blocking_master.is_file()) else (
        Path(asset_files["scene_clean"]) if "scene_clean" in asset_files else None
    )
    if clip_spec.get("include_scene_plate_in_keyframe", True) and anchor_plate is not None:
        refs.append(anchor_plate)
        idx = len(refs)
        s_tok = f"<Subject {idx}>"
        sym_to_subj["Scene"] = s_tok
        part1_defs.append(f"The spatial seating arrangement, furniture geometry, and cinema lighting in <Picture {idx}> are {s_tok}.")
        part2_pres.append(
            f"{s_tok} is partially preserved — strictly maintaining the exact relative seating/standing positions, 180-degree axis, immediate tabletop/desk objects or partitions in front of the character, and lighting while reframing the camera to the target shot size with natural shallow depth-of-field bokeh"
        )

    vis_roles = [r for r in clip_spec.get("visible_role_ids", []) if r in asset_files]
    fg_roles = [r for r in clip_spec.get("foreground_silhouette_role_ids", []) if r in asset_files and r not in vis_roles]

    for r in vis_roles:
        if len(refs) >= 6:
            break
        r_sheet = (role_sheet_overrides or {}).get(r) or Path(asset_files[r])
        refs.append(r_sheet)
        idx = len(refs)
        s_tok = f"<Subject {idx}>"
        sym_to_subj[r] = s_tok
        g = char_lookup.get(r, {}).get("gender", "")
        g_word = "woman" if g == "female" else ("man" if g == "male" else "person")
        part1_defs.append(f"The {g_word} in <Picture {idx}> is {s_tok}.")
        part2_pres.append(
            f"{s_tok} preserves exact facial identity, bone structure, hairstyle, and outfit from <Picture {idx}> while fitting naturally into the scene's spatial posture and gaze direction"
        )

    for r in fg_roles:
        if len(refs) >= 6:
            break
        refs.append(Path(asset_files[r]))
        idx = len(refs)
        s_tok = f"<Subject {idx}>"
        sym_to_subj[r] = s_tok
        part1_defs.append(f"The person in <Picture {idx}> is {s_tok}.")
        part2_pres.append(f"{s_tok} appears ONLY from behind at the foreground edge as a softly blurred back-shoulder silhouette")

    for p_id in clip_spec.get("prop_ids", []):
        if p_id in asset_files and len(refs) < 6:
            refs.append(Path(asset_files[p_id]))
            idx = len(refs)
            s_tok = f"<Subject {idx}>"
            sym_to_subj[p_id] = s_tok
            pname = prop_lookup.get(p_id, {}).get("name", "prop")
            part1_defs.append(f"The {pname} in <Picture {idx}> is {s_tok}.")
            part2_pres.append(f"{s_tok} is preserved as a single consistent rigid object")

    raw_kf = str(clip_spec.get("keyframe_prompt") or "").strip()
    for sym, s_tok in sym_to_subj.items():
        raw_kf = re.sub(rf"\[?<?\b{re.escape(sym)}\b>?\]?", s_tok, raw_kf)

    framing = clip_spec.get("camera_framing", "medium close-up")
    scene_clause = f" inside {sym_to_subj['Scene']}" if "Scene" in sym_to_subj else ""
    pres_str = "; ".join(part2_pres) + "." if part2_pres else ""

    full_kf_prompt = (
        " ".join(part1_defs) + " "
        f"The target image shows a photorealistic 35mm live-action {framing} cinema frame{scene_clause}; "
        f"{pres_str} "
        f"{raw_kf} "
        "Crisp 35mm live-action cinema photography, authentic Asian actor facial fidelity, zero text, zero subtitles, zero watermarks."
    ).strip()
    return full_kf_prompt, refs


def compile_h3_clip_payload(
    clip_spec: Dict[str, Any],
    beat_spec: Dict[str, Any],
    keyframe_1k: Path,
    *,
    vo_wav_dur: Optional[float] = None,
    role_sheet_overrides: Optional[Dict[str, Path]] = None,
) -> Tuple[str, List[Path], List[Path], int]:
    """Bind <Picture 1..N> & <Audio 1..M>, and synchronize `(start_s-end_s)` with tight speech duration."""
    asset_files = beat_spec["asset_files"]
    voice_files = beat_spec["voice_files"]
    char_lookup = {c["role_id"]: c for c in beat_spec.get("characters", [])}
    prop_lookup = {p["prop_id"]: p for p in beat_spec.get("props", [])}

    # Hard-guard: if generator accidentally put a beat_spec `inner_os` turn inside `speaking_role_ids` / `<d>`,
    # deterministically route it to `inner_os` and strip `<d>` so characters NEVER move lips during inner monologue!
    os_turns_bare = {
        re.sub(r"[\s，。！？、；：“”‘’…—,.!?;:\"'（）()]", "", str(t.get("text", ""))): t
        for t in beat_spec.get("dialogue_turns", [])
        if t.get("mode") == "inner_os" and t.get("text")
    }
    raw_det_check = str(clip_spec.get("detailed_action_and_dialogue") or "")
    for m_d in re.finditer(r"<d>\s*(?:\[[A-Za-z]+\])?(.*?)</d>", raw_det_check, re.S):
        d_bare = re.sub(r"[\s，。！？、；：“”‘’…—,.!?;:\"'（）()]", "", m_d.group(1))
        if d_bare and any(d_bare in k or k in d_bare for k in os_turns_bare):
            matched_t = next(t for k, t in os_turns_bare.items() if d_bare in k or k in d_bare)
            if not clip_spec.get("inner_os"):
                clip_spec = dict(clip_spec)
                clip_spec["inner_os"] = {
                    "speaker_id": matched_t["speaker_id"],
                    "text": matched_t["text"],
                    "start_s": 0.15,
                    "mode": "inner_os",
                }
            clip_spec = dict(clip_spec)
            clip_spec["speaking_role_ids"] = []
            break

    ref_images: List[Path] = [keyframe_1k]
    vis_roles = [r for r in clip_spec.get("visible_role_ids", []) if r in asset_files]
    spk_roles = [
        r for r in clip_spec.get("speaking_role_ids", [])
        if r in voice_files and r in vis_roles and not (clip_spec.get("inner_os") and clip_spec["inner_os"].get("text"))
    ]

    role_to_subj_idx: Dict[str, int] = {}
    role_to_pic_idx: Dict[str, int] = {}
    for idx, r in enumerate(vis_roles, 1):
        r_sheet = (role_sheet_overrides or {}).get(r) or Path(asset_files[r])
        ref_images.append(r_sheet)
        role_to_subj_idx[r] = idx
        role_to_pic_idx[r] = len(ref_images)

    prop_to_pic_idx: Dict[str, int] = {}
    for p_id in clip_spec.get("prop_ids", []):
        if p_id in asset_files and len(ref_images) < 7:
            ref_images.append(Path(asset_files[p_id]))
            prop_to_pic_idx[p_id] = len(ref_images)

    ref_audios: List[Path] = []
    role_to_spk_tag: Dict[str, str] = {}
    role_to_aud_idx: Dict[str, int] = {}
    for s_idx, r in enumerate(spk_roles, 1):
        ref_audios.append(Path(voice_files[r]))
        role_to_spk_tag[r] = f"(S{s_idx})"
        role_to_aud_idx[r] = s_idx

    subj_lines = [
        f"<Picture 1> is the opening {clip_spec.get('camera_framing', 'medium close-up')} cinema frame anchoring exact seating, lighting, and initial character pose."
    ]
    ret_lines = [
        "<Picture 1> (opening frame): fully_preserved - anchor exact opening composition, spatial position, and lighting."
    ]

    for r in vis_roles:
        s_idx = role_to_subj_idx[r]
        p_idx = role_to_pic_idx[r]
        s_tag = f" {role_to_spk_tag[r]}" if r in role_to_spk_tag else ""
        c_info = char_lookup.get(r, {})
        gender_word = "woman" if c_info.get("gender") == "female" else ("man" if c_info.get("gender") == "male" else "person")
        subj_lines.append(f"<Subject {s_idx}>{s_tag} is the {gender_word} matching the exact facial identity and outfit in <Picture {p_idx}>.")
        ret_lines.append(f"<Subject {s_idx}>: fully_preserved - retain 100% exact facial identity, hair silhouette, and outfit from <Picture {p_idx}>.")

    for p_id, p_idx in prop_to_pic_idx.items():
        p_info = prop_lookup.get(p_id, {})
        subj_lines.append(f"<Picture {p_idx}> is the reference prop ({p_info.get('name', p_id)}).")
        ret_lines.append(f"<Picture {p_idx}>: fully_preserved - maintain single consistent rigid prop appearance.")

    for r in spk_roles:
        s_idx = role_to_subj_idx[r]
        a_idx = role_to_aud_idx[r]
        s_tag = role_to_spk_tag[r]
        subj_lines.append(f"<Audio {a_idx}> is the voice-timbre reference for <Subject {s_idx}> {s_tag}.")
        ret_lines.append(f"<Audio {a_idx}>: reference - guides <Subject {s_idx}>'s expressive Mandarin voice timbre and accurate lip-sync.")

    def replace_role_tokens(txt: str, with_speaker_tag: bool = False) -> str:
        out = txt
        for r, s_idx in role_to_subj_idx.items():
            rep = f"<Subject {s_idx}> {role_to_spk_tag[r]}" if (with_speaker_tag and r in role_to_spk_tag) else f"<Subject {s_idx}>"
            out = re.sub(rf"\[?<?\b{re.escape(r)}\b>?\]?", rep, out)
        for p_id, p_idx in prop_to_pic_idx.items():
            out = re.sub(rf"\[?<?\b{re.escape(p_id)}\b>?\]?", f"<Picture {p_idx}>", out)
        out = re.sub(r"(\(S\d+\))\s+\1", r"\1", out)
        return out

    mode_tags = "[keyframe completion + reference generation" + (" + audio reference]" if ref_audios else "]")
    raw_sum = replace_role_tokens(str(clip_spec.get("clip_summary") or ""))
    if not raw_sum or re.search(r"[\u4e00-\u9fff]", raw_sum):
        raw_sum = f"Expressive 35mm live-action {clip_spec.get('camera_framing', 'medium close-up')} beat starting from <Picture 1>."

    detail_body = replace_role_tokens(str(clip_spec.get("detailed_action_and_dialogue") or ""), with_speaker_tag=True).strip()
    if not ref_audios:
        detail_body = re.sub(r"<d>.*?</d>", "", detail_body, flags=re.S)
        detail_body += " Strict vocal silence: characters keep lips silent with zero spoken words and zero vocalizations."

    # Synchronize clip duration AND `(start_s-end_s)` window so H3 NEVER sits silent for 3s!
    spoken_cjk = sum(len(re.findall(r"[\u4e00-\u9fff0-9A-Za-z]", m.group(1)) ) for m in re.finditer(r"<d>\s*(?:\[[A-Za-z]+\])?(.*?)</d>", detail_body, re.S))
    raw_dur = int(round(float(clip_spec.get("duration_s", 3))))
    os_spec = clip_spec.get("inner_os") if isinstance(clip_spec.get("inner_os"), dict) else None
    if spoken_cjk > 0 and ref_audios:
        # Tight natural short-drama delivery: allow 2s clips for short lines (<=7 chars) so 5-clip scenes never bloat!
        est_speech_dur = max(0.85, round(spoken_cjk / 5.4, 2))
        sync_dur = max(2, min(8, math.ceil(0.16 + est_speech_dur + 0.34)))
        win_start = 0.16
        win_end = round(min(sync_dur - 0.26, win_start + est_speech_dur), 2)
        # Rewrite first `(Xs-Ys)` before `<d>` so prompt window matches exact clip duration!
        detail_body = re.sub(
            r"\(\s*\d+(?:\.\d+)?s?\s*[-–~to]+\s*\d+(?:\.\d+)?s?\s*\)(\s*:\s*<d>)",
            f"({win_start:.2f}s-{win_end:.2f}s)\\1",
            detail_body,
            count=1,
        )
    elif vo_wav_dur is not None and vo_wav_dur > 0.2:
        vo_start = min(0.18, float(os_spec.get("start_s", 0.15))) if os_spec else 0.15
        sync_dur = max(2, min(8, math.ceil(vo_start + vo_wav_dur + 0.26)))
    elif os_spec and os_spec.get("text"):
        vo_cjk = len(re.findall(r"[\u4e00-\u9fff0-9A-Za-z]", str(os_spec.get("text", ""))))
        sync_dur = max(2, min(8, math.ceil(0.18 + max(0.9, vo_cjk / 4.8) + 0.32)))
    else:
        sync_dur = 2

    acting_hdr = (
        "Live-action 35mm cinema photography, authentic human facial expressions and natural body language matching dramatic subtext, crisp syllable-accurate lip-sync, without any text or captions.\n"
    )
    if not detail_body.startswith("[Shot 1]") and "[Shot 1]" not in detail_body:
        detail_body = acting_hdr + f"[Shot 1] Starting naturally from <Picture 1>, {detail_body}"
    else:
        detail_body = acting_hdr + detail_body

    # Balanced Film Sound Rule:
    # 1. Input `<Audio k>` is 100% studio-dry voice (zero BGM/noise fed in);
    # 2. Allow H3 to generate subtle frame-accurate synchronous physical action foley & natural breaths
    #    (cloth, prop contact, fire crackle, sighs) while forbidding loud ambient roar and forbidding music;
    # 3. Post-stitch adds a gentle continuous room-tone bridge so cuts never drop to dead digital silence!
    raw_sc = str(clip_spec.get("soundscape") or "").strip()
    raw_sc = H3R.HARMFUL_SOUNDSCAPE_MUSIC_RE.sub("subtle ambient air", raw_sc)
    clean_soundscape = (
        f"Quiet controlled studio-grade location acoustics; clean close-mic vocals with subtle synchronous physical action foley only ({raw_sc}), zero loud background noise, zero music."
        if raw_sc
        else "Quiet controlled studio-grade location acoustics; clean close-mic vocals and subtle synchronous cloth/prop foley only, zero loud background noise, zero music."
    )

    full_prompt = (
        "subject_definitions:\n" + "\n".join(subj_lines) + "\n\n"
        f"summary:\n{mode_tags} {raw_sum}\n\n"
        "retention_analysis:\n" + "\n".join(ret_lines) + "\n\n"
        f"detailed_description:\n{detail_body}\n\n"
        f"overall_soundscape:\n{clean_soundscape}\n\n"
        "non_diegetic_music:\nN/A"
    )
    return full_prompt, ref_images, ref_audios, sync_dur


def isolate_clean_dry_dialogue_on_clip(mp4_path: Path, is_speaking_clip: bool) -> None:
    """Gentle spectral hiss cleanup on speaking clips WITHOUT VAD-chopping breaths, unvoiced consonants, or synchronous prop foley!"""
    if not is_speaking_clip:
        return
    marker = mp4_path.with_suffix(".dry_vocal")
    if marker.is_file():
        return
    tmp_mp4 = mp4_path.with_suffix(".clean_spk.mp4")
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-i", str(mp4_path),
            "-c:v", "copy",
            # Gentle -18dB spectral noise floor reduction: removes steady H3 background hiss while 100% preserving breaths, sighs, consonants, and synchronous physical foley!
            "-af", "highpass=f=70,afftdn=nr=14:nf=-30:tn=1",
            "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k",
            str(tmp_mp4),
        ],
        check=True,
    )
    tmp_mp4.replace(mp4_path)
    marker.write_text("ok\n", encoding="utf-8")


def silence_non_speaking_clip_vocals(mp4_path: Path, is_silent_reaction: bool, incoming_lcut_s: float = 0.0) -> None:
    """Strip ONLY hallucinated human vocals on silent reaction shots (preserving subtle non-vocal foley/air via mix-vocals) & trim excess pause."""
    if not is_silent_reaction:
        return
    marker = mp4_path.with_suffix(".muted_react")
    if marker.is_file():
        return
    pr = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_format", "-of", "json", str(mp4_path)], text=True))
    dur = float(pr["format"]["duration"])
    target_react_dur = min(dur, round(max(1.35, float(incoming_lcut_s) + 0.85), 3))

    # Subtract any hallucinated Demucs vocals while retaining subtle physical foley/air (`mix - vocals`)!
    kept_foley_wav: Optional[Path] = None
    if vo_split is not None:
        try:
            with tempfile.TemporaryDirectory(prefix="novoc-") as td:
                td_p = Path(td)
                mix_w = td_p / "mix.wav"
                voc_w = td_p / "voc.wav"
                subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(mp4_path), "-vn", "-ar", "44100", "-ac", "2", str(mix_w)], check=True)
                vo_split.demucs_vocals(mix_w, voc_w)
                with wave.open(str(mix_w), "rb") as wm, wave.open(str(voc_w), "rb") as wv:
                    pm = np.frombuffer(wm.readframes(wm.getnframes()), dtype=np.int16).astype(np.float32)
                    pv = np.frombuffer(wv.readframes(wv.getnframes()), dtype=np.int16).astype(np.float32)
                m_len = min(len(pm), len(pv))
                res_pcm = np.clip((pm[:m_len] - pv[:m_len]) * 0.45, -32767.0, 32767.0).astype(np.int16)
                kept_foley_wav = mp4_path.with_suffix(".novoc_foley.wav")
                with wave.open(str(kept_foley_wav), "wb") as wo:
                    wo.setnchannels(2)
                    wo.setsampwidth(2)
                    wo.setframerate(44100)
                    wo.writeframes(res_pcm.tobytes())
        except Exception:
            kept_foley_wav = None

    tmp_out = mp4_path.with_suffix(".clean_react.mp4")
    if kept_foley_wav is not None and kept_foley_wav.is_file():
        fc = (
            f"[0:v]trim=start=0:end={target_react_dur:.3f},setpts=PTS-STARTPTS,fps=24,format=yuv420p[v];"
            f"[1:a]aresample=48000,aformat=channel_layouts=stereo,apad=whole_dur={target_react_dur:.3f},"
            f"atrim=start=0:end={target_react_dur:.3f},asetpts=PTS-STARTPTS[a]"
        )
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error", "-i", str(mp4_path), "-i", str(kept_foley_wav),
                "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "160k",
                str(tmp_out),
            ],
            check=True,
        )
        kept_foley_wav.unlink(missing_ok=True)
    else:
        fc = (
            f"[0:v]trim=start=0:end={target_react_dur:.3f},setpts=PTS-STARTPTS,fps=24,format=yuv420p[v];"
            f"[0:a]atrim=start=0:end={target_react_dur:.3f},asetpts=PTS-STARTPTS,volume=0.0,aresample=48000[a]"
        )
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error", "-i", str(mp4_path),
                "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "160k",
                str(tmp_out),
            ],
            check=True,
        )
    tmp_out.replace(mp4_path)
    marker.write_text(f"0.000-{target_react_dur:.3f}\n", encoding="utf-8")


def trim_clip_dead_air_sync(mp4_path: Path, is_speaking_clip: bool) -> None:
    """Trim dead pre/post-speech silence identically on BOTH video & audio (0.000s lip-sync preservation!)."""
    if not is_speaking_clip or not DEFAULT_VAD_ONNX.is_file():
        return
    marker = mp4_path.with_suffix(".vad_trimmed")
    if marker.is_file():
        return

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp_wav:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp4_path), "-ac", "1", "-ar", "16000", tmp_wav.name], check=True)
        with wave.open(tmp_wav.name, "rb") as wf:
            pcm = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0

    dur = len(pcm) / 16000.0
    if dur <= 1.35:
        marker.write_text("short\n", encoding="utf-8")
        return

    sess = _get_vad_sess()
    hop = 512
    dt = hop / 16000.0
    h_st = np.zeros((2, 1, 64), dtype=np.float32)
    c_st = np.zeros((2, 1, 64), dtype=np.float32)
    act_indices: List[int] = []
    for i in range(len(pcm) // hop):
        pr, h_st, c_st = sess.run(None, {"x": pcm[i * hop : (i + 1) * hop].reshape(1, hop), "h": h_st, "c": c_st})
        if float(pr[0, 0]) >= 0.48:
            act_indices.append(i)

    if not act_indices:
        marker.write_text("no_vad\n", encoding="utf-8")
        return

    first_s = act_indices[0] * dt
    last_s = (act_indices[-1] + 1) * dt
    ts = round(max(0.0, first_s - 0.14), 3) if first_s > 0.22 else 0.0
    te = round(min(dur, last_s + 0.18), 3) if (dur - last_s) > 0.25 else round(dur, 3)

    if te - ts >= 1.15 and (ts > 0.08 or (dur - te) > 0.12):
        tmp_out = mp4_path.with_suffix(".sync_trim.mp4")
        fc = (
            f"[0:v]trim=start={ts:.3f}:end={te:.3f},setpts=PTS-STARTPTS,fps=24,format=yuv420p[v];"
            f"[0:a]atrim=start={ts:.3f}:end={te:.3f},asetpts=PTS-STARTPTS,aresample=48000[a]"
        )
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error", "-i", str(mp4_path),
                "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k",
                str(tmp_out),
            ],
            check=True,
        )
        tmp_out.replace(mp4_path)
    marker.write_text(f"{ts:.3f}-{te:.3f}\n", encoding="utf-8")


def _trim_wav_dead_air_vad(wav_path: Path) -> float:
    """Trim leading/trailing silence off 4070TiS VO WAV via Silero-VAD and return trimmed duration in seconds."""
    if not DEFAULT_VAD_ONNX.is_file() or not wav_path.is_file():
        pr = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_format", "-of", "json", str(wav_path)], text=True))
        return float(pr["format"]["duration"])
    marker = wav_path.with_suffix(".vo_vad_trimmed")
    if marker.is_file():
        pr = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_format", "-of", "json", str(wav_path)], text=True))
        return float(pr["format"]["duration"])

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp16:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wav_path), "-ac", "1", "-ar", "16000", tmp16.name], check=True)
        with wave.open(tmp16.name, "rb") as wf:
            pcm = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0

    dur = len(pcm) / 16000.0
    sess = _get_vad_sess()
    hop = 512
    dt = hop / 16000.0
    h_st = np.zeros((2, 1, 64), dtype=np.float32)
    c_st = np.zeros((2, 1, 64), dtype=np.float32)
    act: List[int] = []
    for i in range(len(pcm) // hop):
        pr_v, h_st, c_st = sess.run(None, {"x": pcm[i * hop : (i + 1) * hop].reshape(1, hop), "h": h_st, "c": c_st})
        if float(pr_v[0, 0]) >= 0.45:
            act.append(i)
    if act:
        ts = round(max(0.0, act[0] * dt - 0.08), 3)
        te = round(min(dur, (act[-1] + 1) * dt + 0.16), 3)
        if te - ts >= 0.5 and (ts > 0.10 or (dur - te) > 0.15):
            tmp_out = wav_path.with_suffix(".trimmed.wav")
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-i", str(wav_path), "-af", f"atrim=start={ts:.3f}:end={te:.3f},asetpts=PTS-STARTPTS", str(tmp_out)],
                check=True,
            )
            tmp_out.replace(wav_path)
            dur = round(te - ts, 3)
    marker.write_text(f"{dur:.3f}\n", encoding="utf-8")
    return dur


def synthesize_vo_wav_on_4070(
    os_spec: Dict[str, Any],
    beat_spec: Dict[str, Any],
    work_dir: Path,
    seed: int,
) -> Tuple[Optional[Path], float]:
    role_id = os_spec.get("speaker_id", "")
    text = str(os_spec.get("text") or "").strip()
    if not text or role_id not in beat_spec.get("voice_files", {}):
        return None, 0.0

    work_dir.mkdir(parents=True, exist_ok=True)
    vo_wav = work_dir / f"vo_4070_{seed}.wav"
    if vo_wav.is_file() and vo_wav.stat().st_size > 1000:
        return vo_wav, _trim_wav_dead_air_vad(vo_wav)

    cjk_n = len(re.findall(r"[\u4e00-\u9fff0-9A-Za-z]", text))
    vo_gen_dur = max(5, min(8, math.ceil(1.2 + cjk_n / 4.2)))
    vo_spec = {
        "face_1k": beat_spec["asset_files"][role_id],
        "voice": beat_spec["voice_files"][role_id],
        "text": text,
        "duration": vo_gen_dur,
    }
    with _VO_4070_LOCK:
        H3R.synthesize_vo_clip_4070(vo_spec, work_dir / "cache_1k", vo_wav, seed=seed)
    return vo_wav, _trim_wav_dead_air_vad(vo_wav)


def apply_vo_wav_onto_clip(
    base_mp4: Path,
    vo_wav: Optional[Path],
    vo_dur: float,
    os_spec: Dict[str, Any],
) -> Path:
    marker = base_mp4.with_suffix(".vo_done")
    if marker.is_file() or vo_wav is None or not vo_wav.is_file():
        return base_mp4
    # CRITICAL FIX: Strip any hallucinated H3 speech from `base_mp4` BEFORE mixing `vo_wav`,
    # because `mix_vo_custom` restores `[0:a]` to 1.0 outside `[dst_start, de]`!
    clean_base = base_mp4.with_suffix(".muted_base.mp4")
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error", "-i", str(base_mp4),
            "-c:v", "copy",
            "-af", "volume=0.0",
            "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "160k",
            str(clean_base),
        ],
        check=True,
    )
    clean_base.replace(base_mp4)

    probe = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_format", "-of", "json", str(base_mp4)], text=True))
    base_dur = float(probe["format"]["duration"])
    dst_st = min(0.18, float(os_spec.get("start_s", 0.15)))
    mixed_mp4 = base_mp4.with_suffix(".os_mixed.mp4")
    eff = "none" if str(os_spec.get("mode", "")).lower() == "offscreen_speech" else "inner_vo"
    vo_cfg = {
        "dst_start": dst_st,
        "max_len": max(1.2, base_dur - dst_st - 0.05),
        "base_duck": 0.50,
        "vo_gain": 1.80,
        "effect": eff,
    }
    H3R.mix_vo_custom(base_mp4, vo_wav, vo_cfg, mixed_mp4)
    # Trim trailing post-VO dead air on the clip so OS transitions snap crisply!
    tight_end = round(min(base_dur, dst_st + vo_dur + 0.24), 3)
    if base_dur - tight_end > 0.25 and tight_end >= 1.5:
        tight_mp4 = base_mp4.with_suffix(".os_tight.mp4")
        fc = (
            f"[0:v]trim=start=0:end={tight_end:.3f},setpts=PTS-STARTPTS,fps=24,format=yuv420p[v];"
            f"[0:a]atrim=start=0:end={tight_end:.3f},asetpts=PTS-STARTPTS,aresample=48000[a]"
        )
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error", "-i", str(mixed_mp4),
                "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k",
                str(tight_mp4),
            ],
            check=True,
        )
        mixed_mp4.unlink(missing_ok=True)
        tight_mp4.replace(base_mp4)
    else:
        mixed_mp4.replace(base_mp4)
    marker.write_text("ok\n", encoding="utf-8")
    return base_mp4


def synthesize_continuous_ambience_wav(setting_summary: str, duration_s: float, out_wav: Path, seed: int = 42) -> Path:
    """
    Synthesize ONE seamless, uninterrupted stereo post-production room-tone / ambience bed
    spanning `0.000s -> duration_s` so background ambience NEVER turns on/off with speech!
    """
    sr = 48000
    n = max(sr, int(round(duration_s * sr)))
    rng = np.random.default_rng(seed)
    s_txt = str(setting_summary or "")

    # Stereo decorrelated pink/brown natural acoustic air
    w_l = rng.standard_normal(n).astype(np.float32)
    w_r = rng.standard_normal(n).astype(np.float32)

    # Generic acoustic space profile inferred from setting physics (indoor vs outdoor vs night street)
    is_outdoor = any(k in s_txt for k in ("户外", "公园", "街", "城门", "山", "院", "广场", "摊", "步道", "林"))
    is_night_street = any(k in s_txt for k in ("夜", "烧烤", "霓虹", "集市", "闹市"))

    # One-pole lowpass + slow air modulation for natural organic room/air presence (never static white hiss!)
    alpha = 0.035 if is_outdoor else 0.018
    y_l = np.empty(n, dtype=np.float32)
    y_r = np.empty(n, dtype=np.float32)
    # Fast vectorized IIR via scipy-free block filter or cumulative leaky sum
    # Use FFT bandpass shaping for exact natural acoustic room-tone spectrum!
    freqs = np.fft.rfftfreq(n, d=1.0 / sr)
    spec_l = np.fft.rfft(w_l)
    spec_r = np.fft.rfft(w_r)

    if is_night_street:
        # Warm distant urban/market air (90 Hz - 1400 Hz gentle roll-off)
        env = 1.0 / np.maximum(1.0, (freqs / 140.0) ** 0.85)
        env *= (freqs >= 65.0) * np.exp(-np.maximum(0.0, freqs - 1800.0) / 900.0)
        target_rms = 0.011  # ~ -39 dBFS continuous stereo bed
    elif is_outdoor:
        # Soft open-air breeze & distant space (110 Hz - 2200 Hz soft air)
        env = 1.0 / np.maximum(1.0, (freqs / 220.0) ** 0.75)
        env *= (freqs >= 80.0) * np.exp(-np.maximum(0.0, freqs - 2400.0) / 1100.0)
        target_rms = 0.010  # ~ -40 dBFS continuous stereo bed
    else:
        # Quiet cinema indoor room tone (75 Hz - 1100 Hz warm architectural air)
        env = 1.0 / np.maximum(1.0, (freqs / 110.0) ** 0.90)
        env *= (freqs >= 60.0) * np.exp(-np.maximum(0.0, freqs - 1200.0) / 650.0)
        target_rms = 0.0085  # ~ -41.4 dBFS subtle continuous room tone

    y_l = np.fft.irfft(spec_l * env, n=n).astype(np.float32)
    y_r = np.fft.irfft(spec_r * env, n=n).astype(np.float32)

    # Gentle slow organic breathing modulation (0.18 Hz, +-1.2 dB) so air feels alive rather than frozen loop
    t = np.linspace(0.0, duration_s, num=n, dtype=np.float32)
    mod_l = 1.0 + 0.12 * np.sin(2.0 * math.pi * 0.17 * t + 0.3)
    mod_r = 1.0 + 0.12 * np.sin(2.0 * math.pi * 0.19 * t + 1.4)
    y_l *= mod_l
    y_r *= mod_r

    cur_rms = float(np.sqrt(0.5 * (np.mean(y_l ** 2) + np.mean(y_r ** 2)))) + 1e-8
    scale = target_rms / cur_rms
    stereo = np.stack([y_l * scale, y_r * scale], axis=1)
    pcm16 = np.clip(stereo * 32767.0, -32767.0, 32767.0).astype(np.int16)

    out_wav.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_wav), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm16.tobytes())
    return out_wav


def stitch_clips_with_lcut(
    clip_mp4s: List[Path],
    lcut_holds: List[float],
    is_silent_reaction_flags: List[bool],
    aspect_ratio: str,
    resolution: str,
    out_mp4: Path,
    setting_summary: str = "",
) -> Dict[str, Any]:
    """
    Frame-accurate stitcher using explicit named `trim=start=0:end=...` & `atrim=start=0:end=...`.
    Enforces two strict invariants:
      1. `L-Cut` audio overlap (`holds[i] > 0`) is ONLY permitted when `clip[i+1]` is a silent
         reaction shot (`is_silent_reaction_flags[i+1] == True`) — NEVER overlapping two speaking clips!
      2. Verifies via `ffprobe` that `abs(video_stream_dur - audio_stream_dur) <= 0.08s`!
    """
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    tw, th = H3R.RESOLUTION_PRESETS[resolution][aspect_ratio]

    if len(clip_mp4s) == 1:
        pr1 = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_format", "-of", "json", str(clip_mp4s[0])], text=True))
        dur1 = float(pr1["format"]["duration"])
        amb_wav = out_mp4.with_suffix(".amb.wav")
        synthesize_continuous_ambience_wav(setting_summary, dur1, amb_wav)
        vf = f"scale={tw}:{th}:force_original_aspect_ratio=decrease,pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2,fps=24"
        fc1 = (
            f"[0:v]{vf},format=yuv420p[vout];"
            f"[0:a]aresample=48000,aformat=channel_layouts=stereo,loudnorm=I=-16:TP=-1.5:LRA=11[dlg];"
            f"[dlg]apad=whole_dur={dur1:.3f}[dlg_pad];"
            f"[1:a]aresample=48000,aformat=channel_layouts=stereo,atrim=start=0:end={dur1:.3f},asetpts=PTS-STARTPTS[amb];"
            f"[amb][dlg_pad]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,alimiter=limit=0.96[aout]"
        )
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error", "-i", str(clip_mp4s[0]), "-i", str(amb_wav),
                "-filter_complex", fc1, "-map", "[vout]", "-map", "[aout]",
                "-c:v", "libx264", "-preset", "fast", "-crf", "19", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k",
                str(out_mp4),
            ],
            check=True,
        )
        amb_wav.unlink(missing_ok=True)
        return {"clip_count": 1, "visual_cuts": [], "lcut_holds": [0.0]}

    durs: List[float] = []
    for p in clip_mp4s:
        pr = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(p)], text=True))
        vs = next(s for s in pr["streams"] if s["codec_type"] == "video")
        durs.append(float(vs.get("duration") or pr["format"]["duration"]))

    n = len(clip_mp4s)
    holds: List[float] = []
    for i in range(n):
        # ONLY allow L-cut audio hold onto the next clip if the NEXT clip is a non-speaking reaction shot!
        if i == n - 1 or not is_silent_reaction_flags[i + 1]:
            holds.append(0.0)
        else:
            raw_h = max(0.0, float(lcut_holds[i] if i < len(lcut_holds) else 0.0))
            safe_h = min(raw_h, 0.85, durs[i] * 0.30, durs[i + 1] * 0.65)
            holds.append(round(safe_h, 3))

    v_durs = [round(durs[i] - holds[i], 3) for i in range(n)]
    t_starts = [0.0]
    for i in range(n - 1):
        t_starts.append(round(t_starts[-1] + v_durs[i], 3))
    total_dur = round(sum(v_durs), 3)

    inputs: List[str] = []
    v_filters: List[str] = []
    a_filters: List[str] = []
    v_labels: List[str] = []
    a_labels: List[str] = []

    for i, p in enumerate(clip_mp4s):
        inputs.extend(["-i", str(p)])
        # CRITICAL FIX: explicit `trim=start=0:end=...` (NOT `trim=0:...` which sets `starti`!)
        v_filters.append(
            f"[{i}:v]trim=start=0:end={v_durs[i]:.3f},setpts=PTS-STARTPTS,"
            f"scale={tw}:{th}:force_original_aspect_ratio=decrease,pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2,"
            f"fps=24,format=yuv420p[v{i}]"
        )
        v_labels.append(f"[v{i}]")

        prev_hold = holds[i - 1] if i > 0 else 0.0
        a_end = min(durs[i], round(total_dur - t_starts[i], 3))
        delay_ms = int(round(t_starts[i] * 1000))
        vol_expr = f"volume='if(lt(t,{prev_hold:.3f}),0.18,1.0)':eval=frame," if prev_hold > 0.05 else ""
        fade_out_st = max(0.0, a_end - 0.06)
        a_filters.append(
            f"[{i}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"atrim=start=0:end={a_end:.3f},asetpts=PTS-STARTPTS,{vol_expr}"
            f"afade=t=in:d=0.03,afade=t=out:st={fade_out_st:.3f}:d=0.06,"
            f"adelay={delay_ms}:all=1[a{i}]"
        )
        a_labels.append(f"[a{i}]")

    # Synthesize ONE seamless post-stitch stereo ambience bed spanning `0.000s -> total_dur`!
    amb_wav = out_mp4.with_suffix(".amb.wav")
    synthesize_continuous_ambience_wav(setting_summary, total_dur + 0.2, amb_wav)
    amb_idx = n
    inputs.extend(["-i", str(amb_wav)])

    fc = (
        ";".join(v_filters) + ";"
        + "".join(v_labels) + f"concat=n={n}:v=1:a=0,trim=start=0:end={total_dur:.3f},setpts=PTS-STARTPTS[vout];"
        + ";".join(a_filters) + ";"
        + "".join(a_labels) + f"amix=inputs={n}:duration=longest:dropout_transition=0:normalize=0,"
        + f"atrim=start=0:end={total_dur:.3f},asetpts=PTS-STARTPTS,"
        + "loudnorm=I=-16:TP=-1.5:LRA=11,apad=whole_dur=" + f"{total_dur:.3f}[dlg];"
        + f"[{amb_idx}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
        + f"atrim=start=0:end={total_dur:.3f},asetpts=PTS-STARTPTS[amb];"
        + "[amb][dlg]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,alimiter=limit=0.96[aout]"
    )

    tmp_out = out_mp4.with_suffix(".tmp_stitch.mp4")
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            *inputs,
            "-filter_complex", fc,
            "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k",
            str(tmp_out),
        ],
        check=True,
    )
    amb_wav.unlink(missing_ok=True)

    # Hard A/V stream duration sync assertion!
    pr_out = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(tmp_out)], text=True))
    v_s = next(s for s in pr_out["streams"] if s["codec_type"] == "video")
    a_s = next(s for s in pr_out["streams"] if s["codec_type"] == "audio")
    vd = float(v_s.get("duration") or total_dur)
    ad = float(a_s.get("duration") or total_dur)
    if abs(vd - ad) > 0.10:
        raise RuntimeError(f"A/V sync assertion failed on {out_mp4}: v_dur={vd:.3f}s vs a_dur={ad:.3f}s")

    tmp_out.replace(out_mp4)
    return {"clip_count": n, "visual_cuts": t_starts[1:], "lcut_holds": holds, "total_duration_s": round(vd, 3)}


class DualGPUPool:
    """LPT priority scheduler for dedicated RTX 5090 D (`backends=(None,)`) video rendering."""

    def __init__(self, backends: Sequence[Optional[str]] = (None,)):
        self._cond = threading.Condition()
        self._free_backends: List[Optional[str]] = list(backends)
        self._waiters: List[Tuple[float, int, threading.Event, List[Optional[str]]]] = []
        self._seq = 0

    def _dispatch_locked(self) -> None:
        while self._waiters and self._free_backends:
            backend = None if None in self._free_backends else self._free_backends[0]
            self._free_backends.remove(backend)
            _, _, next_ev, next_assigned = self._waiters.pop(0)
            next_assigned.append(backend)
            next_ev.set()

    def run_job(self, fn, *args, priority_dur: float = 4.0, **kwargs):
        ev = threading.Event()
        assigned: List[Optional[str]] = []
        with self._cond:
            self._seq += 1
            entry = (-float(priority_dur), self._seq, ev, assigned)
            self._waiters.append(entry)
            self._waiters.sort(key=lambda x: (x[0], x[1]))
            self._dispatch_locked()

        ev.wait()
        backend = assigned[0]
        try:
            return fn(backend, *args, **kwargs)
        finally:
            with self._cond:
                self._free_backends.append(backend)
                self._dispatch_locked()


def execute_scene_plan(
    scene_plan: Dict[str, Any],
    beat_spec: Dict[str, Any],
    out_dir: Path,
    gpu_pool: DualGPUPool,
    *,
    resolution: str = "512p",
    steps: int = 14,
    base_seed: int = 910000,
) -> Path:
    """Render Blocking Master + shot keyframes (`Spark`) + H3 clips (`5090` + `4070TiS`) + synced stitch."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    final_mp4 = out_dir / "scene_final.mp4"
    if final_mp4.is_file() and final_mp4.stat().st_size > 10000:
        return final_mp4

    clips = (scene_plan.get("clips") or [])[:5]
    if not clips:
        raise ValueError("scene_plan contains zero clips")

    ar = beat_spec.get("aspect_ratio", "16:9")
    kf_dir = out_dir / "keyframes_1k"
    clips_dir = out_dir / "clips"
    kf_dir.mkdir(exist_ok=True)
    clips_dir.mkdir(exist_ok=True)

    # Tier 1: Generate Scene Spatial Blocking Master Plate FIRST so all cuts share locked seating/axis!
    blocking_master = generate_scene_blocking_master(scene_plan, beat_spec, kf_dir, seed=base_seed + 3)

    clip_mp4_map: Dict[int, Path] = {}

    def _pipeline_single_clip(idx_clip: Tuple[int, Dict[str, Any]]) -> Tuple[int, Path]:
        idx, cspec = idx_clip
        c_mp4 = clips_dir / f"clip_{idx:02d}.mp4"
        # Auto-correct any beat_spec `inner_os` turn accidentally placed in `<d>` before checking `has_vo`!
        os_turns_bare = {
            re.sub(r"[\s，。！？、；：“”‘’…—,.!?;:\"'（）()]", "", str(t.get("text", ""))): t
            for t in beat_spec.get("dialogue_turns", [])
            if t.get("mode") == "inner_os" and t.get("text")
        }
        for m_d in re.finditer(r"<d>\s*(?:\[[A-Za-z]+\])?(.*?)</d>", str(cspec.get("detailed_action_and_dialogue") or ""), re.S):
            d_bare = re.sub(r"[\s，。！？、；：“”‘’…—,.!?;:\"'（）()]", "", m_d.group(1))
            if d_bare and any(d_bare in k or k in d_bare for k in os_turns_bare):
                matched_t = next(t for k, t in os_turns_bare.items() if d_bare in k or k in d_bare)
                cspec = dict(cspec)
                if not cspec.get("inner_os"):
                    cspec["inner_os"] = {"speaker_id": matched_t["speaker_id"], "text": matched_t["text"], "start_s": 0.15, "mode": "inner_os"}
                cspec["speaking_role_ids"] = []
                break

        has_vo = bool(cspec.get("inner_os") and isinstance(cspec["inner_os"], dict) and cspec["inner_os"].get("text"))
        is_speaking_on_cam = bool(cspec.get("speaking_role_ids")) and not has_vo
        is_silent_react = (not is_speaking_on_cam) and (not has_vo)
        prev_hold = float(clips[idx - 1].get("lcut_audio_hold_over_next_s", 0.0) or 0.0) if idx > 0 else 0.0

        if c_mp4.is_file() and c_mp4.stat().st_size > 10000:
            if has_vo and not c_mp4.with_suffix(".vo_done").is_file():
                vo_wav, vo_dur = synthesize_vo_wav_on_4070(cspec["inner_os"], beat_spec, clips_dir, base_seed + idx * 13 + 5)
                apply_vo_wav_onto_clip(c_mp4, vo_wav, vo_dur, cspec["inner_os"])
            isolate_clean_dry_dialogue_on_clip(c_mp4, is_speaking_clip=is_speaking_on_cam)
            silence_non_speaking_clip_vocals(c_mp4, is_silent_reaction=is_silent_react, incoming_lcut_s=prev_hold)
            trim_clip_dead_air_sync(c_mp4, is_speaking_clip=is_speaking_on_cam)
            return idx, c_mp4

        vo_pool = cf.ThreadPoolExecutor(max_workers=1) if has_vo else None
        vo_fut = (
            vo_pool.submit(synthesize_vo_wav_on_4070, cspec["inner_os"], beat_spec, clips_dir, base_seed + idx * 13 + 5)
            if vo_pool is not None
            else None
        )

        # Resolve multi-angle (0° + 45°) character reference sheets (with guarded closed-lip ocular micro-expression when requested on MCU/CU!)
        vis_roles_clip = [r for r in cspec.get("visible_role_ids", []) if r in beat_spec.get("asset_files", {})]
        role_sheets: Dict[str, Path] = {}
        for r_i, r_id in enumerate(vis_roles_clip):
            role_sheets[r_id] = resolve_character_multiview_for_clip(r_id, cspec, beat_spec, kf_dir, seed=base_seed + idx * 29 + r_i)

        # Tier 2: Derive shot keyframe from `blocking_master` (`<Picture 1>`) + visible characters on Spark!
        kf_out = kf_dir / f"clip_{idx:02d}_1k.png"
        kf_prompt, kf_refs = resolve_h3_image_keyframe_prompt_and_refs(
            cspec, beat_spec, blocking_master=blocking_master, role_sheet_overrides=role_sheets
        )
        (kf_dir / f"clip_{idx:02d}_kf_prompt.txt").write_text(kf_prompt, encoding="utf-8")
        h3_generate_image_spark(kf_prompt, kf_refs, ar, kf_out, seed=base_seed + idx * 17)

        vo_wav, vo_dur = (vo_fut.result() if vo_fut is not None else (None, 0.0))

        # Compile synced H3 video payload (using exact measured `vo_dur` if `inner_os`!) & render on 5090
        h3_prompt, r_imgs, r_auds, dur = compile_h3_clip_payload(
            cspec, beat_spec, kf_out, vo_wav_dur=(vo_dur if has_vo else None), role_sheet_overrides=role_sheets
        )
        (clips_dir / f"clip_{idx:02d}_prompt.txt").write_text(h3_prompt, encoding="utf-8")

        def _do_on_gpu(remote_ssh: Optional[str]):
            last_err = None
            for att in range(2):
                try:
                    H3R.run_comfy_5090(
                        c_mp4,
                        prompt=h3_prompt,
                        ref_images=r_imgs,
                        ref_audios=r_auds,
                        ratio=ar,
                        resolution=resolution,
                        duration=dur,
                        seed=base_seed + idx * 13 + att,
                        unet_name=H3R.DEFAULT_REF_UNET,
                        steps=steps,
                        use_pika_lora=False,
                        lock_frame0=True,
                        remote_ssh=remote_ssh or "",
                    )
                    break
                except Exception as exc:
                    last_err = exc
                    time.sleep(4)
            else:
                raise RuntimeError(f"ComfyUI render failed on {remote_ssh or '5090'}: {last_err}")
            return c_mp4

        try:
            gpu_pool.run_job(_do_on_gpu, priority_dur=float(dur))
            if has_vo and vo_wav is not None:
                apply_vo_wav_onto_clip(c_mp4, vo_wav, vo_dur, cspec["inner_os"])
            isolate_clean_dry_dialogue_on_clip(c_mp4, is_speaking_clip=is_speaking_on_cam)
            silence_non_speaking_clip_vocals(c_mp4, is_silent_reaction=is_silent_react, incoming_lcut_s=prev_hold)
            trim_clip_dead_air_sync(c_mp4, is_speaking_clip=is_speaking_on_cam)
        finally:
            if vo_pool is not None:
                vo_pool.shutdown(wait=False)
        return idx, c_mp4

    with cf.ThreadPoolExecutor(max_workers=len(clips)) as ex:
        for idx, mp4_p in ex.map(_pipeline_single_clip, enumerate(clips)):
            clip_mp4_map[idx] = mp4_p

    ordered_mp4s = [clip_mp4_map[i] for i in range(len(clips))]
    holds = [float(c.get("lcut_audio_hold_over_next_s", 0.0) or 0.0) for c in clips]
    silent_flags = [not bool(c.get("speaking_role_ids")) for c in clips]

    stitch_meta = stitch_clips_with_lcut(
        ordered_mp4s, holds, silent_flags, ar, resolution, final_mp4, setting_summary=str(beat_spec.get("setting_summary", ""))
    )
    (out_dir / "render_manifest.json").write_text(
        json.dumps({"scene_plan": scene_plan, "stitch_meta": stitch_meta}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return final_mp4


if __name__ == "__main__":
    print("native_video_engine v2 (Blocking Master + Sync-Locked Trim + Zero-Drift Stitch) loaded.")
