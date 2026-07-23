"""Render the ordinary owned Rust types from the finalized facade plan."""

from __future__ import annotations

from tslc.backend.rust_api_model import (
    RustFacadePlan,
    RustFacadeRepresentation,
    RustNativeAlias,
    RustNativeAliasSelection,
)
from tslc.backend.rust_static_selection import RustTargetRequirement
from tslc.compiler_assets import RenderAssets
from tslc.render._common import slug
from tslc.render.rust_static_selection import (
    rust_target_requirement_cfg,
    rust_target_selection_cfg,
)


def rust_facade_module(plan: RustFacadePlan, assets: RenderAssets) -> str:
    """Render opaque logical values without reopening lowered specializations."""

    return assets.fill(
        "rust_facade.rs.tmpl",
        representation_impls=_representation_impls(plan),
        element_impls=_element_impls(plan),
    )


def _representation_impls(plan: RustFacadePlan) -> str:
    blocks = []
    for shape in plan.shapes:
        for representation in shape.representations:
            descriptor = _private_vector_descriptor(representation)
            blocks.append(
                "\n".join(
                    (
                        f"#[cfg({_selection_cfg(representation)})]",
                        f"impl private::Representation<{shape.lanes}> "
                        f"for {shape.base_spelling} {{",
                        "    type Vector = "
                        f"<{descriptor} as crate::tsl_core::SimdVector>::RegisterType;",
                        "    type Mask = "
                        f"<{descriptor} as crate::tsl_core::SimdVector>::MaskType;",
                        "}",
                    )
                )
            )
    return "\n\n".join(blocks)


def _element_impls(plan: RustFacadePlan) -> str:
    blocks = []
    for alias in plan.native_aliases:
        for selection in alias.selections:
            blocks.append(_element_impl(alias, selection))
    return "\n\n".join(blocks)


def _element_impl(
    alias: RustNativeAlias,
    selection: RustNativeAliasSelection,
) -> str:
    cfg = _native_selection_cfg(selection)
    vector = f"Simd<{alias.base_spelling}, {selection.lanes}>"
    mask = f"Mask<{alias.base_spelling}, {selection.lanes}>"
    return "\n".join(
        (
            f"#[cfg({cfg})]",
            f"impl private::SealedElement for {alias.base_spelling} {{}}",
            f"#[cfg({cfg})]",
            f"impl SimdElement for {alias.base_spelling} {{",
            f"    type NativeSimd = {vector};",
            f"    type NativeMask = {mask};",
            "}",
        )
    )


def _private_vector_descriptor(representation: RustFacadeRepresentation) -> str:
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


def _selection_cfg(representation: RustFacadeRepresentation) -> str:
    if representation.requirement is None:
        return _fallback_cfg(representation.stronger_requirements)
    return rust_target_selection_cfg(
        representation.requirement, representation.stronger_requirements
    )


def _native_selection_cfg(selection: RustNativeAliasSelection) -> str:
    if selection.requirement is None:
        return _fallback_cfg(selection.stronger_requirements)
    return rust_target_selection_cfg(
        selection.requirement, selection.stronger_requirements
    )


def _fallback_cfg(requirements: tuple[RustTargetRequirement, ...]) -> str:
    if not requirements:
        return "all()"
    rendered = ", ".join(
        rust_target_requirement_cfg(requirement)
        for requirement in requirements
    )
    return f"not(any({rendered}))"


__all__ = ("rust_facade_module",)
