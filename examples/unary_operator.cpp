#include <cstddef>
#include <cstdint>
#include <vector>

#include <tsl.hpp>

struct square_op {
    template <class Vec>
    typename Vec::register_type operator()(typename tsl::reg_param<Vec>::type value) const {
        return tsl::mul<Vec>(value, value);
    }
};

void fill_input(std::vector<std::int32_t>& input) {
    for (std::size_t i = 0; i < input.size(); ++i) {
        input[i] = static_cast<std::int32_t>(static_cast<int>(i % 31) - 15);
    }
}

bool verify_square(
    const std::vector<std::int32_t>& input,
    const std::vector<std::int32_t>& output) {
    for (std::size_t i = 0; i < output.size(); ++i) {
        const auto expected = input[i] * input[i];
        if (output[i] != expected) {
            return false;
        }
    }
    return true;
}

template <class Parallelism = tsl::algo::parallelism::native>
bool run_square_policy_case() {
    constexpr std::size_t count = 1000;
    std::vector<std::int32_t> input(count);
    std::vector<std::int32_t> output(count);

    fill_input(input);

    tsl::algo::transform_unary<Parallelism, tsl::algo::alignment::unaligned>(
        square_op{},
        input.data(),
        output.data(),
        input.size());

    return verify_square(input, output);
}

template <std::size_t ParallelN>
bool run_square_lane_count_case() {
    constexpr std::size_t count = 1000;
    std::vector<std::int32_t> input(count);
    std::vector<std::int32_t> output(count);

    fill_input(input);

    tsl::algo::transform_unary<ParallelN, tsl::algo::alignment::unaligned>(
        square_op{},
        input.data(),
        output.data(),
        input.size());

    return verify_square(input, output);
}

int main() {
    if (!run_square_policy_case<>()) {
        return 1;
    }
    if (!run_square_lane_count_case<1>()) {
        return 2;
    }
    if (!run_square_lane_count_case<4>()) {
        return 3;
    }
    if (!run_square_lane_count_case<128>()) {
        return 4;
    }
    return 0;
}
