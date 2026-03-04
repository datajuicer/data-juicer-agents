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
        lambda: (lambda: rows, lambda: True, None),
    )
    monkeypatch.setattr(
        svc,
        "_safe_async_retrieve",
        lambda intent, top_k, mode: ([], "fallback"),
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
    names = [item["operator_name"] for item in payload["candidates"]]
    assert "document_deduplicator" in names


def test_safe_async_retrieve_works_inside_running_loop(monkeypatch):
    from data_juicer_agents.tools.op_manager import retrieval_service as svc

    async def fake_retrieve_ops(intent, limit=10, mode="auto"):
        return ["text_length_filter"]

    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    monkeypatch.setattr(
        svc,
        "_load_op_retrieval_funcs",
        lambda: (lambda: [], lambda: True, fake_retrieve_ops),
    )

    async def _inside_loop():
        return svc._safe_async_retrieve("text clean", top_k=5, mode="auto")

    names, source = asyncio.run(_inside_loop())
    assert names == ["text_length_filter"]
    assert source == "auto"
