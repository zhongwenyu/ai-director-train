#!/usr/bin/env python3
"""
End-to-end Episode 2 (10 shots) + Episode 3 (9 shots) execution pipeline:
1. Re-generate 3-2-10 keyframe (bare forearms matching 夏芊芊) in parallel with GPU work.
2. Generate 4 dedicated short 368p VO clips (2-1-07, 2-2-01, 3-2-04, 3-2-10) on 4070 Ti SUPER in parallel!
3. Generate Episode 2 (10 shots, 480p Pika-H3-Flex) on 5090 -> apply precision VO placement -> inspect -> upload to Workstation -> verify automatic Episode 2 film merge -> compile & bind separated BGM + WebVTT subtitles!
4. Generate Episode 3 (9 shots, 480p Pika-H3-Flex) on 5090 -> apply precision VO placement -> inspect -> upload to Workstation -> verify automatic Episode 3 film merge -> compile & bind separated BGM + WebVTT subtitles!
"""
import array
import json
import math
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import http.cookiejar
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

STUDIO_BRIDGE = Path("/home/zhongwenyu/project/playlets-studio/skills/studio-bridge/scripts")
SKILL_SCRIPTS = Path("/home/zhongwenyu/project/ai-director-train/.agents/skills/hit-video/scripts")
sys.path.insert(0, str(STUDIO_BRIDGE))
sys.path.insert(0, str(SKILL_SCRIPTS))

import vtrix_image  # noqa: E402
import vo_split  # noqa: E402
import pika_runner  # noqa: E402
from compress_1k import compress_image_to_1k  # noqa: E402
from post_bgm_subtitles import compile_post_pack  # noqa: E402

WORK_DIR = Path("/home/zhongwenyu/project/ai-director-train/productions/2005_chongqing_hotpot/ep02_03_video_gen")
STUDIO_ROOT = Path("/home/zhongwenyu/project/playlets-studio")
PROJECT_ID = "playlet-mwj57ecn-9658ad48"
EP2_ID = "41d1dd8c-4172-4a26-b985-63fe17e96dce"
EP3_ID = "ed05ad9d-55c2-4a89-a8af-4d88d640ed07"
BASE_URL = "http://127.0.0.1:8765"


def make_studio_client():
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    pw = (STUDIO_ROOT / "runtime/initial-password.txt").read_text(encoding="utf-8").strip()
    req = urllib.request.Request(
        f"{BASE_URL}/api/login",
        data=json.dumps({"password": pw}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with opener.open(req, timeout=15) as resp:
        assert resp.status == 200, f"Login failed: {resp.status}"
    return opener


def studio_json(opener, method: str, path: str, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    with opener.open(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else None


def studio_upload(opener, file_path: Path, mime: str, name: str, target_id: str = "", mtype: str = "other") -> str:
    qs = urllib.parse.urlencode({"name": name, "targetId": target_id, "type": mtype})
    req = urllib.request.Request(
        f"{BASE_URL}/api/studio/projects/{PROJECT_ID}/upload?{qs}",
        data=Path(file_path).read_bytes(),
        headers={"Content-Type": mime},
        method="POST",
    )
    with opener.open(req, timeout=120) as resp:
        out = json.loads(resp.read().decode("utf-8"))
    if isinstance(out, dict) and "id" in out and "assets" not in out:
        return out["id"]
    media = out.get("media", [])
    for m in reversed(media):
        if m.get("name") == name:
            return m["id"]
    return media[-1]["id"]


def fix_3210_keyframe():
    amap = json.loads((WORK_DIR / "asset_map.json").read_text(encoding="utf-8"))
    out_2k = WORK_DIR / "keyframes_2k/3-2-10.png"
    out_1k = WORK_DIR / "keyframes_1k/3-2-10_1k.png"
    marker = WORK_DIR / "keyframes_1k/.3-2-10_fixed"
    if marker.is_file():
        return
    print("[kf-fix] Regenerating 3-2-10 with 夏芊芊 bare forearm match...", flush=True)
    vtrix_image.generate_vtrix_image(
        prompt=(
            "以图1的暖黄台灯原木账桌面与红印泥盒为背景，参照图2的手写方格信纸质感，手部与裸露小臂肤色细节严格保持与图3短袖装年轻女孩一致（裸露小臂，严禁出现长袖蕾丝袖口，画面中不露人脸）。"
            "高机位垂直俯拍桌面特写构图：暖黄台灯光下，写有工整蓝黑钢笔字迹的方格信纸末尾已并排印着两枚鲜红指印，旁边敞开着红色圆铁盒印泥；"
            "图3女孩裸露小臂伸出，右手大拇指蘸着鲜红印泥正稳稳按在纸尾第三处签名位置落下第三枚鲜红手印，明亮清晰电影实拍质感，竖屏9:16构图，严禁出现任何乱码字幕或水印。"
        ),
        out_path=out_2k,
        ref_files=[
            amap["渝清记深夜账房"]["main_1k"],
            amap["9·19手写合伙及秘方公证协议"]["main_1k"],
            amap["夏芊芊"]["front_1k"],
        ],
        aspect_ratio="9:16",
        resolution="2K",
    )
    compress_image_to_1k(out_2k, out_1k, max_side=1024)
    marker.write_text("ok", encoding="utf-8")
    print("[kf-fix] 3-2-10 regenerated cleanly!", flush=True)


def gen_short_vo_4070(spec: dict, outdir: Path):
    sid = spec["id"]
    vs = spec["vo_short_spec"]
    shot_dir = outdir / sid
    shot_dir.mkdir(parents=True, exist_ok=True)
    vo_mp4 = shot_dir / "vo_short_368p.mp4"
    if vo_mp4.is_file() and vo_mp4.stat().st_size > 10000:
        print(f"[4070-vo] Reuse existing {sid}/vo_short_368p.mp4", flush=True)
        return vo_mp4
    prompt = (
        "A realistic cinematic close-up of <Subject 1> indoors in warm light.\n"
        f"[Shot 1] Close-up, static camera. <Subject 1> speaks clearly and briskly with {vs['emotion']}: "
        f"<d>[Chinese] ({vs['speaker']} in Picture 1 speaks clearly with {vs['emotion']}): {vs['text']}</d> "
        "Immediately upon finishing the sentence, <Subject 1> presses his lips shut without another sound. "
        "Clean dry vocal recording, no background music."
    )
    assert not pika_runner.lint_zero_appearance(prompt, f"{sid}:vo_short")
    old_ckpt = vo_split.LOWRES_CHECKPOINT
    vo_split.LOWRES_CHECKPOINT = ""  # Use 4070 default Pika-H3-Flex
    try:
        print(f"[4070-vo] Generating 6s 368p VO for {sid}...", flush=True)
        vo_split.h3_lowres(
            vo_mp4, prompt, 6, int(spec["seed"]) + 77, "9:16", "reference",
            [Path(vs["ref_img"])], None, None, [Path(vs["ref_aud"])]
        )
        print(f"[4070-vo] Finished {sid}/vo_short_368p.mp4", flush=True)
    finally:
        vo_split.LOWRES_CHECKPOINT = old_ckpt
    return vo_mp4


def apply_short_vo(base_mp4: Path, vo_mp4: Path, vs: dict, out_mp4: Path):
    with tempfile.NamedTemporaryFile(suffix=".wav") as f:
        subprocess.run(["ffmpeg", "-y", "-i", str(vo_mp4), "-ac", "1", "-ar", "16000", f.name],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        with wave.open(f.name, "rb") as w:
            sr = w.getframerate()
            raw = array.array("h")
            raw.frombytes(w.readframes(w.getnframes()))
    win = int(sr * 0.08)
    active = []
    for i in range(0, len(raw), win):
        seg = raw[i:i+win]
        rms = math.sqrt(sum((x / 32768.0) ** 2 for x in seg) / len(seg)) if seg else 0.0
        if rms > 0.018:
            active.append(i / sr)
    total = len(raw) / sr
    ss = max(0.0, (min(active) - 0.10)) if active else 0.2
    se = min(total, (max(active) + 0.18)) if active else min(total, 4.0)
    dur = se - ss
    max_win = float(vs["max_window"])
    dst_s = float(vs["dst_start"])

    if dur > max_win:
        speed = min(1.22, dur / max(0.5, max_win - 0.12))
        fit_wav = vo_mp4.with_name("vo_short_fit.wav")
        subprocess.run([
            "ffmpeg", "-v", "error", "-y", "-i", str(vo_mp4),
            "-af", f"atrim={ss:.3f}:{se:.3f},asetpts=PTS-STARTPTS,atempo={speed:.4f}",
            "-ar", "48000", "-ac", "2", str(fit_wav)
        ], check=True)
        fit_dur = dur / speed
        pika_runner.place_vo_segments(
            base_mp4, fit_wav, [(0.0, fit_dur, dst_s)], out_mp4,
            base_duck=float(vs.get("base_duck", 0.28)), vo_gain=1.45, raw_slice=True
        )
        return round(dst_s, 2), round(dst_s + fit_dur, 2)
    else:
        pika_runner.place_vo_segments(
            base_mp4, vo_mp4, [(ss, se, dst_s)], out_mp4,
            base_duck=float(vs.get("base_duck", 0.28)), vo_gain=1.45, raw_slice=True
        )
        return round(dst_s, 2), round(dst_s + dur, 2)


def run_episode_5090(plan: list, outdir: Path, vo_futures: dict):
    cache_1k = outdir / "inputs_1k"
    cache_1k.mkdir(parents=True, exist_ok=True)
    vo_windows_actual = {}

    for sp in plan:
        sid = sp["id"]
        shot_dir = outdir / sid
        shot_dir.mkdir(parents=True, exist_ok=True)
        final_mp4 = shot_dir / "video.mp4"
        novo_mp4 = shot_dir / "video_novo.mp4" if "vo_short_spec" in sp else final_mp4

        if final_mp4.is_file() and (shot_dir / "video.json").is_file():
            print(f"[5090] Skip existing {sid}/video.mp4", flush=True)
            meta = json.loads((shot_dir / "video.json").read_text(encoding="utf-8"))
            if "vo_window_actual" in meta:
                vo_windows_actual[sid] = tuple(meta["vo_window_actual"])
        else:
            refs_1k = [pika_runner.ensure_1k_image(Path(p), cache_1k) for p in sp["ref_images"]]
            audios = [Path(p) for p in sp.get("ref_audios", [])]
            print(f"[5090] Generating {sid} ({sp['duration']}s, 480p, refs={len(refs_1k)}, audios={len(audios)})...", flush=True)
            meta = pika_runner.call_pika_5090(
                novo_mp4, sp["prompt"], int(sp["duration"]), int(sp["seed"]),
                sp["aspect_ratio"], "480p", refs_1k, audios
            )
            if "vo_short_spec" in sp:
                vo_mp4 = vo_futures[sid].result()
                ws, we = apply_short_vo(novo_mp4, vo_mp4, sp["vo_short_spec"], final_mp4)
                meta["vo_window_actual"] = [ws, we]
                vo_windows_actual[sid] = (ws, we)
                print(f"[5090+VO] Placed {sid} VO at [{ws:.2f}s .. {we:.2f}s]", flush=True)
            (shot_dir / "video.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[5090] Completed {sid} ({meta['actual_duration']}s)", flush=True)

        # Extract contact sheet via inspect_video.py
        insp_dir = shot_dir / "inspect"
        if not (insp_dir / "contact_sheet.jpg").is_file():
            subprocess.run([
                "python3", str(SKILL_SCRIPTS / "inspect_video.py"),
                "--outdir", str(insp_dir), str(final_mp4)
            ], check=True)
    return vo_windows_actual


EP2_CUES = {
    "2-1-01": [
        {"start": 3.3, "end": 6.5, "kind": "dialogue", "speaker": "夏芊芊", "text": "前晚熬的川贝梨膏，别磕碎了。"},
        {"start": 6.8, "end": 8.9, "kind": "dialogue", "speaker": "叶寻", "text": "先顾你自家灶台吧。"},
    ],
    "2-1-04": [
        {"start": 0.2, "end": 4.3, "kind": "dialogue", "speaker": "夏建国", "text": "刘师傅，外头三桌学生等半钟头了，好歹炒完这三桌再走啊！"},
        {"start": 4.5, "end": 10.3, "kind": "dialogue", "speaker": "刘大厨", "text": "正街新盘店的大老板开两千二管员工餐，今晚点名到岗。半个月九百块工钱，现结！"},
        {"start": 10.5, "end": 13.4, "kind": "dialogue", "speaker": "苏晴", "text": "七点半礼堂试麦，连碗面都没下锅，退单吧。"},
    ],
    "2-1-07": [
        {"start": 0.2, "end": 3.8, "kind": "caption", "text": "夏家小馆存折余额：6,200元"},
        {"start": 0.35, "end": 3.8, "kind": "vo", "speaker": "叶寻", "text": "账上只剩六千二，楚南挖走厨子就是想逼死夏家。"},
        {"start": 4.1, "end": 6.6, "kind": "dialogue", "speaker": "夏芊芊", "text": "九百块点清，不送。"},
    ],
    "2-1-10": [
        {"start": 0.1, "end": 3.3, "kind": "dialogue", "speaker": "叶寻", "text": "夏叔，早上吊的那锅猪骨老母鸡汤还在火上吧？"},
        {"start": 3.6, "end": 6.8, "kind": "dialogue", "speaker": "夏建国", "text": "在火上，可她们赶着试音忌辣……"},
        {"start": 7.1, "end": 11.2, "kind": "dialogue", "speaker": "叶寻", "text": "给我十分钟，骨汤微辣烫鲜毛肚——呛一下嗓子，这桌免单。"},
    ],
    "2-1-13": [
        {"start": 0.2, "end": 3.8, "kind": "dialogue", "speaker": "苏晴", "text": "十分钟？行，耽误试麦我真走人。"},
    ],
    "2-2-01": [
        {"start": 0.45, "end": 6.8, "kind": "vo", "speaker": "叶寻", "text": "鲜梨汁化牛油，温醪糟退椒燥，辣香入魂却半点不呛嗓。"},
        {"start": 8.0, "end": 11.3, "kind": "dialogue", "speaker": "夏建国", "text": "温醪糟退椒燥……这是叶老爷子的绝活！"},
    ],
    "2-2-04": [
        {"start": 0.1, "end": 2.6, "kind": "dialogue", "speaker": "叶寻", "text": "只是骨汤借味救急。芊芊姐，上菜。"},
        {"start": 5.3, "end": 7.6, "kind": "dialogue", "speaker": "苏晴", "text": "咪——嘛——咪……"},
        {"start": 7.9, "end": 12.1, "kind": "dialogue", "speaker": "苏晴", "text": "真神了，嗓子清清亮亮的！快动筷，吃完赶得上排练！"},
    ],
    "2-2-07": [
        {"start": 0.2, "end": 2.8, "kind": "dialogue", "speaker": "苏晴", "text": "老板，明晚还能订这锅吗？"},
        {"start": 3.1, "end": 8.4, "kind": "dialogue", "speaker": "叶寻", "text": "今晚只是借味救急。等正经底料焖透退火，后天傍晚开张，给你们留桌。"},
        {"start": 8.7, "end": 11.3, "kind": "dialogue", "speaker": "苏晴", "text": "一言为定，后天播音社来两桌！"},
    ],
    "2-2-10": [],
    "2-2-13": [
        {"start": 0.2, "end": 5.8, "kind": "dialogue", "speaker": "林双双", "text": "叶寻，赵主厨明早到店，出来把林家肉菜账交接清楚——我只等你五分钟。"},
    ],
}

EP2_BGM = [
    {
        "label": "罢厨退单困局与接管灶台（沉静复盘 Mixkit Free）",
        "file": "/home/zhongwenyu/project/audio-library/_files/mixkit-music-374.mp3",
        "start_shot": "2-1-01",
        "end_shot": "2-1-13",
        "gain": 0.42,
        "fade_in": 0.8,
        "fade_out": 1.0,
    },
    {
        "label": "本草退燥绝活与播音生亮嗓爽点（伴你归家 Mixkit Free）",
        "file": "/home/zhongwenyu/project/audio-library/_files/mixkit-music-350.mp3",
        "start_shot": "2-2-01",
        "end_shot": "2-2-07",
        "src_offset": 14.0,
        "gain": 0.45,
        "fade_in": 1.0,
        "fade_out": 0.6,
    },
    {
        "label": "林双双闯门拍钥匙五分钟通牒悬念（深鼓悬疑渐强 Mixkit Free）",
        "file": "/home/zhongwenyu/project/audio-library/_files/mixkit-sfx-682.wav",
        "start_shot": "2-2-10",
        "start_delta": 1.5,
        "end_shot": "2-2-13",
        "align_end": True,
        "gain": 0.50,
        "fade_in": 0.7,
        "fade_out": 0.25,
    },
]

EP3_CUES = {
    "3-1-01": [
        {"start": 2.2, "end": 5.1, "kind": "dialogue", "speaker": "林双双", "text": "赌气跑来给人打杂，有意思吗？"},
        {"start": 5.3, "end": 10.2, "kind": "dialogue", "speaker": "林双双", "text": "赵主厨不干粗洗采买，你明天回来管后厨杂务，我给你开八百一个月。"},
    ],
    "3-1-04": [
        {"start": 0.2, "end": 3.8, "kind": "dialogue", "speaker": "叶寻", "text": "林家上月肉菜账在第三页，没有欠款。"},
        {"start": 4.1, "end": 6.1, "kind": "dialogue", "speaker": "林双双", "text": "你什么意思？"},
        {"start": 6.4, "end": 10.2, "kind": "dialogue", "speaker": "叶寻", "text": "下午走出林家店门起，咱们就两清了。钥匙收好。"},
    ],
    "3-1-07": [
        {"start": 0.2, "end": 4.3, "kind": "dialogue", "speaker": "林双双", "text": "你宁肯拿爷爷的方子填夏家这快封门的破院子？"},
        {"start": 4.6, "end": 9.2, "kind": "dialogue", "speaker": "夏芊芊", "text": "小寻跟我们合伙做正经买卖，不打零工。林同学慢走。"},
    ],
    "3-1-09": [
        {"start": 0.2, "end": 4.6, "kind": "dialogue", "speaker": "林双双", "text": "行，我倒要看看十月八号你们拿什么交房租！"},
    ],
    "3-2-01": [
        {"start": 0.2, "end": 4.3, "kind": "dialogue", "speaker": "夏建国", "text": "小寻，夏叔手打着夹板颠不动勺，不能把你也拖下水。"},
        {"start": 4.6, "end": 9.6, "kind": "dialogue", "speaker": "叶寻", "text": "夏叔，小炒全停，咱们改名“渝清记”，专做不用颠勺的子母锅清润火锅。"},
        {"start": 9.8, "end": 13.5, "kind": "caption", "text": "叶寻存折余额：1,800元（奖学金及勤工俭学）"},
        {"start": 9.9, "end": 13.4, "kind": "dialogue", "speaker": "叶寻", "text": "加上店里六千二凑齐八千本钱，十九天挣房租，来得及。"},
    ],
    "3-2-04": [
        {"start": 3.2, "end": 9.0, "kind": "dialogue", "speaker": "夏芊芊", "text": "合伙就按规矩立字据。我家出铺面家伙占四成九，你出手艺占五成一当家。"},
        {"start": 9.3, "end": 13.8, "kind": "caption", "text": "特别约定：《叶氏清润底料配方》所有权归叶寻个人独有"},
        {"start": 9.35, "end": 13.8, "kind": "vo", "speaker": "叶寻", "text": "上一世林双双哄我签走秘方，这一世，芊芊却逼我把方子攥在自己手里。"},
    ],
    "3-2-07": [
        {"start": 0.2, "end": 3.1, "kind": "dialogue", "speaker": "叶寻", "text": "你把方子单摘出来了？"},
        {"start": 3.4, "end": 7.8, "kind": "dialogue", "speaker": "夏芊芊", "text": "叶爷爷留给你的家底，少写这一条，这字我不签。"},
        {"start": 8.1, "end": 11.2, "kind": "dialogue", "speaker": "夏建国", "text": "听芊芊的！来，摁手印！"},
    ],
    "3-2-10": [
        {"start": 0.25, "end": 3.1, "kind": "vo", "speaker": "叶寻", "text": "五一控股落印，渝清记今晚正式立字！"},
        {"start": 7.1, "end": 10.3, "kind": "dialogue", "speaker": "周有福", "text": "老夏，正街改西餐厅的楚老板刚交两千定金，"},
    ],
    "3-2-13": [
        {"start": 0.1, "end": 2.5, "kind": "dialogue", "speaker": "周有福", "text": "要租你这院子堆酒水杂物！"},
        {"start": 2.7, "end": 6.4, "kind": "dialogue", "speaker": "夏建国", "text": "老周，十月八号才到期，你拎管钳干啥？"},
        {"start": 6.6, "end": 10.7, "kind": "dialogue", "speaker": "周有福", "text": "人家怕你们到期赖着不搬，让我今晚先把后院副水表拧了！"},
    ],
}

EP3_BGM = [
    {
        "label": "退钥匙两清与夏芊芊护短逐客（沉静复盘 Mixkit Free）",
        "file": "/home/zhongwenyu/project/audio-library/_files/mixkit-music-374.mp3",
        "start_shot": "3-1-01",
        "end_shot": "3-1-09",
        "src_offset": 19.5,
        "gain": 0.44,
        "fade_in": 0.8,
        "fade_out": 1.0,
    },
    {
        "label": "倾囊凑本与五一控股护秘方立约（长久的温柔 Mixkit Free）",
        "file": "/home/zhongwenyu/project/audio-library/_files/mixkit-music-38.mp3",
        "start_shot": "3-2-01",
        "end_shot": "3-2-10",
        "end_delta": -7.8,
        "src_offset": 30.0,
        "gain": 0.48,
        "fade_in": 1.2,
        "fade_out": 0.3,
    },
    {
        "label": "周有福拎铁管钳断水逼宫与叶寻横身挡门（深鼓悬疑渐强 Mixkit Free）",
        "file": "/home/zhongwenyu/project/audio-library/_files/mixkit-sfx-682.wav",
        "start_shot": "3-2-10",
        "start_delta": 3.3,
        "end_shot": "3-2-13",
        "align_end": True,
        "gain": 0.52,
        "fade_in": 0.5,
        "fade_out": 0.25,
    },
]


def upload_and_finalize_episode(ep_num: int, ep_id: str, plan: list, takes_dir: Path, cues_map: dict, bgm_segs: list):
    opener = make_studio_client()
    print(f"\n[EP{ep_num}] Uploading {len(plan)} keyframes & 480p videos to Workstation...", flush=True)
    for sp in plan:
        sid = sp["id"]
        shot_uuid = sp["shot_uuid"]
        kf_path = Path(sp["keyframe_2k"])
        vid_path = takes_dir / sid / "video.mp4"
        img_id = studio_upload(opener, kf_path, "image/png", f"ep0{ep_num}_{sid}_kf.png", shot_uuid, "shot_image")
        vid_id = studio_upload(opener, vid_path, "video/mp4", f"ep0{ep_num}_{sid}_480p.mp4", shot_uuid, "shot_video")
        patch = {
            "id": shot_uuid,
            "episodeId": ep_id,
            "imageId": img_id,
            "videoId": vid_id,
            "confirmedImage": True,
            "confirmedVideo": True,
            "videoPrompt": sp["prompt"],
        }
        if sid in ("2-1-04", "2-1-07"):
            proj = studio_json(opener, "GET", f"/api/studio/projects/{PROJECT_ID}")
            sh_cur = next(s for e in proj["episodes"] if e["id"] == ep_id for s in e["shots"] if s["id"] == shot_uuid)
            names = list(sh_cur.get("assetNames") or [])
            if "刘大厨" not in names:
                names.append("刘大厨")
            patch["assetNames"] = names
        studio_json(opener, "PATCH", f"/api/studio/projects/{PROJECT_ID}", {"shot": patch})
        print(f"  [EP{ep_num}] Bound {sid} -> img={img_id[:8]} vid={vid_id[:8]}", flush=True)

    # Wait for automatic EpisodeFilmQueue merge triggered by the final shot PATCH!
    print(f"[EP{ep_num}] Verifying automatic episode film merge...", flush=True)
    film_state = None
    for _ in range(45):
        time.sleep(1.5)
        film_state = studio_json(opener, "GET", f"/api/studio/projects/{PROJECT_ID}/episodes/{ep_id}/video")
        if film_state.get("status") == "completed" and film_state.get("media"):
            break
        if film_state.get("status") == "pending":
            studio_json(opener, "POST", f"/api/studio/projects/{PROJECT_ID}/episodes/{ep_id}/video", {})
    assert film_state and film_state.get("status") == "completed", f"EP{ep_num} film merge did not complete: {film_state}"
    print(f"[EP{ep_num}] AUTO-MERGED CLEAN FILM -> {film_state['media']['id']} ({film_state['media']['name']})", flush=True)

    # Compile & bind separated BGM + WebVTT subtitles
    post_spec = {
        "prefix": f"ep0{ep_num}",
        "shots": [
            {
                "id": sp["id"],
                "studioShotId": sp["shot_uuid"],
                "video": str(takes_dir / sp["id"] / "video.mp4"),
                "cues": cues_map.get(sp["id"], []),
            }
            for sp in plan
        ],
        "bgm_segments": bgm_segs,
    }
    post_dir = WORK_DIR / f"post_ep0{ep_num}"
    post_dir.mkdir(parents=True, exist_ok=True)
    spec_path = post_dir / f"ep0{ep_num}_post_spec.json"
    spec_path.write_text(json.dumps(post_spec, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = compile_post_pack(spec_path, post_dir)

    bgm_id = studio_upload(opener, Path(manifest["bgm_file"]), "audio/mpeg", f"ep0{ep_num}_separated_bgm.mp3", ep_id, "bgm")
    vtt_id = studio_upload(opener, Path(manifest["vtt_file"]), "text/vtt", f"ep0{ep_num}_subtitles.vtt", ep_id, "subtitles")

    studio_json(opener, "PATCH", f"/api/studio/projects/{PROJECT_ID}", {
        "episode": {
            "id": ep_id,
            "bgmMediaId": bgm_id,
            "subtitleMediaId": vtt_id,
            "subtitles": manifest["episode_subtitles"],
        }
    })
    for sh in manifest["shots"]:
        studio_json(opener, "PATCH", f"/api/studio/projects/{PROJECT_ID}", {
            "shot": {
                "id": sh["studioShotId"],
                "episodeId": ep_id,
                "bgmMediaId": bgm_id,
                "bgmOffset": sh["bgmOffset"],
                "subtitles": sh["subtitles"],
            }
        })
    print(f"[EP{ep_num}] Bound separated BGM ({bgm_id[:8]}) & WebVTT ({vtt_id[:8]}, {len(manifest['episode_subtitles'])} cues)!", flush=True)


def main():
    ep2_plan = json.loads((WORK_DIR / "ep02_plan.json").read_text(encoding="utf-8"))
    ep3_plan = json.loads((WORK_DIR / "ep03_plan.json").read_text(encoding="utf-8"))
    ep2_takes = WORK_DIR / "takes_ep02"
    ep3_takes = WORK_DIR / "takes_ep03"

    with ThreadPoolExecutor(max_workers=2) as bg_pool:
        fut_kf3210 = bg_pool.submit(fix_3210_keyframe)

        # Dispatch all 4 dedicated short 368p VO jobs sequentially on 4070 Ti SUPER in background!
        vo_futs = {}
        def run_all_4070_vos():
            res = {}
            for sp in ep2_plan:
                if "vo_short_spec" in sp:
                    res[sp["id"]] = gen_short_vo_4070(sp, ep2_takes)
            for sp in ep3_plan:
                if "vo_short_spec" in sp:
                    res[sp["id"]] = gen_short_vo_4070(sp, ep3_takes)
            return res

        # Submit individual futures chained on a single-worker 4070 executor so 5090 can await per-shot
        vo_pool = ThreadPoolExecutor(max_workers=1)
        for sp in ep2_plan:
            if "vo_short_spec" in sp:
                vo_futs[sp["id"]] = vo_pool.submit(gen_short_vo_4070, sp, ep2_takes)
        for sp in ep3_plan:
            if "vo_short_spec" in sp:
                vo_futs[sp["id"]] = vo_pool.submit(gen_short_vo_4070, sp, ep3_takes)

        # 1. Run Episode 2 on 5090 -> auto-merge -> separated BGM & subtitles
        run_episode_5090(ep2_plan, ep2_takes, vo_futs)
        upload_and_finalize_episode(2, EP2_ID, ep2_plan, ep2_takes, EP2_CUES, EP2_BGM)

        # Ensure 3-2-10 keyframe fix finished before Episode 3 runs
        fut_kf3210.result()

        # 2. Run Episode 3 on 5090 -> auto-merge -> separated BGM & subtitles
        run_episode_5090(ep3_plan, ep3_takes, vo_futs)
        upload_and_finalize_episode(3, EP3_ID, ep3_plan, ep3_takes, EP3_CUES, EP3_BGM)

        vo_pool.shutdown(wait=True)

    print("\nALL EPISODES 1-3 VIDEOS, AUTO-MERGED FILMS, AND SEPARATED BGM+SUBTITLES COMPLETE!", flush=True)


if __name__ == "__main__":
    main()
