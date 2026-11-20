#!/usr/bin/env python3
"""Prepare clean gold screenplay slices (from TRAIN) and 200-500 char creative seeds (for DEV & TEST).

1. Converts raw video-transcription chapters (`第001章.md`..`第002章.md`) of top dramas into clean,
   faithful screenwriter format (stripping camera/watermark prose while 100% preserving every line,
   action beat, pause, VO/OS, and ending hook). Used for:
   - Step 0 Judge Calibration (blind comparison in identical formatting)
   - Few-shot gold demonstrations inside our `hit-short-drama` skill (strictly from `train` split!)
2. Generates realistic 200-500 character `简单创意` briefs for `dev` (6 diverse tracks) and `test` (4 tracks,
   including 2 completely unseen original concepts).
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import re
from pathlib import Path
from typing import Any

import llm_clients as L

TRAIN_ROOT = Path("/home/zhongwenyu/project/ai-director-train")
CORPUS_DIR = TRAIN_ROOT / "corpus"
GOLD_DIR = CORPUS_DIR / "gold_slices"
SEEDS_DIR = CORPUS_DIR / "seeds"

TRANSCRIPT_TO_SCRIPT_PROMPT = """你是一位专业的短剧剧本整理师。下面是一集已上线爆款短剧的「视频逐镜画面还原稿」（包含镜头景别、机位切换、水印描述等冗余信息）。
请将它**100%忠实还原**为干净、标准的「编剧创作态分集剧本格式」，用于剧本教学与盲测。

### 铁律（严禁违背）
1. **绝对忠实原片**：100%保留原片的所有台词原句（修正明显的ASR同音错字即可）、人物名字、先后出场顺序、核心动作细节、情绪反应、道具细节和集尾定格钩子！**不准自己编造新剧情、不准删减原有交锋、不准套用任何改写规则**。
2. **彻底剥离摄影机与水印废话**：删掉“正面近景”“过肩镜头”“切至中景”“右上角果果剧水印”“00:12.600”“配乐转为弦乐”等后期/摄影术语，转化为干净的剧本语言。
3. **统一输出格式**（严格遵守以下 Markdown 结构，直接输出剧本正文，不要任何前言或解释）：

```markdown
# 第 {ep_num} 集　<根据本集核心钩子拟4-8字集名>
**预估时长**：约 {dur_sec} 秒

## {ep_num}-1　<内/外>　<具体场景名>　<日/夜>
**人物**：<本场出场人物>

△ <干净利落的可视化动作/神态/道具细节，不写机位词>
角色名（语气或微动作）：<原片台词>
[VO] 角色名：<原片旁白/内心独白>
[画面文字] <原片关键花字/手机屏幕信息，非水印，没有就不写>
...
【本集完】
```

### 原片视频画面还原稿
剧名：《{title}》（赛道：{genre}，本集真实时长约 {dur_sec} 秒）

{raw_md}
"""

DISTILL_IDEA_PROMPT = """你是一位短剧策划主编。请根据下面某部短剧的前2集画面还原稿，反向提炼出一份**模拟人类编剧/老板口述的「简单创意（250～450字）」**，作为下游“从简单创意生成全剧大纲与剧本”的测试输入。

### 严格要求
1. 字数严格控制在 **250～450 个汉字**之间（纯正文一段或两三小段，不要列大纲表！）。
2. 内容只包含：**题材赛道氛围、男女主/核心人物的身份与性格反差、开局核心处境与信息差/金手指、主要矛盾对手与全剧核心爽感方向**。
3. **严禁泄漏逐集分集细纲或具体第几集发生什么**（不能写“第一集……第二集……”，要像人类立项时给的一段故事创意梗概）。
4. 直接输出这段 250～450 字的创意文本，不要标题、不要解释。

### 参考前2集资料
剧名：《{title}》（题材：{genre}）
{raw_excerpt}
"""


def load_manifest() -> dict[str, Any]:
    return json.loads((CORPUS_DIR / "manifest.json").read_text(encoding="utf-8"))


def convert_one_episode(drama: dict[str, Any], ep_no: int, prefix: str) -> Path:
    out_p = GOLD_DIR / f"{prefix}_{drama['id']}_ep{ep_no:03d}.md"
    if out_p.is_file() and out_p.stat().st_size > 400:
        return out_p
    md_path = Path(drama["novel_dir"]) / f"第{ep_no:03d}章.md"
    raw_md = md_path.read_text(encoding="utf-8")
    dur = int(round(drama.get("median_duration_sec") or 110))
    prompt = TRANSCRIPT_TO_SCRIPT_PROMPT.format(
        ep_num=ep_no,
        dur_sec=dur,
        title=drama["title"],
        genre=drama["genre"],
        raw_md=raw_md[:18000],
    )
    L.call_agy(
        prompt,
        timeout=300,
        validator=lambda t: f"# 第 {ep_no} 集" in t and "【本集完】" in t and "镜头切至" not in t,
        out_path=out_p,
    )
    return out_p


def build_gold_slices(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    dramas = manifest["dramas"]

    # Pick diverse, authentic, high-attraction TRAIN dramas across genres (1-3 min real duration!)
    train_targets = [
        ("001_装穷提亲，娶到全家嫌弃的她", [1, 2]),         # 隐富信息差 + 偏心家庭 + 替嫁温情反打 (158s)
        ("039_被赶下车后我收回一切", [1, 2]),               # 都市清醒抽底牌爽剧 (133s)
        ("070_前妻追悔前夫已登云巅", [1, 2]),               # 都市隐退大佬追夫火葬场 (122s)
        ("068_婆婆装瘫七年，我高调离婚！", [1]),            # 家庭欺骗揭穿高调反击 (155s)
        ("040_救下奶萌小龙崽整片大海听我差遣", [1]),         # 年代赶海 + 萌宠奇遇致富 (106s)
        ("030_持斧赶山救母，我靠宝莲灯肉满仓", [1]),         # 年代乡村 + 宝物护母打脸极品亲戚 (114s)
        ("092_一身腱子肉，乱世做谋臣", [1, 2]),             # 古装反差人设（莽夫外形顶级谋士）(70s)
        ("042_激活空间，三天后重生1958", [1]),              # 年代重生空间囤货（爆笑活人嘴炮）(85s)
    ]

    jobs = []
    records = []
    with cf.ThreadPoolExecutor(max_workers=3) as ex:
        for key, eps in train_targets:
            # Find matching key if slightly different
            d = dramas.get(key)
            if not d:
                matches = [v for k, v in dramas.items() if k.startswith(key.split("_")[0] + "_")]
                if not matches:
                    continue
                d = matches[0]
            assert d["split"] == "train", f"Gold slice {d['key']} must be in train, got {d['split']}!"
            for ep_no in eps:
                fut = ex.submit(convert_one_episode, d, ep_no, "train")
                jobs.append((d, ep_no, fut))

        for d, ep_no, fut in jobs:
            p = fut.result()
            records.append(
                {
                    "key": d["key"],
                    "id": d["id"],
                    "title": d["title"],
                    "genre": d["genre"],
                    "split": d["split"],
                    "episode": ep_no,
                    "path": str(p),
                }
            )
            print(f"[gold_slice] Ready: {p.name} ({d['title']} ep{ep_no})")

    (GOLD_DIR / "index.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return records


def distill_seed_for_drama(d: dict[str, Any]) -> str:
    nd = Path(d["novel_dir"])
    ep1 = (nd / "第001章.md").read_text(encoding="utf-8")[:6000]
    ep2_p = nd / "第002章.md"
    ep2 = ep2_p.read_text(encoding="utf-8")[:4000] if ep2_p.is_file() else ""
    prompt = DISTILL_IDEA_PROMPT.format(
        title=d["title"],
        genre=d["genre"],
        raw_excerpt=f"【第1集片段】\n{ep1}\n\n【第2集片段】\n{ep2}",
    )
    return L.call_agy(
        prompt,
        timeout=240,
        validator=lambda t: 180 <= len(re.sub(r"\s+", "", t)) <= 560 and "第1集" not in t and "第一集" not in t,
    )


def build_seeds(manifest: dict[str, Any]) -> None:
    SEEDS_DIR.mkdir(parents=True, exist_ok=True)
    dramas = manifest["dramas"]

    # 6 diverse DEV seeds (strictly from dev split!)
    dev_pick_ids = ["066", "049", "097", "067", "098", "112"]
    dev_seeds = []
    for did in dev_pick_ids:
        d = next(v for v in dramas.values() if v["id"] == did)
        assert d["split"] == "dev", f"Expected dev split for {d['key']}, got {d['split']}"
        seed_file = SEEDS_DIR / f"dev_{did}.json"
        if seed_file.is_file():
            item = json.loads(seed_file.read_text(encoding="utf-8"))
        else:
            brief = distill_seed_for_drama(d)
            item = {
                "seed_id": f"dev_{did}",
                "split": "dev",
                "source_key": d["key"],
                "title_hint": d["title"],
                "genre": d["genre"],
                "idea": brief.strip(),
                "char_count": len(brief.strip()),
            }
            seed_file.write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        dev_seeds.append(item)
        print(f"[seed] DEV {item['seed_id']} ({item['genre']}, {item['char_count']}字): {item['title_hint']}")

    # 4 Holdout TEST seeds: 2 from test split (incl. 085 for head-to-head comparison!) + 2 100% original unseen ideas!
    test_pick_ids = ["085", "048"]
    test_seeds = []
    for tid in test_pick_ids:
        d = next(v for v in dramas.values() if v["id"] == tid)
        assert d["split"] == "test", f"Expected test split for {d['key']}, got {d['split']}"
        seed_file = SEEDS_DIR / f"test_{tid}.json"
        if seed_file.is_file():
            item = json.loads(seed_file.read_text(encoding="utf-8"))
        else:
            brief = distill_seed_for_drama(d)
            item = {
                "seed_id": f"test_{tid}",
                "split": "test",
                "source_key": d["key"],
                "title_hint": d["title"],
                "genre": d["genre"],
                "idea": brief.strip(),
                "char_count": len(brief.strip()),
            }
            seed_file.write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        test_seeds.append(item)
        print(f"[seed] TEST {item['seed_id']} ({item['genre']}, {item['char_count']}字): {item['title_hint']}")

    original_test_ideas = [
        {
            "seed_id": "test_orig_01",
            "split": "test",
            "source_key": None,
            "title_hint": "年夜饭桌上的百亿拆迁款",
            "genre": "都市情感",
            "idea": (
                "林默在海外打拼八年，秘密创立了国内最大的冷链物流集团，今年特意穿着普通工装骑着旧电瓶车回老家过除夕，"
                "想给父母和弟弟一个惊喜，顺便把老宅拆迁补偿升级为市中心整栋商业楼的产权交到家里。没想到刚进家门，"
                "父母和准弟媳一家正摆着八桌团圆宴，唯独把他的位置撤掉，让他去厨房端菜洗碗。准弟媳一家不仅霸占了林默当年出钱盖的婚房，"
                "还拿出一份早就拟好的‘自愿放弃家产及拆迁款声明书’逼林默当场签字按手印，甚至污蔑他在外坐牢混不下去回来啃老。"
                "只有从小被寄养在林家、同样受尽白眼的表妹苏晴偷偷塞给他一碗热饺子。林默看着满屋势利亲戚和嚣张的准弟媳上司（恰恰是自己集团的区域采购副总），"
                "笑着签下放弃老宅破瓦房的字据，反手开启对全家的彻底清算与断亲。"
            ),
        },
        {
            "seed_id": "test_orig_02",
            "split": "test",
            "source_key": None,
            "title_hint": "听懂万物心声后，我在八零供销社躺赢",
            "genre": "年代乡村",
            "idea": (
                "1983年国营红星供销社改制前夕，老实巴交的售货员沈秋月前世被偏心养母和白莲花继妹联手陷害‘贪污公款与投机倒把’，"
                "不仅丢了铁饭碗，还被迫替继妹下嫁给传闻中命硬克妻、双腿残废的退伍侦察营长陆峥，最终含恨病逝。一朝重生回盘点查账当天，"
                "沈秋月意外觉醒‘旧物心声’能力——账本、秤砣、古董瓷瓶甚至藏钱的墙砖都会在她耳边喋喋不休地告密谁偷了钱、哪里藏着真宝贝！"
                "面对养母当众搜身逼她顶罪、继妹抢她供销社编制和城里未婚夫，沈秋月当场揪出藏在继妹棉袄夹层里的赃款与假票据反将一军，"
                "主动抓起与陆峥的婚书搬出养母家。她一边靠听万物心声捡漏古玩、抓特务立功、把亏损供销社盘活成万元户百货大楼，"
                "一边治好表面冷硬实则护短宠妻的陆峥，让等着看她守活寡的极品一家彻底傻眼。"
            ),
        },
    ]
    for item in original_test_ideas:
        item["char_count"] = len(item["idea"])
        (SEEDS_DIR / f"{item['seed_id']}.json").write_text(
            json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        test_seeds.append(item)

    (SEEDS_DIR / "dev_seeds.json").write_text(
        json.dumps(dev_seeds, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (SEEDS_DIR / "test_seeds.json").write_text(
        json.dumps(test_seeds, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"[seed] Saved {len(dev_seeds)} dev seeds and {len(test_seeds)} test seeds.")


if __name__ == "__main__":
    m = load_manifest()
    build_gold_slices(m)
    build_seeds(m)
