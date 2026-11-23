#!/home/zhongwenyu/data/anaconda3/bin/python3
"""
Hermetic Target-Anchored Multimodal Video Arena Judge (`judge/video_arena_judge.py`).

Fixes grading inflation & lip-sync/spatial/expression blind spots:
  1. Target-Anchored Triplet Calibration: Stages `Target_Benchmark.mp4` (`85.0`-point real hit-drama
     standard!) inside the hermetic sandbox alongside anonymized `Video_A.mp4` and `Video_B.mp4`,
     eliminating AI-vs-AI score inflation (no wooden or desynced AI clip can ever score 85-90!).
  2. Strict Deterministic Signal Penalties (`probe_video_signals`):
     - `AV_STREAM_DESYNC` (`|v_dur - a_dur| > 0.10s` -> `-40 pts`)
     - `LIP_SYNC_MOUTH_MISMATCH` (OpenCV face lower-jaw optical motion during speech vs silence -> `-25 pts`)
     - `DURATION_PACING_BLOAT` (duration exceeding `target_duration_s * 1.35` -> `-25 pts`)
     - `PRE_SPEECH_DEAD_LAG` (`> 1.3s` dead staring before speech -> `-15 pts`)
     - `SPEECH_TAIL_TRUNCATED` (`-12 pts`), `MISSING_SPEECH_AUDIO` (`-30 pts`), `FROZEN_STATIC_VIDEO` (`-20 pts`)
  3. Order-Swapped Dual-Blind (`(A=cand, B=champ)` + `(A=champ, B=cand)`) on `gemini-4-argon-medium`.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import wave
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np
import onnxruntime as ort

DEFAULT_VAD_ONNX = Path("/home/zhongwenyu/.paseo/models/local-speech/silero-vad/silero_vad.onnx")
AGY_BIN = (
    "/home/zhongwenyu/.config/paseo/antigravity-bin/agy"
    if Path("/home/zhongwenyu/.config/paseo/antigravity-bin/agy").is_file()
    else (shutil.which("agy") or str(Path.home() / ".local/bin/agy"))
)
JUDGE_MODEL = os.environ.get("VIDEO_JUDGE_MODEL", "gemini-4-argon-medium")
JUDGE_EFFORT = os.environ.get("VIDEO_JUDGE_EFFORT", "medium")
FACE_CASCADE_PATH = str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml")


def _extract_first_json(text: str) -> Dict[str, Any]:
    s = text.strip()
    m = re.match(r"^```[a-zA-Z0-9_-]*\s*\n(.*)\n```\s*$", s, re.S)
    if m:
        s = m.group(1).strip()
    dec = json.JSONDecoder()
    for idx, ch in enumerate(s):
        if ch == "{":
            try:
                obj, _ = dec.raw_decode(s[idx:])
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                continue
    raise ValueError(f"No valid JSON object found in response ({len(text)} chars): {text[:360]!r}")


def call_argon_multimodal(
    prompt_text: str,
    media_items: Sequence[Dict[str, Any]],
    *,
    schema: Optional[Dict[str, Any]] = None,
    effort: str = JUDGE_EFFORT,
    timeout: int = 360,
    retries: int = 2,
) -> Dict[str, Any]:
    """Run context-isolated `gemini-4-argon-medium` inside an empty sandbox tempdir with anonymized media."""
    model = f"gemini-4-argon-{effort}" if effort in ("low", "medium", "high") else JUDGE_MODEL
    last_err = ""

    for attempt in range(1, retries + 2):
        with tempfile.TemporaryDirectory(prefix="hermetic-argon-") as tmp_cwd:
            td_p = Path(tmp_cwd).resolve()
            staged_lines: List[str] = []
            for item in media_items:
                src_p = Path(item["path"]).resolve(strict=True)
                anon_name = str(item["anon_name"])
                caption = str(item.get("caption") or anon_name)
                dst_p = td_p / anon_name
                shutil.copyfile(src_p, dst_p)
                staged_lines.append(f"- `{dst_p}` ：{caption}")

            full_prompt = (
                "【严格沙箱盲审指令】\n"
                f"你当前处于完全隔离的盲审沙箱目录 `{td_p}`。\n"
                "1. 请且仅使用 `read_file` 工具依次完整读取下方列出的沙箱内媒体文件（视频必须逐秒比对嘴唇开合与人声是否同步、人物座位空间是否跳变、面部表情是否鲜活丰富）；\n"
                f"2. 严禁访问 `{td_p}` 以外的任何路径，严禁调用任何其他工具；\n"
                "3. 读取完毕后立即按要求输出结构化 JSON 结果。\n\n"
                "【待读取沙箱媒体附件清单】\n"
                + "\n".join(staged_lines)
                + "\n\n"
                + prompt_text
            )

            cmd = [
                AGY_BIN,
                "--model", model,
                "--effort", effort,
                "--sandbox",
                "--disable-slash-commands",
                "--dangerously-skip-permissions",
                "--output-format", "json",
                "--log-file", str(td_p / "cli.log"),
            ]
            if schema is not None:
                sp = td_p / "schema.json"
                sp.write_text(json.dumps(schema, ensure_ascii=False), encoding="utf-8")
                cmd.extend(["--json-schema", str(sp)])
            cmd.extend(["-p", full_prompt])

            try:
                proc = subprocess.run(cmd, cwd=str(td_p), capture_output=True, text=True, timeout=timeout)
            except subprocess.TimeoutExpired:
                last_err = f"argon timeout after {timeout}s (attempt {attempt})"
                time.sleep(2 * attempt)
                continue

            log_p = td_p / "cli.log"
            if log_p.is_file():
                log_txt = log_p.read_text(encoding="utf-8", errors="ignore")
                if "/ai-director-train/runs" in log_txt or "/ai-director-train/.agents" in log_txt:
                    raise RuntimeError("SECURITY BREACH: Judge attempted to inspect training workspace!")

            if proc.returncode != 0:
                last_err = f"argon exit {proc.returncode} (attempt {attempt}): {(proc.stderr or proc.stdout)[-600:]}"
                time.sleep(2 * attempt)
                continue

            try:
                env_json = json.loads(proc.stdout)
                if isinstance(env_json.get("structured_output"), dict):
                    return env_json["structured_output"]
                resp_text = str(env_json.get("response") or "").strip()
                return _extract_first_json(resp_text)
            except Exception as exc:
                last_err = f"argon JSON parse failed (attempt {attempt}): {exc}"
                time.sleep(2 * attempt)

    raise RuntimeError(last_err or "call_argon_multimodal failed")


_VAD_SESS: Optional[ort.InferenceSession] = None
_VAD_LOCK = None


def _get_vad_sess() -> ort.InferenceSession:
    global _VAD_SESS, _VAD_LOCK
    import threading
    if _VAD_LOCK is None:
        _VAD_LOCK = threading.Lock()
    with _VAD_LOCK:
        if _VAD_SESS is None:
            _VAD_SESS = ort.InferenceSession(str(DEFAULT_VAD_ONNX), providers=["CPUExecutionProvider"])
        return _VAD_SESS


def probe_video_signals(
    mp4_path: Path,
    has_spoken_dialogue: bool = True,
    target_duration_s: Optional[float] = None,
) -> Dict[str, Any]:
    """Deterministic A/V stream sync, lip-sync mouth-motion correlation, duration bloat, VAD, & motion probes."""
    mp4_path = Path(mp4_path)
    probe = json.loads(
        subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(mp4_path)],
            text=True,
        )
    )
    vstream = next(s for s in probe["streams"] if s["codec_type"] == "video")
    astream = next((s for s in probe["streams"] if s["codec_type"] == "audio"), None)
    fmt_dur = float(probe["format"]["duration"])
    v_dur = float(vstream.get("duration") or fmt_dur)
    a_dur = float(astream.get("duration") or fmt_dur) if astream else 0.0
    av_desync_s = round(abs(v_dur - a_dur), 3) if astream else 99.0
    w, h = int(vstream["width"]), int(vstream["height"])

    vad_probs = np.zeros(0, dtype=np.float32)
    vad_segments: List[Tuple[float, float]] = []
    tail_truncated = False
    speech_total_s = 0.0
    first_speech_s = None
    audio_dropout_gating = False

    if astream is not None and DEFAULT_VAD_ONNX.is_file():
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp_wav:
            subprocess.run(
                ["ffmpeg", "-v", "error", "-y", "-i", str(mp4_path), "-ac", "1", "-ar", "16000", tmp_wav.name],
                check=True,
            )
            with wave.open(tmp_wav.name, "rb") as wf:
                pcm = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
        sess = _get_vad_sess()
        hop = 512
        n_frames = len(pcm) // hop
        h_st = np.zeros((2, 1, 64), dtype=np.float32)
        c_st = np.zeros((2, 1, 64), dtype=np.float32)
        vad_probs = np.empty(n_frames, dtype=np.float32)
        non_speech_dbs: List[float] = []
        for i in range(n_frames):
            chunk = pcm[i * hop : (i + 1) * hop]
            pr, h_st, c_st = sess.run(None, {"x": chunk.reshape(1, hop), "h": h_st, "c": c_st})
            vp = float(pr[0, 0])
            vad_probs[i] = vp
            if vp < 0.10:
                rms = float(np.sqrt(np.mean(chunk * chunk)))
                non_speech_dbs.append(20.0 * np.log10(max(1e-5, rms)))
        if len(non_speech_dbs) >= 12:
            # Flag severe audio gating ("background noise present during speech/some clips, dead -80dB drop in pauses/reactions")
            p10_ns = float(np.percentile(non_speech_dbs, 10))
            p85_ns = float(np.percentile(non_speech_dbs, 85))
            if p10_ns < -68.0 or (p85_ns - p10_ns) > 24.0:
                audio_dropout_gating = True
        dt = hop / 16000.0
        in_s, s0 = False, 0
        for idx, p in enumerate(vad_probs):
            if p >= 0.52 and not in_s:
                in_s, s0 = True, idx
            elif p < 0.52 and in_s:
                in_s = False
                if (idx - s0) * dt >= 0.16:
                    vad_segments.append((round(s0 * dt, 3), round(idx * dt, 3)))
        if in_s and (len(vad_probs) - s0) * dt >= 0.16:
            vad_segments.append((round(s0 * dt, 3), round(len(vad_probs) * dt, 3)))
        speech_total_s = round(sum(e - s for s, e in vad_segments), 3)
        if vad_segments:
            first_speech_s = vad_segments[0][0]
        if len(vad_probs) >= 4 and float(vad_probs[-2:].min()) >= 0.75:
            tail_truncated = True

    # OpenCV motion liveness, cut detection, & lower-face mouth motion vs VAD silent-flapping check
    cap = cv2.VideoCapture(str(mp4_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    face_cascade = cv2.CascadeClassifier(FACE_CASCADE_PATH) if os.path.exists(FACE_CASCADE_PATH) else None
    prev_gray = None
    prev_mouth_patch = None
    prev_upper_patch = None
    prev_face_center = None
    diffs: List[float] = []
    cut_frames = 0
    speech_jaw_ratios: List[float] = []
    silent_jaw_ratios: List[float] = []

    step = max(1, int(round(fps / 8.0)))  # Sample at 8 Hz
    fidx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if fidx % step == 0:
            t_sec = fidx / fps
            small = cv2.cvtColor(cv2.resize(frame, (320, int(round(320 * h / max(1, w))))), cv2.COLOR_BGR2GRAY)
            gray160 = cv2.resize(small, (160, 90)).astype(np.float32)
            is_cut = False
            if prev_gray is not None:
                d = float(np.mean(np.abs(gray160 - prev_gray)))
                diffs.append(d)
                if d > 28.0:
                    cut_frames += 1
                    is_cut = True
                    prev_mouth_patch = None
                    prev_upper_patch = None
                    prev_face_center = None
            prev_gray = gray160

            if face_cascade is not None and not is_cut:
                faces = face_cascade.detectMultiScale(small, scaleFactor=1.15, minNeighbors=5, minSize=(40, 40))
                if len(faces) > 0:
                    fx, fy, fw, fh = max(faces, key=lambda b: b[2] * b[3])
                    cx, cy = fx + fw * 0.5, fy + fh * 0.5
                    uy0, uy1 = max(0, fy + int(fh * 0.15)), min(small.shape[0], fy + int(fh * 0.50))
                    my0, my1 = min(small.shape[0] - 4, fy + int(fh * 0.64)), min(small.shape[0], fy + fh)
                    mx0, mx1 = min(small.shape[1] - 4, fx + int(fw * 0.24)), min(small.shape[1], fx + int(fw * 0.76))
                    if my1 - my0 >= 6 and uy1 - uy0 >= 6 and mx1 - mx0 >= 6:
                        mpatch = cv2.resize(small[my0:my1, mx0:mx1], (24, 16)).astype(np.float32)
                        upatch = cv2.resize(small[uy0:uy1, mx0:mx1], (24, 16)).astype(np.float32)
                        same_face = (
                            prev_face_center is not None
                            and abs(cx - prev_face_center[0]) < fw * 0.18
                            and abs(cy - prev_face_center[1]) < fh * 0.18
                        )
                        if prev_mouth_patch is not None and prev_upper_patch is not None and same_face and len(vad_probs) > 0:
                            mdiff = float(np.mean(np.abs(mpatch - prev_mouth_patch)))
                            udiff = float(np.mean(np.abs(upatch - prev_upper_patch)))
                            # Isolate true jaw/lip motion from camera push-in or head translation!
                            jaw_ratio = mdiff / max(1.5, udiff) if mdiff > 3.5 else 0.0
                            v_idx = min(len(vad_probs) - 1, max(0, int(t_sec * 16000 / 512)))
                            win_p = float(vad_probs[max(0, v_idx - 2) : min(len(vad_probs), v_idx + 3)].max())
                            if win_p >= 0.45:
                                speech_jaw_ratios.append(jaw_ratio)
                            elif win_p < 0.10:
                                silent_jaw_ratios.append(jaw_ratio)
                        prev_mouth_patch = mpatch
                        prev_upper_patch = upatch
                        prev_face_center = (cx, cy)
                else:
                    prev_mouth_patch = None
                    prev_upper_patch = None
                    prev_face_center = None
        fidx += 1
    cap.release()

    median_motion = round(float(np.median(diffs)) if diffs else 0.0, 3)
    frozen_slideshow = median_motion < 0.45

    # Detect genuine silent mouth-flapping (isolated jaw motion >= 2.3x upper-face motion during silence!)
    lip_desync_detected = False
    if len(silent_jaw_ratios) >= 8:
        sil_p90 = float(np.percentile(silent_jaw_ratios, 90))
        if sil_p90 >= 2.35:
            lip_desync_detected = True

    penalty = 0.0
    penalty_reasons: List[str] = []
    if av_desync_s > 0.12:
        penalty += 40.0
        penalty_reasons.append(f"AV_STREAM_DESYNC_{av_desync_s:.2f}s")
    if lip_desync_detected:
        penalty += 20.0
        penalty_reasons.append("SILENT_MOUTH_FLAPPING_DESYNC")
    if has_spoken_dialogue and speech_total_s < 0.5:
        penalty += 30.0
        penalty_reasons.append("MISSING_SPEECH_AUDIO")
    if tail_truncated:
        penalty += 12.0
        penalty_reasons.append("SPEECH_TAIL_TRUNCATED")
    if frozen_slideshow:
        penalty += 20.0
        penalty_reasons.append("FROZEN_STATIC_VIDEO")
    if target_duration_s and target_duration_s > 3.0:
        ratio_d = fmt_dur / float(target_duration_s)
        if ratio_d > 1.55 or ratio_d < 0.55:
            penalty += 25.0
            penalty_reasons.append(f"DURATION_MISMATCH_{fmt_dur:.1f}s_vs_{target_duration_s:.1f}s")
    if has_spoken_dialogue and first_speech_s is not None and first_speech_s > 2.5:
        penalty += 12.0
        penalty_reasons.append(f"PRE_SPEECH_ZOMBIE_LAG_{first_speech_s:.2f}s")
    if audio_dropout_gating:
        penalty += 12.0
        penalty_reasons.append("AUDIO_BG_GATING_OR_DEAD_SILENCE_DROP")

    return {
        "width": w,
        "height": h,
        "duration_s": round(fmt_dur, 3),
        "v_dur_s": round(v_dur, 3),
        "a_dur_s": round(a_dur, 3),
        "av_desync_s": av_desync_s,
        "speech_total_s": speech_total_s,
        "first_speech_s": first_speech_s,
        "vad_segments": vad_segments,
        "tail_truncated": tail_truncated,
        "lip_desync_detected": lip_desync_detected,
        "median_motion": median_motion,
        "approx_cuts": cut_frames,
        "frozen_slideshow": frozen_slideshow,
        "deterministic_penalty": penalty,
        "penalty_reasons": penalty_reasons,
    }


DIM_KEYS = (
    "acting_micro_naturalism",
    "vocal_dialogue_delivery",
    "editing_rhythm_and_reactions",
    "character_and_costume_consistency",
    "cinematography_and_spatial_coherence",
    "physical_anatomy_integrity",
)

DIM_SCORE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "acting_micro_naturalism": {"type": "number", "minimum": 0, "maximum": 25},
        "vocal_dialogue_delivery": {"type": "number", "minimum": 0, "maximum": 20},
        "editing_rhythm_and_reactions": {"type": "number", "minimum": 0, "maximum": 20},
        "character_and_costume_consistency": {"type": "number", "minimum": 0, "maximum": 15},
        "cinematography_and_spatial_coherence": {"type": "number", "minimum": 0, "maximum": 10},
        "physical_anatomy_integrity": {"type": "number", "minimum": 0, "maximum": 10},
    },
    "required": list(DIM_KEYS),
    "additionalProperties": False,
}

JUDGE_PAIR_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "video_a_observation": {"type": "string"},
        "video_b_observation": {"type": "string"},
        "scores_a": DIM_SCORE_SCHEMA,
        "scores_b": DIM_SCORE_SCHEMA,
        "winner": {"type": "string", "enum": ["A", "B", "TIE"]},
        "a_key_defects": {"type": "array", "items": {"type": "string"}},
        "b_key_defects": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "video_a_observation",
        "video_b_observation",
        "scores_a",
        "scores_b",
        "winner",
        "a_key_defects",
        "b_key_defects",
    ],
    "additionalProperties": False,
}

JUDGE_PAIR_PROMPT_TEMPLATE = """你是一位极其严苛、眼睛毒辣的真人实拍级短剧总导演与多模态视听质检官。
沙箱中提供了：
- `Target_Benchmark.mp4`（固定锚定为 **85分标准线** 的爆款参考原片，如果提供，请先观看它作为表情鲜活度、人物座位空间、语速节奏与唇音同步的绝对标尺！忽略原片自带的字幕文字，专注其人物鲜活表演、嘴型同步与节奏）；
- 两段待盲评的匿名候选视频 `Video_A.mp4` 与 `Video_B.mp4`；
- `Character_Ref_*.png`（角色标准 0% 中性设定图）。

【严禁打虚高分的铁律！（违者评审作废）】
1. **分数锚定纪律**：`Target_Benchmark.mp4` 的真实水准定为 **85 分**！如果某候选视频存在【声音和嘴型对不上 / 说完话嘴还在乱动 / 声音出了嘴没张】、【人物表情像木头播音员一样僵硬平淡、远不如参考片灵动鲜活】、【人物座位或空间位置跨镜头乱跳】、【总时长拖沓注水】，该候选总分**绝不允许超过 65 分**，更严禁打出 85–90 分的荒谬虚高分！
2. **逐项死磕核查（完全独立盲审，严禁按机械动作数量打分，严禁误罚正常生理表情纹！）**：
   - `acting_micro_naturalism`（0–25分）：对比 `Target_Benchmark.mp4`，重点考察**眉眼、苹果肌、嘴角与肢体情绪层次是否鲜活饱满且准确契合潜台词极性**！**【反面瘫偏置铁律】**：人类做真实笑意、悲痛蹙眉、震惊瞪眼时必然产生自然的卧蚕、笑肌纹或眉间微蹙——**绝对严禁把自然的动态表情肌纹理误判为“显老/变形”而去给眉毛纹丝不动、靠涂红眼珠或干张嘴应付的面瘫安全脸打高分**！只有当表情幅度失控成滑稽鬼脸、同镜混出“瞪眼狞笑”怪相或与语境相反时才扣分。
   - `vocal_dialogue_delivery`（0–20分）：**核查唇音同步（±0.1秒内严丝合缝，错位或心声张嘴直接给 0–7 分）、人声干净度、自然呼吸气口以及环境声连续性**（若出现人物开口突爆杂音、闭嘴或切镜瞬间死寂断层的抽吸感，必须扣分；自然同步的动作音效与平滑连续的环境底噪加分）。
   - `editing_rhythm_and_reactions`（0–20分）：切镜是否像参考片一样紧凑干脆（单镜 2–4秒，总时长与目标接近）？是否有恰当的听话人反应镜头？若把 12 秒戏拍成 20 多秒慢吞吞发呆，或出现生硬的同人同景别跳切（Jump Cut），重扣分！
   - `character_and_costume_consistency`（0–15分）：五官骨相轮廓、发型服饰与 `Character_Ref_*.png` 是否为同一演员、跨镜是否不换脸不串衣？（注意区分“同一演员做出喜怒哀乐自然表情肌变化”与“变成另一张陌生脸或严重十岁以上苍老畸变”，前者不扣分！）
   - `cinematography_and_spatial_coherence`（0–10分）：**核查人物座位/站位空间拓扑！** 同一桌并排坐的两人是否跨镜突然变成前后排或瞬移到走廊？正反打 180° 视线轴线与景深光影是否准确？若空间位置错乱，最多给 2–4 分！
   - `physical_anatomy_integrity`（0–10分）：手部五指、桌面器物是否自然真实无穿模？

【本段戏剧任务卡】
{beat_card_text}"""


def _sum_scores(d: Dict[str, Any]) -> float:
    return float(sum(float(d.get(k, 0.0)) for k in DIM_KEYS))


def format_beat_card_for_judge(beat_spec: Dict[str, Any]) -> str:
    lines = [
        f"- 目标总时长：{beat_spec.get('target_duration_s', 10.0)} 秒（严重超时拖沓必须重扣分！）",
        f"- 画幅与光影环境：{beat_spec.get('aspect_ratio', '16:9')} ｜ {beat_spec.get('setting_summary', '')}",
        f"- 空间座位/站位硬约束：{beat_spec.get('initial_blocking', '')}",
        f"- 戏剧目标与情绪张力：{beat_spec.get('dramatic_goal', '')}",
        "- 出场角色：",
    ]
    for ch in beat_spec.get("characters", []):
        lines.append(f"  * {ch['role_id']}（{ch['display_name']}）：{ch['neutral_visual_bio']}")
    if beat_spec.get("props"):
        lines.append("- 关键道具：" + "；".join(f"{p['prop_id']}（{p['description']}）" for p in beat_spec["props"]))
    lines.append("- 本段台词 / 心声序列（须唇音严丝合缝、情绪鲜活）：")
    for idx, turn in enumerate(beat_spec.get("dialogue_turns", []), 1):
        mode_tag = "心声OS（画内闭嘴）" if turn.get("mode") == "inner_os" else "画内对白"
        lines.append(f"  {idx}. [{mode_tag}] {turn['speaker_id']}（潜台词：{turn.get('subtext_intent', '')}）：“{turn['text']}”")
    return "\n".join(lines)


def _run_single_blind_pass(
    beat_card_text: str,
    char_refs: Sequence[Tuple[str, Path]],
    video_a: Path,
    video_b: Path,
    gold_anchor: Optional[Path] = None,
    effort: str = "medium",
) -> Dict[str, Any]:
    media_items: List[Dict[str, Any]] = []
    if gold_anchor is not None and gold_anchor.is_file():
        # Avoid passing identical file twice if one of A/B IS gold_anchor during vs_gold eval
        if gold_anchor.resolve() != video_a.resolve() and gold_anchor.resolve() != video_b.resolve():
            media_items.append(
                {
                    "kind": "video",
                    "path": gold_anchor,
                    "anon_name": "Target_Benchmark.mp4",
                    "caption": "85分标准线目标参考原片（请以此片的鲜活表情、唇音同步、紧凑切镜与人物座位空间作为绝对评分标尺！）",
                }
            )
    for idx, (label, cpath) in enumerate(char_refs, 1):
        media_items.append(
            {
                "kind": "image",
                "path": cpath,
                "anon_name": f"Character_Ref_{idx}.png",
                "caption": f"角色标准 0% 中性设定图：{label}",
            }
        )
    media_items.append(
        {"kind": "video", "path": video_a, "anon_name": "Video_A.mp4", "caption": "待严苛盲审候选片 Video_A"}
    )
    media_items.append(
        {"kind": "video", "path": video_b, "anon_name": "Video_B.mp4", "caption": "待严苛盲审候选片 Video_B"}
    )
    prompt = JUDGE_PAIR_PROMPT_TEMPLATE.format(beat_card_text=beat_card_text)
    res = call_argon_multimodal(prompt, media_items, schema=JUDGE_PAIR_SCHEMA, effort=effort)
    res["total_a"] = _sum_scores(res.get("scores_a", {}))
    res["total_b"] = _sum_scores(res.get("scores_b", {}))
    w = str(res.get("winner", "")).strip().upper()
    if w not in ("A", "B", "TIE"):
        w = "A" if res["total_a"] > res["total_b"] else ("B" if res["total_b"] > res["total_a"] else "TIE")
    res["winner"] = w
    return res


def judge_pair_swapped(
    beat_spec: Dict[str, Any],
    char_refs: Sequence[Tuple[str, Path]],
    cand_mp4: Path,
    champ_mp4: Path,
    *,
    effort: str = "medium",
) -> Dict[str, Any]:
    """Run Target-Anchored Order-Swapped Dual-Blind + strict A/V sync, lip-sync, & bloat penalties."""
    has_spoken = any(t.get("mode") != "inner_os" for t in beat_spec.get("dialogue_turns", []))
    target_dur = float(beat_spec.get("target_duration_s") or 0.0) or None
    gold_p = Path(beat_spec["gold_sealed_mp4"]) if beat_spec.get("gold_sealed_mp4") else None
    beat_card_text = format_beat_card_for_judge(beat_spec)

    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        f_pc = ex.submit(probe_video_signals, cand_mp4, has_spoken, target_dur)
        f_pr = ex.submit(probe_video_signals, champ_mp4, has_spoken, target_dur)
        f_p1 = ex.submit(_run_single_blind_pass, beat_card_text, char_refs, cand_mp4, champ_mp4, gold_p, effort)
        f_p2 = ex.submit(_run_single_blind_pass, beat_card_text, char_refs, champ_mp4, cand_mp4, gold_p, effort)
        probe_cand = f_pc.result()
        probe_champ = f_pr.result()
        p1 = f_p1.result()
        p2 = f_p2.result()

    cand_raw_1, champ_raw_1 = p1["total_a"], p1["total_b"]
    champ_raw_2, cand_raw_2 = p2["total_a"], p2["total_b"]

    cand_dim_avg = {
        k: round((float(p1["scores_a"].get(k, 0)) + float(p2["scores_b"].get(k, 0))) / 2.0, 2)
        for k in DIM_KEYS
    }
    champ_dim_avg = {
        k: round((float(p1["scores_b"].get(k, 0)) + float(p2["scores_a"].get(k, 0))) / 2.0, 2)
        for k in DIM_KEYS
    }

    is_cand_gold = gold_p is not None and cand_mp4.resolve() == gold_p.resolve()
    is_champ_gold = gold_p is not None and champ_mp4.resolve() == gold_p.resolve()
    pen_cand = 0.0 if is_cand_gold else probe_cand["deterministic_penalty"]
    pen_champ = 0.0 if is_champ_gold else probe_champ["deterministic_penalty"]

    cand_score = round(max(0.0, (cand_raw_1 + cand_raw_2) / 2.0 - pen_cand), 2)
    champ_score = round(max(0.0, (champ_raw_1 + champ_raw_2) / 2.0 - pen_champ), 2)

    v1 = 1 if p1["winner"] == "A" else (-1 if p1["winner"] == "B" else 0)
    v2 = 1 if p2["winner"] == "B" else (-1 if p2["winner"] == "A" else 0)
    vote_sum = v1 + v2
    delta = round(cand_score - champ_score, 2)

    if abs(pen_cand - pen_champ) >= 15.0 and abs(delta) >= 5.0:
        outcome = "cand_win" if delta > 0 else "champ_win"
    elif vote_sum >= 2 or (vote_sum == 1 and delta >= 1.5):
        outcome = "cand_win"
    elif vote_sum <= -2 or (vote_sum == -1 and delta <= -1.5):
        outcome = "champ_win"
    else:
        outcome = "tie"

    cand_defects = list(dict.fromkeys((p1.get("a_key_defects") or []) + (p2.get("b_key_defects") or []) + probe_cand["penalty_reasons"]))
    champ_defects = list(dict.fromkeys((p1.get("b_key_defects") or []) + (p2.get("a_key_defects") or []) + probe_champ["penalty_reasons"]))

    return {
        "case_id": beat_spec.get("case_id", ""),
        "outcome": outcome,
        "cand_score": cand_score,
        "champ_score": champ_score,
        "score_delta": delta,
        "vote_pass1": p1["winner"],
        "vote_pass2_swapped": p2["winner"],
        "cand_dim_avg": cand_dim_avg,
        "champ_dim_avg": champ_dim_avg,
        "probe_cand": probe_cand,
        "probe_champ": probe_champ,
        "cand_defects": cand_defects,
        "champ_defects": champ_defects,
        "pass1_detail": p1,
        "pass2_swapped_detail": p2,
    }


if __name__ == "__main__":
    print("video_arena_judge v2 (Target-Anchored + Hard Lip-Sync/Duration Probes) loaded.")
