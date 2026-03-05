# -*- coding: utf-8 -*-
"""Utilities for computing structured plan diffs."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any, Dict, List, Tuple

from data_juicer_agents.capabilities.plan.schema import PlanModel


def _op_signature(op: Dict[str, Any]) -> Tuple[str, str]:
    name = str(op.get("name", "")).strip()
    params = op.get("params", {})
    try:
        params_json = json.dumps(params, ensure_ascii=False, sort_keys=True)
    except TypeError:
        params_json = "{}"
    return name, params_json


def build_plan_diff(base: PlanModel, revised: PlanModel) -> Dict[str, Any]:
    """Build a structured diff between two plans."""

    field_changes: Dict[str, Dict[str, Any]] = {}
    for key in ("workflow", "modality", "dataset_path", "export_path", "text_keys", "image_key"):
        old = getattr(base, key)
        new = getattr(revised, key)
        if old != new:
            field_changes[key] = {"old": old, "new": new}

    base_ops = [item for item in base.to_dict().get("operators", []) if isinstance(item, dict)]
    revised_ops = [
        item for item in revised.to_dict().get("operators", []) if isinstance(item, dict)
    ]
    base_counter = Counter(_op_signature(op) for op in base_ops)
    revised_counter = Counter(_op_signature(op) for op in revised_ops)

    added = list((revised_counter - base_counter).elements())
    removed = list((base_counter - revised_counter).elements())
    order_changed = (
        [sig[0] for sig in map(_op_signature, base_ops)]
        != [sig[0] for sig in map(_op_signature, revised_ops)]
    )

    metadata_changes: Dict[str, Dict[str, Any]] = {}
    for key in ("risk_notes", "estimation"):
        old = getattr(base, key)
        new = getattr(revised, key)
        if old != new:
            metadata_changes[key] = {"old": old, "new": new}

    return {
        "field_changes": field_changes,
        "operators": {
            "added": [{"name": name, "params": json.loads(params)} for name, params in added],
            "removed": [{"name": name, "params": json.loads(params)} for name, params in removed],
            "order_changed": order_changed and not added and not removed,
        },
        "metadata_changes": metadata_changes,
    }


def summarize_plan_diff(diff: Dict[str, Any]) -> List[str]:
    """Generate human-readable one-line summaries from plan diff."""

    lines: List[str] = []
    field_changes = diff.get("field_changes", {})
    for key in ("workflow", "modality", "dataset_path", "export_path", "text_keys", "image_key"):
        if key not in field_changes:
            continue
        item = field_changes[key]
        lines.append(f"{key}: {item.get('old')} -> {item.get('new')}")

    ops = diff.get("operators", {})
    added = ops.get("added", []) if isinstance(ops, dict) else []
    removed = ops.get("removed", []) if isinstance(ops, dict) else []
    if added:
        names = ", ".join(op.get("name", "") for op in added if isinstance(op, dict))
        lines.append(f"operators added: {names}")
    if removed:
        names = ", ".join(op.get("name", "") for op in removed if isinstance(op, dict))
        lines.append(f"operators removed: {names}")
    if ops.get("order_changed"):
        lines.append("operators order changed")

    metadata_changes = diff.get("metadata_changes", {})
    for key in ("risk_notes", "estimation"):
        if key in metadata_changes:
            lines.append(f"{key} updated")

    if not lines:
        lines.append("No effective changes from base plan.")
    return lines
