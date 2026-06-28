"""Static render drivers for generated backend projects."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from tslc.output.artifacts import Artifact
from tslc.output.verify import VerifyBackend, VerifyProfile
from tslc.render.cpp_project import cpp_artifacts, cpp_verify_profiles
from tslc.render.rust_project import rust_artifacts, rust_verify_profiles
from tslc.render.tests_project import cpp_test_artifacts, rust_test_artifacts
from tslc.value_tests.model import ValueTestBackendSupport, ValueTestProjectPlan
from tslc.value_tests.render_cpp import CPP_VALUE_TEST_SUPPORT
from tslc.value_tests.render_rust import RUST_VALUE_TEST_SUPPORT

if TYPE_CHECKING:
    from tslc.lower.lowerer import LoweredSpecialization
    from tslc.render.project import ProfileRender

ProjectArtifactRenderer = Callable[[tuple["ProfileRender", ...]], list[Artifact]]
VerifyProfileRenderer = Callable[[tuple["ProfileRender", ...]], tuple[VerifyProfile, ...]]
TestArtifactRenderer = Callable[[ValueTestProjectPlan], list[Artifact]]
SpecializationGetter = Callable[
    ["ProfileRender"], Mapping[str, tuple["LoweredSpecialization", ...]]
]


@dataclass(frozen=True, slots=True)
class RenderBackendDriver:
    backend_id: str
    root_path: str
    project_artifacts: ProjectArtifactRenderer
    verify_profiles: VerifyProfileRenderer
    value_test_support: ValueTestBackendSupport
    test_artifacts: TestArtifactRenderer
    specializations: SpecializationGetter

    def verify_backend(self, profiles: tuple[ProfileRender, ...]) -> VerifyBackend:
        return VerifyBackend(
            backend_id=self.backend_id,
            root_path=self.root_path,
            profiles=self.verify_profiles(profiles),
        )


RENDER_BACKENDS: tuple[RenderBackendDriver, ...] = (
    RenderBackendDriver(
        backend_id="cpp",
        root_path="cpp",
        project_artifacts=cpp_artifacts,
        verify_profiles=cpp_verify_profiles,
        value_test_support=CPP_VALUE_TEST_SUPPORT,
        test_artifacts=cpp_test_artifacts,
        specializations=lambda profile: profile.cpp,
    ),
    RenderBackendDriver(
        backend_id="rust",
        root_path="rust",
        project_artifacts=rust_artifacts,
        verify_profiles=rust_verify_profiles,
        value_test_support=RUST_VALUE_TEST_SUPPORT,
        test_artifacts=rust_test_artifacts,
        specializations=lambda profile: profile.rust,
    ),
)

_BY_ID = {driver.backend_id: driver for driver in RENDER_BACKENDS}


def render_backend_drivers(backend_ids: tuple[str, ...]) -> tuple[RenderBackendDriver, ...]:
    requested = set(backend_ids)
    return tuple(driver for driver in RENDER_BACKENDS if driver.backend_id in requested)


def value_test_supports(backend_ids: tuple[str, ...]) -> tuple[ValueTestBackendSupport, ...]:
    return tuple(driver.value_test_support for driver in render_backend_drivers(backend_ids))


__all__ = [
    "RENDER_BACKENDS",
    "RenderBackendDriver",
    "render_backend_drivers",
    "value_test_supports",
]
