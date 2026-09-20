#pragma once

#include "tsl_algorithm_detail_mask.hpp"

namespace tsl::algo::detail {

template <class Vec, class InputAlignment, class Op, class T>
inline std::size_t count_unary_loop(
    Op& predicate,
    const T* input,
    std::size_t count) {
    using scalar_vec = ::tsl::simd<T, ::tsl::scalar>;
    constexpr bool input_aligned =
        std::is_same<InputAlignment, alignment::assume_aligned>::value;

    validate_integral_mask_layout<Vec>();

    const std::size_t lanes = detail::lane_count<Vec>();
    const std::size_t chunk_count = count / lanes;
    std::size_t produced = 0;
    std::size_t i = 0;
    for (std::size_t chunk = 0; chunk < chunk_count; ++chunk, i += lanes) {
        auto x = ::tsl::@{algorithm_helper_contiguous_read}<Vec, input_aligned>(input + i);
        auto active = invoke_op<Vec>(predicate, x);
        produced += ::tsl::@{algorithm_helper_mask_population_count}<Vec>(active);
    }
    for (; i < count; ++i) {
        auto x = ::tsl::@{algorithm_helper_contiguous_read}<scalar_vec, false>(input + i);
        auto active = invoke_op<scalar_vec>(predicate, x);
        if (::tsl::@{algorithm_helper_integral_mask}<scalar_vec>(active) != 0) {
            produced += 1;
        }
    }
    return produced;
}

template <
    class Vec,
    class LeftAlignment,
    class RightAlignment,
    class Op,
    class T>
inline std::size_t count_binary_loop(
    Op& predicate,
    const T* left,
    const T* right,
    std::size_t count) {
    using scalar_vec = ::tsl::simd<T, ::tsl::scalar>;
    constexpr bool left_aligned =
        std::is_same<LeftAlignment, alignment::assume_aligned>::value;
    constexpr bool right_aligned =
        std::is_same<RightAlignment, alignment::assume_aligned>::value;

    validate_integral_mask_layout<Vec>();

    const std::size_t lanes = detail::lane_count<Vec>();
    const std::size_t chunk_count = count / lanes;
    std::size_t produced = 0;
    std::size_t i = 0;
    for (std::size_t chunk = 0; chunk < chunk_count; ++chunk, i += lanes) {
        auto x = ::tsl::@{algorithm_helper_contiguous_read}<Vec, left_aligned>(left + i);
        auto y = ::tsl::@{algorithm_helper_contiguous_read}<Vec, right_aligned>(right + i);
        auto active = invoke_op<Vec>(predicate, x, y);
        produced += ::tsl::@{algorithm_helper_mask_population_count}<Vec>(active);
    }
    for (; i < count; ++i) {
        auto x = ::tsl::@{algorithm_helper_contiguous_read}<scalar_vec, false>(left + i);
        auto y = ::tsl::@{algorithm_helper_contiguous_read}<scalar_vec, false>(right + i);
        auto active = invoke_op<scalar_vec>(predicate, x, y);
        if (::tsl::@{algorithm_helper_integral_mask}<scalar_vec>(active) != 0) {
            produced += 1;
        }
    }
    return produced;
}

template <class Vec, class MaskLayout, class InputAlignment, class Op, class T>
inline std::size_t count_masked_unary_loop(
    Op& predicate,
    const T* input,
    const mask_storage_for_vec_t<MaskLayout, Vec>* masks,
    std::size_t count) {
    using scalar_vec = ::tsl::simd<T, ::tsl::scalar>;
    constexpr bool input_aligned =
        std::is_same<InputAlignment, alignment::assume_aligned>::value;

    validate_mask_layout<MaskLayout, Vec>();
    validate_integral_mask_layout<Vec>();

    const std::size_t lanes = detail::lane_count<Vec>();
    const std::size_t chunk_count = count / lanes;
    std::size_t produced = 0;
    std::size_t i = 0;
    for (std::size_t chunk = 0; chunk < chunk_count; ++chunk, i += lanes) {
        auto input_active = load_mask_storage<MaskLayout, Vec>(masks, chunk, i);
        auto x = ::tsl::@{algorithm_helper_contiguous_read}<Vec, input_aligned>(input + i);
        auto predicate_active = invoke_op<Vec>(predicate, x);
        auto active =
            ::tsl::@{algorithm_helper_mask_intersection}<Vec>(input_active, predicate_active);
        produced += ::tsl::@{algorithm_helper_mask_population_count}<Vec>(active);
    }
    for (std::size_t lane = 0; i < count; ++i, ++lane) {
        if (!mask_storage_lane_active<MaskLayout, Vec>(
                masks, chunk_count, i, lane)) {
            continue;
        }
        auto x = ::tsl::@{algorithm_helper_contiguous_read}<scalar_vec, false>(input + i);
        auto active = invoke_op<scalar_vec>(predicate, x);
        if (::tsl::@{algorithm_helper_integral_mask}<scalar_vec>(active) != 0) {
            produced += 1;
        }
    }
    return produced;
}

template <
    class Vec,
    class MaskLayout,
    class LeftAlignment,
    class RightAlignment,
    class Op,
    class T>
inline std::size_t count_masked_binary_loop(
    Op& predicate,
    const T* left,
    const T* right,
    const mask_storage_for_vec_t<MaskLayout, Vec>* masks,
    std::size_t count) {
    using scalar_vec = ::tsl::simd<T, ::tsl::scalar>;
    constexpr bool left_aligned =
        std::is_same<LeftAlignment, alignment::assume_aligned>::value;
    constexpr bool right_aligned =
        std::is_same<RightAlignment, alignment::assume_aligned>::value;

    validate_mask_layout<MaskLayout, Vec>();
    validate_integral_mask_layout<Vec>();

    const std::size_t lanes = detail::lane_count<Vec>();
    const std::size_t chunk_count = count / lanes;
    std::size_t produced = 0;
    std::size_t i = 0;
    for (std::size_t chunk = 0; chunk < chunk_count; ++chunk, i += lanes) {
        auto input_active = load_mask_storage<MaskLayout, Vec>(masks, chunk, i);
        auto x = ::tsl::@{algorithm_helper_contiguous_read}<Vec, left_aligned>(left + i);
        auto y = ::tsl::@{algorithm_helper_contiguous_read}<Vec, right_aligned>(right + i);
        auto predicate_active = invoke_op<Vec>(predicate, x, y);
        auto active =
            ::tsl::@{algorithm_helper_mask_intersection}<Vec>(input_active, predicate_active);
        produced += ::tsl::@{algorithm_helper_mask_population_count}<Vec>(active);
    }
    for (std::size_t lane = 0; i < count; ++i, ++lane) {
        if (!mask_storage_lane_active<MaskLayout, Vec>(
                masks, chunk_count, i, lane)) {
            continue;
        }
        auto x = ::tsl::@{algorithm_helper_contiguous_read}<scalar_vec, false>(left + i);
        auto y = ::tsl::@{algorithm_helper_contiguous_read}<scalar_vec, false>(right + i);
        auto active = invoke_op<scalar_vec>(predicate, x, y);
        if (::tsl::@{algorithm_helper_integral_mask}<scalar_vec>(active) != 0) {
            produced += 1;
        }
    }
    return produced;
}

template <class Vec, std::size_t Scale, class Op, class T, class IndexT>
inline std::size_t count_selected_unary_loop(
    Op& predicate,
    const T* input,
    const IndexT* indices,
    std::size_t selected_count) {
    using scalar_vec = ::tsl::simd<T, ::tsl::scalar>;

    static_assert(
        is_selection_index<IndexT>::value,
        "selection-vector input indices must use an unsigned integral row-id type");
    validate_integral_mask_layout<Vec>();

    std::size_t produced = 0;
    if constexpr (std::is_same<Vec, scalar_vec>::value) {
        for (std::size_t i = 0; i < selected_count; ++i) {
            auto x = ::tsl::@{algorithm_helper_contiguous_read}<scalar_vec, false>(
                selected_row_pointer<T, IndexT, Scale>(input, indices[i]));
            auto active = invoke_op<scalar_vec>(predicate, x);
            if (::tsl::@{algorithm_helper_integral_mask}<scalar_vec>(active) != 0) {
                produced += 1;
            }
        }
    } else {
        const std::size_t lanes = detail::lane_count<Vec>();
        const std::size_t chunk_count = selected_count / lanes;
        std::size_t i = 0;
        for (std::size_t chunk = 0; chunk < chunk_count; ++chunk, i += lanes) {
            (void)chunk;
            auto x = load_selected_vector<Vec, T, IndexT, Scale>(
                input, indices + i);
            auto active = invoke_op<Vec>(predicate, x);
            produced += ::tsl::@{algorithm_helper_mask_population_count}<Vec>(active);
        }
        for (; i < selected_count; ++i) {
            auto x = ::tsl::@{algorithm_helper_contiguous_read}<scalar_vec, false>(
                selected_row_pointer<T, IndexT, Scale>(input, indices[i]));
            auto active = invoke_op<scalar_vec>(predicate, x);
            if (::tsl::@{algorithm_helper_integral_mask}<scalar_vec>(active) != 0) {
                produced += 1;
            }
        }
    }
    return produced;
}

template <class Vec, std::size_t Scale, class Op, class T, class IndexT>
inline std::size_t count_selected_binary_loop(
    Op& predicate,
    const T* left,
    const T* right,
    const IndexT* indices,
    std::size_t selected_count) {
    using scalar_vec = ::tsl::simd<T, ::tsl::scalar>;

    static_assert(
        is_selection_index<IndexT>::value,
        "selection-vector input indices must use an unsigned integral row-id type");
    validate_integral_mask_layout<Vec>();

    std::size_t produced = 0;
    if constexpr (std::is_same<Vec, scalar_vec>::value) {
        for (std::size_t i = 0; i < selected_count; ++i) {
            auto x = ::tsl::@{algorithm_helper_contiguous_read}<scalar_vec, false>(
                selected_row_pointer<T, IndexT, Scale>(left, indices[i]));
            auto y = ::tsl::@{algorithm_helper_contiguous_read}<scalar_vec, false>(
                selected_row_pointer<T, IndexT, Scale>(right, indices[i]));
            auto active = invoke_op<scalar_vec>(predicate, x, y);
            if (::tsl::@{algorithm_helper_integral_mask}<scalar_vec>(active) != 0) {
                produced += 1;
            }
        }
    } else {
        const std::size_t lanes = detail::lane_count<Vec>();
        const std::size_t chunk_count = selected_count / lanes;
        std::size_t i = 0;
        for (std::size_t chunk = 0; chunk < chunk_count; ++chunk, i += lanes) {
            (void)chunk;
            auto x = load_selected_vector<Vec, T, IndexT, Scale>(
                left, indices + i);
            auto y = load_selected_vector<Vec, T, IndexT, Scale>(
                right, indices + i);
            auto active = invoke_op<Vec>(predicate, x, y);
            produced += ::tsl::@{algorithm_helper_mask_population_count}<Vec>(active);
        }
        for (; i < selected_count; ++i) {
            auto x = ::tsl::@{algorithm_helper_contiguous_read}<scalar_vec, false>(
                selected_row_pointer<T, IndexT, Scale>(left, indices[i]));
            auto y = ::tsl::@{algorithm_helper_contiguous_read}<scalar_vec, false>(
                selected_row_pointer<T, IndexT, Scale>(right, indices[i]));
            auto active = invoke_op<scalar_vec>(predicate, x, y);
            if (::tsl::@{algorithm_helper_integral_mask}<scalar_vec>(active) != 0) {
                produced += 1;
            }
        }
    }
    return produced;
}

template <class Vec, class LeftAlignment, class Op, class T>
inline std::size_t count_binary_dispatch_right(
    Op& predicate,
    const T* left,
    const T* right,
    std::size_t count) {
    if (is_aligned_for<Vec>(right)) {
        return count_binary_loop<
            Vec,
            LeftAlignment,
            alignment::assume_aligned>(predicate, left, right, count);
    }
    return count_binary_loop<
        Vec,
        LeftAlignment,
        alignment::unaligned>(predicate, left, right, count);
}

template <class Vec, class Op, class T>
inline std::size_t count_binary_dispatch_detect(
    Op& predicate,
    const T* left,
    const T* right,
    std::size_t count) {
    if (is_aligned_for<Vec>(left)) {
        return count_binary_dispatch_right<Vec, alignment::assume_aligned>(
            predicate, left, right, count);
    }
    return count_binary_dispatch_right<Vec, alignment::unaligned>(
        predicate, left, right, count);
}

template <class Vec, class MaskLayout, class LeftAlignment, class Op, class T>
inline std::size_t count_masked_binary_dispatch_right(
    Op& predicate,
    const T* left,
    const T* right,
    const mask_storage_for_vec_t<MaskLayout, Vec>* masks,
    std::size_t count) {
    if (is_aligned_for<Vec>(right)) {
        return count_masked_binary_loop<
            Vec,
            MaskLayout,
            LeftAlignment,
            alignment::assume_aligned>(
            predicate, left, right, masks, count);
    }
    return count_masked_binary_loop<
        Vec,
        MaskLayout,
        LeftAlignment,
        alignment::unaligned>(
        predicate, left, right, masks, count);
}

template <class Vec, class MaskLayout, class Op, class T>
inline std::size_t count_masked_binary_dispatch_detect(
    Op& predicate,
    const T* left,
    const T* right,
    const mask_storage_for_vec_t<MaskLayout, Vec>* masks,
    std::size_t count) {
    if (is_aligned_for<Vec>(left)) {
        return count_masked_binary_dispatch_right<
            Vec,
            MaskLayout,
            alignment::assume_aligned>(
            predicate, left, right, masks, count);
    }
    return count_masked_binary_dispatch_right<
        Vec,
        MaskLayout,
        alignment::unaligned>(
        predicate, left, right, masks, count);
}

}  // namespace tsl::algo::detail
