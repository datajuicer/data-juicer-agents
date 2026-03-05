# -*- coding: utf-8 -*-
"""Structured operator retrieval service for DJX."""

from __future__ import annotations

import asyncio
import os
import re
import threading
from typing import Any, Dict, Iterable, List, Tuple

from data_juicer_agents.tools.dataset_probe import inspect_dataset_schema
from data_juicer_agents.tools.op_manager.operator_registry import (
    get_available_operator_names,
    resolve_operator_name,
)


_WORD_RE = re.compile(r"[a-zA-Z0-9_]+")
_OP_TYPES = {
    "mapper",
    "filter",
    "deduplicator",
    "selector",
    "grouper",
    "aggregator",
    "pipeline",
    "formatter",
}


def _load_op_retrieval_funcs():
    try:
        from data_juicer_agents.tools.op_manager.op_retrieval import (
            get_dj_func_info,
            init_dj_func_info,
            retrieve_ops,
        )

        return get_dj_func_info, init_dj_func_info, retrieve_ops
    except Exception:
        return None


def _tokenize(text: str) -> List[str]:
    return [token.lower() for token in _WORD_RE.findall(str(text or ""))]


def _op_type(name: str) -> str:
    parts = str(name or "").split("_")
    if not parts:
        return "unknown"
    maybe = parts[-1].lower()
    if maybe in _OP_TYPES:
        return maybe
    if "dedup" in str(name or "").lower():
        return "deduplicator"
    return "unknown"


def _to_float_score(value: float) -> float:
    if value < 0:
        return 0.0
    if value > 100:
        return 100.0
    return round(value, 2)


def _keyword_score(intent: str, operator_name: str, description: str) -> float:
    intent_tokens = set(_tokenize(intent))
    if not intent_tokens:
        return 0.0

    name_tokens = set(_tokenize(operator_name))
    desc_tokens = set(_tokenize(description))

    name_overlap = len(intent_tokens.intersection(name_tokens))
    desc_overlap = len(intent_tokens.intersection(desc_tokens))
    contains_bonus = 1.0 if any(tok in operator_name.lower() for tok in intent_tokens) else 0.0

    # Weighted to prefer exact-ish operator name matches.
    raw = name_overlap * 16.0 + desc_overlap * 4.0 + contains_bonus * 8.0
    return _to_float_score(raw)


def _safe_async_retrieve(intent: str, top_k: int, mode: str) -> Tuple[List[str], str]:
    api_key = os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("MODELSCOPE_API_TOKEN")
    if not api_key:
        return [], "lexical"

    funcs = _load_op_retrieval_funcs()
    if funcs is None:
        return [], "lexical"
    _, _, retrieve_ops = funcs

    def _normalize_names(names: Any) -> List[str]:
        if not isinstance(names, list):
            return []
        return [str(item) for item in names if str(item).strip()]

    def _run_in_new_thread() -> List[str]:
        payload: Dict[str, Any] = {}

        def _worker() -> None:
            loop = asyncio.new_event_loop()
            try:
                payload["names"] = loop.run_until_complete(
                    retrieve_ops(intent, limit=top_k, mode=mode)
                )
            except Exception as exc:
                payload["error"] = exc
            finally:
                loop.close()

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        thread.join()
        if "error" in payload:
            raise payload["error"]
        return _normalize_names(payload.get("names"))

    try:
        asyncio.get_running_loop()
        names = _run_in_new_thread()
        if names:
            return names, mode
    except RuntimeError:
        names = _normalize_names(
            asyncio.run(retrieve_ops(intent, limit=top_k, mode=mode))
        )
        if names:
            return names, mode
    except Exception:
        pass
    return [], "fallback"


def _lexical_fallback(intent: str, info_rows: List[Dict[str, Any]], top_k: int) -> List[str]:
    scored: List[Tuple[float, str]] = []
    for row in info_rows:
        name = str(row.get("class_name", "")).strip()
        if not name:
            continue
        score = _keyword_score(intent, name, str(row.get("class_desc", "")))
        scored.append((score, name))

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    selected = [name for score, name in scored if score > 0][:top_k]
    if selected:
        return selected
    # If no keyword overlap, still provide deterministic top-k list.
    return [name for _, name in scored[:top_k]]


def _build_candidate_row(
    rank: int,
    name: str,
    intent: str,
    info_map: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    row = info_map.get(name, {})
    desc = str(row.get("class_desc", "")).strip()
    args_text = str(row.get("arguments", "")).strip()
    args_lines = [line.strip() for line in args_text.splitlines() if line.strip()]
    return {
        "rank": rank,
        "operator_name": name,
        "operator_type": _op_type(name),
        "description": desc,
        "relevance_score": _keyword_score(intent, name, desc),
        "arguments_preview": args_lines[:4],
    }


def retrieve_operator_candidates(
    intent: str,
    top_k: int = 10,
    mode: str = "auto",
    dataset_path: str | None = None,
) -> Dict[str, Any]:
    """Retrieve operators and return a structured payload for CLI/agent usage."""

    top_k = int(top_k) if isinstance(top_k, int) or str(top_k).isdigit() else 10
    if top_k <= 0:
        top_k = 10
    top_k = min(top_k, 200)

    info_rows: List[Dict[str, Any]] = []
    funcs = _load_op_retrieval_funcs()
    if funcs is not None:
        get_dj_func_info, init_dj_func_info, _retrieve_ops = funcs
        try:
            init_dj_func_info()
            info_rows = [
                item
                for item in get_dj_func_info()
                if isinstance(item, dict) and str(item.get("class_name", "")).strip()
            ]
        except Exception:
            info_rows = []

    info_map = {
        str(item.get("class_name", "")).strip(): item for item in info_rows
    }

    retrieved_names, retrieval_source = _safe_async_retrieve(intent, top_k=top_k, mode=mode)
    if not retrieved_names:
        retrieved_names = _lexical_fallback(intent, info_rows=info_rows, top_k=top_k)

    available_ops = get_available_operator_names()
    normalized_names: List[str] = []
    seen = set()
    for raw_name in retrieved_names:
        name = resolve_operator_name(raw_name, available_ops=available_ops)
        if name and name not in seen:
            seen.add(name)
            normalized_names.append(name)

    if not normalized_names and info_rows:
        normalized_names = _lexical_fallback(intent, info_rows=info_rows, top_k=top_k)

    candidates = [
        _build_candidate_row(idx, name, intent=intent, info_map=info_map)
        for idx, name in enumerate(normalized_names[:top_k], start=1)
    ]

    dataset_profile = None
    if dataset_path:
        dataset_profile = inspect_dataset_schema(dataset_path, sample_size=20)

    notes: List[str] = []
    if not candidates:
        notes.append("No operator candidates were found from retrieval.")
    if dataset_profile and isinstance(dataset_profile, dict) and dataset_profile.get("ok"):
        modality = str(dataset_profile.get("modality", "unknown"))
        notes.append(f"Detected dataset modality: {modality}")
    elif dataset_profile and isinstance(dataset_profile, dict):
        notes.append(str(dataset_profile.get("error", "dataset probe failed")))

    return {
        "ok": True,
        "intent": intent,
        "top_k": top_k,
        "mode": mode,
        "retrieval_source": retrieval_source,
        "candidate_count": len(candidates),
        "gap_detected": len(candidates) == 0,
        "candidates": candidates,
        "dataset_profile": dataset_profile,
        "notes": notes,
    }


def extract_candidate_names(payload: Dict[str, Any]) -> List[str]:
    names: List[str] = []
    for item in payload.get("candidates", []) if isinstance(payload, dict) else []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("operator_name", "")).strip()
        if name:
            names.append(name)
    return names
