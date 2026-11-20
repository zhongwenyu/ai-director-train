#!/usr/bin/env python3
"""
Step 0: Calibrate `general_arena_judge.py` (`judge/calibration_general_v6/calibration_report.json`)
before running generalized autoregressive evolution.

Verifies two hard requirements using 100% isolated `agy` (`gemini-4-carbon-medium`) sub-agents:
  1. Single-Arc Gate Discrimination (8 cases across 4 genres & 4 distinct failure modes):
     - 4 Real Hongguo `train`-split continuous 3-ep arcs (`urban`, `rural_era`, `ancient`, `fantasy_system`) -> PASS_HIT_READY
     - 4 Real Failure Modes:
       a) Template-hijacked / magic-rewritten seed (`v5` apprentice-banquet script vs user's 3-paragraph college Western-vs-hotpot seed) -> REJECT_REWRITE
       b) Dry compliance/accounting audit prose (`v1` sanitation-doc & soap-ledger outline/script) -> REJECT_REWRITE
       c) Timeline & motivation paradox (`P09` / early hatred contradicting 10-year partnership) -> REJECT_REWRITE
       d) Fast-forward plot cramming (6 major events crammed into 3 episodes) -> REJECT_REWRITE
  2. Swap-Debiased Pairwise Consistency (`A vs B` and `B vs A`): 100% swap-consistent preference for hit-ready arcs over flawed arcs.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

TRAIN_ROOT = Path("/home/zhongwenyu/project/ai-director-train")
SKILL_DIR = TRAIN_ROOT / ".agents" / "skills" / "hit-short-drama"
OUT_DIR = TRAIN_ROOT / "judge" / "calibration_general_v6"

sys.path.insert(0, str(SKILL_DIR / "scripts"))
sys.path.insert(0, str(TRAIN_ROOT / "trainer"))
import general_arena_judge as GJ  # noqa: E402
from prepare_general_bench import USER_VERBATIM_HOTPOT_BRIEF  # noqa: E402

SYNTH_TIMELINE_PARADOX_SCRIPT = """# 第 1 集　离婚书拍脸
**预估时长**：约115秒

## 1-1　内　苏家别墅客厅　夜
**人物**：顾沉、苏晚、秦少

[画面文字] 2025年，结婚十周年纪念日
△ 顾沉端着药碗跪在地上咳血，妻子苏晚挽着秦少冷笑把离婚协议砸在他脸上。
苏晚：顾沉，你替我顾家做牛做马十年又怎样？公司上市了，你这种下贱货色早该滚了！
[VO] 顾沉：我为苏晚隐忍付出整整十年，没想到换来毒发身亡！

## 1-2　内　2015年苏家大厅　日
**人物**：顾沉、苏晚、苏母

[画面文字] 重生回到2015年刚领证第一天
△ 顾沉猛然睁眼坐在椅子上，还没开口说话，苏晚和苏母直接把行李箱砸到他脚边破口大骂。
苏母：顾沉你个臭要饭的！今天就算领了证你也立刻给我滚出苏家大门，我们晚晚昨晚就跟秦少好上了，看见你就恶心！
苏晚：没错！赶紧签字离婚滚蛋，我一秒钟都不会让你进我苏家公司半步！
顾沉：好，这可是你们让我走的！
【本集完】

# 第 2 集　净身出户
**预估时长**：约105秒

## 2-1　内　2015年苏家大厅　日
**人物**：顾沉、苏晚、苏母

△ 顾沉抓起笔签完离婚协议转身出门。
苏晚：算你识相，快滚！
顾沉：你们别后悔！
【本集完】

# 第 3 集　偶遇女首富白送半壁江山
**预估时长**：约110秒

## 3-1　外　马路边　日
**人物**：顾沉、沈冰

△ 顾沉刚走出大门，陌生百亿女总裁沈冰突然停下车递过一份股权转让书。
沈冰：先生面相非凡，我无条件把千亿集团百分之五十股份白送给你，请你当董事长！
△ 顾沉一言不发直接按了手印。
【本集完】
"""

SYNTH_CRAMMED_FAST_FORWARD_SCRIPT = """# 第 1 集　断亲夺厂上市
**预估时长**：约120秒

## 1-1　内　周家老宅　日
**人物**：周牧、周母、周强

△ 周母抢过周牧的拆迁款塞给弟弟周强。
周母：你是哥哥，三十万拆迁款全给你弟买房！
周牧：从今天起我们断绝关系！

## 1-2　内　县城机械厂　日
**人物**：周牧、厂长

△ 周牧转头跑到机械厂，两句话修好进口机床。
厂长：神了！我把整座机械厂送给你当厂长！

## 1-3　内　省城展销会　日
**人物**：周牧、外商

△ 外商当场签下一千万美元订单。
外商：周厂长，我们包下你三年全部产能！
【本集完】

# 第 2 集　跨国并购与弟弟破产
**预估时长**：约115秒

## 2-1　内　赌坊　夜
**人物**：周强、周母

△ 周强把三十万输光被债主追债。
周母：快去找你哥要钱！

## 2-2　内　省城集团总部　日
**人物**：周牧、秘书

△ 秘书汇报周牧已收购全省十家工厂并拿下海外专利。
周牧：把周强拒之门外！
【本集完】

# 第 3 集　敲钟上市全家跪哭
**预估时长**：约115秒

## 3-1　内　证券交易所　日
**人物**：周牧、周母、周强

△ 周牧敲钟上市身家百亿，周母和周强跪在大门外痛哭求原谅。
周母：儿啊，妈错了！
周牧：晚了！保安撵走！
【本集完】
"""

SYNTH_DRY_AUDIT_SCRIPT = """# 第 1 集　科目核销与卫生目录合规
**预估时长**：约125秒

## 1-1　内　小馆柜台　日
**人物**：陈默、林芳

△ 陈默摊开三本账册与卫法监发51号文件复印件，逐行核对折旧科目。
陈默：按卫法监发2002第51号药食同源目录，金银花与砂仁配比合规，三日进油六十斤经氢氧化钠皂化后凝成硬皂块五十八点五斤，损耗率百分之二点五，环卫签收单在第三页。
林芳：流动周转金扣除盘溪香料两千一百元与二手铜锅两千五百元摊销后，账面净余三千三百六十元，日均坪效需达一点八倍才能覆盖半年度租金摊提。
陈默：明天上午九点先去区公证处办理技术独占许可备案，再递交第四十三类餐饮商标初审回执。
【本集完】

# 第 2 集　穿堂共有产权附图测绘
**预估时长**：约120秒

## 2-1　内　小馆后院　日
**人物**：陈默、林芳

△ 两人拿着卷尺测量一米八宽的过道并核对房产证附图红线。
林芳：根据一九九八年房改测绘附图第十二页，该一米八遮雨侧廊计入前铺专有建筑面积，未设立不动产地役权登记。
陈默：所以我们必须按月计提三千六百元偿债准备金，确保现金流覆盖率大于一点三五。
【本集完】

# 第 3 集　股改消除单一自然人依赖预案
**预估时长**：约120秒

## 3-1　内　办公室　日
**人物**：陈默、林芳

△ 陈默指着白板上的股权架构图继续讲解合规条款。
陈默：按主板发行审核备忘录第十四条，无形资产须经无关联第三方评估作价注入拟上市主体，消除对单一自然人的重大技术依赖。
林芳：同意，一致行动人协议按百分之六十七表决权锁定。
【本集完】
"""


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ex_dir = SKILL_DIR / "examples"

    v5_hijacked_script = (TRAIN_ROOT / "productions/2005_chongqing_hotpot_v5/combined_1-3.md").read_text(encoding="utf-8")
    v5_hijacked_outline = (TRAIN_ROOT / "productions/2005_chongqing_hotpot_v5/01_outline.md").read_text(encoding="utf-8")
    v1_dry_outline = (TRAIN_ROOT / "productions/2005_chongqing_hotpot/01_outline.md").read_text(encoding="utf-8")

    cases: List[Dict[str, Any]] = [
        # 4 Multi-Genre Real Hongguo Positives (train split)
        {
            "case_id": "POS_urban_128",
            "expected": "PASS_HIT_READY",
            "seed": "隐瞒富裕身份补贴岳家的女婿吃年夜饭，岳父母给三个孙子各发两千红包却唯独漏掉他女儿还逼他让出新手机，女婿寒心收回三十六万养老金清算。",
            "outline": "",
            "script": (ex_dir / "urban_hit.md").read_text(encoding="utf-8"),
        },
        {
            "case_id": "POS_rural_013",
            "expected": "PASS_HIT_READY",
            "seed": "老实汽修工被黑心叔婶拖欠一年工钱并用破烂旧物抵账，他意外听见旧物心声识破古董与故障玄机，果断离开自立门户逆袭。",
            "outline": "",
            "script": (ex_dir / "rural_era_hit.md").read_text(encoding="utf-8"),
        },
        {
            "case_id": "POS_ancient_092",
            "expected": "PASS_HIT_READY",
            "seed": "天生神力却一心想当文弱谋士的壮汉去军营应聘军师，随手托起滚落巨石救下全营，在乱世军营开启反差成名路。",
            "outline": "",
            "script": (ex_dir / "ancient_hit.md").read_text(encoding="utf-8"),
        },
        {
            "case_id": "POS_fantasy_037",
            "expected": "PASS_HIT_READY",
            "seed": "落魄青年发现祖传戒指能连通修仙异界与现代都市，靠两边物资差价倒卖换取灵石黄金，强势化解现实危机横推万宗。",
            "outline": "",
            "script": (ex_dir / "fantasy_system_hit.md").read_text(encoding="utf-8"),
        },
        # 4 Distinct Generalized Failure Modes
        {
            "case_id": "NEG_template_hijack_v5",
            "expected": "REJECT_REWRITE",
            "seed": USER_VERBATIM_HOTPOT_BRIEF,
            "outline": v5_hijacked_outline,
            "script": v5_hijacked_script,
        },
        {
            "case_id": "NEG_dry_audit_filler",
            "expected": "REJECT_REWRITE",
            "seed": "男主带祖传清润火锅秘方与青梅学姐创业，前女友听信室友改开西餐厅先火后垮追悔莫及。",
            "outline": v1_dry_outline[:6000],
            "script": SYNTH_DRY_AUDIT_SCRIPT,
        },
        {
            "case_id": "NEG_timeline_paradox",
            "expected": "REJECT_REWRITE",
            "seed": "为妻子家族做牛做马十年的丈夫在上市夜被背叛害死，重生回十年前刚领证当天果断抽身离开。",
            "outline": "",
            "script": SYNTH_TIMELINE_PARADOX_SCRIPT,
        },
        {
            "case_id": "NEG_fast_forward_cramming",
            "expected": "REJECT_REWRITE",
            "seed": "被偏心母亲逼让拆迁款的长子果断断亲，凭修机床绝活在县城一步步建厂逆袭。",
            "outline": "",
            "script": SYNTH_CRAMMED_FAST_FORWARD_SCRIPT,
        },
    ]

    def run_single(c: Dict[str, Any]) -> Dict[str, Any]:
        rep = GJ.audit_drama_general(c["script"], seed=c["seed"], outline_md=c["outline"])
        matched = rep["verdict"] == c["expected"]
        print(
            f"[calib-single] {c['case_id']}: expected={c['expected']} actual={rep['verdict']} "
            f"(score={rep['total_score']}, flaws={[f['flaw_type'] for f in rep['flaws']]}) -> {'OK' if matched else 'MISMATCH'}",
            flush=True,
        )
        return {
            "case_id": c["case_id"],
            "expected": c["expected"],
            "actual": rep["verdict"],
            "matched": matched,
            "total_score": rep["total_score"],
            "scores": rep["scores"],
            "flaws": rep["flaws"],
        }

    with cf.ThreadPoolExecutor(max_workers=4) as pool:
        single_results = list(pool.map(run_single, cases))

    # 4 Swap-Debiased Pairwise PKs
    pk_pairs = [
        ("PK1_urban_vs_crammed", cases[0]["script"], SYNTH_CRAMMED_FAST_FORWARD_SCRIPT, ""),
        ("PK2_rural_vs_dry_audit", cases[1]["script"], SYNTH_DRY_AUDIT_SCRIPT, ""),
        ("PK3_ancient_vs_paradox", cases[2]["script"], SYNTH_TIMELINE_PARADOX_SCRIPT, ""),
        ("PK4_fantasy_vs_crammed", cases[3]["script"], SYNTH_CRAMMED_FAST_FORWARD_SCRIPT, ""),
    ]

    pk_results = []
    for pid, good_s, bad_s, sd in pk_pairs:
        pk = GJ.compare_swap_debiased_general("GOOD_HIT", good_s, "BAD_FLAWED", bad_s, seed=sd, parallel_swaps=True)
        ok = pk["winner"] == "GOOD_HIT" and pk["swap_consistent"]
        print(f"[calib-pk] {pid}: winner={pk['winner']} swap_consistent={pk['swap_consistent']} -> {'OK' if ok else 'FAIL'}", flush=True)
        pk_results.append({"pair_id": pid, "ok": ok, **pk})

    single_acc = sum(1 for r in single_results if r["matched"])
    pk_acc = sum(1 for r in pk_results if r["ok"])
    report = {
        "single_gate_accuracy": f"{single_acc}/{len(single_results)}",
        "pairwise_swap_accuracy": f"{pk_acc}/{len(pk_results)}",
        "all_passed": (single_acc == len(single_results) and pk_acc == len(pk_results)),
        "single_results": single_results,
        "pairwise_results": pk_results,
    }
    out_file = OUT_DIR / "calibration_report.json"
    out_file.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"CALIBRATION SUMMARY: single={report['single_gate_accuracy']}, pk={report['pairwise_swap_accuracy']}, all_passed={report['all_passed']}", flush=True)


if __name__ == "__main__":
    main()
