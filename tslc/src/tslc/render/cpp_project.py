"""Render generated C++ project artifacts from backend-decided profile models."""

from __future__ import annotations

import json

from tslc.backend.cpp import CppBackend
from tslc.backend.cpp_profile_model import (
    CppProfileHeader,
    CppProjectRenderModel,
    CppSmokeInstantiation,
    cpp_project_render_model,
)
from tslc.backend.emitted_profile import EmittedProfile
from tslc.compiler_assets import RenderAssets
from tslc.output.artifacts import Artifact
from tslc.render._common import slug, text
from tslc.render.cpp_build import _cpp_cmakelists
from tslc.value_tests.model import ValueTestProjectPlan

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
    value_tests: ValueTestProjectPlan | None = None,
) -> list[Artifact]:
    backend = CppBackend()
    model = cpp_project_render_model(profiles)
    artifacts = [
        text(f"cpp/include/{header}", assets.text(header), media_type=media_type)
        for header in _CPP_STATIC_HEADERS
    ] + [
        text(
            "cpp/include/tsl_primitives.hpp",
            assets.fill(
                "cpp_primitive_tags.hpp.tmpl",
                declarations=(
                    f"\n{model.primitive_tag_declarations}"
                    if model.primitive_tag_declarations
                    else ""
                ),
            ),
            media_type=media_type,
        ),
        # Ship the formatter config at the C++ project root so `clang-format` (ascending from
        # include/ and tests/) finds it and the generated project is self-contained.
        text("cpp/.clang-format", assets.text(".clang-format"), media_type=media_type),
    ]
    for profile_model in model.profiles:
        base = profile_model.base_header
        profile_slug = slug(profile_model.profile_name)
        profile_metadata = assets.fill(
            "cpp_profile_metadata.hpp.tmpl",
            profile_namespace=profile_slug,
            profile_name=json.dumps(profile_slug),
            profile_family=json.dumps(profile_model.profile_family),
        ).rstrip()
        artifacts.append(
            text(
                f"cpp/include/tsl_{profile_slug}.hpp",
                _cpp_profile_header(
                    backend,
                    base,
                    assets,
                    includes=base.includes or "",
                    profile_metadata=profile_metadata,
                ),
                media_type=media_type,
            )
        )
        for header in profile_model.overlay_headers:
            header_name = f"tsl_{profile_slug}_{header.header_group}.hpp"
            artifacts.append(
                text(
                    f"cpp/include/{header_name}",
                    _cpp_profile_header(
                        backend,
                        header,
                        assets,
                        includes=f'#include "tsl_{profile_slug}.hpp"\n',
                        profile_metadata="",
                    ),
                    media_type=media_type,
                )
            )
            artifacts.append(
                text(
                    f"cpp/tests/smoke_{profile_slug}_{header.header_group}.cpp",
                    _cpp_smoke(header.smoke, assets, include_header=header_name),
                    media_type=media_type,
                )
            )
        artifacts.append(
            text(
                f"cpp/tests/smoke_{profile_slug}.cpp",
                _cpp_smoke(base.smoke, assets, include_header="tsl.hpp"),
                media_type=media_type,
            )
        )

    artifacts.append(
        text(
            "cpp/include/tsl.hpp",
            _cpp_dispatch(model, assets),
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
            _cpp_cmakelists(profiles, assets, value_tests=value_tests),
            media_type=media_type,
        )
    )
    return artifacts


def _cpp_profile_header(
    backend: CppBackend,
    header: CppProfileHeader,
    assets: RenderAssets,
    *,
    includes: str,
    profile_metadata: str,
) -> str:
    selectors = "\n\n".join(
        rendered
        for declared in header.declarations
        if (
            rendered := backend.render_variant_selectors(
                declared.name, declared.specializations
            )
        )
    )
    # All implementation templates precede all wrappers and specialization
    # bodies. Selectors precede the optional build-local policy include.
    implementation_declarations = "\n\n".join(
        backend.render_implementation_declarations(
            declared.name, declared.specializations
        )
        for declared in header.declarations
    )
    wrappers = "\n\n".join(
        rendered
        for declared in header.declarations
        if (
            rendered := backend.render_wrappers(
                declared.name, declared.specializations
            )
        )
    )
    definitions = _cpp_conditioned_definitions(backend, header)
    bodies = "\n\n".join(
        part for part in (implementation_declarations, wrappers, definitions) if part
    )
    content = assets.fill(
        "cpp_profile_header.hpp.tmpl",
        includes=includes,
        profile_metadata=profile_metadata,
        registrations=header.registrations,
        selectors=selectors,
        bodies=bodies,
    )
    if header.guard is not None:
        content = header.guard.guard(content)
    return content


def _cpp_conditioned_definitions(backend: CppBackend, header: CppProfileHeader) -> str:
    rendered: list[str] = []
    for group in header.definition_groups:
        definitions = backend.render_definitions(
            group.primitive,
            group.specializations,
        )
        if group.condition is not None:
            definitions = f"#if {group.condition}\n{definitions}\n#endif"
        rendered.append(definitions)
    return "\n\n".join(rendered)


def _cpp_dispatch(model: CppProjectRenderModel, assets: RenderAssets) -> str:
    profile_cases: list[str] = []
    for index, profile_model in enumerate(model.profiles):
        profile_slug = slug(profile_model.profile_name)
        profile_cases.append(
            assets.fill(
                "cpp_dispatch_case.hpp.tmpl",
                directive="#if" if index == 0 else "#elif",
                profile_macro=profile_slug.upper(),
                header=f"tsl_{profile_slug}.hpp",
            ).rstrip()
        )
    overlay_cases: list[str] = []
    for group in model.dispatch_header_groups:
        group_profile_cases: list[str] = []
        for index, profile_model in enumerate(model.profiles):
            profile_slug = slug(profile_model.profile_name)
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
            if model.supports_algorithm
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


def _cpp_smoke(
    smoke: tuple[CppSmokeInstantiation, ...],
    assets: RenderAssets,
    *,
    include_header: str,
) -> str:
    declarations: list[str] = []
    references: list[str] = []
    for index, instantiation in enumerate(smoke):
        if instantiation.template_arguments:
            arguments = ", ".join(instantiation.template_arguments)
            use_line = f"auto* _tsl_use_{index} = &{instantiation.symbol}<{arguments}>;"
        else:
            use_line = f"auto* _tsl_use_{index} = &{instantiation.symbol};"
        reference = f"  (void)_tsl_use_{index};"
        if instantiation.condition is not None:
            use_line = f"#if {instantiation.condition}\n{use_line}\n#endif"
            reference = f"#if {instantiation.condition}\n{reference}\n#endif"
        declarations.append(use_line)
        references.append(reference)
    rendered_declarations = "\n".join(declarations)
    rendered_references = "\n".join(references)
    return assets.fill(
        "cpp_smoke.cpp.tmpl",
        include_header=include_header,
        declarations=(f"\n{rendered_declarations}" if declarations else ""),
        references=(f"\n{rendered_references}" if references else ""),
    )
