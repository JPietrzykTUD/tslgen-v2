#pragma once

// Standalone "hybrid leaf" experiment for the multicolumn sort.
//
// -----------------------------------------------------------------------------
// The question
// -----------------------------------------------------------------------------
// The two leaf configurations differ in more than which leaf runs. `NETWORK`
// sets `leaf_threshold` to the bitonic leaf's fixed capacity (256 for u32/AVX-512)
// and sorts every range at or below it with one full-capacity network, padding the
// remainder with the type maximum. `INSERTION` sets the threshold to 64 and sorts
// those with an O(n^2) insertion leaf, partitioning anything larger.
//
// So the network leaf's cost per leaf is constant while insertion's is quadratic:
// the network wins on a well-filled leaf and loses badly on a sparse one. Which of
// the two a sorter meets is decided by the data and by the row count, not by the
// configuration -- u32/AVX-512, three-way, post-sort, eight columns, best of five:
//
//   shape                  rows   insertion   network   diverted   this driver
//   low_cardinality_d4    2^18     12.20 ms  20.08 ms        74%     13.74 ms
//   low_cardinality_d4    2^20     40.04 ms  39.19 ms         0%     39.43 ms
//   skewed_zipf_s1        2^18     20.04 ms 197.86 ms        98%     29.33 ms
//   unique_first          2^20     70.75 ms  57.23 ms         2%     55.80 ms
//
// Four distinct values per column means eight columns produce 4^7 leaf groups, so
// at 2^20 rows the leaves hold exactly 64 elements and at 2^18 only 16. Same
// shape, same column count, opposite winner. `skewed_zipf_s1`'s 9.9x is the fixed
// cost paid on leaves of a handful of elements. Neither leaf is the right answer;
// the leaf's fill ratio is.
//
// -----------------------------------------------------------------------------
// What this varies
// -----------------------------------------------------------------------------
// `TslMultiColumnQuickSorter`'s `HybridFillPercent`: with `LeafKind == NETWORK`, a
// leaf holding less than that percentage of capacity is diverted to the insertion
// leaf. The partition loop still stops at the network's threshold, so the decision
// is per leaf -- which matters, because a range far above the threshold reaches
// leaves whose lengths nothing outside `sort_impl` can see.
//
// The knob spans the whole space, so the sweep has no gap at either end:
//
//   P = 1     only leaves of 2 elements diverted -- the least the rule can do,
//             which on a zipf shape is still 30% of all leaves
//   P = 25    insertion below 64, network above: each leaf goes to the sorter
//             whose fixed configuration would have handled it anyway
//   P = 100   everything below capacity diverted -- always-insertion, but with
//             partitioning stopping at 256 rather than at 64
//
// P = 100 is therefore *not* the `INSERTION` configuration: it insertion-sorts
// leaves up to 256 elements, which is 16x the work per leaf that a threshold of 64
// admits. Both production configurations are measured alongside as baselines.
//
// -----------------------------------------------------------------------------
// Scope
// -----------------------------------------------------------------------------
// Serial, post-sort discovery, direct addressing, and every policy comes out of
// this one driver, so a comparison between them changes exactly one template
// argument. Deliberately not wired into the benchmark corpus: the corpus varies
// the leaf per configuration, and the point here is that the choice may not belong
// there at all.
//
// -----------------------------------------------------------------------------
// What the sweep found
// -----------------------------------------------------------------------------
// No setting beats the better fixed configuration by more than run-to-run noise
// on any single configuration -- so this is not a speedup. What it buys is not
// having to know the shape. Measured against the per-configuration oracle over
// {insertion, network}, over four shapes x {2^18, 2^20} rows x {2, 4, 8} columns:
//
//   policy      geomean   worst case
//   insertion     1.195        1.91x
//   network       1.313        9.87x
//   P = auto      1.044        1.46x
//   P = 50        1.103        1.30x
//
// Picking one fixed leaf for the whole corpus costs 20% (insertion) or 31%
// (network) on average and up to 9.9x in the worst case; the parameter-free
// diversion costs 4% and 1.5x. The residual is the network's own threshold: under
// `auto` a leaf of 64..256 elements still goes to the network as one
// full-capacity sort where the insertion configuration would have partitioned it
// further, which is what `P = 50` trades away for a better worst case.

#include <array>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

#include <tsl.hpp>

#include "cosort_bitonic_leaf.hpp"
#include "equal_runs.hpp"
#include "multicolumn_quicksort.hpp"
#include "multicolumn_sort_types.hpp"


struct TslHybridLeafMetrics {
  std::size_t ranges = 0;            // sort calls over >= 2 elements
  std::size_t rows = 0;              // summed range lengths
  std::size_t below_threshold = 0;   // ranges that never partition: the leaf does it all
  std::size_t leaves_to_network = 0; // leaf calls taken by the network
  std::size_t leaves_to_insertion = 0;   // leaf calls diverted to insertion
  std::size_t network_padding = 0;   // network capacity spent on padding, summed
};


// Owns the lexicographic recursion; the leaf policy is the sorter's type. Held
// behind `TslLeafPolicyRunner` so one sweep can hold policies that differ in a
// template argument.
template <class DataType>
class TslLeafPolicyRunner {
 public:
  virtual ~TslLeafPolicyRunner() = default;
  virtual auto label() const -> std::string = 0;
  // 0 for the fixed policies; the diversion threshold as a percentage otherwise.
  virtual auto fill_percent() const -> std::size_t = 0;
  virtual auto leaf_threshold() const -> std::size_t = 0;
  virtual void sort(
    TslSortColumn<DataType> const * columns,
    std::size_t column_count,
    std::size_t row_count,
    TslHybridLeafMetrics * metrics
  ) = 0;
};


template <
  class DataType,
  TslPartitionKind PartitionKind,
  TslLeafKind LeafKind,
  std::size_t HybridFillPercent,
  std::size_t MaxColumns,
  class SimdStyle
>
class TslLeafPolicySorter final : public TslLeafPolicyRunner<DataType> {
  using Sorter = TslMultiColumnQuickSorter<
    DataType, PartitionKind, LeafKind, MaxColumns, SimdStyle, HybridFillPercent
  >;

  Sorter sorter_;
  std::string label_;
  TslHybridLeafMetrics metrics_{};

 public:
  TslLeafPolicySorter(std::uint64_t seed, std::string label)
      : sorter_(seed), label_(std::move(label)) {}

  static constexpr auto network_capacity() -> std::size_t {
    return TslCoSortBitonicLeaf<DataType, SimdStyle>::capacity;
  }

  auto label() const -> std::string override { return label_; }
  auto fill_percent() const -> std::size_t override { return HybridFillPercent; }
  auto leaf_threshold() const -> std::size_t override { return Sorter::leaf_size_threshold(); }

  void sort(
    TslSortColumn<DataType> const * columns,
    std::size_t column_count,
    std::size_t row_count,
    TslHybridLeafMetrics * metrics
  ) override {
    if (column_count > MaxColumns + 1) {
      throw std::invalid_argument("column count exceeds MaxColumns + 1");
    }
    for (std::size_t column = 0; column < column_count; ++column) {
      if (columns[column].data == nullptr) {
        throw std::invalid_argument("column " + std::to_string(column) + " is null");
      }
    }

    metrics_ = {};
    tsl_leaf_routing = {};
    sort_level(columns, column_count, 0, 0, row_count);
    metrics_.leaves_to_network = tsl_leaf_routing.to_network;
    metrics_.leaves_to_insertion = tsl_leaf_routing.to_insertion;
    metrics_.network_padding = tsl_leaf_routing.network_padding;
    if (metrics != nullptr) {
      *metrics = metrics_;
    }
  }

 private:
  void sort_level(
    TslSortColumn<DataType> const * columns,
    std::size_t column_count,
    std::size_t active_column,
    std::size_t begin,
    std::size_t end
  ) {
    auto const count = end - begin;
    if (count < 2 || active_column >= column_count) {
      return;
    }

    // Payloads are the columns after the active one: those before it are constant
    // across this range, so permuting them would be work with no effect.
    auto const payload_count = column_count - active_column - 1;
    std::array<DataType *, MaxColumns> payloads{};
    for (std::size_t column = active_column + 1; column < column_count; ++column) {
      payloads[column - active_column - 1] = columns[column].data + begin;
    }

    auto * keys = columns[active_column].data;
    ++metrics_.ranges;
    metrics_.rows += count;
    if (count <= Sorter::leaf_size_threshold()) {
      ++metrics_.below_threshold;
    }
    sorter_.sort_key(
      keys + begin, payloads.data(), payload_count, count, columns[active_column].order
    );

    if (active_column + 1 >= column_count) {
      return;
    }
    tsl_for_each_equal_run(keys, begin, end, [&](TslRunSpan span) {
      sort_level(columns, column_count, active_column + 1, span.begin, span.end);
    });
  }
};


// The sweep's policy set: both production configurations, then the hybrid knob
// across its whole range. Percentages are given rather than ratios so they are
// template arguments.
template <
  class DataType,
  TslPartitionKind PartitionKind = TslPartitionKind::THREE_WAY,
  std::size_t MaxColumns = 16,
  class SimdStyle = tsl::dataparallel::simd_for_t<tsl::dataparallel::native, DataType>
>
auto tsl_leaf_policies(std::uint64_t seed)
  -> std::vector<std::unique_ptr<TslLeafPolicyRunner<DataType>>> {
  std::vector<std::unique_ptr<TslLeafPolicyRunner<DataType>>> policies;

  auto add = [&](auto runner) { policies.push_back(std::move(runner)); };

  constexpr std::size_t auto_percent = tsl_hybrid_auto_percent<DataType, SimdStyle>();

  add(std::make_unique<TslLeafPolicySorter<
    DataType, PartitionKind, TslLeafKind::INSERTION, 0, MaxColumns, SimdStyle>>(seed, "ins"));
  add(std::make_unique<TslLeafPolicySorter<
    DataType, PartitionKind, TslLeafKind::NETWORK, 0, MaxColumns, SimdStyle>>(seed, "net"));
  add(std::make_unique<TslLeafPolicySorter<
    DataType, PartitionKind, TslLeafKind::NETWORK, 1, MaxColumns, SimdStyle>>(seed, "hyb@1"));
  add(std::make_unique<TslLeafPolicySorter<
    DataType, PartitionKind, TslLeafKind::NETWORK, 6, MaxColumns, SimdStyle>>(seed, "hyb@6"));
  add(std::make_unique<TslLeafPolicySorter<
    DataType, PartitionKind, TslLeafKind::NETWORK, 13, MaxColumns, SimdStyle>>(seed, "hyb@13"));
  add(std::make_unique<TslLeafPolicySorter<
    DataType, PartitionKind, TslLeafKind::NETWORK, auto_percent, MaxColumns, SimdStyle>>(
      seed, "hyb@auto"));
  add(std::make_unique<TslLeafPolicySorter<
    DataType, PartitionKind, TslLeafKind::NETWORK, 38, MaxColumns, SimdStyle>>(seed, "hyb@38"));
  add(std::make_unique<TslLeafPolicySorter<
    DataType, PartitionKind, TslLeafKind::NETWORK, 50, MaxColumns, SimdStyle>>(seed, "hyb@50"));
  add(std::make_unique<TslLeafPolicySorter<
    DataType, PartitionKind, TslLeafKind::NETWORK, 75, MaxColumns, SimdStyle>>(seed, "hyb@75"));
  add(std::make_unique<TslLeafPolicySorter<
    DataType, PartitionKind, TslLeafKind::NETWORK, 100, MaxColumns, SimdStyle>>(seed, "hyb@100"));
  return policies;
}
