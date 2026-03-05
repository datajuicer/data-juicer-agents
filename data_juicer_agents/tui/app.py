# -*- coding: utf-8 -*-
"""Transcript-oriented terminal UI for dj-agents."""

from __future__ import annotations

import argparse
import contextlib
import os
import select
import sys
import time
from dataclasses import dataclass
from typing import List
from typing import Any
from typing import Dict

from rich.console import Console
from rich.text import Text

from data_juicer_agents.agentscope_logging import install_thinking_warning_filter
from data_juicer_agents.tui.controller import SessionController
from data_juicer_agents.tui.event_adapter import apply_event
from data_juicer_agents.tui.models import TimelineItem
from data_juicer_agents.tui.models import TuiState
from data_juicer_agents.tui.noise_filter import install_tui_warning_filters
from data_juicer_agents.tui.noise_filter import sanitize_reasoning_text

try:
    import termios
    import tty
except Exception:  # pragma: no cover - non-posix runtime
    termios = None
    tty = None


_INPUT_STYLE = "black on rgb(110,110,110)"
_USER_STYLE = "black on rgb(48,83,132)"
_AGENT_STYLE = "black on rgb(81,107,70)"


@contextlib.contextmanager
def _cbreak_stdin():
    if os.name != "posix" or termios is None or tty is None or not sys.stdin.isatty():
        yield False
        return
    fd = sys.stdin.fileno()
    attrs = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        yield True
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, attrs)


def _poll_esc(timeout_sec: float = 0.05) -> bool:
    if os.name != "posix" or termios is None or tty is None or not sys.stdin.isatty():
        return False
    ready, _, _ = select.select([sys.stdin], [], [], timeout_sec)
    if not ready:
        return False
    try:
        key = sys.stdin.read(1)
    except Exception:
        return False
    return key == "\x1b"


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
    info = Text()
    info.append("model: ", style="grey58")
    info.append(state.model_label)
    info.append("  cwd: ", style="grey58")
    info.append(state.cwd, style="cyan")
    info.append("  permissions: ", style="grey58")
    info.append(state.permissions_label, style="yellow")
    console.print(info, highlight=False)
    console.print(Text("Tip: ESC interrupt, /clear clear transcript, Ctrl+C exit", style="grey58"))
    console.print()


def _print_block(console: Console, label: str, text: str, style: str, *, markdown: bool = False) -> None:
    header = Text(f" {label} ", style=f"bold {style}")
    console.print(header, highlight=False)
    content = str(text or "")
    if markdown:
        lines = _markdown_to_plain_lines(content)
        for line in lines:
            console.print(Text(f" {line}", style=style), highlight=False)
    else:
        lines = content.splitlines() or [""]
        for line in lines:
            console.print(Text(f" {line}", style=style), highlight=False)
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

    console = Console()
    state = TuiState(
        status_line="ready",
        cwd=os.getcwd(),
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
        text="Describe your task in natural language.",
    )
    cursor = _flush_timeline(console, state, cursor=0)

    while True:
        try:
            message = console.input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("Session ended.")
            return 0

        if not message:
            continue

        if message == "/clear":
            state.timeline = []
            cursor = 0
            console.clear()
            _print_header(console, state)
            continue

        state.add_message("you", message, markdown=False)
        cursor = _flush_timeline(console, state, cursor)

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

        with _cbreak_stdin() as cbreak_enabled:
            while controller.is_turn_running():
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

                if cbreak_enabled and not interrupt_sent and _poll_esc(timeout_sec=0.02):
                    if controller.request_interrupt():
                        interrupt_sent = True
                        spinner.clear()
                        state.add_timeline(
                            kind="system",
                            title="interrupt",
                            text="Interrupt requested.",
                        )
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
                    "本轮出现工具计划但未看到实际工具执行结果。"
                    "可重试或使用 --verbose 查看更详细的内部日志。"
                ),
            )
        cursor = _flush_timeline(console, state, cursor)

        if bool(getattr(reply, "stop", False)):
            return 0
