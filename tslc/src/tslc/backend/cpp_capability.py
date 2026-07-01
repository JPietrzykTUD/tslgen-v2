"""C++ generated-backend capability registration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tslc.backend.capability import BackendCapability
from tslc.catalog.model import Catalog

if TYPE_CHECKING:
    from tslc.backend.cpp_translation import CppBackendDialect
    from tslc.compiler_assets import RenderAssets
    from tslc.output.artifacts import Artifact
    from tslc.output.verify_drivers import VerifyBackendDriver
    from tslc.output.verify_model import VerifyProfile
    from tslc.render.project import ProfileRender
    from tslc.value_tests.model import ValueTestBackendSupport, ValueTestProjectPlan


def create_cpp_dialect(catalog: Catalog) -> CppBackendDialect:
    from tslc.backend.cpp_translation import CppBackendDialect

    return CppBackendDialect(catalog)


def cpp_project_artifacts(
    profiles: tuple[ProfileRender, ...], assets: RenderAssets
) -> list[Artifact]:
    from tslc.render.cpp_project import cpp_artifacts

    return cpp_artifacts(profiles, assets)


def cpp_profile_verification(
    profiles: tuple[ProfileRender, ...],
) -> tuple[VerifyProfile, ...]:
    from tslc.render.cpp_project import cpp_verify_profiles

    return cpp_verify_profiles(profiles)


def cpp_value_test_support() -> ValueTestBackendSupport:
    from tslc.value_tests.render_cpp import CPP_VALUE_TEST_SUPPORT

    return CPP_VALUE_TEST_SUPPORT


def cpp_value_test_artifacts(
    plan: ValueTestProjectPlan, assets: RenderAssets
) -> list[Artifact]:
    from tslc.render.tests_project import cpp_test_artifacts

    return cpp_test_artifacts(plan, assets)


def create_cpp_verify_driver() -> VerifyBackendDriver:
    from tslc.output.verify_drivers import cpp_verify_driver

    return cpp_verify_driver()


CPP_BACKEND = BackendCapability(
    backend_id="cpp",
    root_path="cpp",
    dialect_factory=create_cpp_dialect,
    project_artifacts=cpp_project_artifacts,
    verify_profiles=cpp_profile_verification,
    value_test_support_factory=cpp_value_test_support,
    test_artifacts=cpp_value_test_artifacts,
    verify_driver_factory=create_cpp_verify_driver,
)


__all__ = [
    "CPP_BACKEND",
    "cpp_profile_verification",
    "cpp_project_artifacts",
    "cpp_value_test_artifacts",
    "cpp_value_test_support",
    "create_cpp_dialect",
    "create_cpp_verify_driver",
]
