#include <cstddef>
#include <cstdint>
#include <vector>

#include <tsl.hpp>

struct negative_op {
    template <class Vec>
    typename Vec::mask_type operator()(typename tsl::reg_param<Vec>::type value) const {
        return tsl::less_than<Vec>(
            value,
            tsl::set1<Vec>(static_cast<typename Vec::base_type>(0)));
    }
};

struct less_than_op {
    template <class Vec>
    typename Vec::mask_type operator()(
        typename tsl::reg_param<Vec>::type left,
        typename tsl::reg_param<Vec>::type right) const {
        return tsl::less_than<Vec>(left, right);
    }
};

void fill_input(std::vector<std::int32_t>& input) {
    for (std::size_t i = 0; i < input.size(); ++i) {
        input[i] = static_cast<std::int32_t>(static_cast<int>((i * 17) % 53) - 26);
    }
}

void fill_inputs(
    std::vector<std::int32_t>& left,
    std::vector<std::int32_t>& right) {
    for (std::size_t i = 0; i < left.size(); ++i) {
        left[i] = static_cast<std::int32_t>(static_cast<int>((i * 17) % 53) - 26);
        right[i] = static_cast<std::int32_t>(static_cast<int>((i * 11) % 47) - 23);
    }
}

template <class Parallelism>
bool run_unary_selection_case() {
    constexpr std::size_t count = 1000;
    constexpr std::int32_t sentinel = 1234567;
    std::vector<std::int32_t> input(count);
    std::vector<std::int32_t> output(count, sentinel);
    fill_input(input);

    const auto produced = tsl::algo::select_unary<
        Parallelism,
        tsl::algo::alignment::unaligned>(
        negative_op{},
        input.data(),
        output.data(),
        count);

    std::size_t expected_count = 0;
    for (std::size_t i = 0; i < count; ++i) {
        if (input[i] < 0) {
            if (output[expected_count] != input[i]) {
                return false;
            }
            expected_count += 1;
        }
    }
    if (produced != expected_count) {
        return false;
    }
    for (std::size_t i = produced; i < count; ++i) {
        if (output[i] != sentinel) {
            return false;
        }
    }
    return true;
}

template <class Parallelism>
bool run_binary_selection_case() {
    constexpr std::size_t count = 1003;
    constexpr std::int32_t sentinel = 7654321;
    std::vector<std::int32_t> left(count);
    std::vector<std::int32_t> right(count);
    std::vector<std::int32_t> output(count, sentinel);
    fill_inputs(left, right);

    const auto produced = tsl::algo::select_binary<
        Parallelism,
        tsl::algo::alignment::unaligned>(
        less_than_op{},
        left.data(),
        right.data(),
        output.data(),
        count);

    std::size_t expected_count = 0;
    for (std::size_t i = 0; i < count; ++i) {
        if (left[i] < right[i]) {
            if (output[expected_count] != left[i]) {
                return false;
            }
            expected_count += 1;
        }
    }
    if (produced != expected_count) {
        return false;
    }
    for (std::size_t i = produced; i < count; ++i) {
        if (output[i] != sentinel) {
            return false;
        }
    }

    output.assign(count, sentinel);
    const auto range_produced = tsl::algo::select_binary<Parallelism>(
        less_than_op{},
        left,
        right,
        output);
    if (range_produced != expected_count) {
        return false;
    }
    expected_count = 0;
    for (std::size_t i = 0; i < count; ++i) {
        if (left[i] < right[i]) {
            if (output[expected_count] != left[i]) {
                return false;
            }
            expected_count += 1;
        }
    }
    for (std::size_t i = expected_count; i < count; ++i) {
        if (output[i] != sentinel) {
            return false;
        }
    }
    return true;
}

template <class Parallelism>
bool run_selection_cases() {
    return run_unary_selection_case<Parallelism>() &&
           run_binary_selection_case<Parallelism>();
}

int main() {
    if (!run_selection_cases<tsl::dataparallel::fixed<1>>()) {
        return 1;
    }
    if (!run_selection_cases<tsl::dataparallel::generic<4>>()) {
        return 2;
    }
    if (!run_selection_cases<tsl::dataparallel::generic<16>>()) {
        return 3;
    }
    return 0;
}
