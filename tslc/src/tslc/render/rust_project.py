"""Render generated Rust project artifacts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from collections.abc import Mapping
from typing import TYPE_CHECKING

from tslc.backend.primitive_facade import (
    DataparallelPrimitiveFacade,
    DataparallelPrimitiveFacadeKind,
    classify_dataparallel_primitive_facade,
)
from tslc.backend.rust import RustBackend
from tslc.backend.rust_translation import rust_raw_identifier
from tslc.backend.target_capability import (
    rust_arch_module,
    rust_extension_tag,
)
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import Extension
from tslc.catalog.target_families import ProfileFamilyCapability
from tslc.compiler_assets import RenderAssets
from tslc.lower.lowerer import LoweredSpecialization
from tslc.output.artifacts import Artifact
from tslc.output.verify_model import VerifyEmulator, VerifyProfile
from tslc.render._common import (
    feature_spelling,
    slug,
    text,
    type_bits,
    used_exts,
    used_type_specs,
)
from tslc.support_policy import DEFAULT_SUPPORT_POLICY

if TYPE_CHECKING:
    from tslc.render.project import ProfileRender


def rust_artifacts(
    profiles: tuple[ProfileRender, ...], assets: RenderAssets
) -> list[Artifact]:
    artifacts = [
        text("rust/src/tsl_core.rs", assets.text("tsl_core.rs")),
        text("rust/src/tsl_algorithm.rs", assets.text("tsl_algorithm.rs")),
        # Ship the formatter config at the crate root so `rustfmt`/`cargo fmt` finds it and the
        # generated crate is self-contained.
        text("rust/rustfmt.toml", assets.text("rustfmt.toml")),
    ]
    for profile_render in profiles:
        capability = profile_render.profile_family or ProfileFamilyCapability(
            profile_render.profile.family
        )
        backend = RustBackend(
            feature_alternatives=profile_render.profile.alternatives,
            emit_target_features=capability.rust_target_features,
        )
        by_primitive = profile_render.specializations("rust")
        registrations = _rust_registrations(by_primitive, profile_render.extensions)
        internal = "\n\n".join(
            rendered
            for name in sorted(by_primitive)
            if (rendered := backend.render_primitive_internal(name, by_primitive[name]))
        )
        public = "\n\n".join(
            backend.render_primitive_public(name, by_primitive[name])
            for name in sorted(by_primitive)
        )
        bodies = "\n\n".join(
            part for part in (backend.render_primitive_module(internal), public) if part
        )
        # Arch modules are imported for intrinsic constants left verbatim in bodies.
        # Intrinsics themselves stay fully qualified by lowering.
        arch_use = _rust_arch_use(
            used_exts(by_primitive), profile_render.extensions
        )
        content = assets.fill(
            "rust_profile_module.rs.tmpl",
            arch_use=arch_use,
            registrations=registrations,
            bodies=bodies,
            algorithm=_rust_algorithm_module(
                by_primitive, profile_render.extensions, assets
            ),
        )
        artifacts.append(text(f"rust/src/tsl_{slug(profile_render.profile.name)}.rs", content))

    artifacts.append(text("rust/src/lib.rs", _rust_lib(profiles)))
    artifacts.append(text("rust/Cargo.toml", _rust_cargo(profiles, assets)))
    artifacts.append(
        text("rust/tests/smoke.rs", "#[test]\nfn smoke() {\n    assert!(true);\n}\n")
    )
    return artifacts


def rust_verify_profiles(profiles: tuple[ProfileRender, ...]) -> tuple[VerifyProfile, ...]:
    return tuple(
        VerifyProfile(
            profile_name=slug(profile_render.profile.name),
            file_stem=slug(profile_render.profile.name),
            family=profile_render.profile.family,
            rust_target_features=rust_target_features(
                profile_render.profile, profile_render.profile_family
            ),
            rust_target=rust_target(profile_render.profile, profile_render.profile_family),
            rust_linker=rust_linker(profile_render.profile, profile_render.profile_family),
            emulator=_verify_emulator(profile_render.profile),
        )
        for profile_render in profiles
    )


def rust_target_features(
    profile: MachineProfile,
    capability: ProfileFamilyCapability | None = None,
) -> tuple[str, ...]:
    capability = capability or ProfileFamilyCapability(profile.family)
    if not capability.rust_target_features:
        return ()
    return tuple(
        f"+{feature_spelling(feature, profile.alternatives)}"
        for feature in sorted(profile.features)
    )


def rust_target(
    profile: MachineProfile,
    capability: ProfileFamilyCapability | None = None,
) -> str | None:
    capability = capability or ProfileFamilyCapability(profile.family)
    return capability.rust_target


def rust_linker(
    profile: MachineProfile,
    capability: ProfileFamilyCapability | None = None,
) -> str | None:
    capability = capability or ProfileFamilyCapability(profile.family)
    return capability.rust_linker


def _rust_arch_use(emitted_exts: list[str], extensions: Mapping[str, Extension]) -> str:
    modules = {
        module
        for ext in emitted_exts
        if (extension := extensions.get(ext)) is not None
        if (module := rust_arch_module(extension)) is not None
    }
    if not modules:
        return ""
    lines = [
        "#[allow(unused_imports)]",
        *(f"use core::arch::{module}::*;" for module in sorted(modules)),
    ]
    return "\n".join(lines) + "\n"


@dataclass(frozen=True, slots=True)
class _RustVectorRegistration:
    extension_name: str
    type_tag: str
    base_spelling: str
    register_spelling: str
    vector_bits: int


def _verify_emulator(profile: MachineProfile) -> VerifyEmulator | None:
    if profile.emulator is None:
        return None
    return VerifyEmulator(
        kind=profile.emulator.kind,
        profile=profile.emulator.profile,
        args=profile.emulator.args,
    )


def _rust_registrations(
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    extensions: Mapping[str, Extension],
) -> str:
    """Rust extension tag structs + vector trait impls for the used (ext, type) pairs."""

    lines: list[str] = []
    registrations = _rust_vector_registrations(by_primitive, extensions)
    for ext in sorted({registration.extension_name for registration in registrations}):
        extension = extensions.get(ext)
        if extension is not None:
            lines.append(f"pub struct {rust_extension_tag(extension)};")
    for registration in registrations:
        extension = extensions.get(registration.extension_name)
        if extension is None:
            continue
        base = registration.base_spelling
        register = registration.register_spelling
        bits = registration.vector_bits
        mask = _rust_mask_type(extension, base, register)
        imask = _rust_imask_type(extension, base, mask, bits)
        alignment = bits // 8
        lane_count = bits // type_bits(base)
        array = f"array_type<{base}, {lane_count}, {alignment}>"
        lines.append(
            f"impl SimdVector for Simd<{base}, {rust_extension_tag(extension)}> {{ "
            f"type BaseType = {base}; type Extension = {rust_extension_tag(extension)}; "
            f"type RegisterType = {register}; "
            f"type MaskType = {mask}; type ImaskType = {imask}; type Array = {array}; "
            f"type WithBaseType<ToBase> = Simd<ToBase, {rust_extension_tag(extension)}>; "
            f"type WithExtension<ToExtension> = Simd<{base}, ToExtension>; "
            f"const ALIGN: usize = {alignment}; "
            f"fn lane_count() -> usize {{ {lane_count} }} }}"
        )
        lines.append(
            f"impl StaticSimdVector for Simd<{base}, {rust_extension_tag(extension)}> {{ "
            f"const ELEMENT_COUNT: usize = {lane_count}; }}"
        )
    return ("\n".join(lines) + "\n\n") if lines else ""


def _rust_algorithm_module(
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
        "    use crate::tsl_core::{Generic, Scalar, Simd, SimdVector, StaticSimdVector};\n"
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
    primitive_facades = _rust_algorithm_primitive_facades(
        by_primitive,
        reserved_names=_rust_public_function_names(algorithm_wrappers),
    )
    if primitive_facades:
        parts.append(primitive_facades)
    parts.append(algorithm_wrappers)
    return "\n\n" + "\n\n".join(part for part in parts if part) + "\n}\n"


def _rust_algorithm_load_store_impls(
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    extensions: Mapping[str, Extension],
) -> str:
    registrations = _rust_vector_registrations(by_primitive, extensions)
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
    registrations = _rust_vector_registrations(by_primitive, extensions)
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
    registration: _RustVectorRegistration,
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
        f"            + super::detail::primitives::Gather_narrowImpl<{index_vector}, {default_scale}, 1>\n"
        f"            + super::detail::primitives::Gather_narrowImpl<{index_vector}, SCALE, 1>,\n"
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
    registrations = _rust_vector_registrations(by_primitive, extensions)
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
    registrations = _rust_vector_registrations(by_primitive, extensions)
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
    registrations = _rust_vector_registrations(by_primitive, extensions)
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
    registrations = _rust_vector_registrations(by_primitive, extensions)
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
    registrations = _rust_vector_registrations(by_primitive, extensions)
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


def _rust_algorithm_primitive_facades(
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    *,
    reserved_names: frozenset[str],
) -> str:
    parts: list[str] = []
    for primitive_name in sorted(by_primitive):
        function_name = rust_raw_identifier(primitive_name)
        if function_name in reserved_names:
            continue
        specs = by_primitive[primitive_name]
        facade = classify_dataparallel_primitive_facade(primitive_name, specs)
        if facade is None:
            continue
        if facade.kind is DataparallelPrimitiveFacadeKind.CONTIGUOUS_MEMORY:
            parts.append(_rust_algorithm_memory_facade(function_name, facade))
            continue
        shape = facade.shape
        source_type = "FromT" if shape.target is not None else "T"
        source_vec = f"<Policy as VectorFor<Profile, {source_type}>>::Vec"
        target_vec = (
            f"ReboundBase<{source_vec}, ToT>"
            if shape.target is not None
            else None
        )
        params = [
            "        _policy: Policy,",
            *(
                f"        {name}: {_rust_facade_param_type(kind, source_vec, target_vec)},"
                for name, kind in zip(shape.param_names, shape.param_kinds)
            ),
        ]
        args = ", ".join(shape.param_names)
        trait_name = _rust_primitive_trait_name(primitive_name)
        result_type = _rust_facade_result_type(shape.result_kind, target_vec or source_vec)
        function_generics = (
            "Policy, FromT, ToT" if shape.target is not None else "Policy, T"
        )
        target_trait_arg = f"<{target_vec}>" if target_vec is not None else ""
        vec_bound = (
            f"RebindBase<ToT> + super::detail::primitives::{trait_name}{target_trait_arg}"
            if target_vec is not None
            else f"super::detail::primitives::{trait_name}"
        )
        parts.append(
            "\n".join(
                (
                    f"    pub fn {function_name}<{function_generics}>(",
                    *params,
                    f"    ) -> {result_type}",
                    "    where",
                    f"        Policy: VectorFor<Profile, {source_type}>,",
                    f"        {source_vec}: {vec_bound},",
                    "    {",
                    f"        super::{function_name}::<{source_vec}{', ' + target_vec if target_vec is not None else ''}>({args})",
                    "    }",
                )
            )
        )
    return "\n\n".join(parts)


def _rust_algorithm_memory_facade(
    function_name: str,
    facade: DataparallelPrimitiveFacade,
) -> str:
    if function_name == "load":
        return "\n".join(
            (
                "    pub unsafe fn load<Policy, T, const ALIGNED: bool>(",
                "        _policy: Policy,",
                "        ptr: *const T,",
                "    ) -> <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::RegisterType",
                "    where",
                "        Policy: VectorFor<Profile, T>,",
                "        <Policy as VectorFor<Profile, T>>::Vec:",
                "            super::detail::primitives::LoadImpl<ALIGNED>,",
                "    {",
                "        unsafe { super::load::<<Policy as VectorFor<Profile, T>>::Vec, ALIGNED>(ptr) }",
                "    }",
            )
        )
    if function_name == "store":
        return "\n".join(
            (
                "    pub unsafe fn store<Policy, T, const ALIGNED: bool>(",
                "        _policy: Policy,",
                "        ptr: *mut T,",
                "        data: <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::RegisterType,",
                "    )",
                "    where",
                "        Policy: VectorFor<Profile, T>,",
                "        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::RegisterType:",
                "            super::detail::primitives::StoreImplArg<",
                "                <Policy as VectorFor<Profile, T>>::Vec,",
                "                ALIGNED,",
                "            >,",
                "    {",
                "        unsafe { super::store::<<Policy as VectorFor<Profile, T>>::Vec, ALIGNED, _>(ptr, data) }",
                "    }",
            )
        )
    raise AssertionError(f"unsupported Rust memory facade: {function_name}")


def _rust_public_function_names(source: str) -> frozenset[str]:
    return frozenset(re.findall(r"pub (?:unsafe )?fn ([A-Za-z_][A-Za-z0-9_]*)", source))


def _rust_facade_result_type(result_kind: str, vec: str) -> str:
    vec = f"<{vec} as SimdVector>"
    if result_kind == "v":
        return f"{vec}::RegisterType"
    if result_kind == "m":
        return f"{vec}::MaskType"
    if result_kind == "s":
        return f"{vec}::BaseType"
    if result_kind == "usize":
        return "usize"
    raise AssertionError(f"unsupported Rust facade result kind: {result_kind}")


def _rust_facade_param_type(
    param_kind: str, vec: str, target_vec: str | None
) -> str:
    vec = f"<{vec} as SimdVector>"
    if param_kind == "v":
        return f"{vec}::RegisterType"
    if param_kind == "vt" and target_vec is not None:
        return f"<{target_vec} as SimdVector>::RegisterType"
    if param_kind == "m":
        return f"{vec}::MaskType"
    if param_kind == "s":
        return f"{vec}::BaseType"
    raise AssertionError(f"unsupported Rust facade parameter kind: {param_kind}")


def _rust_primitive_trait_name(primitive_name: str) -> str:
    return f"{primitive_name[:1].upper()}{primitive_name[1:]}Impl"


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


def _rust_vector_registrations(
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    extensions: Mapping[str, Extension],
) -> tuple[_RustVectorRegistration, ...]:
    records: dict[tuple[str, str, str, str], _RustVectorRegistration] = {}
    for specs in by_primitive.values():
        for spec in specs:
            _record_rust_vector(
                records,
                extensions,
                spec.extension_name,
                spec.type_tag,
                spec.base_type_spelling,
                spec.register_spelling,
                uses_sized_vector=spec.uses_sized_vector,
            )
            if spec.target is not None:
                _record_rust_vector(
                    records,
                    extensions,
                    spec.target.extension_isa,
                    spec.target.base_tag,
                    spec.target.base_spelling,
                    spec.target.register_spelling,
                    uses_sized_vector=spec.target.uses_sized_vector,
                )
    return tuple(records[key] for key in sorted(records))


def _record_rust_vector(
    records: dict[tuple[str, str, str, str], _RustVectorRegistration],
    extensions: Mapping[str, Extension],
    extension_name: str,
    type_tag: str,
    base_spelling: str,
    register_spelling: str,
    *,
    uses_sized_vector: bool,
) -> None:
    extension = extensions.get(extension_name)
    if (
        extension is None
        or uses_sized_vector
        or extension.family in {"scalar", "generic_like"}
        or extension.vector_bits_kind != "fixed"
        or extension.vector_bits <= 0
        or not extension.supports_backend("rust")
    ):
        return
    key = (extension_name, type_tag, base_spelling, register_spelling)
    records[key] = _RustVectorRegistration(
        extension_name=extension_name,
        type_tag=type_tag,
        base_spelling=base_spelling,
        register_spelling=register_spelling,
        vector_bits=extension.vector_bits,
    )


def _rust_mask_type(extension: Extension | None, base_spelling: str, register: str) -> str:
    """The Rust mask type for one (ext, base) pair."""

    if extension is None or extension.mask_policy.kind != "native_predicate_by_lanes":
        return register
    lanes = extension.vector_bits // type_bits(base_spelling)
    return extension.mask_policy.spelling_for_lanes("rust", max(8, lanes)) or register


def _rust_imask_type(
    extension: Extension | None, base_spelling: str, mask: str, vector_bits: int
) -> str:
    """The Rust integral-mask type for one x86 `Simd<Base, Ext>` registration."""

    kind = extension.imask_policy.kind if extension is not None else "lane_bitmask"
    if kind == "same_as_mask_type":
        return mask
    lanes = vector_bits // type_bits(base_spelling)
    width = 8 if lanes <= 8 else 16 if lanes <= 16 else 32 if lanes <= 32 else 64
    return f"u{width}"


def _rust_lib(profiles: tuple[ProfileRender, ...]) -> str:
    # `non_upper_case_globals` is allowed so an `sImm` immediate can keep its corpus name
    # as a lowercase const-generic, matching the body that uses it.
    lines = [
        "#![allow(dead_code)]",
        "#![allow(non_upper_case_globals)]",
        "",
        "pub mod tsl_core;",
        "pub mod tsl_algorithm;",
        "pub mod tsl_test_core;",
        "pub use tsl_algorithm::dataparallel;",
        "",
    ]
    profile_slugs = tuple(slug(profile_render.profile.name) for profile_render in profiles)
    for profile_slug in profile_slugs:
        lines.append(f'#[cfg(feature = "{profile_slug}")]')
        lines.append(f"pub mod tsl_{profile_slug};")
        lines.append(f"#[cfg({_rust_selected_profile_cfg(profile_slug, profile_slugs)})]")
        lines.append(f"pub use crate::tsl_{profile_slug} as profile;")
        lines.append("")
    return "\n".join(lines)


def _rust_selected_profile_cfg(profile_slug: str, profile_slugs: tuple[str, ...]) -> str:
    other_slugs = tuple(slug for slug in profile_slugs if slug != profile_slug)
    if not other_slugs:
        return f'feature = "{profile_slug}"'
    others = ", ".join(f'feature = "{other}"' for other in other_slugs)
    return f'all(feature = "{profile_slug}", not(any({others})))'


def _rust_cargo(profiles: tuple[ProfileRender, ...], assets: RenderAssets) -> str:
    default = slug(profiles[0].profile.name) if profiles else "scalar"
    features = [f'default = ["{default}"]']
    features.extend(f"{slug(profile_render.profile.name)} = []" for profile_render in profiles)
    # Opt-in feature that compiles+runs the generated value tests (parity with the C++ ctest gate).
    features.append("value_tests = []")
    return assets.fill("rust_cargo.toml.tmpl", features="\n".join(features))
