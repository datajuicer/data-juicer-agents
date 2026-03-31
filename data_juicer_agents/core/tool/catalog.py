# -*- coding: utf-8 -*-
"""Discovery-based catalog of built-in tool specifications."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
import pkgutil
from functools import lru_cache
from typing import List, Sequence, Tuple

from data_juicer_agents.core.tool.contracts import ToolSpec


_TOOLS_PACKAGE = "data_juicer_agents.tools"
_TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
_SKIP_PACKAGES = {"__pycache__"}


class ToolGroupImportError(ImportError):
    """Raised when a tool group cannot be imported because optional deps are missing."""

    def __init__(self, group_name: str, cause: ModuleNotFoundError) -> None:
        self.group_name = str(group_name)
        self.missing_module = str(getattr(cause, "name", "") or "").strip() or None
        message = (
            f"failed to import tool group '{self.group_name}'"
            + (f" (missing module: {self.missing_module})" if self.missing_module else "")
        )
        super().__init__(message)


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

    try:
        module = import_module(module_name)
    except ModuleNotFoundError as exc:
        raise ToolGroupImportError(group_name, exc) from exc
    specs = getattr(module, "TOOL_SPECS", None)
    if specs is None:
        raise AttributeError(f"{module.__name__} does not define TOOL_SPECS")
    if not isinstance(specs, (list, tuple)):
        raise TypeError(f"{module.__name__}.TOOL_SPECS must be a list or tuple")
    return [spec for spec in specs if isinstance(spec, ToolSpec)]


def _normalize_group_names(groups: Sequence[str] | None) -> Tuple[str, ...]:
    if groups is None:
        return ALL_TOOL_GROUPS

    expected = set(ALL_TOOL_GROUPS)
    normalized = []
    for group_name in groups:
        value = str(group_name or "").strip()
        if not value:
            continue
        if value not in expected:
            raise KeyError(f"unknown tool group: {value}")
        if value not in normalized:
            normalized.append(value)
    return tuple(normalized)


@lru_cache(maxsize=None)
def _load_tool_specs_cached(group_names: Tuple[str, ...]) -> Tuple[ToolSpec, ...]:
    all_specs: List[ToolSpec] = []
    for group_name in group_names:
        all_specs.extend(load_tool_specs_for_group(group_name))
    return tuple(all_specs)


def load_tool_specs(groups: Sequence[str] | None = None) -> List[ToolSpec]:
    group_names = _normalize_group_names(groups)
    return list(_load_tool_specs_cached(group_names))


def load_all_tool_specs() -> List[ToolSpec]:
    return load_tool_specs()


ALL_TOOL_GROUPS: Tuple[str, ...] = tuple(iter_tool_group_names())


__all__ = [
    "ALL_TOOL_GROUPS",
    "ToolGroupImportError",
    "iter_tool_group_names",
    "load_all_tool_specs",
    "load_tool_specs",
    "load_tool_specs_for_group",
]
