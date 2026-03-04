# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from pathlib import Path

from studio.api.repositories.settings_repository import SettingsStore, mask_api_key


def test_settings_store_default_document(tmp_path: Path):
    config_path = tmp_path / ".djx" / "config.json"
    store = SettingsStore(config_path=config_path)

    name, profile = store.get_profile()

    assert name == "default"
    assert profile["session_model"] == "qwen3-max-2026-01-23"
    assert profile["base_url"].startswith("https://")


def test_settings_store_update_and_reload(tmp_path: Path):
    config_path = tmp_path / ".djx" / "config.json"
    store = SettingsStore(config_path=config_path)

    store.update_profile(
        profile_name="default",
        patch={
            "dashscope_api_key": "sk-abc123456",
            "thinking": False,
        },
    )

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert payload["profiles"]["default"]["dashscope_api_key"] == "sk-abc123456"
    assert payload["profiles"]["default"]["thinking"] is False

    name, profile = SettingsStore(config_path=config_path).get_profile("default")
    assert name == "default"
    assert profile["dashscope_api_key"] == "sk-abc123456"
    assert profile["thinking"] is False


def test_mask_api_key():
    assert mask_api_key("") is None
    assert mask_api_key("sk-12345678") == "sk-1***5678"
    assert mask_api_key("abcd") == "****"
