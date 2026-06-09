"""Assemble the generated C++ and Rust project tree.

A profile is a machine feature-set. Each profile gets its own header/module
holding the specializations for every extension reachable in it; a top-level
`tsl.hpp` / `lib.rs` includes the active profile. The `simd<>` substrate is a
static hand-written core, copied in verbatim. Build flags are derived from the
profile's feature set (the one place that maps features to compiler options).
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources

from tslc.backend.cpp import CppBackend
from tslc.backend.rust import RustBackend
from tslc.catalog.machine_profiles import MachineProfile
from tslc.lower.lowerer import LoweredSpecialization
from tslc.output.artifacts import Artifact, ArtifactSet
from tslc.output.verify import VerifyBackend, VerifyProfile, VerifyProject

_ASSETS = "tslc.backend.assets"
# Feature spellings that differ from the bare token.
_CPP_FLAG = {"sse4_1": "-msse4.1", "sse4_2": "-msse4.2"}
_RUST_FEATURE = {"sse4_1": "sse4.1", "sse4_2": "sse4.2"}


@dataclass(frozen=True, slots=True)
class ProfileRender:
    profile: MachineProfile
    # primitive name -> its specializations (one backend each)
    cpp: dict[str, tuple[LoweredSpecialization, ...]]
    rust: dict[str, tuple[LoweredSpecialization, ...]]


@dataclass(frozen=True, slots=True)
class RenderedProject:
    artifacts: ArtifactSet
    verify: VerifyProject


def render_project(profiles: tuple[ProfileRender, ...]) -> RenderedProject:
    ordered = tuple(sorted(profiles, key=lambda p: p.profile.name))
    artifacts: list[Artifact] = []
    artifacts.extend(_cpp_artifacts(ordered))
    artifacts.extend(_rust_artifacts(ordered))
    verify = VerifyProject(
        backends=(
            VerifyBackend(
                backend_id="cpp",
                root_path="cpp",
                profiles=tuple(
                    VerifyProfile(
                        profile_name=p.profile.name,
                        file_stem=p.profile.name,
                        cpp_flags=_cpp_flags(p.profile),
                    )
                    for p in ordered
                ),
            ),
            VerifyBackend(
                backend_id="rust",
                root_path="rust",
                profiles=tuple(
                    VerifyProfile(
                        profile_name=p.profile.name,
                        file_stem=p.profile.name,
                        rust_target_features=_rust_features(p.profile),
                    )
                    for p in ordered
                ),
            ),
        )
    )
    return RenderedProject(artifacts=ArtifactSet.create(tuple(artifacts)), verify=verify)


# --- build facts (the only place that maps features to compiler options) -----


def _is_x86_simd(profile: MachineProfile) -> bool:
    return profile.family == "x86" and bool(profile.features)


def _cpp_flags(profile: MachineProfile) -> tuple[str, ...]:
    return tuple(_CPP_FLAG.get(f, f"-m{f}") for f in sorted(profile.features))


def _rust_features(profile: MachineProfile) -> tuple[str, ...]:
    return tuple(f"+{_RUST_FEATURE.get(f, f)}" for f in sorted(profile.features))


def _asset(name: str) -> str:
    return resources.files(_ASSETS).joinpath(name).read_text(encoding="utf-8")


# --- C++ ---------------------------------------------------------------------


def _cpp_artifacts(profiles: tuple[ProfileRender, ...]) -> list[Artifact]:
    backend = CppBackend()
    artifacts = [
        _text("cpp/include/tsl_core.hpp", _asset("tsl_core.hpp")),
        _text("cpp/include/tsl_core_x86.hpp", _asset("tsl_core_x86.hpp")),
    ]
    for p in profiles:
        includes = '#include "tsl_core.hpp"\n'
        if _is_x86_simd(p.profile):
            includes += '#include "tsl_core_x86.hpp"\n'
        bodies = "\n\n".join(
            backend.render_primitive(name, p.cpp[name]) for name in sorted(p.cpp)
        )
        content = (
            "#pragma once\n"
            f"{includes}\n"
            "namespace tsl {\n\n"
            f"{bodies}\n\n"
            "}  // namespace tsl\n"
        )
        artifacts.append(_text(f"cpp/include/tsl_{p.profile.name}.hpp", content))
        artifacts.append(_text(f"cpp/tests/smoke_{p.profile.name}.cpp", _cpp_smoke(p)))

    artifacts.append(_text("cpp/include/tsl.hpp", _cpp_dispatch(profiles)))
    artifacts.append(_text("cpp/CMakeLists.txt", _cpp_cmakelists(profiles)))
    return artifacts


def _cpp_dispatch(profiles: tuple[ProfileRender, ...]) -> str:
    lines = ["#pragma once", ""]
    for index, p in enumerate(profiles):
        keyword = "#if" if index == 0 else "#elif"
        lines.append(f"{keyword} defined(TSL_PROFILE_{p.profile.name.upper()})")
        lines.append(f'#  include "tsl_{p.profile.name}.hpp"')
    lines.append("#else")
    lines.append('#  error "No supported TSL profile selected"')
    lines.append("#endif")
    return "\n".join(lines) + "\n"


def _cpp_smoke(p: ProfileRender) -> str:
    # Address-take every emitted wrapper instantiation so the profile's bodies are
    # fully compiled (with the profile's ISA flags), not merely parsed.
    specs = _ordered_specs(p.cpp)
    lines = ["#include <tsl.hpp>", "", "namespace {"]
    for index, spec in enumerate(specs):
        key = f"tsl::simd<{spec.base_type_spelling}, tsl::{spec.extension_name}>"
        lines.append(f"auto* _tsl_use_{index} = &tsl::{spec.primitive_name}<{key}>;")
    lines.append("}  // namespace")
    lines.append("")
    lines.append("int main() {")
    for index in range(len(specs)):
        lines.append(f"  (void)_tsl_use_{index};")
    lines.append("  return 0;")
    lines.append("}")
    return "\n".join(lines) + "\n"


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
        "add_executable(tsl_smoke tests/smoke_${TSL_PROFILE}.cpp)",
        "target_include_directories(tsl_smoke PRIVATE include)",
        "target_compile_definitions(tsl_smoke PRIVATE TSL_PROFILE_${TSL_PROFILE_UPPER})",
    ]
    for p in profiles:
        flags = _cpp_flags(p.profile)
        if not flags:
            continue
        lines.append(f'if(TSL_PROFILE STREQUAL "{p.profile.name}")')
        lines.append(f"  target_compile_options(tsl_smoke PRIVATE {' '.join(flags)})")
        lines.append("endif()")
    return "\n".join(lines) + "\n"


# --- Rust --------------------------------------------------------------------


def _rust_artifacts(profiles: tuple[ProfileRender, ...]) -> list[Artifact]:
    backend = RustBackend()
    artifacts = [_text("rust/src/tsl_core.rs", _asset("tsl_core.rs"))]
    for p in profiles:
        bodies = "\n\n".join(
            backend.render_primitive(name, p.rust[name]) for name in sorted(p.rust)
        )
        content = (
            "#![allow(non_camel_case_types)]\n"
            "#![allow(dead_code)]\n\n"
            "use crate::tsl_core::*;\n\n"
            f"{bodies}\n"
        )
        artifacts.append(_text(f"rust/src/tsl_{p.profile.name}.rs", content))

    artifacts.append(_text("rust/src/lib.rs", _rust_lib(profiles)))
    artifacts.append(_text("rust/Cargo.toml", _rust_cargo(profiles)))
    artifacts.append(
        _text("rust/tests/smoke.rs", "#[test]\nfn smoke() {\n    assert!(true);\n}\n")
    )
    return artifacts


def _rust_lib(profiles: tuple[ProfileRender, ...]) -> str:
    lines = ["#![allow(dead_code)]", "", "pub mod tsl_core;", ""]
    for p in profiles:
        lines.append(f'#[cfg(feature = "{p.profile.name}")]')
        lines.append(f"pub mod tsl_{p.profile.name};")
        lines.append("")
    return "\n".join(lines)


def _rust_cargo(profiles: tuple[ProfileRender, ...]) -> str:
    default = profiles[0].profile.name if profiles else "scalar"
    features = [f'default = ["{default}"]']
    features.extend(f"{p.profile.name} = []" for p in profiles)
    return (
        "[package]\n"
        'name = "tsl_generated"\n'
        'version = "0.1.0"\n'
        'edition = "2021"\n\n'
        "[lib]\n"
        'path = "src/lib.rs"\n\n'
        "[features]\n" + "\n".join(features) + "\n"
    )


# --- helpers -----------------------------------------------------------------


def _ordered_specs(
    by_primitive: dict[str, tuple[LoweredSpecialization, ...]],
) -> list[LoweredSpecialization]:
    specs: list[LoweredSpecialization] = []
    for name in sorted(by_primitive):
        specs.extend(by_primitive[name])
    return specs


def _text(logical_path: str, content: str) -> Artifact:
    media = "text/x-c++" if logical_path.startswith("cpp/") else "text/rust"
    return Artifact(logical_path=logical_path, content=content, media_type=media)
