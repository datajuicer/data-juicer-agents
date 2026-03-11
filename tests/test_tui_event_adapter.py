# -*- coding: utf-8 -*-

from data_juicer_agents.tui.event_adapter import apply_event
from data_juicer_agents.tui.models import TuiState


def test_apply_event_updates_tool_running_and_done_status():
    state = TuiState()

    apply_event(
        state,
        {
            "type": "tool_start",
            "timestamp": "2026-03-03T10:00:00.000Z",
            "tool": "plan_build",
            "call_id": "tool_1",
            "args": {"intent": "clean rag dataset"},
        },
    )

    call = state.tool_calls["tool_1"]
    assert call.status == "running"
    assert call.tool == "plan_build"
    assert "intent" in call.args_preview
    assert not state.timeline
    assert state.status_line == "Running plan_build"

    apply_event(
        state,
        {
            "type": "tool_end",
            "timestamp": "2026-03-03T10:00:01.100Z",
            "tool": "plan_build",
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
    assert "Finished plan_build" in state.timeline[-1].title


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
