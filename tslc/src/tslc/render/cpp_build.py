"""Render C++ build metadata and profile detection."""

from __future__ import annotations

from collections.abc import Sequence

from tslc.backend.cpp_build_policy import CppCompilerOption
from tslc.backend.cpp_detection import CppProfileDetectionPlan
from tslc.backend.cpp_profile_model import (
    CppProfileRenderModel,
    CppProjectRenderModel,
)
from tslc.compiler_assets import RenderAssets
from tslc.render._common import slug
from tslc.value_tests.compile_failure import compile_failure_target_name
from tslc.value_tests.model import ValueTestProjectPlan


def _cpp_cmakelists(
    model: CppProjectRenderModel,
    assets: RenderAssets,
    *,
    value_tests: ValueTestProjectPlan | None = None,
) -> str:
    slugs = tuple(slug(profile.profile_name) for profile in model.profiles)
    detection_plan = model.profile_detection
    fallback = (
        ""
        if detection_plan.fallback_profile_name is None
        else slug(detection_plan.fallback_profile_name)
    )
    auto_choices = detection_plan.auto_choices
    rendered = assets.fill(
        "cpp_cmakelists.txt.tmpl",
        available_profiles=_cmake_list(slugs),
        compiler_capability_probes=model.compiler_capability_probes,
        profile_choices=" ".join(
            _cmake_quote(value)
            for value in (*slugs, *_profile_alias_choices(model.profiles))
        ),
        profile_auto_choices=" ".join(
            _cmake_quote(value) for value in auto_choices
        ),
        profile_aliases=_cpp_profile_aliases(model.profiles),
        profile_auto_helpers=_cpp_profile_auto_helpers(detection_plan, assets),
        profile_auto_hint=_cpp_profile_auto_hint(auto_choices),
        fallback_profile=fallback,
        profile_detection=_cpp_profile_detection(
            detection_plan,
            fallback,
            auto_gate_id=None,
        ),
        profile_auto_modes=_cpp_profile_auto_modes(detection_plan),
        profile_targets=_cpp_profile_targets(
            model.profiles, model.compiler_capability_definitions
        ),
        overlay_test_targets=_cpp_overlay_test_targets(
            model.profiles, model.value_test_compile_options
        ),
        compile_failure_targets=_cpp_compile_failure_targets(value_tests),
    )
    return rendered.rstrip("\n") + "\n"


def _cpp_compile_failure_targets(
    plan: ValueTestProjectPlan | None,
) -> str:
    if plan is None:
        return ""
    blocks: list[str] = []
    for profile in plan.profiles_for("cpp"):
        for case in profile.compile_failure_cases:
            target = compile_failure_target_name(profile, case)
            blocks.append(
                "\n".join(
                    (
                        f"add_executable({target} EXCLUDE_FROM_ALL tests/{target}.cpp)",
                        f"target_link_libraries({target} PRIVATE "
                        f"tsl_profile_{slug(profile.profile_name)})",
                    )
                )
            )
    return "\n\n".join(blocks)


def _profile_alias_choices(
    profiles: tuple[CppProfileRenderModel, ...],
) -> tuple[str, ...]:
    return tuple(
        profile.profile_name
        for profile in profiles
        if profile.profile_name != slug(profile.profile_name)
    )


def _cpp_profile_auto_hint(auto_choices: tuple[str, ...]) -> str:
    if not auto_choices:
        return ""
    return " or one of: " + ", ".join(auto_choices)


def _cpp_profile_auto_helpers(
    plan: CppProfileDetectionPlan,
    assets: RenderAssets,
) -> str:
    return "\n\n".join(
        assets.text(asset_name).strip()
        for asset_name in plan.helper_assets
    )


def _cpp_profile_aliases(profiles: tuple[CppProfileRenderModel, ...]) -> str:
    lines: list[str] = []
    for profile in profiles:
        profile_name = profile.profile_name
        profile_slug = slug(profile_name)
        if profile_name == profile_slug:
            continue
        lines.append(f'if(_TSL_REQUESTED_PROFILE STREQUAL "{profile_name}")')
        lines.append(f'  set(_TSL_REQUESTED_PROFILE "{profile_slug}")')
        lines.append("endif()")
    return "\n".join(lines)


def _cpp_profile_targets(
    profiles: tuple[CppProfileRenderModel, ...],
    compiler_capability_definitions: tuple[str, ...] = (),
) -> str:
    blocks: list[str] = []
    for profile in profiles:
        profile_slug = slug(profile.profile_name)
        target = f"tsl_profile_{profile_slug}"
        target_definitions = " ".join(
            (
                f"TSL_PROFILE_{profile_slug.upper()}",
                *compiler_capability_definitions,
            )
        )
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
                f"{target_definitions})"
            ),
        ]
        if profile.compile_options:
            lines.append(
                f"target_compile_options({target} INTERFACE "
                + " ".join(
                    _cmake_compiler_option(option)
                    for option in profile.compile_options
                )
                + ")"
            )
        blocks.append("\n".join(lines))
        for header in profile.overlay_headers:
            header_group = header.header_group
            if header_group is None:
                continue
            overlay_target = f"{target}_{header_group}"
            assert header.enable_macro is not None
            compiler_pattern = "|".join(header.compiler_ids)
            blocks.append(
                "\n".join(
                    (
                        f'if(CMAKE_CXX_COMPILER_ID MATCHES "^({compiler_pattern})$")',
                        f"  add_library({overlay_target} INTERFACE)",
                        f"  add_library(tsl::{profile_slug}_{header_group} ALIAS {overlay_target})",
                        f"  target_link_libraries({overlay_target} INTERFACE {target})",
                        "  target_compile_definitions("
                        f"{overlay_target} INTERFACE {header.enable_macro}"
                        ")",
                        "endif()",
                    )
                )
            )
    return "\n\n".join(blocks)


def _cpp_overlay_test_targets(
    profiles: tuple[CppProfileRenderModel, ...],
    compile_options: tuple[CppCompilerOption, ...],
) -> str:
    groups = tuple(
        sorted(
            {
                header.header_group
                for profile in profiles
                for header in profile.overlay_headers
                if header.header_group is not None
            }
        )
    )
    blocks: list[str] = []
    for group in groups:
        lines = [
            f"if(TSL_BUILD_TESTS AND TARGET tsl_profile_${{TSL_SELECTED_PROFILE}}_{group})",
            f"  add_executable(tsl_smoke_{group} tests/smoke_${{TSL_SELECTED_PROFILE}}_{group}.cpp)",
            (
                f"  target_link_libraries(tsl_smoke_{group} PRIVATE "
                f"tsl_profile_${{TSL_SELECTED_PROFILE}}_{group})"
            ),
            f"  add_executable(tsl_values_{group} tests/values_${{TSL_SELECTED_PROFILE}}.cpp)",
            (
                f"  target_link_libraries(tsl_values_{group} PRIVATE "
                f"tsl_profile_${{TSL_SELECTED_PROFILE}}_{group})"
            ),
        ]
        if compile_options:
            lines.append(
                f"  target_compile_options(tsl_values_{group} PRIVATE "
                + " ".join(
                    _cmake_compiler_option(option) for option in compile_options
                )
                + ")"
            )
        lines.extend(
            (
                f"  add_dependencies(tsl_values tsl_values_{group})",
                "  if(TSL_TEST_LAUNCHER)",
                (
                    f"    add_test(NAME values_{group} COMMAND ${{TSL_TEST_LAUNCHER}} "
                    f"$<TARGET_FILE:tsl_values_{group}>)"
                ),
                "  else()",
                f"    add_test(NAME values_{group} COMMAND tsl_values_{group})",
                "  endif()",
                "endif()",
            )
        )
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _cpp_profile_detection(
    plan: CppProfileDetectionPlan,
    fallback_profile: str,
    *,
    auto_gate_id: str | None,
) -> str:
    blocks: list[str] = []
    for candidate in plan.candidates:
        profile_slug = slug(candidate.profile_name)
        if candidate.auto_gate_id != auto_gate_id:
            continue
        if profile_slug == fallback_profile and not candidate.has_features:
            continue
        source = candidate.source
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


def _cpp_profile_auto_modes(
    plan: CppProfileDetectionPlan,
) -> str:
    blocks: list[str] = []
    for gate in plan.auto_gates:
        gated_candidates = tuple(
            candidate
            for candidate in plan.candidates
            if candidate.auto_gate_id == gate.gate_id
        )
        gated_slugs = tuple(
            slug(candidate.profile_name) for candidate in gated_candidates
        )
        if not gated_slugs:
            continue
        mode = gate.mode_name
        detection = _cpp_profile_detection(
            plan,
            "",
            auto_gate_id=gate.gate_id,
        )
        lines = [
            f'elseif(_TSL_REQUESTED_PROFILE STREQUAL "{mode}")',
            '  set(TSL_SELECTED_PROFILE "")',
            f"  {gate.helper_function}(_TSL_GATE_READY _TSL_GATE_REASON)",
            "  if(NOT _TSL_GATE_READY)",
            (
                f'    message(FATAL_ERROR "TSL_PROFILE={mode} requested, but '
                f'{gate.gate_id} auto-detection failed: ${{_TSL_GATE_REASON}}")'
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
                    f'{gate.gate_id}, but no generated gated profile matched this CPU. '
                    f'Available gated profiles: {", ".join(gated_slugs)}")'
                ),
                "    endif()",
                f'    message(STATUS "TSL_PROFILE={mode} selected profile = ${{TSL_SELECTED_PROFILE}}")',
                "  endif()",
            ]
        )
        blocks.append("\n".join(lines))
    return "\n".join(blocks)


def _cmake_list(values: Sequence[str]) -> str:
    return " ".join(_cmake_quote(value) for value in values)


def _cmake_quote(value: str) -> str:
    translations: dict[int, str | int | None] = {
        ord('"'): r"\"",
        ord("\\"): r"\\",
    }
    escaped = value.translate(str.maketrans(translations))
    return '"' + escaped + '"'


def _cmake_compiler_option(option: CppCompilerOption) -> str:
    compiler_ids = ",".join(option.compiler_ids)
    return f"$<$<CXX_COMPILER_ID:{compiler_ids}>:{option.flag}>"
