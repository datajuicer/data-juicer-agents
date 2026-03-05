# -*- coding: utf-8 -*-
"""Map DJSessionAgent events into transcript-style TUI state updates."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from typing import Dict
from typing import Iterable
from typing import Optional

from data_juicer_agents.tui.models import ToolCallState
from data_juicer_agents.tui.models import TuiState
from data_juicer_agents.tui.noise_filter import sanitize_reasoning_text


def _parse_ts(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except Exception:
        return None


def _format_preview(value: Any, max_chars: int = 180) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        try:
            text = json.dumps(value, ensure_ascii=False)
        except Exception:
            text = str(value)
    else:
        text = str(value)
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _tool_names(planned_tools: Any) -> str:
    if not isinstance(planned_tools, Iterable) or isinstance(planned_tools, (str, bytes, dict)):
        return ""
    names = []
    for item in planned_tools:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if name:
            names.append(name)
    return ", ".join(names)


def _build_tool_detail(call: ToolCallState) -> str:
    summary = str(call.summary or "").strip()
    args_preview = str(call.args_preview or "").strip()
    if call.tool in {"execute_shell_command", "execute_python_code"}:
        if args_preview and summary:
            return f"{args_preview} | {summary}"
        if args_preview:
            return args_preview
    return summary or args_preview


def _ensure_tool_call(
    state: TuiState,
    *,
    call_id: str,
    tool: str,
    started_at: Optional[datetime],
) -> ToolCallState:
    existing = state.tool_calls.get(call_id)
    if existing is not None:
        return existing

    call = ToolCallState(
        call_id=call_id,
        tool=tool,
        status="running",
        started_at=started_at,
    )
    state.upsert_tool_call(call)
    return call


def apply_event(state: TuiState, event: Dict[str, Any]) -> None:
    event_type = str(event.get("type", "")).strip()
    if not event_type:
        return

    ts = _parse_ts(event.get("timestamp"))

    if event_type == "tool_start":
        call_id = str(event.get("call_id", "")).strip() or f"tool_{len(state.tool_call_order) + 1}"
        tool = str(event.get("tool", "unknown_tool")).strip() or "unknown_tool"
        args_preview = _format_preview(event.get("args"))
        call = _ensure_tool_call(state, call_id=call_id, tool=tool, started_at=ts)
        call.status = "running"
        call.tool = tool
        call.started_at = call.started_at or ts
        call.args_preview = args_preview
        call.summary = ""
        call.error_type = None
        call.result_preview = ""
        state.status_line = f"Running {tool}"
        state.upsert_tool_call(call)
        return

    if event_type == "tool_end":
        call_id = str(event.get("call_id", "")).strip() or f"tool_{len(state.tool_call_order) + 1}"
        tool = str(event.get("tool", "unknown_tool")).strip() or "unknown_tool"
        call = _ensure_tool_call(state, call_id=call_id, tool=tool, started_at=ts)

        ok = bool(event.get("ok", True))
        call.status = "done" if ok else "failed"
        call.tool = tool
        call.ended_at = ts or datetime.utcnow()
        if call.started_at is not None and call.ended_at is not None:
            try:
                delta = (call.ended_at - call.started_at).total_seconds()
            except Exception:
                delta = 0.0
            call.elapsed_sec = max(delta, 0.0)

        call.error_type = str(event.get("error_type", "")).strip() or None
        call.summary = _format_preview(event.get("summary"))
        call.result_preview = _format_preview(event.get("result_preview"))
        if not call.summary:
            call.summary = call.result_preview
        if not call.summary and call.error_type:
            call.summary = call.error_type

        state.upsert_tool_call(call)

        elapsed = ""
        if call.elapsed_sec is not None:
            elapsed = f" ({call.elapsed_sec:.2f}s)"

        if ok:
            state.status_line = f"Finished {tool}"
            title = f"Finished {tool}{elapsed}"
        else:
            state.status_line = f"Failed {tool}"
            title = f"Failed {tool}{elapsed}"

        detail = _build_tool_detail(call)
        state.add_timeline(
            kind="tool",
            title=title,
            text=detail,
            status=call.status,
            tool=tool,
            timestamp=ts,
        )
        return

    if event_type == "reasoning_step":
        step = str(event.get("step", "")).strip()
        thinking = sanitize_reasoning_text(
            _format_preview(event.get("thinking"), max_chars=220)
        )
        planned_tools_raw = event.get("planned_tools")
        planned = _tool_names(planned_tools_raw)
        parts = []
        if step:
            parts.append(f"step {step}")
        if thinking:
            parts.append(thinking)
        if planned:
            parts.append(f"tools: {planned}")
        if parts:
            state.append_reasoning(" | ".join(parts))
            state.status_line = "Reasoning updated"
        return

    state.status_line = f"Event: {event_type}"
    state.add_timeline(
        kind="system",
        title="event",
        text=f"{event_type}",
        timestamp=ts,
    )
