# -*- coding: utf-8 -*-
"""Implementation for `djx retrieve`."""

from __future__ import annotations

import json
from typing import List

from data_juicer_agents.tools.retrieve import retrieve_operator_candidates


# ---------------------------------------------------------------------------
# Modality → operator tags mapping
# ---------------------------------------------------------------------------

_MODALITY_TAG_MAP: dict[str, List[str]] = {
    "text": ["text"],
    "image": ["image"],
    "multimodal": ["multimodal"],
    "audio": ["audio"],
    "video": ["video"],
}


def _infer_tags_from_dataset(dataset_path: str) -> List[str]:
    """Probe *dataset_path* with ``inspect_dataset_schema`` and return modality tags.

    Returns an empty list when the dataset cannot be inspected or the modality
    is unknown, so the caller can fall back to unfiltered retrieval.
    """
    from data_juicer_agents.tools.context.inspect_dataset.logic import (
        inspect_dataset_schema,
    )

    result = inspect_dataset_schema(dataset_path=dataset_path, sample_size=20)
    if not result.get("ok"):
        return []
    modality = str(result.get("modality", "")).strip().lower()
    return list(_MODALITY_TAG_MAP.get(modality, []))


def _print_human_readable(payload: dict) -> None:
    print("Retrieve Summary:")
    print(f"Intent: {payload.get('intent', '')}")
    print(f"Mode: {payload.get('mode', '')}")
    print(f"Source: {payload.get('retrieval_source', '')}")
    print(f"Candidates: {payload.get('candidate_count', 0)}")

    inferred_tags = payload.get("inferred_tags")
    if inferred_tags:
        print(f"Dataset modality tags: {inferred_tags}")

    candidates = payload.get("candidates", [])
    if not candidates:
        print("No candidate operators found.")
    else:
        print("Top operator candidates:")
        for item in candidates:
            rank = item.get("rank")
            name = item.get("operator_name")
            op_type = item.get("operator_type", "unknown")
            score = item.get("relevance_score", 0)
            desc = str(item.get("description", "")).strip()
            print(f"{rank}. {name} ({op_type}) score={score}")
            if desc:
                print(f"   {desc}")

    for note in payload.get("notes", []):
        print(f"Note: {note}")


def run_retrieve(args) -> int:
    top_k = int(args.top_k)
    if top_k <= 0:
        print("top-k must be > 0")
        return 2

    # --- Collect tags from --tags and --dataset ------------------------------
    tags: List[str] = list(getattr(args, "tags", None) or [])
    dataset_path = getattr(args, "dataset", None)
    if dataset_path:
        inferred = _infer_tags_from_dataset(dataset_path)
        if inferred:
            print(f"Detected dataset modality tags: {inferred}")
            for tag in inferred:
                if tag not in tags:
                    tags.append(tag)
        else:
            print(f"Could not infer modality from dataset: {dataset_path}")

    op_type: str | None = getattr(args, "op_type", None)

    try:
        payload = retrieve_operator_candidates(
            intent=args.intent,
            top_k=top_k,
            mode=args.mode,
            op_type=op_type,
            tags=tags if tags else None,
        )
    except Exception as exc:
        print(f"Retrieve failed: {exc}")
        return 2

    # Attach filter info to payload for JSON output
    if tags:
        payload["inferred_tags"] = tags
    if op_type:
        payload["op_type_filter"] = op_type

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_human_readable(payload)
    return 0