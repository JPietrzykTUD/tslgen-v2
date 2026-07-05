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

struct square_where_op {
    template <class Vec>
    typename Vec::register_type operator()(
        typename Vec::mask_type active,
        typename tsl::reg_param<Vec>::type value) const {
        (void)active;
        return tsl::mul<Vec>(value, value);
    }
};

struct add_where_op {
    template <class Vec>
    typename Vec::register_type operator()(
        typename Vec::mask_type active,
        typename tsl::reg_param<Vec>::type left,
        typename tsl::reg_param<Vec>::type right) const {
        (void)active;
        return tsl::add<Vec>(left, right);
    }
};

void fill_inputs(
    std::vector<std::int32_t>& left,
    std::vector<std::int32_t>& right) {
    for (std::size_t i = 0; i < left.size(); ++i) {
        left[i] = static_cast<std::int32_t>(static_cast<int>(i % 31) - 15);
        right[i] = static_cast<std::int32_t>(static_cast<int>((i * 7) % 43) - 21);
    }
}

template <std::size_t ParallelN>
bool run_where_unary_case() {
    constexpr std::size_t count = 1000;
    constexpr std::int32_t preserved = -123456;
    std::vector<std::int32_t> input(count);
    std::vector<std::int32_t> threshold(count);
    std::vector<std::int32_t> output(count, preserved);
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
    tsl::algo::transform_where_unary<ParallelN, tsl::algo::alignment::unaligned>(
        square_where_op{},
        input.data(),
        masks.data(),
        output.data(),
        count);

    for (std::size_t i = 0; i < count; ++i) {
        const bool active = input[i] < threshold[i];
        const auto expected = active ? input[i] * input[i] : preserved;
        if (output[i] != expected) {
            return false;
        }
    }
    return true;
}

template <std::size_t ParallelN>
bool run_where_binary_case() {
    constexpr std::size_t count = 1000;
    constexpr std::int32_t preserved = -654321;
    std::vector<std::int32_t> left(count);
    std::vector<std::int32_t> right(count);
    std::vector<std::int32_t> output(count, preserved);
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
    tsl::algo::transform_where_binary<ParallelN, tsl::algo::alignment::unaligned>(
        add_where_op{},
        left.data(),
        right.data(),
        masks.data(),
        output.data(),
        count);

    for (std::size_t i = 0; i < count; ++i) {
        const bool active = left[i] < right[i];
        const auto expected = active ? left[i] + right[i] : preserved;
        if (output[i] != expected) {
            return false;
        }
    }
    return true;
}

template <std::size_t ParallelN>
bool run_where_cases() {
    return run_where_unary_case<ParallelN>() && run_where_binary_case<ParallelN>();
}

int main() {
    if (!run_where_cases<1>()) {
        return 1;
    }
    if (!run_where_cases<4>()) {
        return 2;
    }
    if (!run_where_cases<16>()) {
        return 3;
    }
    return 0;
}
