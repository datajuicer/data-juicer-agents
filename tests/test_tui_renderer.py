# -*- coding: utf-8 -*-

from data_juicer_agents.tui.app import _format_tool_prefix
from data_juicer_agents.tui.app import _RunningToolState
from data_juicer_agents.tui.app import _running_tool_status_text
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
            tool="plan_generate",
            started_monotonic=10.0,
        )
    }
    text = _running_tool_status_text(running, now_monotonic=21.0)
    assert "running plan_generate" in text
    assert "(+11s)" in text
