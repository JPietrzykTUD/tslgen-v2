"""Shared target-selection rendering helpers for the ordinary Rust facade."""

from __future__ import annotations

from tslc.backend.rust_api_model import (
    RustFacadeDelegate,
    RustFacadeRepresentation,
    RustFacadeShape,
    RustNativeAliasSelection,
)
from tslc.backend.rust_static_selection import RustTargetRequirement
from tslc.render._common import slug
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
    expected_extension = (
        representation.mapping.extension_name
        or ("scalar" if shape.lanes == 1 else "generic")
    )
    matches = tuple(
        delegate
        for delegate in delegates
        if delegate.profile_name == profile_name
        and any(
            vector.extension_name == expected_extension
            and vector.type_tag == shape.type_tag
            for vector in delegate.vectors
        )
    )
    if len(matches) != 1:
        raise ValueError(
            f"Rust facade surface has {len(matches)} delegates for "
            f"{shape.type_tag}x{shape.lanes} under "
            f"{profile_name or 'fallback'}"
        )
    return matches[0]


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
    requirements = tuple(
        item
        for item in (left.requirement, right.requirement)
        if item is not None
    )
    if not requirements:
        return True
    arches = {item.target_arch for item in requirements}
    if len(arches) != 1:
        return False
    effective = RustTargetRequirement(
        requirements[0].target_arch,
        tuple(
            sorted(
                {
                    feature
                    for requirement in requirements
                    for feature in requirement.target_features
                }
            )
        ),
    )
    return not any(
        _requirement_implies(effective, exclusion)
        for exclusion in (
            *left.stronger_requirements,
            *right.stronger_requirements,
        )
    )


def lower_module(representation: RustFacadeRepresentation) -> str:
    if representation.profile_name is None:
        return "crate::tsl_target_fallback"
    return f"crate::tsl_{slug(representation.profile_name)}"


def private_vector_descriptor(representation: RustFacadeRepresentation) -> str:
    mapping = representation.mapping
    if mapping.extension_name is None:
        extension = "Scalar" if mapping.lanes == 1 else f"Generic<{mapping.lanes}>"
        return (
            f"crate::tsl_core::Simd<{mapping.base_spelling}, "
            f"crate::tsl_core::{extension}>"
        )
    if representation.profile_name is None or mapping.extension_tag_spelling is None:
        raise ValueError("Rust hardware facade mapping is missing qualified tag facts")
    return (
        f"crate::tsl_core::Simd<{mapping.base_spelling}, "
        f"crate::tsl_{slug(representation.profile_name)}::"
        f"{mapping.extension_tag_spelling}>"
    )


def selection_cfg(representation: RustFacadeRepresentation) -> str:
    if representation.requirement is None:
        return fallback_cfg(representation.stronger_requirements)
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


def cfg_attribute(cfg: str) -> str:
    return "" if cfg == "all()" else f"#[cfg({cfg})]"


def _requirement_implies(
    available: RustTargetRequirement,
    required: RustTargetRequirement,
) -> bool:
    return (
        available.target_arch == required.target_arch
        and set(required.target_features) <= set(available.target_features)
    )


__all__ = (
    "cfg_attribute",
    "combined_selection_cfg",
    "fallback_cfg",
    "lower_module",
    "native_selection_cfg",
    "private_vector_descriptor",
    "representations_can_coexist",
    "selection_cfg",
    "surface_delegate",
    "surface_delegate_for_profile",
)
