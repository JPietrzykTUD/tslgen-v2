#include "pipcost/query.hpp"

#include <algorithm>

namespace pipcost {

#if defined(__GNUC__) || defined(__clang__)
__attribute__((noinline))
#endif
PlanResult fused_mask(const QueryView& query, Scratch&) {
    using Vec = tsl::dataparallel::simd_for_t<Parallelism, std::int32_t>;
    static_assert(Vec::has_static_lane_count_v, "PIPCost requires fixed lanes");
    static_assert(
        Vec::vector_element_count == PIPCOST_SIMD_LANES,
        "generated vector does not match PIPCOST_SIMD_LANES");

    const auto p1 = tsl::set1<Vec>(query.p1);
    const auto p2 = tsl::set1<Vec>(query.p2);
    const auto zero = tsl::set1<Vec>(0);
    std::int64_t total = 0;
    std::size_t row = 0;
    for (; row + PIPCOST_SIMD_LANES <= query.rows;
         row += PIPCOST_SIMD_LANES) {
        const auto a = tsl::load<Vec, false>(query.a + row);
        const auto b = tsl::load<Vec, false>(query.b + row);
        const auto c = tsl::load<Vec, false>(query.c + row);
        const auto first = tsl::less_than<Vec>(a, p1);
        const auto second = tsl::less_than<Vec>(p2, b);
        const auto active = tsl::mask_binary_and<Vec>(first, second);
        total += static_cast<std::int64_t>(
            tsl::hadd<Vec>(tsl::select<Vec>(active, c, zero)));
    }
    for (; row < query.rows; ++row) {
        if (query.a[row] < query.p1 && query.b[row] > query.p2) {
            total += static_cast<std::int64_t>(query.c[row]);
        }
    }
    return PlanResult{total, 0};
}

}  // namespace pipcost
