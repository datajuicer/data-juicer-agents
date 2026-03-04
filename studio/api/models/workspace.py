# -*- coding: utf-8 -*-
"""Workspace (plan/data) request/response models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PlanLoadResponse(BaseModel):
    ok: bool = True
    path: str
    plan: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class PlanSaveRequest(BaseModel):
    path: str
    plan: dict = Field(default_factory=dict)


class PlanSaveResponse(BaseModel):
    ok: bool = True
    path: str
    plan: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class DataSampleBlock(BaseModel):
    path: str
    exists: bool
    keys: list[str] = Field(default_factory=list)
    records: list[dict] = Field(default_factory=list)
    sample_count: int = 0
    truncated: bool = False
    modality: str = "unknown"


class DataPreviewResponse(BaseModel):
    ok: bool = True
    sample: DataSampleBlock
    warnings: list[str] = Field(default_factory=list)


class DataCompareByRunResponse(BaseModel):
    ok: bool = True
    run_id: str
    plan_id: str | None = None
    dataset_path: str | None = None
    export_path: str | None = None
    input: DataSampleBlock | None = None
    output: DataSampleBlock | None = None
    warnings: list[str] = Field(default_factory=list)


__all__ = [
    "PlanLoadResponse",
    "PlanSaveRequest",
    "PlanSaveResponse",
    "DataSampleBlock",
    "DataPreviewResponse",
    "DataCompareByRunResponse",
]
