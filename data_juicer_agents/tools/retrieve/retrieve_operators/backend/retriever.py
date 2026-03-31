# -*- coding: utf-8 -*-
"""Retrieval backend abstraction and strategy manager.

Architecture
------------
RetrieverBackend (ABC)
    ├── LLMRetriever      – uses DashScope LLM for semantic ranking
    ├── VectorRetriever   – uses FAISS + DashScope embeddings
    ├── BM25Retriever     – uses Data-Juicer OPSearcher BM25
    └── RegexRetriever    – uses Data-Juicer OPSearcher regex

RetrievalStrategy
    Holds a registry of backends and implements the "auto" fallback chain
    (llm → vector → bm25), replacing the large if/elif block that was
    previously in ``retrieve_ops_with_meta``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import os.path as osp
import re
import time
from abc import ABC, abstractmethod
from typing import Any

from .cache import (
    CK_OP_SEARCHER,
    CK_TOOLS_INFO,
    CK_VECTOR_STORE,
    cache_manager,
)
from .result_builder import (
    build_retrieval_item,
    filter_by_op_type,
    filter_by_tags,
    names_from_items,
    trace_step,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

VECTOR_INDEX_CACHE_PATH = osp.join(osp.dirname(__file__), "vector_index_cache")

RETRIEVAL_PROMPT = """You are a professional tool retrieval assistant responsible for filtering the top {limit} most relevant tools from a large tool library based on user requirements. Execute the following steps:

# Requirement Analysis
    Carefully read the user's [requirement description], extract core keywords, functional objectives, usage scenarios, and technical requirements (such as real-time performance, data types, industry domains, etc.).

# Tool Matching
    Perform multi-dimensional matching based on the following tool attributes:
    - Tool name and functional description
    - Supported input/output formats
    - Applicable industry or scenario tags
    - Technical implementation principles (API, local deployment, AI model types)
    - Relevance ranking

# Use weighted scoring mechanism (example weights):
    - Functional match (40%)
    - Scenario compatibility (30%)
    - Technical compatibility (20%)
    - User rating/usage rate (10%)

# Deduplication and Optimization
    Exclude the following low-quality results:
    - Tools with duplicate functionality (keep only the best one)
    - Tools that cannot meet basic requirements
    - Tools missing critical parameter descriptions

# Constraints
    - Strictly control output to a maximum of {limit} tools
    - Refuse to speculate on unknown tool attributes
    - Maintain accuracy of domain expertise

# Output Format
    Return a JSON format TOP{limit} tool list containing:
    [
        {{
            "rank": 1,
            "tool_name": "Tool Name",
            "description": "Core functionality summary",
            "relevance_score": 98.7,
            "key_match": ["Matching keywords/features"]
        }}
    ]
    Output strictly in JSON array format, and only output the JSON array format tool list.
"""

_WORD_RE = re.compile(r"[a-zA-Z0-9_]+")


def _has_retrieval_api_key() -> bool:
    return bool(
        (os.environ.get("DASHSCOPE_API_KEY") or "").strip()
        or (os.environ.get("MODELSCOPE_API_TOKEN") or "").strip()
    )


def _normalize_bm25_score(rank: int, limit: int) -> float:
    if rank <= 0:
        return 0.0
    span = max(int(limit), 1)
    return round(max(0.0, (span - rank + 1) * 100.0 / span), 2)


def _query_tokens(text: str) -> set[str]:
    return {tok.lower() for tok in _WORD_RE.findall(str(text or ""))}


def _extract_key_match(query: str, name: str, desc: str, tags: list[str]) -> list[str]:
    query_tokens = _query_tokens(query)
    if not query_tokens:
        return []
    joined = " ".join([str(name or ""), str(desc or ""), " ".join(tags or [])]).lower()
    return [token for token in sorted(query_tokens) if token in joined][:5]


def _get_content_hash(op_catalog: list) -> str:
    try:
        content_str = json.dumps(op_catalog, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(content_str.encode("utf-8")).hexdigest()
    except Exception as e:
        logging.warning(f"Failed to compute content hash: {e}")
        return ""


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------


class RetrieverBackend(ABC):
    """Abstract base class for operator retrieval backends."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Backend identifier used in trace/source fields."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return ``True`` if this backend can serve queries right now."""

    @abstractmethod
    async def retrieve_items(
        self,
        query: str,
        limit: int = 20,
        op_type: str | None = None,
        tags: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return a list of retrieval item dicts (``build_retrieval_item`` format)."""


# ---------------------------------------------------------------------------
# LLM backend
# ---------------------------------------------------------------------------


class LLMRetriever(RetrieverBackend):
    """Retrieval via DashScope LLM semantic ranking."""

    @property
    def name(self) -> str:
        return "llm"

    def is_available(self) -> bool:
        return _has_retrieval_api_key()

    async def retrieve_items(
        self,
        query: str,
        limit: int = 20,
        op_type: str | None = None,
        tags: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        from .backend import get_op_catalog  # avoid circular at module level

        op_catalog = get_op_catalog()
        op_catalog = filter_by_op_type(op_catalog, op_type)
        op_catalog = filter_by_tags(op_catalog, tags)

        tool_descriptions = [
            f"{t['class_name']}: {t['class_desc']}" for t in op_catalog
        ]
        tools_string = "\n".join(tool_descriptions)

        from agentscope.formatter import DashScopeChatFormatter
        from agentscope.message import Msg
        from agentscope.model import DashScopeChatModel

        model = DashScopeChatModel(
            model_name="qwen-turbo",
            api_key=os.environ.get("DASHSCOPE_API_KEY"),
            stream=False,
        )
        formatter = DashScopeChatFormatter()

        prompt = RETRIEVAL_PROMPT.format(limit=limit) + (
            "\nUser requirement description:\n{query}\n\nAvailable tools:\n{tools}"
        ).format(query=query, tools=tools_string)

        msgs = [Msg(name="user", role="user", content=prompt)]
        formatted_msgs = await formatter.format(msgs)
        response = await model(formatted_msgs)

        msg = Msg(name="assistant", role="assistant", content=response.content)
        retrieved_tools = json.loads(msg.get_text_content())

        # Build a fast lookup for class_type
        type_map = {t["class_name"]: t.get("class_type", "") for t in op_catalog}
        name_set = {t["class_name"] for t in op_catalog}

        valid_tools: list[dict[str, Any]] = []
        for tool_info in retrieved_tools:
            if not isinstance(tool_info, dict) or "tool_name" not in tool_info:
                logging.warning(f"Invalid tool info format: {tool_info}")
                continue
            tool_name = str(tool_info["tool_name"]).strip()
            if not tool_name:
                continue
            if tool_name not in name_set:
                logging.error(f"Tool not found: `{tool_name}`, skipping!")
                continue
            valid_tools.append(
                build_retrieval_item(
                    tool_name=tool_name,
                    description=tool_info.get("description", ""),
                    relevance_score=tool_info.get("relevance_score", 0.0),
                    score_source="llm",
                    operator_type=type_map.get(tool_name, ""),
                    key_match=tool_info.get("key_match", []),
                )
            )
        return valid_tools


# ---------------------------------------------------------------------------
# Vector backend
# ---------------------------------------------------------------------------


class VectorRetriever(RetrieverBackend):
    """Retrieval via FAISS vector similarity search."""

    @property
    def name(self) -> str:
        return "vector"

    def is_available(self) -> bool:
        return _has_retrieval_api_key()

    # ------------------------------------------------------------------
    # Index management (delegated to cache_manager)
    # ------------------------------------------------------------------

    def _get_vector_store(self):
        return cache_manager.get(CK_VECTOR_STORE)

    def _get_tools_info(self):
        return cache_manager.get(CK_TOOLS_INFO)

    def _ensure_index(self) -> None:
        """Load from disk cache or build a fresh index."""
        if self._get_vector_store() is not None and self._get_tools_info() is not None:
            return
        if not self._load_cached_index():
            logging.info("Building new vector index...")
            self._build_vector_index()

    def _load_cached_index(self) -> bool:
        from .backend import get_op_catalog  # avoid circular at module level

        try:
            op_catalog = get_op_catalog()

            # Fast path: same object identity + hash already stored
            stored_hash = cache_manager.get_hash(CK_VECTOR_STORE)
            if stored_hash and cache_manager.get(CK_TOOLS_INFO) is op_catalog:
                return cache_manager.get(CK_VECTOR_STORE) is not None

            current_hash = _get_content_hash(op_catalog)
            if not current_hash:
                return False

            os.makedirs(VECTOR_INDEX_CACHE_PATH, exist_ok=True)
            index_path = osp.join(VECTOR_INDEX_CACHE_PATH, "faiss_index")
            metadata_path = osp.join(VECTOR_INDEX_CACHE_PATH, "metadata.json")

            if not all(os.path.exists(p) for p in [index_path, metadata_path]):
                return False

            with open(metadata_path, "r") as f:
                metadata = json.load(f)

            if current_hash != metadata.get("content_hash", ""):
                logging.info("Content hash mismatch, need to rebuild index")
                return False

            from langchain_community.embeddings import DashScopeEmbeddings
            from langchain_community.vectorstores import FAISS

            embeddings = DashScopeEmbeddings(
                dashscope_api_key=os.environ.get("DASHSCOPE_API_KEY"),
                model="text-embedding-v3",
            )
            vector_store = FAISS.load_local(
                index_path,
                embeddings,
                allow_dangerous_deserialization=True,
            )
            cache_manager.set(CK_VECTOR_STORE, vector_store, content_hash=current_hash)
            cache_manager.set(CK_TOOLS_INFO, op_catalog)
            logging.info("Successfully loaded cached vector index")
            return True

        except Exception as e:
            logging.warning(f"Failed to load cached index: {e}")
            return False

    def _build_vector_index(self) -> None:
        from .backend import get_op_catalog  # avoid circular at module level

        from langchain_community.embeddings import DashScopeEmbeddings
        from langchain_community.vectorstores import FAISS

        op_catalog = get_op_catalog()
        tool_descriptions = [
            f"{t['class_name']}: {t['class_desc']}" for t in op_catalog
        ]
        embeddings = DashScopeEmbeddings(
            dashscope_api_key=os.environ.get("DASHSCOPE_API_KEY"),
            model="text-embedding-v3",
        )
        metadatas = [{"index": i} for i in range(len(tool_descriptions))]
        vector_store = FAISS.from_texts(
            tool_descriptions, embeddings, metadatas=metadatas
        )

        content_hash = _get_content_hash(op_catalog)
        cache_manager.set(CK_VECTOR_STORE, vector_store, content_hash=content_hash)
        cache_manager.set(CK_TOOLS_INFO, op_catalog)

        # Persist to disk
        try:
            os.makedirs(VECTOR_INDEX_CACHE_PATH, exist_ok=True)
            index_path = osp.join(VECTOR_INDEX_CACHE_PATH, "faiss_index")
            metadata_path = osp.join(VECTOR_INDEX_CACHE_PATH, "metadata.json")
            vector_store.save_local(index_path)
            with open(metadata_path, "w") as f:
                json.dump({"content_hash": content_hash, "created_at": time.time()}, f)
            logging.info("Successfully built and cached vector index")
        except Exception as e:
            logging.error(f"Failed to save cached index: {e}")

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    async def retrieve_items(
        self,
        query: str,
        limit: int = 20,
        op_type: str | None = None,
        tags: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        self._ensure_index()

        vector_store = self._get_vector_store()
        tools_info = self._get_tools_info()

        # Over-fetch when filtering to compensate for post-filter drops
        search_k = limit * 3 if (op_type or tags) else limit
        retrieved_docs = vector_store.similarity_search(query, k=search_k)

        # Pre-compute the filtered index set for fast lookup
        filtered_catalog = filter_by_op_type(tools_info, op_type)
        filtered_catalog = filter_by_tags(filtered_catalog, tags)
        allowed_names = {t["class_name"] for t in filtered_catalog}

        tool_names: list[str] = []
        for doc in retrieved_docs:
            raw_idx = doc.metadata["index"]
            tool_info = tools_info[raw_idx]
            if tool_info["class_name"] not in allowed_names:
                continue
            tool_names.append(tool_info["class_name"])
            if len(tool_names) >= limit:
                break

        # Vector backend returns names only; wrap in minimal item dicts
        return [
            build_retrieval_item(
                tool_name=name,
                score_source="vector",
            )
            for name in tool_names
        ]


# ---------------------------------------------------------------------------
# BM25 backend
# ---------------------------------------------------------------------------


class BM25Retriever(RetrieverBackend):
    """Retrieval via Data-Juicer OPSearcher BM25."""

    @property
    def name(self) -> str:
        return "bm25"

    def is_available(self) -> bool:
        return True  # No API key required

    def _get_searcher(self):
        searcher = cache_manager.get(CK_OP_SEARCHER)
        if searcher is not None:
            return searcher
        from .catalog import searcher as catalog_searcher

        cache_manager.set(CK_OP_SEARCHER, catalog_searcher)
        return catalog_searcher

    async def retrieve_items(
        self,
        query: str,
        limit: int = 20,
        op_type: str | None = None,
        tags: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        searcher = self._get_searcher()
        # Pass op_type and tags directly to OPSearcher for pre-filtering
        ranked = searcher.search_by_bm25(
            query=query,
            top_k=limit,
            tags=tags or None,
            op_type=op_type or None,
        )

        valid_rows = [r for r in ranked if isinstance(r, dict)]

        items: list[dict[str, Any]] = []
        for rank, row in enumerate(valid_rows, start=1):
            tool_name = str(row.get("name", "")).strip()
            if not tool_name:
                continue
            desc = str(row.get("desc", "")).strip()
            row_tags = row.get("tags", [])
            items.append(
                build_retrieval_item(
                    tool_name=tool_name,
                    description=desc,
                    relevance_score=_normalize_bm25_score(rank, limit),
                    score_source="bm25_rank",
                    operator_type=str(row.get("type", "")).strip(),
                    key_match=_extract_key_match(
                        query, tool_name, desc,
                        row_tags if isinstance(row_tags, list) else [],
                    ),
                )
            )
            if len(items) >= limit:
                break
        return items


# ---------------------------------------------------------------------------
# Regex backend
# ---------------------------------------------------------------------------


class RegexRetriever(RetrieverBackend):
    """Retrieval via Data-Juicer OPSearcher regex pattern matching."""

    @property
    def name(self) -> str:
        return "regex"

    def is_available(self) -> bool:
        return True  # No API key required

    def _get_searcher(self):
        searcher = cache_manager.get(CK_OP_SEARCHER)
        if searcher is not None:
            return searcher
        from .catalog import searcher as catalog_searcher

        cache_manager.set(CK_OP_SEARCHER, catalog_searcher)
        return catalog_searcher

    async def retrieve_items(
        self,
        query: str,
        limit: int = 20,
        op_type: str | None = None,
        tags: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        searcher = self._get_searcher()
        # Pass op_type and tags directly to OPSearcher for pre-filtering
        matched = searcher.search_by_regex(
            query=query,
            fields=["name"],
            tags=tags or None,
            op_type=op_type or None,
        )

        valid_rows = [r for r in matched if isinstance(r, dict)]

        items: list[dict[str, Any]] = []
        for rank, row in enumerate(valid_rows, start=1):
            tool_name = str(row.get("name", "")).strip()
            if not tool_name:
                continue
            desc = str(row.get("desc", "")).strip()
            row_tags = row.get("tags", [])
            items.append(
                build_retrieval_item(
                    tool_name=tool_name,
                    description=desc,
                    relevance_score=_normalize_bm25_score(rank, limit),
                    score_source="regex_rank",
                    operator_type=str(row.get("type", "")).strip(),
                    key_match=_extract_key_match(
                        query, tool_name, desc,
                        row_tags if isinstance(row_tags, list) else [],
                    ),
                )
            )
            if len(items) >= limit:
                break
        return items


# ---------------------------------------------------------------------------
# Strategy manager
# ---------------------------------------------------------------------------


class RetrievalStrategy:
    """Manages retrieval backend selection and fallback chain.

    For ``mode="auto"``, backends are tried in order: llm → vector → bm25.
    Unavailable backends are skipped (recorded in trace); failed backends
    trigger fallback to the next one.
    """

    def __init__(self) -> None:
        self.backends: dict[str, RetrieverBackend] = {
            "llm": LLMRetriever(),
            "vector": VectorRetriever(),
            "bm25": BM25Retriever(),
            "regex": RegexRetriever(),
        }
        self.auto_chain: list[str] = ["llm", "vector", "bm25"]

    async def execute(
        self,
        query: str,
        limit: int = 20,
        mode: str = "auto",
        op_type: str | None = None,
        tags: list | None = None,
    ) -> dict[str, Any]:
        """Execute retrieval with the specified mode and return a metadata dict."""
        if mode == "auto":
            return await self._run_auto(query, limit, op_type, tags)
        return await self._run_single(mode, query, limit, op_type, tags)

    async def _run_single(
        self,
        mode: str,
        query: str,
        limit: int,
        op_type: str | None,
        tags: list | None = None,
    ) -> dict[str, Any]:
        backend = self.backends.get(mode)
        if not backend:
            raise ValueError(
                f"Invalid mode: {mode!r}. Must be one of: "
                + ", ".join(repr(k) for k in self.backends)
            )
        trace: list[dict] = []
        if not backend.is_available():
            trace.append(trace_step(mode, "failed", reason="missing_api_key"))
            return {"names": [], "source": "", "trace": trace, "items": []}
        try:
            items = await backend.retrieve_items(query, limit, op_type, tags=tags)
            names = names_from_items(items)
            status = "success" if names else "empty"
            trace.append(trace_step(mode, status))
            return {
                "names": names,
                "source": mode if names else "",
                "trace": trace,
                "items": items,
            }
        except Exception as exc:
            logging.error(f"{mode} retrieval failed: {exc}")
            trace.append(trace_step(mode, "failed", str(exc)))
            return {"names": [], "source": "", "trace": trace, "items": []}

    async def _run_auto(
        self,
        query: str,
        limit: int,
        op_type: str | None,
        tags: list | None,
    ) -> dict[str, Any]:
        trace: list[dict] = []
        for backend_name in self.auto_chain:
            backend = self.backends[backend_name]
            if not backend.is_available():
                reason = (
                    "missing_api_key"
                    if backend_name in ("llm", "vector")
                    else "unavailable"
                )
                trace.append(trace_step(backend_name, "skipped", reason=reason))
                continue
            try:
                items = await backend.retrieve_items(query, limit, op_type, tags=tags)
                names = names_from_items(items)
                if names:
                    trace.append(trace_step(backend_name, "success"))
                    return {
                        "names": names,
                        "source": backend_name,
                        "trace": trace,
                        "items": items,
                    }
                trace.append(trace_step(backend_name, "empty"))
            except Exception as exc:
                logging.warning(
                    "%s retrieval failed in auto mode (%s), trying next backend.",
                    backend_name,
                    exc,
                )
                trace.append(trace_step(backend_name, "failed", str(exc)))

        return {"names": [], "source": "", "trace": trace, "items": []}


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_strategy = RetrievalStrategy()
