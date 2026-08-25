#pragma once

// A fixed pool of objects too stateful to share, handed out one at a time.
//
// -----------------------------------------------------------------------------
// Why borrowing rather than a slot per thread
// -----------------------------------------------------------------------------
// An accelerator-backed detector owns a device job and a scratch buffer and keeps
// mutable counters, so two threads cannot use one at once. It is *not* bound to a
// thread for its lifetime, though, and must not be: an executor starts fresh
// workers on every parallel sort while a pool is constructed once per case, so a
// scheme that gives each new thread its own permanent slot needs as many slots as
// (sorts x workers) rather than as many as run concurrently -- and throws on the
// second sort. That bug was found twice, in two different fleets, before this was
// written down in one place.
//
// Borrowing bounds the pool by concurrency instead. The mutex is held only across
// the handover, never across the work, and every borrower does at least one
// accelerator round trip, so the handover is noise.
//
// -----------------------------------------------------------------------------
// Two ways to hold one
// -----------------------------------------------------------------------------
// `borrow()` returns a lease that returns the object however the scope exits,
// which is what a single call wants. `acquire()`/`release()` are for a caller
// whose lease has to span more than one call -- the frequency detector holds one
// from `prepare` to `detect`, because the counts it starts are the ones it later
// walks. Such a caller owns the pairing; this only lends the object.

#include <cstddef>
#include <condition_variable>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <utility>
#include <vector>


template <class T>
class TslBorrowPool {
  std::vector<std::unique_ptr<T>> owned_;
  std::vector<T *> available_;
  mutable std::mutex mutex_;
  std::condition_variable released_;

 public:
  // Returns the object to the pool however the borrower leaves the scope.
  class lease {
    TslBorrowPool * pool_;
    T * object_;

   public:
    lease(TslBorrowPool & pool, T * object) : pool_(&pool), object_(object) {}
    lease(lease const &) = delete;
    auto operator=(lease const &) -> lease & = delete;
    lease(lease && other) noexcept : pool_(other.pool_), object_(other.object_) {
      other.object_ = nullptr;
    }
    auto operator=(lease &&) -> lease & = delete;
    ~lease() {
      if (object_ != nullptr) {
        pool_->release(object_);
      }
    }
    auto get() const -> T & { return *object_; }
    auto operator->() const -> T * { return object_; }
  };

  // `size` objects, each built by `make(slot)`. Callers size this as
  // `worker_count + 1`: the caller's thread may also run work inline.
  template <class Factory>
  TslBorrowPool(std::size_t size, Factory && make) {
    if (size == 0) {
      throw std::invalid_argument("a borrow pool needs at least one object");
    }
    owned_.reserve(size);
    available_.reserve(size);
    for (std::size_t slot = 0; slot < size; ++slot) {
      owned_.push_back(make(slot));
      available_.push_back(owned_.back().get());
    }
  }

  TslBorrowPool(TslBorrowPool const &) = delete;
  auto operator=(TslBorrowPool const &) -> TslBorrowPool & = delete;

  auto borrow() -> lease { return lease(*this, acquire()); }

  // Only waits when more threads borrow concurrently than the pool was sized
  // for, which the worker count makes unexpected rather than impossible.
  auto acquire() -> T * {
    std::unique_lock<std::mutex> lock(mutex_);
    released_.wait(lock, [this] { return !available_.empty(); });
    auto * object = available_.back();
    available_.pop_back();
    return object;
  }

  void release(T * object) {
    {
      std::lock_guard<std::mutex> lock(mutex_);
      available_.push_back(object);
    }
    released_.notify_one();
  }

  auto size() const -> std::size_t { return owned_.size(); }

  // Visits every object, borrowed or not, under the lock. For aggregating the
  // per-object counters after the work has joined.
  template <class Visit>
  void for_each(Visit && visit) const {
    std::lock_guard<std::mutex> lock(mutex_);
    for (auto const & object : owned_) {
      visit(*object);
    }
  }

  template <class Visit>
  void for_each(Visit && visit) {
    std::lock_guard<std::mutex> lock(mutex_);
    for (auto & object : owned_) {
      visit(*object);
    }
  }
};
