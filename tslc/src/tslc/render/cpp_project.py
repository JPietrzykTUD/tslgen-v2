"""Render generated C++ project artifacts."""

from __future__ import annotations

from tslc.backend.cpp import CppBackend
from tslc.backend.cpp_profile import (
    _cpp_includes,
    _cpp_inferred_simd_registrations,
    _cpp_native_registration,
    _cpp_primitive_tags,
    _cpp_registration,
    _cpp_sized_registration,
    _guard_cpp_profile,
    cpp_profiles_support_algorithm,
)
from tslc.backend.emitted_profile import EmittedProfile, used_extensions
from tslc.backend.target_capability import is_x86_register_extension
from tslc.compiler_assets import RenderAssets
from tslc.lower.lowerer import (
    LoweredSpecialization,
    LoweredTypeParam,
    varying_positions,
)
from tslc.output.artifacts import Artifact
from tslc.render._common import slug, text
from tslc.render.cpp_build import _cpp_cmakelists
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
                include_algorithm=cpp_profiles_support_algorithm(profiles),
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
    spec: LoweredSpecialization,
    param: LoweredTypeParam,
    smoke_lanes: int,
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
