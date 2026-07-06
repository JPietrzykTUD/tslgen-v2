#pragma once

#include "tsl_algorithm_detail_loops.hpp"

namespace tsl::algo {

template <class Parallelism, class T>
using vector_type = typename detail::vector_for_parallelism<Parallelism, T>::type;

template <class Parallelism, class T>
using integral_mask_type = typename detail::integral_mask_for<Parallelism, T>::type;

template <class Parallelism, class T>
using native_mask_type = typename detail::native_mask_for<Parallelism, T>::type;

template <class MaskLayout, class Parallelism, class T>
using mask_storage_type = typename detail::mask_for<MaskLayout, Parallelism, T>::type;

template <class Parallelism, class T>
using byte_mask_type = mask_storage_type<mask_layout::bytes, Parallelism, T>;

template <class Parallelism, class T>
using bit_mask_type = mask_storage_type<mask_layout::bits, Parallelism, T>;

template <std::size_t ParallelN, class T>
using fixed_integral_mask_type =
    integral_mask_type<parallelism::fixed<ParallelN>, T>;

template <std::size_t ParallelN, class T>
using fixed_native_mask_type =
    native_mask_type<parallelism::fixed<ParallelN>, T>;

template <class MaskLayout, std::size_t ParallelN, class T>
using fixed_mask_storage_type =
    mask_storage_type<MaskLayout, parallelism::fixed<ParallelN>, T>;

template <std::size_t ParallelN, class T>
using fixed_byte_mask_type =
    fixed_mask_storage_type<mask_layout::bytes, ParallelN, T>;

template <std::size_t ParallelN, class T>
using fixed_bit_mask_type =
    fixed_mask_storage_type<mask_layout::bits, ParallelN, T>;

template <class Parallelism, class T>
inline std::size_t integral_mask_chunk_count(std::size_t count) {
    using vec = vector_type<Parallelism, T>;
    detail::validate_integral_mask_layout<vec>();
    const std::size_t lanes = detail::lane_count<vec>();
    return (count + lanes - 1) / lanes;
}

template <std::size_t ParallelN, class T>
inline std::size_t integral_mask_chunk_count(std::size_t count) {
    return integral_mask_chunk_count<parallelism::fixed<ParallelN>, T>(count);
}

template <class Parallelism, class T>
inline std::size_t native_mask_chunk_count(std::size_t count) {
    using vec = vector_type<Parallelism, T>;
    detail::validate_native_mask_layout<vec>();
    const std::size_t lanes = detail::lane_count<vec>();
    return (count + lanes - 1) / lanes;
}

template <std::size_t ParallelN, class T>
inline std::size_t native_mask_chunk_count(std::size_t count) {
    return native_mask_chunk_count<parallelism::fixed<ParallelN>, T>(count);
}

template <class MaskLayout, class Parallelism, class T>
inline std::size_t mask_chunk_count(std::size_t count) {
    using vec = vector_type<Parallelism, T>;
    detail::validate_mask_layout<MaskLayout, vec>();
    if constexpr (std::is_same<MaskLayout, mask_layout::bytes>::value) {
        return count;
    } else if constexpr (std::is_same<MaskLayout, mask_layout::bits>::value) {
        return detail::packed_bit_mask_count(count);
    }
    const std::size_t lanes = detail::lane_count<vec>();
    return (count + lanes - 1) / lanes;
}

template <class MaskLayout, std::size_t ParallelN, class T>
inline std::size_t mask_chunk_count(std::size_t count) {
    return mask_chunk_count<MaskLayout, parallelism::fixed<ParallelN>, T>(count);
}

template <class Parallelism, class T>
inline std::size_t byte_mask_count(std::size_t count) {
    return mask_chunk_count<mask_layout::bytes, Parallelism, T>(count);
}

template <std::size_t ParallelN, class T>
inline std::size_t byte_mask_count(std::size_t count) {
    return byte_mask_count<parallelism::fixed<ParallelN>, T>(count);
}

template <class Parallelism, class T>
inline std::size_t bit_mask_count(std::size_t count) {
    return mask_chunk_count<mask_layout::bits, Parallelism, T>(count);
}

template <std::size_t ParallelN, class T>
inline std::size_t bit_mask_count(std::size_t count) {
    return bit_mask_count<parallelism::fixed<ParallelN>, T>(count);
}

template <
    class Parallelism = parallelism::native,
    class Op,
    class T>
inline void for_each_chunk(Op&& op, T* data, std::size_t count) {
    using value_type = typename std::remove_cv<T>::type;
    using vec = typename detail::vector_for_parallelism<Parallelism, value_type>::type;

    detail::validate_vector_for_parallelism<Parallelism, vec, value_type>();
    detail::for_each_chunk_loop<vec>(op, data, count);
}

template <
    std::size_t ParallelN,
    class Op,
    class T>
inline void for_each_chunk(Op&& op, T* data, std::size_t count) {
    for_each_chunk<parallelism::fixed<ParallelN>>(
        std::forward<Op>(op), data, count);
}

template <
    class Parallelism = parallelism::native,
    class Op,
    class Range>
inline void for_each_chunk(Op&& op, Range& data) {
    for_each_chunk<Parallelism>(
        std::forward<Op>(op),
        detail::range_data(data),
        detail::range_size(data));
}

template <
    std::size_t ParallelN,
    class Op,
    class Range>
inline void for_each_chunk(Op&& op, Range& data) {
    for_each_chunk<parallelism::fixed<ParallelN>>(std::forward<Op>(op), data);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class Op,
    class T>
inline void transform_unary(Op&& op, const T* input, T* output, std::size_t count) {
    using vec = typename detail::vector_for_parallelism<Parallelism, T>::type;

    static_assert(
        detail::is_supported_transform_alignment_policy<Alignment>::value,
        "Alignment must be tsl::algo::alignment::detect, unaligned, "
        "assume_aligned, assume_inputs_aligned, assume_output_aligned, "
        "or peel_to_aligned");
    detail::validate_vector_for_parallelism<Parallelism, vec, T>();

    if constexpr (std::is_same<Alignment, alignment::detect>::value) {
        const bool input_aligned = detail::is_aligned_for<vec>(input);
        const bool output_aligned = detail::is_aligned_for<vec>(output);
        if (input_aligned && output_aligned) {
            detail::transform_unary_loop<
                vec,
                alignment::assume_aligned,
                alignment::assume_aligned>(op, input, output, count);
            return;
        }
        if (input_aligned) {
            detail::transform_unary_loop<
                vec,
                alignment::assume_aligned,
                alignment::unaligned>(op, input, output, count);
            return;
        }
        if (output_aligned) {
            detail::transform_unary_loop<
                vec,
                alignment::unaligned,
                alignment::assume_aligned>(op, input, output, count);
            return;
        }
        detail::transform_unary_loop<
            vec,
            alignment::unaligned,
            alignment::unaligned>(op, input, output, count);
    } else if constexpr (std::is_same<Alignment, alignment::assume_aligned>::value) {
        detail::transform_unary_loop<
            vec,
            alignment::assume_aligned,
            alignment::assume_aligned>(op, input, output, count);
    } else if constexpr (std::is_same<Alignment, alignment::assume_inputs_aligned>::value) {
        detail::transform_unary_loop<
            vec,
            alignment::assume_aligned,
            alignment::unaligned>(op, input, output, count);
    } else if constexpr (std::is_same<Alignment, alignment::assume_output_aligned>::value) {
        detail::transform_unary_loop<
            vec,
            alignment::unaligned,
            alignment::assume_aligned>(op, input, output, count);
    } else if constexpr (std::is_same<Alignment, alignment::peel_to_aligned>::value) {
        detail::transform_unary_loop_peel_to_aligned<vec>(
            op, input, output, count);
    } else {
        detail::transform_unary_loop<
            vec,
            alignment::unaligned,
            alignment::unaligned>(op, input, output, count);
    }
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class Op,
    class InputRange,
    class OutputRange>
inline void transform_unary(Op&& op, const InputRange& input, OutputRange& output) {
    transform_unary<Parallelism, Alignment>(
        std::forward<Op>(op),
        detail::range_data(input),
        detail::range_data(output),
        detail::range_size(input));
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class Op,
    class T>
inline void transform_unary(Op&& op, const T* input, T* output, std::size_t count) {
    transform_unary<parallelism::fixed<ParallelN>, Alignment>(
        std::forward<Op>(op), input, output, count);
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class Op,
    class InputRange,
    class OutputRange>
inline void transform_unary(Op&& op, const InputRange& input, OutputRange& output) {
    transform_unary<parallelism::fixed<ParallelN>, Alignment>(
        std::forward<Op>(op), input, output);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class Op,
    class T>
inline void transform_binary(
    Op&& op,
    const T* left,
    const T* right,
    T* output,
    std::size_t count) {
    using vec = typename detail::vector_for_parallelism<Parallelism, T>::type;

    static_assert(
        detail::is_supported_transform_alignment_policy<Alignment>::value,
        "Alignment must be tsl::algo::alignment::detect, unaligned, "
        "assume_aligned, assume_inputs_aligned, assume_output_aligned, "
        "or peel_to_aligned");
    detail::validate_vector_for_parallelism<Parallelism, vec, T>();

    if constexpr (std::is_same<Alignment, alignment::detect>::value) {
        detail::transform_binary_dispatch_detect<vec>(
            op, left, right, output, count);
    } else if constexpr (std::is_same<Alignment, alignment::assume_aligned>::value) {
        detail::transform_binary_loop<
            vec,
            alignment::assume_aligned,
            alignment::assume_aligned,
            alignment::assume_aligned>(op, left, right, output, count);
    } else if constexpr (std::is_same<Alignment, alignment::assume_inputs_aligned>::value) {
        detail::transform_binary_loop<
            vec,
            alignment::assume_aligned,
            alignment::assume_aligned,
            alignment::unaligned>(op, left, right, output, count);
    } else if constexpr (std::is_same<Alignment, alignment::assume_output_aligned>::value) {
        detail::transform_binary_loop<
            vec,
            alignment::unaligned,
            alignment::unaligned,
            alignment::assume_aligned>(op, left, right, output, count);
    } else if constexpr (std::is_same<Alignment, alignment::peel_to_aligned>::value) {
        detail::transform_binary_loop_peel_to_aligned<vec>(
            op, left, right, output, count);
    } else {
        detail::transform_binary_loop<
            vec,
            alignment::unaligned,
            alignment::unaligned,
            alignment::unaligned>(op, left, right, output, count);
    }
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class Op,
    class LeftRange,
    class RightRange,
    class OutputRange>
inline void transform_binary(
    Op&& op,
    const LeftRange& left,
    const RightRange& right,
    OutputRange& output) {
    transform_binary<Parallelism, Alignment>(
        std::forward<Op>(op),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_data(output),
        detail::range_size(left));
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class Op,
    class T>
inline void transform_binary(
    Op&& op,
    const T* left,
    const T* right,
    T* output,
    std::size_t count) {
    transform_binary<parallelism::fixed<ParallelN>, Alignment>(
        std::forward<Op>(op), left, right, output, count);
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class Op,
    class LeftRange,
    class RightRange,
    class OutputRange>
inline void transform_binary(
    Op&& op,
    const LeftRange& left,
    const RightRange& right,
    OutputRange& output) {
    transform_binary<parallelism::fixed<ParallelN>, Alignment>(
        std::forward<Op>(op), left, right, output);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class T>
inline std::size_t predicate_unary(
    Op&& op,
    const T* input,
    typename detail::mask_for<MaskLayout, Parallelism, T>::type* masks,
    std::size_t count) {
    using vec = typename detail::vector_for_parallelism<Parallelism, T>::type;

    static_assert(
        detail::is_supported_alignment_policy<Alignment>::value,
        "Alignment must be tsl::algo::alignment::detect, unaligned, or assume_aligned");
    static_assert(
        detail::is_supported_mask_layout<MaskLayout>::value,
        "MaskLayout must be tsl::algo::mask_layout::integral, native, bytes, "
        "or bits");
    detail::validate_vector_for_parallelism<Parallelism, vec, T>();
    detail::validate_mask_layout<MaskLayout, vec>();

    if constexpr (std::is_same<Alignment, alignment::detect>::value) {
        if (detail::is_aligned_for<vec>(input)) {
            return detail::predicate_unary_loop<
                vec,
                MaskLayout,
                alignment::assume_aligned>(
                op, input, masks, count);
        }
        return detail::predicate_unary_loop<
            vec,
            MaskLayout,
            alignment::unaligned>(
            op, input, masks, count);
    } else if constexpr (std::is_same<Alignment, alignment::assume_aligned>::value) {
        return detail::predicate_unary_loop<
            vec,
            MaskLayout,
            alignment::assume_aligned>(
            op, input, masks, count);
    } else {
        return detail::predicate_unary_loop<
            vec,
            MaskLayout,
            alignment::unaligned>(
            op, input, masks, count);
    }
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class T>
inline std::size_t predicate_unary(
    Op&& op,
    const T* input,
    fixed_mask_storage_type<MaskLayout, ParallelN, T>* masks,
    std::size_t count) {
    return predicate_unary<parallelism::fixed<ParallelN>, Alignment, MaskLayout>(
        std::forward<Op>(op), input, masks, count);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class InputRange,
    class MaskRange>
inline std::size_t predicate_unary(
    Op&& op,
    const InputRange& input,
    MaskRange& masks) {
    return predicate_unary<Parallelism, Alignment, MaskLayout>(
        std::forward<Op>(op),
        detail::range_data(input),
        detail::range_data(masks),
        detail::range_size(input));
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class InputRange,
    class MaskRange>
inline std::size_t predicate_unary(
    Op&& op,
    const InputRange& input,
    MaskRange& masks) {
    return predicate_unary<
        parallelism::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(op), input, masks);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class T>
inline std::size_t predicate_binary(
    Op&& op,
    const T* left,
    const T* right,
    typename detail::mask_for<MaskLayout, Parallelism, T>::type* masks,
    std::size_t count) {
    using vec = typename detail::vector_for_parallelism<Parallelism, T>::type;

    static_assert(
        detail::is_supported_alignment_policy<Alignment>::value,
        "Alignment must be tsl::algo::alignment::detect, unaligned, or assume_aligned");
    static_assert(
        detail::is_supported_mask_layout<MaskLayout>::value,
        "MaskLayout must be tsl::algo::mask_layout::integral, native, bytes, "
        "or bits");
    detail::validate_vector_for_parallelism<Parallelism, vec, T>();
    detail::validate_mask_layout<MaskLayout, vec>();

    if constexpr (std::is_same<Alignment, alignment::detect>::value) {
        return detail::predicate_binary_dispatch_detect<vec, MaskLayout>(
            op, left, right, masks, count);
    } else if constexpr (std::is_same<Alignment, alignment::assume_aligned>::value) {
        return detail::predicate_binary_loop<
            vec,
            MaskLayout,
            alignment::assume_aligned,
            alignment::assume_aligned>(op, left, right, masks, count);
    } else {
        return detail::predicate_binary_loop<
            vec,
            MaskLayout,
            alignment::unaligned,
            alignment::unaligned>(op, left, right, masks, count);
    }
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class T>
inline std::size_t predicate_binary(
    Op&& op,
    const T* left,
    const T* right,
    fixed_mask_storage_type<MaskLayout, ParallelN, T>* masks,
    std::size_t count) {
    return predicate_binary<parallelism::fixed<ParallelN>, Alignment, MaskLayout>(
        std::forward<Op>(op), left, right, masks, count);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class LeftRange,
    class RightRange,
    class MaskRange>
inline std::size_t predicate_binary(
    Op&& op,
    const LeftRange& left,
    const RightRange& right,
    MaskRange& masks) {
    return predicate_binary<Parallelism, Alignment, MaskLayout>(
        std::forward<Op>(op),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_data(masks),
        detail::range_size(left));
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class LeftRange,
    class RightRange,
    class MaskRange>
inline std::size_t predicate_binary(
    Op&& op,
    const LeftRange& left,
    const RightRange& right,
    MaskRange& masks) {
    return predicate_binary<
        parallelism::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(op), left, right, masks);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class T>
inline void transform_where_unary(
    Op&& op,
    const T* input,
    const typename detail::mask_for<MaskLayout, Parallelism, T>::type* masks,
    T* output,
    std::size_t count) {
    using vec = typename detail::vector_for_parallelism<Parallelism, T>::type;

    static_assert(
        detail::is_supported_alignment_policy<Alignment>::value,
        "Alignment must be tsl::algo::alignment::detect, unaligned, or assume_aligned");
    static_assert(
        detail::is_supported_mask_layout<MaskLayout>::value,
        "MaskLayout must be tsl::algo::mask_layout::integral, native, bytes, "
        "or bits");
    detail::validate_vector_for_parallelism<Parallelism, vec, T>();
    detail::validate_mask_layout<MaskLayout, vec>();

    if constexpr (std::is_same<Alignment, alignment::detect>::value) {
        const bool input_aligned = detail::is_aligned_for<vec>(input);
        const bool output_aligned = detail::is_aligned_for<vec>(output);
        if (input_aligned && output_aligned) {
            detail::transform_where_unary_loop<
                vec,
                MaskLayout,
                alignment::assume_aligned,
                alignment::assume_aligned>(op, input, masks, output, count);
            return;
        }
        if (input_aligned) {
            detail::transform_where_unary_loop<
                vec,
                MaskLayout,
                alignment::assume_aligned,
                alignment::unaligned>(op, input, masks, output, count);
            return;
        }
        if (output_aligned) {
            detail::transform_where_unary_loop<
                vec,
                MaskLayout,
                alignment::unaligned,
                alignment::assume_aligned>(op, input, masks, output, count);
            return;
        }
        detail::transform_where_unary_loop<
            vec,
            MaskLayout,
            alignment::unaligned,
            alignment::unaligned>(op, input, masks, output, count);
    } else if constexpr (std::is_same<Alignment, alignment::assume_aligned>::value) {
        detail::transform_where_unary_loop<
            vec,
            MaskLayout,
            alignment::assume_aligned,
            alignment::assume_aligned>(op, input, masks, output, count);
    } else {
        detail::transform_where_unary_loop<
            vec,
            MaskLayout,
            alignment::unaligned,
            alignment::unaligned>(op, input, masks, output, count);
    }
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class T>
inline void transform_where_unary(
    Op&& op,
    const T* input,
    const fixed_mask_storage_type<MaskLayout, ParallelN, T>* masks,
    T* output,
    std::size_t count) {
    transform_where_unary<parallelism::fixed<ParallelN>, Alignment, MaskLayout>(
        std::forward<Op>(op), input, masks, output, count);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class InputRange,
    class MaskRange,
    class OutputRange>
inline void transform_where_unary(
    Op&& op,
    const InputRange& input,
    const MaskRange& masks,
    OutputRange& output) {
    transform_where_unary<Parallelism, Alignment, MaskLayout>(
        std::forward<Op>(op),
        detail::range_data(input),
        detail::range_data(masks),
        detail::range_data(output),
        detail::range_size(input));
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class InputRange,
    class MaskRange,
    class OutputRange>
inline void transform_where_unary(
    Op&& op,
    const InputRange& input,
    const MaskRange& masks,
    OutputRange& output) {
    transform_where_unary<
        parallelism::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(op), input, masks, output);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class T>
inline void transform_where_binary(
    Op&& op,
    const T* left,
    const T* right,
    const typename detail::mask_for<MaskLayout, Parallelism, T>::type* masks,
    T* output,
    std::size_t count) {
    using vec = typename detail::vector_for_parallelism<Parallelism, T>::type;

    static_assert(
        detail::is_supported_alignment_policy<Alignment>::value,
        "Alignment must be tsl::algo::alignment::detect, unaligned, or assume_aligned");
    static_assert(
        detail::is_supported_mask_layout<MaskLayout>::value,
        "MaskLayout must be tsl::algo::mask_layout::integral, native, bytes, "
        "or bits");
    detail::validate_vector_for_parallelism<Parallelism, vec, T>();
    detail::validate_mask_layout<MaskLayout, vec>();

    if constexpr (std::is_same<Alignment, alignment::detect>::value) {
        detail::transform_where_binary_dispatch_detect<vec, MaskLayout>(
            op, left, right, masks, output, count);
    } else if constexpr (std::is_same<Alignment, alignment::assume_aligned>::value) {
        detail::transform_where_binary_loop<
            vec,
            MaskLayout,
            alignment::assume_aligned,
            alignment::assume_aligned,
            alignment::assume_aligned>(op, left, right, masks, output, count);
    } else {
        detail::transform_where_binary_loop<
            vec,
            MaskLayout,
            alignment::unaligned,
            alignment::unaligned,
            alignment::unaligned>(op, left, right, masks, output, count);
    }
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class T>
inline void transform_where_binary(
    Op&& op,
    const T* left,
    const T* right,
    const fixed_mask_storage_type<MaskLayout, ParallelN, T>* masks,
    T* output,
    std::size_t count) {
    transform_where_binary<parallelism::fixed<ParallelN>, Alignment, MaskLayout>(
        std::forward<Op>(op), left, right, masks, output, count);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class LeftRange,
    class RightRange,
    class MaskRange,
    class OutputRange>
inline void transform_where_binary(
    Op&& op,
    const LeftRange& left,
    const RightRange& right,
    const MaskRange& masks,
    OutputRange& output) {
    transform_where_binary<Parallelism, Alignment, MaskLayout>(
        std::forward<Op>(op),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_data(masks),
        detail::range_data(output),
        detail::range_size(left));
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class LeftRange,
    class RightRange,
    class MaskRange,
    class OutputRange>
inline void transform_where_binary(
    Op&& op,
    const LeftRange& left,
    const RightRange& right,
    const MaskRange& masks,
    OutputRange& output) {
    transform_where_binary<
        parallelism::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(op), left, right, masks, output);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class T>
inline void transform_masked_unary(
    Op&& op,
    const T* input,
    const typename detail::mask_for<MaskLayout, Parallelism, T>::type* masks,
    T* output,
    std::size_t count) {
    using vec = typename detail::vector_for_parallelism<Parallelism, T>::type;

    static_assert(
        detail::is_supported_alignment_policy<Alignment>::value,
        "Alignment must be tsl::algo::alignment::detect, unaligned, or assume_aligned");
    static_assert(
        detail::is_supported_mask_layout<MaskLayout>::value,
        "MaskLayout must be tsl::algo::mask_layout::integral, native, bytes, "
        "or bits");
    detail::validate_vector_for_parallelism<Parallelism, vec, T>();
    detail::validate_mask_layout<MaskLayout, vec>();

    if constexpr (std::is_same<Alignment, alignment::detect>::value) {
        const bool input_aligned = detail::is_aligned_for<vec>(input);
        const bool output_aligned = detail::is_aligned_for<vec>(output);
        if (input_aligned && output_aligned) {
            detail::transform_masked_unary_loop<
                vec,
                MaskLayout,
                alignment::assume_aligned,
                alignment::assume_aligned>(op, input, masks, output, count);
            return;
        }
        if (input_aligned) {
            detail::transform_masked_unary_loop<
                vec,
                MaskLayout,
                alignment::assume_aligned,
                alignment::unaligned>(op, input, masks, output, count);
            return;
        }
        if (output_aligned) {
            detail::transform_masked_unary_loop<
                vec,
                MaskLayout,
                alignment::unaligned,
                alignment::assume_aligned>(op, input, masks, output, count);
            return;
        }
        detail::transform_masked_unary_loop<
            vec,
            MaskLayout,
            alignment::unaligned,
            alignment::unaligned>(op, input, masks, output, count);
    } else if constexpr (std::is_same<Alignment, alignment::assume_aligned>::value) {
        detail::transform_masked_unary_loop<
            vec,
            MaskLayout,
            alignment::assume_aligned,
            alignment::assume_aligned>(op, input, masks, output, count);
    } else {
        detail::transform_masked_unary_loop<
            vec,
            MaskLayout,
            alignment::unaligned,
            alignment::unaligned>(op, input, masks, output, count);
    }
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class T>
inline void transform_masked_unary(
    Op&& op,
    const T* input,
    const fixed_mask_storage_type<MaskLayout, ParallelN, T>* masks,
    T* output,
    std::size_t count) {
    transform_masked_unary<parallelism::fixed<ParallelN>, Alignment, MaskLayout>(
        std::forward<Op>(op), input, masks, output, count);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class InputRange,
    class MaskRange,
    class OutputRange>
inline void transform_masked_unary(
    Op&& op,
    const InputRange& input,
    const MaskRange& masks,
    OutputRange& output) {
    transform_masked_unary<Parallelism, Alignment, MaskLayout>(
        std::forward<Op>(op),
        detail::range_data(input),
        detail::range_data(masks),
        detail::range_data(output),
        detail::range_size(input));
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class InputRange,
    class MaskRange,
    class OutputRange>
inline void transform_masked_unary(
    Op&& op,
    const InputRange& input,
    const MaskRange& masks,
    OutputRange& output) {
    transform_masked_unary<
        parallelism::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(op), input, masks, output);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class T>
inline void transform_masked_binary(
    Op&& op,
    const T* left,
    const T* right,
    const typename detail::mask_for<MaskLayout, Parallelism, T>::type* masks,
    T* output,
    std::size_t count) {
    using vec = typename detail::vector_for_parallelism<Parallelism, T>::type;

    static_assert(
        detail::is_supported_alignment_policy<Alignment>::value,
        "Alignment must be tsl::algo::alignment::detect, unaligned, or assume_aligned");
    static_assert(
        detail::is_supported_mask_layout<MaskLayout>::value,
        "MaskLayout must be tsl::algo::mask_layout::integral, native, bytes, "
        "or bits");
    detail::validate_vector_for_parallelism<Parallelism, vec, T>();
    detail::validate_mask_layout<MaskLayout, vec>();

    if constexpr (std::is_same<Alignment, alignment::detect>::value) {
        detail::transform_masked_binary_dispatch_detect<vec, MaskLayout>(
            op, left, right, masks, output, count);
    } else if constexpr (std::is_same<Alignment, alignment::assume_aligned>::value) {
        detail::transform_masked_binary_loop<
            vec,
            MaskLayout,
            alignment::assume_aligned,
            alignment::assume_aligned,
            alignment::assume_aligned>(op, left, right, masks, output, count);
    } else {
        detail::transform_masked_binary_loop<
            vec,
            MaskLayout,
            alignment::unaligned,
            alignment::unaligned,
            alignment::unaligned>(op, left, right, masks, output, count);
    }
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class T>
inline void transform_masked_binary(
    Op&& op,
    const T* left,
    const T* right,
    const fixed_mask_storage_type<MaskLayout, ParallelN, T>* masks,
    T* output,
    std::size_t count) {
    transform_masked_binary<parallelism::fixed<ParallelN>, Alignment, MaskLayout>(
        std::forward<Op>(op), left, right, masks, output, count);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class LeftRange,
    class RightRange,
    class MaskRange,
    class OutputRange>
inline void transform_masked_binary(
    Op&& op,
    const LeftRange& left,
    const RightRange& right,
    const MaskRange& masks,
    OutputRange& output) {
    transform_masked_binary<Parallelism, Alignment, MaskLayout>(
        std::forward<Op>(op),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_data(masks),
        detail::range_data(output),
        detail::range_size(left));
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class LeftRange,
    class RightRange,
    class MaskRange,
    class OutputRange>
inline void transform_masked_binary(
    Op&& op,
    const LeftRange& left,
    const RightRange& right,
    const MaskRange& masks,
    OutputRange& output) {
    transform_masked_binary<
        parallelism::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(op), left, right, masks, output);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class Op,
    class T>
inline std::size_t count_unary(
    Op&& predicate,
    const T* input,
    std::size_t count) {
    using vec = typename detail::vector_for_parallelism<Parallelism, T>::type;

    static_assert(
        detail::is_supported_alignment_policy<Alignment>::value,
        "Alignment must be tsl::algo::alignment::detect, unaligned, or assume_aligned");
    detail::validate_vector_for_parallelism<Parallelism, vec, T>();
    detail::validate_integral_mask_layout<vec>();

    if constexpr (std::is_same<Alignment, alignment::detect>::value) {
        if (detail::is_aligned_for<vec>(input)) {
            return detail::count_unary_loop<vec, alignment::assume_aligned>(
                predicate, input, count);
        }
        return detail::count_unary_loop<vec, alignment::unaligned>(
            predicate, input, count);
    } else if constexpr (std::is_same<Alignment, alignment::assume_aligned>::value) {
        return detail::count_unary_loop<vec, alignment::assume_aligned>(
            predicate, input, count);
    } else {
        return detail::count_unary_loop<vec, alignment::unaligned>(
            predicate, input, count);
    }
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class Op,
    class T>
inline std::size_t count_unary(
    Op&& predicate,
    const T* input,
    std::size_t count) {
    return count_unary<parallelism::fixed<ParallelN>, Alignment>(
        std::forward<Op>(predicate), input, count);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class Op,
    class InputRange>
inline std::size_t count_unary(Op&& predicate, const InputRange& input) {
    return count_unary<Parallelism, Alignment>(
        std::forward<Op>(predicate),
        detail::range_data(input),
        detail::range_size(input));
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class Op,
    class InputRange>
inline std::size_t count_unary(Op&& predicate, const InputRange& input) {
    return count_unary<parallelism::fixed<ParallelN>, Alignment>(
        std::forward<Op>(predicate), input);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class Op,
    class T>
inline std::size_t count_binary(
    Op&& predicate,
    const T* left,
    const T* right,
    std::size_t count) {
    using vec = typename detail::vector_for_parallelism<Parallelism, T>::type;

    static_assert(
        detail::is_supported_alignment_policy<Alignment>::value,
        "Alignment must be tsl::algo::alignment::detect, unaligned, or assume_aligned");
    detail::validate_vector_for_parallelism<Parallelism, vec, T>();
    detail::validate_integral_mask_layout<vec>();

    if constexpr (std::is_same<Alignment, alignment::detect>::value) {
        return detail::count_binary_dispatch_detect<vec>(
            predicate, left, right, count);
    } else if constexpr (std::is_same<Alignment, alignment::assume_aligned>::value) {
        return detail::count_binary_loop<
            vec,
            alignment::assume_aligned,
            alignment::assume_aligned>(
            predicate, left, right, count);
    } else {
        return detail::count_binary_loop<
            vec,
            alignment::unaligned,
            alignment::unaligned>(
            predicate, left, right, count);
    }
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class Op,
    class T>
inline std::size_t count_binary(
    Op&& predicate,
    const T* left,
    const T* right,
    std::size_t count) {
    return count_binary<parallelism::fixed<ParallelN>, Alignment>(
        std::forward<Op>(predicate), left, right, count);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class Op,
    class LeftRange,
    class RightRange>
inline std::size_t count_binary(
    Op&& predicate,
    const LeftRange& left,
    const RightRange& right) {
    return count_binary<Parallelism, Alignment>(
        std::forward<Op>(predicate),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_size(left));
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class Op,
    class LeftRange,
    class RightRange>
inline std::size_t count_binary(
    Op&& predicate,
    const LeftRange& left,
    const RightRange& right) {
    return count_binary<parallelism::fixed<ParallelN>, Alignment>(
        std::forward<Op>(predicate), left, right);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class T>
inline std::size_t count_masked_unary(
    Op&& predicate,
    const T* input,
    const typename detail::mask_for<MaskLayout, Parallelism, T>::type* masks,
    std::size_t count) {
    using vec = typename detail::vector_for_parallelism<Parallelism, T>::type;

    static_assert(
        detail::is_supported_alignment_policy<Alignment>::value,
        "Alignment must be tsl::algo::alignment::detect, unaligned, or assume_aligned");
    static_assert(
        detail::is_supported_mask_layout<MaskLayout>::value,
        "MaskLayout must be tsl::algo::mask_layout::integral, native, bytes, "
        "or bits");
    detail::validate_vector_for_parallelism<Parallelism, vec, T>();
    detail::validate_mask_layout<MaskLayout, vec>();
    detail::validate_integral_mask_layout<vec>();

    if constexpr (std::is_same<Alignment, alignment::detect>::value) {
        if (detail::is_aligned_for<vec>(input)) {
            return detail::count_masked_unary_loop<
                vec,
                MaskLayout,
                alignment::assume_aligned>(
                predicate, input, masks, count);
        }
        return detail::count_masked_unary_loop<
            vec,
            MaskLayout,
            alignment::unaligned>(
            predicate, input, masks, count);
    } else if constexpr (std::is_same<Alignment, alignment::assume_aligned>::value) {
        return detail::count_masked_unary_loop<
            vec,
            MaskLayout,
            alignment::assume_aligned>(
            predicate, input, masks, count);
    } else {
        return detail::count_masked_unary_loop<
            vec,
            MaskLayout,
            alignment::unaligned>(
            predicate, input, masks, count);
    }
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class T>
inline std::size_t count_masked_unary(
    Op&& predicate,
    const T* input,
    const fixed_mask_storage_type<MaskLayout, ParallelN, T>* masks,
    std::size_t count) {
    return count_masked_unary<
        parallelism::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(predicate), input, masks, count);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class InputRange,
    class MaskRange>
inline std::size_t count_masked_unary(
    Op&& predicate,
    const InputRange& input,
    const MaskRange& masks) {
    return count_masked_unary<Parallelism, Alignment, MaskLayout>(
        std::forward<Op>(predicate),
        detail::range_data(input),
        detail::range_data(masks),
        detail::range_size(input));
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class InputRange,
    class MaskRange>
inline std::size_t count_masked_unary(
    Op&& predicate,
    const InputRange& input,
    const MaskRange& masks) {
    return count_masked_unary<
        parallelism::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(predicate), input, masks);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class T>
inline std::size_t count_masked_binary(
    Op&& predicate,
    const T* left,
    const T* right,
    const typename detail::mask_for<MaskLayout, Parallelism, T>::type* masks,
    std::size_t count) {
    using vec = typename detail::vector_for_parallelism<Parallelism, T>::type;

    static_assert(
        detail::is_supported_alignment_policy<Alignment>::value,
        "Alignment must be tsl::algo::alignment::detect, unaligned, or assume_aligned");
    static_assert(
        detail::is_supported_mask_layout<MaskLayout>::value,
        "MaskLayout must be tsl::algo::mask_layout::integral, native, bytes, "
        "or bits");
    detail::validate_vector_for_parallelism<Parallelism, vec, T>();
    detail::validate_mask_layout<MaskLayout, vec>();
    detail::validate_integral_mask_layout<vec>();

    if constexpr (std::is_same<Alignment, alignment::detect>::value) {
        return detail::count_masked_binary_dispatch_detect<vec, MaskLayout>(
            predicate, left, right, masks, count);
    } else if constexpr (std::is_same<Alignment, alignment::assume_aligned>::value) {
        return detail::count_masked_binary_loop<
            vec,
            MaskLayout,
            alignment::assume_aligned,
            alignment::assume_aligned>(
            predicate, left, right, masks, count);
    } else {
        return detail::count_masked_binary_loop<
            vec,
            MaskLayout,
            alignment::unaligned,
            alignment::unaligned>(
            predicate, left, right, masks, count);
    }
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class T>
inline std::size_t count_masked_binary(
    Op&& predicate,
    const T* left,
    const T* right,
    const fixed_mask_storage_type<MaskLayout, ParallelN, T>* masks,
    std::size_t count) {
    return count_masked_binary<
        parallelism::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(predicate), left, right, masks, count);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class LeftRange,
    class RightRange,
    class MaskRange>
inline std::size_t count_masked_binary(
    Op&& predicate,
    const LeftRange& left,
    const RightRange& right,
    const MaskRange& masks) {
    return count_masked_binary<Parallelism, Alignment, MaskLayout>(
        std::forward<Op>(predicate),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_data(masks),
        detail::range_size(left));
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class LeftRange,
    class RightRange,
    class MaskRange>
inline std::size_t count_masked_binary(
    Op&& predicate,
    const LeftRange& left,
    const RightRange& right,
    const MaskRange& masks) {
    return count_masked_binary<
        parallelism::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(predicate), left, right, masks);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class Op,
    class T>
inline std::size_t select_unary(
    Op&& predicate,
    const T* input,
    T* output,
    std::size_t count) {
    using vec = typename detail::vector_for_parallelism<Parallelism, T>::type;

    static_assert(
        detail::is_supported_alignment_policy<Alignment>::value,
        "Alignment must be tsl::algo::alignment::detect, unaligned, or assume_aligned");
    detail::validate_vector_for_parallelism<Parallelism, vec, T>();

    if constexpr (std::is_same<Alignment, alignment::detect>::value) {
        if (detail::is_aligned_for<vec>(input)) {
            return detail::select_unary_loop<vec, alignment::assume_aligned>(
                predicate, input, output, count);
        }
        return detail::select_unary_loop<vec, alignment::unaligned>(
            predicate, input, output, count);
    } else if constexpr (std::is_same<Alignment, alignment::assume_aligned>::value) {
        return detail::select_unary_loop<vec, alignment::assume_aligned>(
            predicate, input, output, count);
    } else {
        return detail::select_unary_loop<vec, alignment::unaligned>(
            predicate, input, output, count);
    }
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class Op,
    class T>
inline std::size_t select_unary(
    Op&& predicate,
    const T* input,
    T* output,
    std::size_t count) {
    return select_unary<parallelism::fixed<ParallelN>, Alignment>(
        std::forward<Op>(predicate), input, output, count);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class Op,
    class InputRange,
    class OutputRange>
inline std::size_t select_unary(
    Op&& predicate,
    const InputRange& input,
    OutputRange& output) {
    return select_unary<Parallelism, Alignment>(
        std::forward<Op>(predicate),
        detail::range_data(input),
        detail::range_data(output),
        detail::range_size(input));
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class Op,
    class InputRange,
    class OutputRange>
inline std::size_t select_unary(
    Op&& predicate,
    const InputRange& input,
    OutputRange& output) {
    return select_unary<parallelism::fixed<ParallelN>, Alignment>(
        std::forward<Op>(predicate), input, output);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class Op,
    class T>
inline std::size_t select_binary(
    Op&& predicate,
    const T* left,
    const T* right,
    T* output,
    std::size_t count) {
    using vec = typename detail::vector_for_parallelism<Parallelism, T>::type;

    static_assert(
        detail::is_supported_alignment_policy<Alignment>::value,
        "Alignment must be tsl::algo::alignment::detect, unaligned, or assume_aligned");
    detail::validate_vector_for_parallelism<Parallelism, vec, T>();

    if constexpr (std::is_same<Alignment, alignment::detect>::value) {
        return detail::select_binary_dispatch_detect<vec>(
            predicate, left, right, output, count);
    } else if constexpr (std::is_same<Alignment, alignment::assume_aligned>::value) {
        return detail::select_binary_loop<
            vec,
            alignment::assume_aligned,
            alignment::assume_aligned>(
            predicate, left, right, output, count);
    } else {
        return detail::select_binary_loop<
            vec,
            alignment::unaligned,
            alignment::unaligned>(
            predicate, left, right, output, count);
    }
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class Op,
    class T>
inline std::size_t select_binary(
    Op&& predicate,
    const T* left,
    const T* right,
    T* output,
    std::size_t count) {
    return select_binary<parallelism::fixed<ParallelN>, Alignment>(
        std::forward<Op>(predicate), left, right, output, count);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class Op,
    class LeftRange,
    class RightRange,
    class OutputRange>
inline std::size_t select_binary(
    Op&& predicate,
    const LeftRange& left,
    const RightRange& right,
    OutputRange& output) {
    return select_binary<Parallelism, Alignment>(
        std::forward<Op>(predicate),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_data(output),
        detail::range_size(left));
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class Op,
    class LeftRange,
    class RightRange,
    class OutputRange>
inline std::size_t select_binary(
    Op&& predicate,
    const LeftRange& left,
    const RightRange& right,
    OutputRange& output) {
    return select_binary<parallelism::fixed<ParallelN>, Alignment>(
        std::forward<Op>(predicate), left, right, output);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class T>
inline std::size_t select_masked_unary(
    Op&& predicate,
    const T* input,
    const typename detail::mask_for<MaskLayout, Parallelism, T>::type* masks,
    T* output,
    std::size_t count) {
    using vec = typename detail::vector_for_parallelism<Parallelism, T>::type;

    static_assert(
        detail::is_supported_alignment_policy<Alignment>::value,
        "Alignment must be tsl::algo::alignment::detect, unaligned, or assume_aligned");
    static_assert(
        detail::is_supported_mask_layout<MaskLayout>::value,
        "MaskLayout must be tsl::algo::mask_layout::integral, native, bytes, "
        "or bits");
    detail::validate_vector_for_parallelism<Parallelism, vec, T>();
    detail::validate_mask_layout<MaskLayout, vec>();

    if constexpr (std::is_same<Alignment, alignment::detect>::value) {
        if (detail::is_aligned_for<vec>(input)) {
            return detail::select_masked_unary_loop<
                vec,
                MaskLayout,
                alignment::assume_aligned>(
                predicate, input, masks, output, count);
        }
        return detail::select_masked_unary_loop<
            vec,
            MaskLayout,
            alignment::unaligned>(
            predicate, input, masks, output, count);
    } else if constexpr (std::is_same<Alignment, alignment::assume_aligned>::value) {
        return detail::select_masked_unary_loop<
            vec,
            MaskLayout,
            alignment::assume_aligned>(
            predicate, input, masks, output, count);
    } else {
        return detail::select_masked_unary_loop<
            vec,
            MaskLayout,
            alignment::unaligned>(
            predicate, input, masks, output, count);
    }
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class T>
inline std::size_t select_masked_unary(
    Op&& predicate,
    const T* input,
    const fixed_mask_storage_type<MaskLayout, ParallelN, T>* masks,
    T* output,
    std::size_t count) {
    return select_masked_unary<
        parallelism::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(predicate), input, masks, output, count);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class InputRange,
    class MaskRange,
    class OutputRange>
inline std::size_t select_masked_unary(
    Op&& predicate,
    const InputRange& input,
    const MaskRange& masks,
    OutputRange& output) {
    return select_masked_unary<Parallelism, Alignment, MaskLayout>(
        std::forward<Op>(predicate),
        detail::range_data(input),
        detail::range_data(masks),
        detail::range_data(output),
        detail::range_size(input));
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class InputRange,
    class MaskRange,
    class OutputRange>
inline std::size_t select_masked_unary(
    Op&& predicate,
    const InputRange& input,
    const MaskRange& masks,
    OutputRange& output) {
    return select_masked_unary<
        parallelism::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(predicate), input, masks, output);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class T>
inline std::size_t select_masked_binary(
    Op&& predicate,
    const T* left,
    const T* right,
    const typename detail::mask_for<MaskLayout, Parallelism, T>::type* masks,
    T* output,
    std::size_t count) {
    using vec = typename detail::vector_for_parallelism<Parallelism, T>::type;

    static_assert(
        detail::is_supported_alignment_policy<Alignment>::value,
        "Alignment must be tsl::algo::alignment::detect, unaligned, or assume_aligned");
    static_assert(
        detail::is_supported_mask_layout<MaskLayout>::value,
        "MaskLayout must be tsl::algo::mask_layout::integral, native, bytes, "
        "or bits");
    detail::validate_vector_for_parallelism<Parallelism, vec, T>();
    detail::validate_mask_layout<MaskLayout, vec>();

    if constexpr (std::is_same<Alignment, alignment::detect>::value) {
        return detail::select_masked_binary_dispatch_detect<vec, MaskLayout>(
            predicate, left, right, masks, output, count);
    } else if constexpr (std::is_same<Alignment, alignment::assume_aligned>::value) {
        return detail::select_masked_binary_loop<
            vec,
            MaskLayout,
            alignment::assume_aligned,
            alignment::assume_aligned>(
            predicate, left, right, masks, output, count);
    } else {
        return detail::select_masked_binary_loop<
            vec,
            MaskLayout,
            alignment::unaligned,
            alignment::unaligned>(
            predicate, left, right, masks, output, count);
    }
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class T>
inline std::size_t select_masked_binary(
    Op&& predicate,
    const T* left,
    const T* right,
    const fixed_mask_storage_type<MaskLayout, ParallelN, T>* masks,
    T* output,
    std::size_t count) {
    return select_masked_binary<
        parallelism::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(predicate), left, right, masks, output, count);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class LeftRange,
    class RightRange,
    class MaskRange,
    class OutputRange>
inline std::size_t select_masked_binary(
    Op&& predicate,
    const LeftRange& left,
    const RightRange& right,
    const MaskRange& masks,
    OutputRange& output) {
    return select_masked_binary<Parallelism, Alignment, MaskLayout>(
        std::forward<Op>(predicate),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_data(masks),
        detail::range_data(output),
        detail::range_size(left));
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class LeftRange,
    class RightRange,
    class MaskRange,
    class OutputRange>
inline std::size_t select_masked_binary(
    Op&& predicate,
    const LeftRange& left,
    const RightRange& right,
    const MaskRange& masks,
    OutputRange& output) {
    return select_masked_binary<
        parallelism::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(predicate), left, right, masks, output);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class Op,
    class T,
    class IndexT>
inline std::size_t select_indices_unary(
    Op&& predicate,
    const T* input,
    IndexT* indices,
    std::size_t count) {
    using vec = typename detail::vector_for_parallelism<Parallelism, T>::type;

    static_assert(
        detail::is_supported_alignment_policy<Alignment>::value,
        "Alignment must be tsl::algo::alignment::detect, unaligned, or assume_aligned");
    detail::validate_vector_for_parallelism<Parallelism, vec, T>();
    detail::validate_integral_mask_layout<vec>();

    if constexpr (std::is_same<Alignment, alignment::detect>::value) {
        if (detail::is_aligned_for<vec>(input)) {
            return detail::select_indices_unary_loop<
                vec,
                alignment::assume_aligned>(
                predicate, input, indices, count);
        }
        return detail::select_indices_unary_loop<vec, alignment::unaligned>(
            predicate, input, indices, count);
    } else if constexpr (std::is_same<Alignment, alignment::assume_aligned>::value) {
        return detail::select_indices_unary_loop<vec, alignment::assume_aligned>(
            predicate, input, indices, count);
    } else {
        return detail::select_indices_unary_loop<vec, alignment::unaligned>(
            predicate, input, indices, count);
    }
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class Op,
    class T,
    class IndexT>
inline std::size_t select_indices_unary(
    Op&& predicate,
    const T* input,
    IndexT* indices,
    std::size_t count) {
    return select_indices_unary<parallelism::fixed<ParallelN>, Alignment>(
        std::forward<Op>(predicate), input, indices, count);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class Op,
    class InputRange,
    class IndexRange>
inline std::size_t select_indices_unary(
    Op&& predicate,
    const InputRange& input,
    IndexRange& indices) {
    return select_indices_unary<Parallelism, Alignment>(
        std::forward<Op>(predicate),
        detail::range_data(input),
        detail::range_data(indices),
        detail::range_size(input));
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class Op,
    class InputRange,
    class IndexRange>
inline std::size_t select_indices_unary(
    Op&& predicate,
    const InputRange& input,
    IndexRange& indices) {
    return select_indices_unary<parallelism::fixed<ParallelN>, Alignment>(
        std::forward<Op>(predicate), input, indices);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class Op,
    class T,
    class IndexT>
inline std::size_t select_indices_binary(
    Op&& predicate,
    const T* left,
    const T* right,
    IndexT* indices,
    std::size_t count) {
    using vec = typename detail::vector_for_parallelism<Parallelism, T>::type;

    static_assert(
        detail::is_supported_alignment_policy<Alignment>::value,
        "Alignment must be tsl::algo::alignment::detect, unaligned, or assume_aligned");
    detail::validate_vector_for_parallelism<Parallelism, vec, T>();
    detail::validate_integral_mask_layout<vec>();

    if constexpr (std::is_same<Alignment, alignment::detect>::value) {
        return detail::select_indices_binary_dispatch_detect<vec>(
            predicate, left, right, indices, count);
    } else if constexpr (std::is_same<Alignment, alignment::assume_aligned>::value) {
        return detail::select_indices_binary_loop<
            vec,
            alignment::assume_aligned,
            alignment::assume_aligned>(
            predicate, left, right, indices, count);
    } else {
        return detail::select_indices_binary_loop<
            vec,
            alignment::unaligned,
            alignment::unaligned>(
            predicate, left, right, indices, count);
    }
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class Op,
    class T,
    class IndexT>
inline std::size_t select_indices_binary(
    Op&& predicate,
    const T* left,
    const T* right,
    IndexT* indices,
    std::size_t count) {
    return select_indices_binary<parallelism::fixed<ParallelN>, Alignment>(
        std::forward<Op>(predicate), left, right, indices, count);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class Op,
    class LeftRange,
    class RightRange,
    class IndexRange>
inline std::size_t select_indices_binary(
    Op&& predicate,
    const LeftRange& left,
    const RightRange& right,
    IndexRange& indices) {
    return select_indices_binary<Parallelism, Alignment>(
        std::forward<Op>(predicate),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_data(indices),
        detail::range_size(left));
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class Op,
    class LeftRange,
    class RightRange,
    class IndexRange>
inline std::size_t select_indices_binary(
    Op&& predicate,
    const LeftRange& left,
    const RightRange& right,
    IndexRange& indices) {
    return select_indices_binary<parallelism::fixed<ParallelN>, Alignment>(
        std::forward<Op>(predicate), left, right, indices);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class T,
    class IndexT>
inline std::size_t select_masked_indices_unary(
    Op&& predicate,
    const T* input,
    const typename detail::mask_for<MaskLayout, Parallelism, T>::type* masks,
    IndexT* indices,
    std::size_t count) {
    using vec = typename detail::vector_for_parallelism<Parallelism, T>::type;

    static_assert(
        detail::is_supported_alignment_policy<Alignment>::value,
        "Alignment must be tsl::algo::alignment::detect, unaligned, or assume_aligned");
    static_assert(
        detail::is_supported_mask_layout<MaskLayout>::value,
        "MaskLayout must be tsl::algo::mask_layout::integral, native, bytes, "
        "or bits");
    detail::validate_vector_for_parallelism<Parallelism, vec, T>();
    detail::validate_mask_layout<MaskLayout, vec>();
    detail::validate_integral_mask_layout<vec>();

    if constexpr (std::is_same<Alignment, alignment::detect>::value) {
        if (detail::is_aligned_for<vec>(input)) {
            return detail::select_masked_indices_unary_loop<
                vec,
                MaskLayout,
                alignment::assume_aligned>(
                predicate, input, masks, indices, count);
        }
        return detail::select_masked_indices_unary_loop<
            vec,
            MaskLayout,
            alignment::unaligned>(
            predicate, input, masks, indices, count);
    } else if constexpr (std::is_same<Alignment, alignment::assume_aligned>::value) {
        return detail::select_masked_indices_unary_loop<
            vec,
            MaskLayout,
            alignment::assume_aligned>(
            predicate, input, masks, indices, count);
    } else {
        return detail::select_masked_indices_unary_loop<
            vec,
            MaskLayout,
            alignment::unaligned>(
            predicate, input, masks, indices, count);
    }
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class T,
    class IndexT>
inline std::size_t select_masked_indices_unary(
    Op&& predicate,
    const T* input,
    const fixed_mask_storage_type<MaskLayout, ParallelN, T>* masks,
    IndexT* indices,
    std::size_t count) {
    return select_masked_indices_unary<
        parallelism::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(predicate), input, masks, indices, count);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class InputRange,
    class MaskRange,
    class IndexRange>
inline std::size_t select_masked_indices_unary(
    Op&& predicate,
    const InputRange& input,
    const MaskRange& masks,
    IndexRange& indices) {
    return select_masked_indices_unary<Parallelism, Alignment, MaskLayout>(
        std::forward<Op>(predicate),
        detail::range_data(input),
        detail::range_data(masks),
        detail::range_data(indices),
        detail::range_size(input));
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class InputRange,
    class MaskRange,
    class IndexRange>
inline std::size_t select_masked_indices_unary(
    Op&& predicate,
    const InputRange& input,
    const MaskRange& masks,
    IndexRange& indices) {
    return select_masked_indices_unary<
        parallelism::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(predicate), input, masks, indices);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class T,
    class IndexT>
inline std::size_t select_masked_indices_binary(
    Op&& predicate,
    const T* left,
    const T* right,
    const typename detail::mask_for<MaskLayout, Parallelism, T>::type* masks,
    IndexT* indices,
    std::size_t count) {
    using vec = typename detail::vector_for_parallelism<Parallelism, T>::type;

    static_assert(
        detail::is_supported_alignment_policy<Alignment>::value,
        "Alignment must be tsl::algo::alignment::detect, unaligned, or assume_aligned");
    static_assert(
        detail::is_supported_mask_layout<MaskLayout>::value,
        "MaskLayout must be tsl::algo::mask_layout::integral, native, bytes, "
        "or bits");
    detail::validate_vector_for_parallelism<Parallelism, vec, T>();
    detail::validate_mask_layout<MaskLayout, vec>();
    detail::validate_integral_mask_layout<vec>();

    if constexpr (std::is_same<Alignment, alignment::detect>::value) {
        return detail::select_masked_indices_binary_dispatch_detect<vec, MaskLayout>(
            predicate, left, right, masks, indices, count);
    } else if constexpr (std::is_same<Alignment, alignment::assume_aligned>::value) {
        return detail::select_masked_indices_binary_loop<
            vec,
            MaskLayout,
            alignment::assume_aligned,
            alignment::assume_aligned>(
            predicate, left, right, masks, indices, count);
    } else {
        return detail::select_masked_indices_binary_loop<
            vec,
            MaskLayout,
            alignment::unaligned,
            alignment::unaligned>(
            predicate, left, right, masks, indices, count);
    }
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class T,
    class IndexT>
inline std::size_t select_masked_indices_binary(
    Op&& predicate,
    const T* left,
    const T* right,
    const fixed_mask_storage_type<MaskLayout, ParallelN, T>* masks,
    IndexT* indices,
    std::size_t count) {
    return select_masked_indices_binary<
        parallelism::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(predicate), left, right, masks, indices, count);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class LeftRange,
    class RightRange,
    class MaskRange,
    class IndexRange>
inline std::size_t select_masked_indices_binary(
    Op&& predicate,
    const LeftRange& left,
    const RightRange& right,
    const MaskRange& masks,
    IndexRange& indices) {
    return select_masked_indices_binary<Parallelism, Alignment, MaskLayout>(
        std::forward<Op>(predicate),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_data(masks),
        detail::range_data(indices),
        detail::range_size(left));
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class LeftRange,
    class RightRange,
    class MaskRange,
    class IndexRange>
inline std::size_t select_masked_indices_binary(
    Op&& predicate,
    const LeftRange& left,
    const RightRange& right,
    const MaskRange& masks,
    IndexRange& indices) {
    return select_masked_indices_binary<
        parallelism::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(predicate), left, right, masks, indices);
}

template <
    std::size_t ParallelN,
    std::size_t Scale = 0,
    class Op,
    class T,
    class InputIndexT,
    class OutputIndexT>
inline std::size_t select_selected_indices_unary(
    Op&& predicate,
    const T* input,
    const InputIndexT* input_indices,
    OutputIndexT* output_indices,
    std::size_t selected_count) {
    static_assert(ParallelN > 0, "select_selected_indices_unary<ParallelN> requires ParallelN > 0");
    using vec = typename detail::vector_for_selected_rows<ParallelN, T>::type;

    static_assert(
        vec::has_static_lane_count_v,
        "selected-row selection requires a static-lane vector");
    static_assert(
        vec::vector_element_count == ParallelN,
        "selected-row selection vector must have exactly ParallelN lanes");

    return detail::select_selected_indices_unary_loop<vec, Scale>(
        predicate, input, input_indices, output_indices, selected_count);
}

template <
    std::size_t ParallelN,
    std::size_t Scale = 0,
    class Op,
    class InputRange,
    class InputIndexRange,
    class OutputIndexRange>
inline std::size_t select_selected_indices_unary(
    Op&& predicate,
    const InputRange& input,
    const InputIndexRange& input_indices,
    OutputIndexRange& output_indices) {
    return select_selected_indices_unary<ParallelN, Scale>(
        std::forward<Op>(predicate),
        detail::range_data(input),
        detail::range_data(input_indices),
        detail::range_data(output_indices),
        detail::range_size(input_indices));
}

template <
    std::size_t ParallelN,
    std::size_t Scale = 0,
    class Op,
    class T,
    class InputIndexT,
    class OutputIndexT>
inline std::size_t select_selected_indices_binary(
    Op&& predicate,
    const T* left,
    const T* right,
    const InputIndexT* input_indices,
    OutputIndexT* output_indices,
    std::size_t selected_count) {
    static_assert(ParallelN > 0, "select_selected_indices_binary<ParallelN> requires ParallelN > 0");
    using vec = typename detail::vector_for_selected_rows<ParallelN, T>::type;

    static_assert(
        vec::has_static_lane_count_v,
        "selected-row selection requires a static-lane vector");
    static_assert(
        vec::vector_element_count == ParallelN,
        "selected-row selection vector must have exactly ParallelN lanes");

    return detail::select_selected_indices_binary_loop<vec, Scale>(
        predicate, left, right, input_indices, output_indices, selected_count);
}

template <
    std::size_t ParallelN,
    std::size_t Scale = 0,
    class Op,
    class LeftRange,
    class RightRange,
    class InputIndexRange,
    class OutputIndexRange>
inline std::size_t select_selected_indices_binary(
    Op&& predicate,
    const LeftRange& left,
    const RightRange& right,
    const InputIndexRange& input_indices,
    OutputIndexRange& output_indices) {
    return select_selected_indices_binary<ParallelN, Scale>(
        std::forward<Op>(predicate),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_data(input_indices),
        detail::range_data(output_indices),
        detail::range_size(input_indices));
}

template <
    std::size_t ParallelN,
    std::size_t Scale = 0,
    class Op,
    class T,
    class IndexT>
inline std::size_t count_selected_unary(
    Op&& predicate,
    const T* input,
    const IndexT* indices,
    std::size_t selected_count) {
    static_assert(ParallelN > 0, "count_selected_unary<ParallelN> requires ParallelN > 0");
    using vec = typename detail::vector_for_selected_rows<ParallelN, T>::type;

    static_assert(
        vec::has_static_lane_count_v,
        "selected-row count requires a static-lane vector");
    static_assert(
        vec::vector_element_count == ParallelN,
        "selected-row count vector must have exactly ParallelN lanes");

    return detail::count_selected_unary_loop<vec, Scale>(
        predicate, input, indices, selected_count);
}

template <
    std::size_t ParallelN,
    std::size_t Scale = 0,
    class Op,
    class InputRange,
    class IndexRange>
inline std::size_t count_selected_unary(
    Op&& predicate,
    const InputRange& input,
    const IndexRange& indices) {
    return count_selected_unary<ParallelN, Scale>(
        std::forward<Op>(predicate),
        detail::range_data(input),
        detail::range_data(indices),
        detail::range_size(indices));
}

template <
    std::size_t ParallelN,
    std::size_t Scale = 0,
    class Op,
    class T,
    class IndexT>
inline std::size_t count_selected_binary(
    Op&& predicate,
    const T* left,
    const T* right,
    const IndexT* indices,
    std::size_t selected_count) {
    static_assert(ParallelN > 0, "count_selected_binary<ParallelN> requires ParallelN > 0");
    using vec = typename detail::vector_for_selected_rows<ParallelN, T>::type;

    static_assert(
        vec::has_static_lane_count_v,
        "selected-row count requires a static-lane vector");
    static_assert(
        vec::vector_element_count == ParallelN,
        "selected-row count vector must have exactly ParallelN lanes");

    return detail::count_selected_binary_loop<vec, Scale>(
        predicate, left, right, indices, selected_count);
}

template <
    std::size_t ParallelN,
    std::size_t Scale = 0,
    class Op,
    class LeftRange,
    class RightRange,
    class IndexRange>
inline std::size_t count_selected_binary(
    Op&& predicate,
    const LeftRange& left,
    const RightRange& right,
    const IndexRange& indices) {
    return count_selected_binary<ParallelN, Scale>(
        std::forward<Op>(predicate),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_data(indices),
        detail::range_size(indices));
}

template <
    std::size_t ParallelN,
    std::size_t Scale = 0,
    class Op,
    class T,
    class IndexT>
inline void transform_selected_unary(
    Op&& op,
    const T* input,
    const IndexT* indices,
    T* output,
    std::size_t selected_count) {
    static_assert(ParallelN > 0, "transform_selected_unary<ParallelN> requires ParallelN > 0");
    using vec = typename detail::vector_for_selected_rows<ParallelN, T>::type;

    static_assert(
        vec::has_static_lane_count_v,
        "selected-row transform requires a static-lane vector");
    static_assert(
        vec::vector_element_count == ParallelN,
        "selected-row transform vector must have exactly ParallelN lanes");

    detail::transform_selected_unary_loop<vec, Scale>(
        op, input, indices, output, selected_count);
}

template <
    std::size_t ParallelN,
    std::size_t Scale = 0,
    class Op,
    class InputRange,
    class IndexRange,
    class OutputRange>
inline void transform_selected_unary(
    Op&& op,
    const InputRange& input,
    const IndexRange& indices,
    OutputRange& output) {
    transform_selected_unary<ParallelN, Scale>(
        std::forward<Op>(op),
        detail::range_data(input),
        detail::range_data(indices),
        detail::range_data(output),
        detail::range_size(indices));
}

template <
    std::size_t ParallelN,
    std::size_t Scale = 0,
    class Op,
    class T,
    class IndexT>
inline void transform_selected_binary(
    Op&& op,
    const T* left,
    const T* right,
    const IndexT* indices,
    T* output,
    std::size_t selected_count) {
    static_assert(ParallelN > 0, "transform_selected_binary<ParallelN> requires ParallelN > 0");
    using vec = typename detail::vector_for_selected_rows<ParallelN, T>::type;

    static_assert(
        vec::has_static_lane_count_v,
        "selected-row transform requires a static-lane vector");
    static_assert(
        vec::vector_element_count == ParallelN,
        "selected-row transform vector must have exactly ParallelN lanes");

    detail::transform_selected_binary_loop<vec, Scale>(
        op, left, right, indices, output, selected_count);
}

template <
    std::size_t ParallelN,
    std::size_t Scale = 0,
    class Op,
    class LeftRange,
    class RightRange,
    class IndexRange,
    class OutputRange>
inline void transform_selected_binary(
    Op&& op,
    const LeftRange& left,
    const RightRange& right,
    const IndexRange& indices,
    OutputRange& output) {
    transform_selected_binary<ParallelN, Scale>(
        std::forward<Op>(op),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_data(indices),
        detail::range_data(output),
        detail::range_size(indices));
}

template <
    std::size_t ParallelN,
    std::size_t Scale = 0,
    class Op,
    class T,
    class IndexT>
inline auto aggregate_selected_unary(
    Op&& op,
    const T* input,
    const IndexT* indices,
    std::size_t selected_count) {
    static_assert(ParallelN > 0, "aggregate_selected_unary<ParallelN> requires ParallelN > 0");
    using vec = typename detail::vector_for_selected_rows<ParallelN, T>::type;

    static_assert(
        vec::has_static_lane_count_v,
        "selected-row aggregate requires a static-lane vector");
    static_assert(
        vec::vector_element_count == ParallelN,
        "selected-row aggregate vector must have exactly ParallelN lanes");

    return detail::aggregate_selected_unary_loop<vec, Scale>(
        op, input, indices, selected_count);
}

template <
    std::size_t ParallelN,
    std::size_t Scale = 0,
    class Op,
    class InputRange,
    class IndexRange>
inline auto aggregate_selected_unary(
    Op&& op,
    const InputRange& input,
    const IndexRange& indices) {
    return aggregate_selected_unary<ParallelN, Scale>(
        std::forward<Op>(op),
        detail::range_data(input),
        detail::range_data(indices),
        detail::range_size(indices));
}

template <
    std::size_t ParallelN,
    std::size_t Scale = 0,
    class Op,
    class T,
    class IndexT>
inline auto aggregate_selected_binary(
    Op&& op,
    const T* left,
    const T* right,
    const IndexT* indices,
    std::size_t selected_count) {
    static_assert(ParallelN > 0, "aggregate_selected_binary<ParallelN> requires ParallelN > 0");
    using vec = typename detail::vector_for_selected_rows<ParallelN, T>::type;

    static_assert(
        vec::has_static_lane_count_v,
        "selected-row aggregate requires a static-lane vector");
    static_assert(
        vec::vector_element_count == ParallelN,
        "selected-row aggregate vector must have exactly ParallelN lanes");

    return detail::aggregate_selected_binary_loop<vec, Scale>(
        op, left, right, indices, selected_count);
}

template <
    std::size_t ParallelN,
    std::size_t Scale = 0,
    class Op,
    class LeftRange,
    class RightRange,
    class IndexRange>
inline auto aggregate_selected_binary(
    Op&& op,
    const LeftRange& left,
    const RightRange& right,
    const IndexRange& indices) {
    return aggregate_selected_binary<ParallelN, Scale>(
        std::forward<Op>(op),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_data(indices),
        detail::range_size(indices));
}

template <
    std::size_t ParallelN,
    std::size_t Scale = 0,
    class Op,
    class T,
    class IndexT>
inline void consume_selected_unary(
    Op&& op,
    const T* input,
    const IndexT* indices,
    std::size_t selected_count) {
    static_assert(ParallelN > 0, "consume_selected_unary<ParallelN> requires ParallelN > 0");
    using vec = typename detail::vector_for_selected_rows<ParallelN, T>::type;

    static_assert(
        vec::has_static_lane_count_v,
        "selected-row consume requires a static-lane vector");
    static_assert(
        vec::vector_element_count == ParallelN,
        "selected-row consume vector must have exactly ParallelN lanes");

    detail::consume_selected_unary_loop<vec, Scale>(
        op, input, indices, selected_count);
}

template <
    std::size_t ParallelN,
    std::size_t Scale = 0,
    class Op,
    class InputRange,
    class IndexRange>
inline void consume_selected_unary(
    Op&& op,
    const InputRange& input,
    const IndexRange& indices) {
    consume_selected_unary<ParallelN, Scale>(
        std::forward<Op>(op),
        detail::range_data(input),
        detail::range_data(indices),
        detail::range_size(indices));
}

template <
    std::size_t ParallelN,
    std::size_t Scale = 0,
    class Op,
    class T,
    class IndexT>
inline void consume_selected_binary(
    Op&& op,
    const T* left,
    const T* right,
    const IndexT* indices,
    std::size_t selected_count) {
    static_assert(ParallelN > 0, "consume_selected_binary<ParallelN> requires ParallelN > 0");
    using vec = typename detail::vector_for_selected_rows<ParallelN, T>::type;

    static_assert(
        vec::has_static_lane_count_v,
        "selected-row consume requires a static-lane vector");
    static_assert(
        vec::vector_element_count == ParallelN,
        "selected-row consume vector must have exactly ParallelN lanes");

    detail::consume_selected_binary_loop<vec, Scale>(
        op, left, right, indices, selected_count);
}

template <
    std::size_t ParallelN,
    std::size_t Scale = 0,
    class Op,
    class LeftRange,
    class RightRange,
    class IndexRange>
inline void consume_selected_binary(
    Op&& op,
    const LeftRange& left,
    const RightRange& right,
    const IndexRange& indices) {
    consume_selected_binary<ParallelN, Scale>(
        std::forward<Op>(op),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_data(indices),
        detail::range_size(indices));
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class Op,
    class T>
inline auto aggregate_unary(
    Op&& op,
    const T* input,
    std::size_t count) {
    using vec = typename detail::vector_for_parallelism<Parallelism, T>::type;

    static_assert(
        detail::is_supported_alignment_policy<Alignment>::value,
        "Alignment must be tsl::algo::alignment::detect, unaligned, or assume_aligned");
    detail::validate_vector_for_parallelism<Parallelism, vec, T>();

    if constexpr (std::is_same<Alignment, alignment::detect>::value) {
        if (detail::is_aligned_for<vec>(input)) {
            return detail::aggregate_unary_loop<vec, alignment::assume_aligned>(
                op, input, count);
        }
        return detail::aggregate_unary_loop<vec, alignment::unaligned>(
            op, input, count);
    } else if constexpr (std::is_same<Alignment, alignment::assume_aligned>::value) {
        return detail::aggregate_unary_loop<vec, alignment::assume_aligned>(
            op, input, count);
    } else {
        return detail::aggregate_unary_loop<vec, alignment::unaligned>(
            op, input, count);
    }
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class Op,
    class T>
inline auto aggregate_unary(
    Op&& op,
    const T* input,
    std::size_t count) {
    return aggregate_unary<parallelism::fixed<ParallelN>, Alignment>(
        std::forward<Op>(op), input, count);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class Op,
    class InputRange>
inline auto aggregate_unary(Op&& op, const InputRange& input) {
    return aggregate_unary<Parallelism, Alignment>(
        std::forward<Op>(op),
        detail::range_data(input),
        detail::range_size(input));
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class Op,
    class InputRange>
inline auto aggregate_unary(Op&& op, const InputRange& input) {
    return aggregate_unary<parallelism::fixed<ParallelN>, Alignment>(
        std::forward<Op>(op), input);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class Op,
    class T>
inline auto aggregate_binary(
    Op&& op,
    const T* left,
    const T* right,
    std::size_t count) {
    using vec = typename detail::vector_for_parallelism<Parallelism, T>::type;

    static_assert(
        detail::is_supported_alignment_policy<Alignment>::value,
        "Alignment must be tsl::algo::alignment::detect, unaligned, or assume_aligned");
    detail::validate_vector_for_parallelism<Parallelism, vec, T>();

    if constexpr (std::is_same<Alignment, alignment::detect>::value) {
        return detail::aggregate_binary_dispatch_detect<vec>(
            op, left, right, count);
    } else if constexpr (std::is_same<Alignment, alignment::assume_aligned>::value) {
        return detail::aggregate_binary_loop<
            vec,
            alignment::assume_aligned,
            alignment::assume_aligned>(op, left, right, count);
    } else {
        return detail::aggregate_binary_loop<
            vec,
            alignment::unaligned,
            alignment::unaligned>(op, left, right, count);
    }
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class Op,
    class T>
inline auto aggregate_binary(
    Op&& op,
    const T* left,
    const T* right,
    std::size_t count) {
    return aggregate_binary<parallelism::fixed<ParallelN>, Alignment>(
        std::forward<Op>(op), left, right, count);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class Op,
    class LeftRange,
    class RightRange>
inline auto aggregate_binary(
    Op&& op,
    const LeftRange& left,
    const RightRange& right) {
    return aggregate_binary<Parallelism, Alignment>(
        std::forward<Op>(op),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_size(left));
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class Op,
    class LeftRange,
    class RightRange>
inline auto aggregate_binary(
    Op&& op,
    const LeftRange& left,
    const RightRange& right) {
    return aggregate_binary<parallelism::fixed<ParallelN>, Alignment>(
        std::forward<Op>(op), left, right);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class T>
inline auto aggregate_masked_unary(
    Op&& op,
    const T* input,
    const typename detail::mask_for<MaskLayout, Parallelism, T>::type* masks,
    std::size_t count) {
    using vec = typename detail::vector_for_parallelism<Parallelism, T>::type;

    static_assert(
        detail::is_supported_alignment_policy<Alignment>::value,
        "Alignment must be tsl::algo::alignment::detect, unaligned, or assume_aligned");
    static_assert(
        detail::is_supported_mask_layout<MaskLayout>::value,
        "MaskLayout must be tsl::algo::mask_layout::integral, native, bytes, "
        "or bits");
    detail::validate_vector_for_parallelism<Parallelism, vec, T>();
    detail::validate_mask_layout<MaskLayout, vec>();

    if constexpr (std::is_same<Alignment, alignment::detect>::value) {
        if (detail::is_aligned_for<vec>(input)) {
            return detail::aggregate_masked_unary_loop<
                vec,
                MaskLayout,
                alignment::assume_aligned>(op, input, masks, count);
        }
        return detail::aggregate_masked_unary_loop<
            vec,
            MaskLayout,
            alignment::unaligned>(op, input, masks, count);
    } else if constexpr (std::is_same<Alignment, alignment::assume_aligned>::value) {
        return detail::aggregate_masked_unary_loop<
            vec,
            MaskLayout,
            alignment::assume_aligned>(op, input, masks, count);
    } else {
        return detail::aggregate_masked_unary_loop<
            vec,
            MaskLayout,
            alignment::unaligned>(op, input, masks, count);
    }
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class T>
inline auto aggregate_masked_unary(
    Op&& op,
    const T* input,
    const fixed_mask_storage_type<MaskLayout, ParallelN, T>* masks,
    std::size_t count) {
    return aggregate_masked_unary<
        parallelism::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(op), input, masks, count);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class InputRange,
    class MaskRange>
inline auto aggregate_masked_unary(
    Op&& op,
    const InputRange& input,
    const MaskRange& masks) {
    return aggregate_masked_unary<Parallelism, Alignment, MaskLayout>(
        std::forward<Op>(op),
        detail::range_data(input),
        detail::range_data(masks),
        detail::range_size(input));
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class InputRange,
    class MaskRange>
inline auto aggregate_masked_unary(
    Op&& op,
    const InputRange& input,
    const MaskRange& masks) {
    return aggregate_masked_unary<
        parallelism::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(op), input, masks);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class T>
inline auto aggregate_masked_binary(
    Op&& op,
    const T* left,
    const T* right,
    const typename detail::mask_for<MaskLayout, Parallelism, T>::type* masks,
    std::size_t count) {
    using vec = typename detail::vector_for_parallelism<Parallelism, T>::type;

    static_assert(
        detail::is_supported_alignment_policy<Alignment>::value,
        "Alignment must be tsl::algo::alignment::detect, unaligned, or assume_aligned");
    static_assert(
        detail::is_supported_mask_layout<MaskLayout>::value,
        "MaskLayout must be tsl::algo::mask_layout::integral, native, bytes, "
        "or bits");
    detail::validate_vector_for_parallelism<Parallelism, vec, T>();
    detail::validate_mask_layout<MaskLayout, vec>();

    if constexpr (std::is_same<Alignment, alignment::detect>::value) {
        return detail::aggregate_masked_binary_dispatch_detect<vec, MaskLayout>(
            op, left, right, masks, count);
    } else if constexpr (std::is_same<Alignment, alignment::assume_aligned>::value) {
        return detail::aggregate_masked_binary_loop<
            vec,
            MaskLayout,
            alignment::assume_aligned,
            alignment::assume_aligned>(op, left, right, masks, count);
    } else {
        return detail::aggregate_masked_binary_loop<
            vec,
            MaskLayout,
            alignment::unaligned,
            alignment::unaligned>(op, left, right, masks, count);
    }
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class T>
inline auto aggregate_masked_binary(
    Op&& op,
    const T* left,
    const T* right,
    const fixed_mask_storage_type<MaskLayout, ParallelN, T>* masks,
    std::size_t count) {
    return aggregate_masked_binary<
        parallelism::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(op), left, right, masks, count);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class LeftRange,
    class RightRange,
    class MaskRange>
inline auto aggregate_masked_binary(
    Op&& op,
    const LeftRange& left,
    const RightRange& right,
    const MaskRange& masks) {
    return aggregate_masked_binary<Parallelism, Alignment, MaskLayout>(
        std::forward<Op>(op),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_data(masks),
        detail::range_size(left));
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class LeftRange,
    class RightRange,
    class MaskRange>
inline auto aggregate_masked_binary(
    Op&& op,
    const LeftRange& left,
    const RightRange& right,
    const MaskRange& masks) {
    return aggregate_masked_binary<
        parallelism::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(op), left, right, masks);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class Op,
    class T>
inline void consume_unary(
    Op&& op,
    const T* input,
    std::size_t count) {
    using vec = typename detail::vector_for_parallelism<Parallelism, T>::type;

    static_assert(
        detail::is_supported_alignment_policy<Alignment>::value,
        "Alignment must be tsl::algo::alignment::detect, unaligned, or assume_aligned");
    detail::validate_vector_for_parallelism<Parallelism, vec, T>();

    if constexpr (std::is_same<Alignment, alignment::detect>::value) {
        if (detail::is_aligned_for<vec>(input)) {
            detail::consume_unary_loop<vec, alignment::assume_aligned>(
                op, input, count);
            return;
        }
        detail::consume_unary_loop<vec, alignment::unaligned>(
            op, input, count);
    } else if constexpr (std::is_same<Alignment, alignment::assume_aligned>::value) {
        detail::consume_unary_loop<vec, alignment::assume_aligned>(
            op, input, count);
    } else {
        detail::consume_unary_loop<vec, alignment::unaligned>(
            op, input, count);
    }
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class Op,
    class T>
inline void consume_unary(
    Op&& op,
    const T* input,
    std::size_t count) {
    consume_unary<parallelism::fixed<ParallelN>, Alignment>(
        std::forward<Op>(op), input, count);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class Op,
    class InputRange>
inline void consume_unary(Op&& op, const InputRange& input) {
    consume_unary<Parallelism, Alignment>(
        std::forward<Op>(op),
        detail::range_data(input),
        detail::range_size(input));
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class Op,
    class InputRange>
inline void consume_unary(Op&& op, const InputRange& input) {
    consume_unary<parallelism::fixed<ParallelN>, Alignment>(
        std::forward<Op>(op), input);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class Op,
    class T>
inline void consume_binary(
    Op&& op,
    const T* left,
    const T* right,
    std::size_t count) {
    using vec = typename detail::vector_for_parallelism<Parallelism, T>::type;

    static_assert(
        detail::is_supported_alignment_policy<Alignment>::value,
        "Alignment must be tsl::algo::alignment::detect, unaligned, or assume_aligned");
    detail::validate_vector_for_parallelism<Parallelism, vec, T>();

    if constexpr (std::is_same<Alignment, alignment::detect>::value) {
        detail::consume_binary_dispatch_detect<vec>(op, left, right, count);
    } else if constexpr (std::is_same<Alignment, alignment::assume_aligned>::value) {
        detail::consume_binary_loop<
            vec,
            alignment::assume_aligned,
            alignment::assume_aligned>(op, left, right, count);
    } else {
        detail::consume_binary_loop<
            vec,
            alignment::unaligned,
            alignment::unaligned>(op, left, right, count);
    }
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class Op,
    class T>
inline void consume_binary(
    Op&& op,
    const T* left,
    const T* right,
    std::size_t count) {
    consume_binary<parallelism::fixed<ParallelN>, Alignment>(
        std::forward<Op>(op), left, right, count);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class Op,
    class LeftRange,
    class RightRange>
inline void consume_binary(
    Op&& op,
    const LeftRange& left,
    const RightRange& right) {
    consume_binary<Parallelism, Alignment>(
        std::forward<Op>(op),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_size(left));
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class Op,
    class LeftRange,
    class RightRange>
inline void consume_binary(
    Op&& op,
    const LeftRange& left,
    const RightRange& right) {
    consume_binary<parallelism::fixed<ParallelN>, Alignment>(
        std::forward<Op>(op), left, right);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class T>
inline void consume_masked_unary(
    Op&& op,
    const T* input,
    const typename detail::mask_for<MaskLayout, Parallelism, T>::type* masks,
    std::size_t count) {
    using vec = typename detail::vector_for_parallelism<Parallelism, T>::type;

    static_assert(
        detail::is_supported_alignment_policy<Alignment>::value,
        "Alignment must be tsl::algo::alignment::detect, unaligned, or assume_aligned");
    static_assert(
        detail::is_supported_mask_layout<MaskLayout>::value,
        "MaskLayout must be tsl::algo::mask_layout::integral, native, bytes, "
        "or bits");
    detail::validate_vector_for_parallelism<Parallelism, vec, T>();
    detail::validate_mask_layout<MaskLayout, vec>();

    if constexpr (std::is_same<Alignment, alignment::detect>::value) {
        if (detail::is_aligned_for<vec>(input)) {
            detail::consume_masked_unary_loop<
                vec,
                MaskLayout,
                alignment::assume_aligned>(op, input, masks, count);
            return;
        }
        detail::consume_masked_unary_loop<
            vec,
            MaskLayout,
            alignment::unaligned>(op, input, masks, count);
    } else if constexpr (std::is_same<Alignment, alignment::assume_aligned>::value) {
        detail::consume_masked_unary_loop<
            vec,
            MaskLayout,
            alignment::assume_aligned>(op, input, masks, count);
    } else {
        detail::consume_masked_unary_loop<
            vec,
            MaskLayout,
            alignment::unaligned>(op, input, masks, count);
    }
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class T>
inline void consume_masked_unary(
    Op&& op,
    const T* input,
    const fixed_mask_storage_type<MaskLayout, ParallelN, T>* masks,
    std::size_t count) {
    consume_masked_unary<parallelism::fixed<ParallelN>, Alignment, MaskLayout>(
        std::forward<Op>(op), input, masks, count);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class InputRange,
    class MaskRange>
inline void consume_masked_unary(
    Op&& op,
    const InputRange& input,
    const MaskRange& masks) {
    consume_masked_unary<Parallelism, Alignment, MaskLayout>(
        std::forward<Op>(op),
        detail::range_data(input),
        detail::range_data(masks),
        detail::range_size(input));
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class InputRange,
    class MaskRange>
inline void consume_masked_unary(
    Op&& op,
    const InputRange& input,
    const MaskRange& masks) {
    consume_masked_unary<
        parallelism::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(op), input, masks);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class T>
inline void consume_masked_binary(
    Op&& op,
    const T* left,
    const T* right,
    const typename detail::mask_for<MaskLayout, Parallelism, T>::type* masks,
    std::size_t count) {
    using vec = typename detail::vector_for_parallelism<Parallelism, T>::type;

    static_assert(
        detail::is_supported_alignment_policy<Alignment>::value,
        "Alignment must be tsl::algo::alignment::detect, unaligned, or assume_aligned");
    static_assert(
        detail::is_supported_mask_layout<MaskLayout>::value,
        "MaskLayout must be tsl::algo::mask_layout::integral, native, bytes, "
        "or bits");
    detail::validate_vector_for_parallelism<Parallelism, vec, T>();
    detail::validate_mask_layout<MaskLayout, vec>();

    if constexpr (std::is_same<Alignment, alignment::detect>::value) {
        detail::consume_masked_binary_dispatch_detect<vec, MaskLayout>(
            op, left, right, masks, count);
    } else if constexpr (std::is_same<Alignment, alignment::assume_aligned>::value) {
        detail::consume_masked_binary_loop<
            vec,
            MaskLayout,
            alignment::assume_aligned,
            alignment::assume_aligned>(op, left, right, masks, count);
    } else {
        detail::consume_masked_binary_loop<
            vec,
            MaskLayout,
            alignment::unaligned,
            alignment::unaligned>(op, left, right, masks, count);
    }
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class T>
inline void consume_masked_binary(
    Op&& op,
    const T* left,
    const T* right,
    const fixed_mask_storage_type<MaskLayout, ParallelN, T>* masks,
    std::size_t count) {
    consume_masked_binary<parallelism::fixed<ParallelN>, Alignment, MaskLayout>(
        std::forward<Op>(op), left, right, masks, count);
}

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class LeftRange,
    class RightRange,
    class MaskRange>
inline void consume_masked_binary(
    Op&& op,
    const LeftRange& left,
    const RightRange& right,
    const MaskRange& masks) {
    consume_masked_binary<Parallelism, Alignment, MaskLayout>(
        std::forward<Op>(op),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_data(masks),
        detail::range_size(left));
}

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class LeftRange,
    class RightRange,
    class MaskRange>
inline void consume_masked_binary(
    Op&& op,
    const LeftRange& left,
    const RightRange& right,
    const MaskRange& masks) {
    consume_masked_binary<
        parallelism::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(op), left, right, masks);
}


}  // namespace tsl::algo
