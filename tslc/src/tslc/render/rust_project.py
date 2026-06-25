"""Render generated Rust project artifacts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tslc.backend.rust import RustBackend, rust_register_type
from tslc.backend.translation import X86_REGISTER_BITS
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import Extension
from tslc.lower.lowerer import LoweredSpecialization
from tslc.output.artifacts import Artifact
from tslc.output.verify import VerifyProfile
from tslc.render._common import (
    asset,
    feature_spelling,
    slug,
    text,
    type_bits,
    used_exts,
    used_pairs,
)

if TYPE_CHECKING:
    from tslc.render.project import ProfileRender

_RUST_TAG = {"scalar": "Scalar", "sse": "Sse", "avx2": "Avx2", "avx512": "Avx512"}


def rust_artifacts(profiles: tuple[ProfileRender, ...]) -> list[Artifact]:
    backend = RustBackend()
    artifacts = [text("rust/src/tsl_core.rs", asset("tsl_core.rs"))]
    for profile_render in profiles:
        registrations = _rust_registrations(profile_render.rust, profile_render.extensions)
        bodies = "\n\n".join(
            backend.render_primitive(name, profile_render.rust[name])
            for name in sorted(profile_render.rust)
        )
        # x86 profiles bring the arch module into scope so intrinsic constant
        # arguments left verbatim in bodies resolve; intrinsics themselves stay fully
        # qualified, so the glob is only for those constants.
        arch_use = ""
        if any(e in X86_REGISTER_BITS for e in used_exts(profile_render.rust)):
            arch_use = "#[allow(unused_imports)]\nuse core::arch::x86_64::*;\n"
        content = (
            "#![allow(non_camel_case_types)]\n"
            "#![allow(dead_code)]\n\n"
            "use crate::tsl_core::*;\n"
            f"{arch_use}\n"
            f"{registrations}"
            f"{bodies}\n"
        )
        artifacts.append(text(f"rust/src/tsl_{slug(profile_render.profile.name)}.rs", content))

    artifacts.append(text("rust/src/lib.rs", _rust_lib(profiles)))
    artifacts.append(text("rust/Cargo.toml", _rust_cargo(profiles)))
    artifacts.append(
        text("rust/tests/smoke.rs", "#[test]\nfn smoke() {\n    assert!(true);\n}\n")
    )
    return artifacts


def rust_verify_profiles(profiles: tuple[ProfileRender, ...]) -> tuple[VerifyProfile, ...]:
    return tuple(
        VerifyProfile(
            profile_name=slug(profile_render.profile.name),
            file_stem=slug(profile_render.profile.name),
            rust_target_features=rust_target_features(profile_render.profile),
            sde=profile_render.profile.sde,
        )
        for profile_render in profiles
    )


def rust_target_features(profile: MachineProfile) -> tuple[str, ...]:
    return tuple(
        f"+{feature_spelling(feature, profile.alternatives)}"
        for feature in sorted(profile.features)
    )


def _rust_registrations(
    by_primitive: dict[str, tuple[LoweredSpecialization, ...]],
    extensions: dict[str, Extension],
) -> str:
    """Rust extension tag structs + SimdVector impls for the used (ext, type) pairs."""

    lines: list[str] = []
    for ext in used_exts(by_primitive):
        if ext in X86_REGISTER_BITS:
            lines.append(f"pub struct {_RUST_TAG[ext]};")
    for ext, base in used_pairs(by_primitive):
        if ext not in X86_REGISTER_BITS:
            continue
        register = rust_register_type(ext, base)
        mask = _rust_mask_type(extensions.get(ext), base, register)
        bits = X86_REGISTER_BITS[ext]
        imask = _rust_imask_type(extensions.get(ext), base, mask, bits)
        array = f"array_type<{base}, {bits // type_bits(base)}, {bits // 8}>"
        lines.append(
            f"impl SimdVector for Simd<{base}, {_RUST_TAG[ext]}> {{ "
            f"type BaseType = {base}; type RegisterType = {register}; "
            f"type MaskType = {mask}; type ImaskType = {imask}; type Array = {array}; }}"
        )
    return ("\n".join(lines) + "\n\n") if lines else ""


def _rust_mask_type(extension: Extension | None, base_spelling: str, register: str) -> str:
    """The Rust mask type for one (ext, base) pair."""

    if extension is None or extension.mask_policy.kind != "native_predicate_by_lanes":
        return register
    lanes = extension.vector_bits // type_bits(base_spelling)
    return extension.mask_policy.rust_by_lanes.get(max(8, lanes), register)


def _rust_imask_type(
    extension: Extension | None, base_spelling: str, mask: str, vector_bits: int
) -> str:
    """The Rust integral-mask type for one x86 `Simd<Base, Ext>` registration."""

    kind = extension.imask_policy.kind if extension is not None else "lane_bitmask"
    if kind == "same_as_mask_type":
        return mask
    lanes = vector_bits // type_bits(base_spelling)
    width = 8 if lanes <= 8 else 16 if lanes <= 16 else 32 if lanes <= 32 else 64
    return f"u{width}"


def _rust_lib(profiles: tuple[ProfileRender, ...]) -> str:
    # `non_upper_case_globals` is allowed so an `sImm` immediate can keep its corpus name
    # as a lowercase const-generic, matching the body that uses it.
    lines = [
        "#![allow(dead_code)]",
        "#![allow(non_upper_case_globals)]",
        "",
        "pub mod tsl_core;",
        "pub mod tsl_test_core;",
        "",
    ]
    for profile_render in profiles:
        profile_slug = slug(profile_render.profile.name)
        lines.append(f'#[cfg(feature = "{profile_slug}")]')
        lines.append(f"pub mod tsl_{profile_slug};")
        lines.append("")
    return "\n".join(lines)


def _rust_cargo(profiles: tuple[ProfileRender, ...]) -> str:
    default = slug(profiles[0].profile.name) if profiles else "scalar"
    features = [f'default = ["{default}"]']
    features.extend(f"{slug(profile_render.profile.name)} = []" for profile_render in profiles)
    # Opt-in feature that compiles+runs the generated value tests (parity with the C++ ctest gate).
    features.append("value_tests = []")
    return (
        "[package]\n"
        'name = "tsl_generated"\n'
        'version = "0.1.0"\n'
        'edition = "2021"\n\n'
        "[lib]\n"
        'path = "src/lib.rs"\n\n'
        "[features]\n" + "\n".join(features) + "\n"
    )
