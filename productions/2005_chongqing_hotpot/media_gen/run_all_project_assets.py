#!/usr/bin/env python3
"""Concurrent generator & Workstation uploader for all 87 assets of playlet-mwj57ecn-9658ad48:
- Stream 1 (Vtrix 26-way concurrent): 34 Characters (outfit-swapped from Global Assets + 5-panel sheet: headless front/side + back + calm face + expression, ALL images strictly <= 1024px)
- Stream 2 (Spark minimax-h3-image persistent SSH loop): 28 Scenes (576x1024 <= 1024px) + 25 Props (512x512 <= 512px, pure white RGB 255,255,255)
- Stream 3 (Workstation voice-from-media): 34 Character voices preserved from Global Voices (<= 3.0s, no VoiceDesign replacement)
Strictly saves ONLY to project playlet-mwj57ecn-9658ad48 — NEVER touches studio_global_assets!
"""
import concurrent.futures
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path
from PIL import Image, ImageChops, ImageOps

STUDIO_ROOT = Path("/home/zhongwenyu/project/playlets-studio")
sys.path.insert(0, str(STUDIO_ROOT / "skills" / "studio-bridge" / "scripts"))
import vtrix_image as vi  # noqa: E402
from studio_api import Studio  # noqa: E402

BASE_DIR = Path("/home/zhongwenyu/project/ai-director-train/productions/2005_chongqing_hotpot/media_gen")
SPECS_FILE = BASE_DIR / "asset_specs.json"
OUT_ROOT = BASE_DIR / "outputs"
CHAR_OUT = OUT_ROOT / "characters"
SCENE_OUT = OUT_ROOT / "scenes"
PROP_OUT = OUT_ROOT / "props"
PILOT_DIR = BASE_DIR / "pilot"
COMPOSE_SCRIPT = str(STUDIO_ROOT / "scripts" / "compose-character-sheet.py")
SYNC_MJS = str(BASE_DIR / "sync_character_fields.mjs")
NODE_BIN = "/home/zhongwenyu/.local/lib/node-v22.23.4-linux-x64/bin/node"

RESAMPLE = getattr(Image, "Resampling", Image).LANCZOS
VTRIX_SEM = threading.Semaphore(24)
PRINT_LOCK = threading.Lock()


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


def trim_white_body(im: Image.Image) -> Image.Image:
    """Trim excess white margin around a full-body view so body occupies ~90% height cleanly."""
    bg = Image.new("RGB", im.size, (248, 248, 248))
    diff = ImageChops.difference(im, bg).convert("L").point(lambda p: 255 if p > 12 else 0)
    bbox = diff.getbbox()
    if not bbox:
        return im
    x0, y0, x1, y1 = bbox
    bw, bh = max(1, x1 - x0), max(1, y1 - y0)
    pad_y = max(16, int(bh * 0.055))
    pad_x = max(24, int(bw * 0.12))
    cx0 = max(0, x0 - pad_x)
    cy0 = max(0, y0 - pad_y)
    cx1 = min(im.width, x1 + pad_x)
    cy1 = min(im.height, y1 + pad_y)
    cropped = im.crop((cx0, cy0, cx1, cy1))
    # Place onto clean 3:4 white canvas before 1K downscale
    th = max(cropped.height, int(cropped.width * 4 / 3))
    tw = max(cropped.width, int(round(th * 0.62)))
    canvas = Image.new("RGB", (tw, th), (255, 255, 255))
    canvas.paste(cropped, ((tw - cropped.width) // 2, (th - cropped.height) // 2))
    return canvas


def save_limited_image(src_path: Path, dst_path: Path, max_edge: int, fmt: str = "PNG", trim_body: bool = False):
    with Image.open(src_path) as raw:
        rgb = to_white_rgb(raw)
    if trim_body:
        rgb = trim_white_body(rgb)
    rgb.thumbnail((max_edge, max_edge), RESAMPLE)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst_path.with_name(f".{dst_path.name}.part")
    if fmt == "JPEG":
        rgb.save(tmp, "JPEG", quality=95, subsampling=0)
    else:
        rgb.save(tmp, "PNG")
    tmp.replace(dst_path)
    return rgb.size


def clean_pure_white_corners(src_path: Path, dst_path: Path, max_edge: int):
    """Ensure prop image is strictly <= max_edge (512) and near-white background pixels (>247) snap cleanly to pure white 255."""
    with Image.open(src_path) as raw:
        rgb = to_white_rgb(raw)
    rgb.thumbnail((max_edge, max_edge), RESAMPLE)
    # Snap near-white background halo (>=249 on all channels) to 255,255,255 while keeping object intact
    px = rgb.load()
    w, h = rgb.size
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            if r >= 249 and g >= 249 and b >= 249:
                px[x, y] = (255, 255, 255)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst_path.with_name(f".{dst_path.name}.part")
    rgb.save(tmp, "PNG")
    tmp.replace(dst_path)
    return rgb.size


def gen_vtrix_cached(prompt: str, raw_out: Path, refs: list, aspect_ratio: str, prefix: str):
    if raw_out.is_file() and raw_out.stat().st_size > 4096:
        return
    with VTRIX_SEM:
        vi.generate_with_fallback(
            prompt=prompt,
            out_path=raw_out,
            ref_files=[str(r) for r in refs if r and Path(r).is_file()],
            aspect_ratio=aspect_ratio,
            resolution="1K",
            quality="high",
            complexity="high",
            timeout=600,
            prefix=prefix,
        )


def generate_one_character(c: dict):
    aid = c["assetId"]
    name = c["name"]
    ckey = c["globalCharacterKey"]
    cdir = CHAR_OUT / aid
    cdir.mkdir(parents=True, exist_ok=True)
    sheet_jpg = cdir / "sheet_1024x576.jpg"
    front_1k = cdir / "front_1k.jpg"

    # Seed from pilot if 夏芊芊
    if name == "夏芊芊" and (PILOT_DIR / "xqq" / "raw_front.png").is_file() and not (cdir / "raw_front.png").is_file():
        for fn in ["raw_front.png", "raw_torsoFront.png", "raw_torsoSide.png", "raw_back.png", "raw_faceFront.png", "raw_faceLeft.png"]:
            src = PILOT_DIR / "xqq" / fn
            if src.is_file():
                shutil.copy2(src, cdir / fn)

    if sheet_jpg.is_file() and front_1k.is_file() and all((cdir / f"{k}_1k.jpg").is_file() for k in ["torsoFront", "torsoSide", "back", "faceFront", "faceLeft"]):
        log(f"[CHAR SKIP] {name} ({ckey}) already complete")
        return aid

    t0 = time.time()
    ref_calm = c["faceCalmRef"]
    ref_expr = c.get("faceExprRef")
    hair = c["hairDesc"]
    outfit = c["outfitDesc"]
    expr_label = c["exprLabel"]
    expr_desc = c["exprDesc"]

    wrist_rule = (
        "右手腕保留整洁白色医用护腕绷带，双臂自然下垂于身体两侧；"
        if name == "夏建国"
        else "双臂与手腕干净自然垂放于身体两侧（除服装描述明确提及的腕表外，手腕绝不缠任何护腕、纱布或绷带！）；"
    )
    youth_guard = (
        "【年龄观感硬性约束】：必须严格保持参考图24-27岁年轻俊朗/明艳轻熟青年的紧致年轻容貌与饱满清透肤质，仅通过干练发型与精英穿搭体现成熟稳重气场，严禁把人物画老、严禁出现中年沧桑感、皱纹或法令纹！"
        if any(k in name for k in ["叶寻", "夏芊芊", "林双双", "楚南", "赵帆"])
        else ""
    )

    p_front = (
        f"严格以参考图中的人物（{c['gender']}，{c['ageDesc']}）为唯一身份原型，100%保持同一张脸的五官骨相、脸型轮廓、眼神气质与精致明亮电影感写实真人画风。{youth_guard}"
        f"生成单张独立【完整人物全身0度正面立姿定妆图】（含完整头部、面部五官与发型，严禁多格拼图）：发型为{hair}（彻底去除参考图原有的围巾或旧高领）；全套穿搭为{outfit}。"
        f"【硬性要求】：彻底去除一切包袋配件与手持杂物（严禁背包、拎包、拿手机水杯文件等），{wrist_rule}"
        "人物头、脸、身体严格0度正对镜头自然站立，表情平静自然，从头顶头发到双脚鞋底100%完整呈现（占画面高度约90%，上下留白），纯白背景（RGB 255,255,255），光线明亮干净柔和，无灰底渐变、无文字水印。"
    )
    raw_front = cdir / "raw_front.png"
    gen_vtrix_cached(p_front, raw_front, [ref_calm], "3:4", f"{ckey}_{aid[:6]}_front")

    p_tf = (
        f"严格以参考图（同一人物完整正面全身定妆图）为唯一服装与身材依据，保持100%完全相同的服装款式、颜色、材质与鞋履（{outfit}）。"
        "输出单张独立【无头正面全身人体服装图】：从锁骨上方的颈根处自然干净平整截断去除整个头部（画面绝不出现头、脸、下巴和头发，颈根截面平整自然肤色，非受伤场景），"
        "完整展示锁骨、双肩、躯干、双手至双脚鞋底，主体居中占画面高度约90%，纯白背景（RGB 255,255,255），光线明亮干净，无拼图无文字水印。"
    )
    p_ts = (
        "CRITICAL: PURE 90-DEGREE LEFT PROFILE HEADLESS FULL BODY. The body faces the LEFT border of the image; chest and toe tips point LEFT, back faces RIGHT. Shoulder and hip joints overlap in pure lateral profile. NO head, NO face, NO chin, NO hair—flat clean neck stump just above collarbones. "
        f"严格以参考图（同一人物完整正面全身定妆图）为唯一服装与身材依据，保持100%相同的全套服装与鞋履（{outfit}）。"
        "输出单张独立【无头90度左侧面全身人体服装图】：彻底去除整个头部与头发，仅保留锁骨上方平整颈根至双脚鞋底，人物严格转至90度正左侧面（胸腹与脚尖朝向画面左侧），自然直立双臂下垂，主体占画面高度约90%，纯白背景（RGB 255,255,255），光线明亮干净，无拼图无文字水印。"
    )
    p_back = (
        f"严格以参考图（同一人物完整正面全身定妆图）为唯一身份与穿搭依据，保持100%相同的身材比例、背面发型（{hair}）以及全套服装鞋履背面剪裁（{outfit}）。"
        "输出单张独立【完整人物全身180度正背面立姿图】（含完整头部与后脑头发）：人物严格180度背对镜头自然直立，绝不回头不露脸，从头顶至双脚鞋跟完整呈现，占画面高度约90%，纯白背景（RGB 255,255,255），光线明亮干净，无拼图无文字水印。"
    )
    p_face = (
        f"第一张参考图为该角色正脸五官原型，第二张参考图为该角色新换的全身服装造型。{youth_guard}"
        f"严格保持第一张参考图100%一致的五官骨相与年轻紧致面容，同时发型与衣领必须100%切换为第二张参考图中的造型（发型：{hair}；领口匹配：{outfit}，彻底去除第一张原图旧衣领、高领毛衣或围巾）！"
        "输出单张独立【正面人物面部图（平静）】：头、脸、鼻尖严格0度正对镜头平视，完整保留头顶头发、面部、脖子及少量新服装领口肩部（占画面高度约85%），表情自然平静，纯白背景（RGB 255,255,255），精致明亮电影感写实光效，无拼图无文字水印。"
    )
    if ref_expr:
        expr_refs = [ref_expr, raw_front]
        p_expr = (
            f"第一张参考图为该角色的真实表情参考，第二张参考图为该角色新换的全身服装造型。{youth_guard}"
            f"严格保持第一张参考图100%同一人的年轻紧致五官骨相，呈现自然生动的【{expr_label}】神态（{expr_desc}），同时发型与衣领必须100%匹配第二张参考图的新造型（发型：{hair}；领口匹配：{outfit}，彻底去除原图旧围巾、高领毛衣或旧衣领）！"
            "输出单张独立【人物面部表情图】：正面平视镜头，表情自然真实不夸张，完整保留头顶头发、面部、脖子及少量新服装领口肩部（占画面高度约85%），纯白背景（RGB 255,255,255），精致明亮电影感写实光效，无拼图无文字水印。"
        )
    else:
        expr_refs = [ref_calm, raw_front]
        p_expr = (
            f"第一张参考图为该角色的正脸五官原型，第二张参考图为该角色新换的全身服装造型。{youth_guard}"
            f"严格保持第一张参考图100%同一人的年轻紧致五官骨相，仅将面部神态自然调整为生动的【{expr_label}】（{expr_desc}），同时发型与衣领100%匹配第二张参考图的新造型（发型：{hair}；领口匹配：{outfit}，彻底去除原图旧围巾、高领毛衣或旧衣领）！"
            "输出单张独立【人物面部表情图】：正面平视镜头，微表情鲜活真实不夸张，完整保留头顶头发、面部、脖子及少量新服装领口肩部（占画面高度约85%），纯白背景（RGB 255,255,255），精致明亮电影感写实光效，无拼图无文字水印。"
        )

    sub_tasks = [
        ("torsoFront", p_tf, [raw_front], "3:4"),
        ("torsoSide", p_ts, [raw_front], "3:4"),
        ("back", p_back, [raw_front], "3:4"),
        ("faceFront", p_face, [ref_calm, raw_front], "1:1"),
        ("faceLeft", p_expr, expr_refs, "1:1"),
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as sub_pool:
        futs = [
            sub_pool.submit(gen_vtrix_cached, pr, cdir / f"raw_{k}.png", rf, ar, f"{ckey}_{aid[:6]}_{k}")
            for k, pr, rf, ar in sub_tasks
        ]
        for f in concurrent.futures.as_completed(futs):
            f.result()

    # Downscale EVERY saved view strictly to <= 1024px (1K) & trim body margins cleanly
    save_limited_image(raw_front, front_1k, 1024, "JPEG", trim_body=True)
    comp_dir = cdir / "comp"
    comp_dir.mkdir(exist_ok=True)
    for k in ["torsoFront", "torsoSide", "back"]:
        save_limited_image(cdir / f"raw_{k}.png", cdir / f"{k}_1k.jpg", 1024, "JPEG", trim_body=True)
        shutil.copy2(cdir / f"{k}_1k.jpg", comp_dir / f"{k}.jpg")
    for k in ["faceFront", "faceLeft"]:
        save_limited_image(cdir / f"raw_{k}.png", cdir / f"{k}_1k.jpg", 1024, "JPEG", trim_body=False)
        shutil.copy2(cdir / f"{k}_1k.jpg", comp_dir / f"{k}.jpg")

    subprocess.run(["python3", COMPOSE_SCRIPT, str(comp_dir), str(sheet_jpg)], check=True)
    log(f"[CHAR DONE] {name} ({ckey}) in {time.time()-t0:.1f}s")
    return aid


def run_spark_scenes_and_props(scenes: list, props: list):
    SCENE_OUT.mkdir(parents=True, exist_ok=True)
    PROP_OUT.mkdir(parents=True, exist_ok=True)

    # Seed pilot scene & prop if matching
    for s in scenes:
        if s["name"] == "桂花巷渝清记大堂与天井" and (PILOT_DIR / "scene_1k.png").is_file():
            dst = SCENE_OUT / f"{s['assetId']}_1k.png"
            if not dst.is_file():
                shutil.copy2(PILOT_DIR / "scene_1k.png", dst)
    for p in props:
        if p["name"] == "紫铜子母鸳鸯锅" and (PILOT_DIR / "prop_512.png").is_file():
            dst = PROP_OUT / f"{p['assetId']}_512.png"
            if not dst.is_file():
                clean_pure_white_corners(PILOT_DIR / "prop_512.png", dst, 512)

    todo = []
    for idx, s in enumerate(scenes):
        dst = SCENE_OUT / f"{s['assetId']}_1k.png"
        if not dst.is_file():
            todo.append({"kind": "scene", "assetId": s["assetId"], "name": s["name"], "prompt": s["prompt"], "width": 1440, "height": 2560, "seed": 2026100 + idx, "dst": dst})
    for idx, p in enumerate(props):
        dst = PROP_OUT / f"{p['assetId']}_512.png"
        if not dst.is_file():
            todo.append({"kind": "prop", "assetId": p["assetId"], "name": p["name"], "prompt": p["prompt"], "width": 2048, "height": 2048, "seed": 2026500 + idx, "dst": dst})

    log(f"[SPARK] Need to generate {len(todo)} items ({sum(1 for x in todo if x['kind']=='scene')} scenes, {sum(1 for x in todo if x['kind']=='prop')} props)")
    if not todo:
        return

    ssh_opts = ["-i", str(Path.home() / ".ssh" / "id_ed25519_spark"), "-o", "BatchMode=yes"]
    for i, item in enumerate(todo, 1):
        t0 = time.time()
        prefix = f"p2005_{item['kind']}_{item['assetId'][:8]}"
        remote_py = f"""
import json, sys, time, urllib.request
opener = urllib.request.build_opener(urllib.request.ProxyHandler({{}}))
def call(path, data=None):
    req = urllib.request.Request('http://127.0.0.1:8338' + path, data=json.dumps(data).encode() if data is not None else None, headers={{'Content-Type':'application/json'}})
    with opener.open(req, timeout=30) as r:
        return json.load(r)
g = {{
  '1': {{'class_type':'UNETLoader','inputs':{{'unet_name':'minimax_h3_image_pruned_int8_convrot.safetensors','weight_dtype':'default'}}}},
  '2': {{'class_type':'CLIPLoader','inputs':{{'clip_name':'qwen3vl_32b_minimax_h3_int8_convrot.safetensors','type':'minimax','device':'default'}}}},
  '3': {{'class_type':'VAELoader','inputs':{{'vae_name':'minimax_h3_image_vae_fp16.safetensors'}}}},
  '4': {{'class_type':'MiniMaxH3ImageConditioning','inputs':{{'clip':['2',0],'vae':['3',0],'prompt':{json.dumps(item['prompt'])},'width':{item['width']},'height':{item['height']}}}}},
  '5': {{'class_type':'ConditioningZeroOut','inputs':{{'conditioning':['4',0]}}}},
  '6': {{'class_type':'KSampler','inputs':{{'model':['1',0],'positive':['4',0],'negative':['5',0],'latent_image':['4',1],'seed':{item['seed']},'steps':6,'cfg':1,'sampler_name':'euler','scheduler':'simple','denoise':1}}}},
  '7': {{'class_type':'VAEDecode','inputs':{{'samples':['6',0],'vae':['3',0]}}}},
  '9': {{'class_type':'SaveImage','inputs':{{'images':['7',0],'filename_prefix':{json.dumps(prefix)}}}}}
}}
pid = call('/prompt', {{'prompt':g,'client_id':'p2005-batch'}})['prompt_id']
for _ in range(360):
    h = call('/history/' + pid)
    if pid in h:
        print(json.dumps(h[pid]))
        sys.exit(0 if h[pid].get('status',{{}}).get('status_str')=='success' else 1)
    time.sleep(1.5)
raise TimeoutError(pid)
"""
        raw_tmp = OUT_ROOT / f".raw_{item['assetId']}.png"
        proc = subprocess.run(["ssh", *ssh_opts, "admin@192.168.0.149", "python3", "-"], input=remote_py, text=True, capture_output=True, timeout=600, check=True)
        hist = json.loads([ln for ln in proc.stdout.splitlines() if ln.strip().startswith("{")][-1])
        img = [im for out in hist["outputs"].values() for im in out.get("images", [])][0]
        sub = f"{img['subfolder']}/" if img.get("subfolder") else ""
        remote_file = f"/home/admin/minimax-h3-image/ComfyUI/output/{sub}{img['filename']}"
        subprocess.run(["scp", "-q", *ssh_opts, f"admin@192.168.0.149:{remote_file}", str(raw_tmp)], check=True, timeout=120)
        if item["kind"] == "scene":
            sz = save_limited_image(raw_tmp, item["dst"], 1024, "PNG", trim_body=False)
        else:
            sz = clean_pure_white_corners(raw_tmp, item["dst"], 512)
        raw_tmp.unlink(missing_ok=True)
        log(f"[SPARK {i}/{len(todo)}] {item['kind']} {item['name']} -> {sz} in {time.time()-t0:.1f}s")


def upload_binary(studio: Studio, project_id: str, file_path: Path, mime: str, name: str, target_id: str, media_type: str) -> str:
    qs = urllib.parse.urlencode({"name": name, "targetId": target_id, "type": media_type})
    res = studio.request("POST", f"/api/studio/projects/{project_id}/upload?{qs}", raw=file_path.read_bytes(), mime=mime, timeout=120)
    return res["id"]


def probe_audio_duration(wav_path: Path) -> float:
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(wav_path)],
        text=True,
    ).strip()
    return float(out)


def bind_all_voices(project_id: str, characters: list):
    studio = Studio()
    proj = studio.project(project_id)
    existing_assets = {a["id"]: a for a in proj["assets"]}
    gv_map = {v["characterKey"]: v for v in studio.request("GET", "/api/studio/global-voices")}

    bound = 0
    for c in characters:
        aid = c["assetId"]
        a = existing_assets.get(aid, {})
        if a.get("voiceId") and a.get("voiceSampleId") and a.get("globalCharacterKey") == c["globalCharacterKey"]:
            continue
        ckey = c["globalCharacterKey"]
        gv = gv_map[ckey]
        wav_path = Path(c["voiceWav"])
        dur = probe_audio_duration(wav_path)
        clip_end = min(2.99, round(max(0.5, dur - 0.01), 3))
        src_mid = upload_binary(studio, project_id, wav_path, "audio/wav", f"{c['name']}-{ckey}-原声源.wav", aid, "voice-source")
        text = (gv.get("transcript") or "我知道了。").strip()[:75]
        studio.request("POST", f"/api/studio/projects/{project_id}/voice-from-media", {
            "assetId": aid,
            "sourceMediaId": src_mid,
            "start": 0,
            "end": clip_end,
            "text": text,
        })
        bound += 1
        log(f"[VOICE] Bound {c['name']} -> {ckey} ({gv['name']}, {clip_end:.2f}s)")
    log(f"[VOICE DONE] Newly bound {bound} character voices (all 34 preserved from Global Assets)")


def upload_and_sync_all_images(specs: dict):
    project_id = specs["projectId"]
    studio = Studio()
    proj = studio.project(project_id)
    existing_assets = {a["id"]: a for a in proj["assets"]}

    media_updates = {}
    asset_updates = []

    # 1. Characters (6 views <= 1K + 1024x576 sheet)
    for c in specs["characters"]:
        aid = c["assetId"]
        a = existing_assets[aid]
        if a.get("sheetImageId") and a.get("imageId") == a.get("sheetImageId") and a.get("globalCharacterKey") == c["globalCharacterKey"]:
            continue
        cdir = CHAR_OUT / aid
        view_ids = {}
        for vname in ["front", "torsoFront", "torsoSide", "back", "faceFront", "faceLeft"]:
            vf = cdir / f"{vname}_1k.jpg"
            mid = upload_binary(studio, project_id, vf, "image/jpeg", f"{c['name']}-{vname}.jpg", aid, "character-view")
            view_ids[vname] = mid
            media_updates[mid] = {"type": "character-view", "view": vname, "targetId": aid}
        sheet_f = cdir / "sheet_1024x576.jpg"
        sheet_id = upload_binary(studio, project_id, sheet_f, "image/jpeg", f"{c['name']}-五格资产图.jpg", aid, "character-sheet")
        media_updates[sheet_id] = {
            "type": "character-sheet",
            "targetId": aid,
            "viewIds": view_ids,
            "metadata": {"width": 1024, "height": 576, "views": ["torsoFront", "torsoSide", "back", "faceFront", "faceLeft"]},
        }
        asset_updates.append({
            "assetId": aid,
            "description": c.get("description", ""),
            "prompt": c["prompt"],
            "imageId": sheet_id,
            "sheetImageId": sheet_id,
            "frontImageId": view_ids["front"],
            "viewIds": view_ids,
            "globalCharacterKey": c["globalCharacterKey"],
        })
        log(f"[UPLOAD CHAR] {c['name']} -> sheet={sheet_id[:8]}")

    # 2. Scenes (576x1024 PNG <= 1024)
    for s in specs["scenes"]:
        aid = s["assetId"]
        a = existing_assets[aid]
        if a.get("imageId"):
            continue
        sf = SCENE_OUT / f"{aid}_1k.png"
        mid = upload_binary(studio, project_id, sf, "image/png", f"{s['name']}.png", aid, "asset-image")
        asset_updates.append({"assetId": aid, "prompt": s["prompt"], "imageId": mid})
        log(f"[UPLOAD SCENE] {s['name']} -> {mid[:8]}")

    # 3. Props (512x512 PNG <= 512)
    for p in specs["props"]:
        aid = p["assetId"]
        a = existing_assets[aid]
        if a.get("imageId"):
            continue
        pf = PROP_OUT / f"{aid}_512.png"
        mid = upload_binary(studio, project_id, pf, "image/png", f"{p['name']}.png", aid, "asset-image")
        asset_updates.append({"assetId": aid, "prompt": p["prompt"], "imageId": mid})
        log(f"[UPLOAD PROP] {p['name']} -> {mid[:8]}")

    sync_payload = {
        "projectId": project_id,
        "stylePrompt": specs["stylePrompt"],
        "mediaUpdates": media_updates,
        "assetUpdates": asset_updates,
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tf:
        json.dump(sync_payload, tf, ensure_ascii=False)
        tmp_path = tf.name
    try:
        subprocess.run([NODE_BIN, SYNC_MJS, tmp_path], check=True, timeout=60)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def main():
    t_start = time.time()
    specs = json.loads(SPECS_FILE.read_text(encoding="utf-8"))
    project_id = specs["projectId"]

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as main_pool:
        # 1. Global voices registration in parallel
        f_voices = main_pool.submit(bind_all_voices, project_id, specs["characters"])

        # 2. Spark minimax-h3-image for all 28 scenes + 25 props
        f_spark = main_pool.submit(run_spark_scenes_and_props, specs["scenes"], specs["props"])

        # 3. Vtrix 12-character concurrent pool (each character spawns up to 5 view tasks gated by VTRIX_SEM=24)
        def run_all_chars():
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as cpool:
                futs = {cpool.submit(generate_one_character, c): c["name"] for c in specs["characters"]}
                for f in concurrent.futures.as_completed(futs):
                    f.result()

        f_chars = main_pool.submit(run_all_chars)

        f_voices.result()
        f_spark.result()
        f_chars.result()

    log("All media generated & voices registered! Uploading & syncing to project...")
    upload_and_sync_all_images(specs)
    log(f"ALL 87 PROJECT ASSETS COMPLETE in {(time.time()-t_start)/60:.1f} min!")


if __name__ == "__main__":
    main()
