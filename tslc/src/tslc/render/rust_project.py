"""Render generated Rust project artifacts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from tslc.backend.rust import RustBackend
from tslc.backend.rust_names import rust_primitive_tag_name
from tslc.backend.target_capability import rust_arch_module
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import Extension
from tslc.catalog.target_families import ProfileFamilyCapability
from tslc.compiler_assets import RenderAssets
from tslc.output.artifacts import Artifact
from tslc.output.verify_model import VerifyProfile, VerifyRunner
from tslc.render._common import (
    feature_spelling,
    slug,
    text,
    used_exts,
)
from tslc.render.rust_algorithm import rust_algorithm_module
from tslc.render.rust_vectors import rust_registrations

if TYPE_CHECKING:
    from tslc.render.project import ProfileRender


def rust_artifacts(
    profiles: tuple[ProfileRender, ...], assets: RenderAssets
) -> list[Artifact]:
    artifacts = [
        text("rust/src/tsl_core.rs", assets.text("tsl_core.rs")),
        text("rust/src/tsl_algorithm.rs", assets.text("tsl_algorithm.rs")),
        # Ship the formatter config at the crate root so `rustfmt`/`cargo fmt` finds it and the
        # generated crate is self-contained.
        text("rust/rustfmt.toml", assets.text("rustfmt.toml")),
    ]
    for profile_render in profiles:
        capability = profile_render.profile_family or ProfileFamilyCapability(
            profile_render.profile.family
        )
        backend = RustBackend(
            feature_alternatives=profile_render.profile.alternatives,
            emit_target_features=capability.rust_target_features,
        )
        by_primitive = profile_render.specializations("rust")
        registrations = rust_registrations(by_primitive, profile_render.extensions)
        internal = "\n\n".join(
            rendered
            for name in sorted(by_primitive)
            if (rendered := backend.render_primitive_internal(name, by_primitive[name]))
        )
        public = "\n\n".join(
            backend.render_primitive_public(name, by_primitive[name])
            for name in sorted(by_primitive)
        )
        bodies = "\n\n".join(
            part
            for part in (
                backend.render_primitive_module(internal),
                public,
                backend.render_implementation_state_queries(by_primitive),
            )
            if part
        )
        # Arch modules are imported for intrinsic constants left verbatim in bodies.
        # Intrinsics themselves stay fully qualified by lowering.
        arch_use = _rust_arch_use(
            used_exts(by_primitive), profile_render.extensions
        )
        content = assets.fill(
            "rust_profile_module.rs.tmpl",
            arch_use=arch_use,
            registrations=registrations,
            bodies=bodies,
            algorithm=rust_algorithm_module(
                by_primitive, profile_render.extensions, assets
            ),
        )
        artifacts.append(text(f"rust/src/tsl_{slug(profile_render.profile.name)}.rs", content))

    artifacts.append(text("rust/src/lib.rs", _rust_lib(profiles)))
    artifacts.append(text("rust/Cargo.toml", _rust_cargo(profiles, assets)))
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
            runner=_verify_runner(profile_render.profile),
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
        if (module := rust_arch_module(extension)) is not None
    }
    if not modules:
        return ""
    lines = [
        "#[allow(unused_imports)]",
        *(f"use core::arch::{module}::*;" for module in sorted(modules)),
    ]
    return "\n".join(lines) + "\n"


def _verify_runner(profile: MachineProfile) -> VerifyRunner | None:
    if profile.runner is None:
        return None
    return VerifyRunner(
        kind=profile.runner.kind,
        profile=profile.runner.profile,
        args=profile.runner.args,
    )


def _rust_lib(profiles: tuple[ProfileRender, ...]) -> str:
    # `non_upper_case_globals` is allowed so an `sImm` immediate can keep its corpus name
    # as a lowercase const-generic, matching the body that uses it.
    lines = [
        "#![allow(dead_code)]",
        "#![allow(non_camel_case_types)]",
        "#![allow(non_upper_case_globals)]",
        "",
        "pub mod tsl_core;",
        "pub mod tsl_algorithm;",
        "pub mod tsl_test_core;",
        "pub use tsl_algorithm::dataparallel;",
        "",
    ]
    primitive_tags = _rust_primitive_tags(profiles)
    if primitive_tags:
        lines.extend([primitive_tags, ""])
    profile_slugs = tuple(slug(profile_render.profile.name) for profile_render in profiles)
    for profile_slug in profile_slugs:
        lines.append(f'#[cfg(feature = "{profile_slug}")]')
        lines.append(f"pub mod tsl_{profile_slug};")
        lines.append(f"#[cfg({_rust_selected_profile_cfg(profile_slug, profile_slugs)})]")
        lines.append(f"pub use crate::tsl_{profile_slug} as profile;")
        lines.append("")
    return "\n".join(lines)


def _rust_primitive_tags(profiles: tuple[ProfileRender, ...]) -> str:
    names = sorted(
        {
            primitive
            for profile_render in profiles
            for primitive in profile_render.specializations("rust")
        }
    )
    if not names:
        return ""
    lines = [
        "pub mod primitive {",
        *(f"    pub struct {rust_primitive_tag_name(name)};" for name in names),
        "}",
    ]
    return "\n".join(lines)


def _rust_selected_profile_cfg(profile_slug: str, profile_slugs: tuple[str, ...]) -> str:
    other_slugs = tuple(slug for slug in profile_slugs if slug != profile_slug)
    if not other_slugs:
        return f'feature = "{profile_slug}"'
    others = ", ".join(f'feature = "{other}"' for other in other_slugs)
    return f'all(feature = "{profile_slug}", not(any({others})))'


def _rust_cargo(profiles: tuple[ProfileRender, ...], assets: RenderAssets) -> str:
    default = slug(profiles[0].profile.name) if profiles else "scalar"
    features = [f'default = ["{default}"]']
    features.extend(f"{slug(profile_render.profile.name)} = []" for profile_render in profiles)
    # Opt-in feature that compiles+runs the generated value tests (parity with the C++ ctest gate).
    features.append("value_tests = []")
    return assets.fill("rust_cargo.toml.tmpl", features="\n".join(features))
