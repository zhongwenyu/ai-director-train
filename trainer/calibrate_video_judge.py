#!/home/zhongwenyu/data/anaconda3/bin/python3
"""
Step 0: Multimodal Video Arena Judge Calibration (`trainer/calibrate_video_judge.py`).

Verifies that `judge/video_arena_judge.py` (`gemini-4-argon` tool-stripped order-swapped blind judge
+ neural `Silero-VAD` & OpenCV motion probes) achieves 100% directional accuracy (`3/3` swapped pairs,
zero positional inversions) on real ground-truth positive vs negative `.mp4` pairs BEFORE starting
closed-loop skill evolution.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

TRAIN_ROOT = Path("/home/zhongwenyu/project/ai-director-train")
BENCH_ROOT = TRAIN_ROOT / "corpus" / "video_bench"
CALIB_DIR = TRAIN_ROOT / "judge" / "calibration_video_v1"

if str(TRAIN_ROOT / "judge") not in sys.path:
    sys.path.insert(0, str(TRAIN_ROOT / "judge"))
import video_arena_judge as VAJ  # noqa: E402


def _norm_512p(src: Path, dst: Path, ar: str = "16:9") -> Path:
    if dst.is_file() and dst.stat().st_size > 10000:
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    tw, th = (896, 512) if ar == "16:9" else (512, 896)
    vf = f"scale={tw}:{th}:force_original_aspect_ratio=decrease,pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2,fps=24"
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error", "-i", str(src),
            "-vf", vf,
            "-af", "aresample=48000,loudnorm=I=-16:TP=-1.5:LRA=11",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k",
            str(dst),
        ],
        check=True,
    )
    return dst


def _make_static_talking_degraded(gold_mp4: Path, first_frame_png: Path, dst_mp4: Path) -> Path:
    """Create a realistic failure-mode negative sample (static single-frame talking slideshow with tail cut)."""
    if dst_mp4.is_file() and dst_mp4.stat().st_size > 10000:
        return dst_mp4
    dst_mp4.parent.mkdir(parents=True, exist_ok=True)
    pr = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_format", "-of", "json", str(gold_mp4)], text=True))
    dur = max(5.0, float(pr["format"]["duration"]) - 0.8)  # Also truncates last 0.8s
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(gold_mp4), "-frames:v", "1", str(first_frame_png)],
        check=True,
    )
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-loop", "1", "-t", f"{dur:.2f}", "-i", str(first_frame_png),
            "-t", f"{dur:.2f}", "-i", str(gold_mp4),
            "-map", "0:v", "-map", "1:a",
            "-vf", "fps=24,format=yuv420p",
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "160k",
            str(dst_mp4),
        ],
        check=True,
    )
    return dst_mp4


def main() -> int:
    CALIB_DIR.mkdir(parents=True, exist_ok=True)
    pairs: List[Dict[str, Any]] = []

    # Pair 1: Real Native 14-step AddGuide Complete Video vs Pika 6-step Smeared/Plastic Video (9:16)
    art_dir = Path("/home/zhongwenyu/.gemini/antigravity-cli/brain/36f0d3c1-8c89-4df4-bc17-b435fe795b2d")
    lab_assets = Path("/home/zhongwenyu/project/ai-director-workstation/runtime/ep01-02-opt-lab-20261122/clean_assets")
    pos1 = _norm_512p(art_dir / "Prod_2-1-04_768p_13s_final.mp4", CALIB_DIR / "p1_pos_native14.mp4", "9:16")
    neg1 = _norm_512p(art_dir / "M1_768p_pika_6step.mp4", CALIB_DIR / "p1_neg_pika6.mp4", "9:16")
    spec1 = {
        "case_id": "calib_01_native_vs_pika",
        "aspect_ratio": "9:16",
        "setting_summary": "正午阳光斜照的重庆老街旧木门框与青石台阶",
        "dramatic_goal": "女方居高临下让男方服软交出配方，男方冷静解下腕上黑色塑料电子表按入女方掌心当场提分手，反打女方震惊破防质问",
        "characters": [
            {"role_id": "CHR_1", "display_name": "年轻男子", "neutral_visual_bio": "穿深藏青拉链夹克、背军绿帆布书包的20岁青年"},
            {"role_id": "CHR_2", "display_name": "年轻女子", "neutral_visual_bio": "穿米白小香风两件套短裙的20岁女子"},
        ],
        "props": [{"prop_id": "PRP_1", "description": "黑色塑料电子表"}],
        "dialogue_turns": [
            {"speaker_id": "CHR_2", "mode": "spoken", "text": "差不多行了。服个软把方子交出来，刚才的事我翻篇。"},
            {"speaker_id": "CHR_1", "mode": "spoken", "text": "东西收好。咱俩完了。"},
            {"speaker_id": "CHR_2", "mode": "spoken", "text": "你说什么？叶寻，你敢提分手？！"},
        ],
    }
    refs1 = [
        ("CHR_1", lab_assets / "ye_2005_bare_front_1k.png"),
        ("CHR_2", lab_assets / "lin_2005_front_1k.png"),
    ]
    pairs.append({"name": "calib_01_native_vs_pika", "spec": spec1, "refs": refs1, "pos": pos1, "neg": neg1})

    # Pair 2: Clean Multi-Cut Acting (`3-2-23` 99/100) vs Whip-Pan Subject Clone Defect (`3-2-08_r1`)
    takes_ep03 = Path("/home/zhongwenyu/project/ai-director-workstation/runtime/ep01-02-opt-lab-20261122/takes_ep03")
    pos2 = _norm_512p(takes_ep03 / "3-2-11/video.mp4", CALIB_DIR / "p2_pos_clean_axis.mp4", "9:16")
    neg2 = _norm_512p(takes_ep03 / "3-2-08/video_r1.mp4", CALIB_DIR / "p2_neg_whip_clone.mp4", "9:16")
    spec2 = {
        "case_id": "calib_02_axis_vs_clone",
        "aspect_ratio": "9:16",
        "setting_summary": "晴朗上午的青石餐饮老街两侧店门对峙",
        "dramatic_goal": "东侧男女隔街嚣张挑衅炫耀，西侧青年沉稳跨街正反打回应，要求轴线稳定、严禁人物分身克隆或失控甩镜",
        "characters": [
            {"role_id": "CHR_1", "display_name": "藏青夹克青年", "neutral_visual_bio": "深藏青夹克黑短发青年"},
            {"role_id": "CHR_2", "display_name": "米白套裙女子", "neutral_visual_bio": "米白小香风套裙年轻女子"},
        ],
        "props": [],
        "dialogue_turns": [
            {"speaker_id": "CHR_2", "mode": "spoken", "text": "隔街挑衅对白"},
        ],
    }
    pairs.append({"name": "calib_02_axis_vs_clone", "spec": spec2, "refs": refs1, "pos": pos2, "neg": neg2})

    # Pair 3: Real Benchmark High-Naturalism Multi-Cut (`dev_01_workplace_rival` gold) vs Static Truncated Failure
    dev01_spec_p = BENCH_ROOT / "dev/dev_01_workplace_rival/beat_spec.json"
    if dev01_spec_p.is_file():
        s3 = json.loads(dev01_spec_p.read_text(encoding="utf-8"))
        gold3 = Path(s3["gold_sealed_mp4"])
        neg3 = _make_static_talking_degraded(gold3, CALIB_DIR / "p3_f0.png", CALIB_DIR / "p3_neg_static_trunc.mp4")
        refs3 = [(c["role_id"], Path(s3["asset_files"][c["role_id"]])) for c in s3["characters"] if c["role_id"] in s3["asset_files"]]
        pairs.append({"name": "calib_03_live_microacting_vs_static", "spec": s3, "refs": refs3, "pos": gold3, "neg": neg3})

    def _eval_calib_pair(item: Dict[str, Any]) -> Dict[str, Any]:
        print(f"[calibrating] {item['name']} (swapped dual-blind)...", flush=True)
        res = VAJ.judge_pair_swapped(item["spec"], item["refs"], item["pos"], item["neg"], effort="medium")
        ok = res["outcome"] == "cand_win" and res["score_delta"] > 3.0
        print(
            f"  -> {item['name']}: outcome={res['outcome']} pos={res['cand_score']} neg={res['champ_score']} "
            f"delta={res['score_delta']:+.2f} votes=({res['vote_pass1']},{res['vote_pass2_swapped']}) [{'PASS' if ok else 'FAIL'}]",
            flush=True,
        )
        return {"pair": item["name"], "passed": ok, "detail": res}

    with cf.ThreadPoolExecutor(max_workers=len(pairs)) as ex:
        results = list(ex.map(_eval_calib_pair, pairs))
    passed = sum(1 for r in results if r["passed"])

    report = {
        "total_pairs": len(pairs),
        "passed_pairs": passed,
        "accuracy": round(passed / max(1, len(pairs)), 4),
        "calibration_passed": passed == len(pairs),
        "results": results,
    }
    out_json = CALIB_DIR / "calibration_report.json"
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nCalibration Summary: {passed}/{len(pairs)} ({report['accuracy']*100:.1f}%) -> {out_json}")
    return 0 if report["calibration_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
