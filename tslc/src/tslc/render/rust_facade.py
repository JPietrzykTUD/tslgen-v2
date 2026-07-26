"""Render the ordinary owned Rust types from the finalized facade plan."""

from __future__ import annotations

from tslc.backend.rust_api_model import (
    RustCuratedMethod,
    RustCuratedTraitImplementation,
    RustFacadeBitConversion,
    RustFacadeCoreDelegate,
    RustFacadeDelegate,
    RustFacadePlan,
    RustFacadeRepresentation,
    RustFacadeReceiverKind,
    RustFacadeShape,
    RustFacadeTraitRhsKind,
    RustNativeAlias,
    RustNativeAliasSelection,
)
from tslc.backend.rust_api_planner import RUST_FACADE_CORE_OPERATION_REQUIREMENTS
from tslc.backend.rust_translation import rust_raw_identifier
from tslc.catalog.arithmetic import ArithmeticOperation
from tslc.catalog.scalar_types import SCALAR_TYPE_INFOS
from tslc.catalog.semantics import PrimitiveOperation
from tslc.compiler_assets import RenderAssets
from tslc.render.rust_facade_common import (
    cfg_attribute as _cfg_attribute,
    combined_selection_cfg as _combined_selection_cfg,
    lower_module as _lower_module,
    native_selection_cfg as _native_selection_cfg,
    private_vector_descriptor as _private_vector_descriptor,
    representations_can_coexist as _representations_can_coexist,
    selection_cfg as _selection_cfg,
    surface_delegate as _surface_delegate,
    surface_delegate_for_profile as _surface_delegate_for_profile,
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
            descriptor = _private_vector_descriptor(representation)
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
            _cfg_attribute(_selection_cfg(representation)),
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
            f"        {call('mask_from_integral')}::<{descriptor}>"
            f"({_mask_integer_argument('bits', representation)})",
            "    }",
            "",
            "    #[inline]",
            "    fn mask_to_bitmask(value: Self::Mask) -> u64 {",
            _mask_integer_result(
                f"{call('mask_to_integral')}::<{descriptor}>(value)",
                representation,
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


def _mask_integer_argument(
    value: str,
    representation: RustFacadeRepresentation,
) -> str:
    imask = representation.mapping.imask_spelling
    return value if imask == "u64" else f"{value} as {imask}"


def _mask_integer_result(
    call: str,
    representation: RustFacadeRepresentation,
) -> str:
    suffix = "" if representation.mapping.imask_spelling == "u64" else " as u64"
    return f"        {call}{suffix}"


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


def _conversion_methods(plan: RustFacadePlan) -> str:
    if not any(method.public_name == "cast" for method in plan.curated_methods):
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
    method = next(
        (item for item in plan.curated_methods if item.public_name == "cast"),
        None,
    )
    if method is None:
        return ""
    blocks: list[str] = []
    for source in plan.shapes:
        if (source.type_tag, source.lanes) not in method.shape_keys:
            continue
        for target in plan.shapes:
            if (
                target.type_tag not in method.target_type_tags
                or target.lanes != source.lanes
            ):
                continue
            for source_representation in source.representations:
                for target_representation in target.representations:
                    if not _representations_can_coexist(
                        source_representation, target_representation
                    ):
                        continue
                    active_representation = (
                        source_representation
                        if source_representation.profile_name is not None
                        else target_representation
                    )
                    delegate = _surface_delegate_for_profile(
                        method.delegates,
                        source,
                        source_representation,
                        active_representation.profile_name,
                    )
                    source_descriptor = _private_vector_descriptor(
                        source_representation
                    )
                    target_descriptor = _private_vector_descriptor(
                        target_representation
                    )
                    module = _lower_module(active_representation)
                    blocks.append(
                        "\n".join(
                            (
                                _cfg_attribute(
                                    _combined_selection_cfg(
                                        source_representation,
                                        target_representation,
                                    )
                                ),
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
                                (
                                    f"        {module}::"
                                    f"{rust_raw_identifier(delegate.primitive_name)}::<"
                                    f"{source_descriptor}, {target_descriptor}>(value)"
                                ),
                                "    }",
                                "}",
                            )
                        )
                    )
    return "\n\n".join(blocks)


def _curated_impls(plan: RustFacadePlan) -> str:
    blocks: list[str] = []
    equality_shapes: set[tuple[str, int]] = set()
    for method in plan.curated_methods:
        if method.public_name == "cast":
            continue
        for shape in plan.shapes:
            if (shape.type_tag, shape.lanes) not in method.shape_keys:
                continue
            if method.operation is PrimitiveOperation.COMPARE_EQUAL:
                equality_shapes.add((shape.type_tag, shape.lanes))
            for representation in shape.representations:
                delegate = _surface_delegate(method.delegates, shape, representation)
                blocks.append(_curated_method_impl(method, shape, representation, delegate))

    if any(method.public_name == "simd_eq" for method in plan.curated_methods):
        for shape in plan.shapes:
            if (shape.type_tag, shape.lanes) not in equality_shapes:
                continue
            vector = f"Simd<{shape.base_spelling}, {shape.lanes}>"
            blocks.append(
                "\n".join(
                    (
                        f"impl PartialEq for {vector} {{",
                        "    #[inline]",
                        "    fn eq(&self, other: &Self) -> bool {",
                        "        (*self).simd_eq(*other).all()",
                        "    }",
                        "}",
                    )
                )
            )
            info = SCALAR_TYPE_INFOS[shape.type_tag]
            if not info.floating:
                blocks.append(f"impl Eq for {vector} {{}}")
    return "\n\n".join(blocks)


def _curated_method_impl(
    method: RustCuratedMethod,
    shape: RustFacadeShape,
    representation: RustFacadeRepresentation,
    delegate: RustFacadeDelegate,
) -> str:
    cfg = _selection_cfg(representation)
    module = _lower_module(representation)
    descriptor = _private_vector_descriptor(representation)
    vector = f"Simd<{shape.base_spelling}, {shape.lanes}>"
    mask = f"Mask<{shape.base_spelling}, {shape.lanes}>"
    if method.receiver_kind is RustFacadeReceiverKind.MASK:
        return "\n".join(
            (
                _cfg_attribute(cfg),
                f"impl {mask} {{",
                "    /// Selects `true_values` on active lanes.",
                "    #[inline]",
                "    #[must_use]",
                (
                    f"    pub fn {method.public_name}(self, true_values: {vector}, "
                    f"false_values: {vector}) -> {vector} {{"
                ),
                f"        Simd::<{shape.base_spelling}, {shape.lanes}> {{",
                (
                    f"            value: {module}::{rust_raw_identifier(delegate.primitive_name)}::<"
                    f"{descriptor}>(self.value, true_values.value, false_values.value),"
                ),
                "        }",
                "    }",
                "}",
            )
        )
    return "\n".join(
        (
            _cfg_attribute(cfg),
            f"impl {vector} {{",
            "    /// Compares corresponding lanes.",
            "    #[inline]",
            "    #[must_use]",
            (
                f"    pub fn {method.public_name}(self, other: Self) -> {mask} {{"
            ),
            f"        Mask::<{shape.base_spelling}, {shape.lanes}> {{",
            (
                f"            value: {module}::{rust_raw_identifier(delegate.primitive_name)}::<"
                f"{descriptor}>(self.value, other.value),"
            ),
            "        }",
            "    }",
            "}",
        )
    )


def _operator_impls(plan: RustFacadePlan) -> str:
    blocks: list[str] = []
    for trait in plan.trait_implementations:
        if trait.receiver_kind is not RustFacadeReceiverKind.VECTOR:
            continue
        for shape in plan.shapes:
            if (shape.type_tag, shape.lanes) not in trait.shape_keys:
                continue
            rhs_types: tuple[str | None, ...]
            if trait.rhs_kind is RustFacadeTraitRhsKind.SCALAR:
                rhs_types = tuple(
                    SCALAR_TYPE_INFOS[tag].documentation_short_label
                    for tag in trait.rhs_type_tags
                )
            elif trait.rhs_kind is RustFacadeTraitRhsKind.SAME_TYPE:
                rhs_types = (f"Simd<{shape.base_spelling}, {shape.lanes}>",)
            else:
                rhs_types = (None,)
            for rhs_type in rhs_types:
                for representation in shape.representations:
                    delegate = _surface_delegate(
                        trait.delegates, shape, representation
                    )
                    blocks.append(
                        _canonical_operator_impl(
                            trait, shape, representation, delegate, rhs_type
                        )
                    )
                blocks.append(_forwarding_operator_impls(trait, shape, rhs_type))
    return "\n\n".join(block for block in blocks if block)


def _canonical_operator_impl(
    trait: RustCuratedTraitImplementation,
    shape: RustFacadeShape,
    representation: RustFacadeRepresentation,
    delegate: RustFacadeDelegate,
    rhs_type: str | None,
) -> str:
    vector = f"Simd<{shape.base_spelling}, {shape.lanes}>"
    trait_use = (
        trait.trait_path if rhs_type is None else f"{trait.trait_path}<{rhs_type}>"
    )
    module = _lower_module(representation)
    descriptor = _private_vector_descriptor(representation)
    tracking = (
        ("    #[track_caller]",)
        if trait.operation
        in {ArithmeticOperation.DIVISION, ArithmeticOperation.REMAINDER}
        else ()
    )
    if rhs_type is None:
        call = (
            f"{module}::{rust_raw_identifier(delegate.primitive_name)}::<"
            f"{descriptor}>(self.value)"
        )
        signature = f"    fn {trait.method_name}(self) -> Self::Output {{"
    else:
        extra_generic = (
            ", _"
            if trait.operation
            in {
                PrimitiveOperation.SHIFT_LEFT_WRAPPING,
                PrimitiveOperation.SHIFT_RIGHT_WRAPPING,
            }
            else ""
        )
        rhs_value = (
            "rhs" if trait.rhs_kind is RustFacadeTraitRhsKind.SCALAR else "rhs.value"
        )
        call = (
            f"{module}::{rust_raw_identifier(delegate.primitive_name)}::<"
            f"{descriptor}{extra_generic}>"
            f"(self.value, {rhs_value})"
        )
        signature = (
            f"    fn {trait.method_name}(self, rhs: {rhs_type}) -> Self::Output {{"
        )
    return "\n".join(
        (
            _cfg_attribute(_selection_cfg(representation)),
            f"impl {trait_use} for {vector} {{",
            "    type Output = Self;",
            "",
            "    #[inline]",
            *tracking,
            signature,
            "        Self {",
            f"            value: {call},",
            "        }",
            "    }",
            "}",
        )
    )


def _forwarding_operator_impls(
    trait: RustCuratedTraitImplementation,
    shape: RustFacadeShape,
    rhs_type: str | None,
) -> str:
    vector = f"Simd<{shape.base_spelling}, {shape.lanes}>"
    tracking = (
        ("    #[track_caller]",)
        if trait.operation
        in {ArithmeticOperation.DIVISION, ArithmeticOperation.REMAINDER}
        else ()
    )
    if rhs_type is None:
        return "\n".join(
            (
                f"impl {trait.trait_path} for &{vector} {{",
                f"    type Output = {vector};",
                "",
                "    #[inline]",
                *tracking,
                f"    fn {trait.method_name}(self) -> Self::Output {{",
                (
                    f"        <{vector} as {trait.trait_path}>::"
                    f"{trait.method_name}(*self)"
                ),
                "    }",
                "}",
            )
        )

    assign_trait, assign_method = _assignment_trait(trait.trait_path)
    rhs_value = "*rhs"
    borrowed_rhs = f"&{rhs_type}"
    blocks = [
        _binary_forwarding_impl(
            trait, vector, rhs_type, f"&{vector}", rhs_value="rhs", tracking=tracking
        ),
        _binary_forwarding_impl(
            trait,
            vector,
            borrowed_rhs,
            vector,
            rhs_value=rhs_value,
            tracking=tracking,
        ),
        _binary_forwarding_impl(
            trait,
            vector,
            borrowed_rhs,
            f"&{vector}",
            rhs_value=rhs_value,
            tracking=tracking,
        ),
    ]
    if assign_trait is not None and assign_method is not None:
        blocks.extend(
            (
                _assignment_impl(
                    trait,
                    vector,
                    rhs_type,
                    assign_trait,
                    assign_method,
                    "rhs",
                    tracking,
                ),
                _assignment_impl(
                    trait,
                    vector,
                    borrowed_rhs,
                    assign_trait,
                    assign_method,
                    rhs_value,
                    tracking,
                ),
            )
        )
    return "\n\n".join(blocks)


def _binary_forwarding_impl(
    trait: RustCuratedTraitImplementation,
    vector: str,
    rhs_type: str,
    self_type: str,
    *,
    rhs_value: str,
    tracking: tuple[str, ...],
) -> str:
    owned_rhs = (
        vector
        if trait.rhs_kind is RustFacadeTraitRhsKind.SAME_TYPE
        else rhs_type.removeprefix("&")
    )
    self_value = "*self" if self_type.startswith("&") else "self"
    return "\n".join(
        (
            f"impl {trait.trait_path}<{rhs_type}> for {self_type} {{",
            f"    type Output = {vector};",
            "",
            "    #[inline]",
            *tracking,
            f"    fn {trait.method_name}(self, rhs: {rhs_type}) -> Self::Output {{",
            (
                f"        <{vector} as {trait.trait_path}<{owned_rhs}>>::"
                f"{trait.method_name}({self_value}, {rhs_value})"
            ),
            "    }",
            "}",
        )
    )


def _assignment_impl(
    trait: RustCuratedTraitImplementation,
    vector: str,
    rhs_type: str,
    assign_trait: str,
    assign_method: str,
    rhs_value: str,
    tracking: tuple[str, ...],
) -> str:
    owned_rhs = (
        vector
        if trait.rhs_kind is RustFacadeTraitRhsKind.SAME_TYPE
        else rhs_type.removeprefix("&")
    )
    return "\n".join(
        (
            f"impl {assign_trait}<{rhs_type}> for {vector} {{",
            "    #[inline]",
            *tracking,
            f"    fn {assign_method}(&mut self, rhs: {rhs_type}) {{",
            (
                f"        *self = <{vector} as {trait.trait_path}<{owned_rhs}>>::"
                f"{trait.method_name}(*self, {rhs_value});"
            ),
            "    }",
            "}",
        )
    )


def _assignment_trait(trait_path: str) -> tuple[str | None, str | None]:
    mapping = {
        "core::ops::Add": ("core::ops::AddAssign", "add_assign"),
        "core::ops::Sub": ("core::ops::SubAssign", "sub_assign"),
        "core::ops::Mul": ("core::ops::MulAssign", "mul_assign"),
        "core::ops::Div": ("core::ops::DivAssign", "div_assign"),
        "core::ops::Rem": ("core::ops::RemAssign", "rem_assign"),
        "core::ops::BitAnd": ("core::ops::BitAndAssign", "bitand_assign"),
        "core::ops::BitOr": ("core::ops::BitOrAssign", "bitor_assign"),
        "core::ops::BitXor": ("core::ops::BitXorAssign", "bitxor_assign"),
        "core::ops::Shl": ("core::ops::ShlAssign", "shl_assign"),
        "core::ops::Shr": ("core::ops::ShrAssign", "shr_assign"),
    }
    return mapping.get(trait_path, (None, None))


def _bit_conversion_impls(plan: RustFacadePlan) -> str:
    blocks: list[str] = []
    for conversion in plan.bit_conversions:
        float_shapes = {
            shape.lanes: shape
            for shape in plan.shapes
            if shape.type_tag == conversion.float_type_tag
        }
        bits_shapes = {
            shape.lanes: shape
            for shape in plan.shapes
            if shape.type_tag == conversion.bits_type_tag
        }
        admitted_lanes = {
            lanes
            for type_tag, lanes in conversion.shape_keys
            if type_tag == conversion.float_type_tag
        }
        for lanes in sorted(
            float_shapes.keys() & bits_shapes.keys() & admitted_lanes
        ):
            float_shape = float_shapes[lanes]
            bits_shape = bits_shapes[lanes]
            for float_representation in float_shape.representations:
                for bits_representation in bits_shape.representations:
                    if not _representations_can_coexist(
                        float_representation, bits_representation
                    ):
                        continue
                    active_representation = (
                        float_representation
                        if float_representation.profile_name is not None
                        else bits_representation
                    )
                    delegate = _surface_delegate_for_profile(
                        conversion.delegates,
                        float_shape,
                        float_representation,
                        active_representation.profile_name,
                    )
                    blocks.append(
                        _bit_method_impl(
                            conversion,
                            float_shape,
                            bits_shape,
                            float_representation,
                            bits_representation,
                            delegate,
                            to_bits=True,
                        )
                    )
            for bits_representation in bits_shape.representations:
                for float_representation in float_shape.representations:
                    if not _representations_can_coexist(
                        bits_representation, float_representation
                    ):
                        continue
                    active_representation = (
                        bits_representation
                        if bits_representation.profile_name is not None
                        else float_representation
                    )
                    delegate = _surface_delegate_for_profile(
                        conversion.delegates,
                        bits_shape,
                        bits_representation,
                        active_representation.profile_name,
                    )
                    blocks.append(
                        _bit_method_impl(
                            conversion,
                            float_shape,
                            bits_shape,
                            bits_representation,
                            float_representation,
                            delegate,
                            to_bits=False,
                        )
                    )
    return "\n\n".join(blocks)


def _bit_method_impl(
    conversion: RustFacadeBitConversion,
    float_shape: RustFacadeShape,
    bits_shape: RustFacadeShape,
    source_representation: RustFacadeRepresentation,
    target_representation: RustFacadeRepresentation,
    delegate: RustFacadeDelegate,
    *,
    to_bits: bool,
) -> str:
    del conversion
    float_vector = f"Simd<{float_shape.base_spelling}, {float_shape.lanes}>"
    bits_vector = f"Simd<{bits_shape.base_spelling}, {bits_shape.lanes}>"
    active_representation = (
        source_representation
        if source_representation.profile_name is not None
        else target_representation
    )
    module = _lower_module(active_representation)
    source_descriptor = _private_vector_descriptor(source_representation)
    target_descriptor = _private_vector_descriptor(target_representation)
    cfg = _combined_selection_cfg(source_representation, target_representation)
    if to_bits:
        signature = f"    pub fn to_bits(self) -> {bits_vector} {{"
        argument = "self.value"
    else:
        signature = f"    pub fn from_bits(bits: {bits_vector}) -> Self {{"
        argument = "bits.value"
    return "\n".join(
        (
            _cfg_attribute(cfg),
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
            (
                f"            value: {module}::{rust_raw_identifier(delegate.primitive_name)}::<"
                f"{source_descriptor}, {target_descriptor}>({argument}),"
            ),
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
