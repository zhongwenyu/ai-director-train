#!/usr/bin/env python3
"""Compress Ep1 assets to <=1K and generate 12 blocking keyframes (2K for studio, <=1K for Pika video) in parallel."""
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

RESAMPLE = getattr(Image, "Resampling", Image).LANCZOS

PROJECT_JSON = Path("/home/zhongwenyu/project/playlets-studio/playlets/playlet-mwj57ecn-9658ad48/project.json")
MEDIA_DIR = Path("/home/zhongwenyu/project/playlets-studio/playlets/playlet-mwj57ecn-9658ad48/media")
WORK_DIR = Path("/home/zhongwenyu/project/ai-director-train/productions/2005_chongqing_hotpot/ep01_video_gen")
ASSETS_1K_DIR = WORK_DIR / "assets_1k"
KF_2K_DIR = WORK_DIR / "keyframes_2k"
KF_1K_DIR = WORK_DIR / "keyframes_1k"

for d in (ASSETS_1K_DIR, KF_2K_DIR, KF_1K_DIR):
    d.mkdir(parents=True, exist_ok=True)

proj = json.loads(PROJECT_JSON.read_text(encoding="utf-8"))
assets_by_name = {a["name"]: a for a in proj["assets"]}


def find_media_file(media_id: str) -> Path:
    matches = list(MEDIA_DIR.glob(f"{media_id}.*"))
    if not matches:
        raise FileNotFoundError(f"Missing media file for {media_id}")
    return matches[0]


# 1. Pre-compress all Ep1 assets (both front & sheet for chars, main image for scenes/props, plus copy voice wavs)
EP1_ASSET_NAMES = [
    "双林轩总部顶层试菜厅", "集团大厦旋转门雨夜街口", "沙正街林家食府老店大堂", "重庆大学A区校门梧桐坡道",
    "配方无偿归属确认书与调岗单", "《叶氏本草食单》蓝布线装册", "桂花巷18000元房租催缴单",
    "叶寻 · 2015行政总厨", "林双双 · 2015女董事长", "楚南 · 海归并购总监西装", "赵帆",
    "叶寻", "林双双", "楚南", "夏芊芊", "小石头",
]

asset_map = {}
for name in EP1_ASSET_NAMES:
    a = assets_by_name[name]
    aid = a["id"]
    entry = {"name": name, "id": aid, "type": a["type"]}
    main_src = find_media_file(a["imageId"])
    main_1k = ASSETS_1K_DIR / f"{aid}_main_1k.png"
    compress_image_to_1k(main_src, main_1k, max_side=1024)
    entry["main_2k"] = str(main_src)
    entry["main_1k"] = str(main_1k)
    if a.get("frontImageId"):
        front_src = find_media_file(a["frontImageId"])
        front_1k = ASSETS_1K_DIR / f"{aid}_front_1k.png"
        compress_image_to_1k(front_src, front_1k, max_side=1024)
        entry["front_2k"] = str(front_src)
        entry["front_1k"] = str(front_1k)
    if a.get("voiceSampleId"):
        v_src = find_media_file(a["voiceSampleId"])
        entry["voice_wav"] = str(v_src)
        entry["voice_media_id"] = a["voiceSampleId"]
    asset_map[name] = entry

(WORK_DIR / "ep01_asset_map.json").write_text(json.dumps(asset_map, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Prepared <=1K reference assets for {len(asset_map)} assets.")

# 2. Define 12 Blocking Keyframes (strictly using #front character portraits + scene, ZERO verbal clothing descriptions!)
STYLE_TAIL = (
    "明亮精致电影实拍质感，竖屏9:16构图，自然真实光影与皮肤纹理，手部结构与桌椅人体比例准确，"
    "严禁出现任何文字、字幕、水印、分格边框或拼图白底。"
)

KEYFRAME_SPECS = [
    {
        "id": "1-1-01",
        "role": "shot2_blocking",
        "refs": [
            asset_map["双林轩总部顶层试菜厅"]["main_1k"],
            asset_map["叶寻 · 2015行政总厨"]["front_1k"],
            asset_map["楚南 · 海归并购总监西装"]["front_1k"],
            asset_map["赵帆"]["front_1k"],
            asset_map["林双双 · 2015女董事长"]["front_1k"],
        ],
        "prompt": (
            "以图1的顶层试菜厅为场景，严格保持图2、图3、图4、图5四位人物各自的五官面容、发型与整套服装和对应参考图完全一致。"
            "中近景平视四人同框站位：白色大理石长试菜台后方，图2的年轻男子站在画面左侧面朝右侧，左胸前吸扣着一枚黑金长方形小铭牌，神情错愕微僵；"
            "图3的男子站在画面中间偏左，右手正伸向图2男子左胸的铭牌嘴角带冷笑；图4的男子紧挨在图3男子右后侧得意抱臂旁观；"
            "图5的女子站在画面最右侧台边，正低头把一叠白纸文件塞进台面上的黑色皮质公文包里。" + STYLE_TAIL
        ),
    },
    {
        "id": "1-1-04",
        "role": "shot1_firstframe",
        "refs": [
            asset_map["双林轩总部顶层试菜厅"]["main_1k"],
            asset_map["叶寻 · 2015行政总厨"]["front_1k"],
            asset_map["赵帆"]["front_1k"],
        ],
        "prompt": (
            "以图1的顶层试菜厅为场景，严格保持图2、图3两位人物各自的五官面容、发型与整套服装和对应参考图完全一致。"
            "中近景微俯拍：白色大理石试菜台中央嵌着一口沸腾翻滚的紫铜红汤火锅，映出暖红光；"
            "图3的男子站在画面右侧锅边，双手端起一只装满浓白淡奶油的玻璃奶罐悬在红汤锅口正上方准备倾倒，神情敷衍轻佻；"
            "图2的男子站在画面左侧锅边面朝右侧，双目圆睁神情震惊欲上前阻拦，嘴巴闭合。" + STYLE_TAIL
        ),
    },
    {
        "id": "1-1-07",
        "role": "shot1_firstframe",
        "refs": [
            asset_map["双林轩总部顶层试菜厅"]["main_1k"],
            asset_map["叶寻 · 2015行政总厨"]["front_1k"],
            asset_map["楚南 · 海归并购总监西装"]["front_1k"],
            asset_map["赵帆"]["front_1k"],
        ],
        "prompt": (
            "以图1的顶层试菜厅为场景，严格保持图2、图3、图4三位人物各自的五官面容、发型与整套服装和对应参考图完全一致。"
            "中近景平视偏俯角：大理石试菜台中央铜锅里已是泛白混浊汤面，图2的男子站在画面左侧，右手紧按在锅边大理石台面上，目光愤慨盯向右侧；"
            "图3的男子站在画面右侧偏前，右手捏着一张白纸通知单与塑料工牌正高举至图2男子右手上方准备往桌面重拍，面露居高临下的讥诮；"
            "图4的男子站在画面右后方抱臂冷笑旁观。" + STYLE_TAIL
        ),
    },
    {
        "id": "1-1-10",
        "role": "shot1_firstframe",
        "refs": [
            asset_map["双林轩总部顶层试菜厅"]["main_1k"],
            asset_map["林双双 · 2015女董事长"]["front_1k"],
            asset_map["楚南 · 海归并购总监西装"]["front_1k"],
            asset_map["叶寻 · 2015行政总厨"]["front_1k"],
        ],
        "prompt": (
            "以图1的顶层试菜厅为场景，严格保持图2、图3、图4三位人物各自的五官面容、发型与整套服装和对应参考图完全一致。"
            "中近景斜侧角：画面左前景为图4男子的侧肩背虚化剪影，画面中右侧大理石台后站着图2的女子，她身前台面上立着一只已合盖的黑色皮质公文包，双手拇指正搭在公文包两侧黄铜锁扣上，低垂眼帘神情冰冷漠然，双唇闭合；"
            "图3的男子站在图2女子右侧半步处双手插兜嘴角冷笑。" + STYLE_TAIL
        ),
    },
    {
        "id": "1-2-01",
        "role": "shot1_firstframe",
        "refs": [
            asset_map["集团大厦旋转门雨夜街口"]["main_1k"],
            asset_map["叶寻 · 2015行政总厨"]["front_1k"],
        ],
        "prompt": (
            "以图1的大厦旋转玻璃门暴雨夜街口为场景，严格保持图2人物的五官面容、发型与整套服装和参考图完全一致。"
            "中全景平视：深夜瓢泼大雨如帘，左后方大厦旋转玻璃门透出明亮暖金灯光并在积水柏油路面上拉出倒影；"
            "图2的男子刚走出旋转门台阶位于画面中左侧面朝右前方，全身被雨水打湿，双臂在胸前紧紧抱着一卷深灰色旧帆布厨刀卷，低垂目光神情木然失魂，双唇紧闭。" + STYLE_TAIL
        ),
    },
    {
        "id": "1-3-01",
        "role": "shot1_firstframe",
        "refs": [
            asset_map["沙正街林家食府老店大堂"]["main_1k"],
            asset_map["叶寻"]["front_1k"],
            asset_map["林双双"]["front_1k"],
            asset_map["楚南"]["front_1k"],
        ],
        "prompt": (
            "以图1的明亮老店大堂为场景，头顶绿色四叶吊扇与敞开木门透入温暖午后阳光，严格保持图2、图3、图4三位人物各自的五官面容、发型与整套服装和对应参考图完全一致。"
            "中近景平视：一张深红棕圆木餐桌旁（桌面高度在坐姿人物腰腹处，三人双肩与完整上半身均清晰露在桌面之上），"
            "图2的年轻男子坐在画面左侧木椅上，身侧斜挎一只军绿色帆布包，此刻双眼紧闭眉头微蹙仿佛刚从噩梦惊醒前一瞬；"
            "圆桌右侧坐着图3的年轻女子与图4的年轻男子，图4男子右手食指挂着一串车钥匙正看向图3女子。" + STYLE_TAIL
        ),
    },
    {
        "id": "1-3-04",
        "role": "shot1_firstframe",
        "refs": [
            asset_map["沙正街林家食府老店大堂"]["main_1k"],
            asset_map["楚南"]["front_1k"],
            asset_map["林双双"]["front_1k"],
            asset_map["叶寻"]["front_1k"],
        ],
        "prompt": (
            "以图1的明亮老店大堂为场景，严格保持图2、图3、图4三位人物各自的五官面容、发型与整套服装和对应参考图完全一致。"
            "中近景越肩构图：左前景虚化坐姿图4男子的肩背侧影，圆木桌右侧坐着图2的年轻男子与图3的年轻女子（两人上半身完整露于桌面之上）；"
            "图2男子位于画面右侧偏中，右手握着一串车钥匙，神态浮夸嫌弃地微扬下巴准备说话，图3女子坐在中间偏右微皱眉转头听他说话。" + STYLE_TAIL
        ),
    },
    {
        "id": "1-3-07",
        "role": "shot1_firstframe",
        "refs": [
            asset_map["沙正街林家食府老店大堂"]["main_1k"],
            asset_map["林双双"]["front_1k"],
            asset_map["叶寻"]["front_1k"],
        ],
        "prompt": (
            "以图1的明亮老店大堂为场景，严格保持图2、图3两位人物各自的五官面容、发型与整套服装和对应参考图完全一致。"
            "中近景双人对坐越肩视角：画面左前景为坐姿图3男子的沉静侧肩与搭在腿侧军绿帆布包铜扣上的右手；"
            "圆木桌右中景坐着图2的年轻女子（完整上半身露于桌面之上，桌右角平放着一串黑色车钥匙），她双手搭在圆木桌沿，微蹙眉头娇纵挑剔地直视左侧图3男子，双唇微闭欲言。" + STYLE_TAIL
        ),
    },
    {
        "id": "1-3-10",
        "role": "shot1_firstframe",
        "refs": [
            asset_map["沙正街林家食府老店大堂"]["main_1k"],
            asset_map["叶寻"]["front_1k"],
            asset_map["林双双"]["front_1k"],
            asset_map["楚南"]["front_1k"],
        ],
        "prompt": (
            "以图1的明亮老店大堂为场景，严格保持图2、图3、图4三位人物各自的五官面容、发型与整套服装和对应参考图完全一致。"
            "中景平视三人站坐对比：圆木桌左侧，图2的年轻男子已推开木椅挺拔站立，左肩单肩背着扣好铜扣的军绿色帆布包，左手稳扶肩带，神情清冷淡然俯视右下方桌面二人，双唇闭合；"
            "圆木桌右侧，图3的年轻女子与图4的年轻男子仍坐在木椅上仰起头愕然看向站立的图2男子，桌角静置车钥匙。" + STYLE_TAIL
        ),
    },
    {
        "id": "1-3-13",
        "role": "shot1_firstframe",
        "refs": [
            asset_map["沙正街林家食府老店大堂"]["main_1k"],
            asset_map["叶寻"]["front_1k"],
            asset_map["林双双"]["front_1k"],
            asset_map["楚南"]["front_1k"],
        ],
        "prompt": (
            "以图1的明亮老店大堂为场景，严格保持图2、图3、图4三位人物各自的五官面容、发型与整套服装和对应参考图完全一致。"
            "中景大堂纵深构图：画面左后方圆木桌旁坐着脸色铁青的图3女子与错愕的图4男子；"
            "画面中间偏右，单肩背着军绿色帆布包的图2年轻男子已干脆转身背对圆桌，正迈开脚步朝右侧敞开透进灿烂午后阳光的老店木门走去，背影挺拔利落。" + STYLE_TAIL
        ),
    },
    {
        "id": "1-4-01",
        "role": "shot1_firstframe",
        "refs": [
            asset_map["重庆大学A区校门梧桐坡道"]["main_1k"],
            asset_map["叶寻"]["front_1k"],
            asset_map["夏芊芊"]["front_1k"],
        ],
        "prompt": (
            "以图1的秋日暖阳梧桐树青石板斜坡与远处民国风大学校门牌坊为场景，严格保持图2、图3两位人物各自的五官面容、发型与整套服装和对应参考图完全一致。"
            "中景平视双人动态起始帧：青石板斜坡中央一辆装载鼓囊囊干辣椒麻袋的旧木板车右侧木轮卡进路边石缝向右歪斜；"
            "画面右侧，图3的年轻女孩双手死死拽住木板车前车把吃力稳住重心，额角带细汗；"
            "画面左侧，单肩背着军绿帆布包的图2年轻男子快步上前，右手刚稳稳托住下沉的木板车左侧车帮准备发力上抬。" + STYLE_TAIL
        ),
    },
    {
        "id": "1-4-04",
        "role": "shot1_firstframe",
        "refs": [
            asset_map["重庆大学A区校门梧桐坡道"]["main_1k"],
            asset_map["叶寻"]["front_1k"],
            asset_map["夏芊芊"]["front_1k"],
            asset_map["小石头"]["front_1k"],
        ],
        "prompt": (
            "以图1的秋日暖阳梧桐青石板坡道为场景，严格保持图2、图3、图4三位人物各自的五官面容、发型与整套服装和对应参考图完全一致。"
            "中景纵深三人构图：停稳的干辣椒麻袋木板车旁，图2的年轻男子站在画面左侧单手扶着木车帮；"
            "画面中间，图3的年轻女孩正俯身弯腰伸手去捡青石板地面上一张盖有红章的白色纸单，神情微窘；"
            "画面右后方坡道岔巷口，图4的年轻小伙满头大汗正神色惊慌地朝他们飞奔冲来。" + STYLE_TAIL
        ),
    },
]


def gen_one_kf(spec):
    kid = spec["id"]
    out_2k = KF_2K_DIR / f"{kid}.png"
    out_1k = KF_1K_DIR / f"{kid}_1k.png"
    if not out_2k.is_file():
        t0 = time.time()
        vtrix_image.generate_vtrix_image(
            prompt=spec["prompt"],
            out_path=out_2k,
            ref_files=spec["refs"],
            aspect_ratio="9:16",
            resolution="2K",
        )
        dt = round(time.time() - t0, 1)
    else:
        dt = 0.0
    info = compress_image_to_1k(out_2k, out_1k, max_side=1024)
    return {"id": kid, "role": spec["role"], "elapsed_s": dt, "out_2k": str(out_2k), "out_1k": str(out_1k), "size_1k": info["new_size"], "prompt": spec["prompt"]}


results = {}
with ThreadPoolExecutor(max_workers=6) as pool:
    futs = {pool.submit(gen_one_kf, sp): sp["id"] for sp in KEYFRAME_SPECS}
    for fut in as_completed(futs):
        kid = futs[fut]
        res = fut.result()
        results[kid] = res
        print(f"[keyframe] {kid} ({res['role']}) ready in {res['elapsed_s']}s -> 1K={res['size_1k']}", flush=True)

ordered = [results[sp["id"]] for sp in KEYFRAME_SPECS]
(WORK_DIR / "ep01_keyframes_manifest.json").write_text(json.dumps(ordered, ensure_ascii=False, indent=2), encoding="utf-8")

# Build visual contact sheet of all 12 blocking keyframes for inspection
cols, rows = 4, 3
cw, ch = 360, 660
sheet = Image.new("RGB", (cols * cw, rows * ch), (20, 20, 24))
draw = ImageDraw.Draw(sheet)
for idx, sp in enumerate(KEYFRAME_SPECS):
    kid = sp["id"]
    im = Image.open(KF_1K_DIR / f"{kid}_1k.png").convert("RGB")
    im.thumbnail((cw - 16, ch - 44), RESAMPLE)
    cx = (idx % cols) * cw + (cw - im.width) // 2
    cy = (idx // cols) * ch + 8
    sheet.paste(im, (cx, cy))
    draw.text(((idx % cols) * cw + 10, (idx // cols) * ch + ch - 30), f"{kid} ({sp['role']})", fill=(245, 225, 130))

sheet_file = WORK_DIR / "ep01_keyframes_sheet.jpg"
sheet.save(sheet_file, quality=92)
print("Saved keyframe review sheet:", sheet_file)
