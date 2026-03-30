# -*- coding: utf-8 -*-
"""Pure logic for list_dataset_formatters."""

from __future__ import annotations

import inspect
from typing import Any, Dict, List


def list_dataset_formatters(
    *,
    include_ray: bool = True,
) -> Dict[str, Any]:
    """List available dataset formatters from Data-Juicer.

    Discovers which dataset formatters (dynamic data generators) are registered
    in the current Data-Juicer installation by comparing OPSearcher results
    with and without formatter inclusion.

    Args:
        include_ray: Whether to include Ray-specific formatters.

    Returns:
        Dict with 'formatters' list and metadata.
    """
    try:
        from data_juicer.tools.op_search import OPSearcher

        searcher = OPSearcher(include_formatter=True)
        formatter_entries = searcher.search(op_type="formatter")

        # Optionally filter out Ray-specific formatters
        if not include_ray:
            formatter_entries = [
                entry for entry in formatter_entries
                if not entry["name"].startswith("Ray")
            ]

        formatters: List[Dict[str, Any]] = []
        for entry in formatter_entries:
            formatter_info: Dict[str, Any] = {
                "name": entry["name"],
                "description": entry.get("desc", "").strip(),
            }

            # Extract parameter info from signature
            signature = entry.get("sig")
            if signature:
                params: List[Dict[str, Any]] = []
                for param_name, param in signature.parameters.items():
                    if param_name in ("self", "args", "kwargs"):
                        continue
                    if param.kind in (
                        inspect.Parameter.VAR_POSITIONAL,
                        inspect.Parameter.VAR_KEYWORD,
                    ):
                        continue

                    param_info: Dict[str, Any] = {"name": param_name}

                    if param.annotation is not inspect.Parameter.empty:
                        param_info["type"] = str(param.annotation)

                    if param.default is not inspect.Parameter.empty:
                        param_info["default"] = param.default
                    else:
                        param_info["required"] = True

                    params.append(param_info)

                if params:
                    formatter_info["parameters"] = params

            formatters.append(formatter_info)

        return {
            "ok": True,
            "message": f"Found {len(formatters)} dataset formatters",
            "formatters": formatters,
            "total_count": len(formatters),
            "include_ray": include_ray,
            "usage_hint": (
                "Use the formatter 'name' as the 'type' value in "
                "generated_dataset_config when calling build_dataset_spec. "
                "Example: generated_dataset_config={\"type\": \"EmptyFormatter\", "
                "\"length\": 1000, \"feature_keys\": [\"text\"]}"
            ),
        }

    except Exception as exc:
        return {
            "ok": False,
            "message": f"Failed to list dataset formatters: {exc}",
            "formatters": [],
            "total_count": 0,
            "include_ray": include_ray,
        }


__all__ = ["list_dataset_formatters"]
