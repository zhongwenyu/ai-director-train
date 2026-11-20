#!/usr/bin/env python3
"""Holdout Blind Evaluation for `hit-storyboard` on Unseen Test Episodes.

Compares Final Champion `hit-storyboard` (`agy gemini-4-carbon-low`) against:
1. Naive Zero-Shot `agy (gemini-4-carbon-low)` (no skill) on all 3 unseen test episodes
2. Claude Code's `drama-s4-shotlist` (`prompts/generate.md` + `references/shotlist-rules.md`) on all 3 unseen test episodes!
All generation and swapped double-blind `codex (gpt-6.1-sol / medium)` judging run in parallel!
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import sys
from pathlib import Path
from typing import Any

TRAIN_ROOT = Path("/home/zhongwenyu/project/ai-director-train")
LIVE_SKILL_DIR = TRAIN_ROOT / ".agents" / "skills" / "hit-storyboard"
SHOWCASE_DIR = TRAIN_ROOT / "runs" / "storyboard_showcase"
TEST_SET_PATH = TRAIN_ROOT / "corpus" / "storyboard_eval_sets" / "test_episodes.json"
CLAUDE_S4_DIR = Path("/home/zhongwenyu/project/ai-director-workstation/skills/drama-s4-shotlist")

sys.path.insert(0, str(TRAIN_ROOT / "trainer"))
sys.path.insert(0, str(TRAIN_ROOT / "judge"))
sys.path.insert(0, str(LIVE_SKILL_DIR / "scripts"))

import llm_clients as L  # noqa: E402
import storyboard_check as SBC  # noqa: E402
import storyboard_judge as SBJ  # noqa: E402
import write_storyboard as WSB  # noqa: E402

NAIVE_PROMPT = """请将下面这集短剧剧本拆成 14 列 Markdown 分镜表（画幅：{aspect_ratio}）。
表头：`镜号 | 生成组 | 组时长 | 时长 | 景别 | 机位 | 运镜 | 画面与构图 | 动作三态 | 表演与视线 | 台词 | 声音与音效 | 资产绑定 | 备注`（同场连续镜头合成 5-15 整数秒生成组，组号填首镜号）。直接输出分镜表 Markdown 正文：

{screenplay}
"""


def _cached_json(path: Path, fn):
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return fn()


def eval_one_test_ep(item: dict[str, Any]) -> dict[str, Any]:
    eid = item["eval_id"]
    sdir = SHOWCASE_DIR / eid
    sdir.mkdir(parents=True, exist_ok=True)
    done_p = sdir / "item_summary.json"
    if done_p.is_file():
        return json.loads(done_p.read_text(encoding="utf-8"))
    sp_md = item["screenplay"]
    ar = item["aspect_ratio"]

    naive_p = sdir / "naive_zeroshot_sb.md"
    claude_s4_p = sdir / "claude_s4_skill_sb.md"

    def _gen_trained() -> tuple[str, dict[str, Any]]:
        p, rep = WSB.generate_one_episode_storyboard(
            1, sp_md, sdir / "trained_skill", skill_dir=LIVE_SKILL_DIR, aspect_ratio=ar, force=False
        )
        return p.read_text(encoding="utf-8"), rep

    def _gen_naive() -> str:
        if not naive_p.is_file():
            L.call_agy(
                NAIVE_PROMPT.format(aspect_ratio=ar, screenplay=sp_md),
                timeout=600,
                validator=lambda t: "|" in t and len(t) >= 600,
                out_path=naive_p,
            )
        return naive_p.read_text(encoding="utf-8")

    def _gen_claude_s4() -> str:
        if not claude_s4_p.is_file():
            s4_prompt = (CLAUDE_S4_DIR / "prompts" / "generate.md").read_text(encoding="utf-8")
            s4_rules = (CLAUDE_S4_DIR / "references" / "shotlist-rules.md").read_text(encoding="utf-8")
            full_p = "\n\n".join(
                [
                    s4_prompt,
                    "# 镜头表规则\n\n" + s4_rules,
                    f"# 补充要求\n本批为第 1 集。画幅 {ar}。",
                    "# 输入：定稿剧本\n\n" + sp_md,
                ]
            )
            L.call_agy(
                full_p,
                timeout=600,
                validator=lambda t: "|" in t and len(t) >= 600,
                out_path=claude_s4_p,
            )
        return claude_s4_p.read_text(encoding="utf-8")

    # 1. Generate all 3 storyboards in parallel!
    with cf.ThreadPoolExecutor(max_workers=3) as gpool:
        ft = gpool.submit(_gen_trained)
        fn = gpool.submit(_gen_naive)
        fc = gpool.submit(_gen_claude_s4)
        trained_sb, trained_rep = ft.result()
        naive_sb = fn.result()
        claude_sb = fc.result()

    # 2. Run ALL scores + swapped double-blind PKs in parallel via codex (gpt-6.1-sol / medium)!
    with cf.ThreadPoolExecutor(max_workers=5) as jpool:
        f_sc_tr = jpool.submit(
            _cached_json,
            sdir / "trained.score.json",
            lambda: SBJ.score_storyboard(
                trained_sb,
                sp_md,
                stats_summary=SBC.format_summary_table(trained_rep),
                out_path=sdir / "trained.score.json",
            ),
        )
        f_sc_nv = jpool.submit(
            _cached_json,
            sdir / "naive.score.json",
            lambda: SBJ.score_storyboard(naive_sb, sp_md, out_path=sdir / "naive.score.json"),
        )
        f_sc_cl = jpool.submit(
            _cached_json,
            sdir / "claude_s4.score.json",
            lambda: SBJ.score_storyboard(claude_sb, sp_md, out_path=sdir / "claude_s4.score.json"),
        )
        f_pk_nv = jpool.submit(
            _cached_json,
            sdir / "pk_vs_naive.json",
            lambda: SBJ.pairwise_compare_storyboards(
                "HIT_STORYBOARD",
                trained_sb,
                "NAIVE_ZEROSHOT",
                naive_sb,
                sp_md,
                swap_debias=True,
                out_path=sdir / "pk_vs_naive.json",
            ),
        )
        f_pk_cl = jpool.submit(
            _cached_json,
            sdir / "pk_vs_claude_s4.json",
            lambda: SBJ.pairwise_compare_storyboards(
                "HIT_STORYBOARD",
                trained_sb,
                "CLAUDE_S4_SHOTLIST",
                claude_sb,
                sp_md,
                swap_debias=True,
                out_path=sdir / "pk_vs_claude_s4.json",
            ),
        )
        sc_tr = f_sc_tr.result()
        sc_nv = f_sc_nv.result()
        sc_cl = f_sc_cl.result()
        pk_nv = f_pk_nv.result()
        pk_cl = f_pk_cl.result()

    ep_stat = trained_rep["episodes"][0] if trained_rep["episodes"] else {}
    res_obj = {
        "eval_id": eid,
        "genre": item["genre"],
        "trained_score": sc_tr["total_score"],
        "naive_score": sc_nv["total_score"],
        "claude_s4_score": sc_cl["total_score"],
        "trained_cam_score": sc_tr["dimensions"]["camera_movement_choreography"]["score"],
        "naive_cam_score": sc_nv["dimensions"]["camera_movement_choreography"]["score"],
        "claude_s4_cam_score": sc_cl["dimensions"]["camera_movement_choreography"]["score"],
        "pk_vs_naive": pk_nv["winner_label"],
        "pk_vs_claude_s4": pk_cl["winner_label"],
        "active_cam_pct": ep_stat.get("active_cam_pct"),
        "shots": ep_stat.get("shots"),
        "groups": ep_stat.get("groups"),
        "why_beats_claude_s4": pk_cl["why_winner_wins"][:240],
    }
    done_p.write_text(json.dumps(res_obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return res_obj


def main() -> None:
    SHOWCASE_DIR.mkdir(parents=True, exist_ok=True)
    test_items = json.loads(TEST_SET_PATH.read_text(encoding="utf-8"))

    results = []
    with cf.ThreadPoolExecutor(max_workers=3) as pool:
        futs = [pool.submit(eval_one_test_ep, it) for it in test_items]
        for f in cf.as_completed(futs):
            r = f.result()
            results.append(r)
            print("[final_eval_sb]", json.dumps(r, ensure_ascii=False))

    results.sort(key=lambda x: x["eval_id"])
    (SHOWCASE_DIR / "final_summary.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"[final_eval_sb] Saved {SHOWCASE_DIR / 'final_summary.json'}")


if __name__ == "__main__":
    main()
