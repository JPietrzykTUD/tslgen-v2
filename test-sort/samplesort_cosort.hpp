#pragma once

// Vectorised samplesort for columnar co-sort, built on TSL.
//
// Sorts one key column ascending and carries an index column alongside it, so
// every other column of a table is materialised afterwards with one gather pass
// (`tsl_apply_permutation`). That is the same data model the indirect quicksort
// in `multicolumn_index_sort.hpp` uses; this is a different algorithm for it.
//
// -----------------------------------------------------------------------------
// Structure: parallelism must be additive
// -----------------------------------------------------------------------------
// The executor is sequential, but nothing below it assumes that. A partition
// step is four named phases and a scheduler can put a barrier between any two:
//
//   1  select_splitters(range)                      collective
//   2  classify_chunk(chunk) + local histogram      per chunk, independent
//   3  combine histograms -> per-chunk write cursors    reduction
//   4  distribute_chunk(chunk, cursors)             per chunk, independent
//
// Phases 2 and 4 are pure functions of their chunk plus the shared splitters and
// cursors: they take an explicit `(begin, end)` and write to absolute positions
// handed to them, never to "start of buffer plus a running counter". Chunk `c`'s
// cursor for bucket `b` is `global_offset[b] + sum of local_hist[c'][b] over
// c' < c`, computed that way even with one chunk so the code path is identical.
//
// Bucket recursion is an explicit task list, not a call stack. The executor
// (`samplesort_executor.hpp`) is the only piece a parallel version replaces.
//
// -----------------------------------------------------------------------------
// Deviations from the specification this implements, and why
// -----------------------------------------------------------------------------
// Recorded in full in `samplesort-notes.md`; the load-bearing ones:
//
// * Bucket ids are key-width, not `uint8_t`. TSL has no `convert_down` for
//   u32 -> u8 on AVX-512, so a byte id would need a scalar narrowing store. The
//   cost is 3 extra scratch bytes per element per pass at 32-bit keys.
// * No CPUID dispatch for VPOPCNTDQ. Selecting an implementation per extension
//   is TSL's job: `tsl::popcnt` resolves to `vpopcntd` where the target has it
//   and to a composed form where it does not, decided when the sorter is
//   instantiated on its `SimdStyle`.
// * Equality buckets are adaptive: a splitter gets one only when the sample says
//   its value repeats. A high-cardinality key therefore costs one comparison
//   sweep and `S + 1` buckets, the same as `Ordered`, and only a duplicate-heavy
//   key pays the second sweep and the extra write streams -- which is exactly
//   when they buy termination by construction.
//
// -----------------------------------------------------------------------------
// Guarantees
// -----------------------------------------------------------------------------
// * `keys` is non-decreasing on return and `idx` is a permutation of `0..n-1`
//   with `keys[i] == original_keys[idx[i]]`.
// * The result is always left in the caller's `keys`/`idx`, never in the scratch
//   pair: a range in the scratch pair is copied back when its task terminates.
// * **The sort is not stable** and must not be assumed to be.

#include <algorithm>
#include <array>
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <type_traits>
#include <chrono>
#include <vector>

#if defined(__AVX512F__)
#include <immintrin.h>
#endif

#include <tsl.hpp>

#include "cosort_bitonic_leaf.hpp"
#include "sort_helpers.hpp"


// Bucket-id width. Classification writes this array and distribution reads it,
// so at 32-bit keys a key-width id is three extra bytes per element per pass in
// each direction. Measured on the phase that reads it: byte ids cost 17.5% less
// at u32 and 19-28% less at u64.
enum class TslSampleSortIds { Byte, KeyWidth };


// TSL gap, and the only place this file leaves TSL. There is no `convert_down`
// from a 32- or 64-bit lane to a byte lane on AVX-512, so the narrowing store
// and the widening load are written against the intrinsics here and nowhere
// else; everything else in the sorter is TSL primitives. If TSL grows the pair,
// these two functions are what it replaces.
template <class Vec>
inline constexpr bool tsl_samplesort_has_byte_ids =
#if defined(__AVX512F__)
  (sizeof(typename Vec::base_type) == 4 && Vec::lane_count_v == 16)
  || (sizeof(typename Vec::base_type) == 8 && Vec::lane_count_v == 8);
#else
  false;
#endif

#if defined(__AVX512F__)
template <class Vec>
inline void tsl_samplesort_store_byte_ids(std::uint8_t * out,
                                          typename Vec::register_type ids) {
  if constexpr (sizeof(typename Vec::base_type) == 4) {
    _mm_storeu_si128(reinterpret_cast<__m128i *>(out), _mm512_cvtepi32_epi8(ids));
  } else {
    _mm_storel_epi64(reinterpret_cast<__m128i *>(out), _mm512_cvtepi64_epi8(ids));
  }
}

template <class Vec>
inline auto tsl_samplesort_load_byte_ids(std::uint8_t const * in) ->
  typename Vec::register_type {
  if constexpr (sizeof(typename Vec::base_type) == 4) {
    return _mm512_cvtepu8_epi32(_mm_loadu_si128(reinterpret_cast<__m128i const *>(in)));
  }
  return _mm512_cvtepu8_epi64(_mm_loadl_epi64(reinterpret_cast<__m128i const *>(in)));
}
#endif


// The index column is unsigned and as wide as the key, so one vector type
// carries ids, positions and the index column alike.
template <class Key>
struct TslSampleSortTraits;

template <> struct TslSampleSortTraits<std::uint32_t> { using index_type = std::uint32_t; };
template <> struct TslSampleSortTraits<std::int32_t>  { using index_type = std::uint32_t; };
template <> struct TslSampleSortTraits<std::uint64_t> { using index_type = std::uint64_t; };
template <> struct TslSampleSortTraits<std::int64_t>  { using index_type = std::uint64_t; };


// What sorts a range once it is small enough to stop partitioning.
enum class TslSampleSortBase {
  // Scalar insertion sort over (key, index) pairs. Correct everywhere and the
  // only option for a signed key, for the reason given at `base_sort_pairs`.
  Insertion,
  // `TslCoSortBitonicLeaf`, the playground's existing branch-free leaf, with the
  // index column as its one payload. Fixed cost for anything at or below its
  // capacity, which is where a samplesort spends most of its elements.
  Network,
};


// How a key maps to a bucket.
enum class TslSampleSortBuckets {
  // `S + 1` ordered buckets: bucket b holds `splitter[b-1] <= x < splitter[b]`.
  // One comparison sweep. A bucket of equal keys is possible, so termination
  // rests on the degenerate fallback and the depth guard.
  Ordered,
  // An equality bucket -- one holding a single repeated value, never recursed
  // into -- but only for a splitter the sample says actually repeats: one whose
  // value fills more than `Oversample` sample slots and so spans more than one
  // splitter position. A high-cardinality key produces none, and then this costs
  // exactly what `Ordered` costs: `S + 1` buckets and one comparison sweep. A
  // duplicate-heavy key pays one extra comparison and two extra write streams
  // per repeating value, which is precisely when that buys termination by
  // construction instead of by fallback.
  Adaptive,
};


struct TslSampleSortMetrics {
  std::size_t partition_steps = 0;
  std::size_t classified_elements = 0;
  std::size_t distributed_elements = 0;
  std::size_t base_case_ranges = 0;
  std::size_t base_case_elements = 0;
  std::size_t equality_buckets = 0;   // ranges skipped because they hold one value
  std::size_t equality_elements = 0;
  std::size_t degenerate_steps = 0;   // splitter selection found fewer than two values
  std::size_t heapsort_ranges = 0;    // depth guard fired
  std::size_t copied_back_elements = 0;
  std::size_t max_depth = 0;
  std::size_t tasks = 0;
  // The largest bucket count any step actually used, so a run reports where it
  // landed against the concurrent-write-stream cliff rather than assuming the
  // compile-time worst case.
  std::size_t max_buckets_used = 0;
  std::size_t equality_buckets_allocated = 0;
  // Filled only when the executor is instantiated with profiling on; two clock
  // reads per phase per task, so it is off by default and off in any timed run
  // that is not asking this question.
  double ns_splitters = 0.0;
  double ns_classify = 0.0;
  double ns_distribute = 0.0;
  double ns_base = 0.0;
  double ns_copyback = 0.0;
};


// One sub-problem. Ranges keep the same absolute offsets in both buffer pairs,
// so a task names an offset and which pair currently holds its data. Parity
// lives here rather than in a global or in the depth because buckets reach
// different depths and a parallel executor runs them out of order.
struct TslSampleSortTask {
  std::size_t begin = 0;
  std::size_t count = 0;
  int depth = 0;
  bool in_scratch = false;  // data is in the scratch pair rather than the caller's
  bool sorted = false;      // an equality bucket: already ordered, only copy-back is due
};


// Distinct splitters for one partition step, plus the bucket layout they imply.
template <class Key, int S>
struct TslSampleSortSplitters {
  std::array<Key, S> values{};
  // The subset of `values` the sample found repeating, in the same order. Empty
  // for a high-cardinality key, which is what keeps the common case at one
  // comparison sweep and `S + 1` buckets.
  std::array<Key, S> repeats{};
  std::array<bool, 2 * S + 1> equality{};  // indexed by bucket
  int count = 0;         // distinct splitters kept
  int repeat_count = 0;  // how many of them get an equality bucket
  int buckets = 1;

  auto is_equality_bucket(int bucket) const -> bool {
    return equality[static_cast<std::size_t>(bucket)];
  }

  // `id(x) = count(x >= s_j)` over every splitter, plus `count(x > s_j)` over
  // the repeating ones only. The ids stay contiguous even when just some
  // splitters repeat: the equality bucket for repeating splitter `i` is
  // `i + 1 + e_i`, where `e_i` counts repeating splitters before `i`.
  void finish() {
    buckets = count + 1 + repeat_count;
    equality.fill(false);
    int seen = 0;
    int at = 0;
    for (int i = 0; i < count; ++i) {
      if (at < repeat_count && !(values[i] < repeats[at]) && !(repeats[at] < values[i])) {
        equality[static_cast<std::size_t>(i + 1 + seen)] = true;
        ++seen;
        ++at;
      }
    }
  }
};


// Runtime knobs. `chunks` exists so the sequential build exercises the code path
// a parallel executor will use; see `samplesort-notes.md`.
struct TslSampleSortOptions {
  std::size_t chunks = 1;
  std::uint64_t seed = 0x5A3F1E77C0FFEEull;
};


// The kernels. `K` is the bucket count under `Ordered` and the splitter count
// plus one under both policies, so it stays a compile-time parameter of every
// kernel: the right K is a measurement, not a constant (see the notes).
template <
  class Key,
  class SimdStyle,
  int K = 16,
  TslSampleSortBuckets Policy = TslSampleSortBuckets::Adaptive,
  int Oversample = 8,
  std::size_t BaseCase = 256,
  TslSampleSortBase BasePolicy = TslSampleSortBase::Insertion,
  TslSampleSortIds IdWidth = TslSampleSortIds::Byte
>
class TslSampleSortKernels {
 public:
  using key_type = Key;
  using index_type = typename TslSampleSortTraits<Key>::index_type;
  using KeyVec = SimdStyle;
  using IdxVec = typename SimdStyle::template with_base_type<index_type>;
  using Splitters = TslSampleSortSplitters<Key, K - 1>;
  // Byte ids where the narrowing pair exists, key-width otherwise. Never a
  // correctness difference, only traffic.
  static constexpr bool byte_ids =
    IdWidth == TslSampleSortIds::Byte
    && tsl_samplesort_has_byte_ids<typename SimdStyle::template with_base_type<
         typename TslSampleSortTraits<Key>::index_type>>;
  using bucket_id_type =
    std::conditional_t<byte_ids, std::uint8_t,
                       typename TslSampleSortTraits<Key>::index_type>;

  static constexpr int splitter_count = K - 1;
  // Worst case, used only to size arrays: every splitter turns out to repeat.
  static constexpr int max_buckets =
    Policy == TslSampleSortBuckets::Adaptive ? 2 * splitter_count + 1 : K;
  static constexpr std::size_t lanes = KeyVec::lane_count_v;
  // The network leaf permutes its payload without interpreting it, so the index
  // column can be handed to it directly -- but only when the index type *is* the
  // key type, which is every unsigned key. For a signed key the two differ and
  // reinterpreting one as the other is not something to do quietly, so that
  // combination keeps the insertion leaf.
  static constexpr bool network_base =
    BasePolicy == TslSampleSortBase::Network
    && std::is_same_v<Key, typename TslSampleSortTraits<Key>::index_type>;
  using NetworkLeaf = TslCoSortBitonicLeaf<Key, SimdStyle>;
  // Asking for the network leaf with a signed key is not an error, it just does
  // not get one: `network_base` is false and the insertion leaf runs.
  static constexpr std::size_t base_case =
    network_base ? std::min(BaseCase, NetworkLeaf::capacity) : BaseCase;
  static constexpr std::size_t sample_size =
    static_cast<std::size_t>(Oversample) * static_cast<std::size_t>(K);

  static_assert(std::is_same_v<typename KeyVec::base_type, Key>,
                "SimdStyle must be the vector type for Key");
  static_assert(sizeof(Key) == sizeof(index_type),
                "the index column is as wide as the key by construction");
  static_assert(lanes == IdxVec::lane_count_v,
                "key and index vectors must agree on lane count");
  // The classifier turns a key comparison into an index-width increment, which
  // needs one mask type across both. True for every fixed-width AVX-512 profile.
  static_assert(std::is_same_v<typename KeyVec::mask_type, typename IdxVec::mask_type>,
                "key and index vectors must share a mask type");
  // Distribution keeps one open write stream per bucket per column and two
  // columns are carried, so the typical bucket count must stay inside the flat
  // region the stream measurement found. `Adaptive` reaches `max_buckets` only on
  // a key where every splitter repeats; that case must stay under the measured
  // cliff rather than under the comfortable rule, and `max_buckets_used` reports
  // where a run actually landed.
  static_assert(2 * K <= 64,
                "too many concurrent write streams in the typical case: lower K");
  static_assert(!byte_ids || max_buckets <= 256,
                "byte bucket ids cannot name this many buckets");
  static_assert(2 * max_buckets <= 128,
                "worst-case bucket count crosses the measured stream cliff: lower K");

  // ---------------------------------------------------------------------------
  // Phase 1: splitter selection
  // ---------------------------------------------------------------------------
  // Draws `Oversample * K` keys with a fixed-seed PRNG, sorts them, takes every
  // `Oversample`-th, and drops duplicates. Deduplication is not optional: equal
  // splitters make empty buckets and, under `Ordered`, break termination.
  static auto select_splitters(
    Key const * keys, std::size_t begin, std::size_t end, TslPivotRng & rng
  ) -> Splitters {
    Splitters out;
    auto const count = end - begin;

    std::array<Key, sample_size> sample{};
    auto const drawn = std::min(sample_size, count);
    for (std::size_t i = 0; i < drawn; ++i) {
      sample[i] = keys[begin + static_cast<std::size_t>(rng.next() % count)];
    }
    std::sort(sample.begin(), sample.begin() + static_cast<std::ptrdiff_t>(drawn));

    // Every Oversample-th sorted sample, deduplicated in one pass.
    auto const stride = std::max<std::size_t>(1, drawn / static_cast<std::size_t>(K));
    for (int i = 0; i < splitter_count; ++i) {
      auto const at = static_cast<std::size_t>(i + 1) * stride - 1;
      if (at >= drawn) {
        break;
      }
      auto const value = sample[at];
      if (out.count != 0 && !(out.values[out.count - 1] < value)) {
        continue;  // equal to the previous splitter
      }
      out.values[out.count++] = value;
    }

    // A splitter earns an equality bucket only if the sample says its value
    // repeats -- occupying more than one splitter slot's worth of sample, i.e.
    // more than `stride` of the `drawn` entries. The sample is sorted, so that
    // is one `equal_range` per kept splitter and no extra pass over the data.
    if constexpr (Policy == TslSampleSortBuckets::Adaptive) {
      auto const first = sample.begin();
      auto const last = sample.begin() + static_cast<std::ptrdiff_t>(drawn);
      for (int i = 0; i < out.count; ++i) {
        auto const span = std::equal_range(first, last, out.values[i]);
        auto const occurrences = static_cast<std::size_t>(span.second - span.first);
        if (occurrences > stride) {
          out.repeats[out.repeat_count++] = out.values[i];
        }
      }
    }
    out.finish();
    return out;
  }

  // The two splitters that always make progress when sampling found fewer than
  // two distinct values: the range's own minimum and maximum. Under either
  // policy this leaves the strict middle to recurse on and nothing else.
  static auto splitters_from_bounds(Key low, Key high) -> Splitters {
    Splitters out;
    out.values[0] = low;
    out.count = 1;
    if (low < high) {
      out.values[1] = high;
      out.count = 2;
    }
    // These two are known to repeat -- they are the range's own bounds, reached
    // because sampling found one value -- so they always earn equality buckets
    // when the policy allows them. That is what leaves only the strict middle to
    // recurse on and makes the fallback strictly shrink the problem.
    if constexpr (Policy == TslSampleSortBuckets::Adaptive) {
      for (int i = 0; i < out.count; ++i) {
        out.repeats[out.repeat_count++] = out.values[i];
      }
    }
    out.finish();
    return out;
  }

  // ---------------------------------------------------------------------------
  // Phase 2: classification
  // ---------------------------------------------------------------------------
  // Sum of masks, not a search tree: O(K) comparisons beat O(log K) gathers at
  // this K because the tree needs a gather per level. Four independent
  // accumulators, because one accumulator is a loop-carried dependency.
  //
  // Under `Adaptive` the id is `count(x >= s_i)` plus `count(x > s_i)` taken
  // over the repeating splitters only, which lands a dedicated id on each value
  // known to repeat. A key with no repeats runs exactly one sweep.
  static void classify_chunk(
    bucket_id_type * bucket_ids,
    Key const * keys,
    std::size_t begin,
    std::size_t end,
    Splitters const & splitters,
    std::size_t * local_hist  // `buckets` entries, caller-zeroed
  ) {
    auto const ones = tsl::set1<IdxVec>(1);
    auto const distinct = splitters.count;
    auto const repeating = splitters.repeat_count;

    // Four interleaved tallies rather than one. Incrementing a single histogram
    // serialises on repeated bucket ids through store-to-load forwarding, and
    // repeated ids are the common case; rotating by lane breaks that into four
    // independent chains. Summed into the caller's array at the end.
    constexpr std::size_t ways = 4;
    std::array<std::array<std::size_t, static_cast<std::size_t>(max_buckets)>, ways>
      tally{};

    std::size_t i = begin;
    for (; i + lanes <= end; i += lanes) {
      auto const v = tsl::load<KeyVec>(keys + i);
      auto a0 = tsl::set_zero<IdxVec>();
      auto a1 = tsl::set_zero<IdxVec>();
      auto a2 = tsl::set_zero<IdxVec>();
      auto a3 = tsl::set_zero<IdxVec>();

      int j = 0;
      for (; j + 4 <= distinct; j += 4) {
        a0 = add_ge(a0, v, splitters.values[j + 0], ones);
        a1 = add_ge(a1, v, splitters.values[j + 1], ones);
        a2 = add_ge(a2, v, splitters.values[j + 2], ones);
        a3 = add_ge(a3, v, splitters.values[j + 3], ones);
      }
      // `K - 1` is not a multiple of four, so this remainder is required.
      for (; j < distinct; ++j) {
        a0 = add_ge(a0, v, splitters.values[j], ones);
      }

      // Only the repeating splitters need the strict sweep, and on a
      // high-cardinality key there are none -- so this loop does not run at all
      // and classification costs the same as under `Ordered`.
      if constexpr (Policy == TslSampleSortBuckets::Adaptive) {
        j = 0;
        for (; j + 4 <= repeating; j += 4) {
          a0 = add_gt(a0, v, splitters.repeats[j + 0], ones);
          a1 = add_gt(a1, v, splitters.repeats[j + 1], ones);
          a2 = add_gt(a2, v, splitters.repeats[j + 2], ones);
          a3 = add_gt(a3, v, splitters.repeats[j + 3], ones);
        }
        for (; j < repeating; ++j) {
          a0 = add_gt(a0, v, splitters.repeats[j], ones);
        }
      }

      auto const ids = tsl::add<IdxVec>(tsl::add<IdxVec>(a0, a1), tsl::add<IdxVec>(a2, a3));
      if constexpr (byte_ids) {
        tsl_samplesort_store_byte_ids<IdxVec>(bucket_ids + i, ids);
      } else {
        tsl::store<IdxVec>(reinterpret_cast<index_type *>(bucket_ids + i), ids);
      }
      // The ids are in store-to-load range, so tallying them here costs no
      // second pass and produces exactly the per-chunk histogram phase 3 needs.
      for (std::size_t lane = 0; lane < lanes; ++lane) {
        ++tally[lane & (ways - 1)][bucket_ids[i + lane]];
      }
    }
    for (; i < end; ++i) {
      auto const id = scalar_bucket(keys[i], splitters);
      bucket_ids[i] = static_cast<bucket_id_type>(id);
      ++tally[0][id];
    }
    for (int b = 0; b < splitters.buckets; ++b) {
      auto const bucket = static_cast<std::size_t>(b);
      for (std::size_t way = 0; way < ways; ++way) {
        local_hist[bucket] += tally[way][bucket];
      }
    }
  }

  // ---------------------------------------------------------------------------
  // Phase 4: distribution
  // ---------------------------------------------------------------------------
  // Scatter, not compress-store: compress-store costs one store per bucket per
  // vector per column, scatter costs one store per vector per column whatever K
  // is. One gather and three scatters per vector.
  //
  // `write_pos` is this chunk's private cursor array, already resolved to
  // absolute positions by phase 3.
  static void distribute_chunk(
    Key * out_keys,
    index_type * out_idx,
    Key const * keys,
    index_type const * idx,
    bucket_id_type const * bucket_ids,
    std::size_t begin,
    std::size_t end,
    index_type * write_pos
  ) {
    auto const one = tsl::set1<IdxVec>(1);

    std::size_t i = begin;
    for (; i + lanes <= end; i += lanes) {
      auto const v = tsl::load<KeyVec>(keys + i);
      auto const iv = tsl::load<IdxVec>(idx + i);
      auto const ids = byte_ids
        ? load_ids(bucket_ids + i)
        : tsl::load<IdxVec>(reinterpret_cast<index_type const *>(bucket_ids + i));

      // How many earlier lanes of this vector go to the same bucket.
      auto const rank = tsl::popcnt<IdxVec>(tsl::conflict<IdxVec>(ids));
      auto const cursor = tsl::gather<IdxVec, IdxVec, sizeof(index_type)>(write_pos, ids);
      auto const addr = tsl::add<IdxVec>(cursor, rank);

      tsl::scatter<KeyVec, IdxVec, sizeof(Key)>(out_keys, addr, v);
      tsl::scatter<IdxVec, IdxVec, sizeof(index_type)>(out_idx, addr, iv);

      // Cursor update. A scatter resolves same-address conflicts by the highest
      // lane index winning, and `rank` increases with lane index within a
      // bucket, so scattering `addr + 1` leaves precisely the next free position
      // with no reduction. This is load-bearing, not incidental -- the assertion
      // in `partition_step` checks each cursor landed on its bucket's end.
      tsl::scatter<IdxVec, IdxVec, sizeof(index_type)>(
        write_pos, ids, tsl::add<IdxVec>(addr, one));
    }
    for (; i < end; ++i) {
      auto const id = bucket_ids[i];
      auto const at = write_pos[id]++;
      out_keys[at] = keys[i];
      out_idx[at] = idx[i];
    }
  }

  // ---------------------------------------------------------------------------
  // Base cases
  // ---------------------------------------------------------------------------
  // Sorts one terminal range. Which leaf runs is a compile-time policy; the
  // executor does not know there is a choice.
  static void base_sort_pairs(
    Key * keys, index_type * idx, std::size_t begin, std::size_t end
  ) {
    if constexpr (network_base) {
      auto const count = end - begin;
      if (count <= NetworkLeaf::capacity) {
        // The index column is the leaf's single payload. `network_base` has
        // already established that its type is the key's.
        Key * payload = reinterpret_cast<Key *>(idx + begin);
        Key * const columns[1] = {payload};
        NetworkLeaf::template sort<TslSortOrder::ASCENDING>(keys + begin, columns,
                                                            1, count);
        return;
      }
    }
    insertion_sort_pairs(keys, idx, begin, end);
  }

  // Insertion sort over (key, index) pairs, both arrays moved in lockstep.
  static void insertion_sort_pairs(
    Key * keys, index_type * idx, std::size_t begin, std::size_t end
  ) {
    for (std::size_t i = begin + 1; i < end; ++i) {
      auto const key = keys[i];
      auto const value = idx[i];
      std::size_t at = i;
      while (at > begin && keys[at - 1] > key) {
        keys[at] = keys[at - 1];
        idx[at] = idx[at - 1];
        --at;
      }
      keys[at] = key;
      idx[at] = value;
    }
  }

  // The depth guard's fallback: O(n log n) whatever the input does, so a
  // pathological recursion becomes a slowdown rather than a hang.
  static void heapsort_pairs(
    Key * keys, index_type * idx, std::size_t begin, std::size_t end
  ) {
    auto const count = end - begin;
    auto sift = [&](std::size_t root, std::size_t size) {
      while (true) {
        auto child = 2 * root + 1;
        if (child >= size) {
          return;
        }
        if (child + 1 < size && keys[begin + child] < keys[begin + child + 1]) {
          ++child;
        }
        if (!(keys[begin + root] < keys[begin + child])) {
          return;
        }
        std::swap(keys[begin + root], keys[begin + child]);
        std::swap(idx[begin + root], idx[begin + child]);
        root = child;
      }
    };
    for (std::size_t i = count / 2; i-- > 0;) {
      sift(i, count);
    }
    for (std::size_t i = count; i-- > 1;) {
      std::swap(keys[begin], keys[begin + i]);
      std::swap(idx[begin], idx[begin + i]);
      sift(0, i);
    }
  }

 private:
  static auto load_ids(bucket_id_type const * at) -> typename IdxVec::register_type {
    if constexpr (byte_ids) {
      return tsl_samplesort_load_byte_ids<IdxVec>(at);
    } else {
      return tsl::load<IdxVec>(reinterpret_cast<index_type const *>(at));
    }
  }

  static auto add_ge(
    typename IdxVec::register_type accumulator,
    typename KeyVec::register_type values,
    Key splitter,
    typename IdxVec::register_type ones
  ) -> typename IdxVec::register_type {
    auto const mask =
      tsl::greater_than_or_equal<KeyVec>(values, tsl::set1<KeyVec>(splitter));
    return tsl::add<IdxVec>(accumulator, tsl::mov_maskz<IdxVec>(mask, ones));
  }

  static auto add_gt(
    typename IdxVec::register_type accumulator,
    typename KeyVec::register_type values,
    Key splitter,
    typename IdxVec::register_type ones
  ) -> typename IdxVec::register_type {
    auto const mask = tsl::greater_than<KeyVec>(values, tsl::set1<KeyVec>(splitter));
    return tsl::add<IdxVec>(accumulator, tsl::mov_maskz<IdxVec>(mask, ones));
  }

 public:
  // The scalar form of the same rule, used by the tail and by the tests as an
  // independent check that the vector classifier agrees.
  static auto scalar_bucket(Key value, Splitters const & splitters) -> index_type {
    index_type id = 0;
    for (int j = 0; j < splitters.count; ++j) {
      if (!(value < splitters.values[j])) {
        ++id;
      }
    }
    if constexpr (Policy == TslSampleSortBuckets::Adaptive) {
      for (int j = 0; j < splitters.repeat_count; ++j) {
        if (value > splitters.repeats[j]) {
          ++id;
        }
      }
    }
    return id;
  }
};


// Scratch that outlives one partition step, allocated once per sort.
template <class Kernels>
struct TslSampleSortWorkspace {
  using index_type = typename Kernels::index_type;

  using bucket_id_type = typename Kernels::bucket_id_type;

  std::vector<bucket_id_type> bucket_ids;  // one per element, indexed absolutely
  std::vector<std::size_t> histogram;  // chunks x buckets, row-major per chunk
  std::vector<index_type> cursors;     // chunks x buckets
  std::vector<std::size_t> counts;     // buckets
  std::vector<std::size_t> offsets;    // buckets, absolute

  void resize(std::size_t elements, std::size_t chunks) {
    bucket_ids.assign(elements, bucket_id_type{0});
    histogram.assign(chunks * static_cast<std::size_t>(Kernels::max_buckets), 0);
    cursors.assign(chunks * static_cast<std::size_t>(Kernels::max_buckets), index_type{0});
    counts.assign(static_cast<std::size_t>(Kernels::max_buckets), 0);
    offsets.assign(static_cast<std::size_t>(Kernels::max_buckets), 0);
  }
};


// One partition step: phases 1 to 4, then subtask descriptors. Recursion is the
// executor's business -- this function never calls itself.
//
// Returns false when the range needs no partitioning at all (every key equal),
// in which case `emit` carries the range back as an already-sorted task.
template <class Kernels, bool Profile = false>
auto tsl_samplesort_partition_step(
  TslSampleSortTask const & task,
  typename Kernels::key_type * keys,
  typename Kernels::index_type * idx,
  typename Kernels::key_type * keys_scratch,
  typename Kernels::index_type * idx_scratch,
  TslSampleSortWorkspace<Kernels> & workspace,
  TslSampleSortOptions const & options,
  TslPivotRng & rng,
  TslSampleSortMetrics & metrics,
  std::vector<TslSampleSortTask> & emit
) -> void {
  using Key = typename Kernels::key_type;
  using Idx = typename Kernels::index_type;
  constexpr auto lanes = Kernels::lanes;

  // Read from whichever pair holds this range; write to the other one.
  Key * const source_keys = task.in_scratch ? keys_scratch : keys;
  Idx * const source_idx = task.in_scratch ? idx_scratch : idx;
  Key * const target_keys = task.in_scratch ? keys : keys_scratch;
  Idx * const target_idx = task.in_scratch ? idx : idx_scratch;

  auto const begin = task.begin;
  auto const end = task.begin + task.count;
  auto const now = [] { return std::chrono::steady_clock::now(); };
  auto const since = [](auto start) {
    return std::chrono::duration<double, std::nano>(
             std::chrono::steady_clock::now() - start).count();
  };

  // ---- phase 1: collective ----
  auto const t_splitters = now();
  auto splitters = Kernels::select_splitters(source_keys, begin, end, rng);
  if constexpr (Profile) {
    metrics.ns_splitters += since(t_splitters);
  }
  if (splitters.count == 0) {
    // Sampling found one value. Either the range really is uniform, or the
    // sample missed: the range's own bounds always separate it if it is not.
    ++metrics.degenerate_steps;
    auto low = source_keys[begin];
    auto high = low;
    for (auto i = begin + 1; i < end; ++i) {
      low = std::min(low, source_keys[i]);
      high = std::max(high, source_keys[i]);
    }
    if (!(low < high)) {
      emit.push_back(TslSampleSortTask{begin, task.count, task.depth,
                                       task.in_scratch, true});
      return;
    }
    splitters = Kernels::splitters_from_bounds(low, high);
  }

  ++metrics.partition_steps;
  auto const buckets = static_cast<std::size_t>(splitters.buckets);
  metrics.max_buckets_used = std::max(metrics.max_buckets_used, buckets);
  metrics.equality_buckets_allocated +=
    static_cast<std::size_t>(splitters.repeat_count);

  // Chunk boundaries are multiples of the lane count, so no chunk needs a
  // scalar head and only the last one has a tail. Enforced even at one chunk so
  // the sequential tests exercise the same arithmetic a parallel run will use.
  auto const vectors = task.count / lanes;
  auto chunks = std::max<std::size_t>(1, options.chunks);
  if (vectors < chunks) {
    chunks = std::max<std::size_t>(1, vectors);
  }
  auto const chunk_begin = [&](std::size_t c) {
    return begin + (c * vectors / chunks) * lanes;
  };
  auto const chunk_end = [&](std::size_t c) {
    return c + 1 == chunks ? end : begin + ((c + 1) * vectors / chunks) * lanes;
  };

  // ---- phase 2: per chunk, independent ----
  std::fill(workspace.histogram.begin(),
            workspace.histogram.begin()
              + static_cast<std::ptrdiff_t>(chunks * buckets), 0);
  auto const t_classify = now();
  for (std::size_t c = 0; c < chunks; ++c) {
    Kernels::classify_chunk(workspace.bucket_ids.data(), source_keys,
                            chunk_begin(c), chunk_end(c), splitters,
                            workspace.histogram.data() + c * buckets);
  }
  if constexpr (Profile) {
    metrics.ns_classify += since(t_classify);
  }
  metrics.classified_elements += task.count;

  // ---- phase 3: collective reduction ----
  // Transposed deliberately: bucket outer, chunk inner, so each bucket's column
  // of per-chunk counts is walked once and the running sum stays in a register.
  std::size_t running = begin;
  for (std::size_t b = 0; b < buckets; ++b) {
    workspace.offsets[b] = running;
    std::size_t total = 0;
    for (std::size_t c = 0; c < chunks; ++c) {
      workspace.cursors[c * buckets + b] = static_cast<Idx>(running + total);
      total += workspace.histogram[c * buckets + b];
    }
    workspace.counts[b] = total;
    running += total;
  }
  assert(running == end && "histogram does not account for every element");

  // ---- phase 4: per chunk, independent ----
  auto const t_distribute = now();
  for (std::size_t c = 0; c < chunks; ++c) {
    Kernels::distribute_chunk(target_keys, target_idx, source_keys, source_idx,
                              workspace.bucket_ids.data(), chunk_begin(c),
                              chunk_end(c), workspace.cursors.data() + c * buckets);
  }
  if constexpr (Profile) {
    metrics.ns_distribute += since(t_distribute);
  }
  metrics.distributed_elements += task.count;

  // Each chunk's cursor must have advanced exactly through its own share, which
  // is what proves the scatter conflict-resolution assumption above held.
  for (std::size_t b = 0; b < buckets; ++b) {
    auto expected = workspace.offsets[b];
    for (std::size_t c = 0; c < chunks; ++c) {
      expected += workspace.histogram[c * buckets + b];
      assert(workspace.cursors[c * buckets + b] == static_cast<Idx>(expected)
             && "a distribution cursor overran its bucket");
    }
    (void)expected;
  }

  // ---- emit subtasks; never recurse here ----
  for (std::size_t b = 0; b < buckets; ++b) {
    auto const count = workspace.counts[b];
    if (count == 0) {
      continue;
    }
    auto const equality = splitters.is_equality_bucket(static_cast<int>(b));
    if (equality) {
      ++metrics.equality_buckets;
      metrics.equality_elements += count;
    }
    emit.push_back(TslSampleSortTask{
      workspace.offsets[b], count, task.depth + 1, !task.in_scratch,
      equality || count <= 1});
  }
}
