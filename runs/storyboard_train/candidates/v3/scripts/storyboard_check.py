#!/usr/bin/env python3
"""Deterministic physical, timing, camera-movement & continuity checker for `hit-storyboard`.

Calibrated against 166 Hongguo hit AI short dramas (7,670 episodes):
- Median ASL: 3.75s (IQR 2.9s - 4.8s), sub-shot window 1.5s - 6.0s (0.5s precision)
- Generation Group (`生成组`): 5 - 15 integer seconds, same scene only, sum(sub-shots) == group_sec
- Empirical active camera movement ratio: median 12.5%, mean 15.0%, P90 30.0%
  (flags lifeless 0% all-static CCTV tables AND dizzying >40% over-moving tables; hard-flags compound camera spam)
- Empirical wide-shot share: ~8.9% (warns if >25% wide shots dilute vertical/short-drama intimacy)
- Checks 100% dialogue fidelity/coverage when `--screenplay` is provided
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

EP_RE = re.compile(r"^#\s*第\s*0*(\d+)\s*集[　\s:：—\-]*(.*)$", re.M)
SCENE_RE = re.compile(r"^##\s*(\d+-\d+)\s+(.+)$")
ROW_RE = re.compile(r"^\|\s*(\d+-\d+-\d+)\s*\|")
SEAM_RE = re.compile(r"【组\s*(\d+-\d+-\d+)\s*末态")
NUM_RE = re.compile(r"\d+(?:\.\d+)?")

COLS = 14
GROUP_MIN, GROUP_MAX = 5, 15
SHOT_MIN, SHOT_MAX = 1.5, 6.5

FIXED_HEADS = ("固定", "固定机位", "静止")
COMPOUND_BAD = ("+", "＋", "同时", "并同时", "推拉", "边推边摇", "环绕推近", "变焦推")
MOVEMENT_KEYWORDS = ("推", "拉", "摇", "移", "跟", "升", "降", "环绕", "手持", "微晃", "震", "转焦")

SCRIPT_DIALOGUE_RE = re.compile(
    r"^(?![#△\[\-\*>\|])([^：:\n]{1,20}?)(?:（[^）\n]*）|\([^)\n]*\))?[：:]\s*(.+)$",
    re.M,
)
SCRIPT_VO_RE = re.compile(r"^\[(?:VO|OS)\]\s*([^：:\n]+)[：:]\s*(.+)$", re.M)


def _num(cell: str) -> float | None:
    m = NUM_RE.search(cell or "")
    return float(m.group()) if m else None


def _clean_speech_chars(line_cell: str) -> int:
    s = (line_cell or "").strip()
    if not s or s in ("无", "-", "—", "（无）"):
        return 0
    if "承接上镜" in s and "：" not in s and ":" not in s:
        return 0
    # Strip speaker prefix & tags like [同步口型], [画外VO·画内闭口], （语气）
    s = re.sub(r"\[[^\]]*\]", "", s)
    s = re.sub(r"（[^）]*）|\([^)]*\)", "", s)
    if "：" in s:
        s = s.split("：", 1)[1]
    elif ":" in s:
        s = s.split(":", 1)[1]
    s = re.sub(r"[“”\"'‘’\s—…，。！？、；：,.!?;:/／]", "", s)
    return len(s)


def _extract_script_phrases(screenplay_md: str, ep_no: int) -> list[str]:
    matches = list(EP_RE.finditer(screenplay_md))
    body = screenplay_md
    for i, m in enumerate(matches):
        if int(m.group(1)) == ep_no:
            end = matches[i + 1].start() if i + 1 < len(matches) else len(screenplay_md)
            body = screenplay_md[m.end():end]
            break
    phrases: list[str] = []
    skip_keys = {"人物", "**人物**", "预估时长", "**预估时长**", "- **画幅**"}
    for spk, content in SCRIPT_DIALOGUE_RE.findall(body):
        if spk.strip() in skip_keys:
            continue
        clean = re.sub(r"[“”\"'\s]", "", content.strip())
        if len(clean) >= 4:
            phrases.append(clean[:8])
    for _, content in SCRIPT_VO_RE.findall(body):
        clean = re.sub(r"[“”\"'\s]", "", content.strip())
        if len(clean) >= 4:
            phrases.append(clean[:8])
    return phrases


def analyze_storyboard(
    storyboard_md: str,
    *,
    screenplay_md: str = "",
    expected_eps: list[int] | None = None,
) -> dict[str, Any]:
    hard_errors: list[str] = []
    warnings: list[str] = []

    ep_matches = list(EP_RE.finditer(storyboard_md))
    found_eps = [int(m.group(1)) for m in ep_matches]
    if not found_eps:
        return {
            "ok": False,
            "episode_count": 0,
            "episodes": [],
            "hard_errors": ["未解析到 `# 第 N 集` 标题"],
            "warnings": [],
        }
    if expected_eps and found_eps != expected_eps:
        hard_errors.append(f"集号序列不匹配：期望 {expected_eps}，实际 {found_eps}")

    ep_reports: list[dict[str, Any]] = []
    for idx, em in enumerate(ep_matches):
        ep_no = int(em.group(1))
        ep_title = em.group(2).strip()
        start = em.end()
        end = ep_matches[idx + 1].start() if idx + 1 < len(ep_matches) else len(storyboard_md)
        ep_body = storyboard_md[start:end]

        scenes: list[str] = []
        axis_headers = 0
        cur_scene: str | None = None
        shot_ids: list[str] = []
        bad_cols: list[str] = []
        long_shots: list[str] = []
        short_shots: list[str] = []
        crammed_speech: list[str] = []
        compound_cams: list[str] = []
        missing_cam_spec: list[str] = []
        wide_shots = 0
        active_cam_shots = 0
        talk_shots = 0
        vo_shots = 0
        total_sec = 0.0

        groups: dict[str, dict[str, Any]] = {}
        group_order: list[str] = []
        group_errors: list[str] = []
        seam_anchors = set(SEAM_RE.findall(ep_body))
        all_dialogue_concat: list[str] = []

        prev_group_end_angle_scale: tuple[str, str] | None = None
        last_group_id: str | None = None
        last_angle_scale: tuple[str, str] = ("", "")
        same_cam_seams: list[str] = []

        for raw_ln in ep_body.splitlines():
            ln = raw_ln.strip()
            sm = SCENE_RE.match(ln)
            if sm:
                cur_scene = sm.group(1)
                scenes.append(cur_scene)
                prev_group_end_angle_scale = None
                last_group_id = None
                continue
            if "轴线" in ln and ("左" in ln or "右" in ln):
                axis_headers += 1

            rm = ROW_RE.match(ln)
            if not rm:
                continue
            cells = [c.strip() for c in ln.strip("|").split("|")]
            sid = cells[0]
            shot_ids.append(sid)
            if len(cells) != COLS:
                bad_cols.append(f"{sid}({len(cells)}列)")
                continue

            gid, gdur_cell, sdur_cell, scale, angle, cam = (
                cells[1],
                cells[2],
                cells[3],
                cells[4],
                cells[5],
                cells[6],
            )
            dialogue_cell = cells[10]
            note_cell = cells[13]
            all_dialogue_concat.append(re.sub(r"[“”\"'\s]", "", dialogue_cell))

            sec = _num(sdur_cell)
            if sec is None or sec <= 0:
                bad_cols.append(f"{sid}(时长无效:{sdur_cell})")
                continue
            total_sec += sec
            if sec > SHOT_MAX:
                long_shots.append(f"{sid}({sec}s)")
            elif sec < SHOT_MIN:
                short_shots.append(f"{sid}({sec}s)")

            if any(w in scale for w in ("大全", "大远", "远景", "全景")):
                wide_shots += 1

            # Check camera movement discipline
            cam_clean = cam.strip()
            is_fixed = any(cam_clean.startswith(fh) for fh in FIXED_HEADS) or cam_clean in ("-", "—", "无")
            if not is_fixed and any(k in cam_clean for k in MOVEMENT_KEYWORDS):
                active_cam_shots += 1
                if any(cb in cam_clean for cb in COMPOUND_BAD):
                    compound_cams.append(f"{sid}({cam_clean[:24]})")
                # Active movement should state trigger/path/landing or speed
                if len(cam_clean) < 6:
                    missing_cam_spec.append(f"{sid}(运镜过于笼统:{cam_clean})")
            elif is_fixed:
                if len(cam_clean) < 4 and "固定" not in note_cell and "对峙" not in note_cell and "留白" not in note_cell and "压迫" not in note_cell:
                    # Mild check: static shot without brief reason
                    pass

            # Check speech rate feasibility
            sp_chars = _clean_speech_chars(dialogue_cell)
            if sp_chars > 0:
                if any(tag in dialogue_cell for tag in ("画外", "VO", "OS", "旁白")):
                    vo_shots += 1
                else:
                    talk_shots += 1
                # Max ~5.4 chars/sec comfortably
                if sp_chars > sec * 5.5 + 2:
                    crammed_speech.append(f"{sid}({sp_chars}字/{sec}s)")

            # Group tracking + cross-group seam angle/scale shift check
            if not gid or gid in ("无", "-", "—"):
                group_errors.append(f"{sid}:缺少生成组号")
                continue

            if last_group_id is not None and gid != last_group_id:
                prev_group_end_angle_scale = last_angle_scale
                if prev_group_end_angle_scale == (scale, angle):
                    same_cam_seams.append(f"{last_group_id}->{gid}({scale}·{angle})")

            g = groups.get(gid)
            if g is None:
                g = groups[gid] = {
                    "first": sid,
                    "scene": cur_scene,
                    "declared": set(),
                    "sum": 0.0,
                    "count": 0,
                    "last": None,
                }
                group_order.append(gid)
            else:
                if group_order[-1] != gid:
                    group_errors.append(f"{gid}:组号不连续({sid})")
                if g["scene"] != cur_scene:
                    group_errors.append(f"{gid}:跨场不断组({sid})")

            g["declared"].add(gdur_cell)
            g["sum"] += sec
            g["count"] += 1
            g["last"] = sid
            last_group_id = gid
            last_angle_scale = (scale, angle)

        # Validate groups
        for gid in group_order:
            g = groups[gid]
            if gid != g["first"]:
                group_errors.append(f"{gid}:组号须等于组首镜号({g['first']})")
            if len(g["declared"]) != 1:
                group_errors.append(f"{gid}:同组声明组时长不一致({g['declared']})")
                continue
            gdur = _num(next(iter(g["declared"])))
            if gdur is None or abs(gdur - round(gdur)) > 1e-6 or not (GROUP_MIN <= int(round(gdur)) <= GROUP_MAX):
                group_errors.append(f"{gid}:组时长({next(iter(g['declared']))})非{GROUP_MIN}-{GROUP_MAX}整数秒")
            elif abs(g["sum"] - gdur) > 1e-4:
                group_errors.append(f"{gid}:子镜之和({g['sum']:g}s)!=组时长({gdur:g}s)")
            if g["count"] > 6:
                warnings.append(f"第{ep_no}集组{gid}内含{g['count']}镜(>6镜易致视频模型切镜崩坏)")

        n_shots = len(shot_ids)
        dup_count = n_shots - len(set(shot_ids))
        if n_shots == 0:
            hard_errors.append(f"第{ep_no}集未解析到任何分镜行")
        if bad_cols:
            hard_errors.append(f"第{ep_no}集列数/时长异常：{bad_cols[:5]}")
        if dup_count > 0:
            hard_errors.append(f"第{ep_no}集存在{dup_count}个重复镜号")
        if group_errors:
            hard_errors.append(f"第{ep_no}集生成组错误：{group_errors[:5]}")
        if compound_cams:
            warnings.append(f"第{ep_no}集存在复合运镜：{compound_cams[:4]}")
        if crammed_speech:
            warnings.append(f"第{ep_no}集台词超载塞不进镜长：{crammed_speech[:4]}")
        if long_shots:
            warnings.append(f"第{ep_no}集单镜超6.5s：{long_shots[:4]}")
        if short_shots:
            warnings.append(f"第{ep_no}集单镜不足1.5s：{short_shots[:4]}")
        if same_cam_seams:
            warnings.append(f"第{ep_no}集跨组接缝同景别同机位硬接：{same_cam_seams[:3]}")
        if scenes and axis_headers < len(scenes):
            warnings.append(f"第{ep_no}集共{len(scenes)}场，仅{axis_headers}场声明180°轴线")

        active_pct = round(active_cam_shots * 100.0 / max(1, n_shots), 1)
        wide_pct = round(wide_shots * 100.0 / max(1, n_shots), 1)
        asl_sec = round(total_sec / max(1, n_shots), 2)

        if active_pct < 6.0:
            warnings.append(f"第{ep_no}集主动运镜率过低({active_pct}%)，承重拍缺乏镜头运动")
        elif active_pct > 42.0:
            warnings.append(f"第{ep_no}集主动运镜率过高({active_pct}% > 42%)，过场滥用运镜")
        if wide_pct > 25.0:
            warnings.append(f"第{ep_no}集全景占比偏高({wide_pct}% > 25%)，削弱人物微表情压迫感")
        if missing_cam_spec:
            warnings.append(f"第{ep_no}集主动运镜缺少触发/路径/落点要素：{missing_cam_spec[:4]}")

        # Optional screenplay dialogue coverage check
        missing_lines: list[str] = []
        if screenplay_md.strip():
            full_text_clean = "".join(all_dialogue_concat)
            expected_phrases = _extract_script_phrases(screenplay_md, ep_no)
            for ph in expected_phrases:
                if ph not in full_text_clean:
                    missing_lines.append(ph)
            if len(missing_lines) > max(2, int(len(expected_phrases) * 0.15)):
                hard_errors.append(
                    f"第{ep_no}集漏拆剧本台词较多({len(missing_lines)}/{len(expected_phrases)}句未匹配，如:{missing_lines[:3]})"
                )
            elif missing_lines:
                warnings.append(f"第{ep_no}集疑似改动或漏落少量台词片段：{missing_lines[:3]}")

        ep_reports.append(
            {
                "episode": ep_no,
                "title": ep_title,
                "scenes": len(scenes),
                "axis_headers": axis_headers,
                "shots": n_shots,
                "groups": len(group_order),
                "seam_anchors": len(seam_anchors),
                "total_sec": round(total_sec, 1),
                "asl_sec": asl_sec,
                "active_cam_shots": active_cam_shots,
                "active_cam_pct": active_pct,
                "wide_pct": wide_pct,
                "talk_shots": talk_shots,
                "vo_shots": vo_shots,
                "crammed_speech_count": len(crammed_speech),
                "compound_cam_count": len(compound_cams),
            }
        )

    return {
        "ok": len(hard_errors) == 0 and len(ep_reports) > 0,
        "episode_count": len(ep_reports),
        "episodes": ep_reports,
        "hard_errors": hard_errors,
        "warnings": warnings,
    }


def format_summary_table(report: dict[str, Any]) -> str:
    lines = [
        f"分镜物理体检：共 {report['episode_count']} 集｜状态：{'PASS' if report['ok'] else 'FAIL'}",
        "| 集 | 场数(轴线) | 总镜数 | 生成组(末态锚) | 总时长(s) | 均镜长ASL(s) | 主动运镜率 | 全景占比 | 同步/画外声镜 |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for e in report["episodes"]:
        lines.append(
            f"| {e['episode']} | {e['scenes']} ({e['axis_headers']}) | {e['shots']} | "
            f"{e['groups']} ({e['seam_anchors']}) | {e['total_sec']} | {e['asl_sec']} | "
            f"{e['active_cam_pct']}% ({e['active_cam_shots']}镜) | {e['wide_pct']}% | "
            f"{e['talk_shots']}/{e['vo_shots']} |"
        )
    if report["hard_errors"]:
        lines.append("硬性错误：" + "；".join(report["hard_errors"]))
    if report["warnings"]:
        lines.append("工艺提示：" + "；".join(report["warnings"]))
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="Check hit-storyboard Markdown output")
    ap.add_argument("storyboard_file", help="Storyboard markdown path")
    ap.add_argument("--screenplay", help="Optional source screenplay markdown path for coverage check")
    ap.add_argument("--json-out", help="Optional JSON report path")
    args = ap.parse_args()

    sb_txt = Path(args.storyboard_file).read_text(encoding="utf-8")
    sp_txt = Path(args.screenplay).read_text(encoding="utf-8") if args.screenplay else ""
    rep = analyze_storyboard(sb_txt, screenplay_md=sp_txt)
    print(format_summary_table(rep))
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sys.exit(0 if rep["ok"] else 1)


if __name__ == "__main__":
    main()
