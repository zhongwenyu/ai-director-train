#!/usr/bin/env python3
"""
Pre-compress all Episode 2 & Episode 3 assets to <=1K (keeping 2K originals untouched in studio_media),
and generate all 2K/1K blocking keyframes for Episode 2 (10 groups) & Episode 3 (9 groups)
following:
  1. <=1K compression invariant for video inputs
  2. Zero-appearance-text rule (no clothing/hair/age words; 100% locked to character #front refs)
  3. t=0.0s Initial Presence Set conservation law (never draw late-entering characters into t=0s frame)
"""
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from PIL import Image, ImageDraw

STUDIO_BRIDGE = Path("/home/zhongwenyu/project/playlets-studio/skills/studio-bridge/scripts")
SKILL_SCRIPTS = Path("/home/zhongwenyu/project/ai-director-train/.agents/skills/hit-video/scripts")
sys.path.insert(0, str(STUDIO_BRIDGE))
sys.path.insert(0, str(SKILL_SCRIPTS))

import vtrix_image  # noqa: E402
from compress_1k import compress_image_to_1k  # noqa: E402

PROJ_DIR = Path("/home/zhongwenyu/project/playlets-studio/playlets/playlet-mwj57ecn-9658ad48")
MEDIA_DIR = PROJ_DIR / "media"
WORK_DIR = Path("/home/zhongwenyu/project/ai-director-train/productions/2005_chongqing_hotpot/ep02_03_video_gen")
ASSETS_1K = WORK_DIR / "assets_1k"
KF_2K = WORK_DIR / "keyframes_2k"
KF_1K = WORK_DIR / "keyframes_1k"

for d in (ASSETS_1K, KF_2K, KF_1K):
    d.mkdir(parents=True, exist_ok=True)


def find_media_file(mid: str) -> Path:
    for ext in (".png", ".jpg", ".jpeg", ".webp", ".wav", ".mp3", ".mp4"):
        p = MEDIA_DIR / f"{mid}{ext}"
        if p.is_file():
            return p
    matches = list(MEDIA_DIR.glob(f"{mid}.*"))
    if matches:
        return matches[0]
    raise FileNotFoundError(f"Media file not found for id={mid}")


def build_asset_map() -> dict:
    proj = json.loads((PROJ_DIR / "project.json").read_text(encoding="utf-8"))
    needed_names = {
        "叶寻",
        "叶寻 · 渝清记围裙掌勺",
        "夏芊芊",
        "夏建国",
        "刘大厨",
        "苏晴",
        "林双双",
        "周有福",
        "沙正街遮雨穿堂私廊与桂花巷口",
        "桂花巷渝清记大堂与天井",
        "渝清记后厨猛火灶间",
        "渝清记深夜账房",
        "青花瓷小罐川贝梨膏",
        "《叶氏本草食单》蓝布线装册",
        "桂花巷18000元房租催缴单",
        "9·19手写合伙及秘方公证协议",
    }
    amap = {}
    for a in proj["assets"]:
        if a["name"] not in needed_names or not a.get("imageId"):
            continue
        entry = {"id": a["id"], "type": a["type"], "imageId": a["imageId"]}
        main_src = find_media_file(a["imageId"])
        main_1k = ASSETS_1K / f"{a['id']}_main_1k.png"
        if not main_1k.is_file():
            compress_image_to_1k(main_src, main_1k, max_side=1024)
        entry["main_2k"] = str(main_src)
        entry["main_1k"] = str(main_1k)

        if a.get("frontImageId"):
            front_src = find_media_file(a["frontImageId"])
            front_1k = ASSETS_1K / f"{a['id']}_front_1k.png"
            if not front_1k.is_file():
                compress_image_to_1k(front_src, front_1k, max_side=1024)
            entry["front_2k"] = str(front_src)
            entry["front_1k"] = str(front_1k)

        if a.get("voiceSampleId"):
            entry["voice"] = str(find_media_file(a["voiceSampleId"]))
        amap[a["name"]] = entry

    (WORK_DIR / "asset_map.json").write_text(json.dumps(amap, ensure_ascii=False, indent=2), encoding="utf-8")
    return amap


STYLE_TAIL = (
    "明亮清晰电影实拍质感，竖屏9:16构图，自然真实光影与皮肤衣料纹理，人物与桌椅比例真实准确，"
    "严禁出现任何文字、字幕、水印、分格边框或纯白拼图底。"
)


def make_specs(amap: dict) -> list:
    specs = [
        # ==================== EPISODE 2 ====================
        {
            "id": "2-1-01",
            "refs": [
                amap["沙正街遮雨穿堂私廊与桂花巷口"]["main_1k"],
                amap["叶寻"]["front_1k"],
                amap["夏芊芊"]["front_1k"],
            ],
            "prompt": (
                "以图1的两侧青砖夹墙、头顶半透明波浪瓦的1.8米宽傍晚遮雨穿堂窄廊为环境，严格保持图2年轻男子与图3年轻女孩的五官、发型及整套穿搭与各自参考图完全一致。"
                "中景平视正面迎面构图：傍晚橘金斜阳透过波浪瓦照入窄廊，画面左侧图2男子双手紧握装满干辣椒麻袋的旧木板车车把正快步向前奔跑，左肩斜挎一只洗白军绿帆布挎包；"
                "画面右侧图3女孩手挽一只竹编小篮紧随其侧快步同行，两人神色紧迫专注直视前方廊口，脚下是微湿的青石板地面。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-1-07",
            "refs": [
                amap["桂花巷渝清记大堂与天井"]["main_1k"],
                amap["夏芊芊"]["front_1k"],
            ],
            "prompt": (
                "以图1的老式原木算盘柜台为背景材质，保持图2女孩手部袖口质感一致。"
                "高机位俯拍桌面抽屉特写构图：老式原木柜台的木抽屉刚刚拉开一半，抽屉里平放着一本深红色储蓄存折（无清晰可读文字），存折底下压着一叠整洁的红色百元纸币；"
                "图2女孩白皙干净的双手伸进抽屉，正利落地从存折下抽出几张百元纸币清点，柜台桌沿可见半截木算盘，暖黄钨丝灯光柔和真实。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-1-10",
            "refs": [
                amap["桂花巷渝清记大堂与天井"]["main_1k"],
                amap["叶寻 · 渝清记围裙掌勺"]["front_1k"],
                amap["夏建国"]["front_1k"],
            ],
            "prompt": (
                "以图1的桂花巷原木方桌小馆大堂与左侧算盘木柜台为场景，严格保持图2年轻男子与图3中年男子的五官、发型及整套穿搭（含图3右手腕白色绷带）与各自参考图完全一致。"
                "中近景平视双人对话构图：暖黄灯光下，图2年轻男子站在画面左侧柜台旁面朝右侧，神情沉着笃定；"
                "图3中年男子站在画面右侧面向图2，右手腕缠着白色绷带，脸上带着惊讶与询问的神色，两人身后可见小馆原木餐桌与天井绿植。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-1-13",
            "refs": [
                amap["桂花巷渝清记大堂与天井"]["main_1k"],
                amap["苏晴"]["front_1k"],
            ],
            "prompt": (
                "以图1的小馆靠窗原木方桌区域为场景，严格保持图2年轻女大学生的五官、发型与整套穿搭和参考图完全一致。"
                "中近景平视偏侧构图：傍晚暖黄灯光下，图2女大学生站在右侧靠窗的原木方桌旁（桌上仅放着两只粗陶茶杯，尚未上菜），"
                "她右手拎着一只浅色帆布单肩书包，正微微低头看自己左手腕上的手表，神情干练中透着赶时间的焦急，同桌后方虚化坐着一名女同学。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-2-01",
            "refs": [
                amap["渝清记后厨猛火灶间"]["main_1k"],
                amap["叶寻 · 渝清记围裙掌勺"]["front_1k"],
            ],
            "prompt": (
                "以图1的传统川菜小馆后厨猛火铁锅灶台为场景，严格保持图2年轻男子的五官、发型与整套穿搭和参考图完全一致。"
                "近景斜俯灶前掌勺构图：灶膛橙蓝猛火映亮大铁锅，图2年轻男子站在画面左侧灶位前，光洁无疤的右手稳握长柄铁勺，"
                "正在大铁锅内用琥珀色牛油与清亮梨汁慢火轻煸刚沥干的红亮干辣椒（锅面温润清亮，仅有轻柔水汽而无刺鼻浓黑油烟），右侧木案台上备有一只干净黑陶砂煲与白瓷碗。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-2-04",
            "refs": [
                amap["渝清记后厨猛火灶间"]["main_1k"],
                amap["叶寻 · 渝清记围裙掌勺"]["front_1k"],
                amap["夏芊芊"]["front_1k"],
            ],
            "prompt": (
                "以图1的后厨出菜木案台与门帘口为场景，严格保持图2年轻男子与图3年轻女孩的五官、发型及整套穿搭与各自参考图完全一致。"
                "近景平视双人交接构图：后厨暖光与蒸汽中，画面左侧图2年轻男子双手稳稳端着一只垫有隔热布的木托盘（托盘上一只黑陶砂煲正冒着奶白微红醇汤的热气），"
                "正向画面右侧递给图3年轻女孩；图3女孩双手稳稳接住木托盘边缘，眉眼含笑准备转身端往外堂。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-2-07",
            "refs": [
                amap["桂花巷渝清记大堂与天井"]["main_1k"],
                amap["叶寻 · 渝清记围裙掌勺"]["front_1k"],
                amap["夏芊芊"]["front_1k"],
            ],
            "prompt": (
                "以图1的小馆原木算盘柜台与暖黄吊灯大堂为场景，严格保持图2年轻男子与图3年轻女孩的五官、发型及整套穿搭与各自参考图完全一致。"
                "近景平视柜台双人构图：夜晚温馨暖黄灯光下，图2年轻男子站在左侧木柜台内双手自然扶着柜台木沿，神情温和沉稳地看向右前方食客方向；"
                "图3年轻女孩并肩站在他右侧半步处，手边放着木算盘，嘴角带着欣慰明朗的笑意。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-2-10",
            "refs": [
                amap["桂花巷渝清记大堂与天井"]["main_1k"],
                amap["苏晴"]["front_1k"],
                amap["林双双"]["front_1k"],
            ],
            "prompt": (
                "以图1的小馆敞开双扇老木门入口为场景，严格保持图2女大学生与图3年轻女子的五官、发型及整套穿搭与各自参考图完全一致。"
                "中景平视门口迎面错身构图：夜晚小馆门灯暖光下，画面左侧门内图2女大学生背着浅色帆布书包面带满意微笑正朝右侧门外迈步走出；"
                "画面右侧门槛处，图3年轻女子左手紧攥一本牛皮纸旧账本、右手拎着一串沉甸甸的后厨铁钥匙正冷着脸朝门内跨入，两人恰好在木门槛处一出一进迎面错身。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-2-13",
            "refs": [
                amap["桂花巷渝清记大堂与天井"]["main_1k"],
                amap["林双双"]["front_1k"],
            ],
            "prompt": (
                "以图1的小馆门边原木方桌与夜晚大堂为场景，严格保持图2年轻女子的五官、发型与整套穿搭和参考图完全一致。"
                "近景略仰压迫感构图：画面右侧偏中，图2年轻女子立于门边原木方桌旁面向左前方，下巴微扬神色高傲冰冷，左手将一本牛皮纸旧账本紧贴在身前，"
                "下前景原木桌面一角清晰平放着一串刚拍下的油亮后厨铁钥匙。" + STYLE_TAIL
            ),
        },

        # ==================== EPISODE 3 ====================
        {
            "id": "3-1-01",
            "refs": [
                amap["桂花巷渝清记大堂与天井"]["main_1k"],
                amap["叶寻 · 渝清记围裙掌勺"]["front_1k"],
                amap["林双双"]["front_1k"],
                amap["夏建国"]["front_1k"],
            ],
            "prompt": (
                "以图1的夜晚小馆原木大堂与左侧算盘柜台为场景，严格保持图2年轻男子、图3年轻女子与图4中年男子的五官、发型及整套穿搭与各自参考图完全一致。"
                "中近景平视对峙构图：暖黄钨丝灯光下，画面左侧图2年轻男子刚从木柜台口从容迈步走出站定，神色平静无波地直视右侧；"
                "画面右侧门边原木方桌旁，图3年轻女子双臂环抱胸前下巴微扬，带着傲慢施舍的神态斜睨图2（桌角放着牛皮纸账本与铁钥匙串）；左后景柜台内虚化可见图4中年男子关切注视。" + STYLE_TAIL
            ),
        },
        {
            "id": "3-1-04",
            "refs": [
                amap["桂花巷渝清记大堂与天井"]["main_1k"],
                amap["叶寻 · 渝清记围裙掌勺"]["front_1k"],
            ],
            "prompt": (
                "以图1的小馆原木方桌面为背景，保持图2年轻男子手部与深色袖口一致。"
                "桌面斜俯特写构图：暖黄灯光下的原木方桌面上平放着一本深棕色牛皮纸旧账本（封皮无乱码文字）；"
                "画面左侧伸出图2年轻男子光洁无疤的右手，正平稳干脆地将一串沉甸甸的后厨铁钥匙放在牛皮纸账本封皮正中央，动作克制利落。" + STYLE_TAIL
            ),
        },
        {
            "id": "3-1-07",
            "refs": [
                amap["桂花巷渝清记大堂与天井"]["main_1k"],
                amap["林双双"]["front_1k"],
                amap["夏芊芊"]["front_1k"],
                amap["叶寻 · 渝清记围裙掌勺"]["front_1k"],
            ],
            "prompt": (
                "以图1的夜晚小馆敞开老木门旁为场景，严格保持图2年轻女子、图3女孩与图4年轻男子的五官、发型及整套穿搭与各自参考图完全一致。"
                "中近景平视对峙构图：画面右侧图2年轻女子脸色铁青气急败坏地盯着左侧；"
                "画面左侧老木门边，图3女孩身姿挺直站在左中位置，右手稳稳扶住半扇敞开的老木门边缘，神情温婉却硬气坚定地迎视对方，图4年轻男子并肩立于图3左后半步处。" + STYLE_TAIL
            ),
        },
        {
            "id": "3-1-09",
            "refs": [
                amap["桂花巷渝清记大堂与天井"]["main_1k"],
                amap["林双双"]["front_1k"],
            ],
            "prompt": (
                "以图1的夜晚小馆门边原木方桌与敞开木门为场景，严格保持图2年轻女子的五官、发型与整套穿搭和参考图完全一致。"
                "近景平视构图：画面右侧偏中，图2年轻女子站在原木方桌旁面向左侧，右手正一把将桌上的铁钥匙串与牛皮纸账本死死抓起攥在掌心，嘴角扯出一抹咬牙切齿的冰冷讥笑。" + STYLE_TAIL
            ),
        },
        {
            "id": "3-2-01",
            "refs": [
                amap["渝清记深夜账房"]["main_1k"],
                amap["夏建国"]["front_1k"],
                amap["叶寻 · 渝清记围裙掌勺"]["front_1k"],
                amap["桂花巷18000元房租催缴单"]["main_1k"],
            ],
            "prompt": (
                "以图1的深夜绿罩黄铜台灯原木账桌为场景，严格保持图2中年男子（右手腕缠白绷带）与图3年轻男子的五官、发型及整套穿搭与各自参考图完全一致。"
                "中近景平视围坐夜谈构图（标准75cm高账桌位于人物腰腹高度，完整露出双肩与上半身）：台灯暖黄光晕下，图2中年男子坐在账桌右侧内侧，未受伤的左手按着桌面上一张与图4一致的盖红章白纸催缴单，眉头深锁面露愧疚；"
                "图3年轻男子坐在账桌左侧面向图2，怀旁放着洗白军绿帆布挎包，眼神清亮笃定。" + STYLE_TAIL
            ),
        },
        {
            "id": "3-2-04",
            "refs": [
                amap["渝清记深夜账房"]["main_1k"],
                amap["夏芊芊"]["front_1k"],
                amap["9·19手写合伙及秘方公证协议"]["main_1k"],
            ],
            "prompt": (
                "以图1的深夜绿罩黄铜台灯原木账桌为场景，严格保持图2年轻女孩的五官、发型与整套穿搭和参考图完全一致。"
                "近景微俯执笔立约构图（桌面位于人物腰腹之上，完整露出上半身与双臂）：暖黄台灯光下，图2女孩端坐账桌前，面前摆着木算盘、一本摊开的红皮储蓄存折与一叠与图3质感一致的方格信纸，"
                "她右手握着一支黑色金属钢笔正专注郑重地在方格信纸上工整疾书，神情清澈坚毅。" + STYLE_TAIL
            ),
        },
        {
            "id": "3-2-07",
            "refs": [
                amap["渝清记深夜账房"]["main_1k"],
                amap["叶寻 · 渝清记围裙掌勺"]["front_1k"],
                amap["夏芊芊"]["front_1k"],
                amap["夏建国"]["front_1k"],
            ],
            "prompt": (
                "以图1的深夜绿罩黄铜台灯原木账桌为场景，严格保持图2年轻男子、图3年轻女孩与图4中年男子的五官、发型及整套穿搭与各自参考图完全一致。"
                "中近景平视三人围坐构图（标准桌高75cm，三人上半身完整清晰）：暖黄台灯光聚焦桌面一张写满蓝黑钢笔字的方格信纸与一盒敞开的鲜红圆铁盒印泥；"
                "左侧图2年轻男子低头看着信纸猛然怔住抬头望向对面，眼底满是震动与暖意；右侧图3女孩握着钢笔坦荡温婉地直视他；中后侧图4中年男子欣慰含笑。" + STYLE_TAIL
            ),
        },
        {
            "id": "3-2-10",
            "refs": [
                amap["渝清记深夜账房"]["main_1k"],
                amap["9·19手写合伙及秘方公证协议"]["main_1k"],
            ],
            "prompt": (
                "以图1的暖黄台灯原木账桌面与红印泥盒为背景，参照图2的手写方格信纸质感（画面中严禁提前出现无关人物）。"
                "高机位垂直俯拍桌面特写构图：暖黄台灯光下，写有工整钢笔字迹的方格信纸末尾已并排印着两枚鲜红指印，旁边敞开着红色印泥盒；"
                "一只年轻女孩白皙的右手大拇指蘸着鲜红印泥，正稳稳按在纸尾第三处签名位置落下第三枚鲜红手印，契约仪式感极强。" + STYLE_TAIL
            ),
        },
        {
            "id": "3-2-13",
            "refs": [
                amap["桂花巷渝清记大堂与天井"]["main_1k"],
                amap["周有福"]["front_1k"],
                amap["夏建国"]["front_1k"],
                amap["叶寻 · 渝清记围裙掌勺"]["front_1k"],
            ],
            "prompt": (
                "以图1的夜晚小馆原木账桌与大堂为场景，严格保持图2花白寸头房东、图3中年男子与图4年轻男子的五官、发型及整套穿搭（含图2腰间铜钥匙串、图3右腕白绷带）与各自参考图完全一致。"
                "中近景平视逼宫对峙构图：夜晚暖黄灯光下，画面右侧图2房东微俯身站在账桌右角，右手重重按着桌角一把沉甸甸的暗红色重型铁管钳，左手捏着一张白纸收条朝左侧比划，满脸市侩强势；"
                "画面左侧账桌旁，图3中年男子与图4年轻男子并肩面对他，气氛剑拔弩张。" + STYLE_TAIL
            ),
        },
    ]

    if "刘大厨" in amap and "front_1k" in amap["刘大厨"]:
        specs.insert(1, {
            "id": "2-1-04",
            "refs": [
                amap["桂花巷渝清记大堂与天井"]["main_1k"],
                amap["夏建国"]["front_1k"],
                amap["刘大厨"]["front_1k"],
            ],
            "prompt": (
                "以图1的小馆原木算盘柜台与傍晚大堂为场景，严格保持图2中年男子（右腕缠白绷带）与图3敦实男厨师（斜背黑帆布厨刀包）的五官、发型及整套穿搭与各自参考图完全一致。"
                "中景平视柜台对峙构图：画面左侧原木算盘柜台前，图2中年男子额头冒汗、抬起未受伤的左手焦急恳求挽留；"
                "画面右中位置，图3敦实男厨师左肩斜背黑色帆布厨刀包堵在柜台前，双臂环抱满脸势利冷漠与不耐烦。" + STYLE_TAIL
            ),
        })
    return specs


def build_contact_sheet(ids: list, out_jpg: Path):
    cols = 5
    rows = (len(ids) + cols - 1) // cols
    tw, th = 320, 568
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


def run_one(sp: dict):
    kid = sp["id"]
    out_2k = KF_2K / f"{kid}.png"
    out_1k = KF_1K / f"{kid}_1k.png"
    if out_2k.is_file() and out_1k.is_file():
        with Image.open(out_1k) as im:
            return kid, 0.0, im.size
    t0 = time.time()
    vtrix_image.generate_vtrix_image(
        prompt=sp["prompt"],
        out_path=out_2k,
        ref_files=sp["refs"],
        aspect_ratio="9:16",
        resolution="2K",
    )
    info = compress_image_to_1k(out_2k, out_1k, max_side=1024)
    return kid, round(time.time() - t0, 1), info["new_size"]


def main():
    amap = build_asset_map()
    print(f"Prepared {len(amap)} <=1K assets in {ASSETS_1K} (Liu present={'刘大厨' in amap})", flush=True)
    specs = make_specs(amap)
    print(f"Generating {len(specs)} 2K/1K keyframes with 5 parallel workers...", flush=True)
    with ThreadPoolExecutor(max_workers=5) as pool:
        futs = {pool.submit(run_one, s): s["id"] for s in specs}
        for f in as_completed(futs):
            kid, dt, sz = f.result()
            print(f"  [kf] {kid} done in {dt}s -> 1K={sz}", flush=True)

    ep2_ids = [s["id"] for s in specs if s["id"].startswith("2-")]
    ep3_ids = [s["id"] for s in specs if s["id"].startswith("3-")]
    build_contact_sheet(ep2_ids, WORK_DIR / "ep02_keyframes_sheet.jpg")
    build_contact_sheet(ep3_ids, WORK_DIR / "ep03_keyframes_sheet.jpg")
    print("Contact sheets saved!", flush=True)


if __name__ == "__main__":
    main()
