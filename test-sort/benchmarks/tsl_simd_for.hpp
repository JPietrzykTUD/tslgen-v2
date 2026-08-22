#pragma once

// Style and register width to a TSL vector type.
//
// **The width half of this is TSL's job, and it does it.**
// `tsl::dataparallel::simd_for_t<tsl::dataparallel::fixed<N>, T>` maps a lane
// count to the extension that provides it -- for `uint32_t`, `fixed<4>` is `sse`,
// `fixed<8>` is `avx2`, `fixed<16>` is `avx512`, and for `uint64_t` the same
// widths are `fixed<2,4,8>`. Keying on lanes rather than bits is the better
// interface, because lanes is what a kernel actually cares about; a sweep that
// wants a fixed *register* size just asks for `bits / (8 * sizeof(T))` lanes.
// The intrinsics rows below therefore delegate rather than repeating the table.
//
// What TSL has no policy for is the **style** axis. `clang_v128`, `clang_v512`,
// `clang_v512_bool` and friends are named extensions, not data-parallelism
// levels: they answer "expressed with compiler vector builtins or with
// intrinsics, and is a mask a lane-wide compare result or a packed boolean" --
// which is a question about the generated code, not about how wide the register
// is. `tsl::dataparallel::generic<N>` is a different thing again, a portable
// modelled register. So only the style rows are written out here.
//
// One thing to read carefully before interpreting a width sweep. `tsl::sse` and
// `tsl::avx2` mean "128-bit" and "256-bit", not "the SSE instruction set" and
// "the AVX2 instruction set". On a host with AVX-512VL the 128- and 256-bit
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

// Intrinsics: ask TSL. A fixed register size is a lane count once the element
// width is known, and `simd_for_t` owns the lane-count-to-extension table.
template <class DataType, std::size_t Width>
struct tsl_simd_for<DataType, TslStyle::Intrinsics, Width> {
  static_assert(Width % (8 * sizeof(DataType)) == 0,
                "a register width must hold a whole number of elements");
  using type = tsl::dataparallel::simd_for_t<
    tsl::dataparallel::fixed<Width / (8 * sizeof(DataType))>, DataType>;
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

