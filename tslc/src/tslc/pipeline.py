"""Compiler orchestration: sources -> ... -> generated per-profile project.

Pure up to the optional write/verify steps. For each machine profile, selects the
implementations reachable in that profile (one specialization per reachable
`(extension, type)`), lowers each, groups by primitive, and renders per-profile
headers/modules with a top-level dispatch.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tslc.backend.translation import create_backend_translation
from tslc.catalog.builder import CatalogBuilder
from tslc.catalog.machine_profiles import load_machine_profiles
from tslc.catalog.model import Extension, RESULT_DIM_BASE, RESULT_DIM_EXTENSION
from tslc.diagnostics import Diagnostic, has_errors, sort_diagnostics
from tslc.lower.dependencies import (
    CallDependency,
    VectorIdentity,
    extract_call_dependencies,
)
from tslc.lower.lowerer import LoweredSpecialization, Lowerer
from tslc.output.artifacts import ArtifactSet
from tslc.render.project import ProfileRender, RenderedProject, render_project
from tslc.select.selector import Selector, immediate_split_names, policy_split_names
from tslc.sources import SourceLoader

_DEFAULT_BACKENDS = ("cpp", "rust")
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


def generate(request: GenerationRequest) -> GenerationResult:
    diagnostics: list[Diagnostic] = []

    load_result = SourceLoader().load(request.source_paths)
    diagnostics.extend(load_result.diagnostics)
    if has_errors(diagnostics):
        return _empty(diagnostics)

    from tslc.syntax.parser import TslParser

    parse_result = TslParser().parse(load_result.documents)
    diagnostics.extend(parse_result.diagnostics)
    if has_errors(diagnostics):
        return _empty(diagnostics)

    catalog_result = CatalogBuilder().build(parse_result)
    diagnostics.extend(catalog_result.diagnostics)
    if catalog_result.catalog is None or has_errors(diagnostics):
        return _empty(diagnostics)
    catalog = catalog_result.catalog
    # Names emitted in >1 form (split to `_mask`/`_maskz`). Only these are policy-distinguished by
    # `CallLowerer`; a single-form masked name (`blend`, `[mask=pass_through]`) stays bare, so the
    # prune must treat it bare too (else a bare `blend` caller can't resolve the pass_through spec).
    split_names = policy_split_names(catalog)
    imm_split_names = immediate_split_names(catalog)
    machine_profiles = load_machine_profiles(request.machine_profiles_path)

    selector = Selector()
    lowerer = Lowerer()
    type_tags = _sorted_type_tags(request.type_tags)
    coverage: list[CoverageEntry] = []
    skipped: list[SkippedEntry] = []
    profile_renders: list[ProfileRender] = []

    for profile_name in sorted(request.profiles):
        profile = machine_profiles.get(profile_name)
        if profile is None:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-PIPELINE-UNKNOWN-PROFILE",
                    message=f"no machine profile named {profile_name!r}",
                )
            )
            continue

        # Profile-scoped dependency closure: start from the requested primitives and pull
        # in only the callees referenced by bodies actually *selected* for this profile
        # (so scalar's call-free comparison bodies don't drag in SIMD-only callees).
        lowered_specs: list[_LoweredSlot] = []
        # Which extension block this profile selected for each emitted ISA tag, so the
        # renderer can register the right mask_type (lane-bitmask vs native __mmaskN).
        selected_extensions: dict[str, Extension] = {}
        worklist = list(request.primitives)
        processed: set[str] = set()
        while worklist:
            primitive = worklist.pop(0)
            if primitive in processed:
                continue
            processed.add(primitive)
            selection = selector.select_profile(catalog, profile, primitive, type_tags)
            diagnostics.extend(selection.diagnostics)
            for slot in selection.selected:
                selected_extensions[slot.extension.isa_name] = slot.extension
                target_alias = (
                    slot.primitive.result_target[1]
                    if slot.primitive.result_target is not None
                    else None
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
                callees = extract_call_dependencies(
                    slot.implementation.body_text,
                    primitive,
                    slot.extension.isa_name,
                    slot.type_tag,
                    target_alias,
                    target_base,
                    target_extension,
                    catalog,
                )
                slot_lowered = False
                for backend in request.backends:
                    translation = create_backend_translation(catalog, backend)
                    lowered = lowerer.lower(slot, catalog, translation)
                    # Real diagnostics (warnings/errors) bubble up; a not-yet-lowerable
                    # body is an "info" skip -> recorded as a coverage gap, not noise.
                    diagnostics.extend(d for d in lowered.diagnostics if d.severity != "info")
                    if lowered.specialization is None:
                        skipped.append(
                            SkippedEntry(
                                profile=profile_name,
                                backend=backend,
                                primitive=primitive,
                                extension=slot.extension.name,
                                type_tag=slot.type_tag,
                                reason=next(
                                    (d.message for d in lowered.diagnostics), "unsupported body"
                                ),
                            )
                        )
                        continue
                    lowered_specs.append(
                        _LoweredSlot(backend=backend, spec=lowered.specialization, callees=callees)
                    )
                    slot_lowered = True
                # Only pull callees referenced by a body that actually lowered — a skipped
                # body (e.g. a deferred `let<type>`/`mask<test>` delegation) must not drag its
                # callees (to_array/store/…) into the emitted set, where they would otherwise
                # surface as unbuildable generic instantiations.
                if slot_lowered:
                    for dependency in callees:
                        # `primitives_named(unmasked=False)` so a masked-ONLY callee
                        # (`blend`/`mov`) is pulled too — a masked body delegates to them, and
                        # `catalog.primitive` (unmasked-only) would miss them and prune the caller.
                        if dependency.primitive not in processed and catalog.primitives_named(
                            dependency.primitive, unmasked=False
                        ):
                            worklist.append(dependency.primitive)

        grouped, pruned = _prune_unresolved(lowered_specs, split_names)
        for slot in pruned:
            skipped.append(
                SkippedEntry(
                    profile=profile_name,
                    backend=slot.backend,
                    primitive=slot.spec.primitive_name,
                    extension=slot.spec.extension_name,
                    type_tag=slot.spec.type_tag,
                    reason="pruned: a called primitive is not generated for this profile",
                )
            )
        for slot in lowered_specs:
            if slot not in pruned:
                coverage.append(
                    CoverageEntry(
                        profile=profile_name,
                        backend=slot.backend,
                        primitive=slot.spec.primitive_name,
                        extension=slot.spec.extension_name,
                        type_tag=slot.spec.type_tag,
                    )
                )

        profile_renders.append(
            ProfileRender(
                profile=profile,
                cpp=_finalize(grouped.get("cpp", {})),
                rust=_finalize(grouped.get("rust", {})),
                extensions=selected_extensions,
            )
        )

    rendered = (
        render_project(tuple(profile_renders), request.backends, imm_split_names)
        if profile_renders
        else None
    )
    artifacts = rendered.artifacts if rendered is not None else ArtifactSet.create(())
    return GenerationResult(
        artifacts=artifacts,
        rendered=rendered,
        diagnostics=sort_diagnostics(diagnostics),
        coverage=tuple(sorted(coverage, key=_coverage_key)),
        skipped=tuple(sorted(skipped, key=_skipped_key)),
    )


@dataclass(slots=True, eq=False)
class _LoweredSlot:
    backend: str
    spec: LoweredSpecialization
    callees: frozenset[CallDependency]


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


def _empty(diagnostics: list[Diagnostic]) -> GenerationResult:
    return GenerationResult(
        artifacts=ArtifactSet.create(()),
        rendered=None,
        diagnostics=sort_diagnostics(diagnostics),
        coverage=(),
    )
