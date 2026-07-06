#pragma once

#include "tsl_algorithm_detail_core.hpp"

namespace tsl::algo::detail {

template <class Vec>
inline void validate_integral_mask_layout() {
    static_assert(
        integral_mask_can_represent_vec<Vec>(),
        "tsl::algo::mask_layout::integral requires Vec::imask_type to have at "
        "least one bit per lane");
}

template <class Vec>
inline void validate_native_mask_layout() {
    static_assert(
        native_mask_can_represent_vec<Vec>(),
        "tsl::algo::mask_layout::native requires Vec::mask_type and "
        "Vec::imask_type to represent at least one bit per lane");
}

template <class Vec>
inline void validate_byte_mask_layout() {
    static_assert(
        integral_mask_can_represent_vec<Vec>(),
        "tsl::algo::mask_layout::bytes requires Vec::imask_type to represent "
        "at least one bit per lane");
}

template <class Vec>
inline void validate_bit_mask_layout() {
    static_assert(
        integral_mask_can_represent_vec<Vec>(),
        "tsl::algo::mask_layout::bits requires Vec::imask_type to represent "
        "at least one bit per lane");
}

template <class MaskLayout, class Vec>
inline void validate_mask_layout() {
    static_assert(
        is_supported_mask_layout<MaskLayout>::value,
        "MaskLayout must be tsl::algo::mask_layout::integral, native, bytes, "
        "or bits");
    if constexpr (std::is_same<MaskLayout, mask_layout::integral>::value) {
        validate_integral_mask_layout<Vec>();
    } else if constexpr (std::is_same<MaskLayout, mask_layout::native>::value) {
        validate_native_mask_layout<Vec>();
    } else if constexpr (std::is_same<MaskLayout, mask_layout::bytes>::value) {
        validate_byte_mask_layout<Vec>();
    } else if constexpr (std::is_same<MaskLayout, mask_layout::bits>::value) {
        validate_bit_mask_layout<Vec>();
    }
}

template <class MaskLayout, class Vec>
inline typename Vec::mask_type mask_from_storage(
    mask_storage_for_vec_t<MaskLayout, Vec> mask) {
    if constexpr (std::is_same<MaskLayout, mask_layout::integral>::value) {
        return ::tsl::to_mask<Vec>(mask);
    } else if constexpr (std::is_same<MaskLayout, mask_layout::native>::value) {
        return mask;
    } else {
        static_assert(
            always_false<MaskLayout, Vec>::value,
            "Row masks are row-oriented and must be loaded by row index");
    }
}

template <class MaskLayout, class Vec>
inline mask_storage_for_vec_t<MaskLayout, Vec> mask_to_storage(
    typename Vec::mask_type mask) {
    if constexpr (std::is_same<MaskLayout, mask_layout::integral>::value) {
        return ::tsl::to_integral<Vec>(mask);
    } else if constexpr (std::is_same<MaskLayout, mask_layout::native>::value) {
        return mask;
    } else {
        static_assert(
            always_false<MaskLayout, Vec>::value,
            "Row masks are row-oriented and must be stored by row index");
    }
}

template <class MaskLayout, class Vec>
inline typename Vec::imask_type mask_storage_to_integral(
    mask_storage_for_vec_t<MaskLayout, Vec> mask) {
    if constexpr (std::is_same<MaskLayout, mask_layout::integral>::value) {
        return mask;
    } else if constexpr (std::is_same<MaskLayout, mask_layout::native>::value) {
        return ::tsl::to_integral<Vec>(mask);
    } else {
        static_assert(
            always_false<MaskLayout, Vec>::value,
            "Row masks are row-oriented and must be tested by row index");
    }
}

template <class MaskLayout, class Vec>
inline mask_storage_for_vec_t<MaskLayout, Vec> mask_storage_from_integral(
    typename Vec::imask_type mask) {
    if constexpr (std::is_same<MaskLayout, mask_layout::integral>::value) {
        return mask;
    } else if constexpr (std::is_same<MaskLayout, mask_layout::native>::value) {
        return ::tsl::to_mask<Vec>(mask);
    } else {
        static_assert(
            always_false<MaskLayout, Vec>::value,
            "Row masks are row-oriented and must be stored by row index");
    }
}

template <class MaskLayout, class Vec>
inline void clear_predicate_mask_storage(
    mask_storage_for_vec_t<MaskLayout, Vec>* masks,
    std::size_t count) {
    if constexpr (std::is_same<MaskLayout, mask_layout::bits>::value) {
        const std::size_t bytes = packed_bit_mask_count(count);
        for (std::size_t i = 0; i < bytes; ++i) {
            masks[i] = std::uint8_t{0};
        }
    }
}

template <class MaskLayout, class Vec>
inline void store_mask_storage(
    mask_storage_for_vec_t<MaskLayout, Vec>* masks,
    std::size_t chunk,
    std::size_t element,
    typename Vec::mask_type mask) {
    if constexpr (std::is_same<MaskLayout, mask_layout::bytes>::value) {
        const auto imask = ::tsl::to_integral<Vec>(mask);
        const std::size_t lanes = detail::lane_count<Vec>();
        for (std::size_t lane = 0; lane < lanes; ++lane) {
            masks[element + lane] =
                imask_test_lane(imask, lane) ? std::uint8_t{1} : std::uint8_t{0};
        }
    } else if constexpr (std::is_same<MaskLayout, mask_layout::bits>::value) {
        const auto imask = ::tsl::to_integral<Vec>(mask);
        const std::size_t lanes = detail::lane_count<Vec>();
        for (std::size_t lane = 0; lane < lanes; ++lane) {
            packed_bit_mask_set(masks, element + lane, imask_test_lane(imask, lane));
        }
    } else {
        masks[chunk] = mask_to_storage<MaskLayout, Vec>(mask);
    }
}

template <class MaskLayout, class Vec>
inline void store_tail_mask_storage(
    mask_storage_for_vec_t<MaskLayout, Vec>* masks,
    std::size_t chunk,
    std::size_t element,
    std::size_t lane,
    bool active) {
    if constexpr (std::is_same<MaskLayout, mask_layout::bytes>::value) {
        masks[element] = active ? std::uint8_t{1} : std::uint8_t{0};
    } else if constexpr (std::is_same<MaskLayout, mask_layout::bits>::value) {
        packed_bit_mask_set(masks, element, active);
    } else {
        auto imask = mask_storage_to_integral<MaskLayout, Vec>(masks[chunk]);
        if (active) {
            imask = imask_set_lane<Vec>(imask, lane);
        }
        masks[chunk] = mask_storage_from_integral<MaskLayout, Vec>(imask);
    }
}

template <class MaskLayout, class Vec>
inline typename Vec::mask_type load_mask_storage(
    const mask_storage_for_vec_t<MaskLayout, Vec>* masks,
    std::size_t chunk,
    std::size_t element) {
    if constexpr (std::is_same<MaskLayout, mask_layout::bytes>::value) {
        typename Vec::imask_type imask{};
        const std::size_t lanes = detail::lane_count<Vec>();
        for (std::size_t lane = 0; lane < lanes; ++lane) {
            if (masks[element + lane] != 0) {
                imask = imask_set_lane<Vec>(imask, lane);
            }
        }
        return ::tsl::to_mask<Vec>(imask);
    } else if constexpr (std::is_same<MaskLayout, mask_layout::bits>::value) {
        typename Vec::imask_type imask{};
        const std::size_t lanes = detail::lane_count<Vec>();
        for (std::size_t lane = 0; lane < lanes; ++lane) {
            if (packed_bit_mask_test(masks, element + lane)) {
                imask = imask_set_lane<Vec>(imask, lane);
            }
        }
        return ::tsl::to_mask<Vec>(imask);
    } else {
        return mask_from_storage<MaskLayout, Vec>(masks[chunk]);
    }
}

template <class MaskLayout, class Vec>
inline bool mask_storage_lane_active(
    const mask_storage_for_vec_t<MaskLayout, Vec>* masks,
    std::size_t chunk,
    std::size_t element,
    std::size_t lane) {
    if constexpr (std::is_same<MaskLayout, mask_layout::bytes>::value) {
        return masks[element] != 0;
    } else if constexpr (std::is_same<MaskLayout, mask_layout::bits>::value) {
        return packed_bit_mask_test(masks, element);
    } else {
        const auto imask = mask_storage_to_integral<MaskLayout, Vec>(masks[chunk]);
        return imask_test_lane(imask, lane);
    }
}

template <class Vec, class IndexT>
inline void append_indices_from_mask(
    typename Vec::mask_type active,
    IndexT* indices,
    std::size_t& produced,
    std::size_t base_index,
    std::size_t lanes) {
    static_assert(
        is_selection_index<IndexT>::value,
        "selection-vector output indices must use an unsigned integral row-id type");
    const auto imask = ::tsl::to_integral<Vec>(active);
    for (std::size_t lane = 0; lane < lanes; ++lane) {
        if (imask_test_lane(imask, lane)) {
            indices[produced] = static_cast<IndexT>(base_index + lane);
            produced += 1;
        }
    }
}

template <class Vec, class InputIndexT, class OutputIndexT>
inline void append_selected_indices_from_mask(
    typename Vec::mask_type active,
    const InputIndexT* input_indices,
    OutputIndexT* output_indices,
    std::size_t& produced,
    std::size_t base_index,
    std::size_t lanes) {
    static_assert(
        is_selection_index<InputIndexT>::value,
        "selection-vector input indices must use an unsigned integral row-id type");
    static_assert(
        is_selection_index<OutputIndexT>::value,
        "selection-vector output indices must use an unsigned integral row-id type");
    const auto imask = ::tsl::to_integral<Vec>(active);
    for (std::size_t lane = 0; lane < lanes; ++lane) {
        if (imask_test_lane(imask, lane)) {
            output_indices[produced] =
                static_cast<OutputIndexT>(input_indices[base_index + lane]);
            produced += 1;
        }
    }
}

}  // namespace tsl::algo::detail
