#include <cstddef>
#include <cstdint>
#include <vector>

#include <tsl.hpp>

struct sum_op {
    std::int64_t total = 0;

    template <class Vec>
    void operator()(typename tsl::reg_param<Vec>::type value) {
        total += static_cast<std::int64_t>(tsl::hadd<Vec>(value));
    }

    std::int64_t finalize() const {
        return total;
    }
};

struct pair_sum_op {
    std::int64_t total = 0;

    template <class Vec>
    void operator()(
        typename tsl::reg_param<Vec>::type left,
        typename tsl::reg_param<Vec>::type right) {
        total += static_cast<std::int64_t>(tsl::hadd<Vec>(tsl::add<Vec>(left, right)));
    }

    std::int64_t finalize() const {
        return total;
    }
};

void fill_inputs(
    std::vector<std::int32_t>& left,
    std::vector<std::int32_t>& right) {
    for (std::size_t i = 0; i < left.size(); ++i) {
        left[i] = static_cast<std::int32_t>(static_cast<int>((i * 13) % 61) - 30);
        right[i] = static_cast<std::int32_t>(static_cast<int>((i * 17) % 67) - 33);
    }
}

std::int64_t expected_sum(const std::vector<std::int32_t>& input) {
    std::int64_t total = 0;
    for (const auto value : input) {
        total += value;
    }
    return total;
}

std::int64_t expected_pair_sum(
    const std::vector<std::int32_t>& left,
    const std::vector<std::int32_t>& right) {
    std::int64_t total = 0;
    for (std::size_t i = 0; i < left.size(); ++i) {
        total += static_cast<std::int64_t>(left[i]) + right[i];
    }
    return total;
}

template <class Parallelism>
bool run_policy_cases(
    const std::vector<std::int32_t>& left,
    const std::vector<std::int32_t>& right,
    std::int64_t expected_unary,
    std::int64_t expected_binary) {
    const auto unary_result = tsl::algo::aggregate_unary<
        Parallelism,
        tsl::algo::alignment::unaligned>(
        sum_op{},
        left.data(),
        left.size());
    if (unary_result != expected_unary) {
        return false;
    }

    const auto binary_result = tsl::algo::aggregate_binary<
        Parallelism,
        tsl::algo::alignment::unaligned>(
        pair_sum_op{},
        left.data(),
        right.data(),
        left.size());
    return binary_result == expected_binary;
}

template <class Parallelism>
bool run_reduction_primitive_facade_case() {
    using vec = tsl::dataparallel::simd_for_t<Parallelism, std::int32_t>;
    if constexpr (!vec::has_static_lane_count_v) {
        return true;
    } else {
        constexpr std::size_t lanes = vec::vector_element_count;
        std::vector<std::int32_t> left(lanes);
        std::vector<std::int32_t> right(lanes);
        fill_inputs(left, right);

        const auto values_for_sum = tsl::load<vec, false>(left.data());
        const auto sum = tsl::hadd<Parallelism, std::int32_t>(values_for_sum);
        std::int64_t expected = 0;
        for (const auto value : left) {
            expected += value;
        }
        if (static_cast<std::int64_t>(sum) != expected) {
            return false;
        }

        const auto values_for_count = tsl::load<vec, false>(left.data());
        const auto matches =
            tsl::count_matches<Parallelism, std::int32_t>(values_for_count, left[0]);
        std::int32_t expected_matches = 0;
        for (const auto value : left) {
            if (value == left[0]) {
                ++expected_matches;
            }
        }
        return matches == expected_matches;
    }
}

int main() {
    constexpr std::size_t count = 1000;
    std::vector<std::int32_t> left(count);
    std::vector<std::int32_t> right(count);
    fill_inputs(left, right);

    const auto expected_unary = expected_sum(left);
    const auto expected_binary = expected_pair_sum(left, right);

    if (!run_policy_cases<tsl::dataparallel::native>(
            left, right, expected_unary, expected_binary)) {
        return 1;
    }
    if (!run_reduction_primitive_facade_case<tsl::dataparallel::native>()) {
        return 5;
    }
    if (!run_policy_cases<tsl::dataparallel::fixed<1>>(
            left, right, expected_unary, expected_binary)) {
        return 2;
    }
    if (!run_reduction_primitive_facade_case<tsl::dataparallel::fixed<1>>()) {
        return 6;
    }
    if (!run_policy_cases<tsl::dataparallel::generic<4>>(
            left, right, expected_unary, expected_binary)) {
        return 3;
    }
    if (!run_reduction_primitive_facade_case<tsl::dataparallel::generic<4>>()) {
        return 7;
    }
    if (!run_policy_cases<tsl::dataparallel::generic<16>>(
            left, right, expected_unary, expected_binary)) {
        return 4;
    }
    if (!run_reduction_primitive_facade_case<tsl::dataparallel::generic<16>>()) {
        return 8;
    }
    return 0;
}
