"""Rust generated-backend capability registration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tslc.backend.capability import BackendCapability, BackendDocumentationFormatter
from tslc.backend.helper_requirements import RUST_HELPER_MANIFEST
from tslc.backend.rust_translation import RustBackendDialect
from tslc.backend.rust_validation import validate_rust_profiles
from tslc.catalog.model import Catalog
from tslc.output.verify_drivers import rust_verify_driver
from tslc.render.documentation_formatters import RUST_DOCUMENTATION_FORMATTER
from tslc.render.rust_project import rust_artifacts, rust_verify_profiles
from tslc.render.tests_project import rust_test_artifacts
from tslc.value_tests.render_rust import RUST_VALUE_TEST_SUPPORT

if TYPE_CHECKING:
    from tslc.backend.emitted_profile import EmittedProfile
    from tslc.compiler_assets import RenderAssets
    from tslc.output.artifacts import Artifact
    from tslc.output.verify_drivers import VerifyBackendDriver
    from tslc.output.verify_model import VerifyProfile
    from tslc.value_tests.model import ValueTestBackendSupport, ValueTestProjectPlan


def create_rust_dialect(catalog: Catalog) -> RustBackendDialect:
    return RustBackendDialect(catalog)


def rust_project_artifacts(
    profiles: tuple[EmittedProfile, ...], assets: RenderAssets, media_type: str
) -> list[Artifact]:
    return rust_artifacts(profiles, assets, media_type=media_type)


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


def rust_documentation_formatter() -> BackendDocumentationFormatter:
    return RUST_DOCUMENTATION_FORMATTER


def create_rust_verify_driver() -> VerifyBackendDriver:
    return rust_verify_driver()


RUST_BACKEND = BackendCapability(
    backend_id="rust",
    root_path="rust",
    artifact_media_type="text/rust",
    dialect_factory=create_rust_dialect,
    project_renderer=rust_project_artifacts,
    verify_profiles=rust_profile_verification,
    value_test_support_factory=rust_value_test_support,
    test_renderer=rust_value_test_artifacts,
    verify_driver_factory=create_rust_verify_driver,
    documentation_formatter_factory=rust_documentation_formatter,
    helper_manifest=RUST_HELPER_MANIFEST,
    profile_validator=validate_rust_profiles,
)


__all__ = [
    "RUST_BACKEND",
    "create_rust_dialect",
    "create_rust_verify_driver",
    "rust_profile_verification",
    "rust_documentation_formatter",
    "rust_project_artifacts",
    "rust_value_test_artifacts",
    "rust_value_test_support",
]
