#!/usr/bin/env python3
"""
Compile & execute ALL 3 EPISODES (`Ep 1` = 14 groups, `Ep 2` = 12 groups, `Ep 3` = 16 groups = 42 groups)
for `2005_chongqing_hotpot_v7` in 9:16 480p (`480x832`) on local 5090 `Pika-H3-Flex` + 4070 `368p` dry male VO,
plus automatic `0.5s` high-res diagnostic frame-strip generation (`diag_strips/<id>_0.5s.jpg`) for every shot!

Hard Invariants Enforced (`hit-video`):
  1. <= 1K reference images (`keyframes_1k` + `assets_1k` + `cache_1k`)
  2. Zero character appearance/clothing/hair/age tokens in video prompts (`lint_zero_appearance` == 0 issues)
  3. Pure `<d>[Chinese] 台词原文</d>` with comma/period pacing & zero speaker prefixes inside `<d>`
  4. Closed-mouth locks after urgent shouts + no mid-sentence visual cuts that could clip speech tails
  5. Dedicated `vo_custom` on 4070 (`yexun_pure_ref.wav` zero-music male ref) for all 5 `[VO]` shots (`1-2-01`, `1-3-04`, `1-3-21`, `2-2-07`, `3-2-08`)
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Tuple
from PIL import Image, ImageDraw

SKILL_SCRIPTS = Path("/home/zhongwenyu/project/ai-director-train/.agents/skills/hit-video/scripts")
STUDIO_BRIDGE = Path("/home/zhongwenyu/project/playlets-studio/skills/studio-bridge/scripts")
for p in (str(SKILL_SCRIPTS), str(STUDIO_BRIDGE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import pika_runner  # noqa: E402
import vo_split  # noqa: E402

WORK_DIR = Path("/home/zhongwenyu/project/ai-director-train/productions/2005_chongqing_hotpot_v7/video_gen")
KF_1K = WORK_DIR / "keyframes_1k"
CACHE_1K = WORK_DIR / "cache_1k"
TAKES_EP1 = WORK_DIR / "takes_ep01"
TAKES_EP2 = WORK_DIR / "takes_ep02"
TAKES_EP3 = WORK_DIR / "takes_ep03"
DIAG_DIR = WORK_DIR / "diag_strips"

for d in (CACHE_1K, TAKES_EP1, TAKES_EP2, TAKES_EP3, DIAG_DIR):
    d.mkdir(parents=True, exist_ok=True)

CLEAN_CAMERA = (
    "- Crisp 35mm live-action cinema photography, natural skin texture, accurate 180-degree eye lines and lip-sync, "
    "completely clean unobstructed frame with zero text overlays, captions, watermarks, or split-screen borders."
)


def kf(sid: str) -> str:
    return str(KF_1K / f"{sid}_1k.png")


def trim_silence_bounds(media_path: Path) -> Tuple[float, float]:
    dur_out = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nk=1:nw=1", str(media_path),
    ], text=True).strip()
    total = float(dur_out)
    p = subprocess.run(
        ["ffmpeg", "-i", str(media_path), "-af", "silencedetect=noise=-36dB:d=0.12", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    starts = [float(x) for x in re.findall(r"silence_start:\s*([0-9.]+)", p.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end:\s*([0-9.]+)", p.stderr)]
    ss = 0.0
    if starts and ends and starts[0] < 0.15:
        ss = max(0.0, ends[0] - 0.04)
    se = total
    if starts and starts[-1] > ss + 0.35 and (not ends or starts[-1] > ends[-1] - 0.05):
        se = min(total, starts[-1] + 0.06)
    return round(ss, 3), round(max(ss + 0.4, se), 3)


def make_half_sec_strip(mp4_path: Path, sid: str, out_jpg: Path) -> Path:
    tmp_dir = DIAG_DIR / f"_frames_{sid}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    for old in tmp_dir.glob("*.jpg"):
        old.unlink()
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-i", str(mp4_path),
        "-vf", "fps=2,scale=270:480", "-q:v", "3", str(tmp_dir / "f_%03d.jpg"),
    ], check=True)
    frames = sorted(tmp_dir.glob("f_*.jpg"))
    if not frames:
        return out_jpg
    cols = min(6, len(frames))
    rows = (len(frames) + cols - 1) // cols
    tw, th = 270, 480
    canvas = Image.new("RGB", (cols * tw, rows * th), (12, 12, 12))
    draw = ImageDraw.Draw(canvas)
    for idx, fp in enumerate(frames):
        r, c = divmod(idx, cols)
        im = Image.open(fp).convert("RGB")
        canvas.paste(im, (c * tw, r * th))
        t_sec = idx * 0.5
        draw.rectangle([c * tw, r * th, c * tw + 96, r * th + 26], fill=(0, 0, 0))
        draw.text((c * tw + 6, r * th + 6), f"{sid} {t_sec:.1f}s", fill=(255, 230, 80))
    canvas.save(out_jpg, quality=88)
    for old in tmp_dir.glob("*.jpg"):
        old.unlink()
    tmp_dir.rmdir()
    return out_jpg


def build_plans() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    amap = json.loads((WORK_DIR / "asset_map.json").read_text(encoding="utf-8"))

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

    f_ye = amap["叶寻"]["front_1k"]
    f_lin = amap["林双双"]["front_1k"]
    f_chu = amap["楚南"]["front_1k"]
    f_zhao = amap["赵帆"]["front_1k"]
    f_qian = amap["夏芊芊"]["front_1k"]
    f_jian = amap["夏建国"]["front_1k"]
    f_thug = amap["混混"]["front_1k"]
    f_chen = amap["陈伯"]["front_1k"]

    sc_banquet = amap["双林轩总部顶层试菜厅"]["main_1k"]
    sc_lin = amap["沙正街林家食府老店大堂"]["main_1k"]
    sc_street = amap["重庆老街对门双火锅铺街景"]["main_1k"]
    sc_xia_hall = amap["夏氏小厨前厅与传菜口"]["main_1k"]
    sc_xia_kitch = amap["夏氏小厨后厨猛火炒灶"]["main_1k"]
    p_pot = amap["紫铜子母鸳鸯锅"]["main_1k"]

    # ==================== EPISODE 1 (14 GROUPS) ====================
    ep1 = [
        {
            "id": "1-1-01", "episode": 1, "duration": 12, "seed": 71101,
            "description": "上市前夕庆功宴，叶寻刚在秘方无偿并入确认书摁完红手印，林双双一把抽走文件并将总厨金帽递给赵帆。",
            "dialogue": "叶寻：双双……这帽子怎么给他了？\n林双双：都要敲钟上市了。后厨往后归赵主厨。",
            "assetNames": ["双林轩总部顶层试菜厅", "叶寻 · 2020研发总厨白服", "林双双 · 塞纳左岸酒红礼服", "赵帆", "配方无偿归属确认书与调岗单"],
            "ref_images": [kf("1-1-01"), f_ye_2020, f_lin_banq, f_zhao],
            "ref_audios": [v_ye, v_lin],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The man standing on screen-left beside the banquet table in <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The woman standing on screen-right in <Picture 1>, matching <Picture 3>. Voice matches Audio 2.\n"
                "- <Subject 3>: The newly hired chef standing to the right of <Subject 2>, matching <Picture 4>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-3.5s) Medium close-up two-shot framed from <Picture 1> behind a blurred foreground champagne tower.\n"
                "- [Shot 2] (3.5s-7.7s) Medium three-shot from the same south side of the table showing <Subject 1> on screen-left, <Subject 2> in center, and <Subject 3> on screen-right.\n"
                "- [Shot 3] (7.7s-12.0s) Over-the-shoulder close-up past <Subject 1>'s right shoulder onto <Subject 2> and <Subject 3>.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-3.4s): As <Subject 1> lifts his red-inked right thumb from the signed agreement paper, <Subject 2> snatches the agreement decisively off the table and tucks it into a folder under her left arm while <Subject 1>'s hand freezes mid-air.\n"
                "- [Shot 2] (3.6s-7.6s): <Subject 2> picks up the gold-trimmed ceremonial cap from the tray and hands it to <Subject 3>, who cradles it smugly against his chest; stunned, <Subject 1> (S1) steps half a pace forward and asks: <d>[Chinese] 双双，这帽子怎么给他了。</d>\n"
                "- [Shot 3] (7.9s-11.6s): Turning her chin coolly back toward <Subject 1>, <Subject 2> (S2) declares coldly: <d>[Chinese] 都要敲钟上市了，后厨往后归赵主厨。</d> Immediately upon finishing, she presses her lips shut in icy detachment.\n"
                "[Environment]\n- Upscale banquet dining room at night with warm crystal chandelier and champagne tower reflections.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Crisp paper snatch, stunned male question, icy female declaration, subtle banquet room tone, zero music."
            ),
        },
        {
            "id": "1-1-04", "episode": 1, "duration": 12, "seed": 71104,
            "description": "楚南两指嫌弃地拈起叶寻洗得发白的旧围布丢进垃圾桶羞辱土锅底，赵帆捧着总厨礼帽得意宣告改做法式鹅肝融火锅。",
            "dialogue": "楚南：老叶，上市得讲门面。你那套土锅底，早该翻篇了。\n赵帆：往后店里主打法式鹅肝融火锅，只接高档客。",
            "assetNames": ["双林轩总部顶层试菜厅", "叶寻 · 2020研发总厨白服", "楚南 · 海归并购总监西装", "赵帆"],
            "ref_images": [kf("1-1-04"), kf("1-1_master_4p"), f_ye_2020, f_chu_exec, f_zhao],
            "ref_audios": [v_chu, v_zhao],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The man standing silently on screen-left beside the round marble table in <Picture 1> and <Picture 2>, matching <Picture 3>.\n"
                "- <Subject 2> (S1): The executive man on screen-right in <Picture 1> and <Picture 2>, matching <Picture 4>. Voice matches Audio 1.\n"
                "- <Subject 3> (S2): The Western-style chef holding the white gold-trimmed ceremonial cap on the far right in <Picture 2>, matching <Picture 5>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-2.4s) Medium shot framed from <Picture 1> beside the round marble table, dining chair, and cylindrical floor trash bin.\n"
                "- [Shot 2] (2.4s-7.4s) Slightly high-angle medium close-up inside the exact night-window VIP room of <Picture 2> favoring <Subject 2> on screen-right beside the round marble table.\n"
                "- [Shot 3] (7.4s-12.0s) Close-up inside <Picture 2> on <Subject 3> on screen-right holding the white gold-trimmed ceremonial cap proudly at his chest.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-2.3s): Wrinkling his nose in disgust, <Subject 2> pinches a corner of the faded old work cloth off the chair back with two fingers and holds it over the floor trash bin while <Subject 1> glares with closed lips.\n"
                "- [Shot 2] (2.5s-7.2s): Dropping the faded cloth into the trash bin and dusting his fingertips together, <Subject 2> (S1) looks toward screen-left and sneers: <d>[Chinese] 老叶，上市得讲门面，你那套土锅底，早该翻篇了。</d>\n"
                "- [Shot 3] (7.6s-11.6s): Resting both hands smugly on the white gold-trimmed ceremonial cap from <Picture 2> at his chest, <Subject 3> (S2) tilts his chin up toward screen-left and boasts: <d>[Chinese] 往后店里主打法式鹅肝融火锅，只接高档客。</d>\n"
                "[Environment]\n- Luxury corporate banquet VIP room at night (<Picture 2>) with round grey marble table and floor-to-ceiling city skyline window.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Cloth thudding into bin, arrogant male sneer, pretentious male boast, zero music."
            ),
        },
        {
            "id": "1-1-07", "episode": 1, "duration": 13, "seed": 71107,
            "description": "叶寻急切争辩撤掉温补底料外地客受不了重辣，被林双双抽出调岗单厉声打断翻脸训斥，叶寻彻骨心寒。",
            "dialogue": "叶寻：撤了我家的温补底料，外地客哪受得了这重辣——\n林双双：少往自己脸上贴金！没楚南铺路做推广，你现在还在小县城守破灶呢！",
            "assetNames": ["双林轩总部顶层试菜厅", "叶寻 · 2020研发总厨白服", "林双双 · 塞纳左岸酒红礼服", "配方无偿归属确认书与调岗单"],
            "ref_images": [kf("1-1-07"), f_ye_2020, f_lin_banq],
            "ref_audios": [v_ye, v_lin],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The man on screen-left in <Picture 1> with a metal lanyard badge at his chest, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The woman on screen-right holding a black folder, matching <Picture 3>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.5s) Close-up framed from <Picture 1> on <Subject 1> facing screen-right.\n"
                "- [Shot 2] (4.5s-11.0s) Reverse close-up from the same 180-degree side on <Subject 2> on screen-right facing screen-left.\n"
                "- [Shot 3] (11.0s-13.0s) Tight close-up back on <Subject 1> on screen-left in silent shock.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-4.4s): Leaning forward urgently and gesturing with his right hand, <Subject 1> (S1) argues earnestly: <d>[Chinese] 撤了我家的温补底料，外地客哪受得了这重辣。</d>\n"
                "- [Shot 2] (4.6s-10.8s): Pulling a printed transfer slip sharply out of her folder, <Subject 2> (S2) glares at screen-left and snaps harshly: <d>[Chinese] 少往自己脸上贴金，没楚南铺路做推广，你现在还在小县城守破灶呢。</d> She presses her lips shut right as the line finishes.\n"
                "- [Shot 3] (11.0s-13.0s): <Subject 1> stands frozen with lips pressed tightly shut, eyes turning ice-cold in bitter realization.\n"
                "[Environment]\n- Upscale banquet room with warm bokeh lights.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Urgent male plea cut off by sharp paper rustle and biting female rebuke, silent room tension, zero music."
            ),
        },
        {
            "id": "1-1-10", "episode": 1, "duration": 13, "seed": 71110,
            "description": "林双双将郊区仓库调岗单重重拍在叶寻胸口并亲昵挽住楚南胳膊，楚南扇着鼻子嫌弃草药味撵叶寻腾地方。",
            "dialogue": "林双双：看在以前的分上，郊区仓库给你留了个位置。去不去随你。\n楚南：行了叶师傅，腾地方吧，这一身草药味儿怪冲的。",
            "assetNames": ["双林轩总部顶层试菜厅", "叶寻 · 2020研发总厨白服", "林双双 · 塞纳左岸酒红礼服", "楚南 · 海归并购总监西装", "赵帆"],
            "ref_images": [kf("1-1-10"), kf("1-1_master_4p"), f_ye_2020, f_lin_banq, f_chu_exec, f_zhao],
            "ref_audios": [v_lin, v_chu],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The man standing on screen-left in <Picture 1> and <Picture 2>, matching <Picture 3>.\n"
                "- <Subject 2> (S1): The woman on screen-right in <Picture 1> and <Picture 2>, matching <Picture 4>. Voice matches Audio 1.\n"
                "- <Subject 3> (S2): The executive man standing to the right of <Subject 2> in <Picture 2>, matching <Picture 5>. Voice matches Audio 2.\n"
                "- <Subject 4>: The chef standing on the far right in <Picture 2>, matching <Picture 6>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-2.4s) Profile medium close-up framed from <Picture 1> beside the round grey marble table edge.\n"
                "- [Shot 2] (2.4s-8.4s) Over-the-shoulder shot past <Subject 1>'s right shoulder inside the exact night-skyline window VIP room of <Picture 2> (strictly keeping the round grey marble table and night floor-to-ceiling window behind them, never cutting to a windowless corridor) as <Subject 2> links arms with <Subject 3> beside <Subject 4>.\n"
                "- [Shot 3] (8.4s-13.0s) Close-up two-shot inside <Picture 2> in front of the night city skyline window favoring <Subject 3> with <Subject 2> holding his left arm.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-2.3s): <Subject 2> slaps the printed transfer slip hard against <Subject 1>'s left chest and withdraws her hand; the paper slides down onto the round marble table edge while <Subject 1> stands motionless.\n"
                "- [Shot 2] (2.5s-8.2s): Stepping back half a pace beside the round marble table in <Picture 2> to link both hands affectionately around <Subject 3>'s left arm, <Subject 2> (S1) speaks condescendingly toward screen-left: <d>[Chinese] 看在以前的分上，郊区仓库给你留了个位置，去不去随你。</d>\n"
                "- [Shot 3] (8.5s-12.6s): Waving his right hand dismissively twice in front of his nose, <Subject 3> (S2) smirks at screen-left and says: <d>[Chinese] 行了叶师傅，腾地方吧，这一身草药味儿怪冲的。</d>\n"
                "[Environment]\n- Upscale banquet VIP room at night (<Picture 2>) with round grey marble table and floor-to-ceiling city skyline window.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Crisp slap of paper on chest, condescending female voice, mocking male dismissal, zero music."
            ),
        },
        {
            "id": "1-1-13", "episode": 1, "duration": 10, "seed": 71113,
            "description": "叶寻盯着垃圾桶里的旧围布攥拳绷白，一把扯断胸前总厨工牌重重砸在桌面调岗单旁，转身推开包厢门决绝离场。",
            "dialogue": "",
            "assetNames": ["双林轩总部顶层试菜厅", "叶寻 · 2020研发总厨白服", "林双双 · 塞纳左岸酒红礼服", "楚南 · 海归并购总监西装"],
            "ref_images": [kf("1-1-13"), kf("1-1-13_aux"), f_ye_2020, f_lin_banq, f_chu_exec],
            "ref_audios": [],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The man whose left hand appears in <Picture 1> and who exits toward the wooden doors in <Picture 2>, matching <Picture 3>.\n"
                "- <Subject 2>: The woman standing behind the round grey marble table in <Picture 2>, matching <Picture 4>.\n"
                "- <Subject 3>: The executive man standing beside <Subject 2> behind the round grey marble table in <Picture 2>, matching <Picture 5>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-2.3s) High-angle close-up framed from <Picture 1> showing <Subject 1>'s left hand in the foreground and the faded cloth inside the cylindrical floor trash bin beside the round marble table.\n"
                "- [Shot 2] (2.3s-5.0s) Fast push-in close-up on <Subject 1>'s upper chest and face in front of the night skyline window of <Picture 2>.\n"
                "- [Shot 3] (5.0s-7.0s) Tabletop close-up on the round grey marble table surface beside a champagne flute and the white transfer slip.\n"
                "- [Shot 4] (7.0s-10.0s) Wide interior shot framed directly from <Picture 2> across the round grey marble table (both <Subject 2> and <Subject 3> remain standing behind the round table, nobody seated) toward the dark double wooden doors at right-rear.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-2.2s): <Subject 1>'s left fingers clench into a rock-hard fist with white knuckles.\n"
                "- [Shot 2] (2.4s-4.9s): With reddened, razor-cold eyes and closed lips, <Subject 1> grabs the metal badge at his chest with his right hand and rips the lanyard cord clean off.\n"
                "- [Shot 3] (5.1s-6.9s): <Subject 1>'s right hand slams the metal badge and snapped cord sharply down onto the round grey marble table beside the transfer slip, making the champagne in the glass tremble.\n"
                "- [Shot 4] (7.1s-10.0s): Leaving <Subject 2> and <Subject 3> standing behind the round grey marble table on screen-left (<Picture 2>), <Subject 1> strides briskly to the right-rear wooden door, pushes it open, and exits.\n"
                "[Environment]\n- Luxury banquet VIP room (<Picture 2>) with round grey marble table, night city window, and dark wooden doors.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Snapping lanyard cord, sharp metallic slam of badge on marble table, brisk footsteps, heavy wooden door pushed open, distant thunder rumble, zero speech, zero music."
            ),
        },
        {
            "id": "1-2-01", "episode": 1, "duration": 13, "seed": 71201,
            "description": "暴雨长街叶寻浑身湿透死攥爷爷留下的旧木牌痛悔心声，刺目远光灯劈开雨幕伴随着急刹声吞没画面，旧木牌与手臂坠落积水黑沉。",
            "dialogue": "叶寻（心声）：十年心血，连爷爷留的方子……全喂了狗。",
            "assetNames": ["集团大厦旋转门雨夜街口", "叶寻 · 2020研发总厨白服"],
            "ref_images": [kf("1-2-01"), f_ye_2020],
            "ref_audios": [],
            "vo_custom": {
                "voice": v_ye,
                "face_1k": f_ye_2020,
                "text": "十年心血，连爷爷留的方子，全喂了狗。",
                "duration": 5,
                "dst_start": 3.25,
                "max_len": 4.0,
                "base_duck": 0.34,
            },
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The drenched man walking in the pouring rain in <Picture 1>, matching <Picture 2>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-3.0s) Wide rainy night street shot framed from <Picture 1>.\n"
                "- [Shot 2] (3.0s-7.5s) Tight close-up on <Subject 1> in the pouring rain clutching a dark carved wooden plaque tightly against his chest.\n"
                "- [Shot 3] (7.5s-10.0s) Fast push-in extreme close-up on <Subject 1>'s rain-streaked face as blinding white car headlights slash in from screen-right.\n"
                "- [Shot 4] (10.0s-13.0s) Low ground-level close-up of dark rain puddles on wet asphalt.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-2.9s): Soaked to the bone in torrential rain, <Subject 1> stumbles forward to the center lane of the empty wet street and pulls an old dark wooden plaque from his pocket.\n"
                "- [Shot 2] (3.1s-7.4s): Rain streaming down his face, <Subject 1> clutches the old wooden plaque fiercely against his chest with trembling white knuckles, keeping his lips pressed tightly shut in silent anguish.\n"
                "- [Shot 3] (7.6s-9.9s): Hearing a sudden horn, <Subject 1> whips his head toward screen-right as blinding twin white headlight beams rapidly flood his widening pupils and wash the entire frame in pure white glare.\n"
                "- [Shot 4] (10.1s-13.0s): After a brief camera jolt, the dark wooden plaque skids to a stop across the rain puddle while <Subject 1>'s limp drenched right forearm rests motionless in the water as the frame fades to pitch black.\n"
                "[Environment]\n- Torrential rainstorm on a wet asphalt city street at night.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Heavy pouring rain and thunder, blaring car horn and screeching tires at 7.6s, dull impact thud and wooden plaque skidding in water at 10.0s fading into silence, zero speech, zero music."
            ),
        },
        {
            "id": "1-3-01", "episode": 1, "duration": 12, "seed": 71301,
            "description": "老吊扇吱呀乱转，叶寻在2005年林记大堂木桌上猛然惊醒，摸向腿边完好无损的试锅草本包，抬头见年轻林双双伸手索要秘方、楚南仰头灌冰可乐。",
            "dialogue": "林双双：叶寻，发什么呆呢？赶紧把你爷爷那方子拿出来呀！",
            "assetNames": ["沙正街林家食府老店大堂", "叶寻", "林双双", "楚南"],
            "ref_images": [kf("1-3-01"), f_ye, f_lin, f_chu, sc_lin],
            "ref_audios": [v_lin],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The young man sleeping face-down at the wooden table in <Picture 1>, matching <Picture 2>.\n"
                "- <Subject 2> (S1): The young woman standing on screen-right of the table, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 3>: The young man lounging on a wooden chair beside <Subject 2> with an iced cola can, matching <Picture 4>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-3.8s) Medium close-up framed from <Picture 1> beneath the spinning vintage green ceiling fan.\n"
                "- [Shot 2] (3.8s-7.0s) High-angle close-up on the worn army-green canvas backpack resting on the wooden bench beside <Subject 1>'s leg.\n"
                "- [Shot 3] (7.0s-12.0s) Over-the-shoulder medium shot past <Subject 1>'s left shoulder onto <Subject 2> standing upper-right and <Subject 3> seated lower-right across the table with a half-sheet sketch on the wood.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-3.7s): <Subject 1> jolts upright from the greasy wooden table gasping heavily, sweeps a stunned look around the sunlit old hall, and reaches his right hand swiftly down toward the canvas backpack beside his leg.\n"
                "- [Shot 2] (3.9s-6.9s): <Subject 1>'s right hand reaches into the half-unzipped canvas backpack and squeezes the bulging twine-tied coarse cloth herb bundle firmly inside.\n"
                "- [Shot 3] (7.1s-11.6s): While <Subject 3> tilts his head back gulping iced cola from a red aluminum can, <Subject 2> (S1) frowns impatiently, holds out her open right palm toward <Subject 1>, and demands: <d>[Chinese] 叶寻，发什么呆呢，赶紧把你爷爷那方子拿出来呀。</d>\n"
                "[Environment]\n- Hot September 2005 afternoon inside an old Chongqing small eatery hall (<Picture 5>) with creaking ceiling fan.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Creaking ceiling fan and cicadas, sharp gasp, canvas rustle, cola gulp, impatient female demand, zero music."
            ),
        },
        {
            "id": "1-3-04", "episode": 1, "duration": 10, "seed": 71304,
            "description": "叶寻确认回到2005年试锅当日眼神转冷，对桌楚南扯着领口嫌九月天太热嘲讽只有干苦力的才吃火锅。",
            "dialogue": "叶寻（心声）：还没交出去……我回到试锅这天了？\n楚南：双双，这九月天热得冒烟，谁进门吃火锅啊？干苦力的？",
            "assetNames": ["沙正街林家食府老店大堂", "叶寻", "楚南"],
            "ref_images": [kf("1-3-04"), f_ye, f_chu],
            "ref_audios": [v_chu],
            "vo_custom": {
                "voice": v_ye,
                "face_1k": f_ye,
                "text": "还没交出去，我回到试锅这天了。",
                "duration": 5,
                "dst_start": 0.35,
                "max_len": 3.6,
                "base_duck": 0.22,
            },
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The young man seated on screen-left in <Picture 1>, matching <Picture 2>.\n"
                "- <Subject 2> (S1): The young man lounging on a chair on screen-right holding an aluminum cola can, matching <Picture 3>. Voice matches Audio 1.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.3s) Push-in close-up starting from <Picture 1> advancing 0.35m onto <Subject 1>'s sharp eyes.\n"
                "- [Shot 2] (4.3s-10.0s) Reverse close-up from the same 180-degree side onto <Subject 2> seated on screen-right.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-4.2s): Looking across the table with his lips pressed completely shut and motionless, <Subject 1> steadies his breathing as shock gives way to razor-sharp, icy clarity.\n"
                "- [Shot 2] (4.5s-9.5s): Lowering the cola can from his mouth and fanning his collar disdainfully, <Subject 2> (S1) scoffs toward screen-left: <d>[Chinese] 双双，这九月天热得冒烟，谁进门吃火锅啊，干苦力的。</d>\n"
                "[Environment]\n- Sunlit old Chongqing eatery hall at midday.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Quiet creaking fan and cicadas during [Shot 1], aluminum can crinkle and arrogant male scoff in [Shot 2], zero music."
            ),
        },
        {
            "id": "1-3-06", "episode": 1, "duration": 14, "seed": 71306,
            "description": "楚南把空可乐罐重重顿在桌上环视空荡大堂，撺掇林双双改开高档西餐厅赚重大学生钱，林双双心动却苦恼账上没钱请西餐师傅。",
            "dialogue": "楚南：听我的，直接改高档西餐厅！外头重大的学生就吃这套。\n林双双：我也想啊，可家里账上没几个活钱了，上哪儿请西餐师傅去……",
            "assetNames": ["沙正街林家食府老店大堂", "楚南", "林双双", "叶寻"],
            "ref_images": [kf("1-3-06"), f_chu, f_lin, f_ye],
            "ref_audios": [v_chu, v_lin],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young man seated on screen-right in <Picture 1> holding the empty cola can, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The young woman standing beside <Subject 1> in <Picture 1>, matching <Picture 3>. Voice matches Audio 2.\n"
                "- <Subject 3>: The young man seated on the far left edge in <Picture 1>, matching <Picture 4>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-2.2s) Medium shot framed from <Picture 1> showing the empty dining tables across the hall.\n"
                "- [Shot 2] (2.2s-7.6s) Close-up on <Subject 1> on screen-right tapping the table edge.\n"
                "- [Shot 3] (7.6s-14.0s) Close-up on <Subject 2> on screen-right looking down toward <Subject 1>.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-2.1s): <Subject 1> thumps the empty aluminum cola can onto the wooden table and sweeps an arrogant look across the empty hall.\n"
                "- [Shot 2] (2.3s-7.3s): Tapping his index finger twice on the table and gesturing grandly up at <Subject 2>, <Subject 1> (S1) pitches enthusiastically: <d>[Chinese] 听我的，直接改高档西餐厅，外头重大的学生就吃这套。</d>\n"
                "- [Shot 3] (7.8s-13.4s): Crossing her arms as her eyes light up with vanity and then cloud over in worry, <Subject 2> (S2) sighs to <Subject 1>: <d>[Chinese] 我也想啊，可家里账上没几个活钱了，上哪儿请西餐师傅去。</d>\n"
                "[Environment]\n- Sunlit empty old eatery hall with wooden tables.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Hollow thump of empty aluminum can on wood, boastful male pitch, fretful female sigh and reply, zero music."
            ),
        },
        {
            "id": "1-3-09", "episode": 1, "duration": 11, "seed": 71309,
            "description": "楚南拍胸口包揽介绍星级西餐主厨，林双双惊喜之余仍不甘心放过叶寻，转头与楚南齐齐盯住叶寻催讨秘方。",
            "dialogue": "楚南：找我啊！我认识个星级西餐主厨，打声招呼的事儿。\n林双双：当真？不过叶寻答应今儿试锅了……叶寻，东西呢？",
            "assetNames": ["沙正街林家食府老店大堂", "楚南", "林双双", "叶寻"],
            "ref_images": [kf("1-3-09"), kf("1-3-06"), f_chu, f_lin, f_ye],
            "ref_audios": [v_chu, v_lin],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young man leaning back in his wooden chair behind the square wooden table in <Picture 1> and <Picture 2>, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The young woman standing beside him in <Picture 2>, matching <Picture 4>. Voice matches Audio 2.\n"
                "- <Subject 3>: The young man seated on the wooden bench on screen-left in <Picture 2>, matching <Picture 5>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-5.2s) Medium close-up framed from <Picture 1> behind the square wooden table with the sketch paper and red aluminum cola can.\n"
                "- [Shot 2] (5.2s-11.0s) Over-the-shoulder medium shot framed from the exact room geometry of <Picture 2> past <Subject 3> on screen-left onto <Subject 2> and <Subject 1> on screen-right across the square wooden table.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-5.0s): Patting his own chest smugly with his right hand, <Subject 1> (S1) boasts up to <Subject 2>: <d>[Chinese] 找我啊，我认识个星级西餐主厨，打声招呼的事儿。</d>\n"
                "- [Shot 2] (5.4s-10.5s): Flashing a delighted smile at <Subject 1> before turning sharply with him across the square wooden table of <Picture 2> to stare at <Subject 3> and holding out her hand again, <Subject 2> (S2) demands: <d>[Chinese] 当真，不过叶寻答应今儿试锅了，叶寻，东西呢。</d>\n"
                "[Environment]\n- Sunlit old eatery dining hall (<Picture 2>) with square dark-brown wooden table and green ceiling fan.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Hand patting chest, smug male brag, greedy female demand, creaking ceiling fan, zero music."
            ),
        },
        {
            "id": "1-3-11", "episode": 1, "duration": 12, "seed": 71311,
            "description": "叶寻果断拉死帆布书包拉链锁起草本包，当着两人面把桌上《林记火锅改造草图》撕成两半丢进痰桶，林双双拍桌炸毛怒斥。",
            "dialogue": "林双双：叶寻你发什么疯？！好端端撕它干嘛！",
            "assetNames": ["沙正街林家食府老店大堂", "叶寻", "林双双", "楚南"],
            "ref_images": [kf("1-3-11"), kf("1-3-12_aux"), f_ye, f_lin, f_chu],
            "ref_audios": [v_lin],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The young man seated on screen-left in <Picture 2>, matching <Picture 3>.\n"
                "- <Subject 2> (S1): The young woman standing on screen-right in <Picture 2>, matching <Picture 4>. Voice matches Audio 1.\n"
                "- <Subject 3>: The young man seated beside <Subject 2> in <Picture 2>, matching <Picture 5>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-2.4s) High-angle close-up framed from <Picture 1> on the army-green canvas backpack on the wooden bench.\n"
                "- [Shot 2] (2.4s-5.6s) Medium close-up three-shot framed from <Picture 2> across the wooden table.\n"
                "- [Shot 3] (5.6s-7.6s) High-angle close-up of the white enamel spittoon beside the table leg.\n"
                "- [Shot 4] (7.6s-12.0s) Close-up on <Subject 2> leaning over the right edge of the table.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-2.3s): <Subject 1>'s right hand pulls the metal zipper briskly from left to right, sealing the canvas backpack completely shut.\n"
                "- [Shot 2] (2.5s-5.5s): With an expressionless stare at <Subject 2> and <Subject 3>, <Subject 1> lifts the renovation sketch paper from the table and rips it cleanly in half right in front of their shocked faces.\n"
                "- [Shot 3] (5.7s-7.5s): <Subject 1>'s right hand drops both torn halves of paper straight into the white enamel spittoon on the floor.\n"
                "- [Shot 4] (7.8s-11.3s): Slamming both palms onto the wooden table and leaning forward with blazing eyes, <Subject 2> (S1) yells furiously: <d>[Chinese] 叶寻你发什么疯，好端端撕它干嘛。</d> Immediately upon finishing, she clamps her lips shut and glares.\n"
                "[Environment]\n- Sunlit 2005 eatery hall.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Sharp metallic zipper pull, crisp paper rip, paper dropping into enamel spittoon, palms slapping table, furious female shout, zero music."
            ),
        },
        {
            "id": "1-3-15", "episode": 1, "duration": 15, "seed": 71315,
            "description": "叶寻拿楚南嫌火锅土的原话淡然回敬，林双双翻旧账倒打一耙，楚南抱臂抖腿阴阳怪气激将嘲讽。",
            "dialogue": "叶寻：楚少不是说了吗，火锅太土，别糟蹋你家这地方。\n林双双：说两句你还甩上脸子了？昨晚拍胸脯说帮我家的人是谁？\n楚南：嗨，人家这是有自知之明，不好意思拿土方子出来丢人。",
            "assetNames": ["沙正街林家食府老店大堂", "叶寻", "林双双", "楚南"],
            "ref_images": [kf("1-3-15"), kf("1-3_post_tear_master"), f_ye, f_lin, f_chu],
            "ref_audios": [v_ye, v_lin, v_chu],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young man seated calmly on the wooden bench on screen-left in <Picture 1> and <Picture 2> with his hands resting on the zipped canvas backpack on the bench, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The young woman standing beside the square wooden table on right-center in <Picture 2>, matching <Picture 4>. Voice matches Audio 2.\n"
                "- <Subject 3> (S3): The young man seated in his wooden chair on screen-right in <Picture 2>, matching <Picture 5>. Voice matches Audio 3.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.7s) Medium close-up framed from <Picture 1> beside the square wooden table on <Subject 1> facing screen-right.\n"
                "- [Shot 2] (4.7s-10.2s) Over-the-shoulder close-up inside the exact square-table hall of <Picture 2> past <Subject 1>'s left shoulder onto <Subject 2> on screen-right.\n"
                "- [Shot 3] (10.2s-15.0s) Close-up inside <Picture 2> on <Subject 3> folding his arms smugly in his wooden chair behind the square wooden table on screen-right.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-4.5s): Unmoved by her anger, <Subject 1> (S1) nods toward screen-right and replies evenly: <d>[Chinese] 楚少不是说了吗，火锅太土，别糟蹋你家这地方。</d>\n"
                "- [Shot 2] (4.9s-10.0s): Straightening up beside the square wooden table and pointing an accusing finger at <Subject 1>, <Subject 2> (S2) snaps indignantly: <d>[Chinese] 说两句你还甩上脸子了，昨晚拍胸脯说帮我家的人是谁。</d>\n"
                "- [Shot 3] (10.4s-14.6s): Folding his arms and tilting his head in a mocking sneer toward screen-left, <Subject 3> (S3) says sarcastically: <d>[Chinese] 嗨，人家这是有自知之明，不好意思拿土方子出来丢人。</d>\n"
                "[Environment]\n- Sunlit 2005 Chongqing eatery hall (<Picture 2>) with square dark-brown wooden table and green ceiling fan.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Cool unhurried male reply, indignant female accusation, sarcastic male mockery, zero music."
            ),
        },
        {
            "id": "1-3-18", "episode": 1, "duration": 10, "seed": 71318,
            "description": "叶寻毫不在意激将，干脆宣告退出，利落拎起帆布书包甩上右肩转身拉开大堂木门，林双双在身后慌乱急喊。",
            "dialogue": "叶寻：嗯。你们改西餐吧，我不掺和了。\n林双双：一中午连个人影都没有，你现在甩手走人？！",
            "assetNames": ["沙正街林家食府老店大堂", "重庆老街对门双火锅铺街景", "叶寻", "林双双", "楚南"],
            "ref_images": [kf("1-3-18"), kf("1-3_doorway_master"), f_ye, f_lin, f_chu],
            "ref_audios": [v_ye, v_lin],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young man seated on the wooden bench in <Picture 1> and standing alone at the open doorway threshold in <Picture 2>, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The young woman standing back beside the square wooden table on screen-left in <Picture 2>, matching <Picture 4>. Voice matches Audio 2.\n"
                "- <Subject 3>: The young man seated at the square wooden table on screen-left in <Picture 2>, matching <Picture 5>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-3.5s) Medium close-up framed from <Picture 1> beside the square wooden table on <Subject 1> gripping the canvas backpack strap on the bench.\n"
                "- [Shot 2] (3.5s-5.8s) Medium shot beside the wooden bench and square wooden table as <Subject 1> stands up and slings the army-green canvas backpack onto his right shoulder.\n"
                "- [Shot 3] (5.8s-10.0s) Wide interior doorway shot framed directly from <Picture 2>: <Subject 1> stands alone at the weathered open wooden doorway threshold on screen-right opening onto the quiet sunlit bluestone lane (zero modern cars outside), while <Subject 2> remains standing far back on screen-left beside the square wooden table without running to the door.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-3.3s): Giving a crisp nod, <Subject 1> (S1) says coolly: <d>[Chinese] 嗯，你们改西餐吧，我不掺和了。</d>\n"
                "- [Shot 2] (3.6s-5.7s): Without sparing the table another glance, <Subject 1> rises briskly from the wooden bench, swings the army-green canvas backpack onto his right shoulder, and grips the front strap.\n"
                "- [Shot 3] (5.9s-9.6s): As <Subject 1> reaches the open weathered wooden doorway on screen-right (<Picture 2>), <Subject 2> (S2) stays back beside the square wooden table on screen-left shouting anxiously toward his back: <d>[Chinese] 一中午连个人影都没有，你现在甩手走人。</d>\n"
                "[Environment]\n- Sunlit 2005 eatery hall opening through weathered dark-brown wooden doors onto a quiet bluestone pedestrian lane (<Picture 2>).\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Crisp male farewell, heavy canvas bag swung onto shoulder, creaking wooden door pulled open, anxious female shout from back of hall, zero music."
            ),
        },
        {
            "id": "1-3-21", "episode": 1, "duration": 15, "seed": 71391,
            "description": "叶寻在门口冷刺回敬后迈入阳光老街暗下决心，林双双脸色骤变追出门槛一把死死拽住他的帆布书包带厉声喝阻切集。",
            "dialogue": "叶寻：找你的星级主厨去。\n叶寻（心声）：上辈子拿我当血包，这回，如你们的愿。\n林双双：叶寻你给我站住！话没说清楚往哪儿走——谁准你反悔的？！",
            "assetNames": ["沙正街林家食府老店大堂", "重庆老街对门双火锅铺街景", "叶寻", "林双双"],
            "ref_images": [kf("1-3-21"), kf("2-1-01"), f_ye, f_lin],
            "ref_audios": [v_ye, v_lin],
            "vo_custom": {
                "voice": v_ye,
                "face_1k": f_ye,
                "text": "上辈子拿我当血包，这回，如你们的愿。",
                "duration": 5,
                "dst_start": 2.90,
                "max_len": 3.7,
                "base_duck": 0.22,
            },
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young man standing alone at the open wooden doorway threshold in <Picture 1> and on the lower stone step in <Picture 2> with the army-green canvas backpack on his right shoulder, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The young woman chasing out onto the upper stone step of the weathered wooden doorway in <Picture 2>, matching <Picture 4>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-2.6s) Medium close-up framed from <Picture 1> on <Subject 1> alone at the sunlit wooden doorway threshold.\n"
                "- [Shot 2] (2.6s-6.8s) Instant hard cut to a tight close-up on <Subject 1>'s chest and resolute face stepping down onto the sunlit stone steps outside the doorway.\n"
                "- [Shot 3] (6.8s-9.0s) Instant hard cut to the exact doorway stone steps of <Picture 2> as <Subject 2> rushes out onto the upper step on screen-right behind <Subject 1> (on the lower step on screen-left) and grabs his right-shoulder green backpack strap.\n"
                "- [Shot 4] (9.0s-15.0s) Medium two-shot matching the exact doorway steps blocking of <Picture 2>: <Subject 1> on the lower step on screen-left, <Subject 2> on the upper step on screen-right gripping his taut army-green backpack strap.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-2.4s): Half-glancing back over his shoulder without turning around, <Subject 1> (S1) replies coldly: <d>[Chinese] 找你的星级主厨去。</d>\n"
                "- [Shot 2] (2.7s-6.7s): Stepping forward down the sunlit stone steps with sharp, resolute eyes, <Subject 1> grips his right backpack strap and keeps his lips completely closed and silent.\n"
                "- [Shot 3] (6.9s-8.9s): <Subject 2> dashes out through the weathered wooden doorway onto the upper stone step on screen-right (<Picture 2>) and grabs <Subject 1>'s army-green canvas backpack strap firmly with her right hand, yanking him to a halt on the lower step.\n"
                "- [Shot 4] (9.1s-14.4s): Holding the taut green canvas strap from the upper stone step on screen-right (<Picture 2>), <Subject 2> (S2) glares down at <Subject 1> and barks imperiously: <d>[Chinese] 叶寻你给我站住，话没说清楚往哪儿走，谁准你反悔的。</d> Both freeze in the exact standoff of <Picture 2>.\n"
                "[Environment]\n- Weathered wooden shop doorway and two grey stone steps in bright midday sunlight (<Picture 2>), zero text signboards.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Cool male retort in [Shot 1], steady footsteps on stone in [Shot 2], urgent running steps and taut canvas strap yank in [Shot 3], furious female command in [Shot 4], zero music."
            ),
        },
    ]

    # ==================== EPISODE 2 (12 GROUPS) ====================
    ep2 = [
        {
            "id": "2-1-01", "episode": 2, "duration": 13, "seed": 72101,
            "description": "林双双死拽书包带不撒手，自以为是断定叶寻是看楚南帮忙吃醋玩欲擒故纵，楚南倚在门框边抱臂戏谑嘲弄。",
            "dialogue": "林双双：行啊叶寻，跟我玩这一套——看楚南帮我出主意，吃醋了？\n楚南：至于吗老叶，大老爷们儿搞欲擒故纵，掉价了啊。",
            "assetNames": ["重庆老街对门双火锅铺街景", "叶寻", "林双双", "楚南"],
            "ref_images": [kf("2-1-01"), f_ye, f_lin, f_chu],
            "ref_audios": [v_lin, v_chu],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The young man standing on the lower step on screen-left in <Picture 1> with a black plastic digital watch on his left wrist, matching <Picture 2>.\n"
                "- <Subject 2> (S1): The young woman standing on the upper step on screen-right clutching <Subject 1>'s canvas backpack strap, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 3> (S2): The young man leaning against the right wooden doorframe, matching <Picture 4>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-1.9s) Medium close-up two-shot framed from <Picture 1> under harsh midday sunlight.\n"
                "- [Shot 2] (1.9s-7.6s) Over-the-shoulder close-up past <Subject 1>'s right shoulder onto <Subject 2> on screen-right.\n"
                "- [Shot 3] (7.6s-13.0s) Medium close-up favoring <Subject 3> leaning with folded arms against the right wooden doorframe.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-1.8s): Gripping the taut backpack strap with her right hand, <Subject 2> looks <Subject 1> up and down and curls her lips into a smug sneer while <Subject 1> keeps his lips closed.\n"
                "- [Shot 2] (2.0s-7.4s): Shaking the backpack strap smugly with lifted chin, <Subject 2> (S1) jeers at <Subject 1>: <d>[Chinese] 行啊叶寻，跟我玩这一套，看楚南帮我出主意，吃醋了。</d>\n"
                "- [Shot 3] (7.8s-12.5s): Leaning lazily against the doorframe and pointing casually toward screen-left, <Subject 3> (S2) chuckles mockingly: <d>[Chinese] 至于吗老叶，大老爷们儿搞欲擒故纵，掉价了啊。</d>\n"
                "[Environment]\n- Harsh midday sunlight on concrete steps outside an old Chongqing street eatery.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Midday cicadas, canvas strap tug, smug female jeer, mocking male chuckle, zero music."
            ),
        },
        {
            "id": "2-1-04", "episode": 2, "duration": 15, "seed": 72104,
            "description": "林双双施舍式勒令叶寻服软交秘方，叶寻咔哒解下左腕廉价塑料电子表直接拍回她掌心当场宣布分手，林双双震惊破防。",
            "dialogue": "林双双：差不多行了。服个软把方子交出来，刚才的事我翻篇。\n叶寻：东西收好。咱俩完了。\n林双双：你说什么？叶寻，你敢提分手？！",
            "assetNames": ["重庆老街对门双火锅铺街景", "林双双", "叶寻"],
            "ref_images": [kf("2-1-04"), kf("2-1-01"), f_lin, f_ye],
            "ref_audios": [v_lin, v_ye],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young woman standing on the upper stone step on screen-right in <Picture 1> and <Picture 2> gripping the taut green backpack strap with her right hand, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The young man standing on the lower stone step on screen-left in <Picture 2> wearing the army-green canvas backpack on his right shoulder, matching <Picture 4>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-5.0s) Medium close-up framed from <Picture 1> outside the weathered wooden doorway on <Subject 1> extending her open left palm at waist height while her right hand holds the taut shoulder-height green strap.\n"
                "- [Shot 2] (5.0s-7.3s) Tight close-up on <Subject 2>'s raised left wrist unclasping the small black plastic digital watch.\n"
                "- [Shot 3] (7.3s-11.2s) Medium close-up two-shot on the exact weathered wooden doorway stone steps of <Picture 2> (strictly keeping <Subject 2>'s army-green canvas backpack on his right shoulder and wooden doorway behind them) pushing in 0.3m onto <Subject 2> on screen-left.\n"
                "- [Shot 4] (11.2s-15.0s) Over-the-shoulder close-up on the exact wooden doorway steps of <Picture 2> past <Subject 2>'s shoulder onto <Subject 1> clutching the small black plastic watch.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-4.8s): Holding out her open left palm imperiously toward screen-left, <Subject 1> (S1) orders: <d>[Chinese] 差不多行了，服个软把方子交出来，刚才的事我翻篇。</d>\n"
                "- [Shot 2] (5.1s-7.2s): <Subject 2>'s right fingers unsnap the black plastic watch buckle from his left wrist with a sharp click and pull the watch free.\n"
                "- [Shot 3] (7.4s-11.0s): Standing on the lower stone step of <Picture 2> with his army-green canvas backpack on his right shoulder, <Subject 2> (S2) slaps the small plastic watch directly into <Subject 1>'s open left palm and states flatly: <d>[Chinese] 东西收好，咱俩完了。</d>\n"
                "- [Shot 4] (11.4s-14.6s): Glancing down at the small black plastic watch in her palm on the upper stone step of <Picture 2> and snapping her stunned eyes up at <Subject 2>, <Subject 1> (S1) gasps sharply: <d>[Chinese] 你说什么，叶寻，你敢提分手。</d>\n"
                "[Environment]\n- Weathered wooden shop doorway and two flat stone steps in midday sunlight (<Picture 2>), zero text signboards.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Condescending female command, crisp plastic watch click, slap of watch into palm, flat icy male breakup line, shocked female gasp, zero music."
            ),
        },
        {
            "id": "2-1-08", "episode": 2, "duration": 13, "seed": 72188,
            "description": "叶寻斩钉截铁划清界限，林双双攥着塑料表呆立原地哑口无言，叶寻转头冷讽激将楚南赶紧把吹出去的星级主厨请来。",
            "dialogue": "叶寻：分了。往后你家店是死是活，别来沾边。\n叶寻：楚少，刚吹出去的星级主厨，赶紧给人请来啊。",
            "assetNames": ["重庆老街对门双火锅铺街景", "叶寻", "林双双", "楚南"],
            "ref_images": [kf("2-1-08"), kf("2-1_post_watch_master"), f_ye, f_lin, f_chu],
            "ref_audios": [v_ye],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young man standing on the lower stone step on screen-left in <Picture 1> and <Picture 2> with the army-green canvas backpack on his right shoulder, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 2>: The young woman standing on the upper stone step in center-right of <Picture 2> clutching the small black plastic watch to her chest, matching <Picture 4>.\n"
                "- <Subject 3>: The young man leaning against the right wooden doorframe in <Picture 2>, matching <Picture 5>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.8s) Close-up framed from <Picture 1> on <Subject 1> facing screen-right.\n"
                "- [Shot 2] (4.8s-6.8s) Reverse close-up inside the exact wooden doorway steps of <Picture 2> on <Subject 2> clutching the small black plastic watch at her chest.\n"
                "- [Shot 3] (6.8s-13.0s) Medium three-shot framed directly from <Picture 2> on the two flat stone steps outside the weathered wooden doorway (zero brick stoves, zero plastic bags, zero signboards) showing <Subject 1> on screen-left, <Subject 2> frozen in center-right, and <Subject 3> at the right doorframe.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-4.5s): With cold finality, <Subject 1> (S1) speaks clearly: <d>[Chinese] 分了，往后你家店是死是活，别来沾边。</d>\n"
                "- [Shot 2] (4.9s-6.7s): Clutching the small black plastic watch tightly against her chest with closed lips, <Subject 2> stands frozen and speechless in stunned disbelief.\n"
                "- [Shot 3] (7.0s-12.4s): Shifting his gaze past <Subject 2> directly to <Subject 3> at the right wooden doorframe of <Picture 2> with a cool, ironic look, <Subject 1> (S1) says evenly: <d>[Chinese] 楚少，刚吹出去的星级主厨，赶紧给人请来啊。</d>\n"
                "[Environment]\n- Sunlit two flat stone steps in front of weathered wooden shop doors (<Picture 2>), zero text signboards.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Decisive male voice, plastic watch creak in fist, cool challenging male taunt, street cicadas, zero music."
            ),
        },
        {
            "id": "2-1-11", "episode": 2, "duration": 14, "seed": 72111,
            "description": "林双双慌忙扭头向楚南求证西餐主厨准不准，楚南好面子拍响胸口大包大揽说明天就把赵帆连装修队拉来，叶寻冷哂握住书包带。",
            "dialogue": "林双双：楚南，你刚说的那个主厨，到底准不准？\n楚南：什么准不准？就明天！我把星级主厨赵帆连装修队一块儿给你拉来！",
            "assetNames": ["重庆老街对门双火锅铺街景", "林双双", "楚南", "叶寻"],
            "ref_images": [kf("2-1-11"), kf("2-1_post_watch_master"), f_lin, f_chu, f_ye],
            "ref_audios": [v_lin, v_chu],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young woman on the upper stone step in <Picture 1> and <Picture 2> clutching the small black plastic watch, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The young man at the right wooden doorframe in <Picture 1> and <Picture 2>, matching <Picture 4>. Voice matches Audio 2.\n"
                "- <Subject 3>: The young man standing on the lower stone step on screen-left in <Picture 2> wearing the army-green canvas backpack on his right shoulder, matching <Picture 5>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.5s) Close-up framed from <Picture 1> on <Subject 1> looking anxiously toward right-rear.\n"
                "- [Shot 2] (4.5s-11.4s) Over-the-shoulder medium close-up inside <Picture 2> past <Subject 1>'s right shoulder onto <Subject 2> by the right wooden doorframe.\n"
                "- [Shot 3] (11.4s-14.0s) Medium two-shot framed from the exact doorway steps blocking of <Picture 2>: <Subject 3> on the lower step on screen-left wearing his army-green canvas backpack (strictly army-green strap, never beige) and <Subject 1> on the upper step on screen-right.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-4.3s): Turning desperately toward <Subject 2> behind her, <Subject 1> (S1) asks urgently: <d>[Chinese] 楚南，你刚说的那个主厨，到底准不准。</d>\n"
                "- [Shot 2] (4.7s-11.2s): Puffing out his chest and slapping his own chest twice loudly with his open right palm, <Subject 2> (S2) boasts loudly: <d>[Chinese] 什么准不准，就明天，我把星级主厨赵帆连装修队一块儿给你拉来。</d> He closes his mouth smugly right as he finishes.\n"
                "- [Shot 3] (11.5s-14.0s): On the two flat stone steps of <Picture 2>, as <Subject 1>'s shoulders relax in relief with closed lips, <Subject 3> flashes a cold, knowing smirk with closed lips and grips the upper part of his army-green canvas backpack strap.\n"
                "[Environment]\n- Sunlit two flat stone steps outside the weathered wooden doorway (<Picture 2>), zero text signboards.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Anxious female question, two loud chest slaps, boastful male pledge, canvas strap grip, zero music."
            ),
        },
        {
            "id": "2-1-14", "episode": 2, "duration": 13, "seed": 72114,
            "description": "叶寻淡声祝福发财后猛地从林双双手中抽回书包带，顶着林双双在身后的破防叫骂头也不回走向斜对门夏记食府。",
            "dialogue": "叶寻：行，祝你们发财。\n林双双：滚就滚！离了我家这门面，你那破方子烂手里都没人要！",
            "assetNames": ["重庆老街对门双火锅铺街景", "叶寻", "林双双", "楚南"],
            "ref_images": [kf("2-1-14"), kf("2-1_post_watch_master"), kf("2-1-14_street_aux"), f_ye, f_lin, f_chu],
            "ref_audios": [v_ye, v_lin],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young man on the lower stone step on screen-left in <Picture 1> and <Picture 2> gripping the upper army-green backpack strap, matching <Picture 4>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The young woman on the upper stone step in center-right in <Picture 1> and <Picture 2>, matching <Picture 5>. Voice matches Audio 2.\n"
                "- <Subject 3>: The young man standing by the right wooden doorframe behind <Subject 2> in <Picture 1> and <Picture 2>, matching <Picture 6>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.0s) Medium shot framed from <Picture 1> on the two flat stone steps outside the weathered wooden doorway.\n"
                "- [Shot 2] (4.0s-9.8s) Close-up on <Subject 2> with <Subject 3> behind her on the flat stone steps of <Picture 2>.\n"
                "- [Shot 3] (9.8s-13.0s) Wide sunlit street shot framed from <Picture 3> (empty clean sidewalks and quiet wooden storefronts, zero outdoor dining tables or signboards) following <Subject 1>'s resolute back across the narrow bluestone road toward the facing shopfront.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-2.2s): Looking flatly at <Subject 2>, <Subject 1> (S1) says: <d>[Chinese] 行，祝你们发财。</d>\n"
                "- [Shot 1] (2.2s-3.9s): <Subject 1> yanks his army-green canvas backpack strap decisively free from <Subject 2>'s right hand, making her stumble slightly empty-handed on the upper stone step as he turns away.\n"
                "- [Shot 2] (4.2s-9.5s): Clenching her empty right hand in rage on the stone step of <Picture 2>, <Subject 2> (S2) shouts spitefully toward screen-left: <d>[Chinese] 滚就滚，离了我家这门面，你那破方子烂手里都没人要。</d> She clamps her jaw shut right after the line.\n"
                "- [Shot 3] (9.9s-13.0s): Holding his right army-green backpack strap steadily without looking back once (<Picture 3>), <Subject 1> strides firmly across the clean sunlit bluestone road toward the quiet wooden shopfront across the street.\n"
                "[Environment]\n- Sunlit 2005 Chongqing bluestone pedestrian street between two quiet wooden shopfronts (<Picture 2>, <Picture 3>), zero outdoor tables, zero text signboards.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Cool male farewell, sharp whoosh of canvas strap yanked free, spiteful female shout, steady footsteps on stone road, zero music."
            ),
        },
        {
            "id": "2-2-01", "episode": 2, "duration": 12, "seed": 72201,
            "description": "斜对门夏记食府门庭冷落，夏芊芊踮脚撕下旧招工纸，混混凑上前硬往她手里塞高利贷传单，被拒后凶狠伸手抓她胳膊。",
            "dialogue": "混混：小老板娘，招工纸都撕啦？周转不开签两万块应急呗——\n夏芊芊：不借！你让开——",
            "assetNames": ["重庆老街对门双火锅铺街景", "夏芊芊", "混混"],
            "ref_images": [kf("2-2-01"), f_qian, f_thug],
            "ref_audios": [v_thug, v_qian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S2): The young woman standing beside the right wooden door pillar in <Picture 1>, matching <Picture 2>. Voice matches Audio 2.\n"
                "- <Subject 2> (S1): The street punk stepping onto the stone steps on screen-left in <Picture 1> holding colorful flyers, matching <Picture 3>. Voice matches Audio 1.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-2.4s) Medium-wide shot framed from <Picture 1> outside the quiet storefront.\n"
                "- [Shot 2] (2.4s-8.2s) Medium close-up two-shot from the east side with <Subject 2> on screen-left pressing in toward <Subject 1> backed against the right wooden pillar.\n"
                "- [Shot 3] (8.2s-12.0s) Tight close-up on <Subject 1> and <Subject 2>'s reaching hand.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-2.3s): <Subject 1> rips the old paper notice off the wooden pillar and lowers her feet flat onto the stone step just as <Subject 2> steps right up beside her with a sleazy grin.\n"
                "- [Shot 2] (2.6s-8.0s): Shoving a colorful loan flyer against <Subject 1>'s forearm and leaning in greedily, <Subject 2> (S1) coaxes: <d>[Chinese] 小老板娘，招工纸都撕啦，周转不开签两万块应急呗。</d>\n"
                "- [Shot 3] (8.3s-10.2s): Knocking the flyer away with her left hand, <Subject 1> (S2) cries out firmly: <d>[Chinese] 不借，你让开。</d> She presses her lips shut right after speaking.\n"
                "- [Shot 3] (10.2s-12.0s): Dropping his grin in anger, <Subject 2> lunges his right hand forward to grab <Subject 1>'s left forearm.\n"
                "[Environment]\n- Quiet sunlit stone steps outside a traditional Chongqing eatery.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Paper ripped from wood, footsteps on stone, sleazy male voice, flyer slapped away, urgent female refusal, zero music."
            ),
        },
        {
            "id": "2-2-04", "episode": 2, "duration": 13, "seed": 72204,
            "description": "叶寻大步跨上台阶一把扣住混混手腕拨开护在夏芊芊身前，朝街口治安岗亭一扬下巴冷声震慑，混混色厉内荏揉腕溜走。",
            "dialogue": "叶寻：街口岗亭民警正往这儿瞧，过去聊聊你这利息？\n混混：少管闲事！守着这冷灶台等关张吧！",
            "assetNames": ["重庆老街对门双火锅铺街景", "叶寻", "混混", "夏芊芊"],
            "ref_images": [kf("2-2-04"), f_ye, f_thug, f_qian],
            "ref_audios": [v_ye, v_thug],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young man striding onto the stone steps center-left in <Picture 1> with the canvas backpack, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The street punk on screen-left in <Picture 1>, matching <Picture 3>. Voice matches Audio 2.\n"
                "- <Subject 3>: The young woman standing behind <Subject 1> by the right wooden pillar in <Picture 1>, matching <Picture 4>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-2.5s) Medium close-up three-shot framed from <Picture 1> with a crisp impact jolt as <Subject 1> intercepts <Subject 2>'s wrist.\n"
                "- [Shot 2] (2.5s-8.0s) Over-the-shoulder close-up past <Subject 2>'s shoulder onto <Subject 1> shielding <Subject 3>.\n"
                "- [Shot 3] (8.0s-13.0s) Medium street shot as <Subject 2> backs down the steps toward screen-left and hurries away.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-2.4s): Stepping firmly between them, <Subject 1> clamps his left hand like an iron vise around <Subject 2>'s reaching right wrist and shoves it outward while <Subject 2> winces in pain.\n"
                "- [Shot 2] (2.7s-7.7s): Tilting his chin coldly toward the street corner on screen-left and fixing an icy stare on <Subject 2>, <Subject 1> (S1) says evenly: <d>[Chinese] 街口岗亭民警正往这儿瞧，过去聊聊你这利息。</d>\n"
                "- [Shot 3] (8.2s-12.0s): Yanking his sore wrist free and backing down two steps nervously, <Subject 2> (S2) barks: <d>[Chinese] 少管闲事，守着这冷灶台等关张吧。</d> Immediately upon finishing, he clamps his mouth shut and scurries off screen-left.\n"
                "[Environment]\n- Sunlit Chongqing bluestone street outside the eatery steps.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Heavy step on stone, solid wrist grab impact, calm intimidating male warning, blustering punk retreat and scurrying footsteps, zero music."
            ),
        },
        {
            "id": "2-2-07", "episode": 2, "duration": 13, "seed": 72277,
            "description": "夏芊芊认出叶寻眼眶一亮，慌忙把撕碎的招工纸藏到身后温柔问候，叶寻凝视她暗下守护夏家的誓言。",
            "dialogue": "夏芊芊：小寻？今天没课啊……怎么跑这儿来了？\n叶寻（心声）：上辈子林双双搞垮夏家逼你们远走……这回有我在。",
            "assetNames": ["重庆老街对门双火锅铺街景", "叶寻", "夏芊芊"],
            "ref_images": [kf("2-2-07"), f_ye, f_qian],
            "ref_audios": [v_qian],
            "vo_custom": {
                "voice": v_ye,
                "face_1k": f_ye,
                "text": "上辈子林双双搞垮夏家逼你们远走，这回有我在。",
                "duration": 6,
                "dst_start": 6.85,
                "max_len": 5.2,
                "base_duck": 0.22,
            },
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The young man on screen-left in <Picture 1> carrying the canvas backpack, matching <Picture 2>.\n"
                "- <Subject 2> (S1): The young woman beside the right wooden pillar in <Picture 1>, matching <Picture 3>. Voice matches Audio 1.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-6.5s) Medium close-up two-shot framed from <Picture 1> outside the sunlit doorway.\n"
                "- [Shot 2] (6.5s-13.0s) Instant hard cut to reverse over-the-shoulder close-up pushing in 0.35m onto <Subject 1>'s resolute eyes on screen-left.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-6.3s): As <Subject 2> quickly tucks her right hand holding the crumpled paper behind her back and curves a gentle, caring smile toward <Subject 1>, <Subject 2> (S1) speaks the entire sentence clearly: <d>[Chinese] 小寻，今天没课啊，怎么跑这儿来了。</d> Meanwhile <Subject 1> listens quietly with lips closed.\n"
                "- [Shot 2] (6.6s-13.0s): Looking steadily at <Subject 2> with deep protective resolve, <Subject 1> draws a calm breath while keeping his lips pressed completely shut and silent.\n"
                "[Environment]\n- Warm sunlit doorway of the traditional Chongqing eatery.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Subtle paper rustle and warm complete female greeting in [Shot 1], quiet steady breath and gentle breeze in [Shot 2], zero music."
            ),
        },
        {
            "id": "2-3-01", "episode": 2, "duration": 15, "seed": 72301,
            "description": "叶寻随夏芊芊走进擦得锃亮却空无一客的八桌前厅，看到柜台满页赤字账本关切询问，夏芊芊无奈叹气合上账本道出昨天才卖两百多块。",
            "dialogue": "叶寻：芊芊姐，这几天客流掉得这么厉害？\n夏芊芊：后街连开了几家快餐店，学生全往那边跑，昨天一天才卖两百多块！",
            "assetNames": ["夏氏小厨前厅与传菜口", "叶寻", "夏芊芊"],
            "ref_images": [kf("2-3-01"), f_qian, f_ye],
            "ref_audios": [v_ye, v_qian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S2): The young woman walking ahead in <Picture 1>, matching <Picture 2>. Voice matches Audio 2.\n"
                "- <Subject 2> (S1): The young man following with the canvas backpack in <Picture 1>, matching <Picture 3>. Voice matches Audio 1.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-2.7s) Wide tracking shot framed from <Picture 1> panning rightward across the spotless empty dining tables to the wooden counter.\n"
                "- [Shot 2] (2.7s-6.8s) Medium close-up over the open red-inked ledger on the wooden counter with <Subject 2> on screen-left and <Subject 1> behind the counter on screen-right.\n"
                "- [Shot 3] (6.8s-13.2s) Over-the-shoulder close-up past <Subject 2>'s shoulder onto <Subject 1> behind the wooden counter.\n"
                "- [Shot 4] (13.2s-15.0s) High-angle close-up of the open red-inked ledger on the wooden counter.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-2.6s): <Subject 1> leads <Subject 2> past the empty wooden tables to the counter on screen-right.\n"
                "- [Shot 2] (2.8s-6.6s): Glancing down at the pages of red deficit figures in the ledger and looking up at <Subject 1>, <Subject 2> (S1) asks earnestly: <d>[Chinese] 芊芊姐，这几天客流掉得这么厉害。</d>\n"
                "- [Shot 3] (7.0s-13.0s): Looking down ruefully at the ledger and back up at <Subject 2> with a bitter smile, <Subject 1> (S2) explains: <d>[Chinese] 后街连开了几家快餐店，学生全往那边跑，昨天一天才卖两百多块。</d> She presses her lips together with a quiet sigh as she finishes.\n"
                "- [Shot 4] (13.3s-15.0s): <Subject 1>'s right hand closes the ledger cover over the red figures and rests flat atop it.\n"
                "[Environment]\n- Clean sunlit traditional small restaurant dining hall with empty wooden tables and closed blue kitchen curtain in rear.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Footsteps in quiet empty hall, concerned male inquiry, worried female explanation, soft sigh and paper ledger closing, zero music."
            ),
        },
        {
            "id": "2-3-05", "episode": 2, "duration": 14, "seed": 72355,
            "description": "叶寻拉开帆布书包取出祖传试锅草本香料包稳稳按在柜台上，提议改做养生火锅合伙经营，夏芊芊震惊推辞。",
            "dialogue": "叶寻：店别关。炒菜改做养生火锅，我出方子盯灶，咱们合伙。\n夏芊芊：这哪行啊？你爷爷留的方子，不是说好拿去帮双双吗？",
            "assetNames": ["夏氏小厨前厅与传菜口", "叶寻", "夏芊芊"],
            "ref_images": [kf("2-3-05"), kf("2-3-08"), f_ye, f_qian, sc_xia_hall],
            "ref_audios": [v_ye, v_qian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young man standing on screen-left outside the dark wooden counter in <Picture 1>, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The young woman standing behind the dark wooden counter inside <Picture 5>, matching <Picture 4>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-2.8s) Medium close-up framed from <Picture 1> as <Subject 1> unzips the canvas backpack once and lifts out a single twine-tied coarse cloth herb bundle.\n"
                "- [Shot 2] (2.8s-8.4s) Close-up framed from <Picture 2> as <Subject 1> presses his right palm firmly atop that single coarse cloth herb bundle on the dark wooden counter.\n"
                "- [Shot 3] (8.4s-14.0s) Over-the-shoulder close-up past <Subject 1>'s left shoulder onto <Subject 2> standing behind the dark wooden counter inside the traditional white-walled dining hall of <Picture 5> (wooden tables and dark-blue cloth curtain behind her, zero glass display cases or modern appliances).\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-2.7s): Holding the canvas backpack on his left forearm, <Subject 1> unzips it and lifts out one bulging twine-tied coarse cloth herb bundle.\n"
                "- [Shot 2] (2.9s-8.2s): Resting his right palm steadily atop the coarse cloth herb bundle on the wooden counter and looking straight at <Subject 2>, <Subject 1> (S1) proposes resolutely: <d>[Chinese] 店别关，炒菜改做养生火锅，我出方子盯灶，咱们合伙。</d>\n"
                "- [Shot 3] (8.6s-13.6s): Staring in shock at the herb bundle on the wooden counter and raising her left hand to decline urgently, <Subject 2> (S2) exclaims: <d>[Chinese] 这哪行啊，你爷爷留的方子，不是说好拿去帮双双吗。</d>\n"
                "[Environment]\n- Traditional 2005 small restaurant front hall (<Picture 5>) with dark wooden counter, wooden tables, and white plaster walls.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Zipper pull, solid thump of herb bundle on wood, steady confident male proposal, surprised earnest female protest, zero music."
            ),
        },
        {
            "id": "2-3-08", "episode": 2, "duration": 13, "seed": 72308,
            "description": "叶寻坦言刚与林双双分手、秘方只信夏家，夏芊芊刚要开口，后厨蓝布门帘猛地掀开，夏建国一手捂红肿脖子一手拎铁炒勺沙哑怒斥冲出。",
            "dialogue": "叶寻：刚跟她分了。这东西，我只信得过夏家。\n夏建国：瞎胡闹！夏家做了一辈子川菜……改什么野路子！",
            "assetNames": ["夏氏小厨前厅与传菜口", "叶寻", "夏芊芊", "夏建国"],
            "ref_images": [kf("2-3-08"), kf("2-3-10_aux"), f_ye, f_qian, f_jian],
            "ref_audios": [v_ye, v_jian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young man at the counter on screen-left in <Picture 1>, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 2>: The young woman at the counter on screen-right, matching <Picture 4>.\n"
                "- <Subject 3> (S2): The master chef standing in front of the dark-blue kitchen curtain in <Picture 2>, matching <Picture 5>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.2s) Over-the-shoulder close-up framed from <Picture 1> onto <Subject 1> pressing his hand on the herb bundle.\n"
                "- [Shot 2] (4.2s-7.0s) Medium shot looking past the counter toward the dark-blue cloth kitchen doorway at left-rear.\n"
                "- [Shot 3] (7.0s-13.0s) Medium close-up framed from <Picture 2> on <Subject 3> standing before the swaying dark-blue curtain.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-4.0s): Tapping the coarse cloth herb bundle once with sincere conviction, <Subject 1> (S1) says firmly: <d>[Chinese] 刚跟她分了，这东西，我只信得过夏家。</d>\n"
                "- [Shot 2] (4.3s-6.9s): Just as <Subject 2> parts her lips in surprise, the dark-blue kitchen curtain at left-rear is flung sharply open and <Subject 3> strides out clutching his swollen neck with his left hand and holding a long iron wok ladle in his right hand, making <Subject 1> and <Subject 2> turn sharply toward screen-left.\n"
                "- [Shot 3] (7.2s-12.5s): Clutching his sore throat with his left hand and pointing the iron ladle slightly forward, <Subject 3> (S2) barks in a strained, raspy voice: <d>[Chinese] 瞎胡闹，夏家做了一辈子川菜，改什么野路子。</d>\n"
                "[Environment]\n- Sunlit traditional eatery front hall between wooden counter and blue kitchen curtain.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Sincere male voice, cloth curtain whipped open, heavy footsteps, raspy strained older male rebuke, zero music."
            ),
        },
        {
            "id": "2-3-11", "episode": 2, "duration": 14, "seed": 72311,
            "description": "夏芊芊心疼劝扁桃体红肿的父亲少说话，夏建国却沙哑立下死规矩绝不准上火烂嘴的红油锅进家门，叶寻手按草本包沉静迎视切集。",
            "dialogue": "夏芊芊：爸，你扁桃体肿得水都咽不下，快少说两句——\n夏建国：小寻，心意叔领了……但那号上火烂嘴的红油锅，绝不能进咱家门！",
            "assetNames": ["夏氏小厨前厅与传菜口", "夏芊芊", "叶寻", "夏建国"],
            "ref_images": [kf("2-3-11"), kf("2-3-13_aux"), f_qian, f_ye, f_jian],
            "ref_audios": [v_qian, v_jian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young woman stepping half a pace forward past the wooden counter on screen-right in <Picture 1> and <Picture 2>, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 2>: The young man standing beside the dark wooden counter on screen-right in <Picture 1> and <Picture 2> keeping his right hand on the herb bundle and his army-green canvas backpack on his left arm, matching <Picture 4>.\n"
                "- <Subject 3> (S2): The master chef standing on screen-left before the dark-blue kitchen curtain in <Picture 2>, matching <Picture 5>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-5.0s) Medium close-up two-shot framed from <Picture 1> with the dark wooden counter and herb bundle strictly on screen-right, facing screen-left.\n"
                "- [Shot 2] (5.0s-11.8s) Close-up on <Subject 3> on screen-left in front of the dark-blue cloth curtain (<Picture 2>) clutching his swollen throat with his left hand and facing screen-right.\n"
                "- [Shot 3] (11.8s-14.0s) Three-layer depth medium shot framed directly from <Picture 2> with the dark wooden counter, coarse burlap herb bundle, and <Subject 2>'s hand in the right foreground and <Subject 3> in the left background.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-4.8s): Stepping half a pace forward beside the right-side wooden counter with worried eyes toward screen-left, <Subject 1> (S1) pleads anxiously: <d>[Chinese] 爸，你扁桃体肿得水都咽不下，快少说两句。</d>\n"
                "- [Shot 2] (5.2s-11.5s): Waving the iron ladle slightly to stop his daughter and looking straight toward screen-right at <Subject 2>, <Subject 3> (S2) speaks in a hoarse, unyielding voice: <d>[Chinese] 小寻，心意叔领了，但那号上火烂嘴的红油锅，绝不能进咱家门。</d> Immediately upon finishing, he clamps his lips shut firmly without another sound.\n"
                "- [Shot 3] (11.9s-14.0s): In crisp three-layer depth matching <Picture 2>, <Subject 2>'s fingers tighten steadily around the coarse cloth herb bundle on the right-side wooden counter while both men keep their lips completely closed in silent deadlock.\n"
                "[Environment]\n- Sunlit traditional eatery front hall (<Picture 2>) with dark wooden counter strictly on screen-right and dark-blue kitchen curtain at left-rear.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Worried female plea, hoarse unyielding older male decree, quiet room tone in [Shot 3] with zero trailing speech, zero music."
            ),
        },
    ]

    # ==================== EPISODE 3 (16 GROUPS) ====================
    ep3 = [
        {
            "id": "3-1-01", "episode": 3, "duration": 13, "seed": 73101,
            "description": "夏建国捂着脖子剧烈干咳被夏芊芊扶坐递温水，叶寻点破急火攻心嗓痛如吞刀片，夏建国沙哑抗拒再闻燥辣红油味。",
            "dialogue": "叶寻：夏叔，急火攻心，嗓子眼疼得像吞刀片吧？\n夏建国：可不是！再闻见那股燥辣红油味儿，我这嗓子彻底交代了！",
            "assetNames": ["夏氏小厨前厅与传菜口", "夏建国", "夏芊芊", "叶寻"],
            "ref_images": [kf("3-1-01"), f_jian, f_qian, f_ye],
            "ref_audios": [v_ye, v_jian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S2): The master chef clutching his sore throat in <Picture 1>, matching <Picture 2>. Voice matches Audio 2.\n"
                "- <Subject 2>: The young woman supporting <Subject 1>'s arm in <Picture 1>, matching <Picture 3>.\n"
                "- <Subject 3> (S1): The young man standing by the wooden counter on screen-left in <Picture 1>, matching <Picture 4>. Voice matches Audio 1.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-2.8s) Medium shot framed from <Picture 1> panning slightly as <Subject 2> helps <Subject 1> sit down on the bench at the wooden table.\n"
                "- [Shot 2] (2.8s-7.0s) Medium close-up across the wooden table as <Subject 2> hands <Subject 1> a white porcelain cup of warm water and <Subject 3> speaks from screen-left.\n"
                "- [Shot 3] (7.0s-13.0s) Over-the-shoulder close-up past <Subject 3>'s left shoulder onto <Subject 1> holding the cup.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-2.7s): Coughing raspingly while clutching his neck, <Subject 1> is guided gently by <Subject 2> onto the wooden bench beside the table.\n"
                "- [Shot 2] (3.0s-6.8s): As <Subject 1> takes the white cup of warm water into his left hand, <Subject 3> (S1) leans slightly forward from screen-left and asks calmly: <d>[Chinese] 夏叔，急火攻心，嗓子眼疼得像吞刀片吧。</d>\n"
                "- [Shot 3] (7.2s-12.5s): Wincing as he holds the warm cup at his chest and tapping the iron ladle handle on the table edge, <Subject 1> (S2) replies in a raspy pained voice: <d>[Chinese] 可不是，再闻见那股燥辣红油味儿，我这嗓子彻底交代了。</d>\n"
                "[Environment]\n- Sunlit traditional eatery front hall.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Dry raspy cough, bench scrape, warm concerned male question, raspy pained older male reply, zero music."
            ),
        },
        {
            "id": "3-1-04", "episode": 3, "duration": 14, "seed": 73104,
            "description": "叶寻立军令状借后厨小灶四十分钟试熬，若烧嗓子拎包就走，夏芊芊柔声帮腔，夏建国搁下铁炒勺默许叶寻捧草本包进后厨。",
            "dialogue": "叶寻：后厨小灶借我四十分钟。熬出来您尝一口，要是烧嗓子，我拎包就走。\n夏芊芊：爸，小寻从小不说空话，就让他开火试试嘛。",
            "assetNames": ["夏氏小厨前厅与传菜口", "叶寻", "夏建国", "夏芊芊"],
            "ref_images": [kf("3-1-04"), f_ye, f_jian, f_qian],
            "ref_audios": [v_ye, v_qian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young man standing by the dark wooden counter on screen-left in <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2>: The master chef seated at the wooden table on screen-right, matching <Picture 3>.\n"
                "- <Subject 3> (S2): The young woman standing beside <Subject 2>, matching <Picture 4>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-6.5s) Over-the-shoulder close-up framed from <Picture 1> onto <Subject 1> patting the coarse cloth herb bundle.\n"
                "- [Shot 2] (6.5s-11.2s) Medium close-up on screen-right as <Subject 3> bends gently beside seated <Subject 2>.\n"
                "- [Shot 3] (11.2s-14.0s) Medium wide shot of the front hall showing <Subject 1> on screen-left and <Subject 2> with <Subject 3> on screen-right.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-6.3s): Patting the coarse cloth herb bundle firmly with his right palm and looking squarely at <Subject 2>, <Subject 1> (S1) pledges clearly: <d>[Chinese] 后厨小灶借我四十分钟，熬出来您尝一口，要是烧嗓子，我拎包就走。</d>\n"
                "- [Shot 2] (6.7s-11.0s): Holding <Subject 2>'s right arm gently with an encouraging smile, <Subject 3> (S2) coaxes softly: <d>[Chinese] 爸，小寻从小不说空话，就让他开火试试嘛。</d>\n"
                "- [Shot 3] (11.3s-14.0s): Shooting his daughter a reluctant look, <Subject 2> lays his iron wok ladle flat onto the table corner in tacit consent; <Subject 1> lifts the herb bundle in both hands and strides toward the rear kitchen curtain.\n"
                "[Environment]\n- Sunlit traditional eatery front hall.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Confident male pledge, warm coaxing female voice, metallic clink of iron ladle set flat on wood, brisk footsteps, zero music."
            ),
        },
        {
            "id": "3-1-08", "episode": 3, "duration": 9, "seed": 73108,
            "description": "后厨小灶火苗升腾，叶寻将十七味温补草本入温油慢焖滤渣再融化醇厚牛油，紫铜锅红汤清亮翻滚无浓烟，药膳脂香顺木窗飘出巷口。",
            "dialogue": "",
            "assetNames": ["夏氏小厨后厨猛火炒灶", "叶寻", "紫铜子母鸳鸯锅"],
            "ref_images": [kf("3-1-08"), f_ye, p_pot, sc_xia_kitch],
            "ref_audios": [],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The young man working beside the brick stove in <Picture 1>, matching <Picture 2>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-3.4s) Medium close-up framed from <Picture 1> at the brick stove in <Picture 4>.\n"
                "- [Shot 2] (3.4s-6.4s) Overhead close-up into the iron wok as herbs are strained clean and rich white beef tallow melts into amber-red oil.\n"
                "- [Shot 3] (6.4s-9.0s) Medium shot panning smoothly 20 degrees leftward from the simmering copper pot (<Picture 3>) on the stove to the open wooden window looking out onto the stone alley.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-3.3s): Untying the coarse cloth bundle, <Subject 1> tips dried aromatic herbs into the warm oil in the wok and stirs steadily with a long wooden ladle.\n"
                "- [Shot 2] (3.5s-6.3s): <Subject 1>'s left hand lifts all infused herbs cleanly out with a fine mesh strainer while his right ladle slides a block of solid white beef tallow into the golden-red oil, melting smoothly.\n"
                "- [Shot 3] (6.5s-9.0s): Clear ruby-red broth bubbles briskly without acrid smoke inside the copper pot as fragrant white steam wafts out through the open left wooden window into the sunlit alley.\n"
                "[Environment]\n- Sunlit traditional brick-stove restaurant kitchen with open wooden alley window.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Roaring stove flame, gentle sizzle of herbs in warm oil, mesh strainer clink, rich bubbling broth, light breeze at window, zero speech, zero music."
            ),
        },
        {
            "id": "3-1-11", "episode": 3, "duration": 11, "seed": 73111,
            "description": "摇蒲扇路过的陈伯被药膳奇香勾住脚步扒着木窗台往里打听，叶寻在灶前撇净浮油盛出半碗清亮红汤并涮熟两片鲜毛肚。",
            "dialogue": "陈伯：老夏，背着人炖啥好汤呢？隔半条街都闻见香了！",
            "assetNames": ["夏氏小厨后厨猛火炒灶", "陈伯", "叶寻", "紫铜子母鸳鸯锅"],
            "ref_images": [kf("3-1-11"), kf("3-1-13_aux"), f_chen, f_ye, p_pot],
            "ref_audios": [v_chen],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The neighborhood uncle holding a palm-leaf fan outside the wooden window in <Picture 1>, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 2>: The young man working at the stove in <Picture 2>, matching <Picture 4>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-2.4s) Exterior alley medium shot framed from <Picture 1> beside the open wooden kitchen window.\n"
                "- [Shot 2] (2.4s-7.2s) Interior kitchen close-up looking past blurred steam toward <Subject 1> leaning eagerly in through the left wooden window.\n"
                "- [Shot 3] (7.2s-11.0s) High-angle stove close-up framed from <Picture 2> showing the simmering copper pot (<Picture 5>) and a white porcelain bowl.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-2.3s): Stopping abruptly outside the open window, <Subject 1> inhales the rich aroma deeply twice and grips the wooden windowsill to peer inside.\n"
                "- [Shot 2] (2.6s-7.0s): Beaming with eager curiosity through the window frame, <Subject 1> (S1) calls out cheerfully: <d>[Chinese] 老夏，背着人炖啥好汤呢，隔半条街都闻见香了。</d>\n"
                "- [Shot 3] (7.3s-11.0s): Skimming the clear ruby broth into the white porcelain bowl, <Subject 2> dips two fresh tripe slices into the bubbling copper pot with long bamboo chopsticks until crisp and places them into the bowl.\n"
                "[Environment]\n- Sunlit Chongqing stone alley window and warm traditional kitchen stove.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Deep sniff of aroma, cheerful hearty male neighbor call, ladle pouring broth and tripe swished in boiling soup, zero music."
            ),
        },
        {
            "id": "3-1-14", "episode": 3, "duration": 12, "seed": 73114,
            "description": "叶寻把红汤端到夏建国面前请他趁热抿原汤，夏建国半信半疑抿一口后双眸微亮，仰头喝下大半碗嚼完毛肚，墙上挂钟走过十分钟。",
            "dialogue": "叶寻：夏叔，趁热抿两口原汤。",
            "assetNames": ["夏氏小厨前厅与传菜口", "叶寻", "夏建国", "夏芊芊", "紫铜子母鸳鸯锅"],
            "ref_images": [kf("3-1-14"), f_ye, f_jian, f_qian, p_pot],
            "ref_audios": [v_ye],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young man on screen-left setting the white bowl down in <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2>: The master chef seated on screen-right of the wooden table in <Picture 1>, matching <Picture 3>.\n"
                "- <Subject 3>: The young woman standing beside <Subject 2> in <Picture 1>, matching <Picture 4>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-3.6s) Medium shot framed from <Picture 1> around the wooden table with the simmering copper pot (<Picture 5>).\n"
                "- [Shot 2] (3.6s-6.6s) Close-up on <Subject 2> taking a cautious first sip from the white bowl.\n"
                "- [Shot 3] (6.6s-10.0s) Side close-up on <Subject 2> drinking half the bowl and chewing the crisp tripe with bamboo chopsticks.\n"
                "- [Shot 4] (10.0s-12.0s) Close-up of the round black-framed quartz wall clock on the white interior wall.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-3.4s): Setting the white bowl of clear red broth steadily in front of <Subject 2>, <Subject 1> (S1) invites him warmly: <d>[Chinese] 夏叔，趁热抿两口原汤。</d>\n"
                "- [Shot 2] (3.7s-6.5s): Lifting the bowl skeptically to his lips, <Subject 2> takes a small sip and swallows; his furrowed brows instantly relax and his eyes light up in astonishment.\n"
                "- [Shot 3] (6.7s-9.9s): <Subject 2> tilts the bowl to gulp down half the broth smoothly without pain, then uses chopsticks to eat both slices of crisp tripe with relish.\n"
                "- [Shot 4] (10.1s-12.0s): On the wall clock, the minute hand sweeps briskly forward ten minutes and settles into a steady tick.\n"
                "[Environment]\n- Sunlit traditional eatery front hall.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Porcelain bowl set on wood, calm male invitation, sip and hearty gulp of soup, crisp chew, brisk ticking wall clock, zero music."
            ),
        },
        {
            "id": "3-1-18", "episode": 3, "duration": 12, "seed": 73118,
            "description": "夏建国额角沁出细汗，咽了口唾沫猛摸脖子惊喜发现火辣肿痛全散、嗓音恢复洪亮清透，夏芊芊惊喜合掌欢呼。",
            "dialogue": "夏建国：奇了……嗓子眼里那股火辣辣顶着的劲儿，真散了？！\n夏芊芊：爸！你听你说话，嗓子不劈也不哑了！",
            "assetNames": ["夏氏小厨前厅与传菜口", "夏建国", "夏芊芊"],
            "ref_images": [kf("3-1-18"), f_jian, f_qian],
            "ref_audios": [v_jian, v_qian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The master chef seated at the table in <Picture 1> with fine sweat on his forehead, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The young woman standing beside him, matching <Picture 3>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-2.4s) Push-in close-up starting from <Picture 1> onto <Subject 1>'s throat and astonished eyes.\n"
                "- [Shot 2] (2.4s-8.0s) Close-up on <Subject 1> feeling his neck with his right hand and looking toward screen-left.\n"
                "- [Shot 3] (8.0s-12.0s) Close-up on <Subject 2> clasping her hands together joyfully.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-2.3s): Swallowing smoothly without a trace of pain, <Subject 1> widens his eyes in disbelief and reaches his right hand swiftly to his neck.\n"
                "- [Shot 2] (2.6s-7.8s): Pressing his throat twice and snapping his amazed gaze toward screen-left, <Subject 1> (S1) exclaims in a clear, resonant voice: <d>[Chinese] 奇了，嗓子眼里那股火辣辣顶着的劲儿，真散了。</d>\n"
                "- [Shot 3] (8.2s-11.6s): Clasping both hands happily in front of her chest and beaming down at her father, <Subject 2> (S2) cheers brightly: <d>[Chinese] 爸，你听你说话，嗓子不劈也不哑了。</d>\n"
                "[Environment]\n- Warm sunlit eatery front hall.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Smooth swallow, booming clear older male exclamation, joyful female cheer and light hand clap, zero music."
            ),
        },
        {
            "id": "3-1-21", "episode": 3, "duration": 12, "seed": 73121,
            "description": "窗外的陈伯馋得直咽口水，摸出二十块钱拍在木窗框上催老夏盛一碗，叶寻爽朗笑着让陈伯收钱许诺新锅挂牌头一顿请他白吃。",
            "dialogue": "陈伯：老夏你可别吃独食！闻着一点不呛嗓子，赶紧给我盛一碗！\n叶寻：陈伯钱收回去，等过几天新锅挂牌，头一顿请您白吃。",
            "assetNames": ["夏氏小厨前厅与传菜口", "陈伯", "叶寻", "紫铜子母鸳鸯锅"],
            "ref_images": [kf("3-1-21"), f_chen, f_ye, p_pot],
            "ref_audios": [v_chen, v_ye],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The neighborhood uncle leaning in at the open left wooden window in <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The young man standing inside the hall beside the wooden table and copper pot (<Picture 4>), matching <Picture 3>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-2.2s) Close-up framed from <Picture 1> at the open wooden window.\n"
                "- [Shot 2] (2.2s-7.3s) Close-up on <Subject 1> pressing a twenty-yuan banknote onto the windowsill.\n"
                "- [Shot 3] (7.3s-12.0s) Over-the-shoulder medium close-up past the wooden window frame onto <Subject 2> smiling warmly inside the hall.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-2.1s): Swallowing eagerly at the sight of the hotpot, <Subject 1> slaps a twenty-yuan bill firmly down onto the wooden windowsill.\n"
                "- [Shot 2] (2.4s-7.1s): Pushing the bill forward on the wood and craning his neck eagerly toward the table, <Subject 1> (S1) calls out loudly: <d>[Chinese] 老夏你可别吃独食，闻着一点不呛嗓子，赶紧给我盛一碗。</d>\n"
                "- [Shot 3] (7.5s-11.6s): Turning toward the left window with a bright, generous smile and gesturing for <Subject 1> to take back his money, <Subject 2> (S2) replies warmly: <d>[Chinese] 陈伯钱收回去，等过几天新锅挂牌，头一顿请您白吃。</d>\n"
                "[Environment]\n- Sunlit open wooden window connecting stone alley and traditional dining hall.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Crisp slap of banknote on wood, eager hearty neighbor shout, warm confident young male reply, gentle simmering pot, zero music."
            ),
        },
        {
            "id": "3-1-24", "episode": 3, "duration": 15, "seed": 73124,
            "description": "夏建国绕红汤锅看了两圈重重一拍大腿，拉过柜台纸笔推给叶寻，当场拍板改火锅让叶寻拿方子占五成一股权，叶寻执笔落字据。",
            "dialogue": "夏建国：小寻，叔今儿服气了！改火锅！你拿方子占五成一，往后叔听你的！\n叶寻：行，夏叔，咱先把字据落下来。",
            "assetNames": ["夏氏小厨前厅与传菜口", "夏建国", "叶寻", "夏芊芊", "紫铜子母鸳鸯锅"],
            "ref_images": [kf("3-1-24"), f_jian, f_ye, f_qian, p_pot],
            "ref_audios": [v_jian, v_ye],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The master chef standing excitedly on screen-right of the wooden table in <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The young man standing on screen-left of the table in <Picture 1>, matching <Picture 3>. Voice matches Audio 2.\n"
                "- <Subject 3>: The young woman smiling behind the table in <Picture 1>, matching <Picture 4>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-3.3s) Medium shot framed from <Picture 1> around the steaming copper pot (<Picture 5>).\n"
                "- [Shot 2] (3.3s-5.7s) Medium close-up panning briefly as <Subject 1> pulls blank white sheets and a black pen from the adjacent counter onto the table before <Subject 2>.\n"
                "- [Shot 3] (5.7s-11.7s) Over-the-shoulder close-up past <Subject 2>'s left shoulder onto <Subject 1> and beaming <Subject 3>.\n"
                "- [Shot 4] (11.7s-15.0s) Reverse over-the-shoulder close-up onto <Subject 2> uncapping the black pen over the paper.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-3.2s): Looking into the clear red broth in admiration, <Subject 1> nods vigorously and slaps his own right thigh hard with a resounding smack.\n"
                "- [Shot 2] (3.4s-5.6s): <Subject 1> reaches over to pull a stack of white paper and a black pen off the counter and slides them briskly across the wooden table to <Subject 2>.\n"
                "- [Shot 3] (5.9s-11.5s): Bracing both hands on the table with blazing conviction, <Subject 1> (S1) declares heartily: <d>[Chinese] 小寻，叔今儿服气了，改火锅，你拿方子占五成一，往后叔听你的。</d>\n"
                "- [Shot 4] (11.9s-14.7s): Steadying the white paper with his left hand and uncapping the black pen, <Subject 2> (S2) looks up with a steady smile and says: <d>[Chinese] 行，夏叔，咱先把字据落下来。</d>\n"
                "[Environment]\n- Sunlit traditional eatery front hall.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Loud palm slap on thigh, paper sliding on wood, booming decisive male declaration, pen cap click and steady male agreement, zero music."
            ),
        },
        {
            "id": "3-2-01", "episode": 3, "duration": 9, "seed": 73201,
            "description": "次日上午叶寻三人拿着字据和账本刚走到夏记门口，斜对门突然炸响鞭炮红纸屑崩满地，赵帆迈出林记大门一脚踩断林记旧木匾。",
            "dialogue": "",
            "assetNames": ["重庆老街对门双火锅铺街景", "叶寻", "夏芊芊", "夏建国", "赵帆"],
            "ref_images": [kf("3-2-01"), kf("3-2-03_aux"), f_ye, f_qian, f_jian, f_zhao],
            "ref_audios": [],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The young man holding a folded white agreement paper in <Picture 1>, matching <Picture 3>.\n"
                "- <Subject 2>: The young woman holding a ledger in <Picture 1>, matching <Picture 4>.\n"
                "- <Subject 3>: The master chef stepping out beside them in <Picture 1>, matching <Picture 5>.\n"
                "- <Subject 4>: The Western-style chef stepping out across the street in <Picture 2>, matching <Picture 6>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-3.4s) Medium shot framed from <Picture 1> at the sunlit stone steps of the west storefront (with a long-handled shovel leaning inside the doorpost).\n"
                "- [Shot 2] (3.4s-5.4s) High-angle close-up of the stone ground across the street bursting with red firecracker confetti and white smoke around an old wooden sign plaque.\n"
                "- [Shot 3] (5.4s-9.0s) Low-angle medium shot framed from <Picture 2> tilting down 18 degrees to <Subject 4>'s polished shoe stomping the wooden plaque.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-3.3s): Stepping cheerfully onto the stone steps, <Subject 1>, <Subject 2>, and <Subject 3> halt abruptly at a sudden burst of loud firecrackers and turn their heads sharply toward screen-right.\n"
                "- [Shot 2] (3.5s-5.3s): Final strings of red firecrackers pop sharply on the pavement, scattering crimson confetti across the detached old black wooden plaque.\n"
                "- [Shot 3] (5.5s-9.0s): Striding out arrogantly with hands behind his back, <Subject 4> raises his right foot high and stomps hard onto the center of the old wooden plaque, cracking the wood in two.\n"
                "[Environment]\n- Bright morning sunlight on the Chongqing bluestone street between the two facing storefronts.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Crackling firecracker bursts, footsteps halting, heavy shoe stomp snapping wooden plaque cleanly, zero speech, zero music."
            ),
        },
        {
            "id": "3-2-04", "episode": 3, "duration": 15, "seed": 73204,
            "description": "林双双挽着楚南当街把红皮聘书递给赵帆，炫耀批下十五万装修款和八千月薪，赵帆拍胸吹嘘正宗法式西餐一开火整条街土馆子全喝西北风。",
            "dialogue": "林双双：赵主厨，十五万装修款我全批了，往后一个月八千块工资，店里可就指望您啦！\n赵帆：林小姐把心放肚子里，等我这正宗法式西餐一开火，整条街的土馆子全得喝西北风！",
            "assetNames": ["重庆老街对门双火锅铺街景", "林双双", "楚南", "赵帆"],
            "ref_images": [kf("3-2-04"), f_lin, f_chu, f_zhao],
            "ref_audios": [v_lin, v_zhao],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young woman on screen-right in <Picture 1> linking arms with <Subject 2> and handing over a red hardcover appointment booklet, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2>: The young man beside <Subject 1> in <Picture 1> holding a red-and-white handheld megaphone at his side, matching <Picture 3>.\n"
                "- <Subject 3> (S2): The chef on screen-left in <Picture 1> receiving the red appointment booklet, matching <Picture 4>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-7.3s) Medium close-up three-shot framed from <Picture 1> amidst red firecracker confetti outside the east storefront.\n"
                "- [Shot 2] (7.3s-15.0s) Close-up favoring <Subject 3> holding the red appointment booklet in his left hand as <Subject 1> and <Subject 2> nod smugly beside him.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-7.0s): Handing the gold-stamped red hardcover booklet proudly to <Subject 3> while clinging to <Subject 2>'s arm, <Subject 1> (S1) flatters him brightly: <d>[Chinese] 赵主厨，十五万装修款我全批了，往后一个月八千块工资，店里可就指望您啦。</d>\n"
                "- [Shot 2] (7.5s-14.5s): Accepting the red booklet, patting his chest theatricality with his right hand, and sweeping his arm grandly down the street, <Subject 3> (S2) brags loudly: <d>[Chinese] 林小姐把心放肚子里，等我这正宗法式西餐一开火，整条街的土馆子全得喝西北风。</d>\n"
                "[Environment]\n- Sunlit Chongqing old street storefront with firecracker confetti on the ground.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Flattering proud female voice, booklet handoff, theatrical chest pat and boastful male brag, street air, zero music."
            ),
        },
        {
            "id": "3-2-08", "episode": 3, "duration": 14, "seed": 73208,
            "description": "叶寻站在台阶上一眼认出前世光会摆盘吃回扣的混子赵帆，对门楚南举起扩音小喇叭冲夏记嚣张喊话叫他们趁早关张。",
            "dialogue": "叶寻（心声）：赵帆……还真是这个光会摆盘吃回扣的混子。\n楚南：喂——半个月后我们“塞纳河畔”西餐厅开业，对门冷锅冷灶的趁早关张吧！",
            "assetNames": ["重庆老街对门双火锅铺街景", "叶寻", "楚南", "林双双", "赵帆", "夏芊芊", "夏建国"],
            "ref_images": [kf("3-2-08"), kf("3-2-09_aux"), f_ye, f_chu, f_lin, f_zhao, f_qian, f_jian],
            "ref_audios": [v_chu],
            "vo_custom": {
                "voice": v_ye,
                "face_1k": f_ye,
                "text": "赵帆，还真是这个光会摆盘吃回扣的混子。",
                "duration": 5,
                "dst_start": 0.35,
                "max_len": 4.0,
                "base_duck": 0.22,
            },
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The young man standing calmly on the stone steps in <Picture 1>, matching <Picture 3>.\n"
                "- <Subject 2> (S1): The young man raising a red-and-white megaphone in <Picture 2>, matching <Picture 4>. Voice matches Audio 1.\n"
                "- <Subject 3>: The young woman holding <Subject 2>'s arm in <Picture 2>, matching <Picture 5>.\n"
                "- <Subject 4>: The chef watching smugly in <Picture 2>, matching <Picture 6>.\n"
                "- <Subject 5>: The young woman holding a ledger on the steps, matching <Picture 7>.\n"
                "- <Subject 6>: The master chef standing beside <Subject 5>, matching <Picture 8>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.6s) Close-up framed from <Picture 1> on <Subject 1> looking toward screen-right.\n"
                "- [Shot 2] (4.6s-11.8s) Medium close-up framed from <Picture 2> on <Subject 2> shouting through the handheld megaphone toward screen-left.\n"
                "- [Shot 3] (11.8s-14.0s) Medium three-shot on the west stone steps showing <Subject 1>, <Subject 5>, and <Subject 6> facing screen-right.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-4.5s): Watching across the street with his lips pressed completely closed and silent, <Subject 1> narrows his eyes in cold recognition.\n"
                "- [Shot 2] (4.8s-11.6s): Lifting the red-and-white megaphone to his mouth and grinning arrogantly toward screen-left, <Subject 2> (S1) shouts loudly: <d>[Chinese] 喂，半个月后我们塞纳河畔西餐厅开业，对门冷锅冷灶的趁早关张吧。</d> He lowers the megaphone slightly with closed mouth as the sentence ends.\n"
                "- [Shot 3] (11.9s-14.0s): On the stone steps, <Subject 6> clenches his fists in anger and <Subject 5> frowns tightly around her ledger, while <Subject 1> stands unmoved with closed lips.\n"
                "[Environment]\n- Sunlit Chongqing bluestone street between the two facing shops.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Quiet street air in [Shot 1], brief megaphone click and loud projected male taunt in [Shot 2], tense reaction in [Shot 3], zero music."
            ),
        },
        {
            "id": "3-2-11", "episode": 3, "duration": 13, "seed": 73211,
            "description": "林双双冲叶寻扬下巴炫耀离了他照样开高档西餐厅，夏建国暴怒斥骂，叶寻收起字据抬臂拦住夏建国看都不看对门一眼直接低头翻账本。",
            "dialogue": "林双双：叶寻，瞧见没？离了你，我家照样开高档西餐厅！\n夏建国：欺负人欺负到家门口了！请个洋厨子就不知道姓啥了——",
            "assetNames": ["重庆老街对门双火锅铺街景", "林双双", "楚南", "夏建国", "叶寻", "夏芊芊"],
            "ref_images": [kf("3-2-11"), kf("3-2-12_aux"), f_lin, f_chu, f_jian, f_ye, f_qian],
            "ref_audios": [v_lin, v_jian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young woman on screen-right in <Picture 1> clinging to <Subject 2>'s arm, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 2>: The young man beside <Subject 1> in <Picture 1>, matching <Picture 4>.\n"
                "- <Subject 3> (S2): The master chef on screen-right of the steps in <Picture 2>, matching <Picture 5>. Voice matches Audio 2.\n"
                "- <Subject 4>: The young man on screen-left of the steps in <Picture 2>, matching <Picture 6>.\n"
                "- <Subject 5>: The young woman holding the ledger between them in <Picture 2>, matching <Picture 7>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.5s) Close-up framed from <Picture 1> on <Subject 1> jeering toward screen-left.\n"
                "- [Shot 2] (4.5s-9.6s) Medium close-up framed from <Picture 2> on the west stone steps.\n"
                "- [Shot 3] (9.6s-13.0s) Tighter medium three-shot on the steps as <Subject 4> blocks <Subject 3> and opens <Subject 5>'s ledger.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-4.3s): Tilting her chin high in spiteful pride toward screen-left, <Subject 1> (S1) calls out sharply: <d>[Chinese] 叶寻，瞧见没，离了你，我家照样开高档西餐厅。</d>\n"
                "- [Shot 2] (4.7s-9.4s): Stepping half a pace forward and pointing furiously toward screen-right while <Subject 4> tucks the folded paper into his backpack pocket, <Subject 3> (S2) roars: <d>[Chinese] 欺负人欺负到家门口了，请个洋厨子就不知道姓啥了。</d>\n"
                "- [Shot 3] (9.7s-13.0s): Raising his left forearm calmly across <Subject 3>'s chest to hold him back without sparing a single glance across the street, <Subject 4> turns directly to <Subject 5> and flips open the ledger in her hands.\n"
                "[Environment]\n- Sunlit Chongqing bluestone street.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Spiteful female taunt, booming angry older male roar, crisp rustle of ledger pages flipped open, zero music."
            ),
        },
        {
            "id": "3-2-14", "episode": 3, "duration": 15, "seed": 73214,
            "description": "叶寻劝夏叔不必置气并向夏芊芊核实账上净剩两万六现钱，正拍板从门口动工改明档，画外骤传沉重铁斗车滚轮急推声。",
            "dialogue": "叶寻：夏叔，犯不着跟他们置气。芊芊姐，账上还能腾出多少现钱？\n夏芊芊：账面一共三万八，刨去欠菜贩子的货款，手里现钱就剩两万六了。\n叶寻：两万六够把前头改成明档了，今儿先从门口动——",
            "assetNames": ["重庆老街对门双火锅铺街景", "叶寻", "夏芊芊", "夏建国"],
            "ref_images": [kf("3-2-14"), f_ye, f_qian, f_jian],
            "ref_audios": [v_ye, v_qian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young man on screen-left in <Picture 1> pointing at the open ledger, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The young woman holding the open ledger on screen-right, matching <Picture 3>. Voice matches Audio 2.\n"
                "- <Subject 3>: The master chef standing beside <Subject 2> on the steps, matching <Picture 4>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-5.0s) Over-the-shoulder close-up framed from <Picture 1> onto <Subject 1>.\n"
                "- [Shot 2] (5.0s-11.0s) Reverse over-the-shoulder close-up onto <Subject 2> reading the open ledger.\n"
                "- [Shot 3] (11.0s-15.0s) Medium close-up three-shot on the stone steps with <Subject 1> on screen-left, <Subject 2> in center, and <Subject 3> on screen-right.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-4.8s): Tapping the open ledger page calmly and looking at <Subject 2>, <Subject 1> (S1) asks steadily: <d>[Chinese] 夏叔，犯不着跟他们置气，芊芊姐，账上还能腾出多少现钱。</d>\n"
                "- [Shot 2] (5.2s-10.8s): Scanning the bottom summary line and looking earnestly up at <Subject 1>, <Subject 2> (S2) answers clearly: <d>[Chinese] 账面一共三万八，刨去欠菜贩子的货款，手里现钱就剩两万六了。</d>\n"
                "- [Shot 3] (11.2s-14.8s): Closing the ledger cover decisively and pointing toward the storefront entrance, <Subject 1> (S1) says: <d>[Chinese] 两万六够把前头改成明档了，今儿先从门口动。</d> At 14.3s, loud heavy iron wheelbarrow wheels rumble from screen-right and all three snap their heads sharply right.\n"
                "[Environment]\n- Sunlit stone steps outside the west storefront.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Calm male inquiry, clear earnest female accounting reply, confident male plan interrupted at 14.3s by heavy rumbling iron wheels, zero music."
            ),
        },
        {
            "id": "3-2-17", "episode": 3, "duration": 11, "seed": 73217,
            "description": "赵帆一挥手，两辆满载水泥沙石的铁皮斗车横穿马路哗啦一声全倾倒在夏记正门口堵死台阶和排水沟，夏芊芊气红眼眶愤怒质问。",
            "dialogue": "夏芊芊：你们干什么呀！自己装修凭什么往我家门口倒沙子？！",
            "assetNames": ["重庆老街对门双火锅铺街景", "赵帆", "叶寻", "夏芊芊", "夏建国"],
            "ref_images": [kf("3-2-17"), f_zhao, f_ye, f_qian, f_jian],
            "ref_audios": [v_qian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The chef standing at right-rear in <Picture 1>, matching <Picture 2>.\n"
                "- <Subject 2>: The young man on the left foreground steps in <Picture 1>, matching <Picture 3>.\n"
                "- <Subject 3> (S1): The young woman clutching the ledger on the left steps in <Picture 1>, matching <Picture 4>. Voice matches Audio 1.\n"
                "- <Subject 4>: The master chef on the left steps in <Picture 1>, matching <Picture 5>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-2.8s) High-angle wide street shot framed from <Picture 1>.\n"
                "- [Shot 2] (2.8s-5.8s) Medium downward shot of the west storefront stone steps and drainage ditch with a sharp impact shake.\n"
                "- [Shot 3] (5.8s-11.0s) Medium close-up on <Subject 3> standing on the stone steps amidst settling dust.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-2.7s): At right-rear, <Subject 1> waves his right hand aggressively and two hard-hatted workers push two iron wheelbarrows heaped with grey-yellow sand and gravel straight across the narrow street to the west steps.\n"
                "- [Shot 2] (2.9s-5.7s): Both workers tip the iron wheelbarrows up sharply, dumping a huge mound of sand and gravel with a roaring crash that completely blocks the stone steps and drainage ditch in a cloud of dust.\n"
                "- [Shot 3] (6.0s-10.4s): Hugging the ledger to her chest and pointing furiously down toward screen-right through the thinning dust, <Subject 3> (S1) shouts indignantly: <d>[Chinese] 你们干什么呀，自己装修凭什么往我家门口倒沙子。</d> She presses her lips shut in anger right as she finishes.\n"
                "[Environment]\n- Sunlit Chongqing bluestone street with sand and gravel dumped against the steps.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Rumbling iron wheelbarrows, crashing roar of dumped gravel and sand, indignant female shout, zero music."
            ),
        },
        {
            "id": "3-2-20", "episode": 3, "duration": 12, "seed": 73220,
            "description": "赵帆歪着脖子无赖嘲讽破店没人登门借台阶堆半个月，夏建国暴怒抄起门边长柄铁锹要拼命，被叶寻一把按住铁锹杆沉稳接过手。",
            "dialogue": "赵帆：路窄，借你们台阶堆半个月呗，横竖你们这破店也没人登门！\n夏建国：蹬鼻子上脸是吧，我跟你们拼了——",
            "assetNames": ["重庆老街对门双火锅铺街景", "赵帆", "夏建国", "叶寻", "夏芊芊"],
            "ref_images": [kf("3-2-20"), f_zhao, f_jian, f_ye, f_qian],
            "ref_audios": [v_zhao, v_jian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The chef standing arrogantly beside the gravel mound on screen-right in <Picture 1> with the red booklet tucked under his left arm, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The master chef on the west stone steps, matching <Picture 3>. Voice matches Audio 2.\n"
                "- <Subject 3>: The young man on the steps, matching <Picture 4>.\n"
                "- <Subject 4>: The young woman holding the ledger on the steps, matching <Picture 5>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-6.0s) Slightly low-angle medium close-up framed from <Picture 1> on <Subject 1> facing upper-left.\n"
                "- [Shot 2] (6.0s-9.5s) Medium side shot of the west doorway steps where a long-handled iron shovel leans against the wooden doorpost.\n"
                "- [Shot 3] (9.5s-12.0s) Tight close-up on the wooden shovel shaft gripped between <Subject 2> on screen-right and <Subject 3> stepping in from screen-left.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-5.8s): Gesturing dismissively at the gravel mound and folding his arms with a smug sneer toward upper-left, <Subject 1> (S1) jeers: <d>[Chinese] 路窄，借你们台阶堆半个月呗，横竖你们这破店也没人登门。</d>\n"
                "- [Shot 2] (6.2s-9.4s): Veins bulging in fury, <Subject 2> (S2) snatches up the long-handled iron shovel from the doorpost with both hands to charge down the steps, roaring: <d>[Chinese] 蹬鼻子上脸是吧，我跟你们拼了。</d>\n"
                "- [Shot 3] (9.6s-12.0s): <Subject 3> clamps both hands firmly onto the center of the wooden shovel shaft, takes the shovel steadily into his own hands, and steps squarely in front of <Subject 2>.\n"
                "[Environment]\n- Sunlit Chongqing street steps blocked by a mound of sand and gravel.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Smug shameless male jeer, iron shovel scraped off stone, furious older male roar, solid grip on wooden shovel handle, zero music."
            ),
        },
        {
            "id": "3-2-23", "episode": 3, "duration": 13, "seed": 73223,
            "description": "迎着对门林双双和楚南看戏的刺耳哄笑，叶寻提铁锹一步踏上沙石堆顶端盯死赵帆，赵帆狂妄拍胸碰瓷叫嚣动一下赔十万切集。",
            "dialogue": "赵帆：咋的穷学生，还敢抡铁锹啊？来，往这儿拍，动一下赔十万！",
            "assetNames": ["重庆老街对门双火锅铺街景", "林双双", "楚南", "叶寻", "赵帆"],
            "ref_images": [kf("3-2-23"), kf("3-2-24_aux"), f_lin, f_chu, f_ye, f_zhao],
            "ref_audios": [v_zhao],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The young woman laughing across the street in <Picture 1>, matching <Picture 3>.\n"
                "- <Subject 2>: The young man holding a megaphone beside <Subject 1> in <Picture 1>, matching <Picture 4>.\n"
                "- <Subject 3>: The young man standing high atop the gravel mound gripping the long-handled iron shovel in <Picture 2>, matching <Picture 5>.\n"
                "- <Subject 4> (S1): The chef standing on the road at lower-right below the gravel mound in <Picture 2>, matching <Picture 6>. Voice matches Audio 1.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-2.0s) Medium close-up two-shot framed from <Picture 1> as <Subject 1> and <Subject 2> laugh mockingly toward screen-left.\n"
                "- [Shot 2] (2.0s-4.8s) Low-angle push-in medium shot framed from <Picture 2> as <Subject 3> steps firmly atop the gravel mound and plants the iron shovel blade into the sand.\n"
                "- [Shot 3] (4.8s-10.5s) High-angle over-the-shoulder close-up past <Subject 3>'s shovel shaft onto <Subject 4> below on screen-right.\n"
                "- [Shot 4] (10.5s-13.0s) Low-angle tight close-up on <Subject 3> towering atop the gravel mound with white-knuckled grip on the shovel shaft.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.1s-1.9s): Watching the blocked entrance across the street, <Subject 1> and <Subject 2> throw their heads back in gloating laughter.\n"
                "- [Shot 2] (2.1s-4.7s): Stepping heavily onto the crest of the sand-and-gravel mound, <Subject 3> drives the iron shovel blade sharply into the gravel beside his boot and locks icy eyes down on <Subject 4>.\n"
                "- [Shot 3] (5.0s-10.3s): Stepping half a pace closer and slapping his own chest twice provocatively with his right palm, <Subject 4> (S1) glares up at <Subject 3> and taunts: <d>[Chinese] 咋的穷学生，还敢抡铁锹啊，来，往这儿拍，动一下赔十万。</d> He holds his arrogant chin-out glare silently.\n"
                "- [Shot 4] (10.6s-13.0s): With lips pressed tightly shut, <Subject 3>'s knuckles tighten white around the wooden shovel shaft as he drives the blade half an inch deeper into the gravel, freezing on the razor's edge of retaliation.\n"
                "[Environment]\n- Bright sunlit Chongqing street with high sand-and-gravel mound blocking the storefront steps.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Mocking laughter in [Shot 1], heavy boot crunch on gravel and iron shovel blade driven into sand in [Shot 2], two chest slaps and brazen male taunt in [Shot 3], creaking wooden shaft in [Shot 4], zero music."
            ),
        },
    ]

    return ep1, ep2, ep3


def gen_dry_vo_4070(out_mp4: Path, face_1k: Path, voice_wav: Path, text: str, dur: int, seed: int) -> dict:
    if out_mp4.is_file() and out_mp4.with_suffix(".json").is_file():
        return json.loads(out_mp4.with_suffix(".json").read_text(encoding="utf-8"))
    vo_prompt = (
        "[Subject]\n"
        "- <Subject 1> (S1): The speaker in <Picture 1>. Voice matches Audio 1.\n"
        "[Shot]\n"
        f"- [Shot 1] (0s-{dur}s) Static close-up framed from <Picture 1>.\n"
        "[Timeline]\n"
        f"- [Shot 1] (0.1s-{dur - 0.2:.1f}s): <Subject 1> (S1) speaks briskly and clearly: <d>[Chinese] {text}</d>\n"
        "[Environment]\n- Quiet dry room.\n"
        "[Camera & Visuals]\n- Static portrait, pure theatrical frame.\n"
        "[Audio]\n- Clean dry close-mic voice matching Audio 1, zero background noise, zero music."
    )
    old_ckpt = vo_split.LOWRES_CHECKPOINT
    vo_split.LOWRES_CHECKPOINT = ""
    try:
        return vo_split.h3_lowres(
            out_mp4, vo_prompt, dur, seed, "9:16", "reference", [face_1k], None, None, [voice_wav]
        )
    finally:
        vo_split.LOWRES_CHECKPOINT = old_ckpt


def run_one_shot(spec: Dict[str, Any], outdir: Path, force: bool = False) -> None:
    sid = spec["id"]
    sdir = outdir / sid
    sdir.mkdir(parents=True, exist_ok=True)
    final_mp4 = sdir / "video.mp4"
    final_meta = sdir / "video.json"
    strip_jpg = DIAG_DIR / f"{sid}_0.5s.jpg"

    if final_mp4.is_file() and final_meta.is_file() and not force:
        if not strip_jpg.is_file():
            make_half_sec_strip(final_mp4, sid, strip_jpg)
        print(f"[skip] {sid} already exists", flush=True)
        return

    vc = spec.get("vo_custom")
    if not vc:
        pika_runner.run_shot(spec, outdir, CACHE_1K, resolution="480p", force=force)
        make_half_sec_strip(final_mp4, sid, strip_jpg)
        return

    base_mp4 = sdir / "video_base.mp4"
    vo_mp4 = sdir / "vo_short_368p.mp4"
    refs_1k = [pika_runner.ensure_1k_image(Path(p), CACHE_1K) for p in spec["ref_images"]]
    audios = [Path(p) for p in spec.get("ref_audios", [])]
    face_1k = pika_runner.ensure_1k_image(Path(vc["face_1k"]), CACHE_1K)

    print(f"[start+vo_custom] {sid} ({spec['duration']}s 480p + {vc['duration']}s 368p male VO)", flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        if base_mp4.is_file() and base_mp4.with_suffix(".json").is_file() and not force:
            fut_b = pool.submit(lambda: json.loads(base_mp4.with_suffix(".json").read_text(encoding="utf-8")))
        else:
            fut_b = pool.submit(
                pika_runner.call_pika_5090,
                base_mp4, spec["prompt"], int(spec["duration"]), int(spec["seed"]), "9:16", "480p", refs_1k, audios,
            )
        if force and vo_mp4.is_file():
            vo_mp4.unlink(missing_ok=True)
            vo_mp4.with_suffix(".json").unlink(missing_ok=True)
        fut_v = pool.submit(
            gen_dry_vo_4070, vo_mp4, face_1k, Path(vc["voice"]), vc["text"], int(vc["duration"]), int(spec["seed"]) + 77
        )
        meta = fut_b.result()
        vo_hdr = fut_v.result()

    vo_vocals = sdir / "vo_short_vocals.wav"
    if force or not vo_vocals.is_file():
        vo_split.demucs_vocals(vo_mp4, vo_vocals)
    ss, se = trim_silence_bounds(vo_vocals)
    raw_dur = se - ss
    atempo_str = ""
    if raw_dur > float(vc["max_len"]):
        ratio = min(1.25, raw_dur / float(vc["max_len"]))
        atempo_str = f"atempo={ratio:.3f},"
        eff_dur = raw_dur / ratio
    else:
        eff_dur = raw_dur

    duck_lvl = float(vc.get("base_duck", 0.22))
    start_mute = max(0.0, float(vc["dst_start"]) - 0.08)
    end_mute = float(vc["dst_start"]) + eff_dur + 0.12
    tmp = final_mp4.with_suffix(".tmp.mp4")
    filt = (
        f"[0:a]aresample=48000,volume='if(between(t,{start_mute:.3f},{end_mute:.3f}),{duck_lvl:.2f},1.0)':eval=frame[base];"
        f"[1:a]aresample=48000,atrim={ss:.3f}:{se:.3f},asetpts=PTS-STARTPTS,{atempo_str}"
        f"afade=t=in:d=0.06,afade=t=out:st={max(0.0, eff_dur - 0.08):.3f}:d=0.08,"
        f"volume=1.85,adelay={int(round(float(vc['dst_start']) * 1000))}:all=1[vo];"
        f"[base][vo]amix=inputs=2:duration=first:normalize=0[a]"
    )
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-i", str(base_mp4), "-i", str(vo_vocals),
        "-filter_complex", filt, "-map", "0:v", "-map", "[a]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(tmp),
    ], check=True)
    tmp.replace(final_mp4)
    meta["vo_custom_applied"] = {
        "src": [ss, se], "eff_dur": round(eff_dur, 3),
        "dst_start": vc["dst_start"], "vo_headers": vo_hdr,
    }
    final_meta.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    make_half_sec_strip(final_mp4, sid, strip_jpg)
    print(f"[done+vo_custom] {sid} -> VO [{ss}..{se}] (eff {eff_dur:.2f}s) placed at {vc['dst_start']}s", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lint-only", action="store_true")
    ap.add_argument("--ep", type=int, choices=[0, 1, 2, 3], default=0, help="0 = all Ep 1, 2, 3")
    ap.add_argument("--only", action="append", default=[])
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    ep1, ep2, ep3 = build_plans()
    (WORK_DIR / "ep01_v7_plan.json").write_text(json.dumps(ep1, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (WORK_DIR / "ep02_v7_plan.json").write_text(json.dumps(ep2, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (WORK_DIR / "ep03_v7_plan.json").write_text(json.dumps(ep3, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    all_issues = []
    for s in ep1 + ep2 + ep3:
        all_issues.extend(pika_runner.lint_zero_appearance(s["prompt"], s["id"]))
        if len(s["ref_images"]) > 9:
            all_issues.append(f"[{s['id']}] Too many ref_images: {len(s['ref_images'])} > 9")
        if len(s.get("ref_audios", [])) > 3:
            all_issues.append(f"[{s['id']}] Too many ref_audios: {len(s['ref_audios'])} > 3")
        if not (5 <= int(s["duration"]) <= 15):
            all_issues.append(f"[{s['id']}] Invalid duration: {s['duration']}")
    if all_issues:
        print("LINT FAILED:\n" + "\n".join(all_issues), file=sys.stderr)
        sys.exit(2)
    print(
        f"LINT PASSED: 0 issues across {len(ep1)} Ep1 + {len(ep2)} Ep2 + {len(ep3)} Ep3 = {len(ep1)+len(ep2)+len(ep3)} groups!",
        flush=True,
    )
    if args.lint_only:
        return

    targets = []
    if args.ep in (0, 1):
        targets.extend((s, TAKES_EP1) for s in ep1)
    if args.ep in (0, 2):
        targets.extend((s, TAKES_EP2) for s in ep2)
    if args.ep in (0, 3):
        targets.extend((s, TAKES_EP3) for s in ep3)
    if args.only:
        only_set = set(args.only)
        targets = [(s, d) for (s, d) in targets if s["id"] in only_set]

    for s, outdir in targets:
        run_one_shot(s, outdir, force=args.force)


if __name__ == "__main__":
    main()
