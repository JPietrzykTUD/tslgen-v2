"""Evaluate and rank implementation candidates for one selection slot."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import Catalog, Extension, Implementation, Primitive
from tslc.diagnostics import Diagnostic, diagnostic_at


@dataclass(frozen=True, slots=True)
class _BestBody:
    implementation: Implementation
    required_features: frozenset[str]
    required_compiler_capabilities: frozenset[str]


@dataclass(frozen=True, slots=True)
class RankedCandidate:
    """A usable implementation body for one ``(extension, type, to_target)`` slot, carrying the
    principled ranking keys so callers (selection, and the ``explain`` tool) can see *why*
    one body outranks another. ``sort_key`` is the exact tuple selection minimizes."""

    implementation: Implementation
    required_features: frozenset[str]
    required_compiler_capabilities: frozenset[str]
    distance: int  # (a) position in the extension chain; own extension (0) before inherited
    specificity: int  # (b) type-group member count; fewer = more specific
    flag_count: int  # (c) applicable target-feature count; more = more specialized
    compiler_capability_count: int  # (d) compiler requirements; more = more specialized
    source_order: int  # (e) first occurrence in source

    @property
    def sort_key(self) -> tuple[int, int, int, int, int]:
        return (
            self.distance,
            self.specificity,
            -self.flag_count,
            -self.compiler_capability_count,
            self.source_order,
        )


@dataclass(frozen=True, slots=True)
class RejectedCandidate:
    """An implementation on the extension chain that could *not* serve this slot, with why."""

    implementation: Implementation
    reason: str


@dataclass(frozen=True, slots=True)
class CandidateEvaluation:
    """The full candidate field for one slot: usable bodies (best-first) and the rejected ones."""

    extension_known: bool
    ranked: tuple[RankedCandidate, ...]
    rejected: tuple[RejectedCandidate, ...]


RANKING_KEYS: tuple[tuple[str, str], ...] = (
    ("distance", "own extension before an inherited one"),
    ("specificity", "more specific type-group (fewer members)"),
    ("flag_count", "more required target features (more specialized)"),
    (
        "compiler_capability_count",
        "more required compiler capabilities (more specialized)",
    ),
    ("source_order", "earlier in source (arbitrary final tiebreak)"),
)


def evaluate_candidates(
    catalog: Catalog,
    profile: MachineProfile,
    primitive: Primitive,
    extension_name: str,
    type_tag: str,
    to_target: str | None,
    backend_id: str | None = None,
    compiler_capabilities: frozenset[str] | None = None,
) -> CandidateEvaluation:
    """The candidate field for one ``(extension, type, to_target)`` slot.

    Gathers bodies from the extension and the ancestors it inherits from (e.g. avx2_vl
    borrows avx2's body where it has none of its own), splits them into usable
    :class:`RankedCandidate` (best-first by the principled keys) and
    :class:`RejectedCandidate` (with the reason each on-chain body was dropped), and
    single-sources selection so both :meth:`_best_bodies` and the ``explain`` tool
    agree on the ranking. Off-chain bodies are not reported — they belong to other slots.
    """

    chain = catalog.extension_chain(extension_name)
    distance = {name: index for index, name in enumerate(chain)}
    ranked: list[RankedCandidate] = []
    rejected: list[RejectedCandidate] = []
    for implementation in primitive.implementations:
        if implementation.extension not in distance:
            continue  # belongs to a different extension's slot, not this one
        if not catalog.type_group_contains(implementation.type_group, type_tag):
            rejected.append(
                RejectedCandidate(
                    implementation,
                    f"type-group {implementation.type_group!r} does not contain {type_tag}",
                )
            )
            continue
        # Second-axis match: a body with a `to_target_group` is kept only if that group contains
        # the target (the `==`/`*` markers contain no concrete tag, so they stay unselected). A
        # body with NO `to_target_group` is a target-generic catch-all (it spells the target
        # symbolically via `as_base`/`window_base`) and matches ANY target — a fallback behind
        # the more type-specific dedicated bodies.
        if (
            to_target is not None
            and implementation.to_target_group is not None
            and not catalog.type_group_contains(implementation.to_target_group, to_target)
        ):
            rejected.append(
                RejectedCandidate(
                    implementation,
                    f"to-target-group {implementation.to_target_group!r} does not contain "
                    f"target {to_target!r}",
                )
            )
            continue
        if to_target is not None and implementation.target_constraint is not None:
            source_extension = catalog.extensions[extension_name]
            target_extension = catalog.extensions.get(to_target)
            if target_extension is None or not implementation.target_constraint.matches(
                source_extension, target_extension
            ):
                rejected.append(
                    RejectedCandidate(
                        implementation,
                        f"target constraint does not admit target {to_target!r}",
                    )
                )
                continue
        requirements = _applicable_requirements(
            catalog,
            implementation,
            type_tag,
            backend_id,
        )
        if requirements is None:
            rejected.append(
                RejectedCandidate(
                    implementation,
                    f"no requires clause applies to {type_tag} for backend {backend_id!r}",
                )
            )
            continue
        flags, required_capabilities = requirements
        if not (flags <= profile.features):
            missing = ", ".join(sorted(flags - profile.features))
            rejected.append(
                RejectedCandidate(
                    implementation,
                    f"requires [{', '.join(sorted(flags))}] not satisfied by profile "
                    f"{profile.name!r} (missing: {missing})",
                )
            )
            continue
        if compiler_capabilities is not None and not (
            required_capabilities <= compiler_capabilities
        ):
            missing = ", ".join(sorted(required_capabilities - compiler_capabilities))
            rejected.append(
                RejectedCandidate(
                    implementation,
                    f"requires compiler capabilities [{', '.join(sorted(required_capabilities))}] "
                    f"for backend {backend_id!r} (missing: {missing})",
                )
            )
            continue
        ranked.append(
            RankedCandidate(
                implementation=implementation,
                required_features=flags,
                required_compiler_capabilities=required_capabilities,
                distance=distance[implementation.extension],
                specificity=catalog.type_group_specificity(implementation.type_group),
                flag_count=len(flags),
                compiler_capability_count=len(required_capabilities),
                source_order=implementation.source_order,
            )
        )
    ranked.sort(key=lambda candidate: candidate.sort_key)
    return CandidateEvaluation(
        extension_known=bool(chain),
        ranked=tuple(ranked),
        rejected=tuple(rejected),
    )


def best_bodies(
    catalog: Catalog,
    profile: MachineProfile,
    primitive: Primitive,
    extension_name: str,
    type_tag: str,
    to_target: str | None,
    backend_id: str | None,
    compiler_capabilities: frozenset[str] | None,
    warnings: dict[str, Diagnostic],
) -> tuple[_BestBody, ...]:
    ranked = evaluate_candidates(
        catalog,
        profile,
        primitive,
        extension_name,
        type_tag,
        to_target,
        backend_id,
        compiler_capabilities,
    ).ranked
    if not ranked:
        return ()
    best = ranked[0]
    best_impl = best.implementation
    # Ambiguity guard: warn only when the pick is genuinely *arbitrary* — two
    # bodies on the same extension that tie on distance, type-group
    # specificity, target-feature count, and compiler-capability count, yet
    # use different type groups. Equal-size different groups are necessarily
    # incomparable (a proper subset has strictly fewer members), so neither
    # is more type-specific and only source order decides. Feature or
    # compiler-capability differences are principled specialization
    # tiebreaks, so they do not warn.
    rival_groups = {
        candidate.implementation.type_group
        for candidate in ranked
        if candidate.distance == best.distance
        and candidate.specificity == best.specificity
        and candidate.flag_count == best.flag_count
        and candidate.compiler_capability_count == best.compiler_capability_count
        and candidate.implementation.type_group != best_impl.type_group
    }
    if rival_groups:
        groups = ", ".join(sorted({best_impl.type_group, *rival_groups}))
        message = (
            f"{primitive.name!r} on {extension_name}: type-groups {{{groups}}} are equally "
            f"specific and incomparable (both match overlapping types); the body is chosen "
            f"by source order — disambiguate the corpus selectors"
        )
        warnings.setdefault(
            message,
            diagnostic_at(
                severity="warning",
                code="TSL-SELECT-AMBIGUOUS-SPECIFICITY",
                message=message,
                source=best_impl.selector_source or best_impl.source or primitive.source,
            ),
        )
    selected = (
        _compiler_capability_frontier(ranked)
        if compiler_capabilities is None
        else (best,)
    )
    # Automatic package generation keeps compiler-gated bodies only as
    # optimizations over an unconditional implementation. Capability-only
    # APIs remain available through explicit capability selection.
    if compiler_capabilities is None and not any(
        not candidate.required_compiler_capabilities
        for candidate in selected
    ):
        return ()
    return tuple(
        _BestBody(
            candidate.implementation,
            candidate.required_features,
            candidate.required_compiler_capabilities,
        )
        for candidate in selected
    )


def fixed_width_fallback(
    catalog: Catalog,
    profile: MachineProfile,
    primitive: Primitive,
    source: Extension,
    type_tag: str,
    to_target: str | None,
    emitted_extensions: list[str],
    backend_id: str,
    compiler_capabilities: frozenset[str] | None,
    *,
    require_native: bool = False,
) -> Extension | None:
    """Best backend-emitted substrate for the source extension's exact width.

    The result remains concrete so call dependency closure can prove the
    fallback specialization exists. Backend overlays opt out through their
    extension metadata.
    """

    if source.vector_bits <= 0 or source.vector_bits_kind != "fixed":
        return None
    source_backend = source.metadata.backend.get(backend_id)
    if (
        source_backend is None
        or source_backend.participates_in_dataparallel_inference
    ):
        return None
    candidates: list[tuple[tuple[int, int, str], Extension]] = []
    for name in emitted_extensions:
        extension = catalog.extensions[name]
        if extension.name == source.name:
            continue
        if extension.vector_bits != source.vector_bits:
            continue
        if extension.vector_bits_kind != "fixed":
            continue
        backend_metadata = extension.metadata.backend.get(backend_id)
        if (
            backend_metadata is not None
            and not backend_metadata.participates_in_dataparallel_inference
        ):
            continue
        if not extension.supports_backend(backend_id):
            continue
        if not _extension_declares_type(
            catalog, extension, type_tag, backend_id
        ):
            continue
        ranked = evaluate_candidates(
            catalog,
            profile,
            primitive,
            name,
            type_tag,
            to_target,
            backend_id,
            compiler_capabilities,
        ).ranked
        if not ranked:
            continue
        if require_native and "intrinsic" not in (
            ranked[0].implementation.safety.reasons
        ):
            continue
        if compiler_capabilities is None and not any(
            not candidate.required_compiler_capabilities
            for candidate in _compiler_capability_frontier(ranked)
        ):
            continue
        candidates.append(
            (
                (
                    extension.metadata.native_sort_order or 0,
                    extension.vector_bits,
                    extension.isa_name,
                ),
                extension,
            )
        )
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def _compiler_capability_frontier(
    ranked: tuple[RankedCandidate, ...],
) -> tuple[RankedCandidate, ...]:
    """Candidates that win for at least one downstream capability set."""

    winners: list[RankedCandidate] = []
    for candidate in ranked:
        if any(
            earlier.required_compiler_capabilities
            <= candidate.required_compiler_capabilities
            for earlier in winners
        ):
            continue
        winners.append(candidate)
    return tuple(winners)


def _applicable_requirements(
    catalog: Catalog,
    implementation: Implementation,
    type_tag: str,
    backend_id: str | None,
) -> tuple[frozenset[str], frozenset[str]] | None:
    """The requirement-clause flags that apply to ``type_tag`` (None if none apply).

    The *union* of every applicable clause's flags: a body's requirements may be the
    selector ancestors' clauses plus its own (e.g. `?i?`'s ``[avx512f]`` + a `ToExtension:
    avx2`'s ``[avx512dq]``), all of which must hold. Mutually-exclusive type-group clauses in
    a `requires` map still contribute only the one that matches the type, so this is
    equivalent to the former first-match for single/disjoint clauses."""

    if not implementation.requirements:
        return frozenset(), frozenset()
    flags: set[str] = set()
    compiler_capabilities: set[str] = set()
    matched = False
    for clause in implementation.requirements:
        if clause.extension is not None and clause.extension != implementation.extension:
            continue
        if clause.type_group is not None and not catalog.type_group_contains(
            clause.type_group, type_tag
        ):
            continue
        flags |= clause.flags
        if clause.compiler:
            matching = tuple(
                requirement
                for requirement in clause.compiler
                if requirement.backend_id == backend_id
            )
            if not matching:
                return None
            for requirement in matching:
                compiler_capabilities |= requirement.capabilities
        matched = True
    if not matched:
        return None
    return frozenset(flags), frozenset(compiler_capabilities)


def _extension_declares_type(
    catalog: Catalog,
    extension: Extension,
    type_tag: str,
    backend_id: str,
) -> bool:
    return any(
        extension.direct_vector_register_type(backend_id, group) is not None
        and catalog.type_group_contains(group, type_tag)
        for group in extension.vector_register_types
    )

__all__ = (
    "CandidateEvaluation",
    "RANKING_KEYS",
    "RankedCandidate",
    "RejectedCandidate",
    "_BestBody",
    "_compiler_capability_frontier",
    "best_bodies",
    "evaluate_candidates",
    "fixed_width_fallback",
)
