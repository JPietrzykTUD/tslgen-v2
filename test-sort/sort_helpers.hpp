#pragma once

// Pivot selection shared by the sort/partition experiments in this directory.
//
// Every quicksort-shaped consumer here needs the same thing: an index into a
// range whose element splits that range. They had four copies of it -- two
// byte-identical median-of-three sorters, one that wrapped the same median in
// its own `pivot_t`, and the IAA frequency walk's median-of-nine -- so a change
// to the rule meant four edits and the four rules had silently drifted apart.
// This header owns the rule; a consumer contributes only its own comparison and
// the seed it wants the sample drawn from.
//
// -----------------------------------------------------------------------------
// The rule
// -----------------------------------------------------------------------------
// Bentley & McIlroy's tiering ("Engineering a Sort Function", 1993): below
// `tsl_pivot_ninther_threshold` elements take the median of three samples,
// above it the pseudomedian of nine -- the median of three medians-of-three.
// Nine samples cost eight more loads and comparisons per partition, which only
// pays off once the partition itself is long enough that a better split saves
// more than that; forty elements is where those two cross for the sorts here,
// and it is what the BSD/pdqsort lineage uses.
//
// -----------------------------------------------------------------------------
// Where the samples come from
// -----------------------------------------------------------------------------
// The three or nine sample positions are spread over evenly spaced ranges of
// the input, one sample per range, so the sample reflects the whole range and a
// presorted input still yields a near-central pivot. The position *inside* each
// range comes from `seed`, because a sampler that always reads the same offsets
// has input shapes that defeat it and this directory has both of them on hand:
//
//   * `datagen/dataset_catalog.hpp` keeps OrganPipe and Sawtooth out of the
//     default catalog only because sampling does not depend on position alone.
//     A sawtooth whose period divides the sample stride hands a strided sampler
//     the same residue for every sample, so all nine agree on the run minimum.
//   * `iaa_distinct_frequencies.hpp` documents organ-pipe input handing a
//     median of first, middle and last element the range minimum at every
//     level, which is the O(n * distinct) walk that file exists to avoid.
//
// Neither sorter here has an introsort depth limit to fall back on, so a
// degenerate split is unbounded rather than merely slow. Drawing the offset
// within each range keeps the spread that makes the sample representative while
// removing the fixed pattern an input can be aligned to, and `seed` keeps it
// reproducible: the same range and seed always yield the same pivot.
//
// -----------------------------------------------------------------------------
// What nine samples cost the two-way partition
// -----------------------------------------------------------------------------
// Measured against the three uniform samples this replaced, over 1M u32 keys
// with 0-4 payload columns (benchmark_multicolumn_sort): every network-leaf
// variant gains 11-19%, three-way insertion-leaf is flat, and two-way with an
// insertion leaf loses 10-28% on 4096-distinct input. That last one is the
// estimator working as intended. A two-way partition cannot separate a value
// from its own copies, so a subrange whose modal value is also its minimum only
// makes progress when the pivot lands above that value -- and nine samples
// identify the modal value far more reliably than three, so it lands on it more
// often. The variance of a worse estimator was doing the work there. Three-way
// partitioning strips the equal band instead and gains from the better median,
// which is why it is the default everywhere in benchmarks/.

#include <array>
#include <cstddef>
#include <cstdint>
#include <functional>


// splitmix64. One integer of state, so seeding is a store -- cheap enough that
// a caller can afford one stream per partition task, and cheap enough to also
// drive the sample offsets inside a single `tsl_pivot_index_of` call.
//
// Unsynchronized on purpose: an instance is a local of one sort call and is
// only ever reached from that call's own thread. A worker that takes over a
// partition receives a task descriptor and seeds its own instance from it. Do
// not promote an instance to a member or share one across workers.
class TslPivotRng {
  std::uint64_t state_;

 public:
  explicit constexpr TslPivotRng(std::uint64_t seed) : state_(seed) {}

  constexpr auto next() -> std::uint64_t {
    state_ += 0x9E3779B97F4A7C15ull;
    auto value = state_;
    value = (value ^ (value >> 30)) * 0xBF58476D1CE4E5B9ull;
    value = (value ^ (value >> 27)) * 0x94D049BB133111EBull;
    return value ^ (value >> 31);
  }
};


// splitmix64 of a single value, for callers that derive one seed from several
// coordinates rather than reading a stream.
constexpr auto tsl_pivot_mix(std::uint64_t value) -> std::uint64_t {
  return TslPivotRng(value).next();
}


// Median of three below, pseudomedian of nine at or above.
inline constexpr std::size_t tsl_pivot_ninther_threshold = 40;


namespace tsl_pivot_detail {

// The median of `keys[i0]`, `keys[i1]` and `keys[i2]`, as an index, using three
// comparisons and no swaps. `before` is the caller's strict order.
template <class DataType, class Before>
auto median_index_of_3(
  DataType const * keys,
  std::size_t i0,
  std::size_t i1,
  std::size_t i2,
  Before before
) -> std::size_t {
  auto const a = keys[i0];
  auto const b = keys[i1];
  auto const c = keys[i2];
  if (before(a, b)) {
    return before(b, c) ? i1 : (before(a, c) ? i2 : i0);
  }
  return before(a, c) ? i0 : (before(b, c) ? i2 : i1);
}

// One position from range `range` of `range_count` evenly spaced ranges over
// `count` elements. Every range is non-empty as long as count >= range_count,
// which both tiers guarantee.
inline auto sample_index(
  std::size_t count,
  std::size_t range,
  std::size_t range_count,
  TslPivotRng & rng
) -> std::size_t {
  auto const begin = count * range / range_count;
  auto const end = count * (range + 1) / range_count;
  return begin + static_cast<std::size_t>(rng.next() % (end - begin));
}

}  // namespace tsl_pivot_detail


// The index of an element of `keys[0, count)` to partition around. `before` is
// the caller's strict order, defaulting to ascending. `count` must not be zero;
// the returned index is always inside the range, so the element is by
// construction one the range contains.
template <class DataType, class Before = std::less<DataType>>
auto tsl_pivot_index_of(
  DataType const * keys,
  std::size_t count,
  std::uint64_t seed,
  Before before = {}
) -> std::size_t {
  if (count < 3) {
    return count / 2;
  }
  auto rng = TslPivotRng(seed);
  // Each draw advances `rng`, so they are named rather than passed inline:
  // argument evaluation order is unspecified, which would make which range got
  // which offset a property of the compiler rather than of the seed.
  if (count < tsl_pivot_ninther_threshold) {
    auto const first = tsl_pivot_detail::sample_index(count, 0, 3, rng);
    auto const middle = tsl_pivot_detail::sample_index(count, 1, 3, rng);
    auto const last = tsl_pivot_detail::sample_index(count, 2, 3, rng);
    return tsl_pivot_detail::median_index_of_3(keys, first, middle, last, before);
  }
  std::array<std::size_t, 3> medians{};
  for (std::size_t group = 0; group < medians.size(); ++group) {
    auto const first = tsl_pivot_detail::sample_index(count, 3 * group, 9, rng);
    auto const middle = tsl_pivot_detail::sample_index(count, 3 * group + 1, 9, rng);
    auto const last = tsl_pivot_detail::sample_index(count, 3 * group + 2, 9, rng);
    medians[group] = tsl_pivot_detail::median_index_of_3(keys, first, middle, last, before);
  }
  return tsl_pivot_detail::median_index_of_3(
    keys,
    medians[0],
    medians[1],
    medians[2],
    before
  );
}


// The pivot value itself, for a caller that does not move the element it
// partitions around.
template <class DataType, class Before = std::less<DataType>>
auto tsl_pivot_of(
  DataType const * keys,
  std::size_t count,
  std::uint64_t seed,
  Before before = {}
) -> DataType {
  return keys[tsl_pivot_index_of(keys, count, seed, before)];
}
