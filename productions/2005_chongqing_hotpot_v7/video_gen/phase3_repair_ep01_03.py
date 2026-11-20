#!/home/zhongwenyu/data/anaconda3/bin/python
"""
Phase 3 Unified 4-Way Fault-to-Action Repair Pipeline across Episodes 1, 2, and 3
driven directly by `supervisor_ep01..03.json` (`gemini-4-hydrogen-high` Script-Supervisor)
and `Silero-VAD` (`check_audio_integrity.py`).

Lanes executed concurrently:
  - Lane 0 (CPU, instant): `PATCH_AUDIO_ONLY` lossless `-c:v copy` room-tone window repair
    for shots with clean visuals and isolated non-dialogue vocal grunts (`1-3-06`, `1-3-11`, `3-1-14`, `3-1-24`).
  - Lane 1 (Spark GB10 `127.0.0.1:8338`): `REBUILD_ANCHOR_IMAGE` generating `ye_bare_wrist_front`
    first (~55s), followed by the 15 updated `Spatial Epoch` / `State-Transition` anchor images,
    signaling per-stem `threading.Event`s as each finishes.
  - Lane 2 (Local 5090 `127.0.0.1:8090`): `REWRITE_PROMPT_TIMELINE` (NEVER feeding motion/timing-defective
    videos back into `reference_video`), running Wave A (11 ready shots) immediately while Spark
    generates Wave B's anchors, then streaming Wave B (13 anchor-rebuilt shots), with automatic
    `Silero-VAD` verification & single auto-retry if `SPEECH_TRUNCATED` occurs.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List

import onnxruntime as ort

SKILL_SCRIPTS = Path("/home/zhongwenyu/project/ai-director-train/.agents/skills/hit-video/scripts")
WORK_DIR = Path("/home/zhongwenyu/project/ai-director-train/productions/2005_chongqing_hotpot_v7/video_gen")
for p in (str(SKILL_SCRIPTS), str(WORK_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import check_audio_integrity as vad_gate  # noqa: E402
import check_transitions  # noqa: E402
import pika_runner  # noqa: E402
from build_and_run_ep01_03_v7 import CLEAN_CAMERA, make_half_sec_strip  # noqa: E402
from compress_1k import compress_image_to_1k  # noqa: E402
from spark_h3_image import generate_spark_h3_image  # noqa: E402

ASSETS_1K = WORK_DIR / "assets_1k"
KF_2K = WORK_DIR / "keyframes_2k"
KF_1K = WORK_DIR / "keyframes_1k"
CACHE_1K = WORK_DIR / "cache_1k"
TAKES = {1: WORK_DIR / "takes_ep01", 2: WORK_DIR / "takes_ep02", 3: WORK_DIR / "takes_ep03"}
DIAG_DIR = WORK_DIR / "diag_strips"
AUDIT_DIR = WORK_DIR / "transition_audit"


def kf(stem: str) -> str:
    return str(KF_1K / f"{stem}_1k.png")


def patch_audio_window_with_room_tone(mp4_path: Path, bad_start: float, bad_end: float, donor_start: float) -> None:
    """Lossless `-c:v copy` replacement of an unscheduled vocal grunt window with clean room tone from the same clip."""
    dur = bad_end - bad_start
    tmp = mp4_path.with_suffix(".audiopatch.mp4")
    filt = (
        f"[0:a]aresample=48000,volume='if(between(t,{bad_start:.3f},{bad_end:.3f}),0.0,1.0)':eval=frame[main];"
        f"[0:a]aresample=48000,atrim={donor_start:.3f}:{donor_start + dur:.3f},asetpts=PTS-STARTPTS,"
        f"afade=t=in:d=0.04,afade=t=out:st={max(0.0, dur - 0.05):.3f}:d=0.04,"
        f"adelay={int(round(bad_start * 1000))}:all=1[fill];"
        f"[main][fill]amix=inputs=2:duration=first:normalize=0[a]"
    )
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-y", "-i", str(mp4_path),
            "-filter_complex", filt, "-map", "0:v", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(tmp),
        ],
        check=True,
    )
    tmp.replace(mp4_path)


def run_vo_mux(base_mp4: Path, vo_vocals: Path, final_mp4: Path, ss: float, se: float, ratio: float, dst_start: float, duck_lvl: float = 0.22) -> Dict[str, Any]:
    eff_dur = (se - ss) / ratio
    start_mute = max(0.0, dst_start - 0.08)
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
    return {"src": [ss, se], "atempo": ratio, "eff_dur": round(eff_dur, 3), "dst_start": dst_start}


def main() -> int:
    amap = json.loads((WORK_DIR / "asset_map.json").read_text(encoding="utf-8"))
    vad_sess = ort.InferenceSession(str(vad_gate.DEFAULT_VAD_ONNX))

    # --- LANE 0: Instant Lossless PATCH_AUDIO_ONLY ---
    audio_patches = [
        (1, "1-3-06", 0.30, 1.02, 1.30),
        (1, "1-3-11", 0.45, 0.92, 1.20),
        (3, "3-1-14", 7.38, 7.80, 6.00),
        (3, "3-1-24", 0.18, 0.82, 2.20),
    ]
    for ep_no, sid, bs, be, ds in audio_patches:
        mp4 = TAKES[ep_no] / sid / "video.mp4"
        patch_audio_window_with_room_tone(mp4, bs, be, ds)
        print(f"[PATCH_AUDIO_ONLY] Repaired {sid} [{bs:.2f}s..{be:.2f}s] losslessly (-c:v copy)", flush=True)

    # Asset shortcuts
    v_ye = amap["叶寻"]["voice"]
    v_lin = amap["林双双"]["voice"]
    v_chu = amap["楚南"]["voice"]
    v_zhao = amap["赵帆"]["voice"]
    v_qian = amap["夏芊芊"]["voice"]
    v_jian = amap["夏建国"]["voice"]
    v_thug = amap["混混"]["voice"]
    v_chen = amap["陈伯"]["voice"]

    f_ye_2020 = amap["叶寻 · 2020研发总厨白服"]["front_1k"]
    f_lin_banq = amap["林双双 · 塞纳左岸酒红礼服"]["front_1k"]
    f_chu_exec = amap["楚南 · 海归并购总监西装"]["front_1k"]
    f_ye_orig = amap["叶寻"]["front_1k"]
    f_lin = amap["林双双"]["front_1k"]
    f_chu = amap["楚南"]["front_1k"]
    f_zhao = amap["赵帆"]["front_1k"]
    f_qian = amap["夏芊芊"]["front_1k"]
    f_jian = amap["夏建国"]["front_1k"]
    f_thug = amap["混混"]["front_1k"]
    f_chen = amap["陈伯"]["front_1k"]

    sc_xia_hall = amap["夏氏小厨前厅与传菜口"]["main_1k"]
    sc_xia_kitch = amap["夏氏小厨后厨猛火炒灶"]["main_1k"]
    p_pot = amap["紫铜子母鸳鸯锅"]["main_1k"]
    p_doc = amap["配方无偿归属确认书与调岗单"]["main_1k"]

    ye_bare_2k = KF_2K / "ye_bare_wrist_front_2k.png"
    ye_bare_1k = ASSETS_1K / "ye_bare_wrist_front_1k.png"
    f_ye_bare = str(ye_bare_1k)

    # --- LANE 1: Spark MiniMax H3 Image Anchor Rebuilds ---
    spark_jobs = [
        {
            "stem": "ye_bare_wrist_front",
            "out_2k": ye_bare_2k,
            "out_1k": ye_bare_1k,
            "seed": 9001,
            "refs": [amap["叶寻"]["front_2k"]],
            "prompt": (
                "The young man standing in front of a clean studio background in <Picture 1> is <Subject 1>. "
                "The target image shows the exact same front portrait of <Subject 1> with one discrete state change: "
                "<Subject 1> is partially preserved, keeping the exact facial features, hairstyle, dark zip jacket over white t-shirt, dark trousers, lighting, and pose, "
                "except BOTH his left wrist and right wrist are completely bare skin with zero wristwatch, zero strap, and zero bracelet. "
                "Clean portrait, natural skin texture, zero text."
            ),
        },
        {
            "stem": "1-1_master_4p",
            "seed": 9101,
            "refs": [str(KF_2K / "1-1-01_2k.png"), f_ye_2020, f_lin_banq, f_chu_exec, f_zhao],
            "prompt": (
                "The luxury rooftop VIP dining room, round grey marble table, crystal champagne glasses, linear ceiling light strips, and night city skyline window in <Picture 1> are <Subject 1>. "
                "The chef in <Picture 2> is <Subject 2>. The woman in <Picture 3> is <Subject 3>. The executive man in <Picture 4> is <Subject 4>. The chef with red neckerchief in <Picture 5> is <Subject 5>. "
                "The target image shows a medium-wide 4-person standing confrontation around the round grey marble table inside <Subject 1>; "
                "<Subject 1> is partially preserved, keeping the exact round grey marble table (the silver tray on the table is now EMPTY with zero hat on the table, and a single printed white transfer slip lies near the left table edge), night skyline window, and cylindrical stainless-steel floor trash bin beside the left chair; "
                "<Subject 2>, <Subject 3>, <Subject 4>, and <Subject 5> are fully preserved in identity and outfit. "
                "On screen-left beside the round table, <Subject 2> stands upright wearing a thin black neck lanyard with a small square gold badge; "
                "on screen-right, <Subject 3> links both hands around <Subject 4>'s left arm while <Subject 5> on the far right holds the ONLY white gold-trimmed ceremonial chef cap at his chest. "
                "Crisp 35mm live-action cinema photography, zero duplicate hats, zero text."
            ),
        },
        {
            "stem": "1-1-07",
            "seed": 9107,
            "refs": [str(KF_2K / "1-1_master_4p_2k.png"), f_ye_2020],
            "prompt": (
                "The luxury rooftop VIP dining room, round grey marble table, crystal champagne glasses, and night city skyline window in <Picture 1> are <Subject 1>. "
                "The chef in <Picture 2> is <Subject 2>. "
                "The target image shows a medium close-up favoring <Subject 2> on screen-left facing screen-right beside the round grey marble table inside <Subject 1>; "
                "<Subject 1> is partially preserved, keeping the round grey marble table and champagne tower bokeh in the background (strictly NO long rectangular hotpot bar or copper pot); "
                "<Subject 2> is fully preserved in facial features, hairstyle, and white double-breasted jacket with a thin black neck lanyard and small square gold badge at his chest. "
                "Furrowing his brows earnestly, <Subject 2> leans slightly forward looking toward screen-right ready to speak. Crisp 35mm cinema photography, zero text."
            ),
        },
        {
            "stem": "1-1-10",
            "seed": 9110,
            "refs": [str(KF_2K / "1-1_master_4p_2k.png"), f_ye_2020, f_lin_banq, p_doc],
            "prompt": (
                "The luxury rooftop VIP dining room, round grey marble table, and night floor-to-ceiling city skyline window in <Picture 1> are <Subject 1>. "
                "The chef in <Picture 2> is <Subject 2>. The woman in <Picture 3> is <Subject 3>. The printed paper sheet in <Picture 4> is <Subject 4>. "
                "The target image shows a profile medium close-up two-shot beside the round grey marble table inside <Subject 1>; "
                "<Subject 1> is partially preserved, keeping the round grey marble table edge in the lower foreground and night city window directly behind them (strictly NO long rectangular bar and NO copper hotpot in the background); "
                "<Subject 2> and <Subject 3> are fully preserved in appearance and outfit. "
                "On screen-left, <Subject 2> stands upright wearing his thin black neck lanyard and small square gold badge; on screen-right facing him, <Subject 3> tucks a black folder under her left arm while pressing <Subject 4> against <Subject 2>'s chest with her right hand. "
                "Crisp 35mm cinema photography, zero text overlays."
            ),
        },
        {
            "stem": "1-1-13_aux",
            "seed": 9113,
            "refs": [str(KF_2K / "1-1_master_4p_2k.png"), f_ye_2020, f_lin_banq, f_chu_exec, f_zhao],
            "prompt": (
                "The luxury rooftop VIP dining room, round grey marble table, cylindrical floor trash bin, and night city skyline window in <Picture 1> are <Subject 1>. "
                "The chef in <Picture 2> is <Subject 2>. The woman in <Picture 3> is <Subject 3>. The executive man in <Picture 4> is <Subject 4>. The chef in <Picture 5> is <Subject 5>. "
                "The target image shows a wide interior shot across the round grey marble table toward dark double wooden exit doors on the right-rear wall of <Subject 1>; "
                "<Subject 1> is partially preserved, retaining the cylindrical stainless-steel trash bin beside the left chair and keeping the white transfer slip, a champagne glass, and the discarded black-lanyard gold badge resting on the round grey marble tabletop; "
                "<Subject 2>, <Subject 3>, <Subject 4>, and <Subject 5> are fully preserved. "
                "On screen-left standing behind the round table, <Subject 3>, <Subject 4>, and <Subject 5> watch coldly; at right-rear, <Subject 2> (seen from behind without neck lanyard) pushes open the dark double wooden exit door to leave. "
                "Crisp 35mm cinema photography, zero text."
            ),
        },
        {
            "stem": "1-3-21",
            "seed": 9121,
            "refs": [str(KF_2K / "1-3_doorway_master_2k.png"), f_ye_orig],
            "prompt": (
                "The open weathered glass-paned double wooden shop doors opening onto the flat sunlit 2005 Chongqing bluestone pedestrian lane in <Picture 1> are <Subject 1>. "
                "The young man in <Picture 2> is <Subject 2>. "
                "The target image shows a medium close-up of <Subject 2> standing alone at the open wooden doorway threshold of <Subject 1>; "
                "<Subject 1> is partially preserved, keeping the exact glass-paned weathered wooden doorframe and flat sunlit bluestone lane outside (zero steep mountain staircase, zero outdoor brick stove, zero cars); "
                "<Subject 2> is fully preserved in facial features, hairstyle, and dark jacket over white t-shirt, carrying a zipper-top faded army-green canvas backpack slung over his right shoulder and wearing a small black plastic digital watch on his left wrist. "
                "Standing at the sunlit threshold with his right hand holding the front green strap, <Subject 2> half-glances coolly back toward the interior on screen-left. Crisp 35mm cinema photography, zero text."
            ),
        },
        {
            "stem": "2-1-01",
            "seed": 9201,
            "refs": [str(KF_2K / "1-3_doorway_master_2k.png"), f_ye_orig, f_lin],
            "prompt": (
                "The open weathered wooden shop doorway, square wooden tables inside, two flat grey stone steps, and flat sunlit Chongqing bluestone pedestrian lane in <Picture 1> are <Subject 1>. "
                "The young man in <Picture 2> is <Subject 2>. The young woman in <Picture 3> is <Subject 3>. "
                "The target image shows a medium two-shot outside the open wooden doorway on the two flat stone steps of <Subject 1>; "
                "<Subject 1> is partially preserved, keeping the wide-open wooden doors on screen-left showing square wooden tables inside and flat bluestone lane on screen-right (strictly ZERO outdoor brick stove, ZERO outdoor wok, ZERO red lantern, ZERO signboards); "
                "<Subject 2> and <Subject 3> are fully preserved in facial identity, hairstyle, and outfit. "
                "On screen-left standing on the lower stone step facing screen-right, <Subject 2> wears his zipper-top faded army-green canvas backpack over his right shoulder and a small black plastic digital watch on his left wrist; "
                "on screen-right standing on the upper stone step facing screen-left, <Subject 3> (wearing only a thin delicate gold chain on her left wrist) reaches out with her right hand to grip <Subject 2>'s taut army-green backpack strap at shoulder height with a smug sneer. "
                "Crisp 35mm cinema photography, zero text."
            ),
        },
        {
            "stem": "2-1-04",
            "seed": 9204,
            "refs": [str(KF_2K / "2-1-01_2k.png"), f_lin, f_ye_orig],
            "prompt": (
                "The wide-open weathered wooden shop doorway (showing sunlit interior tables behind, NOT closed doors) and two flat stone steps in <Picture 1> are <Subject 1>. "
                "The young woman in <Picture 2> is <Subject 2>. The young man in <Picture 3> is <Subject 3>. "
                "The target image shows a tighter medium close-up framed from the exact open-doorway blocking of <Picture 1>; "
                "<Subject 1> is partially preserved, keeping the wooden shop doors WIDE OPEN behind <Subject 2> (never closed wooden panels); "
                "<Subject 2> and <Subject 3> are fully preserved in appearance and outfit. "
                "Standing on the upper stone step on screen-right facing screen-left, <Subject 2> grips <Subject 3>'s taut army-green canvas backpack strap at shoulder height on the left edge of the frame with her right hand, "
                "while extending her open left palm forward toward screen-left (wearing only her thin delicate gold wrist chain) demanding something with a lifted chin. "
                "Crisp 35mm cinema photography, zero text."
            ),
        },
        {
            "stem": "2-1_post_watch_master",
            "seed": 9207,
            "refs": [str(KF_2K / "2-1-01_2k.png"), f_ye_bare, f_lin, f_chu],
            "prompt": (
                "The wide-open weathered wooden shop doorway, two flat grey stone steps, and flat sunlit bluestone lane (zero outdoor brick stove, zero signboards) in <Picture 1> are <Subject 1>. "
                "The bare-wristed young man in <Picture 2> is <Subject 2>. The young woman in <Picture 3> is <Subject 3>. The young man in floral shirt and dark blazer in <Picture 4> is <Subject 4>. "
                "The target image shows a medium 3-person confrontation on the exact two flat stone steps of <Subject 1>; "
                "<Subject 1> is partially preserved in exact open-doorway woodwork and flat stone steps; "
                "<Subject 2>, <Subject 3>, and <Subject 4> are fully preserved in facial features, hairstyle, and outfit. "
                "On screen-left on the lower stone step, <Subject 2> stands tall wearing his zipper-top faded army-green canvas backpack on his right shoulder with BOTH wrists completely bare skin (zero wristwatch on <Subject 2>); "
                "in center-right on the upper stone step, <Subject 3> stands stunned with BOTH her wrists bare of any black watch (only her thin gold chain on left wrist), holding the SINGLE returned small black plastic wristwatch in her left hand against her chest while her right hand STILL grips <Subject 2>'s taut army-green backpack strap; "
                "at the right wooden doorframe behind her, <Subject 4> leans with folded arms smirking. Crisp 35mm cinema photography, zero duplicate watches, zero text."
            ),
        },
        {
            "stem": "2-1-08",
            "seed": 9208,
            "refs": [str(KF_2K / "2-1_post_watch_master_2k.png"), f_ye_bare],
            "prompt": (
                "The sunlit wooden shopfront doorway and flat stone lane in <Picture 1> are <Subject 1>. "
                "The bare-wristed young man in <Picture 2> is <Subject 2>. "
                "The target image shows a close-up favoring <Subject 2> on screen-left facing screen-right in front of the softly blurred open doorway of <Subject 1>; "
                "<Subject 1> is partially preserved in midday lighting; <Subject 2> is fully preserved in facial features, hairstyle, and dark jacket over white t-shirt, with the zipper-top faded army-green canvas backpack strap (strictly army-green, never tan or yellow) on his right shoulder and bare wrists. "
                "With closed lips and sharp jawline in midday sun, <Subject 2> looks coldly toward screen-right. Crisp 35mm cinema photography, zero text."
            ),
        },
        {
            "stem": "2-1-11",
            "seed": 9211,
            "refs": [str(KF_2K / "2-1_post_watch_master_2k.png"), f_lin, f_chu],
            "prompt": (
                "The open weathered wooden shop doorway in <Picture 1> is <Subject 1>. "
                "The young woman in <Picture 2> is <Subject 2>. The young man in dark blazer in <Picture 3> is <Subject 3>. "
                "The target image shows a waist-up standing close-up of <Subject 2> on the upper stone step of <Subject 1> turning her head urgently over her right shoulder toward <Subject 3> leaning at the right-rear wooden doorframe; "
                "<Subject 1> is partially preserved; <Subject 2> and <Subject 3> are fully preserved in appearance and outfit. "
                "Standing upright, <Subject 2> has ONLY a thin delicate gold chain on her left wrist (strictly ZERO black watch worn on her wrist!), holds the SINGLE small black plastic wristwatch in her left hand at her chest, while her right arm extends toward lower-left holding the taut green backpack strap. "
                "Crisp 35mm cinema photography, zero duplicate watches, zero text."
            ),
        },
        {
            "stem": "2-1-14",
            "seed": 9214,
            "refs": [str(KF_2K / "2-1_post_watch_master_2k.png"), f_ye_bare, f_lin, f_chu],
            "prompt": (
                "The open weathered wooden shop doorway and two flat stone steps in <Picture 1> are <Subject 1>. "
                "The bare-wristed young man in <Picture 2> is <Subject 2>. The young woman in <Picture 3> is <Subject 3>. The young man in dark blazer in <Picture 4> is <Subject 4>. "
                "The target image shows the exact medium 3-person doorway steps blocking of <Picture 1>; "
                "<Subject 1> is partially preserved; <Subject 2>, <Subject 3>, and <Subject 4> are fully preserved. "
                "On screen-left on the lower stone step, <Subject 2> (BOTH wrists completely bare without any watch!) raises his bare right hand to grip the upper part of his own army-green canvas backpack strap on his right shoulder, ready to yank it free; "
                "in center-right on the upper step, <Subject 3> (NO black watch on her wrists!) holds the single small black wristwatch at her chest with her left hand while her right hand still holds <Subject 2>'s green strap; at the right doorframe, <Subject 4> watches. "
                "Crisp 35mm cinema photography, zero duplicate watches, zero text."
            ),
        },
        {
            "stem": "2-1-14_street_aux",
            "seed": 9215,
            "refs": [str(KF_2K / "2-2-01_2k.png"), str(KF_2K / "2-1-01_2k.png"), f_ye_bare],
            "prompt": (
                "The quiet sunlit 2005 Chongqing bluestone pedestrian lane between two clean signless traditional wooden shopfronts (zero outdoor tables, zero signboards) in <Picture 1> and <Picture 2> is <Subject 1>. "
                "The bare-wristed young man in <Picture 3> is <Subject 2>. "
                "The target image shows a wide sunlit street view along <Subject 1> following <Subject 2> from behind as he strides across the narrow bluestone road toward the facing wooden shopfront; "
                "<Subject 1> is partially preserved; <Subject 2> is fully preserved with BOTH wrists completely bare (zero wristwatch on left or right wrist!) and the faded army-green canvas backpack slung over his RIGHT shoulder (single right shoulder, matching his exit). "
                "Crisp 35mm cinema photography, zero text."
            ),
        },
        {
            "stem": "2-3-05_qian_aux",
            "seed": 9235,
            "refs": [sc_xia_hall, f_qian],
            "prompt": (
                "The clean sunlit 2005 traditional small restaurant dining hall with white plaster walls, square wooden tables, wooden pass-through kitchen window, and closed dark-blue cloth curtain (strictly ZERO modern glass beverage fridge, ZERO stainless-steel appliances, ZERO aluminum sliding doors) in <Picture 1> is <Subject 1>. "
                "The young woman in grey t-shirt and black apron in <Picture 2> is <Subject 2>. "
                "The target image shows an over-the-counter medium close-up of <Subject 2> standing behind the dark wooden counter inside <Subject 1> facing screen-left, with one closed brown leather ledger and one twine-tied coarse burlap herb bundle on the counter foreground; "
                "<Subject 1> is partially preserved with authentic 2005 plaster walls, wooden tables, and dark-blue cloth curtain behind her (zero modern glowing refrigerator); <Subject 2> is fully preserved, raising her left hand slightly in surprised protest. "
                "Crisp 35mm cinema photography, zero text."
            ),
        },
        {
            "stem": "2-3-08",
            "seed": 9238,
            "refs": [str(KF_2K / "2-3-08_2k.png"), f_ye_bare],
            "prompt": (
                "The traditional eatery front hall, dark wooden counter with twine-tied coarse burlap herb bundle, closed dark-blue cloth kitchen curtain in rear, and blurred female shoulder in right foreground in <Picture 1> are <Subject 1>. "
                "The bare-wristed young man in <Picture 2> is <Subject 2>. "
                "The target image shows the exact same over-the-shoulder close-up of <Subject 1> with one discrete state correction: "
                "<Subject 1> is partially preserved in exact room layout, lighting, counter, herb bundle, and open army-green canvas backpack on <Subject 2>'s left arm; "
                "<Subject 2> is fully preserved except BOTH his wrists are completely bare skin with ZERO wristwatch on his left or right wrist. "
                "Crisp 35mm cinema photography, zero text."
            ),
        },
        {
            "stem": "2-3-13_aux",
            "seed": 9239,
            "refs": [str(KF_2K / "2-3-13_aux_2k.png"), f_ye_bare, f_qian, f_jian],
            "prompt": (
                "The traditional eatery front hall with the dark wooden counter and coarse burlap herb bundle on screen-right, dining tables on screen-left, and dark-blue cloth kitchen curtain on the rear wall in <Picture 1> is <Subject 1>. "
                "The bare-wristed young man in <Picture 2> is <Subject 2>. The young woman in black apron in <Picture 3> is <Subject 3>. The older chef in <Picture 4> is <Subject 4>. "
                "The target image shows the exact same three-layer depth medium shot of <Subject 1> with clean prop consistency: "
                "the dark wooden counter on lower-right foreground holds ONLY the single twine-tied coarse burlap herb bundle (remove the extra glass spice jars on the right edge); "
                "<Subject 2> stands behind the right counter with his army-green canvas backpack on his left arm and his bare right hand resting on the herb bundle (BOTH wrists completely bare with ZERO wristwatch!); "
                "<Subject 3> stands anxiously beside him in center-right; at left-rear on the flat floor before the dark-blue cloth kitchen curtain, <Subject 4> stands clutching his sore neck with his left hand and holding a long iron wok ladle in his right hand. "
                "Crisp 35mm cinema photography, zero modern appliances, zero text."
            ),
        },
        {
            "stem": "2-3-11",
            "seed": 9240,
            "refs": [str(KF_2K / "2-3-13_aux_2k.png"), f_qian, f_ye_bare],
            "prompt": (
                "The traditional eatery front hall with the clean dark wooden counter and single coarse burlap herb bundle on screen-right in <Picture 1> is <Subject 1>. "
                "The young woman in black apron in <Picture 2> is <Subject 2>. The bare-wristed young man in <Picture 3> is <Subject 3>. "
                "The target image shows a medium close-up two-shot on screen-right beside the dark wooden counter looking anxiously toward screen-left; "
                "<Subject 1> is partially preserved with ONLY the coarse burlap herb bundle on the wooden counter (zero glass spice jars); "
                "<Subject 3> stands on screen-right with his army-green canvas backpack on his left arm and his bare right hand on the herb bundle (BOTH wrists completely bare skin with ZERO wristwatch!); "
                "<Subject 2> steps half a pace forward in center-right looking earnestly toward screen-left. Crisp 35mm cinema photography, zero text."
            ),
        },
        {
            "stem": "3-1-01",
            "seed": 9301,
            "refs": [str(KF_2K / "2-3-13_aux_2k.png"), f_jian, f_qian, f_ye_bare],
            "prompt": (
                "The traditional eatery front hall in <Picture 1> (wooden counter and coarse burlap herb bundle strictly on SCREEN-RIGHT, square wooden dining tables and benches on SCREEN-LEFT, rear wall with wooden pass-through window and dark-blue cloth curtain, ZERO modern silver refrigerator) is <Subject 1>. "
                "The older chef in <Picture 2> is <Subject 2>. The young woman in black apron in <Picture 3> is <Subject 3>. The bare-wristed young man in <Picture 4> is <Subject 4>. "
                "The target image shows a medium wide shot inside <Subject 1> preserving the EXACT left-right room topology of <Picture 1>: "
                "on SCREEN-LEFT beside a square wooden dining table in front of the dark-blue curtain, <Subject 2> bends slightly coughing raspingly while clutching his sore neck with his left hand and holding the iron wok ladle in his right hand, as <Subject 3> supports his arm guiding him onto the wooden bench; "
                "on SCREEN-RIGHT beside the dark wooden counter, <Subject 4> (bare wrists, army-green canvas backpack on his left arm, right hand near the herb bundle) looks toward <Subject 2> on screen-left with concern. "
                "Crisp 35mm cinema photography, zero modern refrigerator, zero text."
            ),
        },
    ]

    ready_events: Dict[str, threading.Event] = {j["stem"]: threading.Event() for j in spark_jobs}
    spark_error: List[BaseException] = []

    def spark_worker() -> None:
        staged: set[str] = set()
        try:
            for idx, j in enumerate(spark_jobs, start=1):
                stem = j["stem"]
                o2 = j.get("out_2k", KF_2K / f"{stem}_2k.png")
                o1 = j.get("out_1k", KF_1K / f"{stem}_1k.png")
                t0 = time.time()
                print(f"[Spark {idx}/{len(spark_jobs)}] Generating {stem} ...", flush=True)
                generate_spark_h3_image(
                    prompt=j["prompt"],
                    out_path=o2,
                    out_1k_path=o1,
                    ref_images=j["refs"],
                    aspect_ratio="9:16",
                    seed=j["seed"],
                    steps=6,
                    staged_cache=staged,
                )
                print(f"[Spark {idx}/{len(spark_jobs)}] DONE {stem} in {time.time() - t0:.1f}s", flush=True)
                ready_events[stem].set()
        except BaseException as exc:
            spark_error.append(exc)
            for ev in ready_events.values():
                ev.set()
            raise

    spark_thread = threading.Thread(target=spark_worker, daemon=True)
    spark_thread.start()

    # Wait ~55s for `ye_bare_wrist_front` so all Ep 2 & Ep 3 shots use bare-wrist Ye Xun!
    ready_events["ye_bare_wrist_front"].wait()
    if spark_error:
        raise spark_error[0]

    # --- Updated Shot Specs (Wave A = no further Spark wait; Wave B = waits on specific Spark stems) ---
    repair_specs: List[Dict[str, Any]] = [
        # ================= WAVE A (Immediate 5090 Execution while Spark builds anchors!) =================
        {
            "id": "1-1-04", "episode": 1, "duration": 12, "seed": 81104, "wait_stems": [],
            "ref_images": [kf("1-1-04"), f_ye_2020, f_chu_exec, f_zhao],
            "ref_audios": [v_chu, v_zhao],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The man standing silently on screen-left in <Picture 1>, matching <Picture 2>.\n"
                "- <Subject 2> (S1): The executive man on screen-right in <Picture 1>, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 3> (S2): The Western-style chef holding the white gold-trimmed ceremonial cap, matching <Picture 4>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-3.0s) Medium shot framed from <Picture 1> beside the leather chair, cylindrical stainless-steel floor trash bin, and round grey marble table.\n"
                "- [Shot 2] (3.0s-7.5s) Medium close-up favoring <Subject 2> on screen-right beside the completely bare, clean round grey marble table.\n"
                "- [Shot 3] (7.5s-12.0s) Close-up on <Subject 3> on screen-right in front of the night skyline window holding the white gold-trimmed ceremonial cap.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-2.9s): Pinching the faded cloth off the chair back with two right-hand fingers, <Subject 2> holds it directly over the open cylindrical floor trash bin and drops it straight down INSIDE the trash bin (never placing any cloth onto the marble table) while <Subject 1> glares silently.\n"
                "- [Shot 2] (3.1s-7.3s): Dusting his fingertips above the completely empty round marble tabletop, <Subject 2> (S1) sneers toward screen-left: <d>[Chinese] 老叶，上市得讲门面，你那套土锅底，早该翻篇了。</d>\n"
                "- [Shot 3] (7.7s-11.3s): Holding the white gold-trimmed ceremonial cap proudly at his chest, <Subject 3> (S2) boasts toward screen-left: <d>[Chinese] 往后店里主打法式鹅肝融火锅，只接高档客。</d> He closes his mouth smugly right as he finishes.\n"
                "[Environment]\n- Luxury rooftop banquet VIP room at night with round grey marble table and skyline window.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Soft thud of cloth dropping inside metal bin, arrogant male sneer, boastful male line, zero music."
            ),
        },
        {
            "id": "1-3-01", "episode": 1, "duration": 13, "seed": 81301, "wait_stems": [],
            "ref_images": [kf("1-3-01"), kf("1-3-06"), f_ye_orig, f_lin, f_chu],
            "ref_audios": [v_lin],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The young man waking up at the square wooden table in <Picture 1>, matching <Picture 3>.\n"
                "- <Subject 2> (S1): The young woman standing on screen-right of the square wooden table in <Picture 2>, matching <Picture 4>. Voice matches Audio 1.\n"
                "- <Subject 3>: The young man seated on a wooden chair beside <Subject 2> with a red aluminum cola can in <Picture 2>, matching <Picture 5>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-3.2s) Medium close-up framed from <Picture 1> beneath the spinning green ceiling fan.\n"
                "- [Shot 2] (3.2s-5.6s) High-angle close-up on the half-open army-green canvas backpack resting on the wooden bench beside <Subject 1>'s thigh.\n"
                "- [Shot 3] (5.6s-13.0s) Over-the-shoulder medium shot framed from <Picture 2> past <Subject 1> on screen-left onto <Subject 2> and <Subject 3> across the square wooden table.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-3.1s): <Subject 1> jolts upright from the wooden table gasping once and reaches his right hand down to the canvas backpack on the bench.\n"
                "- [Shot 2] (3.3s-5.5s): <Subject 1>'s right hand reaches inside the half-open zipper and squeezes the twine-tied coarse cloth herb bundle firmly INSIDE the backpack (leaving the herb bundle tucked inside the bag without pulling it out).\n"
                "- [Shot 3] (5.8s-11.4s): While <Subject 3> sips iced cola on screen-right, <Subject 2> (S1) frowns impatiently, holds out her open palm toward <Subject 1>, and demands clearly: <d>[Chinese] 叶寻，发什么呆呢，赶紧把你爷爷那方子拿出来呀。</d> Immediately upon finishing, she keeps her lips closed waiting impatiently.\n"
                "[Environment]\n- Sunlit 2005 Chongqing eatery hall (<Picture 2>) with square dark-brown wooden table and ceiling fan.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Creaking ceiling fan, brief gasp, canvas rustle, impatient complete female demand finishing with clean room tone, zero music."
            ),
        },
        {
            "id": "2-2-01", "episode": 2, "duration": 12, "seed": 82201, "wait_stems": [],
            "ref_images": [kf("2-2-01"), f_qian, f_thug],
            "ref_audios": [v_thug, v_qian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S2): The young woman standing beside the right wooden doorpost in <Picture 1>, matching <Picture 2>. Voice matches Audio 2.\n"
                "- <Subject 2> (S1): The street punk stepping onto the stone steps on screen-left in <Picture 1> holding colorful flyers, matching <Picture 3>. Voice matches Audio 1.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-2.4s) Medium-wide shot framed from <Picture 1> outside the quiet signless wooden storefront.\n"
                "- [Shot 2] (2.4s-8.0s) Medium close-up two-shot with <Subject 2> on screen-left pressing in toward <Subject 1> backed against the right wooden pillar.\n"
                "- [Shot 3] (8.0s-12.0s) Close-up on <Subject 1> and <Subject 2>'s reaching right hand.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-2.3s): <Subject 1> peels the old paper notice off the wooden pillar and clutches the crumpled paper tightly inside her right fist at her side (never dropping it onto the ground) as <Subject 2> steps up with a sleazy grin.\n"
                "- [Shot 2] (2.6s-7.8s): Shoving a colorful loan flyer toward <Subject 1> while she keeps the crumpled paper in her right hand, <Subject 2> (S1) coaxes: <d>[Chinese] 小老板娘，招工纸都撕啦，周转不开签两万块应急呗。</d>\n"
                "- [Shot 3] (8.2s-10.2s): Brushing the flyer back with her left hand, <Subject 1> (S2) says firmly: <d>[Chinese] 不借，你让开。</d> She presses her lips shut right after speaking.\n"
                "- [Shot 3] (10.3s-12.0s): Scowling, <Subject 2> reaches his right hand straight forward toward <Subject 1>'s left forearm.\n"
                "[Environment]\n- Quiet sunlit stone steps outside a traditional Chongqing eatery, zero signboards.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Paper peeled and crumpled in hand, footsteps on stone, sleazy male coaxing, firm female refusal, zero music."
            ),
        },
        {
            "id": "3-1-04", "episode": 3, "duration": 14, "seed": 83104, "wait_stems": [],
            "ref_images": [kf("3-1-04"), sc_xia_hall, f_ye_bare, f_jian, f_qian],
            "ref_audios": [v_ye, v_qian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The bare-wristed young man standing by the wooden counter with the coarse cloth herb bundle in <Picture 1>, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 2>: The master chef seated at the empty clean square wooden table, matching <Picture 4>.\n"
                "- <Subject 3> (S2): The young woman standing beside <Subject 2>, matching <Picture 5>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-6.4s) Over-the-shoulder close-up framed from <Picture 1> onto <Subject 1> (bare wrists) patting the coarse cloth herb bundle.\n"
                "- [Shot 2] (6.4s-11.0s) Medium close-up inside <Picture 2> as <Subject 3> bends gently beside <Subject 2> seated at a bare wooden dining table (only a white porcelain cup on the wood, strictly NO black wok and NO metal sphere on the table).\n"
                "- [Shot 3] (11.0s-14.0s) Medium shot inside the traditional plaster-walled front hall of <Picture 2> (wooden pass-through window and dark-blue cloth kitchen curtain, strictly NO air conditioner and NO plastic strips) as <Subject 2> lays his iron ladle flat on the wooden table and <Subject 1> carries the herb bundle through the blue curtain.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-6.2s): Patting the coarse herb bundle firmly, <Subject 1> (S1) pledges clearly: <d>[Chinese] 后厨小灶借我四十分钟，熬出来您尝一口，要是烧嗓子，我拎包就走。</d>\n"
                "- [Shot 2] (6.6s-10.8s): Holding <Subject 2>'s arm gently beside the clean wooden table, <Subject 3> (S2) coaxes warmly: <d>[Chinese] 爸，小寻从小不说空话，就让他开火试试嘛。</d>\n"
                "- [Shot 3] (11.1s-14.0s): <Subject 2> sets his long iron wok ladle flat onto the clean wooden tabletop in silent consent while <Subject 1> lifts the herb bundle in both hands and walks briskly through the dark-blue cloth kitchen curtain.\n"
                "[Environment]\n- Traditional 2005 restaurant front hall (<Picture 2>) with bare wooden tables, wooden pass-through window, and dark-blue cloth curtain, zero air conditioners.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Confident male pledge, warm female coaxing, metallic clink of ladle laid flat on wood, footsteps, zero music."
            ),
        },
        {
            "id": "3-1-08", "episode": 3, "duration": 9, "seed": 83108, "wait_stems": [],
            "ref_images": [kf("3-1-08"), p_pot, sc_xia_kitch, f_ye_bare],
            "ref_audios": [],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The bare-wristed young man cooking at the red-brick stove in <Picture 1>, matching <Picture 4>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-3.3s) Medium close-up framed from <Picture 1> at the traditional red-brick stove in <Picture 3>.\n"
                "- [Shot 2] (3.3s-6.2s) Overhead close-up into the iron wok as browned dried roots and bark spices are lifted out with a mesh strainer and solid white beef tallow melts into clear amber-red oil (no green pine needles, no whole raw red chilies).\n"
                "- [Shot 3] (6.2s-9.0s) Medium shot at the same traditional red-brick stove of <Picture 3> (strictly NO modern stainless-steel gas range) showing the dual-chamber concentric copper pot with inner small round pot of <Picture 2> simmering gently beside the open wooden alley window.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-3.2s): Untying the burlap bundle, <Subject 1> tips dried brown medicinal herbs into warm golden oil in the wok and stirs steadily with a wooden ladle.\n"
                "- [Shot 2] (3.4s-6.1s): <Subject 1> lifts the infused dried herbs cleanly out with a fine mesh strainer while sliding white beef tallow into the rich amber-red oil.\n"
                "- [Shot 3] (6.3s-9.0s): Inside the dual-chamber concentric copper pot (<Picture 2>) on the red-brick stove, clear ruby broth simmers in the outer ring and milky broth in the inner ring as fragrant white steam drifts out the open wooden window into the Chongqing stone alley.\n"
                "[Environment]\n- Traditional 2005 red-brick kitchen (<Picture 3>) with wooden window opening onto a Chongqing stone alley.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Stove flame, gentle oil sizzle, mesh strainer clink, simmering broth, zero speech, zero music."
            ),
        },
        {
            "id": "3-1-18", "episode": 3, "duration": 13, "seed": 83118, "wait_stems": [],
            "ref_images": [kf("3-1-18"), f_jian, f_qian],
            "ref_audios": [v_jian, v_qian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The master chef seated at the wooden table in <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The young woman standing beside him, matching <Picture 3>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-2.0s) Push-in close-up starting from <Picture 1> onto <Subject 1> swallowing smoothly.\n"
                "- [Shot 2] (2.0s-7.4s) Close-up on <Subject 1> touching his neck in amazement.\n"
                "- [Shot 3] (7.4s-13.0s) Close-up on <Subject 2> clasping her hands joyfully while looking warmly downward toward <Subject 1> on lower-right (never staring into the camera lens).\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-1.9s): Swallowing without pain, <Subject 1> widens his eyes and touches his throat.\n"
                "- [Shot 2] (2.2s-7.2s): Feeling his neck in disbelief, <Subject 1> (S1) exclaims in a clear resonant voice: <d>[Chinese] 奇了，嗓子眼里那股火辣辣顶着的劲儿，真散了。</d>\n"
                "- [Shot 3] (7.6s-11.4s): Clasping both hands happily and looking down toward her seated father, <Subject 2> (S2) cheers brightly: <d>[Chinese] 爸，你听你说话，嗓子不劈也不哑了。</d> Immediately upon finishing the complete sentence, she smiles warmly with closed lips.\n"
                "[Environment]\n- Warm sunlit traditional eatery hall.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Smooth swallow, clear booming male exclamation, complete joyful female cheer followed by 1.5s quiet room tone, zero music."
            ),
        },
        {
            "id": "3-1-21", "episode": 3, "duration": 13, "seed": 83121, "wait_stems": [],
            "ref_images": [kf("3-1-21"), p_pot, f_chen, f_ye_bare],
            "ref_audios": [v_chen, v_ye],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The neighborhood uncle holding a palm-leaf fan at the open wooden window in <Picture 1>, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The bare-wristed young man standing inside beside the flat dual-chamber concentric copper pot (<Picture 2>, flat open rim with inner round divider and ZERO central chimney), matching <Picture 4>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-1.9s) Close-up framed from <Picture 1> as <Subject 1> slaps a twenty-yuan bill onto the wooden windowsill.\n"
                "- [Shot 2] (1.9s-6.6s) Close-up on <Subject 1> leaning eagerly through the window.\n"
                "- [Shot 3] (6.6s-13.0s) Over-the-shoulder medium close-up past <Subject 1> (keeping his palm-leaf fan and exact appearance from <Picture 3>) onto <Subject 2> beside the flat concentric copper pot of <Picture 2> (no tall chimney).\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-1.8s): <Subject 1> slaps a twenty-yuan banknote onto the wooden windowsill.\n"
                "- [Shot 2] (2.0s-6.4s): Pushing the bill forward eagerly, <Subject 1> (S1) calls out: <d>[Chinese] 老夏你可别吃独食，闻着一点不呛嗓子，赶紧给我盛一碗。</d>\n"
                "- [Shot 3] (6.8s-11.5s): Smiling warmly and gesturing with his bare hand for <Subject 1> to take back the money, <Subject 2> (S2) replies clearly: <d>[Chinese] 陈伯钱收回去，等过几天新锅挂牌，头一顿请您白吃。</d> Right after finishing the last word, he nods warmly with closed lips.\n"
                "[Environment]\n- Open wooden window between sunlit stone alley and traditional dining hall.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Crisp slap of banknote, hearty neighbor shout, complete warm male reply finishing with 1.4s room tone, zero music."
            ),
        },
        {
            "id": "3-2-08", "episode": 3, "duration": 14, "seed": 83208, "wait_stems": [],
            "vo_reuse": {"vocals": TAKES[3] / "3-2-08" / "vo_short_vocals.wav", "ss": 0.238, "se": 5.184, "ratio": 1.236, "dst_start": 0.30},
            "ref_images": [kf("3-2-08"), kf("3-2-09_aux"), f_ye_bare, f_chu, f_lin, f_zhao, f_qian, f_jian],
            "ref_audios": [v_chu],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The bare-wristed young man standing calmly on the stone steps in <Picture 1>, matching <Picture 3>.\n"
                "- <Subject 2> (S1): The young man raising a red-and-white megaphone in <Picture 2>, matching <Picture 4>. Voice matches Audio 1.\n"
                "- <Subject 3>: The young woman holding <Subject 2>'s arm in <Picture 2>, matching <Picture 5>.\n"
                "- <Subject 4>: The chef watching smugly in <Picture 2>, matching <Picture 6>.\n"
                "- <Subject 5>: The young woman holding the closed brown ledger on the steps, matching <Picture 7>.\n"
                "- <Subject 6>: The master chef standing beside <Subject 5>, matching <Picture 8>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.4s) Close-up framed from <Picture 1> on <Subject 1> looking across the street.\n"
                "- [Shot 2] (4.4s-10.8s) Medium close-up framed from <Picture 2> on <Subject 2> shouting through the handheld megaphone toward screen-left.\n"
                "- [Shot 3] (10.8s-14.0s) Medium three-shot on the west stone steps showing <Subject 1>, <Subject 5>, and <Subject 6> facing screen-right.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-4.3s): Watching across the street with his lips pressed completely closed and silent, <Subject 1> narrows his eyes coldly.\n"
                "- [Shot 2] (4.6s-10.4s): Raising the megaphone to his mouth, <Subject 2> (S1) shouts clearly and briskly: <d>[Chinese] 喂，半个月后我们塞纳河畔西餐厅开业，对门冷锅冷灶的趁早关张吧。</d> Immediately upon finishing the final syllable, he lowers the megaphone with his mouth closed.\n"
                "- [Shot 3] (10.9s-14.0s): On the stone steps, <Subject 6> clenches his fists in silent anger and <Subject 5> hugs her brown ledger tightly while <Subject 1> stands unmoved with closed lips.\n"
                "[Environment]\n- Sunlit Chongqing bluestone street between the two facing shops.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Quiet street air in [Shot 1], projected megaphone taunt finishing cleanly by 10.4s in [Shot 2], silent tense reaction in [Shot 3], zero music."
            ),
        },
        {
            "id": "3-2-11", "episode": 3, "duration": 13, "seed": 83211, "wait_stems": [],
            "ref_images": [kf("3-2-11"), kf("3-2-12_aux"), f_lin, f_chu, f_jian, f_ye_bare, f_qian],
            "ref_audios": [v_lin, v_jian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young woman on screen-right in <Picture 1>, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 2>: The young man beside <Subject 1> in <Picture 1>, matching <Picture 4>.\n"
                "- <Subject 3> (S2): The master chef on screen-right of the steps in <Picture 2>, matching <Picture 5>. Voice matches Audio 2.\n"
                "- <Subject 4>: The bare-wristed young man wearing the army-green canvas backpack on screen-left in <Picture 2>, matching <Picture 6>.\n"
                "- <Subject 5>: The young woman holding the thick dark-brown hardcover ledger between them in <Picture 2>, matching <Picture 7>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.4s) Close-up framed from <Picture 1> on <Subject 1> jeering toward screen-left.\n"
                "- [Shot 2] (4.4s-9.4s) Medium three-shot framed from <Picture 2>.\n"
                "- [Shot 3] (9.4s-13.0s) Medium close-up on <Subject 4> and <Subject 5> opening the exact same thick dark-brown hardcover ledger.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-4.2s): Tilting her chin high in spiteful pride, <Subject 1> (S1) calls out: <d>[Chinese] 叶寻，瞧见没，离了你，我家照样开高档西餐厅。</d>\n"
                "- [Shot 2] (4.6s-9.2s): As <Subject 4> slips the folded paper into his army-green backpack, <Subject 3> (S2) points angrily right and roars: <d>[Chinese] 欺负人欺负到家门口了，请个洋厨子就不知道姓啥了。</d> He clamps his mouth shut at 9.2s.\n"
                "- [Shot 3] (9.5s-13.0s): Silently raising his left arm gently to hold <Subject 3> back (zero slap or clap sound), <Subject 4> turns smoothly to <Subject 5> and opens the thick dark-brown hardcover ledger in her hands.\n"
                "[Environment]\n- Sunlit Chongqing bluestone street.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Spiteful female taunt, angry older male roar, quiet soft paper page turn in [Shot 3] with zero clapping sound, zero music."
            ),
        },
        {
            "id": "3-2-14", "episode": 3, "duration": 15, "seed": 83214, "wait_stems": [],
            "ref_images": [kf("3-2-14"), kf("3-2-01"), f_ye_bare, f_qian, f_jian],
            "ref_audios": [v_ye, v_qian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The bare-wristed young man wearing the army-green canvas backpack on screen-left in <Picture 1> and <Picture 2>, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The young woman holding the open brown hardcover ledger in <Picture 1> and <Picture 2>, matching <Picture 4>. Voice matches Audio 2.\n"
                "- <Subject 3>: The master chef standing beside <Subject 2> on the steps in <Picture 2>, matching <Picture 5>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.8s) Over-the-shoulder close-up framed from <Picture 1> onto <Subject 1> wearing his army-green canvas backpack.\n"
                "- [Shot 2] (4.8s-10.5s) Reverse close-up onto <Subject 2> reading the brown ledger.\n"
                "- [Shot 3] (10.5s-15.0s) Medium three-shot on the exact plain signless wooden storefront stone steps of <Picture 2> (strictly ZERO overhead signboard or plaque of any kind, keeping <Subject 1>'s army-green canvas backpack on his shoulder).\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-4.6s): Tapping the ledger page calmly, <Subject 1> (S1) asks: <d>[Chinese] 夏叔，犯不着跟他们置气，芊芊姐，账上还能腾出多少现钱。</d>\n"
                "- [Shot 2] (5.0s-10.3s): Looking up earnestly from the ledger, <Subject 2> (S2) answers: <d>[Chinese] 账面一共三万八，刨去欠菜贩子的货款，手里现钱就剩两万六了。</d>\n"
                "- [Shot 3] (10.7s-14.0s): On the signless wooden doorway steps of <Picture 2>, <Subject 2> closes the brown ledger as <Subject 1> (S1) says: <d>[Chinese] 两万六够把前头改成明档了，今儿先从门口动。</d> At 14.1s, heavy iron wheelbarrow wheels rumble from screen-right and all three turn sharply right with closed mouths.\n"
                "[Environment]\n- Plain signless traditional wooden storefront steps (<Picture 2>), zero overhead signboards or text.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Calm male inquiry, clear female reply, decisive male line finishing by 14.0s followed by heavy iron wheels rolling on stone, zero music."
            ),
        },
        {
            "id": "3-2-20", "episode": 3, "duration": 14, "seed": 83220, "wait_stems": [],
            "ref_images": [kf("3-2-20"), kf("3-2-01"), f_zhao, f_jian, f_ye_bare, f_qian],
            "ref_audios": [v_zhao, v_jian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The chef standing beside the gravel mound in <Picture 1> with the red booklet under his left arm, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The master chef on the plain signless wooden doorway steps in <Picture 2>, matching <Picture 4>. Voice matches Audio 2.\n"
                "- <Subject 3>: The bare-wristed young man wearing the army-green canvas backpack on the steps in <Picture 2>, matching <Picture 5>.\n"
                "- <Subject 4>: The young woman hugging the closed brown ledger anxiously to her chest on the steps in <Picture 2>, matching <Picture 6>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-5.6s) Medium close-up framed from <Picture 1> on <Subject 1> facing upper-left.\n"
                "- [Shot 2] (5.6s-10.2s) Medium shot at the plain signless wooden doorway steps of <Picture 2> (strictly ZERO overhead signboard or plaque; <Subject 4> hugs her CLOSED ledger in alarm, <Subject 3> wears his green backpack).\n"
                "- [Shot 3] (10.2s-14.0s) Close-up on <Subject 3> (wearing his green backpack, bare wrists) gripping the wooden shovel shaft firmly and taking it silently from <Subject 2>.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-5.4s): Folding his arms with a shameless sneer, <Subject 1> (S1) jeers: <d>[Chinese] 路窄，借你们台阶堆半个月呗，横竖你们这破店也没人登门。</d>\n"
                "- [Shot 2] (5.8s-9.8s): Simultaneously grabbing the long-handled iron shovel from the left wooden doorpost of <Picture 2>, <Subject 2> (S2) roars immediately: <d>[Chinese] 蹬鼻子上脸是吧，我跟你们拼了。</d> He clamps his jaw shut at 9.8s.\n"
                "- [Shot 3] (10.3s-14.0s): In complete tense silence without any speech, <Subject 3> clamps both bare hands onto the wooden shovel shaft, takes the shovel steadily from <Subject 2>, and steps forward.\n"
                "[Environment]\n- Plain signless wooden storefront steps (<Picture 2>) blocked by dumped sand and gravel, zero signboards or text.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Shameless male jeer in [Shot 1], complete furious older male roar finishing by 9.8s in [Shot 2], firm silent wood grip in [Shot 3], zero music."
            ),
        },
        {
            "id": "3-2-23", "episode": 3, "duration": 14, "seed": 83223, "wait_stems": [],
            "ref_images": [kf("3-2-23"), kf("3-2-24_aux"), f_lin, f_chu, f_ye_bare, f_zhao],
            "ref_audios": [v_zhao],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The young woman laughing across the street in <Picture 1>, matching <Picture 3>.\n"
                "- <Subject 2>: The young man holding a megaphone beside <Subject 1> in <Picture 1>, matching <Picture 4>.\n"
                "- <Subject 3>: The bare-wristed young man wearing the army-green canvas backpack standing high atop the gravel mound gripping the long-handled iron shovel in <Picture 2>, matching <Picture 5>.\n"
                "- <Subject 4> (S1): The chef standing below the gravel mound on screen-right in <Picture 2>, matching <Picture 6>. Voice matches Audio 1.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-1.8s) Brief medium close-up framed from <Picture 1> as <Subject 1> and <Subject 2> smirk mockingly.\n"
                "- [Shot 2] (1.8s-4.0s) Low-angle medium shot framed from <Picture 2> as <Subject 3> steps atop the gravel mound and drives the iron shovel blade into the gravel.\n"
                "- [Shot 3] (4.0s-10.2s) High-angle over-the-shoulder close-up past <Subject 3>'s shovel shaft onto <Subject 4> below on screen-right.\n"
                "- [Shot 4] (10.2s-14.0s) Low-angle tight close-up on <Subject 3> towering silently atop the gravel mound with white-knuckled bare hands gripping the shovel shaft.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-1.7s): <Subject 1> and <Subject 2> exchange a brief gloating chuckle.\n"
                "- [Shot 2] (1.9s-3.9s): <Subject 3> plants his boot atop the gravel crest and drives the shovel blade sharply into the gravel.\n"
                "- [Shot 3] (4.2s-9.8s): Slapping his own chest twice provocatively right as he starts speaking, <Subject 4> (S1) glares up and taunts briskly: <d>[Chinese] 咋的穷学生，还敢抡铁锹啊，来，往这儿拍，动一下赔十万。</d> Immediately upon finishing at 9.8s, he clamps his mouth shut in an arrogant sneer.\n"
                "- [Shot 4] (10.3s-14.0s): In dead silence with closed lips and razor-cold eyes staring down, <Subject 3> tightens both bare hands around the wooden shovel shaft.\n"
                "[Environment]\n- Sunlit Chongqing bluestone street with high gravel mound.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Brief chuckle in [Shot 1], gravel crunch in [Shot 2], chest slaps and complete male taunt finishing cleanly by 9.8s in [Shot 3], pure silent tension and subtle wood creak in [Shot 4], zero music."
            ),
        },
        # ================= WAVE B (Anchor-Rebuilt Shots Streaming from Spark!) =================
        {
            "id": "1-1-07", "episode": 1, "duration": 13, "seed": 81107, "wait_stems": ["1-1_master_4p", "1-1-07"],
            "ref_images": [kf("1-1-07"), kf("1-1_master_4p"), f_ye_2020, f_lin_banq],
            "ref_audios": [v_ye, v_lin],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The man on screen-left in <Picture 1> and <Picture 2> wearing the thin black lanyard and gold square badge, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The woman standing beside the round grey marble table in <Picture 2> holding a black folder, matching <Picture 4>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.4s) Medium close-up framed from <Picture 1> beside the round grey marble table.\n"
                "- [Shot 2] (4.4s-10.8s) Reverse close-up inside <Picture 2> in front of the night skyline window on <Subject 2> facing screen-left.\n"
                "- [Shot 3] (10.8s-13.0s) Tight close-up back on <Subject 1> on screen-left in silent realization.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-4.2s): Gesturing earnestly beside the round marble table, <Subject 1> (S1) argues: <d>[Chinese] 撤了我家的温补底料，外地客哪受得了这重辣。</d>\n"
                "- [Shot 2] (4.6s-10.5s): Pulling a white printed transfer slip from her black folder, <Subject 2> (S2) snaps coldly: <d>[Chinese] 少往自己脸上贴金，没楚南铺路做推广，你现在还在小县城守破灶呢。</d> She presses her lips shut right as she finishes.\n"
                "- [Shot 3] (10.9s-13.0s): <Subject 1> stands frozen with closed lips as his eyes turn ice-cold.\n"
                "[Environment]\n- Upscale rooftop VIP room (<Picture 2>) with round grey marble table and night skyline window.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Earnest male plea, sharp paper pull and biting female rebuke, silent tension, zero music."
            ),
        },
        {
            "id": "1-1-10", "episode": 1, "duration": 13, "seed": 81110, "wait_stems": ["1-1_master_4p", "1-1-10"],
            "ref_images": [kf("1-1-10"), kf("1-1_master_4p"), f_ye_2020, f_lin_banq, f_chu_exec, f_zhao],
            "ref_audios": [v_lin, v_chu],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The man on screen-left wearing the thin black lanyard and gold square badge in <Picture 1> and <Picture 2>, matching <Picture 3>.\n"
                "- <Subject 2> (S1): The woman on screen-right in <Picture 1> and <Picture 2>, matching <Picture 4>. Voice matches Audio 1.\n"
                "- <Subject 3> (S2): The executive man beside <Subject 2> in <Picture 2>, matching <Picture 5>. Voice matches Audio 2.\n"
                "- <Subject 4>: The chef holding the single white gold-trimmed ceremonial cap on far right in <Picture 2>, matching <Picture 6>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-2.3s) Profile medium close-up framed from <Picture 1> beside the round grey marble table.\n"
                "- [Shot 2] (2.3s-8.0s) Medium four-shot framed from <Picture 2> around the round grey marble table (silver tray on table is empty, white transfer slip lies on table edge, <Subject 1> keeps his black lanyard badge).\n"
                "- [Shot 3] (8.0s-13.0s) Close-up two-shot in front of the night skyline window of <Picture 2> favoring <Subject 3> with <Subject 2> holding his arm.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-2.2s): <Subject 2> slaps the white transfer slip against <Subject 1>'s chest and lets it drop onto the round marble table edge.\n"
                "- [Shot 2] (2.5s-7.8s): Linking both hands around <Subject 3>'s left arm beside the round marble table (<Picture 2>), <Subject 2> (S1) says condescendingly: <d>[Chinese] 看在以前的分上，郊区仓库给你留了个位置，去不去随你。</d>\n"
                "- [Shot 3] (8.2s-12.0s): Waving his right hand twice in front of his nose, <Subject 3> (S2) smirks at screen-left and says: <d>[Chinese] 行了叶师傅，腾地方吧，这一身草药味儿怪冲的。</d> He closes his mouth smugly right at 12.0s.\n"
                "[Environment]\n- Upscale rooftop VIP room at night (<Picture 2>) with round grey marble table and skyline window.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Crisp paper slap, condescending female line, mocking male dismissal finishing by 12.0s, zero music."
            ),
        },
        {
            "id": "1-1-13", "episode": 1, "duration": 10, "seed": 81113, "wait_stems": ["1-1-13_aux"],
            "ref_images": [kf("1-1-13"), kf("1-1-13_aux"), f_ye_2020, f_lin_banq, f_chu_exec, f_zhao],
            "ref_audios": [],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The man whose left hand appears in <Picture 1> and who exits in <Picture 2>, matching <Picture 3>.\n"
                "- <Subject 2>: The woman standing behind the round marble table in <Picture 2>, matching <Picture 4>.\n"
                "- <Subject 3>: The executive man beside <Subject 2> in <Picture 2>, matching <Picture 5>.\n"
                "- <Subject 4>: The chef beside <Subject 3> in <Picture 2>, matching <Picture 6>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-2.2s) High-angle close-up framed from <Picture 1> showing <Subject 1>'s left hand clenching beside the cylindrical floor trash bin holding the faded cloth.\n"
                "- [Shot 2] (2.2s-4.8s) Close-up on <Subject 1> in front of the night skyline window ripping off his thin black lanyard with small square gold metal badge (natural clear eyes, no red glow).\n"
                "- [Shot 3] (4.8s-6.8s) Tabletop close-up on the round grey marble table beside the champagne glass and white transfer slip.\n"
                "- [Shot 4] (6.8s-10.0s) Wide interior shot framed directly from <Picture 2> retaining the badge, transfer slip, champagne glass, and floor trash bin as <Subject 1> pushes open the right-rear wooden door and exits.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-2.1s): In complete silence without any breath or grunt, <Subject 1>'s left fingers clench into a tight fist.\n"
                "- [Shot 2] (2.3s-4.7s): With closed lips and cold steady eyes, <Subject 1> grabs the thin black lanyard and gold square badge at his chest and snaps it free.\n"
                "- [Shot 3] (4.9s-6.7s): <Subject 1>'s right hand slams the gold square badge and black cord onto the round marble table beside the white transfer slip.\n"
                "- [Shot 4] (6.9s-10.0s): Leaving <Subject 2>, <Subject 3>, and <Subject 4> standing behind the round table (<Picture 2>), <Subject 1> strides to the right-rear wooden door and exits.\n"
                "[Environment]\n- Luxury rooftop banquet room (<Picture 2>).\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Purely foley sounds only (cord snap, metallic badge slam on marble, footsteps, wooden door open) with strictly zero human voice, zero grunt, and zero music."
            ),
        },
        {
            "id": "1-3-21", "episode": 1, "duration": 15, "seed": 81321, "wait_stems": ["1-3-21", "2-1-01"],
            "vo_reuse": {"vocals": TAKES[1] / "1-3-21" / "vo_short_vocals.wav", "ss": 0.28, "se": 4.94, "ratio": 1.18, "dst_start": 2.55},
            "ref_images": [kf("1-3-21"), kf("2-1-01"), f_ye_orig, f_lin],
            "ref_audios": [v_ye, v_lin],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young man standing alone at the open wooden doorway threshold in <Picture 1> and on the lower flat stone step on screen-left in <Picture 2> wearing the zipper-top army-green canvas backpack on his right shoulder and small black digital watch on his left wrist, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The young woman rushing out onto the upper stone step on screen-right in <Picture 2>, matching <Picture 4>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-2.4s) Medium close-up framed from <Picture 1> on <Subject 1> alone at the sunlit doorway threshold.\n"
                "- [Shot 2] (2.4s-6.6s) Close-up tracking <Subject 1>'s resolute face with closed silent lips as he steps down onto the flat stone step outside.\n"
                "- [Shot 3] (6.6s-8.2s) Medium two-shot framed directly into the exact doorway steps blocking of <Picture 2> (open wooden doors on screen-left, zero outdoor brick stove) as <Subject 2> dashes onto the upper step on screen-right and grabs <Subject 1>'s green backpack strap.\n"
                "- [Shot 4] (8.2s-15.0s) Holding the exact medium two-shot of <Picture 2> on the two flat stone steps.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-2.3s): Half-glancing coolly over his shoulder, <Subject 1> (S1) says crisply: <d>[Chinese] 找你的星级主厨去。</d>\n"
                "- [Shot 2] (2.5s-6.5s): Stepping forward onto the sunlit stone step, <Subject 1> grips his right green backpack strap with sharp eyes and keeps his lips completely closed and silent.\n"
                "- [Shot 3] (6.7s-8.1s): <Subject 2> rushes out onto the upper stone step on screen-right (<Picture 2>) and grabs <Subject 1>'s right-shoulder green backpack strap tightly with her right hand, halting him.\n"
                "- [Shot 4] (8.3s-13.4s): Immediately upon grabbing the strap without any pause, <Subject 2> (S2) glares at <Subject 1> and shouts briskly and furiously: <d>[Chinese] 叶寻你给我站住，话没说清楚往哪儿走，谁准你反悔的。</d> Immediately upon finishing at 13.4s, she clamps her lips shut glaring while both hold the exact frozen standoff of <Picture 2> until 15.0s.\n"
                "[Environment]\n- Open weathered wooden shop doorway and two flat stone steps in midday sunlight (<Picture 2>), zero outdoor brick stove, zero text signboards.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Crisp male retort in [Shot 1], footsteps in [Shot 2], urgent steps and strap grab in [Shot 3], complete furious female shout finishing cleanly by 13.4s followed by 1.5s silent standoff, zero music."
            ),
        },
        {
            "id": "2-1-01", "episode": 2, "duration": 13, "seed": 82101, "wait_stems": ["2-1-01"],
            "ref_images": [kf("2-1-01"), f_ye_orig, f_lin, f_chu],
            "ref_audios": [v_lin, v_chu],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The young man on the lower stone step on screen-left in <Picture 1> with the zipper-top army-green backpack and black digital watch on his left wrist, matching <Picture 2>.\n"
                "- <Subject 2> (S1): The young woman on the upper stone step on screen-right in <Picture 1> gripping <Subject 1>'s shoulder-height green backpack strap with her right hand, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 3> (S2): The young man leaning against the wooden doorframe, matching <Picture 4>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-1.9s) Medium two-shot framed from <Picture 1> outside the open wooden doorway (zero outdoor brick stove).\n"
                "- [Shot 2] (1.9s-7.4s) Over-the-shoulder close-up past <Subject 1>'s shoulder onto <Subject 2> on screen-right keeping her right hand gripping the taut shoulder-height green backpack strap (never dropping down to grab his wrist).\n"
                "- [Shot 3] (7.4s-13.0s) Medium close-up from the same camera side showing <Subject 3> leaning against the wooden doorframe with open shop interior on screen-left and stone lane on screen-right.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-1.8s): Gripping the taut green shoulder strap, <Subject 2> curls her lips into a smug sneer while <Subject 1> stays silent.\n"
                "- [Shot 2] (2.0s-7.2s): Tugging the shoulder-height green backpack strap smugly, <Subject 2> (S1) jeers: <d>[Chinese] 行啊叶寻，跟我玩这一套，看楚南帮我出主意，吃醋了。</d>\n"
                "- [Shot 3] (7.6s-12.1s): Leaning with folded arms against the doorframe, <Subject 3> (S2) chuckles mockingly toward screen-left: <d>[Chinese] 至于吗老叶，大老爷们儿搞欲擒故纵，掉价了啊。</d> He closes his mouth with a smirk at 12.1s.\n"
                "[Environment]\n- Open wooden shop doorway and two flat stone steps in midday sun (<Picture 1>), zero text signboards.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Strap tug, smug female jeer, mocking male chuckle finishing by 12.1s, zero music."
            ),
        },
        {
            "id": "2-1-04", "episode": 2, "duration": 15, "seed": 82104, "wait_stems": ["2-1-04", "2-1_post_watch_master"],
            "ref_images": [kf("2-1-04"), kf("2-1_post_watch_master"), f_lin, f_ye_bare],
            "ref_audios": [v_lin, v_ye],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young woman standing on the upper stone step on screen-right in <Picture 1> and <Picture 2> (wearing only her thin gold chain on her left wrist, zero black watch on her wrist), matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The young man on screen-left wearing the army-green canvas backpack with bare wrists in <Picture 2>, matching <Picture 4>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.8s) Medium close-up framed from <Picture 1> in front of the WIDE-OPEN wooden doorway as <Subject 1> extends her open left palm toward screen-left.\n"
                "- [Shot 2] (4.8s-7.0s) Tight close-up on <Subject 2>'s left wrist as his right hand unclasps and pulls the small black plastic digital watch completely OFF his bare left wrist.\n"
                "- [Shot 3] (7.0s-10.6s) Medium two-shot on the open wooden doorway steps matching <Picture 2>: <Subject 2> (BOTH wrists now completely bare without any watch!) places that single black plastic watch with his right hand into <Subject 1>'s open left palm.\n"
                "- [Shot 4] (10.6s-15.0s) Over-the-shoulder close-up past <Subject 2>'s green-strapped shoulder onto <Subject 1> staring at the single black watch in her left palm.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-4.6s): Extending her open left palm toward screen-left, <Subject 1> (S1) orders haughtily: <d>[Chinese] 差不多行了，服个软把方子交出来，刚才的事我翻篇。</d>\n"
                "- [Shot 2] (4.9s-6.9s): <Subject 2> unsnaps the black plastic watch and pulls it completely off, leaving his left wrist bare.\n"
                "- [Shot 3] (7.2s-10.4s): With bare wrists, <Subject 2> (S2) slaps the single plastic watch firmly into <Subject 1>'s open left palm and states flatly: <d>[Chinese] 东西收好，咱俩完了。</d>\n"
                "- [Shot 4] (10.8s-13.9s): Glancing at the single watch in her palm and snapping stunned eyes up at <Subject 2>, <Subject 1> (S1) gasps: <d>[Chinese] 你说什么，叶寻，你敢提分手。</d> She freezes in shock at 13.9s.\n"
                "[Environment]\n- Wide-open weathered wooden doorway and two flat stone steps (<Picture 2>), zero text.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Haughty female command, watch buckle click, slap into palm, icy male breakup line, shocked female gasp finishing by 13.9s, zero music."
            ),
        },
        {
            "id": "2-1-08", "episode": 2, "duration": 14, "seed": 82108, "wait_stems": ["2-1_post_watch_master", "2-1-08"],
            "ref_images": [kf("2-1-08"), kf("2-1_post_watch_master"), f_ye_bare, f_lin, f_chu],
            "ref_audios": [v_ye],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The bare-wristed young man on screen-left wearing the army-green canvas backpack in <Picture 1> and <Picture 2>, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 2>: The young woman in center-right of <Picture 2> holding the single black watch in her left hand at her chest while her right hand still grips <Subject 1>'s green backpack strap (zero black watch on her wrists), matching <Picture 4>.\n"
                "- <Subject 3>: The young man leaning at the right wooden doorframe in <Picture 2>, matching <Picture 5>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.5s) Close-up framed from <Picture 1> on <Subject 1> facing screen-right.\n"
                "- [Shot 2] (4.5s-6.6s) Reverse close-up inside <Picture 2> on <Subject 2> stunned and silent, left hand holding the single black watch at her chest (no black watch on her wrist) and right hand still gripping the green strap.\n"
                "- [Shot 3] (6.6s-14.0s) Medium three-shot framed directly from <Picture 2> (<Subject 1> bare wrists on left, <Subject 2> center-right keeping her right hand on <Subject 1>'s green strap, <Subject 3> at right doorframe).\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-4.3s): <Subject 1> (S1) declares coldly: <d>[Chinese] 分了，往后你家店是死是活，别来沾边。</d>\n"
                "- [Shot 2] (4.6s-6.5s): <Subject 2> stands speechless with closed lips holding the single watch at her chest.\n"
                "- [Shot 3] (6.8s-12.4s): Looking past <Subject 2> directly at <Subject 3>, <Subject 1> (S1) says evenly: <d>[Chinese] 楚少，刚吹出去的星级主厨，赶紧给人请来啊。</d> He closes his mouth calmly at 12.4s.\n"
                "[Environment]\n- Open wooden doorway and two flat stone steps (<Picture 2>), zero text.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Decisive male voice, quiet street cicadas, cool male challenge finishing cleanly by 12.4s, zero music."
            ),
        },
        {
            "id": "2-1-11", "episode": 2, "duration": 14, "seed": 82111, "wait_stems": ["2-1_post_watch_master", "2-1-11"],
            "ref_images": [kf("2-1-11"), kf("2-1_post_watch_master"), f_lin, f_chu, f_ye_bare],
            "ref_audios": [v_lin, v_chu],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young woman in <Picture 1> and <Picture 2> holding the single black watch in her left hand at her chest while her right hand keeps holding <Subject 3>'s green backpack strap (zero black watch on her wrists), matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The young man at the right wooden doorframe in <Picture 1> and <Picture 2>, matching <Picture 4>. Voice matches Audio 2.\n"
                "- <Subject 3>: The bare-wristed young man on the lower step on screen-left in <Picture 2>, matching <Picture 5>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.3s) Close-up framed from <Picture 1> on <Subject 1> turning her head over her right shoulder.\n"
                "- [Shot 2] (4.3s-11.2s) Same-axis over-the-shoulder close-up with <Subject 1>'s blurred shoulder on the LEFT foreground and <Subject 2> on SCREEN-RIGHT by the wooden doorframe facing screen-left.\n"
                "- [Shot 3] (11.2s-14.0s) Medium three-shot framed directly from <Picture 2> where <Subject 1>'s right hand STILL holds <Subject 3>'s green backpack strap without letting go.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-4.1s): Turning urgently toward right-rear, <Subject 1> (S1) asks: <d>[Chinese] 楚南，你刚说的那个主厨，到底准不准。</d>\n"
                "- [Shot 2] (4.5s-10.9s): Patting his own chest twice right at 5.2s as he speaks, <Subject 2> (S2) boasts loudly toward screen-left: <d>[Chinese] 什么准不准，就明天，我把星级主厨赵帆连装修队一块儿给你拉来。</d> He closes his mouth smugly at 10.9s.\n"
                "- [Shot 3] (11.3s-14.0s): Keeping her right hand gripping <Subject 3>'s green strap as in <Picture 2>, <Subject 1> exhales in silent relief while <Subject 3> grips the upper part of his own strap with his bare right hand and smirks coldly.\n"
                "[Environment]\n- Open wooden doorway and two flat stone steps (<Picture 2>), zero text.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Urgent female question, two chest slaps during boastful male pledge finishing by 10.9s, quiet tension in [Shot 3], zero music."
            ),
        },
        {
            "id": "2-1-14", "episode": 2, "duration": 13, "seed": 82114, "wait_stems": ["2-1_post_watch_master", "2-1-14", "2-1-14_street_aux"],
            "ref_images": [kf("2-1-14"), kf("2-1_post_watch_master"), kf("2-1-14_street_aux"), f_ye_bare, f_lin, f_chu],
            "ref_audios": [v_ye, v_lin],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The bare-wristed young man on screen-left in <Picture 1>, <Picture 2>, and <Picture 3> wearing the army-green canvas backpack slung on his right shoulder, matching <Picture 4>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The young woman in center-right in <Picture 1> and <Picture 2> (no black watch on her wrists), matching <Picture 5>. Voice matches Audio 2.\n"
                "- <Subject 3>: The young man behind <Subject 2> in <Picture 1>, matching <Picture 6>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-3.9s) Medium shot framed from <Picture 1> on the two flat stone steps.\n"
                "- [Shot 2] (3.9s-9.6s) Close-up on <Subject 2> with <Subject 3> behind her on the stone steps.\n"
                "- [Shot 3] (9.6s-13.0s) Wide street shot framed directly from <Picture 3> following <Subject 1> (bare wrists, green backpack slung over his right shoulder) striding across the clean bluestone lane.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-2.1s): Looking flatly at <Subject 2>, <Subject 1> (S1) says: <d>[Chinese] 行，祝你们发财。</d>\n"
                "- [Shot 1] (2.1s-3.8s): <Subject 1> yanks his green backpack strap cleanly free from <Subject 2>'s right hand with his bare right hand and turns away.\n"
                "- [Shot 2] (4.1s-9.3s): Clenching her empty right hand in rage, <Subject 2> (S2) shouts spitefully: <d>[Chinese] 滚就滚，离了我家这门面，你那破方子烂手里都没人要。</d> She clamps her jaw shut at 9.3s.\n"
                "- [Shot 3] (9.7s-13.0s): With bare wrists and the green backpack on his right shoulder (<Picture 3>), <Subject 1> strides resolutely across the sunlit bluestone road without looking back.\n"
                "[Environment]\n- Sunlit 2005 bluestone pedestrian lane (<Picture 2>, <Picture 3>), zero outdoor tables, zero text.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Cool male farewell, sharp strap yank, spiteful female shout finishing by 9.3s, steady footsteps on stone in [Shot 3], zero music."
            ),
        },
        {
            "id": "2-3-05", "episode": 2, "duration": 15, "seed": 82305, "wait_stems": ["2-3-08", "2-3-05_qian_aux"],
            "ref_images": [kf("2-3-05"), kf("2-3-08"), kf("2-3-05_qian_aux"), f_ye_bare, f_qian],
            "ref_audios": [v_ye, v_qian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The bare-wristed young man standing outside the dark wooden counter in <Picture 1> and <Picture 2>, matching <Picture 4>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The young woman standing behind the dark wooden counter in <Picture 3>, matching <Picture 5>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-2.5s) Medium close-up framed from <Picture 1> as <Subject 1> (bare wrists, closed silent lips) unzips the army-green backpack and lifts out one twine-tied coarse burlap herb bundle.\n"
                "- [Shot 2] (2.5s-8.0s) Close-up framed from <Picture 2> as <Subject 1> presses his bare right palm atop the coarse burlap herb bundle on the wooden counter.\n"
                "- [Shot 3] (8.0s-15.0s) Reverse medium close-up framed directly from <Picture 3> onto <Subject 2> behind the wooden counter in front of authentic 2005 white plaster walls, wooden tables, and dark-blue cloth curtain (strictly ZERO modern glowing glass beverage fridge).\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-2.4s): In complete vocal silence (zero grunts or breaths), <Subject 1> unzips the canvas backpack and sets the single twine-tied burlap herb bundle onto the wooden counter.\n"
                "- [Shot 2] (2.7s-7.8s): Pressing his bare hand steadily on the herb bundle, <Subject 1> (S1) proposes clearly: <d>[Chinese] 店别关，炒菜改做养生火锅，我出方子盯灶，咱们合伙。</d>\n"
                "- [Shot 3] (8.2s-13.6s): Raising her left hand in surprised protest inside <Picture 3>, <Subject 2> (S2) exclaims clearly: <d>[Chinese] 这哪行啊，你爷爷留的方子，不是说好拿去帮双双吗。</d> Right upon finishing the final word at 13.6s, she keeps her lips gently parted in silent surprise.\n"
                "[Environment]\n- Traditional 2005 small restaurant front hall (<Picture 3>) with plaster walls and blue cloth curtain, zero modern refrigerators.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Clean zipper pull and bundle thud in [Shot 1] with zero human vocalization, steady male proposal in [Shot 2], complete surprised female protest finishing cleanly by 13.6s in [Shot 3], zero music."
            ),
        },
        {
            "id": "2-3-08", "episode": 2, "duration": 14, "seed": 82308, "wait_stems": ["2-3-08"],
            "ref_images": [kf("2-3-08"), kf("2-3-10_aux"), f_ye_bare, f_qian, f_jian],
            "ref_audios": [v_ye, v_jian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The bare-wristed young man at the wooden counter in <Picture 1>, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 2>: The young woman at the counter on screen-right, matching <Picture 4>.\n"
                "- <Subject 3> (S2): The master chef standing before the dark-blue cloth curtain in <Picture 2>, matching <Picture 5>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.0s) Over-the-shoulder close-up framed from <Picture 1> onto <Subject 1> (bare wrists) tapping the herb bundle.\n"
                "- [Shot 2] (4.0s-6.8s) Medium shot toward the rear dark-blue cloth kitchen curtain as <Subject 3> flings the blue curtain wide open and steps out holding the iron wok ladle.\n"
                "- [Shot 3] (6.8s-14.0s) Medium close-up framed from <Picture 2> on <Subject 3> clutching his sore throat.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-3.8s): Tapping the burlap herb bundle with his bare hand, <Subject 1> (S1) says firmly: <d>[Chinese] 刚跟她分了，这东西，我只信得过夏家。</d>\n"
                "- [Shot 2] (4.1s-6.7s): At 4.3s the dark-blue cloth curtain is flung sharply aside and <Subject 3> strides out clutching his neck with his left hand and holding the iron ladle in his right.\n"
                "- [Shot 3] (7.0s-12.4s): Pointing the iron ladle slightly forward, <Subject 3> (S2) barks in a raspy voice: <d>[Chinese] 瞎胡闹，夏家做了一辈子川菜，改什么野路子。</d> Immediately upon finishing at 12.4s, he clamps his mouth shut glaring.\n"
                "[Environment]\n- Traditional 2005 eatery front hall.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Sincere male line, cloth curtain whipped open and footsteps, complete raspy older male rebuke finishing cleanly by 12.4s, zero music."
            ),
        },
        {
            "id": "2-3-11", "episode": 2, "duration": 14, "seed": 82311, "wait_stems": ["2-3-13_aux", "2-3-11"],
            "ref_images": [kf("2-3-11"), kf("2-3-13_aux"), f_qian, f_ye_bare, f_jian],
            "ref_audios": [v_qian, v_jian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young woman stepping half a pace forward past the right-side wooden counter in <Picture 1> and <Picture 2>, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 2>: The bare-wristed young man standing beside the right-side wooden counter in <Picture 1> and <Picture 2> keeping his bare right hand on the herb bundle and his green backpack on his left arm, matching <Picture 4>.\n"
                "- <Subject 3> (S2): The master chef standing on screen-left before the dark-blue curtain in <Picture 2>, matching <Picture 5>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.8s) Medium close-up two-shot framed from <Picture 1> with the wooden counter strictly on screen-right, facing screen-left.\n"
                "- [Shot 2] (4.8s-11.4s) Close-up on <Subject 3> on screen-left facing screen-right.\n"
                "- [Shot 3] (11.4s-14.0s) Three-layer depth medium shot framed directly from <Picture 2> (<Subject 2>'s bare hand on the herb bundle on lower-right counter, <Subject 3> at left-rear).\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-4.6s): Looking worriedly toward screen-left, <Subject 1> (S1) pleads: <d>[Chinese] 爸，你扁桃体肿得水都咽不下，快少说两句。</d>\n"
                "- [Shot 2] (5.0s-11.1s): Looking straight toward screen-right at <Subject 2>, <Subject 3> (S2) speaks hoarsely: <d>[Chinese] 小寻，心意叔领了，但那号上火烂嘴的红油锅，绝不能进咱家门。</d> He clamps his lips shut firmly at 11.1s.\n"
                "- [Shot 3] (11.5s-14.0s): Matching <Picture 2>, <Subject 2> rests his bare hand calmly on the herb bundle on the right-side counter in silent deadlock with <Subject 3>.\n"
                "[Environment]\n- Sunlit traditional eatery front hall (<Picture 2>) with clean wooden counter on screen-right.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Worried female plea, hoarse older male decree finishing by 11.1s, silent room tone in [Shot 3], zero music."
            ),
        },
        {
            "id": "3-1-01", "episode": 3, "duration": 13, "seed": 83101, "wait_stems": ["2-3-13_aux", "3-1-01"],
            "ref_images": [kf("3-1-01"), kf("2-3-13_aux"), f_jian, f_qian, f_ye_bare],
            "ref_audios": [v_ye, v_jian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S2): The master chef coughing on SCREEN-LEFT beside the square wooden table in <Picture 1>, matching <Picture 3>. Voice matches Audio 2.\n"
                "- <Subject 2>: The young woman helping <Subject 1> sit down on SCREEN-LEFT in <Picture 1>, matching <Picture 4>.\n"
                "- <Subject 3> (S1): The bare-wristed young man standing beside the dark wooden counter on SCREEN-RIGHT in <Picture 1> and <Picture 2> with his green backpack, matching <Picture 5>. Voice matches Audio 1.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-2.8s) Medium wide shot framed from <Picture 1> (wooden counter and <Subject 3> on SCREEN-RIGHT, wooden tables and <Subject 1>/<Subject 2> on SCREEN-LEFT, strictly ZERO modern silver refrigerator) as <Subject 2> helps <Subject 1> sit on the bench.\n"
                "- [Shot 2] (2.8s-7.0s) Medium two-shot from the front keeping <Subject 3> clearly in frame on screen-right speaking toward seated <Subject 1> on screen-left as <Subject 2> hands <Subject 1> a white porcelain cup of warm water.\n"
                "- [Shot 3] (7.0s-13.0s) Close-up on <Subject 1> seated on screen-left holding the white cup and looking toward screen-right.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-2.7s): Coughing raspingly, <Subject 1> is guided by <Subject 2> onto the bench at the left wooden table.\n"
                "- [Shot 2] (3.0s-6.8s): Leaning slightly forward from the right-side wooden counter, <Subject 3> (S1) asks calmly: <d>[Chinese] 夏叔，急火攻心，嗓子眼疼得像吞刀片吧。</d>\n"
                "- [Shot 3] (7.2s-12.0s): Holding the warm white cup and wincing, <Subject 1> (S2) replies raspingly toward screen-right: <d>[Chinese] 可不是，再闻见那股燥辣红油味儿，我这嗓子彻底交代了。</d> He closes his mouth painedly at 12.0s.\n"
                "[Environment]\n- Traditional 2005 eatery front hall (<Picture 1>), wooden counter on screen-right, zero modern refrigerator.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Dry cough, bench scrape, concerned male question, complete raspy older male reply finishing by 12.0s, zero music."
            ),
        },
    ]

    # Merge updated specs into ep01..03_v7_plan.json so plan files match 100%!
    plans = {
        ep_no: json.loads((WORK_DIR / f"ep0{ep_no}_v7_plan.json").read_text(encoding="utf-8"))
        for ep_no in (1, 2, 3)
    }
    spec_by_id = {s["id"]: s for s in repair_specs}
    for ep_no, plist in plans.items():
        for item in plist:
            if item["id"] in spec_by_id:
                upd = spec_by_id[item["id"]]
                item["duration"] = upd["duration"]
                item["seed"] = upd["seed"]
                item["ref_images"] = upd["ref_images"]
                item["ref_audios"] = upd["ref_audios"]
                item["prompt"] = upd["prompt"]
        (WORK_DIR / f"ep0{ep_no}_v7_plan.json").write_text(json.dumps(plist, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Universal zero-appearance lint check BEFORE running 5090!
    lint_errs = []
    for ep_no, plist in plans.items():
        for s in plist:
            lint_errs.extend(pika_runner.lint_zero_appearance(s["prompt"], s["id"]))
    if lint_errs:
        raise RuntimeError("Zero-appearance lint failed:\n" + "\n".join(lint_errs))
    print("[LINT] Universal Zero-Appearance Lint PASSED (0 issues across all 42 shots)!", flush=True)

    # --- LANE 2: Stream 5090 Video Executions + Inline Silero-VAD Gate ---
    for idx, upd in enumerate(repair_specs, start=1):
        sid = upd["id"]
        ep_no = upd["episode"]
        for st in upd["wait_stems"]:
            if not ready_events[st].is_set():
                print(f"[5090] Waiting on Spark anchor {st} for {sid} ...", flush=True)
                ready_events[st].wait()
        if spark_error:
            raise spark_error[0]

        tdir = TAKES[ep_no]
        sdir = tdir / sid
        sdir.mkdir(parents=True, exist_ok=True)
        final_mp4 = sdir / "video.mp4"

        for attempt in range(2):
            cur_seed = int(upd["seed"]) + attempt * 101
            cur_dur = min(15, int(upd["duration"]) + attempt)
            run_spec = dict(upd, seed=cur_seed, duration=cur_dur)
            print(f"[5090 {idx}/{len(repair_specs)}] Generating {sid} (ep{ep_no}, {cur_dur}s, seed={cur_seed}, attempt={attempt+1}) ...", flush=True)

            if "vo_reuse" in upd:
                vr = upd["vo_reuse"]
                base_mp4 = sdir / "video_base.mp4"
                refs_1k = [pika_runner.ensure_1k_image(Path(p), CACHE_1K) for p in run_spec["ref_images"]]
                audios = [Path(p) for p in run_spec.get("ref_audios", [])]
                meta = pika_runner.call_pika_5090(
                    base_mp4, run_spec["prompt"], cur_dur, cur_seed, "9:16", "480p", refs_1k, audios
                )
                vo_info = run_vo_mux(base_mp4, Path(vr["vocals"]), final_mp4, vr["ss"], vr["se"], vr["ratio"], vr["dst_start"])
                meta["vo_custom_applied"] = vo_info
                (sdir / "video.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            else:
                pika_runner.run_shot(run_spec, tdir, CACHE_1K, resolution="480p", force=True)

            make_half_sec_strip(final_mp4, sid, DIAG_DIR / f"{sid}_0.5s.jpg")

            # Inline Silero-VAD check!
            plan_entry = next(x for x in plans[ep_no] if x["id"] == sid)
            vad_res = vad_gate.audit_shot_audio(vad_sess, final_mp4, plan_entry)
            trunc = [iss for iss in vad_res["issues"] if iss["type"] == "SPEECH_TRUNCATED"]
            if trunc and attempt == 0:
                print(f"[VAD-RETRY] {sid} hit SPEECH_TRUNCATED ({trunc}) -> retrying once with seed={cur_seed+101}, dur={min(15, cur_dur+1)}s!", flush=True)
                continue
            print(f"[VAD-CHECK] {sid} -> status={vad_res['status']} issues={vad_res['issues']}", flush=True)
            break

    spark_thread.join()

    # Run full-episode Silero-VAD post-repair summary across ALL 42 shots!
    for ep_no in (1, 2, 3):
        out_vad = []
        for sp in plans[ep_no]:
            out_vad.append(vad_gate.audit_shot_audio(vad_sess, TAKES[ep_no] / sp["id"] / "video.mp4", sp))
        (AUDIT_DIR / f"vad_audit_ep0{ep_no}_after.json").write_text(json.dumps(out_vad, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        fails = sum(1 for x in out_vad if x["status"] != "PASS")
        print(f"[FINAL VAD EP{ep_no}] {len(out_vad)-fails}/{len(out_vad)} PASS, {fails} FAIL", flush=True)

    # Render v3 transition grids across all 3 episodes
    for ep_no in (1, 2, 3):
        vids = [(sp["id"], TAKES[ep_no] / sp["id"] / "video.mp4") for sp in plans[ep_no]]
        check_transitions.build_transition_sheet(vids, AUDIT_DIR / f"ep0{ep_no}_transitions_4col_v3.jpg")

    print("PHASE 3 UNIFIED CONTINUITY REPAIR COMPLETE!", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
