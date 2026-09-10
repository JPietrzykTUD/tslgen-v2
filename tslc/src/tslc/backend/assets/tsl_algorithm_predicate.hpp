#pragma once

#include "tsl_algorithm_utility.hpp"
#include "tsl_algorithm_detail_predicate.hpp"

namespace tsl::algo {

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

}  // namespace tsl::algo
