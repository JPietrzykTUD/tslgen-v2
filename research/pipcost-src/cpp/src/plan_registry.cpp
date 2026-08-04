#include "pipcost/plan.hpp"

#include <algorithm>

namespace pipcost {

const std::vector<PlanSpec>& plan_registry() {
    static const std::vector<PlanSpec> plans = {
        {
            "batch_bitmask", "packed_bits", "batch_at_a_time", "bits", 0,
            PIPCOST_SIMD_LANES, "tsl_algorithms", "explicit_tsl", true,
            "batch", true, "", batch_bitmask,
        },
        {
            "batch_integral_mask", "integral_mask", "batch_at_a_time",
            "integral", 0, PIPCOST_SIMD_LANES, "tsl_algorithms",
            "explicit_tsl", true, "batch", true, "", batch_integral_mask,
        },
        {
            "batch_native_mask", "native_mask", "batch_at_a_time", "native",
            0, PIPCOST_SIMD_LANES, "tsl_algorithms", "explicit_tsl", true,
            "batch", true, "", batch_native_mask,
        },
        {
            "batch_positions_u32", "positions", "batch_at_a_time", "", 32,
            PIPCOST_SIMD_LANES, "tsl_algorithms", "explicit_tsl", true,
            "batch", true, "", batch_positions_u32,
        },
        {
            "full_bitmask", "packed_bits", "operator_at_a_time", "bits", 0,
            PIPCOST_SIMD_LANES, "tsl_algorithms", "explicit_tsl", true,
            "relation", true, "", full_bitmask,
        },
        {
            "full_integral_mask", "integral_mask", "operator_at_a_time",
            "integral", 0, PIPCOST_SIMD_LANES, "tsl_algorithms",
            "explicit_tsl", true, "relation", true, "", full_integral_mask,
        },
        {
            "full_native_mask", "native_mask", "operator_at_a_time", "native",
            0, PIPCOST_SIMD_LANES, "tsl_algorithms", "explicit_tsl", true,
            "relation", true, "", full_native_mask,
        },
        {
            "full_positions_u32", "positions", "operator_at_a_time", "", 32,
            PIPCOST_SIMD_LANES, "tsl_algorithms", "explicit_tsl", true,
            "relation", true, "", full_positions_u32,
        },
        {
            "fused_mask", "transient_native_mask", "fused", "native", 0,
            PIPCOST_SIMD_LANES, "tsl_primitives", "explicit_tsl", false,
            "none", true, "", fused_mask,
        },
        {
            "scalar_autovec", "none", "tuple_scan", "", 0, 1,
            "plain_cpp", "compiler", false, "none", true, "", scalar_autovec,
        },
        {
            "scalar_no_vector", "none", "tuple_scan", "", 0, 1,
            "plain_cpp", "disabled", false, "none", true, "", scalar_no_vector,
        },
    };
    return plans;
}

const PlanSpec* find_plan(std::string_view plan_id) {
    const auto& plans = plan_registry();
    const auto found = std::find_if(
        plans.begin(),
        plans.end(),
        [plan_id](const PlanSpec& plan) { return plan.plan_id == plan_id; });
    return found == plans.end() ? nullptr : &*found;
}

}  // namespace pipcost
