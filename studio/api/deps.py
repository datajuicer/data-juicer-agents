# -*- coding: utf-8 -*-
"""Dependency providers for API routes."""

from __future__ import annotations

from studio.api.managers.session_manager import SessionManager
from studio.api.repositories.settings_repository import SettingsStore


_session_manager = SessionManager()


def get_store() -> SettingsStore:
    return SettingsStore()


def get_session_manager() -> SessionManager:
    return _session_manager


__all__ = ["get_store", "get_session_manager"]
