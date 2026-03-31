# -*- coding: utf-8 -*-
"""Structured operator retrieval service for DJX and session tools."""

from __future__ import annotations

import asyncio
import re
import threading
from typing import Any, Dict, List

from .operator_registry import (
    get_available_operator_names,
    resolve_operator_name,
)
from .backend.result_builder import trace_step

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
        from .backend import (
            get_op_catalog,
            init_op_catalog,
            retrieve_ops,
            retrieve_ops_with_meta,
        )

        return get_op_catalog, init_op_catalog, retrieve_ops, retrieve_ops_with_meta
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
    contains_bonus = (
        1.0 if any(tok in operator_name.lower() for tok in intent_tokens) else 0.0
    )

    # Weighted to prefer exact-ish operator name matches.
    raw = name_overlap * 16.0 + desc_overlap * 4.0 + contains_bonus * 8.0
    return _to_float_score(raw)


def _safe_async_retrieve(
    intent: str,
    top_k: int,
    mode: str,
    op_type: str | None = None,
    tags: list | None = None,
) -> Dict[str, Any]:
    funcs = _load_op_retrieval_funcs()
    if funcs is None:
        return {
            "names": [],
            "source": "lexical",
            "trace": [
                trace_step(
                    "lexical", "selected", reason="retrieval_backend_unavailable"
                )
            ],
        }
    _, _, _, retrieve_ops_with_meta = funcs

    def _normalize_names(names: Any) -> List[str]:
        if not isinstance(names, list):
            return []
        return [str(item) for item in names if str(item).strip()]

    def _normalize_meta(payload: Any) -> Dict[str, Any]:
        if isinstance(payload, dict):
            return {
                "names": _normalize_names(payload.get("names")),
                "source": str(payload.get("source", "")).strip(),
                "trace": (
                    list(payload.get("trace", []))
                    if isinstance(payload.get("trace"), list)
                    else []
                ),
                "items": (
                    list(payload.get("items", []))
                    if isinstance(payload.get("items"), list)
                    else []
                ),
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
                    retrieve_ops_with_meta(
                        intent, limit=top_k, mode=mode, op_type=op_type, tags=tags,
                    )
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
        return _run_in_new_thread()
    except RuntimeError:
        return _normalize_meta(
            asyncio.run(
                retrieve_ops_with_meta(intent, limit=top_k, mode=mode, op_type=op_type, tags=tags)
            )
        )
    except Exception as exc:
        return {
            "names": [],
            "source": "",
            "trace": [trace_step(mode, "failed", str(exc))],
            "items": [],
        }


def _lexical_fallback(
    intent: str, info_rows: List[Dict[str, Any]], top_k: int
) -> List[str]:
    scored: List[tuple[float, str]] = []
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
    retrieval_item: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    row = info_map.get(name, {})
    desc = str(row.get("class_desc", "")).strip()
    args_text = str(row.get("arguments", "")).strip()
    args_lines = [line.strip() for line in args_text.splitlines() if line.strip()]
    class_type = str(row.get("class_type", "")).strip()
    item_desc = str((retrieval_item or {}).get("description", "")).strip()
    item_score = (retrieval_item or {}).get("relevance_score")
    item_score_source = str((retrieval_item or {}).get("score_source", "")).strip()
    item_type = str((retrieval_item or {}).get("operator_type", "")).strip()
    key_match = (retrieval_item or {}).get("key_match")
    if not isinstance(key_match, list):
        key_match = []
    if isinstance(item_score, (int, float)):
        relevance_score = _to_float_score(float(item_score))
        score_source = item_score_source or "retrieval"
    else:
        relevance_score = _keyword_score(intent, name, desc)
        score_source = "keyword"
    return {
        "rank": rank,
        "operator_name": name,
        "operator_type": item_type or class_type or _op_type(name),
        "description": item_desc or desc,
        "relevance_score": relevance_score,
        "score_source": score_source,
        "key_match": [str(item).strip() for item in key_match if str(item).strip()],
        "arguments_preview": args_lines[:4],
    }


def retrieve_operator_candidates(
    intent: str,
    top_k: int = 10,
    mode: str = "auto",
    op_type: str | None = None,
    tags: list | None = None,
) -> Dict[str, Any]:
    """Retrieve operators and return a structured payload for CLI/agent usage.

    Args:
        intent: Natural-language description of the desired operators.
        top_k: Maximum number of candidates to return.
        mode: Retrieval backend mode ("llm", "vector", "bm25", "regex", or "auto").
        op_type: Optional operator type filter (e.g. "filter", "mapper",
                 "deduplicator"). Propagated to retrieval backends for early
                 filtering.
    """

    top_k = int(top_k) if isinstance(top_k, int) or str(top_k).isdigit() else 10
    if top_k <= 0:
        top_k = 10
    top_k = min(top_k, 200)

    info_rows: List[Dict[str, Any]] = []
    funcs = _load_op_retrieval_funcs()
    if funcs is not None:
        get_op_catalog, _init_op_catalog, _retrieve_ops, _retrieve_ops_with_meta = funcs
        try:
            # get_op_catalog() already handles lazy initialization internally;
            # calling init_op_catalog() here is redundant and causes a double
            # catalog load on every invocation.
            info_rows = [
                item
                for item in get_op_catalog()
                if isinstance(item, dict) and str(item.get("class_name", "")).strip()
            ]
        except Exception:
            info_rows = []

    info_map = {str(item.get("class_name", "")).strip(): item for item in info_rows}

    retrieve_meta = _safe_async_retrieve(
        intent, top_k=top_k, mode=mode, op_type=op_type, tags=tags
    )
    retrieved_names = list(retrieve_meta.get("names", []))
    retrieval_source = str(retrieve_meta.get("source", "")).strip()
    retrieval_trace = list(retrieve_meta.get("trace", []))
    retrieval_item_map = {}
    for item in retrieve_meta.get("items", []):
        if not isinstance(item, dict):
            continue
        tool_name = str(item.get("tool_name", "")).strip()
        if not tool_name:
            continue
        if retrieval_source and not str(item.get("score_source", "")).strip():
            item = dict(item)
            item["score_source"] = retrieval_source
        retrieval_item_map[tool_name] = item
    if not retrieved_names:
        retrieved_names = _lexical_fallback(intent, info_rows=info_rows, top_k=top_k)
        retrieval_source = "lexical"
        retrieval_trace.append(
            trace_step(
                "lexical", "selected", reason="fallback_after_remote_empty_or_failed"
            )
        )

    available_ops = get_available_operator_names()
    normalized_item_map: Dict[str, Dict[str, Any]] = {}
    for raw_name, item in retrieval_item_map.items():
        resolved = resolve_operator_name(raw_name, available_ops=available_ops)
        if resolved and resolved not in normalized_item_map:
            normalized_item_map[resolved] = item
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
            retrieval_item=normalized_item_map.get(name)
            or retrieval_item_map.get(name),
        )
        for idx, name in enumerate(normalized_names[:top_k], start=1)
    ]

    notes: List[str] = []
    if not candidates:
        notes.append("No operator candidates were found from retrieval.")

    result = {
        "ok": True,
        "intent": intent,
        "top_k": top_k,
        "mode": mode,
        "retrieval_source": retrieval_source,
        "retrieval_trace": retrieval_trace,
        "candidate_count": len(candidates),
        "gap_detected": len(candidates) == 0,
        "candidates": candidates,
        "notes": notes,
    }
    if op_type:
        result["op_type"] = op_type
    return result


def extract_candidate_names(payload: Dict[str, Any]) -> List[str]:
    names: List[str] = []
    for item in payload.get("candidates", []) if isinstance(payload, dict) else []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("operator_name", "")).strip()
        if name:
            names.append(name)
    return names
