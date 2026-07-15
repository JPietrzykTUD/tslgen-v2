"""Finalize target-visible names after the emitted overload set is known."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import TYPE_CHECKING

from tslc.support_policy import DEFAULT_SUPPORT_POLICY

if TYPE_CHECKING:
    from tslc.lower.lowerer import LoweredSpecialization


def finalize_emitted_names(
    by_name: Mapping[str, tuple[LoweredSpecialization, ...]],
    immediate_split_names: frozenset[str],
) -> dict[str, tuple[LoweredSpecialization, ...]]:
    """Apply emitted-name splits that depend on the final overload set."""

    return _split_immediates(
        _split_explicit_mask_args(_split_masked(by_name)),
        immediate_split_names,
    )


def _split_masked(
    by_name: Mapping[str, tuple[LoweredSpecialization, ...]],
) -> dict[str, tuple[LoweredSpecialization, ...]]:
    out: dict[str, tuple[LoweredSpecialization, ...]] = {}
    for name, specs in by_name.items():
        forms = {spec.mask_policy for spec in specs}
        if len(forms) <= 1:
            out[name] = specs
            continue
        for policy in forms:
            group = tuple(spec for spec in specs if spec.mask_policy == policy)
            if policy is None:
                out[name] = group
            else:
                renamed = f"{name}{DEFAULT_SUPPORT_POLICY.mask_suffix(policy)}"
                out[renamed] = tuple(
                    replace(spec, primitive_name=renamed) for spec in group
                )
    return out


def _split_immediates(
    by_name: dict[str, tuple[LoweredSpecialization, ...]],
    split_names: frozenset[str],
) -> dict[str, tuple[LoweredSpecialization, ...]]:
    out: dict[str, tuple[LoweredSpecialization, ...]] = {}
    immediate_kind = DEFAULT_SUPPORT_POLICY.immediate_kind
    for name, specs in by_name.items():
        imm = tuple(
            spec
            for spec in specs
            if immediate_kind in spec.param_kinds
        )
        runtime = tuple(
            spec
            for spec in specs
            if immediate_kind not in spec.param_kinds
        )
        if _immediate_split_base(name) in split_names and imm and runtime:
            out[name] = runtime
            out[f"{name}_imm"] = tuple(
                replace(spec, primitive_name=f"{name}_imm") for spec in imm
            )
        else:
            out[name] = specs
    return out


def _split_explicit_mask_args(
    by_name: dict[str, tuple[LoweredSpecialization, ...]],
) -> dict[str, tuple[LoweredSpecialization, ...]]:
    """Name a different-arity leading-mask overload ``*_mask``.

    C++ could overload ``hadd(vec)`` and ``hadd(mask, vec)``, but Rust cannot.
    Mask-policy forms already split before this function; this handles the
    policy-less active-lane reductions using the same public suffix.
    """

    out: dict[str, tuple[LoweredSpecialization, ...]] = {}
    for name, specs in by_name.items():
        arities = {len(spec.param_kinds) for spec in specs}
        leading_mask = tuple(
            spec for spec in specs if spec.param_kinds and spec.param_kinds[0] == "m"
        )
        other = tuple(spec for spec in specs if spec not in leading_mask)
        if len(arities) <= 1 or not leading_mask or not other:
            out[name] = specs
            continue
        out[name] = other
        renamed = f"{name}_mask"
        out[renamed] = tuple(
            replace(spec, primitive_name=renamed) for spec in leading_mask
        )
    return out


def _immediate_split_base(name: str) -> str:
    return DEFAULT_SUPPORT_POLICY.mask_split_base(name)


__all__ = ("finalize_emitted_names",)
