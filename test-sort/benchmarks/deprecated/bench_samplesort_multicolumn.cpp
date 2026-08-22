// Multi-column samplesort against the indirect quicksort, on the same problem.
//
// Both sort a table lexicographically by filling an index column and leaving the
// data untouched, so this is like-for-like: same datasets, same oracle, same
// detector. `std::sort` over row indices with a lexicographic comparator is the
// third column, as the scalar reference.
//
// Every configuration is verified against the reference image before it is timed.
//
//   ./bench_samplesort_multicolumn
//   ./bench_samplesort_multicolumn --rows 4194304 --cols 4
//   ./bench_samplesort_multicolumn --csv out.csv

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <numeric>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <vector>

#include "cosort_detectors.hpp"
#include "dataset_catalog.hpp"
#include "dataset_reference.hpp"
#include "dataset_source.hpp"
#include "sorting/quicksort/multicolumn_index_sort.hpp"
#include "sorting/sample_sort/samplesort_multicolumn.hpp"

namespace {

using Clock = std::chrono::steady_clock;
using Key = std::uint32_t;
using Simd = tsl::simd<Key, tsl::avx512>;
constexpr int repetitions = 5;

auto median(std::vector<double> samples) -> double {
  std::sort(samples.begin(), samples.end());
  return samples[samples.size() / 2];
}

struct row {
  std::string shape;
  std::size_t rows;
  std::size_t columns;
  std::string algorithm;
  std::size_t workers;
  double ns_per_element;
};

std::vector<row> g_rows;

void report(row entry, char const * note = "") {
  std::printf("%-26s %5zu %8zu %-26s %7zu %11.2f  %s\n", entry.shape.c_str(),
              entry.columns, entry.rows, entry.algorithm.c_str(), entry.workers,
              entry.ns_per_element, note);
  g_rows.push_back(std::move(entry));
}

// The image the permutation selects; the oracle every timed run is checked against.
auto image_of(std::vector<std::vector<Key>> const & columns,
              std::vector<Key> const & index) -> std::vector<std::vector<Key>> {
  std::vector<std::vector<Key>> out(columns.size());
  for (std::size_t column = 0; column < columns.size(); ++column) {
    out[column].resize(index.size());
    for (std::size_t at = 0; at < index.size(); ++at) {
      out[column][at] = columns[column][static_cast<std::size_t>(index[at])];
    }
  }
  return out;
}

template <class Run>
void measure(std::string const & shape, std::size_t rows, std::size_t columns,
             std::string const & algorithm, std::size_t workers,
             std::vector<std::vector<Key>> const & pristine,
             std::vector<std::vector<Key>> const & reference, Run && run) {
  std::vector<Key> index(rows);
  run(index);
  if (image_of(pristine, index) != reference) {
    std::printf("%-26s %5zu %8zu %-26s %7zu   INCORRECT\n", shape.c_str(), columns,
                rows, algorithm.c_str(), workers);
    return;
  }
  std::vector<double> samples;
  for (int rep = 0; rep < repetitions; ++rep) {
    std::fill(index.begin(), index.end(), Key{0});
    auto const start = Clock::now();
    run(index);
    auto const stop = Clock::now();
    samples.push_back(std::chrono::duration<double, std::nano>(stop - start).count()
                      / static_cast<double>(rows));
  }
  report(row{shape, rows, columns, algorithm, workers, median(samples)});
}

}  // namespace

int main(int argc, char ** argv) {
  std::size_t rows = 1u << 21;
  std::vector<std::size_t> column_counts{2, 4, 8};
  std::vector<std::string> shapes{"low_cardinality_d4", "unique_last_g64",
                                  "skewed_zipf_s1", "unique_first",
                                  "independent_uniform_c1024"};
  std::vector<std::size_t> worker_counts{1, 24};
  std::string csv_path;
  for (int i = 1; i < argc; ++i) {
    auto const flag = std::string(argv[i]);
    if (flag == "--rows" && i + 1 < argc) {
      rows = static_cast<std::size_t>(std::strtoull(argv[++i], nullptr, 10));
    } else if (flag == "--cols" && i + 1 < argc) {
      column_counts = {static_cast<std::size_t>(std::strtoull(argv[++i], nullptr, 10))};
    } else if (flag == "--shapes" && i + 1 < argc) {
      shapes.clear();
      std::string list = argv[++i];
      std::size_t start = 0;
      while (start <= list.size()) {
        auto const cut = list.find(',', start);
        auto const end = cut == std::string::npos ? list.size() : cut;
        if (end > start) {
          shapes.push_back(list.substr(start, end - start));
        }
        if (cut == std::string::npos) {
          break;
        }
        start = cut + 1;
      }
    } else if (flag == "--csv" && i + 1 < argc) {
      csv_path = argv[++i];
    } else {
      std::printf("unknown argument: %s\n", flag.c_str());
      return 2;
    }
  }

  std::printf("rows=%zu repetitions=%d  medians, ns per element\n\n", rows, repetitions);
  std::printf("%-26s %5s %8s %-26s %7s %11s\n", "shape", "cols", "rows",
              "algorithm", "workers", "ns/elem");

  TslDatasetSource<Key> source(6ull << 30);
  auto const tail = "_u" + std::to_string(sizeof(Key) * 8) + "_n";

  for (auto const & shape : shapes) {
    for (auto const columns : column_counts) {
      auto const catalog = tsl_default_catalog(rows, columns, sizeof(Key));
      TslDatasetSpec const * chosen = nullptr;
      for (auto const & spec : catalog) {
        if (spec.id.rfind(shape + tail, 0) == 0) {
          chosen = &spec;
          break;
        }
      }
      if (chosen == nullptr) {
        continue;
      }
      auto const pristine = source.pristine(*chosen);
      auto const reference = source.reference(*chosen, TslDirection::Ascending);

      std::vector<TslSortColumn<Key>> specs;
      for (auto const & column : *pristine) {
        specs.push_back(TslSortColumn<Key>{const_cast<Key *>(column.data()),
                                           TslSortOrder::ASCENDING});
      }

      for (auto const workers : worker_counts) {
        // The whole point of the multi-column driver is that the `rle=` axis
        // applies to it, so every synchronous backend this build has is measured.
        // Asynchronous ones are skipped: this driver never polls, so they would
        // never complete, which its own static_assert also says.
        for (auto const backend : tsl_compiled_detectors()) {
          if (tsl_detector_is_async(backend)) {
            continue;
          }
          TslDetectorConfig config;
          config.workers = workers;
          auto const label =
            std::string("samplesort mc rle=") + tsl_detector_name(backend);
          // A backend can be compiled in and still be unavailable: the IAA
          // hardware path needs a device and configured work queues, and throws
          // from its constructor when the host has neither. Report and move on
          // rather than taking the whole sweep down with it.
          try {
          tsl_with_detector<Key>(backend, config, [&](auto & detector) {
            using Detector = std::decay_t<decltype(detector)>;
            if constexpr (!tsl_detector_wants_executor<Detector>::value) {
              TslSampleSortMultiColumn<Key, Simd, 16> samplesort;
              measure(shape, rows, columns, label, workers, *pristine, *reference,
                      [&](std::vector<Key> & index) {
                        if (workers > 1) {
                          samplesort.sort_index_parallel(specs.data(), columns,
                                                         index.data(), rows, detector,
                                                         workers);
                        } else {
                          samplesort.sort_index(specs.data(), columns, index.data(),
                                                rows, detector);
                        }
                      });
            }
          });
          } catch (std::exception const & error) {
            std::printf("%-26s %5zu %8zu %-26s %7zu   unavailable: %s\n",
                        shape.c_str(), columns, rows, label.c_str(), workers,
                        error.what());
          }
        }

        TslMultiColumnIndexSorter<Key, TslPartitionKind::THREE_WAY,
                                  TslLeafKind::NETWORK, Simd> quicksort(0x5A3F1E77);
        measure(shape, rows, columns, "quicksort index (net)", workers, *pristine,
                *reference, [&](std::vector<Key> & index) {
                  TslIndexScalarDetector<Key> detector;
                  if (workers > 1) {
                    quicksort.sort_index_parallel(specs.data(), columns, index.data(),
                                                  rows, TslRunDiscoveryKind::POST_SORT,
                                                  detector, workers, 16384);
                  } else {
                    quicksort.sort_index(specs.data(), columns, index.data(), rows,
                                         TslRunDiscoveryKind::POST_SORT, detector);
                  }
                });
      }

      // The scalar reference: sort row indices by a lexicographic comparator.
      measure(shape, rows, columns, "std::sort lexicographic", 1, *pristine,
              *reference, [&](std::vector<Key> & index) {
                std::iota(index.begin(), index.end(), Key{0});
                auto const & data = *pristine;
                std::sort(index.begin(), index.end(), [&](Key left, Key right) {
                  for (std::size_t column = 0; column < data.size(); ++column) {
                    if (data[column][left] != data[column][right]) {
                      return data[column][left] < data[column][right];
                    }
                  }
                  return false;
                });
              });
      std::printf("\n");
    }
  }

  if (!csv_path.empty()) {
    std::ofstream csv(csv_path);
    csv << "shape,rows,columns,algorithm,workers,ns_per_element\n";
    for (auto const & entry : g_rows) {
      csv << entry.shape << ',' << entry.rows << ',' << entry.columns << ','
          << entry.algorithm << ',' << entry.workers << ',' << entry.ns_per_element
          << '\n';
    }
    std::printf("wrote %s\n", csv_path.c_str());
  }
  return 0;
}
