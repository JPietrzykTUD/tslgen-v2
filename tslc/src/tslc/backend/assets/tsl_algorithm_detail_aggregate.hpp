#pragma once

#include "tsl_algorithm_detail_mask.hpp"

namespace tsl::algo::detail {

template <class Vec, std::size_t Scale, class Op, class T, class IndexT>
inline auto aggregate_selected_unary_loop(
    Op& op,
    const T* input,
    const IndexT* indices,
    std::size_t selected_count) {
    using scalar_vec = ::tsl::simd<T, ::tsl::scalar>;

    static_assert(
        is_selection_index<IndexT>::value,
        "selection-vector input indices must use an unsigned integral row-id type");

    if constexpr (std::is_same<Vec, scalar_vec>::value) {
        for (std::size_t i = 0; i < selected_count; ++i) {
            auto x = ::tsl::load<scalar_vec, false>(
                selected_row_pointer<T, IndexT, Scale>(input, indices[i]));
            invoke_op<scalar_vec>(op, x);
        }
    } else {
        const std::size_t lanes = detail::lane_count<Vec>();
        const std::size_t chunk_count = selected_count / lanes;
        std::size_t i = 0;
        for (std::size_t chunk = 0; chunk < chunk_count; ++chunk, i += lanes) {
            (void)chunk;
            auto x = load_selected_vector<Vec, T, IndexT, Scale>(
                input, indices + i);
            invoke_op<Vec>(op, x);
        }
        for (; i < selected_count; ++i) {
            auto x = ::tsl::load<scalar_vec, false>(
                selected_row_pointer<T, IndexT, Scale>(input, indices[i]));
            invoke_op<scalar_vec>(op, x);
        }
    }
    return finalize_op(op);
}

template <class Vec, std::size_t Scale, class Op, class T, class IndexT>
inline auto aggregate_selected_binary_loop(
    Op& op,
    const T* left,
    const T* right,
    const IndexT* indices,
    std::size_t selected_count) {
    using scalar_vec = ::tsl::simd<T, ::tsl::scalar>;

    static_assert(
        is_selection_index<IndexT>::value,
        "selection-vector input indices must use an unsigned integral row-id type");

    if constexpr (std::is_same<Vec, scalar_vec>::value) {
        for (std::size_t i = 0; i < selected_count; ++i) {
            auto x = ::tsl::load<scalar_vec, false>(
                selected_row_pointer<T, IndexT, Scale>(left, indices[i]));
            auto y = ::tsl::load<scalar_vec, false>(
                selected_row_pointer<T, IndexT, Scale>(right, indices[i]));
            invoke_op<scalar_vec>(op, x, y);
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
            invoke_op<Vec>(op, x, y);
        }
        for (; i < selected_count; ++i) {
            auto x = ::tsl::load<scalar_vec, false>(
                selected_row_pointer<T, IndexT, Scale>(left, indices[i]));
            auto y = ::tsl::load<scalar_vec, false>(
                selected_row_pointer<T, IndexT, Scale>(right, indices[i]));
            invoke_op<scalar_vec>(op, x, y);
        }
    }
    return finalize_op(op);
}

template <class Vec, class InputAlignment, class Op, class T>
inline auto aggregate_unary_loop(
    Op& op,
    const T* input,
    std::size_t count) {
    using scalar_vec = ::tsl::simd<T, ::tsl::scalar>;
    constexpr bool input_aligned =
        std::is_same<InputAlignment, alignment::assume_aligned>::value;

    const std::size_t lanes = detail::lane_count<Vec>();
    const std::size_t chunk_count = count / lanes;
    std::size_t i = 0;
    for (std::size_t chunk = 0; chunk < chunk_count; ++chunk, i += lanes) {
        auto x = ::tsl::load<Vec, input_aligned>(input + i);
        invoke_op<Vec>(op, x);
    }
    for (; i < count; ++i) {
        auto x = ::tsl::load<scalar_vec, false>(input + i);
        invoke_op<scalar_vec>(op, x);
    }
    return finalize_op(op);
}

template <
    class Vec,
    class LeftAlignment,
    class RightAlignment,
    class Op,
    class T>
inline auto aggregate_binary_loop(
    Op& op,
    const T* left,
    const T* right,
    std::size_t count) {
    using scalar_vec = ::tsl::simd<T, ::tsl::scalar>;
    constexpr bool left_aligned =
        std::is_same<LeftAlignment, alignment::assume_aligned>::value;
    constexpr bool right_aligned =
        std::is_same<RightAlignment, alignment::assume_aligned>::value;

    const std::size_t lanes = detail::lane_count<Vec>();
    const std::size_t chunk_count = count / lanes;
    std::size_t i = 0;
    for (std::size_t chunk = 0; chunk < chunk_count; ++chunk, i += lanes) {
        auto x = ::tsl::load<Vec, left_aligned>(left + i);
        auto y = ::tsl::load<Vec, right_aligned>(right + i);
        invoke_op<Vec>(op, x, y);
    }
    for (; i < count; ++i) {
        auto x = ::tsl::load<scalar_vec, false>(left + i);
        auto y = ::tsl::load<scalar_vec, false>(right + i);
        invoke_op<scalar_vec>(op, x, y);
    }
    return finalize_op(op);
}

template <
    class Vec,
    class MaskLayout,
    class InputAlignment,
    class Op,
    class T>
inline auto aggregate_masked_unary_loop(
    Op& op,
    const T* input,
    const mask_storage_for_vec_t<MaskLayout, Vec>* masks,
    std::size_t count) {
    using scalar_vec = ::tsl::simd<T, ::tsl::scalar>;
    constexpr bool input_aligned =
        std::is_same<InputAlignment, alignment::assume_aligned>::value;

    validate_mask_layout<MaskLayout, Vec>();

    const std::size_t lanes = detail::lane_count<Vec>();
    const std::size_t chunk_count = count / lanes;
    std::size_t i = 0;
    for (std::size_t chunk = 0; chunk < chunk_count; ++chunk, i += lanes) {
        auto active = load_mask_storage<MaskLayout, Vec>(masks, chunk, i);
        auto x = ::tsl::load<Vec, input_aligned>(input + i);
        invoke_required_masked_op<Vec>(op, active, x);
    }
    for (std::size_t lane = 0; i < count; ++i, ++lane) {
        const bool active = mask_storage_lane_active<MaskLayout, Vec>(
            masks, chunk_count, i, lane);
        auto x = ::tsl::load<scalar_vec, false>(input + i);
        invoke_required_masked_op<scalar_vec>(op, active, x);
    }
    return finalize_op(op);
}

template <
    class Vec,
    class MaskLayout,
    class LeftAlignment,
    class RightAlignment,
    class Op,
    class T>
inline auto aggregate_masked_binary_loop(
    Op& op,
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

    const std::size_t lanes = detail::lane_count<Vec>();
    const std::size_t chunk_count = count / lanes;
    std::size_t i = 0;
    for (std::size_t chunk = 0; chunk < chunk_count; ++chunk, i += lanes) {
        auto active = load_mask_storage<MaskLayout, Vec>(masks, chunk, i);
        auto x = ::tsl::load<Vec, left_aligned>(left + i);
        auto y = ::tsl::load<Vec, right_aligned>(right + i);
        invoke_required_masked_op<Vec>(op, active, x, y);
    }
    for (std::size_t lane = 0; i < count; ++i, ++lane) {
        const bool active = mask_storage_lane_active<MaskLayout, Vec>(
            masks, chunk_count, i, lane);
        auto x = ::tsl::load<scalar_vec, false>(left + i);
        auto y = ::tsl::load<scalar_vec, false>(right + i);
        invoke_required_masked_op<scalar_vec>(op, active, x, y);
    }
    return finalize_op(op);
}

template <class Vec, class LeftAlignment, class Op, class T>
inline auto aggregate_binary_dispatch_right(
    Op& op,
    const T* left,
    const T* right,
    std::size_t count) {
    if (is_aligned_for<Vec>(right)) {
        return aggregate_binary_loop<
            Vec,
            LeftAlignment,
            alignment::assume_aligned>(op, left, right, count);
    }
    return aggregate_binary_loop<
        Vec,
        LeftAlignment,
        alignment::unaligned>(op, left, right, count);
}

template <class Vec, class Op, class T>
inline auto aggregate_binary_dispatch_detect(
    Op& op,
    const T* left,
    const T* right,
    std::size_t count) {
    if (is_aligned_for<Vec>(left)) {
        return aggregate_binary_dispatch_right<Vec, alignment::assume_aligned>(
            op, left, right, count);
    }
    return aggregate_binary_dispatch_right<Vec, alignment::unaligned>(
        op, left, right, count);
}

template <class Vec, class MaskLayout, class LeftAlignment, class Op, class T>
inline auto aggregate_masked_binary_dispatch_right(
    Op& op,
    const T* left,
    const T* right,
    const mask_storage_for_vec_t<MaskLayout, Vec>* masks,
    std::size_t count) {
    if (is_aligned_for<Vec>(right)) {
        return aggregate_masked_binary_loop<
            Vec,
            MaskLayout,
            LeftAlignment,
            alignment::assume_aligned>(op, left, right, masks, count);
    }
    return aggregate_masked_binary_loop<
        Vec,
        MaskLayout,
        LeftAlignment,
        alignment::unaligned>(op, left, right, masks, count);
}

template <class Vec, class MaskLayout, class Op, class T>
inline auto aggregate_masked_binary_dispatch_detect(
    Op& op,
    const T* left,
    const T* right,
    const mask_storage_for_vec_t<MaskLayout, Vec>* masks,
    std::size_t count) {
    if (is_aligned_for<Vec>(left)) {
        return aggregate_masked_binary_dispatch_right<
            Vec,
            MaskLayout,
            alignment::assume_aligned>(
            op, left, right, masks, count);
    }
    return aggregate_masked_binary_dispatch_right<
        Vec,
        MaskLayout,
        alignment::unaligned>(
        op, left, right, masks, count);
}

}  // namespace tsl::algo::detail
