# -*- coding: utf-8 -*-
"""Fixed-batch multi-turn A/B experiment for context-management evaluation.

Runs the SAME 9-turn conversation under two runtime configurations
(arm controlled by --arm):
  - before: simulates the pre-optimization runtime (no tool-result compaction,
    no memory compression, 200k window)
  - after:  optimized runtime (tool-result compaction + memory compression +
    formatter budget @ 30k window)

Collects per-turn real ``usage.prompt_tokens`` / ``completion_tokens`` from the
model endpoint, the tool-call sequence, reply text, and memory/snapshot
indicators. Writes JSON to ``benchmarks/out/multiturn_ab_<arm>.json``.

Requires an OpenAI-compatible endpoint configured via the repo-root ``.env``
(same variables as the normal ``djx`` CLI). Token-level payload savings can be
measured offline without any endpoint via
``djx debug token-usage <tool> --provider char``.

Usage::

    uv run python benchmarks/multiturn_ab.py --arm before
    uv run python benchmarks/multiturn_ab.py --arm after
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # repository root
DATASET = str(ROOT / "data" / "demo-dataset.jsonl")

TURNS = [
    ("T1_inspect", "请检查数据集 data/demo-dataset.jsonl 的结构，告诉我它有哪些字段、大约多少条记录。"),
    ("T2_retrieve", "帮我检索适合按文本长度过滤的 Data-Juicer 算子。"),
    ("T3_opinfo", "告诉我 text_length_filter 算子的参数定义和默认值。"),
    ("T4_plan", "请为这个数据集生成一个最小文本清洗计划：使用 text_length_filter，基于 text 字段，只生成计划，不要执行 apply_recipe。"),
    ("T5_validate", "请校验刚才生成的计划是否合法。"),
    ("T6_save", "请把校验通过的计划保存为 yaml 文件。"),
    ("T7_recall_threshold", "我们刚才计划里 text_length_filter 使用的最小/最大长度阈值分别是多少？"),
    ("T8_recall_path", "计划保存到了哪个文件路径？数据集路径是什么？"),
    ("T9_view", "请查看保存的计划文件内容并确认 process 里包含 text_length_filter。"),
]

ARM_ENV = {
    "before": {
        "DJA_CONTEXT_WINDOW_TOKENS": "200000",
        "DJA_CONTEXT_COMPRESSION_ENABLED": "false",
        "DJA_TOOL_RESULT_COMPACTION_ENABLED": "false",
        "DJA_CONTEXT_TRIGGER_RATIO": "0.9",
        "DJA_CONTEXT_FORMATTER_RATIO": "0.95",
        "DJA_CONTEXT_KEEP_RECENT": "10",
    },
    "after": {
        "DJA_CONTEXT_WINDOW_TOKENS": "30000",
        "DJA_CONTEXT_COMPRESSION_ENABLED": "true",
        "DJA_TOOL_RESULT_COMPACTION_ENABLED": "true",
        "DJA_CONTEXT_TRIGGER_RATIO": "0.65",
        "DJA_CONTEXT_FORMATTER_RATIO": "0.85",
        "DJA_CONTEXT_KEEP_RECENT": "10",
    },
}


def _usage_field(usage: object, name: str) -> int:
    if usage is None:
        return 0
    try:
        if isinstance(usage, dict):
            value = usage.get(name)
        else:
            value = getattr(usage, name, None)
    except (KeyError, AttributeError):
        value = None
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def load_dotenv_file() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


class _UsageTrackingModelProxy:
    """Proxy around the real model so __call__ interception works."""

    def __init__(self, model: object, calls: list) -> None:
        object.__setattr__(self, "_model", model)
        object.__setattr__(self, "_calls", calls)

    async def __call__(self, *args, **kwargs):
        response = await self._model(*args, **kwargs)
        usage = getattr(response, "usage", None)
        prompt = _usage_field(usage, "prompt_tokens") or _usage_field(
            usage, "input_tokens"
        )
        completion = _usage_field(usage, "completion_tokens") or _usage_field(
            usage, "output_tokens"
        )
        self._calls.append(
            {
                "prompt_tokens": prompt,
                "completion_tokens": completion,
                "total_tokens": _usage_field(usage, "total_tokens")
                or (prompt + completion),
            }
        )
        return response

    def __getattr__(self, item):
        return getattr(object.__getattribute__(self, "_model"), item)


def patch_model_usage(react_agent, calls: list) -> None:
    proxy = _UsageTrackingModelProxy(react_agent.model, calls)
    react_agent.model = proxy


def patch_toolkit_calls(toolkit: object, calls: list) -> None:
    original_call = toolkit.call_tool_function

    def _tool_name(tool_call) -> str:
        name = getattr(tool_call, "name", None)
        if name is None and isinstance(tool_call, dict):
            name = tool_call.get("name")
        return str(name or tool_call)

    def tracked_call(tool_call, **kwargs):
        calls.append(_tool_name(tool_call))
        return original_call(tool_call, **kwargs)

    toolkit.call_tool_function = tracked_call


async def run_arm(arm: str) -> dict:
    load_dotenv_file()
    for key, value in ARM_ENV[arm].items():
        os.environ[key] = value

    from data_juicer_agents.capabilities.session.orchestrator import DJSessionAgent

    out_dir = ROOT / "benchmarks" / "out" / f"multiturn_ab_{arm}"
    out_dir.mkdir(parents=True, exist_ok=True)

    agent = DJSessionAgent(
        use_llm_router=True,
        dataset_path=DATASET,
        working_dir=str(out_dir),
        verbose=False,
    )

    react = agent._react_agent
    model_calls: list = []
    patch_model_usage(react, model_calls)
    tool_calls: list = []
    patch_toolkit_calls(react.toolkit, tool_calls)

    result = {
        "arm": arm,
        "env": dict(ARM_ENV[arm]),
        "model": os.environ.get("DJA_SESSION_MODEL", ""),
        "dataset": DATASET,
        "turns": [],
        "totals": {},
    }

    for idx, (label, user_text) in enumerate(TURNS, start=1):
        call_start = len(model_calls)
        tool_start = len(tool_calls)
        reply = await agent.handle_message_async(user_text)
        turn_model_calls = model_calls[call_start:]
        turn_tools = tool_calls[tool_start:]

        memory_metrics = await _memory_metrics(react)

        turn_record = {
            "idx": idx,
            "label": label,
            "user": user_text,
            "reply": reply.text,
            "stop": reply.stop,
            "interrupted": reply.interrupted,
            "llm_calls": len(turn_model_calls),
            "prompt_tokens": sum(c["prompt_tokens"] for c in turn_model_calls),
            "completion_tokens": sum(c["completion_tokens"] for c in turn_model_calls),
            "tool_calls": turn_tools,
            "memory": memory_metrics,
        }
        result["turns"].append(turn_record)
        print(
            f"[{arm}] {label}: llm_calls={turn_record['llm_calls']} "
            f"prompt_tokens={turn_record['prompt_tokens']} tools={turn_tools} "
            f"visible={memory_metrics.get('visible_message_count')} "
            f"summary={memory_metrics.get('has_compressed_summary')}",
            flush=True,
        )

    result["totals"] = {
        "prompt_tokens": sum(t["prompt_tokens"] for t in result["turns"]),
        "completion_tokens": sum(t["completion_tokens"] for t in result["turns"]),
        "llm_calls": sum(t["llm_calls"] for t in result["turns"]),
        "tool_calls": sum(len(t["tool_calls"]) for t in result["turns"]),
        "max_turn_prompt_tokens": max(
            (t["prompt_tokens"] for t in result["turns"]), default=0
        ),
    }

    out_path = ROOT / "benchmarks" / "out" / f"multiturn_ab_{arm}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[{arm}] saved -> {out_path}", flush=True)
    return result


async def _memory_metrics(react) -> dict:
    memory = getattr(react, "memory", None)
    metrics = {
        "memory_message_count": None,
        "visible_message_count": None,
        "has_compressed_summary": False,
        "memory_chars": 0,
    }
    if memory is None:
        return metrics
    try:
        visible = await memory.get_memory()
        metrics["visible_message_count"] = len(visible)
        metrics["memory_chars"] = sum(
            len(str(getattr(m, "content", "") or "")) for m in visible
        )
    except Exception as exc:  # pragma: no cover
        metrics["visible_error"] = str(exc)
    try:
        raw_state = memory.state_dict()
        msgs = raw_state.get("memory", raw_state.get("messages", [])) or []
        metrics["memory_message_count"] = len(msgs)
    except Exception as exc:  # pragma: no cover
        metrics["state_error"] = str(exc)
    metrics["has_compressed_summary"] = bool(
        getattr(memory, "_compressed_summary", "") or ""
    )
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", required=True, choices=["before", "after"])
    args = parser.parse_args()
    asyncio.run(run_arm(args.arm))
    return 0


if __name__ == "__main__":
    sys.exit(main())
