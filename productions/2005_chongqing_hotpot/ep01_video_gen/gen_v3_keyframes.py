#!/usr/bin/env python3
"""Generate the 2 generalized-rule keyframes:
1. 1-2-01_aftermath: Post-impact crash aftermath (limp hand + tumbled grey canvas knife roll in rain puddle under car lights)
2. 1-4-01_solo: Initial-presence t=0.0s keyframe (ONLY Xia Qianqian bracing the tilting chili handcart; Ye Xun NOT in frame yet!)
"""
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

STUDIO_BRIDGE = Path("/home/zhongwenyu/project/playlets-studio/skills/studio-bridge/scripts")
SKILL_SCRIPTS = Path("/home/zhongwenyu/project/ai-director-train/.agents/skills/hit-video/scripts")
sys.path.insert(0, str(STUDIO_BRIDGE))
sys.path.insert(0, str(SKILL_SCRIPTS))

import vtrix_image  # noqa: E402
from compress_1k import compress_image_to_1k  # noqa: E402

WORK_DIR = Path("/home/zhongwenyu/project/ai-director-train/productions/2005_chongqing_hotpot/ep01_video_gen")
KF_2K_DIR = WORK_DIR / "keyframes_2k"
KF_1K_DIR = WORK_DIR / "keyframes_1k"
asset_map = json.loads((WORK_DIR / "ep01_asset_map.json").read_text(encoding="utf-8"))

STYLE_TAIL = (
    "明亮清晰电影实拍质感，竖屏9:16构图，自然真实光影与材质纹理，手部与肢体解剖结构准确，"
    "严禁出现任何文字、字幕、水印、分格边框或拼图白底。"
)

SPECS = [
    {
        "id": "1-2-01_aftermath",
        "refs": [
            asset_map["集团大厦旋转门雨夜街口"]["main_1k"],
            asset_map["叶寻 · 2015行政总厨"]["front_1k"],
        ],
        "prompt": (
            "以图1的暴雨夜柏油路积水街面为环境，保持图2人物袖口与服装完全一致。"
            "低机位地面特写：倾盆大雨的湿滑柏油路积水洼中，右侧停着刺目白色车头大灯与红色刹车灯倒影，黑色轮胎紧贴积水边缘；"
            "画面左下方，图2人物昏迷倒在雨水中（仅露出肩臂与右手），他湿透的右前臂与虎口带旧烫疤的右手无力瘫软垂落在积水路面上；"
            "画面中央偏右的积水洼里，一卷摔散半开的深灰色旧帆布厨刀卷泡在雨水里，密集雨滴在车灯逆光下溅起水花，极具车祸重创后的悲怆真实感。" + STYLE_TAIL
        ),
    },
    {
        "id": "1-4-01_solo",
        "refs": [
            asset_map["重庆大学A区校门梧桐坡道"]["main_1k"],
            asset_map["夏芊芊"]["front_1k"],
        ],
        "prompt": (
            "以图1的秋日暖阳梧桐树青石板斜坡与远处民国风大学校门牌坊为场景，严格保持图2年轻女孩的五官面容、发型与整套服装和参考图完全一致。"
            "中景平视单人遇险构图（画面中只有图2这一个人，左侧坡道留出空位供后续他人入画，严禁出现第二个主要人物）："
            "青石板斜坡右侧，一辆装载鼓囊囊干辣椒麻袋的旧木板车右侧木轮死死卡进路沿排水石缝，整辆板车向右侧路沟剧烈倾斜欲翻；"
            "图2的年轻女孩独自站在板车前方偏右，双手拼命死拽两根木车把、双腿蹬地吃力压住重心防止翻车，额角渗出细汗，神色焦急吃力。" + STYLE_TAIL
        ),
    },
]


def run_one(sp):
    kid = sp["id"]
    out_2k = KF_2K_DIR / f"{kid}.png"
    out_1k = KF_1K_DIR / f"{kid}_1k.png"
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


with ThreadPoolExecutor(max_workers=2) as pool:
    futs = [pool.submit(run_one, s) for s in SPECS]
    for f in as_completed(futs):
        kid, dt, sz = f.result()
        print(f"[done] {kid} in {dt}s -> 1K={sz}", flush=True)
