# -*- coding: utf-8 -*-

from pathlib import Path

import pytest
import yaml
from agentscope.message import Msg

from data_juicer_agents.adapters.agentscope import invoke_tool_spec
from data_juicer_agents.capabilities.session.orchestrator import DJSessionAgent
from data_juicer_agents.capabilities.session.runtime import SessionState, SessionToolRuntime
from data_juicer_agents.capabilities.session.toolkit import get_session_tool_specs
from data_juicer_agents.core.tool import ToolContext, build_default_tool_registry, list_tool_specs


def test_session_agent_toolkit_uses_staged_plan_tools_not_plan_build():
    pytest.importorskip("agentscope")
    agent = DJSessionAgent(use_llm_router=False)
    toolkit = agent._build_toolkit()  # pylint: disable=protected-access
    names = set(toolkit.tools.keys())
    assert "build_dataset_spec" in names
    assert "build_process_spec" in names
    assert "build_system_spec" in names
    assert "assemble_plan" in names
    assert "plan_build" not in names
    assert "plan_generate" not in names
    assert "trace_run" not in names


def test_session_toolkit_selects_explicit_tools_without_session_tags():
    specs = get_session_tool_specs()
    names = [spec.name for spec in specs]
    all_names = {spec.name for spec in list_tool_specs()}

    assert {spec.name for spec in specs} == all_names
    assert all("session" not in spec.tags for spec in specs)
    assert "inspect_dataset" in names
    assert "retrieve_operators" in names
    assert "build_dataset_spec" in names
    assert "build_process_spec" in names
    assert "build_system_spec" in names
    assert "assemble_plan" in names
    assert "apply_recipe" in names
    assert "execute_shell_command" in names
    assert "plan_build" not in names
    assert "trace_run" not in names


def test_build_process_spec_is_deterministic_with_explicit_operators(tmp_path: Path):
    registry = build_default_tool_registry()
    ctx = ToolContext(working_dir=str(tmp_path), artifacts_dir=str(tmp_path / ".djx"))

    result = invoke_tool_spec(
        registry.get("build_process_spec"),
        ctx=ctx,
        raw_kwargs={
            "operators": [
                {"name": "text_length_filter", "params": {"max_len": 1500}},
            ],
        },
    )

    assert result["ok"] is True
    assert result["process_spec"]["operators"] == [
        {"name": "text_length_filter", "params": {"max_len": 1500}},
    ]


def test_session_agent_staged_plan_validate_save_with_explicit_payloads(tmp_path: Path, monkeypatch):
    dataset = tmp_path / "data.jsonl"
    dataset.write_text('{"text": "hello world"}\n', encoding="utf-8")
    export_path = tmp_path / "out" / "result.jsonl"
    export_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path = tmp_path / "saved_plan.yaml"

    registry = build_default_tool_registry()
    ctx = ToolContext(working_dir=str(tmp_path), artifacts_dir=str(tmp_path / ".djx"))

    monkeypatch.setattr(
        "data_juicer_agents.tools.retrieve.retrieve_operators.tool.retrieve_operator_candidates",
        lambda **_kwargs: {
            "ok": True,
            "retrieval_source": "llm",
            "candidate_count": 1,
            "candidates": [
                {
                    "operator_name": "text_length_filter",
                    "description": "Filter rows by text length.",
                    "operator_type": "filter",
                    "arguments_preview": ["max_len (int): maximum text length to keep."],
                }
            ],
            "notes": [],
        },
    )
    inspected = invoke_tool_spec(
        registry.get("inspect_dataset"),
        ctx=ctx,
        raw_kwargs={"dataset_path": str(dataset), "sample_size": 5},
    )
    assert inspected["ok"] is True

    retrieved = invoke_tool_spec(
        registry.get("retrieve_operators"),
        ctx=ctx,
        raw_kwargs={"intent": "filter rows longer than 1500 characters", "dataset_path": str(dataset)},
    )
    assert retrieved["ok"] is True
    assert retrieved["candidate_names"] == ["text_length_filter"]

    dataset_spec = invoke_tool_spec(
        registry.get("build_dataset_spec"),
        ctx=ctx,
        raw_kwargs={
            "intent": "filter rows longer than 1500 characters",
            "dataset_path": str(dataset),
            "export_path": str(export_path),
            "dataset_profile": inspected,
        },
    )
    assert dataset_spec["ok"] is True
    assert dataset_spec["dataset_spec"]["binding"]["text_keys"] == ["text"]

    process_spec = invoke_tool_spec(
        registry.get("build_process_spec"),
        ctx=ctx,
        raw_kwargs={
            "operators": [
                {"name": "text_length_filter", "params": {"max_len": 1500}},
            ],
        },
    )
    assert process_spec["ok"] is True
    assert process_spec["process_spec"]["operators"][0]["name"] == "text_length_filter"
    assert "warnings" in process_spec

    system_spec = invoke_tool_spec(
        registry.get("build_system_spec"),
        ctx=ctx,
        raw_kwargs={"custom_operator_paths": []},
    )
    assert system_spec["ok"] is True
    assert system_spec["system_spec"]["np"] == 1
    assert system_spec["warnings"]

    validated_dataset = invoke_tool_spec(
        registry.get("validate_dataset_spec"),
        ctx=ctx,
        raw_kwargs={"dataset_spec": dataset_spec["dataset_spec"], "dataset_profile": inspected},
    )
    assert validated_dataset["ok"] is True

    validated_process = invoke_tool_spec(
        registry.get("validate_process_spec"),
        ctx=ctx,
        raw_kwargs={"process_spec": process_spec["process_spec"]},
    )
    assert validated_process["ok"] is True
    assert any("deferred" in item for item in validated_process["warnings"])

    assembled = invoke_tool_spec(
        registry.get("assemble_plan"),
        ctx=ctx,
        raw_kwargs={
            "intent": "filter rows longer than 1500 characters",
            "dataset_spec": dataset_spec["dataset_spec"],
            "process_spec": process_spec["process_spec"],
            "system_spec": system_spec["system_spec"],
            "approval_required": True,
        },
    )
    assert assembled["ok"] is True
    assert assembled["action"] == "assemble_plan"
    assert assembled["warnings"]
    assert assembled["plan"]["operators"][0]["params"]["max_len"] == 1500

    validated = invoke_tool_spec(
        registry.get("plan_validate"),
        ctx=ctx,
        raw_kwargs={"plan_payload": assembled["plan"]},
    )
    assert validated["ok"] is True
    assert validated["warnings"]

    saved = invoke_tool_spec(
        registry.get("plan_save"),
        ctx=ctx,
        raw_kwargs={"plan_payload": assembled["plan"], "output_path": str(plan_path), "overwrite": True},
    )
    assert saved["ok"] is True
    payload = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
    assert payload["plan_id"] == assembled["plan_id"]
    assert "workflow" not in payload
    assert payload["np"] == 1
    assert payload["warnings"]


def test_session_runtime_remains_observational_after_tool_invocation(tmp_path: Path):
    runtime = SessionToolRuntime(state=SessionState(dataset_path="/tmp/original.jsonl"))
    ctx = ToolContext(
        working_dir=str(tmp_path),
        artifacts_dir=str(tmp_path / ".djx"),
        runtime_values={"session_runtime": runtime},
    )
    registry = build_default_tool_registry()

    result = invoke_tool_spec(
        registry.get("build_process_spec"),
        ctx=ctx,
        raw_kwargs={
            "operators": [{"name": "text_length_filter", "params": {"max_len": 100}}],
        },
    )

    assert result["ok"] is True
    assert runtime.state.process_spec is None
    assert runtime.state.dataset_path == "/tmp/original.jsonl"


def test_session_agent_handle_message_async_uses_async_react_path(monkeypatch):
    agent = DJSessionAgent(use_llm_router=False)
    agent._react_agent = object()  # pylint: disable=protected-access
    raw_reply = Msg(
        name="assistant",
        role="assistant",
        content=[{"type": "thinking", "thinking": "trace"}, {"type": "text", "text": "done"}],
    )

    async def _fake_react_reply_msg_async(message):
        assert message == "hello"
        return raw_reply, "done", "trace", False

    monkeypatch.setattr(agent, "_react_reply_msg_async", _fake_react_reply_msg_async)

    import asyncio

    reply = asyncio.run(agent.handle_message_async("hello"))

    assert reply.text == "done"
    assert reply.thinking == "trace"
    assert reply.stop is False
    assert agent.state.history == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "done"},
    ]


def test_session_agent_does_not_leak_raw_msg_repr_when_reply_has_no_text(monkeypatch):
    agent = DJSessionAgent(use_llm_router=False)
    agent._react_agent = object()  # pylint: disable=protected-access

    async def _fake_react_reply_msg_async(_message):
        reply = Msg(
            name="assistant",
            role="assistant",
            content=[{"type": "tool_use", "name": "noop", "input": {}}],
        )
        return reply, agent._extract_reply_text_and_thinking(reply)[0], "", False  # pylint: disable=protected-access

    monkeypatch.setattr(agent, "_react_reply_msg_async", _fake_react_reply_msg_async)

    import asyncio

    reply = asyncio.run(agent.handle_message_async("hello"))

    assert reply.text == "The request was processed, but no displayable text was returned."
    assert "Msg(" not in reply.text


def test_session_agent_handle_as_studio_turn_async_preserves_react_msg(monkeypatch):
    agent = DJSessionAgent(use_llm_router=False)
    agent._react_agent = object()  # pylint: disable=protected-access

    raw_reply = Msg(
        name="assistant",
        role="assistant",
        content=[
            {"type": "thinking", "thinking": "trace"},
            {"type": "text", "text": "done"},
        ],
        metadata={"source": "react"},
    )

    async def _fake_react_reply_msg_async(message):
        assert message == "hello"
        return raw_reply, "done", "trace", False

    monkeypatch.setattr(agent, "_react_reply_msg_async", _fake_react_reply_msg_async)

    import asyncio

    streamed = []

    async def _emit_chunk(msg, last):
        streamed.append((msg, last))

    reply = asyncio.run(
        agent.handle_as_studio_turn_async(
            Msg(name="user", role="user", content="hello"),
            _emit_chunk,
        )
    )

    assert reply.msg is raw_reply
    assert reply.stop is False
    assert reply.should_emit_final is True
    assert streamed == []
    assert agent.state.history == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "done"},
    ]
    assert reply.msg.metadata["source"] == "react"
    assert reply.msg.metadata["dj_thinking"] == "trace"


def test_session_agent_handle_as_studio_turn_async_avoids_duplicate_final_after_streamed_last(monkeypatch):
    agent = DJSessionAgent(use_llm_router=False)
    agent._react_agent = object()  # pylint: disable=protected-access

    raw_reply = Msg(
        name="assistant",
        role="assistant",
        content=[{"type": "text", "text": "done"}],
    )

    async def _fake_react_reply_msg_async(_message):
        await agent._forward_stream_chunk(Msg(name="assistant", role="assistant", content=[{"type": "text", "text": "part"}]), False)  # pylint: disable=protected-access
        await agent._forward_stream_chunk(Msg(name="assistant", role="assistant", content=[{"type": "text", "text": "done"}]), True)  # pylint: disable=protected-access
        return raw_reply, "done", "", False

    monkeypatch.setattr(agent, "_react_reply_msg_async", _fake_react_reply_msg_async)

    streamed = []

    async def _emit_chunk(msg, last):
        streamed.append((msg.content, last, dict(getattr(msg, "metadata", None) or {})))

    import asyncio

    reply = asyncio.run(
        agent.handle_as_studio_turn_async(
            Msg(name="user", role="user", content="hello"),
            _emit_chunk,
        )
    )

    assert reply.should_emit_final is False
    assert streamed == [
        ([{"type": "text", "text": "part"}], False, {"dj_stream": True}),
        ([{"type": "text", "text": "done"}], True, {"dj_stream": True}),
    ]


def test_session_agent_handle_as_studio_turn_async_marks_final_emit_when_no_stream(monkeypatch):
    agent = DJSessionAgent(use_llm_router=False)
    agent._react_agent = object()  # pylint: disable=protected-access

    raw_reply = Msg(name="assistant", role="assistant", content=[{"type": "text", "text": "done"}])

    async def _fake_react_reply_msg_async(_message):
        return raw_reply, "done", "", False

    monkeypatch.setattr(agent, "_react_reply_msg_async", _fake_react_reply_msg_async)

    streamed = []

    async def _emit_chunk(msg, last):
        streamed.append((msg, last))

    import asyncio

    reply = asyncio.run(
        agent.handle_as_studio_turn_async(
            Msg(name="user", role="user", content="hello"),
            _emit_chunk,
        )
    )

    assert reply.should_emit_final is True
    assert streamed == []


def test_session_agent_handle_as_studio_turn_async_handles_exit_without_stream():
    agent = DJSessionAgent(use_llm_router=False)

    streamed = []

    async def _emit_chunk(msg, last):
        streamed.append((msg, last))

    import asyncio

    reply = asyncio.run(
        agent.handle_as_studio_turn_async(
            Msg(name="user", role="user", content="exit"),
            _emit_chunk,
        )
    )

    assert reply.stop is True
    assert reply.should_emit_final is True
    assert streamed == []
    assert reply.msg.metadata["dj_stop"] is True


def test_session_agent_forward_stream_chunk_uses_callback():
    from agentscope.message import Msg

    seen = []

    async def _callback(msg, last):
        seen.append((msg.content, last))

    agent = DJSessionAgent(use_llm_router=False, enable_streaming=True)
    agent._stream_callback = _callback  # pylint: disable=protected-access

    asyncio = __import__("asyncio")
    asyncio.run(agent._forward_stream_chunk(Msg(name="assistant", role="assistant", content="chunk"), False))  # pylint: disable=protected-access

    assert seen == [("chunk", False)]


def test_session_agent_forward_stream_chunk_ignores_callback_failure():
    from agentscope.message import Msg

    async def _callback(_msg, _last):
        raise RuntimeError("boom")

    agent = DJSessionAgent(use_llm_router=False, enable_streaming=True, verbose=True)
    agent._stream_callback = _callback  # pylint: disable=protected-access

    asyncio = __import__("asyncio")
    asyncio.run(agent._forward_stream_chunk(Msg(name="assistant", role="assistant", content="chunk"), True))  # pylint: disable=protected-access


def test_session_agent_build_react_agent_enables_model_streaming(monkeypatch):
    seen = {}

    class _Model:
        def __init__(self, **kwargs):
            seen["stream"] = kwargs.get("stream")

    class _Formatter:
        pass

    class _Agent:
        def __init__(self, **kwargs):
            self.print = self._print
            seen["agent_kwargs"] = kwargs

        async def _print(self, msg, last=True, speech=None):  # noqa: ARG002
            return None

        def register_instance_hook(self, *_args, **_kwargs):
            return None

        def set_console_output_enabled(self, enabled):
            seen["console_enabled"] = enabled

    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    monkeypatch.setattr("agentscope.model.OpenAIChatModel", _Model)
    monkeypatch.setattr("agentscope.formatter.OpenAIChatFormatter", _Formatter)
    monkeypatch.setattr("agentscope.agent.ReActAgent", _Agent)

    agent = DJSessionAgent(use_llm_router=False, enable_streaming=True)
    react_agent = agent._build_react_agent()  # pylint: disable=protected-access

    assert seen["stream"] is True
    assert seen["console_enabled"] is False
    assert callable(react_agent.print)
