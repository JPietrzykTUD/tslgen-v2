#pragma once

#include <cstddef>

#include "tsl_core.hpp"

namespace tsl::dataparallel {

struct native {};

template <std::size_t N>
struct fixed {
    static_assert(N > 0, "tsl::dataparallel::fixed<N> requires N > 0");
    static constexpr std::size_t lanes = N;
};

template <std::size_t N>
struct generic {
    static_assert(N > 0, "tsl::dataparallel::generic<N> requires N > 0");
    static constexpr std::size_t lanes = N;
};

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

template <class Policy, class T>
using simd_for_t = typename simd_for<Policy, T>::type;

template <class Policy, class T>
using register_t = typename simd_for_t<Policy, T>::register_type;

template <class Vec, class ToT>
using rebind_base_t = typename Vec::template with_base_type<ToT>;

template <class Policy, class FromT, class ToT>
using rebind_simd_for_t = rebind_base_t<simd_for_t<Policy, FromT>, ToT>;

}  // namespace tsl::dataparallel
