#include <cstddef>
#include <cstdint>
#include <vector>

#include <tsl.hpp>

struct add_op {
    template <class Vec>
    typename Vec::register_type operator()(
        typename tsl::reg_param<Vec>::type left,
        typename tsl::reg_param<Vec>::type right) const {
        return tsl::add<Vec>(left, right);
    }
};

void fill_inputs(
    std::vector<std::int32_t>& left,
    std::vector<std::int32_t>& right) {
    for (std::size_t i = 0; i < left.size(); ++i) {
        left[i] = static_cast<std::int32_t>(static_cast<int>(i % 37) - 18);
        right[i] = static_cast<std::int32_t>(static_cast<int>((i * 3) % 29) - 14);
    }
}

bool verify_add(
    const std::vector<std::int32_t>& left,
    const std::vector<std::int32_t>& right,
    const std::vector<std::int32_t>& output) {
    for (std::size_t i = 0; i < output.size(); ++i) {
        const auto expected = left[i] + right[i];
        if (output[i] != expected) {
            return false;
        }
    }
    return true;
}

bool verify_add_region(
    const std::vector<std::int32_t>& left,
    const std::vector<std::int32_t>& right,
    const std::vector<std::int32_t>& output,
    std::size_t offset,
    std::size_t count) {
    for (std::size_t i = 0; i < count; ++i) {
        const auto index = offset + i;
        const auto expected = left[index] + right[index];
        if (output[index] != expected) {
            return false;
        }
    }
    return true;
}

template <class Parallelism = tsl::algo::parallelism::native>
bool run_add_policy_case() {
    constexpr std::size_t count = 1000;
    std::vector<std::int32_t> left(count);
    std::vector<std::int32_t> right(count);
    std::vector<std::int32_t> output(count);

    fill_inputs(left, right);

    tsl::algo::transform_binary<Parallelism, tsl::algo::alignment::unaligned>(
        add_op{},
        left.data(),
        right.data(),
        output.data(),
        left.size());

    return verify_add(left, right, output);
}

template <std::size_t ParallelN>
bool run_add_lane_count_case() {
    constexpr std::size_t count = 1000;
    std::vector<std::int32_t> left(count);
    std::vector<std::int32_t> right(count);
    std::vector<std::int32_t> output(count);

    fill_inputs(left, right);

    tsl::algo::transform_binary<ParallelN, tsl::algo::alignment::unaligned>(
        add_op{},
        left.data(),
        right.data(),
        output.data(),
        left.size());

    return verify_add(left, right, output);
}

bool run_add_peel_to_aligned_case() {
    constexpr std::size_t count = 1000;
    constexpr std::size_t offset = 1;
    std::vector<std::int32_t> left(count + offset);
    std::vector<std::int32_t> right(count + offset);
    std::vector<std::int32_t> output(count + offset);

    fill_inputs(left, right);

    tsl::algo::transform_binary<4, tsl::algo::alignment::peel_to_aligned>(
        add_op{},
        left.data() + offset,
        right.data() + offset,
        output.data() + offset,
        count);

    return verify_add_region(left, right, output, offset, count);
}

template <std::size_t ParallelN>
bool run_add_in_place_case() {
    constexpr std::size_t count = 1000;
    std::vector<std::int32_t> left(count);
    std::vector<std::int32_t> right(count);
    fill_inputs(left, right);
    const auto original_left = left;
    const auto original_right = right;

    tsl::algo::transform_binary<ParallelN, tsl::algo::alignment::unaligned>(
        add_op{},
        left.data(),
        right.data(),
        left.data(),
        left.size());
    if (!verify_add(original_left, original_right, left)) {
        return false;
    }

    left = original_left;
    right = original_right;
    tsl::algo::transform_binary<ParallelN, tsl::algo::alignment::unaligned>(
        add_op{},
        left.data(),
        right.data(),
        right.data(),
        left.size());

    return verify_add(original_left, original_right, right);
}

bool run_add_mixed_alignment_cases() {
    constexpr std::size_t count = 1000;
    std::vector<std::int32_t> left(count);
    std::vector<std::int32_t> right(count);
    std::vector<std::int32_t> output(count);
    fill_inputs(left, right);

    tsl::algo::transform_binary<
        4,
        tsl::algo::alignment::assume_inputs_aligned>(
        add_op{},
        left.data(),
        right.data(),
        output.data(),
        left.size());
    if (!verify_add(left, right, output)) {
        return false;
    }

    output.assign(count, std::int32_t{0});
    tsl::algo::transform_binary<
        4,
        tsl::algo::alignment::assume_output_aligned>(
        add_op{},
        left.data(),
        right.data(),
        output.data(),
        left.size());

    return verify_add(left, right, output);
}

int main() {
    if (!run_add_policy_case<>()) {
        return 1;
    }
    if (!run_add_lane_count_case<1>()) {
        return 2;
    }
    if (!run_add_lane_count_case<4>()) {
        return 3;
    }
    if (!run_add_lane_count_case<128>()) {
        return 4;
    }
    if (!run_add_peel_to_aligned_case()) {
        return 5;
    }
    if (!run_add_in_place_case<4>()) {
        return 6;
    }
    if (!run_add_mixed_alignment_cases()) {
        return 7;
    }
    return 0;
}
