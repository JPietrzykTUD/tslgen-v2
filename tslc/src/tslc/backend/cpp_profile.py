"""Render C++ profile includes and SIMD registrations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from tslc.backend.cpp_validation import resolve_cpp_compile_guards
from tslc.backend.emitted_profile import EmittedProfile, used_type_specs
from tslc.backend.helper_requirements import CPP_HELPER_MANIFEST
from tslc.backend.target_capability import (
    cpp_x86_register_helper,
    is_x86_register_extension,
)
from tslc.catalog.model import BackendCompileGuard, Extension
from tslc.catalog.scalar_types import scalar_bit_width_or_default
from tslc.lower.lowerer import LoweredSpecialization
from tslc.target_text import TemplateApplication
from tslc.support_policy import DEFAULT_SUPPORT_POLICY


def cpp_header_group(extension: Extension | None) -> str | None:
    return None if extension is None else extension.header_group_for_backend("cpp")


def _cpp_includes(
    emitted_exts: Sequence[str],
    extensions: Mapping[str, Extension],
) -> str:
    lines = [
        '#include "tsl_core.hpp"',
        '#include "tsl_primitives.hpp"',
        '#include "tsl_dataparallel.hpp"',
    ]
    if any(is_x86_register_extension(extensions.get(ext)) for ext in emitted_exts):
        lines.append('#include "tsl_x86_traits.hpp"')
    headers = sorted(
        {
            header
            for ext in emitted_exts
            if ext in extensions
            for header in extensions[ext].headers_for_backend("cpp")
        }
    )
    lines.extend(f"#include <{header}>" for header in headers)
    return "\n".join(lines) + "\n"


def _cpp_primitive_tags(profiles: tuple[EmittedProfile, ...]) -> str:
    names = sorted(
        {
            primitive
            for emitted_profile in profiles
            for primitive in emitted_profile.specializations("cpp")
        }
    )
    lines = [
        "#pragma once",
        "namespace tsl::primitive {",
        *(f"struct {name} {{}};" for name in names),
        "}  // namespace tsl::primitive",
        "",
    ]
    return "\n".join(lines)


def cpp_profiles_support_algorithm(profiles: tuple[EmittedProfile, ...]) -> bool:
    """Whether every emitted C++ profile can expose the static algorithm facade."""

    return bool(profiles) and all(
        CPP_HELPER_MANIFEST.supports(
            "algorithm", emitted_profile.specializations("cpp")
        )
        for emitted_profile in profiles
    )


def _guard_cpp_profile(
    content: str,
    emitted_exts: Sequence[str],
    extensions: Mapping[str, Extension],
) -> str:
    guards = resolve_cpp_compile_guards(emitted_exts, extensions).guards
    if not guards:
        return content
    condition = _cpp_compile_guard_condition(guards)
    diagnostic = "; ".join(_cpp_compile_guard_diagnostic(guard) for guard in guards)
    return (
        f"#if {condition}\n"
        f"{content}"
        "#else\n"
        f'#  error "{diagnostic}"\n'
        "#endif\n"
    )


def _cpp_compile_guard_condition(guards: Sequence[BackendCompileGuard]) -> str:
    return " && ".join(
        f"defined({guard.macro}) && {guard.macro} == {guard.equals}"
        for guard in guards
    )


def _cpp_compile_guard_diagnostic(guard: BackendCompileGuard) -> str:
    if guard.diagnostic:
        return guard.diagnostic
    if guard.hint_flag:
        return f"TSL profile requires {guard.hint_flag}"
    return f"TSL profile requires {guard.macro} == {guard.equals}"


def _cpp_registration(ext: str, extension: Extension | None) -> str:
    """A C++ extension tag + `simd<T, ext>` register/mask-type wiring for one ISA ext."""

    helper = cpp_x86_register_helper(extension)
    bits = extension.vector_bits if extension is not None else None
    assert helper is not None and bits is not None, (
        f"C++ profile validation missed unsupported x86 extension {ext!r}"
    )
    if extension is not None and extension.mask_policy.kind == "native_predicate_by_lanes":
        mask = f"typename detail::native_mask<{extension.vector_bits}, T>::type"
    else:
        mask = "register_type"
    imask = _cpp_imask_type(extension, bits, mask)
    alignment = max(1, bits // 8)
    return (
        f"struct {ext} {{}};\n"
        f"template <class T>\n"
        f"struct simd<T, {ext}> {{\n"
        f"    using base_type = T;\n"
        f"    using extension_type = {ext};\n"
        f"    using register_type = typename detail::{helper}<T>::type;\n"
        f"    using mask_type = {mask};\n"
        f"    using imask_type = {imask};\n"
        f"    template <class ToBase>\n"
        f"    using with_base_type = simd<ToBase, {ext}>;\n"
        f"    template <class ToExtension>\n"
        f"    using with_extension = simd<T, ToExtension>;\n"
        f"{_cpp_static_element_count_metadata(f'{bits} / (sizeof(T) * 8)')}"
        f"    static constexpr std::size_t vector_alignment = {alignment};\n"
        "    static constexpr std::size_t simd_register_alignment_v = vector_alignment;\n"
        f"}};\n\n"
    )


def _cpp_native_registration(
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    extensions: Mapping[str, Extension],
) -> str:
    """Register non-x86 native extensions from typed register spellings."""

    lines: list[str] = []
    emitted = {
        ext
        for ext, type_tag, _base in used_type_specs(by_primitive)
        if (extension := extensions.get(ext)) is not None
        and not is_x86_register_extension(extension)
        and extension.direct_vector_register_type("cpp", type_tag) is not None
    }
    for ext in sorted(emitted):
        lines.append(f"struct {ext} {{}};\n")
    for ext, type_tag, base in used_type_specs(by_primitive):
        extension = extensions.get(ext)
        if extension is None or is_x86_register_extension(extension):
            continue
        register = extension.direct_vector_register_type("cpp", type_tag)
        if register is None:
            continue
        bits = extension.vector_bits
        mask = _cpp_mask_type(
            extension,
            bits,
            register,
            base_type=base,
            type_tag=type_tag,
        )
        imask = _cpp_imask_type(extension, bits, mask, base_type=base)
        alignment = DEFAULT_SUPPORT_POLICY.vector_alignment_bytes(extension, type_tag)
        element_count = _cpp_element_count_metadata(extension, type_tag, base)
        lines.append(
            f"template <>\n"
            f"struct simd<{base}, {ext}> {{\n"
            f"    using base_type = {base};\n"
            f"    using extension_type = {ext};\n"
            f"    using register_type = {register};\n"
            f"    using mask_type = {mask};\n"
            f"    using imask_type = {imask};\n"
            f"    template <class ToBase>\n"
            f"    using with_base_type = simd<ToBase, {ext}>;\n"
            f"    template <class ToExtension>\n"
            f"    using with_extension = simd<{base}, ToExtension>;\n"
            f"{element_count}"
            f"    static constexpr std::size_t vector_alignment = {alignment};\n"
            "    static constexpr std::size_t simd_register_alignment_v = vector_alignment;\n"
            f"}};\n\n"
        )
    return "".join(lines)


def _cpp_sized_registration(
    emitted_exts: Sequence[str],
    extensions: Mapping[str, Extension],
) -> str:
    """Register profile-local sized vector tags that are not the static generic tag."""

    lines: list[str] = []
    for ext in emitted_exts:
        extension = extensions.get(ext)
        if (
            extension is None
            or ext == "generic"
            or not DEFAULT_SUPPORT_POLICY.uses_sized_vector(extension)
        ):
            continue
        mask = _cpp_sized_mask_type(extension)
        imask = _cpp_sized_imask_type(extension, mask)
        lines.append(
            f"template <std::size_t LANES>\n"
            f"struct {ext} {{}};\n\n"
            f"template <class T, std::size_t LANES>\n"
            f"struct simd<T, {ext}<LANES>> {{\n"
            "    static_assert((LANES * sizeof(T)) % 16 == 0,\n"
            f"                  \"tsl::{ext}<LANES>: LANES * sizeof(T) must be a "
            "multiple of 16 bytes (128 bits)\");\n"
            "    using base_type = T;\n"
            f"    using extension_type = {ext}<LANES>;\n"
            "    using register_type = array_type<T, LANES>;\n"
            f"    using mask_type = {mask};\n"
            f"    using imask_type = {imask};\n"
            "    template <class ToBase>\n"
            f"    using with_base_type = simd<ToBase, {ext}<LANES>>;\n"
            "    template <class ToExtension>\n"
            "    using with_extension = simd<T, ToExtension>;\n"
            "    static constexpr bool has_static_lane_count_v = true;\n"
            "    static constexpr std::size_t lane_count_v = LANES;\n"
            "    static constexpr std::size_t vector_element_count = lane_count_v;\n"
            "    static constexpr std::size_t lane_count() noexcept {\n"
            "        return lane_count_v;\n"
            "    }\n"
            "    static constexpr std::size_t vector_alignment = alignof(register_type);\n"
            "    static constexpr std::size_t simd_register_alignment_v = vector_alignment;\n"
            "};\n\n"
            f"template <class T, std::size_t LANES>\n"
            f"struct reg_param<simd<T, {ext}<LANES>>> {{\n"
            f"    using type = const typename simd<T, {ext}<LANES>>::register_type &;\n"
            "};\n\n"
        )
    return "".join(lines)


def _cpp_sized_mask_type(extension: Extension) -> str:
    if extension.mask_policy.kind == "exact_lane_bitmask":
        return extension.mask_policy.spelling("cpp") or "std::uint64_t"
    if extension.mask_policy.kind == "lane_bitmask":
        return "std::uint64_t"
    return "register_type"


def _cpp_sized_imask_type(extension: Extension, mask: str) -> str:
    if extension.imask_policy.kind == "same_as_mask_type":
        return mask
    return "std::uint64_t"


def _cpp_static_element_count_metadata(count_expr: str) -> str:
    return (
        "    static constexpr bool has_static_lane_count_v = true;\n"
        f"    static constexpr std::size_t lane_count_v = {count_expr};\n"
        "    static constexpr std::size_t vector_element_count = lane_count_v;\n"
        "    static constexpr std::size_t lane_count() noexcept {\n"
        "        return lane_count_v;\n"
        "    }\n"
    )


def _cpp_element_count_metadata(
    extension: Extension,
    type_tag: str,
    base_type: str,
) -> str:
    lane_count = DEFAULT_SUPPORT_POLICY.lane_count(extension, type_tag)
    if lane_count is not None:
        return _cpp_static_element_count_metadata(str(lane_count))
    runtime = extension.runtime_lane_count.get("cpp")
    assert runtime is not None, (
        "C++ profile validation missed a scalable runtime_lane_count entry for "
        f"extension {extension.name!r}"
    )
    runtime = TemplateApplication(
        f"{extension.name}.runtime_lane_count.cpp",
        runtime,
        {"base_type": base_type, "base": base_type, "type_tag": type_tag},
    ).render()
    return (
        "    static constexpr bool has_static_lane_count_v = false;\n"
        "    static std::size_t lane_count() noexcept {\n"
        f"        return {runtime};\n"
        "    }\n"
    )


def _cpp_inferred_simd_registrations(
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    extensions: Mapping[str, Extension],
) -> str:
    """Specialize C++ SIMD inference helpers for vectors in this profile."""

    candidates: dict[tuple[str, int], tuple[tuple[int, int, str], str]] = {}
    native_candidates: dict[str, tuple[tuple[int, int, str], str]] = {}
    for ext, type_tag, base in used_type_specs(by_primitive):
        extension = extensions.get(ext)
        if extension is None or DEFAULT_SUPPORT_POLICY.uses_sized_vector(extension):
            continue
        metadata = extension.metadata.backend.get("cpp")
        if metadata is not None and not metadata.participates_in_dataparallel_inference:
            continue
        if not _cpp_extension_register_is_available(extension, type_tag):
            continue
        preference = (
            extension.metadata.native_sort_order or 0,
            extension.vector_bits,
            extension.isa_name,
        )
        current_native = native_candidates.get(base)
        if current_native is None or preference > current_native[0]:
            native_candidates[base] = (preference, extension.isa_name)
        lane_count = DEFAULT_SUPPORT_POLICY.lane_count(extension, type_tag)
        if lane_count is None:
            continue
        if lane_count == 1:
            continue
        key = (base, lane_count)
        current = candidates.get(key)
        if current is None or preference > current[0]:
            candidates[key] = (preference, extension.isa_name)

    if not candidates and not native_candidates:
        return ""

    lines = ["namespace dataparallel {\n"]
    for (base, lane_count), (_preference, ext) in sorted(candidates.items()):
        lines.append(
            f"template <>\n"
            f"struct simd_for<fixed<{lane_count}>, {base}> {{\n"
            f"    using type = ::tsl::simd<{base}, ::tsl::{ext}>;\n"
            f"}};\n\n"
        )
    for base, (_preference, ext) in sorted(native_candidates.items()):
        lines.append(
            f"template <>\n"
            f"struct simd_for<native, {base}> {{\n"
            f"    using type = ::tsl::simd<{base}, ::tsl::{ext}>;\n"
            f"}};\n\n"
        )
    lines.append("}  // namespace dataparallel\n\n")
    return "".join(lines)


def _cpp_extension_register_is_available(extension: Extension, type_tag: str) -> bool:
    if extension.vector_bits <= 0 and not DEFAULT_SUPPORT_POLICY.uses_scalable_vector(extension):
        return True
    return is_x86_register_extension(extension) or (
        extension.direct_vector_register_type("cpp", type_tag) is not None
    )


def _cpp_mask_type(
    extension: Extension,
    vector_bits: int,
    register: str,
    *,
    base_type: str,
    type_tag: str,
) -> str:
    kind = extension.mask_policy.kind
    if kind == "native_predicate":
        return extension.mask_policy.spelling("cpp") or register
    if kind == "native_predicate_by_lanes":
        lanes = vector_bits // scalar_bit_width_or_default(type_tag)
        concrete = extension.mask_policy.spelling_for_lanes("cpp", max(8, lanes))
        if concrete is not None:
            return concrete
        return f"typename detail::native_mask<{vector_bits}, {base_type}>::type"
    return register


def _cpp_imask_type(
    extension: Extension | None,
    vector_bits: int,
    mask: str,
    *,
    base_type: str = "T",
) -> str:
    """The C++ integral-mask type for one x86 `simd<T, ext>` registration."""

    kind = extension.imask_policy.kind if extension is not None else "lane_bitmask"
    if kind == "same_as_mask_type":
        return mask
    return f"typename detail::lane_bitmask_int<{vector_bits}, {base_type}>::type"
