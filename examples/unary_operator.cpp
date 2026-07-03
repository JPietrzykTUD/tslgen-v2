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

template <class Parallelism = tsl::algo::parallelism::native>
bool run_square_case() {
    constexpr std::size_t count = 1000;
    std::vector<std::int32_t> input(count);
    std::vector<std::int32_t> output(count);

    for (std::size_t i = 0; i < input.size(); ++i) {
        input[i] = static_cast<std::int32_t>(static_cast<int>(i % 31) - 15);
    }

    tsl::algo::transform_unary<Parallelism, tsl::algo::alignment::unaligned>(
        square_op{},
        input.data(),
        output.data(),
        input.size());

    for (std::size_t i = 0; i < output.size(); ++i) {
        const auto expected = input[i] * input[i];
        if (output[i] != expected) {
            return false;
        }
    }
    return true;
}

int main() {
    if (!run_square_case<>()) {
        return 1;
    }
    if (!run_square_case<tsl::algo::parallelism::fixed<4>>()) {
        return 2;
    }
    if (!run_square_case<tsl::algo::parallelism::fixed<128>>()) {
        return 3;
    }
    return 0;
}
