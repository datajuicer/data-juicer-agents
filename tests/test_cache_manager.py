# -*- coding: utf-8 -*-
"""Unit tests for RetrievalCacheManager."""

import threading

import pytest

from data_juicer_agents.tools.retrieve._shared.backend.cache import (
    CK_OP_CATALOG,
    CK_OP_SEARCHER,
    RetrievalCacheManager,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mgr():
    """Return a fresh RetrievalCacheManager for each test."""
    return RetrievalCacheManager()


# ---------------------------------------------------------------------------
# get / set
# ---------------------------------------------------------------------------


def test_get_returns_none_for_missing_key(mgr):
    assert mgr.get("nonexistent") is None


def test_set_and_get_roundtrip(mgr):
    mgr.set("key1", "value1")
    assert mgr.get("key1") == "value1"


def test_set_overwrites_existing_value(mgr):
    mgr.set("key1", "old")
    mgr.set("key1", "new")
    assert mgr.get("key1") == "new"


def test_set_stores_arbitrary_objects(mgr):
    obj = {"nested": [1, 2, 3]}
    mgr.set("obj", obj)
    assert mgr.get("obj") is obj


# ---------------------------------------------------------------------------
# content hash
# ---------------------------------------------------------------------------


def test_get_hash_returns_empty_string_when_not_set(mgr):
    assert mgr.get_hash("key1") == ""


def test_set_with_content_hash_stores_hash(mgr):
    mgr.set("key1", "value", content_hash="abc123")
    assert mgr.get_hash("key1") == "abc123"


def test_set_without_content_hash_does_not_overwrite_existing_hash(mgr):
    mgr.set("key1", "v1", content_hash="hash1")
    mgr.set("key1", "v2")  # no hash provided
    # Hash should remain unchanged because empty string is falsy
    assert mgr.get_hash("key1") == "hash1"


# ---------------------------------------------------------------------------
# is_stale
# ---------------------------------------------------------------------------


def test_is_stale_returns_true_when_no_hash_stored(mgr):
    assert mgr.is_stale("key1", "somehash") is True


def test_is_stale_returns_false_when_hash_matches(mgr):
    mgr.set("key1", "value", content_hash="abc")
    assert mgr.is_stale("key1", "abc") is False


def test_is_stale_returns_true_when_hash_differs(mgr):
    mgr.set("key1", "value", content_hash="abc")
    assert mgr.is_stale("key1", "xyz") is True


# ---------------------------------------------------------------------------
# invalidate
# ---------------------------------------------------------------------------


def test_invalidate_removes_value_and_hash(mgr):
    mgr.set("key1", "value", content_hash="h1")
    mgr.invalidate("key1")
    assert mgr.get("key1") is None
    assert mgr.get_hash("key1") == ""


def test_invalidate_nonexistent_key_is_noop(mgr):
    mgr.invalidate("ghost")  # should not raise


def test_invalidate_does_not_affect_other_keys(mgr):
    mgr.set("a", 1, content_hash="ha")
    mgr.set("b", 2, content_hash="hb")
    mgr.invalidate("a")
    assert mgr.get("b") == 2
    assert mgr.get_hash("b") == "hb"


# ---------------------------------------------------------------------------
# invalidate_all
# ---------------------------------------------------------------------------


def test_invalidate_all_clears_everything(mgr):
    mgr.set(CK_OP_SEARCHER, "os")
    mgr.set(CK_OP_CATALOG, "dfi")
    mgr.invalidate_all()
    for key in (CK_OP_SEARCHER, CK_OP_CATALOG):
        assert mgr.get(key) is None
        assert mgr.get_hash(key) == ""


def test_invalidate_all_on_empty_manager_is_noop(mgr):
    mgr.invalidate_all()  # should not raise


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------


def test_concurrent_set_and_get_are_thread_safe(mgr):
    """Multiple threads writing different keys should not corrupt state."""
    errors = []

    def writer(key, value):
        try:
            for _ in range(100):
                mgr.set(key, value)
                result = mgr.get(key)
                # The value we read back must be one of the values written by
                # any thread (all are strings here, so just check type).
                assert isinstance(result, str)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(f"k{i}", f"v{i}")) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"Thread errors: {errors}"


def test_concurrent_invalidate_all_does_not_raise(mgr):
    """invalidate_all called concurrently with set should not raise."""
    errors = []

    def setter():
        try:
            for i in range(50):
                mgr.set(f"k{i}", i)
        except Exception as exc:
            errors.append(exc)

    def invalidator():
        try:
            for _ in range(50):
                mgr.invalidate_all()
        except Exception as exc:
            errors.append(exc)

    threads = [
        threading.Thread(target=setter),
        threading.Thread(target=invalidator),
        threading.Thread(target=setter),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"Thread errors: {errors}"


# ---------------------------------------------------------------------------
# Module-level singleton smoke test
# ---------------------------------------------------------------------------


def test_module_singleton_is_accessible():
    """Verify the module-level cache_manager singleton is importable."""
    from data_juicer_agents.tools.retrieve._shared.backend.cache import cache_manager
    assert cache_manager is not None
