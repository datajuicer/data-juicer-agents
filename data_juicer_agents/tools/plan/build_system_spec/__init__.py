# -*- coding: utf-8 -*-
"""build_system_spec tool package."""

from .input import BuildSystemSpecInput
from .logic import build_system_spec
from .tool import BUILD_SYSTEM_SPEC

__all__ = ["BUILD_SYSTEM_SPEC", "BuildSystemSpecInput", "build_system_spec"]
