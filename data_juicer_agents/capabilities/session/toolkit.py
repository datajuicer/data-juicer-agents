# -*- coding: utf-8 -*-
"""Session runtime binding for tool specifications."""

from __future__ import annotations

import os
from typing import List, Tuple

from data_juicer_agents.core.tool import ToolContext, ToolSpec, list_tool_specs
from data_juicer_agents.adapters.agentscope.tools import (
    build_agentscope_json_schema,
    build_agentscope_tool_function,
)
from data_juicer_agents.capabilities.session.runtime import SessionToolRuntime


_SESSION_GROUP_PRIORITY = {
    "context": 10,
    "dataset": 20,
    "retrieve": 30,
    "plan": 40,
    "apply": 50,
    "dev": 60,
    "file": 70,
    "process": 80,
}


def _build_tool_context(runtime: SessionToolRuntime) -> ToolContext:
    return ToolContext(
        working_dir=str(runtime.state.working_dir or "./.djx"),
        env=dict(os.environ),
        artifacts_dir=str(runtime.storage_root()),
    )


def _session_sort_key(spec: ToolSpec) -> Tuple[int, str]:
    priority = min((_SESSION_GROUP_PRIORITY.get(tag, 999) for tag in spec.tags), default=999)
    return priority, spec.name


def get_session_tool_specs() -> List[ToolSpec]:
    return sorted(list_tool_specs(), key=_session_sort_key)


def build_session_toolkit(runtime: SessionToolRuntime):
    from agentscope.tool import Toolkit

    toolkit = Toolkit()
    for spec in get_session_tool_specs():
        func = build_agentscope_tool_function(
            spec,
            ctx_factory=lambda runtime=runtime: _build_tool_context(runtime),
            runtime_invoke=runtime.invoke_tool,
        )
        toolkit.register_tool_function(
            func,
            json_schema=build_agentscope_json_schema(spec),
        )
    return toolkit


__all__ = ["build_session_toolkit", "get_session_tool_specs"]
