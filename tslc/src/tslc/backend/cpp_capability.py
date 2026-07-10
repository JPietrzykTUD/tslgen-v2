"""C++ generated-backend capability registration."""

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
from tslc.backend.cpp_translation import CppBackendDialect
from tslc.backend.helper_requirements import CPP_HELPER_MANIFEST
from tslc.backend.cpp_validation import validate_cpp_profiles
from tslc.catalog.model import Catalog
from tslc.output._verify_cpp import (
    create_cpp_verify_driver as _create_cpp_verify_driver,
)
from tslc.render.cpp_build import cpp_verify_profiles
from tslc.render.cpp_project import cpp_artifacts
from tslc.render.documentation_formatters import CPP_DOCUMENTATION_FORMATTER
from tslc.render.tests_project import cpp_test_artifacts
from tslc.value_tests.render_cpp import CPP_VALUE_TEST_SUPPORT

if TYPE_CHECKING:
    from tslc.backend.translation import BackendDialect
    from tslc.backend.emitted_profile import EmittedProfile
    from tslc.compiler_assets import RenderAssets
    from tslc.output.artifacts import Artifact
    from tslc.output.verify_drivers import VerifyBackendDriver
    from tslc.output.verify_model import VerifyProfile
    from tslc.value_tests.model import ValueTestBackendSupport, ValueTestProjectPlan


def create_cpp_dialect(catalog: Catalog) -> BackendDialect:
    return CppBackendDialect(catalog)


def cpp_project_artifacts(
    profiles: tuple[EmittedProfile, ...], assets: RenderAssets, media_type: str
) -> list[Artifact]:
    return cpp_artifacts(profiles, assets, media_type=media_type)


def cpp_profile_verification(
    profiles: tuple[EmittedProfile, ...],
) -> tuple[VerifyProfile, ...]:
    return cpp_verify_profiles(profiles)


def cpp_value_test_support() -> ValueTestBackendSupport:
    return CPP_VALUE_TEST_SUPPORT


def cpp_value_test_artifacts(
    plan: ValueTestProjectPlan, assets: RenderAssets, media_type: str
) -> list[Artifact]:
    return cpp_test_artifacts(plan, assets, media_type=media_type)


def cpp_documentation_formatter() -> BackendDocumentationFormatter:
    return CPP_DOCUMENTATION_FORMATTER


def create_cpp_verify_driver() -> VerifyBackendDriver:
    return _create_cpp_verify_driver()


CPP_BACKEND = BackendCapability(
    backend_id="cpp",
    root_path="cpp",
    artifact_media_type="text/x-c++",
    dialect_factory=create_cpp_dialect,
    project_renderer=cpp_project_artifacts,
    verify_profiles=cpp_profile_verification,
    value_test_support_factory=cpp_value_test_support,
    test_renderer=cpp_value_test_artifacts,
    verify_driver_factory=create_cpp_verify_driver,
    documentation_formatter_factory=cpp_documentation_formatter,
    helper_manifest=CPP_HELPER_MANIFEST,
    profile_validator=validate_cpp_profiles,
    generated_format=GeneratedFormatSpec(
        executable="clang-format",
        label="cpp",
        patterns=("cpp/**/*.hpp", "cpp/**/*.cpp"),
        args=("-i",),
    ),
    generated_documentation=GeneratedDocumentationSpec(
        builder=GeneratedDocumentationBuilder.DOXYGEN,
        project_path="cpp",
        output_path="cpp/docs/doxygen/xml",
        site_input=DocumentationSiteInput.DOXYGEN_XML,
    ),
)


__all__ = [
    "CPP_BACKEND",
    "cpp_profile_verification",
    "cpp_documentation_formatter",
    "cpp_project_artifacts",
    "cpp_value_test_artifacts",
    "cpp_value_test_support",
    "create_cpp_dialect",
    "create_cpp_verify_driver",
]
