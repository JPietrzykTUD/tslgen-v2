#pragma once

#include <algorithm>
#include <chrono>
#include <condition_variable>
#include <cstddef>
#include <deque>
#include <exception>
#include <functional>
#include <mutex>
#include <stdexcept>
#include <thread>
#include <utility>
#include <vector>


struct TslTaskExecutorMetrics {
  std::size_t tasks_submitted = 0;
  std::size_t tasks_executed_inline = 0;
  std::size_t max_outstanding_tasks = 0;
  std::size_t idle_poll_wakeups = 0;
};


// What an asynchronous producer of work needs from the executor, without
// depending on its template parameters.
//
// `outstanding_` means "units of work that may still produce more work", not
// "queued or running tasks". A unit registered with add_pending keeps wait()
// blocked until resolve_pending, which is what stops the sort from reporting
// completion while an accelerator still holds undiscovered next-column work.
struct TslPendingWork {
  virtual ~TslPendingWork() = default;
  // Call BEFORE handing the work out. A completion that resolved a count which
  // did not exist yet would let wait() observe zero.
  virtual void add_pending(std::size_t count) = 0;
  // Call AFTER every child of that unit has been scheduled, never before.
  virtual void resolve_pending(std::size_t count) = 0;
  // Report a failure raised off a worker thread; a throw there would otherwise
  // reach std::terminate.
  virtual void fail(std::exception_ptr error) = 0;
};

template <class Task, class Worker>
class TslTaskExecutor : public TslPendingWork {
  Worker worker_;
  std::deque<Task> queue_;
  std::vector<std::thread> threads_;
  std::mutex mutex_;
  std::condition_variable work_ready_;
  std::condition_variable all_done_;
  std::exception_ptr error_;
  std::size_t outstanding_ = 0;
  // Pending units registered through add_pending. Counted inside outstanding_;
  // tracked separately because nothing can wake a worker when the only
  // remaining work lives on a device, so an idle worker must time out and poll
  // rather than sleep on the condition variable forever.
  std::size_t pending_external_ = 0;
  std::function<void()> poll_;
  std::chrono::microseconds poll_interval_{200};
  bool shutdown_ = false;
  bool failed_ = false;
  bool joined_ = false;
  TslTaskExecutorMetrics metrics_;

  void record_failure(std::exception_ptr error) {
    {
      std::lock_guard<std::mutex> lock(mutex_);
      if (!failed_) {
        failed_ = true;
        error_ = std::move(error);
        queue_.clear();
        outstanding_ = 0;
        pending_external_ = 0;
      }
    }
    work_ready_.notify_all();
    all_done_.notify_all();
  }

  void worker_loop() {
    while (true) {
      Task task;
      bool have_task = false;
      {
        std::unique_lock<std::mutex> lock(mutex_);
        while (true) {
          if (failed_ || (shutdown_ && queue_.empty())) {
            return;
          }
          if (!queue_.empty()) {
            // Take the newest task. Quicksort partitions publish a child per
            // recursion level, so oldest-first would expand the tree
            // breadth-first and grow the queue with the input size.
            // Newest-first follows the serial visit order and keeps the queue
            // proportional to depth times worker count. Queue order is not part
            // of the executor contract.
            task = std::move(queue_.back());
            queue_.pop_back();
            have_task = true;
            break;
          }
          if (pending_external_ != 0 && poll_) {
            // Starvation safeguard. The queue is empty but a device still holds
            // work that will produce next-column tasks. No thread and no
            // interrupt will notify this condition variable, so sleeping
            // without a deadline would hang until something unrelated happened.
            // Wake on a deadline and let this worker check for completions.
            work_ready_.wait_for(lock, poll_interval_);
            ++metrics_.idle_poll_wakeups;
            break;
          }
          work_ready_.wait(lock);
        }
      }

      if (!have_task) {
        // Woken by the deadline above: check device completions, then retry.
        // Cheap enough to do unconditionally -- a completion test is one load.
        if (!run_poll()) {
          return;
        }
        continue;
      }

      try {
        worker_(task, *this);
      } catch (...) {
        record_failure(std::current_exception());
        return;
      }

      // Amortized completion check: one pass per finished task, so no thread is
      // ever dedicated to waiting on the device.
      if (!run_poll()) {
        return;
      }

      {
        std::lock_guard<std::mutex> lock(mutex_);
        if (!failed_) {
          if (outstanding_ == 0) {
            failed_ = true;
            error_ = std::make_exception_ptr(
              std::logic_error("task executor outstanding count underflow")
            );
            work_ready_.notify_all();
            all_done_.notify_all();
            return;
          }
          --outstanding_;
          if (outstanding_ == 0) {
            all_done_.notify_all();
          }
        }
      }
    }
  }

  // Returns false when the poller failed and this worker should exit.
  auto run_poll() -> bool {
    if (!poll_) {
      return true;
    }
    try {
      poll_();
    } catch (...) {
      record_failure(std::current_exception());
      return false;
    }
    return true;
  }

  void join_threads() {
    if (joined_) {
      return;
    }
    for (auto & thread : threads_) {
      if (thread.joinable()) {
        thread.join();
      }
    }
    joined_ = true;
  }

 public:
  TslTaskExecutor(std::size_t worker_count, Worker worker)
      : worker_(std::move(worker)) {
    if (worker_count == 0) {
      throw std::invalid_argument("task executor requires at least one worker");
    }
    threads_.reserve(worker_count);
    try {
      for (std::size_t worker_index = 0; worker_index < worker_count; ++worker_index) {
        threads_.emplace_back([this] { worker_loop(); });
      }
    } catch (...) {
      {
        std::lock_guard<std::mutex> lock(mutex_);
        shutdown_ = true;
      }
      work_ready_.notify_all();
      join_threads();
      throw;
    }
  }

  TslTaskExecutor(TslTaskExecutor const &) = delete;
  auto operator=(TslTaskExecutor const &) -> TslTaskExecutor & = delete;

  ~TslTaskExecutor() {
    {
      std::lock_guard<std::mutex> lock(mutex_);
      shutdown_ = true;
      queue_.clear();
      outstanding_ = 0;
      pending_external_ = 0;
    }
    work_ready_.notify_all();
    all_done_.notify_all();
    join_threads();
  }

  void submit(Task task) {
    {
      std::lock_guard<std::mutex> lock(mutex_);
      if (failed_) {
        throw std::runtime_error("cannot submit work after task failure");
      }
      if (shutdown_) {
        throw std::runtime_error("cannot submit work after task executor shutdown");
      }
      queue_.push_back(std::move(task));
      ++outstanding_;
      ++metrics_.tasks_submitted;
      metrics_.max_outstanding_tasks = std::max(
        metrics_.max_outstanding_tasks,
        outstanding_
      );
    }
    work_ready_.notify_one();
  }

  void run_inline(Task const & task) {
    {
      std::lock_guard<std::mutex> lock(mutex_);
      if (failed_ || shutdown_) {
        throw std::runtime_error("cannot run inline work after task executor shutdown");
      }
      ++metrics_.tasks_executed_inline;
    }
    worker_(task, *this);
  }

  void wait() {
    std::exception_ptr error;
    {
      std::unique_lock<std::mutex> lock(mutex_);
      all_done_.wait(lock, [&] {
        return failed_ || outstanding_ == 0;
      });
      error = error_;
      shutdown_ = true;
    }
    work_ready_.notify_all();
    join_threads();
    if (error != nullptr) {
      std::rethrow_exception(error);
    }
  }

  // Set before the first submit(). Invoked on worker threads at task boundaries
  // and on idle deadlines; never while holding the executor mutex.
  void set_poller(std::function<void()> poll) {
    std::lock_guard<std::mutex> lock(mutex_);
    poll_ = std::move(poll);
  }

  void set_poll_interval(std::chrono::microseconds interval) {
    std::lock_guard<std::mutex> lock(mutex_);
    poll_interval_ = interval;
  }

  void add_pending(std::size_t count) override {
    {
      std::lock_guard<std::mutex> lock(mutex_);
      if (failed_ || shutdown_) {
        throw std::runtime_error("cannot register pending work after shutdown");
      }
      outstanding_ += count;
      pending_external_ += count;
      metrics_.max_outstanding_tasks =
        std::max(metrics_.max_outstanding_tasks, outstanding_);
    }
  }

  void resolve_pending(std::size_t count) override {
    {
      std::lock_guard<std::mutex> lock(mutex_);
      if (failed_) {
        return;
      }
      if (count > outstanding_ || count > pending_external_) {
        failed_ = true;
        error_ = std::make_exception_ptr(
          std::logic_error("task executor pending count underflow")
        );
        queue_.clear();
        outstanding_ = 0;
        pending_external_ = 0;
        work_ready_.notify_all();
        all_done_.notify_all();
        return;
      }
      outstanding_ -= count;
      pending_external_ -= count;
      if (outstanding_ != 0) {
        return;
      }
    }
    all_done_.notify_all();
  }

  void fail(std::exception_ptr error) override {
    record_failure(std::move(error));
  }

  auto queued() -> std::size_t {
    std::lock_guard<std::mutex> lock(mutex_);
    return queue_.size();
  }

  auto metrics() const -> TslTaskExecutorMetrics {
    return metrics_;
  }
};
