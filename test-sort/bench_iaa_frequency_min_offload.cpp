// Finds `min_offload` for the frequency-backed run detector: the range size below
// which preparing costs more than the scan it replaces.
//
// -----------------------------------------------------------------------------
// What is actually being measured
// -----------------------------------------------------------------------------
// Timing the frequency walk on its own would answer the wrong question. The walk
// is started before a range is sorted and consumed after, so what matters is not
// its duration but how much of it the sort fails to hide. This therefore times
// the whole sequence a sorter performs, twice, over the same range:
//
//   A = sort + scalar scan            (what the scalar detector costs)
//   B = prepare + sort + walk         (what the frequency detector costs)
//
// so that B - A is exactly `exposed_walk - scan`: the part of the walk the sort
// did not cover, less the scan it replaced. A negative delta means preparing pays
// at that range size, a positive one means it does not, and the crossover is the
// smallest size where the delta turns negative and stays there. Nothing has to be
// modelled, and the overlap is real rather than assumed.
//
// The `prepare` call passes `stable` over the untouched original while the sort
// runs on a copy, which is exactly what the indirect sorter does at its first
// level: the source column is read-only for the whole sort, so no snapshot is
// taken and none is measured here.
//
// -----------------------------------------------------------------------------
// Why it needs the hardware
// -----------------------------------------------------------------------------
// On `TslIaaFrequencyPath::SOFTWARE`, QPL runs each scan on the calling thread,
// so the walk consumes a core rather than a device and the crossover lands far
// too high. The software numbers are useful only as a bound and as a check that
// the harness works; the answer this tool exists to produce needs
// `TslIaaFrequencyPath::HARDWARE` on a host with an IAA.
//
// -----------------------------------------------------------------------------
// Running it
// -----------------------------------------------------------------------------
//   ./bench_iaa_frequency_min_offload            # hardware, the default
//   ./bench_iaa_frequency_min_offload sw         # QPL software path
//   ./bench_iaa_frequency_min_offload --csv out.csv
//
// The table it prints is per (distinct values, range size); the summary at the
// end names the crossover per cardinality, which is the value to give
// `COSORT_MIN_OFFLOAD`. Distinct count matters because the walk visits one node
// per distinct value: expect the crossover to rise with cardinality, and expect
// a cardinality high enough to have no crossover at all.

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <random>
#include <string>
#include <vector>

#include "equal_runs.hpp"
#include "iaa_frequency_run_detector.hpp"
#include "multicolumn_quicksort.hpp"

namespace {

using Clock = std::chrono::steady_clock;
using DataType = std::uint32_t;
using Sorter = TslMultiColumnQuickSorter<
  DataType, TslPartitionKind::THREE_WAY, TslLeafKind::NETWORK, 1,
  tsl::simd<DataType, tsl::avx512>
>;

constexpr int repetitions = 9;

auto median(std::vector<double> samples) -> double {
  std::sort(samples.begin(), samples.end());
  return samples[samples.size() / 2];
}

auto values_with(std::size_t count, std::size_t distinct, std::uint64_t seed)
  -> std::vector<DataType> {
  std::vector<DataType> values(count);
  std::mt19937_64 rng(seed);
  std::uniform_int_distribution<std::uint64_t> dist(0, std::max<std::size_t>(distinct, 1) - 1);
  for (auto & value : values) {
    value = static_cast<DataType>(dist(rng));
  }
  return values;
}

// A: sort the range, then discover with the scalar scan.
auto time_scalar(std::vector<DataType> const & source, Sorter const & sorter) -> double {
  std::vector<double> samples;
  std::vector<DataType> work;
  for (int rep = 0; rep < repetitions; ++rep) {
    work = source;
    std::size_t spans = 0;
    auto const start = Clock::now();
    sorter.sort_key(work.data(), nullptr, 0, work.size(), TslSortOrder::ASCENDING);
    tsl_for_each_equal_run(work.data(), 0, work.size(), [&](TslRunSpan) { ++spans; });
    auto const stop = Clock::now();
    samples.push_back(std::chrono::duration<double, std::micro>(stop - start).count());
    if (spans == work.size() + 1) {
      std::printf("impossible span count, keeping the optimizer honest\n");
    }
  }
  return median(samples);
}

// B: start the counts over the untouched original, sort a copy, then discover
// from the counts. `source` stays valid and unchanged throughout, which is what
// lets `prepare` skip the snapshot.
auto time_frequency(
  std::vector<DataType> const & source,
  Sorter const & sorter,
  TslIaaFrequencyRunDetector<DataType> & detector
) -> double {
  std::vector<double> samples;
  std::vector<DataType> work;
  for (int rep = 0; rep < repetitions; ++rep) {
    work = source;
    std::size_t spans = 0;
    auto const start = Clock::now();
    detector.prepare(source.data(), 0, source.size(), true);
    sorter.sort_key(work.data(), nullptr, 0, work.size(), TslSortOrder::ASCENDING);
    detector.detect(work.data(), 0, work.size(), [&](TslRunSpan) { ++spans; });
    auto const stop = Clock::now();
    samples.push_back(std::chrono::duration<double, std::micro>(stop - start).count());
    if (spans == work.size() + 1) {
      std::printf("impossible span count, keeping the optimizer honest\n");
    }
  }
  return median(samples);
}

struct row {
  std::size_t distinct;
  std::size_t count;
  double scalar_us;
  double frequency_us;
  std::size_t walk_steps;
  std::size_t fallbacks;
  std::size_t snapshot;
};

}  // namespace

int main(int argc, char ** argv) {
  auto path = TslIaaFrequencyPath::HARDWARE;
  std::string csv_path;
  for (int index = 1; index < argc; ++index) {
    if (std::strcmp(argv[index], "sw") == 0) {
      path = TslIaaFrequencyPath::SOFTWARE;
    } else if (std::strcmp(argv[index], "--csv") == 0 && index + 1 < argc) {
      csv_path = argv[++index];
      ++index;
    }
  }

  TslIaaFrequencyOptions options;
  options.path = path;
  Sorter sorter(0x310FFul);

  std::vector<std::size_t> const counts{
    256, 512, 1024, 2048, 4096, 8192, 16384, 32768, 65536,
    1u << 18, 1u << 20, 1u << 22
  };
  std::vector<std::size_t> const distincts{4, 64, 1024, 16384, 1u << 20};

  std::printf("path=%s  repetitions=%d  (all times are medians, microseconds)\n\n",
              path == TslIaaFrequencyPath::HARDWARE ? "hardware" : "software", repetitions);
  std::printf("%9s %10s %11s %11s %11s %9s %8s\n",
              "distinct", "elements", "scalar us", "freq us", "delta us", "walk", "fallback");

  std::vector<row> rows;
  for (auto const distinct : distincts) {
    for (auto const count : counts) {
      if (distinct > count) {
        continue;  // more distinct values than elements is not a shape
      }
      auto const source = values_with(count, distinct, 0xC0FFEE ^ (distinct * 31 + count));
      // min_prepare = 0: this tool exists to find the threshold, so it must not
      // be subject to one.
      TslIaaFrequencyRunDetector<DataType> detector(options, 0);
      auto const scalar_us = time_scalar(source, sorter);
      auto const frequency_us = time_frequency(source, sorter, detector);
      auto const & metrics = detector.metrics();
      rows.push_back(row{distinct, count, scalar_us, frequency_us,
                         metrics.walk_steps, metrics.fallback_unprepared + metrics.fallback_mismatch,
                         metrics.snapshot_elements});
      std::printf("%9zu %10zu %11.2f %11.2f %+11.2f %9zu %8zu\n",
                  distinct, count, scalar_us, frequency_us, frequency_us - scalar_us,
                  metrics.walk_steps, metrics.fallback_unprepared + metrics.fallback_mismatch);
    }
    std::printf("\n");
  }

  // The crossover: the smallest size at or above which preparing wins and keeps
  // winning. Reported per cardinality because the walk's cost scales with the
  // distinct count, not with the range.
  std::printf("crossover (smallest range where preparing pays, and pays above it):\n");
  for (auto const distinct : distincts) {
    std::size_t crossover = 0;
    for (auto iterator = rows.rbegin(); iterator != rows.rend(); ++iterator) {
      if (iterator->distinct != distinct) {
        continue;
      }
      if (iterator->frequency_us < iterator->scalar_us) {
        crossover = iterator->count;
      } else {
        break;  // walking downwards, so this is where the run of wins ends
      }
    }
    if (crossover == 0) {
      std::printf("  distinct=%-8zu never -- the scan is cheaper at every size measured\n",
                  distinct);
    } else {
      std::printf("  distinct=%-8zu COSORT_MIN_OFFLOAD=%zu\n", distinct, crossover);
    }
  }
  std::printf("\nA single threshold has to serve every cardinality, so take the\n"
              "largest crossover above that you care about: below it the detector\n"
              "declines and the scalar scan runs, which is the safe direction.\n");

  if (!csv_path.empty()) {
    std::ofstream csv(csv_path);
    csv << "path,distinct,elements,scalar_us,frequency_us,delta_us,walk_steps,fallbacks,snapshot\n";
    for (auto const & entry : rows) {
      csv << (path == TslIaaFrequencyPath::HARDWARE ? "hardware" : "software") << ','
          << entry.distinct << ',' << entry.count << ',' << entry.scalar_us << ','
          << entry.frequency_us << ',' << (entry.frequency_us - entry.scalar_us) << ','
          << entry.walk_steps << ',' << entry.fallbacks << ',' << entry.snapshot << '\n';
    }
    std::printf("wrote %s\n", csv_path.c_str());
  }
  return 0;
}
