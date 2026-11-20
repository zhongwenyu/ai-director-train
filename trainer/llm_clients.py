#!/usr/bin/env python3
"""Unified LLM client wrappers for ai-director-train.

All LLM calls (Generator, Judge, Critic, Prosecutor, Meta-Optimizer) run exclusively via
isolated `agy` sub-agent invocations (`gemini-4-carbon-medium`), with ZERO `codex` usage.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

TRAIN_ROOT = Path("/home/zhongwenyu/project/ai-director-train")
CORPUS_SOURCE_ROOT = Path(
    "/home/zhongwenyu/project/ai-director-workstation/videos/红果AI短剧_800部_前50集"
)

AGY_BIN = (
    os.environ.get("TRAIN_AGY_BIN")
    or ("/home/zhongwenyu/.config/paseo/antigravity-bin/agy"
        if Path("/home/zhongwenyu/.config/paseo/antigravity-bin/agy").is_file()
        else None)
    or shutil.which("agy")
    or "agy"
)
DEFAULT_MODEL = os.environ.get("TRAIN_AGY_MODEL", "gemini-4-carbon-medium")
DEFAULT_EFFORT = os.environ.get("TRAIN_AGY_EFFORT", "medium")
AGY_MODEL = DEFAULT_MODEL
AGY_EFFORT = DEFAULT_EFFORT
JUDGE_MODEL = os.environ.get("TRAIN_JUDGE_MODEL", "gemini-4-carbon-medium")
JUDGE_EFFORT = os.environ.get("TRAIN_JUDGE_EFFORT", "medium")


class LLMError(RuntimeError):
    pass


def strip_markdown_fence(text: str) -> str:
    s = text.strip()
    m = re.match(r"^```[a-zA-Z0-9_-]*\s*\n(.*)\n```\s*$", s, re.S)
    if m:
        return m.group(1).strip()
    return s


def extract_first_json(text: str) -> Any:
    """Robustly parse the first JSON object/array from model output."""
    s = strip_markdown_fence(text)
    dec = json.JSONDecoder()
    for idx, ch in enumerate(s):
        if ch in "{[":
            try:
                obj, _ = dec.raw_decode(s[idx:])
                return obj
            except json.JSONDecodeError:
                continue
    raise ValueError(f"No valid JSON object found in text ({len(text)} chars): {text[:300]!r}")


TEXT_WRAPPER_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "content": {
            "type": "string",
            "description": "完整的输出正文（严禁调用任何读写文件或终端工具，直接在此字段输出全部文本）",
        }
    },
    "required": ["content"],
    "additionalProperties": False,
}


def call_agy(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    effort: str = DEFAULT_EFFORT,
    schema: Optional[Dict[str, Any]] = None,
    timeout: int = 600,
    retries: int = 3,
    validator: Optional[Callable[[str], bool]] = None,
    out_path: Optional[Path] = None,
) -> str:
    """Invoke isolated agy sub-agent single-turn via stdin inside an empty temporary directory.

    Always enforces `--json-schema` (wrapping free-form text in `TEXT_WRAPPER_SCHEMA` when `schema is None`)
    so the sub-agent finishes in `num_turns == 1` via structured output and NEVER hangs trying to call `write_file`.
    """
    use_wrapper = schema is None
    effective_schema = TEXT_WRAPPER_SCHEMA if use_wrapper else schema
    effective_prompt = (
        prompt
        + "\n\n【系统执行约束：严禁调用任何文件读写或终端工具！请直接将完整结果填入 JSON 的 `content` 字段一次性返回。】"
        if use_wrapper
        else prompt
        + "\n\n【系统执行约束：严禁调用任何文件读写或终端工具！请直接按 JSON Schema 一次性返回结构化结果。】"
    )
    last_err = ""
    for attempt in range(1, retries + 2):
        with tempfile.TemporaryDirectory(prefix="train-agy-") as cwd:
            sp = Path(cwd) / "schema.json"
            sp.write_text(json.dumps(effective_schema, ensure_ascii=False), encoding="utf-8")
            cmd = [
                AGY_BIN,
                "--model", model,
                "--effort", effort,
                "--sandbox",
                "--disable-slash-commands",
                "--output-format", "json",
                "--input-format", "text",
                "--json-schema", str(sp),
            ]
            try:
                proc = subprocess.run(
                    cmd,
                    cwd=cwd,
                    input=effective_prompt,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
            except subprocess.TimeoutExpired:
                last_err = f"agy timeout after {timeout}s (attempt {attempt})"
                time.sleep(2 * attempt)
                continue

        if proc.returncode != 0:
            last_err = (
                f"agy exit {proc.returncode} (attempt {attempt}): "
                f"{(proc.stderr or proc.stdout)[-800:]}"
            )
            time.sleep(2 * attempt)
            continue

        envelope = None
        try:
            envelope = json.loads(proc.stdout)
        except ValueError:
            envelope = None

        raw_resp: Any = None
        if isinstance(envelope, dict):
            raw_resp = envelope.get("response")
            status = envelope.get("status")
            if raw_resp is None or (isinstance(raw_resp, str) and not raw_resp.strip()):
                last_err = f"agy empty response (status={status}, err={envelope.get('error')})"
                time.sleep(2 * attempt)
                continue
        else:
            raw_resp = proc.stdout or ""

        try:
            parsed_obj = raw_resp if isinstance(raw_resp, dict) else extract_first_json(str(raw_resp))
        except ValueError as exc:
            last_err = f"agy invalid JSON against schema (attempt {attempt}): {exc}"
            time.sleep(2 * attempt)
            continue

        if use_wrapper:
            text = strip_markdown_fence(str(parsed_obj.get("content") or ""))
        else:
            text = json.dumps(parsed_obj, ensure_ascii=False)

        if not text.strip():
            last_err = f"agy empty stripped text (attempt {attempt})"
            time.sleep(2 * attempt)
            continue

        if validator is not None and not validator(text):
            last_err = f"agy failed custom validator (attempt {attempt}, len={len(text)})"
            time.sleep(2 * attempt)
            continue

        if out_path is not None:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = out_path.with_name(out_path.name + ".tmp")
            tmp.write_text(text + "\n", encoding="utf-8")
            tmp.replace(out_path)
        return text

    raise LLMError(last_err or "agy call failed")


def call_agy_json(
    prompt: str,
    schema: Dict[str, Any],
    *,
    model: str = JUDGE_MODEL,
    effort: str = JUDGE_EFFORT,
    timeout: int = 900,
    retries: int = 3,
    out_path: Optional[Path] = None,
) -> Dict[str, Any]:
    text = call_agy(
        prompt,
        model=model,
        effort=effort,
        schema=schema,
        timeout=timeout,
        retries=retries,
        out_path=out_path,
    )
    obj = extract_first_json(text)
    if not isinstance(obj, dict):
        raise LLMError(f"Expected JSON object from agy, got {type(obj)}")
    return obj


# Backwards-compatible aliases routed 100% to `agy` (`gemini-4-carbon-medium`), zero `codex`!
def call_codex(
    prompt: str,
    *,
    model: str = JUDGE_MODEL,
    effort: str = JUDGE_EFFORT,
    schema: Optional[Dict[str, Any]] = None,
    timeout: int = 900,
    retries: int = 3,
    validator: Optional[Callable[[str], bool]] = None,
    out_path: Optional[Path] = None,
) -> str:
    actual_model = JUDGE_MODEL if ("gpt" in model or "codex" in model or not model) else model
    return call_agy(
        prompt,
        model=actual_model,
        effort=effort,
        schema=schema,
        timeout=timeout,
        retries=retries,
        validator=validator,
        out_path=out_path,
    )


def call_codex_json(
    prompt: str,
    schema: Dict[str, Any],
    *,
    model: str = JUDGE_MODEL,
    effort: str = JUDGE_EFFORT,
    timeout: int = 900,
    retries: int = 3,
    out_path: Optional[Path] = None,
) -> Dict[str, Any]:
    actual_model = JUDGE_MODEL if ("gpt" in model or "codex" in model or not model) else model
    return call_agy_json(
        prompt,
        schema,
        model=actual_model,
        effort=effort,
        timeout=timeout,
        retries=retries,
        out_path=out_path,
    )


if __name__ == "__main__":
    print(f"Testing agy ({DEFAULT_MODEL} / {DEFAULT_EFFORT})...")
    r_agy = call_agy("只回复两个字：就绪", timeout=120)
    print("agy response:", repr(r_agy))
