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
        auto x = ::tsl::load<Vec, input_aligned>(input + i);
        auto active = invoke_op<Vec>(predicate, x);
        produced += ::tsl::mask_population_count<Vec>(active);
    }
    for (; i < count; ++i) {
        auto x = ::tsl::load<scalar_vec, false>(input + i);
        auto active = invoke_op<scalar_vec>(predicate, x);
        if (::tsl::to_integral<scalar_vec>(active) != 0) {
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
        auto x = ::tsl::load<Vec, left_aligned>(left + i);
        auto y = ::tsl::load<Vec, right_aligned>(right + i);
        auto active = invoke_op<Vec>(predicate, x, y);
        produced += ::tsl::mask_population_count<Vec>(active);
    }
    for (; i < count; ++i) {
        auto x = ::tsl::load<scalar_vec, false>(left + i);
        auto y = ::tsl::load<scalar_vec, false>(right + i);
        auto active = invoke_op<scalar_vec>(predicate, x, y);
        if (::tsl::to_integral<scalar_vec>(active) != 0) {
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
        auto x = ::tsl::load<Vec, input_aligned>(input + i);
        auto predicate_active = invoke_op<Vec>(predicate, x);
        auto active =
            ::tsl::mask_binary_and<Vec>(input_active, predicate_active);
        produced += ::tsl::mask_population_count<Vec>(active);
    }
    for (std::size_t lane = 0; i < count; ++i, ++lane) {
        if (!mask_storage_lane_active<MaskLayout, Vec>(
                masks, chunk_count, i, lane)) {
            continue;
        }
        auto x = ::tsl::load<scalar_vec, false>(input + i);
        auto active = invoke_op<scalar_vec>(predicate, x);
        if (::tsl::to_integral<scalar_vec>(active) != 0) {
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
        auto x = ::tsl::load<Vec, left_aligned>(left + i);
        auto y = ::tsl::load<Vec, right_aligned>(right + i);
        auto predicate_active = invoke_op<Vec>(predicate, x, y);
        auto active =
            ::tsl::mask_binary_and<Vec>(input_active, predicate_active);
        produced += ::tsl::mask_population_count<Vec>(active);
    }
    for (std::size_t lane = 0; i < count; ++i, ++lane) {
        if (!mask_storage_lane_active<MaskLayout, Vec>(
                masks, chunk_count, i, lane)) {
            continue;
        }
        auto x = ::tsl::load<scalar_vec, false>(left + i);
        auto y = ::tsl::load<scalar_vec, false>(right + i);
        auto active = invoke_op<scalar_vec>(predicate, x, y);
        if (::tsl::to_integral<scalar_vec>(active) != 0) {
            produced += 1;
        }
    }
    return produced;
}

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
        auto x = ::tsl::load<Vec, input_aligned>(input + i);
        auto active = invoke_op<Vec>(predicate, x);
        ::tsl::compress_store<Vec, true>(active, output + produced, x);
        produced += ::tsl::mask_population_count<Vec>(active);
    }
    for (; i < count; ++i) {
        auto x = ::tsl::load<scalar_vec, false>(input + i);
        auto active = invoke_op<scalar_vec>(predicate, x);
        if (::tsl::to_integral<scalar_vec>(active) != 0) {
            ::tsl::store<scalar_vec, false>(output + produced, x);
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
        auto x = ::tsl::load<Vec, left_aligned>(left + i);
        auto y = ::tsl::load<Vec, right_aligned>(right + i);
        auto active = invoke_op<Vec>(predicate, x, y);
        ::tsl::compress_store<Vec, true>(active, output + produced, x);
        produced += ::tsl::mask_population_count<Vec>(active);
    }
    for (; i < count; ++i) {
        auto x = ::tsl::load<scalar_vec, false>(left + i);
        auto y = ::tsl::load<scalar_vec, false>(right + i);
        auto active = invoke_op<scalar_vec>(predicate, x, y);
        if (::tsl::to_integral<scalar_vec>(active) != 0) {
            ::tsl::store<scalar_vec, false>(output + produced, x);
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
        auto x = ::tsl::load<Vec, input_aligned>(input + i);
        auto active = invoke_op<Vec>(predicate, x);
        append_indices_from_mask<Vec>(active, indices, produced, i, lanes);
    }
    for (; i < count; ++i) {
        auto x = ::tsl::load<scalar_vec, false>(input + i);
        auto active = invoke_op<scalar_vec>(predicate, x);
        if (::tsl::to_integral<scalar_vec>(active) != 0) {
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
        auto x = ::tsl::load<Vec, left_aligned>(left + i);
        auto y = ::tsl::load<Vec, right_aligned>(right + i);
        auto active = invoke_op<Vec>(predicate, x, y);
        append_indices_from_mask<Vec>(active, indices, produced, i, lanes);
    }
    for (; i < count; ++i) {
        auto x = ::tsl::load<scalar_vec, false>(left + i);
        auto y = ::tsl::load<scalar_vec, false>(right + i);
        auto active = invoke_op<scalar_vec>(predicate, x, y);
        if (::tsl::to_integral<scalar_vec>(active) != 0) {
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
        auto x = ::tsl::load<Vec, input_aligned>(input + i);
        auto predicate_active = invoke_op<Vec>(predicate, x);
        auto active =
            ::tsl::mask_binary_and<Vec>(input_active, predicate_active);
        ::tsl::compress_store<Vec, true>(active, output + produced, x);
        produced += ::tsl::mask_population_count<Vec>(active);
    }
    for (std::size_t lane = 0; i < count; ++i, ++lane) {
        if (!mask_storage_lane_active<MaskLayout, Vec>(
                masks, chunk_count, i, lane)) {
            continue;
        }
        auto x = ::tsl::load<scalar_vec, false>(input + i);
        auto active = invoke_op<scalar_vec>(predicate, x);
        if (::tsl::to_integral<scalar_vec>(active) != 0) {
            ::tsl::store<scalar_vec, false>(output + produced, x);
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
        auto x = ::tsl::load<Vec, left_aligned>(left + i);
        auto y = ::tsl::load<Vec, right_aligned>(right + i);
        auto predicate_active = invoke_op<Vec>(predicate, x, y);
        auto active =
            ::tsl::mask_binary_and<Vec>(input_active, predicate_active);
        ::tsl::compress_store<Vec, true>(active, output + produced, x);
        produced += ::tsl::mask_population_count<Vec>(active);
    }
    for (std::size_t lane = 0; i < count; ++i, ++lane) {
        if (!mask_storage_lane_active<MaskLayout, Vec>(
                masks, chunk_count, i, lane)) {
            continue;
        }
        auto x = ::tsl::load<scalar_vec, false>(left + i);
        auto y = ::tsl::load<scalar_vec, false>(right + i);
        auto active = invoke_op<scalar_vec>(predicate, x, y);
        if (::tsl::to_integral<scalar_vec>(active) != 0) {
            ::tsl::store<scalar_vec, false>(output + produced, x);
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
        auto x = ::tsl::load<Vec, input_aligned>(input + i);
        auto predicate_active = invoke_op<Vec>(predicate, x);
        auto active =
            ::tsl::mask_binary_and<Vec>(input_active, predicate_active);
        append_indices_from_mask<Vec>(active, indices, produced, i, lanes);
    }
    for (std::size_t lane = 0; i < count; ++i, ++lane) {
        if (!mask_storage_lane_active<MaskLayout, Vec>(
                masks, chunk_count, i, lane)) {
            continue;
        }
        auto x = ::tsl::load<scalar_vec, false>(input + i);
        auto active = invoke_op<scalar_vec>(predicate, x);
        if (::tsl::to_integral<scalar_vec>(active) != 0) {
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
        auto x = ::tsl::load<Vec, left_aligned>(left + i);
        auto y = ::tsl::load<Vec, right_aligned>(right + i);
        auto predicate_active = invoke_op<Vec>(predicate, x, y);
        auto active =
            ::tsl::mask_binary_and<Vec>(input_active, predicate_active);
        append_indices_from_mask<Vec>(active, indices, produced, i, lanes);
    }
    for (std::size_t lane = 0; i < count; ++i, ++lane) {
        if (!mask_storage_lane_active<MaskLayout, Vec>(
                masks, chunk_count, i, lane)) {
            continue;
        }
        auto x = ::tsl::load<scalar_vec, false>(left + i);
        auto y = ::tsl::load<scalar_vec, false>(right + i);
        auto active = invoke_op<scalar_vec>(predicate, x, y);
        if (::tsl::to_integral<scalar_vec>(active) != 0) {
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
            auto x = ::tsl::load<scalar_vec, false>(
                selected_row_pointer<T, InputIndexT, Scale>(
                    input, input_indices[i]));
            auto active = invoke_op<scalar_vec>(predicate, x);
            if (::tsl::to_integral<scalar_vec>(active) != 0) {
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
            auto x = ::tsl::load<scalar_vec, false>(
                selected_row_pointer<T, InputIndexT, Scale>(
                    input, input_indices[i]));
            auto active = invoke_op<scalar_vec>(predicate, x);
            if (::tsl::to_integral<scalar_vec>(active) != 0) {
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
            auto x = ::tsl::load<scalar_vec, false>(
                selected_row_pointer<T, InputIndexT, Scale>(
                    left, input_indices[i]));
            auto y = ::tsl::load<scalar_vec, false>(
                selected_row_pointer<T, InputIndexT, Scale>(
                    right, input_indices[i]));
            auto active = invoke_op<scalar_vec>(predicate, x, y);
            if (::tsl::to_integral<scalar_vec>(active) != 0) {
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
            auto x = ::tsl::load<scalar_vec, false>(
                selected_row_pointer<T, InputIndexT, Scale>(
                    left, input_indices[i]));
            auto y = ::tsl::load<scalar_vec, false>(
                selected_row_pointer<T, InputIndexT, Scale>(
                    right, input_indices[i]));
            auto active = invoke_op<scalar_vec>(predicate, x, y);
            if (::tsl::to_integral<scalar_vec>(active) != 0) {
                output_indices[produced] =
                    static_cast<OutputIndexT>(input_indices[i]);
                produced += 1;
            }
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
            auto x = ::tsl::load<scalar_vec, false>(
                selected_row_pointer<T, IndexT, Scale>(input, indices[i]));
            auto active = invoke_op<scalar_vec>(predicate, x);
            if (::tsl::to_integral<scalar_vec>(active) != 0) {
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
            produced += ::tsl::mask_population_count<Vec>(active);
        }
        for (; i < selected_count; ++i) {
            auto x = ::tsl::load<scalar_vec, false>(
                selected_row_pointer<T, IndexT, Scale>(input, indices[i]));
            auto active = invoke_op<scalar_vec>(predicate, x);
            if (::tsl::to_integral<scalar_vec>(active) != 0) {
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
            auto x = ::tsl::load<scalar_vec, false>(
                selected_row_pointer<T, IndexT, Scale>(left, indices[i]));
            auto y = ::tsl::load<scalar_vec, false>(
                selected_row_pointer<T, IndexT, Scale>(right, indices[i]));
            auto active = invoke_op<scalar_vec>(predicate, x, y);
            if (::tsl::to_integral<scalar_vec>(active) != 0) {
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
            produced += ::tsl::mask_population_count<Vec>(active);
        }
        for (; i < selected_count; ++i) {
            auto x = ::tsl::load<scalar_vec, false>(
                selected_row_pointer<T, IndexT, Scale>(left, indices[i]));
            auto y = ::tsl::load<scalar_vec, false>(
                selected_row_pointer<T, IndexT, Scale>(right, indices[i]));
            auto active = invoke_op<scalar_vec>(predicate, x, y);
            if (::tsl::to_integral<scalar_vec>(active) != 0) {
                produced += 1;
            }
        }
    }
    return produced;
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

template <class Vec, std::size_t Scale, class Op, class T, class IndexT>
inline void consume_selected_unary_loop(
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
}

template <class Vec, std::size_t Scale, class Op, class T, class IndexT>
inline void consume_selected_binary_loop(
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

template <class Vec, class InputAlignment, class Op, class T>
inline void consume_unary_loop(
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
}

template <
    class Vec,
    class LeftAlignment,
    class RightAlignment,
    class Op,
    class T>
inline void consume_binary_loop(
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
}

template <
    class Vec,
    class MaskLayout,
    class InputAlignment,
    class Op,
    class T>
inline void consume_masked_unary_loop(
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
}

template <
    class Vec,
    class MaskLayout,
    class LeftAlignment,
    class RightAlignment,
    class Op,
    class T>
inline void consume_masked_binary_loop(
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

template <class Vec, class LeftAlignment, class Op, class T>
inline void consume_binary_dispatch_right(
    Op& op,
    const T* left,
    const T* right,
    std::size_t count) {
    if (is_aligned_for<Vec>(right)) {
        consume_binary_loop<
            Vec,
            LeftAlignment,
            alignment::assume_aligned>(op, left, right, count);
    } else {
        consume_binary_loop<
            Vec,
            LeftAlignment,
            alignment::unaligned>(op, left, right, count);
    }
}

template <class Vec, class Op, class T>
inline void consume_binary_dispatch_detect(
    Op& op,
    const T* left,
    const T* right,
    std::size_t count) {
    if (is_aligned_for<Vec>(left)) {
        consume_binary_dispatch_right<Vec, alignment::assume_aligned>(
            op, left, right, count);
    } else {
        consume_binary_dispatch_right<Vec, alignment::unaligned>(
            op, left, right, count);
    }
}

template <class Vec, class MaskLayout, class LeftAlignment, class Op, class T>
inline void consume_masked_binary_dispatch_right(
    Op& op,
    const T* left,
    const T* right,
    const mask_storage_for_vec_t<MaskLayout, Vec>* masks,
    std::size_t count) {
    if (is_aligned_for<Vec>(right)) {
        consume_masked_binary_loop<
            Vec,
            MaskLayout,
            LeftAlignment,
            alignment::assume_aligned>(op, left, right, masks, count);
    } else {
        consume_masked_binary_loop<
            Vec,
            MaskLayout,
            LeftAlignment,
            alignment::unaligned>(op, left, right, masks, count);
    }
}

template <class Vec, class MaskLayout, class Op, class T>
inline void consume_masked_binary_dispatch_detect(
    Op& op,
    const T* left,
    const T* right,
    const mask_storage_for_vec_t<MaskLayout, Vec>* masks,
    std::size_t count) {
    if (is_aligned_for<Vec>(left)) {
        consume_masked_binary_dispatch_right<
            Vec,
            MaskLayout,
            alignment::assume_aligned>(
            op, left, right, masks, count);
    } else {
        consume_masked_binary_dispatch_right<
            Vec,
            MaskLayout,
            alignment::unaligned>(
            op, left, right, masks, count);
    }
}


}  // namespace tsl::algo::detail
