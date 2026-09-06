#pragma once

#include <cstddef>

#include "tsl_core.hpp"

namespace tsl::dataparallel {

/** Select the generated native vector width for an element type. */
struct native {};

/** Select exactly `N` logical lanes using a supported fixed-width vector. */
template <std::size_t N>
struct fixed {
    static_assert(N > 0, "tsl::dataparallel::fixed<N> requires N > 0");
    static constexpr std::size_t lanes = N;
};

/** Select exactly `N` logical lanes using the portable generic representation. */
template <std::size_t N>
struct generic {
    static_assert(N > 0, "tsl::dataparallel::generic<N> requires N > 0");
    static constexpr std::size_t lanes = N;
};

/** Resolve a lane-width policy and element type to a generated `tsl::simd`. */
template <class Policy, class T>
struct simd_for;

template <class T>
struct simd_for<native, T> {
    using type = ::tsl::simd<T, ::tsl::scalar>;
};

template <class T>
struct simd_for<fixed<1>, T> {
    using type = ::tsl::simd<T, ::tsl::scalar>;
};

template <std::size_t N, class T>
struct simd_for<generic<N>, T> {
    using type = ::tsl::simd<T, ::tsl::generic<N>>;
};

/** Vector type selected by `Policy` for element type `T`. */
template <class Policy, class T>
using simd_for_t = typename simd_for<Policy, T>::type;

/** Register type selected by `Policy` for element type `T`. */
template <class Policy, class T>
using register_t = typename simd_for_t<Policy, T>::register_type;

template <class Vec, class ToT>
using rebind_base_t = typename Vec::template with_base_type<ToT>;

template <class Policy, class FromT, class ToT>
using rebind_simd_for_t = rebind_base_t<simd_for_t<Policy, FromT>, ToT>;

}  // namespace tsl::dataparallel
