# -*- coding: utf-8 -*-
"""Tool spec binding for scan_media_folder."""

from __future__ import annotations

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import ScanMediaFolderInput, ScanMediaFolderOutput
from .logic import scan_media_folder


def _scan_media_folder(_ctx: ToolContext, args: ScanMediaFolderInput) -> ToolResult:
    payload = scan_media_folder(
        folder_path=args.folder_path,
        media_type=args.media_type,
        recursive=args.recursive,
        output_path=args.output_path,
        suffixes=args.suffixes,
    )
    if payload.get("ok"):
        return ToolResult.success(
            summary=str(payload.get("message", "scan complete")),
            data=payload,
        )
    return ToolResult.failure(
        summary=str(payload.get("message", "scan_media_folder failed")),
        error_type=str(payload.get("error_type", "scan_failed")),
        data=payload,
    )


SCAN_MEDIA_FOLDER = ToolSpec(
    name="scan_media_folder",
    description=(
        "Scan a local folder of raw images or videos and generate a DJ-Format "
        "JSONL dataset.  Each file becomes one record with the appropriate "
        "text placeholder (<__dj__image> / <__dj__video>) and path list.  "
        "Use media_type='auto' to detect both images and videos together."
    ),
    input_model=ScanMediaFolderInput,
    output_model=ScanMediaFolderOutput,
    executor=_scan_media_folder,
    tags=("media", "scan", "image", "video", "dataset"),
    effects="write",
    confirmation="recommended",
)


__all__ = ["SCAN_MEDIA_FOLDER"]
