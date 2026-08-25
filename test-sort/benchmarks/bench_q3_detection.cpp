// Q3: what does cluster detection cost, and does offloading it pay?
//
// This is built to *look for* a regime where offload pays, not to confirm one.
// What is already measured argues the other way: detection is 0.5-10.4% of the
// multi-column samplesort and about 1.7% of the direct quicksort, `iaa_sw` and
// `iaa_freq_sw` land inside scalar's noise, and `dml_sw` has been up to 23x
// worse. A sweep over backends alone would only restate that. So the outer axes
// are the things that make detection *expensive* -- distinct-value count, element
// width, column count -- and the backends are the inner loop.
//
// The first number every row carries is detection's share of the runtime, from
// the driver's own phase timing. That share is the ceiling on what any backend
// can win, and reporting it first keeps a 2x speedup on 2% of the runtime from
// being read as a 2x speedup.
//
// **Hardware paths only, by default.** The software paths are QPL's and DML's own
// CPU implementations: they exist so a backend can be checked for correctness
// without the device, and a published figure that includes them is comparing our
// scalar scan against somebody else's scalar scan. `--paths sw` and `--paths all`
// are there for the correctness case and for curiosity.
//
// Which hardware exists is per machine and no machine here has both: this host
// has DSA and no `/dev/iax`, the IAA host has the reverse. So the paper's
// accelerator table is assembled from two runs, and each row records the host it
// came from. Where a device is absent the row is emitted as a drop with the
// reason, so a run on the wrong machine cannot be mistaken for a backend that
// lost.
//
//   ./bench_q3_detection
//   ./bench_q3_detection --cardinalities 16,1024,65536 --cols 8
//   ./bench_q3_detection --csv results/q3_detection.csv

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <vector>

#include "tsl_simd_for.hpp"
#include "cosort_detectors.hpp"
#include "dataset_catalog.hpp"
#include "dataset_reference.hpp"
#include "dataset_source.hpp"
#include "paper_harness.hpp"
#include "tuned_config.hpp"
#include "tuned_dispatch.hpp"
#include "sorting/sample_sort/samplesort_multicolumn.hpp"

namespace {

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

// Distinct-value count is the axis that moves detection's cost: a run detector
// walks one step per distinct value, and the scan it replaces walks one per
// element. `independent_uniform_cN` is the catalog's knob for exactly that.
auto cardinality_shape(std::size_t cardinality) -> std::string {
  return "independent_uniform_c" + std::to_string(cardinality);
}

// scalar is always kept: it is the thing every backend is compared against.
inline auto path_of(TslDetectorBackend backend) -> char const * {
  std::string const name = tsl_detector_name(backend);
  if (backend == TslDetectorBackend::Scalar) {
    return "scalar";
  }
  return name.size() >= 3 && name.substr(name.size() - 3) == "_hw" ? "hw" : "sw";
}

inline std::string g_paths = "hw";
TslTunedConfig g_samplesort_config;
TslTunedConfig g_quicksort_config;
std::map<std::string, TslTunedConfig> g_tuned;

// An explicit allow list, when one device is wanted rather than a whole path.
// `--paths hw` asks for every hardware backend compiled in, which on a host with
// only one accelerator means the other one's rows are attempted and dropped as
// unavailable. That is honest but it is not the same as not asking: a per-machine
// run of the paper's accelerator table wants `--detectors scalar,iaa_hw` on the
// IAA host and `scalar,dsa_hw` here. Empty means "whatever --paths says".
inline std::vector<std::string> g_detectors;

inline auto wanted(TslDetectorBackend backend) -> bool {
  auto const name = std::string(tsl_detector_name(backend));
  if (!g_detectors.empty()) {
    return std::find(g_detectors.begin(), g_detectors.end(), name)
           != g_detectors.end();
  }
  auto const path = std::string(path_of(backend));
  return path == "scalar" || g_paths == "all" || g_paths == path;
}

template <class Key>
void run_width(TslPaperResults & results,
               std::vector<std::size_t> const & cardinalities,
               std::vector<std::size_t> const & column_counts,
               std::size_t rows, std::vector<std::size_t> const & worker_counts,
               std::size_t min_offload) {
  // The cell this binary was built for: intr/512 unless
  // TSL_COSORT_MEASURE_STYLE/WIDTH say otherwise. Q0 checks that default against
  // the nine cells it measured, so a host where it is the wrong choice says so
  // rather than reporting a quietly suboptimal number.
  using Simd = tsl_measure_simd_t<Key>;
  TslDatasetSource<Key> source(8ull << 30);
  auto const tail = "_u" + std::to_string(sizeof(Key) * 8) + "_n";

  for (auto const cardinality : cardinalities) {
    auto const shape = cardinality_shape(cardinality);
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
      blank.shape_params = "c=" + std::to_string(cardinality);
      blank.rows = rows;
      blank.columns = columns;
      blank.element_bytes = sizeof(Key);
      blank.algorithm = "samplesort";
      blank.variant = g_samplesort_config.describe_samplesort();
      if (spec == nullptr) {
        results.drop(blank, "no such dataset at this size and column count");
        continue;
      }

      auto const pristine = source.pristine(*spec);
      auto const reference = source.reference(*spec, TslDirection::Ascending);
      std::vector<TslSortColumn<Key>> specs;
      for (auto const & column : *pristine) {
        specs.push_back(TslSortColumn<Key>{const_cast<Key *>(column.data()),
                                           TslSortOrder::ASCENDING});
      }

      for (auto const workers : worker_counts) {
        for (auto const backend : tsl_compiled_detectors()) {
          auto row = blank;
          row.detector = tsl_detector_name(backend);
          row.workers = workers;
          if (tsl_detector_is_async(backend)) {
            results.drop(row, "asynchronous: this driver never polls");
            continue;
          }
          if (!wanted(backend)) {
            continue;  // not asked for; not a drop, the grid never included it
          }
          TslDetectorConfig config;
          config.workers = workers;
          config.min_offload = min_offload;
          std::vector<Key> index(rows);
          try {
            tsl_with_detector<Key>(backend, config, [&](auto & detector) {
              using Detector = std::decay_t<decltype(detector)>;
              if constexpr (!tsl_detector_wants_executor<Detector>::value) {
                // The sorter Q0 chose, not one typed here. Detection's share of
                // the runtime is this driver's headline, and a share is a ratio
                // against the sort: measuring it around a sorter twice as slow as
                // the one we ship would halve the share and understate every
                // offload decision that rests on it.
                TslSampleSortColumnMetrics metrics;
                bool ok = false;
                TslPaperStats stats{};
                // Profiling stays on here, unlike every other driver: the phase
                // split *is* the measurement. So Q3's absolute ns/element are not
                // comparable with Q2's or Q4's -- they carry the timers' 1.08x to
                // 1.28x -- while the share and the between-detector comparison,
                // both taken within this build, are unaffected.
                auto const dispatched = with_samplesort<Key, Simd, true>(
                  g_samplesort_config, [&](auto sorter) {
                    auto const measured = tsl_paper_measure(
                      [&] {
                        metrics = {};
                        if (workers > 1) {
                          sorter.sort_index_parallel(specs.data(), columns,
                                                     index.data(), rows, detector,
                                                     workers, &metrics);
                        } else {
                          sorter.sort_index(specs.data(), columns, index.data(),
                                            rows, detector, &metrics);
                        }
                      },
                      [&] { return image_matches(*pristine, *reference, index); },
                      rows);
                    ok = measured.first;
                    stats = measured.second;
                  });
                if (!dispatched) {
                  results.drop(row, "tuned samplesort configuration is not "
                                    "instantiated here: "
                                    + g_samplesort_config.describe_samplesort());
                } else {
                  row.variant = g_samplesort_config.describe_samplesort()
                                + (g_samplesort_config.from_file ? " (tuned)"
                                                                 : " (default)");
                  row.verified = ok;
                  row.ns_per_element = stats;
                  auto const denominator = static_cast<double>(rows);
                  row.ns_materialize = metrics.ns_materialize / denominator;
                  row.ns_sort = metrics.ns_sort / denominator;
                  row.ns_detect = metrics.ns_detect / denominator;
                  results.add(std::move(row));
                }
              }
            });
          } catch (std::exception const & error) {
            results.drop(row, std::string("unavailable: ") + error.what());
          }
        }
      }
    }
  }
}

}  // namespace

int main(int argc, char ** argv) {
  // The catalog's `independent_uniform` cardinalities, which is the axis that
  // decides how much work a detector has relative to the scan it replaces.
  std::vector<std::size_t> cardinalities{16, 1024, 65536};
  std::vector<std::size_t> column_counts{2, 8};
  std::vector<std::size_t> worker_counts;   // machine-derived unless --workers
  std::vector<std::size_t> widths{4, 8};
  std::size_t rows = 0;                     // machine-derived unless --rows
  std::size_t min_offload = 4096;
  std::string csv_path;
  std::string tuned_path = "best_config.tsv";

  for (int i = 1; i < argc; ++i) {
    auto const flag = std::string(argv[i]);
    auto const value = [&]() -> std::string { return i + 1 < argc ? argv[++i] : ""; };
    auto const list = [&](std::vector<std::size_t> & into) {
      into.clear();
      for (auto const & part : split(value(), ',')) {
        into.push_back(std::strtoull(part.c_str(), nullptr, 10));
      }
    };
    if (flag == "--cardinalities") {
      list(cardinalities);
    } else if (flag == "--cols") {
      list(column_counts);
    } else if (flag == "--workers") {
      list(worker_counts);
    } else if (flag == "--element-bytes" || flag == "--widths") {
      // `--widths` was the old name and meant element *bytes*, which reads as
      // register width and misled a reader into thinking these drivers sweep
      // 128/256/512. They do not: register width is bench_q0_tune's axis and
      // bench_q6_portability's. Kept as an alias so old command lines still work.
      if (flag == "--widths") {
        std::printf("note: --widths means element bytes; prefer --element-bytes\n");
      }
      list(widths);
    } else if (flag == "--rows") {
      rows = std::strtoull(value().c_str(), nullptr, 10);
    } else if (flag == "--min-offload") {
      min_offload = std::strtoull(value().c_str(), nullptr, 10);
    } else if (flag == "--detectors") {
      g_detectors = split(value(), ',');
      for (auto const & name : g_detectors) {
        try {
          (void)tsl_detector_from_name(name);
        } catch (std::exception const & error) {
          std::printf("%s\nvalid names: ", error.what());
          for (auto const backend : tsl_compiled_detectors()) {
            std::printf("%s ", tsl_detector_name(backend));
          }
          std::printf("\n");
          return 2;
        }
      }
    } else if (flag == "--paths") {
      g_paths = value();
      if (g_paths != "hw" && g_paths != "sw" && g_paths != "all") {
        std::printf("--paths takes hw, sw or all\n");
        return 2;
      }
    } else if (flag == "--tuned") {
      tuned_path = value();
    } else if (flag == "--csv") {
      csv_path = value();
    } else {
      std::printf("unknown argument: %s\n", flag.c_str());
      return 2;
    }
  }

  TslPaperResults results("Q3 detection", "bench_q3_detection");
  if (worker_counts.empty()) {
    worker_counts = tsl_default_workers(results.machine());
  }
  if (rows == 0) {
    rows = tsl_rows_out_of_cache(results.machine(), 4, 4);
  }
  std::printf("workers=%zu..%zu, rows=%zu (derived from this machine)\n",
              worker_counts.front(), worker_counts.back(), rows);
  g_tuned = tsl_read_tuned(tuned_path);
  if (g_tuned.empty()) {
    std::printf("no %s: measuring the default configuration, rows labelled "
                "(default)\n", tuned_path.c_str());
  }
  if (g_detectors.empty()) {
    std::printf("paths=%s (software paths are for correctness, not for figures)\n",
                g_paths.c_str());
  } else {
    std::printf("detectors=");
    for (auto const & name : g_detectors) {
      std::printf("%s ", name.c_str());
    }
    std::printf("(explicit list; --paths ignored)\n");
    // Asking for a backend this binary was not built with is a mistake worth
    // saying out loud rather than a quietly shorter grid.
    auto const compiled = tsl_compiled_detectors();
    for (auto const & name : g_detectors) {
      auto const backend = tsl_detector_from_name(name);
      if (std::find(compiled.begin(), compiled.end(), backend) == compiled.end()) {
        std::printf("  !! %s was requested but is not compiled into this binary\n",
                    name.c_str());
      }
    }
  }
  std::printf("min_offload=%zu  backends compiled in: ", min_offload);
  for (auto const backend : tsl_compiled_detectors()) {
    std::printf("%s ", tsl_detector_name(backend));
  }
  std::printf("\n");

  results.expect(cardinalities.size() * column_counts.size() * widths.size()
                 * worker_counts.size() * tsl_compiled_detectors().size());
  for (auto const width : widths) {
    if (width == 4) {
      tsl_select_tuned<std::uint32_t>(g_tuned, g_samplesort_config,
                                      g_quicksort_config);
      run_width<std::uint32_t>(results, cardinalities, column_counts, rows,
                               worker_counts, min_offload);
    } else if (width == 8) {
      tsl_select_tuned<std::uint64_t>(g_tuned, g_samplesort_config,
                                      g_quicksort_config);
      run_width<std::uint64_t>(results, cardinalities, column_counts, rows,
                               worker_counts, min_offload);
    }
  }

  std::printf("\n%s\n", results.summary().c_str());
  if (!csv_path.empty()) {
    results.write_csv(csv_path);
  }
  return 0;
}
