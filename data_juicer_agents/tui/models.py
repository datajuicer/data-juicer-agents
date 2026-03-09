# -*- coding: utf-8 -*-
"""State models for the dj-agents terminal transcript UI."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from typing import Dict
from typing import List
from typing import Optional


@dataclass
class ChatMessage:
    role: str
    text: str
    markdown: bool = False
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ToolCallState:
    call_id: str
    tool: str
    status: str
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    elapsed_sec: Optional[float] = None
    args_preview: str = ""
    summary: str = ""
    error_type: Optional[str] = None
    result_preview: str = ""


@dataclass
class TimelineItem:
    kind: str
    title: str
    text: str = ""
    markdown: bool = False
    status: Optional[str] = None
    tool: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class TuiState:
    messages: List[ChatMessage] = field(default_factory=list)
    tool_calls: Dict[str, ToolCallState] = field(default_factory=dict)
    tool_call_order: List[str] = field(default_factory=list)
    reasoning_notes: List[str] = field(default_factory=list)
    timeline: List[TimelineItem] = field(default_factory=list)
    status_line: str = "Ready."
    model_label: str = "session-agent"
    planner_model_label: str = "planner"
    llm_base_url: str = ""
    permissions_label: str = "Workspace"
    cwd: str = "~"
    session_workdir: str = "./.djx"

    def add_timeline(
        self,
        *,
        kind: str,
        title: str,
        text: str = "",
        markdown: bool = False,
        status: Optional[str] = None,
        tool: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        limit: int = 300,
    ) -> None:
        if not str(title or "").strip() and not str(text or "").strip():
            return
        item = TimelineItem(
            kind=str(kind or "event").strip() or "event",
            title=str(title or "").strip(),
            text=str(text or "").strip(),
            markdown=bool(markdown),
            status=str(status or "").strip() or None,
            tool=str(tool or "").strip() or None,
            timestamp=timestamp or datetime.utcnow(),
        )
        self.timeline.append(item)
        if limit > 0 and len(self.timeline) > limit:
            self.timeline = self.timeline[-limit:]

    def add_message(self, role: str, text: str, markdown: bool = False) -> None:
        content = str(text or "").strip()
        if not content:
            return
        role_text = str(role or "").strip() or "assistant"
        self.messages.append(ChatMessage(role=role_text, text=content, markdown=markdown))
        self.add_timeline(
            kind="user" if role_text.lower() == "you" else "assistant",
            title=role_text,
            text=content,
            markdown=markdown,
        )

    def upsert_tool_call(self, call_state: ToolCallState) -> None:
        if call_state.call_id not in self.tool_calls:
            self.tool_call_order.append(call_state.call_id)
        self.tool_calls[call_state.call_id] = call_state

    def recent_messages(self, limit: int = 12) -> List[ChatMessage]:
        if limit <= 0:
            return []
        return self.messages[-limit:]

    def recent_tool_calls(self, limit: int = 12) -> List[ToolCallState]:
        if limit <= 0:
            return []
        keys = self.tool_call_order[-limit:]
        return [self.tool_calls[k] for k in keys if k in self.tool_calls]

    def recent_timeline(self, limit: int = 40) -> List[TimelineItem]:
        if limit <= 0:
            return []
        return self.timeline[-limit:]

    def append_reasoning(self, note: str, *, limit: int = 20) -> None:
        text = str(note or "").strip()
        if not text:
            return
        self.reasoning_notes.append(text)
        if limit > 0 and len(self.reasoning_notes) > limit:
            self.reasoning_notes = self.reasoning_notes[-limit:]
        self.add_timeline(kind="reasoning", title="reasoning", text=text)
