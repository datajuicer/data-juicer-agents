# -*- coding: utf-8 -*-
"""Session orchestration helpers for API routes."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from data_juicer_agents.capabilities.session.orchestrator import SessionReply
from studio.api.managers.session_manager import SessionManager, SessionRuntime
from studio.api.models.session import SessionMessageRequest, SessionStartRequest
from studio.api.repositories.settings_repository import SettingsStore


def start_session(
    request: SessionStartRequest,
    *,
    store: SettingsStore,
    manager: SessionManager,
) -> SessionRuntime:
    profile_name, profile = store.get_profile(request.profile_name)
    return manager.start_session(
        profile_name=profile_name,
        profile=profile,
        dataset_path=request.dataset_path,
        export_path=request.export_path,
        verbose=request.verbose,
        session_id=request.session_id,
    )


def send_session_message(
    request: SessionMessageRequest,
    *,
    manager: SessionManager,
) -> tuple[SessionRuntime, SessionReply, List[Dict[str, Any]]]:
    runtime = manager.get_runtime(request.session_id)
    reply, events = runtime.send_message(
        request.message,
        client_message_id=request.client_message_id,
    )
    return runtime, reply, events


def list_session_events(
    *,
    manager: SessionManager,
    session_id: str,
    after: int,
    limit: int,
) -> tuple[List[Dict[str, Any]], int]:
    return manager.get_events(session_id=session_id, after=after, limit=limit)


def get_session_state(*, manager: SessionManager, session_id: str) -> Dict[str, Any]:
    return manager.get_state(session_id=session_id)


def stop_session(*, manager: SessionManager, session_id: str) -> bool:
    return manager.stop_session(session_id)


def interrupt_session(*, manager: SessionManager, session_id: str) -> bool:
    return manager.interrupt_session(session_id)


__all__ = [
    "start_session",
    "send_session_message",
    "list_session_events",
    "get_session_state",
    "stop_session",
    "interrupt_session",
]
