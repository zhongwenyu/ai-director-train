#!/usr/bin/env python3
"""Final Holdout Evaluation & Showcase Generator on Unseen Test Ideas.

Evaluates the final evolved `hit-short-drama` skill (`agy gemini-4-carbon-low`) on:
1. `test_085` (《男人哪有火锅香，我吃火锅不烧心》) — Head-to-head blind PK against:
   - Naive Zero-Shot `agy (gemini-4-carbon-low)` (no skill)
   - Claude Code's latest `r28` output (`085/ep001-c0.md`)!
2. `test_orig_01` (《年夜饭桌上的百亿拆迁款》 — 100% unseen original urban creative brief)
3. `test_orig_02` (《听懂万物心声后，我在八零供销社躺赢》 — 100% unseen original 1980s creative brief)
   including both Golden Opening (Ep 1-5) AND First Paywall Climax (Ep 11-12) to verify long-arc continuity!
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import sys
from pathlib import Path
from typing import Any

TRAIN_ROOT = Path("/home/zhongwenyu/project/ai-director-train")
LIVE_SKILL_DIR = TRAIN_ROOT / ".agents" / "skills" / "hit-short-drama"
SHOWCASE_DIR = TRAIN_ROOT / "runs" / "showcase"
SEEDS_DIR = TRAIN_ROOT / "corpus" / "seeds"

sys.path.insert(0, str(TRAIN_ROOT / "trainer"))
sys.path.insert(0, str(TRAIN_ROOT / "judge"))
sys.path.insert(0, str(LIVE_SKILL_DIR / "scripts"))

import judge_runner as J  # noqa: E402
import llm_clients as L  # noqa: E402
import script_check as SC  # noqa: E402
import write_drama as WD  # noqa: E402

CLAUDE_R28_085 = Path(
    "/home/zhongwenyu/project/ai-director-workstation/videos/红果AI短剧_800部_前50集/分析/p3/rounds/r28-select/085_男人哪有火锅香，我吃火锅不烧心/ep001-c0.md"
)

NAIVE_PROMPT = """请根据下面这段短剧简单创意，先写一份简短大纲，然后直接写出第 1～5 集的标准分集剧本（单集约2分钟，格式使用 `# 第 N 集 标题`、`## N-1 内/外 场景 日/夜`、`△ 动作`、`角色：台词`、每集末尾写 `【本集完】`）。直接输出第 1～5 集剧本正文：

创意：
{idea}
"""


def extract_ep1(script_md: str) -> str:
    matches = list(SC.RE_EP_HEADER.finditer(script_md))
    if not matches:
        return script_md
    end = matches[1].start() if len(matches) > 1 else len(script_md)
    return script_md[matches[0].start():end].strip()


def _cached_json(path: Path, fn):
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return fn()


def eval_showcase_seed(seed: dict[str, Any], episodes_spec: str = "1-5") -> dict[str, Any]:
    sid = seed["seed_id"]
    sdir = SHOWCASE_DIR / sid
    sdir.mkdir(parents=True, exist_ok=True)

    naive_p = sdir / "naive_zeroshot_ep1_5.md"

    def _gen_naive() -> str:
        if not naive_p.is_file():
            L.call_agy(
                NAIVE_PROMPT.format(idea=seed["idea"]),
                timeout=600,
                validator=lambda t: "# 第 1 集" in t and "【本集完】" in t,
                out_path=naive_p,
            )
        return naive_p.read_text(encoding="utf-8")

    # 1 & 2. Run Trained Skill Pipeline (`agy`) AND Naive Zero-Shot Baseline (`agy`) in parallel!
    with cf.ThreadPoolExecutor(max_workers=2) as gen_pool:
        fut_trained = gen_pool.submit(
            WD.run_pipeline,
            seed["idea"],
            sdir / "trained_skill",
            episodes_spec=episodes_spec,
            batch_size=3,
            skill_dir=LIVE_SKILL_DIR,
            force=False,
        )
        fut_naive = gen_pool.submit(_gen_naive)
        gen_res = fut_trained.result()
        naive_txt = fut_naive.result()

    outline_txt = Path(gen_res["outline_path"]).read_text(encoding="utf-8")
    trained_txt = Path(gen_res["combined_script_path"]).read_text(encoding="utf-8")
    phys_rep = SC.analyze_script(trained_txt)

    # Slice first 5 episodes for fair head-to-head comparison against Naive Ep 1-5
    trained_ep1_5_p = sdir / "trained_skill" / "combined_1-5.md"
    if not trained_ep1_5_p.is_file():
        ms = list(SC.RE_EP_HEADER.finditer(trained_txt))
        cut = ms[5].start() if len(ms) > 5 else len(trained_txt)
        trained_ep1_5 = trained_txt[:cut].strip()
    else:
        trained_ep1_5 = trained_ep1_5_p.read_text(encoding="utf-8")

    # 3. Run ALL `codex` judge & swapped blind PK tasks concurrently!
    with cf.ThreadPoolExecutor(max_workers=6) as judge_pool:
        f_out = judge_pool.submit(
            _cached_json,
            sdir / "trained_outline.score.json",
            lambda: J.score_outline(
                seed["idea"], outline_txt, out_path=sdir / "trained_outline.score.json"
            ),
        )
        f_tr = judge_pool.submit(
            _cached_json,
            sdir / "trained_episodes.score.json",
            lambda: J.score_episodes(
                trained_txt,
                idea_text=seed["idea"],
                outline_excerpt=outline_txt[:5000],
                stats_summary=SC.format_summary_table(phys_rep),
                out_path=sdir / "trained_episodes.score.json",
            ),
        )
        f_nv = judge_pool.submit(
            _cached_json,
            sdir / "naive_episodes.score.json",
            lambda: J.score_episodes(
                naive_txt,
                idea_text=seed["idea"],
                out_path=sdir / "naive_episodes.score.json",
            ),
        )
        f_pk_nv = judge_pool.submit(
            _cached_json,
            sdir / "pk_vs_naive.json",
            lambda: J.pairwise_compare(
                "TRAINED_SKILL",
                trained_ep1_5,
                "NAIVE_ZEROSHOT",
                naive_txt,
                topic_context=f"盲测对比（创意：{seed['idea'][:240]}…）",
                swap_debias=True,
                out_path=sdir / "pk_vs_naive.json",
            ),
        )

        f_cl_sc = f_our_ep1_sc = f_pk_cl = None
        if sid == "test_085" and CLAUDE_R28_085.is_file():
            claude_ep1 = CLAUDE_R28_085.read_text(encoding="utf-8")
            our_ep1 = extract_ep1(trained_ep1_5)
            f_cl_sc = judge_pool.submit(
                _cached_json,
                sdir / "claude_r28_ep1.score.json",
                lambda: J.score_episodes(
                    claude_ep1,
                    idea_text=seed["idea"],
                    out_path=sdir / "claude_r28_ep1.score.json",
                ),
            )
            f_our_ep1_sc = judge_pool.submit(
                _cached_json,
                sdir / "trained_ep1.score.json",
                lambda: J.score_episodes(
                    our_ep1,
                    idea_text=seed["idea"],
                    out_path=sdir / "trained_ep1.score.json",
                ),
            )
            f_pk_cl = judge_pool.submit(
                _cached_json,
                sdir / "pk_vs_claude_r28.json",
                lambda: J.pairwise_compare(
                    "TRAINED_SKILL",
                    our_ep1,
                    "CLAUDE_CODE_R28",
                    claude_ep1,
                    topic_context=f"《男人哪有火锅香，我吃火锅不烧心》第 1 集双盲对比（创意：{seed['idea'][:240]}…）",
                    swap_debias=True,
                    out_path=sdir / "pk_vs_claude_r28.json",
                ),
            )

        out_score = f_out.result()
        trained_score = f_tr.result()
        naive_score = f_nv.result()
        pk_naive = f_pk_nv.result()

    result: dict[str, Any] = {
        "seed_id": sid,
        "title_hint": seed["title_hint"],
        "genre": seed["genre"],
        "planned_total_episodes": out_score.get("planned_total_episodes"),
        "outline_score": out_score["total_score"],
        "trained_episode_score": trained_score["total_score"],
        "naive_episode_score": naive_score["total_score"],
        "score_gain_over_naive": round(
            trained_score["total_score"] - naive_score["total_score"], 2
        ),
        "pk_vs_naive_winner": pk_naive["winner_label"],
        "mean_duration_sec": phys_rep["mean_est_duration_sec"],
        "trained_ai_smells": len(trained_score.get("ai_smell_flags", [])),
        "naive_ai_smells": len(naive_score.get("ai_smell_flags", [])),
    }

    if f_cl_sc and f_our_ep1_sc and f_pk_cl:
        claude_ep1_score = f_cl_sc.result()
        our_ep1_score = f_our_ep1_sc.result()
        pk_claude = f_pk_cl.result()
        result["vs_claude_r28"] = {
            "our_ep1_score": our_ep1_score["total_score"],
            "claude_r28_ep1_score": claude_ep1_score["total_score"],
            "our_dialogue_score": our_ep1_score["dimensions"]["human_dialogue_and_persona"]["score"],
            "claude_dialogue_score": claude_ep1_score["dimensions"]["human_dialogue_and_persona"]["score"],
            "debiased_pk_winner": pk_claude["winner_label"],
            "why_winner_wins": pk_claude["why_winner_wins"],
            "why_loser_loses": pk_claude["why_loser_loses"],
        }

    return result


def main() -> None:
    SHOWCASE_DIR.mkdir(parents=True, exist_ok=True)
    test_seeds = json.loads((SEEDS_DIR / "test_seeds.json").read_text(encoding="utf-8"))
    seed_map = {s["seed_id"]: s for s in test_seeds}

    tasks = [
        (seed_map["test_085"], "1-5"),
        (seed_map["test_orig_01"], "1-5,11-12"),  # Tests Golden Opening + Paywall Climax!
        (seed_map["test_orig_02"], "1-5"),
    ]

    results = []
    with cf.ThreadPoolExecutor(max_workers=3) as ex:
        futs = [ex.submit(eval_showcase_seed, s, spec) for s, spec in tasks]
        for f in cf.as_completed(futs):
            r = f.result()
            results.append(r)
            print("[final_eval]", json.dumps(r, ensure_ascii=False))

    results.sort(key=lambda x: x["seed_id"])
    (SHOWCASE_DIR / "final_summary.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"[final_eval] Saved showcase summary to {SHOWCASE_DIR / 'final_summary.json'}")


if __name__ == "__main__":
    main()
