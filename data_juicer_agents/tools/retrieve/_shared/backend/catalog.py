# -*- coding: utf-8 -*-
"""Operator catalog builders from OPSearcher records."""

from __future__ import annotations

import inspect
from typing import Any

from data_juicer.tools.op_search import OPSearcher


def create_op_searcher() -> OPSearcher:
    """Create an OPSearcher instance for retrieval tools."""
    return OPSearcher(include_formatter=False)


def build_op_catalog(searcher: OPSearcher) -> list[dict[str, Any]]:
    """Build lightweight catalog rows from the given searcher."""
    all_ops = searcher.search()
    op_catalog: list[dict[str, Any]] = []
    for i, op in enumerate(all_ops):
        class_entry = {
            "index": i,
            "class_name": op["name"],
            "class_desc": op["desc"],
            "class_type": op.get("type", ""),
            "class_tags": list(op.get("tags", [])),
        }
        param_desc = op["param_desc"]
        param_desc_map = {}
        args = ""
        for item in param_desc.split(":param"):
            parts = item.split(":")
            if len(parts) < 2:
                continue
            param_desc_map[parts[0].strip()] = ":".join(parts[1:]).strip()

        if op["sig"]:
            for param_name, param in op["sig"].parameters.items():
                if param_name in ["self", "args", "kwargs"]:
                    continue
                if param.kind in (
                    inspect.Parameter.VAR_POSITIONAL,
                    inspect.Parameter.VAR_KEYWORD,
                ):
                    continue
                if param_name in param_desc_map:
                    args += (
                        f"        {param_name} ({param.annotation}): "
                        f"{param_desc_map[param_name]}\n"
                    )
                else:
                    args += f"        {param_name} ({param.annotation})\n"
        class_entry["arguments"] = args
        op_catalog.append(class_entry)

    return op_catalog
