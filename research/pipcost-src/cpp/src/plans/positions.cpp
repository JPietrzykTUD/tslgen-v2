#include "pipcost/query.hpp"

#include <algorithm>
#include <limits>

namespace pipcost {
namespace {

struct CombinedPredicate {
    std::int32_t p1;
    std::int32_t p2;

    template <class Vec>
    typename Vec::mask_type operator()(
        typename tsl::reg_param<Vec>::type a,
        typename tsl::reg_param<Vec>::type b) const {
        const auto first = tsl::less_than<Vec>(a, tsl::set1<Vec>(p1));
        const auto second = tsl::less_than<Vec>(tsl::set1<Vec>(p2), b);
        return tsl::mask_binary_and<Vec>(first, second);
    }
};

struct Sum {
    std::int64_t total = 0;

    template <class Vec>
    void operator()(typename tsl::reg_param<Vec>::type value) {
        total += static_cast<std::int64_t>(tsl::hadd<Vec>(value));
    }

    std::int64_t finalize() const { return total; }
};

PlanResult run_positions(
    const QueryView& query,
    Scratch& scratch,
    bool relation_wide) {
    if (query.rows > std::numeric_limits<std::uint32_t>::max()) {
        return PlanResult{0, 0};
    }
    const std::size_t batch =
        relation_wide ? std::max<std::size_t>(query.rows, 1) : query.batch_rows;
    std::int64_t total = 0;
    std::size_t produced_total = 0;
    std::size_t offset = 0;
    while (offset < query.rows) {
        const std::size_t count = std::min(batch, query.rows - offset);
        auto* positions = scratch.position_data();
        const auto produced = tsl::algo::select_indices_binary<
            Parallelism,
            tsl::algo::alignment::unaligned>(
            CombinedPredicate{query.p1, query.p2},
            query.a + offset,
            query.b + offset,
            positions,
            count);
        for (std::size_t i = 0; i < produced; ++i) {
            positions[i] += static_cast<std::uint32_t>(offset);
        }
        total += tsl::algo::aggregate_selected_unary<PIPCOST_SIMD_LANES>(
            Sum{},
            query.c,
            positions,
            produced);
        produced_total += produced;
        offset += count;
    }
    return PlanResult{total, produced_total};
}

}  // namespace

#if defined(__GNUC__) || defined(__clang__)
__attribute__((noinline))
#endif
PlanResult batch_positions_u32(const QueryView& query, Scratch& scratch) {
    return run_positions(query, scratch, false);
}

#if defined(__GNUC__) || defined(__clang__)
__attribute__((noinline))
#endif
PlanResult full_positions_u32(const QueryView& query, Scratch& scratch) {
    return run_positions(query, scratch, true);
}

}  // namespace pipcost
