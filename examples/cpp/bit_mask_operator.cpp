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

struct add_or_left_op {
    template <class Vec>
    typename Vec::register_type operator()(
        typename Vec::mask_type active,
        typename tsl::reg_param<Vec>::type left,
        typename tsl::reg_param<Vec>::type right) const {
        const auto sum = tsl::add<Vec>(left, right);
        return tsl::select<Vec>(active, sum, left);
    }
};

void fill_inputs(
    std::vector<std::int32_t>& left,
    std::vector<std::int32_t>& right) {
    for (std::size_t i = 0; i < left.size(); ++i) {
        left[i] = static_cast<std::int32_t>(static_cast<int>((i * 3) % 37) - 18);
        right[i] = static_cast<std::int32_t>(static_cast<int>((i * 17) % 53) - 26);
    }
}

bool packed_mask_active(const std::vector<std::uint8_t>& masks, std::size_t row) {
    return ((masks[row / 8] >> (row % 8)) & std::uint8_t{1}) != 0;
}

template <class Parallelism>
bool run_bit_where_case() {
    constexpr std::size_t count = 1003;
    constexpr std::int32_t preserved = -567890;
    std::vector<std::int32_t> input(count);
    std::vector<std::int32_t> threshold(count);
    std::vector<std::int32_t> output(count, preserved);
    fill_inputs(input, threshold);

    using mask_type = tsl::algo::bit_mask_type<Parallelism, std::int32_t>;
    std::vector<mask_type> masks(
        tsl::algo::bit_mask_count<Parallelism, std::int32_t>(count),
        std::uint8_t{0xFF});

    const auto produced = tsl::algo::predicate_binary<
        Parallelism,
        tsl::algo::alignment::unaligned,
        tsl::algo::mask_layout::bits>(
        less_than_op{},
        input.data(),
        threshold.data(),
        masks.data(),
        count);
    if (produced != masks.size()) {
        return false;
    }

    for (std::size_t i = 0; i < count; ++i) {
        const bool expected = input[i] < threshold[i];
        if (packed_mask_active(masks, i) != expected) {
            return false;
        }
    }
    for (std::size_t i = count; i < masks.size() * 8; ++i) {
        if (packed_mask_active(masks, i)) {
            return false;
        }
    }

    tsl::algo::transform_where_unary<
        Parallelism,
        tsl::algo::alignment::unaligned,
        tsl::algo::mask_layout::bits>(
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

template <class Parallelism>
bool run_bit_masked_case() {
    constexpr std::size_t count = 1003;
    std::vector<std::int32_t> left(count);
    std::vector<std::int32_t> right(count);
    std::vector<std::int32_t> output(count, 0);
    fill_inputs(left, right);

    using mask_type = tsl::algo::bit_mask_type<Parallelism, std::int32_t>;
    std::vector<mask_type> masks(
        tsl::algo::bit_mask_count<Parallelism, std::int32_t>(count));

    tsl::algo::predicate_binary<
        Parallelism,
        tsl::algo::alignment::unaligned,
        tsl::algo::mask_layout::bits>(
        less_than_op{},
        left.data(),
        right.data(),
        masks.data(),
        count);
    tsl::algo::transform_masked_binary<
        Parallelism,
        tsl::algo::alignment::unaligned,
        tsl::algo::mask_layout::bits>(
        add_or_left_op{},
        left.data(),
        right.data(),
        masks.data(),
        output.data(),
        count);

    for (std::size_t i = 0; i < count; ++i) {
        const bool active = left[i] < right[i];
        const auto expected = active ? left[i] + right[i] : left[i];
        if (output[i] != expected) {
            return false;
        }
    }
    return true;
}

template <class Parallelism>
bool run_bit_mask_cases() {
    return run_bit_where_case<Parallelism>() &&
           run_bit_masked_case<Parallelism>();
}

int main() {
    if (!run_bit_mask_cases<tsl::dataparallel::fixed<1>>()) {
        return 1;
    }
    if (!run_bit_mask_cases<tsl::dataparallel::generic<4>>()) {
        return 2;
    }
    if (!run_bit_mask_cases<tsl::dataparallel::generic<16>>()) {
        return 3;
    }
    return 0;
}
