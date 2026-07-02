"""Render generated C++ project artifacts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from tslc.backend.cpp import CppBackend
from tslc.backend.target_capability import (
    cpp_x86_register_helper,
    is_x86_register_extension,
)
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import Extension
from tslc.catalog.target_families import ProfileFamilyCapability
from tslc.compiler_assets import RenderAssets
from tslc.lower.lowerer import LoweredSpecialization, varying_positions
from tslc.output.artifacts import Artifact
from tslc.output.verify_model import VerifyEmulator, VerifyProfile
from tslc.render._common import (
    feature_spelling,
    slug,
    text,
    type_bits,
    used_exts,
    used_type_specs,
)
from tslc.support_policy import DEFAULT_SUPPORT_POLICY

if TYPE_CHECKING:
    from tslc.render.project import ProfileRender


def cpp_artifacts(
    profiles: tuple[ProfileRender, ...], assets: RenderAssets
) -> list[Artifact]:
    backend = CppBackend()
    artifacts = [
        text("cpp/include/tsl_core.hpp", assets.text("tsl_core.hpp")),
        text("cpp/include/tsl_inferred_simd.hpp", assets.text("tsl_inferred_simd.hpp")),
        text("cpp/include/tsl_algorithm.hpp", assets.text("tsl_algorithm.hpp")),
        text("cpp/include/tsl_x86_traits.hpp", assets.text("tsl_x86_traits.hpp")),
        # Ship the formatter config at the C++ project root so `clang-format` (ascending from
        # include/ and tests/) finds it and the generated project is self-contained.
        text("cpp/.clang-format", assets.text(".clang-format")),
    ]
    for profile_render in profiles:
        by_primitive = profile_render.specializations("cpp")
        emitted_exts = used_exts(by_primitive)
        x86_exts = [
            e
            for e in emitted_exts
            if is_x86_register_extension(profile_render.extensions.get(e))
        ]
        includes = _cpp_includes(emitted_exts, profile_render.extensions)
        registrations = "".join(
            _cpp_registration(ext, profile_render.extensions.get(ext))
            for ext in x86_exts
        )
        registrations += _cpp_native_registration(
            by_primitive, profile_render.extensions
        )
        registrations += _cpp_inferred_simd_registrations(
            by_primitive, profile_render.extensions
        )
        # All declarations (impl primary templates + wrappers) precede all
        # specialization bodies, so any body may call any primitive's wrapper.
        declarations = "\n\n".join(
            backend.render_declarations(name, by_primitive[name])
            for name in sorted(by_primitive)
        )
        definitions = "\n\n".join(
            backend.render_definitions(name, by_primitive[name])
            for name in sorted(by_primitive)
        )
        bodies = declarations + "\n\n" + definitions
        content = assets.fill(
            "cpp_profile_header.hpp.tmpl",
            includes=includes,
            registrations=registrations,
            bodies=bodies,
        )
        profile_slug = slug(profile_render.profile.name)
        artifacts.append(text(f"cpp/include/tsl_{profile_slug}.hpp", content))
        artifacts.append(text(f"cpp/tests/smoke_{profile_slug}.cpp", _cpp_smoke(profile_render)))

    artifacts.append(
        text(
            "cpp/include/tsl.hpp",
            _cpp_dispatch(
                profiles,
                include_algorithm=_cpp_profiles_support_algorithm(profiles),
            ),
        )
    )
    artifacts.append(
        text("cpp/docs/input/tsl_api_docs.hpp", _cpp_documentation_facade(profiles))
    )
    artifacts.append(text("cpp/CMakeLists.txt", _cpp_cmakelists(profiles, assets)))
    return artifacts


def cpp_verify_profiles(profiles: tuple[ProfileRender, ...]) -> tuple[VerifyProfile, ...]:
    return tuple(
        VerifyProfile(
            profile_name=slug(profile_render.profile.name),
            file_stem=slug(profile_render.profile.name),
            family=profile_render.profile.family,
            cpp_flags=cpp_flags(profile_render.profile, profile_render.profile_family),
            cpp_target=cpp_target(profile_render.profile, profile_render.profile_family),
            emulator=_verify_emulator(profile_render.profile),
        )
        for profile_render in profiles
    )


def cpp_flags(
    profile: MachineProfile,
    capability: ProfileFamilyCapability | None = None,
) -> tuple[str, ...]:
    capability = capability or ProfileFamilyCapability(profile.family)
    if not capability.cpp_feature_flags:
        return profile.cpp_flags
    return (
        *(
            f"-m{feature_spelling(feature, profile.alternatives)}"
            for feature in sorted(profile.features)
        ),
        *profile.cpp_flags,
    )


def cpp_target(
    profile: MachineProfile,
    capability: ProfileFamilyCapability | None = None,
) -> str | None:
    capability = capability or ProfileFamilyCapability(profile.family)
    return capability.cpp_target


def _verify_emulator(profile: MachineProfile) -> VerifyEmulator | None:
    if profile.emulator is None:
        return None
    return VerifyEmulator(
        kind=profile.emulator.kind,
        profile=profile.emulator.profile,
        args=profile.emulator.args,
    )


def _cpp_includes(emitted_exts: list[str], extensions: Mapping[str, Extension]) -> str:
    lines = ['#include "tsl_core.hpp"', '#include "tsl_inferred_simd.hpp"']
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


def _cpp_registration(ext: str, extension: Extension | None) -> str:
    """A C++ extension tag + `simd<T, ext>` register/mask-type wiring for one ISA ext."""

    helper = cpp_x86_register_helper(extension)
    bits = extension.vector_bits if extension is not None else None
    if helper is None or bits is None:
        raise ValueError(f"unsupported C++ x86 register extension {ext!r}")
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
        f"    using register_type = typename detail::{helper}<T>::type;\n"
        f"    using mask_type = {mask};\n"
        f"    using imask_type = {imask};\n"
        f"{_cpp_static_element_count_metadata(f'{bits} / (sizeof(T) * 8)')}"
        f"    static constexpr std::size_t vector_alignment = {alignment};\n"
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
        mask = _cpp_mask_type(extension, bits, register, base_type=base)
        imask = _cpp_imask_type(extension, bits, mask, base_type=base)
        alignment = DEFAULT_SUPPORT_POLICY.vector_alignment_bytes(extension, type_tag)
        element_count = _cpp_element_count_metadata(extension, type_tag, base)
        lines.append(
            f"template <>\n"
            f"struct simd<{base}, {ext}> {{\n"
            f"    using base_type = {base};\n"
            f"    using register_type = {register};\n"
            f"    using mask_type = {mask};\n"
            f"    using imask_type = {imask};\n"
            f"{element_count}"
            f"    static constexpr std::size_t vector_alignment = {alignment};\n"
            f"}};\n\n"
        )
    return "".join(lines)


def _cpp_static_element_count_metadata(count_expr: str) -> str:
    return (
        "    static constexpr bool has_static_vector_element_count = true;\n"
        f"    static constexpr std::size_t vector_element_count = {count_expr};\n"
        "    static constexpr std::size_t vector_element_count_runtime() noexcept {\n"
        "        return vector_element_count;\n"
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
    if runtime is None:
        raise ValueError(
            f"extension {extension.name!r} needs runtime_lane_count.cpp for "
            "scalable C++ vector registration"
        )
    runtime = (
        runtime.replace("{base_type}", base_type)
        .replace("{base}", base_type)
        .replace("{type_tag}", type_tag)
    )
    return (
        "    static constexpr bool has_static_vector_element_count = false;\n"
        "    static std::size_t vector_element_count_runtime() noexcept {\n"
        f"        return {runtime};\n"
        "    }\n"
    )


def _cpp_inferred_simd_registrations(
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    extensions: Mapping[str, Extension],
) -> str:
    """Specialize ``inferred_simd<T, N>`` for fixed-width vectors in this profile."""

    candidates: dict[tuple[str, int], tuple[tuple[int, int, str], str]] = {}
    for ext, type_tag, base in used_type_specs(by_primitive):
        extension = extensions.get(ext)
        if extension is None or DEFAULT_SUPPORT_POLICY.uses_sized_vector(extension):
            continue
        lane_count = DEFAULT_SUPPORT_POLICY.lane_count(extension, type_tag)
        if lane_count is None:
            continue
        if (
            extension.vector_bits > 0
            and not is_x86_register_extension(extension)
            and extension.direct_vector_register_type("cpp", type_tag) is None
        ):
            continue
        preference = (
            extension.metadata.native_sort_order or 0,
            extension.vector_bits,
            extension.isa_name,
        )
        key = (base, lane_count)
        current = candidates.get(key)
        if current is None or preference > current[0]:
            candidates[key] = (preference, extension.isa_name)

    if not candidates:
        return ""

    lines = ["namespace detail {\n"]
    for (base, lane_count), (_preference, ext) in sorted(candidates.items()):
        lines.append(
            f"template <>\n"
            f"struct inferred_simd<{base}, {lane_count}> {{\n"
            f"    using type = ::tsl::simd<{base}, ::tsl::{ext}>;\n"
            f"}};\n\n"
        )
    lines.append("}  // namespace detail\n\n")
    return "".join(lines)


def _cpp_mask_type(
    extension: Extension,
    vector_bits: int,
    register: str,
    *,
    base_type: str,
) -> str:
    kind = extension.mask_policy.kind
    if kind == "native_predicate":
        return extension.mask_policy.spelling("cpp") or register
    if kind == "native_predicate_by_lanes":
        lanes = vector_bits // type_bits(base_type)
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


def _cpp_profiles_support_algorithm(profiles: tuple[ProfileRender, ...]) -> bool:
    if not profiles:
        return False
    return all(
        {"load", "store"} <= set(profile_render.specializations("cpp"))
        for profile_render in profiles
    )


def _cpp_dispatch(
    profiles: tuple[ProfileRender, ...],
    *,
    include_algorithm: bool = False,
) -> str:
    lines = ["#pragma once", ""]
    for index, profile_render in enumerate(profiles):
        profile_slug = slug(profile_render.profile.name)
        keyword = "#if" if index == 0 else "#elif"
        lines.append(f"{keyword} defined(TSL_PROFILE_{profile_slug.upper()})")
        lines.append(f'#  include "tsl_{profile_slug}.hpp"')
    lines.append("#else")
    lines.append('#  error "No supported TSL profile selected"')
    lines.append("#endif")
    if include_algorithm:
        lines.append('#include "tsl_algorithm.hpp"')
    return "\n".join(lines) + "\n"


def _cpp_documentation_facade(profiles: tuple[ProfileRender, ...]) -> str:
    backend = CppBackend()
    api_declarations: list[str] = []
    seen_api: set[str] = set()
    for profile_render in profiles:
        by_primitive = profile_render.specializations("cpp")
        for name in sorted(by_primitive):
            declaration = backend.render_documentation_api_declaration(
                name, by_primitive[name]
            )
            if declaration not in seen_api:
                api_declarations.append(declaration)
                seen_api.add(declaration)
    sections = [
        "\n".join(
            (
                "#pragma once",
                "",
                "// Documentation-only facade. This file is intentionally not part of",
                "// the generated C++ implementation surface.",
                "",
                "namespace tsl {",
            )
        ),
        *api_declarations,
        "}  // namespace tsl",
    ]
    return "\n\n".join(section.rstrip() for section in sections if section.strip()) + "\n"


def _cpp_smoke(profile_render: ProfileRender) -> str:
    # Address-take every emitted wrapper instantiation so the profile's bodies are
    # fully compiled (with the profile's ISA flags), not merely parsed.
    lines = ["#include <tsl.hpp>", "", "namespace {"]
    index = 0
    by_primitive = profile_render.specializations("cpp")
    for name in sorted(by_primitive):
        specs = by_primitive[name]
        first = specs[0]
        if DEFAULT_SUPPORT_POLICY.is_free_function_signature(
            first.result_kind,
            first.param_kinds,
        ):
            # A free function (`allocate`/`deallocate`) is not a template — address-take it
            # directly (once), so its body is compiled under the profile's flags.
            lines.append(f"auto* _tsl_use_{index} = &tsl::{name};")
            index += 1
            continue
        varying = varying_positions(specs)
        for spec in specs:
            if spec.uses_sized_vector:
                # A MONOMORPHIZED sized slot (numeric `lane_parameter`) only has that one concrete
                # instantiation — exercise it there. A `LANES`-parametric slot is exercised at 16
                # lanes: the sized substrate requires every vector's total width be a multiple of
                # 128 bits, and 16 * 8 (the narrowest lane type) = 128 — so 16 keeps BOTH the source
                # AND a width-changing lane-preserving target (e.g. a `cast` i16->i8) a whole number
                # of 128-bit registers, where a per-type `128 / typebits` would not.
                smoke_lanes = (
                    int(spec.lane_parameter)
                    if spec.lane_parameter and spec.lane_parameter.isdigit()
                    else 16
                )
                vec = f"tsl::simd<{spec.base_type_spelling}, tsl::generic<{smoke_lanes}>>"
            else:
                smoke_lanes = 8
                vec = f"tsl::simd<{spec.base_type_spelling}, tsl::{spec.extension_name}>"
            # A sized-vector representation-change target is instantiated at a concrete lane count
            # matching the source's. A lane-PRESERVING target (cast/reinterpret, load_convert_up)
            # keeps the same count; a WINDOWING convert's count scales by the byte ratio — computed
            # from the source/target type widths (e.g. i8->i16 at 8 lanes -> 4), matching the impl
            # that deduces LANES from the source. Computed from typed widths, not a string rewrite.
            if spec.target is None:
                target_spelling = None
            elif spec.target.uses_sized_vector:
                target_lanes = (
                    DEFAULT_SUPPORT_POLICY.windowed_lane_count(
                        spec.type_tag, spec.target.base_tag, smoke_lanes
                    )
                    if spec.target.windowed
                    else smoke_lanes
                )
                target_spelling = (
                    f"tsl::simd<{spec.target.base_spelling}, tsl::generic<{target_lanes}>>"
                )
            else:
                target_spelling = spec.target.vector_spelling
            targs = (
                [vec]
                + ([target_spelling] if target_spelling else [])
                + [vec for _ in spec.type_params]
                + [value for _, value in spec.axis]
                + (["0"] if spec.immediate is not None else [])
                + [default for _, _, default in spec.generic_params]
                + [_concrete_arg_type(vec, spec.param_kinds[i]) for i in varying]
            )
            lines.append(f"auto* _tsl_use_{index} = &tsl::{name}<{', '.join(targs)}>;")
            index += 1
    lines.append("}  // namespace")
    lines.append("")
    lines.append("int main() {")
    for used in range(index):
        lines.append(f"  (void)_tsl_use_{used};")
    lines.append("  return 0;")
    lines.append("}")
    return "\n".join(lines) + "\n"


def _concrete_arg_type(vec: str, kind: str) -> str:
    """The concrete dispatch-argument type for an overloaded wrapper instantiation."""

    if kind == "v":
        return f"{vec}::register_type"
    if kind == "m":
        return f"{vec}::mask_type"
    if DEFAULT_SUPPORT_POLICY.is_const_pointer_kind(kind):
        return f"{vec}::base_type const *"
    if DEFAULT_SUPPORT_POLICY.is_mutable_pointer_kind(kind):
        return f"{vec}::base_type *"
    if kind in {"s[]", DEFAULT_SUPPORT_POLICY.lane_list_kind}:
        return f"::tsl::array_param<{vec}>::type"
    return f"{vec}::base_type"


def _cpp_cmakelists(profiles: tuple[ProfileRender, ...], assets: RenderAssets) -> str:
    slugs = tuple(slug(profile.profile.name) for profile in profiles)
    fallback = "scalar" if "scalar" in slugs else slugs[0]
    rendered = assets.fill(
        "cpp_cmakelists.txt.tmpl",
        available_profiles=_cmake_list(slugs),
        profile_choices=" ".join(
            _cmake_quote(value)
            for value in (*slugs, *_profile_alias_choices(profiles))
        ),
        profile_aliases=_cpp_profile_aliases(profiles),
        fallback_profile=fallback,
        profile_detection=_cpp_profile_detection(profiles, fallback),
        profile_targets=_cpp_profile_targets(profiles),
    )
    return rendered.rstrip("\n") + "\n"


def _profile_alias_choices(profiles: tuple[ProfileRender, ...]) -> tuple[str, ...]:
    return tuple(
        profile.profile.name
        for profile in profiles
        if profile.profile.name != slug(profile.profile.name)
    )


def _cpp_profile_aliases(profiles: tuple[ProfileRender, ...]) -> str:
    lines: list[str] = []
    for profile_render in profiles:
        profile_name = profile_render.profile.name
        profile_slug = slug(profile_name)
        if profile_name == profile_slug:
            continue
        lines.append(f'if(_TSL_REQUESTED_PROFILE STREQUAL "{profile_name}")')
        lines.append(f'  set(_TSL_REQUESTED_PROFILE "{profile_slug}")')
        lines.append("endif()")
    return "\n".join(lines)


def _cpp_profile_targets(profiles: tuple[ProfileRender, ...]) -> str:
    blocks: list[str] = []
    for profile_render in profiles:
        profile_slug = slug(profile_render.profile.name)
        target = f"tsl_profile_{profile_slug}"
        lines = [
            f"add_library({target} INTERFACE)",
            f"add_library(tsl::{profile_slug} ALIAS {target})",
            f"target_include_directories({target} INTERFACE",
            '  "$<BUILD_INTERFACE:${CMAKE_CURRENT_LIST_DIR}/include>"',
            '  "$<INSTALL_INTERFACE:include>"',
            ")",
            f"target_compile_features({target} INTERFACE cxx_std_17)",
            (
                f"target_compile_definitions({target} INTERFACE "
                f"TSL_PROFILE_{profile_slug.upper()})"
            ),
        ]
        flags = cpp_flags(profile_render.profile, profile_render.profile_family)
        if flags:
            lines.append(
                f"target_compile_options({target} INTERFACE "
                + " ".join(_cmake_cxx_flag(flag) for flag in flags)
                + ")"
            )
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _cpp_profile_detection(
    profiles: tuple[ProfileRender, ...],
    fallback_profile: str,
) -> str:
    blocks: list[str] = []
    for profile_render in _auto_detection_order(profiles):
        profile = profile_render.profile
        profile_slug = slug(profile.name)
        if profile_slug == fallback_profile and not profile.features:
            continue
        source = _cpp_profile_detection_source(profile, profile_render.profile_family)
        if source is None:
            continue
        variable = "TSL_CPU_HAS_" + profile_slug.upper()
        blocks.append(
            "\n".join(
                (
                    f"    check_cxx_source_runs([=[\n{source}\n]=] {variable})",
                    f"    if({variable})",
                    f'      set(TSL_SELECTED_PROFILE "{profile_slug}")',
                    "    endif()",
                )
            )
        )
    return "\n".join(blocks)


def _auto_detection_order(
    profiles: tuple[ProfileRender, ...],
) -> tuple[ProfileRender, ...]:
    return tuple(
        sorted(
            profiles,
            key=lambda profile: (
                _profile_family_sort_order(profile),
                len(profile.profile.features),
                slug(profile.profile.name),
            ),
        )
    )


def _profile_family_sort_order(profile: ProfileRender) -> int:
    if profile.profile_family is None:
        return ProfileFamilyCapability(profile.profile.family).sort_order
    return profile.profile_family.sort_order


def _cpp_profile_detection_source(
    profile: MachineProfile,
    capability: ProfileFamilyCapability | None,
) -> str | None:
    capability = capability or ProfileFamilyCapability(profile.family)
    if capability.cpp_detection is None:
        return None
    renderer = _CPP_DETECTION_RENDERERS.get(capability.cpp_detection)
    if renderer is None:
        return None
    return renderer(profile)


def _x86_profile_detection_source(profile: MachineProfile) -> str:
    checks = tuple(
        f'__builtin_cpu_supports("{feature_spelling(feature, profile.alternatives)}")'
        for feature in sorted(profile.features)
    )
    condition = " && ".join(checks) if checks else "1"
    return "\n".join(
        (
            "int main() {",
            "#if (defined(__x86_64__) || defined(__i386__)) && (defined(__GNUC__) || defined(__clang__))",
            "  __builtin_cpu_init();",
            f"  return ({condition}) ? 0 : 1;",
            "#else",
            "  return 1;",
            "#endif",
            "}",
        )
    )


def _aarch64_profile_detection_source(profile: MachineProfile) -> str | None:
    if "sve" in profile.features:
        return "\n".join(
            (
                "#if defined(__linux__) && defined(__aarch64__)",
                "#  include <sys/auxv.h>",
                "#  include <asm/hwcap.h>",
                "#endif",
                "int main() {",
                "#if defined(__linux__) && defined(__aarch64__) && defined(HWCAP_SVE)",
                "  return (getauxval(AT_HWCAP) & HWCAP_SVE) ? 0 : 1;",
                "#else",
                "  return 1;",
                "#endif",
                "}",
            )
        )
    if "neon" in profile.features:
        return "\n".join(
            (
                "int main() {",
                "#if defined(__aarch64__)",
                "  return 0;",
                "#else",
                "  return 1;",
                "#endif",
                "}",
            )
        )
    return None


_CPP_DETECTION_RENDERERS = {
    "x86_builtin": _x86_profile_detection_source,
    "aarch64_hwcaps": _aarch64_profile_detection_source,
}


def _cmake_list(values: Sequence[str]) -> str:
    return " ".join(_cmake_quote(value) for value in values)


def _cmake_quote(value: str) -> str:
    escaped = value.translate(str.maketrans({'"': r"\"", "\\": r"\\"}))
    return '"' + escaped + '"'


def _cmake_cxx_flag(flag: str) -> str:
    return f"$<$<CXX_COMPILER_ID:GNU,Clang,AppleClang>:{flag}>"
