"""Rust cfg formatting for the finalized compile-target selection plan."""

from __future__ import annotations

import json

from tslc.backend.rust_static_selection import (
    RustStaticProfileSelection,
    RustStaticSelectionPlan,
    RustTargetRequirement,
)


def rust_target_requirement_cfg(requirement: RustTargetRequirement) -> str:
    terms = [f'target_arch = {json.dumps(requirement.target_arch)}']
    terms.extend(
        f'target_feature = {json.dumps(feature)}'
        for feature in requirement.target_features
    )
    return f"all({', '.join(terms)})"


def rust_static_profile_cfg(selection: RustStaticProfileSelection) -> str:
    requirement = rust_target_requirement_cfg(selection.requirement)
    if not selection.stronger_requirements:
        return requirement
    stronger = ", ".join(
        rust_target_requirement_cfg(item)
        for item in selection.stronger_requirements
    )
    return f"all({requirement}, not(any({stronger})))"


def rust_static_fallback_cfg(plan: RustStaticSelectionPlan) -> str:
    if not plan.profiles:
        return "all()"
    hardware = ", ".join(
        rust_target_requirement_cfg(selection.requirement)
        for selection in plan.profiles
    )
    return f"not(any({hardware}))"


__all__ = (
    "rust_static_fallback_cfg",
    "rust_static_profile_cfg",
    "rust_target_requirement_cfg",
)
