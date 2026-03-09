# -*- coding: utf-8 -*-

import asyncio

from data_juicer_agents.tools.op_manager.retrieval_service import retrieve_operator_candidates


def test_retrieval_service_falls_back_to_lexical(monkeypatch):
    from data_juicer_agents.tools.op_manager import retrieval_service as svc

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
        lambda intent, top_k, mode: {
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

    payload = retrieve_operator_candidates(
        intent="need dedup for text corpus",
        top_k=5,
        mode="auto",
        dataset_path=None,
    )
    assert payload["ok"] is True
    assert payload["candidate_count"] >= 1
    assert payload["retrieval_source"] == "lexical"
    assert payload["retrieval_trace"][-1]["backend"] == "lexical"
    names = [item["operator_name"] for item in payload["candidates"]]
    assert "document_deduplicator" in names


def test_safe_async_retrieve_works_inside_running_loop(monkeypatch):
    from data_juicer_agents.tools.op_manager import retrieval_service as svc

    async def fake_retrieve_ops_with_meta(intent, limit=10, mode="auto"):
        return {
            "names": ["text_length_filter"],
            "source": "vector",
            "trace": [{"backend": "vector", "status": "success"}],
        }

    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    monkeypatch.setattr(
        svc,
        "_load_op_retrieval_funcs",
        lambda: (lambda: [], lambda: True, None, fake_retrieve_ops_with_meta),
    )

    async def _inside_loop():
        return svc._safe_async_retrieve("text clean", top_k=5, mode="auto")

    meta = asyncio.run(_inside_loop())
    assert meta["names"] == ["text_length_filter"]
    assert meta["source"] == "vector"
    assert meta["trace"] == [{"backend": "vector", "status": "success"}]


def test_retrieval_service_prefers_true_backend_source(monkeypatch):
    from data_juicer_agents.tools.op_manager import retrieval_service as svc

    rows = [
        {
            "class_name": "text_length_filter",
            "class_desc": "Filter text by length",
            "arguments": "max_len (int): max length",
        }
    ]

    monkeypatch.setattr(
        svc,
        "_load_op_retrieval_funcs",
        lambda: (lambda: rows, lambda: True, None, None),
    )
    monkeypatch.setattr(
        svc,
        "_safe_async_retrieve",
        lambda intent, top_k, mode: {
            "names": ["text_length_filter"],
            "source": "vector",
            "trace": [
                {"backend": "llm", "status": "failed", "error": "import error"},
                {"backend": "vector", "status": "success"},
            ],
        },
    )
    monkeypatch.setattr(
        svc,
        "get_available_operator_names",
        lambda: {"text_length_filter"},
    )

    payload = retrieve_operator_candidates(
        intent="filter long text",
        top_k=5,
        mode="auto",
        dataset_path=None,
    )

    assert payload["retrieval_source"] == "vector"
    assert payload["retrieval_trace"] == [
        {"backend": "llm", "status": "failed", "error": "import error"},
        {"backend": "vector", "status": "success"},
    ]


def test_retrieval_service_uses_llm_scores_when_source_is_llm(monkeypatch):
    from data_juicer_agents.tools.op_manager import retrieval_service as svc

    rows = [
        {
            "class_name": "text_length_filter",
            "class_desc": "Filter text by length",
            "arguments": "max_len (int): max length",
        }
    ]

    monkeypatch.setattr(
        svc,
        "_load_op_retrieval_funcs",
        lambda: (lambda: rows, lambda: True, None, None),
    )
    monkeypatch.setattr(
        svc,
        "_safe_async_retrieve",
        lambda intent, top_k, mode: {
            "names": ["text_length_filter"],
            "source": "llm",
            "trace": [{"backend": "llm", "status": "success"}],
            "items": [
                {
                    "tool_name": "text_length_filter",
                    "description": "Best operator for filtering long text.",
                    "relevance_score": 97.5,
                    "key_match": ["text length", "1500 characters"],
                }
            ],
        },
    )
    monkeypatch.setattr(
        svc,
        "get_available_operator_names",
        lambda: {"text_length_filter"},
    )

    payload = retrieve_operator_candidates(
        intent="filter text longer than 1500 characters",
        top_k=5,
        mode="llm",
        dataset_path=None,
    )

    candidate = payload["candidates"][0]
    assert payload["retrieval_source"] == "llm"
    assert candidate["description"] == "Best operator for filtering long text."
    assert candidate["relevance_score"] == 97.5
    assert candidate["score_source"] == "llm"
    assert candidate["key_match"] == ["text length", "1500 characters"]
