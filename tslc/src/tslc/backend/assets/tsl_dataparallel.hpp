#pragma once

#include <cstddef>

#include "tsl_core.hpp"

namespace tsl::dataparallel {

/** Select the generated native vector width for an element type. */
@{dataparallel_declaration_native} {};

/** Select exactly `N` logical lanes using a supported fixed-width vector. */
@{dataparallel_declaration_fixed} {
    static_assert(N > 0, "tsl::dataparallel::fixed<N> requires N > 0");
@{dataparallel_fixed_constant_lanes};
};

/** Select exactly `N` logical lanes using the portable generic representation. */
@{dataparallel_declaration_generic} {
    static_assert(N > 0, "tsl::dataparallel::generic<N> requires N > 0");
@{dataparallel_generic_constant_lanes};
};

/** Resolve a lane-width policy and element type to a generated `tsl::simd`. */
@{dataparallel_declaration_simd_for};

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
@{dataparallel_alias_simd_for_t};

/** Register type selected by `Policy` for element type `T`. */
@{dataparallel_alias_register_t};

@{dataparallel_alias_rebind_base_t};

@{dataparallel_alias_rebind_simd_for_t};

}  // namespace tsl::dataparallel
