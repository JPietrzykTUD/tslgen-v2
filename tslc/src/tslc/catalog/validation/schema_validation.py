"""Parsed-source schema validation entry point.

This module owns document traversal and top-level block dispatch. Section-specific
schema rules live in focused private modules so new source sections can be added
without lengthening one mixed validator file.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping

from tslc.catalog.model import RESULT_DIMENSIONS
from tslc.catalog.signatures import parse_signature
from tslc.catalog.target_families import TargetFamilyCatalog
from tslc.catalog.validation._schema_common import (
    diagnose_duplicate_fields,
    is_non_empty_scalar_list,
    validate_known_fields,
)
from tslc.catalog.validation._schema_extensions import (
    known_extension_fields,
    validate_extension_block,
)
from tslc.catalog.validation._schema_primitives import validate_primitive
from tslc.catalog.validation._schema_overloads import validate_overload_axes
from tslc.catalog.validation._schema_target_families import validate_target_families
from tslc.syntax.access import child, children, source_span
from tslc.diagnostics import Diagnostic, RelatedLocation, diagnostic_at
from tslc.syntax.ast import (
    OuterTslParseResult,
    ParsedBlockDeclaration,
    ParsedFieldDeclaration,
    ParsedPrimitiveDeclaration,
    ParsedTslAttribute,
    ParsedTslField,
    ParsedTslScalarValue,
)


KNOWN_TYPE_GROUP_FIELDS = frozenset({"types"})
KNOWN_LANGUAGE_TYPE_FIELDS = frozenset({"type"})


def validate_parsed_documents(
    parsed: OuterTslParseResult,
    diagnostics: list[Diagnostic],
    target_families: TargetFamilyCatalog = TargetFamilyCatalog(),
    compiler_capabilities: Mapping[str, Collection[str]] | None = None,
) -> None:
    backend_ids = frozenset(
        declaration.name
        for document in parsed.documents
        for declaration in document.declarations
        if isinstance(declaration, ParsedBlockDeclaration)
        and declaration.kind == "language"
        and declaration.name
    )
    type_group_fields: list[ParsedTslField] = []
    named_blocks: dict[tuple[str, str], ParsedBlockDeclaration] = {}
    seen_primitives: dict[
        _PrimitiveCallableIdentity,
        dict[str | None, ParsedPrimitiveDeclaration],
    ] = {}
    overload_axis_fields: list[ParsedTslField] = []
    target_family_fields: list[ParsedTslField] = []

    for document in parsed.documents:
        for declaration in document.declarations:
            if isinstance(declaration, ParsedBlockDeclaration):
                _validate_named_block_duplicates(declaration, named_blocks, diagnostics)
                _validate_block(
                    declaration,
                    backend_ids,
                    diagnostics,
                    target_families,
                )
                if declaration.kind == "types":
                    type_group_fields.extend(declaration.fields)
            elif isinstance(declaration, ParsedPrimitiveDeclaration):
                _validate_duplicate_primitive(declaration, seen_primitives, diagnostics)
                validate_primitive(
                    declaration,
                    backend_ids,
                    diagnostics,
                    target_families.target_feature_names,
                    compiler_capabilities,
                )
            elif (
                isinstance(declaration, ParsedFieldDeclaration)
                and declaration.field.key.text == "target_families"
            ):
                target_family_fields.append(declaration.field)
                validate_target_families(declaration.field, backend_ids, diagnostics)
            elif (
                isinstance(declaration, ParsedFieldDeclaration)
                and declaration.field.key.text == "overload_axes"
            ):
                overload_axis_fields.append(declaration.field)
                validate_overload_axes(declaration.field, diagnostics)

    diagnose_duplicate_fields(
        type_group_fields,
        diagnostics,
        code="TSL-CATALOG-DUPLICATE-TYPE-GROUP",
        label="type group",
    )
    diagnose_duplicate_fields(
        overload_axis_fields,
        diagnostics,
        code="TSL-CATALOG-DUPLICATE-OVERLOAD-REGISTRY",
        label="overload_axes declaration",
    )
    diagnose_duplicate_fields(
        target_family_fields,
        diagnostics,
        code="TSL-CATALOG-DUPLICATE-TARGET-FAMILIES",
        label="target_families declaration",
    )


def _validate_named_block_duplicates(
    declaration: ParsedBlockDeclaration,
    seen: dict[tuple[str, str], ParsedBlockDeclaration],
    diagnostics: list[Diagnostic],
) -> None:
    if declaration.name is None or declaration.kind not in {
        "extension",
        "language",
        "translation",
    }:
        return
    key = (declaration.kind, declaration.name)
    first = seen.get(key)
    if first is None:
        seen[key] = declaration
        return
    first_span = source_span(first.source)
    diagnostics.append(
        diagnostic_at(
            severity="error",
            code="TSL-CATALOG-DUPLICATE-BLOCK",
            message=(
                f"duplicate {declaration.kind} block {declaration.name!r}; "
                f"first definition is at {first.source.path}:{first.source.line}"
            ),
            source=source_span(declaration.source),
            related=(
                ()
                if first_span is None
                else (
                    RelatedLocation(
                        message="first definition is here",
                        span=first_span,
                    ),
                )
            ),
        )
    )


# The public-callable identity of one primitive declaration. Distinct signatures are
# legal overloads (`store(ptr, v)` vs `store(ptr, s)`); distinct attribute values are
# legal variants (masking, `[aligned=true]` vs `[aligned=false]`). A callable may have
# one base-target and one extension-target declaration, but an ordinary declaration
# cannot coexist with either target-axis form. Wildcards stay unexpanded, so two
# `[aligned=*]` declarations of one callable and target dimension collide.
type _PrimitiveCallableIdentity = tuple[
    str,
    tuple[str, tuple[str, ...]] | str,
    tuple[tuple[str, str, str], ...],
]


def _primitive_identity(
    declaration: ParsedPrimitiveDeclaration,
) -> _PrimitiveCallableIdentity:
    shape = parse_signature(declaration.signature)
    overload: tuple[str, tuple[str, ...]] | str = (
        (shape.result_kind, shape.param_kinds)
        if shape is not None
        else declaration.signature.replace(" ", "")
    )
    return (
        declaration.name,
        overload,
        tuple(sorted(_attribute_identity(item) for item in declaration.attributes)),
    )


def _return_type_dimension(
    declaration: ParsedPrimitiveDeclaration,
) -> str | None:
    for parsed in declaration.fields_by_name("return_type"):
        for field in children(parsed.field):
            if field.key.text in RESULT_DIMENSIONS:
                return field.key.text
    return None


def _attribute_identity(attribute: ParsedTslAttribute) -> tuple[str, str, str]:
    value = attribute.value
    return (
        attribute.key.text,
        attribute.key_argument.text if attribute.key_argument is not None else "",
        value.text
        if isinstance(value, ParsedTslScalarValue)
        else value.source.text.strip(),
    )


def _validate_duplicate_primitive(
    declaration: ParsedPrimitiveDeclaration,
    seen: dict[
        _PrimitiveCallableIdentity,
        dict[str | None, ParsedPrimitiveDeclaration],
    ],
    diagnostics: list[Diagnostic],
) -> None:
    key = _primitive_identity(declaration)
    dimension = _return_type_dimension(declaration)
    declarations = seen.setdefault(key, {})
    first = declarations.get(dimension)
    conflicting_forms = False
    if first is None and dimension is None and declarations:
        first = next(iter(declarations.values()))
        conflicting_forms = True
    elif first is None and dimension is not None and None in declarations:
        first = declarations[None]
        conflicting_forms = True
    if first is None:
        declarations[dimension] = declaration
        return
    first_span = source_span(first.header_source)
    message = (
        f"ordinary and target-axis forms of primitive {declaration.name!r} cannot"
        " share one public callable"
        if conflicting_forms
        else (
            f"duplicate declaration of primitive {declaration.name!r} with the"
            " same signature, attributes, and target dimension"
        )
    )
    diagnostics.append(
        diagnostic_at(
            severity="error",
            code="TSL-CATALOG-DUPLICATE-PRIMITIVE",
            message=(
                f"{message}; first declaration is at"
                f" {first.header_source.path}:{first.header_source.line}"
            ),
            source=source_span(declaration.header_source),
            related=(
                ()
                if first_span is None
                else (
                    RelatedLocation(
                        message="first declaration is here",
                        span=first_span,
                    ),
                )
            ),
        )
    )


def _validate_block(
    declaration: ParsedBlockDeclaration,
    backend_ids: frozenset[str],
    diagnostics: list[Diagnostic],
    target_families: TargetFamilyCatalog,
) -> None:
    if declaration.kind == "extension":
        validate_known_fields(
            declaration.fields,
            known_extension_fields(backend_ids),
            diagnostics,
            owner=f"extension {declaration.name or '<unnamed>'}",
        )
        diagnose_duplicate_fields(declaration.fields, diagnostics, label="extension field")
        validate_extension_block(
            declaration,
            backend_ids,
            diagnostics,
            target_families,
        )
    elif declaration.kind == "types":
        for field in declaration.fields:
            validate_known_fields(
                children(field),
                KNOWN_TYPE_GROUP_FIELDS,
                diagnostics,
                owner=f"type group {field.key.text!r}",
            )
            diagnose_duplicate_fields(children(field), diagnostics, label="type-group field")
            types_field = child(field, "types")
            if types_field is None or not is_non_empty_scalar_list(types_field):
                diagnostics.append(
                    diagnostic_at(
                        severity="error",
                        code="TSL-CATALOG-TYPE-GROUP-MALFORMED",
                        message=(
                            f"type group {field.key.text!r} must declare a"
                            " non-empty `types` list of scalar type tags"
                        ),
                        source=source_span(field.source),
                    )
                )
    elif declaration.kind == "language":
        diagnose_duplicate_fields(declaration.fields, diagnostics, label="language type")
        for field in declaration.fields:
            validate_known_fields(
                children(field),
                KNOWN_LANGUAGE_TYPE_FIELDS,
                diagnostics,
                owner=f"language {declaration.name or '<unnamed>'} type {field.key.text!r}",
            )
            diagnose_duplicate_fields(children(field), diagnostics, label="language type field")
    elif declaration.kind == "translation":
        diagnose_duplicate_fields(declaration.fields, diagnostics, label="translation key")
    elif declaration.kind in {"flags", "lane_set", "template"}:
        return
    else:
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-UNKNOWN-BLOCK",
                message=f"unsupported top-level block kind {declaration.kind!r}",
                source=source_span(declaration.source),
            )
        )


__all__ = ["validate_parsed_documents"]
