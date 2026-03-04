# -*- coding: utf-8 -*-
"""Session-related request/response models."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .common import SessionEventItem


class SessionStartRequest(BaseModel):
    profile_name: str = "default"
    dataset_path: str | None = None
    export_path: str | None = None
    verbose: bool = False
    session_id: str | None = None


class SessionStartResponse(BaseModel):
    ok: bool = True
    session_id: str
    profile_name: str
    created_at: str
    context: dict = Field(default_factory=dict)
    events: list[SessionEventItem] = Field(default_factory=list)


class SessionMessageRequest(BaseModel):
    session_id: str
    message: str
    client_message_id: str | None = None


class SessionMessageResponse(BaseModel):
    ok: bool = True
    session_id: str
    reply_text: str
    stop: bool = False
    interrupted: bool = False
    context: dict = Field(default_factory=dict)
    events: list[SessionEventItem] = Field(default_factory=list)
    next_seq: int = 0


class SessionEventsResponse(BaseModel):
    ok: bool = True
    session_id: str
    events: list[SessionEventItem] = Field(default_factory=list)
    next_seq: int = 0


class SessionStopRequest(BaseModel):
    session_id: str


class SessionStopResponse(BaseModel):
    ok: bool
    session_id: str
    stopped: bool


class SessionInterruptRequest(BaseModel):
    session_id: str


class SessionInterruptResponse(BaseModel):
    ok: bool
    session_id: str
    accepted: bool


class SessionStateResponse(BaseModel):
    ok: bool = True
    session_id: str
    profile_name: str
    created_at: str
    context: dict = Field(default_factory=dict)
    next_seq: int = 0


__all__ = [
    "SessionStartRequest",
    "SessionStartResponse",
    "SessionMessageRequest",
    "SessionMessageResponse",
    "SessionEventsResponse",
    "SessionStopRequest",
    "SessionStopResponse",
    "SessionInterruptRequest",
    "SessionInterruptResponse",
    "SessionStateResponse",
]
