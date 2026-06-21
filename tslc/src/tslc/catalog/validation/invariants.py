"""Catalog-level validation rules over promoted domain objects."""

from __future__ import annotations

from collections.abc import Sequence

from tslc.catalog.model import Catalog
from tslc.catalog.validation.source_spans import (
    child,
    child_from_sequence,
    source_span,
)
from tslc.diagnostics import Diagnostic, SourceSpan, diagnostic_at
from tslc.syntax.ast import (
    OuterTslParseResult,
    ParsedBlockDeclaration,
    ParsedTslListValue,
    ParsedTslScalarValue,
)
from tslc.support_policy import DEFAULT_SUPPORT_POLICY

_KNOWN_TYPE_TAGS = frozenset(
    {"si8", "si16", "si32", "si64", "ui8", "ui16", "ui32", "ui64", "f32", "f64"}
)


def validate_required_backends(
    catalog: Catalog,
    required_backends: Sequence[str],
    diagnostics: list[Diagnostic],
) -> None:
    for backend in required_backends:
        if not DEFAULT_SUPPORT_POLICY.supports_backend(backend):
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-CATALOG-UNKNOWN-BACKEND",
                    message=(
                        f"backend {backend!r} is not supported "
                        f"(expected {DEFAULT_SUPPORT_POLICY.backend_label()})"
                    ),
                )
            )
        elif backend not in catalog.type_spellings:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-CATALOG-MISSING-BACKEND-SPELLINGS",
                    message=f"catalog has no type spellings for backend {backend!r}",
                )
            )


def validate_backend_type_spellings(
    catalog: Catalog,
    required_backends: Sequence[str],
    diagnostics: list[Diagnostic],
    parsed: OuterTslParseResult | None,
) -> None:
    type_sources = _type_member_sources(parsed) if parsed is not None else {}
    type_tags = _catalog_type_tags(catalog)
    for backend in required_backends:
        if (
            not DEFAULT_SUPPORT_POLICY.supports_backend(backend)
            or backend not in catalog.type_spellings
        ):
            continue
        spellings = catalog.type_spellings.get(backend, {})
        for type_tag in type_tags:
            key = _normalize_scalar_tag(type_tag)
            if key not in spellings:
                diagnostics.append(
                    diagnostic_at(
                        severity="error",
                        code="TSL-CATALOG-MISSING-TYPE-SPELLING",
                        message=(
                            f"backend {backend!r} has no scalar spelling for "
                            f"type tag {type_tag!r} (expected language key {key!r})"
                        ),
                        source=type_sources.get(type_tag),
                    )
                )


def validate_extension_inheritance(
    catalog: Catalog,
    diagnostics: list[Diagnostic],
    parsed: OuterTslParseResult | None,
) -> None:
    inherit_sources = _inherit_sources(parsed) if parsed is not None else {}
    for name, extension in catalog.extensions.items():
        parent = extension.inherits
        if parent is None:
            continue
        if parent not in catalog.extensions:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-UNKNOWN-INHERITS",
                    message=f"extension {name!r} inherits unknown extension {parent!r}",
                    source=inherit_sources.get(name),
                )
            )

    reported_cycles: set[tuple[str, ...]] = set()
    for name in catalog.extensions:
        chain: list[str] = []
        current: str | None = name
        while current is not None and current in catalog.extensions:
            if current in chain:
                cycle = tuple(chain[chain.index(current) :] + [current])
                key = tuple(sorted(cycle))
                if key not in reported_cycles:
                    reported_cycles.add(key)
                    diagnostics.append(
                        diagnostic_at(
                            severity="error",
                            code="TSL-CATALOG-INHERITS-CYCLE",
                            message=(
                                "extension inheritance cycle: "
                                + " -> ".join(cycle)
                            ),
                            source=inherit_sources.get(current),
                        )
                    )
                break
            chain.append(current)
            current = catalog.extensions[current].inherits


def _catalog_type_tags(catalog: Catalog) -> tuple[str, ...]:
    tags: set[str] = set()
    for members in catalog.type_groups.values():
        tags.update(member for member in members if member in _KNOWN_TYPE_TAGS)
    for primitive in catalog.primitives:
        for implementation in primitive.implementations:
            tags.update(
                member
                for member in catalog.type_group_members(implementation.type_group)
                if member in _KNOWN_TYPE_TAGS
            )
            if implementation.to_target_group is not None:
                tags.update(
                    member
                    for member in catalog.type_group_members(implementation.to_target_group)
                    if member in _KNOWN_TYPE_TAGS
                )
    return tuple(sorted(tags))


def _type_member_sources(
    parsed: OuterTslParseResult,
) -> dict[str, SourceSpan]:
    sources: dict[str, SourceSpan] = {}
    for document in parsed.documents:
        for declaration in document.declarations:
            if not isinstance(declaration, ParsedBlockDeclaration) or declaration.kind != "types":
                continue
            for group in declaration.fields:
                types = child(group, "types")
                if types is None or not isinstance(types.value, ParsedTslListValue):
                    continue
                for item in types.value.items:
                    if isinstance(item, ParsedTslScalarValue) and item.text in _KNOWN_TYPE_TAGS:
                        sources.setdefault(item.text, source_span(item.source))
    return sources


def _inherit_sources(parsed: OuterTslParseResult | None) -> dict[str, SourceSpan]:
    if parsed is None:
        return {}
    sources: dict[str, SourceSpan] = {}
    for document in parsed.documents:
        for declaration in document.declarations:
            if not isinstance(declaration, ParsedBlockDeclaration) or declaration.kind != "extension":
                continue
            inherit = child_from_sequence(declaration.fields, "inherits")
            if declaration.name is not None and inherit is not None:
                sources[declaration.name] = source_span(inherit.source)
    return sources


def _normalize_scalar_tag(type_tag: str) -> str:
    if type_tag.startswith("si") and type_tag[2:].isdigit():
        return "s" + type_tag[2:]
    if type_tag.startswith("ui") and type_tag[2:].isdigit():
        return "u" + type_tag[2:]
    return type_tag
