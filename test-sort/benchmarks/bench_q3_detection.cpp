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
//   ./bench_q3_detection --shapes skewed_zipf_s1,heavy_hitter_f90 --cols 8
//   ./bench_q3_detection --csv results/q3_detection.csv

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <set>
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

// One shape to measure, and what the row should record about it.
//
// The cardinality sweep is the default because it isolates the axis under test:
// `independent_uniform_cN` sets the equal-run length to rows/N and holds
// everything else flat, so a win or loss belongs to run length rather than to
// skew or to where ties resolve. That is deliberately narrow, and it is also a
// limit -- a uniform family cannot reach the regime a heavy-tailed key creates,
// where one value's run is a large fraction of the table and no other run is
// worth a descriptor. Whether an offload still pays *there* is a different
// question from whether it pays at run length 8192, and `--shapes` is how to ask
// it. The row then carries the catalog's own parameters, since "c=" means nothing
// for a Zipf key.
struct shape_request {
  std::string label;     // catalog id prefix, e.g. "skewed_zipf_s1"
  std::string params;    // what lands in the row; empty means read it from the spec
};

// Every parameter the catalog recorded for a spec, as `k=v` pairs. Used for a
// shape named on the command line, where the driver does not know which knob
// defines it.
auto params_of(TslDatasetSpec const & spec) -> std::string {
  std::string out;
  for (auto const & [name, value] : spec.params) {
    if (!out.empty()) {
      out += ' ';
    }
    auto const rounded = static_cast<long long>(value);
    out += name + "=";
    out += (static_cast<double>(rounded) == value ? std::to_string(rounded)
                                                  : std::to_string(value));
  }
  return out;
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

// Which sorters to measure the share around. Both by default: detection's share
// is a fraction of a particular sorter's runtime, and the reported figures use
// both families.
inline std::set<std::string> g_algorithms{"samplesort", "quicksort"};
// Whether an asynchronous completion respects the share threshold. Off is the
// behaviour every published figure was taken with; on is the variant this driver
// exists to price. A flag rather than a replacement, because the comparison is the
// point and the two have to run in the same process on the same data.
inline bool g_async_spans_local = false;

inline auto wanted(TslDetectorBackend backend) -> bool {
  auto const name = std::string(tsl_detector_name(backend));
  if (!g_detectors.empty()) {
    return std::find(g_detectors.begin(), g_detectors.end(), name)
           != g_detectors.end();
  }
  auto const path = std::string(path_of(backend));
  return path == "scalar" || g_paths == "all" || g_paths == path;
}

// What a detector did with the ranges it was given, normalised across backends.
//
// Runtime alone cannot separate "the offload did not pay" from "the offload never
// happened": a detector that declined every range because it was below the
// threshold, or because its window was full, looks exactly like one that ran and
// lost. These counters are what tell them apart, so they are written beside the
// timings rather than printed and forgotten.
struct detector_counters {
  bool present = false;
  std::size_t ranges = 0;            // ranges the detector was asked about
  std::size_t offloaded = 0;         // ranges that became device work
  std::size_t declined_small = 0;    // below the offload threshold
  std::size_t declined_no_slot = 0;  // the in-flight window was full
  std::size_t descriptors = 0;
  std::size_t spans = 0;
  std::size_t polls = 0;             // asynchronous only
  std::size_t poll_advances = 0;
  std::size_t poll_empty = 0;
};

// Which shape of metrics a detector keeps, detected the way the sorters detect
// the executor and prepare seams: a trait, because the detectors are unrelated
// types by design and this target is C++17.
template <class Detector, class = void>
struct tsl_detector_has_async_metrics : std::false_type {};
template <class Detector>
struct tsl_detector_has_async_metrics<
  Detector,
  decltype(std::declval<Detector &>().metrics().poll_calls, void())
> : std::true_type {};

template <class Detector, class = void>
struct tsl_detector_has_fleet_metrics : std::false_type {};
template <class Detector>
struct tsl_detector_has_fleet_metrics<
  Detector,
  decltype(std::declval<Detector &>().aggregate_metrics().fallback_small, void())
> : std::true_type {};

// Two shapes of metrics struct, one record.
template <class Detector>
auto counters_of(Detector & detector) -> detector_counters {
  detector_counters out;
  if constexpr (tsl_detector_has_async_metrics<Detector>::value) {
    auto const m = detector.metrics();
    out = {true, m.ranges, m.offloaded_ranges, m.fallback_small,
           m.fallback_no_slot, m.descriptors, m.spans_emitted, m.poll_calls,
           m.poll_advances, m.poll_empty};
  } else if constexpr (tsl_detector_has_fleet_metrics<Detector>::value) {
    auto const m = detector.aggregate_metrics();
    out.present = true;
    out.ranges = m.ranges;
    out.declined_small = m.fallback_small;
    out.offloaded = m.ranges - m.fallback_small;
    out.descriptors = m.descriptors;
    out.spans = m.spans_emitted;
  }
  return out;
}

// The sidecar. Not extra columns in the question's CSV: one schema across every
// question is what makes a figure a query over the directory rather than a
// per-question special case, and these fields exist for one question only.
struct counter_sink {
  std::vector<std::string> lines;

  void add(TslPaperRow const & row, std::string const & pairing,
           detector_counters const & counters) {
    if (!counters.present) {
      return;
    }
    lines.push_back(
      row.shape + "," + row.shape_params + "," + std::to_string(row.rows) + ","
      + std::to_string(row.columns) + "," + std::to_string(row.element_bytes) + ","
      + std::to_string(row.workers) + "," + row.detector + "," + pairing + ","
      + std::to_string(row.repetitions) + "," + std::to_string(counters.ranges) + "," + std::to_string(counters.offloaded)
      + "," + std::to_string(counters.declined_small) + ","
      + std::to_string(counters.declined_no_slot) + ","
      + std::to_string(counters.descriptors) + "," + std::to_string(counters.spans)
      + "," + std::to_string(counters.polls) + ","
      + std::to_string(counters.poll_advances) + ","
      + std::to_string(counters.poll_empty));
  }

  void write(std::string const & path) const {
    if (path.empty() || lines.empty()) {
      return;
    }
    std::FILE * out = std::fopen(path.c_str(), "w");
    if (out == nullptr) {
      std::printf("could not write %s\n", path.c_str());
      return;
    }
    // repetitions, because a detector's counters accumulate over every timed
    // pass: the harness resamples a wide row up to 33 times, and a count that
    // does not say how many runs produced it cannot be compared with its
    // neighbour.
    std::fprintf(out, "shape,shape_params,rows,columns,element_bytes,workers,"
                      "detector,pairing,repetitions,ranges,offloaded,declined_small,"
                      "declined_no_slot,descriptors,spans,polls,poll_advances,"
                      "poll_empty\n");
    for (auto const & line : lines) {
      std::fprintf(out, "%s\n", line.c_str());
    }
    std::fclose(out);
    std::printf("wrote %s (%zu rows)\n", path.c_str(), lines.size());
  }
};

inline counter_sink g_counters;

template <class Key>
void run_width(TslPaperResults & results,
               std::vector<shape_request> const & shapes,
               std::vector<std::size_t> const & column_counts,
               std::size_t rows, std::vector<std::size_t> const & worker_counts,
               TslDetectorConfig const & detector_config, bool iso_resource) {
  // The cell this binary was built for: intr/512 unless
  // TSL_COSORT_MEASURE_STYLE/WIDTH say otherwise. Q0 checks that default against
  // the nine cells it measured, so a host where it is the wrong choice says so
  // rather than reporting a quietly suboptimal number.
  using Simd = tsl_measure_simd_t<Key>;
  TslDatasetSource<Key> source(8ull << 30);
  auto const tail = "_u" + std::to_string(sizeof(Key) * 8) + "_n";

  for (auto const & request : shapes) {
    auto const shape = request.label;
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
      blank.shape_params = !request.params.empty() ? request.params
                           : (spec != nullptr ? params_of(*spec) : std::string{});
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
          // Iso-resource pairing: the argument for an offload is usually that it
          // frees a core, and comparing both at the same worker count never
          // charges it for one. So an offloading backend is also measured with one
          // worker fewer than the scalar scan it is being compared against --
          // W-1 cores plus the device against W cores. The device is not free
          // either (one host, one work queue), which is exactly why the pairing
          // has to be measured rather than argued.
          auto const offloads = backend != TslDetectorBackend::Scalar;
          auto const iso = iso_resource && offloads && workers > 1;
          auto const run_workers = iso ? workers - 1 : workers;
          auto const pairing = iso ? "iso vs " + std::to_string(workers) + "w"
                                   : std::string("equal-workers");
          auto row = blank;
          row.detector = tsl_detector_name(backend);
          row.workers = run_workers;
          // Asynchronous backends used to be dropped here: the samplesort's
          // phase-two loop had no way to stay alive while a device still owed it
          // ranges, so it could not poll. It now carries the pending-work
          // contract, and an asynchronous offload is the only form in which
          // moving detection to a device can overlap the sort -- which is the
          // question this driver exists to answer, so it is measured rather than
          // dropped. Serially there is nothing to overlap with, though: the
          // sorter polls from its own idle loop, so a one-worker asynchronous row
          // measures the submission path and not concurrency.
          if (!wanted(backend)) {
            continue;  // not asked for; not a drop, the grid never included it
          }
          // For the worker count this row actually runs at: under the
          // iso-resource pairing that is one fewer than the scalar row it is
          // compared against, and the configuration that would be deployed there
          // is the one tuned for it.
          tsl_select_tuned<Key>(g_tuned, g_samplesort_config, g_quicksort_config,
                                run_workers);
          auto config = detector_config;
          config.workers = run_workers;
          std::vector<Key> index(rows);
          try {
            tsl_with_detector<Key>(backend, config, [&](auto & detector) {
              // The sorter Q0 chose, not one typed here. Detection's share of
              // the runtime is this driver's headline, and a share is a ratio
              // against the sort: measuring it around a sorter twice as slow as
              // the one we ship would halve the share and understate every
              // offload decision that rests on it.
              //
              // Both families, because the share is a property of the sorter as
              // much as of the detector: the samplesort and the index quicksort
              // spend different fractions of their time materialising and
              // sorting, so "detection is N% of the sort" needs saying about the
              // sorter the reported figures use. Q2 and Q4 report both.
              //
              // Profiling stays on here, unlike every other driver: the phase
              // split *is* the measurement. So Q3's absolute ns/element are not
              // comparable with Q2's or Q4's -- they carry the timers' 1.08x to
              // 1.28x -- while the share and the between-detector comparison,
              // both taken within this build, are unaffected.
              auto record = [&](std::string const & algorithm,
                                std::string const & variant, bool dispatched,
                                bool ok, TslPaperStats const & stats,
                                double ns_materialize, double ns_sort,
                                double ns_detect) {
                auto row_out = row;
                row_out.algorithm = algorithm;
                if (!dispatched) {
                  results.drop(row_out, "the tuned " + algorithm + " configuration "
                               "is not instantiated here: " + variant);
                  return;
                }
                row_out.variant = variant + (iso ? " [" + pairing + "]" : "");
                row_out.verified = ok;
                row_out.ns_per_element = stats;
                auto const denominator = static_cast<double>(rows);
                row_out.ns_materialize = ns_materialize / denominator;
                row_out.ns_sort = ns_sort / denominator;
                row_out.ns_detect = ns_detect / denominator;
                g_counters.add(row_out, pairing, counters_of(detector));
                results.add(std::move(row_out));
              };

              if (g_algorithms.count("samplesort") != 0) {
                TslSampleSortColumnMetrics metrics;
                bool ok = false;
                TslPaperStats stats{};
                auto const dispatched = with_samplesort<Key, Simd, true>(
                  g_samplesort_config, [&](auto sorter) {
                    // The span-routing variant under test: an asynchronous
                    // completion polled on another thread applies the same share
                    // threshold a synchronous one would, instead of publishing
                    // every late span to the shared pool whatever its size.
                    sorter.set_async_spans_local(g_async_spans_local);
                    auto const measured = tsl_paper_measure(
                      [&] {
                        metrics = {};
                        if (workers > 1) {
                          sorter.sort_index_parallel(specs.data(), columns,
                                                     index.data(), rows, detector,
                                                     run_workers, &metrics);
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
                record("samplesort",
                       g_samplesort_config.describe_samplesort()
                         + tsl_tuned_label(g_samplesort_config, run_workers),
                       dispatched, ok, stats, metrics.ns_materialize,
                       metrics.ns_sort, metrics.ns_detect);
              }

              if (g_algorithms.count("quicksort") != 0) {
                TslIndexSortMetrics metrics;
                bool ok = false;
                TslPaperStats stats{};
                auto const dispatched = with_quicksort_leaf<Key, Simd, true>(
                  g_quicksort_config, [&](auto sorter) {
                    auto const measured = tsl_paper_measure(
                      [&] {
                        metrics = {};
                        // One worker takes the serial entry, whatever the
                        // detector: it now polls at each level boundary of its own
                        // level loop, so an asynchronous backend completes there.
                        // Which matters for the comparison rather than only for
                        // coverage -- a serial row that had to go through the
                        // parallel entry was paying for a task executor the
                        // scalar row it is compared against did not have.
                        if (workers > 1) {
                          sorter.sort_index_parallel(
                            specs.data(), columns, index.data(), rows,
                            g_quicksort_config.discovery, detector, run_workers,
                            g_quicksort_config.partition_threshold, &metrics);
                        } else {
                          sorter.sort_index(specs.data(), columns, index.data(),
                                            rows, g_quicksort_config.discovery,
                                            detector, &metrics);
                        }
                      },
                      [&] { return image_matches(*pristine, *reference, index); },
                      rows);
                    ok = measured.first;
                    stats = measured.second;
                  });
                record("quicksort",
                       g_quicksort_config.describe_quicksort()
                         + tsl_tuned_label(g_quicksort_config, run_workers),
                       dispatched, ok, stats, metrics.ns_materialize,
                       metrics.ns_sort, metrics.ns_detect);
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
  bool cardinalities_given = false;
  // Catalog shapes named directly, for the regimes the uniform family cannot
  // reach: a heavy-tailed key whose head is a large fraction of the table, a
  // hierarchy whose ties resolve at a fixed depth. Empty means sweep
  // `cardinalities` instead, which is the default because it isolates run length.
  std::vector<std::string> shape_names;
  std::vector<std::size_t> column_counts{2, 8};
  std::vector<std::size_t> worker_counts;   // machine-derived unless --workers
  std::vector<std::size_t> widths{4, 8};
  std::size_t rows = 0;                     // machine-derived unless --rows
  // Working-set targets as multiples of this machine's last level, so the axis
  // means the same thing on a host with a different cache. 4x is where every
  // other reported figure lives; the larger points are there because an offload's
  // case is memory pressure, and a working set that still half-fits cannot show
  // it. Written as multiples rather than row counts for the same reason the row
  // count is derived: a literal here would be a different experiment on the next
  // machine.
  std::vector<std::size_t> llc_multiples{4};
  bool workers_ladder = false;
  // Hold the mean equal-run length fixed across the size axis instead of the
  // cardinality: rows/c constant, so what changes between two sizes is the
  // footprint and not how much work each detect call has. Without it the two
  // mechanisms move together and a result cannot say which one it measured.
  std::size_t run_length = 0;
  TslDetectorConfig detector_config;
  bool iso_resource = false;
  std::string csv_path;
  std::string counters_path;
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
    if (flag == "--workers" && i + 1 < argc && std::string(argv[i + 1]) == "ladder") {
      // Every worker count from one to the physical cores of one NUMA node. The
      // "how many cores does the device replace" question is a crossing between
      // two scaling curves, so it needs the curves rather than two points -- and
      // the top of the ladder is a property of the machine, so it is derived here
      // rather than written into a command line that would mean something else on
      // the next host.
      ++i;
      worker_counts.clear();   // filled once the machine has been probed
      workers_ladder = true;
    } else if (flag == "--cardinalities") {
      list(cardinalities);
      cardinalities_given = true;
    } else if (flag == "--shapes") {
      shape_names = split(value(), ',');
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
      detector_config.min_offload = std::strtoull(value().c_str(), nullptr, 10);
    } else if (flag == "--run-length") {
      run_length = std::strtoull(value().c_str(), nullptr, 10);
    } else if (flag == "--sizes") {
      list(llc_multiples);
    } else if (flag == "--slots") {
      // The device's window, which is a property of the machine rather than of
      // the algorithm: a host with more work queues can hold more in flight.
      detector_config.slots = std::strtoull(value().c_str(), nullptr, 10);
    } else if (flag == "--depth") {
      detector_config.depth = std::strtoull(value().c_str(), nullptr, 10);
    } else if (flag == "--region-bytes") {
      detector_config.region_bytes = std::strtoull(value().c_str(), nullptr, 10);
    } else if (flag == "--iso-resource") {
      iso_resource = true;
    } else if (flag == "--async-spans-local") {
      g_async_spans_local = true;
    } else if (flag == "--counters") {
      counters_path = value();
    } else if (flag == "--algorithms") {
      g_algorithms.clear();
      for (auto const & part : split(value(), ',')) {
        if (part != "samplesort" && part != "quicksort") {
          std::printf("--algorithms takes samplesort and/or quicksort\n");
          return 2;
        }
        g_algorithms.insert(part);
      }
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
  if (workers_ladder) {
    auto const top = std::max<std::size_t>(1, results.machine().parallel_width());
    for (std::size_t workers = 1; workers <= top; ++workers) {
      worker_counts.push_back(workers);
    }
  }
  if (worker_counts.empty()) {
    worker_counts = tsl_default_workers(results.machine());
  }
  auto const llc = results.machine().llc_bytes > 0 ? results.machine().llc_bytes
                                                   : 32ull * 1024 * 1024;
  // One explicit --rows overrides the size axis; otherwise the axis is the axis.
  std::vector<std::size_t> row_counts;
  if (rows != 0) {
    row_counts.push_back(rows);
    llc_multiples.clear();
  } else {
    for (auto const multiple : llc_multiples) {
      row_counts.push_back(tsl_rows_for_bytes(multiple * llc, 4, 4));
    }
  }
  std::printf("workers=%zu..%zu, LLC=%zu MiB, working sets=",
              worker_counts.front(), worker_counts.back(), llc / (1024 * 1024));
  for (std::size_t index = 0; index < row_counts.size(); ++index) {
    std::printf("%zu rows%s", row_counts[index],
                index + 1 < row_counts.size() ? ", " : "");
  }
  std::printf(" (derived from this machine)\n");
  if (iso_resource) {
    std::printf("iso-resource: an offloading backend also runs at one worker "
                "fewer than the scalar scan it is compared against\n");
  }
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
  // The shapes to measure, from whichever of the two flags was used.
  //
  // Mutually exclusive with `--run-length` on purpose: that flag solves for the
  // cardinality that holds the run length fixed at each size, and a named shape
  // has no cardinality to solve for. Refused rather than silently ignored, since
  // the whole value of the run-length sweep is that its rows are comparable.
  if (!shape_names.empty() && run_length != 0) {
    std::printf("--shapes and --run-length are mutually exclusive: --run-length "
                "chooses the cardinality itself, and a named shape has none to "
                "choose.\n");
    return 2;
  }
  if (!shape_names.empty() && cardinalities_given) {
    std::printf("--shapes overrides --cardinalities; drop one of them.\n");
    return 2;
  }
  std::vector<shape_request> shapes;
  if (shape_names.empty()) {
    for (auto const cardinality : cardinalities) {
      shapes.push_back(shape_request{cardinality_shape(cardinality),
                                     "c=" + std::to_string(cardinality)});
    }
  } else {
    for (auto const & name : shape_names) {
      // Params left empty: they come from the catalog spec, because the driver
      // does not know which knob defines a shape it was merely handed the name of.
      shapes.push_back(shape_request{name, std::string{}});
    }
  }
  auto const shape_count = shapes.size();
  std::printf("shapes:");
  for (auto const & request : shapes) {
    std::printf(" %s", request.label.c_str());
  }
  std::printf("%s\n", shape_names.empty()
              ? "  (cardinality sweep: run length is the axis)"
              : "  (named shapes: the axis is whatever distinguishes them)");

  if (g_async_spans_local) {
    std::printf("async span routing: LOCAL (completions respect the share "
                "threshold)\n");
  }
  std::printf("min_offload=%zu slots=%zu depth=%zu region=%zuB  "
              "backends compiled in: ", detector_config.min_offload,
              detector_config.slots, detector_config.depth,
              detector_config.region_bytes);
  for (auto const backend : tsl_compiled_detectors()) {
    std::printf("%s ", tsl_detector_name(backend));
  }
  std::printf("\n");

  // Only the detectors this run will actually measure. Counting every *compiled*
  // backend made the progress line's denominator include the ones `--detectors`
  // excluded, so a three-detector run against five compiled ones reported 84 of
  // 140 and looked as though it had skipped 56 rows it was never going to produce.
  auto const selected_detectors = static_cast<std::size_t>(
    std::count_if(tsl_compiled_detectors().begin(), tsl_compiled_detectors().end(),
                  [](TslDetectorBackend backend) { return wanted(backend); }));
  results.expect(shape_count * column_counts.size() * widths.size()
                 * worker_counts.size() * row_counts.size()
                 * selected_detectors * g_algorithms.size());
  for (auto const size_rows : row_counts) {
    // The cardinality that gives the requested run length at this size. Reported
    // rather than silently substituted: a catalogue without that shape drops the
    // cell with a reason, which is the honest outcome for a diagonal the data
    // cannot supply.
    // `--run-length` overrides the shape list with the one cardinality that holds
    // the run length at this size, which is the whole point of that flag. It has
    // no meaning for a named shape -- a Zipf key has no cardinality knob to solve
    // for -- so the two are mutually exclusive and that is checked at parse time.
    auto size_shapes = shapes;
    if (run_length != 0) {
      auto const cardinality = std::max<std::size_t>(1, size_rows / run_length);
      size_shapes = {shape_request{cardinality_shape(cardinality),
                                   "c=" + std::to_string(cardinality)}};
      std::printf("size %zu rows: cardinality %zu holds the run length at %zu\n",
                  size_rows, cardinality, run_length);
    }
    for (auto const width : widths) {
      if (width == 4) {
        tsl_select_tuned<std::uint32_t>(g_tuned, g_samplesort_config,
                                        g_quicksort_config);
        run_width<std::uint32_t>(results, size_shapes, column_counts, size_rows,
                                 worker_counts, detector_config, iso_resource);
      } else if (width == 8) {
        tsl_select_tuned<std::uint64_t>(g_tuned, g_samplesort_config,
                                        g_quicksort_config);
        run_width<std::uint64_t>(results, size_shapes, column_counts, size_rows,
                                 worker_counts, detector_config, iso_resource);
      }
    }
  }

  std::printf("\n%s\n", results.summary().c_str());
  if (!csv_path.empty()) {
    results.write_csv(csv_path);
  }
  if (counters_path.empty() && !csv_path.empty()) {
    // Beside the question's CSV by default: the counters are only meaningful
    // against the rows they came from.
    auto const dot = csv_path.rfind('.');
    counters_path = (dot == std::string::npos ? csv_path : csv_path.substr(0, dot))
                    + "_detector_counters.csv";
  }
  g_counters.write(counters_path);
  return 0;
}
