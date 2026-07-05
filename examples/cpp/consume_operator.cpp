#include <cstddef>
#include <cstdint>
#include <vector>

#include <tsl.hpp>

struct sum_sink {
    std::int64_t total = 0;

    template <class Vec>
    void operator()(typename tsl::reg_param<Vec>::type value) {
        total += static_cast<std::int64_t>(tsl::hadd<Vec>(value));
    }
};

struct pair_sum_sink {
    std::int64_t total = 0;

    template <class Vec>
    void operator()(
        typename tsl::reg_param<Vec>::type left,
        typename tsl::reg_param<Vec>::type right) {
        total += static_cast<std::int64_t>(tsl::hadd<Vec>(tsl::add<Vec>(left, right)));
    }
};

void fill_inputs(
    std::vector<std::int32_t>& left,
    std::vector<std::int32_t>& right) {
    for (std::size_t i = 0; i < left.size(); ++i) {
        left[i] = static_cast<std::int32_t>(static_cast<int>((i * 19) % 67) - 33);
        right[i] = static_cast<std::int32_t>(static_cast<int>((i * 23) % 71) - 35);
    }
}

std::int64_t expected_unary_sum(const std::vector<std::int32_t>& input) {
    std::int64_t total = 0;
    for (const auto value : input) {
        total += value;
    }
    return total;
}

std::int64_t expected_binary_sum(
    const std::vector<std::int32_t>& left,
    const std::vector<std::int32_t>& right) {
    std::int64_t total = 0;
    for (std::size_t i = 0; i < left.size(); ++i) {
        total += static_cast<std::int64_t>(left[i]) + right[i];
    }
    return total;
}

template <std::size_t ParallelN>
bool run_fixed_cases(
    const std::vector<std::int32_t>& left,
    const std::vector<std::int32_t>& right,
    std::int64_t expected_unary,
    std::int64_t expected_binary) {
    sum_sink unary;
    tsl::algo::consume_unary<ParallelN, tsl::algo::alignment::unaligned>(
        unary,
        left.data(),
        left.size());
    if (unary.total != expected_unary) {
        return false;
    }

    pair_sum_sink binary;
    tsl::algo::consume_binary<ParallelN, tsl::algo::alignment::unaligned>(
        binary,
        left.data(),
        right.data(),
        left.size());
    return binary.total == expected_binary;
}

bool run_native_cases(
    const std::vector<std::int32_t>& left,
    const std::vector<std::int32_t>& right,
    std::int64_t expected_unary,
    std::int64_t expected_binary) {
    sum_sink unary;
    tsl::algo::consume_unary<
        tsl::algo::parallelism::native,
        tsl::algo::alignment::unaligned>(
        unary,
        left.data(),
        left.size());
    if (unary.total != expected_unary) {
        return false;
    }

    pair_sum_sink binary;
    tsl::algo::consume_binary<
        tsl::algo::parallelism::native,
        tsl::algo::alignment::unaligned>(
        binary,
        left.data(),
        right.data(),
        left.size());
    return binary.total == expected_binary;
}

int main() {
    constexpr std::size_t count = 1000;
    std::vector<std::int32_t> left(count);
    std::vector<std::int32_t> right(count);
    fill_inputs(left, right);

    const auto expected_unary = expected_unary_sum(left);
    const auto expected_binary = expected_binary_sum(left, right);

    if (!run_native_cases(left, right, expected_unary, expected_binary)) {
        return 1;
    }
    if (!run_fixed_cases<1>(left, right, expected_unary, expected_binary)) {
        return 2;
    }
    if (!run_fixed_cases<4>(left, right, expected_unary, expected_binary)) {
        return 3;
    }
    if (!run_fixed_cases<16>(left, right, expected_unary, expected_binary)) {
        return 4;
    }
    return 0;
}
