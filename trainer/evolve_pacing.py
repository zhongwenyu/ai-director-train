#!/usr/bin/env python3
"""
Autoregressive Multi-Episode Pacing & Causal Clarity Evolution Engine (`trainer/evolve_pacing.py`).

100% powered by isolated `agy` sub-agents (`--model gemini-4-carbon-medium --sandbox --disable-slash-commands`).
Zero `codex` usage anywhere.

Loop per round r = 0..R:
  1. Snapshot candidate skill `runs/pacing_evolution/candidates/v5_r{r}`
  2. Generate full outline + continuous Ep 1-3 scripts from 1-sentence seeds on unseen `DEV` benchmark
  3. Audit each 3-ep arc via `pacing_arena_judge.audit_three_episode_arc` (on `strip_to_screen` output)
  4. Run Swap-Debiased Blind Pairwise PK:
     - `GEN` vs `REAL_GT` (real Hongguo 3-ep opening of the same drama!)
     - If r > 0: `v5_r{r}` vs current `champion`!
  5. Promote `v5_r{r}` -> `champion` (and sync to `.agents/skills/hit-short-drama`) iff strictly better on DEV
  6. Feed failure diagnostics into isolated Meta-Optimizer (`agy gemini-4-carbon-medium`) to synthesize `v5_r{r+1}`!
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import shutil
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

TRAIN_ROOT = Path("/home/zhongwenyu/project/ai-director-train")
LIVE_SKILL_DIR = TRAIN_ROOT / ".agents" / "skills" / "hit-short-drama"
EVO_ROOT = TRAIN_ROOT / "runs" / "pacing_evolution"
CAND_ROOT = EVO_ROOT / "candidates"
ROUNDS_ROOT = EVO_ROOT / "rounds"
BENCH_DIR = TRAIN_ROOT / "corpus" / "pacing_bench"

for p in (
    str(TRAIN_ROOT / "trainer"),
    str(TRAIN_ROOT / "judge"),
    str(LIVE_SKILL_DIR / "scripts"),
):
    if p not in sys.path:
        sys.path.insert(0, p)

import llm_clients as L  # noqa: E402
import pacing_arena_judge as PJ  # noqa: E402
import script_check as SC  # noqa: E402
import write_drama as WD  # noqa: E402

EVOLVABLE_FILES: Dict[str, int] = {
    "prompts/stage0_premise_lock.md": 3200,
    "prompts/stage1_outline.md": 2800,
    "prompts/stage2_episodes.md": 3200,
    "references/episode-craft.md": 4600,
    "references/anti-patterns.md": 4800,
}

META_EVOLVER_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "root_cause_diagnosis": {
            "type": "string",
            "description": "对比真实红果原片，本轮生成稿在跨集事件节奏、前情关系交代、因果逻辑或台词呼吸感上的核心差距（150字内）",
        },
        "mutation_plan": {
            "type": "string",
            "description": "下一轮Skill的具体进化策略（如何让3集更从容地只承载1个核心事件的前三幕、把人物关系与前因后果演得更透，150字内）",
        },
        "updated_files": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "rel_path": {
                        "type": "string",
                        "enum": list(EVOLVABLE_FILES.keys()),
                    },
                    "reason": {"type": "string"},
                    "new_content": {"type": "string"},
                },
                "required": ["rel_path", "reason", "new_content"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["root_cause_diagnosis", "mutation_plan", "updated_files"],
    "additionalProperties": False,
}

META_EVOLVER_PROMPT = """你是短剧叙事节奏与 AI 编剧 Skill 自回归进化架构师。
我们正在基于红果 105 部真实爆款语料的实证规律（**1个完整戏剧事件平均横跨 5.56 集连载；第1集 90.1% 为设局蓄压；Ep1->Ep2 同场下一秒无缝续接率达 62.2%**），在未见验证集（DEV）上通过「一句话创意生成前3集 → 与红果原片前3集正反换位双盲对抗」自回归进化 `hit-short-drama`。

### 进化硬约束（严禁违反！）
1. **核心优化目标**：彻底消灭「剧情进展太快、3集硬塞四五件大事导致前因后果与人物关系没说清、观众看得莫名其妙」以及「前世今生时间线自相矛盾、哑巴主角读心术签约、无条件白送股份、围裙掏铁盒」等病灶！让生成的连续 3 集像真实红果爆款一样，围绕 **同一个核心开局事件** 层层剥笋、把每个人的关系和算计用大白话演得一清二楚、集尾原场悬念切集、下集第一秒无缝续接！
2. **反 Goodhart 死板教条**：严禁规定“第几秒必须扇巴掌/推搡”等机械动作配额；用清晰的跨集分幕结构原则与脱敏的「❌ 快进跳跃/没说清病灶 vs ✅ 从容铺透的爆款连载写法」正负对照来引导生成模型。
3. **占位符与字符预算守恒**：
   - `prompts/stage1_outline.md` 必须保留 `{{episode_plan_range}}` 占位符！
   - `prompts/stage2_episodes.md` 必须保留 `{{batch_range}}` 占位符！
   - 各模块修改后总字数不得超过上限：`stage0_premise_lock.md` ≤ 3200字，`stage1_outline.md` ≤ 2800字，`stage2_episodes.md` ≤ 3200字，`episode-craft.md` ≤ 4600字，`anti-patterns.md` ≤ 4800字。只修改最关键的 2～4 个文件。

---
### 本轮候选版本 `{cand_name}` 在 DEV 验证集与红果原片双盲对抗的诊断汇总
{diag_report}

---
### 当前 `{cand_name}` 可进化模块全文
{files_dump}
"""


def log(msg: str) -> None:
    EVO_ROOT.mkdir(parents=True, exist_ok=True)
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with (EVO_ROOT / "evolve_pacing.log").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def copy_skill_snapshot(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def evaluate_candidate_on_bench(
    cand_name: str,
    cand_skill_dir: Path,
    bench_items: List[Dict[str, Any]],
    round_dir: Path,
    *,
    champion_round_dir: Path | None = None,
) -> Dict[str, Any]:
    round_dir.mkdir(parents=True, exist_ok=True)

    def run_one_seed(item: Dict[str, Any]) -> Dict[str, Any]:
        bid = item["bench_id"]
        s_dir = round_dir / bid
        s_dir.mkdir(parents=True, exist_ok=True)
        comb_path = s_dir / "combined_1-3.md"
        if not comb_path.is_file():
            log(f"  [{cand_name}] Generating {bid} from 1-sentence seed...")
            WD.run_pipeline(
                item["seed"],
                s_dir,
                "1-3",
                batch_size=3,
                skill_dir=cand_skill_dir,
                force=False,
            )
        gen_md = comb_path.read_text(encoding="utf-8")
        chk = SC.analyze_script(gen_md, [1, 2, 3])
        arc_audit = PJ.audit_three_episode_arc(gen_md)
        (s_dir / "arc_audit.json").write_text(json.dumps(arc_audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        gt_md = Path(item["gt_path"]).read_text(encoding="utf-8")
        vs_gt = PJ.compare_swap_debiased_arcs("GEN", gen_md, "REAL_GT", gt_md, parallel_swaps=False)
        (s_dir / "vs_real_gt.json").write_text(json.dumps(vs_gt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        vs_champ = None
        if champion_round_dir is not None:
            champ_md_path = champion_round_dir / bid / "combined_1-3.md"
            if champ_md_path.is_file():
                champ_md = champ_md_path.read_text(encoding="utf-8")
                vs_champ = PJ.compare_swap_debiased_arcs("CAND", gen_md, "CHAMP", champ_md, parallel_swaps=False)
                (s_dir / "vs_champion.json").write_text(json.dumps(vs_champ, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        gt_pts = 2 if vs_gt["winner"] == "GEN" else (1 if vs_gt["winner"] == "TIE" else 0)
        log(
            f"  [{cand_name}] {bid}: gate={arc_audit['verdict']} (score={arc_audit['total_score']}, events={arc_audit['distinct_major_events_counted']}) | vs_REAL_GT={vs_gt['winner']}"
            + (f" | vs_CHAMP={vs_champ['winner']}" if vs_champ else "")
        )
        return {
            "bench_id": bid,
            "genre": item["genre"],
            "script_check_ok": chk["ok"],
            "arc_verdict": arc_audit["verdict"],
            "arc_score": arc_audit["total_score"],
            "distinct_events": arc_audit["distinct_major_events_counted"],
            "arc_flaws": arc_audit["flaws"],
            "arc_comprehension": arc_audit["viewer_comprehension_summary"],
            "vs_real_gt_winner": vs_gt["winner"],
            "vs_real_gt_points": gt_pts,
            "vs_real_gt_fwd_flaws": vs_gt["forward_detail"]["script_a_flaws"],
            "vs_real_gt_reason": vs_gt["forward_detail"]["decisive_reason"],
            "vs_champ_winner": vs_champ["winner"] if vs_champ else None,
        }

    # Max 3 seeds in parallel so total concurrent isolated agy sub-agents stays smooth (<= 4)
    with cf.ThreadPoolExecutor(max_workers=3) as pool:
        seed_results = list(pool.map(run_one_seed, bench_items))

    pass_cnt = sum(1 for r in seed_results if r["arc_verdict"] == "PASS_IMMERSIVE")
    mean_score = round(statistics.mean(r["arc_score"] for r in seed_results), 2)
    mean_events = round(statistics.mean(r["distinct_events"] for r in seed_results), 2)
    gt_points = sum(r["vs_real_gt_points"] for r in seed_results)
    gt_wins = sum(1 for r in seed_results if r["vs_real_gt_winner"] == "GEN")
    gt_ties = sum(1 for r in seed_results if r["vs_real_gt_winner"] == "TIE")

    champ_wins = sum(1 for r in seed_results if r["vs_champ_winner"] == "CAND")
    champ_losses = sum(1 for r in seed_results if r["vs_champ_winner"] == "CHAMP")
    champ_ties = sum(1 for r in seed_results if r["vs_champ_winner"] == "TIE")

    composite = round(mean_score + gt_points * 8.0 + (pass_cnt / len(seed_results)) * 15.0, 2)
    summary = {
        "cand_name": cand_name,
        "pass_immersive_rate": f"{pass_cnt}/{len(seed_results)}",
        "pass_cnt": pass_cnt,
        "mean_arc_score": mean_score,
        "mean_distinct_events": mean_events,
        "vs_real_gt": {"wins": gt_wins, "ties": gt_ties, "losses": len(seed_results) - gt_wins - gt_ties, "points": gt_points},
        "vs_champion": {"wins": champ_wins, "ties": champ_ties, "losses": champ_losses} if champion_round_dir else None,
        "composite_metric": composite,
        "seeds": seed_results,
    }
    (round_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def synthesize_next_candidate(
    base_cand_name: str,
    base_skill_dir: Path,
    next_cand_name: str,
    next_skill_dir: Path,
    eval_summary: Dict[str, Any],
) -> Dict[str, Any]:
    copy_skill_snapshot(base_skill_dir, next_skill_dir)

    diag_items = []
    for s in eval_summary["seeds"]:
        diag_items.append({
            "bench_id": s["bench_id"],
            "genre": s["genre"],
            "arc_verdict": s["arc_verdict"],
            "arc_score": s["arc_score"],
            "distinct_events_in_3eps": s["distinct_events"],
            "viewer_comprehension": s["arc_comprehension"],
            "arc_flaws": s["arc_flaws"],
            "vs_real_gt_winner": s["vs_real_gt_winner"],
            "gen_weaknesses_vs_real_gt": s["vs_real_gt_fwd_flaws"],
            "why_real_gt_or_gen_won": s["vs_real_gt_reason"],
        })

    files_blocks = []
    for rel_p, budget in EVOLVABLE_FILES.items():
        txt = (base_skill_dir / rel_p).read_text(encoding="utf-8")
        files_blocks.append(f"=== FILE: {rel_p} (len={len(txt)} / max={budget}) ===\n{txt}")

    prompt = META_EVOLVER_PROMPT.format(
        cand_name=base_cand_name,
        diag_report=json.dumps(diag_items, ensure_ascii=False, indent=2),
        files_dump="\n\n".join(files_blocks),
    )

    log(f"Invoking isolated Meta-Optimizer (agy gemini-4-carbon-medium) `{base_cand_name}` -> `{next_cand_name}`...")
    plan = L.call_agy_json(prompt, META_EVOLVER_SCHEMA, model="gemini-4-carbon-medium", effort="medium", timeout=600)

    applied = []
    for uf in plan.get("updated_files", []):
        rel_p = uf["rel_path"]
        new_c = uf["new_content"].strip()
        if rel_p not in EVOLVABLE_FILES:
            continue
        if rel_p == "prompts/stage1_outline.md" and "{episode_plan_range}" not in new_c:
            log(f"  [skip invalid mutation] {rel_p} missing {{episode_plan_range}}")
            continue
        if rel_p == "prompts/stage2_episodes.md" and "{batch_range}" not in new_c:
            log(f"  [skip invalid mutation] {rel_p} missing {{batch_range}}")
            continue
        if len(new_c) > EVOLVABLE_FILES[rel_p] + 600 or len(new_c) < 200:
            log(f"  [skip out-of-budget mutation] {rel_p} len={len(new_c)}")
            continue
        (next_skill_dir / rel_p).write_text(new_c + "\n", encoding="utf-8")
        applied.append({"rel_path": rel_p, "len": len(new_c), "reason": uf["reason"]})

    meta_log = {
        "from": base_cand_name,
        "to": next_cand_name,
        "root_cause_diagnosis": plan["root_cause_diagnosis"],
        "mutation_plan": plan["mutation_plan"],
        "applied_files": applied,
    }
    (EVO_ROOT / f"mutation_{base_cand_name}_to_{next_cand_name}.json").write_text(
        json.dumps(meta_log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    log(f"  Applied {len(applied)} mutated modules for `{next_cand_name}`: {[x['rel_path'] for x in applied]}")
    return meta_log


def sync_champion_to_live(champ_skill_dir: Path) -> None:
    for rel_p in EVOLVABLE_FILES:
        shutil.copy2(champ_skill_dir / rel_p, LIVE_SKILL_DIR / rel_p)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rounds", type=int, default=2, help="Number of mutation rounds after r0 baseline (total r0..rN)")
    ap.add_argument("--run-test", action="store_true", help="Run locked TEST split evaluation on final champion")
    args = ap.parse_args()

    dev_bench = json.loads((BENCH_DIR / "dev_bench.json").read_text(encoding="utf-8"))
    CAND_ROOT.mkdir(parents=True, exist_ok=True)
    ROUNDS_ROOT.mkdir(parents=True, exist_ok=True)

    # Snapshot r0 from LIVE_SKILL_DIR
    r0_name = "v5_r0"
    r0_skill = CAND_ROOT / r0_name
    copy_skill_snapshot(LIVE_SKILL_DIR, r0_skill)

    log(f"=== Evaluating Initial Candidate `{r0_name}` on {len(dev_bench)} DEV dramas ===")
    champ_name = r0_name
    champ_skill = r0_skill
    champ_round_dir = ROUNDS_ROOT / r0_name
    champ_summary = evaluate_candidate_on_bench(r0_name, r0_skill, dev_bench, champ_round_dir)
    log(f"Champion `{champ_name}` DEV composite={champ_summary['composite_metric']} | vs_REAL_GT={champ_summary['vs_real_gt']}")

    history = [champ_summary]

    for r in range(1, args.rounds + 1):
        cand_name = f"v5_r{r}"
        cand_skill = CAND_ROOT / cand_name
        cand_round_dir = ROUNDS_ROOT / cand_name

        # Early stop if already beating/tying REAL_GT on all DEV dramas with 100% PASS_IMMERSIVE
        if (
            champ_summary["pass_cnt"] == len(dev_bench)
            and champ_summary["vs_real_gt"]["losses"] == 0
            and champ_summary["vs_real_gt"]["wins"] >= 2
        ):
            log(f"Early convergence achieved by `{champ_name}` (0 losses vs REAL_GT, 100% PASS_IMMERSIVE)!")
            break

        synthesize_next_candidate(champ_name, champ_skill, cand_name, cand_skill, champ_summary)
        log(f"=== Evaluating Mutated Candidate `{cand_name}` on DEV ===")
        cand_summary = evaluate_candidate_on_bench(
            cand_name, cand_skill, dev_bench, cand_round_dir, champion_round_dir=champ_round_dir
        )
        history.append(cand_summary)

        vc = cand_summary["vs_champion"] or {"wins": 0, "losses": 0}
        promote = (vc["wins"] > vc["losses"]) or (
            vc["wins"] == vc["losses"] and cand_summary["composite_metric"] > champ_summary["composite_metric"]
        )
        if promote:
            log(
                f"PROMOTED `{cand_name}` -> NEW CHAMPION! (vs_champ={vc}, composite {champ_summary['composite_metric']} -> {cand_summary['composite_metric']})"
            )
            champ_name = cand_name
            champ_skill = cand_skill
            champ_round_dir = cand_round_dir
            champ_summary = cand_summary
            sync_champion_to_live(champ_skill)
        else:
            log(
                f"REJECTED `{cand_name}` (vs_champ={vc}, composite {cand_summary['composite_metric']} vs champ {champ_summary['composite_metric']}); keeping `{champ_name}`."
            )

    test_summary = None
    if args.run_test:
        test_bench = json.loads((BENCH_DIR / "test_bench.json").read_text(encoding="utf-8"))
        log(f"=== Running LOCKED UNSEEN TEST Split Evaluation ({len(test_bench)} dramas) on Champion `{champ_name}` ===")
        test_summary = evaluate_candidate_on_bench(
            f"{champ_name}_TEST", champ_skill, test_bench, ROUNDS_ROOT / f"{champ_name}_TEST"
        )
        log(f"LOCKED TEST RESULT for `{champ_name}`: pass={test_summary['pass_immersive_rate']}, mean_score={test_summary['mean_arc_score']}, mean_events={test_summary['mean_distinct_events']}, vs_REAL_GT={test_summary['vs_real_gt']}")

    final_report = {
        "final_champion": champ_name,
        "champion_dev_summary": champ_summary,
        "history": history,
        "locked_test_summary": test_summary,
    }
    (EVO_ROOT / "final_evolution_report.json").write_text(
        json.dumps(final_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    log("Autoregressive pacing evolution complete!")


if __name__ == "__main__":
    main()
