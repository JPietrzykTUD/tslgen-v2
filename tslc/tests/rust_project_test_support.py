"""Build finalized Rust project-render plans for renderer-focused tests."""

from __future__ import annotations

from tslc.backend.emitted_profile import EmittedProfile
from tslc.backend.rust_api_planner import plan_rust_facade
from tslc.backend.rust_dispatch import plan_rust_dispatch
from tslc.backend.rust_package import (
    DEFAULT_RUST_PACKAGE_CONFIG,
    RustPackageConfig,
)
from tslc.backend.rust_policy_selection import RustPolicySelectionPlan
from tslc.backend.rust_static_selection import RustStaticSelectionPlan
from tslc.compiler_assets import RenderAssets
from tslc.output.artifacts import Artifact
from tslc.render.rust_benchmark_layout import plan_rust_benchmark_layout
from tslc.render.rust_policy_consumption import (
    EMPTY_RUST_POLICY_CONSUMPTION_RENDER_PLAN,
    RustPolicyConsumptionRenderPlan,
)
from tslc.render.rust_project import _rust_artifacts


def render_rust_artifacts_for_test(
    profiles: tuple[EmittedProfile, ...],
    assets: RenderAssets,
    *,
    media_type: str,
    selection_plan: RustPolicySelectionPlan,
    static_selection_plan: RustStaticSelectionPlan,
    consumption_plan: RustPolicyConsumptionRenderPlan = (
        EMPTY_RUST_POLICY_CONSUMPTION_RENDER_PLAN
    ),
    package_config: RustPackageConfig = DEFAULT_RUST_PACKAGE_CONFIG,
) -> list[Artifact]:
    facade_plan = plan_rust_facade(profiles, static_selection_plan)
    dispatch_plan = plan_rust_dispatch(
        profiles,
        static_selection_plan,
        facade_plan,
    )
    benchmark_layout_plan = plan_rust_benchmark_layout(
        tuple(profile.profile.name for profile in profiles)
    )
    return _rust_artifacts(
        profiles,
        assets,
        media_type=media_type,
        selection_plan=selection_plan,
        static_selection_plan=static_selection_plan,
        facade_plan=facade_plan,
        dispatch_plan=dispatch_plan,
        consumption_plan=consumption_plan,
        benchmark_layout_plan=benchmark_layout_plan,
        package_config=package_config,
    )
