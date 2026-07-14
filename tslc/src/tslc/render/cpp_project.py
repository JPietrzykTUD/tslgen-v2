"""Render generated C++ project artifacts."""

from __future__ import annotations

import json
from collections.abc import Mapping

from tslc.backend.cpp import CppBackend
from tslc.backend.cpp_profile import (
    _cpp_compiler_builtin_fixed_registrations,
    _cpp_includes,
    _cpp_inferred_simd_registrations,
    _cpp_native_registration,
    _cpp_primitive_tags,
    _cpp_registration,
    _cpp_sized_registration,
    _guard_cpp_profile,
    cpp_extension_availability_condition,
    cpp_header_group,
    cpp_profiles_support_algorithm,
)
from tslc.backend.emitted_profile import EmittedProfile, used_extensions
from tslc.backend.target_capability import is_x86_register_extension
from tslc.compiler_assets import RenderAssets
from tslc.catalog.model import Extension
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
            _cpp_primitive_tags(profiles, assets),
            media_type=media_type,
        ),
        # Ship the formatter config at the C++ project root so `clang-format` (ascending from
        # include/ and tests/) finds it and the generated project is self-contained.
        text("cpp/.clang-format", assets.text(".clang-format"), media_type=media_type),
    ]
    for emitted_profile in profiles:
        all_specializations = emitted_profile.specializations("cpp")
        header_groups = tuple(
            sorted(
                {
                    group
                    for extension in emitted_profile.extensions.values()
                    if (group := cpp_header_group(extension)) is not None
                }
            )
        )
        by_primitive = _cpp_specializations_for_group(
            all_specializations,
            emitted_profile.extensions,
            None,
        )
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
        selectors = "\n\n".join(
            rendered
            for name in sorted(by_primitive)
            if (rendered := backend.render_variant_selectors(name, by_primitive[name]))
        )
        # All implementation templates precede all wrappers and specialization
        # bodies. Selectors precede the optional build-local policy include.
        implementation_declarations = "\n\n".join(
            backend.render_implementation_declarations(name, by_primitive[name])
            for name in sorted(by_primitive)
        )
        wrappers = "\n\n".join(
            rendered
            for name in sorted(by_primitive)
            if (rendered := backend.render_wrappers(name, by_primitive[name]))
        )
        definitions = _cpp_conditioned_definitions(
            backend,
            by_primitive,
            emitted_profile.extensions,
        )
        bodies = "\n\n".join(
            part for part in (implementation_declarations, wrappers, definitions) if part
        )
        profile_slug = slug(emitted_profile.profile.name)
        profile_metadata = assets.fill(
            "cpp_profile_metadata.hpp.tmpl",
            profile_namespace=profile_slug,
            profile_name=json.dumps(profile_slug),
            profile_family=json.dumps(emitted_profile.profile.family),
        ).rstrip()
        content = assets.fill(
            "cpp_profile_header.hpp.tmpl",
            includes=includes,
            profile_metadata=profile_metadata,
            registrations=registrations,
            selectors=selectors,
            bodies=bodies,
        )
        content = _guard_cpp_profile(
            content,
            used_extensions(by_primitive),
            emitted_profile.extensions,
        )
        artifacts.append(
            text(
                f"cpp/include/tsl_{profile_slug}.hpp",
                content,
                media_type=media_type,
            )
        )
        for header_group in header_groups:
            grouped = _cpp_specializations_for_group(
                all_specializations,
                emitted_profile.extensions,
                header_group,
            )
            if not grouped:
                continue
            grouped_exts = used_extensions(grouped)
            grouped_includes = f'#include "tsl_{profile_slug}.hpp"\n'
            grouped_registrations = _cpp_native_registration(
                grouped,
                emitted_profile.extensions,
            )
            grouped_registrations += _cpp_compiler_builtin_fixed_registrations(
                grouped,
                emitted_profile.extensions,
                header_group,
            )
            grouped_selectors = "\n\n".join(
                rendered
                for name in sorted(grouped)
                if name not in by_primitive
                if (rendered := backend.render_variant_selectors(name, grouped[name]))
            )
            grouped_implementation_declarations = "\n\n".join(
                backend.render_implementation_declarations(name, grouped[name])
                for name in sorted(grouped)
                if name not in by_primitive
            )
            grouped_wrappers = "\n\n".join(
                rendered
                for name in sorted(grouped)
                if name not in by_primitive
                if (rendered := backend.render_wrappers(name, grouped[name]))
            )
            grouped_definitions = _cpp_conditioned_definitions(
                backend,
                grouped,
                emitted_profile.extensions,
            )
            grouped_bodies = "\n\n".join(
                part
                for part in (
                    grouped_implementation_declarations,
                    grouped_wrappers,
                    grouped_definitions,
                )
                if part
            )
            grouped_content = assets.fill(
                "cpp_profile_header.hpp.tmpl",
                includes=grouped_includes,
                profile_metadata="",
                registrations=grouped_registrations,
                selectors=grouped_selectors,
                bodies=grouped_bodies,
            )
            grouped_content = _guard_cpp_profile(
                grouped_content,
                grouped_exts,
                emitted_profile.extensions,
            )
            artifacts.append(
                text(
                    f"cpp/include/tsl_{profile_slug}_{header_group}.hpp",
                    grouped_content,
                    media_type=media_type,
                )
            )
            artifacts.append(
                text(
                    f"cpp/tests/smoke_{profile_slug}_{header_group}.cpp",
                    _cpp_smoke(
                        emitted_profile,
                        assets,
                        by_primitive=grouped,
                        include_header=f"tsl_{profile_slug}_{header_group}.hpp",
                    ),
                    media_type=media_type,
                )
            )
        artifacts.append(
            text(
                f"cpp/tests/smoke_{profile_slug}.cpp",
                _cpp_smoke(emitted_profile, assets, by_primitive=by_primitive),
                media_type=media_type,
            )
        )

    artifacts.append(
        text(
            "cpp/include/tsl.hpp",
            _cpp_dispatch(
                profiles,
                assets,
                include_algorithm=cpp_profiles_support_algorithm(profiles),
            ),
            media_type=media_type,
        )
    )
    artifacts.append(
        text(
            "cpp/docs/input/tsl_api_docs.hpp",
            _cpp_documentation_facade(profiles, assets),
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
    assets: RenderAssets,
    *,
    include_algorithm: bool = False,
) -> str:
    profile_cases: list[str] = []
    for index, emitted_profile in enumerate(profiles):
        profile_slug = slug(emitted_profile.profile.name)
        profile_cases.append(
            assets.fill(
                "cpp_dispatch_case.hpp.tmpl",
                directive="#if" if index == 0 else "#elif",
                profile_macro=profile_slug.upper(),
                header=f"tsl_{profile_slug}.hpp",
            ).rstrip()
        )
    header_groups = tuple(
        sorted(
            {
                group
                for profile in profiles
                for extension in profile.extensions.values()
                if (group := cpp_header_group(extension)) is not None
            }
        )
    )
    overlay_cases: list[str] = []
    for group in header_groups:
        group_profile_cases: list[str] = []
        for index, emitted_profile in enumerate(profiles):
            profile_slug = slug(emitted_profile.profile.name)
            group_profile_cases.append(
                assets.fill(
                    "cpp_dispatch_case.hpp.tmpl",
                    directive="#if" if index == 0 else "#elif",
                    profile_macro=profile_slug.upper(),
                    header=f"tsl_{profile_slug}_{group}.hpp",
                ).rstrip()
            )
        overlay_cases.append(
            assets.fill(
                "cpp_dispatch_overlay.hpp.tmpl",
                group_macro=group.upper(),
                profile_cases="\n".join(group_profile_cases),
            ).rstrip()
        )
    rendered_overlay_cases = "\n".join(overlay_cases)
    return assets.fill(
        "cpp_dispatch.hpp.tmpl",
        profile_cases="\n".join(profile_cases),
        overlay_cases=(f"\n{rendered_overlay_cases}" if overlay_cases else ""),
        algorithm_include=(
            f'\n{assets.text("cpp_dispatch_algorithm_include.hpp").rstrip()}'
            if include_algorithm
            else ""
        ),
    )


def _cpp_documentation_facade(
    profiles: tuple[EmittedProfile, ...],
    assets: RenderAssets,
) -> str:
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
    declarations = "\n\n".join(api_declarations)
    return assets.fill(
        "cpp_documentation.hpp.tmpl",
        api_declarations=f"\n\n{declarations}" if declarations else "",
    )


def _cpp_conditioned_definitions(
    backend: CppBackend,
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    extensions: Mapping[str, Extension],
) -> str:
    """Render specialization definitions under their compiler capability guard."""

    rendered: list[str] = []
    for name in sorted(by_primitive):
        by_condition: dict[str | None, list[LoweredSpecialization]] = {}
        for specialization in by_primitive[name]:
            condition = _cpp_specialization_availability_condition(
                specialization,
                extensions,
            )
            by_condition.setdefault(condition, []).append(specialization)
        for condition in sorted(by_condition, key=lambda value: value or ""):
            definitions = backend.render_definitions(
                name,
                tuple(by_condition[condition]),
            )
            if condition is not None:
                definitions = f"#if {condition}\n{definitions}\n#endif"
            rendered.append(definitions)
    return "\n\n".join(rendered)


def _cpp_specialization_availability_condition(
    specialization: LoweredSpecialization,
    extensions: Mapping[str, Extension],
) -> str | None:
    names = [specialization.extension_name]
    if specialization.target is not None:
        names.append(specialization.target.extension_isa)
    conditions = sorted(
        {
            condition
            for name in names
            for condition in (
                cpp_extension_availability_condition(extensions.get(name)),
            )
            if condition is not None
        }
    )
    return " && ".join(conditions) if conditions else None


def _cpp_smoke(
    emitted_profile: EmittedProfile,
    assets: RenderAssets,
    *,
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]] | None = None,
    include_header: str = "tsl.hpp",
) -> str:
    # Address-take every emitted wrapper instantiation so the profile's bodies are
    # fully compiled (with the profile's ISA flags), not merely parsed.
    declarations: list[str] = []
    index = 0
    used_conditions: list[str | None] = []
    if by_primitive is None:
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
            declarations.append(f"auto* _tsl_use_{index} = &tsl::{name};")
            used_conditions.append(None)
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
            use_line = f"auto* _tsl_use_{index} = &tsl::{name}<{', '.join(targs)}>;"
            condition = _cpp_specialization_availability_condition(
                spec,
                emitted_profile.extensions,
            )
            if condition is not None:
                use_line = f"#if {condition}\n{use_line}\n#endif"
            declarations.append(use_line)
            used_conditions.append(condition)
            index += 1
    references: list[str] = []
    for used, condition in enumerate(used_conditions):
        use_line = f"  (void)_tsl_use_{used};"
        if condition is not None:
            use_line = f"#if {condition}\n{use_line}\n#endif"
        references.append(use_line)
    rendered_declarations = "\n".join(declarations)
    rendered_references = "\n".join(references)
    return assets.fill(
        "cpp_smoke.cpp.tmpl",
        include_header=include_header,
        declarations=(f"\n{rendered_declarations}" if declarations else ""),
        references=(f"\n{rendered_references}" if references else ""),
    )


def _cpp_specializations_for_group(
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    extensions: Mapping[str, Extension],
    header_group: str | None,
) -> dict[str, tuple[LoweredSpecialization, ...]]:
    grouped: dict[str, tuple[LoweredSpecialization, ...]] = {}
    for primitive, specializations in by_primitive.items():
        selected = tuple(
            specialization
            for specialization in specializations
            if cpp_header_group(extensions.get(specialization.extension_name))
            == header_group
        )
        if selected:
            grouped[primitive] = selected
    return grouped


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
