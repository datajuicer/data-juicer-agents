# -*- coding: utf-8 -*-
"""Lightweight dataset probing utilities for planning-time schema inference."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


_IMAGE_SUFFIXES = (
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
    ".bmp",
    ".tiff",
    ".svg",
)


def _looks_like_image_value(value: str) -> bool:
    lower = value.strip().lower()
    if lower.startswith(("http://", "https://")):
        return any(lower.split("?")[0].endswith(suf) for suf in _IMAGE_SUFFIXES)
    if "/" in lower or "\\" in lower:
        return any(lower.endswith(suf) for suf in _IMAGE_SUFFIXES)
    return any(lower.endswith(suf) for suf in _IMAGE_SUFFIXES)


def _value_kind(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        if _looks_like_image_value(value):
            return "image_ref"
        return "text"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "other"


def _load_jsonl_records(path: Path, sample_size: int) -> Tuple[List[Dict[str, Any]], int]:
    rows: List[Dict[str, Any]] = []
    scanned = 0
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if len(rows) >= sample_size:
                break
            line = line.strip()
            if not line:
                continue
            scanned += 1
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if isinstance(obj, dict):
                rows.append(obj)
    return rows, scanned


def _load_json_records(path: Path, sample_size: int) -> Tuple[List[Dict[str, Any]], int]:
    with open(path, "r", encoding="utf-8") as f:
        content = json.load(f)
    if isinstance(content, list):
        dict_rows = [item for item in content if isinstance(item, dict)]
        return dict_rows[:sample_size], min(len(dict_rows), sample_size)
    if isinstance(content, dict):
        return [content], 1
    return [], 0

def _load_csv_records(
    path: Path, sample_size: int, delimiter: str = ","
) -> Tuple[List[Dict[str, Any]], int]:
    rows: List[Dict[str, Any]] = []
    try:
        with open(path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            # Check if headers are present
            if reader.fieldnames is None:
                return [], 0
            for row in reader:
                if len(rows) >= sample_size:
                    break
                # Filter out None values that occur when rows have fewer fields than headers
                cleaned_row = {k: v for k, v in row.items() if v is not None}
                rows.append(cleaned_row)
    except (UnicodeDecodeError, csv.Error, IOError) as e:
        return [], 0
    return rows, len(rows)

def _load_parquet_records(path: Path, sample_size: int) -> Tuple[List[Dict[str, Any]], int]:
    try:
        import pyarrow.parquet as pq
    except ImportError:
        return [], 0

    parquet_file = pq.ParquetFile(str(path))
    # Read only the first batch of up to sample_size rows instead of
    # materializing the entire file before slicing.
    batch_iter = parquet_file.iter_batches(batch_size=sample_size)
    try:
        first_batch = next(batch_iter)
    except StopIteration:
        return [], 0

    rows = first_batch.to_pydict()
    num_records = len(next(iter(rows.values()))) if rows else 0
    records: List[Dict[str, Any]] = [
        {col: values[i] for col, values in rows.items()}
        for i in range(num_records)
    ]
    return records, num_records


_UNSUPPORTED_PREFIXES = (
    "hf://",
    "huggingface://",
    "s3://",
    "gs://",
    "az://",
    "hdfs://",
    "http://",
    "https://",
)


def _looks_like_unsupported_source(dataset_path: str) -> bool:
    lower = dataset_path.strip().lower()
    return any(lower.startswith(prefix) for prefix in _UNSUPPORTED_PREFIXES)


def _dataset_path_to_dataset(dataset_path: str) -> Dict[str, Any]:
    """Convert a plain dataset_path string to the standard dataset config format."""
    return {
        "configs": [
            {"type": "local", "path": dataset_path},
        ],
    }


def _resolve_dataset_config(
    dataset_path: str,
    dataset: Dict[str, Any] | None,
) -> Dict[str, Any]:
    """Merge dataset_path and dataset into a single standard dataset config.

    Priority: explicit *dataset* config wins; *dataset_path* is converted to
    the standard format as a fallback.
    """
    if dataset and isinstance(dataset, dict):
        return dict(dataset)
    if dataset_path:
        return _dataset_path_to_dataset(dataset_path)
    return {"configs": []}


def _pick_inspectable_path(dataset_config: Dict[str, Any]) -> str | None:
    """Return the first local file path from a dataset config that can be inspected."""
    configs = dataset_config.get("configs", [])
    if not isinstance(configs, list):
        return None
    for cfg in configs:
        if not isinstance(cfg, dict):
            continue
        source_type = str(cfg.get("type", "local")).strip().lower()
        path_value = str(cfg.get("path", "")).strip()
        if not path_value:
            continue
        if source_type in {"local", ""}:
            if not _looks_like_unsupported_source(path_value):
                return path_value
    return None


def inspect_dataset_schema(
    dataset_path: str = "",
    sample_size: int = 20,
    dataset: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Inspect a small sample of a dataset and infer keys/modality for planning.

    Accepts either a plain *dataset_path* or a structured *dataset* config
    (the ``{"configs": [...]}`` format).  When *dataset_path* is provided it
    is automatically converted to the standard dataset config format so that
    all sources are handled uniformly.
    """
    resolved_config = _resolve_dataset_config(dataset_path, dataset)
    inspectable_path = _pick_inspectable_path(resolved_config)

    if inspectable_path is None:
        # No local path available to inspect
        configs = resolved_config.get("configs", [])
        if configs:
            return {
                "ok": False,
                "error_type": "unsupported_input_source",
                "error": (
                    "inspect_dataset could not find a local file path to inspect "
                    "in the provided dataset config. Only local file-based sources "
                    "are supported for schema inspection."
                ),
                "message": (
                    "No inspectable local path found in dataset config. "
                    "Ensure at least one source has type='local' with a valid file path."
                ),
                "dataset": resolved_config,
            }
        return {
            "ok": False,
            "error_type": "missing_dataset_source",
            "error": "No dataset source provided. Pass dataset_path or dataset config.",
            "message": "No dataset source provided.",
        }

    path = Path(inspectable_path)
    if not path.exists():
        return {
            "ok": False,
            "error_type": "dataset_path_not_found",
            "error": f"dataset_path does not exist: {inspectable_path}",
            "message": f"dataset_path does not exist: {inspectable_path}",
            "dataset": resolved_config,
        }
    if sample_size <= 0:
        sample_size = 20

    rows: List[Dict[str, Any]]
    scanned: int

    suffix = path.suffix.lower()
    if suffix == ".json":
        rows, scanned = _load_json_records(path, sample_size=sample_size)
    elif suffix == ".csv":
        rows, scanned = _load_csv_records(path, sample_size=sample_size)
    elif suffix == ".tsv":
        rows, scanned = _load_csv_records(path, sample_size=sample_size, delimiter="\t")
    elif suffix == ".parquet":
        rows, scanned = _load_parquet_records(path, sample_size=sample_size)
    else:
        rows, scanned = _load_jsonl_records(path, sample_size=sample_size)

    if not rows:
        return {
            "ok": False,
            "error_type": "inspect_failed",
            "error": (
                f"Failed to load any valid records from the dataset. "
                f"This could be due to: (1) file format/encoding issues, "
                f"(2) malformed data structure, or (3) empty dataset. "
                f"Scanned {scanned} lines but found no valid dict records."
            ),
            "message": (
                f"Could not extract valid records from '{inspectable_path}'. "
                f"Try inspecting the file manually with shell commands like: "
                f"'head -n 3 {inspectable_path}' or 'cat {inspectable_path} | head -n 3' "
                f"to verify the file format and content structure."
            ),
            "dataset": resolved_config,
            "sampled_records": 0,
            "scanned_lines": scanned,
        }

    key_stats: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        for key, value in row.items():
            stat = key_stats.setdefault(
                key,
                {
                    "count": 0,
                    "kinds": {},
                    "avg_text_len": 0.0,
                },
            )
            stat["count"] += 1
            kind = _value_kind(value)
            stat["kinds"][kind] = int(stat["kinds"].get(kind, 0)) + 1
            if kind == "text":
                prev_avg = float(stat["avg_text_len"])
                text_count = int(stat["kinds"]["text"])
                new_len = len(str(value))
                stat["avg_text_len"] = prev_avg + (new_len - prev_avg) / text_count

    def text_score(item: Tuple[str, Dict[str, Any]]) -> float:
        key, stat = item
        kinds = stat["kinds"]
        text_cnt = int(kinds.get("text", 0))
        if text_cnt <= 0:
            return -1.0
        key_bonus = 0.0
        if any(h in key.lower() for h in ["text", "content", "doc", "sentence", "chunk"]):
            key_bonus += 1.0
        return text_cnt + min(float(stat.get("avg_text_len", 0.0)) / 80.0, 2.0) + key_bonus

    def image_score(item: Tuple[str, Dict[str, Any]]) -> float:
        key, stat = item
        kinds = stat["kinds"]
        image_cnt = int(kinds.get("image_ref", 0))
        if image_cnt <= 0:
            return -1.0
        key_bonus = 0.0
        if any(h in key.lower() for h in ["image", "img", "picture", "photo", "vision"]):
            key_bonus += 1.0
        return image_cnt + key_bonus

    ranked_text = sorted(key_stats.items(), key=text_score, reverse=True)
    ranked_image = sorted(key_stats.items(), key=image_score, reverse=True)

    candidate_text_keys = [k for k, v in ranked_text if text_score((k, v)) > 0][:3]
    candidate_image_keys = [k for k, v in ranked_image if image_score((k, v)) > 0][:3]

    if candidate_text_keys and candidate_image_keys:
        modality = "multimodal"
    elif candidate_image_keys:
        modality = "image"
    elif candidate_text_keys:
        modality = "text"
    else:
        modality = "unknown"

    # Keep sample preview short and safe.
    preview: List[Dict[str, Any]] = []
    for row in rows[:2]:
        one: Dict[str, Any] = {}
        for k, v in row.items():
            if isinstance(v, str) and len(v) > 120:
                one[k] = v[:117] + "..."
            else:
                one[k] = v
        preview.append(one)

    return {
        "ok": True,
        "message": "dataset inspected",
        "dataset": resolved_config,
        "inspected_path": inspectable_path,
        "sampled_records": len(rows),
        "scanned_lines": scanned,
        "modality": modality,
        "keys": sorted(key_stats.keys()),
        "candidate_text_keys": candidate_text_keys,
        "candidate_image_keys": candidate_image_keys,
        "key_stats": key_stats,
        "sample_preview": preview,
    }
