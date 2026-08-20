#pragma once

// Indirect multi-column sort: sorts a row-index permutation and leaves the
// columns untouched.
//
// The shape is taken from the `cluster_tail ... materialize` experiment in
// TMP/tsl_sort: instead of permuting every column at every recursion level, keep
// one index array and, per column, gather that column through the index into a
// contiguous scratch buffer once. The partition then reads its keys sequentially
// from that buffer, and the only array it permutes is the index.
//
// What differs from that prototype is the partition and the discovery. The swap
// is our two-register stitch (`TslPartitionReplayStep` via
// `TslMultiColumnQuickSorter`, with the index as its single payload column),
// which writes both registers back to the addresses it read and therefore needs
// none of the moving-write-cursor bookkeeping -- no per-array four-register
// lookahead, no consume-side choice, no drain cases. And run discovery goes
// through the detector seam, so `rle=` applies here exactly as it does to the
// direct sorter.
//
// -----------------------------------------------------------------------------
// Why the scratch buffer is the point
// -----------------------------------------------------------------------------
// `scratch[s..e)` holds the active column, in index order, contiguously. That is
// precisely the input `tsl_for_each_equal_run`, DSA's `create_delta` and IAA's
// `scan_eq` all require. A detector needs no indirection and no per-range
// materialization -- contrast dsa_rle_cluster_detection::detect_indexed in the
// prototype, which has to gather into a temporary vector before create_delta can
// see anything, and only for 8-byte elements.
//
// -----------------------------------------------------------------------------
// The level structure
// -----------------------------------------------------------------------------
//   ranges = {[0, n)}
//   for each column j:
//     for each range in ranges:            (disjoint, ascending)
//       materialize scratch[range] = column_j[index[range]]
//       sort (scratch[range], index[range]) on the key
//       discover the equal runs inside it  -> next level's ranges
//     ranges = next
//
// Only rows inside a surviving range are ever materialized, so the gather work
// per level is the number of still-tied rows rather than the whole column. The
// prototype materializes the full column at every level; this shrinks with depth
// the same way the direct sorter's payload set does.
//
// Level 0 is a straight copy: the index is the identity there, so a gather would
// be one too.
//
// -----------------------------------------------------------------------------
// Contract and limits
// -----------------------------------------------------------------------------
//   * `sort_index` fills the index with 0..n-1 itself, so the identity
//     precondition that makes the level-0 copy valid cannot be violated by a
//     caller.
//   * The index element type is the data type. The stitch replays a key mask on
//     payload registers of the same style, so the index has to share the key's
//     lane layout; a narrower or wider index would need the mask re-spacing the
//     prototype's compress_store_index_array does. u32 keys cap a table at 2^32
//     rows, which every configuration here is far below.
//   * Synchronous detectors only. An asynchronous one needs a task executor to
//     poll it, and this driver is serial; the static_assert below says so rather
//     than deadlocking.
//   * The output is a permutation, not a sorted image. Ties leave the index
//     order unspecified (the partition is not stable), so a checker must compare
//     the *values* the permutation selects, not the permutation itself.

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <utility>
#include <vector>

#include <tsl.hpp>

#include "equal_runs.hpp"
#include "multicolumn_quicksort.hpp"
#include "multicolumn_sort_types.hpp"


struct TslIndexSortMetrics {
  std::size_t levels = 0;                  // columns that actually did work
  std::size_t ranges_sorted = 0;
  std::size_t rows_sorted = 0;             // summed range lengths handed to the sort
  std::size_t materialized_elements = 0;   // gather (or level-0 copy) traffic
  std::size_t rle_values_scanned = 0;      // elements handed to the detector
  std::size_t direct_equal_bands = 0;      // bands the sort reported without a scan
  std::size_t direct_equal_band_rows = 0;
  std::size_t next_level_ranges = 0;       // tied ranges passed down, summed
};


// The portable detector, in the same call shape the accelerator fleets use, so a
// caller that does not care about `rle=` need not name one.
template <class DataType>
struct TslIndexScalarDetector {
  template <class Emit>
  void operator()(DataType const * values, std::size_t begin, std::size_t end, Emit && emit) {
    tsl_for_each_equal_run(values, begin, end, std::forward<Emit>(emit));
  }
};


template <
  class DataType = std::uint32_t,
  TslPartitionKind PartitionKind = TslPartitionKind::THREE_WAY,
  TslLeafKind LeafKind = TslLeafKind::NETWORK,
  class SimdStyle = tsl::dataparallel::simd_for_t<tsl::dataparallel::native, DataType>
>
class TslMultiColumnIndexSorter {
  static_assert(std::is_integral_v<DataType>, "the index sort needs an integral element type");
  static_assert(std::is_unsigned_v<DataType>, "the index is stored in the element type");
  static_assert(std::is_same_v<typename SimdStyle::base_type, DataType>,
                "SimdStyle::base_type must match DataType");

  // One payload: the index. The key column is the materialized scratch buffer.
  using Sorter = TslMultiColumnQuickSorter<DataType, PartitionKind, LeafKind, 1, SimdStyle>;
  using register_type = typename SimdStyle::register_type;
  static constexpr std::size_t lane_count = SimdStyle::lane_count_v;

  Sorter sorter_;
  std::vector<DataType> scratch_;
  std::vector<TslRunSpan> ranges_;
  std::vector<TslRunSpan> next_ranges_;

 public:
  explicit TslMultiColumnIndexSorter(std::uint64_t seed) : sorter_(seed) {}

  static constexpr auto leaf_size_threshold() -> std::size_t {
    return Sorter::leaf_size_threshold();
  }

  // Sorts `index` so that `columns[c][index[0..row_count)]` is lexicographically
  // ordered over c. `columns` is read only.
  template <class DetectRuns>
  void sort_index(
    TslSortColumn<DataType> const * columns,
    std::size_t column_count,
    DataType * index,
    std::size_t row_count,
    TslRunDiscoveryKind discovery,
    DetectRuns & detect_runs,
    TslIndexSortMetrics * metrics = nullptr
  ) {
    static_assert(
      !tsl_detector_wants_executor<DetectRuns>::value,
      "the index sort is serial and never polls: an asynchronous detector would "
      "never complete. Use a synchronous backend."
    );
    if (columns == nullptr && column_count != 0) {
      throw std::invalid_argument("column array is null");
    }
    if (row_count != 0 && index == nullptr) {
      throw std::invalid_argument("index pointer is null");
    }
    for (std::size_t column = 0; column < column_count; ++column) {
      if (columns[column].data == nullptr) {
        throw std::invalid_argument("column " + std::to_string(column) + " has a null pointer");
      }
    }

    // The identity the level-0 copy relies on.
    for (std::size_t row = 0; row < row_count; ++row) {
      index[row] = static_cast<DataType>(row);
    }
    if (row_count < 2 || column_count == 0) {
      return;
    }
    if (row_count > static_cast<std::size_t>(std::numeric_limits<DataType>::max())) {
      throw std::invalid_argument("row count exceeds what the index element type can address");
    }

    scratch_.resize(row_count);
    ranges_.clear();
    ranges_.push_back(TslRunSpan{0, row_count});

    for (std::size_t column = 0; column < column_count && !ranges_.empty(); ++column) {
      next_ranges_.clear();
      if (metrics != nullptr) {
        ++metrics->levels;
      }

      for (auto const range : ranges_) {
        if (range.end - range.begin < 2) {
          continue;
        }
        materialize(columns[column].data, index, range, column == 0, metrics);
        sort_range(index, range, columns[column].order, discovery, detect_runs, metrics);
      }

      // Incremental discovery reports completions in whatever order partitions
      // finish; sorting keeps the next level's materialize pass sequential. The
      // post-sort path emits ascending already.
      if (discovery == TslRunDiscoveryKind::INCREMENTAL) {
        std::sort(
          next_ranges_.begin(), next_ranges_.end(),
          [](TslRunSpan left, TslRunSpan right) { return left.begin < right.begin; }
        );
      }
      ranges_.swap(next_ranges_);
    }
  }

  // Convenience overload: the scalar detector, for callers not exercising `rle=`.
  void sort_index(
    TslSortColumn<DataType> const * columns,
    std::size_t column_count,
    DataType * index,
    std::size_t row_count,
    TslRunDiscoveryKind discovery = TslRunDiscoveryKind::POST_SORT,
    TslIndexSortMetrics * metrics = nullptr
  ) {
    TslIndexScalarDetector<DataType> detector;
    sort_index(columns, column_count, index, row_count, discovery, detector, metrics);
  }

 private:
  // scratch[i] = column[index[i]] for i in the range. At level 0 the index is
  // the identity, so the gather would be one: copy instead.
  void materialize(
    DataType const * column,
    DataType const * index,
    TslRunSpan range,
    bool identity,
    TslIndexSortMetrics * metrics
  ) {
    auto const count = range.end - range.begin;
    if (metrics != nullptr) {
      metrics->materialized_elements += count;
    }
    if (identity) {
      std::copy(column + range.begin, column + range.end, scratch_.data() + range.begin);
      return;
    }
    auto position = range.begin;
    for (; position + lane_count <= range.end; position += lane_count) {
      auto const index_reg = tsl::load<SimdStyle, false>(index + position);
      auto const values = tsl::gather<
        SimdStyle, SimdStyle, static_cast<std::uint32_t>(sizeof(DataType))
      >(column, index_reg);
      tsl::store<SimdStyle, false>(scratch_.data() + position, values);
    }
    for (; position < range.end; ++position) {
      scratch_[position] = column[index[position]];
    }
  }

  // Sorts one range on the materialized key and records the tied sub-ranges the
  // next column has to break.
  template <class DetectRuns>
  void sort_range(
    DataType * index,
    TslRunSpan range,
    TslSortOrder order,
    TslRunDiscoveryKind discovery,
    DetectRuns & detect_runs,
    TslIndexSortMetrics * metrics
  ) {
    auto const count = range.end - range.begin;
    if (metrics != nullptr) {
      ++metrics->ranges_sorted;
      metrics->rows_sorted += count;
    }

    DataType * payload = index + range.begin;
    DataType * const * payloads = &payload;
    auto * keys = scratch_.data() + range.begin;

    auto keep = [&](TslRunSpan span) {
      if (span.end - span.begin < 2) {
        return;
      }
      if (metrics != nullptr) {
        metrics->next_level_ranges += span.end - span.begin;
      }
      next_ranges_.push_back(span);
    };

    if (discovery == TslRunDiscoveryKind::POST_SORT) {
      sorter_.sort_key(keys, payloads, 1, count, order);
      if (metrics != nullptr) {
        metrics->rle_values_scanned += count;
      }
      detect_runs(scratch_.data(), range.begin, range.end, keep);
      return;
    }

    // Incremental: the partition hands back pivot-equal bands, which are tied by
    // construction and need no scan, plus completed leaf ranges, which do.
    auto equal_band_sink = [&](std::size_t band_begin, std::size_t band_end) {
      if (metrics != nullptr) {
        ++metrics->direct_equal_bands;
        metrics->direct_equal_band_rows += band_end - band_begin;
      }
      keep(TslRunSpan{band_begin, band_end});
    };
    auto leaf_sink = [&](std::size_t leaf_begin, std::size_t leaf_end) {
      if (metrics != nullptr) {
        metrics->rle_values_scanned += leaf_end - leaf_begin;
      }
      detect_runs(scratch_.data(), leaf_begin, leaf_end, keep);
    };
    sorter_.sort_key_with_completion_events(
      keys, payloads, 1, count, order, range.begin, equal_band_sink, leaf_sink
    );
  }
};
