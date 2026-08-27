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
// Asynchronous backends are accepted at every worker count, one included: the
// worklist below implements `TslPendingWork`, so it knows what the device still
// owes and polls for it rather than finishing early. At one worker that is
// pipelining rather than concurrency -- hand a range over, sort the next one, take
// the completion when it lands.
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
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <chrono>
#include <numeric>
#include <thread>
#include <stdexcept>
#include <string>
#include <vector>

#include "common/instrumentation.hpp"
#include "cluster_detection/scalar/equal_runs.hpp"
#include "sorting/common/multicolumn_sort_types.hpp"
#include "sorting/common/run_discovery.hpp"
#include "sorting/common/pending_range_queue.hpp"
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
  // Filled only when the driver is instantiated with profiling on. Wall time per
  // phase summed across workers, so on threads these exceed the elapsed time and
  // only their ratio means anything.
  double ns_materialize = 0.0;
  double ns_sort = 0.0;
  double ns_detect = 0.0;
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
  std::size_t BaseFillPercent = 50,
  // Forwarded to the samplesort. In place halves the footprint and costs
  // throughput; reachable from here so the tuner can put it on an axis rather
  // than it being a property only the single-key sort has.
  TslSampleSortMovement Movement = TslSampleSortMovement::OutOfPlace,
  // Times the three phases. Two clock reads per phase per range, so it is off by
  // default and off in any timed run that is not asking where the time goes.
  bool Profile = false
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
    TslSampleSortColumnMetrics * metrics_in = nullptr
  ) {
    run(columns, column_count, index, row_count, detect_runs, 1,
        tsl_metrics_for<Profile>(metrics_in));
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
    TslSampleSortColumnMetrics * metrics_in = nullptr
  ) {
    run(columns, column_count, index, row_count, detect_runs,
        std::max<std::size_t>(1, worker_count), tsl_metrics_for<Profile>(metrics_in));
  }

 private:
  struct range {
    std::size_t column;
    std::size_t begin;
    std::size_t end;
  };

  // Where a span emitted *on this worker* should go.
  //
  // An asynchronous detector delivers most spans inline -- every range below its
  // offload threshold is scanned on the calling thread -- and only the rest from a
  // poller. Sending all of them to the shared pool costs the locality the local
  // stacks exist for, and it costs most of the sort: measured on 2.6M rows over
  // three columns at 1024 distinct values, six workers, publishing everything ran
  // 202 ns/row against 21 for the scalar scan with the device holding exactly one
  // range; keeping the inline spans local brought it to 27. So a worker publishes
  // this slot while it is inside
  // `sort_one_range`, an emitter running on that same thread finds it and keeps the
  // child, and a completion observed anywhere else finds it null and publishes to
  // the pool. A pointer, so the check is one thread-local load per span.
  static auto inline_sink() -> std::vector<range> *& {
    static thread_local std::vector<range> * sink = nullptr;
    return sink;
  }

  // Which worker this thread is, for a span that arrives after its `sort_one_range`
  // has returned. The inline sink handles the common case -- a span emitted on the
  // submitting thread while it is still inside the call -- and this handles the
  // one the inline sink cannot: an asynchronous completion polled by *another*
  // thread, which has no safe way to reach the owner's stack but can park the span
  // in a slot the owner will look at.
  static auto worker_slot() -> std::size_t & {
    static thread_local std::size_t slot = 0;
    return slot;
  }

 public:
  // Route asynchronous completions through the same share-threshold decision the
  // synchronous path applies, instead of straight to the shared pool.
  //
  // Worth a switch rather than a replacement, because it is the hypothesis under
  // test. In phase two a worker splits its children: below the share threshold
  // they stay on its own stack, above it they go to the pool. A completion observed
  // on another thread skipped that split entirely and published everything, so
  // every late span became a shared work item however small -- and on this host the
  // asynchronous path was handed 1031 ranges against the synchronous path's 303,
  // each 3.4x smaller, with 3.4x the per-range overhead to amortise.
  void set_async_spans_local(bool enabled) { async_spans_local_ = enabled; }
  auto async_spans_local() const -> bool { return async_spans_local_; }

 private:

  // Sets the slot for the duration of one `sort_one_range` call and restores what
  // was there, so a nested sort cannot lose its own sink.
  bool async_spans_local_ = false;

  class inline_sink_scope {
   public:
    explicit inline_sink_scope(std::vector<range> * sink)
        : previous_(inline_sink()) {
      inline_sink() = sink;
    }
    ~inline_sink_scope() { inline_sink() = previous_; }
    inline_sink_scope(inline_sink_scope const &) = delete;
    auto operator=(inline_sink_scope const &) -> inline_sink_scope & = delete;

   private:
    std::vector<range> * previous_;
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

    // An asynchronous detector reports its spans later, from whichever thread
    // observes the completion, so the sort needs a scheduler that (a) does not
    // declare itself finished while the device still owes it ranges, (b) polls
    // rather than sleeps when the only outstanding work is on the device, and (c)
    // accepts a range from any thread. That is what the queue is; the per-worker
    // local stacks below stay with the worker, because routing every range
    // through one queue is what capped this sorter at 1.04x on 24 threads.
    constexpr bool asynchronous = tsl_detector_wants_executor<DetectRuns>::value;
    std::size_t const workers = std::max<std::size_t>(1, worker_count);
    TslPendingRangeQueue<range> queue(workers);
    // The detector's emitter cannot count into `metrics`: it outlives the frame.
    std::atomic<std::size_t> async_runs{0};
    auto * const queue_address = &queue;
    auto * const runs_address = &async_runs;
    // The share threshold has to be known here, because the emitter is what a late
    // completion reaches and the emitter is where the decision now happens.
    auto const emit_share_threshold =
      std::max<std::size_t>(BaseCase, row_count / (workers * 8));
    auto const spans_local = async_spans_local_;
    auto const publish_shared =
      [queue_address, runs_address, emit_share_threshold, spans_local](
          range const & child) {
      runs_address->fetch_add(1, std::memory_order_relaxed);
      if (auto * const sink = inline_sink()) {
        sink->push_back(child);
        return;
      }
      // No inline sink: this span arrived from a poll on some other thread, after
      // the submitting worker's call had returned. Publishing it unconditionally is
      // what the shared pool did; parking a sub-threshold one in the owner's slot
      // is what the synchronous path would have done with it.
      if (spans_local && (child.end - child.begin) < emit_share_threshold) {
        queue_address->defer(worker_slot(), child);
        return;
      }
      queue_address->publish(child);
    };
    if constexpr (asynchronous) {
      detect_runs.bind(queue);
      queue.set_poller([&detect_runs] { detect_runs.poll(); });
      if (async_spans_local_) {
        queue.enable_deferred(workers);
      }
    }

    std::vector<range> pending;
    pending.push_back(range{0, 0, row_count});

    // ---- phase one: descend, fanning one range at a time across the workers ----
    if (workers > 1) {
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
        if constexpr (asynchronous) {
          {
            inline_sink_scope const scope(&children);
            sort_one_range(columns, column_count, index, keys, keys_scratch,
                           index_scratch, current, detect_runs, workers, metrics,
                           publish_shared);
          }
          // This phase is sequential and decides whether to fan again from what
          // the last fan produced, so the debt has to be settled here rather than
          // carried into the decision. Whatever the device answered late arrives
          // through the pool, so both sources end up in `children`.
          queue.drain_into(children);
        } else {
          sort_one_range(columns, column_count, index, keys, keys_scratch,
                         index_scratch, current, detect_runs, workers, metrics,
                         [&children](range const & child) {
                           children.push_back(child);
                         });
        }
        pending.insert(pending.end(), children.begin(), children.end());
      }
    }

    // ---- phase two: whole ranges, one worker each ----
    // The queue owns what the workers must agree on -- the shared pool, the idle
    // count, the device's outstanding debt and the first failure. Each worker
    // keeps its own stack for ranges too small to be worth another worker's
    // attention, which is where their slice of the key buffer is warm.
    auto const share_threshold =
      std::max<std::size_t>(BaseCase, row_count / (workers * 8));
    std::vector<TslSampleSortColumnMetrics> per_worker(workers);

    auto const worker = [&](std::size_t id) {
      auto & mine = per_worker[id];
      // So an emitter running on this thread knows whose slot to park a span in.
      worker_slot() = id;
      std::vector<Key> scratch;
      std::vector<index_type> index_scratch;
      std::vector<range> local;
      std::vector<range> children;
      std::vector<range> to_share;
      try {
        while (true) {
          range current{};
          if (!local.empty()) {
            current = local.back();
            local.pop_back();
          } else if (!queue.take(current, id)) {
            break;
          }
          auto const count = current.end - current.begin;
          if (count > scratch.size()) {
            scratch.resize(count);
            index_scratch.resize(count);
          }
          children.clear();
          if constexpr (asynchronous) {
            // Spans emitted on this thread land in `children` through the sink
            // below; a completion observed on another thread goes straight to the
            // shared pool, because no other worker's stack is safe to reach into.
            inline_sink_scope const scope(&children);
            sort_one_range(columns, column_count, index, keys, scratch,
                           index_scratch, current, detect_runs, 1, mine,
                           publish_shared);
          } else {
            sort_one_range(columns, column_count, index, keys, scratch,
                           index_scratch, current, detect_runs, 1, mine,
                           [&children](range const & child) {
                             children.push_back(child);
                           });
          }
          to_share.clear();
          for (auto const & child : children) {
            if ((child.end - child.begin) >= share_threshold) {
              to_share.push_back(child);
            } else {
              local.push_back(child);
            }
          }
          if (!to_share.empty()) {
            queue.publish_many(to_share);
          }
        }
      } catch (...) {
        // A throw off a worker thread would otherwise reach std::terminate. The
        // detectors can raise -- a device submission failure is an exception --
        // and until this existed phase two had nowhere to put one.
        queue.fail(std::current_exception());
      }
    };

    if (workers == 1 && !asynchronous) {
      // Serial and synchronous: one stack, one scratch pair, and no queue, so the
      // path that every one-worker figure reports pays no locking for a scheduler
      // it does not use.
      std::vector<Key> scratch(row_count);
      std::vector<index_type> index_scratch(row_count);
      std::vector<range> children;
      while (!pending.empty()) {
        auto const current = pending.back();
        pending.pop_back();
        children.clear();
        sort_one_range(columns, column_count, index, keys, scratch, index_scratch,
                       current, detect_runs, 1, metrics,
                       [&children](range const & child) {
                         children.push_back(child);
                       });
        pending.insert(pending.end(), children.begin(), children.end());
      }
    } else {
      queue.publish_many(pending);
      pending.clear();
      std::vector<std::thread> pool;
      pool.reserve(workers - 1);
      for (std::size_t id = 1; id < workers; ++id) {
        pool.emplace_back(worker, id);
      }
      worker(0);
      for (auto & thread : pool) {
        thread.join();
      }
      // After the join, so a failure is reported once and from the caller's
      // thread rather than from wherever it was raised.
      queue.rethrow_if_failed();
      for (auto const & mine : per_worker) {
        merge(metrics, mine);
      }
      if constexpr (asynchronous) {
        metrics.runs_found += async_runs.load(std::memory_order_relaxed);
      }
    }

    if (metrics_out != nullptr) {
      *metrics_out = metrics;
    }
  }

  // Materialise one range's keys, sort it, and report the equal runs the next
  // column must be sorted inside. `workers > 1` fans this one range across
  // threads; 1 keeps it on the caller's.
  // `publish` is taken by value because an asynchronous detector retains the
  // emitter it is wrapped in and calls it from whichever thread observes the
  // completion: anything captured by reference from this frame would be dangling
  // by then. A synchronous caller passes a callable that appends to its own
  // vector, which costs the same as the vector parameter this used to take.
  template <class DetectRuns, class Publish>
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
    Publish publish
  ) {
    auto const count = current.end - current.begin;
    metrics.deepest_column = std::max(metrics.deepest_column, current.column);
    if (count < 2 || current.column >= column_count) {
      return;
    }
    auto const since = [](auto start) {
      return std::chrono::duration<double, std::nano>(
               std::chrono::steady_clock::now() - start).count();
    };
    auto const t_materialize = std::chrono::steady_clock::now();

    // Level 0's index is the identity, so it is a copy rather than a gather.
    auto const * source = columns[current.column].data;
    if (current.column == 0) {
      std::copy_n(source + current.begin, count, keys.data() + current.begin);
    } else {
      for (std::size_t at = current.begin; at < current.end; ++at) {
        keys[at] = source[static_cast<std::size_t>(index[at])];
      }
    }
    if constexpr (Profile) {
      metrics.ns_materialize += since(t_materialize);
    }
    metrics.materialized_elements += count;
    ++metrics.ranges;
    metrics.rows += count;

    auto const t_sort = std::chrono::steady_clock::now();
    TslSampleSortMetrics sort_metrics;
    if (workers > 1) {
      tsl_samplesort_cosort_parallel<Key, SimdStyle, K, Policy, Oversample, BaseCase,
                                    BasePolicy, IdWidth, BaseRows, BaseFillPercent,
                                    Movement>(
        keys.data() + current.begin, index + current.begin, count,
        keys_scratch.data(), index_scratch.data(), workers, {}, &sort_metrics);
    } else {
      tsl_samplesort_cosort<Key, SimdStyle, K, Policy, Oversample, BaseCase,
                            BasePolicy, IdWidth, BaseRows, BaseFillPercent,
                            Movement>(
        keys.data() + current.begin, index + current.begin, count,
        keys_scratch.data(), index_scratch.data(), {}, &sort_metrics);
    }
    if constexpr (Profile) {
      metrics.ns_sort += since(t_sort);
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
    auto const t_detect = std::chrono::steady_clock::now();
    if constexpr (tsl_detector_wants_executor<DetectRuns>::value) {
      // Self-contained by construction: `publish` and the column index are
      // captured by value and `metrics` is not touched at all, because this
      // callable outlives the frame. The span count is folded in by `run` from the
      // counter `publish` owns.
      tsl_detect_runs(detect_runs, keys.data(), current.begin, current.end,
                      [publish, next](TslRunSpan span) {
                        publish(range{next, span.begin, span.end});
                      });
    } else {
      tsl_detect_runs(detect_runs, keys.data(), current.begin, current.end,
                      [&](TslRunSpan span) {
                        ++metrics.runs_found;
                        publish(range{next, span.begin, span.end});
                      });
    }
    if constexpr (Profile) {
      // With an asynchronous detector this is the handover, not the scan: the
      // device works while this range's sort continues, and the spans arrive on a
      // later poll. Reading it as "time spent detecting" would understate the
      // work and overstate the overlap.
      metrics.ns_detect += since(t_detect);
    }
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
    into.ns_materialize += from.ns_materialize;
    into.ns_sort += from.ns_sort;
    into.ns_detect += from.ns_detect;
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
