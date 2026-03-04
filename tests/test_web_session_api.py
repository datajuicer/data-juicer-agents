# -*- coding: utf-8 -*-

from __future__ import annotations

import threading
import time
from types import SimpleNamespace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from studio.api.managers import session_manager as session_manager_mod
from studio.api.deps import get_session_manager
from studio.api.main import app
from studio.api.managers.session_manager import SessionManager


class _FakeSessionAgent:
    def __init__(
        self,
        use_llm_router=True,
        dataset_path=None,
        export_path=None,
        verbose=False,
        api_key=None,
        base_url=None,
        model_name=None,
        planner_model=None,
        thinking=None,
        event_callback=None,
    ):
        self._event_callback = event_callback
        self.state = SimpleNamespace(
            dataset_path=dataset_path,
            export_path=export_path,
            plan_path=None,
            run_id=None,
            custom_operator_paths=[],
            history=[],
        )

    def handle_message(self, message: str):
        if self._event_callback is not None:
            self._event_callback(
                {
                    "type": "tool_start",
                    "tool": "retrieve_operators",
                    "call_id": "tool_1",
                    "args": {"intent": message},
                }
            )
            self._event_callback(
                {
                    "type": "tool_end",
                    "tool": "retrieve_operators",
                    "call_id": "tool_1",
                    "ok": True,
                    "summary": "ok",
                }
            )
        self.state.history.append({"role": "user", "content": message})
        text = f"echo:{message}"
        self.state.history.append({"role": "assistant", "content": text})
        return SimpleNamespace(text=text, stop=False, thinking="mock_thinking")

    def request_interrupt(self):
        return True


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    config_path = tmp_path / ".djx" / "config.json"
    monkeypatch.setenv("DJX_UI_CONFIG_PATH", str(config_path))
    monkeypatch.setattr(session_manager_mod, "DJSessionAgent", _FakeSessionAgent)

    manager = SessionManager()
    app.dependency_overrides[get_session_manager] = lambda: manager
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _set_profile(client: TestClient, key: str = "sk-test"):
    response = client.put(
        "/api/settings/profile",
        json={
            "profile_name": "default",
            "dashscope_api_key": key,
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "session_model": "qwen3-max-2026-01-23",
            "planner_model": "qwen3-max-2026-01-23",
            "validator_model": "qwen3-max-2026-01-23",
            "thinking": True,
        },
    )
    assert response.status_code == 200


def test_session_start_message_events_and_stop(client: TestClient):
    _set_profile(client)

    start_response = client.post(
        "/api/session/start",
        json={
            "profile_name": "default",
            "dataset_path": "data/demo-dataset.jsonl",
            "export_path": "data/out.jsonl",
        },
    )
    assert start_response.status_code == 200
    start_payload = start_response.json()
    session_id = start_payload["session_id"]
    assert session_id
    assert any(event["type"] == "session_started" for event in start_payload["events"])

    message_response = client.post(
        "/api/session/message",
        json={
            "session_id": session_id,
            "message": "hello",
        },
    )
    assert message_response.status_code == 200
    message_payload = message_response.json()
    assert message_payload["reply_text"] == "echo:hello"
    event_types = [item["type"] for item in message_payload["events"]]
    assert "user_message" in event_types
    assert "tool_start" in event_types
    assert "tool_end" in event_types
    assert "assistant_message" in event_types
    assistant_event = [item for item in message_payload["events"] if item["type"] == "assistant_message"][-1]
    assert assistant_event["payload"]["thinking"] == "mock_thinking"

    list_response = client.get(
        "/api/session/events",
        params={
            "session_id": session_id,
            "after": 0,
        },
    )
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert list_payload["next_seq"] >= len(list_payload["events"])

    state_response = client.get(
        "/api/session/state",
        params={"session_id": session_id},
    )
    assert state_response.status_code == 200
    state_payload = state_response.json()
    assert state_payload["context"]["dataset_path"] == "data/demo-dataset.jsonl"

    stop_response = client.post(
        "/api/session/stop",
        json={"session_id": session_id},
    )
    assert stop_response.status_code == 200
    assert stop_response.json()["stopped"] is True

    after_stop_response = client.post(
        "/api/session/message",
        json={"session_id": session_id, "message": "hi"},
    )
    assert after_stop_response.status_code == 404


def test_session_start_requires_api_key(client: TestClient):
    _set_profile(client, key="")

    response = client.post(
        "/api/session/start",
        json={"profile_name": "default"},
    )
    assert response.status_code == 400
    assert "Missing API key" in response.json()["detail"]


def test_session_start_rejects_duplicate_id(client: TestClient):
    _set_profile(client)

    payload = {"profile_name": "default", "session_id": "sess_dup"}
    first = client.post("/api/session/start", json=payload)
    second = client.post("/api/session/start", json=payload)

    assert first.status_code == 200
    assert second.status_code == 400


def test_session_message_is_idempotent_by_client_message_id(client: TestClient):
    _set_profile(client)
    start = client.post("/api/session/start", json={"profile_name": "default"})
    assert start.status_code == 200
    session_id = start.json()["session_id"]

    payload = {
        "session_id": session_id,
        "message": "hello",
        "client_message_id": "msg_abc123",
    }
    first = client.post("/api/session/message", json=payload)
    second = client.post("/api/session/message", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200

    first_events = first.json()["events"]
    second_events = second.json()["events"]
    assert [item["type"] for item in first_events] == [item["type"] for item in second_events]
    assert first.json()["reply_text"] == second.json()["reply_text"]

    all_events = client.get(
        "/api/session/events",
        params={"session_id": session_id, "after": 0},
    )
    assert all_events.status_code == 200
    event_types = [item["type"] for item in all_events.json()["events"]]
    assert event_types.count("user_message") == 1


def test_session_interrupt_endpoint(client: TestClient, monkeypatch):
    class _InterruptibleAgent(_FakeSessionAgent):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._interrupted = False

        def handle_message(self, message: str):
            start = time.monotonic()
            while time.monotonic() - start < 5.0:
                if self._interrupted:
                    return SimpleNamespace(
                        text="interrupted",
                        stop=False,
                        interrupted=True,
                        thinking="",
                    )
                time.sleep(0.02)
            return SimpleNamespace(text=f"echo:{message}", stop=False, thinking="")

        def request_interrupt(self):
            self._interrupted = True
            return True

    monkeypatch.setattr(session_manager_mod, "DJSessionAgent", _InterruptibleAgent)
    _set_profile(client)
    start_resp = client.post("/api/session/start", json={"profile_name": "default"})
    assert start_resp.status_code == 200
    session_id = start_resp.json()["session_id"]

    holder = {}

    def _send():
        holder["resp"] = client.post(
            "/api/session/message",
            json={"session_id": session_id, "message": "long task"},
        )

    t = threading.Thread(target=_send, daemon=True)
    t.start()
    time.sleep(0.2)

    interrupt_resp = client.post(
        "/api/session/interrupt",
        json={"session_id": session_id},
    )
    assert interrupt_resp.status_code == 200
    assert interrupt_resp.json()["accepted"] is True

    t.join(timeout=8)
    assert "resp" in holder
    message_resp = holder["resp"]
    assert message_resp.status_code == 200
    payload = message_resp.json()
    assert payload["interrupted"] is True
    assert payload["stop"] is False

    events_resp = client.get("/api/session/events", params={"session_id": session_id, "after": 0})
    assert events_resp.status_code == 200
    event_types = [item["type"] for item in events_resp.json()["events"]]
    assert "interrupt_requested" in event_types
    assert "interrupt_ack" in event_types


def test_session_interrupt_when_idle_is_ignored(client: TestClient):
    _set_profile(client)
    start_resp = client.post("/api/session/start", json={"profile_name": "default"})
    assert start_resp.status_code == 200
    session_id = start_resp.json()["session_id"]

    interrupt_resp = client.post(
        "/api/session/interrupt",
        json={"session_id": session_id},
    )
    assert interrupt_resp.status_code == 200
    assert interrupt_resp.json()["accepted"] is False
