# -*- coding: utf-8 -*-
"""Session routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from studio.api.deps import get_session_manager, get_store
from studio.api.managers.session_manager import SessionManager
from studio.api.models.session import (
    SessionInterruptRequest,
    SessionInterruptResponse,
    SessionEventsResponse,
    SessionMessageRequest,
    SessionMessageResponse,
    SessionStartRequest,
    SessionStartResponse,
    SessionStateResponse,
    SessionStopRequest,
    SessionStopResponse,
)
from studio.api.repositories.settings_repository import SettingsStore
from studio.api.services.session_service import (
    get_session_state,
    interrupt_session,
    list_session_events,
    send_session_message,
    start_session,
    stop_session,
)

router = APIRouter(tags=["session"])


@router.post("/api/session/start", response_model=SessionStartResponse)
def route_start_session(
    request: SessionStartRequest,
    store: SettingsStore = Depends(get_store),
    manager: SessionManager = Depends(get_session_manager),
) -> SessionStartResponse:
    try:
        runtime = start_session(request, store=store, manager=manager)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to start session: {exc}") from exc

    return SessionStartResponse(
        ok=True,
        session_id=runtime.session_id,
        profile_name=runtime.profile_name,
        created_at=runtime.created_at,
        context=runtime.context_payload(),
        events=runtime.get_events(after=0, limit=200),
    )


@router.post("/api/session/message", response_model=SessionMessageResponse)
def route_send_session_message(
    request: SessionMessageRequest,
    manager: SessionManager = Depends(get_session_manager),
) -> SessionMessageResponse:
    try:
        runtime, reply, events = send_session_message(request, manager=manager)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return SessionMessageResponse(
        ok=True,
        session_id=runtime.session_id,
        reply_text=reply.text,
        stop=bool(reply.stop),
        interrupted=bool(getattr(reply, "interrupted", False)),
        context=runtime.context_payload(),
        events=events,
        next_seq=runtime.latest_seq(),
    )


@router.get("/api/session/events", response_model=SessionEventsResponse)
def route_list_session_events(
    session_id: str = Query(..., min_length=1),
    after: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    manager: SessionManager = Depends(get_session_manager),
) -> SessionEventsResponse:
    try:
        events, next_seq = list_session_events(
            manager=manager,
            session_id=session_id,
            after=after,
            limit=limit,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return SessionEventsResponse(
        ok=True,
        session_id=session_id,
        events=events,
        next_seq=next_seq,
    )


@router.get("/api/session/state", response_model=SessionStateResponse)
def route_get_session_state(
    session_id: str = Query(..., min_length=1),
    manager: SessionManager = Depends(get_session_manager),
) -> SessionStateResponse:
    try:
        payload = get_session_state(manager=manager, session_id=session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return SessionStateResponse(
        ok=True,
        session_id=str(payload.get("session_id", "")),
        profile_name=str(payload.get("profile_name", "")),
        created_at=str(payload.get("created_at", "")),
        context=payload.get("context", {}),
        next_seq=int(payload.get("next_seq", 0)),
    )


@router.post("/api/session/stop", response_model=SessionStopResponse)
def route_stop_session(
    request: SessionStopRequest,
    manager: SessionManager = Depends(get_session_manager),
) -> SessionStopResponse:
    stopped = stop_session(manager=manager, session_id=request.session_id)
    return SessionStopResponse(
        ok=True,
        session_id=request.session_id,
        stopped=stopped,
    )


@router.post("/api/session/interrupt", response_model=SessionInterruptResponse)
def route_interrupt_session(
    request: SessionInterruptRequest,
    manager: SessionManager = Depends(get_session_manager),
) -> SessionInterruptResponse:
    try:
        accepted = interrupt_session(manager=manager, session_id=request.session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SessionInterruptResponse(
        ok=True,
        session_id=request.session_id,
        accepted=bool(accepted),
    )


__all__ = ["router"]
