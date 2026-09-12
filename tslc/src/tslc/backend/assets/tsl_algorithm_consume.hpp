#pragma once

#include "tsl_algorithm_utility.hpp"
#include "tsl_algorithm_detail_consume.hpp"

namespace tsl::algo {

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
