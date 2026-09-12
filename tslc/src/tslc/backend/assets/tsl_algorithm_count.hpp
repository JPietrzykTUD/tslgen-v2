#pragma once

#include "tsl_algorithm_utility.hpp"
#include "tsl_algorithm_detail_count.hpp"

namespace tsl::algo {

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

}  // namespace tsl::algo
