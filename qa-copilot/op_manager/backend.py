# -*- coding: utf-8 -*-
"""Local QA-copilot retrieval backend, decoupled from data_juicer_agents."""

import hashlib
import json
import logging
import os
import os.path as osp
import time
from typing import Optional

from langchain_community.vectorstores import FAISS

VECTOR_INDEX_CACHE_PATH = osp.join(osp.dirname(__file__), "vector_index_cache")

_cached_vector_store: Optional[FAISS] = None
_cached_tools_info: Optional[list] = None
_cached_content_hash: Optional[str] = None
_global_dj_func_info: Optional[list] = None


def _get_content_hash(dj_func_info: list) -> str:
    try:
        content_str = json.dumps(dj_func_info, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(content_str.encode("utf-8")).hexdigest()
    except Exception as exc:  # pragma: no cover - defensive
        logging.warning("Failed to compute content hash: %s", exc)
        return ""


def _load_cached_index() -> bool:
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

        with open(metadata_path, "r", encoding="utf-8") as fh:
            metadata = json.load(fh)

        cached_hash = metadata.get("content_hash", "")
        if current_hash != cached_hash:
            logging.info("QA-copilot content hash mismatch, rebuilding vector index")
            return False

        from langchain_community.embeddings import DashScopeEmbeddings

        embeddings = DashScopeEmbeddings(
            dashscope_api_key=os.environ.get("DASHSCOPE_API_KEY"),
            model="text-embedding-v3",
        )
        _cached_vector_store = FAISS.load_local(
            index_path,
            embeddings,
            allow_dangerous_deserialization=True,
        )
        _cached_tools_info = dj_func_info
        _cached_content_hash = cached_hash
        return True
    except Exception as exc:  # pragma: no cover - defensive
        logging.warning("Failed to load QA-copilot cached index: %s", exc)
        return False


def _save_cached_index() -> None:
    global _cached_vector_store, _cached_content_hash

    try:
        os.makedirs(VECTOR_INDEX_CACHE_PATH, exist_ok=True)
        index_path = osp.join(VECTOR_INDEX_CACHE_PATH, "faiss_index")
        metadata_path = osp.join(VECTOR_INDEX_CACHE_PATH, "metadata.json")
        if _cached_vector_store:
            _cached_vector_store.save_local(index_path)
        with open(metadata_path, "w", encoding="utf-8") as fh:
            json.dump({"content_hash": _cached_content_hash, "created_at": time.time()}, fh)
    except Exception as exc:  # pragma: no cover - defensive
        logging.warning("Failed to save QA-copilot cached index: %s", exc)


def init_dj_func_info() -> bool:
    global _global_dj_func_info

    try:
        from .catalog import dj_func_info

        _global_dj_func_info = dj_func_info
        return True
    except Exception as exc:  # pragma: no cover - defensive
        logging.error("Failed to initialize QA-copilot dj_func_info: %s", exc)
        return False


def get_dj_func_info():
    global _global_dj_func_info

    if _global_dj_func_info is None and not init_dj_func_info():
        from .catalog import dj_func_info

        return dj_func_info
    return _global_dj_func_info


def _build_vector_index() -> None:
    global _cached_vector_store, _cached_tools_info, _cached_content_hash

    dj_func_info = get_dj_func_info()
    tool_descriptions = [f"{t['class_name']}: {t['class_desc']}" for t in dj_func_info]

    from langchain_community.embeddings import DashScopeEmbeddings

    embeddings = DashScopeEmbeddings(
        dashscope_api_key=os.environ.get("DASHSCOPE_API_KEY"),
        model="text-embedding-v3",
    )
    metadatas = [{"index": i} for i in range(len(tool_descriptions))]
    vector_store = FAISS.from_texts(tool_descriptions, embeddings, metadatas=metadatas)

    _cached_vector_store = vector_store
    _cached_tools_info = dj_func_info
    _cached_content_hash = _get_content_hash(dj_func_info)
    _save_cached_index()


def retrieve_ops_vector(user_query, limit=20):
    global _cached_vector_store, _cached_tools_info

    if not _load_cached_index():
        _build_vector_index()

    retrieved_tools = _cached_vector_store.similarity_search(user_query, k=limit)
    retrieved_indices = [doc.metadata["index"] for doc in retrieved_tools]
    tool_names = []
    for raw_idx in retrieved_indices:
        tool_info = _cached_tools_info[raw_idx]
        tool_names.append(tool_info["class_name"])
    return tool_names
