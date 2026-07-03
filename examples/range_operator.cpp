#include <cstddef>
#include <cstdint>
#include <vector>

#include <tsl.hpp>

struct square_op {
    template <class Vec>
    typename Vec::register_type operator()(
        typename tsl::reg_param<Vec>::type value) const {
        return tsl::mul<Vec>(value, value);
    }
};

struct add_op {
    template <class Vec>
    typename Vec::register_type operator()(
        typename tsl::reg_param<Vec>::type left,
        typename tsl::reg_param<Vec>::type right) const {
        return tsl::add<Vec>(left, right);
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

struct negative_op {
    template <class Vec>
    typename Vec::mask_type operator()(typename tsl::reg_param<Vec>::type value) const {
        return tsl::less_than<Vec>(
            value,
            tsl::set1<Vec>(static_cast<typename Vec::base_type>(0)));
    }
};

struct masked_pair_sum_op {
    std::int64_t total = 0;

    template <class Vec>
    void operator()(
        typename Vec::mask_type active,
        typename tsl::reg_param<Vec>::type left,
        typename tsl::reg_param<Vec>::type right) {
        const auto zero = tsl::set1<Vec>(static_cast<typename Vec::base_type>(0));
        const auto sum = tsl::add<Vec>(left, right);
        const auto selected = tsl::blend<Vec>(active, zero, sum);
        total += static_cast<std::int64_t>(tsl::hadd<Vec>(selected));
    }

    std::int64_t finalize() const {
        return total;
    }
};

struct masked_sum_sink {
    std::int64_t total = 0;

    template <class Vec>
    void operator()(
        typename Vec::mask_type active,
        typename tsl::reg_param<Vec>::type value) {
        const auto zero = tsl::set1<Vec>(static_cast<typename Vec::base_type>(0));
        const auto selected = tsl::blend<Vec>(active, zero, value);
        total += static_cast<std::int64_t>(tsl::hadd<Vec>(selected));
    }
};

struct chunk_sum_op {
    const std::int32_t* base = nullptr;
    std::int64_t total = 0;
    std::size_t visited = 0;
    bool metadata_ok = true;

    template <class Vec>
    void operator()(
        const std::int32_t* ptr,
        std::size_t offset,
        std::size_t count) {
        if (ptr != base + offset) {
            metadata_ok = false;
        }
        const auto values = tsl::load<Vec, false>(ptr);
        total += static_cast<std::int64_t>(tsl::hadd<Vec>(values));
        visited += count;
    }
};

void fill_inputs(
    std::vector<std::int32_t>& left,
    std::vector<std::int32_t>& right) {
    for (std::size_t i = 0; i < left.size(); ++i) {
        left[i] = static_cast<std::int32_t>(static_cast<int>((i * 31) % 79) - 39);
        right[i] = static_cast<std::int32_t>(static_cast<int>((i * 17) % 61) - 30);
    }
}

std::int64_t sum_values(const std::vector<std::int32_t>& values) {
    std::int64_t total = 0;
    for (const auto value : values) {
        total += value;
    }
    return total;
}

std::int64_t expected_masked_pair_sum(
    const std::vector<std::int32_t>& left,
    const std::vector<std::int32_t>& right) {
    std::int64_t total = 0;
    for (std::size_t i = 0; i < left.size(); ++i) {
        if (left[i] < right[i]) {
            total += static_cast<std::int64_t>(left[i]) + right[i];
        }
    }
    return total;
}

bool verify_transform_unary(
    const std::vector<std::int32_t>& input,
    const std::vector<std::int32_t>& output) {
    for (std::size_t i = 0; i < input.size(); ++i) {
        if (output[i] != input[i] * input[i]) {
            return false;
        }
    }
    return true;
}

bool verify_transform_binary(
    const std::vector<std::int32_t>& left,
    const std::vector<std::int32_t>& right,
    const std::vector<std::int32_t>& output) {
    for (std::size_t i = 0; i < left.size(); ++i) {
        if (output[i] != left[i] + right[i]) {
            return false;
        }
    }
    return true;
}

bool run_range_case() {
    constexpr std::size_t count = 1003;
    std::vector<std::int32_t> left(count);
    std::vector<std::int32_t> right(count);
    std::vector<std::int32_t> output(count);
    std::vector<std::int32_t> selected(count, 1234567);
    fill_inputs(left, right);

    tsl::algo::transform_unary<4, tsl::algo::alignment::unaligned>(
        square_op{}, left, output);
    if (!verify_transform_unary(left, output)) {
        return false;
    }

    tsl::algo::transform_binary<4, tsl::algo::alignment::unaligned>(
        add_op{}, left, right, output);
    if (!verify_transform_binary(left, right, output)) {
        return false;
    }

    using mask_type = tsl::algo::fixed_integral_mask_type<4, std::int32_t>;
    std::vector<mask_type> masks(
        tsl::algo::integral_mask_chunk_count<4, std::int32_t>(count));
    const auto mask_chunks = tsl::algo::predicate_binary<
        4,
        tsl::algo::alignment::unaligned>(
        less_than_op{},
        left,
        right,
        masks);
    if (mask_chunks != masks.size()) {
        return false;
    }

    const auto produced = tsl::algo::select_masked_unary<
        4,
        tsl::algo::alignment::unaligned>(
        negative_op{},
        left,
        masks,
        selected);
    std::size_t expected_selected = 0;
    for (std::size_t i = 0; i < count; ++i) {
        if ((left[i] < right[i]) && (left[i] < 0)) {
            if (selected[expected_selected] != left[i]) {
                return false;
            }
            expected_selected += 1;
        }
    }
    if (produced != expected_selected) {
        return false;
    }

    const auto aggregate = tsl::algo::aggregate_masked_binary<
        4,
        tsl::algo::alignment::unaligned>(
        masked_pair_sum_op{},
        left,
        right,
        masks);
    if (aggregate != expected_masked_pair_sum(left, right)) {
        return false;
    }

    masked_sum_sink sink;
    tsl::algo::consume_masked_unary<4, tsl::algo::alignment::unaligned>(
        sink,
        left,
        masks);

    std::int64_t expected_sink = 0;
    for (std::size_t i = 0; i < count; ++i) {
        if (left[i] < right[i]) {
            expected_sink += left[i];
        }
    }
    if (sink.total != expected_sink) {
        return false;
    }

    chunk_sum_op chunk_sum{left.data()};
    tsl::algo::for_each_chunk<4>(chunk_sum, left);
    return chunk_sum.metadata_ok &&
           (chunk_sum.visited == left.size()) &&
           (chunk_sum.total == sum_values(left));
}

int main() {
    return run_range_case() ? 0 : 1;
}
