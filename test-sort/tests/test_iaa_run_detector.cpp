// Differential test for the IAA run detectors against the scalar oracle.
//
// Both detectors rest on one claim that cannot be established by inspection:
// that on sorted input `scan_eq`'s popcount over the tail [cursor, region_end)
// is exactly the length of the run opening at `cursor`, so the boundaries
// derived from it -- plus one scalar comparison per region seam -- reproduce the
// scalar oracle's span set. Every case below compares a detector's full span set
// against tsl_for_each_equal_run over the same range, for both sort orders, the
// element widths QPL scan supports, and region/range shapes chosen to hit the
// seams.
//
// Runs on the QPL software path by default so it needs no accelerator. Pass `hw`
// to additionally run every case on real IAA hardware.

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <exception>
#include <mutex>
#include <random>
#include <string>
#include <vector>

#include "cluster_detection/scalar/equal_runs.hpp"
#include "cluster_detection/iaa/iaa_run_detector.hpp"

namespace {

std::size_t g_checks = 0;
std::size_t g_failures = 0;

auto spans_equal(
  std::vector<TslRunSpan> const & left,
  std::vector<TslRunSpan> const & right
) -> bool {
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

auto describe(std::vector<TslRunSpan> const & spans, std::size_t limit = 6) -> std::string {
  std::string out = "[";
  for (std::size_t index = 0; index < spans.size() && index < limit; ++index) {
    out += "(" + std::to_string(spans[index].begin) + "," + std::to_string(spans[index].end) + ")";
  }
  if (spans.size() > limit) {
    out += "...+" + std::to_string(spans.size() - limit);
  }
  return out + "]";
}

// Contract properties the oracle comparison alone would miss if both sides were
// wrong the same way.
template <class T>
auto contract_holds(
  std::string const & label,
  std::vector<T> const & values,
  std::size_t begin,
  std::size_t end,
  std::vector<TslRunSpan> const & spans
) -> bool {
  for (std::size_t index = 0; index < spans.size(); ++index) {
    auto const & span = spans[index];
    char const * problem = nullptr;
    if (span.end - span.begin < 2) {
      problem = "emitted span shorter than 2";
    } else if (span.begin < begin || span.end > end) {
      problem = "span escapes the requested range";
    } else if (index > 0 && span.begin <= spans[index - 1].begin) {
      problem = "spans not ascending";
    } else if (span.begin > begin && values[span.begin - 1] == values[span.begin]) {
      problem = "span not maximal on the left";
    } else if (span.end < end && values[span.end] == values[span.end - 1]) {
      problem = "span not maximal on the right";
    }
    if (problem != nullptr) {
      ++g_failures;
      std::printf("FAIL %s: %s\n", label.c_str(), problem);
      return false;
    }
  }
  return true;
}

template <class T>
void report(
  std::string const & label,
  TslIaaPath path,
  std::size_t region_bytes,
  std::size_t begin,
  std::size_t end,
  std::vector<TslRunSpan> const & expected,
  std::vector<TslRunSpan> const & actual
) {
  ++g_failures;
  std::printf(
    "FAIL %-46s w=%zu path=%s region=%zuB range=[%zu,%zu)\n"
    "       expected %zu spans %s\n"
    "       actual   %zu spans %s\n",
    label.c_str(), sizeof(T), tsl_iaa_path_name(path), region_bytes, begin, end,
    expected.size(), describe(expected).c_str(),
    actual.size(), describe(actual).c_str()
  );
}

// One synchronous case.
template <class T>
void check_sync(
  std::string const & label,
  std::vector<T> const & values,
  std::size_t begin,
  std::size_t end,
  TslIaaPath path,
  std::size_t region_bytes,
  std::size_t min_offload_elements = 0
) {
  ++g_checks;

  std::vector<TslRunSpan> expected;
  tsl_for_each_equal_run(values.data(), begin, end, [&](TslRunSpan span) {
    expected.push_back(span);
  });

  std::vector<TslRunSpan> actual;
  TslIaaRunDetector<T> detector(path, region_bytes, min_offload_elements);
  detector.detect(values.data(), begin, end, [&](TslRunSpan span) {
    actual.push_back(span);
  });

  if (!spans_equal(expected, actual)) {
    report<T>("sync/" + label, path, region_bytes, begin, end, expected, actual);
    return;
  }
  contract_holds(label, values, begin, end, actual);
}

// Minimal pending-work sink: the asynchronous detector needs the accounting
// interface, not a running executor, so the test drives poll() itself and only
// has to know when the outstanding count returns to zero.
struct TslCountingPendingWork : TslPendingWork {
  std::mutex mutex;
  std::size_t outstanding = 0;
  std::exception_ptr error;

  void add_pending(std::size_t count) override {
    std::lock_guard<std::mutex> lock(mutex);
    outstanding += count;
  }

  void resolve_pending(std::size_t count) override {
    std::lock_guard<std::mutex> lock(mutex);
    outstanding -= count;
  }

  void fail(std::exception_ptr raised) override {
    std::lock_guard<std::mutex> lock(mutex);
    if (!error) error = raised;
  }

  auto busy() -> bool {
    std::lock_guard<std::mutex> lock(mutex);
    return outstanding != 0;
  }
};

// One asynchronous case: hand the range over, then poll to completion.
template <class T>
void check_async(
  std::string const & label,
  std::vector<T> const & values,
  std::size_t begin,
  std::size_t end,
  TslIaaPath path,
  std::size_t region_bytes,
  std::size_t slots,
  std::size_t depth,
  std::size_t min_offload_elements = 0
) {
  ++g_checks;

  std::vector<TslRunSpan> expected;
  tsl_for_each_equal_run(values.data(), begin, end, [&](TslRunSpan span) {
    expected.push_back(span);
  });

  std::vector<TslRunSpan> actual;
  TslCountingPendingWork pending;
  {
    TslIaaAsyncRunDetector<T> detector(path, slots, depth, region_bytes, min_offload_elements);
    detector.bind(pending);
    // The sink is retained past this call, so it captures a pointer rather than
    // a reference to a frame that could go away -- the contract the sorter's
    // emit callables must also satisfy.
    auto * sink = &actual;
    detector(values.data(), begin, end, [sink](TslRunSpan span) { sink->push_back(span); });

    // Bounded so a lost completion fails the test instead of hanging it. Each
    // region needs at most one poll per run it contains.
    std::size_t polls = 0;
    auto const poll_limit = (end - begin) + 1024;
    while (pending.busy() && polls < poll_limit) {
      detector.poll();
      ++polls;
    }
    if (pending.busy()) {
      ++g_failures;
      std::printf("FAIL async/%s: still pending after %zu polls\n", label.c_str(), polls);
      return;
    }
  }
  if (pending.error) {
    ++g_failures;
    try {
      std::rethrow_exception(pending.error);
    } catch (std::exception const & raised) {
      std::printf("FAIL async/%s: detector reported %s\n", label.c_str(), raised.what());
    }
    return;
  }

  if (!spans_equal(expected, actual)) {
    report<T>("async/" + label, path, region_bytes, begin, end, expected, actual);
    return;
  }
  contract_holds(label, values, begin, end, actual);
}

// Sorted column of runs whose lengths are drawn from [1, 2*mean-1].
//
// Values must stay monotonic: the detector's correctness rests on a value
// occurring only inside its own run, and an incrementing counter cast to a
// narrow type wraps and breaks exactly that. A type's domain therefore bounds
// how many runs a range can hold -- 256 for uint8_t -- so once the distinct
// values are exhausted the final value fills the remainder as one long run.
// That is not a weaker case: it is the only sorted shape a narrow column of
// that length can take.
template <class T>
auto make_sorted_runs(std::size_t count, std::size_t mean_run, std::uint64_t seed, bool descending)
  -> std::vector<T> {
  constexpr std::uint64_t domain =
    sizeof(T) >= 8 ? ~std::uint64_t{0} : (std::uint64_t{1} << (8 * sizeof(T)));

  std::vector<T> values;
  values.reserve(count);
  std::mt19937_64 rng(seed);
  std::uniform_int_distribution<std::size_t> length_dist(1, mean_run * 2 - 1);
  std::uint64_t value = 0;
  while (values.size() < count) {
    auto const last_value = value + 1 == domain;
    auto const length = last_value ? count - values.size() : length_dist(rng);
    for (std::size_t index = 0; index < length && values.size() < count; ++index) {
      values.push_back(static_cast<T>(value));
    }
    ++value;
  }
  if (descending) {
    // Reversing a non-decreasing sequence yields a non-increasing one, which is
    // the second monotonic case the run-length argument has to cover.
    std::reverse(values.begin(), values.end());
  }
  return values;
}

template <class T>
auto make_constant(std::size_t count, T value) -> std::vector<T> {
  return std::vector<T>(count, value);
}

template <class T>
void run_width(TslIaaPath path, bool descending) {
  std::string const dir = descending ? "desc" : "asc";

  for (std::size_t region_bytes : {64u * 1024u, 8192u, 1024u}) {
    auto const region_elems = region_bytes / sizeof(T);
    std::string const tag = dir + "/region=" + std::to_string(region_bytes);

    // Cardinality sweep: from one run over everything to all-distinct. The
    // all-distinct end is also the worst case for descriptor count.
    for (std::size_t mean_run : {1u, 2u, 3u, 8u, 64u, 1000u}) {
      auto const values =
        make_sorted_runs<T>(3 * region_elems + 7, mean_run, 0x1AA + mean_run, descending);
      auto const label = tag + "/mean_run=" + std::to_string(mean_run);
      check_sync(label, values, 0, values.size(), path, region_bytes);
      check_async(label, values, 0, values.size(), path, region_bytes, 4, 4);
    }

    // One run spanning several whole regions: no boundary anywhere, so every
    // region seam has to stay un-split.
    {
      auto const values = make_constant<T>(3 * region_elems + 7, static_cast<T>(42));
      auto const label = tag + "/one-run-over-3-regions";
      check_sync(label, values, 0, values.size(), path, region_bytes);
      check_async(label, values, 0, values.size(), path, region_bytes, 4, 4);
    }

    // Range lengths straddling exact region multiples.
    for (std::size_t count : {region_elems - 1, region_elems, region_elems + 1,
                              2 * region_elems, 2 * region_elems + 1}) {
      auto const values = make_sorted_runs<T>(count, 5, 0xBEE, descending);
      auto const label = tag + "/count=" + std::to_string(count);
      check_sync(label, values, 0, values.size(), path, region_bytes);
      check_async(label, values, 0, values.size(), path, region_bytes, 2, 2);
    }

    // Sub-ranges: a detector must never look outside [begin, end), and an
    // unaligned begin shifts every region seam.
    {
      auto const values = make_sorted_runs<T>(3 * region_elems, 7, 0xCAFE, descending);
      for (std::size_t begin : {std::size_t{1}, std::size_t{3}, region_elems / 2}) {
        auto const end = values.size() - 1;
        auto const label = tag + "/sub-range@" + std::to_string(begin);
        check_sync(label, values, begin, end, path, region_bytes);
        check_async(label, values, begin, end, path, region_bytes, 2, 3);
      }
    }

    // Ranges too short to offload: the detector must fall back and still be
    // exactly right.
    for (std::size_t count : {std::size_t{2}, std::size_t{3}, std::size_t{64}}) {
      auto const values = make_sorted_runs<T>(count, 2, 0xF00D, descending);
      auto const label = tag + "/short=" + std::to_string(count);
      check_sync(label, values, 0, values.size(), path, region_bytes, 4096);
      check_async(label, values, 0, values.size(), path, region_bytes, 2, 2, 4096);
    }
  }

  // A single range slot with more work than it can hold exercises the capacity
  // fallback: correctness must not depend on a slot being free.
  {
    auto const values = make_sorted_runs<T>(40000, 9, 0x5107, descending);
    check_async(dir + "/one-slot", values, 0, values.size(), path, 8192, 1, 1);
  }
}

void run_all(TslIaaPath path) {
  std::printf("-- path %s --\n", tsl_iaa_path_name(path));
  for (bool descending : {false, true}) {
    run_width<std::uint8_t>(path, descending);
    run_width<std::uint16_t>(path, descending);
    run_width<std::uint32_t>(path, descending);
  }
}

// The descriptor budget: a range whose runs average below the floor must be
// abandoned mid-walk and finished on the CPU, without changing the span set.
void run_budget_cases(TslIaaPath path) {
  // Mean run 2 against the default floor of 8, so the budget runs out early and
  // most of the range is recovered by the scalar comparison.
  auto const values = make_sorted_runs<std::uint32_t>(200000, 2, 0xB0D9E7, false);

  check_sync("budget/mean_run=2", values, 0, values.size(), path, 64 * 1024);
  check_async("budget/mean_run=2", values, 0, values.size(), path, 64 * 1024, 2, 4);

  TslIaaRunDetector<std::uint32_t> detector(path, 64 * 1024, 0);
  std::size_t spans = 0;
  detector.detect(values.data(), 0, values.size(), [&](TslRunSpan) { ++spans; });
  auto const metrics = detector.metrics();
  ++g_checks;
  if (metrics.fallback_short_runs == 0) {
    ++g_failures;
    std::printf("FAIL budget: expected the descriptor budget to be exhausted\n");
  } else if (metrics.cpu_finished_elements == 0) {
    ++g_failures;
    std::printf("FAIL budget: no elements were recovered on the CPU\n");
  } else if (metrics.descriptors > values.size() / 8 + 1) {
    ++g_failures;
    std::printf(
      "FAIL budget: spent %zu descriptors, above the %zu allowed\n",
      metrics.descriptors, values.size() / 8 + 1
    );
  }
  // The probe must settle the verdict cheaply: a few descriptors per region, not
  // a fraction of the element count.
  ++g_checks;
  auto const probe_allowance = (metrics.regions + 1) * (tsl_iaa_probe_descriptors + 1);
  if (metrics.descriptors > probe_allowance) {
    ++g_failures;
    std::printf(
      "FAIL budget: %zu descriptors for %zu regions, above the %zu-probe allowance\n",
      metrics.descriptors, metrics.regions, probe_allowance
    );
  }

  // An all-distinct range is the pathological case: it emits no spans at all, so
  // every descriptor spent on it is wasted. The budget must cap them.
  auto const distinct = make_sorted_runs<std::uint32_t>(200000, 1, 0xD1571C7, false);
  check_sync("budget/all-distinct", distinct, 0, distinct.size(), path, 64 * 1024);
  check_async("budget/all-distinct", distinct, 0, distinct.size(), path, 64 * 1024, 2, 4);
}

// 8-byte elements have no single-scan form, so both detectors must fall back to
// the oracle rather than produce a wrong answer or throw.
void run_unsupported_width(TslIaaPath path) {
  auto const values = make_sorted_runs<std::uint64_t>(20000, 6, 0x64B17, false);
  check_sync("u64/falls-back", values, 0, values.size(), path, 8192);
  check_async("u64/falls-back", values, 0, values.size(), path, 8192, 4, 4);

  TslIaaRunDetector<std::uint64_t> detector(path, 8192, 0);
  detector.detect(values.data(), 0, values.size(), [](TslRunSpan) {});
  if (detector.metrics().fallback_width == 0) {
    ++g_failures;
    std::printf("FAIL u64: expected the width fallback to be reported\n");
  }
  if (detector.metrics().descriptors != 0) {
    ++g_failures;
    std::printf("FAIL u64: no descriptor may be issued for an 8-byte element\n");
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
    run_all(TslIaaPath::SOFTWARE);
    run_budget_cases(TslIaaPath::SOFTWARE);
    run_unsupported_width(TslIaaPath::SOFTWARE);

    if (want_hardware) {
      run_all(TslIaaPath::HARDWARE);
      run_budget_cases(TslIaaPath::HARDWARE);
      run_unsupported_width(TslIaaPath::HARDWARE);
    } else {
      std::printf("-- path iaa_hw skipped (pass 'hw' to include it) --\n");
    }
  } catch (std::exception const & raised) {
    std::printf("\nIAA run detector tests ABORTED: %s\n", raised.what());
    return 1;
  }

  if (g_failures != 0) {
    std::printf("\nIAA run detector tests FAILED: %zu of %zu checks\n", g_failures, g_checks);
    return 1;
  }
  std::printf("\nIAA run detector tests passed (%zu checks)\n", g_checks);
  return 0;
}
