"""Assemble generated backend project trees."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.backend.emitted_profile import EmittedProfile
from tslc.backend.registry import backend_capabilities, registered_backend_ids
from tslc.benchmark.model import BenchmarkProjectPlan, EMPTY_BENCHMARK_PROJECT_PLAN
from tslc.compiler_assets import RenderAssets
from tslc.output.artifacts import Artifact, ArtifactSet
from tslc.output.verify_model import VerifyBackend, VerifyProject
from tslc.render.documentation_project import documentation_artifacts
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
    backends: tuple[str, ...] = registered_backend_ids(),
    value_tests: ValueTestProjectPlan = _EMPTY_VALUE_TEST_PLAN,
    benchmarks: BenchmarkProjectPlan = EMPTY_BENCHMARK_PROJECT_PLAN,
    *,
    assets: RenderAssets,
) -> RenderedProject:
    ordered = tuple(sorted(profiles, key=lambda profile: profile.profile.name))
    artifacts: list[Artifact] = []
    verify_backends: list[VerifyBackend] = []

    for driver in backend_capabilities(backends):
        artifacts.extend(driver.render_project_artifacts(ordered, assets))
        artifacts.extend(driver.render_test_artifacts(value_tests, assets))
        artifacts.extend(driver.render_benchmark_artifacts(benchmarks, assets))
        verify_backends.append(driver.verify_backend(ordered))
    artifacts.extend(documentation_artifacts(ordered))
    return RenderedProject(
        artifacts=ArtifactSet.create(tuple(artifacts)),
        verify=VerifyProject(backends=tuple(verify_backends)),
        value_tests=value_tests,
        benchmarks=benchmarks,
    )


__all__ = ["RenderedProject", "render_project"]
