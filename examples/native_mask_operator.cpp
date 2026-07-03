#include <cstddef>
#include <cstdint>
#include <memory>
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
        return tsl::blend<Vec>(active, left, sum);
    }
};

void fill_inputs(
    std::vector<std::int32_t>& left,
    std::vector<std::int32_t>& right) {
    for (std::size_t i = 0; i < left.size(); ++i) {
        left[i] = static_cast<std::int32_t>(static_cast<int>((i * 7) % 41) - 20);
        right[i] = static_cast<std::int32_t>(static_cast<int>((i * 11) % 47) - 23);
    }
}

template <std::size_t ParallelN>
bool run_native_where_case() {
    constexpr std::size_t count = 1003;
    constexpr std::int32_t preserved = -345678;
    std::vector<std::int32_t> input(count);
    std::vector<std::int32_t> threshold(count);
    std::vector<std::int32_t> output(count, preserved);
    fill_inputs(input, threshold);

    using mask_type = tsl::algo::fixed_native_mask_type<ParallelN, std::int32_t>;
    const auto mask_chunks =
        tsl::algo::native_mask_chunk_count<ParallelN, std::int32_t>(count);
    std::unique_ptr<mask_type[]> masks(new mask_type[mask_chunks]);

    const auto produced = tsl::algo::predicate_binary<
        ParallelN,
        tsl::algo::alignment::unaligned,
        tsl::algo::mask_layout::native>(
        less_than_op{},
        input.data(),
        threshold.data(),
        masks.get(),
        count);
    if (produced != mask_chunks) {
        return false;
    }

    tsl::algo::transform_where_unary<
        ParallelN,
        tsl::algo::alignment::unaligned,
        tsl::algo::mask_layout::native>(
        square_where_op{},
        input.data(),
        masks.get(),
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

template <std::size_t ParallelN>
bool run_native_masked_case() {
    constexpr std::size_t count = 1003;
    std::vector<std::int32_t> left(count);
    std::vector<std::int32_t> right(count);
    std::vector<std::int32_t> output(count, 0);
    fill_inputs(left, right);

    using mask_type = tsl::algo::fixed_native_mask_type<ParallelN, std::int32_t>;
    const auto mask_chunks =
        tsl::algo::native_mask_chunk_count<ParallelN, std::int32_t>(count);
    std::unique_ptr<mask_type[]> masks(new mask_type[mask_chunks]);

    tsl::algo::predicate_binary<
        ParallelN,
        tsl::algo::alignment::unaligned,
        tsl::algo::mask_layout::native>(
        less_than_op{},
        left.data(),
        right.data(),
        masks.get(),
        count);
    tsl::algo::transform_masked_binary<
        ParallelN,
        tsl::algo::alignment::unaligned,
        tsl::algo::mask_layout::native>(
        add_or_left_op{},
        left.data(),
        right.data(),
        masks.get(),
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

template <std::size_t ParallelN>
bool run_native_mask_cases() {
    return run_native_where_case<ParallelN>() &&
           run_native_masked_case<ParallelN>();
}

int main() {
    if (!run_native_mask_cases<1>()) {
        return 1;
    }
    if (!run_native_mask_cases<4>()) {
        return 2;
    }
    if (!run_native_mask_cases<16>()) {
        return 3;
    }
    return 0;
}
