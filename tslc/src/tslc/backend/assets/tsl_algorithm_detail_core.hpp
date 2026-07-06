#pragma once

#include "tsl_algorithm_tags.hpp"
#include "tsl_dataparallel.hpp"

namespace tsl::algo::detail {

template <class Alignment>
struct is_supported_alignment_policy
    : std::integral_constant<
          bool,
          std::is_same<Alignment, alignment::detect>::value ||
              std::is_same<Alignment, alignment::unaligned>::value ||
              std::is_same<Alignment, alignment::assume_aligned>::value> {};

template <class Alignment>
struct is_supported_transform_alignment_policy
    : std::integral_constant<
          bool,
          is_supported_alignment_policy<Alignment>::value ||
              std::is_same<Alignment, alignment::assume_inputs_aligned>::value ||
              std::is_same<Alignment, alignment::assume_output_aligned>::value ||
              std::is_same<Alignment, alignment::peel_to_aligned>::value> {};

template <class MaskLayout>
struct is_supported_mask_layout
    : std::integral_constant<
          bool,
          std::is_same<MaskLayout, mask_layout::integral>::value ||
              std::is_same<MaskLayout, mask_layout::native>::value ||
              std::is_same<MaskLayout, mask_layout::bytes>::value ||
              std::is_same<MaskLayout, mask_layout::bits>::value> {};

template <class...>
struct always_false : std::false_type {};

template <class Vec>
inline std::size_t lane_count() noexcept {
    if constexpr (Vec::has_static_lane_count_v) {
        return Vec::vector_element_count;
    } else {
        return Vec::lane_count();
    }
}

template <class Parallelism, class T>
struct vector_for_parallelism {
    using type = ::tsl::dataparallel::simd_for_t<Parallelism, T>;
};

template <std::size_t N, class T>
struct vector_for_selected_rows {
    using type =
        ::tsl::dataparallel::simd_for_t<::tsl::dataparallel::generic<N>, T>;
};

template <class T>
struct vector_for_selected_rows<1, T> {
    using type = ::tsl::simd<T, ::tsl::scalar>;
};

template <class Parallelism, class T>
struct integral_mask_for {
    using type = typename vector_for_parallelism<Parallelism, T>::type::imask_type;
};

template <class Parallelism, class T>
struct native_mask_for {
    using type = typename vector_for_parallelism<Parallelism, T>::type::mask_type;
};

template <class MaskLayout, class Vec>
struct mask_storage_for_vec;

template <class Vec>
struct mask_storage_for_vec<mask_layout::integral, Vec> {
    using type = typename Vec::imask_type;
};

template <class Vec>
struct mask_storage_for_vec<mask_layout::native, Vec> {
    using type = typename Vec::mask_type;
};

template <class Vec>
struct mask_storage_for_vec<mask_layout::bytes, Vec> {
    using type = std::uint8_t;
};

template <class Vec>
struct mask_storage_for_vec<mask_layout::bits, Vec> {
    using type = std::uint8_t;
};

template <class MaskLayout, class Vec>
using mask_storage_for_vec_t =
    typename mask_storage_for_vec<MaskLayout, Vec>::type;

template <class MaskLayout, class Parallelism, class T>
struct mask_for {
    using vec = typename vector_for_parallelism<Parallelism, T>::type;
    using type = mask_storage_for_vec_t<MaskLayout, vec>;
};

template <class Vec, class Ptr>
inline bool is_aligned_for(Ptr ptr) noexcept {
    const auto address = reinterpret_cast<std::uintptr_t>(ptr);
    return (address % Vec::vector_alignment) == 0;
}

template <class Vec, class Ptr>
inline std::uintptr_t alignment_residue(Ptr ptr) noexcept {
    const auto address = reinterpret_cast<std::uintptr_t>(ptr);
    return address % Vec::vector_alignment;
}

template <class Vec, class FirstPtr, class SecondPtr>
inline bool has_same_alignment_residue(FirstPtr first, SecondPtr second) noexcept {
    return alignment_residue<Vec>(first) == alignment_residue<Vec>(second);
}

template <class Vec, class FirstPtr, class SecondPtr, class ThirdPtr>
inline bool has_same_alignment_residue(
    FirstPtr first,
    SecondPtr second,
    ThirdPtr third) noexcept {
    const auto residue = alignment_residue<Vec>(first);
    return residue == alignment_residue<Vec>(second) &&
        residue == alignment_residue<Vec>(third);
}

template <class Vec, class Ptr>
inline std::size_t scalar_peel_count_to_alignment(Ptr ptr, std::size_t count) noexcept {
    std::size_t peel = 0;
    while (peel < count && !is_aligned_for<Vec>(ptr + peel)) {
        ++peel;
    }
    return peel;
}

template <class Range>
inline auto range_data(Range& range) -> decltype(std::data(range)) {
    return std::data(range);
}

template <class Range>
inline auto range_data(const Range& range) -> decltype(std::data(range)) {
    return std::data(range);
}

template <class Range>
inline std::size_t range_size(const Range& range) {
    return static_cast<std::size_t>(std::size(range));
}

template <class IndexT>
struct is_selection_index
    : std::integral_constant<
          bool,
          std::is_integral<IndexT>::value &&
              std::is_unsigned<IndexT>::value &&
              !std::is_same<IndexT, bool>::value> {};

template <class IndexT>
inline std::size_t selected_row_offset(IndexT index) noexcept {
    static_assert(
        is_selection_index<IndexT>::value,
        "selection-vector input indices must use an unsigned integral row-id type");
    return static_cast<std::size_t>(index);
}

template <class T, std::size_t Scale>
inline constexpr std::uint32_t selected_row_scale() noexcept {
    static_assert(
        Scale == 0 || Scale <= static_cast<std::size_t>(0xffffffffu),
        "selection-vector scale must fit into the generated gather immediate");
    return static_cast<std::uint32_t>(Scale == 0 ? sizeof(T) : Scale);
}

template <class T, class IndexT, std::size_t Scale>
inline const T* selected_row_pointer(const T* input, IndexT index) noexcept {
    const auto byte_offset =
        selected_row_offset(index) *
        static_cast<std::size_t>(selected_row_scale<T, Scale>());
    return reinterpret_cast<const T*>(
        reinterpret_cast<const std::uint8_t*>(input) + byte_offset);
}

template <class IndexT>
inline constexpr bool selected_index_can_use_gather_narrow() noexcept {
    return is_selection_index<IndexT>::value &&
           (sizeof(IndexT) == 4 || sizeof(IndexT) == 8);
}

template <class Vec>
struct is_generic_vector : std::false_type {};

template <class T, std::size_t N>
struct is_generic_vector<::tsl::simd<T, ::tsl::generic<N>>> : std::true_type {};

template <class Vec, class T, class IndexT, std::size_t Scale>
inline typename Vec::register_type load_selected_vector(
    const T* input,
    const IndexT* indices) {
    using scalar_vec = ::tsl::simd<T, ::tsl::scalar>;

    static_assert(
        is_selection_index<IndexT>::value,
        "selection-vector input indices must use an unsigned integral row-id type");

    if constexpr (std::is_same<Vec, scalar_vec>::value) {
        return ::tsl::load<scalar_vec, false>(
            selected_row_pointer<T, IndexT, Scale>(input, indices[0]));
    } else if constexpr (selected_index_can_use_gather_narrow<IndexT>()) {
        using index_vec = typename Vec::template with_base_type<IndexT>;
        return ::tsl::gather_narrow<
            Vec,
            index_vec,
            selected_row_scale<T, Scale>()>(input, indices);
    } else {
        static_assert(
            is_generic_vector<Vec>::value,
            "selected-row SIMD loading requires 32-bit or 64-bit index elements "
            "unless the vector is the portable generic vector");
        const std::size_t lanes = detail::lane_count<Vec>();
        typename Vec::register_type result{};
        for (std::size_t lane = 0; lane < lanes; ++lane) {
            result[lane] =
                *selected_row_pointer<T, IndexT, Scale>(input, indices[lane]);
        }
        return result;
    }
}

template <class Vec>
inline constexpr bool integral_mask_can_represent_vec() noexcept {
    return Vec::has_static_lane_count_v &&
           (Vec::vector_element_count <= (sizeof(typename Vec::imask_type) * 8));
}

template <class Vec>
inline constexpr bool native_mask_can_represent_vec() noexcept {
    if constexpr (std::is_integral<typename Vec::mask_type>::value) {
        return Vec::has_static_lane_count_v &&
               integral_mask_can_represent_vec<Vec>() &&
               (Vec::vector_element_count <= (sizeof(typename Vec::mask_type) * 8));
    } else {
        return integral_mask_can_represent_vec<Vec>();
    }
}

template <class Vec>
inline typename Vec::imask_type imask_set_lane(
    typename Vec::imask_type mask,
    std::size_t lane) noexcept {
    const auto bits = static_cast<std::uint64_t>(mask) | (std::uint64_t{1} << lane);
    return static_cast<typename Vec::imask_type>(bits);
}

template <class Mask>
inline bool imask_test_lane(Mask mask, std::size_t lane) noexcept {
    return ((static_cast<std::uint64_t>(mask) >> lane) & std::uint64_t{1}) != 0;
}

inline std::size_t packed_bit_mask_count(std::size_t count) noexcept {
    return (count + 7) / 8;
}

inline void packed_bit_mask_set(
    std::uint8_t* masks,
    std::size_t row,
    bool active) noexcept {
    const auto byte_index = row / 8;
    const auto bit = static_cast<std::uint8_t>(std::uint8_t{1} << (row % 8));
    if (active) {
        masks[byte_index] = static_cast<std::uint8_t>(masks[byte_index] | bit);
    } else {
        masks[byte_index] = static_cast<std::uint8_t>(masks[byte_index] & ~bit);
    }
}

inline bool packed_bit_mask_test(
    const std::uint8_t* masks,
    std::size_t row) noexcept {
    return ((masks[row / 8] >> (row % 8)) & std::uint8_t{1}) != 0;
}

template <class MaskLayout>
inline constexpr bool is_row_mask_layout() noexcept {
    return std::is_same<MaskLayout, mask_layout::bytes>::value ||
           std::is_same<MaskLayout, mask_layout::bits>::value;
}

template <class MaskLayout>
inline std::size_t row_mask_storage_count(std::size_t count) noexcept {
    if constexpr (std::is_same<MaskLayout, mask_layout::bits>::value) {
        return packed_bit_mask_count(count);
    } else {
        return count;
    }
}

template <class Op, class Vec, class... Args>
struct can_call_typed {
  private:
    template <class Candidate>
    static auto test(int) -> decltype(
        std::declval<Candidate&>().template operator()<Vec>(
            std::declval<Args>()...),
        std::true_type{});

    template <class>
    static std::false_type test(...);

  public:
    static constexpr bool value = decltype(test<Op>(0))::value;
};

template <class Op, class Vec, class... Args>
struct can_call_tagged {
  private:
    template <class Candidate>
    static auto test(int) -> decltype(
        std::declval<Candidate&>()(vector_tag<Vec>{}, std::declval<Args>()...),
        std::true_type{});

    template <class>
    static std::false_type test(...);

  public:
    static constexpr bool value = decltype(test<Op>(0))::value;
};

template <class Op, class... Args>
struct can_call_plain {
  private:
    template <class Candidate>
    static auto test(int) -> decltype(
        std::declval<Candidate&>()(std::declval<Args>()...),
        std::true_type{});

    template <class>
    static std::false_type test(...);

  public:
    static constexpr bool value = decltype(test<Op>(0))::value;
};

template <class Vec, class Op, class... Args>
decltype(auto) invoke_op(Op& op, Args&&... args) {
    if constexpr (can_call_typed<Op, Vec, Args&&...>::value) {
        return op.template operator()<Vec>(std::forward<Args>(args)...);
    } else if constexpr (can_call_tagged<Op, Vec, Args&&...>::value) {
        return op(vector_tag<Vec>{}, std::forward<Args>(args)...);
    } else if constexpr (can_call_plain<Op, Args&&...>::value) {
        return op(std::forward<Args>(args)...);
    } else {
        static_assert(
            always_false<Op, Vec, Args...>::value,
            "Op must be callable as op.template operator()<Vec>(...), "
            "op(tsl::algo::vector_tag<Vec>{}, ...), or op(...)");
    }
}

template <class Vec, class Op, class Mask, class... Args>
decltype(auto) invoke_masked_op(Op& op, Mask&& mask, Args&&... args) {
    if constexpr (can_call_typed<Op, Vec, Mask&&, Args&&...>::value) {
        return op.template operator()<Vec>(
            std::forward<Mask>(mask), std::forward<Args>(args)...);
    } else if constexpr (can_call_tagged<Op, Vec, Mask&&, Args&&...>::value) {
        return op(
            vector_tag<Vec>{},
            std::forward<Mask>(mask),
            std::forward<Args>(args)...);
    } else if constexpr (can_call_plain<Op, Mask&&, Args&&...>::value) {
        return op(std::forward<Mask>(mask), std::forward<Args>(args)...);
    } else {
        return invoke_op<Vec>(op, std::forward<Args>(args)...);
    }
}

template <class Vec, class Op, class Mask, class... Args>
decltype(auto) invoke_required_masked_op(Op& op, Mask&& mask, Args&&... args) {
    if constexpr (can_call_typed<Op, Vec, Mask&&, Args&&...>::value) {
        return op.template operator()<Vec>(
            std::forward<Mask>(mask), std::forward<Args>(args)...);
    } else if constexpr (can_call_tagged<Op, Vec, Mask&&, Args&&...>::value) {
        return op(
            vector_tag<Vec>{},
            std::forward<Mask>(mask),
            std::forward<Args>(args)...);
    } else if constexpr (can_call_plain<Op, Mask&&, Args&&...>::value) {
        return op(std::forward<Mask>(mask), std::forward<Args>(args)...);
    } else {
        static_assert(
            always_false<Op, Vec, Mask, Args...>::value,
            "Masked aggregate Op must be callable as "
            "op.template operator()<Vec>(mask, ...), "
            "op(tsl::algo::vector_tag<Vec>{}, mask, ...), or op(mask, ...)");
    }
}

template <class Op, class = void>
struct can_finalize_op : std::false_type {};

template <class Op>
struct can_finalize_op<Op, std::void_t<decltype(std::declval<Op&>().finalize())>>
    : std::true_type {};

template <class Op>
auto finalize_op(Op& op) {
    if constexpr (can_finalize_op<Op>::value) {
        return op.finalize();
    } else {
        static_assert(
            always_false<Op>::value,
            "Aggregate Op must expose finalize()");
    }
}

template <class Parallelism, class Vec, class T>
inline void validate_vector_for_parallelism() {
    static_assert(
        std::is_same<T, typename Vec::base_type>::value,
        "selected SIMD vector must preserve T as Vec::base_type");
    if constexpr (!std::is_same<Parallelism, ::tsl::dataparallel::native>::value) {
        static_assert(
            Vec::has_static_lane_count_v,
            "tsl::dataparallel fixed/generic policies require a static-lane SIMD vector");
        static_assert(
            Vec::vector_element_count == Parallelism::lanes,
            "tsl::dataparallel fixed/generic policies must produce exactly N lanes");
    }
}

}  // namespace tsl::algo::detail
