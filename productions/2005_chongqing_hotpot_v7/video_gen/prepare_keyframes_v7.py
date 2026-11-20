#!/usr/bin/env python3
"""
Build complete <=1K asset cache (`asset_map.json`) and generate all 42 primary 2K/1K blocking keyframes
(+ 8 cross-space auxiliary blocking keyframes = 50 keyframes total) for `2005_chongqing_hotpot_v7`
Episodes 1, 2, and 3 (`14` Ep 1 + `12` Ep 2 + `16` Ep 3 = `42` generation groups).

Hard Invariants Enforced (`hit-video`):
  1. Only pass `#front` single-person portraits (NEVER 5-panel sheets) + scene/prop <=1K refs to `vtrix_image`.
  2. Strict `t = 0.0s` Initial Presence Rule: characters entering at `t > 0s` are NEVER prematurely drawn into `t = 0.0s` keyframes.
  3. Zero garment/hat contradictions against studio character `#front` portraits (e.g. Zhao Fan keeps his white double-breasted chef coat + red neckerchief without unreferenced tall hat; Xia Jianguo keeps his dark-navy Chinese chef tunic; Zhou Kai keeps his red-white sporty jacket; Chen Bo keeps his light-grey polo).
  4. Zero text/captions/subtitles/watermarks in all keyframes.
  5. `叶寻` and `叶寻 · 2020研发总厨白服` both bind Demucs-cleaned zero-music `yexun_pure_ref.wav`.
"""
from __future__ import annotations

import json
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List
from PIL import Image, ImageDraw

STUDIO_BRIDGE = Path("/home/zhongwenyu/project/playlets-studio/skills/studio-bridge/scripts")
SKILL_SCRIPTS = Path("/home/zhongwenyu/project/ai-director-train/.agents/skills/hit-video/scripts")
sys.path.insert(0, str(STUDIO_BRIDGE))
sys.path.insert(0, str(SKILL_SCRIPTS))

import vtrix_image  # noqa: E402
from compress_1k import compress_image_to_1k  # noqa: E402

PROJ_DIR = Path("/home/zhongwenyu/project/playlets-studio/playlets/playlet-mwj57ecn-9658ad48")
MEDIA_DIR = PROJ_DIR / "media"
PURE_YEXUN_WAV = Path("/home/zhongwenyu/project/ai-director-train/productions/2005_chongqing_hotpot_v5/video_gen/yexun_pure_ref.wav")

WORK_DIR = Path("/home/zhongwenyu/project/ai-director-train/productions/2005_chongqing_hotpot_v7/video_gen")
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


def build_asset_map() -> Dict[str, Any]:
    proj = json.loads((PROJ_DIR / "project.json").read_text(encoding="utf-8"))
    needed_names = {
        "叶寻",
        "叶寻 · 2020研发总厨白服",
        "林双双",
        "林双双 · 塞纳左岸酒红礼服",
        "楚南",
        "楚南 · 海归并购总监西装",
        "赵帆",
        "夏芊芊",
        "夏建国",
        "周凯",
        "中年食客",
        "双林轩总部顶层试菜厅",
        "集团大厦旋转门雨夜街口",
        "沙正街林家食府老店大堂",
        "重庆老街对门双火锅铺街景",
        "夏氏小厨前厅与传菜口",
        "夏氏小厨后厨猛火炒灶",
        "紫铜子母鸳鸯锅",
        "配方无偿归属确认书与调岗单",
    }
    amap: Dict[str, Any] = {}
    for a in proj["assets"]:
        if a["name"] not in needed_names or not a.get("imageId"):
            continue
        entry: Dict[str, Any] = {"id": a["id"], "type": a["type"], "imageId": a["imageId"]}
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

    # Copy Demucs-cleaned zero-music reference for Ye Xun into v7 workdir
    local_ye_wav = WORK_DIR / "yexun_pure_ref.wav"
    if not local_ye_wav.is_file():
        shutil.copy2(PURE_YEXUN_WAV, local_ye_wav)
    amap["叶寻"]["voice"] = str(local_ye_wav)
    amap["叶寻 · 2020研发总厨白服"]["voice"] = str(local_ye_wav)
    amap["林双双 · 塞纳左岸酒红礼服"]["voice"] = amap["林双双"]["voice"]
    amap["楚南 · 海归并购总监西装"]["voice"] = amap["楚南"]["voice"]

    # Bind clean 2.62s middle-aged male voice to 中年食客 (Chen Bo)
    amap["中年食客"]["voice"] = str(find_media_file("d7b6d049-8fbc-4f8c-9855-2445a9d4d7a0"))

    # Aliases matching storyboard catalog names
    amap["混混"] = dict(amap["周凯"])
    amap["陈伯"] = dict(amap["中年食客"])

    (WORK_DIR / "asset_map.json").write_text(json.dumps(amap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return amap


STYLE_TAIL = (
    "精致35mm电影实拍质感，竖屏9:16构图，真实光影层次与皮肤衣料纹理，严格保持对应参考图人物五官、发型与整套服装完全一致，"
    "人物视线方向与空间透视准确，画面干净无任何文字、字幕、花字、标牌乱码、Logo或水印。"
)


def build_keyframe_specs(amap: Dict[str, Any]) -> List[Dict[str, Any]]:
    sc_banquet = amap["双林轩总部顶层试菜厅"]["main_1k"]
    sc_rain = amap["集团大厦旋转门雨夜街口"]["main_1k"]
    sc_lin = amap["沙正街林家食府老店大堂"]["main_1k"]
    sc_street = amap["重庆老街对门双火锅铺街景"]["main_1k"]
    sc_xia_hall = amap["夏氏小厨前厅与传菜口"]["main_1k"]
    sc_xia_kitch = amap["夏氏小厨后厨猛火炒灶"]["main_1k"]

    p_pot = amap["紫铜子母鸳鸯锅"]["main_1k"]
    p_doc = amap["配方无偿归属确认书与调岗单"]["main_1k"]

    c_ye_2020 = amap["叶寻 · 2020研发总厨白服"]["front_1k"]
    c_lin_banq = amap["林双双 · 塞纳左岸酒红礼服"]["front_1k"]
    c_chu_exec = amap["楚南 · 海归并购总监西装"]["front_1k"]

    c_ye = amap["叶寻"]["front_1k"]
    c_lin = amap["林双双"]["front_1k"]
    c_chu = amap["楚南"]["front_1k"]
    c_zhao = amap["赵帆"]["front_1k"]
    c_qian = amap["夏芊芊"]["front_1k"]
    c_jianguo = amap["夏建国"]["front_1k"]
    c_thug = amap["混混"]["front_1k"]
    c_chenbo = amap["陈伯"]["front_1k"]

    return [
        # ==================== EPISODE 1 (14 PRIMARY + 1 AUX) ====================
        {
            "id": "1-1-01", "ep": 1,
            "refs": [sc_banquet, c_ye_2020, c_lin_banq, p_doc],
            "prompt": (
                "以图1高档餐饮集团顶层包厢为背景，右前景虚化多层香槟塔折射暖金与冷紫庆功灯光，圆桌南侧斜平视中近景。"
                "左侧站着与图2五官发型服装完全一致的男子，左手扶桌沿、沾着红印泥的右手拇指刚从桌面图4样式的纸质确认书签章处抬起；"
                "右侧站着与图3五官发型服装完全一致的女子，神色冷利，正伸出右手一把抓向桌面确认书准备抽走，桌边托盘上放着一顶金色镶边礼仪主厨帽。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-1-04", "ep": 1,
            "refs": [sc_banquet, c_ye_2020, c_chu_exec],
            "prompt": (
                "以图1高档庆功包厢为背景，圆桌南侧偏左中景。左侧与图2五官发型服装完全一致的男子静立在餐椅左旁沉脸注视右侧，餐椅靠背上搭着一块洗得发白的旧棉布围布，椅脚旁地面放着一只敞口金属垃圾桶；"
                "右侧与图3五官发型服装完全一致的男子左手插在裤兜里刚走近餐椅旁，正嫌恶地皱鼻低头准备伸出右手两根手指去拈椅背上的旧围布。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-1-07", "ep": 1,
            "refs": [sc_banquet, c_ye_2020],
            "prompt": (
                "以图1高档庆功包厢虚化香槟塔暖金光斑为背景，正面偏右斜角近景。与图2五官发型服装完全一致的男子居画面左中，左胸前挂着一枚带挂绳的金属工牌，"
                "他眉头紧锁、身体微向前倾，眼神焦灼恳切地直视画面右前方准备开口争辩。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-1-10", "ep": 1,
            "refs": [sc_banquet, c_ye_2020, c_lin_banq, p_doc],
            "prompt": (
                "以图1高档庆功包厢为背景，侧面平视双人胸上中近景，下沿可见圆桌边缘。左侧与图2五官发型服装完全一致的男子胸前挂着金属工牌、双臂自然垂侧静立；"
                "右侧与图3五官发型服装完全一致的女子近距面对他，左臂弯夹着黑色文件夹，右手捏着一张图4样式的白纸调岗单正抬手准备拍向男子左胸口，神色居高临下。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-1-13", "ep": 1,
            "refs": [sc_banquet, c_ye_2020],
            "prompt": (
                "以图1高档包厢地面与圆桌边为背景，斜俯拍局部特写近景。左前景为与图2服装一致的男子垂在身侧的左手与袖口，五指微张绷紧正要死死攥拳；"
                "右后景地面敞口垃圾桶内清楚团着那块洗得发白的旧棉布围布。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-2-01", "ep": 1,
            "refs": [sc_rain, c_ye_2020],
            "prompt": (
                "以图1暗夜倾盆暴雨中的高楼外积水柏油长街为背景，街侧平视纵深全景，雨幕密集，积水路面映出冷蓝路灯与霓虹。"
                "与图2五官发型服装完全一致的男子浑身湿透、头发贴额，低垂着头失魂落魄地刚从左后方路沿迈步踩进马路中央积水里，右手按在胸前衣袋位置，右侧车道空旷尚无车辆。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-3-01", "ep": 1,
            "refs": [sc_lin, c_ye],
            "prompt": (
                "以图1老式重庆小饭馆白昼大堂为背景，顶部可见老旧绿漆铁叶吊扇，午后阳光斜照，方木桌南侧偏右斜拍中近景。"
                "与图2五官发型服装完全一致的年轻男子正俯身趴在油腻的方木桌上沉睡未醒，他左腿旁的木长凳上放着一只拉链半敞的洗旧军绿色帆布书包，包口隐约露出一角麻绳扎口的粗布香料包。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-3-04", "ep": 1,
            "refs": [sc_lin, c_ye],
            "prompt": (
                "以图1老式重庆小饭馆白昼大堂虚化斑驳墙面与木窗光影为背景，正面偏右斜角胸上近景。"
                "与图2五官发型服装完全一致的年轻男子坐在方木桌左侧长凳上，午后热光打亮侧脸，他刚抬起头怔怔望向画面右前方，双唇轻抿完全闭合，眼神由惊愕初醒渐转冷冽清醒。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-3-06", "ep": 1,
            "refs": [sc_lin, c_chu, c_lin, c_ye],
            "prompt": (
                "以图1空无一客的老式小饭馆大堂纵深（后景五六张空方木桌）为背景，方桌南侧偏左中景。"
                "右前景桌边，与图2五官发型服装完全一致的年轻男子靠坐木椅，右手握着一只红色冰可乐易拉罐正前倾准备重重顿在油腻木桌上；"
                "他左旁站着与图3五官发型服装完全一致的年轻女子，桌面摊着半张手绘平面草图；左边缘可见坐在长凳上的图4年轻男子侧影。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-3-09", "ep": 1,
            "refs": [sc_lin, c_chu],
            "prompt": (
                "以图1老式小饭馆白昼大堂为背景，微仰斜角近景。与图2五官发型服装完全一致的年轻男子居画面右中后仰靠坐木椅上，前侧桌沿立着一只空可乐罐，"
                "他满脸自得挑眉仰看画面左上方，正抬起右手准备拍向自己胸口包揽炫耀。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-3-11", "ep": 1,
            "refs": [sc_lin, c_ye],
            "prompt": (
                "以图1老式小饭馆木长凳与方桌边为背景，斜俯拍近景特写。木长凳上立着一只洗旧的军绿色帆布书包，包口拉链半敞露出一线麻绳粗布香料包，"
                "与图2服装一致的年轻男子左手按稳书包左端、右手拇指食指捏住左侧金属拉链头，正准备从左向右一把拉死拉链。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-3-12_aux", "ep": 0,
            "refs": [sc_lin, c_ye, c_lin, c_chu],
            "prompt": (
                "以图1老式小饭馆白昼大堂方木桌为背景，南侧正面平视三人中近景。左侧与图2五官发型服装完全一致的年轻男子端坐长凳，双手刚拿起桌面那张手绘改造草图举到胸前准备当众撕成两半；"
                "右侧站着图3年轻女子、坐着图4年轻男子，两人正错愕盯着他手中的草图，桌脚旁地面放着一只老式白瓷痰桶。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-3-15", "ep": 1,
            "refs": [sc_lin, c_ye],
            "prompt": (
                "以图1老式小饭馆白昼大堂为背景，正面偏右斜角近景。与图2五官发型服装完全一致的年轻男子居左偏中稳坐木长凳上，"
                "双手自然搭在腿侧已拉严拉链的军绿色帆布书包顶面，神色淡然从容，正平视画面右前方。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-3-18", "ep": 1,
            "refs": [sc_lin, c_ye],
            "prompt": (
                "以图1老式小饭馆通透木格窗光斑为背景，正面偏右斜角近景。与图2五官发型服装完全一致的年轻男子居左偏中坐在长凳上，"
                "神色彻底释然冷淡，双手正握紧身侧军绿色帆布书包的提带准备起身离席，目光平静望向右前方。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-3-21", "ep": 1,
            "refs": [sc_lin, sc_street, c_ye],
            "prompt": (
                "以图1老式饭馆敞开的双扇老木门框与门外图2白昼阳光重庆老街日影为背景，门槛右侧斜拍单人近景（画面中仅有男主一人，身后无人追近）。"
                "与图3五官发型服装完全一致的年轻男子居中偏右立于敞开的木门槛处，右肩背着鼓囊的军绿色帆布书包、右手扶住前肩带，门外阳光勾出冷硬侧逆光轮廓，他正微侧过半张脸朝门内左后方冷淡斜瞥。" + STYLE_TAIL
            ),
        },

        # ==================== EPISODE 2 (12 PRIMARY + 2 AUX) ====================
        {
            "id": "2-1-01", "ep": 2,
            "refs": [sc_street, c_ye, c_lin],
            "prompt": (
                "以图1正午阳光下的重庆老街传统小饭馆褪色木门框与两级水泥台阶为背景，西侧平视双人拉扯中近景。"
                "左侧台阶下站着与图2五官发型服装完全一致的年轻男子，右肩背着军绿色帆布书包，左腕戴着一块黑色塑料电子表，背脊挺直侧脸冷淡；"
                "右侧高一级台阶上站着与图3五官发型服装完全一致的年轻女子，伸出右手死死攥住男子右肩的帆布书包带不放，眼神轻蔑笃定地上下打量他。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-1-04", "ep": 2,
            "refs": [sc_street, c_lin],
            "prompt": (
                "以图1正午老街小饭馆褪色木门板为背景，西侧平视单人正侧近景。与图2五官发型服装完全一致的年轻女子居中偏右立于台阶上，"
                "右手在画面左下边缘仍抓着一条军绿色帆布书包带，左手自然垂在腰侧，微扬下巴摆出居高临下施舍姿态紧盯画面左前方。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-1-08", "ep": 2,
            "refs": [sc_street, c_ye],
            "prompt": (
                "以图1正午阳光虚化的重庆老街为背景，西侧偏正单人近景。与图2五官发型服装完全一致的年轻男子居中偏左挺立，右肩斜跨军绿色帆布书包带（手腕空置无手表），"
                "正午硬光勾勒利落下颌线，神色淡漠决绝地平视画面右前方。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-1-11", "ep": 2,
            "refs": [sc_street, c_lin, c_chu],
            "prompt": (
                "以图1老街饭馆木门框为背景，西侧近景。与图2五官发型服装完全一致的年轻女子居中立于台阶上（女子双肩干净不背任何挎包或背包），左手死死攥着一块黑色塑料电子表贴在胸口，右手自然垂在身体左下侧，"
                "她正慌乱急切地猛扭头望向右后方斜倚在木门框旁虚化的图3年轻男子身影。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-1-14", "ep": 2,
            "refs": [sc_street, c_ye, c_lin],
            "prompt": (
                "以图1正午老街饭馆木门与水泥台阶为背景，西侧平视双人拉扯中景。左侧台阶下图2年轻男子右手已握住自己右肩军绿帆布书包带的上部准备发力抽回；"
                "右侧台阶上图3年轻女子左手攥着黑色塑料表贴胸、右手仍抓着绷直的书包带下端，两人分立台阶上下紧绷对峙。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-2-01", "ep": 2,
            "refs": [sc_street, c_qian, c_thug],
            "prompt": (
                "以图1正午冷清无客的重庆老街传统小食府敞开木门头与两级青石台阶为背景（门前空旷无外摆火锅桌），东侧平视中全景。"
                "右侧木门柱旁，与图2五官发型服装完全一致的年轻女子正微踮脚尖伸右手捏住木门柱上贴着的半张旧白纸准备撕下；"
                "左侧街沿下，与图3五官发型服装完全一致的年轻混混右手捏着一叠彩色传单，满脸痞笑正迈步踏上青石台阶向她凑近。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-2-04", "ep": 2,
            "refs": [sc_street, c_ye, c_thug, c_qian],
            "prompt": (
                "以图1老街小食府门前青石台阶与木门柱为背景，东侧平视三人截停中近景。右后方图4年轻女子紧贴木门柱受惊缩肩；左侧图3混混左手捏传单、右手正凶狠探向女子左小臂寸许处；"
                "左中位置与图2五官发型服装完全一致、右肩背军绿帆布书包的年轻男子刚大步跨上台阶切入两人之间，伸出左手正迎面扣向混混探出的右手腕。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-2-07", "ep": 2,
            "refs": [sc_street, c_ye, c_qian],
            "prompt": (
                "以图1正午老街小食府木门柱与敞开店门为背景，东侧斜拍双人中近景。左侧与图2五官发型服装完全一致、右肩背军绿帆布书包的年轻男子刚转过身温和面向右侧；"
                "右侧木门柱旁站着与图3五官发型服装完全一致的年轻女子，右手攥着半张揉皱的碎白纸垂在身侧，泛红的眼眶骤然亮起惊喜望向左侧男子。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-3-01", "ep": 2,
            "refs": [sc_xia_hall, c_qian, c_ye],
            "prompt": (
                "以图1白昼敞亮却空无一客的传统川菜小馆前厅为背景（整齐排列着擦得锃亮的方木桌与条凳，右侧为深色木柜台且台面摊开一本红笔账本，左后方为垂闭的深蓝布后厨门帘），南侧过道全景。"
                "与图2五官发型服装完全一致的年轻女子（双手空置）在前、与图3五官发型服装完全一致且右肩背军绿帆布书包的年轻男子在后，两人刚从敞开大门迈入空荡前厅走向右侧木柜台。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-3-05", "ep": 2,
            "refs": [sc_xia_hall, c_ye],
            "prompt": (
                "以图1空荡整洁的传统小馆前厅与深木色收银柜台为背景，南侧平视柜台外单人中近景。"
                "与图2五官发型服装完全一致的年轻男子居左立于木柜台外侧，右边缘可见木柜台角上合拢的账本，他正将洗旧的军绿色帆布书包托在左小臂前，右手搭在书包金属拉链上准备拉开取物。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-3-08", "ep": 2,
            "refs": [sc_xia_hall, c_ye, c_qian],
            "prompt": (
                "以图1传统小馆前厅木柜台为背景（左后方后厨深蓝布门帘自然垂闭无人），越右侧图3年轻女子虚化肩发的近景。"
                "与图2五官发型服装完全一致的年轻男子居左偏中立于柜台前，左小臂挎着敞口军绿帆布书包，右手五指稳稳按在柜台木面上那包麻绳扎口的粗布草本香料包上，目光坦荡诚挚地平视右前方女子。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-3-10_aux", "ep": 0,
            "refs": [sc_xia_hall, c_jianguo],
            "prompt": (
                "以图1传统小馆前厅左后方挂着深蓝布门帘的后厨门洞为背景，南侧斜拍单人中近景。"
                "与图2五官发型服装完全一致的老师傅居左偏中刚掀帘站在深蓝布门帘前，左手紧紧捂着微微泛红肿痛的脖颈侧，右手垂拎着一把长柄大铁炒勺，眉头紧拧神色威严固执地怒视画面右前方。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-3-11", "ep": 2,
            "refs": [sc_xia_hall, c_qian, c_ye],
            "prompt": (
                "以图1传统小馆前厅深木色柜台旁为背景，南侧双人中近景。右侧与图2五官发型服装完全一致的年轻女子刚从柜台缺口迈出半步，双手微抬满脸心疼焦急地望向画面左方；"
                "左中位置与图3五官发型服装完全一致的年轻男子侧立在柜台前，左臂挎帆布书包、右手仍稳稳护在柜台面的粗布草本香料包上，同样转头注视画面左方。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-3-13_aux", "ep": 0,
            "refs": [sc_xia_hall, c_ye, c_qian, c_jianguo],
            "prompt": (
                "以图1传统小馆前厅为背景，越右侧木柜台向深蓝布门帘纵深拍摄的三层景深中景。右下前景木柜台面上放着麻绳扎口的粗布草本香料包，图2年轻男子右手稳按在草本包上沉静向左迎视，身旁图3年轻女子焦急伫立；"
                "左后景深蓝布门帘前，与图4五官发型服装完全一致的老师傅左手捂着脖颈、右手垂拎长柄铁炒勺冷硬对峙。" + STYLE_TAIL
            ),
        },

        # ==================== EPISODE 3 (16 PRIMARY + 5 AUX) ====================
        {
            "id": "3-1-01", "ep": 3,
            "refs": [sc_xia_hall, c_jianguo, c_qian, c_ye],
            "prompt": (
                "以图1白昼传统小馆前厅为背景，南侧正面偏侧中景。右侧后厨深蓝布门帘前，与图2五官发型服装完全一致的老师傅左手紧捂泛红疼痛的脖颈、右手拎着铁炒勺正痛苦弯腰干咳；"
                "身旁与图3五官发型服装完全一致的年轻女子焦急双手搀扶父亲左臂引向木桌条凳；左前景深木柜台旁可见图4年轻男子右手按在粗布草本包上关切注视。" + STYLE_TAIL
            ),
        },
        {
            "id": "3-1-04", "ep": 3,
            "refs": [sc_xia_hall, c_ye, c_jianguo],
            "prompt": (
                "以图1白昼传统小馆前厅深木色柜台为背景，越右前景图3老师傅虚化肩头拍向左侧的近景。"
                "与图2五官发型服装完全一致的年轻男子居左偏中挺立在深木柜台前，台面敞口军绿帆布书包旁放着麻绳粗布草本香料包，他右手五指稳按在粗布包上，眼神清亮自信直视右前方。" + STYLE_TAIL
            ),
        },
        {
            "id": "3-1-08", "ep": 3,
            "refs": [sc_xia_kitch, c_ye],
            "prompt": (
                "以图1传统小馆白昼后厨砖砌猛火炒灶与木配菜台为背景，灶台南侧斜俯中近景。砖砌小灶炉膛蓝红火苗升腾，大铁锅内盛着清亮温油；"
                "与图2五官发型服装完全一致的年轻男子立于灶台右侧面向左，双手正在灶边解开粗布草本香料包的麻绳，露出砂仁与罗汉果芯等干草本香料准备拨入温油锅中。" + STYLE_TAIL
            ),
        },
        {
            "id": "3-1-11", "ep": 3,
            "refs": [sc_xia_kitch, c_chenbo],
            "prompt": (
                "以重庆青石板老巷与右侧传统餐馆后厨一扇敞开的外推旧木窗为背景（参考图1木窗与砖墙质感，木窗内正袅袅飘出清透温润的淡白药膳水汽），巷口窗外斜侧中景。"
                "与图2五官发型服装完全一致的中年街坊大伯右手拿着一把老式蒲扇，刚从左侧青石巷道迈步走到木窗左沿停步扬鼻闻香。" + STYLE_TAIL
            ),
        },
        {
            "id": "3-1-13_aux", "ep": 0,
            "refs": [sc_xia_kitch, c_ye, p_pot],
            "prompt": (
                "以图1传统后厨猛火小灶为背景，灶前斜俯近景。小灶上架着一口图3样式的紫铜红汤锅（单格满盛清亮透红无浓烟的药膳红汤正咕嘟微沸），灶边木配菜台上放着一盘鲜毛肚片与一只白瓷碗；"
                "与图2服装一致的年轻男子左手持汤勺刚往白瓷碗里舀入半碗清亮红汤，右手执长竹筷正夹起两片鲜毛肚探入红汤锅涮烫。" + STYLE_TAIL
            ),
        },
        {
            "id": "3-1-14", "ep": 3,
            "refs": [sc_xia_hall, c_ye, c_jianguo, c_qian, p_pot],
            "prompt": (
                "以图1白昼传统小馆前厅方木桌为背景（后方白灰内墙高处挂着一只黑框圆形石英挂钟），南侧平视中景。方木桌中央小炉上放着一口微沸的图5紫铜红汤锅；"
                "左侧图2年轻男子正双手端着盛有半碗清亮红汤与毛肚的白瓷碗俯身放到右侧坐着的图3老师傅面前，图4年轻女子立在父亲身侧紧张期待地注视。" + STYLE_TAIL
            ),
        },
        {
            "id": "3-1-18", "ep": 3,
            "refs": [sc_xia_hall, c_jianguo],
            "prompt": (
                "以图1传统小馆前厅木桌旁为背景，正面平视胸上近景。与图2五官发型服装完全一致的老师傅居中静坐在木桌后，桌面一角搁着喝空的白瓷碗与竹筷，"
                "自然暖光下他额角沁出一层细密薄汗，脖颈红肿已消退，正微垂眼帘准备吞咽感知喉部。" + STYLE_TAIL
            ),
        },
        {
            "id": "3-1-21", "ep": 3,
            "refs": [sc_xia_hall, c_chenbo],
            "prompt": (
                "从图1传统小馆前厅内部拍向左侧临巷敞开的双扇旧木窗框，近景构图。与图2五官发型服装完全一致的中年街坊大伯站在木窗外，左手夹着蒲扇扒在木窗沿上探进半个头肩，"
                "两眼放光直勾勾盯着右前方厅内咽口水，右手刚摸出一张二十元纸币正要重重拍按在木窗台面上。" + STYLE_TAIL
            ),
        },
        {
            "id": "3-1-24", "ep": 3,
            "refs": [sc_xia_hall, c_jianguo, c_ye, c_qian, p_pot],
            "prompt": (
                "以图1白昼传统小馆前厅方木桌为背景，南侧正面平视中景。方木桌中央立着热气袅袅的图5紫铜红汤锅；"
                "左侧站着图3年轻男子，右后侧站着面带欣喜的图4年轻女子，桌右与图2五官发型服装完全一致的老师傅刚猛地从条凳站起身俯眼端详红汤锅，满脸振奋钦佩。" + STYLE_TAIL
            ),
        },
        {
            "id": "3-2-01", "ep": 3,
            "refs": [sc_street, c_ye, c_qian, c_jianguo],
            "prompt": (
                "以图1晴朗上午的重庆青灰老街西侧传统小食府敞开木门与三级青石台阶为背景（木门柱内侧斜靠着一把长柄铁锹，门前无外摆桌椅），南侧正面偏侧中景。"
                "图2年轻男子（左肩背军绿帆布书包、右手捏着折好的白纸字据）、图3年轻女子（双手抱着一本流水账本）与空手的图4老师傅三人正神色轻松地并排迈出木门槛踏上青石台阶。" + STYLE_TAIL
            ),
        },
        {
            "id": "3-2-03_aux", "ep": 0,
            "refs": [sc_street, c_zhao],
            "prompt": (
                "以图1晴朗老街东侧传统饭馆大门前灰石地面为背景（地面铺满刚炸开的鲜红鞭炮碎纸屑与淡淡白烟，一块拆下的黑色旧木牌匾平搁在红纸屑中央），南侧低机位微仰中景。"
                "与图2五官发型服装完全一致的西餐厨师（不戴帽子，保持图2发型与双排扣白厨师服红领巾）双手背在身后昂首迈出大门，正高抬右脚黑皮鞋对准地上的旧木牌匾重重踩下。" + STYLE_TAIL
            ),
        },
        {
            "id": "3-2-04", "ep": 3,
            "refs": [sc_street, c_lin, c_chu, c_zhao],
            "prompt": (
                "以图1晴朗老街东侧饭馆大门前（地面散落红鞭炮碎纸屑）为背景，南侧平视三人互动中近景。"
                "右侧图2年轻女子左手亲昵挽着图3年轻男子左臂（图3男子右手垂拎一只红白塑料扩音小喇叭），女子右手捧着一本红色硬壳聘书满脸得意地递向左侧站立的图4白衣厨师（保持图4原发型无帽），图4厨师正受用挑眉准备伸双手接过聘书。" + STYLE_TAIL
            ),
        },
        {
            "id": "3-2-08", "ep": 3,
            "refs": [sc_street, c_ye],
            "prompt": (
                "以图1晴朗老街西侧小食府虚化木门框为背景，青石台阶高处单人正面微侧平视近景。"
                "与图2五官发型服装完全一致的年轻男子居左偏中挺立于台阶上，左肩背着军绿帆布书包，双唇紧抿完全闭合，眼神深邃冷峻地遥望画面右前方斜对门。" + STYLE_TAIL
            ),
        },
        {
            "id": "3-2-09_aux", "ep": 0,
            "refs": [sc_street, c_chu, c_lin, c_zhao],
            "prompt": (
                "以图1晴朗老街东侧饭馆门前为背景，正面偏左三人中近景。图2年轻男子居右偏中，图3年轻女子挽着他左臂，左后方图4白衣厨师左手托红皮聘书抱臂看戏；"
                "图2男子满脸跋扈挑衅盯向左前方对门，右手正举起一只红白扩音小喇叭凑到嘴边大声喊话。" + STYLE_TAIL
            ),
        },
        {
            "id": "3-2-11", "ep": 3,
            "refs": [sc_street, c_lin, c_chu],
            "prompt": (
                "以图1晴朗老街东侧饭馆门前为背景，正面偏左近景。与图2五官发型服装完全一致的年轻女子居右偏中，左手挽着身旁刚放下扩音小喇叭的图3年轻男子左臂，"
                "阳光照亮她高高扬起下巴的面庞，眼神怨怼又得意炫耀地直刺画面左前方。" + STYLE_TAIL
            ),
        },
        {
            "id": "3-2-12_aux", "ep": 0,
            "refs": [sc_street, c_jianguo, c_ye, c_qian],
            "prompt": (
                "以图1晴朗老街西侧小食府青石台阶与木门柱为背景，侧面偏正三人中近景。右侧图2老师傅气得踏前半步抬右手指着右前方对门怒声斥责；"
                "左侧图3年轻男子沉静站立正将折好的白纸字据塞进自己帆布书包侧袋，中间图4年轻女子双手紧抱流水账本。" + STYLE_TAIL
            ),
        },
        {
            "id": "3-2-14", "ep": 3,
            "refs": [sc_street, c_ye, c_qian],
            "prompt": (
                "以图1晴朗老街西侧小食府台阶为背景，越右前景图3年轻女子虚化肩头与双手平托的摊开账本边缘拍向左侧的近景。"
                "与图2五官发型服装完全一致的年轻男子居左偏中，左肩背着军绿帆布书包，右手食指轻点在摊开的账本页码上，神情平静专注地抬头望向右前方女子。" + STYLE_TAIL
            ),
        },
        {
            "id": "3-2-17", "ep": 3,
            "refs": [sc_street, c_zhao, c_ye, c_qian, c_jianguo],
            "prompt": (
                "以图1晴朗重庆青灰老街两侧对门店铺为背景（中间水泥老街路面贯通，此时台阶前尚无沙石），老街南侧斜纵深俯视全景。"
                "右后方斜对门饭馆前，图2白衣厨师左手夹红皮聘书站立，身旁两名戴黄色安全帽的工人正扶着两辆满载灰黄水泥沙石的铁皮独轮斗车准备横穿马路冲过来；"
                "左前景青石台阶上站着图3年轻男子、抱账本的图4年轻女子与图5老师傅。" + STYLE_TAIL
            ),
        },
        {
            "id": "3-2-20", "ep": 3,
            "refs": [sc_street, c_zhao],
            "prompt": (
                "以图1晴朗老街路面与左下角刚倾倒隆起的灰黄水泥沙石堆一角为背景，沙石堆右侧微仰中近景。"
                "与图2五官发型服装完全一致的白衣厨师（无帽）居右偏中站在沙石堆外侧路面上，左手腋下夹着红皮聘书，歪着脖子满脸痞气嚣张地斜睨左上方台阶。" + STYLE_TAIL
            ),
        },
        {
            "id": "3-2-23", "ep": 3,
            "refs": [sc_street, c_lin, c_chu],
            "prompt": (
                "以图1晴朗老街东侧饭馆门前散落红鞭炮纸屑的背景，双人中近景。图2年轻女子挽着图3年轻男子并立门前，图3男子左手抱臂、右手垂拎红白扩音小喇叭，"
                "两人正朝左前方对门望去，满脸幸灾乐祸准备仰头哄笑。" + STYLE_TAIL
            ),
        },
        {
            "id": "3-2-24_aux", "ep": 0,
            "refs": [sc_street, c_ye, c_zhao],
            "prompt": (
                "以图1晴朗老街西侧小食府门头与蓝天逆光为背景，堵在青石台阶前高高隆起的灰黄水泥沙石堆南侧低机位仰拍中近景。"
                "左上方沙石堆最高处，与图2五官发型服装完全一致、背着军绿帆布书包的年轻男子单手提握一把长柄铁锹将铁铲刃重重拄进脚下沙石中，眼神凛冽如刀居高临下俯视右下方路面上的图3白衣厨师。" + STYLE_TAIL
            ),
        },
    ]


def build_contact_sheet(ep_no: int, specs: List[Dict[str, Any]], out_jpg: Path) -> None:
    ep_specs = [s for s in specs if s["ep"] == ep_no]
    if not ep_specs:
        return
    cols = 4
    rows = (len(ep_specs) + cols - 1) // cols
    tw, th = 360, 640
    canvas = Image.new("RGB", (cols * tw, rows * th), (18, 18, 18))
    draw = ImageDraw.Draw(canvas)
    for idx, s in enumerate(ep_specs):
        r, c = divmod(idx, cols)
        p = KF_1K / f"{s['id']}_1k.png"
        if p.is_file():
            im = Image.open(p).convert("RGB").resize((tw, th), Image.LANCZOS)
            canvas.paste(im, (c * tw, r * th))
            draw.rectangle([c * tw, r * th, c * tw + 135, r * th + 32], fill=(0, 0, 0))
            draw.text((c * tw + 8, r * th + 8), s["id"], fill=(255, 230, 80))
    canvas.save(out_jpg, quality=90)


def main() -> None:
    only_ids = set(sys.argv[1:])
    amap = build_asset_map()
    specs = build_keyframe_specs(amap)

    def gen_one(s: Dict[str, Any]) -> str:
        sid = s["id"]
        p2k = KF_2K / f"{sid}_2k.png"
        p1k = KF_1K / f"{sid}_1k.png"
        force = sid in only_ids
        if force or not p2k.is_file() or not p1k.is_file():
            vtrix_image.generate_vtrix_image(
                prompt=s["prompt"],
                out_path=p2k,
                ref_files=s["refs"],
                aspect_ratio="9:16",
                resolution="2K",
            )
            compress_image_to_1k(p2k, p1k, max_side=1024)
        return sid

    target_specs = [s for s in specs if (not only_ids or s["id"] in only_ids)]
    print(f"Generating {len(target_specs)}/{len(specs)} 2K/1K keyframes (5 parallel Vtrix workers)...", flush=True)
    with ThreadPoolExecutor(max_workers=5) as pool:
        futs = {pool.submit(gen_one, s): s["id"] for s in target_specs}
        done = 0
        for fut in as_completed(futs):
            sid = fut.result()
            done += 1
            print(f"  [{done}/{len(target_specs)}] Keyframe {sid} ready", flush=True)

    for ep_no, name in [(1, "ep01"), (2, "ep02"), (3, "ep03"), (0, "aux")]:
        sheet_path = WORK_DIR / f"{name}_v7_keyframes_sheet.jpg"
        build_contact_sheet(ep_no, specs, sheet_path)
        print(f"Saved contact sheet: {sheet_path}", flush=True)


if __name__ == "__main__":
    main()
