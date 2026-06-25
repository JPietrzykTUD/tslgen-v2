"""Compiler orchestration: sources -> ... -> generated per-profile project.

Pure up to the optional write/verify steps. For each machine profile, selects the
implementations reachable in that profile (one specialization per reachable
`(extension, type)`), lowers each, groups by primitive, and renders per-profile
headers/modules with a top-level dispatch.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

from tslc.backend.translation import create_backend_dialect
from tslc.catalog.builder import CatalogBuilder
from tslc.catalog.machine_profiles import MachineProfile, load_machine_profiles_checked
from tslc.catalog.model import (
    Catalog,
    Extension,
    ImplementationSafety,
    RESULT_DIM_BASE,
    RESULT_DIM_EXTENSION,
)
from tslc.catalog.validation import validate_catalog
from tslc.diagnostics import Diagnostic, SourceLocation, has_errors, sort_diagnostics
from tslc.ir.scan import scan
from tslc.lower.dependencies import (
    CallDependency,
    VectorIdentity,
    extract_call_dependencies_from_segments,
)
from tslc.lower.lowerer import LoweredSpecialization, Lowerer, LoweringResult
from tslc.output.artifacts import ArtifactSet
from tslc.render.project import ProfileRender, RenderedProject, render_project
from tslc.select.selector import (
    SelectedImplementation,
    Selector,
)
from tslc.sources import SourceLoader
from tslc.support_policy import DEFAULT_SUPPORT_POLICY
from tslc.support_policy_views import immediate_split_names, policy_split_names
from tslc.value_tests import HarnessPrimitiveNames, discover_harness_primitives

_DEFAULT_BACKENDS = DEFAULT_SUPPORT_POLICY.default_backend_ids
GenerationMode = Literal["partial", "strict"]
_TYPE_ORDER = {
    tag: index
    for index, tag in enumerate(
        ("si8", "si16", "si32", "si64", "ui8", "ui16", "ui32", "ui64", "f32", "f64")
    )
}


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    source_paths: tuple[Path, ...]
    machine_profiles_path: Path
    primitives: tuple[str, ...] | None
    profiles: tuple[str, ...]
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


@dataclass(frozen=True, slots=True)
class GenerationResult:
    artifacts: ArtifactSet
    rendered: RenderedProject | None
    diagnostics: tuple[Diagnostic, ...]
    coverage: tuple[CoverageEntry, ...]
    skipped: tuple[SkippedEntry, ...] = ()


@dataclass(frozen=True, slots=True)
class _PipelineInputs:
    catalog: Catalog
    machine_profiles: Mapping[str, MachineProfile]
    split_names: frozenset[str]
    imm_split_names: frozenset[str]
    test_harness: HarnessPrimitiveNames


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


def _load_inputs(request: GenerationRequest) -> tuple[_PipelineInputs | None, list[Diagnostic]]:
    diagnostics: list[Diagnostic] = []

    load_result = SourceLoader().load(request.source_paths)
    diagnostics.extend(load_result.diagnostics)
    if has_errors(diagnostics):
        return None, diagnostics

    from tslc.syntax.parser import TslParser

    parse_result = TslParser().parse(load_result.documents)
    diagnostics.extend(parse_result.diagnostics)
    if has_errors(diagnostics):
        return None, diagnostics

    catalog_result = CatalogBuilder().build(parse_result)
    diagnostics.extend(catalog_result.diagnostics)
    if catalog_result.catalog is None or has_errors(diagnostics):
        return None, diagnostics
    catalog = catalog_result.catalog
    diagnostics.extend(
        validate_catalog(
            catalog,
            parse_result,
            required_backends=request.backends,
        )
    )
    if has_errors(diagnostics):
        return None, diagnostics
    # Names emitted in >1 form (split to `_mask`/`_maskz`). Only these are policy-distinguished by
    # `CallLowerer`; a single-form masked name (`blend`, `[mask=pass_through]`) stays bare, so the
    # prune must treat it bare too (else a bare `blend` caller can't resolve the pass_through spec).
    split_names = policy_split_names(catalog)
    imm_split_names = immediate_split_names(catalog)
    test_harness = discover_harness_primitives(catalog)
    if request.test_harness:
        diagnostics.extend(test_harness.diagnostics)
    profile_result = load_machine_profiles_checked(request.machine_profiles_path)
    diagnostics.extend(profile_result.diagnostics)
    if has_errors(diagnostics):
        return None, diagnostics
    machine_profiles = profile_result.profiles
    return (
        _PipelineInputs(
            catalog=catalog,
            machine_profiles=machine_profiles,
            split_names=split_names,
            imm_split_names=imm_split_names,
            test_harness=test_harness,
        ),
        diagnostics,
    )


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
        self.type_tags = _sorted_type_tags(request.type_tags)
        self.diagnostics = diagnostics
        self.coverage: list[CoverageEntry] = []
        self.skipped: list[SkippedEntry] = []
        self.profile_renders: list[ProfileRender] = []

    def run(self) -> GenerationResult:
        for profile_name in sorted(self.request.profiles):
            profile = self.inputs.machine_profiles.get(profile_name)
            if profile is None:
                self._record_unknown_profile(profile_name)
                continue
            self._generate_profile(profile_name, profile)

        if self.request.mode == "strict" and (
            self.skipped or has_errors(self.diagnostics)
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
        worklist = list(_requested_primitives(self.request, self.inputs.catalog))
        if self.request.test_harness:
            worklist.extend(
                name
                for name in (
                    self.inputs.test_harness.from_array,
                    self.inputs.test_harness.to_array,
                    self.inputs.test_harness.to_integral,
                )
                if name is not None
            )
        processed: set[str] = set()
        while worklist:
            primitive = worklist.pop(0)
            if primitive in processed:
                continue
            processed.add(primitive)
            primitive_slots, discovered_primitives = self._process_primitive(
                profile, profile_name, primitive, selected_extensions
            )
            lowered_specs.extend(primitive_slots)
            for dependency_primitive in discovered_primitives:
                if dependency_primitive not in processed:
                    worklist.append(dependency_primitive)

        grouped, pruned = _prune_unresolved(lowered_specs, self.inputs.split_names)
        for slot in pruned:
            self._record_pruned_skip(profile_name, slot)
        self._record_coverage(profile_name, lowered_specs, pruned)
        effective_profile = _profile_with_required_features(profile, grouped)
        self.profile_renders.append(
            ProfileRender(
                profile=effective_profile,
                cpp=_finalize(grouped.get("cpp", {})),
                rust=_finalize(grouped.get("rust", {})),
                extensions=selected_extensions,
            )
        )

    def _process_primitive(
        self,
        profile: MachineProfile,
        profile_name: str,
        primitive: str,
        selected_extensions: dict[str, Extension],
    ) -> tuple[list["_LoweredSlot"], list[str]]:
        catalog = self.inputs.catalog
        selection = self.selector.select_profile(
            catalog, profile, primitive, self.type_tags
        )
        self.diagnostics.extend(selection.diagnostics)
        lowered_slots: list[_LoweredSlot] = []
        discovered_primitives: list[str] = []

        for slot in selection.selected:
            selected_extensions[slot.extension.isa_name] = slot.extension
            body_segments = scan(
                slot.implementation.body_text,
                source=slot.implementation.body_source,
            )
            callees = extract_call_dependencies_from_segments(
                body_segments,
                primitive,
                slot.extension.isa_name,
                slot.type_tag,
                *_target_dependency_context(slot),
                catalog,
            )
            slot_lowered = False
            for backend in self.request.backends:
                dialect = create_backend_dialect(catalog, backend)
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
                        callees=callees,
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
        if self.request.mode == "strict":
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
            reason="pruned: a called primitive is not generated for this profile",
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


@dataclass(slots=True, eq=False)
class _LoweredSlot:
    backend: str
    spec: LoweredSpecialization
    callees: frozenset[CallDependency]


def _target_dependency_context(
    slot: SelectedImplementation,
) -> tuple[str | None, str | None, str | None]:
    target_alias = (
        slot.primitive.result_target[1] if slot.primitive.result_target is not None else None
    )
    target_base = (
        slot.to_target
        if slot.primitive.result_target is not None
        and slot.primitive.result_target[0] == RESULT_DIM_BASE
        else None
    )
    target_extension = (
        slot.to_target
        if slot.primitive.result_target is not None
        and slot.primitive.result_target[0] == RESULT_DIM_EXTENSION
        else None
    )
    return target_alias, target_base, target_extension


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
    )


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


def _prune_unresolved(
    slots: list[_LoweredSlot],
    split_names: frozenset[str] = frozenset(),
) -> tuple[dict[str, dict[str, list[LoweredSpecialization]]], list[_LoweredSlot]]:
    """Drop emitted specializations whose called primitives are not themselves emitted
    for the same ``simd<type, ext>`` (else the generated call would not link). Iterated
    to a fixpoint, since pruning a callee can in turn dangle its callers.

    Identity is **policy-aware, but only for names that are actually split** (`split_names`,
    emitted in >1 form → `_mask`/`_maskz`). For those, the slot key and the call both carry the
    `mask_policy`, so `mov_maskz` isn't satisfied by a live `mov_mask`. A name with a single form
    — unmasked, OR a lone `[mask=…]` like `blend` that `CallLowerer` leaves bare — normalizes its
    policy to `None`, so a bare caller (`max`'s `blend`) and a policy-tagged caller (`mov`'s
    `blend attrs[mask=pass_through]`) both resolve the one bare spec."""

    valid = {_slot_key(slot, split_names) for slot in slots}
    changed = True
    while changed:
        changed = False
        for slot in slots:
            slot_key = _slot_key(slot, split_names)
            if slot_key not in valid:
                continue
            for dependency in slot.callees:
                resolved = _dependency_key(slot, dependency, split_names)
                if resolved not in valid:
                    valid.discard(slot_key)
                    changed = True
                    break

    live_slots = [slot for slot in slots if _slot_key(slot, split_names) in valid]
    _propagate_transitive_call_facts(live_slots, split_names)

    grouped: dict[str, dict[str, list[LoweredSpecialization]]] = {}
    pruned: list[_LoweredSlot] = []
    for slot in slots:
        if _slot_key(slot, split_names) in valid:
            grouped.setdefault(slot.backend, {}).setdefault(
                slot.spec.primitive_name, []
            ).append(slot.spec)
        else:
            pruned.append(slot)
    return grouped, pruned


def _policy_of(
    name: str,
    policy: str | None,
    split_names: frozenset[str],
) -> str | None:
    return policy if name in split_names else None


def _slot_key(
    slot: _LoweredSlot,
    split_names: frozenset[str],
) -> tuple[str, str, str | None, VectorIdentity, VectorIdentity | None]:
    spec = slot.spec
    return (
        slot.backend,
        spec.primitive_name,
        _policy_of(spec.primitive_name, spec.mask_policy, split_names),
        VectorIdentity(spec.type_tag, spec.extension_name),
        (
            VectorIdentity(spec.target.base_tag, spec.target.extension_isa)
            if spec.target is not None
            else None
        ),
    )


def _dependency_key(
    slot: _LoweredSlot,
    dependency: CallDependency,
    split_names: frozenset[str],
) -> tuple[str, str, str | None, VectorIdentity, VectorIdentity | None]:
    return (
        slot.backend,
        dependency.primitive,
        _policy_of(dependency.primitive, dependency.mask_policy, split_names),
        dependency.source,
        dependency.target,
    )


def _propagate_transitive_call_facts(
    slots: list[_LoweredSlot],
    split_names: frozenset[str],
) -> None:
    """Propagate lowered call facts through the live call graph.

    A caller that reaches unsafe callee metadata records an internal unsafe
    dependency for review/diagnostics. The call lowerer marks direct
    caller-unsafe call sites as local unsafe blocks, so callee-only unsafety does
    not force a whole-body unsafe frame. The public caller contract remains the
    caller's own explicit or inferred contract: higher-level wrappers such as
    vector-from-array can discharge a raw-pointer callee's requirements by
    passing a pointer they created from local storage.

    Required feature flags also propagate bottom-up. If ``prim1`` calls
    ``prim2`` and ``prim2`` eventually calls a body requiring ``avx512f``, the
    lowered ``prim1`` specialization carries ``avx512f`` too, and the generated
    profile can compile every reached body with the effective architecture
    flags.
    """

    safety_by_key = {
        _safety_key(slot, split_names): slot.spec.safety for slot in slots
    }
    features_by_key = {
        _safety_key(slot, split_names): slot.spec.required_features for slot in slots
    }
    dependency_targets: dict[
        tuple[str, str, str | None, VectorIdentity, VectorIdentity | None],
        list[tuple[
            tuple[str, str, str | None, VectorIdentity, VectorIdentity | None],
            tuple[str, ...],
            tuple[str, str] | None,
            tuple[tuple[str, str, str], ...],
        ]],
    ] = {}
    for slot in slots:
        dependency_targets.setdefault(_slot_key(slot, split_names), []).append(
            _safety_key(slot, split_names)
        )
    changed = True
    while changed:
        changed = False
        for slot in slots:
            slot_key = _safety_key(slot, split_names)
            safety = safety_by_key[slot_key]
            features = features_by_key[slot_key]
            propagated = safety
            propagated_features = features
            for dependency in sorted(
                slot.callees,
                key=lambda dependency: (
                    dependency.primitive,
                    dependency.mask_policy or "",
                    dependency.source.base_tag,
                    dependency.source.extension_isa,
                    dependency.target.base_tag if dependency.target is not None else "",
                    dependency.target.extension_isa
                    if dependency.target is not None
                    else "",
                ),
            ):
                for dependency_safety_key in dependency_targets.get(
                    _dependency_key(slot, dependency, split_names), []
                ):
                    dependency_safety = safety_by_key[dependency_safety_key]
                    if (
                        dependency_safety.internal_unsafe
                        or dependency_safety.caller_unsafe
                    ):
                        propagated = propagated.merge(
                            ImplementationSafety(
                                internal_unsafe=True,
                                reasons=dependency_safety.reasons
                                | frozenset({"unsafe_callee"}),
                            )
                        )
                    dependency_features = features_by_key[dependency_safety_key]
                    if not dependency_features <= propagated_features:
                        propagated_features = propagated_features | dependency_features
            if propagated != safety or propagated_features != features:
                safety_by_key[slot_key] = propagated
                features_by_key[slot_key] = propagated_features
                changed = True

    for slot in slots:
        slot_key = _safety_key(slot, split_names)
        safety = safety_by_key[slot_key]
        features = features_by_key[slot_key]
        if safety == slot.spec.safety and features == slot.spec.required_features:
            continue
        slot.spec = replace(
            slot.spec,
            safety=safety,
            required_features=features,
        )


def _profile_with_required_features(
    profile: MachineProfile,
    grouped: dict[str, dict[str, list[LoweredSpecialization]]],
) -> MachineProfile:
    """Profile plus the transitive feature flags required by live lowered specs."""

    required = set(profile.features)
    for by_primitive in grouped.values():
        for specs in by_primitive.values():
            for spec in specs:
                required.update(spec.required_features)
    features = frozenset(required)
    return profile if features == profile.features else replace(profile, features=features)


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


def _safety_key(
    slot: _LoweredSlot,
    split_names: frozenset[str],
) -> tuple[
    tuple[str, str, str | None, VectorIdentity, VectorIdentity | None],
    tuple[str, ...],
    tuple[str, str] | None,
    tuple[tuple[str, str, str], ...],
]:
    """A lowered-body identity for safety propagation before emitted-name splits.

    Runtime and immediate overloads intentionally share the pruning key until
    final emitted-name splitting. Safety must keep them distinct, because their
    bodies can have different unsafe requirements.
    """

    spec = slot.spec
    return (
        _slot_key(slot, split_names),
        spec.param_kinds,
        spec.immediate,
        spec.generic_params,
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
