#!/usr/bin/env python3
"""
Compile Episode 2 (10 groups, 115s, 9:16) and Episode 3 (9 groups, 106s, 9:16)
zero-appearance Pika-H3-Flex 480p video plans + dedicated short VO placement specs.
"""
import json
import sys
from pathlib import Path

SKILL_SCRIPTS = Path("/home/zhongwenyu/project/ai-director-train/.agents/skills/hit-video/scripts")
sys.path.insert(0, str(SKILL_SCRIPTS))
from pika_runner import lint_zero_appearance  # noqa: E402

PROJECT_JSON = Path("/home/zhongwenyu/project/playlets-studio/playlets/playlet-mwj57ecn-9658ad48/project.json")
WORK_DIR = Path("/home/zhongwenyu/project/ai-director-train/productions/2005_chongqing_hotpot/ep02_03_video_gen")

proj = json.loads(PROJECT_JSON.read_text(encoding="utf-8"))
ep2 = proj["episodes"][1]
ep3 = proj["episodes"][2]
ep2_shots = ep2["shots"]
ep3_shots = ep3["shots"]
amap = json.loads((WORK_DIR / "asset_map.json").read_text(encoding="utf-8"))

STYLE_916 = (
    "The target video is shot in bright, crisp, high-contrast live-action cinema quality in vertical 9:16 framing, "
    "with natural skin texture, realistic fabric folds, accurate 35mm-50mm lens depth of field, and clear facial lighting; "
    "no CG look, no plastic beauty filter, no text overlays, captions, watermarks, or split-screen borders."
)
TAIL_GUARD = (
    "All movement happens at natural real-time speed. Keep every person's body, hands, limbs, and face anatomically stable; "
    "objects keep their exact shape and count; no person duplicates, merges, or changes identity."
)


def kf1k(sid: str) -> str:
    return str(WORK_DIR / "keyframes_1k" / f"{sid}_1k.png")


def kf2k(sid: str) -> str:
    return str(WORK_DIR / "keyframes_2k" / f"{sid}.png")


def main_1k(name: str) -> str:
    return amap[name]["main_1k"]


def voice(name: str) -> str:
    return amap[name]["voice"]


EP2_PLAN = [
    # 01: 2-1-01 (10s)
    {
        "id": "2-1-01",
        "shot_uuid": ep2_shots[0]["id"],
        "aspect_ratio": "9:16",
        "duration": 10,
        "seed": 2101,
        "keyframe_2k": kf2k("2-1-01"),
        "ref_images": [
            kf1k("2-1-01"),
            main_1k("叶寻"),
            main_1k("夏芊芊"),
            main_1k("沙正街遮雨穿堂私廊与桂花巷口"),
            main_1k("青花瓷小罐川贝梨膏"),
            main_1k("桂花巷渝清记大堂与天井"),
        ],
        "ref_audios": [voice("夏芊芊"), voice("叶寻")],
        "prompt": f"""subject_definitions:
<Picture 1> is the first frame of [Shot 1], locking the initial framing and left-right running positions in the narrow covered alley.
<Subject 1> is the person from <Picture 2>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 2> without modification.
<Subject 2> is the person from <Picture 3>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 3> without modification.
<Subject 3> is the narrow covered brick passageway from <Picture 4>.
<Subject 4> is the small blue-and-white porcelain jar with red cloth seal from <Picture 5>.
<Subject 5> is the courtyard restaurant entrance and dining hall from <Picture 6>.
All character sheets (<Picture 2>, <Picture 3>) provide 3D identity and outfit guidance only; never copy studio white backgrounds or multi-panel borders.
<Audio 1> is the voice-timbre reference for <Subject 2> (S1).
<Audio 2> is the voice-timbre reference for <Subject 1> (S2).

summary:
[keyframe completion + reference generation + audio reference] Starting from <Picture 1> in <Subject 3>, <Subject 1> pulls the wooden chili handcart alongside <Subject 2> into the courtyard of <Subject 5>, <Subject 2> slips <Subject 4> into <Subject 1>'s side satchel pocket with caring words, and <Subject 1> answers briskly before rushing toward the dining hall.

retention_analysis:
<Picture 1> ([Shot 1] first frame): fully_preserved - [Shot 1] starts directly from <Picture 1>.
<Subject 1> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - exact identity and outfit from <Picture 2> are preserved.
<Subject 2> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - exact identity and outfit from <Picture 3> are preserved.
<Subject 3> (appears in [Shot 1], [Shot 2]): fully_preserved - brick walls and translucent roof lighting remain consistent.
<Subject 4> (appears in [Shot 2]): fully_preserved - porcelain jar shape and scale remain consistent.
<Subject 5> (appears in [Shot 3]): fully_preserved - wooden courtyard doorway and warm interior remain consistent.
<Audio 1>: reference - <Subject 2> follows <Audio 1>'s voice timbre.
<Audio 2>: reference - <Subject 1> follows <Audio 2>'s voice timbre.

detailed_description:
{STYLE_916}
[Shot 1] Starting from <Picture 1> in <Subject 3>, a medium backward-tracking shot retreats briskly ahead of <Subject 1> on screen-left pulling the wooden chili handcart and <Subject 2> on screen-right hurrying alongside with a bamboo basket during 0.0-3.2 seconds, wheels rattling over stone slabs toward the courtyard gate, both with lips closed.
[Shot 2] At 00:03.200, the camera cuts to a close side tracking shot framing <Subject 1>'s olive canvas side bag on screen-left and <Subject 2>'s hands on screen-right. As <Subject 2> slips <Subject 4> securely into the outer side pocket of <Subject 1>'s canvas bag during 3.3-6.6 seconds, <Subject 2> (S1) looks up warmly and speaks clearly: <d>[Chinese] 前晚熬的川贝梨膏，别磕碎了。</d> Immediately upon finishing, <Subject 2> closes her lips while <Subject 1> keeps his lips closed.
[Shot 3] At 00:06.700, the camera cuts to a medium-close two-shot beside the wooden doorway of <Subject 5>, with <Subject 1> on screen-left halting the handcart and <Subject 2> on screen-right. Patting the side bag once at 6.8 seconds, <Subject 1> (S2) turns his head toward <Subject 2> and speaks briskly: <d>[Chinese] 先顾你自家灶台吧。</d> Immediately upon finishing at 8.9 seconds, <Subject 1> presses his lips shut and strides decisively toward the bustling dining hall during 8.9-10.0 seconds. {TAIL_GUARD}

overall_soundscape:
Wooden cart wheels rattling on flagstones, hurried footsteps, porcelain jar sliding into canvas pocket, and muffled restaurant commotion ahead.

non_diegetic_music:
N/A""",
    },

    # 02: 2-1-04 (14s)
    {
        "id": "2-1-04",
        "shot_uuid": ep2_shots[1]["id"],
        "aspect_ratio": "9:16",
        "duration": 15,
        "seed": 2104,
        "keyframe_2k": kf2k("2-1-04"),
        "ref_images": [
            kf1k("2-1-04"),
            main_1k("夏建国"),
            main_1k("刘大厨"),
            main_1k("苏晴"),
            main_1k("桂花巷渝清记大堂与天井"),
        ],
        "ref_audios": [voice("夏建国"), voice("刘大厨"), voice("苏晴")],
        "prompt": f"""subject_definitions:
<Picture 1> is the first frame of [Shot 1], locking the confrontation at the wooden counter between <Subject 1> on screen-left and <Subject 2> on screen-right.
<Subject 1> is the person from <Picture 2>, strictly preserving the exact facial features, hairstyle, right-wrist white bandage, and complete outfit from <Picture 2>.
<Subject 2> is the person from <Picture 3>, strictly preserving the exact facial features, hairstyle, slung black canvas knife bag, and complete outfit from <Picture 3>.
<Subject 3> is the person from <Picture 4>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 4>.
<Subject 4> is the courtyard restaurant dining hall from <Picture 5>.
All character sheets (<Picture 2>, <Picture 3>, <Picture 4>) provide 3D identity and outfit guidance only; never copy studio white backgrounds or multi-panel borders.
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).
<Audio 2> is the voice-timbre reference for <Subject 2> (S2).
<Audio 3> is the voice-timbre reference for <Subject 3> (S3).

summary:
[keyframe completion + reference generation + audio reference] Starting from <Picture 1> in <Subject 4>, <Subject 1> pleads urgently with <Subject 2> to finish cooking for waiting students, <Subject 2> arrogantly demands his nine-hundred-yuan wages in cash to leave for a higher-paying job, and <Subject 3> stands up at the window table checking her watch to cancel her order.

retention_analysis:
<Picture 1> ([Shot 1] first frame): fully_preserved - [Shot 1] starts directly from <Picture 1>.
<Subject 1> (appears in [Shot 1], [Shot 2]): fully_preserved - exact identity, right-wrist bandage, and outfit from <Picture 2> are preserved.
<Subject 2> (appears in [Shot 1], [Shot 2]): fully_preserved - exact identity, slung knife bag, and outfit from <Picture 3> are preserved.
<Subject 3> (appears in [Shot 3]): fully_preserved - exact identity and outfit from <Picture 4> are preserved.
<Subject 4> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - wooden counter, abacus, and square tables remain consistent.
<Audio 1>: reference - <Subject 1> follows <Audio 1>'s voice timbre.
<Audio 2>: reference - <Subject 2> follows <Audio 2>'s voice timbre.
<Audio 3>: reference - <Subject 3> follows <Audio 3>'s voice timbre.

detailed_description:
{STYLE_916}
[Shot 1] Starting from <Picture 1> in <Subject 4>, a static medium two-shot frames <Subject 1> on screen-left beside the wooden abacus counter and <Subject 2> blocking screen-right with his slung black canvas knife bag. Stepping half a step forward and gesturing anxiously with his uninjured left hand during 0.1-4.3 seconds, <Subject 1> (S1) pleads urgently: <d>[Chinese] 刘师傅，外头三桌学生等半钟头了，好歹炒完这三桌再走啊！</d> <Subject 2> scowls impatiently with lips closed.
[Shot 2] At 00:04.400, the camera cuts to an over-the-shoulder close-up from the same side of the 180-degree axis, with <Subject 1>'s blurred left shoulder on the left foreground and <Subject 2> on right-center. Slapping his palm onto the counter edge and holding his open hand out for cash during 4.5-10.3 seconds, <Subject 2> (S2) speaks loudly and bluntly: <d>[Chinese] 正街新盘店的大老板开两千二管员工餐，今晚点名到岗。半个月九百块工钱，现结！</d> Immediately upon finishing, <Subject 2> presses his lips shut with a cold glare.
[Shot 3] At 00:10.400, the camera cuts to a medium-close shot at the right window wooden table of <Subject 4> (75cm table height, empty teacups on table). Glancing down at her left wristwatch as she picks up her canvas bag and stands up during 10.5-13.4 seconds, <Subject 3> (S3) calls out crisply toward screen-left: <d>[Chinese] 七点半礼堂试麦，连碗面都没下锅，退单吧。</d> Immediately upon finishing at 13.4 seconds, <Subject 3> closes her lips and waits during 13.4-15.0 seconds. {TAIL_GUARD}

overall_soundscape:
Palm slap on wooden counter, wooden bench scraping floor, restless dining hall murmur.

non_diegetic_music:
N/A""",
    },

    # 03: 2-1-07 (11s) + dedicated VO #1 in [0.4..3.7s]
    {
        "id": "2-1-07",
        "shot_uuid": ep2_shots[2]["id"],
        "aspect_ratio": "9:16",
        "duration": 11,
        "seed": 2107,
        "keyframe_2k": kf2k("2-1-07"),
        "ref_images": [
            kf1k("2-1-07"),
            main_1k("夏芊芊"),
            main_1k("刘大厨"),
            main_1k("叶寻 · 渝清记围裙掌勺"),
            main_1k("桂花巷渝清记大堂与天井"),
        ],
        "ref_audios": [voice("夏芊芊")],
        "vo_short_spec": {
            "speaker": "叶寻",
            "ref_img": main_1k("叶寻 · 渝清记围裙掌勺"),
            "ref_aud": voice("叶寻"),
            "text": "账上只剩六千二，楚南挖走厨子就是想逼死夏家。",
            "emotion": "low, sharp,clear-eyed realization",
            "dst_start": 0.35,
            "max_window": 3.55,
            "base_duck": 0.25,
        },
        "prompt": f"""subject_definitions:
<Picture 1> is the first frame of [Shot 1], showing the overhead close-up of the open wooden counter drawer with the red passbook and hundred-yuan banknotes.
<Subject 1> is the person from <Picture 2>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 2>.
<Subject 2> is the person from <Picture 3>, strictly preserving the exact facial features, hairstyle, slung black canvas knife bag, and complete outfit from <Picture 3>.
<Subject 3> is the person from <Picture 4>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 4>.
<Subject 4> is the courtyard restaurant dining hall and wooden counter from <Picture 5>.
All character sheets (<Picture 2>, <Picture 3>, <Picture 4>) provide 3D identity and outfit guidance only; never copy studio white backgrounds or multi-panel borders.
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).

summary:
[keyframe completion + reference generation + audio reference] Starting from <Picture 1> in <Subject 4>, <Subject 1>'s hands count out nine hundred-yuan bills from under the red passbook, <Subject 1> hands the cash coldly to <Subject 2> to send him away, and <Subject 3> steps forward with calm authority ready to take command of the kitchen.

retention_analysis:
<Picture 1> ([Shot 1] first frame): fully_preserved - [Shot 1] starts directly from <Picture 1>.
<Subject 1> (appears in [Shot 1], [Shot 2]): fully_preserved - exact identity and outfit from <Picture 2> are preserved.
<Subject 2> (appears in [Shot 2]): fully_preserved - exact identity and outfit from <Picture 3> are preserved.
<Subject 3> (appears in [Shot 3]): fully_preserved - exact identity and outfit from <Picture 4> are preserved.
<Subject 4> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - wooden counter and dining hall lighting remain consistent.
<Audio 1>: reference - <Subject 1> follows <Audio 1>'s voice timbre.

detailed_description:
{STYLE_916}
[Shot 1] Starting from <Picture 1>, a static high-angle close-up into the open wooden counter drawer shows <Subject 1>'s hands briskly counting out nine crisp red hundred-yuan banknotes from beneath the red passbook and closing the passbook neatly during 0.0-3.9 seconds. No mouths are visible and nobody speaks.
[Shot 2] At 00:04.000, the camera cuts to a medium-close two-shot across the wooden counter of <Subject 4>, framing <Subject 1> standing tall on screen-left and <Subject 2> on screen-right. Extending the nine banknotes flat toward <Subject 2> at 4.1 seconds as <Subject 2> snatches them and turns toward the door, <Subject 1> (S1) speaks with cool, dignified firmness: <d>[Chinese] 九百块点清，不送。</d> Immediately upon finishing at 6.6 seconds, <Subject 1> presses her lips shut.
[Shot 3] At 00:07.000, the camera cuts to a medium-close shot beside the counter pushing smoothly inward toward <Subject 3> standing on screen-left as <Subject 2> exits in the right background. <Subject 3> sets his olive canvas bag inside the counter cubby, smooths his front with practiced chef composure, and turns his steady, determined gaze toward the kitchen doorway during 7.1-11.0 seconds with lips firmly closed. {TAIL_GUARD}

overall_soundscape:
Wooden drawer slide, crisp banknote counting rustle, cash snatch, departing footsteps, and fabric rustle.

non_diegetic_music:
N/A""",
    },

    # 04: 2-1-10 (12s)
    {
        "id": "2-1-10",
        "shot_uuid": ep2_shots[3]["id"],
        "aspect_ratio": "9:16",
        "duration": 13,
        "seed": 2110,
        "keyframe_2k": kf2k("2-1-10"),
        "ref_images": [
            kf1k("2-1-10"),
            main_1k("叶寻 · 渝清记围裙掌勺"),
            main_1k("夏建国"),
            main_1k("苏晴"),
            main_1k("桂花巷渝清记大堂与天井"),
        ],
        "ref_audios": [voice("叶寻"), voice("夏建国")],
        "prompt": f"""subject_definitions:
<Picture 1> is the first frame of [Shot 1], locking the two-shot blocking beside the counter between <Subject 1> on screen-left and <Subject 2> on screen-right.
<Subject 1> is the person from <Picture 2>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 2>.
<Subject 2> is the person from <Picture 3>, strictly preserving the exact facial features, hairstyle, right-wrist white bandage, and complete outfit from <Picture 3>.
<Subject 3> is the person from <Picture 4>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 4>.
<Subject 4> is the courtyard restaurant dining hall from <Picture 5>.
All character sheets (<Picture 2>, <Picture 3>, <Picture 4>) provide 3D identity and outfit guidance only; never copy studio white backgrounds or multi-panel borders.
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).
<Audio 2> is the voice-timbre reference for <Subject 2> (S2).

summary:
[keyframe completion + reference generation + audio reference] Starting from <Picture 1> in <Subject 4>, <Subject 1> asks <Subject 2> if the morning bone-and-chicken broth is still simmering, <Subject 2> worries that the students cannot eat irritating chili before their voice test, and <Subject 1> turns to <Subject 3> to pledge a non-irritating ten-minute tripe pot or the meal is free.

retention_analysis:
<Picture 1> ([Shot 1] first frame): fully_preserved - [Shot 1] starts directly from <Picture 1>.
<Subject 1> (appears in [Shot 1], [Shot 3]): fully_preserved - exact identity and outfit from <Picture 2> are preserved.
<Subject 2> (appears in [Shot 1], [Shot 2]): fully_preserved - exact identity, right-wrist bandage, and outfit from <Picture 3> are preserved.
<Subject 3> (appears in [Shot 3]): fully_preserved - exact identity and outfit from <Picture 4> are preserved.
<Subject 4> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - wooden counter and dining tables remain consistent.
<Audio 1>: reference - <Subject 1> follows <Audio 1>'s voice timbre.
<Audio 2>: reference - <Subject 2> follows <Audio 2>'s voice timbre.

detailed_description:
{STYLE_916}
[Shot 1] Starting from <Picture 1> in <Subject 4>, a static medium-close two-shot frames <Subject 1> on screen-left facing right and <Subject 2> on screen-right facing left. Immediately at 0.1 seconds, <Subject 1> (S1) asks briskly with calm confidence: <d>[Chinese] 夏叔，早上吊的那锅猪骨老母鸡汤还在火上吧？</d> Immediately upon finishing at 3.3 seconds, <Subject 1> closes his lips while <Subject 2> blinks in surprise.
[Shot 2] At 00:03.500, the camera cuts to a close-up of <Subject 2> on right-center glancing worriedly toward the window table and back to <Subject 1>. Gesturing anxiously with his uninjured left hand during 3.6-6.8 seconds, <Subject 2> (S2) replies: <d>[Chinese] 在火上，可她们赶着试音忌辣……</d> Immediately upon finishing, <Subject 2> closes his lips.
[Shot 3] At 00:07.000, the camera cuts to an over-the-shoulder medium-close shot from behind <Subject 3>'s blurred right shoulder in the right foreground, facing <Subject 1> standing center-left in <Subject 4>. Stepping half a step forward and raising one steady index finger during 7.1-11.2 seconds, <Subject 1> (S1) speaks with rock-solid assurance: <d>[Chinese] 给我十分钟，骨汤微辣烫鲜毛肚——呛一下嗓子，这桌免单。</d> Immediately upon finishing at 11.2 seconds, <Subject 1> presses his lips shut and holds <Subject 3>'s gaze calmly until 13.0 seconds. {TAIL_GUARD}

overall_soundscape:
Faint simmering broth sound from the back kitchen and quiet attentive dining room ambience.

non_diegetic_music:
N/A""",
    },

    # 05: 2-1-13 (12s)
    {
        "id": "2-1-13",
        "shot_uuid": ep2_shots[4]["id"],
        "aspect_ratio": "9:16",
        "duration": 12,
        "seed": 2113,
        "keyframe_2k": kf2k("2-1-13"),
        "ref_images": [
            kf1k("2-1-13"),
            main_1k("苏晴"),
            main_1k("叶寻 · 渝清记围裙掌勺"),
            main_1k("夏芊芊"),
            main_1k("桂花巷渝清记大堂与天井"),
            main_1k("渝清记后厨猛火灶间"),
        ],
        "ref_audios": [voice("苏晴")],
        "prompt": f"""subject_definitions:
<Picture 1> is the first frame of [Shot 1], locking <Subject 1> standing beside the window table checking her wristwatch.
<Subject 1> is the person from <Picture 2>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 2>.
<Subject 2> is the person from <Picture 3>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 3>.
<Subject 3> is the person from <Picture 4>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 4>.
<Subject 4> is the dining hall from <Picture 5>.
<Subject 5> is the back-kitchen stove room from <Picture 6>.
All character sheets (<Picture 2>, <Picture 3>, <Picture 4>) provide 3D identity and outfit guidance only; never copy studio white backgrounds or multi-panel borders.
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).

summary:
[keyframe completion + reference generation + audio reference] Starting from <Picture 1> in <Subject 4>, <Subject 1> checks her watch and sits back down giving a strict ten-minute deadline, <Subject 2> strides briskly into <Subject 5> gripping the iron ladle, and <Subject 3> sets a clean black clay casserole and chilled fresh tripe plate beside the stove.

retention_analysis:
<Picture 1> ([Shot 1] first frame): fully_preserved - [Shot 1] starts directly from <Picture 1>.
<Subject 1> (appears in [Shot 1]): fully_preserved - exact identity and outfit from <Picture 2> are preserved.
<Subject 2> (appears in [Shot 2], [Shot 3]): fully_preserved - exact identity and outfit from <Picture 3> are preserved.
<Subject 3> (appears in [Shot 2], [Shot 3]): fully_preserved - exact identity and outfit from <Picture 4> are preserved.
<Subject 4> (appears in [Shot 1], [Shot 2]): fully_preserved - window table and kitchen doorway remain consistent.
<Subject 5> (appears in [Shot 3]): fully_preserved - iron wok stove and wooden prep counter remain consistent.
<Audio 1>: reference - <Subject 1> follows <Audio 1>'s voice timbre.

detailed_description:
{STYLE_916}
[Shot 1] Starting from <Picture 1> in <Subject 4>, a static medium-close shot frames <Subject 1> beside the 75cm-high wooden window table. Setting her canvas bag back onto the table corner and sitting down onto the wooden bench (waist at table-edge height, full upper body visible) during 0.1-3.8 seconds, <Subject 1> (S1) looks left-forward and speaks crisply: <d>[Chinese] 十分钟？行，耽误试麦我真走人。</d> Immediately upon finishing at 3.8 seconds, <Subject 1> closes her lips.
[Shot 2] At 00:04.000, the camera cuts to a medium tracking shot following <Subject 2> walking briskly across <Subject 4> toward the cloth-curtained kitchen doorway with <Subject 3> hurrying right behind him during 4.1-7.8 seconds; <Subject 2> lifts the curtain and steps into the warm glow of the kitchen stove, both silent with lips closed.
[Shot 3] At 00:08.000, the camera cuts inside <Subject 5> to a medium-close shot at the wooden prep table beside the blazing stove: <Subject 3> on screen-right places a clean black clay casserole pot and a white porcelain plate of fresh dark beef tripe within reach of <Subject 2> standing at the iron wok on screen-left during 8.1-12.0 seconds, exchanging a focused, trusting nod in silence. {TAIL_GUARD}

overall_soundscape:
Canvas bag placed on wood, brisk footsteps, cloth curtain swish, clay casserole set on wooden prep board, rising stove flame roar.

non_diegetic_music:
N/A""",
    },

    # 06: 2-2-01 (12s) + dedicated VO #2 in [0.5..7.0s]
    {
        "id": "2-2-01",
        "shot_uuid": ep2_shots[5]["id"],
        "aspect_ratio": "9:16",
        "duration": 13,
        "seed": 2201,
        "keyframe_2k": kf2k("2-2-01"),
        "ref_images": [
            kf1k("2-2-01"),
            main_1k("叶寻 · 渝清记围裙掌勺"),
            main_1k("夏建国"),
            main_1k("渝清记后厨猛火灶间"),
        ],
        "ref_audios": [voice("夏建国")],
        "vo_short_spec": {
            "speaker": "叶寻",
            "ref_img": main_1k("叶寻 · 渝清记围裙掌勺"),
            "ref_aud": voice("叶寻"),
            "text": "鲜梨汁化牛油，温醪糟退椒燥，辣香入魂却半点不呛嗓。",
            "emotion": "calm, confident master-chef mastery",
            "dst_start": 0.45,
            "max_window": 7.10,
            "base_duck": 0.28,
        },
        "prompt": f"""subject_definitions:
<Picture 1> is the first frame of [Shot 1], locking <Subject 1> tempering tallow, pear juice, and glistening dried chilies in the big iron wok of <Subject 3>.
<Subject 1> is the person from <Picture 2>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 2>.
<Subject 2> is the person from <Picture 3>, strictly preserving the exact facial features, hairstyle, right-wrist white bandage, and complete outfit from <Picture 3>.
<Subject 3> is the traditional back-kitchen stove room from <Picture 4>.
All character sheets (<Picture 2>, <Picture 3>) provide 3D identity and outfit guidance only; never copy studio white backgrounds or multi-panel borders.
<Audio 1> is the voice-timbre reference for <Subject 2> (S1).

summary:
[keyframe completion + reference generation + audio reference] Starting from <Picture 1> in <Subject 3>, <Subject 1> tempers amber tallow with clear pear juice and drained chilies without harsh smoke, ladles boiling white bone broth to blanch fresh tripe into the black clay casserole, and <Subject 2> inhales the clean aroma in amazed recognition.

retention_analysis:
<Picture 1> ([Shot 1] first frame): fully_preserved - [Shot 1] starts directly from <Picture 1>.
<Subject 1> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - exact identity and outfit from <Picture 2> are preserved.
<Subject 2> (appears in [Shot 3]): fully_preserved - exact identity, right-wrist bandage, and outfit from <Picture 3> are preserved.
<Subject 3> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - iron wok stove and prep table remain consistent.
<Audio 1>: reference - <Subject 2> follows <Audio 1>'s voice timbre.

detailed_description:
{STYLE_916}
[Shot 1] Starting from <Picture 1> in <Subject 3>, a high-angle close-up on the seasoned iron wok shows <Subject 1>'s unscarred right hand steadily stirring amber beef tallow blended with clear pear juice and drained red dried chilies over controlled flame during 0.0-3.9 seconds; the chilies puff glossy red with fragrant steam and zero harsh black smoke while <Subject 1>'s lips stay closed.
[Shot 2] At 00:04.000, the camera cuts to a medium-close side angle panning smoothly 20 degrees rightward as <Subject 1> tosses dried tangerine peel into the wok, pours a full ladle of rolling milky-white bone broth in, blanches slices of fresh tripe briskly, and ladles the steaming amber-white broth and tripe into the black clay casserole on the prep counter during 4.1-7.8 seconds, silent with lips closed.
[Shot 3] At 00:07.900, the camera cuts to a static medium-close two-shot across the steaming black clay casserole: <Subject 1> stands on screen-left wiping the casserole rim with a clean cloth (lips closed), while <Subject 2> leans in on screen-right inhaling the clean, fragrant steam. His eyes lighting up in awe during 8.0-11.3 seconds, <Subject 2> (S1) exclaims: <d>[Chinese] 温醪糟退椒燥……这是叶老爷子的绝活！</d> Immediately upon finishing at 11.3 seconds, <Subject 2> closes his lips with an admiring smile until 13.0 seconds. {TAIL_GUARD}

overall_soundscape:
Gentle tallow sizzle without harsh splutter, rich boiling bone broth ladle pour into wok and clay casserole, soft bubbling steam.

non_diegetic_music:
N/A""",
    },

    # 07: 2-2-04 (13s)
    {
        "id": "2-2-04",
        "shot_uuid": ep2_shots[6]["id"],
        "aspect_ratio": "9:16",
        "duration": 13,
        "seed": 2204,
        "keyframe_2k": kf2k("2-2-04"),
        "ref_images": [
            kf1k("2-2-04"),
            main_1k("叶寻 · 渝清记围裙掌勺"),
            main_1k("夏芊芊"),
            main_1k("苏晴"),
            main_1k("渝清记后厨猛火灶间"),
            main_1k("桂花巷渝清记大堂与天井"),
        ],
        "ref_audios": [voice("叶寻"), voice("苏晴")],
        "prompt": f"""subject_definitions:
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
[keyframe completion + reference generation + audio reference] Starting from <Picture 1> in <Subject 4>, <Subject 1> hands the steaming casserole tray to <Subject 2> to serve, <Subject 3> sips the broth at the table in <Subject 5> and tests her clear singing voice in delight, and <Subject 3> invites her classmates to dig in happily.

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
[Shot 2] At 00:02.800, the camera cuts to a close-up at the 75cm-high window table of <Subject 5>, slowly pushing in on <Subject 3> seated behind the steaming black clay casserole. During 2.9-5.2 seconds, <Subject 3> skims half a porcelain spoonful of the amber-white broth and sips it; her eyes widen in pleasant surprise and during 5.3-7.6 seconds <Subject 3> (S2) tests her throat with a crystal-clear vocal scale: <d>[Chinese] 咪，嘛，咪。</d>
[Shot 3] At 00:07.800, the camera cuts to a lively medium-close shot at the window table framing <Subject 3> on right-center picking up bamboo chopsticks alongside two delighted female classmates reaching toward the casserole. Beaming brightly during 7.9-12.1 seconds, <Subject 3> (S2) speaks enthusiastically: <d>[Chinese] 真神了，嗓子清清亮亮的！快动筷，吃完赶得上排练！</d> Immediately upon finishing at 12.1 seconds, <Subject 3> closes her lips and happily picks up fresh tripe from the casserole until 13.0 seconds. {TAIL_GUARD}

overall_soundscape:
Wooden tray handoff, gentle spoon sip, crystal-clear vocal scale, cheerful bamboo chopsticks clinking.

non_diegetic_music:
N/A""",
    },

    # 08: 2-2-07 (12s)
    {
        "id": "2-2-07",
        "shot_uuid": ep2_shots[7]["id"],
        "aspect_ratio": "9:16",
        "duration": 12,
        "seed": 2207,
        "keyframe_2k": kf2k("2-2-07"),
        "ref_images": [
            kf1k("2-2-07"),
            main_1k("叶寻 · 渝清记围裙掌勺"),
            main_1k("夏芊芊"),
            main_1k("苏晴"),
            main_1k("桂花巷渝清记大堂与天井"),
        ],
        "ref_audios": [voice("苏晴"), voice("叶寻")],
        "prompt": f"""subject_definitions:
<Picture 1> is the composition and blocking keyframe for [Shot 2], locking <Subject 1> and <Subject 2> standing side by side behind the wooden abacus counter.
<Subject 1> is the person from <Picture 2>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 2>.
<Subject 2> is the person from <Picture 3>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 3>.
<Subject 3> is the person from <Picture 4>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 4>.
<Subject 4> is the warm evening courtyard dining hall from <Picture 5>.
All character sheets (<Picture 2>, <Picture 3>, <Picture 4>) provide 3D identity and outfit guidance only; never copy studio white backgrounds or multi-panel borders.
<Audio 1> is the voice-timbre reference for <Subject 3> (S1).
<Audio 2> is the voice-timbre reference for <Subject 1> (S2).

summary:
[keyframe completion + reference generation + audio reference] In <Subject 4>, <Subject 3> places sixty-eight yuan in banknotes beside the empty clay casserole asking to book tomorrow night, <Subject 1> beside <Subject 2> in <Picture 1> promises a reserved table when the properly aged broth opens in two evenings, and <Subject 3> cheerfully books two tables for the broadcasting club.

retention_analysis:
<Picture 1> ([Shot 2] keyframe): fully_preserved - [Shot 2] matches <Picture 1>'s counter framing and two-person blocking.
<Subject 1> (appears in [Shot 2]): fully_preserved - exact identity and outfit from <Picture 2> are preserved.
<Subject 2> (appears in [Shot 2]): fully_preserved - exact identity and outfit from <Picture 3> are preserved.
<Subject 3> (appears in [Shot 1], [Shot 3]): fully_preserved - exact identity and outfit from <Picture 4> are preserved.
<Subject 4> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - wooden tables and counter lighting remain consistent.
<Audio 1>: reference - <Subject 3> follows <Audio 1>'s voice timbre.
<Audio 2>: reference - <Subject 1> follows <Audio 2>'s voice timbre.

detailed_description:
{STYLE_916}
[Shot 1] A high-angle close-up on the wooden tabletop of <Subject 4> shows the black clay casserole eaten completely clean and empty; as <Subject 3>'s right hand presses neat banknotes onto the table corner during 0.1-2.8 seconds, <Subject 3> (S1) speaks briskly from off-camera above: <d>[Chinese] 老板，明晚还能订这锅吗？</d>
[Shot 2] At 00:03.000, the camera cuts to a static medium-close two-shot matching <Picture 1> behind the wooden abacus counter: <Subject 1> stands on screen-left resting his hands on the counter while <Subject 2> stands smiling beside him on screen-right flicking two abacus beads with lips closed. During 3.1-8.4 seconds, <Subject 1> (S2) replies with sincere craftsmanship: <d>[Chinese] 今晚只是借味救急。等正经底料焖透退火，后天傍晚开张，给你们留桌。</d> Immediately upon finishing, <Subject 1> closes his lips with a warm nod.
[Shot 3] At 00:08.600, the camera cuts to a medium-close shot of <Subject 3> standing by the wooden doorway with her canvas bag slung over her shoulder. Giving a bright wave toward the counter during 8.7-11.3 seconds, <Subject 3> (S1) replies: <d>[Chinese] 一言为定，后天播音社来两桌！</d> Immediately upon finishing at 11.3 seconds, <Subject 3> closes her lips and turns toward the doorway until 13.0 seconds. {TAIL_GUARD}

overall_soundscape:
Crisp banknotes pressed onto wood, two wooden abacus beads clicking, cheerful student footsteps.

non_diegetic_music:
N/A""",
    },

    # 09: 2-2-10 (10s)
    {
        "id": "2-2-10",
        "shot_uuid": ep2_shots[8]["id"],
        "aspect_ratio": "9:16",
        "duration": 10,
        "seed": 2210,
        "keyframe_2k": kf2k("2-2-10"),
        "ref_images": [
            kf1k("2-2-10"),
            main_1k("苏晴"),
            main_1k("林双双"),
            main_1k("叶寻 · 渝清记围裙掌勺"),
            main_1k("夏芊芊"),
            main_1k("桂花巷渝清记大堂与天井"),
        ],
        "ref_audios": [],
        "prompt": f"""subject_definitions:
<Picture 1> is the first frame of [Shot 1], locking <Subject 1> exiting happily on the left and <Subject 2> striding in coldly on the right at the wooden doorway.
<Subject 1> is the person from <Picture 2>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 2>.
<Subject 2> is the person from <Picture 3>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 3>.
<Subject 3> is the person from <Picture 4>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 4>.
<Subject 4> is the person from <Picture 5>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 5>.
<Subject 5> is the evening courtyard dining hall from <Picture 6>.
All character sheets (<Picture 2> to <Picture 5>) provide 3D identity and outfit guidance only; never copy studio white backgrounds or multi-panel borders.

summary:
[keyframe completion + reference generation] Starting from <Picture 1> at the doorway of <Subject 5>, <Subject 1> walks out smiling past <Subject 2> striding in with a kraft ledger and iron key ring, <Subject 3> and <Subject 4> look up calmly side by side behind the counter, and <Subject 2> slams the heavy iron key ring onto the wooden table.

retention_analysis:
<Picture 1> ([Shot 1] first frame): fully_preserved - [Shot 1] starts directly from <Picture 1>.
<Subject 1> (appears in [Shot 1]): fully_preserved - exact identity and outfit from <Picture 2> are preserved.
<Subject 2> (appears in [Shot 1], [Shot 3]): fully_preserved - exact identity and outfit from <Picture 3> are preserved.
<Subject 3> (appears in [Shot 2]): fully_preserved - exact identity and outfit from <Picture 4> are preserved.
<Subject 4> (appears in [Shot 2]): fully_preserved - exact identity and outfit from <Picture 5> are preserved.
<Subject 5> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - doorway, counter, and wooden square table remain consistent.

detailed_description:
{STYLE_916}
[Shot 1] Starting from <Picture 1> at the open wooden doorway of <Subject 5>, the camera glides slightly leftward during 0.0-3.8 seconds as <Subject 1> steps out smiling to screen-right while <Subject 2> strides across the threshold from screen-right holding a kraft-paper ledger in her left hand and an iron key ring in her right; spotting the counter to her left, <Subject 2>'s expression darkens sharply with cold displeasure, lips pressed shut.
[Shot 2] At 00:03.900, the camera cuts to a medium-close two-shot behind the wooden counter of <Subject 5>: <Subject 3> on screen-left pauses wiping his hands with a dry cloth and raises a calm, indifferent gaze toward the door, while <Subject 4> on screen-right steps half a step closer beside him with alert poise during 3.9-6.8 seconds, both silent with lips closed.
[Shot 3] At 00:06.900, the camera cuts to a tight oblique close-up on the wooden square table beside the door: <Subject 2>'s left hand presses the kraft ledger down while her right hand swings down sharply and slams the heavy ring of iron kitchen keys onto the wooden tabletop at 7.5 seconds with a sharp metallic clatter, fingers releasing as the keys vibrate on the wood until 10.0 seconds. Nobody speaks. {TAIL_GUARD}

overall_soundscape:
Passing footsteps at the doorway, sharp heel steps on stone, tense quiet room tone, and a loud metallic slam of iron keys onto solid wood.

non_diegetic_music:
N/A""",
    },

    # 10: 2-2-13 (9s)
    {
        "id": "2-2-13",
        "shot_uuid": ep2_shots[9]["id"],
        "aspect_ratio": "9:16",
        "duration": 9,
        "seed": 2213,
        "keyframe_2k": kf2k("2-2-13"),
        "ref_images": [
            kf1k("2-2-13"),
            main_1k("林双双"),
            main_1k("叶寻 · 渝清记围裙掌勺"),
            main_1k("桂花巷渝清记大堂与天井"),
        ],
        "ref_audios": [voice("林双双")],
        "prompt": f"""subject_definitions:
<Picture 1> is the first frame of [Shot 1], locking <Subject 1> standing arrogantly beside the doorway table with the iron keys on the tabletop.
<Subject 1> is the person from <Picture 2>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 2>.
<Subject 2> is the person from <Picture 3>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 3>.
<Subject 3> is the evening courtyard dining hall from <Picture 4>.
All character sheets (<Picture 2>, <Picture 3>) provide 3D identity and outfit guidance only; never copy studio white backgrounds or multi-panel borders.
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).

summary:
[keyframe completion + reference generation + audio reference] Starting from <Picture 1> in <Subject 3>, <Subject 1> coldly orders <Subject 2> to hand over the kitchen accounts within five minutes, and <Subject 2> sets down his cloth and steps out from behind the counter with icy composure.

retention_analysis:
<Picture 1> ([Shot 1] first frame): fully_preserved - [Shot 1] starts directly from <Picture 1>.
<Subject 1> (appears in [Shot 1], [Shot 2]): fully_preserved - exact identity and outfit from <Picture 2> are preserved.
<Subject 2> (appears in [Shot 2]): fully_preserved - exact identity and outfit from <Picture 3> are preserved.
<Subject 3> (appears in [Shot 1], [Shot 2]): fully_preserved - wooden table, iron keys, and counter lighting remain consistent.
<Audio 1>: reference - <Subject 1> follows <Audio 1>'s voice timbre.

detailed_description:
{STYLE_916}
[Shot 1] Starting from <Picture 1> in <Subject 3>, a static slightly low-angle close-up frames <Subject 1> on right-center holding the kraft ledger against her front with the iron key ring resting on the lower foreground table corner. Lifting her chin imperiously during 0.1-5.8 seconds, <Subject 1> (S1) speaks in a cold, commanding tone toward screen-left: <d>[Chinese] 叶寻，赵主厨明早到店，出来把林家肉菜账交接清楚——我只等你五分钟。</d> Immediately upon finishing at 5.8 seconds, <Subject 1> presses her lips shut with an arrogant stare.
[Shot 2] At 00:06.000, the camera cuts to an over-the-shoulder close-up past <Subject 1>'s blurred right shoulder in the right foreground, slowly pushing in on <Subject 2> at the counter on left-center. <Subject 2> sets the dry hand towel flat onto the wooden counter, steps calmly out from behind the counter opening to face <Subject 1> head-on, and locks his razor-sharp, unyielding gaze onto her in silence during 6.1-9.0 seconds with lips firmly closed. {TAIL_GUARD}

overall_soundscape:
Quiet tense evening room tone, cloth laid on wood, and one steady footstep onto stone floor.

non_diegetic_music:
N/A""",
    },
]


EP3_PLAN = [
    # 01: 3-1-01 (11s)
    {
        "id": "3-1-01",
        "shot_uuid": ep3_shots[0]["id"],
        "aspect_ratio": "9:16",
        "duration": 11,
        "seed": 3101,
        "keyframe_2k": kf2k("3-1-01"),
        "ref_images": [
            kf1k("3-1-01"),
            main_1k("叶寻 · 渝清记围裙掌勺"),
            main_1k("林双双"),
            main_1k("夏建国"),
            main_1k("桂花巷渝清记大堂与天井"),
        ],
        "ref_audios": [voice("林双双")],
        "prompt": f"""subject_definitions:
<Picture 1> is the first frame of [Shot 1], locking <Subject 1> stepping out calmly on screen-left and <Subject 2> standing with arms crossed on screen-right in <Subject 4>.
<Subject 1> is the person from <Picture 2>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 2>.
<Subject 2> is the person from <Picture 3>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 3>.
<Subject 3> is the person from <Picture 4>, strictly preserving the exact facial features, hairstyle, right-wrist white bandage, and complete outfit from <Picture 4>.
<Subject 4> is the night courtyard dining hall from <Picture 5>.
All character sheets (<Picture 2>, <Picture 3>, <Picture 4>) provide 3D identity and outfit guidance only; never copy studio white backgrounds or multi-panel borders.
<Audio 1> is the voice-timbre reference for <Subject 2> (S1).

summary:
[keyframe completion + reference generation + audio reference] Starting from <Picture 1> in <Subject 4>, <Subject 1> stops calmly across from <Subject 2> while <Subject 3> watches from behind the counter, and <Subject 2> condescendingly offers <Subject 1> eight hundred yuan a month to come back as an odd-job kitchen helper.

retention_analysis:
<Picture 1> ([Shot 1] first frame): fully_preserved - [Shot 1] starts directly from <Picture 1>.
<Subject 1> (appears in [Shot 1], [Shot 2]): fully_preserved - exact identity and outfit from <Picture 2> are preserved.
<Subject 2> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - exact identity and outfit from <Picture 3> are preserved.
<Subject 3> (appears in [Shot 1]): fully_preserved - exact identity and outfit from <Picture 4> are preserved.
<Subject 4> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - wooden counter and square table lighting remain consistent.
<Audio 1>: reference - <Subject 2> follows <Audio 1>'s voice timbre.

detailed_description:
{STYLE_916}
[Shot 1] Starting from <Picture 1> in <Subject 4>, a static medium-close shot frames <Subject 1> halting calmly on screen-left facing right while <Subject 2> stands with arms crossed on screen-right and <Subject 3> watches quietly in the left-rear counter during 0.0-2.0 seconds, all with lips closed.
[Shot 2] At 00:02.100, the camera cuts to an over-the-shoulder close-up past <Subject 1>'s blurred left shoulder, framing <Subject 2> on right-center looking <Subject 1> up and down disdainfully. Arching an eyebrow with a condescending scoff during 2.2-5.1 seconds, <Subject 2> (S1) speaks: <d>[Chinese] 赌气跑来给人打杂，有意思吗？</d>
[Shot 3] At 00:05.200, the camera cuts to a tighter frontal-oblique close-up of <Subject 2> gesturing dismissively toward the street outside as if tossing scraps to a servant during 5.3-10.2 seconds, speaking clearly: <d>[Chinese] 赵主厨不干粗洗采买，你明天回来管后厨杂务，我给你开八百一个月。</d> Immediately upon finishing at 10.2 seconds, <Subject 2> crosses her arms and presses her lips shut waiting smugly until 11.0 seconds. {TAIL_GUARD}

overall_soundscape:
Steady footsteps halting on stone, soft disdainful scoff, quiet night street ambience outside.

non_diegetic_music:
N/A""",
    },

    # 02: 3-1-04 (11s)
    {
        "id": "3-1-04",
        "shot_uuid": ep3_shots[1]["id"],
        "aspect_ratio": "9:16",
        "duration": 11,
        "seed": 3104,
        "keyframe_2k": kf2k("3-1-04"),
        "ref_images": [
            kf1k("3-1-04"),
            main_1k("叶寻 · 渝清记围裙掌勺"),
            main_1k("林双双"),
            main_1k("桂花巷渝清记大堂与天井"),
        ],
        "ref_audios": [voice("叶寻"), voice("林双双")],
        "prompt": f"""subject_definitions:
<Picture 1> is the first frame of [Shot 1], showing <Subject 1>'s unscarred right hand placing the iron kitchen key ring onto the center of the kraft ledger.
<Subject 1> is the person from <Picture 2>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 2>.
<Subject 2> is the person from <Picture 3>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 3>.
<Subject 3> is the night courtyard dining hall from <Picture 4>.
All character sheets (<Picture 2>, <Picture 3>) provide 3D identity and outfit guidance only; never copy studio white backgrounds or multi-panel borders.
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).
<Audio 2> is the voice-timbre reference for <Subject 2> (S2).

summary:
[keyframe completion + reference generation + audio reference] Starting from <Picture 1> in <Subject 3>, <Subject 1> places the iron keys onto the ledger stating the accounts are clear, <Subject 2> frowns in disbelief asking what he means, and <Subject 1> calmly declares they are completely done with each other.

retention_analysis:
<Picture 1> ([Shot 1] first frame): fully_preserved - [Shot 1] starts directly from <Picture 1>.
<Subject 1> (appears in [Shot 1], [Shot 3]): fully_preserved - exact identity and outfit from <Picture 2> are preserved.
<Subject 2> (appears in [Shot 2]): fully_preserved - exact identity and outfit from <Picture 3> are preserved.
<Subject 3> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - wooden tabletop and warm night lighting remain consistent.
<Audio 1>: reference - <Subject 1> follows <Audio 1>'s voice timbre.
<Audio 2>: reference - <Subject 2> follows <Audio 2>'s voice timbre.

detailed_description:
{STYLE_916}
[Shot 1] Starting from <Picture 1> on the wooden table of <Subject 3>, the camera pushes slowly inward as <Subject 1>'s unscarred right hand sets the iron key ring cleanly down onto the kraft ledger cover and withdraws to screen-left during 0.1-3.8 seconds while <Subject 1> (S1) speaks calmly from just above: <d>[Chinese] 林家上月肉菜账在第三页，没有欠款。</d>
[Shot 2] At 00:04.000, the camera cuts to a close-up of <Subject 2> on right-center glancing down at the returned keys and snapping her gaze up in stunned annoyance. Furrowing her brows sharply during 4.1-6.1 seconds, <Subject 2> (S2) demands: <d>[Chinese] 你什么意思？</d> Immediately upon finishing, <Subject 2> closes her lips.
[Shot 3] At 00:06.300, the camera cuts to a close-up of <Subject 1> standing tall on left-center under the warm light of <Subject 3>. Looking straight at <Subject 2> without a trace of anger or lingering attachment during 6.4-10.2 seconds, <Subject 1> (S1) speaks with crystal-clear finality: <d>[Chinese] 下午走出林家店门起，咱们就两清了。钥匙收好。</d> Immediately upon finishing at 10.2 seconds, <Subject 1> presses his lips shut in tranquil silence until 11.0 seconds. {TAIL_GUARD}

overall_soundscape:
Soft metallic clink of iron keys set onto paper ledger, subtle fabric rustle, quiet night room tone.

non_diegetic_music:
N/A""",
    },

    # 03: 3-1-07 (10s)
    {
        "id": "3-1-07",
        "shot_uuid": ep3_shots[2]["id"],
        "aspect_ratio": "9:16",
        "duration": 10,
        "seed": 3107,
        "keyframe_2k": kf2k("3-1-07"),
        "ref_images": [
            kf1k("3-1-07"),
            main_1k("林双双"),
            main_1k("夏芊芊"),
            main_1k("叶寻 · 渝清记围裙掌勺"),
            main_1k("桂花巷渝清记大堂与天井"),
        ],
        "ref_audios": [voice("林双双"), voice("夏芊芊")],
        "prompt": f"""subject_definitions:
<Picture 1> is the composition and blocking keyframe for [Shot 2], locking <Subject 2> holding the open wooden door leaf beside <Subject 3> on screen-left facing <Subject 1> on screen-right.
<Subject 1> is the person from <Picture 2>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 2>.
<Subject 2> is the person from <Picture 3>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 3>.
<Subject 3> is the person from <Picture 4>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 4>.
<Subject 4> is the night courtyard dining hall doorway from <Picture 5>.
All character sheets (<Picture 2>, <Picture 3>, <Picture 4>) provide 3D identity and outfit guidance only; never copy studio white backgrounds or multi-panel borders.
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).
<Audio 2> is the voice-timbre reference for <Subject 2> (S2).

summary:
[keyframe completion + reference generation + audio reference] In <Subject 4>, <Subject 1> sneers furiously that <Subject 3> would waste his family recipe on a failing courtyard shop, and in the blocking of <Picture 1>, <Subject 2> steps to the open wooden door declaring they are equal business partners and politely showing <Subject 1> out.

retention_analysis:
<Picture 1> ([Shot 2] keyframe): fully_preserved - [Shot 2] matches <Picture 1>'s doorway blocking.
<Subject 1> (appears in [Shot 1], [Shot 2]): fully_preserved - exact identity and outfit from <Picture 2> are preserved.
<Subject 2> (appears in [Shot 2]): fully_preserved - exact identity and outfit from <Picture 3> are preserved.
<Subject 3> (appears in [Shot 2]): fully_preserved - exact identity and outfit from <Picture 4> are preserved.
<Subject 4> (appears in [Shot 1], [Shot 2]): fully_preserved - open wooden door and night courtyard remain consistent.
<Audio 1>: reference - <Subject 1> follows <Audio 1>'s voice timbre.
<Audio 2>: reference - <Subject 2> follows <Audio 2>'s voice timbre.

detailed_description:
{STYLE_916}
[Shot 1] A static medium-close shot in <Subject 4> frames <Subject 1> on right-center turning livid with wounded pride, pointing sharply at the old wooden rafters during 0.1-4.3 seconds as <Subject 1> (S1) sneers bitterly: <d>[Chinese] 你宁肯拿爷爷的方子填夏家这快封门的破院子？</d> Immediately upon finishing, <Subject 1> presses her lips shut glaring left.
[Shot 2] At 00:04.500, the camera cuts to a medium-close shot matching <Picture 1> beside the open wooden doorway: <Subject 2> stands tall on left-center resting her right hand steadily on the open wooden door edge with <Subject 3> standing calmly half a step behind her (lips closed), facing <Subject 1> on the right. Gesturing gracefully toward the open exit during 4.6-9.2 seconds, <Subject 2> (S2) speaks with poised, protective firmness: <d>[Chinese] 小寻跟我们合伙做正经买卖，不打零工。林同学慢走。</d> Immediately upon finishing at 9.2 seconds, <Subject 2> closes her lips and holds her calm gaze until 10.0 seconds. {TAIL_GUARD}

overall_soundscape:
Sharp intake of breath, steady palm resting on solid wooden door frame, quiet night courtyard breeze.

non_diegetic_music:
N/A""",
    },

    # 04: 3-1-09 (9s)
    {
        "id": "3-1-09",
        "shot_uuid": ep3_shots[3]["id"],
        "aspect_ratio": "9:16",
        "duration": 9,
        "seed": 3109,
        "keyframe_2k": kf2k("3-1-09"),
        "ref_images": [
            kf1k("3-1-09"),
            main_1k("林双双"),
            main_1k("夏芊芊"),
            main_1k("叶寻 · 渝清记围裙掌勺"),
            main_1k("桂花巷渝清记大堂与天井"),
        ],
        "ref_audios": [voice("林双双")],
        "prompt": f"""subject_definitions:
<Picture 1> is the first frame of [Shot 1], locking <Subject 1> snatching the iron keys and kraft ledger off the table with a cold sneer.
<Subject 1> is the person from <Picture 2>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 2>.
<Subject 2> is the person from <Picture 3>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 3>.
<Subject 3> is the person from <Picture 4>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 4>.
<Subject 4> is the night courtyard dining hall doorway from <Picture 5>.
All character sheets (<Picture 2>, <Picture 3>, <Picture 4>) provide 3D identity and outfit guidance only; never copy studio white backgrounds or multi-panel borders.
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).

summary:
[keyframe completion + reference generation + audio reference] Starting from <Picture 1> in <Subject 4>, <Subject 1> clutches the returned keys and throws down an October eighth rent taunt before storming out into the night, while <Subject 2> and <Subject 3> calmly close the wooden doors.

retention_analysis:
<Picture 1> ([Shot 1] first frame): fully_preserved - [Shot 1] starts directly from <Picture 1>.
<Subject 1> (appears in [Shot 1], [Shot 2]): fully_preserved - exact identity and outfit from <Picture 2> are preserved.
<Subject 2> (appears in [Shot 2]): fully_preserved - exact identity and outfit from <Picture 3> are preserved.
<Subject 3> (appears in [Shot 2]): fully_preserved - exact identity and outfit from <Picture 4> are preserved.
<Subject 4> (appears in [Shot 1], [Shot 2]): fully_preserved - wooden doors and night courtyard remain consistent.
<Audio 1>: reference - <Subject 1> follows <Audio 1>'s voice timbre.

detailed_description:
{STYLE_916}
[Shot 1] Starting from <Picture 1> in <Subject 4>, a static close-up frames <Subject 1> clutching the iron key ring and kraft ledger tightly in her fist. Sneering coldly toward screen-left during 0.1-4.6 seconds, <Subject 1> (S1) snaps: <d>[Chinese] 行，我倒要看看十月八号你们拿什么交房租！</d> Immediately upon finishing at 4.6 seconds, <Subject 1> presses her lips shut.
[Shot 2] At 00:04.800, the camera cuts to a medium depth shot from inside <Subject 4> looking toward the open wooden doors: <Subject 1> pivots sharply and strides out into the dark courtyard path on the right during 4.9-6.8 seconds, while in the left foreground <Subject 2> and <Subject 3> stand side by side with calm composure as <Subject 2> pushes the two heavy wooden door leaves shut together during 6.8-9.0 seconds in silence. {TAIL_GUARD}

overall_soundscape:
Sharp jingle of snatched iron keys, angry departing footsteps fading into the night, and heavy wooden doors creaking shut.

non_diegetic_music:
N/A""",
    },

    # 05: 3-2-01 (14s)
    {
        "id": "3-2-01",
        "shot_uuid": ep3_shots[4]["id"],
        "aspect_ratio": "9:16",
        "duration": 15,
        "seed": 3201,
        "keyframe_2k": kf2k("3-2-01"),
        "ref_images": [
            kf1k("3-2-01"),
            main_1k("夏建国"),
            main_1k("叶寻 · 渝清记围裙掌勺"),
            main_1k("夏芊芊"),
            main_1k("渝清记深夜账房"),
            main_1k("桂花巷18000元房租催缴单"),
        ],
        "ref_audios": [voice("夏建国"), voice("叶寻")],
        "prompt": f"""subject_definitions:
<Picture 1> is the first frame of [Shot 1], locking <Subject 1> and <Subject 2> seated at the warm wooden accounting desk of <Subject 4> with <Subject 5> on the tabletop.
<Subject 1> is the person from <Picture 2>, strictly preserving the exact facial features, hairstyle, right-wrist white bandage, and complete outfit from <Picture 2>.
<Subject 2> is the person from <Picture 3>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 3>.
<Subject 3> is the person from <Picture 4>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 4>.
<Subject 4> is the late-night accounting room from <Picture 5>.
<Subject 5> is the red-stamped rent notice sheet from <Picture 6>.
All character sheets (<Picture 2>, <Picture 3>, <Picture 4>) provide 3D identity and outfit guidance only; never copy studio white backgrounds or multi-panel borders.
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).
<Audio 2> is the voice-timbre reference for <Subject 2> (S2).

summary:
[keyframe completion + reference generation + audio reference] Starting from <Picture 1> in <Subject 4>, <Subject 1> sighs over his bandaged wrist fearing he will drag <Subject 2> down, <Subject 2> proposes rebranding as Yuqingji specializing in non-tossing dual-broth hotpot, and <Subject 2> slides his own red passbook across the desk to <Subject 3> to pool eight thousand yuan startup capital.

retention_analysis:
<Picture 1> ([Shot 1] first frame): fully_preserved - [Shot 1] starts directly from <Picture 1>.
<Subject 1> (appears in [Shot 1]): fully_preserved - exact identity, right-wrist bandage, and outfit from <Picture 2> are preserved.
<Subject 2> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - exact identity and outfit from <Picture 3> are preserved.
<Subject 3> (appears in [Shot 3]): fully_preserved - exact identity and outfit from <Picture 4> are preserved.
<Subject 4> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - green brass lamp and 75cm wooden desk remain consistent.
<Subject 5> (appears in [Shot 1], [Shot 2]): fully_preserved - white stamped notice remains consistent.
<Audio 1>: reference - <Subject 1> follows <Audio 1>'s voice timbre.
<Audio 2>: reference - <Subject 2> follows <Audio 2>'s voice timbre.

detailed_description:
{STYLE_916}
[Shot 1] Starting from <Picture 1> at the 75cm-high wooden desk of <Subject 4> (desk edge at waist height, full upper bodies visible), <Subject 1> sits on screen-right resting his uninjured left hand on <Subject 5> opposite <Subject 2> on screen-left. Sighing heavily with guilt during 0.1-4.3 seconds, <Subject 1> (S1) speaks earnestly: <d>[Chinese] 小寻，夏叔手打着夹板颠不动勺，不能把你也拖下水。</d> <Subject 2> listens calmly with lips closed.
[Shot 2] At 00:04.500, the camera cuts to a close-up of <Subject 2> on screen-left placing his steady right hand onto <Subject 5> while opening his olive canvas bag. Speaking with clear, reassuring conviction during 4.6-9.6 seconds, <Subject 2> (S2) says: <d>[Chinese] 夏叔，小炒全停，咱们改名渝清记，专做不用颠勺的子母锅清润火锅。</d>
[Shot 3] At 00:09.800, the camera cuts to a high-angle tabletop close-up as <Subject 2>'s right hand slides an open red savings passbook smoothly across the warm wood to <Subject 3>'s hand beside the wooden abacus during 9.9-13.3 seconds while <Subject 2> (S2) continues crisply: <d>[Chinese] 加上店里六千二凑齐八千本钱，十九天挣房租，来得及。</d> Quiet stillness holds until 15.0 seconds. {TAIL_GUARD}

overall_soundscape:
Heavy sigh, canvas satchel clasp click, paper passbook sliding smoothly across wooden desk.

non_diegetic_music:
N/A""",
    },

    # 06: 3-2-04 (14s) + dedicated VO #1 in [9.4..13.8s]
    {
        "id": "3-2-04",
        "shot_uuid": ep3_shots[5]["id"],
        "aspect_ratio": "9:16",
        "duration": 14,
        "seed": 3204,
        "keyframe_2k": kf2k("3-2-04"),
        "ref_images": [
            kf1k("3-2-04"),
            main_1k("夏芊芊"),
            main_1k("叶寻 · 渝清记围裙掌勺"),
            main_1k("夏建国"),
            main_1k("渝清记深夜账房"),
            main_1k("9·19手写合伙及秘方公证协议"),
        ],
        "ref_audios": [voice("夏芊芊")],
        "vo_short_spec": {
            "speaker": "叶寻",
            "ref_img": main_1k("叶寻 · 渝清记围裙掌勺"),
            "ref_aud": voice("叶寻"),
            "text": "上一世林双双哄我签走秘方，这一世，芊芊却逼我把方子攥在自己手里。",
            "emotion": "deeply moved, warm, heartfelt inner emotion",
            "dst_start": 9.35,
            "max_window": 4.45,
            "base_duck": 0.25,
        },
        "prompt": f"""subject_definitions:
<Picture 1> is the first frame of [Shot 1], locking <Subject 1> seated under the green brass lamp writing on squared letter paper with a fountain pen.
<Subject 1> is the person from <Picture 2>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 2>.
<Subject 2> is the person from <Picture 3>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 3>.
<Subject 3> is the person from <Picture 4>, strictly preserving the exact facial features, hairstyle, right-wrist white bandage, and complete outfit from <Picture 4>.
<Subject 4> is the late-night accounting room from <Picture 5>.
<Subject 5> is the handwritten squared-paper partnership agreement from <Picture 6>.
All character sheets (<Picture 2>, <Picture 3>, <Picture 4>) provide 3D identity and outfit guidance only; never copy studio white backgrounds or multi-panel borders.
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).

summary:
[keyframe completion + reference generation + audio reference] Starting from <Picture 1> in <Subject 4>, <Subject 1> looks touched by the thin passbook and uncaps her fountain pen, states the forty-nine to fifty-one controlling equity split in <Subject 2>'s favor while <Subject 3> nods, and underlines the final sole-ownership clause on <Subject 5> before sliding it to <Subject 2>.

retention_analysis:
<Picture 1> ([Shot 1] first frame): fully_preserved - [Shot 1] starts directly from <Picture 1>.
<Subject 1> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - exact identity and outfit from <Picture 2> are preserved.
<Subject 2> (appears in [Shot 2], [Shot 3]): fully_preserved - exact identity and outfit from <Picture 3> are preserved.
<Subject 3> (appears in [Shot 2]): fully_preserved - exact identity and outfit from <Picture 4> are preserved.
<Subject 4> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - green lamp and wooden desk remain consistent.
<Subject 5> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - squared paper texture remains consistent without inventing garbled subtitles.
<Audio 1>: reference - <Subject 1> follows <Audio 1>'s voice timbre.

detailed_description:
{STYLE_916}
[Shot 1] Starting from <Picture 1> in <Subject 4>, a warm close-up frames <Subject 1> gazing softly at the open red passbook for a beat before drawing out <Subject 5>, uncapping her black fountain pen with a crisp click, and putting pen to paper during 0.0-3.0 seconds with lips closed.
[Shot 2] At 00:03.100, the camera cuts to an over-the-shoulder medium-close shot past <Subject 2>'s blurred left shoulder, framing <Subject 1> writing briskly on <Subject 5> while <Subject 3> nods approvingly in the background. Writing steadily as she speaks during 3.2-9.0 seconds, <Subject 1> (S1) states clearly: <d>[Chinese] 合伙就按规矩立字据。我家出铺面家伙占四成九，你出手艺占五成一当家。</d> Immediately upon finishing at 9.0 seconds, <Subject 1> closes her lips.
[Shot 3] At 00:09.200, the camera cuts to a high-angle close-up pushing slowly in on <Subject 5> on the warm wooden desk: <Subject 1>'s hand underlines the final paragraph firmly with her fountain pen, turns the squared paper sheet around, and slides it smoothly leftward to rest before <Subject 2>'s hand during 9.3-14.0 seconds. No mouths are in frame and nobody speaks aloud. {TAIL_GUARD}

overall_soundscape:
Fountain pen cap click, crisp nib scratching smoothly across squared paper, paper sliding softly across wood.

non_diegetic_music:
N/A""",
    },

    # 07: 3-2-07 (12s)
    {
        "id": "3-2-07",
        "shot_uuid": ep3_shots[6]["id"],
        "aspect_ratio": "9:16",
        "duration": 13,
        "seed": 3207,
        "keyframe_2k": kf2k("3-2-07"),
        "ref_images": [
            kf1k("3-2-07"),
            main_1k("叶寻 · 渝清记围裙掌勺"),
            main_1k("夏芊芊"),
            main_1k("夏建国"),
            main_1k("渝清记深夜账房"),
            main_1k("9·19手写合伙及秘方公证协议"),
        ],
        "ref_audios": [voice("叶寻"), voice("夏芊芊"), voice("夏建国")],
        "prompt": f"""subject_definitions:
<Picture 1> is the composition and blocking keyframe for [Shot 3], locking <Subject 1> on screen-left, <Subject 2> on screen-right, and <Subject 3> center-back around the warm desk of <Subject 4>.
<Subject 1> is the person from <Picture 2>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 2>.
<Subject 2> is the person from <Picture 3>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 3>.
<Subject 3> is the person from <Picture 4>, strictly preserving the exact facial features, hairstyle, right-wrist white bandage, and complete outfit from <Picture 4>.
<Subject 4> is the late-night accounting room from <Picture 5>.
<Subject 5> is the handwritten partnership agreement from <Picture 6>.
All character sheets (<Picture 2>, <Picture 3>, <Picture 4>) provide 3D identity and outfit guidance only; never copy studio white backgrounds or multi-panel borders.
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).
<Audio 2> is the voice-timbre reference for <Subject 2> (S2).
<Audio 3> is the voice-timbre reference for <Subject 3> (S3).

summary:
[keyframe completion + reference generation + audio reference] In <Subject 4>, <Subject 1> looks up deeply moved asking why <Subject 2> carved his recipe ownership out separately, <Subject 2> answers firmly she refuses to sign otherwise, and in <Picture 1> <Subject 3> pushes the red inkpad forward calling on everyone to press their thumbprints.

retention_analysis:
<Picture 1> ([Shot 3] keyframe): fully_preserved - [Shot 3] matches <Picture 1>'s three-person desk blocking.
<Subject 1> (appears in [Shot 1], [Shot 3]): fully_preserved - exact identity and outfit from <Picture 2> are preserved.
<Subject 2> (appears in [Shot 2], [Shot 3]): fully_preserved - exact identity and outfit from <Picture 3> are preserved.
<Subject 3> (appears in [Shot 3]): fully_preserved - exact identity, right-wrist bandage, and outfit from <Picture 4> are preserved.
<Subject 4> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - green lamp, red inkpad, and wooden desk remain consistent.
<Subject 5> (appears in [Shot 2], [Shot 3]): fully_preserved - handwritten agreement sheet remains consistent.
<Audio 1>: reference - <Subject 1> follows <Audio 1>'s voice timbre.
<Audio 2>: reference - <Subject 2> follows <Audio 2>'s voice timbre.
<Audio 3>: reference - <Subject 3> follows <Audio 3>'s voice timbre.

detailed_description:
{STYLE_916}
[Shot 1] A tight warm close-up on <Subject 1> on left-center in <Subject 4> shows him raising his eyes from the desk toward screen-right, deeply moved. Speaking softly in a slightly husky voice during 0.1-3.1 seconds, <Subject 1> (S1) asks: <d>[Chinese] 你把方子单摘出来了？</d> Immediately upon finishing, <Subject 1> closes his lips.
[Shot 2] At 00:03.300, the camera cuts to a close-up of <Subject 2> on right-center meeting his eyes with crystal-clear sincerity as she sets the fountain pen beside <Subject 5>. During 3.4-7.8 seconds, <Subject 2> (S2) speaks warmly and firmly: <d>[Chinese] 叶爷爷留给你的家底，少写这一条，这字我不签。</d> Immediately upon finishing, <Subject 2> closes her lips.
[Shot 3] At 00:08.000, the camera cuts to a medium-close three-shot matching <Picture 1> around the 75cm-high desk: <Subject 1> on screen-left picks up the pen with a firm nod (lips closed), <Subject 2> smiles on screen-right (lips closed), and <Subject 3> in center-back pushes the open bright-red inkpad box to the center of <Subject 5> with his uninjured left hand during 8.1-11.2 seconds, saying heartily: <d>[Chinese] 听芊芊的！来，摁手印！</d> Warm stillness holds until 13.0 seconds. {TAIL_GUARD}

overall_soundscape:
Fountain pen set gently beside paper, red inkpad box sliding onto center of wooden desk, warm quiet room tone.

non_diegetic_music:
N/A""",
    },

    # 08: 3-2-10 (11s) + dedicated VO #2 in [0.3..3.2s]
    {
        "id": "3-2-10",
        "shot_uuid": ep3_shots[7]["id"],
        "aspect_ratio": "9:16",
        "duration": 11,
        "seed": 3210,
        "keyframe_2k": kf2k("3-2-10"),
        "ref_images": [
            kf1k("3-2-10"),
            main_1k("周有福"),
            main_1k("夏建国"),
            main_1k("叶寻 · 渝清记围裙掌勺"),
            main_1k("夏芊芊"),
            main_1k("桂花巷渝清记大堂与天井"),
        ],
        "ref_audios": [voice("周有福")],
        "vo_short_spec": {
            "speaker": "叶寻",
            "ref_img": main_1k("叶寻 · 渝清记围裙掌勺"),
            "ref_aud": voice("叶寻"),
            "text": "五一控股落印，渝清记今晚正式立字！",
            "emotion": "steady, resolute inner vow",
            "dst_start": 0.25,
            "max_window": 3.05,
            "base_duck": 0.30,
        },
        "prompt": f"""subject_definitions:
<Picture 1> is the first frame of [Shot 1], showing the overhead close-up of the third bright-red thumbprint being pressed onto the bottom of the handwritten agreement.
<Subject 1> is the person from <Picture 2>, strictly preserving the exact facial features, hairstyle, belt keys, and complete outfit from <Picture 2>.
<Subject 2> is the person from <Picture 3>, strictly preserving the exact facial features, hairstyle, right-wrist white bandage, and complete outfit from <Picture 3>.
<Subject 3> is the person from <Picture 4>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 4>.
<Subject 4> is the person from <Picture 5>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 5>.
<Subject 5> is the night courtyard dining hall and accounting table from <Picture 6>.
All character sheets (<Picture 2> to <Picture 5>) provide 3D identity and outfit guidance only; never copy studio white backgrounds or multi-panel borders.
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).

summary:
[keyframe completion + reference generation + audio reference] Starting from <Picture 1>, the third red thumbprint seals the partnership agreement right before the courtyard door crashes open, <Subject 1> barges into <Subject 5> slamming a heavy iron pipe wrench onto the table corner in front of <Subject 2>, <Subject 3>, and <Subject 4>, and announces a rival boss just paid a two-thousand-yuan deposit.

retention_analysis:
<Picture 1> ([Shot 1] first frame): fully_preserved - [Shot 1] starts directly from <Picture 1>.
<Subject 1> (appears in [Shot 2], [Shot 3]): fully_preserved - exact identity and outfit from <Picture 2> are preserved.
<Subject 2> (appears in [Shot 2]): fully_preserved - exact identity and outfit from <Picture 3> are preserved.
<Subject 3> (appears in [Shot 2]): fully_preserved - exact identity and outfit from <Picture 4> are preserved.
<Subject 4> (appears in [Shot 1], [Shot 2]): fully_preserved - exact identity and outfit from <Picture 5> are preserved.
<Subject 5> (appears in [Shot 2], [Shot 3]): fully_preserved - wooden doors and accounting table remain consistent.
<Audio 1>: reference - <Subject 1> follows <Audio 1>'s voice timbre.

detailed_description:
{STYLE_916}
[Shot 1] Starting from <Picture 1>, a high-angle close-up shows <Subject 4>'s right thumb pressing the third vivid red thumbprint onto the bottom of the handwritten agreement and lifting cleanly at 2.2 seconds to reveal three aligned red thumbprints; suddenly at 3.1 seconds a loud door bang from off-screen jolts the tabletop slightly. No mouths are in frame.
[Shot 2] At 00:03.400, the camera cuts to a medium tracking shot inside <Subject 5> panning leftward as <Subject 1> barges across the open doorway from screen-right clutching a white receipt in his left hand and a heavy dark-red iron pipe wrench in his right, marching up to the right corner of the wooden table (where <Subject 2>, <Subject 3>, and <Subject 4> look up on screen-left) and slamming the heavy iron pipe wrench loudly onto the table corner at 6.8 seconds, silent with lips closed.
[Shot 3] At 00:07.000, the camera cuts to a close-up of <Subject 1> on right-center resting his right hand on the iron pipe wrench and shaking the white deposit receipt in his left hand toward screen-left. Speaking in a loud, overbearing voice during 7.1-10.3 seconds, <Subject 1> (S1) declares: <d>[Chinese] 老夏，正街改西餐厅的楚老板刚交两千定金，</d> Immediately upon finishing at 10.3 seconds, <Subject 1> closes his lips with a greedy glare until 11.0 seconds. {TAIL_GUARD}

overall_soundscape:
Soft thumb press on paper, sudden loud wooden door bang, heavy footsteps and jangling belt keys, heavy metallic thud of iron pipe wrench slammed onto wooden table, crisp receipt paper shake.

non_diegetic_music:
N/A""",
    },

    # 09: 3-2-13 (14s)
    {
        "id": "3-2-13",
        "shot_uuid": ep3_shots[8]["id"],
        "aspect_ratio": "9:16",
        "duration": 14,
        "seed": 3213,
        "keyframe_2k": kf2k("3-2-13"),
        "ref_images": [
            kf1k("3-2-13"),
            main_1k("周有福"),
            main_1k("夏建国"),
            main_1k("叶寻 · 渝清记围裙掌勺"),
            main_1k("桂花巷渝清记大堂与天井"),
        ],
        "ref_audios": [voice("周有福"), voice("夏建国")],
        "prompt": f"""subject_definitions:
<Picture 1> is the first frame of [Shot 1], locking <Subject 1> on screen-right with his hand on the heavy iron pipe wrench facing <Subject 2> and <Subject 3> on screen-left in <Subject 4>.
<Subject 1> is the person from <Picture 2>, strictly preserving the exact facial features, hairstyle, belt keys, and complete outfit from <Picture 2>.
<Subject 2> is the person from <Picture 3>, strictly preserving the exact facial features, hairstyle, right-wrist white bandage, and complete outfit from <Picture 3>.
<Subject 3> is the person from <Picture 4>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 4>.
<Subject 4> is the night courtyard dining hall from <Picture 5>.
All character sheets (<Picture 2>, <Picture 3>, <Picture 4>) provide 3D identity and outfit guidance only; never copy studio white backgrounds or multi-panel borders.
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).
<Audio 2> is the voice-timbre reference for <Subject 2> (S2).

summary:
[keyframe completion + reference generation + audio reference] Starting from <Picture 1> in <Subject 4>, <Subject 1> says the rival boss rented the yard for storage, <Subject 2> stands up angrily asking why he brought a pipe wrench before October eighth, <Subject 1> threatens to shut off the backyard water meter tonight, and <Subject 3> steps squarely in front of the narrow backyard doorway blocking him cold.

retention_analysis:
<Picture 1> ([Shot 1] first frame): fully_preserved - [Shot 1] starts directly from <Picture 1>.
<Subject 1> (appears in [Shot 1], [Shot 3], [Shot 4]): fully_preserved - exact identity and outfit from <Picture 2> are preserved.
<Subject 2> (appears in [Shot 1], [Shot 2]): fully_preserved - exact identity, right-wrist bandage, and outfit from <Picture 3> are preserved.
<Subject 3> (appears in [Shot 1], [Shot 2], [Shot 4]): fully_preserved - exact identity and outfit from <Picture 4> are preserved.
<Subject 4> (appears in [Shot 1], [Shot 2], [Shot 3], [Shot 4]): fully_preserved - wooden table and narrow backyard door remain consistent.
<Audio 1>: reference - <Subject 1> follows <Audio 1>'s voice timbre.
<Audio 2>: reference - <Subject 2> follows <Audio 2>'s voice timbre.

detailed_description:
{STYLE_916}
[Shot 1] Starting from <Picture 1> in <Subject 4>, <Subject 1> stands on screen-right gesturing across the courtyard toward <Subject 2> and <Subject 3> on screen-left. Immediately during 0.1-2.5 seconds, <Subject 1> (S1) continues bluntly: <d>[Chinese] 要租你这院子堆酒水杂物！</d>
[Shot 2] At 00:02.600, the camera cuts to a medium-close shot on the left side of the table as <Subject 2> pushes his wooden bench back and stands up indignantly alongside <Subject 3> (lips closed). Pointing his left hand at the iron pipe wrench during 2.7-6.4 seconds, <Subject 2> (S2) demands angrily: <d>[Chinese] 老周，十月八号才到期，你拎管钳干啥？</d> Immediately upon finishing, <Subject 2> closes his lips.
[Shot 3] At 00:06.500, the camera cuts to a close-up of <Subject 1> on right-center snatching the heavy iron pipe wrench off the table corner and hefting it menacingly. Sneering during 6.6-10.7 seconds, <Subject 1> (S1) says: <d>[Chinese] 人家怕你们到期赖着不搬，让我今晚先把后院副水表拧了！</d> Immediately upon finishing, <Subject 1> closes his lips and turns to step toward the backyard doorway.
[Shot 4] At 00:10.900, the camera cuts to a fast push-in medium-close two-shot in front of the narrow wooden backyard door: the instant <Subject 1> steps rightward lifting the iron pipe wrench, <Subject 3> steps sideways in one decisive stride on screen-left to plant himself squarely across the center of the narrow doorway, locking an icy, immovable gaze onto <Subject 1> and bringing him to an abrupt halt during 11.0-14.0 seconds in tense silence. {TAIL_GUARD}

overall_soundscape:
Wooden bench scraping stone, metallic heft of heavy iron pipe wrench, and one sharp sneaker plant halting heavy footsteps dead.

non_diegetic_music:
N/A""",
    },
]


def main():
    issues = []
    for plan in (EP2_PLAN, EP3_PLAN):
        for sp in plan:
            issues.extend(lint_zero_appearance(sp["prompt"], sp["id"]))
    if issues:
        for i in issues:
            print("LINT ERROR:", i, file=sys.stderr)
        sys.exit(2)

    (WORK_DIR / "ep02_plan.json").write_text(json.dumps(EP2_PLAN, ensure_ascii=False, indent=2), encoding="utf-8")
    (WORK_DIR / "ep03_plan.json").write_text(json.dumps(EP3_PLAN, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"LINT OK! Saved ep02_plan.json ({len(EP2_PLAN)} shots) and ep03_plan.json ({len(EP3_PLAN)} shots).")


if __name__ == "__main__":
    main()
