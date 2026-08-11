"""Promotion helpers for extension blocks and inheritance."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from typing import cast

from tslc.catalog._builder_common import _list_text_set, _opt_int
from tslc.catalog.model import (
    BackendExtensionMetadata,
    Extension,
    ExtensionActivation,
    ExtensionMetadata,
    ImaskPolicy,
    ImaskPolicyKind,
    IntrinsicComposition,
    IntrinsicNameOrder,
    MaskPolicy,
    MaskPolicyKind,
    VectorBitsKind,
)
from tslc.syntax.access import child as _child
from tslc.syntax.access import children as _children
from tslc.syntax.access import field_text as _field_text
from tslc.syntax.access import list_text as _list_text
from tslc.syntax.access import source_span as _source_span
from tslc.syntax.ast import ParsedBlockDeclaration, ParsedTslField


def _resolve_extension_inheritance(
    extensions: dict[str, Extension],
    declared_fields_by_name: Mapping[str, frozenset[str]] | None = None,
) -> dict[str, Extension]:
    """Fill each extension's compose metadata/family from its `inherits` ancestors."""

    declared_fields_by_name = declared_fields_by_name or {}

    def resolve(name: str, seen: frozenset[str]) -> Extension:
        ext = extensions[name]
        if ext.inherits is None or ext.inherits not in extensions or ext.inherits in seen:
            return ext
        parent = resolve(ext.inherits, seen | {name})
        declared_fields = declared_fields_by_name.get(name, frozenset())
        intrinsic_composition = IntrinsicComposition(
            prefix_by_backend={
                **parent.intrinsic_composition.prefix_by_backend,
                **ext.intrinsic_composition.prefix_by_backend,
            },
            suffix_by_type={
                **parent.intrinsic_composition.suffix_by_type,
                **ext.intrinsic_composition.suffix_by_type,
            },
            order=(
                ext.intrinsic_composition.order
                if "intrinsic_compose.order" in declared_fields
                else parent.intrinsic_composition.order
            ),
            require_explicit_suffix=(
                ext.intrinsic_composition.require_explicit_suffix
                if "intrinsic_compose.require_explicit_suffix" in declared_fields
                else parent.intrinsic_composition.require_explicit_suffix
            ),
        )
        return replace(
            ext,
            family=ext.family or parent.family,
            intrinsic_composition=intrinsic_composition,
            vector_register_types=_merge_nested_string_maps(
                parent.vector_register_types,
                ext.vector_register_types,
            ),
            backend_headers=_merge_header_maps(parent.backend_headers, ext.backend_headers),
            backend_supported={**parent.backend_supported, **ext.backend_supported},
            metadata=replace(
                ext.metadata,
                documentation_width=(
                    ext.metadata.documentation_width
                    or parent.metadata.documentation_width
                ),
                backend=_merge_backend_metadata(
                    parent.metadata.backend,
                    ext.metadata.backend,
                ),
            ),
            # mask policy / width fall back to the parent only when this block didn't
            # state its own (every `_vl` block does, so this is just gap-filling).
            vector_bits=(
                ext.vector_bits if "vector_bits" in declared_fields else parent.vector_bits
            ),
            vector_bits_kind=(
                ext.vector_bits_kind
                if "vector_bits" in declared_fields
                else parent.vector_bits_kind
            ),
            size_parameter_name=(
                ext.size_parameter_name
                if "size_parameter" in declared_fields
                else parent.size_parameter_name
            ),
            vector_register_type_policy=(
                ext.vector_register_type_policy or parent.vector_register_type_policy
            ),
            # A sized extension inheriting another (oneapi_fpga inherits generic) shares its size
            # ladder / unroll default unless it states its own.
            size_bits=ext.size_bits if "size_bits" in declared_fields else parent.size_bits,
            unroll_variants=(
                ext.unroll_variants
                if "unroll_variants" in declared_fields
                else parent.unroll_variants
            ),
            runtime_lane_count={**parent.runtime_lane_count, **ext.runtime_lane_count},
            test_runtime_lanes={**parent.test_runtime_lanes, **ext.test_runtime_lanes},
            test_mask_from_bits={**parent.test_mask_from_bits, **ext.test_mask_from_bits},
            test_mask_check={**parent.test_mask_check, **ext.test_mask_check},
            test_support_headers=_merge_header_maps(
                parent.test_support_headers,
                ext.test_support_headers,
            ),
            mask_policy=(
                ext.mask_policy
                if "mask_type_policy" in declared_fields
                else parent.mask_policy
            ),
            imask_policy=(
                ext.imask_policy
                if "integral_mask_type_policy" in declared_fields
                else parent.imask_policy
            ),
        )

    return {name: resolve(name, frozenset()) for name in extensions}


def _declared_extension_fields(declaration: ParsedBlockDeclaration) -> frozenset[str]:
    fields = {field.key.text for field in declaration.fields}
    compose = next(
        (
            field
            for field in declaration.fields
            if field.key.text == "intrinsic_compose"
        ),
        None,
    )
    fields.update(
        f"intrinsic_compose.{field.key.text}"
        for field in _children(compose)
    )
    return frozenset(fields)


def _build_extension(
    declaration: ParsedBlockDeclaration,
    backend_ids: frozenset[str],
) -> Extension:
    fields = {field.key.text: field for field in declaration.fields}
    backend_ids = backend_ids | frozenset(
        field.key.text
        for field in declaration.fields
        if _child(field, "supported") is not None
    )
    # Identity is the block name: `avx2` and `avx2_vl` are distinct extensions
    # (avx2-only hardware vs. avx512vl-present hardware) even though they share the
    # `extension_name` ISA spelling "avx2".
    compose = fields.get("intrinsic_compose")

    name = declaration.name or ""
    return Extension(
        name=name,
        isa_name=_field_text(fields.get("extension_name")) or name,
        family=_field_text(fields.get("family")) or "",
        intrinsic_composition=_intrinsic_composition(compose),
        vector_register_types=_vector_register_types(fields.get("vector_register_types")),
        backend_headers=_backend_headers(fields, backend_ids),
        backend_supported=_backend_supported(fields, backend_ids),
        inherits=_field_text(fields.get("inherits")),
        active_when=_extension_activation(fields.get("active_when")),
        supersedes=_list_text_set(fields.get("supersedes")),
        vector_bits=_int_text(fields.get("vector_bits")),
        vector_bits_kind=_vector_bits_kind(fields.get("vector_bits")),
        size_parameter_name=_field_text(_child(fields.get("size_parameter"), "name")),
        vector_register_type_policy=(
            _field_text(_child(fields.get("vector_register_type_policy"), "kind")) or ""
        ),
        mask_policy=_mask_policy(fields.get("mask_type_policy")),
        imask_policy=_imask_policy(fields.get("integral_mask_type_policy")),
        metadata=_extension_metadata(fields, backend_ids),
        default_test_target=(_field_text(fields.get("default_test_target")) or "").lower()
        == "true",
        test_filter_exclude_templates=_list_text_set(
            _child(fields.get("test_filter"), "exclude_templates")
        ),
        runtime_lane_count=_backend_text_map(fields.get("runtime_lane_count")),
        test_runtime_lanes=_backend_text_map(fields.get("test_runtime_lanes")),
        test_mask_from_bits=_backend_text_map(fields.get("test_mask_from_bits")),
        test_mask_check=_backend_text_map(fields.get("test_mask_check")),
        test_support_headers=_backend_list_map(fields.get("test_support_headers")),
        size_bits=tuple(
            n for n in (_opt_int(t) for t in _list_text(fields.get("size_bits")))
            if n is not None
        ),
        unroll_variants=(_field_text(fields.get("unroll_variants")) or "").lower() == "true",
        source=_source_span(declaration.source),
    )


def _intrinsic_composition(
    field: ParsedTslField | None,
) -> IntrinsicComposition:
    prefix = _child(field, "prefix")
    suffix = _child(_child(field, "suffix"), "by_type")
    order_text = _field_text(_child(field, "order"))
    order = (
        IntrinsicNameOrder(order_text)
        if order_text in {item.value for item in IntrinsicNameOrder}
        else IntrinsicNameOrder.BASE_SUFFIX
    )
    return IntrinsicComposition(
        prefix_by_backend={
            entry.key.text: (_field_text(entry) or "")
            for entry in _children(prefix)
        },
        suffix_by_type={
            entry.key.text: (_field_text(entry) or "")
            for entry in _children(suffix)
        },
        order=order,
        require_explicit_suffix=bool(
            _bool_text(_child(field, "require_explicit_suffix"))
        ),
    )


def _extension_activation(field: ParsedTslField | None) -> ExtensionActivation:
    return ExtensionActivation(
        target_features=_list_text_set(_child(field, "target_features")),
        compile_modes=_list_text_set(_child(field, "compile_modes")),
    )


def _vector_register_types(
    field: ParsedTslField | None,
) -> dict[str, dict[str, str]]:
    """Promote ``vector_register_types`` to type-key -> backend -> spelling."""

    result: dict[str, dict[str, str]] = {}
    for type_entry in _children(field):
        by_backend = {
            backend_entry.key.text: (_field_text(backend_entry) or "")
            for backend_entry in _children(type_entry)
            if _field_text(backend_entry) is not None
        }
        if by_backend:
            result[type_entry.key.text] = by_backend
    return result


def _backend_headers(
    fields: dict[str, ParsedTslField],
    backend_ids: frozenset[str],
) -> dict[str, tuple[str, ...]]:
    """Promote backend-owned extension include/import metadata."""

    result: dict[str, tuple[str, ...]] = {}
    for backend_id in sorted(backend_ids):
        headers = _list_text(_child(fields.get(backend_id), "headers"))
        if headers:
            result[backend_id] = headers
    return result


def _extension_metadata(
    fields: dict[str, ParsedTslField],
    backend_ids: frozenset[str],
) -> ExtensionMetadata:
    return ExtensionMetadata(
        native_sort_order=_opt_int(_field_text(fields.get("native_sort_order"))),
        documentation_width=_field_text(fields.get("documentation_width")),
        backend=_backend_extension_metadata(fields, backend_ids),
    )


def _backend_extension_metadata(
    fields: dict[str, ParsedTslField],
    backend_ids: frozenset[str],
) -> dict[str, BackendExtensionMetadata]:
    result: dict[str, BackendExtensionMetadata] = {}
    for backend_id in sorted(backend_ids):
        backend = fields.get(backend_id)
        if backend is None:
            continue
        metadata = BackendExtensionMetadata(
            compiler_capabilities=_list_text(
                _child(backend, "compiler_capabilities")
            ),
            dataparallel_inference=_bool_text(
                _child(backend, "dataparallel_inference")
            ),
            type_name=_field_text(_child(backend, "type_name")),
            arch_module=_field_text(_child(backend, "arch_module")),
        )
        if metadata != BackendExtensionMetadata():
            result[backend_id] = metadata
    return result


def _backend_supported(
    fields: dict[str, ParsedTslField],
    backend_ids: frozenset[str],
) -> dict[str, bool]:
    """Promote explicit backend ``supported`` flags."""

    result: dict[str, bool] = {}
    for backend_id in sorted(backend_ids):
        text = _field_text(_child(fields.get(backend_id), "supported"))
        if text is not None:
            result[backend_id] = text.lower() == "true"
    return result


def _bool_text(field: ParsedTslField | None) -> bool | None:
    text = _field_text(field)
    if text is None:
        return None
    return text.lower() == "true"


def _backend_text_map(field: ParsedTslField | None) -> dict[str, str]:
    return {
        child.key.text: text
        for child in _children(field)
        if (text := _field_text(child)) is not None
    }



def _backend_list_map(field: ParsedTslField | None) -> dict[str, tuple[str, ...]]:
    return {
        child.key.text: values
        for child in _children(field)
        if (values := _list_text(child))
    }



def _merge_nested_string_maps(
    parent: Mapping[str, Mapping[str, str]],
    child: Mapping[str, Mapping[str, str]],
) -> dict[str, dict[str, str]]:
    merged = {key: dict(value) for key, value in parent.items()}
    for key, value in child.items():
        merged[key] = {**merged.get(key, {}), **value}
    return merged



def _merge_header_maps(
    parent: Mapping[str, tuple[str, ...]],
    child: Mapping[str, tuple[str, ...]],
) -> dict[str, tuple[str, ...]]:
    merged = {key: tuple(value) for key, value in parent.items()}
    for key, headers in child.items():
        values = list(merged.get(key, ()))
        values.extend(header for header in headers if header not in values)
        merged[key] = tuple(values)
    return merged



def _merge_backend_metadata(
    parent: Mapping[str, BackendExtensionMetadata],
    child: Mapping[str, BackendExtensionMetadata],
) -> dict[str, BackendExtensionMetadata]:
    merged = dict(parent)
    for backend_id, child_meta in child.items():
        parent_meta = merged.get(backend_id, BackendExtensionMetadata())
        merged[backend_id] = BackendExtensionMetadata(
            compiler_capabilities=tuple(
                dict.fromkeys(
                    parent_meta.compiler_capabilities
                    + child_meta.compiler_capabilities
                )
            ),
            dataparallel_inference=(
                child_meta.dataparallel_inference
                if child_meta.dataparallel_inference is not None
                else parent_meta.dataparallel_inference
            ),
            type_name=child_meta.type_name or parent_meta.type_name,
            arch_module=child_meta.arch_module or parent_meta.arch_module,
        )
    return merged


def _mask_policy(field: ParsedTslField | None) -> MaskPolicy:
    """Promote a ``mask_type_policy`` block: its ``kind`` plus backend-owned native
    predicate spellings and lane-count maps."""

    if field is None:
        return MaskPolicy()
    # Typing-only narrow: schema validation diagnoses kinds outside MaskPolicyKind.
    return MaskPolicy(
        kind=cast(MaskPolicyKind, _field_text(_child(field, "kind")) or "lane_bitmask"),
        backend_spelling=_backend_text_map(_child(field, "backend_spelling")),
        backend_spelling_by_type=_backend_type_map(
            _child(field, "backend_spelling_by_type")
        ),
        backend_spelling_by_lanes=_backend_int_map(
            _child(field, "backend_spelling_by_lanes")
        ),
        source=_source_span(field.source),
    )



def _imask_policy(field: ParsedTslField | None) -> ImaskPolicy:
    """Promote the integral-mask representation kind."""

    if field is None:
        return ImaskPolicy()
    # Typing-only narrow: schema validation diagnoses kinds outside ImaskPolicyKind.
    return ImaskPolicy(
        kind=cast(ImaskPolicyKind, _field_text(_child(field, "kind")) or "lane_bitmask")
    )



def _int_keyed_map(field: ParsedTslField | None) -> dict[int, str]:
    """An int-keyed string map (``8 "__mmask8"`` ...), skipping non-numeric keys."""

    result: dict[int, str] = {}
    for entry in _children(field):
        key = entry.key.text
        if key.isdigit():
            result[int(key)] = _field_text(entry) or ""
    return result



def _backend_type_map(field: ParsedTslField | None) -> dict[str, dict[str, str]]:
    return {
        child.key.text: _backend_text_map(child)
        for child in _children(field)
    }


def _backend_int_map(field: ParsedTslField | None) -> dict[str, dict[int, str]]:
    return {
        child.key.text: values
        for child in _children(field)
        if (values := _int_keyed_map(child))
    }



def _int_text(field: ParsedTslField | None) -> int:
    text = _field_text(field)
    return int(text) if text is not None and text.lstrip("-").isdigit() else 0



def _vector_bits_kind(field: ParsedTslField | None) -> VectorBitsKind:
    text = _field_text(field)
    if text is None:
        return ""
    if text.lstrip("-").isdigit():
        return "fixed"
    # Typing-only narrow: schema validation diagnoses spellings outside VectorBitsKind.
    return cast(VectorBitsKind, text)
