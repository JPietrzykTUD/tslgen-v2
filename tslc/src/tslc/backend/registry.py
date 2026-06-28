"""Central registry for generated backend capabilities."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tslc.backend.translation import BackendDialect
    from tslc.catalog.model import Catalog
    from tslc.lower.lowerer import LoweredSpecialization
    from tslc.output.artifacts import Artifact
    from tslc.output.verify import VerifyBackendDriver
    from tslc.output.verify_model import VerifyBackend, VerifyProfile
    from tslc.render.project import ProfileRender
    from tslc.value_tests.model import ValueTestBackendSupport, ValueTestProjectPlan

DialectFactory = Callable[["Catalog"], "BackendDialect"]
ProjectArtifactRenderer = Callable[[tuple["ProfileRender", ...]], list["Artifact"]]
VerifyProfileRenderer = Callable[
    [tuple["ProfileRender", ...]], tuple["VerifyProfile", ...]
]
TestArtifactRenderer = Callable[["ValueTestProjectPlan"], list["Artifact"]]
RendererLoader = Callable[[], ProjectArtifactRenderer]
VerifyProfileLoader = Callable[[], VerifyProfileRenderer]
ValueTestSupportLoader = Callable[[], "ValueTestBackendSupport"]
TestArtifactLoader = Callable[[], TestArtifactRenderer]
VerifyDriverLoader = Callable[[], "VerifyBackendDriver"]


@dataclass(frozen=True, slots=True)
class BackendCapability:
    backend_id: str
    root_path: str
    _dialect_factory: DialectFactory
    _project_artifacts: RendererLoader
    _verify_profiles: VerifyProfileLoader
    _value_test_support: ValueTestSupportLoader
    _test_artifacts: TestArtifactLoader
    _verify_driver: VerifyDriverLoader

    def create_dialect(self, catalog: Catalog) -> BackendDialect:
        return self._dialect_factory(catalog)

    def project_artifacts(self, profiles: tuple[ProfileRender, ...]) -> list[Artifact]:
        return self._project_artifacts()(profiles)

    def verify_profiles(
        self, profiles: tuple[ProfileRender, ...]
    ) -> tuple[VerifyProfile, ...]:
        return self._verify_profiles()(profiles)

    def value_test_support(self) -> ValueTestBackendSupport:
        return self._value_test_support()

    def test_artifacts(self, plan: ValueTestProjectPlan) -> list[Artifact]:
        return self._test_artifacts()(plan)

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
        return self._verify_driver()


def _create_cpp(catalog: Catalog) -> BackendDialect:
    from tslc.backend.cpp_translation import CppBackendDialect

    return CppBackendDialect(catalog)


def _create_rust(catalog: Catalog) -> BackendDialect:
    from tslc.backend.rust_translation import RustBackendDialect

    return RustBackendDialect(catalog)


def _cpp_project_artifacts() -> ProjectArtifactRenderer:
    from tslc.render.cpp_project import cpp_artifacts

    return cpp_artifacts


def _rust_project_artifacts() -> ProjectArtifactRenderer:
    from tslc.render.rust_project import rust_artifacts

    return rust_artifacts


def _cpp_verify_profiles() -> VerifyProfileRenderer:
    from tslc.render.cpp_project import cpp_verify_profiles

    return cpp_verify_profiles


def _rust_verify_profiles() -> VerifyProfileRenderer:
    from tslc.render.rust_project import rust_verify_profiles

    return rust_verify_profiles


def _cpp_value_test_support() -> ValueTestBackendSupport:
    from tslc.value_tests.render_cpp import CPP_VALUE_TEST_SUPPORT

    return CPP_VALUE_TEST_SUPPORT


def _rust_value_test_support() -> ValueTestBackendSupport:
    from tslc.value_tests.render_rust import RUST_VALUE_TEST_SUPPORT

    return RUST_VALUE_TEST_SUPPORT


def _cpp_test_artifacts() -> TestArtifactRenderer:
    from tslc.render.tests_project import cpp_test_artifacts

    return cpp_test_artifacts


def _rust_test_artifacts() -> TestArtifactRenderer:
    from tslc.render.tests_project import rust_test_artifacts

    return rust_test_artifacts


def _cpp_verify_driver() -> VerifyBackendDriver:
    from tslc.output.verify import (
        VerifyBackendDriver,
        _after_noop_command,
        _cpp_command_groups,
        _prepare_cpp_backend,
    )

    return VerifyBackendDriver(
        backend_id="cpp",
        required_tools=("cmake",),
        prepare_backend=_prepare_cpp_backend,
        command_groups=lambda root, backend, config: _cpp_command_groups(
            root, backend, config
        ),
        after_successful_command=_after_noop_command,
    )


def _rust_verify_driver() -> VerifyBackendDriver:
    from tslc.output.verify import (
        VerifyBackendDriver,
        _after_rust_command,
        _prepare_rust_backend,
        _rust_command_groups,
    )

    return VerifyBackendDriver(
        backend_id="rust",
        required_tools=("cargo",),
        prepare_backend=_prepare_rust_backend,
        command_groups=lambda root, backend, config: _rust_command_groups(
            root, backend, config
        ),
        after_successful_command=_after_rust_command,
    )


BACKEND_CAPABILITIES: tuple[BackendCapability, ...] = (
    BackendCapability(
        backend_id="cpp",
        root_path="cpp",
        _dialect_factory=_create_cpp,
        _project_artifacts=_cpp_project_artifacts,
        _verify_profiles=_cpp_verify_profiles,
        _value_test_support=_cpp_value_test_support,
        _test_artifacts=_cpp_test_artifacts,
        _verify_driver=_cpp_verify_driver,
    ),
    BackendCapability(
        backend_id="rust",
        root_path="rust",
        _dialect_factory=_create_rust,
        _project_artifacts=_rust_project_artifacts,
        _verify_profiles=_rust_verify_profiles,
        _value_test_support=_rust_value_test_support,
        _test_artifacts=_rust_test_artifacts,
        _verify_driver=_rust_verify_driver,
    ),
)

_BY_ID = {capability.backend_id: capability for capability in BACKEND_CAPABILITIES}


def backend_capability(backend_id: str) -> BackendCapability:
    capability = _BY_ID.get(backend_id)
    if capability is None:
        raise ValueError(f"unsupported backend {backend_id!r}")
    return capability


def backend_capabilities(backend_ids: tuple[str, ...]) -> tuple[BackendCapability, ...]:
    requested = set(backend_ids)
    unknown = requested - set(_BY_ID)
    if unknown:
        names = ", ".join(repr(name) for name in sorted(unknown))
        raise ValueError(f"unsupported backend {names}")
    return tuple(
        capability
        for capability in BACKEND_CAPABILITIES
        if capability.backend_id in requested
    )


def registered_backend_ids() -> tuple[str, ...]:
    return tuple(sorted(_BY_ID))


def supports_backend(backend_id: str) -> bool:
    return backend_id in _BY_ID


def create_backend_dialect(catalog: Catalog, backend_id: str) -> BackendDialect:
    return backend_capability(backend_id).create_dialect(catalog)


__all__ = [
    "BACKEND_CAPABILITIES",
    "BackendCapability",
    "backend_capabilities",
    "backend_capability",
    "create_backend_dialect",
    "registered_backend_ids",
    "supports_backend",
]
