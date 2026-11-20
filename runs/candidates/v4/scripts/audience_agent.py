#!/usr/bin/env python3
"""
Zero-Context Mobile Short-Drama Audience Agent (`audience_agent.py`).

Replaces abstract literary rubric scoring with realistic 20-second mobile viewer
swipe-away simulation (`BINGE_NEXT` vs `SWIPE_AWAY`), running in a physically isolated
empty temporary directory with ZERO access to creative briefs, outlines, or character bibles.

Targets both:
  1. Single-script sequential gate (`audit_viewer_retention`) for `write_drama.py`
  2. Swap-debiased blind pairwise comparison (`compare_blind_pair`) for calibration & arena evaluation
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

RE_EP_HEADER = re.compile(r"^#\s*第\s*(\d+)\s*集[^\n]*$", re.M)

AGY_BIN = (
    os.environ.get("TRAIN_AGY_BIN")
    or ("/home/zhongwenyu/.config/paseo/antigravity-bin/agy"
        if Path("/home/zhongwenyu/.config/paseo/antigravity-bin/agy").is_file()
        else None)
    or shutil.which("agy")
    or "agy"
)
CODEX_BIN = (
    os.environ.get("TRAIN_CODEX_BIN")
    or shutil.which("codex")
    or "/home/zhongwenyu/.local/bin/codex"
)

SINGLE_AUDIT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "episode": {"type": "integer"},
        "understood_plot_one_line": {
            "type": "string",
            "description": "普通小白观众裸看完本集后一句话复述看懂了什么（35字内）",
        },
        "scene_barrage": {
            "type": "array",
            "description": "按每场戏（约20-30秒）模拟真实手机观众的即时弹幕与留存动作",
            "items": {
                "type": "object",
                "properties": {
                    "scene_id": {"type": "string"},
                    "barrage": {"type": "string", "description": "大白话即时弹幕（夸爽点或骂槽点）"},
                    "action": {"type": "string", "enum": ["KEEP_WATCHING", "FROWN_DOUBT", "SWIPE_AWAY"]},
                },
                "required": ["scene_id", "barrage", "action"],
                "additionalProperties": False,
            },
        },
        "fatal_dropoffs": {
            "type": "array",
            "description": "导致普通观众出戏吐槽或划走弃剧的实质硬伤（没有则填空数组 []，严禁没病硬挑！）",
            "items": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": [
                            "identity_action_dissonance",
                            "contrived_coincidence_crisis",
                            "mainline_detour_npc_filler",
                            "ally_suspicion_frustration",
                            "unexplained_leap_or_ad_cringe",
                            "wordy_essay_dialogue",
                        ],
                    },
                    "quote": {"type": "string"},
                    "viewer_complaint": {"type": "string", "description": "普通观众看到这里的大白话吐槽"},
                    "root_fix": {"type": "string", "description": "如何从人设/事件源头根治，禁止打台词补丁"},
                },
                "required": ["category", "quote", "viewer_complaint", "root_fix"],
                "additionalProperties": False,
            },
        },
        "dopamine_flow": {
            "type": "string",
            "enum": ["CRISP_ESCALATING", "FLAT_DRAGGING", "FRUSTRATING_DETOUR"],
        },
        "immersion_score": {"type": "number", "minimum": 0, "maximum": 10},
        "verdict": {"type": "string", "enum": ["BINGE_NEXT", "SWIPE_AWAY"]},
    },
    "required": [
        "episode",
        "understood_plot_one_line",
        "scene_barrage",
        "fatal_dropoffs",
        "dopamine_flow",
        "immersion_score",
        "verdict",
    ],
    "additionalProperties": False,
}

PAIRWISE_AUDIENCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "script_a_gut_reaction": {
            "type": "string",
            "description": "刷手机普通观众看剧本A的真实体感：哪里代入快/爽，哪里出戏/啰嗦/憋屈（120字内）",
        },
        "script_b_gut_reaction": {
            "type": "string",
            "description": "刷手机普通观众看剧本B的真实体感：哪里代入快/爽，哪里出戏/啰嗦/憋屈（120字内）",
        },
        "script_a_fatal_flaws": {
            "type": "array",
            "items": {"type": "string"},
            "description": "剧本A中违背生活常识、身份违和、支线路人注水、盟友猜忌内耗或说明书台词的槽点清单",
        },
        "script_b_fatal_flaws": {
            "type": "array",
            "items": {"type": "string"},
            "description": "剧本B中违背生活常识、身份违和、支线路人注水、盟友猜忌内耗或说明书台词的槽点清单",
        },
        "preferred": {
            "type": "string",
            "enum": ["A", "B"],
            "description": "作为刷手机的小白观众，哪一部更能让你一秒代入、爽快连刷不划走？（必须二选一）",
        },
        "decisive_reason": {
            "type": "string",
            "description": "决定胜负的最核心观众体验差异（80字内，聚焦常识自洽度、主线爽感连贯度与活人台词）",
        },
    },
    "required": [
        "script_a_gut_reaction",
        "script_b_gut_reaction",
        "script_a_fatal_flaws",
        "script_b_fatal_flaws",
        "preferred",
        "decisive_reason",
    ],
    "additionalProperties": False,
}

SINGLE_AUDIT_PROMPT = """你现在不是文学评委，也不是知道后台设定的编剧。
你只是一个下班刷手机、耐心极低（20秒不抓人或一出戏就立刻划走）的**普通短剧小白观众**。
你手里没有任何故事大纲或人物小传，只能按顺序看到前 {ep_num} 集的剧本画面与台词。

请重点用以下**六大真实观众出戏与弃剧雷达**审视**第 {ep_num} 集**：

1. **身份—行为违和（`identity_action_dissonance`）**：
   - 角色的社会身份、学历地位与他的谋生方式/行为是否符合中国人的现实生活常识？
   - 典型出戏案例：给主角安一个 985/重点大学在校生（如重大、清北、复旦大三学生）、海归博士、大医院精英身份，却毫无令人信服的家庭变故/休学抵债理由，让他不上课不走本专业，像底层学徒一样去街边小馆颠勺当厨子、修破烂、蹬缝纫机！（注意：哪怕前世是总厨/匠人，如果今生设定成重点大学在校生却无故去当街边厨工，普通观众照样会出戏吐槽：“一个985大学生干嘛不去读书拿文凭，非跑去街边当厨子？”）
2. **硬凑巧合危机（`contrived_coincidence_crisis`）**：
   - 店面/家庭危机是不是为了逼主角入局而硬凑出来的假巧合？
   - 典型出戏案例：“老板五天前刚扭伤手腕 → 60块一天的临时工突然当场勒索九千块预支 → 正常营业的老店五天就差一万多房租要贴纸倒闭”。账目和生活常识一眼假！
3. **主线断流、支线路人注水（`mainline_detour_npc_filler`）**：
   - 第 1 集明明立下了对核心仇人（如忘恩前任、黑心亲戚、抢功对手）的强烈怒火与赌约，结果第 2 集核心仇人完全消失，主角跑去跟一个**毫无后续的一次性路人甲恶霸/临时工**扯皮一整集！主线仇恨悬空，爽感彻底断流！
4. **盟友猜忌内耗添堵（`ally_suspicion_frustration`）**：
   - 主角明明刚出手救了盟友/女主的急，结果集尾盟友不仅不干脆合作，反而冷脸质问主角“你是不是跟前任赌气、拿我家救命钱当幌子？”——把本该同仇敌忾打反派的爽剧，写成内部猜忌审讯的憋屈戏！
5. **未铺垫跳变或尴尬假广告（`unexplained_leap_or_ad_cringe`）**：
   - 突然冒出前文没交代过的关系/账本/设定，或者喝一口汤突然唱“咪嘛咪”练声、背诵产品说明书式电视购物台词。
6. **说明文式长句台词（`wordy_essay_dialogue`）**：
   - 活人吵架交锋是一句顶一句的短句（5～22字）；如果角色动辄一口气念四五十个字的背景总结、财务算账或书面排比句，直接判出戏！

### 判决标准
- 只要第 {ep_num} 集踩中上述任意 1 条实质硬伤，或者整集都在平淡算账解释、没有干脆利落的情绪推进与筹码兑现，`verdict` **必须判 `SWIPE_AWAY`**！
- 只有当小白观众零门槛秒懂、身份动机天经地义、主线火力集中不跑偏、台词短促解气、集尾让人迫不及待想看下一集反杀时，才判 `BINGE_NEXT`。
"""

PAIRWISE_AUDIENCE_PROMPT = """你是一个只看真实观剧体验、对“AI假爽八股”极度反感的**普通手机短剧观众**。
下面给你看两部同题材短剧的开篇剧本（**剧本 A** 与 **剧本 B**，均约 5～6 分钟体量）。只问一个问题：**哪一部像真人演的扎心好剧，让你代入信服、一口气刷下去；哪一部充满“AI编剧凑巧合、念商务法务说明书、开万能外挂速通”的塑料感？**

### 普通观众评判铁律（优先级从高到低！）
0. **【一票否决】真生活痛感与活人感 > 塑料AI开挂速通（最关键！）**：
   - **千万不要被“表面反击次数多、报应来得快”骗了！** 如果一部剧为了在两三集里塞满反击，让角色满嘴念“法务核档、银行监管户、不动产网签、财务专用章平账、连报四五个金额数字”等**商务法务说明书台词**，或者靠**强行巧合、现金/证据刚好送到手上、反派降智自爆、一个电话万能秒办一切**来硬推爽点——普通观众只会觉得“假透了、像在听合同汇报”，立刻划走！
   - 真正的爆款好剧哪怕前两集在蓄压拉扯、悄悄抽走底牌，只要每一句都是**扎心的大白话短句**（如“我回自己家也要交房费？”“谁收的钱谁去修”）、人物反应符合真实人性与家庭伦理，观众就会死死盯着屏幕等反派天塌！
1. **身份—行为常识自洽 vs 人设割裂**：
   - 好剧：人物出身与干的活 100% 符合生活常识，痛点一秒听懂。
   - 烂剧：重点/985大学在校生毫无理由跑去街边当厨子/学徒打杂，或者靠长篇台词硬补背景。
2. **主线咬死核心仇人 vs 支线路人注水/盟友内耗**：
   - 好剧：始终围绕核心仇人的压迫蓄力或反制；友军拎得清、痛快配合。
   - 烂剧：核心仇人消失，跑去跟一次性路人临时工扯皮一整集，或救完场反遭盟友冷脸审问“你是不是拿我家钱赌气”。

请严格按 JSON Schema 输出对比结果，在 `preferred` 中明确选出更像真实爆款、更让人信服上头的 `A` 或 `B`！
"""


def _extract_json(text: str) -> Any:
    s = text.strip()
    m = re.match(r"^```[a-zA-Z0-9_-]*\s*\n(.*)\n```\s*$", s, re.S)
    if m:
        s = m.group(1).strip()
    dec = json.JSONDecoder()
    for i, ch in enumerate(s):
        if ch in "{[":
            try:
                obj, _ = dec.raw_decode(s[i:])
                return obj
            except ValueError:
                continue
    raise ValueError(f"No JSON found in output: {text[:400]!r}")


def call_isolated_llm(
    prompt: str,
    schema: dict[str, Any],
    *,
    backend: str = "codex",
    timeout: int = 420,
    retries: int = 3,
) -> dict[str, Any]:
    """Run LLM in an empty temporary directory so ZERO project files can ever be read."""
    last_err = ""
    for attempt in range(1, retries + 2):
        with tempfile.TemporaryDirectory(prefix="isolated-audience-") as empty_dir:
            schema_path = Path(empty_dir) / "schema.json"
            schema_path.write_text(json.dumps(schema, ensure_ascii=False), encoding="utf-8")
            if backend == "codex":
                out_path = Path(empty_dir) / "out.json"
                cmd = [
                    CODEX_BIN,
                    "exec",
                    "--skip-git-repo-check",
                    "--sandbox", "read-only",
                    "-C", empty_dir,
                    "-m", os.environ.get("AUDIENCE_CODEX_MODEL", "gpt-6.1-sol"),
                    "-c", f'model_reasoning_effort="{os.environ.get("AUDIENCE_CODEX_EFFORT", "medium")}"',
                    "--output-schema", str(schema_path),
                    "-o", str(out_path),
                    "-",
                ]
                try:
                    proc = subprocess.run(
                        cmd, cwd=empty_dir, input=prompt, capture_output=True, text=True, timeout=timeout
                    )
                except subprocess.TimeoutExpired:
                    last_err = f"codex timeout {timeout}s"
                    time.sleep(2 * attempt)
                    continue
                if proc.returncode != 0 or not out_path.is_file():
                    last_err = f"codex exit {proc.returncode}: {(proc.stderr or proc.stdout)[-500:]}"
                    time.sleep(2 * attempt)
                    continue
                try:
                    return _extract_json(out_path.read_text(encoding="utf-8"))
                except Exception as exc:
                    last_err = str(exc)
                    continue
            else:
                cmd = [
                    AGY_BIN,
                    "--model", os.environ.get("AUDIENCE_AGY_MODEL", "gemini-4-carbon-medium"),
                    "--effort", os.environ.get("AUDIENCE_AGY_EFFORT", "medium"),
                    "--disable-slash-commands",
                    "--output-format", "json",
                    "--input-format", "text",
                    "--json-schema", str(schema_path),
                ]
                try:
                    proc = subprocess.run(
                        cmd, cwd=empty_dir, input=prompt, capture_output=True, text=True, timeout=timeout
                    )
                except subprocess.TimeoutExpired:
                    last_err = f"agy timeout {timeout}s"
                    time.sleep(2 * attempt)
                    continue
                if proc.returncode != 0:
                    last_err = f"agy exit {proc.returncode}: {(proc.stderr or proc.stdout)[-500:]}"
                    time.sleep(2 * attempt)
                    continue
                try:
                    env = json.loads(proc.stdout)
                    raw = env.get("response", proc.stdout) if isinstance(env, dict) else proc.stdout
                    return raw if isinstance(raw, dict) else _extract_json(str(raw))
                except Exception as exc:
                    last_err = str(exc)
                    continue
    raise RuntimeError(f"Audience LLM ({backend}) failed: {last_err}")


def split_episodes(script_md: str) -> dict[int, str]:
    matches = list(RE_EP_HEADER.finditer(script_md))
    out: dict[int, str] = {}
    for i, m in enumerate(matches):
        ep_no = int(m.group(1))
        end = matches[i + 1].start() if i + 1 < len(matches) else len(script_md)
        out[ep_no] = script_md[m.start():end].strip()
    return out


def audit_viewer_retention(
    script_md: str,
    eval_eps: list[int] | None = None,
    *,
    backend: str = "codex",
) -> dict[str, Any]:
    eps_map = split_episodes(script_md)
    if not eps_map:
        raise ValueError("No `# 第N集` headers found in script.")
    all_sorted = sorted(eps_map.keys())
    targets = sorted(eval_eps) if eval_eps else all_sorted

    results = []
    blocked = []
    for k in targets:
        prefix_eps = [e for e in all_sorted if e <= k]
        visible_text = "\n\n\n".join(eps_map[e] for e in prefix_eps)
        prompt = (
            SINGLE_AUDIT_PROMPT.format(ep_num=k)
            + f"\n\n# 仅有的已播剧集正文（第 1～{k} 集）\n\n"
            + visible_text
        )
        rep = call_isolated_llm(prompt, SINGLE_AUDIT_SCHEMA, backend=backend)
        rep["episode"] = k
        if rep["fatal_dropoffs"] or rep["dopamine_flow"] != "CRISP_ESCALATING" or rep["immersion_score"] < 7.8:
            rep["verdict"] = "SWIPE_AWAY"
        if rep["verdict"] == "SWIPE_AWAY":
            blocked.append(k)
        results.append(rep)

    return {
        "ok": len(blocked) == 0,
        "verdict": "BINGE_NEXT" if len(blocked) == 0 else "SWIPE_AWAY",
        "blocked_episodes": blocked,
        "episodes": results,
    }


def compare_blind_pair(
    label_1: str,
    script_1: str,
    label_2: str,
    script_2: str,
    *,
    backend: str = "codex",
) -> dict[str, Any]:
    """Run BOTH (1 as A, 2 as B) AND (2 as A, 1 as B) independently to eliminate position bias."""
    p_fwd = (
        PAIRWISE_AUDIENCE_PROMPT
        + "\n\n==================== 剧本 A ====================\n\n"
        + script_1.strip()
        + "\n\n==================== 剧本 B ====================\n\n"
        + script_2.strip()
    )
    p_rev = (
        PAIRWISE_AUDIENCE_PROMPT
        + "\n\n==================== 剧本 A ====================\n\n"
        + script_2.strip()
        + "\n\n==================== 剧本 B ====================\n\n"
        + script_1.strip()
    )
    with cf.ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(call_isolated_llm, p_fwd, PAIRWISE_AUDIENCE_SCHEMA, backend=backend)
        f2 = pool.submit(call_isolated_llm, p_rev, PAIRWISE_AUDIENCE_SCHEMA, backend=backend)
        r_fwd = f1.result()
        r_rev = f2.result()

    win_fwd = label_1 if r_fwd["preferred"] == "A" else label_2
    win_rev = label_2 if r_rev["preferred"] == "A" else label_1
    consistent = win_fwd == win_rev
    return {
        "winner": win_fwd if consistent else "TIE_INCONSISTENT",
        "swap_consistent": consistent,
        "forward_pick": win_fwd,
        "reverse_pick": win_rev,
        "forward_detail": r_fwd,
        "reverse_detail": r_rev,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("script_md", type=Path)
    ap.add_argument("--episodes", default="")
    ap.add_argument("--backend", default=os.environ.get("AUDIENCE_BACKEND", "codex"), choices=("codex", "agy"))
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    eval_eps = None
    if args.episodes.strip():
        eval_eps = []
        for part in args.episodes.split(","):
            if "-" in part:
                a, b = part.split("-", 1)
                eval_eps.extend(range(int(a), int(b) + 1))
            else:
                eval_eps.append(int(part))

    rep = audit_viewer_retention(
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
