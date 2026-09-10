#pragma once

#include "tsl_algorithm_utility.hpp"
#include "tsl_algorithm_detail_select.hpp"

namespace tsl::algo {

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

}  // namespace tsl::algo
