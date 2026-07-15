"""Typed coverage-inventory calculation over compiler lowering outcomes."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import Catalog
from tslc.pipeline import CoverageEntry, GenerationResult, SkippedEntry

PrimitiveInventoryStatus = Literal["VERIFIED", "lowers", "partial", "NONE"]


_CATEGORY_BY_CODE = {
    "TSL-PIPELINE-PRUNED-SPECIALIZATION": "pruned (closure)",
    "TSL-LOWER-SIZED-WIDTH-CHANGE": "generic-vector repr-change (deferred)",
    "TSL-LOWER-UNRESOLVED-TYPE-QUERY": "unresolved type query",
    "TSL-LOWER-UNRESOLVED-VALUE-QUERY": "unresolved value query",
    "TSL-LOWER-UNRESOLVED-CAST-TYPE": "unresolved cast type",
    "TSL-LOWER-POLICY-DEFERRED-SIGNATURE": "policy-deferred scalable signature",
    "TSL-LOWER-UNSUPPORTED-KIND": "unsupported signature kind",
    "TSL-LOWER-NO-COMPLETE": "no top-level complete",
    "TSL-LOWER-VARIANT-NO-COMPLETE": "no top-level complete",
    "TSL-LOWER-UNSUPPORTED-CALL-TYPEARGS": "call type-args (bare-ext/index)",
    "TSL-LOWER-UNSUPPORTED-MASK": "unsupported mask region",
}


@dataclass(frozen=True, slots=True)
class BackendProfileInventory:
    """One backend's emitted output against a profile-shared candidate universe."""

    backend: str
    emitted: int
    attempted: int
    shared_candidates: int
    coverage_gaps: int
    policy_deferred: int

    @property
    def applicable(self) -> bool:
        return self.attempted > 0

    @property
    def coverage_percent(self) -> float | None:
        if not self.applicable or self.shared_candidates == 0:
            return None
        return 100.0 * self.emitted / self.shared_candidates

    @property
    def lowering_success_percent(self) -> float | None:
        if not self.applicable:
            return None
        return 100.0 * self.emitted / self.attempted


@dataclass(frozen=True, slots=True)
class ProfileInventory:
    profile: str
    architecture: str
    target_feature_count: int
    shared_candidates: int
    backends: tuple[BackendProfileInventory, ...]


@dataclass(frozen=True, slots=True)
class PrimitiveInventory:
    name: str
    signatures: tuple[str, ...]
    status: PrimitiveInventoryStatus
    extensions_by_backend: tuple[tuple[str, tuple[str, ...]], ...]
    emitted: int
    skipped: int
    coverage_percent: float
    dominant_gap: str | None


@dataclass(frozen=True, slots=True)
class CoverageInventory:
    profiles: tuple[str, ...]
    backends: tuple[str, ...]
    type_tags: tuple[str, ...]
    primitive_count: int
    source_declarations: int
    catalog_variants: int
    signature_count: int
    implementation_count: int
    emitted_specializations: int
    coverage_gaps: int
    policy_deferred: int
    average_specializations_per_primitive: float
    aggregate_coverage_percent: float
    mean_primitive_coverage_percent: float
    build_verified_primitives: int
    backend_parity: bool
    backend_extensions: tuple[tuple[str, tuple[str, ...]], ...]
    profile_inventory: tuple[ProfileInventory, ...]
    primitives: tuple[PrimitiveInventory, ...]
    skip_reasons: tuple[tuple[str, int], ...]


_LogicalSlot = tuple[object, ...]
_SlotCounts = dict[tuple[str, str], Counter[_LogicalSlot]]


def skip_category(entry: SkippedEntry) -> str:
    """Return a stable category from structured diagnostic identity, never prose."""

    if not entry.diagnostics:
        return f"unclassified {entry.status}"
    diagnostic = next(
        (
            diagnostic
            for diagnostic in entry.diagnostics
            if diagnostic.severity == "error"
        ),
        entry.diagnostics[0],
    )
    return _CATEGORY_BY_CODE.get(diagnostic.code, diagnostic.code)


def build_coverage_inventory(
    catalog: Catalog,
    result: GenerationResult,
    *,
    machine_profiles: tuple[MachineProfile, ...],
    backends: tuple[str, ...],
    type_tags: tuple[str, ...],
    verified_primitives: frozenset[str] = frozenset(),
) -> CoverageInventory:
    """Fold finalized lowering outcomes into one backend-comparable inventory."""

    ordered_profiles = tuple(
        sorted(
            machine_profiles,
            key=lambda profile: _profile_sort_key(catalog, profile),
        )
    )
    profiles = tuple(profile.name for profile in ordered_profiles)
    names = tuple(sorted({primitive.name for primitive in catalog.primitives}))
    signatures: dict[str, set[str]] = defaultdict(set)
    for primitive in catalog.primitives:
        signatures[primitive.name].add(primitive.signature)

    emitted = _entry_counts(result.coverage)
    gaps = _entry_counts(
        entry for entry in result.skipped if entry.status == "coverage_gap"
    )
    deferred = _entry_counts(
        entry for entry in result.skipped if entry.status == "policy_deferred"
    )
    attempted = _sum_counts(emitted, gaps)
    shared = _shared_candidate_counts(profiles, backends, attempted)

    profile_inventory = tuple(
        _profile_inventory(
            profile, backends, emitted, gaps, deferred, attempted, shared
        )
        for profile in ordered_profiles
    )
    applicable = {
        (profile.profile, cell.backend)
        for profile in profile_inventory
        for cell in profile.backends
        if cell.applicable
    }
    primitive_percentages = {
        name: _primitive_coverage_percent(
            name, profiles, backends, emitted, shared, applicable
        )
        for name in names
    }

    categories: dict[str, Counter[str]] = defaultdict(Counter)
    skipped_by_primitive: Counter[str] = Counter()
    for skipped_entry in result.skipped:
        skipped_by_primitive[skipped_entry.primitive] += 1
        categories[skipped_entry.primitive][skip_category(skipped_entry)] += 1

    emitted_by_primitive: Counter[str] = Counter(
        entry.primitive for entry in result.coverage
    )
    extensions: dict[str, dict[str, set[str]]] = {
        backend: defaultdict(set) for backend in backends
    }
    for coverage_entry in result.coverage:
        extensions[coverage_entry.backend][coverage_entry.primitive].add(
            coverage_entry.extension
        )

    primitive_inventory = tuple(
        PrimitiveInventory(
            name=name,
            signatures=tuple(sorted(signatures[name])),
            status=_primitive_status(
                name,
                emitted_by_primitive[name],
                skipped_by_primitive[name],
                verified_primitives,
            ),
            extensions_by_backend=tuple(
                (backend, tuple(sorted(extensions[backend][name])))
                for backend in backends
            ),
            emitted=emitted_by_primitive[name],
            skipped=skipped_by_primitive[name],
            coverage_percent=primitive_percentages[name],
            dominant_gap=(
                categories[name].most_common(1)[0][0] if categories[name] else None
            ),
        )
        for name in names
    )

    aggregate_emitted, aggregate_candidates = _aggregate_coverage(
        profile_inventory
    )
    histogram = Counter(skip_category(entry) for entry in result.skipped)
    primitive_count = len(names)
    return CoverageInventory(
        profiles=profiles,
        backends=backends,
        type_tags=type_tags,
        primitive_count=primitive_count,
        source_declarations=_source_declaration_count(catalog),
        catalog_variants=len(catalog.primitives),
        signature_count=len(
            {(primitive.name, primitive.signature) for primitive in catalog.primitives}
        ),
        implementation_count=sum(
            len(primitive.implementations) for primitive in catalog.primitives
        ),
        emitted_specializations=len(result.coverage),
        coverage_gaps=sum(
            entry.status == "coverage_gap" for entry in result.skipped
        ),
        policy_deferred=sum(
            entry.status == "policy_deferred" for entry in result.skipped
        ),
        average_specializations_per_primitive=(
            len(result.coverage) / primitive_count if primitive_count else 0.0
        ),
        aggregate_coverage_percent=(
            100.0 * aggregate_emitted / aggregate_candidates
            if aggregate_candidates
            else 0.0
        ),
        mean_primitive_coverage_percent=(
            sum(primitive_percentages.values()) / primitive_count
            if primitive_count
            else 0.0
        ),
        build_verified_primitives=len(set(names) & verified_primitives),
        backend_parity=_backend_parity(profiles, backends, emitted),
        backend_extensions=tuple(
            (
                backend,
                tuple(
                    sorted(
                        {
                            extension
                            for names_by_primitive in extensions[backend].values()
                            for extension in names_by_primitive
                        }
                    )
                ),
            )
            for backend in backends
        ),
        profile_inventory=profile_inventory,
        primitives=primitive_inventory,
        skip_reasons=tuple(
            sorted(histogram.items(), key=lambda item: (-item[1], item[0]))
        ),
    )


def _entry_counts(
    entries: Iterable[CoverageEntry | SkippedEntry],
) -> _SlotCounts:
    counts: _SlotCounts = defaultdict(Counter)
    for entry in entries:
        counts[(entry.profile, entry.backend)][_logical_slot(entry)] += 1
    return counts


def _logical_slot(entry: CoverageEntry | SkippedEntry) -> _LogicalSlot:
    return (
        entry.primitive,
        entry.extension,
        entry.type_tag,
        entry.source_primitive_name,
        entry.result_kind,
        entry.param_kinds,
        entry.mask_policy,
        entry.axis,
        entry.variant_names,
    )


def _sum_counts(left: _SlotCounts, right: _SlotCounts) -> _SlotCounts:
    keys = left.keys() | right.keys()
    return {
        key: left.get(key, Counter()) + right.get(key, Counter()) for key in keys
    }


def _shared_candidate_counts(
    profiles: tuple[str, ...],
    backends: tuple[str, ...],
    attempted: _SlotCounts,
) -> dict[str, Counter[_LogicalSlot]]:
    shared: dict[str, Counter[_LogicalSlot]] = {}
    for profile in profiles:
        candidates: Counter[_LogicalSlot] = Counter()
        keys = {
            key
            for backend in backends
            for key in attempted.get((profile, backend), Counter())
        }
        for key in keys:
            candidates[key] = max(
                attempted.get((profile, backend), Counter())[key]
                for backend in backends
            )
        shared[profile] = candidates
    return shared


def _profile_inventory(
    profile: MachineProfile,
    backends: tuple[str, ...],
    emitted: _SlotCounts,
    gaps: _SlotCounts,
    deferred: _SlotCounts,
    attempted: _SlotCounts,
    shared: dict[str, Counter[_LogicalSlot]],
) -> ProfileInventory:
    shared_candidates = sum(shared[profile.name].values())
    cells = tuple(
        BackendProfileInventory(
            backend=backend,
            emitted=sum(
                emitted.get((profile.name, backend), Counter()).values()
            ),
            attempted=sum(
                attempted.get((profile.name, backend), Counter()).values()
            ),
            shared_candidates=shared_candidates,
            coverage_gaps=sum(
                gaps.get((profile.name, backend), Counter()).values()
            ),
            policy_deferred=sum(
                deferred.get((profile.name, backend), Counter()).values()
            ),
        )
        for backend in backends
    )
    return ProfileInventory(
        profile=profile.name,
        architecture=profile.family,
        target_feature_count=len(profile.features),
        shared_candidates=shared_candidates,
        backends=cells,
    )


def _profile_sort_key(
    catalog: Catalog, profile: MachineProfile
) -> tuple[int, str, int, str]:
    family = catalog.target_families.profile_family(profile.family)
    family_order = family.sort_order if family is not None else 100
    return (family_order, profile.family, len(profile.features), profile.name)


def _source_declaration_count(catalog: Catalog) -> int:
    identities: set[tuple[object, ...]] = set()
    for index, primitive in enumerate(catalog.primitives):
        source = primitive.header_source
        if source is None:
            identities.add(("catalog", index))
            continue
        identities.add(
            (
                source.start.path,
                source.start.line,
                source.start.column,
            )
        )
    return len(identities)


def _primitive_coverage_percent(
    primitive: str,
    profiles: tuple[str, ...],
    backends: tuple[str, ...],
    emitted: _SlotCounts,
    shared: dict[str, Counter[_LogicalSlot]],
    applicable: set[tuple[str, str]],
) -> float:
    emitted_total = 0
    candidate_total = 0
    for profile in profiles:
        shared_count = sum(
            count for key, count in shared[profile].items() if key[0] == primitive
        )
        for backend in backends:
            if (profile, backend) not in applicable:
                continue
            candidate_total += shared_count
            emitted_total += sum(
                count
                for key, count in emitted.get((profile, backend), Counter()).items()
                if key[0] == primitive
            )
    return 100.0 * emitted_total / candidate_total if candidate_total else 0.0


def _aggregate_coverage(
    profiles: tuple[ProfileInventory, ...],
) -> tuple[int, int]:
    emitted = 0
    candidates = 0
    for profile in profiles:
        for cell in profile.backends:
            if not cell.applicable:
                continue
            emitted += cell.emitted
            candidates += profile.shared_candidates
    return emitted, candidates


def _backend_parity(
    profiles: tuple[str, ...],
    backends: tuple[str, ...],
    emitted: _SlotCounts,
) -> bool:
    if len(backends) < 2:
        return True
    return all(
        len(
            {
                tuple(sorted(emitted.get((profile, backend), Counter()).items()))
                for backend in backends
            }
        )
        <= 1
        for profile in profiles
    )


def _primitive_status(
    name: str,
    emitted: int,
    skipped: int,
    verified: frozenset[str],
) -> PrimitiveInventoryStatus:
    if name in verified:
        return "VERIFIED"
    if emitted and skipped == 0:
        return "lowers"
    if emitted:
        return "partial"
    return "NONE"


__all__ = (
    "BackendProfileInventory",
    "CoverageInventory",
    "PrimitiveInventory",
    "ProfileInventory",
    "build_coverage_inventory",
    "skip_category",
)
