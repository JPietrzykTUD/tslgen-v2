"""Catalog-level validation rules over promoted domain objects."""

from __future__ import annotations

from collections.abc import Sequence

from tslc.catalog.model import Catalog
from tslc.catalog.scalar_types import KNOWN_SCALAR_TYPE_TAGS, normalize_scalar_tag
from tslc.catalog.signatures import (
    LANE_LIST_KIND,
    SignatureShape,
    SignatureTerm,
    parse_signature,
)
from tslc.syntax.access import (
    child,
    child_from_sequence,
    source_span,
)
from tslc.diagnostics import Diagnostic, RelatedLocation, SourceSpan, diagnostic_at
from tslc.syntax.ast import (
    OuterTslParseResult,
    ParsedBlockDeclaration,
    ParsedTslListValue,
    ParsedTslScalarValue,
)
from tslc.support_policy import DEFAULT_SUPPORT_POLICY


def validate_required_backends(
    catalog: Catalog,
    required_backends: Sequence[str],
    supported_backends: Sequence[str],
    diagnostics: list[Diagnostic],
) -> None:
    supported = frozenset(supported_backends)
    for backend in required_backends:
        if backend not in supported:
            expected = " or ".join(sorted(supported))
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-CATALOG-UNKNOWN-BACKEND",
                    message=(
                        f"backend {backend!r} is not supported "
                        f"(expected {expected})"
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
    supported_backends: Sequence[str],
    diagnostics: list[Diagnostic],
    parsed: OuterTslParseResult | None,
) -> None:
    type_sources = _type_member_sources(parsed) if parsed is not None else {}
    type_tags = _catalog_type_tags(catalog)
    supported = frozenset(supported_backends)
    for backend in required_backends:
        if backend not in supported or backend not in catalog.type_spellings:
            continue
        spellings = catalog.type_spellings.get(backend, {})
        for type_tag in type_tags:
            key = normalize_scalar_tag(type_tag)
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


def validate_primitive_signatures(
    catalog: Catalog,
    diagnostics: list[Diagnostic],
) -> None:
    for primitive in catalog.primitives:
        shape = parse_signature(primitive.signature)
        source = primitive.signature_source
        if shape is None:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-BAD-SIGNATURE",
                    message=(
                        f"primitive {primitive.name!r} has malformed signature "
                        f"{primitive.signature!r}"
                    ),
                    source=source,
                )
            )
            continue
        _validate_lane_list_signature_terms(primitive.name, shape, diagnostics, source)


def validate_generic_param_base_constraints(
    catalog: Catalog,
    diagnostics: list[Diagnostic],
) -> None:
    for primitive in catalog.primitives:
        for generic_param in primitive.generic_params:
            if not generic_param.base_type_constraints:
                continue
            for constraint in generic_param.base_type_constraints:
                members = catalog.type_group_members(constraint)
                invalid = tuple(
                    member for member in members if member not in KNOWN_SCALAR_TYPE_TAGS
                )
                if not members or invalid:
                    diagnostics.append(
                        diagnostic_at(
                            severity="error",
                            code="TSL-CATALOG-SIMD-TYPE-CONSTRAINT",
                            message=(
                                f"primitive {primitive.name!r} generic parameter "
                                f"{generic_param.name!r} has invalid base_types entry "
                                f"{constraint!r}; expected scalar type tags or type groups"
                            ),
                            source=generic_param.source,
                        )
                    )


def _validate_lane_list_signature_terms(
    primitive_name: str,
    shape: SignatureShape,
    diagnostics: list[Diagnostic],
    source: SourceSpan | None,
) -> None:
    if shape.result_term.is_lane_list_like:
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-LANE-LIST-RESULT",
                message=(
                    f"primitive {primitive_name!r} uses lane-list result term "
                    f"{shape.result_kind!r}; lane lists are supported only as parameters"
                ),
                source=source,
            )
        )
    for term in shape.param_terms:
        _validate_lane_list_param_term(primitive_name, term, diagnostics, source)


def _validate_lane_list_param_term(
    primitive_name: str,
    term: SignatureTerm,
    diagnostics: list[Diagnostic],
    source: SourceSpan | None,
) -> None:
    if not term.is_lane_list_like:
        return
    if not term.is_lane_list:
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-LANE-LIST-MALFORMED",
                message=(
                    f"primitive {primitive_name!r} has malformed lane-list term "
                    f"{term.kind!r}; expected {LANE_LIST_KIND!r}"
                ),
                source=source,
            )
        )
        return
    element = term.lane_element_kind or ""
    if not element:
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-LANE-LIST-EMPTY",
                message=(
                    f"primitive {primitive_name!r} has empty lane-list term "
                    f"{term.kind!r}; expected {LANE_LIST_KIND!r}"
                ),
                source=source,
            )
        )
        return
    if element.startswith("lanes"):
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-LANE-LIST-NESTED",
                message=(
                    f"primitive {primitive_name!r} has nested lane-list term "
                    f"{term.kind!r}; nested lane lists are not supported"
                ),
                source=source,
            )
        )
        return
    if term.kind != LANE_LIST_KIND:
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-LANE-LIST-ELEMENT",
                message=(
                    f"primitive {primitive_name!r} has lane-list term {term.kind!r}; "
                    f"only {LANE_LIST_KIND!r} is supported"
                ),
                source=source,
            )
        )


def validate_extension_inheritance(
    catalog: Catalog,
    diagnostics: list[Diagnostic],
    parsed: OuterTslParseResult | None,
) -> None:
    inherit_sources = _inherit_sources(parsed) if parsed is not None else {}
    supersedes_sources = (
        _extension_field_sources(parsed, "supersedes") if parsed is not None else {}
    )
    for name, extension in catalog.extensions.items():
        parent = extension.inherits
        if parent is not None and parent not in catalog.extensions:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-UNKNOWN-INHERITS",
                    message=f"extension {name!r} inherits unknown extension {parent!r}",
                    source=inherit_sources.get(name),
                )
            )
        for superseded in sorted(extension.supersedes):
            if superseded not in catalog.extensions:
                diagnostics.append(
                    diagnostic_at(
                        severity="error",
                        code="TSL-CATALOG-UNKNOWN-SUPERSEDES",
                        message=(
                            f"extension {name!r} supersedes unknown extension "
                            f"{superseded!r}"
                        ),
                        source=supersedes_sources.get(name),
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
                            related=tuple(
                                RelatedLocation(
                                    message=f"inheritance edge from {member!r}",
                                    span=span,
                                )
                                for member in cycle[:-1]
                                if member != current
                                if (span := inherit_sources.get(member)) is not None
                            ),
                        )
                    )
                break
            chain.append(current)
            current = catalog.extensions[current].inherits


def validate_scalable_runtime_lane_counts(
    catalog: Catalog,
    required_backends: Sequence[str],
    diagnostics: list[Diagnostic],
    parsed: OuterTslParseResult | None,
) -> None:
    extension_sources = _extension_sources(parsed)
    for name, extension in sorted(catalog.extensions.items()):
        if not DEFAULT_SUPPORT_POLICY.uses_scalable_vector(extension):
            continue
        for backend in required_backends:
            if not extension.supports_backend(backend):
                continue
            if backend in extension.runtime_lane_count:
                continue
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-MISSING-RUNTIME-LANE-COUNT",
                    message=(
                        f"scalable extension {name!r} supports backend {backend!r} "
                        f"but has no runtime_lane_count entry for backend {backend!r}"
                    ),
                    source=extension_sources.get(name),
                )
            )


def _catalog_type_tags(catalog: Catalog) -> tuple[str, ...]:
    tags: set[str] = set()
    for members in catalog.type_groups.values():
        tags.update(member for member in members if member in KNOWN_SCALAR_TYPE_TAGS)
    for primitive in catalog.primitives:
        for implementation in primitive.implementations:
            tags.update(
                member
                for member in catalog.type_group_members(implementation.type_group)
                if member in KNOWN_SCALAR_TYPE_TAGS
            )
            if implementation.to_target_group is not None:
                tags.update(
                    member
                    for member in catalog.type_group_members(implementation.to_target_group)
                    if member in KNOWN_SCALAR_TYPE_TAGS
                )
    return tuple(sorted(tags))


def _type_member_sources(
    parsed: OuterTslParseResult,
) -> dict[str, SourceSpan | None]:
    sources: dict[str, SourceSpan | None] = {}
    for document in parsed.documents:
        for declaration in document.declarations:
            if not isinstance(declaration, ParsedBlockDeclaration) or declaration.kind != "types":
                continue
            for group in declaration.fields:
                types = child(group, "types")
                if types is None or not isinstance(types.value, ParsedTslListValue):
                    continue
                for item in types.value.items:
                    if (
                        isinstance(item, ParsedTslScalarValue)
                        and item.text in KNOWN_SCALAR_TYPE_TAGS
                    ):
                        sources.setdefault(item.text, source_span(item.source))
    return sources


def _inherit_sources(
    parsed: OuterTslParseResult | None,
) -> dict[str, SourceSpan | None]:
    return _extension_field_sources(parsed, "inherits")


def _extension_field_sources(
    parsed: OuterTslParseResult | None,
    field_name: str,
) -> dict[str, SourceSpan | None]:
    if parsed is None:
        return {}
    sources: dict[str, SourceSpan | None] = {}
    for document in parsed.documents:
        for declaration in document.declarations:
            if not isinstance(declaration, ParsedBlockDeclaration) or declaration.kind != "extension":
                continue
            field = child_from_sequence(declaration.fields, field_name)
            if declaration.name is not None and field is not None:
                sources[declaration.name] = source_span(field.source)
    return sources


def _extension_sources(
    parsed: OuterTslParseResult | None,
) -> dict[str, SourceSpan | None]:
    if parsed is None:
        return {}
    sources: dict[str, SourceSpan | None] = {}
    for document in parsed.documents:
        for declaration in document.declarations:
            if not isinstance(declaration, ParsedBlockDeclaration) or declaration.kind != "extension":
                continue
            if declaration.name is not None:
                sources[declaration.name] = source_span(declaration.source)
    return sources
