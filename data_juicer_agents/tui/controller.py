# -*- coding: utf-8 -*-
"""Controller for running DJSessionAgent with asynchronous TUI updates."""

from __future__ import annotations

import queue
import threading
from typing import Any, Dict, List, Optional

from data_juicer_agents.capabilities.session.orchestrator import DJSessionAgent
from data_juicer_agents.capabilities.session.orchestrator import SessionReply
from data_juicer_agents.tui.noise_filter import suppress_tui_noise_stderr


class SessionController:
    def __init__(
        self,
        *,
        dataset_path: Optional[str],
        export_path: Optional[str],
        verbose: bool,
    ) -> None:
        self._dataset_path = dataset_path
        self._export_path = export_path
        self._verbose = bool(verbose)

        self._event_queue: queue.Queue[Dict[str, Any]] = queue.Queue()
        self._agent: Optional[DJSessionAgent] = None

        self._lock = threading.RLock()
        self._turn_running = False
        self._turn_reply: Optional[SessionReply] = None
        self._turn_error: Optional[Exception] = None
        self._turn_thread: Optional[threading.Thread] = None

    def _on_agent_event(self, event: Dict[str, Any]) -> None:
        self._event_queue.put(dict(event))

    def start(self) -> None:
        with self._lock:
            if self._agent is not None:
                return
            self._agent = DJSessionAgent(
                use_llm_router=True,
                dataset_path=self._dataset_path,
                export_path=self._export_path,
                verbose=self._verbose,
                event_callback=self._on_agent_event,
            )

    def submit_turn(self, message: str) -> None:
        with self._lock:
            if self._agent is None:
                raise RuntimeError("SessionController has not been started")
            if self._turn_running:
                raise RuntimeError("A turn is already running")

            self._turn_running = True
            self._turn_reply = None
            self._turn_error = None

            def _worker() -> None:
                try:
                    with suppress_tui_noise_stderr():
                        reply = self._agent.handle_message(message)
                    with self._lock:
                        self._turn_reply = reply
                except Exception as exc:  # pragma: no cover - defensive path
                    with self._lock:
                        self._turn_error = exc
                finally:
                    with self._lock:
                        self._turn_running = False

            thread = threading.Thread(target=_worker, daemon=True)
            self._turn_thread = thread
            thread.start()

    def is_turn_running(self) -> bool:
        with self._lock:
            return self._turn_running

    def request_interrupt(self) -> bool:
        with self._lock:
            agent = self._agent
        if agent is None:
            return False
        try:
            return bool(agent.request_interrupt())
        except Exception:  # pragma: no cover - defensive path
            return False

    def drain_events(self) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        while True:
            try:
                rows.append(self._event_queue.get_nowait())
            except queue.Empty:
                return rows

    def consume_turn_result(self) -> SessionReply:
        with self._lock:
            running = self._turn_running
            reply = self._turn_reply
            error = self._turn_error
            thread = self._turn_thread

        if running:
            raise RuntimeError("Turn is still running")

        if thread is not None:
            thread.join(timeout=0.1)

        if reply is not None:
            with self._lock:
                self._turn_reply = None
                self._turn_error = None
                self._turn_thread = None
            return reply

        if error is not None:
            with self._lock:
                self._turn_reply = None
                self._turn_error = None
                self._turn_thread = None
            return SessionReply(
                text=(
                    "Unhandled session error, exiting session.\n"
                    f"error: {error}"
                ),
                stop=True,
            )

        return SessionReply(text="No response generated.")
