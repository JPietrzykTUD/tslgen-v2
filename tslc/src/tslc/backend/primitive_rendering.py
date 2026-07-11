"""Backend-neutral facts used while rendering lowered primitives."""

from __future__ import annotations

from collections.abc import Sequence

from tslc.documentation import parameter_summary
from tslc.lower.lowerer import LoweredSpecialization
from tslc.support_policy import DEFAULT_SUPPORT_POLICY
from tslc.target_text import LoweredBody


def variant_names(specializations: Sequence[LoweredSpecialization]) -> tuple[str, ...]:
    """Return variant names once, preserving lowering order."""

    names: list[str] = []
    seen: set[str] = set()
    for spec in specializations:
        for variant in spec.variant_bodies:
            if variant.name in seen:
                continue
            seen.add(variant.name)
            names.append(variant.name)
    return tuple(names)


def body_for(
    spec: LoweredSpecialization,
    variant_name: str | None,
) -> LoweredBody | None:
    """Select the default or named lowered body from one specialization."""

    if variant_name is None:
        return spec.body
    for variant in spec.variant_bodies:
        if variant.name == variant_name:
            return variant.body
    return None


def runtime_parameter_summary(spec: LoweredSpecialization) -> str:
    """Document runtime parameters, excluding compile-time immediates."""

    params = tuple(
        (name, kind)
        for name, kind in zip(spec.param_names, spec.param_kinds)
        if kind != DEFAULT_SUPPORT_POLICY.immediate_kind
    )
    return parameter_summary(
        tuple(name for name, _kind in params),
        tuple(kind for _name, kind in params),
    )

