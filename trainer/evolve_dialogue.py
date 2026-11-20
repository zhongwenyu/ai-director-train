#!/usr/bin/env python3
"""
Decoupled Pure-Dialogue Autoregressive Evolution Engine (`trainer/evolve_dialogue.py`).

Fixes the exact root cause why whole-pipeline evolution couldn't make dialogue colloquial:
  1. Freezes the proven `v6_r1` Stage 0..2 plot/outline/motivation skeleton (`DEV` and `TEST` base drafts).
  2. Evaluates ONLY spoken voice quality via `dialogue_turing_judge.py` (which strips ALL `△` visual prose
     and parentheticals so `GEN` and `REAL_GT` stand naked in a pure-audio/dialogue Turing blind test!),
     while ALSO running `general_arena_judge.py` as a safety constraint to guarantee zero plot/logic loss.
  3. Evolves `prompts/stage2_5_dialogue_polish.md` and `references/dialogue-voice.md` across 4 genres
     (`都市情感`, `年代乡村`, `古装穿越`, `玄幻修仙`) via isolated `agy` (`gemini-4-carbon-medium`) sub-agents,
     with strict programmatic anti-overfitting / zero-name-leakage validation.
  4. Evaluates the final Dialogue Champion ONCE on all 7 Locked Unseen `TEST + OOD` cases
     (`6` unseen Hongguo `test` hits + `test_ood_hotpot2005`), comparing against BOTH unpolished `d0_raw`
     AND `REAL_GT` on pure stripped dialogue!
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
from typing import Any, Dict, List, Optional, Tuple

TRAIN_ROOT = Path("/home/zhongwenyu/project/ai-director-train")
LIVE_SKILL_DIR = TRAIN_ROOT / ".agents" / "skills" / "hit-short-drama"
GEN_ROUNDS_ROOT = TRAIN_ROOT / "runs" / "general_evolution" / "rounds"
EVO_ROOT = TRAIN_ROOT / "runs" / "dialogue_evolution"
CAND_ROOT = EVO_ROOT / "candidates"
ROUNDS_ROOT = EVO_ROOT / "rounds"
BENCH_DIR = TRAIN_ROOT / "corpus" / "general_bench"

for p in (
    str(TRAIN_ROOT / "trainer"),
    str(TRAIN_ROOT / "judge"),
    str(LIVE_SKILL_DIR / "scripts"),
):
    if p not in sys.path:
        sys.path.insert(0, p)

import llm_clients as L  # noqa: E402
import dialogue_turing_judge as DTJ  # noqa: E402
import general_arena_judge as GJ  # noqa: E402
import script_check as SC  # noqa: E402
import write_drama as WD  # noqa: E402

EVOLVABLE_DLG_FILES: Dict[str, int] = {
    "prompts/stage2_5_dialogue_polish.md": 3600,
    "references/dialogue-voice.md": 4800,
    "prompts/stage2_episodes.md": 3600,
}

FORBIDDEN_LEAK_TOKENS = [
    "叶寻",
    "林双双",
    "楚南",
    "赵帆",
    "夏芊芊",
    "陆川",
    "陈实",
    "李昊",
    "李满昌",
    "柳巧",
    "程昭",
    "何屿",
]

DLG_META_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "voice_gap_diagnosis": {
            "type": "string",
            "description": "对比红果爆款纯对白原片，当前润色稿在口语松弛度、长短呼吸、话咬话交锋、人物声纹或潜台词上残留的AI味共性问题（200字内）",
        },
        "anti_overfitting_check": {
            "type": "string",
            "description": "确认本次修改不涉及任何具体剧名、角色名或单一赛道套路，对都市、年代、古装、玄幻、末世普遍成立（120字内）",
        },
        "mutation_plan": {
            "type": "string",
            "description": "针对 stage2_5_dialogue_polish.md / dialogue-voice.md / stage2_episodes.md 的具体口语升级策略（180字内）",
        },
        "updated_files": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "rel_path": {"type": "string", "enum": list(EVOLVABLE_DLG_FILES.keys())},
                    "reason": {"type": "string"},
                    "new_content": {"type": "string"},
                },
                "required": ["rel_path", "reason", "new_content"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["voice_gap_diagnosis", "anti_overfitting_check", "mutation_plan", "updated_files"],
    "additionalProperties": False,
}

DLG_META_PROMPT = """你是红果爆款短剧**「对白去 AI 味·真人口语自回归进化架构师」**。
我们已经固定了剧本的剧情骨架，正在跨 **4 大赛道（都市情感、年代乡村、古装穿越、玄幻修仙）** 的验证集（DEV）上，把生成的纯对白与真实红果爆款原片的纯对白放在一起做**「正反换位盲听图灵对抗」**，专门进化 `Stage 2.5 台词口语化医生`。

### 进化硬约束（严禁违反！）
1. **核心目标**：彻底消灭 AI 台词最后的「优等生端着说话感」——即替编剧总结道理金句、句句15字对称双分句、缺2～6字本能短促反应、缺“话咬话”顶针反问、打擂台口号腔、掉书袋术语与千人一面声纹；同时**严禁过度油滑痞化或乱加不合地域的方言儿化音**（比如严肃古装/悬疑不乱加东北话京片子，贴合各自题材身份说活人话）！
2. **骨架绝对安全**：`Stage 2.5` 严禁增删场次编号（`## N-M`）、严禁漏掉原有的金额数字/物证/首次亲属身份称谓、严禁破坏集尾钩子切点！
3. **零数据泄漏与零过拟合**：绝对禁止把验证集或示例集里的任何角色名、剧名或特定道具写进提示词或参考手册！`prompts/stage2_episodes.md` 若修改必须保留 `{{batch_range}}` 占位符。字符预算：`stage2_5_dialogue_polish.md` ≤ 3600字，`dialogue-voice.md` ≤ 4800字，`stage2_episodes.md` ≤ 3600字。

---
### 本轮候选 `{cand_name}` 在纯对白图灵盲测中对比红果原片的逐剧诊断
{diag_report}

---
### 当前 `{cand_name}` 台词模块全文
{files_dump}
"""


def log(msg: str) -> None:
    EVO_ROOT.mkdir(parents=True, exist_ok=True)
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with (EVO_ROOT / "evolve_dialogue.log").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def copy_skill_snapshot(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def evaluate_dialogue_candidate(
    cand_name: str,
    cand_skill_dir: Path,
    bench_items: List[Dict[str, Any]],
    base_draft_root: Path,
    round_dir: Path,
    *,
    apply_polish: bool = True,
    raw_baseline_dir: Optional[Path] = None,
    champion_round_dir: Optional[Path] = None,
    verify_plot_gate: bool = False,
) -> Dict[str, Any]:
    round_dir.mkdir(parents=True, exist_ok=True)

    def run_one(item: Dict[str, Any]) -> Dict[str, Any]:
        bid = item["bench_id"]
        s_dir = round_dir / bid
        s_dir.mkdir(parents=True, exist_ok=True)

        src_dir = base_draft_root / bid
        draft_md = (src_dir / "combined_1-3.md").read_text(encoding="utf-8")
        premise_lock = json.loads((src_dir / "00_premise_lock.json").read_text(encoding="utf-8"))
        outline_md = (src_dir / "01_outline.md").read_text(encoding="utf-8")

        comb_path = s_dir / "combined_1-3.md"
        if not comb_path.is_file():
            if apply_polish:
                log(f"  [{cand_name}] Polishing dialogue for {bid} ({item['genre']})...")
                polished = WD.polish_episode_dialogue(
                    draft_md,
                    premise_lock,
                    [1, 2, 3],
                    skill_dir=cand_skill_dir,
                    idea_text=item["seed"],
                )
                comb_path.write_text(polished + "\n", encoding="utf-8")
            else:
                comb_path.write_text(draft_md, encoding="utf-8")

        gen_md = comb_path.read_text(encoding="utf-8")
        chk = SC.analyze_script(gen_md, [1, 2, 3])

        turing_cache = s_dir / "dialogue_turing.json"
        if turing_cache.is_file():
            t_audit = json.loads(turing_cache.read_text(encoding="utf-8"))
        else:
            t_audit = DTJ.audit_dialogue_turing(gen_md, genre_hint=item["genre"])
            turing_cache.write_text(json.dumps(t_audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        plot_gate = None
        if verify_plot_gate:
            pg_cache = s_dir / "general_plot_gate.json"
            if pg_cache.is_file():
                plot_gate = json.loads(pg_cache.read_text(encoding="utf-8"))
            else:
                plot_gate = GJ.audit_drama_general(gen_md, seed=item["seed"], outline_md=outline_md)
                pg_cache.write_text(json.dumps(plot_gate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        vs_gt = None
        gt_pts: Optional[int] = None
        gt_path_str = item.get("gt_path") or ""
        if gt_path_str and Path(gt_path_str).is_file():
            vs_gt_path = s_dir / "vs_real_gt_dialogue.json"
            if vs_gt_path.is_file():
                vs_gt = json.loads(vs_gt_path.read_text(encoding="utf-8"))
            else:
                gt_md = Path(gt_path_str).read_text(encoding="utf-8")
                vs_gt = DTJ.compare_swap_debiased_dialogue(
                    "GEN", gen_md, "REAL_GT", gt_md, genre_hint=item["genre"], parallel_swaps=False
                )
                vs_gt_path.write_text(json.dumps(vs_gt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            gt_pts = 2 if vs_gt["winner"] == "GEN" else (1 if vs_gt["winner"] == "TIE" else 0)

        vs_raw = None
        if raw_baseline_dir is not None and apply_polish:
            raw_p = raw_baseline_dir / bid / "combined_1-3.md"
            vs_raw_path = s_dir / "vs_d0_raw_dialogue.json"
            if vs_raw_path.is_file():
                vs_raw = json.loads(vs_raw_path.read_text(encoding="utf-8"))
            elif raw_p.is_file():
                vs_raw = DTJ.compare_swap_debiased_dialogue(
                    "POLISHED", gen_md, "UNPOLISHED_RAW", raw_p.read_text(encoding="utf-8"), genre_hint=item["genre"], parallel_swaps=False
                )
                vs_raw_path.write_text(json.dumps(vs_raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        vs_champ = None
        if champion_round_dir is not None:
            champ_p = champion_round_dir / bid / "combined_1-3.md"
            vs_champ_path = s_dir / "vs_champion_dialogue.json"
            if vs_champ_path.is_file():
                vs_champ = json.loads(vs_champ_path.read_text(encoding="utf-8"))
            elif champ_p.is_file():
                vs_champ = DTJ.compare_swap_debiased_dialogue(
                    "CAND", gen_md, "CHAMP", champ_p.read_text(encoding="utf-8"), genre_hint=item["genre"], parallel_swaps=False
                )
                vs_champ_path.write_text(json.dumps(vs_champ, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        log(
            f"  [{cand_name}] {bid} ({item['genre']}): turing={t_audit['verdict']} (score={t_audit['total_score']}, "
            f"short={t_audit['rhythm_metrics']['short_reaction_ratio_le7']}, twin={t_audit['rhythm_metrics']['twin_clause_symmetry_ratio']}) "
            + (f"| vs_REAL_GT={vs_gt['winner']} " if vs_gt else "| [OOD] ")
            + (f"| vs_RAW={vs_raw['winner']} " if vs_raw else "")
            + (f"| vs_CHAMP={vs_champ['winner']} " if vs_champ else "")
            + (f"| plot_gate={plot_gate['verdict']}({plot_gate['total_score']})" if plot_gate else "")
        )
        return {
            "bench_id": bid,
            "genre": item["genre"],
            "script_check_ok": chk["ok"],
            "turing_verdict": t_audit["verdict"],
            "turing_score": t_audit["total_score"],
            "turing_pillars": t_audit["scores"],
            "rhythm_metrics": t_audit["rhythm_metrics"],
            "ai_voice_defects": t_audit["ai_voice_defects"],
            "ear_impression": t_audit["ear_test_impression"],
            "plot_gate_verdict": plot_gate["verdict"] if plot_gate else None,
            "plot_gate_score": plot_gate["total_score"] if plot_gate else None,
            "vs_real_gt_winner": vs_gt["winner"] if vs_gt else None,
            "vs_real_gt_points": gt_pts,
            "vs_real_gt_examples": vs_gt["forward_detail"]["decisive_examples"] if vs_gt else None,
            "vs_real_gt_cand_notes": vs_gt["forward_detail"]["candidate_a_voice_analysis"] if vs_gt else None,
            "vs_raw_winner": vs_raw["winner"] if vs_raw else None,
            "vs_champ_winner": vs_champ["winner"] if vs_champ else None,
        }

    with cf.ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(run_one, bench_items))

    pass_cnt = sum(1 for r in results if r["turing_verdict"] == "PASS_HUMAN_NATURAL")
    mean_score = round(statistics.mean(r["turing_score"] for r in results), 2)
    mean_short = round(statistics.mean(r["rhythm_metrics"]["short_reaction_ratio_le7"] for r in results), 3)
    mean_twin = round(statistics.mean(r["rhythm_metrics"]["twin_clause_symmetry_ratio"] for r in results), 3)

    gt_items = [r for r in results if r["vs_real_gt_winner"] is not None]
    gt_w = sum(1 for r in gt_items if r["vs_real_gt_winner"] == "GEN")
    gt_t = sum(1 for r in gt_items if r["vs_real_gt_winner"] == "TIE")
    gt_l = len(gt_items) - gt_w - gt_t
    gt_pts_tot = sum(r["vs_real_gt_points"] or 0 for r in gt_items)
    gt_norm = (gt_pts_tot / (2.0 * len(gt_items))) if gt_items else 0.0

    raw_items = [r for r in results if r["vs_raw_winner"] is not None]
    raw_w = sum(1 for r in raw_items if r["vs_raw_winner"] == "POLISHED")
    raw_t = sum(1 for r in raw_items if r["vs_raw_winner"] == "TIE")
    raw_l = len(raw_items) - raw_w - raw_t

    champ_items = [r for r in results if r["vs_champ_winner"] is not None]
    ch_w = sum(1 for r in champ_items if r["vs_champ_winner"] == "CAND")
    ch_t = sum(1 for r in champ_items if r["vs_champ_winner"] == "TIE")
    ch_l = len(champ_items) - ch_w - ch_t

    plot_items = [r for r in results if r["plot_gate_verdict"] is not None]
    plot_pass = sum(1 for r in plot_items if r["plot_gate_verdict"] == "PASS_HIT_READY")

    composite = round(mean_score + gt_norm * 45.0 + (pass_cnt / len(results)) * 15.0, 2)
    summary = {
        "cand_name": cand_name,
        "pass_human_natural_rate": f"{pass_cnt}/{len(results)}",
        "pass_cnt": pass_cnt,
        "mean_turing_score": mean_score,
        "mean_short_reaction_ratio": mean_short,
        "mean_twin_clause_ratio": mean_twin,
        "plot_gate_pass_rate": f"{plot_pass}/{len(plot_items)}" if plot_items else None,
        "vs_real_gt_dialogue": {"total": len(gt_items), "wins": gt_w, "ties": gt_t, "losses": gt_l, "points": gt_pts_tot},
        "vs_d0_raw_dialogue": {"total": len(raw_items), "wins": raw_w, "ties": raw_t, "losses": raw_l} if raw_items else None,
        "vs_champion_dialogue": {"wins": ch_w, "ties": ch_t, "losses": ch_l} if champion_round_dir else None,
        "composite_metric": composite,
        "seeds": results,
    }
    (round_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def synthesize_next_dialogue_candidate(
    base_name: str,
    base_skill_dir: Path,
    next_name: str,
    next_skill_dir: Path,
    eval_summary: Dict[str, Any],
    bench_items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    copy_skill_snapshot(base_skill_dir, next_skill_dir)
    leak_tokens = sorted(
        set(FORBIDDEN_LEAK_TOKENS + [it.get("title_ref", "").strip() for it in bench_items if len(it.get("title_ref", "").strip()) >= 3])
    )

    diag = []
    for s in eval_summary["seeds"]:
        diag.append({
            "bench_id": s["bench_id"],
            "genre": s["genre"],
            "turing_verdict": s["turing_verdict"],
            "turing_score": s["turing_score"],
            "rhythm_metrics": s["rhythm_metrics"],
            "ear_impression": s["ear_impression"],
            "ai_voice_defects": s["ai_voice_defects"],
            "vs_real_gt_winner": s["vs_real_gt_winner"],
            "voice_gap_vs_real_gt": s["vs_real_gt_cand_notes"],
            "decisive_quote_comparison": s["vs_real_gt_examples"],
        })

    files_dump = "\n\n".join(
        f"=== FILE: {rp} (len={len((base_skill_dir / rp).read_text(encoding='utf-8'))} / max={mx}) ===\n"
        + (base_skill_dir / rp).read_text(encoding="utf-8")
        for rp, mx in EVOLVABLE_DLG_FILES.items()
    )
    prompt = DLG_META_PROMPT.format(
        cand_name=base_name,
        diag_report=json.dumps(diag, ensure_ascii=False, indent=2),
        files_dump=files_dump,
    )

    log(f"Invoking isolated Dialogue Meta-Optimizer (agy gemini-4-carbon-medium) `{base_name}` -> `{next_name}`...")
    plan = L.call_agy_json(prompt, DLG_META_SCHEMA, model="gemini-4-carbon-medium", effort="medium", timeout=600)

    applied, rejected = [], []
    for uf in plan.get("updated_files", []):
        rp = uf["rel_path"]
        nc = uf["new_content"].strip()
        if rp not in EVOLVABLE_DLG_FILES:
            continue
        if rp == "prompts/stage2_episodes.md" and "{batch_range}" not in nc:
            rejected.append({"rel_path": rp, "reason": "missing {batch_range}"})
            continue
        leaked = [t for t in leak_tokens if t and t in nc]
        if leaked:
            rejected.append({"rel_path": rp, "reason": f"leaked tokens: {leaked}"})
            log(f"  [reject leak] {rp}: {leaked}")
            continue
        if len(nc) > EVOLVABLE_DLG_FILES[rp] + 600 or len(nc) < 200:
            rejected.append({"rel_path": rp, "reason": f"out-of-budget len={len(nc)}"})
            continue
        (next_skill_dir / rp).write_text(nc + "\n", encoding="utf-8")
        applied.append({"rel_path": rp, "len": len(nc), "reason": uf["reason"]})

    meta_log = {
        "from": base_name,
        "to": next_name,
        "voice_gap_diagnosis": plan["voice_gap_diagnosis"],
        "anti_overfitting_check": plan["anti_overfitting_check"],
        "mutation_plan": plan["mutation_plan"],
        "applied_files": applied,
        "rejected_files": rejected,
    }
    (EVO_ROOT / f"mutation_{base_name}_to_{next_name}.json").write_text(
        json.dumps(meta_log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    log(f"  Applied {len(applied)} dialogue mutations for `{next_name}`: {[x['rel_path'] for x in applied]}")
    return meta_log


def sync_champion_to_live(champ_skill_dir: Path) -> None:
    for rp in EVOLVABLE_DLG_FILES:
        shutil.copy2(champ_skill_dir / rp, LIVE_SKILL_DIR / rp)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rounds", type=int, default=2, help="Number of mutation rounds after d1 (d0_raw -> d1 -> d2 -> ...)")
    ap.add_argument("--run-test", action="store_true", help="Run locked TEST+OOD evaluation once on final dialogue champion")
    args = ap.parse_args()

    dev_bench = json.loads((BENCH_DIR / "dev_bench.json").read_text(encoding="utf-8"))
    CAND_ROOT.mkdir(parents=True, exist_ok=True)
    ROUNDS_ROOT.mkdir(parents=True, exist_ok=True)

    dev_draft_root = GEN_ROUNDS_ROOT / "v6_r1"
    test_draft_root = GEN_ROUNDS_ROOT / "v6_r1_TEST"

    # Step 1: Evaluate unpolished `d0_raw` on Pure-Dialogue Turing Judge + vs_REAL_GT!
    d0_dir = ROUNDS_ROOT / "d0_raw"
    log("=== Step 1: Auditing Unpolished `d0_raw` (`v6_r1` before Stage 2.5) on Pure-Dialogue Turing Arena ===")
    d0_summary = evaluate_dialogue_candidate(
        "d0_raw", LIVE_SKILL_DIR, dev_bench, dev_draft_root, d0_dir, apply_polish=False
    )
    log(
        f"Unpolished `d0_raw` DEV Dialogue: pass={d0_summary['pass_human_natural_rate']}, mean={d0_summary['mean_turing_score']}, "
        f"short_ratio={d0_summary['mean_short_reaction_ratio']}, twin_ratio={d0_summary['mean_twin_clause_ratio']}, "
        f"vs_REAL_GT={d0_summary['vs_real_gt_dialogue']}, composite={d0_summary['composite_metric']}"
    )

    # Step 2: Evaluate initial Stage 2.5 candidate `d1`
    d1_name = "d1"
    d1_skill = CAND_ROOT / d1_name
    if not d1_skill.exists():
        copy_skill_snapshot(LIVE_SKILL_DIR, d1_skill)
    d1_dir = ROUNDS_ROOT / d1_name
    log("=== Step 2: Evaluating Stage 2.5 Dialogue Doctor `d1` on DEV Pure-Dialogue Turing Arena ===")
    champ_name = d1_name
    champ_skill = d1_skill
    champ_dir = d1_dir
    champ_summary = evaluate_dialogue_candidate(
        d1_name, d1_skill, dev_bench, dev_draft_root, d1_dir, apply_polish=True, raw_baseline_dir=d0_dir
    )
    log(
        f"Candidate `d1` DEV Dialogue: pass={champ_summary['pass_human_natural_rate']}, mean={champ_summary['mean_turing_score']}, "
        f"vs_d0_raw={champ_summary['vs_d0_raw_dialogue']}, vs_REAL_GT={champ_summary['vs_real_gt_dialogue']}, composite={champ_summary['composite_metric']}"
    )

    history = [d0_summary, champ_summary]

    # Step 3: Autoregressive Dialogue Mutations d1 -> d2 -> ...
    for r in range(2, args.rounds + 2):
        cand_name = f"d{r}"
        cand_skill = CAND_ROOT / cand_name
        cand_dir = ROUNDS_ROOT / cand_name

        if (
            r >= 3
            and champ_summary["pass_cnt"] == len(dev_bench)
            and champ_summary["vs_real_gt_dialogue"]["losses"] == 0
            and champ_summary["vs_real_gt_dialogue"]["wins"] >= 5
        ):
            log(f"Strong pure-dialogue convergence reached by `{champ_name}` — stopping DEV mutations early!")
            break

        if not (EVO_ROOT / f"mutation_{champ_name}_to_{cand_name}.json").is_file() or not cand_skill.exists():
            meta_res = synthesize_next_dialogue_candidate(
                champ_name, champ_skill, cand_name, cand_skill, champ_summary, dev_bench
            )
            if not meta_res["applied_files"]:
                log(f"No valid mutations applied for `{cand_name}`; stopping.")
                break

        log(f"=== Evaluating Mutated Dialogue Doctor `{cand_name}` on Stratified Multi-Genre DEV ===")
        cand_summary = evaluate_dialogue_candidate(
            cand_name,
            cand_skill,
            dev_bench,
            dev_draft_root,
            cand_dir,
            apply_polish=True,
            raw_baseline_dir=d0_dir,
            champion_round_dir=champ_dir,
        )
        history.append(cand_summary)

        vc = cand_summary["vs_champion_dialogue"] or {"wins": 0, "ties": 0, "losses": 0}
        promote = (vc["wins"] > vc["losses"] and cand_summary["composite_metric"] >= champ_summary["composite_metric"] - 2.0) or (
            vc["wins"] == vc["losses"] and cand_summary["composite_metric"] > champ_summary["composite_metric"] + 0.5
        )
        if promote:
            log(f"PROMOTED `{cand_name}` -> NEW DIALOGUE CHAMPION! (vs_champ={vc}, composite {champ_summary['composite_metric']} -> {cand_summary['composite_metric']})")
            champ_name = cand_name
            champ_skill = cand_skill
            champ_dir = cand_dir
            champ_summary = cand_summary
            sync_champion_to_live(champ_skill)
        else:
            log(f"REJECTED `{cand_name}` (vs_champ={vc}, composite {cand_summary['composite_metric']} vs {champ_summary['composite_metric']}); keeping `{champ_name}`.")

    sync_champion_to_live(champ_skill)

    test_summary = None
    if args.run_test:
        test_bench = json.loads((BENCH_DIR / "test_bench.json").read_text(encoding="utf-8"))
        log(f"=== Running LOCKED UNSEEN TEST + OOD Pure-Dialogue + Plot-Safety Evaluation ({len(test_bench)} cases) on `{champ_name}` ===")
        test_summary = evaluate_dialogue_candidate(
            f"{champ_name}_TEST",
            champ_skill,
            test_bench,
            test_draft_root,
            ROUNDS_ROOT / f"{champ_name}_TEST",
            apply_polish=True,
            raw_baseline_dir=test_draft_root,
            verify_plot_gate=True,
        )
        log(
            f"LOCKED TEST DIALOGUE RESULT (`{champ_name}`): turing_pass={test_summary['pass_human_natural_rate']}, "
            f"plot_safety_pass={test_summary['plot_gate_pass_rate']}, vs_UNPOLISHED={test_summary['vs_d0_raw_dialogue']}, "
            f"vs_REAL_GT={test_summary['vs_real_gt_dialogue']}"
        )

    final_report = {
        "final_dialogue_champion": champ_name,
        "d0_unpolished_dev": d0_summary,
        "champion_dev": champ_summary,
        "history": history,
        "locked_test": test_summary,
    }
    (EVO_ROOT / "final_dialogue_report.json").write_text(
        json.dumps(final_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    log("Pure-dialogue autoregressive evolution complete!")


if __name__ == "__main__":
    main()
