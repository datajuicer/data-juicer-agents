# -*- coding: utf-8 -*-
"""Structured operator retrieval service for DJX."""

from __future__ import annotations

import asyncio
import os
import re
import threading
from typing import Any, Dict, Iterable, List

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
            retrieve_ops_with_meta,
        )

        return get_dj_func_info, init_dj_func_info, retrieve_ops, retrieve_ops_with_meta
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


def _trace_entry(backend: str, status: str, error: str = "", reason: str = "") -> Dict[str, str]:
    payload = {
        "backend": str(backend or "").strip(),
        "status": str(status or "").strip(),
    }
    error_text = str(error or "").strip()
    reason_text = str(reason or "").strip()
    if error_text:
        payload["error"] = error_text
    if reason_text:
        payload["reason"] = reason_text
    return payload


def _safe_async_retrieve(intent: str, top_k: int, mode: str) -> Dict[str, Any]:
    api_key = os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("MODELSCOPE_API_TOKEN")
    if not api_key:
        return {
            "names": [],
            "source": "lexical",
            "trace": [_trace_entry("lexical", "selected", reason="missing_api_key")],
        }

    funcs = _load_op_retrieval_funcs()
    if funcs is None:
        return {
            "names": [],
            "source": "lexical",
            "trace": [_trace_entry("lexical", "selected", reason="retrieval_backend_unavailable")],
        }
    _, _, retrieve_ops, retrieve_ops_with_meta = funcs

    def _normalize_names(names: Any) -> List[str]:
        if not isinstance(names, list):
            return []
        return [str(item) for item in names if str(item).strip()]

    def _normalize_meta(payload: Any) -> Dict[str, Any]:
        if isinstance(payload, dict):
            return {
                "names": _normalize_names(payload.get("names")),
                "source": str(payload.get("source", "")).strip(),
                "trace": list(payload.get("trace", [])) if isinstance(payload.get("trace"), list) else [],
                "items": list(payload.get("items", [])) if isinstance(payload.get("items"), list) else [],
            }
        return {
            "names": _normalize_names(payload),
            "source": "",
            "trace": [],
            "items": [],
        }

    def _run_in_new_thread() -> Dict[str, Any]:
        payload: Dict[str, Any] = {}

        def _worker() -> None:
            loop = asyncio.new_event_loop()
            try:
                payload["meta"] = loop.run_until_complete(
                    retrieve_ops_with_meta(intent, limit=top_k, mode=mode)
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
        return _normalize_meta(payload.get("meta"))

    try:
        asyncio.get_running_loop()
        meta = _run_in_new_thread()
        if meta.get("names"):
            return meta
        return meta
    except RuntimeError:
        meta = _normalize_meta(
            asyncio.run(retrieve_ops_with_meta(intent, limit=top_k, mode=mode))
        )
        if meta.get("names"):
            return meta
        return meta
    except Exception as exc:
        return {
            "names": [],
            "source": "",
            "trace": [_trace_entry(mode, "failed", str(exc))],
            "items": [],
        }


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
    llm_item: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    row = info_map.get(name, {})
    desc = str(row.get("class_desc", "")).strip()
    args_text = str(row.get("arguments", "")).strip()
    args_lines = [line.strip() for line in args_text.splitlines() if line.strip()]
    llm_desc = str((llm_item or {}).get("description", "")).strip()
    llm_score = (llm_item or {}).get("relevance_score")
    key_match = (llm_item or {}).get("key_match")
    if not isinstance(key_match, list):
        key_match = []
    if isinstance(llm_score, (int, float)):
        relevance_score = _to_float_score(float(llm_score))
        score_source = "llm"
    else:
        relevance_score = _keyword_score(intent, name, desc)
        score_source = "keyword"
    return {
        "rank": rank,
        "operator_name": name,
        "operator_type": _op_type(name),
        "description": llm_desc or desc,
        "relevance_score": relevance_score,
        "score_source": score_source,
        "key_match": [str(item).strip() for item in key_match if str(item).strip()],
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
        get_dj_func_info, init_dj_func_info, _retrieve_ops, _retrieve_ops_with_meta = funcs
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

    retrieve_meta = _safe_async_retrieve(intent, top_k=top_k, mode=mode)
    retrieved_names = list(retrieve_meta.get("names", []))
    retrieval_source = str(retrieve_meta.get("source", "")).strip()
    retrieval_trace = list(retrieve_meta.get("trace", []))
    llm_item_map = {}
    if retrieval_source == "llm":
        for item in retrieve_meta.get("items", []):
            if not isinstance(item, dict):
                continue
            tool_name = str(item.get("tool_name", "")).strip()
            if tool_name:
                llm_item_map[tool_name] = item
    if not retrieved_names:
        retrieved_names = _lexical_fallback(intent, info_rows=info_rows, top_k=top_k)
        retrieval_source = "lexical"
        retrieval_trace.append(_trace_entry("lexical", "selected", reason="fallback_after_remote_empty_or_failed"))

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
        _build_candidate_row(
            idx,
            name,
            intent=intent,
            info_map=info_map,
            llm_item=llm_item_map.get(name),
        )
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
        "retrieval_trace": retrieval_trace,
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
