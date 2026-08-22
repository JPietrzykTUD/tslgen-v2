// Q4: how does it scale in threads, rows, columns and element width?
//
// Four axes, each swept with the others pinned, because a grid over all four is
// mostly cells nobody reads. Three shapes with opposite range structure, so a
// plateau can be attributed to the data rather than to the machine:
// `low_cardinality_d4` recurses to the last column, `independent_uniform_c1024`
// splits wide and shallow, `skewed_zipf_s1` is heavy-tailed.
//
// Speedup is reported against this driver's own single-thread row for the same
// cell, so the thread axis is self-normalising and a cross-machine reader does
// not have to trust an absolute. The phase split travels with every row, because
// a thread curve that flattens is only interesting once you know which phase
// stopped scaling.
//
//   ./bench_q4_scaling
//   ./bench_q4_scaling --axis threads --shapes skewed_zipf_s1
//   ./bench_q4_scaling --csv results/q4_scaling.csv

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <map>
#include <string>
#include <vector>

#include "dataset_catalog.hpp"
#include "dataset_reference.hpp"
#include "dataset_source.hpp"
#include "paper_harness.hpp"
#include "sorting/quicksort/multicolumn_index_sort.hpp"
#include "sorting/sample_sort/samplesort_multicolumn.hpp"
#include "tuned_config.hpp"
#include "tuned_dispatch.hpp"

// Phase attribution is a build-time choice, not a runtime one: it selects a
// different instantiation of both sorters. It is off unless asked for, because
// the timers cost 1.08x-1.28x on the samplesort and up to 1.79x on the quicksort
// -- enough to move a conclusion. Build with -DTSL_COSORT_PHASES=true when
// attributing time; the published numbers come from a build without it.
#if !defined(TSL_COSORT_PHASES)
#define TSL_COSORT_PHASES false
#endif

namespace {

// The configuration bench_q0_tune chose. Scaling is measured on the sorter we
// would ship, not on whichever instantiation happened to be typed here: this
// driver previously hard-coded a network leaf, which the descent showed is up to
// 6.6x slower than the insertion leaf on real keys, so its thread-scaling
// crossover was a comparison between a tuned samplesort and a mis-configured
// quicksort.
TslTunedConfig g_samplesort_config;
TslTunedConfig g_quicksort_config;

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

struct cell {
  std::string shape;
  std::size_t rows;
  std::size_t columns;
  std::size_t workers;
};

// One measurement of both algorithms over one cell.
template <class Key>
void measure_cell(TslPaperResults & results, TslDatasetSource<Key> & source,
                  cell const & where, std::map<std::string, double> & serial,
                  TslDatasetSpec const * external = nullptr) {
  using Simd = tsl::simd<Key, tsl::avx512>;
  auto const tail = "_u" + std::to_string(sizeof(Key) * 8) + "_n";
  // A measured dataset comes with its own row and column count, so it is passed
  // in rather than looked up by size. That makes it usable on the thread axis --
  // where rows and columns are held fixed anyway -- and not on the row or column
  // axes, which would have to invent data the query never produced.
  auto const catalog = external != nullptr
                         ? std::vector<TslDatasetSpec>{}
                         : tsl_default_catalog(where.rows, where.columns, sizeof(Key));
  TslDatasetSpec const * spec = external;
  for (auto const & candidate : catalog) {
    if (candidate.id.rfind(where.shape + tail, 0) == 0) {
      spec = &candidate;
      break;
    }
  }
  auto blank = results.make_row();
  blank.shape = where.shape;
  blank.rows = where.rows;
  blank.columns = where.columns;
  blank.element_bytes = sizeof(Key);
  blank.workers = where.workers;
  blank.detector = "scalar";
  if (spec == nullptr) {
    blank.algorithm = "-";
    results.drop(blank, "no such dataset at this size and column count");
    return;
  }

  auto const pristine = source.pristine(*spec);
  auto const reference = source.reference(*spec, TslDirection::Ascending);
  std::vector<TslSortColumn<Key>> specs;
  for (auto const & column : *pristine) {
    specs.push_back(TslSortColumn<Key>{const_cast<Key *>(column.data()),
                                       TslSortOrder::ASCENDING});
  }
  std::vector<Key> index(where.rows);

  auto const key = [&](char const * algorithm) {
    return std::string(algorithm) + "/" + where.shape + "/"
           + std::to_string(where.rows) + "/" + std::to_string(where.columns) + "/"
           + std::to_string(sizeof(Key));
  };

  {
    auto row = blank;
    row.algorithm = "samplesort";
    row.variant = g_samplesort_config.describe_samplesort()
                  + (g_samplesort_config.from_file ? " (tuned)" : " (default)");
    TslSampleSortColumnMetrics metrics;
    bool measured_ok = false;
    TslPaperStats measured{};
    auto const dispatched = with_samplesort<Key, Simd, TSL_COSORT_PHASES>(
      g_samplesort_config, [&](auto sorter) {
        auto const [ok, stats] = tsl_paper_measure(
          [&] {
            TslIndexScalarDetector<Key> detector;
            metrics = {};
            if (where.workers > 1) {
              sorter.sort_index_parallel(specs.data(), where.columns, index.data(),
                                         where.rows, detector, where.workers,
                                         &metrics);
            } else {
              sorter.sort_index(specs.data(), where.columns, index.data(),
                                where.rows, detector, &metrics);
            }
          },
          [&] { return image_matches(*pristine, *reference, index); }, where.rows);
        measured_ok = ok;
        measured = stats;
      });
    if (!dispatched) {
      auto drop = row;
      results.drop(drop, "tuned samplesort configuration is not instantiated here: "
                         + g_samplesort_config.describe_samplesort());
    } else if (!measured_ok) {
      auto drop = row;
      results.drop(drop, "sorted wrongly");
    } else {
      row.ns_per_element = measured;
      // Per element, as Q2 reports them: the CSV column is shared, so the unit
      // has to be too or a figure joining the two silently mixes scales.
      auto const sscale = static_cast<double>(where.rows);
      row.ns_materialize = metrics.ns_materialize / sscale;
      row.ns_sort = metrics.ns_sort / sscale;
      row.ns_detect = metrics.ns_detect / sscale;
      row.verified = true;
      double sample_speedup = 0.0;
      if (where.workers == 1) {
        serial[key("samplesort")] = measured.median;
      } else if (auto const found = serial.find(key("samplesort"));
                 found != serial.end() && measured.median > 0.0) {
        sample_speedup = found->second / measured.median;
      }
      results.add(std::move(row));
      if (sample_speedup > 0.0) {
        std::printf("%76s speedup %.2fx vs its own 1 worker\n", "",
                    sample_speedup);
      }
    }
  }

  {
    auto row = blank;
    row.algorithm = "quicksort";
    row.variant = g_quicksort_config.describe_quicksort()
                  + (g_quicksort_config.from_file ? " (tuned)" : " (default)");
    bool measured_ok = false;
    TslPaperStats measured{};
    TslIndexSortMetrics quick_metrics;
    auto const dispatched = with_quicksort_leaf<Key, Simd, TSL_COSORT_PHASES>(
      g_quicksort_config, [&](auto sorter) {
        auto const [ok, stats] = tsl_paper_measure(
          [&] {
            TslIndexScalarDetector<Key> detector;
            quick_metrics = {};
            if (where.workers > 1) {
              sorter.sort_index_parallel(specs.data(), where.columns, index.data(),
                                         where.rows, g_quicksort_config.discovery,
                                         detector, where.workers,
                                         g_quicksort_config.partition_threshold,
                                         &quick_metrics);
            } else {
              sorter.sort_index(specs.data(), where.columns, index.data(),
                                where.rows, g_quicksort_config.discovery, detector,
                                &quick_metrics);
            }
          },
          [&] { return image_matches(*pristine, *reference, index); }, where.rows);
        measured_ok = ok;
        measured = stats;
      });
    double speedup = 0.0;
    if (!dispatched) {
      results.drop(row, "tuned quicksort configuration is not instantiated here: "
                        + g_quicksort_config.describe_quicksort());
    } else if (!measured_ok) {
      results.drop(row, "sorted wrongly");
    } else {
      row.verified = true;
      row.ns_per_element = measured;
      auto const qscale = static_cast<double>(where.rows);
      row.ns_materialize = quick_metrics.ns_materialize / qscale;
      row.ns_sort = quick_metrics.ns_sort / qscale;
      row.ns_detect = quick_metrics.ns_detect / qscale;
      if (where.workers == 1) {
        serial[key("quicksort")] = measured.median;
      } else if (auto const found = serial.find(key("quicksort"));
                 found != serial.end() && measured.median > 0.0) {
        speedup = found->second / measured.median;
      }
      results.add(std::move(row));
    }
    // After the row, so the two read together.
    if (speedup > 0.0) {
      std::printf("%76s speedup %.2fx vs its own 1 worker\n", "", speedup);
    }
  }
}

template <class Key>
void run_width(TslPaperResults & results, std::string const & tpcds_dir,
               std::vector<std::string> const & shapes,
               std::string const & axis, std::size_t base_rows,
               std::size_t base_columns) {
  TslDatasetSource<Key> source(12ull << 30);
  std::map<std::string, double> serial;

  for (auto const & shape : shapes) {
    if (axis == "threads" || axis == "all") {
      std::printf("\n-- threads, %s, %zu rows, %zu columns, u%zu --\n", shape.c_str(),
                  base_rows, base_columns, sizeof(Key) * 8);
      for (std::size_t workers : {1u, 2u, 4u, 8u, 16u, 24u}) {
        measure_cell<Key>(results, source, {shape, base_rows, base_columns, workers},
                          serial);
      }
    }
    if (axis == "rows" || axis == "all") {
      std::printf("\n-- rows, %s, %zu columns, u%zu --\n", shape.c_str(),
                  base_columns, sizeof(Key) * 8);
      for (std::size_t rows : {1u << 18, 1u << 20, 1u << 22, 1u << 24}) {
        for (std::size_t workers : {1u, 24u}) {
          measure_cell<Key>(results, source, {shape, rows, base_columns, workers},
                            serial);
        }
      }
    }
    if (axis == "columns" || axis == "all") {
      std::printf("\n-- columns, %s, %zu rows, u%zu --\n", shape.c_str(), base_rows,
                  sizeof(Key) * 8);
      for (std::size_t columns : {1u, 2u, 4u, 8u, 16u}) {
        for (std::size_t workers : {1u, 24u}) {
          measure_cell<Key>(results, source, {shape, base_rows, columns, workers},
                            serial);
        }
      }
    }
  }

  // Real query keys, thread axis only. This is where the crossover lives: the
  // synthetic shapes are duplicate-heavy in a uniform way and the quicksort wins
  // them at every thread count, while a measured key's skew is what lets the
  // samplesort's wider fan-out pay above a thread count.
  if (!tpcds_dir.empty() && (axis == "threads" || axis == "all")) {
    auto const measured = tsl_external_catalog(tpcds_dir, sizeof(Key));
    for (auto const & spec : measured) {
      std::printf("\n-- threads, %s, %zu rows, %zu columns, u%zu (measured) --\n",
                  spec.id.c_str(), spec.rows, spec.columns, sizeof(Key) * 8);
      for (std::size_t workers : {1u, 2u, 4u, 8u, 16u, 24u}) {
        measure_cell<Key>(results, source,
                          {spec.id, spec.rows, spec.columns, workers}, serial,
                          &spec);
      }
    }
  }
}

}  // namespace

int main(int argc, char ** argv) {
  std::vector<std::string> shapes{"tpcds_q67_sf1", "low_cardinality_d4",
                                  "independent_uniform_c1024", "skewed_zipf_s1"};
  std::string axis = "all";
  std::size_t base_rows = 1u << 21;
  std::size_t base_columns = 4;
  std::vector<std::size_t> widths{4, 8};
  std::string csv_path;
  std::string tuned_path = "best_config.tsv";
  std::string tpcds_dir;

  for (int i = 1; i < argc; ++i) {
    auto const flag = std::string(argv[i]);
    auto const value = [&]() -> std::string { return i + 1 < argc ? argv[++i] : ""; };
    if (flag == "--shapes") {
      shapes = split(value(), ',');
    } else if (flag == "--axis") {
      axis = value();
    } else if (flag == "--rows") {
      base_rows = std::strtoull(value().c_str(), nullptr, 10);
    } else if (flag == "--cols") {
      base_columns = std::strtoull(value().c_str(), nullptr, 10);
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
    } else {
      std::printf("unknown argument: %s\n", flag.c_str());
      return 2;
    }
  }

  TslPaperResults results("Q4 scaling", "bench_q4_scaling");

  // The tuned configuration, or the defaults with every row labelled "(default)"
  // so a run without Q0 cannot be mistaken for a tuned one.
  {
    auto const tuned = tsl_read_tuned(tuned_path);
    if (tuned.empty()) {
      std::printf("no %s: measuring defaults, rows labelled (default)\n",
                  tuned_path.c_str());
    } else {
      std::printf("tuned configurations from %s\n", tuned_path.c_str());
    }
    g_samplesort_config = tsl_tuned_for(tuned, "samplesort", TslStyle::Intrinsics,
                                        512, 4);
    g_quicksort_config = tsl_tuned_for(tuned, "quicksort", TslStyle::Intrinsics,
                                       512, 4);
  }
  for (auto const width : widths) {
    if (width == 4) {
      run_width<std::uint32_t>(results, tpcds_dir, shapes, axis, base_rows, base_columns);
    } else if (width == 8) {
      run_width<std::uint64_t>(results, tpcds_dir, shapes, axis, base_rows, base_columns);
    }
  }
  std::printf("\n%s\n", results.summary().c_str());
  if (!csv_path.empty()) {
    results.write_csv(csv_path);
  }
  return 0;
}
