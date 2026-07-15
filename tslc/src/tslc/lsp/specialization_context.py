"""Cursor scope and selectable specialization slots for editor commands."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import Catalog
from tslc.catalog.scalar_types import DEFAULT_SCALAR_TYPE_TAGS, SCALAR_TYPE_ORDER
from tslc.select.selector import Selector
from tslc.syntax.ast import (
    OuterTslParseResult,
    ParsedImplementationSelectorEntry,
    ParsedPrimitiveDeclaration,
    ParsedTslSourceSpan,
)


@dataclass(frozen=True, slots=True, order=True)
class SpecializationSlot:
    profile: str
    extension: str
    type_tag: str

    def payload(self) -> dict[str, str]:
        return {
            "profile": self.profile,
            "extension": self.extension,
            "type": self.type_tag,
        }


@dataclass(frozen=True, slots=True)
class SpecializationContext:
    primitive: str | None
    contextual_extensions: tuple[str, ...]
    contextual_types: tuple[str, ...]
    profiles: tuple[str, ...]
    slots: tuple[SpecializationSlot, ...]

    @property
    def extension(self) -> str | None:
        return (
            self.contextual_extensions[0]
            if len(self.contextual_extensions) == 1
            else None
        )

    @property
    def type_tag(self) -> str | None:
        return self.contextual_types[0] if len(self.contextual_types) == 1 else None

    def payload(self) -> dict[str, object]:
        return {
            "primitive": self.primitive,
            "extension": self.extension,
            "type": self.type_tag,
            "contextualExtensions": list(self.contextual_extensions),
            "contextualTypes": list(self.contextual_types),
            "profiles": list(self.profiles),
            "slots": [slot.payload() for slot in self.slots],
        }


def specialization_context(
    catalog: Catalog,
    parsed: OuterTslParseResult | None,
    profiles: Mapping[str, MachineProfile],
    *,
    backend: str,
    path: Path | None = None,
    line: int | None = None,
    column: int | None = None,
) -> SpecializationContext:
    """Return cursor facts and selector-valid slots without lowering or rendering."""

    profile_names = tuple(sorted(profiles))
    primitive, selector_path = _source_scope(parsed, path, line, column)
    if primitive is None:
        return SpecializationContext(None, (), (), profile_names, ())

    contextual_extensions = _contextual_extensions(catalog, selector_path)
    contextual_types = _contextual_types(catalog, primitive, selector_path)
    slots: set[SpecializationSlot] = set()
    selector = Selector()
    for profile_name in profile_names:
        selected = selector.select_profile(
            catalog,
            profiles[profile_name],
            primitive.name,
            DEFAULT_SCALAR_TYPE_TAGS,
            backend_id=backend,
        )
        slots.update(
            SpecializationSlot(
                profile=profile_name,
                extension=item.extension.isa_name,
                type_tag=item.type_tag,
            )
            for item in selected.selected
        )
    ordered = tuple(
        sorted(
            slots,
            key=lambda item: (
                item.profile,
                item.extension,
                SCALAR_TYPE_ORDER.get(item.type_tag, 999),
                item.type_tag,
            ),
        )
    )
    return SpecializationContext(
        primitive.name,
        contextual_extensions,
        contextual_types,
        profile_names,
        ordered,
    )


def _source_scope(
    parsed: OuterTslParseResult | None,
    path: Path | None,
    line: int | None,
    column: int | None,
) -> tuple[ParsedPrimitiveDeclaration | None, tuple[str, ...]]:
    if parsed is None or path is None or line is None or column is None:
        return None, ()
    selected_path = path.resolve()
    for document in parsed.documents:
        if document.path.resolve() != selected_path:
            continue
        for primitive in document.primitives:
            if _contains(primitive.source, line, column):
                return primitive, _selector_path_at(
                    primitive.impl_entries, line, column
                )
    return None, ()


def _selector_path_at(
    entries: tuple[ParsedImplementationSelectorEntry, ...],
    line: int,
    column: int,
    parent: tuple[str, ...] = (),
) -> tuple[str, ...]:
    for entry in entries:
        if not _contains(entry.source, line, column):
            continue
        current = (*parent, entry.selector.text)
        nested = _selector_path_at(entry.children, line, column, current)
        return nested or current
    return ()


def _contextual_extensions(
    catalog: Catalog, selector_path: tuple[str, ...]
) -> tuple[str, ...]:
    if not selector_path:
        return ()
    head = selector_path[0].strip()
    names = (
        tuple(item.strip() for item in head[1:-1].split(",") if item.strip())
        if head.startswith("[") and head.endswith("]")
        else (head,)
    )
    return tuple(
        sorted(
            {
                catalog.extensions[name].isa_name
                for name in names
                if name in catalog.extensions
            }
        )
    )


def _contextual_types(
    catalog: Catalog,
    primitive: ParsedPrimitiveDeclaration,
    selector_path: tuple[str, ...],
) -> tuple[str, ...]:
    if not selector_path:
        return ()
    groups = {
        implementation.type_group
        for variant in catalog.primitives_named(primitive.name, unmasked=False)
        if _same_source(variant.source, primitive.source)
        for implementation in variant.implementations
        if implementation.selector_path == selector_path
    }
    members = {
        member
        for group in groups
        for member in catalog.type_group_members(group)
        if member in SCALAR_TYPE_ORDER
    }
    return tuple(
        sorted(members, key=lambda item: (SCALAR_TYPE_ORDER[item], item))
    )


def _same_source(left: object, right: ParsedTslSourceSpan) -> bool:
    return bool(
        left is not None
        and getattr(left, "path", None) == right.path
        and getattr(left, "line", None) == right.line
        and getattr(left, "column", None) == right.column
    )


def _contains(span: ParsedTslSourceSpan, line: int, column: int) -> bool:
    position = (line, column)
    return (span.line, span.column) <= position < (span.end_line, span.end_column)


__all__ = (
    "SpecializationContext",
    "SpecializationSlot",
    "specialization_context",
)
