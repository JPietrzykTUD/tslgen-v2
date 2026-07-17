"""Promotion helpers for target-family declarations."""

from __future__ import annotations

from tslc.catalog._builder_common import _list_text_set, _opt_int
from tslc.syntax.access import child as _child
from tslc.syntax.access import children as _children
from tslc.syntax.access import field_text as _field_text
from tslc.syntax.access import list_text as _list_text
from tslc.syntax.access import source_span as _source_span
from tslc.catalog.target_families import (
    BackendProfileFamily,
    ExtensionFamilyCapability,
    ProfileFamilyCapability,
    TargetFamilyCatalog,
)
from tslc.syntax.ast import ParsedTslField


def _build_target_families(fields: list[ParsedTslField]) -> TargetFamilyCatalog:
    known: set[str] = set()
    universal: set[str] = set()
    extension_capabilities: dict[str, ExtensionFamilyCapability] = {}
    profiles: dict[str, ProfileFamilyCapability] = {}
    for field in fields:
        known.update(_list_text(_child(field, "known_extension_families")))
        universal.update(_list_text(_child(field, "universal_extension_families")))
        extension_families = _child(field, "extension_family_capabilities")
        for entry in _children(extension_families):
            extension_capabilities[entry.key.text] = ExtensionFamilyCapability(
                name=entry.key.text,
                implementation_fallback=_bool_field(
                    _child(entry, "implementation_fallback"), default=False
                ),
                free_function_owner=_bool_field(
                    _child(entry, "free_function_owner"), default=True
                ),
                requires_declared_vector_register=_bool_field(
                    _child(entry, "requires_declared_vector_register"), default=True
                ),
                index_vector_register=_bool_field(
                    _child(entry, "index_vector_register"), default=False
                ),
                source=_source_span(entry.source),
            )
        profile_families = _child(field, "profile_families")
        for entry in _children(profile_families):
            profiles[entry.key.text] = ProfileFamilyCapability(
                name=entry.key.text,
                extension_families=_list_text_set(_child(entry, "extension_families")),
                runner_kinds=_list_text_set(_child(entry, "runner_kinds")),
                native_without_runner=_bool_field(
                    _child(entry, "native_without_runner"), default=False
                ),
                sort_order=_int_field(_child(entry, "sort_order"), default=100),
                backends=_build_backend_profile_families(_child(entry, "backends")),
                source=_source_span(entry.source),
            )
    return TargetFamilyCatalog(
        known_extension_families=frozenset(known),
        universal_extension_families=frozenset(universal),
        extension_families=extension_capabilities,
        profile_families=profiles,
    )


def _build_backend_profile_families(
    field: ParsedTslField | None,
) -> dict[str, BackendProfileFamily]:
    return {
        entry.key.text: BackendProfileFamily(
            feature_flags=_bool_field(
                _child(entry, "feature_flags"),
                default=True,
            ),
            target=_field_text(_child(entry, "target")),
            linker=_field_text(_child(entry, "linker")),
            detection=_field_text(_child(entry, "detection")),
            source=_source_span(entry.source),
        )
        for entry in _children(field)
    }


def _bool_field(field: ParsedTslField | None, *, default: bool) -> bool:
    text = _field_text(field)
    if text is None:
        return default
    return text.lower() == "true"


def _int_field(field: ParsedTslField | None, *, default: int) -> int:
    value = _opt_int(_field_text(field))
    return default if value is None else value
