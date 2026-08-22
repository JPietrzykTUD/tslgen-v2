// Correctness tests for the TSL samplesort co-sort.
//
// The properties checked per case are the ones the design exists for: the keys
// come out ordered, `idx` is a genuine permutation, and `keys[i]` is the key
// that lived at `idx[i]` before the sort -- the last is what makes materialising
// the remaining columns with one gather pass valid.
//
// Two cases carry more weight than the rest:
//
// * All-equal and two-distinct keys, which are what break a naive samplesort:
//   sampling returns no distinct splitter and the recursion never shrinks.
// * Chunk invariance. The whole sort is run with the chunk count forced to 1, 2,
//   3 and 7 -- still one thread -- and the outputs must be byte-identical. That
//   is the test that proves parallelism is additive: if a kernel carried state
//   across chunks, this fails here rather than after threads are added. The
//   chunk counts deliberately do not divide the sizes evenly.

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <numeric>
#include <random>
#include <string>
#include <vector>

#include "samplesort_executor.hpp"

namespace {

std::size_t g_checks = 0;
std::size_t g_failures = 0;

void fail(std::string const & label, std::string const & why) {
  ++g_failures;
  std::printf("FAIL %-56s %s\n", label.c_str(), why.c_str());
}

// The nine documented distributions, plus the two that break naive samplesort.
enum class Shape {
  Random, Sorted, Reverse, AllEqual, TwoValues, ModThree, Skewed, OrganPipe, Sawtooth
};

auto shape_name(Shape shape) -> char const * {
  switch (shape) {
    case Shape::Random: return "random";
    case Shape::Sorted: return "sorted";
    case Shape::Reverse: return "reverse";
    case Shape::AllEqual: return "all-equal";
    case Shape::TwoValues: return "two-values";
    case Shape::ModThree: return "i%3";
    case Shape::Skewed: return "skewed-90";
    case Shape::OrganPipe: return "organ-pipe";
    case Shape::Sawtooth: return "sawtooth";
  }
  return "?";
}

template <class Key>
auto make_keys(Shape shape, std::size_t n, std::uint64_t seed) -> std::vector<Key> {
  std::vector<Key> keys(n);
  std::mt19937_64 rng(seed);
  // Stay inside the signed domain so a signed Key never relies on wraparound.
  auto const span = static_cast<std::uint64_t>(std::numeric_limits<Key>::max());
  for (std::size_t i = 0; i < n; ++i) {
    std::uint64_t value = 0;
    switch (shape) {
      case Shape::Random:     value = rng() % (span / 2 + 1); break;
      case Shape::Sorted:     value = i; break;
      case Shape::Reverse:    value = n - i; break;
      case Shape::AllEqual:   value = 42; break;
      case Shape::TwoValues:  value = (rng() & 1u) ? 7 : 999; break;
      case Shape::ModThree:   value = i % 3; break;
      case Shape::Skewed:     value = (rng() % 10 == 0) ? rng() % 1000 : 5; break;
      case Shape::OrganPipe:  value = i < n / 2 ? i : n - i; break;
      case Shape::Sawtooth:   value = i % 128; break;
    }
    keys[i] = static_cast<Key>(value % (span / 2 + 1));
  }
  return keys;
}

// Sortedness, permutation validity, co-sort consistency, and the third-column
// materialisation, in one pass over the result.
template <class Key, class Idx>
void check_result(std::string const & label, std::vector<Key> const & original,
                  std::vector<Key> const & keys, std::vector<Idx> const & idx) {
  ++g_checks;
  auto const n = original.size();
  if (!std::is_sorted(keys.begin(), keys.end())) {
    fail(label, "keys are not non-decreasing");
    return;
  }
  std::vector<bool> seen(n, false);
  for (std::size_t i = 0; i < n; ++i) {
    auto const at = static_cast<std::size_t>(idx[i]);
    if (at >= n) {
      fail(label, "index " + std::to_string(at) + " out of range");
      return;
    }
    if (seen[at]) {
      fail(label, "index " + std::to_string(at) + " appears twice");
      return;
    }
    seen[at] = true;
    if (keys[i] != original[at]) {
      fail(label, "keys[i] != original[idx[i]] at i=" + std::to_string(i));
      return;
    }
  }

  // A further column materialised through the permutation must agree with the
  // scalar reference -- this is the operation the index column exists to enable.
  std::vector<std::uint64_t> column(n), got(n), want(n);
  for (std::size_t i = 0; i < n; ++i) {
    column[i] = i * 31 + 7;
  }
  tsl_apply_permutation(got.data(), column.data(), idx.data(), n);
  for (std::size_t i = 0; i < n; ++i) {
    want[i] = column[static_cast<std::size_t>(idx[i])];
  }
  if (got != want) {
    fail(label, "apply_permutation disagrees with the scalar reference");
  }
}

template <class Key, class Simd, int K, TslSampleSortBuckets Policy,
          TslSampleSortBase BasePolicy = TslSampleSortBase::Insertion>
auto run_sort(std::vector<Key> keys, std::size_t chunks,
              std::vector<typename TslSampleSortTraits<Key>::index_type> & idx_out,
              TslSampleSortMetrics * metrics = nullptr) -> std::vector<Key> {
  using Idx = typename TslSampleSortTraits<Key>::index_type;
  auto const n = keys.size();
  std::vector<Idx> idx(n);
  std::iota(idx.begin(), idx.end(), Idx{0});
  std::vector<Key> keys_scratch(n);
  std::vector<Idx> idx_scratch(n);

  TslSampleSortOptions options;
  options.chunks = chunks;
  tsl_samplesort_cosort<Key, Simd, K, Policy, 8, 256, BasePolicy>(
    keys.data(), idx.data(), n, keys_scratch.data(), idx_scratch.data(),
    options, metrics);
  idx_out = std::move(idx);
  return keys;
}

template <class Key, class Simd, int K, TslSampleSortBuckets Policy,
          TslSampleSortBase BasePolicy = TslSampleSortBase::Insertion>
void run_shape(char const * tag, Shape shape, std::size_t n) {
  using Idx = typename TslSampleSortTraits<Key>::index_type;
  auto const label = std::string(tag) + "/" + shape_name(shape) + "/n=" + std::to_string(n);
  auto const original = make_keys<Key>(shape, n, 0xC0FFEE ^ (n * 31));

  std::vector<Idx> idx;
  auto const keys = run_sort<Key, Simd, K, Policy, BasePolicy>(original, 1, idx);
  check_result(label, original, keys, idx);
}

// The chunk-invariance test of the specification's section 8 item 6.
template <class Key, class Simd, int K, TslSampleSortBuckets Policy,
          TslSampleSortBase BasePolicy = TslSampleSortBase::Insertion>
void run_chunk_invariance(char const * tag, Shape shape, std::size_t n) {
  using Idx = typename TslSampleSortTraits<Key>::index_type;
  auto const label =
    std::string(tag) + "/chunks/" + shape_name(shape) + "/n=" + std::to_string(n);
  auto const original = make_keys<Key>(shape, n, 0xBEEF ^ (n * 17));

  std::vector<Idx> reference_idx;
  auto const reference_keys =
    run_sort<Key, Simd, K, Policy, BasePolicy>(original, 1, reference_idx);
  check_result(label + "/c=1", original, reference_keys, reference_idx);

  for (std::size_t chunks : {std::size_t{2}, std::size_t{3}, std::size_t{7}}) {
    ++g_checks;
    std::vector<Idx> idx;
    auto const keys = run_sort<Key, Simd, K, Policy, BasePolicy>(original, chunks, idx);
    if (keys != reference_keys) {
      fail(label + "/c=" + std::to_string(chunks), "keys differ from the one-chunk run");
      continue;
    }
    if (idx != reference_idx) {
      fail(label + "/c=" + std::to_string(chunks), "permutation differs from the one-chunk run");
    }
  }
}

// The vector classifier and the scalar rule must agree exactly; the scalar form
// is the tail's implementation, so a disagreement is a silently split bucket.
template <class Key, class Simd, int K, TslSampleSortBuckets Policy>
void run_classifier_agreement(char const * tag) {
  using Kernels = TslSampleSortKernels<Key, Simd, K, Policy>;
  using Id = typename Kernels::bucket_id_type;
  ++g_checks;

  auto const keys = make_keys<Key>(Shape::Random, 4099, 0x51DE);
  TslPivotRng rng(0xA11CE);
  auto const splitters = Kernels::select_splitters(keys.data(), 0, keys.size(), rng);

  std::vector<Id> ids(keys.size(), Id{0});
  std::vector<std::size_t> histogram(
    static_cast<std::size_t>(Kernels::max_buckets), 0);
  Kernels::classify_chunk(ids.data(), keys.data(), 0, keys.size(), splitters,
                          histogram.data());

  std::vector<std::size_t> expected_hist(
    static_cast<std::size_t>(Kernels::max_buckets), 0);
  for (std::size_t i = 0; i < keys.size(); ++i) {
    auto const want = Kernels::scalar_bucket(keys[i], splitters);
    ++expected_hist[want];
    if (ids[i] != want) {
      fail(std::string(tag) + "/classifier",
           "vector id " + std::to_string(ids[i]) + " != scalar id "
             + std::to_string(want) + " at " + std::to_string(i));
      return;
    }
  }
  if (histogram != expected_hist) {
    fail(std::string(tag) + "/classifier", "histogram disagrees with the ids");
  }
}

template <class Key, class Simd, int K, TslSampleSortBuckets Policy,
          TslSampleSortBase BasePolicy = TslSampleSortBase::Insertion>
void run_width(char const * tag) {
  std::vector<std::size_t> const sizes{
    0, 1, 2, 15, 16, 17, 255, 256, 257, 4095, 1u << 20
  };
  std::vector<Shape> const shapes{
    Shape::Random, Shape::Sorted, Shape::Reverse, Shape::AllEqual, Shape::TwoValues,
    Shape::ModThree, Shape::Skewed, Shape::OrganPipe, Shape::Sawtooth
  };

  for (auto const shape : shapes) {
    for (auto const n : sizes) {
      run_shape<Key, Simd, K, Policy, BasePolicy>(tag, shape, n);
    }
  }
  // Sizes that are not multiples of the lane count, and shapes that stress the
  // duplicate handling, are the ones worth running through every chunk count.
  for (auto const shape : {Shape::Random, Shape::AllEqual, Shape::TwoValues,
                           Shape::Skewed, Shape::Sawtooth}) {
    run_chunk_invariance<Key, Simd, K, Policy, BasePolicy>(tag, shape, 4095);
    run_chunk_invariance<Key, Simd, K, Policy, BasePolicy>(tag, shape, 1u << 20);
  }
  run_classifier_agreement<Key, Simd, K, Policy>(tag);
}

}  // namespace

int main() {
  std::printf("-- TSL samplesort co-sort --\n");

  run_width<std::uint32_t, tsl::simd<std::uint32_t, tsl::avx512>, 16,
            TslSampleSortBuckets::Adaptive>("u32/K=16/equality");
  run_width<std::uint32_t, tsl::simd<std::uint32_t, tsl::avx512>, 16,
            TslSampleSortBuckets::Ordered>("u32/K=16/ordered");
  run_width<std::int32_t, tsl::simd<std::int32_t, tsl::avx512>, 16,
            TslSampleSortBuckets::Adaptive>("i32/K=16/equality");
  run_width<std::uint64_t, tsl::simd<std::uint64_t, tsl::avx512>, 16,
            TslSampleSortBuckets::Adaptive>("u64/K=16/equality");
  run_width<std::int64_t, tsl::simd<std::int64_t, tsl::avx512>, 16,
            TslSampleSortBuckets::Ordered>("i64/K=16/ordered");
  // K is a compile-time parameter of every kernel precisely so this is cheap.
  run_width<std::uint32_t, tsl::simd<std::uint32_t, tsl::avx512>, 8,
            TslSampleSortBuckets::Adaptive>("u32/K=8/equality");
  run_width<std::uint32_t, tsl::simd<std::uint32_t, tsl::avx512>, 32,
            TslSampleSortBuckets::Ordered>("u32/K=32/ordered");

  // The bitonic network as the base case instead of insertion. Measured slower
  // (see samplesort-notes.md) but it is a supported policy, so it is tested.
  run_width<std::uint32_t, tsl::simd<std::uint32_t, tsl::avx512>, 16,
            TslSampleSortBuckets::Adaptive,
            TslSampleSortBase::Network>("u32/K=16/equality/net-base");
  run_width<std::uint64_t, tsl::simd<std::uint64_t, tsl::avx512>, 16,
            TslSampleSortBuckets::Ordered,
            TslSampleSortBase::Network>("u64/K=16/ordered/net-base");

  // One pass at a size large enough to reach several recursion levels.
  run_shape<std::uint32_t, tsl::simd<std::uint32_t, tsl::avx512>, 16,
            TslSampleSortBuckets::Adaptive>("u32/K=16/equality", Shape::Random,
                                                1u << 24);
  run_shape<std::uint32_t, tsl::simd<std::uint32_t, tsl::avx512>, 16,
            TslSampleSortBuckets::Adaptive>("u32/K=16/equality", Shape::AllEqual,
                                                1u << 24);

  if (g_failures != 0) {
    std::printf("\nsamplesort tests FAILED: %zu of %zu checks\n", g_failures, g_checks);
    return 1;
  }
  std::printf("\nsamplesort tests passed (%zu checks)\n", g_checks);
  return 0;
}
