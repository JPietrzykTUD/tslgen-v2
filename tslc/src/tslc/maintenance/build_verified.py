"""Typed build-verification evidence shared by tests and coverage inventory.

Each entry names one generated-build gate in ``tslc/tests/test_build_verify.py``
and the corpus primitives that test compiles, in the exact order the test
requests them.  The test functions consume these tuples as their
``primitives=`` input, so the constant cannot drift from what the gate actually
builds; ``coverage_inventory`` consumes the same constant for its
build-verified column instead of sniffing test-source syntax.

Tests that generate from synthetic (non-corpus) sources or compute their
primitive list from the whole catalog deliberately have no entry here: this
constant records targeted per-primitive-group build evidence for the corpus.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

_COMPARISON_FAMILY = (
    "equal",
    "nequal",
    "less_than",
    "greater_than",
    "less_than_or_equal",
    "greater_than_or_equal",
    "unequal_zero",
)

BUILD_VERIFIED_PRIMITIVE_SETS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "test_generated_profiles_build": ("add", "hadd"),
        "test_clang_vector_overlay_builds_and_runs_through_opt_in_target": (
            "abs",
            "add",
            "select",
            "equal",
            "hadd",
            "mask_binary_and",
            "mask_binary_not",
            "mask_binary_or",
            "mask_binary_xor",
            "mask_false",
            "mask_population_count",
            "mask_true",
            "to_integral",
            "to_mask",
        ),
        "test_cpp_fetch_content_consumer_builds": ("add",),
        "test_rust_path_dependency_consumer_builds": (
            "add",
            "sub",
            "mul",
            "div",
            "mod",
            "neg",
            "equal",
            "nequal",
            "less_than",
            "less_than_or_equal",
            "greater_than",
            "greater_than_or_equal",
            "select",
            "convert_lanes",
            "reinterpret",
            "shift_left",
            "shift_left_wrapping",
            "shift_right_wrapping",
            "binary_and",
            "binary_or",
            "binary_xor",
            "inv",
        ),
        "test_rust_compile_target_selects_static_mapping": ("add",),
        "test_cpp_auto_profile_configures": ("add",),
        "test_scalar_mask_comparison_family_builds": _COMPARISON_FAMILY,
        "test_simd_comparison_family_builds": _COMPARISON_FAMILY,
        "test_select_native_builds": ("select",),
        "test_neg_builds": ("neg",),
        "test_wrapping_shifts_build": (
            "shift_left_wrapping",
            "shift_right_wrapping",
        ),
        "test_runtime_lane_mutation_builds": (
            "extract_value_at",
            "insert_value_at",
            "set_mask_lane",
        ),
        "test_to_from_array_roundtrip_builds": ("to_array", "from_array"),
        "test_select_composition_builds": ("mul", "select", "mov", "min", "max"),
        "test_generic_masks_build": _COMPARISON_FAMILY,
        "test_generic_extension_builds": ("add", "sub"),
        "test_elementwise_bitwise_builds": (
            "add",
            "sub",
            "mul",
            "div",
            "binary_and",
            "binary_andnot",
            "binary_or",
            "binary_xor",
        ),
        "test_reductions_build": ("hadd", "hmax", "hmin"),
        "test_load_store_builds": ("load", "store"),
        "test_convert_builds": ("convert_up", "convert_down", "load_convert_up"),
        "test_convert_lanes_builds": ("convert_lanes",),
        "test_cast_reinterpret_builds": ("cast", "reinterpret"),
        "test_sequence_builds": ("sequence",),
        "test_extract_value_builds": ("extract_value",),
        "test_max_min_builds": ("max", "min"),
        "test_gather_scatter_builds": ("gather", "scatter"),
        "test_to_integral_builds": ("to_integral",),
        "test_to_mask_builds": ("to_mask",),
        "test_to_vector_builds": ("to_vector",),
        "test_masked_value_ops_build": (
            "binary_and",
            "add",
            "inv",
            "shift_left",
            "mul_imm",
        ),
        "test_masked_comparisons_build": (
            "equal",
            "less_than",
            "greater_than_or_equal",
            "between_inclusive",
        ),
        "test_masked_load_store_build": ("load", "store"),
        "test_mul_imm_builds": ("mul_imm",),
        "test_shift_left_builds": ("shift_left",),
        "test_shift_right_scalar_builds": ("shift_right",),
        "test_shift_right_imask_builds": ("shift_right_imask",),
        "test_shift_right_delegation_builds": ("shift_right",),
        "test_shift_right_avx512_immediate_builds": ("shift_right",),
        "test_set1_avx512_builds": ("set1",),
        "test_shift_float_builds": ("shift_left", "shift_right"),
        "test_reinterpret_integer_builds": ("reinterpret",),
        "test_extract_builds": ("extract",),
        "test_insert_builds": ("insert",),
        "test_resize_and_indexed_permute_builds": (
            "resize_down",
            "resize_up_undef",
            "resize_up_zero",
            "concat",
            "permute_lanes",
        ),
        "test_mask_binary_and_builds": ("mask_binary_and",),
        "test_range_comparisons_build": (
            "between_inclusive",
            "between_left_inclusive",
            "between_right_inclusive",
            "between_exclusive",
        ),
        "test_mask_boolean_algebra_builds": (
            "mask_binary_or",
            "mask_binary_xor",
            "mask_binary_not",
        ),
        "test_mask_true_builds": ("mask_true",),
        "test_imask_ops_build": (
            "test_imask",
            "overlay_imask",
            "insert_imask",
            "extract_imask",
        ),
        "test_mask_population_count_builds": ("mask_population_count",),
        "test_nullary_constants_build": ("set_zero", "set_undef", "mask_false"),
        "test_simple_memory_build": ("load_scalar",),
        "test_modulo_build": ("mod", "mod_imm"),
        "test_blend_add_sequence_build": ("blend_add", "custom_sequence"),
        "test_conflict_counting_build": (
            "conflict",
            "conflict_free",
            "count_matches",
        ),
        "test_bit_reductions_build": ("popcnt", "hand", "hor", "tzc"),
        "test_leading_zeros_build": ("lzc", "lzc_imask", "lzc_scalar"),
        "test_masked_memory_build": (
            "load_mask_repr",
            "store_mask_repr",
            "masked_set1",
            "compress",
            "compress_store",
            "expand_load",
        ),
        "test_memory_cp_builds": ("memory_cp",),
        "test_allocate_family_builds": (
            "allocate",
            "allocate_aligned",
            "deallocate",
        ),
        "test_set_builds": ("set",),
        "test_to_ostream_builds": ("to_ostream",),
    }
)


def build_verified_primitives() -> frozenset[str]:
    """Primitive names covered by at least one generated build test."""

    return frozenset(
        name for names in BUILD_VERIFIED_PRIMITIVE_SETS.values() for name in names
    )


__all__ = ("BUILD_VERIFIED_PRIMITIVE_SETS", "build_verified_primitives")
