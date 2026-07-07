"""Promotion helpers for target-family declarations."""

from __future__ import annotations

from tslc.catalog._builder_common import (
    _child,
    _children,
    _field_text,
    _list_text,
    _list_text_set,
    _opt_int,
    _source_span,
)
from tslc.catalog.target_families import ProfileFamilyCapability, TargetFamilyCatalog
from tslc.syntax.ast import ParsedTslField


def _build_target_families(fields: list[ParsedTslField]) -> TargetFamilyCatalog:
    known: set[str] = set()
    universal: set[str] = set()
    profiles: dict[str, ProfileFamilyCapability] = {}
    for field in fields:
        known.update(_list_text(_child(field, "known_extension_families")))
        universal.update(_list_text(_child(field, "universal_extension_families")))
        profile_families = _child(field, "profile_families")
        for entry in _children(profile_families):
            profiles[entry.key.text] = ProfileFamilyCapability(
                name=entry.key.text,
                extension_families=_list_text_set(_child(entry, "extension_families")),
                runner_kinds=_list_text_set(_child(entry, "runner_kinds")),
                sort_order=_int_field(_child(entry, "sort_order"), default=100),
                cpp_feature_flags=_bool_field(
                    _child(entry, "cpp_feature_flags"),
                    default=True,
                ),
                cpp_target=_field_text(_child(entry, "cpp_target")),
                cpp_detection=_field_text(_child(entry, "cpp_detection")),
                rust_target_features=_bool_field(
                    _child(entry, "rust_target_features"),
                    default=True,
                ),
                rust_target=_field_text(_child(entry, "rust_target")),
                rust_linker=_field_text(_child(entry, "rust_linker")),
                source=_source_span(entry.source),
            )
    return TargetFamilyCatalog(
        known_extension_families=frozenset(known),
        universal_extension_families=frozenset(universal),
        profile_families=profiles,
    )


def _bool_field(field: ParsedTslField | None, *, default: bool) -> bool:
    text = _field_text(field)
    if text is None:
        return default
    return text.lower() == "true"


def _int_field(field: ParsedTslField | None, *, default: int) -> int:
    value = _opt_int(_field_text(field))
    return default if value is None else value
