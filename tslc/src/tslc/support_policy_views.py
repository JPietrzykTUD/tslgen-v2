"""Catalog-derived views over the central support policy.

``SupportPolicy`` owns facts and predicates over already-typed values. This
module owns deterministic catalog scans that need those policy predicates.
Keeping the scans here prevents the policy object from growing into a catalog
query facade.
"""

from __future__ import annotations

from tslc.catalog.model import (
    RESULT_DIM_BASE,
    RESULT_DIM_EXTENSION,
    RESULT_DIM_VECTOR,
    Catalog,
    Primitive,
    PrimitiveCastMode,
)
from tslc.catalog.signatures import parse_signature
from tslc.support_policy import DEFAULT_SUPPORT_POLICY, SupportPolicy


def is_maskable_primitive(
    primitive: Primitive,
    support: SupportPolicy = DEFAULT_SUPPORT_POLICY,
) -> bool:
    shape = parse_signature(primitive.signature)
    return shape is not None and support.is_maskable_signature(shape)


def selectable_variants(
    catalog: Catalog,
    primitive_name: str,
    support: SupportPolicy = DEFAULT_SUPPORT_POLICY,
) -> tuple[Primitive, ...]:
    """Primitive declarations for the currently emitted callable family."""

    unmasked = catalog.primitives_named(primitive_name, unmasked=True)
    masked = tuple(
        primitive
        for primitive in catalog.primitives_named(primitive_name, unmasked=False)
        if "mask" in primitive.attributes
        and is_maskable_primitive(primitive, support)
    )
    if unmasked:
        return unmasked + masked
    if masked:
        return masked
    return catalog.primitives_named(primitive_name, unmasked=False)


def policy_split_names(
    catalog: Catalog,
    support: SupportPolicy = DEFAULT_SUPPORT_POLICY,
) -> frozenset[str]:
    """Names with more than one emitted mask-policy form."""

    names: set[str] = set()
    for name in {primitive.name for primitive in catalog.primitives}:
        variants = catalog.primitives_named(name, unmasked=False)
        forms: set[str | None] = set()
        if any("mask" not in p.attributes for p in variants):
            forms.add(None)
        forms.update(
            p.attributes["mask"]
            for p in variants
            if "mask" in p.attributes and is_maskable_primitive(p, support)
        )
        if len(forms) > 1:
            names.add(name)
    return frozenset(names)


def immediate_split_names(
    catalog: Catalog,
    support: SupportPolicy = DEFAULT_SUPPORT_POLICY,
) -> frozenset[str]:
    """Names whose callable family mixes compile-time and runtime operands."""

    names: set[str] = set()
    for name in {primitive.name for primitive in catalog.primitives}:
        has_immediate = False
        has_runtime = False
        for primitive in catalog.primitives_named(name, unmasked=False):
            shape = parse_signature(primitive.signature)
            if shape is None:
                continue
            if support.has_immediate_operand(shape):
                has_immediate = True
            else:
                has_runtime = True
        if has_immediate and has_runtime:
            names.add(name)
    return frozenset(names)


def concrete_target_candidates(
    catalog: Catalog,
    primitive: Primitive,
    extension_name: str,
    type_tag: str,
    support: SupportPolicy = DEFAULT_SUPPORT_POLICY,
) -> tuple[str | None, ...]:
    """The currently emit-ready second-axis targets for one source slot."""

    if primitive.result_target is None:
        return (None,)
    dim = primitive.result_target[0]
    if dim == RESULT_DIM_VECTOR:
        return (None,)
    chain = catalog.extension_chain(extension_name)
    # If this extension has no target-bearing body of its own for the source type — only a
    # target-generic catch-all (a body with no `ToBase`/`ToExtension` level, which spells the
    # target symbolically and works for ANY target, e.g. the generic vector's software
    # `convert_*` loop) — it draws the primitive's GLOBAL target set (the targets declared by the
    # other bodies). Extensions that declare their own targets keep exactly their chain's set.
    has_chain_target = any(
        impl.extension in chain
        and impl.to_target_group is not None
        and catalog.type_group_contains(impl.type_group, type_tag)
        for impl in primitive.implementations
    )
    has_unconstrained_catch_all = not has_chain_target and any(
        impl.extension in chain
        and impl.to_target_group is None
        and impl.target_constraint is None
        and catalog.type_group_contains(impl.type_group, type_tag)
        for impl in primitive.implementations
    )
    targets: set[str] = set()
    for implementation in primitive.implementations:
        if implementation.to_target_group is None:
            continue
        if not (has_unconstrained_catch_all or implementation.extension in chain):
            continue
        if not catalog.type_group_contains(implementation.type_group, type_tag):
            continue
        for member in catalog.type_group_members(implementation.to_target_group):
            if member.strip('"') not in support.target_marker_values:
                targets.add(member)
    if dim == RESULT_DIM_EXTENSION:
        source_extension = catalog.extensions.get(extension_name)
        if source_extension is not None:
            constraints = (
                implementation.target_constraint
                for implementation in primitive.implementations
                if implementation.extension in chain
                and implementation.target_constraint is not None
                and catalog.type_group_contains(implementation.type_group, type_tag)
            )
            for constraint in constraints:
                assert constraint is not None
                targets.update(
                    candidate_name
                    for candidate_name, candidate in catalog.extensions.items()
                    # Activation variants such as ``sse_vl`` share their public
                    # ISA identity with the canonical ``sse`` target. A
                    # representation target is keyed by that public identity,
                    # so admitting both would emit duplicate backend impls.
                    if candidate_name == candidate.isa_name
                    if constraint.matches(source_extension, candidate)
                )
        return tuple(sorted(t for t in targets if t in catalog.extensions))
    if (
        dim == RESULT_DIM_BASE
        and primitive.cast_mode is PrimitiveCastMode.REINTERPRET
    ):
        extension = catalog.extensions.get(extension_name)
        # Scalar and lane-count-parametric vectors preserve their lane count
        # when rebased, so a different scalar width would change total
        # storage and cannot be a bit reinterpretation. Fixed/scalable
        # register extensions preserve register width instead; rebasing them
        # legitimately regroups the same bits into a different lane width.
        if (
            extension is None
            or extension.vector_bits <= 0
            or support.uses_sized_vector(extension)
        ):
            targets = {
                target
                for target in targets
                if support.same_type_width(target, type_tag)
            }
    return tuple(sorted(targets))


__all__ = (
    "concrete_target_candidates",
    "immediate_split_names",
    "is_maskable_primitive",
    "policy_split_names",
    "selectable_variants",
)
