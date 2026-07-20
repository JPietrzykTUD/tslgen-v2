"""Rust generated-backend capability registration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tslc.backend.capability import (
    BackendCapability,
    BackendDocumentationFormatter,
    DocumentationSiteInput,
    GeneratedDocumentationBuilder,
    GeneratedDocumentationSpec,
    GeneratedFormatSpec,
)
from tslc.backend.helper_requirements import RUST_HELPER_MANIFEST
from tslc.backend.rust import RustBackend
from tslc.backend.rust_policy_selection import plan_rust_policy_selection
from tslc.backend.rust_policy_consumption import plan_rust_policy_consumption
from tslc.backend.rust_translation import RustBackendDialect
from tslc.backend.rust_validation import validate_rust_profiles
from tslc.benchmark.planner import (
    BenchmarkPlanner,
    BenchmarkProfileContext,
    BenchmarkScenarioAdmission,
)
from tslc.benchmark.render_rust import rust_benchmark_artifacts
from tslc.catalog.model import Catalog
from tslc.output._verify_rust import (
    create_rust_verify_driver as _create_rust_verify_driver,
)
from tslc.output._verify_rust_config import rust_toolchain_commands
from tslc.render.documentation_formatters import RUST_DOCUMENTATION_FORMATTER
from tslc.render.rust_benchmark_layout import plan_rust_benchmark_layout
from tslc.render.rust_policy_consumption import plan_rust_policy_consumption_render
from tslc.render.rust_project import (
    rust_artifacts,
    rust_verify_profile,
    rust_verify_profiles,
)
from tslc.render.tests_project import rust_test_artifacts
from tslc.value_tests.render_rust import RUST_VALUE_TEST_SUPPORT

if TYPE_CHECKING:
    from tslc.benchmark.model import BenchmarkProjectPlan
    from tslc.backend.translation import BackendDialect
    from tslc.backend.emitted_profile import EmittedProfile
    from tslc.compiler_assets import RenderAssets
    from tslc.output.artifacts import Artifact
    from tslc.output.verify_drivers import VerifyBackendDriver
    from tslc.output.verify_model import VerifyProfile
    from tslc.lower.lowerer import LoweredSpecialization
    from tslc.value_tests.model import ValueTestBackendSupport, ValueTestProjectPlan


_RUST_SSE2_BENCHMARK_CONTEXT = BenchmarkProfileContext(
    profile_name="sse2",
    profile_family="x86",
    features=frozenset({"sse", "sse2"}),
    backend_feature_spellings=("sse", "sse2"),
    compile_modes=frozenset(),
    backend_flags=(),
)
_RUST_AVX2_BENCHMARK_CONTEXT = BenchmarkProfileContext(
    profile_name="avx2",
    profile_family="x86",
    features=frozenset(
        {"avx", "avx2", "rdrand", "sse", "sse2", "sse4_1", "sse4_2", "ssse3"}
    ),
    backend_feature_spellings=(
        "avx",
        "avx2",
        "rdrand",
        "sse",
        "sse2",
        "sse4.1",
        "sse4.2",
        "ssse3",
    ),
    compile_modes=frozenset(),
    backend_flags=(),
)
_RUST_BENCHMARK_ADMISSIONS = frozenset(
    {
        BenchmarkScenarioAdmission(_RUST_AVX2_BENCHMARK_CONTEXT, "reduction"),
        BenchmarkScenarioAdmission(_RUST_SSE2_BENCHMARK_CONTEXT, "immediate"),
        BenchmarkScenarioAdmission(_RUST_SSE2_BENCHMARK_CONTEXT, "register"),
    }
)


def create_rust_dialect(catalog: Catalog) -> BackendDialect:
    return RustBackendDialect(catalog)


def rust_profile_verification(
    profiles: tuple[EmittedProfile, ...],
) -> tuple[VerifyProfile, ...]:
    return rust_verify_profiles(profiles)


def rust_value_test_support() -> ValueTestBackendSupport:
    return RUST_VALUE_TEST_SUPPORT


def rust_value_test_artifacts(
    plan: ValueTestProjectPlan, assets: RenderAssets, media_type: str
) -> list[Artifact]:
    return rust_test_artifacts(plan, assets, media_type=media_type)


def rust_benchmark_plan(
    catalog: Catalog,
    profiles: tuple[EmittedProfile, ...],
    value_tests: ValueTestProjectPlan,
) -> BenchmarkProjectPlan:
    return BenchmarkPlanner(
        catalog,
        backend_id="rust",
        supported_admissions=_RUST_BENCHMARK_ADMISSIONS,
    ).plan(profiles, value_tests)


def rust_backend_artifacts(
    profiles: tuple[EmittedProfile, ...],
    value_tests: ValueTestProjectPlan,
    benchmarks: BenchmarkProjectPlan,
    assets: RenderAssets,
    media_type: str,
) -> list[Artifact]:
    """Render Rust from one frozen selection/consumption projection."""

    selection_plan = plan_rust_policy_selection(profiles)
    consumption_plan = plan_rust_policy_consumption_render(
        plan_rust_policy_consumption(benchmarks, selection_plan)
    )
    benchmark_layout_plan = plan_rust_benchmark_layout(
        tuple(profile.profile.name for profile in profiles)
    )
    return [
        *rust_artifacts(
            profiles,
            assets,
            media_type=media_type,
            selection_plan=selection_plan,
            consumption_plan=consumption_plan,
            benchmark_layout_plan=benchmark_layout_plan,
        ),
        *rust_test_artifacts(value_tests, assets, media_type=media_type),
        *rust_benchmark_artifacts(
            benchmarks,
            assets,
            media_type,
            consumption_plan=consumption_plan,
            layout_plan=benchmark_layout_plan,
        ),
    ]


def rust_documentation_formatter() -> BackendDocumentationFormatter:
    return RUST_DOCUMENTATION_FORMATTER


def create_rust_verify_driver() -> VerifyBackendDriver:
    return _create_rust_verify_driver()


def rust_primitive_preview(
    profile: EmittedProfile,
    primitive_name: str,
    specializations: tuple[LoweredSpecialization, ...],
) -> str:
    family = profile.profile_family
    policy_selection = plan_rust_policy_selection((profile,)).profile(
        profile.profile.name
    )
    if policy_selection is None:
        raise ValueError("Rust primitive preview requires a policy-selection profile")
    return RustBackend(
        feature_spellings=profile.profile.feature_spellings("rust"),
        emit_target_features=(
            family.backend("rust").feature_flags if family is not None else True
        ),
        policy_selection=policy_selection,
    ).render_primitive(primitive_name, specializations)


RUST_BACKEND = BackendCapability(
    backend_id="rust",
    root_path="rust",
    artifact_media_type="text/rust",
    dialect_factory=create_rust_dialect,
    artifact_renderer=rust_backend_artifacts,
    verify_profiles=rust_profile_verification,
    value_test_support_factory=rust_value_test_support,
    verify_driver_factory=create_rust_verify_driver,
    verify_machine_profile=rust_verify_profile,
    toolchain_commands=rust_toolchain_commands,
    documentation_formatter_factory=rust_documentation_formatter,
    benchmark_plan_builder=rust_benchmark_plan,
    helper_manifest=RUST_HELPER_MANIFEST,
    profile_validator=validate_rust_profiles,
    primitive_preview_renderer=rust_primitive_preview,
    generated_format=GeneratedFormatSpec(
        executable="rustfmt",
        label="rust",
        patterns=("rust/**/*.rs",),
        args=("--edition", "2021"),
    ),
    generated_documentation=GeneratedDocumentationSpec(
        builder=GeneratedDocumentationBuilder.RUSTDOC,
        project_path="rust",
        output_path="rust/docs/target/doc",
        site_input=DocumentationSiteInput.RUSTDOC,
        args=("--no-default-features",),
    ),
)


__all__ = [
    "RUST_BACKEND",
    "create_rust_dialect",
    "create_rust_verify_driver",
    "rust_profile_verification",
    "rust_benchmark_plan",
    "rust_documentation_formatter",
    "rust_value_test_artifacts",
    "rust_value_test_support",
]
