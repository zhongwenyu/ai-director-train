#!/usr/bin/env python3
"""
Pre-compress all Episode 1 & Episode 2 hotpot_v3 assets to <=1K (keeping 2K originals untouched in studio_media),
generate 1 seamless apronless variant portrait of Ye Xun (matching his dark charcoal rolled-sleeve pullover in 1-1
when he rips off his brown apron in 1-1-05 and crosses into Xia's courtyard in 1-2),
and generate all 18 2K/1K blocking keyframes (9 for Ep 1 + 9 for Ep 2).
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
WORK_DIR = Path("/home/zhongwenyu/project/ai-director-train/productions/2005_chongqing_hotpot_v3/ep01_02_video_gen")
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
        "林双双",
        "楚南",
        "林有才",
        "周有福",
        "陈科长",
        "沙正街林家食府老店大堂",
        "桂花巷渝清记大堂与天井",
        "重庆老街对门双火锅铺街景",
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
    amap["叶寻 · 渝清记围裙掌勺"]["voice"] = amap["叶寻"]["voice"]
    amap["林有才"]["voice"] = str(find_media_file("d7b6d049-8fbc-4f8c-9855-2445a9d4d7a0"))
    amap["周有福"]["voice"] = "/home/zhongwenyu/project/ai-director-train/productions/2005_chongqing_hotpot_v3/voices/zhou_director_clean.wav"

    # Generate seamless apronless portrait of Ye Xun in the exact same rolled-sleeve dark charcoal pullover + dark jeans
    no_apron_2k = ASSETS_1K / "yexun_charcoal_no_apron_2k.png"
    no_apron_1k = ASSETS_1K / "yexun_charcoal_no_apron_1k.png"
    if not no_apron_2k.is_file() or not no_apron_1k.is_file():
        print("[portrait] Generating seamless apronless charcoal-pullover front portrait for Ye Xun...", flush=True)
        vtrix_image.generate_vtrix_image(
            prompt=(
                "纯白干净背景人物正面全身定妆照。严格保持图1年轻中国男子的五官脸型、清爽短发、水洗炭黑色挽袖圆领长袖卫衣、深炭灰直筒工装裤与深色运动鞋完全一致，"
                "仅去掉脖子上搭着的白毛巾与身前的棕色围裙，双手自然垂放身侧（右手手背带一道浅淡旧烫痕），姿态挺拔沉稳，写实摄影棚柔光质感，严禁任何文字或分格。"
            ),
            out_path=no_apron_2k,
            ref_files=[amap["叶寻 · 渝清记围裙掌勺"]["front_1k"]],
            aspect_ratio="9:16",
            resolution="2K",
        )
        compress_image_to_1k(no_apron_2k, no_apron_1k, max_side=1024)

    amap["叶寻_脱围裙"] = {
        "id": amap["叶寻"]["id"],
        "type": "character",
        "front_2k": str(no_apron_2k),
        "front_1k": str(no_apron_1k),
        "voice": amap["叶寻"]["voice"],
    }

    (WORK_DIR / "asset_map.json").write_text(json.dumps(amap, ensure_ascii=False, indent=2), encoding="utf-8")
    return amap


STYLE_TAIL = (
    "精致电影实拍质感，竖屏9:16中近景或中景腰部以上为主构图（避免人物过小或底部大片空地），真实光影层次与皮肤衣料纹理，人物与环境透视比例准确，"
    "严禁出现任何屏幕字幕、台词文字、水印、分格边框或纯白拼图底。"
)


def make_specs(amap: dict) -> list:
    lin_hall = amap["沙正街林家食府老店大堂"]["main_1k"]
    xia_yard = amap["桂花巷渝清记大堂与天井"]["main_1k"]
    dual_street = amap["重庆老街对门双火锅铺街景"]["main_1k"]
    lin_kitchen = amap["夏氏小厨后厨猛火炒灶"]["main_1k"]

    f_ye_apron = amap["叶寻 · 渝清记围裙掌勺"]["front_1k"]
    f_ye_clean = amap["叶寻_脱围裙"]["front_1k"]
    f_qian = amap["夏芊芊"]["front_1k"]
    f_lin = amap["林双双"]["front_1k"]
    f_chu = amap["楚南"]["front_1k"]
    f_youcai = amap["林有才"]["front_1k"]
    f_zhou = amap["周有福"]["front_1k"]
    f_chen = amap["陈科长"]["front_1k"]

    return [
        # ==================== EPISODE 1 (9 keyframes) ====================
        {
            "id": "1-1-01",
            "refs": [lin_hall, f_ye_apron, f_lin, f_chu],
            "prompt": (
                "以图1的2005年重庆老餐馆夜晚暖黄灯光大堂（头顶吊扇转动，木圆桌上沸腾热气）为环境，严格保持图2系棕色帆布围裙年轻男子、图3米白套裙女子、图4黑西装花衬衫男子的五官、发型及穿搭完全一致。"
                "中近景腰部以上三人戏剧冲突构图：画面左侧图2围裙男子双手刚把一盆色泽红亮醇厚的火锅底料端放上枣红木桌；"
                "画面右侧图3米白套裙女子亲昵挽着图4黑西装男子的手臂走近，图3女子一手嫌弃掩住鼻端、另一手把半页泛黄手写纸张傲慢拍在图2男子胸口。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-1-02",
            "refs": [lin_hall, f_ye_apron, f_chu, f_lin],
            "prompt": (
                "以图1的2005年重庆餐馆夜晚暖黄大堂为环境，严格保持图2系棕色围裙年轻男子、图3黑西装花衬衫男子、图4米白套裙女子的五官、发型及穿搭完全一致。"
                "中近景前景特写对峙构图：左前景图2围裙男子猛然怔住，低头看清自己右手手背旧烫痕与指间捏着的那半页泛黄手写纸，眼神骤然清醒锐利；"
                "右中景图3黑西装男子单手揽着图4米白套裙女子的肩膀，满脸居高临下的讥诮冷笑。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-1-03",
            "refs": [lin_hall, f_youcai, f_ye_apron, f_lin],
            "prompt": (
                "以图1的2005年重庆餐馆夜晚枣红实木餐桌前为环境，桌面放着一只装满清水的透明玻璃凉水壶，严格保持图2暗红唐装中年男子、图3系棕色围裙年轻男子、图4米白套裙女子的五官、发型及穿搭完全一致。"
                "中近景桌面交锋构图：画面左侧图2暗红唐装中年男子左手端着青花盖碗茶，右手屈起指节重重敲击桌面逼视；"
                "画面中间偏右图3围裙男子眼神冷冽，双手捏起那半页泛黄纸张置于玻璃凉水壶正上方准备撕碎，右侧图4米白套裙女子神情傲慢。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-1-04",
            "refs": [lin_hall, f_ye_apron, f_lin, f_youcai],
            "prompt": (
                "以图1的2005年重庆餐馆夜晚实木餐桌前为环境，桌面玻璃凉水壶里漂着碎纸屑，严格保持图2系棕色围裙年轻男子、图3米白套裙女子、图4暗红唐装中年男子的五官、发型及穿搭完全一致。"
                "中近景拍单打脸构图：画面左侧图2围裙男子左手拿着一只掉漆铁盒，右手重重将厚厚一沓2005年代淡绿粉边邮政汇款存根单据拍在木桌面上，目光冷峻如刀；"
                "画面右侧图3米白套裙女子脸色涨红慌乱低头盯着满桌存根，后侧图4暗红唐装男子脸色骤变。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-1-05",
            "refs": [lin_hall, f_ye_clean, f_youcai, f_lin],
            "prompt": (
                "以图1的2005年重庆餐馆夜晚敞开的木门与竹编废纸篓旁为环境，严格保持图2穿炭黑色挽袖圆领长袖卫衣的年轻男子、图3暗红唐装中年男子、图4米白套裙女子的五官、发型及穿搭完全一致。"
                "中景决绝撤火离场构图：画面左侧门口图2炭黑卫衣年轻男子刚扯下棕色旧围裙与白毛巾甩向脚边竹篓，神情冷硬果决准备跨出门外；"
                "画面右侧图3暗红唐装中年男子伸手欲拦、气急败坏怒指门口，后侧木桌旁图4米白套裙女子按着汇款单僵立原地。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-2-01",
            "refs": [xia_yard, f_ye_clean, f_qian],
            "prompt": (
                "以图1的2005年重庆老火锅店夜晚暖黄串灯小院（整齐摆放原木火锅桌与黄铜双耳锅，竹筐里盛着洗净的鲜毛肚与青菜）为环境，严格保持图2穿炭黑挽袖卫衣年轻男子与图3系黑色围裙清秀女子的五官、发型及穿搭完全一致。"
                "中近景小院迎客构图：画面左侧图2炭黑卫衣男子刚大步跨进温暖敞亮的小院，眼神温柔笃定；"
                "画面右侧图3系黑围裙的清秀女子欣喜迎上前，怀里抱着一本牛皮纸账本、一支毛笔与一只圆铁盒红印泥。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-2-02",
            "refs": [xia_yard, f_qian, f_ye_clean],
            "prompt": (
                "以图1的2005年重庆火锅小院夜晚暖黄灯光下的原木方桌为环境，严格保持图2系黑围裙清秀女子与图3穿炭黑挽袖卫衣年轻男子的五官、发型及穿搭完全一致。"
                "中近景立契摁手印构图：木桌面上铺着一张刚写好的毛笔宣纸契书与打开盖子的鲜红印泥盒，画面右侧图2清秀女子唇角扬起爽利笑意，刚摁完红手印并将印泥盒推向对面；"
                "画面左侧图3炭黑卫衣男子右手大拇指沾着鲜红印泥，正重重并排摁向契书纸面。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-2-03",
            "refs": [dual_street, f_chu, f_lin, f_qian, f_ye_clean],
            "prompt": (
                "以图1的2005年重庆夜晚灯笼亮起的青石板老街与左侧火锅店敞开木门前为环境，严格保持图2黑西装花衬衫男子、图3米白套裙女子、图4系黑围裙清秀女子、图5炭黑挽袖卫衣男子的五官、发型及穿搭完全一致。"
                "中景堵门挑衅对峙构图：画面右侧青石板街门外，图2黑西装男子晃着老式手机嚣张冷笑，身旁图3米白套裙女子得意扬起手里一张大红纸宴席改签单；"
                "画面左侧门槛内，图4黑围裙女子眉头紧蹙，身旁图5炭黑卫衣男子神色沉静冷冽并肩迎视。" + STYLE_TAIL
            ),
        },
        {
            "id": "1-2-04",
            "refs": [dual_street, f_ye_clean, f_qian],
            "prompt": (
                "以图1的2005年重庆夜晚暖黄街灯下的青石板老街与左侧火锅铺门前为环境，严格保持图2穿炭黑挽袖卫衣年轻男子与图3系黑围裙清秀女子的五官、发型及穿搭完全一致。"
                "中景蹬三轮车出发构图：左侧火锅铺门前青石板路上停着一辆老式铁架平板人力三轮车，图2炭黑卫衣男子双手稳稳握紧三轮车车把、跨坐车座回首招呼，眼神锐利果敢；"
                "图3黑围裙女子眼睛发亮，双手扶住平板车斗边缘正轻快坐上后车斗准备出发。" + STYLE_TAIL
            ),
        },

        # ==================== EPISODE 2 (9 keyframes) ====================
        {
            "id": "2-1-01",
            "refs": [dual_street, f_ye_apron, f_qian],
            "prompt": (
                "以图1的2005年重庆清晨天光微亮的青石板老街左侧火锅铺门前两口红砖生铁大锅为环境，严格保持图2系棕色帆布围裙年轻男子与图3系黑色围裙清秀女子的五官、发型及穿搭完全一致。"
                "中近景晨光现炼牛油构图：清透晨光洒在青石板街上，左侧生铁大锅内一块块雪白新鲜牛板油正慢火熬出清亮金黄油花，图2棕色围裙男子双手执长柄铜勺稳稳翻搅；"
                "右侧木案旁图3黑色围裙女子双手托着洁白细纱布，正将淡青金色草本清液滤入粗陶盆中，两人默契相视。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-1-02",
            "refs": [lin_kitchen, f_youcai, f_lin],
            "prompt": (
                "以图1的2005年传统餐馆昏暗老旧后厨红砖铁锅灶台为环境，严格保持图2暗红唐装中年男子与图3米白套裙女子的五官、发型及穿搭完全一致。"
                "中近景后厨炸糊草药构图：右侧红砖灶上的大铁锅内发黑陈年老油剧烈翻滚，干枯栀子与罗汉果壳刚下锅便炸得焦黑并窜起一股呛人灰黑青烟，图2暗红唐装男子左手捏着皱巴巴的偷师纸条、右手握铁勺强自镇定；"
                "左侧图3米白套裙女子被呛得皱眉伸手在鼻前扇风，神色焦急。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-1-03",
            "refs": [dual_street, f_ye_apron, f_qian],
            "prompt": (
                "以图1的2005年重庆正午阳光明媚的青石板老街左侧火锅铺门前两口生铁大锅为环境，严格保持图2系棕色围裙年轻男子与图3系黑围裙清秀女子的五官、发型及穿搭完全一致。"
                "中近景红汤出锅奇香构图：正午阳光下，生铁大锅内鲜牛油与红亮糍粑海椒醇厚翻滚、升腾起清爽洁白水雾，左侧图2棕色围裙男子左手端粗陶碗淋入草本清液、右手执长柄铜勺撇沫，目光笃定瞥向街对门；"
                "右侧图3黑围裙女子端着一盘铺满碎冰的鲜润毛肚满脸喜悦。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-2-01",
            "refs": [dual_street, f_zhou],
            "prompt": (
                "以图1的2005年重庆白天青石板老街右侧林记火锅门前圆木餐桌为环境，后景虚化坐着几名穿蓝色工装的2005年代机械厂工友，严格保持图2穿暗酒红短袖Polo衫五十岁微壮男子的五官、发型及穿搭完全一致。"
                "中近景尝汤呛咳吐出构图：前景圆木桌中央红锅里翻涌着黑褐色焦糊药渣，图2酒红Polo衫男子坐在主位，左手拿白瓷汤勺、右手捂住嘴剧烈皱眉呛咳嫌恶，桌上工友们纷纷皱眉放下竹筷。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-2-02",
            "refs": [dual_street, f_lin, f_qian, f_ye_apron, f_zhou],
            "prompt": (
                "以图1的2005年重庆白天青石板老街两家对门火锅铺之间的街心为环境，严格保持图2米白套裙女子、图3系黑围裙清秀女子、图4系棕色围裙年轻男子、图5酒红Polo衫中年男子的五官、发型及穿搭完全一致。"
                "中景当街端汤叫板构图：画面右侧餐桌边图2米白套裙女子双手端着一壶深色酸梅汤正朝坐着的图5酒红Polo衫男子陪笑解释；"
                "画面左侧青石板街心，图3黑围裙清秀女子双手稳稳端着一口盛满红亮清透汤底的双耳黄铜小锅大步走来，图4棕色围裙年轻男子手执长柄铜勺并肩而立。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-2-03",
            "refs": [dual_street, f_youcai, f_ye_apron, f_qian],
            "prompt": (
                "以图1的2005年重庆白天青石板老街两铺对门街心（左后方敞开院门内可见整齐圆木桌与鲜菜碗筷）为环境，严格保持图2暗红唐装中年男子、图3系棕色围裙年轻男子、图4系黑围裙清秀女子的五官、发型及穿搭完全一致。"
                "中近景当街对质构图：画面右侧图2暗红唐装男子满脸慌张伸手指着对门狡辩；"
                "画面左侧图3棕色围裙男子挺胸执铜勺沉稳回应，身旁图4黑围裙女子侧身让开身后整齐备好菜品的火锅小院大门，神色坦荡自信。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-2-04",
            "refs": [dual_street, f_zhou, f_qian, f_ye_apron],
            "prompt": (
                "以图1的2005年重庆白天青石板老街心与左侧敞亮火锅小院门前为环境，后景多名穿蓝工装的工友纷纷起身，严格保持图2酒红Polo衫中年男子、图3系黑围裙清秀女子、图4系棕色围裙年轻男子的五官、发型及穿搭完全一致。"
                "中近景试汤惊艳挥手过街构图：画面中央图2酒红Polo衫男子左手端着盛有透亮红汤的小白碗与竹筷，尝完毛肚后双眼大亮满脸赞叹，右手豪迈一挥招呼身后工友过街入席；"
                "左侧图3黑围裙女子端着铜锅与图4棕色围裙男子微笑迎客。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-2-05",
            "refs": [dual_street, f_chen, f_lin, f_chu, f_ye_apron],
            "prompt": (
                "以图1的2005年重庆白天青石板老街左侧火锅铺两口生铁大锅前为环境，严格保持图2穿白色短袖制服衬衫系深蓝领带的年轻执法科长、图3米白套裙女子、图4黑西装花衬衫男子、图5系棕色围裙年轻男子的五官、发型及穿搭完全一致。"
                "中近景举报查验冲突构图：画面中间偏右图2白衬衫制服科长神色严肃公正，右手亮出深蓝色执法证件夹走到铁锅前；"
                "右后侧图3米白套裙女子与图4黑西装男子幸灾乐祸直指铁锅举报，画面左侧图5棕色围裙男子立在沸腾红汤铁锅旁神色镇定。" + STYLE_TAIL
            ),
        },
        {
            "id": "2-2-06",
            "refs": [dual_street, f_chu, f_ye_apron, f_qian, f_chen],
            "prompt": (
                "以图1的2005年重庆白天青石板老街左侧火锅铺铁锅灶台前为环境，院内食客停筷观望，严格保持图2黑西装花衬衫男子、图3系棕色围裙年轻男子、图4系黑围裙清秀女子、图5白衬衫深蓝领带制服科长的五官、发型及穿搭完全一致。"
                "中近景高张力悬念定格构图：画面右侧图2黑西装男子抱臂指向对门嚣张揽客，中景图5白衬衫制服科长手持采样管等待快检；"
                "画面左侧铁锅前，图4黑围裙女子神情紧绷，图3棕色围裙男子沉稳伸手按住她的手背安抚，另一手从容关掉炉火迎上检查目光。" + STYLE_TAIL
            ),
        },
    ]


def build_contact_sheet(ids: list, out_jpg: Path):
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
    build_contact_sheet(ep1_ids, WORK_DIR / "ep01_v3_keyframes_sheet.jpg")
    build_contact_sheet(ep2_ids, WORK_DIR / "ep02_v3_keyframes_sheet.jpg")
    print("Contact sheets saved!", flush=True)


if __name__ == "__main__":
    main()
