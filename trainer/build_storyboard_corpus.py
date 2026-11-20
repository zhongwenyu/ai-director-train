#!/usr/bin/env python3
"""Empirical Shot & Camera Movement Corpus Miner for Hongguo Hit AI Short Dramas.

Reads `/home/zhongwenyu/project/ai-director-workstation/videos/红果AI短剧_800部_前50集/小说/已完成剧目清单.md`
(read-only) and mines:
1. True Cuts Per Minute & Average Shot Length (ASL) across 7,000+ episodes
2. Shot Scale distribution (全景/远景, 中景, 中近景, 近景, 过肩OTS, 特写)
3. Camera Angle distribution (俯拍/高机位, 仰拍/低机位, 过肩, 侧面, 背面, 正面/平视)
4. Active Camera Movement taxonomy & frequency (推近, 拉远, 摇摄, 升降/上下移, 跟拍/横移, 环绕, 手持震动, 转焦, 集尾定格)
5. Preserves strict IP-stem `train / dev / test` isolation (0 cross-season leakage)

Writes ONLY inside `/home/zhongwenyu/project/ai-director-train/corpus/`.
"""
from __future__ import annotations

import hashlib
import json
import re
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

CORPUS_SRC = Path("/home/zhongwenyu/project/ai-director-workstation/videos/红果AI短剧_800部_前50集/小说")
TRAIN_ROOT = Path("/home/zhongwenyu/project/ai-director-train")
CORPUS_OUT = TRAIN_ROOT / "corpus"

RE_CHUNK_SPAN = re.compile(r"^##\s*片段\s*\d+\s*·\s*原集\s*(\d+(?:\.\d+)?)[–\-~](\d+(?:\.\d+)?)\s*秒", re.M)
RE_TIME_RANGE = re.compile(
    r"^###\s*(\d{1,2}):(\d{2})(?:\.(\d+))?\s*-\s*(\d{1,2}):(\d{2})(?:\.(\d+))?",
    re.M,
)

# Explicit cut / shot-start markers in gemini-4-argon reverse-engineered video descriptions
RE_CUT_SPLIT = re.compile(
    r"(?:镜头|画面)(?:随即|紧接着|最后|再次|略微|迅速)?(?:切至|切回|切换至|切换为|转至)"
    r"|(?<![a-zA-Z0-9])(?:经短暂黑场)?(?:切至|切回)(?=.{0,16}(?:全景|远景|中景|中近景|近景|特写|机位|视角|镜头|画面|车内|户外|街道|院))"
)

MOVEMENT_PATTERNS: dict[str, re.Pattern[str]] = {
    "push_in": re.compile(r"(?:缓慢|略微|快速|猛地|逐渐)?(?:前推|推近|拉近|推进|推至)"),
    "pull_out": re.compile(r"(?:缓慢|略微|快速|逐渐)?(?:拉远|后拉|后退拉出|拉出至)"),
    "pan_tilt": re.compile(r"(?:左摇|右摇|上摇|下摇|摇向|横摇|摇摄|镜头(?:向左|向右|向上|向下)摇)"),
    "pedestal_shift": re.compile(r"镜头(?:缓慢|逐渐)?(?:上移|下移|升起|下降|下沉)"),
    "track_truck": re.compile(r"(?:跟拍|跟随镜头|横向跟|横移|平移|伴随.*移动拍摄|镜头跟随)"),
    "arc_orbit": re.compile(r"(?:环绕|绕着.*旋转拍摄|弧线移动)"),
    "handheld_shake": re.compile(r"(?:手持|镜头剧烈晃动|画面震动|轻微晃动|震颤)"),
    "rack_focus": re.compile(r"(?:焦点(?:从|转|切|移)|虚化切换|转焦|前景虚化后景清晰)"),
}

SCALE_PATTERNS: dict[str, re.Pattern[str]] = {
    "wide_establishing": re.compile(r"(?:大全景|大远景|远景|全景)"),
    "medium": re.compile(r"(?:全身中景|双人中景|三人中景|侧面中景|背面中景|车内.*中景|中景)"),
    "medium_closeup": re.compile(r"中近景"),
    "over_shoulder": re.compile(r"过肩(?:正拍|反打)?(?:近景|中近景|中景|视角)?"),
    "closeup": re.compile(r"(?<!中)(?<!过肩)(?<!过肩正拍)近景"),
    "extreme_closeup": re.compile(r"(?:大特写|面部特写|手部特写|俯拍特写|特写)"),
}

ANGLE_PATTERNS: dict[str, re.Pattern[str]] = {
    "high_overhead": re.compile(r"(?:高机位|高空俯拍|俯拍|顶视)"),
    "low_upward": re.compile(r"(?:低机位|仰拍|仰视视角)"),
    "over_shoulder": re.compile(r"过肩"),
    "profile_side": re.compile(r"侧面"),
    "back_rear": re.compile(r"(?:背面|背影)"),
    "pov": re.compile(r"(?:主观视角|第一人称视角|POV)"),
}

RE_FREEZE_END = re.compile(r"(?:画面定格|定格在|定格至|未完待续)")
RE_VO_CUE = re.compile(r"(?:旁白|内心独白|画外音)")


def normalize_ip_stem(title: str) -> str:
    s = re.sub(r"^\d+_", "", title.strip())
    s = re.sub(r"(?:第[一二三四五六七八九十\d]+[季部]|[\(（]?[上下一二三四五12345][部季篇]?[\)）]?)$", "", s)
    return s.strip() or title.strip()


def assign_split(ip_stem: str, existing_map: dict[str, str]) -> str:
    if ip_stem in existing_map:
        return existing_map[ip_stem]
    h = int(hashlib.md5(ip_stem.encode("utf-8")).hexdigest()[:8], 16) % 100
    if h < 74:
        return "train"
    if h < 89:
        return "dev"
    return "test"


def compute_episode_duration(md_text: str) -> float:
    chunks = RE_CHUNK_SPAN.findall(md_text)
    if chunks:
        return max(float(end) for _, end in chunks)
    # No chunk headers -> single continuous timeline
    max_t = 0.0
    for m in RE_TIME_RANGE.finditer(md_text):
        em, es, ems = int(m.group(4)), int(m.group(5)), m.group(6)
        end_sec = em * 60 + es + (float("0." + ems) if ems else 0.0)
        if end_sec > max_t:
            max_t = end_sec
    return max_t


def analyze_chapter(md_path: Path) -> dict[str, Any] | None:
    txt = md_path.read_text(encoding="utf-8", errors="ignore")
    if len(txt.strip()) < 200:
        return None
    dur = compute_episode_duration(txt)
    if dur < 20.0 or dur > 600.0:
        return None

    # Split into scene blocks (`### ...`), then split each block by explicit cut markers
    blocks = re.split(r"(?m)^###\s+[^\n]+\n", txt)
    scene_blocks = [b.strip() for b in blocks[1:] if b.strip()] if len(blocks) > 1 else [txt]

    shot_segments: list[str] = []
    for blk in scene_blocks:
        parts = [p.strip() for p in RE_CUT_SPLIT.split(blk) if len(p.strip()) >= 12]
        if parts:
            shot_segments.extend(parts)

    n_shots = len(shot_segments)
    if n_shots < 4:
        return None

    move_counts: Counter[str] = Counter()
    scale_counts: Counter[str] = Counter()
    angle_counts: Counter[str] = Counter()
    active_move_shots = 0

    for seg in shot_segments:
        seg_moved = False
        for k, pat in MOVEMENT_PATTERNS.items():
            if pat.search(seg):
                move_counts[k] += 1
                seg_moved = True
        if seg_moved:
            active_move_shots += 1

        for k, pat in SCALE_PATTERNS.items():
            if pat.search(seg):
                scale_counts[k] += 1
        for k, pat in ANGLE_PATTERNS.items():
            if pat.search(seg):
                angle_counts[k] += 1

    asl = round(dur / n_shots, 2)
    cuts_per_min = round(n_shots / (dur / 60.0), 2)
    active_cam_ratio = round(active_move_shots / n_shots, 4)

    return {
        "duration_sec": round(dur, 2),
        "n_scene_blocks": len(scene_blocks),
        "n_shots": n_shots,
        "asl_sec": asl,
        "cuts_per_min": cuts_per_min,
        "active_move_shots": active_move_shots,
        "active_cam_ratio": active_cam_ratio,
        "has_freeze_ending": bool(RE_FREEZE_END.search(txt[-600:])),
        "vo_mentions": len(RE_VO_CUE.findall(txt)),
        "move_counts": dict(move_counts),
        "scale_counts": dict(scale_counts),
        "angle_counts": dict(angle_counts),
    }


def pct_quantiles(vals: list[float]) -> dict[str, float]:
    if not vals:
        return {"p10": 0.0, "p25": 0.0, "p50": 0.0, "p75": 0.0, "p90": 0.0, "mean": 0.0}
    s = sorted(vals)
    n = len(s)

    def q(p: float) -> float:
        idx = min(n - 1, max(0, int(round(p * (n - 1)))))
        return round(s[idx], 2)

    return {
        "p10": q(0.10),
        "p25": q(0.25),
        "p50": q(0.50),
        "p75": q(0.75),
        "p90": q(0.90),
        "mean": round(statistics.mean(s), 2),
    }


def main() -> None:
    CORPUS_OUT.mkdir(parents=True, exist_ok=True)
    existing_ip_split: dict[str, str] = {}
    prev_manifest_p = CORPUS_OUT / "manifest.json"
    if prev_manifest_p.is_file():
        prev = json.loads(prev_manifest_p.read_text(encoding="utf-8"))
        prev_dramas = prev.get("dramas", [])
        if isinstance(prev_dramas, dict):
            prev_dramas = list(prev_dramas.values())
        for d in prev_dramas:
            if isinstance(d, dict):
                ip = d.get("ip_root") or normalize_ip_stem(d.get("folder", ""))
                if ip and d.get("split"):
                    existing_ip_split[ip] = d["split"]

    drama_dirs = sorted(
        [p for p in CORPUS_SRC.iterdir() if p.is_dir() and re.match(r"^\d{3}_", p.name)]
    )

    dramas_meta: list[dict[str, Any]] = []
    all_durs: list[float] = []
    all_shots: list[float] = []
    all_asls: list[float] = []
    all_cpm: list[float] = []
    all_cam_ratios: list[float] = []
    tot_moves: Counter[str] = Counter()
    tot_scales: Counter[str] = Counter()
    tot_angles: Counter[str] = Counter()
    freeze_end_eps = 0
    total_valid_eps = 0
    split_drama_counts: Counter[str] = Counter()

    for ddir in drama_dirs:
        title = re.sub(r"^\d{3}_", "", ddir.name)
        ip_stem = normalize_ip_stem(title)
        sp = assign_split(ip_stem, existing_ip_split)
        existing_ip_split[ip_stem] = sp

        ch_files = sorted(ddir.glob("第*章.md"))
        ep_stats = []
        for cf in ch_files:
            st = analyze_chapter(cf)
            if st is None:
                continue
            ep_stats.append(st)
            total_valid_eps += 1
            all_durs.append(st["duration_sec"])
            all_shots.append(float(st["n_shots"]))
            all_asls.append(st["asl_sec"])
            all_cpm.append(st["cuts_per_min"])
            all_cam_ratios.append(st["active_cam_ratio"] * 100.0)
            if st["has_freeze_ending"]:
                freeze_end_eps += 1
            tot_moves.update(st["move_counts"])
            tot_scales.update(st["scale_counts"])
            tot_angles.update(st["angle_counts"])

        if not ep_stats:
            continue

        split_drama_counts[sp] += 1
        dramas_meta.append(
            {
                "drama_id": ddir.name[:3],
                "folder": ddir.name,
                "title": title,
                "ip_root": ip_stem,
                "split": sp,
                "valid_episodes": len(ep_stats),
                "mean_duration_sec": round(statistics.mean(x["duration_sec"] for x in ep_stats), 1),
                "mean_shots": round(statistics.mean(x["n_shots"] for x in ep_stats), 1),
                "mean_asl_sec": round(statistics.mean(x["asl_sec"] for x in ep_stats), 2),
                "mean_active_cam_pct": round(
                    statistics.mean(x["active_cam_ratio"] * 100.0 for x in ep_stats), 1
                ),
            }
        )

    # Verify zero IP leakage
    ip_to_splits: dict[str, set[str]] = {}
    for d in dramas_meta:
        ip_to_splits.setdefault(d["ip_root"], set()).add(d["split"])
    leaks = {k: sorted(v) for k, v in ip_to_splits.items() if len(v) > 1}
    assert not leaks, f"IP leakage detected: {leaks}"

    tot_scale_hits = sum(tot_scales.values()) or 1
    tot_move_hits = sum(tot_moves.values()) or 1
    tot_angle_hits = sum(tot_angles.values()) or 1

    summary = {
        "total_dramas": len(dramas_meta),
        "total_valid_episodes": total_valid_eps,
        "split_dramas": dict(split_drama_counts),
        "ip_leakage_count": len(leaks),
        "duration_sec": pct_quantiles(all_durs),
        "shots_per_episode": pct_quantiles(all_shots),
        "asl_sec": pct_quantiles(all_asls),
        "cuts_per_min": pct_quantiles(all_cpm),
        "active_camera_pct_per_ep": pct_quantiles(all_cam_ratios),
        "freeze_ending_rate_pct": round(freeze_end_eps * 100.0 / max(1, total_valid_eps), 1),
        "shot_scale_share_pct": {
            k: round(v * 100.0 / tot_scale_hits, 2) for k, v in tot_scales.most_common()
        },
        "camera_movement_share_pct": {
            k: round(v * 100.0 / tot_move_hits, 2) for k, v in tot_moves.most_common()
        },
        "camera_angle_share_pct": {
            k: round(v * 100.0 / tot_angle_hits, 2) for k, v in tot_angles.most_common()
        },
        "dramas": dramas_meta,
    }

    out_json = CORPUS_OUT / "storyboard_manifest.json"
    out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md_lines = [
        "# 红果爆款 AI 短剧逆向分镜与运镜实证基线报告",
        "",
        f"- **覆盖规模**：共 **{summary['total_dramas']} 部爆款短剧**、**{summary['total_valid_episodes']} 集有效分镜逆向样本**",
        f"- **防泄漏划分（按同 IP 词干绑定）**：`train={split_drama_counts['train']}` / `dev={split_drama_counts['dev']}` / `test={split_drama_counts['test']}`（跨季/上下部泄漏数 = `0`）",
        "",
        "## 一、核心剪辑密度与单镜时长分布（实证真值）",
        "",
        "| 指标 | P10 | P25 | P50（中位数） | P75 | P90 | 均值 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| 单集总时长 (秒) | {summary['duration_sec']['p10']} | {summary['duration_sec']['p25']} | **{summary['duration_sec']['p50']}** | {summary['duration_sec']['p75']} | {summary['duration_sec']['p90']} | {summary['duration_sec']['mean']} |",
        f"| 单集剪辑镜头数 (镜/集) | {summary['shots_per_episode']['p10']} | {summary['shots_per_episode']['p25']} | **{summary['shots_per_episode']['p50']}** | {summary['shots_per_episode']['p75']} | {summary['shots_per_episode']['p90']} | {summary['shots_per_episode']['mean']} |",
        f"| 平均单镜时长 ASL (秒/镜) | {summary['asl_sec']['p10']} | {summary['asl_sec']['p25']} | **{summary['asl_sec']['p50']}** | {summary['asl_sec']['p75']} | {summary['asl_sec']['p90']} | {summary['asl_sec']['mean']} |",
        f"| 每分钟切镜频次 (镜/分) | {summary['cuts_per_min']['p10']} | {summary['cuts_per_min']['p25']} | **{summary['cuts_per_min']['p50']}** | {summary['cuts_per_min']['p75']} | {summary['cuts_per_min']['p90']} | {summary['cuts_per_min']['mean']} |",
        f"| 主动运镜占全集镜头比 (%) | {summary['active_camera_pct_per_ep']['p10']}% | {summary['active_camera_pct_per_ep']['p25']}% | **{summary['active_camera_pct_per_ep']['p50']}%** | {summary['active_camera_pct_per_ep']['p75']}% | {summary['active_camera_pct_per_ep']['p90']}% | {summary['active_camera_pct_per_ep']['mean']}% |",
        "",
        f"- **集尾显式定格/悬停断章率**：`{summary['freeze_ending_rate_pct']}%`",
        "",
        "## 二、景别结构占比（Shot Scale Mix）",
        "",
        "| 景别类型 | 占比 | 实证导演规律 |",
        "| --- | ---: | --- |",
    ]
    scale_notes = {
        "closeup": "近景（竖屏/横屏工作主力景别，承载交锋口型与眼神压迫）",
        "medium": "中景/双人中景（交代肢体动作、持物交接与两人位置关系）",
        "extreme_closeup": "特写/大特写（证据文件、手部细节、情绪破防微表情与钩子峰值）",
        "medium_closeup": "中近景（兼顾胸口手势与面部反应）",
        "wide_establishing": "全景/远景（严格克制，仅用于场首空间建立、车队/院落气势或孤立收尾）",
        "over_shoulder": "过肩镜头 OTS（建立180°轴线纵深与强弱对峙压迫感）",
    }
    for k, pct in summary["shot_scale_share_pct"].items():
        md_lines.append(f"| `{k}` | **{pct}%** | {scale_notes.get(k, '')} |")

    md_lines += [
        "",
        "## 三、主动运镜类型占比（Active Camera Movement Mix）",
        "",
        "| 运镜类别 | 占全部主动运镜比 | 典型叙事触发点 |",
        "| --- | ---: | --- |",
    ]
    move_notes = {
        "push_in": "前推/缓推（权力加压、底牌逼近、情绪决断收束——绝对主力运镜！）",
        "track_truck": "跟拍/横移（人物决绝离场背影、闯入空间、关系并行与揭开遮挡）",
        "pull_out": "拉远/后拉（暴露孤立处境、揭示围观全局或拉开阶级/关系距离）",
        "pan_tilt": "摇摄（视线引导画外新变数入场、扫视长桌/人群反应）",
        "pedestal_shift": "升降/上下移（从手部物证上移至冷峻脸庞，或高空下沉建立压迫）",
        "handheld_shake": "手持/短促震颤（仅用于受击、车祸、突发失控峰值，绝不滥用）",
        "rack_focus": "转焦（前后景信息差切换：前景端茶不动声色→后景偷换证据清晰）",
        "arc_orbit": "环绕（高光亮相、对峙局势翻转，极度克制以防AI背景崩坏）",
    }
    for k, pct in summary["camera_movement_share_pct"].items():
        md_lines.append(f"| `{k}` | **{pct}%** | {move_notes.get(k, '')} |")

    md_lines += [
        "",
        "## 四、特殊机位角度分布（Non-Neutral Angles）",
        "",
        "| 机位角度 | 占显式特殊角度比 |",
        "| --- | ---: |",
    ]
    for k, pct in summary["camera_angle_share_pct"].items():
        md_lines.append(f"| `{k}` | **{pct}%** |")

    out_md = CORPUS_OUT / "storyboard_stats_report.md"
    out_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(f"[build_storyboard_corpus] Processed {summary['total_dramas']} dramas, {total_valid_eps} episodes.")
    print(f"[build_storyboard_corpus] Saved {out_json} and {out_md}")


if __name__ == "__main__":
    main()
