#!/usr/bin/env python3
"""Upload validated blocking keyframes and shot videos to Director Workstation and optionally trigger episode film merge."""
import argparse
import json
import urllib.parse
import urllib.request
from pathlib import Path


def login_studio(base_url: str, password_file: Path) -> str:
    pw = password_file.read_text(encoding="utf-8").strip()
    req = urllib.request.Request(
        f"{base_url}/api/login",
        data=json.dumps({"password": pw}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        set_cookie = resp.headers.get("set-cookie") or ""
        return set_cookie.split(";")[0]


def api_json(base_url: str, cookie: str, method: str, path: str, payload=None) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    headers = {"Cookie": cookie}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{base_url}{path}", data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def upload_binary(base_url: str, cookie: str, project_id: str, file_path: Path,
                  target_id: str, media_type: str, mime: str, name: str) -> dict:
    qs = urllib.parse.urlencode({"name": name, "targetId": target_id, "type": media_type})
    req = urllib.request.Request(
        f"{base_url}/api/studio/projects/{project_id}/upload?{qs}",
        data=file_path.read_bytes(),
        headers={"Cookie": cookie, "Content-Type": mime},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", required=True)
    ap.add_argument("--episode", required=True)
    ap.add_argument("--plan", required=True, type=Path)
    ap.add_argument("--videos-dir", required=True, type=Path)
    ap.add_argument("--base-url", default="http://127.0.0.1:8765")
    ap.add_argument("--password-file", type=Path, default=Path("/home/zhongwenyu/project/playlets-studio/runtime/initial-password.txt"))
    ap.add_argument("--merge-episode", action="store_true")
    args = ap.parse_args()

    cookie = login_studio(args.base_url, args.password_file)
    specs = json.loads(args.plan.read_text(encoding="utf-8"))

    uploaded = []
    for sp in specs:
        sid = sp["id"]
        shot_uuid = sp["shot_uuid"]
        kf_path = Path(sp["keyframe_2k"]) if sp.get("keyframe_2k") else None
        mp4_path = args.videos_dir / sid / "video.mp4"
        assert mp4_path.is_file(), f"Missing video for {sid}: {mp4_path}"

        kf_media_id = None
        if kf_path and kf_path.is_file():
            up_kf = upload_binary(
                args.base_url, cookie, args.project, kf_path,
                target_id=shot_uuid, media_type="image", mime="image/png", name=f"{sid}_keyframe.png"
            )
            kf_media_id = up_kf.get("media", {}).get("id") or up_kf.get("id")

        up_vid = upload_binary(
            args.base_url, cookie, args.project, mp4_path,
            target_id=shot_uuid, media_type="video", mime="video/mp4", name=f"{sid}_pika_480p.mp4"
        )
        vid_media_id = up_vid.get("media", {}).get("id") or up_vid.get("id")

        patch_shot = {
            "episodeId": args.episode,
            "id": shot_uuid,
            "duration": int(sp["duration"]),
            "videoPrompt": sp["prompt"],
            "dialogue": sp.get("dialogue", ""),
            "description": sp.get("description", ""),
            "assetNames": sp.get("asset_names", []),
        }
        if sp.get("keyframe_prompt"):
            patch_shot["imagePrompt"] = sp["keyframe_prompt"]
        if kf_media_id:
            patch_shot["imageId"] = kf_media_id
        if vid_media_id:
            patch_shot["videoId"] = vid_media_id

        api_json(args.base_url, cookie, "PATCH", f"/api/studio/projects/{args.project}", {"shot": patch_shot})
        uploaded.append({"id": sid, "shot_uuid": shot_uuid, "imageId": kf_media_id, "videoId": vid_media_id})
        print(f"[uploaded] {sid} -> shot={shot_uuid} img={kf_media_id} vid={vid_media_id}", flush=True)

    if args.merge_episode:
        merge_res = api_json(args.base_url, cookie, "POST", f"/api/studio/projects/{args.project}/episodes/{args.episode}/video", {})
        print("[episode-merge]", json.dumps(merge_res, ensure_ascii=False))


if __name__ == "__main__":
    main()
