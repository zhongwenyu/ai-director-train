#!/usr/bin/env python3
"""Prepare Real-Hit Gold Storyboard Pairs, Dev/Test Eval Sets, and Run Step 0 Judge Calibration.

All tasks execute concurrently across agy (gemini-4-carbon-low) and codex (gpt-6.1-sol / medium).
Strictly writes inside /home/zhongwenyu/project/ai-director-train.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import re
import sys
from pathlib import Path
from typing import Any

TRAIN_ROOT = Path("/home/zhongwenyu/project/ai-director-train")
CORPUS_SRC = Path("/home/zhongwenyu/project/ai-director-workstation/videos/红果AI短剧_800部_前50集/小说")
SKILL_DIR = TRAIN_ROOT / ".agents" / "skills" / "hit-storyboard"
GOLD_SB_DIR = TRAIN_ROOT / "corpus" / "storyboard_gold_pairs"
EVAL_SET_DIR = TRAIN_ROOT / "corpus" / "storyboard_eval_sets"
CALIB_DIR = TRAIN_ROOT / "judge" / "storyboard_calibration"

sys.path.insert(0, str(TRAIN_ROOT / "trainer"))
sys.path.insert(0, str(TRAIN_ROOT / "judge"))
sys.path.insert(0, str(SKILL_DIR / "scripts"))

import llm_clients as L  # noqa: E402
import storyboard_check as SBC  # noqa: E402
import storyboard_judge as SBJ  # noqa: E402

GOLD_TRAIN_ITEMS = [
    ("001", "train_001_ep001.md", "9:16 竖屏"),
    ("039", "train_039_ep001.md", "9:16 竖屏"),
    ("092", "train_092_ep001.md", "9:16 竖屏"),
]

ALIGN_REAL_HIT_PROMPT = """请将下方【红果真实爆款原片逆向逐镜实录】忠实整理为标准 14 列导演分镜表（严格保留原片真实的景别切换、机位角度、每一次推/拉/摇/跟拍运镜、物证特写与集尾定格，不要擅自改动原片分镜逻辑或台词！）。

要求：
1. 对照【提纯剧本】确保每句台词与关键动作一一对应，标题写 `# 第 1 集 ...`。
2. 每场开头写三行场头（场景与光影锚点、180°主轴线左A右B、本场时长与生成组数）。
3. 将同场连续子镜（1.5s-6.0s，0.5s精度）合成为 5-15 整数秒的生成组（组号为组首镜号，子镜时长之和精确等于组时长），每组结束后附一行 `> 【组 X-X-XX 末态与接缝】：...`。
4. 主动运镜按原片实拍动作写清触发、路径、速度与落点；固定镜简注固定意图。严格 14 列：`镜号 | 生成组 | 组时长 | 时长 | 景别 | 机位 | 运镜 | 画面与构图 | 动作三态（起始→执行→落定） | 表演与视线 | 台词（含同步／画外标注） | 声音与音效 | 资产绑定 | 备注`（单元格内禁出现 `|`）。直接输出 Markdown 正文：

### 【提纯剧本】
{screenplay_md}

### 【红果真实爆款原片逆向逐镜实录】
{raw_video_md}
"""

NAIVE_SB_PROMPT = """请把下面这集短剧剧本拆成 14 列 Markdown 分镜表（画幅：{aspect_ratio}）。
表头固定为：`镜号 | 生成组 | 组时长 | 时长 | 景别 | 机位 | 运镜 | 画面与构图 | 动作三态 | 表演与视线 | 台词 | 声音与音效 | 资产绑定 | 备注`（每场标题用 `## 1-1 ...`，同场连续镜头合成 5-15 整数秒生成组，组号填首镜号）。直接输出分镜表 Markdown 正文：

{screenplay_md}
"""


def extract_ep1(md_text: str) -> str:
    ms = list(re.finditer(r"^#\s*第\s*0*(\d+)\s*集", md_text, re.M))
    if not ms:
        return md_text.strip()
    end = ms[1].start() if len(ms) > 1 else len(md_text)
    return md_text[ms[0].start():end].strip()


def find_raw_ep1(drama_id: str) -> str:
    matches = sorted(CORPUS_SRC.glob(f"{drama_id}_*/第001章.md"))
    if not matches:
        raise FileNotFoundError(f"Missing raw chapter for {drama_id}")
    return matches[0].read_text(encoding="utf-8")


def build_eval_sets() -> None:
    EVAL_SET_DIR.mkdir(parents=True, exist_ok=True)
    # 4 diverse dev tracks from r03_v3 high-quality scripts (zero overlap with test or 2005_chongqing_hotpot)
    r03_dir = TRAIN_ROOT / "runs" / "rounds" / "r03_v3"
    dev_items = [
        ("dev_066", "都市商业情感", "9:16 竖屏", r03_dir / "dev_066" / "combined_1-5.md"),
        ("dev_067", "古装奇幻萌宝", "9:16 竖屏", r03_dir / "dev_067" / "combined_1-5.md"),
        ("dev_097", "九零年代逆袭", "9:16 竖屏", r03_dir / "dev_097" / "combined_1-5.md"),
        ("dev_098", "都市律政交锋", "9:16 竖屏", r03_dir / "dev_098" / "combined_1-5.md"),
    ]
    dev_list = []
    for sid, genre, ar, p in dev_items:
        ep1 = extract_ep1(p.read_text(encoding="utf-8"))
        dev_list.append({"eval_id": f"{sid}_ep01", "genre": genre, "aspect_ratio": ar, "screenplay": ep1})
    (EVAL_SET_DIR / "dev_episodes.json").write_text(
        json.dumps(dev_list, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # 3 unseen holdout test episodes from runs/showcase
    sc_dir = TRAIN_ROOT / "runs" / "showcase"
    test_items = [
        ("test_085", "都市清醒搞钱", "9:16 竖屏", sc_dir / "test_085" / "trained_skill" / "combined_1-5.md"),
        ("test_orig_01", "都市除夕家庭切割", "9:16 竖屏", sc_dir / "test_orig_01" / "trained_skill" / "combined_1-5_11-12.md"),
        ("test_orig_02", "八零年代供销社轻喜", "9:16 竖屏", sc_dir / "test_orig_02" / "trained_skill" / "combined_1-5.md"),
    ]
    test_list = []
    for sid, genre, ar, p in test_items:
        ep1 = extract_ep1(p.read_text(encoding="utf-8"))
        test_list.append({"eval_id": f"{sid}_ep01", "genre": genre, "aspect_ratio": ar, "screenplay": ep1})
    (EVAL_SET_DIR / "test_episodes.json").write_text(
        json.dumps(test_list, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"[prepare] Built {len(dev_list)} dev episodes and {len(test_list)} test episodes.")


def process_calibration_pair(did: str, slice_file: str, aspect_ratio: str) -> dict[str, Any]:
    GOLD_SB_DIR.mkdir(parents=True, exist_ok=True)
    CALIB_DIR.mkdir(parents=True, exist_ok=True)

    sp_md = extract_ep1((TRAIN_ROOT / "corpus" / "gold_slices" / slice_file).read_text(encoding="utf-8"))
    raw_vid = find_raw_ep1(did)

    gold_p = GOLD_SB_DIR / f"real_hit_{did}_ep01_sb.md"
    naive_p = CALIB_DIR / f"naive_{did}_ep01_sb.md"

    def _make_gold() -> str:
        if gold_p.is_file():
            return gold_p.read_text(encoding="utf-8")
        txt = L.call_agy(
            ALIGN_REAL_HIT_PROMPT.format(screenplay_md=sp_md, raw_video_md=raw_vid[:16000]),
            timeout=600,
            validator=lambda t: "| 1-1-01 |" in t or "|1-1-01|" in t.replace(" ", ""),
            out_path=gold_p,
        )
        return txt

    def _make_naive() -> str:
        if naive_p.is_file():
            return naive_p.read_text(encoding="utf-8")
        txt = L.call_agy(
            NAIVE_SB_PROMPT.format(aspect_ratio=aspect_ratio, screenplay_md=sp_md),
            timeout=600,
            validator=lambda t: "|" in t and len(t) >= 600,
            out_path=naive_p,
        )
        return txt

    with cf.ThreadPoolExecutor(max_workers=2) as pool:
        f_g = pool.submit(_make_gold)
        f_n = pool.submit(_make_naive)
        gold_sb = f_g.result()
        naive_sb = f_n.result()

    # Score both & run swapped double-blind PK concurrently via codex (gpt-6.1-sol / medium)
    gold_sc_p = CALIB_DIR / f"real_hit_{did}.score.json"
    naive_sc_p = CALIB_DIR / f"naive_{did}.score.json"
    pk_p = CALIB_DIR / f"pk_{did}.json"

    with cf.ThreadPoolExecutor(max_workers=3) as jpool:
        fg_sc = jpool.submit(
            lambda: json.loads(gold_sc_p.read_text(encoding="utf-8"))
            if gold_sc_p.is_file()
            else SBJ.score_storyboard(
                gold_sb,
                sp_md,
                stats_summary=SBC.format_summary_table(SBC.analyze_storyboard(gold_sb, screenplay_md=sp_md)),
                out_path=gold_sc_p,
            )
        )
        fn_sc = jpool.submit(
            lambda: json.loads(naive_sc_p.read_text(encoding="utf-8"))
            if naive_sc_p.is_file()
            else SBJ.score_storyboard(
                naive_sb,
                sp_md,
                stats_summary=SBC.format_summary_table(SBC.analyze_storyboard(naive_sb, screenplay_md=sp_md)),
                out_path=naive_sc_p,
            )
        )
        f_pk = jpool.submit(
            lambda: json.loads(pk_p.read_text(encoding="utf-8"))
            if pk_p.is_file()
            else SBJ.pairwise_compare_storyboards(
                "REAL_HIT_VIDEO",
                gold_sb,
                "NAIVE_ZEROSHOT",
                naive_sb,
                sp_md,
                swap_debias=True,
                out_path=pk_p,
            )
        )
        g_sc = fg_sc.result()
        n_sc = fn_sc.result()
        pk = f_pk.result()

    return {
        "drama_id": did,
        "real_hit_score": g_sc["total_score"],
        "naive_score": n_sc["total_score"],
        "real_cam_score": g_sc["dimensions"]["camera_movement_choreography"]["score"],
        "naive_cam_score": n_sc["dimensions"]["camera_movement_choreography"]["score"],
        "debiased_pk_winner": pk["winner_label"],
        "why_winner_wins": pk["why_winner_wins"],
    }


def main() -> None:
    build_eval_sets()
    ex_dir = SKILL_DIR / "examples"
    ex_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    with cf.ThreadPoolExecutor(max_workers=3) as pool:
        futs = [pool.submit(process_calibration_pair, did, sf, ar) for did, sf, ar in GOLD_TRAIN_ITEMS]
        for f in cf.as_completed(futs):
            r = f.result()
            rows.append(r)
            print("[calib]", json.dumps(r, ensure_ascii=False))

    rows.sort(key=lambda x: x["drama_id"])

    # Copy top clean real-hit gold storyboard into skill examples/
    for did in ("001", "039"):
        src = GOLD_SB_DIR / f"real_hit_{did}_ep01_sb.md"
        if src.is_file():
            (ex_dir / f"real_hit_{did}_ep01.md").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    wins = sum(1 for r in rows if r["debiased_pk_winner"] == "REAL_HIT_VIDEO")
    ties = sum(1 for r in rows if r["debiased_pk_winner"] == "TIE")
    losses = sum(1 for r in rows if r["debiased_pk_winner"] == "NAIVE_ZEROSHOT")

    md = [
        "# 分镜与运镜异族评委校准报告（Step 0 Storyboard Judge Calibration）",
        "",
        f"- **评审模型**：`codex (gpt-6.1-sol, effort=medium)`",
        f"- **正反换位双盲 PK 总战绩（真实红果原片实拍调度 vs 零样本 AI 分镜）**：**`{wins} 胜 {ties} 平 {losses} 负`**",
        "",
        "| 样本剧号 | 真爆款实拍分镜总分 (运镜分) | 零样本AI分镜总分 (运镜分) | 正反双盲PK胜方 | 核心判词摘要 |",
        "| :---: | ---: | ---: | :---: | --- |",
    ]
    for r in rows:
        md.append(
            f"| `{r['drama_id']}` | **{r['real_hit_score']}** (`{r['real_cam_score']}/25`) | "
            f"{r['naive_score']} (`{r['naive_cam_score']}/25`) | **{r['debiased_pk_winner']}** | "
            f"{r['why_winner_wins'][:110].replace(chr(10), ' ')}… |"
        )
    (CALIB_DIR / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (CALIB_DIR / "summary.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[calib] Done! W/T/L = {wins}/{ties}/{losses}. Saved {CALIB_DIR / 'report.md'}")


if __name__ == "__main__":
    main()
