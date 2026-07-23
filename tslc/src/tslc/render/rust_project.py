"""Render generated Rust project artifacts."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from tslc.backend.rust import RustBackend
from tslc.backend.rust_api_model import RustFacadePlan
from tslc.backend.rust_api_planner import (
    plan_rust_facade,
    validate_rust_facade_plan,
)
from tslc.backend.rust_benchmark_context import (
    RUST_BENCHMARK_CODEGEN_CONTRACT,
    RUST_BENCHMARK_POLICY_SCHEMA_VERSION,
    RUST_POLICY_CONSUMPTION_SCHEMA_VERSION,
)
from tslc.backend.rust_policy_selection import (
    RustPolicySelectionPlan,
    validate_rust_policy_selection_plan,
)
from tslc.backend.rust_package import (
    DEFAULT_RUST_PACKAGE_CONFIG,
    RustPackageConfig,
)
from tslc.backend.rust_static_selection import (
    RustStaticSelectionPlan,
    validate_rust_static_selection_plan,
)
from tslc.backend.emitted_profile import (
    EmittedProfile,
    used_extensions,
)
from tslc.backend.rust_names import rust_primitive_tag_name
from tslc.backend.target_capability import rust_arch_module
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import Extension
from tslc.catalog.target_families import ProfileFamilyCapability
from tslc.benchmark.planner import BENCHMARK_PROTOCOL_VERSION
from tslc.compiler_assets import RenderAssets
from tslc.lower.lowerer import LoweredSpecialization
from tslc.output.artifacts import Artifact
from tslc.output.verify_model import VerifyProfile, VerifyRunner
from tslc.render._common import slug, text
from tslc.render.rust_benchmark_layout import (
    RustBenchmarkLayoutPlan,
    plan_rust_benchmark_layout,
)
from tslc.render.rust_facade import rust_facade_module
from tslc.render.rust_policy_consumption import (
    EMPTY_RUST_POLICY_CONSUMPTION_RENDER_PLAN,
    RustPolicyConsumptionRenderPlan,
    RustPolicyConsumptionRenderProfile,
)
from tslc.render.rust_static_selection import (
    rust_static_fallback_cfg,
    rust_static_profile_cfg,
)
from tslc.backend.rust_algorithm import rust_algorithm_module
from tslc.backend.rust_vectors import rust_registrations, rust_vector_registrations


def rust_artifacts(
    profiles: tuple[EmittedProfile, ...],
    assets: RenderAssets,
    *,
    media_type: str,
    selection_plan: RustPolicySelectionPlan,
    static_selection_plan: RustStaticSelectionPlan,
    facade_plan: RustFacadePlan | None = None,
    consumption_plan: RustPolicyConsumptionRenderPlan = (
        EMPTY_RUST_POLICY_CONSUMPTION_RENDER_PLAN
    ),
    benchmark_layout_plan: RustBenchmarkLayoutPlan | None = None,
    package_config: RustPackageConfig = DEFAULT_RUST_PACKAGE_CONFIG,
) -> list[Artifact]:
    validate_rust_policy_selection_plan(profiles, selection_plan)
    validate_rust_static_selection_plan(profiles, static_selection_plan)
    if facade_plan is None:
        facade_plan = plan_rust_facade(profiles, static_selection_plan)
    validate_rust_facade_plan(profiles, static_selection_plan, facade_plan)
    emitted_names = {profile.profile.name for profile in profiles}
    if any(
        entry.profile.profile_name not in emitted_names
        for entry in consumption_plan.profiles
    ):
        raise ValueError("Rust policy consumption plan is foreign to the project")
    policy_profiles = consumption_plan.profiles
    if benchmark_layout_plan is None:
        benchmark_layout_plan = plan_rust_benchmark_layout(
            tuple(profile.profile.name for profile in profiles)
        )
    if tuple(
        profile.profile_name for profile in benchmark_layout_plan.profiles
    ) != tuple(profile.profile.name for profile in profiles):
        raise ValueError("Rust benchmark layout plan does not match the project")
    artifacts = [
        text(
            "rust/build.rs",
            assets.fill(
                "rust_build.rs",
                default_debug_assertions=str(
                    RUST_BENCHMARK_CODEGEN_CONTRACT.debug_assertions
                ).lower(),
                default_overflow_checks=str(
                    RUST_BENCHMARK_CODEGEN_CONTRACT.overflow_checks
                ).lower(),
                default_lto=str(RUST_BENCHMARK_CODEGEN_CONTRACT.lto).lower(),
                default_codegen_units=str(
                    RUST_BENCHMARK_CODEGEN_CONTRACT.codegen_units
                ),
                default_incremental=str(
                    RUST_BENCHMARK_CODEGEN_CONTRACT.incremental
                ).lower(),
                benchmark_codegen_contract=RUST_BENCHMARK_CODEGEN_CONTRACT.identity,
                policy_modules=_rust_build_policy_modules(policy_profiles),
                policy_profiles=_rust_build_policy_profiles(policy_profiles),
            ),
            media_type=media_type,
        ),
        text(
            "rust/src/tsl_core.rs",
            _rust_core(profiles, assets),
            media_type=media_type,
        ),
        text(
            "rust/src/tsl_algorithm.rs",
            assets.text("tsl_algorithm.rs"),
            media_type=media_type,
        ),
        text(
            "rust/src/tsl_facade.rs",
            rust_facade_module(facade_plan, assets),
            media_type=media_type,
        ),
        text(
            "rust/src/tsl_rust_cpu_identity.rs",
            assets.text("tsl_rust_cpu_identity.rs"),
            media_type=media_type,
        ),
        text(
            "rust/tsl_rust_policy_json.rs",
            assets.text("tsl_rust_policy_json.rs"),
            media_type=media_type,
        ),
        text(
            "rust/tsl_rust_variant_policy.rs",
            assets.text("tsl_rust_variant_policy.rs"),
            media_type=media_type,
        ),
        text(
            "rust/tsl_rust_variant_policy_protocol.rs",
            assets.fill(
                "tsl_rust_variant_policy_protocol.rs",
                descriptor_schema_version=str(
                    RUST_POLICY_CONSUMPTION_SCHEMA_VERSION
                ),
                policy_schema_version=str(RUST_BENCHMARK_POLICY_SCHEMA_VERSION),
                benchmark_protocol_version=str(BENCHMARK_PROTOCOL_VERSION),
            ),
            media_type=media_type,
        ),
        text(
            "rust/tsl_rust_variant_policy_validation.rs",
            assets.text("tsl_rust_variant_policy_validation.rs"),
            media_type=media_type,
        ),
        # Ship the formatter config at the crate root so `rustfmt`/`cargo fmt` finds it and the
        # generated crate is self-contained.
        text("rust/rustfmt.toml", assets.text("rustfmt.toml"), media_type=media_type),
    ]
    for emitted_profile in profiles:
        benchmark_layout = benchmark_layout_plan.profile(emitted_profile.profile.name)
        if benchmark_layout is None:
            raise ValueError("Rust project rendering requires benchmark layout profiles")
        policy_selection = selection_plan.profile(emitted_profile.profile.name)
        if policy_selection is None:
            raise ValueError(
                "Rust project rendering requires complete policy-selection profiles"
            )
        consumption = consumption_plan.profile(emitted_profile.profile.name)
        capability = emitted_profile.profile_family or ProfileFamilyCapability(
            emitted_profile.profile.family
        )
        backend = RustBackend(
            feature_spellings=emitted_profile.profile.feature_spellings("rust"),
            emit_target_features=capability.backend("rust").feature_flags,
            policy_selection=policy_selection,
            deferred_policy_mapping_file=(
                consumption.names.materialized_mapping_file
                if consumption is not None
                else None
            ),
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
        static_selection = static_selection_plan.profile(
            emitted_profile.profile.name
        )
        module_cfg = (
            rust_static_profile_cfg(static_selection)
            if static_selection is not None
            else "any()"
        )
        content = assets.fill(
            "rust_profile_module.rs.tmpl",
            module_cfg_attr=f"#![cfg({module_cfg})]",
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
            text(
                f"rust/benches/{benchmark_layout.benchmark_target}.rs",
                assets.fill(
                    "rust_benchmark_main.rs.tmpl",
                    profile_slug=benchmark_layout.profile_slug,
                ),
                media_type=media_type,
            )
        )

    fallback_by_primitive = (
        static_selection_plan.fallback_module.specializations_by_primitive()
    )
    fallback_extensions = static_selection_plan.fallback_module.extensions_by_name()
    fallback_backend = RustBackend(emit_target_features=False)
    fallback_internal = "\n\n".join(
        rendered
        for name in sorted(fallback_by_primitive)
        if (
            rendered := fallback_backend.render_primitive_internal(
                name, fallback_by_primitive[name]
            )
        )
    )
    fallback_public = "\n\n".join(
        fallback_backend.render_primitive_public(
            name, fallback_by_primitive[name]
        )
        for name in sorted(fallback_by_primitive)
    )
    fallback_bodies = "\n\n".join(
        part
        for part in (
            fallback_backend.render_primitive_module(fallback_internal),
            fallback_public,
            fallback_backend.render_implementation_state_queries(
                fallback_by_primitive
            ),
        )
        if part
    )
    fallback_content = assets.fill(
        "rust_profile_module.rs.tmpl",
        module_cfg_attr="",
        arch_use=_rust_arch_use(
            used_extensions(fallback_by_primitive), fallback_extensions
        ),
        profile_metadata=assets.fill(
            "rust_profile_metadata.rs.tmpl",
            profile_name=json.dumps("target_fallback"),
            profile_family=json.dumps("generic"),
        ).rstrip(),
        registrations=rust_registrations(
            fallback_by_primitive, fallback_extensions
        ),
        bodies=fallback_bodies,
        algorithm=rust_algorithm_module(
            fallback_by_primitive, fallback_extensions, assets
        ),
    )
    artifacts.append(
        text(
            "rust/src/tsl_target_fallback.rs",
            fallback_content,
            media_type=media_type,
        )
    )

    artifacts.append(
        text(
            "rust/src/lib.rs",
            _rust_lib(profiles, static_selection_plan, assets),
            media_type=media_type,
        )
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
            _rust_cargo(
                benchmark_layout_plan,
                assets,
                package_config,
            ),
            media_type=media_type,
        )
    )
    artifacts.append(
        text(
            f"rust/{package_config.readme}",
            assets.fill(
                "rust_readme.md.tmpl",
                package_name=package_config.name,
                documentation_url=package_config.documentation,
                repository_url=package_config.repository,
            ),
            media_type="text/markdown",
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


def _rust_core(profiles: Sequence[EmittedProfile], assets: RenderAssets) -> str:
    core = assets.text("tsl_core.rs").rstrip()
    register_impls = _rust_valid_bit_pattern_impls(profiles)
    return f"{core}\n\n{register_impls}\n" if register_impls else f"{core}\n"


def _rust_valid_bit_pattern_impls(profiles: Sequence[EmittedProfile]) -> str:
    """Render destination-validity proofs from typed vector registrations."""

    registers: set[tuple[str, str]] = set()
    for emitted_profile in profiles:
        by_primitive = emitted_profile.specializations("rust")
        for registration in rust_vector_registrations(
            by_primitive, emitted_profile.extensions
        ):
            extension = emitted_profile.extensions.get(registration.extension_name)
            arch = rust_arch_module(extension)
            if arch is not None:
                registers.add((arch, registration.register_spelling))
    lines: list[str] = []
    for arch, spelling in sorted(registers):
        lines.extend(
            (
                f'#[cfg(target_arch = "{arch}")]',
                "// SAFETY: Rust SIMD registers accept every bit pattern; the typed",
                "// registration plan supplies only concrete register types.",
                f"unsafe impl ValidBitPattern for {spelling} {{}}",
            )
        )
    return "\n".join(lines)


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
        f"+{profile.feature_spelling(feature, 'rust')}"
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
    static_selection_plan: RustStaticSelectionPlan,
    assets: RenderAssets,
) -> str:
    # `non_upper_case_globals` is allowed so an `sImm` immediate can keep its corpus name
    # as a lowercase const-generic, matching the body that uses it.
    primitive_tags = _rust_primitive_tags(profiles, assets)
    profile_slugs = tuple(
        slug(selection.profile_name)
        for selection in static_selection_plan.profiles
    )
    profile_modules = "\n\n".join(
        assets.fill(
            "rust_lib_profile.rs.tmpl",
            profile_slug=profile_slug,
            module_cfg_attr=f"#[cfg({rust_static_profile_cfg(selection)})]",
            selected_profile_cfg=rust_static_profile_cfg(selection),
        ).rstrip()
        for profile_slug, selection in zip(
            profile_slugs, static_selection_plan.profiles, strict=True
        )
    )
    fallback_cfg = rust_static_fallback_cfg(static_selection_plan)
    fallback_module = assets.fill(
        "rust_lib_profile.rs.tmpl",
        profile_slug="target_fallback",
        module_cfg_attr="",
        selected_profile_cfg=fallback_cfg,
    ).rstrip()
    profile_modules = "\n\n".join(
        part for part in (profile_modules, fallback_module) if part
    )
    selections_by_name = {
        selection.profile_name: selection
        for selection in static_selection_plan.profiles
    }
    benchmark_modules = "\n\n".join(
        assets.fill(
            "rust_lib_benchmark_profile.rs.tmpl",
            profile_slug=slug(profile.profile.name),
            selected_profile_cfg=(
                rust_static_profile_cfg(selection)
                if (
                    selection := selections_by_name.get(profile.profile.name)
                )
                is not None
                else fallback_cfg
            ),
        ).rstrip()
        for profile in profiles
    )
    return assets.fill(
        "rust_lib.rs.tmpl",
        primitive_tags=(f"{primitive_tags}\n\n" if primitive_tags else ""),
        profile_modules=profile_modules,
        benchmark_modules=benchmark_modules,
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


def _rust_build_policy_profiles(
    profiles: tuple[RustPolicyConsumptionRenderProfile, ...],
) -> str:
    if not profiles:
        return "&[]"
    entries = [
        (
            "tsl_rust_variant_policy::GeneratedProfile {",
            f"    name: {json.dumps(entry.profile.profile_name)},",
            "    target_arch: "
            f"{json.dumps(entry.static_selection.requirement.target_arch)},",
            "    target_features: &["
            + ", ".join(
                json.dumps(feature)
                for feature in entry.static_selection.requirement.target_features
            )
            + "],",
            "    stronger_requirements: &["
            + ", ".join(
                "tsl_rust_variant_policy::GeneratedTargetRequirement { "
                f"target_arch: {json.dumps(requirement.target_arch)}, "
                "target_features: &["
                + ", ".join(
                    json.dumps(feature)
                    for feature in requirement.target_features
                )
                + "] }"
                for requirement in entry.static_selection.stronger_requirements
            )
            + "],",
            "    descriptor_relative_path: "
            f'"{entry.names.descriptor_path}",',
            "    descriptor: "
            f'include_str!("{entry.names.descriptor_path}"),',
            "    mappings: "
            f"tsl_rust_policy_data_{entry.names.profile_slug}::MAPPINGS,",
            "    materialized_mapping_file: "
            f'"{entry.names.materialized_mapping_file}",',
            "    required_rustflags: &["
            + ", ".join(
                json.dumps(flag)
                for flag in RUST_BENCHMARK_CODEGEN_CONTRACT.policy_rustflags_for(
                    entry.profile.required_features
                )
            )
            + "],",
            "    required_incremental_environment: "
            + json.dumps(
                RUST_BENCHMARK_CODEGEN_CONTRACT.policy_incremental_environment
            )
            + ",",
            "}",
        )
        for entry in profiles
    ]
    if len(entries) == 1:
        return "&[" + "\n".join(entries[0]) + "]"
    return "&[\n" + "\n".join(
        "\n".join(f"    {line}" for line in entry[:-1]) + "\n    },"
        for entry in entries
    ) + "\n]"


def _rust_build_policy_modules(
    profiles: tuple[RustPolicyConsumptionRenderProfile, ...],
) -> str:
    return "\n".join(
        "\n".join(
            (
                f'#[path = "{entry.names.mapping_source_path}"]',
                f"mod tsl_rust_policy_data_{entry.names.profile_slug};",
            )
        )
        for entry in profiles
    )


def _rust_cargo(
    benchmark_layout_plan: RustBenchmarkLayoutPlan,
    assets: RenderAssets,
    package_config: RustPackageConfig,
) -> str:
    features = ["default = []", "std = []", 'runtime-dispatch = ["std"]']
    bench_targets = "\n\n".join(
        assets.fill(
            "rust_benchmark_target.toml.tmpl",
            profile_slug=profile.profile_slug,
            benchmark_target=profile.benchmark_target,
        ).rstrip()
        for profile in benchmark_layout_plan.profiles
    )
    return assets.fill(
        "rust_cargo.toml.tmpl",
        package_name=json.dumps(package_config.name),
        package_version=json.dumps(package_config.version),
        package_edition=json.dumps(package_config.edition),
        rust_version=json.dumps(package_config.rust_version),
        package_license=json.dumps(package_config.license),
        repository_url=json.dumps(package_config.repository),
        documentation_url=json.dumps(package_config.documentation),
        readme_path=json.dumps(package_config.readme),
        features="\n".join(features),
        bench_targets=(
            "\n\n"
            + "\n\n".join(
                part for part in (bench_targets,) if part
            )
            if bench_targets
            else ""
        ),
        benchmark_profile=RUST_BENCHMARK_CODEGEN_CONTRACT.render_cargo_profile(),
    )
