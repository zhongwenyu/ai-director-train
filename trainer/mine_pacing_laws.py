#!/usr/bin/env python3
"""
Empirical Multi-Episode Pacing & Event-Span Miner (`trainer/mine_pacing_laws.py`).

Strictly reads ONLY `split == "train"` dramas (105 dramas, ~5,100 episodes) from:
  - `/home/zhongwenyu/project/ai-director-train/corpus/manifest.json`
  - `/home/zhongwenyu/project/ai-director-workstation/videos/红果AI短剧_800部_前50集/小说/<drama>/summary.md`
  - `/home/zhongwenyu/project/ai-director-workstation/videos/红果AI短剧_800部_前50集/分析/episodes-repaired/<drama>/ep*.json`
  - `/home/zhongwenyu/project/ai-director-workstation/videos/红果AI短剧_800部_前50集/小说/<drama>/第001..005章*.md`

NEVER touches `dev` or `test` splits!
Quantifies:
  1. Episodes per Complete Dramatic Event (`chapter_count / num_stages` from `summary.md`).
  2. Foreshadowing Plant-to-Payoff Episode Span (`ep_resolved - ep_planted` from `episodes-repaired`).
  3. Episode 1..5 `episodeFunction`, `endingHook.type`, beat count, character count, and payoff types.
  4. Cross-episode same-event / cliffhanger continuation rate (`Ep 1 -> Ep 2`, `Ep 2 -> Ep 3`, `Ep 3 -> Ep 4`).
  5. Opening exposition patterns (flash-forward / flashback cold-open rate, screen lower-third identity tags).
"""
from __future__ import annotations

import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set

TRAIN_ROOT = Path("/home/zhongwenyu/project/ai-director-train")
MANIFEST_PATH = TRAIN_ROOT / "corpus" / "manifest.json"
CORPUS_ROOT = Path("/home/zhongwenyu/project/ai-director-workstation/videos/红果AI短剧_800部_前50集")
REPAIRED_ROOT = CORPUS_ROOT / "分析" / "episodes-repaired"

RE_STAGE_LINE = re.compile(r"^\s*-\s*阶段\s*\d+\s*[｜|]", re.M)
RE_PLANT_EP = re.compile(r"ep0*(\d+)-")


def pct(vals: List[float], q: float) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    idx = min(len(s) - 1, max(0, int(round((len(s) - 1) * q))))
    return round(float(s[idx]), 2)


def token_overlap(a: str, b: str) -> float:
    sa = set(re.findall(r"[\u4e00-\u9fff]{2}", a))
    sb = set(re.findall(r"[\u4e00-\u9fff]{2}", b))
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / float(min(len(sa), len(sb)))


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    train_dramas = [
        d for d in manifest["dramas"].values()
        if d.get("split") == "train"
    ]

    eps_per_stage_list: List[float] = []
    stage_counts_list: List[int] = []
    stage_examples: List[Dict[str, Any]] = []

    plant_to_resolve_spans: List[int] = []
    ep1_plant_resolve_eps: List[int] = []

    ep_func_by_num: Dict[int, Counter] = defaultdict(Counter)
    end_hook_by_num: Dict[int, Counter] = defaultdict(Counter)
    char_count_by_num: Dict[int, List[int]] = defaultdict(list)
    beat_count_by_num: Dict[int, List[int]] = defaultdict(list)
    payoff_count_by_num: Dict[int, List[int]] = defaultdict(list)

    # Cross-episode continuity (same cast & unresolved cliffhanger continuation)
    same_cast_cont_by_pair: Dict[str, List[int]] = defaultdict(list)
    unresolved_hook_cont_by_pair: Dict[str, List[int]] = defaultdict(list)
    cold_open_flash_count = 0
    ep1_total_annotated = 0
    screen_id_tag_dramas = 0
    novel_checked_dramas = 0

    for d in sorted(train_dramas, key=lambda x: x["key"]):
        key = d["key"]
        chap_cnt = int(d.get("chapter_count") or 50)

        # 1. Stage count from summary.md
        if d.get("has_summary_md") and d.get("summary_path"):
            sp = Path(d["summary_path"])
            if sp.is_file():
                stxt = sp.read_text(encoding="utf-8")
                stages = RE_STAGE_LINE.findall(stxt)
                if len(stages) >= 3:
                    eps_per_stage = round(chap_cnt / float(len(stages)), 2)
                    eps_per_stage_list.append(eps_per_stage)
                    stage_counts_list.append(len(stages))
                    if len(stage_examples) < 12:
                        stage_lines = [
                            ln.strip() for ln in stxt.splitlines()
                            if RE_STAGE_LINE.match(ln)
                        ]
                        stage_examples.append({
                            "drama": key,
                            "genre": d.get("genre"),
                            "chapters": chap_cnt,
                            "num_stages": len(stages),
                            "episodes_per_stage": eps_per_stage,
                            "first_2_stages": stage_lines[:2],
                        })

        # 2. Check raw chapter 1 for screen identity tags / flashback-flashforward markers
        ndir = Path(d.get("novel_dir", ""))
        if ndir.is_dir():
            ch1s = sorted(ndir.glob("*001*.md")) + sorted(ndir.glob("*第1章*.md")) + sorted(ndir.glob("*第01章*.md"))
            if not ch1s:
                ch1s = sorted(p for p in ndir.glob("*.md") if p.name != "summary.md")[:1]
            if ch1s:
                novel_checked_dramas += 1
                c1_txt = ch1s[0].read_text(encoding="utf-8", errors="ignore")
                if any(k in c1_txt for k in ("字幕", "花字", "屏幕显示", "名牌", "身份标", "分钟前", "年前", "前世", "重生")):
                    screen_id_tag_dramas += 1

        # 3. Analyze episodes-repaired annotations
        rdir = REPAIRED_ROOT / key
        if not rdir.is_dir():
            continue
        all_eps: Dict[int, Dict[str, Any]] = {}
        for jf in sorted(rdir.glob("ep*.json")):
            try:
                jdata = json.loads(jf.read_text(encoding="utf-8"))
            except Exception:
                continue
            for ep_obj in jdata.get("episodes", []):
                eno = int(ep_obj.get("episode", 0))
                if eno > 0:
                    all_eps[eno] = ep_obj

        if not all_eps:
            continue

        # Track foreshadowing spans across episodes 1..50
        planted_at: Dict[str, int] = {}
        for eno in sorted(all_eps.keys()):
            ep_obj = all_eps[eno]
            fsh = ep_obj.get("foreshadow") or {}
            for p_item in (fsh.get("planted") or []):
                pid = str(p_item.get("id") or "")
                if pid:
                    planted_at[pid] = eno
            for r_item in (fsh.get("resolved") or []):
                rid = str(r_item.get("id") or r_item if isinstance(r_item, str) else "")
                src_ep = planted_at.get(rid)
                if src_ep is None:
                    m = RE_PLANT_EP.search(rid)
                    if m:
                        src_ep = int(m.group(1))
                if src_ep is not None and eno >= src_ep:
                    span = eno - src_ep + 1
                    plant_to_resolve_spans.append(span)
                    if src_ep == 1:
                        ep1_plant_resolve_eps.append(eno)

        # Episode 1..5 structure
        if 1 in all_eps:
            ep1_total_annotated += 1
            s1 = json.dumps(all_eps[1], ensure_ascii=False)
            if any(k in s1 for k in ("分钟前", "小时前", "前世", "预告", "倒叙", "闪回", "重生")):
                cold_open_flash_count += 1

        for eno in range(1, 6):
            if eno not in all_eps:
                continue
            eo = all_eps[eno]
            ep_func_by_num[eno][str(eo.get("episodeFunction") or "unknown")] += 1
            eh = eo.get("endingHook") or {}
            end_hook_by_num[eno][str(eh.get("type") or "unknown")] += 1
            chars = eo.get("characters") or []
            beats = eo.get("beats") or []
            payoffs = eo.get("payoffs") or []
            char_count_by_num[eno].append(len(chars))
            beat_count_by_num[eno].append(len(beats))
            payoff_count_by_num[eno].append(len(payoffs))

        # Continuity across Ep k -> Ep k+1 (k=1,2,3,4)
        for k in (1, 2, 3, 4):
            if k in all_eps and (k + 1) in all_eps:
                e_cur = all_eps[k]
                e_nxt = all_eps[k + 1]
                c_cur: Set[str] = {str(c.get("name", "")) for c in (e_cur.get("characters") or []) if c.get("name")}
                c_nxt: Set[str] = {str(c.get("name", "")) for c in (e_nxt.get("characters") or []) if c.get("name")}
                shared_ratio = (len(c_cur & c_nxt) / float(max(1, min(len(c_cur), len(c_nxt))))) if (c_cur and c_nxt) else 0.0
                same_cast_cont_by_pair[f"ep{k}->ep{k+1}"].append(1 if shared_ratio >= 0.6 else 0)

                eh_desc = str((e_cur.get("endingHook") or {}).get("description") or "")
                nxt_b1 = ""
                if e_nxt.get("beats"):
                    nxt_b1 = str(e_nxt["beats"][0].get("description") or "") + " " + str(e_nxt.get("summary") or "")[:80]
                ov = token_overlap(eh_desc, nxt_b1)
                unresolved_hook_cont_by_pair[f"ep{k}->ep{k+1}"].append(1 if (ov >= 0.18 or shared_ratio >= 0.67) else 0)

    stats = {
        "train_drama_count": len(train_dramas),
        "dramas_with_summary_stages": len(eps_per_stage_list),
        "episodes_per_complete_event_stage": {
            "p25": pct(eps_per_stage_list, 0.25),
            "median": pct(eps_per_stage_list, 0.50),
            "mean": round(statistics.mean(eps_per_stage_list), 2) if eps_per_stage_list else 0.0,
            "p75": pct(eps_per_stage_list, 0.75),
            "p90": pct(eps_per_stage_list, 0.90),
        },
        "stages_per_50ep_window": {
            "p25": pct([float(x) for x in stage_counts_list], 0.25),
            "median": pct([float(x) for x in stage_counts_list], 0.50),
            "p75": pct([float(x) for x in stage_counts_list], 0.75),
        },
        "foreshadow_plant_to_payoff_span_eps": {
            "count": len(plant_to_resolve_spans),
            "p25": pct([float(x) for x in plant_to_resolve_spans], 0.25),
            "median": pct([float(x) for x in plant_to_resolve_spans], 0.50),
            "mean": round(statistics.mean(plant_to_resolve_spans), 2) if plant_to_resolve_spans else 0.0,
            "p75": pct([float(x) for x in plant_to_resolve_spans], 0.75),
        },
        "ep1_promise_resolved_at_episode": {
            "count": len(ep1_plant_resolve_eps),
            "p25": pct([float(x) for x in ep1_plant_resolve_eps], 0.25),
            "median": pct([float(x) for x in ep1_plant_resolve_eps], 0.50),
            "p75": pct([float(x) for x in ep1_plant_resolve_eps], 0.75),
        },
        "ep1_flashforward_or_pastlife_hook_rate": round(cold_open_flash_count / float(max(1, ep1_total_annotated)), 3),
        "cross_episode_same_scene_or_cast_continuation_rate": {
            k: round(sum(v) / float(max(1, len(v))), 3)
            for k, v in sorted(unresolved_hook_cont_by_pair.items())
        },
        "ep1_to_5_profile": {
            f"ep{eno}": {
                "top_functions": ep_func_by_num[eno].most_common(4),
                "top_ending_hooks": end_hook_by_num[eno].most_common(4),
                "median_active_characters": pct([float(x) for x in char_count_by_num[eno]], 0.50),
                "median_micro_beats": pct([float(x) for x in beat_count_by_num[eno]], 0.50),
                "median_payoffs": pct([float(x) for x in payoff_count_by_num[eno]], 0.50),
            }
            for eno in range(1, 6)
        },
        "stage_span_examples": stage_examples,
    }

    out_json = TRAIN_ROOT / "corpus" / "pacing_stats.json"
    out_md = TRAIN_ROOT / "corpus" / "pacing_event_span_report.md"
    out_json.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    es = stats["episodes_per_complete_event_stage"]
    fs = stats["foreshadow_plant_to_payoff_span_eps"]
    ep1r = stats["ep1_promise_resolved_at_episode"]
    cont = stats["cross_episode_same_scene_or_cast_continuation_rate"]

    md_lines = [
        "# 红果爆款短剧「跨集事件跨度与叙事节奏」实证基线报告（`train=105` 部严格隔离统计）",
        "",
        "## 一、核心发现：1 集根本承载不了 1 个完整戏剧事件！",
        "",
        f"- **单一完整戏剧阶段（Stage / Event Unit）平均跨集数**：中位数 **`{es['median']} 集/事件`**（均值 `{es['mean']} 集`，四分位区间 `{es['p25']} ～ {es['p75']} 集/事件`，P90 达 `{es['p90']} 集`）。",
        f"- **前 50 集包含的完整大事件（阶段）总数**：中位数仅 **`{stats['stages_per_50ep_window']['median']} 个大事件`**（四分位 `{stats['stages_per_50ep_window']['p25']} ～ {stats['stages_per_50ep_window']['p75']} 个`）。",
        f"- **第 1 集立下的核心反击承诺（如“收回婚车/撤回秘方打脸”）实际兑现集数**：中位数在 **第 `{ep1r['median']}` 集**（四分位 **第 `{ep1r['p25']} ～ {ep1r['p75']}` 集**），全剧伏笔从埋设到回收中位数跨 **`{fs['median']}` 集**（均值 `{fs['mean']}` 集）。",
        f"- **跨集同场/同事件无缝续接率**：`Ep1→Ep2` 高达 **`{cont.get('ep1->ep2', 0)*100:.1f}%`**，`Ep2→Ep3` 达 **`{cont.get('ep2->ep3', 0)*100:.1f}%`**，`Ep3→Ep4` 达 **`{cont.get('ep3->ep4', 0)*100:.1f}%`**。",
        f"- **第 1 集倒叙预告 / 前世闪回钩子占比**：**`{stats['ep1_flashforward_or_pastlife_hook_rate']*100:.1f}%`**。",
        "",
        "## 二、前 5 集逐集叙事职能（`episodeFunction`）与断章形态实证分布",
        "",
        "| 集号 | Top 叙事职能 (`episodeFunction`) | Top 集尾断章 (`endingHook`) | 活跃角色中位数 | 场内微节拍中位数 | 爽点兑现中位数 |",
        "|---:|---|---|---:|---:|---:|",
    ]
    for eno in range(1, 6):
        pf = stats["ep1_to_5_profile"][f"ep{eno}"]
        fn_str = ", ".join(f"`{k}`({v})" for k, v in pf["top_functions"][:3])
        hk_str = ", ".join(f"`{k}`({v})" for k, v in pf["top_ending_hooks"][:3])
        md_lines.append(
            f"| 第 {eno} 集 | {fn_str} | {hk_str} | {pf['median_active_characters']} | {pf['median_micro_beats']} | {pf['median_payoffs']} |"
        )

    md_lines += [
        "",
        "## 三、代表性爆款剧目「50集阶段数 vs 每事件跨集数」实证样本",
        "",
        "| 剧目 | 赛道 | 章节数 | 阶段数 | 每完整事件所跨集数 | 前两阶段实况 |",
        "|---|---|---:|---:|---:|---|",
    ]
    for ex in stage_examples:
        s12 = "<br>".join(ex["first_2_stages"])
        md_lines.append(
            f"| `{ex['drama']}` | {ex['genre']} | {ex['chapters']} | {ex['num_stages']} | **{ex['episodes_per_stage']} 集** | {s12} |"
        )

    out_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(out_md.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
