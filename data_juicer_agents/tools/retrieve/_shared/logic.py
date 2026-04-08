# -*- coding: utf-8 -*-
"""Structured operator retrieval service for DJX and session tools."""

from __future__ import annotations

import asyncio
import inspect
import logging
import re
import threading
from typing import Any, Dict, List

from .operator_registry import (
    get_available_operator_names,
    resolve_operator_name,
)
from .backend.result_builder import trace_step

_logger = logging.getLogger(__name__)

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
_LOCAL_RETRIEVAL_MODES = {"auto", "bm25", "regex"}
_API_RETRIEVAL_MODES = {"auto", "llm", "vector"}


def _load_op_retrieval_funcs():
    try:
        from .backend import (
            get_op_catalog,
            init_op_catalog,
            retrieve_ops,
            retrieve_ops_with_meta,
        )

        return get_op_catalog, init_op_catalog, retrieve_ops, retrieve_ops_with_meta
    except Exception as exc:
        _logger.debug("load_op_retrieval_funcs failed: %s", exc)
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
                _logger.debug("worker thread error: %s", exc)
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
        _logger.debug("async retrieve failed: %s", exc)
        return {
            "names": [],
            "source": "",
            "trace": [trace_step(mode, "failed", str(exc))],
            "items": [],
        }


def _looks_like_regex_pattern(text: str) -> bool:
    value = str(text or "").strip()
    if not value:
        return False
    return bool(re.search(r"[\^\$\[\]\(\)\|\*\+\?\\]", value))


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


_MODALITY_TAG_MAP: Dict[str, List[str]] = {
    "text": ["text"],
    "image": ["image"],
    "multimodal": ["multimodal"],
    "audio": ["audio"],
    "video": ["video"],
}

def _infer_tags_from_dataset(
    dataset_path: str,
    dataset: dict | None = None,
) -> List[str]:
    """Probe dataset and return modality tags inferred from its schema.

    Accepts either a plain *dataset_path* or a structured *dataset* config.
    Returns an empty list when the dataset cannot be inspected or the modality
    is unknown, so the caller can fall back to unfiltered retrieval.
    """
    try:
        from data_juicer_agents.tools.context.inspect_dataset.logic import (
            inspect_dataset_schema,
        )
        result = inspect_dataset_schema(dataset_path=dataset_path, sample_size=20, dataset=dataset)
        if not result.get("ok"):
            return []
        modality = str(result.get("modality", "")).strip().lower()
        return list(_MODALITY_TAG_MAP.get(modality, []))
    except Exception as exc:
        _logger.debug("infer_tags_from_dataset failed for %s: %s", dataset_path, exc)
        return []


def _prepare_retrieval_inputs(
    top_k: int,
    tags: list | None = None,
    dataset_path: str | None = None,
    dataset: dict | None = None,
) -> Dict[str, Any]:
    requested_tags = [str(tag).strip() for tag in (tags or []) if str(tag).strip()]
    inferred_tags: List[str] = []
    if dataset_path:
        inferred_tags = _infer_tags_from_dataset(dataset_path=dataset_path, dataset=None)
    elif dataset:
        inferred_tags = _infer_tags_from_dataset(dataset_path="", dataset=dataset)

    effective_tags = list(requested_tags)
    for tag in inferred_tags:
        if tag not in effective_tags:
            effective_tags.append(tag)

    normalized_top_k = int(top_k) if isinstance(top_k, int) or str(top_k).isdigit() else 10
    if normalized_top_k <= 0:
        normalized_top_k = 10
    normalized_top_k = min(normalized_top_k, 200)

    info_rows: List[Dict[str, Any]] = []
    funcs = _load_op_retrieval_funcs()
    if funcs is not None:
        get_op_catalog, _init_op_catalog, _retrieve_ops, _retrieve_ops_with_meta = funcs
        try:
            info_rows = [
                item
                for item in get_op_catalog()
                if isinstance(item, dict) and str(item.get("class_name", "")).strip()
            ]
        except Exception as exc:
            _logger.debug("get_op_catalog failed: %s", exc)
            info_rows = []

    return {
        "top_k": normalized_top_k,
        "requested_tags": requested_tags,
        "inferred_tags": inferred_tags,
        "effective_tags": effective_tags,
        "info_rows": info_rows,
        "info_map": {str(item.get("class_name", "")).strip(): item for item in info_rows},
    }


def _normalize_retrieved_names(
    retrieved_names: List[str],
    retrieval_item_map: Dict[str, Dict[str, Any]],
    available_ops: set[str],
) -> tuple[List[str], Dict[str, Dict[str, Any]]]:
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
    return normalized_names, normalized_item_map


def _finalize_candidate_payload(
    *,
    intent: str,
    top_k: int,
    requested_mode: str,
    op_type: str | None,
    requested_tags: List[str],
    inferred_tags: List[str],
    effective_tags: List[str],
    info_rows: List[Dict[str, Any]],
    info_map: Dict[str, Dict[str, Any]],
    retrieve_meta: Dict[str, Any],
    allow_lexical_fallback: bool,
    fallback_note: str | None = None,
) -> Dict[str, Any]:
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

    if not retrieved_names and allow_lexical_fallback:
        retrieved_names = _lexical_fallback(intent, info_rows=info_rows, top_k=top_k)
        retrieval_source = "lexical"
        retrieval_trace.append(
            trace_step(
                "lexical", "selected", reason="fallback_after_remote_empty_or_failed"
            )
        )

    available_ops = get_available_operator_names()
    normalized_names, normalized_item_map = _normalize_retrieved_names(
        retrieved_names,
        retrieval_item_map,
        available_ops=available_ops,
    )

    if not normalized_names and info_rows and allow_lexical_fallback:
        normalized_names = _lexical_fallback(intent, info_rows=info_rows, top_k=top_k)
        retrieval_source = "lexical"
        retrieval_trace.append(
            trace_step(
                "lexical", "selected", reason="fallback_after_remote_empty_or_failed"
            )
        )

    candidates = [
        _build_candidate_row(
            idx,
            name,
            intent=intent,
            info_map=info_map,
            retrieval_item=normalized_item_map.get(name),
        )
        for idx, name in enumerate(normalized_names[:top_k], start=1)
    ]

    candidate_names = [item["operator_name"] for item in candidates]
    notes: List[str] = []
    if not candidates:
        notes.append(fallback_note or "No operator candidates were found from retrieval.")

    result = {
        "ok": True,
        "intent": intent,
        "top_k": top_k,
        "mode": requested_mode,
        "retrieval_source": retrieval_source,
        "retrieval_trace": retrieval_trace,
        "candidate_count": len(candidates),
        "candidate_names": candidate_names,
        "gap_detected": len(candidates) == 0,
        "requested_tags": requested_tags,
        "inferred_tags": inferred_tags,
        "effective_tags": effective_tags,
        "candidates": candidates,
        "notes": notes,
    }
    if op_type:
        result["op_type"] = op_type
    return result

def retrieve_operator_candidates(
    intent: str,
    top_k: int = 10,
    mode: str = "auto",
    op_type: str | None = None,
    tags: list | None = None,
    dataset_path: str | None = None,
    dataset: dict | None = None,
) -> Dict[str, Any]:
    """Retrieve operators and return a structured payload for CLI/agent usage.

    Args:
        intent: Natural-language description of the desired operators.
        top_k: Maximum number of candidates to return.
        mode: Retrieval backend mode ("llm", "vector", "bm25", "regex", or "auto").
        op_type: Optional operator type filter (e.g. "filter", "mapper",
                 "deduplicator"). Propagated to retrieval backends for early
                 filtering.
        tags: Explicit modality/resource tags for filtering (match-all semantics).
        dataset_path: Optional dataset path; when provided, the dataset modality
                      is probed via ``inspect_dataset_schema`` and the inferred
                      tags are merged with any explicit *tags*.
        dataset: Optional structured dataset config (``{"configs": [...]}``).
                 Used for modality probing when *dataset_path* is not provided.
    """
    prepared = _prepare_retrieval_inputs(
        top_k=top_k,
        tags=tags,
        dataset_path=dataset_path,
        dataset=dataset,
    )
    effective_tags = prepared["effective_tags"] or None
    retrieve_meta = _safe_async_retrieve(
        intent,
        top_k=prepared["top_k"],
        mode=mode,
        op_type=op_type,
        tags=effective_tags,
    )
    return _finalize_candidate_payload(
        intent=intent,
        top_k=prepared["top_k"],
        requested_mode=mode,
        op_type=op_type,
        requested_tags=prepared["requested_tags"],
        inferred_tags=prepared["inferred_tags"],
        effective_tags=prepared["effective_tags"],
        info_rows=prepared["info_rows"],
        info_map=prepared["info_map"],
        retrieve_meta=retrieve_meta,
        allow_lexical_fallback=True,
    )


def retrieve_operator_candidates_local(
    intent: str,
    top_k: int = 10,
    mode: str = "auto",
    op_type: str | None = None,
    tags: list | None = None,
    dataset_path: str | None = None,
    dataset: dict | None = None,
) -> Dict[str, Any]:
    normalized_mode = str(mode or "auto").strip().lower() or "auto"
    if normalized_mode not in _LOCAL_RETRIEVAL_MODES:
        raise ValueError(
            f"invalid local retrieval mode: {mode!r}; expected one of {sorted(_LOCAL_RETRIEVAL_MODES)}"
        )

    prepared = _prepare_retrieval_inputs(
        top_k=top_k,
        tags=tags,
        dataset_path=dataset_path,
        dataset=dataset,
    )
    effective_tags = prepared["effective_tags"] or None
    effective_mode = normalized_mode
    if normalized_mode == "auto":
        effective_mode = "regex" if _looks_like_regex_pattern(intent) else "bm25"

    retrieve_meta = _safe_async_retrieve(
        intent,
        top_k=prepared["top_k"],
        mode=effective_mode,
        op_type=op_type,
        tags=effective_tags,
    )
    return _finalize_candidate_payload(
        intent=intent,
        top_k=prepared["top_k"],
        requested_mode=normalized_mode,
        op_type=op_type,
        requested_tags=prepared["requested_tags"],
        inferred_tags=prepared["inferred_tags"],
        effective_tags=prepared["effective_tags"],
        info_rows=prepared["info_rows"],
        info_map=prepared["info_map"],
        retrieve_meta=retrieve_meta,
        allow_lexical_fallback=True,
    )


def retrieve_operator_candidates_api(
    intent: str,
    top_k: int = 10,
    mode: str = "auto",
    op_type: str | None = None,
    tags: list | None = None,
    dataset_path: str | None = None,
    dataset: dict | None = None,
) -> Dict[str, Any]:
    normalized_mode = str(mode or "auto").strip().lower() or "auto"
    if normalized_mode not in _API_RETRIEVAL_MODES:
        raise ValueError(
            f"invalid api retrieval mode: {mode!r}; expected one of {sorted(_API_RETRIEVAL_MODES)}"
        )

    prepared = _prepare_retrieval_inputs(
        top_k=top_k,
        tags=tags,
        dataset_path=dataset_path,
        dataset=dataset,
    )
    effective_tags = prepared["effective_tags"] or None

    if normalized_mode == "auto":
        llm_meta = _safe_async_retrieve(
            intent,
            top_k=prepared["top_k"],
            mode="llm",
            op_type=op_type,
            tags=effective_tags,
        )
        if llm_meta.get("names"):
            retrieve_meta = llm_meta
        else:
            vector_meta = _safe_async_retrieve(
                intent,
                top_k=prepared["top_k"],
                mode="vector",
                op_type=op_type,
                tags=effective_tags,
            )
            retrieve_meta = {
                "names": list(vector_meta.get("names", [])),
                "source": str(vector_meta.get("source", "")).strip(),
                "trace": list(llm_meta.get("trace", [])) + list(vector_meta.get("trace", [])),
                "items": list(vector_meta.get("items", [])),
            }
    else:
        retrieve_meta = _safe_async_retrieve(
            intent,
            top_k=prepared["top_k"],
            mode=normalized_mode,
            op_type=op_type,
            tags=effective_tags,
        )

    return _finalize_candidate_payload(
        intent=intent,
        top_k=prepared["top_k"],
        requested_mode=normalized_mode,
        op_type=op_type,
        requested_tags=prepared["requested_tags"],
        inferred_tags=prepared["inferred_tags"],
        effective_tags=prepared["effective_tags"],
        info_rows=prepared["info_rows"],
        info_map=prepared["info_map"],
        retrieve_meta=retrieve_meta,
        allow_lexical_fallback=False,
        fallback_note="No operator candidates were found from API retrieval.",
    )


def _format_type_hint(annotation: Any) -> str:
    if annotation is inspect.Signature.empty:
        return ""
    if isinstance(annotation, type):
        return annotation.__name__
    text = str(annotation).replace("typing.", "").strip()
    if text == "<class 'inspect._empty'>":
        return ""
    return text


def _format_default_repr(value: Any) -> str:
    if value is inspect.Signature.empty:
        return ""
    return repr(value)


def _build_operator_parameters(record: Any) -> List[Dict[str, Any]]:
    parameters: List[Dict[str, Any]] = []
    for param_name, param in record.sig.parameters.items():
        if param_name in {"self", "args", "kwargs"}:
            continue
        if param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        parameters.append(
            {
                "name": param_name,
                "type_hint": _format_type_hint(param.annotation),
                "required": param.default is inspect.Signature.empty,
                "default_repr": _format_default_repr(param.default),
                "description": str(record.param_desc_map.get(param_name, "")).strip(),
            }
        )
    return parameters


def list_operator_catalog(
    *,
    op_type: str | None = None,
    tags: List[str] | None = None,
    include_parameters: bool = False,
    limit: int = 0,
) -> Dict[str, Any]:
    normalized_type = str(op_type or "").strip().lower()
    requested_tags = [str(item).strip().lower() for item in (tags or []) if str(item).strip()]

    try:
        from .backend.catalog import searcher
    except Exception as exc:
        _logger.debug("catalog import failed: %s", exc)
        return {
            "ok": False,
            "message": f"operator catalog unavailable: {exc}",
            "error_type": "catalog_unavailable",
            "operators": [],
            "total_count": 0,
            "returned_count": 0,
            "op_type_filter": normalized_type or None,
            "requested_tags": requested_tags,
            "include_parameters": bool(include_parameters),
            "limit": max(int(limit or 0), 0),
        }

    limit_value = max(int(limit or 0), 0)
    filtered_records: List[tuple[str, Any]] = []
    for name, record in sorted(searcher.all_ops.items(), key=lambda item: item[0]):
        record_type = str(record.type or "").strip().lower()
        record_tags = [str(item).strip() for item in (record.tags or []) if str(item).strip()]
        record_tags_lower = {item.lower() for item in record_tags}

        if normalized_type and record_type != normalized_type:
            continue
        if requested_tags and not all(tag in record_tags_lower for tag in requested_tags):
            continue
        filtered_records.append((name, record))

    total_count = len(filtered_records)
    selected_records = filtered_records[:limit_value] if limit_value > 0 else filtered_records

    operators: List[Dict[str, Any]] = []
    for name, record in selected_records:
        item: Dict[str, Any] = {
            "operator_name": str(name).strip(),
            "operator_type": str(record.type or "").strip(),
            "tags": [str(tag).strip() for tag in (record.tags or []) if str(tag).strip()],
            "description": str(record.desc or "").strip(),
            "source_path": str(record.source_path or "").strip(),
            "test_path": str(record.test_path or "").strip(),
        }
        if include_parameters:
            item["parameters"] = _build_operator_parameters(record)
        operators.append(item)

    message = f"listed {len(operators)} operators"
    if total_count != len(operators):
        message += f" (filtered from {total_count})"

    return {
        "ok": True,
        "message": message,
        "operators": operators,
        "total_count": total_count,
        "returned_count": len(operators),
        "op_type_filter": normalized_type or None,
        "requested_tags": requested_tags,
        "include_parameters": bool(include_parameters),
        "limit": limit_value,
    }


def get_operator_info(operator_name: str) -> Dict[str, Any]:
    raw_name = str(operator_name or "").strip()
    if not raw_name:
        return {
            "ok": False,
            "requested_name": raw_name,
            "resolved_name": "",
            "resolved": False,
            "exact_match": False,
            "error_type": "missing_required",
            "message": "operator_name is required",
        }

    try:
        from .backend.catalog import searcher
    except Exception as exc:
        _logger.debug("catalog import failed: %s", exc)
        return {
            "ok": False,
            "requested_name": raw_name,
            "resolved_name": "",
            "resolved": False,
            "exact_match": False,
            "error_type": "catalog_unavailable",
            "message": f"operator catalog unavailable: {exc}",
        }

    available_ops = set(searcher.all_ops.keys())
    resolved_name = resolve_operator_name(raw_name, available_ops=available_ops)
    record = searcher.all_ops.get(resolved_name)
    if record is None:
        return {
            "ok": False,
            "requested_name": raw_name,
            "resolved_name": resolved_name,
            "resolved": False,
            "exact_match": False,
            "error_type": "operator_not_found",
            "message": f"operator not found: {raw_name}",
        }

    exact_match = resolved_name == raw_name
    return {
        "ok": True,
        "requested_name": raw_name,
        "resolved_name": resolved_name,
        "resolved": True,
        "exact_match": exact_match,
        "operator_type": str(record.type).strip(),
        "tags": list(record.tags or []),
        "description": str(record.desc or "").strip(),
        "source_path": str(record.source_path or "").strip(),
        "test_path": str(record.test_path or "").strip(),
        "parameters": _build_operator_parameters(record),
        "message": "retrieved operator info",
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
