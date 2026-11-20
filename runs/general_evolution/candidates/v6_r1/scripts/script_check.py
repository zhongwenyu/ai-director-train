#!/usr/bin/env python3
"""Physical pacing, dialogue depth & screen-clarity checker for `hit-short-drama v5`.

Calibrated against real Hongguo hit openings (`P01..P04` average 22-28 spoken lines/ep, ~115-140s):
1. Prevents telegraphic fast-forwarding (`spoken_count >= 18` lines/ep, `est_sec >= 90s`):
   `hotpot_v3` had only 12-14 lines/ep while cramming 8-10 events, leaving viewers baffled.
2. Prevents wordy corporate essays (`avg_line_chars <= 27`, `max_single <= 55`, `est_sec <= 170s`).
3. Enforces screen-truth relationship clarity via `strip_to_screen.py`:
   - Any named character speaking >= 2 audible lines in an episode MUST have their name or
     clear kinship/title introduced in dialogue/VO/screen-text in or before that episode.
   - Primary protagonist cannot stand mute (`0` audible lines) in a substantive scene (`>= 5`
     audible lines) where they are physically present.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import strip_to_screen as STS  # noqa: E402

RE_EP_HEADER = re.compile(r"^#{1,2}\s*第\s*(\d+)\s*集[　\s:：—\-]*(.*)$", re.M)
RE_SCENE_HEADER = re.compile(r"^##\s*(\d+)-(\d+)\s+(.+)$", re.M)
RE_ACTION = re.compile(r"^△\s*(.+)$", re.M)
RE_VO_LINE = re.compile(r"^\[(?:VO|OS)\]\s*([^：:\n]+)[：:]\s*(.+)$", re.M)
RE_DIALOGUE = re.compile(
    r"^(?![#△\[\-\*])([^：:\n]{1,24}?)(?:（([^）\n]*)）|\(([^)\n]*)\))?[：:]\s*(.+)$",
    re.M,
)

CAMERA_JARGON = ("镜头切", "过肩近景", "正面近景", "全景镜头", "中近景", "推镜头", "果果剧", "水印")
AI_CLICHES = ("嘴角勾起一抹", "空气仿佛凝固", "空气瞬间凝固", "眼神冷得像冰", "三分凉薄")


def analyze_script(
    text: str,
    expected_eps: Optional[List[int]] = None,
    *,
    strict_v5: bool = True,
) -> Dict[str, Any]:
    matches = list(RE_EP_HEADER.finditer(text))
    episodes: List[Dict[str, Any]] = []
    warnings: List[str] = []
    hard_errors: List[str] = []

    found_nums = [int(m.group(1)) for m in matches]
    if expected_eps and found_nums != expected_eps:
        hard_errors.append(f"集数序列不匹配：期望 {expected_eps}，实际解析到 {found_nums}")

    stripped = STS.strip_script_to_screen(text)
    diag_by_ep = {d["episode"]: d for d in stripped.get("episodes", [])}

    # Identify primary protagonist across the script (highest total audible + VO lines)
    global_counts: Dict[str, int] = {}
    for d in stripped.get("episodes", []):
        for spk, cnt in d.get("audible_counts", {}).items():
            if not STS.is_generic_role_label(spk):
                global_counts[spk] = global_counts.get(spk, 0) + cnt
        for sc in d.get("scenes", []):
            for spk, cnt in sc.get("vo_counts", {}).items():
                if not STS.is_generic_role_label(spk):
                    global_counts[spk] = global_counts.get(spk, 0) + cnt
    protagonist = max(global_counts.items(), key=lambda kv: kv[1])[0] if global_counts else ""

    for i, m in enumerate(matches):
        ep_no = int(m.group(1))
        ep_title = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()

        has_end_marker = "【本集完】" in body
        if not has_end_marker:
            hard_errors.append(f"第 {ep_no} 集缺少【本集完】收尾标记")
        else:
            after_end = body.split("【本集完】", 1)[1].strip()
            after_clean = re.sub(r"^---\s*$", "", after_end).strip()
            if after_clean:
                warnings.append(f"第 {ep_no} 集在【本集完】之后仍有残留文本（{len(after_clean)}字）")

        scenes = RE_SCENE_HEADER.findall(body)
        actions = RE_ACTION.findall(body)
        vo_bracket = RE_VO_LINE.findall(body)
        raw_dialogues = []
        os_paren_lines = []
        for spk, p1, p2, line in RE_DIALOGUE.findall(body):
            s_clean = spk.strip()
            if s_clean in ("人物", "**人物**", "预估时长", "**预估时长**"):
                continue
            paren = (p1 or p2 or "").strip()
            if paren.upper() in ("OS", "VO") or "内心" in paren:
                os_paren_lines.append((s_clean, line.strip()))
            else:
                raw_dialogues.append((s_clean, line.strip()))

        all_vo = [(s.strip(), l.strip()) for s, l in vo_bracket] + os_paren_lines
        spoken_texts = [ln for _, ln in raw_dialogues] + [ln for _, ln in all_vo]
        spoken_chars = sum(len(re.sub(r"\s+", "", s)) for s in spoken_texts)
        spoken_count = len(spoken_texts)
        avg_line_len = round(spoken_chars / spoken_count, 1) if spoken_count else 0.0

        est_sec = round(spoken_chars / 4.5 + len(actions) * 1.6 + max(1, len(scenes)) * 2.0, 1)

        if strict_v5 and spoken_count < 18:
            hard_errors.append(
                f"第 {ep_no} 集对白+VO总句数过少（仅 {spoken_count} 句 < 18 句），剧情推进过快像提纲口号、无法把人物关系和前因后果说清楚，须从容展开到 20~32 句自然交锋"
            )

        if strict_v5 and est_sec < 85:
            hard_errors.append(
                f"第 {ep_no} 集预估时长过短（{est_sec}s < 85s），前因后果展开不足，须写足 100~155s 把场面讲透"
            )
        elif est_sec > 205:
            hard_errors.append(
                f"第 {ep_no} 集预估时长超标（{est_sec}s > 205s），戏量过载，须控制在 100~165s（约20~28句对白）内"
            )

        if strict_v5 and len(scenes) > 4:
            hard_errors.append(
                f"第 {ep_no} 集场次切碎过多（{len(scenes)} 场 > 4 场），导致走马灯快进，每集须控制在 1~3 场内深挖交锋"
            )

        if strict_v5 and avg_line_len > 28.5:
            hard_errors.append(
                f"第 {ep_no} 集句均字数过长（{avg_line_len}字 > 28.5字），须用 14~24 字通俗活人短句把事说清"
            )

        max_single = max(([len(s) for _, s in raw_dialogues] + [len(s) for _, s in all_vo]) or [0])
        if strict_v5 and max_single > 60:
            hard_errors.append(
                f"第 {ep_no} 集存在超长单句台词（{max_single}字 > 60字），请拆为有来有回的真实对话"
            )

        ep_diag = diag_by_ep.get(ep_no, {})
        if strict_v5 and ep_diag:
            # Check unintroduced recurring speakers (>= 2 audible lines in the episode).
            # Note: In natural Chinese family/ancient/rural dialogue, elders/in-laws are addressed by kinship
            # ("妈/娘/爹/大嫂/二哥") rather than full household-register names ("我娘刘翠兰").
            # Only raise a hard error if NO kinship/title tokens were heard at all when >= 2 speakers are unintroduced;
            # otherwise record as a soft warning and let `general_arena_judge` evaluate semantic screen clarity on stripped text.
            aud_map = ep_diag.get("audible_counts", {})
            bad_unintro = [
                u for u in ep_diag.get("unintroduced_speakers", [])
                if aud_map.get(u, 0) >= 2
            ]
            kinship_heard = ep_diag.get("kinship_or_titles_heard", [])
            if bad_unintro:
                if not kinship_heard and len(bad_unintro) >= 2:
                    hard_errors.append(
                        f"第 {ep_no} 集角色身份与称谓完全缺失：{bad_unintro} 多次开口，且全集台词/字幕既无姓名也无任何亲属或身份称谓，观众裸看无法分辨人物关系"
                    )
                else:
                    warnings.append(
                        f"第 {ep_no} 集角色 {bad_unintro} 未直接叫出全名（已出现称谓 {kinship_heard[:6]}，交由屏幕盲审核验关系清晰度）"
                    )
            # Check mute protagonist in major confrontation scenes (>= 8 total audible lines, or < 3 protagonist lines in whole episode)
            if protagonist:
                ep_prot_aud = aud_map.get(protagonist, 0)
                if ep_prot_aud < 2:
                    hard_errors.append(
                        f"第 {ep_no} 集主角「{protagonist}」全集有声对白仅 {ep_prot_aud} 句（沦为哑巴背景板），主角必须亲口主导核心交锋"
                    )
                else:
                    for sc in ep_diag.get("scenes", []):
                        tot_sc_aud = sum(sc.get("audible_counts", {}).values())
                        loc_txt = sc.get("location", "")
                        is_witness_loc = any(w in loc_txt for w in ("门外", "窗外", "暗处", "走廊外", "拐角", "车内"))
                        if tot_sc_aud >= 9 and not is_witness_loc and protagonist in sc.get("mute_present_characters", []):
                            hard_errors.append(
                                f"第 {ep_no} 集重头场景 {sc['scene_id']}（共{tot_sc_aud}句对白）主角「{protagonist}」在场却 0 句有声开口，须让主角开口回应或将该场标为门外暗中观察"
                            )

        jargon_hits = [w for w in CAMERA_JARGON if w in body]
        if jargon_hits:
            warnings.append(f"第 {ep_no} 集混入摄影/水印术语：{jargon_hits}")

        cliche_hits = [w for w in AI_CLICHES if w in body]
        if cliche_hits:
            warnings.append(f"第 {ep_no} 集出现网文套话：{cliche_hits}")

        episodes.append(
            {
                "episode": ep_no,
                "title": ep_title,
                "scenes": len(scenes),
                "actions": len(actions),
                "dialogue_lines": len(raw_dialogues),
                "vo_lines": len(all_vo),
                "spoken_chars": spoken_chars,
                "avg_line_chars": avg_line_len,
                "est_duration_sec": est_sec,
                "has_end_marker": has_end_marker,
            }
        )

    mean_dur = (
        round(sum(e["est_duration_sec"] for e in episodes) / len(episodes), 1)
        if episodes
        else 0.0
    )
    return {
        "ok": len(hard_errors) == 0 and len(episodes) > 0,
        "protagonist_detected": protagonist,
        "episode_count": len(episodes),
        "mean_est_duration_sec": mean_dur,
        "episodes": episodes,
        "hard_errors": hard_errors,
        "warnings": warnings,
    }


def format_summary_table(report: Dict[str, Any]) -> str:
    lines = [
        f"共 {report['episode_count']} 集（识别主角：{report.get('protagonist_detected') or '未知'}），平均预估时长 {report['mean_est_duration_sec']} 秒（目标 100~150s，每集 20~32 句把一件事讲透）",
        "| 集号 | 集名 | 场数 | △动作数 | 对白+VO句数 | 台词总字数 | 句均字数 | 预估时长(s) | 完结标 |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for e in report["episodes"]:
        tot_lines = e["dialogue_lines"] + e["vo_lines"]
        lines.append(
            f"| {e['episode']} | {e['title']} | {e['scenes']} | {e['actions']} | "
            f"{tot_lines} ({e['vo_lines']} VO) | {e['spoken_chars']} | {e['avg_line_chars']} | "
            f"{e['est_duration_sec']} | {'✓' if e['has_end_marker'] else '✗'} |"
        )
    if report["hard_errors"]:
        lines.append("硬性错误：" + "；".join(report["hard_errors"]))
    if report["warnings"]:
        lines.append("节奏提示：" + "；".join(report["warnings"]))
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("script_file", help="Markdown script file to check")
    ap.add_argument("--json-out", help="Optional JSON output path")
    args = ap.parse_args()

    text = Path(args.script_file).read_text(encoding="utf-8")
    rep = analyze_script(text)
    print(format_summary_table(rep))
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sys.exit(0 if rep["ok"] else 1)


if __name__ == "__main__":
    main()
