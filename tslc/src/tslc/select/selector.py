"""Resolve which implementation bodies a machine profile emits.

For a profile, a primitive, and a concrete type, every *extension* reachable in
the profile yields its own specialization slot (the extension is part of the
`simd<type, ext>` key, so there is no cross-extension ambiguity). Within one
`(extension, type)` slot the body is chosen by the confirmed order:

    1. most specific type-group (fewest members)
    2. tie -> most required target features (most specialized)
    3. tie -> most required compiler capabilities (most specialized)
    4. tie -> first occurrence (source order)

An implementation body is usable only if the `requires` clause that applies to
the type has its target features ⊆ the profile's feature set. With an explicit
backend compiler capability set, its compiler requirements must also be a
subset of that set. Ordinary project generation instead retains every body
that can win for some compiler capability set, provided that frontier contains
an unconditional fallback; the backend can then select locally for the
downstream compiler. Extension variants such as `avx2_vl` become candidates
through `active_when` profile capabilities and hide their bases through
explicit `supersedes`; base extension bodies self-gate via `requires`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import (
    Catalog,
    Extension,
    Implementation,
    Primitive,
    PrimitivePortability,
    RESULT_DIM_BASE,
    RESULT_DIM_EXTENSION,
)
from tslc.catalog.signatures import parse_signature
from tslc.catalog.target_families import ExtensionFamilyCapability
from tslc.diagnostics import Diagnostic
from tslc.select.candidates import (
    CandidateEvaluation,
    RANKING_KEYS,
    RankedCandidate,
    RejectedCandidate,
    _compiler_capability_frontier,
    best_bodies,
    evaluate_candidates,
    fixed_width_fallback,
)
from tslc.select.slots import (
    SelectionSlot as _SelectionSlot,
    SimdTypeBaseBinding,
    monomorphized_lanes,
    selection_slots,
    simd_type_base_binding_sets,
)
from tslc.support_policy import DEFAULT_SUPPORT_POLICY, SupportPolicy
from tslc.support_policy_views import selectable_variants


@dataclass(frozen=True, slots=True)
class SelectedImplementation:
    primitive: Primitive
    implementation: Implementation
    extension: Extension
    type_tag: str
    # The concrete target features selected for this implementation body after
    # applying extension/type-scoped `requires` clauses.
    required_features: frozenset[str] = frozenset()
    # The backend compiler capabilities selected for this body.
    required_compiler_capabilities: frozenset[str] = frozenset()
    # A non-None rank groups automatic capability-frontier winners for
    # downstream selection. Explicit selection and ordinary single winners
    # leave it unset.
    compiler_alternative_rank: int | None = None

    # For a representation-change primitive (`result_target`), the concrete target this slot
    # is monomorphized for: a target *type tag* (base dim, e.g. ``ui32``) or a target
    # *extension name* (extension dim, e.g. ``sse``). None for ordinary primitives.
    to_target: str | None = None
    # For a sized-vector body with ``unroll_variants`` effective-true, the concrete lane count
    # this slot is monomorphized at (one slot per ``size_bits`` entry; lanes = size // typebits).
    # None = the ordinary single ``LANES``-parametric slot. Lets a size-changing body emit a
    # concrete ``Generic<N>`` per size instead of a const-generic-expression template.
    concrete_lanes: int | None = None
    # Opt-in associated-base monomorphization for ``generic_params`` entries with
    # ``kind simd_type``. The public API remains generic over the SIMD type; this
    # binding gives lowering one concrete associated base case for generation-time
    # queries such as ``base::generic(IndicesType)``.
    simd_type_base_bindings: tuple[SimdTypeBaseBinding, ...] = ()
    # Concrete profile extension behind a backend's fixed-width facade. This
    # stays typed for dependency closure while the backend renders the facade.
    fixed_fallback_extension: Extension | None = None
    # The exact-width facade substrate only when its selected body is an
    # intrinsic leaf. Source-authored compiler overlays use this stronger fact
    # to prefer native hardware without mistaking a portable hardware body for
    # a native implementation.
    fixed_native_fallback_extension: Extension | None = None
    extension_family_capability: ExtensionFamilyCapability = (
        ExtensionFamilyCapability("")
    )


@dataclass(frozen=True, slots=True)
class ProfileSelectionResult:
    selected: tuple[SelectedImplementation, ...]
    diagnostics: tuple[Diagnostic, ...]
    slots: tuple["SelectionSlotResult", ...] = ()


class SelectionSlotDisposition(StrEnum):
    """Selector-owned outcome before any implementation body is lowered."""

    ABSENT = "absent"
    SELECTED = "selected"
    FIXED_SHAPE_ONLY = "fixed_shape_only"
    NOT_APPLICABLE = "not_applicable"


class SelectionSlotInapplicability(StrEnum):
    """Stable reason why an otherwise-enumerated selector axis has no slot."""

    NO_COMPATIBLE_BASE_TARGET = "TSL-SELECT-NO-COMPATIBLE-BASE-TARGET"
    NO_COMPATIBLE_EXTENSION_TARGET = (
        "TSL-SELECT-NO-COMPATIBLE-EXTENSION-TARGET"
    )
    TARGET_SPECIFIC_UNAVAILABLE = "TSL-SELECT-TARGET-SPECIFIC-UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class SelectionSlotResult:
    """One selector-owned expected slot and every realization selected for it."""

    primitive: Primitive
    extension: Extension
    type_tag: str
    to_target: str | None
    selected: tuple[SelectedImplementation, ...]
    disposition: SelectionSlotDisposition
    fixed_shape_kinds: frozenset[str] = frozenset()
    inapplicability_reason: SelectionSlotInapplicability | None = None

    def __post_init__(self) -> None:
        if bool(self.selected) != (
            self.disposition is SelectionSlotDisposition.SELECTED
        ):
            raise ValueError("selected slot disposition must match selected bodies")
        if bool(self.fixed_shape_kinds) != (
            self.disposition is SelectionSlotDisposition.FIXED_SHAPE_ONLY
        ):
            raise ValueError(
                "fixed-shape slot disposition must match fixed signature kinds"
            )
        if (self.inapplicability_reason is not None) != (
            self.disposition is SelectionSlotDisposition.NOT_APPLICABLE
        ):
            raise ValueError(
                "not-applicable slot disposition must carry exactly one reason"
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
        backend_id: str | None = None,
        compiler_capabilities: frozenset[str] | None = None,
        collect_slots: bool = False,
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
        evaluated_slots: list[SelectionSlotResult] = []
        warnings: dict[str, Diagnostic] = {}  # keyed by message, so each ambiguity warns once
        emitted_extensions = list(
            self.emitted_extensions(catalog, profile, backend_id=backend_id)
        )
        for primitive in variants:
            shape = parse_signature(primitive.signature)
            if shape is not None and self.support.shape_is_free_function(shape):
                free_selected, free_slots = self._select_free_function(
                    catalog,
                    profile,
                    primitive,
                    emitted_extensions,
                    backend_id,
                    compiler_capabilities,
                    warnings,
                    collect_slots,
                )
                selected.extend(free_selected)
                if collect_slots:
                    evaluated_slots.extend(free_slots)
                continue
            for slot in selection_slots(
                catalog,
                profile,
                primitive,
                emitted_extensions,
                type_tags,
                self.support,
            ):
                extension = catalog.extensions[slot.extension_name]
                fixed_shape_kinds = (
                    frozenset()
                    if shape is None
                    else self.support.fixed_shape_kinds_for_extension(
                        shape, extension
                    )
                )
                fixed_shape_only = bool(fixed_shape_kinds)
                slot_selected = (
                    ()
                    if fixed_shape_only or not slot.target_resolved
                    else self._select_slot(
                        catalog,
                        profile,
                        primitive,
                        slot,
                        emitted_extensions,
                        backend_id,
                        compiler_capabilities,
                        warnings,
                    )
                )
                selected.extend(slot_selected)
                if collect_slots or fixed_shape_only:
                    disposition, inapplicability = _slot_disposition(
                        primitive,
                        slot,
                        slot_selected,
                        fixed_shape_kinds,
                    )
                    evaluated_slots.append(
                        SelectionSlotResult(
                            primitive=primitive,
                            extension=extension,
                            type_tag=slot.type_tag,
                            to_target=slot.to_target,
                            selected=slot_selected,
                            disposition=disposition,
                            fixed_shape_kinds=fixed_shape_kinds,
                            inapplicability_reason=inapplicability,
                        )
                    )
        return ProfileSelectionResult(
            selected=tuple(selected),
            diagnostics=tuple(warnings.values()),
            slots=tuple(evaluated_slots),
        )

    def _select_free_function(
        self,
        catalog: Catalog,
        profile: MachineProfile,
        primitive: Primitive,
        emitted_extensions: list[str],
        backend_id: str | None,
        compiler_capabilities: frozenset[str] | None,
        warnings: dict[str, Diagnostic],
        collect_slots: bool,
    ) -> tuple[tuple[SelectedImplementation, ...], tuple[SelectionSlotResult, ...]]:
        """Select the first ISA-independent declaration owner in profile order."""

        # Free functions have no SIMD axis. Their placeholder type groups still
        # provide the concrete base used by queries such as `base::in`.
        type_tags = tuple(
            sorted(
                {
                    member
                    for implementation in primitive.implementations
                    for member in catalog.type_group_members(
                        implementation.type_group
                    )
                }
            )
        )
        authored_extensions = {
            implementation.extension
            for implementation in primitive.implementations
            if implementation.extension in emitted_extensions
        }
        # Compiler overlays live in opt-in, backend-specific headers and do not
        # own the single ISA-independent declaration.
        owner_extensions = [
            name
            for name in emitted_extensions
            if name in authored_extensions
            and catalog.target_families.extension_family(
                catalog.extensions[name].family
            ).free_function_owner
        ]
        evaluated: list[SelectionSlotResult] = []
        for slot in selection_slots(
            catalog,
            profile,
            primitive,
            owner_extensions,
            type_tags,
            self.support,
        ):
            slot_selected = (
                self._select_slot(
                    catalog,
                    profile,
                    primitive,
                    slot,
                    emitted_extensions,
                    backend_id,
                    compiler_capabilities,
                    warnings,
                )
                if slot.target_resolved
                else ()
            )
            if collect_slots:
                disposition, inapplicability = _slot_disposition(
                    primitive,
                    slot,
                    slot_selected,
                    frozenset(),
                )
                evaluated.append(
                    SelectionSlotResult(
                        primitive=primitive,
                        extension=catalog.extensions[slot.extension_name],
                        type_tag=slot.type_tag,
                        to_target=slot.to_target,
                        selected=slot_selected,
                        disposition=disposition,
                        inapplicability_reason=inapplicability,
                    )
                )
            if slot_selected:
                return slot_selected, tuple(evaluated)
        return (), tuple(evaluated)


    def _select_slot(
        self,
        catalog: Catalog,
        profile: MachineProfile,
        primitive: Primitive,
        slot: _SelectionSlot,
        emitted_extensions: list[str],
        backend_id: str | None,
        compiler_capabilities: frozenset[str] | None,
        warnings: dict[str, Diagnostic],
    ) -> tuple[SelectedImplementation, ...]:
        selected_bodies = best_bodies(
            catalog,
            profile,
            primitive,
            slot.extension_name,
            slot.type_tag,
            slot.to_target,
            backend_id,
            compiler_capabilities,
            warnings,
        )
        if not selected_bodies:
            return ()
        extension = catalog.extensions[slot.extension_name]
        fallback = (
            fixed_width_fallback(
                catalog,
                profile,
                primitive,
                extension,
                slot.type_tag,
                slot.to_target,
                emitted_extensions,
                backend_id,
                compiler_capabilities,
            )
            if backend_id is not None
            else None
        )
        native_fallback = (
            fixed_width_fallback(
                catalog,
                profile,
                primitive,
                extension,
                slot.type_tag,
                slot.to_target,
                emitted_extensions,
                backend_id,
                compiler_capabilities,
                require_native=True,
            )
            if backend_id is not None
            else None
        )
        family = catalog.target_families.extension_family(extension.family)
        return tuple(
            SelectedImplementation(
                primitive=primitive,
                implementation=best.implementation,
                extension=extension,
                type_tag=slot.type_tag,
                required_features=best.required_features,
                required_compiler_capabilities=(
                    best.required_compiler_capabilities
                ),
                compiler_alternative_rank=(
                    rank
                    if compiler_capabilities is None and len(selected_bodies) > 1
                    else None
                ),
                to_target=slot.to_target,
                concrete_lanes=lanes,
                simd_type_base_bindings=bindings,
                fixed_fallback_extension=fallback,
                fixed_native_fallback_extension=native_fallback,
                extension_family_capability=family,
            )
            for rank, best in enumerate(selected_bodies)
            for lanes in monomorphized_lanes(
                self.support,
                extension,
                best.implementation,
                slot.type_tag,
            )
            for bindings in simd_type_base_binding_sets(
                catalog, primitive, slot.type_tag
            )
        )

    def _emit_extensions(self, catalog: Catalog, profile: MachineProfile) -> list[str]:
        """Extensions to emit for a profile.

        Extension activation establishes that the profile can use the register
        substrate at all. Individual bodies then self-gate finer capabilities
        via `requires` (e.g. the avx2-tagged 256-bit *float* add needs only `avx`,
        while its 256-bit *integer* add needs `avx2`).
        Extension variants (e.g. `avx2_vl`) use `active_when` to become candidates
        and explicit `supersedes` entries to hide bases on profiles where the variant
        should replace them. Candidates with no usable body for any type drop out later
        in `_best_body`.
        """

        active: dict[str, Extension] = {}
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
            if not ext.active_when.is_satisfied_by(
                profile.features,
                profile.compile_modes,
            ):
                continue
            active[name] = ext

        superseded = {
            superseded_name
            for ext in active.values()
            for superseded_name in ext.supersedes
        }
        return sorted(name for name in active if name not in superseded)

    def emitted_extensions(
        self,
        catalog: Catalog,
        profile: MachineProfile,
        *,
        backend_id: str | None = None,
    ) -> tuple[str, ...]:
        """Profile-active extensions, optionally restricted to one backend.

        This is the public catalog/selection view used by authoring tools that
        need to display the complete extension axis, including slots for which
        no primitive implementation is selected. It deliberately stops before
        body selection and lowering.
        """

        names = self._emit_extensions(catalog, profile)
        if backend_id is not None:
            names = [
                name
                for name in names
                if catalog.extensions[name].supports_backend(backend_id)
            ]
        return tuple(names)

    def evaluate_candidates(
        self,
        catalog: Catalog,
        profile: MachineProfile,
        primitive: Primitive,
        extension_name: str,
        type_tag: str,
        to_target: str | None,
        backend_id: str | None = None,
        compiler_capabilities: frozenset[str] | None = None,
    ) -> CandidateEvaluation:
        """Return ranked and rejected candidates for one typed slot."""

        return evaluate_candidates(
            catalog,
            profile,
            primitive,
            extension_name,
            type_tag,
            to_target,
            backend_id,
            compiler_capabilities,
        )

def _slot_disposition(
    primitive: Primitive,
    slot: _SelectionSlot,
    selected: tuple[SelectedImplementation, ...],
    fixed_shape_kinds: frozenset[str],
) -> tuple[SelectionSlotDisposition, SelectionSlotInapplicability | None]:
    if not slot.target_resolved:
        assert primitive.result_target is not None
        dimension = primitive.result_target[0]
        reason = {
            RESULT_DIM_BASE: SelectionSlotInapplicability.NO_COMPATIBLE_BASE_TARGET,
            RESULT_DIM_EXTENSION: (
                SelectionSlotInapplicability.NO_COMPATIBLE_EXTENSION_TARGET
            ),
        }[dimension]
        return SelectionSlotDisposition.NOT_APPLICABLE, reason
    if fixed_shape_kinds:
        return SelectionSlotDisposition.FIXED_SHAPE_ONLY, None
    if selected:
        return SelectionSlotDisposition.SELECTED, None
    if primitive.portability is PrimitivePortability.TARGET_SPECIFIC:
        return (
            SelectionSlotDisposition.NOT_APPLICABLE,
            SelectionSlotInapplicability.TARGET_SPECIFIC_UNAVAILABLE,
        )
    return SelectionSlotDisposition.ABSENT, None
