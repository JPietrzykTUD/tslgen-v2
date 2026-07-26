"""Shared target-selection rendering helpers for the ordinary Rust facade."""

from __future__ import annotations

from tslc.backend.rust_api_model import (
    RustFacadeDelegate,
    RustFacadeRepresentation,
    RustFacadeShape,
    RustNativeAliasSelection,
    rust_facade_representations_can_coexist,
)
from tslc.backend.rust_names import rust_profile_module_name
from tslc.backend.rust_static_selection import RustTargetRequirement
from tslc.render.rust_static_selection import (
    rust_target_requirement_cfg,
    rust_target_selection_cfg,
)


def surface_delegate(
    delegates: tuple[RustFacadeDelegate, ...],
    shape: RustFacadeShape,
    representation: RustFacadeRepresentation,
) -> RustFacadeDelegate:
    return surface_delegate_for_profile(
        delegates, shape, representation, representation.profile_name
    )


def surface_delegate_for_profile(
    delegates: tuple[RustFacadeDelegate, ...],
    shape: RustFacadeShape,
    representation: RustFacadeRepresentation,
    profile_name: str | None,
) -> RustFacadeDelegate:
    matches = tuple(
        delegate
        for delegate in delegates
        if delegate.profile_name == profile_name
        and _delegate_has_owner(delegate, shape, representation)
    )
    if len(matches) != 1:
        raise ValueError(
            f"Rust facade surface has {len(matches)} delegates for "
            f"{shape.type_tag}x{shape.lanes} under "
            f"{profile_name or 'fallback'}"
        )
    return matches[0]


def surface_delegate_owner(
    delegate: RustFacadeDelegate,
    shape: RustFacadeShape,
    representation: RustFacadeRepresentation,
) -> str:
    matches = tuple(
        owner.extension_name
        for owner in delegate.owners
        if owner.type_tag == shape.type_tag
        and owner.lanes == shape.lanes
        and owner.representation_profile_name == representation.profile_name
    )
    if len(matches) != 1:
        raise ValueError(
            f"Rust facade delegate {delegate.primitive_name!r} has "
            f"{len(matches)} implementation owners for "
            f"{shape.type_tag}x{shape.lanes} under "
            f"{representation.profile_name or 'fallback'}"
        )
    return matches[0]


def _delegate_has_owner(
    delegate: RustFacadeDelegate,
    shape: RustFacadeShape,
    representation: RustFacadeRepresentation,
) -> bool:
    return (
        sum(
            owner.type_tag == shape.type_tag
            and owner.lanes == shape.lanes
            and owner.representation_profile_name == representation.profile_name
            for owner in delegate.owners
        )
        == 1
    )


def combined_selection_cfg(
    left: RustFacadeRepresentation,
    right: RustFacadeRepresentation,
) -> str:
    left_cfg = selection_cfg(left)
    right_cfg = selection_cfg(right)
    if left_cfg == right_cfg:
        return left_cfg
    return f"all({left_cfg}, {right_cfg})"


def representations_can_coexist(
    left: RustFacadeRepresentation,
    right: RustFacadeRepresentation,
) -> bool:
    return rust_facade_representations_can_coexist(left, right)


def lower_module(representation: RustFacadeRepresentation) -> str:
    if representation.profile_name is None:
        return "crate::tsl_target_fallback"
    return f"crate::{rust_profile_module_name(representation.profile_name)}"


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
    "cfg_attribute",
    "combined_selection_cfg",
    "fallback_cfg",
    "fallback_selection_cfg",
    "lower_module",
    "native_selection_cfg",
    "representations_can_coexist",
    "selection_cfg",
    "surface_delegate",
    "surface_delegate_for_profile",
)
