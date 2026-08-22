// Times equal-run detection on the CPU against the DSA offload.
//
// The number that matters is not "is create_delta faster than a scalar scan"
// -- one DSA engine will not out-scan a core running at memory bandwidth. It is
// how much CPU time the offload *removes* from the calling thread, because the
// point of the offload is to free a core for sorting, not to detect runs
// faster. This benchmark therefore reports wall time and, for the accelerator
// backends, how many elements actually reached a descriptor.

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <random>
#include <string>
#include <vector>

#include "cluster_detection/dsa/dsa_run_detector.hpp"
#include "cluster_detection/scalar/equal_runs.hpp"

namespace {

template <class T>
auto make_sorted_runs(std::size_t count, std::size_t mean_run, std::uint64_t seed)
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
  return values;
}

struct measurement {
  double milliseconds = 0.0;
  std::size_t spans = 0;
  TslDsaRunDetectorMetrics metrics{};
};

template <class T>
auto time_detector(
  std::vector<T> const & values,
  TslRleBackend backend,
  std::size_t region_bytes,
  int repetitions
) -> measurement {
  measurement best;
  best.milliseconds = 1e30;
  TslDsaRunDetector<T> detector(backend, region_bytes, 0);

  for (int rep = 0; rep < repetitions; ++rep) {
    detector.reset_metrics();
    std::size_t spans = 0;
    std::size_t checksum = 0;
    auto const start = std::chrono::steady_clock::now();
    detector.detect(values.data(), 0, values.size(), [&](TslRunSpan span) {
      ++spans;
      checksum += span.end - span.begin;
    });
    auto const stop = std::chrono::steady_clock::now();
    asm volatile("" :: "r"(&checksum) : "memory");
    auto const ms = std::chrono::duration<double, std::milli>(stop - start).count();
    if (ms < best.milliseconds) {
      best.milliseconds = ms;
      best.spans = spans;
      best.metrics = detector.metrics();
    }
  }
  return best;
}

template <class T>
void run_width(char const * type_name, std::size_t count, int repetitions, bool with_hardware) {
  for (std::size_t mean_run : {std::size_t{1}, std::size_t{4}, std::size_t{64}, std::size_t{4096}}) {
    auto const values = make_sorted_runs<T>(count, mean_run, 0x51ED + mean_run);
    auto const megabytes = double(values.size() * sizeof(T)) / (1024.0 * 1024.0);

    auto const scalar = time_detector(values, TslRleBackend::SCALAR, tsl_dsa_default_region_bytes, repetitions);

    std::printf(
      "%-5s n=%-9zu %6.1f MiB mean_run=%-5zu spans=%-9zu | scalar %8.3f ms (%6.2f GiB/s)",
      type_name, values.size(), megabytes, mean_run, scalar.spans,
      scalar.milliseconds, megabytes / 1024.0 / (scalar.milliseconds / 1000.0)
    );

    for (auto backend : {TslRleBackend::DML_SOFTWARE, TslRleBackend::DSA_HARDWARE}) {
      if (backend == TslRleBackend::DSA_HARDWARE && !with_hardware) {
        continue;
      }
      for (std::size_t region_bytes : {32u * 1024u, 128u * 1024u, 512u * 1024u}) {
        measurement result;
        try {
          result = time_detector(values, backend, region_bytes, repetitions);
        } catch (std::exception const & error) {
          std::printf("\n       %s region=%zuKiB FAILED: %s",
                      tsl_rle_backend_name(backend), region_bytes / 1024, error.what());
          continue;
        }
        if (result.spans != scalar.spans) {
          std::printf("\n       %s region=%zuKiB MISMATCH: %zu spans vs scalar %zu",
                      tsl_rle_backend_name(backend), region_bytes / 1024,
                      result.spans, scalar.spans);
          continue;
        }
        std::printf(
          "\n       %-6s region=%3zuKiB %8.3f ms  %5.2fx scalar  desc=%-6zu fired=%-9zu offloaded=%.0f%%",
          tsl_rle_backend_name(backend), region_bytes / 1024, result.milliseconds,
          scalar.milliseconds / result.milliseconds,
          result.metrics.descriptors, result.metrics.fired_blocks,
          100.0 * double(result.metrics.offloaded_elements) / double(values.size())
        );
      }
    }
    std::printf("\n");
  }
}

}  // namespace

int main(int argc, char ** argv) {
  std::size_t count = 16u * 1024u * 1024u;
  int repetitions = 5;
  bool with_hardware = true;

  for (int index = 1; index < argc; ++index) {
    std::string const arg = argv[index];
    if (arg == "--no-hw") {
      with_hardware = false;
    } else if (arg.rfind("--n=", 0) == 0) {
      count = std::stoull(arg.substr(4));
    } else if (arg.rfind("--reps=", 0) == 0) {
      repetitions = std::stoi(arg.substr(7));
    } else {
      std::printf("usage: %s [--n=<elements>] [--reps=<n>] [--no-hw]\n", argv[0]);
      return 2;
    }
  }

  std::printf("equal-run detection, best of %d, single thread\n\n", repetitions);
  run_width<std::uint32_t>("u32", count, repetitions, with_hardware);
  run_width<std::uint64_t>("u64", count / 2, repetitions, with_hardware);
  return 0;
}
