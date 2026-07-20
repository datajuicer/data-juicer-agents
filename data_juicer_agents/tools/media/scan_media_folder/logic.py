# -*- coding: utf-8 -*-
"""Pure logic for scan_media_folder — runtime-agnostic."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set


# ---- Suffix constants (mirrored from data_juicer.format.media_folder_formatter) ----
IMAGE_SUFFIXES: frozenset = frozenset({
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".tif", ".svg",
})

VIDEO_SUFFIXES: frozenset = frozenset({
    ".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv", ".webm", ".m4v", ".ts",
})

# DJ special tokens (defaults; kept literal to avoid importing DJ at tool-logic time)
_IMAGE_TOKEN = "<__dj__image>"
_VIDEO_TOKEN = "<__dj__video>"
_EOC_TOKEN = "<|__dj__eoc|>"


def _normalize_suffixes(suffixes: Optional[Sequence[str]]) -> Set[str]:
    if suffixes is None:
        return set()
    result = set()
    for s in suffixes:
        s = s.strip().lower()
        if not s:
            continue
        if not s.startswith("."):
            s = f".{s}"
        result.add(s)
    return result


def _scan_folder(
    folder_path: str,
    suffixes: Set[str],
    recursive: bool,
) -> List[str]:
    """Return sorted list of absolute paths matching *suffixes*."""
    matched: List[str] = []
    if recursive:
        walker = os.walk(folder_path)
    else:
        try:
            _root, _dirs, files = next(os.walk(folder_path))
        except StopIteration:
            return []
        walker = [(_root, [], files)]

    for root, _dirs, files in walker:
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext in suffixes:
                matched.append(os.path.join(root, fname))

    matched.sort()
    return matched


def scan_media_folder(
    *,
    folder_path: str,
    media_type: str = "auto",
    recursive: bool = True,
    output_path: str,
    suffixes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Scan *folder_path* and write a DJ-Format JSONL to *output_path*.

    Returns a summary dict.
    """
    # Resolve paths
    folder = Path(folder_path).expanduser().resolve()
    if not folder.is_dir():
        return {
            "ok": False,
            "error_type": "not_a_directory",
            "message": f"folder_path does not exist or is not a directory: {folder}",
        }

    out = Path(output_path).expanduser().resolve()

    # Determine suffixes to scan
    custom_suffixes = _normalize_suffixes(suffixes)

    if custom_suffixes:
        all_suffixes = custom_suffixes
    elif media_type == "image":
        all_suffixes = set(IMAGE_SUFFIXES)
    elif media_type == "video":
        all_suffixes = set(VIDEO_SUFFIXES)
    else:  # auto
        all_suffixes = set(IMAGE_SUFFIXES) | set(VIDEO_SUFFIXES)

    # Scan
    paths = _scan_folder(str(folder), all_suffixes, recursive)
    if not paths:
        return {
            "ok": False,
            "error_type": "no_files_found",
            "message": f"No media files found under {folder} (suffixes={sorted(all_suffixes)})",
        }

    # Build records
    records: List[Dict[str, Any]] = []
    image_count = 0
    video_count = 0

    for p in paths:
        ext = os.path.splitext(p)[1].lower()
        if ext in IMAGE_SUFFIXES:
            records.append({
                "text": f"{_IMAGE_TOKEN} {_EOC_TOKEN}",
                "images": [p],
            })
            image_count += 1
        elif ext in VIDEO_SUFFIXES:
            records.append({
                "text": f"{_VIDEO_TOKEN} {_EOC_TOKEN}",
                "videos": [p],
            })
            video_count += 1

    # Write JSONL
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as fh:
            for rec in records:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception as exc:
        return {
            "ok": False,
            "error_type": "write_failed",
            "message": f"Failed to write JSONL to {out}: {exc}",
        }

    # Determine detected type label
    if image_count > 0 and video_count > 0:
        detected = "mixed"
    elif video_count > 0:
        detected = "video"
    else:
        detected = "image"

    sample = records[:3]

    return {
        "ok": True,
        "record_count": len(records),
        "output_path": str(out),
        "sample_records": sample,
        "media_type_detected": detected,
        "image_count": image_count,
        "video_count": video_count,
        "message": (
            f"Scanned {len(records)} media file(s) ({image_count} image(s), "
            f"{video_count} video(s)) → {out}"
        ),
    }
