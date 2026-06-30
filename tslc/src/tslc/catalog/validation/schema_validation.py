"""Parsed-source schema validation entry point.

This module owns document traversal and top-level block dispatch. Section-specific
schema rules live in focused private modules so new source sections can be added
without lengthening one mixed validator file.
"""

from __future__ import annotations

from tslc.catalog.target_families import TargetFamilyCatalog
from tslc.catalog.validation._schema_common import (
    diagnose_duplicate_fields,
    validate_known_fields,
)
from tslc.catalog.validation._schema_extensions import (
    known_extension_fields,
    validate_extension_block,
)
from tslc.catalog.validation._schema_primitives import validate_primitive
from tslc.catalog.validation._schema_target_families import validate_target_families
from tslc.catalog.validation.source_spans import children, source_span
from tslc.diagnostics import Diagnostic, diagnostic_at
from tslc.syntax.ast import (
    OuterTslParseResult,
    ParsedBlockDeclaration,
    ParsedFieldDeclaration,
    ParsedPrimitiveDeclaration,
    ParsedTslField,
)


def validate_parsed_documents(
    parsed: OuterTslParseResult,
    diagnostics: list[Diagnostic],
    target_families: TargetFamilyCatalog = TargetFamilyCatalog(),
) -> None:
    type_group_fields: list[ParsedTslField] = []
    named_blocks: dict[tuple[str, str], ParsedBlockDeclaration] = {}
    target_family_fields: list[ParsedTslField] = []

    for document in parsed.documents:
        for declaration in document.declarations:
            if isinstance(declaration, ParsedBlockDeclaration):
                _validate_named_block_duplicates(declaration, named_blocks, diagnostics)
                _validate_block(declaration, diagnostics, target_families)
                if declaration.kind == "types":
                    type_group_fields.extend(declaration.fields)
            elif isinstance(declaration, ParsedPrimitiveDeclaration):
                validate_primitive(declaration, diagnostics)
            elif (
                isinstance(declaration, ParsedFieldDeclaration)
                and declaration.field.key.text == "target_families"
            ):
                target_family_fields.append(declaration.field)
                validate_target_families(declaration.field, diagnostics)

    diagnose_duplicate_fields(
        type_group_fields,
        diagnostics,
        code="TSL-CATALOG-DUPLICATE-TYPE-GROUP",
        label="type group",
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
    diagnostics.append(
        diagnostic_at(
            severity="error",
            code="TSL-CATALOG-DUPLICATE-BLOCK",
            message=(
                f"duplicate {declaration.kind} block {declaration.name!r}; "
                f"first definition is at {first.source.path}:{first.source.line}"
            ),
            source=source_span(declaration.source),
        )
    )


def _validate_block(
    declaration: ParsedBlockDeclaration,
    diagnostics: list[Diagnostic],
    target_families: TargetFamilyCatalog,
) -> None:
    if declaration.kind == "extension":
        validate_known_fields(
            declaration.fields,
            known_extension_fields(),
            diagnostics,
            owner=f"extension {declaration.name or '<unnamed>'}",
        )
        diagnose_duplicate_fields(declaration.fields, diagnostics, label="extension field")
        validate_extension_block(declaration, diagnostics, target_families)
    elif declaration.kind == "types":
        for field in declaration.fields:
            validate_known_fields(
                children(field),
                frozenset({"types"}),
                diagnostics,
                owner=f"type group {field.key.text!r}",
            )
            diagnose_duplicate_fields(children(field), diagnostics, label="type-group field")
    elif declaration.kind == "language":
        diagnose_duplicate_fields(declaration.fields, diagnostics, label="language type")
        for field in declaration.fields:
            validate_known_fields(
                children(field),
                frozenset({"type"}),
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
