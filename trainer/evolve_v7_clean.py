#!/usr/bin/env python3
"""
Zero-Overfitting Joint Dramatic-Tension & Pure-Dialogue Autoregressive Engine (`trainer/evolve_v7_clean.py`).

Addresses all 4 root causes identified in the overfitting audit of `d1..d3`:
  1. End-to-End First-Principles Generation (`Stage 0 -> Stage 1 -> Stage 2 -> Stage 2.5`) with ZERO foreign-drama
     raw-snippet injection (eliminating cross-drama Northern dialect & prop contamination).
  2. De-Goodharted Joint Arena: Evaluates every candidate on an expanded 8-drama multi-genre/multi-tension `DEV` set
     across BOTH `general_arena_judge` (dramatic tension, premise fidelity, motivation, state shift) AND
     `dialogue_turing_judge` (pure stripped spoken ear-test with regex stats removed from judge prompts).
  3. 3-Agent Information-Theoretic Anti-Overfitting Bottleneck:
     - Agent 1 (`Plot-Blind Bottleneck`): Strips all plots, quotes, props, roles, and words from `DEV` diagnostics,
       outputting ONLY abstract structural/linguistic failure frequencies.
     - Agent 2 (`Blind Meta-Optimizer`): Sees ONLY Agent 1's plot-blind summary + current skill files (never sees `DEV`!).
     - Agent 3 (`Anti-Overfitting Prosecutor`): Rejects any diff introducing `%` quotas, everyday-word bans, narrow
       trope examples, or closed rhythm/genre enums!
  4. Locked `TEST + OOD` (`7` unseen cases including `test_ood_hotpot2005`) evaluated strictly ONCE on final champion.
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
EVO_ROOT = TRAIN_ROOT / "runs" / "v7_clean_evolution"
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
import prepare_general_bench as PGB  # noqa: E402
import script_check as SC  # noqa: E402
import write_drama as WD  # noqa: E402

EVOLVABLE_FILES: Dict[str, int] = {
    "prompts/stage0_premise_lock.md": 3600,
    "prompts/stage1_outline.md": 3400,
    "prompts/stage2_episodes.md": 3600,
    "prompts/stage2_5_dialogue_polish.md": 3400,
    "references/dialogue-voice.md": 4200,
    "references/episode-craft.md": 5000,
}

FORBIDDEN_PATTERNS = [
    re.compile(r"(?<!\d)\d{1,2}\s*[%％]"),  # Block 1%..99% Goodhart quotas ("18%～30%", "≤30%") while allowing "100%"
    re.compile(r"略略略|海豚|向阳大房|孙掌柜|枯木抽|废标底|叶寻|林双双|楚南|赵帆|夏芊芊"),
]

BOTTLENECK_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "abstract_tension_bottlenecks": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "maxItems": 4,
            "description": "跨多部剧普遍存在的戏剧张力/叙事推进共性短板（严格禁止出现任何具体台词引文、职业、道具、人物关系、地名或具体词汇！只能用纯叙事学抽象语言描述，每条80字内）",
        },
        "abstract_dialogue_bottlenecks": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "maxItems": 4,
            "description": "跨多部剧普遍存在的口语自然度/潜台词共性短板（严格禁止出现任何具体台词引文、具体方言词例、具体道具或桥段！只能用纯语言学/表演学抽象语言描述，每条80字内）",
        },
    },
    "required": ["abstract_tension_bottlenecks", "abstract_dialogue_bottlenecks"],
    "additionalProperties": False,
}

BLIND_META_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "evolution_rationale": {"type": "string"},
        "updated_files": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "rel_path": {"type": "string", "enum": list(EVOLVABLE_FILES.keys())},
                    "reason": {"type": "string"},
                    "new_content": {"type": "string"},
                },
                "required": ["rel_path", "reason", "new_content"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["evolution_rationale", "updated_files"],
    "additionalProperties": False,
}

ANTI_OVERFIT_AUDIT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "is_clean_and_general": {"type": "boolean"},
        "overfitting_violations": {
            "type": "array",
            "items": {"type": "string"},
            "description": "若存在以下任一过拟合现象则逐条列出：1.机械百分比配额（如短句占XX%、感叹号≤XX%）；2.一刀切封杀正常高频现代口语词（如好嘞、喏）；3.窄化到单一题材/单一节奏套路枚举；4.塞入高度具体的特定剧情/特定道具补丁案例。完全普适干净则返回 []",
        },
    },
    "required": ["is_clean_and_general", "overfitting_violations"],
    "additionalProperties": False,
}


def log(msg: str) -> None:
    EVO_ROOT.mkdir(parents=True, exist_ok=True)
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with (EVO_ROOT / "evolve_v7_clean.log").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def copy_skill_snapshot(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def ensure_expanded_dev8_bench() -> List[Dict[str, Any]]:
    dev8_path = BENCH_DIR / "dev8_bench.json"
    if dev8_path.is_file():
        return json.loads(dev8_path.read_text(encoding="utf-8"))

    base_dev6 = json.loads((BENCH_DIR / "dev_bench.json").read_text(encoding="utf-8"))
    manifest = json.loads((TRAIN_ROOT / "corpus" / "manifest.json").read_text(encoding="utf-8"))["dramas"]
    by_id = {v["id"]: v for v in manifest.values()}

    extra_specs = [
        ("036", "rich_brief"),   # 万米高空的反击 (高空危机/专业反击，非婚姻套路)
        ("107", "concise_1s"),   # 穿进年代文，我成了团宠恶毒女配 (穿书反差温情轻喜)
    ]
    dev_dir = BENCH_DIR / "dev"
    dev_dir.mkdir(parents=True, exist_ok=True)

    for did, smode in extra_specs:
        d = by_id[did]
        bid = f"dev_{did}"
        gt_path = dev_dir / f"{bid}_gt_ep001-003.md"
        log(f"[dev8-prep] Preparing extra stratified DEV item {bid} ({d['genre']} | {smode})...")
        gt_md = PGB.convert_3ep_for_drama(d, gt_path)
        if smode == "rich_brief" and d.get("has_summary_md") and Path(d["summary_path"]).is_file():
            sum_md = Path(d["summary_path"]).read_text(encoding="utf-8")
            seed = L.call_agy(
                PGB.RICH_BRIEF_SEED_PROMPT.format(summary_md=sum_md[:5000], script_3ep=gt_md[:7000]),
                timeout=360,
            ).strip()
        else:
            seed = L.call_agy(PGB.CONCISE_SEED_PROMPT.format(script_3ep=gt_md[:7500]), timeout=360).strip()
        base_dev6.append({
            "bench_id": bid,
            "drama_id": did,
            "split": "dev",
            "genre": d["genre"],
            "title_ref": d["title"],
            "seed_mode": smode,
            "seed": seed,
            "gt_path": str(gt_path),
        })

    dev8_path.write_text(json.dumps(base_dev6, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log(f"[dev8-prep] Saved 8-drama Stratified Multi-Genre/Multi-Tension DEV benchmark -> {dev8_path}")
    return base_dev6


def evaluate_joint_candidate(
    cand_name: str,
    cand_skill_dir: Path,
    bench_items: List[Dict[str, Any]],
    round_dir: Path,
    *,
    gate_rounds: int = 1,
    champion_round_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    round_dir.mkdir(parents=True, exist_ok=True)
    prev_gate = os.environ.get("HIT_DRAMA_GATE_ROUNDS")
    prev_pol = os.environ.get("HIT_DRAMA_DIALOGUE_POLISH")
    os.environ["HIT_DRAMA_GATE_ROUNDS"] = str(gate_rounds)
    os.environ["HIT_DRAMA_DIALOGUE_POLISH"] = "1"

    def run_one(item: Dict[str, Any]) -> Dict[str, Any]:
        bid = item["bench_id"]
        gran = item.get("seed_mode") or "concise_1s"
        s_dir = round_dir / bid
        s_dir.mkdir(parents=True, exist_ok=True)

        comb_path = s_dir / "combined_1-3.md"
        if not comb_path.is_file():
            log(f"  [{cand_name}] End-to-End Generating {bid} ({item['genre']} | {gran})...")
            WD.run_pipeline(
                item["seed"],
                s_dir,
                "1-3",
                batch_size=3,
                skill_dir=cand_skill_dir,
                force=False,
            )

        gen_md = comb_path.read_text(encoding="utf-8")
        outline_md = (s_dir / "01_outline.md").read_text(encoding="utf-8")

        # 1. General Tension & Premise Audit
        gen_audit_p = s_dir / "general_audit.json"
        gate_files = sorted((s_dir / "episodes").glob("ep001-003.general_gate_r*.json"))
        if gen_audit_p.is_file():
            g_audit = json.loads(gen_audit_p.read_text(encoding="utf-8"))
        elif gate_files:
            g_audit = json.loads(gate_files[-1].read_text(encoding="utf-8"))
            gen_audit_p.write_text(json.dumps(g_audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        else:
            g_audit = GJ.audit_drama_general(gen_md, seed=item["seed"], outline_md=outline_md)
            gen_audit_p.write_text(json.dumps(g_audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        # 2. De-Goodharted Pure-Dialogue Turing Audit
        dlg_audit_p = s_dir / "dialogue_turing.json"
        if dlg_audit_p.is_file():
            d_audit = json.loads(dlg_audit_p.read_text(encoding="utf-8"))
        else:
            d_audit = DTJ.audit_dialogue_turing(gen_md, genre_hint=item["genre"])
            dlg_audit_p.write_text(json.dumps(d_audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        # 3. Swap-Debiased Pairwise PKs vs REAL_GT (BOTH Tension Arena AND Pure-Dialogue Arena!)
        vs_gt_ten, vs_gt_dlg = None, None
        ten_pts, dlg_pts = 0, 0
        gt_path_str = item.get("gt_path") or ""
        if gt_path_str and Path(gt_path_str).is_file():
            gt_md = Path(gt_path_str).read_text(encoding="utf-8")
            p_ten = s_dir / "vs_real_gt_tension.json"
            if p_ten.is_file():
                vs_gt_ten = json.loads(p_ten.read_text(encoding="utf-8"))
            else:
                vs_gt_ten = GJ.compare_swap_debiased_general(
                    "GEN", gen_md, "REAL_GT", gt_md, seed=item["seed"], parallel_swaps=False
                )
                p_ten.write_text(json.dumps(vs_gt_ten, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            ten_pts = 2 if vs_gt_ten["winner"] == "GEN" else (1 if vs_gt_ten["winner"] == "TIE" else 0)

            p_dlg = s_dir / "vs_real_gt_dialogue.json"
            if p_dlg.is_file():
                vs_gt_dlg = json.loads(p_dlg.read_text(encoding="utf-8"))
            else:
                vs_gt_dlg = DTJ.compare_swap_debiased_dialogue(
                    "GEN", gen_md, "REAL_GT", gt_md, genre_hint=item["genre"], parallel_swaps=False
                )
                p_dlg.write_text(json.dumps(vs_gt_dlg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            dlg_pts = 2 if vs_gt_dlg["winner"] == "GEN" else (1 if vs_gt_dlg["winner"] == "TIE" else 0)

        # 4. Swap-Debiased Pairwise PKs vs Current Champion (BOTH Tension AND Pure-Dialogue!)
        vs_ch_ten, vs_ch_dlg = None, None
        if champion_round_dir is not None:
            ch_md_p = champion_round_dir / bid / "combined_1-3.md"
            ch_out_p = champion_round_dir / bid / "01_outline.md"
            if ch_md_p.is_file():
                ch_md = ch_md_p.read_text(encoding="utf-8")
                ch_out = ch_out_p.read_text(encoding="utf-8") if ch_out_p.is_file() else ""
                pt = s_dir / "vs_champ_tension.json"
                if pt.is_file():
                    vs_ch_ten = json.loads(pt.read_text(encoding="utf-8"))
                else:
                    vs_ch_ten = GJ.compare_swap_debiased_general(
                        "CAND", gen_md, "CHAMP", ch_md, seed=item["seed"], outline_1_md=outline_md, outline_2_md=ch_out, parallel_swaps=False
                    )
                    pt.write_text(json.dumps(vs_ch_ten, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

                pd = s_dir / "vs_champ_dialogue.json"
                if pd.is_file():
                    vs_ch_dlg = json.loads(pd.read_text(encoding="utf-8"))
                else:
                    vs_ch_dlg = DTJ.compare_swap_debiased_dialogue(
                        "CAND", gen_md, "CHAMP", ch_md, genre_hint=item["genre"], parallel_swaps=False
                    )
                    pd.write_text(json.dumps(vs_ch_dlg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        log(
            f"  [{cand_name}] {bid} ({item['genre']}/{gran}): "
            f"ten={g_audit['verdict']}({g_audit['total_score']}) dlg={d_audit['verdict']}({d_audit['total_score']}) "
            + (f"| vs_GT[ten={vs_gt_ten['winner']}, dlg={vs_gt_dlg['winner']}] " if vs_gt_ten else "| [OOD] ")
            + (f"| vs_CHAMP[ten={vs_ch_ten['winner']}, dlg={vs_ch_dlg['winner']}]" if vs_ch_ten else "")
        )
        return {
            "bench_id": bid,
            "genre": item["genre"],
            "granularity": gran,
            "ten_verdict": g_audit["verdict"],
            "ten_score": g_audit["total_score"],
            "ten_flaws": g_audit["flaws"],
            "dlg_verdict": d_audit["verdict"],
            "dlg_score": d_audit["total_score"],
            "dlg_defects": d_audit["ai_voice_defects"],
            "vs_gt_ten": vs_gt_ten["winner"] if vs_gt_ten else None,
            "vs_gt_ten_reason": vs_gt_ten["forward_detail"]["decisive_reason"] if vs_gt_ten else None,
            "vs_gt_ten_pts": ten_pts if vs_gt_ten else None,
            "vs_gt_dlg": vs_gt_dlg["winner"] if vs_gt_dlg else None,
            "vs_gt_dlg_notes": vs_gt_dlg["forward_detail"]["candidate_a_voice_analysis"] if vs_gt_dlg else None,
            "vs_gt_dlg_pts": dlg_pts if vs_gt_dlg else None,
            "vs_ch_ten": vs_ch_ten["winner"] if vs_ch_ten else None,
            "vs_ch_dlg": vs_ch_dlg["winner"] if vs_ch_dlg else None,
        }

    try:
        with cf.ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(run_one, bench_items))
    finally:
        if prev_gate is None:
            os.environ.pop("HIT_DRAMA_GATE_ROUNDS", None)
        else:
            os.environ["HIT_DRAMA_GATE_ROUNDS"] = prev_gate
        if prev_pol is None:
            os.environ.pop("HIT_DRAMA_DIALOGUE_POLISH", None)
        else:
            os.environ["HIT_DRAMA_DIALOGUE_POLISH"] = prev_pol

    ten_pass = sum(1 for r in results if r["ten_verdict"] == "PASS_HIT_READY")
    dlg_pass = sum(1 for r in results if r["dlg_verdict"] == "PASS_HUMAN_NATURAL")
    mean_ten = round(statistics.mean(r["ten_score"] for r in results), 2)
    mean_dlg = round(statistics.mean(r["dlg_score"] for r in results), 2)

    gt_items = [r for r in results if r["vs_gt_ten"] is not None]
    gt_ten_rec = {
        "wins": sum(1 for r in gt_items if r["vs_gt_ten"] == "GEN"),
        "ties": sum(1 for r in gt_items if r["vs_gt_ten"] == "TIE"),
        "losses": sum(1 for r in gt_items if r["vs_gt_ten"] == "REAL_GT"),
        "points": sum(r["vs_gt_ten_pts"] or 0 for r in gt_items),
    }
    gt_dlg_rec = {
        "wins": sum(1 for r in gt_items if r["vs_gt_dlg"] == "GEN"),
        "ties": sum(1 for r in gt_items if r["vs_gt_dlg"] == "TIE"),
        "losses": sum(1 for r in gt_items if r["vs_gt_dlg"] == "REAL_GT"),
        "points": sum(r["vs_gt_dlg_pts"] or 0 for r in gt_items),
    }

    ch_ten_rec, ch_dlg_rec = None, None
    if champion_round_dir is not None:
        ch_items = [r for r in results if r["vs_ch_ten"] is not None]
        ch_ten_rec = {
            "wins": sum(1 for r in ch_items if r["vs_ch_ten"] == "CAND"),
            "ties": sum(1 for r in ch_items if r["vs_ch_ten"] == "TIE"),
            "losses": sum(1 for r in ch_items if r["vs_ch_ten"] == "CHAMP"),
        }
        ch_dlg_rec = {
            "wins": sum(1 for r in ch_items if r["vs_ch_dlg"] == "CAND"),
            "ties": sum(1 for r in ch_items if r["vs_ch_dlg"] == "TIE"),
            "losses": sum(1 for r in ch_items if r["vs_ch_dlg"] == "CHAMP"),
        }

    gt_norm = (
        (gt_ten_rec["points"] + gt_dlg_rec["points"]) / (4.0 * len(gt_items))
        if gt_items
        else 0.0
    )
    composite = round(
        mean_ten * 0.5
        + mean_dlg * 0.5
        + gt_norm * 50.0
        + ((ten_pass + dlg_pass) / (2.0 * len(results))) * 15.0,
        2,
    )

    summary = {
        "cand_name": cand_name,
        "tension_pass_rate": f"{ten_pass}/{len(results)}",
        "dialogue_pass_rate": f"{dlg_pass}/{len(results)}",
        "mean_tension_score": mean_ten,
        "mean_dialogue_score": mean_dlg,
        "vs_real_gt_tension": gt_ten_rec,
        "vs_real_gt_dialogue": gt_dlg_rec,
        "vs_champ_tension": ch_ten_rec,
        "vs_champ_dialogue": ch_dlg_rec,
        "composite_metric": composite,
        "seeds": results,
    }
    (round_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def synthesize_clean_candidate(
    base_name: str,
    base_skill_dir: Path,
    next_name: str,
    next_skill_dir: Path,
    eval_summary: Dict[str, Any],
) -> Dict[str, Any]:
    copy_skill_snapshot(base_skill_dir, next_skill_dir)

    # AGENT 1: Plot-Blind Bottleneck Summarizer (strips ALL quotes, props, roles, and words!)
    raw_diag = [
        {
            "case_idx": idx + 1,
            "ten_winner_vs_gt": s["vs_gt_ten"],
            "ten_reason": s["vs_gt_ten_reason"],
            "dlg_winner_vs_gt": s["vs_gt_dlg"],
            "dlg_notes": s["vs_gt_dlg_notes"],
        }
        for idx, s in enumerate(eval_summary["seeds"])
    ]
    bottleneck_prompt = (
        "你是『防数据泄漏·去剧情抽象归因器』。请阅读以下多部匿名短剧的评测反馈，提炼出**至少在2部以上剧目中重复出现的底层叙事张力短板与口语自然度短板**。\n"
        "【最高安全红线】：你的输出将被交给盲态进化器，因此你的输出中**绝对禁止出现任何具体台词引文、具体人名/称呼、具体职业（如总裁/律师/猎户/公主）、具体道具（如灯牌/手机/房本/药草）、具体方言词例或具体剧情桥段**！只能使用纯叙事学、戏剧动作学与语言学的抽象概念描述问题本质。\n\n"
        + json.dumps(raw_diag, ensure_ascii=False, indent=2)
    )
    log(f"  [Anti-Overfit Layer 1] Distilling plot-blind abstract bottlenecks from `{base_name}`...")
    bottlenecks = L.call_agy_json(bottleneck_prompt, BOTTLENECK_SCHEMA, timeout=420)

    # AGENT 2: Blind Meta-Optimizer (NEVER sees DEV dramas, genres, plots, or quotes!)
    files_dump = "\n\n".join(
        f"=== FILE: {rp} (len={len((base_skill_dir / rp).read_text(encoding='utf-8'))} / max={mx}) ===\n"
        + (base_skill_dir / rp).read_text(encoding="utf-8")
        for rp, mx in EVOLVABLE_FILES.items()
    )
    meta_prompt = (
        "你是全赛道短剧编剧 Skill 盲态通用进化架构师。\n"
        "以下是完全脱敏的跨题材共性短板抽象摘要，请只针对最核心的 2～4 个模块做高泛化改进：\n"
        "1. **绝对禁止过拟合与刷指标**：严禁写入任何百分比数字配额（如XX%短句、感叹号≤XX%）；严禁一刀切封杀正常日常口语词（如好嘞、喏）；严禁设立封闭的题材或节奏分类枚举；严禁编造狭窄的具体剧情补丁！\n"
        "2. **占位符与预算守恒**：`stage1_outline.md` 必须保留 `{episode_plan_range}`，`stage2_episodes.md` 必须保留 `{batch_range}`；各文件字数不超过上限。\n\n"
        "### 跨题材抽象共性短板\n"
        + json.dumps(bottlenecks, ensure_ascii=False, indent=2)
        + "\n\n### 当前可进化模块全文\n"
        + files_dump
    )
    log(f"  [Anti-Overfit Layer 2] Running Blind Meta-Optimizer `{base_name}` -> `{next_name}`...")
    plan = L.call_agy_json(meta_prompt, BLIND_META_SCHEMA, timeout=600)

    applied, rejected = [], []
    for uf in plan.get("updated_files", []):
        rp = uf["rel_path"]
        nc = uf["new_content"].strip()
        if rp not in EVOLVABLE_FILES:
            continue
        if rp == "prompts/stage1_outline.md" and "{episode_plan_range}" not in nc:
            rejected.append({"rel_path": rp, "reason": "missing {episode_plan_range}"})
            continue
        if rp == "prompts/stage2_episodes.md" and "{batch_range}" not in nc:
            rejected.append({"rel_path": rp, "reason": "missing {batch_range}"})
            continue
        regex_hits = [pat.pattern for pat in FORBIDDEN_PATTERNS if pat.search(nc)]
        if regex_hits:
            rejected.append({"rel_path": rp, "reason": f"forbidden quota/patch regex: {regex_hits}"})
            log(f"  [Layer 3 Regex Reject] {rp}: {regex_hits}")
            continue
        if len(nc) > EVOLVABLE_FILES[rp] + 500 or len(nc) < 200:
            rejected.append({"rel_path": rp, "reason": f"out-of-budget len={len(nc)}"})
            continue

        # AGENT 3: Independent Anti-Overfitting Prosecutor!
        audit_p = (
            "你是『零过拟合独立检察官』。请严格审查以下拟更新的编剧 Skill 模块全文，检查是否混入了任何过拟合毒药：\n"
            "1. 机械百分比配额（如短句占XX%、感叹号不超XX%）；\n"
            "2. 一刀切禁用正常高频现代汉语词汇（如禁说“好嘞/喏”）；\n"
            "3. 封闭式单一套路/节奏枚举框；\n"
            "4. 只针对某一个极窄场景的特定剧情补丁。\n"
            "完全符合跨全题材通用第一性原理则返回 is_clean_and_general=true, overfitting_violations=[]。\n\n"
            f"=== 待审模块 {rp} ===\n{nc}"
        )
        audit = L.call_agy_json(audit_p, ANTI_OVERFIT_AUDIT_SCHEMA, timeout=300)
        if not audit["is_clean_and_general"] or audit["overfitting_violations"]:
            rejected.append({"rel_path": rp, "reason": f"Prosecutor rejected: {audit['overfitting_violations']}"})
            log(f"  [Layer 3 Prosecutor Reject] {rp}: {audit['overfitting_violations']}")
            continue

        (next_skill_dir / rp).write_text(nc + "\n", encoding="utf-8")
        applied.append({"rel_path": rp, "len": len(nc), "reason": uf["reason"]})

    meta_log = {
        "from": base_name,
        "to": next_name,
        "plot_blind_bottlenecks": bottlenecks,
        "evolution_rationale": plan["evolution_rationale"],
        "applied_files": applied,
        "rejected_files": rejected,
    }
    (EVO_ROOT / f"mutation_{base_name}_to_{next_name}.json").write_text(
        json.dumps(meta_log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    log(f"  Applied {len(applied)} verified clean mutations for `{next_name}`: {[x['rel_path'] for x in applied]}")
    return meta_log


def sync_champion_to_live(champ_skill_dir: Path) -> None:
    for rp in EVOLVABLE_FILES:
        shutil.copy2(champ_skill_dir / rp, LIVE_SKILL_DIR / rp)


def should_promote_joint(cand: Dict[str, Any], champ: Dict[str, Any]) -> Tuple[bool, str]:
    ct = cand["vs_champ_tension"] or {"wins": 0, "ties": 0, "losses": 0}
    cd = cand["vs_champ_dialogue"] or {"wins": 0, "ties": 0, "losses": 0}
    net_ten = ct["wins"] - ct["losses"]
    net_dlg = cd["wins"] - cd["losses"]
    # Must improve total net pairwise wins across tension + dialogue WITHOUT collapsing either arena
    if net_ten >= -1 and net_dlg >= 0 and (net_ten + net_dlg) > 0:
        return True, f"joint pairwise gain (vs_champ ten={ct}, dlg={cd})"
    if (net_ten + net_dlg) == 0 and cand["composite_metric"] > champ["composite_metric"] + 0.8:
        return True, f"tied pairwise with higher joint composite ({cand['composite_metric']} > {champ['composite_metric']})"
    return False, f"no joint gain (ten={ct}, dlg={cd}, comp {cand['composite_metric']} vs {champ['composite_metric']})"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--dev-gate-rounds", type=int, default=1)
    ap.add_argument("--test-gate-rounds", type=int, default=2)
    ap.add_argument("--run-test", action="store_true")
    args = ap.parse_args()

    CAND_ROOT.mkdir(parents=True, exist_ok=True)
    ROUNDS_ROOT.mkdir(parents=True, exist_ok=True)
    dev8_bench = ensure_expanded_dev8_bench()

    r0_name = "v7_r0"
    r0_skill = CAND_ROOT / r0_name
    if not r0_skill.exists():
        copy_skill_snapshot(LIVE_SKILL_DIR, r0_skill)

    log(f"=== Evaluating Clean First-Principles Baseline `{r0_name}` on {len(dev8_bench)} Stratified DEV Dramas ===")
    champ_name = r0_name
    champ_skill = r0_skill
    champ_dir = ROUNDS_ROOT / r0_name
    champ_summary = evaluate_joint_candidate(
        r0_name, r0_skill, dev8_bench, champ_dir, gate_rounds=args.dev_gate_rounds
    )
    log(
        f"Baseline `{champ_name}` DEV8: ten_pass={champ_summary['tension_pass_rate']}, dlg_pass={champ_summary['dialogue_pass_rate']}, "
        f"vs_GT_ten={champ_summary['vs_real_gt_tension']}, vs_GT_dlg={champ_summary['vs_real_gt_dialogue']}, comp={champ_summary['composite_metric']}"
    )

    history = [champ_summary]

    for r in range(1, args.rounds + 1):
        cand_name = f"v7_r{r}"
        cand_skill = CAND_ROOT / cand_name
        cand_dir = ROUNDS_ROOT / cand_name

        if not (EVO_ROOT / f"mutation_{champ_name}_to_{cand_name}.json").is_file() or not cand_skill.exists():
            mres = synthesize_clean_candidate(champ_name, champ_skill, cand_name, cand_skill, champ_summary)
            if not mres["applied_files"]:
                log(f"No clean mutations passed Anti-Overfitting Prosecutor for `{cand_name}`; stopping DEV loop.")
                break

        log(f"=== Evaluating Clean Candidate `{cand_name}` on 8-Drama Stratified DEV ===")
        cand_summary = evaluate_joint_candidate(
            cand_name,
            cand_skill,
            dev8_bench,
            cand_dir,
            gate_rounds=args.dev_gate_rounds,
            champion_round_dir=champ_dir,
        )
        history.append(cand_summary)

        promote, reason = should_promote_joint(cand_summary, champ_summary)
        if promote:
            log(f"PROMOTED `{cand_name}` -> NEW CLEAN CHAMPION! ({reason})")
            champ_name = cand_name
            champ_skill = cand_skill
            champ_dir = cand_dir
            champ_summary = cand_summary
            sync_champion_to_live(champ_skill)
        else:
            log(f"REJECTED `{cand_name}` ({reason}); keeping `{champ_name}`.")

    sync_champion_to_live(champ_skill)

    test_summary = None
    if args.run_test:
        test_bench = json.loads((BENCH_DIR / "test_bench.json").read_text(encoding="utf-8"))
        log(f"=== Running LOCKED UNSEEN TEST + OOD Joint Evaluation ({len(test_bench)} cases) on `{champ_name}` ===")
        test_summary = evaluate_joint_candidate(
            f"{champ_name}_TEST",
            champ_skill,
            test_bench,
            ROUNDS_ROOT / f"{champ_name}_TEST",
            gate_rounds=args.test_gate_rounds,
        )
        log(
            f"LOCKED TEST RESULT (`{champ_name}`): ten_pass={test_summary['tension_pass_rate']}, "
            f"dlg_pass={test_summary['dialogue_pass_rate']}, vs_GT_ten={test_summary['vs_real_gt_tension']}, "
            f"vs_GT_dlg={test_summary['vs_real_gt_dialogue']}"
        )

    final_report = {
        "final_clean_champion": champ_name,
        "champion_dev8_summary": champ_summary,
        "history": history,
        "locked_test_summary": test_summary,
    }
    (EVO_ROOT / "final_v7_clean_report.json").write_text(
        json.dumps(final_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    log("Clean zero-overfitting joint tension & dialogue evolution complete!")


if __name__ == "__main__":
    main()
