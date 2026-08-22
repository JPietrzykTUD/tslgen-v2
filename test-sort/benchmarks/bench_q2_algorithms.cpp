// Q2: quicksort or samplesort -- which, where, and why?
//
// Both sort a table lexicographically by filling an index column and leaving the
// data untouched, so this is like-for-like. What made the earlier numbers hard to
// defend is that they came from different grids: the samplesort sweeps used their
// own row counts and shapes while the corpus uses cache-derived size levels. This
// drives both over one grid.
//
// Each samplesort row carries its phase split -- materialise, sort, detect --
// because the interesting result is not which wins but why. The quicksort rows
// carry no split yet: `TslMultiColumnIndexSorter` has no phase timing, and adding
// it to a header the whole corpus instantiates is a change of its own. So the
// attribution here is one-sided, and says so.
//
//   ./bench_q2_algorithms
//   ./bench_q2_algorithms --rows 1048576 --cols 4 --shapes skewed_zipf_s1
//   ./bench_q2_algorithms --all --csv results/q2_algorithms.csv

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <numeric>
#include <string>
#include <vector>

#include "dataset_catalog.hpp"
#include "dataset_reference.hpp"
#include "dataset_source.hpp"
#include "paper_harness.hpp"
#include "sorting/quicksort/multicolumn_index_sort.hpp"
#include "sorting/sample_sort/samplesort_multicolumn.hpp"

namespace {

// Shape classes rather than every parameterisation: opposite range structures,
// which is what separates the two algorithms. `--all` takes the whole catalog.
auto default_shapes() -> std::vector<std::string> {
  return {"tpcds_q67_sf1", "tpcds_q67_sf100",
          "unique_first", "unique_last_g2", "unique_last_g64", "unique_last_g4096",
          "independent_uniform_c16", "independent_uniform_c1024",
          "independent_uniform_c65536", "balanced_hierarchy_c64",
          "skewed_zipf_s0.5", "skewed_zipf_s1", "skewed_zipf_s2",
          "heavy_hitter_f90", "low_cardinality_d4"};
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

template <class Key>
auto image_matches(std::vector<std::vector<Key>> const & columns,
                   std::vector<std::vector<Key>> const & reference,
                   std::vector<Key> const & index) -> bool {
  for (std::size_t column = 0; column < columns.size(); ++column) {
    for (std::size_t at = 0; at < index.size(); ++at) {
      if (columns[column][static_cast<std::size_t>(index[at])]
          != reference[column][at]) {
        return false;
      }
    }
  }
  return true;
}

template <class Key>
void run_grid(TslPaperResults & results, std::vector<std::string> const & shapes,
              std::vector<std::size_t> const & row_counts,
              std::vector<std::size_t> const & column_counts,
              std::vector<std::size_t> const & worker_counts) {
  using Simd = tsl::simd<Key, tsl::avx512>;
  TslDatasetSource<Key> source(8ull << 30);
  auto const tail = "_u" + std::to_string(sizeof(Key) * 8) + "_n";

  for (auto const & shape : shapes) {
    for (auto const rows : row_counts) {
      for (auto const columns : column_counts) {
        auto const catalog = tsl_default_catalog(rows, columns, sizeof(Key));
        TslDatasetSpec const * spec = nullptr;
        for (auto const & candidate : catalog) {
          if (candidate.id.rfind(shape + tail, 0) == 0) {
            spec = &candidate;
            break;
          }
        }
        auto blank = results.make_row();
        blank.shape = shape;
        blank.rows = rows;
        blank.columns = columns;
        blank.element_bytes = sizeof(Key);
        if (spec == nullptr) {
          blank.algorithm = "-";
          results.drop(blank, "no such dataset at this size and column count");
          continue;
        }
        // `params` is a name->value map; flatten it so one CSV column carries it.
        for (auto const & [name, value] : spec->params) {
          if (!blank.shape_params.empty()) {
            blank.shape_params += ';';
          }
          auto text = std::to_string(value);
          // Trim the trailing zeros std::to_string leaves on a double.
          if (text.find('.') != std::string::npos) {
            text.erase(text.find_last_not_of('0') + 1);
            if (!text.empty() && text.back() == '.') {
              text.pop_back();
            }
          }
          blank.shape_params += name + '=' + text;
        }

        auto const pristine = source.pristine(*spec);
        auto const reference = source.reference(*spec, TslDirection::Ascending);
        std::vector<TslSortColumn<Key>> specs;
        for (auto const & column : *pristine) {
          specs.push_back(TslSortColumn<Key>{const_cast<Key *>(column.data()),
                                             TslSortOrder::ASCENDING});
        }

        for (auto const workers : worker_counts) {
          std::vector<Key> index(rows);

          // ---- samplesort, with its phase split ----
          {
            auto row = blank;
            row.algorithm = "samplesort";
            row.variant = "K=16/adaptive/net";
            row.detector = "scalar";
            row.workers = workers;
            TslSampleSortMultiColumn<Key, Simd, 16, TslSampleSortBuckets::Adaptive, 8,
                                     256, TslSampleSortBase::Network,
                                     TslSampleSortIds::Byte,
                                     256 / Simd::lane_count_v, 50, true> sorter;
            TslSampleSortColumnMetrics metrics;
            auto const [ok, stats] = tsl_paper_measure(
              [&] {
                TslIndexScalarDetector<Key> detector;
                metrics = {};
                if (workers > 1) {
                  sorter.sort_index_parallel(specs.data(), columns, index.data(), rows,
                                             detector, workers, &metrics);
                } else {
                  sorter.sort_index(specs.data(), columns, index.data(), rows,
                                    detector, &metrics);
                }
              },
              [&] { return image_matches(*pristine, *reference, index); }, rows);
            row.verified = ok;
            row.ns_per_element = stats;
            row.ns_materialize = metrics.ns_materialize / static_cast<double>(rows);
            row.ns_sort = metrics.ns_sort / static_cast<double>(rows);
            row.ns_detect = metrics.ns_detect / static_cast<double>(rows);
            results.add(std::move(row));
          }

          // ---- the indirect quicksort, the sorter this has to beat ----
          {
            auto row = blank;
            row.algorithm = "quicksort";
            row.variant = "3way/net/post";
            row.detector = "scalar";
            row.workers = workers;
            TslMultiColumnIndexSorter<Key, TslPartitionKind::THREE_WAY,
                                      TslLeafKind::NETWORK, Simd> sorter(0x5A3F1E77);
            auto const [ok, stats] = tsl_paper_measure(
              [&] {
                TslIndexScalarDetector<Key> detector;
                if (workers > 1) {
                  sorter.sort_index_parallel(specs.data(), columns, index.data(), rows,
                                             TslRunDiscoveryKind::POST_SORT, detector,
                                             workers, 16384);
                } else {
                  sorter.sort_index(specs.data(), columns, index.data(), rows,
                                    TslRunDiscoveryKind::POST_SORT, detector);
                }
              },
              [&] { return image_matches(*pristine, *reference, index); }, rows);
            row.verified = ok;
            row.ns_per_element = stats;
            results.add(std::move(row));
          }
        }

        // ---- the scalar reference, once per dataset ----
        {
          auto row = blank;
          row.algorithm = "std::sort lexicographic";
          row.detector = "-";
          row.workers = 1;
          std::vector<Key> index(rows);
          auto const & data = *pristine;
          auto const [ok, stats] = tsl_paper_measure(
            [&] {
              std::iota(index.begin(), index.end(), Key{0});
              std::sort(index.begin(), index.end(), [&](Key left, Key right) {
                for (std::size_t column = 0; column < data.size(); ++column) {
                  if (data[column][left] != data[column][right]) {
                    return data[column][left] < data[column][right];
                  }
                }
                return false;
              });
            },
            [&] { return image_matches(*pristine, *reference, index); }, rows);
          row.verified = ok;
          row.ns_per_element = stats;
          results.add(std::move(row));
        }
      }
    }
  }
}

}  // namespace

int main(int argc, char ** argv) {
  std::vector<std::string> shapes = default_shapes();
  std::vector<std::size_t> row_counts{1u << 20, 1u << 23};
  std::vector<std::size_t> column_counts{2, 4, 8};
  std::vector<std::size_t> worker_counts{1, 24};
  std::vector<std::size_t> widths{4, 8};
  std::string csv_path;

  for (int i = 1; i < argc; ++i) {
    auto const flag = std::string(argv[i]);
    auto const value = [&]() -> std::string { return i + 1 < argc ? argv[++i] : ""; };
    if (flag == "--shapes") {
      shapes = split(value(), ',');
    } else if (flag == "--rows") {
      row_counts.clear();
      for (auto const & part : split(value(), ',')) {
        row_counts.push_back(std::strtoull(part.c_str(), nullptr, 10));
      }
    } else if (flag == "--cols") {
      column_counts.clear();
      for (auto const & part : split(value(), ',')) {
        column_counts.push_back(std::strtoull(part.c_str(), nullptr, 10));
      }
    } else if (flag == "--workers") {
      worker_counts.clear();
      for (auto const & part : split(value(), ',')) {
        worker_counts.push_back(std::strtoull(part.c_str(), nullptr, 10));
      }
    } else if (flag == "--widths") {
      widths.clear();
      for (auto const & part : split(value(), ',')) {
        widths.push_back(std::strtoull(part.c_str(), nullptr, 10));
      }
    } else if (flag == "--csv") {
      csv_path = value();
    } else if (flag == "--all") {
      shapes.clear();  // an empty selector means every shape the catalog offers
    } else {
      std::printf("unknown argument: %s\n", flag.c_str());
      return 2;
    }
  }

  TslPaperResults results("Q2 algorithms", "bench_q2_algorithms");

  if (shapes.empty()) {
    // Every shape at the smallest requested size and column count, so `--all`
    // stays runnable; widen the other axes explicitly.
    auto const catalog = tsl_default_catalog(row_counts.front(),
                                             column_counts.front(), 4);
    auto const tail = std::string("_u32_n");
    for (auto const & spec : catalog) {
      auto const cut = spec.id.find(tail);
      if (cut != std::string::npos) {
        shapes.push_back(spec.id.substr(0, cut));
      }
    }
    std::printf("--all: %zu shapes\n", shapes.size());
  }

  for (auto const width : widths) {
    if (width == 4) {
      run_grid<std::uint32_t>(results, shapes, row_counts, column_counts,
                              worker_counts);
    } else if (width == 8) {
      run_grid<std::uint64_t>(results, shapes, row_counts, column_counts,
                              worker_counts);
    } else {
      std::printf("unsupported element width: %zu\n", width);
    }
  }

  std::printf("\n%s\n", results.summary().c_str());
  if (!csv_path.empty()) {
    results.write_csv(csv_path);
  }
  return 0;
}
