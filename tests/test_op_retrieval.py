# -*- coding: utf-8 -*-

import asyncio


def test_retrieve_ops_with_meta_auto_uses_llm_when_available(monkeypatch):
    from data_juicer_agents.tools.op_manager import op_retrieval as retrieval_mod

    async def fake_llm_items(_query, limit=20):  # noqa: ARG001
        return [{"tool_name": "text_length_filter"}][:limit]

    monkeypatch.setattr(retrieval_mod, "retrieve_ops_lm_items", fake_llm_items)
    monkeypatch.setattr(
        retrieval_mod,
        "retrieve_ops_vector",
        lambda _query, limit=20: ["document_deduplicator"][:limit],
    )

    payload = asyncio.run(
        retrieval_mod.retrieve_ops_with_meta(
            "filter long text",
            limit=5,
            mode="auto",
        )
    )

    assert payload["names"] == ["text_length_filter"]
    assert payload["source"] == "llm"
    assert payload["trace"] == [{"backend": "llm", "status": "success"}]


def test_retrieve_ops_with_meta_auto_falls_back_to_vector(monkeypatch):
    from data_juicer_agents.tools.op_manager import op_retrieval as retrieval_mod

    async def fail_llm_items(_query, limit=20):  # noqa: ARG001
        raise ImportError("cannot import async_sessionmaker")

    monkeypatch.setattr(retrieval_mod, "retrieve_ops_lm_items", fail_llm_items)
    monkeypatch.setattr(
        retrieval_mod,
        "retrieve_ops_vector",
        lambda _query, limit=20: ["text_length_filter"][:limit],
    )

    payload = asyncio.run(
        retrieval_mod.retrieve_ops_with_meta(
            "filter long text",
            limit=5,
            mode="auto",
        )
    )

    assert payload["names"] == ["text_length_filter"]
    assert payload["source"] == "vector"
    assert payload["trace"][0]["backend"] == "llm"
    assert payload["trace"][0]["status"] == "failed"
    assert "async_sessionmaker" in payload["trace"][0]["error"]
    assert payload["trace"][1] == {"backend": "vector", "status": "success"}


def test_retrieve_ops_with_meta_auto_returns_empty_when_all_backends_fail(monkeypatch):
    from data_juicer_agents.tools.op_manager import op_retrieval as retrieval_mod

    async def fail_llm_items(_query, limit=20):  # noqa: ARG001
        raise RuntimeError("llm unavailable")

    def fail_vector(_query, limit=20):  # noqa: ARG001
        raise RuntimeError("vector unavailable")

    monkeypatch.setattr(retrieval_mod, "retrieve_ops_lm_items", fail_llm_items)
    monkeypatch.setattr(retrieval_mod, "retrieve_ops_vector", fail_vector)

    payload = asyncio.run(
        retrieval_mod.retrieve_ops_with_meta(
            "filter long text",
            limit=5,
            mode="auto",
        )
    )

    assert payload["names"] == []
    assert payload["source"] == ""
    assert payload["trace"] == [
        {"backend": "llm", "status": "failed", "error": "llm unavailable"},
        {"backend": "vector", "status": "failed", "error": "vector unavailable"},
    ]
