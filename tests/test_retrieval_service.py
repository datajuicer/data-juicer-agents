# -*- coding: utf-8 -*-

import os

import pytest

from data_juicer_agents.tools.retrieve import (
    retrieve_operator_candidates,
    retrieve_operator_candidates_api,
    retrieve_operator_candidates_local,
)

_has_api_key = bool(
    (os.environ.get("DASHSCOPE_API_KEY") or "").strip()
    or (os.environ.get("MODELSCOPE_API_TOKEN") or "").strip()
)
_skip_no_api_key = pytest.mark.skipif(
    not _has_api_key,
    reason="DASHSCOPE_API_KEY / MODELSCOPE_API_TOKEN not set",
)

# ---------------------------------------------------------------------------
# Real tests
# ---------------------------------------------------------------------------

def test_retrieve_operator_candidates_bm25():
    """Real retrieval via BM25 (no API key needed)."""
    payload = retrieve_operator_candidates(
        intent="deduplicate documents",
        top_k=10,
        mode="bm25",
    )
    assert payload["ok"] is True
    assert payload["candidate_count"] >= 1
    assert payload["candidate_names"]
    names = [c["operator_name"] for c in payload["candidates"]]
    assert any("dedup" in n for n in names)

@_skip_no_api_key
def test_retrieve_operator_candidates_auto():
    """Real retrieval via auto mode (requires API key)."""
    payload = retrieve_operator_candidates(
        intent="filter text by length",
        top_k=5,
        mode="auto",
    )
    assert payload["ok"] is True
    assert payload["candidate_count"] >= 1

@_skip_no_api_key
def test_retrieve_operator_candidates_llm():
    """Real retrieval via LLM (requires API key)."""
    payload = retrieve_operator_candidates(
        intent="filter text longer than 1500 characters",
        top_k=5,
        mode="llm",
    )
    assert payload["ok"] is True
    assert payload["retrieval_source"] == "llm"
    candidate = payload["candidates"][0]
    assert candidate["score_source"] == "llm"

# ---------------------------------------------------------------------------
# Fallback tests (must use mocks to simulate failures)
# ---------------------------------------------------------------------------

def test_retrieval_service_falls_back_to_lexical(monkeypatch):
    """When all backends fail, lexical fallback kicks in."""
    from data_juicer_agents.tools.retrieve._shared import logic as svc

    rows = [
        {
            "class_name": "document_deduplicator",
            "class_desc": "Deduplicate documents",
            "arguments": "lowercase (bool): Whether to lowercase.",
        },
        {
            "class_name": "text_length_filter",
            "class_desc": "Filter text by length",
            "arguments": "min_len (int): min length",
        },
    ]

    monkeypatch.setattr(
        svc,
        "_load_op_retrieval_funcs",
        lambda: (lambda: rows, lambda: True, None, None),
    )
    monkeypatch.setattr(
        svc,
        "_safe_async_retrieve",
        lambda intent, top_k, mode, op_type=None, tags=None: {
            "names": [],
            "source": "",
            "trace": [{"backend": "llm", "status": "failed", "error": "boom"}],
        },
    )
    monkeypatch.setattr(
        svc,
        "get_available_operator_names",
        lambda: {"document_deduplicator", "text_length_filter"},
    )
    monkeypatch.setattr(
        svc,
        "resolve_operator_name",
        lambda name, available_ops=None: (
            ""
            if str(name).strip() == "TotallyInvalidOperatorName"
            else str(name).strip()
        ),
    )

    payload = svc.retrieve_operator_candidates(
        intent="need dedup for text corpus",
        top_k=5,
        mode="auto",
    )
    assert payload["ok"] is True
    assert payload["candidate_count"] >= 1
    assert payload["retrieval_source"] == "lexical"
    assert payload["retrieval_trace"][-1]["backend"] == "lexical"
    names = [item["operator_name"] for item in payload["candidates"]]
    assert "document_deduplicator" in names


def test_retrieval_service_normalization_empty_updates_lexical_source(monkeypatch):
    """If raw retrieval names fail normalization, lexical fallback must update source/trace."""
    from data_juicer_agents.tools.retrieve._shared import logic as svc

    rows = [
        {
            "class_name": "document_deduplicator",
            "class_desc": "Deduplicate documents",
            "arguments": "lowercase (bool): Whether to lowercase.",
        },
        {
            "class_name": "text_length_filter",
            "class_desc": "Filter text by length",
            "arguments": "min_len (int): min length",
        },
    ]

    monkeypatch.setattr(
        svc,
        "_load_op_retrieval_funcs",
        lambda: (lambda: rows, lambda: True, None, None),
    )
    monkeypatch.setattr(
        svc,
        "_safe_async_retrieve",
        lambda intent, top_k, mode, op_type=None, tags=None: {
            "names": ["TotallyInvalidOperatorName"],
            "source": "llm",
            "trace": [{"backend": "llm", "status": "success"}],
            "items": [
                {
                    "tool_name": "TotallyInvalidOperatorName",
                    "description": "bad candidate",
                    "relevance_score": 99.0,
                    "score_source": "llm",
                }
            ],
        },
    )
    monkeypatch.setattr(
        svc,
        "get_available_operator_names",
        lambda: {"document_deduplicator", "text_length_filter"},
    )
    monkeypatch.setattr(
        svc,
        "resolve_operator_name",
        lambda name, available_ops=None: (
            ""
            if str(name).strip() == "TotallyInvalidOperatorName"
            else str(name).strip()
        ),
    )

    payload = svc.retrieve_operator_candidates(
        intent="need dedup for text corpus",
        top_k=5,
        mode="auto",
    )
    assert payload["ok"] is True
    assert payload["candidate_count"] >= 1
    assert payload["retrieval_source"] == "lexical"
    assert payload["retrieval_trace"][-1]["backend"] == "lexical"
    assert payload["retrieval_trace"][-1]["reason"] == "fallback_after_remote_empty_or_failed"
    names = [item["operator_name"] for item in payload["candidates"]]
    assert "document_deduplicator" in names


def test_prepare_retrieval_inputs_uses_explicit_tags_only(monkeypatch):
    from data_juicer_agents.tools.retrieve._shared import logic as svc

    monkeypatch.setattr(svc, "_load_op_retrieval_funcs", lambda: None)

    prepared = svc._prepare_retrieval_inputs(top_k=5, tags=["cpu"])

    assert prepared["requested_tags"] == ["cpu"]


def test_retrieve_operator_candidates_local_auto_uses_regex_for_regex_like_query():
    payload = retrieve_operator_candidates_local(
        intent="^text_length.*",
        top_k=5,
        mode="auto",
    )
    assert payload["ok"] is True
    assert payload["retrieval_source"] == "regex"
    assert "text_length_filter" in payload["candidate_names"]


def test_retrieve_operator_candidates_api_without_api_key_returns_empty(monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("MODELSCOPE_API_TOKEN", raising=False)

    payload = retrieve_operator_candidates_api(
        intent="filter long text",
        top_k=5,
        mode="auto",
    )
    assert payload["ok"] is True
    assert payload["candidate_count"] == 0
    assert payload["candidate_names"] == []
    assert payload["retrieval_source"] == ""
    assert payload["retrieval_trace"][0]["backend"] == "llm"
    assert payload["retrieval_trace"][-1]["backend"] == "vector"
    assert payload["notes"] == ["No operator candidates were found from API retrieval."]
