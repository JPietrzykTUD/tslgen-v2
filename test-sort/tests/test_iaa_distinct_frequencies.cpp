// Differential test for the IAA distinct-frequency counter against a CPU tally.
//
// The counter rests on two claims that cannot be established by inspection: that
// `scan_eq`'s popcount over a range is the frequency of the pivot in it, and
// that `scan_lt`/`scan_gt` plus `select` split the rest into two ranges which
// together hold every remaining element exactly once. Either failing shows up as
// a wrong count or a missing value, so every case below compares the full map
// against std::unordered_map counting over the same range, across the element
// widths QPL scan supports, both signednesses, and the input shapes that decide
// the recursion depth -- sorted, reverse sorted, uniform, all distinct, organ
// pipe, and heavily skewed.
//
// It also asserts the cost properties the design exists for: descriptors stay
// proportional to the distinct count rather than the element count, and the CPU
// never tallies a significant fraction of the range.
//
// Runs on the QPL software path by default so it needs no accelerator. Pass `hw`
// to additionally run every case on real IAA hardware.

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <exception>
#include <limits>
#include <random>
#include <span>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <typeinfo>
#include <unordered_map>
#include <vector>

#include "cluster_detection/iaa/iaa_distinct_frequencies.hpp"

namespace {

std::size_t g_checks = 0;
std::size_t g_failures = 0;

template <class T>
auto tally(std::vector<T> const & values) -> std::unordered_map<T, std::size_t> {
  std::unordered_map<T, std::size_t> counts;
  for (auto const value : values) {
    ++counts[value];
  }
  return counts;
}

template <class T>
void fail(std::string const & label, std::string const & problem) {
  ++g_failures;
  std::printf("FAIL %s [%s]: %s\n", label.c_str(), typeid(T).name(), problem.c_str());
}

// Compares the counter's map against the oracle's, and reports the cost
// properties of the walk that produced it.
template <class T>
void check(
  std::string const & label,
  std::vector<T> const & values,
  TslIaaFrequencyPath path,
  TslIaaFrequencyOptions options = {}
) {
  options.path = path;
  auto const expected = tally(values);

  TslIaaDistinctFrequencies<T> counter(options);
  auto const produced = counter.count(values.data(), values.size());
  auto const metrics = counter.metrics();

  ++g_checks;
  if (produced.size() != expected.size()) {
    fail<T>(
      label,
      "distinct count " + std::to_string(produced.size()) + ", expected "
        + std::to_string(expected.size())
    );
    return;
  }
  for (auto const & entry : expected) {
    auto const found = produced.find(entry.first);
    if (found == produced.end()) {
      fail<T>(label, "value " + std::to_string(+entry.first) + " missing");
      return;
    }
    if (found->second != entry.second) {
      fail<T>(
        label,
        "value " + std::to_string(+entry.first) + " counted " + std::to_string(found->second)
          + ", expected " + std::to_string(entry.second)
      );
      return;
    }
  }

  if (metrics.fallback_small != 0 || metrics.fallback_width != 0
      || metrics.fallback_disabled != 0) {
    return;  // a CPU tally has no accelerator cost to assert
  }

  // Every node resolves at least one distinct value, so the walk cannot visit
  // more nodes than the answer has entries. This is the property that separates
  // the three-way partition from the O(n * distinct) formulation.
  auto const per_region = expected.size() * metrics.regions + metrics.regions;
  ++g_checks;
  if (metrics.nodes > per_region) {
    fail<T>(
      label,
      "visited " + std::to_string(metrics.nodes) + " nodes for "
        + std::to_string(expected.size()) + " distinct values in "
        + std::to_string(metrics.regions) + " regions"
    );
  }
  // Exactly one scan_eq per node the accelerator resolved, and at most two
  // partition scans on top of it.
  ++g_checks;
  if (metrics.equality_scans + metrics.scalar_leaves != metrics.nodes) {
    fail<T>(
      label,
      std::to_string(metrics.equality_scans) + " equality scans plus "
        + std::to_string(metrics.scalar_leaves) + " scalar leaves over "
        + std::to_string(metrics.nodes) + " nodes"
    );
  }
  ++g_checks;
  if (metrics.pivot_scans > 2 * metrics.equality_scans) {
    fail<T>(
      label,
      std::to_string(metrics.pivot_scans) + " partition scans over "
        + std::to_string(metrics.equality_scans) + " equality scans"
    );
  }
  ++g_checks;
  auto const select_allowance =
    2 * metrics.nodes + metrics.scanned_elements / options.select_block_elements + 2;
  if (metrics.selects > select_allowance) {
    fail<T>(
      label,
      std::to_string(metrics.selects) + " selects, above the allowance of "
        + std::to_string(select_allowance)
    );
  }
  // Elements read must grow with log(distinct), not with distinct. Measured at
  // about 4.7 * log2(distinct) reads per element; the allowance leaves room for
  // pivot luck while still rejecting a walk that degenerated to one pass per
  // distinct value.
  ++g_checks;
  auto const depth_allowance = 32.0 * std::log2(static_cast<double>(expected.size()) + 2.0);
  auto const read_allowance =
    static_cast<std::size_t>(depth_allowance * static_cast<double>(values.size())) + 64;
  if (metrics.scanned_elements > read_allowance) {
    fail<T>(
      label,
      "read " + std::to_string(metrics.scanned_elements) + " elements over "
        + std::to_string(values.size()) + ", above the allowance of "
        + std::to_string(read_allowance)
    );
  }
  // The CPU may resolve small leaves, but never a meaningful share of the range.
  ++g_checks;
  auto const scalar_allowance = options.scalar_leaf_elements * per_region;
  if (metrics.scalar_elements > scalar_allowance) {
    fail<T>(
      label,
      "the CPU tallied " + std::to_string(metrics.scalar_elements) + " of "
        + std::to_string(values.size()) + " elements, above the allowance of "
        + std::to_string(scalar_allowance)
    );
  }
}

// -----------------------------------------------------------------------------
// Shapes
// -----------------------------------------------------------------------------

template <class T>
auto spread(std::uint64_t index, std::uint64_t distinct) -> T {
  // Keeps the values inside the type's range while staying wide apart, so the
  // partition cannot rely on a dense value domain.
  using Raw = std::make_unsigned_t<T>;
  auto const span = static_cast<std::uint64_t>(std::numeric_limits<Raw>::max()) + 1;
  auto const step = std::max<std::uint64_t>(1, span / std::max<std::uint64_t>(distinct, 1));
  auto const raw = static_cast<Raw>((index % std::max<std::uint64_t>(distinct, 1)) * step);
  T value;
  std::memcpy(&value, &raw, sizeof(value));
  return value;
}

template <class T>
auto make_uniform(std::size_t count) -> std::vector<T> {
  return std::vector<T>(count, spread<T>(3, 8));
}

template <class T>
auto make_distinct(std::size_t count) -> std::vector<T> {
  std::vector<T> values(count);
  for (std::size_t index = 0; index < count; ++index) {
    values[index] = spread<T>(index, count);
  }
  return values;
}

template <class T>
auto make_random(std::size_t count, std::size_t distinct, std::uint32_t seed) -> std::vector<T> {
  std::mt19937 engine(seed);
  std::uniform_int_distribution<std::uint64_t> pick(0, distinct - 1);
  std::vector<T> values(count);
  for (auto & value : values) {
    value = spread<T>(pick(engine), distinct);
  }
  return values;
}

// Zipf-like: one value dominates, the tail is rare. The shape where a pivot that
// splits by element count still has to reach the rare values.
template <class T>
auto make_skewed(std::size_t count, std::size_t distinct, std::uint32_t seed) -> std::vector<T> {
  std::mt19937 engine(seed);
  std::vector<T> values(count);
  for (auto & value : values) {
    auto const rank = static_cast<std::uint64_t>(engine() % (distinct * distinct));
    value = spread<T>(static_cast<std::uint64_t>(std::sqrt(static_cast<double>(rank))), distinct);
  }
  return values;
}

// Ascending, descending, and up-then-down: the orderings a first-element pivot
// degenerates on.
template <class T>
auto make_organ_pipe(std::size_t count, std::size_t distinct) -> std::vector<T> {
  std::vector<T> values(count);
  for (std::size_t index = 0; index < count; ++index) {
    auto const position = index < count / 2 ? index : count - index - 1;
    values[index] = spread<T>(position % distinct, distinct);
  }
  return values;
}

template <class T>
void run_width(TslIaaFrequencyPath path) {
  std::string const name = std::string("w") + std::to_string(sizeof(T))
                         + (std::is_signed_v<T> ? "s" : "u");
  auto const distinct_cap = sizeof(T) == 1 ? std::size_t{200} : std::size_t{4096};

  check<T>(name + "/uniform", make_uniform<T>(50000), path);
  check<T>(name + "/random", make_random<T>(50000, distinct_cap, 0x51A7), path);
  check<T>(name + "/skewed", make_skewed<T>(50000, sizeof(T) == 1 ? 12 : 64, 0x2E1F), path);
  check<T>(name + "/organ-pipe", make_organ_pipe<T>(50000, distinct_cap), path);

  {
    auto ascending = make_random<T>(50000, distinct_cap, 0xA5CE);
    std::sort(ascending.begin(), ascending.end());
    check<T>(name + "/sorted", ascending, path);
    std::reverse(ascending.begin(), ascending.end());
    check<T>(name + "/reversed", ascending, path);
  }

  // All distinct is the pathological cardinality: every node resolves one value
  // and the map is as large as the range.
  check<T>(name + "/all-distinct", make_distinct<T>(sizeof(T) == 1 ? 256 : 20000), path,
           TslIaaFrequencyOptions{path, tsl_iaa_frequency_default_region_elements, 128, 8});

  // Two values only, as far apart as the type allows: the split has to be by a
  // value that is present, not by the midpoint of the domain.
  {
    std::vector<T> pair(30000);
    for (std::size_t index = 0; index < pair.size(); ++index) {
      pair[index] = index % 3 == 0 ? spread<T>(0, 1) : spread<T>(1, 2);
    }
    check<T>(name + "/two-values", pair, path);
  }

  // Regions: frequencies must add across them, and a value in several regions
  // must land in one entry.
  {
    auto const values = make_random<T>(40000, sizeof(T) == 1 ? 40 : 300, 0xBEEF);
    check<T>(name + "/regions", values, path,
             TslIaaFrequencyOptions{path, 4096, 128, 8});
  }

  // A leaf threshold of 1 leaves everything but a single element to the
  // accelerator; a large one hands whole nodes to the CPU. Both must agree.
  {
    auto const values = make_random<T>(20000, sizeof(T) == 1 ? 30 : 500, 0x1EAF);
    check<T>(name + "/leaf=1", values, path,
             TslIaaFrequencyOptions{path, tsl_iaa_frequency_default_region_elements, 128, 1});
    check<T>(name + "/leaf=512", values, path,
             TslIaaFrequencyOptions{path, tsl_iaa_frequency_default_region_elements, 128, 512});
  }

  // The answer must not depend on how many nodes are in flight.
  {
    auto const values = make_random<T>(30000, sizeof(T) == 1 ? 50 : 350, 0xF117);
    for (std::size_t slots : {std::size_t{1}, std::size_t{2}, std::size_t{32}}) {
      TslIaaFrequencyOptions options;
      options.region_elements = tsl_iaa_frequency_default_region_elements;
      options.min_offload_elements = 128;
      options.in_flight_descriptors = slots;
      check<T>(name + "/in-flight=" + std::to_string(slots), values, path, options);
    }
  }

  // A tiny select block turns every compaction into many jobs; the result must
  // not depend on how a compaction was cut up.
  {
    auto const values = make_random<T>(30000, sizeof(T) == 1 ? 60 : 400, 0xB10C);
    check<T>(name + "/select-block=64", values, path,
             TslIaaFrequencyOptions{path, tsl_iaa_frequency_default_region_elements, 128, 8, 64});
  }

  // Shapes around the region and mask boundaries.
  for (std::size_t count : {1u, 2u, 3u, 7u, 8u, 9u, 63u, 64u, 65u, 4095u, 4096u, 4097u}) {
    check<T>(name + "/n=" + std::to_string(count), make_random<T>(count, 7, static_cast<std::uint32_t>(0x99 + count)), path,
             TslIaaFrequencyOptions{path, 512, 1, 8});
  }
}

void run_all(TslIaaFrequencyPath path) {
  std::printf("-- path %s --\n", tsl_iaa_frequency_path_name(path));
  run_width<std::uint8_t>(path);
  run_width<std::int8_t>(path);
  run_width<std::uint16_t>(path);
  run_width<std::int16_t>(path);
  run_width<std::uint32_t>(path);
  run_width<std::int32_t>(path);
}

// 8-byte elements have no single-scan form, so the counter must fall back to a
// CPU tally rather than produce a wrong answer or throw.
void run_unsupported_width(TslIaaFrequencyPath path) {
  auto const values = make_random<std::uint64_t>(20000, 500, 0x64B17);
  check<std::uint64_t>("u64/falls-back", values, path);

  TslIaaFrequencyOptions options;
  options.path = path;
  TslIaaDistinctFrequencies<std::uint64_t> counter(options);
  auto const produced = counter.count(values.data(), values.size());
  ++g_checks;
  if (counter.metrics().fallback_width == 0) {
    fail<std::uint64_t>("u64", "expected the width fallback to be reported");
  }
  ++g_checks;
  if (counter.metrics().descriptors() != 0) {
    fail<std::uint64_t>("u64", "no descriptor may be issued for an 8-byte element");
  }
  ++g_checks;
  if (produced != tally(values)) {
    fail<std::uint64_t>("u64", "the fallback tally disagrees with the oracle");
  }
}

// A range below the offload threshold, and an empty one.
void run_small_ranges(TslIaaFrequencyPath path) {
  TslIaaFrequencyOptions options;
  options.path = path;
  options.min_offload_elements = 4096;

  auto const values = make_random<std::uint32_t>(1000, 50, 0x5A11);
  TslIaaDistinctFrequencies<std::uint32_t> counter(options);
  auto const produced = counter.count(values.data(), values.size());
  ++g_checks;
  if (counter.metrics().fallback_small == 0 || counter.metrics().descriptors() != 0) {
    fail<std::uint32_t>("small", "a range below the threshold must not reach a descriptor");
  }
  ++g_checks;
  if (produced != tally(values)) {
    fail<std::uint32_t>("small", "the fallback tally disagrees with the oracle");
  }

  ++g_checks;
  if (!counter.count(values.data(), 0).empty()) {
    fail<std::uint32_t>("empty", "an empty range must produce an empty map");
  }
}

// The non-blocking surface. Three claims: the caller's own work interleaves with
// the walk, more slots turn the same descriptors into fewer sweeps -- which is
// the whole point, since a sweep is where a hardware round trip would be waited
// out -- and the guards refuse a misuse rather than answering wrongly.
void run_pipeline(TslIaaFrequencyPath path) {
  auto const values = make_random<std::uint32_t>(100000, 2048, 0x9198);
  auto const expected = tally(values);

  std::size_t previous_polls = 0;
  for (std::size_t slots : {std::size_t{1}, std::size_t{4}, std::size_t{16}}) {
    TslIaaFrequencyOptions options;
    options.path = path;
    options.min_offload_elements = 128;
    options.in_flight_descriptors = slots;
    TslIaaDistinctFrequencies<std::uint32_t> counter(options);

    std::size_t polls = 0;
    std::size_t interleaved = 0;
    counter.start(values.data(), values.size());
    while (!counter.poll()) {
      ++polls;
      interleaved += polls % 7;  // stands in for the caller's own work
    }
    auto const produced = counter.take();
    auto const metrics = counter.metrics();

    ++g_checks;
    if (produced != expected) {
      fail<std::uint32_t>("pipeline/slots=" + std::to_string(slots), "disagrees with the oracle");
    }
    ++g_checks;
    if (polls == 0 || interleaved == 0) {
      fail<std::uint32_t>(
        "pipeline/slots=" + std::to_string(slots),
        "the walk finished without ever returning to the caller"
      );
    }
    // Every slot must actually be used, or the pipeline is decoration.
    ++g_checks;
    if (metrics.max_in_flight != slots) {
      fail<std::uint32_t>(
        "pipeline/slots=" + std::to_string(slots),
        "peak in flight " + std::to_string(metrics.max_in_flight) + ", expected "
          + std::to_string(slots)
      );
    }
    // Sweeps must fall roughly in proportion to the slot count. Four times the
    // slots against half the sweeps is a loose bound that still fails outright
    // if the chains stopped overlapping.
    ++g_checks;
    if (previous_polls != 0 && polls > previous_polls / 2) {
      fail<std::uint32_t>(
        "pipeline/slots=" + std::to_string(slots),
        std::to_string(polls) + " sweeps against " + std::to_string(previous_polls)
          + " at a quarter of the slots"
      );
    }
    previous_polls = polls;
  }

  // start() while a walk is open, and take() before it closed, are misuse.
  {
    TslIaaFrequencyOptions options;
    options.path = path;
    options.min_offload_elements = 128;
    TslIaaDistinctFrequencies<std::uint32_t> counter(options);
    counter.start(values.data(), values.size());
    bool refused_start = false;
    bool refused_take = false;
    try {
      counter.start(values.data(), values.size());
    } catch (std::logic_error const &) {
      refused_start = true;
    }
    try {
      (void)counter.take();
    } catch (std::logic_error const &) {
      refused_take = true;
    }
    ++g_checks;
    if (!refused_start || !refused_take) {
      fail<std::uint32_t>("pipeline/guards", "a misuse was accepted");
    }
    while (!counter.poll()) {
    }
    ++g_checks;
    if (counter.take() != expected) {
      fail<std::uint32_t>("pipeline/guards", "the walk did not survive the refusals");
    }
  }

  // A counter dropped mid-walk must wait its descriptors out rather than leave
  // them writing into a freed completion record.
  {
    TslIaaFrequencyOptions options;
    options.path = path;
    options.min_offload_elements = 128;
    TslIaaDistinctFrequencies<std::uint32_t> counter(options);
    counter.start(values.data(), values.size());
    counter.poll();
    ++g_checks;  // the destructor below is the check; a leak or crash fails it
  }
}

// The requested entry point: a span in, a map out.
void run_span_entry_point(TslIaaFrequencyPath path) {
  auto values = make_random<std::uint32_t>(20000, 300, 0x5A0F);
  TslIaaFrequencyOptions options;
  options.path = path;
  options.min_offload_elements = 128;

  std::unordered_map<std::uint32_t, std::size_t> const mutable_span =
    distinct_frequencies(std::span<std::uint32_t>(values), options);
  std::unordered_map<std::uint32_t, std::size_t> const const_span =
    distinct_frequencies(std::span<std::uint32_t const>(values), options);

  ++g_checks;
  if (mutable_span != tally(values) || const_span != tally(values)) {
    fail<std::uint32_t>("span", "the span entry point disagrees with the oracle");
  }
}

}  // namespace

int main(int argc, char ** argv) {
  bool want_hardware = false;
  for (int index = 1; index < argc; ++index) {
    if (std::strcmp(argv[index], "hw") == 0) {
      want_hardware = true;
    }
  }

  try {
    run_all(TslIaaFrequencyPath::SOFTWARE);
    run_unsupported_width(TslIaaFrequencyPath::SOFTWARE);
    run_small_ranges(TslIaaFrequencyPath::SOFTWARE);
    run_pipeline(TslIaaFrequencyPath::SOFTWARE);
    run_span_entry_point(TslIaaFrequencyPath::SOFTWARE);

    if (want_hardware) {
      run_all(TslIaaFrequencyPath::HARDWARE);
      run_unsupported_width(TslIaaFrequencyPath::HARDWARE);
      run_small_ranges(TslIaaFrequencyPath::HARDWARE);
      run_pipeline(TslIaaFrequencyPath::HARDWARE);
      run_span_entry_point(TslIaaFrequencyPath::HARDWARE);
    } else {
      std::printf("-- path iaa_hw skipped (pass 'hw' to include it) --\n");
    }
  } catch (std::exception const & raised) {
    std::printf("\nIAA distinct-frequency tests ABORTED: %s\n", raised.what());
    return 1;
  }

  if (g_failures != 0) {
    std::printf(
      "\nIAA distinct-frequency tests FAILED: %zu of %zu checks\n", g_failures, g_checks
    );
    return 1;
  }
  std::printf("\nIAA distinct-frequency tests passed (%zu checks)\n", g_checks);
  return 0;
}
