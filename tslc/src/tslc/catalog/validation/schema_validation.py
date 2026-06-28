"""Parsed-source schema validation for catalog declarations."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
import re

from tslc.catalog.validation.requires_validation import validate_requires
from tslc.catalog.validation.source_spans import (
    attribute_scalar_text,
    child,
    children,
    field_text,
    source_span,
)
from tslc.diagnostics import Diagnostic, diagnostic_at
from tslc.catalog.target_families import TargetFamilyCatalog
from tslc.syntax.ast import (
    OuterTslParseResult,
    ParsedBlockDeclaration,
    ParsedFieldDeclaration,
    ParsedImplementationSelectorEntry,
    ParsedPrimitiveDeclaration,
    ParsedTslAttribute,
    ParsedTslField,
    ParsedTslListValue,
    ParsedTslMapValue,
    ParsedTslScalarValue,
)
from tslc.support_policy import DEFAULT_SUPPORT_POLICY
_KNOWN_MASK_POLICY_KINDS = frozenset(
    {"bool", "lane_bitmask", "native_predicate", "native_predicate_by_lanes"}
)
_KNOWN_IMASK_POLICY_KINDS = frozenset(
    {"lane_bitmask", "same_as_mask_type", "unsigned_scalar"}
)
_KNOWN_GENERIC_PARAM_KINDS = frozenset({"bool", "int", "simd_type"})
_KNOWN_IMMEDIATE_DISPATCH = frozenset({"literal_match"})
_KNOWN_SAFETY_FIELDS = frozenset({"internal_unsafe", "caller_unsafe", "reasons"})
_KNOWN_BOOLEAN_VALUES = frozenset({"true", "false"})
_KNOWN_PRIMITIVE_FIELDS = frozenset(
    {
        "brief_description",
        "cross_lane",
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
_PARAM_TYPE_CONDITION_RE = re.compile(r"^if\s+([A-Za-z_][A-Za-z0-9_]*)=([A-Za-z0-9_]+)$")
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
        "size_bits",
        "size_parameter",
        "test_filter",
        "test_mask_check",
        "test_mask_from_bits",
        "test_runtime_lanes",
        "test_support_headers",
        "test_sizes_bits",
        "unroll_variants",
        "vector_bits",
        "vector_register_type_policy",
        "vector_register_types",
        "vendor",
    }
)
_KNOWN_TARGET_FAMILIES_FIELDS = frozenset(
    {"known_extension_families", "universal_extension_families", "profile_families"}
)
_KNOWN_PROFILE_FAMILY_FIELDS = frozenset({"extension_families", "emulator_kinds"})


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
                _validate_primitive(declaration, diagnostics)
            elif (
                isinstance(declaration, ParsedFieldDeclaration)
                and declaration.field.key.text == "target_families"
            ):
                target_family_fields.append(declaration.field)
                _validate_target_families(declaration.field, diagnostics)

    _diagnose_duplicate_fields(
        type_group_fields,
        diagnostics,
        code="TSL-CATALOG-DUPLICATE-TYPE-GROUP",
        label="type group",
    )
    _diagnose_duplicate_fields(
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
        _validate_known_fields(
            declaration.fields,
            _KNOWN_EXTENSION_FIELDS,
            diagnostics,
            owner=f"extension {declaration.name or '<unnamed>'}",
        )
        _diagnose_duplicate_fields(declaration.fields, diagnostics, label="extension field")
        _validate_extension_block(declaration, diagnostics, target_families)
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


def _validate_target_families(
    field: ParsedTslField,
    diagnostics: list[Diagnostic],
) -> None:
    target_fields = children(field)
    _validate_known_fields(
        target_fields,
        _KNOWN_TARGET_FAMILIES_FIELDS,
        diagnostics,
        owner="target_families",
    )
    _diagnose_duplicate_fields(target_fields, diagnostics, label="target_families field")
    for list_name in ("known_extension_families", "universal_extension_families"):
        list_field = child(field, list_name)
        if list_field is not None and not _is_scalar_list(list_field):
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-TARGET-FAMILIES-MALFORMED-LIST",
                    message=f"target_families {list_name!r} must be a scalar list",
                    source=source_span(list_field.source),
                )
            )

    profiles = child(field, "profile_families")
    _diagnose_duplicate_fields(
        children(profiles),
        diagnostics,
        label="profile family",
    )
    for profile in children(profiles):
        _validate_known_fields(
            children(profile),
            _KNOWN_PROFILE_FAMILY_FIELDS,
            diagnostics,
            owner=f"profile family {profile.key.text!r}",
        )
        _diagnose_duplicate_fields(
            children(profile),
            diagnostics,
            label=f"profile family {profile.key.text!r} field",
        )
        for list_name in ("extension_families", "emulator_kinds"):
            list_field = child(profile, list_name)
            if list_field is not None and not _is_scalar_list(list_field):
                diagnostics.append(
                    diagnostic_at(
                        severity="error",
                        code="TSL-CATALOG-TARGET-FAMILIES-MALFORMED-LIST",
                        message=(
                            f"profile family {profile.key.text!r} {list_name!r} "
                            "must be a scalar list"
                        ),
                        source=source_span(list_field.source),
                    )
                )


def _validate_extension_block(
    declaration: ParsedBlockDeclaration,
    diagnostics: list[Diagnostic],
    target_families: TargetFamilyCatalog,
) -> None:
    fields = {field.key.text: field for field in declaration.fields}
    family = field_text(fields.get("family")) or ""
    if (
        family
        and target_families.known_extension_families
        and family not in target_families.known_extension_families
    ):
        _invalid_enum(
            diagnostics,
            fields.get("family"),
            f"extension family {family!r}",
            sorted(target_families.known_extension_families),
        )

    mask = fields.get("mask_type_policy")
    _validate_policy_block(
        mask,
        frozenset({"kind", "width", "cpp_by_lanes", "rust_by_lanes", "cpp", "rust"}),
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
    for backend_map_name in (
        "test_runtime_lanes",
        "test_mask_from_bits",
        "test_mask_check",
        "test_support_headers",
    ):
        backend_map = fields.get(backend_map_name)
        if backend_map is not None:
            _diagnose_duplicate_fields(
                children(backend_map),
                diagnostics,
                label=f"{backend_map_name} backend field",
            )
            _validate_backend_key_fields(
                children(backend_map),
                diagnostics,
                owner=backend_map_name,
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
    for cross_lane_field in declaration.fields_by_name("cross_lane"):
        value = field_text(cross_lane_field.field)
        if value not in _KNOWN_BOOLEAN_VALUES:
            _invalid_enum(
                diagnostics,
                cross_lane_field.field,
                f"primitive {declaration.name!r} cross_lane value {value!r}",
                sorted(_KNOWN_BOOLEAN_VALUES),
            )
    _validate_attributes(declaration.attributes, diagnostics)
    _validate_generic_params(declaration, diagnostics)
    _validate_immediate_params(declaration, diagnostics)
    _validate_param_types(declaration, diagnostics)
    _validate_implementation_safety(declaration, diagnostics)
    _validate_return_type(declaration, diagnostics)
    _validate_tests(declaration, diagnostics)
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


_KNOWN_TEST_FIELDS = frozenset(
    {
        "id",
        "tags",
        "type",
        "role",
        "lane_count",
        "extension",
        "expected_rule",
        "to_type",
        "to_extension",
        "index",
        "offset",
        "src_offset",
        "dst_offset",
        "scale",
        "alignment",
        "attrs",
        "case",
    }
)
_REQUIRED_TEST_FIELDS = ("tags", "type", "case")
_KNOWN_TEST_ROLES = frozenset({"value", "compile"})


def _validate_tests(
    declaration: ParsedPrimitiveDeclaration,
    diagnostics: list[Diagnostic],
) -> None:
    """Validate the internal structure of a `tests:` block.

    Structural problems (wrong shape, unknown/missing keys, non-positive ``lane_count``) are
    errors. Lane-count inference happens during catalog promotion, where test facts have typed
    inputs and expected values."""

    for field in declaration.fields_by_name("tests"):
        value = field.field.value
        if not isinstance(value, ParsedTslListValue):
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-TESTS-NOT-LIST",
                    message=f"primitive {declaration.name!r}: `tests` must be a list of cases",
                    source=source_span(field.field.source),
                )
            )
            continue
        for item in value.items:
            if not isinstance(item, ParsedTslMapValue):
                diagnostics.append(
                    diagnostic_at(
                        severity="error",
                        code="TSL-CATALOG-TEST-NOT-MAP",
                        message=f"primitive {declaration.name!r}: each test case must be a `{{...}}` map",
                        source=source_span(item.source),
                    )
                )
                continue
            _validate_test_case(declaration.name, item, diagnostics)


def _validate_test_case(
    primitive_name: str,
    item: ParsedTslMapValue,
    diagnostics: list[Diagnostic],
) -> None:
    _diagnose_duplicate_fields(item.entries, diagnostics, label="test field")
    entries = {entry.key.text: entry for entry in item.entries}
    case_id = field_text(entries.get("id"))
    owner = (
        f"primitive {primitive_name!r} test {case_id!r}"
        if case_id is not None
        else f"primitive {primitive_name!r} test"
    )
    for key, entry in entries.items():
        if key not in _KNOWN_TEST_FIELDS:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-UNKNOWN-TEST-FIELD",
                    message=f"{owner}: unknown field {key!r}",
                    source=source_span(entry.source),
                )
            )
    for required in _REQUIRED_TEST_FIELDS:
        if required not in entries:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-TEST-MISSING-FIELD",
                    message=f"{owner}: missing required field {required!r}",
                    source=source_span(item.source),
                )
            )
    tags = entries.get("tags")
    if tags is not None and not _is_non_empty_scalar_list(tags):
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-TEST-BAD-TAGS",
                message=f"{owner}: `tags` must be a non-empty list",
                source=source_span(tags.source),
            )
        )
    lanes = _test_lane_count(entries.get("lane_count"))
    if "lane_count" in entries and lanes is None:
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-TEST-BAD-LANE-COUNT",
                message=f"{owner}: `lane_count` must be a positive integer",
                source=source_span(entries["lane_count"].source),
            )
        )
    role = field_text(entries.get("role"))
    if role is not None and role not in _KNOWN_TEST_ROLES:
        _invalid_enum(
            diagnostics,
            entries.get("role"),
            f"test role {role!r}",
            sorted(_KNOWN_TEST_ROLES),
        )
    case = entries.get("case")
    if case is not None:
        case_children = children(case)
        _validate_known_fields(
            case_children,
            frozenset({"inputs", "expected"}),
            diagnostics,
            owner=f"{owner} case",
        )
        _diagnose_duplicate_fields(
            case_children,
            diagnostics,
            label=f"{owner} case field",
        )
        for required in ("inputs", "expected"):
            if child(case, required) is None:
                diagnostics.append(
                    diagnostic_at(
                        severity="error",
                        code="TSL-CATALOG-TEST-MISSING-FIELD",
                        message=f"{owner}: case is missing {required!r}",
                        source=source_span(case.source),
                    )
                )


def _test_lane_count(field: ParsedTslField | None) -> int | None:
    text = field_text(field)
    if text is None:
        return None
    try:
        lanes = int(text)
    except ValueError:
        return None
    return lanes if lanes > 0 else None


def _is_non_empty_scalar_list(field: ParsedTslField) -> bool:
    value = field.value
    return isinstance(value, ParsedTslListValue) and any(
        isinstance(item, ParsedTslScalarValue) for item in value.items
    )


def _is_scalar_list(field: ParsedTslField) -> bool:
    value = field.value
    return isinstance(value, ParsedTslListValue) and all(
        isinstance(item, ParsedTslScalarValue) for item in value.items
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
                if not DEFAULT_SUPPORT_POLICY.supports_backend(child_field.key.text):
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


def _validate_implementation_safety(
    declaration: ParsedPrimitiveDeclaration,
    diagnostics: list[Diagnostic],
) -> None:
    def walk(entry: ParsedImplementationSelectorEntry) -> None:
        _diagnose_duplicate_fields(
            tuple(field for field in entry.fields if field.key.text == "safety"),
            diagnostics,
            label="implementation safety block",
        )
        for field in entry.fields:
            if field.key.text == "safety":
                _validate_safety_field(field, diagnostics)
            elif field.key.text == "implementation":
                _validate_implementation_body_field(field, diagnostics)
        for child_entry in entry.children:
            walk(child_entry)

    for entry in declaration.impl_entries:
        walk(entry)


def _validate_implementation_body_field(
    field: ParsedTslField,
    diagnostics: list[Diagnostic],
) -> None:
    body_children = children(field)
    _validate_known_fields(
        body_children,
        frozenset({"tsil", "tsl"}),
        diagnostics,
        owner="implementation body",
    )
    for body in body_children:
        if body.key.text not in {"tsil", "tsl"}:
            continue
        if (
            not isinstance(body.value, ParsedTslScalarValue)
            or body.value.quote_form not in {"inline", "multiline"}
        ):
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-MALFORMED-IMPLEMENTATION",
                    message="implementation body must be a quoted tsil/tsl field",
                    source=source_span(body.source),
                )
            )


def _validate_safety_field(
    field: ParsedTslField,
    diagnostics: list[Diagnostic],
) -> None:
    field_children = children(field)
    if not field_children:
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-MALFORMED-SAFETY",
                message="implementation safety must contain safety fields",
                source=source_span(field.source),
            )
        )
        return
    _validate_known_fields(
        field_children,
        _KNOWN_SAFETY_FIELDS,
        diagnostics,
        owner="implementation safety",
    )
    _diagnose_duplicate_fields(
        field_children, diagnostics, label="implementation safety field"
    )
    for name in ("internal_unsafe", "caller_unsafe"):
        bool_field = child(field, name)
        value = field_text(bool_field)
        if bool_field is not None and value not in _KNOWN_BOOLEAN_VALUES:
            _invalid_enum(
                diagnostics,
                bool_field,
                f"implementation safety {name} value {value!r}",
                sorted(_KNOWN_BOOLEAN_VALUES),
            )
    reasons = child(field, "reasons")
    if reasons is None:
        return
    if not isinstance(reasons.value, ParsedTslListValue):
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-MALFORMED-SAFETY",
                message="implementation safety reasons must be a scalar list",
                source=source_span(reasons.source),
            )
        )
        return
    for item in reasons.value.items:
        if not isinstance(item, ParsedTslScalarValue):
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-MALFORMED-SAFETY",
                    message="implementation safety reasons must be scalar labels",
                    source=source_span(item.source),
                )
            )


def _validate_param_types(
    declaration: ParsedPrimitiveDeclaration,
    diagnostics: list[Diagnostic],
) -> None:
    attributes = {attribute.key.text: attribute for attribute in declaration.attributes}
    seen: set[tuple[str, str, str]] = set()
    for field in declaration.fields_by_name("param_types"):
        _diagnose_duplicate_fields(children(field.field), diagnostics, label="param_types parameter")
        for parameter in children(field.field):
            parameter_name = parameter.key.text
            if parameter_name not in declaration.parameters:
                diagnostics.append(
                    diagnostic_at(
                        severity="error",
                        code="TSL-CATALOG-PARAM-TYPES-UNKNOWN-PARAM",
                        message=(
                            f"primitive {declaration.name!r} param_types references "
                            f"unknown parameter {parameter_name!r}"
                        ),
                        source=source_span(parameter.source),
                    )
                )
            for entry in children(parameter):
                parsed = _parse_param_type_condition(entry.key.text)
                if parsed is None:
                    diagnostics.append(
                        diagnostic_at(
                            severity="error",
                            code="TSL-CATALOG-PARAM-TYPES-BAD-CONDITION",
                            message=(
                                f"primitive {declaration.name!r} param_types rule "
                                f"{_unquote_key(entry.key.text)!r} must be shaped "
                                "as 'if attribute=value'"
                            ),
                            source=source_span(entry.source),
                        )
                    )
                    continue
                attribute_name, attribute_value = parsed
                attribute = attributes.get(attribute_name)
                if attribute is None:
                    diagnostics.append(
                        diagnostic_at(
                            severity="error",
                            code="TSL-CATALOG-PARAM-TYPES-UNKNOWN-ATTRIBUTE",
                            message=(
                                f"primitive {declaration.name!r} param_types rule references "
                                f"unknown attribute {attribute_name!r}"
                            ),
                            source=source_span(entry.source),
                        )
                    )
                    continue
                allowed = _KNOWN_PRIMITIVE_ATTRIBUTES.get(attribute_name, frozenset())
                if attribute_value not in allowed or attribute_value == "*":
                    _invalid_enum(
                        diagnostics,
                        entry,
                        (
                            f"param_types condition value {attribute_value!r} for "
                            f"attribute {attribute_name!r}"
                        ),
                        sorted(value for value in allowed if value != "*"),
                    )
                identity = (parameter_name, attribute_name, attribute_value)
                if identity in seen:
                    diagnostics.append(
                        diagnostic_at(
                            severity="error",
                            code="TSL-CATALOG-PARAM-TYPES-DUPLICATE-RULE",
                            message=(
                                f"duplicate param_types rule for parameter {parameter_name!r} "
                                f"when {attribute_name}={attribute_value}"
                            ),
                            source=source_span(entry.source),
                        )
                    )
                seen.add(identity)
                if not field_text(entry):
                    diagnostics.append(
                        diagnostic_at(
                            severity="error",
                            code="TSL-CATALOG-PARAM-TYPES-MISSING-TYPE",
                            message=(
                                f"primitive {declaration.name!r} param_types rule for "
                                f"parameter {parameter_name!r} has no type expression"
                            ),
                            source=source_span(entry.source),
                        )
                    )


def _parse_param_type_condition(text: str) -> tuple[str, str] | None:
    match = _PARAM_TYPE_CONDITION_RE.fullmatch(_unquote_key(text))
    if match is None:
        return None
    return match.group(1), match.group(2)


def _unquote_key(text: str) -> str:
    if len(text) >= 2 and text[0] == text[-1] == '"':
        return text[1:-1]
    return text


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
        if not DEFAULT_SUPPORT_POLICY.supports_backend(field.key.text):
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
