#pragma once

// Equal-run detection from precomputed value frequencies, overlapped with the
// sort that produces the order.
//
// A fourth implementation of the `tsl_for_each_equal_run` contract in
// equal_runs.hpp, and the only one that does no comparing. On a sorted range the
// multiplicity of a value *is* the length of its run, so a map from value to
// count turns discovery into a walk of at most one step per distinct value:
//
//   p = begin
//   while p < end:  v = values[p];  emit [p, p + count(v));  p += count(v)
//
// The counts come from `iaa_distinct_frequencies.hpp`, which resolves them on the
// accelerator without sorting anything, and they do not depend on order -- so the
// walk can be started on the *unsorted* range and consumed after the sort. That
// is the point of this detector: discovery leaves the critical path.
//
// -----------------------------------------------------------------------------
// Two costs the idea does not avoid
// -----------------------------------------------------------------------------
// **A snapshot, unless the caller already has one.**
// `TslIaaDistinctFrequencies::start` keeps a pointer and requires the range to
// stay unchanged until the walk finishes, and a sort rewrites exactly that range.
// So `prepare` copies it -- but only when it has to. A caller passing `stable`
// promises the buffer will not change until the matching `detect`, and then no
// copy happens at all. The indirect sorter can promise that twice over: at its
// first level the source column *is* the key buffer and is read-only for the
// whole sort, and at deeper levels its materialize pass can mirror the gathered
// values into a second buffer for one extra store rather than a second pass. A
// sorter that permutes its columns in place cannot promise it and pays the copy.
// `snapshot_elements` reports what was actually copied.
//
// **A thread.** The walk advances only inside `poll()`, so something has to call
// it while the sort runs. Polling from the partition loop is not on offer, so
// `prepare` hands the walk to one helper thread per detector that spins until the
// answer is ready. On a saturated machine that thread competes with the sort's
// own workers; on an idle one it is free. `TslIaaFrequencyPath::SOFTWARE` makes
// this strictly a loss -- QPL runs the scan on the calling thread there, so the
// helper does the whole walk itself -- and it exists so the logic can be tested
// without a device.
//
// -----------------------------------------------------------------------------
// Where it can be used
// -----------------------------------------------------------------------------
// `prepare` must see the same multiset the later `detect` walks, so a caller has
// to know the range before it sorts it. That is the post-sort discovery shape:
// materialize (or take) a range, prepare, sort, detect. Incremental discovery
// interleaves reporting with partitioning and has no such point, so a caller with
// `Discovery == INCREMENTAL` simply never calls `prepare` and gets the scalar
// scan.
//
// A range that was never prepared, or was prepared with different bounds, falls
// back to `tsl_for_each_equal_run`, so a caller that only sometimes prepares is
// still correct and the fallbacks show up in the metrics rather than silently.
//
// The walk also confirms each run it is told about with two loads -- the last
// element must be the value, the next must not. That is O(1) per run against
// O(1) per element for a scan, and without it a map describing *different* data
// yields spans that are wrong rather than absent: a count that is merely too
// small stays inside the range, so checking only for overruns misses it. On any
// inconsistency the whole range is rescanned, because spans already emitted came
// from the same untrustworthy map.

#include <algorithm>
#include <atomic>
#include <condition_variable>
#include <cstddef>
#include <cstdint>
#include <exception>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>
#include <thread>
#include <type_traits>
#include <utility>
#include <vector>

#include "equal_runs.hpp"
#include "iaa_distinct_frequencies.hpp"
#include "multicolumn_sort_types.hpp"


struct TslFrequencyDetectorMetrics {
  std::size_t ranges = 0;              // detect() calls over >= 2 elements
  std::size_t elements = 0;
  std::size_t prepared_ranges = 0;     // ranges whose counts were precomputed
  std::size_t prepared_elements = 0;
  std::size_t snapshot_elements = 0;   // elements copied so the walk had a stable input
  std::size_t distinct_values = 0;     // map entries consumed
  std::size_t walk_steps = 0;          // one per run the map resolved
  std::size_t fallback_unprepared = 0; // detect() without a matching prepare()
  std::size_t fallback_mismatch = 0;   // the map disagreed with the sorted range
  std::size_t spans_emitted = 0;
};


// One detector: one snapshot buffer, one helper thread, one pending answer.
// Not shareable -- `TslFrequencyDetectorFleet` hands one to each worker.
template <class DataType>
class TslIaaFrequencyRunDetector {
  static_assert(std::is_integral_v<DataType>, "run detection needs an integral element type");

  using counter_type = TslIaaDistinctFrequencies<DataType>;
  using map_type = typename counter_type::map_type;

  counter_type counter_;
  std::size_t min_prepare_elements_;

  // The snapshot the walk reads. Owned here because the caller's range is about
  // to be permuted by the sort.
  std::vector<DataType> snapshot_;

  // The helper thread and its handshake. `pending_` means a walk is in flight;
  // `answer_` is valid once it clears.
  std::thread helper_;
  std::mutex mutex_;
  std::condition_variable work_ready_;
  std::condition_variable answer_ready_;
  map_type answer_;
  std::exception_ptr error_;
  std::size_t prepared_begin_ = 0;
  std::size_t prepared_end_ = 0;
  bool pending_ = false;
  bool stop_ = false;

  TslFrequencyDetectorMetrics metrics_{};

  void helper_loop() {
    for (;;) {
      {
        std::unique_lock<std::mutex> lock(mutex_);
        work_ready_.wait(lock, [this] { return stop_ || pending_; });
        if (stop_) {
          return;
        }
      }
      // Outside the lock: this is the part that is supposed to overlap.
      std::exception_ptr failure;
      map_type result;
      try {
        while (!counter_.poll()) {
        }
        result = counter_.take();
      } catch (...) {
        failure = std::current_exception();
      }
      {
        std::lock_guard<std::mutex> lock(mutex_);
        answer_ = std::move(result);
        error_ = failure;
        pending_ = false;
      }
      answer_ready_.notify_one();
    }
  }

  void ensure_helper() {
    if (!helper_.joinable()) {
      helper_ = std::thread([this] { helper_loop(); });
    }
  }

  // Blocks until the in-flight walk finishes. Called from detect().
  void await_answer() {
    std::unique_lock<std::mutex> lock(mutex_);
    answer_ready_.wait(lock, [this] { return !pending_; });
    if (error_ != nullptr) {
      auto const failure = error_;
      error_ = nullptr;
      prepared_end_ = prepared_begin_;
      std::rethrow_exception(failure);
    }
  }

 public:
  explicit TslIaaFrequencyRunDetector(
    TslIaaFrequencyOptions options = {},
    std::size_t min_prepare_elements = 4096
  )
      : counter_(options), min_prepare_elements_(min_prepare_elements) {}

  TslIaaFrequencyRunDetector(TslIaaFrequencyRunDetector const &) = delete;
  auto operator=(TslIaaFrequencyRunDetector const &) -> TslIaaFrequencyRunDetector & = delete;

  ~TslIaaFrequencyRunDetector() {
    if (helper_.joinable()) {
      {
        std::lock_guard<std::mutex> lock(mutex_);
        stop_ = true;
      }
      work_ready_.notify_all();
      helper_.join();
    }
  }

  auto metrics() const -> TslFrequencyDetectorMetrics const & { return metrics_; }
  void reset_metrics() { metrics_ = {}; }
  auto counter_metrics() const -> TslIaaFrequencyMetrics const & { return counter_.metrics(); }

  // Starts counting the values of [begin, end) so a later `detect` over the same
  // bounds needs no comparisons.
  //
  // `stable` says [begin, end) will not change until that `detect`, so the walk
  // may read it directly. Without it the values are copied here and the caller is
  // free to permute immediately. Passing `stable` for a buffer the sort then
  // rewrites would make the counts describe data that no longer exists -- the
  // walk's boundary check turns that into a fallback rather than a wrong answer,
  // but it is a caller bug either way.
  void prepare(
    DataType const * values,
    std::size_t begin,
    std::size_t end,
    bool stable = false
  ) {
    if (end - begin < 2 || end - begin < min_prepare_elements_) {
      return;
    }
    // A walk already in flight would be abandoned; wait rather than leak it.
    if (prepared_end_ > prepared_begin_) {
      await_answer();
      prepared_end_ = prepared_begin_;
    }
    auto const count = end - begin;
    DataType const * walk_input = values + begin;
    if (!stable) {
      snapshot_.assign(values + begin, values + end);
      metrics_.snapshot_elements += count;
      walk_input = snapshot_.data();
    }
    ++metrics_.prepared_ranges;
    metrics_.prepared_elements += count;

    ensure_helper();
    counter_.start(walk_input, count);
    {
      std::lock_guard<std::mutex> lock(mutex_);
      prepared_begin_ = begin;
      prepared_end_ = end;
      pending_ = true;
    }
    work_ready_.notify_one();
  }

  // Emits every maximal equal run of length > 1 in [begin, end), ascending.
  // `values` must be sorted over that range.
  template <class Emit>
  void detect(DataType const * values, std::size_t begin, std::size_t end, Emit && emit) {
    if (end - begin < 2) {
      return;
    }
    ++metrics_.ranges;
    metrics_.elements += end - begin;

    auto counting_emit = [&](TslRunSpan span) {
      ++metrics_.spans_emitted;
      emit(span);
    };

    if (prepared_begin_ != begin || prepared_end_ != end) {
      ++metrics_.fallback_unprepared;
      tsl_for_each_equal_run(values, begin, end, counting_emit);
      return;
    }
    await_answer();
    map_type counts;
    {
      std::lock_guard<std::mutex> lock(mutex_);
      counts = std::move(answer_);
      answer_.clear();
    }
    prepared_end_ = prepared_begin_;
    metrics_.distinct_values += counts.size();

    // The walk. One step per run, no comparison: the count is the run length.
    auto position = begin;
    while (position < end) {
      auto const value = values[position];
      auto const found = counts.find(value);
      auto const length = found == counts.end() ? std::size_t{0} : found->second;
      auto const run_end = position + length;
      // Two loads confirm the run the count claims: its last element must be the
      // value, and the next must not. Cheap -- O(1) per run against O(1) per
      // element for a scan -- and it is what keeps a map that does not describe
      // this range from producing spans that are wrong rather than absent. A
      // count that is merely too small stays inside the range, so an overrun
      // check alone would not catch it.
      auto const consistent =
        length != 0 && run_end <= end && values[run_end - 1] == value
        && (run_end == end || values[run_end] != value);
      if (!consistent) {
        ++metrics_.fallback_mismatch;
        // Restart from `begin`, not from here: spans already emitted came from the
        // same untrustworthy map, so the caller must see one consistent set.
        tsl_for_each_equal_run(values, begin, end, counting_emit);
        return;
      }
      ++metrics_.walk_steps;
      if (run_end - position > 1) {
        counting_emit(TslRunSpan{position, run_end});
      }
      position = run_end;
    }
  }

  template <class Emit>
  void operator()(DataType const * values, std::size_t begin, std::size_t end, Emit && emit) {
    detect(values, begin, end, std::forward<Emit>(emit));
  }
};


// A pool of detectors, borrowed for the duration of a (prepare, detect) *pair*.
//
// This cannot be the per-call borrow the run-detector fleets use: the counts one
// call prepares are consumed by the next, so the lease has to survive between
// them. Nor can it be a slot fixed per thread -- the sorters start fresh workers
// on every parallel call while a detector is constructed once per case, so
// slot-per-thread needs as many slots as (iterations x workers), and each
// detector owns a helper thread. So `prepare` takes a detector and holds it in a
// thread-local, and `detect` uses that one and returns it. A `detect` with no
// lease borrows and returns within the call, which is what an incremental caller
// does.
template <class DataType>
class TslFrequencyDetectorFleet {
  using detector_type = TslIaaFrequencyRunDetector<DataType>;

  std::vector<std::unique_ptr<detector_type>> detectors_;
  std::vector<detector_type *> available_;
  mutable std::mutex mutex_;
  std::condition_variable released_;

  // The lease this thread holds on this fleet, if any. Keyed on the fleet so two
  // of them cannot be confused; a thread is only ever inside one at a time here.
  auto lease_slot() -> detector_type *& {
    thread_local void const * owner = nullptr;
    thread_local detector_type * leased = nullptr;
    if (owner != this) {
      owner = this;
      leased = nullptr;
    }
    return leased;
  }

  auto acquire() -> detector_type * {
    std::unique_lock<std::mutex> lock(mutex_);
    released_.wait(lock, [this] { return !available_.empty(); });
    auto * detector = available_.back();
    available_.pop_back();
    return detector;
  }

  void release(detector_type * detector) {
    {
      std::lock_guard<std::mutex> lock(mutex_);
      available_.push_back(detector);
    }
    released_.notify_one();
  }

 public:
  TslFrequencyDetectorFleet(
    TslIaaFrequencyOptions options,
    std::size_t worker_count,
    std::size_t min_prepare_elements = 4096
  ) {
    auto const size = worker_count + 1;
    detectors_.reserve(size);
    available_.reserve(size);
    for (std::size_t slot = 0; slot < size; ++slot) {
      detectors_.push_back(std::make_unique<detector_type>(options, min_prepare_elements));
      available_.push_back(detectors_.back().get());
    }
  }

  void prepare(
    DataType const * values,
    std::size_t begin,
    std::size_t end,
    bool stable = false
  ) {
    auto *& leased = lease_slot();
    if (leased == nullptr) {
      leased = acquire();
    }
    leased->prepare(values, begin, end, stable);
  }

  template <class Emit>
  void operator()(DataType const * values, std::size_t begin, std::size_t end, Emit && emit) {
    auto *& leased = lease_slot();
    auto * detector = leased;
    if (detector != nullptr) {
      leased = nullptr;
    } else {
      detector = acquire();
    }
    try {
      detector->detect(values, begin, end, std::forward<Emit>(emit));
    } catch (...) {
      release(detector);
      throw;
    }
    release(detector);
  }

  auto aggregate_metrics() const -> TslFrequencyDetectorMetrics {
    std::lock_guard<std::mutex> lock(mutex_);
    TslFrequencyDetectorMetrics total{};
    for (auto const & detector : detectors_) {
      auto const & m = detector->metrics();
      total.ranges += m.ranges;
      total.elements += m.elements;
      total.prepared_ranges += m.prepared_ranges;
      total.prepared_elements += m.prepared_elements;
      total.snapshot_elements += m.snapshot_elements;
      total.distinct_values += m.distinct_values;
      total.walk_steps += m.walk_steps;
      total.fallback_unprepared += m.fallback_unprepared;
      total.fallback_mismatch += m.fallback_mismatch;
      total.spans_emitted += m.spans_emitted;
    }
    return total;
  }
};
