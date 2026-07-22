"""Typed generated-backend capability contract."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Protocol

from tslc.backend.helper_requirements import (
    BackendHelperManifest,
    EMPTY_HELPER_MANIFEST,
)
from tslc.output.verify_model import VerifyBackend

if TYPE_CHECKING:
    from tslc.backend.emitted_profile import EmittedProfile
    from tslc.benchmark.model import BenchmarkProjectPlan
    from tslc.backend.translation import BackendDialect
    from tslc.catalog.machine_profiles import MachineProfile
    from tslc.catalog.model import Catalog, Extension
    from tslc.catalog.target_families import ProfileFamilyCapability
    from tslc.compiler_assets import RenderAssets
    from tslc.diagnostics import Diagnostic
    from tslc.lower.lowerer import LoweredSpecialization
    from tslc.output.artifacts import Artifact
    from tslc.output.verify_drivers import VerifyBackendDriver
    from tslc.output.verify_model import (
        BuildVerifierConfig,
        ToolchainCommands,
        VerifyProfile,
    )
    from tslc.value_tests.model import ValueTestBackendSupport, ValueTestProjectPlan

DialectFactory = Callable[["Catalog"], "BackendDialect"]
VerifyProfileRenderer = Callable[
    [tuple["EmittedProfile", ...]], tuple["VerifyProfile", ...]
]
VerifyMachineProfileProjector = Callable[
    ["MachineProfile", "ProfileFamilyCapability | None"], "VerifyProfile"
]
ToolchainCommandsResolver = Callable[
    ["VerifyProfile", "BuildVerifierConfig"], "ToolchainCommands"
]
BenchmarkPlanBuilder = Callable[
    ["Catalog", tuple["EmittedProfile", ...], "ValueTestProjectPlan"],
    "BenchmarkProjectPlan",
]
BackendArtifactRenderer = Callable[
    [
        tuple["EmittedProfile", ...],
        "ValueTestProjectPlan",
        "BenchmarkProjectPlan",
        "RenderAssets",
        str,
    ],
    list["Artifact"],
]
DocumentationFormatterFactory = Callable[[], "BackendDocumentationFormatter"]
ValueTestSupportFactory = Callable[[], "ValueTestBackendSupport"]
VerifyDriverFactory = Callable[[], "VerifyBackendDriver"]
ProfileValidator = Callable[[tuple["EmittedProfile", ...]], tuple["Diagnostic", ...]]
PrimitivePreviewRenderer = Callable[
    ["EmittedProfile", str, tuple["LoweredSpecialization", ...]], str
]


@dataclass(frozen=True, slots=True)
class DocumentationSpec:
    spec: LoweredSpecialization
    extension: Extension | None


@dataclass(frozen=True, slots=True)
class GeneratedFormatSpec:
    executable: str
    label: str
    patterns: tuple[str, ...]
    args: tuple[str, ...]


class GeneratedDocumentationBuilder(str, Enum):
    DOXYGEN = "doxygen"
    RUSTDOC = "rustdoc"


class DocumentationSiteInput(str, Enum):
    DOXYGEN_XML = "doxygen_xml"
    RUSTDOC = "rustdoc"


@dataclass(frozen=True, slots=True)
class GeneratedDocumentationSpec:
    builder: GeneratedDocumentationBuilder
    project_path: str
    output_path: str
    site_input: DocumentationSiteInput
    args: tuple[str, ...] = ()


class BackendDocumentationFormatter(Protocol):
    def register_type(self, spec: LoweredSpecialization) -> str: ...
    def facade(self, doc: DocumentationSpec) -> str: ...
    def expression(self, doc: DocumentationSpec) -> str: ...


def _no_profile_diagnostics(
    profiles: tuple[EmittedProfile, ...],
) -> tuple[Diagnostic, ...]:
    del profiles
    return ()


def _unsupported_primitive_preview(
    profile: EmittedProfile,
    primitive_name: str,
    specializations: tuple[LoweredSpecialization, ...],
) -> str:
    del profile, primitive_name, specializations
    raise ValueError("this backend does not support specialization preview")


@dataclass(frozen=True, slots=True)
class BackendCapability:
    backend_id: str
    root_path: str
    artifact_media_type: str
    dialect_factory: DialectFactory
    artifact_renderer: BackendArtifactRenderer
    verify_profiles: VerifyProfileRenderer
    value_test_support_factory: ValueTestSupportFactory
    verify_driver_factory: VerifyDriverFactory
    verify_machine_profile: VerifyMachineProfileProjector
    toolchain_commands: ToolchainCommandsResolver
    documentation_formatter_factory: DocumentationFormatterFactory
    benchmark_plan_builder: BenchmarkPlanBuilder | None = None
    helper_manifest: BackendHelperManifest = EMPTY_HELPER_MANIFEST
    profile_validator: ProfileValidator = _no_profile_diagnostics
    primitive_preview_renderer: PrimitivePreviewRenderer = (
        _unsupported_primitive_preview
    )
    generated_format: GeneratedFormatSpec | None = None
    generated_documentation: GeneratedDocumentationSpec | None = None

    def create_dialect(self, catalog: Catalog) -> BackendDialect:
        return self.dialect_factory(catalog)

    def value_test_support(self) -> ValueTestBackendSupport:
        return self.value_test_support_factory()

    def render_artifacts(
        self,
        profiles: tuple[EmittedProfile, ...],
        value_tests: ValueTestProjectPlan,
        benchmarks: BenchmarkProjectPlan,
        assets: RenderAssets,
    ) -> list[Artifact]:
        """Render the backend's complete artifact set from one fact snapshot."""

        return self.artifact_renderer(
            profiles,
            value_tests,
            benchmarks,
            assets,
            self.artifact_media_type,
        )

    def plan_benchmarks(
        self,
        catalog: Catalog,
        profiles: tuple[EmittedProfile, ...],
        value_tests: ValueTestProjectPlan,
    ) -> BenchmarkProjectPlan | None:
        if self.benchmark_plan_builder is None:
            return None
        return self.benchmark_plan_builder(catalog, profiles, value_tests)

    def documentation_formatter(self) -> BackendDocumentationFormatter:
        return self.documentation_formatter_factory()

    def specializations(
        self, profile: EmittedProfile
    ) -> Mapping[str, tuple[LoweredSpecialization, ...]]:
        return profile.specializations(self.backend_id)

    def verify_backend(self, profiles: tuple[EmittedProfile, ...]) -> VerifyBackend:
        return VerifyBackend(
            backend_id=self.backend_id,
            root_path=self.root_path,
            profiles=self.verify_profiles(profiles),
        )

    def verify_driver(self) -> VerifyBackendDriver:
        return self.verify_driver_factory()

    def closure_seed_primitives(self, catalog: Catalog) -> tuple[str, ...]:
        return self.helper_manifest.closure_seed_primitives(catalog)

    def validate_profiles(
        self, profiles: tuple[EmittedProfile, ...]
    ) -> tuple[Diagnostic, ...]:
        return self.profile_validator(profiles)

    def render_primitive_preview(
        self,
        profile: EmittedProfile,
        primitive_name: str,
        specializations: tuple[LoweredSpecialization, ...],
    ) -> str:
        return self.primitive_preview_renderer(
            profile, primitive_name, specializations
        )


__all__ = [
    "BackendArtifactRenderer",
    "BackendCapability",
    "BackendDocumentationFormatter",
    "DocumentationSiteInput",
    "DocumentationSpec",
    "GeneratedDocumentationBuilder",
    "GeneratedDocumentationSpec",
    "GeneratedFormatSpec",
]
