// tslc SIMD inference compatibility helpers. New code should prefer
// `tsl::dataparallel::simd_for_t<Policy, T>`; these aliases preserve the older
// generated helper vocabulary.
#pragma once
#include <cstddef>

#include "tsl_dataparallel.hpp"

namespace tsl::detail {

template <class T, std::size_t ParallelN>
struct inferred_simd {
    using type =
        ::tsl::dataparallel::simd_for_t<::tsl::dataparallel::fixed<ParallelN>, T>;
};

template <class T>
struct native_simd {
    using type = ::tsl::dataparallel::simd_for_t<::tsl::dataparallel::native, T>;
};

}  // namespace tsl::detail

namespace tsl {

template <class T, std::size_t ParallelN>
using inferred_simd_t = typename detail::inferred_simd<T, ParallelN>::type;

template <class T>
using native_simd_t = typename detail::native_simd<T>::type;

}  // namespace tsl
