"""Rust generated-backend capability registration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tslc.backend.capability import BackendCapability
from tslc.catalog.model import Catalog

if TYPE_CHECKING:
    from tslc.backend.rust_translation import RustBackendDialect
    from tslc.compiler_assets import RenderAssets
    from tslc.output.artifacts import Artifact
    from tslc.output.verify_drivers import VerifyBackendDriver
    from tslc.output.verify_model import VerifyProfile
    from tslc.render.project import ProfileRender
    from tslc.value_tests.model import ValueTestBackendSupport, ValueTestProjectPlan


def create_rust_dialect(catalog: Catalog) -> RustBackendDialect:
    from tslc.backend.rust_translation import RustBackendDialect

    return RustBackendDialect(catalog)


def rust_project_artifacts(
    profiles: tuple[ProfileRender, ...], assets: RenderAssets
) -> list[Artifact]:
    from tslc.render.rust_project import rust_artifacts

    return rust_artifacts(profiles, assets)


def rust_profile_verification(
    profiles: tuple[ProfileRender, ...],
) -> tuple[VerifyProfile, ...]:
    from tslc.render.rust_project import rust_verify_profiles

    return rust_verify_profiles(profiles)


def rust_value_test_support() -> ValueTestBackendSupport:
    from tslc.value_tests.render_rust import RUST_VALUE_TEST_SUPPORT

    return RUST_VALUE_TEST_SUPPORT


def rust_value_test_artifacts(
    plan: ValueTestProjectPlan, assets: RenderAssets
) -> list[Artifact]:
    from tslc.render.tests_project import rust_test_artifacts

    return rust_test_artifacts(plan, assets)


def create_rust_verify_driver() -> VerifyBackendDriver:
    from tslc.output.verify_drivers import rust_verify_driver

    return rust_verify_driver()


_RUST_ALGORITHM_SUPPORT_PRIMITIVES = (
    "load",
    "store",
    "set_zero",
    "to_array",
    "from_array",
    "gather_narrow",
    "compress_store",
    "mask_population_count",
    "to_integral",
    "to_mask",
)


def rust_closure_seed_primitives(catalog: Catalog) -> tuple[str, ...]:
    return tuple(
        primitive
        for primitive in _RUST_ALGORITHM_SUPPORT_PRIMITIVES
        if catalog.primitives_named(primitive, unmasked=False)
    )


RUST_BACKEND = BackendCapability(
    backend_id="rust",
    root_path="rust",
    dialect_factory=create_rust_dialect,
    project_artifacts=rust_project_artifacts,
    verify_profiles=rust_profile_verification,
    value_test_support_factory=rust_value_test_support,
    test_artifacts=rust_value_test_artifacts,
    verify_driver_factory=create_rust_verify_driver,
    closure_seed_primitives_factory=rust_closure_seed_primitives,
)


__all__ = [
    "RUST_BACKEND",
    "create_rust_dialect",
    "create_rust_verify_driver",
    "rust_closure_seed_primitives",
    "rust_profile_verification",
    "rust_project_artifacts",
    "rust_value_test_artifacts",
    "rust_value_test_support",
]
