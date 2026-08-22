#pragma once

// The sequential executor for `samplesort_cosort.hpp`, and the public entry
// points.
//
// This is the only file a parallel version replaces. It owns the task queue and
// the pop policy and nothing else: it never touches a kernel, and the kernels
// never learn how many tasks are in flight. If making this parallel required an
// edit to `classify_chunk` or `distribute_chunk`, the split would be wrong.
//
// Sequential policy is LIFO with the largest bucket pushed first, so the
// smallest is popped first and the queue stays shallow. A parallel executor is a
// different pop policy over the same queue.

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <chrono>
#include <vector>

#include "samplesort_cosort.hpp"


// Sorts `keys[0..n)` ascending and applies the same permutation to `idx`, which
// the caller must have filled with `0,1,...,n-1`. The scratch pair must hold `n`
// elements each; its contents are undefined afterwards. The result is always in
// `keys`/`idx`.
//
// Not stable.
template <
  class Key,
  class SimdStyle,
  int K = 16,
  TslSampleSortBuckets Policy = TslSampleSortBuckets::Adaptive,
  int Oversample = 8,
  std::size_t BaseCase = 256,
  TslSampleSortBase BasePolicy = TslSampleSortBase::Insertion,
  TslSampleSortIds IdWidth = TslSampleSortIds::Byte,
  bool Profile = false
>
void tsl_samplesort_cosort(
  Key * keys,
  typename TslSampleSortTraits<Key>::index_type * idx,
  std::size_t n,
  Key * keys_scratch,
  typename TslSampleSortTraits<Key>::index_type * idx_scratch,
  TslSampleSortOptions const & options = {},
  TslSampleSortMetrics * metrics_out = nullptr
) {
  using Kernels =
    TslSampleSortKernels<Key, SimdStyle, K, Policy, Oversample, BaseCase, BasePolicy,
                         IdWidth>;
  using Idx = typename Kernels::index_type;

  TslSampleSortMetrics metrics;
  if (n > 1) {
    if (keys == nullptr || idx == nullptr || keys_scratch == nullptr
        || idx_scratch == nullptr) {
      throw std::invalid_argument("samplesort needs both buffer pairs");
    }

    // 2 * ceil(log_K n) + 8: the safety net that turns a pathological recursion
    // into a slowdown rather than a hang.
    int levels = 1;
    for (std::size_t reach = Kernels::base_case; reach < n; reach *= K) {
      ++levels;
    }
    auto const max_depth = 2 * levels + 8;

    TslSampleSortWorkspace<Kernels> workspace;
    workspace.resize(n, std::max<std::size_t>(1, options.chunks));
    TslPivotRng rng(options.seed);

    std::vector<TslSampleSortTask> queue;
    std::vector<TslSampleSortTask> emitted;
    queue.push_back(TslSampleSortTask{0, n, 0, false, false});

    while (!queue.empty()) {
      auto const task = queue.back();
      queue.pop_back();
      ++metrics.tasks;
      metrics.max_depth = std::max(metrics.max_depth,
                                   static_cast<std::size_t>(task.depth));

      Key * const task_keys = task.in_scratch ? keys_scratch : keys;
      Idx * const task_idx = task.in_scratch ? idx_scratch : idx;

      auto const terminal = task.sorted || task.count <= Kernels::base_case
                            || task.depth > max_depth;
      if (terminal) {
        auto const t_base = std::chrono::steady_clock::now();
        if (!task.sorted) {
          ++metrics.base_case_ranges;
          metrics.base_case_elements += task.count;
          if (task.depth > max_depth) {
            ++metrics.heapsort_ranges;
            Kernels::heapsort_pairs(task_keys, task_idx, task.begin,
                                    task.begin + task.count);
          } else {
            Kernels::base_sort_pairs(task_keys, task_idx, task.begin,
                                     task.begin + task.count);
          }
        }
        if constexpr (Profile) {
          metrics.ns_base += std::chrono::duration<double, std::nano>(
            std::chrono::steady_clock::now() - t_base).count();
        }
        auto const t_copy = std::chrono::steady_clock::now();
        // The answer must end up in the caller's pair, so a range that finished
        // in the scratch pair is copied back as it terminates. Per range rather
        // than by pre-computing a global parity, because buckets reach different
        // depths and a parallel executor will finish them out of order.
        if (task.in_scratch) {
          std::copy_n(keys_scratch + task.begin, task.count, keys + task.begin);
          std::copy_n(idx_scratch + task.begin, task.count, idx + task.begin);
          metrics.copied_back_elements += task.count;
        }
        if constexpr (Profile) {
          metrics.ns_copyback += std::chrono::duration<double, std::nano>(
            std::chrono::steady_clock::now() - t_copy).count();
        }
        continue;
      }

      emitted.clear();
      tsl_samplesort_partition_step<Kernels, Profile>(task, keys, idx, keys_scratch,
                                             idx_scratch, workspace, options,
                                             rng, metrics, emitted);
      // Largest first, so the smallest is popped first and the queue stays
      // shallow. Buckets are disjoint, so the order does not affect the result.
      std::sort(emitted.begin(), emitted.end(),
                [](TslSampleSortTask const & a, TslSampleSortTask const & b) {
                  return a.count > b.count;
                });
      queue.insert(queue.end(), emitted.begin(), emitted.end());
    }
  }

  if (metrics_out != nullptr) {
    *metrics_out = metrics;
  }
}


// Materialises one further column through the permutation the sort left in
// `idx`: `out[i] = column[idx[i]]`.
template <class Column, class Idx>
void tsl_apply_permutation(Column * out, Column const * column, Idx const * idx,
                           std::size_t n) {
  for (std::size_t i = 0; i < n; ++i) {
    out[i] = column[idx[i]];
  }
}
