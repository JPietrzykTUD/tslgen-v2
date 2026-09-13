"""Plan deterministic extension, type, target, and monomorphization slots."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from itertools import product
from typing import assert_never

from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import (
    BaseWidthRelation,
    Catalog,
    Extension,
    GenericParam,
    Implementation,
    Primitive,
)
from tslc.catalog.scalar_types import scalar_bit_width
from tslc.support_policy import SupportPolicy
from tslc.support_policy_views import concrete_target_candidates


@dataclass(frozen=True, slots=True)
class SimdTypeBaseBinding:
    """A selected associated-base case for a free SIMD type parameter."""

    param_name: str
    base_tag: str


@dataclass(frozen=True, slots=True)
class SelectionSlot:
    extension_name: str
    type_tag: str
    to_target: str | None
    target_resolved: bool = True


def selection_slots(
    catalog: Catalog,
    profile: MachineProfile,
    primitive: Primitive,
    extension_names: list[str],
    type_tags: tuple[str, ...],
    support: SupportPolicy,
) -> Iterator[SelectionSlot]:
    """Enumerate the literal extension/type/representation target axis."""

    for extension_name in extension_names:
        for type_tag in type_tags:
            if not any(
                catalog.type_group_contains(
                    implementation.type_group, type_tag
                )
                for implementation in primitive.implementations
            ):
                continue
            targets = concrete_target_candidates(
                catalog,
                primitive,
                extension_name,
                type_tag,
                support,
                profile=profile,
            )
            for to_target in targets:
                yield SelectionSlot(extension_name, type_tag, to_target)
            if primitive.result_target is not None and not targets:
                yield SelectionSlot(
                    extension_name,
                    type_tag,
                    None,
                    target_resolved=False,
                )


def monomorphized_lanes(
    support: SupportPolicy,
    extension: Extension,
    implementation: Implementation,
    type_tag: str,
) -> tuple[int | None, ...]:
    """The concrete lane counts to monomorphize this body at, or ``(None,)`` for the
    ordinary single ``LANES``-parametric slot.

    A sized-vector body with ``unroll_variants`` effective-true and a non-empty
    ``size_bits`` emits one slot per size, lanes = size // type-bit-width — so a
    size-changing body is concrete per size (stable Rust can spell the changed-width
    output) rather than a const-generic-expression template. Everything else (fixed-width
    extensions, non-unrolled sized bodies) keeps the single ``None`` slot, byte-identical
    to before."""

    if not support.uses_sized_vector(extension) or not extension.size_bits:
        return (None,)
    unroll = (
        implementation.unroll_variants
        if implementation.unroll_variants is not None
        else extension.unroll_variants
    )
    if not unroll:
        return (None,)
    type_bits = support.type_bit_width_or_default(type_tag)
    return tuple(
        size // type_bits for size in extension.size_bits if size >= type_bits
    )


def simd_type_base_binding_sets(
    catalog: Catalog, primitive: Primitive, type_tag: str
) -> tuple[tuple[SimdTypeBaseBinding, ...], ...]:
    params = tuple(
        generic_param
        for generic_param in primitive.generic_params
        if generic_param.kind == "simd_type" and generic_param.specialize_base
    )
    if not params:
        return ((),)

    choices: list[tuple[SimdTypeBaseBinding, ...]] = []
    for param in params:
        base_tags = tuple(
            base_tag
            for base_tag in _concrete_base_tags(catalog, param.base_type_constraints)
            if _base_width_constraints_match(param, base_tag, type_tag)
        )
        if not base_tags:
            return ()
        choices.append(
            tuple(
                SimdTypeBaseBinding(param.name, base_tag)
                for base_tag in base_tags
            )
        )
    return tuple(
        tuple(item for item in combination) for combination in product(*choices)
    )


def _concrete_base_tags(
    catalog: Catalog, constraints: tuple[str, ...]
) -> tuple[str, ...]:
    seen: set[str] = set()
    members: list[str] = []
    for constraint in constraints:
        for member in catalog.type_group_members(constraint):
            if member in seen:
                continue
            seen.add(member)
            members.append(member)
    return tuple(members)


def _base_width_constraints_match(
    param: GenericParam,
    base_tag: str,
    type_tag: str,
) -> bool:
    if not param.base_width_constraints:
        return True
    base_width = scalar_bit_width(base_tag)
    input_width = scalar_bit_width(type_tag)
    if base_width is None or input_width is None:
        return False
    return all(
        _compare_widths(base_width, constraint.relation, input_width)
        for constraint in param.base_width_constraints
    )


def _compare_widths(left: int, relation: BaseWidthRelation, right: int) -> bool:
    """Exhaustive over BaseWidthRelation: catalog promotion diagnoses unknown
    relations, so an unhandled member here is a programming error, not a
    silently-empty selection."""

    if relation == ">=":
        return left >= right
    if relation == ">":
        return left > right
    if relation == "==":
        return left == right
    assert_never(relation)


__all__ = (
    "SelectionSlot",
    "SimdTypeBaseBinding",
    "monomorphized_lanes",
    "selection_slots",
    "simd_type_base_binding_sets",
)
