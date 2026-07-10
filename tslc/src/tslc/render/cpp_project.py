"""Render generated C++ project artifacts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from tslc.backend.cpp import CppBackend
from tslc.backend.cpp_validation import resolve_cpp_compile_guards
from tslc.backend.emitted_profile import (
    EmittedProfile,
    used_extensions,
    used_type_specs,
)
from tslc.backend.target_capability import (
    cpp_x86_register_helper,
    feature_spelling,
    is_x86_register_extension,
)
from tslc.backend.helper_requirements import CPP_HELPER_MANIFEST
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import BackendCompileGuard, Extension
from tslc.catalog.scalar_types import scalar_bit_width_or_default
from tslc.catalog.target_families import ProfileFamilyCapability
from tslc.compiler_assets import RenderAssets
from tslc.lower.lowerer import LoweredSpecialization, varying_positions
from tslc.output.artifacts import Artifact
from tslc.output.verify_model import VerifyProfile, VerifyRunner
from tslc.render._common import slug, text
from tslc.target_text import TemplateApplication
from tslc.support_policy import DEFAULT_SUPPORT_POLICY

_CPP_STATIC_HEADERS = (
    "tsl_core.hpp",
    "tsl_dataparallel.hpp",
    "tsl_algorithm_tags.hpp",
    "tsl_algorithm_detail_core.hpp",
    "tsl_algorithm_detail_mask.hpp",
    "tsl_algorithm_detail_loops.hpp",
    "tsl_algorithm.hpp",
    "tsl_x86_traits.hpp",
)
_CMAKE_CXX_FEATURE_FLAG_COMPILERS = "GNU,Clang,AppleClang,IntelLLVM"


def cpp_artifacts(
    profiles: tuple[EmittedProfile, ...],
    assets: RenderAssets,
    *,
    media_type: str,
) -> list[Artifact]:
    backend = CppBackend()
    artifacts = [
        text(f"cpp/include/{header}", assets.text(header), media_type=media_type)
        for header in _CPP_STATIC_HEADERS
    ] + [
        text(
            "cpp/include/tsl_primitives.hpp",
            _cpp_primitive_tags(profiles),
            media_type=media_type,
        ),
        # Ship the formatter config at the C++ project root so `clang-format` (ascending from
        # include/ and tests/) finds it and the generated project is self-contained.
        text("cpp/.clang-format", assets.text(".clang-format"), media_type=media_type),
    ]
    for emitted_profile in profiles:
        by_primitive = emitted_profile.specializations("cpp")
        emitted_exts = used_extensions(by_primitive)
        x86_exts = [
            e
            for e in emitted_exts
            if is_x86_register_extension(emitted_profile.extensions.get(e))
        ]
        includes = _cpp_includes(emitted_exts, emitted_profile.extensions)
        registrations = "".join(
            _cpp_registration(ext, emitted_profile.extensions.get(ext))
            for ext in x86_exts
        )
        registrations += _cpp_sized_registration(
            emitted_exts, emitted_profile.extensions
        )
        registrations += _cpp_native_registration(
            by_primitive, emitted_profile.extensions
        )
        registrations += _cpp_inferred_simd_registrations(
            by_primitive, emitted_profile.extensions
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
        content = _guard_cpp_profile(
            content,
            used_extensions(by_primitive),
            emitted_profile.extensions,
        )
        profile_slug = slug(emitted_profile.profile.name)
        artifacts.append(
            text(
                f"cpp/include/tsl_{profile_slug}.hpp",
                content,
                media_type=media_type,
            )
        )
        artifacts.append(
            text(
                f"cpp/tests/smoke_{profile_slug}.cpp",
                _cpp_smoke(emitted_profile),
                media_type=media_type,
            )
        )

    artifacts.append(
        text(
            "cpp/include/tsl.hpp",
            _cpp_dispatch(
                profiles,
                include_algorithm=_cpp_profiles_support_algorithm(profiles),
            ),
            media_type=media_type,
        )
    )
    artifacts.append(
        text(
            "cpp/docs/input/tsl_api_docs.hpp",
            _cpp_documentation_facade(profiles),
            media_type=media_type,
        )
    )
    artifacts.append(
        text(
            "cpp/CMakeLists.txt",
            _cpp_cmakelists(profiles, assets),
            media_type=media_type,
        )
    )
    return artifacts


def cpp_verify_profiles(profiles: tuple[EmittedProfile, ...]) -> tuple[VerifyProfile, ...]:
    return tuple(
        VerifyProfile(
            profile_name=slug(emitted_profile.profile.name),
            file_stem=slug(emitted_profile.profile.name),
            family=emitted_profile.profile.family,
            compile_modes=emitted_profile.profile.compile_modes,
            cpp_flags=cpp_flags(emitted_profile.profile, emitted_profile.profile_family),
            cpp_target=cpp_target(emitted_profile.profile, emitted_profile.profile_family),
            runner=_verify_runner(emitted_profile.profile),
        )
        for emitted_profile in profiles
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


def _verify_runner(profile: MachineProfile) -> VerifyRunner | None:
    if profile.runner is None:
        return None
    return VerifyRunner(
        kind=profile.runner.kind,
        profile=profile.runner.profile,
        args=profile.runner.args,
    )


def _cpp_includes(emitted_exts: list[str], extensions: Mapping[str, Extension]) -> str:
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


def _cpp_profiles_support_algorithm(profiles: tuple[EmittedProfile, ...]) -> bool:
    if not profiles:
        return False
    return all(
        CPP_HELPER_MANIFEST.supports(
            "algorithm", emitted_profile.specializations("cpp")
        )
        for emitted_profile in profiles
    )


def _cpp_dispatch(
    profiles: tuple[EmittedProfile, ...],
    *,
    include_algorithm: bool = False,
) -> str:
    lines = ["#pragma once", ""]
    for index, emitted_profile in enumerate(profiles):
        profile_slug = slug(emitted_profile.profile.name)
        keyword = "#if" if index == 0 else "#elif"
        lines.append(f"{keyword} defined(TSL_PROFILE_{profile_slug.upper()})")
        lines.append(f'#  include "tsl_{profile_slug}.hpp"')
    lines.append("#else")
    lines.append('#  error "No supported TSL profile selected"')
    lines.append("#endif")
    if include_algorithm:
        lines.append('#include "tsl_algorithm.hpp"')
    return "\n".join(lines) + "\n"


def _cpp_documentation_facade(profiles: tuple[EmittedProfile, ...]) -> str:
    backend = CppBackend()
    api_declarations: list[str] = []
    seen_api: set[str] = set()
    for emitted_profile in profiles:
        by_primitive = emitted_profile.specializations("cpp")
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


def _cpp_smoke(emitted_profile: EmittedProfile) -> str:
    # Address-take every emitted wrapper instantiation so the profile's bodies are
    # fully compiled (with the profile's ISA flags), not merely parsed.
    lines = ["#include <tsl.hpp>", "", "namespace {"]
    index = 0
    by_primitive = emitted_profile.specializations("cpp")
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
                vec = _cpp_sized_vector_type(
                    spec.base_type_spelling,
                    spec.extension_name,
                    smoke_lanes,
                )
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
                target_spelling = _cpp_sized_vector_type(
                    spec.target.base_spelling,
                    spec.target.extension_isa,
                    target_lanes,
                )
            else:
                target_spelling = spec.target.vector_spelling
            targs = (
                [vec]
                + ([target_spelling] if target_spelling else [])
                + [
                    _cpp_type_param_smoke_vector(spec, param, smoke_lanes)
                    for param in spec.type_params
                ]
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


def _cpp_type_param_smoke_vector(
    spec: LoweredSpecialization, param, smoke_lanes: int  # noqa: ANN001
) -> str:
    base = param.base_type_binding_spelling or spec.base_type_spelling
    if spec.uses_sized_vector:
        return _cpp_sized_vector_type(base, spec.extension_name, smoke_lanes)
    return f"tsl::simd<{base}, tsl::{spec.extension_name}>"


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


def _cpp_sized_vector_type(base_spelling: str, extension_name: str, lanes: int) -> str:
    return f"tsl::simd<{base_spelling}, tsl::{extension_name}<{lanes}>>"


def _cpp_cmakelists(profiles: tuple[EmittedProfile, ...], assets: RenderAssets) -> str:
    slugs = tuple(slug(profile.profile.name) for profile in profiles)
    ungated_slugs = tuple(
        slug(profile.profile.name)
        for profile in profiles
        if profile.profile.auto_detect_gate is None
    )
    fallback = (
        "scalar"
        if "scalar" in ungated_slugs
        else ungated_slugs[0]
        if ungated_slugs
        else ""
    )
    auto_choices = _cpp_profile_auto_choices(profiles)
    rendered = assets.fill(
        "cpp_cmakelists.txt.tmpl",
        available_profiles=_cmake_list(slugs),
        profile_choices=" ".join(
            _cmake_quote(value)
            for value in (*slugs, *_profile_alias_choices(profiles))
        ),
        profile_auto_choices=" ".join(
            _cmake_quote(value) for value in auto_choices
        ),
        profile_aliases=_cpp_profile_aliases(profiles),
        profile_auto_helpers=_cpp_profile_auto_helpers(profiles, assets),
        profile_auto_hint=_cpp_profile_auto_hint(auto_choices),
        fallback_profile=fallback,
        profile_detection=_cpp_profile_detection(profiles, fallback, auto_gate=None),
        profile_auto_modes=_cpp_profile_auto_modes(profiles),
        profile_targets=_cpp_profile_targets(profiles),
    )
    return rendered.rstrip("\n") + "\n"


def _profile_alias_choices(profiles: tuple[EmittedProfile, ...]) -> tuple[str, ...]:
    return tuple(
        profile.profile.name
        for profile in profiles
        if profile.profile.name != slug(profile.profile.name)
    )


def _cpp_profile_auto_choices(profiles: tuple[EmittedProfile, ...]) -> tuple[str, ...]:
    return tuple(
        _cpp_profile_auto_mode_name(gate)
        for gate in _cpp_profile_auto_gates(profiles)
    )


def _cpp_profile_auto_hint(auto_choices: tuple[str, ...]) -> str:
    if not auto_choices:
        return ""
    return " or one of: " + ", ".join(auto_choices)


def _cpp_profile_auto_helpers(
    profiles: tuple[EmittedProfile, ...],
    assets: RenderAssets,
) -> str:
    if not _cpp_profile_auto_gates(profiles):
        return ""
    return assets.text("cpp_profile_auto_helpers.cmake").strip()


def _cpp_profile_aliases(profiles: tuple[EmittedProfile, ...]) -> str:
    lines: list[str] = []
    for emitted_profile in profiles:
        profile_name = emitted_profile.profile.name
        profile_slug = slug(profile_name)
        if profile_name == profile_slug:
            continue
        lines.append(f'if(_TSL_REQUESTED_PROFILE STREQUAL "{profile_name}")')
        lines.append(f'  set(_TSL_REQUESTED_PROFILE "{profile_slug}")')
        lines.append("endif()")
    return "\n".join(lines)


def _cpp_profile_targets(profiles: tuple[EmittedProfile, ...]) -> str:
    blocks: list[str] = []
    for emitted_profile in profiles:
        profile_slug = slug(emitted_profile.profile.name)
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
        flags = cpp_flags(emitted_profile.profile, emitted_profile.profile_family)
        if flags:
            lines.append(
                f"target_compile_options({target} INTERFACE "
                + " ".join(_cmake_cxx_flag(flag) for flag in flags)
                + ")"
            )
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _cpp_profile_detection(
    profiles: tuple[EmittedProfile, ...],
    fallback_profile: str,
    *,
    auto_gate: str | None,
) -> str:
    blocks: list[str] = []
    for emitted_profile in _auto_detection_order(profiles):
        profile = emitted_profile.profile
        profile_slug = slug(profile.name)
        if profile.auto_detect_gate != auto_gate:
            continue
        if profile_slug == fallback_profile and not profile.features:
            continue
        source = _cpp_profile_detection_source(emitted_profile)
        if source is None:
            continue
        variable = "TSL_CPU_HAS_" + profile_slug.upper()
        block = "\n".join(
            (
                f"    check_cxx_source_runs([=[\n{source}\n]=] {variable})",
                f"    if({variable})",
                f'      set(TSL_SELECTED_PROFILE "{profile_slug}")',
                "    endif()",
            )
        )
        blocks.append(block)
    return "\n".join(blocks)


def _cpp_profile_auto_modes(profiles: tuple[EmittedProfile, ...]) -> str:
    blocks: list[str] = []
    for gate in _cpp_profile_auto_gates(profiles):
        gated_profiles = tuple(
            profile for profile in profiles if profile.profile.auto_detect_gate == gate
        )
        gated_slugs = tuple(slug(profile.profile.name) for profile in gated_profiles)
        if not gated_slugs:
            continue
        mode = _cpp_profile_auto_mode_name(gate)
        detection = _cpp_profile_detection(gated_profiles, "", auto_gate=gate)
        lines = [
            f'elseif(_TSL_REQUESTED_PROFILE STREQUAL "{mode}")',
            '  set(TSL_SELECTED_PROFILE "")',
            f'  _tsl_detect_profile_gate("{gate}" _TSL_GATE_READY _TSL_GATE_REASON)',
            "  if(NOT _TSL_GATE_READY)",
            (
                f'    message(FATAL_ERROR "TSL_PROFILE={mode} requested, but '
                f'{gate} auto-detection failed: ${{_TSL_GATE_REASON}}")'
            ),
            "  endif()",
            "  if(CMAKE_CROSSCOMPILING)",
            (
                f'    message(FATAL_ERROR "TSL_PROFILE={mode} cannot run CPU '
                'profile probes while cross-compiling")'
            ),
            "  else()",
            "    include(CheckCXXSourceRuns)",
        ]
        if detection:
            lines.append(detection)
        lines.extend(
            [
                '    if(TSL_SELECTED_PROFILE STREQUAL "")',
                (
                    f'      message(FATAL_ERROR "TSL_PROFILE={mode} verified '
                    f'{gate}, but no generated gated profile matched this CPU. '
                    f'Available gated profiles: {", ".join(gated_slugs)}")'
                ),
                "    endif()",
                f'    message(STATUS "TSL_PROFILE={mode} selected profile = ${{TSL_SELECTED_PROFILE}}")',
                "  endif()",
            ]
        )
        blocks.append("\n".join(lines))
    return "\n".join(blocks)


def _cpp_profile_auto_gates(profiles: tuple[EmittedProfile, ...]) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                profile.profile.auto_detect_gate
                for profile in profiles
                if profile.profile.auto_detect_gate is not None
            }
        )
    )


def _cpp_profile_auto_mode_name(gate: str) -> str:
    return "auto-" + slug(gate).replace("_", "-")


def _indent_lines(text: str, prefix: str) -> str:
    return "\n".join(prefix + line if line else line for line in text.splitlines())


def _auto_detection_order(
    profiles: tuple[EmittedProfile, ...],
) -> tuple[EmittedProfile, ...]:
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


def _profile_family_sort_order(profile: EmittedProfile) -> int:
    if profile.profile_family is None:
        return ProfileFamilyCapability(profile.profile.family).sort_order
    return profile.profile_family.sort_order


def _cpp_profile_detection_source(
    emitted_profile: EmittedProfile,
) -> str | None:
    profile = emitted_profile.profile
    capability = emitted_profile.profile_family
    capability = capability or ProfileFamilyCapability(profile.family)
    if capability.cpp_detection is None:
        return None
    renderer = _CPP_DETECTION_RENDERERS.get(capability.cpp_detection)
    if renderer is None:
        return None
    guards = resolve_cpp_compile_guards(
        used_extensions(emitted_profile.specializations("cpp")),
        emitted_profile.extensions,
    ).guards
    return renderer(profile, guards)


def _x86_profile_detection_source(
    profile: MachineProfile,
    guards: Sequence[BackendCompileGuard] = (),
) -> str:
    checks = [
        f'__builtin_cpu_supports("{feature_spelling(feature, profile.alternatives)}")'
        for feature in sorted(profile.features)
    ]
    if guards:
        checks.append(_cpp_compile_guard_condition(guards))
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


def _aarch64_profile_detection_source(
    profile: MachineProfile,
    guards: Sequence[BackendCompileGuard] = (),
) -> str | None:
    if "sve" in profile.features:
        guard_condition = (
            f" && {_cpp_compile_guard_condition(guards)}" if guards else ""
        )
        return "\n".join(
            (
                "#if defined(__linux__) && defined(__aarch64__)",
                "#  include <sys/auxv.h>",
                "#  include <asm/hwcap.h>",
                "#endif",
                "int main() {",
                (
                    "#if defined(__linux__) && defined(__aarch64__) "
                    f"&& defined(HWCAP_SVE){guard_condition}"
                ),
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
    return f"$<$<CXX_COMPILER_ID:{_CMAKE_CXX_FEATURE_FLAG_COMPILERS}>:{flag}>"
