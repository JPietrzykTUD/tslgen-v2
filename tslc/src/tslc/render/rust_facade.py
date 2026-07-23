"""Render the ordinary owned Rust types from the finalized facade plan."""

from __future__ import annotations

from tslc.backend.rust_api_model import (
    RustFacadeCoreDelegate,
    RustFacadePlan,
    RustFacadeRepresentation,
    RustFacadeShape,
    RustNativeAlias,
    RustNativeAliasSelection,
)
from tslc.backend.rust_api_planner import RUST_FACADE_CORE_OPERATION_REQUIREMENTS
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
        facade_impls=_facade_impls(plan),
        element_impls=_element_impls(plan),
        array_from_impls=_array_from_impls(plan),
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


def _facade_impls(plan: RustFacadePlan) -> str:
    blocks: list[str] = []
    for shape in plan.shapes:
        for representation in shape.representations:
            blocks.append(_facade_impl(plan, shape, representation))
    return "\n\n".join(blocks)


def _facade_impl(
    plan: RustFacadePlan,
    shape: RustFacadeShape,
    representation: RustFacadeRepresentation,
) -> str:
    descriptor = _private_vector_descriptor(representation)
    module = _lower_module(representation)
    delegates = {
        requirement.role: _core_delegate(plan, shape, representation, requirement.role)
        for requirement in RUST_FACADE_CORE_OPERATION_REQUIREMENTS
    }

    def call(name: str) -> str:
        return f"{module}::{delegates[name].source_primitive_name}"

    return "\n".join(
        (
            f"#[cfg({_selection_cfg(representation)})]",
            f"impl private::FacadeOps<{shape.lanes}> for {shape.base_spelling} {{",
            "    #[inline]",
            "    fn vector_splat(value: Self) -> Self::Vector {",
            f"        {call('vector_splat')}::<{descriptor}>(value)",
            "    }",
            "",
            "    #[inline]",
            f"    fn vector_from_array(values: [Self; {shape.lanes}]) -> Self::Vector {{",
            "        let values = crate::tsl_core::ArrayStorage::from_array(values);",
            f"        {call('vector_from_array')}::<{descriptor}>(&values)",
            "    }",
            "",
            "    #[inline]",
            f"    fn vector_to_array(value: Self::Vector) -> [Self; {shape.lanes}] {{",
            f"        {call('vector_to_array')}::<{descriptor}>(value).into_array()",
            "    }",
            "",
            "    #[inline]",
            "    fn vector_zero() -> Self::Vector {",
            f"        {call('vector_zero')}::<{descriptor}>()",
            "    }",
            "",
            "    #[inline]",
            "    fn extract_lane(value: Self::Vector, index: usize) -> Self {",
            f"        {call('extract_lane')}::<{descriptor}>(value, index)",
            "    }",
            "",
            "    #[inline]",
            (
                "    fn insert_lane(value: Self::Vector, index: usize, "
                "lane: Self) -> Self::Vector {"
            ),
            f"        {call('insert_lane')}::<{descriptor}>(value, index, lane)",
            "    }",
            "",
            "    #[inline]",
            "    unsafe fn load(source: *const Self) -> Self::Vector {",
            "        // SAFETY: forwarded from the private facade boundary.",
            f"        unsafe {{ {call('load')}::<{descriptor}, false>(source) }}",
            "    }",
            "",
            "    #[inline]",
            "    unsafe fn store(destination: *mut Self, value: Self::Vector) {",
            "        // SAFETY: forwarded from the private facade boundary.",
            f"        unsafe {{ {call('store')}::<{descriptor}, false, _>(destination, value) }}",
            "    }",
            "",
            "    #[inline]",
            "    fn mask_false() -> Self::Mask {",
            f"        {call('mask_false')}::<{descriptor}>()",
            "    }",
            "",
            "    #[inline]",
            "    fn mask_true() -> Self::Mask {",
            f"        {call('mask_true')}::<{descriptor}>()",
            "    }",
            "",
            "    #[inline]",
            "    fn mask_from_bitmask(bits: u64) -> Self::Mask {",
            (
                f"        {call('mask_from_integral')}::<{descriptor}>"
                f"(bits as {representation.mapping.imask_spelling})"
            ),
            "    }",
            "",
            "    #[inline]",
            "    fn mask_to_bitmask(value: Self::Mask) -> u64 {",
            (
                f"        {call('mask_to_integral')}::<{descriptor}>(value)"
                " as u64"
            ),
            "    }",
            "",
            "    #[inline]",
            "    fn mask_test(value: Self::Mask, index: usize) -> bool {",
            f"        let bits = {call('mask_to_integral')}::<{descriptor}>(value);",
            f"        {call('integral_mask_test')}::<{descriptor}>(bits, index) != 0",
            "    }",
            "",
            "    #[inline]",
            "    fn mask_set(value: Self::Mask, index: usize, active: bool) -> Self::Mask {",
            f"        {call('mask_set_lane')}::<{descriptor}>(",
            "            value,",
            "            index,",
            "            if active { 1 } else { 0 },",
            "        )",
            "    }",
            "",
            "    #[inline]",
            "    fn mask_count(value: Self::Mask) -> usize {",
            f"        {call('mask_population_count')}::<{descriptor}>(value)",
            "    }",
            "",
            "    #[inline]",
            "    fn mask_and(left: Self::Mask, right: Self::Mask) -> Self::Mask {",
            f"        {call('mask_and')}::<{descriptor}>(left, right)",
            "    }",
            "",
            "    #[inline]",
            "    fn mask_or(left: Self::Mask, right: Self::Mask) -> Self::Mask {",
            f"        {call('mask_or')}::<{descriptor}>(left, right)",
            "    }",
            "",
            "    #[inline]",
            "    fn mask_xor(left: Self::Mask, right: Self::Mask) -> Self::Mask {",
            f"        {call('mask_xor')}::<{descriptor}>(left, right)",
            "    }",
            "",
            "    #[inline]",
            "    fn mask_not(value: Self::Mask) -> Self::Mask {",
            f"        {call('mask_not')}::<{descriptor}>(value)",
            "    }",
            "}",
        )
    )


def _core_delegate(
    plan: RustFacadePlan,
    shape: RustFacadeShape,
    representation: RustFacadeRepresentation,
    role: str,
) -> RustFacadeCoreDelegate:
    matches = tuple(
        delegate
        for delegate in plan.core_delegates
        if delegate.role == role
        and delegate.type_tag == shape.type_tag
        and delegate.lanes == shape.lanes
        and delegate.profile_name == representation.profile_name
    )
    if len(matches) != 1:
        raise ValueError(
            f"Rust facade role {role!r} has {len(matches)} finalized delegates "
            f"for {shape.type_tag}x{shape.lanes} "
            f"under {representation.profile_name or 'fallback'}"
        )
    return matches[0]


def _array_from_impls(plan: RustFacadePlan) -> str:
    blocks: list[str] = []
    for shape in plan.shapes:
        vector = f"Simd<{shape.base_spelling}, {shape.lanes}>"
        array = f"[{shape.base_spelling}; {shape.lanes}]"
        mask = f"Mask<{shape.base_spelling}, {shape.lanes}>"
        mask_array = f"[bool; {shape.lanes}]"
        blocks.extend(
            (
                "\n".join(
                    (
                        f"impl From<{vector}> for {array} {{",
                        "    #[inline]",
                        f"    fn from(value: {vector}) -> Self {{",
                        "        value.to_array()",
                        "    }",
                        "}",
                    )
                ),
                "\n".join(
                    (
                        f"impl From<{mask}> for {mask_array} {{",
                        "    #[inline]",
                        f"    fn from(value: {mask}) -> Self {{",
                        "        value.to_array()",
                        "    }",
                        "}",
                    )
                ),
            )
        )
    return "\n\n".join(blocks)


def _lower_module(representation: RustFacadeRepresentation) -> str:
    if representation.profile_name is None:
        return "crate::tsl_target_fallback"
    return f"crate::tsl_{slug(representation.profile_name)}"


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
