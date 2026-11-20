#!/usr/bin/env python3
"""
Episode 1 Seamless Continuity Production Pipeline (ep01_v4_seamless):
Enforces:
  1. Chained Keyframe Generation (1-1-01 -> 1-1-02 -> 1-1-03 -> 1-1-04 -> 1-1-05; 1-2-01 -> 1-2-02; 1-2-03 -> 1-2-04)
     locking tabletop props (red pot + water pitcher -> water pitcher with yellow torn paper shreds -> 48 slips)
  2. Strict t=0.0s Pre-Action Initial Frame Law:
     - 1-1-01 t=0s: recipe in Lin's hand BEFORE slapping chest
     - 1-1-03 t=0s: Chu Nan still present, Lin Youcai steps up, recipe in ONE hand BEFORE ripping, ends with hand reaching into apron pocket
     - 1-1-04 t=0s: yellow shreds STILL floating in water pitcher, ZERO slips on table yet, slips raised in hand -> slammed ON CAMERA -> ends grabbing apron strap
     - 1-1-05 t=0s: Match-on-Action holding pulled-off apron at chest height -> flung into basket ON CAMERA -> walks out door
     - 1-2-01 t=0s: Explicit 6m dual-shop street bridge (walking out of Lin's on right -> across 6m bluestone street -> into Xia's on left)
     - 1-2-02 t=0s: Standing over front wooden table with UNSTAMPED contract -> both stamp red thumbprints ON CAMERA -> footsteps outside make BOTH turn & step toward doorway
     - 1-2-03 t=0s: Blocking doorway matching 1-2-02 end -> villains walk off leaving Ye & Xia standing at doorway
     - 1-2-04 t=0s: Ye & Xia STANDING on feet outside doorway next to EMPTY parked tricycle -> ask question FIRST -> wheel tricycle & hop on ON CAMERA -> pedal off!
"""
from __future__ import annotations
import argparse
import json
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from PIL import Image, ImageDraw

STUDIO_BRIDGE = Path("/home/zhongwenyu/project/playlets-studio/skills/studio-bridge/scripts")
SKILL_SCRIPTS = Path("/home/zhongwenyu/project/ai-director-train/.agents/skills/hit-video/scripts")
sys.path.insert(0, str(STUDIO_BRIDGE))
sys.path.insert(0, str(SKILL_SCRIPTS))

import vtrix_image  # noqa: E402
import pika_runner  # noqa: E402
import vo_split  # noqa: E402
import check_transitions  # noqa: E402
from compress_1k import compress_image_to_1k  # noqa: E402

PREV_WORK = Path("/home/zhongwenyu/project/ai-director-train/productions/2005_chongqing_hotpot_v3/ep01_02_video_gen")
WORK_DIR = Path("/home/zhongwenyu/project/ai-director-train/productions/2005_chongqing_hotpot_v3/ep01_v4_seamless")
KF_2K = WORK_DIR / "keyframes_2k"
KF_1K = WORK_DIR / "keyframes_1k"
CACHE_1K = WORK_DIR / "cache_1k"
TAKES_EP1 = WORK_DIR / "takes_ep01"
for d in (KF_2K, KF_1K, CACHE_1K, TAKES_EP1):
    d.mkdir(parents=True, exist_ok=True)

STYLE_TAIL = (
    "精致电影实拍质感，竖屏9:16中景或中近景构图（避免人物过小或底部大片空地），真实光影层次与皮肤衣料纹理，人物与环境透视比例准确，"
    "严禁出现任何屏幕字幕、台词气泡、水印、分格边框或纯白拼图底。"
)


def kf(sid: str) -> str:
    return str(KF_1K / f"{sid}_1k.png")


def gen_kf(kid: str, refs: list[str], prompt: str, force: bool = False):
    out_2k = KF_2K / f"{kid}.png"
    out_1k = KF_1K / f"{kid}_1k.png"
    if out_2k.is_file() and out_1k.is_file() and not force:
        print(f"  [kf-skip] {kid} exists", flush=True)
        return
    t0 = time.time()
    vtrix_image.generate_vtrix_image(
        prompt=prompt,
        out_path=out_2k,
        ref_files=refs,
        aspect_ratio="9:16",
        resolution="2K",
    )
    info = compress_image_to_1k(out_2k, out_1k, max_side=1024)
    print(f"  [kf-done] {kid} in {time.time() - t0:.1f}s -> 1K={info['new_size']}", flush=True)


def build_contact_sheet(ids: list[str], out_jpg: Path):
    cols = 3
    rows = (len(ids) + cols - 1) // cols
    tw, th = 340, 604
    canvas = Image.new("RGB", (cols * tw, rows * (th + 32)), (18, 16, 24))
    draw = ImageDraw.Draw(canvas)
    resample = getattr(Image, "Resampling", Image).LANCZOS
    for idx, kid in enumerate(ids):
        p = KF_1K / f"{kid}_1k.png"
        if not p.is_file():
            continue
        r, c = divmod(idx, cols)
        x, y = c * tw, r * (th + 32)
        with Image.open(p) as im:
            im_fit = im.convert("RGB").resize((tw - 8, th - 8), resample)
        canvas.paste(im_fit, (x + 4, y + 28))
        draw.text((x + 10, y + 6), kid, fill=(240, 230, 255))
    canvas.save(out_jpg, quality=90)


def generate_chained_keyframes(amap: dict, force: bool = False):
    lin_hall = amap["沙正街林家食府老店大堂"]["main_1k"]
    xia_yard = amap["桂花巷渝清记大堂与天井"]["main_1k"]
    dual_street = amap["重庆老街对门双火锅铺街景"]["main_1k"]

    f_ye_apron = amap["叶寻 · 渝清记围裙掌勺"]["front_1k"]
    f_ye_clean = amap["叶寻_脱围裙"]["front_1k"]
    f_qian = amap["夏芊芊"]["front_1k"]
    f_lin = amap["林双双"]["front_1k"]
    f_chu = amap["楚南"]["front_1k"]
    f_youcai = amap["林有才"]["front_1k"]

    print("=== Stage 1: Generating Chained Pre-Action Keyframes for Episode 1 ===", flush=True)

    # Chain A (Scene 1-1: Lin's Hall) & Chain B (Scene 1-2: Street Bridge + Xia's Courtyard) can run as 2 parallel chains!
    def run_chain_1_1():
        # 1-1-01: Master scene anchor (locks BOTH red broth pot AND clear glass water pitcher on the round wooden table! Recipe still in Lin's hand BEFORE slapping chest!)
        gen_kf(
            "1-1-01",
            [lin_hall, f_ye_apron, f_lin, f_chu],
            (
                "以图1的2005年重庆老餐馆夜晚暖黄灯光大堂（头顶吊扇转动，枣红圆木桌上左侧放着一盆刚端上的红亮火锅底料、桌面右中侧放着一只装满清水的透明玻璃凉水壶）为环境，"
                "严格保持图2系棕色大口袋围裙搭白毛巾年轻男子、图3米白套裙女子、图4黑西装花衬衫男子的五官、发型及穿搭完全一致。"
                "中近景腰部以上三人起始构图（动作发生前态）：画面左侧图2围裙男子刚把红汤盆稳稳放在圆木桌左侧并直起身；"
                "画面右侧图3米白套裙女子挽着图4黑西装男子刚走到桌边，图3女子左手嫌弃掩在鼻前，右手捏着半页泛黄手写纸张正准备朝图2男子胸前递拍过去（纸张尚未贴上胸口）。" + STYLE_TAIL
            ),
            force=force,
        )
        # 1-1-02: Chained from 1-1-01 (Ye Xun holding the slapped half-recipe looking at burn scar on hand, Chu Nan & Lin across same table with pot & pitcher)
        gen_kf(
            "1-1-02",
            [kf("1-1-01"), f_ye_apron, f_chu, f_lin],
            (
                "严格延续图1同一间餐馆夜晚大堂、同一张枣红圆木桌（桌上有红汤盆与透明玻璃凉水壶）及完全一致的光影方位，"
                "严格保持图2系棕色围裙搭白毛巾年轻男子、图3黑西装花衬衫男子、图4米白套裙女子的五官、发型及穿搭一致。"
                "中近景前景特写对峙构图：左前景图2围裙男子右手接住那半页泛黄手写纸，低头怔怔看清自己右手手背浅淡旧烫痕与纸面字迹；"
                "右中景桌旁图3黑西装男子单手揽住图4米白套裙女子的肩膀，满脸居高临下的讥诮冷笑。" + STYLE_TAIL
            ),
            force=force,
        )
        # 1-1-03: Chained from 1-1-01 (Chu Nan & Lin STILL present on right! Lin Youcai steps in on left with teacup! Ye Xun holds paper in ONE hand BEFORE ripping!)
        gen_kf(
            "1-1-03",
            [kf("1-1-01"), f_youcai, f_ye_apron, f_lin, f_chu],
            (
                "严格延续图1同一间餐馆夜晚大堂与同一张枣红圆木桌（桌面左有红汤盆、中间偏右放着那只装满清水的透明玻璃凉水壶），"
                "严格保持图2暗红唐装中年男子、图3系棕色大口袋围裙年轻男子、图4米白套裙女子、图5黑西装男子的五官、发型及穿搭完全一致。"
                "中景四人同桌交锋起始构图（撕纸前态）：画面左侧图2暗红唐装中年男子左手端着青花盖碗茶刚走到桌边，右手屈指准备敲击桌面；"
                "画面中间图3围裙男子站在玻璃凉水壶后方，仅用右手单手在胸前捏着那半页完好的泛黄手写纸（尚未双手撕开），冷冷注视图2；画面右侧图4女子与图5黑西装男子并立旁观。" + STYLE_TAIL
            ),
            force=force,
        )
        # 1-1-04: Chained from 1-1-03 (Glass water pitcher NOW HAS YELLOW TORN PAPER SHREDS floating inside! Tabletop has ZERO slips yet! Ye Xun holds open tin box + raised stack of slips BEFORE slamming!)
        gen_kf(
            "1-1-04",
            [kf("1-1-03"), f_ye_apron, f_lin, f_youcai],
            (
                "严格延续图1同一张枣红圆木桌与人物站位：桌面右侧那只透明玻璃凉水壶的水中清晰漂浮着几片刚撕碎的黄色纸屑，且此时木桌面上除了水壶与茶杯外空无一物（尚未铺放汇款单）！"
                "严格保持图2系棕色围裙年轻男子、图3米白套裙女子、图4暗红唐装中年男子的五官、发型及穿搭完全一致。"
                "中近景拍单前态构图：画面左侧图2围裙男子刚从围裙大兜掏出一只掉漆小铁盒托在左手，右手高高攥着厚厚一沓2005年代淡绿粉边邮政汇款存根悬在木桌上方二十厘米处，正准备重重拍向空桌面；"
                "画面右侧图3米白套裙女子与后侧图4暗红唐装男子神色惊愕盯着他举起的单据。" + STYLE_TAIL
            ),
            force=force,
        )
        # 1-1-05: Chained from 1-1-04 (Match-on-Action: fanned slips & shred-filled pitcher visible on table behind! Ye Xun in charcoal pullover holding just-pulled-off apron at chest height BEFORE dropping into basket!)
        gen_kf(
            "1-1-05",
            [kf("1-1-04"), f_ye_clean, f_youcai, f_lin],
            (
                "延续图1同一间2005年重庆餐馆夜晚大堂（后侧圆木桌上散铺着那沓汇款存根与漂着碎纸的玻璃水壶，左侧通向敞开的双扇木门与门边竹编废纸篓），"
                "严格保持图2穿炭黑色挽袖圆领长袖卫衣年轻男子、图3暗红唐装中年男子、图4米白套裙女子的五官、发型及穿搭完全一致。"
                "中景脱围裙顺接构图（扔篓前态）：画面左中景图2炭黑卫衣年轻男子刚把脖子上的棕色围裙与白毛巾扯下抓在右手胸前高度（尚未扔进左下角竹篓），眼神冷硬果决；"
                "画面右侧桌边图3暗红唐装中年男子脸色铁青欲上前阻拦，后侧图4米白套裙女子双手按着桌上汇款单怔立原地。" + STYLE_TAIL
            ),
            force=force,
        )

    def run_chain_1_2():
        # 1-2-01: Explicit 6-meter dual-shop bluestone street bridge (Nighttime! Right = 林记火锅, Left = 夏记老火锅!)
        gen_kf(
            "1-2-01",
            [dual_street, f_ye_clean, f_qian],
            (
                "以图1的2005年重庆6米宽青石板老街对门双火锅铺（右侧挂红灯笼的『林记火锅』，正对门左侧敞开木门露出圆木桌铜锅的『夏记老火锅』）为环境，转换为夏夜暖黄街灯与红灯笼亮起的夜景，"
                "严格保持图2穿炭黑挽袖圆领卫衣年轻男子与图3系黑色围裙清秀女子的五官、发型及穿搭完全一致。"
                "中景过街空间交代构图：画面右侧『林记火锅』门前石阶下，图2炭黑卫衣男子正大步流星横跨6米青石板街朝左侧走来；"
                "画面左侧正对门『夏记老火锅』敞亮的屋檐门廊下，图3系黑围裙清秀女子站在备好鲜菜的木桌旁关切欣喜地迎上前。" + STYLE_TAIL
            ),
            force=force,
        )
        # 1-2-02: Standing over front wooden table inside Xia's open entrance, UNSTAMPED handwritten sheet + brush + red inkpad (Pre-Stamp!)
        gen_kf(
            "1-2-02",
            [xia_yard, f_qian, f_ye_clean],
            (
                "以图1的2005年重庆老火锅店夜晚暖黄串灯门厅原木方桌（右侧紧邻敞开的临街木门门槛）为环境，严格保持图2系黑围裙清秀女子与图3穿炭黑挽袖卫衣年轻男子的五官、发型及穿搭完全一致。"
                "中近景站立俯身立契前态构图（严禁看镜头）：两人并肩站在原木方桌后方微俯身看着桌面，桌面上铺着一张刚用毛笔写好的宣纸契书（纸面干净尚未摁任何红手印）、一支毛笔与打开盖子的鲜红印泥盒；"
                "右侧图2黑围裙女子刚放下毛笔，右手大拇指正沾向红印泥盒准备摁印，左侧图3炭黑卫衣男子目光专注温和地看着契书。" + STYLE_TAIL
            ),
            force=force,
        )
        # 1-2-03: Blocking Xia's open street doorway (matching 1-2-02 doorway turn!)
        gen_kf(
            "1-2-03",
            [dual_street, f_chu, f_lin, f_qian, f_ye_clean],
            (
                "以图1的2005年重庆夜晚红灯笼亮起的青石板老街与左侧『夏记老火锅』敞开木门前为环境，严格保持图2黑西装花衬衫男子、图3米白套裙女子、图4系黑围裙清秀女子、图5炭黑挽袖卫衣男子的五官、发型及穿搭完全一致。"
                "中景堵门挑衅对峙构图：画面右侧青石板街门外（后方可见对门『林记火锅』灯笼），图2黑西装男子晃着老式手机嚣张冷笑，身旁图3米白套裙女子手里捏着一张大红纸宴席改签单；"
                "画面左侧『夏记老火锅』门槛内，图4黑围裙女子与图5炭黑卫衣男子刚走到门口并肩冷冷迎视。" + STYLE_TAIL
            ),
            force=force,
        )
        # 1-2-04: Chained from 1-2-03! BOTH STANDING ON FEET outside doorway beside EMPTY parked flatbed tricycle (STRICT ZERO PRE-SITTING!)
        gen_kf(
            "1-2-04",
            [kf("1-2-03"), f_ye_clean, f_qian],
            (
                "严格延续图1同一条夜晚暖黄灯笼青石板老街与左侧『夏记老火锅』门前位置（挑衅男女已离开），严格保持图2炭黑挽袖卫衣年轻男子与图3系黑围裙清秀女子的五官、发型及穿搭完全一致。"
                "中景站立商量前态构图（两人双脚均站在青石板地面上，严禁提前坐上三轮车）：左侧『夏记老火锅』木门外墙边停放着一辆空载的老式铁架木斗人力平板三轮车（车座与后木车斗完全空着无人乘坐）；"
                "三轮车旁，图3黑围裙女子站在地面上眉头微锁望向图2男子发愁询问，图2炭黑卫衣男子站在地面上左手扶住三轮车车把、目光果敢看向她。" + STYLE_TAIL
            ),
            force=force,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(run_chain_1_1)
        f2 = pool.submit(run_chain_1_2)
        f1.result()
        f2.result()

    ep1_ids = ["1-1-01", "1-1-02", "1-1-03", "1-1-04", "1-1-05", "1-2-01", "1-2-02", "1-2-03", "1-2-04"]
    build_contact_sheet(ep1_ids, WORK_DIR / "ep01_v4_seamless_keyframes.jpg")
    print("Saved chained keyframe sheet -> ep01_v4_seamless_keyframes.jpg", flush=True)


def build_ep1_plan(amap: dict) -> list[dict]:
    v_yexun = amap["叶寻"]["voice"]
    v_qian = amap["夏芊芊"]["voice"]
    v_lin = amap["林双双"]["voice"]
    v_chu = amap["楚南"]["voice"]
    v_youcai = amap["林有才"]["voice"]

    f_ye_apron = amap["叶寻 · 渝清记围裙掌勺"]["front_1k"]
    f_ye_clean = amap["叶寻_脱围裙"]["front_1k"]
    f_qian = amap["夏芊芊"]["front_1k"]
    f_lin = amap["林双双"]["front_1k"]
    f_chu = amap["楚南"]["front_1k"]
    f_youcai = amap["林有才"]["front_1k"]

    return [
        {
            "id": "1-1-01",
            "episode": 1,
            "duration": 10,
            "seed": 41101,
            "description": "2005年夏夜林记火锅大堂，叶寻刚将红汤底料端上放有玻璃凉水壶的圆桌，林双双挽着楚南嫌恶掩鼻，将半页汤谱拍在叶寻胸口退婚逼方。",
            "dialogue": "林双双：把你叶家清润汤剩下几味草本补全，咱俩婚约算完了。",
            "assetNames": ["沙正街林家食府老店大堂", "叶寻 · 渝清记围裙掌勺", "林双双", "楚南"],
            "ref_images": [kf("1-1-01"), f_ye_apron, f_lin, f_chu],
            "ref_audios": [v_lin],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The man standing on screen-left beside the wooden table in <Picture 1>, matching <Picture 2>.\n"
                "- <Subject 2> (S1): The woman standing in the center-right of <Picture 1> holding the half-sheet yellowed paper, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 3>: The man standing arm-in-arm beside <Subject 2> on screen-right in <Picture 1>, matching <Picture 4>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-2.4s) Medium three-shot starting directly from <Picture 1> beside the wooden table with the red broth pot and clear glass water pitcher.\n"
                "- [Shot 2] (2.4s-10.0s) Medium close-up from the same 180-degree axis favoring <Subject 2> and <Subject 1>.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-2.4s): Covering her nose disdainfully with her left hand beside <Subject 3>, <Subject 2> briskly slaps the yellowed half-sheet paper in her right hand against <Subject 1>'s chest; <Subject 1> catches the paper sheet in his right hand.\n"
                "- [Shot 2] (2.6s-8.4s): Lowering her left hand and tilting her chin arrogantly beside <Subject 3>'s smug smirk, <Subject 2> (S1) speaks in a cold, dismissive tone: <d>[Chinese] 把你叶家清润汤剩下几味草本补全，咱俩婚约算完了。</d>\n"
                "- [Shot 2] (8.4s-10.0s): Holding the yellowed half-sheet paper in his right hand, <Subject 1> lowers his eyes to look at his right hand and the paper as his expression freezes.\n"
                "[Environment]\n"
                "- Warm tungsten-lit 2005 Chongqing restaurant hall on a summer night.\n"
                "[Camera & Visuals]\n"
                "- Pure 35mm theatrical cinema photography with completely clean unobstructed lower frame, crisp physical slap-and-catch action and natural lip-sync.\n"
                "[Audio]\n"
                "- Crisp slap of paper against chest, clear arrogant female Mandarin dialogue, subtle fan hum, zero music."
            ),
        },
        {
            "id": "1-1-02",
            "episode": 1,
            "duration": 12,
            "seed": 41102,
            "description": "顺接上镜，叶寻低头看清右手旧烫痕与半页汤谱确认重回2005年，楚南揽着林双双当面羞辱他是满身牛油味的伙夫。",
            "dialogue": "[VO] 叶寻：重回2005年？前世我交出祖传秘方，反被他们榨干赶出老街！\n楚南：双双马上进我楚氏餐饮当主管，能嫁你个满身牛油味的伙夫？",
            "assetNames": ["沙正街林家食府老店大堂", "叶寻 · 渝清记围裙掌勺", "楚南", "林双双"],
            "ref_images": [kf("1-1-02"), f_ye_apron, f_chu, f_lin],
            "ref_audios": [v_chu],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The man in the left foreground of <Picture 1> holding the half-sheet paper, matching <Picture 2>.\n"
                "- <Subject 2> (S1): The man on screen-right in <Picture 1> with one arm around <Subject 3>, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 3>: The woman standing beside <Subject 2> in <Picture 1>, matching <Picture 4>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-5.4s) Close-up starting from <Picture 1> on <Subject 1> staring down at the faint burn mark on his right hand and the half-sheet paper.\n"
                "- [Shot 2] (5.4s-12.0s) Medium close-up reverse angle from the same 180-degree axis on <Subject 2> and <Subject 3> beside the wooden table.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-5.4s): Keeping his lips firmly closed in silent shock and fierce realization, <Subject 1> stares down at his right hand holding the yellowed half-sheet paper, then raises his eyes sharply toward <Subject 2> and <Subject 3>.\n"
                "- [Shot 2] (5.7s-10.8s): <Subject 2> (S1) pats <Subject 3>'s shoulder and sneers condescendingly at <Subject 1>: <d>[Chinese] 双双马上进我楚氏餐饮当主管，能嫁你个满身牛油味的伙夫。</d>\n"
                "- [Shot 2] (10.8s-12.0s): <Subject 1> turns his gaze slightly toward the left side of the table as heavy footsteps approach.\n"
                "[Environment]\n"
                "- Warm-lit 2005 Chongqing restaurant interior beside the wooden table.\n"
                "[Camera & Visuals]\n"
                "- Pure 35mm theatrical cinema photography with completely clean unobstructed lower frame, <Subject 1>'s lips strictly closed throughout.\n"
                "[Audio]\n"
                "- Quiet paper rustle from 0s to 5.5s, arrogant male dialogue starting at 5.7s, approaching footsteps at 11s, zero music."
            ),
            "vo_custom": {
                "face_1k": f_ye_clean,
                "voice": v_yexun,
                "duration": 6,
                "text": "重回二零零五年，前世我交出祖传秘方，反被他们榨干赶出老街。",
                "dst_start": 0.25,
                "max_len": 5.0,
            },
        },
        {
            "id": "1-1-03",
            "episode": 1,
            "duration": 14,
            "seed": 41103,
            "description": "林有才端茶走到同桌旁敲桌逼叶寻留方抵恩，叶寻双手撕碎半页汤谱扔进桌上玻璃凉水壶，林双双怒斥，叶寻伸手探入围裙前兜掏铁盒。",
            "dialogue": "林有才：白吃我家四年，留张方子抵恩，是你的本分！\n林双双：叶寻你疯了！敢撕我家的方子？",
            "assetNames": ["沙正街林家食府老店大堂", "林有才", "叶寻 · 渝清记围裙掌勺", "林双双", "楚南"],
            "ref_images": [kf("1-1-03"), f_youcai, f_ye_apron, f_lin, f_chu],
            "ref_audios": [v_youcai, v_lin],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The older man holding the lidded teacup on screen-left in <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2>: The man standing behind the clear glass water pitcher in the center of <Picture 1> holding the intact half-sheet paper in his right hand, matching <Picture 3>.\n"
                "- <Subject 3> (S2): The woman standing on screen-right in <Picture 1>, matching <Picture 4>. Voice matches Audio 2.\n"
                "- <Subject 4>: The man standing beside <Subject 3> on screen-right in <Picture 1>, matching <Picture 5>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.4s) Medium four-person shot starting directly from <Picture 1> around the wooden table.\n"
                "- [Shot 2] (4.4s-8.2s) Medium close-up on <Subject 2> bringing both hands together to rip the half-sheet paper into shreds and drop them into the clear glass water pitcher.\n"
                "- [Shot 3] (8.2s-14.0s) Medium two-shot on <Subject 3> snapping in fury while <Subject 2> reaches his hand into his front pocket to pull out a small worn tin box.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-4.2s): Rapping his right knuckles firmly onto the wooden tabletop, <Subject 1> (S1) glares at <Subject 2> and speaks sternly: <d>[Chinese] 白吃我家四年，留张方子抵恩，是你的本分。</d>\n"
                "- [Shot 2] (4.4s-8.1s): Keeping his lips closed with icy resolve, <Subject 2> raises his left hand to grip the intact yellowed paper sheet alongside his right hand, rips the paper cleanly into pieces, and drops the yellow shreds straight into the clear glass water pitcher.\n"
                "- [Shot 3] (8.3s-11.8s): Staring at the floating paper shreds in the pitcher, <Subject 3> (S2) snaps angrily and briskly: <d>[Chinese] 叶寻你疯了，敢撕我家的方子。</d> Immediately upon finishing, <Subject 3> presses her lips shut.\n"
                "- [Shot 3] (11.8s-14.0s): Without speaking, <Subject 2> reaches decisively into his large front pocket and pulls out a small worn tin box.\n"
                "[Environment]\n"
                "- 2005 Chongqing restaurant wooden table with the red broth pot and glass water pitcher.\n"
                "[Camera & Visuals]\n"
                "- Pure 35mm theatrical cinema photography with completely clean unobstructed lower frame, clear Pre-Action -> Rip -> Pocket-Reach continuity.\n"
                "[Audio]\n"
                "- Knuckle rap on wood, stern older male voice, crisp paper rip and water splash, angry female voice, metallic clink of tin box at 12.5s, zero music."
            ),
        },
        {
            "id": "1-1-04",
            "episode": 1,
            "duration": 13,
            "seed": 41104,
            "description": "水壶内漂着碎汤谱，叶寻将手中高举的四十八张邮政汇款存根重重拍上空桌面打脸四年供读真相，林双双羞愤按单，叶寻双手抓住围裙带准备扯下。",
            "dialogue": "叶寻：我辍学熬四年牛油，四十八张汇款单供你读完大学，两清了！",
            "assetNames": ["沙正街林家食府老店大堂", "叶寻 · 渝清记围裙掌勺", "林双双", "林有才"],
            "ref_images": [kf("1-1-04"), f_ye_apron, f_lin, f_youcai],
            "ref_audios": [v_yexun],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The man on screen-left in <Picture 1> holding the worn tin box in his right hand and raising the thick stack of postal remittance slips in his left hand above the bare tabletop, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2>: The woman standing on screen-right in <Picture 1>, matching <Picture 3>.\n"
                "- <Subject 3>: The older man standing behind <Subject 2> in <Picture 1>, matching <Picture 4>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-8.2s) Medium close-up starting directly from <Picture 1> beside the glass water pitcher filled with floating yellow paper shreds.\n"
                "- [Shot 2] (8.2s-13.0s) Medium two-shot as <Subject 2> flushes and presses the fanned slips while <Subject 1> grabs his neck cloth to pull it off.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-1.8s): <Subject 1> slams the raised thick stack of greenish-pink postal remittance slips in his left hand hard onto the wooden tabletop with a sharp smack, sliding his palm so the slips fan out across the wood.\n"
                "- [Shot 1] (1.9s-8.0s): Locking cold, piercing eyes onto <Subject 2>, <Subject 1> (S1) speaks with forceful clarity: <d>[Chinese] 我辍学熬四年牛油，四十八张汇款单供你读完大学，两清了。</d>\n"
                "- [Shot 2] (8.2s-10.8s): <Subject 2>'s face flushes crimson as she reflexively presses both hands over the fanned remittance slips while <Subject 3> stiffens behind her.\n"
                "- [Shot 2] (10.8s-13.0s): Setting the tin box down, <Subject 1> reaches up decisively with both hands, grabs the white cloth and strap around his neck, and pulls them upward off his shoulders.\n"
                "[Environment]\n"
                "- 2005 Chongqing restaurant wooden table with torn yellow paper floating in the glass pitcher.\n"
                "[Camera & Visuals]\n"
                "- Pure 35mm theatrical cinema photography with completely clean unobstructed lower frame, crisp slam onto bare wood and end-of-shot neck-strap pull.\n"
                "[Audio]\n"
                "- Heavy smack of paper stack hitting wood, firm resonant male Mandarin voice, flustered paper rustle, cloth tug at 11.2s, zero music."
            ),
        },
        {
            "id": "1-1-05",
            "episode": 1,
            "duration": 10,
            "seed": 411059,
            "description": "动作顺接上镜，叶寻将刚扯下的围裙甩进门边竹篓宣布撤火，转身朝左侧大门大步走出画外，林有才在厅内指门怒喊。",
            "dialogue": "叶寻：今晚起火我撤了，看你们拿什么端上桌！\n林有才：忘恩负义的东西！离了林记，这条街谁敢要你？",
            "assetNames": ["沙正街林家食府老店大堂", "叶寻", "林有才", "林双双"],
            "ref_images": [kf("1-1-05"), f_ye_clean, f_youcai, f_lin],
            "ref_audios": [v_yexun, v_youcai],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The man on screen-left in <Picture 1> holding the just-removed brown kitchen cloth at chest height, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The older man on screen-right in <Picture 1>, matching <Picture 3>. Voice matches Audio 2.\n"
                "- <Subject 3>: The woman standing by the remittance-covered table in the center-right background of <Picture 1>, matching <Picture 4>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-10.0s) Single continuous unedited medium shot starting directly from <Picture 1> inside the warm restaurant hall with zero camera cuts.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-1.2s): Continuing his motion smoothly from <Picture 1>, <Subject 1> flings the crumpled brown kitchen cloth and white cloth downward into the bamboo wastebasket at the lower left.\n"
                "- [Shot 1] (1.3s-4.8s): Looking coldly at <Subject 2> and <Subject 3>, <Subject 1> (S1) declares clearly: <d>[Chinese] 今晚起火我撤了，看你们拿什么端上桌。</d>\n"
                "- [Shot 1] (4.9s-9.2s): <Subject 1> turns decisively toward screen-left and strides briskly out of the left edge of the frame toward the front exit, while <Subject 2> (S2) steps forward beside the table pointing angrily toward screen-left and shouting: <d>[Chinese] 忘恩负义的东西，离了林记，这条街谁敢要你。</d> Immediately upon finishing, <Subject 2> closes his lips.\n"
                "- [Shot 1] (9.2s-10.0s): <Subject 2> glares toward screen-left while <Subject 3> stands frozen beside the table with the remittance slips and glass pitcher.\n"
                "[Environment]\n"
                "- Warm-lit 2005 Chongqing restaurant interior beside the wooden table.\n"
                "[Camera & Visuals]\n"
                "- Pure 35mm theatrical cinema photography with completely clean unobstructed lower frame, single continuous camera setup with screen-left exit matching the next shot's right-to-left street crossing.\n"
                "[Audio]\n"
                "- Cloth thudding into bamboo basket, resolute young male voice, brisk footsteps exiting left, furious older male shout, zero music."
            ),
        },
        {
            "id": "1-2-01",
            "episode": 1,
            "duration": 13,
            "seed": 41201,
            "description": "老街空间过街桥：叶寻从右侧林记火锅门前大步跨过6米青石板街走入正对门左侧夏记老火锅，夏芊芊在门厅木桌旁热情迎他掌勺并拿起毛笔。",
            "dialogue": "[VO] 叶寻：前世只有世交芊芊护我到底，这辈子换我撑起夏记！\n夏芊芊：叶爷爷熬汤真传我从小看着！林家瞎了眼，夏记迎你掌勺！",
            "assetNames": ["重庆老街对门双火锅铺街景", "叶寻", "夏芊芊"],
            "ref_images": [kf("1-2-01"), f_ye_clean, f_qian],
            "ref_audios": [v_qian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The man on screen-right in <Picture 1> striding across the narrow bluestone street from the right-hand shop toward the left-hand shop, matching <Picture 2>.\n"
                "- <Subject 2> (S1): The woman standing under the warm left-hand shop eaves in <Picture 1> welcoming him, matching <Picture 3>. Voice matches Audio 1.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-5.2s) Medium-wide street-crossing shot starting directly from <Picture 1> clearly showing <Subject 1> crossing the 6-meter bluestone street from the right shop straight to <Subject 2> at the open left shop.\n"
                "- [Shot 2] (5.2s-13.0s) Medium two-shot right inside the open entrance of the left shop beside a wooden table holding rice paper, a brush, and an inkpad box.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-5.2s): Keeping his lips closed with warm determination, <Subject 1> strides briskly across the lantern-lit bluestone street from the right-hand shop straight up to <Subject 2> waiting warmly under the left-hand shop eaves.\n"
                "- [Shot 2] (5.5s-11.2s): Welcoming <Subject 1> beside the front wooden table inside the open entrance, <Subject 2> (S1) looks at <Subject 1> with bright, unconditional trust and speaks briskly: <d>[Chinese] 叶爷爷熬汤真传我从小看着，林家瞎了眼，夏记迎你掌勺。</d>\n"
                "- [Shot 2] (11.2s-13.0s): <Subject 1> nods warmly as <Subject 2> turns to the wooden table and picks up the writing brush over the sheet of rice paper.\n"
                "[Environment]\n"
                "- Nighttime 2005 Chongqing 6-meter bluestone street with two facing hotpot shops lit by warm lanterns.\n"
                "[Camera & Visuals]\n"
                "- Pure 35mm theatrical cinema photography with completely clean unobstructed lower frame, crystal-clear cross-street geography, <Subject 1>'s lips strictly closed throughout.\n"
                "[Audio]\n"
                "- Brisk footsteps across stone pavement from 0s to 5.2s, warm spirited female Mandarin voice starting at 5.5s, subtle brush pickup at 11.8s, zero music."
            ),
            "vo_custom": {
                "face_1k": f_ye_clean,
                "voice": v_yexun,
                "duration": 6,
                "text": "前世只有世交芊芊护我到底，这辈子换我撑起夏记。",
                "dst_start": 0.25,
                "max_len": 4.8,
            },
        },
        {
            "id": "1-2-02",
            "episode": 1,
            "duration": 13,
            "seed": 41202,
            "description": "顺接门厅木桌，夏芊芊与叶寻站立俯身先后在空白落款处摁下并排红手印立定五五分账契书，门外响起脚步声，两人同时转头迈向门口。",
            "dialogue": "夏芊芊：五五分账，往后咱俩一口锅里搅马勺！",
            "assetNames": ["桂花巷渝清记大堂与天井", "夏芊芊", "叶寻"],
            "ref_images": [kf("1-2-02"), f_qian, f_ye_clean],
            "ref_audios": [v_qian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The woman standing on screen-right behind the wooden table in <Picture 1> dipping her thumb in the red inkpad, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2>: The man standing beside her on screen-left behind the wooden table in <Picture 1>, matching <Picture 3>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.8s) Medium close-up starting directly from <Picture 1> as both stand over the wooden table stamping their red thumbprints onto the contract sheet.\n"
                "- [Shot 2] (4.8s-13.0s) Medium two-shot of <Subject 1> and <Subject 2> standing by the table near the open street doorway (never looking into the camera lens).\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-4.8s): <Subject 1> presses her red-inked right thumb firmly onto the bottom of the handwritten contract sheet; <Subject 2> immediately touches his right thumb to the open red inkpad and presses a second bright red thumbprint right beside hers.\n"
                "- [Shot 2] (5.0s-9.4s): Looking directly at <Subject 2> in profile with a bright smile, <Subject 1> (S1) speaks cheerfully: <d>[Chinese] 五五分账，往后咱俩一口锅里搅马勺。</d>\n"
                "- [Shot 2] (9.5s-13.0s): Sharp footsteps and a mocking chuckle sound just outside the open doorway on screen-right; both <Subject 1> and <Subject 2> immediately stop smiling, turn their heads sharply toward the open doorway on screen-right, and take two brisk steps toward the threshold.\n"
                "[Environment]\n"
                "- Warm lantern-lit front table just inside the open street entrance of Xia's hotpot shop at night.\n"
                "[Camera & Visuals]\n"
                "- Pure 35mm theatrical cinema photography with completely clean unobstructed lower frame, sequential two-person thumbprinting and sharp turn-to-door transition.\n"
                "[Audio]\n"
                "- Two firm thumbprint presses on paper, cheerful female Mandarin voice, approaching leather-shoe footsteps on stone outside at 9.6s, zero music."
            ),
        },
        {
            "id": "1-2-03",
            "episode": 1,
            "duration": 15,
            "seed": 41203,
            "description": "顺接门口朝向，楚南与林双双堵在夏记门槛外嚣张宣布明早断供全部成品牛油，并亮出红纸定单炫耀截胡十二桌庆功席后哄笑离去。",
            "dialogue": "楚南：夏芊芊，敢收他？明早断你夏记全部成品牛油，看你拿什么交房租！\n林双双：你们备好菜的机械厂十二桌席，周厂长刚改签给林记了！",
            "assetNames": ["重庆老街对门双火锅铺街景", "楚南", "林双双", "夏芊芊", "叶寻"],
            "ref_images": [kf("1-2-03"), f_chu, f_lin, f_qian, f_ye_clean],
            "ref_audios": [v_chu, v_lin],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The man holding the mobile phone on screen-right outside the doorway in <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The woman holding the red banquet order slip beside <Subject 1> in <Picture 1>, matching <Picture 3>. Voice matches Audio 2.\n"
                "- <Subject 3>: The woman standing on screen-left at the threshold in <Picture 1>, matching <Picture 4>.\n"
                "- <Subject 4>: The man standing calmly beside <Subject 3> at the threshold in <Picture 1>, matching <Picture 5>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-7.4s) Medium confrontation shot starting directly from <Picture 1> at Xia's lantern-lit doorway.\n"
                "- [Shot 2] (7.4s-15.0s) Medium shot favoring <Subject 2> raising the red order slip before <Subject 3> and <Subject 4>, then turning away with <Subject 1>.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-7.1s): Twirling his mobile phone arrogantly outside the threshold, <Subject 1> (S1) sneers at <Subject 3> and <Subject 4> and speaks loudly: <d>[Chinese] 夏芊芊，敢收他，明早断你夏记全部成品牛油，看你拿什么交房租。</d>\n"
                "- [Shot 2] (7.5s-13.0s): Raising the red paper slip smugly, <Subject 2> (S2) speaks sharply: <d>[Chinese] 你们备好菜的机械厂十二桌席，周厂长刚改签给林记了。</d>\n"
                "- [Shot 2] (13.0s-15.0s): <Subject 1> laughs smugly and walks away down the bluestone street arm-in-arm with <Subject 2>, leaving <Subject 3> and <Subject 4> standing outside the doorway.\n"
                "[Environment]\n"
                "- Nighttime lantern-lit 2005 Chongqing bluestone street outside Xia's doorway.\n"
                "[Camera & Visuals]\n"
                "- Pure 35mm theatrical cinema photography with completely clean unobstructed lower frame, consistent left-right axis and exit.\n"
                "[Audio]\n"
                "- Arrogant male voice, crisp paper rustle, gloating female voice, smug laugh and receding footsteps, zero music."
            ),
        },
        {
            "id": "1-2-04",
            "episode": 1,
            "duration": 13,
            "seed": 412048,
            "description": "顺接门口站位，夏芊芊站在空三轮车旁发愁断油，叶寻跨上车座招呼她上车去屠宰场抢头刀鲜牛板油，夏芊芊随即坐上后车斗双人同框出发。",
            "dialogue": "夏芊芊：成品牛油全断了，明早拿什么开火？\n叶寻：不用陈年老油！上车，去屠宰场抢今晚头刀鲜牛板油！\n夏芊芊：走！我跟你去！",
            "assetNames": ["重庆老街对门双火锅铺街景", "叶寻", "夏芊芊"],
            "ref_images": [kf("1-2-04"), f_ye_clean, f_qian],
            "ref_audios": [v_qian, v_yexun],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S2): The man standing on the bluestone pavement holding the handlebars of the empty parked tricycle on screen-right in <Picture 1>, matching <Picture 2>. Voice matches Audio 2.\n"
                "- <Subject 2> (S1): The woman standing on her feet on the bluestone pavement on screen-left beside the empty tricycle in <Picture 1>, matching <Picture 3>. Voice matches Audio 1.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-8.0s) Medium two-shot starting directly from <Picture 1> outside Xia's shop: <Subject 2> stays standing on the pavement while <Subject 1> swings onto the tricycle saddle and calls her aboard.\n"
                "- [Shot 2] (8.0s-13.0s) Tight medium two-shot keeping both <Subject 1> on the front saddle and <Subject 2> seated right behind him in the wooden rear cart clearly visible together in frame until 13.0s.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-3.2s): Standing on her feet on the bluestone pavement beside the empty tricycle, <Subject 2> (S1) looks anxiously at <Subject 1> and asks: <d>[Chinese] 成品牛油全断了，明早拿什么开火。</d>\n"
                "- [Shot 1] (3.3s-7.9s): While <Subject 2> remains standing on the pavement listening, <Subject 1> (S2) swings his leg onto the tricycle saddle, grips the handlebars, turns his head toward <Subject 2>, and speaks briskly: <d>[Chinese] 不用陈年老油，上车，去屠宰场抢今晚头刀鲜牛板油。</d>\n"
                "- [Shot 2] (8.1s-10.4s): <Subject 2>'s eyes light up as she steps up and sits securely inside the wooden rear cart right behind <Subject 1>, gripping both wooden side rails and calling out: <d>[Chinese] 走，我跟你去。</d>\n"
                "- [Shot 2] (10.4s-13.0s): With <Subject 2> remaining clearly seated in the wooden rear cart smiling right behind <Subject 1>'s back, <Subject 1> pedals the tricycle steadily forward along the warm lantern-lit bluestone street.\n"
                "[Environment]\n"
                "- Nighttime 2005 Chongqing bluestone street outside Xia's doorway under warm lanterns.\n"
                "[Camera & Visuals]\n"
                "- Pure 35mm theatrical cinema photography with completely clean unobstructed lower frame; both <Subject 1> and <Subject 2> stay fully preserved together on the tricycle through the final frame.\n"
                "[Audio]\n"
                "- Urgent female question, metallic creak of saddle mount, confident young male reply, cheerful female reply, bicycle chain and rolling wheels on stone, zero music."
            ),
        },
    ]


def trim_silence_bounds(wav_or_mp4: Path) -> tuple[float, float]:
    probe = json.loads(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(wav_or_mp4)],
        text=True,
    ))
    dur = float(probe["format"]["duration"])
    proc = subprocess.run(
        ["ffmpeg", "-i", str(wav_or_mp4), "-af", "silencedetect=noise=-36dB:d=0.20", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    starts = [float(x) for x in re.findall(r"silence_start:\s*([0-9.]+)", proc.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end:\s*([0-9.]+)", proc.stderr)]
    s0 = 0.05
    if starts and starts[0] < 0.15 and ends:
        s0 = max(0.0, ends[0] - 0.06)
    e0 = dur - 0.05
    if starts and starts[-1] > s0 + 0.5:
        last_s = starts[-1]
        if not ends or ends[-1] < last_s:
            e0 = min(dur, last_s + 0.12)
    return round(s0, 3), round(max(s0 + 0.4, e0), 3)


def gen_dry_vo_4070(out_mp4: Path, face_1k: Path, voice_wav: Path, text: str, dur: int, seed: int):
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


def run_one_shot(spec: dict, force: bool = False):
    sid = spec["id"]
    sdir = TAKES_EP1 / sid
    sdir.mkdir(parents=True, exist_ok=True)
    final_mp4 = sdir / "video.mp4"
    final_meta = sdir / "video.json"
    if final_mp4.is_file() and final_meta.is_file() and not force:
        print(f"[skip] {sid} already exists", flush=True)
        return

    vc = spec.get("vo_custom")
    if not vc:
        pika_runner.run_shot(spec, TAKES_EP1, CACHE_1K, resolution="480p", force=force)
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

    ss, se = trim_silence_bounds(vo_mp4)
    raw_dur = se - ss
    atempo_str = ""
    if raw_dur > float(vc["max_len"]):
        ratio = min(1.25, raw_dur / float(vc["max_len"]))
        atempo_str = f"atempo={ratio:.3f},"
        eff_dur = raw_dur / ratio
    else:
        eff_dur = raw_dur

    end_mute = float(vc["dst_start"]) + eff_dur + 0.12
    tmp = final_mp4.with_suffix(".tmp.mp4")
    filt = (
        f"[0:a]aresample=48000,volume='if(between(t,0,{end_mute:.3f}),0.08,1.0)':eval=frame[base];"
        f"[1:a]aresample=48000,atrim={ss:.3f}:{se:.3f},asetpts=PTS-STARTPTS,{atempo_str}"
        f"afade=t=in:d=0.06,afade=t=out:st={max(0.0, eff_dur - 0.08):.3f}:d=0.08,"
        f"volume=1.65,adelay={int(round(float(vc['dst_start']) * 1000))}:all=1[vo];"
        f"[base][vo]amix=inputs=2:duration=first:normalize=0[a]"
    )
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-i", str(base_mp4), "-i", str(vo_mp4),
        "-filter_complex", filt, "-map", "0:v", "-map", "[a]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(tmp),
    ], check=True)
    tmp.replace(final_mp4)
    meta["vo_custom_applied"] = {"src": [ss, se], "eff_dur": round(eff_dur, 3), "dst_start": vc["dst_start"], "vo_headers": vo_hdr}
    final_meta.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[done+vo_custom] {sid} -> VO [{ss}..{se}] (eff {eff_dur:.2f}s) placed at {vc['dst_start']}s", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kf-only", action="store_true")
    ap.add_argument("--videos-only", action="store_true")
    ap.add_argument("--only", action="append", default=[])
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    amap = json.loads((PREV_WORK / "asset_map.json").read_text(encoding="utf-8"))
    ep1 = build_ep1_plan(amap)
    (WORK_DIR / "ep01_v4_plan.json").write_text(json.dumps(ep1, ensure_ascii=False, indent=2), encoding="utf-8")

    issues = []
    for s in ep1:
        issues.extend(pika_runner.lint_zero_appearance(s["prompt"], s["id"]))
    if issues:
        print("LINT FAILED:\n" + "\n".join(issues), file=sys.stderr)
        sys.exit(2)
    print(f"LINT PASSED: 0 issues across {len(ep1)} Ep1 v4 seamless shots!", flush=True)

    if not args.videos_only:
        generate_chained_keyframes(amap, force=args.force)
    if args.kf_only:
        return

    targets = ep1
    if args.only:
        only_set = set(args.only)
        targets = [s for s in ep1 if s["id"] in only_set]

    for s in targets:
        run_one_shot(s, force=args.force)

    if not args.only:
        vids = [(s["id"], TAKES_EP1 / s["id"] / "video.mp4") for s in ep1]
        check_transitions.build_transition_sheet(vids, WORK_DIR / "ep01_v4_transitions.jpg")


if __name__ == "__main__":
    main()
