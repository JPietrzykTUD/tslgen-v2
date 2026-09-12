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
    return rust_target_selection_cfg(
        selection.requirement, selection.higher_priority_requirements
    )


def rust_target_selection_cfg(
    requirement: RustTargetRequirement,
    higher_priority_requirements: tuple[RustTargetRequirement, ...],
) -> str:
    rendered_requirement = rust_target_requirement_cfg(requirement)
    if not higher_priority_requirements:
        return rendered_requirement
    higher_priority = ", ".join(
        rust_target_requirement_cfg(item)
        for item in higher_priority_requirements
    )
    return f"all({rendered_requirement}, not(any({higher_priority})))"


def rust_static_fallback_cfg(plan: RustStaticSelectionPlan) -> str:
    if not plan.profiles:
        return "all()"
    hardware = ", ".join(
        rust_target_requirement_cfg(selection.requirement)
        for selection in plan.profiles
    )
    return f"not(any({hardware}))"


def rust_cfg_all(*terms: str) -> str:
    """Join cfg predicates without emitting redundant ``all()`` children."""

    effective = tuple(term for term in terms if term != "all()")
    if not effective:
        return "all()"
    if len(effective) == 1:
        return effective[0]
    return f"all({', '.join(effective)})"


__all__ = (
    "rust_cfg_all",
    "rust_static_fallback_cfg",
    "rust_static_profile_cfg",
    "rust_target_selection_cfg",
    "rust_target_requirement_cfg",
)
