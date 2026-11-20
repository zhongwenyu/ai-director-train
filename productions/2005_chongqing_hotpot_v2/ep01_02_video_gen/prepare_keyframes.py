#!/usr/bin/env python3
"""
Pre-compress all Episode 1 & Episode 2 v2 assets to <=1K (keeping 2K originals untouched in studio_media),
and generate all 22 2K/1K blocking keyframes (12 for Ep 1 including 1-1-07_aftermath + 10 for Ep 2)
strictly enforcing:
  1. <=1K compression invariant for video inputs
  2. Character identity & costume fidelity from 2K/1K #front references
  3. t=0.0s Initial Presence Set conservation law (no late-entering characters in t=0s frame)
  4. Cross-Scene Reference Isolation (separate dining room vs kitchen blocking keyframes)
  5. Pre-Impact -> Aftermath physical crash montage in 1-1-07
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
WORK_DIR = Path("/home/zhongwenyu/project/ai-director-train/productions/2005_chongqing_hotpot_v2/ep01_02_video_gen")
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
        "叶寻 · 2020研发总厨白服",
        "夏芊芊",
        "林双双",
        "林双双 · 塞纳左岸酒红礼服",
        "楚南",
        "楚南 · 海归并购总监西装",
        "夏建国",
        "老王",
        "中年食客",
        "集团大厦旋转门雨夜街口",
        "沙正街林家食府老店大堂",
        "重庆大学外沙正街黄昏老街",
        "夏氏小厨前厅与传菜口",
        "夏氏小厨后厨猛火炒灶",
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

    # Bind audited clean single-speaker voices
    amap["叶寻 · 2020研发总厨白服"]["voice"] = amap["叶寻"]["voice"]
    amap["林双双 · 塞纳左岸酒红礼服"]["voice"] = amap["林双双"]["voice"]
    amap["楚南 · 海归并购总监西装"]["voice"] = amap["楚南"]["voice"]
    amap["夏建国"]["voice"] = "/home/zhongwenyu/project/ai-director-train/productions/2005_chongqing_hotpot_v2/voices/xia_jianguo_clean.wav"
    amap["老王"]["voice"] = str(find_media_file("d7b6d049-8fbc-4f8c-9855-2445a9d4d7a0"))
    amap["中年食客"]["voice"] = str(find_media_file("d1acfe71-5ed3-4fb8-be3e-01c6a2530359"))
    amap["_diner_shout_voice"] = str(find_media_file("fdb623ec-1481-45d2-8447-069d563077f4"))

    (WORK_DIR / "asset_map.json").write_text(json.dumps(amap, ensure_ascii=False, indent=2), encoding="utf-8")
    return amap


STYLE_TAIL = (
    "精致电影实拍质感，竖屏9:16构图，真实光影层次与皮肤衣料纹理，人物与环境透视比例准确，"
    "严禁出现任何文字、字幕、水印、分格边框或纯白拼图底。"
)


def make_specs(amap: dict) -> list:
    return [
        # ==================== EPISODE 1 (12 keyframes for 11 groups) ====================
        {
            "id": "1-1-01",
            "refs": [
                amap["集团大厦旋转门雨夜街口"]["main_1k"],
                amap["叶寻 · 2020研发总厨白服"]["front_1k"],
                amap["楚南 · 海归并购总监西装"]["front_1k"],
                amap["林双双 · 塞纳左岸酒红礼服"]["front_1k"],
            ],
            "prompt": (
                "以图1的雨夜高档酒店侧铁门与湿滑柏油街口为环境，倾盆夜雨如注，严格保持图2男主厨、图3西装男子、图4酒红礼服女子的五官、发型及整套穿搭与各自参考图完全一致。"
                "中全景纵深俯仰对峙构图：前景湿漉漉的泥水地面上，图2穿白色总厨服的男子刚被推倒单膝撑地，身旁泥水洼里散落一只深棕色旧木盒与一张胸牌；"
                "中后景酒店侧门台阶上，图3西装男子一手撑一把大黑伞、一手揽着图4酒红礼服女子的肩膀居高临下冷眼俯视，冷蓝雨幕与台阶暖金灯光形成强烈冷暖反差。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-1-04",
            "refs": [
                amap["集团大厦旋转门雨夜街口"]["main_1k"],
                amap["叶寻 · 2020研发总厨白服"]["front_1k"],
                amap["林双双 · 塞纳左岸酒红礼服"]["front_1k"],
                amap["楚南 · 海归并购总监西装"]["front_1k"],
            ],
            "prompt": (
                "以图1的雨夜酒店台阶与铁门外湿滑地面为环境，大雨滂沱，严格保持图2白总厨服男子、图3酒红礼服女子、图4西装男子的五官、发型及穿搭与参考图完全一致。"
                "中近景高低对峙构图：画面左下方湿透的图2白总厨服男子左手按住雨水泥地、护住怀里旧木盒，仰起头满眼悲愤与不甘直视上方；"
                "画面右上方黑伞下，图3酒红礼服女子神情冰冷傲慢低头斥责，图4西装男子在旁轻蔑冷笑。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-1-07",
            "refs": [
                amap["集团大厦旋转门雨夜街口"]["main_1k"],
                amap["叶寻 · 2020研发总厨白服"]["front_1k"],
            ],
            "prompt": (
                "以图1的瓢泼大雨深夜柏油马路与紧闭铁门外街口为环境，严格保持图2白总厨服男子的五官、发型及穿搭与参考图一致。"
                "中景侧面跟拍构图：身后酒店铁门紧闭，全身湿透的图2男子双手死死抱紧怀里的深棕旧木盒，神情恍惚悲怆踉跄踏上湿滑反光的深夜马路，右侧远处两束刺目雪白的汽车远光灯正穿透雨幕极速射来。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-1-07_aftermath",
            "refs": [
                amap["集团大厦旋转门雨夜街口"]["main_1k"],
                amap["叶寻 · 2020研发总厨白服"]["front_1k"],
            ],
            "prompt": (
                "以图1的瓢泼大雨深夜积水柏油马路为环境，严格保持图2白总厨服男子的五官、发型及穿搭与参考图一致（干净无血腥，仅雨水湿透）。"
                "高机位俯拍雨夜事故余波构图：冰冷大雨砸在积水路面上，图2穿白色总厨服的男子双目微闭静静倒在湿滑的柏油马路积水中一动不动，他微松的右手旁落着那只深棕旧木盒，暗红色汽车尾灯倒影在雨水中晕开。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-2-01",
            "refs": [
                amap["沙正街林家食府老店大堂"]["main_1k"],
                amap["叶寻"]["front_1k"],
            ],
            "prompt": (
                "以图1的2005年重庆老式餐馆大堂（墨绿老吊扇、枣红木餐桌、暖黄斜阳）为环境，严格保持图2年轻男大学生的五官、发型及深藏青夹克内搭白T恤穿搭与参考图完全一致。"
                "中近景平视构图：傍晚橘金色夕阳斜照进空无一人的餐馆大堂，图2年轻男子刚从实木餐桌上猛然惊醒坐直身体，双手摊开在眼前震惊端详自己年轻光滑的手掌，桌上放着一部亮屏的2005年黑色诺基亚老式直板按键手机。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-2-04",
            "refs": [
                amap["沙正街林家食府老店大堂"]["main_1k"],
                amap["叶寻"]["front_1k"],
                amap["林双双"]["front_1k"],
            ],
            "prompt": (
                "以图1的2005年餐馆傍晚空荡大堂为环境，严格保持图2年轻男子与图3高马尾年轻女生的五官、发型及整套穿搭与各自参考图完全一致。"
                "中景双人对峙构图：画面左侧图2年轻男子坐在枣红实木餐桌前神色冷静审视，桌面上刚被丢下一件叠皱的发黄旧帆布围裙；"
                "画面右侧图3高马尾女生站在桌旁双手抱胸、眉头紧皱满脸嫌弃与抱怨。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-2-07",
            "refs": [
                amap["沙正街林家食府老店大堂"]["main_1k"],
                amap["楚南"]["front_1k"],
                amap["林双双"]["front_1k"],
                amap["叶寻"]["front_1k"],
            ],
            "prompt": (
                "以图1的2005年餐馆傍晚大堂为环境，严格保持图2年轻男生、图3高马尾女生、图4深藏青夹克男生的五官、发型及穿搭与各自参考图完全一致。"
                "中景三人同框构图：画面中间图2男生刚从门口走进坐在邻桌旁，右手食指得意晃动一串带塑料牌的寝室钥匙串正侃侃而谈；"
                "画面右侧图3高马尾女生眼睛发亮满脸崇拜倾听；画面左侧图4深藏青夹克男生静坐桌边神色淡漠冷眼旁观。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-2-10",
            "refs": [
                amap["沙正街林家食府老店大堂"]["main_1k"],
                amap["楚南"]["front_1k"],
                amap["林双双"]["front_1k"],
                amap["叶寻"]["front_1k"],
            ],
            "prompt": (
                "以图1的2005年餐馆傍晚收银柜台与餐桌旁为环境，严格保持图2男生、图3高马尾女生、图4深藏青夹克男生的五官、发型及穿搭与各自参考图完全一致。"
                "中近景戏剧冲突构图：画面右侧图2男生嘴角挂着居高临下的戏谑冷笑，右手两指拈起一颗灰黑色金属刷锅钢丝球递到画面左侧图4深藏青夹克男生面前；"
                "中景偏右图3高马尾女生昂着下巴理所当然地看着图4男生；图4男生站起身神色平静锐利。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-2-13",
            "refs": [
                amap["沙正街林家食府老店大堂"]["main_1k"],
                amap["叶寻"]["front_1k"],
                amap["楚南"]["front_1k"],
                amap["林双双"]["front_1k"],
            ],
            "prompt": (
                "以图1的2005年餐馆傍晚大堂门口逆光夕阳为环境，严格保持图2深藏青夹克男生、图3男生、图4高马尾女生的五官、发型及穿搭与各自参考图完全一致。"
                "中近景反击构图：画面左侧图2深藏青夹克男生眼神清冷决绝，正将那件发黄旧帆布围裙裹住钢丝球，稳稳塞回画面中间图3男生摊开的掌心里；"
                "图3男生笑容僵住满脸错愕，右侧图4高马尾女生愣在原地脸色骤变。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-2-16",
            "refs": [
                amap["沙正街林家食府老店大堂"]["main_1k"],
                amap["叶寻"]["front_1k"],
                amap["楚南"]["front_1k"],
                amap["林双双"]["front_1k"],
            ],
            "prompt": (
                "以图1的2005年餐馆敞开的双扇木门与门外橘红黄昏街口为环境，严格保持图2深藏青夹克男生、图3男生、图4高马尾女生的五官、发型及穿搭与各自参考图完全一致。"
                "中全景纵深离场构图：后景店内木桌旁，图3男生把旧围裙摔在桌上嗤笑，图4高马尾女生冲门口气急冷喊；"
                "前景敞开的木门槛处，图2深藏青夹克男生挺直脊背大步跨出门槛走进温暖橘红暮色中，头也不回。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-3-01",
            "refs": [
                amap["重庆大学外沙正街黄昏老街"]["main_1k"],
                amap["叶寻"]["front_1k"],
            ],
            "prompt": (
                "以图1的2005年重庆沙正街黄昏老黄葛树与亮起灯箱的青石人行道为环境，严格保持图2深藏青夹克男生的五官、发型及穿搭与参考图完全一致。"
                "中近景平视构图：橘红色晚霞穿过黄葛树叶洒下斑驳光影，图2深藏青夹克男生停步在老树下，双手翻开一本2005年代红色折角储蓄存折低头端详，目光沉静笃定。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-3-04",
            "refs": [
                amap["重庆大学外沙正街黄昏老街"]["main_1k"],
                amap["叶寻"]["front_1k"],
                amap["夏芊芊"]["front_1k"],
            ],
            "prompt": (
                "以图1的2005年沙正街黄昏青石板路与远处街尾暖黄小馆门头为环境，严格保持图2深藏青夹克男生与图3清秀女大学生的五官、发型及整套穿搭与各自参考图完全一致。"
                "中景街头偶遇构图：画面右侧图3清秀女生双臂怀抱两本厚会计课本与一叠大红色传单纸匆匆跑来刚喘气站定；"
                "画面左侧图2深藏青夹克男生及时伸手稳稳托住她怀里险些滑落的课本与红纸，两人面带熟稔关切对视，后景三十米外街尾老小馆亮着暖黄灯光。" + STYLE_TAIL
            ),
        },

        # ==================== EPISODE 2 (10 keyframes for 10 groups) ====================
        {
            "id": "2-1-01",
            "refs": [
                amap["夏氏小厨前厅与传菜口"]["main_1k"],
                amap["夏建国"]["front_1k"],
                amap["老王"]["front_1k"],
            ],
            "prompt": (
                "以图1的2005年夏氏小厨前厅算盘木柜台与传菜口为环境，严格保持图2右腕缠白绷带的藏青唐装中年大叔与图3浅灰短袖中厨服微胖男厨师的五官、发型及穿搭与各自参考图完全一致。"
                "中景戏剧冲突构图：柜台前水泥地上散落几片摔碎的白瓷盘碎片，画面左侧图2右腕缠白绷带的大叔用左手撑住实木算盘柜台，气得脸色涨红胸口起伏；"
                "画面右侧传菜木台边，图3男厨师右手按在插于木台砧板上的宽背菜刀柄上，昂头眯眼满脸市侩嚣张地逼视索要。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-1-04",
            "refs": [
                amap["夏氏小厨前厅与传菜口"]["main_1k"],
                amap["夏芊芊"]["front_1k"],
                amap["夏建国"]["front_1k"],
                amap["老王"]["front_1k"],
                amap["中年食客"]["front_1k"],
            ],
            "prompt": (
                "以图1的2005年夏氏小厨前厅木方桌与柜台为环境，严格保持图2清秀女生、图3右腕缠白绷带大叔、图4灰白中厨服男厨师、图5戴细框眼镜Polo衫中年食客的五官、发型及穿搭与各自参考图完全一致。"
                "中全景前厅冲突构图：后景左柜台旁图2女生刚冲进店护在图3受伤父亲身前，中景偏右图4男厨师正一把扯下腰间深蓝围裙摔在木台上冷笑；"
                "前景右侧平顶木方桌旁，图5戴眼镜中年食客左手夹起一只黑色皮手包刚从长条凳站起身准备离开。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-1-07",
            "refs": [
                amap["夏氏小厨前厅与传菜口"]["main_1k"],
                amap["叶寻"]["front_1k"],
                amap["中年食客"]["front_1k"],
                amap["夏芊芊"]["front_1k"],
                amap["老王"]["front_1k"],
                amap["夏建国"]["front_1k"],
            ],
            "prompt": (
                "以图1的2005年夏氏小厨前厅门口与木方桌为环境，严格保持图2深藏青夹克男生、图3戴眼镜中年食客、图4清秀女生、图5灰白短袖男厨师、图6右腕缠绷带大叔的五官、发型及穿搭与参考图一致。"
                "中景救场构图：画面左前景图2深藏青夹克男生大步跨进店门，沉稳抬手示意画面中间木方桌旁的图3戴眼镜食客坐下喝茶；"
                "后景柜台旁图6受伤大叔与图4女生面露惊喜，右侧图5灰白短袖男厨师双手抱臂满脸轻蔑嗤笑。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-2-01",
            "refs": [
                amap["夏氏小厨后厨猛火炒灶"]["main_1k"],
                amap["叶寻"]["front_1k"],
                amap["夏建国"]["front_1k"],
            ],
            "prompt": (
                "以图1的2005年老街小炒馆传统后厨（原木备菜案板、红泡椒仔姜青花碗、红砖猛火炒灶）为环境，严格保持图2深藏青夹克男生（袖口利落挽至小臂）与图3右腕缠白绷带大叔的五官、发型及穿搭与参考图一致。"
                "中近景后厨传承构图：画面左侧厚实原木案板前，图2男生挽起夹克袖口，右手稳稳握起一把木柄包铜传统中式宽背厨刀准备切配案板上的鲜润猪肝与鸭胗；"
                "画面右侧后厨门边，图3右腕缠白绷带的大叔看着他手里的老厨刀神情唏嘘感慨。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-2-04",
            "refs": [
                amap["夏氏小厨后厨猛火炒灶"]["main_1k"],
                amap["叶寻"]["front_1k"],
            ],
            "prompt": (
                "以图1的2005年老街小馆红砖商用猛火大铁锅炒灶为环境，严格保持图2深藏青夹克男生（袖口挽至小臂）的五官、发型及穿搭与参考图完全一致。"
                "中近景极具视觉冲击力的猛火颠勺构图：红砖灶台上的黑铁大炒锅内红亮泡椒、嫩黄仔姜与滑嫩猪肝翻飞，橘金色猛烈灶火窜起半米高映亮图2男生专注利落的脸庞，他左手稳托铁锅木柄凌空翻勺，浓郁鲜香白气升腾。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-2-07",
            "refs": [
                amap["夏氏小厨前厅与传菜口"]["main_1k"],
                amap["中年食客"]["front_1k"],
                amap["叶寻"]["front_1k"],
                amap["夏芊芊"]["front_1k"],
            ],
            "prompt": (
                "以图1的2005年夏氏小厨前厅平顶老榆木方桌（无火锅孔洞）为环境，严格保持图2戴细框眼镜中年食客、图3深藏青夹克男生、图4清秀女生的五官、发型及穿搭与各自参考图完全一致。"
                "中近景上菜品鉴构图：前景木方桌上刚摆上两盘热气腾腾、色泽红亮油润的泡椒炒猪肝与仔姜爆鸭杂，图2戴眼镜食客端坐在桌前右手执竹筷夹起一片鲜嫩猪肝送入口中，镜片后的双眼骤然瞪亮满脸惊艳赞叹；"
                "中景桌旁图3男生与端着白瓷盘清炒莲白的图4女生微笑注视。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-2-10",
            "refs": [
                amap["夏氏小厨前厅与传菜口"]["main_1k"],
                amap["夏建国"]["front_1k"],
                amap["老王"]["front_1k"],
            ],
            "prompt": (
                "以图1的2005年夏氏小厨前厅木算盘柜台与店门口为环境，暖黄白炽灯下充满晚市热闹烟火气，严格保持图2右腕缠白绷带藏青唐装大叔与图3灰白短袖男厨师的五官、发型及穿搭与参考图完全一致。"
                "中景扬眉吐气逐客构图：画面左侧木柜台后，图2右腕缠白绷带的大叔满脸畅快硬气，正用未受伤的左手将柜台上一叠红色传单纸狠狠攥成纸团扔向脚边废纸篓，抬眼朝门口送客；"
                "画面右侧店门框边，图3灰白短袖男厨师脸色涨红难堪、灰溜溜准备转身跨出门外。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-3-01",
            "refs": [
                amap["夏氏小厨前厅与传菜口"]["main_1k"],
                amap["夏芊芊"]["front_1k"],
                amap["夏建国"]["front_1k"],
                amap["叶寻"]["front_1k"],
            ],
            "prompt": (
                "以图1的2005年夏氏小厨深夜打烊前厅（店门卷帘拉下一半、头顶暖黄白炽灯亮着、墙角立着闲置生铁大圆锅）为环境，严格保持图2清秀女生、图3右腕缠绷带大叔、图4深藏青夹克男生的五官、发型及穿搭与参考图完全一致。"
                "中近景深夜对坐算账构图：老木方桌上放着一把老式木算盘与翻开的牛皮纸账本，画面右侧图2女生手指轻按算盘框、垂眸看着账本轻轻叹气；"
                "中间图3受伤大叔愁眉紧锁，左侧图4深藏青夹克男生安静坐在桌边专注倾听。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-3-04",
            "refs": [
                amap["夏氏小厨前厅与传菜口"]["main_1k"],
                amap["叶寻"]["front_1k"],
                amap["夏芊芊"]["front_1k"],
                amap["夏建国"]["front_1k"],
            ],
            "prompt": (
                "以图1的2005年夏氏小厨深夜前厅（后景墙角可见那口闲置生铁双耳大圆锅）为环境，严格保持图2深藏青夹克男生、图3清秀女生、图4右腕缠绷带大叔的五官、发型及穿搭与参考图完全一致。"
                "中近景拍存折入伙构图：画面左侧图2深藏青夹克男生站起身探向桌面，右手果断将一本2005年代红色储蓄存折重重拍在牛皮纸账本旁，目光灼灼充满笃定底气；"
                "画面右侧桌边图4受伤大叔猛地抬头满眼震动，图3清秀女生微怔看向桌上的红存折。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-3-07",
            "refs": [
                amap["夏氏小厨前厅与传菜口"]["main_1k"],
                amap["夏芊芊"]["front_1k"],
                amap["叶寻"]["front_1k"],
                amap["夏建国"]["front_1k"],
            ],
            "prompt": (
                "以图1的2005年夏氏小厨深夜暖黄白炽灯前厅木桌为环境，严格保持图2清秀女生、图3深藏青夹克男生、图4右腕缠绷带大叔的五官、发型及穿搭与参考图完全一致。"
                "中近景高张力悬念对视构图：桌面摆放着木算盘、账本与红色存折，画面右侧图2清秀女生右手五指微收紧紧按住账本边缘，抬起清醒锐利而审视的目光直直盯住对面的图3男生；"
                "画面左侧图3男生坦然迎上她的目光，中间后侧图4受伤大叔屏息紧张望着两人。" + STYLE_TAIL
            ),
        },
    ]


def build_contact_sheet(ids: list, out_jpg: Path):
    cols = 4
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
    print(f"Prepared {len(amap)} <=1K assets & clean voices in {ASSETS_1K}", flush=True)
    specs = make_specs(amap)
    print(f"Generating {len(specs)} 2K/1K keyframes with 5 parallel workers...", flush=True)
    with ThreadPoolExecutor(max_workers=5) as pool:
        futs = {pool.submit(run_one, s): s["id"] for s in specs}
        for f in as_completed(futs):
            kid, dt, sz = f.result()
            print(f"  [kf] {kid} done in {dt}s -> 1K={sz}", flush=True)

    ep1_ids = [s["id"] for s in specs if s["id"].startswith("1-")]
    ep2_ids = [s["id"] for s in specs if s["id"].startswith("2-")]
    build_contact_sheet(ep1_ids, WORK_DIR / "ep01_v2_keyframes_sheet.jpg")
    build_contact_sheet(ep2_ids, WORK_DIR / "ep02_v2_keyframes_sheet.jpg")
    print("Contact sheets saved!", flush=True)


if __name__ == "__main__":
    main()
