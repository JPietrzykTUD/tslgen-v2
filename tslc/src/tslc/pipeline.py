"""Compiler orchestration: sources -> ... -> generated per-profile project.

Pure up to the optional write/verify steps. For each machine profile, selects the
implementations reachable in that profile (one specialization per reachable
`(extension, type)`), lowers each, groups by primitive, and renders per-profile
headers/modules with a top-level dispatch.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from tslc._pipeline_closure import (
    LoweringTrace,
    LoweringTraceSlot,
    _LoweredSlot,
    _profile_with_required_features,
    _prune_unresolved,
    unresolved_callee_reason,
)
from tslc._pipeline_inputs import _PipelineInputs, _load_inputs
from tslc._pipeline_lowering_cache import _LoweringCache
from tslc.backend.emitted_profile import EmittedProfile
from tslc.backend.registry import backend_capabilities, registered_backend_ids
from tslc.benchmark.model import EMPTY_BENCHMARK_PROJECT_PLAN
from tslc.benchmark.model import BenchmarkProjectPlan
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import (
    BOOLEAN_WILDCARD_ATTRIBUTES,
    RESULT_DIM_EXTENSION,
    Catalog,
    Extension,
)
from tslc.catalog.scalar_types import SCALAR_TYPE_ORDER
from tslc.catalog.signatures import parse_signature
from tslc.diagnostics import Diagnostic, SourceLocation, has_errors, sort_diagnostics
from tslc.ir.scan import scan
from tslc.lower.dependencies import dependency_sort_key
from tslc.lower.lowerer import LoweredSpecialization, Lowerer, LoweringResult
from tslc.output.artifacts import ArtifactSet
from tslc.render.project import RenderedProject, render_project
from tslc.select.selector import (
    SelectedImplementation,
    Selector,
)
from tslc.value_tests import (
    ValueTestBackendProfileInput,
    ValueTestPlanner,
    ValueTestProjectPlan,
)

_DEFAULT_BACKENDS = registered_backend_ids()
GenerationMode = Literal["partial", "strict"]
SkipStatus = Literal["coverage_gap", "policy_deferred"]
_TYPE_ORDER = SCALAR_TYPE_ORDER


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    source_paths: tuple[Path, ...]
    machine_profiles_path: Path
    primitives: tuple[str, ...] | None
    profiles: tuple[str, ...] | None
    type_tags: tuple[str, ...]
    extensions: tuple[str, ...] | None = None
    backends: tuple[str, ...] = _DEFAULT_BACKENDS
    mode: GenerationMode = "partial"
    # Pull the value-test harness primitives (vector<->array round-trip and mask normalization)
    # into the dependency closure so the generated differential tests can build a hardware
    # register from a lane array and read its result back. Off for ordinary generation.
    test_harness: bool = False
    # Report authored value-test cases that could not be planned for a backend/profile. Off for
    # ordinary generation because source data often includes broader test intent than the current
    # backend test harness supports.
    value_test_warnings: bool = False
    # Emit differential-fuzz value tests: a runtime PRNG loop comparing each hardware
    # specialization against the generic scalar reference over many random inputs. Opt-in (adds
    # build/run cost); requires the test harness so the generated code can round-trip registers.
    value_test_fuzz: bool = False
    # Authoring checks reuse selection and lowering but stop before test planning,
    # benchmarking, render-asset loading, and artifact rendering.
    render_artifacts: bool = True
    # Explicit concrete-analysis commands may retain the lowered call graph.
    # Ordinary checking/generation discards it after closure and propagation.
    collect_lowering_trace: bool = False


@dataclass(frozen=True, slots=True)
class CoverageEntry:
    profile: str
    backend: str
    primitive: str
    extension: str
    type_tag: str
    source_primitive_name: str = ""
    result_kind: str = ""
    param_kinds: tuple[str, ...] = ()
    mask_policy: str | None = None
    axis: tuple[tuple[str, str], ...] = ()
    variant_names: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SkippedEntry:
    """A selected slot whose body could not be lowered yet (recorded, not failed)."""

    profile: str
    backend: str
    primitive: str
    extension: str
    type_tag: str
    reason: str
    diagnostics: tuple[Diagnostic, ...] = ()
    status: SkipStatus = "coverage_gap"
    source_primitive_name: str = ""
    result_kind: str = ""
    param_kinds: tuple[str, ...] = ()
    mask_policy: str | None = None
    axis: tuple[tuple[str, str], ...] = ()
    variant_names: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GenerationResult:
    artifacts: ArtifactSet
    rendered: RenderedProject | None
    diagnostics: tuple[Diagnostic, ...]
    coverage: tuple[CoverageEntry, ...]
    skipped: tuple[SkippedEntry, ...] = ()
    emitted_profiles: tuple[EmittedProfile, ...] = ()
    lowering_trace: LoweringTrace | None = None


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

    def run(self) -> GenerationResult:
        for profile_name in _expand_requested_profiles(
            self.request.profiles,
            self.inputs.machine_profiles,
        ):
            profile = self.inputs.machine_profiles.get(profile_name)
            if profile is None:
                self._record_unknown_profile(profile_name)
                continue
            self._generate_profile(profile_name, profile)

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
        backend_diagnostics: list[Diagnostic] = []
        for capability in self.backends:
            backend_diagnostics.extend(capability.validate_profiles(emitted_profiles))
        self.diagnostics.extend(backend_diagnostics)

        if has_errors(backend_diagnostics):
            return _result_without_artifacts(
                self.diagnostics,
                self.coverage,
                self.skipped,
                emitted_profiles,
                lowering_trace,
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
            )

        if not self.request.render_artifacts:
            return _result_without_artifacts(
                self.diagnostics,
                self.coverage,
                self.skipped,
                emitted_profiles,
                lowering_trace,
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
        benchmarks = _merge_benchmark_plans(
            tuple(
                plan
                for capability in self.backends
                if (
                    plan := capability.plan_benchmarks(
                        self.inputs.catalog, emitted_profiles, value_tests
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
        )

    def _plan_value_tests(
        self, profiles: tuple[EmittedProfile, ...]
    ) -> ValueTestProjectPlan:
        inputs = tuple(
            ValueTestBackendProfileInput(
                capability.backend_id,
                profile.profile.name,
                capability.specializations(profile),
            )
            for profile in profiles
            for capability in self.backends
        )
        return ValueTestPlanner(
            self.inputs.catalog,
            tuple(capability.value_test_support() for capability in self.backends),
            fuzz=self.request.value_test_fuzz,
        ).plan(inputs)

    def _record_unknown_profile(self, profile_name: str) -> None:
        self.diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-PIPELINE-UNKNOWN-PROFILE",
                message=f"no machine profile named {profile_name!r}",
            )
        )

    def _generate_profile(self, profile_name: str, profile: MachineProfile) -> None:
        # Profile-scoped dependency closure: start from the requested primitives and pull in only
        # callees referenced by bodies actually selected and lowered for this profile.
        lowered_specs: list[_LoweredSlot] = []
        # Which extension block this profile selected for each emitted ISA tag, so the renderer
        # can register the right mask_type (lane-bitmask vs native __mmaskN).
        selected_extensions: dict[str, Extension] = {}
        all_backend_ids = frozenset(capability.backend_id for capability in self.backends)
        worklist = [
            (primitive, self.type_tags, all_backend_ids, self.request.extensions)
            for primitive in _requested_primitives(self.request, self.inputs.catalog)
        ]
        if self.request.test_harness:
            worklist.extend(
                (name, self.type_tags, all_backend_ids, None)
                for name in (
                    self.inputs.test_harness.from_array,
                    self.inputs.test_harness.to_array,
                    self.inputs.test_harness.to_integral,
                    self.inputs.test_harness.load,
                    self.inputs.test_harness.store,
                )
                if name is not None
            )
        if self.request.render_artifacts or self.request.extensions is None:
            for capability in self.backends:
                worklist.extend(
                    (name, self.type_tags, frozenset({capability.backend_id}), None)
                    for name in capability.closure_seed_primitives(self.inputs.catalog)
                )
        processed: dict[tuple[str, str, tuple[str, ...] | None], set[str]] = {}
        while worklist:
            primitive, requested_types, target_backends, extensions = worklist.pop(0)
            scope = tuple(extensions) if extensions is not None else None
            for backend in sorted(target_backends):
                remaining_types = tuple(
                    type_tag
                    for type_tag in requested_types
                    if backend
                    not in processed.get((primitive, type_tag, scope), set())
                )
                if not remaining_types:
                    continue
                primitive_slots, discovered_dependencies = self._process_primitive(
                    profile,
                    profile_name,
                    primitive,
                    remaining_types,
                    selected_extensions,
                    frozenset({backend}),
                    extensions,
                )
                for type_tag in remaining_types:
                    processed.setdefault((primitive, type_tag, scope), set()).add(backend)
                lowered_specs.extend(primitive_slots)
                for (
                    dependency_primitive,
                    dependency_type,
                    dependency_extension,
                    dependency_backend,
                ) in discovered_dependencies:
                    dependency_scope = (
                        (dependency_extension,) if extensions is not None else None
                    )
                    if dependency_backend not in processed.get(
                        (dependency_primitive, dependency_type, dependency_scope), set()
                    ):
                        worklist.append(
                            (
                                dependency_primitive,
                                (dependency_type,),
                                frozenset({dependency_backend}),
                                dependency_scope,
                            )
                        )

        grouped, pruned = _prune_unresolved(lowered_specs, self.inputs.split_names)
        if self.request.collect_lowering_trace:
            pruned_ids = {id(slot) for slot in pruned}
            self.lowering_trace_slots.extend(
                LoweringTraceSlot(
                    profile=profile_name,
                    backend=slot.backend,
                    specialization=slot.spec,
                    callees=tuple(sorted(slot.callees, key=dependency_sort_key)),
                    callee_origins=slot.callee_origins,
                    emitted=id(slot) not in pruned_ids,
                    unresolved_callee=slot.unresolved_callee,
                    selection_required_features=slot.selection_required_features,
                    selector_source=slot.selector_source,
                )
                for slot in lowered_specs
            )
        for slot in pruned:
            self._record_pruned_skip(profile_name, slot)
        self._record_coverage(profile_name, lowered_specs, pruned)
        effective_profile = _profile_with_required_features(profile, grouped)
        self.emitted_profiles.append(
            EmittedProfile(
                profile=effective_profile,
                specializations_by_backend={
                    capability.backend_id: _finalize(
                        grouped.get(capability.backend_id, {})
                    )
                    for capability in self.backends
                },
                extensions=selected_extensions,
                profile_family=self.inputs.catalog.target_families.profile_family(
                    effective_profile.family
                ),
                immediate_split_names=self.inputs.imm_split_names,
            )
        )

    def _process_primitive(
        self,
        profile: MachineProfile,
        profile_name: str,
        primitive: str,
        type_tags: tuple[str, ...],
        selected_extensions: dict[str, Extension],
        backend_ids: frozenset[str],
        extensions: tuple[str, ...] | None,
    ) -> tuple[list["_LoweredSlot"], tuple[tuple[str, str, str, str], ...]]:
        catalog = self.inputs.catalog
        lowered_slots: list[_LoweredSlot] = []
        discovered_dependencies: set[tuple[str, str, str, str]] = set()

        for capability in self.backends:
            backend = capability.backend_id
            if backend not in backend_ids:
                continue
            selection = self.selector.select_profile(
                catalog,
                profile,
                primitive,
                type_tags,
                backend_id=backend,
            )
            self.diagnostics.extend(selection.diagnostics)
            for slot in selection.selected:
                if (
                    extensions is not None
                    and slot.extension.name not in extensions
                    and slot.extension.isa_name not in extensions
                ):
                    continue
                _record_render_extensions(catalog, selected_extensions, slot)
                body_segments = scan(
                    slot.implementation.body_text,
                    source=slot.implementation.body_source,
                )
                lowered = self.lowering_cache.lower(
                    slot,
                    backend,
                    body_segments=body_segments,
                )
                self._record_lowering_diagnostics(
                    profile_name, backend, primitive, slot, lowered
                )
                if lowered.specialization is None:
                    continue
                callee_origins = lowered.specialization.call_dependency_origins
                callees = frozenset(
                    origin.dependency for origin in callee_origins
                )
                lowered_slots.append(
                    _LoweredSlot(
                        backend=backend,
                        spec=lowered.specialization,
                        callees=callees,
                        callee_origins=callee_origins,
                        selection_required_features=slot.required_features,
                        selector_source=slot.implementation.selector_source,
                    )
                )
                discovered_dependencies.update(
                    (
                        dependency.primitive,
                        dependency.source.base_tag,
                        dependency.source.extension_isa,
                        backend,
                    )
                    for dependency in callees
                    if catalog.primitives_named(dependency.primitive, unmasked=False)
                )

        return lowered_slots, tuple(sorted(discovered_dependencies))

    def _record_lowering_diagnostics(
        self,
        profile_name: str,
        backend: str,
        primitive: str,
        slot: SelectedImplementation,
        lowered: LoweringResult,
    ) -> None:
        # In partial mode, lowerer "info" diagnostics are coverage gaps. Strict mode promotes
        # them below, scoped to the selected profile/backend slot.
        self.diagnostics.extend(d for d in lowered.diagnostics if d.severity != "info")
        if lowered.specialization is not None:
            return
        entry = _lowering_skipped_entry(profile_name, backend, primitive, slot, lowered)
        self.skipped.append(entry)
        if self.request.mode == "strict" and entry.status == "coverage_gap":
            self.diagnostics.extend(_strict_lowering_diagnostics(entry))

    def _record_pruned_skip(self, profile_name: str, slot: "_LoweredSlot") -> None:
        reason = _pruned_reason(slot)
        diagnostic = Diagnostic(
            severity="info",
            code="TSL-PIPELINE-PRUNED-SPECIALIZATION",
            message=reason,
            location=slot.spec.source.start if slot.spec.source is not None else None,
        )
        entry = SkippedEntry(
            profile=profile_name,
            backend=slot.backend,
            primitive=slot.spec.primitive_name,
            extension=slot.spec.extension_name,
            type_tag=slot.spec.type_tag,
            reason=reason,
            diagnostics=(diagnostic,),
            source_primitive_name=slot.spec.source_primitive_name,
            result_kind=slot.spec.result_kind,
            param_kinds=slot.spec.param_kinds,
            mask_policy=slot.spec.mask_policy,
            axis=slot.spec.axis,
            variant_names=slot.spec.variant_names,
        )
        self.skipped.append(entry)
        if self.request.mode == "strict":
            self.diagnostics.append(_strict_pruned_diagnostic(entry))

    def _record_coverage(
        self,
        profile_name: str,
        lowered_specs: list["_LoweredSlot"],
        pruned: list["_LoweredSlot"],
    ) -> None:
        self.coverage.extend(
            CoverageEntry(
                profile=profile_name,
                backend=slot.backend,
                primitive=slot.spec.primitive_name,
                extension=slot.spec.extension_name,
                type_tag=slot.spec.type_tag,
                source_primitive_name=slot.spec.source_primitive_name,
                result_kind=slot.spec.result_kind,
                param_kinds=slot.spec.param_kinds,
                mask_policy=slot.spec.mask_policy,
                axis=slot.spec.axis,
                variant_names=slot.spec.variant_names,
            )
            for slot in lowered_specs
            if slot not in pruned
        )


def _record_render_extensions(
    catalog: Catalog,
    selected_extensions: dict[str, Extension],
    slot: SelectedImplementation,
) -> None:
    _record_preferred_render_extension(selected_extensions, slot.extension)
    if slot.fixed_fallback_extension is not None:
        _record_preferred_render_extension(
            selected_extensions, slot.fixed_fallback_extension
        )
    if (
        slot.primitive.result_target is None
        or slot.primitive.result_target[0] != RESULT_DIM_EXTENSION
        or slot.to_target is None
    ):
        return
    target_extension = catalog.extensions.get(slot.to_target)
    if target_extension is not None:
        _record_preferred_render_extension(selected_extensions, target_extension)


def _record_preferred_render_extension(
    selected_extensions: dict[str, Extension],
    extension: Extension,
) -> None:
    """Keep the most capable active variant for one emitted public ISA tag.

    Internal variants such as ``avx2_vl`` and their base ``avx2`` both render as
    ``avx2``. Dependency closure can discover a base extension later as a fixed-width
    fallback or representation target; that must not overwrite the active variant's
    native-predicate mask policy.
    """

    current = selected_extensions.get(extension.isa_name)
    if current is None or _render_extension_priority(extension) > _render_extension_priority(
        current
    ):
        selected_extensions[extension.isa_name] = extension


def _render_extension_priority(extension: Extension) -> tuple[int, str]:
    return (extension.metadata.native_sort_order or 0, extension.name)


def _pruned_reason(slot: "_LoweredSlot") -> str:
    return unresolved_callee_reason(slot.unresolved_callee)


def _lowering_skipped_entry(
    profile_name: str,
    backend: str,
    primitive: str,
    slot: SelectedImplementation,
    lowered: LoweringResult,
) -> SkippedEntry:
    shape = parse_signature(slot.primitive.signature)
    return SkippedEntry(
        profile=profile_name,
        backend=backend,
        primitive=primitive,
        extension=slot.extension.name,
        type_tag=slot.type_tag,
        reason=next((d.message for d in lowered.diagnostics), "unsupported body"),
        diagnostics=lowered.diagnostics,
        status=_skip_status(lowered.diagnostics),
        source_primitive_name=slot.primitive.name,
        result_kind="" if shape is None else shape.result_kind,
        param_kinds=() if shape is None else shape.param_kinds,
        mask_policy=slot.primitive.attributes.get("mask"),
        axis=tuple(
            (key, slot.primitive.attributes[key])
            for key in sorted(slot.primitive.attributes)
            if key in BOOLEAN_WILDCARD_ATTRIBUTES
        ),
        variant_names=tuple(
            variant.name for variant in slot.implementation.variants
        ),
    )


def _skip_status(diagnostics: tuple[Diagnostic, ...]) -> SkipStatus:
    if any(d.code == "TSL-LOWER-POLICY-DEFERRED-SIGNATURE" for d in diagnostics):
        return "policy_deferred"
    return "coverage_gap"


def _has_strict_skips(skipped: list[SkippedEntry]) -> bool:
    return any(entry.status == "coverage_gap" for entry in skipped)


def _strict_lowering_diagnostics(entry: SkippedEntry) -> tuple[Diagnostic, ...]:
    coverage_gaps = tuple(
        diagnostic
        for diagnostic in entry.diagnostics
        if diagnostic.severity == "info"
    )
    if not coverage_gaps:
        return (
            _strict_skip_diagnostic(
                entry,
                code="TSL-PIPELINE-SKIPPED-SPECIALIZATION",
                message=entry.reason,
            ),
        )
    return tuple(
        _strict_skip_diagnostic(
            entry,
            code=diagnostic.code,
            message=diagnostic.message,
            location=diagnostic.location,
        )
        for diagnostic in coverage_gaps
    )


def _strict_pruned_diagnostic(entry: SkippedEntry) -> Diagnostic:
    return _strict_skip_diagnostic(
        entry,
        code="TSL-PIPELINE-PRUNED-SPECIALIZATION",
        message=entry.reason,
    )


def _strict_skip_diagnostic(
    entry: SkippedEntry,
    *,
    code: str,
    message: str,
    location: SourceLocation | None = None,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code=code,
        message=f"{_skipped_label(entry)} skipped: {message}",
        location=location,
    )


def _skipped_label(entry: SkippedEntry) -> str:
    return (
        f"{entry.profile}/{entry.backend} "
        f"{entry.primitive}<{entry.extension}, {entry.type_tag}>"
    )


def _requested_primitives(
    request: GenerationRequest,
    catalog: Catalog,
) -> tuple[str, ...]:
    """Primitive roots requested by the caller.

    ``None`` means "the whole loaded catalog"; an explicit empty tuple remains
    a deliberate request for no roots.
    """

    if request.primitives is not None:
        return request.primitives
    return tuple(sorted({primitive.name for primitive in catalog.primitives}))


def _merge_benchmark_plans(
    plans: tuple[BenchmarkProjectPlan, ...],
) -> BenchmarkProjectPlan:
    if not plans:
        return EMPTY_BENCHMARK_PROJECT_PLAN
    return BenchmarkProjectPlan(
        profiles=tuple(profile for plan in plans for profile in plan.profiles),
        diagnostics=tuple(diagnostic for plan in plans for diagnostic in plan.diagnostics),
        coverage=tuple(entry for plan in plans for entry in plan.coverage),
    )


def _finalize(
    by_primitive: dict[str, list[LoweredSpecialization]],
) -> dict[str, tuple[LoweredSpecialization, ...]]:
    return {
        name: tuple(sorted(specs, key=_spec_key)) for name, specs in by_primitive.items()
    }


def _spec_key(spec: LoweredSpecialization) -> tuple[int, str, str]:
    return (_TYPE_ORDER.get(spec.type_tag, 99), spec.type_tag, spec.extension_name)


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


def _coverage_key(entry: CoverageEntry) -> tuple[object, ...]:
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


def _skipped_key(entry: SkippedEntry) -> tuple[object, ...]:
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
) -> GenerationResult:
    return _result(
        ArtifactSet.create(()),
        None,
        diagnostics,
        coverage,
        skipped,
        emitted_profiles,
        lowering_trace,
    )


def _result(
    artifacts: ArtifactSet,
    rendered: RenderedProject | None,
    diagnostics: list[Diagnostic],
    coverage: list[CoverageEntry],
    skipped: list[SkippedEntry],
    emitted_profiles: tuple[EmittedProfile, ...] = (),
    lowering_trace: LoweringTrace | None = None,
) -> GenerationResult:
    return GenerationResult(
        artifacts=artifacts,
        rendered=rendered,
        diagnostics=sort_diagnostics(diagnostics),
        coverage=tuple(sorted(coverage, key=_coverage_key)),
        skipped=tuple(sorted(skipped, key=_skipped_key)),
        emitted_profiles=emitted_profiles,
        lowering_trace=lowering_trace,
    )


def _empty(diagnostics: list[Diagnostic]) -> GenerationResult:
    return _result(ArtifactSet.create(()), None, diagnostics, [], [])
