"""Resolve which implementation bodies a machine profile emits.

For a profile, a primitive, and a concrete type, every *extension* reachable in
the profile yields its own specialization slot (the extension is part of the
`simd<type, ext>` key, so there is no cross-extension ambiguity). Within one
`(extension, type)` slot the body is chosen by the confirmed order:

    1. most specific type-group (fewest members)
    2. tie -> most hardware flags (most specialized)
    3. tie -> first occurrence (source order)

An implementation body is usable only if the `requires` clause that applies to the
type has its flags ⊆ the profile's feature set. A *derived* extension (`avx2_vl`
inherits `avx2`) is only active when its `lscpu_flags ⊆ features`, and then
supersedes its base; a base extension's bodies self-gate via `requires`.
"""

from __future__ import annotations

from dataclasses import dataclass

from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import (
    Catalog,
    Extension,
    Implementation,
    Primitive,
)
from tslc.catalog.signatures import parse_signature
from tslc.diagnostics import Diagnostic, diagnostic_at
from tslc.support_policy import DEFAULT_SUPPORT_POLICY, SupportPolicy
from tslc.support_policy_views import (
    concrete_target_candidates,
    selectable_variants,
)


@dataclass(frozen=True, slots=True)
class SelectedImplementation:
    primitive: Primitive
    implementation: Implementation
    extension: Extension
    type_tag: str
    # The concrete feature flags selected for this implementation body after
    # applying extension/type-scoped `requires` clauses.
    required_features: frozenset[str] = frozenset()
    # For a representation-change primitive (`result_target`), the concrete target this slot
    # is monomorphized for: a target *type tag* (base dim, e.g. ``ui32``) or a target
    # *extension name* (extension dim, e.g. ``sse``). None for ordinary primitives.
    to_target: str | None = None
    # For a sized-vector body with ``unroll_variants`` effective-true, the concrete lane count
    # this slot is monomorphized at (one slot per ``size_bits`` entry; lanes = size // typebits).
    # None = the ordinary single ``LANES``-parametric slot. Lets a size-changing body emit a
    # concrete ``Generic<N>`` per size instead of a const-generic-expression template.
    concrete_lanes: int | None = None


@dataclass(frozen=True, slots=True)
class ProfileSelectionResult:
    selected: tuple[SelectedImplementation, ...]
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class _BestBody:
    implementation: Implementation
    required_features: frozenset[str]


@dataclass(frozen=True, slots=True)
class RankedCandidate:
    """A usable implementation body for one ``(extension, type, to_target)`` slot, carrying the
    four principled ranking keys so callers (selection, and the ``explain`` tool) can see *why*
    one body outranks another. ``sort_key`` is the exact tuple selection minimizes."""

    implementation: Implementation
    required_features: frozenset[str]
    distance: int  # (a) position in the extension chain; own extension (0) before inherited
    specificity: int  # (b) type-group member count; fewer = more specific
    flag_count: int  # (c) applicable hardware-flag count; more = more specialized
    source_order: int  # (d) first occurrence in source

    @property
    def sort_key(self) -> tuple[int, int, int, int]:
        return (self.distance, self.specificity, -self.flag_count, self.source_order)


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


# Ranking keys, by the order selection applies them; surfaced by ``explain`` to name the decisive
# tiebreak between the winner and the runner-up.
RANKING_KEYS: tuple[tuple[str, str], ...] = (
    ("distance", "own extension before an inherited one"),
    ("specificity", "more specific type-group (fewer members)"),
    ("flag_count", "more required hardware flags (more specialized)"),
    ("source_order", "earlier in source (arbitrary final tiebreak)"),
)


class Selector:
    def __init__(self, support: SupportPolicy = DEFAULT_SUPPORT_POLICY) -> None:
        self.support = support

    def select_profile(
        self,
        catalog: Catalog,
        profile: MachineProfile,
        primitive_name: str,
        type_tags: tuple[str, ...],
    ) -> ProfileSelectionResult:
        # Variants of this name fall into two groups, emitted side by side:
        #  - the UNMASKED overload set: same-arity overloads (store's `(ptr,v)`/`(ptr,s)`,
        #    shift's `(v,s)`/`(v,sImm)`/`(v,v)`) resolved by argument type. The arity filter
        #    keeps only this group's shared arity (a different-arity unmasked overload — e.g.
        #    hadd `s:=v` vs masked-arg `s:=(m,v)` — is left for later).
        #  - the MASKED variants admitted by the support-policy catalog view: value-masking ops
        #    (result `v`), mask-producing comparisons (result `m`), and masked `load`/`store`
        #    (`ptr`). Each is a distinct callable, split to `<name>_mask`/`_maskz` at render
        #    (so a different arity / two policies like `mov`'s zero+pass_through both emit).
        #    `gather`/`scatter` (`vidx`) and masked reductions (result `s`) are deferred.
        variants = selectable_variants(catalog, primitive_name, self.support)
        if not variants:
            return ProfileSelectionResult(
                selected=(),
                diagnostics=(
                    Diagnostic(
                        severity="error",
                        code="TSL-SELECT-UNKNOWN-PRIMITIVE",
                        message=f"no primitive named {primitive_name!r}",
                    ),
                ),
            )

        selected: list[SelectedImplementation] = []
        warnings: dict[str, Diagnostic] = {}  # keyed by message, so each ambiguity warns once
        for primitive in variants:
            # A non-vector (free-function) primitive (`allocate`/`deallocate`) has no SIMD axis:
            # its type group is a placeholder (`ptr`) that no arith tag matches, and its body is
            # ISA-independent. Iterate its OWN type-group members (so `base::in` resolves) and
            # emit a single slot — the free-function render emits one `tsl::name(...)`.
            shape = parse_signature(primitive.signature)
            free_function = shape is not None and shape.is_free_function
            primitive_type_tags = (
                tuple(
                    sorted(
                        {
                            member
                            for impl in primitive.implementations
                            for member in catalog.type_group_members(impl.type_group)
                        }
                    )
                )
                if free_function
                else type_tags
            )
            emitted_free = False
            for extension_name in self._emit_extensions(catalog, profile):
                if emitted_free:
                    break
                for type_tag in primitive_type_tags:
                    # A representation-change primitive has a SECOND axis (the target type /
                    # extension); it emits one slot per (type_tag, to_target). An ordinary
                    # primitive has a single target-less slot.
                    to_targets = concrete_target_candidates(
                        catalog,
                        primitive,
                        extension_name,
                        type_tag,
                        self.support,
                    )
                    for to_target in to_targets:
                        best = self._best_body(
                            catalog, profile, primitive, extension_name,
                            type_tag, to_target, warnings,
                        )
                        if best is not None:
                            extension = catalog.extensions[extension_name]
                            for lanes in self._monomorphized_lanes(
                                extension, best.implementation, type_tag
                            ):
                                selected.append(
                                    SelectedImplementation(
                                        primitive=primitive,
                                        implementation=best.implementation,
                                        extension=extension,
                                        type_tag=type_tag,
                                        required_features=best.required_features,
                                        to_target=to_target,
                                        concrete_lanes=lanes,
                                    )
                                )
                            if free_function:
                                # One ISA-independent slot is enough; the body is identical
                                # across extensions and the render ignores the extension.
                                emitted_free = True
                                break
                    if emitted_free:
                        break
        return ProfileSelectionResult(
            selected=tuple(selected), diagnostics=tuple(warnings.values())
        )

    def _emit_extensions(self, catalog: Catalog, profile: MachineProfile) -> list[str]:
        """Extensions to emit for a profile.

        A *base* extension (no `inherits`) is always a candidate; its individual
        bodies self-gate via their `requires` (e.g. avx2's 256-bit *float* add needs
        only `avx`, so it appears on an avx-only profile while its 256-bit *integer*
        add does not). A *derived* extension (e.g. `avx2_vl`, which `inherits avx2`)
        is a candidate only when genuinely active — its `lscpu_flags ⊆ features` —
        and then it *supersedes* its base (avx512vl profiles use `_vl`, not the base).
        Candidates with no usable body for any type drop out later in `_best_body`.
        """

        active_derived = [
            name
            for name, ext in catalog.extensions.items()
            if ext.inherits is not None and ext.lscpu_flags <= profile.features
        ]
        superseded = {catalog.extensions[name].inherits for name in active_derived}

        emit: list[str] = []
        for name, ext in catalog.extensions.items():
            if not self.support.supports_extension(ext, catalog.target_families):
                # Unsupported extension substrates stay source-visible but are not generated in
                # this slice. Concrete bodies still self-gate via `requires`, so they drop on a
                # profile lacking the flags.
                continue
            if not self.support.extension_targets_profile(
                ext.family,
                profile.family,
                catalog.target_families,
            ):
                # Family routing is catalog-owned. This prevents an ISA-independent
                # `requires []` body (the scalar-store) from registering an extension substrate
                # on a profile family that did not declare it.
                continue
            if name in superseded:
                continue
            if ext.inherits is not None and not (ext.lscpu_flags <= profile.features):
                continue  # inactive derived extension
            emit.append(name)
        return sorted(emit)

    def evaluate_candidates(
        self,
        catalog: Catalog,
        profile: MachineProfile,
        primitive: Primitive,
        extension_name: str,
        type_tag: str,
        to_target: str | None,
    ) -> CandidateEvaluation:
        """The candidate field for one ``(extension, type, to_target)`` slot.

        Gathers bodies from the extension and the ancestors it inherits from (e.g. avx2_vl
        borrows avx2's body where it has none of its own), splits them into usable
        :class:`RankedCandidate` (best-first by the four principled keys) and
        :class:`RejectedCandidate` (with the reason each on-chain body was dropped), and
        single-sources the selection logic so both :meth:`_best_body` and the ``explain`` tool
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
            flags = _applicable_flags(catalog, implementation, type_tag)
            if flags is None:
                rejected.append(
                    RejectedCandidate(
                        implementation, f"no requires clause applies to {type_tag}"
                    )
                )
                continue
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
            ranked.append(
                RankedCandidate(
                    implementation=implementation,
                    required_features=flags,
                    distance=distance[implementation.extension],
                    specificity=catalog.type_group_specificity(implementation.type_group),
                    flag_count=len(flags),
                    source_order=implementation.source_order,
                )
            )
        ranked.sort(key=lambda candidate: candidate.sort_key)
        return CandidateEvaluation(
            extension_known=bool(chain),
            ranked=tuple(ranked),
            rejected=tuple(rejected),
        )

    def _best_body(
        self,
        catalog: Catalog,
        profile: MachineProfile,
        primitive: Primitive,
        extension_name: str,
        type_tag: str,
        to_target: str | None,
        warnings: dict[str, Diagnostic],
    ) -> _BestBody | None:
        ranked = self.evaluate_candidates(
            catalog, profile, primitive, extension_name, type_tag, to_target
        ).ranked
        if not ranked:
            return None
        best = ranked[0]
        best_impl = best.implementation
        # Ambiguity guard: warn only when the pick is genuinely *arbitrary* — two candidate
        # bodies on the same extension that tie on every principled key (a) distance,
        # (b) type-group specificity, and (c) hardware-flag count, yet are keyed to *different*
        # type-groups. Equal-size different groups are necessarily incomparable (a proper
        # subset has strictly fewer members), so neither is more type-specific; equal flag
        # counts mean hardware-specialization doesn't separate them either — so only
        # `source_order` (d) decides, which is arbitrary. A flag-count difference IS a
        # principled tiebreak (more required features = more specialized), so it does not warn.
        rival_groups = {
            candidate.implementation.type_group
            for candidate in ranked
            if candidate.distance == best.distance
            and candidate.specificity == best.specificity
            and candidate.flag_count == best.flag_count
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
        return _BestBody(best_impl, best.required_features)
        # (a) before (b): when a derived extension is active and supersedes its base
        # (e.g. avx2_vl over avx2 on an avx512vl profile), the derived ext's OWN body
        # wins even if a base body is more type-specific — so avx512vl comparisons use
        # the `_vl` native-mask body, not the base's lane-bitmask `si?` body. Within a
        # single extension distance ties, so specificity still decides there.

    def _monomorphized_lanes(
        self, extension: Extension, implementation: Implementation, type_tag: str
    ) -> tuple[int | None, ...]:
        """The concrete lane counts to monomorphize this body at, or ``(None,)`` for the
        ordinary single ``LANES``-parametric slot.

        A sized-vector body with ``unroll_variants`` effective-true and a non-empty
        ``size_bits`` emits one slot per size, lanes = size // type-bit-width — so a
        size-changing body is concrete per size (stable Rust can spell the changed-width
        output) rather than a const-generic-expression template. Everything else (fixed-width
        extensions, non-unrolled sized bodies) keeps the single ``None`` slot, byte-identical
        to before."""

        if not self.support.uses_sized_vector(extension) or not extension.size_bits:
            return (None,)
        unroll = (
            implementation.unroll_variants
            if implementation.unroll_variants is not None
            else extension.unroll_variants
        )
        if not unroll:
            return (None,)
        type_bits = self.support.type_bit_width_or_default(type_tag)
        return tuple(size // type_bits for size in extension.size_bits if size >= type_bits)


def _applicable_flags(
    catalog: Catalog, implementation: Implementation, type_tag: str
) -> frozenset[str] | None:
    """The requirement-clause flags that apply to ``type_tag`` (None if none apply).

    The *union* of every applicable clause's flags: a body's requirements may be the
    selector ancestors' clauses plus its own (e.g. `?i?`'s ``[avx512f]`` + a `ToExtension:
    avx2`'s ``[avx512dq]``), all of which must hold. Mutually-exclusive type-group clauses in
    a `requires` map still contribute only the one that matches the type, so this is
    equivalent to the former first-match for single/disjoint clauses."""

    if not implementation.requirements:
        return frozenset()
    flags: set[str] = set()
    matched = False
    for clause in implementation.requirements:
        if clause.extension is not None and clause.extension != implementation.extension:
            continue  # this clause is scoped to a different extension
        if clause.type_group is None or catalog.type_group_contains(
            clause.type_group, type_tag
        ):
            flags |= clause.flags
            matched = True
    return frozenset(flags) if matched else None
