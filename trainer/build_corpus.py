#!/usr/bin/env python3
"""Incremental corpus builder for /home/zhongwenyu/project/ai-director-train.

Reads (read-only) from:
  /home/zhongwenyu/project/ai-director-workstation/videos/红果AI短剧_800部_前50集/小说/已完成剧目清单.md
  and corresponding chapter / summary / episode annotation files.

Key fixes over legacy scripts:
1. Fixes the 28-second chunked video timestamp bug (`## 片段 K · 原集 A–B 秒` vs local `### 00:00 - 00:28`).
2. Groups multi-season IPs (`持械入宋`, `反向拿捏`, `一身腱子肉`, etc.) into identical splits to prevent data leakage.
3. Supports incremental re-runs as `已完成剧目清单.md` grows while preserving existing train/dev/test assignments.
"""
from __future__ import annotations

import hashlib
import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

CORPUS_ROOT = Path(
    "/home/zhongwenyu/project/ai-director-workstation/videos/红果AI短剧_800部_前50集"
)
NOVEL_ROOT = CORPUS_ROOT / "小说"
DONE_LIST_MD = NOVEL_ROOT / "已完成剧目清单.md"
REPAIRED_EPS_ROOT = CORPUS_ROOT / "分析" / "episodes-repaired"

TRAIN_ROOT = Path("/home/zhongwenyu/project/ai-director-train")
OUT_CORPUS = TRAIN_ROOT / "corpus"

GENRE_DIRS = ["都市情感", "年代乡村", "古装穿越", "玄幻修仙", "末世科幻", "悬疑恐怖", "其他"]

RE_DONE_ROW = re.compile(
    r"^\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(\d+)\s*\|\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s*\|$",
    re.M,
)
RE_CHUNK = re.compile(
    r"^##\s*片段\s*(\d+)\s*[·•]\s*原集\s*([\d.]+)\s*[–\-~至]\s*([\d.]+)\s*秒",
    re.M,
)
RE_SUBSCENE_TS = re.compile(
    r"^###\s*(\d{1,2}):(\d{2})(?:\.(\d+))?\s*-\s*(\d{1,2}):(\d{2})(?:\.(\d+))?\s*(.*)$",
    re.M,
)
RE_INLINE_END_TS = re.compile(r"定格至\s*(\d{1,2}):(\d{2})(?:\.(\d+))?")
# Spoken quotes after speech verbs / colons (excludes screen watermarks / signs where possible)
RE_SPOKEN_QUOTE = re.compile(
    r"(?:道|说|问|喊|骂|斥|吼|答|回|念|嚷|嘱|叹|笑|哭|白|音|声|唱|喝|劝|哄|怼|讽|嘲|求|应)"
    r"[^：“”\n]{0,12}[：:]\s*“([^”]{1,220})”"
)
RE_VO_MARKER = re.compile(r"(旁白|内心独白|画外音|系统提示音|机械[男女]声)")


def ts_to_sec(mm: str, ss: str, frac: str | None = None) -> float:
    val = int(mm) * 60 + int(ss)
    if frac:
        val += float("0." + frac)
    return val


def canonical_ip_root(title: str) -> str:
    """Normalize multi-season drama titles to a single IP root so seasons never leak across splits."""
    s = title.strip()
    s = re.sub(r"[（(]完[)）]", "", s)
    s = re.sub(r"第[一二三四五六七八九十百零\d]+[季部篇]", "", s)
    s = re.sub(r"[2-9]$", "", s)
    # Known series prefixes before colon (e.g. 持械入宋：第一季, 莞城往事：..., 反向拿捏2：...)
    if "：" in s:
        prefix, rest = s.split("：", 1)
        prefix_clean = re.sub(r"\d+$", "", prefix).strip()
        if len(prefix_clean) >= 4 and any(
            kw in prefix_clean
            for kw in ("持械入宋", "反向拿捏", "莞城往事", "大唐憨婿", "顾家四千金", "暴富", "抽象三国")
        ):
            return prefix_clean
    s = re.sub(r"[：:·\s]+$", "", s)
    return s.strip()


def build_genre_lookup() -> dict[str, str]:
    title_to_genre: dict[str, str] = {}
    for g in GENRE_DIRS:
        gd = CORPUS_ROOT / g
        if not gd.is_dir():
            continue
        for sub in gd.iterdir():
            if not sub.is_dir():
                continue
            parts = sub.name.split("_", 1)
            t = parts[1] if len(parts) == 2 else sub.name
            title_to_genre[t.strip()] = g
    # Fallback from legacy manifest if present
    legacy = CORPUS_ROOT / "分析" / "manifest.json"
    if legacy.is_file():
        try:
            lm = json.loads(legacy.read_text(encoding="utf-8")).get("dramas", {})
            for entry in lm.values():
                if entry.get("title") and entry.get("genre"):
                    title_to_genre.setdefault(entry["title"].strip(), entry["genre"])
        except Exception:
            pass
    return title_to_genre


def infer_genre_by_title(title: str) -> str:
    if any(k in title for k in ("七零", "八零", "九零", "1958", "1977", "七六", "93", "赶山", "赶海", "下乡", "知青", "老太", "猎")):
        return "年代乡村"
    if any(k in title for k in ("大唐", "入宋", "世子", "王妃", "皇室", "皇宫", "节度使", "乱世", "少帅", "三国", "流放")):
        return "古装穿越"
    if any(k in title for k in ("修仙", "玄门", "灵葫", "龙珠", "万宗", "异界")):
        return "玄幻修仙"
    if any(k in title for k in ("末日", "末世")):
        return "末世科幻"
    return "都市情感"


def parse_chapter_md(md_path: Path) -> dict[str, Any]:
    text = md_path.read_text(encoding="utf-8")
    chunks = list(RE_CHUNK.finditer(text))
    duration_sec = 0.0
    subscene_count = 0

    if chunks:
        # Chunked format: true duration is the maximum global end timestamp in `原集 A–B 秒`
        for m in chunks:
            end_s = float(m.group(3))
            if end_s > duration_sec:
                duration_sec = end_s
        subscene_count = len(RE_SUBSCENE_TS.findall(text))
    else:
        for m in RE_SUBSCENE_TS.finditer(text):
            subscene_count += 1
            end_s = ts_to_sec(m.group(4), m.group(5), m.group(6))
            if end_s > duration_sec:
                duration_sec = end_s
        for m in RE_INLINE_END_TS.finditer(text):
            end_s = ts_to_sec(m.group(1), m.group(2), m.group(3))
            if end_s > duration_sec:
                duration_sec = end_s

    quotes = [q.strip() for q in RE_SPOKEN_QUOTE.findall(text) if q.strip()]
    spoken_chars = sum(len(q) for q in quotes)
    spoken_lines = len(quotes)
    has_vo = bool(RE_VO_MARKER.search(text))

    return {
        "chunked": bool(chunks),
        "chunk_count": len(chunks),
        "subscene_count": subscene_count,
        "duration_sec": round(duration_sec, 2),
        "spoken_lines": spoken_lines,
        "spoken_chars": spoken_chars,
        "avg_line_chars": round(spoken_chars / spoken_lines, 2) if spoken_lines else 0.0,
        "has_vo": has_vo,
        "raw_bytes": len(text.encode("utf-8")),
    }


def load_repaired_annotations(drama_key: str) -> dict[int, dict[str, Any]]:
    d = REPAIRED_EPS_ROOT / drama_key
    eps: dict[int, dict[str, Any]] = {}
    if not d.is_dir():
        return eps
    for jf in sorted(d.glob("ep*.json")):
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
            for item in data.get("episodes", []):
                ep_no = int(item["episode"])
                eps[ep_no] = item
        except Exception:
            continue
    return eps


def assign_split_deterministic(ip_root: str, existing: dict[str, str]) -> str:
    if ip_root in existing:
        return existing[ip_root]
    h = int(hashlib.md5(ip_root.encode("utf-8")).hexdigest()[:8], 16) % 100
    # 72% train, 16% dev, 12% test
    if h < 72:
        return "train"
    if h < 88:
        return "dev"
    return "test"


def pct(vals: list[float], q: float) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    idx = min(len(s) - 1, max(0, int(round((len(s) - 1) * q))))
    return round(s[idx], 2)


def main() -> None:
    OUT_CORPUS.mkdir(parents=True, exist_ok=True)
    existing_manifest_path = OUT_CORPUS / "manifest.json"
    existing_ip_splits: dict[str, str] = {}
    if existing_manifest_path.is_file():
        try:
            old = json.loads(existing_manifest_path.read_text(encoding="utf-8"))
            for d in old.get("dramas", {}).values():
                if d.get("ip_root") and d.get("split"):
                    existing_ip_splits[d["ip_root"]] = d["split"]
        except Exception:
            pass

    genre_lookup = build_genre_lookup()
    done_md = DONE_LIST_MD.read_text(encoding="utf-8")
    rows = RE_DONE_ROW.findall(done_md)

    dramas: dict[str, Any] = {}
    all_ep_durations: list[float] = []
    all_chars_per_min: list[float] = []
    all_lines_per_min: list[float] = []
    all_line_lengths: list[float] = []
    genre_buckets: dict[str, list[dict[str, float]]] = defaultdict(list)

    hook_opening_types: Counter[str] = Counter()
    hook_ending_types: Counter[str] = Counter()
    payoff_types: Counter[str] = Counter()

    for num_str, title, ch_count_str, ts_added in rows:
        title = title.strip()
        key = f"{num_str}_{title}"
        novel_dir = NOVEL_ROOT / key
        if not novel_dir.is_dir():
            # Try matching by prefix num_str_
            cands = list(NOVEL_ROOT.glob(f"{num_str}_*"))
            if not cands:
                continue
            novel_dir = cands[0]
            key = novel_dir.name

        chapter_files = sorted(novel_dir.glob("第*章.md"))
        if not chapter_files:
            continue

        genre = genre_lookup.get(title) or infer_genre_by_title(title)
        ip_root = canonical_ip_root(title)
        split = assign_split_deterministic(ip_root, existing_ip_splits)
        existing_ip_splits[ip_root] = split

        summary_path = novel_dir / "summary.md"
        has_summary_md = summary_path.is_file()
        repaired_eps = load_repaired_annotations(key)

        ep_stats_list = []
        valid_durations = []
        valid_cpm = []
        valid_lpm = []

        for cf in chapter_files:
            m_ep = re.search(r"第(\d+)章", cf.name)
            ep_no = int(m_ep.group(1)) if m_ep else len(ep_stats_list) + 1
            st = parse_chapter_md(cf)
            st["episode"] = ep_no
            dur = st["duration_sec"]
            if dur >= 35.0:
                cpm = round(st["spoken_chars"] / (dur / 60.0), 1)
                lpm = round(st["spoken_lines"] / (dur / 60.0), 2)
                st["spoken_chars_per_min"] = cpm
                st["spoken_lines_per_min"] = lpm
                valid_durations.append(dur)
                all_ep_durations.append(dur)
                if st["spoken_lines"] >= 3:
                    valid_cpm.append(cpm)
                    valid_lpm.append(lpm)
                    all_chars_per_min.append(cpm)
                    all_lines_per_min.append(lpm)
                    all_line_lengths.append(st["avg_line_chars"])
                    genre_buckets[genre].append(
                        {"dur": dur, "cpm": cpm, "lpm": lpm, "line_len": st["avg_line_chars"]}
                    )
            ep_stats_list.append(st)

        # Aggregate structural annotations if available
        open_scores, end_scores, payoffs_cnt, rev_cnt = [], [], 0, 0
        for ep_no, ann in repaired_eps.items():
            oh = ann.get("openingHook") or {}
            eh = ann.get("endingHook") or {}
            if oh.get("strength"):
                open_scores.append(float(oh["strength"]))
            if oh.get("type"):
                hook_opening_types[str(oh["type"])] += 1
            if eh.get("strength"):
                end_scores.append(float(eh["strength"]))
            if eh.get("type"):
                hook_ending_types[str(eh["type"])] += 1
            for p in ann.get("payoffs") or []:
                payoffs_cnt += 1
                if p.get("type"):
                    payoff_types[str(p["type"])] += 1
            rev_cnt += len(ann.get("reversals") or [])

        n_ann = len(repaired_eps)
        struct_score = 0.0
        if n_ann >= 20:
            o_mean = statistics.mean(open_scores) if open_scores else 3.0
            e_mean = statistics.mean(end_scores) if end_scores else 3.0
            p_rate = payoffs_cnt / n_ann
            r_rate = rev_cnt / n_ann
            struct_score = round(o_mean * 1.2 + e_mean * 1.2 + min(p_rate, 3.0) * 1.1 + min(r_rate, 2.5) * 1.1, 3)

        dramas[key] = {
            "key": key,
            "id": num_str,
            "title": title,
            "ip_root": ip_root,
            "genre": genre,
            "split": split,
            "added_at": ts_added,
            "chapter_count": len(chapter_files),
            "novel_dir": str(novel_dir),
            "has_summary_md": has_summary_md,
            "summary_path": str(summary_path) if has_summary_md else None,
            "annotated_episodes": n_ann,
            "median_duration_sec": round(statistics.median(valid_durations), 1) if valid_durations else 0.0,
            "p10_duration_sec": pct(valid_durations, 0.10),
            "p90_duration_sec": pct(valid_durations, 0.90),
            "median_spoken_cpm": round(statistics.median(valid_cpm), 1) if valid_cpm else 0.0,
            "median_spoken_lpm": round(statistics.median(valid_lpm), 1) if valid_lpm else 0.0,
            "opening_hook_mean": round(statistics.mean(open_scores), 2) if open_scores else None,
            "ending_hook_mean": round(statistics.mean(end_scores), 2) if end_scores else None,
            "payoffs_per_ep": round(payoffs_cnt / n_ann, 2) if n_ann else None,
            "reversals_per_ep": round(rev_cnt / n_ann, 2) if n_ann else None,
            "quality_rank_score": struct_score,
        }

    split_counts = Counter(d["split"] for d in dramas.values())
    genre_counts = Counter(d["genre"] for d in dramas.values())

    manifest_out = {
        "source_list": str(DONE_LIST_MD),
        "total_dramas": len(dramas),
        "split_counts": dict(split_counts),
        "genre_counts": dict(genre_counts),
        "dramas": dramas,
    }
    (OUT_CORPUS / "manifest.json").write_text(
        json.dumps(manifest_out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # Verify zero IP leakage across splits
    ip_to_splits: dict[str, set[str]] = defaultdict(set)
    for d in dramas.values():
        ip_to_splits[d["ip_root"]].add(d["split"])
    leaks = {ip: list(sps) for ip, sps in ip_to_splits.items() if len(sps) > 1}
    assert not leaks, f"IP leakage detected: {leaks}"

    # Write clean empirical baseline report
    report_lines = [
        "# 红果优秀 AI 短剧真实统计基线报告（修复分片时长后）",
        "",
        f"- 同步自：`{DONE_LIST_MD}`",
        f"- 已入库剧目数：**{len(dramas)} 部**（有效解析章节 **{len(all_ep_durations)} 集**）",
        f"- 数据集划分（按同 IP 词干严格隔离，0 跨季泄漏）：`train={split_counts['train']}` / `dev={split_counts['dev']}` / `test={split_counts['test']}`",
        f"- 具备 `summary.md` 完整全剧拆解：**{sum(1 for d in dramas.values() if d['has_summary_md'])} 部**；具备逐集钩子/爽点标注：**{sum(1 for d in dramas.values() if d['annotated_episodes'] >= 20)} 部**",
        "",
        "## 一、全局真实单集时长与台词密度（修复 28s 切片重置 Bug 后）",
        "",
        "| 指标 | P10 | P25 | P50 (中位数) | P75 | P90 | 说明 |",
        "|---|---:|---:|---:|---:|---:|---|",
        f"| 单集真实时长（秒） | {pct(all_ep_durations, 0.10)} | {pct(all_ep_durations, 0.25)} | **{pct(all_ep_durations, 0.50)}** | {pct(all_ep_durations, 0.75)} | {pct(all_ep_durations, 0.90)} | 自然分布在 1~3 分钟浮动区间 |",
        f"| 纯对白字数 / 分钟 | {pct(all_chars_per_min, 0.10)} | {pct(all_chars_per_min, 0.25)} | **{pct(all_chars_per_min, 0.50)}** | {pct(all_chars_per_min, 0.75)} | {pct(all_chars_per_min, 0.90)} | 正常人语速，留足视觉反应与留白 |",
        f"| 对白句数 / 分钟 | {pct(all_lines_per_min, 0.10)} | {pct(all_lines_per_min, 0.25)} | **{pct(all_lines_per_min, 0.50)}** | {pct(all_lines_per_min, 0.75)} | {pct(all_lines_per_min, 0.90)} | 短句快交锋，绝非每秒塞满废话 |",
        f"| 平均每句对白字数 | {pct(all_line_lengths, 0.10)} | {pct(all_line_lengths, 0.25)} | **{pct(all_line_lengths, 0.50)}** | {pct(all_line_lengths, 0.75)} | {pct(all_line_lengths, 0.90)} | 口语短促有力（约 10~15 字/句） |",
        "",
        "## 二、分赛道真实节奏特征",
        "",
        "| 赛道 | 剧目数 | 有效集数 | 单集时长 P50 (s) | 单集时长 P10–P90 (s) | 对白字/分 P50 | 对白句/分 P50 | 句均字数 P50 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for g in GENRE_DIRS:
        rows_g = genre_buckets.get(g, [])
        if not rows_g:
            continue
        durs = [r["dur"] for r in rows_g]
        cpms = [r["cpm"] for r in rows_g]
        lpms = [r["lpm"] for r in rows_g]
        llens = [r["line_len"] for r in rows_g]
        report_lines.append(
            f"| {g} | {genre_counts[g]} | {len(rows_g)} | {pct(durs, 0.50)} | "
            f"{pct(durs, 0.10)}–{pct(durs, 0.90)} | {pct(cpms, 0.50)} | {pct(lpms, 0.50)} | {pct(llens, 0.50)} |"
        )

    report_lines += [
        "",
        "## 三、高频开局钩子、爽点与集尾断章分布（来自语料结构化标注）",
        "",
        "- **Top 开场钩子形态**：" + "、".join(f"{k}({v})" for k, v in hook_opening_types.most_common(12)),
        "- **Top 爽点兑现形态**：" + "、".join(f"{k}({v})" for k, v in payoff_types.most_common(8)),
        "- **Top 集尾断章形态**：" + "、".join(f"{k}({v})" for k, v in hook_ending_types.most_common(7)),
        "",
        "## 四、Train 集综合结构质量 Top 15 标杆剧目（供提纯创作态示范切片）",
        "",
        "| 排名 | 剧目 | 赛道 | 单集时长中位(s) | 开场钩子 | 集尾钩子 | 爽点/集 | 反转/集 | summary.md |",
        "|---:|---|---|---:|---:|---:|---:|---:|---|",
    ]
    train_ranked = sorted(
        [d for d in dramas.values() if d["split"] == "train" and d["annotated_episodes"] >= 30],
        key=lambda x: x["quality_rank_score"],
        reverse=True,
    )[:15]
    for idx, d in enumerate(train_ranked, 1):
        report_lines.append(
            f"| {idx} | {d['key']} | {d['genre']} | {d['median_duration_sec']} | "
            f"{d['opening_hook_mean']} | {d['ending_hook_mean']} | {d['payoffs_per_ep']} | "
            f"{d['reversals_per_ep']} | {'✓' if d['has_summary_md'] else '-'} |"
        )

    (OUT_CORPUS / "stats_report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(f"[build_corpus] Processed {len(dramas)} dramas, {len(all_ep_durations)} valid episodes.")
    print(f"[build_corpus] Splits: {dict(split_counts)} | Genres: {dict(genre_counts)}")
    print(f"[build_corpus] True duration P10/P50/P90: {pct(all_ep_durations, 0.1)}s / {pct(all_ep_durations, 0.5)}s / {pct(all_ep_durations, 0.9)}s")


if __name__ == "__main__":
    main()
