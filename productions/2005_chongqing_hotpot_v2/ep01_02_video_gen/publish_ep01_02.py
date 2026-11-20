#!/usr/bin/env python3
"""
Upload all 21 audited 480p clean shot videos (Ep 1: 11 shots, Ep 2: 10 shots) to Director Workstation,
wait for automatic EpisodeFilmQueue merges to reach `completed`, compile separated BGM (.mp3) +
dual-layer subtitles (.vtt + JSON) via `post_bgm_subtitles.py`, and bind them to Episode 1 & Episode 2
while keeping all raw/merged MP4 streams 100% free of burned-in text or baked-in BGM.
"""
from __future__ import annotations
import json
import sys
import time
import urllib.parse
from pathlib import Path
import requests

SKILL_SCRIPTS = Path("/home/zhongwenyu/project/ai-director-train/.agents/skills/hit-video/scripts")
sys.path.insert(0, str(SKILL_SCRIPTS))
import post_bgm_subtitles  # noqa: E402

WORK_DIR = Path("/home/zhongwenyu/project/ai-director-train/productions/2005_chongqing_hotpot_v2/ep01_02_video_gen")
STUDIO_DIR = Path("/home/zhongwenyu/project/playlets-studio")
BASE_URL = "http://127.0.0.1:8765"
PID = "playlet-mwj57ecn-9658ad48"
EP1_ID = "ecec609a-31c3-407e-b368-1b598543bca8"
EP2_ID = "41d1dd8c-4172-4a26-b985-63fe17e96dce"


def login_session() -> requests.Session:
    pw = (STUDIO_DIR / "runtime/initial-password.txt").read_text(encoding="utf-8").strip()
    sess = requests.Session()
    r = sess.post(f"{BASE_URL}/api/login", json={"password": pw}, timeout=15)
    r.raise_for_status()
    return sess


def upload_media(sess: requests.Session, file_path: Path, name: str, target_id: str, mtype: str, mime: str) -> str:
    qs = urllib.parse.urlencode({"name": name, "targetId": target_id, "type": mtype})
    data = file_path.read_bytes()
    r = sess.post(
        f"{BASE_URL}/api/studio/projects/{PID}/upload?{qs}",
        data=data,
        headers={"Content-Type": mime},
        timeout=120,
    )
    r.raise_for_status()
    js = r.json()
    return js["id"] if "id" in js else js["media"][-1]["id"]


def build_ep1_post_spec(shot_map: dict) -> dict:
    t = WORK_DIR / "takes_ep01"
    return {
        "prefix": "ep01_v2",
        "bgm_segments": [
            {
                "label": "2020上市前夜雨巷背叛与车祸余波（低回悲鸣钢琴 CC0）",
                "file": "/home/zhongwenyu/project/audio-library/_files/freesound-807111.mp3",
                "start_shot": "1-1-01",
                "end_shot": "1-1-07",
                "end_delta": -0.4,
                "gain": 0.48,
                "fade_in": 0.8,
                "fade_out": 0.6,
            },
            {
                "label": "2005重生醒悟、反塞钢丝球护方退场（沉静复盘逆袭 Mixkit Free）",
                "file": "/home/zhongwenyu/project/audio-library/_files/mixkit-music-374.mp3",
                "start_shot": "1-2-01",
                "start_delta": 0.6,
                "end_shot": "1-2-16",
                "src_offset": 1.5,
                "gain": 0.44,
                "fade_in": 1.0,
                "fade_out": 1.0,
            },
            {
                "label": "沙正街黄昏立誓与重逢青梅（怀旧温暖吉他 CC0）",
                "file": "/home/zhongwenyu/project/audio-library/_files/freesound-845168.mp3",
                "start_shot": "1-3-01",
                "end_shot": "1-3-04",
                "end_delta": -3.0,
                "gain": 0.46,
                "fade_in": 0.8,
                "fade_out": 0.5,
            },
            {
                "label": "街尾夏氏小厨摔盘砸店突发危机卡点（深鼓悬疑渐强 Mixkit Free）",
                "file": "/home/zhongwenyu/project/audio-library/_files/mixkit-sfx-682.wav",
                "start_shot": "1-3-04",
                "start_delta": 9.0,
                "end_shot": "1-3-04",
                "align_end": True,
                "gain": 0.52,
                "fade_in": 0.4,
                "fade_out": 0.2,
            },
        ],
        "shots": [
            {
                "id": "1-1-01",
                "studioShotId": shot_map["1-1-01"]["shotId"],
                "video": str(t / "1-1-01/video.mp4"),
                "cues": [
                    {"start": 0.3, "end": 3.5, "kind": "caption", "speaker": "", "text": "2020年 · 林记集团上市敲钟前夜"},
                    {"start": 5.3, "end": 11.2, "kind": "dialogue", "speaker": "楚南", "text": "叶大厨，明天集团敲钟，里头全是投行贵客，你一身牛油味往里闯，给双双丢人？"},
                ],
            },
            {
                "id": "1-1-04",
                "studioShotId": shot_map["1-1-04"]["shotId"],
                "video": str(t / "1-1-04/video.mp4"),
                "cues": [
                    {"start": 0.3, "end": 5.9, "kind": "dialogue", "speaker": "叶寻", "text": "林双双！十五年，我拿爷爷的火锅方子把林记熬到上市，过河就拆桥？！"},
                    {"start": 6.6, "end": 13.9, "kind": "dialogue", "speaker": "林双双", "text": "方子是你当年上赶着献的！没楚南留洋回来做资本包装，你熬土火锅也配敲钟？遣散费打你卡上了！"},
                ],
            },
            {
                "id": "1-1-07",
                "studioShotId": shot_map["1-1-07"]["shotId"],
                "video": str(t / "1-1-07/video.mp4"),
                "cues": [],
            },
            {
                "id": "1-2-01",
                "studioShotId": shot_map["1-2-01"]["shotId"],
                "video": str(t / "1-2-01/video.mp4"),
                "cues": [
                    {"start": 0.2, "end": 3.8, "kind": "caption", "speaker": "", "text": "2005年9月10日 周六傍晚 · 重庆大学外沙正街"},
                    {"start": 2.4, "end": 9.5, "kind": "vo", "speaker": "叶寻", "text": "2005年9月10号？大三刚开学……爷爷的清润火锅方子，还没交出去！"},
                ],
            },
            {
                "id": "1-2-04",
                "studioShotId": shot_map["1-2-04"]["shotId"],
                "video": str(t / "1-2-04/video.mp4"),
                "cues": [
                    {"start": 2.3, "end": 11.2, "kind": "dialogue", "speaker": "林双双", "text": "睡迷糊了？到饭点半桌客人都没有，馆子连亏三个月就剩四万块。你昨天说拿你家土火锅救店，算了吧。"},
                ],
            },
            {
                "id": "1-2-07",
                "studioShotId": shot_map["1-2-07"]["shotId"],
                "video": str(t / "1-2-07/video.mp4"),
                "cues": [
                    {"start": 0.2, "end": 6.7, "kind": "dialogue", "speaker": "楚南", "text": "老叶，外语系女生约会谁吃油烟土火锅？拿两万五铺白桌布改法式西餐厅，剩一万五搞开业促销！"},
                    {"start": 7.0, "end": 8.5, "kind": "dialogue", "speaker": "林双双", "text": "那主厨呢？"},
                    {"start": 8.7, "end": 14.2, "kind": "dialogue", "speaker": "楚南", "text": "我表哥赵帆在深圳大酒店当西餐副厨，我替你请好了，牛排五十八一份！"},
                ],
            },
            {
                "id": "1-2-10",
                "studioShotId": shot_map["1-2-10"]["shotId"],
                "video": str(t / "1-2-10/video.mp4"),
                "cues": [
                    {"start": 0.2, "end": 6.3, "kind": "dialogue", "speaker": "林双双", "text": "还是楚南见过世面！明天停业收拾，叶寻，你留下把后厨油灶刷干净打个杂。"},
                    {"start": 6.9, "end": 11.2, "kind": "dialogue", "speaker": "楚南", "text": "接着吧叶大厨，灶刷亮堂点，等我表哥到了赏你口罗宋汤。"},
                ],
            },
            {
                "id": "1-2-13",
                "studioShotId": shot_map["1-2-13"]["shotId"],
                "video": str(t / "1-2-13/video.mp4"),
                "cues": [
                    {"start": 2.3, "end": 9.5, "kind": "dialogue", "speaker": "叶寻", "text": "五十八的牛排配你们正好。方子收回，油灶你们自己刷。林双双，咱俩到此为止。"},
                ],
            },
            {
                "id": "1-2-16",
                "studioShotId": shot_map["1-2-16"]["shotId"],
                "video": str(t / "1-2-16/video.mp4"),
                "cues": [
                    {"start": 1.2, "end": 6.4, "kind": "dialogue", "speaker": "楚南", "text": "装什么硬气！掏不出三千块的穷学生，离了双双家店面，攥个破方子去哪儿开锅？"},
                    {"start": 6.8, "end": 10.9, "kind": "dialogue", "speaker": "林双双", "text": "叶寻！出了这道门，明天求我也别想再进我家后厨！"},
                ],
            },
            {
                "id": "1-3-01",
                "studioShotId": shot_map["1-3-01"]["shotId"],
                "video": str(t / "1-3-01/video.mp4"),
                "cues": [
                    {"start": 1.6, "end": 8.0, "kind": "vo", "speaker": "叶寻", "text": "两千八暑期工存款，哪怕摆摊，这一世绝不再给白眼狼熬一滴油！"},
                ],
            },
            {
                "id": "1-3-04",
                "studioShotId": shot_map["1-3-04"]["shotId"],
                "video": str(t / "1-3-04/video.mp4"),
                "cues": [
                    {"start": 0.3, "end": 4.6, "kind": "dialogue", "speaker": "夏芊芊", "text": "小寻？上晚市了不在街中段林家帮忙，怎么往街尾跑？"},
                    {"start": 5.0, "end": 8.8, "kind": "vo", "speaker": "叶寻", "text": "青梅夏芊芊，前世只有她劝我提防楚南！"},
                    {"start": 9.8, "end": 12.1, "kind": "dialogue", "speaker": "叶寻", "text": "芊芊姐，夏叔出什么事了？"},
                ],
            },
        ],
    }


def build_ep2_post_spec(shot_map: dict) -> dict:
    t = WORK_DIR / "takes_ep02"
    return {
        "prefix": "ep02_v2",
        "bgm_segments": [
            {
                "label": "恶厨老王趁伤勒索与叶寻跨门立军令状（沉静紧迫博弈 Mixkit Free）",
                "file": "/home/zhongwenyu/project/audio-library/_files/mixkit-music-374.mp3",
                "start_shot": "2-1-01",
                "end_shot": "2-1-07",
                "gain": 0.42,
                "fade_in": 0.8,
                "fade_out": 0.8,
            },
            {
                "label": "爷爷旧刀猛火颠勺爆炒猪肝鸭杂满堂喝彩（温暖燃情爽点 Mixkit Free）",
                "file": "/home/zhongwenyu/project/audio-library/_files/mixkit-music-350.mp3",
                "start_shot": "2-2-01",
                "end_shot": "2-2-10",
                "src_offset": 14.0,
                "gain": 0.45,
                "fade_in": 0.9,
                "fade_out": 0.8,
            },
            {
                "label": "深夜算账房租缺口与拍存折合伙（怀旧温情铺垫 CC0）",
                "file": "/home/zhongwenyu/project/audio-library/_files/freesound-845168.mp3",
                "start_shot": "2-3-01",
                "end_shot": "2-3-04",
                "gain": 0.40,
                "fade_in": 0.8,
                "fade_out": 0.6,
            },
            {
                "label": "夏芊芊按住账本直击灵魂质问悬念卡点（深鼓悬疑渐强 Mixkit Free）",
                "file": "/home/zhongwenyu/project/audio-library/_files/mixkit-sfx-682.wav",
                "start_shot": "2-3-07",
                "start_delta": 0.8,
                "end_shot": "2-3-07",
                "align_end": True,
                "gain": 0.50,
                "fade_in": 0.8,
                "fade_out": 0.25,
            },
        ],
        "shots": [
            {
                "id": "2-1-01",
                "studioShotId": shot_map["2-1-01"]["shotId"],
                "video": str(t / "2-1-01/video.mp4"),
                "cues": [
                    {"start": 0.3, "end": 7.6, "kind": "dialogue", "speaker": "老王", "text": "老夏，少打感情牌！你五天前颠勺拉裂手腕筋，现在晚市三桌单子都下了，不签三千块长约、预支九千块，老子立马走人！"},
                    {"start": 7.9, "end": 13.4, "kind": "dialogue", "speaker": "夏建国", "text": "老王！上周说好六十块一天顶班，你趁上客坐地起价，让我上哪儿掏九千块？！"},
                ],
            },
            {
                "id": "2-1-04",
                "studioShotId": shot_map["2-1-04"]["shotId"],
                "video": str(t / "2-1-04/video.mp4"),
                "cues": [
                    {"start": 0.2, "end": 2.9, "kind": "dialogue", "speaker": "夏芊芊", "text": "王师傅，菜都点好了你趁火打劫——"},
                    {"start": 3.0, "end": 7.3, "kind": "dialogue", "speaker": "老王", "text": "没钱就贴红纸关门！各位街坊趁早换别家吃吧，老夏家今晚断灶了！"},
                    {"start": 7.5, "end": 11.9, "kind": "dialogue", "speaker": "中年食客", "text": "老夏，我们专门来捧场，没厨子你早说嘛，饿着肚子干等也不是事啊。"},
                ],
            },
            {
                "id": "2-1-07",
                "studioShotId": shot_map["2-1-07"]["shotId"],
                "video": str(t / "2-1-07/video.mp4"),
                "cues": [
                    {"start": 0.2, "end": 4.7, "kind": "dialogue", "speaker": "叶寻", "text": "叔，坐下喝口茶。十分钟热菜不上桌，今晚三桌全免单，算我的！"},
                    {"start": 4.8, "end": 6.6, "kind": "dialogue", "speaker": "夏建国", "text": "寻娃子？你怎么过来了！"},
                    {"start": 6.8, "end": 10.4, "kind": "dialogue", "speaker": "老王", "text": "案板上就剩副腥猪肝和鸭杂，你个穷学生拿嘴炒啊？"},
                    {"start": 10.6, "end": 13.5, "kind": "dialogue", "speaker": "叶寻", "text": "芊芊姐，结他六十块日工钱，请他腾地方。"},
                ],
            },
            {
                "id": "2-2-01",
                "studioShotId": shot_map["2-2-01"]["shotId"],
                "video": str(t / "2-2-01/video.mp4"),
                "cues": [
                    {"start": 0.7, "end": 6.4, "kind": "dialogue", "speaker": "夏建国", "text": "十年前你爷爷教我吊高汤留下的刀。叔这一伤老客跑了一半，撑不过这个月了……"},
                    {"start": 6.6, "end": 9.3, "kind": "dialogue", "speaker": "叶寻", "text": "夏叔，有我在，这口灶凉不了。"},
                ],
            },
            {
                "id": "2-2-04",
                "studioShotId": shot_map["2-2-04"]["shotId"],
                "video": str(t / "2-2-04/video.mp4"),
                "cues": [],
            },
            {
                "id": "2-2-07",
                "studioShotId": shot_map["2-2-07"]["shotId"],
                "video": str(t / "2-2-07/video.mp4"),
                "cues": [
                    {"start": 5.8, "end": 11.2, "kind": "dialogue", "speaker": "中年食客", "text": "半点血腥气没有，又滑又脆！老夏，这小伙子手艺比姓王的强出两条街！"},
                ],
            },
            {
                "id": "2-2-10",
                "studioShotId": shot_map["2-2-10"]["shotId"],
                "video": str(t / "2-2-10/video.mp4"),
                "cues": [
                    {"start": 0.3, "end": 4.9, "kind": "dialogue", "speaker": "邻桌食客", "text": "老夏，我们也加份泡椒猪肝和爆鸭杂，再拿四瓶啤酒！"},
                    {"start": 5.4, "end": 8.3, "kind": "dialogue", "speaker": "夏建国", "text": "王师傅，好走不送！"},
                ],
            },
            {
                "id": "2-3-01",
                "studioShotId": shot_map["2-3-01"]["shotId"],
                "video": str(t / "2-3-01/video.mp4"),
                "cues": [
                    {"start": 1.2, "end": 11.9, "kind": "dialogue", "speaker": "夏芊芊", "text": "今晚净落一百一十块，可账上总共只剩六千二。十月一号要交下季度房租一万八，还差一万一千八……剩二十天靠小炒怎么也填不上。"},
                ],
            },
            {
                "id": "2-3-04",
                "studioShotId": shot_map["2-3-04"]["shotId"],
                "video": str(t / "2-3-04/video.mp4"),
                "cues": [
                    {"start": 0.25, "end": 4.2, "kind": "vo", "speaker": "叶寻", "text": "百平临街熟铺证照齐全，缺的只是高毛利爆品！"},
                    {"start": 4.7, "end": 12.3, "kind": "dialogue", "speaker": "叶寻", "text": "夏叔，芊芊姐，小炒翻不了身。我拿全部存款和爷爷传下的清润火锅方子入伙，咱们改开老火锅，二十天挣出房租！"},
                ],
            },
            {
                "id": "2-3-07",
                "studioShotId": shot_map["2-3-07"]["shotId"],
                "video": str(t / "2-3-07/video.mp4"),
                "cues": [
                    {"start": 0.2, "end": 13.3, "kind": "dialogue", "speaker": "夏芊芊", "text": "叶寻，林双双家馆子就在前头一百米，整条街谁不知道你对她百依百顺了两年？你今晚突然拿存折来我家开火锅，到底是真心合伙，还是跟她赌气、拿我爸最后的救命钱当筏子？"},
                ],
            },
        ],
    }


def main():
    sess = login_session()
    shot_map = json.loads((WORK_DIR / "shot_uuid_map.json").read_text(encoding="utf-8"))

    # 1. Upload all 21 clean shot MP4s and PATCH shot.videoId (triggers instant auto-merge!)
    for ep_num, takes_dir, plan_name in [(1, WORK_DIR / "takes_ep01", "ep01_v2_plan.json"), (2, WORK_DIR / "takes_ep02", "ep02_v2_plan.json")]:
        plan = json.loads((WORK_DIR / plan_name).read_text(encoding="utf-8"))
        for sp in plan:
            sid = sp["id"]
            kf_png = WORK_DIR / f"keyframes_2k/{sid}.png"
            mp4 = takes_dir / sid / "video.mp4"
            info = shot_map[sid]
            img_id = upload_media(sess, kf_png, f"{sid}_v2_2k.png", info["shotId"], "image", "image/png")
            vid_id = upload_media(sess, mp4, f"{sid}_v2_480p.mp4", info["shotId"], "video", "video/mp4")
            dur_int = max(5, min(15, int(round(post_bgm_subtitles.probe_duration(mp4)))))
            r = sess.patch(
                f"{BASE_URL}/api/studio/projects/{PID}",
                json={"shot": {"episodeId": info["episodeId"], "id": info["shotId"], "duration": dur_int, "imageId": img_id, "videoId": vid_id, "confirmedImage": True, "confirmedVideo": True}},
                timeout=30,
            )
            r.raise_for_status()
            print(f"[upload] Ep{ep_num} {sid} -> videoId={vid_id}", flush=True)

    # 2. Compile separated BGM + WebVTT/JSON subtitles & bind to Workstation
    for ep_id, label, spec in [
        (EP1_ID, "ep01_v2", build_ep1_post_spec(shot_map)),
        (EP2_ID, "ep02_v2", build_ep2_post_spec(shot_map)),
    ]:
        pdir = WORK_DIR / f"post_{label}"
        pdir.mkdir(parents=True, exist_ok=True)
        spec_file = pdir / f"{label}_spec.json"
        spec_file.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest = post_bgm_subtitles.compile_post_pack(spec_file, pdir)

        bgm_id = upload_media(sess, Path(manifest["bgm_file"]), f"{label}_bgm.mp3", ep_id, "audio", "audio/mpeg")
        vtt_id = upload_media(sess, Path(manifest["vtt_file"]), f"{label}_subtitles.vtt", ep_id, "subtitle", "text/vtt")

        # Bind on episode
        r = sess.patch(
            f"{BASE_URL}/api/studio/projects/{PID}",
            json={"episode": {"id": ep_id, "bgmMediaId": bgm_id, "subtitleMediaId": vtt_id, "subtitles": manifest["episode_subtitles"]}},
            timeout=30,
        )
        r.raise_for_status()

        # Bind bgmMediaId, bgmOffset, subtitles on each shot
        for sh in manifest["shots"]:
            r2 = sess.patch(
                f"{BASE_URL}/api/studio/projects/{PID}",
                json={"shot": {"episodeId": ep_id, "id": sh["studioShotId"], "bgmMediaId": bgm_id, "bgmOffset": sh["bgmOffset"], "subtitles": sh["subtitles"]}},
                timeout=30,
            )
            r2.raise_for_status()
        print(f"[post] Bound {label}: bgmMediaId={bgm_id}, subtitleMediaId={vtt_id}, total={manifest['total_duration']}s", flush=True)

    # 3. Wait for automatic EpisodeFilmQueue merges to complete & verify HTTP 200
    for ep_id, name in [(EP1_ID, "Episode 1"), (EP2_ID, "Episode 2")]:
        sess.post(f"{BASE_URL}/api/studio/projects/{PID}/episodes/{ep_id}/video", json={}, timeout=30)
        for _ in range(45):
            st = sess.get(f"{BASE_URL}/api/studio/projects/{PID}/episodes/{ep_id}/video", timeout=15).json()
            mid = st.get("mediaId") or (st.get("media") or {}).get("id")
            if st.get("status") == "completed" and mid:
                head = sess.head(f"{BASE_URL}/api/studio/media/{mid}", timeout=15)
                print(f"[merged] {name} film READY -> mediaId={mid} (HTTP {head.status_code}), shots={st.get('completedShots')}", flush=True)
                break
            time.sleep(2)
        else:
            raise RuntimeError(f"{name} film merge did not complete in time: {st}")


if __name__ == "__main__":
    main()
