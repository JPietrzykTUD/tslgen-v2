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

struct square_or_original_op {
    template <class Vec>
    typename Vec::register_type operator()(
        typename Vec::mask_type active,
        typename tsl::reg_param<Vec>::type value) const {
        const auto squared = tsl::mul<Vec>(value, value);
        return tsl::blend<Vec>(active, value, squared);
    }
};

struct add_or_left_op {
    template <class Vec>
    typename Vec::register_type operator()(
        typename Vec::mask_type active,
        typename tsl::reg_param<Vec>::type left,
        typename tsl::reg_param<Vec>::type right) const {
        const auto sum = tsl::add<Vec>(left, right);
        return tsl::blend<Vec>(active, left, sum);
    }
};

void fill_inputs(
    std::vector<std::int32_t>& left,
    std::vector<std::int32_t>& right) {
    for (std::size_t i = 0; i < left.size(); ++i) {
        left[i] = static_cast<std::int32_t>(static_cast<int>(i % 29) - 14);
        right[i] = static_cast<std::int32_t>(static_cast<int>((i * 11) % 47) - 23);
    }
}

template <std::size_t ParallelN>
bool run_masked_unary_case() {
    constexpr std::size_t count = 1000;
    constexpr std::int32_t sentinel = -777777;
    std::vector<std::int32_t> input(count);
    std::vector<std::int32_t> threshold(count);
    std::vector<std::int32_t> output(count, sentinel);
    fill_inputs(input, threshold);

    using mask_type = tsl::algo::fixed_integral_mask_type<ParallelN, std::int32_t>;
    std::vector<mask_type> masks(
        tsl::algo::integral_mask_chunk_count<ParallelN, std::int32_t>(count));

    tsl::algo::predicate_binary<ParallelN, tsl::algo::alignment::unaligned>(
        less_than_op{},
        input.data(),
        threshold.data(),
        masks.data(),
        count);
    tsl::algo::transform_masked_unary<ParallelN, tsl::algo::alignment::unaligned>(
        square_or_original_op{},
        input.data(),
        masks.data(),
        output.data(),
        count);

    for (std::size_t i = 0; i < count; ++i) {
        const bool active = input[i] < threshold[i];
        const auto expected = active ? input[i] * input[i] : input[i];
        if (output[i] != expected) {
            return false;
        }
    }
    return true;
}

template <std::size_t ParallelN>
bool run_masked_binary_case() {
    constexpr std::size_t count = 1000;
    constexpr std::int32_t sentinel = -888888;
    std::vector<std::int32_t> left(count);
    std::vector<std::int32_t> right(count);
    std::vector<std::int32_t> output(count, sentinel);
    fill_inputs(left, right);

    using mask_type = tsl::algo::fixed_integral_mask_type<ParallelN, std::int32_t>;
    std::vector<mask_type> masks(
        tsl::algo::integral_mask_chunk_count<ParallelN, std::int32_t>(count));

    tsl::algo::predicate_binary<ParallelN, tsl::algo::alignment::unaligned>(
        less_than_op{},
        left.data(),
        right.data(),
        masks.data(),
        count);
    tsl::algo::transform_masked_binary<ParallelN, tsl::algo::alignment::unaligned>(
        add_or_left_op{},
        left.data(),
        right.data(),
        masks.data(),
        output.data(),
        count);

    for (std::size_t i = 0; i < count; ++i) {
        const bool active = left[i] < right[i];
        const auto expected = active ? left[i] + right[i] : left[i];
        if (output[i] != expected) {
            return false;
        }
    }
    return true;
}

template <std::size_t ParallelN>
bool run_masked_cases() {
    return run_masked_unary_case<ParallelN>() &&
           run_masked_binary_case<ParallelN>();
}

int main() {
    if (!run_masked_cases<1>()) {
        return 1;
    }
    if (!run_masked_cases<4>()) {
        return 2;
    }
    if (!run_masked_cases<16>()) {
        return 3;
    }
    return 0;
}
