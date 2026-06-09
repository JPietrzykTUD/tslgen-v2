// tslc static core for x86 extensions. Included only by x86 profile headers, so
// the scalar profile stays free of <immintrin.h>.
#pragma once
#include <cstdint>
#include <immintrin.h>

#include "tsl_core.hpp"

namespace tsl {

// register_type selection by base-type category (integral -> *i, float -> *, double -> *d).
template <class T> struct register_trait_sse { using type = __m128i; };
template <> struct register_trait_sse<float> { using type = __m128; };
template <> struct register_trait_sse<double> { using type = __m128d; };

template <class T> struct register_trait_avx2 { using type = __m256i; };
template <> struct register_trait_avx2<float> { using type = __m256; };
template <> struct register_trait_avx2<double> { using type = __m256d; };

template <class T>
struct simd<T, sse> {
    using base_type = T;
    using register_type = typename register_trait_sse<T>::type;
};

template <class T>
struct simd<T, avx2> {
    using base_type = T;
    using register_type = typename register_trait_avx2<T>::type;
};

}  // namespace tsl
