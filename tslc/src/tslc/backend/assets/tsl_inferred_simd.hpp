// tslc SIMD inference helper. Profile headers add the concrete specializations
// for fixed-width SIMD types they actually register.
#pragma once
#include <cstddef>

#include "tsl_core.hpp"

namespace tsl::detail {

template <class T, std::size_t ParallelN>
struct inferred_simd;

}  // namespace tsl::detail

namespace tsl {

template <class T, std::size_t ParallelN>
using inferred_simd_t = typename detail::inferred_simd<T, ParallelN>::type;

}  // namespace tsl
