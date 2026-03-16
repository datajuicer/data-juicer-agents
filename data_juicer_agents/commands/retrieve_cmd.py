# -*- coding: utf-8 -*-
"""Implementation for `djx retrieve`."""

from __future__ import annotations

import json

from data_juicer_agents.tools.retrieve import retrieve_operator_candidates


def _print_human_readable(payload: dict) -> None:
    print("Retrieve Summary:")
    print(f"Intent: {payload.get('intent', '')}")
    print(f"Mode: {payload.get('mode', '')}")
    print(f"Source: {payload.get('retrieval_source', '')}")
    print(f"Candidates: {payload.get('candidate_count', 0)}")

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

    try:
        payload = retrieve_operator_candidates(
            intent=args.intent,
            top_k=top_k,
            mode=args.mode,
            dataset_path=args.dataset,
        )
    except Exception as exc:
        print(f"Retrieve failed: {exc}")
        return 2

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_human_readable(payload)
    return 0
