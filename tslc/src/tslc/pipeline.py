"""Compiler orchestration: sources -> ... -> generated per-profile project.

Pure up to the optional write/verify steps. For each machine profile, selects the
implementations reachable in that profile (one specialization per reachable
`(extension, type)`), lowers each, groups by primitive, and renders per-profile
headers/modules with a top-level dispatch.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from tslc._pipeline_closure import (
    LoweringTrace,
    LoweringTraceSlot,
    _LoweredSlot,
    _profile_with_required_features,
    _prune_unresolved,
)
from tslc._pipeline_inputs import _PipelineInputs, _load_inputs
from tslc._pipeline_lowering_cache import _LoweringCache
from tslc._pipeline_profile_generation import (
    CoverageEntry,
    ProfileGenerator,
    SkippedEntry,
    _dependency_discovery_requests,
    _lowering_skipped_entry,
    _pruned_reason,
)
from tslc._pipeline_target_support import TargetSupportRecorder
from tslc.backend.emitted_profile import EmittedProfile
from tslc.backend.registry import backend_capabilities
from tslc.benchmark.model import BenchmarkProjectPlan
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.scalar_types import (
    DEFAULT_SCALAR_TYPE_TAGS,
    SCALAR_TYPE_ORDER,
)
from tslc.diagnostics import (
    Diagnostic,
    has_errors,
    sort_diagnostics,
)
from tslc.lower.dependencies import dependency_sort_key
from tslc.lower.lowerer import Lowerer
from tslc.output.artifacts import ArtifactSet
from tslc.pipeline_request import (
    BackendCompilerCapabilitySet,
    BackendProfileScope,
    GenerationMode,
    GenerationRequest,
    backend_profile_scope_diagnostics,
    compiler_capability_diagnostics,
)
from tslc.render.project import RenderedProject, render_project
from tslc.select.selector import Selector
from tslc.target_support import TargetSupportTrace
from tslc.value_tests import (
    ValueTestBackendProfileInput,
    ValueTestPlanner,
    ValueTestProjectPlan,
)

_TYPE_ORDER = SCALAR_TYPE_ORDER


@dataclass(frozen=True, slots=True)
class GenerationResult:
    artifacts: ArtifactSet
    rendered: RenderedProject | None
    diagnostics: tuple[Diagnostic, ...]
    coverage: tuple[CoverageEntry, ...]
    skipped: tuple[SkippedEntry, ...] = ()
    emitted_profiles: tuple[EmittedProfile, ...] = ()
    lowering_trace: LoweringTrace | None = None
    target_support: TargetSupportTrace | None = None


def generate(request: GenerationRequest) -> GenerationResult:
    if request.mode not in ("partial", "strict"):
        return _empty(
            [
                Diagnostic(
                    severity="error",
                    code="TSL-PIPELINE-BAD-GENERATION-MODE",
                    message=f"generation mode must be 'partial' or 'strict', got {request.mode!r}",
                )
            ]
        )

    inputs, diagnostics = _load_inputs(request)
    if inputs is None:
        return _empty(diagnostics)

    return _generate_loaded(request, inputs, diagnostics)


def _generate_loaded(
    request: GenerationRequest,
    inputs: _PipelineInputs,
    diagnostics: list[Diagnostic],
) -> GenerationResult:
    """Run from one already-loaded immutable input snapshot."""

    return _GenerationSession(request, inputs, list(diagnostics)).run()


class _GenerationSession:
    def __init__(
        self,
        request: GenerationRequest,
        inputs: _PipelineInputs,
        diagnostics: list[Diagnostic],
    ) -> None:
        self.request = request
        self.inputs = inputs
        self.selector = Selector()
        self.lowerer = Lowerer()
        self.backends = backend_capabilities(request.backends)
        self.dialects = {
            capability.backend_id: capability.create_dialect(inputs.catalog)
            for capability in self.backends
        }
        self.lowering_cache = _LoweringCache(
            self.lowerer,
            inputs.catalog,
            self.dialects,
        )
        self.type_tags = _sorted_type_tags(request.type_tags)
        self.diagnostics = diagnostics
        self.coverage: list[CoverageEntry] = []
        self.skipped: list[SkippedEntry] = []
        self.emitted_profiles: list[EmittedProfile] = []
        self.lowering_trace_slots: list[LoweringTraceSlot] = []
        self.target_support = TargetSupportRecorder(
            enabled=request.collect_target_support
        )

    def run(self) -> GenerationResult:
        request_diagnostics = (
            *backend_profile_scope_diagnostics(
                self.request,
                self.backends,
                self.inputs.machine_profiles,
                _expand_requested_profiles(
                    self.request.profiles,
                    self.inputs.machine_profiles,
                ),
            ),
            *compiler_capability_diagnostics(self.request, self.backends),
        )
        self.diagnostics.extend(request_diagnostics)
        if has_errors(request_diagnostics):
            return _result_without_artifacts(
                self.diagnostics, self.coverage, self.skipped
            )

        for profile_name in _expand_requested_profiles(
            self.request.profiles,
            self.inputs.machine_profiles,
        ):
            profile = self.inputs.machine_profiles.get(profile_name)
            if profile is None:
                self._record_unknown_profile(profile_name)
                continue
            generated = ProfileGenerator(
                request=self.request,
                inputs=self.inputs,
                selector=self.selector,
                lowering_cache=self.lowering_cache,
                backends=self.backends,
                type_tags=self.type_tags,
                target_support=self.target_support,
                profile_name=profile_name,
                profile=profile,
            ).generate()
            self.diagnostics.extend(generated.diagnostics)
            self.coverage.extend(generated.coverage)
            self.skipped.extend(generated.skipped)
            self.lowering_trace_slots.extend(generated.lowering_trace_slots)
            if generated.emitted_profile is not None:
                self.emitted_profiles.append(generated.emitted_profile)

        emitted_profiles = tuple(
            sorted(self.emitted_profiles, key=lambda item: item.profile.name)
        )
        lowering_trace = (
            LoweringTrace(
                split_names=self.inputs.split_names,
                slots=tuple(sorted(self.lowering_trace_slots, key=_trace_slot_key)),
            )
            if self.request.collect_lowering_trace
            else None
        )
        target_support = self.target_support.trace()
        backend_diagnostics: list[Diagnostic] = []
        for capability in self.backends:
            profiles_for_backend = self._profiles_for_backend(
                emitted_profiles, capability.backend_id
            )
            backend_diagnostics.extend(
                capability.validate_profiles(profiles_for_backend)
            )
            if (
                _request_has_complete_backend_inventory(
                    self.request, capability.backend_id
                )
                and capability.backend_id in self.inputs.policy_inputs.values
            ):
                backend_diagnostics.extend(
                    capability.validate_policy_inventory(
                        profiles_for_backend, self.inputs.policy_inputs
                    )
                )
        self.diagnostics.extend(backend_diagnostics)

        if has_errors(backend_diagnostics):
            return _result_without_artifacts(
                self.diagnostics,
                self.coverage,
                self.skipped,
                emitted_profiles,
                lowering_trace,
                target_support,
            )

        if self.request.mode == "strict" and (
            _has_strict_skips(self.skipped) or has_errors(self.diagnostics)
        ):
            return _result_without_artifacts(
                self.diagnostics,
                self.coverage,
                self.skipped,
                emitted_profiles,
                lowering_trace,
                target_support,
            )

        if not self.request.render_artifacts:
            return _result_without_artifacts(
                self.diagnostics,
                self.coverage,
                self.skipped,
                emitted_profiles,
                lowering_trace,
                target_support,
            )

        value_tests = (
            self._plan_value_tests(emitted_profiles)
            if emitted_profiles
            else ValueTestProjectPlan(profiles=())
        )
        value_test_diagnostics = tuple(
            diagnostic
            for diagnostic in value_tests.diagnostics
            if self.request.value_test_warnings or diagnostic.severity == "error"
        )
        self.diagnostics.extend(value_test_diagnostics)
        benchmarks = BenchmarkProjectPlan.merge(
            tuple(
                plan
                for capability in self.backends
                if (
                    plan := capability.plan_benchmarks(
                        self.inputs.catalog,
                        self._profiles_for_backend(emitted_profiles, capability.backend_id),
                        value_tests,
                        self.inputs.policy_inputs,
                    )
                )
                is not None
            )
        )
        self.diagnostics.extend(benchmarks.diagnostics)
        if has_errors((*value_test_diagnostics, *benchmarks.diagnostics)):
            return _result_without_artifacts(
                self.diagnostics,
                self.coverage,
                self.skipped,
                emitted_profiles,
                lowering_trace,
                target_support,
            )
        if self.inputs.render_assets is None:
            raise AssertionError("render assets were not loaded for generation")
        rendered = (
            render_project(
                emitted_profiles,
                self.request.backends,
                value_tests,
                benchmarks,
                assets=self.inputs.render_assets,
                config=self.request.render_config,
                policy_inputs=self.inputs.policy_inputs,
                input_digest=self.inputs.input_digest,
            )
            if self.emitted_profiles
            else None
        )
        artifacts = rendered.artifacts if rendered is not None else ArtifactSet.create(())
        return _result(
            artifacts,
            rendered,
            self.diagnostics,
            self.coverage,
            self.skipped,
            emitted_profiles,
            lowering_trace,
            target_support,
        )

    def _plan_value_tests(
        self, profiles: tuple[EmittedProfile, ...]
    ) -> ValueTestProjectPlan:
        inputs = tuple(
            ValueTestBackendProfileInput(
                capability.backend_id,
                profile.profile.name,
                capability.specializations(profile),
                (
                    profile.profile_family is None
                    or profile.profile_family.backend(
                        capability.backend_id
                    ).runtime_failure_observable
                ),
            )
            for profile in profiles
            for capability in self.backends
            if profile.supports_backend(capability.backend_id)
        )
        return ValueTestPlanner(
            self.inputs.catalog,
            tuple(capability.value_test_support() for capability in self.backends),
            fuzz=self.request.value_test_fuzz,
        ).plan(inputs)

    @staticmethod
    def _profiles_for_backend(
        profiles: tuple[EmittedProfile, ...], backend_id: str
    ) -> tuple[EmittedProfile, ...]:
        return tuple(
            profile for profile in profiles if profile.supports_backend(backend_id)
        )

    def _record_unknown_profile(self, profile_name: str) -> None:
        self.diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-PIPELINE-UNKNOWN-PROFILE",
                message=f"no machine profile named {profile_name!r}",
            )
        )

def _has_strict_skips(skipped: list[SkippedEntry]) -> bool:
    return any(entry.status == "coverage_gap" for entry in skipped)


def _trace_slot_key(slot: LoweringTraceSlot) -> tuple[object, ...]:
    spec = slot.specialization
    source = spec.source
    return (
        slot.profile,
        slot.backend,
        spec.primitive_name,
        _TYPE_ORDER.get(spec.type_tag, 99),
        spec.type_tag,
        spec.extension_name,
        spec.mask_policy or "",
        spec.param_kinds,
        spec.axis,
        source.path.as_posix() if source is not None else "",
        source.line if source is not None else 0,
        source.column if source is not None else 0,
    )


def _request_has_complete_backend_inventory(
    request: GenerationRequest, backend_id: str
) -> bool:
    return (
        request.primitives is None
        and request.profiles is None
        and request.extensions is None
        and frozenset(request.type_tags) == frozenset(DEFAULT_SCALAR_TYPE_TAGS)
        and all(
            scope.backend_id != backend_id
            for scope in request.backend_profile_scopes
        )
        and all(
            item.backend_id != backend_id
            for item in request.backend_compiler_capabilities
        )
    )


def _sorted_type_tags(type_tags: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(type_tags, key=lambda tag: (_TYPE_ORDER.get(tag, 99), tag)))


def _expand_requested_profiles(
    requested: tuple[str, ...] | None,
    machine_profiles: Mapping[str, MachineProfile],
) -> tuple[str, ...]:
    if requested is None:
        return tuple(sorted(machine_profiles))
    names: set[str] = set()
    for profile_name in requested:
        names.add(profile_name)
    return tuple(sorted(names))


def _slot_result_key(entry: CoverageEntry | SkippedEntry) -> tuple[object, ...]:
    return (
        entry.profile,
        entry.primitive,
        entry.backend,
        entry.extension,
        _TYPE_ORDER.get(entry.type_tag, 99),
        entry.type_tag,
        entry.source_primitive_name,
        entry.result_kind,
        entry.param_kinds,
        entry.mask_policy or "",
        entry.axis,
        entry.variant_names,
    )


def _result_without_artifacts(
    diagnostics: list[Diagnostic],
    coverage: list[CoverageEntry],
    skipped: list[SkippedEntry],
    emitted_profiles: tuple[EmittedProfile, ...] = (),
    lowering_trace: LoweringTrace | None = None,
    target_support: TargetSupportTrace | None = None,
) -> GenerationResult:
    return _result(
        ArtifactSet.create(()),
        None,
        diagnostics,
        coverage,
        skipped,
        emitted_profiles,
        lowering_trace,
        target_support,
    )


def _result(
    artifacts: ArtifactSet,
    rendered: RenderedProject | None,
    diagnostics: list[Diagnostic],
    coverage: list[CoverageEntry],
    skipped: list[SkippedEntry],
    emitted_profiles: tuple[EmittedProfile, ...] = (),
    lowering_trace: LoweringTrace | None = None,
    target_support: TargetSupportTrace | None = None,
) -> GenerationResult:
    return GenerationResult(
        artifacts=artifacts,
        rendered=rendered,
        diagnostics=sort_diagnostics(diagnostics),
        coverage=tuple(sorted(coverage, key=_slot_result_key)),
        skipped=tuple(sorted(skipped, key=_slot_result_key)),
        emitted_profiles=emitted_profiles,
        lowering_trace=lowering_trace,
        target_support=target_support,
    )


def _empty(diagnostics: list[Diagnostic]) -> GenerationResult:
    return _result(ArtifactSet.create(()), None, diagnostics, [], [])
