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
    RESULT_DIM_BASE,
    RESULT_DIM_EXTENSION,
    Catalog,
    Extension,
    Implementation,
    Primitive,
)
from tslc.catalog.signatures import parse_signature
from tslc.diagnostics import Diagnostic


@dataclass(frozen=True, slots=True)
class SelectedImplementation:
    primitive: Primitive
    implementation: Implementation
    extension: Extension
    type_tag: str
    # For a representation-change primitive (`result_target`), the concrete target this slot
    # is monomorphized for: a target *type tag* (base dim, e.g. ``ui32``) or a target
    # *extension name* (extension dim, e.g. ``sse``). None for ordinary primitives.
    to_target: str | None = None


@dataclass(frozen=True, slots=True)
class ProfileSelectionResult:
    selected: tuple[SelectedImplementation, ...]
    diagnostics: tuple[Diagnostic, ...]


_SUPPORTED_FAMILIES = frozenset(
    {"scalar", "x86", "generic_like"}
)  # families tslc registers `simd<>` for (generic_like = the portable `generic` vector)


class Selector:
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
        #  - the MASKED variants in the **value-masking** category (vector result, no memory
        #    operand): each is a distinct callable, split to `<name>_mask`/`_maskz` at render
        #    (so a different arity / two policies like `mov`'s zero+pass_through both emit).
        #    Mask-producing comparisons (result `m`) and `load`/`store`/`gather`/`scatter`
        #    (`ptr`/`vidx`) are a deferred follow-up.
        unmasked = catalog.primitives_named(primitive_name, unmasked=True)
        masked = tuple(
            p
            for p in catalog.primitives_named(primitive_name, unmasked=False)
            if "mask" in p.attributes and _is_value_masking(p)
        )
        if unmasked:
            arity = len(unmasked[0].parameters)
            variants = tuple(p for p in unmasked if len(p.parameters) == arity) + masked
        elif masked:
            variants = masked  # masked-only (blend/mov/…): every policy is its own callable
        else:
            variants = catalog.primitives_named(primitive_name, unmasked=False)
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
            masked = "mask" in primitive.attributes
            for extension_name in self._emit_extensions(catalog, profile):
                # The generic (`<LANES>`) vector's masked body is a per-lane `mask<test>` loop
                # that isn't substrate-ready (`details::mask_test` is unimplemented; the C-style
                # `if` doesn't translate to Rust). Defer masked variants on the generic vector;
                # the SIMD (blend/mov/maskz) and scalar (if/set_zero) masked bodies are emitted.
                if masked and catalog.extensions[extension_name].family == "generic_like":
                    continue
                for type_tag in type_tags:
                    # A representation-change primitive has a SECOND axis (the target type /
                    # extension); it emits one slot per (type_tag, to_target). An ordinary
                    # primitive has a single target-less slot.
                    to_targets = self._target_candidates(
                        catalog, primitive, extension_name, type_tag
                    )
                    for to_target in to_targets:
                        best = self._best_body(
                            catalog, profile, primitive, extension_name,
                            type_tag, to_target, warnings,
                        )
                        if best is not None:
                            selected.append(
                                SelectedImplementation(
                                    primitive=primitive,
                                    implementation=best,
                                    extension=catalog.extensions[extension_name],
                                    type_tag=type_tag,
                                    to_target=to_target,
                                )
                            )
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
            if ext.family not in _SUPPORTED_FAMILIES:
                # tslc only registers scalar + x86 `simd<>`; bodies for `arm`/`generic_like`/
                # `cuda`/fpga have no backend tag. (x86 exts still self-gate via `requires`,
                # so they drop on a profile lacking the flags.) Other families are future work.
                continue
            if name in superseded:
                continue
            if ext.inherits is not None and not (ext.lscpu_flags <= profile.features):
                continue  # inactive derived extension
            emit.append(name)
        return sorted(emit)

    def _target_candidates(
        self,
        catalog: Catalog,
        primitive: Primitive,
        extension_name: str,
        type_tag: str,
    ) -> tuple[str | None, ...]:
        """The concrete second-axis targets to emit for this (extension, source type).

        An ordinary primitive yields a single ``None`` (no second axis). A
        representation-change primitive yields its in-scope targets, gathered from the
        ``to_target_group`` of the impls matching this (extension, source type):
        - **extension** dim -> target *extension* names that are registered extensions
          (the concrete `sse`/`avx2` branches; the generic `where:`-clause level is not an
          extension, so it drops — deferred).
        - **base** dim, *bit-reinterpret* (`[cast=reinterpret]`) -> same-width targets, any domain
          (signedness flips `si32↔ui32`, cross-domain `f32↔ui32`): a `bit_cast` is meaningful
          between equal-width types (a size mismatch on scalar). Different-width reinterpret is
          deferred.
        - **base** dim, *value conversion* (`cast`/`convert_up`, `[cast=convert]`) -> all targets
          (these genuinely change width/domain); their conversion-intrinsic bodies are not lowered
          yet, so they skip at the body level — discoverably, rather than vanishing here.
        """

        if primitive.result_target is None:
            return (None,)
        dim = primitive.result_target[0]
        chain = catalog.extension_chain(extension_name)
        targets: set[str] = set()
        for impl in primitive.implementations:
            if impl.extension not in chain or impl.to_target_group is None:
                continue
            if not catalog.type_group_contains(impl.type_group, type_tag):
                continue
            targets.update(catalog.type_group_members(impl.to_target_group))
        if dim == RESULT_DIM_EXTENSION:
            return tuple(sorted(t for t in targets if t in catalog.extensions))
        if dim == RESULT_DIM_BASE and primitive.attributes.get("cast") == "reinterpret":
            return tuple(sorted(t for t in targets if _same_width(t, type_tag)))
        return tuple(sorted(targets))

    def _best_body(
        self,
        catalog: Catalog,
        profile: MachineProfile,
        primitive: Primitive,
        extension_name: str,
        type_tag: str,
        to_target: str | None,
        warnings: dict[str, Diagnostic],
    ) -> Implementation | None:
        # Gather candidates from the extension and the ancestors it inherits from
        # (e.g. avx2_vl borrows avx2's body where it has none of its own).
        chain = catalog.extension_chain(extension_name)
        distance = {name: index for index, name in enumerate(chain)}
        candidates: list[tuple[Implementation, frozenset[str]]] = []
        for implementation in primitive.implementations:
            if implementation.extension not in distance:
                continue
            if not catalog.type_group_contains(implementation.type_group, type_tag):
                continue
            # Second-axis match: the body's `to_target_group` must contain the target slot.
            if to_target is not None and not (
                implementation.to_target_group is not None
                and catalog.type_group_contains(implementation.to_target_group, to_target)
            ):
                continue
            flags = _applicable_flags(catalog, implementation, type_tag)
            if flags is None or not (flags <= profile.features):
                continue
            candidates.append((implementation, flags))
        if not candidates:
            return None
        best, best_flags = min(
            candidates,
            key=lambda item: (
                distance[item[0].extension],  # own extension before inherited (a)
                catalog.type_group_specificity(item[0].type_group),  # most specific (b)
                -len(item[1]),  # most hardware flags (c)
                item[0].source_order,  # first occurrence (d)
            ),
        )
        # Ambiguity guard: warn only when the pick is genuinely *arbitrary* — two candidate
        # bodies on the same extension that tie on every principled key (a) distance,
        # (b) type-group specificity, and (c) hardware-flag count, yet are keyed to *different*
        # type-groups. Equal-size different groups are necessarily incomparable (a proper
        # subset has strictly fewer members), so neither is more type-specific; equal flag
        # counts mean hardware-specialization doesn't separate them either — so only
        # `source_order` (d) decides, which is arbitrary. A flag-count difference IS a
        # principled tiebreak (more required features = more specialized), so it does not warn.
        best_spec = catalog.type_group_specificity(best.type_group)
        rival_groups = {
            impl.type_group
            for impl, flags in candidates
            if distance[impl.extension] == distance[best.extension]
            and catalog.type_group_specificity(impl.type_group) == best_spec
            and len(flags) == len(best_flags)
            and impl.type_group != best.type_group
        }
        if rival_groups:
            groups = ", ".join(sorted({best.type_group, *rival_groups}))
            message = (
                f"{primitive.name!r} on {extension_name}: type-groups {{{groups}}} are equally "
                f"specific and incomparable (both match overlapping types); the body is chosen "
                f"by source order — disambiguate the corpus selectors"
            )
            warnings.setdefault(
                message,
                Diagnostic(
                    severity="warning",
                    code="TSL-SELECT-AMBIGUOUS-SPECIFICITY",
                    message=message,
                ),
            )
        return best
        # (a) before (b): when a derived extension is active and supersedes its base
        # (e.g. avx2_vl over avx2 on an avx512vl profile), the derived ext's OWN body
        # wins even if a base body is more type-specific — so avx512vl comparisons use
        # the `_vl` native-mask body, not the base's lane-bitmask `si?` body. Within a
        # single extension distance ties, so specificity still decides there.


def _same_width(target_tag: str, source_tag: str) -> bool:
    """Both tags have the same bit width, regardless of domain — `si32`/`ui32`/`f32` are all
    32-bit, `si64`/`ui64`/`f64` all 64-bit. This is the scope of the delivered `base`-dim
    `reinterpret`: a register no-op on x86, a valid same-size `bit_cast` on scalar. It admits
    same-width *cross-domain* targets (`f32`↔`ui32` — the bit pattern of a float read as an int
    and back, used by float shifts); different-width targets stay deferred."""

    def width(tag: str) -> int | None:
        digits = "".join(c for c in tag if c.isdigit())
        return int(digits) if digits else None

    tw, sw = width(target_tag), width(source_tag)
    return tw is not None and tw == sw


def _is_value_masking(primitive: Primitive) -> bool:
    """A masked variant in the **value-masking** category (the masked-variant slice's scope):
    its result is a vector and it has no memory operand. This admits `add`/`mul`/`binary_and`/
    `shift_left`/`mul_imm`/… (mask selects which lanes get the op) and excludes mask-*producing*
    comparisons (result `m`) and `load`/`store`/`gather`/`scatter` (`ptr`/`vidx`), which are
    deferred follow-ups."""

    shape = parse_signature(primitive.signature)
    return (
        shape is not None
        and shape.result_kind == "v"
        and "ptr" not in shape.param_kinds
        and "vidx" not in shape.param_kinds
    )


def policy_split_names(catalog: Catalog) -> frozenset[str]:
    """Names with MORE THAN ONE emitted *form* — so a `call<…attrs[mask=…]>` to them must take
    the `_mask`/`_maskz` suffix (matching the render rename). A form is the unmasked variant (if
    any) plus each value-masking mask policy. Examples: `add` (unmasked + zero + merge → 3 forms)
    and `mov` (zero + merge → 2 forms) split; `blend` (merge only → 1 form) keeps its bare name."""

    names: set[str] = set()
    for name in {primitive.name for primitive in catalog.primitives}:
        variants = catalog.primitives_named(name, unmasked=False)
        forms: set[str | None] = set()
        if any("mask" not in p.attributes for p in variants):
            forms.add(None)
        forms.update(
            p.attributes["mask"]
            for p in variants
            if "mask" in p.attributes and _is_value_masking(p)
        )
        if len(forms) > 1:
            names.add(name)
    return frozenset(names)


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
