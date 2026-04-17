# -*- coding: utf-8 -*-
"""Operator retrieval backend package.

This package contains the backend modules for operator retrieval:

* ``backend``      – thin coordination layer and public API
* ``cache``        – thread-safe cache manager
* ``catalog``      – operator catalog initialization
* ``retriever``    – retrieval backend abstraction and strategy manager
* ``result_builder`` – shared helpers for building result/trace dicts
"""

from .backend import (
    get_op_catalog,
    get_op_searcher,
    init_op_catalog,
    refresh_op_catalog,
    retrieve_ops,
    retrieve_ops_bm25_items,
    retrieve_ops_lm_items,
    retrieve_ops_regex_items,
    retrieve_ops_with_meta,
)
from .cache import cache_manager
from .result_builder import names_from_items

__all__ = [
    "cache_manager",
    "get_op_catalog",
    "get_op_searcher",
    "init_op_catalog",
    "names_from_items",
    "refresh_op_catalog",
    "retrieve_ops",
    "retrieve_ops_bm25_items",
    "retrieve_ops_lm_items",
    "retrieve_ops_regex_items",
    "retrieve_ops_with_meta",
]
