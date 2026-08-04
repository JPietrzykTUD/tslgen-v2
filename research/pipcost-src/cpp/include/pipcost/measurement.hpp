#pragma once

#include <cstddef>
#include <cstdint>

#include "pipcost/plan.hpp"

namespace pipcost {

struct TimedResult {
    std::uint64_t elapsed_ns;
    std::uint64_t checksum;
    PlanResult last_result;
};

TimedResult measure_plan(
    const PlanSpec& plan,
    const QueryView& query,
    Scratch& scratch,
    std::size_t warmups,
    std::size_t inner_iterations);

bool run_correctness_suite();

}  // namespace pipcost
