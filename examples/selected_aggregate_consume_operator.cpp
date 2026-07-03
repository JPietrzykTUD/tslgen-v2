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
        left[i] = static_cast<std::int32_t>(static_cast<int>((i * 19) % 67) - 33);
        right[i] = static_cast<std::int32_t>(static_cast<int>((i * 23) % 71) - 35);
    }
}

std::vector<std::uint32_t> make_selection(std::size_t count) {
    std::vector<std::uint32_t> indices;
    for (std::size_t i = count; i > 0; --i) {
        const std::size_t row = i - 1;
        if ((row % 4) == 0 || (row % 7) == 0) {
            indices.push_back(static_cast<std::uint32_t>(row));
        }
    }
    return indices;
}

std::int64_t expected_unary_sum(
    const std::vector<std::int32_t>& input,
    const std::vector<std::uint32_t>& indices) {
    std::int64_t total = 0;
    for (const auto row : indices) {
        total += input[row];
    }
    return total;
}

std::int64_t expected_binary_sum(
    const std::vector<std::int32_t>& left,
    const std::vector<std::int32_t>& right,
    const std::vector<std::uint32_t>& indices) {
    std::int64_t total = 0;
    for (const auto row : indices) {
        total += static_cast<std::int64_t>(left[row]) + right[row];
    }
    return total;
}

template <std::size_t ParallelN>
bool run_selected_aggregate_cases(
    const std::vector<std::int32_t>& left,
    const std::vector<std::int32_t>& right,
    const std::vector<std::uint32_t>& indices,
    std::int64_t expected_unary,
    std::int64_t expected_binary) {
    const auto unary_result = tsl::algo::aggregate_selected_unary<ParallelN>(
        sum_op{},
        left.data(),
        indices.data(),
        indices.size());
    if (unary_result != expected_unary) {
        return false;
    }

    const auto binary_result = tsl::algo::aggregate_selected_binary<ParallelN>(
        pair_sum_op{},
        left,
        right,
        indices);
    return binary_result == expected_binary;
}

template <std::size_t ParallelN>
bool run_selected_consume_cases(
    const std::vector<std::int32_t>& left,
    const std::vector<std::int32_t>& right,
    const std::vector<std::uint32_t>& indices,
    std::int64_t expected_unary,
    std::int64_t expected_binary) {
    sum_op unary;
    tsl::algo::consume_selected_unary<ParallelN>(
        unary,
        left,
        indices);
    if (unary.total != expected_unary) {
        return false;
    }

    pair_sum_op binary;
    tsl::algo::consume_selected_binary<ParallelN>(
        binary,
        left.data(),
        right.data(),
        indices.data(),
        indices.size());
    return binary.total == expected_binary;
}

template <std::size_t ParallelN>
bool run_selected_sink_cases(
    const std::vector<std::int32_t>& left,
    const std::vector<std::int32_t>& right,
    const std::vector<std::uint32_t>& indices,
    std::int64_t expected_unary,
    std::int64_t expected_binary) {
    return run_selected_aggregate_cases<ParallelN>(
               left,
               right,
               indices,
               expected_unary,
               expected_binary) &&
           run_selected_consume_cases<ParallelN>(
               left,
               right,
               indices,
               expected_unary,
               expected_binary);
}

int main() {
    constexpr std::size_t count = 1003;
    std::vector<std::int32_t> left(count);
    std::vector<std::int32_t> right(count);
    fill_inputs(left, right);
    const auto indices = make_selection(count);
    const auto expected_unary = expected_unary_sum(left, indices);
    const auto expected_binary = expected_binary_sum(left, right, indices);

    if (!run_selected_sink_cases<1>(
            left, right, indices, expected_unary, expected_binary)) {
        return 1;
    }
    if (!run_selected_sink_cases<4>(
            left, right, indices, expected_unary, expected_binary)) {
        return 2;
    }
    if (!run_selected_sink_cases<16>(
            left, right, indices, expected_unary, expected_binary)) {
        return 3;
    }
    return 0;
}
