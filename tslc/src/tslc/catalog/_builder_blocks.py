"""Promotion helpers for simple catalog block declarations."""

from __future__ import annotations

from tslc.syntax.access import child as _child
from tslc.syntax.access import field_text as _field_text
from tslc.syntax.access import list_text as _list_text
from tslc.syntax.ast import ParsedBlockDeclaration


def _build_type_groups(declaration: ParsedBlockDeclaration) -> dict[str, tuple[str, ...]]:
    # A group without a non-empty member list is not promoted; schema validation
    # reports it (TSL-CATALOG-TYPE-GROUP-MALFORMED). Promoting an empty group
    # would make it the most specific selector while matching nothing.
    groups: dict[str, tuple[str, ...]] = {}
    for field in declaration.fields:
        types_field = _child(field, "types")
        if types_field is None:
            continue
        members = _list_text(types_field)
        if not members:
            continue
        groups[field.key.text] = members
    return groups



def _build_type_spellings(declaration: ParsedBlockDeclaration) -> dict[str, str]:
    spellings: dict[str, str] = {}
    for field in declaration.fields:
        type_entry = _child(field, "type")
        text = _field_text(type_entry) if type_entry is not None else None
        if text is not None:
            spellings[field.key.text] = text
    return spellings



def _build_translations(declaration: ParsedBlockDeclaration) -> dict[str, str]:
    """Promote a ``translation <backend>:`` block of ``key "template"`` entries."""

    templates: dict[str, str] = {}
    for field in declaration.fields:
        text = _field_text(field)
        if text is not None:
            templates[field.key.text] = text
    return templates

