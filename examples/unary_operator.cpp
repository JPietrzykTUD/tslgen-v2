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

bool verify_square_region(
    const std::vector<std::int32_t>& input,
    const std::vector<std::int32_t>& output,
    std::size_t offset,
    std::size_t count) {
    for (std::size_t i = 0; i < count; ++i) {
        const auto index = offset + i;
        const auto expected = input[index] * input[index];
        if (output[index] != expected) {
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

bool run_square_peel_to_aligned_case() {
    constexpr std::size_t count = 1000;
    constexpr std::size_t offset = 1;
    std::vector<std::int32_t> input(count + offset);
    std::vector<std::int32_t> output(count + offset);

    fill_input(input);

    tsl::algo::transform_unary<4, tsl::algo::alignment::peel_to_aligned>(
        square_op{},
        input.data() + offset,
        output.data() + offset,
        count);

    return verify_square_region(input, output, offset, count);
}

template <std::size_t ParallelN>
bool run_square_in_place_case() {
    constexpr std::size_t count = 1000;
    std::vector<std::int32_t> values(count);
    fill_input(values);
    const auto original = values;

    tsl::algo::transform_unary<ParallelN, tsl::algo::alignment::unaligned>(
        square_op{},
        values.data(),
        values.data(),
        values.size());

    return verify_square(original, values);
}

bool run_square_mixed_alignment_cases() {
    constexpr std::size_t count = 1000;
    std::vector<std::int32_t> input(count);
    std::vector<std::int32_t> output(count);
    fill_input(input);

    tsl::algo::transform_unary<
        4,
        tsl::algo::alignment::assume_inputs_aligned>(
        square_op{},
        input.data(),
        output.data(),
        input.size());
    if (!verify_square(input, output)) {
        return false;
    }

    output.assign(count, std::int32_t{0});
    tsl::algo::transform_unary<
        4,
        tsl::algo::alignment::assume_output_aligned>(
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
    if (!run_square_peel_to_aligned_case()) {
        return 5;
    }
    if (!run_square_in_place_case<4>()) {
        return 6;
    }
    if (!run_square_mixed_alignment_cases()) {
        return 7;
    }
    return 0;
}
