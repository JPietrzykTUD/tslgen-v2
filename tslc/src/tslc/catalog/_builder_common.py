"""Shared promoted-value helpers for catalog promotion.

Parse-tree shape access (children/child/scalar/list/span) lives in
:mod:`tslc.syntax.access`; this module keeps only the small value coercions
promotion layers share.
"""

from __future__ import annotations

from tslc.syntax.access import field_text as _field_text
from tslc.syntax.access import list_text as _list_text
from tslc.syntax.ast import ParsedTslField


def _opt_int(text: str | None) -> int | None:
    if text is None:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _bool_field(field: ParsedTslField | None) -> bool:
    return (_field_text(field) or "").lower() == "true"


def _list_text_set(field: ParsedTslField | None) -> frozenset[str]:
    return frozenset(_list_text(field))
