"""Render Rust profile-local algorithm facade modules."""

from __future__ import annotations

from tslc.backend.rust_algorithm_plan import (
    RustAlgorithmImplTarget,
    RustAlgorithmProfilePlan,
    RustAlgorithmSelectedLoadTarget,
)
from tslc.backend.rust_algorithm_contracts import rust_algorithm_contract_holes
from tslc.backend.rust_algorithm_public_declarations import (
    rust_profile_algorithm_module_declaration,
    rust_profile_algorithm_support_reexports,
)
from tslc.backend.rust_facades import (
    RustAlgorithmPrimitiveFacade,
    rust_algorithm_primitive_facades,
)
from tslc.backend.rust_names import rust_primitive_trait_name
from tslc.backend.rust_static_selection import RustStaticVectorMapping
from tslc.backend.rust_translation import rust_raw_identifier
from tslc.compiler_assets import RenderAssets


def rust_algorithm_module(
    plan: RustAlgorithmProfilePlan,
    assets: RenderAssets,
) -> str:
    """Profile-local Rust algorithm facade and SIMD policy mappings."""

    if not plan.supported:
        raise ValueError("cannot format an unsupported Rust algorithm profile")
    if plan.read_facade is None or plan.write_facade is None:
        raise ValueError("supported Rust algorithm profile has no memory bindings")
    read_facade = plan.read_facade
    write_facade = plan.write_facade
    impl_targets = plan.implementation_targets
    mappings = _rust_algorithm_vector_mappings(plan)
    rebind_imports = (
        ", RebindBase, ReboundBase"
        if plan.requires_rebind
        else ""
    )
    support_reexports = "\n".join(
        "    " + declaration.render_head() + ";"
        for declaration in rust_profile_algorithm_support_reexports(
            ("profile", "algo")
        )
    )
    module_head = rust_profile_algorithm_module_declaration(
        ("profile",),
    ).render_head()
    parts = [
        f"{module_head} {{\n"
        f"{support_reexports}\n\n"
        "    use crate::tsl_algorithm::{\n"
        "        CompressStore, IntegralMask, LoadStore, MaskFromIntegral, MaskedStore,\n"
        f"        MaskPopulationCount, SelectedLoad, VectorFor{rebind_imports},\n"
        "    };\n"
        "    use crate::dataparallel;\n"
        "    use crate::tsl_core::{\n"
        "        Generic, Scalar, Simd, SimdVector, StaticSimdVector,\n"
        "    };\n"
        "\n"
        "    pub struct Profile;"
    ]
    parts.append(
        _rust_algorithm_load_store_impls(
            impl_targets,
            read_facade,
            write_facade,
        )
    )
    selected_load_impls = _rust_algorithm_selected_load_impls(
        plan,
        read_facade,
    )
    if selected_load_impls:
        parts.append(selected_load_impls)
    parts.append(
        _rust_algorithm_masked_store_impls(
            impl_targets, plan.helper("masked_store").supported
        )
    )
    compress_store_impls = _rust_algorithm_compress_store_impls(
        impl_targets, plan.helper("compress_store").supported
    )
    if compress_store_impls:
        parts.append(compress_store_impls)
    mask_population_count_impls = _rust_algorithm_mask_population_count_impls(
        impl_targets, plan.helper("mask_population_count").supported
    )
    if mask_population_count_impls:
        parts.append(mask_population_count_impls)
    integral_mask_impls = _rust_algorithm_integral_mask_impls(
        impl_targets, plan.helper("integral_mask").supported
    )
    if integral_mask_impls:
        parts.append(integral_mask_impls)
    mask_from_integral_impls = _rust_algorithm_mask_from_integral_impls(
        impl_targets, plan.helper("mask_from_integral").supported
    )
    if mask_from_integral_impls:
        parts.append(mask_from_integral_impls)
    if mappings:
        parts.append(mappings)
    algorithm_wrappers = assets.fill(
        _RUST_ALGORITHM_WRAPPER_ASSET,
        **rust_algorithm_contract_holes(
            admitted_form_names=frozenset(plan.admitted_form_names)
        ),
    ).rstrip()
    primitive_facades = rust_algorithm_primitive_facades(plan.primitive_facades)
    if primitive_facades:
        parts.append(primitive_facades)
    parts.append(algorithm_wrappers)
    return "\n\n" + "\n\n".join(part for part in parts if part) + "\n}\n"


def _rust_algorithm_load_store_impls(
    targets: tuple[RustAlgorithmImplTarget, ...],
    read_facade: RustAlgorithmPrimitiveFacade,
    write_facade: RustAlgorithmPrimitiveFacade,
) -> str:
    return "\n\n".join(
        _rust_algorithm_load_store_impl(
            target,
            read_facade,
            write_facade,
        )
        for target in targets
    )


def _rust_algorithm_load_store_impl(
    target: RustAlgorithmImplTarget,
    read_facade: RustAlgorithmPrimitiveFacade,
    write_facade: RustAlgorithmPrimitiveFacade,
) -> str:
    vector = target.vector
    read_name = rust_raw_identifier(read_facade.primitive_name)
    write_name = rust_raw_identifier(write_facade.primitive_name)
    read_trait = rust_primitive_trait_name(read_facade.primitive_name)
    write_trait = rust_primitive_trait_name(write_facade.primitive_name)
    if write_facade.overload_parameter_positions:
        write_bound = (
            f"        <{vector} as SimdVector>::RegisterType:\n"
            f"            super::detail::primitives::{write_trait}Arg<{vector}, false>,\n"
        )
        write_generics = f"<{vector}, false, _>"
    else:
        write_bound = (
            f"        {vector}: super::detail::primitives::{write_trait}<false>,\n"
        )
        write_generics = f"<{vector}, false>"
    return (
        f"    impl<{target.type_parameters}> LoadStore<{vector}> for Profile\n"
        "    where\n"
        f"        {vector}: StaticSimdVector<BaseType = T>\n"
        f"            + super::detail::primitives::{read_trait}<false>,\n"
        f"{write_bound}"
        "    {\n"
        f"        unsafe fn load_unaligned(ptr: *const T) -> <{vector} as SimdVector>::RegisterType {{\n"
        f"            unsafe {{ super::{read_name}::<{vector}, false>(ptr) }}\n"
        "        }\n\n"
        f"        unsafe fn store_unaligned(ptr: *mut T, value: <{vector} as SimdVector>::RegisterType) {{\n"
        f"            unsafe {{ super::{write_name}::{write_generics}(ptr, value) }}\n"
        "        }\n"
        "    }"
    )


def _rust_algorithm_selected_load_impls(
    plan: RustAlgorithmProfilePlan,
    read_facade: RustAlgorithmPrimitiveFacade,
) -> str:
    if not plan.helper("selected_load").supported:
        return ""
    parts = [
        _rust_algorithm_scalar_selected_load_impl(read_facade),
        _rust_algorithm_generic_selected_load_impl(),
    ]
    parts.extend(
        _rust_algorithm_selected_load_impl(target)
        for target in plan.selected_load_targets
    )
    return "\n\n".join(parts)


def _rust_algorithm_scalar_selected_load_impl(
    read_facade: RustAlgorithmPrimitiveFacade,
) -> str:
    vector = "Simd<T, Scalar>"
    read_name = rust_raw_identifier(read_facade.primitive_name)
    read_trait = rust_primitive_trait_name(read_facade.primitive_name)
    return (
        f"    impl<T, const SCALE: u32> SelectedLoad<{vector}, SCALE> for Profile\n"
        "    where\n"
        f"        {vector}: StaticSimdVector<BaseType = T>\n"
        f"            + super::detail::primitives::{read_trait}<false>,\n"
        "    {\n"
        f"        unsafe fn load_selected(input: *const T, indices: *const usize)\n"
        f"            -> <{vector} as SimdVector>::RegisterType {{\n"
        "            unsafe {\n"
        "                let ptr = crate::tsl_algorithm::selected_row_pointer::<T, SCALE>(\n"
        "                    input,\n"
        "                    indices.read(),\n"
        "                );\n"
        f"                super::{read_name}::<{vector}, false>(ptr)\n"
        "            }\n"
        "        }\n"
        "    }"
    )


def _rust_algorithm_generic_selected_load_impl() -> str:
    vector = "Simd<T, Generic<N>>"
    return (
        f"    impl<T, const N: usize, const SCALE: u32> SelectedLoad<{vector}, SCALE> for Profile\n"
        "    where\n"
        f"        {vector}: StaticSimdVector<BaseType = T>\n"
        "            + super::detail::primitives::Set_zeroImpl\n"
        "            + super::detail::primitives::To_arrayImpl\n"
        "            + super::detail::primitives::From_arrayImpl,\n"
        "        T: Copy,\n"
        "    {\n"
        f"        unsafe fn load_selected(input: *const T, indices: *const usize)\n"
        f"            -> <{vector} as SimdVector>::RegisterType {{\n"
        "            unsafe {\n"
        f"                let mut result = super::to_array::<{vector}>(super::set_zero::<{vector}>());\n"
        f"                let lanes = <{vector} as StaticSimdVector>::ELEMENT_COUNT;\n"
        "                let mut lane = 0usize;\n"
        "                while lane < lanes {\n"
        "                    let ptr = crate::tsl_algorithm::selected_row_pointer::<T, SCALE>(\n"
        "                        input,\n"
        "                        indices.add(lane).read(),\n"
        "                    );\n"
        "                    result[lane] = ptr.read();\n"
        "                    lane += 1;\n"
        "                }\n"
        f"                super::from_array::<{vector}>(&result)\n"
        "            }\n"
        "        }\n"
        "    }"
    )


def _rust_algorithm_selected_load_impl(
    target: RustAlgorithmSelectedLoadTarget,
) -> str:
    mapping = target.mapping
    base = mapping.base_spelling
    lane_count = mapping.lanes
    default_scale = mapping.total_bits // mapping.lanes // 8
    vector = _rust_algorithm_vector_type(mapping)
    if not target.use_gather_narrow:
        return _rust_algorithm_array_selected_load_impl(vector, base)
    index_vector = f"Simd<usize, Generic<{lane_count}>>"
    return (
        f"    impl<const SCALE: u32> SelectedLoad<{vector}, SCALE> for Profile\n"
        "    where\n"
        f"        {vector}: StaticSimdVector<BaseType = {base}>\n"
        f"            + super::detail::primitives::Gather_narrowImpl<{index_vector}, "
        f"<usize as crate::tsl_core::BaseTypeDispatch>::Key, {default_scale}, 1>\n"
        f"            + super::detail::primitives::Gather_narrowImpl<{index_vector}, "
        f"<usize as crate::tsl_core::BaseTypeDispatch>::Key, SCALE, 1>,\n"
        "    {\n"
        f"        unsafe fn load_selected(input: *const {base}, indices: *const usize)\n"
        f"            -> <{vector} as SimdVector>::RegisterType {{\n"
        "            unsafe {\n"
        "                if SCALE == 0 {\n"
        f"                    super::gather_narrow::<{vector}, {index_vector}, {default_scale}, 1>(\n"
        "                        input,\n"
        "                        indices,\n"
        "                    )\n"
        "                } else {\n"
        f"                    super::gather_narrow::<{vector}, {index_vector}, SCALE, 1>(\n"
        "                        input,\n"
        "                        indices,\n"
        "                    )\n"
        "                }\n"
        "            }\n"
        "        }\n"
        "    }"
    )


def _rust_algorithm_array_selected_load_impl(vector: str, base: str) -> str:
    return (
        f"    impl<const SCALE: u32> SelectedLoad<{vector}, SCALE> for Profile\n"
        "    where\n"
        f"        {vector}: StaticSimdVector<BaseType = {base}>\n"
        "            + super::detail::primitives::Set_zeroImpl\n"
        "            + super::detail::primitives::To_arrayImpl\n"
        "            + super::detail::primitives::From_arrayImpl,\n"
        "    {\n"
        f"        unsafe fn load_selected(input: *const {base}, indices: *const usize)\n"
        f"            -> <{vector} as SimdVector>::RegisterType {{\n"
        "            unsafe {\n"
        f"                let mut result = super::to_array::<{vector}>(super::set_zero::<{vector}>());\n"
        f"                let lanes = <{vector} as StaticSimdVector>::ELEMENT_COUNT;\n"
        "                let mut lane = 0usize;\n"
        "                while lane < lanes {\n"
        f"                    let ptr = crate::tsl_algorithm::selected_row_pointer::<{base}, SCALE>(\n"
        "                        input,\n"
        "                        indices.add(lane).read(),\n"
        "                    );\n"
        "                    result[lane] = ptr.read();\n"
        "                    lane += 1;\n"
        "                }\n"
        f"                super::from_array::<{vector}>(&result)\n"
        "            }\n"
        "        }\n"
        "    }"
    )


def _rust_algorithm_masked_store_impls(
    targets: tuple[RustAlgorithmImplTarget, ...],
    supported: bool,
) -> str:
    if not supported:
        return ""
    return "\n\n".join(
        _rust_algorithm_masked_store_impl(target) for target in targets
    )


def _rust_algorithm_masked_store_impl(target: RustAlgorithmImplTarget) -> str:
    vector = target.vector
    return (
        f"    impl<{target.type_parameters}> MaskedStore<{vector}> for Profile\n"
        "    where\n"
        f"        {vector}: StaticSimdVector<BaseType = T>\n"
        "            + super::detail::primitives::Store_maskImpl<false>,\n"
        "    {\n"
        f"        unsafe fn store_mask_unaligned(\n"
        f"            mask: <{vector} as SimdVector>::MaskType,\n"
        f"            ptr: *mut T,\n"
        f"            value: <{vector} as SimdVector>::RegisterType,\n"
        "        ) {\n"
        f"            unsafe {{ super::store_mask::<{vector}, false>(mask, ptr, value) }}\n"
        "        }\n"
        "    }"
    )


def _rust_algorithm_compress_store_impls(
    targets: tuple[RustAlgorithmImplTarget, ...],
    supported: bool,
) -> str:
    if not supported:
        return ""
    return "\n\n".join(
        _rust_algorithm_compress_store_impl(target) for target in targets
    )


def _rust_algorithm_compress_store_impl(target: RustAlgorithmImplTarget) -> str:
    vector = target.vector
    return (
        f"    impl<{target.type_parameters}> CompressStore<{vector}> for Profile\n"
        "    where\n"
        f"        {vector}: StaticSimdVector<BaseType = T>\n"
        "            + super::detail::primitives::Compress_storeImpl<true>,\n"
        "    {\n"
        "        unsafe fn compress_store(\n"
        f"            mask: <{vector} as SimdVector>::MaskType,\n"
        "            ptr: *mut T,\n"
        f"            value: <{vector} as SimdVector>::RegisterType,\n"
        "        ) {\n"
        f"            unsafe {{ super::compress_store::<{vector}, true>(mask, ptr, value) }}\n"
        "        }\n"
        "    }"
    )


def _rust_algorithm_mask_population_count_impls(
    targets: tuple[RustAlgorithmImplTarget, ...],
    supported: bool,
) -> str:
    if not supported:
        return ""
    return "\n\n".join(
        _rust_algorithm_mask_population_count_impl(target) for target in targets
    )


def _rust_algorithm_mask_population_count_impl(
    target: RustAlgorithmImplTarget,
) -> str:
    vector = target.vector
    return (
        f"    impl<{target.type_parameters}> MaskPopulationCount<{vector}> for Profile\n"
        "    where\n"
        f"        {vector}: StaticSimdVector\n"
        "            + super::detail::primitives::Mask_population_countImpl,\n"
        "    {\n"
        f"        fn mask_population_count(mask: <{vector} as SimdVector>::MaskType) -> usize {{\n"
        f"            super::mask_population_count::<{vector}>(mask)\n"
        "        }\n"
        "    }"
    )


def _rust_algorithm_integral_mask_impls(
    targets: tuple[RustAlgorithmImplTarget, ...],
    supported: bool,
) -> str:
    if not supported:
        return ""
    return "\n\n".join(
        _rust_algorithm_integral_mask_impl(target) for target in targets
    )


def _rust_algorithm_integral_mask_impl(target: RustAlgorithmImplTarget) -> str:
    vector = target.vector
    return (
        f"    impl<{target.type_parameters}> IntegralMask<{vector}> for Profile\n"
        "    where\n"
        f"        {vector}: StaticSimdVector\n"
        "            + super::detail::primitives::To_integralImpl,\n"
        "    {\n"
        f"        fn to_integral(mask: <{vector} as SimdVector>::MaskType)\n"
        f"            -> <{vector} as SimdVector>::ImaskType {{\n"
        f"            super::to_integral::<{vector}>(mask)\n"
        "        }\n"
        "    }"
    )


def _rust_algorithm_mask_from_integral_impls(
    targets: tuple[RustAlgorithmImplTarget, ...],
    supported: bool,
) -> str:
    if not supported:
        return ""
    return "\n\n".join(
        _rust_algorithm_mask_from_integral_impl(target) for target in targets
    )


def _rust_algorithm_mask_from_integral_impl(
    target: RustAlgorithmImplTarget,
) -> str:
    vector = target.vector
    return (
        f"    impl<{target.type_parameters}> MaskFromIntegral<{vector}> for Profile\n"
        "    where\n"
        f"        {vector}: StaticSimdVector\n"
        "            + super::detail::primitives::To_maskImpl,\n"
        "    {\n"
        f"        fn to_mask(mask: <{vector} as SimdVector>::ImaskType)\n"
        f"            -> <{vector} as SimdVector>::MaskType {{\n"
        f"            super::to_mask::<{vector}>(mask)\n"
        "        }\n"
        "    }"
    )


def _rust_algorithm_vector_mappings(
    plan: RustAlgorithmProfilePlan,
) -> str:
    lines: list[str] = []
    for mapping in sorted(
        plan.fixed_mappings, key=lambda item: (item.base_spelling, item.lanes)
    ):
        lines.append(
            f"    impl VectorFor<Profile, {mapping.base_spelling}> "
            f"for dataparallel::Fixed<{mapping.lanes}> {{\n"
            f"        type Vec = {_rust_algorithm_vector_type(mapping)};\n"
            "    }"
        )
    for mapping in sorted(plan.native_mappings, key=lambda item: item.base_spelling):
        lines.append(
            f"    impl VectorFor<Profile, {mapping.base_spelling}> "
            "for dataparallel::Native {\n"
            f"        type Vec = {_rust_algorithm_vector_type(mapping)};\n"
            "    }"
        )
    return "\n\n".join(lines)


def rust_fixed_vector_spelling(base: str, lane_count: int) -> str:
    """Crate-external spelling of the ``Fixed<N>`` vector admitted by VectorFor.

    Consumers outside the generated ``tsl`` crate address the dataparallel
    policy and algorithm profile through their fully qualified paths.
    """

    return (
        f"<tsl::dataparallel::Fixed<{lane_count}> as "
        f"tsl::tsl_algorithm::VectorFor<tsl::profile::algo::Profile, {base}>>::Vec"
    )


def _rust_algorithm_vector_type(mapping: RustStaticVectorMapping) -> str:
    if mapping.extension_tag_spelling is None:
        return mapping.vector_spelling
    return f"Simd<{mapping.base_spelling}, super::{mapping.extension_tag_spelling}>"


_RUST_ALGORITHM_WRAPPER_ASSET = "rust_algo_wrappers.rs"
