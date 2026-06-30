"""Promotion helpers for simple catalog block declarations."""

from __future__ import annotations

from tslc.catalog._builder_common import (
    _entry,
    _field_text,
    _list_text,
    _scalar_text,
)
from tslc.syntax.ast import ParsedBlockDeclaration


def _build_type_groups(declaration: ParsedBlockDeclaration) -> dict[str, tuple[str, ...]]:
    groups: dict[str, tuple[str, ...]] = {}
    for field in declaration.fields:
        types_field = _entry(field, "types")
        if types_field is None:
            continue
        groups[field.key.text] = _list_text(types_field)
    return groups



def _build_type_spellings(declaration: ParsedBlockDeclaration) -> dict[str, str]:
    spellings: dict[str, str] = {}
    for field in declaration.fields:
        type_entry = _entry(field, "type")
        text = _scalar_text(type_entry) if type_entry is not None else None
        if text is not None:
            spellings[field.key.text] = text
    return spellings



def _build_translations(declaration: ParsedBlockDeclaration) -> dict[str, str]:
    """Promote a ``translation <backend>:`` block of ``key "template"`` entries."""

    templates: dict[str, str] = {}
    for field in declaration.fields:
        text = _scalar_text(field)
        if text is not None:
            templates[field.key.text] = text
    return templates

