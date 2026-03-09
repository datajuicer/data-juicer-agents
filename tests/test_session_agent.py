# -*- coding: utf-8 -*-

from pathlib import Path

import pytest
import yaml

from data_juicer_agents.capabilities.session.orchestrator import DJSessionAgent


def test_session_agent_exit_command_short_circuit():
    agent = DJSessionAgent(use_llm_router=False)
    reply = agent.handle_message("exit")
    assert reply.stop is True
    assert "Session ended" in reply.text


def test_session_agent_sys_prompt_limits_default_working_directory():
    agent = DJSessionAgent(use_llm_router=False)
    prompt = agent._session_sys_prompt()
    assert "current working directory: ./.djx" in prompt
    assert "only read, write, create, or execute files/commands inside" in prompt
    assert "always send a final user-facing reply for that turn" in prompt
    assert "If any new files were saved or written" in prompt
    assert "If you want ..., tell me ..., and I will ..." in prompt


def test_session_agent_sys_prompt_uses_custom_working_directory():
    agent = DJSessionAgent(use_llm_router=False, working_dir="./workspace")
    prompt = agent._session_sys_prompt()
    assert "current working directory: ./workspace" in prompt
    assert "new working directory for this session" in prompt


def test_session_agent_cancel_without_pending():
    agent = DJSessionAgent(use_llm_router=False)
    reply = agent.handle_message("cancel")
    assert "No pending action" in reply.text


def test_session_agent_requires_react_for_natural_language():
    agent = DJSessionAgent(use_llm_router=False)
    reply = agent.handle_message("帮我做一个RAG清洗计划")
    assert reply.stop is True
    assert "ReAct agent is unavailable" in reply.text


def test_session_agent_tool_plan_updates_context(monkeypatch, tmp_path: Path):
    from data_juicer_agents.capabilities.session import orchestrator as session_mod

    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello"}\n', encoding="utf-8")
    export = tmp_path / "out.jsonl"
    output = tmp_path / "plan.yaml"

    called = {}

    def fake_execute_plan(args):
        called["dataset"] = args.dataset
        called["export"] = args.export
        called["output"] = args.output
        return {
            "ok": True,
            "exit_code": 0,
            "plan_path": str(args.output),
            "plan": {
                "plan_id": "plan_x",
                "workflow": "custom",
                "dataset_path": str(args.dataset),
                "export_path": str(args.export),
                "modality": "text",
                "text_keys": ["text"],
                "operators": [{"name": "text_length_filter", "params": {"min_len": 1}}],
            },
            "planning_meta": {},
            "attempts": [],
            "fallback_messages": [],
        }

    monkeypatch.setattr(session_mod, "execute_plan", fake_execute_plan)

    agent = DJSessionAgent(use_llm_router=False)
    result = agent.tool_plan(
        intent="做一个清洗计划",
        dataset_path=str(dataset),
        export_path=str(export),
        output_path=str(output),
    )

    assert result["ok"] is True
    assert called["dataset"] == str(dataset)
    assert called["export"] == str(export)
    assert called["output"] == str(output)
    assert agent.state.dataset_path == str(dataset)
    assert agent.state.export_path == str(export)
    assert agent.state.plan_path == str(output)


def test_session_agent_tool_apply_requires_confirmation():
    agent = DJSessionAgent(use_llm_router=False)

    result = agent.tool_apply(plan_path="/tmp/a.yaml", confirm=False)
    assert result["ok"] is False
    assert result["error_type"] == "confirmation_required"


def test_session_agent_tool_apply_updates_run_id(monkeypatch, tmp_path: Path):
    from data_juicer_agents.capabilities.session import orchestrator as session_mod

    plan = tmp_path / "plan.yaml"
    plan.write_text(
        "plan_id: plan_x\n"
        "user_intent: test\n"
        "workflow: custom\n"
        "dataset_path: a\n"
        "export_path: b\n"
        "modality: text\n"
        "text_keys: [text]\n"
        "operators:\n"
        "  - name: text_length_filter\n"
        "    params: {min_len: 1}\n",
        encoding="utf-8",
    )

    def fake_run_apply(args):
        print("Run Summary:")
        print("Run ID: run_123")
        return 0

    monkeypatch.setattr(session_mod, "run_apply", fake_run_apply)

    agent = DJSessionAgent(use_llm_router=False)
    result = agent.tool_apply(plan_path=str(plan), confirm=True)

    assert result["ok"] is True
    assert result["run_id"] == "run_123"
    assert agent.state.run_id == "run_123"


def test_session_agent_tool_apply_interrupted(monkeypatch, tmp_path: Path):
    from data_juicer_agents.capabilities.session import orchestrator as session_mod

    plan = tmp_path / "plan.yaml"
    plan.write_text(
        "plan_id: plan_x\n"
        "user_intent: test\n"
        "workflow: custom\n"
        "dataset_path: a\n"
        "export_path: b\n"
        "modality: text\n"
        "text_keys: [text]\n"
        "operators:\n"
        "  - name: text_length_filter\n"
        "    params: {min_len: 1}\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(session_mod, "run_apply", lambda _args: 130)
    agent = DJSessionAgent(use_llm_router=False)
    result = agent.tool_apply(plan_path=str(plan), confirm=True)
    assert result["ok"] is False
    assert result["error_type"] == "interrupted"


def test_session_agent_react_mode_handles_natural_language(monkeypatch):
    from data_juicer_agents.capabilities.session import orchestrator as session_mod

    monkeypatch.setattr(session_mod.DJSessionAgent, "_build_react_agent", lambda self: object())
    monkeypatch.setattr(session_mod.DJSessionAgent, "_react_reply", lambda self, message: ("react-response", False))

    agent = DJSessionAgent(use_llm_router=True)
    reply = agent.handle_message("hi")
    assert reply.text == "react-response"


def test_session_agent_init_failure_raises(monkeypatch):
    from data_juicer_agents.capabilities.session import orchestrator as session_mod

    def _raise(_self):
        raise RuntimeError("mock init failure")

    monkeypatch.setattr(session_mod.DJSessionAgent, "_build_react_agent", _raise)
    with pytest.raises(RuntimeError, match="Failed to initialize dj-agents ReAct session"):
        _ = DJSessionAgent(use_llm_router=True)


def test_session_agent_react_failure_exits(monkeypatch):
    from data_juicer_agents.capabilities.session import orchestrator as session_mod

    monkeypatch.setattr(session_mod.DJSessionAgent, "_build_react_agent", lambda self: object())

    def _raise(_self, _message):
        raise RuntimeError("mock call failure")

    monkeypatch.setattr(session_mod.DJSessionAgent, "_react_reply", _raise)
    agent = DJSessionAgent(use_llm_router=True)
    reply = agent.handle_message("hi")
    assert reply.stop is True
    assert "LLM session call failed" in reply.text


def test_session_agent_react_interrupted_returns_non_stop(monkeypatch):
    from data_juicer_agents.capabilities.session import orchestrator as session_mod

    monkeypatch.setattr(session_mod.DJSessionAgent, "_build_react_agent", lambda self: object())
    monkeypatch.setattr(
        session_mod.DJSessionAgent,
        "_react_reply",
        lambda self, _message: ("ignored", True),
    )

    agent = DJSessionAgent(use_llm_router=True)
    reply = agent.handle_message("请中断当前任务")
    assert reply.stop is False
    assert reply.interrupted is True
    assert "已中断" in reply.text


def test_session_agent_request_interrupt_uses_native_agent_interrupt(monkeypatch):
    from data_juicer_agents.capabilities.session import orchestrator as session_mod

    class _FakeLoop:
        def is_closed(self):
            return False

    class _FakeFuture:
        def result(self, timeout=None):
            return None

    class _FakeReactAgent:
        async def interrupt(self):
            return None

    captured = {}

    def _fake_run_coroutine_threadsafe(coro, loop):
        captured["loop"] = loop
        captured["is_coro"] = hasattr(coro, "close")
        if hasattr(coro, "close"):
            coro.close()
        return _FakeFuture()

    monkeypatch.setattr(session_mod.DJSessionAgent, "_build_react_agent", lambda self: _FakeReactAgent())
    monkeypatch.setattr(session_mod.asyncio, "run_coroutine_threadsafe", _fake_run_coroutine_threadsafe)

    agent = session_mod.DJSessionAgent(use_llm_router=True)
    agent._active_react_loop = _FakeLoop()
    agent._active_react_inflight = True

    assert agent.request_interrupt() is True
    assert captured["loop"] is agent._active_react_loop
    assert captured["is_coro"] is True


def test_session_agent_request_interrupt_returns_false_when_idle(monkeypatch):
    from data_juicer_agents.capabilities.session import orchestrator as session_mod

    monkeypatch.setattr(session_mod.DJSessionAgent, "_build_react_agent", lambda self: object())
    agent = session_mod.DJSessionAgent(use_llm_router=True)
    assert agent.request_interrupt() is False


def test_session_agent_verbose_logs_tool_call(capsys):
    agent = DJSessionAgent(use_llm_router=False, verbose=True)
    _ = agent.tool_get_context()
    captured = capsys.readouterr()
    assert "[dj-agents][debug] tool:get_session_context" in captured.out


def test_session_agent_tool_plan_passes_llm_config(monkeypatch, tmp_path: Path):
    from data_juicer_agents.capabilities.session import orchestrator as session_mod

    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello"}\n', encoding="utf-8")
    export = tmp_path / "out.jsonl"
    output = tmp_path / "plan.yaml"
    called = {}

    def fake_execute_plan(args):
        called["llm_api_key"] = args.llm_api_key
        called["llm_base_url"] = args.llm_base_url
        called["llm_thinking"] = args.llm_thinking
        called["planner_model"] = args.planner_model
        return {
            "ok": True,
            "exit_code": 0,
            "plan_path": str(args.output),
            "plan": {
                "plan_id": "plan_x",
                "workflow": "custom",
                "dataset_path": str(args.dataset),
                "export_path": str(args.export),
                "modality": "text",
                "text_keys": ["text"],
                "operators": [{"name": "text_length_filter", "params": {"min_len": 1}}],
            },
            "planning_meta": {},
            "attempts": [],
            "fallback_messages": [],
        }

    monkeypatch.setattr(session_mod, "execute_plan", fake_execute_plan)

    agent = DJSessionAgent(
        use_llm_router=False,
        api_key="sk-test-key",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        planner_model="qwen3-max-2026-01-23",
        thinking=True,
    )
    result = agent.tool_plan(
        intent="做一个清洗计划",
        dataset_path=str(dataset),
        export_path=str(export),
        output_path=str(output),
    )

    assert result["ok"] is True
    assert called["llm_api_key"] == "sk-test-key"
    assert called["llm_base_url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert called["llm_thinking"] is True
    assert called["planner_model"] == "qwen3-max-2026-01-23"


def test_session_agent_tool_plan_returns_structured_error(monkeypatch, tmp_path: Path):
    from data_juicer_agents.capabilities.session import orchestrator as session_mod

    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello"}\n', encoding="utf-8")
    export = tmp_path / "out.jsonl"

    monkeypatch.setattr(
        session_mod,
        "execute_plan",
        lambda _args: {
            "ok": False,
            "exit_code": 2,
            "error_type": "plan_failed",
            "error_code": "plan_validation_failed",
            "stage": "full-llm",
            "message": "Plan generation failed: invalid operators",
            "recoverable": True,
            "attempts": [{"name": "full-llm", "status": "failed"}],
            "next_actions": ["run retrieve_operators then retry"],
            "fallback_messages": [],
        },
    )

    agent = DJSessionAgent(use_llm_router=False)
    result = agent.tool_plan(
        intent="做一个清洗计划",
        dataset_path=str(dataset),
        export_path=str(export),
    )

    assert result["ok"] is False
    assert result["error_type"] == "plan_failed"
    assert result["plan_error"]["code"] == "plan_validation_failed"
    assert result["plan_error"]["stage"] == "full-llm"
    assert result["plan_error"]["attempts"] == [{"name": "full-llm", "status": "failed"}]


def test_extract_reply_text_and_thinking_prefers_thinking_block():
    class _ReplyMsg:
        @staticmethod
        def get_text_content():
            return "</think>\n最终答案"

        @staticmethod
        def get_content_blocks():
            return [
                {"type": "thinking", "thinking": "step 1\nstep 2"},
                {"type": "text", "text": "</think>\n最终答案"},
            ]

    reply_msg = _ReplyMsg()
    text, thinking = DJSessionAgent._extract_reply_text_and_thinking(reply_msg)
    assert text == "最终答案"
    assert "step 1" in thinking


def test_extract_reply_text_and_thinking_fallback_from_text_tag():
    class _ReplyMsg:
        @staticmethod
        def get_text_content():
            return "<think>内部推理</think>\n结论"

        @staticmethod
        def get_content_blocks():
            return [{"type": "text", "text": "<think>内部推理</think>\n结论"}]

    reply_msg = _ReplyMsg()
    text, thinking = DJSessionAgent._extract_reply_text_and_thinking(reply_msg)
    assert text == "结论"
    assert thinking == "内部推理"


def test_extract_reply_text_and_thinking_supports_text_field_blocks():
    class _ReplyMsg:
        @staticmethod
        def get_text_content():
            return "最终回答"

        @staticmethod
        def get_content_blocks():
            return [{"type": "thinking", "text": "先判断字段，再生成方案"}]

    reply_msg = _ReplyMsg()
    text, thinking = DJSessionAgent._extract_reply_text_and_thinking(reply_msg)
    assert text == "最终回答"
    assert thinking == "先判断字段，再生成方案"


def test_extract_reply_text_and_thinking_handles_leaked_close_tag():
    class _ReplyMsg:
        @staticmethod
        def get_text_content():
            return "internal reasoning line 1\nline 2\n</think>\n最终回答"

        @staticmethod
        def get_content_blocks():
            return [{"type": "text", "text": "internal reasoning line 1\nline 2\n</think>\n最终回答"}]

    reply_msg = _ReplyMsg()
    text, thinking = DJSessionAgent._extract_reply_text_and_thinking(reply_msg)
    assert text == "最终回答"
    assert "internal reasoning line 1" in thinking


def test_extract_reply_text_and_thinking_strips_reflective_tail_from_output():
    class _ReplyMsg:
        @staticmethod
        def get_text_content():
            return (
                "✅ 任务已完成！\n"
                "处理结果：保留 6 条。\n\n"
                "· The user requested to remove text samples with length greater than 1000.\n"
                "I have successfully completed this task."
            )

        @staticmethod
        def get_content_blocks():
            return [
                {
                    "type": "text",
                    "text": (
                        "✅ 任务已完成！\n"
                        "处理结果：保留 6 条。\n\n"
                        "· The user requested to remove text samples with length greater than 1000.\n"
                        "I have successfully completed this task."
                    ),
                }
            ]

    reply_msg = _ReplyMsg()
    text, thinking = DJSessionAgent._extract_reply_text_and_thinking(reply_msg)
    assert "任务已完成" in text
    assert "The user requested" not in text
    assert "The user requested" not in thinking


def test_extract_reply_text_and_thinking_strips_reflective_tail_without_bullet():
    class _ReplyMsg:
        @staticmethod
        def get_text_content():
            return (
                "处理已完成，输出保存在 ./data/demo-dataset_filtered.jsonl。\n\n"
                "The user requested to remove text samples with length greater than 1000.\n"
                "I have successfully completed this task."
            )

        @staticmethod
        def get_content_blocks():
            return [
                {
                    "type": "text",
                    "text": (
                        "处理已完成，输出保存在 ./data/demo-dataset_filtered.jsonl。\n\n"
                        "The user requested to remove text samples with length greater than 1000.\n"
                        "I have successfully completed this task."
                    ),
                }
            ]

    reply_msg = _ReplyMsg()
    text, thinking = DJSessionAgent._extract_reply_text_and_thinking(reply_msg)
    assert "处理已完成" in text
    assert "The user requested" not in text
    assert "The user requested" not in thinking


def test_extract_reply_text_and_thinking_strips_reflective_prefix_report():
    class _ReplyMsg:
        @staticmethod
        def get_text_content():
            return (
                "· The user requested to remove text samples longer than 1000 characters from the dataset. "
                "I successfully:\n\n"
                "1. **Inspected the dataset** - Found 20 samples with text field averaging 1874 characters\n"
                "2. **Retrieved relevant operators** - Identified `text_length_filter` as the best match\n"
                "3. **Applied the recipe** - Successfully executed with run_id `run_3cc01c3ba30e`\n"
                "The task is complete. The filtered dataset is saved at "
                "`./data/"
                "demo-dataset_filtered.jsonl`."
            )

        @staticmethod
        def get_content_blocks():
            return [
                {
                    "type": "text",
                    "text": _ReplyMsg.get_text_content(),
                }
            ]

    reply_msg = _ReplyMsg()
    text, thinking = DJSessionAgent._extract_reply_text_and_thinking(reply_msg)
    assert "The user requested" not in text
    assert "I successfully" not in text
    assert "**Inspected the dataset**" in text
    assert "demo-dataset_filtered.jsonl" in text
    assert "The user requested" not in thinking


def test_extract_reply_text_and_thinking_strips_reflective_thinking_summary():
    class _ReplyMsg:
        @staticmethod
        def get_text_content():
            return "✅ 任务完成：输出已保存。"

        @staticmethod
        def get_content_blocks():
            return [
                {
                    "type": "thinking",
                    "thinking": (
                        "The task has been successfully completed. Here's a summary:\n"
                        "1. inspected dataset\n"
                        "2. retrieved operators\n"
                        "3. applied recipe"
                    ),
                },
                {
                    "type": "text",
                    "text": "✅ 任务完成：输出已保存。",
                },
            ]

    reply_msg = _ReplyMsg()
    text, thinking = DJSessionAgent._extract_reply_text_and_thinking(reply_msg)
    assert text == "✅ 任务完成：输出已保存。"
    assert "The task has been successfully completed" not in thinking
    assert "Here's a summary" not in thinking
    assert thinking == ""


def test_extract_reply_text_and_thinking_keeps_short_plain_text():
    class _ReplyMsg:
        @staticmethod
        def get_text_content():
            return "The user requested deduplication."

        @staticmethod
        def get_content_blocks():
            return [{"type": "text", "text": "The user requested deduplication."}]

    reply_msg = _ReplyMsg()
    text, thinking = DJSessionAgent._extract_reply_text_and_thinking(reply_msg)
    assert text == "The user requested deduplication."
    assert thinking == ""


def test_build_reasoning_event_payload_with_tool_calls():
    class _ReasoningMsg:
        @staticmethod
        def get_content_blocks():
            return [
                {"type": "thinking", "thinking": "先判断数据结构"},
                {"type": "tool_use", "id": "call_1", "name": "inspect_dataset", "input": {"sample_size": 20}},
                {"type": "text", "text": "准备调用工具"},
            ]

    payload = DJSessionAgent._build_reasoning_event_payload(
        output=_ReasoningMsg(),
        step=2,
        tool_choice="auto",
    )
    assert payload is not None
    assert payload["step"] == 2
    assert payload["tool_choice"] == "auto"
    assert "先判断数据结构" in payload["thinking"]
    assert payload["has_tool_calls"] is True
    assert payload["planned_tools"][0]["name"] == "inspect_dataset"


def test_build_reasoning_event_payload_strips_reflective_tail():
    class _ReasoningMsg:
        @staticmethod
        def get_content_blocks():
            return [
                {
                    "type": "thinking",
                    "thinking": (
                        "先确认数据结构和字段。\n\n"
                        "The user requested ./data/demo-dataset.jsonl去除长度大于1000的文本\n"
                        "I have successfully completed this task."
                    ),
                },
                {
                    "type": "text",
                    "text": (
                        "计划已生成。\n\n"
                        "The user requested ./data/demo-dataset.jsonl去除长度大于1000的文本"
                    ),
                },
            ]

    payload = DJSessionAgent._build_reasoning_event_payload(
        output=_ReasoningMsg(),
        step=3,
        tool_choice="auto",
    )
    assert payload is not None
    assert "先确认数据结构" in payload["thinking"]
    assert "The user requested" not in payload["thinking"]
    assert "The user requested" not in payload["text_preview"]


def test_build_reasoning_event_payload_strips_reflective_prefix_report():
    class _ReasoningMsg:
        @staticmethod
        def get_content_blocks():
            return [
                {
                    "type": "thinking",
                    "thinking": (
                        "The user requested to remove text samples longer than 1000 characters.\n"
                        "I successfully:\n"
                        "1. 先看数据分布\n"
                        "2. 再检索候选算子"
                    ),
                }
            ]

    payload = DJSessionAgent._build_reasoning_event_payload(
        output=_ReasoningMsg(),
        step=8,
        tool_choice="auto",
    )
    assert payload is None


def test_build_reasoning_event_payload_strips_reflective_task_completed_summary():
    class _ReasoningMsg:
        @staticmethod
        def get_content_blocks():
            return [
                {
                    "type": "thinking",
                    "thinking": (
                        "The task has been successfully completed. Here's a summary:\n"
                        "1. inspected dataset\n"
                        "2. retrieved operators\n"
                        "3. generated plan"
                    ),
                },
                {
                    "type": "text",
                    "text": "The task has been successfully completed. Here's a summary:\n"
                    "plan saved to ./plans/filter_text_length_1000.yaml",
                },
            ]

    payload = DJSessionAgent._build_reasoning_event_payload(
        output=_ReasoningMsg(),
        step=9,
        tool_choice="auto",
    )
    assert payload is None


def test_build_reasoning_event_payload_empty_returns_none():
    class _ReasoningMsg:
        @staticmethod
        def get_content_blocks():
            return []

    payload = DJSessionAgent._build_reasoning_event_payload(
        output=_ReasoningMsg(),
        step=1,
        tool_choice=None,
    )
    assert payload is None


def test_session_agent_text_file_tools_roundtrip(tmp_path: Path):
    agent = DJSessionAgent(use_llm_router=False)
    path = tmp_path / "notes.txt"

    write_result = agent.tool_write_text_file(
        file_path=str(path),
        content="line1\nline3\n",
    )
    assert write_result["ok"] is True

    insert_result = agent.tool_insert_text_file(
        file_path=str(path),
        content="line2",
        line_number=2,
    )
    assert insert_result["ok"] is True

    replace_result = agent.tool_write_text_file(
        file_path=str(path),
        content="line-two",
        ranges=[2, 2],
    )
    assert replace_result["ok"] is True

    view_result = agent.tool_view_text_file(file_path=str(path))
    assert view_result["ok"] is True
    assert "line1" in view_result["content"]
    assert "line-two" in view_result["content"]
    assert "line3" in view_result["content"]


def test_session_agent_execute_shell_and_python_tools():
    agent = DJSessionAgent(use_llm_router=False)

    shell_result = agent.tool_execute_shell_command(
        command="echo hello_djx",
        timeout=5,
    )
    assert shell_result["returncode"] == 0
    assert "hello_djx" in shell_result["stdout"]

    py_result = agent.tool_execute_python_code(
        code="print('py_ok')",
        timeout=5,
    )
    assert py_result["returncode"] == 0
    assert "py_ok" in py_result["stdout"]


def test_session_agent_toolkit_includes_file_and_exec_tools():
    pytest.importorskip("agentscope")
    agent = DJSessionAgent(use_llm_router=False)
    toolkit = agent._build_toolkit()  # pylint: disable=protected-access
    names = set(toolkit.tools.keys())
    assert "view_text_file" in names
    assert "write_text_file" in names
    assert "insert_text_file" in names
    assert "execute_shell_command" in names
    assert "execute_python_code" in names
    assert "plan_retrieve_candidates" in names
    assert "plan_generate" in names
    assert "plan_validate" in names
    assert "plan_save" in names
    assert "plan_recipe" not in names


def test_session_agent_plan_chain_reuses_cached_retrieval(monkeypatch, tmp_path: Path):
    from data_juicer_agents.capabilities.session import orchestrator as session_mod
    from data_juicer_agents.capabilities.plan.schema import OperatorStep, PlanModel

    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello"}\n', encoding="utf-8")
    export = tmp_path / "out.jsonl"
    output = tmp_path / "plan.yaml"

    monkeypatch.setattr(
        session_mod,
        "retrieve_operator_candidates",
        lambda **_kwargs: {
            "ok": True,
            "candidate_count": 2,
            "candidates": [
                {"operator_name": "text_length_filter"},
                {"operator_name": "document_deduplicator"},
            ],
        },
    )

    captured = {}

    def fake_build_plan(self, **kwargs):  # noqa: ARG001
        captured["retrieved_candidates"] = kwargs.get("retrieved_candidates")
        return PlanModel(
            plan_id="plan_chain_1",
            user_intent=kwargs["user_intent"],
            workflow="custom",
            dataset_path=kwargs["dataset_path"],
            export_path=kwargs["export_path"],
            modality="text",
            text_keys=["text"],
            operators=[OperatorStep(name="text_length_filter", params={"max_len": 1000})],
            custom_operator_paths=list(kwargs.get("custom_operator_paths") or []),
        )

    monkeypatch.setattr(session_mod.PlanUseCase, "build_plan", fake_build_plan)
    monkeypatch.setattr(session_mod.PlanValidator, "validate", staticmethod(lambda _plan: []))
    monkeypatch.setattr(
        session_mod.PlanValidator,
        "llm_review",
        staticmethod(lambda _plan: {"errors": [], "warnings": []}),
    )

    agent = DJSessionAgent(use_llm_router=False)
    inspected = agent.tool_inspect_dataset(dataset_path=str(dataset), sample_size=5)
    assert inspected["ok"] is True
    retrieval = agent.tool_plan_retrieve_candidates(
        intent="filter long text",
        dataset_path=str(dataset),
    )
    assert retrieval["ok"] is True
    assert retrieval["candidate_names"] == ["text_length_filter", "document_deduplicator"]

    generated = agent.tool_plan_generate(
        intent="filter long text",
        dataset_path=str(dataset),
        export_path=str(export),
        output_path=str(output),
    )
    assert generated["ok"] is True
    assert captured["retrieved_candidates"] == ["text_length_filter", "document_deduplicator"]

    validated = agent.tool_plan_validate()
    assert validated["ok"] is True
    assert validated["plan_id"] == "plan_chain_1"

    saved = agent.tool_plan_save(output_path=str(output))
    assert saved["ok"] is True
    assert Path(saved["plan_path"]).exists()
    payload = yaml.safe_load(Path(saved["plan_path"]).read_text(encoding="utf-8"))
    assert payload["plan_id"] == "plan_chain_1"


def test_session_agent_plan_generate_without_inspect_is_allowed(monkeypatch, tmp_path: Path):
    from data_juicer_agents.capabilities.session import orchestrator as session_mod
    from data_juicer_agents.capabilities.plan.schema import OperatorStep, PlanModel

    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello"}\n', encoding="utf-8")
    export = tmp_path / "out.jsonl"

    captured = {}

    def fake_build_plan(self, **kwargs):  # noqa: ARG001
        captured["called"] = True
        return PlanModel(
            plan_id="plan_no_inspect_ok",
            user_intent=kwargs["user_intent"],
            workflow="custom",
            dataset_path=kwargs["dataset_path"],
            export_path=kwargs["export_path"],
            modality="text",
            text_keys=["text"],
            operators=[OperatorStep(name="text_length_filter", params={"max_len": 1000})],
        )

    monkeypatch.setattr(
        session_mod.PlanUseCase,
        "build_plan",
        fake_build_plan,
    )
    monkeypatch.setattr(session_mod.PlanValidator, "validate", staticmethod(lambda _plan: []))
    monkeypatch.setattr(
        session_mod.PlanValidator,
        "llm_review",
        staticmethod(lambda _plan: {"errors": [], "warnings": []}),
    )

    agent = DJSessionAgent(use_llm_router=False)
    result = agent.tool_plan_generate(
        intent="filter long text",
        dataset_path=str(dataset),
        export_path=str(export),
    )
    assert result["ok"] is True
    assert result["plan_id"] == "plan_no_inspect_ok"
    assert captured.get("called") is True
    assert result["output_path_hint"] is None
    assert agent.state.draft_plan_path_hint is None
    assert agent.state.plan_path is None


def test_session_agent_plan_generate_llm_review_default_off_but_can_enable(monkeypatch, tmp_path: Path):
    from data_juicer_agents.capabilities.session import orchestrator as session_mod
    from data_juicer_agents.capabilities.plan.schema import OperatorStep, PlanModel

    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello"}\n', encoding="utf-8")
    export = tmp_path / "out.jsonl"
    called = {"review": 0}

    monkeypatch.setattr(
        session_mod.PlanUseCase,
        "build_plan",
        lambda self, **kwargs: PlanModel(  # noqa: ARG005
            plan_id="plan_review_toggle",
            user_intent=kwargs["user_intent"],
            workflow="custom",
            dataset_path=kwargs["dataset_path"],
            export_path=kwargs["export_path"],
            modality="text",
            text_keys=["text"],
            operators=[OperatorStep(name="text_length_filter", params={"max_len": 1000})],
        ),
    )
    monkeypatch.setattr(session_mod.PlanValidator, "validate", staticmethod(lambda _plan: []))

    def _review(_plan):
        called["review"] += 1
        return {"errors": [], "warnings": []}

    monkeypatch.setattr(
        session_mod.PlanValidator,
        "llm_review",
        staticmethod(_review),
    )

    agent = DJSessionAgent(use_llm_router=False)
    default_result = agent.tool_plan_generate(
        intent="filter long text",
        dataset_path=str(dataset),
        export_path=str(export),
    )
    assert default_result["ok"] is True
    assert default_result["llm_review_enabled"] is False
    assert called["review"] == 0

    enabled_result = agent.tool_plan_generate(
        intent="filter long text",
        dataset_path=str(dataset),
        export_path=str(export),
        include_llm_review=True,
    )
    assert enabled_result["ok"] is True
    assert enabled_result["llm_review_enabled"] is True
    assert called["review"] == 1


def test_session_agent_plan_validate_with_missing_path_falls_back_to_draft(monkeypatch, tmp_path: Path):
    from data_juicer_agents.capabilities.session import orchestrator as session_mod
    from data_juicer_agents.capabilities.plan.schema import OperatorStep, PlanModel

    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello"}\n', encoding="utf-8")
    export = tmp_path / "out.jsonl"

    monkeypatch.setattr(
        session_mod.PlanUseCase,
        "build_plan",
        lambda self, **kwargs: PlanModel(  # noqa: ARG005
            plan_id="plan_fallback_validate",
            user_intent=kwargs["user_intent"],
            workflow="custom",
            dataset_path=kwargs["dataset_path"],
            export_path=kwargs["export_path"],
            modality="text",
            text_keys=["text"],
            operators=[OperatorStep(name="text_length_filter", params={"max_len": 1000})],
        ),
    )
    monkeypatch.setattr(session_mod.PlanValidator, "validate", staticmethod(lambda _plan: []))
    monkeypatch.setattr(
        session_mod.PlanValidator,
        "llm_review",
        staticmethod(lambda _plan: {"errors": [], "warnings": []}),
    )

    agent = DJSessionAgent(use_llm_router=False)
    generated = agent.tool_plan_generate(
        intent="filter long text",
        dataset_path=str(dataset),
        export_path=str(export),
    )
    assert generated["ok"] is True

    validated = agent.tool_plan_validate(
        plan_path=str(tmp_path / "missing-plan.yaml"),
        include_llm_review=False,
        use_draft=True,
    )
    assert validated["ok"] is True
    assert validated["plan_source"] == "draft_fallback"
    assert validated["error_count"] == 0
    assert validated["warnings"]
    assert "fallback to draft plan" in validated["warnings"][0]


def test_session_agent_plan_save_without_output_path_allocates_lazy_default(
    monkeypatch, tmp_path: Path
):
    from data_juicer_agents.capabilities.session import orchestrator as session_mod
    from data_juicer_agents.capabilities.plan.schema import OperatorStep, PlanModel

    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello"}\n', encoding="utf-8")
    export = tmp_path / "out.jsonl"

    monkeypatch.setattr(
        session_mod.PlanUseCase,
        "build_plan",
        lambda self, **kwargs: PlanModel(  # noqa: ARG005
            plan_id="plan_lazy_save",
            user_intent=kwargs["user_intent"],
            workflow="custom",
            dataset_path=kwargs["dataset_path"],
            export_path=kwargs["export_path"],
            modality="text",
            text_keys=["text"],
            operators=[OperatorStep(name="text_length_filter", params={"max_len": 1000})],
        ),
    )
    monkeypatch.setattr(session_mod.PlanValidator, "validate", staticmethod(lambda _plan: []))
    monkeypatch.setattr(
        session_mod.PlanValidator,
        "llm_review",
        staticmethod(lambda _plan: {"errors": [], "warnings": []}),
    )

    agent = DJSessionAgent(use_llm_router=False)
    generated = agent.tool_plan_generate(
        intent="filter long text",
        dataset_path=str(dataset),
        export_path=str(export),
    )
    assert generated["ok"] is True
    assert generated["output_path_hint"] is None
    assert agent.state.plan_path is None

    saved = agent.tool_plan_save()
    assert saved["ok"] is True
    assert saved["plan_path"].startswith(".djx/session_plans/session_plan_")
    assert Path(saved["plan_path"]).exists()
    assert agent.state.plan_path == saved["plan_path"]
    assert agent.state.draft_plan_path_hint == saved["plan_path"]


def test_session_agent_plan_validate_accepts_plan_id_token(monkeypatch, tmp_path: Path):
    from data_juicer_agents.capabilities.session import orchestrator as session_mod
    from data_juicer_agents.capabilities.plan.schema import OperatorStep, PlanModel

    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello"}\n', encoding="utf-8")
    export = tmp_path / "out.jsonl"

    monkeypatch.setattr(
        session_mod.PlanUseCase,
        "build_plan",
        lambda self, **kwargs: PlanModel(  # noqa: ARG005
            plan_id="plan_token_validate",
            user_intent=kwargs["user_intent"],
            workflow="custom",
            dataset_path=kwargs["dataset_path"],
            export_path=kwargs["export_path"],
            modality="text",
            text_keys=["text"],
            operators=[OperatorStep(name="text_length_filter", params={"max_len": 1000})],
        ),
    )
    monkeypatch.setattr(session_mod.PlanValidator, "validate", staticmethod(lambda _plan: []))
    monkeypatch.setattr(
        session_mod.PlanValidator,
        "llm_review",
        staticmethod(lambda _plan: {"errors": [], "warnings": []}),
    )

    agent = DJSessionAgent(use_llm_router=False)
    generated = agent.tool_plan_generate(
        intent="filter long text",
        dataset_path=str(dataset),
        export_path=str(export),
    )
    assert generated["ok"] is True

    validated = agent.tool_plan_validate(
        plan_path="plan_token_validate",
        include_llm_review=False,
    )
    assert validated["ok"] is True
    assert validated["plan_source"] == "draft_by_plan_id"
    assert validated["warnings"]
    assert "plan_id token" in validated["warnings"][0]


def test_session_agent_plan_save_accepts_source_plan_id_token(monkeypatch, tmp_path: Path):
    from data_juicer_agents.capabilities.session import orchestrator as session_mod
    from data_juicer_agents.capabilities.plan.schema import OperatorStep, PlanModel

    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello"}\n', encoding="utf-8")
    export = tmp_path / "out.jsonl"
    output = tmp_path / "saved_from_token.yaml"

    monkeypatch.setattr(
        session_mod.PlanUseCase,
        "build_plan",
        lambda self, **kwargs: PlanModel(  # noqa: ARG005
            plan_id="plan_token_save",
            user_intent=kwargs["user_intent"],
            workflow="custom",
            dataset_path=kwargs["dataset_path"],
            export_path=kwargs["export_path"],
            modality="text",
            text_keys=["text"],
            operators=[OperatorStep(name="text_length_filter", params={"max_len": 1000})],
        ),
    )
    monkeypatch.setattr(session_mod.PlanValidator, "validate", staticmethod(lambda _plan: []))
    monkeypatch.setattr(
        session_mod.PlanValidator,
        "llm_review",
        staticmethod(lambda _plan: {"errors": [], "warnings": []}),
    )

    agent = DJSessionAgent(use_llm_router=False)
    generated = agent.tool_plan_generate(
        intent="filter long text",
        dataset_path=str(dataset),
        export_path=str(export),
    )
    assert generated["ok"] is True

    saved = agent.tool_plan_save(
        output_path=str(output),
        source_plan_path="plan_token_save",
    )
    assert saved["ok"] is True
    assert Path(saved["plan_path"]).exists()
    assert saved["warnings"]
    assert "plan_id token" in saved["warnings"][0]
