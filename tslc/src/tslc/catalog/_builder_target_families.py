"""Promotion helpers for target-family declarations."""

from __future__ import annotations

from tslc.catalog._builder_common import (
    _child,
    _children,
    _list_text,
    _list_text_set,
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
                emulator_kinds=_list_text_set(_child(entry, "emulator_kinds")),
                source=_source_span(entry.source),
            )
    return TargetFamilyCatalog(
        known_extension_families=frozenset(known),
        universal_extension_families=frozenset(universal),
        profile_families=profiles,
    )

