#pragma once

// Style and register width to a TSL vector type.
//
// Extracted from cosort_bench.cpp because the tuning driver needs the same
// mapping: it re-runs its coordinate descent once per (style, width) pair, and a
// second copy of this table would be a second thing to keep in step with the
// generated TSL release.
//
// One thing to read carefully before interpreting a width sweep. `tsl::sse` and
// `tsl::avx2` here mean "128-bit" and "256-bit", not "the SSE instruction set"
// and "the AVX2 instruction set". On a host with AVX-512VL the 128- and 256-bit
// scatter resolve to `_mm_i32scatter_epi32` and `_mm256_i32scatter_epi32`, which
// are VL-encoded AVX-512 instructions. So a width sweep on such a host compares
// register widths on one ISA; it does not tell you what the algorithm would do on
// a machine that genuinely lacks AVX-512.

#include <cstddef>

#include <tsl.hpp>

#include "cosort_plan.hpp"

// --- style and width to a TSL vector type -----------------------------------

template <class DataType, TslStyle Style, std::size_t Width>
struct tsl_simd_for;

template <class DataType> struct tsl_simd_for<DataType, TslStyle::Intrinsics, 128> {
  using type = tsl::simd<DataType, tsl::sse>;
};
template <class DataType> struct tsl_simd_for<DataType, TslStyle::Intrinsics, 256> {
  using type = tsl::simd<DataType, tsl::avx2>;
};
template <class DataType> struct tsl_simd_for<DataType, TslStyle::Intrinsics, 512> {
  using type = tsl::simd<DataType, tsl::avx512>;
};

#if defined(TSL_COSORT_HAVE_CLANG_STYLE)
template <class DataType> struct tsl_simd_for<DataType, TslStyle::ClangBuiltin, 128> {
  using type = tsl::simd<DataType, tsl::clang_v128>;
};
template <class DataType> struct tsl_simd_for<DataType, TslStyle::ClangBuiltin, 256> {
  using type = tsl::simd<DataType, tsl::clang_v256>;
};
template <class DataType> struct tsl_simd_for<DataType, TslStyle::ClangBuiltin, 512> {
  using type = tsl::simd<DataType, tsl::clang_v512>;
};
constexpr bool tsl_clang_style_available = true;
#else
// The clang profile header needs a clang new enough for its elementwise builtins;
// CMake probes for that and only then defines TSL_COSORT_HAVE_CLANG_STYLE. The
// style axis stays in the model either way, so a run reports what it could not
// measure instead of silently omitting it.
template <class DataType, std::size_t Width> struct tsl_simd_for<DataType, TslStyle::ClangBuiltin, Width> {
  using type = tsl::simd<DataType, tsl::avx512>;  // never registered; keeps the table total
};
constexpr bool tsl_clang_style_available = false;
#endif

#if defined(TSL_COSORT_HAVE_CLANG_BOOL_STYLE)
template <class DataType> struct tsl_simd_for<DataType, TslStyle::ClangBoolMask, 128> {
  using type = tsl::simd<DataType, tsl::clang_v128_bool>;
};
template <class DataType> struct tsl_simd_for<DataType, TslStyle::ClangBoolMask, 256> {
  using type = tsl::simd<DataType, tsl::clang_v256_bool>;
};
template <class DataType> struct tsl_simd_for<DataType, TslStyle::ClangBoolMask, 512> {
  using type = tsl::simd<DataType, tsl::clang_v512_bool>;
};
constexpr bool tsl_clang_bool_style_available = true;
#else
// `clang_v*_bool` additionally needs the ext_vector_type boolean extension, which
// is a separate capability from the elementwise builtins, so it gets its own probe.
template <class DataType, std::size_t Width> struct tsl_simd_for<DataType, TslStyle::ClangBoolMask, Width> {
  using type = tsl::simd<DataType, tsl::avx512>;  // never registered; keeps the table total
};
constexpr bool tsl_clang_bool_style_available = false;
#endif

