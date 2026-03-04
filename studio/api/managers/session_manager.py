# -*- coding: utf-8 -*-
"""In-memory session manager for DJX frontend chat workflow."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List
from uuid import uuid4

from data_juicer_agents.capabilities.session.orchestrator import DJSessionAgent, SessionReply
from studio.api.agentscope_logging import install_thinking_warning_filter


def _utc_now() -> str:
    return datetime.utcnow().isoformat(timespec="milliseconds") + "Z"


@dataclass
class SessionRuntime:
    session_id: str
    profile_name: str
    created_at: str = field(default_factory=_utc_now)
    events: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._seq = 0
        self._lock = threading.RLock()
        self._message_cache: Dict[str, tuple[SessionReply, List[Dict[str, Any]]]] = {}
        self._message_cache_order: List[str] = []
        self._active_turn_running = False
        self.agent: DJSessionAgent | None = None

    def attach_agent(self, agent: DJSessionAgent) -> None:
        self.agent = agent

    def append_event(self, event_type: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
        data = payload or {}
        with self._lock:
            self._seq += 1
            event = {
                "seq": self._seq,
                "session_id": self.session_id,
                "type": event_type,
                "timestamp": _utc_now(),
                "payload": data,
            }
            self.events.append(event)
            if len(self.events) > 5000:
                self.events = self.events[-5000:]
            return event

    def on_agent_event(self, payload: Dict[str, Any]) -> None:
        self.append_event(str(payload.get("type", "agent_event")), payload)

    def get_events(self, after: int = 0, limit: int = 200) -> List[Dict[str, Any]]:
        with self._lock:
            rows = [item for item in self.events if int(item.get("seq", 0)) > int(after)]
            if limit > 0:
                return rows[:limit]
            return rows

    def latest_seq(self) -> int:
        with self._lock:
            return self._seq

    def _cache_message_response(
        self,
        client_message_id: str,
        payload: tuple[SessionReply, List[Dict[str, Any]]],
    ) -> None:
        with self._lock:
            self._message_cache[client_message_id] = payload
            self._message_cache_order.append(client_message_id)
            if len(self._message_cache_order) > 200:
                stale = self._message_cache_order.pop(0)
                self._message_cache.pop(stale, None)

    def send_message(
        self,
        message: str,
        client_message_id: str | None = None,
    ) -> tuple[SessionReply, List[Dict[str, Any]]]:
        if self.agent is None:
            raise RuntimeError("Session runtime is not initialized")

        msg_id = str(client_message_id or "").strip()
        if msg_id:
            with self._lock:
                cached = self._message_cache.get(msg_id)
            if cached is not None:
                return cached

        before_seq = self.latest_seq()
        self.append_event("user_message", {"text": message})
        with self._lock:
            self._active_turn_running = True

        try:
            reply = self.agent.handle_message(message)
        except Exception as exc:
            reply = SessionReply(
                text=(
                    "Unhandled session error, exiting session.\n"
                    f"error: {exc}"
                ),
                stop=True,
            )
            self.append_event(
                "session_error",
                {
                    "error": str(exc),
                },
            )
        finally:
            with self._lock:
                self._active_turn_running = False

        assistant_payload = {
            "text": reply.text,
            "stop": bool(reply.stop),
        }
        if bool(getattr(reply, "interrupted", False)):
            assistant_payload["interrupted"] = True
            self.append_event(
                "interrupt_ack",
                {
                    "session_id": self.session_id,
                    "message": "current turn interrupted",
                },
            )
        thinking_text = str(getattr(reply, "thinking", "") or "").strip()
        if thinking_text:
            assistant_payload["thinking"] = thinking_text
        self.append_event("assistant_message", assistant_payload)
        payload = (reply, self.get_events(after=before_seq))
        if msg_id:
            self._cache_message_response(msg_id, payload)
        return payload

    def request_interrupt(self) -> bool:
        with self._lock:
            turn_running = self._active_turn_running
            agent = self.agent
        if not turn_running:
            self.append_event(
                "interrupt_ignored",
                {
                    "session_id": self.session_id,
                    "reason": "no_pending_turn",
                },
            )
            return False

        accepted = True
        if agent is not None:
            try:
                accepted = bool(agent.request_interrupt())
            except Exception:
                accepted = False

        event_type = "interrupt_requested" if accepted else "interrupt_ignored"
        payload = {
            "session_id": self.session_id,
            "reason": "requested" if accepted else "not_accepted",
        }
        self.append_event(event_type, payload)
        return accepted

    def context_payload(self) -> Dict[str, Any]:
        if self.agent is None:
            return {}
        state = self.agent.state
        return {
            "dataset_path": state.dataset_path,
            "export_path": state.export_path,
            "plan_path": state.plan_path,
            "run_id": state.run_id,
            "custom_operator_paths": list(state.custom_operator_paths),
            "history_len": len(state.history),
        }


class SessionManager:
    """Manage frontend session runtimes keyed by session_id."""

    def __init__(self) -> None:
        self._sessions: Dict[str, SessionRuntime] = {}
        self._lock = threading.RLock()

    def start_session(
        self,
        profile_name: str,
        profile: Dict[str, Any],
        dataset_path: str | None = None,
        export_path: str | None = None,
        verbose: bool = False,
        session_id: str | None = None,
    ) -> SessionRuntime:
        install_thinking_warning_filter()

        sid = str(session_id or f"sess_{uuid4().hex[:12]}").strip()
        if not sid:
            raise ValueError("session_id cannot be empty")

        api_key = str(profile.get("dashscope_api_key", "") or "").strip()
        if not api_key:
            raise RuntimeError("Missing API key in selected profile")

        runtime = SessionRuntime(
            session_id=sid,
            profile_name=profile_name,
        )

        agent = DJSessionAgent(
            use_llm_router=True,
            dataset_path=str(dataset_path or "").strip() or None,
            export_path=str(export_path or "").strip() or None,
            verbose=bool(verbose),
            api_key=api_key,
            base_url=str(profile.get("base_url", "") or "").strip() or None,
            model_name=str(profile.get("session_model", "") or "").strip() or None,
            planner_model=str(profile.get("planner_model", "") or "").strip() or None,
            thinking=bool(profile.get("thinking", True)),
            event_callback=runtime.on_agent_event,
        )
        runtime.attach_agent(agent)
        runtime.append_event(
            "session_started",
            {
                "profile_name": profile_name,
                "dataset_path": runtime.agent.state.dataset_path,
                "export_path": runtime.agent.state.export_path,
            },
        )

        with self._lock:
            if sid in self._sessions:
                raise ValueError(f"Session already exists: {sid}")
            self._sessions[sid] = runtime
        return runtime

    def get_runtime(self, session_id: str) -> SessionRuntime:
        sid = str(session_id).strip()
        with self._lock:
            runtime = self._sessions.get(sid)
        if runtime is None:
            raise KeyError(f"Session not found: {sid}")
        return runtime

    def stop_session(self, session_id: str) -> bool:
        sid = str(session_id).strip()
        with self._lock:
            runtime = self._sessions.pop(sid, None)
        if runtime is None:
            return False
        runtime.append_event("session_stopped", {"session_id": sid})
        return True

    def interrupt_session(self, session_id: str) -> bool:
        runtime = self.get_runtime(session_id)
        return runtime.request_interrupt()

    def send_message(
        self,
        session_id: str,
        message: str,
        client_message_id: str | None = None,
    ) -> tuple[SessionReply, List[Dict[str, Any]]]:
        runtime = self.get_runtime(session_id)
        return runtime.send_message(message, client_message_id=client_message_id)

    def get_events(self, session_id: str, after: int = 0, limit: int = 200) -> tuple[List[Dict[str, Any]], int]:
        runtime = self.get_runtime(session_id)
        events = runtime.get_events(after=after, limit=limit)
        return events, runtime.latest_seq()

    def get_state(self, session_id: str) -> Dict[str, Any]:
        runtime = self.get_runtime(session_id)
        return {
            "session_id": runtime.session_id,
            "profile_name": runtime.profile_name,
            "created_at": runtime.created_at,
            "next_seq": runtime.latest_seq(),
            "context": runtime.context_payload(),
        }
