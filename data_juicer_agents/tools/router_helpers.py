# -*- coding: utf-8 -*-
"""Workflow-first routing helpers for v0.1."""

from __future__ import annotations

from typing import Dict, List, Optional


RAG_STRONG_HINTS: List[str] = [
    "rag",
    "retrieval",
    "embedding",
    "chunk",
    "语料",
    "检索",
]

MULTIMODAL_STRONG_HINTS: List[str] = [
    "multimodal",
    "多模态",
    "image",
    "img",
    "图像",
    "图片",
    "图文",
    "视觉",
    "vlm",
    "vision",
    "near-duplicate",
]

RAG_WEAK_HINTS: List[str] = [
    "clean",
    "normalize",
    "文本",
    "清洗",
    "知识库",
]

MULTIMODAL_WEAK_HINTS: List[str] = [
    "dedup",
    "duplicate",
    "去重",
]


def retrieve_workflow(user_intent: str) -> Optional[str]:
    """Try matching a workflow template from intent.

    Returns:
    - workflow name when intent has enough routing signals
    - None when no reliable template signal is found
    """

    text = user_intent.lower()
    rag_strong = sum(1 for hint in RAG_STRONG_HINTS if hint in text)
    mm_strong = sum(1 for hint in MULTIMODAL_STRONG_HINTS if hint in text)
    rag_weak = sum(1 for hint in RAG_WEAK_HINTS if hint in text)
    mm_weak = sum(1 for hint in MULTIMODAL_WEAK_HINTS if hint in text)

    if rag_strong == 0 and mm_strong == 0 and rag_weak == 0 and mm_weak == 0:
        return None

    # Strong signals first.
    if mm_strong > rag_strong:
        return "multimodal_dedup"
    if rag_strong > mm_strong:
        return "rag_cleaning"

    # Tie on strong signals; compare weak hints.
    rag_score = rag_weak + rag_strong * 2
    mm_score = mm_weak + mm_strong * 2

    if mm_score > rag_score and mm_strong > 0:
        return "multimodal_dedup"
    if rag_score > mm_score:
        return "rag_cleaning"

    # Ambiguous default for retrieval mode: no confident match.
    return None


def select_workflow(user_intent: str) -> str:
    """Select workflow template with weighted intent signals.

    Routing principle:
    - Strong multimodal signals should dominate because image workflows are
      materially different from text-only RAG cleaning.
    - Pure dedup wording is ambiguous; without multimodal cues, default to RAG.
    """

    matched = retrieve_workflow(user_intent)
    if matched:
        return matched
    return "rag_cleaning"


def explain_routing(user_intent: str) -> Dict[str, str]:
    workflow = select_workflow(user_intent)
    return {
        "strategy": "workflow-first",
        "selected_workflow": workflow,
        "reason": "weighted strong/weak intent hints",
    }
