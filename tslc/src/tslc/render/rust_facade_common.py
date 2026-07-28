"""Shared target-selection rendering helpers for the ordinary Rust facade."""

from __future__ import annotations

from tslc.backend.rust_api_arms import (
    RustFacadeArmSelection,
    RustFacadeLowerCall,
)
from tslc.backend.rust_api_model import (
    RustFacadeRepresentation,
    RustNativeAliasSelection,
)
from tslc.backend.rust_translation import rust_raw_identifier
from tslc.backend.rust_static_selection import RustTargetRequirement
from tslc.render.rust_static_selection import (
    rust_target_requirement_cfg,
    rust_target_selection_cfg,
)


def arm_selection_cfg(
    selection: RustFacadeArmSelection,
) -> str:
    cfgs = tuple(selection_cfg(item) for item in selection.representations)
    return cfgs[0] if len(set(cfgs)) == 1 else f"all({', '.join(cfgs)})"


def lower_call_expression(
    call: RustFacadeLowerCall,
    *,
    include_result_suffix: bool = True,
) -> str:
    generics = (
        f"::<{', '.join(call.generic_arguments)}>"
        if call.generic_arguments
        else ""
    )
    result_suffix = call.result_suffix if include_result_suffix else ""
    return (
        f"{call.module_spelling}::{rust_raw_identifier(call.primitive_name)}"
        f"{generics}({', '.join(call.arguments)}){result_suffix}"
    )


def selection_cfg(representation: RustFacadeRepresentation) -> str:
    if representation.requirement is None:
        return fallback_selection_cfg(representation)
    return rust_target_selection_cfg(
        representation.requirement, representation.stronger_requirements
    )


def native_selection_cfg(selection: RustNativeAliasSelection) -> str:
    if selection.requirement is None:
        return fallback_cfg(selection.stronger_requirements)
    return rust_target_selection_cfg(
        selection.requirement, selection.stronger_requirements
    )


def fallback_cfg(requirements: tuple[RustTargetRequirement, ...]) -> str:
    if not requirements:
        return "all()"
    rendered = ", ".join(
        rust_target_requirement_cfg(requirement)
        for requirement in requirements
    )
    return f"not(any({rendered}))"


def fallback_selection_cfg(representation: RustFacadeRepresentation) -> str:
    if not representation.fallback_exclusions:
        return "all()"
    rendered = ", ".join(
        rust_target_selection_cfg(
            exclusion.requirement,
            exclusion.stronger_requirements,
        )
        for exclusion in representation.fallback_exclusions
    )
    return f"not(any({rendered}))"


def cfg_attribute(cfg: str) -> str:
    return "" if cfg == "all()" else f"#[cfg({cfg})]"


__all__ = (
    "arm_selection_cfg",
    "cfg_attribute",
    "fallback_cfg",
    "fallback_selection_cfg",
    "lower_call_expression",
    "native_selection_cfg",
    "selection_cfg",
)
