#include "pipcost/measurement.hpp"

#include <chrono>
#include <stdexcept>

namespace pipcost {
namespace {

volatile std::uint64_t measurement_sink = 0;

std::uint64_t mix_checksum(std::uint64_t value, const PlanResult& result) {
    const auto sum = static_cast<std::uint64_t>(result.sum);
    value ^= sum + 0x9e3779b97f4a7c15ULL + (value << 6U) + (value >> 2U);
    value ^= static_cast<std::uint64_t>(result.produced) *
        0xbf58476d1ce4e5b9ULL;
    return value;
}

}  // namespace

TimedResult measure_plan(
    const PlanSpec& plan,
    const QueryView& query,
    Scratch& scratch,
    std::size_t warmups,
    std::size_t inner_iterations) {
    if (!plan.supported || plan.function == nullptr) {
        throw std::invalid_argument("cannot measure an unsupported plan");
    }
    if (inner_iterations == 0) {
        throw std::invalid_argument("inner_iterations must be positive");
    }

    PlanResult last{0, 0};
    for (std::size_t i = 0; i < warmups; ++i) {
        last = plan.function(query, scratch);
    }

    std::uint64_t checksum = 0;
    const auto begin = std::chrono::steady_clock::now();
    for (std::size_t i = 0; i < inner_iterations; ++i) {
        last = plan.function(query, scratch);
        checksum = mix_checksum(checksum, last);
    }
    const auto end = std::chrono::steady_clock::now();
    const auto elapsed = std::chrono::duration_cast<std::chrono::nanoseconds>(
        end - begin);
    measurement_sink ^= checksum;
    return TimedResult{
        static_cast<std::uint64_t>(elapsed.count()),
        checksum,
        last,
    };
}

}  // namespace pipcost
