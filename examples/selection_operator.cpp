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

void fill_input(std::vector<std::int32_t>& input) {
    for (std::size_t i = 0; i < input.size(); ++i) {
        input[i] = static_cast<std::int32_t>(static_cast<int>((i * 17) % 53) - 26);
    }
}

template <std::size_t ParallelN>
bool run_selection_case() {
    constexpr std::size_t count = 1000;
    constexpr std::int32_t sentinel = 1234567;
    std::vector<std::int32_t> input(count);
    std::vector<std::int32_t> output(count, sentinel);
    fill_input(input);

    const auto produced = tsl::algo::select_unary<
        ParallelN,
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

int main() {
    if (!run_selection_case<1>()) {
        return 1;
    }
    if (!run_selection_case<4>()) {
        return 2;
    }
    if (!run_selection_case<16>()) {
        return 3;
    }
    return 0;
}
