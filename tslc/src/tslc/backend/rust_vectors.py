"""Rust render helpers for vector registration and mask type facts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from tslc.backend.target_capability import rust_extension_tag
from tslc.catalog.model import Extension
from tslc.catalog.scalar_types import scalar_bit_width_or_default
from tslc.lower.lowerer import LoweredSpecialization
from tslc.support_policy import DEFAULT_SUPPORT_POLICY


@dataclass(frozen=True, slots=True)
class RustVectorRegistration:
    extension_name: str
    type_tag: str
    base_spelling: str
    register_spelling: str
    vector_bits: int
    type_bits: int


@dataclass(frozen=True, slots=True)
class RustExtensionTagRegistration:
    """One public extension-tag declaration emitted by a profile module."""

    extension_name: str
    tag_name: str
    sized: bool

    def __post_init__(self) -> None:
        if not self.extension_name or not self.tag_name:
            raise ValueError("Rust extension-tag registrations require names")

    def render_declaration(self) -> str:
        if self.sized:
            return f"pub struct {self.tag_name}<const LANES: usize>;"
        return f"pub struct {self.tag_name};"


def rust_registrations(
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    extensions: Mapping[str, Extension],
) -> str:
    """Rust extension tag structs + vector trait impls for the used pairs."""

    registrations = rust_vector_registrations(by_primitive, extensions)
    tag_registrations = _rust_extension_tag_registrations(
        by_primitive,
        extensions,
        registrations,
    )
    lines = _rust_sized_registrations(tag_registrations)
    lines.extend(
        registration.render_declaration()
        for registration in tag_registrations
        if not registration.sized
    )
    for registration in registrations:
        extension = extensions.get(registration.extension_name)
        if extension is None:
            continue
        base = registration.base_spelling
        register = registration.register_spelling
        bits = registration.vector_bits
        mask = rust_mask_type(extension, registration.type_bits, register)
        imask = rust_imask_type(extension, registration.type_bits, mask, bits)
        alignment = bits // 8
        lane_count = bits // registration.type_bits
        array = f"array_type<{base}, {lane_count}, {alignment}>"
        tag = rust_extension_tag(extension)
        lines.append(
            "impl crate::tsl_core::representation_sealed::SimdVector "
            f"for Simd<{base}, {tag}> {{}}"
        )
        lines.append(
            f"impl SimdVector for Simd<{base}, {tag}> {{ "
            f"type BaseType = {base}; type Extension = {tag}; "
            f"type RegisterType = {register}; "
            f"type MaskType = {mask}; type ImaskType = {imask}; type Array = {array}; "
            f"type WithBaseType<ToBase> = Simd<ToBase, {tag}>; "
            f"type WithExtension<ToExtension> = Simd<{base}, ToExtension>; "
            f"const ALIGN: usize = {alignment}; "
            f"const MASK_IS_BITSET: bool = "
            f"{str(_rust_mask_is_bitset(extension)).lower()}; "
            f"fn lane_count() -> usize {{ {lane_count} }} }}"
        )
        lines.append(
            "impl crate::tsl_core::representation_sealed::StaticSimdVector "
            f"for Simd<{base}, {tag}> {{}}"
        )
        lines.append(
            f"impl StaticSimdVector for Simd<{base}, {tag}> {{ "
            f"const ELEMENT_COUNT: usize = {lane_count}; }}"
        )
    return ("\n".join(lines) + "\n\n") if lines else ""


def _rust_sized_registrations(
    registrations: tuple[RustExtensionTagRegistration, ...],
) -> list[str]:
    lines: list[str] = []
    for registration in registrations:
        if not registration.sized:
            continue
        tag = registration.tag_name
        sized_tag = f"{tag}<LANES>"
        lines.append(registration.render_declaration())
        lines.append(
            "impl<T, const LANES: usize> "
            "crate::tsl_core::representation_sealed::SimdVector "
            f"for Simd<T, {sized_tag}> {{}}"
        )
        lines.append(
            f"impl<T: Copy, const LANES: usize> SimdVector for Simd<T, {sized_tag}> {{ "
            "type BaseType = T; "
            f"type Extension = {sized_tag}; "
            "type RegisterType = array_type<T, LANES>; "
            "type MaskType = u64; type ImaskType = u64; "
            "type Array = array_type<T, LANES>; "
            f"type WithBaseType<ToBase> = Simd<ToBase, {sized_tag}>; "
            "type WithExtension<ToExtension> = Simd<T, ToExtension>; "
            "const ALIGN: usize = core::mem::align_of::<array_type<T, LANES>>(); "
            "const MASK_IS_BITSET: bool = true; "
            "fn lane_count() -> usize { LANES } }"
        )
        lines.append(
            "impl<T, const LANES: usize> "
            "crate::tsl_core::representation_sealed::StaticSimdVector "
            f"for Simd<T, {sized_tag}> {{}}"
        )
        lines.append(
            f"impl<T: Copy, const LANES: usize> StaticSimdVector for Simd<T, {sized_tag}> {{ "
            "const ELEMENT_COUNT: usize = LANES; }"
        )
    return lines


def rust_extension_tag_registrations(
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    extensions: Mapping[str, Extension],
) -> tuple[RustExtensionTagRegistration, ...]:
    """Plan the public tag structs rendered for one physical profile module."""

    return _rust_extension_tag_registrations(
        by_primitive,
        extensions,
        rust_vector_registrations(by_primitive, extensions),
    )


def _rust_extension_tag_registrations(
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    extensions: Mapping[str, Extension],
    vector_registrations: tuple[RustVectorRegistration, ...],
) -> tuple[RustExtensionTagRegistration, ...]:
    records: dict[str, RustExtensionTagRegistration] = {}
    candidates = [
        (name, True) for name in _used_sized_extensions(by_primitive, extensions)
    ]
    candidates.extend(
        (name, False)
        for name in sorted(
            {registration.extension_name for registration in vector_registrations}
        )
    )
    for extension_name, sized in candidates:
        extension = extensions.get(extension_name)
        if extension is None:
            continue
        tag_name = rust_extension_tag(extension)
        record = RustExtensionTagRegistration(extension_name, tag_name, sized)
        previous = records.setdefault(tag_name, record)
        if previous.sized != record.sized:
            raise ValueError(
                f"Rust extension tag {tag_name!r} has conflicting declaration arity"
            )
    return tuple(records[name] for name in sorted(records))


def _used_sized_extensions(
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    extensions: Mapping[str, Extension],
) -> tuple[str, ...]:
    used: set[str] = set()
    for specs in by_primitive.values():
        for spec in specs:
            _record_sized_extension(used, extensions, spec.extension_name, spec.uses_sized_vector)
            if spec.target is not None:
                _record_sized_extension(
                    used,
                    extensions,
                    spec.target.extension_isa,
                    spec.target.uses_sized_vector,
                )
    return tuple(sorted(used))


def _record_sized_extension(
    used: set[str],
    extensions: Mapping[str, Extension],
    extension_name: str,
    uses_sized_vector: bool,
) -> None:
    extension = extensions.get(extension_name)
    if (
        extension is None
        or (
            extension.is_unconditional_implementation_fallback
            and DEFAULT_SUPPORT_POLICY.uses_sized_vector(extension)
        )
        or not uses_sized_vector
        or not DEFAULT_SUPPORT_POLICY.uses_sized_vector(extension)
        or not extension.supports_backend("rust")
    ):
        return
    used.add(extension_name)


def rust_vector_registrations(
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    extensions: Mapping[str, Extension],
) -> tuple[RustVectorRegistration, ...]:
    records: dict[tuple[str, str, str, str], RustVectorRegistration] = {}
    for specs in by_primitive.values():
        for spec in specs:
            if not DEFAULT_SUPPORT_POLICY.is_free_function_signature(
                spec.result_kind, spec.param_kinds
            ):
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
        type_bits=scalar_bit_width_or_default(type_tag),
    )


def rust_mask_type(extension: Extension | None, type_bits: int, register: str) -> str:
    if extension is None or extension.mask_policy.kind != "native_predicate_by_lanes":
        return register
    lanes = extension.vector_bits // type_bits
    return extension.mask_policy.spelling_for_lanes("rust", max(8, lanes)) or register


def _rust_mask_is_bitset(extension: Extension) -> bool:
    return extension.mask_policy.kind in {
        "exact_lane_bitmask",
        "native_predicate_by_lanes",
    }


def rust_imask_type(
    extension: Extension | None, type_bits: int, mask: str, vector_bits: int
) -> str:
    kind = extension.imask_policy.kind if extension is not None else "lane_bitmask"
    if kind == "same_as_mask_type":
        return mask
    lanes = vector_bits // type_bits
    width = rust_imask_width(lanes)
    return f"u{width}"


def rust_imask_width(lanes: int) -> int:
    if lanes <= 0:
        raise ValueError("Rust integral masks require a positive lane count")
    return 8 if lanes <= 8 else 16 if lanes <= 16 else 32 if lanes <= 32 else 64


__all__ = (
    "RustExtensionTagRegistration",
    "RustVectorRegistration",
    "rust_extension_tag_registrations",
    "rust_imask_type",
    "rust_imask_width",
    "rust_mask_type",
    "rust_registrations",
    "rust_vector_registrations",
)
