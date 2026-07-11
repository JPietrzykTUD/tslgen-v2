"""Render generated Rust project artifacts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from tslc.backend.rust import RustBackend
from tslc.backend.emitted_profile import (
    EmittedProfile,
    used_extensions,
)
from tslc.backend.rust_names import rust_primitive_tag_name
from tslc.backend.target_capability import feature_spelling, rust_arch_module
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import Extension
from tslc.catalog.target_families import ProfileFamilyCapability
from tslc.compiler_assets import RenderAssets
from tslc.output.artifacts import Artifact
from tslc.output.verify_model import VerifyProfile, VerifyRunner
from tslc.render._common import slug, text
from tslc.backend.rust_algorithm import rust_algorithm_module
from tslc.backend.rust_vectors import rust_registrations


def rust_artifacts(
    profiles: tuple[EmittedProfile, ...],
    assets: RenderAssets,
    *,
    media_type: str,
) -> list[Artifact]:
    artifacts = [
        text("rust/src/tsl_core.rs", assets.text("tsl_core.rs"), media_type=media_type),
        text(
            "rust/src/tsl_algorithm.rs",
            assets.text("tsl_algorithm.rs"),
            media_type=media_type,
        ),
        # Ship the formatter config at the crate root so `rustfmt`/`cargo fmt` finds it and the
        # generated crate is self-contained.
        text("rust/rustfmt.toml", assets.text("rustfmt.toml"), media_type=media_type),
    ]
    for emitted_profile in profiles:
        capability = emitted_profile.profile_family or ProfileFamilyCapability(
            emitted_profile.profile.family
        )
        backend = RustBackend(
            feature_alternatives=emitted_profile.profile.alternatives,
            emit_target_features=capability.backend("rust").feature_flags,
        )
        by_primitive = emitted_profile.specializations("rust")
        registrations = rust_registrations(by_primitive, emitted_profile.extensions)
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
            used_extensions(by_primitive), emitted_profile.extensions
        )
        content = assets.fill(
            "rust_profile_module.rs.tmpl",
            arch_use=arch_use,
            registrations=registrations,
            bodies=bodies,
            algorithm=rust_algorithm_module(
                by_primitive, emitted_profile.extensions, assets
            ),
        )
        artifacts.append(
            text(
                f"rust/src/tsl_{slug(emitted_profile.profile.name)}.rs",
                content,
                media_type=media_type,
            )
        )

    artifacts.append(text("rust/src/lib.rs", _rust_lib(profiles), media_type=media_type))
    artifacts.append(
        text(
            "rust/Cargo.toml",
            _rust_cargo(profiles, assets),
            media_type=media_type,
        )
    )
    artifacts.append(
        text(
            "rust/tests/smoke.rs",
            "#[test]\nfn smoke() {\n    assert!(true);\n}\n",
            media_type=media_type,
        )
    )
    return artifacts


def rust_verify_profiles(profiles: tuple[EmittedProfile, ...]) -> tuple[VerifyProfile, ...]:
    return tuple(
        VerifyProfile(
            profile_name=slug(emitted_profile.profile.name),
            file_stem=slug(emitted_profile.profile.name),
            family=emitted_profile.profile.family,
            compile_modes=emitted_profile.profile.compile_modes,
            target_features=rust_target_features(
                emitted_profile.profile, emitted_profile.profile_family
            ),
            target=rust_target(emitted_profile.profile, emitted_profile.profile_family),
            linker=rust_linker(emitted_profile.profile, emitted_profile.profile_family),
            runner=_verify_runner(emitted_profile.profile),
        )
        for emitted_profile in profiles
    )


def rust_target_features(
    profile: MachineProfile,
    capability: ProfileFamilyCapability | None = None,
) -> tuple[str, ...]:
    capability = capability or ProfileFamilyCapability(profile.family)
    if not capability.backend("rust").feature_flags:
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
    return capability.backend("rust").target


def rust_linker(
    profile: MachineProfile,
    capability: ProfileFamilyCapability | None = None,
) -> str | None:
    capability = capability or ProfileFamilyCapability(profile.family)
    return capability.backend("rust").linker


def _rust_arch_use(
    emitted_exts: Sequence[str],
    extensions: Mapping[str, Extension],
) -> str:
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


def _rust_lib(profiles: tuple[EmittedProfile, ...]) -> str:
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
    profile_slugs = tuple(slug(emitted_profile.profile.name) for emitted_profile in profiles)
    for profile_slug in profile_slugs:
        lines.append(f'#[cfg(feature = "{profile_slug}")]')
        lines.append(f"pub mod tsl_{profile_slug};")
        lines.append(f"#[cfg({_rust_selected_profile_cfg(profile_slug, profile_slugs)})]")
        lines.append(f"pub use crate::tsl_{profile_slug} as profile;")
        lines.append("")
    return "\n".join(lines)


def _rust_primitive_tags(profiles: tuple[EmittedProfile, ...]) -> str:
    names = sorted(
        {
            primitive
            for emitted_profile in profiles
            for primitive in emitted_profile.specializations("rust")
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


def _rust_cargo(profiles: tuple[EmittedProfile, ...], assets: RenderAssets) -> str:
    default = slug(profiles[0].profile.name) if profiles else "scalar"
    features = [f'default = ["{default}"]']
    features.extend(f"{slug(emitted_profile.profile.name)} = []" for emitted_profile in profiles)
    # Opt-in feature that compiles+runs the generated value tests (parity with the C++ ctest gate).
    features.append("value_tests = []")
    return assets.fill("rust_cargo.toml.tmpl", features="\n".join(features))
