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
    CallDependencyOrigin,
    _LoweredSlot,
    _profile_with_required_features,
    _propagate_transitive_call_facts,
    _prune_unresolved,
    _target_dependency_context,
)
from tslc._pipeline_inputs import _PipelineInputs, _load_inputs
from tslc.backend.registry import backend_capabilities
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import RESULT_DIM_EXTENSION, Catalog, Extension
from tslc.catalog.scalar_types import SCALAR_TYPE_ORDER
from tslc.diagnostics import Diagnostic, SourceLocation, has_errors, sort_diagnostics
from tslc.ir.scan import scan
from tslc.lower.dependencies import (
    CallDependency,
    extract_call_dependencies_from_segments,
)
from tslc.lower.lowerer import LoweredSpecialization, Lowerer, LoweringResult
from tslc.output.artifacts import ArtifactSet
from tslc.render.project import ProfileRender, RenderedProject, render_project
from tslc.select.selector import (
    SelectedImplementation,
    Selector,
)
from tslc.support_policy import DEFAULT_SUPPORT_POLICY

_DEFAULT_BACKENDS = DEFAULT_SUPPORT_POLICY.default_backend_ids
GenerationMode = Literal["partial", "strict"]
SkipStatus = Literal["coverage_gap", "policy_deferred"]
_TYPE_ORDER = SCALAR_TYPE_ORDER
_CPP_ALGORITHM_SUPPORT_PRIMITIVES = (
    "load",
    "store",
    # The helper calls the emitted wrapper `store_mask`; selecting `store`
    # also selects its pass-through masked form, which is split to that name
    # during C++ emitted-name finalization.
    "to_integral",
    "to_mask",
    "gather_narrow",
    "compress_store",
    "mask_population_count",
    "mask_binary_and",
)
_RUST_ALGORITHM_SUPPORT_PRIMITIVES = (
    "load",
    "store",
)


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    source_paths: tuple[Path, ...]
    machine_profiles_path: Path
    primitives: tuple[str, ...] | None
    profiles: tuple[str, ...] | None
    type_tags: tuple[str, ...]
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


@dataclass(frozen=True, slots=True)
class CoverageEntry:
    profile: str
    backend: str
    primitive: str
    extension: str
    type_tag: str


@dataclass(frozen=True, slots=True)
class SkippedEntry:
    """A selected slot whose body could not be lowered yet (recorded, not failed)."""

    profile: str
    backend: str
    primitive: str
    extension: str
    type_tag: str
    reason: str
    status: SkipStatus = "coverage_gap"


@dataclass(frozen=True, slots=True)
class GenerationResult:
    artifacts: ArtifactSet
    rendered: RenderedProject | None
    diagnostics: tuple[Diagnostic, ...]
    coverage: tuple[CoverageEntry, ...]
    skipped: tuple[SkippedEntry, ...] = ()


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

    return _GenerationSession(request, inputs, diagnostics).run()


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
        self.type_tags = _sorted_type_tags(request.type_tags)
        self.diagnostics = diagnostics
        self.coverage: list[CoverageEntry] = []
        self.skipped: list[SkippedEntry] = []
        self.profile_renders: list[ProfileRender] = []

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

        if self.request.mode == "strict" and (
            _has_strict_skips(self.skipped) or has_errors(self.diagnostics)
        ):
            return _result_without_artifacts(
                self.diagnostics, self.coverage, self.skipped
            )

        rendered = (
            render_project(
                tuple(self.profile_renders),
                self.request.backends,
                self.inputs.imm_split_names,
                catalog=self.inputs.catalog,
                value_test_warnings=self.request.value_test_warnings,
                value_test_fuzz=self.request.value_test_fuzz,
                assets=self.inputs.render_assets,
            )
            if self.profile_renders
            else None
        )
        if rendered is not None:
            self.diagnostics.extend(rendered.diagnostics)
        artifacts = rendered.artifacts if rendered is not None else ArtifactSet.create(())
        return _result(artifacts, rendered, self.diagnostics, self.coverage, self.skipped)

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
            (primitive, all_backend_ids)
            for primitive in _requested_primitives(self.request, self.inputs.catalog)
        ]
        if self.request.test_harness:
            worklist.extend(
                (name, all_backend_ids)
                for name in (
                    self.inputs.test_harness.from_array,
                    self.inputs.test_harness.to_array,
                    self.inputs.test_harness.to_integral,
                    self.inputs.test_harness.load,
                    self.inputs.test_harness.store,
                )
                if name is not None
            )
        if "cpp" in all_backend_ids:
            worklist.extend(
                (name, frozenset({"cpp"}))
                for name in _cpp_algorithm_support_primitives(self.inputs.catalog)
            )
        if "rust" in all_backend_ids:
            worklist.extend(
                (name, frozenset({"rust"}))
                for name in _rust_algorithm_support_primitives(self.inputs.catalog)
            )
        processed: dict[str, set[str]] = {}
        while worklist:
            primitive, target_backends = worklist.pop(0)
            remaining_backends = target_backends - processed.get(primitive, set())
            if not remaining_backends:
                continue
            primitive_slots, discovered_primitives = self._process_primitive(
                profile,
                profile_name,
                primitive,
                selected_extensions,
                remaining_backends,
            )
            processed.setdefault(primitive, set()).update(remaining_backends)
            lowered_specs.extend(primitive_slots)
            for dependency_primitive in discovered_primitives:
                if remaining_backends - processed.get(dependency_primitive, set()):
                    worklist.append((dependency_primitive, remaining_backends))

        grouped, pruned = _prune_unresolved(lowered_specs, self.inputs.split_names)
        for slot in pruned:
            self._record_pruned_skip(profile_name, slot)
        self._record_coverage(profile_name, lowered_specs, pruned)
        effective_profile = _profile_with_required_features(profile, grouped)
        self.profile_renders.append(
            ProfileRender(
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
            )
        )

    def _process_primitive(
        self,
        profile: MachineProfile,
        profile_name: str,
        primitive: str,
        selected_extensions: dict[str, Extension],
        backend_ids: frozenset[str],
    ) -> tuple[list["_LoweredSlot"], list[str]]:
        catalog = self.inputs.catalog
        selection = self.selector.select_profile(
            catalog, profile, primitive, self.type_tags
        )
        self.diagnostics.extend(selection.diagnostics)
        lowered_slots: list[_LoweredSlot] = []
        discovered_primitives: list[str] = []

        for slot in selection.selected:
            _record_render_extensions(catalog, selected_extensions, slot)
            body_segments = scan(
                slot.implementation.body_text,
                source=slot.implementation.body_source,
            )
            dependency_context = _target_dependency_context(slot)
            callees = set(
                extract_call_dependencies_from_segments(
                    body_segments,
                    primitive,
                    slot.extension.isa_name,
                    slot.type_tag,
                    *dependency_context,
                    catalog,
                )
            )
            callee_origins = [
                CallDependencyOrigin(dependency, "implementation")
                for dependency in sorted(callees, key=_dependency_sort_key)
            ]
            for variant in slot.implementation.variants:
                variant_callees = extract_call_dependencies_from_segments(
                    scan(variant.body_text, source=variant.body_source),
                    primitive,
                    slot.extension.isa_name,
                    slot.type_tag,
                    *dependency_context,
                    catalog,
                )
                callees.update(variant_callees)
                callee_origins.extend(
                    CallDependencyOrigin(
                        dependency,
                        f"implementation variant {variant.name!r}",
                    )
                    for dependency in sorted(variant_callees, key=_dependency_sort_key)
                )
            slot_lowered = False
            for capability in self.backends:
                backend = capability.backend_id
                if backend not in backend_ids:
                    continue
                dialect = capability.create_dialect(catalog)
                lowered = self.lowerer.lower(
                    slot,
                    catalog,
                    dialect,
                    body_segments=body_segments,
                )
                self._record_lowering_diagnostics(
                    profile_name, backend, primitive, slot, lowered
                )
                if lowered.specialization is None:
                    continue
                lowered_slots.append(
                    _LoweredSlot(
                        backend=backend,
                        spec=lowered.specialization,
                        callees=frozenset(callees),
                        callee_origins=tuple(callee_origins),
                    )
                )
                slot_lowered = True

            if slot_lowered:
                discovered_primitives.extend(
                    dependency_primitive
                    for dependency_primitive in sorted(
                        {dependency.primitive for dependency in callees}
                    )
                    if catalog.primitives_named(dependency_primitive, unmasked=False)
                )

        return lowered_slots, discovered_primitives

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
            self.diagnostics.extend(
                _strict_lowering_diagnostics(entry, lowered.diagnostics)
            )

    def _record_pruned_skip(self, profile_name: str, slot: "_LoweredSlot") -> None:
        entry = SkippedEntry(
            profile=profile_name,
            backend=slot.backend,
            primitive=slot.spec.primitive_name,
            extension=slot.spec.extension_name,
            type_tag=slot.spec.type_tag,
            reason=_pruned_reason(slot),
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
            )
            for slot in lowered_specs
            if slot not in pruned
        )


def _record_render_extensions(
    catalog: Catalog,
    selected_extensions: dict[str, Extension],
    slot: SelectedImplementation,
) -> None:
    selected_extensions[slot.extension.isa_name] = slot.extension
    if (
        slot.primitive.result_target is None
        or slot.primitive.result_target[0] != RESULT_DIM_EXTENSION
        or slot.to_target is None
    ):
        return
    target_extension = catalog.extensions.get(slot.to_target)
    if target_extension is not None:
        selected_extensions[target_extension.isa_name] = target_extension


def _dependency_sort_key(
    dependency: CallDependency,
) -> tuple[str, str, str, str, str, str]:
    return (
        dependency.primitive,
        dependency.mask_policy or "",
        dependency.source.extension_isa,
        dependency.source.base_tag,
        dependency.target.extension_isa if dependency.target is not None else "",
        dependency.target.base_tag if dependency.target is not None else "",
    )


def _pruned_reason(slot: "_LoweredSlot") -> str:
    unresolved = slot.unresolved_callee
    if unresolved is None:
        return "pruned: a called primitive is not generated for this profile"
    dependency = unresolved.dependency
    return (
        f"pruned: {unresolved.origin} calls {_dependency_label(dependency)}, "
        "but that specialization is not generated for this profile"
    )


def _dependency_label(dependency: CallDependency) -> str:
    source = (
        f"{dependency.primitive}<"
        f"{dependency.source.extension_isa}, {dependency.source.base_tag}>"
    )
    if dependency.mask_policy is not None:
        source = f"{source}[mask={dependency.mask_policy}]"
    if dependency.target is None:
        return source
    return (
        f"{source} -> <"
        f"{dependency.target.extension_isa}, {dependency.target.base_tag}>"
    )


def _lowering_skipped_entry(
    profile_name: str,
    backend: str,
    primitive: str,
    slot: SelectedImplementation,
    lowered: LoweringResult,
) -> SkippedEntry:
    return SkippedEntry(
        profile=profile_name,
        backend=backend,
        primitive=primitive,
        extension=slot.extension.name,
        type_tag=slot.type_tag,
        reason=next((d.message for d in lowered.diagnostics), "unsupported body"),
        status=_skip_status(lowered.diagnostics),
    )


def _skip_status(diagnostics: tuple[Diagnostic, ...]) -> SkipStatus:
    if any(d.code == "TSL-LOWER-POLICY-DEFERRED-SIGNATURE" for d in diagnostics):
        return "policy_deferred"
    return "coverage_gap"


def _has_strict_skips(skipped: list[SkippedEntry]) -> bool:
    return any(entry.status == "coverage_gap" for entry in skipped)


def _strict_lowering_diagnostics(
    entry: SkippedEntry, diagnostics: tuple[Diagnostic, ...]
) -> tuple[Diagnostic, ...]:
    coverage_gaps = tuple(d for d in diagnostics if d.severity == "info")
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


def _cpp_algorithm_support_primitives(catalog: Catalog) -> tuple[str, ...]:
    return tuple(
        primitive
        for primitive in _CPP_ALGORITHM_SUPPORT_PRIMITIVES
        if catalog.primitives_named(primitive, unmasked=False)
    )


def _rust_algorithm_support_primitives(catalog: Catalog) -> tuple[str, ...]:
    return tuple(
        primitive
        for primitive in _RUST_ALGORITHM_SUPPORT_PRIMITIVES
        if catalog.primitives_named(primitive, unmasked=False)
    )


def _finalize(
    by_primitive: dict[str, list[LoweredSpecialization]],
) -> dict[str, tuple[LoweredSpecialization, ...]]:
    return {
        name: tuple(sorted(specs, key=_spec_key)) for name, specs in by_primitive.items()
    }


def _spec_key(spec: LoweredSpecialization) -> tuple[int, str, str]:
    return (_TYPE_ORDER.get(spec.type_tag, 99), spec.type_tag, spec.extension_name)


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


def _coverage_key(entry: CoverageEntry) -> tuple[str, str, str, str, int, str]:
    return (
        entry.profile,
        entry.primitive,
        entry.backend,
        entry.extension,
        _TYPE_ORDER.get(entry.type_tag, 99),
        entry.type_tag,
    )


def _skipped_key(entry: SkippedEntry) -> tuple[str, str, str, str, int, str]:
    return (
        entry.profile,
        entry.primitive,
        entry.backend,
        entry.extension,
        _TYPE_ORDER.get(entry.type_tag, 99),
        entry.type_tag,
    )


def _result_without_artifacts(
    diagnostics: list[Diagnostic],
    coverage: list[CoverageEntry],
    skipped: list[SkippedEntry],
) -> GenerationResult:
    return _result(ArtifactSet.create(()), None, diagnostics, coverage, skipped)


def _result(
    artifacts: ArtifactSet,
    rendered: RenderedProject | None,
    diagnostics: list[Diagnostic],
    coverage: list[CoverageEntry],
    skipped: list[SkippedEntry],
) -> GenerationResult:
    return GenerationResult(
        artifacts=artifacts,
        rendered=rendered,
        diagnostics=sort_diagnostics(diagnostics),
        coverage=tuple(sorted(coverage, key=_coverage_key)),
        skipped=tuple(sorted(skipped, key=_skipped_key)),
    )


def _empty(diagnostics: list[Diagnostic]) -> GenerationResult:
    return _result(ArtifactSet.create(()), None, diagnostics, [], [])
