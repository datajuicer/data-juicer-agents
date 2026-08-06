# -*- coding: utf-8 -*-
"""Debug helpers for context/token evaluation."""

from __future__ import annotations

import asyncio
import json
import os
import urllib.request
from pathlib import Path
from typing import Any, Dict

from data_juicer_agents.adapters.agentscope import compact_payload_for_model

# Reference context windows used for percentage reporting.
_WINDOW_30K = 30000
_WINDOW_50K = 50000

_DEFAULT_QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
_QWEN_PROBE_SYSTEM_PROMPT = "You only estimate and summarize tool results."


def _success_payload(*, action: str, **data: Any) -> Dict[str, Any]:
    payload = {"ok": True, "action": action}
    payload.update(data)
    return payload


def _error_payload(
    *, action: str, message: str, error_type: str, **data: Any
) -> Dict[str, Any]:
    payload = {
        "ok": False,
        "action": action,
        "error_type": error_type,
        "message": str(message),
    }
    payload.update(data)
    return payload


def _emit_json(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _json_text(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)


def _load_payload(args: Any) -> Dict[str, Any]:
    raw_json = getattr(args, "input_json", None)
    input_file = getattr(args, "input_file", None)
    if raw_json is not None:
        source = str(raw_json)
    else:
        source = Path(str(input_file)).expanduser().read_text(encoding="utf-8")
    payload = json.loads(source)
    if not isinstance(payload, dict):
        raise ValueError("debug token-usage input must decode to a JSON object")
    return payload


async def _char_token_count(text: str) -> int:
    from agentscope.token import CharTokenCounter

    value = await CharTokenCounter().count(text)
    if isinstance(value, tuple):
        return int(value[0])
    return int(value)


def _resolve_qwen_model(args: Any) -> str:
    return str(
        getattr(args, "model", None)
        or os.environ.get("DJA_SESSION_MODEL")
        or "qwen-plus"
    )


def _qwen_prompt_tokens(label: str, payload: Dict[str, Any], args: Any) -> int:
    api_key = os.environ.get("DASHSCOPE_API_KEY") or os.environ.get(
        "MODELSCOPE_API_TOKEN"
    )
    if not api_key:
        raise RuntimeError(
            "DASHSCOPE_API_KEY or MODELSCOPE_API_TOKEN is required"
            " for provider=qwen"
        )
    base_url = str(
        getattr(args, "base_url", None)
        or os.environ.get("DJA_OPENAI_BASE_URL")
        or _DEFAULT_QWEN_BASE_URL
    ).rstrip("/")
    body = {
        "model": _resolve_qwen_model(args),
        "messages": [
            {"role": "system", "content": _QWEN_PROBE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Summarize this {label} tool result in one short sentence:\n"
                    f"{_json_text(payload)}"
                ),
            },
        ],
        "max_tokens": max(int(getattr(args, "max_tokens", 1) or 1), 1),
        "temperature": 0,
    }
    request = urllib.request.Request(
        base_url + "/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    timeout = int(getattr(args, "timeout", 120) or 120)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    usage = data.get("usage") or {}
    prompt_tokens = usage.get("prompt_tokens")
    if prompt_tokens is None:
        raise RuntimeError("qwen response did not include usage.prompt_tokens")
    return int(prompt_tokens)


async def _measure_char(
    tool_name: str,
    full_payload: Dict[str, Any],
    compact_payload: Dict[str, Any],
) -> Dict[str, Any]:
    full_text = _json_text(full_payload)
    compact_text = _json_text(compact_payload)
    full_tokens = await _char_token_count(full_text)
    compact_tokens = await _char_token_count(compact_text)
    return _usage_payload(
        provider="char",
        full_tokens=full_tokens,
        compact_tokens=compact_tokens,
        full_chars=len(full_text),
        compact_chars=len(compact_text),
        tool_name=tool_name,
        model=None,
    )


def _measure_qwen(
    tool_name: str,
    full_payload: Dict[str, Any],
    compact_payload: Dict[str, Any],
    args: Any,
) -> Dict[str, Any]:
    full_tokens = _qwen_prompt_tokens(tool_name + " full", full_payload, args)
    compact_tokens = _qwen_prompt_tokens(tool_name + " compact", compact_payload, args)
    return _usage_payload(
        provider="qwen",
        full_tokens=full_tokens,
        compact_tokens=compact_tokens,
        full_chars=len(_json_text(full_payload)),
        compact_chars=len(_json_text(compact_payload)),
        tool_name=tool_name,
        model=_resolve_qwen_model(args),
    )


def _usage_payload(
    *,
    provider: str,
    full_tokens: int,
    compact_tokens: int,
    full_chars: int,
    compact_chars: int,
    tool_name: str,
    model: str | None,
) -> Dict[str, Any]:
    saved_tokens = max(full_tokens - compact_tokens, 0)
    saved_pct = round(saved_tokens / full_tokens * 100, 2) if full_tokens else 0.0
    return _success_payload(
        action="debug_token_usage",
        provider=provider,
        tool_name=tool_name,
        model=model,
        full_chars=full_chars,
        compact_chars=compact_chars,
        full_tokens=full_tokens,
        compact_tokens=compact_tokens,
        saved_tokens=saved_tokens,
        saved_pct=saved_pct,
        full_pct_30k=round(full_tokens / _WINDOW_30K * 100, 2),
        compact_pct_30k=round(compact_tokens / _WINDOW_30K * 100, 2),
        full_pct_50k=round(full_tokens / _WINDOW_50K * 100, 2),
        compact_pct_50k=round(compact_tokens / _WINDOW_50K * 100, 2),
        compaction_enabled_env=os.environ.get(
            "DJA_TOOL_RESULT_COMPACTION_ENABLED", "true"
        ),
    )


def _execute_token_usage(args: Any) -> tuple[Dict[str, Any], int]:
    tool_name = str(getattr(args, "tool_name", "") or "").strip()
    try:
        payload = _load_payload(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return (
            _error_payload(
                action="debug_token_usage",
                message=str(exc),
                error_type="invalid_input",
            ),
            2,
        )

    compact = compact_payload_for_model(tool_name, payload)
    provider = str(getattr(args, "provider", "char") or "char").strip().lower()
    try:
        if provider == "char":
            result = asyncio.run(_measure_char(tool_name, payload, compact))
        elif provider == "qwen":
            result = _measure_qwen(tool_name, payload, compact, args)
        else:
            return (
                _error_payload(
                    action="debug_token_usage",
                    message=f"unsupported token usage provider: {provider}",
                    error_type="unsupported_provider",
                ),
                2,
            )
    except Exception as exc:  # debug command must surface failures as JSON
        return (
            _error_payload(
                action="debug_token_usage",
                message=str(exc),
                error_type="token_usage_failed",
                provider=provider,
            ),
            4,
        )
    return result, 0


def run_debug(args: Any) -> int:
    action = str(getattr(args, "debug_action", "") or "").strip()
    if action == "token-usage":
        payload, code = _execute_token_usage(args)
    else:
        payload = _error_payload(
            action="debug",
            message=f"unsupported debug action: {action}",
            error_type="unsupported_action",
        )
        code = 2
    _emit_json(payload)
    return int(code)


__all__ = ["run_debug"]
