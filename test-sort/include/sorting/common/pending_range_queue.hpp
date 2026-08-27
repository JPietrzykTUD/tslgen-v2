#pragma once

// A shared range worklist that also implements `TslPendingWork`, so a sorter
// whose scheduler is a worklist rather than a task tree can carry an
// asynchronous detector.
//
// Why this exists as its own concept. An asynchronous detector hands a range to a
// device and returns; the spans arrive later, on whichever thread observes the
// completion. Three things follow, and a plain worklist has none of them:
//
//   1. **Termination cannot be "no queued work and every worker idle."** A range
//      whose descriptor is in flight has produced no children yet, so that
//      condition is reachable while the device still owes the sort its next
//      column. Ending there does not hang -- it returns a partially sorted table,
//      which is the worse failure. `add_pending` / `resolve_pending` make that
//      debt part of the termination condition.
//   2. **Nothing wakes a sleeping worker when the remaining work is on a device.**
//      A completion is not a push. So a worker that idles while a debt is
//      outstanding polls on a timeout instead of sleeping on the condition
//      variable, exactly as `TslTaskExecutor` does for the task tree.
//   3. **A published range must outlive the frame that produced it.** The
//      detector retains the emit callable past the call, so an emitter writing
//      into a caller-local vector is a dangling reference the moment that frame
//      returns. `publish` is callable from any thread and owns what it stores, so
//      an emitter needs to capture nothing but this queue and a column index.
//
// This is deliberately *not* the task executor. `TslTaskExecutor` routes every
// task through one queue, which is right for the quicksort's tree and measured
// wrong for the samplesort: a shared queue capped it at 1.04x on 24 threads
// against 8.2x with per-worker local stacks. So the local stacks stay with the
// worker and this queue owns only what the workers must agree on -- the shared
// pool, the idle count, the outstanding debt, and the first failure.
//
// Failure handling is part of the contract rather than an extra: `fail` is how a
// detector reports an exception raised off a worker thread, and without somewhere
// to put it that throw reaches `std::terminate`.

#include "sorting/common/multicolumn_sort_tasks.hpp"
#include "sorting/common/multicolumn_sort_types.hpp"

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstddef>
#include <exception>
#include <functional>
#include <mutex>
#include <utility>
#include <vector>


template <class Range>
class TslPendingRangeQueue final : public TslPendingWork {
 public:
  // `workers` counts every thread that will call `take`, including the caller's
  // own. The poll interval is the longest a worker may sleep while a device still
  // owes the sort work; 200us is the task executor's value, for the same reason.
  explicit TslPendingRangeQueue(
    std::size_t workers,
    std::chrono::microseconds poll_interval = std::chrono::microseconds{200}
  )
      : workers_(workers == 0 ? 1 : workers), poll_interval_(poll_interval) {}

  // Must be set before any range is handed to an asynchronous detector.
  void set_poller(std::function<void()> poller) {
    std::lock_guard<std::mutex> lock(mutex_);
    poller_ = std::move(poller);
  }

  // Callable from any thread, including one running a detector completion.
  void publish(Range const & range) {
    {
      std::lock_guard<std::mutex> lock(mutex_);
      shared_.push_back(range);
      ++published_;
    }
    ready_.notify_one();
  }

  // Several at once: one lock and one wake-up for a range's whole set of
  // children, which is the shape a sorter publishes in.
  void publish_many(std::vector<Range> const & ranges) {
    if (ranges.empty()) {
      return;
    }
    {
      std::lock_guard<std::mutex> lock(mutex_);
      shared_.insert(shared_.end(), ranges.begin(), ranges.end());
      published_ += ranges.size();
    }
    ready_.notify_all();
  }

  // The next range to work on, or false when the sort is over. Blocks while any
  // work could still appear -- from another worker's local stack or from a device.
  auto take(Range & out) -> bool {
    std::unique_lock<std::mutex> lock(mutex_);
    while (true) {
      if (finished_) {
        return false;
      }
      if (!shared_.empty()) {
        out = shared_.back();
        shared_.pop_back();
        return true;
      }
      ++idle_;
      // Nothing queued, nobody working, nothing owed: this is the only state in
      // which no further range can appear.
      if (idle_ == workers_ && pending_ == 0) {
        finished_ = true;
        --idle_;
        ready_.notify_all();
        return false;
      }
      if (pending_ != 0) {
        // A completion is not a notification, so an idle worker drives the
        // detector rather than waiting to be woken.
        //
        // One worker at a time, and bounded. Every `publish` wakes the waiters,
        // and a sort publishes constantly, so letting each of them re-poll on
        // every wake turned into a poll storm: measured 401,138 polls of which
        // 400,180 found nothing, on cores that were meant to be sorting, for a
        // 1.7x penalty against the synchronous offload. Checking a completion is
        // idempotent, so there is nothing to gain from a second worker doing it
        // at the same moment.
        auto poll = poller_;
        if (poll && !polling_) {
          polling_ = true;
          lock.unlock();
          poll();
          lock.lock();
          polling_ = false;
          --idle_;
          // Back off whenever the poll left this worker with nothing to take.
          //
          // The condition used to be `published_ == before`, and that counter is
          // global and monotonic: every worker's every publish moves it. A sort
          // publishes constantly, so on a busy run it had always moved by the time
          // the poll returned, the branch was never taken, and this loop polled at
          // full speed. Measured on a six-worker run at eight columns: 105 polls
          // per descriptor against 1.4 at one worker, where the same detector and
          // the same device produce the same completions. The device was never the
          // problem; the guard asked "did anyone publish anything" when the only
          // thing worth asking is "did I get work".
          //
          // Waiting costs no latency: `resolve_pending` notifies `settled_` on
          // every completion, so a span that lands during the interval wakes this
          // worker immediately. What the interval bounds is the *fruitless* rate.
          if (shared_.empty() && pending_ != 0) {
            settled_.wait_for(lock, poll_interval_);
          }
          continue;
        }
        // Someone else is polling, or nothing polls at all: wait out the interval
        // rather than duplicate the check, and re-examine after it. On `settled_`,
        // so the stream of publishes a sort produces does not wake this worker
        // into another poll it has no reason to make.
        settled_.wait_for(lock, poll_interval_);
        --idle_;
        continue;
      }
      ready_.wait(lock);
      --idle_;
    }
  }

  // For a sequential phase that wants the ranges rather than a worker loop:
  // settle every outstanding debt, then hand over what was published.
  void drain_into(std::vector<Range> & out) {
    std::unique_lock<std::mutex> lock(mutex_);
    while (pending_ != 0 && !finished_) {
      auto poll = poller_;
      if (!poll) {
        settled_.wait_for(lock, poll_interval_);
        continue;
      }
      auto const before = pending_;
      lock.unlock();
      poll();
      lock.lock();
      // Back off when that poll settled nothing. This loop is the sequential
      // phase's drain: there is no other work to interleave, so it spins rather
      // than sleeps -- but a spin with no backoff at all takes the detector's pool
      // lock on every iteration, which is what turned a device that was keeping up
      // into a lock convoy. A pause is tens of cycles against a descriptor's
      // microseconds, so it costs no completion latency.
      if (pending_ == before && pending_ != 0) {
        lock.unlock();
        for (int spin = 0; spin < 64; ++spin) {
          tsl_cpu_pause();
        }
        lock.lock();
      }
    }
    out.insert(out.end(), shared_.begin(), shared_.end());
    shared_.clear();
  }

  // --- TslPendingWork -------------------------------------------------------
  // Called before the work is handed out: a completion that resolved a debt not
  // yet registered would let `take` observe zero and finish early.
  void add_pending(std::size_t count) override {
    std::lock_guard<std::mutex> lock(mutex_);
    pending_ += count;
  }

  // Called after every span of that unit has been published, never before.
  void resolve_pending(std::size_t count) override {
    bool settled = false;
    {
      std::lock_guard<std::mutex> lock(mutex_);
      pending_ = count >= pending_ ? 0 : pending_ - count;
      settled = pending_ == 0;
    }
    // Only the debt reaching zero can change what a waiter decides -- until then
    // there is still something outstanding and nothing new to take -- so that is
    // the only resolution worth waking anyone for.
    if (settled) {
      ready_.notify_all();
    }
    settled_.notify_all();
  }

  void fail(std::exception_ptr error) override {
    {
      std::lock_guard<std::mutex> lock(mutex_);
      if (!error_) {
        error_ = std::move(error);
      }
      // Stop the sort rather than let workers keep taking ranges whose next
      // column will never be discovered.
      finished_ = true;
      shared_.clear();
      pending_ = 0;
    }
    ready_.notify_all();
    settled_.notify_all();
  }

  void rethrow_if_failed() {
    std::exception_ptr error;
    {
      std::lock_guard<std::mutex> lock(mutex_);
      error = error_;
    }
    if (error) {
      std::rethrow_exception(error);
    }
  }

  auto failed() -> bool {
    std::lock_guard<std::mutex> lock(mutex_);
    return static_cast<bool>(error_);
  }

  // Ranges published through this queue. The emitter cannot count into a
  // frame-local metrics struct -- it outlives the frame -- so the count lives
  // here and the caller folds it in once the workers have joined.
  auto published() -> std::size_t {
    std::lock_guard<std::mutex> lock(mutex_);
    return published_;
  }

 private:
  std::size_t const workers_;
  std::chrono::microseconds const poll_interval_;

  std::mutex mutex_;
  // Two conditions, because they wake different waiters. `ready_` means a range
  // is available (or the sort is over) and every worker cares. `settled_` means
  // the outstanding debt moved, which only matters to the one worker that is
  // driving the detector -- waking the rest on it made every publish cost a
  // round of empty polls: measured 401,138 polls of which 400,180 found nothing.
  std::condition_variable ready_;
  std::condition_variable settled_;
  std::vector<Range> shared_;
  std::function<void()> poller_;
  std::exception_ptr error_;
  std::size_t idle_ = 0;
  std::size_t pending_ = 0;
  std::size_t published_ = 0;
  bool finished_ = false;
  bool polling_ = false;
};
