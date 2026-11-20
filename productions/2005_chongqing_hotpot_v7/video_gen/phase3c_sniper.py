#!/home/zhongwenyu/data/anaconda3/bin/python
"""
Phase 3C Sniper Pass driven by Round-3 `gemini-4-hydrogen-high` Script-Supervisor verdicts:
  - 1 Spark anchor (`3-2-20_steps_aux`: empty bare left doorframe with ZERO leaning shovel; ONLY ONE iron shovel held in Xia Jianguo's hands)
  - 6 targeted 5090 video shots (`1-1-04`, `1-1-13`, `1-3-01`, `2-3-08`, `3-2-08`, `3-2-20`):
      * `1-1-04` (15s): tighter Shot 1/2 (`0s-1.7s`, `1.8s-5.8s`) so Shot 3 (`6.0s-15.0s`) gives Zhao Fan 4.4s tail buffer
      * `1-1-13` (10s): completely purge any "red"/"eye"/"glow" words from positive prompt so H3 never paints neon red eyes onto `<Picture 2>`
      * `1-3-01` (15s): pass `sc_lin_hall` (`沙正街林家食府老店大堂`) to lock authentic wooden wall panels on screen-left (zero floor-standing AC) + 5s tail buffer
      * `2-3-08` (14s): clean 2-shot structure (`[Shot 1]` `0s-3.7s` -> `[Shot 2]` `3.7s-14.0s` framed directly from `2-3-10_aux`) eliminating mid-sentence cut gibberish
      * `3-2-08` (15s): anchor `[Shot 3]` directly to `3-2-12_aux` and remove `f_zhao`/`f_lin` portrait refs so Zhao Fan & megaphone never leak onto west steps
      * `3-2-20` (14s): re-anchored on single-shovel `3-2-20_steps_aux`
"""
from __future__ import annotations

import json
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


def kf(stem: str) -> str:
    return str(KF_1K / f"{stem}_1k.png")


def main() -> int:
    amap = json.loads((WORK_DIR / "asset_map.json").read_text(encoding="utf-8"))
    vad_sess = ort.InferenceSession(str(vad_gate.DEFAULT_VAD_ONNX))

    v_ye = amap["叶寻"]["voice"]
    v_lin = amap["林双双"]["voice"]
    v_chu = amap["楚南"]["voice"]
    v_zhao = amap["赵帆"]["voice"]
    v_jian = amap["夏建国"]["voice"]

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
    sc_lin_hall = amap["沙正街林家食府老店大堂"]["main_1k"]

    ready_step_aux = threading.Event()
    spark_error: List[BaseException] = []

    def spark_worker() -> None:
        try:
            t0 = time.time()
            print("[Spark 3C 1/1] Generating single-shovel 3-2-20_steps_aux ...", flush=True)
            generate_spark_h3_image(
                prompt=(
                    "The plain signless traditional 2005 wooden shopfront doorway and grey stone steps in <Picture 1> are <Subject 1>. "
                    "The older chef with white-bandaged right wrist in <Picture 2> is <Subject 2>. "
                    "The bare-wristed young man in <Picture 3> is <Subject 3>. "
                    "The young woman in black apron in <Picture 4> is <Subject 4>. "
                    "The target image shows a medium shot at the open wooden doorway of <Subject 1> with a large mound of yellow-grey sand and gravel piled across the bottom stone step; "
                    "the left and right wooden doorframes are completely empty bare timber (strictly NO shovel or tool leaning against the wooden doorframe — there is ONLY ONE shovel in the entire image!); "
                    "on the right side behind the sand mound, <Subject 2> holds that ONLY long-handled iron shovel diagonally across his chest with BOTH hands roaring in anger, "
                    "while on screen-left <Subject 3> (wearing his army-green canvas backpack, both hands empty and bare-wristed) steps beside <Subject 2> reaching his empty hands toward <Subject 2>'s wooden shovel shaft, "
                    "and in center-back <Subject 4> hugs her CLOSED brown hardcover ledger to her chest. "
                    "Crisp 35mm cinema photography, strictly one single shovel in the whole scene, zero overhead signboard, zero text."
                ),
                out_path=KF_2K / "3-2-20_steps_aux_2k.png",
                out_1k_path=KF_1K / "3-2-20_steps_aux_1k.png",
                ref_images=[str(KF_2K / "2-2-01_2k.png"), f_jian, f_ye_bare, f_qian],
                aspect_ratio="9:16",
                seed=9820,
                steps=6,
            )
            print(f"[Spark 3C 1/1] DONE 3-2-20_steps_aux in {time.time() - t0:.1f}s", flush=True)
            ready_step_aux.set()
        except BaseException as exc:
            spark_error.append(exc)
            ready_step_aux.set()
            raise

    spark_thread = threading.Thread(target=spark_worker, daemon=True)
    spark_thread.start()

    specs: List[Dict[str, Any]] = [
        {
            "id": "1-1-04", "episode": 1, "duration": 15, "seed": 95104, "wait_spark": False,
            "ref_images": [kf("1-1-04"), kf("1-1_master_4p"), f_ye_2020, f_chu_exec, f_zhao],
            "ref_audios": [v_chu, v_zhao],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The man standing silently on screen-left in <Picture 1>, matching <Picture 3>.\n"
                "- <Subject 2> (S1): The executive man on screen-right in <Picture 1>, matching <Picture 4>. Voice matches Audio 1.\n"
                "- <Subject 3> (S2): The Western-style chef holding the white gold-trimmed ceremonial cap on far right in <Picture 2>, matching <Picture 5>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-1.8s) Medium shot framed from <Picture 1> beside the leather chair and cylindrical floor trash bin.\n"
                "- [Shot 2] (1.8s-6.0s) Medium close-up favoring <Subject 2> on screen-right beside the bare round grey marble table.\n"
                "- [Shot 3] (6.0s-15.0s) Close-up inside <Picture 2> on <Subject 3> holding the white gold-trimmed ceremonial cap.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-1.7s): <Subject 2> drops the faded cloth straight down INSIDE the cylindrical floor trash bin (marble tabletop stays completely empty).\n"
                "- [Shot 2] (1.9s-5.8s): Speaking immediately at 1.9s without rubbing his hands or waiting, <Subject 2> (S1) sneers briskly: <d>[Chinese] 老叶，上市得讲门面，你那套土锅底，早该翻篇了。</d> He closes his mouth at 5.8s.\n"
                "- [Shot 3] (6.2s-10.6s): Immediately at 6.2s without any pause, <Subject 3> (S2) pats the ceremonial cap at his chest and speaks briskly at fast conversational pace: <d>[Chinese] 往后店里主打法式鹅肝融火锅，只接高档客。</d> Right at 10.6s he closes his lips into a smug grin and holds silent from 10.7s to 15.0s.\n"
                "[Environment]\n- Luxury rooftop VIP room (<Picture 2>) with round grey marble table and night skyline window.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Cloth dropped into bin, brisk male sneer (1.9s-5.8s), brisk male boast finishing completely by 10.6s followed by 4.3s quiet room tone, zero music."
            ),
        },
        {
            "id": "1-1-13", "episode": 1, "duration": 10, "seed": 95113, "wait_spark": False,
            "ref_images": [kf("1-1-13"), kf("1-1-13_face_aux"), kf("1-1-13_aux"), f_ye_2020, f_lin_banq, f_chu_exec, f_zhao],
            "ref_audios": [],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The calm stoic man in <Picture 1>, <Picture 2>, and <Picture 3>, matching <Picture 4>.\n"
                "- <Subject 2>: The woman standing behind the round marble table in <Picture 3>, matching <Picture 5>.\n"
                "- <Subject 3>: The executive man beside <Subject 2> in <Picture 3>, matching <Picture 6>.\n"
                "- <Subject 4>: The chef beside <Subject 3> in <Picture 3>, matching <Picture 7>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-2.2s) High-angle close-up framed from <Picture 1> showing <Subject 1>'s left hand clenching beside the cylindrical floor trash bin.\n"
                "- [Shot 2] (2.2s-4.6s) Chest-up front close-up framed directly from <Picture 2> preserving his exact calm realistic human facial appearance in <Picture 2> while his right hand lifts the thin matte-black fabric lanyard and small square gold badge up off his collar.\n"
                "- [Shot 3] (4.6s-6.6s) Tabletop close-up on the round grey marble table beside the champagne glass and white transfer slip.\n"
                "- [Shot 4] (6.6s-10.0s) Wide interior shot framed directly from <Picture 3> as <Subject 1> walks to the right-rear wooden door and exits.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-2.1s): Silently clenching his left hand into a firm fist.\n"
                "- [Shot 2] (2.3s-4.5s): Looking slightly downward with calm stoic composure (<Picture 2>) and closed lips, <Subject 1> unloops and pulls the matte-black fabric lanyard and square gold badge off his neck.\n"
                "- [Shot 3] (4.7s-6.5s): <Subject 1>'s hand tosses the square gold badge with its matte-black lanyard onto the grey marble table beside the white transfer slip.\n"
                "- [Shot 4] (6.7s-10.0s): Without looking back at the three figures behind the round table (<Picture 3>), <Subject 1> pushes open the right-rear wooden door and walks out.\n"
                "[Environment]\n- Luxury rooftop banquet room (<Picture 3>) with warm hotel lighting.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Pure foley only (fabric strap pull, metallic badge clink on marble, leather shoes walking, wooden door opening), zero speech, zero music."
            ),
        },
        {
            "id": "1-3-01", "episode": 1, "duration": 15, "seed": 95301, "wait_spark": False,
            "ref_images": [kf("1-3-01"), kf("1-3-06"), sc_lin_hall, f_ye_orig, f_lin, f_chu],
            "ref_audios": [v_lin],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The young man seated upright on the wooden bench on screen-left, matching <Picture 4>.\n"
                "- <Subject 2> (S1): The young woman standing right beside the square wooden table on screen-right in <Picture 2>, matching <Picture 5>. Voice matches Audio 1.\n"
                "- <Subject 3>: The young man seated on a wooden chair beside <Subject 2> in <Picture 2>, matching <Picture 6>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-2.4s) Medium close-up framed from <Picture 1> as <Subject 1> jolts awake and sits upright.\n"
                "- [Shot 2] (2.4s-4.3s) High-angle close-up on the half-open army-green canvas backpack on the wooden bench.\n"
                "- [Shot 3] (4.3s-15.0s) Medium three-shot framed directly from <Picture 2> inside the weathered wooden-walled 2005 hall of <Picture 3> (old dark wooden wall Wainscoting and vintage wall posters behind <Subject 1>, strictly ZERO white air conditioner or modern cabinet anywhere!).\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-2.3s): <Subject 1> jolts upright from the wooden table and reaches down to his backpack.\n"
                "- [Shot 2] (2.5s-4.2s): <Subject 1>'s right hand squeezes the twine-tied herb bundle INSIDE the half-open backpack without taking it out.\n"
                "- [Shot 3] (4.5s-10.0s): Already standing right beside the table (<Picture 2>), immediately at 4.5s without walking or waiting, <Subject 2> (S1) extends her open palm toward seated <Subject 1> and demands briskly: <d>[Chinese] 叶寻，发什么呆呢，赶紧把你爷爷那方子拿出来呀。</d> Right at 10.0s she closes her mouth and glares impatiently while <Subject 1> stays seated upright in silent refusal.\n"
                "[Environment]\n- Authentic 2005 weathered wooden Chongqing eatery hall (<Picture 2>, <Picture 3>) with dark wooden walls, square wooden tables, and green ceiling fan (strictly zero floor-standing air conditioner).\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Overhead fan hum, brief gasp, canvas rustle, brisk complete female demand finishing cleanly by 10.0s followed by 4.8s quiet room tone, zero music."
            ),
        },
        {
            "id": "2-3-08", "episode": 2, "duration": 14, "seed": 95308, "wait_spark": False,
            "ref_images": [kf("2-3-08"), kf("2-3-10_aux"), f_ye_bare, f_qian, f_jian],
            "ref_audios": [v_ye, v_jian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The bare-wristed young man at the wooden counter in <Picture 1> (zero wristwatch), matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 2>: The young woman at the counter on screen-right in <Picture 1>, matching <Picture 4>.\n"
                "- <Subject 3> (S2): The master chef standing in front of the dark-blue cloth curtain holding the iron wok ladle in <Picture 2>, matching <Picture 5>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-3.8s) Over-the-shoulder medium close-up framed from <Picture 1> onto bare-wristed <Subject 1> tapping the burlap herb bundle.\n"
                "- [Shot 2] (3.8s-14.0s) Single unbroken medium close-up framed directly from <Picture 2> on <Subject 3> standing in front of the swaying dark-blue cloth kitchen curtain (no internal cut after 3.8s!).\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-3.5s): Tapping the burlap herb bundle with his bare right hand, <Subject 1> (S1) says firmly: <d>[Chinese] 刚跟她分了，这东西，我只信得过夏家。</d> He closes his mouth at 3.5s.\n"
                "- [Shot 2] (4.0s-9.8s): Standing before the swaying blue cloth curtain (<Picture 2>) holding the iron wok ladle, <Subject 3> (S2) speaks ONE single continuous line briskly from 4.0s to 9.8s: <d>[Chinese] 瞎胡闹，夏家做了一辈子川菜，改什么野路子。</d> Right at 9.8s he clamps his lips tightly shut and glares in complete vocal silence from 9.9s to 14.0s.\n"
                "[Environment]\n- Traditional 2005 eatery front hall (<Picture 1>, <Picture 2>).\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Sincere male line (0.2s-3.5s), cloth curtain rustle, one single continuous raspy older male line finishing cleanly by 9.8s followed by 4.0s complete vocal silence, zero extra speech, zero music."
            ),
        },
        {
            "id": "3-2-08", "episode": 3, "duration": 15, "seed": 95208, "wait_spark": False,
            "vo_reuse": {"vocals": TAKES[3] / "3-2-08" / "vo_short_vocals.wav", "ss": 0.238, "se": 5.184, "ratio": 1.25, "dst_start": 0.25},
            "ref_images": [kf("3-2-08"), kf("3-2-09_aux"), kf("3-2-12_aux"), f_ye_bare, f_chu, f_jian],
            "ref_audios": [v_chu],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The young man standing silently with empty hands in <Picture 1> and on screen-left of <Picture 3>, matching <Picture 4>.\n"
                "- <Subject 2> (S1): The young man raising the red-and-white megaphone on the opposite east storefront in <Picture 2>, matching <Picture 5>. Voice matches Audio 1.\n"
                "- <Subject 3>: The young woman hugging the closed brown ledger in the center of <Picture 3>.\n"
                "- <Subject 4>: The older master chef on screen-right of <Picture 3>, matching <Picture 6>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.8s) Unbroken 4.8-second slow push-in close-up framed strictly on <Picture 1> (<Subject 1> alone on the stone steps with closed motionless lips; DO NOT cut before 00:04.800!).\n"
                "- [Shot 2] (4.8s-11.4s) At 00:04.800 hard cut to medium close-up framed strictly from <Picture 2> as <Subject 2> shouts through the megaphone.\n"
                "- [Shot 3] (11.4s-15.0s) At 00:11.400 hard cut to medium three-shot framed strictly from <Picture 3> showing ONLY <Subject 1> (empty hands, zero megaphone!), <Subject 3> (hugging closed brown ledger), and <Subject 4> (clenching fists in silent anger, no fourth person).\n"
                "[Timeline]\n"
                "- [Shot 1] (0.0s-4.7s): For the entire first 4.7 seconds, <Subject 1> watches across the street in complete vocal silence with closed lips.\n"
                "- [Shot 2] (5.0s-11.1s): Raising the megaphone in <Picture 2>, <Subject 2> (S1) shouts loudly: <d>[Chinese] 喂，半个月后我们塞纳河畔西餐厅开业，对门冷锅冷灶的趁早关张吧。</d> He lowers the megaphone at 11.1s.\n"
                "- [Shot 3] (11.5s-15.0s): Framed strictly as <Picture 3> in complete silence (strictly zero clapping, zero applause), <Subject 4> clenches his bandaged fist glaring across the street while <Subject 1> (empty hands) and <Subject 3> stand tense.\n"
                "[Environment]\n- Sunlit Chongqing bluestone street.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Quiet street air from 0.0s to 4.8s, loud megaphone taunt from 5.0s to 11.1s, quiet tense street air from 11.2s to 15.0s, strictly zero applause, zero clapping, zero music."
            ),
        },
        {
            "id": "3-2-20", "episode": 3, "duration": 14, "seed": 95220, "wait_spark": True,
            "ref_images": [kf("3-2-20"), kf("3-2-20_steps_aux"), f_zhao, f_jian, f_ye_bare, f_qian],
            "ref_audios": [v_zhao, v_jian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The chef standing beside the gravel mound in <Picture 1> with the red booklet under his left arm, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The older master chef holding the ONLY long-handled iron shovel in <Picture 2>, matching <Picture 4>. Voice matches Audio 2.\n"
                "- <Subject 3>: The bare-wristed young man wearing the army-green backpack on screen-left in <Picture 2>, matching <Picture 5>.\n"
                "- <Subject 4>: The young woman hugging the closed brown ledger in <Picture 2>, matching <Picture 6>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-5.4s) Medium close-up framed from <Picture 1> on <Subject 1> facing upper-left.\n"
                "- [Shot 2] (5.4s-9.6s) Medium shot framed directly from <Picture 2> (empty bare left wooden doorframe with NO leaning shovel; only ONE shovel held in <Subject 2>'s hands behind the sand-and-gravel mound).\n"
                "- [Shot 3] (9.6s-14.0s) Tight chest-up close-up on <Subject 3> (closed motionless lips) clamping both bare hands firmly onto the wooden shovel shaft in <Subject 2>'s grasp to stop him (<Subject 2>'s face cropped offscreen, strictly ZERO speech after 9.3s!).\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-5.2s): Folding his arms smugly, <Subject 1> (S1) jeers: <d>[Chinese] 路窄，借你们台阶堆半个月呗，横竖你们这破店也没人登门。</d>\n"
                "- [Shot 2] (5.6s-9.2s): Behind the gravel mound in <Picture 2>, <Subject 2> (S2) raises that single iron shovel in both hands and roars briskly: <d>[Chinese] 蹬鼻子上脸是吧，我跟你们拼了。</d> Right at 9.2s he clamps his jaw shut.\n"
                "- [Shot 3] (9.7s-14.0s): In complete vocal silence with closed lips, <Subject 3> grips the wooden shovel shaft firmly with both bare hands and holds it steady.\n"
                "[Environment]\n- Plain signless wooden storefront steps blocked by sand and gravel (<Picture 2>), single shovel only, zero overhead signboards.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Smug male jeer (0.2s-5.2s), furious older male roar finishing cleanly by 9.2s, pure wood grip foley from 9.6s to 14.0s with zero speech, zero music."
            ),
        },
    ]

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
    print("[LINT 3C] Universal Zero-Appearance Lint PASSED!", flush=True)

    for idx, u in enumerate(specs, start=1):
        sid = u["id"]
        ep_no = u["episode"]
        if u["wait_spark"]:
            ready_step_aux.wait()
        if spark_error:
            raise spark_error[0]
        tdir = TAKES[ep_no]
        sdir = tdir / sid
        final_mp4 = sdir / "video.mp4"
        print(f"[5090 3C {idx}/{len(specs)}] Generating {sid} ({u['duration']}s, seed={u['seed']}) ...", flush=True)
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
        print(f"[VAD 3C] {sid} -> status={vad_res['status']} vad={[(s, e) for s, e, _ in vad_res['vad_segments']]}", flush=True)

    spark_thread.join()
    print("PHASE 3C SNIPER PASS COMPLETE!", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
