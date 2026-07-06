"""Schema validation for `extension` blocks."""

from __future__ import annotations

from collections.abc import Iterable

from tslc.catalog.target_families import TargetFamilyCatalog
from tslc.catalog.validation._schema_common import (
    diagnose_duplicate_fields,
    invalid_enum,
    validate_backend_key_fields,
    validate_known_fields,
)
from tslc.catalog.validation.source_spans import child, children, field_text
from tslc.diagnostics import Diagnostic
from tslc.support_policy import DEFAULT_SUPPORT_POLICY
from tslc.syntax.ast import ParsedBlockDeclaration, ParsedTslField

EXTENSION_METADATA_FIELDS = frozenset(
    {
        "active_when",
        "autodetect",
        "default_test_target",
        "extension_name",
        "family",
        "inherits",
        "integral_mask_type_policy",
        "intrinsic_compose",
        "intrinsic_style",
        "mask_repr",
        "mask_type_policy",
        "mask_vector_loadable",
        "mask_width",
        "native_sort_order",
        "runtime_lane_count",
        "runtime_lanes",
        "signature_support",
        "size_bits",
        "size_parameter",
        "supersedes",
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
KNOWN_EXTENSION_FIELDS = EXTENSION_METADATA_FIELDS | frozenset(
    DEFAULT_SUPPORT_POLICY.default_backend_ids
)
KNOWN_EXTENSION_BACKEND_FIELDS = frozenset(
    {
        "arch_module",
        "generation_support",
        "header_guard",
        "headers",
        "supported",
        "test_suite_name",
        "test_support_header",
        "type_name",
    }
)
_KNOWN_MASK_POLICY_KINDS = frozenset(
    {"bool", "lane_bitmask", "native_predicate", "native_predicate_by_lanes"}
)
_KNOWN_IMASK_POLICY_KINDS = frozenset(
    {"lane_bitmask", "same_as_mask_type", "unsigned_scalar"}
)


def known_extension_fields(
    backend_ids: Iterable[str] = DEFAULT_SUPPORT_POLICY.default_backend_ids,
) -> frozenset[str]:
    return EXTENSION_METADATA_FIELDS | frozenset(backend_ids)


def validate_extension_block(
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
        invalid_enum(
            diagnostics,
            fields.get("family"),
            f"extension family {family!r}",
            sorted(target_families.known_extension_families),
        )

    mask = fields.get("mask_type_policy")
    _validate_policy_block(
        mask,
        frozenset({"kind", "width", "backend_spelling", "backend_spelling_by_lanes"}),
        _KNOWN_MASK_POLICY_KINDS,
        "mask_type_policy",
        diagnostics,
    )
    _validate_mask_policy_backend_maps(mask, diagnostics)
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
        validate_known_fields(
            children(compose),
            frozenset({"prefix", "suffix"}),
            diagnostics,
            owner="intrinsic_compose",
        )
        prefix = child(compose, "prefix")
        if prefix is not None:
            validate_backend_key_fields(
                children(prefix), diagnostics, owner="intrinsic prefix"
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
            frozenset({"target_features"}),
            diagnostics,
            owner="active_when",
        )
        diagnose_duplicate_fields(
            children(active_when),
            diagnostics,
            label="active_when field",
        )
    signature_support = fields.get("signature_support")
    if signature_support is not None:
        validate_known_fields(
            children(signature_support),
            frozenset({"exclude"}),
            diagnostics,
            owner="signature_support",
        )
        diagnose_duplicate_fields(
            children(signature_support),
            diagnostics,
            label="signature_support field",
        )
    for backend_id in DEFAULT_SUPPORT_POLICY.default_backend_ids:
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
    validate_known_fields(children(field), allowed_fields, diagnostics, owner=owner)
    diagnose_duplicate_fields(children(field), diagnostics, label=f"{owner} field")
    kind_field = child(field, "kind")
    kind = field_text(kind_field)
    if kind is not None and kind not in allowed_kinds:
        invalid_enum(diagnostics, kind_field, f"{owner} kind {kind!r}", sorted(allowed_kinds))


def _validate_mask_policy_backend_maps(
    field: ParsedTslField | None,
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
        diagnostics,
        owner="mask_type_policy backend_spelling_by_lanes",
    )
    for backend in children(by_lanes):
        diagnose_duplicate_fields(
            children(backend),
            diagnostics,
            label=f"mask_type_policy {backend.key.text!r} lane field",
        )
