#!/home/zhongwenyu/data/anaconda3/bin/python
"""
Phase 3B Final Polish Pass driven by Round-2 `gemini-4-hydrogen-high` Script-Supervisor verdicts
(`supervisor_ep01_round2.json`, `supervisor_ep02_round2.json`, `supervisor_ep03_round2.json`):
  - Instant lossless audio swap on `3-1-08` (clean sizzling stove foley, zero piano BGM)
  - 6 targeted Spark `MiniMax H3 Image` anchors (`1-1-13_face_aux`, `2-1_post_watch_master`, `2-2-01`,
    `2-3-05`, `2-3-08`, `3-2-20_steps_aux`) running concurrently with 13 final 5090 video shots:
      Ep 1: `1-1-04`, `1-1-13`, `1-3-01`
      Ep 2: `2-1-04`, `2-1-08`, `2-2-01`, `2-3-05`, `2-3-08`
      Ep 3: `3-1-01`, `3-2-08`, `3-2-11`, `3-2-14`, `3-2-20`
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
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
from phase3_repair_ep01_03 import run_vo_mux  # noqa: E402
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


def fix_3_1_08_pure_kitchen_foley() -> None:
    """Replace 3-1-08's piano-contaminated audio with pure simmering broth & stove foley (-c:v copy)."""
    mp4 = TAKES[3] / "3-1-08" / "video.mp4"
    donor = TAKES[3] / "3-1-11" / "video.mp4"  # 7.3s-11.5s of 3-1-11 is pure simmering soup & kitchen stove foley!
    dur = check_transitions.probe_duration(mp4)
    tmp = mp4.with_suffix(".foley.mp4")
    filt = (
        f"[1:a]aresample=48000,atrim=7.35:11.45,asetpts=PTS-STARTPTS,aloop=loop=2:size=196800,"
        f"atrim=0:{dur:.3f},afade=t=in:d=0.15,afade=t=out:st={max(0.0, dur - 0.25):.3f}:d=0.25,volume=1.15[a]"
    )
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-y", "-i", str(mp4), "-i", str(donor),
            "-filter_complex", filt, "-map", "0:v", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(tmp),
        ],
        check=True,
    )
    tmp.replace(mp4)
    print("[PATCH_AUDIO_ONLY] Replaced 3-1-08 audio with pure simmering stove foley (-c:v copy, zero BGM)", flush=True)


def main() -> int:
    amap = json.loads((WORK_DIR / "asset_map.json").read_text(encoding="utf-8"))
    vad_sess = ort.InferenceSession(str(vad_gate.DEFAULT_VAD_ONNX))

    # 0. Instant lossless audio fix for 3-1-08
    fix_3_1_08_pure_kitchen_foley()

    v_ye = amap["叶寻"]["voice"]
    v_lin = amap["林双双"]["voice"]
    v_chu = amap["楚南"]["voice"]
    v_zhao = amap["赵帆"]["voice"]
    v_qian = amap["夏芊芊"]["voice"]
    v_jian = amap["夏建国"]["voice"]
    v_thug = amap["混混"]["voice"]

    f_ye_2020 = amap["叶寻 · 2020研发总厨白服"]["front_1k"]
    f_lin_banq = amap["林双双 · 塞纳左岸酒红礼服"]["front_1k"]
    f_chu_exec = amap["楚南 · 海归并购总监西装"]["front_1k"]
    f_ye_orig = amap["叶寻"]["front_1k"]
    f_ye_bare = str(ASSETS_1K / "ye_bare_wrist_front_1k.png")
    f_lin = amap["林双双"]["front_1k"]
    f_chu = amap["楚南"]["front_1k"]
    f_zhao = amap["赵帆"]["front_1k"]
    f_qian = amap["夏芊芊"]["front_1k"]
    f_jian = amap["夏建国"]["front_1k"]
    f_thug = amap["混混"]["front_1k"]
    sc_xia_hall = amap["夏氏小厨前厅与传菜口"]["main_1k"]

    # 1. 6 targeted Spark anchor plates
    spark_jobs = [
        {
            "stem": "1-1-13_face_aux",
            "seed": 9513,
            "refs": [str(KF_2K / "1-1_master_4p_2k.png"), f_ye_2020],
            "prompt": (
                "The luxury rooftop VIP dining room with night floor-to-ceiling city skyline window in <Picture 1> is <Subject 1>. "
                "The chef in white double-breasted jacket in <Picture 2> is <Subject 2>. "
                "The target image shows a tight chest-up front close-up of <Subject 2> standing inside <Subject 1>; "
                "<Subject 1> is partially preserved in warm ceiling lights and night city bokeh; "
                "<Subject 2> is fully preserved with completely natural human dark-brown irises and clean normal white sclera (strictly ZERO red eyes or glowing eyes!), "
                "wearing a thin matte-black fabric neck lanyard with a small square gold metal badge, his right hand gripping the gold badge at his chest ready to pull it off. "
                "Crisp 35mm cinema photography, natural eye color, zero text."
            ),
        },
        {
            "stem": "2-1_post_watch_master",
            "seed": 9507,
            "refs": [str(KF_2K / "2-1-01_2k.png"), f_ye_bare, f_lin, f_chu],
            "prompt": (
                "The wide-open weathered wooden shop doorway, two flat grey stone steps, and sunlit bluestone lane in <Picture 1> are <Subject 1>. "
                "The bare-wristed young man in <Picture 2> is <Subject 2>. The young woman in <Picture 3> is <Subject 3>. The young man in dark blazer in <Picture 4> is <Subject 4>. "
                "The target image shows a medium 3-person confrontation on the two flat stone steps of <Subject 1>; "
                "<Subject 1> is partially preserved; <Subject 2>, <Subject 3>, and <Subject 4> are fully preserved. "
                "On screen-left on the lower step, <Subject 2> wears his army-green canvas backpack over his right shoulder with BOTH his left and right wrists completely bare skin (zero wristwatch); "
                "in center-right on the upper step, <Subject 3> also has BOTH her left and right wrists completely bare skin (strictly ZERO wristwatch or bracelet worn on either of her wrists!), "
                "holding the ONLY single small black plastic wristwatch inside her left palm at her chest while her right hand grips <Subject 2>'s green backpack strap; "
                "at the right doorframe, <Subject 4> leans watching. Crisp 35mm cinema photography, only one wristwatch in the entire image, zero text."
            ),
        },
        {
            "stem": "2-2-01",
            "seed": 9521,
            "refs": [str(KF_2K / "2-2-01_2k.png"), f_qian, f_thug],
            "prompt": (
                "The quiet sunlit 2005 Chongqing traditional wooden shopfront with clean empty wooden pillars and two grey stone steps in <Picture 1> is <Subject 1>. "
                "The young woman in grey t-shirt and black apron in <Picture 2> is <Subject 2>. The street punk in red-and-white sporty jacket in <Picture 3> is <Subject 3>. "
                "The target image shows the exact east-side medium-wide view of <Subject 1> right AFTER <Subject 2> has already peeled the old notice off the wooden pillar: "
                "the wooden door pillar beside <Subject 2> is now completely bare wood (zero paper left stuck on the pillar), and <Subject 2> stands flat on the upper stone step clutching the crumpled white paper notice firmly inside her lowered RIGHT hand at her hip; "
                "on screen-left stepping onto the lower stone step, <Subject 3> holds a stack of colorful loan flyers in his left hand with a sleazy grin. "
                "Crisp 35mm cinema photography, zero text signboards."
            ),
        },
        {
            "stem": "2-3-05",
            "seed": 9535,
            "refs": [sc_xia_hall, f_ye_bare],
            "prompt": (
                "The clean sunlit 2005 traditional restaurant front hall with dark-brown wooden counter on lower-right foreground (with ONE closed brown hardcover ledger resting on the counter corner), wooden dining tables on left, and white plaster walls in <Picture 1> is <Subject 1>. "
                "The bare-wristed young man in <Picture 2> is <Subject 2>. "
                "The target image shows a medium close-up of <Subject 2> standing outside the dark wooden counter inside <Subject 1>; "
                "<Subject 1> is partially preserved; <Subject 2> is fully preserved with BOTH his left and right wrists completely bare skin (strictly ZERO wristwatch or strap on either wrist!), "
                "holding his faded army-green canvas backpack on his left forearm while his bare right hand pulls open the top metal zipper. "
                "Crisp 35mm cinema photography, zero wristwatch, zero text."
            ),
        },
        {
            "stem": "2-3-08",
            "seed": 9538,
            "refs": [sc_xia_hall, f_ye_bare, f_qian],
            "prompt": (
                "The traditional restaurant front hall with dark wooden counter, wooden pass-through window, and closed dark-blue cloth kitchen curtain on the rear wall in <Picture 1> is <Subject 1>. "
                "The bare-wristed young man in <Picture 2> is <Subject 2>. The young woman in black apron in <Picture 3> is <Subject 3>. "
                "The target image shows an over-the-shoulder medium close-up past <Subject 3>'s softly blurred right-foreground shoulder onto <Subject 2> standing at the dark wooden counter inside <Subject 1>; "
                "on the wooden counter sit ONE closed brown hardcover ledger and ONE twine-tied coarse burlap herb bundle; "
                "<Subject 2> carries the open army-green canvas backpack on his left forearm and presses his bare right palm onto the burlap herb bundle, with BOTH his left wrist and right wrist completely bare skin (strictly ZERO wristwatch on either wrist!). "
                "Crisp 35mm cinema photography, zero wristwatch, zero text."
            ),
        },
        {
            "stem": "3-2-20_steps_aux",
            "seed": 9620,
            "refs": [str(KF_2K / "3-2-01_2k.png"), f_jian, f_ye_bare, f_qian],
            "prompt": (
                "The plain signless traditional wooden shopfront doorway and stone steps (strictly ZERO overhead signboard or plaque) in <Picture 1> are <Subject 1>. "
                "The older chef with bandaged right wrist in <Picture 2> is <Subject 2>. The bare-wristed young man in <Picture 3> is <Subject 3>. The young woman in black apron in <Picture 4> is <Subject 4>. "
                "The target image shows a medium shot at the doorway steps of <Subject 1> where a large mound of grey-yellow sand and gravel is piled across the bottom of the stone steps; "
                "on the upper stone step, <Subject 2> furiously grips a long-handled iron shovel with both hands ready to lunge forward, while <Subject 3> (wearing his army-green canvas backpack, bare wrists) reaches out beside him to intercept the wooden shovel shaft, and <Subject 4> stands behind them hugging her CLOSED brown hardcover ledger anxiously to her chest. "
                "Crisp 35mm cinema photography, zero overhead signboard, zero text."
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
                t0 = time.time()
                print(f"[Spark 3B {idx}/{len(spark_jobs)}] Generating {stem} ...", flush=True)
                generate_spark_h3_image(
                    prompt=j["prompt"],
                    out_path=KF_2K / f"{stem}_2k.png",
                    out_1k_path=KF_1K / f"{stem}_1k.png",
                    ref_images=j["refs"],
                    aspect_ratio="9:16",
                    seed=j["seed"],
                    steps=6,
                    staged_cache=staged,
                )
                print(f"[Spark 3B {idx}/{len(spark_jobs)}] DONE {stem} in {time.time() - t0:.1f}s", flush=True)
                ready_events[stem].set()
        except BaseException as exc:
            spark_error.append(exc)
            for ev in ready_events.values():
                ev.set()
            raise

    spark_thread = threading.Thread(target=spark_worker, daemon=True)
    spark_thread.start()

    specs: List[Dict[str, Any]] = [
        # --- Immediate 5090 Shots (No Spark Wait!) ---
        {
            "id": "1-1-04", "episode": 1, "duration": 14, "seed": 91104, "wait_stems": [],
            "ref_images": [kf("1-1-04"), kf("1-1_master_4p"), f_ye_2020, f_chu_exec, f_zhao],
            "ref_audios": [v_chu, v_zhao],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The man standing silently on screen-left in <Picture 1>, matching <Picture 3>.\n"
                "- <Subject 2> (S1): The executive man on screen-right in <Picture 1>, matching <Picture 4>. Voice matches Audio 1.\n"
                "- <Subject 3> (S2): The Western-style chef holding the white gold-trimmed ceremonial cap on far right in <Picture 2>, matching <Picture 5>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-2.4s) Medium shot framed from <Picture 1> beside the leather chair and cylindrical floor trash bin.\n"
                "- [Shot 2] (2.4s-7.0s) Medium close-up favoring <Subject 2> on screen-right beside the bare round grey marble table.\n"
                "- [Shot 3] (7.0s-14.0s) Close-up inside <Picture 2> on <Subject 3> holding the white gold-trimmed ceremonial cap.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-2.3s): <Subject 2> pinches the faded cloth off the chair back and drops it straight down INSIDE the cylindrical floor trash bin (keeping the marble tabletop completely empty).\n"
                "- [Shot 2] (2.5s-6.8s): Dusting his fingertips smugly, <Subject 2> (S1) sneers at screen-left: <d>[Chinese] 老叶，上市得讲门面，你那套土锅底，早该翻篇了。</d>\n"
                "- [Shot 3] (7.2s-11.8s): Immediately at 7.2s without delay, <Subject 3> (S2) pats the ceremonial cap at his chest and boasts briskly: <d>[Chinese] 往后店里主打法式鹅肝融火锅，只接高档客。</d> Immediately upon finishing at 11.8s, he closes his mouth in a proud smirk.\n"
                "[Environment]\n- Luxury rooftop VIP room (<Picture 2>) with round grey marble table and night skyline window.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Cloth dropped into bin, arrogant male sneer, brisk boast finishing cleanly by 11.8s followed by 2.0s quiet room tone, zero music."
            ),
        },
        {
            "id": "1-3-01", "episode": 1, "duration": 15, "seed": 91301, "wait_stems": [],
            "ref_images": [kf("1-3-01"), kf("1-3-06"), f_ye_orig, f_lin, f_chu],
            "ref_audios": [v_lin],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The young man seated upright on the wooden bench on screen-left, matching <Picture 3>.\n"
                "- <Subject 2> (S1): The young woman standing on screen-right of the square wooden table in <Picture 2>, matching <Picture 4>. Voice matches Audio 1.\n"
                "- <Subject 3>: The young man seated on a wooden chair beside <Subject 2> in <Picture 2>, matching <Picture 5>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-2.6s) Medium close-up framed from <Picture 1> as <Subject 1> jolts awake and sits upright.\n"
                "- [Shot 2] (2.6s-4.8s) High-angle close-up on the half-open army-green canvas backpack on the wooden bench.\n"
                "- [Shot 3] (4.8s-15.0s) Medium three-shot framed directly from <Picture 2> (<Subject 1> stays seated upright on screen-left, never lying down again) focusing on <Subject 2> demanding across the square wooden table.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-2.5s): <Subject 1> jolts upright from the wooden table and reaches down toward his backpack.\n"
                "- [Shot 2] (2.7s-4.7s): <Subject 1>'s right hand squeezes the twine-tied herb bundle INSIDE the half-open backpack without removing it.\n"
                "- [Shot 3] (5.0s-11.2s): Immediately at 5.0s without waiting for <Subject 3>, <Subject 2> (S1) holds out her open palm toward upright <Subject 1> and demands briskly: <d>[Chinese] 叶寻，发什么呆呢，赶紧把你爷爷那方子拿出来呀。</d> Right at 11.2s she closes her lips and glares impatiently while <Subject 3> sips his cola silently.\n"
                "[Environment]\n- Sunlit 2005 Chongqing eatery hall (<Picture 2>) with square wooden table and green ceiling fan.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Creaking fan, brief gasp, canvas rustle, brisk complete female demand finishing cleanly by 11.2s followed by quiet fan hum, zero music."
            ),
        },
        {
            "id": "3-1-01", "episode": 3, "duration": 15, "seed": 93101, "wait_stems": [],
            "ref_images": [kf("3-1-01"), sc_xia_hall, f_jian, f_qian, f_ye_bare],
            "ref_audios": [v_ye, v_jian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S2): The master chef coughing on SCREEN-LEFT beside the square wooden table in <Picture 1>, matching <Picture 3>. Voice matches Audio 2.\n"
                "- <Subject 2>: The young woman helping <Subject 1> sit down on SCREEN-LEFT in <Picture 1>, matching <Picture 4>.\n"
                "- <Subject 3> (S1): The bare-wristed young man standing beside the dark wooden counter on SCREEN-RIGHT in <Picture 1>, matching <Picture 5>. Voice matches Audio 1.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-2.2s) Medium wide shot framed from <Picture 1> (wooden counter and <Subject 3> on SCREEN-RIGHT, wooden table and <Subject 1>/<Subject 2> on SCREEN-LEFT, authentic plaster walls of <Picture 2> with strictly ZERO refrigerator).\n"
                "- [Shot 2] (2.2s-6.2s) Medium shot inside <Picture 2> (plain white plaster wall and wooden pass-through window behind, ZERO modern refrigerator) keeping <Subject 3> on screen-right speaking toward seated <Subject 1> on screen-left.\n"
                "- [Shot 3] (6.2s-15.0s) Close-up on <Subject 1> seated on screen-left holding a white porcelain cup against plain plaster wall.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-2.1s): Coughing once, <Subject 1> sits onto the wooden bench supported by <Subject 2>.\n"
                "- [Shot 2] (2.3s-6.0s): From the right-side wooden counter, <Subject 3> (S1) asks calmly: <d>[Chinese] 夏叔，急火攻心，嗓子眼疼得像吞刀片吧。</d>\n"
                "- [Shot 3] (6.4s-12.0s): Immediately at 6.4s, holding the white cup and wincing, <Subject 1> (S2) replies briskly in a raspy voice: <d>[Chinese] 可不是，再闻见那股燥辣红油味儿，我这嗓子彻底交代了。</d> Immediately upon finishing at 12.0s, he presses his lips shut and winces silently.\n"
                "[Environment]\n- Traditional 2005 plaster-walled eatery front hall (<Picture 1>, <Picture 2>), zero refrigerators.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Brief dry cough, concerned male question, complete raspy older male reply finishing cleanly by 12.0s with 2.8s quiet room buffer, zero music."
            ),
        },
        {
            "id": "3-2-08", "episode": 3, "duration": 15, "seed": 93208, "wait_stems": [],
            "vo_reuse": {"vocals": TAKES[3] / "3-2-08" / "vo_short_vocals.wav", "ss": 0.238, "se": 5.184, "ratio": 1.25, "dst_start": 0.25},
            "ref_images": [kf("3-2-08"), kf("3-2-09_aux"), f_ye_bare, f_chu, f_lin, f_zhao, f_qian, f_jian],
            "ref_audios": [v_chu],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The bare-wristed young man standing silently on the stone steps in <Picture 1>, matching <Picture 3>.\n"
                "- <Subject 2> (S1): The young man raising a red-and-white megaphone in <Picture 2>, matching <Picture 4>. Voice matches Audio 1.\n"
                "- <Subject 3>: The young woman holding <Subject 2>'s arm in <Picture 2>, matching <Picture 5>.\n"
                "- <Subject 4>: The chef watching smugly in <Picture 2>, matching <Picture 6>.\n"
                "- <Subject 5>: The young woman hugging the closed brown ledger, matching <Picture 7>.\n"
                "- <Subject 6>: The master chef standing beside <Subject 5>, matching <Picture 8>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.8s) Unbroken 4.8-second slow push-in close-up framed strictly on <Picture 1> (<Subject 1> alone on the west steps, DO NOT cut to <Picture 2> before 00:04.800!).\n"
                "- [Shot 2] (4.8s-11.6s) At 00:04.800 hard cut to medium close-up framed from <Picture 2> as <Subject 2> shouts through the megaphone.\n"
                "- [Shot 3] (11.6s-15.0s) At 00:11.600 hard cut to medium three-shot on the west steps showing <Subject 1>, <Subject 5>, and <Subject 6> in silent tension.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.0s-4.7s): For the entire first 4.7 seconds, <Subject 1> watches across the street in complete silence with closed motionless lips.\n"
                "- [Shot 2] (5.0s-11.2s): Only AFTER 5.0s, raising the megaphone to his mouth, <Subject 2> (S1) shouts loudly: <d>[Chinese] 喂，半个月后我们塞纳河畔西餐厅开业，对门冷锅冷灶的趁早关张吧。</d> He lowers the megaphone with closed mouth at 11.2s.\n"
                "- [Shot 3] (11.7s-15.0s): In complete silence (zero clapping sounds, zero music), <Subject 6> clenches his fists and <Subject 5> hugs her closed brown ledger while <Subject 1> stands calm.\n"
                "[Environment]\n- Sunlit Chongqing bluestone street.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Pure quiet street air from 0.0s to 4.8s, loud megaphone taunt from 5.0s to 11.2s, quiet street air from 11.3s to 15.0s, strictly zero music and zero clapping."
            ),
        },
        {
            "id": "3-2-11", "episode": 3, "duration": 13, "seed": 93211, "wait_stems": [],
            "ref_images": [kf("3-2-11"), kf("3-2-12_aux"), f_lin, f_chu, f_jian, f_ye_bare, f_qian],
            "ref_audios": [v_lin, v_jian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young woman on screen-right in <Picture 1>, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 2>: The young man beside <Subject 1> in <Picture 1>, matching <Picture 4>.\n"
                "- <Subject 3> (S2): The master chef on screen-right of the steps in <Picture 2>, matching <Picture 5>. Voice matches Audio 2.\n"
                "- <Subject 4>: The bare-wristed young man wearing the army-green backpack on screen-left in <Picture 2> (his hands hold NO book), matching <Picture 6>.\n"
                "- <Subject 5>: The young woman in center in <Picture 2> holding the ONLY dark-brown hardcover ledger, matching <Picture 7>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.3s) Close-up framed from <Picture 1> on <Subject 1> jeering toward screen-left.\n"
                "- [Shot 2] (4.3s-9.4s) Medium three-shot framed from <Picture 2>.\n"
                "- [Shot 3] (9.4s-13.0s) Close-up two-shot on <Subject 4> (empty bare hands) and <Subject 5> (holding the single brown hardcover ledger between them).\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-4.1s): <Subject 1> (S1) jeers proudly: <d>[Chinese] 叶寻，瞧见没，离了你，我家照样开高档西餐厅。</d>\n"
                "- [Shot 2] (4.5s-9.1s): As <Subject 4> tucks the folded white paper into his green backpack, <Subject 3> (S2) roars angrily: <d>[Chinese] 欺负人欺负到家门口了，请个洋厨子就不知道姓啥了。</d> He closes his mouth at 9.1s.\n"
                "- [Shot 3] (9.5s-13.0s): Keeping both his bare hands empty of any book, <Subject 4> calmly gestures once to quiet <Subject 3> in silence, then points his right index finger at the single dark-brown hardcover ledger held in <Subject 5>'s hands as <Subject 5> opens its cover.\n"
                "[Environment]\n- Sunlit Chongqing bluestone street.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Spiteful female taunt, angry older male roar, soft quiet paper rustle in [Shot 3] with strictly zero clapping or slapping sounds, zero music."
            ),
        },
        {
            "id": "3-2-14", "episode": 3, "duration": 15, "seed": 93214, "wait_stems": [],
            "ref_images": [kf("3-2-14"), kf("3-2-01"), f_ye_bare, f_qian, f_jian],
            "ref_audios": [v_ye, v_qian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The bare-wristed young man wearing the army-green canvas backpack on screen-left in <Picture 1>, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The young woman holding the open brown hardcover ledger in <Picture 1>, matching <Picture 4>. Voice matches Audio 2.\n"
                "- <Subject 3>: The master chef standing beside <Subject 2> on the stone steps, matching <Picture 5>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.8s) Over-the-shoulder close-up framed from <Picture 1> onto <Subject 1> (empty bare hands, no white paper in hand).\n"
                "- [Shot 2] (4.8s-10.4s) Reverse close-up onto <Subject 2> reading the open brown ledger.\n"
                "- [Shot 3] (10.4s-15.0s) Tight medium three-shot on the plain signless wooden doorway steps (strictly ZERO signboards, ZERO carts or vehicles entering the frame; street stays clear while all three react to an offscreen sound).\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-4.6s): Pointing his bare finger at the open ledger page, <Subject 1> (S1) asks calmly: <d>[Chinese] 夏叔，犯不着跟他们置气，芊芊姐，账上还能腾出多少现钱。</d>\n"
                "- [Shot 2] (5.0s-10.2s): Looking up earnestly from the ledger, <Subject 2> (S2) answers: <d>[Chinese] 账面一共三万八，刨去欠菜贩子的货款，手里现钱就剩两万六了。</d>\n"
                "- [Shot 3] (10.6s-13.8s): As <Subject 2> closes the brown ledger, <Subject 1> (S1) says: <d>[Chinese] 两万六够把前头改成明档了，今儿先从门口动。</d> At 13.9s, a loud heavy metallic rolling sound comes from offscreen-right (nothing enters the visual frame) and all three whip their heads sharply toward screen-right with startled eyes and closed mouths.\n"
                "[Environment]\n- Plain signless wooden storefront stone steps, zero text signboards, zero carts in frame.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Calm male question, earnest female reply, confident male line finishing by 13.8s followed by offscreen heavy iron wheel rolling rumble on stone (no engine motor sound), zero music."
            ),
        },
        # --- Spark-Anchored 5090 Shots ---
        {
            "id": "1-1-13", "episode": 1, "duration": 10, "seed": 91113, "wait_stems": ["1-1-13_face_aux"],
            "ref_images": [kf("1-1-13"), kf("1-1-13_face_aux"), kf("1-1-13_aux"), f_ye_2020, f_lin_banq, f_chu_exec, f_zhao],
            "ref_audios": [],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The man in <Picture 1>, <Picture 2>, and <Picture 3> (natural dark-brown eyes and clean white sclera as in <Picture 2>), matching <Picture 4>.\n"
                "- <Subject 2>: The woman behind the round marble table in <Picture 3>, matching <Picture 5>.\n"
                "- <Subject 3>: The executive man beside <Subject 2> in <Picture 3>, matching <Picture 6>.\n"
                "- <Subject 4>: The chef beside <Subject 3> in <Picture 3>, matching <Picture 7>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-2.2s) High-angle close-up framed from <Picture 1> showing <Subject 1>'s left hand clenching beside the cylindrical floor trash bin.\n"
                "- [Shot 2] (2.2s-4.8s) Chest-up front close-up framed directly from <Picture 2> (natural normal human dark-brown eyes, zero red glow) as <Subject 1> rips off his thin black lanyard and small square gold badge.\n"
                "- [Shot 3] (4.8s-6.8s) Tabletop close-up on the round grey marble table beside the champagne glass and white transfer slip.\n"
                "- [Shot 4] (6.8s-10.0s) Wide interior shot framed directly from <Picture 3> as <Subject 1> pushes open the right-rear wooden door and exits.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-2.1s): Silently clenching his left hand into a tight fist.\n"
                "- [Shot 2] (2.3s-4.7s): Keeping normal clear dark-brown eyes and closed lips (<Picture 2>), <Subject 1> yanks the thin black lanyard and square gold badge off his neck.\n"
                "- [Shot 3] (4.9s-6.7s): <Subject 1>'s hand slams the square gold badge and black lanyard onto the round marble table beside the white transfer slip.\n"
                "- [Shot 4] (6.9s-10.0s): Leaving the others standing behind the round table (<Picture 3>), <Subject 1> strides to the right-rear wooden door and exits.\n"
                "[Environment]\n- Luxury rooftop banquet room (<Picture 3>).\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Pure foley only (cord snap, metallic badge slam on marble, footsteps, wooden door open), zero human voice, zero music."
            ),
        },
        {
            "id": "2-1-04", "episode": 2, "duration": 15, "seed": 92104, "wait_stems": ["2-1_post_watch_master"],
            "ref_images": [kf("2-1-04"), kf("2-1_post_watch_master"), f_lin, f_ye_bare],
            "ref_audios": [v_lin, v_ye],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young woman on the upper stone step on screen-right in <Picture 1> and <Picture 2> (bare wrists), matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The bare-wristed young man on screen-left wearing the army-green canvas backpack in <Picture 2>, matching <Picture 4>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.8s) Medium close-up framed from <Picture 1> in front of the wide-open wooden doorway.\n"
                "- [Shot 2] (4.8s-7.0s) Tight close-up on <Subject 2>'s wrist as his right hand unclasps and removes the small black plastic watch completely off, leaving bare skin.\n"
                "- [Shot 3] (7.0s-10.6s) Chest-up medium close-up two-shot (cropping above the waist so <Subject 2>'s lowered left arm stays out of frame while his bare right hand places the single black plastic watch into <Subject 1>'s open left palm).\n"
                "- [Shot 4] (10.6s-15.0s) Over-the-shoulder close-up past <Subject 2>'s green-strapped shoulder onto <Subject 1> staring at the single black watch in her left palm (her wrists bare).\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-4.6s): Extending her open left palm toward screen-left, <Subject 1> (S1) orders: <d>[Chinese] 差不多行了，服个软把方子交出来，刚才的事我翻篇。</d>\n"
                "- [Shot 2] (4.9s-6.9s): <Subject 2> unsnaps the black plastic watch and pulls it completely off his bare wrist.\n"
                "- [Shot 3] (7.2s-10.4s): Reaching his bare right hand across, <Subject 2> (S2) presses that single black watch into <Subject 1>'s open left palm and states flatly: <d>[Chinese] 东西收好，咱俩完了。</d>\n"
                "- [Shot 4] (10.8s-13.9s): Looking from the watch in her palm up to <Subject 2> in disbelief, <Subject 1> (S1) gasps: <d>[Chinese] 你说什么，叶寻，你敢提分手。</d> She freezes silently at 13.9s.\n"
                "[Environment]\n- Wide-open wooden doorway steps (<Picture 2>), zero text.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Haughty female command, watch click, slap into palm, icy male breakup line, shocked female gasp finishing by 13.9s, zero music."
            ),
        },
        {
            "id": "2-1-08", "episode": 2, "duration": 15, "seed": 92108, "wait_stems": ["2-1_post_watch_master"],
            "ref_images": [kf("2-1-08"), kf("2-1_post_watch_master"), f_ye_bare, f_lin, f_chu],
            "ref_audios": [v_ye],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The bare-wristed young man on screen-left in <Picture 1> and <Picture 2>, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 2>: The bare-wristed young woman in center-right of <Picture 2> holding the single black watch inside her left palm at her chest while her right hand grips <Subject 1>'s green strap, matching <Picture 4>.\n"
                "- <Subject 3>: The young man leaning at the right wooden doorframe in <Picture 2>, matching <Picture 5>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.2s) Close-up framed from <Picture 1> on <Subject 1> facing screen-right.\n"
                "- [Shot 2] (4.2s-6.2s) Reverse close-up inside <Picture 2> on <Subject 2> (BOTH her wrists completely bare without any watch!) holding the single black watch in her left hand at her chest.\n"
                "- [Shot 3] (6.2s-15.0s) Medium three-shot framed directly from <Picture 2> (<Subject 1> bare wrists, <Subject 2> bare wrists keeping right hand on green strap, <Subject 3> at doorframe).\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-4.0s): <Subject 1> (S1) says coldly: <d>[Chinese] 分了，往后你家店是死是活，别来沾边。</d>\n"
                "- [Shot 2] (4.3s-6.1s): With bare wrists, <Subject 2> stands speechless holding the single watch in her palm.\n"
                "- [Shot 3] (6.4s-11.8s): Immediately at 6.4s without pausing, <Subject 1> (S1) looks past <Subject 2> at <Subject 3> and says briskly: <d>[Chinese] 楚少，刚吹出去的星级主厨，赶紧给人请来啊。</d> Right at 11.8s he closes his mouth calmly while all three hold tension.\n"
                "[Environment]\n- Open wooden doorway and two flat stone steps (<Picture 2>), zero text.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Decisive male voice, quiet street cicadas, brisk male challenge finishing cleanly by 11.8s followed by 3.0s quiet street air, zero music."
            ),
        },
        {
            "id": "2-2-01", "episode": 2, "duration": 12, "seed": 92201, "wait_stems": ["2-2-01"],
            "ref_images": [kf("2-2-01"), f_qian, f_thug],
            "ref_audios": [v_thug, v_qian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S2): The young woman standing beside the bare wooden pillar in <Picture 1> holding the crumpled white paper inside her lowered right hand, matching <Picture 2>. Voice matches Audio 2.\n"
                "- <Subject 2> (S1): The street punk stepping onto the stone steps on screen-left in <Picture 1> holding colorful flyers, matching <Picture 3>. Voice matches Audio 1.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-2.2s) Medium-wide shot framed from <Picture 1> (bare wooden pillar with zero paper on the pillar; <Subject 1> already holds the crumpled white paper in her right hand at her hip).\n"
                "- [Shot 2] (2.2s-7.8s) Medium close-up two-shot beside the bare wooden pillar with <Subject 2> on screen-left pressing in toward <Subject 1> (keeping the crumpled white paper clutched in her right hand).\n"
                "- [Shot 3] (7.8s-12.0s) Close-up on <Subject 1> and <Subject 2>'s reaching right hand.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-2.1s): Holding the crumpled recruitment paper tightly in her lowered right fist (never dropping it), <Subject 1> takes half a step back against the bare wooden pillar as <Subject 2> steps up grinning.\n"
                "- [Shot 2] (2.4s-7.6s): Extending a colorful loan flyer toward <Subject 1>, <Subject 2> (S1) coaxes: <d>[Chinese] 小老板娘，招工纸都撕啦，周转不开签两万块应急呗。</d>\n"
                "- [Shot 3] (8.0s-10.0s): Pushing the flyer back with her left hand while keeping the crumpled paper in her right hand, <Subject 1> (S2) says firmly: <d>[Chinese] 不借，你让开。</d> She closes her lips at 10.0s.\n"
                "- [Shot 3] (10.1s-12.0s): Scowling, <Subject 2> lunges his right hand forward to grab <Subject 1>'s left forearm.\n"
                "[Environment]\n- Quiet sunlit stone steps outside the bare-pillared wooden storefront (<Picture 1>), zero signboards.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Footsteps on stone, paper crinkle in fist, sleazy male coaxing, firm female refusal, zero music."
            ),
        },
        {
            "id": "2-3-05", "episode": 2, "duration": 15, "seed": 92305, "wait_stems": ["2-3-05", "2-3-08"],
            "ref_images": [kf("2-3-05"), kf("2-3-08"), kf("2-3-05_qian_aux"), f_ye_bare, f_qian],
            "ref_audios": [v_ye, v_qian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The bare-wristed young man standing outside the dark wooden counter in <Picture 1> and <Picture 2> (strictly ZERO wristwatch on either wrist!), matching <Picture 4>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The young woman standing behind the dark wooden counter in <Picture 3>, matching <Picture 5>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-2.5s) Medium close-up framed from <Picture 1> as bare-wristed <Subject 1> silently unzips the army-green backpack and lifts out one twine-tied coarse burlap herb bundle beside the single closed brown ledger.\n"
                "- [Shot 2] (2.5s-8.0s) Over-the-shoulder close-up framed from <Picture 2> as <Subject 1> presses his bare right palm atop the coarse burlap herb bundle.\n"
                "- [Shot 3] (8.0s-15.0s) Reverse medium close-up framed directly from <Picture 3> onto <Subject 2> behind the wooden counter in front of plain 2005 plaster walls and dark-blue cloth curtain (zero modern glass fridge).\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-2.4s): In complete vocal silence, <Subject 1> unzips the green backpack with bare hands and places the burlap herb bundle onto the counter.\n"
                "- [Shot 2] (2.7s-7.8s): Pressing his bare palm on the herb bundle, <Subject 1> (S1) proposes clearly: <d>[Chinese] 店别关，炒菜改做养生火锅，我出方子盯灶，咱们合伙。</d>\n"
                "- [Shot 3] (8.2s-13.6s): Raising her left hand in surprised protest (<Picture 3>), <Subject 2> (S2) exclaims: <d>[Chinese] 这哪行啊，你爷爷留的方子，不是说好拿去帮双双吗。</d> She finishes cleanly at 13.6s with silent parted lips.\n"
                "[Environment]\n- Traditional 2005 restaurant front hall (<Picture 1>, <Picture 2>, <Picture 3>), bare wrists, single brown ledger, zero modern appliances.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Clean zipper pull and bundle thud in [Shot 1] with zero vocal grunt, steady male proposal, complete female protest finishing by 13.6s, zero music."
            ),
        },
        {
            "id": "2-3-08", "episode": 2, "duration": 15, "seed": 92308, "wait_stems": ["2-3-08"],
            "ref_images": [kf("2-3-08"), kf("2-3-10_aux"), f_ye_bare, f_qian, f_jian],
            "ref_audios": [v_ye, v_jian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The bare-wristed young man at the wooden counter in <Picture 1> (strictly ZERO wristwatch on either wrist!), matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 2>: The young woman at the counter on screen-right, matching <Picture 4>.\n"
                "- <Subject 3> (S2): The master chef standing before the dark-blue cloth curtain in <Picture 2>, matching <Picture 5>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-3.6s) Over-the-shoulder close-up framed from <Picture 1> onto bare-wristed <Subject 1> tapping the herb bundle.\n"
                "- [Shot 2] (3.6s-5.8s) Medium shot toward the rear dark-blue cloth curtain as <Subject 3> flings the curtain open and steps out.\n"
                "- [Shot 3] (5.8s-15.0s) Medium close-up framed from <Picture 2> on <Subject 3> clutching his sore throat.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-3.4s): Tapping the burlap herb bundle with his bare hand, <Subject 1> (S1) says firmly: <d>[Chinese] 刚跟她分了，这东西，我只信得过夏家。</d>\n"
                "- [Shot 2] (3.7s-5.7s): At 3.8s the dark-blue curtain is flung sharply open and <Subject 3> strides out holding the iron wok ladle.\n"
                "- [Shot 3] (6.0s-11.8s): Immediately at 6.0s without delay, <Subject 3> (S2) points the ladle slightly forward and barks briskly in a raspy voice: <d>[Chinese] 瞎胡闹，夏家做了一辈子川菜，改什么野路子。</d> Right upon finishing at 11.8s, he clamps his mouth shut glaring silently.\n"
                "[Environment]\n- Traditional 2005 eatery front hall.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Sincere male line, cloth curtain whipped open, brisk complete raspy older male rebuke finishing cleanly by 11.8s followed by 3.0s silent tension, zero music."
            ),
        },
        {
            "id": "3-2-20", "episode": 3, "duration": 14, "seed": 93220, "wait_stems": ["3-2-20_steps_aux"],
            "ref_images": [kf("3-2-20"), kf("3-2-20_steps_aux"), f_zhao, f_jian, f_ye_bare, f_qian],
            "ref_audios": [v_zhao, v_jian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The chef standing beside the gravel mound in <Picture 1> with the red booklet under his left arm, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The master chef gripping the iron shovel on the gravel-blocked signless doorway steps in <Picture 2>, matching <Picture 4>. Voice matches Audio 2.\n"
                "- <Subject 3>: The bare-wristed young man wearing the army-green backpack in <Picture 2>, matching <Picture 5>.\n"
                "- <Subject 4>: The young woman hugging the closed brown ledger in <Picture 2>, matching <Picture 6>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-5.5s) Medium close-up framed from <Picture 1> on <Subject 1> facing upper-left.\n"
                "- [Shot 2] (5.5s-9.8s) Medium shot framed directly from <Picture 2> (large sand-and-gravel mound already blocking the signless wooden steps, zero overhead signboard) as <Subject 2> raises the shovel roaring.\n"
                "- [Shot 3] (9.8s-14.0s) Tight single close-up ONLY on silent <Subject 3> (wearing his green backpack, closed motionless lips) clamping his bare hands onto the wooden shovel shaft and taking the shovel firmly (<Subject 2>'s face is offscreen, strictly ZERO speech after 9.5s!).\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-5.3s): Folding his arms smugly, <Subject 1> (S1) jeers: <d>[Chinese] 路窄，借你们台阶堆半个月呗，横竖你们这破店也没人登门。</d>\n"
                "- [Shot 2] (5.7s-9.4s): Behind the gravel mound of <Picture 2>, <Subject 2> (S2) hoists the iron shovel in both hands and roars briskly: <d>[Chinese] 蹬鼻子上脸是吧，我跟你们拼了。</d> Immediately at 9.4s he clamps his jaw shut.\n"
                "- [Shot 3] (9.9s-14.0s): In dead vocal silence with closed lips, <Subject 3> grips the wooden shovel shaft firmly with both bare hands and takes control of the shovel.\n"
                "[Environment]\n- Plain signless wooden storefront steps blocked by sand and gravel (<Picture 2>), zero overhead signboards.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Smug male jeer in [Shot 1], complete furious older male roar finishing by 9.4s in [Shot 2], pure silent wood grip from 9.8s to 14.0s with zero speech, zero music."
            ),
        },
    ]

    # Update ep01..03_v7_plan.json & verify zero-appearance lint
    plans = {
        ep_no: json.loads((WORK_DIR / f"ep0{ep_no}_v7_plan.json").read_text(encoding="utf-8"))
        for ep_no in (1, 2, 3)
    }
    by_id = {s["id"]: s for s in specs}
    for ep_no, plist in plans.items():
        for item in plist:
            if item["id"] in by_id:
                u = by_id[item["id"]]
                item["duration"] = u["duration"]
                item["seed"] = u["seed"]
                item["ref_images"] = u["ref_images"]
                item["ref_audios"] = u["ref_audios"]
                item["prompt"] = u["prompt"]
        (WORK_DIR / f"ep0{ep_no}_v7_plan.json").write_text(json.dumps(plist, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lint_errs = []
    for ep_no, plist in plans.items():
        for s in plist:
            lint_errs.extend(pika_runner.lint_zero_appearance(s["prompt"], s["id"]))
    if lint_errs:
        raise RuntimeError("Lint failed:\n" + "\n".join(lint_errs))
    print("[LINT 3B] Universal Zero-Appearance Lint PASSED!", flush=True)

    for idx, u in enumerate(specs, start=1):
        sid = u["id"]
        ep_no = u["episode"]
        for st in u["wait_stems"]:
            if not ready_events[st].is_set():
                print(f"[5090 3B] Waiting on Spark {st} for {sid} ...", flush=True)
                ready_events[st].wait()
        if spark_error:
            raise spark_error[0]

        tdir = TAKES[ep_no]
        sdir = tdir / sid
        final_mp4 = sdir / "video.mp4"
        print(f"[5090 3B {idx}/{len(specs)}] Generating {sid} ({u['duration']}s, seed={u['seed']}) ...", flush=True)
        if "vo_reuse" in u:
            vr = u["vo_reuse"]
            base_mp4 = sdir / "video_base.mp4"
            refs_1k = [pika_runner.ensure_1k_image(Path(p), CACHE_1K) for p in u["ref_images"]]
            audios = [Path(p) for p in u.get("ref_audios", [])]
            meta = pika_runner.call_pika_5090(
                base_mp4, u["prompt"], int(u["duration"]), int(u["seed"]), "9:16", "480p", refs_1k, audios
            )
            vo_info = run_vo_mux(base_mp4, Path(vr["vocals"]), final_mp4, vr["ss"], vr["se"], vr["ratio"], vr["dst_start"])
            meta["vo_custom_applied"] = vo_info
            (sdir / "video.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        else:
            pika_runner.run_shot(u, tdir, CACHE_1K, resolution="480p", force=True)

        make_half_sec_strip(final_mp4, sid, DIAG_DIR / f"{sid}_0.5s.jpg")
        plan_entry = next(x for x in plans[ep_no] if x["id"] == sid)
        vad_res = vad_gate.audit_shot_audio(vad_sess, final_mp4, plan_entry)
        print(f"[VAD 3B] {sid} -> status={vad_res['status']} vad={[(s, e) for s, e, _ in vad_res['vad_segments']]}", flush=True)

    spark_thread.join()
    print("PHASE 3B FINAL POLISH COMPLETE!", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
