// Section 9.2: does the concurrent write-stream cliff move with thread count?
//
// -----------------------------------------------------------------------------
// The question
// -----------------------------------------------------------------------------
// K=16 was fixed by a single-core measurement: distribution keeps one open write
// stream per bucket per column, the `key+index` minus `key-only` penalty is flat
// to 64 streams and shows a 3.3-3.9x cliff at 128, so `2K <= 64` and K=16 leaves
// headroom. That was one core. With T threads the shared levels see `2*T*K`
// streams -- 768 at T=24, K=16 -- against one LLC and one set of memory
// controllers, so the binding constraint may move from per-core buffers (L1
// write-combine, DTLB, store buffer) to LLC associativity or DRAM bank
// conflicts, and the optimal K with it. The direction is genuinely unknown:
// contention argues for a smaller K, fewer passes over shared memory for a
// larger one.
//
// -----------------------------------------------------------------------------
// What is measured
// -----------------------------------------------------------------------------
// Part A is the experiment as specified: T threads each distributing their own
// disjoint input chunk into their own disjoint output region, with K buckets
// each, timed twice -- carrying the index column and not carrying it. The
// difference is the second column's cost, which is what the original cliff was
// measured on. Both variants are written here rather than one being the shipped
// kernel, so they differ in exactly one scatter.
//
// Part B asks the question that actually decides K: end to end, on threads, does
// a larger K pay?
//
//   ./bench_samplesort_streams
//   ./bench_samplesort_streams --n 33554432

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <numeric>
#include <random>
#include <thread>
#include <vector>

#include "sorting/sample_sort/samplesort_parallel_executor.hpp"

namespace {

using Clock = std::chrono::steady_clock;
constexpr int repetitions = 5;

auto median(std::vector<double> samples) -> double {
  std::sort(samples.begin(), samples.end());
  return samples[samples.size() / 2];
}

// One chunk's distribution, carrying the index column or not. Identical apart
// from the one extra scatter, so the difference is the second column.
template <class Vec, bool WithIndex>
void distribute(
  typename Vec::base_type * out_keys,
  typename Vec::base_type * out_idx,
  typename Vec::base_type const * keys,
  typename Vec::base_type const * idx,
  std::uint8_t const * ids,
  std::size_t begin,
  std::size_t end,
  typename Vec::base_type * cursors
) {
  using Base = typename Vec::base_type;
  constexpr std::size_t lanes = Vec::lane_count_v;
  auto const one = tsl::set1<Vec>(1);
  std::size_t i = begin;
  for (; i + lanes <= end; i += lanes) {
    auto const v = tsl::load<Vec>(keys + i);
    auto const id = tsl_samplesort_load_byte_ids<Vec>(ids + i);
    auto const rank = tsl::popcnt<Vec>(tsl::conflict<Vec>(id));
    auto const cursor = tsl::gather<Vec, Vec, sizeof(Base)>(cursors, id);
    auto const addr = tsl::add<Vec>(cursor, rank);
    tsl::scatter<Vec, Vec, sizeof(Base)>(out_keys, addr, v);
    if constexpr (WithIndex) {
      tsl::scatter<Vec, Vec, sizeof(Base)>(out_idx, addr, tsl::load<Vec>(idx + i));
    }
    tsl::scatter<Vec, Vec, sizeof(Base)>(cursors, id, tsl::add<Vec>(addr, one));
  }
  for (; i < end; ++i) {
    auto const bucket = static_cast<std::size_t>(ids[i]);
    auto const at = static_cast<std::size_t>(cursors[bucket]++);
    out_keys[at] = keys[i];
    if constexpr (WithIndex) {
      out_idx[at] = idx[i];
    }
  }
}

// Part A: T threads, K buckets each, disjoint in and out.
template <class Key, class Vec>
void stream_sweep(char const * type, std::size_t n) {
  using Base = typename Vec::base_type;
  std::printf("\n%s: distribution penalty for the second column\n", type);
  std::printf("%8s %6s %9s %11s %11s %11s %9s\n", "threads", "K", "streams",
              "key only", "key+index", "penalty", "per elem");

  std::vector<std::size_t> const thread_counts{1, 2, 4, 8, 16, 24};
  std::vector<std::size_t> const bucket_counts{8, 16, 32, 64};

  std::vector<Key> keys(n), out_keys(n), idx(n), out_idx(n);
  std::vector<std::uint8_t> ids(n);
  std::mt19937_64 rng(0x5712EA);
  for (std::size_t i = 0; i < n; ++i) {
    keys[i] = static_cast<Key>(rng());
    idx[i] = static_cast<Key>(i);
  }

  for (auto const threads : thread_counts) {
    for (auto const buckets : bucket_counts) {
      for (std::size_t i = 0; i < n; ++i) {
        ids[i] = static_cast<std::uint8_t>(rng() % buckets);
      }
      // Per-thread cursors, each addressing only its own output region.
      auto const span = n / threads;
      std::vector<std::vector<Base>> cursors(threads);
      for (std::size_t t = 0; t < threads; ++t) {
        std::vector<std::size_t> histogram(buckets, 0);
        for (std::size_t i = t * span; i < (t + 1) * span; ++i) {
          ++histogram[ids[i]];
        }
        cursors[t].assign(buckets, Base{0});
        Base running = static_cast<Base>(t * span);
        for (std::size_t b = 0; b < buckets; ++b) {
          cursors[t][b] = running;
          running += static_cast<Base>(histogram[b]);
        }
      }

      auto const run = [&](bool with_index) {
        std::vector<double> samples;
        for (int rep = 0; rep < repetitions; ++rep) {
          auto fresh = cursors;
          auto const start = Clock::now();
          std::vector<std::thread> pool;
          pool.reserve(threads - 1);
          auto const body = [&](std::size_t t) {
            if (with_index) {
              distribute<Vec, true>(out_keys.data(), out_idx.data(), keys.data(),
                                    idx.data(), ids.data(), t * span,
                                    (t + 1) * span, fresh[t].data());
            } else {
              distribute<Vec, false>(out_keys.data(), out_idx.data(), keys.data(),
                                     idx.data(), ids.data(), t * span,
                                     (t + 1) * span, fresh[t].data());
            }
          };
          for (std::size_t t = 1; t < threads; ++t) {
            pool.emplace_back(body, t);
          }
          body(0);
          for (auto & thread : pool) {
            thread.join();
          }
          auto const stop = Clock::now();
          samples.push_back(
            std::chrono::duration<double, std::nano>(stop - start).count()
            / static_cast<double>(span * threads));
        }
        return median(samples);
      };

      auto const key_only = run(false);
      auto const both = run(true);
      std::printf("%8zu %6zu %9zu %11.3f %11.3f %11.3f %9.3f\n", threads, buckets,
                  2 * threads * buckets, key_only, both, both - key_only,
                  (both - key_only));
    }
    std::printf("\n");
  }
  std::printf("Penalty is ns/element for carrying the index column. The\n"
              "single-core measurement that fixed K=16 was flat to 64 streams\n"
              "and showed a 3.3-3.9x jump at 128.\n");
}

// Part B: does a larger K pay end to end, on threads?
template <class Key, class Simd, int K>
void end_to_end(char const * type, std::size_t n, std::size_t workers) {
  using Idx = typename TslSampleSortTraits<Key>::index_type;
  auto const source = [&] {
    std::vector<Key> values(n);
    std::mt19937_64 rng(0x1234F00D);
    auto const span = static_cast<std::uint64_t>(std::numeric_limits<Key>::max() / 2);
    for (auto & value : values) {
      value = static_cast<Key>(rng() % (span + 1));
    }
    return values;
  }();

  std::vector<Key> keys(n), keys_scratch(n);
  std::vector<Idx> idx(n), idx_scratch(n);
  std::vector<double> samples;
  TslSampleSortMetrics metrics;
  for (int rep = 0; rep < repetitions; ++rep) {
    keys = source;
    std::iota(idx.begin(), idx.end(), Idx{0});
    auto const start = Clock::now();
    tsl_samplesort_cosort_parallel<Key, Simd, K>(
      keys.data(), idx.data(), n, keys_scratch.data(), idx_scratch.data(), workers,
      {}, &metrics);
    auto const stop = Clock::now();
    samples.push_back(std::chrono::duration<double, std::nano>(stop - start).count()
                      / static_cast<double>(n));
  }
  if (!std::is_sorted(keys.begin(), keys.end())) {
    std::printf("  !! not sorted\n");
  }
  std::printf("%6s %6d %8zu %9zu %11.3f   buckets<=%zu\n", type, K, workers,
              2 * workers * static_cast<std::size_t>(K), median(samples),
              metrics.max_buckets_used);
}

}  // namespace

int main(int argc, char ** argv) {
  std::size_t n = 1u << 24;
  for (int i = 1; i < argc; ++i) {
    if (std::strcmp(argv[i], "--n") == 0 && i + 1 < argc) {
      n = static_cast<std::size_t>(std::strtoull(argv[++i], nullptr, 10));
    } else {
      std::printf("unknown argument: %s\n", argv[i]);
      return 2;
    }
  }
  std::printf("n=%zu  repetitions=%d  medians\n", n, repetitions);

  stream_sweep<std::uint32_t, tsl::simd<std::uint32_t, tsl::avx512>>("u32", n);
  stream_sweep<std::uint64_t, tsl::simd<std::uint64_t, tsl::avx512>>("u64", n);

  std::printf("\nend to end, parallel: does a larger K pay?\n");
  std::printf("%6s %6s %8s %9s %11s\n", "type", "K", "workers", "streams", "ns/elem");
  for (std::size_t workers : {std::size_t{1}, std::size_t{8}, std::size_t{24}}) {
    end_to_end<std::uint32_t, tsl::simd<std::uint32_t, tsl::avx512>, 8>("u32", n, workers);
    end_to_end<std::uint32_t, tsl::simd<std::uint32_t, tsl::avx512>, 16>("u32", n, workers);
    end_to_end<std::uint32_t, tsl::simd<std::uint32_t, tsl::avx512>, 32>("u32", n, workers);
  }
  for (std::size_t workers : {std::size_t{1}, std::size_t{24}}) {
    end_to_end<std::uint64_t, tsl::simd<std::uint64_t, tsl::avx512>, 8>("u64", n, workers);
    end_to_end<std::uint64_t, tsl::simd<std::uint64_t, tsl::avx512>, 16>("u64", n, workers);
    end_to_end<std::uint64_t, tsl::simd<std::uint64_t, tsl::avx512>, 32>("u64", n, workers);
  }
  return 0;
}
