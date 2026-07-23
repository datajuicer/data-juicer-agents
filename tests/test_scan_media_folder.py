# -*- coding: utf-8 -*-

import json
from pathlib import Path

from data_juicer_agents.tools.media.scan_media_folder.logic import scan_media_folder


def _touch(folder: Path, *names: str) -> None:
    """Create empty files (no real media bytes needed for these tests)."""
    for name in names:
        (folder / name).write_text("", encoding="utf-8")


def _read_jsonl(path: Path) -> list:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_scan_images(tmp_path: Path):
    src = tmp_path / "media"
    src.mkdir()
    _touch(src, "a.jpg", "b.png", "note.txt")
    out = tmp_path / "index.jsonl"

    result = scan_media_folder(
        folder_path=str(src), media_type="image", output_path=str(out)
    )

    assert result["ok"] is True
    assert result["image_count"] == 2
    assert result["video_count"] == 0
    assert result["record_count"] == 2
    assert result["media_type_detected"] == "image"
    rows = _read_jsonl(out)
    assert len(rows) == 2
    assert all(r.get("images") for r in rows)


def test_scan_videos(tmp_path: Path):
    src = tmp_path / "media"
    src.mkdir()
    _touch(src, "a.mp4", "b.mov")
    out = tmp_path / "index.jsonl"

    result = scan_media_folder(
        folder_path=str(src), media_type="video", output_path=str(out)
    )

    assert result["ok"] is True
    assert result["video_count"] == 2
    assert result["image_count"] == 0
    assert result["media_type_detected"] == "video"
    rows = _read_jsonl(out)
    assert all(r.get("videos") for r in rows)


def test_scan_mixed_auto(tmp_path: Path):
    src = tmp_path / "media"
    src.mkdir()
    _touch(src, "a.jpg", "b.mp4")
    out = tmp_path / "index.jsonl"

    # media_type defaults to 'auto'
    result = scan_media_folder(folder_path=str(src), output_path=str(out))

    assert result["ok"] is True
    assert result["image_count"] == 1
    assert result["video_count"] == 1
    assert result["record_count"] == 2
    assert result["media_type_detected"] == "mixed"


def test_empty_folder_creates_no_file(tmp_path: Path):
    src = tmp_path / "media"
    src.mkdir()
    _touch(src, "note.txt")  # no media files
    out = tmp_path / "index.jsonl"

    result = scan_media_folder(folder_path=str(src), output_path=str(out))

    assert result["ok"] is False
    assert result["error_type"] == "no_files_found"
    # lazy-open means no stray empty file is left behind
    assert not out.exists()


def test_custom_suffixes(tmp_path: Path):
    src = tmp_path / "media"
    src.mkdir()
    _touch(src, "a.dng", "b.dng", "c.jpg")
    out = tmp_path / "index.jsonl"

    result = scan_media_folder(
        folder_path=str(src), output_path=str(out), suffixes=[".dng"]
    )

    assert result["ok"] is True
    # custom suffixes override the defaults: only .dng matched, .jpg excluded
    assert result["record_count"] == 2
    # a custom suffix under 'auto' is classified as image, not dropped
    assert result["image_count"] == 2
    rows = _read_jsonl(out)
    assert all(r.get("images") for r in rows)


def test_recursive_false_skips_subdirs(tmp_path: Path):
    src = tmp_path / "media"
    (src / "sub").mkdir(parents=True)
    _touch(src, "top.jpg")
    _touch(src / "sub", "nested.jpg")
    out = tmp_path / "index.jsonl"

    result = scan_media_folder(
        folder_path=str(src), output_path=str(out), recursive=False
    )

    assert result["ok"] is True
    assert result["record_count"] == 1  # only the top-level file


def test_bad_path(tmp_path: Path):
    missing = tmp_path / "does_not_exist"
    out = tmp_path / "index.jsonl"

    result = scan_media_folder(folder_path=str(missing), output_path=str(out))

    assert result["ok"] is False
    assert result["error_type"] == "not_a_directory"
