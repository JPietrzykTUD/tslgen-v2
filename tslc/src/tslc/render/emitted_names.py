"""Finalize emitted wrapper names for lowered primitive groups."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from tslc.lower.lowerer import LoweredSpecialization
from tslc.support_policy import DEFAULT_SUPPORT_POLICY


def finalize_emitted_names(
    by_name: Mapping[str, tuple[LoweredSpecialization, ...]],
    immediate_split_names: frozenset[str],
) -> dict[str, tuple[LoweredSpecialization, ...]]:
    """Apply emitted-name splits that depend on the final overload set."""

    return _split_immediates(_split_masked(by_name), immediate_split_names)


def _split_masked(
    by_name: Mapping[str, tuple[LoweredSpecialization, ...]],
) -> dict[str, tuple[LoweredSpecialization, ...]]:
    """Split a name with more than one mask-policy form into emitted mask names."""

    out: dict[str, tuple[LoweredSpecialization, ...]] = {}
    for name, specs in by_name.items():
        forms = {s.mask_policy for s in specs}  # None == the unmasked form
        if len(forms) <= 1:
            out[name] = specs
            continue
        for policy in forms:
            group = tuple(s for s in specs if s.mask_policy == policy)
            if policy is None:
                out[name] = group
            else:
                renamed = f"{name}{DEFAULT_SUPPORT_POLICY.mask_suffix(policy)}"
                out[renamed] = tuple(replace(s, primitive_name=renamed) for s in group)
    return out


def _split_immediates(
    by_name: dict[str, tuple[LoweredSpecialization, ...]],
    split_names: frozenset[str],
) -> dict[str, tuple[LoweredSpecialization, ...]]:
    """Split mixed runtime/immediate overload families into `<name>` and `<name>_imm`."""

    out: dict[str, tuple[LoweredSpecialization, ...]] = {}
    for name, specs in by_name.items():
        imm = tuple(
            s for s in specs if DEFAULT_SUPPORT_POLICY.immediate_kind in s.param_kinds
        )
        runtime = tuple(
            s for s in specs if DEFAULT_SUPPORT_POLICY.immediate_kind not in s.param_kinds
        )
        if _immediate_split_base(name) in split_names and imm and runtime:
            out[name] = runtime
            out[f"{name}_imm"] = tuple(replace(s, primitive_name=f"{name}_imm") for s in imm)
        else:
            out[name] = specs
    return out


def _immediate_split_base(name: str) -> str:
    return DEFAULT_SUPPORT_POLICY.mask_split_base(name)
