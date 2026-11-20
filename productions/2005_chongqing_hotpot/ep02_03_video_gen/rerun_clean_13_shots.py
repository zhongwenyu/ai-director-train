#!/usr/bin/env python3
"""
1. Upgrade build_ep02_03_video_plan.py to strip all `(中文名 in Picture N ...):` stage directions out of <d>...</d>
   and add +1s tail buffers on 2-1-04, 2-1-10, 2-2-01, 3-2-01, 3-2-07.
2. Re-mix 2-1-07 (VO in [Shot 3] 6.90..10.92s) and 3-2-04 (compact VO 9.25..13.95s) immediately.
3. Re-generate the 13 clean-<d> 480p shots on 5090, apply clean VO slice on 2-2-01 (stripping 0..0.85s),
   re-upload updated Episode 2 & Episode 3 videos to Workstation -> verify automatic Episode 2 & Episode 3
   film merges -> re-compile & bind separated BGM + WebVTT subtitles!
"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

SKILL_DIR = Path("/home/zhongwenyu/project/ai-director-train/.agents/skills/hit-video")
SKILL_SCRIPTS = SKILL_DIR / "scripts"
STUDIO_BRIDGE = Path("/home/zhongwenyu/project/playlets-studio/skills/studio-bridge/scripts")
sys.path.insert(0, str(STUDIO_BRIDGE))
sys.path.insert(0, str(SKILL_SCRIPTS))

import pika_runner  # noqa: E402
from post_bgm_subtitles import compile_post_pack  # noqa: E402

WORK_DIR = Path("/home/zhongwenyu/project/ai-director-train/productions/2005_chongqing_hotpot/ep02_03_video_gen")
sys.path.insert(0, str(WORK_DIR))
import run_ep02_03_pipeline as pipe  # noqa: E402


def clean_plan_source():
    p = WORK_DIR / "build_ep02_03_video_plan.py"
    txt = p.read_text(encoding="utf-8")

    # Replace `<d>[Chinese] (Name in Picture K ...): LINE</d>` -> `<d>[Chinese] LINE</d>`
    txt_new, n = re.subn(
        r"<d>\[Chinese\]\s*\([^)]*\)\s*:\s*(.*?)</d>",
        r"<d>[Chinese] \1</d>",
        txt,
    )
    print(f"Cleaned {n} <d> tags in build_ep02_03_video_plan.py", flush=True)

    # Add +1s tail buffer on the 5 tight-ending shots
    bumps = [
        ('"id": "2-1-04",\n        "shot_uuid": ep2_shots[1]["id"],\n        "aspect_ratio": "9:16",\n        "duration": 14,',
         '"id": "2-1-04",\n        "shot_uuid": ep2_shots[1]["id"],\n        "aspect_ratio": "9:16",\n        "duration": 15,'),
        ("during 13.4-14.0 seconds.", "during 13.4-15.0 seconds."),
        ('"id": "2-1-10",\n        "shot_uuid": ep2_shots[3]["id"],\n        "aspect_ratio": "9:16",\n        "duration": 12,',
         '"id": "2-1-10",\n        "shot_uuid": ep2_shots[3]["id"],\n        "aspect_ratio": "9:16",\n        "duration": 13,'),
        ("until 12.0 seconds.", "until 13.0 seconds."),
        ('"id": "2-2-01",\n        "shot_uuid": ep2_shots[5]["id"],\n        "aspect_ratio": "9:16",\n        "duration": 12,',
         '"id": "2-2-01",\n        "shot_uuid": ep2_shots[5]["id"],\n        "aspect_ratio": "9:16",\n        "duration": 13,'),
        ('"id": "3-2-01",\n        "shot_uuid": ep3_shots[4]["id"],\n        "aspect_ratio": "9:16",\n        "duration": 14,',
         '"id": "3-2-01",\n        "shot_uuid": ep3_shots[4]["id"],\n        "aspect_ratio": "9:16",\n        "duration": 15,'),
        ("until 14.0 seconds.", "until 15.0 seconds."),
        ('"id": "3-2-07",\n        "shot_uuid": ep3_shots[6]["id"],\n        "aspect_ratio": "9:16",\n        "duration": 12,',
         '"id": "3-2-07",\n        "shot_uuid": ep3_shots[6]["id"],\n        "aspect_ratio": "9:16",\n        "duration": 13,'),
    ]
    for old, new in bumps:
        txt_new = txt_new.replace(old, new)

    p.write_text(txt_new, encoding="utf-8")
    subprocess.run(["python3", str(p)], check=True)


def fix_existing_vos():
    # 1. 2-1-07: place clean VO in [Shot 3] (6.90..10.92s)
    d2107 = WORK_DIR / "takes_ep02/2-1-07"
    pika_runner.place_vo_segments(
        d2107 / "video_novo.mp4",
        d2107 / "vo_short_368p.mp4",
        segments=[
            (0.55, 1.90, 6.90),   # 账上只剩六千二， (6.90..8.25)
            (2.25, 4.82, 8.35),   # 楚南挖走厨子就是想逼死夏家。 (8.35..10.92)
        ],
        out_mp4=d2107 / "video.mp4",
        base_duck=0.25,
        vo_gain=1.45,
        raw_slice=True,
    )
    print("[vo-fix] Re-mixed 2-1-07 VO into [Shot 3] (6.90..10.92s)!", flush=True)

    # 2. 3-2-04: compact pauses + gentle atempo=1.14 so full line lands 9.25..13.90s (<14.40s!)
    d3204 = WORK_DIR / "takes_ep03/3-2-04"
    compact_wav = d3204 / "vo_compact_fit.wav"
    filt = (
        "[0:a]atrim=0.18:2.52,asetpts=PTS-STARTPTS[a0];"
        "[0:a]atrim=3.10:3.70,asetpts=PTS-STARTPTS[a1];"
        "[0:a]atrim=4.02:6.28,asetpts=PTS-STARTPTS[a2];"
        "[a0][a1][a2]concat=n=3:v=0:a=1,atempo=1.14[out]"
    )
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-i", str(d3204 / "vo_short_368p.mp4"),
        "-filter_complex", filt, "-map", "[out]", "-ar", "48000", "-ac", "2", str(compact_wav)
    ], check=True)
    dur = float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(compact_wav)],
        text=True
    ).strip())
    pika_runner.place_vo_segments(
        d3204 / "video_novo.mp4",
        compact_wav,
        segments=[(0.0, dur, 9.25)],
        out_mp4=d3204 / "video.mp4",
        base_duck=0.20,
        vo_gain=1.45,
        raw_slice=True,
    )
    print(f"[vo-fix] Re-mixed 3-2-04 VO cleanly into [9.25s .. {9.25+dur:.2f}s]!", flush=True)


def regen_13_shots():
    ep2_plan = json.loads((WORK_DIR / "ep02_plan.json").read_text(encoding="utf-8"))
    ep3_plan = json.loads((WORK_DIR / "ep03_plan.json").read_text(encoding="utf-8"))

    rerun_ep2 = {"2-1-01", "2-1-04", "2-1-10", "2-1-13", "2-2-01", "2-2-04", "2-2-07", "2-2-13"}
    rerun_ep3 = {"3-1-04", "3-1-07", "3-1-09", "3-2-01", "3-2-07"}

    # Episode 2
    ep2_takes = WORK_DIR / "takes_ep02"
    cache2 = ep2_takes / "inputs_1k"
    for sp in ep2_plan:
        sid = sp["id"]
        if sid not in rerun_ep2:
            continue
        sdir = ep2_takes / sid
        refs_1k = [pika_runner.ensure_1k_image(Path(p), cache2) for p in sp["ref_images"]]
        audios = [Path(p) for p in sp.get("ref_audios", [])]
        target_mp4 = sdir / ("video_novo.mp4" if sid == "2-2-01" else "video.mp4")
        print(f"[5090-clean] Regenerating {sid} ({sp['duration']}s, 480p)...", flush=True)
        meta = pika_runner.call_pika_5090(
            target_mp4, sp["prompt"], int(sp["duration"]), int(sp["seed"]) + 10,
            "9:16", "480p", refs_1k, audios
        )
        if sid == "2-2-01":
            # Place clean VO slices [0.85..2.08], [2.36..3.55], [4.02..6.38] stripping "叶寻，"
            pika_runner.place_vo_segments(
                target_mp4,
                sdir / "vo_short_368p.mp4",
                segments=[
                    (0.85, 2.08, 0.50),   # 0.50..1.73 鲜梨汁化牛油，
                    (2.36, 3.55, 1.85),   # 1.85..3.04 温醪糟退椒燥，
                    (4.02, 6.38, 3.18),   # 3.18..5.54 辣香入魂却半点不呛嗓。
                ],
                out_mp4=sdir / "video.mp4",
                base_duck=0.28,
                vo_gain=1.45,
                raw_slice=True,
            )
        (sdir / "video.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        subprocess.run(["python3", str(SKILL_SCRIPTS / "inspect_video.py"), "--outdir", str(sdir / "inspect"), str(sdir / "video.mp4")], check=True)

    # Update 2-1-07 VO cue window in EP2_CUES
    ep2_cues = dict(pipe.EP2_CUES)
    ep2_cues["2-1-07"] = [
        {"start": 0.2, "end": 3.8, "kind": "caption", "text": "夏家小馆存折余额：6,200元"},
        {"start": 4.1, "end": 6.6, "kind": "dialogue", "speaker": "夏芊芊", "text": "九百块点清，不送。"},
        {"start": 6.9, "end": 10.9, "kind": "vo", "speaker": "叶寻", "text": "账上只剩六千二，楚南挖走厨子就是想逼死夏家。"},
    ]
    ep2_cues["2-2-01"] = [
        {"start": 0.5, "end": 5.6, "kind": "vo", "speaker": "叶寻", "text": "鲜梨汁化牛油，温醪糟退椒燥，辣香入魂却半点不呛嗓。"},
        {"start": 8.0, "end": 11.8, "kind": "dialogue", "speaker": "夏建国", "text": "温醪糟退椒燥……这是叶老爷子的绝活！"},
    ]
    pipe.upload_and_finalize_episode(2, pipe.EP2_ID, ep2_plan, ep2_takes, ep2_cues, pipe.EP2_BGM)

    # Episode 3
    ep3_takes = WORK_DIR / "takes_ep03"
    cache3 = ep3_takes / "inputs_1k"
    for sp in ep3_plan:
        sid = sp["id"]
        if sid not in rerun_ep3:
            continue
        sdir = ep3_takes / sid
        refs_1k = [pika_runner.ensure_1k_image(Path(p), cache3) for p in sp["ref_images"]]
        audios = [Path(p) for p in sp.get("ref_audios", [])]
        print(f"[5090-clean] Regenerating {sid} ({sp['duration']}s, 480p)...", flush=True)
        meta = pika_runner.call_pika_5090(
            sdir / "video.mp4", sp["prompt"], int(sp["duration"]), int(sp["seed"]) + 10,
            "9:16", "480p", refs_1k, audios
        )
        (sdir / "video.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        subprocess.run(["python3", str(SKILL_SCRIPTS / "inspect_video.py"), "--outdir", str(sdir / "inspect"), str(sdir / "video.mp4")], check=True)

    pipe.upload_and_finalize_episode(3, pipe.EP3_ID, ep3_plan, ep3_takes, pipe.EP3_CUES, pipe.EP3_BGM)
    print("\nALL 13 CLEAN-<d> REGENERATIONS & EP2-3 AUTO-MERGES COMPLETE!", flush=True)


if __name__ == "__main__":
    for dst in (
        Path("/home/zhongwenyu/project/ai-director-workstation/skills/hit-video"),
        Path("/home/zhongwenyu/project/playlets-studio/skills/hit-video"),
        Path("/home/zhongwenyu/project/playlets-studio/playlets/playlet-mwj57ecn-9658ad48/skills/hit-video"),
    ):
        subprocess.run(["rsync", "-a", "--delete", f"{SKILL_DIR}/", f"{dst}/"], check=True)
    clean_plan_source()
    fix_existing_vos()
    regen_13_shots()
