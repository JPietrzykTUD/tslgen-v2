"""Render generated Rust project artifacts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from tslc.backend.rust import RustBackend
from tslc.backend.target_capability import (
    is_x86_register_extension,
    rust_arch_module,
    rust_extension_tag,
    rust_register_type,
    x86_register_bits,
)
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import Extension
from tslc.catalog.target_families import ProfileFamilyCapability
from tslc.lower.lowerer import LoweredSpecialization
from tslc.output.artifacts import Artifact
from tslc.output.verify_model import VerifyEmulator, VerifyProfile
from tslc.render._common import (
    asset,
    feature_spelling,
    fill_asset,
    slug,
    text,
    type_bits,
    used_exts,
    used_pairs,
    used_type_specs,
)

if TYPE_CHECKING:
    from tslc.render.project import ProfileRender


def rust_artifacts(profiles: tuple[ProfileRender, ...]) -> list[Artifact]:
    backend = RustBackend()
    artifacts = [
        text("rust/src/tsl_core.rs", asset("tsl_core.rs")),
        # Ship the formatter config at the crate root so `rustfmt`/`cargo fmt` finds it and the
        # generated crate is self-contained.
        text("rust/rustfmt.toml", asset("rustfmt.toml")),
    ]
    for profile_render in profiles:
        by_primitive = profile_render.specializations("rust")
        registrations = _rust_registrations(by_primitive, profile_render.extensions)
        bodies = "\n\n".join(
            backend.render_primitive(name, by_primitive[name])
            for name in sorted(by_primitive)
        )
        # Arch modules are imported for intrinsic constants left verbatim in bodies.
        # Intrinsics themselves stay fully qualified by lowering.
        arch_use = _rust_arch_use(
            used_exts(by_primitive), profile_render.extensions
        )
        content = fill_asset(
            "rust_profile_module.rs.tmpl",
            arch_use=arch_use,
            registrations=registrations,
            bodies=bodies,
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
            family=profile_render.profile.family,
            rust_target_features=rust_target_features(
                profile_render.profile, profile_render.profile_family
            ),
            rust_target=rust_target(profile_render.profile, profile_render.profile_family),
            rust_linker=rust_linker(profile_render.profile, profile_render.profile_family),
            emulator=_verify_emulator(profile_render.profile),
        )
        for profile_render in profiles
    )


def rust_target_features(
    profile: MachineProfile,
    capability: ProfileFamilyCapability | None = None,
) -> tuple[str, ...]:
    capability = capability or ProfileFamilyCapability(profile.family)
    if not capability.rust_target_features:
        return ()
    return tuple(
        f"+{feature_spelling(feature, profile.alternatives)}"
        for feature in sorted(profile.features)
    )


def rust_target(
    profile: MachineProfile,
    capability: ProfileFamilyCapability | None = None,
) -> str | None:
    capability = capability or ProfileFamilyCapability(profile.family)
    return capability.rust_target


def rust_linker(
    profile: MachineProfile,
    capability: ProfileFamilyCapability | None = None,
) -> str | None:
    capability = capability or ProfileFamilyCapability(profile.family)
    return capability.rust_linker


def _rust_arch_use(emitted_exts: list[str], extensions: Mapping[str, Extension]) -> str:
    modules = {
        module
        for ext in emitted_exts
        if (extension := extensions.get(ext)) is not None
        if (module := rust_arch_module(extension.family)) is not None
    }
    if not modules:
        return ""
    lines = [
        "#[allow(unused_imports)]",
        *(f"use core::arch::{module}::*;" for module in sorted(modules)),
    ]
    return "\n".join(lines) + "\n"


def _verify_emulator(profile: MachineProfile) -> VerifyEmulator | None:
    if profile.emulator is None:
        return None
    return VerifyEmulator(
        kind=profile.emulator.kind,
        profile=profile.emulator.profile,
        args=profile.emulator.args,
    )


def _rust_registrations(
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    extensions: Mapping[str, Extension],
) -> str:
    """Rust extension tag structs + SimdVector impls for the used (ext, type) pairs."""

    lines: list[str] = []
    for ext in used_exts(by_primitive):
        extension = extensions.get(ext)
        if is_x86_register_extension(ext) or _has_rust_registers(by_primitive, ext, extension):
            lines.append(f"pub struct {rust_extension_tag(ext)};")
    for ext, base in used_pairs(by_primitive):
        if not is_x86_register_extension(ext):
            continue
        register = rust_register_type(ext, base)
        mask = _rust_mask_type(extensions.get(ext), base, register)
        bits = x86_register_bits(ext)
        if bits is None:
            raise ValueError(f"unsupported Rust x86 register extension {ext!r}")
        imask = _rust_imask_type(extensions.get(ext), base, mask, bits)
        array = f"array_type<{base}, {bits // type_bits(base)}, {bits // 8}>"
        lines.append(
            f"impl SimdVector for Simd<{base}, {rust_extension_tag(ext)}> {{ "
            f"type BaseType = {base}; type RegisterType = {register}; "
            f"type MaskType = {mask}; type ImaskType = {imask}; type Array = {array}; }}"
        )
    for ext, type_tag, base in used_type_specs(by_primitive):
        if is_x86_register_extension(ext):
            continue
        extension = extensions.get(ext)
        if extension is None:
            continue
        register = extension.direct_vector_register_type("rust", type_tag)
        if register is None:
            continue
        bits = extension.vector_bits
        mask = _rust_mask_type(extension, base, register)
        imask = _rust_imask_type(extension, base, mask, bits)
        array = f"array_type<{base}, {bits // type_bits(base)}, {bits // 8}>"
        lines.append(
            f"impl SimdVector for Simd<{base}, {rust_extension_tag(ext)}> {{ "
            f"type BaseType = {base}; type RegisterType = {register}; "
            f"type MaskType = {mask}; type ImaskType = {imask}; type Array = {array}; }}"
        )
    return ("\n".join(lines) + "\n\n") if lines else ""


def _has_rust_registers(
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    ext: str,
    extension: Extension | None,
) -> bool:
    if extension is None:
        return False
    return any(
        used_ext == ext
        and extension.direct_vector_register_type("rust", type_tag) is not None
        for used_ext, type_tag, _base in used_type_specs(by_primitive)
    )


def _rust_mask_type(extension: Extension | None, base_spelling: str, register: str) -> str:
    """The Rust mask type for one (ext, base) pair."""

    if extension is None or extension.mask_policy.kind != "native_predicate_by_lanes":
        return register
    lanes = extension.vector_bits // type_bits(base_spelling)
    return extension.mask_policy.spelling_for_lanes("rust", max(8, lanes)) or register


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
    return fill_asset("rust_cargo.toml.tmpl", features="\n".join(features))
