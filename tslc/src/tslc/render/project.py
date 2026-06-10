"""Assemble the generated C++ and Rust project tree.

A profile is a machine feature-set. Each profile gets its own header/module
holding the specializations for every extension reachable in it; a top-level
`tsl.hpp` / `lib.rs` includes the active profile. The `simd<>` substrate is a
static hand-written core, copied in verbatim. Build flags are derived from the
profile's feature set (the one place that maps features to compiler options).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from importlib import resources

from tslc.backend.cpp import CppBackend
from tslc.backend.rust import RustBackend
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import Extension
from tslc.lower.lowerer import LoweredSpecialization
from tslc.output.artifacts import Artifact, ArtifactSet
from tslc.output.verify import VerifyBackend, VerifyProfile, VerifyProject

_ASSETS = "tslc.backend.assets"
# x86 ISA extension -> register width and per-backend register-type wiring.
_X86_WIDTH = {"sse": 128, "avx2": 256, "avx512": 512}
_CPP_REG_HELPER = {128: "reg128", 256: "reg256", 512: "reg512"}
_RUST_TAG = {"scalar": "Scalar", "sse": "Sse", "avx2": "Avx2", "avx512": "Avx512"}


def _slug(profile_name: str) -> str:
    """A safe C++/Rust/CMake identifier for a profile (e.g. icelake-rockerlake)."""

    return re.sub(r"[^0-9A-Za-z_]", "_", profile_name)


def _feature_spelling(feature: str, alternatives: dict[str, str]) -> str:
    """A feature's compiler/target-feature spelling (gcc `-m` / rust `target-feature`).

    Most x86 features spell as the bare token; the exceptions are: `sse4_1`/`sse4_2`
    use a dot; `avx512_*` drop the underscore (`avx512_vnni` -> `avx512vnni`); and
    `alternatives` from the profile data override entirely (`avx512_gfni` -> `gfni`).
    """

    if feature in alternatives:
        return alternatives[feature]
    if feature.startswith("sse4_"):
        return "sse4." + feature[len("sse4_") :]
    if feature.startswith("avx512_"):
        return "avx512" + feature[len("avx512_") :]
    return feature


@dataclass(frozen=True, slots=True)
class ProfileRender:
    profile: MachineProfile
    # primitive name -> its specializations (one backend each)
    cpp: dict[str, tuple[LoweredSpecialization, ...]]
    rust: dict[str, tuple[LoweredSpecialization, ...]]
    # isa_name -> the extension block this profile actually selected for that ISA tag
    # (so registrations know whether `avx2` here is lane-bitmask `avx2` or native
    # `avx2_vl`). Per (profile, isa) exactly one block is selected, so this is 1:1.
    extensions: dict[str, Extension] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RenderedProject:
    artifacts: ArtifactSet
    verify: VerifyProject


def render_project(
    profiles: tuple[ProfileRender, ...], backends: tuple[str, ...] = ("cpp", "rust")
) -> RenderedProject:
    ordered = tuple(sorted(profiles, key=lambda p: p.profile.name))
    artifacts: list[Artifact] = []
    verify_backends: list[VerifyBackend] = []

    if "cpp" in backends:
        artifacts.extend(_cpp_artifacts(ordered))
        verify_backends.append(
            VerifyBackend(
                backend_id="cpp",
                root_path="cpp",
                profiles=tuple(
                    VerifyProfile(
                        profile_name=_slug(p.profile.name),
                        file_stem=_slug(p.profile.name),
                        cpp_flags=_cpp_flags(p.profile),
                    )
                    for p in ordered
                ),
            )
        )
    if "rust" in backends:
        artifacts.extend(_rust_artifacts(ordered))
        verify_backends.append(
            VerifyBackend(
                backend_id="rust",
                root_path="rust",
                profiles=tuple(
                    VerifyProfile(
                        profile_name=_slug(p.profile.name),
                        file_stem=_slug(p.profile.name),
                        rust_target_features=_rust_features(p.profile),
                    )
                    for p in ordered
                ),
            )
        )
    return RenderedProject(
        artifacts=ArtifactSet.create(tuple(artifacts)),
        verify=VerifyProject(backends=tuple(verify_backends)),
    )


# --- build facts (the only place that maps features to compiler options) -----


def _used_exts(by_primitive: dict[str, tuple[LoweredSpecialization, ...]]) -> list[str]:
    exts: set[str] = set()
    for specs in by_primitive.values():
        exts.update(spec.extension_name for spec in specs)
    return sorted(exts)


def _used_pairs(
    by_primitive: dict[str, tuple[LoweredSpecialization, ...]],
) -> list[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for specs in by_primitive.values():
        pairs.update((spec.extension_name, spec.base_type_spelling) for spec in specs)
    return sorted(pairs)


def _cpp_registration(ext: str, extension: Extension | None) -> str:
    """A C++ extension tag + `simd<T, ext>` register/mask-type wiring for one ISA ext.

    Lane-bitmask extensions alias the mask to the register; native-predicate ones
    (avx512 / the `_vl` variants selected on this profile) compute a `__mmaskN` from
    the lane count via the `native_mask<bits, T>` substrate trait."""

    helper = _CPP_REG_HELPER[_X86_WIDTH[ext]]
    if extension is not None and extension.mask_policy.kind == "native_predicate_by_lanes":
        mask = f"typename detail::native_mask<{extension.vector_bits}, T>::type"
    else:
        mask = "register_type"
    return (
        f"struct {ext} {{}};\n"
        f"template <class T>\n"
        f"struct simd<T, {ext}> {{\n"
        f"    using base_type = T;\n"
        f"    using register_type = typename detail::{helper}<T>::type;\n"
        f"    using mask_type = {mask};\n"
        f"}};\n\n"
    )


def _rust_registrations(
    by_primitive: dict[str, tuple[LoweredSpecialization, ...]],
    extensions: dict[str, Extension],
) -> str:
    """Rust extension tag structs + SimdVector impls for the used (ext, type) pairs."""

    lines: list[str] = []
    for ext in _used_exts(by_primitive):
        if ext in _X86_WIDTH:
            lines.append(f"pub struct {_RUST_TAG[ext]};")
    for ext, base in _used_pairs(by_primitive):
        if ext not in _X86_WIDTH:
            continue
        register = _rust_register(ext, base)
        mask = _rust_mask_type(extensions.get(ext), base, register)
        lines.append(
            f"impl SimdVector for Simd<{base}, {_RUST_TAG[ext]}> {{ "
            f"type BaseType = {base}; type RegisterType = {register}; "
            f"type MaskType = {mask}; }}"
        )
    return ("\n".join(lines) + "\n\n") if lines else ""


def _rust_register(ext: str, base_spelling: str) -> str:
    width = _X86_WIDTH[ext]
    if base_spelling == "f32":
        return f"core::arch::x86_64::__m{width}"
    if base_spelling == "f64":
        return f"core::arch::x86_64::__m{width}d"
    return f"core::arch::x86_64::__m{width}i"


def _rust_mask_type(extension: Extension | None, base_spelling: str, register: str) -> str:
    """The Rust mask type for one (ext, base) pair: the register for lane-bitmask, or
    the native ``__mmaskN`` (looked up by lane count) for native-predicate extensions."""

    if extension is None or extension.mask_policy.kind != "native_predicate_by_lanes":
        return register
    lanes = extension.vector_bits // _type_bits(base_spelling)
    return extension.mask_policy.rust_by_lanes.get(max(8, lanes), register)


def _type_bits(base_spelling: str) -> int:
    """Bit width from a base-type spelling: ``i8``/``u32``/``f64`` -> 8/32/64."""

    digits = "".join(c for c in base_spelling if c.isdigit())
    return int(digits) if digits else 8


def _cpp_flags(profile: MachineProfile) -> tuple[str, ...]:
    return tuple(
        f"-m{_feature_spelling(f, profile.alternatives)}" for f in sorted(profile.features)
    )


def _rust_features(profile: MachineProfile) -> tuple[str, ...]:
    return tuple(
        f"+{_feature_spelling(f, profile.alternatives)}" for f in sorted(profile.features)
    )


def _asset(name: str) -> str:
    return resources.files(_ASSETS).joinpath(name).read_text(encoding="utf-8")


# --- C++ ---------------------------------------------------------------------


def _cpp_artifacts(profiles: tuple[ProfileRender, ...]) -> list[Artifact]:
    backend = CppBackend()
    artifacts = [
        _text("cpp/include/tsl_core.hpp", _asset("tsl_core.hpp")),
        _text("cpp/include/tsl_x86_traits.hpp", _asset("tsl_x86_traits.hpp")),
    ]
    for p in profiles:
        x86_exts = [e for e in _used_exts(p.cpp) if e in _X86_WIDTH]
        includes = '#include "tsl_core.hpp"\n'
        if x86_exts:
            includes += '#include "tsl_x86_traits.hpp"\n'
        registrations = "".join(
            _cpp_registration(ext, p.extensions.get(ext)) for ext in x86_exts
        )
        # All declarations (impl primary templates + wrappers) precede all
        # specialization bodies, so any body may call any primitive's wrapper.
        declarations = "\n\n".join(
            backend.render_declarations(name, p.cpp[name]) for name in sorted(p.cpp)
        )
        definitions = "\n\n".join(
            backend.render_definitions(name, p.cpp[name]) for name in sorted(p.cpp)
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
        slug = _slug(p.profile.name)
        artifacts.append(_text(f"cpp/include/tsl_{slug}.hpp", content))
        artifacts.append(_text(f"cpp/tests/smoke_{slug}.cpp", _cpp_smoke(p)))

    artifacts.append(_text("cpp/include/tsl.hpp", _cpp_dispatch(profiles)))
    artifacts.append(_text("cpp/CMakeLists.txt", _cpp_cmakelists(profiles)))
    return artifacts


def _cpp_dispatch(profiles: tuple[ProfileRender, ...]) -> str:
    lines = ["#pragma once", ""]
    for index, p in enumerate(profiles):
        slug = _slug(p.profile.name)
        keyword = "#if" if index == 0 else "#elif"
        lines.append(f"{keyword} defined(TSL_PROFILE_{slug.upper()})")
        lines.append(f'#  include "tsl_{slug}.hpp"')
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
        lines.append(f'if(TSL_PROFILE STREQUAL "{_slug(p.profile.name)}")')
        lines.append(f"  target_compile_options(tsl_smoke PRIVATE {' '.join(flags)})")
        lines.append("endif()")
    return "\n".join(lines) + "\n"


# --- Rust --------------------------------------------------------------------


def _rust_artifacts(profiles: tuple[ProfileRender, ...]) -> list[Artifact]:
    backend = RustBackend()
    artifacts = [_text("rust/src/tsl_core.rs", _asset("tsl_core.rs"))]
    for p in profiles:
        registrations = _rust_registrations(p.rust, p.extensions)
        bodies = "\n\n".join(
            backend.render_primitive(name, p.rust[name]) for name in sorted(p.rust)
        )
        # x86 profiles bring the arch module into scope so intrinsic constant
        # arguments left verbatim in bodies (e.g. `_CMP_EQ_OQ`) resolve; intrinsics
        # themselves stay fully qualified, so the glob is only for those constants.
        arch_use = ""
        if any(e in _X86_WIDTH for e in _used_exts(p.rust)):
            arch_use = "#[allow(unused_imports)]\nuse core::arch::x86_64::*;\n"
        content = (
            "#![allow(non_camel_case_types)]\n"
            "#![allow(dead_code)]\n\n"
            "use crate::tsl_core::*;\n"
            f"{arch_use}\n"
            f"{registrations}"
            f"{bodies}\n"
        )
        artifacts.append(_text(f"rust/src/tsl_{_slug(p.profile.name)}.rs", content))

    artifacts.append(_text("rust/src/lib.rs", _rust_lib(profiles)))
    artifacts.append(_text("rust/Cargo.toml", _rust_cargo(profiles)))
    artifacts.append(
        _text("rust/tests/smoke.rs", "#[test]\nfn smoke() {\n    assert!(true);\n}\n")
    )
    return artifacts


def _rust_lib(profiles: tuple[ProfileRender, ...]) -> str:
    lines = ["#![allow(dead_code)]", "", "pub mod tsl_core;", ""]
    for p in profiles:
        slug = _slug(p.profile.name)
        lines.append(f'#[cfg(feature = "{slug}")]')
        lines.append(f"pub mod tsl_{slug};")
        lines.append("")
    return "\n".join(lines)


def _rust_cargo(profiles: tuple[ProfileRender, ...]) -> str:
    default = _slug(profiles[0].profile.name) if profiles else "scalar"
    features = [f'default = ["{default}"]']
    features.extend(f"{_slug(p.profile.name)} = []" for p in profiles)
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
