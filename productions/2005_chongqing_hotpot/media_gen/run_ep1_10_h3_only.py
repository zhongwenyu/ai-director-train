#!/usr/bin/env python3
"""Generate & bind ONLY the 44 assets required for Episodes 1-10 of playlet-mwj57ecn-9658ad48:
- 20 Characters (Leads 叶寻 & 夏芊芊 already completed; ALL remaining supporting characters generated 100% via Spark minimaxh3image — ZERO Vtrix calls!)
- 14 Scenes (100% Spark minimaxh3image, 576x1024 <= 1024px)
- 10 Props (100% Spark minimaxh3image, 512x512 <= 512px, pure white RGB 255,255,255)
- Voices: preserved directly from matched Global Asset voices (<= 3.0s, no replacement)
Strictly saved ONLY to project playlet-mwj57ecn-9658ad48 (never touches studio_global_assets).
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
from studio_api import Studio  # noqa: E402

BASE_DIR = Path("/home/zhongwenyu/project/ai-director-train/productions/2005_chongqing_hotpot/media_gen")
SPECS_FILE = BASE_DIR / "asset_specs.json"
OUT_ROOT = BASE_DIR / "outputs"
CHAR_OUT = OUT_ROOT / "characters"
SCENE_OUT = OUT_ROOT / "scenes"
PROP_OUT = OUT_ROOT / "props"
COMPOSE_SCRIPT = str(STUDIO_ROOT / "scripts" / "compose-character-sheet.py")
SYNC_MJS = str(BASE_DIR / "sync_character_fields.mjs")
NODE_BIN = "/home/zhongwenyu/.local/lib/node-v22.23.4-linux-x64/bin/node"

SSH_OPTS = ["-i", str(Path.home() / ".ssh" / "id_ed25519_spark"), "-o", "BatchMode=yes"]
SPARK_HOST = "admin@192.168.0.149"
COMFY_DIR = "/home/admin/minimax-h3-image/ComfyUI"
RESAMPLE = getattr(Image, "Resampling", Image).LANCZOS
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
    bg = Image.new("RGB", im.size, (246, 246, 246))
    diff = ImageChops.difference(im, bg).convert("L").point(lambda p: 255 if p > 14 else 0)
    bbox = diff.getbbox()
    if not bbox:
        return im
    x0, y0, x1, y1 = bbox
    bw, bh = max(1, x1 - x0), max(1, y1 - y0)
    pad_y = max(16, int(bh * 0.055))
    pad_x = max(24, int(bw * 0.12))
    cropped = im.crop((max(0, x0 - pad_x), max(0, y0 - pad_y), min(im.width, x1 + pad_x), min(im.height, y1 + pad_y)))
    th = max(cropped.height, int(cropped.width * 4 / 3))
    tw = max(cropped.width, int(round(th * 0.62)))
    canvas = Image.new("RGB", (tw, th), (255, 255, 255))
    canvas.paste(cropped, ((tw - cropped.width) // 2, (th - cropped.height) // 2))
    return canvas


def save_limited_image(src_path: Path, dst_path: Path, max_edge: int, fmt: str = "JPEG", trim_body: bool = False):
    with Image.open(src_path) as raw:
        rgb = to_white_rgb(raw)
    # Snap near-white background halo (>=249) to pure white 255,255,255
    px = rgb.load()
    w, h = rgb.size
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            if r >= 249 and g >= 249 and b >= 249:
                px[x, y] = (255, 255, 255)
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


def spark_h3_generate(prompt: str, ref_paths: list, width: int, height: int, seed: int, prefix: str, out_path: Path):
    if out_path.is_file() and out_path.stat().st_size > 4096:
        return
    remote_refs = []
    ref_cache_dir = OUT_ROOT / ".h3_refs_1k"
    ref_cache_dir.mkdir(parents=True, exist_ok=True)
    for idx, rp in enumerate(ref_paths):
        rp = Path(rp)
        # Pre-downscale reference to <=1024 JPEG for fast SCP + fast VAE/VL encoding
        local_1k = ref_cache_dir / f"{rp.stem}_{rp.stat().st_size}_1k.jpg"
        if not local_1k.is_file():
            save_limited_image(rp, local_1k, 1024, "JPEG", trim_body=False)
        rname = f"ep10_{prefix}_{idx}.jpg"
        subprocess.run(["scp", "-q", *SSH_OPTS, str(local_1k), f"{SPARK_HOST}:{COMFY_DIR}/input/{rname}"], check=True, timeout=60)
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

pid = call('/prompt', {{'prompt':g,'client_id':'ep10-h3-char'}})['prompt_id']
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


def generate_supporting_character_h3(c: dict, idx: int):
    aid = c["assetId"]
    name = c["name"]
    ckey = c["globalCharacterKey"]
    cdir = CHAR_OUT / aid
    cdir.mkdir(parents=True, exist_ok=True)
    sheet_jpg = cdir / "sheet_1024x576.jpg"
    front_1k = cdir / "front_1k.jpg"

    if sheet_jpg.is_file() and front_1k.is_file() and all((cdir / f"{k}_1k.jpg").is_file() for k in ["torsoFront", "torsoSide", "back", "faceFront", "faceLeft"]):
        log(f"[CHAR SKIP] {name} ({ckey}) already complete")
        return

    t0 = time.time()
    ref_calm = c["faceCalmRef"]
    ref_expr = c.get("faceExprRef")
    hair = c["hairDesc"]
    outfit = c["outfitDesc"]
    expr_label = c["exprLabel"]
    expr_desc = c["exprDesc"]
    base_seed = 2027000 + idx * 10

    wrist_rule = (
        "右手腕包扎干净整洁的白色医用透气护腕绷带，双臂自然垂放于身体两侧；"
        if name == "夏建国"
        else "双臂与手腕干净自然垂放于身体两侧（除服装描述提及的手表外，手腕绝无任何绷带或护腕）；"
    )
    youth_guard = (
        "保持24-27岁年轻俊朗/明艳轻熟青年的紧致年轻容貌，绝无中年沧桑皱纹；"
        if any(k in name for k in ["林双双", "楚南", "赵帆", "苏晴", "周凯", "陈浩", "李薇", "小石头"])
        else ""
    )

    raw_front = cdir / "raw_front.png"
    p_front = (
        f"基于 <Picture 1> 中人物（{c['gender']}，{c['ageDesc']}）的五官骨相与脸型轮廓，100%保持同一人物身份与精致明亮电影感写实真人画风。{youth_guard}"
        f"生成单张独立【完整人物全身0度正面立姿定妆图】（含完整头部、面部五官与发型，严禁拼图）：发型为{hair}（去除 <Picture 1> 旧围巾或旧衣领）；全套穿搭换为：{outfit}。"
        f"去除一切包袋与手持杂物，{wrist_rule}头、脸、身体严格0度正对镜头平视自然站立，表情平静自然，从头顶头发到双脚鞋底完整呈现（占画面高度约88%，上下留白），纯白背景（RGB 255,255,255），光线明亮干净柔和，无阴影背景无文字水印。"
    )
    spark_h3_generate(p_front, [ref_calm], 896, 1184, base_seed + 1, f"{ckey}_{aid[:6]}_front", raw_front)

    p_tf = (
        f"基于 <Picture 1> 的完整正面全身人物图，100%保持完全相同的全套服装、颜色、材质、双手姿态与鞋履（{outfit}）。"
        "输出单张独立【无头正面全身人体服装图】：仅从锁骨上方的颈根处自然干净平整截断去除整个头部与全部头发（画面顶部绝不出现头、脸、下巴和头发，颈根截面平整正常肤色，非受伤场景），"
        "完整展示锁骨、双肩、上衣、下装、双手至双脚鞋底，主体居中占画面高度约88%，纯白背景（RGB 255,255,255），光线明亮干净，单人单视角无拼图无文字。"
    )
    spark_h3_generate(p_tf, [raw_front], 896, 1184, base_seed + 2, f"{ckey}_{aid[:6]}_tf", cdir / "raw_torsoFront.png")

    p_ts = (
        f"基于 <Picture 1> 的完整正面全身人物图，100%保持完全相同的全套服装、颜色、材质与鞋履（{outfit}）。"
        "输出单张独立【无头90度正左侧面全身人体服装图】：彻底去除整个头部、脸部与全部头发，仅保留锁骨上方平整颈根至双脚鞋底；"
        "将人物身体严格旋转至90度正左侧面轮廓（胸腹、衣襟前侧与双脚鞋尖全部朝向画面左侧边缘，后背朝向画面右侧，双肩重叠呈标准侧面轮廓，双臂自然下垂），主体占画面高度约88%，纯白背景（RGB 255,255,255），光线明亮干净，无拼图无文字。"
    )
    spark_h3_generate(p_ts, [raw_front], 896, 1184, base_seed + 3, f"{ckey}_{aid[:6]}_ts", cdir / "raw_torsoSide.png")

    p_back = (
        f"基于 <Picture 1> 的完整正面全身人物图，100%保持同一人物身材比例、后脑勺背面发型（{hair}）以及全套服装与鞋履的背面剪裁（{outfit}）。"
        "输出单张独立【完整人物全身180度正背面立姿图】（含完整头部与后脑头发）：人物严格180度背对镜头自然直立，双臂自然下垂，不回头不露脸，从头顶头发至双脚鞋跟完整呈现，占画面高度约88%，纯白背景（RGB 255,255,255），光线明亮干净，无拼图无文字。"
    )
    spark_h3_generate(p_back, [raw_front], 896, 1184, base_seed + 4, f"{ckey}_{aid[:6]}_back", cdir / "raw_back.png")

    raw_face = cdir / "raw_faceFront.png"
    p_face = (
        f"基于 <Picture 1> 的人物五官骨相与 <Picture 2> 的新换服装造型：100%保持 <Picture 1> 同一人的五官脸型与眼神气质，{youth_guard}"
        f"同时去除 <Picture 1> 旧衣领或围巾，将发型与上衣领口切换为 <Picture 2> 的造型（发型：{hair}；领口匹配：{outfit}）。"
        "输出单张独立【正面人物面部图（平静）】：头、脸、鼻尖严格0度正对镜头平视，完整保留头顶头发、面部、脖子及少量新服装肩领（占画面高度约85%），表情自然平静，纯白背景（RGB 255,255,255），精致明亮电影感写实光效，无拼图无文字。"
    )
    spark_h3_generate(p_face, [ref_calm, raw_front], 1024, 1024, base_seed + 5, f"{ckey}_{aid[:6]}_face", raw_face)

    if ref_expr:
        p_expr = (
            f"基于 <Picture 1> 的人物真实表情参考与 <Picture 2> 的新发型领口正面头像：100%保持 <Picture 2> 同一张脸的五官骨相、发型（{hair}）与新服装领口，{youth_guard}"
            f"同时将面部表情还原为 <Picture 1> 所示的自然生动【{expr_label}】神态（{expr_desc}，真实微表情不夸张）。"
            "输出单张独立【人物面部表情图】：正面平视镜头，完整保留头顶头发、面部、脖子及少量新服装肩领（占画面高度约85%），纯白背景（RGB 255,255,255），精致明亮电影感写实光效，无拼图无文字。"
        )
        spark_h3_generate(p_expr, [ref_expr, raw_face], 1024, 1024, base_seed + 6, f"{ckey}_{aid[:6]}_expr", cdir / "raw_faceLeft.png")
    else:
        p_expr = (
            f"基于 <Picture 1> 的同一人物正面头像：100%保持 <Picture 1> 完全相同的五官骨相、发型（{hair}）与上衣领口，{youth_guard}"
            f"仅将面部神态自然调整为生动的【{expr_label}】（{expr_desc}，真实微表情不夸张）。"
            "输出单张独立【人物面部表情图】：正面平视镜头，完整保留头顶头发、面部、脖子及少量新服装肩领（占画面高度约85%），纯白背景（RGB 255,255,255），精致明亮电影感写实光效，无拼图无文字。"
        )
        spark_h3_generate(p_expr, [raw_face], 1024, 1024, base_seed + 6, f"{ckey}_{aid[:6]}_expr", cdir / "raw_faceLeft.png")

    # Downscale all views strictly <= 1024px (1K) and compose 1024x576 sheet
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
    log(f"[H3 CHAR DONE] {name} ({ckey}) -> 1024x576 sheet in {time.time()-t0:.1f}s")


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


def sync_ready_ep1_10_to_studio(project_id: str, style_prompt: str, chars: list, scenes: list, props: list):
    """Incrementally upload & bind every completed Ep 1-10 character, scene, prop, and global voice sample into playlets-studio."""
    studio = Studio()
    proj = studio.project(project_id)
    existing_assets = {a["id"]: a for a in proj["assets"]}
    gv_map = {v["characterKey"]: v for v in studio.request("GET", "/api/studio/global-voices")}

    remove_media_ids = [m["id"] for m in proj.get("media", []) if m.get("type") == "voice-source"]
    media_updates = {}
    asset_updates = []

    for c in chars:
        aid = c["assetId"]
        a = existing_assets[aid]
        ckey = c["globalCharacterKey"]
        gv = gv_map[ckey]
        upd = {
            "assetId": aid,
            "description": c.get("description", ""),
            "prompt": c["prompt"],
            "globalCharacterKey": ckey,
        }
        changed = False

        # Bind original Global Voice WAV directly (<=3s, no VoiceDesign, no dependency on inactive qwen3-tts daemon)
        if not a.get("voiceSampleId") or a.get("globalCharacterKey") != ckey:
            wav_path = Path(c["voiceWav"])
            dur = round(float(gv.get("duration") or probe_audio_duration(wav_path)), 2)
            profile = {
                "description": f"全局资产原声（{gv['name']}）：{gv.get('description', '')}",
                "sampleText": (gv.get("transcript") or "我知道了。").strip()[:75],
                "language": "Chinese",
                "seed": 0,
            }
            vmid = upload_binary(studio, project_id, wav_path, "audio/wav", f"{c['name']}-{ckey}-原声参考.wav", aid, "voice-sample")
            media_updates[vmid] = {
                "type": "voice-sample",
                "targetId": aid,
                "duration": dur,
                "voiceProvider": "qwen-reference",
                "voiceProfile": profile,
                "globalVoiceId": gv["id"],
            }
            upd.update({
                "voiceSampleId": vmid,
                "voiceDuration": dur,
                "voiceProvider": "qwen-reference",
                "voiceReview": "pending",
                "globalVoiceId": gv["id"],
                "voiceProfile": profile,
            })
            changed = True
            log(f"[VOICE BOUND] {c['name']} -> {ckey} ({gv['name']}, {dur:.2f}s)")

        # Bind 5-panel character sheet + 6 <=1K views if ready on disk
        cdir = CHAR_OUT / aid
        sheet_f = cdir / "sheet_1024x576.jpg"
        if sheet_f.is_file() and all((cdir / f"{v}_1k.jpg").is_file() for v in ["front", "torsoFront", "torsoSide", "back", "faceFront", "faceLeft"]):
            if not (a.get("sheetImageId") and a.get("imageId") == a.get("sheetImageId") and a.get("globalCharacterKey") == ckey):
                view_ids = {}
                for vname in ["front", "torsoFront", "torsoSide", "back", "faceFront", "faceLeft"]:
                    vf = cdir / f"{vname}_1k.jpg"
                    mid = upload_binary(studio, project_id, vf, "image/jpeg", f"{c['name']}-{vname}.jpg", aid, "character-view")
                    view_ids[vname] = mid
                    media_updates[mid] = {"type": "character-view", "view": vname, "targetId": aid}
                sheet_id = upload_binary(studio, project_id, sheet_f, "image/jpeg", f"{c['name']}-五格资产图.jpg", aid, "character-sheet")
                media_updates[sheet_id] = {
                    "type": "character-sheet",
                    "targetId": aid,
                    "viewIds": view_ids,
                    "metadata": {"width": 1024, "height": 576, "views": ["torsoFront", "torsoSide", "back", "faceFront", "faceLeft"]},
                }
                upd.update({
                    "imageId": sheet_id,
                    "sheetImageId": sheet_id,
                    "frontImageId": view_ids["front"],
                    "viewIds": view_ids,
                })
                changed = True
                log(f"[UPLOAD CHAR] {c['name']} -> sheet={sheet_id[:8]}")

        if changed:
            asset_updates.append(upd)

    for s in scenes:
        aid = s["assetId"]
        a = existing_assets[aid]
        sf = SCENE_OUT / f"{aid}_1k.png"
        if not a.get("imageId") and sf.is_file():
            mid = upload_binary(studio, project_id, sf, "image/png", f"{s['name']}.png", aid, "asset-image")
            asset_updates.append({"assetId": aid, "prompt": s["prompt"], "imageId": mid})
            log(f"[UPLOAD SCENE] {s['name']} -> {mid[:8]}")

    for p in props:
        aid = p["assetId"]
        a = existing_assets[aid]
        pf = PROP_OUT / f"{aid}_512.png"
        if not a.get("imageId") and pf.is_file():
            mid = upload_binary(studio, project_id, pf, "image/png", f"{p['name']}.png", aid, "asset-image")
            asset_updates.append({"assetId": aid, "prompt": p["prompt"], "imageId": mid})
            log(f"[UPLOAD PROP] {p['name']} -> {mid[:8]}")

    if asset_updates or media_updates or remove_media_ids:
        sync_payload = {
            "projectId": project_id,
            "stylePrompt": style_prompt,
            "removeMediaIds": remove_media_ids,
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
    t0 = time.time()
    specs = json.loads(SPECS_FILE.read_text(encoding="utf-8"))
    project_id = specs["projectId"]
    proj_disk = json.loads((STUDIO_ROOT / "playlets" / project_id / "project.json").read_text(encoding="utf-8"))

    ep1_10_names = {
        n
        for ep in proj_disk["episodes"][:10]
        for s in ep.get("shots", [])
        for n in s.get("assetNames", [])
    }

    chars = [c for c in specs["characters"] if c["name"] in ep1_10_names]
    scenes = [s for s in specs["scenes"] if s["name"] in ep1_10_names]
    props = [p for p in specs["props"] if p["name"] in ep1_10_names]
    log(f"Scoped strictly to Episodes 1-10: {len(chars)} characters, {len(scenes)} scenes, {len(props)} props (total {len(chars)+len(scenes)+len(props)} assets)")

    # Immediately sync all already-completed images (34/44) + all 20 voices into Workstation DB first!
    sync_ready_ep1_10_to_studio(project_id, specs["stylePrompt"], chars, scenes, props)

    if "--sync-only" in sys.argv:
        return

    # Generate remaining characters on Spark minimaxh3image and sync each one immediately upon completion!
    for idx, c in enumerate(chars):
        sheet_f = CHAR_OUT / c["assetId"] / "sheet_1024x576.jpg"
        was_done = sheet_f.is_file()
        generate_supporting_character_h3(c, idx)
        if not was_done and sheet_f.is_file():
            sync_ready_ep1_10_to_studio(project_id, specs["stylePrompt"], [c], [], [])

    log(f"ALL 44 EPISODE 1-10 ASSETS GENERATED & BOUND IN {(time.time()-t0)/60:.1f} MIN (0 new Vtrix calls)!")


if __name__ == "__main__":
    main()
