#!/usr/bin/env python3
"""
Reset old v2 Ep 1 & Ep 2 storyboards on Director Workstation project playlet-mwj57ecn-9658ad48,
sync hotpot_v3 outline & Ep 1-3 scripts, create the 18 new shots (9 Ep 1 + 9 Ep 2),
upload all 18 audited 2K keyframes & 480p clean shot videos, compile separated BGM (.mp3) +
dual-layer WebVTT/JSON subtitles via post_bgm_subtitles.py, bind them cleanly, and verify
automatic EpisodeFilmQueue merges + HTTP 200 media availability.
"""
from __future__ import annotations
import argparse
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path
import requests

SKILL_SCRIPTS = Path("/home/zhongwenyu/project/ai-director-train/.agents/skills/hit-video/scripts")
sys.path.insert(0, str(SKILL_SCRIPTS))
import post_bgm_subtitles  # noqa: E402

PROD_DIR = Path("/home/zhongwenyu/project/ai-director-train/productions/2005_chongqing_hotpot_v3")
WORK_DIR = PROD_DIR / "ep01_02_video_gen"
STUDIO_DIR = Path("/home/zhongwenyu/project/playlets-studio")
BASE_URL = "http://127.0.0.1:8765"
PID = "playlet-mwj57ecn-9658ad48"
EP1_ID = "ecec609a-31c3-407e-b368-1b598543bca8"
EP2_ID = "41d1dd8c-4172-4a26-b985-63fe17e96dce"
EP3_ID = "ed05ad9d-55c2-4a89-a8af-4d88d640ed07"


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


def sync_outline_names(raw_outline: str) -> str:
    rep = [
        ("陈野哥", "叶寻"),
        ("陈野", "叶寻"),
        ("陈满仓", "叶满仓"),
        ("陈伯伯", "叶爷爷"),
        ("陈记红汤", "叶记红汤"),
        ("陈氏", "叶氏"),
        ("老陈家", "老叶家"),
        ("陈苏老火锅", "叶夏老火锅"),
        ("苏晚", "夏芊芊"),
        ("苏记老火锅", "夏记老火锅"),
        ("苏记", "夏记"),
        ("林薇", "林双双"),
        ("林大富", "林有才"),
        ("赵凯", "楚南"),
        ("赵德全", "楚德全"),
        ("凯旋火锅", "楚氏火锅"),
        ("凯旋餐饮", "楚氏餐饮"),
        ("凯旋集团", "楚氏集团"),
        ("凯旋", "楚氏"),
        ("凯源干货", "楚源干货"),
        ("赵家", "楚家"),
        ("林赵两家", "林楚两家"),
        ("姓赵", "姓楚"),
        ("百桌坝坝席", "十二桌庆功席"),
        ("百桌定金", "十二桌定金"),
        ("百桌席", "十二桌席"),
        ("百桌", "十二桌"),
    ]
    out = raw_outline
    for k, v in rep:
        out = out.replace(k, v)
    return out


def split_episodes(md_text: str) -> dict[int, tuple[str, str]]:
    parts = re.split(r"(?m)^#\s*第(\d+)集\s+([^\n]+)\n", md_text)
    res = {}
    for i in range(1, len(parts), 3):
        ep_no = int(parts[i])
        title = parts[i + 1].strip()
        body = f"# 第{ep_no}集　{title}\n" + parts[i + 2].strip() + "\n"
        res[ep_no] = (f"第{ep_no}集：{title}", body)
    return res


def reset_and_create_shots(sess: requests.Session) -> dict:
    # 1. Sync outline + script + Ep 1-3 text
    raw_outline = (PROD_DIR / "01_outline.md").read_text(encoding="utf-8")
    clean_outline = sync_outline_names(raw_outline)
    (PROD_DIR / "01_outline_studio.md").write_text(clean_outline, encoding="utf-8")

    ep_md = (PROD_DIR / "episodes/ep001-003.md").read_text(encoding="utf-8")
    ep_map = split_episodes(ep_md)

    r = sess.patch(
        f"{BASE_URL}/api/studio/projects/{PID}",
        json={"outline": clean_outline, "script": ep_md, "aspectRatio": "9:16"},
        timeout=30,
    )
    r.raise_for_status()

    for ep_no, ep_id in [(1, EP1_ID), (2, EP2_ID), (3, EP3_ID)]:
        title, body = ep_map[ep_no]
        r = sess.patch(
            f"{BASE_URL}/api/studio/projects/{PID}",
            json={"episode": {"id": ep_id, "title": title, "script": body, "aspectRatio": "9:16"}},
            timeout=30,
        )
        r.raise_for_status()

    # 2. Clear existing Ep 1 & Ep 2 shots cleanly (unlink imageId/videoId first so DELETE storyboard succeeds)
    proj = sess.get(f"{BASE_URL}/api/studio/projects/{PID}", timeout=30).json()
    for ep in proj.get("episodes", []):
        if ep["id"] not in (EP1_ID, EP2_ID):
            continue
        for sh in ep.get("shots", []):
            if sh.get("imageId") or sh.get("videoId"):
                sess.patch(
                    f"{BASE_URL}/api/studio/projects/{PID}",
                    json={"shot": {"episodeId": ep["id"], "id": sh["id"], "imageId": "", "videoId": "", "confirmedImage": False, "confirmedVideo": False}},
                    timeout=30,
                ).raise_for_status()
        if ep.get("shots"):
            sess.delete(f"{BASE_URL}/api/studio/projects/{PID}/episodes/{ep['id']}/storyboard", timeout=30).raise_for_status()

    # 3. Create 9 Ep 1 shots + 9 Ep 2 shots and upload 2K keyframes
    shot_map = {}
    for ep_id, plan_name in [(EP1_ID, "ep01_v3_plan.json"), (EP2_ID, "ep02_v3_plan.json")]:
        plan = json.loads((WORK_DIR / plan_name).read_text(encoding="utf-8"))
        for sp in plan:
            sid = sp["id"]
            r = sess.post(f"{BASE_URL}/api/studio/projects/{PID}/shots", json={"episodeId": ep_id}, timeout=30)
            r.raise_for_status()
            created = r.json()
            # Find newly created shot ID
            if "shot" in created and isinstance(created["shot"], dict):
                sh_id = created["shot"]["id"]
            elif "id" in created and "episodes" not in created:
                sh_id = created["id"]
            else:
                ep_obj = next(e for e in created["episodes"] if e["id"] == ep_id)
                sh_id = ep_obj["shots"][-1]["id"]

            kf_png = WORK_DIR / f"keyframes_2k/{sid}.png"
            img_id = upload_media(sess, kf_png, f"{sid}_v3_2k.png", sh_id, "image", "image/png")
            sess.patch(
                f"{BASE_URL}/api/studio/projects/{PID}",
                json={
                    "shot": {
                        "episodeId": ep_id,
                        "id": sh_id,
                        "description": f"[{sid}] {sp['description']}",
                        "dialogue": sp["dialogue"],
                        "videoPrompt": sp["prompt"],
                        "duration": int(sp["duration"]),
                        "assetNames": sp["assetNames"],
                        "imageId": img_id,
                        "confirmedImage": True,
                    }
                },
                timeout=30,
            ).raise_for_status()
            shot_map[sid] = {"episodeId": ep_id, "shotId": sh_id, "imageId": img_id}
            print(f"[shot-init] {sid} -> shotId={sh_id}, imageId={img_id}", flush=True)

    (WORK_DIR / "shot_uuid_map.json").write_text(json.dumps(shot_map, ensure_ascii=False, indent=2), encoding="utf-8")
    return shot_map


def build_ep1_post_spec(shot_map: dict) -> dict:
    t = WORK_DIR / "takes_ep01"
    return {
        "prefix": "ep01_v3",
        "bgm_segments": [
            {
                "label": "庆功宴逼交秘方与撕方拍48张汇款单撤火反击（沉静紧迫逆袭 Mixkit Free）",
                "file": "/home/zhongwenyu/project/audio-library/_files/mixkit-music-374.mp3",
                "start_shot": "1-1-01",
                "end_shot": "1-1-05",
                "gain": 0.42,
                "fade_in": 0.8,
                "fade_out": 0.8,
            },
            {
                "label": "跨街入伙夏记立五五契书摁红手印（温暖烟火同盟 CC0）",
                "file": "/home/zhongwenyu/project/audio-library/_files/freesound-845168.mp3",
                "start_shot": "1-2-01",
                "end_shot": "1-2-02",
                "gain": 0.42,
                "fade_in": 0.8,
                "fade_out": 0.7,
            },
            {
                "label": "反派堵门断油抢席与连夜蹬三轮抢鲜牛板油（燃情破局出发 Mixkit Free）",
                "file": "/home/zhongwenyu/project/audio-library/_files/mixkit-music-350.mp3",
                "start_shot": "1-2-03",
                "end_shot": "1-2-04",
                "src_offset": 12.0,
                "gain": 0.44,
                "fade_in": 0.8,
                "fade_out": 0.6,
            },
        ],
        "shots": [
            {
                "id": "1-1-01",
                "studioShotId": shot_map["1-1-01"]["shotId"],
                "video": str(t / "1-1-01/video.mp4"),
                "cues": [
                    {"start": 0.2, "end": 3.0, "kind": "caption", "speaker": "", "text": "2005年夏 · 重庆老街 林记火锅"},
                    {"start": 3.0, "end": 7.6, "kind": "dialogue", "speaker": "林双双", "text": "把你叶家清润汤剩下几味草本补全，咱俩婚约算完了。"},
                ],
            },
            {
                "id": "1-1-02",
                "studioShotId": shot_map["1-1-02"]["shotId"],
                "video": str(t / "1-1-02/video.mp4"),
                "cues": [
                    {"start": 0.25, "end": 5.4, "kind": "vo", "speaker": "叶寻", "text": "重回2005年？前世我交出祖传秘方，反被他们榨干赶出老街！"},
                    {"start": 7.1, "end": 11.4, "kind": "dialogue", "speaker": "楚南", "text": "双双马上进我楚氏餐饮当主管，能嫁你个满身牛油味的伙夫？"},
                ],
            },
            {
                "id": "1-1-03",
                "studioShotId": shot_map["1-1-03"]["shotId"],
                "video": str(t / "1-1-03/video.mp4"),
                "cues": [
                    {"start": 0.1, "end": 4.0, "kind": "dialogue", "speaker": "林有才", "text": "白吃我家四年，留张方子抵恩，是你的本分！"},
                    {"start": 10.2, "end": 13.3, "kind": "dialogue", "speaker": "林双双", "text": "叶寻你疯了！敢撕我家的方子？"},
                ],
            },
            {
                "id": "1-1-04",
                "studioShotId": shot_map["1-1-04"]["shotId"],
                "video": str(t / "1-1-04/video.mp4"),
                "cues": [
                    {"start": 0.3, "end": 4.2, "kind": "caption", "speaker": "", "text": "邮政汇款存根（共48张 · 四年大学学费生活费）"},
                    {"start": 4.5, "end": 9.1, "kind": "dialogue", "speaker": "叶寻", "text": "我辍学熬四年牛油，四十八张汇款单供你读完大学，两清了！"},
                ],
            },
            {
                "id": "1-1-05",
                "studioShotId": shot_map["1-1-05"]["shotId"],
                "video": str(t / "1-1-05/video.mp4"),
                "cues": [
                    {"start": 1.0, "end": 4.3, "kind": "dialogue", "speaker": "叶寻", "text": "今晚起火我撤了，看你们拿什么端上桌！"},
                    {"start": 4.5, "end": 8.2, "kind": "dialogue", "speaker": "林有才", "text": "忘恩负义的东西！离了林记，这条街谁敢要你？"},
                ],
            },
            {
                "id": "1-2-01",
                "studioShotId": shot_map["1-2-01"]["shotId"],
                "video": str(t / "1-2-01/video.mp4"),
                "cues": [
                    {"start": 0.25, "end": 5.4, "kind": "vo", "speaker": "叶寻", "text": "前世只有世交芊芊护我到底，这辈子换我撑起夏记！"},
                    {"start": 7.6, "end": 12.9, "kind": "dialogue", "speaker": "夏芊芊", "text": "叶爷爷熬汤真传我从小看着！林家瞎了眼，夏记迎你掌勺！"},
                ],
            },
            {
                "id": "1-2-02",
                "studioShotId": shot_map["1-2-02"]["shotId"],
                "video": str(t / "1-2-02/video.mp4"),
                "cues": [
                    {"start": 0.3, "end": 3.8, "kind": "caption", "speaker": "", "text": "合营契书：叶夏合营 · 五五分账"},
                    {"start": 4.6, "end": 8.6, "kind": "dialogue", "speaker": "夏芊芊", "text": "五五分账，往后咱俩一口锅里搅马勺！"},
                ],
            },
            {
                "id": "1-2-03",
                "studioShotId": shot_map["1-2-03"]["shotId"],
                "video": str(t / "1-2-03/video.mp4"),
                "cues": [
                    {"start": 0.5, "end": 6.2, "kind": "dialogue", "speaker": "楚南", "text": "夏芊芊，敢收他？明早断你夏记全部成品牛油，看你拿什么交房租！"},
                    {"start": 9.3, "end": 13.6, "kind": "dialogue", "speaker": "林双双", "text": "你们备好菜的机械厂十二桌席，周厂长刚改签给林记了！"},
                ],
            },
            {
                "id": "1-2-04",
                "studioShotId": shot_map["1-2-04"]["shotId"],
                "video": str(t / "1-2-04/video.mp4"),
                "cues": [
                    {"start": 0.1, "end": 3.3, "kind": "dialogue", "speaker": "夏芊芊", "text": "成品牛油全断了，明早拿什么开火？"},
                    {"start": 3.6, "end": 7.9, "kind": "dialogue", "speaker": "叶寻", "text": "不用陈年老油！坐稳，去屠宰场抢今晚头刀鲜牛板油！"},
                    {"start": 8.1, "end": 9.9, "kind": "dialogue", "speaker": "夏芊芊", "text": "走！我跟你去！"},
                ],
            },
        ],
    }


def build_ep2_post_spec(shot_map: dict) -> dict:
    t = WORK_DIR / "takes_ep02"
    return {
        "prefix": "ep02_v3",
        "bgm_segments": [
            {
                "label": "清晨现炼头刀鲜牛板油 vs 对门干炸焦苦废汤（紧凑烟火博弈 Mixkit Free）",
                "file": "/home/zhongwenyu/project/audio-library/_files/mixkit-music-374.mp3",
                "start_shot": "2-1-01",
                "end_shot": "2-2-01",
                "gain": 0.40,
                "fade_in": 0.8,
                "fade_out": 0.8,
            },
            {
                "label": "当街端出清润红汤试吃惊艳、十二桌工友满席过街（燃爽逆袭高潮 Mixkit Free）",
                "file": "/home/zhongwenyu/project/audio-library/_files/mixkit-music-350.mp3",
                "start_shot": "2-2-02",
                "end_shot": "2-2-04",
                "src_offset": 14.0,
                "gain": 0.45,
                "fade_in": 0.8,
                "fade_out": 0.8,
            },
            {
                "label": "恶意实名举报违禁药壳封样快检与叶寻从容关火迎战（悬疑钩子卡点 Mixkit Free）",
                "file": "/home/zhongwenyu/project/audio-library/_files/mixkit-sfx-682.wav",
                "start_shot": "2-2-05",
                "start_delta": 4.5,
                "end_shot": "2-2-06",
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
                    {"start": 0.3, "end": 4.2, "kind": "caption", "speaker": "", "text": "次日清晨 · 距机械厂十二桌开席还有五小时"},
                ],
            },
            {
                "id": "2-1-02",
                "studioShotId": shot_map["2-1-02"]["shotId"],
                "video": str(t / "2-1-02/video.mp4"),
                "cues": [
                    {"start": 1.7, "end": 4.8, "kind": "dialogue", "speaker": "林双双", "text": "爸，工友们快入席了，这油味怎么发苦？"},
                    {"start": 6.8, "end": 11.5, "kind": "dialogue", "speaker": "林有才", "text": "我偷瞄过十来回，药材下油锅炸准没错！多搁两勺糖压压！"},
                ],
            },
            {
                "id": "2-1-03",
                "studioShotId": shot_map["2-1-03"]["shotId"],
                "video": str(t / "2-1-03/video.mp4"),
                "cues": [
                    {"start": 0.25, "end": 5.4, "kind": "vo", "speaker": "叶寻", "text": "干药材下高温老油必炸成苦炭。林有才，这十二桌席你咽不下去。"},
                    {"start": 8.6, "end": 13.3, "kind": "dialogue", "speaker": "夏芊芊", "text": "太香了！鲜毛肚和配菜全冰镇备齐，随时开席！"},
                ],
            },
            {
                "id": "2-2-01",
                "studioShotId": shot_map["2-2-01"]["shotId"],
                "video": str(t / "2-2-01/video.mp4"),
                "cues": [
                    {"start": 6.1, "end": 11.3, "kind": "dialogue", "speaker": "周有福", "text": "林老板，又焦又苦还呛嗓子，这就是你吹的清润红汤？"},
                ],
            },
            {
                "id": "2-2-02",
                "studioShotId": shot_map["2-2-02"]["shotId"],
                "video": str(t / "2-2-02/video.mp4"),
                "cues": [
                    {"start": 0.2, "end": 4.8, "kind": "dialogue", "speaker": "林双双", "text": "周厂长，草本入汤难免带苦，喝口酸梅汤压压就顺了！"},
                    {"start": 10.1, "end": 13.5, "kind": "dialogue", "speaker": "夏芊芊", "text": "正宗清润红汤，可不用酸梅汤硬压！"},
                ],
            },
            {
                "id": "2-2-03",
                "studioShotId": shot_map["2-2-03"]["shotId"],
                "video": str(t / "2-2-03/video.mp4"),
                "cues": [
                    {"start": 0.1, "end": 4.2, "kind": "dialogue", "speaker": "林有才", "text": "别信！夏记连牛油都被断了，拿什么接十二桌大席？"},
                    {"start": 4.6, "end": 9.6, "kind": "dialogue", "speaker": "叶寻", "text": "我用头刀鲜板油现熬。林记前四年的招牌汤，本就是我炒的。"},
                    {"start": 10.1, "end": 14.8, "kind": "dialogue", "speaker": "夏芊芊", "text": "桌灶鲜菜早备齐了！周厂长尝一口，有一丝苦味分文不收！"},
                ],
            },
            {
                "id": "2-2-04",
                "studioShotId": shot_map["2-2-04"]["shotId"],
                "video": str(t / "2-2-04/video.mp4"),
                "cues": [
                    {"start": 4.8, "end": 8.8, "kind": "dialogue", "speaker": "周有福", "text": "醇香生津，脆嫩化渣！这才是真手艺！"},
                    {"start": 9.9, "end": 13.3, "kind": "dialogue", "speaker": "周有福", "text": "林记退单！工友们，过街坐夏记！"},
                ],
            },
            {
                "id": "2-2-05",
                "studioShotId": shot_map["2-2-05"]["shotId"],
                "video": str(t / "2-2-05/video.mp4"),
                "cues": [
                    {"start": 0.1, "end": 4.6, "kind": "dialogue", "speaker": "林双双", "text": "陈科长！我实名举报夏记往汤里偷加违禁药壳提香！"},
                    {"start": 5.0, "end": 9.1, "kind": "dialogue", "speaker": "陈科长", "text": "接到实名举报，请立刻熄火封样，配合现场快检！"},
                ],
            },
            {
                "id": "2-2-06",
                "studioShotId": shot_map["2-2-06"]["shotId"],
                "video": str(t / "2-2-06/video.mp4"),
                "cues": [
                    {"start": 0.1, "end": 5.9, "kind": "dialogue", "speaker": "楚南", "text": "吃着黑心锅还不跑？楚氏总店刚送来招牌红汤，对门全场免单！"},
                ],
            },
        ],
    }


def upload_videos_and_post(sess: requests.Session, shot_map: dict):
    for ep_num, takes_dir, plan_name in [(1, WORK_DIR / "takes_ep01", "ep01_v3_plan.json"), (2, WORK_DIR / "takes_ep02", "ep02_v3_plan.json")]:
        plan = json.loads((WORK_DIR / plan_name).read_text(encoding="utf-8"))
        for sp in plan:
            sid = sp["id"]
            mp4 = takes_dir / sid / "video.mp4"
            info = shot_map[sid]
            vid_id = upload_media(sess, mp4, f"{sid}_v3_480p.mp4", info["shotId"], "video", "video/mp4")
            dur_int = max(5, min(15, int(round(post_bgm_subtitles.probe_duration(mp4)))))
            sess.patch(
                f"{BASE_URL}/api/studio/projects/{PID}",
                json={
                    "shot": {
                        "episodeId": info["episodeId"],
                        "id": info["shotId"],
                        "duration": dur_int,
                        "imageId": info["imageId"],
                        "videoId": vid_id,
                        "confirmedImage": True,
                        "confirmedVideo": True,
                    }
                },
                timeout=30,
            ).raise_for_status()
            print(f"[upload-video] Ep{ep_num} {sid} -> videoId={vid_id}", flush=True)

    for ep_id, label, spec in [
        (EP1_ID, "ep01_v3", build_ep1_post_spec(shot_map)),
        (EP2_ID, "ep02_v3", build_ep2_post_spec(shot_map)),
    ]:
        pdir = WORK_DIR / f"post_{label}"
        pdir.mkdir(parents=True, exist_ok=True)
        spec_file = pdir / f"{label}_spec.json"
        spec_file.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest = post_bgm_subtitles.compile_post_pack(spec_file, pdir)

        bgm_id = upload_media(sess, Path(manifest["bgm_file"]), f"{label}_bgm.mp3", ep_id, "audio", "audio/mpeg")
        vtt_id = upload_media(sess, Path(manifest["vtt_file"]), f"{label}_subtitles.vtt", ep_id, "subtitle", "text/vtt")

        sess.patch(
            f"{BASE_URL}/api/studio/projects/{PID}",
            json={"episode": {"id": ep_id, "bgmMediaId": bgm_id, "subtitleMediaId": vtt_id, "subtitles": manifest["episode_subtitles"]}},
            timeout=30,
        ).raise_for_status()

        for sh in manifest["shots"]:
            sess.patch(
                f"{BASE_URL}/api/studio/projects/{PID}",
                json={"shot": {"episodeId": ep_id, "id": sh["studioShotId"], "bgmMediaId": bgm_id, "bgmOffset": sh["bgmOffset"], "subtitles": sh["subtitles"]}},
                timeout=30,
            ).raise_for_status()
        print(f"[post] Bound {label}: bgmMediaId={bgm_id}, subtitleMediaId={vtt_id}, total={manifest['total_duration']}s", flush=True)

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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--init-only", action="store_true")
    ap.add_argument("--upload-only", action="store_true")
    args = ap.parse_args()

    sess = login_session()
    if args.init_only:
        reset_and_create_shots(sess)
        return
    if args.upload_only:
        shot_map = json.loads((WORK_DIR / "shot_uuid_map.json").read_text(encoding="utf-8"))
        upload_videos_and_post(sess, shot_map)
        return

    shot_map = reset_and_create_shots(sess)
    upload_videos_and_post(sess, shot_map)


if __name__ == "__main__":
    main()
