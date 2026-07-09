"""Render Rust profile-local algorithm facade modules."""

from __future__ import annotations

from collections.abc import Mapping

from tslc.backend.target_capability import rust_extension_tag
from tslc.catalog.model import Extension
from tslc.compiler_assets import RenderAssets
from tslc.lower.lowerer import LoweredSpecialization
from tslc.render._common import type_bits, used_type_specs
from tslc.render.rust_facades import (
    rust_algorithm_primitive_facades,
    rust_public_function_names,
)
from tslc.render.rust_vectors import RustVectorRegistration, rust_vector_registrations
from tslc.support_policy import DEFAULT_SUPPORT_POLICY


def rust_algorithm_module(
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    extensions: Mapping[str, Extension],
    assets: RenderAssets,
) -> str:
    """Profile-local Rust algorithm facade and SIMD policy mappings."""

    if "load" not in by_primitive or "store" not in by_primitive:
        return ""

    parts = [
        "pub mod algo {\n"
        "    pub use crate::tsl_algorithm::{\n"
        "        mask_layout, BinaryAggregateKernel, BinaryConsumeKernel, BinaryKernel,\n"
        "        BinaryPredicateKernel, ChunkKernel, IntegralMaskWord,\n"
        "        MaskedBinaryAggregateKernel, MaskedBinaryConsumeKernel,\n"
        "        MaskedBinaryKernel, MaskedUnaryAggregateKernel,\n"
        "        MaskedUnaryConsumeKernel, MaskedUnaryKernel, UnaryAggregateKernel,\n"
        "        UnaryConsumeKernel, UnaryKernel, UnaryPredicateKernel, MaskLayout,\n"
        "    };\n\n"
        "    use crate::tsl_algorithm::{\n"
        "        CompressStore, IntegralMask, LoadStore, MaskFromIntegral, MaskedStore,\n"
        "        MaskPopulationCount, RebindBase, ReboundBase, SelectedLoad, VectorFor,\n"
        "    };\n"
        "    use crate::dataparallel;\n"
        "    use crate::tsl_core::{\n"
        "        BaseTypeDispatch, Generic, Scalar, Simd, SimdVector, StaticSimdVector,\n"
        "    };\n"
        "\n"
        "    pub struct Profile;"
    ]
    parts.append(_rust_algorithm_load_store_impls(by_primitive, extensions))
    selected_load_impls = _rust_algorithm_selected_load_impls(
        by_primitive, extensions
    )
    if selected_load_impls:
        parts.append(selected_load_impls)
    parts.append(_rust_algorithm_masked_store_impls(by_primitive, extensions))
    compress_store_impls = _rust_algorithm_compress_store_impls(
        by_primitive, extensions
    )
    if compress_store_impls:
        parts.append(compress_store_impls)
    mask_population_count_impls = _rust_algorithm_mask_population_count_impls(
        by_primitive, extensions
    )
    if mask_population_count_impls:
        parts.append(mask_population_count_impls)
    integral_mask_impls = _rust_algorithm_integral_mask_impls(
        by_primitive, extensions
    )
    if integral_mask_impls:
        parts.append(integral_mask_impls)
    mask_from_integral_impls = _rust_algorithm_mask_from_integral_impls(
        by_primitive, extensions
    )
    if mask_from_integral_impls:
        parts.append(mask_from_integral_impls)
    mappings = _rust_algorithm_vector_mappings(by_primitive, extensions)
    if mappings:
        parts.append(mappings)
    algorithm_wrappers = assets.text(_RUST_ALGORITHM_WRAPPER_ASSET).rstrip()
    primitive_facades = rust_algorithm_primitive_facades(
        by_primitive,
        reserved_names=rust_public_function_names(algorithm_wrappers),
    )
    if primitive_facades:
        parts.append(primitive_facades)
    parts.append(algorithm_wrappers)
    return "\n\n" + "\n\n".join(part for part in parts if part) + "\n}\n"


def _rust_algorithm_load_store_impls(
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    extensions: Mapping[str, Extension],
) -> str:
    registrations = rust_vector_registrations(by_primitive, extensions)
    concrete_extensions = sorted(
        {
            f"super::{rust_extension_tag(extensions[registration.extension_name])}"
            for registration in registrations
            if registration.extension_name in extensions
        }
    )
    parts = [
        _rust_algorithm_load_store_impl("Scalar"),
        _rust_algorithm_generic_load_store_impl(),
    ]
    parts.extend(
        _rust_algorithm_load_store_impl(extension)
        for extension in concrete_extensions
    )
    return "\n\n".join(parts)


def _rust_algorithm_load_store_impl(extension: str) -> str:
    vector = f"Simd<T, {extension}>"
    return (
        f"    impl<T> LoadStore<{vector}> for Profile\n"
        "    where\n"
        f"        {vector}: StaticSimdVector<BaseType = T>\n"
        "            + super::detail::primitives::LoadImpl<false>,\n"
        f"        <{vector} as SimdVector>::RegisterType:\n"
        f"            super::detail::primitives::StoreImplArg<{vector}, false>,\n"
        "    {\n"
        f"        unsafe fn load_unaligned(ptr: *const T) -> <{vector} as SimdVector>::RegisterType {{\n"
        f"            unsafe {{ super::load::<{vector}, false>(ptr) }}\n"
        "        }\n\n"
        f"        unsafe fn store_unaligned(ptr: *mut T, value: <{vector} as SimdVector>::RegisterType) {{\n"
        f"            unsafe {{ super::store::<{vector}, false, _>(ptr, value) }}\n"
        "        }\n"
        "    }"
    )


def _rust_algorithm_generic_load_store_impl() -> str:
    vector = "Simd<T, Generic<N>>"
    return (
        f"    impl<T, const N: usize> LoadStore<{vector}> for Profile\n"
        "    where\n"
        f"        {vector}: StaticSimdVector<BaseType = T>\n"
        "            + super::detail::primitives::LoadImpl<false>,\n"
        f"        <{vector} as SimdVector>::RegisterType:\n"
        f"            super::detail::primitives::StoreImplArg<{vector}, false>,\n"
        "    {\n"
        f"        unsafe fn load_unaligned(ptr: *const T) -> <{vector} as SimdVector>::RegisterType {{\n"
        f"            unsafe {{ super::load::<{vector}, false>(ptr) }}\n"
        "        }\n\n"
        f"        unsafe fn store_unaligned(ptr: *mut T, value: <{vector} as SimdVector>::RegisterType) {{\n"
        f"            unsafe {{ super::store::<{vector}, false, _>(ptr, value) }}\n"
        "        }\n"
        "    }"
    )


def _rust_algorithm_selected_load_impls(
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    extensions: Mapping[str, Extension],
) -> str:
    if not {"set_zero", "to_array", "from_array"}.issubset(by_primitive):
        return ""
    registrations = rust_vector_registrations(by_primitive, extensions)
    gather_narrow_vectors = _rust_algorithm_gather_narrow_vectors(by_primitive)
    selected_load_vectors = (
        gather_narrow_vectors | _rust_algorithm_array_selected_load_vectors(by_primitive)
    )
    parts = [
        _rust_algorithm_scalar_selected_load_impl(),
        _rust_algorithm_generic_selected_load_impl(),
    ]
    parts.extend(
        _rust_algorithm_selected_load_impl(
            registration,
            extensions[registration.extension_name],
            use_gather_narrow=(
                registration.extension_name,
                registration.base_spelling,
            )
            in gather_narrow_vectors,
        )
        for registration in registrations
        if registration.extension_name in extensions
        and (registration.extension_name, registration.base_spelling)
        in selected_load_vectors
    )
    return "\n\n".join(parts)


def _rust_algorithm_gather_narrow_vectors(
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]]
) -> frozenset[tuple[str, str]]:
    return frozenset(
        (spec.extension_name, spec.base_type_spelling)
        for spec in by_primitive.get("gather_narrow", ())
    )


def _rust_algorithm_array_selected_load_vectors(
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]]
) -> frozenset[tuple[str, str]]:
    required = ("set_zero", "to_array", "from_array")
    vector_sets = [
        {
            (spec.extension_name, spec.base_type_spelling)
            for spec in by_primitive.get(primitive, ())
        }
        for primitive in required
    ]
    return frozenset(set.intersection(*vector_sets)) if vector_sets else frozenset()


def _rust_algorithm_scalar_selected_load_impl() -> str:
    vector = "Simd<T, Scalar>"
    return (
        f"    impl<T, const SCALE: u32> SelectedLoad<{vector}, SCALE> for Profile\n"
        "    where\n"
        f"        {vector}: StaticSimdVector<BaseType = T>\n"
        "            + super::detail::primitives::LoadImpl<false>,\n"
        "    {\n"
        f"        unsafe fn load_selected(input: *const T, indices: *const usize)\n"
        f"            -> <{vector} as SimdVector>::RegisterType {{\n"
        "            unsafe {\n"
        "                let ptr = crate::tsl_algorithm::selected_row_pointer::<T, SCALE>(\n"
        "                    input,\n"
        "                    indices.read(),\n"
        "                );\n"
        f"                super::load::<{vector}, false>(ptr)\n"
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
    registration: RustVectorRegistration,
    extension: Extension,
    *,
    use_gather_narrow: bool,
) -> str:
    base = registration.base_spelling
    lane_count = registration.vector_bits // type_bits(base)
    default_scale = type_bits(base) // 8
    vector = f"Simd<{base}, super::{rust_extension_tag(extension)}>"
    if not use_gather_narrow:
        return _rust_algorithm_array_selected_load_impl(vector, base)
    index_vector = f"Simd<usize, Generic<{lane_count}>>"
    return (
        f"    impl<const SCALE: u32> SelectedLoad<{vector}, SCALE> for Profile\n"
        "    where\n"
        f"        {vector}: StaticSimdVector<BaseType = {base}>\n"
        f"            + super::detail::primitives::Gather_narrowImpl<{index_vector}, "
        f"<usize as BaseTypeDispatch>::Key, {default_scale}, 1>\n"
        f"            + super::detail::primitives::Gather_narrowImpl<{index_vector}, "
        f"<usize as BaseTypeDispatch>::Key, SCALE, 1>,\n"
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
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    extensions: Mapping[str, Extension],
) -> str:
    if "store" not in by_primitive:
        return ""
    registrations = rust_vector_registrations(by_primitive, extensions)
    concrete_extensions = sorted(
        {
            f"super::{rust_extension_tag(extensions[registration.extension_name])}"
            for registration in registrations
            if registration.extension_name in extensions
        }
    )
    parts = [
        _rust_algorithm_masked_store_impl("Scalar"),
        _rust_algorithm_generic_masked_store_impl(),
    ]
    parts.extend(
        _rust_algorithm_masked_store_impl(extension)
        for extension in concrete_extensions
    )
    return "\n\n".join(parts)


def _rust_algorithm_masked_store_impl(extension: str) -> str:
    vector = f"Simd<T, {extension}>"
    return (
        f"    impl<T> MaskedStore<{vector}> for Profile\n"
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


def _rust_algorithm_generic_masked_store_impl() -> str:
    vector = "Simd<T, Generic<N>>"
    return (
        f"    impl<T, const N: usize> MaskedStore<{vector}> for Profile\n"
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
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    extensions: Mapping[str, Extension],
) -> str:
    if "compress_store" not in by_primitive:
        return ""
    registrations = rust_vector_registrations(by_primitive, extensions)
    concrete_extensions = sorted(
        {
            f"super::{rust_extension_tag(extensions[registration.extension_name])}"
            for registration in registrations
            if registration.extension_name in extensions
        }
    )
    parts = [
        _rust_algorithm_compress_store_impl("Scalar"),
        _rust_algorithm_generic_compress_store_impl(),
    ]
    parts.extend(
        _rust_algorithm_compress_store_impl(extension)
        for extension in concrete_extensions
    )
    return "\n\n".join(parts)


def _rust_algorithm_compress_store_impl(extension: str) -> str:
    vector = f"Simd<T, {extension}>"
    return (
        f"    impl<T> CompressStore<{vector}> for Profile\n"
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


def _rust_algorithm_generic_compress_store_impl() -> str:
    vector = "Simd<T, Generic<N>>"
    return (
        f"    impl<T, const N: usize> CompressStore<{vector}> for Profile\n"
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
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    extensions: Mapping[str, Extension],
) -> str:
    if "mask_population_count" not in by_primitive:
        return ""
    registrations = rust_vector_registrations(by_primitive, extensions)
    concrete_extensions = sorted(
        {
            f"super::{rust_extension_tag(extensions[registration.extension_name])}"
            for registration in registrations
            if registration.extension_name in extensions
        }
    )
    parts = [
        _rust_algorithm_mask_population_count_impl("Scalar"),
        _rust_algorithm_generic_mask_population_count_impl(),
    ]
    parts.extend(
        _rust_algorithm_mask_population_count_impl(extension)
        for extension in concrete_extensions
    )
    return "\n\n".join(parts)


def _rust_algorithm_mask_population_count_impl(extension: str) -> str:
    vector = f"Simd<T, {extension}>"
    return (
        f"    impl<T> MaskPopulationCount<{vector}> for Profile\n"
        "    where\n"
        f"        {vector}: StaticSimdVector\n"
        "            + super::detail::primitives::Mask_population_countImpl,\n"
        "    {\n"
        f"        fn mask_population_count(mask: <{vector} as SimdVector>::MaskType) -> usize {{\n"
        f"            super::mask_population_count::<{vector}>(mask)\n"
        "        }\n"
        "    }"
    )


def _rust_algorithm_generic_mask_population_count_impl() -> str:
    vector = "Simd<T, Generic<N>>"
    return (
        f"    impl<T, const N: usize> MaskPopulationCount<{vector}> for Profile\n"
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
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    extensions: Mapping[str, Extension],
) -> str:
    if "to_integral" not in by_primitive:
        return ""
    registrations = rust_vector_registrations(by_primitive, extensions)
    concrete_extensions = sorted(
        {
            f"super::{rust_extension_tag(extensions[registration.extension_name])}"
            for registration in registrations
            if registration.extension_name in extensions
        }
    )
    parts = [
        _rust_algorithm_integral_mask_impl("Scalar"),
        _rust_algorithm_generic_integral_mask_impl(),
    ]
    parts.extend(
        _rust_algorithm_integral_mask_impl(extension)
        for extension in concrete_extensions
    )
    return "\n\n".join(parts)


def _rust_algorithm_integral_mask_impl(extension: str) -> str:
    vector = f"Simd<T, {extension}>"
    return (
        f"    impl<T> IntegralMask<{vector}> for Profile\n"
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


def _rust_algorithm_generic_integral_mask_impl() -> str:
    vector = "Simd<T, Generic<N>>"
    return (
        f"    impl<T, const N: usize> IntegralMask<{vector}> for Profile\n"
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
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    extensions: Mapping[str, Extension],
) -> str:
    if "to_mask" not in by_primitive:
        return ""
    registrations = rust_vector_registrations(by_primitive, extensions)
    concrete_extensions = sorted(
        {
            f"super::{rust_extension_tag(extensions[registration.extension_name])}"
            for registration in registrations
            if registration.extension_name in extensions
        }
    )
    parts = [
        _rust_algorithm_mask_from_integral_impl("Scalar"),
        _rust_algorithm_generic_mask_from_integral_impl(),
    ]
    parts.extend(
        _rust_algorithm_mask_from_integral_impl(extension)
        for extension in concrete_extensions
    )
    return "\n\n".join(parts)


def _rust_algorithm_mask_from_integral_impl(extension: str) -> str:
    vector = f"Simd<T, {extension}>"
    return (
        f"    impl<T> MaskFromIntegral<{vector}> for Profile\n"
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


def _rust_algorithm_generic_mask_from_integral_impl() -> str:
    vector = "Simd<T, Generic<N>>"
    return (
        f"    impl<T, const N: usize> MaskFromIntegral<{vector}> for Profile\n"
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
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    extensions: Mapping[str, Extension],
) -> str:
    fixed: dict[tuple[str, int], tuple[tuple[int, int, str], str]] = {}
    native: dict[str, tuple[tuple[int, int, str], str]] = {}

    for ext_name, type_tag, base in used_type_specs(by_primitive):
        extension = extensions.get(ext_name)
        if not _rust_algorithm_vector_is_mappable(extension):
            continue
        lane_count = DEFAULT_SUPPORT_POLICY.lane_count(extension, type_tag)
        if lane_count is None:
            continue
        preference = (
            extension.metadata.native_sort_order or 0,
            extension.vector_bits,
            extension.isa_name,
        )
        vector = _rust_algorithm_vector_type(extension, base)
        fixed_key = (base, lane_count)
        current_fixed = fixed.get(fixed_key)
        if current_fixed is None or preference > current_fixed[0]:
            fixed[fixed_key] = (preference, vector)
        current_native = native.get(base)
        if current_native is None or preference > current_native[0]:
            native[base] = (preference, vector)

    lines: list[str] = []
    for (base, lane_count), (_preference, vector) in sorted(fixed.items()):
        lines.append(
            f"    impl VectorFor<Profile, {base}> for dataparallel::Fixed<{lane_count}> {{\n"
            f"        type Vec = {vector};\n"
            "    }"
        )
    for base, (_preference, vector) in sorted(native.items()):
        lines.append(
            f"    impl VectorFor<Profile, {base}> for dataparallel::Native {{\n"
            f"        type Vec = {vector};\n"
            "    }"
        )
    return "\n\n".join(lines)


def _rust_algorithm_vector_is_mappable(extension: Extension | None) -> bool:
    if extension is None:
        return False
    if DEFAULT_SUPPORT_POLICY.uses_sized_vector(extension):
        return False
    if extension.family == "generic_like":
        return False
    return extension.supports_backend("rust")


def _rust_algorithm_vector_type(extension: Extension, base: str) -> str:
    if extension.family == "scalar":
        return f"Simd<{base}, Scalar>"
    return f"Simd<{base}, super::{rust_extension_tag(extension)}>"


_RUST_ALGORITHM_WRAPPER_ASSET = "rust_algo_wrappers.rs"
