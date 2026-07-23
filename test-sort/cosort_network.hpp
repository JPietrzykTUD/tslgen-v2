#pragma once

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <vector>

#include <tsl.hpp>


// Which side of the pivot the partition collects on the left.
enum class TslPartitionMode { LESS_THAN, EQUAL_TO };


// -----------------------------------------------------------------------------
// Co-sorting SIMD sorting network (prototype).
//
// Demonstrates that a sorting network can co-sort a runtime number of payload
// columns "on the fly". A network's exchange decision at each stage depends on
// the evolving key state, so the columns cannot be held resident in lockstep for
// a runtime column count. Instead the keys are sorted once while the per-
// comparator exchange mask is recorded; each payload column then replays those
// recorded masks with one select pair per comparator. This decouples the column
// count from register pressure -- only the keys and one column are resident at a
// time -- so the number of columns can come from a std::vector at runtime.
//
// Layout: `RegisterCount` registers of `lane_count` lanes are sorted with a
// Batcher bitonic network over the register (wire) index. Each lane column is
// sorted independently, i.e. for every lane l the sequence
//   keys[0][l] <= keys[1][l] <= ... <= keys[RegisterCount - 1][l]
// becomes ascending, and every payload column follows the keys.
// -----------------------------------------------------------------------------
template <class DataType = std::uint32_t, std::size_t RegisterCount = 16>
class TslCoSortNetwork {
  using DataSimdStyle = tsl::dataparallel::simd_for_t<tsl::dataparallel::native, DataType>;
  using register_type = typename DataSimdStyle::register_type;
  using mask_type = typename DataSimdStyle::mask_type;

  static constexpr std::size_t count_comparators() {
    std::size_t comparators = 0;
    for (std::size_t span = 2; span <= RegisterCount; span <<= 1) {
      for (std::size_t stride = span >> 1; stride > 0; stride >>= 1) {
        for (std::size_t wire = 0; wire < RegisterCount; ++wire) {
          if ((wire ^ stride) > wire) {
            ++comparators;
          }
        }
      }
    }
    return comparators;
  }

 public:
  static constexpr std::size_t lane_count = DataSimdStyle::lane_count_v;
  static constexpr std::size_t element_count = RegisterCount * lane_count;
  static constexpr std::size_t comparator_count = count_comparators();
  static_assert((RegisterCount & (RegisterCount - 1)) == 0, "RegisterCount must be a power of two");

 private:
  using key_bank = std::array<register_type, RegisterCount>;

  // Sorts the key wires. When Record is set, the exchange mask of every
  // comparator is stored in network order for later replay on payload columns.
  template <bool Record>
  static void sort_keys(key_bank & keys, mask_type * recorded) {
    std::size_t comparator = 0;
    for (std::size_t span = 2; span <= RegisterCount; span <<= 1) {
      for (std::size_t stride = span >> 1; stride > 0; stride >>= 1) {
        for (std::size_t wire = 0; wire < RegisterCount; ++wire) {
          auto const partner = wire ^ stride;
          if (partner > wire) {
            bool const ascending = (wire & span) == 0;
            auto const lo = tsl::min<DataSimdStyle>(keys[wire], keys[partner]);
            auto const hi = tsl::max<DataSimdStyle>(keys[wire], keys[partner]);
            if constexpr (Record) {
              // lanes whose payloads must swap: wire held the value that moves to
              // the partner (a > b ascending, a < b descending). Direction is
              // baked in, so replay is a direction-independent conditional swap.
              recorded[comparator++] = ascending
                ? tsl::greater_than<DataSimdStyle>(keys[wire], keys[partner])
                : tsl::less_than<DataSimdStyle>(keys[wire], keys[partner]);
            }
            keys[wire] = ascending ? lo : hi;
            keys[partner] = ascending ? hi : lo;
          }
        }
      }
    }
  }

  // Replays the recorded per-comparator exchange masks on one payload bank.
  static void replay(key_bank & pay, mask_type const * recorded) {
    std::size_t comparator = 0;
    for (std::size_t span = 2; span <= RegisterCount; span <<= 1) {
      for (std::size_t stride = span >> 1; stride > 0; stride >>= 1) {
        for (std::size_t wire = 0; wire < RegisterCount; ++wire) {
          auto const partner = wire ^ stride;
          if (partner > wire) {
            auto const exchange = recorded[comparator++];
            auto const pay_wire = tsl::select<DataSimdStyle>(exchange, pay[partner], pay[wire]);
            auto const pay_partner = tsl::select<DataSimdStyle>(exchange, pay[wire], pay[partner]);
            pay[wire] = pay_wire;
            pay[partner] = pay_partner;
          }
        }
      }
    }
  }

  static void load_bank(key_bank & bank, DataType const * ptr) {
    for (std::size_t row = 0; row < RegisterCount; ++row) {
      bank[row] = tsl::load<DataSimdStyle, false>(ptr + row * lane_count);
    }
  }

  static void store_bank(DataType * ptr, key_bank const & bank) {
    for (std::size_t row = 0; row < RegisterCount; ++row) {
      tsl::store<DataSimdStyle, false>(ptr + row * lane_count, bank[row]);
    }
  }

 public:
  // Sorts the key block and co-sorts `column_count` payload columns, each given
  // as a pointer to element_count contiguous values.
  static void run(DataType * keys_ptr, DataType * const * pays_ptr, std::size_t column_count) {
    key_bank keys;
    load_bank(keys, keys_ptr);
    if (column_count == 0) {
      sort_keys<false>(keys, nullptr);
      store_bank(keys_ptr, keys);
      return;
    }
    std::array<mask_type, comparator_count> recorded{};
    sort_keys<true>(keys, recorded.data());
    store_bank(keys_ptr, keys);
    for (std::size_t column = 0; column < column_count; ++column) {
      key_bank pay;
      load_bank(pay, pays_ptr[column]);
      replay(pay, recorded.data());
      store_bank(pays_ptr[column], pay);
    }
  }
};


// -----------------------------------------------------------------------------
// Partition swap step with per-column replay (reference).
//
// Mirrors the swap branch of TslPairWiseSwapQuickSorter::quicksort_partition:
// the key masks and counts are computed once and drive the compress/expand
// stitch, and every payload column replays the identical mask-permutations. The
// column count is a runtime argument, so the payloads can come from a std::vector.
// -----------------------------------------------------------------------------
template <class DataType = std::uint32_t,
          class SimdStyle = tsl::dataparallel::simd_for_t<tsl::dataparallel::native, DataType>>
class TslPartitionReplayStep {
  using DataSimdStyle = SimdStyle;
  using register_type = typename DataSimdStyle::register_type;
  using mask_type = typename DataSimdStyle::mask_type;
  using reg_param = typename tsl::reg_param<DataSimdStyle>::type;
  static constexpr std::size_t lane_count = DataSimdStyle::lane_count_v;

  static auto low_lane_mask(std::size_t count) {
    // Integer mask with the low `count` lanes set: take the all-lanes mask and
    // shift the surplus high lanes out. Requires to_integral(mask_true) to report
    // exactly lane_count bits, which holds as of TSL v0.2.4 (earlier releases
    // over-reported for sub-native widths, e.g. 0xff for a 4-lane vector).
    auto const full_mask = tsl::to_integral<DataSimdStyle>(tsl::mask_true<DataSimdStyle>());
    return tsl::shift_right_imask<DataSimdStyle>(full_mask, lane_count - count);
  }

  static auto lane_mask(std::size_t offset, std::size_t count) {
    return tsl::shift_left_imask<DataSimdStyle>(low_lane_mask(count), offset);
  }

  static auto expand_three_compacted_groups(
    reg_param first_vec,
    std::size_t first_count,
    reg_param second_vec,
    std::size_t second_count,
    reg_param third_vec,
    std::size_t third_count
  ) -> register_type {
    auto result = first_vec;
    result = tsl::expand<DataSimdStyle>(lane_mask(first_count, second_count), result, second_vec);
    result = tsl::expand<DataSimdStyle>(lane_mask(first_count + second_count, third_count), result, third_vec);
    return result;
  }

  // Everything the stitch needs, derived from the keys alone.
  struct stitch_plan {
    mask_type bad_l_mask;
    mask_type good_l_mask;
    mask_type bad_r_mask;
    mask_type good_r_mask;
    mask_type carry_l_select_mask;
    mask_type carry_r_select_mask;
    std::size_t swappable_lanes_count;
    std::size_t carry_l_count;
    std::size_t carry_r_count;
    std::size_t good_l_count;
    std::size_t good_r_count;
  };

  template <TslPartitionMode Mode>
  static auto plan_from_keys(reg_param key_l, reg_param key_r, reg_param pivot_vec) -> stitch_plan {
    stitch_plan plan{};
    if constexpr (Mode == TslPartitionMode::LESS_THAN) {
      // keep < pivot on the left: left lanes >= pivot and right lanes < pivot are ill-placed
      plan.bad_l_mask = tsl::greater_than_or_equal<DataSimdStyle>(key_l, pivot_vec);
      plan.bad_r_mask = tsl::less_than<DataSimdStyle>(key_r, pivot_vec);
    } else {
      // keep == pivot on the left: left lanes > pivot and right lanes == pivot are ill-placed
      plan.bad_l_mask = tsl::greater_than<DataSimdStyle>(key_l, pivot_vec);
      plan.bad_r_mask = tsl::equal<DataSimdStyle>(key_r, pivot_vec);
    }
    plan.good_l_mask = tsl::mask_binary_not<DataSimdStyle>(plan.bad_l_mask);
    plan.good_r_mask = tsl::mask_binary_not<DataSimdStyle>(plan.bad_r_mask);
    auto const bad_l_count = tsl::mask_population_count<DataSimdStyle>(plan.bad_l_mask);
    auto const bad_r_count = tsl::mask_population_count<DataSimdStyle>(plan.bad_r_mask);
    plan.swappable_lanes_count = std::min(bad_l_count, bad_r_count);
    plan.carry_l_count = bad_l_count - plan.swappable_lanes_count;
    plan.carry_r_count = bad_r_count - plan.swappable_lanes_count;
    plan.good_l_count = lane_count - bad_l_count;
    plan.good_r_count = lane_count - bad_r_count;
    auto const swap_mask = low_lane_mask(plan.swappable_lanes_count);
    plan.carry_l_select_mask = tsl::mask_binary_xor<DataSimdStyle>(swap_mask, low_lane_mask(bad_l_count));
    plan.carry_r_select_mask = tsl::mask_binary_xor<DataSimdStyle>(swap_mask, low_lane_mask(bad_r_count));
    return plan;
  }

  // Replays the plan on one column (keys or a payload) using compress/expand.
  static void apply(
    stitch_plan const & plan,
    reg_param data_l,
    reg_param data_r,
    register_type & write_l,
    register_type & write_r
  ) {
    auto const compact_bad_l   = tsl::compress<DataSimdStyle>(plan.bad_l_mask, data_l);
    auto const compact_good_l  = tsl::compress<DataSimdStyle>(plan.good_l_mask, data_l);
    auto const compact_bad_r   = tsl::compress<DataSimdStyle>(plan.bad_r_mask, data_r);
    auto const compact_good_r  = tsl::compress<DataSimdStyle>(plan.good_r_mask, data_r);
    auto const compact_carry_l = tsl::compress<DataSimdStyle>(plan.carry_l_select_mask, compact_bad_l);
    auto const compact_carry_r = tsl::compress<DataSimdStyle>(plan.carry_r_select_mask, compact_bad_r);
    write_l = expand_three_compacted_groups(
      compact_bad_r, plan.swappable_lanes_count, compact_good_l, plan.good_l_count, compact_carry_l, plan.carry_l_count
    );
    write_r = expand_three_compacted_groups(
      compact_carry_r, plan.carry_r_count, compact_bad_l, plan.swappable_lanes_count, compact_good_r, plan.good_r_count
    );
  }

 public:
  // Produces the left/right writes for the keys and `column_count` payload
  // columns, using masks and counts derived solely from the keys.
  template <TslPartitionMode Mode = TslPartitionMode::LESS_THAN>
  static void step(
    reg_param key_l,
    reg_param key_r,
    register_type const * pay_l,
    register_type const * pay_r,
    std::size_t column_count,
    reg_param pivot_vec,
    register_type & key_write_l,
    register_type & key_write_r,
    register_type * pay_write_l,
    register_type * pay_write_r
  ) {
    auto const plan = plan_from_keys<Mode>(key_l, key_r, pivot_vec);
    apply(plan, key_l, key_r, key_write_l, key_write_r);
    for (std::size_t column = 0; column < column_count; ++column) {
      apply(plan, pay_l[column], pay_r[column], pay_write_l[column], pay_write_r[column]);
    }
  }
};
