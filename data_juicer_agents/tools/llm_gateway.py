# -*- coding: utf-8 -*-
"""Utilities for calling LLMs via OpenAI-compatible endpoints."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
_DEFAULT_THINKING = "true"


def _extract_json_text(text: str) -> str:
    match = _JSON_BLOCK_RE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


def _call_model_json_once(
    model_name: str,
    prompt: str,
    api_key: str | None = None,
    base_url: str | None = None,
    thinking: bool | None = None,
) -> Dict[str, Any]:
    from openai import OpenAI

    api_key = (
        str(api_key).strip()
        if api_key is not None
        else (os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("MODELSCOPE_API_TOKEN"))
    )
    if not api_key:
        raise RuntimeError("Missing API key: set DASHSCOPE_API_KEY or MODELSCOPE_API_TOKEN")

    if base_url is None:
        base_url = os.environ.get("DJA_OPENAI_BASE_URL", _DEFAULT_BASE_URL)
    if thinking is None:
        thinking_flag = os.environ.get("DJA_LLM_THINKING", _DEFAULT_THINKING).lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
    else:
        thinking_flag = bool(thinking)

    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model_name,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        extra_body={"enable_thinking": thinking_flag},
    )

    text = response.choices[0].message.content or ""
    payload = _extract_json_text(text)
    return json.loads(payload)


def _candidate_models(model_name: str) -> List[str]:
    configured = os.environ.get("DJA_MODEL_FALLBACKS", "")
    extras = [item.strip() for item in configured.split(",") if item.strip()]

    seen = {model_name}
    ordered = [model_name]
    for item in extras:
        if item not in seen:
            ordered.append(item)
            seen.add(item)
    return ordered


def call_model_json(
    model_name: str,
    prompt: str,
    api_key: str | None = None,
    base_url: str | None = None,
    thinking: bool | None = None,
) -> Dict[str, Any]:
    errors: List[str] = []

    for candidate in _candidate_models(model_name):
        try:
            return _call_model_json_once(
                candidate,
                prompt,
                api_key=api_key,
                base_url=base_url,
                thinking=thinking,
            )
        except Exception as exc:  # pragma: no cover - exercised via tests with monkeypatch
            errors.append(f"{candidate}: {exc}")

    joined = "; ".join(errors)
    raise RuntimeError(f"LLM call failed for all candidate models: {joined}")
