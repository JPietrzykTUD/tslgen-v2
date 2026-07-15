"""Installed compiler version shared by CLI, LSP, and release tooling."""

from __future__ import annotations

from functools import cache
from importlib.metadata import PackageNotFoundError, version


@cache
def package_version() -> str:
    """Return the installed distribution version, including in frozen builds."""

    try:
        return version("tslc")
    except PackageNotFoundError:
        return "unknown"


__all__ = ("package_version",)
