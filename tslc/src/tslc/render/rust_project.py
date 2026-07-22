"""Render generated Rust project artifacts."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from tslc.backend.rust import RustBackend
from tslc.backend.rust_benchmark_context import (
    RUST_BENCHMARK_CODEGEN_CONTRACT,
    RUST_BENCHMARK_POLICY_SCHEMA_VERSION,
    RUST_POLICY_CONSUMPTION_SCHEMA_VERSION,
)
from tslc.backend.rust_policy_selection import (
    RustPolicySelectionPlan,
    validate_rust_policy_selection_plan,
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
from tslc.render.rust_policy_consumption import (
    EMPTY_RUST_POLICY_CONSUMPTION_RENDER_PLAN,
    RustPolicyConsumptionRenderPlan,
    RustPolicyConsumptionRenderProfile,
)
from tslc.backend.rust_algorithm import rust_algorithm_module
from tslc.backend.rust_vectors import rust_registrations
from tslc.value_tests.compile_failure import compile_failure_target_name
from tslc.value_tests.model import ValueTestProjectPlan


def rust_artifacts(
    profiles: tuple[EmittedProfile, ...],
    assets: RenderAssets,
    *,
    media_type: str,
    selection_plan: RustPolicySelectionPlan,
    consumption_plan: RustPolicyConsumptionRenderPlan = (
        EMPTY_RUST_POLICY_CONSUMPTION_RENDER_PLAN
    ),
    benchmark_layout_plan: RustBenchmarkLayoutPlan | None = None,
    value_tests: ValueTestProjectPlan | None = None,
) -> list[Artifact]:
    validate_rust_policy_selection_plan(profiles, selection_plan)
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
        text("rust/src/tsl_core.rs", assets.text("tsl_core.rs"), media_type=media_type),
        text(
            "rust/src/tsl_algorithm.rs",
            assets.text("tsl_algorithm.rs"),
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
            text(
                f"rust/benches/{benchmark_layout.benchmark_target}.rs",
                assets.fill(
                    "rust_benchmark_main.rs.tmpl",
                    profile_slug=benchmark_layout.profile_slug,
                ),
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
            _rust_cargo(benchmark_layout_plan, assets, value_tests=value_tests),
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
    benchmark_modules = "\n\n".join(
        assets.fill(
            "rust_lib_benchmark_profile.rs.tmpl",
            profile_slug=profile_slug,
        ).rstrip()
        for profile_slug in profile_slugs
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


def _rust_selected_profile_cfg(profile_slug: str, profile_slugs: tuple[str, ...]) -> str:
    other_slugs = tuple(slug for slug in profile_slugs if slug != profile_slug)
    if not other_slugs:
        return f'feature = "{profile_slug}"'
    others = ", ".join(f'feature = "{other}"' for other in other_slugs)
    return f'all(feature = "{profile_slug}", not(any({others})))'


def _rust_build_policy_profiles(
    profiles: tuple[RustPolicyConsumptionRenderProfile, ...],
) -> str:
    if not profiles:
        return "&[]"
    entries = [
        (
            "tsl_rust_variant_policy::GeneratedProfile {",
            f"    name: {json.dumps(entry.profile.profile_name)},",
            f'    feature_environment: "{entry.names.feature_environment}",',
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
                for flag in RUST_BENCHMARK_CODEGEN_CONTRACT.policy_rustflags
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
    *,
    value_tests: ValueTestProjectPlan | None = None,
) -> str:
    profile_slugs = tuple(
        profile.profile_slug for profile in benchmark_layout_plan.profiles
    )
    default = (
        "scalar"
        if "scalar" in profile_slugs
        else profile_slugs[0] if profile_slugs else "scalar"
    )
    features = [f'default = ["{default}"]']
    features.extend(f"{profile_slug} = []" for profile_slug in profile_slugs)
    # Opt-in feature that compiles+runs the generated value tests (parity with the C++ ctest gate).
    features.append("value_tests = []")
    # Benchmark targets stay outside ordinary builds unless explicitly requested.
    features.append("variant_benchmarks = []")
    compile_failure_targets: list[str] = []
    if value_tests is not None:
        for profile in value_tests.profiles_for("rust"):
            for case in profile.compile_failure_cases:
                target = compile_failure_target_name(profile, case)
                features.append(f"{target} = []")
                compile_failure_targets.append(
                    "\n".join(
                        (
                            "[[example]]",
                            f'name = "{target}"',
                            f'path = "examples/{target}.rs"',
                            f'required-features = ["{target}"]',
                        )
                    )
                )
    bench_targets = "\n\n".join(
        assets.fill(
            "rust_benchmark_target.toml.tmpl",
            profile_slug=profile.profile_slug,
            benchmark_target=profile.benchmark_target,
            required_features=", ".join(
                json.dumps(feature) for feature in profile.cargo_features
            ),
        ).rstrip()
        for profile in benchmark_layout_plan.profiles
    )
    return assets.fill(
        "rust_cargo.toml.tmpl",
        features="\n".join(features),
        bench_targets=(
            "\n\n"
            + "\n\n".join(
                part for part in (bench_targets, *compile_failure_targets) if part
            )
            if bench_targets or compile_failure_targets
            else ""
        ),
        benchmark_profile=RUST_BENCHMARK_CODEGEN_CONTRACT.render_cargo_profile(),
    )
