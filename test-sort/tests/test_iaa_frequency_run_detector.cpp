// Differential test for the frequency-based run detector.
//
// The claim under test is that on a sorted range the multiplicity of a value is
// the length of its run, so a value->count map found on the *unsorted* range
// reproduces the scalar oracle's span set exactly. Every case therefore prepares
// on the unsorted data, sorts, detects, and demands the same spans
// `tsl_for_each_equal_run` produces.
//
// The three ways the fast path can be unavailable are checked too, because each
// has to degrade rather than mislead: a range nobody prepared, a range prepared
// with different bounds, and a range prepared from different data.
//
// Runs on the QPL software path, so it needs no accelerator. The counts are the
// same either way -- the path decides who computes them, not what they are.

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <random>
#include <string>
#include <vector>

#include "cluster_detection/scalar/equal_runs.hpp"
#include "cluster_detection/iaa/iaa_frequency_run_detector.hpp"

namespace {

std::size_t g_checks = 0;
std::size_t g_failures = 0;

auto spans_equal(std::vector<TslRunSpan> const & left,
                 std::vector<TslRunSpan> const & right) -> bool {
  if (left.size() != right.size()) {
    return false;
  }
  for (std::size_t index = 0; index < left.size(); ++index) {
    if (left[index].begin != right[index].begin || left[index].end != right[index].end) {
      return false;
    }
  }
  return true;
}

auto describe(std::vector<TslRunSpan> const & spans, std::size_t limit = 5) -> std::string {
  std::string out = "[";
  for (std::size_t index = 0; index < spans.size() && index < limit; ++index) {
    out += "(" + std::to_string(spans[index].begin) + "," + std::to_string(spans[index].end) + ")";
  }
  if (spans.size() > limit) {
    out += "...+" + std::to_string(spans.size() - limit);
  }
  return out + "]";
}

template <class T>
auto values_with(std::size_t count, std::size_t cardinality, std::uint64_t seed)
  -> std::vector<T> {
  std::vector<T> values(count);
  std::mt19937_64 rng(seed);
  std::uniform_int_distribution<std::uint64_t> dist(0, std::max<std::size_t>(cardinality, 1) - 1);
  for (auto & value : values) {
    value = static_cast<T>(dist(rng));
  }
  return values;
}

auto software_options() -> TslIaaFrequencyOptions {
  TslIaaFrequencyOptions options;
  options.path = TslIaaFrequencyPath::SOFTWARE;
  return options;
}

// prepare on the unsorted range, sort, detect: the sequence a sorter performs.
template <class T>
void check(std::string const & label, std::vector<T> values, std::size_t min_prepare = 0) {
  ++g_checks;
  TslIaaFrequencyRunDetector<T> detector(software_options(), min_prepare);
  detector.prepare(values.data(), 0, values.size());
  std::sort(values.begin(), values.end());

  std::vector<TslRunSpan> expected;
  tsl_for_each_equal_run(values.data(), 0, values.size(), [&](TslRunSpan span) {
    expected.push_back(span);
  });
  std::vector<TslRunSpan> actual;
  detector.detect(values.data(), 0, values.size(), [&](TslRunSpan span) {
    actual.push_back(span);
  });

  if (!spans_equal(expected, actual)) {
    ++g_failures;
    std::printf("FAIL %-40s w=%zu n=%zu\n       expected %zu %s\n       actual   %zu %s\n",
                label.c_str(), sizeof(T), values.size(),
                expected.size(), describe(expected).c_str(),
                actual.size(), describe(actual).c_str());
    return;
  }
  // Spans must also be maximal and ascending, which a matching oracle would not
  // catch if both walked the same wrong way.
  for (std::size_t index = 0; index < actual.size(); ++index) {
    auto const & span = actual[index];
    char const * problem = nullptr;
    if (span.end - span.begin < 2) {
      problem = "span shorter than 2";
    } else if (index > 0 && span.begin < actual[index - 1].end) {
      problem = "spans overlap or are unordered";
    } else if (span.begin > 0 && values[span.begin - 1] == values[span.begin]) {
      problem = "span not maximal on the left";
    } else if (span.end < values.size() && values[span.end] == values[span.end - 1]) {
      problem = "span not maximal on the right";
    }
    if (problem != nullptr) {
      ++g_failures;
      std::printf("FAIL %s: %s\n", label.c_str(), problem);
      return;
    }
  }
}

// A sub-range of a larger buffer: the bounds the sorters actually pass.
template <class T>
void check_subrange(std::string const & label, std::size_t count, std::size_t cardinality,
                    std::size_t begin, std::size_t end) {
  ++g_checks;
  auto values = values_with<T>(count, cardinality, 0x50B1 ^ begin);
  TslIaaFrequencyRunDetector<T> detector(software_options(), 0);
  detector.prepare(values.data(), begin, end);
  std::sort(values.begin() + begin, values.begin() + end);

  std::vector<TslRunSpan> expected;
  tsl_for_each_equal_run(values.data(), begin, end, [&](TslRunSpan span) {
    expected.push_back(span);
  });
  std::vector<TslRunSpan> actual;
  detector.detect(values.data(), begin, end, [&](TslRunSpan span) { actual.push_back(span); });

  if (!spans_equal(expected, actual)) {
    ++g_failures;
    std::printf("FAIL %s: sub-range [%zu,%zu) of %zu\n       expected %zu %s\n"
                "       actual   %zu %s\n",
                label.c_str(), begin, end, count,
                expected.size(), describe(expected).c_str(),
                actual.size(), describe(actual).c_str());
  }
}

// Each way the fast path can be unavailable has to fall back, not mislead.
template <class T>
void check_fallbacks() {
  auto const source = values_with<T>(20000, 32, 0xFA11);

  // 1. never prepared
  {
    ++g_checks;
    auto values = source;
    std::sort(values.begin(), values.end());
    TslIaaFrequencyRunDetector<T> detector(software_options(), 0);
    std::vector<TslRunSpan> expected;
    tsl_for_each_equal_run(values.data(), 0, values.size(),
                           [&](TslRunSpan span) { expected.push_back(span); });
    std::vector<TslRunSpan> actual;
    detector.detect(values.data(), 0, values.size(),
                    [&](TslRunSpan span) { actual.push_back(span); });
    if (!spans_equal(expected, actual) || detector.metrics().fallback_unprepared != 1) {
      ++g_failures;
      std::printf("FAIL fallback/unprepared: %zu spans vs %zu, fallbacks=%zu\n",
                  actual.size(), expected.size(), detector.metrics().fallback_unprepared);
    }
  }

  // 2. prepared with different bounds
  {
    ++g_checks;
    auto values = source;
    TslIaaFrequencyRunDetector<T> detector(software_options(), 0);
    detector.prepare(values.data(), 0, values.size() / 2);
    std::sort(values.begin(), values.end());
    std::vector<TslRunSpan> expected;
    tsl_for_each_equal_run(values.data(), 0, values.size(),
                           [&](TslRunSpan span) { expected.push_back(span); });
    std::vector<TslRunSpan> actual;
    detector.detect(values.data(), 0, values.size(),
                    [&](TslRunSpan span) { actual.push_back(span); });
    if (!spans_equal(expected, actual) || detector.metrics().fallback_unprepared != 1) {
      ++g_failures;
      std::printf("FAIL fallback/other-bounds: %zu spans vs %zu, fallbacks=%zu\n",
                  actual.size(), expected.size(), detector.metrics().fallback_unprepared);
    }
  }

  // 3. prepared from data that does not match the range it is asked about. The
  //    counts then describe a different multiset, which the walk has to notice
  //    rather than emit a span running past a boundary.
  {
    ++g_checks;
    auto prepared = values_with<T>(20000, 32, 0xBAD1);
    auto values = values_with<T>(20000, 7, 0xBAD2);
    TslIaaFrequencyRunDetector<T> detector(software_options(), 0);
    detector.prepare(prepared.data(), 0, prepared.size());
    std::sort(values.begin(), values.end());
    std::vector<TslRunSpan> expected;
    tsl_for_each_equal_run(values.data(), 0, values.size(),
                           [&](TslRunSpan span) { expected.push_back(span); });
    std::vector<TslRunSpan> actual;
    detector.detect(values.data(), 0, values.size(),
                    [&](TslRunSpan span) { actual.push_back(span); });
    if (!spans_equal(expected, actual)) {
      ++g_failures;
      std::printf("FAIL fallback/mismatched-data: %zu spans vs %zu (mismatch=%zu)\n",
                  actual.size(), expected.size(), detector.metrics().fallback_mismatch);
    }
  }

  // 4. below the prepare threshold: prepare declines, detect still correct
  {
    ++g_checks;
    auto values = values_with<T>(600, 8, 0x5A11);
    TslIaaFrequencyRunDetector<T> detector(software_options(), 4096);
    detector.prepare(values.data(), 0, values.size());
    std::sort(values.begin(), values.end());
    std::vector<TslRunSpan> expected;
    tsl_for_each_equal_run(values.data(), 0, values.size(),
                           [&](TslRunSpan span) { expected.push_back(span); });
    std::vector<TslRunSpan> actual;
    detector.detect(values.data(), 0, values.size(),
                    [&](TslRunSpan span) { actual.push_back(span); });
    if (!spans_equal(expected, actual) || detector.metrics().prepared_ranges != 0) {
      ++g_failures;
      std::printf("FAIL fallback/below-threshold: %zu spans vs %zu, prepared=%zu\n",
                  actual.size(), expected.size(), detector.metrics().prepared_ranges);
    }
  }
}

template <class T>
void run_width(char const * width) {
  std::string const tag = std::string(width) + "/";

  // Cardinality sweep: one value over everything, through all-distinct. The
  // all-distinct end is the case where every run has length one and the map
  // resolves nothing useful.
  for (std::size_t cardinality : {std::size_t{1}, std::size_t{2}, std::size_t{7},
                                  std::size_t{64}, std::size_t{1024}, std::size_t{100000}}) {
    check<T>(tag + "card=" + std::to_string(cardinality),
             values_with<T>(20000, cardinality, 0xC0DE ^ cardinality));
  }

  // Sizes around the offload threshold and small enough to be handled inline.
  for (std::size_t count : {std::size_t{2}, std::size_t{3}, std::size_t{17},
                            std::size_t{4095}, std::size_t{4096}, std::size_t{4097},
                            std::size_t{65537}}) {
    check<T>(tag + "n=" + std::to_string(count), values_with<T>(count, 16, 0xBEEF ^ count));
  }

  // One value: a single run over the whole range.
  check<T>(tag + "all-equal", std::vector<T>(10000, static_cast<T>(42)));

  // Sub-ranges, including one that starts unaligned.
  check_subrange<T>(tag + "sub/aligned", 30000, 24, 0, 20000);
  check_subrange<T>(tag + "sub/offset", 30000, 24, 1, 20001);
  check_subrange<T>(tag + "sub/tail", 30000, 24, 9999, 30000);

  check_fallbacks<T>();
}

}  // namespace

int main() {
  std::printf("-- frequency run detector, QPL software path --\n");
  run_width<std::uint8_t>("u8");
  run_width<std::uint16_t>("u16");
  run_width<std::uint32_t>("u32");
  // 8-byte elements have no scan form; the counter tallies them on the CPU and
  // the detector must still be exactly right.
  run_width<std::uint64_t>("u64");

  if (g_failures != 0) {
    std::printf("\nfrequency run detector tests FAILED: %zu of %zu checks\n",
                g_failures, g_checks);
    return 1;
  }
  std::printf("\nfrequency run detector tests passed (%zu checks)\n", g_checks);
  return 0;
}
