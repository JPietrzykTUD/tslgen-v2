#pragma once

#include <algorithm>
#include <array>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <type_traits>
#include <utility>

#include <tsl.hpp>

#include "common/instrumentation.hpp"
#include "sorting/primitives/cosort_bitonic_leaf.hpp"
#include "sorting/primitives/cosort_network.hpp"
#include "cluster_detection/scalar/equal_runs.hpp"
#include "sorting/common/multicolumn_sort_types.hpp"
#include "sorting/common/multicolumn_sort_tasks.hpp"
#include "sorting/common/run_discovery.hpp"
#include "sorting/common/sort_helpers.hpp"


enum class TslLeafKind { INSERTION, NETWORK };
enum class TslPartitionKind { TWO_WAY, THREE_WAY };


// The largest range the insertion leaf handles before partitioning takes over.
// At namespace scope because the hybrid rule below is stated in terms of it and
// callers pick a fill percentage from it without naming a sorter.
inline constexpr std::size_t tsl_insertion_leaf_threshold = 64;


// The parameter-free hybrid setting: divert exactly the leaves the insertion
// configuration would have handled itself, so the network runs only where it is at
// least as full as insertion's own threshold. Derived rather than written down
// because the capacity depends on type and lane count -- u32/AVX-512 is 64 of 256,
// so 25%, and u64/AVX-512 is 64 of 128, so 50%.
template <class DataType, class SimdStyle>
constexpr auto tsl_hybrid_auto_percent() -> std::size_t {
  return 100 * tsl_insertion_leaf_threshold
    / TslCoSortBitonicLeaf<DataType, SimdStyle>::capacity;
}


// Leaf routing tally for the hybrid-leaf experiment (`bench_hybrid_leaf`). Only
// the hybrid branch of `leaf` writes it, so with `HybridFillPercent == 0` -- every
// instantiation outside that experiment -- nothing here is read or written.
struct TslLeafRoutingCounters {
  std::size_t to_network = 0;      // leaves sorted by the fixed-cost network
  std::size_t to_insertion = 0;    // leaves diverted to insertion instead
  std::size_t network_padding = 0; // network capacity spent on padding, summed
};
inline thread_local TslLeafRoutingCounters tsl_leaf_routing{};


// Sorts one active key while replaying its permutation on a runtime number of
// payload columns. sort_columns builds a lexicographic sort from that primitive
// by sorting the next column only inside complete equal runs of the active key.
template <
  class DataType = std::uint32_t,
  TslPartitionKind PartitionKind = TslPartitionKind::TWO_WAY,
  TslLeafKind LeafKind = TslLeafKind::INSERTION,
  std::size_t MaxColumns = 16,
  class SimdStyle = tsl::dataparallel::simd_for_t<tsl::dataparallel::native, DataType>,
  // Hybrid leaf, for the experiment above: with `LeafKind == NETWORK`, a leaf
  // holding less than this percentage of the network's fixed capacity goes to the
  // insertion leaf instead. The partition loop still stops at the network's
  // threshold, so the choice is made per leaf and costs one comparison there.
  // 0 disables it, which is what every other instantiation uses.
  std::size_t HybridFillPercent = 0
>
class TslMultiColumnQuickSorter {
  using DataSimdStyle = SimdStyle;
  static_assert(std::is_same_v<typename SimdStyle::base_type, DataType>,
                "SimdStyle::base_type must match DataType");
  using register_type = typename DataSimdStyle::register_type;
  using Partition = TslPartitionReplayStep<DataType, SimdStyle>;
  static constexpr std::size_t lane_count = DataSimdStyle::lane_count_v;
  static constexpr std::size_t insertion_leaf_threshold = tsl_insertion_leaf_threshold;
  static constexpr std::size_t network_leaf_capacity =
    TslCoSortBitonicLeaf<DataType, SimdStyle>::capacity;
  static constexpr std::size_t compute_leaf_threshold() {
    if constexpr (LeafKind == TslLeafKind::NETWORK) {
      return network_leaf_capacity;
    } else {
      return insertion_leaf_threshold;
    }
  }
  // The largest range a leaf may be handed. Also the floor for the parallel
  // paths' partition threshold, so it stays the network's capacity under the
  // hybrid even though smaller ranges may keep partitioning.
  static constexpr std::size_t leaf_threshold = compute_leaf_threshold();

  // True when a range stops partitioning and goes to the leaf.
  //
  // Under the hybrid the two leaves keep their own thresholds: insertion takes
  // anything at or below its own, and the network takes over only where it would
  // be filled enough to be worth its fixed cost. A range between the two -- too
  // sparse for the network, too long for insertion -- keeps partitioning, which is
  // what makes `HybridFillPercent` interpolate between the fixed configurations
  // rather than inherit the network's threshold for both leaves.
  static constexpr auto leaf_accepts(std::size_t count) -> bool {
    if constexpr (HybridFillPercent == 0) {
      return count <= leaf_threshold;
    } else {
      return count <= insertion_leaf_threshold
        || (count <= network_leaf_capacity
            && count * 100 >= HybridFillPercent * network_leaf_capacity);
    }
  }

  using column_pointers = std::array<DataType *, MaxColumns>;

  struct three_way_bounds {
    std::size_t left_end;
    std::size_t equal_begin;
    std::size_t equal_end;
    std::size_t right_begin;
  };

  std::uint64_t const seed_;

  auto task_seed(
    std::size_t column,
    std::size_t begin,
    std::size_t end
  ) const -> std::uint64_t {
    auto value = seed_;
    value ^= tsl_pivot_mix(static_cast<std::uint64_t>(column));
    value ^= tsl_pivot_mix(static_cast<std::uint64_t>(begin));
    value ^= tsl_pivot_mix(static_cast<std::uint64_t>(end));
    return tsl_pivot_mix(value);
  }

  template <TslSortOrder Order>
  static auto before(DataType left, DataType right) -> bool {
    if constexpr (Order == TslSortOrder::ASCENDING) {
      return left < right;
    } else {
      return left > right;
    }
  }

  static void swap_all(
    DataType * keys,
    column_pointers const & columns,
    std::size_t payload_count,
    std::size_t left,
    std::size_t right
  ) {
    std::swap(keys[left], keys[right]);
    for (std::size_t column = 0; column < payload_count; ++column) {
      std::swap(columns[column][left], columns[column][right]);
    }
  }

  // Moves the chosen element to keys[count - 1], where partition expects it,
  // and returns its value. The rule itself lives in sort_helpers.hpp.
  template <TslSortOrder Order>
  static auto get_pivot(
    DataType * keys,
    column_pointers const & columns,
    std::size_t payload_count,
    std::size_t count,
    std::uint64_t seed
  ) -> DataType {
    auto const pivot_index = tsl_pivot_index_of(
      keys,
      count,
      seed,
      [](DataType left, DataType right) { return before<Order>(left, right); }
    );
    swap_all(keys, columns, payload_count, pivot_index, count - 1);
    return keys[count - 1];
  }

  // The pivot remains at keys[count - 1]. BEFORE_PIVOT returns the first
  // element not ordered before it. EQUAL_TO returns the first element ordered
  // after it within a range known to contain only equal/after values.
  template <TslSortOrder Order, TslPartitionMode Mode>
  static auto partition(
    DataType * keys,
    column_pointers const & columns,
    std::size_t payload_count,
    std::size_t count,
    DataType pivot_value
  ) -> std::size_t {
    auto const pivot_vec = tsl::set1<DataSimdStyle>(pivot_value);
    DataType * left_ptr = keys;
    DataType * const pivot_ptr = keys + count - 1;
    DataType * scalar_end = pivot_ptr;

    register_type key_l{};
    register_type key_r{};
    std::size_t bad_l_count = 0;
    std::size_t bad_r_count = 0;
    enum class advance_state { LEFT, RIGHT, BOTH };
    auto advance = advance_state::BOTH;

    auto const bad_left = [&](register_type value) {
      if constexpr (Mode == TslPartitionMode::BEFORE_PIVOT) {
        if constexpr (Order == TslSortOrder::ASCENDING) {
          return tsl::greater_than_or_equal<DataSimdStyle>(value, pivot_vec);
        } else {
          return tsl::less_than_or_equal<DataSimdStyle>(value, pivot_vec);
        }
      } else if constexpr (Order == TslSortOrder::ASCENDING) {
        return tsl::greater_than<DataSimdStyle>(value, pivot_vec);
      } else {
        return tsl::less_than<DataSimdStyle>(value, pivot_vec);
      }
    };
    auto const bad_right = [&](register_type value) {
      if constexpr (Mode == TslPartitionMode::BEFORE_PIVOT) {
        if constexpr (Order == TslSortOrder::ASCENDING) {
          return tsl::less_than<DataSimdStyle>(value, pivot_vec);
        } else {
          return tsl::greater_than<DataSimdStyle>(value, pivot_vec);
        }
      } else {
        return tsl::equal<DataSimdStyle>(value, pivot_vec);
      }
    };

    if (static_cast<std::size_t>(pivot_ptr - left_ptr) >= 2 * lane_count) {
      DataType * right_ptr = pivot_ptr - lane_count;
      while ((right_ptr - left_ptr) >= static_cast<std::ptrdiff_t>(lane_count)) {
        if (advance == advance_state::LEFT || advance == advance_state::BOTH) {
          key_l = tsl::load<DataSimdStyle, false>(left_ptr);
          bad_l_count = tsl::mask_population_count<DataSimdStyle>(bad_left(key_l));
          if (bad_l_count == 0) {
            left_ptr += lane_count;
            advance = advance == advance_state::BOTH ? advance_state::BOTH : advance_state::LEFT;
            continue;
          }
        }
        if (advance == advance_state::RIGHT || advance == advance_state::BOTH) {
          key_r = tsl::load<DataSimdStyle, false>(right_ptr);
          bad_r_count = tsl::mask_population_count<DataSimdStyle>(bad_right(key_r));
          if (bad_r_count == 0) {
            right_ptr -= lane_count;
            advance = advance_state::RIGHT;
            continue;
          }
        }

        auto const left_offset = static_cast<std::size_t>(left_ptr - keys);
        auto const right_offset = static_cast<std::size_t>(right_ptr - keys);
        // Uninitialized on purpose: only [0, payload_count) is ever written or
        // read. Value-initializing them made every swap iteration memset
        // 4 * MaxColumns * sizeof(register_type) bytes of stack.
        std::array<register_type, MaxColumns> payload_l;
        std::array<register_type, MaxColumns> payload_r;
        std::array<register_type, MaxColumns> payload_write_l;
        std::array<register_type, MaxColumns> payload_write_r;
        for (std::size_t column = 0; column < payload_count; ++column) {
          payload_l[column] = tsl::load<DataSimdStyle, false>(columns[column] + left_offset);
          payload_r[column] = tsl::load<DataSimdStyle, false>(columns[column] + right_offset);
        }
        register_type key_write_l;
        register_type key_write_r;
        Partition::template step<Mode, Order>(
          key_l,
          key_r,
          payload_l.data(),
          payload_r.data(),
          payload_count,
          pivot_vec,
          key_write_l,
          key_write_r,
          payload_write_l.data(),
          payload_write_r.data()
        );
        tsl::store<DataSimdStyle, false>(left_ptr, key_write_l);
        tsl::store<DataSimdStyle, false>(right_ptr, key_write_r);
        for (std::size_t column = 0; column < payload_count; ++column) {
          tsl::store<DataSimdStyle, false>(columns[column] + left_offset, payload_write_l[column]);
          tsl::store<DataSimdStyle, false>(columns[column] + right_offset, payload_write_r[column]);
        }

        auto const swappable = std::min(bad_l_count, bad_r_count);
        left_ptr += swappable + (lane_count - bad_l_count);
        right_ptr -= swappable + (lane_count - bad_r_count);
        advance = advance_state::BOTH;
      }
      scalar_end = right_ptr + lane_count;
    }

    auto const left_good = [pivot_value](DataType value) {
      if constexpr (Mode == TslPartitionMode::BEFORE_PIVOT) {
        return before<Order>(value, pivot_value);
      } else {
        return value == pivot_value;
      }
    };
    auto const right_good = [pivot_value](DataType value) {
      if constexpr (Mode == TslPartitionMode::BEFORE_PIVOT) {
        return !before<Order>(value, pivot_value);
      } else {
        return before<Order>(pivot_value, value);
      }
    };

    while (left_ptr < scalar_end) {
      while (left_ptr < scalar_end && left_good(*left_ptr)) {
        ++left_ptr;
      }
      while (left_ptr < scalar_end && right_good(*(scalar_end - 1))) {
        --scalar_end;
      }
      if (left_ptr < scalar_end) {
        swap_all(
          keys,
          columns,
          payload_count,
          static_cast<std::size_t>(left_ptr - keys),
          static_cast<std::size_t>((scalar_end - 1) - keys)
        );
        ++left_ptr;
        --scalar_end;
      }
    }
    return static_cast<std::size_t>(left_ptr - keys);
  }

  template <TslSortOrder Order>
  static void insertion_leaf(
    DataType * keys,
    column_pointers const & columns,
    std::size_t payload_count,
    std::size_t count
  ) {
    for (std::size_t index = 1; index < count; ++index) {
      auto const key = keys[index];
      std::array<DataType, MaxColumns> payload{};
      for (std::size_t column = 0; column < payload_count; ++column) {
        payload[column] = columns[column][index];
      }
      auto destination = index;
      while (destination > 0 && before<Order>(key, keys[destination - 1])) {
        keys[destination] = keys[destination - 1];
        for (std::size_t column = 0; column < payload_count; ++column) {
          columns[column][destination] = columns[column][destination - 1];
        }
        --destination;
      }
      keys[destination] = key;
      for (std::size_t column = 0; column < payload_count; ++column) {
        columns[column][destination] = payload[column];
      }
    }
  }

  template <TslSortOrder Order>
  static void leaf(
    DataType * keys,
    column_pointers const & columns,
    std::size_t payload_count,
    std::size_t count
  ) {
    if constexpr (LeafKind == TslLeafKind::NETWORK) {
      // The network sorts `capacity` elements whatever the leaf holds, so a
      // sparse leaf pays for padding. Divert those to insertion, which is
      // O(count^2) but on a handful of elements far cheaper than a full network.
      if constexpr (HybridFillPercent != 0) {
        constexpr auto capacity = network_leaf_capacity;
        // `count > capacity` is not redundant. The network holds `lanes * rows`
        // elements, which at a narrow register and a wide key is *smaller* than
        // insertion's threshold -- 128-bit u64 gives two lanes, so capacity is 32
        // against a threshold of 64. `leaf_accepts` admits anything up to the
        // threshold, so without this test a 64-element leaf is handed to a network
        // that holds 32 and the sort is silently wrong. A leaf too long for the
        // network goes to insertion whatever its fill.
        if (count > capacity || count * 100 < HybridFillPercent * capacity) {
          if constexpr (tsl_cosort_instrumentation) {
            ++tsl_leaf_routing.to_insertion;
          }
          insertion_leaf<Order>(keys, columns, payload_count, count);
          return;
        }
        if constexpr (tsl_cosort_instrumentation) {
          ++tsl_leaf_routing.to_network;
          tsl_leaf_routing.network_padding += capacity - count;
        }
      }
      TslCoSortBitonicLeaf<DataType, SimdStyle>::template sort<Order>(
        keys,
        columns.data(),
        payload_count,
        count
      );
    } else {
      insertion_leaf<Order>(keys, columns, payload_count, count);
    }
  }

  // `range_sink` receives the absolute bounds of the partition side that would
  // otherwise become an inline recursive call. Returning true transfers
  // ownership of that range and this call skips it; returning false keeps the
  // recursion. The larger side is always continued in the loop, so recursion
  // depth stays logarithmic whether or not ranges are offloaded.
  //
  // Offering the smaller side is deliberate. Either choice publishes one
  // independent range per level, but keeping the larger side leaves this worker
  // with real work; publishing it instead would leave this worker with a
  // remainder it finishes immediately, and a newest-first queue would then very
  // likely hand the same large range straight back to it.
  template <
    TslSortOrder Order,
    bool ReportCompletion,
    class EqualBandSink,
    class LeafSink,
    class RangeSink
  >
  static void sort_impl(
    DataType * keys,
    column_pointers columns,
    std::size_t payload_count,
    std::size_t count,
    TslPivotRng & rng,
    std::size_t absolute_begin,
    // Start of the maximal equal run overlapping this range's left edge when that
    // edge is open; equal to `absolute_begin` when it is closed.
    std::size_t open_begin,
    EqualBandSink & equal_band_sink,
    LeafSink & leaf_sink,
    RangeSink & range_sink
  ) {
    while (!leaf_accepts(count)) {
      auto const pivot_value =
        get_pivot<Order>(keys, columns, payload_count, count, rng.next());
      std::size_t left_count;
      std::size_t right_begin;
      std::size_t right_count;

      if constexpr (PartitionKind == TslPartitionKind::TWO_WAY) {
        auto const before_end = partition<Order, TslPartitionMode::BEFORE_PIVOT>(
          keys,
          columns,
          payload_count,
          count,
          pivot_value
        );
        swap_all(keys, columns, payload_count, before_end, count - 1);
        left_count = before_end;
        right_begin = before_end + 1;
        right_count = count - right_begin;
      } else {
        auto const before_end = partition<Order, TslPartitionMode::BEFORE_PIVOT>(
          keys,
          columns,
          payload_count,
          count,
          pivot_value
        );
        column_pointers middle_columns{};
        for (std::size_t column = 0; column < payload_count; ++column) {
          middle_columns[column] = columns[column] + before_end;
        }
        auto const equal_pivot_position = before_end + partition<Order, TslPartitionMode::EQUAL_TO>(
          keys + before_end,
          middle_columns,
          payload_count,
          count - before_end,
          pivot_value
        );
        swap_all(keys, columns, payload_count, equal_pivot_position, count - 1);
        three_way_bounds const bounds{
          before_end,
          before_end,
          equal_pivot_position + 1,
          equal_pivot_position + 1,
        };
        left_count = bounds.left_end;
        right_begin = bounds.right_begin;
        right_count = count - right_begin;
        if constexpr (ReportCompletion) {
          equal_band_sink(
            absolute_begin + bounds.equal_begin,
            absolute_begin + bounds.equal_end
          );
        }
      }

      // Boundary state of the two children. A three-way partition closes every
      // boundary it creates -- the equal band lies strictly between the two sides --
      // which is why three-way incremental discovery needs no bookkeeping. A
      // two-way partition leaves
      //
      //   [ strictly before pivot ] [ pivot ] [ not before pivot ]
      //
      // so the left part's right boundary is closed by the pivot while the right
      // part's left boundary is open: a maximal run may span the pivot and the head
      // of the right part. Right boundaries are always closed -- the root's is, a
      // left part's is the pivot, a right part inherits it -- so only the left edge
      // needs tracking.
      //
      // One bit does not suffice. On duplicate-heavy input two-way peels one copy per
      // level with an empty left part, so a run of k equal values becomes a chain of
      // k consecutive pivots, and widening a fragment by one element would cover only
      // the nearest. Carrying the *start* of the run that overlaps the left edge
      // covers a chain of any length: everything in [open_begin, absolute_begin) is
      // equal and already final, so a fragment reporting from there finds a maximal
      // run.
      //
      // A range handed to another worker re-enters as a root with a closed left edge,
      // so the open run travels with it: the range is offered from the run's start.
      // Those extra elements are final and no other worker writes them, and a range
      // beginning with its own minimum keeps it there, so the offer is
      // self-contained.
      constexpr bool two_way = PartitionKind == TslPartitionKind::TWO_WAY;
      auto right_open_begin = absolute_begin + right_begin;
      auto left_open_begin = absolute_begin;
      if constexpr (two_way) {
        left_open_begin = open_begin;
        right_open_begin = absolute_begin + left_count;   // the pivot's position
        if (left_count == 0 && open_begin < absolute_begin) {
          // The left part is empty, so the pivot sits immediately right of the open
          // run. Reading keys[-1] is safe: it is inside the column and final.
          if (keys[-1] == keys[0]) {
            right_open_begin = open_begin;                // the chain continues
          } else if (ReportCompletion && absolute_begin - open_begin >= 2) {
            // The chain ends here: a complete all-equal range that no fragment of
            // this subtree would otherwise cover.
            leaf_sink(open_begin, absolute_begin);
          }
        }
      }

      column_pointers right_columns{};
      for (std::size_t column = 0; column < payload_count; ++column) {
        right_columns[column] = columns[column] + right_begin;
      }
      auto * const right_keys = keys + right_begin;
      if (left_count < right_count) {
        if (!range_sink(left_open_begin, absolute_begin + left_count)) {
          sort_impl<Order, ReportCompletion>(
            keys,
            columns,
            payload_count,
            left_count,
            rng,
            absolute_begin,
            left_open_begin,
            equal_band_sink,
            leaf_sink,
            range_sink
          );
        }
        keys = right_keys;
        columns = right_columns;
        count = right_count;
        absolute_begin += right_begin;
        open_begin = right_open_begin;
      } else {
        if (!range_sink(right_open_begin, absolute_begin + count)) {
          sort_impl<Order, ReportCompletion>(
            right_keys,
            right_columns,
            payload_count,
            right_count,
            rng,
            absolute_begin + right_begin,
            right_open_begin,
            equal_band_sink,
            leaf_sink,
            range_sink
          );
        }
        count = left_count;
        open_begin = left_open_begin;
      }
    }

    if (count >= 2) {
      leaf<Order>(keys, columns, payload_count, count);
    }
    if constexpr (ReportCompletion) {
      // Reporting from `open_begin` makes every reported range closed on both sides,
      // so the runs a consumer finds in it are maximal. An empty fragment reports
      // nothing: its open run either continues into the sibling pivot, whose range
      // covers it, or was already reported where the chain ended.
      auto const report_end = absolute_begin + count;
      if (count != 0 && report_end - open_begin >= 2) {
        leaf_sink(open_begin, report_end);
      }
    }
  }

  template <
    bool ReportCompletion,
    class EqualBandSink,
    class LeafSink,
    class RangeSink
  >
  static void sort_active_range(
    DataType * keys,
    column_pointers const & columns,
    std::size_t payload_count,
    std::size_t count,
    TslSortOrder order,
    TslPivotRng & rng,
    std::size_t absolute_begin,
    EqualBandSink & equal_band_sink,
    LeafSink & leaf_sink,
    RangeSink & range_sink
  ) {
    if (count < 2) {
      if constexpr (ReportCompletion) {
        if (count == 1) {
          leaf_sink(absolute_begin, absolute_begin + 1);
        }
      }
      return;
    }
    if (order == TslSortOrder::ASCENDING) {
      sort_impl<TslSortOrder::ASCENDING, ReportCompletion>(
        keys,
        columns,
        payload_count,
        count,
        rng,
        absolute_begin,
        absolute_begin,  // the root of a column sort is closed on both sides
        equal_band_sink,
        leaf_sink,
        range_sink
      );
    } else {
      sort_impl<TslSortOrder::DESCENDING, ReportCompletion>(
        keys,
        columns,
        payload_count,
        count,
        rng,
        absolute_begin,
        absolute_begin,
        equal_band_sink,
        leaf_sink,
        range_sink
      );
    }
  }

  // Serial entry points never transfer a partition range to another worker.
  static auto keep_range_local() {
    return [](std::size_t, std::size_t) { return false; };
  }

  static auto payload_columns_for(
    TslSortColumn<DataType> const * columns,
    std::size_t column_count,
    std::size_t active_column,
    std::size_t begin
  ) -> column_pointers {
    column_pointers payloads{};
    for (auto column = active_column + 1; column < column_count; ++column) {
      payloads[column - active_column - 1] = columns[column].data + begin;
    }
    return payloads;
  }

  template <TslRunDiscoveryKind Discovery>
  void sort_columns_impl(
    TslSortColumn<DataType> const * columns,
    std::size_t column_count,
    std::size_t active_column,
    std::size_t begin,
    std::size_t end,
    TslMultiColumnSortMetrics * metrics
  ) const {
    if (end - begin < 2 || active_column >= column_count) {
      return;
    }

    auto const payload_count = column_count - active_column - 1;
    auto const payloads = payload_columns_for(columns, column_count, active_column, begin);
    auto rng = TslPivotRng(task_seed(active_column, begin, end));
    auto no_equal_band = [](std::size_t, std::size_t) {};
    auto no_leaf = [](std::size_t, std::size_t) {};
    auto no_range = keep_range_local();

    if constexpr (Discovery == TslRunDiscoveryKind::INCREMENTAL) {
      if (active_column + 1 == column_count) {
        sort_active_range<false>(
          columns[active_column].data + begin,
          payloads,
          payload_count,
          end - begin,
          columns[active_column].order,
          rng,
          begin,
          no_equal_band,
          no_leaf,
          no_range
        );
        return;
      }

      auto on_equal_band = [&](std::size_t band_begin, std::size_t band_end) {
        if (band_end - band_begin < 2) {
          return;
        }
        if (metrics != nullptr) {
          ++metrics->direct_equal_bands;
          metrics->direct_equal_band_rows += band_end - band_begin;
        }
        sort_columns_impl<Discovery>(
          columns,
          column_count,
          active_column + 1,
          band_begin,
          band_end,
          metrics
        );
      };
      auto on_leaf = [&](std::size_t leaf_begin, std::size_t leaf_end) {
        if (leaf_end - leaf_begin < 2) {
          return;
        }
        if (metrics != nullptr) {
          metrics->rle_values_scanned += leaf_end - leaf_begin;
        }
        tsl_for_each_equal_run(
          columns[active_column].data,
          leaf_begin,
          leaf_end,
          [&](TslRunSpan span) {
            sort_columns_impl<Discovery>(
              columns,
              column_count,
              active_column + 1,
              span.begin,
              span.end,
              metrics
            );
          }
        );
      };
      sort_active_range<true>(
        columns[active_column].data + begin,
        payloads,
        payload_count,
        end - begin,
        columns[active_column].order,
        rng,
        begin,
        on_equal_band,
        on_leaf,
        no_range
      );
      return;
    }

    sort_active_range<false>(
      columns[active_column].data + begin,
      payloads,
      payload_count,
      end - begin,
      columns[active_column].order,
      rng,
      begin,
      no_equal_band,
      no_leaf,
      no_range
    );
    if (active_column + 1 == column_count) {
      return;
    }
    if (metrics != nullptr) {
      metrics->rle_values_scanned += end - begin;
    }
    tsl_for_each_equal_run(
      columns[active_column].data,
      begin,
      end,
      [&](TslRunSpan span) {
        sort_columns_impl<Discovery>(
          columns,
          column_count,
          active_column + 1,
          span.begin,
          span.end,
          metrics
        );
      }
    );
  }

  struct concurrent_sort_metrics {
    std::atomic<std::size_t> rle_values_scanned{0};
    std::atomic<std::size_t> direct_equal_bands{0};
    std::atomic<std::size_t> direct_equal_band_rows{0};
    std::atomic<std::size_t> partition_tasks{0};
  };

  template <
    TslRunDiscoveryKind Discovery,
    class Schedule,
    class Offload,
    class DetectRuns,
    class MakeEmit
  >
  void process_parallel_task(
    TslSortColumn<DataType> const * columns,
    std::size_t column_count,
    TslColumnSortTask task,
    Schedule & schedule,
    Offload & offload,
    DetectRuns & detect_runs,
    MakeEmit & make_emit,
    concurrent_sort_metrics * metrics
  ) const {
    if (task.end - task.begin < 2 || task.column >= column_count) {
      return;
    }

    auto const payload_count = column_count - task.column - 1;
    auto const payloads = payload_columns_for(
      columns,
      column_count,
      task.column,
      task.begin
    );
    auto rng = TslPivotRng(task_seed(task.column, task.begin, task.end));
    auto no_equal_band = [](std::size_t, std::size_t) {};
    auto no_leaf = [](std::size_t, std::size_t) {};

    // A partition subrange may be finished by a different worker only when this
    // task owes nothing to its complete range. Incremental discovery qualifies for
    // either partition kind: three-way closes every boundary it creates, and
    // two-way hands an open left edge to the receiving worker by widening the
    // offered range to include the pivot, so each partition reports self-contained
    // work no matter who sorts it. A final column qualifies because no column
    // follows it. Post-sort discovery over a non-final column does not: its RLE
    // scan needs the whole sorted range, and an equal run may cross a partition
    // boundary, so those partitions stay on this worker.
    constexpr bool discovery_is_partition_local =
      Discovery == TslRunDiscoveryKind::INCREMENTAL;
    auto offload_range = [&](std::size_t range_begin, std::size_t range_end) {
      if (!discovery_is_partition_local && task.column + 1 != column_count) {
        return false;
      }
      if (!offload(TslColumnSortTask{task.column, range_begin, range_end})) {
        return false;
      }
      if (metrics != nullptr) {
        metrics->partition_tasks.fetch_add(1, std::memory_order_relaxed);
      }
      return true;
    };

    if constexpr (Discovery == TslRunDiscoveryKind::INCREMENTAL) {
      if (task.column + 1 == column_count) {
        sort_active_range<false>(
          columns[task.column].data + task.begin,
          payloads,
          payload_count,
          task.end - task.begin,
          columns[task.column].order,
          rng,
          task.begin,
          no_equal_band,
          no_leaf,
          offload_range
        );
        return;
      }

      auto on_equal_band = [&](std::size_t band_begin, std::size_t band_end) {
        if (band_end - band_begin < 2) {
          return;
        }
        if (metrics != nullptr) {
          metrics->direct_equal_bands.fetch_add(1, std::memory_order_relaxed);
          metrics->direct_equal_band_rows.fetch_add(
            band_end - band_begin,
            std::memory_order_relaxed
          );
        }
        schedule(TslColumnSortTask{task.column + 1, band_begin, band_end});
      };
      auto on_leaf = [&](std::size_t leaf_begin, std::size_t leaf_end) {
        if (leaf_end - leaf_begin < 2) {
          return;
        }
        if (metrics != nullptr) {
          metrics->rle_values_scanned.fetch_add(
            leaf_end - leaf_begin,
            std::memory_order_relaxed
          );
        }
        // make_emit, not a [&] lambda: an asynchronous detector retains this
        // callable past the end of this task, so it must own what it needs.
        tsl_detect_runs(
          detect_runs,
          columns[task.column].data,
          leaf_begin,
          leaf_end,
          make_emit(task.column + 1)
        );
      };
      sort_active_range<true>(
        columns[task.column].data + task.begin,
        payloads,
        payload_count,
        task.end - task.begin,
        columns[task.column].order,
        rng,
        task.begin,
        on_equal_band,
        on_leaf,
        offload_range
      );
      return;
    }

    // A detector that wants the range before it is sorted gets it here: this path
    // sorts [task.begin, task.end) and then detects over exactly that range, so
    // the two see the same multiset. Order-independent work -- value frequencies,
    // say -- can therefore overlap the sort. A detector without `prepare` is
    // unaffected.
    if constexpr (tsl_detector_wants_prepare<DetectRuns, DataType>::value) {
      detect_runs.prepare(columns[task.column].data, task.begin, task.end);
    }
    sort_active_range<false>(
      columns[task.column].data + task.begin,
      payloads,
      payload_count,
      task.end - task.begin,
      columns[task.column].order,
      rng,
      task.begin,
      no_equal_band,
      no_leaf,
      offload_range
    );
    if (task.column + 1 == column_count) {
      return;
    }
    if (metrics != nullptr) {
      metrics->rle_values_scanned.fetch_add(
        task.end - task.begin,
        std::memory_order_relaxed
      );
    }
    tsl_detect_runs(
      detect_runs,
      columns[task.column].data,
      task.begin,
      task.end,
      make_emit(task.column + 1)
    );
  }

  static void validate_columns(
    TslSortColumn<DataType> const * columns,
    std::size_t column_count,
    std::size_t row_count
  ) {
    if (column_count > MaxColumns) {
      throw std::invalid_argument("sort column count exceeds MaxColumns");
    }
    if (column_count == 0) {
      return;
    }
    if (row_count == 0) {
      return;
    }
    if (columns == nullptr) {
      throw std::invalid_argument("sort columns pointer is null");
    }
    for (std::size_t column = 0; column < column_count; ++column) {
      if (columns[column].data == nullptr) {
        throw std::invalid_argument("sort column data pointer is null");
      }
      for (std::size_t previous = 0; previous < column; ++previous) {
        if (columns[column].data == columns[previous].data) {
          throw std::invalid_argument("sort columns must not alias");
        }
      }
    }
  }

 public:
  explicit TslMultiColumnQuickSorter(std::uint64_t seed) : seed_(seed) {}

  static constexpr auto leaf_size_threshold() -> std::size_t {
    return leaf_threshold;
  }

  void sort_key(
    DataType * keys,
    DataType * const * payload_columns,
    std::size_t payload_count,
    std::size_t count,
    TslSortOrder order
  ) const {
    if (payload_count > MaxColumns) {
      throw std::invalid_argument("payload column count exceeds MaxColumns");
    }
    if (count == 0) {
      return;
    }
    if (count != 0 && keys == nullptr) {
      throw std::invalid_argument("key pointer is null");
    }
    if (payload_count != 0 && payload_columns == nullptr) {
      throw std::invalid_argument("payload columns pointer is null");
    }

    column_pointers columns{};
    for (std::size_t column = 0; column < payload_count; ++column) {
      if (count != 0 && payload_columns[column] == nullptr) {
        throw std::invalid_argument("payload column data pointer is null");
      }
      if (payload_columns[column] == keys) {
        throw std::invalid_argument("active key must not alias a payload column");
      }
      for (std::size_t previous = 0; previous < column; ++previous) {
        if (payload_columns[column] == payload_columns[previous]) {
          throw std::invalid_argument("payload columns must not alias");
        }
      }
      columns[column] = payload_columns[column];
    }
    auto rng = TslPivotRng(task_seed(0, 0, count));
    auto no_equal_band = [](std::size_t, std::size_t) {};
    auto no_leaf = [](std::size_t, std::size_t) {};
    auto no_range = keep_range_local();
    sort_active_range<false>(
      keys,
      columns,
      payload_count,
      count,
      order,
      rng,
      0,
      no_equal_band,
      no_leaf,
      no_range
    );
  }

  void operator()(
    DataType * keys,
    DataType * const * payload_columns,
    std::size_t payload_count,
    std::size_t count
  ) const {
    sort_key(
      keys,
      payload_columns,
      payload_count,
      count,
      TslSortOrder::ASCENDING
    );
  }

  template <class EqualBandSink, class LeafSink>
  void sort_key_with_completion_events(
    DataType * keys,
    DataType * const * payload_columns,
    std::size_t payload_count,
    std::size_t count,
    TslSortOrder order,
    std::size_t absolute_begin,
    EqualBandSink & equal_band_sink,
    LeafSink & leaf_sink
  ) const {
    // Both partition kinds report completion. Three-way emits pivot-equal bands
    // directly and closes every boundary; two-way emits none and instead widens a
    // fragment whose left edge is open, so a consumer sees closed ranges either
    // way.
    if (payload_count > MaxColumns) {
      throw std::invalid_argument("payload column count exceeds MaxColumns");
    }
    if (count == 0) {
      return;
    }
    if (count != 0 && keys == nullptr) {
      throw std::invalid_argument("key pointer is null");
    }
    if (payload_count != 0 && payload_columns == nullptr) {
      throw std::invalid_argument("payload columns pointer is null");
    }
    column_pointers columns{};
    for (std::size_t column = 0; column < payload_count; ++column) {
      if (count != 0 && payload_columns[column] == nullptr) {
        throw std::invalid_argument("payload column data pointer is null");
      }
      if (payload_columns[column] == keys) {
        throw std::invalid_argument("active key must not alias a payload column");
      }
      for (std::size_t previous = 0; previous < column; ++previous) {
        if (payload_columns[column] == payload_columns[previous]) {
          throw std::invalid_argument("payload columns must not alias");
        }
      }
      columns[column] = payload_columns[column];
    }
    auto rng = TslPivotRng(task_seed(
      0,
      absolute_begin,
      absolute_begin + count
    ));
    auto no_range = keep_range_local();
    sort_active_range<true>(
      keys,
      columns,
      payload_count,
      count,
      order,
      rng,
      absolute_begin,
      equal_band_sink,
      leaf_sink,
      no_range
    );
  }

  void sort_columns(
    TslSortColumn<DataType> const * columns,
    std::size_t column_count,
    std::size_t row_count,
    TslRunDiscoveryKind discovery = TslRunDiscoveryKind::POST_SORT,
    TslMultiColumnSortMetrics * metrics = nullptr
  ) const {
    validate_columns(columns, column_count, row_count);
    if (metrics != nullptr) {
      *metrics = {};
    }
    if (column_count == 0 || row_count < 2) {
      return;
    }
    if (discovery == TslRunDiscoveryKind::INCREMENTAL) {
      sort_columns_impl<TslRunDiscoveryKind::INCREMENTAL>(
        columns,
        column_count,
        0,
        0,
        row_count,
        metrics
      );
    } else {
      sort_columns_impl<TslRunDiscoveryKind::POST_SORT>(
        columns,
        column_count,
        0,
        0,
        row_count,
        metrics
      );
    }
  }

  // `partition_threshold` is zero to keep every quicksort partition on the
  // worker that produced it, or the smallest partition row count worth handing
  // to another worker. It is deliberately separate from `task_threshold`: a
  // next-column task pays for run discovery plus a whole subtree, while a
  // partition task pays for one partition pass.
  // Default equal-run detector: the scalar linear pass. `sort_columns_parallel`
  // accepts a replacement so an accelerator-backed detector can be substituted
  // without this header knowing anything about the accelerator.
  struct scalar_run_detector {
    template <class Emit>
    void operator()(
      DataType const * values,
      std::size_t begin,
      std::size_t end,
      Emit && emit
    ) const {
      tsl_for_each_equal_run(values, begin, end, std::forward<Emit>(emit));
    }
  };

  // Sorts ONE key range with its payloads across `worker_count` threads and
  // reports the completion events, driving no multi-column recursion of its own.
  // `sort_columns_parallel` owns the recursion because it owns the columns; a
  // caller that owns its own level structure -- the indirect sorter in
  // multicolumn_index_sort.hpp -- needs the range parallelism without it, and this
  // is the seam for that.
  //
  // Two things the caller takes on:
  //
  //   * The sinks are invoked from worker threads, and a partition may be
  //     finished by a worker other than the one that created it, so they must be
  //     thread-safe. `sort_columns_parallel` sidesteps this by turning events into
  //     executor tasks rather than user callbacks.
  //   * Offloading a partition is unconditional here, where
  //     `process_parallel_task` allows it only when a task owes nothing to its
  //     complete range. That is sound precisely because this entry promises
  //     nothing about scanning the whole range: it sorts and reports, and a caller
  //     wanting a post-sort scan runs it after this returns, over the range as a
  //     whole. A caller that instead scans inside a sink inherits the constraint
  //     `process_parallel_task` documents and must pass `partition_threshold = 0`.
  //
  // `absolute_begin` offsets the reported spans, as in
  // `sort_key_with_completion_events`.
  template <class EqualBandSink, class LeafSink>
  void sort_key_parallel(
    DataType * keys,
    DataType * const * payload_columns,
    std::size_t payload_count,
    std::size_t count,
    TslSortOrder order,
    std::size_t absolute_begin,
    std::size_t worker_count,
    std::size_t task_threshold,
    std::size_t partition_threshold,
    EqualBandSink & equal_band_sink,
    LeafSink & leaf_sink
  ) const {
    if (payload_count > MaxColumns) {
      throw std::invalid_argument("payload column count exceeds MaxColumns");
    }
    if (count < 2) {
      return;
    }
    if (keys == nullptr) {
      throw std::invalid_argument("key pointer is null");
    }
    if (worker_count == 0) {
      worker_count = 1;
    }
    if (task_threshold == 0) {
      task_threshold = 1;
    }
    if (partition_threshold != 0) {
      // A range at or below the leaf threshold never partitions, so a smaller
      // value would only queue ranges that cannot produce children.
      partition_threshold = std::max(partition_threshold, leaf_threshold + 1);
    }

    // Relative to `keys`, so a task carries no column index: there is one key
    // column here and the caller decides what follows.
    struct range_task {
      std::size_t begin;
      std::size_t end;
    };

    auto payloads_at = [payload_columns, payload_count](std::size_t begin) {
      column_pointers payloads{};
      for (std::size_t column = 0; column < payload_count; ++column) {
        payloads[column] = payload_columns[column] + begin;
      }
      return payloads;
    };

    auto worker = [&](range_task const & task, auto & executor) {
      auto const task_count = task.end - task.begin;
      if (task_count < 2) {
        return;
      }
      // Seeded from the task's offset within this call, not from its absolute
      // position, so that a range sorted here draws the same pivots it would
      // under `sort_key`/`sort_key_with_completion_events`. That keeps the serial
      // and parallel forms bit-identical, which is what lets a differential test
      // compare permutations rather than only value images.
      auto rng = TslPivotRng(task_seed(0, task.begin, task.end));
      auto const payloads = payloads_at(task.begin);
      // sort_impl reports in absolute coordinates, so a range it offers is
      // converted back to the task's own frame here.
      auto offload_range = [&executor, task_threshold, partition_threshold, absolute_begin](
        std::size_t range_begin,
        std::size_t range_end
      ) {
        if (partition_threshold == 0 || range_end - range_begin < partition_threshold) {
          return false;
        }
        range_task child{range_begin - absolute_begin, range_end - absolute_begin};
        if (child.end - child.begin < task_threshold) {
          executor.run_inline(child);
        } else {
          executor.submit(child);
        }
        return true;
      };
      sort_active_range<true>(
        keys + task.begin,
        payloads,
        payload_count,
        task_count,
        order,
        rng,
        absolute_begin + task.begin,
        equal_band_sink,
        leaf_sink,
        offload_range
      );
    };

    TslTaskExecutor<range_task, decltype(worker)> executor(worker_count, worker);
    executor.submit(range_task{0, count});
    executor.wait();
  }

  void sort_columns_parallel(
    TslSortColumn<DataType> const * columns,
    std::size_t column_count,
    std::size_t row_count,
    std::size_t worker_count,
    std::size_t task_threshold,
    std::size_t partition_threshold,
    TslRunDiscoveryKind discovery = TslRunDiscoveryKind::POST_SORT,
    TslMultiColumnSortMetrics * metrics = nullptr
  ) const {
    scalar_run_detector detector;
    sort_columns_parallel(
      columns, column_count, row_count, worker_count, task_threshold,
      partition_threshold, discovery, detector, metrics
    );
  }

  template <class DetectRuns>
  void sort_columns_parallel(
    TslSortColumn<DataType> const * columns,
    std::size_t column_count,
    std::size_t row_count,
    std::size_t worker_count,
    std::size_t task_threshold,
    std::size_t partition_threshold,
    TslRunDiscoveryKind discovery,
    DetectRuns & detect_runs,
    TslMultiColumnSortMetrics * metrics = nullptr
  ) const {
    validate_columns(columns, column_count, row_count);
    if (metrics != nullptr) {
      *metrics = {};
    }
    if (column_count == 0 || row_count < 2) {
      return;
    }
    if (worker_count == 0) {
      throw std::invalid_argument("parallel sort requires at least one worker");
    }
    task_threshold = std::max<std::size_t>(task_threshold, 2);
    if (partition_threshold != 0) {
      // A range at or below the leaf threshold is never partitioned, so a
      // smaller value would only queue ranges that cannot produce children.
      partition_threshold = std::max(partition_threshold, leaf_threshold + 1);
    }

    concurrent_sort_metrics algorithm_metrics;
    auto worker = [&](TslColumnSortTask const & task, auto & executor) {
      auto schedule = [&](TslColumnSortTask child) {
        if (child.end - child.begin < task_threshold) {
          executor.run_inline(child);
        } else {
          executor.submit(std::move(child));
        }
      };
      // Unlike a next-column child, a partition range below the threshold is
      // declined rather than run inline: the caller still holds it and its own
      // recursion is cheaper than re-entering a task.
      auto offload = [&](TslColumnSortTask child) {
        if (
          partition_threshold == 0
          || child.end - child.begin < partition_threshold
        ) {
          return false;
        }
        executor.submit(std::move(child));
        return true;
      };
      // Produces a next-column emitter that captures nothing task-local: the
      // executor by pointer (it outlives the whole sort) and the threshold and
      // column by value. An asynchronous detector may invoke the result on
      // another worker long after this task returned, so a [&] capture of
      // `schedule` or `task` would dangle. Same scheduling policy as `schedule`.
      auto make_emit = [&executor, task_threshold](std::size_t next_column) {
        return [target = &executor, task_threshold, next_column](TslRunSpan span) {
          TslColumnSortTask child{next_column, span.begin, span.end};
          if (child.end - child.begin < task_threshold) {
            target->run_inline(child);
          } else {
            target->submit(std::move(child));
          }
        };
      };
      if (discovery == TslRunDiscoveryKind::INCREMENTAL) {
        process_parallel_task<TslRunDiscoveryKind::INCREMENTAL>(
          columns,
          column_count,
          task,
          schedule,
          offload,
          detect_runs,
          make_emit,
          metrics != nullptr ? &algorithm_metrics : nullptr
        );
      } else {
        process_parallel_task<TslRunDiscoveryKind::POST_SORT>(
          columns,
          column_count,
          task,
          schedule,
          offload,
          detect_runs,
          make_emit,
          metrics != nullptr ? &algorithm_metrics : nullptr
        );
      }
    };

    TslTaskExecutor<TslColumnSortTask, decltype(worker)> executor(
      worker_count,
      worker
    );
    // An asynchronous detector needs the executor to hold a pending unit per
    // in-flight range and needs its completions checked from worker threads.
    // Both are wired here, before the first task exists, so nothing can run
    // against a half-connected detector. Detectors without these members are
    // unaffected.
    if constexpr (tsl_detector_wants_executor<DetectRuns>::value) {
      detect_runs.bind(executor);
      executor.set_poller([&detect_runs] { detect_runs.poll(); });
    }
    executor.submit(TslColumnSortTask{0, 0, row_count});
    executor.wait();

    if (metrics != nullptr) {
      auto const task_metrics = executor.metrics();
      metrics->rle_values_scanned =
        algorithm_metrics.rle_values_scanned.load(std::memory_order_relaxed);
      metrics->direct_equal_bands =
        algorithm_metrics.direct_equal_bands.load(std::memory_order_relaxed);
      metrics->direct_equal_band_rows =
        algorithm_metrics.direct_equal_band_rows.load(std::memory_order_relaxed);
      metrics->partition_tasks_submitted =
        algorithm_metrics.partition_tasks.load(std::memory_order_relaxed);
      metrics->tasks_submitted = task_metrics.tasks_submitted;
      metrics->tasks_executed_inline = task_metrics.tasks_executed_inline;
      metrics->max_outstanding_tasks = task_metrics.max_outstanding_tasks;
      metrics->idle_poll_wakeups = task_metrics.idle_poll_wakeups;
    }
  }
};
