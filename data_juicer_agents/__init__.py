# -*- coding: utf-8 -*-
"""Data-Juicer-Agents package."""

from importlib.metadata import PackageNotFoundError, version


try:
    __version__ = version("data-juicer-agents")
except PackageNotFoundError:
    __version__ = "0+unknown"


__all__ = ["__version__"]
