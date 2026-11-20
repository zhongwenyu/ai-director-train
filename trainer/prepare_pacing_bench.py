#!/usr/bin/env python3
"""
Prepare strictly IP-isolated 3-episode continuous opening benchmark (`ep001-003`)
for `DEV` (used in `evolve_pacing.py`) and `TEST` (locked unseen final evaluation).

Uses ONLY isolated `agy` (`gemini-4-carbon-medium`) sub-agents.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

TRAIN_ROOT = Path("/home/zhongwenyu/project/ai-director-train")
sys.path.insert(0, str(TRAIN_ROOT / "trainer"))
import llm_clients as L  # noqa: E402
import prepare_assets as PA  # noqa: E402

BENCH_DIR = TRAIN_ROOT / "corpus" / "pacing_bench"

ONE_SENTENCE_SEED_PROMPT = """你是一位短剧策划总监。请根据下面某部爆款短剧的前3集原片内容，提炼出一句**极简的一句话核心创意种子（45～80字）**，用于下游编剧系统测试。

要求：
1. 只用 **1～2 句话（45～80个汉字）** 概括主角身份处境、核心冲突与反击爽点方向（例如：“隐瞒集团掌舵人身份的女婿过年扶持岳家，丈母娘发红包却唯独当众漏掉他女儿还骂赔钱货，女婿寒心收回三十六万养老金掀桌清算。”）。
2. **严禁出现具体人名**（方便盲测对比），严禁写“第一集、第二集”分集剧透。
3. 直接输出这一句话正文，不要引号或任何解释。

原片前3集参考：
{script_3ep}
"""


def convert_3ep_for_drama(drama: Dict[str, Any], out_file: Path) -> str:
    if out_file.is_file() and out_file.stat().st_size > 1500:
        return out_file.read_text(encoding="utf-8")

    ndir = Path(drama["novel_dir"])
    dur = int(round(drama.get("median_duration_sec") or 120))
    ep_texts: List[str] = []

    def conv_ep(ep_no: int) -> str:
        ch_path = ndir / f"第{ep_no:03d}章.md"
        if not ch_path.is_file():
            cands = sorted(ndir.glob(f"*{ep_no:03d}*.md"))
            if not cands:
                raise FileNotFoundError(f"Missing ep {ep_no} in {ndir}")
            ch_path = cands[0]
        raw_md = ch_path.read_text(encoding="utf-8")
        prompt = PA.TRANSCRIPT_TO_SCRIPT_PROMPT.format(
            ep_num=ep_no,
            dur_sec=dur,
            title=drama["title"],
            genre=drama["genre"],
            raw_md=raw_md[:18000],
        )
        return L.call_agy(
            prompt,
            model="gemini-4-carbon-medium",
            effort="medium",
            timeout=360,
            validator=lambda t: ("【本集完】" in t and len(t) > 250),
        )

    with cf.ThreadPoolExecutor(max_workers=3) as pool:
        ep_texts = list(pool.map(conv_ep, [1, 2, 3]))

    combined = "\n\n---\n\n".join(t.strip() for t in ep_texts) + "\n"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(combined, encoding="utf-8")
    return combined


def distill_short_seed(script_3ep: str, seed_file: Path) -> str:
    if seed_file.is_file() and seed_file.stat().st_size > 30:
        return seed_file.read_text(encoding="utf-8").strip()
    s = L.call_agy(
        ONE_SENTENCE_SEED_PROMPT.format(script_3ep=script_3ep[:9000]),
        model="gemini-4-carbon-medium",
        effort="medium",
        timeout=240,
        validator=lambda t: 25 <= len(t.strip()) <= 160,
    ).strip()
    seed_file.parent.mkdir(parents=True, exist_ok=True)
    seed_file.write_text(s + "\n", encoding="utf-8")
    return s


def main() -> None:
    manifest = json.loads((TRAIN_ROOT / "corpus" / "manifest.json").read_text(encoding="utf-8"))["dramas"]
    by_id = {v["id"]: v for v in manifest.values()}

    BENCH_DIR.mkdir(parents=True, exist_ok=True)

    # 1. DEV 4-drama continuous 3-ep benchmark
    dev_specs = [
        {
            "bench_id": "dev_049",
            "id": "049",
            "existing_gt": TRAIN_ROOT / "judge/calibration_v2/benchmark/P06_049_house_occupy/real_equal_ep001-003.md",
            "seed": "隐退女董事长把亡母留下的学区房借给小姑子一家白住三年救急，期满收房时小姑子私自换锁毁坏遗物，偏心丈夫还偷撕协议逼她把房过户给外甥，女主彻底寒心强势收房清算。",
        },
        {
            "bench_id": "dev_066",
            "id": "066",
            "existing_gt": None,
            "seed": None,
        },
        {
            "bench_id": "dev_133",
            "id": "133",
            "existing_gt": None,
            "seed": None,
        },
    ]

    # 2. TEST 3-drama locked unseen benchmark
    test_specs = [
        {
            "bench_id": "test_085",
            "id": "085",
            "existing_gt": TRAIN_ROOT / "judge/calibration_v2/benchmark/P08_085_hotpot_10m/real_equal_ep001-003.md",
            "seed": "豪门阔少以为温顺女友爱惨了自己而纵容绿茶女大当众羞辱她，殊不知女友六年深情全是演戏，正默默变卖他闲置奢侈品凑够一千万远走高飞自由吃火锅。",
        },
        {
            "bench_id": "test_048",
            "id": "048",
            "existing_gt": None,
            "seed": None,
        },
        {
            "bench_id": "test_075",
            "id": "075",
            "existing_gt": None,
            "seed": None,
        },
    ]

    def build_group(specs: List[Dict[str, Any]], split_name: str) -> List[Dict[str, Any]]:
        out_items: List[Dict[str, Any]] = []
        for sp in specs:
            bid = sp["bench_id"]
            d = by_id[sp["id"]]
            assert d["split"] == split_name, f"Split mismatch for {bid}: {d['split']} != {split_name}"
            gt_path = BENCH_DIR / split_name / f"{bid}_gt_ep001-003.md"
            seed_path = BENCH_DIR / split_name / f"{bid}_seed.txt"
            if sp["existing_gt"] and Path(sp["existing_gt"]).is_file():
                gt_path.parent.mkdir(parents=True, exist_ok=True)
                gt_txt = Path(sp["existing_gt"]).read_text(encoding="utf-8")
                gt_path.write_text(gt_txt, encoding="utf-8")
            else:
                gt_txt = convert_3ep_for_drama(d, gt_path)

            if sp["seed"]:
                seed_path.write_text(sp["seed"] + "\n", encoding="utf-8")
                seed_txt = sp["seed"]
            else:
                seed_txt = distill_short_seed(gt_txt, seed_path)

            out_items.append({
                "bench_id": bid,
                "drama_id": sp["id"],
                "split": split_name,
                "genre": d["genre"],
                "seed": seed_txt,
                "gt_path": str(gt_path),
            })
            print(f"[{split_name}] Prepared {bid} (genre={d['genre']}, gt_bytes={len(gt_txt.encode('utf-8'))})", flush=True)
        return out_items

    dev_items = build_group(dev_specs, "dev")
    test_items = build_group(test_specs, "test")

    (BENCH_DIR / "dev_bench.json").write_text(json.dumps(dev_items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (BENCH_DIR / "test_bench.json").write_text(json.dumps(test_items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved dev_bench ({len(dev_items)}) and test_bench ({len(test_items)})!", flush=True)


if __name__ == "__main__":
    main()
