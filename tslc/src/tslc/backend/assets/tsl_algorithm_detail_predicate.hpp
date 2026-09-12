#pragma once

#include "tsl_algorithm_detail_mask.hpp"

namespace tsl::algo::detail {

template <class Vec, class MaskLayout, class InputAlignment, class Op, class T>
inline std::size_t predicate_unary_loop(
    Op& op,
    const T* input,
    mask_storage_for_vec_t<MaskLayout, Vec>* masks,
    std::size_t count) {
    using scalar_vec = ::tsl::simd<T, ::tsl::scalar>;
    constexpr bool input_aligned =
        std::is_same<InputAlignment, alignment::assume_aligned>::value;

    validate_mask_layout<MaskLayout, Vec>();
    clear_predicate_mask_storage<MaskLayout, Vec>(masks, count);

    const std::size_t lanes = detail::lane_count<Vec>();
    const std::size_t chunk_count = count / lanes;
    std::size_t i = 0;
    for (std::size_t chunk = 0; chunk < chunk_count; ++chunk, i += lanes) {
        auto x = ::tsl::load<Vec, input_aligned>(input + i);
        auto mask = invoke_op<Vec>(op, x);
        store_mask_storage<MaskLayout, Vec>(masks, chunk, i, mask);
    }
    if (i == count) {
        if constexpr (is_row_mask_layout<MaskLayout>()) {
            return row_mask_storage_count<MaskLayout>(count);
        } else {
            return chunk_count;
        }
    }

    if constexpr (is_row_mask_layout<MaskLayout>()) {
        for (std::size_t lane = 0; i < count; ++i, ++lane) {
            auto x = ::tsl::load<scalar_vec, false>(input + i);
            auto active = invoke_op<scalar_vec>(op, x);
            store_tail_mask_storage<MaskLayout, Vec>(
                masks,
                chunk_count,
                i,
                lane,
                ::tsl::to_integral<scalar_vec>(active) != 0);
        }
        return row_mask_storage_count<MaskLayout>(count);
    } else {
        typename Vec::imask_type tail_mask{};
        for (std::size_t lane = 0; i < count; ++i, ++lane) {
            auto x = ::tsl::load<scalar_vec, false>(input + i);
            auto active = invoke_op<scalar_vec>(op, x);
            if (::tsl::to_integral<scalar_vec>(active) != 0) {
                tail_mask = imask_set_lane<Vec>(tail_mask, lane);
            }
        }
        masks[chunk_count] = mask_storage_from_integral<MaskLayout, Vec>(tail_mask);
        return chunk_count + 1;
    }
}

template <
    class Vec,
    class MaskLayout,
    class LeftAlignment,
    class RightAlignment,
    class Op,
    class T>
inline std::size_t predicate_binary_loop(
    Op& op,
    const T* left,
    const T* right,
    mask_storage_for_vec_t<MaskLayout, Vec>* masks,
    std::size_t count) {
    using scalar_vec = ::tsl::simd<T, ::tsl::scalar>;
    constexpr bool left_aligned =
        std::is_same<LeftAlignment, alignment::assume_aligned>::value;
    constexpr bool right_aligned =
        std::is_same<RightAlignment, alignment::assume_aligned>::value;

    validate_mask_layout<MaskLayout, Vec>();
    clear_predicate_mask_storage<MaskLayout, Vec>(masks, count);

    const std::size_t lanes = detail::lane_count<Vec>();
    const std::size_t chunk_count = count / lanes;
    std::size_t i = 0;
    for (std::size_t chunk = 0; chunk < chunk_count; ++chunk, i += lanes) {
        auto x = ::tsl::load<Vec, left_aligned>(left + i);
        auto y = ::tsl::load<Vec, right_aligned>(right + i);
        auto mask = invoke_op<Vec>(op, x, y);
        store_mask_storage<MaskLayout, Vec>(masks, chunk, i, mask);
    }
    if (i == count) {
        if constexpr (is_row_mask_layout<MaskLayout>()) {
            return row_mask_storage_count<MaskLayout>(count);
        } else {
            return chunk_count;
        }
    }

    if constexpr (is_row_mask_layout<MaskLayout>()) {
        for (std::size_t lane = 0; i < count; ++i, ++lane) {
            auto x = ::tsl::load<scalar_vec, false>(left + i);
            auto y = ::tsl::load<scalar_vec, false>(right + i);
            auto active = invoke_op<scalar_vec>(op, x, y);
            store_tail_mask_storage<MaskLayout, Vec>(
                masks,
                chunk_count,
                i,
                lane,
                ::tsl::to_integral<scalar_vec>(active) != 0);
        }
        return row_mask_storage_count<MaskLayout>(count);
    } else {
        typename Vec::imask_type tail_mask{};
        for (std::size_t lane = 0; i < count; ++i, ++lane) {
            auto x = ::tsl::load<scalar_vec, false>(left + i);
            auto y = ::tsl::load<scalar_vec, false>(right + i);
            auto active = invoke_op<scalar_vec>(op, x, y);
            if (::tsl::to_integral<scalar_vec>(active) != 0) {
                tail_mask = imask_set_lane<Vec>(tail_mask, lane);
            }
        }
        masks[chunk_count] = mask_storage_from_integral<MaskLayout, Vec>(tail_mask);
        return chunk_count + 1;
    }
}

template <class Vec, class MaskLayout, class LeftAlignment, class Op, class T>
inline std::size_t predicate_binary_dispatch_right(
    Op& op,
    const T* left,
    const T* right,
    mask_storage_for_vec_t<MaskLayout, Vec>* masks,
    std::size_t count) {
    if (is_aligned_for<Vec>(right)) {
        return predicate_binary_loop<
            Vec,
            MaskLayout,
            LeftAlignment,
            alignment::assume_aligned>(op, left, right, masks, count);
    }
    return predicate_binary_loop<
        Vec,
        MaskLayout,
        LeftAlignment,
        alignment::unaligned>(op, left, right, masks, count);
}

template <class Vec, class MaskLayout, class Op, class T>
inline std::size_t predicate_binary_dispatch_detect(
    Op& op,
    const T* left,
    const T* right,
    mask_storage_for_vec_t<MaskLayout, Vec>* masks,
    std::size_t count) {
    if (is_aligned_for<Vec>(left)) {
        return predicate_binary_dispatch_right<
            Vec,
            MaskLayout,
            alignment::assume_aligned>(
            op, left, right, masks, count);
    }
    return predicate_binary_dispatch_right<
        Vec,
        MaskLayout,
        alignment::unaligned>(
        op, left, right, masks, count);
}

}  // namespace tsl::algo::detail
