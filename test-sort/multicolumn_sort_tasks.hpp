#pragma once

#include <algorithm>
#include <condition_variable>
#include <cstddef>
#include <deque>
#include <exception>
#include <mutex>
#include <stdexcept>
#include <thread>
#include <utility>
#include <vector>


struct TslTaskExecutorMetrics {
  std::size_t tasks_submitted = 0;
  std::size_t tasks_executed_inline = 0;
  std::size_t max_outstanding_tasks = 0;
};

template <class Task, class Worker>
class TslTaskExecutor {
  Worker worker_;
  std::deque<Task> queue_;
  std::vector<std::thread> threads_;
  std::mutex mutex_;
  std::condition_variable work_ready_;
  std::condition_variable all_done_;
  std::exception_ptr error_;
  std::size_t outstanding_ = 0;
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
      }
    }
    work_ready_.notify_all();
    all_done_.notify_all();
  }

  void worker_loop() {
    while (true) {
      Task task;
      {
        std::unique_lock<std::mutex> lock(mutex_);
        work_ready_.wait(lock, [&] {
          return shutdown_ || failed_ || !queue_.empty();
        });
        if (failed_ || (shutdown_ && queue_.empty())) {
          return;
        }
        task = std::move(queue_.front());
        queue_.pop_front();
      }

      try {
        worker_(task, *this);
      } catch (...) {
        record_failure(std::current_exception());
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

  auto metrics() const -> TslTaskExecutorMetrics {
    return metrics_;
  }
};
