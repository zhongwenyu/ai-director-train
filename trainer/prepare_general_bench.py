#!/usr/bin/env python3
"""
Prepare Stratified Multi-Genre + Multi-Granularity (1-sentence & Rich-Brief) Benchmark
(`corpus/general_bench/dev_bench.json` & `test_bench.json`) + fix `train`-split 3-ep examples
(`examples/ancient_hit.md` & `examples/fantasy_system_hit.md`).

Strict anti-leakage & generalization guarantees:
  1. `examples/*.md` come 100% from `split == "train"`.
  2. `dev_bench.json` (6 dramas) comes 100% from `split == "dev"`, covering 4 genres
     (`都市情感`, `年代乡村`, `古装穿越`, `玄幻修仙`) AND 2 seed granularities (`concise_1s`, `rich_brief`).
  3. `test_bench.json` (6 Hongguo `split == "test"` dramas across 4 genres & 2 seed granularities
     + 1 held-out OOD verbatim user 3-paragraph brief `test_ood_hotpot2005` = 7 items) is LOCKED unseen!
  4. All LLM calls run via isolated `agy` (`gemini-4-carbon-medium`) sub-agents (`cwd=/tmp/...`, zero `codex`).
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

TRAIN_ROOT = Path("/home/zhongwenyu/project/ai-director-train")
SKILL_DIR = TRAIN_ROOT / ".agents" / "skills" / "hit-short-drama"
GEN_BENCH_DIR = TRAIN_ROOT / "corpus" / "general_bench"

sys.path.insert(0, str(TRAIN_ROOT / "trainer"))
import llm_clients as L  # noqa: E402
import prepare_assets as PA  # noqa: E402

CONCISE_SEED_PROMPT = """你是一位短剧策划总监。请根据下面某部短剧的前3集原片剧本，提炼出一句**极简的一句话核心创意种子（50～85字）**，用于测试编剧系统对短种子的扩写与张力构建能力。

要求：
1. 只用 **1～2 句话（50～85个汉字）** 概括主角处境、核心冲突与原生情绪爽点方向。
2. **不出现具体人名**（方便盲测对比），严禁写“第一集、第二集”分集剧透。
3. 直接输出这一句话正文，不要引号或解释。

原片前3集参考：
{script_3ep}
"""

RICH_BRIEF_SEED_PROMPT = """你是一位提供原创故事构想的创作者。请根据下面这部短剧的全剧总结（及前3集参考），还原出一段**220～380字的口述式多句故事创意简报**，用于测试编剧系统对“多细节长创意”的核心冲突保真与情感张力提炼能力。

要求：
1. 用自然平实的口述段落（220～380字，不分集、不列提纲标题）讲清：主角是谁、过往与他人的恩怨/付出关系、当前关键冲突是如何引爆的、对手/前任的误判与后续走向、以及主角如何反击逆袭至终局。
2. **为了与原片盲测对齐，不保留原片具体人名**（统一用“男主/女主”或全新普通姓氏指代即可），严禁写“第一集、第二集”字样。
3. 直接输出这段创意简报正文，不要任何寒暄或标题。

全剧总结参考：
{summary_md}

原片前3集参考：
{script_3ep}
"""

USER_VERBATIM_HOTPOT_BRIEF = (
    "男主叶寻重生前是一家连锁火锅店的总厨，他手里有爷爷传承下来的火锅配方，能让人吃了火锅后不上火反而身体变得更好，"
    "靠着这个配方他把原本局限在四川小地方的火锅店做成了全国连锁，让外地原本不习惯火锅的客户也喜欢上他们家的火锅，准备上市前夕。"
    "火锅店的老板是男主的女朋友林双双，也是大学时期的情侣，那时林双双家里经营的饭店客源不佳，即将倒闭，是男主帮忙，"
    "用自家的配方制作火锅，才让这家即将倒闭的饭店浴火重生成连锁火锅店。男主本性稳重踏实，勤勤恳恳，努力把火锅店做大做强，"
    "后面为了火锅店上市，更是把配方贡献给了火锅店，但林双双一直习惯了男主的付出，反而认为是理所当然。"
    "楚南是男主的室友，是个富二代，不学无术，大学毕业出国留学，其实是花钱买个水硕，留学回来把自己包装成海归精英，"
    "让林双双误以为是人才，重金邀请加入了火锅店，当了负责经营推广的经理，但之后没干什么事情，整天在林双双周围转，各种拍马屁，"
    "反而是男主背后一直努力把火锅店做大做强。但林双双没有看到男主的付出，反而认为火锅店能做大做强全是楚南的功劳，"
    "然后在上市前夕听从了楚南的建议，把西餐融入火锅，能扩大火锅店的国际口味，并且打算聘用楚南带来的草包厨师赵帆为总厨，"
    "认为男主已经落伍了，不配当上市连锁店的总厨。楚南对男主极致嘲讽，林双双也在旁边帮腔羞辱男主。\n"
    "男主遭此重创，收拾东西走出火锅店，浑浑噩噩间被车撞了重生到大学期间林双双烦恼家里饭店经营不善，男主之前答应林双双说自己可以帮忙做火锅，"
    "这时楚南在旁边嘲讽男主的是过时的，没跟上时代的节奏，建议林双双把饭店做成西餐厅，说自己认识大厨可以帮忙。"
    "男主重生过来后，认识到了当前的情况，果断拒绝并符合了楚南的话，转身就走，然后在学校里碰到了学姐夏芊芊，"
    "夏芊芊男主的青梅竹马，一直对男主有好感，家里经营了一家中餐厅，叶家和夏家长辈也认识，一直以为男主和夏芊芊会走到一起，"
    "但男主前世沉迷在林双双这里错过了夏芊芊，前世后面林双双一直不喜欢夏芊芊，暗地里各种打击，逼迫夏芊芊家里的餐馆倒闭最终夏家搬离了当地，"
    "临走前夏芊芊提醒男主要提防林双双和楚南，但男主没当回事。\n"
    "男主重生后选择和夏芊芊一起努力，重新把火锅做了起来，而同时林双双听了楚南的话把家里的饭店转成了西餐厅，还聘用了楚南推荐的草包厨师，"
    "结果刚开店因为西餐厅款式新颖，吸引了不少客户，为此楚南和林双双还过去嘲讽男主和夏芊芊的中餐厅，认为已经跟不上时代了。"
    "结果没过多久，因为草包厨师厨艺不行导致客流量流失，楚南建议林双双贷款花巨资打广告吸引用户，到最后林双双背负债务餐厅倒闭，"
    "而男主和夏芊芊的连锁火锅店上市成功，男主当上了董事长，并向夏芊芊求婚，两人举办婚礼。\n"
    "重生后的时间点是2005年，地点是重庆，男女主都在重庆大学。"
)


def convert_3ep_for_drama(drama: Dict[str, Any], out_file: Path) -> str:
    if out_file.is_file() and out_file.stat().st_size > 1500:
        return out_file.read_text(encoding="utf-8")

    ndir = Path(drama["novel_dir"])
    dur = int(round(drama.get("median_duration_sec") or 120))

    def conv_ep(ep_no: int) -> str:
        ch_path = ndir / f"第{ep_no:03d}章.md"
        if not ch_path.is_file():
            cands = [p for p in sorted(ndir.glob(f"*{ep_no:03d}*.md")) if p.name != "summary.md"]
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

    ep_texts = [conv_ep(ep_no) for ep_no in (1, 2, 3)]
    combined = "\n\n---\n\n".join(t.strip() for t in ep_texts) + "\n"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(combined, encoding="utf-8")
    return combined


def distill_seed(drama: Dict[str, Any], script_3ep: str, seed_mode: str, seed_file: Path) -> str:
    if seed_file.is_file() and seed_file.stat().st_size > 40:
        return seed_file.read_text(encoding="utf-8").strip()
    if seed_mode == "rich_brief":
        sp = drama.get("summary_path") or ""
        sum_md = Path(sp).read_text(encoding="utf-8")[:6500] if (sp and Path(sp).is_file()) else ""
        s = L.call_agy(
            RICH_BRIEF_SEED_PROMPT.format(summary_md=sum_md, script_3ep=script_3ep[:6500]),
            model="gemini-4-carbon-medium",
            effort="medium",
            timeout=300,
            validator=lambda t: 160 <= len(t.strip()) <= 520,
        ).strip()
    else:
        s = L.call_agy(
            CONCISE_SEED_PROMPT.format(script_3ep=script_3ep[:8500]),
            model="gemini-4-carbon-medium",
            effort="medium",
            timeout=240,
            validator=lambda t: 30 <= len(t.strip()) <= 160,
        ).strip()
    seed_file.parent.mkdir(parents=True, exist_ok=True)
    seed_file.write_text(s + "\n", encoding="utf-8")
    return s


def main() -> None:
    manifest = json.loads((TRAIN_ROOT / "corpus" / "manifest.json").read_text(encoding="utf-8"))["dramas"]
    by_id = {v["id"]: v for v in manifest.values()}

    # 1) Fix train-split 3-ep continuous examples for ancient_hit.md (092) & fantasy_system_hit.md (037)
    for ex_id, ex_name in [("092", "ancient_hit.md"), ("037", "fantasy_system_hit.md")]:
        d = by_id[ex_id]
        assert d["split"] == "train", f"Example {ex_id} must be train split!"
        ex_out = SKILL_DIR / "examples" / ex_name
        # Rebuild if < 3 episodes
        cur = ex_out.read_text(encoding="utf-8") if ex_out.is_file() else ""
        if cur.count("【本集完】") < 3:
            print(f"[example] Converting train drama {ex_id} ({d['title']}) -> {ex_name} (3 continuous eps)...", flush=True)
            ex_tmp = GEN_BENCH_DIR / "train_examples" / ex_name
            txt = convert_3ep_for_drama(d, ex_tmp)
            ex_out.write_text(txt, encoding="utf-8")
            print(f"[example] Saved {ex_out} ({len(txt)} chars)", flush=True)

    # 2) Stratified DEV benchmark (6 dramas across 4 genres & 2 seed granularities)
    dev_specs = [
        {
            "bench_id": "dev_066",
            "id": "066",
            "seed_mode": "concise_1s",
            "existing_gt": TRAIN_ROOT / "corpus/pacing_bench/dev/dev_066_gt_ep001-003.md",
            "existing_seed": TRAIN_ROOT / "corpus/pacing_bench/dev/dev_066_seed.txt",
        },
        {
            "bench_id": "dev_014",
            "id": "014",
            "seed_mode": "rich_brief",
            "existing_gt": None,
            "existing_seed": None,
        },
        {
            "bench_id": "dev_023",
            "id": "023",
            "seed_mode": "rich_brief",
            "existing_gt": None,
            "existing_seed": None,
        },
        {
            "bench_id": "dev_067",
            "id": "067",
            "seed_mode": "concise_1s",
            "existing_gt": None,
            "existing_seed": None,
        },
        {
            "bench_id": "dev_098",
            "id": "098",
            "seed_mode": "concise_1s",
            "existing_gt": None,
            "existing_seed": None,
        },
        {
            "bench_id": "dev_112",
            "id": "112",
            "seed_mode": "concise_1s",
            "existing_gt": None,
            "existing_seed": None,
        },
    ]

    # 3) Locked Unseen TEST benchmark (6 Hongguo dramas across 4 genres & 2 seed granularities + 1 held-out OOD brief)
    test_specs = [
        {
            "bench_id": "test_007",
            "id": "007",
            "seed_mode": "rich_brief",
            "existing_gt": None,
            "existing_seed": None,
        },
        {
            "bench_id": "test_011",
            "id": "011",
            "seed_mode": "rich_brief",
            "existing_gt": None,
            "existing_seed": None,
        },
        {
            "bench_id": "test_054",
            "id": "054",
            "seed_mode": "concise_1s",
            "existing_gt": None,
            "existing_seed": None,
        },
        {
            "bench_id": "test_102",
            "id": "102",
            "seed_mode": "concise_1s",
            "existing_gt": None,
            "existing_seed": None,
        },
        {
            "bench_id": "test_085",
            "id": "085",
            "seed_mode": "concise_1s",
            "existing_gt": TRAIN_ROOT / "corpus/pacing_bench/test/test_085_gt_ep001-003.md",
            "existing_seed": TRAIN_ROOT / "corpus/pacing_bench/test/test_085_seed.txt",
        },
        {
            "bench_id": "test_137",
            "id": "137",
            "seed_mode": "concise_1s",
            "existing_gt": None,
            "existing_seed": None,
        },
    ]

    def process_one(sp: Dict[str, Any], split_name: str) -> Dict[str, Any]:
        bid = sp["bench_id"]
        d = by_id[sp["id"]]
        assert d["split"] == split_name, f"Split mismatch {bid}: {d['split']} != {split_name}"
        gt_path = GEN_BENCH_DIR / split_name / f"{bid}_gt_ep001-003.md"
        seed_path = GEN_BENCH_DIR / split_name / f"{bid}_seed.txt"
        gt_path.parent.mkdir(parents=True, exist_ok=True)

        if sp["existing_gt"] and Path(sp["existing_gt"]).is_file():
            gt_txt = Path(sp["existing_gt"]).read_text(encoding="utf-8")
            gt_path.write_text(gt_txt, encoding="utf-8")
        else:
            gt_txt = convert_3ep_for_drama(d, gt_path)

        if sp["existing_seed"] and Path(sp["existing_seed"]).is_file():
            seed_txt = Path(sp["existing_seed"]).read_text(encoding="utf-8").strip()
            seed_path.write_text(seed_txt + "\n", encoding="utf-8")
        else:
            seed_txt = distill_seed(d, gt_txt, sp["seed_mode"], seed_path)

        print(f"[bench-ready] {bid} ({d['genre']} | {sp['seed_mode']}): {len(seed_txt)} chars seed, {len(gt_txt)} chars GT", flush=True)
        return {
            "bench_id": bid,
            "drama_id": sp["id"],
            "split": split_name,
            "genre": d["genre"],
            "title_ref": d["title"],
            "seed_mode": sp["seed_mode"],
            "seed": seed_txt,
            "gt_path": str(gt_path),
        }

    with cf.ThreadPoolExecutor(max_workers=4) as pool:
        dev_futs = [pool.submit(process_one, sp, "dev") for sp in dev_specs]
        test_futs = [pool.submit(process_one, sp, "test") for sp in test_specs]
        dev_items = [f.result() for f in dev_futs]
        test_items = [f.result() for f in test_futs]

    # Append OOD held-out user verbatim 3-paragraph creative brief to test_bench.json (gt_path=None -> single-arc fidelity & tension evaluation)
    test_items.append({
        "bench_id": "test_ood_hotpot2005",
        "drama_id": "ood_hotpot2005",
        "split": "test_ood",
        "genre": "都市年代重生商战情感",
        "title_ref": "2005重庆大学火锅vs西餐厅原始三段创意",
        "seed_mode": "rich_brief",
        "seed": USER_VERBATIM_HOTPOT_BRIEF,
        "gt_path": None,
    })

    GEN_BENCH_DIR.mkdir(parents=True, exist_ok=True)
    (GEN_BENCH_DIR / "dev_bench.json").write_text(json.dumps(dev_items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (GEN_BENCH_DIR / "test_bench.json").write_text(json.dumps(test_items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"DONE! Saved {len(dev_items)} DEV items and {len(test_items)} TEST items in {GEN_BENCH_DIR}", flush=True)


if __name__ == "__main__":
    main()
