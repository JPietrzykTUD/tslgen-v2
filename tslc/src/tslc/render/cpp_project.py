"""Render generated C++ project artifacts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tslc.backend.cpp import CppBackend
from tslc.backend.translation import X86_REGISTER_BITS
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import Extension
from tslc.catalog.signatures import is_free_function_signature
from tslc.lower.lowerer import varying_positions
from tslc.output.artifacts import Artifact
from tslc.output.verify import VerifyProfile
from tslc.render._common import asset, feature_spelling, slug, text, used_exts
from tslc.support_policy import DEFAULT_SUPPORT_POLICY

if TYPE_CHECKING:
    from tslc.render.project import ProfileRender

_CPP_REG_HELPER = {128: "reg128", 256: "reg256", 512: "reg512"}


def cpp_artifacts(profiles: tuple[ProfileRender, ...]) -> list[Artifact]:
    backend = CppBackend()
    artifacts = [
        text("cpp/include/tsl_core.hpp", asset("tsl_core.hpp")),
        text("cpp/include/tsl_x86_traits.hpp", asset("tsl_x86_traits.hpp")),
    ]
    for profile_render in profiles:
        x86_exts = [e for e in used_exts(profile_render.cpp) if e in X86_REGISTER_BITS]
        includes = '#include "tsl_core.hpp"\n'
        if x86_exts:
            includes += '#include "tsl_x86_traits.hpp"\n'
        registrations = "".join(
            _cpp_registration(ext, profile_render.extensions.get(ext)) for ext in x86_exts
        )
        # All declarations (impl primary templates + wrappers) precede all
        # specialization bodies, so any body may call any primitive's wrapper.
        declarations = "\n\n".join(
            backend.render_declarations(name, profile_render.cpp[name])
            for name in sorted(profile_render.cpp)
        )
        definitions = "\n\n".join(
            backend.render_definitions(name, profile_render.cpp[name])
            for name in sorted(profile_render.cpp)
        )
        bodies = declarations + "\n\n" + definitions
        content = (
            "#pragma once\n"
            f"{includes}\n"
            "namespace tsl {\n\n"
            f"{registrations}"
            f"{bodies}\n\n"
            "}  // namespace tsl\n"
        )
        profile_slug = slug(profile_render.profile.name)
        artifacts.append(text(f"cpp/include/tsl_{profile_slug}.hpp", content))
        artifacts.append(text(f"cpp/tests/smoke_{profile_slug}.cpp", _cpp_smoke(profile_render)))

    artifacts.append(text("cpp/include/tsl.hpp", _cpp_dispatch(profiles)))
    artifacts.append(text("cpp/CMakeLists.txt", _cpp_cmakelists(profiles)))
    return artifacts


def cpp_verify_profiles(profiles: tuple[ProfileRender, ...]) -> tuple[VerifyProfile, ...]:
    return tuple(
        VerifyProfile(
            profile_name=slug(profile_render.profile.name),
            file_stem=slug(profile_render.profile.name),
            family=profile_render.profile.family,
            cpp_flags=cpp_flags(profile_render.profile),
            sde=profile_render.profile.sde,
        )
        for profile_render in profiles
    )


def cpp_flags(profile: MachineProfile) -> tuple[str, ...]:
    return tuple(
        f"-m{feature_spelling(feature, profile.alternatives)}"
        for feature in sorted(profile.features)
    )


def _cpp_registration(ext: str, extension: Extension | None) -> str:
    """A C++ extension tag + `simd<T, ext>` register/mask-type wiring for one ISA ext."""

    helper = _CPP_REG_HELPER[X86_REGISTER_BITS[ext]]
    bits = X86_REGISTER_BITS[ext]
    if extension is not None and extension.mask_policy.kind == "native_predicate_by_lanes":
        mask = f"typename detail::native_mask<{extension.vector_bits}, T>::type"
    else:
        mask = "register_type"
    imask = _cpp_imask_type(extension, bits, mask)
    return (
        f"struct {ext} {{}};\n"
        f"template <class T>\n"
        f"struct simd<T, {ext}> {{\n"
        f"    using base_type = T;\n"
        f"    using register_type = typename detail::{helper}<T>::type;\n"
        f"    using mask_type = {mask};\n"
        f"    using imask_type = {imask};\n"
        f"}};\n\n"
    )


def _cpp_imask_type(extension: Extension | None, vector_bits: int, mask: str) -> str:
    """The C++ integral-mask type for one x86 `simd<T, ext>` registration."""

    kind = extension.imask_policy.kind if extension is not None else "lane_bitmask"
    if kind == "same_as_mask_type":
        return mask
    return f"typename detail::lane_bitmask_int<{vector_bits}, T>::type"


def _cpp_dispatch(profiles: tuple[ProfileRender, ...]) -> str:
    lines = ["#pragma once", ""]
    for index, profile_render in enumerate(profiles):
        profile_slug = slug(profile_render.profile.name)
        keyword = "#if" if index == 0 else "#elif"
        lines.append(f"{keyword} defined(TSL_PROFILE_{profile_slug.upper()})")
        lines.append(f'#  include "tsl_{profile_slug}.hpp"')
    lines.append("#else")
    lines.append('#  error "No supported TSL profile selected"')
    lines.append("#endif")
    return "\n".join(lines) + "\n"


def _cpp_smoke(profile_render: ProfileRender) -> str:
    # Address-take every emitted wrapper instantiation so the profile's bodies are
    # fully compiled (with the profile's ISA flags), not merely parsed.
    lines = ["#include <tsl.hpp>", "", "namespace {"]
    index = 0
    for name in sorted(profile_render.cpp):
        specs = profile_render.cpp[name]
        first = specs[0]
        if is_free_function_signature(first.result_kind, first.param_kinds):
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


def _cpp_cmakelists(profiles: tuple[ProfileRender, ...]) -> str:
    lines = [
        "cmake_minimum_required(VERSION 3.16)",
        "project(tsl_generated_cpp CXX)",
        "set(CMAKE_CXX_STANDARD 17)",
        "set(CMAKE_CXX_STANDARD_REQUIRED ON)",
        "if(NOT DEFINED TSL_PROFILE)",
        "  set(TSL_PROFILE scalar)",
        "endif()",
        'string(TOUPPER "${TSL_PROFILE}" TSL_PROFILE_UPPER)',
        "enable_testing()",
        # The smoke binary forces every wrapper specialization to compile; the values binary
        # runs the generated value-correctness checks (returns non-zero on a lane mismatch).
        "add_executable(tsl_smoke tests/smoke_${TSL_PROFILE}.cpp)",
        "add_executable(tsl_values tests/values_${TSL_PROFILE}.cpp)",
        "foreach(target tsl_smoke tsl_values)",
        "  target_include_directories(${target} PRIVATE include)",
        "  target_compile_definitions(${target} PRIVATE TSL_PROFILE_${TSL_PROFILE_UPPER})",
        "endforeach()",
        "add_test(NAME values COMMAND tsl_values)",
    ]
    for profile_render in profiles:
        flags = cpp_flags(profile_render.profile)
        if not flags:
            continue
        lines.append(f'if(TSL_PROFILE STREQUAL "{slug(profile_render.profile.name)}")')
        lines.append(
            f"  target_compile_options(tsl_smoke PRIVATE {' '.join(flags)})"
        )
        lines.append(
            f"  target_compile_options(tsl_values PRIVATE {' '.join(flags)})"
        )
        lines.append("endif()")
    return "\n".join(lines) + "\n"
