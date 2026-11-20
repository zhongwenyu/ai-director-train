#!/usr/bin/env python3
"""Step 0: Judge Calibration — Verify codex (gpt-6.1-sol, medium) distinguishes
Real Hongguo Hit Scripts from Mechanical Rubric-Gamed AI Scripts & Naive Zero-Shot AI Scripts.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import sys
from pathlib import Path

TRAIN_ROOT = Path("/home/zhongwenyu/project/ai-director-train")
sys.path.insert(0, str(TRAIN_ROOT / "trainer"))
sys.path.insert(0, str(TRAIN_ROOT / "judge"))

import judge_runner as J  # noqa: E402
import llm_clients as L  # noqa: E402

GOLD_DIR = TRAIN_ROOT / "corpus" / "gold_slices"
CALIB_DIR = TRAIN_ROOT / "judge" / "calibration"
LEGACY_R27 = Path(
    "/home/zhongwenyu/project/ai-director-workstation/videos/红果AI短剧_800部_前50集/分析/p3/rounds/r27c-v11f"
)


def make_naive_zeroshot_001() -> Path:
    out_p = CALIB_DIR / "naive_001_ep001.md"
    if out_p.is_file():
        return out_p
    prompt = (
        "请根据以下创意写第1集短剧剧本（约2分钟，标准剧本格式：# 第 1 集 标题、## 1-1 场头、人物、△动作、角色对白、【本集完】）：\n"
        "创意：百亿集团董事长顾承川为了完成爷爷遗愿回农村履行娃娃亲，特意穿旧衣服装穷上门，想让势利眼的林家母女主动退婚；"
        "林家正在办寿宴，偏心疼爱小女儿林雪晴，苛待同父异母的大女儿林小满。顾承川上门提亲被当成叫花子嫌弃退婚，刚转身走到院门口却被林父喊住。"
    )
    L.call_agy(prompt, timeout=240, out_path=out_p)
    return out_p


def make_naive_zeroshot_039() -> Path:
    out_p = CALIB_DIR / "naive_039_ep001.md"
    if out_p.is_file():
        return out_p
    prompt = (
        "请根据以下创意写第1集短剧剧本（约2分钟，标准剧本格式：# 第 1 集 标题、## 1-1 场头、人物、△动作、角色对白、【本集完】）：\n"
        "创意：隐瞒集团幕后掌舵人身份的丈夫开车送妻子一家去参加高端宴会，半路上岳母和小舅子为了讨好妻子的富二代男闺蜜，竟嫌丈夫占座丢人，在高速路口把丈夫硬生生赶下车。丈夫心冷之下不再隐忍，下车后一通电话开始收回给妻子一家的豪车、合作与特权。"
    )
    L.call_agy(prompt, timeout=240, out_path=out_p)
    return out_p


def main() -> None:
    CALIB_DIR.mkdir(parents=True, exist_ok=True)
    naive_001 = make_naive_zeroshot_001()
    naive_039 = make_naive_zeroshot_039()

    pairs = [
        (
            "001_装穷提亲娶到全家嫌弃的她_ep01",
            GOLD_DIR / "train_001_ep001.md",
            naive_001,
            "naive_zeroshot",
        ),
        (
            "039_被赶下车后我收回一切_ep01",
            GOLD_DIR / "train_039_ep001.md",
            naive_039,
            "naive_zeroshot",
        ),
        (
            "070_前妻追悔前夫已登云巅_ep01",
            GOLD_DIR / "train_070_ep001.md",
            LEGACY_R27 / "070_前妻追悔前夫已登云巅" / "ep001.md",
            "legacy_r27",
        ),
        (
            "092_一身腱子肉乱世做谋臣_ep01",
            GOLD_DIR / "train_092_ep001.md",
            LEGACY_R27 / "092_一身腱子肉，乱世做谋臣" / "ep001.md",
            "legacy_r27",
        ),
    ]

    results = []

    def eval_one_pair(item):
        tag, real_p, neg_p, neg_kind = item
        real_txt = real_p.read_text(encoding="utf-8")
        neg_txt = neg_p.read_text(encoding="utf-8")

        real_score = J.score_episodes(
            real_txt, out_path=CALIB_DIR / f"{tag}_real.score.json"
        )
        neg_score = J.score_episodes(
            neg_txt, out_path=CALIB_DIR / f"{tag}_{neg_kind}.score.json"
        )
        pk = J.pairwise_compare(
            "REAL_HIT",
            real_txt,
            neg_kind.upper(),
            neg_txt,
            topic_context=f"同剧目第1集盲测对比（{tag}）",
            swap_debias=True,
            out_path=CALIB_DIR / f"{tag}_pk.json",
        )
        return {
            "case": tag,
            "neg_kind": neg_kind,
            "real_score": real_score["total_score"],
            "neg_score": neg_score["total_score"],
            "score_gap": round(real_score["total_score"] - neg_score["total_score"], 2),
            "pk_winner": pk["winner_label"],
            "swap_consistent": pk.get("swap_check", {}).get("consistent"),
            "real_dialogue_score": real_score["dimensions"]["human_dialogue_and_persona"]["score"],
            "neg_dialogue_score": neg_score["dimensions"]["human_dialogue_and_persona"]["score"],
            "neg_ai_smells": len(neg_score.get("ai_smell_flags", [])),
            "why_winner_wins": pk["why_winner_wins"],
            "why_loser_loses": pk["why_loser_loses"],
        }

    with cf.ThreadPoolExecutor(max_workers=2) as ex:
        futs = [ex.submit(eval_one_pair, it) for it in pairs]
        for f in cf.as_completed(futs):
            r = f.result()
            results.append(r)
            print(
                f"[calib] {r['case']}: REAL={r['real_score']} vs {r['neg_kind']}={r['neg_score']} "
                f"(gap={r['score_gap']:+.1f}) | PK winner={r['pk_winner']} (consistent={r['swap_consistent']})"
            )

    results.sort(key=lambda x: x["case"])
    win_count = sum(1 for r in results if r["pk_winner"] == "REAL_HIT")
    score_wins = sum(1 for r in results if r["real_score"] > r["neg_score"])
    summary = {
        "n_pairs": len(results),
        "score_accuracy": round(score_wins / len(results), 3),
        "debiased_pk_win_rate": round(win_count / len(results), 3),
        "mean_real_score": round(sum(r["real_score"] for r in results) / len(results), 2),
        "mean_neg_score": round(sum(r["neg_score"] for r in results) / len(results), 2),
        "cases": results,
    }
    (CALIB_DIR / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    md = [
        "# Step 0：评委校准报告（`codex gpt-6.1-sol / medium` 盲测鉴别力验证）",
        "",
        f"- 测试对数：**{len(results)} 组同剧第 1 集盲测**（真红果爆款清洗稿 vs 旧版 r27c 八股刷分稿 / 零样本直出稿）",
        f"- 绝对总分准确率：**{score_wins}/{len(results)} ({summary['score_accuracy']*100:.0f}%)**（真爆款均分 **{summary['mean_real_score']}** vs 负例均分 **{summary['mean_neg_score']}**）",
        f"- 正反双盲交换顺序 PK 胜率：**{win_count}/{len(results)} ({summary['debiased_pk_win_rate']*100:.0f}%)**",
        "",
        "| 剧目 | 负例类型 | 真爆款总分 | 负例总分 | 分差 | 活人台词分 (真/负) | 负例检出AI病灶数 | 双盲交换PK胜者 |",
        "|---|---|---:|---:|---:|---|---:|---|",
    ]
    for r in results:
        md.append(
            f"| {r['case']} | {r['neg_kind']} | **{r['real_score']}** | {r['neg_score']} | "
            f"{r['score_gap']:+.1f} | {r['real_dialogue_score']} / {r['neg_dialogue_score']} | "
            f"{r['neg_ai_smells']} | **{r['pk_winner']}** |"
        )
    md.append("\n## 评委典型判词摘录\n")
    for r in results:
        md.append(f"### {r['case']}")
        md.append(f"- **真爆款胜因**：{r['why_winner_wins']}")
        md.append(f"- **负例败因**：{r['why_loser_loses']}\n")

    (CALIB_DIR / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"[calib] Done! Report saved to {CALIB_DIR / 'report.md'}")


if __name__ == "__main__":
    main()
