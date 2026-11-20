#!/home/zhongwenyu/data/anaconda3/bin/python
"""
Phase 3D Final 3-Shot Closure (~6.5 mins):
  1. Exact hard-cut splice on `2-3-08` (frames 0..90 [0.000-3.792s] + frames 120..end [5.000-14.375s],
     cutting out the 1.2s pre-cut filler right at frame-120 hard cut `diff=67.28`).
  2. 1 Spark anchor (`1-3-01_shot3_aux`: 3-person table shot with authentic dark wooden wall panels behind Ye Xun,
     strictly ZERO white floor-standing AC, Lin Shuangshuang already standing right beside the table).
  3. 3 final 5090 shots (`1-1-04`, `3-2-08`, `1-3-01`).
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
from spark_h3_image import generate_spark_h3_image  # noqa: E402

ASSETS_1K = WORK_DIR / "assets_1k"
KF_2K = WORK_DIR / "keyframes_2k"
KF_1K = WORK_DIR / "keyframes_1k"
CACHE_1K = WORK_DIR / "cache_1k"
TAKES = {1: WORK_DIR / "takes_ep01", 2: WORK_DIR / "takes_ep02", 3: WORK_DIR / "takes_ep03"}
DIAG_DIR = WORK_DIR / "diag_strips"


def kf(stem: str) -> str:
    return str(KF_1K / f"{stem}_1k.png")


def splice_2_3_08_at_hard_cut() -> None:
    """Remove [3.7917s .. 5.0000s] right at exact Shot1->Shot2 hard cut (frame 120, t=5.0000s)."""
    mp4 = TAKES[2] / "2-3-08" / "video.mp4"
    bak = TAKES[2] / "2-3-08" / "video_pre_splice.mp4"
    if not bak.exists():
        bak.write_bytes(mp4.read_bytes())
    tmp = mp4.with_suffix(".spliced.mp4")
    filt = (
        "[0:v]trim=start_frame=0:end_frame=91,setpts=PTS-STARTPTS[v0];"
        "[0:v]trim=start_frame=120,setpts=PTS-STARTPTS[v1];"
        "[v0][v1]concat=n=2:v=1:a=0[v];"
        "[0:a]aresample=48000,atrim=0:3.791667,asetpts=PTS-STARTPTS,afade=t=out:st=3.73:d=0.06[a0];"
        "[0:a]aresample=48000,atrim=5.000000,asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.04[a1];"
        "[a0][a1]concat=n=2:v=0:a=1[a]"
    )
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-y", "-i", str(bak),
            "-filter_complex", filt, "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-crf", "15", "-preset", "fast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", str(tmp),
        ],
        check=True,
    )
    tmp.replace(mp4)
    make_half_sec_strip(mp4, "2-3-08", DIAG_DIR / "2-3-08_0.5s.jpg")
    print(f"[SPLICE] 2-3-08 spliced cleanly at frame-120 hard cut -> dur={check_transitions.probe_duration(mp4):.3f}s", flush=True)


def run_vo_and_clean_tail_3_2_08(
    base_mp4: Path,
    vocals_wav: Path,
    donor_street_mp4: Path,
    out_mp4: Path,
    ss: float,
    se: float,
    ratio: float,
    dst_start: float,
    tail_mute_start: float = 12.15,
) -> Dict[str, Any]:
    """Mix clean Ye Xun VO in [0..4.6s] AND replace [tail_mute_start..end] with pure quiet street room tone."""
    dur = check_transitions.probe_duration(base_mp4)
    raw_len = se - ss
    stretched = raw_len / ratio
    mute_end = dst_start + stretched + 0.08
    tmp = out_mp4.with_suffix(".vo3d.mp4")
    filt = (
        f"[0:a]aresample=48000,"
        f"volume=enable='between(t,0,{mute_end:.3f})+between(t,{tail_mute_start:.3f},{dur + 1:.3f})':volume=0.0[base];"
        f"[1:a]aresample=48000,atrim=start={ss:.3f}:end={se:.3f},asetpts=PTS-STARTPTS,"
        f"atempo={ratio:.4f},afade=t=in:d=0.03,afade=t=out:st={max(0.0, stretched - 0.05):.3f}:d=0.05,"
        f"adelay={int(round(dst_start * 1000))}|{int(round(dst_start * 1000))}[vo];"
        f"[2:a]aresample=48000,atrim=11.60:14.20,asetpts=PTS-STARTPTS,aloop=loop=2:size=120000,"
        f"atrim=0:{max(0.2, dur - tail_mute_start + 0.2):.3f},afade=t=in:d=0.08,volume=0.65,"
        f"adelay={int(round(tail_mute_start * 1000))}|{int(round(tail_mute_start * 1000))}[amb];"
        f"[base][vo][amb]amix=inputs=3:duration=first:dropout_transition=0:normalize=0[aout]"
    )
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-y", "-i", str(base_mp4), "-i", str(vocals_wav), "-i", str(donor_street_mp4),
            "-filter_complex", filt, "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(tmp),
        ],
        check=True,
    )
    tmp.replace(out_mp4)
    return {"dst_start": dst_start, "dst_end": round(dst_start + stretched, 3), "tail_mute_start": tail_mute_start}


def main() -> int:
    amap = json.loads((WORK_DIR / "asset_map.json").read_text(encoding="utf-8"))
    vad_sess = ort.InferenceSession(str(vad_gate.DEFAULT_VAD_ONNX))

    # 1. Instant exact hard-cut splice on 2-3-08
    splice_2_3_08_at_hard_cut()
    plans = {
        ep_no: json.loads((WORK_DIR / f"ep0{ep_no}_v7_plan.json").read_text(encoding="utf-8"))
        for ep_no in (1, 2, 3)
    }
    p2308 = next(x for x in plans[2] if x["id"] == "2-3-08")
    vad_2308 = vad_gate.audit_shot_audio(vad_sess, TAKES[2] / "2-3-08" / "video.mp4", p2308)
    print(f"[VAD 3D] 2-3-08 (spliced) -> status={vad_2308['status']} vad={[(s, e) for s, e, _ in vad_2308['vad_segments']]}", flush=True)

    v_lin = amap["林双双"]["voice"]
    v_chu = amap["楚南"]["voice"]
    v_zhao = amap["赵帆"]["voice"]

    f_ye_2020 = amap["叶寻 · 2020研发总厨白服"]["front_1k"]
    f_chu_exec = amap["楚南 · 海归并购总监西装"]["front_1k"]
    f_ye_orig = amap["叶寻"]["front_1k"]
    f_ye_bare = str(ASSETS_1K / "ye_bare_wrist_front_1k.png")
    f_lin = amap["林双双"]["front_1k"]
    f_chu = amap["楚南"]["front_1k"]
    f_zhao = amap["赵帆"]["front_1k"]
    f_jian = amap["夏建国"]["front_1k"]
    sc_lin_hall = amap["沙正街林家食府老店大堂"]["main_1k"]

    ready_1301_aux = threading.Event()
    spark_error: List[BaseException] = []

    def spark_worker() -> None:
        try:
            t0 = time.time()
            print("[Spark 3D 1/1] Generating 1-3-01_shot3_aux (authentic wooden left wall, zero AC) ...", flush=True)
            generate_spark_h3_image(
                prompt=(
                    "The sunlit 2005 traditional Chongqing eatery hall with dark weathered wooden wall panels, wooden columns, square wooden tables, and green ceiling fan (strictly ZERO modern white floor-standing air conditioner anywhere!) in <Picture 1> is <Subject 1>. "
                    "The young man in dark-blue jacket and white t-shirt in <Picture 2> is <Subject 2>. "
                    "The young woman in pink cardigan in <Picture 3> is <Subject 3>. "
                    "The young man in dark casual blazer in <Picture 4> is <Subject 4>. "
                    "The target image shows a medium three-shot inside <Subject 1> around a square wooden table: "
                    "on screen-left seated upright on a wooden bench in front of dark weathered wooden wall wainscoting (strictly NO white cabinet or air conditioner behind him!), <Subject 2> sits guardedly with his half-open army-green canvas backpack beside his leg; "
                    "standing right beside the right edge of the square wooden table, <Subject 3> leans slightly forward extending her open right palm toward <Subject 2> demanding something; "
                    "on far screen-right seated on a wooden chair beside the table, <Subject 4> holds a red soda can watching smugly. "
                    "Crisp 35mm cinema photography, authentic 2005 wooden interior, zero modern white air conditioner, zero text."
                ),
                out_path=KF_2K / "1-3-01_shot3_aux_2k.png",
                out_1k_path=KF_1K / "1-3-01_shot3_aux_1k.png",
                ref_images=[sc_lin_hall, f_ye_orig, f_lin, f_chu],
                aspect_ratio="9:16",
                seed=9901,
                steps=6,
            )
            print(f"[Spark 3D 1/1] DONE 1-3-01_shot3_aux in {time.time() - t0:.1f}s", flush=True)
            ready_1301_aux.set()
        except BaseException as exc:
            spark_error.append(exc)
            ready_1301_aux.set()
            raise

    spark_thread = threading.Thread(target=spark_worker, daemon=True)
    spark_thread.start()

    specs: List[Dict[str, Any]] = [
        {
            "id": "1-1-04", "episode": 1, "duration": 15, "seed": 91105, "wait_spark": False,
            "ref_images": [kf("1-1-04"), kf("1-1_master_4p"), f_ye_2020, f_chu_exec, f_zhao],
            "ref_audios": [v_chu, v_zhao],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The man standing silently on screen-left in <Picture 1>, matching <Picture 3>.\n"
                "- <Subject 2> (S1): The executive man on screen-right in <Picture 1>, matching <Picture 4>. Voice matches Audio 1.\n"
                "- <Subject 3> (S2): The Western-style chef holding the white gold-trimmed ceremonial cap on far right in <Picture 2>, matching <Picture 5>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-2.2s) Medium shot framed from <Picture 1> beside the leather chair and cylindrical floor trash bin.\n"
                "- [Shot 2] (2.2s-7.0s) Medium close-up favoring <Subject 2> on screen-right beside the bare round grey marble table (do NOT cut to <Subject 3> before 7.0s!).\n"
                "- [Shot 3] (7.0s-15.0s) Close-up inside <Picture 2> on <Subject 3> holding the white gold-trimmed ceremonial cap.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-2.1s): In complete vocal silence, <Subject 2> pinches the faded cloth off the chair back and drops it straight down INSIDE the cylindrical floor trash bin.\n"
                "- [Shot 2] (2.4s-6.7s): Starting cleanly with '老叶' at 2.4s (zero filler syllables before '老叶'), <Subject 2> (S1) sneers at screen-left: <d>[Chinese] 老叶，上市得讲门面，你那套土锅底，早该翻篇了。</d> He closes his mouth at 6.7s.\n"
                "- [Shot 3] (7.2s-12.2s): Immediately at 7.2s, <Subject 3> (S2) pats the ceremonial cap at his chest and boasts clearly: <d>[Chinese] 往后店里主打法式鹅肝融火锅，只接高档客。</d> Right at 12.2s he closes his mouth into a proud smirk for the remaining 2.8s.\n"
                "[Environment]\n- Luxury rooftop VIP room (<Picture 2>) with round grey marble table and night skyline window.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Soft cloth drop into bin, arrogant male sneer (2.4s-6.7s), proud male boast finishing completely by 12.2s followed by 2.8s quiet room tone, zero extra words, zero music."
            ),
        },
        {
            "id": "3-2-08", "episode": 3, "duration": 15, "seed": 96208, "wait_spark": False,
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
                "- [Shot 1] (0s-4.5s) Unbroken 4.5-second slow push-in close-up framed strictly on <Picture 1> (<Subject 1> alone on the stone steps with closed motionless lips; DO NOT cut before 00:04.500!).\n"
                "- [Shot 2] (4.5s-12.3s) Long 7.8-second medium close-up framed strictly from <Picture 2> keeping the camera on <Subject 2> the ENTIRE time until he finishes his full megaphone announcement and lowers the megaphone at 11.8s (DO NOT cut to <Picture 3> before 12.3s!).\n"
                "- [Shot 3] (12.3s-15.0s) Brief 2.7-second silent reaction medium three-shot framed strictly from <Picture 3> showing ONLY <Subject 1> (empty hands), <Subject 3> (hugging closed brown ledger), and <Subject 4> (clenching fists in silent anger with closed mouth).\n"
                "[Timeline]\n"
                "- [Shot 1] (0.0s-4.4s): <Subject 1> watches across the street in complete vocal silence with closed lips.\n"
                "- [Shot 2] (4.7s-11.6s): Keeping the megaphone raised to his mouth in <Picture 2> for the entire sentence, <Subject 2> (S1) shouts clearly once: <d>[Chinese] 喂，半个月后我们塞纳河畔西餐厅开业，对门冷锅冷灶的趁早关张吧。</d> Only after finishing '关张吧' at 11.6s does he lower the megaphone with closed mouth.\n"
                "- [Shot 3] (12.4s-15.0s): In complete silence (<Subject 1>, <Subject 3>, and <Subject 4> all keep closed mouths, zero speech, zero applause), <Subject 4> clenches his fists glaring across the lane.\n"
                "[Environment]\n- Sunlit Chongqing bluestone street.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Quiet street air (0.0s-4.5s), one complete clear megaphone shout (4.7s-11.6s), quiet street air (11.7s-15.0s), strictly zero repeat voice, zero clapping, zero music."
            ),
        },
        {
            "id": "1-3-01", "episode": 1, "duration": 15, "seed": 96301, "wait_spark": True,
            "ref_images": [kf("1-3-01"), kf("1-3-01_shot3_aux"), f_ye_orig, f_lin, f_chu],
            "ref_audios": [v_lin],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The young man seated upright on the wooden bench on screen-left in <Picture 1> and <Picture 2>, matching <Picture 3>.\n"
                "- <Subject 2> (S1): The young woman already standing right beside the square wooden table extending her palm in <Picture 2>, matching <Picture 4>. Voice matches Audio 1.\n"
                "- <Subject 3>: The young man seated with a red soda can on screen-right in <Picture 2>, matching <Picture 5>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-2.3s) Medium close-up framed from <Picture 1> as <Subject 1> jolts awake and sits upright.\n"
                "- [Shot 2] (2.3s-4.2s) High-angle close-up on the half-open army-green canvas backpack beside <Subject 1>'s leg.\n"
                "- [Shot 3] (4.2s-15.0s) Medium three-shot framed strictly from <Picture 2> (dark weathered wooden wall panels behind <Subject 1> exactly as in <Picture 2>, zero white cabinet or air conditioner; <Subject 2> is ALREADY standing stationary beside the table).\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-2.2s): <Subject 1> jolts upright from the wooden table and reaches down toward his backpack.\n"
                "- [Shot 2] (2.4s-4.1s): <Subject 1>'s right hand squeezes the twine-tied herb bundle INSIDE the half-open backpack without removing it.\n"
                "- [Shot 3] (4.4s-10.2s): Already standing stationary right beside the wooden table as in <Picture 2>, immediately at 4.4s without walking or waiting, <Subject 2> (S1) holds out her open palm toward seated <Subject 1> and demands briskly: <d>[Chinese] 叶寻，发什么呆呢，赶紧把你爷爷那方子拿出来呀。</d> Right at 10.2s she closes her lips and glares impatiently for the remaining 4.8s while <Subject 1> sits silent.\n"
                "[Environment]\n- Sunlit 2005 weathered wooden eatery hall (<Picture 2>) with dark wood walls and green ceiling fan, zero modern appliances.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Ceiling fan hum, brief gasp, canvas rustle, immediate brisk complete female demand (4.4s-10.2s) followed by 4.8s quiet fan hum, zero music."
            ),
        },
    ]

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
    print("[LINT 3D] Universal Zero-Appearance Lint PASSED!", flush=True)

    for idx, u in enumerate(specs, start=1):
        sid = u["id"]
        ep_no = u["episode"]
        if u["wait_spark"]:
            ready_1301_aux.wait()
        if spark_error:
            raise spark_error[0]
        tdir = TAKES[ep_no]
        sdir = tdir / sid
        final_mp4 = sdir / "video.mp4"
        print(f"[5090 3D {idx}/{len(specs)}] Generating {sid} ({u['duration']}s, seed={u['seed']}) ...", flush=True)
        if "vo_reuse" in u:
            vr = u["vo_reuse"]
            base_mp4 = sdir / "video_base.mp4"
            refs_1k = [pika_runner.ensure_1k_image(Path(p), CACHE_1K) for p in u["ref_images"]]
            audios = [Path(p) for p in u.get("ref_audios", [])]
            meta = pika_runner.call_pika_5090(
                base_mp4, u["prompt"], int(u["duration"]), int(u["seed"]), "9:16", "480p", refs_1k, audios
            )
            vo_info = run_vo_and_clean_tail_3_2_08(
                base_mp4, Path(vr["vocals"]), TAKES[3] / "3-2-23" / "video.mp4", final_mp4,
                vr["ss"], vr["se"], vr["ratio"], vr["dst_start"], tail_mute_start=12.25,
            )
            meta["vo_custom_applied"] = vo_info
            (sdir / "video.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        else:
            pika_runner.run_shot(u, tdir, CACHE_1K, resolution="480p", force=True)

        make_half_sec_strip(final_mp4, sid, DIAG_DIR / f"{sid}_0.5s.jpg")
        plan_entry = next(x for x in plans[ep_no] if x["id"] == sid)
        vad_res = vad_gate.audit_shot_audio(vad_sess, final_mp4, plan_entry)
        print(f"[VAD 3D] {sid} -> status={vad_res['status']} vad={[(s, e) for s, e, _ in vad_res['vad_segments']]}", flush=True)

    spark_thread.join()
    print("PHASE 3D FINAL 3-SHOT CLOSURE COMPLETE!", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
