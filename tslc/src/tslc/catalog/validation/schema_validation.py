"""Parsed-source schema validation for catalog declarations."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from tslc.catalog.validation.requires_validation import validate_requires
from tslc.catalog.validation.source_spans import (
    attribute_scalar_text,
    child,
    children,
    field_text,
    source_span,
)
from tslc.diagnostics import Diagnostic, diagnostic_at
from tslc.syntax.ast import (
    OuterTslParseResult,
    ParsedBlockDeclaration,
    ParsedPrimitiveDeclaration,
    ParsedTslAttribute,
    ParsedTslField,
)

_KNOWN_BACKENDS = frozenset({"cpp", "rust"})
_KNOWN_EXTENSION_FAMILIES = frozenset(
    {"scalar", "x86", "generic_like", "arm", "cuda", ""}
)
_KNOWN_MASK_POLICY_KINDS = frozenset(
    {"bool", "lane_bitmask", "native_predicate", "native_predicate_by_lanes"}
)
_KNOWN_IMASK_POLICY_KINDS = frozenset(
    {"lane_bitmask", "same_as_mask_type", "unsigned_scalar"}
)
_KNOWN_GENERIC_PARAM_KINDS = frozenset({"bool", "int", "simd_type"})
_KNOWN_IMMEDIATE_DISPATCH = frozenset({"literal_match"})
_KNOWN_PRIMITIVE_FIELDS = frozenset(
    {
        "brief_description",
        "generic_params",
        "impls",
        "operation",
        "param_types",
        "params",
        "return_type",
        "sImm_type",
        "tests",
    }
)
_KNOWN_PRIMITIVE_ATTRIBUTES = {
    "aligned": frozenset({"true", "false", "*"}),
    "arg_count": frozenset({"return_vector_length"}),
    "cast": frozenset({"reinterpret", "convert"}),
    "direction": frozenset({"up", "down"}),
    "mask": frozenset({"zero", "pass_through"}),
    "op": frozenset({"pack", "expand", "keep"}),
    "packed": frozenset({"true", "false", "*"}),
    "value": frozenset({"zero", "undef", "all"}),
}
_KNOWN_EXTENSION_FIELDS = frozenset(
    {
        "autodetect",
        "cpp",
        "default_test_target",
        "extension_name",
        "family",
        "inherits",
        "integral_mask_type_policy",
        "intrinsic_compose",
        "intrinsic_style",
        "lscpu_flags",
        "mask_repr",
        "mask_type_policy",
        "mask_vector_loadable",
        "mask_width",
        "native_sort_order",
        "runtime_lanes",
        "rust",
        "signature_support",
        "size_parameter",
        "test_filter",
        "test_sizes_bits",
        "vector_bits",
        "vector_register_type_policy",
        "vector_register_types",
        "vendor",
    }
)


def validate_parsed_documents(
    parsed: OuterTslParseResult,
    diagnostics: list[Diagnostic],
) -> None:
    type_group_fields: list[ParsedTslField] = []
    named_blocks: dict[tuple[str, str], ParsedBlockDeclaration] = {}

    for document in parsed.documents:
        for declaration in document.declarations:
            if isinstance(declaration, ParsedBlockDeclaration):
                _validate_named_block_duplicates(declaration, named_blocks, diagnostics)
                _validate_block(declaration, diagnostics)
                if declaration.kind == "types":
                    type_group_fields.extend(declaration.fields)
            elif isinstance(declaration, ParsedPrimitiveDeclaration):
                _validate_primitive(declaration, diagnostics)

    _diagnose_duplicate_fields(
        type_group_fields,
        diagnostics,
        code="TSL-CATALOG-DUPLICATE-TYPE-GROUP",
        label="type group",
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
) -> None:
    if declaration.kind == "extension":
        _validate_known_fields(
            declaration.fields,
            _KNOWN_EXTENSION_FIELDS,
            diagnostics,
            owner=f"extension {declaration.name or '<unnamed>'}",
        )
        _diagnose_duplicate_fields(declaration.fields, diagnostics, label="extension field")
        _validate_extension_block(declaration, diagnostics)
    elif declaration.kind == "types":
        for field in declaration.fields:
            _validate_known_fields(
                children(field),
                frozenset({"types"}),
                diagnostics,
                owner=f"type group {field.key.text!r}",
            )
            _diagnose_duplicate_fields(children(field), diagnostics, label="type-group field")
    elif declaration.kind == "language":
        _diagnose_duplicate_fields(declaration.fields, diagnostics, label="language type")
        for field in declaration.fields:
            _validate_known_fields(
                children(field),
                frozenset({"type"}),
                diagnostics,
                owner=f"language {declaration.name or '<unnamed>'} type {field.key.text!r}",
            )
            _diagnose_duplicate_fields(children(field), diagnostics, label="language type field")
    elif declaration.kind == "translation":
        _diagnose_duplicate_fields(declaration.fields, diagnostics, label="translation key")
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


def _validate_extension_block(
    declaration: ParsedBlockDeclaration,
    diagnostics: list[Diagnostic],
) -> None:
    fields = {field.key.text: field for field in declaration.fields}
    family = field_text(fields.get("family")) or ""
    if family not in _KNOWN_EXTENSION_FAMILIES:
        _invalid_enum(
            diagnostics,
            fields.get("family"),
            f"extension family {family!r}",
            sorted(_KNOWN_EXTENSION_FAMILIES - {""}),
        )

    mask = fields.get("mask_type_policy")
    _validate_policy_block(
        mask,
        frozenset({"kind", "width", "cpp_by_lanes", "rust_by_lanes", "cpp"}),
        _KNOWN_MASK_POLICY_KINDS,
        "mask_type_policy",
        diagnostics,
    )
    imask = fields.get("integral_mask_type_policy")
    _validate_policy_block(
        imask,
        frozenset({"kind", "width", "cpp", "rust"}),
        _KNOWN_IMASK_POLICY_KINDS,
        "integral_mask_type_policy",
        diagnostics,
    )

    compose = fields.get("intrinsic_compose")
    if compose is not None:
        _validate_known_fields(
            children(compose),
            frozenset({"prefix", "suffix"}),
            diagnostics,
            owner="intrinsic_compose",
        )
        prefix = child(compose, "prefix")
        if prefix is not None:
            _validate_backend_key_fields(children(prefix), diagnostics, owner="intrinsic prefix")
        suffix = child(compose, "suffix")
        if suffix is not None:
            _validate_known_fields(
                children(suffix),
                frozenset({"by_type"}),
                diagnostics,
                owner="intrinsic suffix",
            )


def _validate_policy_block(
    field: ParsedTslField | None,
    allowed_fields: frozenset[str],
    allowed_kinds: frozenset[str],
    owner: str,
    diagnostics: list[Diagnostic],
) -> None:
    if field is None:
        return
    _validate_known_fields(children(field), allowed_fields, diagnostics, owner=owner)
    _diagnose_duplicate_fields(children(field), diagnostics, label=f"{owner} field")
    kind_field = child(field, "kind")
    kind = field_text(kind_field)
    if kind is not None and kind not in allowed_kinds:
        _invalid_enum(diagnostics, kind_field, f"{owner} kind {kind!r}", sorted(allowed_kinds))


def _validate_primitive(
    declaration: ParsedPrimitiveDeclaration,
    diagnostics: list[Diagnostic],
) -> None:
    fields = tuple(field.field for field in declaration.fields)
    _validate_known_fields(
        fields,
        _KNOWN_PRIMITIVE_FIELDS,
        diagnostics,
        owner=f"primitive {declaration.name!r}",
    )
    _diagnose_duplicate_fields(fields, diagnostics, label="primitive field")
    _validate_attributes(declaration.attributes, diagnostics)
    _validate_generic_params(declaration, diagnostics)
    _validate_immediate_params(declaration, diagnostics)
    _validate_return_type(declaration, diagnostics)
    validate_requires(declaration, diagnostics)


def _validate_attributes(
    attributes: tuple[ParsedTslAttribute, ...],
    diagnostics: list[Diagnostic],
) -> None:
    seen: set[tuple[str, str | None]] = set()
    for attribute in attributes:
        key = attribute.key.text
        key_arg = attribute.key_argument.text if attribute.key_argument is not None else None
        identity = (key, key_arg)
        if identity in seen:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-DUPLICATE-ATTRIBUTE",
                    message=f"duplicate primitive attribute {key!r}",
                    source=source_span(attribute.source),
                )
            )
        seen.add(identity)
        allowed = _KNOWN_PRIMITIVE_ATTRIBUTES.get(key)
        if allowed is None:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-UNKNOWN-ATTRIBUTE",
                    message=f"unknown primitive attribute {key!r}",
                    source=source_span(attribute.source),
                )
            )
            continue
        value = attribute_scalar_text(attribute)
        if value is not None and value not in allowed:
            _invalid_enum(
                diagnostics,
                attribute,
                f"primitive attribute {key!r} value {value!r}",
                sorted(allowed),
            )


def _validate_generic_params(
    declaration: ParsedPrimitiveDeclaration,
    diagnostics: list[Diagnostic],
) -> None:
    for field in declaration.fields_by_name("generic_params"):
        _diagnose_duplicate_fields(children(field.field), diagnostics, label="generic parameter")
        for entry in children(field.field):
            _validate_known_fields(
                children(entry),
                frozenset({"kind", "default"}),
                diagnostics,
                owner=f"generic parameter {entry.key.text!r}",
            )
            kind_field = child(entry, "kind")
            kind = field_text(kind_field)
            if kind is not None and kind not in _KNOWN_GENERIC_PARAM_KINDS:
                _invalid_enum(
                    diagnostics,
                    kind_field,
                    f"generic parameter kind {kind!r}",
                    sorted(_KNOWN_GENERIC_PARAM_KINDS),
                )


def _validate_immediate_params(
    declaration: ParsedPrimitiveDeclaration,
    diagnostics: list[Diagnostic],
) -> None:
    for field in declaration.fields_by_name("params"):
        for entry in children(field.field):
            _validate_known_fields(
                children(entry),
                frozenset({"type", "value_range", "dispatch"}),
                diagnostics,
                owner=f"params entry {entry.key.text!r}",
            )
            dispatch = child(entry, "dispatch")
            for child_field in children(dispatch):
                if child_field.key.text not in _KNOWN_BACKENDS:
                    diagnostics.append(
                        diagnostic_at(
                            severity="error",
                            code="TSL-CATALOG-UNKNOWN-BACKEND",
                            message=f"dispatch backend {child_field.key.text!r} is not supported",
                            source=source_span(child_field.source),
                        )
                    )
                strategy = field_text(child_field)
                if strategy is not None and strategy not in _KNOWN_IMMEDIATE_DISPATCH:
                    _invalid_enum(
                        diagnostics,
                        child_field,
                        f"immediate dispatch strategy {strategy!r}",
                        sorted(_KNOWN_IMMEDIATE_DISPATCH),
                    )


def _validate_return_type(
    declaration: ParsedPrimitiveDeclaration,
    diagnostics: list[Diagnostic],
) -> None:
    for field in declaration.fields_by_name("return_type"):
        _validate_known_fields(
            children(field.field),
            frozenset({"base", "extension"}),
            diagnostics,
            owner="return_type",
        )


def _validate_known_fields(
    fields: Sequence[ParsedTslField],
    allowed: frozenset[str],
    diagnostics: list[Diagnostic],
    *,
    owner: str,
) -> None:
    for field in fields:
        if field.key.text not in allowed:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-UNKNOWN-FIELD",
                    message=f"unknown field {field.key.text!r} in {owner}",
                    source=source_span(field.source),
                )
            )


def _validate_backend_key_fields(
    fields: Sequence[ParsedTslField],
    diagnostics: list[Diagnostic],
    *,
    owner: str,
) -> None:
    for field in fields:
        if field.key.text not in _KNOWN_BACKENDS:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-UNKNOWN-BACKEND",
                    message=f"unknown backend field {field.key.text!r} in {owner}",
                    source=source_span(field.source),
                )
            )


def _diagnose_duplicate_fields(
    fields: Sequence[ParsedTslField],
    diagnostics: list[Diagnostic],
    *,
    label: str,
    code: str = "TSL-CATALOG-DUPLICATE-FIELD",
) -> None:
    counts = Counter(field.key.text for field in fields)
    seen: set[str] = set()
    for field in fields:
        key = field.key.text
        if counts[key] < 2:
            continue
        if key in seen:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code=code,
                    message=f"duplicate {label} {key!r}",
                    source=source_span(field.source),
                )
            )
        seen.add(key)


def _invalid_enum(
    diagnostics: list[Diagnostic],
    source: ParsedTslField | ParsedTslAttribute | None,
    value_label: str,
    allowed: Sequence[str],
) -> None:
    diagnostics.append(
        diagnostic_at(
            severity="error",
            code="TSL-CATALOG-INVALID-ENUM",
            message=f"invalid {value_label}; expected one of: {', '.join(allowed)}",
            source=(
                source_span(source.source)
                if source is not None
                else None
            ),
        )
    )
