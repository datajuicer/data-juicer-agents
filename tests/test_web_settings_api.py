# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from studio.api.main import app


class _DummyResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_settings_profile_default(tmp_path: Path, monkeypatch):
    config_path = tmp_path / ".djx" / "config.json"
    monkeypatch.setenv("DJX_UI_CONFIG_PATH", str(config_path))

    with TestClient(app) as client:
        response = client.get("/api/settings/profile")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["profile_name"] == "default"
    assert payload["profile"]["has_api_key"] is False
    assert payload["profile"]["dashscope_api_key_masked"] is None
    assert payload["config_path"] == str(config_path)


def test_settings_profile_update_persists(tmp_path: Path, monkeypatch):
    config_path = tmp_path / ".djx" / "config.json"
    monkeypatch.setenv("DJX_UI_CONFIG_PATH", str(config_path))

    update_payload = {
        "profile_name": "default",
        "dashscope_api_key": "sk-12345678",
        "session_model": "qwen3-max-2026-01-23",
        "planner_model": "qwen3-max-2026-01-23",
        "validator_model": "qwen3-max-2026-01-23",
        "thinking": True,
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    }

    with TestClient(app) as client:
        response = client.put("/api/settings/profile", json=update_payload)

    assert response.status_code == 200
    payload = response.json()
    assert payload["profile"]["has_api_key"] is True
    assert payload["profile"]["dashscope_api_key_masked"].startswith("sk-1")
    assert "12345678" not in payload["profile"]["dashscope_api_key_masked"]

    raw = json.loads(config_path.read_text(encoding="utf-8"))
    assert raw["profiles"]["default"]["dashscope_api_key"] == "sk-12345678"


def test_settings_connection_missing_key(tmp_path: Path, monkeypatch):
    config_path = tmp_path / ".djx" / "config.json"
    monkeypatch.setenv("DJX_UI_CONFIG_PATH", str(config_path))

    with TestClient(app) as client:
        response = client.post("/api/settings/test-connection", json={})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert "Missing API key" in payload["message"]


def test_settings_connection_success_with_override(tmp_path: Path, monkeypatch):
    config_path = tmp_path / ".djx" / "config.json"
    monkeypatch.setenv("DJX_UI_CONFIG_PATH", str(config_path))

    from studio.api.services import settings_service

    def _fake_get(url, headers=None, timeout=None):
        assert url.endswith("/models")
        return _DummyResponse(
            200,
            {
                "data": [
                    {"id": "qwen3-max-2026-01-23"},
                    {"id": "qwen-plus"},
                ]
            },
        )

    monkeypatch.setattr(settings_service.httpx, "get", _fake_get)

    with TestClient(app) as client:
        response = client.post(
            "/api/settings/test-connection",
            json={
                "override": {
                    "dashscope_api_key": "sk-override",
                    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                }
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["models"] == ["qwen3-max-2026-01-23", "qwen-plus"]
