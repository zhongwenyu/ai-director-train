#!/usr/bin/env python3
"""
Publish regenerated `2005_chongqing_hotpot_v7` Premise Title, Outline, Screenplay, and ALL 3 EPISODES
(`Ep 1` = 14 groups, `Ep 2` = 12 groups, `Ep 3` = 16 groups = 42 crisp shots) to Director Workstation
project `playlet-mwj57ecn-9658ad48`:
  1. Updates project `title`, `outline`, `script`, and Ep 1-3 titles/scripts (`9:16`).
  2. Clears old Ep 1, Ep 2, Ep 3 storyboards cleanly, creates all 42 new shots, and uploads 2K keyframes.
  3. Uploads audited, unburned, BGM-free 480p shot videos (`takes_ep01..03`).
  4. Compiles separated `audio-library` BGM (.mp3) + frame-clamped dual-layer WebVTT/JSON subtitles
     (`caption`, `vo`, `dialogue`) for Ep 1, Ep 2, and Ep 3, binds them, triggers full-episode merge,
     verifies all 3 merged films reach `status == "completed"` (`HTTP 200`), and writes `publish_report_v7.json`.
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

PROD_DIR = Path("/home/zhongwenyu/project/ai-director-train/productions/2005_chongqing_hotpot_v7")
WORK_DIR = PROD_DIR / "video_gen"
STUDIO_DIR = Path("/home/zhongwenyu/project/playlets-studio")
BASE_URL = "http://127.0.0.1:8765"
PID = "playlet-mwj57ecn-9658ad48"

EP1_ID = "ecec609a-31c3-407e-b368-1b598543bca8"
EP2_ID = "41d1dd8c-4172-4a26-b985-63fe17e96dce"
EP3_ID = "ed05ad9d-55c2-4a89-a8af-4d88d640ed07"

ASSET_NAME_ALIAS = {
    "混混": "周凯",
    "陈伯": "中年食客",
}


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
    parts = re.split(r"(?m)^#\s*第\s*(\d+)\s*集[　\s:：]+([^\n]+)\n", md_text)
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
    premise = json.loads((PROD_DIR / "00_premise_lock.json").read_text(encoding="utf-8"))
    outline_md = (PROD_DIR / "01_outline.md").read_text(encoding="utf-8")
    ep_md = (PROD_DIR / "combined_1-3.md").read_text(encoding="utf-8")
    ep_map = split_episodes(ep_md)

    proj_title = premise.get("title", "重生2005：收起秘方，我带青梅沸腾全国").strip("《》")
    sess.patch(
        f"{BASE_URL}/api/studio/projects/{PID}",
        json={"title": proj_title, "outline": outline_md, "script": ep_md, "aspectRatio": "9:16"},
        timeout=30,
    ).raise_for_status()

    for ep_no, ep_id in [(1, EP1_ID), (2, EP2_ID), (3, EP3_ID)]:
        title, body = ep_map[ep_no]
        sess.patch(
            f"{BASE_URL}/api/studio/projects/{PID}",
            json={"episode": {"id": ep_id, "title": title, "script": body, "aspectRatio": "9:16"}},
            timeout=30,
        ).raise_for_status()

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
        (EP1_ID, "ep01_v7_plan.json"),
        (EP2_ID, "ep02_v7_plan.json"),
        (EP3_ID, "ep03_v7_plan.json"),
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
            img_id = upload_media(sess, kf_png, f"{sid}_v7_2k.png", sh_id, "image", "image/png")
            asset_names = [ASSET_NAME_ALIAS.get(n, n) for n in sp["assetNames"]]
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
            {"start": 0.15, "end": 3.5, "kind": "caption", "speaker": "", "text": "上市前夕 · 庆功宴"},
            {"start": 3.7, "end": 7.5, "kind": "dialogue", "speaker": "叶寻", "text": "双双……这帽子怎么给他了？"},
            {"start": 7.9, "end": 11.6, "kind": "dialogue", "speaker": "林双双", "text": "都要敲钟上市了。后厨往后归赵主厨。"},
        ]),
        ("1-1-04", [
            {"start": 2.5, "end": 7.2, "kind": "dialogue", "speaker": "楚南", "text": "老叶，上市得讲门面。你那套土锅底，早该翻篇了。"},
            {"start": 7.6, "end": 11.6, "kind": "dialogue", "speaker": "赵帆", "text": "往后店里主打法式鹅肝融火锅，只接高档客。"},
        ]),
        ("1-1-07", [
            {"start": 0.15, "end": 4.4, "kind": "dialogue", "speaker": "叶寻", "text": "撤了我家的温补底料，外地客哪受得了这重辣——"},
            {"start": 4.6, "end": 10.8, "kind": "dialogue", "speaker": "林双双", "text": "少往自己脸上贴金！没楚南铺路做推广，你现在还在小县城守破灶呢！"},
        ]),
        ("1-1-10", [
            {"start": 2.5, "end": 8.2, "kind": "dialogue", "speaker": "林双双", "text": "看在以前的分上，郊区仓库给你留了个位置。去不去随你。"},
            {"start": 8.5, "end": 12.6, "kind": "dialogue", "speaker": "楚南", "text": "行了叶师傅，腾地方吧，这一身草药味儿怪冲的。"},
        ]),
        ("1-1-13", []),
        ("1-2-01", [
            {"start": 3.25, "end": 7.2, "kind": "vo", "speaker": "叶寻", "text": "十年心血，连爷爷留的方子……全喂了狗。"},
        ]),
        ("1-3-01", [
            {"start": 0.15, "end": 3.7, "kind": "caption", "speaker": "", "text": "2005年9月 · 重庆大学外餐饮街"},
            {"start": 7.1, "end": 11.6, "kind": "dialogue", "speaker": "林双双", "text": "叶寻，发什么呆呢？赶紧把你爷爷那方子拿出来呀！"},
        ]),
        ("1-3-04", [
            {"start": 0.35, "end": 3.9, "kind": "vo", "speaker": "叶寻", "text": "还没交出去……我回到试锅这天了？"},
            {"start": 4.5, "end": 9.5, "kind": "dialogue", "speaker": "楚南", "text": "双双，这九月天热得冒烟，谁进门吃火锅啊？干苦力的？"},
        ]),
        ("1-3-06", [
            {"start": 2.3, "end": 7.3, "kind": "dialogue", "speaker": "楚南", "text": "听我的，直接改高档西餐厅！外头重大的学生就吃这套。"},
            {"start": 7.8, "end": 13.4, "kind": "dialogue", "speaker": "林双双", "text": "我也想啊，可家里账上没几个活钱了，上哪儿请西餐师傅去……"},
        ]),
        ("1-3-09", [
            {"start": 0.2, "end": 5.0, "kind": "dialogue", "speaker": "楚南", "text": "找我啊！我认识个星级西餐主厨，打声招呼的事儿。"},
            {"start": 5.4, "end": 10.5, "kind": "dialogue", "speaker": "林双双", "text": "当真？不过叶寻答应今儿试锅了……叶寻，东西呢？"},
        ]),
        ("1-3-11", [
            {"start": 7.8, "end": 11.4, "kind": "dialogue", "speaker": "林双双", "text": "叶寻你发什么疯？！好端端撕它干嘛！"},
        ]),
        ("1-3-15", [
            {"start": 0.2, "end": 4.5, "kind": "dialogue", "speaker": "叶寻", "text": "楚少不是说了吗，火锅太土，别糟蹋你家这地方。"},
            {"start": 4.9, "end": 10.0, "kind": "dialogue", "speaker": "林双双", "text": "说两句你还甩上脸子了？昨晚拍胸脯说帮我家的人是谁？"},
            {"start": 10.4, "end": 14.6, "kind": "dialogue", "speaker": "楚南", "text": "嗨，人家这是有自知之明，不好意思拿土方子出来丢人。"},
        ]),
        ("1-3-18", [
            {"start": 0.15, "end": 3.3, "kind": "dialogue", "speaker": "叶寻", "text": "嗯。你们改西餐吧，我不掺和了。"},
            {"start": 5.9, "end": 9.6, "kind": "dialogue", "speaker": "林双双", "text": "一中午连个人影都没有，你现在甩手走人？！"},
        ]),
        ("1-3-21", [
            {"start": 0.15, "end": 2.4, "kind": "dialogue", "speaker": "叶寻", "text": "找你的星级主厨去。"},
            {"start": 2.9, "end": 6.6, "kind": "vo", "speaker": "叶寻", "text": "上辈子拿我当血包，这回，如你们的愿。"},
            {"start": 9.0, "end": 14.3, "kind": "dialogue", "speaker": "林双双", "text": "叶寻你给我站住！话没说清楚往哪儿走——谁准你反悔的？！"},
        ]),
    ]
    return {
        "prefix": "ep01_v7",
        "bgm_segments": [
            {
                "label": "上市前夕庆功宴背叛羞辱至扯工牌冲出包厢（冷峻悲怆悬疑 Mixkit Free）",
                "file": "/home/zhongwenyu/project/audio-library/_files/mixkit-music-374.mp3",
                "start_shot": "1-1-01",
                "end_shot": "1-1-13",
                "gain": 0.40,
                "fade_in": 0.6,
                "fade_out": 0.9,
            },
            {
                "label": "重回2005年9月林记大堂午后索方与改西餐厅算计（市井烟火衬底 CC0）",
                "file": "/home/zhongwenyu/project/audio-library/_files/freesound-845168.mp3",
                "start_shot": "1-3-01",
                "end_shot": "1-3-09",
                "gain": 0.34,
                "fade_in": 0.8,
                "fade_out": 0.7,
            },
            {
                "label": "拉死书包拉链撕毁草图入痰桶至门槛拽带悬念切集（利落反击渐强 Mixkit Free）",
                "file": "/home/zhongwenyu/project/audio-library/_files/mixkit-music-350.mp3",
                "start_shot": "1-3-11",
                "end_shot": "1-3-21",
                "src_offset": 6.0,
                "gain": 0.43,
                "fade_in": 0.6,
                "fade_out": 0.4,
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
            {"start": 2.0, "end": 7.4, "kind": "dialogue", "speaker": "林双双", "text": "行啊叶寻，跟我玩这一套——看楚南帮我出主意，吃醋了？"},
            {"start": 7.8, "end": 12.5, "kind": "dialogue", "speaker": "楚南", "text": "至于吗老叶，大老爷们儿搞欲擒故纵，掉价了啊。"},
        ]),
        ("2-1-04", [
            {"start": 0.2, "end": 4.8, "kind": "dialogue", "speaker": "林双双", "text": "差不多行了。服个软把方子交出来，刚才的事我翻篇。"},
            {"start": 7.6, "end": 11.0, "kind": "dialogue", "speaker": "叶寻", "text": "东西收好。咱俩完了。"},
            {"start": 11.4, "end": 14.6, "kind": "dialogue", "speaker": "林双双", "text": "你说什么？叶寻，你敢提分手？！"},
        ]),
        ("2-1-08", [
            {"start": 0.2, "end": 4.5, "kind": "dialogue", "speaker": "叶寻", "text": "分了。往后你家店是死是活，别来沾边。"},
            {"start": 7.0, "end": 12.4, "kind": "dialogue", "speaker": "叶寻", "text": "楚少，刚吹出去的星级主厨，赶紧给人请来啊。"},
        ]),
        ("2-1-11", [
            {"start": 0.2, "end": 4.3, "kind": "dialogue", "speaker": "林双双", "text": "楚南，你刚说的那个主厨，到底准不准？"},
            {"start": 4.7, "end": 11.2, "kind": "dialogue", "speaker": "楚南", "text": "什么准不准？就明天！我把星级主厨赵帆连装修队一块儿给你拉来！"},
        ]),
        ("2-1-14", [
            {"start": 0.2, "end": 2.2, "kind": "dialogue", "speaker": "叶寻", "text": "行，祝你们发财。"},
            {"start": 4.2, "end": 9.5, "kind": "dialogue", "speaker": "林双双", "text": "滚就滚！离了我家这门面，你那破方子烂手里都没人要！"},
        ]),
        ("2-2-01", [
            {"start": 0.15, "end": 3.4, "kind": "caption", "speaker": "", "text": "斜对门 · 夏记食府"},
            {"start": 2.6, "end": 8.0, "kind": "dialogue", "speaker": "混混", "text": "小老板娘，招工纸都撕啦？周转不开签两万块应急呗——"},
            {"start": 8.3, "end": 10.2, "kind": "dialogue", "speaker": "夏芊芊", "text": "不借！你让开——"},
        ]),
        ("2-2-04", [
            {"start": 2.7, "end": 7.7, "kind": "dialogue", "speaker": "叶寻", "text": "街口岗亭民警正往这儿瞧，过去聊聊你这利息？"},
            {"start": 8.2, "end": 12.0, "kind": "dialogue", "speaker": "混混", "text": "少管闲事！守着这冷灶台等关张吧！"},
        ]),
        ("2-2-07", [
            {"start": 2.2, "end": 6.5, "kind": "dialogue", "speaker": "夏芊芊", "text": "小寻？今天没课啊……怎么跑这儿来了？"},
            {"start": 7.15, "end": 12.3, "kind": "vo", "speaker": "叶寻", "text": "上辈子林双双搞垮夏家逼你们远走……这回有我在。"},
        ]),
        ("2-3-01", [
            {"start": 2.8, "end": 6.6, "kind": "dialogue", "speaker": "叶寻", "text": "芊芊姐，这几天客流掉得这么厉害？"},
            {"start": 7.0, "end": 13.0, "kind": "dialogue", "speaker": "夏芊芊", "text": "后街连开了几家快餐店，学生全往那边跑，昨天一天才卖两百多块！"},
        ]),
        ("2-3-05", [
            {"start": 2.9, "end": 8.2, "kind": "dialogue", "speaker": "叶寻", "text": "店别关。炒菜改做养生火锅，我出方子盯灶，咱们合伙。"},
            {"start": 8.6, "end": 13.6, "kind": "dialogue", "speaker": "夏芊芊", "text": "这哪行啊？你爷爷留的方子，不是说好拿去帮双双吗？"},
        ]),
        ("2-3-08", [
            {"start": 0.2, "end": 4.0, "kind": "dialogue", "speaker": "叶寻", "text": "刚跟她分了。这东西，我只信得过夏家。"},
            {"start": 7.2, "end": 12.5, "kind": "dialogue", "speaker": "夏建国", "text": "瞎胡闹！夏家做了一辈子川菜……改什么野路子！"},
        ]),
        ("2-3-11", [
            {"start": 0.2, "end": 4.8, "kind": "dialogue", "speaker": "夏芊芊", "text": "爸，你扁桃体肿得水都咽不下，快少说两句——"},
            {"start": 5.2, "end": 11.5, "kind": "dialogue", "speaker": "夏建国", "text": "小寻，心意叔领了……但那号上火烂嘴的红油锅，绝不能进咱家门！"},
        ]),
    ]
    return {
        "prefix": "ep02_v7",
        "bgm_segments": [
            {
                "label": "林记门口解塑料电子表拍掌断交、激将楚南抽包带过街（干脆决裂 Mixkit Free）",
                "file": "/home/zhongwenyu/project/audio-library/_files/mixkit-music-350.mp3",
                "start_shot": "2-1-01",
                "end_shot": "2-1-14",
                "gain": 0.41,
                "fade_in": 0.6,
                "fade_out": 0.8,
            },
            {
                "label": "护夏芊芊逼退混混、前厅取出祖传草本包提议合伙（温情守护 CC0）",
                "file": "/home/zhongwenyu/project/audio-library/_files/freesound-845168.mp3",
                "start_shot": "2-2-01",
                "end_shot": "2-3-05",
                "gain": 0.37,
                "fade_in": 0.7,
                "fade_out": 0.6,
            },
            {
                "label": "夏建国捂红肿脖子拎铁炒勺冲出死拒红油锅进门悬念切集（紧绷对峙 Mixkit Free）",
                "file": "/home/zhongwenyu/project/audio-library/_files/mixkit-music-374.mp3",
                "start_shot": "2-3-08",
                "end_shot": "2-3-11",
                "src_offset": 15.0,
                "gain": 0.42,
                "fade_in": 0.6,
                "fade_out": 0.4,
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
            {"start": 3.0, "end": 6.8, "kind": "dialogue", "speaker": "叶寻", "text": "夏叔，急火攻心，嗓子眼疼得像吞刀片吧？"},
            {"start": 7.2, "end": 12.5, "kind": "dialogue", "speaker": "夏建国", "text": "可不是！再闻见那股燥辣红油味儿，我这嗓子彻底交代了！"},
        ]),
        ("3-1-04", [
            {"start": 0.2, "end": 6.3, "kind": "dialogue", "speaker": "叶寻", "text": "后厨小灶借我四十分钟。熬出来您尝一口，要是烧嗓子，我拎包就走。"},
            {"start": 6.7, "end": 11.0, "kind": "dialogue", "speaker": "夏芊芊", "text": "爸，小寻从小不说空话，就让他开火试试嘛。"},
        ]),
        ("3-1-08", []),
        ("3-1-11", [
            {"start": 2.6, "end": 7.0, "kind": "dialogue", "speaker": "陈伯", "text": "老夏，背着人炖啥好汤呢？隔半条街都闻见香了！"},
        ]),
        ("3-1-14", [
            {"start": 0.2, "end": 3.4, "kind": "dialogue", "speaker": "叶寻", "text": "夏叔，趁热抿两口原汤。"},
        ]),
        ("3-1-18", [
            {"start": 2.6, "end": 7.8, "kind": "dialogue", "speaker": "夏建国", "text": "奇了……嗓子眼里那股火辣辣顶着的劲儿，真散了？！"},
            {"start": 8.2, "end": 11.6, "kind": "dialogue", "speaker": "夏芊芊", "text": "爸！你听你说话，嗓子不劈也不哑了！"},
        ]),
        ("3-1-21", [
            {"start": 2.4, "end": 7.1, "kind": "dialogue", "speaker": "陈伯", "text": "老夏你可别吃独食！闻着一点不呛嗓子，赶紧给我盛一碗！"},
            {"start": 7.5, "end": 11.6, "kind": "dialogue", "speaker": "叶寻", "text": "陈伯钱收回去，等过几天新锅挂牌，头一顿请您白吃。"},
        ]),
        ("3-1-24", [
            {"start": 5.9, "end": 11.5, "kind": "dialogue", "speaker": "夏建国", "text": "小寻，叔今儿服气了！改火锅！你拿方子占五成一，往后叔听你的！"},
            {"start": 11.9, "end": 14.7, "kind": "dialogue", "speaker": "叶寻", "text": "行，夏叔，咱先把字据落下来。"},
        ]),
        ("3-2-01", [
            {"start": 0.15, "end": 3.3, "kind": "caption", "speaker": "", "text": "次日上午"},
        ]),
        ("3-2-04", [
            {"start": 0.2, "end": 7.0, "kind": "dialogue", "speaker": "林双双", "text": "赵主厨，十五万装修款我全批了，往后一个月八千块工资，店里可就指望您啦！"},
            {"start": 7.5, "end": 14.5, "kind": "dialogue", "speaker": "赵帆", "text": "林小姐把心放肚子里，等我这正宗法式西餐一开火，整条街的土馆子全得喝西北风！"},
        ]),
        ("3-2-08", [
            {"start": 0.35, "end": 4.3, "kind": "vo", "speaker": "叶寻", "text": "赵帆……还真是这个光会摆盘吃回扣的混子。"},
            {"start": 4.8, "end": 11.6, "kind": "dialogue", "speaker": "楚南", "text": "喂——半个月后我们“塞纳河畔”西餐厅开业，对门冷锅冷灶的趁早关张吧！"},
        ]),
        ("3-2-11", [
            {"start": 0.2, "end": 4.3, "kind": "dialogue", "speaker": "林双双", "text": "叶寻，瞧见没？离了你，我家照样开高档西餐厅！"},
            {"start": 4.7, "end": 9.4, "kind": "dialogue", "speaker": "夏建国", "text": "欺负人欺负到家门口了！请个洋厨子就不知道姓啥了——"},
        ]),
        ("3-2-14", [
            {"start": 0.2, "end": 4.8, "kind": "dialogue", "speaker": "叶寻", "text": "夏叔，犯不着跟他们置气。芊芊姐，账上还能腾出多少现钱？"},
            {"start": 5.2, "end": 10.8, "kind": "dialogue", "speaker": "夏芊芊", "text": "账面一共三万八，刨去欠菜贩子的货款，手里现钱就剩两万六了。"},
            {"start": 11.2, "end": 14.6, "kind": "dialogue", "speaker": "叶寻", "text": "两万六够把前头改成明档了，今儿先从门口动——"},
        ]),
        ("3-2-17", [
            {"start": 6.0, "end": 10.4, "kind": "dialogue", "speaker": "夏芊芊", "text": "你们干什么呀！自己装修凭什么往我家门口倒沙子？！"},
        ]),
        ("3-2-20", [
            {"start": 0.2, "end": 5.8, "kind": "dialogue", "speaker": "赵帆", "text": "路窄，借你们台阶堆半个月呗，横竖你们这破店也没人登门！"},
            {"start": 6.2, "end": 9.4, "kind": "dialogue", "speaker": "夏建国", "text": "蹬鼻子上脸是吧，我跟你们拼了——"},
        ]),
        ("3-2-23", [
            {"start": 5.0, "end": 10.3, "kind": "dialogue", "speaker": "赵帆", "text": "咋的穷学生，还敢抡铁锹啊？来，往这儿拍，动一下赔十万！"},
        ]),
    ]
    return {
        "prefix": "ep03_v7",
        "bgm_segments": [
            {
                "label": "熬制十七味温补红汤隔街飘香、十分钟消肿拍板五成一股权（暖燃烟火逆袭 CC0）",
                "file": "/home/zhongwenyu/project/audio-library/_files/freesound-845168.mp3",
                "start_shot": "3-1-01",
                "end_shot": "3-1-24",
                "gain": 0.39,
                "fade_in": 0.7,
                "fade_out": 0.8,
            },
            {
                "label": "对门踩匾聘赵帆扩音叫嚣、两车沙石堵死店门（紧迫压迫 Mixkit Free）",
                "file": "/home/zhongwenyu/project/audio-library/_files/mixkit-music-374.mp3",
                "start_shot": "3-2-01",
                "end_shot": "3-2-17",
                "gain": 0.40,
                "fade_in": 0.6,
                "fade_out": 0.6,
            },
            {
                "label": "叶寻接过铁锹踏上沙石堆顶端对峙赵帆碰瓷挑衅切集（高燃悬念拉满 Mixkit Free）",
                "file": "/home/zhongwenyu/project/audio-library/_files/mixkit-music-350.mp3",
                "start_shot": "3-2-20",
                "end_shot": "3-2-23",
                "src_offset": 12.0,
                "gain": 0.45,
                "fade_in": 0.6,
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


def upload_videos_and_post(sess: requests.Session, shot_map: Dict[str, Any]) -> Dict[str, Any]:
    for ep_num, takes_dir, plan_name in [
        (1, WORK_DIR / "takes_ep01", "ep01_v7_plan.json"),
        (2, WORK_DIR / "takes_ep02", "ep02_v7_plan.json"),
        (3, WORK_DIR / "takes_ep03", "ep03_v7_plan.json"),
    ]:
        plan = json.loads((WORK_DIR / plan_name).read_text(encoding="utf-8"))
        for sp in plan:
            sid = sp["id"]
            mp4 = takes_dir / sid / "video.mp4"
            info = shot_map[sid]
            vid_id = upload_media(sess, mp4, f"{sid}_v7_480p.mp4", info["shotId"], "video", "video/mp4")
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

    report: Dict[str, Any] = {"project_id": PID, "episodes": {}}
    for ep_no, ep_id, label, spec in [
        (1, EP1_ID, "ep01_v7", build_ep1_post_spec(shot_map)),
        (2, EP2_ID, "ep02_v7", build_ep2_post_spec(shot_map)),
        (3, EP3_ID, "ep03_v7", build_ep3_post_spec(shot_map)),
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
        report["episodes"][f"ep{ep_no:02d}"] = {
            "episodeId": ep_id,
            "bgmMediaId": bgm_id,
            "subtitleMediaId": vtt_id,
            "total_duration_s": manifest["total_duration"],
            "shot_count": len(manifest["shots"]),
        }

    for ep_no, ep_id, name in [(1, EP1_ID, "Episode 1"), (2, EP2_ID, "Episode 2"), (3, EP3_ID, "Episode 3")]:
        sess.post(f"{BASE_URL}/api/studio/projects/{PID}/episodes/{ep_id}/video", json={}, timeout=30)
        for _ in range(90):
            st = sess.get(f"{BASE_URL}/api/studio/projects/{PID}/episodes/{ep_id}/video", timeout=15).json()
            mid = st.get("mediaId") or (st.get("media") or {}).get("id")
            if st.get("status") == "completed" and mid:
                head = sess.head(f"{BASE_URL}/api/studio/media/{mid}", timeout=15)
                print(
                    f"[merged] {name} film READY -> mediaId={mid} (HTTP {head.status_code}), shots={st.get('completedShots')}",
                    flush=True,
                )
                report["episodes"][f"ep{ep_no:02d}"]["filmMediaId"] = mid
                report["episodes"][f"ep{ep_no:02d}"]["httpStatus"] = head.status_code
                report["episodes"][f"ep{ep_no:02d}"]["completedShots"] = st.get("completedShots")
                break
            time.sleep(2)
        else:
            raise RuntimeError(f"{name} film merge did not complete in time: {st}")

    (WORK_DIR / "publish_report_v7.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


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
