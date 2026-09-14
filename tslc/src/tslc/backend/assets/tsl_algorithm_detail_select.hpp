#pragma once

#include "tsl_algorithm_detail_mask.hpp"

namespace tsl::algo::detail {

template <class Vec, class InputAlignment, class Op, class T>
inline std::size_t select_unary_loop(
    Op& predicate,
    const T* input,
    T* output,
    std::size_t count) {
    using scalar_vec = ::tsl::simd<T, ::tsl::scalar>;
    constexpr bool input_aligned =
        std::is_same<InputAlignment, alignment::assume_aligned>::value;

    const std::size_t lanes = detail::lane_count<Vec>();
    const std::size_t chunk_count = count / lanes;
    std::size_t produced = 0;
    std::size_t i = 0;
    for (std::size_t chunk = 0; chunk < chunk_count; ++chunk, i += lanes) {
        auto x = ::tsl::@{algorithm_helper_contiguous_read}<Vec, input_aligned>(input + i);
        auto active = invoke_op<Vec>(predicate, x);
        ::tsl::@{algorithm_helper_compaction}<Vec, true>(active, output + produced, x);
        produced += ::tsl::@{algorithm_helper_mask_population_count}<Vec>(active);
    }
    for (; i < count; ++i) {
        auto x = ::tsl::@{algorithm_helper_contiguous_read}<scalar_vec, false>(input + i);
        auto active = invoke_op<scalar_vec>(predicate, x);
        if (::tsl::@{algorithm_helper_integral_mask}<scalar_vec>(active) != 0) {
            ::tsl::@{algorithm_helper_contiguous_write}<scalar_vec, false>(output + produced, x);
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
inline std::size_t select_binary_loop(
    Op& predicate,
    const T* left,
    const T* right,
    T* output,
    std::size_t count) {
    using scalar_vec = ::tsl::simd<T, ::tsl::scalar>;
    constexpr bool left_aligned =
        std::is_same<LeftAlignment, alignment::assume_aligned>::value;
    constexpr bool right_aligned =
        std::is_same<RightAlignment, alignment::assume_aligned>::value;

    const std::size_t lanes = detail::lane_count<Vec>();
    const std::size_t chunk_count = count / lanes;
    std::size_t produced = 0;
    std::size_t i = 0;
    for (std::size_t chunk = 0; chunk < chunk_count; ++chunk, i += lanes) {
        auto x = ::tsl::@{algorithm_helper_contiguous_read}<Vec, left_aligned>(left + i);
        auto y = ::tsl::@{algorithm_helper_contiguous_read}<Vec, right_aligned>(right + i);
        auto active = invoke_op<Vec>(predicate, x, y);
        ::tsl::@{algorithm_helper_compaction}<Vec, true>(active, output + produced, x);
        produced += ::tsl::@{algorithm_helper_mask_population_count}<Vec>(active);
    }
    for (; i < count; ++i) {
        auto x = ::tsl::@{algorithm_helper_contiguous_read}<scalar_vec, false>(left + i);
        auto y = ::tsl::@{algorithm_helper_contiguous_read}<scalar_vec, false>(right + i);
        auto active = invoke_op<scalar_vec>(predicate, x, y);
        if (::tsl::@{algorithm_helper_integral_mask}<scalar_vec>(active) != 0) {
            ::tsl::@{algorithm_helper_contiguous_write}<scalar_vec, false>(output + produced, x);
            produced += 1;
        }
    }
    return produced;
}

template <class Vec, class InputAlignment, class Op, class T, class IndexT>
inline std::size_t select_indices_unary_loop(
    Op& predicate,
    const T* input,
    IndexT* indices,
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
        append_indices_from_mask<Vec>(active, indices, produced, i, lanes);
    }
    for (; i < count; ++i) {
        auto x = ::tsl::@{algorithm_helper_contiguous_read}<scalar_vec, false>(input + i);
        auto active = invoke_op<scalar_vec>(predicate, x);
        if (::tsl::@{algorithm_helper_integral_mask}<scalar_vec>(active) != 0) {
            indices[produced] = static_cast<IndexT>(i);
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
    class T,
    class IndexT>
inline std::size_t select_indices_binary_loop(
    Op& predicate,
    const T* left,
    const T* right,
    IndexT* indices,
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
        append_indices_from_mask<Vec>(active, indices, produced, i, lanes);
    }
    for (; i < count; ++i) {
        auto x = ::tsl::@{algorithm_helper_contiguous_read}<scalar_vec, false>(left + i);
        auto y = ::tsl::@{algorithm_helper_contiguous_read}<scalar_vec, false>(right + i);
        auto active = invoke_op<scalar_vec>(predicate, x, y);
        if (::tsl::@{algorithm_helper_integral_mask}<scalar_vec>(active) != 0) {
            indices[produced] = static_cast<IndexT>(i);
            produced += 1;
        }
    }
    return produced;
}

template <class Vec, class MaskLayout, class InputAlignment, class Op, class T>
inline std::size_t select_masked_unary_loop(
    Op& predicate,
    const T* input,
    const mask_storage_for_vec_t<MaskLayout, Vec>* masks,
    T* output,
    std::size_t count) {
    using scalar_vec = ::tsl::simd<T, ::tsl::scalar>;
    constexpr bool input_aligned =
        std::is_same<InputAlignment, alignment::assume_aligned>::value;

    validate_mask_layout<MaskLayout, Vec>();

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
        ::tsl::@{algorithm_helper_compaction}<Vec, true>(active, output + produced, x);
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
            ::tsl::@{algorithm_helper_contiguous_write}<scalar_vec, false>(output + produced, x);
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
inline std::size_t select_masked_binary_loop(
    Op& predicate,
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

    validate_mask_layout<MaskLayout, Vec>();

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
        ::tsl::@{algorithm_helper_compaction}<Vec, true>(active, output + produced, x);
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
            ::tsl::@{algorithm_helper_contiguous_write}<scalar_vec, false>(output + produced, x);
            produced += 1;
        }
    }
    return produced;
}

template <
    class Vec,
    class MaskLayout,
    class InputAlignment,
    class Op,
    class T,
    class IndexT>
inline std::size_t select_masked_indices_unary_loop(
    Op& predicate,
    const T* input,
    const mask_storage_for_vec_t<MaskLayout, Vec>* masks,
    IndexT* indices,
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
        append_indices_from_mask<Vec>(active, indices, produced, i, lanes);
    }
    for (std::size_t lane = 0; i < count; ++i, ++lane) {
        if (!mask_storage_lane_active<MaskLayout, Vec>(
                masks, chunk_count, i, lane)) {
            continue;
        }
        auto x = ::tsl::@{algorithm_helper_contiguous_read}<scalar_vec, false>(input + i);
        auto active = invoke_op<scalar_vec>(predicate, x);
        if (::tsl::@{algorithm_helper_integral_mask}<scalar_vec>(active) != 0) {
            indices[produced] = static_cast<IndexT>(i);
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
    class T,
    class IndexT>
inline std::size_t select_masked_indices_binary_loop(
    Op& predicate,
    const T* left,
    const T* right,
    const mask_storage_for_vec_t<MaskLayout, Vec>* masks,
    IndexT* indices,
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
        append_indices_from_mask<Vec>(active, indices, produced, i, lanes);
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
            indices[produced] = static_cast<IndexT>(i);
            produced += 1;
        }
    }
    return produced;
}

template <
    class Vec,
    std::size_t Scale,
    class Op,
    class T,
    class InputIndexT,
    class OutputIndexT>
inline std::size_t select_selected_indices_unary_loop(
    Op& predicate,
    const T* input,
    const InputIndexT* input_indices,
    OutputIndexT* output_indices,
    std::size_t selected_count) {
    using scalar_vec = ::tsl::simd<T, ::tsl::scalar>;

    static_assert(
        is_selection_index<InputIndexT>::value,
        "selection-vector input indices must use an unsigned integral row-id type");
    static_assert(
        is_selection_index<OutputIndexT>::value,
        "selection-vector output indices must use an unsigned integral row-id type");
    validate_integral_mask_layout<Vec>();

    std::size_t produced = 0;
    if constexpr (std::is_same<Vec, scalar_vec>::value) {
        for (std::size_t i = 0; i < selected_count; ++i) {
            auto x = ::tsl::@{algorithm_helper_contiguous_read}<scalar_vec, false>(
                selected_row_pointer<T, InputIndexT, Scale>(
                    input, input_indices[i]));
            auto active = invoke_op<scalar_vec>(predicate, x);
            if (::tsl::@{algorithm_helper_integral_mask}<scalar_vec>(active) != 0) {
                output_indices[produced] =
                    static_cast<OutputIndexT>(input_indices[i]);
                produced += 1;
            }
        }
    } else {
        const std::size_t lanes = detail::lane_count<Vec>();
        const std::size_t chunk_count = selected_count / lanes;
        std::size_t i = 0;
        for (std::size_t chunk = 0; chunk < chunk_count; ++chunk, i += lanes) {
            (void)chunk;
            auto x = load_selected_vector<Vec, T, InputIndexT, Scale>(
                input, input_indices + i);
            auto active = invoke_op<Vec>(predicate, x);
            append_selected_indices_from_mask<Vec>(
                active, input_indices, output_indices, produced, i, lanes);
        }
        for (; i < selected_count; ++i) {
            auto x = ::tsl::@{algorithm_helper_contiguous_read}<scalar_vec, false>(
                selected_row_pointer<T, InputIndexT, Scale>(
                    input, input_indices[i]));
            auto active = invoke_op<scalar_vec>(predicate, x);
            if (::tsl::@{algorithm_helper_integral_mask}<scalar_vec>(active) != 0) {
                output_indices[produced] =
                    static_cast<OutputIndexT>(input_indices[i]);
                produced += 1;
            }
        }
    }
    return produced;
}

template <
    class Vec,
    std::size_t Scale,
    class Op,
    class T,
    class InputIndexT,
    class OutputIndexT>
inline std::size_t select_selected_indices_binary_loop(
    Op& predicate,
    const T* left,
    const T* right,
    const InputIndexT* input_indices,
    OutputIndexT* output_indices,
    std::size_t selected_count) {
    using scalar_vec = ::tsl::simd<T, ::tsl::scalar>;

    static_assert(
        is_selection_index<InputIndexT>::value,
        "selection-vector input indices must use an unsigned integral row-id type");
    static_assert(
        is_selection_index<OutputIndexT>::value,
        "selection-vector output indices must use an unsigned integral row-id type");
    validate_integral_mask_layout<Vec>();

    std::size_t produced = 0;
    if constexpr (std::is_same<Vec, scalar_vec>::value) {
        for (std::size_t i = 0; i < selected_count; ++i) {
            auto x = ::tsl::@{algorithm_helper_contiguous_read}<scalar_vec, false>(
                selected_row_pointer<T, InputIndexT, Scale>(
                    left, input_indices[i]));
            auto y = ::tsl::@{algorithm_helper_contiguous_read}<scalar_vec, false>(
                selected_row_pointer<T, InputIndexT, Scale>(
                    right, input_indices[i]));
            auto active = invoke_op<scalar_vec>(predicate, x, y);
            if (::tsl::@{algorithm_helper_integral_mask}<scalar_vec>(active) != 0) {
                output_indices[produced] =
                    static_cast<OutputIndexT>(input_indices[i]);
                produced += 1;
            }
        }
    } else {
        const std::size_t lanes = detail::lane_count<Vec>();
        const std::size_t chunk_count = selected_count / lanes;
        std::size_t i = 0;
        for (std::size_t chunk = 0; chunk < chunk_count; ++chunk, i += lanes) {
            (void)chunk;
            auto x = load_selected_vector<Vec, T, InputIndexT, Scale>(
                left, input_indices + i);
            auto y = load_selected_vector<Vec, T, InputIndexT, Scale>(
                right, input_indices + i);
            auto active = invoke_op<Vec>(predicate, x, y);
            append_selected_indices_from_mask<Vec>(
                active, input_indices, output_indices, produced, i, lanes);
        }
        for (; i < selected_count; ++i) {
            auto x = ::tsl::@{algorithm_helper_contiguous_read}<scalar_vec, false>(
                selected_row_pointer<T, InputIndexT, Scale>(
                    left, input_indices[i]));
            auto y = ::tsl::@{algorithm_helper_contiguous_read}<scalar_vec, false>(
                selected_row_pointer<T, InputIndexT, Scale>(
                    right, input_indices[i]));
            auto active = invoke_op<scalar_vec>(predicate, x, y);
            if (::tsl::@{algorithm_helper_integral_mask}<scalar_vec>(active) != 0) {
                output_indices[produced] =
                    static_cast<OutputIndexT>(input_indices[i]);
                produced += 1;
            }
        }
    }
    return produced;
}

template <class Vec, class LeftAlignment, class Op, class T, class IndexT>
inline std::size_t select_indices_binary_dispatch_right(
    Op& op,
    const T* left,
    const T* right,
    IndexT* indices,
    std::size_t count) {
    if (is_aligned_for<Vec>(right)) {
        return select_indices_binary_loop<
            Vec,
            LeftAlignment,
            alignment::assume_aligned>(op, left, right, indices, count);
    }
    return select_indices_binary_loop<
        Vec,
        LeftAlignment,
        alignment::unaligned>(op, left, right, indices, count);
}

template <class Vec, class Op, class T, class IndexT>
inline std::size_t select_indices_binary_dispatch_detect(
    Op& op,
    const T* left,
    const T* right,
    IndexT* indices,
    std::size_t count) {
    if (is_aligned_for<Vec>(left)) {
        return select_indices_binary_dispatch_right<
            Vec,
            alignment::assume_aligned>(
            op, left, right, indices, count);
    }
    return select_indices_binary_dispatch_right<
        Vec,
        alignment::unaligned>(
        op, left, right, indices, count);
}

template <class Vec, class LeftAlignment, class Op, class T>
inline std::size_t select_binary_dispatch_right(
    Op& op,
    const T* left,
    const T* right,
    T* output,
    std::size_t count) {
    if (is_aligned_for<Vec>(right)) {
        return select_binary_loop<
            Vec,
            LeftAlignment,
            alignment::assume_aligned>(op, left, right, output, count);
    }
    return select_binary_loop<
        Vec,
        LeftAlignment,
        alignment::unaligned>(op, left, right, output, count);
}

template <class Vec, class Op, class T>
inline std::size_t select_binary_dispatch_detect(
    Op& op,
    const T* left,
    const T* right,
    T* output,
    std::size_t count) {
    if (is_aligned_for<Vec>(left)) {
        return select_binary_dispatch_right<Vec, alignment::assume_aligned>(
            op, left, right, output, count);
    }
    return select_binary_dispatch_right<Vec, alignment::unaligned>(
        op, left, right, output, count);
}

template <
    class Vec,
    class MaskLayout,
    class LeftAlignment,
    class Op,
    class T,
    class IndexT>
inline std::size_t select_masked_indices_binary_dispatch_right(
    Op& op,
    const T* left,
    const T* right,
    const mask_storage_for_vec_t<MaskLayout, Vec>* masks,
    IndexT* indices,
    std::size_t count) {
    if (is_aligned_for<Vec>(right)) {
        return select_masked_indices_binary_loop<
            Vec,
            MaskLayout,
            LeftAlignment,
            alignment::assume_aligned>(
            op, left, right, masks, indices, count);
    }
    return select_masked_indices_binary_loop<
        Vec,
        MaskLayout,
        LeftAlignment,
        alignment::unaligned>(
        op, left, right, masks, indices, count);
}

template <class Vec, class MaskLayout, class Op, class T, class IndexT>
inline std::size_t select_masked_indices_binary_dispatch_detect(
    Op& op,
    const T* left,
    const T* right,
    const mask_storage_for_vec_t<MaskLayout, Vec>* masks,
    IndexT* indices,
    std::size_t count) {
    if (is_aligned_for<Vec>(left)) {
        return select_masked_indices_binary_dispatch_right<
            Vec,
            MaskLayout,
            alignment::assume_aligned>(
            op, left, right, masks, indices, count);
    }
    return select_masked_indices_binary_dispatch_right<
        Vec,
        MaskLayout,
        alignment::unaligned>(
        op, left, right, masks, indices, count);
}

template <
    class Vec,
    class MaskLayout,
    class LeftAlignment,
    class Op,
    class T>
inline std::size_t select_masked_binary_dispatch_right(
    Op& op,
    const T* left,
    const T* right,
    const mask_storage_for_vec_t<MaskLayout, Vec>* masks,
    T* output,
    std::size_t count) {
    if (is_aligned_for<Vec>(right)) {
        return select_masked_binary_loop<
            Vec,
            MaskLayout,
            LeftAlignment,
            alignment::assume_aligned>(
            op, left, right, masks, output, count);
    }
    return select_masked_binary_loop<
        Vec,
        MaskLayout,
        LeftAlignment,
        alignment::unaligned>(
        op, left, right, masks, output, count);
}

template <class Vec, class MaskLayout, class Op, class T>
inline std::size_t select_masked_binary_dispatch_detect(
    Op& op,
    const T* left,
    const T* right,
    const mask_storage_for_vec_t<MaskLayout, Vec>* masks,
    T* output,
    std::size_t count) {
    if (is_aligned_for<Vec>(left)) {
        return select_masked_binary_dispatch_right<
            Vec,
            MaskLayout,
            alignment::assume_aligned>(
            op, left, right, masks, output, count);
    }
    return select_masked_binary_dispatch_right<
        Vec,
        MaskLayout,
        alignment::unaligned>(
        op, left, right, masks, output, count);
}

}  // namespace tsl::algo::detail
