"""End-to-end: the generated project uses the template/trait specialization layout."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tslc.api import generate_project
from tslc.backend.primitive_facade import (
    DataparallelPrimitiveFacadeKind,
    classify_dataparallel_primitive_facade,
)
from tslc.diagnostics import has_errors
from tslc.lower.lowerer import LoweredSpecialization
from tslc.lower.target_vectors import TargetVector
from tslc.render.model import LoweredBody


def _generate(data_root: Path, machine_profiles_path: Path):
    return generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=[
            "add",
            "mul",
            "hadd",
            "count_matches",
            "load",
            "store",
            "cast",
            "reinterpret",
            "less_than",
            "unequal_zero",
            "mask_true",
            "mask_binary_not",
            "mask_binary_and",
            "mask_population_count",
        ],
        profiles=["scalar", "sse2", "avx", "avx2", "skylake"],
    )


@pytest.fixture(scope="module")
def specialization_result(data_root: Path, machine_profiles_path: Path):
    return _generate(data_root, machine_profiles_path)


@pytest.fixture(scope="module")
def specialization_artifacts(specialization_result) -> dict[str, str]:
    return {
        artifact.logical_path: artifact.content
        for artifact in specialization_result.artifacts.artifacts
    }


def _facade_spec(
    primitive_name: str,
    result_kind: str,
    param_kinds: tuple[str, ...],
    *,
    extension_name: str = "avx2",
    axis: tuple[tuple[str, str], ...] = (),
    target: TargetVector | None = None,
) -> LoweredSpecialization:
    return LoweredSpecialization(
        backend_id="cpp",
        primitive_name=primitive_name,
        source_primitive_name=primitive_name,
        extension_name=extension_name,
        type_tag="si32",
        base_type_spelling="int32_t",
        register_spelling="__m256i",
        result_kind=result_kind,
        param_names=tuple(f"p{i}" for i in range(len(param_kinds))),
        param_kinds=param_kinds,
        body=LoweredBody.from_text("", backend_id="cpp"),
        axis=axis,
        target=target,
    )


def test_dataparallel_primitive_facade_descriptor_classifies_shared_policy_shapes() -> None:
    add = classify_dataparallel_primitive_facade(
        "add", (_facade_spec("add", "v", ("v", "v")),)
    )
    assert add is not None
    assert add.kind is DataparallelPrimitiveFacadeKind.REGISTER_MASK_OR_REDUCTION
    assert add.shape.param_kinds == ("v", "v")

    store = classify_dataparallel_primitive_facade(
        "store",
        (
            _facade_spec(
                "store", "void", ("ptr", "s"), axis=(("aligned", "false"),)
            ),
            _facade_spec(
                "store", "void", ("ptr", "v"), axis=(("aligned", "true"),)
            ),
        ),
    )
    assert store is not None
    assert store.kind is DataparallelPrimitiveFacadeKind.CONTIGUOUS_MEMORY
    assert store.shape.param_kinds == ("ptr", "v")

    cast = classify_dataparallel_primitive_facade(
        "cast",
        (
            _facade_spec(
                "cast",
                "v",
                ("v",),
                extension_name="avx2",
                target=TargetVector(
                    vector_spelling="Simd<uint32_t, avx2>",
                    register_spelling="__m256i",
                    extension_isa="avx2",
                    base_tag="ui32",
                    base_spelling="uint32_t",
                ),
            ),
        ),
    )
    assert cast is not None
    assert cast.kind is DataparallelPrimitiveFacadeKind.TARGET_BASE_CONVERSION

    assert (
        classify_dataparallel_primitive_facade(
            "blend", (_facade_spec("blend", "v", ("m", "v", "v")),)
        )
        is None
    )


def test_artifact_layout(specialization_result) -> None:
    result = specialization_result
    assert not has_errors(result.diagnostics), result.diagnostics
    paths = {a.logical_path for a in result.artifacts.artifacts}
    # static cores, per-profile headers, top-level dispatch, per-profile smokes.
    assert {
        "cpp/include/tsl_core.hpp",
        "cpp/include/tsl_primitives.hpp",
        "cpp/include/tsl_dataparallel.hpp",
        "cpp/include/tsl_inferred_simd.hpp",
        "cpp/include/tsl_algorithm_tags.hpp",
        "cpp/include/tsl_algorithm_detail_core.hpp",
        "cpp/include/tsl_algorithm_detail_mask.hpp",
        "cpp/include/tsl_algorithm_detail_loops.hpp",
        "cpp/include/tsl_algorithm.hpp",
        "cpp/include/tsl_x86_traits.hpp",
        "cpp/include/tsl.hpp",
        "cpp/include/tsl_avx2.hpp",
        "cpp/include/tsl_scalar.hpp",
        "cpp/docs/input/tsl_api_docs.hpp",
        "docs/specializations/specializations.json",
        "cpp/tests/smoke_avx2.cpp",
        "rust/src/tsl_core.rs",
        "rust/src/tsl_algorithm.rs",
        "rust/src/tsl_avx2.rs",
        "rust/src/lib.rs",
    } <= paths
    assert "docs/specializations/index.html" not in paths
    assert "docs/specializations/app.js" not in paths
    assert "docs/specializations/styles.css" not in paths


def test_cpp_core_vectors_expose_metadata_constants(
    specialization_artifacts: dict[str, str]
) -> None:
    core = specialization_artifacts["cpp/include/tsl_core.hpp"]

    assert "enum class implementation_state" in core
    assert "template <auto Value>" in core
    assert "struct implementation_state_of" in core
    assert "inline constexpr implementation_state implementation_state_v" in core
    assert "static constexpr bool has_static_lane_count_v = true;" in core
    assert "using extension_type = scalar;" in core
    assert "using with_base_type = simd<ToBase, scalar>;" in core
    assert "using with_extension = simd<T, ToExtension>;" in core
    assert "static constexpr std::size_t lane_count_v = 1;" in core
    assert "static constexpr std::size_t lane_count_v = LANES;" in core
    assert "using extension_type = generic<LANES>;" in core
    assert "using with_base_type = simd<ToBase, generic<LANES>>;" in core
    assert "static constexpr std::size_t vector_element_count = lane_count_v;" in core
    assert "static constexpr std::size_t lane_count() noexcept" in core
    assert "static constexpr std::size_t vector_alignment = alignof(T);" in core
    assert "static constexpr std::size_t simd_register_alignment_v = vector_alignment;" in core
    assert (
        "static constexpr std::size_t vector_alignment = alignof(register_type);"
        in core
    )


def test_cpp_implementation_state_api(
    specialization_artifacts: dict[str, str]
) -> None:
    tags = specialization_artifacts["cpp/include/tsl_primitives.hpp"]
    avx2 = specialization_artifacts["cpp/include/tsl_avx2.hpp"]
    scalar = specialization_artifacts["cpp/include/tsl_scalar.hpp"]

    assert "struct add {};" in tags
    assert "struct add_mask {};" in tags
    assert '#include "tsl_primitives.hpp"' in avx2
    assert (
        "struct implementation_state_of<primitive::add, Vec> {\n"
        "    static constexpr implementation_state value = "
        "detail::primitives::add_impl<Vec>::implementation_state;\n"
        "};"
        in avx2
    )
    assert (
        "struct implementation_state_of<primitive::load, Vec, value_arg<Aligned>>"
        in avx2
    )
    assert (
        "struct implementation_state_of<primitive::store, Vec, value_arg<Aligned>>"
        in avx2
    )
    assert (
        "struct implementation_state_of<primitive::reinterpret, Vec, ToVec>"
        in avx2
    )
    assert (
        "struct implementation_state_of<primitive::gather_narrow, Vec, "
        "IndicesType, value_arg<scale>, value_arg<N>>"
        in avx2
    )
    assert (
        "struct add_impl<tsl::simd<int32_t, tsl::avx2>> {\n"
        "    static constexpr ::tsl::implementation_state implementation_state = "
        "::tsl::implementation_state::native;"
        in avx2
    )
    assert (
        "struct add_impl<tsl::simd<int32_t, tsl::scalar>> {\n"
        "    static constexpr ::tsl::implementation_state implementation_state = "
        "::tsl::implementation_state::fallback;"
        in scalar
    )


def test_cpp_dataparallel_helper_owns_policy_vocabulary(
    specialization_artifacts: dict[str, str]
) -> None:
    dataparallel = specialization_artifacts["cpp/include/tsl_dataparallel.hpp"]
    inferred = specialization_artifacts["cpp/include/tsl_inferred_simd.hpp"]

    assert "namespace tsl::dataparallel" in dataparallel
    assert "struct native" in dataparallel
    assert "struct fixed" in dataparallel
    assert "struct generic" in dataparallel
    assert "tsl::dataparallel::fixed<N> requires N > 0" in dataparallel
    assert "tsl::dataparallel::generic<N> requires N > 0" in dataparallel
    assert "template <class Policy, class T>\nstruct simd_for;" in dataparallel
    assert "struct simd_for<native, T>" in dataparallel
    assert "struct simd_for<fixed<1>, T>" in dataparallel
    assert "struct simd_for<generic<N>, T>" in dataparallel
    assert "using simd_for_t = typename simd_for<Policy, T>::type;" in dataparallel
    assert "using register_t = typename simd_for_t<Policy, T>::register_type;" in dataparallel
    assert "using rebind_base_t = typename Vec::template with_base_type<ToT>;" in dataparallel
    assert "using rebind_simd_for_t = rebind_base_t<simd_for_t<Policy, FromT>, ToT>;" in dataparallel
    assert "tsl::avx2" not in dataparallel
    assert "tsl::sse" not in dataparallel

    assert "`tsl::dataparallel::simd_for_t<Policy, T>`" in inferred
    assert "using native_simd_t = typename detail::native_simd" in inferred
    assert "using inferred_simd_t = typename detail::inferred_simd" in inferred


def test_cpp_algorithm_helper_is_shipped_through_dispatch_header(
    specialization_artifacts: dict[str, str]
) -> None:
    umbrella = specialization_artifacts["cpp/include/tsl_algorithm.hpp"]
    helper = "\n".join(
        specialization_artifacts[f"cpp/include/{header}"]
        for header in (
            "tsl_dataparallel.hpp",
            "tsl_algorithm_tags.hpp",
            "tsl_algorithm_detail_core.hpp",
            "tsl_algorithm_detail_mask.hpp",
            "tsl_algorithm_detail_loops.hpp",
            "tsl_algorithm.hpp",
        )
    )
    dispatch = specialization_artifacts["cpp/include/tsl.hpp"]
    avx2 = specialization_artifacts["cpp/include/tsl_avx2.hpp"]

    assert '#include "tsl_algorithm_detail_loops.hpp"' in umbrella
    assert "namespace tsl::algo" in helper
    assert "#include <iterator>" in helper
    assert "template <class Vec>\nstruct vector_tag" in helper
    assert "namespace tsl::dataparallel" in helper
    assert "struct native" in helper
    assert "struct fixed" in helper
    assert "struct generic" in helper
    assert "tsl::dataparallel::fixed<N> requires N > 0" in helper
    assert "dataparallel::simd_for_t<Parallelism, T>" in helper
    assert "class Alignment = alignment::detect" in helper
    assert "struct peel_to_aligned {};" in helper
    assert "struct assume_inputs_aligned {};" in helper
    assert "struct assume_output_aligned {};" in helper
    assert "is_supported_transform_alignment_policy" in helper
    assert "has_same_alignment_residue" in helper
    assert "range_data" in helper
    assert "std::size(range)" in helper
    assert "void for_each_chunk(Op&& op" in helper
    assert "void for_each_chunk(Op&& op, Range& data)" in helper
    assert "void transform_unary(Op&& op" in helper
    assert "void transform_unary(Op&& op, const InputRange& input" in helper
    assert "transform_unary_loop_peel_to_aligned" in helper
    assert "alignment::assume_inputs_aligned" in helper
    assert "alignment::assume_output_aligned" in helper
    assert "std::size_t ParallelN" in helper
    assert "transform_unary<::tsl::dataparallel::fixed<ParallelN>, Alignment>" in helper
    assert "void transform_binary(" in helper
    assert "transform_binary_loop" in helper
    assert "transform_binary_loop_peel_to_aligned" in helper
    assert "transform_binary<::tsl::dataparallel::fixed<ParallelN>, Alignment>" in helper
    assert "namespace mask_layout" in helper
    assert (
        "struct integral {};\nstruct native {};\nstruct bytes {};\nstruct bits {};"
        in helper
    )
    assert "fixed_native_mask_type" in helper
    assert "native_mask_chunk_count" in helper
    assert "fixed_byte_mask_type" in helper
    assert "byte_mask_count" in helper
    assert "fixed_bit_mask_type" in helper
    assert "bit_mask_count" in helper
    assert "std::size_t predicate_unary(" in helper
    assert "std::size_t predicate_binary(" in helper
    assert "void transform_where_unary(" in helper
    assert "void transform_where_binary(" in helper
    assert "void transform_masked_unary(" in helper
    assert "void transform_masked_binary(" in helper
    assert "std::size_t select_unary(" in helper
    assert "std::size_t select_binary(" in helper
    assert "std::size_t select_masked_unary(" in helper
    assert "std::size_t select_masked_binary(" in helper
    assert "std::size_t select_indices_unary(" in helper
    assert "std::size_t select_indices_binary(" in helper
    assert "std::size_t select_masked_indices_unary(" in helper
    assert "std::size_t select_masked_indices_binary(" in helper
    assert "is_selection_index" in helper
    assert (
        "selection-vector output indices must use an unsigned integral row-id type"
        in helper
    )
    assert "std::size_t select_selected_indices_unary(" in helper
    assert "std::size_t select_selected_indices_binary(" in helper
    assert "append_selected_indices_from_mask" in helper
    assert "void transform_selected_unary(" in helper
    assert "void transform_selected_binary(" in helper
    assert "auto aggregate_selected_unary(" in helper
    assert "auto aggregate_selected_binary(" in helper
    assert "void consume_selected_unary(" in helper
    assert "void consume_selected_binary(" in helper
    assert (
        "selection-vector input indices must use an unsigned integral row-id type"
        in helper
    )
    assert "vector_for_selected_rows" in helper
    assert "load_selected_vector" in helper
    assert "gather_narrow" in helper
    assert "std::size_t Scale = 0" in helper
    assert "std::size_t count_unary(" in helper
    assert "std::size_t count_binary(" in helper
    assert "std::size_t count_masked_unary(" in helper
    assert "std::size_t count_masked_binary(" in helper
    assert "std::size_t count_selected_unary(" in helper
    assert "std::size_t count_selected_binary(" in helper
    assert "auto aggregate_unary(" in helper
    assert "auto aggregate_binary(" in helper
    assert "auto aggregate_masked_unary(" in helper
    assert "auto aggregate_masked_binary(" in helper
    assert "void consume_unary(" in helper
    assert "void consume_binary(" in helper
    assert "void consume_masked_unary(" in helper
    assert "void consume_masked_binary(" in helper
    assert '#include "tsl_algorithm.hpp"' in dispatch
    assert "inline typename Vec::register_type load(" in avx2
    assert "inline void store(" in avx2
    assert "inline void store_mask(" in avx2
    assert "inline typename Vec::imask_type to_integral(" in avx2
    assert "inline typename Vec::mask_type to_mask(" in avx2
    assert "inline typename Vec::register_type gather_narrow(" in avx2
    assert "inline typename Vec::register_type gather(" not in avx2
    assert "inline void compress_store(" in avx2
    assert "inline std::size_t mask_population_count(" in avx2
    assert "inline typename Vec::mask_type mask_binary_and(" in avx2


def test_rust_algorithm_helper_is_shipped_with_profile_mappings(
    specialization_artifacts: dict[str, str]
) -> None:
    helper = specialization_artifacts["rust/src/tsl_algorithm.rs"]
    lib = specialization_artifacts["rust/src/lib.rs"]
    cargo = specialization_artifacts["rust/Cargo.toml"]
    avx2 = specialization_artifacts["rust/src/tsl_avx2.rs"]

    assert 'name = "tsl"' in cargo
    assert "pub mod tsl_algorithm;" in lib
    assert "pub use tsl_algorithm::dataparallel;" in lib
    assert "pub mod tsl_avx2;" in lib
    assert '#[cfg(all(feature = "avx2", not(any(' in lib
    assert "pub use crate::tsl_avx2 as profile;" in lib
    assert "pub mod dataparallel" in helper
    assert "pub struct Native" in helper
    assert "pub struct Fixed<const N: usize>" in helper
    assert "pub struct Generic<const N: usize>" in helper
    assert "pub mod mask_layout" in helper
    assert "pub struct Integral" in helper
    assert "pub struct Bytes" in helper
    assert "pub struct Bits" in helper
    assert "pub trait VectorFor<Profile, T>" in helper
    assert "pub trait RebindBase<ToBase>: SimdVector" in helper
    assert "pub type ReboundBase<V, ToBase> = <V as RebindBase<ToBase>>::Vec;" in helper
    assert "pub trait SelectedLoad<V: StaticSimdVector, const SCALE: u32>" in helper
    assert "pub trait IntegralMaskWord" in helper
    assert "pub trait IntegralMask<V: StaticSimdVector>" in helper
    assert "pub trait MaskFromIntegral<V: StaticSimdVector>" in helper
    assert "pub trait MaskLayout<Profile, V: StaticSimdVector>" in helper
    assert "pub trait MaskedStore<V: StaticSimdVector>" in helper
    assert "pub trait CompressStore<V: StaticSimdVector>" in helper
    assert "pub trait MaskPopulationCount<V: StaticSimdVector>" in helper
    assert "pub trait UnaryKernel<V: StaticSimdVector>" in helper
    assert "pub trait BinaryKernel<V: StaticSimdVector>" in helper
    assert "pub trait UnaryPredicateKernel<V: StaticSimdVector>" in helper
    assert "pub trait BinaryPredicateKernel<V: StaticSimdVector>" in helper
    assert "pub trait MaskedUnaryKernel<V: StaticSimdVector>" in helper
    assert "pub trait MaskedBinaryKernel<V: StaticSimdVector>" in helper
    assert "pub trait UnaryConsumeKernel<V: StaticSimdVector>" in helper
    assert "pub trait BinaryConsumeKernel<V: StaticSimdVector>" in helper
    assert "pub trait MaskedUnaryConsumeKernel<V: StaticSimdVector>" in helper
    assert "pub trait MaskedBinaryConsumeKernel<V: StaticSimdVector>" in helper
    assert "pub trait UnaryAggregateKernel<V: StaticSimdVector>" in helper
    assert "pub trait BinaryAggregateKernel<V: StaticSimdVector>" in helper
    assert "pub trait MaskedUnaryAggregateKernel<V: StaticSimdVector>" in helper
    assert "pub trait MaskedBinaryAggregateKernel<V: StaticSimdVector>" in helper
    assert "pub trait ChunkKernel<V: StaticSimdVector>" in helper
    assert "pub fn for_each_chunk<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn for_each_chunk_raw<Profile, Policy, Op, T>" in helper
    assert "pub fn transform_unary<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn transform_unary_raw<Profile, Policy, Op, T>" in helper
    assert "pub fn transform_binary<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn transform_binary_raw<Profile, Policy, Op, T>" in helper
    assert "pub fn integral_mask_chunk_count<Profile, Policy, T>" in helper
    assert "pub fn mask_chunk_count<Profile, Policy, Layout, T>" in helper
    assert "pub fn native_mask_chunk_count<Profile, Policy, T>" in helper
    assert "pub fn byte_mask_count<Profile, Policy, T>" in helper
    assert "pub fn bit_mask_count<Profile, Policy, T>" in helper
    assert "pub fn predicate_unary<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn predicate_unary_raw<Profile, Policy, Op, T>" in helper
    assert "pub fn predicate_binary<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn predicate_binary_raw<Profile, Policy, Op, T>" in helper
    assert "pub fn predicate_binary_mask_layout<Profile, Policy, Layout, Op, T>" in helper
    assert "pub unsafe fn predicate_binary_mask_layout_raw<" in helper
    assert "pub fn count_unary<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn count_unary_raw<Profile, Policy, Op, T>" in helper
    assert "pub fn count_binary<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn count_binary_raw<Profile, Policy, Op, T>" in helper
    assert "pub fn count_masked_unary<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn count_masked_unary_raw<Profile, Policy, Op, T>" in helper
    assert "pub fn count_masked_binary<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn count_masked_binary_raw<Profile, Policy, Op, T>" in helper
    assert "pub fn count_masked_unary_mask_layout<Profile, Policy, Layout, Op, T>" in helper
    assert "pub unsafe fn count_masked_unary_mask_layout_raw<" in helper
    assert "pub fn count_masked_binary_mask_layout<Profile, Policy, Layout, Op, T>" in helper
    assert "pub unsafe fn count_masked_binary_mask_layout_raw<" in helper
    assert "pub fn count_selected_unary<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn count_selected_unary_raw<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn count_selected_unary_scaled_raw<" in helper
    assert "pub fn count_selected_binary<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn count_selected_binary_raw<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn count_selected_binary_scaled_raw<" in helper
    assert "pub fn select_unary<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn select_unary_raw<Profile, Policy, Op, T>" in helper
    assert "pub fn select_binary<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn select_binary_raw<Profile, Policy, Op, T>" in helper
    assert "pub fn select_masked_unary<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn select_masked_unary_raw<Profile, Policy, Op, T>" in helper
    assert "pub fn select_masked_binary<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn select_masked_binary_raw<Profile, Policy, Op, T>" in helper
    assert "pub fn select_masked_unary_mask_layout<Profile, Policy, Layout, Op, T>" in helper
    assert "pub unsafe fn select_masked_unary_mask_layout_raw<" in helper
    assert "pub fn select_masked_binary_mask_layout<Profile, Policy, Layout, Op, T>" in helper
    assert "pub unsafe fn select_masked_binary_mask_layout_raw<" in helper
    assert "pub fn select_indices_unary<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn select_indices_unary_raw<Profile, Policy, Op, T>" in helper
    assert "pub fn select_indices_binary<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn select_indices_binary_raw<Profile, Policy, Op, T>" in helper
    assert "pub fn select_masked_indices_unary<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn select_masked_indices_unary_raw<Profile, Policy, Op, T>" in helper
    assert "pub fn select_masked_indices_binary<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn select_masked_indices_binary_raw<Profile, Policy, Op, T>" in helper
    assert "pub fn select_masked_indices_unary_mask_layout<Profile, Policy, Layout, Op, T>" in helper
    assert "pub unsafe fn select_masked_indices_unary_mask_layout_raw<" in helper
    assert "pub fn select_masked_indices_binary_mask_layout<Profile, Policy, Layout, Op, T>" in helper
    assert "pub unsafe fn select_masked_indices_binary_mask_layout_raw<" in helper
    assert "pub fn select_selected_indices_unary<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn select_selected_indices_unary_raw<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn select_selected_indices_unary_scaled_raw<" in helper
    assert "pub fn select_selected_indices_binary<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn select_selected_indices_binary_raw<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn select_selected_indices_binary_scaled_raw<" in helper
    assert "pub fn transform_selected_unary<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn transform_selected_unary_raw<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn transform_selected_unary_scaled_raw<" in helper
    assert "pub fn transform_selected_binary<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn transform_selected_binary_raw<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn transform_selected_binary_scaled_raw<" in helper
    assert "pub fn consume_selected_unary<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn consume_selected_unary_raw<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn consume_selected_unary_scaled_raw<" in helper
    assert "pub fn consume_selected_binary<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn consume_selected_binary_raw<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn consume_selected_binary_scaled_raw<" in helper
    assert "pub fn aggregate_selected_unary<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn aggregate_selected_unary_raw<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn aggregate_selected_unary_scaled_raw<" in helper
    assert "pub fn aggregate_selected_binary<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn aggregate_selected_binary_raw<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn aggregate_selected_binary_scaled_raw<" in helper
    assert "pub fn transform_where_unary<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn transform_where_unary_raw<Profile, Policy, Op, T>" in helper
    assert "pub fn transform_where_unary_mask_layout<Profile, Policy, Layout, Op, T>" in helper
    assert "pub unsafe fn transform_where_unary_mask_layout_raw<" in helper
    assert "pub fn transform_where_binary<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn transform_where_binary_raw<Profile, Policy, Op, T>" in helper
    assert "pub fn transform_masked_unary<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn transform_masked_unary_raw<Profile, Policy, Op, T>" in helper
    assert "pub fn transform_masked_binary<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn transform_masked_binary_raw<Profile, Policy, Op, T>" in helper
    assert "pub fn transform_masked_binary_mask_layout<Profile, Policy, Layout, Op, T>" in helper
    assert "pub unsafe fn transform_masked_binary_mask_layout_raw<" in helper
    assert "pub fn consume_unary<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn consume_unary_raw<Profile, Policy, Op, T>" in helper
    assert "pub fn consume_binary<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn consume_binary_raw<Profile, Policy, Op, T>" in helper
    assert "pub fn consume_masked_unary<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn consume_masked_unary_raw<Profile, Policy, Op, T>" in helper
    assert "pub fn consume_masked_binary<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn consume_masked_binary_raw<Profile, Policy, Op, T>" in helper
    assert "pub fn aggregate_unary<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn aggregate_unary_raw<Profile, Policy, Op, T>" in helper
    assert "pub fn aggregate_binary<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn aggregate_binary_raw<Profile, Policy, Op, T>" in helper
    assert "pub fn aggregate_masked_unary<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn aggregate_masked_unary_raw<Profile, Policy, Op, T>" in helper
    assert "pub fn aggregate_masked_binary<Profile, Policy, Op, T>" in helper
    assert "pub unsafe fn aggregate_masked_binary_raw<Profile, Policy, Op, T>" in helper

    assert "pub mod algo" in avx2
    assert "BinaryAggregateKernel" in avx2
    assert "BinaryConsumeKernel" in avx2
    assert "UnaryAggregateKernel" in avx2
    assert "UnaryConsumeKernel" in avx2
    assert "BinaryPredicateKernel" in avx2
    assert "UnaryPredicateKernel" in avx2
    assert "MaskedBinaryKernel" in avx2
    assert "MaskedUnaryKernel" in avx2
    assert "MaskedBinaryAggregateKernel" in avx2
    assert "MaskedUnaryAggregateKernel" in avx2
    assert "MaskedBinaryConsumeKernel" in avx2
    assert "MaskedUnaryConsumeKernel" in avx2
    assert "ChunkKernel" in avx2
    assert "mask_layout" in avx2
    assert "MaskLayout" in avx2
    assert "SelectedLoad" in avx2
    assert "pub fn for_each_chunk<Policy, Op, T>" in avx2
    assert "pub fn transform_binary<Policy, Op, T>" in avx2
    assert "pub fn integral_mask_chunk_count<Policy, T>" in avx2
    assert "pub fn native_mask_chunk_count<Policy, T>" in avx2
    assert "pub fn byte_mask_count<Policy, T>" in avx2
    assert "pub fn bit_mask_count<Policy, T>" in avx2
    assert "pub fn predicate_unary<Policy, Op, T>" in avx2
    assert "pub fn predicate_binary<Policy, Op, T>" in avx2
    assert "pub fn predicate_binary_mask_layout<Policy, Layout, Op, T>" in avx2
    assert "pub fn count_unary<Policy, Op, T>" in avx2
    assert "pub fn count_binary<Policy, Op, T>" in avx2
    assert "pub fn count_masked_unary<Policy, Op, T>" in avx2
    assert "pub fn count_masked_binary<Policy, Op, T>" in avx2
    assert "pub fn count_masked_unary_mask_layout<Policy, Layout, Op, T>" in avx2
    assert "pub fn count_masked_binary_mask_layout<Policy, Layout, Op, T>" in avx2
    assert "pub fn count_selected_unary<Policy, Op, T>" in avx2
    assert "pub fn count_selected_binary<Policy, Op, T>" in avx2
    assert "pub fn select_unary<Policy, Op, T>" in avx2
    assert "pub fn select_binary<Policy, Op, T>" in avx2
    assert "pub fn select_masked_unary<Policy, Op, T>" in avx2
    assert "pub fn select_masked_binary<Policy, Op, T>" in avx2
    assert "pub fn select_masked_unary_mask_layout<Policy, Layout, Op, T>" in avx2
    assert "pub fn select_masked_binary_mask_layout<Policy, Layout, Op, T>" in avx2
    assert "pub fn select_indices_unary<Policy, Op, T>" in avx2
    assert "pub fn select_indices_binary<Policy, Op, T>" in avx2
    assert "pub fn select_masked_indices_unary<Policy, Op, T>" in avx2
    assert "pub fn select_masked_indices_binary<Policy, Op, T>" in avx2
    assert "pub fn select_masked_indices_unary_mask_layout<Policy, Layout, Op, T>" in avx2
    assert "pub fn select_masked_indices_binary_mask_layout<Policy, Layout, Op, T>" in avx2
    assert "pub fn select_selected_indices_unary<Policy, Op, T>" in avx2
    assert "pub fn select_selected_indices_binary<Policy, Op, T>" in avx2
    assert "pub fn transform_selected_unary<Policy, Op, T>" in avx2
    assert "pub fn transform_selected_binary<Policy, Op, T>" in avx2
    assert "pub fn consume_selected_unary<Policy, Op, T>" in avx2
    assert "pub fn consume_selected_binary<Policy, Op, T>" in avx2
    assert "pub fn aggregate_selected_unary<Policy, Op, T>" in avx2
    assert "pub fn aggregate_selected_binary<Policy, Op, T>" in avx2
    assert "pub fn transform_where_unary<Policy, Op, T>" in avx2
    assert "pub fn transform_where_unary_mask_layout<Policy, Layout, Op, T>" in avx2
    assert "pub fn transform_where_binary<Policy, Op, T>" in avx2
    assert "pub fn transform_masked_unary<Policy, Op, T>" in avx2
    assert "pub fn transform_masked_binary<Policy, Op, T>" in avx2
    assert "pub fn transform_masked_binary_mask_layout<Policy, Layout, Op, T>" in avx2
    assert "pub fn consume_unary<Policy, Op, T>" in avx2
    assert "pub fn consume_binary<Policy, Op, T>" in avx2
    assert "pub fn consume_masked_unary<Policy, Op, T>" in avx2
    assert "pub fn consume_masked_binary<Policy, Op, T>" in avx2
    assert "pub fn aggregate_unary<Policy, Op, T>" in avx2
    assert "pub fn aggregate_binary<Policy, Op, T>" in avx2
    assert "pub fn aggregate_masked_unary<Policy, Op, T>" in avx2
    assert "pub fn aggregate_masked_binary<Policy, Op, T>" in avx2
    assert "pub use crate::tsl_algorithm::{" in avx2
    assert "mask_layout, BinaryAggregateKernel" in avx2
    assert "parallelism" not in avx2
    assert "impl VectorFor<Profile, i32> for dataparallel::Fixed<1>" in avx2
    assert "type Vec = Simd<i32, Scalar>;" in avx2
    assert "impl VectorFor<Profile, i32> for dataparallel::Fixed<4>" in avx2
    assert "type Vec = Simd<i32, super::Sse>;" in avx2
    assert "impl VectorFor<Profile, i32> for dataparallel::Fixed<8>" in avx2
    assert "type Vec = Simd<i32, super::Avx2>;" in avx2
    assert "impl VectorFor<Profile, i32> for dataparallel::Native" in avx2
    assert "pub fn add<Policy, T>(" in avx2
    assert "_policy: Policy" in avx2
    assert "Policy: VectorFor<Profile, T>" in avx2
    assert (
        "<Policy as VectorFor<Profile, T>>::Vec: super::detail::primitives::AddImpl"
        in avx2
    )
    assert (
        "super::add::<<Policy as VectorFor<Profile, T>>::Vec>(left, right)"
        in avx2
    )
    assert "pub fn mul<Policy, T>(" in avx2
    assert (
        "<Policy as VectorFor<Profile, T>>::Vec: super::detail::primitives::MulImpl"
        in avx2
    )
    assert (
        "super::mul::<<Policy as VectorFor<Profile, T>>::Vec>(factor1, factor2)"
        in avx2
    )
    assert "pub fn less_than<Policy, T>(" in avx2
    assert (
        ") -> <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::MaskType"
        in avx2
    )
    assert (
        "<Policy as VectorFor<Profile, T>>::Vec: super::detail::primitives::Less_thanImpl"
        in avx2
    )
    assert (
        "super::less_than::<<Policy as VectorFor<Profile, T>>::Vec>(left, right)"
        in avx2
    )
    assert "pub fn unequal_zero<Policy, T>(" in avx2
    assert (
        "<Policy as VectorFor<Profile, T>>::Vec: super::detail::primitives::Unequal_zeroImpl"
        in avx2
    )
    assert "super::unequal_zero::<<Policy as VectorFor<Profile, T>>::Vec>(data)" in avx2
    assert "pub fn mask_true<Policy, T>(" in avx2
    assert (
        "<Policy as VectorFor<Profile, T>>::Vec: super::detail::primitives::Mask_trueImpl"
        in avx2
    )
    assert "super::mask_true::<<Policy as VectorFor<Profile, T>>::Vec>()" in avx2
    assert "pub fn mask_binary_not<Policy, T>(" in avx2
    assert (
        "mask: <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::MaskType,"
        in avx2
    )
    assert (
        "<Policy as VectorFor<Profile, T>>::Vec: super::detail::primitives::Mask_binary_notImpl"
        in avx2
    )
    assert "super::mask_binary_not::<<Policy as VectorFor<Profile, T>>::Vec>(mask)" in avx2
    assert "pub fn mask_binary_and<Policy, T>(" in avx2
    assert (
        "mask_a: <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::MaskType,"
        in avx2
    )
    assert (
        "mask_b: <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::MaskType,"
        in avx2
    )
    assert (
        "<Policy as VectorFor<Profile, T>>::Vec: super::detail::primitives::Mask_binary_andImpl"
        in avx2
    )
    assert (
        "super::mask_binary_and::<<Policy as VectorFor<Profile, T>>::Vec>(mask_a, mask_b)"
        in avx2
    )
    assert "pub fn hadd<Policy, T>(" in avx2
    assert ") -> <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::BaseType" in avx2
    assert (
        "<Policy as VectorFor<Profile, T>>::Vec: super::detail::primitives::HaddImpl"
        in avx2
    )
    assert "super::hadd::<<Policy as VectorFor<Profile, T>>::Vec>(vec)" in avx2
    assert "pub fn count_matches<Policy, T>(" in avx2
    assert (
        "value: <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::BaseType,"
        in avx2
    )
    assert (
        "<Policy as VectorFor<Profile, T>>::Vec: super::detail::primitives::Count_matchesImpl"
        in avx2
    )
    assert "super::count_matches::<<Policy as VectorFor<Profile, T>>::Vec>(data, value)" in avx2
    assert "pub fn mask_population_count<Policy, T>(" in avx2
    assert (
        "<Policy as VectorFor<Profile, T>>::Vec: super::detail::primitives::Mask_population_countImpl"
        in avx2
    )
    assert (
        "super::mask_population_count::<<Policy as VectorFor<Profile, T>>::Vec>(mask)"
        in avx2
    )
    assert "pub fn cast<Policy, FromT, ToT>(" in avx2
    assert (
        ") -> <ReboundBase<<Policy as VectorFor<Profile, FromT>>::Vec, ToT> as SimdVector>::RegisterType"
        in avx2
    )
    assert (
        "<Policy as VectorFor<Profile, FromT>>::Vec: RebindBase<ToT>"
        in avx2
    )
    assert "super::detail::primitives::CastImpl<" in avx2
    assert "ReboundBase<<Policy as VectorFor<Profile, FromT>>::Vec, ToT>" in avx2
    assert "super::cast::<" in avx2
    assert "pub fn reinterpret<Policy, FromT, ToT>(" in avx2
    assert "super::detail::primitives::ReinterpretImpl<" in avx2
    assert "super::reinterpret::<" in avx2
    assert "pub unsafe fn load<Policy, T, const ALIGNED: bool>(" in avx2
    assert "super::detail::primitives::LoadImpl<ALIGNED>" in avx2
    assert (
        "unsafe { super::load::<<Policy as VectorFor<Profile, T>>::Vec, ALIGNED>(ptr) }"
        in avx2
    )
    assert "pub unsafe fn store<Policy, T, const ALIGNED: bool>(" in avx2
    assert (
        "super::detail::primitives::StoreImplArg<\n"
        "                <Policy as VectorFor<Profile, T>>::Vec,\n"
        "                ALIGNED,"
        in avx2
    )
    assert (
        "unsafe { super::store::<<Policy as VectorFor<Profile, T>>::Vec, ALIGNED, _>(ptr, data) }"
        in avx2
    )
    assert "super::load::<Simd<T, super::Avx2>, false>" in avx2
    assert "super::store::<Simd<T, super::Avx2>, false, _>" in avx2
    assert "impl<T> MaskedStore<Simd<T, super::Avx2>> for Profile" in avx2
    assert "super::store_mask::<Simd<T, super::Avx2>, false>" in avx2
    assert "impl<T> IntegralMask<Simd<T, super::Avx2>> for Profile" in avx2
    assert "super::to_integral::<Simd<T, super::Avx2>>(mask)" in avx2
    assert "impl<T> MaskFromIntegral<Simd<T, super::Avx2>> for Profile" in avx2
    assert "super::to_mask::<Simd<T, super::Avx2>>(mask)" in avx2
    assert "impl<T> MaskFromIntegral<Simd<T, Scalar>> for Profile" in avx2
    assert "super::to_mask::<Simd<T, Scalar>>(mask)" in avx2
    assert "impl<T> CompressStore<Simd<T, super::Avx2>> for Profile" in avx2
    assert "super::compress_store::<Simd<T, super::Avx2>, true>" in avx2
    assert "impl<T> MaskPopulationCount<Simd<T, super::Avx2>> for Profile" in avx2
    assert "super::mask_population_count::<Simd<T, super::Avx2>>(mask)" in avx2
    assert "impl<const SCALE: u32> SelectedLoad<Simd<i32, super::Avx2>, SCALE> for Profile" in avx2
    assert (
        "super::detail::primitives::Gather_narrowImpl<Simd<usize, Generic<8>>, 4, 1>"
        in avx2
    )
    assert (
        "super::detail::primitives::Gather_narrowImpl<Simd<usize, Generic<8>>, SCALE, 1>"
        in avx2
    )
    assert (
        "super::gather_narrow::<Simd<i32, super::Avx2>, Simd<usize, Generic<8>>, 4, 1>"
        in avx2
    )
    assert (
        "super::gather_narrow::<Simd<i32, super::Avx2>, Simd<usize, Generic<8>>, SCALE, 1>"
        in avx2
    )


def test_cpp_specialization_structure(specialization_artifacts: dict[str, str]) -> None:
    avx2 = specialization_artifacts["cpp/include/tsl_avx2.hpp"]
    # primary template, the avx2 si32 specialization, an sse specialization in the
    # same profile header, and the generic wrapper.
    assert "template <class Vec>\nstruct add_impl;" in avx2
    assert (
        "static constexpr std::size_t lane_count_v = 256 / (sizeof(T) * 8);"
        in avx2
    )
    assert "static constexpr std::size_t vector_element_count = lane_count_v;" in avx2
    assert "static constexpr std::size_t vector_alignment = 32;" in avx2
    assert "static constexpr std::size_t simd_register_alignment_v = vector_alignment;" in avx2
    assert "using extension_type = avx2;" in avx2
    assert "using with_base_type = simd<ToBase, avx2>;" in avx2
    assert "using with_extension = simd<T, ToExtension>;" in avx2
    assert "struct add_impl<tsl::simd<int32_t, tsl::avx2>>" in avx2
    assert "return _mm256_add_epi32(left, right);" in avx2
    assert "struct add_impl<tsl::simd<int32_t, tsl::sse>>" in avx2
    assert "return _mm_add_epi32(left, right);" in avx2
    assert "inline typename Vec::register_type add(" in avx2
    assert (
        "template <class Policy, class T>\n"
        "inline typename ::tsl::dataparallel::simd_for_t<Policy, T>::register_type add("
        in avx2
    )
    resolved_vec = "::tsl::dataparallel::simd_for_t<Policy, T>"
    assert (
        "template <class Policy, class T, bool Aligned = false>\n"
        "inline typename ::tsl::dataparallel::simd_for_t<Policy, T>::register_type load("
        in avx2
    )
    assert (
        f"return ::tsl::load<{resolved_vec}, Aligned>(ptr);"
        in avx2
    )
    assert (
        "template <class Policy, class T, bool Aligned = false>\n"
        "inline void store("
        in avx2
    )
    assert (
        "typename ::tsl::dataparallel::simd_for_t<Policy, T>::base_type* ptr"
        in avx2
    )
    assert (
        f"::tsl::store<{resolved_vec}, Aligned>(ptr, data);"
        in avx2
    )
    assert f"return ::tsl::add<{resolved_vec}>(left, right);" in avx2
    assert (
        "template <class Policy, class T>\n"
        "inline typename ::tsl::dataparallel::simd_for_t<Policy, T>::register_type mul("
        in avx2
    )
    assert f"return ::tsl::mul<{resolved_vec}>(factor1, factor2);" in avx2
    assert (
        "template <class Policy, class T>\n"
        "inline typename ::tsl::dataparallel::simd_for_t<Policy, T>::mask_type less_than("
        in avx2
    )
    assert f"return ::tsl::less_than<{resolved_vec}>(left, right);" in avx2
    assert (
        "template <class Policy, class T>\n"
        "inline typename ::tsl::dataparallel::simd_for_t<Policy, T>::mask_type unequal_zero("
        in avx2
    )
    assert f"return ::tsl::unequal_zero<{resolved_vec}>(data);" in avx2
    assert (
        "template <class Policy, class T>\n"
        "inline typename ::tsl::dataparallel::simd_for_t<Policy, T>::mask_type mask_true()"
        in avx2
    )
    assert f"return ::tsl::mask_true<{resolved_vec}>();" in avx2
    assert (
        "template <class Policy, class T>\n"
        "inline typename ::tsl::dataparallel::simd_for_t<Policy, T>::mask_type mask_binary_not("
        in avx2
    )
    assert "typename ::tsl::dataparallel::simd_for_t<Policy, T>::mask_type mask" in avx2
    assert f"return ::tsl::mask_binary_not<{resolved_vec}>(mask);" in avx2
    assert (
        "template <class Policy, class T>\n"
        "inline typename ::tsl::dataparallel::simd_for_t<Policy, T>::mask_type mask_binary_and("
        in avx2
    )
    assert f"return ::tsl::mask_binary_and<{resolved_vec}>(mask_a, mask_b);" in avx2
    assert (
        "template <class Policy, class T>\n"
        "inline typename ::tsl::dataparallel::simd_for_t<Policy, T>::base_type hadd("
        in avx2
    )
    assert f"return ::tsl::hadd<{resolved_vec}>(vec);" in avx2
    assert (
        "template <class Policy, class T>\n"
        "inline typename ::tsl::dataparallel::simd_for_t<Policy, T>::base_type count_matches("
        in avx2
    )
    assert f"return ::tsl::count_matches<{resolved_vec}>(data, value);" in avx2
    assert (
        "template <class Policy, class T>\n"
        "inline std::size_t mask_population_count("
        in avx2
    )
    assert f"return ::tsl::mask_population_count<{resolved_vec}>(mask);" in avx2
    assert "template <class Policy, class FromT, class ToT>" in avx2
    assert "inline typename ::tsl::dataparallel::rebind_base_t<" in avx2
    assert "cast(typename ::tsl::reg_param<" in avx2
    assert "return ::tsl::cast<" in avx2
    assert "::tsl::dataparallel::simd_for_t<Policy, FromT>" in avx2
    assert "::tsl::dataparallel::rebind_base_t<" in avx2
    assert "reinterpret(typename ::tsl::reg_param<" in avx2
    assert "return ::tsl::reinterpret<" in avx2
    assert (
        "inline typename ::tsl::dataparallel::simd_for_t<Policy, T>::register_type hadd("
        not in avx2
    )
    assert "@brief Adds the corresponding lanes of two vector registers." in avx2
    assert "@par Semantics" in avx2
    assert "@par API" in avx2
    assert "- Template parameters: Vec selects the SIMD vector type" in avx2
    assert "- Returns: SIMD register (typename Vec::register_type)" in avx2
    assert "- Parameters: left: SIMD register; right: SIMD register" in avx2
    assert "@par Specialization" in avx2
    assert "- Extension: avx2" in avx2
    assert "- Element type: int32_t" in avx2
    assert "- Register type: __m256i" in avx2
    assert "- Context:" not in avx2
    assert "- Result kind:" not in avx2
    assert "- Parameter kinds:" not in avx2
    # hadd is scalar-returning (s:=v) and picks the f64 body.
    assert "inline typename Vec::base_type hadd(" in avx2
    assert "struct hadd_impl<tsl::simd<double, tsl::avx2>>" in avx2


def test_cpp_profile_specializes_dataparallel_simd_for_registered_vectors(
    specialization_artifacts: dict[str, str]
) -> None:
    avx2 = specialization_artifacts["cpp/include/tsl_avx2.hpp"]

    assert "struct simd_for<fixed<1>, int32_t>" not in avx2
    assert "struct simd_for<fixed<4>, int32_t>" in avx2
    assert "using type = ::tsl::simd<int32_t, ::tsl::sse>;" in avx2
    assert "struct simd_for<fixed<8>, int32_t>" in avx2
    assert "using type = ::tsl::simd<int32_t, ::tsl::avx2>;" in avx2
    assert "struct simd_for<fixed<4>, float>" in avx2
    assert "using type = ::tsl::simd<float, ::tsl::sse>;" in avx2
    assert "struct simd_for<fixed<8>, float>" in avx2
    assert "using type = ::tsl::simd<float, ::tsl::avx2>;" in avx2
    assert "struct simd_for<native, int32_t>" in avx2
    assert (
        "struct simd_for<native, int32_t> {\n"
        "    using type = ::tsl::simd<int32_t, ::tsl::avx2>;"
        in avx2
    )
    assert "struct simd_for<native, float>" in avx2
    assert (
        "struct simd_for<native, float> {\n"
        "    using type = ::tsl::simd<float, ::tsl::avx2>;"
        in avx2
    )


def test_rust_specialization_structure(specialization_artifacts: dict[str, str]) -> None:
    avx2 = specialization_artifacts["rust/src/tsl_avx2.rs"]
    core = specialization_artifacts["rust/src/tsl_core.rs"]
    lib = specialization_artifacts["rust/src/lib.rs"]

    assert "pub enum ImplementationState" in core
    assert "pub trait ImplementationStateOf<Primitive, Vec, Args = ()>" in core
    assert "pub struct BoolArg<const VALUE: bool>;" in core
    assert "pub struct U32Arg<const VALUE: u32>;" in core
    assert "pub struct I32Arg<const VALUE: i32>;" in core
    assert "pub trait StaticSimdVector: SimdVector" in core
    assert "type Extension;" in core
    assert "type WithBaseType<ToBase>;" in core
    assert "type WithExtension<ToExtension>;" in core
    assert "type Extension = Scalar;" in core
    assert "type WithBaseType<ToBase> = Simd<ToBase, Scalar>;" in core
    assert "type WithExtension<ToExtension> = Simd<T, ToExtension>;" in core
    assert "type Extension = Generic<LANES>;" in core
    assert "type WithBaseType<ToBase> = Simd<ToBase, Generic<LANES>>;" in core
    assert "fn lane_count() -> usize;" in core
    assert "const ELEMENT_COUNT: usize;" in core
    assert "const ELEMENT_COUNT: usize = 1;" in core
    assert "const ELEMENT_COUNT: usize = LANES;" in core
    assert "const ALIGN: usize;" in core
    assert "const ALIGN: usize = core::mem::align_of::<T>();" in core
    assert (
        "const ALIGN: usize = core::mem::align_of::<array_type<T, LANES>>();"
        in core
    )
    assert "pub trait AddImpl: StaticSimdVector {" in avx2
    assert "const IMPLEMENTATION_STATE: ImplementationState;" in avx2
    assert "impl AddImpl for Simd<i32, Avx2> {" in avx2
    assert (
        "const IMPLEMENTATION_STATE: ImplementationState = ImplementationState::Native;"
        in avx2
    )
    assert "impl StaticSimdVector for Simd<i32, Avx2>" in avx2
    assert "type Extension = Avx2;" in avx2
    assert "type WithBaseType<ToBase> = Simd<ToBase, Avx2>;" in avx2
    assert "type WithExtension<ToExtension> = Simd<i32, ToExtension>;" in avx2
    assert "const ELEMENT_COUNT: usize = 8;" in avx2
    assert "fn lane_count() -> usize { 8 }" in avx2
    assert "const ALIGN: usize = 32;" in avx2
    assert "unsafe { return core::arch::x86_64::_mm256_add_epi32(left, right); }" in avx2
    assert "impl AddImpl for Simd<i32, Sse> {" in avx2
    assert "pub mod detail {\n    pub mod primitives {" in avx2
    assert "pub struct Profile;" in avx2
    assert "pub mod primitive {\n    pub struct Add;" in lib
    assert (
        "impl<S> ImplementationStateOf<crate::primitive::Add, S, ()> for Profile\n"
        "where\n"
        "    S: detail::primitives::AddImpl,\n"
        "{\n"
        "    const VALUE: ImplementationState = "
        "<S as detail::primitives::AddImpl>::IMPLEMENTATION_STATE;\n"
        "}"
        in avx2
    )
    assert (
        "impl<S, const ALIGNED: bool> "
        "ImplementationStateOf<crate::primitive::Load, S, (BoolArg<ALIGNED>,)> "
        "for Profile"
        in avx2
    )
    assert (
        "impl<S: StaticSimdVector, const ALIGNED: bool, V> "
        "ImplementationStateOf<crate::primitive::Store, S, (BoolArg<ALIGNED>, V)> "
        "for Profile"
        in avx2
    )
    assert (
        "impl<S, ToVec: StaticSimdVector> "
        "ImplementationStateOf<crate::primitive::Reinterpret, S, (ToVec,)> "
        "for Profile"
        in avx2
    )
    assert (
        "ImplementationStateOf<crate::primitive::GatherNarrow, S, "
        "(IndicesType, U32Arg<scale>, I32Arg<N>)> for Profile"
        in avx2
    )
    assert "pub fn add<S: detail::primitives::AddImpl>(" in avx2
    assert '/// Adds the corresponding lanes of two vector registers.' in avx2
    assert "/// # Semantics" in avx2
    assert "/// # API" in avx2
    assert "/// - Type parameters: S selects the SIMD vector type" in avx2
    assert "/// - Returns: SIMD register (S::RegisterType)" in avx2
    assert "/// - Parameters: left: SIMD register; right: SIMD register" in avx2
    assert "/// # Specialization" in avx2
    assert "/// - Extension: avx2" in avx2
    assert "/// - Element type: i32" in avx2
    assert "/// - Register type: core::arch::x86_64::__m256i" in avx2
    assert "/// - Context:" not in avx2
    assert "/// - Result kind:" not in avx2
    assert "/// - Parameter kinds:" not in avx2


def test_cpp_documentation_facade_contains_api_declarations_only(
    specialization_artifacts: dict[str, str],
) -> None:
    facade = specialization_artifacts["cpp/docs/input/tsl_api_docs.hpp"]

    assert "namespace tsl {" in facade
    assert "template <class Vec>" in facade
    assert "typename Vec::register_type add(" in facade
    assert "template <class Policy, class T>" in facade
    assert "tsl::dataparallel::simd_for_t<Policy, T>" in facade
    assert "return _mm256_add_epi32" not in facade
    assert '#include "tsl_avx2.hpp"' not in facade
    assert '#include "tsl.hpp"' not in facade
    assert "namespace specializations" not in facade
    assert "void doc_avx2_add_avx2_si32_" not in facade
    assert "- Profile: avx2" not in facade


def test_specialization_explorer_data_contains_all_selected_specializations(
    specialization_result,
    specialization_artifacts: dict[str, str],
) -> None:
    payload = json.loads(specialization_artifacts["docs/specializations/specializations.json"])
    records = _decode_specialization_records(payload)

    assert payload["schema_version"] == 7
    assert "profiles" in payload
    assert "backends" in payload
    assert "types" in payload
    assert "expressions" in payload
    assert "implementation_state" in payload["columns"]
    assert "width_label" in payload["columns"]
    assert "extension_rank" in payload["columns"]
    assert sum(record["count"] for record in records) == len(specialization_result.coverage)
    strings = payload["strings"]
    primitive_docs = {strings[row[0]]: row for row in payload["primitives"]}
    add_doc = primitive_docs["add"]
    add_signature = strings[add_doc[5]]
    add_expressions = {
        strings[row[0]]: {"label": strings[row[1]], "code": strings[row[2]]}
        for row in payload["expressions"][add_doc[6]]
    }
    add_cpp = add_expressions["cpp"]["code"]
    add_rust = add_expressions["rust"]["code"]
    assert add_signature == "(SIMD register, SIMD register) => SIMD register"
    assert "using Vec = tsl::simd<" in add_cpp
    assert "tsl::dataparallel::native" in add_cpp
    assert "tsl::dataparallel::fixed<" in add_cpp
    assert "tsl::dataparallel::generic<" in add_cpp
    assert "auto result = tsl::add<Vec>(left, right);" in add_cpp
    assert "type S = Simd<" in add_rust
    assert "dataparallel::Native" in add_rust
    assert "dataparallel::Fixed<" in add_rust
    assert "dataparallel::Generic<" in add_rust
    assert "let result = add::<S>(left, right);" in add_rust
    load_doc = primitive_docs["load"]
    assert strings[load_doc[5]] == "(const pointer) => SIMD register"
    load_expressions = {
        strings[row[0]]: strings[row[2]]
        for row in payload["expressions"][load_doc[6]]
    }
    assert "/* aligned */" in load_expressions["cpp"]
    assert "/* aligned */" in load_expressions["rust"]
    assert any(
        record["backend"] == "cpp"
        and record["profile"] == "avx2"
        and record["primitive"] == "add"
        and record["extension"] == "avx2"
        and record["family"] == "x86"
        and record["type_tag"] == "si32"
        and record["register_type"] == "__m256i"
        and record["required_features"] == ["avx", "avx2"]
        and record["implementation_state"] == "native"
        and record["width_label"] == "256-bit"
        for record in records
    )
    profile_rows = {
        strings[row[0]]: {
            "family": strings[row[1]],
            "features": [strings[index] for index in payload["features"][row[2]]],
            "group_label": strings[row[6]],
            "summary": strings[row[8]],
            "tooltip": strings[row[9]],
            "sort_key": strings[row[10]],
        }
        for row in payload["profiles"]
    }
    assert {"avx512f", "avx512vl"} <= set(profile_rows["skylake"]["features"])
    assert profile_rows["skylake"]["family"] == "x86"
    assert profile_rows["skylake"]["group_label"] == "x86"
    assert profile_rows["skylake"]["summary"].startswith("x86 class")
    assert "Features: " in profile_rows["skylake"]["tooltip"]
    backend_rows = {
        strings[row[0]]: {"label": strings[row[1]], "rank": strings[row[2]]}
        for row in payload["backends"]
    }
    assert set(backend_rows) == {"cpp", "rust"}
    type_rows = {
        strings[row[0]]: {"short": strings[row[1]], "label": strings[row[2]]}
        for row in payload["types"]
    }
    assert type_rows["si32"] == {"short": "i32", "label": "signed int32"}
    assert any(
        record["profile"] == "skylake"
        and record["primitive"] == "add"
        and record["extension"] == "avx2"
        and record["type_tag"] == "si32"
        and record["required_features"] == ["avx", "avx2"]
        for record in records
    )
    assert any(
        record["profile"] == "skylake"
        and record["primitive"] == "add"
        and record["extension"] == "avx512"
        and record["type_tag"] == "si32"
        and record["required_features"] == ["avx512f"]
        for record in records
    )
    app_source = (
        Path(__file__).parents[2]
        / "supplementary/docs/site/specializations/react/src/App.jsx"
    ).read_text(encoding="utf-8")
    assert 'import React, { useEffect, useMemo, useState } from "react";' in app_source
    assert "const [filtersOpen, setFiltersOpen] = useState(false);" in app_source
    assert "setActiveCell(null);" in app_source
    assert "function PrimitiveBrowser" in app_source
    assert "function PrimitiveHero" in app_source
    assert "function TypeHeatmap" in app_source
    assert "function Drilldown" in app_source
    assert "function ProfileRollup" in app_source
    assert "function DeveloperModeToggle" in app_source
    assert "developerToggle" in app_source
    assert "VITE_TSLC_GIT_BRANCH" in app_source
    assert "VITE_TSLC_GIT_HASH" in app_source
    assert "docMeta" in app_source
    assert "signatureSummary" in app_source
    assert "signature: strings[signature]" in app_source
    assert "Profile x type heatmap" in app_source
    assert "Rows are machine profiles. Columns are data types." in app_source
    assert "short dash repeats the cell state color" in app_source
    assert "profileClassSummary(profile, 2)" in app_source
    assert "function profileFeatureTooltip" in app_source
    assert 'record.implementation_state === "native"' in app_source
    assert 'state: "yes", label: "nat"' in app_source
    assert 'state: "mixed", label: "part"' in app_source
    assert 'state: "no", label: "∅"' in app_source
    assert 'state: "degraded", label: "fb"' in app_source
    assert 'state: "degraded", label: "cmp"' in app_source
    assert "legendDegraded" in app_source
    assert "<details className=\"expressionBox\">" in app_source
    assert "Call examples" in app_source
    assert "Expression" in app_source
    assert (
        app_source.index("<PrimitiveHero")
        < app_source.index("<PrimitiveStatus")
        < app_source.index("<ProfileRollup")
        < app_source.index("<TypeHeatmap")
    )
    assert 'get("dev") === "1"' in app_source
    assert 'url.searchParams.set("dev", "1")' in app_source
    assert "TSL Primitive Specialization Reference" in app_source
    assert "Primitive support without misleading profile shortcuts" not in app_source
    assert "Profile capabilities are shown separately" in app_source
    assert "function typeLabel" in app_source
    assert "function targetWidthForRecord" not in app_source
    assert "record.profile === profile.name" in app_source
    assert "activeCell?.profile === profile.name" in app_source
    assert "function implementationTargetRank" in app_source
    assert "profileCapabilityGroup" not in app_source
    assert "implementation_state" in app_source
    assert "Selected implementation requirements are shown in the drilldown" in app_source
    assert "enabledRequirements" in app_source
    assert "enabledProfiles" in app_source
    assert "function ProfileChipGroups" in app_source
    assert "function profileFilterGroups" in app_source
    assert "function profileSortKey" in app_source
    assert "function requirementsForProfiles" in app_source
    assert "function profileClassSummary" in app_source
    assert "setEnabledRequirements(requirementsForProfiles" in app_source
    assert "implementationState" in app_source
    assert "const BACKENDS" not in app_source
    assert "const TYPE_ORDER" not in app_source
    assert "X86_PROFILE_CLASSES" not in app_source
    assert "profileClassFromBaselines" not in app_source
    assert "implementationExtensionGroup" not in app_source
    assert "featureRankKey" not in app_source
    assert "extensionRank(" not in app_source
    assert "familyRank(" not in app_source
    assert "targetWidthForRecord" not in app_source
    assert "expressions?.cpp" not in app_source
    assert "expressions?.rust" not in app_source
    assert "AVX" not in app_source
    assert "SSE" not in app_source
    assert "NEON" not in app_source
    assert "SVE" not in app_source
    assert "enabledFamilies" in app_source
    assert 'title="Profile"' in app_source
    assert 'title="Requirements"' in app_source
    assert 'title="Families"' in app_source
    assert 'typeTag !== "ptr"' not in app_source
    assert "enabledTargets" not in app_source
    assert "setEnabledTargets" not in app_source
    assert "SupportMatrix" not in app_source
    assert "supportMatrix" not in app_source
    assert "3D support matrix" not in app_source
    assert "getSupportValue" not in app_source


def test_avx_profile_falls_back_to_sse_for_integers(
    specialization_artifacts: dict[str, str],
) -> None:
    avx = specialization_artifacts["cpp/include/tsl_avx.hpp"]
    # avx lacks the avx2 flag, so 256-bit integer add is NOT specialized...
    assert "add_impl<tsl::simd<int32_t, tsl::avx2>>" not in avx
    assert "add_impl<tsl::simd<int32_t, tsl::sse>>" in avx
    # ...but 256-bit float add only needs `avx`, so it IS present.
    assert "add_impl<tsl::simd<float, tsl::avx2>>" in avx


def test_skylake_uses_vl_and_avx512_not_base(
    specialization_artifacts: dict[str, str],
) -> None:
    sky = specialization_artifacts["cpp/include/tsl_skylake.hpp"]
    # avx512vl present -> the avx512vl-aware bodies are selected, but they are
    # emitted under the *ISA* names (avx2/sse), never the internal `_vl` tags.
    assert "_vl" not in sky
    assert "add_impl<tsl::simd<int32_t, tsl::avx512>>" in sky
    assert "return _mm512_add_epi32(left, right);" in sky
    # avx2 here is the avx2_vl-selected body (inherits avx2's), emitted as avx2.
    assert "add_impl<tsl::simd<int32_t, tsl::avx2>>" in sky
    assert "return _mm256_add_epi32(left, right);" in sky
    assert "add_impl<tsl::simd<int32_t, tsl::sse>>" in sky


def test_cast_lowers_integer_reductions(specialization_artifacts: dict[str, str]) -> None:
    sky_cpp = specialization_artifacts["cpp/include/tsl_skylake.hpp"]
    sky_rust = specialization_artifacts["rust/src/tsl_skylake.rs"]
    # hadd's avx512 integer reduction casts the result to the base type:
    # cast<static>(type(base::in), intrin<reduce_add, build[...]>(vec)).
    assert "static_cast<int32_t>(_mm512_reduce_add_epi32(vec))" in sky_cpp
    assert "(core::arch::x86_64::_mm512_reduce_add_epi32(vec)) as i32" in sky_rust


def test_coverage_counts_specializations(specialization_result) -> None:
    result = specialization_result
    keys = {(c.profile, c.extension, c.primitive, c.type_tag) for c in result.coverage}
    assert ("avx2", "avx2", "add", "si32") in keys
    assert ("avx2", "avx2", "hadd", "f64") in keys
    assert ("scalar", "scalar", "add", "f64") in keys


def _decode_specialization_records(payload: dict) -> list[dict]:
    strings = payload["strings"]
    feature_sets = [
        [strings[index] for index in feature_set]
        for feature_set in payload["features"]
    ]
    safeties = [
        {
            "caller_unsafe": caller,
            "internal_unsafe": internal,
            "reasons": [strings[index] for index in reasons],
        }
        for caller, internal, reasons in payload["safeties"]
    ]
    records: list[dict] = []
    for primitive, rows in payload["specialization_groups"]:
        for row in rows:
            records.append(
                {
                    "primitive": strings[primitive],
                    "backend": strings[row[0]],
                    "profile": strings[row[1]],
                    "extension": strings[row[2]],
                    "family": strings[row[3]],
                    "type_tag": strings[row[4]],
                    "register_type": strings[row[5]],
                    "required_features": feature_sets[row[6]],
                    "safety": safeties[row[7]],
                    "implementation_state": strings[row[8]],
                    "width_label": strings[row[9]],
                    "width_rank": strings[row[10]],
                    "extension_group": strings[row[11]],
                    "extension_rank": strings[row[12]],
                    "family_rank": strings[row[13]],
                    "count": row[14] if len(row) > 14 else 1,
                }
            )
    return records
