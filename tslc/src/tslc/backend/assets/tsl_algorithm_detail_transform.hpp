#pragma once

#include "tsl_algorithm_detail_mask.hpp"

namespace tsl::algo::detail {

template <
    class Vec,
    class InputAlignment,
    class OutputAlignment,
    class Op,
    class T>
inline void transform_unary_loop(
    Op& op,
    const T* input,
    T* output,
    std::size_t count) {
    using scalar_vec = ::tsl::simd<T, ::tsl::scalar>;
    constexpr bool input_aligned =
        std::is_same<InputAlignment, alignment::assume_aligned>::value;
    constexpr bool output_aligned =
        std::is_same<OutputAlignment, alignment::assume_aligned>::value;

    const std::size_t lanes = detail::lane_count<Vec>();
    const std::size_t chunk_count = count / lanes;
    std::size_t i = 0;
    for (std::size_t chunk = 0; chunk < chunk_count; ++chunk, i += lanes) {
        auto x = ::tsl::load<Vec, input_aligned>(input + i);
        auto y = invoke_op<Vec>(op, x);
        ::tsl::store<Vec, output_aligned>(output + i, y);
    }
    for (; i < count; ++i) {
        auto x = ::tsl::load<scalar_vec, false>(input + i);
        auto y = invoke_op<scalar_vec>(op, x);
        ::tsl::store<scalar_vec, false>(output + i, y);
    }
}

template <
    class Vec,
    class LeftAlignment,
    class RightAlignment,
    class OutputAlignment,
    class Op,
    class T>
inline void transform_binary_loop(
    Op& op,
    const T* left,
    const T* right,
    T* output,
    std::size_t count) {
    using scalar_vec = ::tsl::simd<T, ::tsl::scalar>;
    constexpr bool left_aligned =
        std::is_same<LeftAlignment, alignment::assume_aligned>::value;
    constexpr bool right_aligned =
        std::is_same<RightAlignment, alignment::assume_aligned>::value;
    constexpr bool output_aligned =
        std::is_same<OutputAlignment, alignment::assume_aligned>::value;

    const std::size_t lanes = detail::lane_count<Vec>();
    const std::size_t chunk_count = count / lanes;
    std::size_t i = 0;
    for (std::size_t chunk = 0; chunk < chunk_count; ++chunk, i += lanes) {
        auto x = ::tsl::load<Vec, left_aligned>(left + i);
        auto y = ::tsl::load<Vec, right_aligned>(right + i);
        auto z = invoke_op<Vec>(op, x, y);
        ::tsl::store<Vec, output_aligned>(output + i, z);
    }
    for (; i < count; ++i) {
        auto x = ::tsl::load<scalar_vec, false>(left + i);
        auto y = ::tsl::load<scalar_vec, false>(right + i);
        auto z = invoke_op<scalar_vec>(op, x, y);
        ::tsl::store<scalar_vec, false>(output + i, z);
    }
}

template <
    class Vec,
    class LeftAlignment,
    class RightAlignment,
    class Op,
    class T>
inline void transform_binary_dispatch_output(
    Op& op,
    const T* left,
    const T* right,
    T* output,
    std::size_t count) {
    if (is_aligned_for<Vec>(output)) {
        transform_binary_loop<
            Vec,
            LeftAlignment,
            RightAlignment,
            alignment::assume_aligned>(op, left, right, output, count);
    } else {
        transform_binary_loop<
            Vec,
            LeftAlignment,
            RightAlignment,
            alignment::unaligned>(op, left, right, output, count);
    }
}

template <class Vec, class LeftAlignment, class Op, class T>
inline void transform_binary_dispatch_right(
    Op& op,
    const T* left,
    const T* right,
    T* output,
    std::size_t count) {
    if (is_aligned_for<Vec>(right)) {
        transform_binary_dispatch_output<
            Vec,
            LeftAlignment,
            alignment::assume_aligned>(op, left, right, output, count);
    } else {
        transform_binary_dispatch_output<
            Vec,
            LeftAlignment,
            alignment::unaligned>(op, left, right, output, count);
    }
}

template <class Vec, class Op, class T>
inline void transform_binary_dispatch_detect(
    Op& op,
    const T* left,
    const T* right,
    T* output,
    std::size_t count) {
    if (is_aligned_for<Vec>(left)) {
        transform_binary_dispatch_right<Vec, alignment::assume_aligned>(
            op, left, right, output, count);
    } else {
        transform_binary_dispatch_right<Vec, alignment::unaligned>(
            op, left, right, output, count);
    }
}

template <class Vec, class Op, class T>
inline void transform_unary_loop_peel_to_aligned(
    Op& op,
    const T* input,
    T* output,
    std::size_t count) {
    using scalar_vec = ::tsl::simd<T, ::tsl::scalar>;

    if (!has_same_alignment_residue<Vec>(input, output)) {
        transform_unary_loop<
            Vec,
            alignment::unaligned,
            alignment::unaligned>(op, input, output, count);
        return;
    }

    const std::size_t peel = scalar_peel_count_to_alignment<Vec>(input, count);
    if (peel != 0) {
        transform_unary_loop<
            scalar_vec,
            alignment::unaligned,
            alignment::unaligned>(op, input, output, peel);
    }
    if (peel == count) {
        return;
    }

    transform_unary_loop<
        Vec,
        alignment::assume_aligned,
        alignment::assume_aligned>(op, input + peel, output + peel, count - peel);
}

template <class Vec, class Op, class T>
inline void transform_binary_loop_peel_to_aligned(
    Op& op,
    const T* left,
    const T* right,
    T* output,
    std::size_t count) {
    using scalar_vec = ::tsl::simd<T, ::tsl::scalar>;

    if (!has_same_alignment_residue<Vec>(left, right, output)) {
        transform_binary_loop<
            Vec,
            alignment::unaligned,
            alignment::unaligned,
            alignment::unaligned>(op, left, right, output, count);
        return;
    }

    const std::size_t peel = scalar_peel_count_to_alignment<Vec>(left, count);
    if (peel != 0) {
        transform_binary_loop<
            scalar_vec,
            alignment::unaligned,
            alignment::unaligned,
            alignment::unaligned>(op, left, right, output, peel);
    }
    if (peel == count) {
        return;
    }

    transform_binary_loop<
        Vec,
        alignment::assume_aligned,
        alignment::assume_aligned,
        alignment::assume_aligned>(
            op,
            left + peel,
            right + peel,
            output + peel,
            count - peel);
}

template <
    class Vec,
    class MaskLayout,
    class InputAlignment,
    class OutputAlignment,
    class Op,
    class T>
inline void transform_where_unary_loop(
    Op& op,
    const T* input,
    const mask_storage_for_vec_t<MaskLayout, Vec>* masks,
    T* output,
    std::size_t count) {
    using scalar_vec = ::tsl::simd<T, ::tsl::scalar>;
    constexpr bool input_aligned =
        std::is_same<InputAlignment, alignment::assume_aligned>::value;
    constexpr bool output_aligned =
        std::is_same<OutputAlignment, alignment::assume_aligned>::value;

    validate_mask_layout<MaskLayout, Vec>();

    const std::size_t lanes = detail::lane_count<Vec>();
    const std::size_t chunk_count = count / lanes;
    std::size_t i = 0;
    for (std::size_t chunk = 0; chunk < chunk_count; ++chunk, i += lanes) {
        auto active = load_mask_storage<MaskLayout, Vec>(masks, chunk, i);
        auto x = ::tsl::load<Vec, input_aligned>(input + i);
        auto y = invoke_masked_op<Vec>(op, active, x);
        ::tsl::store_mask<Vec, output_aligned>(active, output + i, y);
    }
    if (i == count) {
        return;
    }

    for (std::size_t lane = 0; i < count; ++i, ++lane) {
        if (!mask_storage_lane_active<MaskLayout, Vec>(
                masks, chunk_count, i, lane)) {
            continue;
        }
        auto x = ::tsl::load<scalar_vec, false>(input + i);
        auto y = invoke_masked_op<scalar_vec>(op, true, x);
        ::tsl::store<scalar_vec, false>(output + i, y);
    }
}

template <
    class Vec,
    class MaskLayout,
    class LeftAlignment,
    class RightAlignment,
    class OutputAlignment,
    class Op,
    class T>
inline void transform_where_binary_loop(
    Op& op,
    const T* left,
    const T* right,
    const mask_storage_for_vec_t<MaskLayout, Vec>* masks,
    T* output,
    std::size_t count) {
    using scalar_vec = ::tsl::simd<T, ::tsl::scalar>;
    constexpr bool left_aligned =
        std::is_same<LeftAlignment, alignment::assume_aligned>::value;
    constexpr bool right_aligned =
        std::is_same<RightAlignment, alignment::assume_aligned>::value;
    constexpr bool output_aligned =
        std::is_same<OutputAlignment, alignment::assume_aligned>::value;

    validate_mask_layout<MaskLayout, Vec>();

    const std::size_t lanes = detail::lane_count<Vec>();
    const std::size_t chunk_count = count / lanes;
    std::size_t i = 0;
    for (std::size_t chunk = 0; chunk < chunk_count; ++chunk, i += lanes) {
        auto active = load_mask_storage<MaskLayout, Vec>(masks, chunk, i);
        auto x = ::tsl::load<Vec, left_aligned>(left + i);
        auto y = ::tsl::load<Vec, right_aligned>(right + i);
        auto z = invoke_masked_op<Vec>(op, active, x, y);
        ::tsl::store_mask<Vec, output_aligned>(active, output + i, z);
    }
    if (i == count) {
        return;
    }

    for (std::size_t lane = 0; i < count; ++i, ++lane) {
        if (!mask_storage_lane_active<MaskLayout, Vec>(
                masks, chunk_count, i, lane)) {
            continue;
        }
        auto x = ::tsl::load<scalar_vec, false>(left + i);
        auto y = ::tsl::load<scalar_vec, false>(right + i);
        auto z = invoke_masked_op<scalar_vec>(op, true, x, y);
        ::tsl::store<scalar_vec, false>(output + i, z);
    }
}

template <
    class Vec,
    class MaskLayout,
    class InputAlignment,
    class OutputAlignment,
    class Op,
    class T>
inline void transform_masked_unary_loop(
    Op& op,
    const T* input,
    const mask_storage_for_vec_t<MaskLayout, Vec>* masks,
    T* output,
    std::size_t count) {
    using scalar_vec = ::tsl::simd<T, ::tsl::scalar>;
    constexpr bool input_aligned =
        std::is_same<InputAlignment, alignment::assume_aligned>::value;
    constexpr bool output_aligned =
        std::is_same<OutputAlignment, alignment::assume_aligned>::value;

    validate_mask_layout<MaskLayout, Vec>();

    const std::size_t lanes = detail::lane_count<Vec>();
    const std::size_t chunk_count = count / lanes;
    std::size_t i = 0;
    for (std::size_t chunk = 0; chunk < chunk_count; ++chunk, i += lanes) {
        auto active = load_mask_storage<MaskLayout, Vec>(masks, chunk, i);
        auto x = ::tsl::load<Vec, input_aligned>(input + i);
        auto y = invoke_masked_op<Vec>(op, active, x);
        ::tsl::store<Vec, output_aligned>(output + i, y);
    }
    if (i == count) {
        return;
    }

    for (std::size_t lane = 0; i < count; ++i, ++lane) {
        const bool active = mask_storage_lane_active<MaskLayout, Vec>(
            masks, chunk_count, i, lane);
        auto x = ::tsl::load<scalar_vec, false>(input + i);
        auto y = invoke_masked_op<scalar_vec>(op, active, x);
        ::tsl::store<scalar_vec, false>(output + i, y);
    }
}

template <
    class Vec,
    class MaskLayout,
    class LeftAlignment,
    class RightAlignment,
    class OutputAlignment,
    class Op,
    class T>
inline void transform_masked_binary_loop(
    Op& op,
    const T* left,
    const T* right,
    const mask_storage_for_vec_t<MaskLayout, Vec>* masks,
    T* output,
    std::size_t count) {
    using scalar_vec = ::tsl::simd<T, ::tsl::scalar>;
    constexpr bool left_aligned =
        std::is_same<LeftAlignment, alignment::assume_aligned>::value;
    constexpr bool right_aligned =
        std::is_same<RightAlignment, alignment::assume_aligned>::value;
    constexpr bool output_aligned =
        std::is_same<OutputAlignment, alignment::assume_aligned>::value;

    validate_mask_layout<MaskLayout, Vec>();

    const std::size_t lanes = detail::lane_count<Vec>();
    const std::size_t chunk_count = count / lanes;
    std::size_t i = 0;
    for (std::size_t chunk = 0; chunk < chunk_count; ++chunk, i += lanes) {
        auto active = load_mask_storage<MaskLayout, Vec>(masks, chunk, i);
        auto x = ::tsl::load<Vec, left_aligned>(left + i);
        auto y = ::tsl::load<Vec, right_aligned>(right + i);
        auto z = invoke_masked_op<Vec>(op, active, x, y);
        ::tsl::store<Vec, output_aligned>(output + i, z);
    }
    if (i == count) {
        return;
    }

    for (std::size_t lane = 0; i < count; ++i, ++lane) {
        const bool active = mask_storage_lane_active<MaskLayout, Vec>(
            masks, chunk_count, i, lane);
        auto x = ::tsl::load<scalar_vec, false>(left + i);
        auto y = ::tsl::load<scalar_vec, false>(right + i);
        auto z = invoke_masked_op<scalar_vec>(op, active, x, y);
        ::tsl::store<scalar_vec, false>(output + i, z);
    }
}

template <class Vec, std::size_t Scale, class Op, class T, class IndexT>
inline void transform_selected_unary_loop(
    Op& op,
    const T* input,
    const IndexT* indices,
    T* output,
    std::size_t selected_count) {
    using scalar_vec = ::tsl::simd<T, ::tsl::scalar>;

    static_assert(
        is_selection_index<IndexT>::value,
        "selection-vector input indices must use an unsigned integral row-id type");

    if constexpr (std::is_same<Vec, scalar_vec>::value) {
        for (std::size_t i = 0; i < selected_count; ++i) {
            auto x = ::tsl::load<scalar_vec, false>(
                selected_row_pointer<T, IndexT, Scale>(input, indices[i]));
            auto y = invoke_op<scalar_vec>(op, x);
            ::tsl::store<scalar_vec, false>(output + i, y);
        }
    } else {
        const std::size_t lanes = detail::lane_count<Vec>();
        const std::size_t chunk_count = selected_count / lanes;
        std::size_t i = 0;
        for (std::size_t chunk = 0; chunk < chunk_count; ++chunk, i += lanes) {
            (void)chunk;
            auto x = load_selected_vector<Vec, T, IndexT, Scale>(
                input, indices + i);
            auto y = invoke_op<Vec>(op, x);
            ::tsl::store<Vec, false>(output + i, y);
        }
        for (; i < selected_count; ++i) {
            auto x = ::tsl::load<scalar_vec, false>(
                selected_row_pointer<T, IndexT, Scale>(input, indices[i]));
            auto y = invoke_op<scalar_vec>(op, x);
            ::tsl::store<scalar_vec, false>(output + i, y);
        }
    }
}

template <class Vec, std::size_t Scale, class Op, class T, class IndexT>
inline void transform_selected_binary_loop(
    Op& op,
    const T* left,
    const T* right,
    const IndexT* indices,
    T* output,
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
            auto z = invoke_op<scalar_vec>(op, x, y);
            ::tsl::store<scalar_vec, false>(output + i, z);
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
            auto z = invoke_op<Vec>(op, x, y);
            ::tsl::store<Vec, false>(output + i, z);
        }
        for (; i < selected_count; ++i) {
            auto x = ::tsl::load<scalar_vec, false>(
                selected_row_pointer<T, IndexT, Scale>(left, indices[i]));
            auto y = ::tsl::load<scalar_vec, false>(
                selected_row_pointer<T, IndexT, Scale>(right, indices[i]));
            auto z = invoke_op<scalar_vec>(op, x, y);
            ::tsl::store<scalar_vec, false>(output + i, z);
        }
    }
}

template <
    class Vec,
    class MaskLayout,
    class LeftAlignment,
    class RightAlignment,
    class Op,
    class T>
inline void transform_where_binary_dispatch_output(
    Op& op,
    const T* left,
    const T* right,
    const mask_storage_for_vec_t<MaskLayout, Vec>* masks,
    T* output,
    std::size_t count) {
    if (is_aligned_for<Vec>(output)) {
        transform_where_binary_loop<
            Vec,
            MaskLayout,
            LeftAlignment,
            RightAlignment,
            alignment::assume_aligned>(op, left, right, masks, output, count);
    } else {
        transform_where_binary_loop<
            Vec,
            MaskLayout,
            LeftAlignment,
            RightAlignment,
            alignment::unaligned>(op, left, right, masks, output, count);
    }
}

template <class Vec, class MaskLayout, class LeftAlignment, class Op, class T>
inline void transform_where_binary_dispatch_right(
    Op& op,
    const T* left,
    const T* right,
    const mask_storage_for_vec_t<MaskLayout, Vec>* masks,
    T* output,
    std::size_t count) {
    if (is_aligned_for<Vec>(right)) {
        transform_where_binary_dispatch_output<
            Vec,
            MaskLayout,
            LeftAlignment,
            alignment::assume_aligned>(op, left, right, masks, output, count);
    } else {
        transform_where_binary_dispatch_output<
            Vec,
            MaskLayout,
            LeftAlignment,
            alignment::unaligned>(op, left, right, masks, output, count);
    }
}

template <class Vec, class MaskLayout, class Op, class T>
inline void transform_where_binary_dispatch_detect(
    Op& op,
    const T* left,
    const T* right,
    const mask_storage_for_vec_t<MaskLayout, Vec>* masks,
    T* output,
    std::size_t count) {
    if (is_aligned_for<Vec>(left)) {
        transform_where_binary_dispatch_right<
            Vec,
            MaskLayout,
            alignment::assume_aligned>(
            op, left, right, masks, output, count);
    } else {
        transform_where_binary_dispatch_right<
            Vec,
            MaskLayout,
            alignment::unaligned>(
            op, left, right, masks, output, count);
    }
}

template <
    class Vec,
    class MaskLayout,
    class LeftAlignment,
    class RightAlignment,
    class Op,
    class T>
inline void transform_masked_binary_dispatch_output(
    Op& op,
    const T* left,
    const T* right,
    const mask_storage_for_vec_t<MaskLayout, Vec>* masks,
    T* output,
    std::size_t count) {
    if (is_aligned_for<Vec>(output)) {
        transform_masked_binary_loop<
            Vec,
            MaskLayout,
            LeftAlignment,
            RightAlignment,
            alignment::assume_aligned>(op, left, right, masks, output, count);
    } else {
        transform_masked_binary_loop<
            Vec,
            MaskLayout,
            LeftAlignment,
            RightAlignment,
            alignment::unaligned>(op, left, right, masks, output, count);
    }
}

template <class Vec, class MaskLayout, class LeftAlignment, class Op, class T>
inline void transform_masked_binary_dispatch_right(
    Op& op,
    const T* left,
    const T* right,
    const mask_storage_for_vec_t<MaskLayout, Vec>* masks,
    T* output,
    std::size_t count) {
    if (is_aligned_for<Vec>(right)) {
        transform_masked_binary_dispatch_output<
            Vec,
            MaskLayout,
            LeftAlignment,
            alignment::assume_aligned>(op, left, right, masks, output, count);
    } else {
        transform_masked_binary_dispatch_output<
            Vec,
            MaskLayout,
            LeftAlignment,
            alignment::unaligned>(op, left, right, masks, output, count);
    }
}

template <class Vec, class MaskLayout, class Op, class T>
inline void transform_masked_binary_dispatch_detect(
    Op& op,
    const T* left,
    const T* right,
    const mask_storage_for_vec_t<MaskLayout, Vec>* masks,
    T* output,
    std::size_t count) {
    if (is_aligned_for<Vec>(left)) {
        transform_masked_binary_dispatch_right<
            Vec,
            MaskLayout,
            alignment::assume_aligned>(
            op, left, right, masks, output, count);
    } else {
        transform_masked_binary_dispatch_right<
            Vec,
            MaskLayout,
            alignment::unaligned>(
            op, left, right, masks, output, count);
    }
}

}  // namespace tsl::algo::detail
