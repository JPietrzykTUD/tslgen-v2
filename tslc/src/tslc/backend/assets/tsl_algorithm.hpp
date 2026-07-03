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

template <class...>
struct always_false : std::false_type {};

template <class Vec>
inline std::size_t lane_count() noexcept {
    if constexpr (Vec::has_static_lane_count_v) {
        return Vec::lane_count_v;
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

template <class Vec, class Ptr>
inline bool is_aligned_for(Ptr ptr) noexcept {
    const auto address = reinterpret_cast<std::uintptr_t>(ptr);
    return (address % Vec::simd_register_alignment_v) == 0;
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

}  // namespace detail

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
    static_assert(
        std::is_same<T, typename vec::base_type>::value,
        "selected SIMD vector must preserve T as Vec::base_type");
    if constexpr (!std::is_same<Parallelism, parallelism::native>::value) {
        static_assert(
            vec::has_static_lane_count_v,
            "tsl::algo::parallelism::fixed<N> requires a static-lane SIMD vector");
        static_assert(
            vec::lane_count_v == Parallelism::lanes,
            "tsl::algo::parallelism::fixed<N> must produce exactly N lanes");
    }

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
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class Op,
    class T>
inline void transform_unary(Op&& op, const T* input, T* output, std::size_t count) {
    transform_unary<parallelism::fixed<ParallelN>, Alignment>(
        std::forward<Op>(op), input, output, count);
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
    static_assert(
        std::is_same<T, typename vec::base_type>::value,
        "selected SIMD vector must preserve T as Vec::base_type");
    if constexpr (!std::is_same<Parallelism, parallelism::native>::value) {
        static_assert(
            vec::has_static_lane_count_v,
            "tsl::algo::parallelism::fixed<N> requires a static-lane SIMD vector");
        static_assert(
            vec::lane_count_v == Parallelism::lanes,
            "tsl::algo::parallelism::fixed<N> must produce exactly N lanes");
    }

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

}  // namespace tsl::algo
