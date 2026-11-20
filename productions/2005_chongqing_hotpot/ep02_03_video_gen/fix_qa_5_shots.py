#!/usr/bin/env python3
"""
Targeted QA fix for the 5 shots caught during full Episode 2 & Episode 3 multimodal review:
- Ep2 `2-1-13`: Fix [Shot 3] cross-scene bleed (no open-flame wok inside a courtyard dining table! Use 2-2-01_1k back-kitchen brick stove reference for [Shot 3]).
- Ep2 `2-2-04`: Fix [Shot 3] unnamed classmates borrowing 夏芊芊's black waiter apron (frame tight cheerful reaction on 苏晴 savoring crisp tripe at the window table without unnamed aproned clones).
- Ep2 `2-2-13`: Fix [Shot 2] modern stainless-steel fridge anachronism (anchor [Shot 2] to 2-2-07_1k wooden abacus counter so 叶寻 steps out from the authentic 2005 wooden counter!).
- Ep3 `3-1-09`: Fix prop continuity reversal (林双双 keeps the iron keys & kraft ledger clutched in her hand as she storms out the door, NOT tossing them back onto the table!).
- Ep3 `3-2-07`: Fix polyphone misread ("单摘" read as "山寨" -> change to "单独列出来了" matching natural spoken Chinese!).
Automatically uploads fixed clips -> Workstation auto-merges Ep 2 & Ep 3 clean films -> updates subtitle cues!
"""
import json
import subprocess
import sys
from pathlib import Path

SKILL_SCRIPTS = Path("/home/zhongwenyu/project/ai-director-train/.agents/skills/hit-video/scripts")
STUDIO_BRIDGE = Path("/home/zhongwenyu/project/playlets-studio/skills/studio-bridge/scripts")
WORK_DIR = Path("/home/zhongwenyu/project/ai-director-train/productions/2005_chongqing_hotpot/ep02_03_video_gen")
sys.path.insert(0, str(STUDIO_BRIDGE))
sys.path.insert(0, str(SKILL_SCRIPTS))
sys.path.insert(0, str(WORK_DIR))

import pika_runner  # noqa: E402
import run_ep02_03_pipeline as pipe  # noqa: E402

amap = json.loads((WORK_DIR / "asset_map.json").read_text(encoding="utf-8"))
ep2_plan = json.loads((WORK_DIR / "ep02_plan.json").read_text(encoding="utf-8"))
ep3_plan = json.loads((WORK_DIR / "ep03_plan.json").read_text(encoding="utf-8"))

STYLE_916 = (
    "The target video is shot in bright, crisp, high-contrast live-action cinema quality in vertical 9:16 framing, "
    "with natural skin texture, realistic fabric folds, accurate 35mm-50mm lens depth of field, and clear facial lighting; "
    "no CG look, no plastic beauty filter, no text overlays, captions, watermarks, or split-screen borders."
)
TAIL_GUARD = (
    "All movement happens at natural real-time speed. Keep every person's body, hands, limbs, and face anatomically stable; "
    "objects keep their exact shape and count; no person duplicates, merges, or changes identity."
)

# 1. Update 2-1-13 in ep2_plan
for sp in ep2_plan:
    if sp["id"] == "2-1-13":
        sp["ref_images"] = [
            str(WORK_DIR / "keyframes_1k/2-1-13_1k.png"),
            str(WORK_DIR / "keyframes_1k/2-2-01_1k.png"),
            amap["苏晴"]["main_1k"],
            amap["叶寻 · 渝清记围裙掌勺"]["main_1k"],
            amap["夏芊芊"]["main_1k"],
            amap["桂花巷渝清记大堂与天井"]["main_1k"],
        ]
        sp["prompt"] = f"""subject_definitions:
<Picture 1> is the first frame of [Shot 1], locking <Subject 1> standing beside the window table checking her wristwatch.
<Picture 2> is the composition reference for [Shot 3] inside the brick-stove back kitchen with spice jars on wooden shelves.
<Subject 1> is the person from <Picture 3>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 3>.
<Subject 2> is the person from <Picture 4>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 4>.
<Subject 3> is the person from <Picture 5>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 5>.
<Subject 4> is the dining hall from <Picture 6>.
All character sheets (<Picture 3>, <Picture 4>, <Picture 5>) provide 3D identity and outfit guidance only; never copy studio white backgrounds or multi-panel borders.
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).

summary:
[keyframe completion + reference generation + audio reference] Starting from <Picture 1> in <Subject 4>, <Subject 1> sits back down giving a ten-minute deadline, <Subject 2> and <Subject 3> walk through the cloth kitchen curtain, and inside the brick-stove kitchen of <Picture 2>, <Subject 3> sets a clean black clay casserole and fresh tripe plate on the wooden counter beside <Subject 2>.

retention_analysis:
<Picture 1> ([Shot 1] first frame): fully_preserved - [Shot 1] starts directly from <Picture 1>.
<Picture 2> ([Shot 3] back-kitchen reference): fully_preserved - [Shot 3] takes place strictly inside the brick-stove kitchen with spice-jar shelves, never in the dining hall.
<Subject 1> (appears in [Shot 1]): fully_preserved - exact identity and outfit from <Picture 3> are preserved.
<Subject 2> (appears in [Shot 2], [Shot 3]): fully_preserved - exact identity and outfit from <Picture 4> are preserved.
<Subject 3> (appears in [Shot 2], [Shot 3]): fully_preserved - exact identity and outfit from <Picture 5> are preserved.
<Subject 4> (appears in [Shot 1], [Shot 2]): fully_preserved - window table and kitchen curtain doorway remain consistent.
<Audio 1>: reference - <Subject 1> follows <Audio 1>'s voice timbre.

detailed_description:
{STYLE_916}
[Shot 1] Starting from <Picture 1> in <Subject 4>, a static medium-close shot frames <Subject 1> beside the 75cm-high wooden window table. Setting her canvas bag onto the table corner and sitting down onto the wooden bench during 0.1-3.8 seconds, <Subject 1> (S1) looks left-forward and speaks crisply: <d>[Chinese] 十分钟？行，耽误试麦我真走人。</d> Immediately upon finishing at 3.8 seconds, <Subject 1> closes her lips.
[Shot 2] At 00:04.000, the camera cuts to a medium tracking shot following <Subject 2> walking briskly across <Subject 4> toward the cloth-curtained kitchen doorway with <Subject 3> right behind him during 4.1-7.8 seconds; <Subject 2> pushes through the cloth curtain into the back kitchen, both silent with lips closed.
[Shot 3] At 00:08.000, the camera cuts strictly inside the enclosed brick-stove back kitchen of <Picture 2> (brick wok range on left, wooden prep counter and glass spice-jar shelves behind, zero dining tables): <Subject 2> stands at the brick iron wok gripping the long iron ladle on screen-left while <Subject 3> on screen-right sets a clean black clay casserole and a white plate of fresh dark beef tripe onto the wooden prep counter beside him during 8.1-12.0 seconds, exchanging a focused nod in silence. {TAIL_GUARD}

overall_soundscape:
Canvas bag placed on wood, brisk footsteps, cloth curtain swish, clay casserole placed on wooden prep counter, brick stove flame roar.

non_diegetic_music:
N/A"""

    elif sp["id"] == "2-2-04":
        sp["prompt"] = f"""subject_definitions:
<Picture 1> is the first frame of [Shot 1], locking <Subject 1> on screen-left handing the steaming black clay casserole tray to <Subject 2> on screen-right.
<Subject 1> is the person from <Picture 2>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 2>.
<Subject 2> is the person from <Picture 3>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 3>.
<Subject 3> is the person from <Picture 4>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 4>.
<Subject 4> is the back-kitchen prep area from <Picture 5>.
<Subject 5> is the warm dining hall window table from <Picture 6>.
All character sheets (<Picture 2>, <Picture 3>, <Picture 4>) provide 3D identity and outfit guidance only; never copy studio white backgrounds or multi-panel borders.
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).
<Audio 2> is the voice-timbre reference for <Subject 3> (S2).

summary:
[keyframe completion + reference generation + audio reference] Starting from <Picture 1> in <Subject 4>, <Subject 1> hands the steaming casserole tray to <Subject 2> to serve, <Subject 3> sips the broth at the window table in <Subject 5> and tests her crystal-clear singing voice, and <Subject 3> beams with delight picking up crisp beef tripe with bamboo chopsticks.

retention_analysis:
<Picture 1> ([Shot 1] first frame): fully_preserved - [Shot 1] starts directly from <Picture 1>.
<Subject 1> (appears in [Shot 1]): fully_preserved - exact identity and outfit from <Picture 2> are preserved.
<Subject 2> (appears in [Shot 1]): fully_preserved - exact identity and outfit from <Picture 3> are preserved.
<Subject 3> (appears in [Shot 2], [Shot 3]): fully_preserved - exact identity and outfit from <Picture 4> are preserved.
<Subject 4> (appears in [Shot 1]): fully_preserved - prep counter lighting remains consistent.
<Subject 5> (appears in [Shot 2], [Shot 3]): fully_preserved - wooden window table and warm evening bulbs remain consistent.
<Audio 1>: reference - <Subject 1> follows <Audio 1>'s voice timbre.
<Audio 2>: reference - <Subject 3> follows <Audio 2>'s voice timbre.

detailed_description:
{STYLE_916}
[Shot 1] Starting from <Picture 1> in <Subject 4>, a medium-close two-shot frames <Subject 1> on screen-left passing the wooden tray holding the steaming black clay casserole to <Subject 2> on screen-right. Immediately during 0.1-2.6 seconds, <Subject 1> (S1) speaks warmly: <d>[Chinese] 只是骨汤借味救急。芊芊姐，上菜。</d> <Subject 2> smiles with lips closed and turns briskly toward the dining hall.
[Shot 2] At 00:02.800, the camera cuts to a close-up at the 75cm-high window table of <Subject 5>, framing ONLY <Subject 3> seated behind the steaming black clay casserole filled with amber-white broth and dark sliced beef tripe. During 2.9-5.2 seconds, <Subject 3> sips half a porcelain spoonful of broth; her eyes light up in surprise and during 5.3-7.6 seconds <Subject 3> (S2) tests her throat with a crystal-clear vocal warmup: <d>[Chinese] 咪，嘛，咪。</d>
[Shot 3] At 00:07.800, the camera cuts to a lively medium-close solo shot of <Subject 3> at the window table (no extra people wearing restaurant workwear in frame) picking up bamboo chopsticks to lift a tender slice of dark beef tripe from the steaming black clay casserole. Beaming brightly toward her off-screen tablemates during 7.9-12.1 seconds, <Subject 3> (S2) speaks enthusiastically: <d>[Chinese] 真神了，嗓子清清亮亮的！快动筷，吃完赶得上排练！</d> Immediately upon finishing at 12.1 seconds, <Subject 3> closes her lips and happily tastes the crisp tripe until 13.0 seconds. {TAIL_GUARD}

overall_soundscape:
Wooden tray handoff, gentle spoon sip, crystal-clear vocal scale, bamboo chopsticks picking up tripe from simmering broth.

non_diegetic_music:
N/A"""

    elif sp["id"] == "2-2-13":
        sp["ref_images"] = [
            str(WORK_DIR / "keyframes_1k/2-2-13_1k.png"),
            str(WORK_DIR / "keyframes_1k/2-2-07_1k.png"),
            amap["林双双"]["main_1k"],
            amap["叶寻 · 渝清记围裙掌勺"]["main_1k"],
            amap["桂花巷渝清记大堂与天井"]["main_1k"],
        ]
        sp["prompt"] = f"""subject_definitions:
<Picture 1> is the first frame of [Shot 1], locking <Subject 1> standing arrogantly beside the doorway wooden table with the iron keys on the tabletop.
<Picture 2> is the antique wooden abacus counter reference for [Shot 2], locking the warm old wooden counter and traditional courtyard interior without any modern stainless-steel appliances.
<Subject 1> is the person from <Picture 3>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 3>.
<Subject 2> is the person from <Picture 4>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 4>.
<Subject 3> is the evening traditional wooden courtyard dining hall from <Picture 5>.
All character sheets (<Picture 3>, <Picture 4>) provide 3D identity and outfit guidance only; never copy studio white backgrounds or multi-panel borders.
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).

summary:
[keyframe completion + reference generation + audio reference] Starting from <Picture 1> in <Subject 3>, <Subject 1> coldly orders <Subject 2> to hand over the accounts within five minutes, and from the traditional wooden abacus counter of <Picture 2>, <Subject 2> steps calmly out into the wooden dining hall to face her head-on.

retention_analysis:
<Picture 1> ([Shot 1] first frame): fully_preserved - [Shot 1] starts directly from <Picture 1>.
<Picture 2> ([Shot 2] wooden counter reference): fully_preserved - [Shot 2] shows the warm antique wooden abacus counter and wooden rafters, with zero modern metal fridges.
<Subject 1> (appears in [Shot 1], [Shot 2]): fully_preserved - exact identity and outfit from <Picture 3> are preserved.
<Subject 2> (appears in [Shot 2]): fully_preserved - exact identity and outfit from <Picture 4> are preserved.
<Subject 3> (appears in [Shot 1], [Shot 2]): fully_preserved - warm tungsten courtyard wooden hall remains consistent.
<Audio 1>: reference - <Subject 1> follows <Audio 1>'s voice timbre.

detailed_description:
{STYLE_916}
[Shot 1] Starting from <Picture 1> in <Subject 3>, a static slightly low-angle close-up frames <Subject 1> on right-center holding the kraft ledger against her front with the iron key ring on the lower foreground table corner. Lifting her chin imperiously during 0.1-5.8 seconds, <Subject 1> (S1) speaks in an icy, commanding voice toward screen-left: <d>[Chinese] 叶寻，赵主厨明早到店，出来把林家肉菜账交接清楚——我只等你五分钟。</d> Immediately upon finishing at 5.8 seconds, <Subject 1> presses her lips shut.
[Shot 2] At 00:06.000, the camera cuts to an over-the-shoulder medium-close shot past <Subject 1>'s blurred right shoulder in the right foreground, looking toward the antique wooden abacus counter of <Picture 2> under warm wooden rafters in <Subject 3> (no modern stainless-steel kitchen equipment anywhere): <Subject 2> sets a dry cloth onto the wooden counter, steps calmly out from beside the wooden counter into the dining hall, and locks an unyielding gaze onto <Subject 1> in silence during 6.1-9.0 seconds with lips firmly closed. {TAIL_GUARD}

overall_soundscape:
Quiet tense evening room tone, cloth laid on wood, and steady footsteps on stone floor.

non_diegetic_music:
N/A"""

# 2. Update 3-1-09 and 3-2-07 in ep3_plan
for sp in ep3_plan:
    if sp["id"] == "3-1-09":
        sp["prompt"] = f"""subject_definitions:
<Picture 1> is the first frame of [Shot 1], locking <Subject 1> snatching the iron keys and kraft ledger off the wooden table into her right hand.
<Subject 1> is the person from <Picture 2>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 2>.
<Subject 2> is the person from <Picture 3>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 3>.
<Subject 3> is the person from <Picture 4>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 4>.
<Subject 4> is the night courtyard dining hall doorway from <Picture 5>.
All character sheets (<Picture 2>, <Picture 3>, <Picture 4>) provide 3D identity and outfit guidance only; never copy studio white backgrounds or multi-panel borders.
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).

summary:
[keyframe completion + reference generation + audio reference] Starting from <Picture 1> in <Subject 4>, <Subject 1> clutches the returned iron keys and kraft ledger tightly in her hand as she snaps a spiteful October eighth rent taunt, then carries both the keys and ledger out with her into the night while <Subject 2> and <Subject 3> calmly shut the wooden doors.

retention_analysis:
<Picture 1> ([Shot 1] first frame): fully_preserved - [Shot 1] starts directly from <Picture 1>.
<Subject 1> (appears in [Shot 1], [Shot 2]): fully_preserved - exact identity and outfit from <Picture 2> are preserved, and she keeps holding the keys and ledger as she leaves.
<Subject 2> (appears in [Shot 2]): fully_preserved - exact identity and outfit from <Picture 3> are preserved.
<Subject 3> (appears in [Shot 2]): fully_preserved - exact identity and outfit from <Picture 4> are preserved.
<Subject 4> (appears in [Shot 1], [Shot 2]): fully_preserved - wooden doors and bare wooden table corner remain consistent.
<Audio 1>: reference - <Subject 1> follows <Audio 1>'s voice timbre.

detailed_description:
{STYLE_916}
[Shot 1] Starting from <Picture 1> in <Subject 4>, a static close-up frames <Subject 1> lifting the iron key ring and kraft ledger off the bare wooden tabletop and clutching them tightly against her side (she never puts them back down on the table). Sneering coldly toward screen-left during 0.1-4.6 seconds, <Subject 1> (S1) snaps: <d>[Chinese] 行，我倒要看看十月八号你们拿什么交房租！</d> Immediately upon finishing at 4.6 seconds, <Subject 1> presses her lips shut while still gripping the keys and ledger.
[Shot 2] At 00:04.800, the camera cuts to a medium depth shot looking toward the open wooden doors (the wooden table corner in the lower foreground is now completely empty): still carrying the kraft ledger and iron keys in her hand, <Subject 1> turns sharply and strides out into the night courtyard during 4.9-6.8 seconds, while <Subject 2> and <Subject 3> step forward calmly and push the two wooden door leaves shut together during 6.8-9.0 seconds in silence. {TAIL_GUARD}

overall_soundscape:
Metallic jingle of iron keys held in hand, sharp departing footsteps into the night, and wooden doors creaking shut.

non_diegetic_music:
N/A"""

    elif sp["id"] == "3-2-07":
        sp["prompt"] = sp["prompt"].replace(
            "<d>[Chinese] 你把方子单摘出来了？</d>",
            "<d>[Chinese] 你把方子单独列出来了？</d>",
        )

for sp in ep2_plan + ep3_plan:
    errs = pika_runner.lint_zero_appearance(sp["prompt"], sp["id"])
    assert not errs, f"Lint failed: {errs}"

(WORK_DIR / "ep02_plan.json").write_text(json.dumps(ep2_plan, ensure_ascii=False, indent=2), encoding="utf-8")
(WORK_DIR / "ep03_plan.json").write_text(json.dumps(ep3_plan, ensure_ascii=False, indent=2), encoding="utf-8")

# Regenerate the 3 Ep2 shots
ep2_takes = WORK_DIR / "takes_ep02"
cache2 = ep2_takes / "inputs_1k"
for sp in ep2_plan:
    if sp["id"] in {"2-1-13", "2-2-04", "2-2-13"}:
        sid = sp["id"]
        sdir = ep2_takes / sid
        refs_1k = [pika_runner.ensure_1k_image(Path(p), cache2) for p in sp["ref_images"]]
        audios = [Path(p) for p in sp.get("ref_audios", [])]
        print(f"[QA-fix] Regenerating {sid} ({sp['duration']}s, 480p)...", flush=True)
        meta = pika_runner.call_pika_5090(
            sdir / "video.mp4", sp["prompt"], int(sp["duration"]), int(sp["seed"]) + 25,
            "9:16", "480p", refs_1k, audios
        )
        (sdir / "video.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

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

# Regenerate the 2 Ep3 shots
ep3_takes = WORK_DIR / "takes_ep03"
cache3 = ep3_takes / "inputs_1k"
for sp in ep3_plan:
    if sp["id"] in {"3-1-09", "3-2-07"}:
        sid = sp["id"]
        sdir = ep3_takes / sid
        refs_1k = [pika_runner.ensure_1k_image(Path(p), cache3) for p in sp["ref_images"]]
        audios = [Path(p) for p in sp.get("ref_audios", [])]
        print(f"[QA-fix] Regenerating {sid} ({sp['duration']}s, 480p)...", flush=True)
        meta = pika_runner.call_pika_5090(
            sdir / "video.mp4", sp["prompt"], int(sp["duration"]), int(sp["seed"]) + 25,
            "9:16", "480p", refs_1k, audios
        )
        (sdir / "video.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

ep3_cues = dict(pipe.EP3_CUES)
ep3_cues["3-2-07"] = [
    {"start": 0.2, "end": 3.2, "kind": "dialogue", "speaker": "叶寻", "text": "你把方子单独列出来了？"},
    {"start": 3.4, "end": 7.8, "kind": "dialogue", "speaker": "夏芊芊", "text": "叶爷爷留给你的家底，少写这一条，这字我不签。"},
    {"start": 8.1, "end": 11.8, "kind": "dialogue", "speaker": "夏建国", "text": "听芊芊的！来，摁手印！"},
]
pipe.upload_and_finalize_episode(3, pipe.EP3_ID, ep3_plan, ep3_takes, ep3_cues, pipe.EP3_BGM)
print("ALL 5 QA FIXES & AUTO-MERGES COMPLETE!", flush=True)
