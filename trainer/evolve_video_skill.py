#!/home/zhongwenyu/data/anaconda3/bin/python3
"""
4-Agent Hermetic Closed-Loop Video Generation Skill Evolution Engine (`trainer/evolve_video_skill.py`).

Strictly enforces the 4-Way Information-Theoretic Firewall & Zero-Overfitting Gates:
  - Agent 1 (`Blind Scene-Plan Generator`): Sees ONLY candidate skill files + de-leaked text `beat_spec`.
    Zero access to source videos, judge rubric weights, or historical scores.
  - Execution Engine (`DualGPUPool`: RTX 5090 D + Spark + Cloud Vtrix): Renders real 1K keyframes +
    real H3 Native 14-step AddGuide clips + deterministic `L-Cut` audio-over-reaction assembly.
  - Agent 2 (`Hermetic Multimodal Video Arena Judge`): Tool-stripped `gemini-4-argon` + `Silero-VAD`
    & OpenCV probes; runs Order-Swapped Dual-Blind (`(A,B)` + `(B,A)`) on `.mp4` videos WITHOUT seeing
    any prompts, storyboards, or version names.
  - Agent 3 (`Plot-Blind Bottleneck Distiller`): Receives deterministically entity-scrubbed `DEV`
    defect records and outputs ONLY cross-genre abstract cinematic/acting/audio bottleneck laws.
  - Agent 4 (`Blind Meta-Optimizer` + `Anti-Overfitting Prosecutor`): Sees ONLY current skill files +
    abstract bottleneck frequencies + structural telemetry; enforces MDL byte caps & zero-entity/zero-quota
    gates; promotes candidate ONLY if it wins Order-Swapped Blind Arena on UNSEEN `VAL` dramas!
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
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

TRAIN_ROOT = Path("/home/zhongwenyu/project/ai-director-train")
BENCH_ROOT = TRAIN_ROOT / "corpus" / "video_bench"
EVO_ROOT = TRAIN_ROOT / "runs" / "video_skill_evolution"
CAND_ROOT = EVO_ROOT / "candidates"
RENDERS_ROOT = EVO_ROOT / "renders"
ARENA_ROOT = EVO_ROOT / "arena_logs"
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

# MDL (Minimum Description Length) Byte/Char Caps per evolvable skill file to prevent rule bloat!
EVOLVABLE_FILES: Dict[str, int] = {
    "SKILL.md": 3400,
    "prompts/stage1_director_decompose.md": 3600,
    "prompts/stage2_keyframe_prompting.md": 3600,
    "prompts/stage3_motion_acting_prompting.md": 4000,
}

# Hard deterministic anti-overfitting regex gate (blocks Goodhart % quotas, drama/role names, & narrow workplace tropes)
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
                                },
                                "required": ["speaker_id", "text", "start_s"],
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
                "description": "跨题材抽象视听/表演/剪辑/声画共性短板（严禁出现任何角色名、剧名、台词原文、特定职业或具体道具词！每条90字以内）",
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
    cases = []
    for sp in sorted(split_dir.glob("*/beat_spec.json")):
        cases.append(json.loads(sp.read_text(encoding="utf-8")))
    if not cases:
        raise RuntimeError(f"No benchmark cases found for split={split!r} in {split_dir}")
    return cases


def public_beat_spec_for_generator(beat_spec: Dict[str, Any]) -> Dict[str, Any]:
    """Strip sealed gold paths and file paths so Generator sees ONLY pure creative task spec + symbolic IDs."""
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
    """Agent 1 (Blind Generator): Runs in isolated tempdir with ZERO access to source videos or judge rubric."""
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
        "1. 必须覆盖任务卡中的全部 `dialogue_turns`（画内对白用 `<CHR_x> speaks (起s-止s): <d>[Chinese] 原文</d>`，心声放入 `inner_os` 且画内角色闭嘴，严禁漏句或改字！）。\n"
        "2. `visible_role_ids` 只填该子镜头实际露出正脸/侧脸/正身的角色 ID；若某角色仅作为虚化背影肩部前景出现，只放入 `foreground_silhouette_role_ids`，绝不放入 `visible_role_ids`。\n"
        "3. `keyframe_prompt` 与 `detailed_action_and_dialogue` 除 `<d>[Chinese] ... </d>` 内的中文台词外，全部使用英文编写。"
    )
    plan = L.call_agy_json(prompt, SCENE_PLAN_SCHEMA, effort="medium", timeout=480, out_path=out_plan_path)
    return plan


def compute_plan_telemetry(plans: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute plot-free structural telemetry across generated plans."""
    clip_counts = []
    clip_durs = []
    reaction_clips = 0
    lcut_clips = 0
    tight_framings = 0
    total_clips = 0
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
    """Generate blind scene plans in parallel, then render keyframes + H3 clips across DualGPUPool."""
    cand_render_dir = RENDERS_ROOT / cand_id
    cand_render_dir.mkdir(parents=True, exist_ok=True)

    plans: Dict[str, Dict[str, Any]] = {}
    # Generate ALL scene plans concurrently!
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
    # Launch ALL scenes concurrently: Cloud Vtrix keyframes run massively parallel while LPT DualGPUPool stays 100% saturated!
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
    """Agent 2 (Hermetic Multimodal Judge): Order-swapped dual-blind evaluation across cases."""
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
    dim_means_cand = {
        k: round(statistics.mean(r["cand_dim_avg"][k] for r in case_results), 2) for k in VAJ.DIM_KEYS
    }
    dim_means_ref = {
        k: round(statistics.mean(r["champ_dim_avg"][k] for r in case_results), 2) for k in VAJ.DIM_KEYS
    }

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
    """Deterministically scrub ALL character names, role IDs, quotes, and case IDs BEFORE Agent 3 sees defects."""
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
    telemetry: Dict[str, Any],
    out_path: Path,
) -> List[str]:
    """Agent 3 (Plot-Blind Bottleneck): Outputs strictly abstract cross-genre failure laws."""
    scrubbed_defects = scrub_entities_from_defects(dev_cases, arena_summary)
    prompt = (
        "你是多模态视频生成系统的【脱敏残差蒸馏器（Plot-Blind Bottleneck）】。\n"
        "下方是当前视频生成技能在多题材开发集上的各维度均分对比、结构遥测统计以及已脱敏的常见扣分现象。\n"
        "请将其归纳为 3～5 条**纯粹跨题材通用（同时适用于现代、年代、古装、悬疑、情感）的视听/微表演/首帧景深/切镜节奏/声画同步底层共性短板**。\n"
        "严禁出现任何具体剧情、职业、角色称谓、具体台词或单一场景动作词！\n\n"
        f"【维度均分对比（当前技能 vs 参照标杆）】\n候选: {json.dumps(arena_summary['cand_dim_means'], ensure_ascii=False)}\n"
        f"参照: {json.dumps(arena_summary['ref_dim_means'], ensure_ascii=False)}\n\n"
        f"【生成计划结构遥测】\n{json.dumps(telemetry, ensure_ascii=False, indent=2)}\n\n"
        f"【脱敏缺陷列表】\n" + "\n".join(f"- {x}" for x in scrubbed_defects[:25])
    )
    res = L.call_agy_json(prompt, BOTTLENECK_SCHEMA, effort="medium", timeout=360, out_path=out_path)
    return res["abstract_bottlenecks"]


def validate_mutation_gates(files: Dict[str, str]) -> List[str]:
    """Deterministic MDL size & zero-overfitting regex gate + Anti-Overfitting Prosecutor."""
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
        "3. 允许使用抽象宽泛、跨题材成立的物理与表演学规律（如：浅景深中近景聚焦微表情、0%~12%克制起幅首帧、15cm内贴合当前情境的具象小动作支点、眼神与呼吸先于开口的肌肉时序、听话人无台词微反应插切与L-Cut声留画切、背影前景角色不挂载正脸参考图等）。\n\n"
        + "\n\n".join(f"### `{k}`\n{v}" for k, v in files.items())
    )
    verdict = L.call_agy_json(prosecutor_prompt, PROSECUTOR_SCHEMA, effort="medium", timeout=300)
    if not verdict.get("approved"):
        errors.extend(verdict.get("violations") or ["Rejected by Anti-Overfitting Prosecutor"])
    return errors


def propose_next_skill_candidate(
    champ_files: Dict[str, str],
    bottlenecks: Sequence[str],
    telemetry: Dict[str, Any],
    cand_dir: Path,
) -> Tuple[Dict[str, str], str]:
    """Agent 4 (Blind Meta-Optimizer): Evolves skill files from abstract bottlenecks ONLY."""
    feedback = ""
    for attempt in range(1, 4):
        prompt = (
            "你是【盲视元优化架构师（Blind Meta-Optimizer）】。你看不到任何具体训练或测试剧本，"
            "只能根据下方【当前冠军视频生成 Skill】、【结构遥测统计】和【跨题材抽象共性短板】，"
            "对 4 个技能文件进行底层规律升级与精炼压缩。\n\n"
            "【核心物理与视听进化方向提示（仅保留真正普适的第一性原理）】\n"
            "- 视频扩散模型的注意力随单镜时长平方稀释：对话交锋若拆分为短促精准的 2.5~5s 单动作微拍子镜，并在长句尾段插入 2~3s 听话人零口型微反应切镜（配合 `lcut_audio_hold_over_next_s: 0.6~1.0` 声留画切），能彻底消除十几秒站桩木偶感与多切镜串衣变形；\n"
            "- 首帧图（Stage 2）若在对话/情绪拍采用浅景深中近景/特写/过肩构图（柔和虚化杂乱后景），并严守 `0%~10%` 平静克制起幅面部（绝不在静态首帧画歪嘴邪笑或张大嘴咆哮），视频微表情自然度最高；\n"
            "- 动态表演提示词（Stage 3）废除空洞情绪形容词，改为“视线转移/眨眼呼吸 -> 贴合当前情境的 15cm 内具象小动作支点 -> 带真实语气气口的对白”的生理肌肉时序。\n\n"
            f"【各文件最大字符上限（MDL 规则压缩门禁）】\n{json.dumps(EVOLVABLE_FILES, ensure_ascii=False)}\n"
            "严禁出现任何 `1%~99%` 数字百分比配额（可用“绝大多数/主导/优先”表述），严禁出现任何具体人名、剧名或狭窄职场专属动作词！\n\n"
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
        print(f"  [gate-retry {attempt}] Mutation rejected: {feedback}")
    raise RuntimeError(f"Failed to produce valid anti-overfit skill mutation after 3 attempts: {feedback}")


def git_checkpoint(msg: str) -> None:
    """Commit & push non-binary evolution artifacts to ai-director-train main per AGENTS.md Rule 3."""
    try:
        subprocess.run(["git", "-C", str(TRAIN_ROOT), "add", "judge", "trainer", ".agents/skills/hit-video", "runs/video_skill_evolution", "corpus/video_bench"], check=False)
        diff = subprocess.run(["git", "-C", str(TRAIN_ROOT), "diff", "--cached", "--quiet"])
        if diff.returncode != 0:
            subprocess.run(["git", "-C", str(TRAIN_ROOT), "commit", "-m", msg], check=True)
            subprocess.run(["git", "-C", str(TRAIN_ROOT), "push", "origin", "main"], check=False, timeout=45)
            print(f"[git] Committed & pushed: {msg}")
    except Exception as exc:
        print(f"[git-warn] {exc}")


def sync_champion_to_live_skills(champ_dir: Path) -> None:
    """Sync promoted champion skill into live `ai-director-train/.agents/skills/hit-video` and workstation."""
    for rel in EVOLVABLE_FILES:
        src = champ_dir / rel
        dst = LIVE_SKILL_DIR / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=2, help="Number of evolutionary mutation rounds")
    ap.add_argument("--run-final-test", action="store_true", help="Run locked unseen TEST set evaluation at end")
    ap.add_argument("--test-resolution", default="512p", choices=("512p", "768p"))
    args = ap.parse_args()

    calib_report_p = TRAIN_ROOT / "judge/calibration_video_v1/calibration_report.json"
    if not calib_report_p.is_file() or not json.loads(calib_report_p.read_text(encoding="utf-8")).get("calibration_passed"):
        raise RuntimeError("Step 0 Judge Calibration MUST pass 100% before starting evolution! Run calibrate_video_judge.py first.")

    dev_cases = load_split_cases("dev")
    val_cases = load_split_cases("val")
    gpu_pool = NVE.DualGPUPool(backends=(None, "sol-spark-benchmark"))

    history_path = EVO_ROOT / "evolution_history.json"
    history: Dict[str, Any] = (
        json.loads(history_path.read_text(encoding="utf-8"))
        if history_path.is_file()
        else {"champion": "v0", "rounds": []}
    )
    champ_id = history["champion"]
    champ_dir = CAND_ROOT / champ_id
    champ_files = load_skill_bundle(champ_dir)

    # Round 0: Render v0 Baseline on DEV + VAL in ONE unified massively-parallel batch!
    print(f"\n================ [ROUND 0] RENDERING & AUDITING CHAMPION BASELINE ({champ_id}) ================", flush=True)
    all_dev_val_cases = list(dev_cases) + list(val_cases)
    champ_all_videos, champ_all_plans = render_candidate_on_cases(champ_id, champ_files, all_dev_val_cases, gpu_pool, seed_offset=0)
    champ_dev_videos = {c["case_id"]: champ_all_videos[c["case_id"]] for c in dev_cases}
    champ_val_videos = {c["case_id"]: champ_all_videos[c["case_id"]] for c in val_cases}
    champ_dev_plans = {c["case_id"]: champ_all_plans[c["case_id"]] for c in dev_cases}

    gold_dev_videos = {c["case_id"]: Path(c["gold_sealed_mp4"]) for c in dev_cases}
    dev_vs_gold = evaluate_arena_on_cases(f"{champ_id}_vs_gold_dev", dev_cases, champ_dev_videos, gold_dev_videos)
    champ_telemetry = compute_plan_telemetry(list(champ_dev_plans.values()))
    print(
        f"[BASELINE {champ_id} vs GOLD on DEV] score={dev_vs_gold['cand_mean_score']} vs gold={dev_vs_gold['ref_mean_score']} "
        f"(delta={dev_vs_gold['mean_delta']:+.2f}) telemetry={champ_telemetry}"
    )

    done_rounds = {r["round"] for r in history["rounds"]}
    latest_diagnostic_arena = dev_vs_gold

    for r_idx in range(1, args.rounds + 1):
        if r_idx in done_rounds:
            print(f"[skip] Round {r_idx} already recorded in evolution_history.json")
            champ_id = history["champion"]
            champ_dir = CAND_ROOT / champ_id
            champ_files = load_skill_bundle(champ_dir)
            champ_dev_videos, champ_dev_plans = render_candidate_on_cases(champ_id, champ_files, dev_cases, gpu_pool)
            champ_val_videos, _ = render_candidate_on_cases(champ_id, champ_files, val_cases, gpu_pool, seed_offset=500)
            champ_telemetry = compute_plan_telemetry(list(champ_dev_plans.values()))
            continue

        cand_id = f"v{r_idx}"
        cand_dir = CAND_ROOT / cand_id
        print(f"\n================ [ROUND {r_idx}] EVOLVING {champ_id} -> {cand_id} ================")

        # Agent 3: Distill plot-blind bottlenecks from DEV diagnostics ONLY
        bottlenecks = distill_plot_blind_bottlenecks(
            dev_cases,
            latest_diagnostic_arena,
            champ_telemetry,
            EVO_ROOT / f"round_{r_idx}_bottlenecks.json",
        )
        print(f"  [bottlenecks] {bottlenecks}")

        # Agent 4: Propose anti-overfit mutated skill bundle
        if (cand_dir / "SKILL.md").is_file():
            cand_files = load_skill_bundle(cand_dir)
            rationale = (cand_dir / "mutation_rationale.txt").read_text(encoding="utf-8").strip() if (cand_dir / "mutation_rationale.txt").is_file() else "loaded existing candidate"
        else:
            cand_files, rationale = propose_next_skill_candidate(champ_files, bottlenecks, champ_telemetry, cand_dir)
        print(f"  [mutation] {rationale}")

        # Render candidate on DEV + UNSEEN VAL in ONE unified parallel batch & run DEV + VAL Arenas concurrently!
        cand_all_videos, cand_all_plans = render_candidate_on_cases(cand_id, cand_files, all_dev_val_cases, gpu_pool, seed_offset=r_idx * 1000)
        cand_dev_videos = {c["case_id"]: cand_all_videos[c["case_id"]] for c in dev_cases}
        cand_val_videos = {c["case_id"]: cand_all_videos[c["case_id"]] for c in val_cases}
        cand_dev_plans = {c["case_id"]: cand_all_plans[c["case_id"]] for c in dev_cases}
        cand_telemetry = compute_plan_telemetry(list(cand_dev_plans.values()))

        with cf.ThreadPoolExecutor(max_workers=2) as aex:
            f_dev = aex.submit(evaluate_arena_on_cases, f"{cand_id}_vs_{champ_id}_dev", dev_cases, cand_dev_videos, champ_dev_videos)
            f_val = aex.submit(evaluate_arena_on_cases, f"{cand_id}_vs_{champ_id}_val", val_cases, cand_val_videos, champ_val_videos)
            dev_arena = f_dev.result()
            val_arena = f_val.result()

        # Strict Unseen VAL Promotion Rule
        val_passed = (
            (val_arena["wins"] > val_arena["losses"] and val_arena["mean_delta"] > 0.0)
            or (val_arena["wins"] == val_arena["losses"] and val_arena["mean_delta"] >= 2.0)
        ) and dev_arena["mean_delta"] >= 0.0

        round_rec = {
            "round": r_idx,
            "prev_champion": champ_id,
            "candidate": cand_id,
            "bottlenecks": bottlenecks,
            "mutation_rationale": rationale,
            "cand_telemetry": cand_telemetry,
            "dev_arena": {k: dev_arena[k] for k in ("wins", "losses", "ties", "cand_mean_score", "ref_mean_score", "mean_delta", "cand_dim_means", "ref_dim_means")},
            "val_arena": {k: val_arena[k] for k in ("wins", "losses", "ties", "cand_mean_score", "ref_mean_score", "mean_delta", "cand_dim_means", "ref_dim_means")},
            "promoted": val_passed,
        }

        if val_passed:
            print(f"  [PROMOTED!] {cand_id} beat {champ_id} on unseen VAL ({val_arena['wins']}W-{val_arena['losses']}L-{val_arena['ties']}T, delta={val_arena['mean_delta']:+.2f})!")
            champ_id = cand_id
            champ_dir = cand_dir
            champ_files = cand_files
            champ_dev_videos = cand_dev_videos
            champ_val_videos = cand_val_videos
            champ_telemetry = cand_telemetry
            history["champion"] = champ_id
            sync_champion_to_live_skills(champ_dir)
            # Refresh gap vs Gold on DEV for next round's residual distillation
            latest_diagnostic_arena = evaluate_arena_on_cases(f"{champ_id}_vs_gold_dev", dev_cases, champ_dev_videos, gold_dev_videos)
            round_rec["new_champ_vs_gold_dev_delta"] = latest_diagnostic_arena["mean_delta"]
        else:
            print(f"  [REJECTED & ROLLED BACK] {cand_id} did not pass unseen VAL gate ({val_arena['wins']}W-{val_arena['losses']}L-{val_arena['ties']}T, delta={val_arena['mean_delta']:+.2f}). Keeping {champ_id}.")
            latest_diagnostic_arena = dev_arena

        history["rounds"].append(round_rec)
        history_path.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        git_checkpoint(f"video-skill-evo: round {r_idx} ({cand_id} promoted={val_passed}, champ={champ_id})")

    # Locked Unseen TEST Set Evaluation (Strictly ONCE at completion!)
    if args.run_final_test and "final_locked_test" not in history:
        print(f"\n================ [FINAL LOCKED TEST] {champ_id} vs v0 ON UNSEEN TEST DRAMAS ({args.test_resolution}) ================")
        test_cases = load_split_cases("test")
        v0_files = load_skill_bundle(CAND_ROOT / "v0")
        v0_test_videos, _ = render_candidate_on_cases(f"v0_test_{args.test_resolution}", v0_files, test_cases, gpu_pool, resolution=args.test_resolution, seed_offset=7000)
        champ_test_videos, _ = render_candidate_on_cases(f"{champ_id}_test_{args.test_resolution}", champ_files, test_cases, gpu_pool, resolution=args.test_resolution, seed_offset=7000)
        test_arena = evaluate_arena_on_cases(f"FINAL_TEST_{champ_id}_vs_v0_{args.test_resolution}", test_cases, champ_test_videos, v0_test_videos)

        gold_test_videos = {c["case_id"]: Path(c["gold_sealed_mp4"]) for c in test_cases}
        champ_vs_gold_test = evaluate_arena_on_cases(f"FINAL_TEST_{champ_id}_vs_gold_{args.test_resolution}", test_cases, champ_test_videos, gold_test_videos)

        history["final_locked_test"] = {
            "champion": champ_id,
            "resolution": args.test_resolution,
            "vs_v0_baseline": {k: test_arena[k] for k in ("wins", "losses", "ties", "cand_mean_score", "ref_mean_score", "mean_delta", "cand_dim_means", "ref_dim_means")},
            "vs_source_gold": {k: champ_vs_gold_test[k] for k in ("wins", "losses", "ties", "cand_mean_score", "ref_mean_score", "mean_delta", "cand_dim_means", "ref_dim_means")},
        }
        history_path.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        sync_champion_to_live_skills(CAND_ROOT / champ_id)
        git_checkpoint(f"video-skill-evo: final locked TEST complete ({champ_id} vs v0: {test_arena['wins']}W-{test_arena['losses']}L, delta={test_arena['mean_delta']:+.2f})")

    print("\nALL EVOLUTION STAGES COMPLETE! Final Champion:", history["champion"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
