#!/usr/bin/env python3
"""Compile Episode 1 (12 generation groups, 137s, 9:16) zero-appearance Pika-H3-Flex 480p video plan."""
import json
import sys
from pathlib import Path

SKILL_SCRIPTS = Path("/home/zhongwenyu/project/ai-director-train/.agents/skills/hit-video/scripts")
sys.path.insert(0, str(SKILL_SCRIPTS))
from pika_runner import lint_zero_appearance  # noqa: E402

PROJECT_JSON = Path("/home/zhongwenyu/project/playlets-studio/playlets/playlet-mwj57ecn-9658ad48/project.json")
WORK_DIR = Path("/home/zhongwenyu/project/ai-director-train/productions/2005_chongqing_hotpot/ep01_video_gen")

proj = json.loads(PROJECT_JSON.read_text(encoding="utf-8"))
ep1 = proj["episodes"][0]
shots_by_idx = ep1["shots"]
asset_map = json.loads((WORK_DIR / "ep01_asset_map.json").read_text(encoding="utf-8"))

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
    return asset_map[name]["main_1k"]


def voice(name: str) -> str:
    return asset_map[name]["voice_wav"]


PLAN = [
    # 01: 1-1-01 (9s)
    {
        "id": "1-1-01",
        "shot_uuid": shots_by_idx[0]["id"],
        "episode": ep1["title"],
        "aspect_ratio": "9:16",
        "duration": 9,
        "seed": 9101,
        "keyframe_2k": kf2k("1-1-01"),
        "asset_names": ["叶寻 · 2015行政总厨", "林双双 · 2015女董事长", "楚南 · 海归并购总监西装", "赵帆", "双林轩总部顶层试菜厅", "配方无偿归属确认书与调岗单"],
        "dialogue": "",
        "description": (
            "drama-key:1-1-01\n"
            "0.0–2.5s 1-1-01 特写 俯拍 固定：叶寻带旧烫疤的右手签完确认书最后一笔，林双双右手瞬间将文件往右侧抽走。\n"
            "2.5–5.5s 1-1-02 中近景 平视 固定：林双双在右侧将确认书塞入黑色公文包合盖，楚南在中间一把扯下叶寻左胸的黑金铭牌。\n"
            "5.5–9.0s 1-1-03 近景 平视 横移：楚南半转身向右将铭牌啪地吸扣在身旁赵帆左胸前，赵帆得意挺胸斜睨左侧。"
        ),
        "ref_images": [
            kf1k("1-1-01"),
            main_1k("叶寻 · 2015行政总厨"),
            main_1k("楚南 · 海归并购总监西装"),
            main_1k("赵帆"),
            main_1k("林双双 · 2015女董事长"),
            main_1k("双林轩总部顶层试菜厅"),
            main_1k("配方无偿归属确认书与调岗单"),
        ],
        "ref_audios": [],
        "prompt": f"""subject_definitions:
<Picture 1> is the composition and blocking keyframe for [Shot 2], defining the exact four-person spatial placement around the marble tasting table.
<Subject 1> is the person from <Picture 2>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 2> without modification.
<Subject 2> is the person from <Picture 3>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 3> without modification.
<Subject 3> is the person from <Picture 4>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 4> without modification.
<Subject 4> is the person from <Picture 5>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 5> without modification.
<Subject 5> is the executive tasting room from <Picture 6>, preserving its white marble table, recessed copper hotpot, and rainy night window backdrop.
<Subject 6> is the stamped agreement document and rectangular black-and-gold chest badge from <Picture 7>.
All character sheets (<Picture 2> to <Picture 5>) provide 3D identity and outfit guidance only; never copy studio white backgrounds or multi-panel borders.

summary:
[keyframe completion + reference generation] Across three crisp cuts in <Subject 5>, <Subject 1> finishes signing <Subject 6> before <Subject 4> snatches it away, <Subject 2> rips the chest badge off <Subject 1> in the four-person layout of <Picture 1>, and <Subject 2> snaps that badge onto <Subject 3>'s chest.

retention_analysis:
<Picture 1> ([Shot 2] keyframe): fully_preserved - [Shot 2] matches <Picture 1>'s four-person left-to-right placement and framing.
<Subject 1> (appears in [Shot 1], [Shot 2]): fully_preserved - exact identity and outfit from <Picture 2> are preserved.
<Subject 2> (appears in [Shot 2], [Shot 3]): fully_preserved - exact identity and outfit from <Picture 3> are preserved.
<Subject 3> (appears in [Shot 2], [Shot 3]): fully_preserved - exact identity and outfit from <Picture 4> are preserved.
<Subject 4> (appears in [Shot 1], [Shot 2]): fully_preserved - exact identity and outfit from <Picture 5> are preserved.
<Subject 5> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - marble table geometry and crisp overhead lighting remain consistent.
<Subject 6> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - single agreement document and single black-and-gold badge maintain consistent shape.

detailed_description:
{STYLE_916}
[Shot 1] A static top-down close-up onto the white marble tabletop of <Subject 5> shows the white agreement paper of <Subject 6>. <Subject 1>'s right hand, bearing an old burn scar on the thumb web, enters from screen-left holding a black pen and completes the final stroke of a signature at 0.0-0.8 seconds. The instant the pen tip lifts at 0.9 seconds, <Subject 4>'s right hand enters sharply from screen-right and snatches the signed paper briskly off the table to the right during 0.9-2.2 seconds, leaving only the pen in <Subject 1>'s tense fingers.
[Shot 2] At 00:02.500, the camera cuts to a static eye-level medium-close four-shot matching the exact blocking of <Picture 1>: standing behind the 75cm-high marble table (table edge at upper-thigh height), <Subject 1> stands on screen-left facing right with the black-and-gold badge on his left chest, <Subject 2> stands left-of-center reaching toward <Subject 1>, <Subject 3> stands just right of <Subject 2> with arms crossed, and <Subject 4> stands at screen-right. During 2.6-4.2 seconds, <Subject 4> slides the signed paper into a black leather briefcase on the table and snaps the flap shut, while simultaneously <Subject 2>'s right hand grabs and rips the magnetic badge sharply off <Subject 1>'s left chest with a smug sneer. During 4.2-5.4 seconds, <Subject 1> freezes in shock and looks down at his bare chest.
[Shot 3] At 00:05.500, the camera cuts to a tight medium-close two-shot on the right side of the same 180-degree axis framing <Subject 2> on screen-left and <Subject 3> standing right beside him on screen-right. As <Subject 2> pivots half-right holding the badge during 5.6-7.2 seconds, the camera pans smoothly 25 centimeters rightward at medium speed to center on <Subject 3>, where <Subject 2> snaps the magnetic black-and-gold badge firmly onto <Subject 3>'s left chest with an audible click. During 7.2-9.0 seconds, <Subject 3> puffs his chest out arrogantly and raises his chin, casting a gloating sideways smirk toward screen-left while <Subject 2> arches a mocking eyebrow. {TAIL_GUARD}

overall_soundscape:
Crisp pen scratch on paper, sharp paper snatch, leather briefcase clasp click, metallic badge rip and snap-click, over continuous muffled rain and distant thunder outside the glass windows.

non_diegetic_music:
N/A
""",
    },

    # 02: 1-1-04 (13s - upgraded v1.1: +1s tail buffer & simultaneous spoon-set + speech so '撤掉' never clips!)
    {
        "id": "1-1-04",
        "shot_uuid": shots_by_idx[1]["id"],
        "episode": ep1["title"],
        "aspect_ratio": "9:16",
        "duration": 13,
        "seed": 10102,
        "keyframe_2k": kf2k("1-1-04"),
        "asset_names": ["叶寻 · 2015行政总厨", "赵帆", "双林轩总部顶层试菜厅"],
        "dialogue": "叶寻 · 2015行政总厨：谁让你往母汤里倒奶油的？草本回甘全毁了！\n赵帆：明早路演主桌改上法式浓汤锅，原版红汤撤掉。",
        "description": (
            "drama-key:1-1-04\n"
            "0.0–3.2s 1-1-04 中近景 斜俯 推近：赵帆将整罐淡奶油哗啦倒进翻滚的琥珀红汤铜锅，白腻浮沫瞬间吞没红汤。\n"
            "3.2–7.0s 1-1-05 近景 越肩 固定：叶寻右手猛按锅边大理石台面，震怒质问赵帆。\n"
            "7.0–13.0s 1-1-06 近景 反打越肩 固定：赵帆放下银勺高傲扬下巴，冷笑下令撤掉原版红汤。"
        ),
        "ref_images": [
            kf1k("1-1-04"),
            main_1k("叶寻 · 2015行政总厨"),
            main_1k("赵帆"),
            main_1k("双林轩总部顶层试菜厅"),
        ],
        "ref_audios": [
            voice("叶寻 · 2015行政总厨"),
            voice("赵帆"),
        ],
        "prompt": f"""subject_definitions:
<Picture 1> is the first frame of [Shot 1], locking the initial two-person blocking beside the boiling copper red-broth hotpot.
<Subject 1> is the person from <Picture 2>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 2> without modification.
<Subject 2> is the person from <Picture 3>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 3> without modification.
<Subject 3> is the executive tasting room from <Picture 4>, preserving its marble table, recessed copper hotpot, and bright modern lighting.
All character sheets (<Picture 2>, <Picture 3>) provide 3D identity and outfit guidance only; never copy studio white backgrounds or multi-panel borders.
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).
<Audio 2> is the voice-timbre reference for <Subject 2> (S2).

summary:
[keyframe completion + reference generation + audio reference] Starting from <Picture 1> in <Subject 3>, <Subject 2> pours thick white cream into the boiling red hotpot broth, <Subject 1> slams his hand beside the pot and confronts him angrily, and <Subject 2> sets down a tasting spoon and arrogantly orders the original red broth replaced, following <Audio 1> and <Audio 2> for vocal timbre.

retention_analysis:
<Picture 1> ([Shot 1] first frame): fully_preserved - [Shot 1] begins directly from <Picture 1>'s framing and positions.
<Subject 1> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - exact identity and outfit from <Picture 2> are preserved across all cuts.
<Subject 2> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - exact identity and outfit from <Picture 3> are preserved across all cuts.
<Subject 3> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - marble table and central copper hotpot remain consistent.
<Audio 1>: reference - <Subject 1> follows <Audio 1>'s voice timbre without copying the source recording.
<Audio 2>: reference - <Subject 2> follows <Audio 2>'s voice timbre without copying the source recording.

detailed_description:
{STYLE_916}
[Shot 1] Starting from <Picture 1>, an angled high-eye-level medium-close shot frames the boiling amber-red broth in the recessed copper pot of <Subject 3>, with <Subject 1> standing on screen-left and <Subject 2> standing on screen-right holding a glass pitcher of thick white cream above the pot. During 0.1-3.0 seconds, <Subject 2> tilts the pitcher with a dismissive smirk and pours a heavy stream of thick white cream straight into the simmering red broth; as greasy white foam churns across the surface, the camera pushes in smoothly at medium speed toward the bubbling milky pot while <Subject 1> lunges half a step forward in shock with lips closed.
[Shot 2] At 00:03.200, the camera cuts to a static close over-the-shoulder shot from the same side of the 180-degree axis, with <Subject 2>'s blurred shoulder on the right foreground and <Subject 1> on left-center leaning intensely forward. At 3.3 seconds <Subject 1> slams his right palm firmly onto the marble table edge beside the pot and immediately shouts in a sharp, outraged young male voice (<Subject 1> (S1)) at a brisk pace during 3.4-6.7 seconds: <d>[Chinese] 谁让你往母汤里倒奶油的？草本回甘全毁了！</d> His lips move clearly with every syllable while <Subject 2>'s foreground shoulder stays unbothered.
[Shot 3] At 00:07.000, the camera cuts to the reverse static close over-the-shoulder shot from the same 180-degree axis, with <Subject 1>'s blurred left shoulder in the left foreground and <Subject 2> on right-center behind the milky pot setting a silver tasting spoon onto a small dish at 7.1-7.5 seconds. Immediately at 7.5 seconds, lifting his chin haughtily with a smug sideways sneer, <Subject 2> (S2) speaks in an oily, condescending male voice at a brisk pace during 7.5-11.6 seconds: <d>[Chinese] 明早路演主桌改上法式浓汤锅，原版红汤撤掉。</d> His lips articulate the entire sentence including the final words clearly, holding a cold smirk during 11.6-13.0 seconds while <Subject 1> clenches his jaw with lips closed. {TAIL_GUARD}

overall_soundscape:
Heavy liquid pouring and sizzling into boiling broth, a sharp palm slam on marble, a crisp silver spoon clink at 7.3 seconds, and steady rain outside.

non_diegetic_music:
N/A
""",
    },

    # 03: 1-1-07 (10s)
    {
        "id": "1-1-07",
        "shot_uuid": shots_by_idx[2]["id"],
        "episode": ep1["title"],
        "aspect_ratio": "9:16",
        "duration": 10,
        "seed": 9103,
        "keyframe_2k": kf2k("1-1-07"),
        "asset_names": ["叶寻 · 2015行政总厨", "楚南 · 海归并购总监西装", "赵帆", "双林轩总部顶层试菜厅"],
        "dialogue": "楚南 · 海归并购总监西装：叶师傅，外资投行认海归履历，赵主厨比你体面。\n叶寻 · 2015行政总厨：双双，方子墨迹还没干，你就撤我的灶？",
        "description": (
            "drama-key:1-1-07\n"
            "0.0–2.0s 1-1-07 中近景 斜俯 固定：楚南右手将老仓调岗单与塑料工牌重重拍在叶寻手旁大理石台面上。\n"
            "2.0–6.0s 1-1-08 近景 侧角 固定：楚南双手插兜居高临下讥讽叶寻，后方赵帆抱臂冷笑。\n"
            "6.0–10.0s 1-1-09 近景 正偏左 固定：叶寻松开锅边猛然转头盯向右侧林双双方向，声音颤抖质问。"
        ),
        "ref_images": [
            kf1k("1-1-07"),
            main_1k("叶寻 · 2015行政总厨"),
            main_1k("楚南 · 海归并购总监西装"),
            main_1k("赵帆"),
            main_1k("双林轩总部顶层试菜厅"),
        ],
        "ref_audios": [
            voice("楚南 · 海归并购总监西装"),
            voice("叶寻 · 2015行政总厨"),
        ],
        "prompt": f"""subject_definitions:
<Picture 1> is the first frame of [Shot 1], locking the three-person spatial blocking around the marble tasting table.
<Subject 1> is the person from <Picture 2>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 2> without modification.
<Subject 2> is the person from <Picture 3>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 3> without modification.
<Subject 3> is the person from <Picture 4>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 4> without modification.
<Subject 4> is the executive tasting room from <Picture 5>, preserving its marble table and modern lighting.
All character sheets (<Picture 2> to <Picture 4>) provide 3D identity and outfit guidance only; never copy studio white backgrounds or multi-panel borders.
<Audio 1> is the voice-timbre reference for <Subject 2> (S1).
<Audio 2> is the voice-timbre reference for <Subject 1> (S2).

summary:
[keyframe completion + reference generation + audio reference] Starting from <Picture 1> in <Subject 4>, <Subject 2> slaps a transfer notice and plastic ID card onto the marble tabletop beside <Subject 1>'s hand, mocks <Subject 1> arrogantly while <Subject 3> smirks behind him, and <Subject 1> turns sharply to confront the far right end of the table, following <Audio 1> and <Audio 2>.

retention_analysis:
<Picture 1> ([Shot 1] first frame): fully_preserved - [Shot 1] begins directly from <Picture 1>.
<Subject 1> (appears in [Shot 1], [Shot 3]): fully_preserved - exact identity and outfit from <Picture 2> are preserved.
<Subject 2> (appears in [Shot 1], [Shot 2]): fully_preserved - exact identity and outfit from <Picture 3> are preserved.
<Subject 3> (appears in [Shot 1], [Shot 2]): fully_preserved - exact identity and outfit from <Picture 4> are preserved.
<Subject 4> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - marble table and rainy window backdrop remain consistent.
<Audio 1>: reference - <Subject 2> follows <Audio 1>'s voice timbre without copying the source recording.
<Audio 2>: reference - <Subject 1> follows <Audio 2>'s voice timbre without copying the source recording.

detailed_description:
{STYLE_916}
[Shot 1] Starting from <Picture 1>, a static high-angle medium-close shot frames <Subject 1> on screen-left with his right hand gripping the marble table edge, <Subject 2> on screen-right, and <Subject 3> in the right background of <Subject 4>. During 0.1-1.4 seconds, <Subject 2> brings his right hand sharply down and slaps a plastic ID card and white notice sheet flat onto the marble tabletop right beside <Subject 1>'s hand with a loud snap, then withdraws his hand as <Subject 1>'s fingers curl into a tight fist.
[Shot 2] At 00:02.000, the camera cuts to a static eye-level close shot on the right side of the 180-degree axis framing <Subject 2> on right-center facing screen-left, with <Subject 3> standing blurred in the right background folding his arms with a smug grin. <Subject 2> slides both hands into his pockets, leans his upper body slightly forward to look <Subject 1> up and down with disdain, and <Subject 2> (S1) speaks in a smooth, patronizing male voice at a brisk pace during 2.2-5.8 seconds: <d>[Chinese] 叶师傅，外资投行认海归履历，赵主厨比你体面。</d> His lips move clearly with the complete line, ending in a crooked sneer while <Subject 3> nods smugly with lips closed.
[Shot 3] At 00:06.000, the camera cuts to a static close-up on <Subject 1> on left-center facing screen-right against the rain-streaked glass window of <Subject 4>. At 6.1-6.6 seconds <Subject 1> releases the table edge and snaps his head sharply toward the far screen-right end of the table, eyes reddened with disbelief and betrayal. <Subject 1> (S2), speaking in a tight, trembling yet forceful male voice at a brisk pace during 6.6-9.8 seconds, demands: <d>[Chinese] 双双，方子墨迹还没干，你就撤我的灶？</d> His lips match every word clearly as his chest rises and locks in tense silence. {TAIL_GUARD}

overall_soundscape:
Sharp slap of a plastic badge on marble, subtle fabric rustle, a sharp intake of breath, and rain beating against the glass window with a low rumble of thunder.

non_diegetic_music:
N/A
""",
    },

    # 04: 1-1-10 (13s) - Restores S05 + S06 + S07!
    {
        "id": "1-1-10",
        "shot_uuid": shots_by_idx[3]["id"],
        "episode": ep1["title"],
        "aspect_ratio": "9:16",
        "duration": 13,
        "seed": 9104,
        "keyframe_2k": kf2k("1-1-10"),
        "asset_names": ["林双双 · 2015女董事长", "叶寻 · 2015行政总厨", "楚南 · 海归并购总监西装", "双林轩总部顶层试菜厅"],
        "dialogue": (
            "林双双 · 2015女董事长：方子已经归档入库，谁看火都一样。\n"
            "叶寻 · 2015行政总厨：十年心血我全给了公司，连明早路演都不让我露面？\n"
            "林双双 · 2015女董事长：见机构要注意团队形象。老仓清静，工资照发，你别让我为难。"
        ),
        "description": (
            "drama-key:1-1-10\n"
            "0.0–3.5s 1-1-10 近景 斜侧 缓推：林双双双手咔哒按死公文包两侧黄铜锁扣，低垂眼帘冷漠回应。\n"
            "3.5–8.0s 1-1-11 特写 正偏侧 固定：叶寻喉结滚动，满眼寒心悲愤追问十年心血。\n"
            "8.0–13.0s 1-1-12 中近景 越肩 固定：林双双冷淡抬眼拎起公文包侧身欲走，丢下逐客令，楚南在旁冷笑。"
        ),
        "ref_images": [
            kf1k("1-1-10"),
            main_1k("林双双 · 2015女董事长"),
            main_1k("叶寻 · 2015行政总厨"),
            main_1k("楚南 · 海归并购总监西装"),
            main_1k("双林轩总部顶层试菜厅"),
        ],
        "ref_audios": [
            voice("林双双 · 2015女董事长"),
            voice("叶寻 · 2015行政总厨"),
        ],
        "prompt": f"""subject_definitions:
<Picture 1> is the first frame of [Shot 1], locking the three-person spatial blocking with the black briefcase on the marble table.
<Subject 1> is the person from <Picture 2>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 2> without modification.
<Subject 2> is the person from <Picture 3>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 3> without modification.
<Subject 3> is the person from <Picture 4>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 4> without modification.
<Subject 4> is the executive tasting room from <Picture 5>, preserving its marble table and cool overhead lighting.
All character sheets (<Picture 2> to <Picture 4>) provide 3D identity and outfit guidance only; never copy studio white backgrounds or multi-panel borders.
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).
<Audio 2> is the voice-timbre reference for <Subject 2> (S2).

summary:
[keyframe completion + reference generation + audio reference] Starting from <Picture 1> in <Subject 4>, <Subject 1> locks the brass clasps of her black briefcase while dismissing <Subject 2> without looking up, <Subject 2> asks in heartbroken disbelief about his ten years of devotion, and <Subject 1> picks up the briefcase to leave with cold finality beside <Subject 3>, following <Audio 1> and <Audio 2>.

retention_analysis:
<Picture 1> ([Shot 1] first frame): fully_preserved - [Shot 1] begins directly from <Picture 1>'s framing and positions.
<Subject 1> (appears in [Shot 1], [Shot 3]): fully_preserved - exact identity and outfit from <Picture 2> are preserved.
<Subject 2> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - exact identity and outfit from <Picture 3> are preserved.
<Subject 3> (appears in [Shot 1], [Shot 3]): fully_preserved - exact identity and outfit from <Picture 4> are preserved.
<Subject 4> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - marble table and lighting remain consistent.
<Audio 1>: reference - <Subject 1> follows <Audio 1>'s voice timbre without copying the source recording.
<Audio 2>: reference - <Subject 2> follows <Audio 2>'s voice timbre without copying the source recording.

detailed_description:
{STYLE_916}
[Shot 1] Starting from <Picture 1>, a medium-close shot frames <Subject 2>'s blurred shoulder on the left foreground, <Subject 1> standing at right-center behind the marble table of <Subject 4> with both thumbs poised on the brass latches of a closed black leather briefcase, and <Subject 3> standing beside her at screen-right. At 0.1-0.6 seconds <Subject 1> presses both brass latches shut with two crisp clicks and folds her hands on the briefcase handle while keeping her eyelids coldly lowered, refusing to look at <Subject 2>. As the camera pushes in at modest speed toward <Subject 1>'s icy face, <Subject 1> (S1) speaks in a detached, businesslike female voice at a brisk pace during 0.6-3.3 seconds: <d>[Chinese] 方子已经归档入库，谁看火都一样。</d> Her lips move clearly with the line while <Subject 3> smirks silently with lips closed.
[Shot 2] At 00:03.500, the camera cuts to a static tight close-up of <Subject 2> on left-center facing screen-right against defocused cool ceiling lights. <Subject 2> swallows hard, eyes shattering from shock into bitter chill, jaw trembling visibly as <Subject 2> (S2) speaks in a hoarse, devastated male voice at a brisk pace during 3.7-7.8 seconds: <d>[Chinese] 十年心血我全给了公司，连明早路演都不让我露面？</d> His lips move clearly with every word, clenching his jaw tightly at the end.
[Shot 3] At 00:08.000, the camera cuts to a static over-the-shoulder medium-close shot from the same 180-degree axis, with <Subject 2>'s blurred left shoulder in the left foreground, <Subject 1> at right-center, and <Subject 3> beside her at screen-right. <Subject 1> finally lifts her eyes to sweep an impatient, condescending glance over <Subject 2>, lifts the locked black briefcase in her right hand, turns her body half-right toward the exit, and <Subject 1> (S1) speaks at a brisk, dismissive pace during 8.2-12.8 seconds: <d>[Chinese] 见机构要注意团队形象。老仓清静，工资照发，你别让我为难。</d> Her lips match the complete sentence clearly while <Subject 3> watches with a smug grin and closed lips. {TAIL_GUARD}

overall_soundscape:
Two sharp brass briefcase latch clicks, subtle room ambience, heavy rain outside the glass, and a booming thunderclap rising at the end.

non_diegetic_music:
N/A
""",
    },

    # 05: 1-2-01 (9s) - v1.2 upgraded crash impact + splice_window VO!
    {
        "id": "1-2-01",
        "shot_uuid": shots_by_idx[4]["id"],
        "episode": ep1["title"],
        "aspect_ratio": "9:16",
        "duration": 9,
        "seed": 10105,
        "keyframe_2k": kf2k("1-2-01"),
        "asset_names": ["叶寻 · 2015行政总厨", "集团大厦旋转门雨夜街口"],
        "dialogue": "叶寻 · 2015行政总厨（画外）：十年托举，最后连爷爷留下的根都亲手送了人……",
        "description": (
            "drama-key:1-2-01\n"
            "0.0–2.4s 1-2-01 中全景 平视 固定：暴雨如注，叶寻双臂紧抱旧帆布厨刀卷走出大厦旋转门踏入积水街面。\n"
            "2.4–6.5s 1-2-02 特写 俯拍 固定：雨水重砸在叶寻紧扣帆布刀卷的右手虎口旧烫疤上，伴随画外悲怆独白。\n"
            "6.5–9.0s 1-2-03 中近景 低机位 震动：右侧失控汽车刺目双远光灯高速冲入占满镜头撞击闪白，叶寻被猛烈冲击震出左画框外，旧厨刀卷脱手飞砸进强光照亮的积水洼中。"
        ),
        "ref_images": [
            kf1k("1-2-01"),
            main_1k("叶寻 · 2015行政总厨"),
            main_1k("集团大厦旋转门雨夜街口"),
        ],
        "ref_audios": [
            voice("叶寻 · 2015行政总厨"),
        ],
        "prompt": f"""subject_definitions:
<Picture 1> is the first frame of [Shot 1], locking the rainy night street framing outside the revolving glass doors.
<Subject 1> is the person from <Picture 2>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 2> without modification.
<Subject 2> is the rain-slicked corporate plaza entrance at night from <Picture 3>, preserving its warm-lit revolving glass doors and wet asphalt reflections.
All character sheets (<Picture 2>) provide 3D identity and outfit guidance only; never copy studio white backgrounds or multi-panel borders.
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).

summary:
[keyframe completion + reference generation + audio reference] Starting from <Picture 1> in <Subject 2>, rain-drenched <Subject 1> walks into the downpour clutching a grey canvas knife roll while his off-screen voiceover reflects bitterly, until a speeding car's blinding headlights rush into frame from screen-right and knock him out of frame as the knife roll splashes into a puddle, following <Audio 1>.

retention_analysis:
<Picture 1> ([Shot 1] first frame): fully_preserved - [Shot 1] starts directly from <Picture 1>.
<Subject 1> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - exact identity and wet outfit from <Picture 2> are maintained.
<Subject 2> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - wet asphalt reflections and revolving door lights remain consistent.
<Audio 1>: reference - <Subject 1> follows <Audio 1>'s voice timbre without copying the source recording.

detailed_description:
{STYLE_916}
[Shot 1] Starting from <Picture 1>, a static eye-level medium-wide shot in <Subject 2> shows torrential night rain pouring outside the glowing revolving glass doors at left-rear. <Subject 1>, soaked by rain and clutching a rolled dark-grey canvas knife bundle tightly against his chest with both arms, steps down off the curb from screen-left toward center-right during 0.0-2.4 seconds, splashing ankle-deep through reflective puddles with a numb, hollow expression and lips completely closed.
[Shot 2] At 00:02.400, the camera cuts to a static high-angle close-up on <Subject 1>'s rain-drenched right hand gripping the cord of the dark-grey canvas knife roll against his chest, a dark old burn scar clearly visible on his thumb web as heavy raindrops splatter across his knuckles. During 2.5-6.4 seconds his fingers clench the wet canvas tighter with trembling veins as bright white headlight beams begin washing across his wet hand from screen-right, while <Subject 1> (S1) says in an off-screen voiceover at a bitter, aching pace: <d>[Chinese] 十年托举，最后连爷爷留下的根都亲手送了人……</d>
[Shot 3] At 00:06.500, the camera cuts to a tight low-angle medium-close shot on the wet street of <Subject 2> framing <Subject 1> from the waist up on left-center turning his startled face sharply toward screen-right as twin blinding white car headlights rush rapidly forward from screen-right straight at him during 6.5-7.2 seconds. At 7.3 seconds the glaring white headlights fill the right side of the lens with a violent camera shake and impact jolt that knocks <Subject 1> backward out of the left edge of the frame, while the dark-grey canvas knife roll flies from his grip and splashes hard into the headlight-lit rain puddle in the foreground during 7.5-9.0 seconds. {TAIL_GUARD}

overall_soundscape:
Torrential downpour, footsteps splashing in puddles, roaring approaching car engine, piercing tire screech and heavy crash impact thud at 7.3 seconds, ending with the canvas roll splashing into water.

non_diegetic_music:
N/A
""",
        "vo_split": {
            "mode": "splice_window",
            "windows": [[2.0, 6.6]],
            "prompt_novo": f"""subject_definitions:
<Picture 1> is the first frame of [Shot 1], locking the rainy night street framing outside the revolving glass doors.
<Subject 1> is the person from <Picture 2>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 2> without modification.
<Subject 2> is the rain-slicked corporate plaza entrance at night from <Picture 3>, preserving its warm-lit revolving glass doors and wet asphalt reflections.
All character sheets (<Picture 2>) provide 3D identity and outfit guidance only; never copy studio white backgrounds or multi-panel borders.

summary:
[keyframe completion + reference generation] Starting from <Picture 1> in <Subject 2>, rain-drenched <Subject 1> walks silently into the downpour clutching a grey canvas knife roll, stares down at the burn scar on his hand, and is struck out of frame as speeding car headlights rush straight at him from screen-right, knocking the knife roll into a puddle.

retention_analysis:
<Picture 1> ([Shot 1] first frame): fully_preserved - [Shot 1] starts directly from <Picture 1>.
<Subject 1> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - exact identity and wet outfit from <Picture 2> are maintained.
<Subject 2> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - wet asphalt reflections and revolving door lights remain consistent.

detailed_description:
{STYLE_916}
[Shot 1] Starting from <Picture 1>, a static eye-level medium-wide shot in <Subject 2> shows torrential night rain pouring outside the glowing revolving glass doors at left-rear. <Subject 1>, soaked by rain and clutching a rolled dark-grey canvas knife bundle tightly against his chest with both arms, steps down off the curb from screen-left toward center-right during 0.0-2.4 seconds, splashing ankle-deep through reflective puddles with a numb, hollow expression and lips completely closed and still.
[Shot 2] At 00:02.400, the camera cuts to a static high-angle close-up on <Subject 1>'s rain-drenched right hand gripping the cord of the dark-grey canvas knife roll against his chest, a dark old burn scar clearly visible on his thumb web as heavy raindrops splatter across his knuckles. During 2.5-6.4 seconds his fingers clench the wet canvas tighter with trembling veins in complete silence as bright white headlight beams begin washing across his wet hand from screen-right.
[Shot 3] At 00:06.500, the camera cuts to a tight low-angle medium-close shot on the wet street of <Subject 2> framing <Subject 1> from the waist up on left-center turning his startled face sharply toward screen-right with lips closed as twin blinding white car headlights rush rapidly forward from screen-right straight at him during 6.5-7.2 seconds. At 7.3 seconds the glaring white headlights fill the right side of the lens with a violent camera shake and impact jolt that knocks <Subject 1> backward out of the left edge of the frame, while the dark-grey canvas knife roll flies from his grip and splashes hard into the headlight-lit rain puddle in the foreground during 7.5-9.0 seconds. {TAIL_GUARD}

overall_soundscape:
Torrential downpour, footsteps splashing in puddles, roaring approaching car engine, piercing tire screech and heavy crash impact thud at 7.3 seconds, ending with the canvas roll splashing into water; no human voice.

non_diegetic_music:
N/A
""",
        },
    },

    # 06: 1-3-01 (11s - v1.1 tail buffer + simultaneous key-twirl & speech)
    {
        "id": "1-3-01",
        "shot_uuid": shots_by_idx[5]["id"],
        "episode": ep1["title"],
        "aspect_ratio": "9:16",
        "duration": 11,
        "seed": 9106,
        "keyframe_2k": kf2k("1-3-01"),
        "asset_names": ["叶寻", "林双双", "楚南", "沙正街林家食府老店大堂", "《叶氏本草食单》蓝布线装册"],
        "dialogue": "楚南：双双，你真打算听叶寻的，把馆子改成老火锅？",
        "description": (
            "drama-key:1-3-01\n"
            "0.0–2.8s 1-3-01 中近景 平视 快拉：2005年午后老店圆桌旁，叶寻猛然睁眼急促喘息，双手扶稳圆木桌沿。\n"
            "2.8–5.8s 1-3-02 特写 俯拍 固定：叶寻摊开光洁无疤的右手，探入身侧军绿帆布包摸到完好的蓝布线装《叶氏本草食单》。\n"
            "5.8–11.0s 1-3-03 中近景 越肩 固定：圆桌右侧楚南边转车钥匙边嫌弃挑眉问林双双是否真要改成老火锅。"
        ),
        "ref_images": [
            kf1k("1-3-01"),
            main_1k("叶寻"),
            main_1k("林双双"),
            main_1k("楚南"),
            main_1k("沙正街林家食府老店大堂"),
            main_1k("《叶氏本草食单》蓝布线装册"),
        ],
        "ref_audios": [
            voice("楚南"),
        ],
        "prompt": f"""subject_definitions:
<Picture 1> is the first frame of [Shot 1], locking the three-person seated spatial blocking around the round wooden dining table under the ceiling fan.
<Subject 1> is the person from <Picture 2>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 2> without modification.
<Subject 2> is the person from <Picture 3>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 3> without modification.
<Subject 3> is the person from <Picture 4>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 4> without modification.
<Subject 4> is the sunlit traditional restaurant dining hall from <Picture 5>, preserving its round dark-reddish wooden tables, wooden chairs, green ceiling fan, and sunlit open doors.
<Subject 5> is the indigo-blue cloth thread-bound recipe book from <Picture 6>.
All character sheets (<Picture 2> to <Picture 4>) provide 3D identity and outfit guidance only; never copy studio white backgrounds or multi-panel borders.
<Audio 1> is the voice-timbre reference for <Subject 3> (S1).

summary:
[keyframe completion + reference generation + audio reference] Starting from <Picture 1> in <Subject 4>, <Subject 1> jolts awake gasping at the round wooden table, checks his unscarred right hand and touches <Subject 5> inside his canvas bag, and <Subject 3> spins car keys while questioning <Subject 2> skeptically, following <Audio 1>.

retention_analysis:
<Picture 1> ([Shot 1] first frame): fully_preserved - [Shot 1] begins directly from <Picture 1>'s sunlit dining-hall blocking.
<Subject 1> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - exact identity and outfit from <Picture 2> are preserved.
<Subject 2> (appears in [Shot 1], [Shot 3]): fully_preserved - exact identity and outfit from <Picture 3> are preserved.
<Subject 3> (appears in [Shot 1], [Shot 3]): fully_preserved - exact identity and outfit from <Picture 4> are preserved.
<Subject 4> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - sunlit restaurant interior and round table height remain consistent.
<Subject 5> (appears in [Shot 2]): fully_preserved - indigo thread-bound book cover and proportions are preserved.
<Audio 1>: reference - <Subject 3> follows <Audio 1>'s voice timbre without copying the source recording.

detailed_description:
{STYLE_916}
[Shot 1] Starting from <Picture 1>, in the warm sunlit dining hall of <Subject 4> beneath a turning green ceiling fan, <Subject 1> sits on screen-left at a 75cm-high round wooden table (table edge at waist level, full upper torsos clearly above the tabletop) with <Subject 2> and <Subject 3> seated on the right side. At 0.1 seconds <Subject 1>'s tightly shut eyes snap wide open with a sharp gasp as the camera pulls back briskly over 0.8 seconds to a clear medium-close view; during 0.9-2.7 seconds <Subject 1> braces both hands onto the wooden table edge, chest heaving as his startled eyes scan the bright sunlit room.
[Shot 2] At 00:02.800, the camera cuts to a static POV top-down close-up of <Subject 1>'s right hand in warm sunlight: at 2.9-4.1 seconds he turns his palm and back of hand over, revealing smooth, completely unscarred skin on his thumb web; at 4.1-5.6 seconds his steady hand reaches into the open olive-green canvas crossbody bag at his hip and presses firmly onto the indigo cloth cover of <Subject 5> resting safely inside.
[Shot 3] At 00:05.800, the camera cuts to a static over-the-shoulder medium-close shot from the same 180-degree axis, with <Subject 1>'s blurred left shoulder in the left foreground and <Subject 2> (center-right) and <Subject 3> (screen-right) seated across the round wooden table. Immediately at 6.0 seconds, while twirling a car key ring on his right index finger with raised sceptical brows toward <Subject 2>, <Subject 3> (S1) speaks in a cocky, disdainful young male voice at a brisk pace during 6.0-9.6 seconds: <d>[Chinese] 双双，你真打算听叶寻的，把馆子改成老火锅？</d> His lips articulate the entire question clearly, holding a skeptical smirk during 9.6-11.0 seconds while <Subject 2> frowns hesitantly with lips closed. {TAIL_GUARD}

overall_soundscape:
Gentle rhythmic creak of the overhead ceiling fan, summer cicadas outside the open doors, a sharp waking gasp, canvas bag rustle, and metallic jingle of spinning car keys.

non_diegetic_music:
N/A
""",
    },

    # 07: 1-3-04 (11s - v1.1 tail buffer + simultaneous key-slap & speech)
    {
        "id": "1-3-04",
        "shot_uuid": shots_by_idx[6]["id"],
        "episode": ep1["title"],
        "aspect_ratio": "9:16",
        "duration": 11,
        "seed": 9107,
        "keyframe_2k": kf2k("1-3-04"),
        "asset_names": ["楚南", "林双双", "叶寻", "沙正街林家食府老店大堂"],
        "dialogue": "楚南：外语系女生谁爱熏一身牛油味？\n楚南：改成法式西餐厅，我把上海星级西厨赵帆请来给你镇场！",
        "description": (
            "drama-key:1-3-04\n"
            "0.0–1.8s 1-3-04 中近景 越肩 固定：楚南停下转车钥匙握在手心，嫌热浮夸扇了两下风。\n"
            "1.8–4.8s 1-3-05 中近景 越肩双人 固定：楚南向林双双撇嘴挥手嫌弃牛油火锅味，林双双动摇倾听。\n"
            "4.8–11.0s 1-3-06 近景 紧凑越肩 固定：楚南啪地把本田车钥匙拍在圆木桌面上，同时眉飞色舞打包票请上海西厨赵帆镇场。"
        ),
        "ref_images": [
            kf1k("1-3-04"),
            main_1k("楚南"),
            main_1k("林双双"),
            main_1k("叶寻"),
            main_1k("沙正街林家食府老店大堂"),
        ],
        "ref_audios": [
            voice("楚南"),
        ],
        "prompt": f"""subject_definitions:
<Picture 1> is the first frame of [Shot 1], locking the three-person over-the-shoulder blocking at the round wooden table.
<Subject 1> is the person from <Picture 2>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 2> without modification.
<Subject 2> is the person from <Picture 3>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 3> without modification.
<Subject 3> is the person from <Picture 4>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 4> without modification.
<Subject 4> is the sunlit traditional restaurant dining hall from <Picture 5>, preserving its round wooden tables, wooden chairs, and warm afternoon light.
All character sheets (<Picture 2> to <Picture 4>) provide 3D identity and outfit guidance only; never copy studio white backgrounds or multi-panel borders.
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).

summary:
[keyframe completion + reference generation + audio reference] Starting from <Picture 1> in <Subject 4>, <Subject 1> fans himself theatricality while holding car keys, disparages hotpot odor to sway <Subject 2>, and slaps his car keys onto the wooden tabletop while boasting about bringing in a star Western chef, following <Audio 1>.

retention_analysis:
<Picture 1> ([Shot 1] first frame): fully_preserved - [Shot 1] begins directly from <Picture 1>.
<Subject 1> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - exact identity and outfit from <Picture 2> are preserved.
<Subject 2> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - exact identity and outfit from <Picture 3> are preserved.
<Subject 3> (appears in [Shot 1], [Shot 2]): fully_preserved - exact identity and outfit from <Picture 4> are preserved.
<Subject 4> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - sunlit restaurant interior and round wooden table remain consistent.
<Audio 1>: reference - <Subject 1> follows <Audio 1>'s voice timbre without copying the source recording.

detailed_description:
{STYLE_916}
[Shot 1] Starting from <Picture 1>, an eye-level over-the-shoulder medium-close shot in <Subject 4> frames <Subject 3>'s blurred shoulder at screen-left and <Subject 2> (center-right) and <Subject 1> (screen-right) seated behind the round wooden table with their full upper torsos above the tabletop. During 0.1-1.7 seconds, <Subject 1> catches the car keys in his right palm, waves his left hand twice near his neck to fan away the warm air with an exaggerated grimace, and lifts his chin toward <Subject 2>.
[Shot 2] At 00:01.800, the camera cuts to a slightly tighter static two-shot on the right side of the same 180-degree axis framing <Subject 2> on left-center and <Subject 1> on right-center, with <Subject 3>'s shoulder edge at far screen-left. Immediately at 1.9 seconds, waving his hand dismissively toward <Subject 2>, <Subject 1> (S1) speaks in a flashy, disdainful young male voice at a brisk pace during 1.9-4.5 seconds: <d>[Chinese] 外语系女生谁爱熏一身牛油味？</d> His lips move clearly with the line while <Subject 2> listens visibly tempted with lips closed.
[Shot 3] At 00:04.800, the camera cuts to a tight close-up over <Subject 2>'s left shoulder onto <Subject 1> on right-center. At 4.9-5.3 seconds <Subject 1> slaps the car keys sharply onto the right corner of the wooden tabletop and immediately at 5.3 seconds, patting his chest boastfully, <Subject 1> (S1) speaks excitedly at a brisk pace during 5.3-9.8 seconds: <d>[Chinese] 改成法式西餐厅，我把上海星级西厨赵帆请来给你镇场！</d> His lips articulate the entire sentence clearly, leaning back smugly during 9.8-11.0 seconds while <Subject 2> in the foreground nods eagerly with lips closed. {TAIL_GUARD}

overall_soundscape:
Metallic car keys slapped sharply onto a solid wooden table at 5.1 seconds, ceiling fan hum, and warm daytime street ambience outside.

non_diegetic_music:
N/A
""",
    },

    # 08: 1-3-07 (13s - v1.1 comfortable window for S11a + S11b + crisp bag-buckle stand-up)
    {
        "id": "1-3-07",
        "shot_uuid": shots_by_idx[7]["id"],
        "episode": ep1["title"],
        "aspect_ratio": "9:16",
        "duration": 13,
        "seed": 9108,
        "keyframe_2k": kf2k("1-3-07"),
        "asset_names": ["林双双", "叶寻", "沙正街林家食府老店大堂", "《叶氏本草食单》蓝布线装册"],
        "dialogue": "林双双：叶寻，你昨天答应拿爷爷方子帮我家救店，可楚南说火锅上不了台面……\n林双双：你怎么不吭声？",
        "description": (
            "drama-key:1-3-07\n"
            "0.0–6.4s 1-3-07 中近景 越肩 固定：林双双双手搭在圆木桌沿，挑剔娇纵地向左侧叶寻施压试探。\n"
            "6.4–9.2s 1-3-08 近景 紧凑越肩 固定：见叶寻一言不发，林双双身体前倾不满催问。\n"
            "9.2–13.0s 1-3-09 中近景 俯升平视 上摇：叶寻右手咔哒扣死军绿帆布包铜扣，抓起肩带甩上左肩推椅干脆站起身。"
        ),
        "ref_images": [
            kf1k("1-3-07"),
            main_1k("林双双"),
            main_1k("叶寻"),
            main_1k("沙正街林家食府老店大堂"),
        ],
        "ref_audios": [
            voice("林双双"),
        ],
        "prompt": f"""subject_definitions:
<Picture 1> is the first frame of [Shot 1], locking the two-person over-the-shoulder blocking across the round wooden table.
<Subject 1> is the person from <Picture 2>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 2> without modification.
<Subject 2> is the person from <Picture 3>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 3> without modification.
<Subject 3> is the sunlit traditional restaurant dining hall from <Picture 4>, preserving its round wooden tables, wooden chairs, and warm afternoon light.
All character sheets (<Picture 2>, <Picture 3>) provide 3D identity and outfit guidance only; never copy studio white backgrounds or multi-panel borders.
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).

summary:
[keyframe completion + reference generation + audio reference] Starting from <Picture 1> in <Subject 3>, <Subject 1> pressures <Subject 2> across the round table expecting him to plead, demands why he stays silent, and <Subject 2> decisively buckles his olive-green canvas bag shut and stands up tall, following <Audio 1>.

retention_analysis:
<Picture 1> ([Shot 1] first frame): fully_preserved - [Shot 1] starts directly from <Picture 1>.
<Subject 1> (appears in [Shot 1], [Shot 2]): fully_preserved - exact identity and outfit from <Picture 2> are preserved.
<Subject 2> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - exact identity and outfit from <Picture 3> are preserved.
<Subject 3> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - sunlit wooden dining hall and round table remain consistent.
<Audio 1>: reference - <Subject 1> follows <Audio 1>'s voice timbre without copying the source recording.

detailed_description:
{STYLE_916}
[Shot 1] Starting from <Picture 1>, a static over-the-shoulder medium-close shot in <Subject 3> frames <Subject 2>'s calm shoulder on the left foreground and <Subject 1> seated on right-center behind the round wooden table (full upper torso clearly above the tabletop, car keys resting untouched on the right table corner). Immediately at 0.2 seconds, knitting her brows with entitled, spoiled impatience while looking straight at <Subject 2>, <Subject 1> (S1) speaks in a crisp, demanding young female voice at a brisk pace during 0.2-6.1 seconds: <d>[Chinese] 叶寻，你昨天答应拿爷爷方子帮我家救店，可楚南说火锅上不了台面……</d> Her lips move clearly with the complete sentence while <Subject 2> remains completely still.
[Shot 2] At 00:06.400, the camera cuts to a tighter over-the-shoulder close shot from the same 180-degree axis, showing <Subject 2>'s steady right hand resting on the brass buckle of his olive-green canvas bag in the lower-left foreground and <Subject 1> leaning sharply forward on right-center. Annoyed by his silence, <Subject 1> narrows her eyes and <Subject 1> (S1) snaps briskly during 6.5-8.8 seconds: <d>[Chinese] 你怎么不吭声？</d> Her lips match the line clearly.
[Shot 3] At 00:09.200, the camera cuts to a medium-close shot on the left side of the round table starting on the olive-green canvas bag at <Subject 2>'s hip. At 9.3-10.0 seconds <Subject 2>'s right hand snaps the brass bag buckle firmly shut with a sharp click; during 10.0-12.8 seconds he grabs the wide canvas strap, swings the bag cleanly onto his left shoulder, and pushes his wooden chair back to stand up tall at natural real-time speed as the camera tilts and rises smoothly with him to frame <Subject 2>'s calm, razor-sharp gaze looking down toward screen-right with lips closed. {TAIL_GUARD}

overall_soundscape:
Quiet overhead fan creak, a crisp brass buckle snap-click at 9.6 seconds, and a wooden chair scraping backward across the floor as he stands.

non_diegetic_music:
N/A
""",
    },

    # 09: 1-3-10 (10s - v1.1 +1s tail buffer so S14 never clips)
    {
        "id": "1-3-10",
        "shot_uuid": shots_by_idx[8]["id"],
        "episode": ep1["title"],
        "aspect_ratio": "9:16",
        "duration": 10,
        "seed": 9109,
        "keyframe_2k": kf2k("1-3-10"),
        "asset_names": ["叶寻", "林双双", "楚南", "沙正街林家食府老店大堂", "《叶氏本草食单》蓝布线装册"],
        "dialogue": "叶寻：楚少说得对。\n林双双：你说什么？\n叶寻：西餐体面，我这老方子就不耽误你们发财了。",
        "description": (
            "drama-key:1-3-10\n"
            "0.0–2.0s 1-3-10 近景 略仰 固定：站立的叶寻左手扶稳军绿挎包肩带，平静淡然顺水推舟。\n"
            "2.0–4.5s 1-3-11 中近景 略俯 固定：坐着的林双双瞬间怔住错愕仰头追问，身旁楚南意外挑眉。\n"
            "4.5–10.0s 1-3-12 近景 侧偏正 固定：叶寻眼神清亮无悔，干脆利落说完切割台词微颔首准备转身。"
        ),
        "ref_images": [
            kf1k("1-3-10"),
            main_1k("叶寻"),
            main_1k("林双双"),
            main_1k("楚南"),
            main_1k("沙正街林家食府老店大堂"),
        ],
        "ref_audios": [
            voice("叶寻"),
            voice("林双双"),
        ],
        "prompt": f"""subject_definitions:
<Picture 1> is the first frame of [Shot 1], locking the standing-versus-seated three-person spatial blocking around the round wooden table.
<Subject 1> is the person from <Picture 2>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 2> without modification.
<Subject 2> is the person from <Picture 3>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 3> without modification.
<Subject 3> is the person from <Picture 4>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 4> without modification.
<Subject 4> is the sunlit traditional restaurant dining hall from <Picture 5>, preserving its round wooden tables, green ceiling fan, and warm afternoon light.
All character sheets (<Picture 2> to <Picture 4>) provide 3D identity and outfit guidance only; never copy studio white backgrounds or multi-panel borders.
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).
<Audio 2> is the voice-timbre reference for <Subject 2> (S2).

summary:
[keyframe completion + reference generation + audio reference] Starting from <Picture 1> in <Subject 4>, standing <Subject 1> calmly agrees with <Subject 3>, seated <Subject 2> freezes in stunned disbelief and asks what he said, and <Subject 1> cleanly withdraws his family recipe for good, following <Audio 1> and <Audio 2>.

retention_analysis:
<Picture 1> ([Shot 1] first frame): fully_preserved - [Shot 1] begins directly from <Picture 1>'s standing-and-seated blocking.
<Subject 1> (appears in [Shot 1], [Shot 3]): fully_preserved - exact identity and outfit from <Picture 2> are preserved.
<Subject 2> (appears in [Shot 1], [Shot 2]): fully_preserved - exact identity and outfit from <Picture 3> are preserved.
<Subject 3> (appears in [Shot 1], [Shot 2]): fully_preserved - exact identity and outfit from <Picture 4> are preserved.
<Subject 4> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - sunlit restaurant interior and round table remain consistent.
<Audio 1>: reference - <Subject 1> follows <Audio 1>'s voice timbre without copying the source recording.
<Audio 2>: reference - <Subject 2> follows <Audio 2>'s voice timbre without copying the source recording.

detailed_description:
{STYLE_916}
[Shot 1] Starting from <Picture 1>, a medium-close shot in <Subject 4> frames <Subject 1> standing tall on screen-left with his left hand holding the strap of his olive-green canvas shoulder bag, looking calmly down toward <Subject 2> and <Subject 3> seated on screen-right. Immediately at 0.2 seconds, with a faint, cool curve at the corner of his mouth, <Subject 1> (S1) speaks in a crisp, composed young male voice at a brisk pace during 0.2-1.8 seconds: <d>[Chinese] 楚少说得对。</d> His lips move clearly with the line while the two seated listeners freeze with lips closed.
[Shot 2] At 00:02.000, the camera cuts to a static high-angle medium-close two-shot on the right side of the 180-degree axis looking down at <Subject 2> (center) and <Subject 3> (screen-right) seated behind the round wooden table with car keys resting on the tabletop. <Subject 2>'s arrogant expression freezes completely, her eyes widening in shock as she looks up toward screen-left, and <Subject 2> (S2) blurts out in stunned disbelief during 2.1-4.1 seconds: <d>[Chinese] 你说什么？</d> Her lips match the question clearly while <Subject 3> raises his eyebrows in surprise with lips closed.
[Shot 3] At 00:04.500, the camera cuts to a static slightly low-angle close shot of <Subject 1> standing on left-center bathed in warm sunlight from the doorway on the right, his left hand steady on his canvas bag strap. Immediately at 4.6 seconds, looking at them like complete strangers with bright, unwavering eyes, <Subject 1> (S1) speaks cleanly at a brisk pace during 4.6-8.6 seconds: <d>[Chinese] 西餐体面，我这老方子就不耽误你们发财了。</d> His lips articulate the entire sentence clearly, followed by a crisp, final nod during 8.7-10.0 seconds with lips closed. {TAIL_GUARD}

overall_soundscape:
Sudden hush in the sunlit dining room, subtle wooden chair creak, and a faint bicycle bell outside on the street.

non_diegetic_music:
N/A
""",
    },

    # 10: 1-3-13 (15s)
    {
        "id": "1-3-13",
        "shot_uuid": shots_by_idx[9]["id"],
        "episode": ep1["title"],
        "aspect_ratio": "9:16",
        "duration": 15,
        "seed": 9110,
        "keyframe_2k": kf2k("1-3-13"),
        "asset_names": ["叶寻", "林双双", "楚南", "沙正街林家食府老店大堂", "《叶氏本草食单》蓝布线装册"],
        "dialogue": "林双双：叶寻你站住！出了这扇门，以后你求着把方子送来我都不要！",
        "description": (
            "drama-key:1-3-13\n"
            "0.0–2.0s 1-3-13 中景 纵深 固定：叶寻背着军绿帆布包毫不留恋转身迈步走向右侧敞开木门。\n"
            "2.0–7.5s 1-3-14 中近景 正面 固定：林双双双手重拍圆木桌猛然站起，恼羞成怒冲门口尖声威胁。\n"
            "7.5–12.0s 1-3-15 中景 跟拍 缓跟：叶寻脚步丝毫未停一把推开老木门，大步跨入明媚午后阳光街道。\n"
            "12.0–15.0s 1-3-16 近景 侧逆光 固定：叶寻快步走在门外梧桐树荫下，听到前方刺耳木轮卡石缝声猛然抬头望去。"
        ),
        "ref_images": [
            kf1k("1-3-13"),
            main_1k("叶寻"),
            main_1k("林双双"),
            main_1k("楚南"),
            main_1k("沙正街林家食府老店大堂"),
        ],
        "ref_audios": [
            voice("林双双"),
        ],
        "prompt": f"""subject_definitions:
<Picture 1> is the first frame of [Shot 1], locking the depth blocking as <Subject 1> turns away from the seated pair toward the sunlit restaurant doorway.
<Subject 1> is the person from <Picture 2>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 2> without modification.
<Subject 2> is the person from <Picture 3>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 3> without modification.
<Subject 3> is the person from <Picture 4>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 4> without modification.
<Subject 4> is the sunlit traditional restaurant dining hall from <Picture 5>, preserving its round wooden tables, wooden chairs, and sunlit double wooden entrance doors.
All character sheets (<Picture 2> to <Picture 4>) provide 3D identity and outfit guidance only; never copy studio white backgrounds or multi-panel borders.
<Audio 1> is the voice-timbre reference for <Subject 2> (S1).

summary:
[keyframe completion + reference generation + audio reference] Starting from <Picture 1> in <Subject 4>, <Subject 1> strides decisively toward the open entrance door without looking back, <Subject 2> slams the table and stands up shouting a furious ultimatum beside <Subject 3>, and <Subject 1> pushes straight out into the bright sunlit sycamore street before alerting to a wheel-scraping sound ahead, following <Audio 1>.

retention_analysis:
<Picture 1> ([Shot 1] first frame): fully_preserved - [Shot 1] begins directly from <Picture 1>.
<Subject 1> (appears in [Shot 1], [Shot 3], [Shot 4]): fully_preserved - exact identity and outfit from <Picture 2> are preserved.
<Subject 2> (appears in [Shot 1], [Shot 2]): fully_preserved - exact identity and outfit from <Picture 3> are preserved.
<Subject 3> (appears in [Shot 1], [Shot 2]): fully_preserved - exact identity and outfit from <Picture 4> are preserved.
<Subject 4> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - wooden dining hall and sunlit wooden entrance doors remain consistent.
<Audio 1>: reference - <Subject 2> follows <Audio 1>'s voice timbre without copying the source recording.

detailed_description:
{STYLE_916}
[Shot 1] Starting from <Picture 1>, a static medium depth shot inside <Subject 4> shows <Subject 2> and <Subject 3> seated at the round wooden table in the left background while <Subject 1>, carrying the olive-green canvas bag on his left shoulder, strides briskly and decisively toward the sunlit wooden entrance doors at screen-right during 0.0-2.0 seconds without hesitating.
[Shot 2] At 00:02.000, the camera cuts to a static medium-close shot of the round wooden table where <Subject 2> slams both palms hard onto the wooden tabletop at 2.1 seconds and springs angrily to her feet beside seated <Subject 3>, her face flushed with wounded pride. Staring furiously toward the doorway at screen-right, <Subject 2> (S1) shouts in a sharp, indignant young female voice at a brisk pace during 2.5-7.3 seconds: <d>[Chinese] 叶寻你站住！出了这扇门，以后你求着把方子送来我都不要！</d> Her lips move clearly through the entire shouted threat while <Subject 3> watches beside her with lips closed.
[Shot 3] At 00:07.500, the camera cuts to a medium following shot behind <Subject 1> facing the sunlit double wooden entrance doors of <Subject 4>. Without breaking stride for a fraction of a second, <Subject 1> pushes the wooden door wide open with his right hand at 8.0 seconds and steps straight across the threshold into golden afternoon sunlight on a bustling tree-lined sidewalk as the camera tracks smoothly forward one meter inside the doorway during 7.5-11.8 seconds.
[Shot 4] At 00:12.000, the camera cuts to a static medium-close sunlit side-front shot outside on the sycamore-shaded sidewalk as <Subject 1> walks briskly toward screen-right holding his canvas bag strap; at 13.4 seconds a sudden harsh sound of a wooden cart wheel grinding into stone cracks ahead, and <Subject 1>'s eyes sharpen alertly as he lifts his head toward screen-right with lips closed. {TAIL_GUARD}

overall_soundscape:
Brisk footsteps on wood, a loud double-palm slam on the wooden table and chair scrape, creak of wooden doors opening into lively outdoor street ambience, ending with a sharp wooden-wheel grinding scrape ahead.

non_diegetic_music:
N/A
""",
    },

    # 11: 1-4-01 (14s - v2.0 accidental pocket drop without looking down)
    {
        "id": "1-4-01",
        "shot_uuid": shots_by_idx[10]["id"],
        "episode": ep1["title"],
        "aspect_ratio": "9:16",
        "duration": 14,
        "seed": 10111,
        "keyframe_2k": kf2k("1-4-01"),
        "asset_names": ["叶寻", "夏芊芊", "重庆大学A区校门梧桐坡道", "桂花巷18000元房租催缴单"],
        "dialogue": "夏芊芊：谢谢同……小寻？！",
        "description": (
            "drama-key:1-4-01\n"
            "0.0–4.5s 1-4-01 中景 平视 跟拍：辣椒麻袋木板车右轮卡在石缝歪斜，叶寻从左侧一把托起木车帮与右侧夏芊芊协力推上平路停稳。\n"
            "4.5–8.5s 1-4-02 近景 越肩 固定：夏芊芊擦汗抬头认出叶寻满眼惊喜轻呼，兜口探出折角的白纸无意滑落出下画框，她浑然未觉。\n"
            "8.5–14.0s 1-4-03 特写 俯拍 缓推：青石板地面上盖着醒目红章的催缴单，叶寻球鞋尖驻立左上角，镜头缓推红章单据同时尾端先入急促奔跑脚步声。"
        ),
        "ref_images": [
            kf1k("1-4-01"),
            main_1k("叶寻"),
            main_1k("夏芊芊"),
            main_1k("重庆大学A区校门梧桐坡道"),
            main_1k("桂花巷18000元房租催缴单"),
        ],
        "ref_audios": [
            voice("夏芊芊"),
        ],
        "prompt": f"""subject_definitions:
<Picture 1> is the first frame of [Shot 1], locking the two-person spatial blocking beside the tilted chili-sack wooden handcart on the stone slope.
<Subject 1> is the person from <Picture 2>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 2> without modification.
<Subject 2> is the person from <Picture 3>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 3> without modification.
<Subject 3> is the sunlit sycamore-lined stone slope before the historic university gate from <Picture 4>, preserving its golden foliage, stone flagstones, and red-brick gate arch.
<Subject 4> is the white notice sheet stamped with a bright red official seal from <Picture 5>.
All character sheets (<Picture 2>, <Picture 3>) provide 3D identity and outfit guidance only; never copy studio white backgrounds or multi-panel borders.
<Audio 1> is the voice-timbre reference for <Subject 2> (S1).

summary:
[keyframe completion + reference generation + audio reference] Starting from <Picture 1> on <Subject 3>, <Subject 1> helps <Subject 2> lift a tilted wooden chili handcart onto flat pavement, <Subject 2> recognizes <Subject 1> in joyful surprise while a folded paper accidentally slips unnoticed out of her pocket toward the ground, and [Shot 3] pushes in on <Subject 4> lying on the flagstones, following <Audio 1>.

retention_analysis:
<Picture 1> ([Shot 1] first frame): fully_preserved - [Shot 1] begins directly from <Picture 1>.
<Subject 1> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - exact identity and outfit from <Picture 2> are preserved.
<Subject 2> (appears in [Shot 1], [Shot 2]): fully_preserved - exact identity and outfit from <Picture 3> are preserved.
<Subject 3> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - sunlit sycamore stone slope and lighting remain consistent.
<Subject 4> (appears in [Shot 3]): fully_preserved - white paper sheet with red circular stamp lies flat on the flagstones in [Shot 3].
<Audio 1>: reference - <Subject 2> follows <Audio 1>'s voice timbre without copying the source recording.

detailed_description:
{STYLE_916}
[Shot 1] Starting from <Picture 1> on the sunlit stone slope of <Subject 3>, a wooden handcart piled with burlap sacks of dried red chilies has its right wheel wedged in a stone drainage crack, with <Subject 2> bracing both wooden handles on screen-right and <Subject 1> gripping the tilting left wooden cart frame on screen-left. During 0.2-4.2 seconds, <Subject 1> heaves upward forcefully with both hands while <Subject 2> pulls forward on the handles; the wooden wheel clunks free of the groove and rolls smoothly onto flat flagstones as the camera tracks rightward one meter at medium speed until the cart settles securely.
[Shot 2] At 00:04.500, the camera cuts to a static over-the-shoulder close shot from the same 180-degree axis, with <Subject 1>'s blurred left shoulder in the left foreground and <Subject 2> on right-center bathed in warm golden sycamore sunlight, a corner of folded white paper peeking loosely from her front pocket. Wiping sweat from her brow with the back of her left wrist at 4.7 seconds, <Subject 2> looks straight up into <Subject 1>'s eyes—keeping her gaze locked joyfully on <Subject 1>'s face the entire time—and <Subject 2> (S1) exclaims in a bright, lively young female voice during 5.1-7.6 seconds: <d>[Chinese] 谢谢同……小寻？！</d> Immediately after speaking, she beams at <Subject 1> with lips closed; as her elbow brushes her pocket at 7.5 seconds, the folded white paper slips out by itself and drops straight down out of the bottom edge of the frame completely unnoticed by <Subject 2>, never held in her hands.
[Shot 3] At 00:08.500, the camera cuts to a high-angle close-up looking down at the sunlit stone flagstones of <Subject 3>, where <Subject 4> now lies half-unfolded on the ground with its bright red circular official stamp clearly visible beside <Subject 1>'s stationary shoe tip at upper-left. During 8.6-13.9 seconds, the camera pushes in steadily toward the red-stamped paper sheet on the stone pavement while urgent, rapid running footsteps approach loudly from off-screen right. {TAIL_GUARD}

overall_soundscape:
Wooden cart wheel clunking out of stone, heavy burlap sacks settling, a bright surprised breath, soft paper flutter, and urgent running footsteps approaching at the end.

non_diegetic_music:
N/A
""",
    },

    # 12: 1-4-04 (13s - v2.0 tight urgent-speech cut + post-speech mouth lock + natural crumpled hold)
    {
        "id": "1-4-04",
        "shot_uuid": shots_by_idx[11]["id"],
        "episode": ep1["title"],
        "aspect_ratio": "9:16",
        "duration": 13,
        "seed": 10112,
        "keyframe_2k": kf2k("1-4-04"),
        "asset_names": ["叶寻", "夏芊芊", "小石头", "重庆大学A区校门梧桐坡道", "桂花巷18000元房租催缴单"],
        "dialogue": "小石头：芊芊姐快回店！刘师傅关火背刀包要走，堂里三桌客人都拍桌子了！",
        "description": (
            "drama-key:1-4-04\n"
            "0.0–3.2s 1-4-04 中景 低平视 固定：夏芊芊慌忙弯腰捡起地面红章催缴单，右后巷口满头大汗的小石头猛冲到近前急刹撑膝喘气。\n"
            "3.2–8.6s 1-4-05 近景 正偏右 固定：小石头猛地直起身焦急指着身后巷口方向大声疾呼报信，说完闭口急喘。\n"
            "8.6–13.0s 1-4-06 近景 斜正 快推：夏芊芊低手攥紧催缴单脸色煞白失措，叶寻单手扶木车帮猛然转头锐利凝视巷口方向，危机悬停定格。"
        ),
        "ref_images": [
            kf1k("1-4-04"),
            main_1k("叶寻"),
            main_1k("夏芊芊"),
            main_1k("小石头"),
            main_1k("重庆大学A区校门梧桐坡道"),
            main_1k("桂花巷18000元房租催缴单"),
        ],
        "ref_audios": [
            voice("小石头"),
        ],
        "prompt": f"""subject_definitions:
<Picture 1> is the first frame of [Shot 1], locking the three-person depth blocking on the sycamore stone slope beside the chili handcart.
<Subject 1> is the person from <Picture 2>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 2> without modification.
<Subject 2> is the person from <Picture 3>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 3> without modification.
<Subject 3> is the person from <Picture 4>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 4> without modification.
<Subject 4> is the sunlit sycamore-lined stone slope from <Picture 5>, preserving its stone flagstones, brick walls, and golden afternoon light.
<Subject 5> is the red-stamped white notice sheet from <Picture 6>.
All character sheets (<Picture 2> to <Picture 4>) provide 3D identity and outfit guidance only; never copy studio white backgrounds or multi-panel borders.
<Audio 1> is the voice-timbre reference for <Subject 3> (S1).

summary:
[keyframe completion + reference generation + audio reference] Starting from <Picture 1> on <Subject 4>, <Subject 2> hurriedly picks up <Subject 5> as sweating <Subject 3> sprints up from the side alley and gasps out an urgent kitchen walkout crisis, leaving <Subject 2> pale with panic while <Subject 1> whips his sharp gaze toward the alley in a cliffhanger freeze, following <Audio 1>.

retention_analysis:
<Picture 1> ([Shot 1] first frame): fully_preserved - [Shot 1] begins directly from <Picture 1>'s three-person depth layout.
<Subject 1> (appears in [Shot 1], [Shot 3]): fully_preserved - exact identity and outfit from <Picture 2> are preserved.
<Subject 2> (appears in [Shot 1], [Shot 3]): fully_preserved - exact identity and outfit from <Picture 3> are preserved.
<Subject 3> (appears in [Shot 1], [Shot 2]): fully_preserved - exact identity and outfit from <Picture 4> are preserved.
<Subject 4> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - sunlit stone slope and brick alley entrance remain consistent.
<Subject 5> (appears in [Shot 1]): weak_reference - folded white paper picked up and held down at <Subject 2>'s side.
<Audio 1>: reference - <Subject 3> follows <Audio 1>'s voice timbre without copying the source recording.

detailed_description:
{STYLE_916}
[Shot 1] Starting from <Picture 1>, a static medium depth shot on <Subject 4> shows <Subject 1> standing on screen-left steadying the chili handcart, <Subject 2> in the center bending down flustered to snatch <Subject 5> off the flagstones and fold it down by her side during 0.1-1.6 seconds, and sweat-drenched <Subject 3> sprinting urgently forward from the right-background alley, skidding to a halt at screen-right at 2.4 seconds and bracing both hands on his knees to gasp for air.
[Shot 2] At 00:03.200, the camera cuts to a static close-up of <Subject 3> on right-center facing screen-left against defocused sunlit brick and foliage, sweat glistening on his forehead. Straightening up at 3.3 seconds and pointing his right arm anxiously backward toward the side alley, <Subject 3> (S1) shouts urgently in a breathless, panicked young male voice during 3.5-8.1 seconds: <d>[Chinese] 芊芊姐快回店！刘师傅关火背刀包要走，堂里三桌客人都拍桌子了！</d> Immediately upon finishing that single sentence at 8.1 seconds, <Subject 3> presses his lips tightly shut and breathes silently without uttering another sound.
[Shot 3] At 00:08.600, the camera cuts to a tight waist-up two-shot on the left side of the 180-degree axis framing <Subject 1> on screen-left with his right hand gripping the wooden chili cart and <Subject 2> beside him on center-right with her hands lowered near her waist clutching the folded edge of the paper. Hearing the crisis, <Subject 2>'s face drains pale in panicked helplessness with lips silently parted, while <Subject 1>'s brows lock sharply and he whips his head at 9.6 seconds to stare intently toward the side alley at screen-right as the camera pushes in briskly to a razor-sharp, high-tension cliffhanger close-up on <Subject 1>'s resolute profile during 9.8-13.0 seconds. {TAIL_GUARD}

overall_soundscape:
Paper snatched off stone, urgent running soles skidding to a stop on flagstones, one heavy gasping breath at 2.8 seconds, and a tense low percussive thud holding at the cliffhanger end; no extra speech after 8.1 seconds.

non_diegetic_music:
N/A
""",
    },
]

# Lint all 12 prompts right away!
errors = []
for item in PLAN:
    errors.extend(lint_zero_appearance(item["prompt"], item["id"]))
    if item.get("vo_split"):
        errors.extend(lint_zero_appearance(item["vo_split"]["prompt_novo"], f"{item['id']}:novo"))

if errors:
    for e in errors:
        print("ERROR:", e, file=sys.stderr)
    sys.exit(1)

out_plan = WORK_DIR / "ep01_video_plan.json"
out_plan.write_text(json.dumps(PLAN, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Compiled & lint-verified {len(PLAN)} Episode 1 shots -> {out_plan}")
