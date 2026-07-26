"""Render the ordinary owned Rust types from the finalized facade plan."""

from __future__ import annotations

from tslc.backend.rust_api_arms import (
    RustCuratedMethodImplementationArm,
    RustCuratedMethodKind,
    RustFacadeAssignmentOperatorArm,
    RustFacadeBitConversionDirection,
    RustFacadeBitConversionImplementationArm,
    RustFacadeCanonicalOperatorArm,
    RustFacadeConversionImplementationArm,
    RustFacadeCoreImplementationArm,
    RustFacadeEqualityImplementation,
    RustFacadeForwardingOperatorArm,
    RustFacadeOperatorImplementation,
)
from tslc.backend.rust_api_model import (
    RustCuratedMethod,
    RustFacadePlan,
    RustFacadeRepresentation,
    RustFacadeReceiverKind,
    RustFacadeShape,
    RustNativeAlias,
    RustNativeAliasSelection,
)
from tslc.compiler_assets import RenderAssets
from tslc.render.rust_facade_common import (
    arm_selection_cfg as _arm_selection_cfg,
    cfg_attribute as _cfg_attribute,
    lower_call_expression as _lower_call_expression,
    native_selection_cfg as _native_selection_cfg,
    selection_cfg as _selection_cfg,
)
from tslc.render.rust_facade_comprehensive import render_comprehensive_facade


def rust_facade_module(plan: RustFacadePlan, assets: RenderAssets) -> str:
    """Render opaque logical values without reopening lowered specializations."""

    comprehensive = render_comprehensive_facade(plan)
    return assets.fill(
        "rust_facade.rs.tmpl",
        comprehensive_private_traits=comprehensive.private_traits,
        comprehensive_private_impls=comprehensive.private_impls,
        comprehensive_items=comprehensive.public_items,
        representation_impls=_representation_impls(plan),
        facade_impls=_facade_impls(plan),
        conversion_pair_impls=_conversion_pair_impls(plan),
        conversion_methods=_conversion_methods(plan),
        element_impls=_element_impls(plan),
        array_from_impls=_array_from_impls(plan),
        curated_impls=_curated_impls(plan),
        operator_impls=_operator_impls(plan),
        bit_conversion_impls=_bit_conversion_impls(plan),
    )


def _representation_impls(plan: RustFacadePlan) -> str:
    blocks = []
    for shape in plan.shapes:
        for representation in shape.representations:
            descriptor = representation.vector_descriptor
            blocks.append(
                "\n".join(
                    (
                        _cfg_attribute(_selection_cfg(representation)),
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
            _cfg_attribute(cfg),
            f"impl private::SealedElement for {alias.base_spelling} {{}}",
            _cfg_attribute(cfg),
            f"impl SimdElement for {alias.base_spelling} {{",
            f"    type NativeSimd = {vector};",
            f"    type NativeMask = {mask};",
            "}",
        )
    )


def _facade_impls(plan: RustFacadePlan) -> str:
    return "\n\n".join(
        _facade_impl(arm) for arm in plan.core_implementation_arms
    )


def _facade_impl(
    arm: RustFacadeCoreImplementationArm,
) -> str:
    shape = arm.shape
    calls = {item.role: item.call for item in arm.calls}

    def invoke(name: str) -> str:
        return _lower_call_expression(calls[name])

    return "\n".join(
        (
            _cfg_attribute(_arm_selection_cfg(arm.selection)),
            f"impl private::FacadeOps<{shape.lanes}> for {shape.base_spelling} {{",
            "    #[inline]",
            "    fn vector_splat(value: Self) -> Self::Vector {",
            f"        {invoke('vector_splat')}",
            "    }",
            "",
            "    #[inline]",
            f"    fn vector_from_array(values: [Self; {shape.lanes}]) -> Self::Vector {{",
            "        let values = crate::tsl_core::ArrayStorage::from_array(values);",
            f"        {invoke('vector_from_array')}",
            "    }",
            "",
            "    #[inline]",
            f"    fn vector_to_array(value: Self::Vector) -> [Self; {shape.lanes}] {{",
            f"        {invoke('vector_to_array')}.into_array()",
            "    }",
            "",
            "    #[inline]",
            "    fn vector_zero() -> Self::Vector {",
            f"        {invoke('vector_zero')}",
            "    }",
            "",
            "    #[inline]",
            "    fn extract_lane(value: Self::Vector, index: usize) -> Self {",
            f"        {invoke('extract_lane')}",
            "    }",
            "",
            "    #[inline]",
            (
                "    fn insert_lane(value: Self::Vector, index: usize, "
                "lane: Self) -> Self::Vector {"
            ),
            f"        {invoke('insert_lane')}",
            "    }",
            "",
            "    #[inline]",
            "    unsafe fn load(source: *const Self) -> Self::Vector {",
            "        // SAFETY: forwarded from the private facade boundary.",
            f"        unsafe {{ {invoke('load')} }}",
            "    }",
            "",
            "    #[inline]",
            "    unsafe fn store(destination: *mut Self, value: Self::Vector) {",
            "        // SAFETY: forwarded from the private facade boundary.",
            (
                "        unsafe { "
                f"{invoke('store')}"
                " }"
            ),
            "    }",
            "",
            "    #[inline]",
            "    fn mask_false() -> Self::Mask {",
            f"        {invoke('mask_false')}",
            "    }",
            "",
            "    #[inline]",
            "    fn mask_true() -> Self::Mask {",
            f"        {invoke('mask_true')}",
            "    }",
            "",
            "    #[inline]",
            "    fn mask_from_bitmask(bits: u64) -> Self::Mask {",
            f"        {invoke('mask_from_bitmask')}",
            "    }",
            "",
            "    #[inline]",
            "    fn mask_to_bitmask(value: Self::Mask) -> u64 {",
            f"        {invoke('mask_to_bitmask')}",
            "    }",
            "",
            "    #[inline]",
            "    fn mask_test(value: Self::Mask, index: usize) -> bool {",
            (
                "        let bits = "
                f"{invoke('mask_to_integral_for_test')};"
            ),
            f"        {invoke('integral_mask_test')} != 0",
            "    }",
            "",
            "    #[inline]",
            "    fn mask_set(value: Self::Mask, index: usize, active: bool) -> Self::Mask {",
            f"        {invoke('mask_set_lane')}",
            "    }",
            "",
            "    #[inline]",
            "    fn mask_count(value: Self::Mask) -> usize {",
            f"        {invoke('mask_population_count')}",
            "    }",
            "",
            "    #[inline]",
            "    fn mask_and(left: Self::Mask, right: Self::Mask) -> Self::Mask {",
            f"        {invoke('mask_and')}",
            "    }",
            "",
            "    #[inline]",
            "    fn mask_or(left: Self::Mask, right: Self::Mask) -> Self::Mask {",
            f"        {invoke('mask_or')}",
            "    }",
            "",
            "    #[inline]",
            "    fn mask_xor(left: Self::Mask, right: Self::Mask) -> Self::Mask {",
            f"        {invoke('mask_xor')}",
            "    }",
            "",
            "    #[inline]",
            "    fn mask_not(value: Self::Mask) -> Self::Mask {",
            f"        {invoke('mask_not')}",
            "    }",
            "}",
        )
    )


def _conversion_methods(plan: RustFacadePlan) -> str:
    if not any(
        method.kind is RustCuratedMethodKind.NUMERIC_CAST
        for method in plan.curated_methods
    ):
        return ""
    return "\n".join(
        (
            "    /// Numerically converts each lane while preserving the lane count.",
            "    #[inline]",
            "    #[must_use]",
            "    #[allow(private_bounds)]",
            "    pub fn cast<U>(self) -> Simd<U, N>",
            "    where",
            "        U: SupportedSimd<N>,",
            "        T: private::ConvertTo<U, N>,",
            "    {",
            "        Simd {",
            (
                "            value: <T as private::ConvertTo<U, N>>::"
                "convert(self.value),"
            ),
            "        }",
            "    }",
        )
    )


def _conversion_pair_impls(plan: RustFacadePlan) -> str:
    return "\n\n".join(
        _conversion_pair_impl(arm)
        for method in plan.curated_methods
        if method.kind is RustCuratedMethodKind.NUMERIC_CAST
        for arm in method.conversion_implementation_arms
    )


def _conversion_pair_impl(
    arm: RustFacadeConversionImplementationArm,
) -> str:
    source = arm.source_shape
    target = arm.target_shape
    return "\n".join(
        (
            _cfg_attribute(_arm_selection_cfg(arm.selection)),
            (
                f"impl private::ConvertTo<{target.base_spelling}, "
                f"{source.lanes}> for {source.base_spelling} {{"
            ),
            "    #[inline]",
            (
                "    fn convert(value: Self::Vector) -> "
                f"<{target.base_spelling} as "
                f"private::Representation<{source.lanes}>>::Vector {{"
            ),
            f"        {_lower_call_expression(arm.call)}",
            "    }",
            "}",
        )
    )


def _curated_impls(plan: RustFacadePlan) -> str:
    blocks = [
        _curated_method_impl(method, arm)
        for method in plan.curated_methods
        for arm in method.implementation_arms
    ]
    blocks.extend(
        block
        for implementation in plan.equality_implementations
        for block in _equality_impls(implementation)
    )
    return "\n\n".join(blocks)


def _curated_method_impl(
    method: RustCuratedMethod,
    arm: RustCuratedMethodImplementationArm,
) -> str:
    shape = arm.shape
    vector = f"Simd<{shape.base_spelling}, {shape.lanes}>"
    mask = f"Mask<{shape.base_spelling}, {shape.lanes}>"
    call = _lower_call_expression(arm.call)
    if method.kind is RustCuratedMethodKind.SELECTION:
        return "\n".join(
            (
                _cfg_attribute(_arm_selection_cfg(arm.selection)),
                f"impl {mask} {{",
                "    /// Selects `true_values` on active lanes.",
                "    #[inline]",
                "    #[must_use]",
                (
                    f"    pub fn {method.public_name}(self, true_values: {vector}, "
                    f"false_values: {vector}) -> {vector} {{"
                ),
                f"        Simd::<{shape.base_spelling}, {shape.lanes}> {{",
                f"            value: {call},",
                "        }",
                "    }",
                "}",
            )
        )
    return "\n".join(
        (
            _cfg_attribute(_arm_selection_cfg(arm.selection)),
            f"impl {vector} {{",
            "    /// Compares corresponding lanes.",
            "    #[inline]",
            "    #[must_use]",
            (
                f"    pub fn {method.public_name}(self, other: Self) -> {mask} {{"
            ),
            f"        Mask::<{shape.base_spelling}, {shape.lanes}> {{",
            f"            value: {call},",
            "        }",
            "    }",
            "}",
        )
    )


def _equality_impls(
    implementation: RustFacadeEqualityImplementation,
) -> tuple[str, ...]:
    shape = implementation.shape
    vector = f"Simd<{shape.base_spelling}, {shape.lanes}>"
    partial_eq = "\n".join(
        (
            f"impl PartialEq for {vector} {{",
            "    #[inline]",
            "    fn eq(&self, other: &Self) -> bool {",
            (
                f"        (*self).{implementation.method_name}"
                "(*other).all()"
            ),
            "    }",
            "}",
        )
    )
    return (
        partial_eq,
        *((f"impl Eq for {vector} {{}}",) if implementation.implements_eq else ()),
    )


def _operator_impls(plan: RustFacadePlan) -> str:
    return "\n\n".join(
        block
        for trait in plan.trait_implementations
        for implementation in trait.implementations
        for block in _operator_implementation_blocks(implementation)
    )


def _operator_implementation_blocks(
    implementation: RustFacadeOperatorImplementation,
) -> tuple[str, ...]:
    return (
        *(
            _canonical_operator_impl(implementation, arm)
            for arm in implementation.canonical_arms
        ),
        *(
            _forwarding_operator_impl(implementation, arm)
            for arm in implementation.forwarding_arms
        ),
        *(
            _assignment_operator_impl(implementation, arm)
            for arm in implementation.assignment_arms
        ),
    )


def _canonical_operator_impl(
    implementation: RustFacadeOperatorImplementation,
    arm: RustFacadeCanonicalOperatorArm,
) -> str:
    value_type = _operator_value_type(implementation)
    trait_use = (
        implementation.trait_path
        if implementation.rhs_type is None
        else f"{implementation.trait_path}<{implementation.rhs_type}>"
    )
    tracking = (
        ("    #[track_caller]",)
        if implementation.track_caller
        else ()
    )
    if implementation.rhs_type is None:
        signature = (
            f"    fn {implementation.method_name}(self) -> Self::Output {{"
        )
    else:
        signature = (
            f"    fn {implementation.method_name}"
            f"(self, rhs: {implementation.rhs_type}) -> Self::Output {{"
        )
    return "\n".join(
        (
            _cfg_attribute(_arm_selection_cfg(arm.selection)),
            f"impl {trait_use} for {value_type} {{",
            "    type Output = Self;",
            "",
            "    #[inline]",
            *tracking,
            signature,
            "        Self {",
            f"            value: {_lower_call_expression(arm.call)},",
            "        }",
            "    }",
            "}",
        )
    )


def _forwarding_operator_impl(
    implementation: RustFacadeOperatorImplementation,
    arm: RustFacadeForwardingOperatorArm,
) -> str:
    value_type = _operator_value_type(implementation)
    tracking = (
        ("    #[track_caller]",)
        if implementation.track_caller
        else ()
    )
    if arm.rhs_type is None:
        return "\n".join(
            (
                f"impl {implementation.trait_path} for {arm.self_type} {{",
                f"    type Output = {value_type};",
                "",
                "    #[inline]",
                *tracking,
                (
                    f"    fn {implementation.method_name}"
                    "(self) -> Self::Output {"
                ),
                (
                    f"        <{value_type} as "
                    f"{implementation.trait_path}>::"
                    f"{implementation.method_name}({arm.self_value})"
                ),
                "    }",
                "}",
            )
        )
    assert arm.owned_rhs_type is not None
    assert arm.rhs_value is not None
    return "\n".join(
        (
            (
                f"impl {implementation.trait_path}<{arm.rhs_type}> "
                f"for {arm.self_type} {{"
            ),
            f"    type Output = {value_type};",
            "",
            "    #[inline]",
            *tracking,
            (
                f"    fn {implementation.method_name}"
                f"(self, rhs: {arm.rhs_type}) -> Self::Output {{"
            ),
            (
                f"        <{value_type} as "
                f"{implementation.trait_path}<{arm.owned_rhs_type}>>::"
                f"{implementation.method_name}"
                f"({arm.self_value}, {arm.rhs_value})"
            ),
            "    }",
            "}",
        )
    )


def _assignment_operator_impl(
    implementation: RustFacadeOperatorImplementation,
    arm: RustFacadeAssignmentOperatorArm,
) -> str:
    value_type = _operator_value_type(implementation)
    tracking = (
        ("    #[track_caller]",)
        if implementation.track_caller
        else ()
    )
    return "\n".join(
        (
            f"impl {arm.trait_path}<{arm.rhs_type}> for {value_type} {{",
            "    #[inline]",
            *tracking,
            f"    fn {arm.method_name}(&mut self, rhs: {arm.rhs_type}) {{",
            (
                f"        *self = <{value_type} as "
                f"{implementation.trait_path}<{arm.owned_rhs_type}>>::"
                f"{implementation.method_name}(*self, {arm.rhs_value});"
            ),
            "    }",
            "}",
        )
    )


def _operator_value_type(
    implementation: RustFacadeOperatorImplementation,
) -> str:
    owner = (
        "Simd"
        if implementation.receiver_kind is RustFacadeReceiverKind.VECTOR
        else "Mask"
    )
    shape = implementation.shape
    return f"{owner}<{shape.base_spelling}, {shape.lanes}>"


def _bit_conversion_impls(plan: RustFacadePlan) -> str:
    return "\n\n".join(
        _bit_method_impl(arm)
        for conversion in plan.bit_conversions
        for arm in conversion.implementation_arms
    )


def _bit_method_impl(
    arm: RustFacadeBitConversionImplementationArm,
) -> str:
    float_shape = arm.float_shape
    bits_shape = arm.bits_shape
    float_vector = f"Simd<{float_shape.base_spelling}, {float_shape.lanes}>"
    bits_vector = f"Simd<{bits_shape.base_spelling}, {bits_shape.lanes}>"
    to_bits = arm.direction is RustFacadeBitConversionDirection.TO_BITS
    if to_bits:
        signature = f"    pub fn to_bits(self) -> {bits_vector} {{"
    else:
        signature = f"    pub fn from_bits(bits: {bits_vector}) -> Self {{"
    return "\n".join(
        (
            _cfg_attribute(_arm_selection_cfg(arm.conversion.selection)),
            f"impl {float_vector} {{",
            "    /// Reinterprets the same-width lane bit patterns.",
            "    #[inline]",
            "    #[must_use]",
            signature,
            (
                f"        Simd::<{bits_shape.base_spelling}, {bits_shape.lanes}> {{"
                if to_bits
                else "        Self {"
            ),
            f"            value: {_lower_call_expression(arm.conversion.call)},",
            "        }",
            "    }",
            "}",
        )
    )


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


__all__ = ("rust_facade_module",)
