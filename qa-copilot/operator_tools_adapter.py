# -*- coding: utf-8 -*-
"""AgentScope adapter for qa-copilot operator tools."""

from __future__ import annotations

import os
from typing import Any, Callable, Dict

from pydantic import BaseModel, Field

from data_juicer_agents.adapters.agentscope.tools import (
    build_agentscope_json_schema,
    build_agentscope_tool_function,
)
from data_juicer_agents.core.tool import ToolContext, ToolSpec
from data_juicer_agents.tools.retrieve.get_operator_info.tool import GET_OPERATOR_INFO
from data_juicer_agents.tools.retrieve.retrieve_operators_api.tool import (
    RETRIEVE_OPERATORS_API,
)


class QARetrieveOperatorsAPIInput(BaseModel):
    intent: str = Field(
        description=(
            "Natural-language description of the operator capability you want "
            "to find in Data-Juicer."
        )
    )
    top_k: int = Field(
        default=10,
        ge=1,
        description="Maximum number of operator candidates to return.",
    )
    op_type: str = Field(
        default="",
        description=(
            "Optional operator type filter (for example: 'filter', 'mapper', "
            "'deduplicator', 'selector', 'grouper', 'aggregator', 'pipeline')."
        ),
    )
    tags: list[str] = Field(
        default_factory=list,
        description=(
            "Optional tags to constrain retrieval, such as 'text', 'image', "
            "'multimodal', 'audio', 'video', 'cpu', 'gpu', or 'api'."
        ),
    )
    dataset_path: str = Field(
        default="",
        description=(
            "Optional dataset path used to infer modality tags and improve "
            "operator retrieval."
        ),
    )


def _qa_retrieve_operators_api(ctx: ToolContext, args: QARetrieveOperatorsAPIInput):
    return RETRIEVE_OPERATORS_API.execute(
        ctx,
        {
            "intent": args.intent,
            "top_k": args.top_k,
            "mode": "llm",
            "op_type": args.op_type,
            "tags": list(args.tags),
            "dataset_path": args.dataset_path,
        },
    )


QA_RETRIEVE_OPERATORS_API = ToolSpec(
    name="retrieve_operators_api",
    description=(
        "Retrieve candidate Data-Juicer operators for a natural-language intent. "
        "This QA runtime always uses llm mode internally."
    ),
    input_model=QARetrieveOperatorsAPIInput,
    output_model=RETRIEVE_OPERATORS_API.output_model,
    executor=_qa_retrieve_operators_api,
    tags=RETRIEVE_OPERATORS_API.tags,
    effects=RETRIEVE_OPERATORS_API.effects,
    confirmation=RETRIEVE_OPERATORS_API.confirmation,
)


def _build_tool_context() -> ToolContext:
    qa_root = os.path.dirname(os.path.abspath(__file__))
    artifacts_dir = os.path.join(qa_root, ".tool_artifacts")
    os.makedirs(artifacts_dir, exist_ok=True)
    return ToolContext(
        working_dir=qa_root,
        env=dict(os.environ),
        artifacts_dir=artifacts_dir,
    )


def _runtime_invoke(
    _tool_name: str,
    _args: Dict[str, Any],
    fn: Callable[[], Dict[str, Any]],
) -> Dict[str, Any]:
    return fn()


def register_qa_operator_tools(toolkit) -> None:
    for spec in (QA_RETRIEVE_OPERATORS_API, GET_OPERATOR_INFO):
        func = build_agentscope_tool_function(
            spec,
            ctx_factory=_build_tool_context,
            runtime_invoke=_runtime_invoke,
        )
        toolkit.register_tool_function(
            func,
            json_schema=build_agentscope_json_schema(spec),
        )


__all__ = [
    "QA_RETRIEVE_OPERATORS_API",
    "register_qa_operator_tools",
]
