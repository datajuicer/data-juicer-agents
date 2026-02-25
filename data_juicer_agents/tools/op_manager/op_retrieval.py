# -*- coding: utf-8 -*-
import os
import os.path as osp
import json
import logging
import hashlib
import time
from typing import Optional

from langchain_community.vectorstores import FAISS
from rank_bm25 import BM25Okapi
import re

# ============================================================================
# Configuration Constants
# ============================================================================

# --- Paths ---
CACHE_RETRIEVED_TOOLS_PATH = osp.join(osp.dirname(__file__), "cache_retrieve")
VECTOR_INDEX_CACHE_PATH = osp.join(osp.dirname(__file__), "vector_index_cache")

# --- Embedding Model ---
EMBEDDING_MODEL = "text-embedding-v3"

# --- Vector Search ---
VECTOR_SEARCH_DEFAULT_LIMIT = 20
VECTOR_SIMILARITY_THRESHOLD = 0.25  # minimum cosine similarity to include

# --- BM25 Search ---
BM25_DEFAULT_LIMIT = 20
BM25_SCORE_THRESHOLD = 0.7  # minimum BM25 score to include

# --- Hybrid Search (RRF) ---
HYBRID_DEFAULT_LIMIT = 20
HYBRID_VECTOR_WEIGHT = 1.0  # RRF weight for vector search ranks
HYBRID_BM25_WEIGHT = 2.0  # RRF weight for BM25 ranks (higher = favour lexical)
HYBRID_TOP_K_MULTIPLIER = 3  # per-retriever fetch size = limit * multiplier
HYBRID_SCORE_THRESHOLD = 0.03  # minimum fused RRF score to include
HYBRID_BM25_SCORE_THRESHOLD = 0.7  # BM25 threshold used inside hybrid retrieval

# --- Regex Search ---
REGEX_DEFAULT_LIMIT = 20
REGEX_MAX_PATTERN_LENGTH = 200  # maximum allowed regex pattern length

# ============================================================================
# Global Caches
# ============================================================================

_cached_bm25: Optional[BM25Okapi] = None
_cached_bm25_tools_info: Optional[list] = None

_cached_vector_store: Optional[FAISS] = None
_cached_tools_info: Optional[list] = None
_cached_content_hash: Optional[str] = None

_global_dj_func_info: Optional[list] = None


# ============================================================================
# Utilities
# ============================================================================


def _tokenize(text: str) -> list:
    text = re.sub(r"([A-Z])", r" \1", text)
    text = re.sub(r"[_\-/]", " ", text)
    return [w.lower() for w in text.split() if w]


def fast_text_encoder(text: str) -> str:
    """Fast encoding using xxHash algorithm"""
    import xxhash

    hasher = xxhash.xxh64(seed=0)
    hasher.update(text.encode("utf-8"))
    return hasher.hexdigest()


def _get_content_hash(dj_func_info: list) -> str:
    """Get content hash of dj_func_info using SHA256"""
    try:
        content_str = json.dumps(dj_func_info, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(content_str.encode("utf-8")).hexdigest()
    except Exception as e:
        logging.warning(f"Failed to compute content hash: {e}")
        return ""


# ============================================================================
# dj_func_info Lifecycle Management
# ============================================================================


def init_dj_func_info():
    """Initialize dj_func_info at agent startup"""
    global _global_dj_func_info

    try:
        logging.info("Initializing dj_func_info for agent lifecycle...")
        from .create_dj_func_info import dj_func_info

        _global_dj_func_info = dj_func_info
        logging.info(
            f"Successfully initialized dj_func_info with "
            f"{len(_global_dj_func_info)} operators"
        )
        return True
    except Exception as e:
        logging.error(f"Failed to initialize dj_func_info: {e}")
        return False


def refresh_dj_func_info():
    """Refresh dj_func_info during agent runtime (for manual updates)"""
    global _global_dj_func_info, _cached_vector_store, _cached_tools_info, _cached_content_hash

    try:
        logging.info("Refreshing dj_func_info...")

        _cached_vector_store = None
        _cached_tools_info = None
        _cached_content_hash = None

        import importlib
        from . import create_dj_func_info
        from data_juicer import ops

        importlib.reload(ops)
        importlib.reload(create_dj_func_info)
        dj_func_info = get_dj_func_info()

        _global_dj_func_info = dj_func_info
        logging.info(
            f"Successfully refreshed dj_func_info with "
            f"{len(_global_dj_func_info)} operators"
        )
        return True
    except Exception as e:
        import traceback

        traceback.print_exc()
        logging.error(f"Failed to refresh dj_func_info: {e}")
        return False


def get_dj_func_info():
    """Get current dj_func_info (lifecycle-aware)"""
    global _global_dj_func_info

    if _global_dj_func_info is None:
        logging.warning("dj_func_info not initialized, initializing now...")
        if not init_dj_func_info():
            logging.warning("Falling back to direct import of dj_func_info")
            from .create_dj_func_info import dj_func_info

            return dj_func_info

    return _global_dj_func_info


# ============================================================================
# Vector Index Cache Management
# ============================================================================


def _load_cached_index() -> bool:
    """Load cached vector index from disk"""
    global _cached_vector_store, _cached_tools_info, _cached_content_hash

    try:
        dj_func_info = get_dj_func_info()
        current_hash = _get_content_hash(dj_func_info)

        if not current_hash:
            return False

        os.makedirs(VECTOR_INDEX_CACHE_PATH, exist_ok=True)

        index_path = osp.join(VECTOR_INDEX_CACHE_PATH, "faiss_index")
        metadata_path = osp.join(VECTOR_INDEX_CACHE_PATH, "metadata.json")

        if not all(os.path.exists(p) for p in [index_path, metadata_path]):
            return False

        with open(metadata_path, "r") as f:
            metadata = json.load(f)

        cached_hash = metadata.get("content_hash", "")

        if current_hash != cached_hash:
            logging.info("Content hash mismatch, need to rebuild index")
            return False

        from langchain_community.embeddings import DashScopeEmbeddings

        embeddings = DashScopeEmbeddings(
            dashscope_api_key=os.environ.get("DASHSCOPE_API_KEY"),
            model=EMBEDDING_MODEL,
        )

        _cached_vector_store = FAISS.load_local(
            index_path,
            embeddings,
            allow_dangerous_deserialization=True,
        )

        _cached_tools_info = dj_func_info
        _cached_content_hash = cached_hash

        logging.info("Successfully loaded cached vector index")
        return True

    except Exception as e:
        logging.warning(f"Failed to load cached index: {e}")
        return False


def _save_cached_index():
    """Save vector index to disk cache"""
    global _cached_vector_store, _cached_content_hash

    try:
        os.makedirs(VECTOR_INDEX_CACHE_PATH, exist_ok=True)

        index_path = osp.join(VECTOR_INDEX_CACHE_PATH, "faiss_index")
        metadata_path = osp.join(VECTOR_INDEX_CACHE_PATH, "metadata.json")

        if _cached_vector_store:
            _cached_vector_store.save_local(index_path)

        metadata = {
            "content_hash": _cached_content_hash,
            "created_at": time.time(),
        }
        with open(metadata_path, "w") as f:
            json.dump(metadata, f)

        logging.info("Successfully saved vector index to cache")

    except Exception as e:
        logging.error(f"Failed to save cached index: {e}")


def _build_vector_index():
    """Build vector index using fresh dj_func_info"""
    global _cached_vector_store, _cached_tools_info, _cached_content_hash

    dj_func_info = get_dj_func_info()
    tool_descriptions = [f"{t['class_name']}: {t['class_desc']}" for t in dj_func_info]

    from langchain_community.embeddings import DashScopeEmbeddings

    embeddings = DashScopeEmbeddings(
        dashscope_api_key=os.environ.get("DASHSCOPE_API_KEY"),
        model=EMBEDDING_MODEL,
    )

    metadatas = [{"index": i} for i in range(len(tool_descriptions))]
    vector_store = FAISS.from_texts(
        tool_descriptions,
        embeddings,
        metadatas=metadatas,
    )

    _cached_vector_store = vector_store
    _cached_tools_info = dj_func_info
    _cached_content_hash = _get_content_hash(dj_func_info)

    _save_cached_index()
    logging.info("Successfully built and cached vector index")


# ============================================================================
# BM25 Index Management
# ============================================================================


def _build_bm25_index():
    global _cached_bm25, _cached_bm25_tools_info

    dj_func_info = get_dj_func_info()
    corpus = [_tokenize(f"{t['class_name']} {t['class_desc']}") for t in dj_func_info]

    _cached_bm25 = BM25Okapi(corpus)
    _cached_bm25_tools_info = dj_func_info
    logging.info(f"BM25 index built with {len(dj_func_info)} operators")


# ============================================================================
# Retrieval Functions
# ============================================================================


def retrieve_ops_vector(
    user_query: str,
    limit: int = VECTOR_SEARCH_DEFAULT_LIMIT,
) -> list:
    """
    Retrieve operators using vector similarity search.

    Returns:
        List of operator class names ordered by similarity descending.
    """
    global _cached_vector_store, _cached_tools_info

    if not _load_cached_index():
        logging.info("Building new vector index...")
        _build_vector_index()

    retrieved_tools = _cached_vector_store.similarity_search_with_relevance_scores(
        user_query, k=limit, score_threshold=VECTOR_SIMILARITY_THRESHOLD
    )
    retrieved_indices = [doc.metadata["index"] for doc, score in retrieved_tools]

    tool_names = []
    for raw_idx in retrieved_indices:
        tool_info = _cached_tools_info[raw_idx]
        tool_names.append(tool_info["class_name"])

    return tool_names


def retrieve_ops_bm25(
    user_query: str,
    limit: int = BM25_DEFAULT_LIMIT,
    score_threshold: float = BM25_SCORE_THRESHOLD,
) -> list:
    """
    Retrieve operators using BM25 keyword matching.

    Returns:
        List of operator class names ordered by BM25 score descending.
    """
    global _cached_bm25, _cached_bm25_tools_info

    if _cached_bm25 is None:
        _build_bm25_index()

    query_tokens = _tokenize(user_query)
    scores = _cached_bm25.get_scores(query_tokens)

    ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)

    tool_names = []
    for idx in ranked_indices[:limit]:
        if scores[idx] <= score_threshold:
            break
        tool_names.append(_cached_bm25_tools_info[idx]["class_name"])

    return tool_names


def retrieve_ops_regex(
    user_query: str,
    limit: int = REGEX_DEFAULT_LIMIT,
) -> list:
    """
    Retrieve operators using a Python regex pattern matched against
    operator names and descriptions.

    Returns:
        List of matched operator class names, in definition order.

    Raises:
        ValueError: If the pattern exceeds REGEX_MAX_PATTERN_LENGTH characters.
    """
    if len(user_query) > REGEX_MAX_PATTERN_LENGTH:
        raise ValueError(
            f"Regex query too long. Maximum length is "
            f"{REGEX_MAX_PATTERN_LENGTH} characters."
        )

    dj_func_info = get_dj_func_info()

    try:
        pattern = re.compile(user_query)
    except re.error as e:
        logging.error(f"Invalid regex pattern '{user_query}': {e}")
        return []

    matched_tools = []
    for tool_info in dj_func_info:
        tool_name = tool_info["class_name"]
        tool_desc = tool_info["class_desc"]
        if pattern.search(f"{tool_name} {tool_desc}"):
            matched_tools.append(tool_name)

    return matched_tools[:limit]


def retrieve_ops_hybrid(
    user_query: str,
    limit: int = HYBRID_DEFAULT_LIMIT,
    vector_weight: float = HYBRID_VECTOR_WEIGHT,
    bm25_weight: float = HYBRID_BM25_WEIGHT,
    top_k_multiplier: int = HYBRID_TOP_K_MULTIPLIER,
    rrf_k: int = 60,
    score_threshold: float = HYBRID_SCORE_THRESHOLD,
) -> list:
    """
    Retrieve operators using hybrid BM25 + vector search with reciprocal
    rank fusion (RRF).

    Returns:
        List of operator class names ordered by fused score descending.
    """
    fetch_limit = limit * top_k_multiplier

    bm25_results = retrieve_ops_bm25(
        user_query,
        limit=fetch_limit,
        score_threshold=HYBRID_BM25_SCORE_THRESHOLD,
    )
    vector_results = retrieve_ops_vector(user_query, limit=fetch_limit)

    # Reciprocal Rank Fusion with smoothing constant k
    scores: dict[str, float] = {}

    for rank, name in enumerate(bm25_results, start=1):
        scores[name] = scores.get(name, 0.0) + bm25_weight / (rrf_k + rank)

    for rank, name in enumerate(vector_results, start=1):
        scores[name] = scores.get(name, 0.0) + vector_weight / (rrf_k + rank)

    ranked = sorted(
        ((name, score) for name, score in scores.items() if score > score_threshold),
        key=lambda x: x[1],
        reverse=True,
    )
    return [name for name, _ in ranked[:limit]]


# ============================================================================
# Main Entry Point
# ============================================================================


async def retrieve_ops(
    user_query: str,
    limit: int = HYBRID_DEFAULT_LIMIT,
    mode: str = "vector",
) -> list:
    """
    Tool retrieval with configurable mode.

    Args:
        user_query: Query string, interpretation depends on mode:
                    - "regex": A Python regex pattern to match against operator
                               names and descriptions (e.g., "image.*filter",
                               "(?i)dedup")
                    - "bm25": Natural language query, tokenized and matched via
                              BM25 keyword scoring
                    - "vector": Natural language query, encoded and matched via
                                semantic vector similarity
                    - "hybrid": Natural language query, fused results from both
                                BM25 and vector search
        limit: Maximum number of tools to retrieve
        mode: Retrieval mode - "regex", "bm25", "vector", "hybrid"
              (default: "vector")

    Returns:
        List of operator class names, ordered by relevance
    """

    if mode == "regex":
        return retrieve_ops_regex(user_query, limit=limit)

    elif mode == "bm25":
        return retrieve_ops_bm25(user_query, limit=limit)

    elif mode in ("vector", "hybrid"):
        try:
            if mode == "vector":
                return retrieve_ops_vector(user_query, limit=limit)
            else:
                return retrieve_ops_hybrid(user_query, limit=limit)
        except Exception as e:
            logging.warning(
                f"{mode.capitalize()} retrieval failed: {e}. "
                f"Falling back to bm25 search.",
            )
            return retrieve_ops_bm25(user_query, limit=limit)

    else:
        raise ValueError(
            f"Invalid mode: {mode}. "
            f"Must be 'regex', 'bm25', 'vector', or 'hybrid'.",
        )


# ============================================================================
# CLI Testing
# ============================================================================

if __name__ == "__main__":
    import asyncio

    user_query = (
        "Clean special characters from text and filter samples with "
        "excessive length. Mask sensitive information and filter unsafe "
        "content including adult/terror-related terms."
        "Additionally, filter out small images, perform image tagging, "
        "and remove duplicate images."
    )

    print("=== Testing BM25 mode ===")
    tool_names_bm25 = asyncio.run(
        retrieve_ops(user_query, limit=10, mode="bm25"),
    )
    print("Retrieved tool names (BM25):")
    print(tool_names_bm25)

    print("\n=== Testing Vector mode ===")
    tool_names_vector = asyncio.run(
        retrieve_ops(user_query, limit=10, mode="vector"),
    )
    print("Retrieved tool names (Vector):")
    print(tool_names_vector)

    print("\n=== Testing Hybrid mode (default) ===")
    tool_names_hybrid = asyncio.run(
        retrieve_ops(user_query, limit=10, mode="hybrid"),
    )
    print("Retrieved tool names (Hybrid):")
    print(tool_names_hybrid)
