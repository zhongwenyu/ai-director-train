#!/usr/bin/env python3
"""Parallel regeneration for optimized Episode 1 script (v3):
- 5090 (480p Pika-H3-Flex):
  1) 1-2-01 (10s): Pre-Impact headlight flash close-up -> Post-Impact Aftermath (1-2-01_aftermath_1k.png)
  2) 1-4-01 (14s): Initial-Presence solo keyframe (1-4-01_solo_1k.png) -> Ye Xun rushes in from screen-left at t=0.8s
- 4070 Ti SUPER (368p Pika-H3-Flex VO lane, running concurrently!):
  Generates Ye Xun's 4 new inner-monologue [VO] tracks (1-1-01, 1-3-01, 1-3-07, 1-4-01),
  and mixes all 5 [VO] tracks (including verified 1-2-01 VO) cleanly onto the silent-mouth visual masters!
"""
import json
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

STUDIO_BRIDGE = Path("/home/zhongwenyu/project/playlets-studio/skills/studio-bridge/scripts")
SKILL_SCRIPTS = Path("/home/zhongwenyu/project/ai-director-train/.agents/skills/hit-video/scripts")
sys.path.insert(0, str(STUDIO_BRIDGE))
sys.path.insert(0, str(SKILL_SCRIPTS))

import vo_split  # noqa: E402
from pika_runner import call_pika_5090, ensure_1k_image, lint_zero_appearance, mix_vo_upgraded  # noqa: E402

WORK_DIR = Path("/home/zhongwenyu/project/ai-director-train/productions/2005_chongqing_hotpot/ep01_video_gen")
TAKES_R1 = WORK_DIR / "takes_r1"
TAKES_V3 = WORK_DIR / "takes_v3"
CACHE_1K = TAKES_V3 / "inputs_1k"
CACHE_1K.mkdir(parents=True, exist_ok=True)

asset_map = json.loads((WORK_DIR / "ep01_asset_map.json").read_text(encoding="utf-8"))
old_plan = json.loads((WORK_DIR / "ep01_video_plan.json").read_text(encoding="utf-8"))
plan_by_id = {s["id"]: s for s in old_plan}

# Copy already-validated unchanged shots into takes_v3
UNCHANGED = ["1-1-04", "1-1-07", "1-1-10", "1-3-04", "1-3-10", "1-3-13", "1-4-04"]
for sid in UNCHANGED:
    dst = TAKES_V3 / sid
    dst.mkdir(parents=True, exist_ok=True)
    if not (dst / "video.mp4").is_file():
        shutil.copy2(TAKES_R1 / sid / "video.mp4", dst / "video.mp4")
        shutil.copy2(TAKES_R1 / sid / "video.json", dst / "video.json")

# Also copy silent visual bases for 1-1-01, 1-3-01, 1-3-07 so we add VO cleanly onto them
for sid in ["1-1-01", "1-3-01", "1-3-07"]:
    dst = TAKES_V3 / sid
    dst.mkdir(parents=True, exist_ok=True)
    if not (dst / "video_novo.mp4").is_file():
        shutil.copy2(TAKES_R1 / sid / "video.mp4", dst / "video_novo.mp4")
        shutil.copy2(TAKES_R1 / sid / "video.json", dst / "video_novo.json")

STYLE_916 = (
    "The target video is shot in bright, crisp, high-contrast live-action cinema quality in vertical 9:16 framing, "
    "with natural skin texture, realistic fabric folds, accurate 35mm-50mm lens depth of field, and clear facial lighting; "
    "no CG look, no plastic beauty filter, no text overlays, captions, watermarks, or split-screen borders."
)
TAIL_GUARD = (
    "All movement happens at natural real-time speed. Keep every person's body, hands, limbs, and face anatomically stable; "
    "objects keep their exact shape and count; no person duplicates, merges, or changes identity."
)


def main_1k(name: str) -> Path:
    return ensure_1k_image(Path(asset_map[name]["main_1k"]), CACHE_1K)


def kf_1k(name: str) -> Path:
    return ensure_1k_image(WORK_DIR / "keyframes_1k" / f"{name}_1k.png", CACHE_1K)


def voice(name: str) -> Path:
    return Path(asset_map[name]["voice_wav"])


# --- 1. New 5090 Visual Prompt for 1-2-01 (10s: Pre-Impact flash -> Post-Impact Aftermath keyframe!) ---
PROMPT_1201_NOVO = f"""subject_definitions:
<Picture 1> is the first frame of [Shot 1], locking the rainy night street framing outside the revolving glass doors.
<Picture 2> is the aftermath keyframe of [Shot 4], locking the post-crash ground composition where the unconscious arm and tumbled grey canvas knife roll lie motionless in the rain puddle beside the stopped car wheel and red-and-white lights.
<Subject 1> is the person from <Picture 3>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 3> without modification.
<Subject 2> is the rain-slicked corporate plaza entrance at night from <Picture 4>, preserving its warm-lit revolving glass doors and wet asphalt reflections.
All character sheets (<Picture 3>) provide 3D identity and outfit guidance only; never copy studio white backgrounds or multi-panel borders.

summary:
[keyframe completion + reference generation] Starting from <Picture 1> in <Subject 2>, rain-drenched <Subject 1> walks silently into the downpour clutching a grey canvas knife roll, clenches his burn-scarred hand in the rain, flinches as blinding headlights swallow his face in [Shot 3], and [Shot 4] cuts to the post-impact aftermath anchored by <Picture 2>.

retention_analysis:
<Picture 1> ([Shot 1] first frame): fully_preserved - [Shot 1] starts directly from <Picture 1>.
<Picture 2> ([Shot 4] aftermath keyframe): fully_preserved - [Shot 4] matches <Picture 2>'s ground-level post-crash puddle composition.
<Subject 1> (appears in [Shot 1], [Shot 2], [Shot 3], [Shot 4]): fully_preserved - exact identity and wet outfit from <Picture 3> are maintained.
<Subject 2> (appears in [Shot 1], [Shot 2], [Shot 3], [Shot 4]): fully_preserved - wet asphalt reflections and night rain remain consistent.

detailed_description:
{STYLE_916}
[Shot 1] Starting from <Picture 1>, a static eye-level medium-wide shot in <Subject 2> shows torrential night rain pouring outside the glowing revolving glass doors at left-rear. <Subject 1>, soaked by rain and clutching a rolled dark-grey canvas knife bundle tightly against his chest with both arms, steps down off the curb from screen-left toward center-right during 0.0-2.4 seconds, splashing through reflective puddles with a hollow expression and lips completely closed and still.
[Shot 2] At 00:02.400, the camera cuts to a static high-angle close-up on <Subject 1>'s rain-drenched right hand gripping the cord of the dark-grey canvas knife roll against his chest, a dark old burn scar clearly visible on his thumb web as heavy raindrops splatter across his knuckles. During 2.5-6.1 seconds his fingers clench the wet canvas tighter in complete silence as bright white headlight beams begin washing across his wet hand from screen-right.
[Shot 3] At 00:06.200, the camera cuts to a tight close-up on <Subject 1>'s rain-soaked face turning sharply toward screen-right; blinding white car headlights flood straight into the lens, his pupils contract in terror and he throws his left forearm up in front of his eyes with lips closed as overexposed white headlight glare and a violent camera jolt fill the frame at 7.2 seconds.
[Shot 4] At 00:07.300, the camera cuts directly to the low-angle ground-level aftermath shot matching <Picture 2>: on the flooded wet asphalt beside a stopped car tire and red brake-light reflections at screen-right, <Subject 1> lies unconscious at lower-left with only his soaked right forearm and burn-scarred hand resting completely limp and motionless in the shallow puddle, while the unrolled grey canvas knife bundle lies scattered in the splashing rain water during 7.3-10.0 seconds. {TAIL_GUARD}

overall_soundscape:
Torrential downpour, footsteps splashing in puddles, roaring approaching engine, piercing tire screech at 6.3 seconds, a heavy dull crash thud at 7.2 seconds, followed by steady rain splashing into puddles; no human voice.

non_diegetic_music:
N/A
"""

# --- 2. New 5090 Visual Prompt for 1-4-01 (14s: Solo Initial Presence -> Ye Xun rushes in from screen-left!) ---
PROMPT_1401_NOVO = f"""subject_definitions:
<Picture 1> is the first frame of [Shot 1], locking the solo initial presence of <Subject 2> straining alone to hold the tilted wooden chili handcart on the stone slope while the left side of the path is empty.
<Subject 1> is the person from <Picture 2>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 2> without modification.
<Subject 2> is the person from <Picture 3>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 3> without modification.
<Subject 3> is the sunlit sycamore-lined stone slope before the historic university gate from <Picture 4>, preserving its golden foliage, stone flagstones, and red-brick gate arch.
<Subject 4> is the white notice sheet stamped with a bright red official seal from <Picture 5>.
All character sheets (<Picture 2>, <Picture 3>) provide 3D identity and outfit guidance only; never copy studio white backgrounds or multi-panel borders.
<Audio 1> is the voice-timbre reference for <Subject 2> (S1).

summary:
[keyframe completion + reference generation + audio reference] Starting from <Picture 1> on <Subject 3> where <Subject 2> struggles alone with a tilted chili handcart, <Subject 1> rushes into frame from screen-left to help push it onto flat ground, <Subject 2> recognizes <Subject 1> joyfully while a folded paper slips from her pocket, and [Shot 3] pushes in silently on <Subject 4> lying on the flagstones, following <Audio 1>.

retention_analysis:
<Picture 1> ([Shot 1] first frame): fully_preserved - [Shot 1] begins directly from <Picture 1> with only <Subject 2> in frame before <Subject 1> enters.
<Subject 1> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - exact identity and outfit from <Picture 2> are preserved when entering from screen-left.
<Subject 2> (appears in [Shot 1], [Shot 2]): fully_preserved - exact identity and outfit from <Picture 3> are preserved.
<Subject 3> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - sunlit sycamore stone slope and lighting remain consistent.
<Subject 4> (appears in [Shot 3]): fully_preserved - white paper sheet with red circular stamp lies flat on the flagstones in [Shot 3].
<Audio 1>: reference - <Subject 2> follows <Audio 1>'s voice timbre without copying the source recording.

detailed_description:
{STYLE_916}
[Shot 1] Starting from <Picture 1> on the sunlit stone slope of <Subject 3>, <Subject 2> stands alone on right-center straining with both hands on the wooden shafts of a handcart piled with burlap sacks of dried red chilies whose right wheel is wedged in a stone curb crack. During 0.0-0.8 seconds the heavy cart lurches further rightward and <Subject 2> slips half a step struggling to hold it; at 0.8 seconds <Subject 1> (carrying an olive-green canvas bag) strides briskly into the frame from screen-left, grabs the tilting left wooden cart frame firmly with both hands at 1.5 seconds, and heaves upward alongside <Subject 2> during 1.6-4.4 seconds until the wooden wheel clunks free onto flat flagstones and settles steady.
[Shot 2] At 00:04.600, the camera cuts to a static over-the-shoulder close shot from the same 180-degree axis, with <Subject 1>'s blurred left shoulder in the left foreground and <Subject 2> on right-center bathed in warm golden sunlight, a corner of folded white paper peeking loosely from her front pocket. Wiping sweat from her brow with her left wrist at 4.8 seconds, <Subject 2> looks straight up into <Subject 1>'s eyes—keeping her joyful gaze locked on <Subject 1>'s face—and <Subject 2> (S1) exclaims in a bright, lively young female voice during 5.2-7.8 seconds: <d>[Chinese] 谢谢同……小寻？！</d> As she exhales happily with lips closed at 7.9-8.5 seconds, the folded white paper slips out of her pocket toward the ground.
[Shot 3] At 00:08.600, the camera cuts to a high-angle close-up looking down at the sunlit stone flagstones of <Subject 3>, where <Subject 4> lies half-unfolded on the ground with its bright red circular official stamp clearly visible beside <Subject 1>'s stationary shoe tip at upper-left. During 8.7-13.9 seconds, the camera pushes in steadily toward the red-stamped paper sheet on the stone pavement in quiet outdoor ambience while urgent running footsteps approach at the very end; no on-screen speech in [Shot 3]. {TAIL_GUARD}

overall_soundscape:
Creaking wooden cart, brisk footsteps rushing in at 0.8 seconds, wooden wheel clunking onto flat stone, a bright surprised breath, soft paper flutter, and approaching running footsteps at 13.0 seconds.

non_diegetic_music:
N/A
"""

# --- 3. 4070 VO Generation Prompts (for Ye Xun's 4 new inner monologues!) ---
VO_SPECS = [
    {
        "id": "1-1-01",
        "duration": 9,
        "seed": 11101,
        "refs": [kf_1k("1-1-01"), main_1k("叶寻 · 2015行政总厨"), main_1k("双林轩总部顶层试菜厅")],
        "audios": [voice("叶寻 · 2015行政总厨")],
        "windows": [[0.4, 6.4]],
        "mode": "demucs_duck",
        "prompt": f"""subject_definitions:
<Picture 1> is a composition reference.
<Subject 1> is the person from <Picture 2>, preserving exact identity and outfit from <Picture 2>.
<Subject 2> is the room from <Picture 3>.
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).

summary:
[reference generation + audio reference] In <Subject 2>, <Subject 1>'s off-screen inner voiceover reflects bitterly on ten years of sacrifice while signing away his family recipe, following <Audio 1>.

retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - identity preserved.
<Subject 2> (appears in [Shot 1]): fully_preserved - room preserved.
<Audio 1>: reference - <Subject 1> follows <Audio 1>'s voice timbre without copying the source recording.

detailed_description:
{STYLE_916}
[Shot 1] A quiet close-up of a signed white paper on the marble table in <Subject 2>. During 0.5-6.0 seconds, <Subject 1> (S1) says in a calm, bitter, emotionally restrained off-screen voiceover at a natural brisk pace: <d>[Chinese] 十年，我熬废右手把林双双托上顶峰，连叶家祖传秘方都无偿签了出去。</d> From 6.1 to 9.0 seconds the room stays completely silent. {TAIL_GUARD}

overall_soundscape:
Very quiet indoor room tone; clear off-screen voiceover during 0.5-6.0 seconds, then silence.

non_diegetic_music:
N/A
""",
    },
    {
        "id": "1-3-01",
        "duration": 11,
        "seed": 11301,
        "refs": [kf_1k("1-3-01"), main_1k("叶寻"), main_1k("沙正街林家食府老店大堂")],
        "audios": [voice("叶寻")],
        "windows": [[1.2, 6.6]],
        "mode": "demucs_duck",
        "prompt": f"""subject_definitions:
<Picture 1> is a composition reference.
<Subject 1> is the person from <Picture 2>, preserving exact identity and outfit from <Picture 2>.
<Subject 2> is the sunlit restaurant hall from <Picture 3>.
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).

summary:
[reference generation + audio reference] In <Subject 2>, <Subject 1>'s off-screen inner voiceover realizes in stunned disbelief that he has returned to 2005 with his family recipe book still safe, following <Audio 1>.

retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - identity preserved.
<Subject 2> (appears in [Shot 1]): fully_preserved - hall preserved.
<Audio 1>: reference - <Subject 1> follows <Audio 1>'s voice timbre without copying the source recording.

detailed_description:
{STYLE_916}
[Shot 1] A quiet close-up of <Subject 1>'s unscarred right hand touching the indigo cloth book inside his canvas bag in <Subject 2>. During 1.3-6.3 seconds, <Subject 1> (S1) says in a stunned, awakening off-screen voiceover at a brisk pace: <d>[Chinese] 烫疤没了，食单还在……我重回到了二零零五年，还没交出秘方的这一天！</d> From 6.4 to 11.0 seconds there is complete silence. {TAIL_GUARD}

overall_soundscape:
Very quiet indoor ambience; clear off-screen voiceover during 1.3-6.3 seconds, then silence.

non_diegetic_music:
N/A
""",
    },
    {
        "id": "1-3-07",
        "duration": 13,
        "seed": 11307,
        "refs": [kf_1k("1-3-07"), main_1k("叶寻"), main_1k("沙正街林家食府老店大堂")],
        "audios": [voice("叶寻")],
        "windows": [[8.6, 13.5]],
        "mode": "demucs_duck",
        "prompt": f"""subject_definitions:
<Picture 1> is a composition reference.
<Subject 1> is the person from <Picture 2>, preserving exact identity and outfit from <Picture 2>.
<Subject 2> is the sunlit restaurant hall from <Picture 3>.
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).

summary:
[reference generation + audio reference] In <Subject 2>, <Subject 1>'s cold, resolute off-screen inner voiceover decides to walk away from his ungrateful past life during the final five seconds, following <Audio 1>.

retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - identity preserved.
<Subject 2> (appears in [Shot 1]): fully_preserved - hall preserved.
<Audio 1>: reference - <Subject 1> follows <Audio 1>'s voice timbre without copying the source recording.

detailed_description:
{STYLE_916}
[Shot 1] A quiet view of the olive-green canvas bag on the wooden chair in <Subject 2>. During 0.0-8.6 seconds the room is completely silent with zero speech. At 8.7-13.2 seconds, <Subject 1> (S1) says in a cold, razor-sharp, resolute off-screen voiceover at a brisk pace: <d>[Chinese] 上一世掏心掏肺换来卸磨杀驴，这一世，这火坑你们自己跳吧。</d> {TAIL_GUARD}

overall_soundscape:
Quiet room tone; complete silence before 8.7 seconds, then clear off-screen voiceover during 8.7-13.2 seconds.

non_diegetic_music:
N/A
""",
    },
    {
        "id": "1-4-01",
        "duration": 14,
        "seed": 11401,
        "refs": [kf_1k("1-4-01_solo"), main_1k("叶寻"), main_1k("重庆大学A区校门梧桐坡道")],
        "audios": [voice("叶寻")],
        "windows": [[8.7, 14.1]],
        "mode": "demucs_duck",
        "prompt": f"""subject_definitions:
<Picture 1> is a composition reference.
<Subject 1> is the person from <Picture 2>, preserving exact identity and outfit from <Picture 2>.
<Subject 2> is the sunlit stone slope from <Picture 3>.
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).

summary:
[reference generation + audio reference] On <Subject 2>, <Subject 1>'s resolute off-screen inner voiceover reads the rent notice on the ground during the final five seconds and vows to protect Xia's family, following <Audio 1>.

retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - identity preserved.
<Subject 2> (appears in [Shot 1]): fully_preserved - slope preserved.
<Audio 1>: reference - <Subject 1> follows <Audio 1>'s voice timbre without copying the source recording.

detailed_description:
{STYLE_916}
[Shot 1] A quiet top-down view of a white paper sheet lying on sunlit flagstones on <Subject 2>. During 0.0-8.7 seconds there is complete silence with zero speech. During 8.8-13.8 seconds, <Subject 1> (S1) says in a shocked yet deeply protective, determined off-screen voiceover at a brisk pace: <d>[Chinese] 欠租一万八，十月八号封门？上辈子夏家就是这关被逼垮的，这一世换我来护！</d> {TAIL_GUARD}

overall_soundscape:
Quiet outdoor breeze; complete silence before 8.8 seconds, then clear off-screen voiceover during 8.8-13.8 seconds.

non_diegetic_music:
N/A
""",
    },
]

# Lint all new prompts!
all_errs = []
all_errs.extend(lint_zero_appearance(PROMPT_1201_NOVO, "1-2-01:novo"))
all_errs.extend(lint_zero_appearance(PROMPT_1401_NOVO, "1-4-01:novo"))
for vs in VO_SPECS:
    all_errs.extend(lint_zero_appearance(vs["prompt"], f"{vs['id']}:vo"))
if all_errs:
    for e in all_errs:
        print("LINT ERROR:", e, file=sys.stderr)
    sys.exit(2)
print("LINT OK: All v3 visual and VO prompts passed zero-appearance check.", flush=True)


def run_5090_lane():
    # 1-2-01 (10s)
    d1201 = TAKES_V3 / "1-2-01"
    d1201.mkdir(parents=True, exist_ok=True)
    novo_1201 = d1201 / "video_novo.mp4"
    if not novo_1201.is_file():
        print("[5090] Starting 1-2-01 v3 crash-aftermath montage (10s, 480p)...", flush=True)
        call_pika_5090(
            novo_1201, PROMPT_1201_NOVO, 10, 12201, "9:16", "480p",
            [kf_1k("1-2-01"), kf_1k("1-2-01_aftermath"), main_1k("叶寻 · 2015行政总厨"), main_1k("集团大厦旋转门雨夜街口")],
            []
        )
        print("[5090] Finished 1-2-01 video_novo.mp4", flush=True)

    # 1-4-01 (14s)
    d1401 = TAKES_V3 / "1-4-01"
    d1401.mkdir(parents=True, exist_ok=True)
    novo_1401 = d1401 / "video_novo.mp4"
    if not novo_1401.is_file():
        print("[5090] Starting 1-4-01 v3 solo-initial-presence + Ye Xun entrance (14s, 480p)...", flush=True)
        call_pika_5090(
            novo_1401, PROMPT_1401_NOVO, 14, 12401, "9:16", "480p",
            [kf_1k("1-4-01_solo"), main_1k("叶寻"), main_1k("夏芊芊"), main_1k("重庆大学A区校门梧桐坡道"), main_1k("桂花巷18000元房租催缴单")],
            [voice("夏芊芊")]
        )
        print("[5090] Finished 1-4-01 video_novo.mp4", flush=True)


    # After 480p visuals finish (~3.8 min), 5090 helps render VO for 1-3-07 & 1-4-01 at 368p (~45s each)!
    for vs in VO_SPECS[2:]:
        sid = vs["id"]
        sdir = TAKES_V3 / sid
        sdir.mkdir(parents=True, exist_ok=True)
        out_vo = sdir / "vo_368p.mp4"
        if not out_vo.is_file():
            print(f"[5090-VO] Generating {sid} VO (368p, {vs['duration']}s)...", flush=True)
            call_pika_5090(out_vo, vs["prompt"], vs["duration"], vs["seed"], "9:16", "368p", vs["refs"], vs["audios"])
            print(f"[5090-VO] Finished {sid} vo_368p.mp4", flush=True)


def run_4070_lane():
    vo_split.LOWRES_CHECKPOINT = ""
    # Copy already verified 1-2-01 vo_368p.mp4
    d1201 = TAKES_V3 / "1-2-01"
    d1201.mkdir(parents=True, exist_ok=True)
    if not (d1201 / "vo_368p.mp4").is_file():
        shutil.copy2(TAKES_R1 / "1-2-01" / "vo_368p.mp4", d1201 / "vo_368p.mp4")

    # 4070 renders VO for 1-1-01 & 1-3-01 concurrently while 5090 renders 480p visuals!
    for vs in VO_SPECS[:2]:
        sid = vs["id"]
        sdir = TAKES_V3 / sid
        sdir.mkdir(parents=True, exist_ok=True)
        out_vo = sdir / "vo_368p.mp4"
        if not out_vo.is_file():
            print(f"[4070] Generating {sid} VO (368p, {vs['duration']}s)...", flush=True)
            vo_split.h3_lowres(
                out_vo, vs["prompt"], vs["duration"], vs["seed"],
                "9:16", "reference", vs["refs"], None, None, vs["audios"]
            )
            print(f"[4070] Finished {sid} vo_368p.mp4", flush=True)


with ThreadPoolExecutor(max_workers=2) as pool:
    f5090 = pool.submit(run_5090_lane)
    f4070 = pool.submit(run_4070_lane)
    f5090.result()
    f4070.result()

# Mix all 5 VO shots onto their silent-mouth visual masters!
MIX_JOBS = [
    ("1-1-01", [[0.4, 6.4]], "demucs_duck"),
    ("1-2-01", [[2.0, 6.2]], "splice_window"),
    ("1-3-01", [[1.2, 6.6]], "demucs_duck"),
    ("1-3-07", [[8.6, 13.5]], "demucs_duck"),
    ("1-4-01", [[8.7, 14.1]], "demucs_duck"),
]
for sid, wins, mode in MIX_JOBS:
    sdir = TAKES_V3 / sid
    print(f"[mix] Mixing VO into {sid} ({mode}, windows={wins})...", flush=True)
    mix_vo_upgraded(sdir / "video_novo.mp4", sdir / "vo_368p.mp4", wins, sdir / "video.mp4", mode=mode)
    shutil.copy2(sdir / "video_novo.json", sdir / "video.json")

print("ALL V3 SHOTS & VO MIXES COMPLETE!", flush=True)
