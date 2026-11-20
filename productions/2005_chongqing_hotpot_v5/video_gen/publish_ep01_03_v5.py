#!/usr/bin/env python3
"""
Publish regenerated `2005_chongqing_hotpot_v5` Outline, Script, and ALL 3 EPISODES (`Ep 1`, `Ep 2`, `Ep 3`:
12 + 12 + 11 = 35 crisp shots) to Director Workstation project `playlet-mwj57ecn-9658ad48`:
  1. Updates `outline`, `script`, Ep 1-3 titles/scripts, and renames vendor asset `老王` -> `老马`.
  2. Clears old Ep 1, Ep 2, Ep 3 storyboards cleanly, creates all 35 new shots, and uploads 2K keyframes.
  3. Uploads audited, trimmed, BGM-free 480p shot videos.
  4. Compiles separated `audio-library` BGM (.mp3) + frame-clamped dual-layer WebVTT/JSON subtitles
     (`caption`, `vo`, `dialogue`) for Ep 1, Ep 2, and Ep 3, binds them, and verifies all 3 merged
     full-episode films reach `status == "completed"` (`HTTP 200`).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Tuple
import requests

SKILL_SCRIPTS = Path("/home/zhongwenyu/project/ai-director-train/.agents/skills/hit-video/scripts")
if str(SKILL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SKILL_SCRIPTS))
import post_bgm_subtitles  # noqa: E402

PROD_DIR = Path("/home/zhongwenyu/project/ai-director-train/productions/2005_chongqing_hotpot_v5")
WORK_DIR = PROD_DIR / "video_gen"
STUDIO_DIR = Path("/home/zhongwenyu/project/playlets-studio")
BASE_URL = "http://127.0.0.1:8765"
PID = "playlet-mwj57ecn-9658ad48"

EP1_ID = "ecec609a-31c3-407e-b368-1b598543bca8"
EP2_ID = "41d1dd8c-4172-4a26-b985-63fe17e96dce"
EP3_ID = "ed05ad9d-55c2-4a89-a8af-4d88d640ed07"
LAOMA_ASSET_ID = "d59c2497-3a6e-4af1-9163-7d76d9654411"


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


def split_episodes(md_text: str) -> Dict[int, Tuple[str, str]]:
    parts = re.split(r"(?m)^#\s*第(\d+)集[　\s]+([^\n]+)\n", md_text)
    res: Dict[int, Tuple[str, str]] = {}
    for i in range(1, len(parts), 3):
        ep_no = int(parts[i])
        title = parts[i + 1].strip()
        body = f"# 第{ep_no}集　{title}\n" + parts[i + 2].strip() + "\n"
        res[ep_no] = (f"第{ep_no}集：{title}", body)
    return res


def clamp_cues_to_video(mp4_path: Path, raw_cues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    dur = post_bgm_subtitles.probe_duration(mp4_path)
    out: List[Dict[str, Any]] = []
    for c in raw_cues:
        cc = dict(c)
        s = min(max(0.05, float(cc["start"])), max(0.1, dur - 0.5))
        e = min(float(cc["end"]), max(s + 0.35, dur - 0.08))
        cc["start"] = round(s, 2)
        cc["end"] = round(e, 2)
        out.append(cc)
    return out


def reset_and_create_shots(sess: requests.Session) -> Dict[str, Any]:
    outline_md = (PROD_DIR / "01_outline.md").read_text(encoding="utf-8")
    ep_md = (PROD_DIR / "combined_1-3.md").read_text(encoding="utf-8")
    ep_map = split_episodes(ep_md)

    # Rename 老王 -> 老马 cleanly on Workstation
    sess.patch(
        f"{BASE_URL}/api/studio/projects/{PID}",
        json={
            "asset": {
                "id": LAOMA_ASSET_ID,
                "name": "老马",
                "description": "沙正街林记与夏记两店共用的成品老油供货商，为人老实抹不开大单压力。",
            }
        },
        timeout=30,
    ).raise_for_status()

    # Sync project outline & script
    sess.patch(
        f"{BASE_URL}/api/studio/projects/{PID}",
        json={"outline": outline_md, "script": ep_md, "aspectRatio": "9:16"},
        timeout=30,
    ).raise_for_status()

    for ep_no, ep_id in [(1, EP1_ID), (2, EP2_ID), (3, EP3_ID)]:
        title, body = ep_map[ep_no]
        sess.patch(
            f"{BASE_URL}/api/studio/projects/{PID}",
            json={"episode": {"id": ep_id, "title": title, "script": body, "aspectRatio": "9:16"}},
            timeout=30,
        ).raise_for_status()

    # Clear existing Ep 1, Ep 2, Ep 3 shots cleanly
    proj = sess.get(f"{BASE_URL}/api/studio/projects/{PID}", timeout=30).json()
    for ep in proj.get("episodes", []):
        if ep["id"] not in (EP1_ID, EP2_ID, EP3_ID):
            continue
        for sh in ep.get("shots", []):
            if sh.get("imageId") or sh.get("videoId"):
                sess.patch(
                    f"{BASE_URL}/api/studio/projects/{PID}",
                    json={
                        "shot": {
                            "episodeId": ep["id"],
                            "id": sh["id"],
                            "imageId": "",
                            "videoId": "",
                            "confirmedImage": False,
                            "confirmedVideo": False,
                        }
                    },
                    timeout=30,
                ).raise_for_status()
        if ep.get("shots"):
            sess.delete(f"{BASE_URL}/api/studio/projects/{PID}/episodes/{ep['id']}/storyboard", timeout=30).raise_for_status()

    shot_map: Dict[str, Any] = {}
    for ep_id, plan_name in [
        (EP1_ID, "ep01_v5_plan.json"),
        (EP2_ID, "ep02_v5_plan.json"),
        (EP3_ID, "ep03_v5_plan.json"),
    ]:
        plan = json.loads((WORK_DIR / plan_name).read_text(encoding="utf-8"))
        for sp in plan:
            sid = sp["id"]
            r = sess.post(f"{BASE_URL}/api/studio/projects/{PID}/shots", json={"episodeId": ep_id}, timeout=30)
            r.raise_for_status()
            created = r.json()
            if "shot" in created and isinstance(created["shot"], dict):
                sh_id = created["shot"]["id"]
            elif "id" in created and "episodes" not in created:
                sh_id = created["id"]
            else:
                ep_obj = next(e for e in created["episodes"] if e["id"] == ep_id)
                sh_id = ep_obj["shots"][-1]["id"]

            kf_png = WORK_DIR / f"keyframes_2k/{sid}_2k.png"
            img_id = upload_media(sess, kf_png, f"{sid}_v5_2k.png", sh_id, "image", "image/png")
            asset_names = ["老马" if n == "老王" else n for n in sp["assetNames"]]
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
                        "assetNames": asset_names,
                        "imageId": img_id,
                        "confirmedImage": True,
                    }
                },
                timeout=30,
            ).raise_for_status()
            shot_map[sid] = {"episodeId": ep_id, "shotId": sh_id, "imageId": img_id}
            print(f"[shot-init] {sid} -> shotId={sh_id}, imageId={img_id}", flush=True)

    (WORK_DIR / "shot_uuid_map.json").write_text(json.dumps(shot_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return shot_map


def build_ep1_post_spec(shot_map: Dict[str, Any]) -> Dict[str, Any]:
    t = WORK_DIR / "takes_ep01"
    raw_shots = [
        ("1-1-01", [
            {"start": 0.15, "end": 3.5, "kind": "caption", "speaker": "", "text": "2015年 · 林氏火锅上市夜"},
            {"start": 0.25, "end": 4.6, "kind": "dialogue", "speaker": "叶寻", "text": "林叔，双双！我替林家熬坏了肺，不是说上市就完婚吗？"},
            {"start": 4.85, "end": 8.7, "kind": "dialogue", "speaker": "林有才", "text": "小寻呐，林氏都上市了，哪能招个病痨厨子当女婿？"},
        ]),
        ("1-1-02", [
            {"start": 0.15, "end": 3.5, "kind": "caption", "speaker": "", "text": "楚南｜省城楚氏餐饮少东家"},
            {"start": 0.25, "end": 4.5, "kind": "dialogue", "speaker": "林双双", "text": "阿寻哥，看清这金表没？毕业前楚南哥早送我了。"},
            {"start": 4.75, "end": 8.7, "kind": "dialogue", "speaker": "楚南", "text": "骗全你们叶家红汤秘方，你的用处早到头了。"},
        ]),
        ("1-1-03", [
            {"start": 0.25, "end": 4.1, "kind": "dialogue", "speaker": "叶寻", "text": "那是我爸的心血……你们不得好死！"},
        ]),
        ("1-2-01", [
            {"start": 0.15, "end": 3.8, "kind": "caption", "speaker": "", "text": "2005年7月 · 重庆沙正街林记火锅"},
            {"start": 0.7, "end": 5.6, "kind": "vo", "speaker": "叶寻", "text": "二〇〇五年……我回到了双双毕业家宴这天？"},
        ]),
        ("1-2-02", [
            {"start": 0.15, "end": 4.2, "kind": "caption", "speaker": "", "text": "林有才｜林记老板·叶父师弟　林双双｜林有才独女"},
            {"start": 0.25, "end": 5.1, "kind": "dialogue", "speaker": "林有才", "text": "小寻，林叔敬你！你厨校毕业掌勺四年，林记全靠你撑火！"},
            {"start": 5.4, "end": 9.6, "kind": "dialogue", "speaker": "林双双", "text": "是呀阿寻哥，多亏你守灶供我读完省城财大。"},
        ]),
        ("1-2-03", [
            {"start": 0.25, "end": 3.0, "kind": "dialogue", "speaker": "叶寻", "text": "林叔，今天吹什么风，这么客气？"},
            {"start": 3.3, "end": 9.6, "kind": "dialogue", "speaker": "林有才", "text": "你爸走得早，林叔早把你当亲半子疼，下月初八给你们定亲，分你林记三成干股！"},
        ]),
        ("1-2-04", [
            {"start": 0.25, "end": 3.0, "kind": "dialogue", "speaker": "叶寻", "text": "三成干股，下个月就定亲？"},
            {"start": 3.3, "end": 8.6, "kind": "dialogue", "speaker": "林双双", "text": "那还有假？下周换新执照，想拿招牌红汤报评优。"},
        ]),
        ("1-2-05", [
            {"start": 0.25, "end": 4.4, "kind": "dialogue", "speaker": "林双双", "text": "叶叔那方子还缺最后三味退燥配比，你写全嘛。"},
            {"start": 4.7, "end": 8.6, "kind": "dialogue", "speaker": "林有才", "text": "写全锁柜里，往后这店不都是你们小两口的？"},
        ]),
        ("1-2-06", [
            {"start": 0.3, "end": 4.4, "kind": "vo", "speaker": "叶寻", "text": "前世刚补全这三味，他们就拿婚约拖死我十年。"},
            {"start": 4.8, "end": 9.6, "kind": "dialogue", "speaker": "叶寻", "text": "我爸留我立命的方子，没定亲就交，太早了吧？"},
        ]),
        ("1-2-07", [
            {"start": 0.2, "end": 3.5, "kind": "dialogue", "speaker": "林有才", "text": "一家人咋还见外？林叔还能亏待自家姑爷？"},
            {"start": 3.7, "end": 7.0, "kind": "dialogue", "speaker": "林双双", "text": "阿寻哥你疑心我？我一毕业就回来守着你呢！"},
            {"start": 7.2, "end": 10.7, "kind": "dialogue", "speaker": "叶寻", "text": "守着我？你腕上这块浪琴金表，专柜得八千多吧？"},
        ]),
        ("1-2-08", [
            {"start": 0.2, "end": 3.5, "kind": "dialogue", "speaker": "林双双", "text": "这……省城地摊几十块买的仿表，你看岔了！"},
            {"start": 3.7, "end": 6.8, "kind": "dialogue", "speaker": "叶寻", "text": "仿表有原厂钢印？省城哪位少爷送的定情礼？"},
            {"start": 7.0, "end": 9.7, "kind": "dialogue", "speaker": "林有才", "text": "大喜日子揪着块表盘问啥？快把方子写上！"},
        ]),
        ("1-2-09", [
            {"start": 0.3, "end": 4.2, "kind": "dialogue", "speaker": "叶寻", "text": "方子补全，下月进林家门的，真是我吗？"},
        ]),
    ]
    return {
        "prefix": "ep01_v5",
        "bgm_segments": [
            {
                "label": "2015雨夜惨死背叛开场（悲怆冷峻悬疑 Mixkit Free）",
                "file": "/home/zhongwenyu/project/audio-library/_files/mixkit-music-374.mp3",
                "start_shot": "1-1-01",
                "end_shot": "1-1-03",
                "gain": 0.42,
                "fade_in": 0.6,
                "fade_out": 0.8,
            },
            {
                "label": "2005毕业家宴温情画饼表象（烟火暖调 CC0）",
                "file": "/home/zhongwenyu/project/audio-library/_files/freesound-845168.mp3",
                "start_shot": "1-2-01",
                "end_shot": "1-2-05",
                "gain": 0.36,
                "fade_in": 0.8,
                "fade_out": 0.8,
            },
            {
                "label": "推回账本点破八千浪琴金表至全场骤僵悬念切集（暗流逼压 Mixkit Free）",
                "file": "/home/zhongwenyu/project/audio-library/_files/mixkit-music-374.mp3",
                "start_shot": "1-2-06",
                "end_shot": "1-2-09",
                "src_offset": 18.0,
                "gain": 0.42,
                "fade_in": 0.8,
                "fade_out": 0.35,
            },
        ],
        "shots": [
            {
                "id": sid,
                "studioShotId": shot_map[sid]["shotId"],
                "video": str(t / sid / "video.mp4"),
                "cues": clamp_cues_to_video(t / sid / "video.mp4", cues),
            }
            for sid, cues in raw_shots
        ],
    }


def build_ep2_post_spec(shot_map: Dict[str, Any]) -> Dict[str, Any]:
    t = WORK_DIR / "takes_ep02"
    raw_shots = [
        ("2-1-01", [
            {"start": 0.2, "end": 4.0, "kind": "dialogue", "speaker": "林双双", "text": "阿寻哥，你胡说啥，什么进门不进门的！"},
            {"start": 4.3, "end": 8.6, "kind": "dialogue", "speaker": "林有才", "text": "小寻，林叔看你长大，一家人你说啥子怪话？"},
        ]),
        ("2-1-02", [
            {"start": 1.15, "end": 4.6, "kind": "dialogue", "speaker": "叶寻", "text": "一家人？熟练大厨月薪两千二，林叔给我发多少？"},
            {"start": 4.9, "end": 9.6, "kind": "dialogue", "speaker": "林有才", "text": "每月四百零花还少？余钱不是替你攒着娶双双吗！"},
        ]),
        ("2-1-03", [
            {"start": 0.2, "end": 3.5, "kind": "dialogue", "speaker": "叶寻", "text": "攒彩礼，还是拿我的手艺钱供她读完四年大学？"},
            {"start": 3.7, "end": 6.5, "kind": "dialogue", "speaker": "林双双", "text": "当年是你甘愿供我的，现在翻什么旧账！"},
            {"start": 6.7, "end": 9.7, "kind": "dialogue", "speaker": "叶寻", "text": "我是供未婚妻，不是替省城楚少楚南养女人。"},
        ]),
        ("2-1-04", [
            {"start": 0.75, "end": 2.65, "kind": "dialogue", "speaker": "林双双", "text": "你……你怎么知道楚南哥？"},
            {"start": 4.9, "end": 11.35, "kind": "dialogue", "speaker": "叶寻", "text": "大四实习你就跟了他，等三天后他来验汤，好拿全方献宝吧？"},
            {"start": 11.48, "end": 14.8, "kind": "vo", "speaker": "叶寻", "text": "前世直到死前，我才知楚南一直在幕后等摘桃子。"},
        ]),
        ("2-1-05", [
            {"start": 0.2, "end": 3.5, "kind": "dialogue", "speaker": "林有才", "text": "行，既然看穿了，林叔也不跟你装糊涂。"},
            {"start": 3.7, "end": 6.9, "kind": "dialogue", "speaker": "林双双", "text": "人往高处走！楚少肯注资二十万，你给得起吗？"},
            {"start": 7.1, "end": 9.7, "kind": "dialogue", "speaker": "叶寻", "text": "二十万买我叶家祖传锅底，算盘打得真响。"},
        ]),
        ("2-1-06", [
            {"start": 0.3, "end": 9.5, "kind": "dialogue", "speaker": "林有才", "text": "少拿乔！你炒料四年，二十多味香料顺序我早看熟了！有楚少二十万撑腰，离了我林记，你连口铁锅都支不起！"},
        ]),
        ("2-1-07", [
            {"start": 3.1, "end": 6.6, "kind": "dialogue", "speaker": "林有才", "text": "你干啥！把试配单捞出来！"},
        ]),
        ("2-1-08", [
            {"start": 0.25, "end": 5.05, "kind": "dialogue", "speaker": "叶寻", "text": "灶火我替林家烧了四年，今天撤勺熄火，两清了。"},
        ]),
        ("2-1-09", [
            {"start": 0.2, "end": 4.4, "kind": "dialogue", "speaker": "林双双", "text": "你身无分文出门，不出三天就得回来求我爸！"},
            {"start": 4.7, "end": 7.7, "kind": "dialogue", "speaker": "叶寻", "text": "三天后谁求谁，走着瞧。"},
        ]),
        ("2-2-01", [
            {"start": 0.15, "end": 3.8, "kind": "caption", "speaker": "", "text": "夏芊芊｜对门夏记少掌柜 · 叶家世交"},
            {"start": 0.3, "end": 3.9, "kind": "dialogue", "speaker": "夏芊芊", "text": "小寻哥！真跟林有才断干净了？"},
            {"start": 4.2, "end": 8.6, "kind": "dialogue", "speaker": "叶寻", "text": "芊芊？嗯，火熄了，往后跟林记再无瓜葛。"},
        ]),
        ("2-2-02", [
            {"start": 0.2, "end": 4.3, "kind": "dialogue", "speaker": "林有才", "text": "夏丫头，你店里昨晚刚跑了师傅，自身都难保喽！"},
            {"start": 4.6, "end": 8.7, "kind": "dialogue", "speaker": "叶寻", "text": "林老板还是先操心今晚自己的锅底能不能熬响吧。"},
        ]),
        ("2-2-03", [
            {"start": 0.15, "end": 4.85, "kind": "dialogue", "speaker": "夏芊芊", "text": "说得好！叶叔的老铁勺还在，小寻哥，来我夏记掌勺敢不敢？"},
        ]),
    ]
    return {
        "prefix": "ep02_v5",
        "bgm_segments": [
            {
                "label": "原桌拆穿四年吸血旧账与楚南私情对峙（冷冽交锋 Mixkit Free）",
                "file": "/home/zhongwenyu/project/audio-library/_files/mixkit-music-374.mp3",
                "start_shot": "2-1-01",
                "end_shot": "2-1-06",
                "gain": 0.40,
                "fade_in": 0.6,
                "fade_out": 0.8,
            },
            {
                "label": "茶碗毁稿、拧死燃气总阀摘下亡父老铁勺断恩出门（燃爽决断 Mixkit Free）",
                "file": "/home/zhongwenyu/project/audio-library/_files/mixkit-music-350.mp3",
                "start_shot": "2-1-07",
                "end_shot": "2-2-03",
                "src_offset": 8.0,
                "gain": 0.43,
                "fade_in": 0.6,
                "fade_out": 0.5,
            },
        ],
        "shots": [
            {
                "id": sid,
                "studioShotId": shot_map[sid]["shotId"],
                "video": str(t / sid / "video.mp4"),
                "cues": clamp_cues_to_video(t / sid / "video.mp4", cues),
            }
            for sid, cues in raw_shots
        ],
    }


def build_ep3_post_spec(shot_map: Dict[str, Any]) -> Dict[str, Any]:
    t = WORK_DIR / "takes_ep03"
    raw_shots = [
        ("3-1-01", [
            {"start": 0.2, "end": 2.8, "kind": "dialogue", "speaker": "叶寻", "text": "昨晚店里师傅怎么突然跑了？"},
            {"start": 3.1, "end": 9.6, "kind": "dialogue", "speaker": "夏芊芊", "text": "省城那姓楚的开双倍工钱，连夜把人挖走了。当年叶叔救过我爸的急，只要你掌勺，夏记咱五五分！"},
        ]),
        ("3-1-02", [
            {"start": 0.2, "end": 4.0, "kind": "dialogue", "speaker": "叶寻", "text": "交情归交情，我不白拿股，咱们立字据。"},
            {"start": 4.3, "end": 7.7, "kind": "dialogue", "speaker": "夏芊芊", "text": "立啥规矩？我还信不过叶叔的儿子？"},
        ]),
        ("3-1-03", [
            {"start": 0.2, "end": 5.8, "kind": "dialogue", "speaker": "叶寻", "text": "三天内晚市十二桌满座翻台，我才拿四成分红；要是做不到，我分文不取。"},
            {"start": 6.1, "end": 9.7, "kind": "dialogue", "speaker": "夏芊芊", "text": "痛快！我管账备菜，小寻哥掌勺，咱们这就开火！"},
        ]),
        ("3-1-04", [
            {"start": 0.15, "end": 3.8, "kind": "caption", "speaker": "", "text": "老马｜两店共用油料商"},
            {"start": 0.2, "end": 4.2, "kind": "dialogue", "speaker": "夏芊芊", "text": "老马，来得正好！今天送我们夏记的成品老油呢？"},
            {"start": 4.5, "end": 8.6, "kind": "dialogue", "speaker": "老马", "text": "夏掌柜对不住！二十块定金退你，油我送不了了。"},
        ]),
        ("3-1-05", [
            {"start": 0.2, "end": 3.1, "kind": "dialogue", "speaker": "叶寻", "text": "老马，是对门林有才卡我们吧？"},
            {"start": 3.4, "end": 7.6, "kind": "dialogue", "speaker": "老马", "text": "叶师傅明鉴！林老板拿楚氏大单压我，不准给夏记供油！"},
        ]),
        ("3-1-06", [
            {"start": 0.2, "end": 4.1, "kind": "dialogue", "speaker": "林有才", "text": "哟，老油断供啦？今晚你们夏记拿白水煮菜嗦！"},
            {"start": 4.4, "end": 7.1, "kind": "dialogue", "speaker": "夏芊芊", "text": "林有才，挖人又断货，你还要不要脸！"},
            {"start": 7.3, "end": 9.8, "kind": "dialogue", "speaker": "叶寻", "text": "芊芊，拿两百块钱，我去菜场买鲜牛板油！"},
        ]),
        ("3-2-01", [
            {"start": 0.15, "end": 3.6, "kind": "caption", "speaker": "", "text": "一小时后 · 晚市前夕"},
            {"start": 0.2, "end": 4.5, "kind": "dialogue", "speaker": "林有才", "text": "叶寻，临上客现买生板油熬？熬出来全是生腥气！"},
            {"start": 4.8, "end": 8.7, "kind": "dialogue", "speaker": "叶寻", "text": "林老板，谁规定老火锅非得靠隔夜陈油撑场面？"},
        ]),
        ("3-2-02", [
            {"start": 0.2, "end": 4.2, "kind": "dialogue", "speaker": "夏芊芊", "text": "小寻哥，现熬来得及吗？急火催油可容易发苦。"},
            {"start": 4.5, "end": 8.7, "kind": "dialogue", "speaker": "叶寻", "text": "偷学皮毛才怕苦。叶家红汤的根，就在现炼鲜油上。"},
        ]),
        ("3-2-03", [
            {"start": 0.3, "end": 5.2, "kind": "vo", "speaker": "叶寻", "text": "林有才偷看四年，却不知慢火三沸、醪糟退燥才是命门。"},
            {"start": 5.6, "end": 9.6, "kind": "dialogue", "speaker": "夏芊芊", "text": "好香！半点牛腥都没有，闻着还有股清甜劲儿！"},
        ]),
        ("3-2-04", [
            {"start": 3.1, "end": 6.7, "kind": "dialogue", "speaker": "林有才", "text": "邪门了……生板油现熬，咋没一点焦燥味？"},
        ]),
        ("3-2-05", [
            {"start": 0.2, "end": 3.9, "kind": "dialogue", "speaker": "叶寻", "text": "油成了，开堂迎客！今晚就跟对门比一锅真章！"},
            {"start": 4.1, "end": 7.1, "kind": "dialogue", "speaker": "夏芊芊", "text": "好嘞！夏记清润老火锅，现熬头锅红汤开灶喽！"},
        ]),
    ]
    return {
        "prefix": "ep03_v5",
        "bgm_segments": [
            {
                "label": "夏记谈明同源困局、立三日满座四成分红对赌字据（温暖坚定同盟 CC0）",
                "file": "/home/zhongwenyu/project/audio-library/_files/freesound-845168.mp3",
                "start_shot": "3-1-01",
                "end_shot": "3-1-03",
                "gain": 0.40,
                "fade_in": 0.7,
                "fade_out": 0.7,
            },
            {
                "label": "老马退定金断供成品油、林有才门外冷嘲施压（紧迫压迫 Mixkit Free）",
                "file": "/home/zhongwenyu/project/audio-library/_files/mixkit-music-374.mp3",
                "start_shot": "3-1-04",
                "end_shot": "3-1-06",
                "gain": 0.40,
                "fade_in": 0.6,
                "fade_out": 0.7,
            },
            {
                "label": "当街架铁锅现炼鲜牛板油、醪糟退燥醇香漫街破局迎客（燃爽高潮 Mixkit Free）",
                "file": "/home/zhongwenyu/project/audio-library/_files/mixkit-music-350.mp3",
                "start_shot": "3-2-01",
                "end_shot": "3-2-05",
                "src_offset": 12.0,
                "gain": 0.45,
                "fade_in": 0.8,
                "fade_out": 0.5,
            },
        ],
        "shots": [
            {
                "id": sid,
                "studioShotId": shot_map[sid]["shotId"],
                "video": str(t / sid / "video.mp4"),
                "cues": clamp_cues_to_video(t / sid / "video.mp4", cues),
            }
            for sid, cues in raw_shots
        ],
    }


def upload_videos_and_post(sess: requests.Session, shot_map: Dict[str, Any]) -> None:
    for ep_num, takes_dir, plan_name in [
        (1, WORK_DIR / "takes_ep01", "ep01_v5_plan.json"),
        (2, WORK_DIR / "takes_ep02", "ep02_v5_plan.json"),
        (3, WORK_DIR / "takes_ep03", "ep03_v5_plan.json"),
    ]:
        plan = json.loads((WORK_DIR / plan_name).read_text(encoding="utf-8"))
        for sp in plan:
            sid = sp["id"]
            mp4 = takes_dir / sid / "video.mp4"
            info = shot_map[sid]
            if sid == "3-2-04":
                kf_png = WORK_DIR / "keyframes_2k/3-2-04_2k.png"
                info["imageId"] = upload_media(sess, kf_png, "3-2-04_v5_2k_clean.png", info["shotId"], "image", "image/png")
            vid_id = upload_media(sess, mp4, f"{sid}_v5_480p.mp4", info["shotId"], "video", "video/mp4")
            dur_int = max(5, min(15, int(round(post_bgm_subtitles.probe_duration(mp4)))))
            sess.patch(
                f"{BASE_URL}/api/studio/projects/{PID}",
                json={
                    "shot": {
                        "episodeId": info["episodeId"],
                        "id": info["shotId"],
                        "videoPrompt": sp["prompt"],
                        "duration": dur_int,
                        "imageId": info["imageId"],
                        "videoId": vid_id,
                        "confirmedImage": True,
                        "confirmedVideo": True,
                    }
                },
                timeout=30,
            ).raise_for_status()
            print(f"[upload-video] Ep{ep_num} {sid} -> videoId={vid_id} ({dur_int}s)", flush=True)

    for ep_id, label, spec in [
        (EP1_ID, "ep01_v5", build_ep1_post_spec(shot_map)),
        (EP2_ID, "ep02_v5", build_ep2_post_spec(shot_map)),
        (EP3_ID, "ep03_v5", build_ep3_post_spec(shot_map)),
    ]:
        pdir = WORK_DIR / f"post_{label}"
        pdir.mkdir(parents=True, exist_ok=True)
        spec_file = pdir / f"{label}_spec.json"
        spec_file.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        manifest = post_bgm_subtitles.compile_post_pack(spec_file, pdir)

        bgm_id = upload_media(sess, Path(manifest["bgm_file"]), f"{label}_bgm.mp3", ep_id, "audio", "audio/mpeg")
        vtt_id = upload_media(sess, Path(manifest["vtt_file"]), f"{label}_subtitles.vtt", ep_id, "subtitle", "text/vtt")

        sess.patch(
            f"{BASE_URL}/api/studio/projects/{PID}",
            json={
                "episode": {
                    "id": ep_id,
                    "bgmMediaId": bgm_id,
                    "subtitleMediaId": vtt_id,
                    "subtitles": manifest["episode_subtitles"],
                }
            },
            timeout=30,
        ).raise_for_status()

        for sh in manifest["shots"]:
            sess.patch(
                f"{BASE_URL}/api/studio/projects/{PID}",
                json={
                    "shot": {
                        "episodeId": ep_id,
                        "id": sh["studioShotId"],
                        "bgmMediaId": bgm_id,
                        "bgmOffset": sh["bgmOffset"],
                        "subtitles": sh["subtitles"],
                    }
                },
                timeout=30,
            ).raise_for_status()
        print(f"[post] Bound {label}: bgmMediaId={bgm_id}, subtitleMediaId={vtt_id}, total={manifest['total_duration']}s", flush=True)

    for ep_id, name in [(EP1_ID, "Episode 1"), (EP2_ID, "Episode 2"), (EP3_ID, "Episode 3")]:
        sess.post(f"{BASE_URL}/api/studio/projects/{PID}/episodes/{ep_id}/video", json={}, timeout=30)
        for _ in range(60):
            st = sess.get(f"{BASE_URL}/api/studio/projects/{PID}/episodes/{ep_id}/video", timeout=15).json()
            mid = st.get("mediaId") or (st.get("media") or {}).get("id")
            if st.get("status") == "completed" and mid:
                head = sess.head(f"{BASE_URL}/api/studio/media/{mid}", timeout=15)
                print(
                    f"[merged] {name} film READY -> mediaId={mid} (HTTP {head.status_code}), shots={st.get('completedShots')}",
                    flush=True,
                )
                break
            time.sleep(2)
        else:
            raise RuntimeError(f"{name} film merge did not complete in time: {st}")


def main() -> None:
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
