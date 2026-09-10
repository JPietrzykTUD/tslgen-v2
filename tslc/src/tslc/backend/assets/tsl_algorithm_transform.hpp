#pragma once

#include "tsl_algorithm_utility.hpp"
#include "tsl_algorithm_detail_transform.hpp"

namespace tsl::algo {

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

}  // namespace tsl::algo
