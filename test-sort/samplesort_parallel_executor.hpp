#pragma once

// The parallel executor for `samplesort_cosort.hpp`.
//
// This file exists to make one claim checkable: adding threads to this sorter is
// a scheduling change. It contains no kernel and no phase logic. It calls the
// same `tsl_samplesort_partition_step` the sequential executor calls, with the
// same chunk-scoped kernels underneath, and differs only in who runs the chunk
// bodies and who pops the task queue.
//
// -----------------------------------------------------------------------------
// Two stages, because the task tree starts with one task
// -----------------------------------------------------------------------------
// Level 0 is a single task covering the whole input, so task-level parallelism
// has nothing to work with until the tree fans out. Hence:
//
//   stage 1, descent      one task at a time, its phases 2 and 4 fanned across
//                         `workers` chunks, with the phase-3 reduction between
//                         them on the calling thread. Runs until the queue holds
//                         at least `workers` independent tasks -- two levels at
//                         K=16 -- so it forks a few dozen times, not per step.
//
//   stage 2, task parallel  every worker pops whole tasks and runs them with one
//                         chunk each. Ranges are disjoint, so the workers share
//                         `bucket_ids` and touch nothing else in common.
//
// Stage 1 is what the chunked kernels were built for; stage 2 is what the
// explicit task list was built for. Neither needed a kernel change, and the
// chunk-invariance test in `test_samplesort_cosort.cpp` is what makes stage 1
// trustworthy: it already proves the phase-3 write positions are right for chunk
// counts that do not divide the range.

#include <algorithm>
#include <atomic>
#include <condition_variable>
#include <cstddef>
#include <mutex>
#include <stdexcept>
#include <thread>
#include <vector>

#include "samplesort_cosort.hpp"


// Fans the chunk bodies of one phase across threads and joins. Stage 1 runs a
// couple of dozen of these over a whole sort, so a fresh set of threads per phase
// costs less than the pool it would take to avoid them.
class TslSampleSortForkedChunks {
  std::size_t workers_;

 public:
  explicit TslSampleSortForkedChunks(std::size_t workers) : workers_(workers) {}

  template <class Body>
  void operator()(std::size_t chunks, Body && body) const {
    if (chunks <= 1 || workers_ <= 1) {
      for (std::size_t c = 0; c < chunks; ++c) {
        body(c);
      }
      return;
    }
    std::vector<std::thread> threads;
    threads.reserve(chunks - 1);
    for (std::size_t c = 1; c < chunks; ++c) {
      threads.emplace_back([&body, c] { body(c); });
    }
    body(0);  // the calling thread takes one, so `chunks` threads do `chunks` work
    for (auto & thread : threads) {
      thread.join();
    }
  }
};


// Same contract as `tsl_samplesort_cosort`: sorts `keys[0..n)` ascending, applies
// the permutation to `idx`, leaves the answer in the caller's pair, not stable.
// `workers == 0` asks the hardware.
template <
  class Key,
  class SimdStyle,
  int K = 16,
  TslSampleSortBuckets Policy = TslSampleSortBuckets::Adaptive,
  int Oversample = 8,
  std::size_t BaseCase = 256,
  TslSampleSortBase BasePolicy = TslSampleSortBase::Network,
  TslSampleSortIds IdWidth = TslSampleSortIds::Byte,
  std::size_t BaseRows = BaseCase / SimdStyle::lane_count_v,
  std::size_t BaseFillPercent = 50
>
void tsl_samplesort_cosort_parallel(
  Key * keys,
  typename TslSampleSortTraits<Key>::index_type * idx,
  std::size_t n,
  Key * keys_scratch,
  typename TslSampleSortTraits<Key>::index_type * idx_scratch,
  std::size_t workers = 0,
  TslSampleSortOptions const & options = {},
  TslSampleSortMetrics * metrics_out = nullptr
) {
  using Kernels = TslSampleSortKernels<Key, SimdStyle, K, Policy, Oversample,
                                       BaseCase, BasePolicy, IdWidth, BaseRows,
                                       BaseFillPercent>;
  using Idx = typename Kernels::index_type;

  if (workers == 0) {
    workers = std::max<std::size_t>(1, std::thread::hardware_concurrency());
  }
  TslSampleSortMetrics metrics;
  if (n <= 1 || workers == 1) {
    tsl_samplesort_cosort<Key, SimdStyle, K, Policy, Oversample, BaseCase,
                          BasePolicy, IdWidth, BaseRows, BaseFillPercent>(
      keys, idx, n, keys_scratch, idx_scratch, options, metrics_out);
    return;
  }
  if (keys == nullptr || idx == nullptr || keys_scratch == nullptr
      || idx_scratch == nullptr) {
    throw std::invalid_argument("samplesort needs both buffer pairs");
  }

  int levels = 1;
  for (std::size_t reach = Kernels::base_case; reach < n; reach *= K) {
    ++levels;
  }
  auto const max_depth = 2 * levels + 8;

  // Ranges are disjoint, so one bucket-id array serves every worker; only the
  // per-step reduction arrays are private.
  std::vector<typename Kernels::bucket_id_type> shared_ids(
    n, typename Kernels::bucket_id_type{0});

  auto const terminate = [&](TslSampleSortTask const & task,
                             TslSampleSortMetrics & into) {
    Key * const task_keys = task.in_scratch ? keys_scratch : keys;
    Idx * const task_idx = task.in_scratch ? idx_scratch : idx;
    if (!task.sorted) {
      ++into.base_case_ranges;
      into.base_case_elements += task.count;
      if (task.depth > max_depth) {
        ++into.heapsort_ranges;
        Kernels::heapsort_pairs(task_keys, task_idx, task.begin,
                                task.begin + task.count);
      } else {
        Kernels::base_sort_pairs(task_keys, task_idx, task.begin,
                                 task.begin + task.count);
      }
    }
    if (task.in_scratch) {
      std::copy_n(keys_scratch + task.begin, task.count, keys + task.begin);
      std::copy_n(idx_scratch + task.begin, task.count, idx + task.begin);
      into.copied_back_elements += task.count;
    }
  };
  auto const is_terminal = [&](TslSampleSortTask const & task) {
    return task.sorted || task.count <= Kernels::base_case || task.depth > max_depth;
  };

  std::vector<TslSampleSortTask> queue;
  std::vector<TslSampleSortTask> emitted;
  queue.push_back(TslSampleSortTask{0, n, 0, false, false});

  // ---- stage 1: descend, splitting each step's chunks across workers ----
  {
    TslSampleSortWorkspace<Kernels> workspace;
    workspace.attach(shared_ids.data(), workers);
    TslPivotRng rng(options.seed);
    TslSampleSortForkedChunks forked(workers);
    TslSampleSortOptions chunked = options;
    chunked.chunks = workers;

    while (queue.size() < workers) {
      auto const largest = std::max_element(
        queue.begin(), queue.end(),
        [](TslSampleSortTask const & a, TslSampleSortTask const & b) {
          return a.count < b.count;
        });
      if (largest == queue.end()) {
        break;
      }
      auto const task = *largest;
      queue.erase(largest);
      ++metrics.tasks;
      // Nothing left worth fanning out: hand the rest to stage 2.
      if (is_terminal(task) || task.count < workers * Kernels::lanes * 4) {
        if (is_terminal(task)) {
          terminate(task, metrics);
        } else {
          queue.push_back(task);
        }
        if (!is_terminal(task)) {
          break;
        }
        continue;
      }
      emitted.clear();
      tsl_samplesort_partition_step<Kernels, false, TslSampleSortForkedChunks>(
        task, keys, idx, keys_scratch, idx_scratch, workspace, chunked, rng,
        metrics, emitted, forked);
      queue.insert(queue.end(), emitted.begin(), emitted.end());
    }
  }

  // ---- stage 2: workers pop whole tasks ----
  //
  // Each worker keeps its own LIFO stack and only publishes a task to the shared
  // queue when it is large enough to be worth another worker's attention. That
  // matters more than it sounds: a run produces about 440k tasks, almost all of
  // them base-case ranges, and routing every one of them through a mutex plus a
  // notify was measured to cap the whole sort at 1.04x on 24 threads. Publishing
  // only the tasks that will fan out again cuts shared-queue traffic by orders of
  // magnitude and leaves the small work where it was produced, which is also
  // where its data is warm.
  auto const share_threshold = Kernels::base_case * static_cast<std::size_t>(K);

  std::mutex mutex;
  std::condition_variable cv;
  std::vector<TslSampleSortTask> shared;
  std::size_t idle = 0;
  // A latch rather than re-testing `idle == workers`: the worker that observes
  // the all-idle condition has to decrement `idle` on its way out, which would
  // falsify that condition for everyone still waiting on it.
  bool finished = false;
  std::vector<TslSampleSortMetrics> per_worker(workers);

  {
    std::lock_guard<std::mutex> lock(mutex);
    shared.swap(queue);
  }

  auto const worker = [&](std::size_t id) {
    TslSampleSortWorkspace<Kernels> workspace;
    workspace.attach(shared_ids.data(), 1);  // shared; every range is disjoint
    TslPivotRng rng(options.seed ^ (0x9E3779B97F4A7C15ull * (id + 1)));
    auto & mine = per_worker[id];
    std::vector<TslSampleSortTask> local;
    std::vector<TslSampleSortTask> produced;

    while (true) {
      TslSampleSortTask task{};
      if (!local.empty()) {
        task = local.back();
        local.pop_back();
      } else {
        std::unique_lock<std::mutex> lock(mutex);
        ++idle;
        if (idle == workers && shared.empty()) {
          finished = true;  // every worker is out of local work and nothing queued
          cv.notify_all();
        }
        cv.wait(lock, [&] { return !shared.empty() || finished; });
        if (finished) {
          return;
        }
        task = shared.back();
        shared.pop_back();
        --idle;
      }

      ++mine.tasks;
      mine.max_depth = std::max(mine.max_depth, static_cast<std::size_t>(task.depth));
      if (is_terminal(task)) {
        terminate(task, mine);
        continue;
      }

      produced.clear();
      tsl_samplesort_partition_step<Kernels>(task, keys, idx, keys_scratch,
                                             idx_scratch, workspace, options, rng,
                                             mine, produced);
      std::sort(produced.begin(), produced.end(),
                [](TslSampleSortTask const & a, TslSampleSortTask const & b) {
                  return a.count > b.count;
                });
      std::size_t published = 0;
      for (auto const & subtask : produced) {
        if (subtask.count >= share_threshold) {
          ++published;
        } else {
          local.push_back(subtask);
        }
      }
      if (published != 0) {
        {
          std::lock_guard<std::mutex> lock(mutex);
          for (auto const & subtask : produced) {
            if (subtask.count >= share_threshold) {
              shared.push_back(subtask);
            }
          }
        }
        cv.notify_all();
      }
    }
  };

  std::vector<std::thread> pool;
  pool.reserve(workers - 1);
  for (std::size_t id = 1; id < workers; ++id) {
    pool.emplace_back(worker, id);
  }
  worker(0);
  for (auto & thread : pool) {
    thread.join();
  }

  for (auto const & mine : per_worker) {
    metrics.tasks += mine.tasks;
    metrics.partition_steps += mine.partition_steps;
    metrics.classified_elements += mine.classified_elements;
    metrics.distributed_elements += mine.distributed_elements;
    metrics.base_case_ranges += mine.base_case_ranges;
    metrics.base_case_elements += mine.base_case_elements;
    metrics.equality_buckets += mine.equality_buckets;
    metrics.equality_elements += mine.equality_elements;
    metrics.degenerate_steps += mine.degenerate_steps;
    metrics.heapsort_ranges += mine.heapsort_ranges;
    metrics.copied_back_elements += mine.copied_back_elements;
    metrics.equality_buckets_allocated += mine.equality_buckets_allocated;
    metrics.max_depth = std::max(metrics.max_depth, mine.max_depth);
    metrics.max_buckets_used = std::max(metrics.max_buckets_used, mine.max_buckets_used);
  }
  if (metrics_out != nullptr) {
    *metrics_out = metrics;
  }
}
