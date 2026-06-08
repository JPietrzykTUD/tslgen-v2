"""Assemble the generated C++ and Rust project tree from lowered functions.

This is presentation only: it formats already-decided values (function text,
profile names, build flags) into files. It makes no backend semantic decisions.
The one piece of build-system knowledge — which ISA flags a profile needs — is
the explicit ``_PROFILE_BUILD`` table below.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tslc.backend.cpp import CppBackend
from tslc.backend.rust import RustBackend
from tslc.lower.lowerer import LoweredFunction
from tslc.output.artifacts import Artifact, ArtifactSet
from tslc.output.verify import VerifyBackend, VerifyProfile, VerifyProject


@dataclass(frozen=True, slots=True)
class _ProfileBuild:
    cpp_includes: tuple[str, ...]
    cpp_flags: tuple[str, ...]
    rust_target_features: tuple[str, ...]


# Per-extension build facts. The only place in tslc that knows ISA compiler flags.
_PROFILE_BUILD: dict[str, _ProfileBuild] = {
    "scalar": _ProfileBuild(cpp_includes=("<cstdint>",), cpp_flags=(), rust_target_features=()),
    "avx2": _ProfileBuild(
        cpp_includes=("<cstdint>", "<immintrin.h>"),
        cpp_flags=("-mavx2", "-mavx"),
        rust_target_features=("+avx2",),
    ),
}


@dataclass(frozen=True, slots=True)
class ProfileRender:
    """One profile (extension) with its rendered functions for each backend."""

    extension: str
    cpp_functions: tuple[LoweredFunction, ...]
    rust_functions: tuple[LoweredFunction, ...]


@dataclass(frozen=True, slots=True)
class RenderedProject:
    artifacts: ArtifactSet
    verify: VerifyProject


def render_project(profiles: tuple[ProfileRender, ...]) -> RenderedProject:
    ordered = tuple(sorted(profiles, key=lambda profile: profile.extension))
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
                        profile_name=profile.extension,
                        file_stem=profile.extension,
                        cpp_flags=_build(profile.extension).cpp_flags,
                    )
                    for profile in ordered
                ),
            ),
            VerifyBackend(
                backend_id="rust",
                root_path="rust",
                profiles=tuple(
                    VerifyProfile(
                        profile_name=profile.extension,
                        file_stem=profile.extension,
                        rust_target_features=_build(profile.extension).rust_target_features,
                    )
                    for profile in ordered
                ),
            ),
        )
    )
    return RenderedProject(artifacts=ArtifactSet.create(tuple(artifacts)), verify=verify)


def _build(extension: str) -> _ProfileBuild:
    return _PROFILE_BUILD.get(extension, _ProfileBuild((), (), ()))


# --- C++ ---------------------------------------------------------------------


def _cpp_artifacts(profiles: tuple[ProfileRender, ...]) -> list[Artifact]:
    backend = CppBackend()
    artifacts: list[Artifact] = []
    for profile in profiles:
        includes = "\n".join(f"#include {inc}" for inc in _build(profile.extension).cpp_includes)
        defs = "\n\n".join(backend.render_function(fn) for fn in profile.cpp_functions)
        content = (
            "#pragma once\n"
            f"{includes}\n\n"
            f"namespace tsl::profiles::{profile.extension} {{\n\n"
            f"{defs}\n\n"
            f"}}  // namespace tsl::profiles::{profile.extension}\n"
        )
        artifacts.append(_text(f"cpp/include/profiles/{profile.extension}.hpp", content))

    artifacts.append(_text("cpp/include/tsl.hpp", _cpp_public_header(profiles)))
    artifacts.append(_text("cpp/CMakeLists.txt", _cpp_cmakelists(profiles)))
    artifacts.append(
        _text(
            "cpp/tests/smoke.cpp",
            '#include <tsl.hpp>\n\nint main() {\n  return 0;\n}\n',
        )
    )
    return artifacts


def _cpp_public_header(profiles: tuple[ProfileRender, ...]) -> str:
    lines = ["#pragma once", ""]
    for index, profile in enumerate(profiles):
        keyword = "#if" if index == 0 else "#elif"
        macro = f"TSL_PROFILE_{profile.extension.upper()}"
        lines.append(f"{keyword} defined({macro})")
        lines.append(f'#  include "profiles/{profile.extension}.hpp"')
    lines.append("#else")
    lines.append('#  error "No supported TSL profile selected"')
    lines.append("#endif")
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
        "add_executable(tsl_smoke tests/smoke.cpp)",
        "target_include_directories(tsl_smoke PRIVATE include)",
        "target_compile_definitions(tsl_smoke PRIVATE TSL_PROFILE_${TSL_PROFILE_UPPER})",
    ]
    for profile in profiles:
        flags = _build(profile.extension).cpp_flags
        if not flags:
            continue
        lines.append(f'if(TSL_PROFILE STREQUAL "{profile.extension}")')
        lines.append(
            f"  target_compile_options(tsl_smoke PRIVATE {' '.join(flags)})"
        )
        lines.append("endif()")
    return "\n".join(lines) + "\n"


# --- Rust --------------------------------------------------------------------


def _rust_artifacts(profiles: tuple[ProfileRender, ...]) -> list[Artifact]:
    backend = RustBackend()
    artifacts: list[Artifact] = []
    for profile in profiles:
        defs = "\n\n".join(backend.render_function(fn) for fn in profile.rust_functions)
        content = (
            "#![allow(non_camel_case_types)]\n"
            "#![allow(dead_code)]\n\n"
            f"{defs}\n"
        )
        artifacts.append(_text(f"rust/src/profiles/{profile.extension}.rs", content))

    artifacts.append(_text("rust/src/lib.rs", _rust_lib(profiles)))
    artifacts.append(_text("rust/Cargo.toml", _rust_cargo(profiles)))
    artifacts.append(
        _text("rust/tests/smoke.rs", "#[test]\nfn smoke() {\n    assert!(true);\n}\n")
    )
    return artifacts


def _rust_lib(profiles: tuple[ProfileRender, ...]) -> str:
    lines = ["#![allow(dead_code)]", ""]
    for profile in profiles:
        lines.append(f'#[cfg(feature = "{profile.extension}")]')
        lines.append(f'#[path = "profiles/{profile.extension}.rs"]')
        lines.append(f"pub mod {profile.extension};")
        lines.append("")
    return "\n".join(lines)


def _rust_cargo(profiles: tuple[ProfileRender, ...]) -> str:
    default = profiles[0].extension if profiles else "scalar"
    feature_lines = [f'default = ["{default}"]']
    feature_lines.extend(f"{profile.extension} = []" for profile in profiles)
    return (
        "[package]\n"
        'name = "tsl_generated"\n'
        'version = "0.1.0"\n'
        'edition = "2021"\n\n'
        "[lib]\n"
        'path = "src/lib.rs"\n\n'
        "[features]\n" + "\n".join(feature_lines) + "\n"
    )


def _text(logical_path: str, content: str) -> Artifact:
    media = "text/x-c++" if logical_path.startswith("cpp/") else "text/rust"
    return Artifact(logical_path=logical_path, content=content, media_type=media)
