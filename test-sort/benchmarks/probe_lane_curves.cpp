// Does a knob's response curve depend on lanes alone?
//
// `lanes = bits / (8 * bytes)`, so 256-bit over 4-byte keys and 512-bit over
// 8-byte keys are both eight lanes. If the algorithmic knobs are a function of
// lanes, the two cells should respond to a knob the same way.
//
// Comparing each cell's *winner* cannot answer this: the curve is flat near its
// minimum, so the argmin is the least stable statistic it has, and two runs of one
// cell already disagree. What is measurable is the curve itself. Each cell's K
// sweep is interleaved and normalised to its own K=16, so absolute cost -- u64
// moves twice the bytes -- divides out and only the shape remains.
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <functional>
#include <string>
#include <vector>

#include "datagen/dataset_catalog.hpp"
#include "datagen/dataset_source.hpp"
#include "sorting/sample_sort/samplesort_multicolumn.hpp"
#include "cluster_detection/scalar/equal_runs.hpp"
#include "tsl_simd_for.hpp"

namespace {
auto median(std::vector<double> v) -> double {
  std::sort(v.begin(), v.end());
  return v[v.size() / 2];
}
}  // namespace

// One cell: sweep K interleaved, return the curve normalised to K=16.
template <class Key, std::size_t Bits>
auto sweep_k(std::string const & shape, std::size_t rows, std::size_t cols,
             int rounds) -> std::vector<double> {
  using Simd = typename tsl_simd_for<Key, TslStyle::Intrinsics, Bits>::type;
  constexpr std::size_t lanes = Simd::lane_count_v;
  TslDatasetSource<Key> source(12ull << 30);
  auto const catalog = tsl_default_catalog(rows, cols, sizeof(Key));
  auto const tail = "_u" + std::to_string(sizeof(Key) * 8) + "_n";
  TslDatasetSpec const * spec = nullptr;
  for (auto const & c : catalog) {
    if (c.id.rfind(shape + tail, 0) == 0) { spec = &c; break; }
  }
  if (spec == nullptr) { std::printf("  no dataset\n"); return {}; }
  auto const pristine = source.pristine(*spec);
  std::vector<TslSortColumn<Key>> columns;
  for (auto const & c : *pristine) {
    columns.push_back(TslSortColumn<Key>{const_cast<Key *>(c.data()), TslSortOrder::ASCENDING});
  }
  std::vector<Key> index(spec->rows);

  constexpr std::size_t base = 256;
  TslSampleSortMultiColumn<Key, Simd, 8, TslSampleSortBuckets::Adaptive, 8, base,
      TslSampleSortBase::Network, TslSampleSortIds::Byte, base / lanes, 50,
      TslSampleSortMovement::OutOfPlace, false> k8;
  TslSampleSortMultiColumn<Key, Simd, 16, TslSampleSortBuckets::Adaptive, 8, base,
      TslSampleSortBase::Network, TslSampleSortIds::Byte, base / lanes, 50,
      TslSampleSortMovement::OutOfPlace, false> k16;
  TslSampleSortMultiColumn<Key, Simd, 32, TslSampleSortBuckets::Adaptive, 8, base,
      TslSampleSortBase::Network, TslSampleSortIds::Byte, base / lanes, 50,
      TslSampleSortMovement::OutOfPlace, false> k32;

  std::vector<std::function<void()>> runs;
  auto add = [&](auto & sorter) {
    runs.push_back([&sorter, &columns, cols, &index, spec] {
      TslIndexScalarDetector<Key> detector;
      sorter.sort_index(columns.data(), cols, index.data(), spec->rows, detector);
    });
  };
  add(k8); add(k16); add(k32);

  std::vector<std::vector<double>> times(runs.size());
  for (int round = 0; round < rounds; ++round) {
    for (std::size_t at = 0; at < runs.size(); ++at) {
      auto const start = std::chrono::steady_clock::now();
      runs[at]();
      times[at].push_back(std::chrono::duration<double, std::milli>(
        std::chrono::steady_clock::now() - start).count());
    }
  }
  // Normalise to K=16 per round, then take the median ratio: drift divides out.
  std::vector<double> curve;
  for (std::size_t at = 0; at < runs.size(); ++at) {
    std::vector<double> ratios;
    for (int round = 0; round < rounds; ++round) {
      ratios.push_back(times[at][round] / times[1][round]);
    }
    std::sort(ratios.begin(), ratios.end());
    curve.push_back(median(ratios));
    curve.push_back(ratios[ratios.size() / 4]);
    curve.push_back(ratios[(3 * ratios.size()) / 4]);
  }
  std::printf("  %2zu lanes (u%zu @ %zu-bit)  K8 %.4f [%.4f..%.4f]  K16 1.0000  "
              "K32 %.4f [%.4f..%.4f]\n", lanes, sizeof(Key) * 8, Bits,
              curve[0], curve[1], curve[2], curve[6], curve[7], curve[8]);
  return curve;
}

int main(int argc, char ** argv) {
  std::size_t const rows = argc > 1 ? std::strtoull(argv[1], nullptr, 10) : (1u << 21);
  int const rounds = argc > 2 ? std::atoi(argv[2]) : 15;
  std::string const shape = argc > 3 ? argv[3] : "low_cardinality_d4";
  std::printf("K response curve, normalised to K=16 within each cell\n");
  std::printf("%s, %zu rows x 4 columns, %d interleaved rounds\n\n", shape.c_str(),
              rows, rounds);
  std::printf("the two eight-lane cells -- if lanes is the axis, these two agree\n");
  auto const a = sweep_k<std::uint32_t, 256>(shape, rows, 4, rounds);
  auto const b = sweep_k<std::uint64_t, 512>(shape, rows, 4, rounds);
  std::printf("\nfor contrast, the other lane counts\n");
  sweep_k<std::uint32_t, 512>(shape, rows, 4, rounds);
  sweep_k<std::uint64_t, 256>(shape, rows, 4, rounds);
  if (a.size() >= 9 && b.size() >= 9) {
    auto overlap = [](double lo1, double hi1, double lo2, double hi2) {
      return !(hi1 < lo2 || hi2 < lo1);
    };
    std::printf("\neight-lane verdict: K8 %s, K32 %s\n",
                overlap(a[1], a[2], b[1], b[2]) ? "agrees" : "DIFFERS",
                overlap(a[7], a[8], b[7], b[8]) ? "agrees" : "DIFFERS");
  }
  return 0;
}
