#pragma once

// Lexicographic multi-column co-sort driven by samplesort.
//
// The samplesort in `samplesort_cosort.hpp` sorts one key column and carries an
// index. This is the level above it: the column loop that turns that into a
// lexicographic sort of a table, which is what the quicksort family does and what
// makes the `rle=` detector axis apply.
//
// -----------------------------------------------------------------------------
// Shape
// -----------------------------------------------------------------------------
// Index movement, necessarily: samplesort's whole premise is that the permutation
// lives in an index column and the other columns are materialised afterwards, so
// there is no direct-movement form of this. The loop is therefore the same as
// `multicolumn_index_sort.hpp`'s:
//
//     materialise keys[range] = column[j][index[range]]
//     samplesort keys[range], carrying index[range]
//     for each maximal equal run in keys[range]:
//         recurse on column j+1 over that run
//
// Level 0 needs no gather: the index is the identity there, so it is a copy.
// Only rows inside a surviving range are ever materialised, so the gather work
// shrinks with depth.
//
// -----------------------------------------------------------------------------
// Detection
// -----------------------------------------------------------------------------
// The detector is the seam every backend in `benchmarks/cosort_detectors.hpp`
// satisfies: `operator()(values, begin, end, emit)` emitting maximal equal runs.
// Asynchronous backends are rejected at compile time, for the same reason the
// serial index sort rejects them -- nothing here polls.
//
// A samplesort knows some of those runs already, for free: under
// `TslSampleSortBuckets::Adaptive` a bucket holding one repeated value is bounded
// by neighbours that are strictly smaller and strictly greater, so its span *is*
// the maximal run for that value, and the histogram already gives its bounds. It
// is deliberately not exploited here. Doing so needs the samplesort to report
// those spans, and in the parallel executor that means pushing one report per
// terminal range -- about 440k of them in a 2^24-row sort -- through a shared
// mutex, which is the exact shape measured to cap that executor at 1.04x on 24
// threads. Whether detection is even a large enough share of this driver's
// profile to be worth that is the thing to measure first.
//
// -----------------------------------------------------------------------------
// Limits
// -----------------------------------------------------------------------------
// Ascending only. The samplesort compares keys directly and takes no order
// argument, so a descending column would need the comparison inverted throughout
// rather than a flag here; `sort_index` rejects it rather than sorting wrongly.
//
// `sort_index_parallel` is two phases, for the same reason the samplesort's own
// executor is: the range list starts with one entry, so range-level parallelism
// has nothing to work with until the first column has been sorted.
//
//   descend    while there are fewer ranges than workers, sort the largest with
//              the parallel samplesort, which fans that one range across threads
//   spread     once there are enough ranges, a persistent pool sorts whole ranges,
//              each serially
//
// The second phase is not optional. Calling the parallel samplesort per range
// creates a thread pool per call: at 2^21 rows over four columns that is 33 calls
// and several thousand thread creations, which measured *slower* than one thread
// -- 145 ns/element against 51 -- and grew monotonically with the worker count.
// Ranges are disjoint, so the phase-two workers share the key buffer and the
// index, and only the samplesort scratch is private.
//
// The detector is called from worker threads in phase two, so it must be a fleet
// or stateless -- the same contract `sort_columns_parallel` places on it.

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <condition_variable>
#include <mutex>
#include <numeric>
#include <thread>
#include <stdexcept>
#include <string>
#include <vector>

#include "cluster_detection/scalar/equal_runs.hpp"
#include "sorting/common/multicolumn_sort_types.hpp"
#include "sorting/sample_sort/samplesort_executor.hpp"
#include "sorting/sample_sort/samplesort_parallel_executor.hpp"


struct TslSampleSortColumnMetrics {
  std::size_t ranges = 0;                 // samplesort calls over >= 2 rows
  std::size_t rows = 0;                   // summed range lengths
  std::size_t materialized_elements = 0;  // gather traffic, plus level 0's copy
  std::size_t detected_ranges = 0;        // ranges handed to the detector
  std::size_t detected_elements = 0;
  std::size_t runs_found = 0;             // equal runs the detector emitted
  std::size_t deepest_column = 0;
  std::size_t parallel_ranges = 0;        // ranges sorted by the parallel executor
  TslSampleSortMetrics sort;              // summed from every samplesort call
};


template <
  class Key = std::uint32_t,
  class SimdStyle = tsl::dataparallel::simd_for_t<tsl::dataparallel::native, Key>,
  int K = 16,
  TslSampleSortBuckets Policy = TslSampleSortBuckets::Adaptive,
  int Oversample = 8,
  std::size_t BaseCase = 256,
  TslSampleSortBase BasePolicy = TslSampleSortBase::Network,
  TslSampleSortIds IdWidth = TslSampleSortIds::Byte,
  std::size_t BaseRows = BaseCase / SimdStyle::lane_count_v,
  std::size_t BaseFillPercent = 50
>
class TslSampleSortMultiColumn {
 public:
  using key_type = Key;
  using index_type = typename TslSampleSortTraits<Key>::index_type;

  // Below this a range is sorted by the serial executor whatever the worker count
  // is: forking for a few hundred rows costs more than it saves.
  static constexpr std::size_t parallel_range_threshold = 1u << 16;

  // Sorts `columns[0..column_count)` lexicographically by filling `index` with
  // the permutation that orders them. The columns are never written; apply the
  // permutation afterwards with `tsl_apply_permutation`. Not stable.
  template <class DetectRuns>
  void sort_index(
    TslSortColumn<Key> const * columns,
    std::size_t column_count,
    index_type * index,
    std::size_t row_count,
    DetectRuns & detect_runs,
    TslSampleSortColumnMetrics * metrics = nullptr
  ) {
    static_assert(
      !tsl_detector_wants_executor<DetectRuns>::value,
      "this driver never polls, so an asynchronous detector would never "
      "complete. Use a synchronous backend."
    );
    run(columns, column_count, index, row_count, detect_runs, 0, metrics);
  }

  // As above, with each range's samplesort run on `worker_count` threads.
  template <class DetectRuns>
  void sort_index_parallel(
    TslSortColumn<Key> const * columns,
    std::size_t column_count,
    index_type * index,
    std::size_t row_count,
    DetectRuns & detect_runs,
    std::size_t worker_count,
    TslSampleSortColumnMetrics * metrics = nullptr
  ) {
    static_assert(
      !tsl_detector_wants_executor<DetectRuns>::value,
      "this driver never polls, so an asynchronous detector would never "
      "complete. Use a synchronous backend."
    );
    run(columns, column_count, index, row_count, detect_runs,
        std::max<std::size_t>(1, worker_count), metrics);
  }

 private:
  struct range {
    std::size_t column;
    std::size_t begin;
    std::size_t end;
  };

  template <class DetectRuns>
  void run(
    TslSortColumn<Key> const * columns,
    std::size_t column_count,
    index_type * index,
    std::size_t row_count,
    DetectRuns & detect_runs,
    std::size_t worker_count,
    TslSampleSortColumnMetrics * metrics_out
  ) {
    validate(columns, column_count, index, row_count);
    TslSampleSortColumnMetrics metrics;
    if (row_count == 0 || column_count == 0) {
      if (metrics_out != nullptr) {
        *metrics_out = metrics;
      }
      return;
    }

    std::iota(index, index + row_count, index_type{0});
    // The active column's values. Ranges are disjoint, so every worker writes its
    // own slice of this and of `index`.
    std::vector<Key> keys(row_count);

    std::vector<range> pending;
    pending.push_back(range{0, 0, row_count});

    // ---- phase one: descend, fanning one range at a time across the workers ----
    if (worker_count > 1) {
      std::vector<Key> keys_scratch(row_count);
      std::vector<index_type> index_scratch(row_count);
      while (pending.size() < worker_count) {
        auto const largest = std::max_element(
          pending.begin(), pending.end(),
          [](range const & a, range const & b) {
            return (a.end - a.begin) < (b.end - b.begin);
          });
        if (largest == pending.end()
            || (largest->end - largest->begin) < parallel_range_threshold) {
          break;
        }
        // Only fan a range that *dominates* what is left. Fanning until there are
        // as many ranges as workers sounds right and is not: a shape whose key
        // has four distinct values yields four children per split, so reaching 24
        // ranges takes eight fans, each on a smaller range, and the pool built per
        // fan costs more than the split gains -- measured 20.6 ns/element against
        // 12.4 with a single fan. Once no range dominates, range-level parallelism
        // is the better instrument, and that is phase two.
        std::size_t remaining = 0;
        for (auto const & entry : pending) {
          remaining += entry.end - entry.begin;
        }
        if ((largest->end - largest->begin) * 2 < remaining) {
          break;
        }
        auto const current = *largest;
        pending.erase(largest);
        ++metrics.parallel_ranges;
        std::vector<range> children;
        sort_one_range(columns, column_count, index, keys, keys_scratch,
                       index_scratch, current, detect_runs, worker_count, metrics,
                       children);
        pending.insert(pending.end(), children.begin(), children.end());
      }
    }

    // ---- phase two: whole ranges, one worker each ----
    if (worker_count > 1 && !pending.empty()) {
      std::mutex mutex;
      std::condition_variable cv;
      std::size_t idle = 0;
      bool finished = false;
      std::vector<TslSampleSortColumnMetrics> per_worker(worker_count);
      std::vector<range> shared(pending.begin(), pending.end());
      pending.clear();
      // Publish only ranges big enough to be worth another worker's attention;
      // the rest stay where they were produced, which is also where their slice
      // of the key buffer is warm. Same reason the samplesort executor does it.
      auto const share_threshold = std::max<std::size_t>(BaseCase, row_count / (worker_count * 8));

      auto const worker = [&](std::size_t id) {
        auto & mine = per_worker[id];
        std::vector<Key> scratch;
        std::vector<index_type> index_scratch;
        std::vector<range> local;
        std::vector<range> children;
        while (true) {
          range current{};
          if (!local.empty()) {
            current = local.back();
            local.pop_back();
          } else {
            std::unique_lock<std::mutex> lock(mutex);
            ++idle;
            if (idle == worker_count && shared.empty()) {
              finished = true;
              cv.notify_all();
            }
            cv.wait(lock, [&] { return !shared.empty() || finished; });
            if (finished) {
              return;
            }
            current = shared.back();
            shared.pop_back();
            --idle;
          }
          auto const count = current.end - current.begin;
          if (count > scratch.size()) {
            scratch.resize(count);
            index_scratch.resize(count);
          }
          children.clear();
          sort_one_range(columns, column_count, index, keys, scratch, index_scratch,
                         current, detect_runs, 1, mine, children);
          std::size_t published = 0;
          for (auto const & child : children) {
            if ((child.end - child.begin) >= share_threshold) {
              ++published;
            } else {
              local.push_back(child);
            }
          }
          if (published != 0) {
            {
              std::lock_guard<std::mutex> lock(mutex);
              for (auto const & child : children) {
                if ((child.end - child.begin) >= share_threshold) {
                  shared.push_back(child);
                }
              }
            }
            cv.notify_all();
          }
        }
      };

      std::vector<std::thread> pool;
      pool.reserve(worker_count - 1);
      for (std::size_t id = 1; id < worker_count; ++id) {
        pool.emplace_back(worker, id);
      }
      worker(0);
      for (auto & thread : pool) {
        thread.join();
      }
      for (auto const & mine : per_worker) {
        merge(metrics, mine);
      }
    } else {
      // Serial: one stack, one scratch pair, no pool.
      std::vector<Key> scratch(row_count);
      std::vector<index_type> index_scratch(row_count);
      std::vector<range> children;
      while (!pending.empty()) {
        auto const current = pending.back();
        pending.pop_back();
        children.clear();
        sort_one_range(columns, column_count, index, keys, scratch, index_scratch,
                       current, detect_runs, 1, metrics, children);
        pending.insert(pending.end(), children.begin(), children.end());
      }
    }

    if (metrics_out != nullptr) {
      *metrics_out = metrics;
    }
  }

  // Materialise one range's keys, sort it, and report the equal runs the next
  // column must be sorted inside. `workers > 1` fans this one range across
  // threads; 1 keeps it on the caller's.
  template <class DetectRuns>
  void sort_one_range(
    TslSortColumn<Key> const * columns,
    std::size_t column_count,
    index_type * index,
    std::vector<Key> & keys,
    std::vector<Key> & keys_scratch,
    std::vector<index_type> & index_scratch,
    range const & current,
    DetectRuns & detect_runs,
    std::size_t workers,
    TslSampleSortColumnMetrics & metrics,
    std::vector<range> & children
  ) {
    auto const count = current.end - current.begin;
    metrics.deepest_column = std::max(metrics.deepest_column, current.column);
    if (count < 2 || current.column >= column_count) {
      return;
    }

    // Level 0's index is the identity, so it is a copy rather than a gather.
    auto const * source = columns[current.column].data;
    if (current.column == 0) {
      std::copy_n(source + current.begin, count, keys.data() + current.begin);
    } else {
      for (std::size_t at = current.begin; at < current.end; ++at) {
        keys[at] = source[static_cast<std::size_t>(index[at])];
      }
    }
    metrics.materialized_elements += count;
    ++metrics.ranges;
    metrics.rows += count;

    TslSampleSortMetrics sort_metrics;
    if (workers > 1) {
      tsl_samplesort_cosort_parallel<Key, SimdStyle, K, Policy, Oversample, BaseCase,
                                    BasePolicy, IdWidth, BaseRows, BaseFillPercent>(
        keys.data() + current.begin, index + current.begin, count,
        keys_scratch.data(), index_scratch.data(), workers, {}, &sort_metrics);
    } else {
      tsl_samplesort_cosort<Key, SimdStyle, K, Policy, Oversample, BaseCase,
                            BasePolicy, IdWidth, BaseRows, BaseFillPercent>(
        keys.data() + current.begin, index + current.begin, count,
        keys_scratch.data(), index_scratch.data(), {}, &sort_metrics);
    }
    accumulate(metrics.sort, sort_metrics);

    if (current.column + 1 >= column_count) {
      return;
    }
    // Ties in this column decide nothing, so the next column is sorted inside
    // each of them and nowhere else.
    ++metrics.detected_ranges;
    metrics.detected_elements += count;
    auto const next = current.column + 1;
    detect_runs(keys.data(), current.begin, current.end, [&](TslRunSpan span) {
      ++metrics.runs_found;
      children.push_back(range{next, span.begin, span.end});
    });
  }

  static void merge(TslSampleSortColumnMetrics & into,
                    TslSampleSortColumnMetrics const & from) {
    into.ranges += from.ranges;
    into.rows += from.rows;
    into.materialized_elements += from.materialized_elements;
    into.detected_ranges += from.detected_ranges;
    into.detected_elements += from.detected_elements;
    into.runs_found += from.runs_found;
    into.parallel_ranges += from.parallel_ranges;
    into.deepest_column = std::max(into.deepest_column, from.deepest_column);
    accumulate(into.sort, from.sort);
  }

  static void validate(
    TslSortColumn<Key> const * columns,
    std::size_t column_count,
    index_type const * index,
    std::size_t row_count
  ) {
    if (row_count != 0 && index == nullptr) {
      throw std::invalid_argument("index column is null");
    }
    if (column_count != 0 && columns == nullptr) {
      throw std::invalid_argument("column array is null");
    }
    for (std::size_t column = 0; column < column_count; ++column) {
      if (row_count != 0 && columns[column].data == nullptr) {
        throw std::invalid_argument("column " + std::to_string(column) + " is null");
      }
      if (columns[column].order != TslSortOrder::ASCENDING) {
        throw std::invalid_argument(
          "samplesort sorts ascending only: column " + std::to_string(column)
          + " asks for descending, which needs the comparison inverted in the "
            "kernels rather than a flag here");
      }
    }
  }

  static void accumulate(TslSampleSortMetrics & into, TslSampleSortMetrics const & from) {
    into.partition_steps += from.partition_steps;
    into.classified_elements += from.classified_elements;
    into.distributed_elements += from.distributed_elements;
    into.base_case_ranges += from.base_case_ranges;
    into.base_case_elements += from.base_case_elements;
    into.equality_buckets += from.equality_buckets;
    into.equality_elements += from.equality_elements;
    into.degenerate_steps += from.degenerate_steps;
    into.heapsort_ranges += from.heapsort_ranges;
    into.copied_back_elements += from.copied_back_elements;
    into.equality_buckets_allocated += from.equality_buckets_allocated;
    into.tasks += from.tasks;
    into.max_depth = std::max(into.max_depth, from.max_depth);
    into.max_buckets_used = std::max(into.max_buckets_used, from.max_buckets_used);
  }
};
