#pragma once

#include <cstddef>
#include <cstdint>
#include <limits>
#include <vector>

#include <tsl.hpp>

#ifndef PIPCOST_SIMD_LANES
#define PIPCOST_SIMD_LANES 8
#endif

namespace pipcost {

using Parallelism = tsl::dataparallel::fixed<PIPCOST_SIMD_LANES>;
using NativeMask = tsl::algo::mask_storage_type<
    tsl::algo::mask_layout::native,
    Parallelism,
    std::int32_t>;
using IntegralMask = tsl::algo::mask_storage_type<
    tsl::algo::mask_layout::integral,
    Parallelism,
    std::int32_t>;
using BitMask = tsl::algo::mask_storage_type<
    tsl::algo::mask_layout::bits,
    Parallelism,
    std::int32_t>;

struct QueryView {
    const std::int32_t* a;
    const std::int32_t* b;
    const std::int32_t* c;
    std::size_t rows;
    std::size_t batch_rows;
    std::int32_t p1;
    std::int32_t p2;
};

struct PlanResult {
    std::int64_t sum;
    std::size_t produced;
};

struct Scratch {
    explicit Scratch(std::size_t rows);

    NativeMask* native_data() { return native_masks.data() + 1; }
    IntegralMask* integral_data() { return integral_masks.data() + 1; }
    BitMask* bit_data() { return bit_masks.data() + 1; }
    std::uint32_t* position_data() { return positions.data() + 1; }

    void reset_canaries();
    bool canaries_intact() const;

    std::vector<NativeMask> native_masks;
    std::vector<IntegralMask> integral_masks;
    std::vector<BitMask> bit_masks;
    std::vector<std::uint32_t> positions;
};

using PlanFunction = PlanResult (*)(const QueryView&, Scratch&);

PlanResult fused_mask(const QueryView& query, Scratch& scratch);
PlanResult scalar_autovec(const QueryView& query, Scratch& scratch);
PlanResult scalar_no_vector(const QueryView& query, Scratch& scratch);
PlanResult batch_native_mask(const QueryView& query, Scratch& scratch);
PlanResult full_native_mask(const QueryView& query, Scratch& scratch);
PlanResult batch_integral_mask(const QueryView& query, Scratch& scratch);
PlanResult full_integral_mask(const QueryView& query, Scratch& scratch);
PlanResult batch_bitmask(const QueryView& query, Scratch& scratch);
PlanResult full_bitmask(const QueryView& query, Scratch& scratch);
PlanResult batch_positions_u32(const QueryView& query, Scratch& scratch);
PlanResult full_positions_u32(const QueryView& query, Scratch& scratch);

}  // namespace pipcost
