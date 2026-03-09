# -*- coding: utf-8 -*-
"""Transcript-oriented terminal UI for dj-agents."""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List
from typing import Any
from typing import Dict

from rich.console import Console
from rich.text import Text

from data_juicer_agents.utils.agentscope_logging import install_thinking_warning_filter
from data_juicer_agents.utils.terminal_input import TerminalLineReader
from data_juicer_agents.tui.controller import SessionController
from data_juicer_agents.tui.event_adapter import apply_event
from data_juicer_agents.tui.models import TimelineItem
from data_juicer_agents.tui.models import TuiState
from data_juicer_agents.tui.noise_filter import install_tui_warning_filters
from data_juicer_agents.tui.noise_filter import sanitize_reasoning_text


_INPUT_STYLE = "bright_white"
_USER_STYLE = "bright_cyan"
_AGENT_STYLE = "bright_cyan"
_INPUT_PROMPT = "\n> "


@dataclass
class _ThinkingSpinner:
    stream: Any
    text: str = "thinking..."
    interval_sec: float = 0.35

    def __post_init__(self) -> None:
        self._frames: List[str] = ["|", "/", "-", "\\"]
        self._idx = 0
        self._last_tick = 0.0
        self._visible = False
        self._last_line_len = 0

    def tick(self) -> None:
        now = time.monotonic()
        if now - self._last_tick < self.interval_sec:
            return
        self._last_tick = now
        frame = self._frames[self._idx % len(self._frames)]
        self._idx += 1
        body = f"{frame} {self.text}"
        pad = max(self._last_line_len - len(body), 0)
        line = f"\r{body}{' ' * pad}"
        self.stream.write(line)
        self.stream.flush()
        self._visible = True
        self._last_line_len = len(body)

    def clear(self) -> None:
        if not self._visible:
            return
        self.stream.write("\r" + (" " * self._last_line_len) + "\r")
        self.stream.flush()
        self._visible = False
        self._last_line_len = 0


@dataclass
class _RunningToolState:
    tool: str
    started_monotonic: float


def _print_header(console: Console, state: TuiState) -> None:
    console.print(Text("dj-agents", style="bold"), highlight=False)
    line1 = Text()
    line1.append("session model: ", style="grey58")
    line1.append(state.model_label, style="bold")
    line1.append("  planner model: ", style="grey58")
    line1.append(state.planner_model_label, style="bold")
    console.print(line1, highlight=False)
    line2 = Text()
    line2.append("cwd: ", style="grey58")
    line2.append(state.cwd, style="cyan")
    line2.append("  session workdir: ", style="grey58")
    line2.append(state.session_workdir, style="cyan")
    console.print(line2, highlight=False)
    line3 = Text()
    line3.append("base url: ", style="grey58")
    line3.append(state.llm_base_url or "-", style="magenta")
    line3.append("  permissions: ", style="grey58")
    line3.append(state.permissions_label, style="yellow")
    console.print(line3, highlight=False)
    console.print(
        Text(
            "Tip: Ctrl+C interrupt current turn, Ctrl+D exit, /clear clear transcript",
            style="grey58",
        )
    )
    console.print()


def _new_line_reader() -> TerminalLineReader:
    return TerminalLineReader()


def _usage_hint_text() -> str:
    return (
        "Describe your task in natural language.\n"
        "Examples / 示例:\n"
        "1. Remove texts longer than 1500 characters from ./data/demo-dataset.jsonl, "
        "generate a plan, and execute it. / 我要去除 ./data/demo-dataset.jsonl 中长度大于 1500 的文本，帮我生成方案并执行。\n"
        "2. Retrieve operators for multimodal deduplication and explain when to use them. / "
        "帮我检索多模态去重相关算子，并说明适用场景。\n"
    )


def _print_block(console: Console, label: str, text: str, style: str, *, markdown: bool = False) -> None:
    header = Text(f" {label} ", style=f"bold {style}")
    console.print(header, highlight=False)
    content = str(text or "")
    if markdown:
        lines = _markdown_to_plain_lines(content)
        for line in lines:
            console.print(Text(f" {line}", style=f"bold {style}"), highlight=False)
    else:
        lines = content.splitlines() or [""]
        for line in lines:
            console.print(Text(f" {line}", style=f"bold {style}"), highlight=False)
    console.print()


def _markdown_to_plain_lines(content: str) -> List[str]:
    lines: List[str] = []
    in_code = False
    for raw in str(content or "").splitlines():
        stripped = raw.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            lines.append(raw)
            continue
        if stripped.startswith("#"):
            text = stripped.lstrip("#").strip()
            lines.append(text)
            continue
        lines.append(raw)
    if not lines:
        return [""]
    return lines


def _format_tool_prefix(item: TimelineItem) -> Text:
    status = str(item.status or "").strip().lower()
    if status == "running":
        marker = "●"
        color = "yellow"
        label = "running"
    elif status == "done":
        marker = "●"
        color = "green"
        label = "done"
    elif status == "failed":
        marker = "●"
        color = "red"
        label = "failed"
    else:
        marker = "●"
        color = "grey50"
        label = status or "event"

    line = Text()
    line.append(f"{marker} ", style=color)
    line.append(f"{label:<7}", style=f"bold {color}")
    line.append(" ")
    line.append(item.title)
    return line


def _print_tool_item(console: Console, item: TimelineItem) -> None:
    console.print(_format_tool_prefix(item), highlight=False)
    if item.text:
        console.print(Text(f"  {item.text}", style="grey62"), highlight=False)


def _print_timeline_item(console: Console, item: TimelineItem) -> None:
    if item.kind == "input":
        _print_block(console, "input", item.text, _INPUT_STYLE, markdown=False)
        return
    if item.kind == "user":
        _print_block(console, "you", item.text, _USER_STYLE, markdown=False)
        return
    if item.kind == "assistant":
        _print_block(console, "agent", item.text, _AGENT_STYLE, markdown=item.markdown)
        return
    if item.kind == "tool":
        _print_tool_item(console, item)
        return
    if item.kind == "reasoning":
        console.print(Text(f"· {item.text}", style="grey58"), highlight=False)
        return
    if item.kind == "system":
        console.print(Text(f"△ {item.text or item.title}", style="yellow"), highlight=False)
        return
    console.print(Text(f"- {item.text or item.title}", style="grey58"), highlight=False)


def _flush_timeline(console: Console, state: TuiState, cursor: int) -> int:
    items = state.timeline
    if cursor < 0:
        cursor = 0
    if cursor >= len(items):
        return cursor
    for item in items[cursor:]:
        _print_timeline_item(console, item)
    return len(items)


def _track_tool_event(
    event: Dict[str, Any],
    running_tools: Dict[str, _RunningToolState],
    now_monotonic: float,
) -> None:
    event_type = str(event.get("type", "")).strip()
    if event_type == "tool_start":
        call_id = str(event.get("call_id", "")).strip()
        tool = str(event.get("tool", "")).strip() or "unknown_tool"
        if call_id:
            running_tools[call_id] = _RunningToolState(
                tool=tool,
                started_monotonic=now_monotonic,
            )
        return
    if event_type == "tool_end":
        call_id = str(event.get("call_id", "")).strip()
        if call_id:
            running_tools.pop(call_id, None)


def _running_tool_status_text(
    running_tools: Dict[str, _RunningToolState],
    now_monotonic: float,
) -> str:
    if not running_tools:
        return ""
    active = sorted(running_tools.values(), key=lambda row: row.started_monotonic)
    primary = active[0]
    elapsed = max(now_monotonic - primary.started_monotonic, 0.0)
    extra = len(active) - 1
    if extra > 0:
        return f"running {primary.tool} (+{elapsed:.0f}s), +{extra} more"
    return f"running {primary.tool} (+{elapsed:.0f}s)"


def run_tui_session(args: argparse.Namespace) -> int:
    install_thinking_warning_filter()
    install_tui_warning_filters()

    session_model = os.environ.get("DJA_SESSION_MODEL", "qwen3-max-2026-01-23")
    planner_model = os.environ.get("DJA_PLANNER_MODEL", "qwen3-max-2026-01-23")
    base_url = os.environ.get(
        "DJA_OPENAI_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

    console = Console()
    line_reader = _new_line_reader()
    state = TuiState(
        status_line="ready",
        model_label=session_model,
        planner_model_label=planner_model,
        llm_base_url=base_url,
        cwd=os.getcwd(),
        session_workdir=str((Path.cwd() / ".djx").resolve()),
    )
    controller = SessionController(
        dataset_path=args.dataset,
        export_path=args.export,
        verbose=bool(args.verbose),
    )

    try:
        controller.start()
    except Exception as exc:
        console.print(f"Failed to start dj-agents session: {exc}", style="bold red")
        return 2

    _print_header(console, state)
    state.add_timeline(
        kind="system",
        title="tip",
        text=_usage_hint_text(),
    )
    cursor = _flush_timeline(console, state, cursor=0)

    while True:
        try:
            message = line_reader.read_line(_INPUT_PROMPT).strip()
        except EOFError:
            console.print("Session ended.")
            return 0
        except KeyboardInterrupt:
            state.add_timeline(
                kind="system",
                title="interrupt",
                text="No running task to interrupt. Press Ctrl+D to exit.",
            )
            cursor = _flush_timeline(console, state, cursor)
            continue

        if not message:
            continue

        if message == "/clear":
            state.timeline = []
            cursor = 0
            console.clear()
            _print_header(console, state)
            continue

        try:
            controller.submit_turn(message)
        except Exception as exc:
            console.print(f"Failed to submit turn: {exc}", style="red")
            continue

        spinner = _ThinkingSpinner(stream=sys.stdout, text="agent thinking")
        interrupt_sent = False
        turn_tool_event_count = 0
        turn_planned_tool_count = 0
        turn_reasoning_event_count = 0
        running_tools: Dict[str, _RunningToolState] = {}
        saw_any_turn_event = False

        while controller.is_turn_running():
            try:
                events = controller.drain_events()
                if events:
                    spinner.clear()
                    saw_any_turn_event = True
                    for event in events:
                        now = time.monotonic()
                        _track_tool_event(event, running_tools, now)
                        event_type = str(event.get("type", "")).strip()
                        if event_type in {"tool_start", "tool_end"}:
                            turn_tool_event_count += 1
                        if event_type == "reasoning_step":
                            turn_reasoning_event_count += 1
                            planned_tools = event.get("planned_tools")
                            if isinstance(planned_tools, list):
                                turn_planned_tool_count += len(
                                    [row for row in planned_tools if isinstance(row, dict)]
                                )
                        apply_event(state, event)
                    cursor = _flush_timeline(console, state, cursor)

                now = time.monotonic()
                status_text = _running_tool_status_text(running_tools, now)
                if status_text:
                    spinner.text = status_text
                    spinner.tick()
                elif not saw_any_turn_event:
                    spinner.text = "agent thinking"
                    spinner.tick()
                else:
                    spinner.clear()
                time.sleep(0.03)
            except KeyboardInterrupt:
                if not interrupt_sent and controller.request_interrupt():
                    interrupt_sent = True
                    spinner.clear()
                    state.add_timeline(
                        kind="system",
                        title="interrupt",
                        text="Interrupt requested (Ctrl+C).",
                    )
                    cursor = _flush_timeline(console, state, cursor)
                else:
                    spinner.clear()
                    state.add_timeline(
                        kind="system",
                        title="interrupt",
                        text="Interrupt ignored.",
                    )
                    cursor = _flush_timeline(console, state, cursor)

        spinner.clear()

        for event in controller.drain_events():
            now = time.monotonic()
            _track_tool_event(event, running_tools, now)
            event_type = str(event.get("type", "")).strip()
            if event_type in {"tool_start", "tool_end"}:
                turn_tool_event_count += 1
            if event_type == "reasoning_step":
                turn_reasoning_event_count += 1
                planned_tools = event.get("planned_tools")
                if isinstance(planned_tools, list):
                    turn_planned_tool_count += len([row for row in planned_tools if isinstance(row, dict)])
            apply_event(state, event)
        cursor = _flush_timeline(console, state, cursor)

        reply = controller.consume_turn_result()
        state.add_message("agent", reply.text, markdown=True)
        thinking = sanitize_reasoning_text(str(getattr(reply, "thinking", "") or ""))
        if thinking and turn_reasoning_event_count == 0:
            state.append_reasoning(thinking)
        if turn_tool_event_count == 0 and turn_planned_tool_count > 0:
            state.add_timeline(
                kind="system",
                title="tool_hint",
                text=(
                    "A tool was planned in this turn, but no actual execution result was observed. "
                    "Retry or use --verbose to inspect more detailed internal logs."
                ),
            )
        cursor = _flush_timeline(console, state, cursor)

        if bool(getattr(reply, "stop", False)):
            return 0
