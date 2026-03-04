# -*- coding: utf-8 -*-
"""Shared API schema fragments."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SessionEventItem(BaseModel):
    seq: int
    session_id: str
    type: str
    timestamp: str
    payload: dict = Field(default_factory=dict)


__all__ = ["SessionEventItem"]
