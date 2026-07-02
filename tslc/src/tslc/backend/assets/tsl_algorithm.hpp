#pragma once

#include <cstddef>
#include <cstdint>
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

namespace detail {

template <class Alignment>
struct is_supported_alignment_policy
    : std::integral_constant<
          bool,
          std::is_same<Alignment, alignment::detect>::value ||
              std::is_same<Alignment, alignment::unaligned>::value ||
              std::is_same<Alignment, alignment::assume_aligned>::value> {};

template <class...>
struct always_false : std::false_type {};

template <class Vec, class Ptr>
inline bool is_aligned_for(Ptr ptr) noexcept {
    const auto address = reinterpret_cast<std::uintptr_t>(ptr);
    return (address % Vec::vector_alignment) == 0;
}

template <class Op, class Vec, class Arg, class = void>
struct can_call_typed : std::false_type {};

template <class Op, class Vec, class Arg>
struct can_call_typed<
    Op,
    Vec,
    Arg,
    std::void_t<decltype(
        std::declval<Op&>().template operator()<Vec>(std::declval<Arg>()))>>
    : std::true_type {};

template <class Op, class Vec, class Arg, class = void>
struct can_call_tagged : std::false_type {};

template <class Op, class Vec, class Arg>
struct can_call_tagged<
    Op,
    Vec,
    Arg,
    std::void_t<decltype(std::declval<Op&>()(
        vector_tag<Vec>{},
        std::declval<Arg>()))>> : std::true_type {};

template <class Op, class Arg, class = void>
struct can_call_plain : std::false_type {};

template <class Op, class Arg>
struct can_call_plain<
    Op,
    Arg,
    std::void_t<decltype(std::declval<Op&>()(std::declval<Arg>()))>>
    : std::true_type {};

template <class Vec, class Op, class Arg>
decltype(auto) invoke_op(Op& op, Arg&& arg) {
    if constexpr (can_call_typed<Op, Vec, Arg&&>::value) {
        return op.template operator()<Vec>(std::forward<Arg>(arg));
    } else if constexpr (can_call_tagged<Op, Vec, Arg&&>::value) {
        return op(vector_tag<Vec>{}, std::forward<Arg>(arg));
    } else if constexpr (can_call_plain<Op, Arg&&>::value) {
        return op(std::forward<Arg>(arg));
    } else {
        static_assert(
            always_false<Op, Vec, Arg>::value,
            "Op must be callable as op.template operator()<Vec>(value), "
            "op(tsl::algo::vector_tag<Vec>{}, value), or op(value)");
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
    static_assert(
        Vec::has_static_vector_element_count,
        "tsl::algo::transform_unary requires a static-lane SIMD vector");
    constexpr bool input_aligned =
        std::is_same<InputAlignment, alignment::assume_aligned>::value;
    constexpr bool output_aligned =
        std::is_same<OutputAlignment, alignment::assume_aligned>::value;

    constexpr std::size_t lanes = Vec::vector_element_count;
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

}  // namespace detail

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class Op,
    class T>
inline void transform_unary(Op&& op, const T* input, T* output, std::size_t count) {
    using vec = ::tsl::inferred_simd_t<T, ParallelN>;

    static_assert(ParallelN > 0, "ParallelN must be greater than zero");
    static_assert(
        detail::is_supported_alignment_policy<Alignment>::value,
        "Alignment must be tsl::algo::alignment::detect, unaligned, or assume_aligned");
    static_assert(
        std::is_same<T, typename vec::base_type>::value,
        "tsl::inferred_simd_t<T, ParallelN> must preserve T as Vec::base_type");
    static_assert(
        vec::has_static_vector_element_count,
        "tsl::inferred_simd_t<T, ParallelN> must be a static-lane SIMD vector");
    static_assert(
        vec::vector_element_count == ParallelN,
        "tsl::inferred_simd_t<T, ParallelN> must produce exactly ParallelN lanes");

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

}  // namespace tsl::algo
