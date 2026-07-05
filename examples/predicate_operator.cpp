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

template <std::size_t ParallelN>
bool run_negative_case() {
    constexpr std::size_t count = 1000;
    std::vector<std::int32_t> input(count);
    std::vector<std::int32_t> scratch(count);
    fill_inputs(input, scratch);

    using mask_type = tsl::algo::fixed_integral_mask_type<ParallelN, std::int32_t>;
    std::vector<mask_type> masks(
        tsl::algo::integral_mask_chunk_count<ParallelN, std::int32_t>(count));

    const auto produced = tsl::algo::predicate_unary<
        ParallelN,
        tsl::algo::alignment::unaligned>(
        negative_op{},
        input.data(),
        masks.data(),
        count);
    if (produced != masks.size()) {
        return false;
    }

    for (std::size_t i = 0; i < count; ++i) {
        const std::size_t chunk = i / ParallelN;
        const std::size_t lane = i % ParallelN;
        const bool expected = input[i] < 0;
        if (mask_lane_is_set(masks[chunk], lane) != expected) {
            return false;
        }
    }
    return true;
}

template <std::size_t ParallelN>
bool run_less_than_case() {
    constexpr std::size_t count = 1000;
    std::vector<std::int32_t> left(count);
    std::vector<std::int32_t> right(count);
    fill_inputs(left, right);

    using mask_type = tsl::algo::fixed_integral_mask_type<ParallelN, std::int32_t>;
    std::vector<mask_type> masks(
        tsl::algo::integral_mask_chunk_count<ParallelN, std::int32_t>(count));

    const auto produced = tsl::algo::predicate_binary<
        ParallelN,
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
        const std::size_t chunk = i / ParallelN;
        const std::size_t lane = i % ParallelN;
        const bool expected = left[i] < right[i];
        if (mask_lane_is_set(masks[chunk], lane) != expected) {
            return false;
        }
    }
    return true;
}

template <std::size_t ParallelN>
bool run_predicate_cases() {
    return run_negative_case<ParallelN>() && run_less_than_case<ParallelN>();
}

int main() {
    if (!run_predicate_cases<1>()) {
        return 1;
    }
    if (!run_predicate_cases<4>()) {
        return 2;
    }
    if (!run_predicate_cases<16>()) {
        return 3;
    }
    return 0;
}
