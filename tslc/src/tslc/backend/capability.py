"""Typed generated-backend capability contract."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass, field, replace
from enum import Enum
from types import MappingProxyType
from typing import TYPE_CHECKING, Generic, Protocol, TypeVar

from tslc.backend.helper_requirements import (
    BackendHelperManifest,
    EMPTY_HELPER_MANIFEST,
)
from tslc.output.verify_model import VerifyBackend, VerifyCompileFailure
from tslc.project_render import DEFAULT_PROJECT_RENDER_CONFIG, ProjectRenderConfig
from tslc.value_tests.compile_failure import compile_failure_target_name

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
    [
        "Catalog",
        tuple["EmittedProfile", ...],
        "ValueTestProjectPlan",
        "BackendPolicyInputs",
    ],
    "BenchmarkProjectPlan",
]
ClosureSeedProjector = Callable[["Catalog"], tuple[str, ...]]
BackendArtifactRenderer = Callable[
    [
        tuple["EmittedProfile", ...],
        "ValueTestProjectPlan",
        "BenchmarkProjectPlan",
        "RenderAssets",
        str,
        "ProjectRenderConfig",
        "BackendPolicyInputs",
    ],
    list["Artifact"],
]
DocumentationFormatterFactory = Callable[[], "BackendDocumentationFormatter"]
ValueTestSupportFactory = Callable[[], "ValueTestBackendSupport"]
VerifyDriverFactory = Callable[[], "VerifyBackendDriver"]
ProfileValidator = Callable[[tuple["EmittedProfile", ...]], tuple["Diagnostic", ...]]
PrimitivePreviewRenderer = Callable[
    [
        "EmittedProfile",
        str,
        tuple["LoweredSpecialization", ...],
        "BackendPolicyInputs",
    ],
    str,
]


class BackendPolicyInput:
    """Marker base for one backend-owned, parsed compiler input."""

    __slots__ = ()


_BackendPolicyT = TypeVar("_BackendPolicyT", bound=BackendPolicyInput)


@dataclass(frozen=True, slots=True)
class BackendPolicyInputs:
    """Frozen backend-policy inputs loaded before planning or rendering."""

    values: Mapping[str, BackendPolicyInput] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "values",
            MappingProxyType(dict(sorted(self.values.items()))),
        )

    def require(
        self,
        backend_id: str,
        expected_type: type[_BackendPolicyT],
    ) -> _BackendPolicyT:
        value = self.values.get(backend_id)
        if not isinstance(value, expected_type):
            raise ValueError(
                f"backend {backend_id!r} requires a loaded "
                f"{expected_type.__name__} policy input"
            )
        return value


EMPTY_BACKEND_POLICY_INPUTS = BackendPolicyInputs()


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


def _no_additional_closure_seeds(catalog: Catalog) -> tuple[str, ...]:
    del catalog
    return ()


def _unsupported_primitive_preview(
    profile: EmittedProfile,
    primitive_name: str,
    specializations: tuple[LoweredSpecialization, ...],
    policy_inputs: BackendPolicyInputs,
) -> str:
    del profile, primitive_name, specializations, policy_inputs
    raise ValueError("this backend does not support specialization preview")


@dataclass(frozen=True, slots=True)
class CompilerCapability:
    """One backend-owned compiler fact used by source semantic requirements."""

    capability_id: str
    header_group: str | None = field(default=None, kw_only=True)
    compiler_ids: tuple[str, ...] = field(default=(), kw_only=True)

    def __post_init__(self) -> None:
        object.__setattr__(self, "compiler_ids", tuple(self.compiler_ids))


_CompilerCapabilityT = TypeVar(
    "_CompilerCapabilityT", bound=CompilerCapability, covariant=True
)


class CompilerCapabilityRegistry(Generic[_CompilerCapabilityT]):
    """One immutable owner for a backend's compiler-capability vocabulary."""

    __slots__ = ("_capabilities", "_by_id")

    def __init__(self, capabilities: Iterable[_CompilerCapabilityT] = ()) -> None:
        ordered = tuple(capabilities)
        by_id: dict[str, _CompilerCapabilityT] = {}
        duplicates: set[str] = set()
        for capability in ordered:
            if capability.capability_id in by_id:
                duplicates.add(capability.capability_id)
            by_id[capability.capability_id] = capability
        if duplicates:
            raise ValueError(
                "duplicate compiler capability IDs: "
                + ", ".join(sorted(duplicates))
            )
        self._capabilities = ordered
        self._by_id = MappingProxyType(by_id)

    def __iter__(self) -> Iterator[_CompilerCapabilityT]:
        return iter(self._capabilities)

    def __len__(self) -> int:
        return len(self._capabilities)

    @property
    def capability_ids(self) -> frozenset[str]:
        return frozenset(self._by_id)

    def get(self, capability_id: str) -> _CompilerCapabilityT | None:
        return self._by_id.get(capability_id)

    def require(self, capability_id: str) -> _CompilerCapabilityT:
        return self._by_id[capability_id]

    def known(
        self, capability_ids: Iterable[str]
    ) -> tuple[_CompilerCapabilityT, ...]:
        return tuple(
            capability
            for capability_id in capability_ids
            if (capability := self.get(capability_id)) is not None
        )

    def require_all(
        self, capability_ids: Iterable[str]
    ) -> tuple[_CompilerCapabilityT, ...]:
        return tuple(self.require(capability_id) for capability_id in capability_ids)

    def header_groups(self, capability_ids: Iterable[str]) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    capability.header_group
                    for capability in self.known(capability_ids)
                    if capability.header_group is not None
                }
            )
        )

    def compiler_ids(self, capability_ids: Iterable[str]) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    compiler_id
                    for capability in self.known(capability_ids)
                    for compiler_id in capability.compiler_ids
                }
            )
        )


EMPTY_COMPILER_CAPABILITY_REGISTRY: CompilerCapabilityRegistry[
    CompilerCapability
] = CompilerCapabilityRegistry()


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
    policy_input_loader: Callable[[], BackendPolicyInput] | None = None
    helper_manifest: BackendHelperManifest = EMPTY_HELPER_MANIFEST
    additional_closure_seeds: ClosureSeedProjector = _no_additional_closure_seeds
    profile_validator: ProfileValidator = _no_profile_diagnostics
    primitive_preview_renderer: PrimitivePreviewRenderer = (
        _unsupported_primitive_preview
    )
    generated_format: GeneratedFormatSpec | None = None
    generated_documentation: GeneratedDocumentationSpec | None = None
    compiler_capabilities: CompilerCapabilityRegistry[CompilerCapability] = (
        EMPTY_COMPILER_CAPABILITY_REGISTRY
    )

    def load_policy_input(self) -> BackendPolicyInput | None:
        if self.policy_input_loader is None:
            return None
        return self.policy_input_loader()

    def compiler_capability(self, capability_id: str) -> CompilerCapability | None:
        return self.compiler_capabilities.get(capability_id)

    def extension_compiler_capabilities(
        self, extension: Extension | None
    ) -> tuple[CompilerCapability, ...]:
        if extension is None:
            return ()
        metadata = extension.metadata.backend.get(self.backend_id)
        if metadata is None:
            return ()
        return self.compiler_capabilities.known(metadata.compiler_capabilities)

    def extension_header_groups(self, extension: Extension | None) -> tuple[str, ...]:
        if extension is None:
            return ()
        metadata = extension.metadata.backend.get(self.backend_id)
        if metadata is None:
            return ()
        return self.compiler_capabilities.header_groups(
            metadata.compiler_capabilities
        )

    def extension_header_group(self, extension: Extension | None) -> str | None:
        groups = self.extension_header_groups(extension)
        return groups[0] if len(groups) == 1 else None

    def extension_compiler_ids(self, extension: Extension | None) -> tuple[str, ...]:
        if extension is None:
            return ()
        metadata = extension.metadata.backend.get(self.backend_id)
        if metadata is None:
            return ()
        return self.compiler_capabilities.compiler_ids(
            metadata.compiler_capabilities
        )

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
        config: ProjectRenderConfig = DEFAULT_PROJECT_RENDER_CONFIG,
        policy_inputs: BackendPolicyInputs = EMPTY_BACKEND_POLICY_INPUTS,
    ) -> list[Artifact]:
        """Render the backend's complete artifact set from one fact snapshot."""

        return self.artifact_renderer(
            profiles,
            value_tests,
            benchmarks,
            assets,
            self.artifact_media_type,
            config,
            policy_inputs,
        )

    def plan_benchmarks(
        self,
        catalog: Catalog,
        profiles: tuple[EmittedProfile, ...],
        value_tests: ValueTestProjectPlan,
        policy_inputs: BackendPolicyInputs = EMPTY_BACKEND_POLICY_INPUTS,
    ) -> BenchmarkProjectPlan | None:
        if self.benchmark_plan_builder is None:
            return None
        return self.benchmark_plan_builder(
            catalog, profiles, value_tests, policy_inputs
        )

    def documentation_formatter(self) -> BackendDocumentationFormatter:
        return self.documentation_formatter_factory()

    def specializations(
        self, profile: EmittedProfile
    ) -> Mapping[str, tuple[LoweredSpecialization, ...]]:
        return profile.specializations(self.backend_id)

    def verify_backend(
        self,
        profiles: tuple[EmittedProfile, ...],
        value_tests: ValueTestProjectPlan,
    ) -> VerifyBackend:
        test_profiles = {
            profile.profile_name: profile
            for profile in value_tests.profiles_for(self.backend_id)
        }
        projected_profiles = self.verify_profiles(profiles)
        source_names = {
            projected.profile_name: emitted.profile.name
            for emitted in profiles
            if (
                projected := self.verify_machine_profile(
                    emitted.profile, emitted.profile_family
                )
            )
            is not None
        }
        verify_profiles = []
        for profile in projected_profiles:
            test_profile = test_profiles.get(
                source_names.get(profile.profile_name, profile.profile_name)
            )
            failures = (
                tuple(
                    VerifyCompileFailure(
                        target_name=compile_failure_target_name(test_profile, case),
                        marker=case.failure.marker,
                    )
                    for case in test_profile.compile_failure_cases
                    if case.failure is not None
                )
                if test_profile is not None
                else ()
            )
            verify_profiles.append(replace(profile, compile_failures=failures))
        return VerifyBackend(
            backend_id=self.backend_id,
            root_path=self.root_path,
            profiles=tuple(verify_profiles),
        )

    def verify_driver(self) -> VerifyBackendDriver:
        return self.verify_driver_factory()

    def closure_seed_primitives(self, catalog: Catalog) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                (
                    *self.helper_manifest.closure_seed_primitives(catalog),
                    *self.additional_closure_seeds(catalog),
                )
            )
        )

    def validate_profiles(
        self, profiles: tuple[EmittedProfile, ...]
    ) -> tuple[Diagnostic, ...]:
        return self.profile_validator(profiles)

    def render_primitive_preview(
        self,
        profile: EmittedProfile,
        primitive_name: str,
        specializations: tuple[LoweredSpecialization, ...],
        policy_inputs: BackendPolicyInputs = EMPTY_BACKEND_POLICY_INPUTS,
    ) -> str:
        return self.primitive_preview_renderer(
            profile, primitive_name, specializations, policy_inputs
        )


__all__ = [
    "BackendArtifactRenderer",
    "BackendCapability",
    "BackendDocumentationFormatter",
    "BackendPolicyInput",
    "BackendPolicyInputs",
    "EMPTY_BACKEND_POLICY_INPUTS",
    "DocumentationSiteInput",
    "DocumentationSpec",
    "GeneratedDocumentationBuilder",
    "GeneratedDocumentationSpec",
    "GeneratedFormatSpec",
]
