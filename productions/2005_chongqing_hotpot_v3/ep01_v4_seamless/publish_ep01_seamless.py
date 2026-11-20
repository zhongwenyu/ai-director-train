#!/usr/bin/env python3
"""
Publish Episode 1 Seamless Continuity Cut (ep01_v4_seamless) to Director Workstation
project playlet-mwj57ecn-9658ad48 (Episode 1: ecec609a-31c3-407e-b368-1b598543bca8),
compile separated BGM (.mp3) + dual-layer WebVTT/JSON subtitles, wait for EpisodeFilmQueue
auto-merge to reach `completed`, and print the merged Episode 1 MP4 path for full-episode
transition continuity inspection.
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

PREV_WORK = Path("/home/zhongwenyu/project/ai-director-train/productions/2005_chongqing_hotpot_v3/ep01_02_video_gen")
WORK_DIR = Path("/home/zhongwenyu/project/ai-director-train/productions/2005_chongqing_hotpot_v3/ep01_v4_seamless")
STUDIO_DIR = Path("/home/zhongwenyu/project/playlets-studio")
BASE_URL = "http://127.0.0.1:8765"
PID = "playlet-mwj57ecn-9658ad48"
EP1_ID = "ecec609a-31c3-407e-b368-1b598543bca8"


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


def build_ep1_post_spec(shot_map: dict, cue_overrides: dict) -> dict:
    t = WORK_DIR / "takes_ep01"
    default_cues = {
        "1-1-01": [
            {"start": 0.2, "end": 2.6, "kind": "caption", "speaker": "", "text": "2005年夏 · 重庆老街 林记火锅"},
            {"start": 2.6, "end": 8.2, "kind": "dialogue", "speaker": "林双双", "text": "把你叶家清润汤剩下几味草本补全，咱俩婚约算完了。"},
        ],
        "1-1-02": [
            {"start": 0.25, "end": 5.4, "kind": "vo", "speaker": "叶寻", "text": "重回2005年？前世我交出祖传秘方，反被他们榨干赶出老街！"},
            {"start": 5.8, "end": 11.2, "kind": "dialogue", "speaker": "楚南", "text": "双双马上进我楚氏餐饮当主管，能嫁你个满身牛油味的伙夫？"},
        ],
        "1-1-03": [
            {"start": 0.2, "end": 4.2, "kind": "dialogue", "speaker": "林有才", "text": "白吃我家四年，留张方子抵恩，是你的本分！"},
            {"start": 8.4, "end": 11.8, "kind": "dialogue", "speaker": "林双双", "text": "叶寻你疯了！敢撕我家的方子？"},
        ],
        "1-1-04": [
            {"start": 0.3, "end": 2.8, "kind": "caption", "speaker": "", "text": "邮政汇款存根（共48张 · 四年大学学费生活费）"},
            {"start": 2.0, "end": 8.2, "kind": "dialogue", "speaker": "叶寻", "text": "我辍学熬四年牛油，四十八张汇款单供你读完大学，两清了！"},
        ],
        "1-1-05": [
            {"start": 1.5, "end": 5.2, "kind": "dialogue", "speaker": "叶寻", "text": "今晚起火我撤了，看你们拿什么端上桌！"},
            {"start": 5.6, "end": 10.2, "kind": "dialogue", "speaker": "林有才", "text": "忘恩负义的东西！离了林记，这条街谁敢要你？"},
        ],
        "1-2-01": [
            {"start": 0.25, "end": 5.2, "kind": "vo", "speaker": "叶寻", "text": "前世只有世交芊芊护我到底，这辈子换我撑起夏记！"},
            {"start": 5.6, "end": 11.4, "kind": "dialogue", "speaker": "夏芊芊", "text": "叶爷爷熬汤真传我从小看着！林家瞎了眼，夏记迎你掌勺！"},
        ],
        "1-2-02": [
            {"start": 0.3, "end": 4.6, "kind": "caption", "speaker": "", "text": "合营契书：叶夏合营 · 五五分账"},
            {"start": 5.0, "end": 9.4, "kind": "dialogue", "speaker": "夏芊芊", "text": "五五分账，往后咱俩一口锅里搅马勺！"},
        ],
        "1-2-03": [
            {"start": 0.2, "end": 7.1, "kind": "dialogue", "speaker": "楚南", "text": "夏芊芊，敢收他？明早断你夏记全部成品牛油，看你拿什么交房租！"},
            {"start": 7.5, "end": 13.0, "kind": "dialogue", "speaker": "林双双", "text": "你们备好菜的机械厂十二桌席，周厂长刚改签给林记了！"},
        ],
        "1-2-04": [
            {"start": 0.2, "end": 3.5, "kind": "dialogue", "speaker": "夏芊芊", "text": "成品牛油全断了，明早拿什么开火？"},
            {"start": 3.8, "end": 8.8, "kind": "dialogue", "speaker": "叶寻", "text": "不用陈年老油！上车，去屠宰场抢今晚头刀鲜牛板油！"},
            {"start": 9.0, "end": 11.2, "kind": "dialogue", "speaker": "夏芊芊", "text": "走！我跟你去！"},
        ],
    }
    default_cues.update(cue_overrides)

    shots = []
    for sid in ["1-1-01", "1-1-02", "1-1-03", "1-1-04", "1-1-05", "1-2-01", "1-2-02", "1-2-03", "1-2-04"]:
        shots.append({
            "id": sid,
            "studioShotId": shot_map[sid]["shotId"],
            "video": str(t / sid / "video.mp4"),
            "cues": default_cues[sid],
        })

    return {
        "prefix": "ep01_v4_seamless",
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
                "label": "跨过6米老街入伙对门夏记摁红手印立五五契书（温暖烟火同盟 CC0）",
                "file": "/home/zhongwenyu/project/audio-library/_files/freesound-845168.mp3",
                "start_shot": "1-2-01",
                "end_shot": "1-2-02",
                "end_delta": -3.2,
                "gain": 0.42,
                "fade_in": 0.8,
                "fade_out": 0.6,
            },
            {
                "label": "门外脚步堵门断油抢席与推三轮上车连夜抢鲜牛板油（燃情破局出发 Mixkit Free）",
                "file": "/home/zhongwenyu/project/audio-library/_files/mixkit-music-350.mp3",
                "start_shot": "1-2-03",
                "end_shot": "1-2-04",
                "src_offset": 12.0,
                "gain": 0.44,
                "fade_in": 0.8,
                "fade_out": 0.6,
            },
        ],
        "shots": shots,
    }


def main():
    sess = login_session()
    shot_map = json.loads((PREV_WORK / "shot_uuid_map.json").read_text(encoding="utf-8"))
    plan = json.loads((WORK_DIR / "ep01_v4_plan.json").read_text(encoding="utf-8"))
    cue_overrides_file = WORK_DIR / "cue_overrides.json"
    cue_overrides = json.loads(cue_overrides_file.read_text(encoding="utf-8")) if cue_overrides_file.is_file() else {}

    for sp in plan:
        sid = sp["id"]
        info = shot_map[sid]
        kf_png = WORK_DIR / f"keyframes_2k/{sid}.png"
        mp4 = WORK_DIR / f"takes_ep01/{sid}/video.mp4"
        img_id = upload_media(sess, kf_png, f"{sid}_v4_seamless_2k.png", info["shotId"], "image", "image/png")
        vid_id = upload_media(sess, mp4, f"{sid}_v4_seamless_480p.mp4", info["shotId"], "video", "video/mp4")
        dur_int = max(5, min(15, int(round(post_bgm_subtitles.probe_duration(mp4)))))
        sess.patch(
            f"{BASE_URL}/api/studio/projects/{PID}",
            json={
                "shot": {
                    "episodeId": EP1_ID,
                    "id": info["shotId"],
                    "description": f"[{sid}] {sp['description']}",
                    "dialogue": sp["dialogue"],
                    "videoPrompt": sp["prompt"],
                    "duration": dur_int,
                    "assetNames": sp["assetNames"],
                    "imageId": img_id,
                    "videoId": vid_id,
                    "confirmedImage": True,
                    "confirmedVideo": True,
                }
            },
            timeout=30,
        ).raise_for_status()
        print(f"[upload-ep1-v4] {sid} -> imageId={img_id}, videoId={vid_id}", flush=True)

    pdir = WORK_DIR / "post_ep01_v4"
    pdir.mkdir(parents=True, exist_ok=True)
    spec = build_ep1_post_spec(shot_map, cue_overrides)
    spec_file = pdir / "ep01_v4_spec.json"
    spec_file.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = post_bgm_subtitles.compile_post_pack(spec_file, pdir)

    bgm_id = upload_media(sess, Path(manifest["bgm_file"]), "ep01_v4_seamless_bgm.mp3", EP1_ID, "audio", "audio/mpeg")
    vtt_id = upload_media(sess, Path(manifest["vtt_file"]), "ep01_v4_seamless_subtitles.vtt", EP1_ID, "subtitle", "text/vtt")

    sess.patch(
        f"{BASE_URL}/api/studio/projects/{PID}",
        json={"episode": {"id": EP1_ID, "bgmMediaId": bgm_id, "subtitleMediaId": vtt_id, "subtitles": manifest["episode_subtitles"]}},
        timeout=30,
    ).raise_for_status()

    for sh in manifest["shots"]:
        sess.patch(
            f"{BASE_URL}/api/studio/projects/{PID}",
            json={"shot": {"episodeId": EP1_ID, "id": sh["studioShotId"], "bgmMediaId": bgm_id, "bgmOffset": sh["bgmOffset"], "subtitles": sh["subtitles"]}},
            timeout=30,
        ).raise_for_status()

    sess.post(f"{BASE_URL}/api/studio/projects/{PID}/episodes/{EP1_ID}/video", json={}, timeout=30)
    for _ in range(45):
        st = sess.get(f"{BASE_URL}/api/studio/projects/{PID}/episodes/{EP1_ID}/video", timeout=15).json()
        mid = st.get("mediaId") or (st.get("media") or {}).get("id")
        if st.get("status") == "completed" and mid:
            head = sess.head(f"{BASE_URL}/api/studio/media/{mid}", timeout=15)
            print(f"[merged-ep1-v4] Episode 1 film READY -> mediaId={mid} (HTTP {head.status_code}), total={manifest['total_duration']}s", flush=True)
            break
        time.sleep(2)
    else:
        raise RuntimeError(f"Episode 1 v4 merge timed out: {st}")


if __name__ == "__main__":
    main()
