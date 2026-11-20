#!/usr/bin/env python3
"""
Compile & execute ALL 3 EPISODES (`Ep 1` = 12 shots, `Ep 2` = 12 shots, `Ep 3` = 11 shots = 35 crisp shots)
for `2005_chongqing_hotpot_v5` in 9:16 480p on local 5090 Pika-H3-Flex + 4070 Ti SUPER 368p dry male VO,
plus automatic `0.5s` high-res frame-strip generation (`diag_strips/<id>_0.5s.jpg`) for every shot!

Strict invariants enforced:
  - <= 1K reference images (`keyframes_1k` + `assets_1k`)
  - Zero character appearance/clothing/age tokens in video prompts (`lint_zero_appearance` == 0 issues)
  - Pure 35mm theatrical cinema framing + comma/period `<d>` punctuation (zero burned-in text/subtitles)
  - Exact `[start_mute..end_mute]` ducking window for 4070 male `[VO]` clips (`v_yexun` + `f_ye_apron`)
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

WORK_DIR = Path("/home/zhongwenyu/project/ai-director-train/productions/2005_chongqing_hotpot_v5/video_gen")
KF_1K = WORK_DIR / "keyframes_1k"
CACHE_1K = WORK_DIR / "cache_1k"
TAKES_EP1 = WORK_DIR / "takes_ep01"
TAKES_EP2 = WORK_DIR / "takes_ep02"
TAKES_EP3 = WORK_DIR / "takes_ep03"
DIAG_DIR = WORK_DIR / "diag_strips"

for d in (CACHE_1K, TAKES_EP1, TAKES_EP2, TAKES_EP3, DIAG_DIR):
    d.mkdir(parents=True, exist_ok=True)

CLEAN_CAMERA = "- Pure 35mm theatrical cinema photography with completely clean unobstructed lower frame, natural eye lines and lip-sync."


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
        draw.rectangle([c * tw, r * th, c * tw + 92, r * th + 26], fill=(0, 0, 0))
        draw.text((c * tw + 6, r * th + 6), f"{sid} {t_sec:.1f}s", fill=(255, 230, 80))
    canvas.save(out_jpg, quality=88)
    for old in tmp_dir.glob("*.jpg"):
        old.unlink()
    tmp_dir.rmdir()
    return out_jpg


def build_plans() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    amap = json.loads((WORK_DIR / "asset_map.json").read_text(encoding="utf-8"))

    v_ye = amap["叶寻"]["voice"]
    v_qian = amap["夏芊芊"]["voice"]
    v_lin = amap["林双双"]["voice"]
    v_chu = amap["楚南"]["voice"]
    v_youcai = amap["林有才"]["voice"]
    v_laoma = amap["老马"]["voice"]

    f_ye_2015 = amap["叶寻 · 2020研发总厨白服"]["front_1k"]
    f_lin_2015 = amap["林双双 · 塞纳左岸酒红礼服"]["front_1k"]
    f_chu_2015 = amap["楚南 · 海归并购总监西装"]["front_1k"]

    f_ye_apron = amap["叶寻 · 渝清记围裙掌勺"]["front_1k"]
    f_ye_clean = amap["叶寻_脱围裙"]["front_1k"]
    f_lin = amap["林双双"]["front_1k"]
    f_youcai = amap["林有才"]["front_1k"]
    f_qian = amap["夏芊芊"]["front_1k"]
    f_laoma = amap["老马"]["front_1k"]
    f_diner = amap["中年食客"]["front_1k"]

    # ==================== EPISODE 1 (12 SHOTS) ====================
    ep1 = [
        {
            "id": "1-1-01", "episode": 1, "duration": 9, "seed": 51101,
            "description": "2015年林氏火锅上市夜雨巷，叶寻咳血跌跪在泥水里质问婚约，林有才嫌恶踢开药袋翻脸。",
            "dialogue": "叶寻：林叔，双双！我替林家熬坏了肺，不是说上市就完婚吗？\n林有才：小寻呐，林氏都上市了，哪能招个病痨厨子当女婿？",
            "assetNames": ["集团大厦旋转门雨夜街口", "叶寻 · 2020研发总厨白服", "林有才"],
            "ref_images": [kf("1-1-01"), f_ye_2015, f_youcai],
            "ref_audios": [v_ye, v_youcai],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The drenched man kneeling on the wet pavement on the left of <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The man standing under the eaves on the right of <Picture 1>, matching <Picture 3>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.7s) Low-angle medium shot framed from <Picture 1> in the pouring night rain.\n"
                "- [Shot 2] (4.7s-9.0s) Reverse high-angle medium close-up favoring <Subject 2> looking down coldly.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-4.6s): Clutching his chest in the rain puddles, <Subject 1> (S1) looks up desperately and speaks hoarsely: <d>[Chinese] 林叔，双双，我替林家熬坏了肺，不是说上市就完婚吗。</d>\n"
                "- [Shot 2] (4.8s-8.7s): Nudging the soaked medicine packet away with his shoe, <Subject 2> (S2) sneers down disdainfully: <d>[Chinese] 小寻呐，林氏都上市了，哪能招个病痨厨子当女婿。</d>\n"
                "[Environment]\n- Rain-lashed city street outside a glowing banquet building at night.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Pouring night rain, hoarse anguished male speech, cold disdainful male reply, zero music."
            ),
        },
        {
            "id": "1-1-02", "episode": 1, "duration": 9, "seed": 51102,
            "description": "黑伞下林双双挽紧楚南露出腕间浪琴金表炫耀早与楚南定情，楚南冷漠揭穿骗取秘方真相。",
            "dialogue": "林双双：阿寻哥，看清这金表没？毕业前楚南哥早送我了。\n楚南：骗全你们叶家红汤秘方，你的用处早到头了。",
            "assetNames": ["集团大厦旋转门雨夜街口", "林双双 · 塞纳左岸酒红礼服", "楚南 · 海归并购总监西装"],
            "ref_images": [kf("1-1-02"), f_lin_2015, f_chu_2015],
            "ref_audios": [v_lin, v_chu],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The woman on the left under the black umbrella in <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The man on the right holding the umbrella in <Picture 1>, matching <Picture 3>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.6s) Medium close-up two-shot under the umbrella framed from <Picture 1>, showing the gold watch on <Subject 1>'s left wrist.\n"
                "- [Shot 2] (4.6s-9.0s) Tighter two-shot favoring <Subject 2>'s cold gaze.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-4.5s): Holding <Subject 2>'s arm closely and tilting her left wrist so the gold watch catches the light, <Subject 1> (S1) speaks smugly: <d>[Chinese] 阿寻哥，看清这金表没，毕业前楚南哥早送我了。</d>\n"
                "- [Shot 2] (4.7s-8.7s): Looking down without pity, <Subject 2> (S2) speaks in an icy tone: <d>[Chinese] 骗全你们叶家红汤秘方，你的用处早到头了。</d>\n"
                "[Environment]\n- Neon-lit rainy night outside the luxury building entrance.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Rain pattering on umbrella canopy, smug female dialogue, cold male dialogue, zero music."
            ),
        },
        {
            "id": "1-1-03", "episode": 1, "duration": 7, "seed": 51103,
            "description": "叶寻双目赤红嘶吼咒骂，楚南搂林双双转身进门，叶寻重重栽倒在雨夜积水中昏死过去。",
            "dialogue": "叶寻：那是我爸的心血……你们不得好死！",
            "assetNames": ["集团大厦旋转门雨夜街口", "叶寻 · 2020研发总厨白服"],
            "ref_images": [kf("1-1-03"), f_ye_2015],
            "ref_audios": [v_ye],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The drenched man on the wet pavement in <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-7.0s) Low-angle close-up framed from <Picture 1> in heavy rain.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-4.0s): Trembling in the rain with bloodshot eyes fixed ahead, <Subject 1> (S1) cries out in raw fury: <d>[Chinese] 那是我爸的心血，你们不得好死。</d>\n"
                "- [Shot 1] (4.0s-7.0s): His strength gives out completely and <Subject 1> collapses sideways onto the rain-soaked asphalt as his eyes slowly close.\n"
                "[Environment]\n- Heavy night rain pooling over dark asphalt with warm golden lights blurred behind.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Heavy rain splash, fierce hoarse male cry, dull thud in puddle, zero music."
            ),
        },
        {
            "id": "1-2-01", "episode": 1, "duration": 7, "seed": 51201,
            "description": "叶寻在2005年夏沙正街林记火锅堂厅猛然惊醒，看着自己年轻有力的双手确认重回林双双毕业家宴。",
            "dialogue": "[VO] 叶寻：二〇〇五年……我回到了双双毕业家宴这天？",
            "assetNames": ["沙正街林家食府老店大堂", "叶寻 · 渝清记围裙掌勺"],
            "ref_images": [kf("1-2-01"), f_ye_apron],
            "ref_audios": [],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The man seated on the left of the round wooden table in <Picture 1>, matching <Picture 2>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-7.0s) Medium close-up framed from <Picture 1> inside the sunlit 2005 hotpot hall under a spinning ceiling fan.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-7.0s): Jolting awake with a sharp silent gasp and keeping his lips firmly closed, <Subject 1> looks down in disbelief at both of his hands held above the wooden tabletop, clenches his fists feeling his strength, and lifts his gaze alertly.\n"
                "[Environment]\n- Warm sunlit 2005 Chongqing wooden hotpot hall with rising pot steam.\n"
                "[Camera & Visuals]\n- Pure 35mm theatrical cinema photography with completely clean unobstructed lower frame, <Subject 1>'s lips strictly closed throughout.\n"
                "[Audio]\n- Gentle bubbling of hotpot broth and quiet ceiling fan hum, zero speech, zero music."
            ),
            "vo_custom": {
                "face_1k": f_ye_apron, "voice": v_ye,
                "text": "二〇〇五年，我回到了双双毕业家宴这天。",
                "duration": 5, "dst_start": 0.7, "max_len": 5.5,
            },
        },
        {
            "id": "1-2-02", "episode": 1, "duration": 10, "seed": 51202,
            "description": "林有才满面红光端啤酒拍叶寻肩膀夸他掌勺四年撑火，林双双甜笑感谢叶寻守灶供她读完财大。",
            "dialogue": "林有才：小寻，林叔敬你！你厨校毕业掌勺四年，林记全靠你撑火！\n林双双：是呀阿寻哥，多亏你守灶供我读完省城财大。",
            "assetNames": ["沙正街林家食府老店大堂", "叶寻 · 渝清记围裙掌勺", "林有才", "林双双"],
            "ref_images": [kf("1-2-02"), f_ye_apron, f_youcai, f_lin],
            "ref_audios": [v_youcai, v_lin],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The man seated on the left of the round table in <Picture 1>, matching <Picture 2>.\n"
                "- <Subject 2> (S1): The man seated in the center of <Picture 1> holding a beer glass, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 3> (S2): The woman seated on the right of <Picture 1>, matching <Picture 4>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-5.3s) Medium three-shot framed from <Picture 1> across the steaming hotpot table.\n"
                "- [Shot 2] (5.3s-10.0s) Medium close-up favoring <Subject 3> smiling warmly toward <Subject 1>.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-5.1s): Patting <Subject 1>'s shoulder warmly and raising his chilled beer glass with a beaming grin, <Subject 2> (S1) speaks heartily: <d>[Chinese] 小寻，林叔敬你，你厨校毕业掌勺四年，林记全靠你撑火。</d>\n"
                "- [Shot 2] (5.4s-9.6s): Smiling sweetly at <Subject 1>, <Subject 3> (S2) chimes in softly: <d>[Chinese] 是呀阿寻哥，多亏你守灶供我读完省城财大。</d>\n"
                "[Environment]\n- Sunlit bustling 2005 Chongqing wooden hotpot hall.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Warm clink of glass, hearty male toast, sweet female voice, subtle hotpot simmer, zero music."
            ),
        },
        {
            "id": "1-2-03", "episode": 1, "duration": 10, "seed": 51203,
            "description": "叶寻不动声色反问何事客气，林有才笑眯眯抛出下月初八定亲并分三成干股的温情大饼。",
            "dialogue": "叶寻：林叔，今天吹什么风，这么客气？\n林有才：你爸走得早，林叔早把你当亲半子疼。\n林有才：下月初八给你们定亲，分你林记三成干股！",
            "assetNames": ["沙正街林家食府老店大堂", "叶寻 · 渝清记围裙掌勺", "林有才"],
            "ref_images": [kf("1-2-03"), f_ye_apron, f_youcai],
            "ref_audios": [v_ye, v_youcai],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The man seated in the left foreground of <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The man seated opposite in the center of <Picture 1>, matching <Picture 3>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-3.2s) Over-shoulder medium close-up on <Subject 1> watching calmly without touching his beer glass.\n"
                "- [Shot 2] (3.2s-10.0s) Reverse medium close-up on <Subject 2> leaning forward with an affectionate, calculating grin.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-3.0s): Keeping his hand still on the table, <Subject 1> (S1) asks evenly: <d>[Chinese] 林叔，今天吹什么风，这么客气。</d>\n"
                "- [Shot 2] (3.3s-9.7s): Setting down his glass and patting his chest affectionately, <Subject 2> (S2) beams and declares: <d>[Chinese] 你爸走得早，林叔早把你当亲半子疼，下月初八给你们定亲，分你林记三成干股。</d>\n"
                "[Environment]\n- Sunlit 2005 Chongqing hotpot hall.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Calm young male voice, warm effusive older male voice, subtle restaurant ambience, zero music."
            ),
        },
        {
            "id": "1-2-04", "episode": 1, "duration": 9, "seed": 51204,
            "description": "叶寻平静追问定亲干股，林双双娇笑着取出记账本和钢笔摆上桌，左手腕间露出崭新浪琴金表。",
            "dialogue": "叶寻：三成干股，下个月就定亲？\n林双双：那还有假？下周换新执照，想拿招牌红汤报评优。",
            "assetNames": ["沙正街林家食府老店大堂", "叶寻 · 渝清记围裙掌勺", "林双双"],
            "ref_images": [kf("1-2-04"), f_ye_apron, f_lin],
            "ref_audios": [v_ye, v_lin],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The man seated on the left of <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The woman seated on the right of <Picture 1> with a gold watch on her left wrist, matching <Picture 3>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-3.2s) Medium two-shot framed from <Picture 1>.\n"
                "- [Shot 2] (3.2s-9.0s) Closer medium shot on <Subject 2> setting the hardcover ledger and uncapped pen onto the wooden table, revealing the gleaming gold watch on her left wrist.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-3.0s): Looking steadily across at her, <Subject 1> (S1) asks coolly: <d>[Chinese] 三成干股，下个月就定亲。</d>\n"
                "- [Shot 2] (3.3s-8.6s): Placing the hardcover ledger and pen onto the tabletop so the gold watch on her left wrist gleams in the light, <Subject 2> (S2) smiles coaxingly: <d>[Chinese] 那还有假，下周换新执照，想拿招牌红汤报评优。</d>\n"
                "[Environment]\n- Sunlit 2005 wooden hotpot hall.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Ledger set on wooden table, calm male voice, sweet coaxing female voice, zero music."
            ),
        },
        {
            "id": "1-2-05", "episode": 1, "duration": 9, "seed": 51205,
            "description": "叶寻目光钉在金表上，林双双推过账本哄他写全最后三味退燥配比，林有才帮腔说店归小两口。",
            "dialogue": "林双双：叶叔那方子还缺最后三味退燥配比，你写全嘛。\n林有才：写全锁柜里，往后这店不都是你们小两口的？",
            "assetNames": ["沙正街林家食府老店大堂", "叶寻 · 渝清记围裙掌勺", "林双双", "林有才"],
            "ref_images": [kf("1-2-05"), f_ye_apron, f_lin, f_youcai],
            "ref_audios": [v_lin, v_youcai],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The man on the left of <Picture 1> staring sharply at the gold watch, matching <Picture 2>.\n"
                "- <Subject 2> (S1): The woman on the right of <Picture 1> pushing the open ledger forward, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 3> (S2): The man in the center background of <Picture 1>, matching <Picture 4>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.6s) Tight medium shot framed from <Picture 1> as <Subject 2>'s watch-clad left hand slides the open ledger toward <Subject 1>.\n"
                "- [Shot 2] (4.6s-9.0s) Medium shot favoring <Subject 3> nodding warmly beside <Subject 2> while <Subject 1>'s eyes narrow on the watch.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-4.4s): Sliding the open ledger and pen right to <Subject 1>'s hand, <Subject 2> (S1) speaks in a cajoling voice: <d>[Chinese] 叶叔那方子还缺最后三味退燥配比，你写全嘛。</d>\n"
                "- [Shot 2] (4.7s-8.6s): Nodding reassuringly, <Subject 3> (S2) adds: <d>[Chinese] 写全锁柜里，往后这店不都是你们小两口的。</d>\n"
                "[Environment]\n- Sunlit 2005 wooden hotpot hall.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Paper sliding on wood, cajoling female voice, smooth older male voice, zero music."
            ),
        },
        {
            "id": "1-2-06", "episode": 1, "duration": 10, "seed": 51206,
            "description": "叶寻心底冷笑前世被婚约拖死十年，伸两指将记账本稳稳推回，拒绝未定亲先交立命秘方。",
            "dialogue": "[VO] 叶寻：前世刚补全这三味，他们就拿婚约拖死我十年。\n叶寻：我爸留我立命的方子，没定亲就交，太早了吧？",
            "assetNames": ["沙正街林家食府老店大堂", "叶寻 · 渝清记围裙掌勺"],
            "ref_images": [kf("1-2-06"), f_ye_apron],
            "ref_audios": [v_ye],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The man seated on the left of the table in <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.6s) Close-up on <Subject 1> with lips strictly closed as his two fingers push the open ledger firmly back across the wooden table.\n"
                "- [Shot 2] (4.6s-10.0s) Medium close-up on <Subject 1> looking up coldly and speaking.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-4.5s): Keeping his lips completely closed with an icy glint in his eyes, <Subject 1> presses two fingers onto the edge of the ledger and slides it steadily back across the tabletop.\n"
                "- [Shot 2] (4.8s-9.6s): Lifting his gaze calmly, <Subject 1> (S1) speaks clearly: <d>[Chinese] 我爸留我立命的方子，没定亲就交，太早了吧。</d>\n"
                "[Environment]\n- Sunlit 2005 wooden hotpot hall.\n"
                "[Camera & Visuals]\n- Pure 35mm theatrical cinema photography with completely clean unobstructed lower frame, <Subject 1>'s lips strictly closed from 0s to 4.6s.\n"
                "[Audio]\n- Crisp slide of ledger across wood from 0s to 4.6s, clear measured male speech starting at 4.8s, zero music."
            ),
            "vo_custom": {
                "face_1k": f_ye_apron, "voice": v_ye,
                "text": "前世刚补全这三味，他们就拿婚约拖死我十年。",
                "duration": 5, "dst_start": 0.3, "max_len": 4.2,
            },
        },
        {
            "id": "1-2-07", "episode": 1, "duration": 11, "seed": 51207,
            "description": "林有才林双双假意打圆场装委屈，叶寻直接点破林双双腕上专柜八千多的浪琴金表。",
            "dialogue": "林有才：一家人咋还见外？林叔还能亏待自家姑爷？\n林双双：阿寻哥你疑心我？我一毕业就回来守着你呢！\n叶寻：守着我？你腕上这块浪琴金表，专柜得八千多吧？",
            "assetNames": ["沙正街林家食府老店大堂", "叶寻 · 渝清记围裙掌勺", "林有才", "林双双"],
            "ref_images": [kf("1-2-07"), f_ye_apron, f_youcai, f_lin],
            "ref_audios": [v_youcai, v_lin, v_ye],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S3): The man seated on the left of <Picture 1>, matching <Picture 2>. Voice matches Audio 3.\n"
                "- <Subject 2> (S1): The man seated in the center of <Picture 1>, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 3> (S2): The woman seated on the right of <Picture 1>, matching <Picture 4>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-7.1s) Medium three-shot framed from <Picture 1> across the round table.\n"
                "- [Shot 2] (7.1s-11.0s) Close-up favoring <Subject 1> nodding sharply toward <Subject 3>'s left wrist.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-3.5s): Spreading his hands warmly, <Subject 2> (S1) says: <d>[Chinese] 一家人咋还见外，林叔还能亏待自家姑爷。</d>\n"
                "- [Shot 1] (3.7s-7.0s): Leaning in with feigned hurt, <Subject 3> (S2) says: <d>[Chinese] 阿寻哥你疑心我，我一毕业就回来守着你呢。</d>\n"
                "- [Shot 2] (7.2s-10.7s): Fixing his cold gaze on her wrist, <Subject 1> (S3) asks pointedly: <d>[Chinese] 守着我，你腕上这块浪琴金表，专柜得八千多吧。</d>\n"
                "[Environment]\n- Sunlit 2005 wooden hotpot hall.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Brisk three-person dramatic exchange, subtle restaurant room tone, zero music."
            ),
        },
        {
            "id": "1-2-08", "episode": 1, "duration": 10, "seed": 51208,
            "description": "林双双脸色骤变慌忙捂表谎称地摊仿表，叶寻点破原厂钢印追问哪位省城少爷送的，林有才急催写方。",
            "dialogue": "林双双：这……省城地摊几十块买的仿表，你看岔了！\n叶寻：仿表有原厂钢印？省城哪位少爷送的定情礼？\n林有才：大喜日子揪着块表盘问啥？快把方子写上！",
            "assetNames": ["沙正街林家食府老店大堂", "林双双", "林有才", "叶寻 · 渝清记围裙掌勺"],
            "ref_images": [kf("1-2-08"), f_lin, f_youcai, f_ye_apron],
            "ref_audios": [v_lin, v_ye, v_youcai],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The woman on the right of <Picture 1> clutching her left wrist, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2> (S3): The man beside her on the left of <Picture 1>, matching <Picture 3>. Voice matches Audio 3.\n"
                "- <Subject 3> (S2): The man seated opposite them, matching <Picture 4>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-3.6s) Medium close-up framed from <Picture 1> as <Subject 1> hurriedly covers her gold watch.\n"
                "- [Shot 2] (3.6s-6.9s) Reverse close-up on <Subject 3> questioning coldly.\n"
                "- [Shot 3] (6.9s-10.0s) Medium close-up back on <Subject 2> frowning impatiently.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-3.5s): Pulling her right hand over her left wrist in panic, <Subject 1> (S1) stammers: <d>[Chinese] 这，省城地摊几十块买的仿表，你看岔了。</d>\n"
                "- [Shot 2] (3.7s-6.8s): Unblinking, <Subject 3> (S2) presses coldly: <d>[Chinese] 仿表有原厂钢印，省城哪位少爷送的定情礼。</d>\n"
                "- [Shot 3] (7.0s-9.7s): Scowling impatiently, <Subject 2> (S3) snaps: <d>[Chinese] 大喜日子揪着块表盘问啥，快把方子写上。</d>\n"
                "[Environment]\n- Sunlit 2005 wooden hotpot hall.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Flustered female excuse, piercing young male question, impatient older male bark, zero music."
            ),
        },
        {
            "id": "1-2-09", "episode": 1, "duration": 7, "seed": 51299,
            "description": "叶寻靠回竹椅直视面色煞白的林双双抛出致命一问，林有才酒杯僵在半空，满桌假笑彻底凝固。",
            "dialogue": "叶寻：方子补全，下月进林家门的，真是我吗？",
            "assetNames": ["沙正街林家食府老店大堂", "叶寻 · 渝清记围裙掌勺", "林有才", "林双双"],
            "ref_images": [kf("1-2-09"), f_ye_apron, f_youcai, f_lin],
            "ref_audios": [v_ye],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The man leaning back in his bamboo chair on the left of <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2>: The man in the center of <Picture 1> holding a beer glass, matching <Picture 3>.\n"
                "- <Subject 3>: The woman on the right of <Picture 1> gripping the pen, matching <Picture 4>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.4s) Medium three-shot framed from <Picture 1> across the round wooden table as <Subject 1> leans back calmly.\n"
                "- [Shot 2] (4.4s-7.0s) Instant hard cut to medium close-up two-shot on <Subject 2> and <Subject 3> freezing in dead silence.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-4.3s): Leaning back steadily with razor-sharp eyes fixed on <Subject 3>, <Subject 1> (S1) asks in a calm, piercing voice: <d>[Chinese] 方子补全，下月进林家门的，真是我吗。</d>\n"
                "- [Shot 2] (4.4s-7.0s): Keeping their mouths completely shut in stunned silence, <Subject 2> freezes with his beer glass mid-air and <Subject 3> goes pale clutching the pen.\n"
                "[Environment]\n- Sunlit 2005 wooden hotpot hall falling abruptly silent.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Calm piercing male question from 0.2s to 4.3s, then silent room tone only, zero music."
            ),
        },
    ]

    # ==================== EPISODE 2 (12 SHOTS) ====================
    ep2 = [
        {
            "id": "2-1-01", "episode": 2, "duration": 9, "seed": 52101,
            "description": "紧接上集原桌死寂，林双双心虚捂表抵赖，林有才沉脸重重墩下酒杯拿一家人道德绑架。",
            "dialogue": "林双双：阿寻哥，你胡说啥，什么进门不进门的！\n林有才：小寻，林叔看你长大，一家人你说啥子怪话？",
            "assetNames": ["沙正街林家食府老店大堂", "叶寻 · 渝清记围裙掌勺", "林有才", "林双双"],
            "ref_images": [kf("2-1-01"), f_ye_apron, f_youcai, f_lin],
            "ref_audios": [v_lin, v_youcai],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The man seated calmly on the left of <Picture 1>, matching <Picture 2>.\n"
                "- <Subject 2> (S2): The man seated in the center of <Picture 1>, matching <Picture 3>. Voice matches Audio 2.\n"
                "- <Subject 3> (S1): The woman seated on the right of <Picture 1>, matching <Picture 4>. Voice matches Audio 1.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.2s) Medium three-shot framed from <Picture 1> in the silent hotpot hall.\n"
                "- [Shot 2] (4.2s-9.0s) Medium close-up on <Subject 2> slamming his beer glass down onto the wooden table.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-4.0s): Covering her left wrist nervously, <Subject 3> (S1) protests sharply: <d>[Chinese] 阿寻哥，你胡说啥，什么进门不进门的。</d>\n"
                "- [Shot 2] (4.3s-8.6s): Dropping his smile and slamming the beer glass down with a thud, <Subject 2> (S2) scowls: <d>[Chinese] 小寻，林叔看你长大，一家人你说啥子怪话。</d>\n"
                "[Environment]\n- Sunlit 2005 wooden hotpot hall under spinning ceiling fan.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Flustered female voice, heavy thud of glass on wood, stern older male voice, zero music."
            ),
        },
        {
            "id": "2-1-02", "episode": 2, "duration": 10, "seed": 52102,
            "description": "叶寻摊开满是烫疤的双手质问月薪两千二只发四百，林有才强辩余钱替他攒着娶林双双。",
            "dialogue": "叶寻：一家人？熟练大厨月薪两千二，林叔给我发多少？\n林有才：每月四百零花还少？余钱不是替你攒着娶双双吗！",
            "assetNames": ["沙正街林家食府老店大堂", "叶寻 · 渝清记围裙掌勺", "林有才"],
            "ref_images": [kf("2-1-02"), f_ye_apron, f_youcai],
            "ref_audios": [v_ye, v_youcai],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The man on the left of <Picture 1> spreading his scarred hands on the table, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The man in the center of <Picture 1>, matching <Picture 3>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.6s) Medium close-up framed from <Picture 1> showing <Subject 1>'s hands flat beside the ledger.\n"
                "- [Shot 2] (4.6s-10.0s) Reverse medium close-up on <Subject 2> retorting defensively.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-4.4s): Spreading both scarred palms flat beside the ledger and staring straight at <Subject 2>, <Subject 1> (S1) asks coldly: <d>[Chinese] 一家人，熟练大厨月薪两千二，林叔给我发多少。</d>\n"
                "- [Shot 2] (4.8s-9.5s): Pointing at the table defensively, <Subject 2> (S2) blusters: <d>[Chinese] 每月四百零花还少，余钱不是替你攒着娶双双吗。</d>\n"
                "[Environment]\n- Sunlit 2005 wooden hotpot hall.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Palms placed on wood, cold steady male voice, defensive older male bluster, zero music."
            ),
        },
        {
            "id": "2-1-03", "episode": 2, "duration": 10, "seed": 52103,
            "description": "叶寻戳破林家拿他手艺钱供林双双读完四年大学，更一针见血点出省城楚少楚南的名字。",
            "dialogue": "叶寻：攒彩礼，还是拿我的手艺钱供她读完四年大学？\n林双双：当年是你甘愿供我的，现在翻什么旧账！\n叶寻：我是供未婚妻，不是替省城楚少楚南养女人。",
            "assetNames": ["沙正街林家食府老店大堂", "叶寻 · 渝清记围裙掌勺", "林双双"],
            "ref_images": [kf("2-1-03"), f_ye_apron, f_lin],
            "ref_audios": [v_ye, v_lin],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The man on the left of <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The woman on the right of <Picture 1>, matching <Picture 3>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-6.6s) Medium two-shot framed from <Picture 1> across the wooden table.\n"
                "- [Shot 2] (6.6s-10.0s) Tight close-up on <Subject 1> delivering the decisive blow.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-3.5s): Looking straight at her, <Subject 1> (S1) says: <d>[Chinese] 攒彩礼，还是拿我的手艺钱供她读完四年大学。</d>\n"
                "- [Shot 1] (3.7s-6.5s): Flushing with annoyance, <Subject 2> (S2) snaps back: <d>[Chinese] 当年是你甘愿供我的，现在翻什么旧账。</d>\n"
                "- [Shot 2] (6.7s-9.7s): Unflinching, <Subject 1> (S1) replies in an ice-cold voice: <d>[Chinese] 我是供未婚妻，不是替省城楚少楚南养女人。</d>\n"
                "[Environment]\n- Sunlit 2005 wooden hotpot hall.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Sharp rapid confrontation between young man and woman, zero music."
            ),
        },
        {
            "id": "2-1-04", "episode": 2, "duration": 11, "seed": 52104,
            "description": "林双双惊骇起身撞歪竹椅追问怎知楚南，叶寻揭穿三天后楚南来验汤摘桃子的算计。",
            "dialogue": "林双双：你……你怎么知道楚南哥？\n叶寻：大四实习你就跟了他，等三天后他来验汤，好拿全方献宝吧？\n[VO] 叶寻：前世直到死前，我才知楚南一直在幕后等摘桃子。",
            "assetNames": ["沙正街林家食府老店大堂", "叶寻 · 渝清记围裙掌勺", "林有才", "林双双"],
            "ref_images": [kf("2-1-04"), f_ye_apron, f_youcai, f_lin],
            "ref_audios": [v_lin, v_ye],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S2): The man seated steadily on the left of <Picture 1>, matching <Picture 2>. Voice matches Audio 2.\n"
                "- <Subject 2>: The dark-faced man in the center of <Picture 1>, matching <Picture 3>.\n"
                "- <Subject 3> (S1): The startled woman standing on the right of <Picture 1>, matching <Picture 4>. Voice matches Audio 1.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-2.7s) Medium three-shot framed from <Picture 1> as <Subject 3> stands in shock.\n"
                "- [Shot 2] (2.7s-11.0s) Close-up on <Subject 1> speaking coldly from 2.8s to 6.8s, then holding a silent, piercing stare with lips strictly closed from 6.8s to 11.0s.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-2.5s): Standing rigid beside her tilted bamboo chair, <Subject 3> (S1) gasps: <d>[Chinese] 你，你怎么知道楚南哥。</d>\n"
                "- [Shot 2] (2.8s-6.7s): Looking up at her calmly, <Subject 1> (S2) says: <d>[Chinese] 大四实习你就跟了他，等三天后他来验汤，好拿全方献宝吧。</d>\n"
                "- [Shot 2] (6.8s-11.0s): Keeping his lips completely closed, <Subject 1> holds an ice-cold, knowing gaze across the table.\n"
                "[Environment]\n- Sunlit 2005 wooden hotpot hall.\n"
                "[Camera & Visuals]\n- Pure 35mm theatrical cinema photography with completely clean unobstructed lower frame, <Subject 1>'s lips strictly closed from 6.8s to 11.0s.\n"
                "[Audio]\n- Shocked female gasp, cold male revelation ending at 6.7s, quiet room tone from 6.8s to 11.0s, zero music."
            ),
            "vo_custom": {
                "face_1k": f_ye_apron, "voice": v_ye,
                "text": "前世直到死前，我才知楚南一直在幕后等摘桃子。",
                "duration": 5, "dst_start": 6.9, "max_len": 3.9,
            },
        },
        {
            "id": "2-1-05", "episode": 2, "duration": 10, "seed": 52105,
            "description": "林有才索性撕破伪善摊牌，林双双炫耀楚少注资二十万，叶寻冷嘲二十万买叶家祖传锅底。",
            "dialogue": "林有才：行，既然看穿了，林叔也不跟你装糊涂。\n林双双：人往高处走！楚少肯注资二十万，你给得起吗？\n叶寻：二十万买我叶家祖传锅底，算盘打得真响。",
            "assetNames": ["沙正街林家食府老店大堂", "林有才", "林双双", "叶寻 · 渝清记围裙掌勺"],
            "ref_images": [kf("2-1-05"), f_youcai, f_lin, f_ye_apron],
            "ref_audios": [v_youcai, v_lin, v_ye],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The man seated and leaning back coldly on the right of <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The woman standing beside him on the left of <Picture 1>, matching <Picture 3>. Voice matches Audio 2.\n"
                "- <Subject 3> (S3): The young man opposite them, matching <Picture 4>. Voice matches Audio 3.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-7.0s) Medium two-shot framed from <Picture 1> on <Subject 1> and <Subject 2> dropping all pretense.\n"
                "- [Shot 2] (7.0s-10.0s) Reverse close-up on <Subject 3> sneering quietly.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-3.5s): Leaning back with a brazen sneer, <Subject 1> (S1) says: <d>[Chinese] 行，既然看穿了，林叔也不跟你装糊涂。</d>\n"
                "- [Shot 1] (3.7s-6.9s): Lifting her chin arrogantly, <Subject 2> (S2) says: <d>[Chinese] 人往高处走，楚少肯注资二十万，你给得起吗。</d>\n"
                "- [Shot 2] (7.1s-9.7s): <Subject 3> (S3) replies coolly: <d>[Chinese] 二十万买我叶家祖传锅底，算盘打得真响。</d>\n"
                "[Environment]\n- Sunlit 2005 wooden hotpot hall.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Brazen older male voice, haughty female voice, dry incisive young male reply, zero music."
            ),
        },
        {
            "id": "2-1-06", "episode": 2, "duration": 10, "seed": 52106,
            "description": "林有才狂妄宣称叶寻炒料四年二十多味香料顺序他早看熟了，离了林记叶寻连铁锅都支不起。",
            "dialogue": "林有才：少拿乔！你炒料四年，二十多味香料顺序我早看熟了！\n林有才：有楚少二十万撑腰，离了我林记，你连口铁锅都支不起！",
            "assetNames": ["沙正街林家食府老店大堂", "林有才"],
            "ref_images": [kf("2-1-06"), f_youcai],
            "ref_audios": [v_youcai],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The arrogant boss in <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-10.0s) Medium close-up framed from <Picture 1> with the kitchen pass behind him.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.3s-9.5s): Pointing his thumb cockily toward the kitchen behind him and jabbing a finger forward, <Subject 1> (S1) boasts loudly: <d>[Chinese] 少拿乔，你炒料四年，二十多味香料顺序我早看熟了，有楚少二十万撑腰，离了我林记，你连口铁锅都支不起。</d>\n"
                "[Environment]\n- Sunlit 2005 wooden hotpot hall.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Arrogant booming male boast, subtle restaurant ambience, zero music."
            ),
        },
        {
            "id": "2-1-07", "episode": 2, "duration": 7, "seed": 52107,
            "description": "叶寻一言不发将半页试配单按进冷茶碗搓成烂纸泥，林有才惊怒伸手大喊捞出来。",
            "dialogue": "林有才：你干啥！把试配单捞出来！",
            "assetNames": ["沙正街林家食府老店大堂", "叶寻 · 渝清记围裙掌勺", "林有才"],
            "ref_images": [kf("2-1-07"), f_ye_apron, f_youcai],
            "ref_audios": [v_youcai],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The young man standing on the left of <Picture 1>, matching <Picture 2>.\n"
                "- <Subject 2> (S1): The older man reaching out in alarm on the right of <Picture 1>, matching <Picture 3>. Voice matches Audio 1.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-3.1s) Medium two-shot framed from <Picture 1> as <Subject 1>'s hand plunges the half-sheet handwritten draft into the porcelain bowl of dark cold tea and crushes it into wet pulp.\n"
                "- [Shot 2] (3.1s-7.0s) Instant hard cut to medium close-up on <Subject 2> lunging toward the bowl in panic.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-3.0s): Without a word, <Subject 1> presses the half-sheet paper deep into the bowl of dark tea and rubs it into shredded wet pulp.\n"
                "- [Shot 2] (3.2s-6.6s): Lunging toward the table in panic, <Subject 2> (S1) shouts: <d>[Chinese] 你干啥，把试配单捞出来。</d>\n"
                "[Environment]\n- Sunlit 2005 wooden hotpot hall.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Splash of tea and wet paper tearing, frantic older male shout, zero music."
            ),
        },
        {
            "id": "2-1-08", "episode": 2, "duration": 8, "seed": 52108,
            "description": "已解下围裙的叶寻拧死后厨母锅燃气总阀熄火，摘下亡父留下的老熟铁炒勺宣告四年两清。",
            "dialogue": "叶寻：灶火我替林家烧了四年，今天撤勺熄火，两清了。",
            "assetNames": ["夏氏小厨后厨猛火炒灶", "叶寻"],
            "ref_images": [kf("2-1-08"), f_ye_clean],
            "ref_audios": [v_ye],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young man standing beside the stove in <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-8.0s) Medium shot framed from <Picture 1> at the kitchen stove pass.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-2.2s): <Subject 1> twists the brass main gas valve firmly shut with a sharp metallic click and lifts the long-handled wrought-iron ladle off the wall hook.\n"
                "- [Shot 1] (2.4s-7.6s): Holding the wrought-iron ladle steadily, <Subject 1> (S1) speaks with calm finality: <d>[Chinese] 灶火我替林家烧了四年，今天撤勺熄火，两清了。</d>\n"
                "[Environment]\n- Sunlit 2005 Chongqing restaurant kitchen pass with unlit iron wok.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Crisp metallic valve click, iron ladle lifted from hook, resolute male voice, zero music."
            ),
        },
        {
            "id": "2-1-09", "episode": 2, "duration": 8, "seed": 52109,
            "description": "叶寻提着亡父老铁勺跨向店门，林双双在身后叫嚣不出三天必回来求她爸，叶寻冷声回应走着瞧。",
            "dialogue": "林双双：你身无分文出门，不出三天就得回来求我爸！\n叶寻：三天后谁求谁，走着瞧。",
            "assetNames": ["沙正街林家食府老店大堂", "叶寻", "林双双"],
            "ref_images": [kf("2-1-09"), f_ye_clean, f_lin],
            "ref_audios": [v_lin, v_ye],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S2): The young man at the sunlit doorway on the left of <Picture 1> holding the long iron ladle, matching <Picture 2>. Voice matches Audio 2.\n"
                "- <Subject 2> (S1): The woman inside the hall on the right of <Picture 1>, matching <Picture 3>. Voice matches Audio 1.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.6s) Medium shot framed from <Picture 1> as <Subject 2> shouts at <Subject 1>'s back.\n"
                "- [Shot 2] (4.6s-8.0s) Medium close-up on <Subject 1> glancing half-back at the threshold before stepping out.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-4.4s): Glaring after him, <Subject 2> (S1) shouts spitefully: <d>[Chinese] 你身无分文出门，不出三天就得回来求我爸。</d>\n"
                "- [Shot 2] (4.7s-7.7s): Glancing over his shoulder at the bright doorway, <Subject 1> (S2) replies coolly: <d>[Chinese] 三天后谁求谁，走着瞧。</d>\n"
                "[Environment]\n- Sunlit wooden doorway opening onto a Chongqing bluestone street.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Sharp spiteful female shout, calm confident male reply, footsteps on threshold, zero music."
            ),
        },
        {
            "id": "2-2-01", "episode": 2, "duration": 9, "seed": 52201,
            "description": "叶寻拎老铁勺跨出林记，对门夏记少掌柜夏芊芊穿过青石板街迎上前确认他与林家彻底断清。",
            "dialogue": "夏芊芊：小寻哥！真跟林有才断干净了？\n叶寻：芊芊？嗯，火熄了，往后跟林记再无瓜葛。",
            "assetNames": ["重庆老街对门双火锅铺街景", "叶寻", "夏芊芊"],
            "ref_images": [kf("2-2-01"), f_ye_clean, f_qian],
            "ref_audios": [v_qian, v_ye],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S2): The young man on the right of <Picture 1> holding the wrought-iron ladle, matching <Picture 2>. Voice matches Audio 2.\n"
                "- <Subject 2> (S1): The young woman on the left of <Picture 1> stepping up to meet him, matching <Picture 3>. Voice matches Audio 1.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-9.0s) Sunlit street medium two-shot framed from <Picture 1> between the two facing hotpot shops.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.3s-3.9s): Stopping right in front of <Subject 1> with bright, earnest eyes, <Subject 2> (S1) asks briskly: <d>[Chinese] 小寻哥，真跟林有才断干净了。</d>\n"
                "- [Shot 1] (4.2s-8.6s): Nodding firmly with the iron ladle in hand, <Subject 1> (S2) answers: <d>[Chinese] 芊芊，嗯，火熄了，往后跟林记再无瓜葛。</d>\n"
                "[Environment]\n- Daytime sunlit 2005 Chongqing bluestone street between two traditional hotpot storefronts.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Footsteps on bluestone, crisp female question, steady male answer, daytime street air, zero music."
            ),
        },
        {
            "id": "2-2-02", "episode": 2, "duration": 9, "seed": 52202,
            "description": "林有才追到门口幸灾乐祸嘲笑夏记昨晚刚跑了师傅，叶寻反唇相讥让他先操心今晚自家锅底。",
            "dialogue": "林有才：夏丫头，你店里昨晚刚跑了师傅，自身都难保喽！\n叶寻：林老板还是先操心今晚自己的锅底能不能熬响吧。",
            "assetNames": ["重庆老街对门双火锅铺街景", "夏芊芊", "叶寻", "林有才"],
            "ref_images": [kf("2-2-02"), f_qian, f_ye_clean, f_youcai],
            "ref_audios": [v_youcai, v_ye],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The young woman standing on the left of <Picture 1>, matching <Picture 2>.\n"
                "- <Subject 2> (S2): The young man standing center-left in <Picture 1> holding the iron ladle, matching <Picture 3>. Voice matches Audio 2.\n"
                "- <Subject 3> (S1): The older boss leaning in the doorway on the right of <Picture 1>, matching <Picture 4>. Voice matches Audio 1.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.5s) Medium shot framed from <Picture 1> favoring <Subject 3> jeering from the right doorway.\n"
                "- [Shot 2] (4.5s-9.0s) Instant hard cut to medium two-shot on <Subject 2> and <Subject 1> in the sunlit street as <Subject 2> replies coolly.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-4.3s): Leaning against the wooden doorframe with folded arms, <Subject 3> (S1) jeers loudly: <d>[Chinese] 夏丫头，你店里昨晚刚跑了师傅，自身都难保喽。</d>\n"
                "- [Shot 2] (4.6s-8.7s): Glancing calmly toward <Subject 3>, <Subject 2> (S2) replies evenly: <d>[Chinese] 林老板还是先操心今晚自己的锅底能不能熬响吧。</d>\n"
                "[Environment]\n- Sunlit 2005 Chongqing bluestone street.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Mocking older male jeer, cool composed young male retort, subtle street ambience, zero music."
            ),
        },
        {
            "id": "2-2-03", "episode": 2, "duration": 7, "seed": 52203,
            "description": "夏芊芊目光灼灼盯住叶寻手中的叶叔老铁勺，盛邀叶寻入主夏记掌勺，两人四目相对定下战局。",
            "dialogue": "夏芊芊：说得好！叶叔的老铁勺还在，小寻哥，来我夏记掌勺敢不敢？",
            "assetNames": ["重庆老街对门双火锅铺街景", "夏芊芊", "叶寻"],
            "ref_images": [kf("2-2-03"), f_qian, f_ye_clean],
            "ref_audios": [v_qian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young woman on the left of <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2>: The young man on the right of <Picture 1> gripping the wrought-iron ladle, matching <Picture 3>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-7.0s) Tight sunlit two-shot framed from <Picture 1> in the middle of the bluestone street.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-5.2s): Looking straight at the wrought-iron ladle and up into <Subject 2>'s eyes with fiery spirit, <Subject 1> (S1) speaks crisply: <d>[Chinese] 说得好，叶叔的老铁勺还在，小寻哥，来我夏记掌勺敢不敢。</d>\n"
                "- [Shot 1] (5.2s-7.0s): <Subject 2> tightens his grip on the iron ladle handle, locking determined eyes with <Subject 1>.\n"
                "[Environment]\n- Warm sunlit Chongqing old street.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Spirited clear female challenge, subtle metallic grip on iron ladle, zero music."
            ),
        },
    ]

    # ==================== EPISODE 3 (11 SHOTS) ====================
    ep3 = [
        {
            "id": "3-1-01", "episode": 3, "duration": 10, "seed": 53101,
            "description": "步入夏记堂厅，夏芊芊坦言原师傅昨夜被楚南双倍工钱挖走，念及叶父旧恩愿与叶寻五五分账。",
            "dialogue": "叶寻：昨晚店里师傅怎么突然跑了？\n夏芊芊：省城那姓楚的开双倍工钱，连夜把人挖走了。\n夏芊芊：当年叶叔救过我爸的急，只要你掌勺，夏记咱五五分！",
            "assetNames": ["桂花巷渝清记大堂与天井", "叶寻", "夏芊芊"],
            "ref_images": [kf("3-1-01"), f_ye_clean, f_qian],
            "ref_audios": [v_ye, v_qian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young man on the left of <Picture 1> beside the wooden counter, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The young woman on the right of <Picture 1>, matching <Picture 3>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-3.0s) Medium two-shot framed from <Picture 1> inside the clean wooden hotpot hall.\n"
                "- [Shot 2] (3.0s-10.0s) Medium close-up favoring <Subject 2> speaking candidly and generously.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-2.8s): Resting the iron ladle against the counter, <Subject 1> (S1) asks: <d>[Chinese] 昨晚店里师傅怎么突然跑了。</d>\n"
                "- [Shot 2] (3.1s-9.6s): Looking straight at him without hesitation, <Subject 2> (S2) explains earnestly: <d>[Chinese] 省城那姓楚的开双倍工钱，连夜把人挖走了，当年叶叔救过我爸的急，只要你掌勺，夏记咱五五分。</d>\n"
                "[Environment]\n- Sunlit clean traditional Chongqing hotpot hall interior.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Calm male inquiry, forthright spirited female reply, quiet wooden hall tone, zero music."
            ),
        },
        {
            "id": "3-1-02", "episode": 3, "duration": 8, "seed": 53102,
            "description": "叶寻拒绝白拿干股，执笔在毛边账纸上写下一式两份字据，夏芊芊感动追问何必立规矩。",
            "dialogue": "叶寻：交情归交情，我不白拿股，咱们立字据。\n夏芊芊：立啥规矩？我还信不过叶叔的儿子？",
            "assetNames": ["桂花巷渝清记大堂与天井", "叶寻", "夏芊芊"],
            "ref_images": [kf("3-1-02"), f_ye_clean, f_qian],
            "ref_audios": [v_ye, v_qian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young man on the left of <Picture 1> holding a brush over two ledger sheets on the counter, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The young woman on the right of <Picture 1>, matching <Picture 3>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-8.0s) Countertop medium two-shot framed from <Picture 1>.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-4.0s): Setting the brush down beside the two written sheets on the wooden counter, <Subject 1> (S1) says firmly: <d>[Chinese] 交情归交情，我不白拿股，咱们立字据。</d>\n"
                "- [Shot 1] (4.3s-7.7s): Looking at the written sheets with warm respect, <Subject 2> (S2) says: <d>[Chinese] 立啥规矩，我还信不过叶叔的儿子。</d>\n"
                "[Environment]\n- Sunlit wooden counter inside the traditional hotpot shop.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Brush placed on wood, principled male voice, warm female voice, zero music."
            ),
        },
        {
            "id": "3-1-03", "episode": 3, "duration": 10, "seed": 53193,
            "description": "叶寻亲口立下三天晚市十二桌满座翻台才拿四成分红的军令状，两人爽快在字据上摁下红手印。",
            "dialogue": "叶寻：三天内晚市十二桌满座翻台，我才拿四成分红。\n叶寻：要是做不到，我分文不取。\n夏芊芊：痛快！我管账备菜，小寻哥掌勺，咱们这就开火！",
            "assetNames": ["桂花巷渝清记大堂与天井", "叶寻", "夏芊芊"],
            "ref_images": [kf("3-1-03"), f_ye_clean, f_qian],
            "ref_audios": [v_ye, v_qian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young man on the left of <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The young woman on the right of <Picture 1>, matching <Picture 3>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-5.9s) Medium two-shot framed from <Picture 1> over the two written sheets on the wooden counter, both looking at the sheets and at each other.\n"
                "- [Shot 2] (5.9s-10.0s) Instant hard cut to closer countertop two-shot as both press their red-inked thumbs onto the papers and turn to face each other in profile.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-5.7s): Tapping the written sheet and looking directly across at <Subject 2> (never toward the camera), <Subject 1> (S1) declares clearly: <d>[Chinese] 三天内晚市十二桌满座翻台，我才拿四成分红，要是做不到，我分文不取。</d>\n"
                "- [Shot 2] (6.0s-9.7s): Pressing her red-inked thumb firmly onto the sheet and turning her head left to look warmly into <Subject 1>'s eyes (never toward the camera), <Subject 2> (S2) says brightly: <d>[Chinese] 痛快，我管账备菜，小寻哥掌勺，咱们这就开火。</d>\n"
                "[Environment]\n- Sunlit wooden counter inside the hotpot shop.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Resolute male pledge, firm thump of thumbprints on paper, spirited female response, zero music."
            ),
        },
        {
            "id": "3-1-04", "episode": 3, "duration": 9, "seed": 53194,
            "description": "共用油料商老马擦汗进门把二十块定金拍回柜台，向夏芊芊致歉坦言今天送不了成品老油。",
            "dialogue": "夏芊芊：老马，来得正好！今天送我们夏记的成品老油呢？\n老马：夏掌柜对不住！二十块定金退你，油我送不了了。",
            "assetNames": ["桂花巷渝清记大堂与天井", "叶寻", "夏芊芊", "老王"],
            "ref_images": [kf("3-1-04"), f_ye_clean, f_qian, f_laoma],
            "ref_audios": [v_qian, v_laoma],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The young man on the left of <Picture 1>, matching <Picture 2>.\n"
                "- <Subject 2> (S1): The young woman in the center of <Picture 1> facing <Subject 3>, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 3> (S2): The oil vendor on the right of <Picture 1> placing two banknotes on the counter, matching <Picture 4>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.4s) Medium three-shot framed from <Picture 1> at the shop counter.\n"
                "- [Shot 2] (4.4s-9.0s) Instant hard cut to medium close-up on <Subject 3> pushing the two banknotes forward apologetically.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-4.2s): Looking straight across the counter at <Subject 3> without turning away, <Subject 2> (S1) greets him briskly: <d>[Chinese] 老马，来得正好，今天送我们夏记的成品老油呢。</d>\n"
                "- [Shot 2] (4.5s-8.6s): Setting the two ten-yuan bills onto the wood with a sheepish grimace, <Subject 3> (S2) says apologetically: <d>[Chinese] 夏掌柜对不住，二十块定金退你，油我送不了了。</d>\n"
                "[Environment]\n- Sunlit traditional hotpot shop counter near open street doorway.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Crisp female greeting, apologetic husky male vendor voice, banknotes tapped on counter, zero music."
            ),
        },
        {
            "id": "3-1-05", "episode": 3, "duration": 8, "seed": 53105,
            "description": "叶寻一眼点破是对门林有才卡货，老马拱手承认林有才拿楚氏大单施压不准给夏记供油。",
            "dialogue": "叶寻：老马，是对门林有才卡我们吧？\n老马：叶师傅明鉴！林老板拿楚氏大单压我，不准给夏记供油！",
            "assetNames": ["桂花巷渝清记大堂与天井", "叶寻", "夏芊芊", "老王"],
            "ref_images": [kf("3-1-05"), f_ye_clean, f_qian, f_laoma],
            "ref_audios": [v_ye, v_laoma],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young man on the left of <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2>: The young woman in the center of <Picture 1>, matching <Picture 3>.\n"
                "- <Subject 3> (S2): The vendor on the right of <Picture 1>, matching <Picture 4>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-3.3s) Medium three-shot framed from <Picture 1> favoring <Subject 1> speaking calmly.\n"
                "- [Shot 2] (3.3s-8.0s) Instant hard cut to medium close-up on <Subject 3> clasping his hands apologetically before turning toward the exit.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-3.1s): Calm and unhurried, <Subject 1> (S1) asks: <d>[Chinese] 老马，是对门林有才卡我们吧。</d>\n"
                "- [Shot 2] (3.4s-7.6s): Clasping his hands in apology, <Subject 3> (S2) sighs helplessly: <d>[Chinese] 叶师傅明鉴，林老板拿楚氏大单压我，不准给夏记供油。</d>\n"
                "[Environment]\n- Sunlit hotpot shop interior.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Calm male voice, honest apologetic vendor voice, footsteps departing, zero music."
            ),
        },
        {
            "id": "3-1-06", "episode": 3, "duration": 10, "seed": 53106,
            "description": "林有才摇蒲扇踱到夏记门外嘲笑今晚白水煮菜，夏芊芊怒斥，叶寻从容要两百块去买鲜牛板油。",
            "dialogue": "林有才：哟，老油断供啦？今晚你们夏记拿白水煮菜嗦！\n夏芊芊：林有才，挖人又断货，你还要不要脸！\n叶寻：芊芊，拿两百块钱，我去菜场买鲜牛板油！",
            "assetNames": ["桂花巷渝清记大堂与天井", "叶寻", "夏芊芊", "林有才"],
            "ref_images": [kf("3-1-06"), f_ye_clean, f_qian, f_youcai],
            "ref_audios": [v_youcai, v_qian, v_ye],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S3): The young man standing center-left in <Picture 1>, matching <Picture 2>. Voice matches Audio 3.\n"
                "- <Subject 2> (S2): The young woman standing on the far left of <Picture 1>, matching <Picture 3>. Voice matches Audio 2.\n"
                "- <Subject 3> (S1): The older boss standing outside the doorway on the right of <Picture 1> waving a palm fan, matching <Picture 4>. Voice matches Audio 1.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.3s) Medium shot framed from <Picture 1> favoring <Subject 3> gloating at the open doorway.\n"
                "- [Shot 2] (4.3s-10.0s) Instant hard cut to medium two-shot on <Subject 2> glaring out and <Subject 1> speaking decisively.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-4.1s): Waving his woven palm fan smugly at the threshold, <Subject 3> (S1) jeers: <d>[Chinese] 哟，老油断供啦，今晚你们夏记拿白水煮菜嗦。</d>\n"
                "- [Shot 2] (4.4s-7.1s): Taking half a step forward, <Subject 2> (S2) snaps angrily: <d>[Chinese] 林有才，挖人又断货，你还要不要脸。</d>\n"
                "- [Shot 2] (7.3s-9.8s): Placing a steadying hand near the counter, <Subject 1> (S3) says calmly: <d>[Chinese] 芊芊，拿两百块钱，我去菜场买鲜牛板油。</d>\n"
                "[Environment]\n- Sunlit traditional Chongqing hotpot shop doorway.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Smug older male jeer, indignant female voice, decisive calm young male voice, zero music."
            ),
        },
        {
            "id": "3-2-01", "episode": 3, "duration": 9, "seed": 53201,
            "description": "傍晚晚市前夕夏记门口架起猛火铁锅现切鲜牛板油下锅，林有才抱胸嘲笑生板油现熬必带腥气，叶寻淡定回击。",
            "dialogue": "林有才：叶寻，临上客现买生板油熬？熬出来全是生腥气！\n叶寻：林老板，谁规定老火锅非得靠隔夜陈油撑场面？",
            "assetNames": ["重庆老街对门双火锅铺街景", "叶寻 · 渝清记围裙掌勺", "林有才"],
            "ref_images": [kf("3-2-01"), f_ye_apron, f_youcai],
            "ref_audios": [v_youcai, v_ye],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S2): The young chef on the left of <Picture 1> standing behind the outdoor cast-iron cauldron, matching <Picture 2>. Voice matches Audio 2.\n"
                "- <Subject 2> (S1): The older boss standing arms-crossed on the right side of the street in <Picture 1>, matching <Picture 3>. Voice matches Audio 1.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.7s) Street medium shot framed from <Picture 1> favoring <Subject 2> scoffing from across the bluestone lane.\n"
                "- [Shot 2] (4.7s-9.0s) Instant hard cut to medium close-up on <Subject 1> sliding fresh white beef suet cubes into the hot iron cauldron.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-4.5s): Folding his arms with a mocking laugh, <Subject 2> (S1) calls out: <d>[Chinese] 叶寻，临上客现买生板油熬，熬出来全是生腥气。</d>\n"
                "- [Shot 2] (4.8s-8.7s): Stirring the sizzling suet cubes with his wrought-iron ladle, <Subject 1> (S2) replies evenly: <d>[Chinese] 林老板，谁规定老火锅非得靠隔夜陈油撑场面。</d>\n"
                "[Environment]\n- Warm golden-dusk 2005 Chongqing bluestone street between the two hotpot shops.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Sizzle of fresh suet hitting hot iron, mocking older male shout, confident young chef reply, zero music."
            ),
        },
        {
            "id": "3-2-02", "episode": 3, "duration": 9, "seed": 53202,
            "description": "夏芊芊担忧急火催油发苦，叶寻稳执老铁勺推搅金黄油脂，道出叶家红汤根在现炼鲜油。",
            "dialogue": "夏芊芊：小寻哥，现熬来得及吗？急火催油可容易发苦。\n叶寻：偷学皮毛才怕苦。叶家红汤的根，就在现炼鲜油上。",
            "assetNames": ["重庆老街对门双火锅铺街景", "叶寻 · 渝清记围裙掌勺", "夏芊芊"],
            "ref_images": [kf("3-2-02"), f_ye_apron, f_qian],
            "ref_audios": [v_qian, v_ye],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S2): The young chef on the left of <Picture 1> stirring the cauldron, matching <Picture 2>. Voice matches Audio 2.\n"
                "- <Subject 2> (S1): The young woman on the right of <Picture 1> leaning near the cauldron, matching <Picture 3>. Voice matches Audio 1.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-9.0s) Golden-dusk medium two-shot framed from <Picture 1> beside the sizzling iron cauldron.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-4.2s): Watching the bubbling golden suet closely, <Subject 2> (S1) asks with concern: <d>[Chinese] 小寻哥，现熬来得及吗，急火催油可容易发苦。</d>\n"
                "- [Shot 1] (4.5s-8.7s): Moving the long wrought-iron ladle in steady circles through the clear golden oil, <Subject 1> (S2) answers calmly: <d>[Chinese] 偷学皮毛才怕苦，叶家红汤的根，就在现炼鲜油上。</d>\n"
                "[Environment]\n- Golden dusk outside the traditional hotpot shop with rising warm steam.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Rich rhythmic sizzling of beef tallow, concerned female voice, steady assured male voice, zero music."
            ),
        },
        {
            "id": "3-2-03", "episode": 3, "duration": 10, "seed": 53203,
            "description": "叶寻沿锅边淋入清亮醪糟与葱姜紫草慢火三沸退燥，白雾升腾化出琥珀红油，夏芊芊闻香惊喜赞叹。",
            "dialogue": "[VO] 叶寻：林有才偷看四年，却不知慢火三沸、醪糟退燥才是命门。\n夏芊芊：好香！半点牛腥都没有，闻着还有股清甜劲儿！",
            "assetNames": ["重庆老街对门双火锅铺街景", "叶寻 · 渝清记围裙掌勺", "夏芊芊"],
            "ref_images": [kf("3-2-03"), f_ye_apron, f_qian],
            "ref_audios": [v_qian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The young chef on the left of <Picture 1> pouring the porcelain bowl along the cauldron rim, matching <Picture 2>.\n"
                "- <Subject 2> (S1): The young woman on the right of <Picture 1>, matching <Picture 3>. Voice matches Audio 1.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-5.4s) Close-to-medium culinary shot framed from <Picture 1> as <Subject 1> (lips strictly closed) pours clear fermented rice liquid and aromatics along the hot cauldron rim, sending up fragrant white steam.\n"
                "- [Shot 2] (5.4s-10.0s) Medium close-up on <Subject 2> inhaling deeply as her eyes light up with delight.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-5.3s): Keeping his lips completely closed in focused mastery, <Subject 1> pours the clear bowl of liquid and herbs steadily around the hot iron rim as white steam billows up over luminous amber-red oil.\n"
                "- [Shot 2] (5.6s-9.6s): Leaning in with a radiant smile, <Subject 2> (S1) exclaims happily: <d>[Chinese] 好香，半点牛腥都没有，闻着还有股清甜劲儿。</d>\n"
                "[Environment]\n- Golden dusk outside the Chongqing hotpot shop wrapped in fragrant white steam.\n"
                "[Camera & Visuals]\n- Pure 35mm theatrical cinema photography with completely clean unobstructed lower frame, <Subject 1>'s lips strictly closed from 0s to 5.4s.\n"
                "[Audio]\n- Crisp sizzling hiss of liquid meeting hot oil from 0.5s to 5.2s, delighted female exclamation at 5.6s, zero music."
            ),
            "vo_custom": {
                "face_1k": f_ye_apron, "voice": v_ye,
                "text": "林有才偷看四年，却不知慢火三沸，醪糟退燥才是命门。",
                "duration": 5, "dst_start": 0.3, "max_len": 4.9,
            },
        },
        {
            "id": "3-2-04", "episode": 3, "duration": 7, "seed": 53294,
            "description": "醇厚脂香漫过沙正街，原本走向林记的老街坊停步深吸香气转身朝夏记聚拢，林有才错愕变色。",
            "dialogue": "林有才：邪门了……生板油现熬，咋没一点焦燥味？",
            "assetNames": ["重庆老街对门双火锅铺街景", "中年食客", "林有才"],
            "ref_images": [kf("3-2-04"), f_diner, f_youcai],
            "ref_audios": [v_youcai],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The local diner on the left of <Picture 1>, matching <Picture 2>.\n"
                "- <Subject 2> (S1): The older boss holding a woven palm fan on the right of <Picture 1>, matching <Picture 3>. Voice matches Audio 1.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-2.9s) Medium street shot framed from <Picture 1> as <Subject 1> inhales the drifting steam with pleasure and turns toward the left shop.\n"
                "- [Shot 2] (2.9s-7.0s) Instant hard cut to medium close-up on <Subject 2> staring dumbfounded across the street toward the left.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-2.8s): Stopping mid-step on the bluestone lane, <Subject 1> breathes in the rich aroma deeply with an appreciative nod and walks toward the left storefront.\n"
                "- [Shot 2] (3.0s-6.7s): Staring across the street toward the left in disbelief (never at the camera), <Subject 2> (S1) mutters in shock: <d>[Chinese] 邪门了，生板油现熬，咋没一点焦燥味。</d>\n"
                "[Environment]\n- Early evening lantern-lit Chongqing bluestone street.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Gentle street footsteps, stunned older male mutter, subtle simmering pot sound, zero music."
            ),
        },
        {
            "id": "3-2-05", "episode": 3, "duration": 10, "seed": 53295,
            "description": "叶寻宣告现炼清润老油成了正式开堂迎客，夏芊芊高声招呼街坊进堂，对门林有才铁青着脸怒拍蒲扇。",
            "dialogue": "叶寻：油成了，开堂迎客！今晚就跟对门比一锅真章！\n夏芊芊：好嘞！夏记清润老火锅，现熬头锅红汤开灶喽！",
            "assetNames": ["重庆老街对门双火锅铺街景", "叶寻 · 渝清记围裙掌勺", "夏芊芊", "林有才"],
            "ref_images": [kf("3-2-05"), f_ye_apron, f_qian, f_youcai],
            "ref_audios": [v_ye, v_qian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young chef standing proudly beside the steaming cauldron on the left of <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The young woman welcoming guests beside him in <Picture 1>, matching <Picture 3>. Voice matches Audio 2.\n"
                "- <Subject 3>: The furious older boss on the right steps in <Picture 1>, matching <Picture 4>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-7.5s) Medium street shot framed from <Picture 1> favoring <Subject 1> and <Subject 2> beside the glowing amber cauldron.\n"
                "- [Shot 2] (7.5s-10.0s) Instant hard cut to medium close-up on <Subject 3> glaring leftward across the street and slapping his palm fan sharply against his thigh in silent rage.\n"
                "[Timeline]\n"
                "- [Shot 1] (0.2s-3.9s): Lifting his wrought-iron ladle beside the simmering amber cauldron and looking across the street, <Subject 1> (S1) declares powerfully: <d>[Chinese] 油成了，开堂迎客，今晚就跟对门比一锅真章。</d>\n"
                "- [Shot 1] (4.1s-7.4s): Waving diners warmly toward the open hall, <Subject 2> (S2) calls out brightly: <d>[Chinese] 好嘞，夏记清润老火锅，现熬头锅红汤开灶喽。</d>\n"
                "- [Shot 2] (7.6s-10.0s): Keeping his mouth firmly shut and glaring leftward toward the opposite shop (never looking at the camera), <Subject 3>'s face darkens with fury as he slaps the woven palm fan sharply against his leg.\n"
                "[Environment]\n- Lantern-lit dusk on the bustling Chongqing bluestone street.\n"
                f"[Camera & Visuals]\n{CLEAN_CAMERA}\n"
                "[Audio]\n- Confident male declaration, cheerful female call ending at 7.4s, sharp slap of woven palm fan at 8.2s, zero music."
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

    start_mute = max(0.0, float(vc["dst_start"]) - 0.08)
    end_mute = float(vc["dst_start"]) + eff_dur + 0.12
    tmp = final_mp4.with_suffix(".tmp.mp4")
    filt = (
        f"[0:a]aresample=48000,volume='if(between(t,{start_mute:.3f},{end_mute:.3f}),0.18,1.0)':eval=frame[base];"
        f"[1:a]aresample=48000,atrim={ss:.3f}:{se:.3f},asetpts=PTS-STARTPTS,{atempo_str}"
        f"afade=t=in:d=0.06,afade=t=out:st={max(0.0, eff_dur - 0.08):.3f}:d=0.08,"
        f"volume=1.80,adelay={int(round(float(vc['dst_start']) * 1000))}:all=1[vo];"
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
    (WORK_DIR / "ep01_v5_plan.json").write_text(json.dumps(ep1, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (WORK_DIR / "ep02_v5_plan.json").write_text(json.dumps(ep2, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (WORK_DIR / "ep03_v5_plan.json").write_text(json.dumps(ep3, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    all_issues = []
    for s in ep1 + ep2 + ep3:
        all_issues.extend(pika_runner.lint_zero_appearance(s["prompt"], s["id"]))
    if all_issues:
        print("LINT FAILED:\n" + "\n".join(all_issues), file=sys.stderr)
        sys.exit(2)
    print(f"LINT PASSED: 0 issues across {len(ep1)} Ep1 + {len(ep2)} Ep2 + {len(ep3)} Ep3 = {len(ep1)+len(ep2)+len(ep3)} shots!", flush=True)
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
