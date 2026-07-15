"""Schema validation for `extension` blocks."""

from __future__ import annotations

from collections.abc import Collection, Iterable

from tslc.catalog.target_families import TargetFamilyCatalog
from tslc.catalog.validation._schema_common import (
    diagnose_duplicate_fields,
    invalid_enum,
    validate_backend_key_fields,
    validate_known_fields,
)
from tslc.catalog.validation.source_spans import child, children, field_text, source_span
from tslc.diagnostics import Diagnostic, diagnostic_at
from tslc.syntax.ast import ParsedBlockDeclaration, ParsedTslField

KNOWN_EXTENSION_FIELDS = frozenset(
    {
        "active_when",
        "default_test_target",
        "extension_name",
        "family",
        "inherits",
        "integral_mask_type_policy",
        "intrinsic_compose",
        "intrinsic_style",
        "mask_type_policy",
        "native_sort_order",
        "runtime_lane_count",
        "size_bits",
        "size_parameter",
        "supersedes",
        "test_filter",
        "test_mask_check",
        "test_mask_from_bits",
        "test_runtime_lanes",
        "test_support_headers",
        "unroll_variants",
        "vector_bits",
        "vector_register_type_policy",
        "vector_register_types",
    }
)
KNOWN_EXTENSION_BACKEND_FIELDS = frozenset(
    {
        "arch_module",
        "compile_guards",
        "compiler_features",
        "compiler_ids",
        "dataparallel_inference",
        "header_group",
        "headers",
        "supported",
        "type_name",
    }
)
_KNOWN_MASK_POLICY_KINDS = frozenset(
    {
        "bool",
        "exact_lane_bitmask",
        "lane_bitmask",
        "native_predicate",
        "native_predicate_by_lanes",
        "comparison_lane_vector",
        "boolean_lane_vector",
    }
)
_KNOWN_IMASK_POLICY_KINDS = frozenset(
    {"lane_bitmask", "same_as_mask_type", "unsigned_scalar"}
)


def known_extension_fields(backend_ids: Iterable[str] = ()) -> frozenset[str]:
    return KNOWN_EXTENSION_FIELDS | frozenset(backend_ids)


def validate_extension_block(
    declaration: ParsedBlockDeclaration,
    backend_ids: Collection[str],
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
        invalid_enum(
            diagnostics,
            fields.get("family"),
            f"extension family {family!r}",
            sorted(target_families.known_extension_families),
        )

    mask = fields.get("mask_type_policy")
    _validate_policy_block(
        mask,
        frozenset({"kind", "backend_spelling", "backend_spelling_by_lanes"}),
        _KNOWN_MASK_POLICY_KINDS,
        "mask_type_policy",
        diagnostics,
    )
    _validate_mask_policy_backend_maps(mask, backend_ids, diagnostics)
    imask = fields.get("integral_mask_type_policy")
    _validate_policy_block(
        imask,
        frozenset({"kind"}),
        _KNOWN_IMASK_POLICY_KINDS,
        "integral_mask_type_policy",
        diagnostics,
    )

    compose = fields.get("intrinsic_compose")
    if compose is not None:
        validate_known_fields(
            children(compose),
            frozenset({"prefix", "suffix"}),
            diagnostics,
            owner="intrinsic_compose",
        )
        prefix = child(compose, "prefix")
        if prefix is not None:
            validate_backend_key_fields(
                children(prefix), backend_ids, diagnostics, owner="intrinsic prefix"
            )
        suffix = child(compose, "suffix")
        if suffix is not None:
            validate_known_fields(
                children(suffix),
                frozenset({"by_type"}),
                diagnostics,
                owner="intrinsic suffix",
            )
    active_when = fields.get("active_when")
    if active_when is not None:
        validate_known_fields(
            children(active_when),
            frozenset({"target_features", "compile_modes"}),
            diagnostics,
            owner="active_when",
        )
        diagnose_duplicate_fields(
            children(active_when),
            diagnostics,
            label="active_when field",
        )
    size_parameter = fields.get("size_parameter")
    if size_parameter is not None:
        validate_known_fields(
            children(size_parameter),
            frozenset({"name"}),
            diagnostics,
            owner="size_parameter",
        )
        diagnose_duplicate_fields(
            children(size_parameter),
            diagnostics,
            label="size_parameter field",
        )
    register_policy = fields.get("vector_register_type_policy")
    if register_policy is not None:
        validate_known_fields(
            children(register_policy),
            frozenset({"kind"}),
            diagnostics,
            owner="vector_register_type_policy",
        )
        diagnose_duplicate_fields(
            children(register_policy),
            diagnostics,
            label="vector_register_type_policy field",
        )
    for backend_id in sorted(backend_ids):
        backend = fields.get(backend_id)
        if backend is None:
            continue
        validate_known_fields(
            children(backend),
            KNOWN_EXTENSION_BACKEND_FIELDS,
            diagnostics,
            owner=f"extension backend {backend_id}",
        )
        diagnose_duplicate_fields(
            children(backend),
            diagnostics,
            label=f"extension backend {backend_id} field",
        )
        _validate_compile_guards(
            child(backend, "compile_guards"),
            diagnostics,
            backend_id,
        )
        inference_field = child(backend, "dataparallel_inference")
        inference = field_text(inference_field)
        if inference is not None and inference not in {"true", "false"}:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-MALFORMED-DATAPARALLEL-INFERENCE",
                    message=(
                        f"extension backend {backend_id} field "
                        "'dataparallel_inference' must be true or false"
                    ),
                    source=(
                        source_span(inference_field.source)
                        if inference_field is not None
                        else None
                    ),
                )
            )
    for backend_map_name in (
        "runtime_lane_count",
        "test_runtime_lanes",
        "test_mask_from_bits",
        "test_mask_check",
        "test_support_headers",
    ):
        backend_map = fields.get(backend_map_name)
        if backend_map is not None:
            diagnose_duplicate_fields(
                children(backend_map),
                diagnostics,
                label=f"{backend_map_name} backend field",
            )
            validate_backend_key_fields(
                children(backend_map),
                backend_ids,
                diagnostics,
                owner=backend_map_name,
            )


def _validate_compile_guards(
    field: ParsedTslField | None,
    diagnostics: list[Diagnostic],
    backend_id: str,
) -> None:
    if field is None:
        return
    diagnose_duplicate_fields(
        children(field),
        diagnostics,
        label=f"{backend_id} compile guard",
    )
    for guard in children(field):
        validate_known_fields(
            children(guard),
            frozenset({"macro", "equals", "hint_flag", "diagnostic"}),
            diagnostics,
            owner=f"{backend_id} compile guard {guard.key.text!r}",
        )
        diagnose_duplicate_fields(
            children(guard),
            diagnostics,
            label=f"{backend_id} compile guard {guard.key.text!r} field",
        )
        for required in ("macro", "equals"):
            if field_text(child(guard, required)) is None:
                diagnostics.append(
                    diagnostic_at(
                        severity="error",
                        code="TSL-CATALOG-MALFORMED-COMPILE-GUARD",
                        message=(
                            f"{backend_id} compile guard {guard.key.text!r} "
                            f"requires scalar field {required!r}"
                        ),
                        source=source_span(guard.source),
                    )
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
    validate_known_fields(children(field), allowed_fields, diagnostics, owner=owner)
    diagnose_duplicate_fields(children(field), diagnostics, label=f"{owner} field")
    kind_field = child(field, "kind")
    kind = field_text(kind_field)
    if kind is not None and kind not in allowed_kinds:
        invalid_enum(diagnostics, kind_field, f"{owner} kind {kind!r}", sorted(allowed_kinds))


def _validate_mask_policy_backend_maps(
    field: ParsedTslField | None,
    backend_ids: Collection[str],
    diagnostics: list[Diagnostic],
) -> None:
    if field is None:
        return
    spelling = child(field, "backend_spelling")
    if spelling is not None:
        diagnose_duplicate_fields(
            children(spelling),
            diagnostics,
            label="mask_type_policy backend_spelling field",
        )
        validate_backend_key_fields(
            children(spelling),
            backend_ids,
            diagnostics,
            owner="mask_type_policy backend_spelling",
        )
    by_lanes = child(field, "backend_spelling_by_lanes")
    if by_lanes is None:
        return
    diagnose_duplicate_fields(
        children(by_lanes),
        diagnostics,
        label="mask_type_policy backend_spelling_by_lanes field",
    )
    validate_backend_key_fields(
        children(by_lanes),
        backend_ids,
        diagnostics,
        owner="mask_type_policy backend_spelling_by_lanes",
    )
    for backend in children(by_lanes):
        diagnose_duplicate_fields(
            children(backend),
            diagnostics,
            label=f"mask_type_policy {backend.key.text!r} lane field",
        )
