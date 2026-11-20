#!/usr/bin/env python3
"""
Cold Common-Sense & Causal Logic Prosecutor (`logic_prosecutor.py`) — Gate 1 of `hit-short-drama v5`.

Why `audience_agent.py` alone was not enough:
`audience_agent.py` simulates an emotional mobile viewer who can get swept up by fast,
earthy face-slaps (`撕方子`、`晒48张汇款单`、`五五分账`) while overlooking catastrophic
underlying causal & physical absurdities unless stripped to pure screen truth and
cross-examined by a ruthless logic prosecutor!

`logic_prosecutor.py`:
  1. Runs `strip_to_screen.py` FIRST so authorial `**人物**` lists are gone and `[VO]` is
     explicitly tagged as inaudible to other characters on screen.
  2. Runs in an isolated empty temp directory (`codex` or `agy`) with ZERO access to
     outlines or premise files.
  3. Prosecutes 6 concrete causal/human-logic felonies (`CONVICT_REWRITE` vs `ACQUIT_PASS`),
     while explicitly respecting declared supernatural/fantasy hooks (e.g. hearing antiques
     speak) and grounded family/workplace conflicts.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import strip_to_screen as STS  # noqa: E402
import audience_agent as AA  # noqa: E402

PROSECUTOR_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "episode": {"type": "integer"},
        "reconstructed_timeline_and_motives": {
            "type": "string",
            "description": "仅凭屏幕实况还原：前世/过往发生了什么、今生/当下分叉点谁先改变了行为、各方图什么（60字内）",
        },
        "convictions": {
            "type": "array",
            "description": "确凿违反现实因果/人性自利/屏幕信息完备性的硬伤清单；若因果严密自洽则必须填空数组 []（严禁吹毛求疵无罪强判！）",
            "items": {
                "type": "object",
                "properties": {
                    "article": {
                        "type": "string",
                        "enum": [
                            "timeline_branch_paradox",
                            "telepathy_or_unintroduced_role",
                            "irrational_charity_or_self_sabotage",
                            "magic_pocket_prop_or_instant_bureaucracy",
                            "crammed_telegram_outline",
                            "mute_passive_protagonist",
                        ],
                    },
                    "quote": {"type": "string"},
                    "indictment": {
                        "type": "string",
                        "description": "一针见血指出为什么这在现实逻辑/人情世故里根本说不通",
                    },
                    "structural_remedy": {
                        "type": "string",
                        "description": "从剧本结构、人物动机、筹码交换或场次删减源头给出的根治方案（禁止靠加长台词打补丁）",
                    },
                },
                "required": ["article", "quote", "indictment", "structural_remedy"],
                "additionalProperties": False,
            },
        },
        "logic_score": {"type": "number", "minimum": 0, "maximum": 10},
        "verdict": {"type": "string", "enum": ["ACQUIT_PASS", "CONVICT_REWRITE"]},
    },
    "required": [
        "episode",
        "reconstructed_timeline_and_motives",
        "convictions",
        "logic_score",
        "verdict",
    ],
    "additionalProperties": False,
}

PROSECUTOR_PROMPT = """你是一位冷酷、毒辣、只认**现实因果律、人性理性自利与屏幕可见事实**的「短剧剧本逻辑检察官」。
你手里没有任何大纲或设定表，看到的只有经过去作者化处理的《屏幕裸看实况版》（已剥离作者偷写的 `**人物**` 名单，且已标明哪些 `[内心独白VO/OS]` 在场旁人根本听不见）。

请对 **第 {ep_num} 集** 进行逐条因果与常识庭审（注意：若作品本身明确是听见万物心声/系统等奇幻设定，奇幻金手指本身不算逻辑漏洞；我们要抓的是**人物动机、时间线分叉、信息传递、物理常识与剧情塞爆**六大硬伤！）：

### 六大必判死刑的剧本逻辑重罪

1. **重生/前世今生分叉点悖论（`timeline_branch_paradox`）**：
   - 拷问：如果是重生剧，**前世主角为什么会留下来被吸血多年（比如从2005年一直替反派干到2015年才被踢出局）？**
   - **典型死罪**：如果2005年开场，重生主角还没做任何反常举动，反派一家就已经当众嫌弃他是臭伙夫、主动退婚撵他走——那前世他怎么可能留下来替反派干十年？！这叫时间线自相矛盾！
   - **唯一合法的因果结构**：要么（A）当年在这个节点，反派表面是在**笑脸画大饼/哄骗稳住主角**（如“婚事缓两年，先把秘方交出来入股，以后都是咱俩的”），前世主角信了画饼交出底牌才被榨干十年，而**今生是重生主角看穿伪善、主动掀桌拒交**才导致反派气急败坏撕破脸；要么（B）这一天本就是前世命运转折逼迫日（如1993年亲爹逼长子让出高考状元通知书，前世他屈服让了所以苦一辈子，今生他当场说“不交”断亲改变命运）。

2. **读心术跨空知情 & 关键熟人整集无称谓（`telepathy_or_unintroduced_role`）**：
   - `[内心独白VO/OS]` 只有观众能听见，剧里其他角色**绝对听不见**！如果主角走进另一家店一句话没说（只有内心OS），对方却像开了天眼一样自动知道他刚跟前东家闹翻、立刻写合同签约，判读心术死罪！
   - 如果一个推动核心冲突的重要角色（如女方父亲、店老板、奸夫）在整集里多次开口吵架，却直到本集结束都没人叫过他一声“爸/叔/X老板/名字”（见实况版末尾预警），导致裸看屏幕的观众根本不知道这男的是谁，判人物关系缺失罪！（注：路人住客、收银员或本场已通过“叔/爸/妈/姐”等称谓交代清楚亲属关系的角色不在此列）。

3. **违背理性自利的无条件慈善或无底牌自残（`irrational_charity_or_self_sabotage`）**：
   - **无条件送股份慈善**：哪有正常老板在主角刚进门、连一句合作方案或对赌承诺都没开口说的情况下，当场白送自家店铺 **50%（五五分账）** 股份的？！真正的合作必须有**双向筹码或对赌军令状**（如盟友正急招大厨救命，主角主动开口立下“明晚大席我掌勺拿下才五五分，砸了分文不取抵油钱”）。
   - **反派无底牌自残**：如果店里明天就有大席/急单，反派除非明确自以为留了后手（如“偷瞄四年自以为早把方子记全了”或“已挖来新大厨”），否则绝不会白痴到主动把唯一能做菜的人轰走！（若是主角主动辞职反将一军，反派慌神或嘴硬自大则完全合理）。
   - **权限失真狂言**：街边餐饮同行或普通公司主管张口就说“明早起断你全城一滴成品牛油”，把普通地头蛇写成只手遮天的垄断神仙，判失真！（施压只能针对双方共用的某个具体供货商或某单具体客户）。

4. **哆啦A梦围裙道具 & 20秒瞬移公章（`magic_pocket_prop_or_instant_bureaucracy`）**：
   - 正在后厨端火锅熬油的厨子，怎么可能随身在油腻围裙兜里揣着一个装满 **48张邮政汇款存根的铁盒** 当场倒出来？！（要晒账本/存根，只能是在自己住处收拾行李时，或账房抽屉里原本就锁着）。
   - 同一场戏里主角刚进对门院子两分钟，反派就拿着“客户刚改签盖好章的十二桌红纸定单”瞬移堵门——大晚上客户厂长是蹲在门口秒签字吗？！

5. **把2分钟短剧塞成电报提纲（`crammed_telegram_outline`）**：
   - 真实高留存短剧一集（90～130秒）只聚焦 **1～2个主场景、2～3个递进戏剧节拍**，把人物虚伪拉扯和翻脸反应演透。如果一集115秒里硬塞进 **6～9个大事件**（退婚+撕方+掏铁盒晒单+辞工+过街+无言签五五分账+断全城油+抢走十二桌席+半夜骑三轮去屠宰场），每个人说话都像在念大纲提纲，直接判重罪！

6. **哑巴工具人主角（`mute_passive_protagonist`）**：
   - 在结盟、立契或正面交锋的关键场次里，主角竟然全程不开口谈条件（或整场只有1句口号），全靠女配/反派自说自话把流程走完，判死罪！

### 庭审铁律
- **有罪必究**：只要第 {ep_num} 集确凿犯下上述任意 1 条逻辑重罪，`verdict` **必须判 `CONVICT_REWRITE`**，并在 `convictions` 中逐条给出源头重构方案！
- **无罪铁律（严禁冤假错案）**：如果本集时间线分叉清晰合理（如亲爹逼交录取通知书主角当场拒交、修车一年要工钱被赖账拿破烂辞工、回家住民宿被弟媳收房费、分手后默默取消87项代付）、人物关系通过自然称呼一听就懂、每集只讲透一两个扎实冲突，则 `convictions` **必须返回空数组 `[]`**，`verdict` 判 `ACQUIT_PASS`！
"""


def prosecute_script_logic(
    script_md: str,
    eval_eps: Optional[List[int]] = None,
    *,
    backend: str = "agy",
) -> Dict[str, Any]:
    eps_map = AA.split_episodes(script_md)
    if not eps_map:
        raise ValueError("No `# 第N集` headers found in script.")
    all_sorted = sorted(eps_map.keys())
    targets = sorted(eval_eps) if eval_eps else all_sorted

    full_stripped = STS.strip_script_to_screen(script_md)
    stripped_eps_map = AA.split_episodes(full_stripped["screen_markdown"])

    results: List[Dict[str, Any]] = []
    blocked: List[int] = []
    for k in targets:
        prefix_eps = [e for e in all_sorted if e <= k]
        visible_screen_text = "\n\n\n".join(stripped_eps_map[e] for e in prefix_eps if e in stripped_eps_map)
        prompt = (
            PROSECUTOR_PROMPT.format(ep_num=k)
            + f"\n\n# 观众裸看屏幕实况记录（第 1～{k} 集）\n\n"
            + visible_screen_text
        )
        rep = AA.call_isolated_llm(prompt, PROSECUTOR_SCHEMA, backend=backend)
        rep["episode"] = k
        if rep["convictions"] or rep["logic_score"] < 7.8:
            rep["verdict"] = "CONVICT_REWRITE"
        if rep["verdict"] == "CONVICT_REWRITE":
            blocked.append(k)
        results.append(rep)

    return {
        "ok": len(blocked) == 0,
        "verdict": "ACQUIT_PASS" if len(blocked) == 0 else "CONVICT_REWRITE",
        "blocked_episodes": blocked,
        "screen_diagnostics": full_stripped["episodes"],
        "episodes": results,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("script_md", type=Path)
    ap.add_argument("--episodes", default="")
    ap.add_argument("--backend", default=os.environ.get("PROSECUTOR_BACKEND", "agy"), choices=("agy",))
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    eval_eps: Optional[List[int]] = None
    if args.episodes.strip():
        eval_eps = []
        for part in args.episodes.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                a, b = part.split("-", 1)
                eval_eps.extend(range(int(a), int(b) + 1))
            else:
                eval_eps.append(int(part))

    rep = prosecute_script_logic(
        args.script_md.read_text(encoding="utf-8"),
        eval_eps=eval_eps,
        backend=args.backend,
    )
    txt = json.dumps(rep, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(txt + "\n", encoding="utf-8")
    print(txt)
    sys.exit(0 if rep["ok"] else 2)


if __name__ == "__main__":
    main()
