#pragma once

#include "tsl_algorithm_detail_mask.hpp"

namespace tsl::algo::detail {

template <class Vec, class Op, class T>
inline void for_each_chunk_loop(Op& op, T* data, std::size_t count) {
    using value_type = typename std::remove_cv<T>::type;
    using scalar_vec = ::tsl::simd<value_type, ::tsl::scalar>;

    const std::size_t lanes = detail::lane_count<Vec>();
    const std::size_t chunk_count = count / lanes;
    std::size_t i = 0;
    for (std::size_t chunk = 0; chunk < chunk_count; ++chunk, i += lanes) {
        (void)chunk;
        invoke_op<Vec>(op, data + i, i, lanes);
    }
    for (; i < count; ++i) {
        invoke_op<scalar_vec>(op, data + i, i, std::size_t{1});
    }
}

}  // namespace tsl::algo::detail
