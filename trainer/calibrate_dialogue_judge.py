#!/usr/bin/env python3
"""
Step 0: Calibrate `dialogue_turing_judge.py` (`judge/calibration_dialogue_v6/calibration_report.json`)
before running Stage 2.5 Pure-Dialogue Autoregressive Evolution.

Uses **Matched-Plot Pairs** across 4 genres (`urban`, `rural_era`, `ancient`, `fantasy_system`) from `train` split:
  - Positive (`REAL_HONGGUO`): Real Hongguo hit 3-ep opening dialogue
  - Negative (`AI_STIFF_TWIN`): Exact same story/characters/scenes rewritten into typical AI 15-char twin-clause
    summary/slogan dialogue (zero plot bugs, ONLY stiff AI spoken register!)

Verifies:
  1. `8/8 (100%)` Single-Script Pure-Dialogue Turing Gate accuracy
  2. `4/4 (100%)` Swap-Debiased Pairwise Pure-Dialogue accuracy (`REAL_HONGGUO` beats `AI_STIFF_TWIN` in both orders)
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

TRAIN_ROOT = Path("/home/zhongwenyu/project/ai-director-train")
SKILL_DIR = TRAIN_ROOT / ".agents" / "skills" / "hit-short-drama"
OUT_DIR = TRAIN_ROOT / "judge" / "calibration_dialogue_v6"

sys.path.insert(0, str(SKILL_DIR / "scripts"))
sys.path.insert(0, str(TRAIN_ROOT / "trainer"))

import dialogue_turing_judge as DTJ  # noqa: E402
import llm_clients as L  # noqa: E402

DEGRADE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "stiff_markdown": {
            "type": "string",
            "description": "保持原剧本分集、场次、人物与剧情信息完全不变，但将全部人物台词改写为典型的『AI工整书面双分句/总结中心思想金句/舞台口号腔』后的完整剧本Markdown",
        }
    },
    "required": ["stiff_markdown"],
    "additionalProperties": False,
}


def build_ai_stiff_twin(case_id: str, real_md: str) -> str:
    cache_p = OUT_DIR / f"{case_id}_ai_stiff_twin.md"
    if cache_p.is_file():
        return cache_p.read_text(encoding="utf-8")

    prompt = (
        "你是台词负样本合成器。请在不改变以下剧本的分集标题、场次编号、人物名字与任何剧情事件的前提下，"
        "将剧中所有角色的台词与OS改写为典型的**『AI端着说话的假台词』**：\n"
        "1. 删掉所有2～5字短促口语反应、结巴重复和语气词（啊/嘛/喏/哎）；\n"
        "2. 把每句台词都改写成14～18字、前后半句对称工整的书面双分句；\n"
        "3. 让角色频繁替作者总结人性道理、输出公众号金句（如“是你习惯了将我的付出视作理所当然的义务”）或喊打擂台口号、背行业术语。\n\n"
        "# 原剧本\n\n" + real_md
    )
    res = L.call_agy_json(prompt, DEGRADE_SCHEMA, model="gemini-4-carbon-medium", effort="medium", timeout=480)
    txt = res["stiff_markdown"].strip() + "\n"
    cache_p.write_text(txt, encoding="utf-8")
    return txt


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ex_dir = SKILL_DIR / "examples"

    raw_positives = [
        ("urban_128", "都市家庭情感", (ex_dir / "urban_hit.md").read_text(encoding="utf-8")),
        ("rural_013", "年代市井逆袭", (ex_dir / "rural_era_hit.md").read_text(encoding="utf-8")),
        ("ancient_092", "古装军营反差喜剧", (ex_dir / "ancient_hit.md").read_text(encoding="utf-8")),
        ("fantasy_037", "都市修仙双穿", (ex_dir / "fantasy_system_hit.md").read_text(encoding="utf-8")),
    ]

    print("[calib-dlg] Building 4 matched-plot AI-stiff dialogue twins via isolated agy...", flush=True)
    with cf.ThreadPoolExecutor(max_workers=4) as pool:
        stiff_twins = list(pool.map(lambda x: build_ai_stiff_twin(x[0], x[2]), raw_positives))

    cases: List[Dict[str, Any]] = []
    for (cid, genre, real_md), stiff_md in zip(raw_positives, stiff_twins):
        cases.append({"case_id": f"POS_{cid}", "genre": genre, "expected": "PASS_HUMAN_NATURAL", "script": real_md})
        cases.append({"case_id": f"NEG_stiff_{cid}", "genre": genre, "expected": "REJECT_AI_STAGEY", "script": stiff_md})

    def run_single(c: Dict[str, Any]) -> Dict[str, Any]:
        rep = DTJ.audit_dialogue_turing(c["script"], genre_hint=c["genre"])
        matched = rep["verdict"] == c["expected"]
        print(
            f"[calib-dlg-single] {c['case_id']}: expected={c['expected']} actual={rep['verdict']} "
            f"(score={rep['total_score']}, short_ratio={rep['rhythm_metrics']['short_reaction_ratio_le7']}, "
            f"twin_ratio={rep['rhythm_metrics']['twin_clause_symmetry_ratio']}, defects={len(rep['ai_voice_defects'])}) -> {'OK' if matched else 'MISMATCH'}",
            flush=True,
        )
        return {
            "case_id": c["case_id"],
            "expected": c["expected"],
            "actual": rep["verdict"],
            "matched": matched,
            "total_score": rep["total_score"],
            "rhythm_metrics": rep["rhythm_metrics"],
            "scores": rep["scores"],
            "defects_count": len(rep["ai_voice_defects"]),
            "defects": rep["ai_voice_defects"][:4],
        }

    with cf.ThreadPoolExecutor(max_workers=4) as pool:
        single_results = list(pool.map(run_single, cases))

    pk_results = []
    for (cid, genre, real_md), stiff_md in zip(raw_positives, stiff_twins):
        pk = DTJ.compare_swap_debiased_dialogue(
            "REAL_HONGGUO", real_md, "AI_STIFF_TWIN", stiff_md, genre_hint=genre, parallel_swaps=True
        )
        ok = pk["winner"] == "REAL_HONGGUO" and pk["swap_consistent"]
        print(f"[calib-dlg-pk] {cid} ({genre}): winner={pk['winner']} swap_consistent={pk['swap_consistent']} -> {'OK' if ok else 'FAIL'}", flush=True)
        pk_results.append({"pair_id": cid, "genre": genre, "ok": ok, **pk})

    s_acc = sum(1 for r in single_results if r["matched"])
    p_acc = sum(1 for r in pk_results if r["ok"])
    report = {
        "single_gate_accuracy": f"{s_acc}/{len(single_results)}",
        "pairwise_swap_accuracy": f"{p_acc}/{len(pk_results)}",
        "all_passed": (s_acc == len(single_results) and p_acc == len(pk_results)),
        "single_results": single_results,
        "pairwise_results": pk_results,
    }
    (OUT_DIR / "calibration_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"DIALOGUE JUDGE CALIBRATION: single={report['single_gate_accuracy']}, pk={report['pairwise_swap_accuracy']}, all_passed={report['all_passed']}", flush=True)


if __name__ == "__main__":
    main()
