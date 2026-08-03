#pragma once

#include <algorithm>
#include <array>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <random>
#include <stdexcept>
#include <type_traits>
#include <utility>

#include <tsl.hpp>

#include "cosort_bitonic_leaf.hpp"
#include "cosort_network.hpp"
#include "equal_runs.hpp"
#include "multicolumn_sort_types.hpp"
#include "multicolumn_sort_tasks.hpp"


enum class TslLeafKind { INSERTION, NETWORK };
enum class TslPartitionKind { TWO_WAY, THREE_WAY };


// Sorts one active key while replaying its permutation on a runtime number of
// payload columns. sort_columns builds a lexicographic sort from that primitive
// by sorting the next column only inside complete equal runs of the active key.
template <
  class DataType = std::uint32_t,
  TslPartitionKind PartitionKind = TslPartitionKind::TWO_WAY,
  TslLeafKind LeafKind = TslLeafKind::INSERTION,
  std::size_t MaxColumns = 16,
  class SimdStyle = tsl::dataparallel::simd_for_t<tsl::dataparallel::native, DataType>
>
class TslMultiColumnQuickSorter {
  using DataSimdStyle = SimdStyle;
  static_assert(std::is_same_v<typename SimdStyle::base_type, DataType>,
                "SimdStyle::base_type must match DataType");
  using register_type = typename DataSimdStyle::register_type;
  using Partition = TslPartitionReplayStep<DataType, SimdStyle>;
  static constexpr std::size_t lane_count = DataSimdStyle::lane_count_v;
  static constexpr std::size_t compute_leaf_threshold() {
    if constexpr (LeafKind == TslLeafKind::NETWORK) {
      return TslCoSortBitonicLeaf<DataType, SimdStyle>::capacity;
    } else {
      return 64;
    }
  }
  static constexpr std::size_t leaf_threshold = compute_leaf_threshold();

  using column_pointers = std::array<DataType *, MaxColumns>;

  struct three_way_bounds {
    std::size_t left_end;
    std::size_t equal_begin;
    std::size_t equal_end;
    std::size_t right_begin;
  };

  std::uint64_t const seed_;

  static auto mix_seed(std::uint64_t value) -> std::uint64_t {
    value += 0x9e3779b97f4a7c15ULL;
    value = (value ^ (value >> 30)) * 0xbf58476d1ce4e5b9ULL;
    value = (value ^ (value >> 27)) * 0x94d049bb133111ebULL;
    return value ^ (value >> 31);
  }

  auto task_seed(
    std::size_t column,
    std::size_t begin,
    std::size_t end
  ) const -> std::uint64_t {
    auto value = seed_;
    value ^= mix_seed(static_cast<std::uint64_t>(column));
    value ^= mix_seed(static_cast<std::uint64_t>(begin));
    value ^= mix_seed(static_cast<std::uint64_t>(end));
    return mix_seed(value);
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

  template <TslSortOrder Order>
  static auto get_pivot(
    DataType * keys,
    column_pointers const & columns,
    std::size_t payload_count,
    std::size_t count,
    std::mt19937_64 & rng
  ) -> DataType {
    auto const i0 = static_cast<std::size_t>(rng() % count);
    auto const i1 = static_cast<std::size_t>(rng() % count);
    auto const i2 = static_cast<std::size_t>(rng() % count);
    auto const a = keys[i0];
    auto const b = keys[i1];
    auto const c = keys[i2];
    std::size_t median_index;
    if (before<Order>(a, b)) {
      median_index = before<Order>(b, c) ? i1 : (before<Order>(a, c) ? i2 : i0);
    } else {
      median_index = before<Order>(a, c) ? i0 : (before<Order>(b, c) ? i2 : i1);
    }
    swap_all(keys, columns, payload_count, median_index, count - 1);
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
        std::array<register_type, MaxColumns> payload_l{};
        std::array<register_type, MaxColumns> payload_r{};
        std::array<register_type, MaxColumns> payload_write_l{};
        std::array<register_type, MaxColumns> payload_write_r{};
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
    std::mt19937_64 & rng,
    std::size_t absolute_begin,
    EqualBandSink & equal_band_sink,
    LeafSink & leaf_sink,
    RangeSink & range_sink
  ) {
    while (count > leaf_threshold) {
      auto const pivot_value = get_pivot<Order>(keys, columns, payload_count, count, rng);
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

      column_pointers right_columns{};
      for (std::size_t column = 0; column < payload_count; ++column) {
        right_columns[column] = columns[column] + right_begin;
      }
      auto * const right_keys = keys + right_begin;
      if (left_count < right_count) {
        if (!range_sink(absolute_begin, absolute_begin + left_count)) {
          sort_impl<Order, ReportCompletion>(
            keys,
            columns,
            payload_count,
            left_count,
            rng,
            absolute_begin,
            equal_band_sink,
            leaf_sink,
            range_sink
          );
        }
        keys = right_keys;
        columns = right_columns;
        count = right_count;
        absolute_begin += right_begin;
      } else {
        if (!range_sink(absolute_begin + right_begin, absolute_begin + count)) {
          sort_impl<Order, ReportCompletion>(
            right_keys,
            right_columns,
            payload_count,
            right_count,
            rng,
            absolute_begin + right_begin,
            equal_band_sink,
            leaf_sink,
            range_sink
          );
        }
        count = left_count;
      }
    }

    if (count >= 2) {
      leaf<Order>(keys, columns, payload_count, count);
    }
    if constexpr (ReportCompletion) {
      if (count != 0) {
        leaf_sink(absolute_begin, absolute_begin + count);
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
    std::mt19937_64 & rng,
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
    auto rng = std::mt19937_64(task_seed(active_column, begin, end));
    auto no_equal_band = [](std::size_t, std::size_t) {};
    auto no_leaf = [](std::size_t, std::size_t) {};
    auto no_range = keep_range_local();

    if constexpr (
      Discovery == TslRunDiscoveryKind::INCREMENTAL
      && PartitionKind == TslPartitionKind::THREE_WAY
    ) {
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

  template <TslRunDiscoveryKind Discovery, class Schedule, class Offload>
  void process_parallel_task(
    TslSortColumn<DataType> const * columns,
    std::size_t column_count,
    TslColumnSortTask task,
    Schedule & schedule,
    Offload & offload,
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
    auto rng = std::mt19937_64(task_seed(task.column, task.begin, task.end));
    auto no_equal_band = [](std::size_t, std::size_t) {};
    auto no_leaf = [](std::size_t, std::size_t) {};

    // A partition subrange may be finished by a different worker only when this
    // task owes nothing to its complete range. Three-way incremental discovery
    // qualifies because every maximal equal run lies wholly inside one leaf or
    // one pivot-equal band, so each partition reports self-contained work no
    // matter which worker sorts it. A final column qualifies because no column
    // follows it. Post-sort discovery over a non-final column does not: its RLE
    // scan needs the whole sorted range, and an equal run may cross a partition
    // boundary, so those partitions stay on this worker.
    constexpr bool discovery_is_partition_local =
      Discovery == TslRunDiscoveryKind::INCREMENTAL
      && PartitionKind == TslPartitionKind::THREE_WAY;
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

    if constexpr (
      Discovery == TslRunDiscoveryKind::INCREMENTAL
      && PartitionKind == TslPartitionKind::THREE_WAY
    ) {
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
        tsl_for_each_equal_run(
          columns[task.column].data,
          leaf_begin,
          leaf_end,
          [&](TslRunSpan span) {
            schedule(TslColumnSortTask{
              task.column + 1,
              span.begin,
              span.end,
            });
          }
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
    tsl_for_each_equal_run(
      columns[task.column].data,
      task.begin,
      task.end,
      [&](TslRunSpan span) {
        schedule(TslColumnSortTask{
          task.column + 1,
          span.begin,
          span.end,
        });
      }
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
    auto rng = std::mt19937_64(task_seed(0, 0, count));
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
    static_assert(
      PartitionKind == TslPartitionKind::THREE_WAY,
      "completion events require three-way partitioning"
    );
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
    auto rng = std::mt19937_64(task_seed(
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
    if (
      discovery == TslRunDiscoveryKind::INCREMENTAL
      && PartitionKind == TslPartitionKind::THREE_WAY
    ) {
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
      if (
        discovery == TslRunDiscoveryKind::INCREMENTAL
        && PartitionKind == TslPartitionKind::THREE_WAY
      ) {
        process_parallel_task<TslRunDiscoveryKind::INCREMENTAL>(
          columns,
          column_count,
          task,
          schedule,
          offload,
          metrics != nullptr ? &algorithm_metrics : nullptr
        );
      } else {
        process_parallel_task<TslRunDiscoveryKind::POST_SORT>(
          columns,
          column_count,
          task,
          schedule,
          offload,
          metrics != nullptr ? &algorithm_metrics : nullptr
        );
      }
    };

    TslTaskExecutor<TslColumnSortTask, decltype(worker)> executor(
      worker_count,
      worker
    );
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
    }
  }
};
