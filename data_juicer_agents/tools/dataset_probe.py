# -*- coding: utf-8 -*-
"""Lightweight dataset probing utilities for planning-time schema inference."""

from __future__ import annotations

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


def inspect_dataset_schema(dataset_path: str, sample_size: int = 20) -> Dict[str, Any]:
    """Inspect a small sample of a dataset and infer keys/modality for planning."""

    path = Path(dataset_path)
    if not path.exists():
        return {
            "ok": False,
            "error": f"dataset_path does not exist: {dataset_path}",
            "dataset_path": dataset_path,
        }
    if sample_size <= 0:
        sample_size = 20

    rows: List[Dict[str, Any]]
    scanned: int

    if path.suffix.lower() == ".json":
        rows, scanned = _load_json_records(path, sample_size=sample_size)
    else:
        rows, scanned = _load_jsonl_records(path, sample_size=sample_size)

    if not rows:
        return {
            "ok": False,
            "error": "No valid object records found in sample",
            "dataset_path": dataset_path,
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
        "dataset_path": dataset_path,
        "sampled_records": len(rows),
        "scanned_lines": scanned,
        "modality": modality,
        "keys": sorted(key_stats.keys()),
        "candidate_text_keys": candidate_text_keys,
        "candidate_image_keys": candidate_image_keys,
        "key_stats": key_stats,
        "sample_preview": preview,
    }
