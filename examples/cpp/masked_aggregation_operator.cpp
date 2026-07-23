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

struct masked_sum_op {
    std::int64_t total = 0;

    template <class Vec>
    void operator()(
        typename Vec::mask_type active,
        typename tsl::reg_param<Vec>::type value) {
        const auto zero = tsl::set1<Vec>(static_cast<typename Vec::base_type>(0));
        const auto selected = tsl::select<Vec>(active, value, zero);
        total += static_cast<std::int64_t>(tsl::hadd<Vec>(selected));
    }

    std::int64_t finalize() const {
        return total;
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
        const auto selected = tsl::select<Vec>(active, sum, zero);
        total += static_cast<std::int64_t>(tsl::hadd<Vec>(selected));
    }

    std::int64_t finalize() const {
        return total;
    }
};

void fill_inputs(
    std::vector<std::int32_t>& left,
    std::vector<std::int32_t>& right) {
    for (std::size_t i = 0; i < left.size(); ++i) {
        left[i] = static_cast<std::int32_t>(static_cast<int>((i * 7) % 41) - 20);
        right[i] = static_cast<std::int32_t>(static_cast<int>((i * 13) % 59) - 29);
    }
}

std::int64_t expected_masked_sum(
    const std::vector<std::int32_t>& left,
    const std::vector<std::int32_t>& right) {
    std::int64_t total = 0;
    for (std::size_t i = 0; i < left.size(); ++i) {
        if (left[i] < right[i]) {
            total += left[i];
        }
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

template <class MaskLayout, class Parallelism>
bool run_masked_aggregation_cases() {
    constexpr std::size_t count = 1003;
    std::vector<std::int32_t> left(count);
    std::vector<std::int32_t> right(count);
    fill_inputs(left, right);

    using mask_type =
        tsl::algo::mask_storage_type<MaskLayout, Parallelism, std::int32_t>;
    const auto mask_count =
        tsl::algo::mask_chunk_count<MaskLayout, Parallelism, std::int32_t>(count);
    std::unique_ptr<mask_type[]> masks(new mask_type[mask_count]);

    const auto produced = tsl::algo::predicate_binary<
        Parallelism,
        tsl::algo::alignment::unaligned,
        MaskLayout>(
        less_than_op{},
        left.data(),
        right.data(),
        masks.get(),
        count);
    if (produced != mask_count) {
        return false;
    }

    const auto unary_result = tsl::algo::aggregate_masked_unary<
        Parallelism,
        tsl::algo::alignment::unaligned,
        MaskLayout>(
        masked_sum_op{},
        left.data(),
        masks.get(),
        count);
    if (unary_result != expected_masked_sum(left, right)) {
        return false;
    }

    const auto binary_result = tsl::algo::aggregate_masked_binary<
        Parallelism,
        tsl::algo::alignment::unaligned,
        MaskLayout>(
        masked_pair_sum_op{},
        left.data(),
        right.data(),
        masks.get(),
        count);
    return binary_result == expected_masked_pair_sum(left, right);
}

template <class Parallelism>
bool run_layout_cases() {
    return run_masked_aggregation_cases<
               tsl::algo::mask_layout::integral,
               Parallelism>() &&
           run_masked_aggregation_cases<
               tsl::algo::mask_layout::native,
               Parallelism>() &&
           run_masked_aggregation_cases<
               tsl::algo::mask_layout::bytes,
               Parallelism>() &&
           run_masked_aggregation_cases<
               tsl::algo::mask_layout::bits,
               Parallelism>();
}

int main() {
    if (!run_layout_cases<tsl::dataparallel::fixed<1>>()) {
        return 1;
    }
    if (!run_layout_cases<tsl::dataparallel::generic<4>>()) {
        return 2;
    }
    if (!run_layout_cases<tsl::dataparallel::generic<16>>()) {
        return 3;
    }
    return 0;
}
