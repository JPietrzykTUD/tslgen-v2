#include <cstddef>
#include <cstdint>
#include <vector>

#include <tsl.hpp>

struct less_than_op {
    template <class Vec>
    typename Vec::mask_type operator()(
        typename tsl::reg_param<Vec>::type left,
        typename tsl::reg_param<Vec>::type right) const {
        return tsl::less_than<Vec>(left, right);
    }
};

struct negative_op {
    template <class Vec>
    typename Vec::mask_type operator()(typename tsl::reg_param<Vec>::type value) const {
        return tsl::less_than<Vec>(
            value,
            tsl::set1<Vec>(static_cast<typename Vec::base_type>(0)));
    }
};

void fill_inputs(
    std::vector<std::int32_t>& left,
    std::vector<std::int32_t>& right) {
    for (std::size_t i = 0; i < left.size(); ++i) {
        left[i] = static_cast<std::int32_t>(static_cast<int>(i % 41) - 20);
        right[i] = static_cast<std::int32_t>(static_cast<int>((i * 5) % 37) - 18);
    }
}

template <class Mask>
bool mask_lane_is_set(Mask mask, std::size_t lane) {
    return ((static_cast<std::uint64_t>(mask) >> lane) & std::uint64_t{1}) != 0;
}

template <class Parallelism>
bool run_negative_case() {
    using vec = tsl::algo::vector_type<Parallelism, std::int32_t>;
    constexpr std::size_t lanes = vec::vector_element_count;
    constexpr std::size_t count = 1000;
    std::vector<std::int32_t> input(count);
    std::vector<std::int32_t> scratch(count);
    fill_inputs(input, scratch);

    using mask_type = tsl::algo::integral_mask_type<Parallelism, std::int32_t>;
    std::vector<mask_type> masks(
        tsl::algo::integral_mask_chunk_count<Parallelism, std::int32_t>(count));

    const auto produced = tsl::algo::predicate_unary<
        Parallelism,
        tsl::algo::alignment::unaligned>(
        negative_op{},
        input.data(),
        masks.data(),
        count);
    if (produced != masks.size()) {
        return false;
    }

    for (std::size_t i = 0; i < count; ++i) {
        const std::size_t chunk = i / lanes;
        const std::size_t lane = i % lanes;
        const bool expected = input[i] < 0;
        if (mask_lane_is_set(masks[chunk], lane) != expected) {
            return false;
        }
    }
    return true;
}

template <class Parallelism>
bool run_less_than_case() {
    using vec = tsl::algo::vector_type<Parallelism, std::int32_t>;
    constexpr std::size_t lanes = vec::vector_element_count;
    constexpr std::size_t count = 1000;
    std::vector<std::int32_t> left(count);
    std::vector<std::int32_t> right(count);
    fill_inputs(left, right);

    using mask_type = tsl::algo::integral_mask_type<Parallelism, std::int32_t>;
    std::vector<mask_type> masks(
        tsl::algo::integral_mask_chunk_count<Parallelism, std::int32_t>(count));

    const auto produced = tsl::algo::predicate_binary<
        Parallelism,
        tsl::algo::alignment::unaligned>(
        less_than_op{},
        left.data(),
        right.data(),
        masks.data(),
        count);
    if (produced != masks.size()) {
        return false;
    }

    for (std::size_t i = 0; i < count; ++i) {
        const std::size_t chunk = i / lanes;
        const std::size_t lane = i % lanes;
        const bool expected = left[i] < right[i];
        if (mask_lane_is_set(masks[chunk], lane) != expected) {
            return false;
        }
    }
    return true;
}

template <class Parallelism>
bool run_unequal_zero_primitive_facade_case() {
    using vec = tsl::dataparallel::simd_for_t<Parallelism, std::int32_t>;
    if constexpr (!vec::has_static_lane_count_v) {
        return true;
    } else {
        constexpr std::size_t lanes = vec::vector_element_count;
        std::vector<std::int32_t> input(lanes);
        std::vector<std::int32_t> scratch(lanes);
        fill_inputs(input, scratch);

        const auto values = tsl::load<vec, false>(input.data());
        const auto mask = tsl::unequal_zero<Parallelism, std::int32_t>(values);
        const auto bits = tsl::to_integral<vec>(mask);

        for (std::size_t lane = 0; lane < lanes; ++lane) {
            const bool expected = input[lane] != 0;
            if (mask_lane_is_set(bits, lane) != expected) {
                return false;
            }
        }
        return true;
    }
}

template <class Parallelism>
bool run_less_than_primitive_facade_case() {
    using vec = tsl::dataparallel::simd_for_t<Parallelism, std::int32_t>;
    if constexpr (!vec::has_static_lane_count_v) {
        return true;
    } else {
        constexpr std::size_t lanes = vec::vector_element_count;
        std::vector<std::int32_t> left(lanes);
        std::vector<std::int32_t> right(lanes);
        fill_inputs(left, right);

        const auto left_values = tsl::load<vec, false>(left.data());
        const auto right_values = tsl::load<vec, false>(right.data());
        const auto mask =
            tsl::less_than<Parallelism, std::int32_t>(left_values, right_values);
        const auto all = tsl::mask_true<Parallelism, std::int32_t>();
        const auto active =
            tsl::mask_binary_and<Parallelism, std::int32_t>(all, mask);
        const auto inactive =
            tsl::mask_binary_not<Parallelism, std::int32_t>(active);
        const auto all_bits = tsl::to_integral<vec>(all);
        const auto active_bits = tsl::to_integral<vec>(active);
        const auto inactive_bits = tsl::to_integral<vec>(inactive);
        const auto active_count =
            tsl::mask_population_count<Parallelism, std::int32_t>(active);
        std::size_t expected_count = 0;

        for (std::size_t lane = 0; lane < lanes; ++lane) {
            const bool expected = left[lane] < right[lane];
            if (!mask_lane_is_set(all_bits, lane)) {
                return false;
            }
            if (mask_lane_is_set(active_bits, lane) != expected) {
                return false;
            }
            if (mask_lane_is_set(inactive_bits, lane) != !expected) {
                return false;
            }
            if (expected) {
                ++expected_count;
            }
        }
        return active_count == expected_count;
    }
}

template <class Parallelism>
bool run_predicate_cases() {
    return run_negative_case<Parallelism>() &&
           run_less_than_case<Parallelism>() &&
           run_unequal_zero_primitive_facade_case<Parallelism>() &&
           run_less_than_primitive_facade_case<Parallelism>();
}

int main() {
    if (!run_predicate_cases<tsl::dataparallel::fixed<1>>()) {
        return 1;
    }
    if (!run_predicate_cases<tsl::dataparallel::generic<4>>()) {
        return 2;
    }
    if (!run_predicate_cases<tsl::dataparallel::generic<16>>()) {
        return 3;
    }
    return 0;
}
