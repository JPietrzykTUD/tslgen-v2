#include "pipcost/query.hpp"

#include <algorithm>
#include <type_traits>

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

struct MaskedSum {
    std::int64_t total = 0;

    template <class Vec>
    void operator()(
        typename Vec::mask_type active,
        typename tsl::reg_param<Vec>::type value) {
        const auto zero = tsl::set1<Vec>(0);
        total += static_cast<std::int64_t>(
            tsl::hadd<Vec>(tsl::select<Vec>(active, value, zero)));
    }

    std::int64_t finalize() const { return total; }
};

template <class Layout>
auto mask_data(Scratch& scratch) {
    if constexpr (std::is_same_v<Layout, tsl::algo::mask_layout::native>) {
        return scratch.native_data();
    } else if constexpr (
        std::is_same_v<Layout, tsl::algo::mask_layout::integral>) {
        return scratch.integral_data();
    } else {
        return scratch.bit_data();
    }
}

template <class Layout>
PlanResult run_materialized(
    const QueryView& query,
    Scratch& scratch,
    bool relation_wide) {
    const std::size_t batch =
        relation_wide ? std::max<std::size_t>(query.rows, 1) : query.batch_rows;
    std::int64_t total = 0;
    std::size_t offset = 0;
    while (offset < query.rows) {
        const std::size_t count = std::min(batch, query.rows - offset);
        auto* masks = mask_data<Layout>(scratch);
        tsl::algo::predicate_binary<
            Parallelism,
            tsl::algo::alignment::unaligned,
            Layout>(
            CombinedPredicate{query.p1, query.p2},
            query.a + offset,
            query.b + offset,
            masks,
            count);
        total += tsl::algo::aggregate_masked_unary<
            Parallelism,
            tsl::algo::alignment::unaligned,
            Layout>(
            MaskedSum{},
            query.c + offset,
            masks,
            count);
        offset += count;
    }
    return PlanResult{total, 0};
}

}  // namespace

#if defined(__GNUC__) || defined(__clang__)
__attribute__((noinline))
#endif
PlanResult batch_native_mask(const QueryView& query, Scratch& scratch) {
    return run_materialized<tsl::algo::mask_layout::native>(
        query, scratch, false);
}

#if defined(__GNUC__) || defined(__clang__)
__attribute__((noinline))
#endif
PlanResult full_native_mask(const QueryView& query, Scratch& scratch) {
    return run_materialized<tsl::algo::mask_layout::native>(
        query, scratch, true);
}

#if defined(__GNUC__) || defined(__clang__)
__attribute__((noinline))
#endif
PlanResult batch_integral_mask(const QueryView& query, Scratch& scratch) {
    return run_materialized<tsl::algo::mask_layout::integral>(
        query, scratch, false);
}

#if defined(__GNUC__) || defined(__clang__)
__attribute__((noinline))
#endif
PlanResult full_integral_mask(const QueryView& query, Scratch& scratch) {
    return run_materialized<tsl::algo::mask_layout::integral>(
        query, scratch, true);
}

#if defined(__GNUC__) || defined(__clang__)
__attribute__((noinline))
#endif
PlanResult batch_bitmask(const QueryView& query, Scratch& scratch) {
    return run_materialized<tsl::algo::mask_layout::bits>(
        query, scratch, false);
}

#if defined(__GNUC__) || defined(__clang__)
__attribute__((noinline))
#endif
PlanResult full_bitmask(const QueryView& query, Scratch& scratch) {
    return run_materialized<tsl::algo::mask_layout::bits>(
        query, scratch, true);
}

}  // namespace pipcost
