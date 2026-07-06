#include <cstddef>
#include <cstdint>
#include <vector>

#include <tsl.hpp>

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
        std::size_t expected_count = 0;
        if constexpr (Vec::has_static_lane_count_v) {
            expected_count = Vec::lane_count_v;
        } else {
            expected_count = Vec::lane_count();
        }
        if ((ptr != base + offset) || (count != expected_count)) {
            metadata_ok = false;
        }
        const auto values = tsl::load<Vec, false>(ptr);
        total += static_cast<std::int64_t>(tsl::hadd<Vec>(values));
        visited += count;
    }
};

void fill_input(std::vector<std::int32_t>& input) {
    for (std::size_t i = 0; i < input.size(); ++i) {
        input[i] = static_cast<std::int32_t>(static_cast<int>((i * 29) % 73) - 36);
    }
}

std::int64_t expected_sum(const std::vector<std::int32_t>& input) {
    std::int64_t total = 0;
    for (const auto value : input) {
        total += value;
    }
    return total;
}

template <class Parallelism>
bool run_policy_case(const std::vector<std::int32_t>& input, std::int64_t expected) {
    chunk_sum_op op{input.data()};
    tsl::algo::for_each_chunk<Parallelism>(
        op,
        input.data(),
        input.size());
    return op.metadata_ok && (op.visited == input.size()) && (op.total == expected);
}

int main() {
    constexpr std::size_t count = 1003;
    std::vector<std::int32_t> input(count);
    fill_input(input);
    const auto expected = expected_sum(input);

    if (!run_policy_case<tsl::dataparallel::native>(input, expected)) {
        return 1;
    }
    if (!run_policy_case<tsl::dataparallel::fixed<1>>(input, expected)) {
        return 2;
    }
    if (!run_policy_case<tsl::dataparallel::generic<4>>(input, expected)) {
        return 3;
    }
    if (!run_policy_case<tsl::dataparallel::generic<16>>(input, expected)) {
        return 4;
    }
    return 0;
}
