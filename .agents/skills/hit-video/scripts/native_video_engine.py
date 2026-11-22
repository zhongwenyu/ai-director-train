#!/home/zhongwenyu/data/anaconda3/bin/python3
"""
Unified Dual-GPU (`5090` + `Spark`) `MiniMax H3 Image` + `MiniMax H3 Video` & Deterministic `L-Cut` Engine
(`.agents/skills/hit-video/scripts/native_video_engine.py`).

Executes a structured `scene_plan.json` produced by the Generator Sub-Agent on a `beat_spec.json`:
  1. Generates `<=1K` opening keyframes per sub-clip via Spark `MiniMax H3 Image` (`127.0.0.1:8338`,
     6 steps, `MiniMaxH3ImageConditioning` `<Picture 1..K> -> <Subject 1..K>` 3-part syntax),
     referencing ONLY standardized `0%` character sheets, clean scene plate, and prop assets.
  2. Coordinates `Spark:8338` (H3 Image) and `Spark:8188` (H3 Video) + `5090:8188` (H3 Video) via a
     Spark-Guarded LPT Priority Pool: while `Spark:8338` streams out keyframes, `5090:8188` immediately
     renders completed scenes' H3 Videos in parallel; the instant the last keyframe finishes on
     `Spark:8338`, `Spark:8188` automatically unlocks and joins `5090:8188` at full 2-GPU speed!
  3. Deterministically stitches sub-clips with frame-accurate `L-Cut` audio-over-reaction crossfades
     and normalizes output container (`24fps`, `48kHz` stereo AAC, `-16 LUFS` loudness).
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import math
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

HERE = Path(__file__).resolve().parent
WORKSTATION_SCRIPTS = Path("/home/zhongwenyu/project/ai-director-workstation/skills/storyboard-video-gen/scripts")

for p in (str(HERE), str(WORKSTATION_SCRIPTS)):
    if p not in sys.path:
        sys.path.insert(0, str(p))

import h3_native_runner as H3R  # noqa: E402
from spark_h3_image import generate_spark_h3_image  # noqa: E402

_VO_4070_LOCK = threading.Lock()
_SPARK_STAGE_LOCK = threading.Lock()
_SPARK_STAGED_CACHE: set[str] = set()
_SPARK_IMG_SEM = threading.Semaphore(2)  # Optimal 2-deep pipeline on dedicated Spark:8338 (60GiB free RAM!)


def resolve_h3_image_keyframe_prompt_and_refs(
    clip_spec: Dict[str, Any],
    beat_spec: Dict[str, Any],
) -> Tuple[str, List[Path]]:
    """Compile symbolic tags ([Scene], [CHR_1], [PRP_1]) into official 3-part MiniMax H3 Image syntax."""
    asset_files = beat_spec["asset_files"]
    char_lookup = {c["role_id"]: c for c in beat_spec.get("characters", [])}
    prop_lookup = {p["prop_id"]: p for p in beat_spec.get("props", [])}

    refs: List[Path] = []
    part1_defs: List[str] = []
    part2_pres: List[str] = []
    sym_to_subj: Dict[str, str] = {}

    if clip_spec.get("include_scene_plate_in_keyframe", True) and "scene_clean" in asset_files:
        refs.append(Path(asset_files["scene_clean"]))
        idx = len(refs)
        s_tok = f"<Subject {idx}>"
        sym_to_subj["Scene"] = s_tok
        part1_defs.append(f"The environment architecture and lighting in <Picture {idx}> are {s_tok}.")
        part2_pres.append(f"{s_tok} is partially preserved to anchor authentic spatial lighting and background bokeh")

    vis_roles = [r for r in clip_spec.get("visible_role_ids", []) if r in asset_files]
    fg_roles = [r for r in clip_spec.get("foreground_silhouette_role_ids", []) if r in asset_files and r not in vis_roles]

    for r in vis_roles:
        if len(refs) >= 6:
            break
        refs.append(Path(asset_files[r]))
        idx = len(refs)
        s_tok = f"<Subject {idx}>"
        sym_to_subj[r] = s_tok
        g = char_lookup.get(r, {}).get("gender", "")
        g_word = "woman" if g == "female" else ("man" if g == "male" else "person")
        part1_defs.append(f"The {g_word} in <Picture {idx}> is {s_tok}.")
        part2_pres.append(f"{s_tok} is fully preserved in exact facial bone structure, hairstyle, and complete outfit from <Picture {idx}>")

    for r in fg_roles:
        if len(refs) >= 6:
            break
        refs.append(Path(asset_files[r]))
        idx = len(refs)
        s_tok = f"<Subject {idx}>"
        sym_to_subj[r] = s_tok
        part1_defs.append(f"The person in <Picture {idx}> is {s_tok}.")
        part2_pres.append(f"{s_tok} appears ONLY from behind as a softly out-of-focus foreground back-shoulder silhouette")

    for p_id in clip_spec.get("prop_ids", []):
        if p_id in asset_files and len(refs) < 6:
            refs.append(Path(asset_files[p_id]))
            idx = len(refs)
            s_tok = f"<Subject {idx}>"
            sym_to_subj[p_id] = s_tok
            pname = prop_lookup.get(p_id, {}).get("name", "prop")
            part1_defs.append(f"The {pname} in <Picture {idx}> is {s_tok}.")
            part2_pres.append(f"{s_tok} is preserved as a single realistic rigid object")

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
        "Crisp 35mm live-action cinema photography, natural skin pores, zero text, zero subtitles, zero watermarks, zero split-screen."
    ).strip()
    return full_kf_prompt, refs


def h3_generate_keyframe(
    prompt: str,
    ref_paths: List[Path],
    aspect_ratio: str,
    out_1k_png: Path,
    seed: int,
    gpu_pool: "DualGPUPool",
) -> Path:
    """Generate a 1K opening keyframe via Spark `MiniMax H3 Image` (`127.0.0.1:8338`, 6 steps)."""
    out_1k_png.parent.mkdir(parents=True, exist_ok=True)
    if out_1k_png.is_file() and out_1k_png.stat().st_size > 1024:
        return out_1k_png

    raw_2k = out_1k_png.with_suffix(".2k_raw.png")
    ar = aspect_ratio if aspect_ratio in ("16:9", "9:16", "1:1", "3:4", "4:3") else "16:9"

    gpu_pool.enter_spark_image()
    try:
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
    finally:
        gpu_pool.exit_spark_image()


def compile_h3_clip_payload(
    clip_spec: Dict[str, Any],
    beat_spec: Dict[str, Any],
    keyframe_1k: Path,
) -> Tuple[str, List[Path], List[Path]]:
    """Deterministically bind <Picture 1..N>, <Subject 1..K>, (S1..SM), and <Audio 1..M> for H3 Ref2VA."""
    asset_files = beat_spec["asset_files"]
    voice_files = beat_spec["voice_files"]
    char_lookup = {c["role_id"]: c for c in beat_spec.get("characters", [])}
    prop_lookup = {p["prop_id"]: p for p in beat_spec.get("props", [])}

    ref_images: List[Path] = [keyframe_1k]  # <Picture 1> is ALWAYS the clip's opening keyframe
    vis_roles = [r for r in clip_spec.get("visible_role_ids", []) if r in asset_files]
    spk_roles = [
        r for r in clip_spec.get("speaking_role_ids", [])
        if r in voice_files and r in vis_roles
    ]

    role_to_subj_idx: Dict[str, int] = {}
    role_to_pic_idx: Dict[str, int] = {}
    for idx, r in enumerate(vis_roles, 1):
        ref_images.append(Path(asset_files[r]))
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
        f"<Picture 1> is the opening {clip_spec.get('camera_framing', 'medium close-up')} cinema frame anchoring lighting, spatial depth, and initial character posture."
    ]
    ret_lines = [
        "<Picture 1> (opening frame): fully_preserved - anchor exact opening composition, lighting, and initial pose."
    ]

    for r in vis_roles:
        s_idx = role_to_subj_idx[r]
        p_idx = role_to_pic_idx[r]
        s_tag = f" {role_to_spk_tag[r]}" if r in role_to_spk_tag else ""
        c_info = char_lookup.get(r, {})
        gender_word = "woman" if c_info.get("gender") == "female" else ("man" if c_info.get("gender") == "male" else "person")
        subj_lines.append(f"<Subject {s_idx}>{s_tag} is the {gender_word} matching the identity and outfit in <Picture {p_idx}>.")
        ret_lines.append(f"<Subject {s_idx}>: fully_preserved - retain exact facial bone structure, hair silhouette, and outfit from <Picture {p_idx}>.")

    for p_id, p_idx in prop_to_pic_idx.items():
        p_info = prop_lookup.get(p_id, {})
        subj_lines.append(f"<Picture {p_idx}> is the reference prop ({p_info.get('name', p_id)}).")
        ret_lines.append(f"<Picture {p_idx}>: fully_preserved - maintain single consistent rigid prop appearance.")

    for r in spk_roles:
        s_idx = role_to_subj_idx[r]
        a_idx = role_to_aud_idx[r]
        s_tag = role_to_spk_tag[r]
        subj_lines.append(f"<Audio {a_idx}> is the voice-timbre reference for <Subject {s_idx}> {s_tag}.")
        ret_lines.append(f"<Audio {a_idx}>: reference - guides <Subject {s_idx}>'s natural Mandarin voice timbre.")

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
    # Keep H3 summary strictly English if generator accidentally emitted Chinese in clip_summary
    if not raw_sum or re.search(r"[\u4e00-\u9fff]", raw_sum):
        raw_sum = f"Natural 35mm live-action {clip_spec.get('camera_framing', 'medium close-up')} beat starting from <Picture 1>."
    summary_body = raw_sum
    detail_body = replace_role_tokens(str(clip_spec.get("detailed_action_and_dialogue") or ""), with_speaker_tag=True).strip()
    if not detail_body.startswith("[Shot 1]") and "[Shot 1]" not in detail_body:
        detail_body = f"Live-action 35mm cinema photography, natural skin pores, accurate five-fingered hands, without any text or captions.\n[Shot 1] Starting from <Picture 1>, {detail_body}"
    elif "without any text" not in detail_body.lower():
        detail_body = "Live-action 35mm cinema photography, natural skin pores, accurate five-fingered hands, without any text or captions.\n" + detail_body

    if not ref_audios:
        detail_body = re.sub(r"<d>.*?</d>", "", detail_body, flags=re.S)

    soundscape = str(clip_spec.get("soundscape") or "Quiet natural room ambience and subtle realistic cloth/object foley.").strip()
    soundscape = H3R.HARMFUL_SOUNDSCAPE_MUSIC_RE.sub("ambient tone", soundscape)

    full_prompt = (
        "subject_definitions:\n" + "\n".join(subj_lines) + "\n\n"
        f"summary:\n{mode_tags} {summary_body}\n\n"
        "retention_analysis:\n" + "\n".join(ret_lines) + "\n\n"
        f"detailed_description:\n{detail_body}\n\n"
        f"overall_soundscape:\n{soundscape}\n\n"
        "non_diegetic_music:\nN/A"
    )
    return full_prompt, ref_images, ref_audios


def synthesize_vo_wav_on_4070(
    os_spec: Dict[str, Any],
    beat_spec: Dict[str, Any],
    work_dir: Path,
    seed: int,
) -> Optional[Path]:
    """Synthesize offscreen dialogue / inner-OS via dedicated 4070TiS 368p low-res video lane in parallel."""
    role_id = os_spec.get("speaker_id", "")
    text = str(os_spec.get("text") or "").strip()
    if not text or role_id not in beat_spec.get("voice_files", {}):
        return None

    work_dir.mkdir(parents=True, exist_ok=True)
    vo_wav = work_dir / f"vo_4070_{seed}.wav"
    if vo_wav.is_file() and vo_wav.stat().st_size > 1000:
        return vo_wav

    vo_spec = {
        "face_1k": beat_spec["asset_files"][role_id],
        "voice": beat_spec["voice_files"][role_id],
        "text": text,
        "duration": 6,
    }
    with _VO_4070_LOCK:
        H3R.synthesize_vo_clip_4070(vo_spec, work_dir / "cache_1k", vo_wav, seed=seed)
    return vo_wav


def apply_vo_wav_onto_clip(
    base_mp4: Path,
    vo_wav: Optional[Path],
    os_spec: Dict[str, Any],
) -> Path:
    """Mix pre-synthesized 4070TiS voiceover WAV onto silent-mouth visual clip."""
    if vo_wav is None or not vo_wav.is_file():
        return base_mp4
    probe = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_format", "-of", "json", str(base_mp4)], text=True))
    base_dur = float(probe["format"]["duration"])
    mixed_mp4 = base_mp4.with_suffix(".os_mixed.mp4")
    eff = "none" if str(os_spec.get("mode", "")).lower() == "offscreen_speech" else "inner_vo"
    H3R.mix_vo_into_video(
        base_mp4=base_mp4,
        vo_wav=vo_wav,
        dst_start=float(os_spec.get("start_s", 0.25)),
        max_len=max(1.2, base_dur - 0.30),
        base_duck=0.22,
        effect=eff,
        out_mp4=mixed_mp4,
    )
    mixed_mp4.replace(base_mp4)
    return base_mp4


def stitch_clips_with_lcut(
    clip_mp4s: List[Path],
    lcut_holds: List[float],
    aspect_ratio: str,
    resolution: str,
    out_mp4: Path,
) -> Dict[str, Any]:
    """Deterministically assemble atomic clips with cinema L-Cut audio-over-reaction crossfades + -16 LUFS loudnorm."""
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    tw, th = H3R.RESOLUTION_PRESETS[resolution][aspect_ratio]

    if len(clip_mp4s) == 1:
        vf = f"scale={tw}:{th}:force_original_aspect_ratio=decrease,pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2,fps=24"
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error", "-i", str(clip_mp4s[0]),
                "-vf", vf,
                "-af", "aresample=48000,loudnorm=I=-16:TP=-1.5:LRA=11",
                "-c:v", "libx264", "-preset", "fast", "-crf", "19", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k",
                str(out_mp4),
            ],
            check=True,
        )
        return {"clip_count": 1, "visual_cuts": []}

    durs: List[float] = []
    for p in clip_mp4s:
        pr = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_format", "-of", "json", str(p)], text=True))
        durs.append(float(pr["format"]["duration"]))

    n = len(clip_mp4s)
    holds: List[float] = []
    for i in range(n):
        if i == n - 1:
            holds.append(0.0)
        else:
            raw_h = max(0.0, float(lcut_holds[i] if i < len(lcut_holds) else 0.0))
            safe_h = min(raw_h, 1.4, durs[i] * 0.38, durs[i + 1] * 0.72)
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
        v_filters.append(
            f"[{i}:v]trim=0:{v_durs[i]:.3f},setpts=PTS-STARTPTS,"
            f"scale={tw}:{th}:force_original_aspect_ratio=decrease,pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2,"
            f"fps=24,format=yuv420p[v{i}]"
        )
        v_labels.append(f"[v{i}]")

        prev_hold = holds[i - 1] if i > 0 else 0.0
        a_end = min(durs[i], round(total_dur - t_starts[i], 3))
        delay_ms = int(round(t_starts[i] * 1000))
        vol_expr = f"volume='if(lt(t,{prev_hold:.3f}),0.18,1.0)':eval=frame," if prev_hold > 0.05 else ""
        fade_out_st = max(0.0, a_end - 0.08)
        a_filters.append(
            f"[{i}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"atrim=0:{a_end:.3f},asetpts=PTS-STARTPTS,{vol_expr}"
            f"afade=t=in:d=0.04,afade=t=out:st={fade_out_st:.3f}:d=0.08,"
            f"adelay={delay_ms}:all=1[a{i}]"
        )
        a_labels.append(f"[a{i}]")

    fc = (
        ";".join(v_filters) + ";"
        + "".join(v_labels) + f"concat=n={n}:v=1:a=0[vout];"
        + ";".join(a_filters) + ";"
        + "".join(a_labels) + f"amix=inputs={n}:duration=longest:dropout_transition=0,atrim=0:{total_dur:.3f},"
        + "loudnorm=I=-16:TP=-1.5:LRA=11[aout]"
    )

    tmp_out = out_mp4.with_suffix(".tmp_stitch.mp4")
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            *inputs,
            "-filter_complex", fc,
            "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "19", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k",
            str(tmp_out),
        ],
        check=True,
    )
    tmp_out.replace(out_mp4)
    return {"clip_count": n, "visual_cuts": t_starts[1:], "lcut_holds": holds, "total_duration_s": total_dur}


class DualGPUPool:
    """
    Spark-Guarded LPT (Longest-Processing-Time-First) priority scheduler across RTX 5090 D & Spark.

    - While `Spark:8338` (`MiniMax H3 Image`) has active keyframe jobs (`_spark_image_active > 0`),
      `5090:8188` (`None`) immediately starts rendering H3 Videos in parallel while `Spark:8188`
      stays parked to avoid GPU thrashing between `:8338` and `:8188` on Spark!
    - The instant `_spark_image_active` drops to `0`, `Spark:8188` immediately unlocks and joins
      `5090:8188` to co-render all remaining H3 Videos at full 2-GPU speed!
    """

    def __init__(self, backends: Sequence[Optional[str]] = (None,)):
        self._cond = threading.Condition()
        self._free_backends: List[Optional[str]] = list(backends)
        self._waiters: List[Tuple[float, int, threading.Event, List[Optional[str]]]] = []
        self._seq = 0
        self._spark_image_active = 0

    def _usable_backends(self) -> List[Optional[str]]:
        if self._spark_image_active > 0:
            return [b for b in self._free_backends if b != "sol-spark-benchmark"]
        return list(self._free_backends)

    def _dispatch_locked(self) -> None:
        while self._waiters:
            usable = self._usable_backends()
            if not usable:
                break
            backend = None if None in usable else usable[0]
            self._free_backends.remove(backend)
            _, _, next_ev, next_assigned = self._waiters.pop(0)
            next_assigned.append(backend)
            next_ev.set()

    def enter_spark_image(self) -> None:
        with self._cond:
            self._spark_image_active += 1

    def exit_spark_image(self) -> None:
        with self._cond:
            self._spark_image_active = max(0, self._spark_image_active - 1)
            if self._spark_image_active == 0:
                self._dispatch_locked()

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
    """Render all keyframes (`MiniMax H3 Image`) + H3 Video clips and stitch into `scene_final.mp4`."""
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

    # Stream each clip independently: keyframe on Spark MiniMax H3 Image -> immediate H3 Video enqueue!
    clip_mp4_map: Dict[int, Path] = {}

    def _pipeline_single_clip(idx_clip: Tuple[int, Dict[str, Any]]) -> Tuple[int, Path]:
        idx, cspec = idx_clip
        c_mp4 = clips_dir / f"clip_{idx:02d}.mp4"
        if c_mp4.is_file() and c_mp4.stat().st_size > 10000:
            return idx, c_mp4

        # Step A: Start 4070TiS 368p low-res voiceover synthesis IMMEDIATELY in parallel if clip has inner_os / offscreen VO!
        has_vo = bool(cspec.get("inner_os") and isinstance(cspec["inner_os"], dict) and cspec["inner_os"].get("text"))
        vo_pool = cf.ThreadPoolExecutor(max_workers=1) if has_vo else None
        vo_fut = (
            vo_pool.submit(synthesize_vo_wav_on_4070, cspec["inner_os"], beat_spec, clips_dir, base_seed + idx * 13 + 5)
            if vo_pool is not None
            else None
        )

        # Step B: Generate 1K keyframe on dedicated Spark:8338 (`MiniMax H3 Image`)
        kf_out = kf_dir / f"clip_{idx:02d}_1k.png"
        kf_prompt, kf_refs = resolve_h3_image_keyframe_prompt_and_refs(cspec, beat_spec)
        (kf_dir / f"clip_{idx:02d}_kf_prompt.txt").write_text(kf_prompt, encoding="utf-8")
        h3_generate_keyframe(kf_prompt, kf_refs, ar, kf_out, seed=base_seed + idx * 17, gpu_pool=gpu_pool)

        # Step C: Auto-pad duration if spoken CJK line exceeds raw duration budget (prevents tail truncation!)
        raw_dur = float(cspec.get("duration_s", 4))
        h3_prompt, r_imgs, r_auds = compile_h3_clip_payload(cspec, beat_spec, kf_out)
        spoken_cjk = sum(len(re.findall(r"[\u4e00-\u9fff]", m.group(1))) for m in re.finditer(r"<d>(.*?)</d>", h3_prompt, re.S))
        min_safe_dur = math.ceil(0.35 + spoken_cjk / 4.4 + 0.75) if spoken_cjk > 0 else 2
        dur = max(2, min(14, max(int(round(raw_dur)), min_safe_dur)))
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
            if vo_fut is not None:
                vo_wav = vo_fut.result()
                apply_vo_wav_onto_clip(c_mp4, vo_wav, cspec["inner_os"])
        finally:
            if vo_pool is not None:
                vo_pool.shutdown(wait=False)
        return idx, c_mp4

    with cf.ThreadPoolExecutor(max_workers=len(clips)) as ex:
        for idx, mp4_p in ex.map(_pipeline_single_clip, enumerate(clips)):
            clip_mp4_map[idx] = mp4_p

    ordered_mp4s = [clip_mp4_map[i] for i in range(len(clips))]
    holds = [float(c.get("lcut_audio_hold_over_next_s", 0.0) or 0.0) for c in clips]

    stitch_meta = stitch_clips_with_lcut(ordered_mp4s, holds, ar, resolution, final_mp4)
    (out_dir / "render_manifest.json").write_text(
        json.dumps({"scene_plan": scene_plan, "stitch_meta": stitch_meta}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return final_mp4


if __name__ == "__main__":
    print("native_video_engine (MiniMax H3 Image + H3 Video) loaded successfully.")
