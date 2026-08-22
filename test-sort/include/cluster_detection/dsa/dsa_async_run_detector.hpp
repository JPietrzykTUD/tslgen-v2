#pragma once

// Asynchronous DSA equal-run detection: hands a sorted range to the accelerator
// and returns immediately, so the calling worker goes back to sorting while the
// device scans.
//
// -----------------------------------------------------------------------------
// No thread waits on the device
// -----------------------------------------------------------------------------
// There is no dedicated poller. `dml::handler::is_finished()` is a single load
// of the completion-record status byte, so completion checks are folded into
// work the executor already does: every worker calls `poll()` at each task
// boundary. A worker therefore never blocks on the device, and no core is
// consumed waiting.
//
// Deliberately NOT used: `dml::execute` and `handler::get()` before
// `is_finished()`. Both funnel into DML's `wait()`, which is either a
// `_mm_pause` spin or a UMONITOR/UMWAIT loop -- in both cases the thread is
// parked and unavailable, which is exactly what this class exists to avoid.
//
// The one case completion checks alone cannot cover is an empty task queue with
// descriptors still in flight: nothing would wake a sleeping worker, because the
// device cannot signal a condition variable and user-space DSA completion is
// record-based rather than interrupt-based. The executor closes that with a
// bounded `wait_for` used only while pending units exist; see the starvation
// safeguard in multicolumn_sort_tasks.hpp.
//
// -----------------------------------------------------------------------------
// Lifetime rules that make this safe
// -----------------------------------------------------------------------------
// 1. The emitted callable outlives the caller's stack frame. `detect` stores it
//    in the job, and spans are emitted long after the producing task returned.
//    The caller must therefore pass a self-contained callable -- one that copies
//    whatever it needs rather than capturing task-local state by reference.
// 2. The range must stay sorted and immutable until the job completes. On the
//    post-sort path a task owns its whole range, descendants only write later
//    columns, and rows permuted inside an equal run carry identical values in
//    this column, so the bytes the device reads never change.
// 3. Regions of one job are refined strictly in index order, so emitted spans
//    stay ascending even though the device may complete them out of order.
//
// A range is split into regions of at most 512 KiB (the `create_delta` transfer
// maximum). Only `window_depth` of them are in flight at once: submitting all
// regions of a large range would need one delta buffer each, which for a 60 MiB
// range is well over 70 MiB of scratch.

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <exception>
#include <functional>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include "cluster_detection/dsa/dsa_run_detector.hpp"
#include "cluster_detection/scalar/equal_runs.hpp"
#include "sorting/common/multicolumn_sort_tasks.hpp"
#include "sorting/common/multicolumn_sort_types.hpp"

#ifdef TSL_COSORT_ENABLE_DSA
#include <dml/dml.hpp>
#endif


struct TslDsaAsyncMetrics {
  std::size_t ranges = 0;              // detect() calls with >= 2 elements
  std::size_t elements = 0;
  std::size_t offloaded_ranges = 0;    // ranges that became a device job
  std::size_t offloaded_elements = 0;
  std::size_t descriptors = 0;
  std::size_t fired_blocks = 0;
  std::size_t spans_emitted = 0;
  std::size_t fallback_small = 0;      // below the offload threshold
  std::size_t fallback_no_slot = 0;    // job pool exhausted
  std::size_t poll_calls = 0;
  std::size_t poll_advances = 0;       // completions observed by a poll
  std::size_t poll_empty = 0;          // polls that found nothing finished
};


#ifdef TSL_COSORT_ENABLE_DSA

template <class DataType>
class TslDsaAsyncRunDetector {
  static_assert(sizeof(DataType) <= 8 && (8u % sizeof(DataType)) == 0,
                "element width must divide the 8-byte create_delta block");
  static constexpr std::size_t block_elements = 8u / sizeof(DataType);

  using handler_t = dml::handler<dml::create_delta_operation, std::allocator<std::uint8_t>>;

  // One in-flight descriptor plus the delta buffer it writes into.
  struct region_slot {
    handler_t handler{};
    tsl_dsa_detail::aligned_bytes deltas;
    std::size_t base = 0;         // absolute index of the region start
    std::size_t elems = 0;        // region length in elements
    std::size_t delta_elems = 0;  // elements actually compared
    bool active = false;
  };

  struct job {
    DataType const * values = nullptr;
    std::size_t begin = 0;
    std::size_t end = 0;
    std::size_t next_base = 0;   // absolute base of the next region to submit
    std::size_t run_begin = 0;   // boundary -> span cursor
    std::function<void(TslRunSpan)> emit;
    std::vector<region_slot> window;
    std::size_t head = 0;        // oldest in-flight slot
    std::size_t tail = 0;        // next slot to fill
    std::size_t in_flight = 0;
    // Claimed by whichever worker advances this job; refinement runs outside
    // the pool mutex so concurrent polls do not serialize on it.
    std::atomic<bool> busy{false};
    // Bumped every time the slot is released. A poller works from a snapshot of
    // the active list, and the job it points at may have completed and been
    // reused by another thread's detect() in the meantime; comparing the
    // generation it recorded rejects that stale pointer before touching any
    // non-atomic field of a job someone else is initializing.
    std::atomic<std::uint64_t> generation{0};
    bool finished = false;
  };

  TslRleBackend backend_;
  std::size_t region_elements_;
  std::size_t min_offload_elements_;
  std::size_t window_depth_;
  TslPendingWork * pending_ = nullptr;

  std::mutex pool_mutex_;
  std::vector<std::unique_ptr<job>> pool_;    // owns every job object
  std::vector<job *> free_;                   // available slots
  std::vector<job *> active_;                 // jobs with work outstanding

  std::mutex metrics_mutex_;
  TslDsaAsyncMetrics metrics_{};

 public:
  TslDsaAsyncRunDetector(
    TslRleBackend backend,
    std::size_t slots = 4,
    std::size_t window_depth = 4,
    std::size_t region_bytes = tsl_dsa_default_region_bytes,
    std::size_t min_offload_elements = 4096
  )
      : backend_(backend),
        min_offload_elements_(min_offload_elements),
        window_depth_(std::max<std::size_t>(window_depth, 1)) {
    if (region_bytes == 0 || region_bytes % 8u != 0) {
      throw std::invalid_argument("region_bytes must be a non-zero multiple of 8");
    }
    if (region_bytes > tsl_dsa_max_region_bytes) {
      throw std::invalid_argument("region_bytes exceeds the create_delta transfer maximum");
    }
    region_elements_ = region_bytes / sizeof(DataType);

    // Worst case one 10-byte delta record per 8 input bytes, so a full buffer
    // can never overflow. Overflow would silently drop boundaries and merge two
    // distinct-value runs into one span, corrupting the sort.
    auto const buffer_bytes = std::max<std::size_t>((region_bytes / 8u) * sizeof(TslDsaDeltaRecord), 128u);

    pool_.reserve(slots);
    free_.reserve(slots);
    for (std::size_t slot = 0; slot < slots; ++slot) {
      auto owned = std::make_unique<job>();
      owned->window.resize(window_depth_);
      for (auto & region : owned->window) {
        region.deltas = tsl_dsa_detail::aligned_bytes(buffer_bytes);
      }
      free_.push_back(owned.get());
      pool_.push_back(std::move(owned));
    }
  }

  // Must be called before the first task is submitted.
  void bind(TslPendingWork & pending) { pending_ = &pending; }

  auto metrics() -> TslDsaAsyncMetrics {
    std::lock_guard<std::mutex> lock(metrics_mutex_);
    return metrics_;
  }

  // Detector seam. `emit` must be self-contained: it is retained past this
  // call and invoked on whichever worker observes the completion.
  template <class Emit>
  void operator()(DataType const * values, std::size_t begin, std::size_t end, Emit && emit) {
    if (end - begin < 2) {
      return;
    }
    {
      std::lock_guard<std::mutex> lock(metrics_mutex_);
      ++metrics_.ranges;
      metrics_.elements += end - begin;
    }

    if (backend_ == TslRleBackend::SCALAR || pending_ == nullptr
        || (end - begin) < min_offload_elements_) {
      if (backend_ != TslRleBackend::SCALAR && pending_ != nullptr) {
        std::lock_guard<std::mutex> lock(metrics_mutex_);
        ++metrics_.fallback_small;
      }
      scan_scalar(values, begin, end, emit);
      return;
    }

    job * claimed = nullptr;
    {
      std::lock_guard<std::mutex> lock(pool_mutex_);
      if (!free_.empty()) {
        claimed = free_.back();
        free_.pop_back();
      }
    }
    if (claimed == nullptr) {
      {
        std::lock_guard<std::mutex> lock(metrics_mutex_);
        ++metrics_.fallback_no_slot;
      }
      scan_scalar(values, begin, end, emit);
      return;
    }

    claimed->values = values;
    claimed->begin = begin;
    claimed->end = end;
    claimed->run_begin = begin;
    claimed->head = 0;
    claimed->tail = 0;
    claimed->in_flight = 0;
    claimed->finished = false;
    claimed->emit = std::forward<Emit>(emit);

    // Scalar prologue until the source pointer is 8-byte aligned. Runs here, on
    // the calling thread, before the job is visible to any poller, so the span
    // cursor is not shared yet.
    std::size_t position = begin;
    while (position + 1 < end
           && (reinterpret_cast<std::uintptr_t>(values + position) % 8u) != 0) {
      if (values[position] != values[position + 1]) {
        emit_boundary(*claimed, position);
      }
      ++position;
    }
    claimed->next_base = position;

    // add_pending BEFORE the first submission: a fast completion must never
    // resolve a count that does not exist yet.
    pending_->add_pending(1);

    try {
      while (claimed->in_flight < window_depth_ && claimed->next_base + 1 < end) {
        submit_next_region(*claimed);
      }
    } catch (...) {
      pending_->fail(std::current_exception());
      release(*claimed);
      return;
    }

    if (claimed->in_flight == 0) {
      // Nothing was worth a descriptor (a very short aligned remainder): finish
      // it here rather than leaving a job that no completion will ever advance.
      finalize(*claimed);
      return;
    }

    {
      std::lock_guard<std::mutex> lock(pool_mutex_);
      active_.push_back(claimed);
    }
    {
      std::lock_guard<std::mutex> lock(metrics_mutex_);
      ++metrics_.offloaded_ranges;
    }
  }

  // Called by workers at task boundaries and on idle deadlines. Never blocks.
  void poll() {
    std::vector<std::pair<job *, std::uint64_t>> snapshot;
    {
      std::lock_guard<std::mutex> lock(pool_mutex_);
      if (active_.empty()) {
        return;
      }
      snapshot.reserve(active_.size());
      for (auto * candidate : active_) {
        snapshot.emplace_back(candidate, candidate->generation.load(std::memory_order_relaxed));
      }
    }

    std::size_t advances = 0;
    for (auto const & entry : snapshot) {
      auto * candidate = entry.first;
      bool expected = false;
      if (!candidate->busy.compare_exchange_strong(expected, true, std::memory_order_acquire)) {
        continue;  // another worker is advancing this job
      }
      if (candidate->generation.load(std::memory_order_acquire) != entry.second) {
        // Recycled since the snapshot: not ours to touch.
        candidate->busy.store(false, std::memory_order_release);
        continue;
      }
      try {
        advances += advance(*candidate);
      } catch (...) {
        candidate->busy.store(false, std::memory_order_release);
        pending_->fail(std::current_exception());
        return;
      }
      candidate->busy.store(false, std::memory_order_release);
    }

    std::lock_guard<std::mutex> lock(metrics_mutex_);
    ++metrics_.poll_calls;
    metrics_.poll_advances += advances;
    if (advances == 0) {
      ++metrics_.poll_empty;
    }
  }

 private:
  template <class Emit>
  void scan_scalar(DataType const * values, std::size_t begin, std::size_t end, Emit & emit) {
    std::size_t spans = 0;
    tsl_for_each_equal_run(values, begin, end, [&](TslRunSpan span) {
      ++spans;
      emit(span);
    });
    std::lock_guard<std::mutex> lock(metrics_mutex_);
    metrics_.spans_emitted += spans;
  }

  // Boundary at `position` means values[position] != values[position + 1].
  void emit_boundary(job & active, std::size_t position) {
    if (position + 1 - active.run_begin > 1) {
      active.emit(TslRunSpan{active.run_begin, position + 1});
      std::lock_guard<std::mutex> lock(metrics_mutex_);
      ++metrics_.spans_emitted;
    }
    active.run_begin = position + 1;
  }

  void submit_next_region(job & active) {
    auto const base = active.next_base;
    auto const remaining = active.end - base;
    auto const elems = std::min(region_elements_, remaining);
    auto & slot = active.window[active.tail];

    std::size_t delta_elems = 0;
    if (elems > block_elements) {
      delta_elems = ((elems - block_elements) / block_elements) * block_elements;
    }

    slot.base = base;
    slot.elems = elems;
    slot.delta_elems = delta_elems;
    slot.active = true;

    if (delta_elems > 0) {
      auto const * source_1 = active.values + base + block_elements;
      auto const * source_2 = active.values + base;
      auto * delta_out = static_cast<std::uint8_t *>(slot.deltas.data());
      slot.handler = (backend_ == TslRleBackend::DSA_HARDWARE)
        ? dml::submit<dml::hardware>(
            dml::create_delta.block_on_fault(),
            dml::make_view(source_1, delta_elems), dml::make_view(source_2, delta_elems),
            dml::make_view(delta_out, slot.deltas.size()))
        : dml::submit<dml::software>(
            dml::create_delta.block_on_fault(),
            dml::make_view(source_1, delta_elems), dml::make_view(source_2, delta_elems),
            dml::make_view(delta_out, slot.deltas.size()));
      std::lock_guard<std::mutex> lock(metrics_mutex_);
      ++metrics_.descriptors;
      metrics_.offloaded_elements += delta_elems;
    }

    active.next_base = base + elems;
    active.tail = (active.tail + 1) % window_depth_;
    ++active.in_flight;
  }

  // Retires every completed region at the head of the window, in order.
  // Returns how many regions were retired.
  auto advance(job & active) -> std::size_t {
    std::size_t retired = 0;
    while (active.in_flight != 0) {
      auto & slot = active.window[active.head];
      if (slot.delta_elems > 0 && !slot.handler.is_finished()) {
        break;  // still in flight; later regions must not be refined first
      }
      refine_region(active, slot);
      slot.active = false;
      active.head = (active.head + 1) % window_depth_;
      --active.in_flight;
      ++retired;

      if (active.next_base + 1 < active.end) {
        submit_next_region(active);
      }
    }

    if (active.in_flight == 0 && retired != 0) {
      finalize(active);
    }
    return retired;
  }

  void refine_region(job & active, region_slot & slot) {
    if (slot.delta_elems > 0) {
      auto const result = slot.handler.get();
      if (result.status != dml::status_code::ok) {
        throw std::runtime_error(
          "async create_delta failed with DML status "
          + std::to_string(static_cast<std::uint32_t>(result.status))
        );
      }
      if (result.delta_record_size > slot.deltas.size()) {
        throw std::runtime_error("async create_delta reported more delta bytes than the buffer holds");
      }
      auto const fired = result.delta_record_size / sizeof(TslDsaDeltaRecord);
      auto const * records = static_cast<TslDsaDeltaRecord const *>(slot.deltas.data());
      for (std::size_t index = 0; index < fired; ++index) {
        auto const block_base = slot.base + std::size_t{records[index].offset} * block_elements;
        for (std::size_t offset = 0; offset < block_elements; ++offset) {
          auto const position = block_base + offset;
          if (active.values[position] != active.values[position + 1]) {
            emit_boundary(active, position);
          }
        }
      }
      std::lock_guard<std::mutex> lock(metrics_mutex_);
      metrics_.fired_blocks += fired;
    }

    // Boundaries the compare did not cover: the ragged tail plus the seam index
    // shared with the next region, hence `< slot.base + slot.elems`.
    for (auto position = slot.base + slot.delta_elems;
         position + 1 < active.end && position < slot.base + slot.elems;
         ++position) {
      if (active.values[position] != active.values[position + 1]) {
        emit_boundary(active, position);
      }
    }
  }

  // Emits the trailing run, releases the executor's pending unit, and returns
  // the slot. resolve_pending comes last: every child must be scheduled before
  // the parent unit is released, or wait() could observe zero too early.
  void finalize(job & active) {
    if (active.end - active.run_begin > 1) {
      active.emit(TslRunSpan{active.run_begin, active.end});
      std::lock_guard<std::mutex> lock(metrics_mutex_);
      ++metrics_.spans_emitted;
    }
    active.finished = true;
    auto * pending = pending_;
    release(active);
    pending->resolve_pending(1);
  }

  void release(job & active) {
    active.emit = nullptr;
    // Invalidate every snapshot that still points here before the slot can be
    // handed to another detect() call.
    active.generation.fetch_add(1, std::memory_order_release);
    std::lock_guard<std::mutex> lock(pool_mutex_);
    active_.erase(std::remove(active_.begin(), active_.end(), &active), active_.end());
    free_.push_back(&active);
  }
};

#endif  // TSL_COSORT_ENABLE_DSA
