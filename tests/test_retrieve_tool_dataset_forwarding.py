# -*- coding: utf-8 -*-

import os

import pytest

from data_juicer_agents.adapters.agentscope import invoke_tool_spec
from data_juicer_agents.core.tool import DatasetSource, ToolContext, build_default_tool_registry

_has_api_key = bool(
    (os.environ.get("DASHSCOPE_API_KEY") or "").strip()
    or (os.environ.get("MODELSCOPE_API_TOKEN") or "").strip()
)
_skip_no_api_key = pytest.mark.skipif(
    not _has_api_key,
    reason="DASHSCOPE_API_KEY / MODELSCOPE_API_TOKEN not set",
)


def test_retrieve_operators_accepts_dataset_on_real_local_backend(tmp_path):
    dataset_path = tmp_path / "sample.jsonl"
    dataset_path.write_text('{"text":"hello world"}\n', encoding="utf-8")
    dataset_source = DatasetSource(config={"configs": [{"type": "local", "path": str(dataset_path)}]})
    registry = build_default_tool_registry()
    result = invoke_tool_spec(
        registry.get("retrieve_operators"),
        ctx=ToolContext(working_dir=str(tmp_path)),
        raw_kwargs={
            "intent": "filter text by length",
            "mode": "auto",
            "top_k": 3,
            "dataset_source": dataset_source,
        },
    )

    assert result["ok"] is True
    assert "text" in result.get("inferred_tags", [])
    assert "text" in result.get("effective_tags", [])


@_skip_no_api_key
def test_retrieve_operators_api_accepts_dataset_on_real_backend(tmp_path):
    dataset_path = tmp_path / "sample.jsonl"
    dataset_path.write_text('{"text":"hello world"}\n', encoding="utf-8")
    dataset_source = DatasetSource(config={"configs": [{"type": "local", "path": str(dataset_path)}]})
    registry = build_default_tool_registry()
    result = invoke_tool_spec(
        registry.get("retrieve_operators_api"),
        ctx=ToolContext(working_dir=str(tmp_path)),
        raw_kwargs={
            "intent": "filter text by length",
            "mode": "auto",
            "top_k": 3,
            "dataset_source": dataset_source,
        },
    )

    assert result["ok"] is True
    assert isinstance(result.get("retrieval_trace"), list)
    assert "missing_required" not in str(result.get("error_type", ""))
