# -*- coding: utf-8 -*-
"""Registry for runtime-agnostic tool definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Dict, Iterable, List, Sequence

from .contracts import ToolSpec


@dataclass
class ToolRegistry:
    """Container of tool definitions."""

    _tools: Dict[str, ToolSpec] = field(default_factory=dict)

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"tool already registered: {spec.name}")
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec:
        spec = self._tools.get(str(name).strip())
        if spec is None:
            raise KeyError(f"tool not found: {name}")
        return spec

    def list(self, *, tags: Sequence[str] | None = None) -> List[ToolSpec]:
        specs = list(self._tools.values())
        if not tags:
            return specs
        expected = {str(tag).strip() for tag in tags if str(tag).strip()}
        if not expected:
            return specs
        return [spec for spec in specs if expected.intersection(spec.tags)]

    def list_tools(self, *, tags: Sequence[str] | None = None) -> List[ToolSpec]:
        return self.list(tags=tags)

    def names(self) -> List[str]:
        return list(self._tools.keys())


@lru_cache(maxsize=1)
def build_default_tool_registry() -> ToolRegistry:
    from data_juicer_agents.core.tool.catalog import ALL_TOOL_SPECS

    registry = ToolRegistry()
    for spec in ALL_TOOL_SPECS:
        registry.register(spec)
    return registry


def get_tool_spec(name: str) -> ToolSpec:
    return build_default_tool_registry().get(name)


def list_tool_specs(*, tags: Sequence[str] | None = None) -> List[ToolSpec]:
    return build_default_tool_registry().list(tags=tags)


__all__ = [
    "ToolRegistry",
    "build_default_tool_registry",
    "get_tool_spec",
    "list_tool_specs",
]
