// Benchmark for the TSL samplesort co-sort.
//
// Reports ns/element, never speedup ratios, because the interesting comparisons
// here are against a per-stage budget rather than against each other.
//
// Four questions, in the order they matter:
//
//  1. Do the two kernels meet their per-pass budgets in isolation?
//  2. What does K cost? The specification's K=16 is the argmin of a cost model
//     measured on different hardware with hand-written intrinsics; on any other
//     machine it is a hypothesis. K is a compile-time parameter of the kernels
//     so re-checking it costs one instantiation.
//  3. What does `WithEquality` cost? It is the policy that makes duplicate-heavy
//     input terminate by construction, and it pays for that with a second
//     comparison sweep per splitter. That trade is the main open question the
//     specification leaves.
//  4. What does the chunked structure cost when there is only one chunk to run?
//     That is the fixed tax a parallel executor pays before it gains anything.
//
//   ./bench_samplesort_cosort                 # the default sweep
//   ./bench_samplesort_cosort --n 16777216
//   ./bench_samplesort_cosort --csv out.csv

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <numeric>
#include <random>
#include <string>
#include <vector>

#include "multicolumn_quicksort.hpp"
#include "samplesort_executor.hpp"

namespace {

using Clock = std::chrono::steady_clock;
constexpr int repetitions = 5;

auto median(std::vector<double> samples) -> double {
  std::sort(samples.begin(), samples.end());
  return samples[samples.size() / 2];
}

template <class Key>
auto random_keys(std::size_t n, std::uint64_t seed) -> std::vector<Key> {
  std::vector<Key> keys(n);
  std::mt19937_64 rng(seed);
  auto const span = static_cast<std::uint64_t>(std::numeric_limits<Key>::max() / 2);
  for (auto & key : keys) {
    key = static_cast<Key>(rng() % (span + 1));
  }
  return keys;
}

struct row {
  std::string what;
  std::string type;
  int k;
  std::string policy;
  std::size_t chunks;
  std::size_t n;
  double ns_per_element;
};

std::vector<row> g_rows;

void report(std::string const & what, std::string const & type, int k,
            std::string const & policy, std::size_t chunks, std::size_t n,
            double ns_per_element, char const * note = "") {
  std::printf("%-34s %-5s %4d %-9s %7zu %12.3f  %s\n", what.c_str(), type.c_str(),
              k, policy.c_str(), chunks, ns_per_element, note);
  g_rows.push_back(row{what, type, k, policy, chunks, n, ns_per_element});
}

auto policy_name(TslSampleSortBuckets policy) -> char const * {
  return policy == TslSampleSortBuckets::Adaptive ? "equality" : "ordered";
}

// ---------------------------------------------------------------------------
// Per-stage: one classification pass and one distribution pass over the whole
// array, which is what a single level of the recursion costs.
// ---------------------------------------------------------------------------
template <class Key, class Simd, int K, TslSampleSortBuckets Policy>
void stage_breakdown(char const * type, std::size_t n) {
  using Kernels = TslSampleSortKernels<Key, Simd, K, Policy>;
  using Idx = typename Kernels::index_type;

  auto const keys = random_keys<Key>(n, 0x51A6E);
  std::vector<Idx> idx(n);
  std::iota(idx.begin(), idx.end(), Idx{0});
  std::vector<Key> out_keys(n);
  std::vector<Idx> out_idx(n);
  std::vector<typename Kernels::bucket_id_type> ids(
    n, typename Kernels::bucket_id_type{0});

  TslPivotRng rng(0xA11CE);
  auto const splitters = Kernels::select_splitters(keys.data(), 0, n, rng);
  auto const buckets = static_cast<std::size_t>(splitters.buckets);

  std::vector<double> classify_samples;
  std::vector<std::size_t> histogram(buckets, 0);
  for (int rep = 0; rep < repetitions; ++rep) {
    std::fill(histogram.begin(), histogram.end(), 0);
    auto const start = Clock::now();
    Kernels::classify_chunk(ids.data(), keys.data(), 0, n, splitters, histogram.data());
    auto const stop = Clock::now();
    classify_samples.push_back(
      std::chrono::duration<double, std::nano>(stop - start).count()
      / static_cast<double>(n));
  }
  auto const classify_ns = median(classify_samples);
  report("classify (one pass)", type, K, policy_name(Policy), 1, n, classify_ns,
         classify_ns <= 0.40 ? "<= 0.40 target" : "OVER the 0.40 target");

  // Distribution needs the cursors the reduction would have produced.
  std::vector<Idx> cursors(buckets, Idx{0});
  std::vector<double> distribute_samples;
  for (int rep = 0; rep < repetitions; ++rep) {
    Idx running = 0;
    for (std::size_t b = 0; b < buckets; ++b) {
      cursors[b] = running;
      running += static_cast<Idx>(histogram[b]);
    }
    auto const start = Clock::now();
    Kernels::distribute_chunk(out_keys.data(), out_idx.data(), keys.data(),
                              idx.data(), ids.data(), 0, n, cursors.data());
    auto const stop = Clock::now();
    distribute_samples.push_back(
      std::chrono::duration<double, std::nano>(stop - start).count()
      / static_cast<double>(n));
  }
  auto const distribute_ns = median(distribute_samples);
  report("distribute key+index (one pass)", type, K, policy_name(Policy), 1, n,
         distribute_ns,
         distribute_ns <= 1.30 ? "<= 1.30 target"
                               : (distribute_ns > 1.60 ? "check stream count first"
                                                       : "OVER the 1.30 target"));
  report("combined (one pass)", type, K, policy_name(Policy), 1, n,
         classify_ns + distribute_ns,
         classify_ns + distribute_ns <= 1.70 ? "<= 1.70 target" : "OVER the 1.70 target");
}

// ---------------------------------------------------------------------------
// End to end.
// ---------------------------------------------------------------------------
template <class Key, class Simd, int K, TslSampleSortBuckets Policy,
          int Oversample = 8, std::size_t BaseCase = 256,
          TslSampleSortBase BasePolicy = TslSampleSortBase::Insertion>
auto end_to_end(char const * type, std::size_t n, std::size_t chunks) -> double {
  using Idx = typename TslSampleSortTraits<Key>::index_type;
  auto const source = random_keys<Key>(n, 0x1234F00D);

  std::vector<Key> keys(n);
  std::vector<Idx> idx(n);
  std::vector<Key> keys_scratch(n);
  std::vector<Idx> idx_scratch(n);

  TslSampleSortOptions options;
  options.chunks = chunks;

  std::vector<double> samples;
  TslSampleSortMetrics metrics;
  for (int rep = 0; rep < repetitions; ++rep) {
    keys = source;
    std::iota(idx.begin(), idx.end(), Idx{0});
    auto const start = Clock::now();
    tsl_samplesort_cosort<Key, Simd, K, Policy, Oversample, BaseCase, BasePolicy>(
      keys.data(), idx.data(), n, keys_scratch.data(), idx_scratch.data(),
      options, &metrics);
    auto const stop = Clock::now();
    samples.push_back(std::chrono::duration<double, std::nano>(stop - start).count()
                      / static_cast<double>(n));
  }
  if (!std::is_sorted(keys.begin(), keys.end())) {
    std::printf("  !! result is not sorted -- timing is meaningless\n");
  }
  auto const ns = median(samples);
  char note[128];
  std::snprintf(note, sizeof(note),
                "%s base=%zu passes=%.2f baseel=%.2f copyback=%.2f buckets<=%zu eqb=%zu",
                BasePolicy == TslSampleSortBase::Network ? "net" : "ins", BaseCase,
                static_cast<double>(metrics.classified_elements) / static_cast<double>(n),
                static_cast<double>(metrics.base_case_elements) / static_cast<double>(n),
                static_cast<double>(metrics.copied_back_elements) / static_cast<double>(n),
                metrics.max_buckets_used, metrics.equality_buckets_allocated);
  report("end to end", type, K, policy_name(Policy), chunks, n, ns, note);
  return ns;
}

// std::sort over (key, index) pairs is the reference a co-sort has to beat.
template <class Key>
void baselines(char const * type, std::size_t n) {
  using Idx = typename TslSampleSortTraits<Key>::index_type;
  struct pair { Key key; Idx idx; };
  auto const source = random_keys<Key>(n, 0x1234F00D);

  std::vector<pair> pairs(n);
  std::vector<double> sort_samples;
  std::vector<double> stable_samples;
  for (int rep = 0; rep < repetitions; ++rep) {
    for (std::size_t i = 0; i < n; ++i) {
      pairs[i] = pair{source[i], static_cast<Idx>(i)};
    }
    auto start = Clock::now();
    std::sort(pairs.begin(), pairs.end(),
              [](pair const & a, pair const & b) { return a.key < b.key; });
    auto stop = Clock::now();
    sort_samples.push_back(std::chrono::duration<double, std::nano>(stop - start).count()
                           / static_cast<double>(n));

    for (std::size_t i = 0; i < n; ++i) {
      pairs[i] = pair{source[i], static_cast<Idx>(i)};
    }
    start = Clock::now();
    std::stable_sort(pairs.begin(), pairs.end(),
                     [](pair const & a, pair const & b) { return a.key < b.key; });
    stop = Clock::now();
    stable_samples.push_back(
      std::chrono::duration<double, std::nano>(stop - start).count()
      / static_cast<double>(n));
  }
  report("std::sort over pairs", type, 0, "-", 1, n, median(sort_samples));
  report("std::stable_sort over pairs", type, 0, "-", 1, n, median(stable_samples));
}

// The playground's existing sorter on exactly the same problem: one key column
// with the index as its single replayed payload. This is the head-to-head that
// decides whether samplesort is worth carrying -- same machine, same n, same
// data model, same result.
template <class Key, class Simd, TslLeafKind Leaf>
void quicksort_baseline(char const * type, char const * leaf, std::size_t n) {
  using Idx = typename TslSampleSortTraits<Key>::index_type;
  using Sorter = TslMultiColumnQuickSorter<Key, TslPartitionKind::THREE_WAY, Leaf, 1, Simd>;
  static_assert(sizeof(Key) == sizeof(Idx), "the index is the key's width");

  auto const source = random_keys<Key>(n, 0x1234F00D);
  std::vector<Key> keys(n);
  std::vector<Key> index(n);  // the sorter replays payloads of the key's type
  Sorter sorter(0x5A3F1E77);

  std::vector<double> samples;
  for (int rep = 0; rep < repetitions; ++rep) {
    keys = source;
    for (std::size_t i = 0; i < n; ++i) {
      index[i] = static_cast<Key>(i);
    }
    Key * columns[1] = {index.data()};
    auto const start = Clock::now();
    sorter.sort_key(keys.data(), columns, 1, n, TslSortOrder::ASCENDING);
    auto const stop = Clock::now();
    samples.push_back(std::chrono::duration<double, std::nano>(stop - start).count()
                      / static_cast<double>(n));
  }
  if (!std::is_sorted(keys.begin(), keys.end())) {
    std::printf("  !! quicksort baseline did not sort\n");
  }
  report(std::string("quicksort sort_key + index (") + leaf + ")", type, 0, "-", 1, n,
         median(samples));
}

}  // namespace

int main(int argc, char ** argv) {
  std::size_t n = 1u << 24;
  std::string csv_path;
  for (int i = 1; i < argc; ++i) {
    if (std::strcmp(argv[i], "--n") == 0 && i + 1 < argc) {
      n = static_cast<std::size_t>(std::strtoull(argv[++i], nullptr, 10));
    } else if (std::strcmp(argv[i], "--csv") == 0 && i + 1 < argc) {
      csv_path = argv[++i];
    } else {
      std::printf("unknown argument: %s\n", argv[i]);
      return 2;
    }
  }

  using U32 = std::uint32_t;
  using U64 = std::uint64_t;
  using Simd32 = tsl::simd<U32, tsl::avx512>;
  using Simd64 = tsl::simd<U64, tsl::avx512>;
  constexpr auto equality = TslSampleSortBuckets::Adaptive;
  constexpr auto ordered = TslSampleSortBuckets::Ordered;

  std::printf("n=%zu  repetitions=%d  medians, ns per element\n\n", n, repetitions);
  std::printf("%-34s %-5s %4s %-9s %7s %12s  %s\n",
              "what", "type", "K", "policy", "chunks", "ns/element", "note");

  std::printf("\n-- per stage, one pass over the whole array --\n");
  stage_breakdown<U32, Simd32, 16, equality>("u32", n);
  stage_breakdown<U32, Simd32, 16, ordered>("u32", n);
  stage_breakdown<U64, Simd64, 16, equality>("u64", n);
  stage_breakdown<U64, Simd64, 16, ordered>("u64", n);

  std::printf("\n-- K sweep, end to end --\n");
  end_to_end<U32, Simd32, 8, equality>("u32", n, 1);
  end_to_end<U32, Simd32, 16, equality>("u32", n, 1);
  end_to_end<U32, Simd32, 8, ordered>("u32", n, 1);
  end_to_end<U32, Simd32, 16, ordered>("u32", n, 1);
  end_to_end<U32, Simd32, 32, ordered>("u32", n, 1);
  end_to_end<U64, Simd64, 16, equality>("u64", n, 1);
  end_to_end<U64, Simd64, 16, ordered>("u64", n, 1);
  end_to_end<U64, Simd64, 32, ordered>("u64", n, 1);

  // K=32 under the equality policy would be 63 buckets and 126 write streams,
  // which the kernels reject at compile time: the measured stream cliff is at
  // 128. That rejection is the point -- see samplesort-notes.md.

  // BASE_CASE is a compile-time parameter, so re-deriving it is one
  // instantiation per point. The specification's 256 is a scalar insertion sort
  // over 256 elements, which is quadratic in exactly the place the recursion
  // spends most of its elements.
  std::printf("\n-- base-case sweep, end to end --\n");
  end_to_end<U32, Simd32, 16, equality, 8, 16>("u32", n, 1);
  end_to_end<U32, Simd32, 16, equality, 8, 32>("u32", n, 1);
  end_to_end<U32, Simd32, 16, equality, 8, 64>("u32", n, 1);
  end_to_end<U32, Simd32, 16, equality, 8, 128>("u32", n, 1);
  end_to_end<U32, Simd32, 16, equality, 8, 256>("u32", n, 1);

  // The same sweep against the playground's branch-free leaf. Its cost does not
  // depend on how full the range is, which is the property that matters when
  // most ranges arrive at the base case rather than through it.
  constexpr auto network_base = TslSampleSortBase::Network;
  std::printf("\n-- base-case sweep with the bitonic network leaf --\n");
  end_to_end<U32, Simd32, 16, equality, 8, 64, network_base>("u32", n, 1);
  end_to_end<U32, Simd32, 16, equality, 8, 128, network_base>("u32", n, 1);
  end_to_end<U32, Simd32, 16, equality, 8, 256, network_base>("u32", n, 1);
  end_to_end<U64, Simd64, 16, equality, 8, 128, network_base>("u64", n, 1);

  std::printf("\n-- chunk sweep, still one thread: the tax a parallel run prepays --\n");
  auto const one_chunk = end_to_end<U32, Simd32, 16, equality>("u32", n, 1);
  double widest = one_chunk;
  for (std::size_t chunks : {std::size_t{2}, std::size_t{4}, std::size_t{8},
                             std::size_t{16}}) {
    widest = end_to_end<U32, Simd32, 16, equality>("u32", n, chunks);
  }
  std::printf("  chunked bookkeeping, 1 -> 16 chunks: %+.1f%% %s\n",
              100.0 * (widest - one_chunk) / one_chunk,
              (widest - one_chunk) / one_chunk > 0.05
                ? "(over 5%: check the phase-3 loop order)" : "(within 5%)");

  std::printf("\n-- baselines --\n");
  quicksort_baseline<U32, Simd32, TslLeafKind::INSERTION>("u32", "ins", n);
  quicksort_baseline<U32, Simd32, TslLeafKind::NETWORK>("u32", "net", n);
  quicksort_baseline<U64, Simd64, TslLeafKind::INSERTION>("u64", "ins", n);
  quicksort_baseline<U64, Simd64, TslLeafKind::NETWORK>("u64", "net", n);
  baselines<U32>("u32", n);
  baselines<U64>("u64", n);

  if (!csv_path.empty()) {
    std::ofstream csv(csv_path);
    csv << "what,type,k,policy,chunks,n,ns_per_element\n";
    for (auto const & entry : g_rows) {
      csv << entry.what << ',' << entry.type << ',' << entry.k << ',' << entry.policy
          << ',' << entry.chunks << ',' << entry.n << ',' << entry.ns_per_element << '\n';
    }
    std::printf("wrote %s\n", csv_path.c_str());
  }
  return 0;
}
