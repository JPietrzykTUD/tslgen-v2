"""Target-neutral generated identifier spelling."""

from __future__ import annotations

import re


def identifier_slug(name: str) -> str:
    return re.sub(r"[^0-9A-Za-z_]", "_", name)


__all__ = ("identifier_slug",)
