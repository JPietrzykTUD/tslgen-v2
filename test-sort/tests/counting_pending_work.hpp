#pragma once

// A `TslPendingWork` that only counts, for tests that drive an asynchronous
// detector without a sorter.
//
// An asynchronous detector needs the accounting interface, not a running
// executor: it registers a unit before handing a range to the device and resolves
// it after every span has been emitted. A test can therefore call `poll()` itself
// and use `busy()` as the completion condition, which is what makes an
// accelerator detector testable without a thread pool.

#include "sorting/common/multicolumn_sort_types.hpp"

#include <cstddef>
#include <exception>
#include <mutex>

struct TslCountingPendingWork : TslPendingWork {
  std::mutex mutex;
  std::size_t outstanding = 0;
  std::size_t registered = 0;   // total add_pending calls, so a test can assert
                                // the offload route was taken at all
  std::exception_ptr error;

  void add_pending(std::size_t count) override {
    std::lock_guard<std::mutex> lock(mutex);
    outstanding += count;
    registered += count;
  }

  void resolve_pending(std::size_t count) override {
    std::lock_guard<std::mutex> lock(mutex);
    outstanding -= count;
  }

  void fail(std::exception_ptr raised) override {
    std::lock_guard<std::mutex> lock(mutex);
    if (!error) {
      error = raised;
    }
  }

  auto busy() -> bool {
    std::lock_guard<std::mutex> lock(mutex);
    return outstanding != 0;
  }

  auto offloaded() -> std::size_t {
    std::lock_guard<std::mutex> lock(mutex);
    return registered;
  }
};
