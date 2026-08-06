"""Render C++ build metadata and profile detection."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from tslc.backend.cpp_detection import CPP_PROFILE_DETECTION_KINDS
from tslc.backend.cpp_compiler_capabilities import (
    cpp_compiler_capability_cmake_probes,
    cpp_compiler_capability_compile_definitions,
    used_cpp_compiler_capability_ids,
)
from tslc.backend.cpp_profile import (
    cpp_compile_guard_condition,
    cpp_header_group,
)
from tslc.backend.cpp_validation import resolve_cpp_compile_guards
from tslc.backend.emitted_profile import EmittedProfile, used_extensions
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import BackendCompileGuard
from tslc.catalog.target_families import ProfileFamilyCapability
from tslc.compiler_assets import RenderAssets
from tslc.output.verify_model import VerifyProfile, VerifyRunner
from tslc.render._common import slug
from tslc.value_tests.compile_failure import compile_failure_target_name
from tslc.value_tests.model import ValueTestProjectPlan

_CMAKE_CXX_FEATURE_FLAG_COMPILERS = "GNU,Clang,AppleClang,IntelLLVM"


@dataclass(frozen=True, slots=True)
class _X86CpuidProbe:
    leaf: int
    subleaf: int | None
    register: str
    bit: int


# Clang 17 accepts these compiler target features but rejects their spellings in
# __builtin_cpu_supports. Profiles still check their other AVX/AVX-512 features
# through the builtin, preserving its operating-system vector-state checks.
_X86_CPUID_PROBES = {
    "rdrand": _X86CpuidProbe(leaf=1, subleaf=None, register="ecx", bit=30),
    "avx512_vaes": _X86CpuidProbe(leaf=7, subleaf=0, register="ecx", bit=9),
    "avx512_fp16": _X86CpuidProbe(leaf=7, subleaf=0, register="edx", bit=23),
}


def _cpp_preflight_headers(profile: EmittedProfile) -> tuple[str, ...]:
    used = used_extensions(profile.specializations("cpp"))
    return tuple(
        sorted(
            {
                header
                for extension_name in used
                if (extension := profile.extensions.get(extension_name)) is not None
                for header in extension.headers_for_backend("cpp")
            }
        )
    )


def cpp_verify_profiles(profiles: tuple[EmittedProfile, ...]) -> tuple[VerifyProfile, ...]:
    return tuple(
        cpp_verify_profile(
            emitted_profile.profile,
            emitted_profile.profile_family,
            preflight_headers=_cpp_preflight_headers(emitted_profile),
        )
        for emitted_profile in profiles
    )


def cpp_verify_profile(
    profile: MachineProfile,
    capability: ProfileFamilyCapability | None = None,
    *,
    preflight_headers: tuple[str, ...] = (),
) -> VerifyProfile:
    """Project a source machine profile into verifier-owned C++ facts."""

    capability = capability or ProfileFamilyCapability(profile.family)
    backend = capability.backend("cpp")

    return VerifyProfile(
        profile_name=slug(profile.name),
        file_stem=slug(profile.name),
        family=profile.family,
        native_without_runner=(
            capability.native_without_runner if capability is not None else False
        ),
        compile_modes=profile.compile_modes,
        flags=cpp_flags(profile, capability),
        target=cpp_target(profile, capability),
        compiler_role=backend.compiler_role,
        cmake_system_name=backend.cmake_system_name,
        cmake_system_processor=backend.cmake_system_processor,
        pass_target_to_compiler=backend.pass_target_to_compiler,
        preflight_headers=preflight_headers,
        runner=_verify_runner(profile),
    )


def cpp_flags(
    profile: MachineProfile,
    capability: ProfileFamilyCapability | None = None,
) -> tuple[str, ...]:
    capability = capability or ProfileFamilyCapability(profile.family)
    backend = capability.backend("cpp")
    if not backend.feature_flags:
        return profile.flags_for_backend("cpp")
    return (
        *(
            f"-m{profile.feature_spelling(feature, 'cpp')}"
            for feature in sorted(profile.features)
        ),
        *profile.flags_for_backend("cpp"),
    )


def cpp_target(
    profile: MachineProfile,
    capability: ProfileFamilyCapability | None = None,
) -> str | None:
    capability = capability or ProfileFamilyCapability(profile.family)
    return capability.backend("cpp").target


def _verify_runner(profile: MachineProfile) -> VerifyRunner | None:
    if profile.runner is None:
        return None
    return VerifyRunner(
        kind=profile.runner.kind,
        profile=profile.runner.profile,
        args=profile.runner.args,
    )


def _cpp_cmakelists(
    profiles: tuple[EmittedProfile, ...],
    assets: RenderAssets,
    *,
    value_tests: ValueTestProjectPlan | None = None,
) -> str:
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
    capability_ids = used_cpp_compiler_capability_ids(profiles)
    capability_definitions = (
        cpp_compiler_capability_compile_definitions(capability_ids)
    )
    rendered = assets.fill(
        "cpp_cmakelists.txt.tmpl",
        available_profiles=_cmake_list(slugs),
        compiler_capability_probes=cpp_compiler_capability_cmake_probes(
            capability_ids
        ),
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
        profile_targets=_cpp_profile_targets(profiles, capability_definitions),
        overlay_test_targets=_cpp_overlay_test_targets(profiles),
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


def _cpp_profile_targets(
    profiles: tuple[EmittedProfile, ...],
    compiler_capability_definitions: tuple[str, ...] = (),
) -> str:
    blocks: list[str] = []
    for emitted_profile in profiles:
        profile_slug = slug(emitted_profile.profile.name)
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
        flags = cpp_flags(emitted_profile.profile, emitted_profile.profile_family)
        if flags:
            lines.append(
                f"target_compile_options({target} INTERFACE "
                + " ".join(_cmake_cxx_flag(flag) for flag in flags)
                + ")"
            )
        blocks.append("\n".join(lines))
        for header_group in _cpp_profile_header_groups(emitted_profile):
            overlay_target = f"{target}_{header_group}"
            macro = f"TSL_ENABLE_{header_group.upper()}"
            compiler_ids = _cpp_header_group_compiler_ids(
                emitted_profile,
                header_group,
            )
            compiler_pattern = "|".join(compiler_ids)
            blocks.append(
                "\n".join(
                    (
                        f'if(CMAKE_CXX_COMPILER_ID MATCHES "^({compiler_pattern})$")',
                        f"  add_library({overlay_target} INTERFACE)",
                        f"  add_library(tsl::{profile_slug}_{header_group} ALIAS {overlay_target})",
                        f"  target_link_libraries({overlay_target} INTERFACE {target})",
                        f"  target_compile_definitions({overlay_target} INTERFACE {macro})",
                        "endif()",
                    )
                )
            )
    return "\n\n".join(blocks)


def _cpp_profile_header_groups(profile: EmittedProfile) -> tuple[str, ...]:
    used = set(used_extensions(profile.specializations("cpp")))
    return tuple(
        sorted(
            {
                group
                for name, extension in profile.extensions.items()
                if name in used and (group := cpp_header_group(extension)) is not None
            }
        )
    )


def _cpp_header_group_compiler_ids(
    profile: EmittedProfile,
    header_group: str,
) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                compiler_id
                for extension in profile.extensions.values()
                if cpp_header_group(extension) == header_group
                for compiler_id in extension.metadata.backend["cpp"].compiler_ids
            }
        )
    )


def _cpp_overlay_test_targets(profiles: tuple[EmittedProfile, ...]) -> str:
    groups = tuple(
        sorted(
            {
                group
                for profile in profiles
                for group in _cpp_profile_header_groups(profile)
            }
        )
    )
    blocks: list[str] = []
    for group in groups:
        blocks.append(
            "\n".join(
                (
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
                    (
                        f"  target_compile_options(tsl_values_{group} PRIVATE "
                        "$<$<CXX_COMPILER_ID:GNU,Clang,AppleClang>:-fwrapv>)"
                    ),
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
        )
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
    detection = capability.backend("cpp").detection
    if detection is None:
        return None
    renderer = _CPP_DETECTION_RENDERERS.get(detection)
    if renderer is None:
        return None
    guards = resolve_cpp_compile_guards(
        tuple(
            extension_name
            for extension_name in used_extensions(
                emitted_profile.specializations("cpp")
            )
            if cpp_header_group(
                emitted_profile.extensions.get(extension_name)
            ) is None
        ),
        emitted_profile.extensions,
    ).guards
    return renderer(profile, guards)


def _x86_profile_detection_source(
    profile: MachineProfile,
    guards: Sequence[BackendCompileGuard] = (),
) -> str:
    cpuid_probes = {
        feature: _X86_CPUID_PROBES[feature]
        for feature in sorted(profile.features)
        if feature in _X86_CPUID_PROBES
    }
    checks = []
    for feature in sorted(profile.features):
        if feature in cpuid_probes:
            checks.append(f"tsl_cpu_has_{feature}")
        else:
            checks.append(
                f'__builtin_cpu_supports("{profile.feature_spelling(feature, "cpp")}")'
            )
    if guards:
        checks.append(cpp_compile_guard_condition(guards))
    condition = " && ".join(checks) if checks else "1"
    target_condition = (
        "(defined(__x86_64__) || defined(__i386__)) "
        "&& (defined(__GNUC__) || defined(__clang__))"
    )
    lines: list[str] = []
    if cpuid_probes:
        lines.extend((f"#if {target_condition}", "#include <cpuid.h>", "#endif"))
    lines.extend(("int main() {", f"#if {target_condition}", "  __builtin_cpu_init();"))
    cpuid_queries = sorted(
        {(probe.leaf, probe.subleaf) for probe in cpuid_probes.values()},
        key=lambda query: (query[0], -1 if query[1] is None else query[1]),
    )
    for leaf, subleaf in cpuid_queries:
        query_name = f"tsl_cpuid_{leaf}"
        if subleaf is not None:
            query_name += f"_{subleaf}"
        registers = tuple(
            f"{query_name}_{register}"
            for register in ("eax", "ebx", "ecx", "edx")
        )
        call = "__get_cpuid" if subleaf is None else "__get_cpuid_count"
        arguments = [str(leaf)]
        if subleaf is not None:
            arguments.append(str(subleaf))
        arguments.extend(f"&{register}" for register in registers)
        lines.extend(
            (
                f"  unsigned int {', '.join(f'{register} = 0' for register in registers)};",
                f"  const bool {query_name}_available =",
                f"      {call}({', '.join(arguments)}) != 0;",
            )
        )
    for feature, probe in cpuid_probes.items():
        query_name = f"tsl_cpuid_{probe.leaf}"
        if probe.subleaf is not None:
            query_name += f"_{probe.subleaf}"
        lines.extend(
            (
                f"  const bool tsl_cpu_has_{feature} =",
                f"      {query_name}_available &&",
                f"      ({query_name}_{probe.register} & (1u << {probe.bit})) != 0;",
            )
        )
    lines.extend(
        (
            f"  return ({condition}) ? 0 : 1;",
            "#else",
            "  return 1;",
            "#endif",
            "}",
        )
    )
    return "\n".join(lines)


def _aarch64_profile_detection_source(
    profile: MachineProfile,
    guards: Sequence[BackendCompileGuard] = (),
) -> str | None:
    if "sve" in profile.features:
        guard_condition = (
            f" && {cpp_compile_guard_condition(guards)}" if guards else ""
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

assert frozenset(_CPP_DETECTION_RENDERERS) == CPP_PROFILE_DETECTION_KINDS


def _cmake_list(values: Sequence[str]) -> str:
    return " ".join(_cmake_quote(value) for value in values)


def _cmake_quote(value: str) -> str:
    translations: dict[int, str | int | None] = {
        ord('"'): r"\"",
        ord("\\"): r"\\",
    }
    escaped = value.translate(str.maketrans(translations))
    return '"' + escaped + '"'


def _cmake_cxx_flag(flag: str) -> str:
    return f"$<$<CXX_COMPILER_ID:{_CMAKE_CXX_FEATURE_FLAG_COMPILERS}>:{flag}>"
