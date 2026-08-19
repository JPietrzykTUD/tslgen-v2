// Single-threaded timing benchmark for the standalone leashed multicolumn sort.
//
// Drives `TslMultiColumnLeashedSorter` from ../multicolumn_qs_leashed.hpp against
// the shared structured data generator in ../datagen/. Self-contained experiment:
// it does not touch the shared multicolumn_quicksort.hpp or its benchmark.
//
// Methodology (leash-specific knob sweep on top of the structured data):
//   - TRUE lexicographic multi-key sort via sort_columns(): every generated
//     column is a real sort key (ascending), not a passive payload.
//   - Input from the shared structured data generator (dataset_catalog),
//     shape = PrefixPresorted: sorted by the first `p` key columns, random
//     within each equal-prefix group. p swept {1, 2, 3} (p=3 = fully sorted).
//   - uint32 keys, AVX-512, THREE_WAY partition + NETWORK leaf, POST_SORT run
//     discovery. 3 columns. sizes 1M / 4M / 16M rows.
//   - LEASH KNOB SWEEP: for each (size, p) the leash knobs are swept over a grid
//     (chunk_lanes in {64..4096}, leash_lanes = chunk * {1, 2}); the BEST
//     configuration is reported on stdout, and every config is logged to stderr.
//   - each trial restores pristine unsorted input; report MEDIAN of `trials`
//     total-times / rows -> nanoseconds per element. Output verified against the
//     full lexicographic comparator every trial.
//
// Pin to an idle core for stable numbers, e.g.:
//   numactl --physcpubind=2 --membind=0 ./benchmark 7
#include <algorithm>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>

#include <tsl.hpp>
#include "../multicolumn_qs_leashed.hpp"
#include "../datagen/dataset_catalog.hpp"

using DataType = std::uint32_t;
using Avx512 = tsl::simd<DataType, tsl::avx512>;

constexpr auto PK = TslPartitionKind::THREE_WAY;
constexpr auto LK = TslLeafKind::NETWORK;
constexpr auto DISCOVERY = TslRunDiscoveryKind::POST_SORT;
using Sorter = TslMultiColumnLeashedSorter<DataType, PK, LK, 16, Avx512>;

static std::uint64_t now_ns() {
  return std::chrono::duration_cast<std::chrono::nanoseconds>(
             std::chrono::steady_clock::now().time_since_epoch()).count();
}

// Adjacent-row check against the complete lexicographic comparator (all columns
// ascending). A false result means the sort produced a wrong global order.
static bool lexicographically_sorted(
    const std::vector<std::vector<DataType>>& columns) {
  if (columns.empty() || columns.front().size() < 2) return true;
  const std::size_t cols = columns.size();
  for (std::size_t row = 1; row < columns.front().size(); ++row) {
    for (std::size_t c = 0; c < cols; ++c) {
      const auto prev = columns[c][row - 1];
      const auto cur = columns[c][row];
      if (prev == cur) continue;
      if (prev > cur) return false;  // strictly out of order
      break;                          // this column decides the pair -> ok
    }
  }
  return true;
}

static std::vector<std::vector<DataType>> make_dataset(
    std::size_t rows, std::size_t columns, std::size_t p) {
  TslDatasetSpec spec;
  spec.id = "prefix_presorted_r" + std::to_string(rows) + "_p" + std::to_string(p);
  spec.shape = TslShape::PrefixPresorted;
  spec.rows = rows;
  spec.columns = columns;
  spec.element_bytes = sizeof(DataType);
  spec.params["p"] = static_cast<double>(p);
  return tsl_generate_dataset<DataType>(spec);
}

// Median ns/elem for the currently-set leash knobs over `trials`, restoring the
// pristine dataset each trial. Verifies the output lexicographically.
static double time_config(const std::vector<std::vector<DataType>>& pristine,
                          std::size_t rows, std::size_t columns,
                          std::size_t trials, bool* ok) {
  auto work = pristine;
  std::vector<std::uint64_t> samples;
  samples.reserve(trials);
  for (std::size_t t = 0; t < trials; ++t) {
    for (std::size_t c = 0; c < columns; ++c) work[c] = pristine[c];
    std::vector<TslSortColumn<DataType>> specs(columns);
    for (std::size_t c = 0; c < columns; ++c)
      specs[c] = TslSortColumn<DataType>{work[c].data(), TslSortOrder::ASCENDING};
    Sorter sorter(0x11);
    const auto t0 = now_ns();
    sorter.sort_columns(specs.data(), specs.size(), rows, DISCOVERY, nullptr);
    const auto t1 = now_ns();
    samples.push_back(t1 - t0);
  }
  if (ok) *ok = lexicographically_sorted(work);
  std::sort(samples.begin(), samples.end());
  return static_cast<double>(samples[samples.size() / 2]) / static_cast<double>(rows);
}

int main(int argc, char** argv) {
  std::size_t trials = 7;
  if (argc > 1) trials = std::stoull(argv[1]);

  const std::size_t sizes[] = {1u << 20, 4u << 20, 16u << 20};
  const std::size_t columns = 3;
  const std::size_t prefixes[] = {1, 2, columns};  // p=full (==columns) is fully sorted
  const std::size_t chunks[] = {64, 128, 256, 512, 1024, 2048, 4096};

  std::printf("size_elems\tcols\tpresort_p\tbest_ns\tchunk\tleash\n");
  for (auto rows : sizes) {
    for (auto p : prefixes) {
      const auto pristine = make_dataset(rows, columns, p);  // generate once, reuse across knobs
      double best = 1e300;
      std::size_t best_chunk = 0, best_leash = 0;
      for (auto chunk : chunks) {
        for (std::size_t lf : {std::size_t{1}, std::size_t{2}}) {
          bool ok = true;
          Sorter::chunk_lanes = chunk;
          Sorter::leash_lanes = chunk * lf;
          const double v = time_config(pristine, rows, columns, trials, &ok);
          if (!ok)
            std::fprintf(stderr, "UNSORTED size=%zu p=%zu chunk=%zu leash=%zu\n",
                         rows, p, chunk, chunk * lf);
          std::fprintf(stderr, "  size=%zu p=%zu chunk=%zu leash=%zu -> %.4f ns/elem\n",
                       rows, p, chunk, chunk * lf, v);
          if (v < best) { best = v; best_chunk = chunk; best_leash = chunk * lf; }
        }
      }
      std::printf("%zu\t%zu\t%zu\t%.4f\t%zu\t%zu\n",
                  rows, columns, p, best, best_chunk, best_leash);
    }
  }
  return 0;
}
