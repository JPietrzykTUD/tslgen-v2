// tslc x86 width helpers (profile-independent). Map a base type to its x86 register
// type by width. Included only by x86 profile headers; the per-profile header then
// registers `simd<T, ext>` for the extensions it uses, referencing these helpers.
#pragma once
#include <cstdint>
#include <immintrin.h>

namespace tsl::detail {

template <class T> struct reg128 { using type = __m128i; };
template <> struct reg128<float> { using type = __m128; };
template <> struct reg128<double> { using type = __m128d; };

template <class T> struct reg256 { using type = __m256i; };
template <> struct reg256<float> { using type = __m256; };
template <> struct reg256<double> { using type = __m256d; };

template <class T> struct reg512 { using type = __m512i; };
template <> struct reg512<float> { using type = __m512; };
template <> struct reg512<double> { using type = __m512d; };

// Native-predicate mask type (avx512 / the _vl variants): a `__mmaskN` whose width
// covers the lane count `Bits / (sizeof(T) * 8)`, clamped to the smallest `__mmask8`.
template <int Lanes> struct mmask_of;
template <> struct mmask_of<8>  { using type = __mmask8;  };
template <> struct mmask_of<16> { using type = __mmask16; };
template <> struct mmask_of<32> { using type = __mmask32; };
template <> struct mmask_of<64> { using type = __mmask64; };

template <int Bits, class T>
struct native_mask {
    static constexpr int lanes = Bits / (static_cast<int>(sizeof(T)) * 8);
    using type = typename mmask_of<(lanes < 8 ? 8 : lanes)>::type;
};

}  // namespace tsl::detail
