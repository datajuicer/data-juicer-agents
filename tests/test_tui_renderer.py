# -*- coding: utf-8 -*-

# -*- coding: utf-8 -*-

from pathlib import Path

from rich.console import Console

from data_juicer_agents.tui.app import _print_header
from data_juicer_agents.tui.app import _format_tool_prefix
from data_juicer_agents.tui.app import _RunningToolState
from data_juicer_agents.tui.app import _running_tool_status_text
from data_juicer_agents.tui.app import _usage_hint_text
from data_juicer_agents.tui.models import TimelineItem
from data_juicer_agents.tui.models import TuiState


def test_tool_prefix_includes_status_and_title():
    item = TimelineItem(kind="tool", title="Run inspect_dataset", status="running")
    text = _format_tool_prefix(item)
    assert "running" in text.plain
    assert "Run inspect_dataset" in text.plain


def test_add_message_appends_timeline_item():
    state = TuiState()
    state.add_message("agent", "hello", markdown=True)
    assert len(state.timeline) == 1
    assert state.timeline[0].kind == "assistant"
    assert state.timeline[0].markdown is True


def test_add_message_you_appends_single_user_timeline_item():
    state = TuiState()
    state.add_message("you", "hello", markdown=False)
    assert len(state.timeline) == 1
    assert state.timeline[0].kind == "user"
    assert state.timeline[0].text == "hello"


def test_running_tool_status_text_shows_elapsed():
    running = {
        "tool_1": _RunningToolState(
            tool="plan_build",
            started_monotonic=10.0,
        )
    }
    text = _running_tool_status_text(running, now_monotonic=21.0)
    assert "running plan_build" in text
    assert "(+11s)" in text


def test_print_header_includes_runtime_context():
    console = Console(record=True, width=120)
    workdir = str((Path("/tmp/project") / ".djx").resolve())
    state = TuiState(
        model_label="qwen3-max-2026-01-23",
        planner_model_label="qwen3-max-2026-01-23",
        llm_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        cwd="/tmp/project",
        session_workdir=workdir,
    )
    _print_header(console, state)
    output = console.export_text()
    assert "session model:" in output
    assert "planner model:" in output
    assert "cwd:" in output
    assert "/tmp/project" in output
    assert "session workdir:" in output
    assert workdir in output
    assert "base url:" in output
    assert "Tip: Ctrl+C interrupt current turn" in output


def test_usage_hint_text_is_bilingual_and_includes_examples():
    hint = _usage_hint_text()
    assert "Describe your task in natural language." in hint
    assert "Examples / 示例:" in hint
    assert "多模态去重" in hint
    assert "1500" in hint
    assert hint.endswith("适用场景。\n")
