# -*- coding: utf-8 -*-
"""Pure logic for scan_media_folder — runtime-agnostic."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Set


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


def _iter_media_files(
    folder_path: str,
    suffixes: Set[str],
    recursive: bool,
) -> Iterator[str]:
    """Yield absolute paths under *folder_path* whose suffix is in *suffixes*.

    Streams results so peak memory stays O(files-per-directory) instead of
    holding every matched path at once — important for the large FUSE-mounted
    folders this tool targets. Entries are sorted within each directory (and
    directories traversed in sorted order) for deterministic output.
    """
    if recursive:
        walker = os.walk(folder_path)
    else:
        try:
            _root, _dirs, files = next(os.walk(folder_path))
        except StopIteration:
            return
        walker = [(_root, [], files)]

    for root, dirs, files in walker:
        dirs.sort()
        for fname in sorted(files):
            ext = os.path.splitext(fname)[1].lower()
            if ext in suffixes:
                yield os.path.join(root, fname)


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

    # Stream: classify and write one record per file so peak memory stays O(1)
    # regardless of folder size (only counts and up to 3 samples are retained).
    # The output file is opened lazily on the first match, so an empty result
    # never creates a stray file (and never needs a delete on a FUSE mount).
    image_count = 0
    video_count = 0
    sample_records: List[Dict[str, Any]] = []
    fh = None
    try:
        for p in _iter_media_files(str(folder), all_suffixes, recursive):
            ext = os.path.splitext(p)[1].lower()
            # A file reaches this loop only if its suffix was scanned for, so an
            # extension outside the standard sets must be a user-supplied custom
            # suffix. Classify those by media_type instead of dropping them
            # silently: 'video' -> video record, 'image'/'auto' -> image record.
            is_video = ext in VIDEO_SUFFIXES or (
                ext not in IMAGE_SUFFIXES and media_type == "video"
            )
            if is_video:
                rec = {"text": f"{_VIDEO_TOKEN} {_EOC_TOKEN}", "videos": [p]}
                video_count += 1
            else:
                rec = {"text": f"{_IMAGE_TOKEN} {_EOC_TOKEN}", "images": [p]}
                image_count += 1

            if fh is None:
                out.parent.mkdir(parents=True, exist_ok=True)
                fh = open(out, "w", encoding="utf-8")
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

            if len(sample_records) < 3:
                sample_records.append(rec)
    except Exception as exc:
        return {
            "ok": False,
            "error_type": "write_failed",
            "message": f"Failed to write JSONL to {out}: {exc}",
        }
    finally:
        if fh is not None:
            fh.close()

    record_count = image_count + video_count
    if record_count == 0:
        return {
            "ok": False,
            "error_type": "no_files_found",
            "message": f"No media files found under {folder} (suffixes={sorted(all_suffixes)})",
        }

    # Determine detected type label
    if image_count > 0 and video_count > 0:
        detected = "mixed"
    elif video_count > 0:
        detected = "video"
    else:
        detected = "image"

    return {
        "ok": True,
        "record_count": record_count,
        "output_path": str(out),
        "sample_records": sample_records,
        "media_type_detected": detected,
        "image_count": image_count,
        "video_count": video_count,
        "message": (
            f"Scanned {record_count} media file(s) ({image_count} image(s), "
            f"{video_count} video(s)) → {out}"
        ),
    }
