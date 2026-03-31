# -*- coding: utf-8 -*-
"""Registry for runtime-agnostic tool definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Dict, List, Sequence, Tuple

from .contracts import ToolSpec
from .profiles import groups_for_tool_profile


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


def _registry_cache_key(
    *,
    profile: str | None = None,
    groups: Sequence[str] | None = None,
) -> Tuple[str, ...] | None:
    if groups is not None:
        normalized = tuple(str(item or "").strip() for item in groups if str(item or "").strip())
        return normalized
    return groups_for_tool_profile(profile)


@lru_cache(maxsize=None)
def _build_registry_cached(group_names: Tuple[str, ...] | None) -> ToolRegistry:
    from data_juicer_agents.core.tool.catalog import load_tool_specs

    specs = load_tool_specs(group_names)
    registry = ToolRegistry()
    for spec in specs:
        registry.register(spec)
    return registry


def build_default_tool_registry(
    *,
    profile: str | None = None,
    groups: Sequence[str] | None = None,
) -> ToolRegistry:
    return _build_registry_cached(_registry_cache_key(profile=profile, groups=groups))


def get_tool_spec(name: str, *, profile: str | None = None) -> ToolSpec:
    return build_default_tool_registry(profile=profile).get(name)


def list_tool_specs(
    *,
    tags: Sequence[str] | None = None,
    profile: str | None = None,
) -> List[ToolSpec]:
    return build_default_tool_registry(profile=profile).list(tags=tags)


__all__ = [
    "ToolRegistry",
    "build_default_tool_registry",
    "get_tool_spec",
    "list_tool_specs",
]
