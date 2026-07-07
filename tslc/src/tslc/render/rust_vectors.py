"""Rust render helpers for vector registration and mask type facts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from tslc.backend.target_capability import rust_extension_tag
from tslc.catalog.model import Extension
from tslc.lower.lowerer import LoweredSpecialization
from tslc.render._common import type_bits


@dataclass(frozen=True, slots=True)
class RustVectorRegistration:
    extension_name: str
    type_tag: str
    base_spelling: str
    register_spelling: str
    vector_bits: int


def rust_registrations(
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    extensions: Mapping[str, Extension],
) -> str:
    """Rust extension tag structs + vector trait impls for the used pairs."""

    lines: list[str] = []
    registrations = rust_vector_registrations(by_primitive, extensions)
    for ext in sorted({registration.extension_name for registration in registrations}):
        extension = extensions.get(ext)
        if extension is not None:
            lines.append(f"pub struct {rust_extension_tag(extension)};")
    for registration in registrations:
        extension = extensions.get(registration.extension_name)
        if extension is None:
            continue
        base = registration.base_spelling
        register = registration.register_spelling
        bits = registration.vector_bits
        mask = rust_mask_type(extension, base, register)
        imask = rust_imask_type(extension, base, mask, bits)
        alignment = bits // 8
        lane_count = bits // type_bits(base)
        array = f"array_type<{base}, {lane_count}, {alignment}>"
        tag = rust_extension_tag(extension)
        lines.append(
            f"impl SimdVector for Simd<{base}, {tag}> {{ "
            f"type BaseType = {base}; type Extension = {tag}; "
            f"type RegisterType = {register}; "
            f"type MaskType = {mask}; type ImaskType = {imask}; type Array = {array}; "
            f"type WithBaseType<ToBase> = Simd<ToBase, {tag}>; "
            f"type WithExtension<ToExtension> = Simd<{base}, ToExtension>; "
            f"const ALIGN: usize = {alignment}; "
            f"fn lane_count() -> usize {{ {lane_count} }} }}"
        )
        lines.append(
            f"impl StaticSimdVector for Simd<{base}, {tag}> {{ "
            f"const ELEMENT_COUNT: usize = {lane_count}; }}"
        )
    return ("\n".join(lines) + "\n\n") if lines else ""


def rust_vector_registrations(
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    extensions: Mapping[str, Extension],
) -> tuple[RustVectorRegistration, ...]:
    records: dict[tuple[str, str, str, str], RustVectorRegistration] = {}
    for specs in by_primitive.values():
        for spec in specs:
            _record_rust_vector(
                records,
                extensions,
                spec.extension_name,
                spec.type_tag,
                spec.base_type_spelling,
                spec.register_spelling,
                uses_sized_vector=spec.uses_sized_vector,
            )
            if spec.target is not None:
                _record_rust_vector(
                    records,
                    extensions,
                    spec.target.extension_isa,
                    spec.target.base_tag,
                    spec.target.base_spelling,
                    spec.target.register_spelling,
                    uses_sized_vector=spec.target.uses_sized_vector,
                )
    return tuple(records[key] for key in sorted(records))


def _record_rust_vector(
    records: dict[tuple[str, str, str, str], RustVectorRegistration],
    extensions: Mapping[str, Extension],
    extension_name: str,
    type_tag: str,
    base_spelling: str,
    register_spelling: str,
    *,
    uses_sized_vector: bool,
) -> None:
    extension = extensions.get(extension_name)
    if (
        extension is None
        or uses_sized_vector
        or extension.family in {"scalar", "generic_like"}
        or extension.vector_bits_kind != "fixed"
        or extension.vector_bits <= 0
        or not extension.supports_backend("rust")
    ):
        return
    key = (extension_name, type_tag, base_spelling, register_spelling)
    records[key] = RustVectorRegistration(
        extension_name=extension_name,
        type_tag=type_tag,
        base_spelling=base_spelling,
        register_spelling=register_spelling,
        vector_bits=extension.vector_bits,
    )


def rust_mask_type(extension: Extension | None, base_spelling: str, register: str) -> str:
    if extension is None or extension.mask_policy.kind != "native_predicate_by_lanes":
        return register
    lanes = extension.vector_bits // type_bits(base_spelling)
    return extension.mask_policy.spelling_for_lanes("rust", max(8, lanes)) or register


def rust_imask_type(
    extension: Extension | None, base_spelling: str, mask: str, vector_bits: int
) -> str:
    kind = extension.imask_policy.kind if extension is not None else "lane_bitmask"
    if kind == "same_as_mask_type":
        return mask
    lanes = vector_bits // type_bits(base_spelling)
    width = 8 if lanes <= 8 else 16 if lanes <= 16 else 32 if lanes <= 32 else 64
    return f"u{width}"


__all__ = (
    "RustVectorRegistration",
    "rust_registrations",
    "rust_vector_registrations",
)
