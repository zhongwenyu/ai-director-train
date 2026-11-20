#!/usr/bin/env python3
"""Autoregressive Skill Evolution Engine for `hit-short-drama`.

Generator: agy (gemini-4-carbon-low, effort=low)
Judge & Meta-Optimizer: codex (gpt-6.1-sol, effort=medium)

Loop per round r:
  1. Snapshot current skill candidate `runs/candidates/v{r}`
  2. Run end-to-end generation (`200-500 char idea -> 40-120 ep outline -> Ep 1-5 scripts`) on DEV benchmark
  3. Score outlines & episodes via cross-family Judge (`codex gpt-6.1-sol / medium`)
  4. If r > 0, run Blind Pairwise Arena (`v{r}` vs current `champion`) on every DEV seed
  5. Promote `v{r}` to `champion` (and sync to `.agents/skills/hit-short-drama`) iff composite score & Arena win-rate improve
  6. Aggregate failure attribution (`dropoff_points`, `ai_smell_flags`, `outline_weaknesses`) and invoke
     Meta-Optimizer (`codex gpt-6.1-sol / medium`) under strict module character budgets to synthesize `v{r+1}`!
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import shutil
import statistics
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

TRAIN_ROOT = Path("/home/zhongwenyu/project/ai-director-train")
LIVE_SKILL_DIR = TRAIN_ROOT / ".agents" / "skills" / "hit-short-drama"
RUNS_DIR = TRAIN_ROOT / "runs"
CAND_DIR = RUNS_DIR / "candidates"
ROUNDS_DIR = RUNS_DIR / "rounds"
SEEDS_DIR = TRAIN_ROOT / "corpus" / "seeds"

sys.path.insert(0, str(TRAIN_ROOT / "trainer"))
sys.path.insert(0, str(TRAIN_ROOT / "judge"))
sys.path.insert(0, str(LIVE_SKILL_DIR / "scripts"))

import judge_runner as J  # noqa: E402
import llm_clients as L  # noqa: E402
import script_check as SC  # noqa: E402
import write_drama as WD  # noqa: E402

# 4 maximally diverse DEV tracks: Urban Regret, 90s Rebirth, Ancient Farming/Court, Urban Anti-Cliche Lawyer
DEFAULT_DEV_IDS = ["dev_066", "dev_097", "dev_067", "dev_098"]

EVOLVABLE_FILES = {
    "references/story-engine.md": 3800,
    "references/playbooks.md": 4200,
    "references/episode-craft.md": 4400,
    "references/anti-patterns.md": 4000,
    "prompts/stage1_outline.md": 2400,
    "prompts/stage2_episodes.md": 2400,
}

META_OPTIMIZER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "diagnosis_summary": {
            "type": "string",
            "description": "本轮生成稿的核心短板归因（观众为何划走、哪里有AI味、大纲哪里不够抓人）",
        },
        "evolution_strategy": {
            "type": "string",
            "description": "下一代Skill的进化策略（如何增强戏剧张力与活人感，同时坚决避免机械死板规则）",
        },
        "clean_examples_advice": {
            "type": "boolean",
            "description": "如果发现示范切片里残留服饰堆砌或冗余括号情绪词带偏了生成模型，设为true触发示范清洗",
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
        "diagnosis_summary",
        "evolution_strategy",
        "clean_examples_advice",
        "updated_files",
    ],
    "additionalProperties": False,
}

META_OPTIMIZER_PROMPT = """你是顶级短剧编剧教练兼 AI Skill 架构进化专家。
我们正在通过「生成（agy gemini-4-carbon-low）→ 异族总编审盲评（codex gpt-6.1-sol）→ 归因进化 Skill」的自回归闭环，训练一个能把 200-500 字简单创意变成爆款全剧大纲（40-120集）与高吸引力分集剧本（单集1-3分钟浮动）的全新 Skill：`hit-short-drama`。

### 绝对禁止的进化方向（反 Goodhart 铁律！）
1. **严禁添加机械死板的一刀切硬指标**！例如严禁规定“每集第1行必须抓手腕/推人”“连写3条△必须插台词”“每句必须小于15字”“前15秒必须同一句带死线和后果”。历史证明这类死规则只会逼模型写出荒唐的假冲突和独处自言自语！
2. **字数预算硬约束（防规则膨胀互相打架）**：你只能修改最需要进化的 2～5 个模块文件，且修改后每个文件总字符数不得超过其预算上限：
   - `references/story-engine.md` ≤ 3800 字
   - `references/playbooks.md` ≤ 4200 字
   - `references/episode-craft.md` ≤ 4400 字
   - `references/anti-patterns.md` ≤ 4000 字
   - `prompts/stage1_outline.md` ≤ 2400 字
   - `prompts/stage2_episodes.md` ≤ 2400 字
   **如果要加新法则或新的「❌ 本轮真实病灶原句 vs ✅ 高留存改写」对照，必须精简合并旧的冗余表述！**
   注意：`prompts/stage1_outline.md` 必须保留 `{{episode_plan_range}}` 占位符；`prompts/stage2_episodes.md` 必须保留 `{{batch_range}}` 占位符！

### 高效进化手段（推荐优先采用）
- **把本轮被评委抓包的真实坏句子（脱敏人名后）写进 `anti-patterns.md`**，给出极度鲜明的 `❌ 平庸/AI味写法` vs `✅ 爆款潜台词/动作反差写法`！模型看1组精准正负例胜过10条抽象说教！
- **针对得分偏低的维度（如 `cliffhanger_addiction` 钩子偏软、或 `tension_and_payoff` 中段同义反复吵架无筹码位移、或 `visual_pacing_and_craft` 服装神态词堆砌）**，在 `episode-craft.md` 和 `stage2_episodes.md` 里给出可操作的编剧动作拆解法（例如：同义羞辱不许超过一轮，第二轮必须动真格转移物件/权限；`△` 里禁止罗列衣着穿搭和连续近义冷笑形容词；集尾禁止停在“撕照片表决心”，必须停在“对手刚踏进陷阱或电话那头传来惊变”的未完成瞬间！）。
- **针对大纲评审指出的问题**（如前5集推进慢、第10-12集付费卡点不够炸、40-120集分卷换地图不够清晰），强化 `story-engine.md` 与 `stage1_outline.md`。

---
### 当前候选 Skill 版本（`{cand_name}`）本轮评测归因汇总
{attribution_report}

---
### 当前候选 Skill 各模块全文
{current_files_dump}
"""


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    with (RUNS_DIR / "evolve.log").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_seeds(seed_ids: list[str] | None = None, split: str = "dev") -> list[dict[str, Any]]:
    fname = "dev_seeds.json" if split == "dev" else "test_seeds.json"
    seeds = json.loads((SEEDS_DIR / fname).read_text(encoding="utf-8"))
    if seed_ids:
        want = set(seed_ids)
        seeds = [s for s in seeds if s["seed_id"] in want]
    return seeds


def ensure_candidate_snapshot(cand_name: str, src_dir: Path = LIVE_SKILL_DIR) -> Path:
    dst = CAND_DIR / cand_name
    if not dst.is_dir():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src_dir, dst)
    return dst


def sync_candidate_to_live(cand_dir: Path) -> None:
    if LIVE_SKILL_DIR.exists():
        shutil.rmtree(LIVE_SKILL_DIR)
    shutil.copytree(cand_dir, LIVE_SKILL_DIR)


def polish_skill_examples(skill_dir: Path) -> None:
    """Clean excessive wardrobe catalogs & repetitive stage adjectives from gold slice examples."""
    ex_dir = skill_dir / "examples"
    if not ex_dir.is_dir():
        return
    prompt_prefix = (
        "请对下面这份从视频还原的短剧参考剧本做轻量精修（保持全部人物、剧情、台词原意、场次和【本集完】100%不变）：\n"
        "1. 删掉 `△` 动作行里冗长的服装首饰穿搭罗列（如“身穿藏青色修身西装套装、白色V领衬衫，佩戴珍珠耳环...”精简为最核心的一个视觉特征或直接写动作），让动作行短促利落；\n"
        "2. 把台词括号里堆砌的多个近义情绪形容词（如“（低沉平静，毫无波澜）”精简为2-4字具体微动作或神态，甚至无需括号的可直接去掉）；\n"
        "3. 直接输出精修后的干净剧本正文，不要任何解释：\n\n"
    )
    for md_file in sorted(ex_dir.glob("*.md")):
        orig = md_file.read_text(encoding="utf-8")
        cleaned = L.call_agy(
            prompt_prefix + orig,
            timeout=360,
            validator=lambda t: "# 第 1 集" in t and "【本集完】" in t,
        )
        md_file.write_text(cleaned + "\n", encoding="utf-8")
        log(f"Polished example file {md_file.name}: {len(orig)} -> {len(cleaned)} chars")


def evaluate_one_seed(
    seed: dict[str, Any],
    cand_dir: Path,
    round_out_dir: Path,
    episodes_spec: str = "1-5",
    champion_round_dir: Path | None = None,
) -> dict[str, Any]:
    sid = seed["seed_id"]
    sdir = round_out_dir / sid
    sdir.mkdir(parents=True, exist_ok=True)

    # 1. Generate Outline + Ep 1-5 (batch_size=3 -> ep001-003 then ep004-005 with State Ledger!)
    gen_res = WD.run_pipeline(
        seed["idea"],
        sdir,
        episodes_spec=episodes_spec,
        batch_size=3,
        skill_dir=cand_dir,
        force=False,
    )
    outline_txt = Path(gen_res["outline_path"]).read_text(encoding="utf-8")
    script_txt = Path(gen_res["combined_script_path"]).read_text(encoding="utf-8")
    phys_rep = SC.analyze_script(script_txt, WD.parse_ep_range(episodes_spec))
    stats_table = SC.format_summary_table(phys_rep)

    # 2. Score Outline & Episodes with codex (gpt-6.1-sol, medium)
    out_score_p = sdir / "outline.score.json"
    if out_score_p.is_file():
        out_score = json.loads(out_score_p.read_text(encoding="utf-8"))
    else:
        out_score = J.score_outline(seed["idea"], outline_txt, out_path=out_score_p)

    ep_score_p = sdir / "episodes.score.json"
    if ep_score_p.is_file():
        ep_score = json.loads(ep_score_p.read_text(encoding="utf-8"))
    else:
        ep_score = J.score_episodes(
            script_txt,
            idea_text=seed["idea"],
            outline_excerpt=outline_txt[:5000],
            stats_summary=stats_table,
            out_path=ep_score_p,
        )

    # 3. Optional Blind Pairwise Arena vs previous Champion on exact same seed
    pk_res = None
    if champion_round_dir is not None:
        champ_script_p = (
            champion_round_dir / sid / f"combined_{episodes_spec.replace(',', '_')}.md"
        )
        pk_p = sdir / "arena_vs_champion.json"
        if pk_p.is_file():
            pk_res = json.loads(pk_p.read_text(encoding="utf-8"))
        elif champ_script_p.is_file():
            champ_txt = champ_script_p.read_text(encoding="utf-8")
            pk_res = J.pairwise_compare(
                "CANDIDATE",
                script_txt,
                "CHAMPION",
                champ_txt,
                topic_context=f"同一创意生成的第 {episodes_spec} 集剧本盲测对比（创意：{seed['idea'][:220]}…）",
                swap_debias=True,
                out_path=pk_p,
            )

    composite = round(0.25 * out_score["total_score"] + 0.75 * ep_score["total_score"], 2)
    return {
        "seed_id": sid,
        "genre": seed["genre"],
        "title_hint": seed["title_hint"],
        "outline_score": out_score["total_score"],
        "episode_score": ep_score["total_score"],
        "composite_score": composite,
        "mean_duration_sec": phys_rep["mean_est_duration_sec"],
        "dimensions": {k: v["score"] for k, v in ep_score["dimensions"].items()},
        "ai_smell_count": len(ep_score.get("ai_smell_flags", [])),
        "dropoff_count": len(ep_score.get("dropoff_points", [])),
        "pk_vs_champion": pk_res["winner_label"] if pk_res else None,
        "pk_detail": pk_res,
        "outline_eval": out_score,
        "episode_eval": ep_score,
    }


def run_round(
    round_idx: int,
    cand_name: str,
    seeds: list[dict[str, Any]],
    *,
    episodes_spec: str = "1-5",
    champion_round_dir: Path | None = None,
    workers: int = 2,
) -> tuple[Path, dict[str, Any]]:
    cand_dir = ensure_candidate_snapshot(cand_name)
    rdir = ROUNDS_DIR / f"r{round_idx:02d}_{cand_name}"
    rdir.mkdir(parents=True, exist_ok=True)
    log(f"=== Starting Round r{round_idx:02d} with candidate `{cand_name}` on {len(seeds)} seeds ===")

    rows: list[dict[str, Any]] = []
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {
            ex.submit(
                evaluate_one_seed, s, cand_dir, rdir, episodes_spec, champion_round_dir
            ): s["seed_id"]
            for s in seeds
        }
        for fut in cf.as_completed(futs):
            sid = futs[fut]
            res = fut.result()
            rows.append(res)
            log(
                f"  [{cand_name}] {sid} ({res['genre']}): Outline={res['outline_score']} | "
                f"Episodes={res['episode_score']} | Composite={res['composite_score']} | "
                f"Dur={res['mean_duration_sec']}s | Smells={res['ai_smell_count']} | "
                f"PK={res['pk_vs_champion'] or '-'}"
            )

    rows.sort(key=lambda x: x["seed_id"])
    dim_keys = list(rows[0]["dimensions"].keys())
    dim_means = {
        k: round(statistics.mean(r["dimensions"][k] for r in rows), 2) for k in dim_keys
    }
    pk_wins = sum(1 for r in rows if r["pk_vs_champion"] == "CANDIDATE")
    pk_losses = sum(1 for r in rows if r["pk_vs_champion"] == "CHAMPION")
    pk_ties = sum(1 for r in rows if r["pk_vs_champion"] == "TIE")

    summary = {
        "round": round_idx,
        "candidate": cand_name,
        "n_seeds": len(rows),
        "mean_outline_score": round(statistics.mean(r["outline_score"] for r in rows), 2),
        "mean_episode_score": round(statistics.mean(r["episode_score"] for r in rows), 2),
        "mean_composite_score": round(statistics.mean(r["composite_score"] for r in rows), 2),
        "dimension_means": dim_means,
        "total_ai_smells": sum(r["ai_smell_count"] for r in rows),
        "total_dropoffs": sum(r["dropoff_count"] for r in rows),
        "arena_vs_champion": {"wins": pk_wins, "losses": pk_losses, "ties": pk_ties},
        "seeds": rows,
    }
    (rdir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    log(
        f"=== Finished r{round_idx:02d} ({cand_name}): Composite={summary['mean_composite_score']} "
        f"(Outline={summary['mean_outline_score']}, Ep={summary['mean_episode_score']}), "
        f"Smells={summary['total_ai_smells']}, Arena W/L/T={pk_wins}/{pk_losses}/{pk_ties} ==="
    )
    return rdir, summary


def build_attribution_markdown(summary: dict[str, Any]) -> str:
    lines = [
        f"- 候选版本：`{summary['candidate']}`",
        f"- 大纲均分：{summary['mean_outline_score']} / 100",
        f"- 分集剧本均分：{summary['mean_episode_score']} / 100（综合分 {summary['mean_composite_score']}）",
        f"- 五维细分均值：{json.dumps(summary['dimension_means'], ensure_ascii=False)}",
        f"- 检出 AI 味病灶总数：{summary['total_ai_smells']} 处；观众划走风险点：{summary['total_dropoffs']} 处",
        "",
        "### 各测试剧目详细失分归因与病灶原句",
    ]
    smell_counter: Counter[str] = Counter()
    for r in summary["seeds"]:
        ep_ev = r["episode_eval"]
        out_ev = r["outline_eval"]
        lines.append(
            f"\n#### {r['seed_id']}（{r['genre']}｜大纲 {r['outline_score']} 分，剧本 {r['episode_score']} 分，均时长 {r['mean_duration_sec']}s）"
        )
        lines.append(f"- **观众第一直觉**：{ep_ev['viewer_gut_reaction']}")
        for k, v in ep_ev["dimensions"].items():
            lines.append(f"  - `{k}` ({v['score']}): {v['critique']}")
        if out_ev.get("weaknesses"):
            lines.append("- **大纲短板**：" + "；".join(out_ev["weaknesses"][:3]))
        if ep_ev.get("dropoff_points"):
            lines.append("- **观众划走点**：")
            for dp in ep_ev["dropoff_points"][:3]:
                lines.append(f"  - 第{dp['episode']}集「{dp['quote_or_moment']}」→ {dp['reason']}")
        if ep_ev.get("ai_smell_flags"):
            lines.append("- **AI 病灶抓包**：")
            for fl in ep_ev["ai_smell_flags"][:4]:
                smell_counter[fl["category"]] += 1
                lines.append(f"  - [{fl['category']}] 原句：{fl['quote']} → 改进：{fl['fix_direction']}")
        if ep_ev.get("actionable_skill_fixes"):
            lines.append("- **评委对 Skill 的通用改进建议**：" + "；".join(ep_ev["actionable_skill_fixes"][:4]))

    lines.insert(6, f"- AI 病灶分类统计：{dict(smell_counter)}")
    return "\n".join(lines)


def evolve_next_candidate(
    base_cand_name: str,
    next_cand_name: str,
    summary: dict[str, Any],
    round_dir: Path,
) -> Path:
    base_dir = CAND_DIR / base_cand_name
    next_dir = CAND_DIR / next_cand_name

    attrib_md = build_attribution_markdown(summary)
    (round_dir / "attribution.md").write_text(attrib_md + "\n", encoding="utf-8")

    file_dumps = []
    for rel_p, cap in EVOLVABLE_FILES.items():
        txt = (base_dir / rel_p).read_text(encoding="utf-8")
        file_dumps.append(
            f"### 文件：`{rel_p}`（当前 {len(txt)} 字 / 上限 {cap} 字）\n\n```markdown\n{txt}\n```"
        )

    prompt = META_OPTIMIZER_PROMPT.format(
        cand_name=base_cand_name,
        attribution_report=attrib_md,
        current_files_dump="\n\n".join(file_dumps),
    )
    log(f"Invoking Meta-Optimizer (codex gpt-6.1-sol / medium) to evolve `{base_cand_name}` -> `{next_cand_name}`...")
    plan = L.call_codex_json(
        prompt,
        META_OPTIMIZER_SCHEMA,
        timeout=900,
        out_path=round_dir / f"evolve_to_{next_cand_name}.json",
    )
    log(f"Meta-Optimizer diagnosis: {plan['diagnosis_summary']}")
    log(f"Meta-Optimizer strategy: {plan['evolution_strategy']}")

    if next_dir.exists():
        shutil.rmtree(next_dir)
    shutil.copytree(base_dir, next_dir)

    applied = 0
    for item in plan["updated_files"]:
        rel_p = item["rel_path"]
        if rel_p not in EVOLVABLE_FILES:
            continue
        new_txt = L.strip_markdown_fence(item["new_content"]).strip()
        if not new_txt:
            continue
        # Verify required placeholders in prompt templates
        if rel_p == "prompts/stage1_outline.md" and "{episode_plan_range}" not in new_txt:
            log(f"  [skip] {rel_p} missing {{episode_plan_range}} placeholder")
            continue
        if rel_p == "prompts/stage2_episodes.md" and "{batch_range}" not in new_txt:
            log(f"  [skip] {rel_p} missing {{batch_range}} placeholder")
            continue
        cap = EVOLVABLE_FILES[rel_p]
        if len(new_txt) > int(cap * 1.18):
            log(f"  [warn] {rel_p} slightly over cap ({len(new_txt)} vs {cap}), still applying if reasonable")
        target_p = next_dir / rel_p
        target_p.write_text(new_txt + "\n", encoding="utf-8")
        applied += 1
        log(f"  [updated] {rel_p} ({len(new_txt)} chars): {item['reason']}")

    if applied == 0:
        raise RuntimeError("Meta-Optimizer produced 0 valid file updates!")
    return next_dir


def should_promote(cand_summary: dict[str, Any], champ_summary: dict[str, Any]) -> bool:
    c_comp = cand_summary["mean_composite_score"]
    b_comp = champ_summary["mean_composite_score"]
    arena = cand_summary["arena_vs_champion"]
    # Promote if composite score improves AND candidate does not lose head-to-head Arena (wins >= losses)
    if c_comp > b_comp and arena["wins"] >= arena["losses"]:
        return True
    # Also promote if Arena decisively wins (wins > losses + 1) and score is within noise margin (-0.8)
    if arena["wins"] >= arena["losses"] + 2 and c_comp >= b_comp - 0.8:
        return True
    return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=3, help="Number of evolution rounds after v0 baseline")
    ap.add_argument("--seeds", default=",".join(DEFAULT_DEV_IDS), help="Comma-separated dev seed IDs")
    ap.add_argument("--episodes", default="1-5", help="Episode range per drama")
    ap.add_argument("--workers", type=int, default=2, help="Parallel drama workers")
    args = ap.parse_args()

    seed_ids = [x.strip() for x in args.seeds.split(",") if x.strip()]
    seeds = load_seeds(seed_ids, split="dev")

    history_path = RUNS_DIR / "evolution_history.json"
    history: list[dict[str, Any]] = []

    # Round 0: Baseline v0
    champ_name = "v0"
    champ_rdir, champ_sum = run_round(
        0, champ_name, seeds, episodes_spec=args.episodes, champion_round_dir=None, workers=args.workers
    )
    history.append({"round": 0, "candidate": "v0", "promoted": True, "summary": champ_sum})
    history_path.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for r in range(1, args.rounds + 1):
        cand_name = f"v{r}"
        cand_path = CAND_DIR / cand_name
        if not cand_path.is_dir():
            evolve_next_candidate(champ_name, cand_name, champ_sum, champ_rdir)

        rdir, cand_sum = run_round(
            r,
            cand_name,
            seeds,
            episodes_spec=args.episodes,
            champion_round_dir=champ_rdir,
            workers=args.workers,
        )
        promoted = should_promote(cand_sum, champ_sum)
        log(
            f"Promotion check for `{cand_name}` vs `{champ_name}`: "
            f"Composite {cand_sum['mean_composite_score']} vs {champ_sum['mean_composite_score']}, "
            f"Arena {cand_sum['arena_vs_champion']} -> PROMOTED={promoted}"
        )
        if promoted:
            champ_name = cand_name
            champ_rdir = rdir
            champ_sum = cand_sum
            sync_candidate_to_live(CAND_DIR / champ_name)
            log(f"Synced new champion `{champ_name}` to live skill {LIVE_SKILL_DIR}!")

        history.append(
            {
                "round": r,
                "candidate": cand_name,
                "compared_against": history[-1]["candidate"] if not promoted else None,
                "promoted": promoted,
                "champion_after_round": champ_name,
                "summary": cand_sum,
            }
        )
        history_path.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    log(f"Evolution complete! Final Champion: `{champ_name}` (Composite={champ_sum['mean_composite_score']})")


if __name__ == "__main__":
    main()
