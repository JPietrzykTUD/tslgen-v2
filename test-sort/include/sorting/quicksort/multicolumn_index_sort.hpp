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
//   * `sort_index` is serial and calls the detector on the calling thread.
//     `sort_index_parallel` drives a task tree and calls it from workers, so it
//     needs a detector safe for concurrent use -- a fleet or a stateless one --
//     exactly as `sort_columns_parallel` does.
//   * Synchronous detectors only, on both paths. An asynchronous one retains the
//     emitting callable past the task that produced it, and the child-submitting
//     emitters here are not yet self-contained; the static_assert says so rather
//     than letting it dangle.
//   * The output is a permutation, not a sorted image. Ties leave the index
//     order unspecified (the partition is not stable), so a checker must compare
//     the *values* the permutation selects, not the permutation itself.

#include <chrono>
#include <algorithm>
#include <atomic>
#include <cstddef>
#include <condition_variable>
#include <cstdint>
#include <functional>
#include <mutex>
#include <thread>
#include <limits>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <utility>
#include <vector>

#include <tsl.hpp>

#include "cluster_detection/scalar/equal_runs.hpp"
#include "sorting/quicksort/multicolumn_quicksort.hpp"
#include "sorting/common/multicolumn_sort_tasks.hpp"
#include "sorting/common/multicolumn_sort_types.hpp"


// Chunk of one range's materialize pass, the unit the parallel form hands out.
struct TslIndexMaterializeChunk {
  std::size_t begin = 0;
  std::size_t end = 0;
};

// Below this a range's gather is not worth splitting: the chunk hand-off costs
// more than the pass saves. Levels past the first have many small ranges, and
// those are parallelized across ranges instead.
inline constexpr std::size_t tsl_index_materialize_chunk = 64 * 1024;
// A level holding one range has no ranges to spread, so its sort is split inside
// the partition instead, through `TslMultiColumnQuickSorter::sort_key_parallel`.
// Below this the split is not worth an executor.
inline constexpr std::size_t tsl_index_parallel_range = 1u << 18;
// Partition subranges smaller than this stay with the worker that made them.
inline constexpr std::size_t tsl_index_partition_threshold = 16 * 1024;
// A discovered range below this is finished by the worker that found it rather
// than queued: re-entering a task costs more than the range does.
//
// Deliberately small, because the two failure modes are not symmetric. Queueing a
// range that was too small to bother with costs a constant. Inlining one that was
// large enough to share costs a whole level's parallelism -- every child of a
// range is discovered by the *one* thread that sorted it, so if they all fall
// under this threshold they all run on that thread. Measured on 4 Mi rows over 8
// columns whose second level holds ranges of about a thousand rows: a threshold of
// 1024 gives 1.99x on 8 workers, 256 gives 4.18x, 64 gives 4.31x.
inline constexpr std::size_t tsl_index_inline_task = 256;


struct TslIndexSortMetrics {
  std::size_t levels = 0;                  // columns that actually did work
  std::size_t ranges_sorted = 0;
  std::size_t rows_sorted = 0;             // summed range lengths handed to the sort
  std::size_t materialized_elements = 0;   // gather (or level-0 copy) traffic
  std::size_t rle_values_scanned = 0;      // elements handed to the detector
  std::size_t direct_equal_bands = 0;      // bands the sort reported without a scan
  std::size_t direct_equal_band_rows = 0;
  std::size_t next_level_ranges = 0;       // tied ranges passed down, summed
  std::size_t materialize_chunks = 0;      // parallel form: chunks handed out
  std::size_t tasks = 0;                   // parallel form: task-tree nodes executed
  std::size_t levels_split = 0;            // ranges split inside their partitions
  // Filled only when the sorter is instantiated with profiling on. Wall time per
  // phase, summed across workers, so on threads these exceed the elapsed time and
  // only their ratio means anything. They exist to answer "where did the time go"
  // when a thread count makes the sort slower rather than faster: the three phases
  // scale for different reasons -- the gather is memory-bound, the sort is the
  // task tree, and detection is whatever the `rle=` backend does under contention.
  double ns_materialize = 0.0;
  double ns_sort = 0.0;
  double ns_detect = 0.0;
};

// Nanoseconds since a mark, as a double. Local to the profiling paths.
inline auto tsl_index_since(std::chrono::steady_clock::time_point mark) -> double {
  return std::chrono::duration<double, std::nano>(
    std::chrono::steady_clock::now() - mark).count();
}


// The portable detector, in the same call shape the accelerator fleets use, so a
// caller that does not care about `rle=` need not name one.


template <
  class DataType = std::uint32_t,
  TslPartitionKind PartitionKind = TslPartitionKind::THREE_WAY,
  TslLeafKind LeafKind = TslLeafKind::NETWORK,
  class SimdStyle = tsl::dataparallel::simd_for_t<tsl::dataparallel::native, DataType>,
  // Forwarded to the inner sorter: with `LeafKind == NETWORK`, divert a leaf
  // holding less than this share of the network's capacity to the insertion leaf.
  // 0 keeps the leaf fixed. See `tsl_hybrid_auto_percent`.
  std::size_t HybridFillPercent = 0,
  // Time the materialize / sort / detect phases into the metrics. Off by default
  // because the clock reads sit on the per-range path, and a caller that only
  // wants the sort should not pay for them.
  bool Profile = false
>
class TslMultiColumnIndexSorter {
  static_assert(std::is_integral_v<DataType>, "the index sort needs an integral element type");
  static_assert(std::is_unsigned_v<DataType>, "the index is stored in the element type");
  static_assert(std::is_same_v<typename SimdStyle::base_type, DataType>,
                "SimdStyle::base_type must match DataType");

  // One payload: the index. The key column is the materialized scratch buffer.
  using Sorter =
    TslMultiColumnQuickSorter<DataType, PartitionKind, LeafKind, 1, SimdStyle,
                              HybridFillPercent>;

  using register_type = typename SimdStyle::register_type;
  static constexpr std::size_t lane_count = SimdStyle::lane_count_v;

  // One node of the parallel task tree. `materialized` says the range's values
  // are already in `scratch_`, which is true for the root (a pre-pass filled
  // column 0) and false for a child, which owns a new column.
  struct index_task {
    std::size_t column;
    std::size_t begin;
    std::size_t end;
    bool materialized;
  };

  // Counters written from worker threads. Copied into the caller's struct once
  // the tree has drained.
  struct concurrent_index_metrics {
    std::atomic<std::uint64_t> column_mask{0};
    std::atomic<std::size_t> tasks{0};
    std::atomic<std::size_t> ranges_sorted{0};
    std::atomic<std::size_t> rows_sorted{0};
    std::atomic<std::size_t> materialized_elements{0};
    std::atomic<std::size_t> rle_values_scanned{0};
    std::atomic<std::size_t> direct_equal_bands{0};
    std::atomic<std::size_t> direct_equal_band_rows{0};
    std::atomic<std::size_t> next_level_ranges{0};
    std::atomic<std::size_t> materialize_chunks{0};
    std::atomic<std::size_t> levels_split{0};
    // Nanoseconds, integral so the accumulation is lock-free.
    std::atomic<std::uint64_t> ns_materialize{0};
    std::atomic<std::uint64_t> ns_sort{0};
    std::atomic<std::uint64_t> ns_detect{0};
  };

  Sorter sorter_;
  std::size_t workers_ = 1;
  std::size_t partition_threshold_ = tsl_index_partition_threshold;
  std::vector<DataType> scratch_;
  // Second copy of the materialized keys, written by the same gather that writes
  // `scratch_`, for a detector that wants the values before the sort permutes
  // them. Sized only when such a detector is in use.
  std::vector<DataType> stable_keys_;
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
    validate_inputs(columns, column_count, index, row_count);

    // The identity the level-0 copy relies on.
    for (std::size_t row = 0; row < row_count; ++row) {
      index[row] = static_cast<DataType>(row);
    }
    if (row_count < 2 || column_count == 0) {
      return;
    }
    scratch_.resize(row_count);
    if constexpr (tsl_detector_wants_prepare<DetectRuns, DataType>::value) {
      stable_keys_.resize(row_count);
    }
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
        if constexpr (Profile) {
          auto const mark = std::chrono::steady_clock::now();
          materialize(columns[column].data, index, range, column == 0, metrics);
          if (metrics != nullptr) {
            metrics->ns_materialize += tsl_index_since(mark);
          }
        } else {
          materialize(columns[column].data, index, range, column == 0, metrics);
        }
        sort_range(index, range, columns[column], column == 0, discovery, detect_runs, metrics);
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

  // Same sort, driven as a task tree instead of a level loop. A task is one
  // (column, range): it materializes the range, sorts it, and submits a child
  // task per tied sub-range it discovers. Children run as soon as they exist, so
  // there is no barrier between columns and a worker that finishes a small range
  // does not wait for the largest one in its level.
  //
  // Two consequences for the caller:
  //
  //   * `detect_runs` is invoked from worker threads, so it must be safe for
  //     concurrent use -- a fleet (`TslIaaDetectorFleet`, `TslDsaDetectorFleet`)
  //     or a stateless detector. This is the same contract
  //     `sort_columns_parallel` has, for the same reason.
  //   * Column 0 is one range, so the tree has nothing to spread there. Its copy
  //     is filled by a one-shot fan-out before the tree starts, and its sort is
  //     split inside its partitions through `sort_key_parallel`.
  template <class DetectRuns>
  void sort_index_parallel(
    TslSortColumn<DataType> const * columns,
    std::size_t column_count,
    DataType * index,
    std::size_t row_count,
    TslRunDiscoveryKind discovery,
    DetectRuns & detect_runs,
    std::size_t worker_count,
    std::size_t partition_threshold,
    TslIndexSortMetrics * metrics = nullptr
  ) {
    static_assert(
      !tsl_detector_wants_executor<DetectRuns>::value,
      "an asynchronous detector retains the emitting callable past the task that "
      "produced it, and this driver's child-submitting emitters are not yet "
      "self-contained. Use a synchronous backend."
    );
    if (worker_count <= 1) {
      sort_index(columns, column_count, index, row_count, discovery, detect_runs, metrics);
      return;
    }
    validate_inputs(columns, column_count, index, row_count);
    for (std::size_t row = 0; row < row_count; ++row) {
      index[row] = static_cast<DataType>(row);
    }
    if (row_count < 2 || column_count == 0) {
      return;
    }
    scratch_.resize(row_count);
    if constexpr (tsl_detector_wants_prepare<DetectRuns, DataType>::value) {
      stable_keys_.resize(row_count);
    }
    workers_ = worker_count;
    partition_threshold_ = partition_threshold != 0
      ? partition_threshold
      : tsl_index_partition_threshold;

    concurrent_index_metrics shared;
    auto * shared_metrics = metrics != nullptr ? &shared : nullptr;

    // Column 0's fetch is a copy of the whole table, and the tree cannot spread
    // it: the root task is the only task that exists yet. A one-shot executor
    // does it first, which is all `TslTaskExecutor` supports and all that is
    // needed. Only the copy -- a gather does not scale this way.
    auto const chunk =
      ((tsl_index_materialize_chunk + lane_count - 1) / lane_count) * lane_count;
    if (row_count >= 2 * tsl_index_materialize_chunk) {
      auto const * source = columns[0].data;
      auto copy_worker = [this, source, chunk, row_count](
        TslIndexMaterializeChunk const & piece, auto &
      ) {
        (void)chunk;
        (void)row_count;
        std::copy(source + piece.begin, source + piece.end, scratch_.data() + piece.begin);
      };
      TslTaskExecutor<TslIndexMaterializeChunk, decltype(copy_worker)> copier(
        worker_count, copy_worker
      );
      for (std::size_t begin = 0; begin < row_count; begin += chunk) {
        copier.submit(TslIndexMaterializeChunk{begin, std::min(begin + chunk, row_count)});
        if (shared_metrics != nullptr) {
          shared_metrics->materialize_chunks.fetch_add(1, std::memory_order_relaxed);
        }
      }
      copier.wait();
    } else {
      std::copy(columns[0].data, columns[0].data + row_count, scratch_.data());
    }
    if (shared_metrics != nullptr) {
      shared_metrics->materialized_elements.fetch_add(row_count, std::memory_order_relaxed);
    }

    auto worker = [&](index_task const & task, auto & executor) {
      process_task(columns, column_count, index, task, discovery, detect_runs,
                   executor, shared_metrics);
    };
    TslTaskExecutor<index_task, decltype(worker)> executor(worker_count, worker);
    // The root's values are already in scratch_, so it does not fetch them again.
    executor.submit(index_task{0, 0, row_count, true});
    executor.wait();

    if (metrics != nullptr) {
      metrics->levels = static_cast<std::size_t>(
        __builtin_popcountll(shared.column_mask.load(std::memory_order_relaxed))
      );
      metrics->ranges_sorted = shared.ranges_sorted.load(std::memory_order_relaxed);
      metrics->rows_sorted = shared.rows_sorted.load(std::memory_order_relaxed);
      metrics->materialized_elements =
        shared.materialized_elements.load(std::memory_order_relaxed);
      metrics->rle_values_scanned = shared.rle_values_scanned.load(std::memory_order_relaxed);
      metrics->direct_equal_bands = shared.direct_equal_bands.load(std::memory_order_relaxed);
      metrics->direct_equal_band_rows =
        shared.direct_equal_band_rows.load(std::memory_order_relaxed);
      metrics->next_level_ranges = shared.next_level_ranges.load(std::memory_order_relaxed);
      if constexpr (Profile) {
        metrics->ns_materialize =
          static_cast<double>(shared.ns_materialize.load(std::memory_order_relaxed));
        metrics->ns_sort =
          static_cast<double>(shared.ns_sort.load(std::memory_order_relaxed));
        metrics->ns_detect =
          static_cast<double>(shared.ns_detect.load(std::memory_order_relaxed));
      }
      metrics->materialize_chunks = shared.materialize_chunks.load(std::memory_order_relaxed);
      metrics->levels_split = shared.levels_split.load(std::memory_order_relaxed);
      metrics->tasks = shared.tasks.load(std::memory_order_relaxed);
    }
  }

  template <class DetectRuns>
  void sort_index_parallel(
    TslSortColumn<DataType> const * columns,
    std::size_t column_count,
    DataType * index,
    std::size_t row_count,
    TslRunDiscoveryKind discovery,
    DetectRuns & detect_runs,
    std::size_t worker_count,
    TslIndexSortMetrics * metrics = nullptr
  ) {
    sort_index_parallel(columns, column_count, index, row_count, discovery, detect_runs,
                        worker_count, tsl_index_partition_threshold, metrics);
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
    materialize_chunk(column, index, range.begin, range.end, identity);
  }

  // One chunk of a gather pass. Chunks are cut on a lane boundary, so the vector
  // body of every chunk is aligned to the same stride the serial pass uses and no
  // chunk needs a scalar prologue.
  void materialize_chunk(
    DataType const * column,
    DataType const * index,
    std::size_t begin,
    std::size_t end,
    bool identity
  ) {
    // `mirror` is null unless a detector asked to see the keys before the sort.
    // Writing it here costs one extra store per vector inside a pass that already
    // runs, where a detector-side snapshot would be a second read/write pass.
    auto * const mirror = stable_keys_.empty() ? nullptr : stable_keys_.data();
    if (identity) {
      // The source column is itself a stable copy, so nothing is mirrored: the
      // caller prepares on `column` directly.
      std::copy(column + begin, column + end, scratch_.data() + begin);
      return;
    }
    auto position = begin;
    for (; position + lane_count <= end; position += lane_count) {
      auto const index_reg = tsl::load<SimdStyle, false>(index + position);
      auto const values = tsl::gather<
        SimdStyle, SimdStyle, static_cast<std::uint32_t>(sizeof(DataType))
      >(column, index_reg);
      tsl::store<SimdStyle, false>(scratch_.data() + position, values);
      if (mirror != nullptr) {
        tsl::store<SimdStyle, false>(mirror + position, values);
      }
    }
    for (; position < end; ++position) {
      scratch_[position] = column[index[position]];
      if (mirror != nullptr) {
        mirror[position] = scratch_[position];
      }
    }
  }

  // Hands a detector the range's values before the sort permutes them, from a
  // buffer that will not change: the source column at level 0, where the index is
  // the identity and the column is read-only for the whole sort, and the gather's
  // mirror below it. Either way no copy is made here.
  template <class DetectRuns>
  void prepare_detector(
    DetectRuns & detect_runs,
    DataType const * column,
    std::size_t begin,
    std::size_t end,
    bool identity
  ) {
    if constexpr (tsl_detector_wants_prepare<DetectRuns, DataType>::value) {
      auto const * source = identity ? column : stable_keys_.data();
      detect_runs.prepare(source, begin, end, true);
    } else {
      (void)detect_runs;
      (void)column;
      (void)begin;
      (void)end;
      (void)identity;
    }
  }

  void validate_inputs(
    TslSortColumn<DataType> const * columns,
    std::size_t column_count,
    DataType const * index,
    std::size_t row_count
  ) const {
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
    if (row_count > static_cast<std::size_t>(std::numeric_limits<DataType>::max())) {
      throw std::invalid_argument("row count exceeds what the index element type can address");
    }
  }

  // One node of the task tree: fetch this range's column values unless they are
  // already in `scratch_`, sort it, and submit a child per tied sub-range. Column
  // 0 additionally splits its own partitions, because while the root is the only
  // task the tree has nothing to spread.
  template <class DetectRuns, class Executor>
  void process_task(
    TslSortColumn<DataType> const * columns,
    std::size_t column_count,
    DataType * index,
    index_task const & task,
    TslRunDiscoveryKind discovery,
    DetectRuns & detect_runs,
    Executor & executor,
    concurrent_index_metrics * metrics
  ) {
    auto const count = task.end - task.begin;
    if (count < 2 || task.column >= column_count) {
      return;
    }
    if (metrics != nullptr) {
      metrics->tasks.fetch_add(1, std::memory_order_relaxed);
      metrics->ranges_sorted.fetch_add(1, std::memory_order_relaxed);
      metrics->rows_sorted.fetch_add(count, std::memory_order_relaxed);
      metrics->column_mask.fetch_or(
        std::uint64_t{1} << std::min<std::size_t>(task.column, 63),
        std::memory_order_relaxed
      );
    }
    if (!task.materialized) {
      auto const mark = std::chrono::steady_clock::now();
      materialize_chunk(columns[task.column].data, index, task.begin, task.end, false);
      if (metrics != nullptr) {
        metrics->materialized_elements.fetch_add(count, std::memory_order_relaxed);
        if constexpr (Profile) {
          metrics->ns_materialize.fetch_add(
            static_cast<std::uint64_t>(tsl_index_since(mark)),
            std::memory_order_relaxed);
        }
      }
    }

    auto * keys = scratch_.data() + task.begin;
    DataType * payload = index + task.begin;
    DataType * const * payloads = &payload;
    auto const order = columns[task.column].order;
    auto const next_column = task.column + 1;
    auto const split = task.column == 0 && count >= tsl_index_parallel_range;

    // A small child runs inline, which means the whole child subtree executes
    // inside whatever call emitted it -- and the emitting call is a detector
    // callback. Timing the detector by bracketing it would therefore charge every
    // nested materialize and sort to detection, which is how it first came out at
    // fifteen times the total runtime. The inline time is accumulated here and
    // subtracted by the caller. Atomic because `split` fans one range across
    // workers, so the sink runs concurrently.
    std::atomic<std::uint64_t> inline_ns{0};
    auto emit_child = [&executor, metrics, next_column, column_count,
                       &inline_ns](TslRunSpan span) {
      if (span.end - span.begin < 2 || next_column >= column_count) {
        return;
      }
      if (metrics != nullptr) {
        metrics->next_level_ranges.fetch_add(span.end - span.begin, std::memory_order_relaxed);
      }
      index_task child{next_column, span.begin, span.end, false};
      if (span.end - span.begin < tsl_index_inline_task) {
        if constexpr (Profile) {
          auto const mark = std::chrono::steady_clock::now();
          executor.run_inline(child);
          inline_ns.fetch_add(static_cast<std::uint64_t>(tsl_index_since(mark)),
                              std::memory_order_relaxed);
        } else {
          executor.run_inline(child);
        }
      } else {
        executor.submit(child);
      }
    };

    if (discovery == TslRunDiscoveryKind::POST_SORT) {
      prepare_detector(detect_runs, columns[task.column].data, task.begin, task.end,
                       task.column == 0);
      auto const t_sort = std::chrono::steady_clock::now();
      if (split) {
        auto no_band = [](std::size_t, std::size_t) {};
        auto no_leaf = [](std::size_t, std::size_t) {};
        sorter_.sort_key_parallel(keys, payloads, 1, count, order, task.begin,
                                  workers_, 1, partition_threshold_, no_band, no_leaf);
        if (metrics != nullptr) {
          metrics->levels_split.fetch_add(1, std::memory_order_relaxed);
        }
      } else {
        sorter_.sort_key(keys, payloads, 1, count, order);
      }
      if (metrics != nullptr) {
        if constexpr (Profile) {
          metrics->ns_sort.fetch_add(
            static_cast<std::uint64_t>(tsl_index_since(t_sort)),
            std::memory_order_relaxed);
        }
        metrics->rle_values_scanned.fetch_add(count, std::memory_order_relaxed);
      }
      // Sound here and not inside a partition: the whole range is sorted by now,
      // so no equal run can be split between two scans.
      auto const t_detect = std::chrono::steady_clock::now();
      detect_runs(scratch_.data(), task.begin, task.end, emit_child);
      if (metrics != nullptr) {
        if constexpr (Profile) {
          auto const spent = static_cast<std::uint64_t>(tsl_index_since(t_detect));
          auto const nested = inline_ns.load(std::memory_order_relaxed);
          metrics->ns_detect.fetch_add(spent > nested ? spent - nested : 0,
                                       std::memory_order_relaxed);
        }
      }
      return;
    }

    auto equal_band_sink = [&](std::size_t begin, std::size_t end) {
      if (metrics != nullptr) {
        metrics->direct_equal_bands.fetch_add(1, std::memory_order_relaxed);
        metrics->direct_equal_band_rows.fetch_add(end - begin, std::memory_order_relaxed);
      }
      emit_child(TslRunSpan{begin, end});
    };
    // As in the serial form: detection runs from inside the sort, so it is
    // accumulated here and subtracted from the enclosing duration. `split` fans
    // this range across workers, so the sink runs on several threads at once and
    // the accumulator is atomic.
    std::atomic<std::uint64_t> detect_ns{0};
    auto leaf_sink = [&](std::size_t begin, std::size_t end) {
      if (metrics != nullptr) {
        metrics->rle_values_scanned.fetch_add(end - begin, std::memory_order_relaxed);
      }
      auto const mark = std::chrono::steady_clock::now();
      detect_runs(scratch_.data(), begin, end, emit_child);
      if constexpr (Profile) {
        detect_ns.fetch_add(static_cast<std::uint64_t>(tsl_index_since(mark)),
                            std::memory_order_relaxed);
      }
    };
    auto const t_sort = std::chrono::steady_clock::now();
    if (split) {
      sorter_.sort_key_parallel(keys, payloads, 1, count, order, task.begin,
                                workers_, 1, partition_threshold_,
                                equal_band_sink, leaf_sink);
      if (metrics != nullptr) {
        metrics->levels_split.fetch_add(1, std::memory_order_relaxed);
      }
    } else {
      sorter_.sort_key_with_completion_events(
        keys, payloads, 1, count, order, task.begin, equal_band_sink, leaf_sink
      );
    }
    if (metrics != nullptr) {
      if constexpr (Profile) {
        // The sort encloses detection, which itself encloses any inline child
        // subtree. Both are removed so the three phases stay disjoint.
        auto const nested_detect = detect_ns.load(std::memory_order_relaxed);
        auto const nested_inline = inline_ns.load(std::memory_order_relaxed);
        auto const total = static_cast<std::uint64_t>(tsl_index_since(t_sort));
        auto const own = nested_detect + nested_inline;
        metrics->ns_sort.fetch_add(total > own ? total - own : 0,
                                   std::memory_order_relaxed);
        metrics->ns_detect.fetch_add(
          nested_detect > nested_inline ? nested_detect - nested_inline : 0,
          std::memory_order_relaxed);
      }
    }
  }

  // Sorts one range on the materialized key and records the tied sub-ranges the
  // next column has to break.
  template <class DetectRuns>
  void sort_range(
    DataType * index,
    TslRunSpan range,
    TslSortColumn<DataType> const & column,
    bool identity,
    TslRunDiscoveryKind discovery,
    DetectRuns & detect_runs,
    TslIndexSortMetrics * metrics
  ) {
    auto const order = column.order;
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
      prepare_detector(detect_runs, column.data, range.begin, range.end, identity);
      auto const t_sort = std::chrono::steady_clock::now();
      sorter_.sort_key(keys, payloads, 1, count, order);
      if constexpr (Profile) {
        if (metrics != nullptr) {
          metrics->ns_sort += tsl_index_since(t_sort);
        }
      }
      if (metrics != nullptr) {
        metrics->rle_values_scanned += count;
      }
      auto const t_detect = std::chrono::steady_clock::now();
      detect_runs(scratch_.data(), range.begin, range.end, keep);
      if constexpr (Profile) {
        if (metrics != nullptr) {
          metrics->ns_detect += tsl_index_since(t_detect);
        }
      }
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
    // Incremental discovery runs detection from inside the sort, so the two cannot
    // be timed by bracketing them. Detection is accumulated in the sink and
    // subtracted from the enclosing duration, which is what makes the phase split
    // comparable between the two discovery kinds rather than an artefact of where
    // the calls sit.
    double detect_ns = 0.0;
    auto leaf_sink = [&](std::size_t leaf_begin, std::size_t leaf_end) {
      if (metrics != nullptr) {
        metrics->rle_values_scanned += leaf_end - leaf_begin;
      }
      auto const mark = std::chrono::steady_clock::now();
      detect_runs(scratch_.data(), leaf_begin, leaf_end, keep);
      if constexpr (Profile) {
        detect_ns += tsl_index_since(mark);
      }
    };
    auto const t_sort = std::chrono::steady_clock::now();
    sorter_.sort_key_with_completion_events(
      keys, payloads, 1, count, order, range.begin, equal_band_sink, leaf_sink
    );
    if constexpr (Profile) {
      if (metrics != nullptr) {
        metrics->ns_sort += tsl_index_since(t_sort) - detect_ns;
        metrics->ns_detect += detect_ns;
      }
    }
  }
};
