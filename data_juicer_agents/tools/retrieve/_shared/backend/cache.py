# -*- coding: utf-8 -*-
"""Thread-safe cache manager for retrieval backends."""

from __future__ import annotations

import threading
from typing import Any

class RetrievalCacheManager:
    """Thread-safe cache for retrieval backends.

    Replaces the scattered module-level global variables previously used in
    backend.py (``_cached_op_searcher``,
    ``_global_op_catalog``).
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._store: dict[str, Any] = {}
        self._hashes: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str) -> Any:
        """Return the cached value for *key*, or ``None`` if absent."""
        with self._lock:
            return self._store.get(key)

    def set(self, key: str, value: Any, content_hash: str = "") -> None:
        """Store *value* under *key*, optionally recording *content_hash*."""
        with self._lock:
            self._store[key] = value
            if content_hash:
                self._hashes[key] = content_hash

    def get_hash(self, key: str) -> str:
        """Return the content hash recorded for *key*, or empty string."""
        with self._lock:
            return self._hashes.get(key, "")

    def invalidate(self, key: str) -> None:
        """Remove a single cache entry and its associated hash."""
        with self._lock:
            self._store.pop(key, None)
            self._hashes.pop(key, None)

    def invalidate_all(self) -> None:
        """Clear all cached values and hashes."""
        with self._lock:
            self._store.clear()
            self._hashes.clear()

    def is_stale(self, key: str, content_hash: str) -> bool:
        """Return ``True`` when the stored hash for *key* differs from *content_hash*."""
        with self._lock:
            return self._hashes.get(key, "") != content_hash

# ---------------------------------------------------------------------------
# Cache key constants
# ---------------------------------------------------------------------------

CK_OP_SEARCHER = "op_searcher"
CK_OP_CATALOG = "op_catalog"

# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

cache_manager = RetrievalCacheManager()
