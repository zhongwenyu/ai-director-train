#!/home/zhongwenyu/data/anaconda3/bin/python
"""
Single-shot closure for `1-3-01` (~3.5 mins total):
  1. Rebuild `1-3-01_shot3_aux` on Spark DIRECTLY from `1-3-01_2k.png` + `1-3-06_2k.png` + character front refs
     with ZERO garment words (preserving exact cream-yellow plaster wall & framed wall rules of `1-3-01_2k.png`,
     exact cream-beige suit & black patterned-shirt blazer of `1-3-06_2k.png`, zipper green backpack on wooden bench,
     and strictly ZERO white floor-standing air conditioner!).
  2. Regenerate `1-3-01` on 5090 (`15s`, clean 3-shot without 05s-08s extra transition shot, pouch stays inside bag).
  3. Re-upload & re-merge Episode 1 ONLY on Director Workstation (`publish_ep01_03_v7.py --upload-only --only-episodes 1`).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import onnxruntime as ort

SKILL_SCRIPTS = Path("/home/zhongwenyu/project/ai-director-train/.agents/skills/hit-video/scripts")
WORK_DIR = Path("/home/zhongwenyu/project/ai-director-train/productions/2005_chongqing_hotpot_v7/video_gen")
for p in (str(SKILL_SCRIPTS), str(WORK_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import check_audio_integrity as vad_gate  # noqa: E402
import pika_runner  # noqa: E402
from build_and_run_ep01_03_v7 import CLEAN_CAMERA, make_half_sec_strip  # noqa: E402
from spark_h3_image import generate_spark_h3_image  # noqa: E402

KF_2K = WORK_DIR / "keyframes_2k"
KF_1K = WORK_DIR / "keyframes_1k"
CACHE_1K = WORK_DIR / "cache_1k"
TAKES_EP1 = WORK_DIR / "takes_ep01"
DIAG_DIR = WORK_DIR / "diag_strips"


def main() -> int:
    amap = json.loads((WORK_DIR / "asset_map.json").read_text(encoding="utf-8"))
    vad_sess = ort.InferenceSession(str(vad_gate.DEFAULT_VAD_ONNX))

    f_ye_orig = amap["叶寻"]["front_1k"]
    f_lin = amap["林双双"]["front_1k"]
    f_chu = amap["楚南"]["front_1k"]
    v_lin = amap["林双双"]["voice"]

    print("[1/3] Generating costume-locked & room-locked 1-3-01_shot3_aux on Spark ...", flush=True)
    generate_spark_h3_image(
        prompt=(
            "The sunlit 2005 eatery hall with cream-yellow plaster upper walls, dark wooden lower wainscoting, wooden-framed wall signs, green ceiling fan, and open wooden front window in <Picture 1> is <Subject 1>. "
            "The three-person grouping and their exact outfits around the square wooden table in <Picture 2> are <Subject 2>. "
            "The young man in <Picture 3> is <Subject 3>. The young woman in <Picture 4> is <Subject 4>. The young man in <Picture 5> is <Subject 5>. "
            "The target image shows a medium three-shot around the square wooden table inside <Subject 1> preserving the EXACT cream-yellow plaster walls and framed wall signs of <Subject 1> (strictly ZERO white air conditioner anywhere!) and the EXACT outfits of <Picture 2>: "
            "on screen-left seated upright on the wooden bench with his zippered army-green canvas backpack resting on the wooden bench beside his thigh, <Subject 3> sits silent and guarded; "
            "standing right beside the center-right edge of the square wooden table (preserving her exact outfit in <Picture 2>), <Subject 4> leans slightly forward extending her open right palm toward <Subject 3>; "
            "seated on a wooden chair on screen-right (preserving his exact outfit in <Picture 2>), <Subject 5> holds a red cola can watching smugly. "
            "Crisp 35mm cinema photography, exact room and outfit continuity with <Picture 1> and <Picture 2>, zero air conditioner, zero text."
        ),
        out_path=KF_2K / "1-3-01_shot3_aux_2k.png",
        out_1k_path=KF_1K / "1-3-01_shot3_aux_1k.png",
        ref_images=[
            str(KF_2K / "1-3-01_2k.png"),
            str(KF_2K / "1-3-06_2k.png"),
            f_ye_orig,
            f_lin,
            f_chu,
        ],
        aspect_ratio="9:16",
        seed=9931,
        steps=6,
    )
    # Invalidate cached 1k copy in CACHE_1K so pika_runner re-reads the updated 1-3-01_shot3_aux_1k.png!
    for stale in CACHE_1K.glob("*1-3-01_shot3_aux*"):
        stale.unlink(missing_ok=True)

    spec = {
        "id": "1-3-01",
        "episode": 1,
        "duration": 15,
        "seed": 97301,
        "ref_images": [
            str(KF_1K / "1-3-01_1k.png"),
            str(KF_1K / "1-3-01_shot3_aux_1k.png"),
            f_ye_orig,
            f_lin,
            f_chu,
        ],
        "ref_audios": [v_lin],
        "prompt": (
            "[Subject]\n"
            "- <Subject 1>: The young man seated upright on the wooden bench on screen-left in <Picture 1> and <Picture 2>, matching <Picture 3>.\n"
            "- <Subject 2> (S1): The young woman standing beside the square wooden table in <Picture 2>, matching <Picture 4>. Voice matches Audio 1.\n"
            "- <Subject 3>: The young man seated with a red cola can on screen-right in <Picture 2>, matching <Picture 5>.\n"
            "[Shot]\n"
            "- [Shot 1] (0s-2.3s) Medium close-up framed strictly from <Picture 1> as <Subject 1> jolts awake and sits upright at the wooden table.\n"
            "- [Shot 2] (2.3s-4.3s) High-angle close-up on the zippered army-green canvas backpack resting on the wooden bench beside <Subject 1>'s leg (<Subject 1> only touches the twine-tied burlap pouch INSIDE the bag and leaves it inside the bag!).\n"
            "- [Shot 3] (4.3s-15.0s) Hard cut at 4.3s directly to the unbroken medium three-shot framed strictly from <Picture 2> (cream-yellow plaster wall with wooden-framed wall signs and green ceiling fan exactly as in <Picture 2>, zero white air conditioner; NO intermediate single shot between Shot 2 and <Picture 2>!).\n"
            "[Timeline]\n"
            "- [Shot 1] (0.1s-2.2s): <Subject 1> jolts upright from the wooden table and glances down at his backpack on the bench.\n"
            "- [Shot 2] (2.4s-4.2s): Reaching two fingers into the half-open zippered backpack, <Subject 1> briefly presses the burlap pouch INSIDE the backpack without lifting it out.\n"
            "- [Shot 3] (4.5s-10.4s): Framed strictly as <Picture 2>, immediately at 4.5s <Subject 2> (S1) extends her open palm across the square wooden table toward <Subject 1> and demands briskly: <d>[Chinese] 叶寻，发什么呆呢，赶紧把你爷爷那方子拿出来呀。</d> Right at 10.4s she closes her lips and glares impatiently for the remaining 4.6s while <Subject 1> sits silent.\n"
            "[Environment]\n- Sunlit 2005 Chongqing eatery hall (<Picture 1>, <Picture 2>) with cream-yellow plaster upper walls, framed wall signs, square wooden tables, and green ceiling fan (zero air conditioner).\n"
            f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
            "[Audio]\n- Ceiling fan hum, brief gasp, soft canvas touch, brisk complete female demand (4.5s-10.4s) followed by 4.6s quiet fan hum, zero music."
        ),
    }

    errs = pika_runner.lint_zero_appearance(spec["prompt"], "1-3-01")
    if errs:
        raise RuntimeError("\n".join(errs))
    print("[LINT] 1-3-01 Zero-Appearance Lint PASSED!", flush=True)

    plan_path = WORK_DIR / "ep01_v7_plan.json"
    ep1_plan = json.loads(plan_path.read_text(encoding="utf-8"))
    for item in ep1_plan:
        if item["id"] == "1-3-01":
            item["duration"] = spec["duration"]
            item["seed"] = spec["seed"]
            item["ref_images"] = spec["ref_images"]
            item["ref_audios"] = spec["ref_audios"]
            item["prompt"] = spec["prompt"]
    plan_path.write_text(json.dumps(ep1_plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("[2/3] Generating 1-3-01 on 5090 ...", flush=True)
    pika_runner.run_shot(spec, TAKES_EP1, CACHE_1K, resolution="480p", force=True)
    final_mp4 = TAKES_EP1 / "1-3-01" / "video.mp4"
    make_half_sec_strip(final_mp4, "1-3-01", DIAG_DIR / "1-3-01_0.5s.jpg")
    vad_res = vad_gate.audit_shot_audio(vad_sess, final_mp4, next(x for x in ep1_plan if x["id"] == "1-3-01"))
    print(f"[VAD] 1-3-01 -> status={vad_res['status']} vad={[(s, e) for s, e, _ in vad_res['vad_segments']]}", flush=True)

    print("[3/3] Re-publishing Episode 1 to Director Workstation ...", flush=True)
    subprocess.run(
        [
            sys.executable, "-u", str(WORK_DIR / "publish_ep01_03_v7.py"),
            "--upload-only", "--only-episodes", "1",
        ],
        check=True,
    )
    print("1-3-01 COSTUME & ROOM LOCK CLOSURE COMPLETE!", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
