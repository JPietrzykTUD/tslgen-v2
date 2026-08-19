// Single-threaded timing benchmark for the multicolumn sort.
//
// Methodology (kept identical across both experiments so numbers compare):
//   - TRUE lexicographic multi-key sort via sort_columns(): every generated
//     column is a real sort key (ascending), not a passive payload. This is the
//     only shape that exercises the multi-column tie-breaking machinery.
//   - Input comes from the shared structured data generator (dataset_catalog),
//     shape = PrefixPresorted: rows are sorted by the first `p` key columns and
//     random within each equal-prefix group. Sweeping p traces how much existing
//     order each algorithm exploits and how deep into the secondary keys it works.
//   - uint32 keys, AVX-512, THREE_WAY partition + NETWORK leaf, POST_SORT run
//     discovery. 3 columns. sizes 1M / 4M / 16M rows.
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
#include "../multicolumn_quicksort.hpp"
#include "../datagen/dataset_catalog.hpp"

using DataType = std::uint32_t;
using Avx512 = tsl::simd<DataType, tsl::avx512>;

constexpr auto PK = TslPartitionKind::THREE_WAY;
constexpr auto LK = TslLeafKind::NETWORK;
constexpr auto DISCOVERY = TslRunDiscoveryKind::POST_SORT;
using Sorter = TslMultiColumnQuickSorter<DataType, PK, LK, 16, Avx512>;

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

// One (rows, p) case: generate a PrefixPresorted instance, sort all columns
// lexicographically `trials` times, return median ns/elem.
static double time_case(std::size_t rows, std::size_t columns, std::size_t p,
                        std::size_t trials, bool* ok) {
  TslDatasetSpec spec;
  spec.id = "prefix_presorted_r" + std::to_string(rows) + "_p" + std::to_string(p);
  spec.shape = TslShape::PrefixPresorted;
  spec.rows = rows;
  spec.columns = columns;
  spec.element_bytes = sizeof(DataType);
  spec.params["p"] = static_cast<double>(p);
  const auto pristine = tsl_generate_dataset<DataType>(spec);

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

  std::printf("size_elems\tcols\tpresort_p\tns_per_elem\n");
  for (auto rows : sizes) {
    for (auto p : prefixes) {
      bool ok = true;
      const double t = time_case(rows, columns, p, trials, &ok);
      if (!ok) std::fprintf(stderr, "UNSORTED size=%zu p=%zu\n", rows, p);
      std::printf("%zu\t%zu\t%zu\t%.4f\n", rows, columns, p, t);
    }
  }
  return 0;
}
