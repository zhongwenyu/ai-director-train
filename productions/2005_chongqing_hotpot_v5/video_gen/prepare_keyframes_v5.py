#!/usr/bin/env python3
"""
Build complete <=1K asset cache (`asset_map.json`) and generate all 35 2K/1K blocking keyframes
for `2005_chongqing_hotpot_v5` Episodes 1, 2, and 3 (`12` Ep 1 + `12` Ep 2 + `11` Ep 3 = `35` shots),
enforcing:
  - Locked 180° left-right spatial axes across continuous table/street scenes
  - Exact visual costume & prop anchors (2015 white chef coat + gold watch; 2005 apron -> apron off + wrought-iron ladle)
  - Zero text/subtitles/watermarks in all keyframes
  - Contact sheets (`ep01_v5_sheet.jpg`, `ep02_v5_sheet.jpg`, `ep03_v5_sheet.jpg`) for mandatory visual inspection
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
V3_ASSETS_1K = Path("/home/zhongwenyu/project/ai-director-train/productions/2005_chongqing_hotpot_v3/ep01_02_video_gen/assets_1k")

WORK_DIR = Path("/home/zhongwenyu/project/ai-director-train/productions/2005_chongqing_hotpot_v5/video_gen")
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
        "叶寻 · 渝清记围裙掌勺",
        "叶寻 · 2020研发总厨白服",
        "夏芊芊",
        "林双双",
        "林双双 · 塞纳左岸酒红礼服",
        "楚南",
        "楚南 · 海归并购总监西装",
        "林有才",
        "老王",
        "中年食客",
        "集团大厦旋转门雨夜街口",
        "沙正街林家食府老店大堂",
        "桂花巷渝清记大堂与天井",
        "重庆老街对门双火锅铺街景",
        "夏氏小厨后厨猛火炒灶",
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

    # Bind audited single-speaker voices
    v_ye = amap["叶寻"]["voice"]
    amap["叶寻 · 渝清记围裙掌勺"]["voice"] = v_ye
    amap["叶寻 · 2020研发总厨白服"]["voice"] = v_ye
    amap["林双双 · 塞纳左岸酒红礼服"]["voice"] = amap["林双双"]["voice"]
    amap["楚南 · 海归并购总监西装"]["voice"] = amap["楚南"]["voice"]
    amap["林有才"]["voice"] = str(find_media_file("d7b6d049-8fbc-4f8c-9855-2445a9d4d7a0"))

    # Copy cached apronless charcoal pullover portrait from v3
    no_apron_2k = ASSETS_1K / "yexun_charcoal_no_apron_2k.png"
    no_apron_1k = ASSETS_1K / "yexun_charcoal_no_apron_1k.png"
    if not no_apron_1k.is_file() and (V3_ASSETS_1K / "yexun_charcoal_no_apron_1k.png").is_file():
        shutil.copy2(V3_ASSETS_1K / "yexun_charcoal_no_apron_2k.png", no_apron_2k)
        shutil.copy2(V3_ASSETS_1K / "yexun_charcoal_no_apron_1k.png", no_apron_1k)
    amap["叶寻_脱围裙"] = {
        "id": amap["叶寻"]["id"],
        "type": "character",
        "front_2k": str(no_apron_2k),
        "front_1k": str(no_apron_1k),
        "voice": v_ye,
    }

    # Alias 老马 -> 老王 asset (`c18f6f58.png`) + clean 45yo male voice (`zhou_director_clean.wav`)
    laoma = dict(amap["老王"])
    laoma["voice"] = "/home/zhongwenyu/project/ai-director-train/productions/2005_chongqing_hotpot_v3/voices/zhou_director_clean.wav"
    amap["老马"] = laoma

    (WORK_DIR / "asset_map.json").write_text(json.dumps(amap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return amap


STYLE_TAIL = (
    "精致35mm电影实拍质感，竖屏9:16中近景或中景腰部以上构图，真实光影层次与皮肤衣料纹理，"
    "人物视线方向与空间透视准确，画面干净无任何文字、字幕、花字、Logo或水印。"
)


def build_keyframe_specs(amap: Dict[str, Any]) -> List[Dict[str, Any]]:
    sc_tower = amap["集团大厦旋转门雨夜街口"]["main_1k"]
    sc_lin = amap["沙正街林家食府老店大堂"]["main_1k"]
    sc_xia = amap["桂花巷渝清记大堂与天井"]["main_1k"]
    sc_street = amap["重庆老街对门双火锅铺街景"]["main_1k"]
    sc_kitchen = amap["夏氏小厨后厨猛火炒灶"]["main_1k"]

    c_ye_2015 = amap["叶寻 · 2020研发总厨白服"]["front_1k"]
    c_lin_2015 = amap["林双双 · 塞纳左岸酒红礼服"]["front_1k"]
    c_chu_2015 = amap["楚南 · 海归并购总监西装"]["front_1k"]

    c_ye_apron = amap["叶寻 · 渝清记围裙掌勺"]["front_1k"]
    c_ye_clean = amap["叶寻_脱围裙"]["front_1k"]
    c_lin = amap["林双双"]["front_1k"]
    c_youcai = amap["林有才"]["front_1k"]
    c_qian = amap["夏芊芊"]["front_1k"]
    c_laoma = amap["老马"]["front_1k"]
    c_diner = amap["中年食客"]["front_1k"]

    return [
        # ==================== EPISODE 1 (12 SHOTS) ====================
        {
            "id": "1-1-01", "ep": 1,
            "refs": [sc_tower, c_ye_2015, c_youcai],
            "prompt": (
                "以图1现代大厦玻璃旋转门外的雨夜湿滑街道为背景。瓢泼大雨中，左侧地面积水里半跪着浑身湿透、面色灰败憔悴的图2白厨师服男子，他一手捂着胸口痛苦抬头，身旁积水里散落着一只湿透的白色药袋；"
                "右侧屋檐下站着图3穿酒红暗纹唐装的中年男子，正嫌恶冷酷地低头俯视他。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-1-02", "ep": 1,
            "refs": [sc_tower, c_lin_2015, c_chu_2015],
            "prompt": (
                "以图1辉煌灯火大厦外的雨夜为背景，中近景双人同框。一把大黑伞下，右侧图3穿黑色三件套西装戴金丝眼镜的年轻男子单手撑伞，另一只手揽着左侧图2穿酒红缎面长裙外搭米色风衣的年轻女子；"
                "女子亲密挽住男子手臂，她左手腕上戴着一块醒目的金色女式腕表，两人居高临下冷漠俯视镜头左下方。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-1-03", "ep": 1,
            "refs": [sc_tower, c_ye_2015],
            "prompt": (
                "以图1雨夜大厦金色旋转门虚化光斑为背景，低机位近景特写。图2穿湿透旧白厨师服的男子跌坐在积水柏油地面上，雨水顺着乌黑短发和苍白脸颊滑落，嘴角带一丝血迹，双目通红充满悲愤死死仰望前方；远处雨幕中一男一女撑黑伞转身走向旋转门的背影虚化。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-2-01", "ep": 1,
            "refs": [sc_lin, c_ye_apron],
            "prompt": (
                "以图1充满烟火气的2005年重庆老火锅木质堂厅白天内景为背景，头顶老吊扇旋转，圆木桌中央红铜火锅热气升腾。中近景拍向坐在圆桌左侧竹椅上的图2系棕色围裙的二十三岁年轻男子，他刚猛然惊醒，正低头震惊地看着自己摊开在桌面上方、手背带浅淡旧烫痕却年轻有力的双手。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-2-02", "ep": 1,
            "refs": [sc_lin, c_ye_apron, c_youcai, c_lin],
            "prompt": (
                "以图1白天热闹的2005年重庆老火锅堂厅圆木桌为背景，中景三人同框（严格锁定左中右站位：图2系棕色围裙年轻男子坐左侧，图3穿酒红唐装中年老板坐中间，图4穿米色短袖套裙左手腕戴金色女表的年轻女子坐右侧）。"
                "中间图3满面红光笑呵呵地端起一杯冰镇啤酒，左手热情拍着左侧图2年轻男子的肩膀，右侧图4女子满脸甜笑看着图2男子。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-2-03", "ep": 1,
            "refs": [sc_lin, c_ye_apron, c_youcai],
            "prompt": (
                "以图1白天老火锅堂厅圆木桌为背景，过肩中近景。左前景坐着神色冷静审视的图2系棕色围裙年轻男子，他的手稳稳搭在桌边未碰酒杯；对面中间图3穿酒红唐装的中年老板正端着啤酒杯前倾身体，满脸堆满讨好又精明的褶子笑意。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-2-04", "ep": 1,
            "refs": [sc_lin, c_ye_apron, c_lin],
            "prompt": (
                "以图1白天老火锅堂厅圆桌为背景，中近景双人构图。左侧图2系棕色围裙年轻男子平静注视对面；右侧图3穿米色套裙的年轻女子娇笑着将一本深色硬皮记账本和一支拔开笔帽的钢笔放到木桌面上，她伸出的左手腕上清晰戴着一块崭新闪亮的金色女式腕表。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-2-05", "ep": 1,
            "refs": [sc_lin, c_ye_apron, c_lin, c_youcai],
            "prompt": (
                "以图1白天老火锅堂厅圆桌为背景，桌面与人物腰部以上紧凑中近景。右侧图3女子伸出戴着醒目金色女表的左手，将摊开的硬皮记账本与钢笔推向左侧图2系围裙年轻男子手边；中后景图4穿酒红唐装中年男子笑眯眯点头帮腔；左侧图2男子的目光锐利地钉在女子手腕那块金表上。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-2-06", "ep": 1,
            "refs": [sc_lin, c_ye_apron],
            "prompt": (
                "以图1白天老火锅堂厅圆桌为背景，左侧人物中近景特写。图2系棕色围裙的年轻男子坐在竹椅上，神情冷峻清醒，伸出右手食指与中指稳稳按在摊开的记账本边缘，将其往桌面右侧推回。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-2-07", "ep": 1,
            "refs": [sc_lin, c_ye_apron, c_youcai, c_lin],
            "prompt": (
                "以图1白天老火锅堂厅圆桌为背景，中景三人同框（图2年轻男子居左，图3酒红唐装老板居中，图4米色套裙女子居右）。中间图3摊手笑着打圆场，右侧图4女子故作委屈双手搭在桌沿露出左手腕金表，左侧图2年轻男子眼神微冷直视她手腕上的金表。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-2-08", "ep": 1,
            "refs": [sc_lin, c_lin, c_youcai],
            "prompt": (
                "以图1白天老火锅堂厅圆桌为背景，右侧双人中近景。右侧图2穿米色套裙的女子脸色骤变心虚慌乱，正用右手慌忙去拉扯遮挡左手腕上的金色女表；身旁左侧图3穿酒红唐装的父亲眉头拧起、神色焦躁催促。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-2-09", "ep": 1,
            "refs": [sc_lin, c_ye_apron, c_youcai, c_lin],
            "prompt": (
                "以图1白天老火锅堂厅圆桌为背景，高张力中景三人定格构图（左图2、中图3、右图4）。左侧图2系棕色围裙年轻男子从容靠回竹椅椅背，眼神锋利如刀直视对面；中间图3端在半空的啤酒杯僵住，右侧图4女子死死捏着钢笔脸色煞白，满桌假笑彻底凝固。" + STYLE_TAIL
            ),
        },

        # ==================== EPISODE 2 (12 SHOTS) ====================
        {
            "id": "2-1-01", "ep": 2,
            "refs": [sc_lin, c_ye_apron, c_youcai, c_lin],
            "prompt": (
                "严格延续图1白天老火锅堂厅圆桌左中右站位（图2坐左、图3坐中、图4坐右）。头顶吊扇下气氛死寂，右侧图4女子心虚捂住左手腕金表，中间图3酒红唐装老板脸上的假笑彻底沉下，右手重重将啤酒杯墩在木桌面上。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-1-02", "ep": 2,
            "refs": [sc_lin, c_ye_apron, c_youcai],
            "prompt": (
                "以图1白天老火锅堂厅圆桌为背景，中近景双人对峙。左侧图2系棕色围裙年轻男子将一双带浅淡陈年油泡烫痕的手掌平摊在桌面记账本旁，目光平静冷冽地逼视中间阴沉着脸的图3酒红唐装老板。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-1-03", "ep": 2,
            "refs": [sc_lin, c_ye_apron, c_lin],
            "prompt": (
                "以图1白天老火锅堂厅圆桌为背景，中近景双人正反同框。左侧图2系棕色围裙年轻男子神色冷峻字字如刀，右侧图3穿米色套裙的女子脸色涨红、气急败坏地瞪着他辩解。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-1-04", "ep": 2,
            "refs": [sc_lin, c_ye_apron, c_youcai, c_lin],
            "prompt": (
                "以图1白天老火锅堂厅圆桌为背景，中景三人戏剧爆发瞬间。右侧图4米色套裙女子如遭雷击猛地站起身，身后的竹椅向后歪斜，满脸惊骇地盯着左侧稳坐如山的图2系围裙年轻男子；中间图3酒红唐装老板脸色铁青。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-1-05", "ep": 2,
            "refs": [sc_lin, c_youcai, c_lin],
            "prompt": (
                "以图1白天老火锅堂厅圆桌为背景，右侧双人中近景。图2穿酒红唐装的老板彻底撕下伪善画皮，冷笑着往竹椅背上一靠；身旁站着的图3米色套裙女子扬起下巴露出势利傲慢的冷漠神情。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-1-06", "ep": 2,
            "refs": [sc_lin, c_youcai],
            "prompt": (
                "以图1白天老火锅堂厅内景（后方可见半敞的后厨门框与香料架）为背景，图2穿酒红唐装的中年老板单人中近景。他满脸狂妄自大，伸手大拇指朝身后后厨方向一指，眼神轻蔑不屑。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-1-07", "ep": 2,
            "refs": [sc_lin, c_ye_apron, c_youcai],
            "prompt": (
                "以图1白天老火锅堂厅木桌为背景，极具冲击力的中近景。左侧站起身的图2年轻男子右手果断将半页手写配方草稿纸重重按进桌面一只装满深色冷茶水的粗瓷大碗里浸湿揉烂；右侧图3酒红唐装老板惊怒变色伸手欲抢。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-1-08", "ep": 2,
            "refs": [sc_kitchen, c_ye_clean],
            "prompt": (
                "以图1白天2005年重庆老火锅店后厨猛火炒灶口为背景（旁边的木椅背上已搭着解下的棕色围裙）。图2穿水洗炭黑挽袖圆领卫衣的年轻男子站在熄灭的大铁锅旁，左手刚拧死墙边的黄铜燃气总阀，右手正稳稳摘下灶头铁钩上挂着的一把古旧长柄熟铁炒勺。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-1-09", "ep": 2,
            "refs": [sc_lin, c_ye_clean, c_lin],
            "prompt": (
                "以图1白天老火锅店敞开的木质大门框为背景，逆光中近景。左侧图2穿炭黑挽袖卫衣的年轻男子右手提着那把长柄旧熟铁炒勺跨到门槛边，微微侧头冷眼回望；右后方店堂内图3穿米色套裙的女子满脸怨毒不甘地冲他背影叫嚷。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-2-01", "ep": 2,
            "refs": [sc_street, c_ye_clean, c_qian],
            "prompt": (
                "以图1白天阳光下的重庆青石板老街对门双火锅铺（左为夏记老火锅，右为林记火锅）为背景，街心中景双人同框。右侧图2穿炭黑挽袖卫衣、右手提着长柄旧铁炒勺的年轻男子刚走出林记台阶；左侧图3穿灰色短袖系黑色围裙、长卷发的年轻女掌柜正快步穿过青石板街迎上前拦住他，神色关切爽朗。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-2-02", "ep": 2,
            "refs": [sc_street, c_qian, c_ye_clean, c_youcai],
            "prompt": (
                "以图1白天重庆青石板老街双铺门前为背景，中景三人同框。左侧街心并肩站着图2黑围裙女掌柜与提着旧铁炒勺的图3炭黑卫衣年轻男子；右侧林记火锅木门框边，图4穿酒红唐装的中年老板双手抱胸倚门幸灾乐祸地嗤笑。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-2-03", "ep": 2,
            "refs": [sc_street, c_qian, c_ye_clean],
            "prompt": (
                "以图1白天阳光下的青石板老街夏记木牌虚化背景，紧凑中近景双人正面交锋。左侧图2系黑围裙的年轻女掌柜目光清亮灼灼地看着对面的男子与他手中的老熟铁炒勺；右侧图3穿炭黑挽袖卫衣的年轻男子握紧长柄老铁勺，眼神坚定沉稳地与她四目相对。" + STYLE_TAIL
            ),
        },

        # ==================== EPISODE 3 (11 SHOTS) ====================
        {
            "id": "3-1-01", "ep": 3,
            "refs": [sc_xia, c_ye_clean, c_qian],
            "prompt": (
                "以图1白天整洁敞亮的夏记老火锅木质堂厅（八仙桌擦得锃亮，暂时空桌未开火）为背景，中近景双人同框。左侧图2穿炭黑挽袖卫衣的年轻男子将长柄老铁炒勺靠放在木柜台边询问；右侧图3系黑围裙的女掌柜神情坦率愤慨地向他讲述。" + STYLE_TAIL
            ),
        },
        {
            "id": "3-1-02", "ep": 3,
            "refs": [sc_xia, c_ye_clean, c_qian],
            "prompt": (
                "以图1白天夏记老火锅木柜台前为背景，中近景双人构图。左侧图2穿炭黑挽袖卫衣的年轻男子站在木柜台旁，执毛笔在两张并排铺开的米黄色毛边账纸上刚写完字据，神色坦荡认真；右侧图3系黑围裙的女掌柜看着字据眼眶微热、满眼敬重。" + STYLE_TAIL
            ),
        },
        {
            "id": "3-1-03", "ep": 3,
            "refs": [sc_xia, c_ye_clean, c_qian],
            "prompt": (
                "以图1白天夏记老火锅木柜台为背景，腰部以上桌面紧凑双人中近景。木柜台上并排平铺着两份写好毛笔字的毛边纸字据，旁边摆着一盒敞开的朱砂红印泥；左侧图2炭黑卫衣男子与右侧图3黑围裙女掌柜大拇指指腹已沾着鲜红印泥，正同时果断将红手印按在两份字据落款处。" + STYLE_TAIL
            ),
        },
        {
            "id": "3-1-04", "ep": 3,
            "refs": [sc_xia, c_ye_clean, c_qian, c_laoma],
            "prompt": (
                "以图1白天夏记老火锅敞开的堂厅大门与木柜台为背景（门外隐约停着装铁油桶的三轮车），中景三人同框。右侧图4穿浅灰短袖系深色围裙、满头微汗的中年油商站在柜台前，一脸为难愧疚地将两张十元纸币放在木柜台上；中间图3黑围裙女掌柜愕然，左侧图2炭黑卫衣年轻男子目光沉静。" + STYLE_TAIL
            ),
        },
        {
            "id": "3-1-05", "ep": 3,
            "refs": [sc_xia, c_ye_clean, c_qian, c_laoma],
            "prompt": (
                "以图1白天夏记老火锅柜台前为背景，中近景三人构图。左侧图2炭黑卫衣年轻男子神色平静发问，中间图3黑围裙女掌柜柳眉紧蹙，右侧图4系深色围裙的中年油商双手合抱拱手赔罪、面露无奈苦笑。" + STYLE_TAIL
            ),
        },
        {
            "id": "3-1-06", "ep": 3,
            "refs": [sc_xia, c_ye_clean, c_qian, c_youcai],
            "prompt": (
                "以图1白天夏记老火锅敞开的木门槛为背景，内外对峙中景。右侧门外站着图4穿酒红唐装的中年老板，正摇着一把大蒲扇探头进来得意冷笑；左侧店内图3黑围裙女掌柜怒目而视，身旁的图2炭黑卫衣年轻男子神色淡定从容。" + STYLE_TAIL
            ),
        },
        {
            "id": "3-2-01", "ep": 3,
            "refs": [sc_street, c_ye_apron, c_youcai],
            "prompt": (
                "以图1暖金色傍晚夕阳下的重庆青石板老街双铺门前为背景。左侧夏记老火锅店门口架起一口猛火大生铁锅，旁边竹匾里盛着切好的雪白新鲜牛板油丁与一坛醪糟，图2重新系上棕色围裙的年轻男子站在铁锅后执老铁炒勺下料；右侧对门台阶上图3穿酒红唐装的老板双手抱胸看热闹冷笑。" + STYLE_TAIL
            ),
        },
        {
            "id": "3-2-02", "ep": 3,
            "refs": [sc_street, c_ye_apron, c_qian],
            "prompt": (
                "以图1傍晚暖光下的夏记门前大铁锅为背景，中近景双人构图。铁锅内雪白牛板油丁正滋滋融化出金黄清亮油脂，左侧图2系棕色围裙的年轻男子双手稳执长柄老铁炒勺匀速推搅；右侧图3系黑围裙的女掌柜凑在锅边紧张关切地注视锅内。" + STYLE_TAIL
            ),
        },
        {
            "id": "3-2-03", "ep": 3,
            "refs": [sc_street, c_ye_apron, c_qian],
            "prompt": (
                "以图1傍晚夏记门前沸腾大铁锅为背景，极具食欲感的烟火中近景。左侧图2系棕色围裙的年轻男子左手端着一只盛满清亮醪糟汁与葱段姜片紫草的白瓷碗，正沿滚烫铁锅边缘缓缓淋入，锅内腾起浓郁白雾并泛出透亮琥珀红光；右侧图3系黑围裙女掌柜闻香眼睛大亮、面露惊喜。" + STYLE_TAIL
            ),
        },
        {
            "id": "3-2-04", "ep": 3,
            "refs": [sc_street, c_diner, c_youcai],
            "prompt": (
                "以图1傍晚华灯初上的重庆青石板老街双铺门前为背景，中景双人街面构图（全画面严格仅此两人，严禁出现第三人或重复人物）。左侧夏记铁锅飘出醇厚白雾香气漫过石板街，街心偏左仅一名图2浅色短袖本地食客停下脚步，闭眼深吸香气面露陶醉并转身朝左侧夏记走去；右侧林记门口仅一名图3穿酒红唐装的老板握着蒲扇满脸错愕地望向对门。" + STYLE_TAIL
            ),
        },
        {
            "id": "3-2-05", "ep": 3,
            "refs": [sc_street, c_ye_apron, c_qian, c_youcai],
            "prompt": (
                "以图1傍晚灯笼亮起的重庆青石板老街双铺门前为背景，高燃集尾中景构图。左侧夏记大铁锅内琥珀红油透亮沸腾，图2系围裙年轻男子握长柄老铁炒勺傲然挺立，身旁图3黑围裙女掌柜满面春风抬手热情招呼食客进店；右侧对门冷清台阶上图4酒红唐装老板脸色铁青暴怒欲狂。" + STYLE_TAIL
            ),
        },
    ]


def build_contact_sheet(ep_no: int, specs: List[Dict[str, Any]], out_jpg: Path) -> None:
    ep_specs = [s for s in specs if s["ep"] == ep_no]
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
            draw.rectangle([c * tw, r * th, c * tw + 110, r * th + 32], fill=(0, 0, 0))
            draw.text((c * tw + 8, r * th + 8), s["id"], fill=(255, 230, 80))
    canvas.save(out_jpg, quality=90)


def main() -> None:
    amap = build_asset_map()
    specs = build_keyframe_specs(amap)

    def gen_one(s: Dict[str, Any]) -> str:
        sid = s["id"]
        p2k = KF_2K / f"{sid}_2k.png"
        p1k = KF_1K / f"{sid}_1k.png"
        if not p2k.is_file() or not p1k.is_file():
            vtrix_image.generate_vtrix_image(
                prompt=s["prompt"],
                out_path=p2k,
                ref_files=s["refs"],
                aspect_ratio="9:16",
                resolution="2K",
            )
            compress_image_to_1k(p2k, p1k, max_side=1024)
        return sid

    print(f"Generating {len(specs)} 2K/1K keyframes across Ep 1-3 (5 parallel Vtrix workers)...", flush=True)
    with ThreadPoolExecutor(max_workers=5) as pool:
        futs = {pool.submit(gen_one, s): s["id"] for s in specs}
        done = 0
        for fut in as_completed(futs):
            sid = fut.result()
            done += 1
            print(f"  [{done}/{len(specs)}] Keyframe {sid} ready", flush=True)

    for ep_no in (1, 2, 3):
        sheet_path = WORK_DIR / f"ep{ep_no:02d}_v5_keyframes_sheet.jpg"
        build_contact_sheet(ep_no, specs, sheet_path)
        print(f"Saved contact sheet: {sheet_path}", flush=True)


if __name__ == "__main__":
    main()
