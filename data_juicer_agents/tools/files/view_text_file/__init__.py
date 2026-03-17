# -*- coding: utf-8 -*-
"""view_text_file tool package."""

from .input import GenericOutput, ViewTextFileInput
from .logic import view_text_file
from .tool import VIEW_TEXT_FILE

__all__ = ["GenericOutput", "VIEW_TEXT_FILE", "ViewTextFileInput", "view_text_file"]
