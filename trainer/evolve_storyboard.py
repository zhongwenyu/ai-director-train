#!/usr/bin/env python3
"""Multi-Round Autoregressive Evolution for `hit-storyboard` Skill.

- Generator: agy (gemini-4-carbon-low, effort=low)
- Judge / Swapped Double-Blind Arena / Meta-Optimizer: codex (gpt-6.1-sol, effort=medium)
- Anti-Goodhart Gate: Promotes candidate ONLY if it wins Swapped Pairwise Arena against current Champion.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any

TRAIN_ROOT = Path("/home/zhongwenyu/project/ai-director-train")
LIVE_SKILL_DIR = TRAIN_ROOT / ".agents" / "skills" / "hit-storyboard"
SB_RUNS_DIR = TRAIN_ROOT / "runs" / "storyboard_train"
CAND_DIR = SB_RUNS_DIR / "candidates"
ROUNDS_DIR = SB_RUNS_DIR / "rounds"
EVAL_SET_PATH = TRAIN_ROOT / "corpus" / "storyboard_eval_sets" / "dev_episodes.json"

sys.path.insert(0, str(TRAIN_ROOT / "trainer"))
sys.path.insert(0, str(TRAIN_ROOT / "judge"))
sys.path.insert(0, str(LIVE_SKILL_DIR / "scripts"))

import llm_clients as L  # noqa: E402
import storyboard_check as SBC  # noqa: E402
import storyboard_judge as SBJ  # noqa: E402
import write_storyboard as WSB  # noqa: E402

EDITABLE_MODULES = [
    "references/camera-choreography.md",
    "references/grouping-and-continuity.md",
    "references/storyboard-anti-patterns.md",
    "prompts/generate_storyboard.md",
]

MODULE_CHAR_BUDGETS = {
    "references/camera-choreography.md": 3600,
    "references/grouping-and-continuity.md": 3600,
    "references/storyboard-anti-patterns.md": 3400,
    "prompts/generate_storyboard.md": 2400,
}

META_SB_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "root_cause_diagnosis": {"type": "string"},
        "evolution_strategy": {"type": "string"},
        "updated_files": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "rel_path": {"type": "string", "enum": EDITABLE_MODULES},
                    "reason": {"type": "string"},
                    "full_markdown_content": {"type": "string"},
                },
                "required": ["rel_path", "reason", "full_markdown_content"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["root_cause_diagnosis", "evolution_strategy", "updated_files"],
    "additionalProperties": False,
}

META_SB_PROMPT = """你是 AI 短剧视听分镜与摄影机运镜 Skill 的元优化架构师（Meta-Optimizer）。
生成端是轻量高并发模型 `agy (gemini-4-carbon-low, effort=low)`，它在加载当前冠军 Skill `{champ_name}` 后，在 4 个跨赛道剧本上生成的分镜表刚刚接受了严苛盲审。

### 本轮评测暴露出的共性失分与病灶归因
{attribution_report}

### 当前冠军 Skill (`{champ_name}`) 可编辑模块全文
{current_modules_dump}

---
### 你的进化重写任务（产出下一代 `{next_name}`）
1. **直击真病根，拒绝机械配额（Anti-Goodhart）**：
   - 仔细阅读上方评委指出的运镜缺陷、空间轴线漏洞、段缝跳切、台词塞字超载或画面抽象套话，用本轮抓包到的真实反例（脱敏人名）更新 `storyboard-anti-patterns.md` 并优化 `camera-choreography.md`、`grouping-and-continuity.md`、`prompts/generate_storyboard.md`。
   - **严禁发明死板机械配额**（如禁止规定“每集必须固定28镜”“每场第2镜必须缓推”），而是给模型清晰可判定的**导演决策准则**（何时固定留白、何时用触发+路径+速度+落点推进、如何拆解爽点四拍、如何写实组末静态画面锚点）。
2. **必须保留的硬契约与占位符**：
   - `prompts/generate_storyboard.md` 中**必须原样保留** `{{episode_range}}` 与 `{{aspect_ratio}}` 两个格式化占位符（单花括号形式：即文本内包含 `{episode_range}` 和 `{aspect_ratio}`），且保持 14 列表头与 `# 第 N 集`、`## N-M`、`> 【组 X-X-XX 末态与接缝】` 输出契约不变，以便确定性体检脚本 `storyboard_check.py` 解析！
3. **字符预算控制（防上下文稀释）**：
   - `references/camera-choreography.md` ≤ 3600 字符
   - `references/grouping-and-continuity.md` ≤ 3600 字符
   - `references/storyboard-anti-patterns.md` ≤ 3400 字符
   - `prompts/generate_storyboard.md` ≤ 2400 字符
   只输出修改后需要替换的模块完整全文。
"""


def log(msg: str) -> None:
    SB_RUNS_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with (SB_RUNS_DIR / "evolve_storyboard.log").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def sync_skill_dir(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def evaluate_one_item(
    item: dict[str, Any],
    cand_dir: Path,
    round_dir: Path,
    champ_round_dir: Path | None = None,
) -> dict[str, Any]:
    eid = item["eval_id"]
    idir = round_dir / eid
    idir.mkdir(parents=True, exist_ok=True)

    sp_md = item["screenplay"]
    sb_path, phys_rep = WSB.generate_one_episode_storyboard(
        1,
        sp_md,
        idir,
        skill_dir=cand_dir,
        aspect_ratio=item["aspect_ratio"],
        force=False,
    )
    sb_txt = sb_path.read_text(encoding="utf-8")
    stats_tbl = SBC.format_summary_table(phys_rep)

    sc_p = idir / "score.json"
    pk_p = idir / "arena_vs_champion.json"

    def _get_score() -> dict[str, Any]:
        if sc_p.is_file():
            return json.loads(sc_p.read_text(encoding="utf-8"))
        return SBJ.score_storyboard(sb_txt, sp_md, stats_summary=stats_tbl, out_path=sc_p)

    def _get_pk() -> dict[str, Any] | None:
        if champ_round_dir is None:
            return None
        if pk_p.is_file():
            return json.loads(pk_p.read_text(encoding="utf-8"))
        champ_sb_p = champ_round_dir / eid / "ep001_storyboard.md"
        if champ_sb_p.is_file():
            champ_txt = champ_sb_p.read_text(encoding="utf-8")
            return SBJ.pairwise_compare_storyboards(
                "CANDIDATE",
                sb_txt,
                "CHAMPION",
                champ_txt,
                sp_md,
                swap_debias=True,
                out_path=pk_p,
            )
        return None

    with cf.ThreadPoolExecutor(max_workers=2) as pool:
        f_sc = pool.submit(_get_score)
        f_pk = pool.submit(_get_pk)
        sc = f_sc.result()
        pk = f_pk.result()

    ep_stat = phys_rep["episodes"][0] if phys_rep["episodes"] else {}
    return {
        "eval_id": eid,
        "genre": item["genre"],
        "total_score": sc["total_score"],
        "dimensions": {k: v["score"] for k, v in sc["dimensions"].items()},
        "flaw_count": len(sc.get("camera_and_staging_flaws", [])),
        "shots": ep_stat.get("shots", 0),
        "groups": ep_stat.get("groups", 0),
        "active_cam_pct": ep_stat.get("active_cam_pct", 0.0),
        "asl_sec": ep_stat.get("asl_sec", 0.0),
        "pk_vs_champion": pk["winner_label"] if pk else None,
        "pk_detail": pk,
        "score_detail": sc,
        "phys_warnings": phys_rep.get("warnings", []),
    }


def build_attribution(summary: dict[str, Any]) -> str:
    lines = [
        f"候选版本 `{summary['candidate']}` 四赛道均分：{summary['mean_score']}（运镜均分 {summary['dimension_means']['camera_movement_choreography']}/25，AI可拍与接缝 {summary['dimension_means']['ai_video_executability_and_seam_lock']}/20）",
        "",
    ]
    for it in summary["items"]:
        sc = it["score_detail"]
        lines.append(
            f"### {it['eval_id']} ({it['genre']}) — 总分 {it['total_score']} | 主动运镜率 {it['active_cam_pct']}% | PK={it['pk_vs_champion']}"
        )
        lines.append(f"- 导演直觉：{sc['director_gut_verdict']}")
        if it["phys_warnings"]:
            lines.append(f"- 物理告警：{'；'.join(it['phys_warnings'][:4])}")
        for fl in sc.get("camera_and_staging_flaws", [])[:5]:
            lines.append(f"- 病灶 [{fl['category']}] `{fl['shot_id_or_quote'][:60]}` → {fl['fix_direction']}")
        for fx in sc.get("actionable_skill_fixes", [])[:4]:
            lines.append(f"- 方法论建议：{fx}")
        if it["pk_detail"] and it["pk_vs_champion"] != "CANDIDATE":
            lines.append(f"- 双盲未胜原因：{it['pk_detail']['why_loser_loses'][:220]}")
        lines.append("")
    return "\n".join(lines)


def run_round(
    round_idx: int,
    cand_name: str,
    dev_items: list[dict[str, Any]],
    champ_round_dir: Path | None,
    workers: int = 4,
) -> tuple[Path, dict[str, Any]]:
    rdir = ROUNDS_DIR / f"r{round_idx:02d}_{cand_name}"
    rdir.mkdir(parents=True, exist_ok=True)
    sum_p = rdir / "summary.json"

    log(f"=== Starting Storyboard Round r{round_idx:02d} ({cand_name}) on {len(dev_items)} tracks ===")
    cand_dir = CAND_DIR / cand_name

    results = []
    with cf.ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futs = {
            pool.submit(evaluate_one_item, it, cand_dir, rdir, champ_round_dir): it["eval_id"]
            for it in dev_items
        }
        for f in cf.as_completed(futs):
            r = f.result()
            results.append(r)
            log(
                f"  [{cand_name}] {r['eval_id']} ({r['genre']}): Score={r['total_score']} | "
                f"Cam={r['dimensions']['camera_movement_choreography']}/25 | "
                f"ActiveCam={r['active_cam_pct']}% | Shots={r['shots']} | PK={r['pk_vs_champion'] or '-'}"
            )

    results.sort(key=lambda x: x["eval_id"])
    n = len(results)
    dim_keys = list(results[0]["dimensions"].keys())
    dim_means = {k: round(sum(r["dimensions"][k] for r in results) / n, 2) for k in dim_keys}
    wins = sum(1 for r in results if r["pk_vs_champion"] == "CANDIDATE")
    losses = sum(1 for r in results if r["pk_vs_champion"] == "CHAMPION")
    ties = sum(1 for r in results if r["pk_vs_champion"] == "TIE")

    summary = {
        "round": round_idx,
        "candidate": cand_name,
        "mean_score": round(sum(r["total_score"] for r in results) / n, 2),
        "dimension_means": dim_means,
        "total_flaws": sum(r["flaw_count"] for r in results),
        "arena_vs_champion": {"wins": wins, "losses": losses, "ties": ties},
        "items": results,
    }
    sum_p.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (rdir / "attribution.md").write_text(build_attribution(summary) + "\n", encoding="utf-8")
    log(
        f"=== Finished r{round_idx:02d} ({cand_name}): Mean={summary['mean_score']} "
        f"(Cam={dim_means['camera_movement_choreography']}/25), Flaws={summary['total_flaws']}, "
        f"Arena W/L/T={wins}/{losses}/{ties} ==="
    )
    return rdir, summary


def evolve_candidate(
    champ_name: str,
    next_name: str,
    champ_sum: dict[str, Any],
    champ_rdir: Path,
) -> Path:
    plan_p = champ_rdir / f"evolve_to_{next_name}.json"
    base_dir = CAND_DIR / champ_name
    next_dir = CAND_DIR / next_name

    if plan_p.is_file():
        plan = json.loads(plan_p.read_text(encoding="utf-8"))
    else:
        log(f"Invoking Meta-Optimizer (codex gpt-6.1-sol / medium) to evolve `{champ_name}` -> `{next_name}`...")
        mods_dump = []
        for rel in EDITABLE_MODULES:
            txt = (base_dir / rel).read_text(encoding="utf-8")
            mods_dump.append(f"#### FILE: `{rel}` ({len(txt)} chars)\n```markdown\n{txt}\n```")
        prompt = META_SB_PROMPT.format(
            champ_name=champ_name,
            next_name=next_name,
            attribution_report=build_attribution(champ_sum),
            current_modules_dump="\n\n".join(mods_dump),
            episode_range="{episode_range}",
            aspect_ratio="{aspect_ratio}",
        )
        plan = L.call_codex_json(prompt, META_SB_SCHEMA, timeout=900)
        plan_p.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    sync_skill_dir(base_dir, next_dir)
    log(f"Meta-Optimizer diagnosis: {plan['root_cause_diagnosis'][:220]}")
    for uf in plan.get("updated_files", []):
        rel = uf["rel_path"]
        content = uf["full_markdown_content"].strip()
        if rel == "prompts/generate_storyboard.md":
            if "{episode_range}" not in content or "{aspect_ratio}" not in content:
                log(f"  [skip] {rel} missing required placeholders, keeping base")
                continue
        limit = MODULE_CHAR_BUDGETS.get(rel, 4000)
        if len(content) > limit * 1.35:
            log(f"  [warn] {rel} slightly over budget ({len(content)} chars), writing anyway")
        (next_dir / rel).write_text(content + "\n", encoding="utf-8")
        log(f"  [updated] {rel} ({len(content)} chars): {uf['reason']}")
    return next_dir


def should_promote(cand_sum: dict[str, Any], champ_sum: dict[str, Any]) -> bool:
    ar = cand_sum["arena_vs_champion"]
    if ar["wins"] > ar["losses"]:
        return True
    if ar["wins"] == ar["losses"] and cand_sum["mean_score"] >= champ_sum["mean_score"] + 1.0:
        return True
    return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    CAND_DIR.mkdir(parents=True, exist_ok=True)
    ROUNDS_DIR.mkdir(parents=True, exist_ok=True)
    dev_items = json.loads(EVAL_SET_PATH.read_text(encoding="utf-8"))

    v0_dir = CAND_DIR / "v0"
    if not v0_dir.is_dir():
        sync_skill_dir(LIVE_SKILL_DIR, v0_dir)

    champ_name = "v0"
    champ_rdir, champ_sum = run_round(0, "v0", dev_items, champ_round_dir=None, workers=args.workers)
    history = [{"round": 0, "candidate": "v0", "promoted": True, "summary": champ_sum}]

    for r in range(1, args.rounds + 1):
        cand_name = f"v{r}"
        if not (CAND_DIR / cand_name).is_dir():
            evolve_candidate(champ_name, cand_name, champ_sum, champ_rdir)
        rdir, cand_sum = run_round(r, cand_name, dev_items, champ_round_dir=champ_rdir, workers=args.workers)
        promoted = should_promote(cand_sum, champ_sum)
        log(
            f"Promotion check `{cand_name}` vs `{champ_name}`: Mean {cand_sum['mean_score']} vs {champ_sum['mean_score']}, "
            f"Arena {cand_sum['arena_vs_champion']} -> PROMOTED={promoted}"
        )
        if promoted:
            champ_name = cand_name
            champ_rdir = rdir
            champ_sum = cand_sum
            sync_skill_dir(CAND_DIR / champ_name, LIVE_SKILL_DIR)
            log(f"Synced new Storyboard Champion `{champ_name}` to {LIVE_SKILL_DIR}!")
        history.append({"round": r, "candidate": cand_name, "promoted": promoted, "summary": cand_sum})
        (SB_RUNS_DIR / "evolution_history.json").write_text(
            json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    log(f"Storyboard Evolution Complete! Final Champion: `{champ_name}` (Mean={champ_sum['mean_score']})")


if __name__ == "__main__":
    main()
