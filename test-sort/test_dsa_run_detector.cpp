// Differential test for the DSA run detector against the scalar oracle.
//
// The detector's correctness rests on one claim that cannot be established by
// inspection: that comparing sorted data against itself shifted by one 8-byte
// block fires exactly the blocks containing a run boundary. Every case below
// therefore compares the detector's full span set against
// tsl_for_each_equal_run over the same range, for both sort orders, all four
// element widths, and region/range shapes chosen to hit the seams.
//
// Runs on the DML software path by default so it needs no accelerator. Pass
// `hw` to additionally run every case on real DSA hardware.

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <functional>
#include <random>
#include <string>
#include <vector>

#include "dsa_run_detector.hpp"
#include "equal_runs.hpp"

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

// One case: run the detector over [begin, end) and demand the exact span set
// the scalar oracle produces.
template <class T>
void check(
  std::string const & label,
  std::vector<T> const & values,
  std::size_t begin,
  std::size_t end,
  TslRleBackend backend,
  std::size_t region_bytes,
  std::size_t min_offload_elements = 0
) {
  ++g_checks;

  std::vector<TslRunSpan> expected;
  tsl_for_each_equal_run(values.data(), begin, end, [&](TslRunSpan span) {
    expected.push_back(span);
  });

  std::vector<TslRunSpan> actual;
  TslDsaRunDetector<T> detector(backend, region_bytes, min_offload_elements);
  detector.detect(values.data(), begin, end, [&](TslRunSpan span) {
    actual.push_back(span);
  });

  if (!spans_equal(expected, actual)) {
    ++g_failures;
    std::printf(
      "FAIL %-46s w=%zu backend=%s region=%zuB range=[%zu,%zu)\n"
      "       expected %zu spans %s\n"
      "       actual   %zu spans %s\n",
      label.c_str(), sizeof(T), tsl_rle_backend_name(backend), region_bytes, begin, end,
      expected.size(), describe(expected).c_str(),
      actual.size(), describe(actual).c_str()
    );
    return;
  }

  // Contract checks the oracle comparison alone would not catch if both were
  // wrong the same way.
  for (std::size_t index = 0; index < actual.size(); ++index) {
    auto const & span = actual[index];
    if (span.end - span.begin < 2) {
      ++g_failures;
      std::printf("FAIL %s: emitted span shorter than 2\n", label.c_str());
      return;
    }
    if (span.begin < begin || span.end > end) {
      ++g_failures;
      std::printf("FAIL %s: span escapes the requested range\n", label.c_str());
      return;
    }
    if (index > 0 && span.begin <= actual[index - 1].begin) {
      ++g_failures;
      std::printf("FAIL %s: spans not ascending\n", label.c_str());
      return;
    }
    // Maximality: the elements bracketing a run must differ from it.
    if (span.begin > begin && values[span.begin - 1] == values[span.begin]) {
      ++g_failures;
      std::printf("FAIL %s: span not maximal on the left\n", label.c_str());
      return;
    }
    if (span.end < end && values[span.end] == values[span.end - 1]) {
      ++g_failures;
      std::printf("FAIL %s: span not maximal on the right\n", label.c_str());
      return;
    }
  }
}

// Sorted column of runs whose lengths are drawn from [1, 2*mean-1].
template <class T>
auto make_sorted_runs(std::size_t count, std::size_t mean_run, std::uint64_t seed, bool descending)
  -> std::vector<T> {
  std::vector<T> values;
  values.reserve(count);
  std::mt19937_64 rng(seed);
  std::uniform_int_distribution<std::size_t> length_dist(1, mean_run * 2 - 1);
  std::uint64_t value = 0;
  while (values.size() < count) {
    auto const length = length_dist(rng);
    for (std::size_t index = 0; index < length && values.size() < count; ++index) {
      values.push_back(static_cast<T>(value));
    }
    ++value;
  }
  if (descending) {
    // Reversing a non-decreasing sequence yields a non-increasing one; run
    // structure is preserved, which is exactly the second monotonic case the
    // block-shift argument has to cover.
    std::reverse(values.begin(), values.end());
  }
  return values;
}

template <class T>
auto make_constant(std::size_t count, T value) -> std::vector<T> {
  return std::vector<T>(count, value);
}

template <class T>
void run_width(TslRleBackend backend, bool descending) {
  constexpr std::size_t g = 8u / sizeof(T);
  std::string const dir = descending ? "desc" : "asc";

  for (std::size_t region_bytes : {64u * 1024u, 8192u, 1024u}) {
    auto const region_elems = region_bytes / sizeof(T);
    std::string const tag = dir + "/region=" + std::to_string(region_bytes);

    // Cardinality sweep: from one run over everything to all-distinct.
    for (std::size_t mean_run : {1u, 2u, 3u, 8u, 64u, 1000u}) {
      auto const values = make_sorted_runs<T>(3 * region_elems + 7, mean_run, 0xD5A + mean_run, descending);
      check(tag + "/mean_run=" + std::to_string(mean_run), values, 0, values.size(), backend, region_bytes);
    }

    // One run spanning several whole regions -- the shape that a naive
    // per-region encoder would clip into pieces.
    {
      auto const values = make_constant<T>(3 * region_elems + 7, static_cast<T>(42));
      check(tag + "/one-run-over-3-regions", values, 0, values.size(), backend, region_bytes);
    }

    // Range lengths straddling exact region multiples.
    for (std::size_t count : {region_elems - 1, region_elems, region_elems + 1,
                              2 * region_elems, 2 * region_elems + 1}) {
      auto const values = make_sorted_runs<T>(count, 4, 0xBEEF + count, descending);
      check(tag + "/count=" + std::to_string(count), values, 0, values.size(), backend, region_bytes);
    }

    // A boundary placed exactly at the region seam, and one on either side of
    // it: the indices the delta compare of neither region covers.
    for (std::size_t offset : {std::size_t{0}, std::size_t{1}, g, 2 * g}) {
      for (int delta = -2; delta <= 2; ++delta) {
        auto const split = region_elems + offset + static_cast<std::size_t>(delta + 2) - 2;
        if (split < 2 || split + 2 >= 2 * region_elems) {
          continue;
        }
        std::vector<T> values(2 * region_elems, static_cast<T>(1));
        for (std::size_t index = split; index < values.size(); ++index) {
          values[index] = static_cast<T>(2);
        }
        if (descending) {
          std::reverse(values.begin(), values.end());
        }
        check(tag + "/seam-split=" + std::to_string(split), values, 0, values.size(),
              backend, region_bytes);
      }
    }

    // Isolated length-1 runs around a seam: these emit nothing, so a detector
    // that mistook them for runs would show up here and nowhere else.
    {
      std::vector<T> values(2 * region_elems);
      for (std::size_t index = 0; index < values.size(); ++index) {
        values[index] = static_cast<T>(index % 251);  // strictly increasing in blocks
      }
      std::sort(values.begin(), values.end());
      if (descending) {
        std::reverse(values.begin(), values.end());
      }
      check(tag + "/dense-distinct", values, 0, values.size(), backend, region_bytes);
    }

    // Unaligned starts: begin offsets that force the scalar prologue, since
    // create_delta rejects a source that is not 8-byte aligned.
    for (std::size_t begin = 0; begin < 2 * g + 1; ++begin) {
      auto const values = make_sorted_runs<T>(2 * region_elems + 11, 5, 0xA11 + begin, descending);
      check(tag + "/begin=" + std::to_string(begin), values, begin, values.size(),
            backend, region_bytes);
      check(tag + "/begin=" + std::to_string(begin) + "/short-end", values, begin,
            values.size() - begin / 2 - 1, backend, region_bytes);
    }

    // Sub-region and degenerate ranges.
    for (std::size_t count : {std::size_t{0}, std::size_t{1}, std::size_t{2}, std::size_t{3},
                              g, g + 1, 2 * g, 2 * g + 1, std::size_t{100}}) {
      auto const values = make_sorted_runs<T>(count + 1, 2, 0x5A5 + count, descending);
      check(tag + "/tiny=" + std::to_string(count), values, 0, count, backend, region_bytes);
    }
  }

  // The min_offload_elements gate must not change the answer, only the route.
  {
    auto const values = make_sorted_runs<T>(50000, 6, 0xC0FFEE, descending);
    check(dir + "/gate-declines", values, 0, values.size(), backend, 64u * 1024u, 1u << 20);
    check(dir + "/gate-accepts", values, 0, values.size(), backend, 64u * 1024u, 1u);
  }
}

void run_all(TslRleBackend backend) {
  std::printf("-- backend %s --\n", tsl_rle_backend_name(backend));
  auto const before = g_failures;
  for (bool descending : {false, true}) {
    run_width<std::uint8_t>(backend, descending);
    run_width<std::uint16_t>(backend, descending);
    run_width<std::uint32_t>(backend, descending);
    run_width<std::uint64_t>(backend, descending);
  }
  std::printf("   %zu checks total, %zu failed on this backend\n", g_checks, g_failures - before);
}

}  // namespace

int main(int argc, char ** argv) {
  bool want_hardware = false;
  for (int index = 1; index < argc; ++index) {
    if (std::strcmp(argv[index], "hw") == 0) {
      want_hardware = true;
    }
  }

  run_all(TslRleBackend::SCALAR);
  run_all(TslRleBackend::DML_SOFTWARE);

  if (want_hardware) {
    run_all(TslRleBackend::DSA_HARDWARE);
  } else {
    std::printf("-- backend dsa_hw skipped (pass 'hw' to include it) --\n");
  }

  if (g_failures != 0) {
    std::printf("\nDSA run detector tests FAILED: %zu of %zu checks\n", g_failures, g_checks);
    return 1;
  }
  std::printf("\nDSA run detector tests passed (%zu checks)\n", g_checks);
  return 0;
}
