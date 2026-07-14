"""Render generated Rust project artifacts."""

from __future__ import annotations

import json
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
from tslc.lower.lowerer import LoweredSpecialization
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
            profile_metadata=assets.fill(
                "rust_profile_metadata.rs.tmpl",
                profile_name=json.dumps(slug(emitted_profile.profile.name)),
                profile_family=json.dumps(emitted_profile.profile.family),
            ).rstrip(),
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

    artifacts.append(
        text("rust/src/lib.rs", _rust_lib(profiles, assets), media_type=media_type)
    )
    artifacts.append(
        text(
            "rust/src/tsl_documentation.rs",
            _rust_documentation_module(profiles, assets),
            media_type=media_type,
        )
    )
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
            assets.text("rust_smoke.rs"),
            media_type=media_type,
        )
    )
    return artifacts


def rust_verify_profiles(profiles: tuple[EmittedProfile, ...]) -> tuple[VerifyProfile, ...]:
    return tuple(
        rust_verify_profile(emitted_profile.profile, emitted_profile.profile_family)
        for emitted_profile in profiles
    )


def rust_verify_profile(
    profile: MachineProfile,
    capability: ProfileFamilyCapability | None = None,
) -> VerifyProfile:
    """Project a source machine profile into verifier-owned Rust facts."""

    return VerifyProfile(
        profile_name=slug(profile.name),
        file_stem=slug(profile.name),
        family=profile.family,
        native_without_runner=(
            capability.native_without_runner if capability is not None else False
        ),
        compile_modes=profile.compile_modes,
        target_features=rust_target_features(profile, capability),
        target=rust_target(profile, capability),
        linker=rust_linker(profile, capability),
        runner=_verify_runner(profile),
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


def _rust_lib(
    profiles: tuple[EmittedProfile, ...],
    assets: RenderAssets,
) -> str:
    # `non_upper_case_globals` is allowed so an `sImm` immediate can keep its corpus name
    # as a lowercase const-generic, matching the body that uses it.
    primitive_tags = _rust_primitive_tags(profiles, assets)
    profile_slugs = tuple(slug(emitted_profile.profile.name) for emitted_profile in profiles)
    profile_modules = "\n\n".join(
        assets.fill(
            "rust_lib_profile.rs.tmpl",
            profile_slug=profile_slug,
            selected_profile_cfg=_rust_selected_profile_cfg(profile_slug, profile_slugs),
        ).rstrip()
        for profile_slug in profile_slugs
    )
    return assets.fill(
        "rust_lib.rs.tmpl",
        primitive_tags=(f"{primitive_tags}\n\n" if primitive_tags else ""),
        profile_modules=profile_modules,
    )


def _rust_documentation_module(
    profiles: tuple[EmittedProfile, ...],
    assets: RenderAssets,
) -> str:
    """Render one architecture-neutral rustdoc facade from all emitted profiles."""

    by_primitive: dict[str, list[LoweredSpecialization]] = {}
    for emitted_profile in profiles:
        for primitive_name, specializations in sorted(
            emitted_profile.specializations("rust").items()
        ):
            by_primitive.setdefault(primitive_name, []).extend(specializations)
    backend = RustBackend(emit_target_features=False)
    bodies = "\n\n".join(
        backend.render_documentation_api(
            primitive_name,
            tuple(by_primitive[primitive_name]),
        )
        for primitive_name in sorted(by_primitive)
    )
    return assets.fill(
        "rust_documentation.rs.tmpl",
        bodies=f"\n\n{bodies}" if bodies else "",
    )


def _rust_primitive_tags(
    profiles: tuple[EmittedProfile, ...],
    assets: RenderAssets,
) -> str:
    names = sorted(
        {
            primitive
            for emitted_profile in profiles
            for primitive in emitted_profile.specializations("rust")
        }
    )
    if not names:
        return ""
    declarations = "\n".join(
        f"    pub struct {rust_primitive_tag_name(name)};" for name in names
    )
    return assets.fill(
        "rust_primitive_tags.rs.tmpl",
        declarations=f"\n{declarations}",
    ).rstrip()


def _rust_selected_profile_cfg(profile_slug: str, profile_slugs: tuple[str, ...]) -> str:
    other_slugs = tuple(slug for slug in profile_slugs if slug != profile_slug)
    if not other_slugs:
        return f'feature = "{profile_slug}"'
    others = ", ".join(f'feature = "{other}"' for other in other_slugs)
    return f'all(feature = "{profile_slug}", not(any({others})))'


def _rust_cargo(profiles: tuple[EmittedProfile, ...], assets: RenderAssets) -> str:
    profile_slugs = tuple(slug(profile.profile.name) for profile in profiles)
    default = (
        "scalar"
        if "scalar" in profile_slugs
        else profile_slugs[0] if profile_slugs else "scalar"
    )
    features = [f'default = ["{default}"]']
    features.extend(f"{slug(emitted_profile.profile.name)} = []" for emitted_profile in profiles)
    # Opt-in feature that compiles+runs the generated value tests (parity with the C++ ctest gate).
    features.append("value_tests = []")
    return assets.fill("rust_cargo.toml.tmpl", features="\n".join(features))
