// Does choosing the leaf per *leaf* beat choosing it per configuration?
//
// `TslMultiColumnQuickSorter`'s two leaf configurations differ in both the leaf
// and the size at which partitioning stops (network: one full-capacity bitonic
// sort for anything <= 256; insertion: an O(n^2) leaf for anything <= 64). This
// sweeps `HybridFillPercent`, which diverts a leaf holding less than that share of
// the network's capacity to the insertion leaf, and reports whether any setting
// beats both fixed configurations.
//
// Every policy comes out of one driver, so a comparison changes exactly one
// template argument -- no cross-binary or cross-build comparison is involved. The
// sweep's ends coincide with always-network and always-insertion by construction,
// so it cannot miss a winner by not reaching it.
//
// Row count is swept because it is what sets the leaf fill ratio on a
// low-cardinality shape: m columns of d distinct values produce d^m groups, so the
// leaves shrink as columns are added and grow as rows are. A single row count
// answers the question only for one fill regime.
//
// Every configuration is checked against the reference image before it is timed:
// with every column a sort key the sorted image is unique however ties are broken,
// so a wrong leaf choice cannot hide behind an unstable sort.
//
//   ./bench_hybrid_leaf                                # the default sweep
//   ./bench_hybrid_leaf --rows 262144,1048576
//   ./bench_hybrid_leaf --shapes skewed_zipf_s1 --cols 8
//   ./bench_hybrid_leaf --csv hybrid.csv

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <memory>
#include <string>
#include <vector>

#include "dataset_catalog.hpp"
#include "dataset_reference.hpp"
#include "dataset_source.hpp"
#include "multicolumn_qs_hybrid_leaf.hpp"

namespace {

using Clock = std::chrono::steady_clock;
using DataType = std::uint32_t;
using Runner = TslLeafPolicyRunner<DataType>;

constexpr int repetitions = 5;

auto median(std::vector<double> samples) -> double {
  std::sort(samples.begin(), samples.end());
  return samples[samples.size() / 2];
}

struct outcome {
  double milliseconds;
  double best_milliseconds;
  TslHybridLeafMetrics metrics;
  bool correct;
};

// Times one policy over one dataset, verifying before the timed runs.
auto measure(
  Runner & runner,
  std::vector<std::vector<DataType>> const & pristine,
  std::vector<std::vector<DataType>> const & reference
) -> outcome {
  auto const columns = pristine.size();
  auto const rows = pristine.front().size();

  std::vector<std::vector<DataType>> work(pristine);
  std::vector<TslSortColumn<DataType>> specs;
  auto const refresh = [&]() {
    for (std::size_t column = 0; column < columns; ++column) {
      work[column] = pristine[column];
    }
    specs.clear();
    for (std::size_t column = 0; column < columns; ++column) {
      specs.push_back(TslSortColumn<DataType>{work[column].data(), TslSortOrder::ASCENDING});
    }
  };

  // Correctness first, so a policy that sorts wrongly never reports a time.
  refresh();
  runner.sort(specs.data(), columns, rows, nullptr);
  for (std::size_t column = 0; column < columns; ++column) {
    if (work[column] != reference[column]) {
      return outcome{0.0, 0.0, {}, false};
    }
  }

  std::vector<double> samples;
  TslHybridLeafMetrics metrics;
  for (int rep = 0; rep < repetitions; ++rep) {
    refresh();
    auto const start = Clock::now();
    runner.sort(specs.data(), columns, rows, &metrics);
    auto const stop = Clock::now();
    samples.push_back(std::chrono::duration<double, std::milli>(stop - start).count());
  }
  auto const best = *std::min_element(samples.begin(), samples.end());
  return outcome{median(samples), best, metrics, true};
}

// A dataset id is `<shape><params>_u<bits>_n<rows>_c<cols>`, so a shape name plus
// the width tail is a prefix of exactly the specs for that shape. Inlined rather
// than pulled from benchmarks/cosort_case.hpp, which this experiment does not
// otherwise depend on.
auto id_tail() -> std::string {
  return "_u" + std::to_string(sizeof(DataType) * 8) + "_n";
}

auto select_shape(std::vector<TslDatasetSpec> const & catalog, std::string const & shape)
  -> std::vector<TslDatasetSpec> {
  std::vector<TslDatasetSpec> chosen;
  for (auto const & spec : catalog) {
    if (spec.id.rfind(shape + id_tail(), 0) == 0) {
      chosen.push_back(spec);
    }
  }
  return chosen;
}

auto shape_label(TslDatasetSpec const & spec) -> std::string {
  auto const cut = spec.id.find(id_tail());
  return cut == std::string::npos ? spec.id : spec.id.substr(0, cut);
}

auto split(std::string const & text, char separator) -> std::vector<std::string> {
  std::vector<std::string> parts;
  std::size_t start = 0;
  while (start <= text.size()) {
    auto const cut = text.find(separator, start);
    auto const end = cut == std::string::npos ? text.size() : cut;
    if (end > start) {
      parts.push_back(text.substr(start, end - start));
    }
    if (cut == std::string::npos) {
      break;
    }
    start = cut + 1;
  }
  return parts;
}

struct row {
  std::string shape;
  std::size_t rows;
  std::size_t columns;
  std::string policy;
  std::size_t fill_percent;
  double milliseconds;
  double best_milliseconds;
  TslHybridLeafMetrics metrics;
};

}  // namespace

int main(int argc, char ** argv) {
  std::vector<std::size_t> row_counts;
  // Shapes whose leaf structure differs most: a low-cardinality key explodes into
  // many equally-sized small leaves as columns are added, zipf produces a long
  // tail of tiny ones, a terminal-group shape keeps them mid-sized, and an
  // all-distinct first column ends the recursion at once.
  std::vector<std::string> shapes{
    "low_cardinality_d4", "unique_last_g64", "skewed_zipf_s1", "unique_first"
  };
  std::vector<std::size_t> column_counts{2, 4, 8};
  std::string csv_path;

  for (int index = 1; index < argc; ++index) {
    auto const flag = std::string(argv[index]);
    auto const has_value = index + 1 < argc;
    if (flag == "--csv" && has_value) {
      csv_path = argv[++index];
    } else if (flag == "--rows" && has_value) {
      row_counts.clear();
      for (auto const & part : split(argv[++index], ',')) {
        row_counts.push_back(static_cast<std::size_t>(std::strtoull(part.c_str(), nullptr, 10)));
      }
    } else if (flag == "--shapes" && has_value) {
      shapes = split(argv[++index], ',');
    } else if (flag == "--cols" && has_value) {
      column_counts.clear();
      for (auto const & part : split(argv[++index], ',')) {
        column_counts.push_back(static_cast<std::size_t>(std::strtoull(part.c_str(), nullptr, 10)));
      }
    } else {
      std::printf("unknown or incomplete argument: %s\n", flag.c_str());
      return 2;
    }
  }
  if (row_counts.empty()) {
    row_counts = {1u << 18, 1u << 20};
  }

  auto const policies = tsl_leaf_policies<DataType, TslPartitionKind::THREE_WAY, 16,
                                          tsl::simd<DataType, tsl::avx512>>(0x11EAF);
  auto const capacity = TslCoSortBitonicLeaf<DataType, tsl::simd<DataType, tsl::avx512>>::capacity;

  std::printf("network capacity=%zu  hyb@auto=%zu%% (network only at or above the\n"
              "insertion threshold)  repetitions=%d  (ms, median then best)\n",
              capacity, tsl_hybrid_auto_percent<DataType, tsl::simd<DataType, tsl::avx512>>(),
              repetitions);
  std::printf("%-20s %8s %5s %-8s %6s %9s %9s %10s %10s %9s\n",
              "shape", "rows", "cols", "policy", "leafT", "median", "best",
              "leaf->net", "leaf->ins", "pad/row");

  std::vector<row> table;
  TslDatasetSource<DataType> source(4ull << 30);

  for (auto const & shape : shapes) {
    for (auto const rows : row_counts) {
      for (auto const columns : column_counts) {
        auto const catalog = tsl_default_catalog(rows, columns, sizeof(DataType));
        auto const chosen = select_shape(catalog, shape);
        if (chosen.empty()) {
          std::printf("%-20s %8zu %5zu  (no such dataset in the catalog)\n",
                      shape.c_str(), rows, columns);
          continue;
        }
        auto const & spec = chosen.front();
        auto const pristine = source.pristine(spec);
        auto const reference = source.reference(spec, TslDirection::Ascending);

        for (auto const & policy : policies) {
          auto const result = measure(*policy, *pristine, *reference);
          if (!result.correct) {
            std::printf("%-20s %8zu %5zu %-8s   INCORRECT -- differs from the reference\n",
                        shape_label(spec).c_str(), rows, columns, policy->label().c_str());
            return 1;
          }
          auto const & m = result.metrics;
          std::printf("%-20s %8zu %5zu %-8s %6zu %9.2f %9.2f %10zu %10zu %9.2f\n",
                      shape_label(spec).c_str(), rows, columns, policy->label().c_str(),
                      policy->leaf_threshold(), result.milliseconds, result.best_milliseconds,
                      m.leaves_to_network, m.leaves_to_insertion,
                      static_cast<double>(m.network_padding) / static_cast<double>(rows));
          table.push_back(row{shape_label(spec), rows, columns, policy->label(),
                              policy->fill_percent(), result.milliseconds,
                              result.best_milliseconds, m});
        }
        std::printf("\n");
      }
    }
  }

  // The question the sweep exists to answer: per (shape, rows, columns), does any
  // diversion threshold beat both fixed configurations, and by how much?
  std::printf("%-20s %8s %5s %9s %9s %11s %8s %s\n",
              "shape", "rows", "cols", "ins", "net", "best hybrid", "gain", "at P");
  for (auto const & shape : shapes) {
    for (auto const rows : row_counts) {
      for (auto const columns : column_counts) {
        double ins = 0.0;
        double net = 0.0;
        double hybrid = 0.0;
        std::size_t at_percent = 0;
        for (auto const & entry : table) {
          if (entry.shape != shape || entry.rows != rows || entry.columns != columns) {
            continue;
          }
          if (entry.policy == "ins") {
            ins = entry.best_milliseconds;
          } else if (entry.policy == "net") {
            net = entry.best_milliseconds;
          } else if (hybrid == 0.0 || entry.best_milliseconds < hybrid) {
            hybrid = entry.best_milliseconds;
            at_percent = entry.fill_percent;
          }
        }
        if (ins == 0.0 || net == 0.0 || hybrid == 0.0) {
          continue;
        }
        auto const fixed_best = std::min(ins, net);
        std::printf("%-20s %8zu %5zu %9.2f %9.2f %11.2f %7.1f%% %8zu\n",
                    shape.c_str(), rows, columns, ins, net, hybrid,
                    100.0 * (fixed_best - hybrid) / fixed_best, at_percent);
      }
    }
  }
  std::printf("\nGain compares best-of-%d runs against the better fixed configuration.\n"
              "A positive gain means a per-leaf choice beat both; around zero means the\n"
              "better fixed leaf was already right for nearly every leaf in that shape.\n",
              repetitions);

  if (!csv_path.empty()) {
    std::ofstream csv(csv_path);
    csv << "shape,rows,columns,policy,fill_percent,median_ms,best_ms,ranges,"
           "below_threshold,leaves_to_network,leaves_to_insertion,network_padding\n";
    for (auto const & entry : table) {
      csv << entry.shape << ',' << entry.rows << ',' << entry.columns << ','
          << entry.policy << ',' << entry.fill_percent << ',' << entry.milliseconds << ','
          << entry.best_milliseconds << ',' << entry.metrics.ranges << ','
          << entry.metrics.below_threshold << ',' << entry.metrics.leaves_to_network << ','
          << entry.metrics.leaves_to_insertion << ',' << entry.metrics.network_padding << '\n';
    }
    std::printf("wrote %s\n", csv_path.c_str());
  }
  return 0;
}
