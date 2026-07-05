// tslc SIMD inference helper. Profile headers add the concrete specializations
// for fixed-width SIMD types they actually register; otherwise inference falls
// back to the portable generic vector.
#pragma once
#include <cstddef>

#include "tsl_core.hpp"

namespace tsl::detail {

template <class T, std::size_t ParallelN>
struct inferred_simd {
    using type = ::tsl::simd<T, ::tsl::generic<ParallelN>>;
};

template <class T>
struct inferred_simd<T, 1> {
    using type = ::tsl::simd<T, ::tsl::scalar>;
};

template <class T>
struct native_simd {
    using type = ::tsl::simd<T, ::tsl::scalar>;
};

}  // namespace tsl::detail

namespace tsl {

template <class T, std::size_t ParallelN>
using inferred_simd_t = typename detail::inferred_simd<T, ParallelN>::type;

template <class T>
using native_simd_t = typename detail::native_simd<T>::type;

}  // namespace tsl
