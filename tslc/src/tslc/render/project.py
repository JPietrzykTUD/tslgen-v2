"""Assemble generated backend project trees."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.backend.capability import (
    BackendPolicyInputs,
    EMPTY_BACKEND_POLICY_INPUTS,
)
from tslc.backend.emitted_profile import EmittedProfile
from tslc.backend.registry import backend_capabilities
from tslc.benchmark.model import BenchmarkProjectPlan, EMPTY_BENCHMARK_PROJECT_PLAN
from tslc.compiler_assets import RenderAssets
from tslc.output.artifacts import Artifact, ArtifactSet
from tslc.output.verify_model import VerifyBackend, VerifyProject
from tslc.render.documentation_project import documentation_artifacts
from tslc.project_render import DEFAULT_PROJECT_RENDER_CONFIG, ProjectRenderConfig
from tslc.render.licensing import (
    add_generated_license_notice,
    generated_license_artifacts,
)
from tslc.value_tests import ValueTestProjectPlan

_EMPTY_VALUE_TEST_PLAN = ValueTestProjectPlan(profiles=())


@dataclass(frozen=True, slots=True)
class RenderedProject:
    artifacts: ArtifactSet
    verify: VerifyProject
    value_tests: ValueTestProjectPlan = _EMPTY_VALUE_TEST_PLAN
    benchmarks: BenchmarkProjectPlan = EMPTY_BENCHMARK_PROJECT_PLAN


def render_project(
    profiles: tuple[EmittedProfile, ...],
    backends: tuple[str, ...],
    value_tests: ValueTestProjectPlan = _EMPTY_VALUE_TEST_PLAN,
    benchmarks: BenchmarkProjectPlan = EMPTY_BENCHMARK_PROJECT_PLAN,
    *,
    assets: RenderAssets,
    config: ProjectRenderConfig = DEFAULT_PROJECT_RENDER_CONFIG,
    policy_inputs: BackendPolicyInputs = EMPTY_BACKEND_POLICY_INPUTS,
) -> RenderedProject:
    ordered = tuple(sorted(profiles, key=lambda profile: profile.profile.name))
    artifacts: list[Artifact] = []
    verify_backends: list[VerifyBackend] = []

    drivers = backend_capabilities(backends)
    for driver in drivers:
        backend_profiles = tuple(
            profile
            for profile in ordered
            if profile.supports_backend(driver.backend_id)
        )
        artifacts.extend(
            driver.render_artifacts(
                backend_profiles,
                value_tests,
                benchmarks,
                assets,
                config,
                policy_inputs,
            )
        )
        verify_backends.append(driver.verify_backend(backend_profiles, value_tests))
    artifacts.extend(documentation_artifacts(ordered))
    artifacts.extend(generated_license_artifacts(drivers, assets))
    artifacts = [add_generated_license_notice(artifact) for artifact in artifacts]
    return RenderedProject(
        artifacts=ArtifactSet.create(tuple(artifacts)),
        verify=VerifyProject(backends=tuple(verify_backends)),
        value_tests=value_tests,
        benchmarks=benchmarks,
    )


__all__ = ["RenderedProject", "render_project"]
