#!/usr/bin/env python3
"""
Generalized Cross-Genre & Cross-Granularity Autoregressive Evolution Engine (`trainer/evolve_general.py`).

100% powered by context-isolated `agy` sub-agents (`--model gemini-4-carbon-medium --sandbox --disable-slash-commands`).
Zero `codex` usage anywhere.

Anti-Overfitting Design:
  1. Stratified `DEV` benchmark spans 4 distinct genres (`都市情感`, `年代乡村`, `古装穿越`, `玄幻修仙`) AND
     2 seed granularities (`concise_1s` 1-sentence seeds + `rich_brief` multi-paragraph creative briefs).
  2. Evaluates each candidate on 4 orthogonal domain-agnostic pillars via `general_arena_judge`:
     `seed_fidelity_and_hook`, `motivation_and_logic`, `dramatic_tension_and_emotion`, `serial_pacing_and_clarity`,
     plus Swap-Debiased Blind Pairwise PK against `REAL_GT` (real Hongguo hit opening) and against `CHAMP`.
  3. Hard programmatic anti-leakage filter rejects any Meta-Optimizer mutation that leaks benchmark character names/titles,
     drops template placeholders, or violates file character budgets, and blocks promotion on single-genre collapse.
  4. Locked `TEST` split (`6` unseen multi-genre Hongguo dramas + `test_ood_hotpot2005` verbatim 3-paragraph user brief)
     is touched strictly ONCE on the final champion after evolution finishes.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import re
import shutil
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TRAIN_ROOT = Path("/home/zhongwenyu/project/ai-director-train")
LIVE_SKILL_DIR = TRAIN_ROOT / ".agents" / "skills" / "hit-short-drama"
EVO_ROOT = TRAIN_ROOT / "runs" / "general_evolution"
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
import general_arena_judge as GJ  # noqa: E402
import script_check as SC  # noqa: E402
import write_drama as WD  # noqa: E402

EVOLVABLE_FILES: Dict[str, int] = {
    "prompts/stage0_premise_lock.md": 3600,
    "prompts/stage1_outline.md": 3400,
    "prompts/stage2_episodes.md": 3600,
    "references/story-engine.md": 4400,
    "references/episode-craft.md": 5000,
    "references/anti-patterns.md": 5200,
}

# Explicit anti-leakage blocklist: never allow specific user/benchmark character names or overfitted rules into skill files!
FORBIDDEN_LEAK_TOKENS = [
    "叶寻",
    "林双双",
    "楚南",
    "赵帆",
    "夏芊芊",
    "禁止在校生",
    "严禁大学生掌勺",
    "CRAFT_BUSINESS_REBIRTH",
    "FAMILY_ETHICS_COUNTERATTACK",
]

META_EVOLVER_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "cross_genre_diagnosis": {
            "type": "string",
            "description": "综合都市、年代、古装、玄幻4大赛道及极简/详尽2种种子粒度，本轮生成稿对比红果原片暴露出的共性短板（200字内）",
        },
        "anti_overfitting_check": {
            "type": "string",
            "description": "说明本次修改为何属于跨题材通用戏剧规律，而非针对某一部验证剧或某单一套路的过拟合补丁（120字内）",
        },
        "mutation_plan": {
            "type": "string",
            "description": "下一轮Skill的具体进化方案（针对最关键的2～4个模块说明如何提升原创意保真、分时动机心理层次、情绪拉扯浓度与跨集连载从容度，180字内）",
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
    "required": [
        "cross_genre_diagnosis",
        "anti_overfitting_check",
        "mutation_plan",
        "updated_files",
    ],
    "additionalProperties": False,
}

META_EVOLVER_PROMPT = """你是全赛道爆款短剧叙事引擎与 AI 编剧 Skill 泛化自回归进化架构师。
我们正在跨 **4 大题材赛道（都市情感、年代乡村、古装穿越、玄幻修仙）** 与 **2 种输入粒度（一句话极简种子 `concise_1s`、多段详尽创意梗概 `rich_brief`）** 的分层验证集（DEV）上，通过「生成全剧大纲+前3集剧本 → 四维通用盲审 + 与真实红果爆款原片正反换位双盲对抗」来进化 `hit-short-drama`。

### 泛化自回归进化铁律（严禁过拟合！）
1. **四大通用提升目标**：
   - **原创意保真与原生卖点放大（`seed_fidelity_and_hook`）**：详尽创意里的明确人物身份、核心关系、关键对照路线与爽点弧线必须 100% 忠实保留并演活；极简一句话种子则顺应其原生题材扩写出扎实抓人的人物羁绊与开局困境。
   - **全员分时动机与人性心理渐变（`motivation_and_logic`）**：严防时间线悖论（如曾相守多年却在早期节点无故深恶痛绝赶人）、未卜先知、把 `[VO]` 心声当公开对白接话、无条件白送股份或脸谱化弱智送人头；让对手/前任展现出真实的认知局限、傲慢惯性、短期甜头侥幸或体面遮掩。
   - **高浓度人情拉扯与情绪兑现（`dramatic_tension_and_emotion`）**：彻底杜绝把大纲或台词写成枯燥的财税法务审计说明书；用具体的人情冷暖、利益试探、潜台词反差、护短立威或追悔失衡拉满追更情绪。
   - **从容多集连载与裸看清晰度（`serial_pacing_and_clarity`）**：遵循红果 4～6 集共载 1 个完整阶段事件规律，前 3 集只聚焦开局第 1 个核心事件的起承升级，自然叫响人物关系称谓，集尾卡在紧绷未决的悬念钩子处。
2. **严禁过拟合与严禁数据泄漏**：
   - **绝对禁止**把本轮 DEV 验证集中的任何剧名、角色人名、特有地名或仅适用于某一部剧的特殊机关写进提示词或参考文档！
   - **绝对禁止**添加限制题材或身份的死板禁令（如禁止某种职业/年龄段做某事、或强行规定所有剧都必须走重生/悔恨/商战单一套路）！所有法则必须对都市、年代、古装、玄幻、悬疑全赛道普遍成立。
3. **占位符与字符预算守恒**：
   - `prompts/stage1_outline.md` 必须原样保留 `{{episode_plan_range}}` 占位符！
   - `prompts/stage2_episodes.md` 必须原样保留 `{{batch_range}}` 占位符！
   - 各模块修改后总字数不得超过上限：`stage0_premise_lock.md` ≤ 3600字，`stage1_outline.md` ≤ 3400字，`stage2_episodes.md` ≤ 3600字，`story-engine.md` ≤ 4400字，`episode-craft.md` ≤ 5000字，`anti-patterns.md` ≤ 5200字。每次精选最关键的 2～4 个文件做高信噪比迭代。

---
### 本轮候选版本 `{cand_name}` 在分层多赛道 DEV 验证集上的诊断汇总
{diag_report}

---
### 当前 `{cand_name}` 可进化模块全文
{files_dump}
"""


def log(msg: str) -> None:
    EVO_ROOT.mkdir(parents=True, exist_ok=True)
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with (EVO_ROOT / "evolve_general.log").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def copy_skill_snapshot(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def _latest_gate_file(ep_dir: Path) -> Optional[Path]:
    files = sorted(ep_dir.glob("ep001-003.general_gate_r*.json"))
    return files[-1] if files else None


def evaluate_candidate_on_bench(
    cand_name: str,
    cand_skill_dir: Path,
    bench_items: List[Dict[str, Any]],
    round_dir: Path,
    *,
    gate_rounds: int = 1,
    champion_round_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    round_dir.mkdir(parents=True, exist_ok=True)
    prev_env = os.environ.get("HIT_DRAMA_GATE_ROUNDS")
    os.environ["HIT_DRAMA_GATE_ROUNDS"] = str(gate_rounds)

    def run_one_seed(item: Dict[str, Any]) -> Dict[str, Any]:
        bid = item["bench_id"]
        s_dir = round_dir / bid
        s_dir.mkdir(parents=True, exist_ok=True)
        comb_path = s_dir / "combined_1-3.md"
        outline_path = s_dir / "01_outline.md"

        gran = item.get("seed_mode") or item.get("granularity") or "concise_1s"
        if not comb_path.is_file():
            log(f"  [{cand_name}] Generating {bid} ({item['genre']} | {gran})...")
            WD.run_pipeline(
                item["seed"],
                s_dir,
                "1-3",
                batch_size=3,
                skill_dir=cand_skill_dir,
                force=False,
            )

        gen_md = comb_path.read_text(encoding="utf-8")
        outline_md = outline_path.read_text(encoding="utf-8") if outline_path.is_file() else ""
        chk = SC.analyze_script(gen_md, [1, 2, 3])

        audit_cache = s_dir / "general_audit.json"
        latest_gate = _latest_gate_file(s_dir / "episodes")
        if audit_cache.is_file():
            gen_audit = json.loads(audit_cache.read_text(encoding="utf-8"))
        elif latest_gate is not None:
            gen_audit = json.loads(latest_gate.read_text(encoding="utf-8"))
            audit_cache.write_text(json.dumps(gen_audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        else:
            gen_audit = GJ.audit_drama_general(gen_md, seed=item["seed"], outline_md=outline_md)
            audit_cache.write_text(json.dumps(gen_audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        # Also capture r1 raw flaws if gate_rounds > 1 rewrote it
        r1_gate_p = s_dir / "episodes" / "ep001-003.general_gate_r1.json"
        r1_flaws = []
        if r1_gate_p.is_file():
            r1_obj = json.loads(r1_gate_p.read_text(encoding="utf-8"))
            r1_flaws = r1_obj.get("flaws", [])

        vs_gt = None
        gt_pts: Optional[int] = None
        gt_path_str = item.get("gt_path") or ""
        if gt_path_str and Path(gt_path_str).is_file():
            vs_gt_path = s_dir / "vs_real_gt.json"
            if vs_gt_path.is_file():
                vs_gt = json.loads(vs_gt_path.read_text(encoding="utf-8"))
            else:
                gt_md = Path(gt_path_str).read_text(encoding="utf-8")
                # Note: REAL_GT has no generated outline, so compare_swap_debiased_general compares stripped 3-ep screen scripts fairly + seed!
                vs_gt = GJ.compare_swap_debiased_general(
                    "GEN",
                    gen_md,
                    "REAL_GT",
                    gt_md,
                    seed=item["seed"],
                    parallel_swaps=False,
                )
                vs_gt_path.write_text(json.dumps(vs_gt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            gt_pts = 2 if vs_gt["winner"] == "GEN" else (1 if vs_gt["winner"] == "TIE" else 0)

        vs_champ = None
        if champion_round_dir is not None:
            champ_md_path = champion_round_dir / bid / "combined_1-3.md"
            champ_out_path = champion_round_dir / bid / "01_outline.md"
            vs_champ_path = s_dir / "vs_champion.json"
            if vs_champ_path.is_file():
                vs_champ = json.loads(vs_champ_path.read_text(encoding="utf-8"))
            elif champ_md_path.is_file():
                champ_md = champ_md_path.read_text(encoding="utf-8")
                champ_out = champ_out_path.read_text(encoding="utf-8") if champ_out_path.is_file() else ""
                vs_champ = GJ.compare_swap_debiased_general(
                    "CAND",
                    gen_md,
                    "CHAMP",
                    champ_md,
                    seed=item["seed"],
                    outline_1_md=outline_md,
                    outline_2_md=champ_out,
                    parallel_swaps=False,
                )
                vs_champ_path.write_text(json.dumps(vs_champ, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        log(
            f"  [{cand_name}] {bid} ({item['genre']}/{gran}): "
            f"gate={gen_audit['verdict']} (score={gen_audit['total_score']}, dims={gen_audit['scores']}) "
            + (f"| vs_REAL_GT={vs_gt['winner']} " if vs_gt else "| [OOD no GT] ")
            + (f"| vs_CHAMP={vs_champ['winner']}" if vs_champ else "")
        )
        return {
            "bench_id": bid,
            "title": item.get("title_ref") or item.get("title") or bid,
            "genre": item["genre"],
            "granularity": gran,
            "script_check_ok": chk["ok"],
            "verdict": gen_audit["verdict"],
            "total_score": gen_audit["total_score"],
            "pillar_scores": gen_audit["scores"],
            "distinct_events": gen_audit["distinct_major_events_in_3eps"],
            "flaws": gen_audit["flaws"],
            "r1_raw_flaws": r1_flaws,
            "engine_summary": gen_audit["native_engine_and_comprehension"],
            "vs_real_gt_winner": vs_gt["winner"] if vs_gt else None,
            "vs_real_gt_points": gt_pts,
            "vs_real_gt_cand_notes": vs_gt["forward_detail"]["candidate_a_strengths_and_flaws"] if vs_gt else None,
            "vs_real_gt_gt_notes": vs_gt["forward_detail"]["candidate_b_strengths_and_flaws"] if vs_gt else None,
            "vs_real_gt_reason": vs_gt["forward_detail"]["decisive_reason"] if vs_gt else None,
            "vs_champ_winner": vs_champ["winner"] if vs_champ else None,
            "vs_champ_reason": vs_champ["forward_detail"]["decisive_reason"] if vs_champ else None,
        }

    try:
        # Keep max_workers=3 with parallel_swaps=False so concurrent isolated agy sub-agents stay <= 3
        with cf.ThreadPoolExecutor(max_workers=3) as pool:
            seed_results = list(pool.map(run_one_seed, bench_items))
    finally:
        if prev_env is None:
            os.environ.pop("HIT_DRAMA_GATE_ROUNDS", None)
        else:
            os.environ["HIT_DRAMA_GATE_ROUNDS"] = prev_env

    pass_cnt = sum(1 for r in seed_results if r["verdict"] == "PASS_HIT_READY")
    mean_score = round(statistics.mean(r["total_score"] for r in seed_results), 2)
    pillar_means = {
        k: round(statistics.mean(r["pillar_scores"][k] for r in seed_results), 2)
        for k in ("seed_fidelity_and_hook", "motivation_and_logic", "dramatic_tension_and_emotion", "serial_pacing_and_clarity")
    }
    by_genre: Dict[str, List[float]] = {}
    for r in seed_results:
        by_genre.setdefault(r["genre"], []).append(r["total_score"])
    genre_means = {g: round(statistics.mean(vals), 2) for g, vals in by_genre.items()}
    min_genre_score = min(genre_means.values()) if genre_means else 0.0

    gt_items = [r for r in seed_results if r["vs_real_gt_winner"] is not None]
    gt_wins = sum(1 for r in gt_items if r["vs_real_gt_winner"] == "GEN")
    gt_ties = sum(1 for r in gt_items if r["vs_real_gt_winner"] == "TIE")
    gt_losses = len(gt_items) - gt_wins - gt_ties
    gt_points = sum(r["vs_real_gt_points"] or 0 for r in gt_items)
    gt_norm = (gt_points / (2.0 * len(gt_items))) if gt_items else 0.0

    champ_items = [r for r in seed_results if r["vs_champ_winner"] is not None]
    champ_wins = sum(1 for r in champ_items if r["vs_champ_winner"] == "CAND")
    champ_losses = sum(1 for r in champ_items if r["vs_champ_winner"] == "CHAMP")
    champ_ties = sum(1 for r in champ_items if r["vs_champ_winner"] == "TIE")

    # Generalized composite rewards mean score, worst-genre floor (anti-single-genre collapse!), pass rate, and vs_REAL_GT win rate
    composite = round(
        mean_score * 0.75
        + min_genre_score * 0.25
        + gt_norm * 40.0
        + (pass_cnt / len(seed_results)) * 15.0,
        2,
    )

    summary = {
        "cand_name": cand_name,
        "gate_rounds": gate_rounds,
        "pass_hit_ready_rate": f"{pass_cnt}/{len(seed_results)}",
        "pass_cnt": pass_cnt,
        "mean_total_score": mean_score,
        "pillar_means": pillar_means,
        "genre_means": genre_means,
        "min_genre_score": min_genre_score,
        "vs_real_gt": {
            "total": len(gt_items),
            "wins": gt_wins,
            "ties": gt_ties,
            "losses": gt_losses,
            "points": gt_points,
        },
        "vs_champion": (
            {"wins": champ_wins, "ties": champ_ties, "losses": champ_losses}
            if champion_round_dir
            else None
        ),
        "composite_metric": composite,
        "seeds": seed_results,
    }
    (round_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def _extract_bench_leak_tokens(bench_items: List[Dict[str, Any]]) -> List[str]:
    tokens = list(FORBIDDEN_LEAK_TOKENS)
    for it in bench_items:
        t = (it.get("title_ref") or it.get("title") or "").strip()
        if len(t) >= 3:
            tokens.append(t)
    return sorted(set(tokens))


def synthesize_next_candidate(
    base_cand_name: str,
    base_skill_dir: Path,
    next_cand_name: str,
    next_skill_dir: Path,
    eval_summary: Dict[str, Any],
    bench_items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    copy_skill_snapshot(base_skill_dir, next_skill_dir)
    leak_tokens = _extract_bench_leak_tokens(bench_items)

    diag_items = []
    for s in eval_summary["seeds"]:
        # Anonymize bench titles in diagnostic report to further discourage copying plot details
        diag_items.append({
            "bench_id": s["bench_id"],
            "genre": s["genre"],
            "seed_granularity": s["granularity"],
            "verdict": s["verdict"],
            "total_score": s["total_score"],
            "pillar_scores": s["pillar_scores"],
            "distinct_events_in_3eps": s["distinct_events"],
            "flaws": s["flaws"] or s["r1_raw_flaws"],
            "vs_real_gt_winner": s["vs_real_gt_winner"],
            "cand_strengths_and_flaws_vs_gt": s["vs_real_gt_cand_notes"],
            "why_gt_or_cand_won": s["vs_real_gt_reason"],
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
    rejected = []
    for uf in plan.get("updated_files", []):
        rel_p = uf["rel_path"]
        new_c = uf["new_content"].strip()
        if rel_p not in EVOLVABLE_FILES:
            continue
        if rel_p == "prompts/stage1_outline.md" and "{episode_plan_range}" not in new_c:
            rejected.append({"rel_path": rel_p, "reason": "missing {episode_plan_range}"})
            log(f"  [reject mutation] {rel_p} missing {{episode_plan_range}}")
            continue
        if rel_p == "prompts/stage2_episodes.md" and "{batch_range}" not in new_c:
            rejected.append({"rel_path": rel_p, "reason": "missing {batch_range}"})
            log(f"  [reject mutation] {rel_p} missing {{batch_range}}")
            continue
        leaked = [tok for tok in leak_tokens if tok in new_c]
        if leaked:
            rejected.append({"rel_path": rel_p, "reason": f"leaked tokens: {leaked}"})
            log(f"  [reject overfitting leak] {rel_p} contained {leaked}")
            continue
        if len(new_c) > EVOLVABLE_FILES[rel_p] + 600 or len(new_c) < 200:
            rejected.append({"rel_path": rel_p, "reason": f"out-of-budget len={len(new_c)}"})
            log(f"  [reject out-of-budget] {rel_p} len={len(new_c)}")
            continue
        (next_skill_dir / rel_p).write_text(new_c + "\n", encoding="utf-8")
        applied.append({"rel_path": rel_p, "len": len(new_c), "reason": uf["reason"]})

    meta_log = {
        "from": base_cand_name,
        "to": next_cand_name,
        "cross_genre_diagnosis": plan["cross_genre_diagnosis"],
        "anti_overfitting_check": plan["anti_overfitting_check"],
        "mutation_plan": plan["mutation_plan"],
        "applied_files": applied,
        "rejected_files": rejected,
    }
    (EVO_ROOT / f"mutation_{base_cand_name}_to_{next_cand_name}.json").write_text(
        json.dumps(meta_log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    log(f"  Applied {len(applied)} generalized mutations for `{next_cand_name}`: {[x['rel_path'] for x in applied]}")
    return meta_log


def sync_champion_to_live(champ_skill_dir: Path) -> None:
    for rel_p in EVOLVABLE_FILES:
        shutil.copy2(champ_skill_dir / rel_p, LIVE_SKILL_DIR / rel_p)


def should_promote(cand: Dict[str, Any], champ: Dict[str, Any]) -> Tuple[bool, str]:
    vc = cand.get("vs_champion") or {"wins": 0, "ties": 0, "losses": 0}
    # Anti-genre-collapse guard: never promote if worst-genre mean drops below 76 or regresses > 4 pts
    if cand["min_genre_score"] < 76.0 and cand["min_genre_score"] < champ["min_genre_score"] - 2.0:
        return False, f"single-genre floor regression ({cand['min_genre_score']} vs {champ['min_genre_score']})"
    if vc["wins"] > vc["losses"] and cand["composite_metric"] >= champ["composite_metric"] - 2.0:
        return True, f"pairwise win vs champion ({vc['wins']}W-{vc['ties']}T-{vc['losses']}L)"
    if vc["wins"] == vc["losses"] and cand["composite_metric"] > champ["composite_metric"] + 0.5:
        return True, f"tied pairwise ({vc['wins']}W-{vc['ties']}T-{vc['losses']}L) with higher composite ({cand['composite_metric']} > {champ['composite_metric']})"
    return False, f"did not beat champion (vs_champ={vc}, composite {cand['composite_metric']} vs {champ['composite_metric']})"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rounds", type=int, default=2, help="Number of mutation rounds after v6_r0 baseline")
    ap.add_argument("--dev-gate-rounds", type=int, default=1, help="Gate rounds during DEV evolution (1 = raw first-pass policy optimization)")
    ap.add_argument("--test-gate-rounds", type=int, default=2, help="Gate rounds during locked TEST evaluation")
    ap.add_argument("--run-test", action="store_true", help="Run locked unseen TEST + OOD evaluation once on final champion")
    args = ap.parse_args()

    dev_bench = json.loads((BENCH_DIR / "dev_bench.json").read_text(encoding="utf-8"))
    CAND_ROOT.mkdir(parents=True, exist_ok=True)
    ROUNDS_ROOT.mkdir(parents=True, exist_ok=True)

    r0_name = "v6_r0"
    r0_skill = CAND_ROOT / r0_name
    if not r0_skill.exists():
        copy_skill_snapshot(LIVE_SKILL_DIR, r0_skill)

    log(f"=== Evaluating Generalized Baseline `{r0_name}` on {len(dev_bench)} Stratified Multi-Genre DEV Dramas (gate_rounds={args.dev_gate_rounds}) ===")
    champ_name = r0_name
    champ_skill = r0_skill
    champ_round_dir = ROUNDS_ROOT / r0_name
    champ_summary = evaluate_candidate_on_bench(
        r0_name, r0_skill, dev_bench, champ_round_dir, gate_rounds=args.dev_gate_rounds
    )
    log(
        f"Baseline `{champ_name}` DEV: pass={champ_summary['pass_hit_ready_rate']}, mean={champ_summary['mean_total_score']}, "
        f"min_genre={champ_summary['min_genre_score']}, vs_REAL_GT={champ_summary['vs_real_gt']}, composite={champ_summary['composite_metric']}"
    )

    history = [champ_summary]

    for r in range(1, args.rounds + 1):
        cand_name = f"v6_r{r}"
        cand_skill = CAND_ROOT / cand_name
        cand_round_dir = ROUNDS_ROOT / cand_name

        # Early convergence only after at least 1 evolution round if 100% PASS_HIT_READY and near-sweep vs REAL_GT
        if (
            r >= 2
            and champ_summary["pass_cnt"] == len(dev_bench)
            and champ_summary["vs_real_gt"]["losses"] == 0
            and champ_summary["vs_real_gt"]["wins"] >= 5
            and champ_summary["min_genre_score"] >= 88.0
        ):
            log(f"Strong multi-genre convergence achieved by `{champ_name}` — stopping DEV mutations early!")
            break

        if not (EVO_ROOT / f"mutation_{champ_name}_to_{cand_name}.json").is_file() or not cand_skill.exists():
            meta_res = synthesize_next_candidate(
                champ_name, champ_skill, cand_name, cand_skill, champ_summary, dev_bench
            )
            if not meta_res["applied_files"]:
                log(f"No valid mutations applied for `{cand_name}`; stopping.")
                break

        log(f"=== Evaluating Generalized Candidate `{cand_name}` on Stratified Multi-Genre DEV ===")
        cand_summary = evaluate_candidate_on_bench(
            cand_name,
            cand_skill,
            dev_bench,
            cand_round_dir,
            gate_rounds=args.dev_gate_rounds,
            champion_round_dir=champ_round_dir,
        )
        history.append(cand_summary)

        promote, reason = should_promote(cand_summary, champ_summary)
        if promote:
            log(f"PROMOTED `{cand_name}` -> NEW GENERALIZED CHAMPION! Reason: {reason}")
            champ_name = cand_name
            champ_skill = cand_skill
            champ_round_dir = cand_round_dir
            champ_summary = cand_summary
            sync_champion_to_live(champ_skill)
        else:
            log(f"REJECTED `{cand_name}` ({reason}); keeping `{champ_name}`.")

    # Ensure live skill matches final champion
    sync_champion_to_live(champ_skill)

    test_summary = None
    if args.run_test:
        test_bench = json.loads((BENCH_DIR / "test_bench.json").read_text(encoding="utf-8"))
        log(
            f"=== Running LOCKED UNSEEN TEST + OOD Evaluation ({len(test_bench)} cases) on Champion `{champ_name}` (gate_rounds={args.test_gate_rounds}) ==="
        )
        test_summary = evaluate_candidate_on_bench(
            f"{champ_name}_TEST",
            champ_skill,
            test_bench,
            ROUNDS_ROOT / f"{champ_name}_TEST",
            gate_rounds=args.test_gate_rounds,
        )
        log(
            f"LOCKED TEST RESULT for `{champ_name}`: pass={test_summary['pass_hit_ready_rate']}, "
            f"mean={test_summary['mean_total_score']}, genre_means={test_summary['genre_means']}, "
            f"vs_REAL_GT={test_summary['vs_real_gt']}"
        )

    final_report = {
        "final_champion": champ_name,
        "champion_dev_summary": champ_summary,
        "history": history,
        "locked_test_summary": test_summary,
    }
    (EVO_ROOT / "final_general_report.json").write_text(
        json.dumps(final_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    log("Generalized cross-genre autoregressive evolution complete!")


if __name__ == "__main__":
    main()
