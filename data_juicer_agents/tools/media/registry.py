# -*- coding: utf-8 -*-
"""Registry for media tool specs."""

from __future__ import annotations

from typing import List

from data_juicer_agents.core.tool import ToolSpec

from .scan_media_folder.tool import SCAN_MEDIA_FOLDER

TOOL_SPECS: List[ToolSpec] = [SCAN_MEDIA_FOLDER]

__all__ = ["SCAN_MEDIA_FOLDER", "TOOL_SPECS"]
