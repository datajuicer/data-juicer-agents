# -*- coding: utf-8 -*-
"""Operator retrieval backend: data-source management and public API.

This module is now a thin coordination layer.  The heavy lifting has been
moved to dedicated modules:

* ``cache.py``         – thread-safe cache manager (replaces global variables)
* ``result_builder.py``– shared helpers for building result/trace dicts
* ``retriever.py``     – RetrieverBackend ABC, four concrete backends,
                          and RetrievalStrategy (replaces the large
                          if/elif block in retrieve_ops_with_meta)

Public surface kept for backward-compatibility with existing callers and tests
that monkeypatch individual retrieval functions:
  retrieve_ops_lm_items, retrieve_ops_lm,
  retrieve_ops_bm25_items, retrieve_ops_bm25,
  retrieve_ops_regex_items, retrieve_ops_regex,
  retrieve_ops_with_meta, retrieve_ops
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from .cache import CK_OP_CATALOG, CK_OP_SEARCHER, cache_manager
from .catalog import build_op_catalog, create_op_searcher
from .retriever import _strategy

# ---------------------------------------------------------------------------
# op_catalog lifecycle
# ---------------------------------------------------------------------------

def init_op_catalog() -> bool:
    """Initialize op_catalog at agent startup."""
    try:
        logging.info("Initializing op_catalog for agent lifecycle...")
        searcher = get_op_searcher()
        op_catalog = build_op_catalog(searcher)
        cache_manager.set(CK_OP_CATALOG, op_catalog)
        logging.info(
            "Successfully initialized op_catalog with %d operators",
            len(op_catalog),
        )
        return True
    except Exception as e:
        logging.error(f"Failed to initialize op_catalog: {e}")
        return False

def refresh_op_catalog() -> bool:
    """Refresh op_catalog during agent runtime (for manual updates)."""
    try:
        logging.info("Refreshing op_catalog...")
        # Keep a single source of truth: invalidate cached catalog/searcher
        # and repopulate through get_op_catalog().
        cache_manager.invalidate(CK_OP_CATALOG)
        cache_manager.invalidate(CK_OP_SEARCHER)
        try:
            from ..operator_registry import get_available_operator_names

            get_available_operator_names.cache_clear()
        except Exception:
            # Registry cache clear is best-effort and should not block refresh.
            pass
        op_catalog = get_op_catalog()
        logging.info(
            "Successfully refreshed op_catalog with %d operators",
            len(op_catalog),
        )
        return True
    except Exception as e:
        logging.error(f"Failed to refresh op_catalog: {e}")
        return False

def get_op_catalog() -> list:
    """Return current op_catalog (lifecycle-aware)."""
    cached = cache_manager.get(CK_OP_CATALOG)
    if cached is None:
        logging.warning("op_catalog not initialized, initializing now...")
        if not init_op_catalog():
            raise RuntimeError("op_catalog initialization failed")
        cached = cache_manager.get(CK_OP_CATALOG)
        if cached is None:
            raise RuntimeError("op_catalog cache missing after successful initialization")
    return cached


def get_op_searcher():
    """Return cached OPSearcher, creating it on first use."""
    cached = cache_manager.get(CK_OP_SEARCHER)
    if cached is not None:
        return cached
    searcher = create_op_searcher()
    cache_manager.set(CK_OP_SEARCHER, searcher)
    return searcher

# ---------------------------------------------------------------------------
# Thin wrappers – kept so existing tests can monkeypatch these names
# ---------------------------------------------------------------------------

async def retrieve_ops_lm_items(
    user_query: str,
    limit: int = 20,
    op_type: Optional[str] = None,
) -> List[dict]:
    """Thin wrapper: delegates to LLMRetriever.retrieve_items."""
    return await _strategy.backends["llm"].retrieve_items(user_query, limit=limit, op_type=op_type)

def retrieve_ops_bm25_items(
    user_query: str,
    limit: int = 20,
    op_type: Optional[str] = None,
) -> List[dict]:
    """Thin wrapper: BM25 retrieval – returns list of item dicts.

    Note: synchronous wrapper around the async backend for backward compat.
    """
    import asyncio

    async def _run():
        return await _strategy.backends["bm25"].retrieve_items(user_query, limit=limit, op_type=op_type)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, _run())
                return future.result()
        return loop.run_until_complete(_run())
    except RuntimeError:
        return asyncio.run(_run())

def retrieve_ops_regex_items(
    user_query: str,
    limit: int = 20,
    op_type: Optional[str] = None,
) -> List[dict]:
    """Thin wrapper: regex retrieval – returns list of item dicts.

    Note: synchronous wrapper around the async backend for backward compat.
    """
    import asyncio

    async def _run():
        return await _strategy.backends["regex"].retrieve_items(user_query, limit=limit, op_type=op_type)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, _run())
                return future.result()
        return loop.run_until_complete(_run())
    except RuntimeError:
        return asyncio.run(_run())

# ---------------------------------------------------------------------------
# Primary public API
# ---------------------------------------------------------------------------

async def retrieve_ops_with_meta(
    user_query: str,
    limit: int = 20,
    mode: str = "auto",
    op_type: Optional[str] = None,
    tags: Optional[list] = None,
) -> dict[str, Any]:
    """Tool retrieval with source/trace metadata.

    Delegates entirely to RetrievalStrategy.execute().

    Args:
        user_query: User query string.
        limit: Maximum number of tools to retrieve.
        mode: Retrieval mode – "llm", "bm25", "regex", or "auto".
        op_type: Optional operator type filter (e.g. "filter", "mapper").
        tags: List of tags to match.
    """
    return await _strategy.execute(user_query, limit=limit, mode=mode, op_type=op_type, tags=tags)

async def retrieve_ops(
    user_query: str,
    limit: int = 20,
    mode: str = "auto",
    op_type: Optional[str] = None,
) -> list:
    """Tool retrieval – returns list of tool names.

    Args:
        user_query: User query string.
        limit: Maximum number of tools to retrieve.
        mode: Retrieval mode – "llm", "bm25", "regex", or "auto".
        op_type: Optional operator type filter.
    """
    meta = await retrieve_ops_with_meta(
        user_query=user_query,
        limit=limit,
        mode=mode,
        op_type=op_type,
    )
    return list(meta.get("names", []))
