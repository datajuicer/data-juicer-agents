# -*- coding: utf-8 -*-

import asyncio
import os

import pytest

_has_api_key = bool(
    (os.environ.get("DASHSCOPE_API_KEY") or "").strip()
    or (os.environ.get("MODELSCOPE_API_TOKEN") or "").strip()
)
_skip_no_api_key = pytest.mark.skipif(
    not _has_api_key,
    reason="DASHSCOPE_API_KEY / MODELSCOPE_API_TOKEN not set",
)

# ---------------------------------------------------------------------------
# Real LLM tests (skipped in GHA)
# ---------------------------------------------------------------------------

@_skip_no_api_key
def test_retrieve_ops_with_meta_llm():
    """Real LLM retrieval - requires DASHSCOPE_API_KEY."""
    import data_juicer_agents.tools.retrieve._shared.backend as mod

    payload = asyncio.run(
        mod.retrieve_ops_with_meta("filter text by length", limit=5, mode="llm")
    )
    assert payload["source"] == "llm"
    assert len(payload["names"]) > 0
    assert "text_length_filter" in payload["names"]

@_skip_no_api_key
def test_retrieve_ops_with_meta_auto():
    """Real auto retrieval - requires DASHSCOPE_API_KEY."""
    import data_juicer_agents.tools.retrieve._shared.backend as mod

    payload = asyncio.run(
        mod.retrieve_ops_with_meta("filter text by length", limit=5, mode="auto")
    )
    assert payload["source"] in ("llm", "bm25")
    assert len(payload["names"]) > 0

# ---------------------------------------------------------------------------
# Fallback / failure tests (must use mocks)
# ---------------------------------------------------------------------------

def test_retrieve_ops_with_meta_auto_mock_all_fail(monkeypatch):
    """Mock test: auto mode returns empty when all backends fail."""
    import data_juicer_agents.tools.retrieve._shared.backend as retrieval_mod
    from data_juicer_agents.tools.retrieve._shared.backend.retriever import _strategy

    async def fail_llm_retrieve_items(_self, _query, limit=20, op_type=None, tags=None):  # noqa: ARG001
        raise RuntimeError("llm unavailable")

    async def fail_bm25_retrieve_items(_self, _query, limit=20, op_type=None, tags=None):  # noqa: ARG001
        raise RuntimeError("bm25 unavailable")

    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    monkeypatch.setattr(type(_strategy.backends["llm"]), "retrieve_items", fail_llm_retrieve_items)
    monkeypatch.setattr(type(_strategy.backends["bm25"]), "retrieve_items", fail_bm25_retrieve_items)

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
        {"backend": "bm25", "status": "failed", "error": "bm25 unavailable"},
    ]

# ---------------------------------------------------------------------------
# op_catalog lifecycle (real tests)
# ---------------------------------------------------------------------------

def test_get_op_catalog_returns_non_empty_list():
    """get_op_catalog returns a non-empty list of operator dicts."""
    from data_juicer_agents.tools.retrieve._shared.backend import get_op_catalog

    catalog = get_op_catalog()
    assert isinstance(catalog, list)
    assert len(catalog) > 0
    assert "class_name" in catalog[0]
    assert "class_desc" in catalog[0]
    assert "class_type" in catalog[0]
    assert "class_tags" in catalog[0]

def test_get_op_catalog_caches_result():
    """Consecutive get_op_catalog calls return the same cached object."""
    from data_juicer_agents.tools.retrieve._shared.backend import get_op_catalog

    result1 = get_op_catalog()
    result2 = get_op_catalog()
    assert result1 is result2

def test_refresh_op_catalog_updates_cache():
    """refresh_op_catalog reloads and updates the cached catalog."""
    from data_juicer_agents.tools.retrieve._shared.backend import (
        get_op_catalog,
        refresh_op_catalog,
    )
    from data_juicer_agents.tools.retrieve._shared.backend.cache import (
        CK_OP_CATALOG,
        cache_manager,
    )

    original = get_op_catalog()
    assert len(original) > 0

    result = refresh_op_catalog()
    assert result is True

    refreshed = cache_manager.get(CK_OP_CATALOG)
    assert isinstance(refreshed, list)
    assert len(refreshed) > 0
    assert refreshed[0]["class_name"] == original[0]["class_name"]

# ---------------------------------------------------------------------------
# BM25 retrieval (real tests - no API key needed)
# ---------------------------------------------------------------------------

def test_retrieve_ops_with_meta_passes_op_type_to_bm25(monkeypatch):
    """BM25 retrieval correctly filters by op_type."""
    import data_juicer_agents.tools.retrieve._shared.backend as mod

    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("MODELSCOPE_API_TOKEN", raising=False)

    payload = asyncio.run(
        mod.retrieve_ops_with_meta(
            "filter text",
            limit=5,
            mode="bm25",
            op_type="filter",
        )
    )
    assert "text_length_filter" in payload["names"]
    assert payload["source"] == "bm25"

def test_retrieve_ops_without_api_key_falls_back_to_bm25(monkeypatch):
    """Auto mode falls back to BM25 when no API key is configured."""
    import data_juicer_agents.tools.retrieve._shared.backend as mod

    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("MODELSCOPE_API_TOKEN", raising=False)

    names = asyncio.run(
        mod.retrieve_ops("deduplicate document", limit=5, mode="auto", op_type="deduplicator")
    )

    assert "document_deduplicator" in names

# ---------------------------------------------------------------------------
# Regex retrieval (real tests - no API key needed)
# ---------------------------------------------------------------------------

def test_retrieve_ops_regex_items_basic():
    """retrieve_ops_regex_items returns items matching a regex pattern."""
    import data_juicer_agents.tools.retrieve._shared.backend as mod

    items = mod.retrieve_ops_regex_items("text_length", limit=10)
    assert len(items) == 1
    assert items[0]["tool_name"] == "text_length_filter"
    assert items[0]["score_source"] == "regex_rank"
    assert items[0]["operator_type"] == "filter"

def test_retrieve_ops_regex_items_with_op_type():
    """retrieve_ops_regex_items filters results by op_type."""
    import data_juicer_agents.tools.retrieve._shared.backend as mod

    items = mod.retrieve_ops_regex_items("text.*filter", limit=5, op_type="filter")
    for item in items:
        assert item["operator_type"] == "filter"

def test_retrieve_ops_regex_returns_name_list():
    """retrieve_ops_regex_items returns items whose names can be extracted."""
    import data_juicer_agents.tools.retrieve._shared.backend as mod

    items = mod.retrieve_ops_regex_items("text_len|document", limit=10)
    names = [item["tool_name"] for item in items]
    assert isinstance(names, list)
    assert "text_length_filter" in names
    assert "document_deduplicator" in names

def test_retrieve_ops_regex_items_invalid_pattern():
    """retrieve_ops_regex_items handles invalid regex gracefully."""
    import data_juicer_agents.tools.retrieve._shared.backend as mod

    items = mod.retrieve_ops_regex_items("[invalid(regex", limit=5)
    assert items == []

def test_retrieve_ops_regex_items_respects_limit():
    """retrieve_ops_regex_items respects the limit parameter."""
    import data_juicer_agents.tools.retrieve._shared.backend as mod

    items = mod.retrieve_ops_regex_items("filter", limit=3)
    assert len(items) == 3

def test_retrieve_ops_with_meta_regex_mode():
    """retrieve_ops_with_meta correctly dispatches regex mode."""
    import data_juicer_agents.tools.retrieve._shared.backend as mod

    payload = asyncio.run(
        mod.retrieve_ops_with_meta(
            "text_length",
            limit=5,
            mode="regex",
        )
    )

    assert payload["names"] == ["text_length_filter"]
    assert payload["source"] == "regex"
    assert payload["trace"] == [{"backend": "regex", "status": "success"}]
    assert len(payload["items"]) == 1
    assert payload["items"][0]["tool_name"] == "text_length_filter"

def test_retrieve_ops_with_meta_regex_mode_with_op_type():
    """retrieve_ops_with_meta passes op_type to regex backend."""
    import data_juicer_agents.tools.retrieve._shared.backend as mod

    payload = asyncio.run(
        mod.retrieve_ops_with_meta(
            "^text.*",
            limit=5,
            mode="regex",
            op_type="filter",
        )
    )

    assert "text_length_filter" in payload["names"]
    assert payload["source"] == "regex"

def test_retrieve_ops_with_meta_regex_mode_empty_result():
    """retrieve_ops_with_meta returns empty payload when regex matches nothing."""
    import data_juicer_agents.tools.retrieve._shared.backend as mod

    payload = asyncio.run(
        mod.retrieve_ops_with_meta(
            "nonexistent_pattern_xyz",
            limit=5,
            mode="regex",
        )
    )

    assert payload["names"] == []
    assert payload["source"] == ""
    assert payload["trace"] == [{"backend": "regex", "status": "empty"}]
