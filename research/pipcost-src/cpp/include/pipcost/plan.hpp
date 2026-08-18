#pragma once

#include <cstddef>
#include <string_view>
#include <vector>

#include "pipcost/query.hpp"

namespace pipcost {

struct PlanSpec {
    std::string_view plan_id;
    std::string_view representation;
    std::string_view processing_mode;
    std::string_view mask_layout;
    int position_width;
    std::size_t simd_lanes;
    std::string_view implementation;
    std::string_view vectorization;
    bool materialized;
    std::string_view scope;
    bool supported;
    std::string_view skip_reason;
    PlanFunction function;
};

const std::vector<PlanSpec>& plan_registry();
const PlanSpec* find_plan(std::string_view plan_id);

}  // namespace pipcost
