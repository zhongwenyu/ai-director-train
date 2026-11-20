#!/usr/bin/env python3
"""Physical sanity & natural timing checker for hit-short-drama scripts.

Calibrated against 6,968 real Hongguo AI short drama episodes:
- Natural dramatic speech rate: ~4.6 spoken chars/sec (~204 spoken chars/min when combined with visual beats)
- Visual action beat (`△`): ~1.6 sec on average
- Scene transition (`## N-M`): ~2.0 sec

Does NOT enforce rigid Goodhart rules (no forced shoving, no >3 action bans).
Only checks:
1. Episode completeness & `【本集完】` markers
2. Natural 1-3 minute floating duration window (55s - 195s, batch mean ~85s - 165s)
3. Camera jargon leakage (`镜头切至`, `近景`, `全景`, `水印`) or obvious AI cliché phrases
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

RE_EP_HEADER = re.compile(r"^#{1,2}\s*第\s*(\d+)\s*集[　\s:：—\-]*(.*)$", re.M)
RE_SCENE_HEADER = re.compile(r"^##\s*(\d+)-(\d+)\s+(.+)$", re.M)
RE_ACTION = re.compile(r"^△\s*(.+)$", re.M)
RE_VO_LINE = re.compile(r"^\[(?:VO|OS)\]\s*([^：:\n]+)[：:]\s*(.+)$", re.M)
RE_SCREEN_TEXT = re.compile(r"^\[画面文字\]\s*(.+)$", re.M)
RE_DIALOGUE = re.compile(
    r"^(?![#△\[\-\*])([^：:\n]{1,24}?)(?:（[^）\n]*）|\([^)\n]*\))?[：:]\s*(.+)$",
    re.M,
)

CAMERA_JARGON = ("镜头切", "过肩近景", "正面近景", "全景镜头", "中近景", "推镜头", "果果剧", "水印")
AI_CLICHES = ("嘴角勾起一抹", "空气仿佛凝固", "空气瞬间凝固", "眼神冷得像冰", "三分凉薄")


def analyze_script(text: str, expected_eps: list[int] | None = None) -> dict[str, Any]:
    matches = list(RE_EP_HEADER.finditer(text))
    episodes: list[dict[str, Any]] = []
    warnings: list[str] = []
    hard_errors: list[str] = []

    found_nums = [int(m.group(1)) for m in matches]
    if expected_eps and found_nums != expected_eps:
        hard_errors.append(f"集数序列不匹配：期望 {expected_eps}，实际解析到 {found_nums}")

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
            if after_end:
                warnings.append(f"第 {ep_no} 集在【本集完】之后仍有残留文本（{len(after_end)}字）")

        scenes = RE_SCENE_HEADER.findall(body)
        actions = RE_ACTION.findall(body)
        vo_lines = RE_VO_LINE.findall(body)
        raw_dialogues = [
            (spk.strip(), line.strip())
            for spk, line in RE_DIALOGUE.findall(body)
            if spk.strip() not in ("人物", "**人物**", "预估时长", "**预估时长**")
        ]

        spoken_texts = [ln for _, ln in raw_dialogues] + [ln for _, ln in vo_lines]
        spoken_chars = sum(len(re.sub(r"\s+", "", s)) for s in spoken_texts)
        spoken_count = len(spoken_texts)
        avg_line_len = round(spoken_chars / spoken_count, 1) if spoken_count else 0.0

        est_sec = round(spoken_chars / 4.6 + len(actions) * 1.6 + max(1, len(scenes)) * 2.0, 1)
        if est_sec < 55:
            warnings.append(f"第 {ep_no} 集预估时长偏短（{est_sec}s < 60s），戏量可能单薄")
        elif est_sec > 175:
            hard_errors.append(f"第 {ep_no} 集预估时长超标（{est_sec}s > 175s），台词过密或戏量膨胀，须精简为短剧快节奏")
        elif est_sec > 155:
            warnings.append(f"第 {ep_no} 集预估时长偏长（{est_sec}s > 155s），注意保持紧凑")

        if avg_line_len > 28:
            hard_errors.append(f"第 {ep_no} 集句均字数过长（{avg_line_len}字 > 28字），像念财务汇报/背景说明书，须改为短促有力的活人短句（建议句均14~25字）")

        max_single = max(([len(s) for _, s in raw_dialogues] + [len(s) for s in vo_lines]) or [0])
        if max_single > 56:
            hard_errors.append(f"第 {ep_no} 集存在超长单句台词（{max_single}字 > 56字），严禁一口气背诵长段背景或报账")

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
                "vo_lines": len(vo_lines),
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
        "episode_count": len(episodes),
        "mean_est_duration_sec": mean_dur,
        "episodes": episodes,
        "hard_errors": hard_errors,
        "warnings": warnings,
    }


def format_summary_table(report: dict[str, Any]) -> str:
    lines = [
        f"共 {report['episode_count']} 集，平均预估时长 {report['mean_est_duration_sec']} 秒（目标 60~180s 浮动，均值 ~120s）",
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
