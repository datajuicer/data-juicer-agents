# -*- coding: utf-8 -*-

from data_juicer_agents.capabilities.session.runtime import SessionState, SessionToolRuntime
from data_juicer_agents.tui.event_adapter import apply_event
from data_juicer_agents.tui.models import TuiState


def test_apply_event_updates_tool_running_and_done_status():
    state = TuiState()

    apply_event(
        state,
        {
            "type": "tool_start",
            "timestamp": "2026-03-03T10:00:00.000Z",
            "tool": "assemble_plan",
            "call_id": "tool_1",
            "args": {"intent": "clean rag dataset"},
        },
    )

    call = state.tool_calls["tool_1"]
    assert call.status == "running"
    assert call.tool == "assemble_plan"
    assert "intent" in call.args_preview
    assert not state.timeline
    assert state.status_line == "Running assemble_plan"

    apply_event(
        state,
        {
            "type": "tool_end",
            "timestamp": "2026-03-03T10:00:01.100Z",
            "tool": "assemble_plan",
            "call_id": "tool_1",
            "ok": True,
            "summary": "plan built",
        },
    )

    call = state.tool_calls["tool_1"]
    assert call.status == "done"
    assert call.elapsed_sec is not None
    assert call.elapsed_sec >= 1.0
    assert "plan built" in call.summary
    assert state.timeline[-1].status == "done"
    assert "Finished assemble_plan" in state.timeline[-1].title


def test_apply_event_marks_failed_tool_and_sets_error_summary():
    state = TuiState()

    apply_event(
        state,
        {
            "type": "tool_end",
            "timestamp": "2026-03-03T10:00:02.000Z",
            "tool": "apply_recipe",
            "call_id": "tool_2",
            "ok": False,
            "error_type": "execution_failed",
            "summary": "command timed out",
        },
    )

    call = state.tool_calls["tool_2"]
    assert call.status == "failed"
    assert call.error_type == "execution_failed"
    assert "timed out" in call.summary
    assert state.timeline[-1].status == "failed"


def test_apply_event_prefers_failure_preview_for_failed_tool_detail():
    state = TuiState()

    apply_event(
        state,
        {
            "type": "tool_end",
            "timestamp": "2026-03-03T10:00:02.000Z",
            "tool": "apply_recipe",
            "call_id": "tool_2",
            "ok": False,
            "error_type": "plan_invalid",
            "summary": "apply failed",
            "failure_preview": "plan validation failed before apply | dataset_path does not exist: ./missing.jsonl",
        },
    )

    call = state.tool_calls["tool_2"]
    assert call.status == "failed"
    assert "dataset_path does not exist" in call.failure_preview
    assert call.summary == call.failure_preview
    assert "dataset_path does not exist" in state.timeline[-1].text


def test_runtime_tool_end_failure_preview_flows_into_tui_state():
    captured = []
    runtime = SessionToolRuntime(state=SessionState(), event_callback=captured.append)
    state = TuiState()

    runtime.invoke_tool(
        "apply_recipe",
        {"plan_path": "/tmp/missing.yaml"},
        lambda: {
            "ok": False,
            "error_type": "plan_invalid",
            "message": "apply failed",
            "validation_errors": ["dataset_path does not exist: /tmp/missing.jsonl"],
        },
    )

    for event in captured:
        apply_event(state, event)

    call = state.recent_tool_calls(limit=1)[0]
    assert call.status == "failed"
    assert "dataset_path does not exist" in call.failure_preview
    assert "dataset_path does not exist" in state.timeline[-1].text


def test_apply_event_shell_tool_detail_includes_command_and_summary():
    state = TuiState()
    apply_event(
        state,
        {
            "type": "tool_start",
            "timestamp": "2026-03-03T10:10:00.000Z",
            "tool": "execute_shell_command",
            "call_id": "tool_shell_1",
            "args": {"command": "echo hello_djx", "timeout": 5},
        },
    )
    apply_event(
        state,
        {
            "type": "tool_end",
            "timestamp": "2026-03-03T10:10:00.300Z",
            "tool": "execute_shell_command",
            "call_id": "tool_shell_1",
            "ok": True,
            "summary": "process finished with returncode=0",
        },
    )

    detail = state.timeline[-1].text
    assert "echo hello_djx" in detail
    assert "returncode=0" in detail


def test_apply_event_python_tool_detail_includes_code_and_summary():
    state = TuiState()
    apply_event(
        state,
        {
            "type": "tool_start",
            "timestamp": "2026-03-03T10:10:02.000Z",
            "tool": "execute_python_code",
            "call_id": "tool_py_1",
            "args": {"code": "print('py_ok')", "timeout": 5},
        },
    )
    apply_event(
        state,
        {
            "type": "tool_end",
            "timestamp": "2026-03-03T10:10:02.400Z",
            "tool": "execute_python_code",
            "call_id": "tool_py_1",
            "ok": True,
            "summary": "process finished with returncode=0",
        },
    )

    detail = state.timeline[-1].text
    assert "print('py_ok')" in detail
    assert "returncode=0" in detail


def test_apply_event_adds_reasoning_note_with_planned_tools():
    state = TuiState()

    apply_event(
        state,
        {
            "type": "reasoning_step",
            "step": 3,
            "thinking": "compare schema and choose candidate operators",
            "planned_tools": [
                {"name": "inspect_dataset"},
                {"name": "retrieve_operators"},
            ],
        },
    )

    assert len(state.reasoning_notes) == 1
    note = state.reasoning_notes[0]
    assert "step 3" in note
    assert "inspect_dataset" in note
    assert "retrieve_operators" in note
    tool_items = [item for item in state.timeline if item.kind == "tool" and item.status == "planned"]
    assert not tool_items
    assert state.timeline[-1].kind == "reasoning"
