# -*- coding: utf-8 -*-
"""Unit tests for GrepRetriever — pure-Python grep through operator name + description."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Mock data_juicer.tools.op_search BEFORE any data_juicer_agents imports
# ---------------------------------------------------------------------------
_fake_op_search = MagicMock()
_fake_op_search.OPSearcher = MagicMock
sys.modules["data_juicer"] = MagicMock()
sys.modules["data_juicer.tools"] = MagicMock()
sys.modules["data_juicer.tools.op_search"] = _fake_op_search

from data_juicer_agents.tools.retrieve._shared.backend.retriever import (
    GrepRetriever,
    _normalize_grep_score,
)

# ---------------------------------------------------------------------------
# Test catalog (matches real op_catalog structure from catalog.py)
# ---------------------------------------------------------------------------
CATALOG = [
    {
        "class_name": "text_length_filter",
        "class_desc": "Filter text samples by length (min/max).",
        "class_type": "filter",
        "class_tags": ["text"],
    },
    {
        "class_name": "document_deduplicator",
        "class_desc": "Deduplicate documents using MinHash or exact matching.",
        "class_type": "deduplicator",
        "class_tags": ["text"],
    },
    {
        "class_name": "image_resize_mapper",
        "class_desc": "Resize images to target dimensions.",
        "class_type": "mapper",
        "class_tags": ["image"],
    },
    {
        "class_name": "text_normalizer",
        "class_desc": "Normalize text: lowercase, remove accents, etc.",
        "class_type": "mapper",
        "class_tags": ["text"],
    },
    {
        "class_name": "alphanumeric_filter",
        "class_desc": "Filter out samples with too few alphanumeric characters.",
        "class_type": "filter",
        "class_tags": ["text"],
    },
    {
        "class_name": "video_frame_selector",
        "class_desc": "Select key frames from video samples.",
        "class_type": "selector",
        "class_tags": ["video"],
    },
]


def _make_grep(catalog=None):
    retriever = GrepRetriever()
    retriever._get_catalog = lambda: catalog or CATALOG
    return retriever


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

class TestNormalizeGrepScore:
    def test_both_match_high_score(self):
        score = _normalize_grep_score(10, True, True)
        assert score == 0.95

    def test_both_match_single(self):
        score = _normalize_grep_score(1, True, True)
        assert score == 0.55

    def test_name_only(self):
        score = _normalize_grep_score(1, True, False)
        assert score == 0.5

    def test_desc_only(self):
        score = _normalize_grep_score(1, False, True)
        assert score == pytest.approx(0.4)

    def test_multiple_name_hits(self):
        score = _normalize_grep_score(5, True, False)
        assert score == 0.7

    def test_multiple_desc_hits(self):
        score = _normalize_grep_score(8, False, True)
        assert score == 0.70  # capped at 0.70

    def test_no_match_zero(self):
        assert _normalize_grep_score(0, False, False) == 0.0


class TestGrepRetrieverBasics:
    def test_name_property(self):
        r = GrepRetriever()
        assert r.name == "grep"

    def test_is_always_available(self):
        r = GrepRetriever()
        assert r.is_available() is True

    def test_empty_query_returns_empty(self):
        r = _make_grep()
        items = r._gather(r.retrieve_items(""))
        assert items == []

    def test_whitespace_query_returns_empty(self):
        r = _make_grep()
        items = r._gather(r.retrieve_items("   "))
        assert items == []


class TestGrepRetrieverKeywordMatching:
    def test_exact_name_match(self):
        r = _make_grep()
        items = r._gather(r.retrieve_items("text_length_filter"))
        assert len(items) == 1
        assert items[0]["tool_name"] == "text_length_filter"
        assert items[0]["score_source"] == "grep"
        assert items[0]["relevance_score"] > 0.45  # name-only match base 0.5

    def test_partial_name_match_returns_multiple(self):
        r = _make_grep()
        items = r._gather(r.retrieve_items("filter"))
        names = [i["tool_name"] for i in items]
        assert "text_length_filter" in names
        assert "alphanumeric_filter" in names

    def test_case_insensitive_match(self):
        r = _make_grep()
        items = r._gather(r.retrieve_items("TEXT_LENGTH_FILTER"))
        assert len(items) >= 1
        assert items[0]["tool_name"] == "text_length_filter"

    def test_description_match(self):
        r = _make_grep()
        items = r._gather(r.retrieve_items("MinHash"))
        assert len(items) >= 1
        assert items[0]["tool_name"] == "document_deduplicator"

    def test_description_match_finds_correct_operator(self):
        r = _make_grep()
        items = r._gather(r.retrieve_items("resize images to target"))
        assert len(items) >= 1
        assert items[0]["tool_name"] == "image_resize_mapper"

    def test_mixed_name_desc_scores_higher(self):
        r = _make_grep()
        items = r._gather(r.retrieve_items("filter text"))
        # text_length_filter has "filter" in name AND "text" in name+desc
        # alphanumeric_filter has "filter" in name but "text" only in tags
        assert items[0]["tool_name"] == "text_length_filter"


class TestGrepRetrieverRegexMatching:
    def test_regex_metacharacters_used_as_pattern(self):
        r = _make_grep()
        items = r._gather(r.retrieve_items("text.*filter"))
        names = [i["tool_name"] for i in items]
        # text.*filter matches names containing "text" then "filter"
        assert "text_length_filter" in names
        # alphanumeric_filter has no "text" → excluded (correct)
        assert "alphanumeric_filter" not in names

    def test_alternation_regex(self):
        r = _make_grep()
        items = r._gather(r.retrieve_items("image|video"))
        names = [i["tool_name"] for i in items]
        assert "image_resize_mapper" in names
        assert "video_frame_selector" in names

    def test_anchor_start(self):
        r = _make_grep()
        items = r._gather(r.retrieve_items("^text_"))
        names = [i["tool_name"] for i in items]
        assert "text_length_filter" in names
        assert "text_normalizer" in names

    def test_invalid_regex_falls_back_to_escaped_literal(self):
        r = _make_grep()
        items = r._gather(r.retrieve_items("[unclosed"))
        # Should not raise; treats as escaped literal
        # [unclosed won't match normal operator names
        assert items == []

    def test_regex_with_description(self):
        r = _make_grep()
        items = r._gather(r.retrieve_items(r"lowercase|accent"))
        names = [i["tool_name"] for i in items]
        assert "text_normalizer" in names


class TestGrepRetrieverFiltering:
    def test_op_type_filter_only_filters(self):
        r = _make_grep()
        items = r._gather(r.retrieve_items("filter", op_type="filter"))
        names = [i["tool_name"] for i in items]
        # Both filter-type operators have "filter" in name
        assert "text_length_filter" in names
        assert "alphanumeric_filter" in names
        assert "text_normalizer" not in names  # mapper, not filter

    def test_op_type_filter_deduplicator(self):
        r = _make_grep()
        items = r._gather(r.retrieve_items("document", op_type="deduplicator"))
        assert len(items) == 1
        assert items[0]["tool_name"] == "document_deduplicator"

    def test_tags_filter_text_only(self):
        r = _make_grep()
        items = r._gather(r.retrieve_items("filter", tags=["text"]))
        names = [i["tool_name"] for i in items]
        assert "image_resize_mapper" not in names
        assert "video_frame_selector" not in names

    def test_tags_filter_image(self):
        r = _make_grep()
        items = r._gather(r.retrieve_items("resize", tags=["image"]))
        assert len(items) >= 1
        assert items[0]["tool_name"] == "image_resize_mapper"

    def test_combined_op_type_and_tags(self):
        r = _make_grep()
        items = r._gather(r.retrieve_items("filter", op_type="filter", tags=["text"]))
        names = [i["tool_name"] for i in items]
        assert "text_length_filter" in names
        assert "alphanumeric_filter" in names


class TestGrepRetrieverScoring:
    def test_name_match_scores_higher_than_desc_match(self):
        r = _make_grep()
        items = r._gather(r.retrieve_items("selector"))
        # video_frame_selector has "selector" in name → higher score
        # Other operators might have "selector" in description
        if len(items) >= 1:
            assert items[0]["tool_name"] == "video_frame_selector"

    def test_multiple_matches_scored_correctly(self):
        r = _make_grep()
        items = r._gather(r.retrieve_items("text"))
        # text_length_filter, text_normalizer match in name
        # Others may match in desc only
        assert len(items) >= 2
        name_scores = [
            i["relevance_score"]
            for i in items
            if "text" in i["tool_name"]
        ]
        assert all(s >= 0.45 for s in name_scores)

    def test_no_results_for_unrelated_query(self):
        r = _make_grep()
        items = r._gather(r.retrieve_items("zzz_nonexistent_pattern"))
        assert items == []


class TestGrepRetrieverLimit:
    def test_limit_respected(self):
        r = _make_grep()
        items = r._gather(r.retrieve_items("filter", limit=1))
        assert len(items) == 1

    def test_limit_larger_than_matches_returns_all(self):
        r = _make_grep()
        items = r._gather(r.retrieve_items("filter", limit=50))
        # Only 2 filter operators in catalog
        assert len(items) == 2


class TestGrepRetrieverKeyMatch:
    def test_key_match_includes_matched_text(self):
        r = _make_grep()
        items = r._gather(r.retrieve_items("MinHash"))
        assert len(items) >= 1
        assert any("MinHash" in km for km in items[0]["key_match"])

    def test_name_matches_prefixed_with_name_colon(self):
        r = _make_grep()
        items = r._gather(r.retrieve_items("text_normalizer"))
        assert len(items) == 1
        assert any(km.startswith("name:") for km in items[0]["key_match"])

    def test_desc_matches_prefixed_with_desc_colon(self):
        r = _make_grep()
        items = r._gather(r.retrieve_items("dimensions"))
        assert len(items) >= 1
        assert any(km.startswith("desc:") for km in items[0]["key_match"])


# ---------------------------------------------------------------------------
# Integration tests (verify grep is wired into the system)
# ---------------------------------------------------------------------------

class TestGrepIntegration:
    def test_grep_in_local_retrieval_modes(self):
        from data_juicer_agents.tools.retrieve._shared.logic import _LOCAL_RETRIEVAL_MODES
        assert "grep" in _LOCAL_RETRIEVAL_MODES

    def test_grep_in_strategy_backends(self):
        from data_juicer_agents.tools.retrieve._shared.backend.retriever import _strategy
        assert "grep" in _strategy.backends
        assert isinstance(_strategy.backends["grep"], GrepRetriever)

    def test_grep_in_auto_chain(self):
        from data_juicer_agents.tools.retrieve._shared.backend.retriever import _strategy
        assert "grep" in _strategy.auto_chain

    def test_grep_is_last_in_auto_chain(self):
        from data_juicer_agents.tools.retrieve._shared.backend.retriever import _strategy
        assert _strategy.auto_chain[-1] == "grep"

    def test_retrieve_operators_mode_accepts_grep(self):
        from data_juicer_agents.tools.retrieve.retrieve_operators.input import (
            RetrieveOperatorsInput,
        )
        inp = RetrieveOperatorsInput(intent="dedup", mode="grep")
        assert inp.mode == "grep"

    def test_all_backends_are_available(self):
        from data_juicer_agents.tools.retrieve._shared.backend.retriever import _strategy
        for name, backend in _strategy.backends.items():
            if name == "llm":
                continue  # LLM may be unavailable without API key
            assert backend.is_available(), f"{name} backend should be available"


# ---------------------------------------------------------------------------
# Helper: run async in sync context
# ---------------------------------------------------------------------------

def _gather(coro):
    import asyncio
    return asyncio.run(coro)

GrepRetriever._gather = staticmethod(_gather)  # type: ignore[attr-defined]
