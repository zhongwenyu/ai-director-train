#!/usr/bin/env python3
"""
Deterministic Screen-View De-Authoring Stripper (`strip_to_screen.py`).

Why this exists:
When an LLM judge reads raw screenplay Markdown, authorial crutches leak information
that an actual video viewer NEVER sees on screen:
  1. `**人物**：叶寻、林双双、楚南、林有才` tells the reader everyone's name & surname
     even if nobody ever addresses `林有才` aloud in the entire episode!
  2. `[VO] 叶寻：...` looks like a line of dialogue on paper, hiding the fact that on
     screen the character is standing COMPLETELY MUTE in front of the other person!
  3. Proper names inside `△` action lines tell the reader who someone is before any
     dialogue or `[画面文字]` introduces them.

This script converts raw screenplay Markdown into an honest Screen-Truth Transcript
(`屏幕实况纯享版`) + per-scene deterministic Audible Speech & Introduction Ledger,
used as the mandatory input to `logic_prosecutor.py` and `audience_agent.py`.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

RE_EP_HEADER = re.compile(r"^#{1,2}\s*第\s*(\d+)\s*集[　\s:：—\-]*(.*)$", re.M)
RE_SCENE_HEADER = re.compile(r"^##\s*(\d+-\d+)\s+(.+)$")
RE_META_CAST = re.compile(r"^\*\*人物\*\*[：:]\s*(.+)$")
RE_META_DUR = re.compile(r"^\*\*预估时长\*\*[：:]\s*(.+)$")
RE_VO_BRACKET = re.compile(r"^\[(?:VO|OS)\]\s*([^：:\n]+?)(?:（[^）\n]*）|\([^)\n]*\))?[：:]\s*(.+)$")
RE_SCREEN_TEXT = re.compile(r"^\[画面文字\]\s*(.+)$")
RE_ACTION = re.compile(r"^△\s*(.+)$")
RE_DIALOGUE = re.compile(
    r"^(?![#△\[\-\*])([^：:\n]{1,24}?)(?:（([^）\n]*)）|\(([^)\n]*)\))?[：:]\s*(.+)$"
)

GENERIC_ROLE_WORDS = (
    "父", "母", "爸", "妈", "叔", "婶", "爷", "奶", "哥", "姐", "弟", "妹",
    "群演", "众人", "路人", "住客", "观众", "工友", "食客", "店员", "服务员",
    "收银", "老板", "大爷", "大妈", "保安", "护士", "医生", "警察", "检查员",
    "系统", "电子音", "收款机", "画外音", "电话", "闺蜜", "同学", "伙计",
    "客服", "助理", "秘书", "经理", "律师", "司机", "管家", "保镖", "主持", "司仪", "职员", "宾客", "亲戚",
)
KINSHIP_OR_TITLE_TOKENS = (
    "爸", "爹", "妈", "娘", "叔", "婶", "伯", "姨", "舅", "爷", "奶",
    "哥", "姐", "弟", "妹", "老公", "老婆", "媳妇", "女婿", "未婚妻", "未婚夫",
    "总", "厂长", "科长", "主任", "院长", "老板", "掌柜", "师傅", "医生", "大夫",
)


def is_generic_role_label(name: str) -> bool:
    clean = re.sub(r"（.*?）|\(.*?\)", "", name).strip()
    if any(w in clean for w in GENERIC_ROLE_WORDS):
        return True
    if clean.startswith(("老年", "少年", "幼年", "童年", "青年", "中年")):
        return True
    return False


def base_char_name(raw_name: str) -> str:
    s = re.sub(r"（.*?）|\(.*?\)", "", raw_name).strip()
    s = re.sub(r"^(?:老年|少年|幼年|童年|青年|中年)", "", s).strip()
    return s


def check_name_introduced(name: str, corpus_text: str) -> bool:
    """Check whether `name` (or its surname+title / given name) has appeared in audible speech, VO, or screen text."""
    if is_generic_role_label(name):
        return True
    b = base_char_name(name)
    if not b:
        return True
    if b in corpus_text:
        return True
    # Given name (e.g. 双双 for 林双双, 芊芊 for 夏芊芊, 小浩 for 林浩)
    if len(b) >= 3 and b[1:] in corpus_text:
        return True
    if len(b) >= 2 and ("小" + b[-1] in corpus_text or "阿" + b[-1] in corpus_text or b[-1] * 2 in corpus_text):
        return True
    # Surname + explicit personal title/kinship (NOT shop names like 林记/林家!)
    surname = b[0]
    for tk in ("老板", "厂长", "科长", "总", "叔", "婶", "伯", "爷", "奶", "师傅", "姐", "哥", "少"):
        if (surname + tk) in corpus_text:
            return True
    return False


def strip_script_to_screen(script_md: str) -> Dict[str, Any]:
    """Return both the de-authored screen transcript and structured diagnostics."""
    ep_matches = list(RE_EP_HEADER.finditer(script_md))
    if not ep_matches:
        return {
            "screen_markdown": script_md,
            "episodes": [],
        }

    # Global across sequential episodes: track spoken/shown text so far
    revealed_corpus = ""
    known_cast_order: List[str] = []
    alias_map: Dict[str, str] = {}

    def get_unintroduced_tag(name: str) -> str:
        b = base_char_name(name)
        if b not in alias_map:
            idx = len(alias_map) + 1
            alias_map[b] = f"未报姓名角色#{idx}"
        return alias_map[b]

    out_lines: List[str] = []
    ep_diagnostics: List[Dict[str, Any]] = []

    for i, m in enumerate(ep_matches):
        ep_no = int(m.group(1))
        ep_title = m.group(2).strip()
        start = m.end()
        end = ep_matches[i + 1].start() if i + 1 < len(ep_matches) else len(script_md)
        body = script_md[start:end].strip()

        # First pass inside episode to collect cast names mentioned in `**人物**` so we can mask them in `△` if unspoken
        ep_cast_names: List[str] = []
        for raw_ln in body.splitlines():
            mc = RE_META_CAST.match(raw_ln.strip())
            if mc:
                parts = re.split(r"[、，,/\s]+", mc.group(1).strip())
                for p in parts:
                    bn = base_char_name(p)
                    if bn and len(bn) >= 2 and not is_generic_role_label(bn) and bn not in ep_cast_names:
                        ep_cast_names.append(bn)
                        if bn not in known_cast_order:
                            known_cast_order.append(bn)

        out_lines.append(f"# 第{ep_no}集（屏幕裸看实况版）")

        current_scene_id = f"{ep_no}-0"
        current_scene_loc = "开场"
        scene_audible_counts: Dict[str, int] = {}
        scene_vo_counts: Dict[str, int] = {}
        scene_present_chars: Set[str] = set()
        ep_audible_counts: Dict[str, int] = {}
        ep_speakers_seen: List[str] = []
        ep_scenes_diag: List[Dict[str, Any]] = []

        def flush_scene_summary() -> None:
            if not scene_audible_counts and not scene_vo_counts and not scene_present_chars:
                return
            mute_present = [
                c for c in sorted(scene_present_chars)
                if scene_audible_counts.get(c, 0) == 0 and not is_generic_role_label(c)
            ]
            audible_str = (
                "、".join(f"{k}({v}句)" for k, v in scene_audible_counts.items())
                if scene_audible_counts
                else "全场0句有声对白"
            )
            summary_parts = [f"有声开口：{audible_str}"]
            if scene_vo_counts:
                vo_str = "、".join(f"{k}({v}句内心OS，旁人听不见)" for k, v in scene_vo_counts.items())
                summary_parts.append(f"内心独白：{vo_str}")
            if mute_present:
                summary_parts.append(f"在场但0句有声开口：{mute_present}")
            out_lines.append(f"  > 【本场屏幕客观统计 {current_scene_id}】" + " ｜ ".join(summary_parts))
            ep_scenes_diag.append({
                "scene_id": current_scene_id,
                "location": current_scene_loc,
                "audible_counts": dict(scene_audible_counts),
                "vo_counts": dict(scene_vo_counts),
                "mute_present_characters": mute_present,
            })

        for raw_ln in body.splitlines():
            ln = raw_ln.strip()
            if not ln:
                continue
            if RE_META_DUR.match(ln):
                continue
            mc = RE_META_CAST.match(ln)
            if mc:
                # Strip `**人物**` authorial list completely from screen transcript,
                # while tracking who is physically listed in the scene for mute-detection.
                for p in re.split(r"[、，,/\s]+", mc.group(1).strip()):
                    if "闪现" in p or "电话" in p or "画外" in p:
                        continue
                    bn = base_char_name(p)
                    if bn:
                        scene_present_chars.add(bn)
                continue

            ms = RE_SCENE_HEADER.match(ln)
            if ms:
                flush_scene_summary()
                current_scene_id = ms.group(1)
                current_scene_loc = ms.group(2).strip()
                scene_audible_counts = {}
                scene_vo_counts = {}
                scene_present_chars = set()
                out_lines.append(f"\n## 场景 {current_scene_id}　{current_scene_loc}")
                continue

            if ln == "【本集完】":
                flush_scene_summary()
                scene_audible_counts = {}
                scene_vo_counts = {}
                scene_present_chars = set()
                out_lines.append("【本集完】")
                continue

            mst = RE_SCREEN_TEXT.match(ln)
            if mst:
                txt = mst.group(1).strip()
                revealed_corpus += "\n" + txt
                out_lines.append(f"[屏幕字幕] {txt}")
                continue

            mvo = RE_VO_BRACKET.match(ln)
            if mvo:
                spk = base_char_name(mvo.group(1))
                content = mvo.group(2).strip()
                revealed_corpus += "\n" + content
                scene_vo_counts[spk] = scene_vo_counts.get(spk, 0) + 1
                spk_disp = spk if check_name_introduced(spk, revealed_corpus) else f"{get_unintroduced_tag(spk)}（原稿名:{spk}，但屏幕尚未交代其名）"
                out_lines.append(f"[内心独白VO·在场其他人听不见] {spk_disp}：{content}")
                continue

            mdlg = RE_DIALOGUE.match(ln)
            if mdlg:
                raw_spk = mdlg.group(1).strip()
                paren = (mdlg.group(2) or mdlg.group(3) or "").strip()
                content = mdlg.group(4).strip()
                spk = base_char_name(raw_spk)
                is_os = paren.upper() in ("OS", "VO") or "内心" in paren
                revealed_corpus += "\n" + content
                if is_os:
                    scene_vo_counts[spk] = scene_vo_counts.get(spk, 0) + 1
                    spk_disp = spk if check_name_introduced(spk, revealed_corpus) else f"{get_unintroduced_tag(spk)}（原稿名:{spk}）"
                    out_lines.append(f"[内心独白OS·在场其他人听不见] {spk_disp}：{content}")
                else:
                    scene_audible_counts[spk] = scene_audible_counts.get(spk, 0) + 1
                    ep_audible_counts[spk] = ep_audible_counts.get(spk, 0) + 1
                    scene_present_chars.add(spk)
                    if spk not in ep_speakers_seen:
                        ep_speakers_seen.append(spk)
                    spk_disp = spk if check_name_introduced(spk, revealed_corpus) else f"{get_unintroduced_tag(spk)}（原稿名:{spk}，注意观众在台词中尚未听见其姓名/称谓）"
                    paren_str = f"（{paren}）" if paren else ""
                    out_lines.append(f"{spk_disp}{paren_str}：{content}")
                continue

            mact = RE_ACTION.match(ln)
            if mact:
                act_txt = mact.group(1).strip()
                # Visible banners/plaques/certificates in quotes inside action lines ARE readable on screen
                for qm in re.findall(r"[“\"]([^”\"\n]{2,40})[”\"]", act_txt):
                    revealed_corpus += "\n" + qm
                masked_act = act_txt
                for cn in known_cast_order:
                    if cn in masked_act:
                        scene_present_chars.add(cn)
                        if not check_name_introduced(cn, revealed_corpus):
                            masked_act = masked_act.replace(cn, f"[{get_unintroduced_tag(cn)}]")
                out_lines.append(f"△ {masked_act}")
                continue

            out_lines.append(ln)

        # End-of-episode check: which speaking characters STILL have never had their name/kinship introduced?
        unintroduced_speakers = [
            s for s in ep_speakers_seen
            if not is_generic_role_label(s) and not check_name_introduced(s, revealed_corpus)
        ]
        # Also check kinship ambiguity: e.g. someone sharing a surname in raw script whose kinship was never spoken
        kinship_spoken = [tk for tk in KINSHIP_OR_TITLE_TOKENS if tk in revealed_corpus]
        if unintroduced_speakers:
            out_lines.append(
                f"> 【第{ep_no}集未交代身份角色预警】以下开口角色截至本集结束，台词与字幕中从未出现过其姓名或明确称谓：{unintroduced_speakers}"
            )
        out_lines.append("")

        ep_diagnostics.append({
            "episode": ep_no,
            "title": ep_title,
            "audible_counts": ep_audible_counts,
            "unintroduced_speakers": unintroduced_speakers,
            "kinship_or_titles_heard": kinship_spoken,
            "scenes": ep_scenes_diag,
        })

    return {
        "screen_markdown": "\n".join(out_lines).strip() + "\n",
        "episodes": ep_diagnostics,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("script_md", type=Path)
    ap.add_argument("--json-out", type=Path, default=None)
    args = ap.parse_args()

    res = strip_script_to_screen(args.script_md.read_text(encoding="utf-8"))
    print(res["screen_markdown"])
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
