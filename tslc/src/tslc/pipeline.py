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

from tslc.backend.translation import create_backend_dialect
from tslc.catalog.builder import CatalogBuilder
from tslc.catalog.machine_profiles import MachineProfile, load_machine_profiles_checked
from tslc.catalog.model import Catalog, Extension, RESULT_DIM_BASE, RESULT_DIM_EXTENSION
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
    primitives: tuple[str, ...]
    profiles: tuple[str, ...]
    type_tags: tuple[str, ...]
    backends: tuple[str, ...] = _DEFAULT_BACKENDS
    mode: GenerationMode = "partial"
    # Pull the value-test harness primitives (vector<->array round-trip and mask normalization)
    # into the dependency closure so the generated differential tests can build a hardware
    # register from a lane array and read its result back. Off for ordinary generation.
    test_harness: bool = False


# Primitives the differential value tests call to move data in/out of a hardware register and to
# normalize a hardware mask. Seeded into the closure only when ``test_harness`` is set.
TEST_HARNESS_PRIMITIVES = ("from_array", "to_array", "to_integral")


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
            )
            if self.profile_renders
            else None
        )
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
        worklist = list(self.request.primitives)
        if self.request.test_harness:
            worklist.extend(TEST_HARNESS_PRIMITIVES)
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
        self.profile_renders.append(
            ProfileRender(
                profile=profile,
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
                    dependency.primitive
                    for dependency in callees
                    if catalog.primitives_named(dependency.primitive, unmasked=False)
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

    def policy_of(name: str, policy: str | None) -> str | None:
        return policy if name in split_names else None

    def key(
        slot: _LoweredSlot,
    ) -> tuple[str, str, str | None, VectorIdentity, VectorIdentity | None]:
        s = slot.spec
        return (
            slot.backend,
            s.primitive_name,
            policy_of(s.primitive_name, s.mask_policy),
            VectorIdentity(s.type_tag, s.extension_name),
            (
                VectorIdentity(s.target.base_tag, s.target.extension_isa)
                if s.target is not None
                else None
            ),
        )

    valid = {key(slot) for slot in slots}
    changed = True
    while changed:
        changed = False
        for slot in slots:
            slot_key = key(slot)
            if slot_key not in valid:
                continue
            for dependency in slot.callees:
                resolved = (
                    slot.backend,
                    dependency.primitive,
                    policy_of(dependency.primitive, dependency.mask_policy),
                    dependency.source,
                    dependency.target,
                )
                if resolved not in valid:
                    valid.discard(slot_key)
                    changed = True
                    break

    grouped: dict[str, dict[str, list[LoweredSpecialization]]] = {}
    pruned: list[_LoweredSlot] = []
    for slot in slots:
        if key(slot) in valid:
            grouped.setdefault(slot.backend, {}).setdefault(
                slot.spec.primitive_name, []
            ).append(slot.spec)
        else:
            pruned.append(slot)
    return grouped, pruned


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
