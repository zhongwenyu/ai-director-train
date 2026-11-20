#!/usr/bin/env python3
"""Full 2K Asset Pipeline for Episodes 1-10 (44 assets) of playlet-mwj57ecn-9658ad48:
1. Saves ALL project asset images at 2K into playlet-mwj57ecn-9658ad48 (0 writes to studio_global_assets!):
   - Character 5-panel sheets: 2048x1152 (2K 16:9), individual views: 1536x2048 / 2048x2048 (2K)
   - Scene images (14 items): 1152x2048 (2K 9:16, pulled from raw 1440x2560 Spark H3 outputs)
   - Prop images (10 items): 2048x2048 (2K 1:1 pure white RGB 255,255,255, pulled from raw 2048x2048 Spark H3 outputs)
2. Female lead 夏芊芊 -> 夏柠柒 (gd_c02) + Global Costume `gd_c02 · 灰T恤配黑围裙兼职装`.
3. All 9 Major Ep 1-10 Character Assets use outfits from Global Asset Library's Costume Module (`type='costume'`).
4. Leads (叶寻 x3, 夏芊芊 x1) run on Vtrix 2K concurrent pool; Rivals (林双双 x3, 楚南 x2) run 100% on Spark minimaxh3image 2K (0 Vtrix calls).
"""
import concurrent.futures
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from pathlib import Path
from PIL import Image, ImageChops, ImageOps

STUDIO_ROOT = Path("/home/zhongwenyu/project/playlets-studio")
sys.path.insert(0, str(STUDIO_ROOT / "skills" / "studio-bridge" / "scripts"))
import vtrix_image as vi  # noqa: E402
from studio_api import Studio  # noqa: E402

G1 = STUDIO_ROOT / "runtime" / "global-assets-rebuild" / "generated"
G2 = STUDIO_ROOT / "runtime" / "gudeng-assets-rebuild" / "generated"

BASE_DIR = Path("/home/zhongwenyu/project/ai-director-train/productions/2005_chongqing_hotpot/media_gen")
SPECS_FILE = BASE_DIR / "asset_specs.json"
OLD_OUT = BASE_DIR / "outputs"
PILOT_DIR = BASE_DIR / "pilot"
OUT_2K = BASE_DIR / "outputs_2k"
CHAR_2K = OUT_2K / "characters"
SCENE_2K = OUT_2K / "scenes"
PROP_2K = OUT_2K / "props"
SYNC_MJS = str(BASE_DIR / "sync_character_fields.mjs")
NODE_BIN = "/home/zhongwenyu/.local/lib/node-v22.23.4-linux-x64/bin/node"

PROJECT_ID = "playlet-mwj57ecn-9658ad48"
SSH_OPTS = ["-i", str(Path.home() / ".ssh" / "id_ed25519_spark"), "-o", "BatchMode=yes"]
SPARK_HOST = "admin@192.168.0.149"
COMFY_DIR = "/home/admin/minimax-h3-image/ComfyUI"
RESAMPLE = getattr(Image, "Resampling", Image).LANCZOS
PRINT_LOCK = threading.Lock()
SYNC_LOCK = threading.Lock()
VTRIX_SEM = threading.Semaphore(12)

# Exact 2x 2K layout matching compose-character-sheet.py (2048x1152)
PANELS_2K = [
    ("torsoFront", 0, 0, 528, 1152),
    ("torsoSide", 528, 0, 440, 1152),
    ("back", 968, 0, 440, 1152),
    ("faceFront", 1408, 0, 640, 576),
    ("faceLeft", 1408, 576, 640, 576),
]


def log(msg: str):
    with PRINT_LOCK:
        print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def to_white_rgb(im: Image.Image) -> Image.Image:
    im = ImageOps.exif_transpose(im)
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        rgba = im.convert("RGBA")
        bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        return Image.alpha_composite(bg, rgba).convert("RGB")
    return im.convert("RGB")


def snap_white(rgb: Image.Image) -> Image.Image:
    px = rgb.load()
    w, h = rgb.size
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            if r >= 249 and g >= 249 and b >= 249:
                px[x, y] = (255, 255, 255)
    return rgb


def format_2k_view(src_path: Path, dst_path: Path, is_body: bool):
    """Save clean 2K character view: 1536x2048 for body views (trimmed cleanly to ~90% height), 2048x2048 for face views."""
    with Image.open(src_path) as raw:
        rgb = snap_white(to_white_rgb(raw))
    if is_body:
        bg = Image.new("RGB", rgb.size, (246, 246, 246))
        diff = ImageChops.difference(rgb, bg).convert("L").point(lambda p: 255 if p > 14 else 0)
        bbox = diff.getbbox()
        if bbox:
            x0, y0, x1, y1 = bbox
            sub = rgb.crop((x0, y0, x1, y1))
            tw, th = 1536, 2048
            scale = min((tw - 120) / max(1, sub.width), int(th * 0.90) / max(1, sub.height))
            nw, nh = max(1, int(round(sub.width * scale))), max(1, int(round(sub.height * scale)))
            resized = sub.resize((nw, nh), RESAMPLE)
            canvas = Image.new("RGB", (tw, th), (255, 255, 255))
            canvas.paste(resized, ((tw - nw) // 2, (th - nh) // 2))
            rgb = canvas
        else:
            rgb = rgb.resize((1536, 2048), RESAMPLE)
    else:
        if rgb.size != (2048, 2048):
            tw, th = 2048, 2048
            scale = min(tw / rgb.width, th / rgb.height)
            nw, nh = int(round(rgb.width * scale)), int(round(rgb.height * scale))
            resized = rgb.resize((nw, nh), RESAMPLE)
            canvas = Image.new("RGB", (tw, th), (255, 255, 255))
            canvas.paste(resized, ((tw - nw) // 2, (th - nh) // 2))
            rgb = canvas
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst_path.with_name(f".{dst_path.name}.part")
    rgb.save(tmp, "JPEG", quality=95, subsampling=0)
    tmp.replace(dst_path)
    return rgb.size


def compose_sheet_2k(view_dir: Path, out_jpg: Path):
    canvas = Image.new("RGB", (2048, 1152), (255, 255, 255))
    for name, x, y, width, height in PANELS_2K:
        with Image.open(view_dir / f"{name}_2k.jpg") as original:
            image = ImageOps.exif_transpose(original).convert("RGB")
            image.thumbnail((width, height), RESAMPLE)
            canvas.paste(image, (x + (width - image.width) // 2, y + (height - image.height) // 2))
    tmp = out_jpg.with_name(f".{out_jpg.name}.part")
    canvas.save(tmp, "JPEG", quality=95, subsampling=0)
    tmp.replace(out_jpg)


def upload_binary(studio: Studio, file_path: Path, mime: str, name: str, target_id: str, media_type: str) -> str:
    qs = urllib.parse.urlencode({"name": name, "targetId": target_id, "type": media_type})
    res = studio.request("POST", f"/api/studio/projects/{PROJECT_ID}/upload?{qs}", raw=file_path.read_bytes(), mime=mime, timeout=180)
    return res["id"]


def prepare_2k_scenes_and_props_and_minor_chars(specs: dict, ep1_10_names: set):
    """Step 1: Pull raw 2K scenes (1152x2048) & 2K props (2048x2048) from Spark + build 2048x1152 sheets for the 11 minor characters, and sync to DB!"""
    SCENE_2K.mkdir(parents=True, exist_ok=True)
    PROP_2K.mkdir(parents=True, exist_ok=True)
    CHAR_2K.mkdir(parents=True, exist_ok=True)

    major_ids = {c["assetId"] for c in MAJOR_CONFIGS}
    scenes = [s for s in specs["scenes"] if s["name"] in ep1_10_names]
    props = [p for p in specs["props"] if p["name"] in ep1_10_names]
    minor_chars = [c for c in specs["characters"] if c["name"] in ep1_10_names and c["assetId"] not in major_ids]

    # 1. Fetch 14 raw 2K scenes -> 1152x2048 PNG
    for s in scenes:
        aid = s["assetId"]
        dst = SCENE_2K / f"{aid}_2k.png"
        if dst.is_file():
            continue
        raw_tmp = OUT_2K / f".raw_scn_{aid}.png"
        if s["name"] == "桂花巷渝清记大堂与天井" and (PILOT_DIR / "raw_scene.png").is_file():
            shutil.copy2(PILOT_DIR / "raw_scene.png", raw_tmp)
        else:
            remote = f"{COMFY_DIR}/output/p2005_scene_{aid[:8]}_00001_.png"
            subprocess.run(["scp", "-q", *SSH_OPTS, f"{SPARK_HOST}:{remote}", str(raw_tmp)], check=True, timeout=120)
        with Image.open(raw_tmp) as im:
            rgb = to_white_rgb(im).resize((1152, 2048), RESAMPLE)
            tmp = dst.with_name(f".{dst.name}.part")
            rgb.save(tmp, "PNG")
            tmp.replace(dst)
        raw_tmp.unlink(missing_ok=True)
        log(f"[SCENE 2K] {s['name']} -> 1152x2048")

    # 2. Fetch 10 raw 2K props -> 2048x2048 PNG
    for p in props:
        aid = p["assetId"]
        dst = PROP_2K / f"{aid}_2k.png"
        if dst.is_file():
            continue
        raw_tmp = OUT_2K / f".raw_prp_{aid}.png"
        if p["name"] == "紫铜子母鸳鸯锅" and (PILOT_DIR / "raw_prop.png").is_file():
            shutil.copy2(PILOT_DIR / "raw_prop.png", raw_tmp)
        else:
            remote = f"{COMFY_DIR}/output/p2005_prop_{aid[:8]}_00001_.png"
            subprocess.run(["scp", "-q", *SSH_OPTS, f"{SPARK_HOST}:{remote}", str(raw_tmp)], check=True, timeout=120)
        with Image.open(raw_tmp) as im:
            rgb = snap_white(to_white_rgb(im))
            if rgb.size != (2048, 2048):
                rgb = rgb.resize((2048, 2048), RESAMPLE)
            tmp = dst.with_name(f".{dst.name}.part")
            rgb.save(tmp, "PNG")
            tmp.replace(dst)
        raw_tmp.unlink(missing_ok=True)
        log(f"[PROP 2K] {p['name']} -> 2048x2048")

    # 3. Build 2048x1152 2K sheets + 2K views for the 11 minor Ep 1-10 supporting characters from their raw_*.png
    for c in minor_chars:
        aid = c["assetId"]
        cdir_2k = CHAR_2K / aid
        sheet_2k = cdir_2k / "sheet_2048x1152.jpg"
        if sheet_2k.is_file():
            continue
        old_cdir = OLD_OUT / "characters" / aid
        for k in ["front", "torsoFront", "torsoSide", "back"]:
            format_2k_view(old_cdir / f"raw_{k}.png", cdir_2k / f"{k}_2k.jpg", is_body=True)
        for k in ["faceFront", "faceLeft"]:
            format_2k_view(old_cdir / f"raw_{k}.png", cdir_2k / f"{k}_2k.jpg", is_body=False)
        compose_sheet_2k(cdir_2k, sheet_2k)
        log(f"[MINOR CHAR 2K] {c['name']} -> 2048x1152 sheet")

    # Sync all 14 2K scenes + 10 2K props + 11 2K minor characters to Workstation DB immediately!
    with SYNC_LOCK:
        studio = Studio()
        proj = studio.project(PROJECT_ID)
        media_by_id = {m["id"]: m for m in proj.get("media", [])}
        existing_assets = {a["id"]: a for a in proj["assets"]}
        media_updates = {}
        asset_updates = []

        for s in scenes:
            aid = s["assetId"]
            cur_m = media_by_id.get(existing_assets[aid].get("imageId") or "")
            if cur_m and (cur_m.get("metadata") or {}).get("width") == 1152:
                continue
            sf = SCENE_2K / f"{aid}_2k.png"
            mid = upload_binary(studio, sf, "image/png", f"{s['name']}-2K.png", aid, "asset-image")
            media_updates[mid] = {"metadata": {"width": 1152, "height": 2048, "tier": "2K"}}
            asset_updates.append({"assetId": aid, "prompt": s["prompt"], "imageId": mid})

        for p in props:
            aid = p["assetId"]
            cur_m = media_by_id.get(existing_assets[aid].get("imageId") or "")
            if cur_m and (cur_m.get("metadata") or {}).get("width") == 2048:
                continue
            pf = PROP_2K / f"{aid}_2k.png"
            mid = upload_binary(studio, pf, "image/png", f"{p['name']}-2K.png", aid, "asset-image")
            media_updates[mid] = {"metadata": {"width": 2048, "height": 2048, "tier": "2K"}}
            asset_updates.append({"assetId": aid, "prompt": p["prompt"], "imageId": mid})

        for c in minor_chars:
            aid = c["assetId"]
            cur_m = media_by_id.get(existing_assets[aid].get("sheetImageId") or "")
            if cur_m and (cur_m.get("metadata") or {}).get("width") == 2048:
                continue
            cdir_2k = CHAR_2K / aid
            view_ids = {}
            for vname in ["front", "torsoFront", "torsoSide", "back", "faceFront", "faceLeft"]:
                vf = cdir_2k / f"{vname}_2k.jpg"
                mid = upload_binary(studio, vf, "image/jpeg", f"{c['name']}-{vname}-2K.jpg", aid, "character-view")
                view_ids[vname] = mid
                media_updates[mid] = {"type": "character-view", "view": vname, "targetId": aid}
            sheet_id = upload_binary(studio, cdir_2k / "sheet_2048x1152.jpg", "image/jpeg", f"{c['name']}-五格资产图-2K.jpg", aid, "character-sheet")
            media_updates[sheet_id] = {
                "type": "character-sheet",
                "targetId": aid,
                "viewIds": view_ids,
                "metadata": {"width": 2048, "height": 1152, "tier": "2K", "views": ["torsoFront", "torsoSide", "back", "faceFront", "faceLeft"]},
            }
            asset_updates.append({
                "assetId": aid,
                "imageId": sheet_id,
                "sheetImageId": sheet_id,
                "frontImageId": view_ids["front"],
                "viewIds": view_ids,
            })

        if asset_updates:
            payload = {"projectId": PROJECT_ID, "mediaUpdates": media_updates, "assetUpdates": asset_updates}
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tf:
                json.dump(payload, tf, ensure_ascii=False)
                tmp_path = tf.name
            try:
                subprocess.run([NODE_BIN, SYNC_MJS, tmp_path], check=True, timeout=60)
            finally:
                Path(tmp_path).unlink(missing_ok=True)
            log(f"[SYNCED 2K BATCH] Updated {len(asset_updates)} scenes/props/minor-chars to 2K in Workstation DB!")


def gen_vtrix_2k(prompt: str, out_path: Path, refs: list, aspect_ratio: str, prefix: str):
    if out_path.is_file() and out_path.stat().st_size > 4096:
        return
    with VTRIX_SEM:
        vi.generate_with_fallback(
            prompt=prompt,
            out_path=out_path,
            ref_files=[str(r) for r in refs if r and Path(r).is_file()],
            aspect_ratio=aspect_ratio,
            resolution="2K",
            quality="high",
            complexity="high",
            timeout=600,
            prefix=prefix,
        )


def gen_spark_h3_2k(prompt: str, refs: list, width: int, height: int, seed: int, prefix: str, out_path: Path):
    if out_path.is_file() and out_path.stat().st_size > 4096:
        return
    ref_cache = OUT_2K / ".h3_refs_jpg"
    ref_cache.mkdir(parents=True, exist_ok=True)
    remote_refs = []
    for idx, rp in enumerate(refs):
        rp = Path(rp)
        # Keep crisp 1536px reference JPEG (~350KB) for fast SCP while preserving sharp 2K detail
        local_ref = ref_cache / f"{rp.parent.name}_{rp.stem}_1536.jpg"
        if not local_ref.is_file():
            with Image.open(rp) as im:
                rgb = to_white_rgb(im)
                rgb.thumbnail((1536, 1536), RESAMPLE)
                rgb.save(local_ref, "JPEG", quality=94)
        rname = f"gc2k_{prefix}_{idx}.jpg"
        subprocess.run(["scp", "-q", *SSH_OPTS, str(local_ref), f"{SPARK_HOST}:{COMFY_DIR}/input/{rname}"], check=True, timeout=60)
        remote_refs.append(rname)

    remote_py = f"""
import json, sys, time, urllib.request
opener = urllib.request.build_opener(urllib.request.ProxyHandler({{}}))
def call(path, data=None):
    req = urllib.request.Request('http://127.0.0.1:8338' + path, data=json.dumps(data).encode() if data is not None else None, headers={{'Content-Type':'application/json'}})
    with opener.open(req, timeout=30) as r:
        return json.load(r)
c = {{'clip':['2',0], 'vae':['3',0], 'prompt':{json.dumps(prompt)}, 'width':{width}, 'height':{height}}}
g = {{
  '1': {{'class_type':'UNETLoader','inputs':{{'unet_name':'minimax_h3_image_pruned_int8_convrot.safetensors','weight_dtype':'default'}}}},
  '2': {{'class_type':'CLIPLoader','inputs':{{'clip_name':'qwen3vl_32b_minimax_h3_int8_convrot.safetensors','type':'minimax','device':'default'}}}},
  '3': {{'class_type':'VAELoader','inputs':{{'vae_name':'minimax_h3_image_vae_fp16.safetensors'}}}},
  '4': {{'class_type':'MiniMaxH3ImageConditioning','inputs':c}},
  '5': {{'class_type':'ConditioningZeroOut','inputs':{{'conditioning':['4',0]}}}},
  '6': {{'class_type':'KSampler','inputs':{{'model':['1',0],'positive':['4',0],'negative':['5',0],'latent_image':['4',1],'seed':{seed},'steps':6,'cfg':1,'sampler_name':'euler','scheduler':'simple','denoise':1}}}},
  '7': {{'class_type':'VAEDecode','inputs':{{'samples':['6',0],'vae':['3',0]}}}},
  '9': {{'class_type':'SaveImage','inputs':{{'images':['7',0],'filename_prefix':{json.dumps(prefix)}}}}}
}}
refs = {json.dumps(remote_refs)}
for i, rname in enumerate(refs, 1):
    nid = str(10 + i)
    g[nid] = {{'class_type':'LoadImage','inputs':{{'image':rname}}}}
    c[f'images.image_{{i}}'] = [nid, 0]

pid = call('/prompt', {{'prompt':g,'client_id':'gc-h3-2k'}})['prompt_id']
for _ in range(360):
    h = call('/history/' + pid)
    if pid in h:
        print(json.dumps(h[pid]))
        sys.exit(0 if h[pid].get('status',{{}}).get('status_str')=='success' else 1)
    time.sleep(1.5)
raise TimeoutError(pid)
"""
    proc = subprocess.run(["ssh", *SSH_OPTS, SPARK_HOST, "python3", "-"], input=remote_py, text=True, capture_output=True, timeout=600, check=True)
    hist = json.loads([ln for ln in proc.stdout.splitlines() if ln.strip().startswith("{")][-1])
    img = [im for out in hist["outputs"].values() for im in out.get("images", [])][0]
    sub = f"{img['subfolder']}/" if img.get("subfolder") else ""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_name(f".{out_path.name}.part")
    subprocess.run(["scp", "-q", *SSH_OPTS, f"{SPARK_HOST}:{COMFY_DIR}/output/{sub}{img['filename']}", str(tmp)], check=True, timeout=120)
    tmp.replace(out_path)


MAJOR_CONFIGS = [
    {
        "assetId": "6a250d00-356f-4d47-bf7d-935314755542",
        "name": "夏芊芊",
        "engine": "vtrix",
        "globalCharacterKey": "gd_c02",
        "globalCharacterName": "夏柠柒",
        "globalCostumeKey": "gd_c02:灰T恤配黑围裙兼职装",
        "hairDesc": "深棕黑色柔顺微卷披肩长发，中分轻薄空气感八字刘海",
        "costumeDesc": "全局服装库【gd_c02 · 灰T恤配黑围裙兼职装】：浅灰色V领短袖针织T恤，外罩纯黑色挂脖式餐饮围裙，颈间佩戴细银链小吊坠，下身着深色修身直筒长裤与黑色休闲鞋",
        "description": "女主基础形象（原型：夏柠柒 gd_c02；服装：全局库 gd_c02 灰T恤配黑围裙兼职装）：清透冷白瓜子小脸，眼下细小泪痣，微卷披肩长发配黑色挂脖餐饮围裙。",
        "faceCalmRef": G2 / "gd_c02" / "face_平静_2k.png",
        "faceExprRef": G2 / "gd_c02" / "face_温柔微笑_2k.png",
        "exprLabel": "温柔微笑",
        "exprDesc": "眼眸含笑清亮动人，唇角轻轻弯起治愈甜美浅笑",
        "reuseFront": G2 / "gd_c02" / "cropped_outfit_01_front_2k.png",
        "reuseTorsoFront": G2 / "gd_c02" / "body_front_headless_2k.png",
        "reuseTorsoSide": G2 / "gd_c02" / "body_side_headless_2k.png",
        "reuseBack": G2 / "gd_c02" / "body_back_with_head_2k.png",
    },
    {
        "assetId": "ad5aa9a9-3d3f-4201-baf7-e6908e38ec71",
        "name": "叶寻",
        "engine": "vtrix",
        "globalCharacterKey": "v01_c01",
        "globalCharacterName": "陈峰（男主）",
        "globalCostumeKey": "v01_c01:深藏青夹克休闲日常装",
        "hairDesc": "自然乌黑清爽男士三七分短碎发",
        "costumeDesc": "全局服装库【v01_c01 · 深藏青夹克休闲日常装】：外穿深藏青色翻领长袖休闲拉链夹克外套，内搭纯白色圆领纯棉T恤，下搭深黑色修身直筒休闲长裤与黑白拼色运动板鞋，左手腕佩戴黑色皮表带腕表",
        "description": "男主基础形象（原型：陈峰 v01_c01；服装：全局库 v01_c01 深藏青夹克休闲日常装）：21岁阳光清隽大学生，深藏青翻领夹克叠穿白T恤配黑直筒裤。",
        "faceCalmRef": G1 / "v01_c01" / "face_平静_2k.png",
        "faceExprRef": None,
        "exprLabel": "自信微笑",
        "exprDesc": "剑眉舒展目光清亮笃定，嘴角扬起温暖自信的浅笑",
        "reuseFront": G1 / "v01_c01" / "cropped_costume_front_2k.png",
        "reuseTorsoFront": G1 / "v01_c01" / "body_front_headless_2k.png",
        "reuseTorsoSide": G1 / "v01_c01" / "body_side_headless_2k.png",
        "reuseBack": G1 / "v01_c01" / "body_back_with_head_2k.png",
        "reuseFaceFront": G1 / "v01_c01" / "face_平静_2k.png",
    },
    {
        "assetId": "11d0769a-9ddb-472b-b155-cf9045694851",
        "name": "叶寻 · 渝清记围裙掌勺",
        "engine": "vtrix",
        "globalCharacterKey": "v01_c01",
        "globalCharacterName": "陈峰（男主）",
        "globalCostumeKey": "v28_c01:炭灰卫衣配深棕帆布围裙夜市摆摊装",
        "hairDesc": "自然乌黑清爽男士三七分短碎发",
        "costumeDesc": "全局服装库【v28_c01 · 炭灰卫衣配深棕帆布围裙装】：内穿深炭灰色宽松圆领长袖卫衣（袖口挽至小臂），外系深棕褐色水洗帆布挂脖围裙（腹部工装贴袋、背后系带），脖颈搭挂米白色双灰条纹纯棉毛巾，下搭深炭灰色直筒工装长裤与深黑防滑工作鞋",
        "description": "叶寻渝清记掌勺与凌晨跑屠场造型（原型：陈峰 v01_c01；服装：全局库 v28_c01 炭灰卫衣配深棕帆布围裙装）：保留年轻清隽容貌，炭灰卫衣外系深棕帆布长围裙配擦汗毛巾。",
        "faceCalmRef": G1 / "v01_c01" / "face_平静_2k.png",
        "charBackRef": G1 / "v01_c01" / "body_back_with_head_2k.png",
        "costumeFrontRef": G1 / "v28_c01" / "cropped_costume_front_2k.png",
        "costumeBackRef": G1 / "v28_c01" / "cropped_costume_back_2k.png",
        "reuseTorsoFront": G1 / "v28_c01" / "body_front_headless_2k.png",
        "reuseTorsoSide": G1 / "v28_c01" / "body_side_headless_2k.png",
        "faceExprRef": None,
        "exprLabel": "温和笃定微笑",
        "exprDesc": "眼神温暖专注充满烟火干劲，嘴角带清爽笃定的微笑",
    },
    {
        "assetId": "7cf4b125-052f-40b5-b910-2e757657d808",
        "name": "叶寻 · 2015行政总厨",
        "engine": "vtrix",
        "globalCharacterKey": "v01_c01",
        "globalCharacterName": "陈峰（男主）",
        "globalCostumeKey": "v10_c02:浅天蓝长袖衬衫配黑西裤踏实青年装",
        "hairDesc": "自然乌黑利落三七偏分青年精英短发",
        "costumeDesc": "全局服装库【v10_c02 · 浅天蓝长袖衬衫配黑西裤踏实青年装】：上身穿浅天蓝色纯棉修身尖翻领长袖商务衬衫（领口解开第一颗纽扣自然微敞），下身穿纯黑色修身直筒西装长裤、系黑色皮带，脚穿黑色哑光系带商务皮鞋",
        "description": "叶寻前世上市路演前夜造型（原型：陈峰 v01_c01；服装：全局库 v10_c02 浅天蓝长袖衬衫配黑西裤踏实青年装）：26岁年轻俊朗轻熟青年气质（绝非中年沧桑），穿浅天蓝挺括长袖衬衫配黑西裤。",
        "faceCalmRef": G1 / "v01_c01" / "face_平静_2k.png",
        "charBackRef": G1 / "v01_c01" / "body_back_with_head_2k.png",
        "costumeFrontRef": G1 / "v10_c02" / "cropped_costume_front_2k.png",
        "costumeBackRef": G1 / "v10_c02" / "cropped_costume_back_2k.png",
        "reuseTorsoFront": G1 / "v10_c02" / "body_front_headless_2k.png",
        "reuseTorsoSide": G1 / "v10_c02" / "body_side_headless_2k.png",
        "faceExprRef": None,
        "exprLabel": "冷峻克制",
        "exprDesc": "年轻俊朗面容双眉微敛，眼神沉静冷峻透出隐忍锋芒",
    },
    {
        "assetId": "a548b547-5051-4d6e-9a99-99fd5c5e6168",
        "name": "林双双",
        "engine": "spark",
        "seed": 2029100,
        "globalCharacterKey": "v04_c02",
        "globalCharacterName": "喝多了就找人分手·女主",
        "globalCostumeKey": "v16_c02:米白金扣小香风短外套半裙套装",
        "hairDesc": "深棕栗色韩系慵懒空气感低盘发，前额散落轻薄空气碎刘海，双耳戴小巧珍珠耳钉",
        "costumeDesc": "全局服装库【v16_c02 · 米白金扣小香风短外套半裙套装】：外穿米白色修身无领V口短款小香风粗花呢西装外套（门襟点缀精致金色圆纽扣），内搭纯白色修身打底衫，下搭同色系米白色高腰金扣A字短裙配细金腰链，脚穿米白色尖头高跟单鞋",
        "description": "林双双2005年骄纵校花基础造型（原型：v04_c02；服装：全局库 v16_c02 米白金扣小香风短外套半裙套装）：年轻精致明艳，穿米白金扣小香风套裙。",
        "faceCalmRef": G1 / "v04_c02" / "face_平静_2k.png",
        "charBackRef": G1 / "v04_c02" / "body_back_with_head_2k.png",
        "costumeFrontRef": G1 / "v16_c02" / "cropped_costume_front_2k.png",
        "costumeBackRef": G1 / "v16_c02" / "cropped_costume_back_2k.png",
        "reuseTorsoFront": G1 / "v16_c02" / "body_front_headless_2k.png",
        "reuseTorsoSide": G1 / "v16_c02" / "body_side_headless_2k.png",
        "faceExprRef": None,
        "exprLabel": "傲慢娇嗔",
        "exprDesc": "眉峰微挑眼神高傲挑剔，唇角微撇带几分娇纵嫌弃神情",
    },
    {
        "assetId": "a4cc731c-eb3d-4784-a8db-5cc124fe8b07",
        "name": "林双双 · 2015女董事长",
        "engine": "spark",
        "seed": 2029200,
        "globalCharacterKey": "v04_c02",
        "globalCharacterName": "喝多了就找人分手·女主",
        "globalCostumeKey": "v15_c03:中灰色修身西装职场套装",
        "hairDesc": "深棕栗色利落精致低盘发，前额留轻盈八字刘海修饰年轻鹅蛋脸",
        "costumeDesc": "全局服装库【v15_c03 · 中灰色修身西装职场套装】：外穿中灰色修身平驳领单排黑扣西装外套（袖口自然推挽至小臂），内搭米白色轻薄丝质翻领衬衫，下搭同色系中灰色高腰修身西装长裤，脚穿米白色尖头细高跟单鞋",
        "description": "林双双前世上市前夜女总裁造型（原型：v04_c02；服装：全局库 v15_c03 中灰色修身西装职场套装）：26岁年轻明艳轻熟女高管气质（绝非中年面容），穿中灰色修身西装套装。",
        "faceCalmRef": G1 / "v04_c02" / "face_平静_2k.png",
        "charBackRef": G1 / "v04_c02" / "body_back_with_head_2k.png",
        "costumeFrontRef": G1 / "v15_c03" / "cropped_costume_front_2k.png",
        "costumeBackRef": G1 / "v15_c03" / "cropped_costume_back_2k.png",
        "reuseTorsoFront": G1 / "v15_c03" / "body_front_headless_2k.png",
        "reuseTorsoSide": G1 / "v15_c03" / "body_side_headless_2k.png",
        "faceExprRef": None,
        "exprLabel": "冷漠强势",
        "exprDesc": "年轻精致面庞下巴微抬，眼神清冷凌厉居高临下",
    },
    {
        "assetId": "4dc3a4ab-e8b4-4a5f-afb5-7354fed97e49",
        "name": "林双双 · 塞纳左岸酒红礼服",
        "engine": "spark",
        "seed": 2029300,
        "globalCharacterKey": "v04_c02",
        "globalCharacterName": "喝多了就找人分手·女主",
        "globalCostumeKey": "v09_c02:浅杏色风衣配酒红缎面裙都市轻熟装",
        "hairDesc": "深棕栗色韩系优雅低盘发配轻盈八字碎刘海，双耳戴精致小耳坠",
        "costumeDesc": "全局服装库【v09_c02 · 浅杏色风衣配酒红缎面裙都市轻熟装】：外穿浅米杏色双排深棕圆扣中长款大翻领风衣外套，内搭酒红色丝缎微光泽立领修身衬衫式连衣中裙（腰系深棕细腰带），脚穿浅米杏色尖头细高跟单鞋",
        "description": "林双双塞纳左岸西餐厅老板娘造型（原型：v04_c02；服装：全局库 v09_c02 浅杏色风衣配酒红缎面裙都市轻熟装）：年轻明艳虚荣得意，浅杏风衣叠穿酒红丝缎连衣裙。",
        "faceCalmRef": G1 / "v04_c02" / "face_平静_2k.png",
        "charBackRef": G1 / "v04_c02" / "body_back_with_head_2k.png",
        "costumeFrontRef": G1 / "v09_c02" / "cropped_costume_front_2k.png",
        "costumeBackRef": G1 / "v09_c02" / "cropped_costume_back_2k.png",
        "reuseTorsoFront": G1 / "v09_c02" / "body_front_headless_2k.png",
        "reuseTorsoSide": G1 / "v09_c02" / "body_side_headless_2k.png",
        "faceExprRef": None,
        "exprLabel": "得意娇矜笑",
        "exprDesc": "眉眼飞扬透着虚荣炫耀的得意神采，唇角勾起明艳笑意",
    },
    {
        "assetId": "2cb3701e-c132-45f3-b6c7-f2a188cfb449",
        "name": "楚南",
        "engine": "spark",
        "seed": 2029400,
        "globalCharacterKey": "v09_c01",
        "globalCharacterName": "徐云（男主）",
        "globalCostumeKey": "v01_c03:黑西装花衬衫纨绔阔少装",
        "hairDesc": "深棕黑色蓬松四六分微卷括号刘海青年短发",
        "costumeDesc": "全局服装库【v01_c03 · 黑西装花衬衫纨绔阔少装】：外穿纯黑色宽松廓形平驳领休闲西装外套，内搭米白底深棕黑色水墨花卉印花大翻领长袖丝质衬衫（领口敞开两颗纽扣，风格张扬纨绔），下搭纯黑色垂感直筒西装长裤与黑色亮面尖头德比皮鞋",
        "description": "楚南2005年富二代公子哥造型（原型：徐云 v09_c01；服装：全局库 v01_c03 黑西装花衬衫纨绔阔少装）：22岁年轻俊朗张扬纨绔，黑休闲西装内搭水墨印花丝质敞领衬衫。",
        "faceCalmRef": G1 / "v09_c01" / "face_平静_2k.png",
        "charBackRef": G1 / "v09_c01" / "body_back_with_head_2k.png",
        "costumeFrontRef": G1 / "v01_c03" / "cropped_costume_front_2k.png",
        "costumeBackRef": G1 / "v01_c03" / "cropped_costume_back_2k.png",
        "reuseTorsoFront": G1 / "v01_c03" / "body_front_headless_2k.png",
        "reuseTorsoSide": G1 / "v01_c03" / "body_side_headless_2k.png",
        "faceExprRef": None,
        "exprLabel": "轻佻玩味笑",
        "exprDesc": "剑眉微挑眼神轻佻傲慢，嘴角勾起一抹讥诮玩味的公子哥笑意",
    },
    {
        "assetId": "e7103299-3c66-4f69-ace0-156e25de97df",
        "name": "楚南 · 海归并购总监西装",
        "engine": "spark",
        "seed": 2029500,
        "globalCharacterKey": "v09_c01",
        "globalCharacterName": "徐云（男主）",
        "globalCostumeKey": "gd_c01:黑色正装西服配金丝眼镜",
        "hairDesc": "深棕黑色精致四六分微卷刘海青年精英短发，鼻梁佩戴精致细金丝边框光学眼镜",
        "costumeDesc": "全局服装库【gd_c01 · 黑色正装西服配金丝眼镜】：身穿纯黑色修身平驳领正装三件套西服（含黑色修身马甲与西装外套），内搭浅灰蓝色尖领正装衬衫与纯黑色领带，下搭纯黑色修身西装长裤与黑色亮面牛津皮鞋，佩戴细金丝眼镜",
        "description": "楚南前世及海归精英包装造型（原型：徐云 v09_c01；服装：全局库 gd_c01 黑色正装西服配金丝眼镜）：26岁年轻斯文败类海归精英感（绝非中年人），戴细金丝眼镜穿黑色修身三件套西服。",
        "faceCalmRef": G1 / "v09_c01" / "face_平静_2k.png",
        "charBackRef": G1 / "v09_c01" / "body_back_with_head_2k.png",
        "costumeFrontRef": G2 / "gd_c01" / "cropped_outfit_10_front_2k.png",
        "costumeSideRef": G2 / "gd_c01" / "cropped_outfit_10_side_2k.png",
        "costumeBackRef": G2 / "gd_c01" / "cropped_outfit_10_back_2k.png",
        "faceExprRef": None,
        "exprLabel": "斯文算计笑",
        "exprDesc": "年轻俊朗面孔在细金丝眼镜后透出精明算计，嘴角挂着虚伪得意的浅笑",
    },
]


def build_major_char_2k(cfg: dict):
    aid = cfg["assetId"]
    name = cfg["name"]
    engine = cfg["engine"]
    cdir = CHAR_2K / aid
    cdir.mkdir(parents=True, exist_ok=True)
    sheet_2k = cdir / "sheet_2048x1152.jpg"

    if sheet_2k.is_file() and all((cdir / f"{v}_2k.jpg").is_file() for v in ["front", "torsoFront", "torsoSide", "back", "faceFront", "faceLeft"]):
        log(f"[SKIP MAJOR 2K] {name} already complete")
        return

    t0 = time.time()
    hair = cfg["hairDesc"]
    cdesc = cfg["costumeDesc"]
    face_calm = cfg["faceCalmRef"]
    expr_label = cfg["exprLabel"]
    expr_desc = cfg["exprDesc"]

    raw_front = cdir / "raw_front_2k.png"
    raw_tf = cdir / "raw_torsoFront_2k.png"
    raw_ts = cdir / "raw_torsoSide_2k.png"
    raw_back = cdir / "raw_back_2k.png"
    raw_face = cdir / "raw_faceFront_2k.png"
    raw_expr = cdir / "raw_faceLeft_2k.png"

    if cfg.get("reuseFront") and not raw_front.is_file():
        shutil.copy2(cfg["reuseFront"], raw_front)
    if cfg.get("reuseTorsoFront") and not raw_tf.is_file():
        shutil.copy2(cfg["reuseTorsoFront"], raw_tf)
    if cfg.get("reuseTorsoSide") and not raw_ts.is_file():
        shutil.copy2(cfg["reuseTorsoSide"], raw_ts)
    if cfg.get("reuseBack") and not raw_back.is_file():
        shutil.copy2(cfg["reuseBack"], raw_back)
    if cfg.get("reuseFaceFront") and not raw_face.is_file():
        shutil.copy2(cfg["reuseFaceFront"], raw_face)

    youth_rule = "严格保持22-26岁年轻俊朗/明艳轻熟青年的紧致白净容貌，绝无中年皱纹或沧桑老态！"

    if engine == "vtrix":
        if not raw_front.is_file():
            p_front = (
                f"第一张参考图是目标人物的正脸身份原型，第二张参考图是全局服装库的目标服装造型（{cdesc}）。{youth_rule}"
                f"请将第一张参考图的人物头部五官与发型（{hair}）自然换穿到第二张参考图的100%同款全套服装、围裙/配饰、裤装与鞋履上！"
                "输出单张独立2K【完整人物全身0度正面立姿定妆图】：头、脸、身体严格0度正对镜头自然站立，双臂自然垂放无包袋杂物，从头顶至鞋底完整呈现（占画面高度约90%），纯白背景（RGB 255,255,255），精致明亮电影感写实光效，无拼图无文字。"
            )
            gen_vtrix_2k(p_front, raw_front, [face_calm, cfg["costumeFrontRef"]], "1536x2048", f"m2k_{aid[:6]}_front")

        sub_jobs = []
        if not raw_back.is_file():
            p_back = (
                f"第一张参考图是全局服装库的背面服装参考（{cdesc}），第二张参考图是目标人物的后脑勺发型参考（{hair}）。"
                "生成单张独立2K【完整人物全身180度正背面立姿图】：100%保留第一张参考图的背面全套服装、围裙系带与鞋跟，同时后脑勺与短发严格匹配第二张参考图！"
                "人物严格180度背对镜头自然直立不露脸，从头顶至鞋跟完整呈现，纯白背景（RGB 255,255,255），明亮干净无拼图无文字。"
            )
            sub_jobs.append((p_back, raw_back, [cfg["costumeBackRef"], cfg["charBackRef"]], "1536x2048", f"m2k_{aid[:6]}_back"))

        if not raw_face.is_file():
            p_face = (
                f"第一张参考图为该角色正脸五官原型，第二张参考图为该角色所穿全局库服装造型（{cdesc}）。{youth_rule}"
                f"100%保持第一张参考图完全一致的五官骨相、泪痣/眉眼细节与发型（{hair}），仅将肩颈衣领切换为第二张参考图完全一致的服装领口与挂脖带/衬衫领！"
                "输出单张独立2K【正面人物面部图（平静）】：0度正对镜头平视，完整保留头顶头发、面部、脖子及少量新服装领口肩部（占画面高度约85%），表情自然平静，纯白背景（RGB 255,255,255），精致明亮电影感写实光效，无拼图无文字。"
            )
            sub_jobs.append((p_face, raw_face, [face_calm, raw_front], "2048x2048", f"m2k_{aid[:6]}_face"))

        if not raw_expr.is_file():
            expr_refs = [cfg["faceExprRef"], raw_front] if cfg.get("faceExprRef") else [face_calm, raw_front]
            p_expr = (
                f"第一张参考图为该角色的五官/真实表情原型，第二张参考图为该角色所穿全局库服装造型（{cdesc}）。{youth_rule}"
                f"100%保持第一张参考图同一人的五官骨相与发型（{hair}），呈现自然生动的【{expr_label}】神态（{expr_desc}），同时肩颈衣领100%匹配第二张参考图的新服装领口！"
                "输出单张独立2K【人物面部表情图】：正面平视镜头，完整保留头顶头发、面部、脖子及少量新服装肩领（占画面高度约85%），纯白背景（RGB 255,255,255），精致明亮电影感写实光效，无拼图无文字。"
            )
            sub_jobs.append((p_expr, raw_expr, expr_refs, "2048x2048", f"m2k_{aid[:6]}_expr"))

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futs = [pool.submit(gen_vtrix_2k, pr, op, rf, ar, px) for pr, op, rf, ar, px in sub_jobs]
            for f in concurrent.futures.as_completed(futs):
                f.result()

    else:
        # Spark minimaxh3image native 2K (1536x2048 bodies, 2048x2048 portraits)
        sbase = cfg["seed"]
        if not raw_front.is_file():
            p_front = (
                f"基于 <Picture 1> 的人物五官骨相与 <Picture 2> 的全局服装库全套服装（{cdesc}）：{youth_rule}"
                f"将 <Picture 1> 的年轻面部五官与发型（{hair}）自然融合换穿到 <Picture 2> 100%完全一致的服装款式、颜色、材质与鞋履上（去除 <Picture 1> 旧高领或旧外套）。"
                "输出单张独立2K【完整人物全身0度正面立姿定妆图】：头、脸、身体严格0度正对镜头平视自然站立，双臂自然垂放无包袋杂物，从头顶头发到双脚鞋底完整呈现（占画面高度约88%），纯白背景（RGB 255,255,255），光线明亮干净柔和，无拼图无文字。"
            )
            gen_spark_h3_2k(p_front, [face_calm, cfg["costumeFrontRef"]], 1536, 2048, sbase + 1, f"m2k_{aid[:6]}_front", raw_front)

        if not raw_tf.is_file():
            p_tf = (
                f"基于 <Picture 1> 的完整正面全身人物服装图（{cdesc}）：100%保持完全相同的全套西装/衬衫/领带/裤装与皮鞋，仅从锁骨上方的颈根处自然干净平整截断去除整个头部、脸部、眼镜与全部头发（画面顶部绝不出现头、脸、下巴和头发，颈根截面平整正常肤色）。"
                "输出单张独立2K【无头正面全身人体服装图】，主体居中占画面高度约88%，纯白背景（RGB 255,255,255），明亮干净无拼图无文字。"
            )
            gen_spark_h3_2k(p_tf, [cfg.get("costumeFrontRef") or raw_front], 1536, 2048, sbase + 2, f"m2k_{aid[:6]}_tf", raw_tf)

        if not raw_ts.is_file():
            p_ts = (
                f"基于 <Picture 1> 的侧面全身人物服装图（{cdesc}）：100%保持完全相同的全套侧面服装与皮鞋轮廓，彻底去除整个头部、脸部、眼镜与全部头发，仅保留锁骨上方平整颈根至双脚鞋底；人物胸腹与鞋尖朝向画面左侧呈严格90度正左侧面。"
                "输出单张独立2K【无头90度左侧面全身人体服装图】，主体占画面高度约88%，纯白背景（RGB 255,255,255），明亮干净无拼图无文字。"
            )
            gen_spark_h3_2k(p_ts, [cfg.get("costumeSideRef") or raw_front], 1536, 2048, sbase + 3, f"m2k_{aid[:6]}_ts", raw_ts)

        if not raw_back.is_file():
            p_back = (
                f"基于 <Picture 1> 的全局服装库背面全身服装图（{cdesc}）与 <Picture 2> 的人物后脑发型参考（{hair}）："
                "100%保持 <Picture 1> 完全一致的背面服装、下摆与鞋履，同时头部背面发型严格匹配 <Picture 2>！"
                "输出单张独立2K【完整人物全身180度正背面立姿图】：严格180度背对镜头自然直立不露脸，从头顶至鞋跟完整呈现，占画面高度约88%，纯白背景（RGB 255,255,255），明亮干净无拼图无文字。"
            )
            gen_spark_h3_2k(p_back, [cfg["costumeBackRef"], cfg["charBackRef"]], 1536, 2048, sbase + 4, f"m2k_{aid[:6]}_back", raw_back)

        if not raw_face.is_file():
            p_face = (
                f"基于 <Picture 1> 的年轻人物五官骨相与 <Picture 2> 的新换全局库服装造型（{cdesc}）：{youth_rule}"
                f"100%保持 <Picture 1> 同一人的年轻精致五官轮廓，去除 <Picture 1> 旧衣领或高领毛衣，切换为 <Picture 2> 的发型配饰（{hair}）与完全一致的新服装上衣领口！"
                "输出单张独立2K【正面人物面部图（平静）】：0度正对镜头平视，完整保留头顶头发、面部、脖子及少量新服装肩领（占画面高度约85%），表情自然平静，纯白背景（RGB 255,255,255），精致明亮电影感写实光效，无拼图无文字。"
            )
            gen_spark_h3_2k(p_face, [face_calm, raw_front], 2048, 2048, sbase + 5, f"m2k_{aid[:6]}_face", raw_face)

        if not raw_expr.is_file():
            p_expr = (
                f"基于 <Picture 1> 的同一人物正面头像：100%保持 <Picture 1> 完全相同的年轻五官骨相、发型眼镜配饰（{hair}）与新服装领口，{youth_rule}"
                f"仅将面部神态自然调整为生动的【{expr_label}】（{expr_desc}，真实微表情不夸张）。"
                "输出单张独立2K【人物面部表情图】：正面平视镜头，完整保留头顶头发、面部、脖子及少量新服装肩领（占画面高度约85%），纯白背景（RGB 255,255,255），精致明亮电影感写实光效，无拼图无文字。"
            )
            gen_spark_h3_2k(p_expr, [raw_face], 2048, 2048, sbase + 6, f"m2k_{aid[:6]}_expr", raw_expr)

    # Format clean 2K views (1536x2048 / 2048x2048) & compose 2048x1152 2K sheet
    for k in ["front", "torsoFront", "torsoSide", "back"]:
        format_2k_view(cdir / f"raw_{k}_2k.png", cdir / f"{k}_2k.jpg", is_body=True)
    for k in ["faceFront", "faceLeft"]:
        format_2k_view(cdir / f"raw_{k}_2k.png", cdir / f"{k}_2k.jpg", is_body=False)
    compose_sheet_2k(cdir, sheet_2k)
    log(f"[{engine.upper()} 2K DONE] {name} ({cfg['globalCharacterKey']} + {cfg['globalCostumeKey']}) in {time.time()-t0:.1f}s")
    sync_major_char_2k_to_studio(cfg)


def sync_major_char_2k_to_studio(cfg: dict):
    with SYNC_LOCK:
        studio = Studio()
        aid = cfg["assetId"]
        name = cfg["name"]
        cdir = CHAR_2K / aid
        media_updates = {}
        view_ids = {}
        for vname in ["front", "torsoFront", "torsoSide", "back", "faceFront", "faceLeft"]:
            vf = cdir / f"{vname}_2k.jpg"
            mid = upload_binary(studio, vf, "image/jpeg", f"{name}-{vname}-2K.jpg", aid, "character-view")
            view_ids[vname] = mid
            media_updates[mid] = {"type": "character-view", "view": vname, "targetId": aid}
        sheet_id = upload_binary(studio, cdir / "sheet_2048x1152.jpg", "image/jpeg", f"{name}-五格资产图-2K.jpg", aid, "character-sheet")
        media_updates[sheet_id] = {
            "type": "character-sheet",
            "targetId": aid,
            "viewIds": view_ids,
            "metadata": {
                "width": 2048,
                "height": 1152,
                "tier": "2K",
                "views": ["torsoFront", "torsoSide", "back", "faceFront", "faceLeft"],
                "globalCharacterKey": cfg["globalCharacterKey"],
                "globalCostumeKey": cfg["globalCostumeKey"],
            },
        }
        prompt_str = (
            f"精致明亮电影质感2K人物设定｜全局角色原型：{cfg['globalCharacterKey']}（{cfg['globalCharacterName']}）｜"
            f"{cfg['costumeDesc']}｜发型：{cfg['hairDesc']}｜纯白背景 RGB(255,255,255) 五格资产图（2048×1152，含{cfg['exprLabel']}表情图）。"
        )
        payload = {
            "projectId": PROJECT_ID,
            "mediaUpdates": media_updates,
            "assetUpdates": [{
                "assetId": aid,
                "description": cfg["description"],
                "prompt": prompt_str,
                "imageId": sheet_id,
                "sheetImageId": sheet_id,
                "frontImageId": view_ids["front"],
                "viewIds": view_ids,
                "globalCharacterKey": cfg["globalCharacterKey"],
                "globalCostumeKey": cfg["globalCostumeKey"],
            }],
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tf:
            json.dump(payload, tf, ensure_ascii=False)
            tmp_path = tf.name
        try:
            subprocess.run([NODE_BIN, SYNC_MJS, tmp_path], check=True, timeout=60)
        finally:
            Path(tmp_path).unlink(missing_ok=True)
        log(f"[SYNCED 2K MAJOR] {name} -> sheet={sheet_id[:8]} (2048x1152)")


def main():
    t0 = time.time()
    specs = json.loads(SPECS_FILE.read_text(encoding="utf-8"))
    proj_disk = json.loads((STUDIO_ROOT / "playlets" / PROJECT_ID / "project.json").read_text(encoding="utf-8"))
    ep1_10_names = {
        n
        for ep in proj_disk["episodes"][:10]
        for s in ep.get("shots", [])
        for n in s.get("assetNames", [])
    }

    # Run Step 1 (35 scenes/props/minor-chars upgraded to 2K) + Stream A (Vtrix 2K leads) + Stream B (Spark 2K rivals) ALL CONCURRENTLY!
    vtrix_cfgs = [c for c in MAJOR_CONFIGS if c["engine"] == "vtrix"]
    spark_cfgs = [c for c in MAJOR_CONFIGS if c["engine"] == "spark"]

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as root_pool:
        f_prep = root_pool.submit(prepare_2k_scenes_and_props_and_minor_chars, specs, ep1_10_names)

        def run_vtrix():
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as lpool:
                futs = [lpool.submit(build_major_char_2k, c) for c in vtrix_cfgs]
                for f in concurrent.futures.as_completed(futs):
                    f.result()

        def run_spark():
            for c in spark_cfgs:
                build_major_char_2k(c)

        f_vtrix = root_pool.submit(run_vtrix)
        f_spark = root_pool.submit(run_spark)

        f_prep.result()
        f_vtrix.result()
        f_spark.result()

    log(f"ALL 44 EPISODE 1-10 ASSETS UPGRADED TO 2K & SYNCED IN {(time.time()-t0)/60:.1f} MIN!")


if __name__ == "__main__":
    main()
