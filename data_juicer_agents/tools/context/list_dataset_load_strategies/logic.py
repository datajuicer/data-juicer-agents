# -*- coding: utf-8 -*-
"""Pure logic for list_dataset_load_strategies."""

from __future__ import annotations

import dataclasses
from typing import Any, Dict

from data_juicer_agents.tools.plan._shared.schema import DatasetObjectConfig, DatasetSourceConfig


def _extract_field_schema(cls: type) -> dict:
    """Dynamically extract field descriptions from a dataclass using field metadata."""
    result = {}
    for f in dataclasses.fields(cls):
        if f.name.startswith("_"):
            continue
        desc = f.metadata.get("description", f"Field '{f.name}'")
        result[f.name] = desc
    return result


def list_dataset_load_strategies(
    *,
    executor_type: str = "default",
) -> Dict[str, Any]:
    """List truly implemented dataset load strategies from Data-Juicer.

    Uses dynamic source-code inspection to filter out placeholder strategies
    that raise NotImplementedError, ensuring the returned list reflects what
    actually works at runtime.

    Args:
        executor_type: Filter by executor type ('default', 'ray', or '*' for all).

    Returns:
        Dict with 'strategies' list and metadata.
    """
    try:
        from data_juicer_agents.utils.dj_config_bridge import get_dj_config_bridge

        bridge = get_dj_config_bridge()
        strategies = bridge.get_implemented_load_strategies(executor_type=executor_type)

        # Build a user-friendly summary, surfacing required/optional fields
        formatted = []
        for s in strategies:
            entry: Dict[str, Any] = {
                "type": s["type"],
                "source": s["source"],
            }
            rules = s.get("config_validation_rules", {})
            if rules:
                if rules.get("required_fields"):
                    entry["required_fields"] = rules["required_fields"]
                if rules.get("optional_fields"):
                    entry["optional_fields"] = rules["optional_fields"]
            formatted.append(entry)

        return {
            "ok": True,
            "message": (
                f"Found {len(formatted)} implemented dataset load strategies "
                f"for executor_type='{executor_type}'"
            ),
            "executor_type_filter": executor_type,
            "source_config_common_fields": {
                **_extract_field_schema(DatasetSourceConfig),
                "_extra_kwargs": "Any additional strategy-specific fields listed under 'required_fields'/'optional_fields' of the chosen strategy.",
            },
            "dataset_object_fields": _extract_field_schema(DatasetObjectConfig),
            "strategies": formatted,
            "total_count": len(formatted),
            "usage_hint": (
                "Build the 'dataset' argument for build_dataset_spec using the schema above. "
                "Example: dataset={\"configs\": [{\"type\": \"local\", \"path\": \"/data/my.jsonl\", \"weight\": 1.0}], \"max_sample_num\": 10000}"
            ),
        }

    except Exception as e:
        return {
            "ok": False,
            "message": f"Failed to list dataset load strategies: {str(e)}",
            "strategies": [],
            "total_count": 0,
            "executor_type_filter": executor_type,
        }


__all__ = ["list_dataset_load_strategies"]
