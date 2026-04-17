# -*- coding: utf-8 -*-
"""Tool spec for inspect_dataset."""

from __future__ import annotations

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec
from data_juicer_agents.utils.runtime_helpers import to_int

from .input import GenericOutput, InspectDatasetInput
from .logic import inspect_dataset_schema


def _inspect_dataset(_ctx: ToolContext, args: InspectDatasetInput) -> ToolResult:
    payload = inspect_dataset_schema(
        dataset_source=args.dataset_source,
        sample_size=max(to_int(args.sample_size, 20), 1),
    )
    if payload.get("ok"):
        return ToolResult.success(summary=str(payload.get("message", "dataset inspected")), data=payload)
    return ToolResult.failure(
        summary=str(payload.get("error") or payload.get("message") or "inspect_dataset failed"),
        error_type=str(payload.get("error_type", "inspect_failed")),
        data={
            "ok": False,
            "error_type": str(payload.get("error_type", "inspect_failed")),
            "message": str(payload.get("error") or payload.get("message") or "inspect_dataset failed"),
            **payload,
        },
    )


INSPECT_DATASET = ToolSpec(
    name="inspect_dataset",
    description="Inspect a dataset sample to identify modality, keys, and sample statistics.",
    input_model=InspectDatasetInput,
    output_model=GenericOutput,
    executor=_inspect_dataset,
    tags=("dataset", "inspect"),
    effects="read",
    confirmation="none",
)


__all__ = ["INSPECT_DATASET"]
