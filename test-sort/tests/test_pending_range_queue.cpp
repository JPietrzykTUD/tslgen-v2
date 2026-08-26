// Unit test for the worklist scheduler an asynchronous detector needs.
//
// Three properties are what separate this queue from a plain shared vector, and
// each one is a wrong answer rather than a hang if it is missing:
//
//   * the sort must not finish while a device still owes it ranges,
//   * an idle worker must drive the detector rather than sleep, because a
//     completion is not a push, and
//   * a published range must outlive the frame that produced it, since the
//     detector retains the emit callable and calls it from another thread later.
//
// None of this needs a sorter, a SIMD backend or an accelerator, so it is tested
// here directly. The detectors below are fakes that defer their spans exactly the
// way `TslDsaAsyncRunDetector` does -- register the debt, keep the callable, emit
// on a later `poll()`.

#include <atomic>
#include <chrono>
#include <cstddef>
#include <cstdio>
#include <functional>
#include <mutex>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

#include "sorting/common/pending_range_queue.hpp"

namespace {

std::size_t g_checks = 0;
std::size_t g_failures = 0;

void check(bool condition, std::string const & what) {
  ++g_checks;
  if (!condition) {
    ++g_failures;
    std::printf("FAIL %s\n", what.c_str());
  }
}

struct range {
  std::size_t column = 0;
  std::size_t begin = 0;
  std::size_t end = 0;
};

using queue = TslPendingRangeQueue<range>;

// Run `body` on `workers` threads, including this one, and join.
template <class Body>
void with_workers(std::size_t workers, Body && body) {
  std::vector<std::thread> pool;
  pool.reserve(workers - 1);
  for (std::size_t id = 1; id < workers; ++id) {
    pool.emplace_back([&body, id] { body(id); });
  }
  body(std::size_t{0});
  for (auto & thread : pool) {
    thread.join();
  }
}

// --- every range delivered exactly once, and every worker released -----------
void plain_worklist() {
  constexpr std::size_t workers = 4;
  constexpr std::size_t count = 500;
  queue pool(workers);
  for (std::size_t index = 0; index < count; ++index) {
    pool.publish(range{0, index, index + 1});
  }
  std::vector<std::atomic<int>> seen(count);
  std::atomic<std::size_t> released{0};

  with_workers(workers, [&](std::size_t) {
    range taken;
    while (pool.take(taken)) {
      ++seen[taken.begin];
    }
    ++released;
  });

  std::size_t exactly_once = 0;
  for (auto const & flag : seen) {
    exactly_once += flag.load() == 1 ? 1 : 0;
  }
  check(exactly_once == count, "every published range taken exactly once");
  check(released.load() == workers, "every worker released when the pool drained");
  check(pool.published() == count, "published count matches what was pushed");
}

// --- a worker that produces work keeps the others alive ----------------------
void children_keep_workers_alive() {
  constexpr std::size_t workers = 3;
  queue pool(workers);
  pool.publish(range{0, 0, 64});
  std::atomic<std::size_t> processed{0};

  with_workers(workers, [&](std::size_t) {
    range taken;
    while (pool.take(taken)) {
      ++processed;
      // A binary descent: each range publishes two halves until they are single
      // elements. Total ranges for a 64-wide root is 127.
      auto const width = taken.end - taken.begin;
      if (width > 1) {
        auto const middle = taken.begin + width / 2;
        pool.publish(range{taken.column + 1, taken.begin, middle});
        pool.publish(range{taken.column + 1, middle, taken.end});
      }
    }
  });
  check(processed.load() == 127, "descent ran to completion across workers");
}

// --- the debt is part of the termination condition ---------------------------
// Without add_pending in the predicate, every worker goes idle with an empty pool
// and the sort reports completion while the range is still on the device.
void no_finish_while_pending() {
  constexpr std::size_t workers = 3;
  queue pool(workers);
  std::atomic<std::size_t> finished{0};
  std::atomic<std::size_t> taken_count{0};
  pool.add_pending(1);

  std::vector<std::thread> pool_threads;
  for (std::size_t id = 0; id < workers; ++id) {
    pool_threads.emplace_back([&] {
      range taken;
      while (pool.take(taken)) {
        ++taken_count;
      }
      ++finished;
    });
  }

  std::this_thread::sleep_for(std::chrono::milliseconds(50));
  check(finished.load() == 0, "no worker finished while a debt was outstanding");

  // The completion: publish the discovered range, then resolve. In that order,
  // as the detector contract requires.
  pool.publish(range{1, 0, 8});
  pool.resolve_pending(1);

  for (auto & thread : pool_threads) {
    thread.join();
  }
  check(taken_count.load() == 1, "the range published on completion was delivered");
  check(finished.load() == workers, "every worker finished once the debt cleared");
}

// --- an idle worker drives the detector --------------------------------------
// A fake asynchronous detector: it keeps the emit callable and produces its spans
// only when polled. Nothing notifies the queue, so if idle workers slept on the
// condition variable this would never complete.
class deferred_detector {
 public:
  explicit deferred_detector(std::size_t polls_before_completion)
      : polls_needed_(polls_before_completion) {}

  void bind(TslPendingWork & pending) { pending_ = &pending; }

  // Same shape as the real detector's seam: the callable is stored, not called.
  template <class Emit>
  void submit(std::size_t begin, std::size_t end, Emit && emit) {
    std::lock_guard<std::mutex> lock(mutex_);
    pending_->add_pending(1);
    emit_ = std::forward<Emit>(emit);
    begin_ = begin;
    end_ = end;
  }

  void poll() {
    std::function<void(std::size_t, std::size_t)> emit;
    {
      std::lock_guard<std::mutex> lock(mutex_);
      ++polls_;
      if (!emit_ || polls_ < polls_needed_) {
        return;
      }
      emit = emit_;
      emit_ = nullptr;
    }
    // Emitted outside the lock, exactly where the real detector emits: on the
    // polling thread, after the submitting frame is long gone.
    emit(begin_, end_);
    pending_->resolve_pending(1);
  }

  auto polls() -> std::size_t {
    std::lock_guard<std::mutex> lock(mutex_);
    return polls_;
  }

 private:
  std::mutex mutex_;
  TslPendingWork * pending_ = nullptr;
  std::function<void(std::size_t, std::size_t)> emit_;
  std::size_t polls_ = 0;
  std::size_t polls_needed_;
  std::size_t begin_ = 0;
  std::size_t end_ = 0;
};

void polling_delivers_completions() {
  constexpr std::size_t workers = 2;
  queue pool(workers);
  deferred_detector detector(5);
  detector.bind(pool);
  pool.set_poller([&detector] { detector.poll(); });

  // The emitter owns everything it touches: the queue by pointer and the column
  // by value. This is the contract a sorter's emit callable has to satisfy, and
  // the scope below going away is what would break a frame-capturing one.
  {
    auto * sink = &pool;
    std::size_t const next_column = 2;
    detector.submit(0, 32, [sink, next_column](std::size_t begin, std::size_t end) {
      sink->publish(range{next_column, begin, end});
    });
  }

  std::atomic<std::size_t> delivered{0};
  std::size_t observed_column = 0;
  std::mutex observed_mutex;
  with_workers(workers, [&](std::size_t) {
    range taken;
    while (pool.take(taken)) {
      ++delivered;
      std::lock_guard<std::mutex> lock(observed_mutex);
      observed_column = taken.column;
    }
  });

  check(delivered.load() == 1, "the deferred range was delivered");
  check(observed_column == 2, "the emitter's captured column survived its frame");
  check(detector.polls() >= 5, "idle workers polled the detector rather than sleeping");
}

// --- a failure off a worker thread stops the sort and reaches the caller ------
void failure_propagates() {
  constexpr std::size_t workers = 3;
  queue pool(workers);
  pool.add_pending(1);
  pool.publish(range{0, 0, 4});

  std::atomic<std::size_t> finished{0};
  // Whichever worker gets the range raises, which is where a detector failure
  // actually surfaces: on a worker thread, with the others waiting on a debt that
  // will now never be resolved.
  with_workers(workers, [&](std::size_t) {
    range taken;
    while (pool.take(taken)) {
      pool.fail(std::make_exception_ptr(std::runtime_error("device refused")));
    }
    ++finished;
  });

  check(finished.load() == workers, "every worker released after a failure");
  check(pool.failed(), "the failure was recorded");
  bool rethrown = false;
  try {
    pool.rethrow_if_failed();
  } catch (std::runtime_error const & error) {
    rethrown = std::string(error.what()) == "device refused";
  }
  check(rethrown, "the original exception reached the caller");
}

// --- a sequential phase can settle the debt itself ---------------------------
void drain_settles_debt() {
  queue pool(1);
  deferred_detector detector(3);
  detector.bind(pool);
  pool.set_poller([&detector] { detector.poll(); });
  auto * sink = &pool;
  detector.submit(4, 20, [sink](std::size_t begin, std::size_t end) {
    sink->publish(range{1, begin, end});
  });

  std::vector<range> drained;
  pool.drain_into(drained);
  check(drained.size() == 1, "drain_into returned the completed range");
  check(!drained.empty() && drained.front().begin == 4 && drained.front().end == 20,
        "drain_into returned the range the detector emitted");
}

}  // namespace

int main() {
  struct named { char const * name; void (*run)(); };
  for (auto const & entry : {
         named{"plain worklist", plain_worklist},
         named{"children keep workers alive", children_keep_workers_alive},
         named{"no finish while pending", no_finish_while_pending},
         named{"polling delivers completions", polling_delivers_completions},
         named{"failure propagates", failure_propagates},
         named{"drain settles debt", drain_settles_debt}}) {
    std::printf("-- %s\n", entry.name);
    std::fflush(stdout);
    entry.run();
  }

  if (g_failures != 0) {
    std::printf("\npending range queue tests FAILED: %zu of %zu checks\n", g_failures,
                g_checks);
    return 1;
  }
  std::printf("\npending range queue tests passed (%zu checks)\n", g_checks);
  return 0;
}
