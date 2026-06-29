"""Typed generated-backend capability contract."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tslc.backend.translation import BackendDialect
    from tslc.catalog.model import Catalog
    from tslc.lower.lowerer import LoweredSpecialization
    from tslc.output.artifacts import Artifact
    from tslc.output.verify_drivers import VerifyBackendDriver
    from tslc.output.verify_model import VerifyBackend, VerifyProfile
    from tslc.render.project import ProfileRender
    from tslc.value_tests.model import ValueTestBackendSupport, ValueTestProjectPlan

DialectFactory = Callable[["Catalog"], "BackendDialect"]
ProjectArtifactRenderer = Callable[[tuple["ProfileRender", ...]], list["Artifact"]]
VerifyProfileRenderer = Callable[
    [tuple["ProfileRender", ...]], tuple["VerifyProfile", ...]
]
TestArtifactRenderer = Callable[["ValueTestProjectPlan"], list["Artifact"]]
ValueTestSupportFactory = Callable[[], "ValueTestBackendSupport"]
VerifyDriverFactory = Callable[[], "VerifyBackendDriver"]


@dataclass(frozen=True, slots=True)
class BackendCapability:
    backend_id: str
    root_path: str
    dialect_factory: DialectFactory
    project_artifacts: ProjectArtifactRenderer
    verify_profiles: VerifyProfileRenderer
    value_test_support_factory: ValueTestSupportFactory
    test_artifacts: TestArtifactRenderer
    verify_driver_factory: VerifyDriverFactory

    def create_dialect(self, catalog: Catalog) -> BackendDialect:
        return self.dialect_factory(catalog)

    def value_test_support(self) -> ValueTestBackendSupport:
        return self.value_test_support_factory()

    def specializations(
        self, profile: ProfileRender
    ) -> Mapping[str, tuple[LoweredSpecialization, ...]]:
        return profile.specializations(self.backend_id)

    def verify_backend(self, profiles: tuple[ProfileRender, ...]) -> VerifyBackend:
        from tslc.output.verify_model import VerifyBackend

        return VerifyBackend(
            backend_id=self.backend_id,
            root_path=self.root_path,
            profiles=self.verify_profiles(profiles),
        )

    def verify_driver(self) -> VerifyBackendDriver:
        return self.verify_driver_factory()


__all__ = ["BackendCapability"]
