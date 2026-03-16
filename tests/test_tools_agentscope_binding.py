# -*- coding: utf-8 -*-

import json

import pytest

from data_juicer_agents.adapters.agentscope import (
    build_agentscope_json_schema,
    build_agentscope_tool_function,
)
from data_juicer_agents.core.tool import ToolContext, build_default_tool_registry


def test_build_agentscope_json_schema_uses_input_model():
    spec = build_default_tool_registry().get("retrieve_operators")
    schema = build_agentscope_json_schema(spec)

    assert schema["type"] == "function"
    assert schema["function"]["name"] == "retrieve_operators"
    assert "intent" in schema["function"]["parameters"]["properties"]
    assert "top_k" in schema["function"]["parameters"]["properties"]


def test_build_process_spec_schema_stays_shallow_for_agent_calls():
    spec = build_default_tool_registry().get("build_process_spec")
    schema = build_agentscope_json_schema(spec)
    params = schema["function"]["parameters"]

    assert schema["function"]["name"] == "build_process_spec"
    assert params["required"] == ["operators"]
    assert "operators" in params["properties"]
    assert "$defs" not in params
    assert "fill appropriate params" in params["properties"]["operators"]["description"]
    assert params["properties"]["operators"]["items"]["required"] == ["name", "params"]


def test_build_agentscope_tool_function_uses_arg_preview():
    pytest.importorskip("agentscope")
    spec = build_default_tool_registry().get("execute_python_code")
    seen = {}

    def fake_runtime_invoke(tool_name, args, fn):
        seen["tool_name"] = tool_name
        seen["args"] = dict(args)
        return fn()

    func = build_agentscope_tool_function(
        spec,
        ctx_factory=lambda: ToolContext(),
        runtime_invoke=fake_runtime_invoke,
    )
    long_code = "print('x')\n" * 300
    response = func(code=long_code, timeout=5)
    payload = json.loads(response.content[0]["text"])

    assert seen["tool_name"] == "execute_python_code"
    assert "[truncated" in seen["args"]["code"]
    assert payload["action"] == "execute_python_code"
