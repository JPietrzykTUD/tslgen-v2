"""Assemble the generated C++ and Rust project tree.

A profile is a machine feature-set. Each profile gets its own header/module
holding the specializations for every extension reachable in it; a top-level
`tsl.hpp` / `lib.rs` includes the active profile. The `simd<>` substrate is a
static hand-written core, copied in verbatim. Build flags are derived from the
profile's feature set (the one place that maps features to compiler options).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from importlib import resources

from tslc.backend.cpp import CppBackend
from tslc.backend.rust import RustBackend, rust_register_type
from tslc.backend.translation import X86_REGISTER_BITS
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import Extension
from tslc.lower.lowerer import LoweredSpecialization, varying_positions
from tslc.output.artifacts import Artifact, ArtifactSet
from tslc.output.verify import VerifyBackend, VerifyProfile, VerifyProject

_ASSETS = "tslc.backend.assets"
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
    ordered = tuple(
        replace(p, cpp=_split_immediates(p.cpp), rust=_split_immediates(p.rust))
        for p in sorted(profiles, key=lambda p: p.profile.name)
    )
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


def _split_immediates(
    by_name: dict[str, tuple[LoweredSpecialization, ...]],
) -> dict[str, tuple[LoweredSpecialization, ...]]:
    """Split a primitive whose overload set MIXES an `sImm` form with runtime forms into two
    emitted primitives: the runtime forms keep `<name>` (a normal scalar/vector overload),
    the `sImm` form moves to `<name>_imm` (a non-overloaded const-generic wrapper). Rust has
    no fn overloading and neither backend's single-wrapper machinery can carry a position
    that is compile-time in one form and runtime in another, so the immediate form is lifted
    out; `<name>_imm` follows TSL's own `mul_imm`/`mod_imm` convention. Pure-`sImm` primitives
    (`mul_imm`) and immediate-free primitives are unchanged."""

    out: dict[str, tuple[LoweredSpecialization, ...]] = {}
    for name, specs in by_name.items():
        imm = tuple(s for s in specs if "sImm" in s.param_kinds)
        runtime = tuple(s for s in specs if "sImm" not in s.param_kinds)
        if imm and runtime:
            out[name] = runtime
            out[f"{name}_imm"] = tuple(replace(s, primitive_name=f"{name}_imm") for s in imm)
        else:
            out[name] = specs
    return out


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
    """The C++ integral-mask type for an x86 `simd<T, ext>` registration: the native mask
    spelling for `same_as_mask_type` (avx512 / _vl), else a lane-sized unsigned integer
    (the `lane_bitmask` sse / avx2 case). Scalar/generic are not registered here — they
    carry `imask_type` in the static substrate (`tsl_core.hpp`), like their `mask_type`."""

    kind = extension.imask_policy.kind if extension is not None else "lane_bitmask"
    if kind == "same_as_mask_type":
        return mask
    return f"typename detail::lane_bitmask_int<{vector_bits}, T>::type"


def _rust_registrations(
    by_primitive: dict[str, tuple[LoweredSpecialization, ...]],
    extensions: dict[str, Extension],
) -> str:
    """Rust extension tag structs + SimdVector impls for the used (ext, type) pairs."""

    lines: list[str] = []
    for ext in _used_exts(by_primitive):
        if ext in X86_REGISTER_BITS:
            lines.append(f"pub struct {_RUST_TAG[ext]};")
    for ext, base in _used_pairs(by_primitive):
        if ext not in X86_REGISTER_BITS:
            continue
        register = rust_register_type(ext, base)
        mask = _rust_mask_type(extensions.get(ext), base, register)
        bits = X86_REGISTER_BITS[ext]
        imask = _rust_imask_type(extensions.get(ext), base, mask, bits)
        array = f"array_type<{base}, {bits // _type_bits(base)}, {bits // 8}>"
        lines.append(
            f"impl SimdVector for Simd<{base}, {_RUST_TAG[ext]}> {{ "
            f"type BaseType = {base}; type RegisterType = {register}; "
            f"type MaskType = {mask}; type ImaskType = {imask}; type Array = {array}; }}"
        )
    return ("\n".join(lines) + "\n\n") if lines else ""


def _rust_mask_type(extension: Extension | None, base_spelling: str, register: str) -> str:
    """The Rust mask type for one (ext, base) pair: the register for lane-bitmask, or
    the native ``__mmaskN`` (looked up by lane count) for native-predicate extensions."""

    if extension is None or extension.mask_policy.kind != "native_predicate_by_lanes":
        return register
    lanes = extension.vector_bits // _type_bits(base_spelling)
    return extension.mask_policy.rust_by_lanes.get(max(8, lanes), register)


def _rust_imask_type(
    extension: Extension | None, base_spelling: str, mask: str, vector_bits: int
) -> str:
    """The Rust integral-mask type for one (ext, base) pair: the native mask spelling for
    `same_as_mask_type` (avx512 / _vl), else the smallest `u{8,16,32,64}` with one bit per
    lane (the `lane_bitmask` sse / avx2 case). Scalar/generic are not registered here —
    they carry `ImaskType` in the static substrate (`tsl_core.rs`), like their `MaskType`."""

    kind = extension.imask_policy.kind if extension is not None else "lane_bitmask"
    if kind == "same_as_mask_type":
        return mask
    lanes = vector_bits // _type_bits(base_spelling)
    width = 8 if lanes <= 8 else 16 if lanes <= 16 else 32 if lanes <= 32 else 64
    return f"u{width}"


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
        x86_exts = [e for e in _used_exts(p.cpp) if e in X86_REGISTER_BITS]
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
    # fully compiled (with the profile's ISA flags), not merely parsed. All template
    # args are spelled explicitly (Vec, axis bool values, and the dispatch-arg type for
    # each overloaded position) so address-of resolves without deduction.
    lines = ["#include <tsl.hpp>", "", "namespace {"]
    index = 0
    for name in sorted(p.cpp):
        specs = p.cpp[name]
        varying = varying_positions(specs)
        for spec in specs:
            # The `generic` vector is a LANES template; instantiate it at a representative
            # width so address-of forces the body to compile.
            if spec.extension_name == "generic":
                vec = f"tsl::simd<{spec.base_type_spelling}, tsl::generic<8>>"
            else:
                vec = f"tsl::simd<{spec.base_type_spelling}, tsl::{spec.extension_name}>"
            targs = (
                [vec]
                + [value for _, value in spec.axis]
                # An `sImm` immediate is a non-type template param: pick a representative
                # positive literal so address-of forces the body to compile.
                + (["3"] if spec.immediate is not None else [])
                # `generic_params` (e.g. `PreserveSign`) precede the deduced `Arg` params in
                # the wrapper's template list, so they must be spelled (at their default) to
                # keep the explicit args aligned with the varying-arg positions.
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
    if kind == "ptr":
        return f"{vec}::base_type *"
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
        if any(e in X86_REGISTER_BITS for e in _used_exts(p.rust)):
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
    # `non_upper_case_globals` is allowed so an `sImm` immediate can keep its corpus name
    # (e.g. `factor`) as a lowercase const-generic, matching the body that uses it.
    lines = [
        "#![allow(dead_code)]",
        "#![allow(non_upper_case_globals)]",
        "",
        "pub mod tsl_core;",
        "",
    ]
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


def _text(logical_path: str, content: str) -> Artifact:
    media = "text/x-c++" if logical_path.startswith("cpp/") else "text/rust"
    return Artifact(logical_path=logical_path, content=content, media_type=media)
