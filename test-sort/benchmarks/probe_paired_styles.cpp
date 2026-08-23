#include <functional>
// Paired, interleaved measurement.
//
// Sequential measurement -- all nine repetitions of A, then all nine of B --
// charges any drift between the two blocks to the A-B difference. When the
// difference is 0.2% and the drift is 3.5%, the comparison is noise. Interleaving
// A,B,C,A,B,C,... and taking the median of the per-round *ratios* cancels drift
// that is slow relative to a round, which is what machine drift is.
//
// This answers two questions the sequential tuner could not:
//   * do the three implementation styles differ at a fixed lane count
//   * does a knob's response curve depend on lanes alone
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <numeric>
#include <string>
#include <vector>

#include "datagen/dataset_catalog.hpp"
#include "datagen/dataset_source.hpp"
#include "sorting/quicksort/multicolumn_index_sort.hpp"
#include "sorting/sample_sort/samplesort_multicolumn.hpp"
#include "cluster_detection/scalar/equal_runs.hpp"
#include "tsl_simd_for.hpp"

namespace {

struct Entrant {
  std::string name;
  std::function<void()> run;
};

// Median of per-round ratios against the first entrant. Drift common to a round
// divides out.
void interleave(std::vector<Entrant> & entrants, int rounds) {
  std::vector<std::vector<double>> times(entrants.size());
  for (int round = 0; round < rounds; ++round) {
    for (std::size_t at = 0; at < entrants.size(); ++at) {
      auto const start = std::chrono::steady_clock::now();
      entrants[at].run();
      times[at].push_back(std::chrono::duration<double, std::milli>(
        std::chrono::steady_clock::now() - start).count());
    }
  }
  auto median = [](std::vector<double> v) {
    std::sort(v.begin(), v.end());
    return v[v.size() / 2];
  };
  std::printf("%-26s %10s %10s   %s\n", "entrant", "median ms", "vs first",
              "per-round ratio spread");
  for (std::size_t at = 0; at < entrants.size(); ++at) {
    std::vector<double> ratios;
    for (int round = 0; round < rounds; ++round) {
      ratios.push_back(times[at][round] / times[0][round]);
    }
    std::sort(ratios.begin(), ratios.end());
    auto const lo = ratios[ratios.size() / 4];
    auto const hi = ratios[(3 * ratios.size()) / 4];
    std::printf("%-26s %10.2f %10.4f   [%.4f .. %.4f]%s\n",
                entrants[at].name.c_str(), median(times[at]),
                median(ratios), lo, hi,
                (lo > 1.0 || hi < 1.0) ? "  distinguishable" : "  tied with first");
  }
}

}  // namespace

template <class Key, TslStyle Style, std::size_t Bits>
auto quicksort_entrant(std::vector<TslSortColumn<Key>> & columns, std::size_t cols,
                       std::vector<Key> & index, std::size_t rows,
                       char const * label) -> Entrant {
  using Simd = typename tsl_simd_for<Key, Style, Bits>::type;
  static TslMultiColumnIndexSorter<Key, TslPartitionKind::THREE_WAY,
                                   TslLeafKind::NETWORK, Simd,
                                   tsl_hybrid_auto_percent<Key, Simd>()> sorter(0x5A3F1E77);
  return Entrant{label, [&columns, cols, &index, rows] {
    TslIndexScalarDetector<Key> detector;
    sorter.sort_index(columns.data(), cols, index.data(), rows,
                      TslRunDiscoveryKind::POST_SORT, detector);
  }};
}

int main(int argc, char ** argv) {
  std::size_t const rows = argc > 1 ? std::strtoull(argv[1], nullptr, 10) : (1u << 21);
  int const rounds = argc > 2 ? std::atoi(argv[2]) : 15;
  std::string const shape = argc > 3 ? argv[3] : "low_cardinality_d4";
  std::size_t const cols = 4;

  using Key = std::uint32_t;
  TslDatasetSource<Key> source(12ull << 30);
  auto const catalog = tsl_default_catalog(rows, cols, sizeof(Key));
  TslDatasetSpec const * spec = nullptr;
  auto const tail = "_u32_n";
  for (auto const & c : catalog) {
    if (c.id.rfind(shape + tail, 0) == 0) { spec = &c; break; }
  }
  if (spec == nullptr) { std::printf("no shape %s\n", shape.c_str()); return 1; }
  auto const pristine = source.pristine(*spec);
  std::vector<TslSortColumn<Key>> columns;
  for (auto const & c : *pristine) {
    columns.push_back(TslSortColumn<Key>{const_cast<Key *>(c.data()), TslSortOrder::ASCENDING});
  }
  std::vector<Key> index(spec->rows);

  std::printf("%s, %zu rows x %zu columns, u32 = 16 lanes at 512-bit\n",
              spec->id.c_str(), spec->rows, spec->columns);
  std::printf("%d interleaved rounds, quicksort 3way/hyb/post, 1 worker\n\n", rounds);

  std::vector<Entrant> entrants;
  entrants.push_back(quicksort_entrant<Key, TslStyle::Intrinsics, 512>(
    columns, cols, index, spec->rows, "intrinsics/512"));
  entrants.push_back(quicksort_entrant<Key, TslStyle::ClangBuiltin, 512>(
    columns, cols, index, spec->rows, "clang_builtin/512"));
  entrants.push_back(quicksort_entrant<Key, TslStyle::ClangBoolMask, 512>(
    columns, cols, index, spec->rows, "clang_bool_mask/512"));
  interleave(entrants, rounds);
  return 0;
}
