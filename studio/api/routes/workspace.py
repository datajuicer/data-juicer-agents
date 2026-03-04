# -*- coding: utf-8 -*-
"""Workspace routes for plan/data operations."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from studio.api.models.workspace import (
    DataCompareByRunResponse,
    DataPreviewResponse,
    PlanLoadResponse,
    PlanSaveRequest,
    PlanSaveResponse,
)
from studio.api.services.workspace_service import (
    compare_data_by_run,
    load_plan_file,
    preview_data_file,
    save_plan_file,
)

router = APIRouter(tags=["workspace"])


@router.get("/api/plan", response_model=PlanLoadResponse)
def load_plan(path: str = Query(..., min_length=1)) -> PlanLoadResponse:
    try:
        plan_path, payload, warnings = load_plan_file(path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return PlanLoadResponse(
        ok=True,
        path=str(plan_path),
        plan=payload,
        warnings=warnings,
    )


@router.post("/api/plan", response_model=PlanSaveResponse)
def save_plan(request: PlanSaveRequest) -> PlanSaveResponse:
    try:
        plan_path, payload, warnings = save_plan_file(
            path=request.path,
            plan_payload=request.plan,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return PlanSaveResponse(
        ok=True,
        path=str(plan_path),
        plan=payload,
        warnings=warnings,
    )


@router.get("/api/data/preview", response_model=DataPreviewResponse)
def preview_data(
    path: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> DataPreviewResponse:
    sample, warnings = preview_data_file(path=path, limit=limit, offset=offset)
    return DataPreviewResponse(ok=True, sample=sample, warnings=warnings)


@router.get("/api/data/compare-by-run", response_model=DataCompareByRunResponse)
def preview_compare_by_run(
    run_id: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> DataCompareByRunResponse:
    try:
        payload = compare_data_by_run(run_id=run_id, limit=limit, offset=offset)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return DataCompareByRunResponse(
        ok=True,
        run_id=str(payload.get("run_id", "")),
        plan_id=payload.get("plan_id"),
        dataset_path=payload.get("dataset_path"),
        export_path=payload.get("export_path"),
        input=payload.get("input"),
        output=payload.get("output"),
        warnings=list(payload.get("warnings", [])),
    )


__all__ = ["router"]
