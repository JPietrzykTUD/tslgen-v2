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
#include "tuned_config.hpp"
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

// The configuration bench_q0_tune chose, or the defaults when it has not run.
// This is not a convenience: hard-coding a knob here is how the first version of
// this driver came to report the quicksort with a network leaf on keys where the
// insertion leaf is up to 6.6x faster, which made a comparison look like a result.
TslTunedConfig g_samplesort_config;
TslTunedConfig g_quicksort_config;
bool g_tuned_from_file = false;

// Only the axes the descent found decisive are dispatched here; a configuration
// asking for anything else is reported rather than silently replaced.
template <class Key, class Simd, class Run>
auto with_quicksort_leaf(TslTunedConfig const & config, Run && run) -> bool {
  constexpr auto three = TslPartitionKind::THREE_WAY;
  if (config.partition != three) {
    return false;
  }
  if (config.hybrid_leaf) {
    run(TslMultiColumnIndexSorter<Key, three, TslLeafKind::NETWORK, Simd,
                                  tsl_hybrid_auto_percent<Key, Simd>()>(0x5A3F1E77));
  } else if (config.leaf == TslLeafKind::INSERTION) {
    run(TslMultiColumnIndexSorter<Key, three, TslLeafKind::INSERTION, Simd>(0x5A3F1E77));
  } else {
    run(TslMultiColumnIndexSorter<Key, three, TslLeafKind::NETWORK, Simd>(0x5A3F1E77));
  }
  return true;
}

template <class Key, class Simd, class Run>
auto with_samplesort(TslTunedConfig const & config, Run && run) -> bool {
  constexpr auto adaptive = TslSampleSortBuckets::Adaptive;
  constexpr auto byte_ids = TslSampleSortIds::Byte;
  constexpr auto oop = TslSampleSortMovement::OutOfPlace;
  constexpr std::size_t lanes = Simd::lane_count_v;
  if (config.k != 16 || config.buckets != adaptive || config.ids != byte_ids
      || config.movement != oop) {
    return false;
  }
  auto const net = config.base_policy == TslSampleSortBase::Network;
#define TSL_Q2_SS(BC, P)                                                            run(TslSampleSortMultiColumn<Key, Simd, 16, adaptive, 8, BC, P, byte_ids,                                       BC / lanes, 50, oop, true>{})
  if (config.base_case == 64) {
    if (net) { TSL_Q2_SS(64, TslSampleSortBase::Network); }
    else { TSL_Q2_SS(64, TslSampleSortBase::Insertion); }
  } else if (config.base_case == 128) {
    if (net) { TSL_Q2_SS(128, TslSampleSortBase::Network); }
    else { TSL_Q2_SS(128, TslSampleSortBase::Insertion); }
  } else if (config.base_case == 256) {
    if (net) { TSL_Q2_SS(256, TslSampleSortBase::Network); }
    else { TSL_Q2_SS(256, TslSampleSortBase::Insertion); }
  } else {
    return false;
  }
#undef TSL_Q2_SS
  return true;
}

// Both algorithms plus the scalar reference over one dataset. Shared so a
// measured key and a generated one go through exactly the same measurement.
template <class Key>
void run_pair(TslPaperResults & results, TslDatasetSource<Key> & source,
              TslDatasetSpec const & spec, TslPaperRow const & blank,
              std::vector<std::size_t> const & worker_counts) {
  using Simd = tsl::simd<Key, tsl::avx512>;
  auto const columns = spec.columns;
  auto const rows = spec.rows;
  auto const pristine = source.pristine(spec);
  auto const reference = source.reference(spec, TslDirection::Ascending);
  std::vector<TslSortColumn<Key>> specs;
  for (auto const & column : *pristine) {
    specs.push_back(TslSortColumn<Key>{const_cast<Key *>(column.data()),
                                       TslSortOrder::ASCENDING});
  }

  for (auto const workers : worker_counts) {
    std::vector<Key> index(rows);
    {
      auto row = blank;
      row.algorithm = "samplesort";
      row.detector = "scalar";
      row.workers = workers;
      row.variant = g_samplesort_config.describe_samplesort()
                    + (g_tuned_from_file ? " (tuned)" : " (default)");
      TslSampleSortColumnMetrics metrics;
      auto const dispatched = with_samplesort<Key, Simd>(
        g_samplesort_config, [&](auto sorter) {
          auto const [ok, stats] = tsl_paper_measure(
            [&] {
              TslIndexScalarDetector<Key> detector;
              metrics = {};
              if (workers > 1) {
                sorter.sort_index_parallel(specs.data(), columns, index.data(), rows,
                                           detector, workers, &metrics);
              } else {
                sorter.sort_index(specs.data(), columns, index.data(), rows, detector,
                                  &metrics);
              }
            },
            [&] { return image_matches(*pristine, *reference, index); }, rows);
          row.verified = ok;
          row.ns_per_element = stats;
          auto const scale = static_cast<double>(rows);
          row.ns_materialize = metrics.ns_materialize / scale;
          row.ns_sort = metrics.ns_sort / scale;
          row.ns_detect = metrics.ns_detect / scale;
        });
      if (dispatched) {
        results.add(std::move(row));
      } else {
        results.drop(row, "tuned configuration is not instantiated in this driver: "
                          + g_samplesort_config.describe_samplesort());
      }
    }
    {
      auto row = blank;
      row.algorithm = "quicksort";
      row.detector = "scalar";
      row.workers = workers;
      row.variant = g_quicksort_config.describe_quicksort()
                    + (g_tuned_from_file ? " (tuned)" : " (default)");
      auto const dispatched = with_quicksort_leaf<Key, Simd>(
        g_quicksort_config, [&](auto sorter) {
          auto const [ok, stats] = tsl_paper_measure(
            [&] {
              TslIndexScalarDetector<Key> detector;
              if (workers > 1) {
                sorter.sort_index_parallel(specs.data(), columns, index.data(), rows,
                                           g_quicksort_config.discovery, detector,
                                           workers,
                                           g_quicksort_config.partition_threshold);
              } else {
                sorter.sort_index(specs.data(), columns, index.data(), rows,
                                  g_quicksort_config.discovery, detector);
              }
            },
            [&] { return image_matches(*pristine, *reference, index); }, rows);
          row.verified = ok;
          row.ns_per_element = stats;
        });
      if (dispatched) {
        results.add(std::move(row));
      } else {
        results.drop(row, "tuned configuration is not instantiated in this driver: "
                          + g_quicksort_config.describe_quicksort());
      }
    }
  }
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


// The measured keys, read rather than generated. Their row count and column count
// come from the data, so they ignore the grid's rows/cols axes -- a real key has
// the width the query gives it.
template <class Key>
void run_external(TslPaperResults & results, std::string const & directory,
                  std::vector<std::size_t> const & worker_counts) {
  TslDatasetSource<Key> source(12ull << 30);
  for (auto const & spec : tsl_external_catalog(directory, sizeof(Key))) {
    auto blank = results.make_row();
    blank.shape = spec.id.substr(0, spec.id.find("_u"));
    blank.shape_params = "measured";
    blank.rows = spec.rows;
    blank.columns = spec.columns;
    blank.element_bytes = sizeof(Key);
    try {
      run_pair<Key>(results, source, spec, blank, worker_counts);
    } catch (std::exception const & error) {
      auto row = blank;
      row.algorithm = "-";
      results.drop(row, std::string("could not read: ") + error.what());
    }
  }
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

        run_pair<Key>(results, source, *spec, blank, worker_counts);
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
  std::string tpcds_dir;
  std::string tuned_path = "best_config.tsv";

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
    } else if (flag == "--element-bytes" || flag == "--widths") {
      // `--widths` was the old name and meant element *bytes*, which reads as
      // register width and misled a reader into thinking these drivers sweep
      // 128/256/512. They do not: register width is bench_q0_tune's axis and
      // bench_q6_portability's. Kept as an alias so old command lines still work.
      if (flag == "--widths") {
        std::printf("note: --widths means element bytes; prefer --element-bytes\n");
      }
      widths.clear();
      for (auto const & part : split(value(), ',')) {
        widths.push_back(std::strtoull(part.c_str(), nullptr, 10));
      }
    } else if (flag == "--tuned") {
      tuned_path = value();
    } else if (flag == "--tpcds-dir") {
      tpcds_dir = value();
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

  // Read the descent's answer. Without it the defaults are used and every row
  // says "(default)", so a figure can never quietly rest on an untuned knob.
  auto const tuned = tsl_read_tuned(tuned_path);
  g_samplesort_config = tsl_tuned_for(tuned, "samplesort", TslStyle::Intrinsics, 512, 4);
  g_quicksort_config = tsl_tuned_for(tuned, "quicksort", TslStyle::Intrinsics, 512, 4);
  g_tuned_from_file = g_samplesort_config.from_file || g_quicksort_config.from_file;
  std::printf("tuning: %s\n  samplesort %s\n  quicksort  %s\n",
              g_tuned_from_file ? tuned_path.c_str()
                                : "not found, using defaults",
              g_samplesort_config.describe_samplesort().c_str(),
              g_quicksort_config.describe_quicksort().c_str());

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
      if (!tpcds_dir.empty()) {
        run_external<std::uint32_t>(results, tpcds_dir, worker_counts);
      }
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
