# -*- coding: utf-8 -*-
"""Discovery-based catalog of built-in tool specifications."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
import pkgutil
from typing import Iterable, List, Sequence, Tuple

from data_juicer_agents.core.tool.contracts import ToolSpec


_TOOLS_PACKAGE = "data_juicer_agents.tools"
_TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
_SKIP_PACKAGES = {"__pycache__"}


def iter_tool_group_names() -> List[str]:
    groups: List[str] = []
    for module_info in pkgutil.iter_modules([str(_TOOLS_DIR)]):
        if not module_info.ispkg:
            continue
        name = str(module_info.name).strip()
        if not name or name in _SKIP_PACKAGES:
            continue
        registry_py = _TOOLS_DIR / name / "registry.py"
        definition_py = _TOOLS_DIR / name / "definition.py"
        if registry_py.exists() or definition_py.exists():
            groups.append(name)
    return sorted(groups)


def load_tool_specs_for_group(group_name: str) -> List[ToolSpec]:
    registry_py = _TOOLS_DIR / group_name / "registry.py"
    definition_py = _TOOLS_DIR / group_name / "definition.py"
    if registry_py.exists():
        module_name = f"{_TOOLS_PACKAGE}.{group_name}.registry"
    elif definition_py.exists():
        module_name = f"{_TOOLS_PACKAGE}.{group_name}.definition"
    else:
        raise FileNotFoundError(f"no registry.py or definition.py for tool group: {group_name}")

    module = import_module(module_name)
    specs = getattr(module, "TOOL_SPECS", None)
    if specs is None:
        raise AttributeError(f"{module.__name__} does not define TOOL_SPECS")
    if not isinstance(specs, (list, tuple)):
        raise TypeError(f"{module.__name__}.TOOL_SPECS must be a list or tuple")
    return [spec for spec in specs if isinstance(spec, ToolSpec)]


def load_all_tool_specs() -> List[ToolSpec]:
    all_specs: List[ToolSpec] = []
    for group_name in iter_tool_group_names():
        all_specs.extend(load_tool_specs_for_group(group_name))
    return all_specs


ALL_TOOL_GROUPS: Tuple[str, ...] = tuple(iter_tool_group_names())
ALL_TOOL_SPECS: List[ToolSpec] = load_all_tool_specs()


__all__ = [
    "ALL_TOOL_GROUPS",
    "ALL_TOOL_SPECS",
    "iter_tool_group_names",
    "load_all_tool_specs",
    "load_tool_specs_for_group",
]
