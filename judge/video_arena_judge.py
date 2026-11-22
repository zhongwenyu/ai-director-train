#!/home/zhongwenyu/data/anaconda3/bin/python3
"""
Hermetic Multimodal Video Arena Judge (`judge/video_arena_judge.py`).

Enforces strict information-theoretic context isolation & cross-model heterogeneity:
  1. Uses heterogeneous `gemini-4-argon-medium` (distinct from Generator `gemini-4-carbon-medium`)
     inside an isolated empty `tempfile.TemporaryDirectory()` (`--sandbox --disable-slash-commands`).
  2. Stages ONLY anonymized media copies (`Video_A.mp4`, `Video_B.mp4`, `Character_Ref_1.png`, ...)
     inside that temporary directory — NEVER exposing `SKILL.md`, storyboard text, keyframe prompts,
     H3 video prompts, or version labels, and verifying via CLI log that zero paths outside the
     hermetic temp directory are ever read.
  3. Combines Order-Swapped Dual-Blind (`(A=cand, B=champ)` + `(A=champ, B=cand)`) multimodal evaluation
     with deterministic neural `Silero-VAD` & OpenCV motion/cut signal probes.
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
    timeout: int = 300,
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
                "1. 请且仅使用 `read_file` 工具依次完整读取下方列出的沙箱内媒体文件（视频请同时仔细观看画面与听取完整音轨）；\n"
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
                proc = subprocess.run(
                    cmd,
                    cwd=str(td_p),
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
            except subprocess.TimeoutExpired:
                last_err = f"argon timeout after {timeout}s (attempt {attempt})"
                time.sleep(2 * attempt)
                continue

            # Verify zero leak outside tmp_cwd in cli.log if present
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


def _get_vad_sess() -> ort.InferenceSession:
    global _VAD_SESS
    if _VAD_SESS is None:
        _VAD_SESS = ort.InferenceSession(str(DEFAULT_VAD_ONNX), providers=["CPUExecutionProvider"])
    return _VAD_SESS


def probe_video_signals(mp4_path: Path, has_spoken_dialogue: bool = True) -> Dict[str, Any]:
    """Deterministic container, neural Silero-VAD speech integrity, and motion/cut probes."""
    mp4_path = Path(mp4_path)
    probe = json.loads(
        subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(mp4_path)],
            text=True,
        )
    )
    vstream = next(s for s in probe["streams"] if s["codec_type"] == "video")
    astream = next((s for s in probe["streams"] if s["codec_type"] == "audio"), None)
    dur = float(probe["format"]["duration"])
    w, h = int(vstream["width"]), int(vstream["height"])

    vad_segments: List[Tuple[float, float]] = []
    tail_truncated = False
    speech_total_s = 0.0
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
        probs = np.empty(n_frames, dtype=np.float32)
        for i in range(n_frames):
            pr, h_st, c_st = sess.run(None, {"x": pcm[i * hop : (i + 1) * hop].reshape(1, hop), "h": h_st, "c": c_st})
            probs[i] = float(pr[0, 0])
        dt = hop / 16000.0
        in_s, s0 = False, 0
        for idx, p in enumerate(probs):
            if p >= 0.52 and not in_s:
                in_s, s0 = True, idx
            elif p < 0.52 and in_s:
                in_s = False
                if (idx - s0) * dt >= 0.16:
                    vad_segments.append((round(s0 * dt, 3), round(idx * dt, 3)))
        if in_s and (len(probs) - s0) * dt >= 0.16:
            vad_segments.append((round(s0 * dt, 3), round(len(probs) * dt, 3)))
        speech_total_s = round(sum(e - s for s, e in vad_segments), 3)
        if len(probs) >= 6 and float(probs[-6:].max()) >= 0.58:
            tail_truncated = True

    cap = cv2.VideoCapture(str(mp4_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    prev_gray = None
    diffs: List[float] = []
    cut_frames = 0
    step = max(1, int(round(fps / 6.0)))
    fidx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if fidx % step == 0:
            gray = cv2.cvtColor(cv2.resize(frame, (160, 90)), cv2.COLOR_BGR2GRAY).astype(np.float32)
            if prev_gray is not None:
                d = float(np.mean(np.abs(gray - prev_gray)))
                diffs.append(d)
                if d > 28.0:
                    cut_frames += 1
            prev_gray = gray
        fidx += 1
    cap.release()

    median_motion = round(float(np.median(diffs)) if diffs else 0.0, 3)
    frozen_slideshow = median_motion < 0.45

    penalty = 0.0
    penalty_reasons: List[str] = []
    if has_spoken_dialogue and speech_total_s < 0.5:
        penalty += 25.0
        penalty_reasons.append("MISSING_SPEECH_AUDIO")
    if tail_truncated:
        penalty += 10.0
        penalty_reasons.append("SPEECH_TAIL_TRUNCATED")
    if frozen_slideshow:
        penalty += 15.0
        penalty_reasons.append("FROZEN_STATIC_VIDEO")

    return {
        "width": w,
        "height": h,
        "duration_s": round(dur, 3),
        "speech_total_s": speech_total_s,
        "vad_segments": vad_segments,
        "tail_truncated": tail_truncated,
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

JUDGE_PAIR_PROMPT_TEMPLATE = """你是一位严苛、客观的真人实拍级 AI 短剧总导演与多模态视听评审官。
请用 `read_file` 完整读取并观看/听审两段匿名候选成片 `Video_A.mp4` 与 `Video_B.mp4`（均针对下方同一份【戏剧段落任务卡】生成），并对照附带的 `Character_Ref_*.png`【角色标准 0% 中性设定图】进行盲评。

【绝对盲审纪律】
1. 严禁脑补画面里没演出来的动作！必须同时仔细听两段视频的原声音轨（核对台词清晰度、语气呼吸感、口型同步、是否有吞尾字或心声乱动嘴）并逐秒观察画面！
2. 严禁给“同分和稀泥”——除非两段视频在全部 6 个维度真的毫无差别，否则必须明确分出 `A` 或 `B` 胜出！

【本段戏剧任务卡（脱敏纯文本题目）】
{beat_card_text}

【六维 100 分制客观评分标准（分别对 A 和 B 独立打分）】
1. `acting_micro_naturalism`（0–25分，表演微表情与具象肢体支点）：
   - 高分（20–25）：起幅面部自然放松不夸张；开口前有真实的视线流转、眨眼、微蹙眉或呼吸起伏；情绪通过具体、生活化的小动作支点（如手部轻触桌面/器物、扶额、歪头、侧身低语等）自然外化。
   - 低分（0–12）：全程像木偶站桩死盯镜头念稿，或首帧/中途出现五官扭曲的“歪嘴邪笑/惊悚瞪眼”假脸。
2. `vocal_dialogue_delivery`（0–20分，语言自然度、副语言气口与声画同步）：
   - 高分（16–20）：全部要求台词清晰完整无截断；语速自然有潜台词重音与生理呼吸感（如叹气、轻笑、停顿）；谁说话谁动嘴，听话人与内心独白（OS）期间双唇严格自然闭合。
   - 低分（0–10）：漏句/尾字被硬生生切断、机械播音腔、多人串嘴、或心声 OS 时人物跟着张嘴念白。
3. `editing_rhythm_and_reactions`（0–20分，剪辑节奏与听话人微反应插切）：
   - 高分（16–20）：切镜干脆利落（2–5秒一拍，无拖沓发呆空镜），在对手出招或长句尾端切入恰当的听话人无台词微表情反应镜（或流畅的声留画切 L-Cut），戏剧来回张力紧凑抓人。
   - 低分（0–10）：十几秒单机位死拍不切镜、切镜瞬间出现人物/衣服融化变形、或无故横摇甩镜。
4. `character_and_costume_consistency`（0–15分，角色五官与服装跨镜一致性）：
   - 对照【角色标准设定图】，核查五官骨相、发型轮廓、服装款式颜色在各切镜间是否稳定一致，有无同框克隆分身或衣服串色。
5. `cinematography_and_spatial_coherence`（0–10分，电影感景深构图与 180° 轴线）：
   - 对话戏是否善用中近景/特写与柔和浅景深（虚化杂乱背景突出人物眼神），前景过肩/遮挡是否有纵深感，正反打左右视线是否严守 180° 轴线。
6. `physical_anatomy_integrity`（0–10分，手部解剖与道具物理真实性）：
   - 手指结构是否正常、手持/交接道具是否唯一稳定（无凭空多出双份道具、穿模或漂浮慢动作）。"""


def _sum_scores(d: Dict[str, Any]) -> float:
    return float(sum(float(d.get(k, 0.0)) for k in DIM_KEYS))


def format_beat_card_for_judge(beat_spec: Dict[str, Any]) -> str:
    lines = [
        f"- 画幅与光影环境：{beat_spec.get('aspect_ratio', '16:9')} ｜ {beat_spec.get('setting_summary', '')}",
        f"- 戏剧目标与情绪弧线：{beat_spec.get('dramatic_goal', '')}",
        "- 出场角色：",
    ]
    for ch in beat_spec.get("characters", []):
        lines.append(f"  * {ch['role_id']}（{ch['display_name']}）：{ch['neutral_visual_bio']}")
    if beat_spec.get("props"):
        lines.append("- 关键道具：" + "；".join(f"{p['prop_id']}（{p['description']}）" for p in beat_spec["props"]))
    lines.append("- 本段台词 / 心声序列（需完整呈现）：")
    for idx, turn in enumerate(beat_spec.get("dialogue_turns", []), 1):
        mode_tag = "心声OS（画内闭嘴）" if turn.get("mode") == "inner_os" else "画内对白"
        lines.append(f"  {idx}. [{mode_tag}] {turn['speaker_id']}：“{turn['text']}”")
    return "\n".join(lines)


def _run_single_blind_pass(
    beat_card_text: str,
    char_refs: Sequence[Tuple[str, Path]],
    video_a: Path,
    video_b: Path,
    effort: str = "medium",
) -> Dict[str, Any]:
    media_items: List[Dict[str, Any]] = []
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
        {"kind": "video", "path": video_a, "anon_name": "Video_A.mp4", "caption": "匿名候选成片 Video_A（含完整音轨）"}
    )
    media_items.append(
        {"kind": "video", "path": video_b, "anon_name": "Video_B.mp4", "caption": "匿名候选成片 Video_B（含完整音轨）"}
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
    """Run Order-Swapped Dual-Blind (`(A=cand,B=champ)` + `(A=champ,B=cand)`) + deterministic signal probes."""
    has_spoken = any(t.get("mode") != "inner_os" for t in beat_spec.get("dialogue_turns", []))
    beat_card_text = format_beat_card_for_judge(beat_spec)

    # Run deterministic signal probes + BOTH order-swapped blind passes concurrently!
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        f_pc = ex.submit(probe_video_signals, cand_mp4, has_spoken)
        f_pr = ex.submit(probe_video_signals, champ_mp4, has_spoken)
        f_p1 = ex.submit(_run_single_blind_pass, beat_card_text, char_refs, cand_mp4, champ_mp4, effort)
        f_p2 = ex.submit(_run_single_blind_pass, beat_card_text, char_refs, champ_mp4, cand_mp4, effort)
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

    cand_score = round(max(0.0, (cand_raw_1 + cand_raw_2) / 2.0 - probe_cand["deterministic_penalty"]), 2)
    champ_score = round(max(0.0, (champ_raw_1 + champ_raw_2) / 2.0 - probe_champ["deterministic_penalty"]), 2)

    v1 = 1 if p1["winner"] == "A" else (-1 if p1["winner"] == "B" else 0)
    v2 = 1 if p2["winner"] == "B" else (-1 if p2["winner"] == "A" else 0)
    vote_sum = v1 + v2
    delta = round(cand_score - champ_score, 2)

    if vote_sum >= 2 or (vote_sum == 1 and delta >= 1.5):
        outcome = "cand_win"
    elif vote_sum <= -2 or (vote_sum == -1 and delta <= -1.5):
        outcome = "champ_win"
    elif abs(delta) >= 4.0 and probe_cand["deterministic_penalty"] != probe_champ["deterministic_penalty"]:
        outcome = "cand_win" if delta > 0 else "champ_win"
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
    print("video_arena_judge loaded successfully. AGY_BIN =", AGY_BIN)
