# -*- coding: utf-8 -*-
"""Unit tests for result_builder helpers."""

import pytest

from data_juicer_agents.tools.retrieve.retrieve_operators.backend.result_builder import (
    build_retrieval_item,
    filter_by_op_type,
    names_from_items,
    trace_step,
)


# ---------------------------------------------------------------------------
# build_retrieval_item
# ---------------------------------------------------------------------------


def test_build_retrieval_item_basic():
    item = build_retrieval_item(
        tool_name="text_length_filter",
        description="Filter by length",
        relevance_score=95.5,
        score_source="llm",
        operator_type="filter",
        key_match=["text", "length"],
    )
    assert item["tool_name"] == "text_length_filter"
    assert item["description"] == "Filter by length"
    assert item["relevance_score"] == 95.5
    assert item["score_source"] == "llm"
    assert item["operator_type"] == "filter"
    assert item["key_match"] == ["text", "length"]


def test_build_retrieval_item_strips_whitespace():
    item = build_retrieval_item(
        tool_name="  text_length_filter  ",
        description="  desc  ",
        score_source="  bm25  ",
        operator_type="  filter  ",
    )
    assert item["tool_name"] == "text_length_filter"
    assert item["description"] == "desc"
    assert item["score_source"] == "bm25"
    assert item["operator_type"] == "filter"


def test_build_retrieval_item_defaults():
    item = build_retrieval_item(tool_name="op_a")
    assert item["description"] == ""
    assert item["relevance_score"] == 0.0
    assert item["score_source"] == ""
    assert item["operator_type"] == ""
    assert item["key_match"] == []


def test_build_retrieval_item_casts_score_to_float():
    item = build_retrieval_item(tool_name="op_a", relevance_score=80)
    assert isinstance(item["relevance_score"], float)
    assert item["relevance_score"] == 80.0


def test_build_retrieval_item_sanitizes_key_match():
    item = build_retrieval_item(
        tool_name="op_a",
        key_match=["  text  ", "", "  length  ", None],
    )
    # None becomes "None" after str(), but empty strings are filtered
    assert "text" in item["key_match"]
    assert "length" in item["key_match"]
    assert "" not in item["key_match"]


def test_build_retrieval_item_none_key_match_becomes_empty_list():
    item = build_retrieval_item(tool_name="op_a", key_match=None)
    assert item["key_match"] == []


def test_build_retrieval_item_non_list_key_match_becomes_empty_list():
    item = build_retrieval_item(tool_name="op_a", key_match="not a list")
    assert item["key_match"] == []


# ---------------------------------------------------------------------------
# names_from_items
# ---------------------------------------------------------------------------


def test_names_from_items_basic():
    items = [
        {"tool_name": "op_a"},
        {"tool_name": "op_b"},
    ]
    assert names_from_items(items) == ["op_a", "op_b"]


def test_names_from_items_skips_empty_names():
    items = [
        {"tool_name": "op_a"},
        {"tool_name": ""},
        {"tool_name": "   "},
        {"tool_name": "op_b"},
    ]
    assert names_from_items(items) == ["op_a", "op_b"]


def test_names_from_items_skips_missing_key():
    items = [
        {"tool_name": "op_a"},
        {"other_key": "value"},
        {"tool_name": "op_b"},
    ]
    assert names_from_items(items) == ["op_a", "op_b"]


def test_names_from_items_empty_list():
    assert names_from_items([]) == []


def test_names_from_items_strips_whitespace():
    items = [{"tool_name": "  op_a  "}]
    assert names_from_items(items) == ["op_a"]


# ---------------------------------------------------------------------------
# filter_by_op_type
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_ops():
    return [
        {"class_name": "text_length_filter", "class_type": "filter"},
        {"class_name": "document_deduplicator", "class_type": "deduplicator"},
        {"class_name": "text_clean_mapper", "class_type": "mapper"},
        {"class_name": "image_size_filter", "class_type": "filter"},
    ]


def test_filter_by_op_type_returns_matching_entries(sample_ops):
    result = filter_by_op_type(sample_ops, "filter")
    names = [r["class_name"] for r in result]
    assert "text_length_filter" in names
    assert "image_size_filter" in names
    assert "document_deduplicator" not in names


def test_filter_by_op_type_is_case_insensitive(sample_ops):
    result = filter_by_op_type(sample_ops, "FILTER")
    names = [r["class_name"] for r in result]
    assert "text_length_filter" in names


def test_filter_by_op_type_none_returns_full_list(sample_ops):
    result = filter_by_op_type(sample_ops, None)
    assert result is sample_ops


def test_filter_by_op_type_empty_string_returns_full_list(sample_ops):
    result = filter_by_op_type(sample_ops, "")
    assert result is sample_ops


def test_filter_by_op_type_fallback_when_no_match(sample_ops):
    """When filter yields nothing, the full list is returned as fallback."""
    result = filter_by_op_type(sample_ops, "nonexistent_type")
    assert result is sample_ops


def test_filter_by_op_type_custom_type_key():
    ops = [
        {"name": "op_a", "type": "filter"},
        {"name": "op_b", "type": "mapper"},
    ]
    result = filter_by_op_type(ops, "filter", type_key="type")
    assert len(result) == 1
    assert result[0]["name"] == "op_a"


def test_filter_by_op_type_empty_list_returns_empty():
    result = filter_by_op_type([], "filter")
    assert result == []


# ---------------------------------------------------------------------------
# trace_step
# ---------------------------------------------------------------------------


def test_trace_step_basic():
    entry = trace_step("llm", "success")
    assert entry == {"backend": "llm", "status": "success"}


def test_trace_step_with_error():
    entry = trace_step("vector", "failed", error="connection timeout")
    assert entry["error"] == "connection timeout"
    assert "reason" not in entry


def test_trace_step_with_reason():
    entry = trace_step("llm", "skipped", reason="missing_api_key")
    assert entry["reason"] == "missing_api_key"
    assert "error" not in entry


def test_trace_step_with_both_error_and_reason():
    entry = trace_step("bm25", "failed", error="err", reason="why")
    assert entry["error"] == "err"
    assert entry["reason"] == "why"


def test_trace_step_empty_error_omitted():
    entry = trace_step("bm25", "success", error="")
    assert "error" not in entry


def test_trace_step_empty_reason_omitted():
    entry = trace_step("bm25", "success", reason="")
    assert "reason" not in entry


def test_trace_step_strips_whitespace():
    entry = trace_step("  llm  ", "  success  ")
    assert entry["backend"] == "llm"
    assert entry["status"] == "success"


def test_trace_step_none_values_become_empty_strings():
    entry = trace_step(None, None)
    assert entry["backend"] == ""
    assert entry["status"] == ""
