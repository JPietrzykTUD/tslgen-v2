#pragma once

#include "tsl_algorithm_detail_loops.hpp"

/**
 * @@file
 * Public unchecked data-parallel algorithms.
 *
 * Pointer/count overloads require every pointer to denote its complete live
 * range. Range overloads take their driving count from the first input and
 * require every secondary input, mask, index, and output to cover the related
 * extent. Explicit `assume_*` alignment policies are caller promises. Output
 * ranges must obey the alias rules documented by the corresponding
 * `*_checked` family. These functions perform no hidden validation; use the
 * checked range overload when the complete runtime contract is representable.
 */

namespace tsl::algo {

@{algorithm_alias_vector_type}

@{algorithm_alias_integral_mask_type}

@{algorithm_alias_native_mask_type}

@{algorithm_alias_mask_storage_type}

@{algorithm_alias_byte_mask_type}

@{algorithm_alias_bit_mask_type}

@{algorithm_alias_fixed_integral_mask_type}

@{algorithm_alias_fixed_native_mask_type}

@{algorithm_alias_fixed_mask_storage_type}

@{algorithm_alias_fixed_byte_mask_type}

@{algorithm_alias_fixed_bit_mask_type}

@{algorithm_declaration_integral_mask_chunk_count_2}
    using vec = vector_type<Parallelism, T>;
    detail::validate_integral_mask_layout<vec>();
    const std::size_t lanes = detail::lane_count<vec>();
    return (count + lanes - 1) / lanes;
}

@{algorithm_declaration_integral_mask_chunk_count_1}
    return integral_mask_chunk_count<::tsl::dataparallel::fixed<ParallelN>, T>(count);
}

@{algorithm_declaration_native_mask_chunk_count_2}
    using vec = vector_type<Parallelism, T>;
    detail::validate_native_mask_layout<vec>();
    const std::size_t lanes = detail::lane_count<vec>();
    return (count + lanes - 1) / lanes;
}

@{algorithm_declaration_native_mask_chunk_count_1}
    return native_mask_chunk_count<::tsl::dataparallel::fixed<ParallelN>, T>(count);
}

@{algorithm_declaration_mask_chunk_count_2}
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

@{algorithm_declaration_mask_chunk_count_1}
    return mask_chunk_count<MaskLayout, ::tsl::dataparallel::fixed<ParallelN>, T>(count);
}

@{algorithm_declaration_byte_mask_count_2}
    return mask_chunk_count<mask_layout::bytes, Parallelism, T>(count);
}

@{algorithm_declaration_byte_mask_count_1}
    return byte_mask_count<::tsl::dataparallel::fixed<ParallelN>, T>(count);
}

@{algorithm_declaration_bit_mask_count_2}
    return mask_chunk_count<mask_layout::bits, Parallelism, T>(count);
}

@{algorithm_declaration_bit_mask_count_1}
    return bit_mask_count<::tsl::dataparallel::fixed<ParallelN>, T>(count);
}

@{algorithm_declaration_for_each_chunk_4}
    using value_type = typename std::remove_cv<T>::type;
    using vec = typename detail::vector_for_parallelism<Parallelism, value_type>::type;

    detail::validate_vector_for_parallelism<Parallelism, vec, value_type>();
    detail::for_each_chunk_loop<vec>(op, data, count);
}

@{algorithm_declaration_for_each_chunk_2}
    for_each_chunk<::tsl::dataparallel::fixed<ParallelN>>(
        std::forward<Op>(op), data, count);
}

@{algorithm_declaration_for_each_chunk_3}
    for_each_chunk<Parallelism>(
        std::forward<Op>(op),
        detail::range_data(data),
        detail::range_size(data));
}

@{algorithm_declaration_for_each_chunk_1}
    for_each_chunk<::tsl::dataparallel::fixed<ParallelN>>(std::forward<Op>(op), data);
}

@{algorithm_declaration_transform_unary_4}
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

@{algorithm_declaration_transform_unary_3}
    transform_unary<Parallelism, Alignment>(
        std::forward<Op>(op),
        detail::range_data(input),
        detail::range_data(output),
        detail::range_size(input));
}

@{algorithm_declaration_transform_unary_2}
    transform_unary<::tsl::dataparallel::fixed<ParallelN>, Alignment>(
        std::forward<Op>(op), input, output, count);
}

@{algorithm_declaration_transform_unary_1}
    transform_unary<::tsl::dataparallel::fixed<ParallelN>, Alignment>(
        std::forward<Op>(op), input, output);
}

@{algorithm_declaration_transform_binary_4}
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

@{algorithm_declaration_transform_binary_3}
    transform_binary<Parallelism, Alignment>(
        std::forward<Op>(op),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_data(output),
        detail::range_size(left));
}

@{algorithm_declaration_transform_binary_2}
    transform_binary<::tsl::dataparallel::fixed<ParallelN>, Alignment>(
        std::forward<Op>(op), left, right, output, count);
}

@{algorithm_declaration_transform_binary_1}
    transform_binary<::tsl::dataparallel::fixed<ParallelN>, Alignment>(
        std::forward<Op>(op), left, right, output);
}

@{algorithm_declaration_predicate_unary_4}
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

@{algorithm_declaration_predicate_unary_2}
    return predicate_unary<::tsl::dataparallel::fixed<ParallelN>, Alignment, MaskLayout>(
        std::forward<Op>(op), input, masks, count);
}

@{algorithm_declaration_predicate_unary_3}
    return predicate_unary<Parallelism, Alignment, MaskLayout>(
        std::forward<Op>(op),
        detail::range_data(input),
        detail::range_data(masks),
        detail::range_size(input));
}

@{algorithm_declaration_predicate_unary_1}
    return predicate_unary<
        ::tsl::dataparallel::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(op), input, masks);
}

@{algorithm_declaration_predicate_binary_4}
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

@{algorithm_declaration_predicate_binary_2}
    return predicate_binary<::tsl::dataparallel::fixed<ParallelN>, Alignment, MaskLayout>(
        std::forward<Op>(op), left, right, masks, count);
}

@{algorithm_declaration_predicate_binary_3}
    return predicate_binary<Parallelism, Alignment, MaskLayout>(
        std::forward<Op>(op),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_data(masks),
        detail::range_size(left));
}

@{algorithm_declaration_predicate_binary_1}
    return predicate_binary<
        ::tsl::dataparallel::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(op), left, right, masks);
}

@{algorithm_declaration_transform_where_unary_4}
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

@{algorithm_declaration_transform_where_unary_2}
    transform_where_unary<::tsl::dataparallel::fixed<ParallelN>, Alignment, MaskLayout>(
        std::forward<Op>(op), input, masks, output, count);
}

@{algorithm_declaration_transform_where_unary_3}
    transform_where_unary<Parallelism, Alignment, MaskLayout>(
        std::forward<Op>(op),
        detail::range_data(input),
        detail::range_data(masks),
        detail::range_data(output),
        detail::range_size(input));
}

@{algorithm_declaration_transform_where_unary_1}
    transform_where_unary<
        ::tsl::dataparallel::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(op), input, masks, output);
}

@{algorithm_declaration_transform_where_binary_4}
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

@{algorithm_declaration_transform_where_binary_2}
    transform_where_binary<::tsl::dataparallel::fixed<ParallelN>, Alignment, MaskLayout>(
        std::forward<Op>(op), left, right, masks, output, count);
}

@{algorithm_declaration_transform_where_binary_3}
    transform_where_binary<Parallelism, Alignment, MaskLayout>(
        std::forward<Op>(op),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_data(masks),
        detail::range_data(output),
        detail::range_size(left));
}

@{algorithm_declaration_transform_where_binary_1}
    transform_where_binary<
        ::tsl::dataparallel::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(op), left, right, masks, output);
}

@{algorithm_declaration_transform_masked_unary_4}
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

@{algorithm_declaration_transform_masked_unary_2}
    transform_masked_unary<::tsl::dataparallel::fixed<ParallelN>, Alignment, MaskLayout>(
        std::forward<Op>(op), input, masks, output, count);
}

@{algorithm_declaration_transform_masked_unary_3}
    transform_masked_unary<Parallelism, Alignment, MaskLayout>(
        std::forward<Op>(op),
        detail::range_data(input),
        detail::range_data(masks),
        detail::range_data(output),
        detail::range_size(input));
}

@{algorithm_declaration_transform_masked_unary_1}
    transform_masked_unary<
        ::tsl::dataparallel::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(op), input, masks, output);
}

@{algorithm_declaration_transform_masked_binary_4}
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

@{algorithm_declaration_transform_masked_binary_2}
    transform_masked_binary<::tsl::dataparallel::fixed<ParallelN>, Alignment, MaskLayout>(
        std::forward<Op>(op), left, right, masks, output, count);
}

@{algorithm_declaration_transform_masked_binary_3}
    transform_masked_binary<Parallelism, Alignment, MaskLayout>(
        std::forward<Op>(op),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_data(masks),
        detail::range_data(output),
        detail::range_size(left));
}

@{algorithm_declaration_transform_masked_binary_1}
    transform_masked_binary<
        ::tsl::dataparallel::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(op), left, right, masks, output);
}

@{algorithm_declaration_count_unary_4}
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

@{algorithm_declaration_count_unary_2}
    return count_unary<::tsl::dataparallel::fixed<ParallelN>, Alignment>(
        std::forward<Op>(predicate), input, count);
}

@{algorithm_declaration_count_unary_3}
    return count_unary<Parallelism, Alignment>(
        std::forward<Op>(predicate),
        detail::range_data(input),
        detail::range_size(input));
}

@{algorithm_declaration_count_unary_1}
    return count_unary<::tsl::dataparallel::fixed<ParallelN>, Alignment>(
        std::forward<Op>(predicate), input);
}

@{algorithm_declaration_count_binary_4}
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

@{algorithm_declaration_count_binary_2}
    return count_binary<::tsl::dataparallel::fixed<ParallelN>, Alignment>(
        std::forward<Op>(predicate), left, right, count);
}

@{algorithm_declaration_count_binary_3}
    return count_binary<Parallelism, Alignment>(
        std::forward<Op>(predicate),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_size(left));
}

@{algorithm_declaration_count_binary_1}
    return count_binary<::tsl::dataparallel::fixed<ParallelN>, Alignment>(
        std::forward<Op>(predicate), left, right);
}

@{algorithm_declaration_count_masked_unary_4}
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

@{algorithm_declaration_count_masked_unary_2}
    return count_masked_unary<
        ::tsl::dataparallel::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(predicate), input, masks, count);
}

@{algorithm_declaration_count_masked_unary_3}
    return count_masked_unary<Parallelism, Alignment, MaskLayout>(
        std::forward<Op>(predicate),
        detail::range_data(input),
        detail::range_data(masks),
        detail::range_size(input));
}

@{algorithm_declaration_count_masked_unary_1}
    return count_masked_unary<
        ::tsl::dataparallel::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(predicate), input, masks);
}

@{algorithm_declaration_count_masked_binary_4}
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

@{algorithm_declaration_count_masked_binary_2}
    return count_masked_binary<
        ::tsl::dataparallel::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(predicate), left, right, masks, count);
}

@{algorithm_declaration_count_masked_binary_3}
    return count_masked_binary<Parallelism, Alignment, MaskLayout>(
        std::forward<Op>(predicate),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_data(masks),
        detail::range_size(left));
}

@{algorithm_declaration_count_masked_binary_1}
    return count_masked_binary<
        ::tsl::dataparallel::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(predicate), left, right, masks);
}

@{algorithm_declaration_select_unary_4}
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

@{algorithm_declaration_select_unary_2}
    return select_unary<::tsl::dataparallel::fixed<ParallelN>, Alignment>(
        std::forward<Op>(predicate), input, output, count);
}

@{algorithm_declaration_select_unary_3}
    return select_unary<Parallelism, Alignment>(
        std::forward<Op>(predicate),
        detail::range_data(input),
        detail::range_data(output),
        detail::range_size(input));
}

@{algorithm_declaration_select_unary_1}
    return select_unary<::tsl::dataparallel::fixed<ParallelN>, Alignment>(
        std::forward<Op>(predicate), input, output);
}

@{algorithm_declaration_select_binary_4}
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

@{algorithm_declaration_select_binary_2}
    return select_binary<::tsl::dataparallel::fixed<ParallelN>, Alignment>(
        std::forward<Op>(predicate), left, right, output, count);
}

@{algorithm_declaration_select_binary_3}
    return select_binary<Parallelism, Alignment>(
        std::forward<Op>(predicate),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_data(output),
        detail::range_size(left));
}

@{algorithm_declaration_select_binary_1}
    return select_binary<::tsl::dataparallel::fixed<ParallelN>, Alignment>(
        std::forward<Op>(predicate), left, right, output);
}

@{algorithm_declaration_select_masked_unary_4}
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

@{algorithm_declaration_select_masked_unary_2}
    return select_masked_unary<
        ::tsl::dataparallel::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(predicate), input, masks, output, count);
}

@{algorithm_declaration_select_masked_unary_3}
    return select_masked_unary<Parallelism, Alignment, MaskLayout>(
        std::forward<Op>(predicate),
        detail::range_data(input),
        detail::range_data(masks),
        detail::range_data(output),
        detail::range_size(input));
}

@{algorithm_declaration_select_masked_unary_1}
    return select_masked_unary<
        ::tsl::dataparallel::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(predicate), input, masks, output);
}

@{algorithm_declaration_select_masked_binary_4}
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

@{algorithm_declaration_select_masked_binary_2}
    return select_masked_binary<
        ::tsl::dataparallel::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(predicate), left, right, masks, output, count);
}

@{algorithm_declaration_select_masked_binary_3}
    return select_masked_binary<Parallelism, Alignment, MaskLayout>(
        std::forward<Op>(predicate),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_data(masks),
        detail::range_data(output),
        detail::range_size(left));
}

@{algorithm_declaration_select_masked_binary_1}
    return select_masked_binary<
        ::tsl::dataparallel::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(predicate), left, right, masks, output);
}

@{algorithm_declaration_select_indices_unary_4}
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

@{algorithm_declaration_select_indices_unary_2}
    return select_indices_unary<::tsl::dataparallel::fixed<ParallelN>, Alignment>(
        std::forward<Op>(predicate), input, indices, count);
}

@{algorithm_declaration_select_indices_unary_3}
    return select_indices_unary<Parallelism, Alignment>(
        std::forward<Op>(predicate),
        detail::range_data(input),
        detail::range_data(indices),
        detail::range_size(input));
}

@{algorithm_declaration_select_indices_unary_1}
    return select_indices_unary<::tsl::dataparallel::fixed<ParallelN>, Alignment>(
        std::forward<Op>(predicate), input, indices);
}

@{algorithm_declaration_select_indices_binary_4}
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

@{algorithm_declaration_select_indices_binary_2}
    return select_indices_binary<::tsl::dataparallel::fixed<ParallelN>, Alignment>(
        std::forward<Op>(predicate), left, right, indices, count);
}

@{algorithm_declaration_select_indices_binary_3}
    return select_indices_binary<Parallelism, Alignment>(
        std::forward<Op>(predicate),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_data(indices),
        detail::range_size(left));
}

@{algorithm_declaration_select_indices_binary_1}
    return select_indices_binary<::tsl::dataparallel::fixed<ParallelN>, Alignment>(
        std::forward<Op>(predicate), left, right, indices);
}

@{algorithm_declaration_select_masked_indices_unary_4}
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

@{algorithm_declaration_select_masked_indices_unary_2}
    return select_masked_indices_unary<
        ::tsl::dataparallel::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(predicate), input, masks, indices, count);
}

@{algorithm_declaration_select_masked_indices_unary_3}
    return select_masked_indices_unary<Parallelism, Alignment, MaskLayout>(
        std::forward<Op>(predicate),
        detail::range_data(input),
        detail::range_data(masks),
        detail::range_data(indices),
        detail::range_size(input));
}

@{algorithm_declaration_select_masked_indices_unary_1}
    return select_masked_indices_unary<
        ::tsl::dataparallel::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(predicate), input, masks, indices);
}

@{algorithm_declaration_select_masked_indices_binary_4}
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

@{algorithm_declaration_select_masked_indices_binary_2}
    return select_masked_indices_binary<
        ::tsl::dataparallel::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(predicate), left, right, masks, indices, count);
}

@{algorithm_declaration_select_masked_indices_binary_3}
    return select_masked_indices_binary<Parallelism, Alignment, MaskLayout>(
        std::forward<Op>(predicate),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_data(masks),
        detail::range_data(indices),
        detail::range_size(left));
}

@{algorithm_declaration_select_masked_indices_binary_1}
    return select_masked_indices_binary<
        ::tsl::dataparallel::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(predicate), left, right, masks, indices);
}

@{algorithm_declaration_select_selected_indices_unary_2}
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

@{algorithm_declaration_select_selected_indices_unary_1}
    return select_selected_indices_unary<ParallelN, Scale>(
        std::forward<Op>(predicate),
        detail::range_data(input),
        detail::range_data(input_indices),
        detail::range_data(output_indices),
        detail::range_size(input_indices));
}

@{algorithm_declaration_select_selected_indices_binary_2}
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

@{algorithm_declaration_select_selected_indices_binary_1}
    return select_selected_indices_binary<ParallelN, Scale>(
        std::forward<Op>(predicate),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_data(input_indices),
        detail::range_data(output_indices),
        detail::range_size(input_indices));
}

@{algorithm_declaration_count_selected_unary_2}
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

@{algorithm_declaration_count_selected_unary_1}
    return count_selected_unary<ParallelN, Scale>(
        std::forward<Op>(predicate),
        detail::range_data(input),
        detail::range_data(indices),
        detail::range_size(indices));
}

@{algorithm_declaration_count_selected_binary_2}
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

@{algorithm_declaration_count_selected_binary_1}
    return count_selected_binary<ParallelN, Scale>(
        std::forward<Op>(predicate),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_data(indices),
        detail::range_size(indices));
}

@{algorithm_declaration_transform_selected_unary_2}
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

@{algorithm_declaration_transform_selected_unary_1}
    transform_selected_unary<ParallelN, Scale>(
        std::forward<Op>(op),
        detail::range_data(input),
        detail::range_data(indices),
        detail::range_data(output),
        detail::range_size(indices));
}

@{algorithm_declaration_transform_selected_binary_2}
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

@{algorithm_declaration_transform_selected_binary_1}
    transform_selected_binary<ParallelN, Scale>(
        std::forward<Op>(op),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_data(indices),
        detail::range_data(output),
        detail::range_size(indices));
}

@{algorithm_declaration_aggregate_selected_unary_2}
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

@{algorithm_declaration_aggregate_selected_unary_1}
    return aggregate_selected_unary<ParallelN, Scale>(
        std::forward<Op>(op),
        detail::range_data(input),
        detail::range_data(indices),
        detail::range_size(indices));
}

@{algorithm_declaration_aggregate_selected_binary_2}
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

@{algorithm_declaration_aggregate_selected_binary_1}
    return aggregate_selected_binary<ParallelN, Scale>(
        std::forward<Op>(op),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_data(indices),
        detail::range_size(indices));
}

@{algorithm_declaration_consume_selected_unary_2}
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

@{algorithm_declaration_consume_selected_unary_1}
    consume_selected_unary<ParallelN, Scale>(
        std::forward<Op>(op),
        detail::range_data(input),
        detail::range_data(indices),
        detail::range_size(indices));
}

@{algorithm_declaration_consume_selected_binary_2}
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

@{algorithm_declaration_consume_selected_binary_1}
    consume_selected_binary<ParallelN, Scale>(
        std::forward<Op>(op),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_data(indices),
        detail::range_size(indices));
}

@{algorithm_declaration_aggregate_unary_4}
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

@{algorithm_declaration_aggregate_unary_2}
    return aggregate_unary<::tsl::dataparallel::fixed<ParallelN>, Alignment>(
        std::forward<Op>(op), input, count);
}

@{algorithm_declaration_aggregate_unary_3}
    return aggregate_unary<Parallelism, Alignment>(
        std::forward<Op>(op),
        detail::range_data(input),
        detail::range_size(input));
}

@{algorithm_declaration_aggregate_unary_1}
    return aggregate_unary<::tsl::dataparallel::fixed<ParallelN>, Alignment>(
        std::forward<Op>(op), input);
}

@{algorithm_declaration_aggregate_binary_4}
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

@{algorithm_declaration_aggregate_binary_2}
    return aggregate_binary<::tsl::dataparallel::fixed<ParallelN>, Alignment>(
        std::forward<Op>(op), left, right, count);
}

@{algorithm_declaration_aggregate_binary_3}
    return aggregate_binary<Parallelism, Alignment>(
        std::forward<Op>(op),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_size(left));
}

@{algorithm_declaration_aggregate_binary_1}
    return aggregate_binary<::tsl::dataparallel::fixed<ParallelN>, Alignment>(
        std::forward<Op>(op), left, right);
}

@{algorithm_declaration_aggregate_masked_unary_4}
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

@{algorithm_declaration_aggregate_masked_unary_2}
    return aggregate_masked_unary<
        ::tsl::dataparallel::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(op), input, masks, count);
}

@{algorithm_declaration_aggregate_masked_unary_3}
    return aggregate_masked_unary<Parallelism, Alignment, MaskLayout>(
        std::forward<Op>(op),
        detail::range_data(input),
        detail::range_data(masks),
        detail::range_size(input));
}

@{algorithm_declaration_aggregate_masked_unary_1}
    return aggregate_masked_unary<
        ::tsl::dataparallel::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(op), input, masks);
}

@{algorithm_declaration_aggregate_masked_binary_4}
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

@{algorithm_declaration_aggregate_masked_binary_2}
    return aggregate_masked_binary<
        ::tsl::dataparallel::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(op), left, right, masks, count);
}

@{algorithm_declaration_aggregate_masked_binary_3}
    return aggregate_masked_binary<Parallelism, Alignment, MaskLayout>(
        std::forward<Op>(op),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_data(masks),
        detail::range_size(left));
}

@{algorithm_declaration_aggregate_masked_binary_1}
    return aggregate_masked_binary<
        ::tsl::dataparallel::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(op), left, right, masks);
}

@{algorithm_declaration_consume_unary_4}
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

@{algorithm_declaration_consume_unary_2}
    consume_unary<::tsl::dataparallel::fixed<ParallelN>, Alignment>(
        std::forward<Op>(op), input, count);
}

@{algorithm_declaration_consume_unary_3}
    consume_unary<Parallelism, Alignment>(
        std::forward<Op>(op),
        detail::range_data(input),
        detail::range_size(input));
}

@{algorithm_declaration_consume_unary_1}
    consume_unary<::tsl::dataparallel::fixed<ParallelN>, Alignment>(
        std::forward<Op>(op), input);
}

@{algorithm_declaration_consume_binary_4}
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

@{algorithm_declaration_consume_binary_2}
    consume_binary<::tsl::dataparallel::fixed<ParallelN>, Alignment>(
        std::forward<Op>(op), left, right, count);
}

@{algorithm_declaration_consume_binary_3}
    consume_binary<Parallelism, Alignment>(
        std::forward<Op>(op),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_size(left));
}

@{algorithm_declaration_consume_binary_1}
    consume_binary<::tsl::dataparallel::fixed<ParallelN>, Alignment>(
        std::forward<Op>(op), left, right);
}

@{algorithm_declaration_consume_masked_unary_4}
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

@{algorithm_declaration_consume_masked_unary_2}
    consume_masked_unary<::tsl::dataparallel::fixed<ParallelN>, Alignment, MaskLayout>(
        std::forward<Op>(op), input, masks, count);
}

@{algorithm_declaration_consume_masked_unary_3}
    consume_masked_unary<Parallelism, Alignment, MaskLayout>(
        std::forward<Op>(op),
        detail::range_data(input),
        detail::range_data(masks),
        detail::range_size(input));
}

@{algorithm_declaration_consume_masked_unary_1}
    consume_masked_unary<
        ::tsl::dataparallel::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(op), input, masks);
}

@{algorithm_declaration_consume_masked_binary_4}
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

@{algorithm_declaration_consume_masked_binary_2}
    consume_masked_binary<::tsl::dataparallel::fixed<ParallelN>, Alignment, MaskLayout>(
        std::forward<Op>(op), left, right, masks, count);
}

@{algorithm_declaration_consume_masked_binary_3}
    consume_masked_binary<Parallelism, Alignment, MaskLayout>(
        std::forward<Op>(op),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_data(masks),
        detail::range_size(left));
}

@{algorithm_declaration_consume_masked_binary_1}
    consume_masked_binary<
        ::tsl::dataparallel::fixed<ParallelN>,
        Alignment,
        MaskLayout>(
        std::forward<Op>(op), left, right, masks);
}


}  // namespace tsl::algo
