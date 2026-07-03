#pragma once

#include <cstddef>
#include <cstdint>
#include <iterator>
#include <type_traits>
#include <utility>

namespace tsl::algo {

template <class Vec>
struct vector_tag {
    using type = Vec;
};

namespace alignment {
struct detect {};
struct unaligned {};
struct assume_aligned {};
}  // namespace alignment

namespace mask_layout {
struct integral {};
struct native {};
struct bytes {};
struct bits {};
}  // namespace mask_layout

namespace parallelism {
struct native {};

template <std::size_t N>
struct fixed {
    static_assert(N > 0, "tsl::algo::parallelism::fixed<N> requires N > 0");
    static constexpr std::size_t lanes = N;
};
}  // namespace parallelism

namespace detail {

template <class Alignment>
struct is_supported_alignment_policy
    : std::integral_constant<
          bool,
          std::is_same<Alignment, alignment::detect>::value ||
              std::is_same<Alignment, alignment::unaligned>::value ||
              std::is_same<Alignment, alignment::assume_aligned>::value> {};

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
struct vector_for_parallelism;

template <class T>
struct vector_for_parallelism<parallelism::native, T> {
    using type = ::tsl::native_simd_t<T>;
};

template <std::size_t N, class T>
struct vector_for_parallelism<parallelism::fixed<N>, T> {
    using type = ::tsl::inferred_simd_t<T, N>;
};

template <std::size_t N, class T>
struct vector_for_selected_rows {
    using type = ::tsl::simd<T, ::tsl::generic<N>>;
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
inline std::size_t selected_row_offset(IndexT index) noexcept {
    static_assert(
        std::is_integral<IndexT>::value,
        "selection-vector input indices must use an integral element type");
    return static_cast<std::size_t>(index);
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
    if constexpr (!std::is_same<Parallelism, parallelism::native>::value) {
        static_assert(
            Vec::has_static_lane_count_v,
            "tsl::algo::parallelism::fixed<N> requires a static-lane SIMD vector");
        static_assert(
            Vec::vector_element_count == Parallelism::lanes,
            "tsl::algo::parallelism::fixed<N> must produce exactly N lanes");
    }
}

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
        std::is_integral<IndexT>::value,
        "selection-vector output indices must use an integral element type");
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
        std::is_integral<InputIndexT>::value,
        "selection-vector input indices must use an integral element type");
    static_assert(
        std::is_integral<OutputIndexT>::value,
        "selection-vector output indices must use an integral element type");
    const auto imask = ::tsl::to_integral<Vec>(active);
    for (std::size_t lane = 0; lane < lanes; ++lane) {
        if (imask_test_lane(imask, lane)) {
            output_indices[produced] =
                static_cast<OutputIndexT>(input_indices[base_index + lane]);
            produced += 1;
        }
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
        std::is_integral<InputIndexT>::value,
        "selection-vector input indices must use an integral element type");
    static_assert(
        std::is_integral<OutputIndexT>::value,
        "selection-vector output indices must use an integral element type");
    validate_integral_mask_layout<Vec>();

    std::size_t produced = 0;
    if constexpr (std::is_same<Vec, scalar_vec>::value) {
        for (std::size_t i = 0; i < selected_count; ++i) {
            auto x = ::tsl::load<scalar_vec, false>(
                input + selected_row_offset(input_indices[i]));
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
            typename Vec::register_type x{};
            for (std::size_t lane = 0; lane < lanes; ++lane) {
                x[lane] = input[selected_row_offset(input_indices[i + lane])];
            }
            auto active = invoke_op<Vec>(predicate, x);
            append_selected_indices_from_mask<Vec>(
                active, input_indices, output_indices, produced, i, lanes);
        }
        for (; i < selected_count; ++i) {
            auto x = ::tsl::load<scalar_vec, false>(
                input + selected_row_offset(input_indices[i]));
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
        std::is_integral<InputIndexT>::value,
        "selection-vector input indices must use an integral element type");
    static_assert(
        std::is_integral<OutputIndexT>::value,
        "selection-vector output indices must use an integral element type");
    validate_integral_mask_layout<Vec>();

    std::size_t produced = 0;
    if constexpr (std::is_same<Vec, scalar_vec>::value) {
        for (std::size_t i = 0; i < selected_count; ++i) {
            const std::size_t row = selected_row_offset(input_indices[i]);
            auto x = ::tsl::load<scalar_vec, false>(left + row);
            auto y = ::tsl::load<scalar_vec, false>(right + row);
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
            typename Vec::register_type x{};
            typename Vec::register_type y{};
            for (std::size_t lane = 0; lane < lanes; ++lane) {
                const std::size_t row =
                    selected_row_offset(input_indices[i + lane]);
                x[lane] = left[row];
                y[lane] = right[row];
            }
            auto active = invoke_op<Vec>(predicate, x, y);
            append_selected_indices_from_mask<Vec>(
                active, input_indices, output_indices, produced, i, lanes);
        }
        for (; i < selected_count; ++i) {
            const std::size_t row = selected_row_offset(input_indices[i]);
            auto x = ::tsl::load<scalar_vec, false>(left + row);
            auto y = ::tsl::load<scalar_vec, false>(right + row);
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

template <class Vec, class Op, class T, class IndexT>
inline std::size_t count_selected_unary_loop(
    Op& predicate,
    const T* input,
    const IndexT* indices,
    std::size_t selected_count) {
    using scalar_vec = ::tsl::simd<T, ::tsl::scalar>;

    static_assert(
        std::is_integral<IndexT>::value,
        "selection-vector input indices must use an integral element type");
    validate_integral_mask_layout<Vec>();

    std::size_t produced = 0;
    if constexpr (std::is_same<Vec, scalar_vec>::value) {
        for (std::size_t i = 0; i < selected_count; ++i) {
            auto x = ::tsl::load<scalar_vec, false>(
                input + selected_row_offset(indices[i]));
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
            typename Vec::register_type x{};
            for (std::size_t lane = 0; lane < lanes; ++lane) {
                x[lane] = input[selected_row_offset(indices[i + lane])];
            }
            auto active = invoke_op<Vec>(predicate, x);
            produced += ::tsl::mask_population_count<Vec>(active);
        }
        for (; i < selected_count; ++i) {
            auto x = ::tsl::load<scalar_vec, false>(
                input + selected_row_offset(indices[i]));
            auto active = invoke_op<scalar_vec>(predicate, x);
            if (::tsl::to_integral<scalar_vec>(active) != 0) {
                produced += 1;
            }
        }
    }
    return produced;
}

template <class Vec, class Op, class T, class IndexT>
inline std::size_t count_selected_binary_loop(
    Op& predicate,
    const T* left,
    const T* right,
    const IndexT* indices,
    std::size_t selected_count) {
    using scalar_vec = ::tsl::simd<T, ::tsl::scalar>;

    static_assert(
        std::is_integral<IndexT>::value,
        "selection-vector input indices must use an integral element type");
    validate_integral_mask_layout<Vec>();

    std::size_t produced = 0;
    if constexpr (std::is_same<Vec, scalar_vec>::value) {
        for (std::size_t i = 0; i < selected_count; ++i) {
            const std::size_t row = selected_row_offset(indices[i]);
            auto x = ::tsl::load<scalar_vec, false>(left + row);
            auto y = ::tsl::load<scalar_vec, false>(right + row);
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
            typename Vec::register_type x{};
            typename Vec::register_type y{};
            for (std::size_t lane = 0; lane < lanes; ++lane) {
                const std::size_t row = selected_row_offset(indices[i + lane]);
                x[lane] = left[row];
                y[lane] = right[row];
            }
            auto active = invoke_op<Vec>(predicate, x, y);
            produced += ::tsl::mask_population_count<Vec>(active);
        }
        for (; i < selected_count; ++i) {
            const std::size_t row = selected_row_offset(indices[i]);
            auto x = ::tsl::load<scalar_vec, false>(left + row);
            auto y = ::tsl::load<scalar_vec, false>(right + row);
            auto active = invoke_op<scalar_vec>(predicate, x, y);
            if (::tsl::to_integral<scalar_vec>(active) != 0) {
                produced += 1;
            }
        }
    }
    return produced;
}

template <class Vec, class Op, class T, class IndexT>
inline void transform_selected_unary_loop(
    Op& op,
    const T* input,
    const IndexT* indices,
    T* output,
    std::size_t selected_count) {
    using scalar_vec = ::tsl::simd<T, ::tsl::scalar>;

    static_assert(
        std::is_integral<IndexT>::value,
        "selection-vector input indices must use an integral element type");

    if constexpr (std::is_same<Vec, scalar_vec>::value) {
        for (std::size_t i = 0; i < selected_count; ++i) {
            auto x = ::tsl::load<scalar_vec, false>(
                input + selected_row_offset(indices[i]));
            auto y = invoke_op<scalar_vec>(op, x);
            ::tsl::store<scalar_vec, false>(output + i, y);
        }
    } else {
        const std::size_t lanes = detail::lane_count<Vec>();
        const std::size_t chunk_count = selected_count / lanes;
        std::size_t i = 0;
        for (std::size_t chunk = 0; chunk < chunk_count; ++chunk, i += lanes) {
            (void)chunk;
            typename Vec::register_type x{};
            for (std::size_t lane = 0; lane < lanes; ++lane) {
                x[lane] = input[selected_row_offset(indices[i + lane])];
            }
            auto y = invoke_op<Vec>(op, x);
            ::tsl::store<Vec, false>(output + i, y);
        }
        for (; i < selected_count; ++i) {
            auto x = ::tsl::load<scalar_vec, false>(
                input + selected_row_offset(indices[i]));
            auto y = invoke_op<scalar_vec>(op, x);
            ::tsl::store<scalar_vec, false>(output + i, y);
        }
    }
}

template <class Vec, class Op, class T, class IndexT>
inline void transform_selected_binary_loop(
    Op& op,
    const T* left,
    const T* right,
    const IndexT* indices,
    T* output,
    std::size_t selected_count) {
    using scalar_vec = ::tsl::simd<T, ::tsl::scalar>;

    static_assert(
        std::is_integral<IndexT>::value,
        "selection-vector input indices must use an integral element type");

    if constexpr (std::is_same<Vec, scalar_vec>::value) {
        for (std::size_t i = 0; i < selected_count; ++i) {
            const std::size_t row = selected_row_offset(indices[i]);
            auto x = ::tsl::load<scalar_vec, false>(left + row);
            auto y = ::tsl::load<scalar_vec, false>(right + row);
            auto z = invoke_op<scalar_vec>(op, x, y);
            ::tsl::store<scalar_vec, false>(output + i, z);
        }
    } else {
        const std::size_t lanes = detail::lane_count<Vec>();
        const std::size_t chunk_count = selected_count / lanes;
        std::size_t i = 0;
        for (std::size_t chunk = 0; chunk < chunk_count; ++chunk, i += lanes) {
            (void)chunk;
            typename Vec::register_type x{};
            typename Vec::register_type y{};
            for (std::size_t lane = 0; lane < lanes; ++lane) {
                const std::size_t row = selected_row_offset(indices[i + lane]);
                x[lane] = left[row];
                y[lane] = right[row];
            }
            auto z = invoke_op<Vec>(op, x, y);
            ::tsl::store<Vec, false>(output + i, z);
        }
        for (; i < selected_count; ++i) {
            const std::size_t row = selected_row_offset(indices[i]);
            auto x = ::tsl::load<scalar_vec, false>(left + row);
            auto y = ::tsl::load<scalar_vec, false>(right + row);
            auto z = invoke_op<scalar_vec>(op, x, y);
            ::tsl::store<scalar_vec, false>(output + i, z);
        }
    }
}

template <class Vec, class Op, class T, class IndexT>
inline auto aggregate_selected_unary_loop(
    Op& op,
    const T* input,
    const IndexT* indices,
    std::size_t selected_count) {
    using scalar_vec = ::tsl::simd<T, ::tsl::scalar>;

    static_assert(
        std::is_integral<IndexT>::value,
        "selection-vector input indices must use an integral element type");

    if constexpr (std::is_same<Vec, scalar_vec>::value) {
        for (std::size_t i = 0; i < selected_count; ++i) {
            auto x = ::tsl::load<scalar_vec, false>(
                input + selected_row_offset(indices[i]));
            invoke_op<scalar_vec>(op, x);
        }
    } else {
        const std::size_t lanes = detail::lane_count<Vec>();
        const std::size_t chunk_count = selected_count / lanes;
        std::size_t i = 0;
        for (std::size_t chunk = 0; chunk < chunk_count; ++chunk, i += lanes) {
            (void)chunk;
            typename Vec::register_type x{};
            for (std::size_t lane = 0; lane < lanes; ++lane) {
                x[lane] = input[selected_row_offset(indices[i + lane])];
            }
            invoke_op<Vec>(op, x);
        }
        for (; i < selected_count; ++i) {
            auto x = ::tsl::load<scalar_vec, false>(
                input + selected_row_offset(indices[i]));
            invoke_op<scalar_vec>(op, x);
        }
    }
    return finalize_op(op);
}

template <class Vec, class Op, class T, class IndexT>
inline auto aggregate_selected_binary_loop(
    Op& op,
    const T* left,
    const T* right,
    const IndexT* indices,
    std::size_t selected_count) {
    using scalar_vec = ::tsl::simd<T, ::tsl::scalar>;

    static_assert(
        std::is_integral<IndexT>::value,
        "selection-vector input indices must use an integral element type");

    if constexpr (std::is_same<Vec, scalar_vec>::value) {
        for (std::size_t i = 0; i < selected_count; ++i) {
            const std::size_t row = selected_row_offset(indices[i]);
            auto x = ::tsl::load<scalar_vec, false>(left + row);
            auto y = ::tsl::load<scalar_vec, false>(right + row);
            invoke_op<scalar_vec>(op, x, y);
        }
    } else {
        const std::size_t lanes = detail::lane_count<Vec>();
        const std::size_t chunk_count = selected_count / lanes;
        std::size_t i = 0;
        for (std::size_t chunk = 0; chunk < chunk_count; ++chunk, i += lanes) {
            (void)chunk;
            typename Vec::register_type x{};
            typename Vec::register_type y{};
            for (std::size_t lane = 0; lane < lanes; ++lane) {
                const std::size_t row = selected_row_offset(indices[i + lane]);
                x[lane] = left[row];
                y[lane] = right[row];
            }
            invoke_op<Vec>(op, x, y);
        }
        for (; i < selected_count; ++i) {
            const std::size_t row = selected_row_offset(indices[i]);
            auto x = ::tsl::load<scalar_vec, false>(left + row);
            auto y = ::tsl::load<scalar_vec, false>(right + row);
            invoke_op<scalar_vec>(op, x, y);
        }
    }
    return finalize_op(op);
}

template <class Vec, class Op, class T, class IndexT>
inline void consume_selected_unary_loop(
    Op& op,
    const T* input,
    const IndexT* indices,
    std::size_t selected_count) {
    using scalar_vec = ::tsl::simd<T, ::tsl::scalar>;

    static_assert(
        std::is_integral<IndexT>::value,
        "selection-vector input indices must use an integral element type");

    if constexpr (std::is_same<Vec, scalar_vec>::value) {
        for (std::size_t i = 0; i < selected_count; ++i) {
            auto x = ::tsl::load<scalar_vec, false>(
                input + selected_row_offset(indices[i]));
            invoke_op<scalar_vec>(op, x);
        }
    } else {
        const std::size_t lanes = detail::lane_count<Vec>();
        const std::size_t chunk_count = selected_count / lanes;
        std::size_t i = 0;
        for (std::size_t chunk = 0; chunk < chunk_count; ++chunk, i += lanes) {
            (void)chunk;
            typename Vec::register_type x{};
            for (std::size_t lane = 0; lane < lanes; ++lane) {
                x[lane] = input[selected_row_offset(indices[i + lane])];
            }
            invoke_op<Vec>(op, x);
        }
        for (; i < selected_count; ++i) {
            auto x = ::tsl::load<scalar_vec, false>(
                input + selected_row_offset(indices[i]));
            invoke_op<scalar_vec>(op, x);
        }
    }
}

template <class Vec, class Op, class T, class IndexT>
inline void consume_selected_binary_loop(
    Op& op,
    const T* left,
    const T* right,
    const IndexT* indices,
    std::size_t selected_count) {
    using scalar_vec = ::tsl::simd<T, ::tsl::scalar>;

    static_assert(
        std::is_integral<IndexT>::value,
        "selection-vector input indices must use an integral element type");

    if constexpr (std::is_same<Vec, scalar_vec>::value) {
        for (std::size_t i = 0; i < selected_count; ++i) {
            const std::size_t row = selected_row_offset(indices[i]);
            auto x = ::tsl::load<scalar_vec, false>(left + row);
            auto y = ::tsl::load<scalar_vec, false>(right + row);
            invoke_op<scalar_vec>(op, x, y);
        }
    } else {
        const std::size_t lanes = detail::lane_count<Vec>();
        const std::size_t chunk_count = selected_count / lanes;
        std::size_t i = 0;
        for (std::size_t chunk = 0; chunk < chunk_count; ++chunk, i += lanes) {
            (void)chunk;
            typename Vec::register_type x{};
            typename Vec::register_type y{};
            for (std::size_t lane = 0; lane < lanes; ++lane) {
                const std::size_t row = selected_row_offset(indices[i + lane]);
                x[lane] = left[row];
                y[lane] = right[row];
            }
            invoke_op<Vec>(op, x, y);
        }
        for (; i < selected_count; ++i) {
            const std::size_t row = selected_row_offset(indices[i]);
            auto x = ::tsl::load<scalar_vec, false>(left + row);
            auto y = ::tsl::load<scalar_vec, false>(right + row);
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

}  // namespace detail

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
        detail::is_supported_alignment_policy<Alignment>::value,
        "Alignment must be tsl::algo::alignment::detect, unaligned, or assume_aligned");
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
        detail::is_supported_alignment_policy<Alignment>::value,
        "Alignment must be tsl::algo::alignment::detect, unaligned, or assume_aligned");
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

    return detail::select_selected_indices_unary_loop<vec>(
        predicate, input, input_indices, output_indices, selected_count);
}

template <
    std::size_t ParallelN,
    class Op,
    class InputRange,
    class InputIndexRange,
    class OutputIndexRange>
inline std::size_t select_selected_indices_unary(
    Op&& predicate,
    const InputRange& input,
    const InputIndexRange& input_indices,
    OutputIndexRange& output_indices) {
    return select_selected_indices_unary<ParallelN>(
        std::forward<Op>(predicate),
        detail::range_data(input),
        detail::range_data(input_indices),
        detail::range_data(output_indices),
        detail::range_size(input_indices));
}

template <
    std::size_t ParallelN,
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

    return detail::select_selected_indices_binary_loop<vec>(
        predicate, left, right, input_indices, output_indices, selected_count);
}

template <
    std::size_t ParallelN,
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
    return select_selected_indices_binary<ParallelN>(
        std::forward<Op>(predicate),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_data(input_indices),
        detail::range_data(output_indices),
        detail::range_size(input_indices));
}

template <
    std::size_t ParallelN,
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

    return detail::count_selected_unary_loop<vec>(
        predicate, input, indices, selected_count);
}

template <
    std::size_t ParallelN,
    class Op,
    class InputRange,
    class IndexRange>
inline std::size_t count_selected_unary(
    Op&& predicate,
    const InputRange& input,
    const IndexRange& indices) {
    return count_selected_unary<ParallelN>(
        std::forward<Op>(predicate),
        detail::range_data(input),
        detail::range_data(indices),
        detail::range_size(indices));
}

template <
    std::size_t ParallelN,
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

    return detail::count_selected_binary_loop<vec>(
        predicate, left, right, indices, selected_count);
}

template <
    std::size_t ParallelN,
    class Op,
    class LeftRange,
    class RightRange,
    class IndexRange>
inline std::size_t count_selected_binary(
    Op&& predicate,
    const LeftRange& left,
    const RightRange& right,
    const IndexRange& indices) {
    return count_selected_binary<ParallelN>(
        std::forward<Op>(predicate),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_data(indices),
        detail::range_size(indices));
}

template <
    std::size_t ParallelN,
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

    detail::transform_selected_unary_loop<vec>(
        op, input, indices, output, selected_count);
}

template <
    std::size_t ParallelN,
    class Op,
    class InputRange,
    class IndexRange,
    class OutputRange>
inline void transform_selected_unary(
    Op&& op,
    const InputRange& input,
    const IndexRange& indices,
    OutputRange& output) {
    transform_selected_unary<ParallelN>(
        std::forward<Op>(op),
        detail::range_data(input),
        detail::range_data(indices),
        detail::range_data(output),
        detail::range_size(indices));
}

template <
    std::size_t ParallelN,
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

    detail::transform_selected_binary_loop<vec>(
        op, left, right, indices, output, selected_count);
}

template <
    std::size_t ParallelN,
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
    transform_selected_binary<ParallelN>(
        std::forward<Op>(op),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_data(indices),
        detail::range_data(output),
        detail::range_size(indices));
}

template <
    std::size_t ParallelN,
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

    return detail::aggregate_selected_unary_loop<vec>(
        op, input, indices, selected_count);
}

template <
    std::size_t ParallelN,
    class Op,
    class InputRange,
    class IndexRange>
inline auto aggregate_selected_unary(
    Op&& op,
    const InputRange& input,
    const IndexRange& indices) {
    return aggregate_selected_unary<ParallelN>(
        std::forward<Op>(op),
        detail::range_data(input),
        detail::range_data(indices),
        detail::range_size(indices));
}

template <
    std::size_t ParallelN,
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

    return detail::aggregate_selected_binary_loop<vec>(
        op, left, right, indices, selected_count);
}

template <
    std::size_t ParallelN,
    class Op,
    class LeftRange,
    class RightRange,
    class IndexRange>
inline auto aggregate_selected_binary(
    Op&& op,
    const LeftRange& left,
    const RightRange& right,
    const IndexRange& indices) {
    return aggregate_selected_binary<ParallelN>(
        std::forward<Op>(op),
        detail::range_data(left),
        detail::range_data(right),
        detail::range_data(indices),
        detail::range_size(indices));
}

template <
    std::size_t ParallelN,
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

    detail::consume_selected_unary_loop<vec>(
        op, input, indices, selected_count);
}

template <
    std::size_t ParallelN,
    class Op,
    class InputRange,
    class IndexRange>
inline void consume_selected_unary(
    Op&& op,
    const InputRange& input,
    const IndexRange& indices) {
    consume_selected_unary<ParallelN>(
        std::forward<Op>(op),
        detail::range_data(input),
        detail::range_data(indices),
        detail::range_size(indices));
}

template <
    std::size_t ParallelN,
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

    detail::consume_selected_binary_loop<vec>(
        op, left, right, indices, selected_count);
}

template <
    std::size_t ParallelN,
    class Op,
    class LeftRange,
    class RightRange,
    class IndexRange>
inline void consume_selected_binary(
    Op&& op,
    const LeftRange& left,
    const RightRange& right,
    const IndexRange& indices) {
    consume_selected_binary<ParallelN>(
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
