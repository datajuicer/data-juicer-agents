# -*- coding: utf-8 -*-
"""SmartBash harness — structured bash execution with result parsing and error diagnosis."""

from .execute_bash.tool import EXECUTE_BASH

TOOL_SPECS = [EXECUTE_BASH]

__all__ = ["TOOL_SPECS"]
