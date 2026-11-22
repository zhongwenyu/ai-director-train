#!/home/zhongwenyu/data/anaconda3/bin/python3
"""
4-Agent Hermetic Closed-Loop Video Generation Skill Evolution Engine (`trainer/evolve_video_skill.py`).

Upgraded Regression Training & Target-Video Verification Architecture:
  1. Dedicated 3-GPU Resident Hardware Pipeline:
     - `Spark:8338` -> Dedicated `MiniMax H3 Image` (6 steps, permanently warm in 60GiB RAM)
     - `RTX 5090 D:8188` -> Dedicated `MiniMax H3 Video` (14 steps + Frame-0 AddGuide, LPT queue)
     - `RTX 4070 TiS:8090` -> Dedicated `368p` parallel voiceover synthesis (`inner_os` & `offscreen_speech`)
  2. Diversified `K=2` Tournament Beam Search per Round:
     - Blind Meta-Optimizer proposes 2 complementary anti-overfit candidate skills in parallel (`v{r}a`, `v{r}b`),
       screened head-to-head on a 3-drama orthogonal subset (`16:9` multi-focus + `16:9` inner-OS + `9:16` period)
       before pushing the tournament winner through full `DEV + Unseen VAL` verification!
  3. Dual-Ruler Regression & Target-Parity Verification:
     - Ruler 1 (`Regression Gate`): Order-swapped dual-blind `v_cand vs v_champ` on `DEV` + unseen `VAL`
       (enforcing positive `VAL` win-rate/delta & zero severe regression).
     - Ruler 2 (`Target-Video Parity`): Order-swapped dual-blind `v_cand vs Target Gold Video`
       (including `target_video.mp4`) + deterministic physical signal alignment (`verify_against_target.py`:
       ASL cut-pacing gap, Silero-VAD zero-truncation rate, motion liveness, and Target Parity %)!
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

TRAIN_ROOT = Path("/home/zhongwenyu/project/ai-director-train")
BENCH_ROOT = TRAIN_ROOT / "corpus" / "video_bench"
EVO_ROOT = TRAIN_ROOT / "runs" / "video_skill_evolution"
CAND_ROOT = EVO_ROOT / "candidates"
RENDERS_ROOT = EVO_ROOT / "renders"
ARENA_ROOT = EVO_ROOT / "arena_logs"
VERIFY_ROOT = EVO_ROOT / "target_verification"
LIVE_SKILL_DIR = TRAIN_ROOT / ".agents" / "skills" / "hit-video"

for p in (
    str(TRAIN_ROOT / "trainer"),
    str(TRAIN_ROOT / "judge"),
    str(LIVE_SKILL_DIR / "scripts"),
):
    if p not in sys.path:
        sys.path.insert(0, p)

import llm_clients as L  # noqa: E402
import video_arena_judge as VAJ  # noqa: E402
import native_video_engine as NVE  # noqa: E402
import verify_against_target as VAT  # noqa: E402

# MDL (Minimum Description Length) Char Caps per evolvable skill file to prevent rule bloat!
EVOLVABLE_FILES: Dict[str, int] = {
    "SKILL.md": 3400,
    "prompts/stage1_director_decompose.md": 3600,
    "prompts/stage2_keyframe_prompting.md": 3600,
    "prompts/stage3_motion_acting_prompting.md": 4000,
}

# Orthogonal 3-drama fast screening subset covering multi-focus 16:9, inner-OS 16:9, and period 9:16
SCREEN_CASE_IDS = ("dev_01_workplace_rival", "dev_02_mindread_os", "dev_04_period_1988")

FORBIDDEN_MUTATION_PATTERNS = [
    re.compile(r"(?<!\d)(?:[1-9]\d?)\s*[%％]"),  # Blocks 1%..99% Goodhart quotas while allowing 0% and 100%
    re.compile(
        r"青禾|Coco|小钱|叶寻|林双双|楚南|夏芊芊|夏建国|赵帆|杨浩|李明河|秦朗|"
        r"星爸爸|雪王冰城|塞纳河畔|窝囊牛马|博物馆值夜班|重回1988|脑瓜崩",
        re.IGNORECASE,
    ),
]

SCENE_PLAN_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "scene_summary": {"type": "string"},
        "clips": {
            "type": "array",
            "minItems": 1,
            "maxItems": 5,
            "items": {
                "type": "object",
                "properties": {
                    "clip_id": {"type": "string"},
                    "duration_s": {"type": "integer", "minimum": 2, "maximum": 12},
                    "camera_framing": {"type": "string"},
                    "visible_role_ids": {"type": "array", "items": {"type": "string"}},
                    "foreground_silhouette_role_ids": {"type": "array", "items": {"type": "string"}},
                    "prop_ids": {"type": "array", "items": {"type": "string"}},
                    "include_scene_plate_in_keyframe": {"type": "boolean"},
                    "keyframe_prompt": {"type": "string"},
                    "speaking_role_ids": {"type": "array", "items": {"type": "string"}},
                    "inner_os": {
                        "anyOf": [
                            {"type": "null"},
                            {
                                "type": "object",
                                "properties": {
                                    "speaker_id": {"type": "string"},
                                    "text": {"type": "string"},
                                    "start_s": {"type": "number"},
                                    "mode": {"type": "string", "enum": ["inner_os", "offscreen_speech"]},
                                },
                                "required": ["speaker_id", "text", "start_s", "mode"],
                                "additionalProperties": False,
                            },
                        ]
                    },
                    "lcut_audio_hold_over_next_s": {"type": "number", "minimum": 0.0, "maximum": 1.4},
                    "clip_summary": {"type": "string"},
                    "detailed_action_and_dialogue": {"type": "string"},
                    "soundscape": {"type": "string"},
                },
                "required": [
                    "clip_id",
                    "duration_s",
                    "camera_framing",
                    "visible_role_ids",
                    "foreground_silhouette_role_ids",
                    "prop_ids",
                    "include_scene_plate_in_keyframe",
                    "keyframe_prompt",
                    "speaking_role_ids",
                    "inner_os",
                    "lcut_audio_hold_over_next_s",
                    "clip_summary",
                    "detailed_action_and_dialogue",
                    "soundscape",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["scene_summary", "clips"],
    "additionalProperties": False,
}

BOTTLENECK_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "abstract_bottlenecks": {
            "type": "array",
            "minItems": 2,
            "maxItems": 5,
            "items": {
                "type": "string",
                "description": "跨题材抽象视听/微表演/首帧景深/切镜节奏/声画同步共性短板（严禁出现任何角色名、剧名、台词原文、特定职业或具体道具词！每条90字以内）",
            },
        }
    },
    "required": ["abstract_bottlenecks"],
    "additionalProperties": False,
}

MUTATION_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "mutation_rationale": {"type": "string"},
        "files": {
            "type": "object",
            "properties": {
                "SKILL.md": {"type": "string"},
                "prompts/stage1_director_decompose.md": {"type": "string"},
                "prompts/stage2_keyframe_prompting.md": {"type": "string"},
                "prompts/stage3_motion_acting_prompting.md": {"type": "string"},
            },
            "required": list(EVOLVABLE_FILES.keys()),
            "additionalProperties": False,
        },
    },
    "required": ["mutation_rationale", "files"],
    "additionalProperties": False,
}

PROSECUTOR_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "approved": {"type": "boolean"},
        "violations": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["approved", "violations"],
    "additionalProperties": False,
}


def load_skill_bundle(cand_dir: Path) -> Dict[str, str]:
    return {rel: (cand_dir / rel).read_text(encoding="utf-8") for rel in EVOLVABLE_FILES}


def save_skill_bundle(cand_dir: Path, files: Dict[str, str]) -> None:
    for rel, content in files.items():
        p = cand_dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content.strip() + "\n", encoding="utf-8")


def load_split_cases(split: str) -> List[Dict[str, Any]]:
    split_dir = BENCH_ROOT / split
    cases = [json.loads(sp.read_text(encoding="utf-8")) for sp in sorted(split_dir.glob("*/beat_spec.json"))]
    if not cases:
        raise RuntimeError(f"No benchmark cases found for split={split!r} in {split_dir}")
    return cases


def public_beat_spec_for_generator(beat_spec: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "case_id": beat_spec["case_id"],
        "aspect_ratio": beat_spec["aspect_ratio"],
        "target_duration_s": beat_spec["target_duration_s"],
        "setting_summary": beat_spec["setting_summary"],
        "dramatic_goal": beat_spec["dramatic_goal"],
        "initial_blocking": beat_spec.get("initial_blocking", ""),
        "available_scene_tag": "[Scene]",
        "characters": beat_spec["characters"],
        "props": beat_spec.get("props", []),
        "dialogue_turns": beat_spec["dialogue_turns"],
    }


def generate_scene_plan_blind(skill_files: Dict[str, str], beat_spec: Dict[str, Any], out_plan_path: Path) -> Dict[str, Any]:
    if out_plan_path.is_file() and out_plan_path.stat().st_size > 100:
        return json.loads(out_plan_path.read_text(encoding="utf-8"))

    pub_spec = public_beat_spec_for_generator(beat_spec)
    prompt = (
        "你是一位专业 AI 短剧导演与多模态视频生成编译专家。请严格遵循下方提供的【当前版本技能规范】，"
        "将给定的【戏剧段落任务卡】编译为结构化 `scene_plan` JSON。\n\n"
        "==================== 当前版本技能规范 ====================\n"
        + "\n\n".join(f"### 文件 `{k}`\n{v}" for k, v in skill_files.items())
        + "\n\n==================== 戏剧段落任务卡 ====================\n"
        + json.dumps(pub_spec, ensure_ascii=False, indent=2)
        + "\n\n【硬性输出契约】\n"
        "1. 必须覆盖任务卡中的全部 `dialogue_turns`（画内对白用 `<CHR_x> speaks (起s-止s): <d>[Chinese] 原文</d>`，心声或画外独白放入 `inner_os` 且画内角色闭嘴，严禁漏句或改字！）。\n"
        "2. `visible_role_ids` 只填该子镜头实际露出正脸/侧脸/正身的角色 ID；若某角色仅作为虚化背影肩部前景出现，只放入 `foreground_silhouette_role_ids`，绝不放入 `visible_role_ids`。\n"
        "3. `clip_summary`、`keyframe_prompt` 与 `detailed_action_and_dialogue` 除 `<d>[Chinese] ... </d>` 内的中文台词外，全部使用英文编写。"
    )
    return L.call_agy_json(prompt, SCENE_PLAN_SCHEMA, effort="medium", timeout=480, out_path=out_plan_path)


def compute_plan_telemetry(plans: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    clip_counts, clip_durs = [], []
    reaction_clips, lcut_clips, tight_framings, total_clips = 0, 0, 0, 0
    for pl in plans:
        cs = pl.get("clips") or []
        clip_counts.append(len(cs))
        for c in cs:
            total_clips += 1
            clip_durs.append(float(c.get("duration_s", 4)))
            if not c.get("speaking_role_ids") and not c.get("inner_os"):
                reaction_clips += 1
            if float(c.get("lcut_audio_hold_over_next_s", 0.0) or 0.0) >= 0.25:
                lcut_clips += 1
            fr = str(c.get("camera_framing", "")).upper()
            if any(k in fr for k in ("CU", "MCU", "CLOSE", "OTS")):
                tight_framings += 1
    return {
        "avg_clips_per_scene": round(statistics.mean(clip_counts), 2) if clip_counts else 0.0,
        "avg_clip_duration_s": round(statistics.mean(clip_durs), 2) if clip_durs else 0.0,
        "silent_reaction_clip_ratio": round(reaction_clips / max(1, total_clips), 3),
        "lcut_overlap_clip_ratio": round(lcut_clips / max(1, total_clips), 3),
        "tight_mcu_cu_ots_ratio": round(tight_framings / max(1, total_clips), 3),
    }


def render_candidate_on_cases(
    cand_id: str,
    skill_files: Dict[str, str],
    cases: Sequence[Dict[str, Any]],
    gpu_pool: NVE.DualGPUPool,
    *,
    resolution: str = "512p",
    seed_offset: int = 0,
) -> Tuple[Dict[str, Path], Dict[str, Dict[str, Any]]]:
    cand_render_dir = RENDERS_ROOT / cand_id
    cand_render_dir.mkdir(parents=True, exist_ok=True)

    plans: Dict[str, Dict[str, Any]] = {}
    with cf.ThreadPoolExecutor(max_workers=max(1, len(cases))) as ex:
        fut_map = {
            ex.submit(
                generate_scene_plan_blind,
                skill_files,
                c,
                cand_render_dir / c["case_id"] / "scene_plan.json",
            ): c
            for c in cases
        }
        for fut in cf.as_completed(fut_map):
            c = fut_map[fut]
            plans[c["case_id"]] = fut.result()
            print(f"  [plan-ok] {cand_id} :: {c['case_id']} ({len(plans[c['case_id']]['clips'])} clips)", flush=True)

    videos: Dict[str, Path] = {}
    with cf.ThreadPoolExecutor(max_workers=max(1, len(cases))) as ex:
        fut_v = {
            ex.submit(
                NVE.execute_scene_plan,
                plans[c["case_id"]],
                c,
                cand_render_dir / c["case_id"],
                gpu_pool,
                resolution=resolution,
                steps=14,
                base_seed=910000 + seed_offset + idx * 100,
            ): c["case_id"]
            for idx, c in enumerate(cases)
        }
        for fut in cf.as_completed(fut_v):
            cid = fut_v[fut]
            videos[cid] = fut.result()
            print(f"  [video-ok] {cand_id} :: {cid} -> {videos[cid]}", flush=True)

    return videos, plans


def evaluate_arena_on_cases(
    arena_tag: str,
    cases: Sequence[Dict[str, Any]],
    cand_videos: Dict[str, Path],
    ref_videos: Dict[str, Path],
) -> Dict[str, Any]:
    out_file = ARENA_ROOT / f"{arena_tag}.json"
    if out_file.is_file():
        return json.loads(out_file.read_text(encoding="utf-8"))
    ARENA_ROOT.mkdir(parents=True, exist_ok=True)

    case_results: List[Dict[str, Any]] = []

    def _eval_one(c: Dict[str, Any]) -> Dict[str, Any]:
        cid = c["case_id"]
        char_refs = [
            (ch["role_id"], Path(c["asset_files"][ch["role_id"]]))
            for ch in c.get("characters", [])
            if ch["role_id"] in c.get("asset_files", {})
        ]
        return VAJ.judge_pair_swapped(c, char_refs, cand_videos[cid], ref_videos[cid], effort="medium")

    with cf.ThreadPoolExecutor(max_workers=max(1, len(cases))) as ex:
        for res in ex.map(_eval_one, cases):
            case_results.append(res)
            print(
                f"  [arena] {arena_tag} :: {res['case_id']} -> {res['outcome']} "
                f"(cand={res['cand_score']} vs ref={res['champ_score']}, delta={res['score_delta']:+.2f})",
                flush=True,
            )

    wins = sum(1 for r in case_results if r["outcome"] == "cand_win")
    losses = sum(1 for r in case_results if r["outcome"] == "champ_win")
    ties = sum(1 for r in case_results if r["outcome"] == "tie")
    cand_mean = round(statistics.mean(r["cand_score"] for r in case_results), 2)
    ref_mean = round(statistics.mean(r["champ_score"] for r in case_results), 2)
    dim_means_cand = {k: round(statistics.mean(r["cand_dim_avg"][k] for r in case_results), 2) for k in VAJ.DIM_KEYS}
    dim_means_ref = {k: round(statistics.mean(r["champ_dim_avg"][k] for r in case_results), 2) for k in VAJ.DIM_KEYS}

    summary = {
        "arena_tag": arena_tag,
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "cand_mean_score": cand_mean,
        "ref_mean_score": ref_mean,
        "mean_delta": round(cand_mean - ref_mean, 2),
        "cand_dim_means": dim_means_cand,
        "ref_dim_means": dim_means_ref,
        "cases": case_results,
    }
    out_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def scrub_entities_from_defects(cases: Sequence[Dict[str, Any]], arena_summary: Dict[str, Any]) -> List[str]:
    ban_tokens: List[str] = []
    for c in cases:
        ban_tokens.append(c["case_id"])
        for ch in c.get("characters", []):
            if ch.get("display_name"):
                ban_tokens.append(ch["display_name"])
            ban_tokens.append(ch["role_id"])
        for pr in c.get("props", []):
            if pr.get("name"):
                ban_tokens.append(pr["name"])
    ban_tokens = [t for t in sorted(set(ban_tokens), key=len, reverse=True) if len(t) >= 2]

    scrubbed: List[str] = []
    for cr in arena_summary.get("cases", []):
        for d in cr.get("cand_defects", []):
            s = re.sub(r"[“\"「『].*?[”\"」』]", "[台词]", str(d))
            for tok in ban_tokens:
                s = s.replace(tok, "[角色/元素]")
            scrubbed.append(s)
    return scrubbed


def distill_plot_blind_bottlenecks(
    dev_cases: Sequence[Dict[str, Any]],
    arena_summary: Dict[str, Any],
    signal_report: Dict[str, Any],
    telemetry: Dict[str, Any],
    out_path: Path,
) -> List[str]:
    scrubbed_defects = scrub_entities_from_defects(dev_cases, arena_summary)
    sig_summary = {k: signal_report[k] for k in ("zero_tail_truncation_rate", "mean_cand_asl_s", "mean_target_gold_asl_s", "mean_asl_abs_gap_s", "target_parity_overall_pct")}
    prompt = (
        "你是多模态视频生成系统的【脱敏残差蒸馏器（Plot-Blind Bottleneck）】。\n"
        "下方是当前视频生成技能对比目标标杆原片在多题材开发集上的六维均分、客观信号探针差距、结构遥测统计及脱敏扣分记录。\n"
        "请将其归纳为 3～5 条**纯粹跨题材通用（同时适用于现代、年代、古装、悬疑、情感）的视听/微表演/首帧景深/切镜节奏/声画同步底层共性短板**。\n"
        "严禁出现任何具体剧情、职业、角色称谓、具体台词或单一场景动作词！\n\n"
        f"【六维均分对比（当前技能 vs 目标原片标杆）】\n候选: {json.dumps(arena_summary['cand_dim_means'], ensure_ascii=False)}\n"
        f"目标标杆: {json.dumps(arena_summary['ref_dim_means'], ensure_ascii=False)}\n\n"
        f"【客观物理信号对齐度】\n{json.dumps(sig_summary, ensure_ascii=False, indent=2)}\n\n"
        f"【生成计划结构遥测】\n{json.dumps(telemetry, ensure_ascii=False, indent=2)}\n\n"
        f"【脱敏缺陷列表】\n" + "\n".join(f"- {x}" for x in scrubbed_defects[:25])
    )
    res = L.call_agy_json(prompt, BOTTLENECK_SCHEMA, effort="medium", timeout=360, out_path=out_path)
    return res["abstract_bottlenecks"]


def validate_mutation_gates(files: Dict[str, str]) -> List[str]:
    errors: List[str] = []
    for rel, max_chars in EVOLVABLE_FILES.items():
        txt = files.get(rel, "")
        if len(txt) < 120:
            errors.append(f"{rel} is too short ({len(txt)} chars)")
        if len(txt) > max_chars:
            errors.append(f"{rel} exceeds MDL cap ({len(txt)} > {max_chars} chars); compress rules instead of bloating!")
        for pat in FORBIDDEN_MUTATION_PATTERNS:
            m = pat.search(txt)
            if m:
                errors.append(f"{rel} contains forbidden entity/quota token {m.group(0)!r}")
    if errors:
        return errors

    prosecutor_prompt = (
        "你是【反过拟合审查检察官（Anti-Overfitting Prosecutor）】。请严格审查以下视频生成 Skill 文件，若存在以下任一违规，必须判 `approved: false`：\n"
        "1. 硬编码了某一部具体剧名、角色名、台词或狭窄题材专属桥段（例如把全剧都锁死成办公室揉太阳穴/喝咖啡/古装挥剑）；\n"
        "2. 设定了机械死板的百分比配额（如“必须占73%”）；\n"
        "3. 允许并鼓励跨题材成立的物理与视听第一性原理（如：浅景深中近景/特写聚焦微表情、0%中性或微克制起幅首帧、贴合当前情境的近身具象小动作支点、眼神与呼吸先于开口的生理时序、听话人无台词微反应切镜与L-Cut声留画切、背影前景角色不挂载正脸参考图等）。\n\n"
        + "\n\n".join(f"### `{k}`\n{v}" for k, v in files.items())
    )
    verdict = L.call_agy_json(prosecutor_prompt, PROSECUTOR_SCHEMA, effort="medium", timeout=300)
    if not verdict.get("approved"):
        errors.extend(verdict.get("violations") or ["Rejected by Anti-Overfitting Prosecutor"])
    return errors


def propose_single_axis_candidate(
    axis_directive: str,
    champ_files: Dict[str, str],
    bottlenecks: Sequence[str],
    telemetry: Dict[str, Any],
    cand_dir: Path,
) -> Tuple[Dict[str, str], str]:
    if (cand_dir / "SKILL.md").is_file():
        rationale = (cand_dir / "mutation_rationale.txt").read_text(encoding="utf-8").strip() if (cand_dir / "mutation_rationale.txt").is_file() else "loaded cached candidate"
        return load_skill_bundle(cand_dir), rationale

    feedback = ""
    for attempt in range(1, 4):
        prompt = (
            "你是【盲视元优化架构师（Blind Meta-Optimizer）】。你看不到任何具体训练或测试剧本，"
            "只能根据下方【当前冠军视频生成 Skill】、【结构遥测统计】和【跨题材抽象共性短板】，"
            "对 4 个技能文件进行底层规律升级与精炼压缩。\n\n"
            f"【本分支差异化重点突破方向】\n{axis_directive}\n\n"
            f"【各文件最大字符上限（MDL 规则压缩门禁）】\n{json.dumps(EVOLVABLE_FILES, ensure_ascii=False)}\n"
            "严禁出现任何 `1%~99%` 数字百分比配额（可用“主导/优先/常态”表述，0%中性态与100%全覆盖除外），严禁出现任何具体人名、剧名或狭窄职场专属动作词！\n\n"
            f"【当前生成计划结构遥测】\n{json.dumps(telemetry, ensure_ascii=False, indent=2)}\n\n"
            "【本轮跨题材抽象短板】\n" + "\n".join(f"- {b}" for b in bottlenecks)
            + (f"\n\n【上一次提交被反过拟合门禁拦截的原因，请立即修正】：\n{feedback}" if feedback else "")
            + "\n\n==================== 当前冠军 Skill 文件 ====================\n"
            + "\n\n".join(f"### `{k}`\n{v}" for k, v in champ_files.items())
        )
        mut = L.call_agy_json(prompt, MUTATION_SCHEMA, effort="medium", timeout=600)
        new_files = mut["files"]
        gate_errs = validate_mutation_gates(new_files)
        if not gate_errs:
            save_skill_bundle(cand_dir, new_files)
            (cand_dir / "mutation_rationale.txt").write_text(mut["mutation_rationale"] + "\n", encoding="utf-8")
            return new_files, mut["mutation_rationale"]
        feedback = "; ".join(gate_errs)
        print(f"  [gate-retry {cand_dir.name} #{attempt}] Rejected: {feedback}", flush=True)
    raise RuntimeError(f"Failed to produce valid anti-overfit skill mutation for {cand_dir.name}: {feedback}")


def git_checkpoint(msg: str) -> None:
    try:
        subprocess.run(
            ["git", "-C", str(TRAIN_ROOT), "add", "judge", "trainer", ".agents/skills/hit-video", "runs/video_skill_evolution", "corpus/video_bench"],
            check=False,
        )
        diff = subprocess.run(["git", "-C", str(TRAIN_ROOT), "diff", "--cached", "--quiet"])
        if diff.returncode != 0:
            subprocess.run(["git", "-C", str(TRAIN_ROOT), "commit", "-m", msg], check=True)
            subprocess.run(["git", "-C", str(TRAIN_ROOT), "push", "origin", "main"], check=False, timeout=45)
            print(f"[git] Committed & pushed: {msg}", flush=True)
    except Exception as exc:
        print(f"[git-warn] {exc}", flush=True)


def sync_champion_to_live_skills(champ_dir: Path) -> None:
    for rel in EVOLVABLE_FILES:
        src = champ_dir / rel
        dst = LIVE_SKILL_DIR / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=2, help="Number of tournament evolutionary rounds")
    ap.add_argument("--run-final-test", action="store_true", help="Run locked unseen TEST set evaluation at end")
    ap.add_argument("--test-resolution", default="512p", choices=("512p", "768p"))
    args = ap.parse_args()

    calib_report_p = TRAIN_ROOT / "judge/calibration_video_v1/calibration_report.json"
    if not calib_report_p.is_file() or not json.loads(calib_report_p.read_text(encoding="utf-8")).get("calibration_passed"):
        raise RuntimeError("Step 0 Judge Calibration MUST pass 100% before starting evolution!")

    VERIFY_ROOT.mkdir(parents=True, exist_ok=True)
    dev_cases = load_split_cases("dev")
    val_cases = load_split_cases("val")
    screen_cases = [c for c in dev_cases if c["case_id"] in SCREEN_CASE_IDS]
    all_dev_val_cases = list(dev_cases) + list(val_cases)
    gold_dev_videos = {c["case_id"]: Path(c["gold_sealed_mp4"]) for c in dev_cases}

    # Dedicated 3-GPU resident pipeline: Spark:8338 -> H3 Image, 5090:8188 (None) -> H3 Video, 4070TiS:8090 -> 368p VO
    gpu_pool = NVE.DualGPUPool(backends=(None,))

    history_path = EVO_ROOT / "evolution_history.json"
    history: Dict[str, Any] = (
        json.loads(history_path.read_text(encoding="utf-8"))
        if history_path.is_file()
        else {"champion": "v0", "rounds": []}
    )
    champ_id = history["champion"]
    champ_dir = CAND_ROOT / champ_id
    champ_files = load_skill_bundle(champ_dir)

    print(f"\n================ [ROUND 0] RENDERING & TARGET-PARITY AUDIT OF BASELINE ({champ_id}) ================", flush=True)
    champ_all_videos, champ_all_plans = render_candidate_on_cases(champ_id, champ_files, all_dev_val_cases, gpu_pool, seed_offset=0)
    champ_dev_videos = {c["case_id"]: champ_all_videos[c["case_id"]] for c in dev_cases}
    champ_val_videos = {c["case_id"]: champ_all_videos[c["case_id"]] for c in val_cases}
    champ_dev_plans = {c["case_id"]: champ_all_plans[c["case_id"]] for c in dev_cases}

    dev_vs_gold = evaluate_arena_on_cases(f"{champ_id}_vs_gold_dev", dev_cases, champ_dev_videos, gold_dev_videos)
    champ_signals = VAT.compute_signal_alignment_report(dev_cases, champ_dev_videos, dev_vs_gold)
    (VERIFY_ROOT / f"{champ_id}_dev_target_alignment.json").write_text(
        json.dumps(champ_signals, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    champ_telemetry = compute_plan_telemetry(list(champ_dev_plans.values()))
    history["baseline_v0_target_parity"] = {
        "dev_score": dev_vs_gold["cand_mean_score"],
        "target_gold_score": dev_vs_gold["ref_mean_score"],
        "target_parity_pct": champ_signals["target_parity_overall_pct"],
        "target_parity_by_dim_pct": champ_signals["target_parity_by_dim_pct"],
        "mean_cand_asl_s": champ_signals["mean_cand_asl_s"],
        "mean_target_gold_asl_s": champ_signals["mean_target_gold_asl_s"],
        "telemetry": champ_telemetry,
    }
    history_path.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"[BASELINE {champ_id} vs TARGET GOLD] score={dev_vs_gold['cand_mean_score']} / {dev_vs_gold['ref_mean_score']} "
        f"(Parity={champ_signals['target_parity_overall_pct']}%, ASL={champ_signals['mean_cand_asl_s']}s vs Gold {champ_signals['mean_target_gold_asl_s']}s)",
        flush=True,
    )

    done_rounds = {r["round"] for r in history["rounds"]}
    latest_vs_gold = dev_vs_gold

    for r_idx in range(1, args.rounds + 1):
        if r_idx in done_rounds:
            print(f"[skip] Round {r_idx} already completed", flush=True)
            champ_id = history["champion"]
            champ_dir = CAND_ROOT / champ_id
            champ_files = load_skill_bundle(champ_dir)
            champ_all_videos, champ_all_plans = render_candidate_on_cases(champ_id, champ_files, all_dev_val_cases, gpu_pool)
            champ_dev_videos = {c["case_id"]: champ_all_videos[c["case_id"]] for c in dev_cases}
            champ_val_videos = {c["case_id"]: champ_all_videos[c["case_id"]] for c in val_cases}
            champ_dev_plans = {c["case_id"]: champ_all_plans[c["case_id"]] for c in dev_cases}
            champ_telemetry = compute_plan_telemetry(list(champ_dev_plans.values()))
            latest_vs_gold = evaluate_arena_on_cases(f"{champ_id}_vs_gold_dev", dev_cases, champ_dev_videos, gold_dev_videos)
            champ_signals = VAT.compute_signal_alignment_report(dev_cases, champ_dev_videos, latest_vs_gold)
            continue

        print(f"\n================ [ROUND {r_idx}] K=2 TOURNAMENT EVOLUTION FROM {champ_id} ================", flush=True)
        bottlenecks = distill_plot_blind_bottlenecks(
            dev_cases,
            latest_vs_gold,
            champ_signals,
            champ_telemetry,
            EVO_ROOT / f"round_{r_idx}_bottlenecks.json",
        )
        print(f"  [bottlenecks] {bottlenecks}", flush=True)

        # Diversified K=2 Proposal in Parallel (`v{r}a`: Micro-Acting & Shallow-DOF Restraint; `v{r}b`: Fast Atomic Cut + L-Cut Reaction)
        cand_a_id, cand_b_id = f"v{r_idx}a", f"v{r_idx}b"
        axis_a = (
            "方向 A（深度微表演与浅景深起幅克制优先）：重点强化首帧图采用 85mm 大光圈浅景深中近景/特写/前景半遮挡构图（虚化杂乱背景）及 0% 平静克制起幅神态；"
            "动态提示词严格遵循“先眼神流转与呼吸气口 -> 贴合当前情境的近身具象小动作支点 -> 开口说话”的生理肌肉时序，彻底消除木偶站桩与夸张假笑。"
        )
        axis_b = (
            "方向 B（短原子快切节奏、听话人微反应插切与 L-Cut 声画缝合优先）：在保持浅景深与具象微动作的基础上，将对话交锋拆分为 2.5~4.5 秒高密度单动作子镜，"
            "并在关键出招/反讽句尾强制插入 2~3 秒听话人零口型微表情反应切镜（搭配 `lcut_audio_hold_over_next_s: 0.6~1.1` 让说话尾音自然覆盖反应画面），同时精细利用 `inner_os` 分离心声与画外音。"
        )
        with cf.ThreadPoolExecutor(max_workers=2) as pex:
            fa = pex.submit(propose_single_axis_candidate, axis_a, champ_files, bottlenecks, champ_telemetry, CAND_ROOT / cand_a_id)
            fb = pex.submit(propose_single_axis_candidate, axis_b, champ_files, bottlenecks, champ_telemetry, CAND_ROOT / cand_b_id)
            files_a, rat_a = fa.result()
            files_b, rat_b = fb.result()

        # Stage 1: Fast 3-Drama Orthogonal Screening Tournament (`v{r}a` vs `v{r}b`)
        print(f"  [tournament] Screening {cand_a_id} vs {cand_b_id} on 3 orthogonal DEV cases...", flush=True)
        vids_a_scr, _ = render_candidate_on_cases(cand_a_id, files_a, screen_cases, gpu_pool, seed_offset=r_idx * 1000)
        vids_b_scr, _ = render_candidate_on_cases(cand_b_id, files_b, screen_cases, gpu_pool, seed_offset=r_idx * 1000)
        tour_arena = evaluate_arena_on_cases(f"tour_{cand_a_id}_vs_{cand_b_id}_screen", screen_cases, vids_a_scr, vids_b_scr)

        if tour_arena["mean_delta"] >= 0.0:
            win_id, win_files, win_rat = cand_a_id, files_a, rat_a
        else:
            win_id, win_files, win_rat = cand_b_id, files_b, rat_b
        print(f"  [tournament-winner] {win_id} ({tour_arena['wins']}W-{tour_arena['losses']}L, delta={tour_arena['mean_delta']:+.2f})", flush=True)

        # Stage 2: Complete rendering `win_id` across ALL DEV + UNSEEN VAL cases (reusing already-rendered 3 screen cases!)
        cand_all_videos, cand_all_plans = render_candidate_on_cases(win_id, win_files, all_dev_val_cases, gpu_pool, seed_offset=r_idx * 1000)
        cand_dev_videos = {c["case_id"]: cand_all_videos[c["case_id"]] for c in dev_cases}
        cand_val_videos = {c["case_id"]: cand_all_videos[c["case_id"]] for c in val_cases}
        cand_dev_plans = {c["case_id"]: cand_all_plans[c["case_id"]] for c in dev_cases}
        cand_telemetry = compute_plan_telemetry(list(cand_dev_plans.values()))

        # Dual-Ruler Verification in Parallel: (1) vs Prev Champion on DEV & VAL; (2) vs Target Gold Video on DEV!
        with cf.ThreadPoolExecutor(max_workers=3) as aex:
            f_dev = aex.submit(evaluate_arena_on_cases, f"{win_id}_vs_{champ_id}_dev", dev_cases, cand_dev_videos, champ_dev_videos)
            f_val = aex.submit(evaluate_arena_on_cases, f"{win_id}_vs_{champ_id}_val", val_cases, cand_val_videos, champ_val_videos)
            f_gold = aex.submit(evaluate_arena_on_cases, f"{win_id}_vs_gold_dev", dev_cases, cand_dev_videos, gold_dev_videos)
            dev_arena = f_dev.result()
            val_arena = f_val.result()
            cand_vs_gold = f_gold.result()

        cand_signals = VAT.compute_signal_alignment_report(dev_cases, cand_dev_videos, cand_vs_gold)
        (VERIFY_ROOT / f"{win_id}_dev_target_alignment.json").write_text(
            json.dumps(cand_signals, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        # Strict Unseen VAL Regression Gate + Zero Catastrophic Single-Case Drop (> -8.0 pts)
        worst_val_drop = min((cr["score_delta"] for cr in val_arena["cases"]), default=0.0)
        val_passed = (
            (
                (val_arena["wins"] > val_arena["losses"] and val_arena["mean_delta"] > 0.0)
                or (val_arena["wins"] == val_arena["losses"] and val_arena["mean_delta"] >= 1.5)
            )
            and dev_arena["mean_delta"] >= 0.0
            and worst_val_drop > -8.0
        )

        round_rec = {
            "round": r_idx,
            "prev_champion": champ_id,
            "tournament_candidates": [cand_a_id, cand_b_id],
            "tournament_screen_delta_a_vs_b": tour_arena["mean_delta"],
            "selected_candidate": win_id,
            "bottlenecks": bottlenecks,
            "mutation_rationale": win_rat,
            "cand_telemetry": cand_telemetry,
            "dev_vs_prev_champ": {k: dev_arena[k] for k in ("wins", "losses", "ties", "cand_mean_score", "ref_mean_score", "mean_delta")},
            "val_vs_prev_champ": {k: val_arena[k] for k in ("wins", "losses", "ties", "cand_mean_score", "ref_mean_score", "mean_delta")},
            "dev_target_parity_pct": cand_signals["target_parity_overall_pct"],
            "dev_target_parity_by_dim_pct": cand_signals["target_parity_by_dim_pct"],
            "mean_cand_asl_s": cand_signals["mean_cand_asl_s"],
            "promoted": val_passed,
        }

        if val_passed:
            print(
                f"  [PROMOTED!] {win_id} beat {champ_id} on unseen VAL ({val_arena['wins']}W-{val_arena['losses']}L-{val_arena['ties']}T, "
                f"delta={val_arena['mean_delta']:+.2f}) | Target Parity={cand_signals['target_parity_overall_pct']}%!",
                flush=True,
            )
            champ_id = win_id
            champ_dir = CAND_ROOT / champ_id
            champ_files = win_files
            champ_dev_videos = cand_dev_videos
            champ_val_videos = cand_val_videos
            champ_telemetry = cand_telemetry
            latest_vs_gold = cand_vs_gold
            champ_signals = cand_signals
            history["champion"] = champ_id
            sync_champion_to_live_skills(champ_dir)
        else:
            print(
                f"  [REJECTED & ROLLED BACK] {win_id} failed VAL regression gate ({val_arena['wins']}W-{val_arena['losses']}L, "
                f"delta={val_arena['mean_delta']:+.2f}, worst_drop={worst_val_drop:+.2f}). Keeping {champ_id}.",
                flush=True,
            )

        history["rounds"].append(round_rec)
        history_path.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        git_checkpoint(f"video-skill-evo: round {r_idx} ({win_id} promoted={val_passed}, parity={cand_signals['target_parity_overall_pct']}%)")

    # Locked Unseen TEST Evaluation + Direct Target-Video Comparison & Triptych Showcase!
    if args.run_final_test and "final_locked_test" not in history:
        print(f"\n================ [FINAL LOCKED TEST & TARGET COMPARISON] ({champ_id} vs v0 vs TARGET) ================", flush=True)
        test_cases = load_split_cases("test")
        v0_files = load_skill_bundle(CAND_ROOT / "v0")
        v0_test_videos, _ = render_candidate_on_cases(f"v0_test_{args.test_resolution}", v0_files, test_cases, gpu_pool, resolution=args.test_resolution, seed_offset=7000)
        champ_test_videos, _ = render_candidate_on_cases(f"{champ_id}_test_{args.test_resolution}", champ_files, test_cases, gpu_pool, resolution=args.test_resolution, seed_offset=7000)

        gold_test_videos = {c["case_id"]: Path(c["gold_sealed_mp4"]) for c in test_cases}
        with cf.ThreadPoolExecutor(max_workers=3) as tex:
            f_tv0 = tex.submit(evaluate_arena_on_cases, f"FINAL_TEST_{champ_id}_vs_v0_{args.test_resolution}", test_cases, champ_test_videos, v0_test_videos)
            f_v0g = tex.submit(evaluate_arena_on_cases, f"FINAL_TEST_v0_vs_gold_{args.test_resolution}", test_cases, v0_test_videos, gold_test_videos)
            f_chg = tex.submit(evaluate_arena_on_cases, f"FINAL_TEST_{champ_id}_vs_gold_{args.test_resolution}", test_cases, champ_test_videos, gold_test_videos)
            test_arena = f_tv0.result()
            v0_vs_gold_test = f_v0g.result()
            champ_vs_gold_test = f_chg.result()

        v0_test_sig = VAT.compute_signal_alignment_report(test_cases, v0_test_videos, v0_vs_gold_test)
        champ_test_sig = VAT.compute_signal_alignment_report(test_cases, champ_test_videos, champ_vs_gold_test)
        (VERIFY_ROOT / "final_test_target_alignment.json").write_text(
            json.dumps({"v0": v0_test_sig, "champion": champ_test_sig}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        # Render side-by-side 3-way Triptych MP4s (`[v0 | Champion | Target Video]`) for target_video (`dev_01`) + all TEST cases!
        triptych_dir = VERIFY_ROOT / "triptych_comparisons"
        triptych_paths: Dict[str, str] = {}
        v0_dev01 = RENDERS_ROOT / "v0/dev_01_workplace_rival/scene_final.mp4"
        ch_dev01 = champ_dev_videos.get("dev_01_workplace_rival")
        if v0_dev01.is_file() and ch_dev01 and ch_dev01.is_file():
            tp = VAT.render_triptych_comparison(
                v0_dev01, ch_dev01, gold_dev_videos["dev_01_workplace_rival"], triptych_dir / "triptych_dev_01_target_video.mp4", aspect_ratio="16:9"
            )
            triptych_paths["dev_01_workplace_rival"] = str(tp)

        for c in test_cases:
            cid = c["case_id"]
            tp = VAT.render_triptych_comparison(
                v0_test_videos[cid], champ_test_videos[cid], gold_test_videos[cid], triptych_dir / f"triptych_{cid}.mp4", aspect_ratio=c["aspect_ratio"]
            )
            triptych_paths[cid] = str(tp)

        history["final_locked_test"] = {
            "champion": champ_id,
            "resolution": args.test_resolution,
            "vs_v0_baseline": {k: test_arena[k] for k in ("wins", "losses", "ties", "cand_mean_score", "ref_mean_score", "mean_delta", "cand_dim_means", "ref_dim_means")},
            "v0_target_parity_pct": v0_test_sig["target_parity_overall_pct"],
            "champion_target_parity_pct": champ_test_sig["target_parity_overall_pct"],
            "champion_target_parity_by_dim_pct": champ_test_sig["target_parity_by_dim_pct"],
            "v0_asl_s": v0_test_sig["mean_cand_asl_s"],
            "champion_asl_s": champ_test_sig["mean_cand_asl_s"],
            "target_gold_asl_s": champ_test_sig["mean_target_gold_asl_s"],
            "triptych_videos": triptych_paths,
        }
        history_path.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        sync_champion_to_live_skills(CAND_ROOT / champ_id)
        git_checkpoint(
            f"video-skill-evo: FINAL LOCKED TEST ({champ_id} vs v0: {test_arena['wins']}W-{test_arena['losses']}L, "
            f"Target Parity {v0_test_sig['target_parity_overall_pct']}% -> {champ_test_sig['target_parity_overall_pct']}%)"
        )

    print("\nALL EVOLUTION & TARGET-PARITY VERIFICATION STAGES COMPLETE! Final Champion:", history["champion"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
