# -*- coding: utf-8 -*-
"""Workspace helpers for plan/data panels."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

from data_juicer_agents.capabilities.plan.schema import PlanModel, validate_plan
from data_juicer_agents.capabilities.trace.repository import TraceStore
from studio.api.models.workspace import DataSampleBlock


def _normalize_record(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {"_value": value}


def _infer_modality(keys: List[str]) -> str:
    key_set = {item.lower() for item in keys}
    image_hints = {"image", "image_path", "image_url", "images", "pixel_values"}
    text_hints = {"text", "content", "messages", "prompt", "response"}
    has_image = bool(key_set.intersection(image_hints))
    has_text = bool(key_set.intersection(text_hints))
    if has_image and has_text:
        return "multimodal"
    if has_image:
        return "image"
    if has_text:
        return "text"
    return "unknown"


def _read_jsonl_sample(path: Path, limit: int = 20, offset: int = 0) -> Tuple[DataSampleBlock, List[str]]:
    warnings: List[str] = []
    if limit <= 0:
        limit = 20
    if offset < 0:
        offset = 0

    records: List[Dict[str, Any]] = []
    keys_seen: set[str] = set()
    truncated = False

    if not path.exists():
        return (
            DataSampleBlock(
                path=str(path),
                exists=False,
                keys=[],
                records=[],
                sample_count=0,
                truncated=False,
                modality="unknown",
            ),
            warnings,
        )

    with path.open("r", encoding="utf-8") as f:
        for line_idx, line in enumerate(f, start=1):
            if line_idx <= offset:
                continue
            if len(records) >= limit:
                truncated = True
                break
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError:
                warnings.append(f"Invalid JSON line at {line_idx} skipped.")
                continue
            row = _normalize_record(payload)
            records.append(row)
            keys_seen.update(str(item) for item in row.keys())

    keys = sorted(keys_seen)
    sample = DataSampleBlock(
        path=str(path),
        exists=True,
        keys=keys,
        records=records,
        sample_count=len(records),
        truncated=truncated,
        modality=_infer_modality(keys),
    )
    return sample, warnings


def load_plan_file(path: str) -> Tuple[Path, Dict[str, Any], List[str]]:
    plan_path = Path(path).expanduser().resolve()
    if not plan_path.exists():
        raise FileNotFoundError(f"Plan file not found: {plan_path}")
    payload = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Plan YAML must parse to an object")
    return plan_path, payload, []


def save_plan_file(path: str, plan_payload: Dict[str, Any]) -> Tuple[Path, Dict[str, Any], List[str]]:
    plan_path = Path(path).expanduser().resolve()
    if not isinstance(plan_payload, dict):
        raise ValueError("plan must be an object")

    warnings: List[str] = []
    try:
        model = PlanModel.from_dict(plan_payload)
    except KeyError as exc:
        raise ValueError(f"Missing required plan field: {exc}") from exc
    except Exception as exc:
        raise ValueError(f"Invalid plan payload: {exc}") from exc

    errors = validate_plan(model)
    if errors:
        raise ValueError("; ".join(errors))

    normalized = model.to_dict()
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(
        yaml.safe_dump(normalized, allow_unicode=False, sort_keys=False),
        encoding="utf-8",
    )
    return plan_path, normalized, warnings


def preview_data_file(path: str, limit: int = 20, offset: int = 0) -> Tuple[DataSampleBlock, List[str]]:
    sample_path = Path(path).expanduser().resolve()
    return _read_jsonl_sample(sample_path, limit=limit, offset=offset)


def compare_data_by_run(run_id: str, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
    store = TraceStore()
    row = store.get(run_id)
    if row is None:
        raise FileNotFoundError(f"Run not found: {run_id}")

    warnings: List[str] = []
    plan_id = str(row.get("plan_id", "")).strip() or None

    dataset_path: str | None = None
    export_path: str | None = None

    recipe_path_raw = str(row.get("generated_recipe_path", "")).strip()
    if recipe_path_raw:
        recipe_path = Path(recipe_path_raw).expanduser()
        if recipe_path.exists():
            try:
                recipe_payload = yaml.safe_load(recipe_path.read_text(encoding="utf-8"))
                if isinstance(recipe_payload, dict):
                    dataset_path = str(recipe_payload.get("dataset_path", "")).strip() or None
                    export_path = str(recipe_payload.get("export_path", "")).strip() or None
            except Exception:
                warnings.append("Failed to parse generated recipe for dataset/export paths.")

    if not export_path:
        artifacts = row.get("artifacts", {})
        if isinstance(artifacts, dict):
            export_path = str(artifacts.get("export_path", "")).strip() or None

    input_sample = None
    output_sample = None

    if dataset_path:
        input_sample, in_warn = preview_data_file(dataset_path, limit=limit, offset=offset)
        warnings.extend(in_warn)
    else:
        warnings.append("dataset_path unavailable from run metadata.")

    if export_path:
        output_sample, out_warn = preview_data_file(export_path, limit=limit, offset=offset)
        warnings.extend(out_warn)
    else:
        warnings.append("export_path unavailable from run metadata.")

    return {
        "run_id": run_id,
        "plan_id": plan_id,
        "dataset_path": dataset_path,
        "export_path": export_path,
        "input": input_sample,
        "output": output_sample,
        "warnings": warnings,
    }
