#!/usr/bin/env python3
"""
Build the 12-pair De-styled + Poison-Pill Audience Calibration Benchmark (`calibration_v2`):
  - Pairs 01..08: De-styled Real Hongguo Hit Ep 1-3 (stripped of ALL camera/watermark/wardrobe inventory bloat)
                  vs `hit-short-drama v3` Ep 1-3 generated from a 50-85 char ultra-short one-sentence idea!
  - Pairs 09..12: Controlled same-style Poison-Pill pairs testing exact common-sense motivation,
                  contrived crisis, side-quest detour, and ally-suspicion failure modes (including hotpot_v2!).
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

TRAIN_ROOT = Path("/home/zhongwenyu/project/ai-director-train")
sys.path.insert(0, str(TRAIN_ROOT / "trainer"))
sys.path.insert(0, str(TRAIN_ROOT / "runs/candidates/v3/scripts"))

import llm_clients as L  # noqa: E402
import write_drama as WD_V3  # noqa: E402

CORPUS_MANIFEST = TRAIN_ROOT / "corpus/manifest.json"
BENCH_DIR = TRAIN_ROOT / "judge/calibration_v2/benchmark"
V3_SKILL_DIR = TRAIN_ROOT / "runs/candidates/v3"

DESTYLE_EPISODE_PROMPT = """你是一位资深的短剧剧本去皮标准化编辑。下面是一集已上线短剧的「视频画面拉片还原稿」。
请将它转换为**与人类编剧初稿完全同构的纯净标准剧本格式**，用于双盲评测。

### 去皮同构铁律（防止评测模型靠表面文风作弊，必须严格执行！）
1. **100% 忠实保留剧情与台词**：完全保留原片的人物姓名、身份关系、每一句台词原意（仅修正明显同音错字）、出场顺序、关键道具与金额数字、核心戏剧动作和集尾断章钩子！严禁删减冲突或自行改写剧情走向。
2. **彻底清除拉片外貌与穿搭报菜名（极重要！）**：原稿中凡是“身穿米白色毛绒开衫”“留着齐耳短发、身穿深色碎花衬衫”“左腕戴着玉镯”“盘着微卷短发”等视频拉片特有的外貌衣着描写，**一律彻底删净**（除非某件衣物本身就是推动剧情的核心道具，如“沾满黑油的工装”“染血的衬衫”）！
3. **彻底清除摄影机、后期与切镜词**：删掉所有“近景/特写/远景/过肩镜头/切至/推近/定格/画中画/配乐/水印/00:12”等术语；将连续碎镜头合并为自然流畅的场次（每集 1～3 场，`## {ep_num}-1`、`## {ep_num}-2`），每场 `△` 动作控制在简练有画面感的短句（与常规编剧手稿密度一致）。
4. **标准输出格式**（直接输出 Markdown 剧本正文，绝不带任何解释）：

# 第{ep_num}集　<4-9字集名>
**预估时长**：约{dur_sec}秒

## {ep_num}-1　<内/外>　<场景名>　<日/夜>
**人物**：<本场人物，顿号分隔>

[画面文字] <仅保留原片对剧情必要的时空/身份/手机屏幕信息，无则不写>
△ <简练精悍的戏剧动作与神态反应，不含任何穿搭报菜名或机位词>
角色名：<台词>
[VO] 角色名：<内心独白/旁白>

【本集完】

### 原片拉片稿（第 {ep_num} 集，原片时长约 {dur_sec} 秒）
剧名：《{title}》
{raw_md}
"""

REAL_TARGETS = [
    (
        "P01_013_antique",
        "013_",
        "千禧年汽修学徒被黑心亲叔白使唤一年赖掉三千六工钱，手血意外唤醒听见旧物说话的异能，果断辞工拿抵账破烂捡漏暴富打脸叔婶。",
    ),
    (
        "P02_097_gaokao93",
        "097_",
        "老实长子被吸血弟妹榨干惨死，重生回1993年全县高考状元放榜日，面对亲爹逼他把录取通知书让给弟弟去工地搬砖，当场护证断亲逆袭。",
    ),
    (
        "P03_139_autopay87",
        "139_",
        "舔狗男友被拜金女友提分手羞辱，平静吃完最后一碗粉，默默在手机上逐一取消替她绑定的房租车贷等87项自动代付，看她瞬间破防。",
    ),
    (
        "P04_145_bnb_sell",
        "145_",
        "姐姐花两百五十万买房装修成民宿免费给失业弟弟一家经营，国庆回家住两晚竟被弟媳按计算器收九百六房费、父母帮腔，姐姐直接全款卖掉民宿。",
    ),
    (
        "P05_128_redpacket",
        "128_",
        "隐瞒集团掌舵人身份的女婿过年随礼扶持岳家，岳母发压岁红包却唯独当众漏掉他女儿还出言刻薄，女婿彻底寒心转身收回给岳家的一切。",
    ),
    (
        "P06_049_house_occupy",
        "049_",
        "好心把城里新房借给亲戚暂住三年救急，收房办婚事时亲戚竟鸠占鹊巢反咬一口要把房子据为己有，房主不再留情强势清场反击。",
    ),
    (
        "P07_001_poor_marry",
        "001_",
        "百亿总裁按爷爷遗愿穿旧衣回村履行娃娃亲试探人心，势利母女当众嫌贫退婚并苛待大姐，总裁转身看中善良受欺的大姐。",
    ),
    (
        "P08_085_hotpot_10m",
        "085_",
        "京圈太子爷以为温顺女友爱惨了自己，纵容绿茶女大抢位羞辱她；殊不知女友六年深情全是演戏，正偷偷变卖他闲置奢侈品凑够一千万去自由吃火锅。",
    ),
]


def destyle_real_ep1_3(pair_id: str, prefix: str, manifest: dict[str, Any]) -> Path:
    out_dir = BENCH_DIR / pair_id
    out_dir.mkdir(parents=True, exist_ok=True)
    real_p = out_dir / "real_equal_ep001-003.md"
    if real_p.is_file() and real_p.stat().st_size > 1500:
        return real_p

    _, drama = next((k, v) for k, v in manifest["dramas"].items() if k.startswith(prefix))
    dur = float(drama.get("median_duration_sec") or 95.0)
    # Match ~360-400s total story volume (same as 3 x 125s AI episodes!)
    n_ch = 5 if dur < 85 else (4 if dur < 118 else 3)
    nd = Path(drama["novel_dir"])
    raw_chunks = []
    for ch in range(1, n_ch + 1):
        cp = nd / f"第{ch:03d}章.md"
        if cp.is_file():
            raw_chunks.append(f"=== 原片第 {ch} 章 ===\n" + cp.read_text(encoding="utf-8")[:10000])

    prompt = (
        "你是一位资深的短剧剧本去皮标准化编辑。下面是已上线爆款短剧开篇约 6 分钟的「视频拉片还原稿」（共 "
        f"{len(raw_chunks)} 章短集）。\n"
        "请将其**100%忠实还原并按自然戏剧节点切分为标准的 3 集剧本（`# 第1集`、`# 第2集`、`# 第3集`，每集约 115～130 秒，总剧情量与原稿完全一致）**，用于同体量双盲评测！\n\n"
        "### 去皮同构与消重铁律（极重要！）\n"
        "1. **消除片头倒叙预演重复**：许多原片第 1 章开头 30 秒是第 2 章高潮的“倒叙预演片花”，随后打 `[一天前/二十分钟前]` 从头再演一遍同一幕！整理时**请直接按顺叙时间线合并同一幕戏，绝不要把同一场收房费/赶下车/抢座位的戏重复写两遍**！\n"
        "2. **100% 保留原片剧情、人物、活人台词原句与反转爽点**：严禁自己编造原片没有的剧情或删减核心交锋！\n"
        "3. **彻底清除拉片外貌穿搭报菜名与摄影机词**：删净所有“身穿米白开衫/留着短发/近景/切至/特写/水印/配乐/00:12”等拉片痕迹，保持与人类编剧初稿完全同构的简练 `△` 动作。\n"
        "4. 每集格式严格为 `# 第N集　<集名>`、`**预估时长**：约120秒`、`## N-1　内/外　场景　日/夜`、`**人物**：...`、`△ ...`、`角色：...`、`【本集完】`。直接输出第 1～3 集完整 Markdown 正文，不要任何前言解释。\n\n"
        f"剧名：《{drama['title']}》\n\n" + "\n\n".join(raw_chunks)
    )
    cleaned = L.call_agy(
        prompt,
        model="gemini-4-carbon-low",
        effort="low",
        timeout=420,
        validator=lambda t: (
            bool(re.search(r"^#\s*第\s*0*1\s*集", t, re.M))
            and bool(re.search(r"^#\s*第\s*0*2\s*集", t, re.M))
            and bool(re.search(r"^#\s*第\s*0*3\s*集", t, re.M))
            and "【本集完】" in t
            and "切至" not in t
        ),
    )
    real_p.write_text(cleaned.strip() + "\n", encoding="utf-8")
    return real_p


def generate_v3_ep1_3(pair_id: str, short_idea: str) -> Path:
    out_dir = BENCH_DIR / pair_id / "v3_gen"
    comb = out_dir / "combined_1-3.md"
    if comb.is_file() and comb.stat().st_size > 1200:
        return comb
    out_dir.mkdir(parents=True, exist_ok=True)
    WD_V3.run_pipeline(
        short_idea,
        out_dir,
        episodes_spec="1-3",
        batch_size=3,
        skill_dir=V3_SKILL_DIR,
        force=True,
    )
    return comb


POISON_SYNTH_PROMPT = """你是一位短剧编剧评测专家。请围绕以下同一个 60 字短剧创意，写出**两版格式与文风完全一致、均为第 1～2 集（每集约 110～130 秒，标准 `# 第1集`、`## 1-1`、`△`、`角色：`、`【本集完】` 格式）的对照剧本**，以 JSON 返回 `{{"clean_script": "...", "poison_script": "..."}}`：

### 短剧创意
{idea}

### A 版（`clean_script`：极致丝滑爆款版）必须做到：
1. **身份—动作 100% 常识自洽**：主角干这行的出身理由天经地义，普通人一秒信服、一秒代入。
2. **危机同源、主线锁死**：第 2 集盟友面临的危机**直接由第 1 集的核心反派打压/截胡造成**，主角出手救场就是在正面抽核心反派的脸！绝不插入无关紧要的路人恶霸水时长。
3. **盟友双向奔赴、爽感连贯**：救场成功后盟友干脆利落拍板合作，钩子来自反派迎面压上的下一轮正面交锋，台词短促有活人劲儿（单句平均 15～25 字）。

### B 版（`poison_script`：隐蔽槽点与爽感断流毒丸版——注意：不要写低幼乱码，要写成看似完整、实则踩中典型 AI 编剧暗坑的剧本！）必须埋入以下 3 个暗坑：
1. **人设违和暗坑**：给主角安一个高大上的 985 名校热门专业在校生身份，却毫无合理解释地让他像底层学徒一样去干苦力手艺活。
2. **巧合危机 + 支线路人注水暗坑**：第 1 集的反派在第 2 集完全隐身；第 2 集改成“盟友家里几天前突然扭伤手脚 + 一个毫无后续的一次性临时工坐地起价勒索几万块 + 下个月房租莫名其妙差一大截”，主角花整集跟这个路人临时工扯皮。
3. **盟友内耗憋屈钩子**：第 2 集结尾主角刚帮完忙拿出全部积蓄要合伙，盟友不仅不感激，反而冷脸质问主角“是不是跟前任吵架赌气拿我家救命钱当幌子”，让观众看得憋屈添堵。
"""


def build_poison_pairs() -> list[dict[str, Any]]:
    records = []

    # Pair 09: Real 2005_chongqing_hotpot_v2 (actual user-flagged script!) vs Clean Same-Root Hotpot Ep 1-2!
    p09_dir = BENCH_DIR / "P09_hotpot_2005"
    p09_dir.mkdir(parents=True, exist_ok=True)
    v2_full = (TRAIN_ROOT / "productions/2005_chongqing_hotpot_v2/episodes/ep001-003.md").read_text(encoding="utf-8")
    v2_eps = [s.strip() for s in re.split(r"(?=^#\s*第\s*\d+\s*集)", v2_full, flags=re.M) if s.strip()]
    p09_neg = p09_dir / "neg_ep001-002.md"
    p09_neg.write_text("\n\n\n".join(v2_eps[:2]) + "\n", encoding="utf-8")

    p09_pos = p09_dir / "pos_ep001-002.md"
    if not p09_pos.is_file():
        prompt_09 = """请根据以下设定写出极度丝滑、爽感拉满、零支线注水的《重回2005重庆老火锅》第 1～2 集标准短剧剧本（每集约 120 秒，格式 `# 第1集`、`## 1-1`、`△`、`角色：`、`【本集完】`，台词短促有力像活人说话）：
1. **身份自洽（零985当厨子违和）**：叶寻（20岁）是川渝老字号火锅传人遗孤，四年前为供青梅竹马的女友林双双考上并就读重庆大学，自己放弃学业在“林记小馆”后厨没日没夜熬了四年骨汤养她全家。2020年林记上市前夜他被林双双与海归男闺蜜楚南过河拆桥赶出雨巷撞车身亡，重生回2005年9月10日傍晚还未交出爷爷《清润红汤母本》这天！
2. **第1集干脆切割**：林双双考上大三后嫌弃叶寻是个没文凭的伙夫给她丢脸，当着重大校草楚南的面甩给叶寻一把钢丝球，宣布林记改开高档西餐厅请楚南表哥掌勺，让叶寻留后厨刷锅打杂。叶寻一把扯下穿了四年的油围裙裹住钢丝球拍回桌上，收回秘方、算清四年白干的账，当场断情走人！楚南林双双狂笑他一个没本钱的厨子离了林家连口锅都支不起来。
3. **第2集危机同源 + 正面打脸爽点（严禁路人老王、严禁女主猜忌！）**：叶寻走出门，正撞见对门三十米外“夏家老馆”的夏叔和青梅夏芊芊被林双双与楚南当街羞辱——原来楚南刚用学生会关系加回扣，恶意撬走了夏家今晚已经备好十桌鲜毛肚鸭肠的“经管院迎新包席”，逼夏家食材烂在锅里低价把铺面盘给林记扩建！夏芊芊父女毫不犹豫信任叶寻（夏叔早年受过叶爷爷恩惠），叶寻直接把两口大铜锅支在夏家店门外上风口，用鲜梨汁醪糟现场炒制零油烟清润红汤底料烫鲜毛肚免费试吃！霸道醇香顺风灌进斜对面冷清的林记，原本被楚南拉走的迎新大学生闻香全涌回夏家坐满十桌，林双双楚南站在空荡荡的门口脸色铁青！
直接输出第1集和第2集完整剧本正文，不要任何前言解释。"""
        txt09 = L.call_agy(
            prompt_09,
            model="gemini-4-carbon-medium",
            effort="medium",
            timeout=360,
            validator=lambda t: bool(re.search(r"#\s*第\s*0*1\s*集", t)) and bool(re.search(r"#\s*第\s*0*2\s*集", t)) and "【本集完】" in t,
        )
        p09_pos.write_text(txt09.strip() + "\n", encoding="utf-8")

    records.append({
        "pair_id": "P09_hotpot_2005",
        "kind": "poison_pill",
        "idea": "火锅传人重生回2005年撤回秘方踹掉忘恩女友，联手对门老店用清润红汤当街截流反杀。",
        "pos_path": str(p09_pos),
        "neg_path": str(p09_neg),
    })

    # Pairs 10..12: Diverse genres testing the exact same structural poison pills
    synth_ideas = [
        ("P10_clinic_1999", "中医正骨传人被势利未婚妻与海归院长之子抢走署名赶出医院，转身入驻斜对面被他们恶意断药挤兑的老医馆，一手绝活当场治好省队主力打脸前任。"),
        ("P11_garment_1996", "制版师姐姐累死累活把弟弟服装厂捧大却被弟媳算计赶走，重生回1996年撤回爆款版型图，联手被弟弟退单坑害的布行老板娘三天卖爆批发市场。"),
        ("P12_baker_2008", "糕点匠人被合伙女友与富二代踢出局，重生回2008年护住古法桃酥秘方，接手被他们联手断供面粉的街口老饼铺，开业当天排队长龙排到前任店门口。"),
    ]
    schema = {
        "type": "object",
        "properties": {
            "clean_script": {"type": "string"},
            "poison_script": {"type": "string"},
        },
        "required": ["clean_script", "poison_script"],
        "additionalProperties": False,
    }
    for pid, idea in synth_ideas:
        pdir = BENCH_DIR / pid
        pdir.mkdir(parents=True, exist_ok=True)
        pos_p = pdir / "pos_ep001-002.md"
        neg_p = pdir / "neg_ep001-002.md"
        if not (pos_p.is_file() and neg_p.is_file()):
            raw = L.call_agy(
                POISON_SYNTH_PROMPT.format(idea=idea),
                model="gemini-4-carbon-medium",
                effort="medium",
                schema=schema,
                timeout=420,
            )
            obj = L.extract_first_json(raw)
            pos_p.write_text(obj["clean_script"].strip() + "\n", encoding="utf-8")
            neg_p.write_text(obj["poison_script"].strip() + "\n", encoding="utf-8")
        records.append({
            "pair_id": pid,
            "kind": "poison_pill",
            "idea": idea,
            "pos_path": str(pos_p),
            "neg_path": str(neg_p),
        })
    return records


def main() -> None:
    os.environ["HIT_DRAMA_BLIND_ROUNDS"] = "0"
    BENCH_DIR.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(CORPUS_MANIFEST.read_text(encoding="utf-8"))

    all_pairs: list[dict[str, Any]] = []

    def prep_real_pair(item):
        pid, pfx, idea = item
        print(f"[bench] Preparing {pid} (de-styling real hit + running v3 from {len(idea)}-char seed)...", flush=True)
        with cf.ThreadPoolExecutor(max_workers=2) as sub:
            fr = sub.submit(destyle_real_ep1_3, pid, pfx, manifest)
            fv = sub.submit(generate_v3_ep1_3, pid, idea)
            real_p = fr.result()
            v3_p = fv.result()
        print(f"[bench] Done {pid}!", flush=True)
        return {
            "pair_id": pid,
            "kind": "real_vs_v3_short_seed",
            "idea": idea,
            "pos_path": str(real_p),
            "neg_path": str(v3_p),
        }

    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(prep_real_pair, it) for it in REAL_TARGETS]
        for f in cf.as_completed(futs):
            all_pairs.append(f.result())

    all_pairs.sort(key=lambda x: x["pair_id"])
    all_pairs.extend(build_poison_pairs())

    manifest_out = BENCH_DIR / "pairs_manifest.json"
    manifest_out.write_text(json.dumps(all_pairs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Benchmark v2 ready: {len(all_pairs)} pairs saved to {manifest_out}", flush=True)


if __name__ == "__main__":
    main()
