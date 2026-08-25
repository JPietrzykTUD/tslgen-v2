// Threaded multi-column co-sort with scalar versus DSA equal-run detection.
//
// Emits Google Benchmark JSON in the *same naming schema* as
// benchmark_multicolumn_gbench, plus one extra `rle=` axis, so
// visualize_multicolumn_bench.py reads it directly and rows can be compared
// against an existing sweep JSON. Two schema requirements are easy to miss: the
// visualizer keeps only non-aggregate or `median` rows, and it drops any row
// without a `count` counter.
//
// Algorithm names deliberately reuse `deep_parallel_*_3way_ins`: this harness
// runs the parallel sort with a non-zero partition threshold, which is exactly
// what that name means in the main sweep. Choosing the same size levels,
// distribution and `dist=low_entropy` semantics makes the `rle=scalar` rows
// directly comparable to the corresponding rows of a full sweep.
//
// Read the `rle_*` counters alongside the timing: the equal-run scan is a small
// fraction of total sort time on this path, so a wall-clock difference between
// backends is expected to be small. `rle_offloaded_frac` reports how much
// scanning actually left the CPU, which is what the offload controls.
//
// Every axis below is a comma-separated list and its values are registered as a
// Cartesian product, exactly like COSORT_COLUMNS in benchmark_multicolumn_gbench.
// `COSORT_WORKERS=1,6,12` therefore means three configurations, not one.
// Every varying axis appears in the benchmark name, so rows stay distinguishable.
//
//   COSORT_SIZE_LEVELS  levels into L1,L2,halfLLC,LLC,2xLLC   (default 4)
//   COSORT_ROWS         explicit rows per column; overrides SIZE_LEVELS
//   COSORT_COLUMNS      column counts                         (default 2)
//   COSORT_WORKERS      worker counts                         (default 12)
//   COSORT_DISTINCT     distinct values per column            (default 4096)
//   COSORT_TASK_THRESHOLD                                     (default 4096)
//   COSORT_PARTITION_THRESHOLD                                (default 16384)
//   COSORT_REGION_BYTES DSA region sizes                      (default 524288)
//   COSORT_MIN_OFFLOAD  min elements to offload               (default 4096)
//   COSORT_DSA_SLOTS    concurrent offloaded ranges           (default 16)
//   COSORT_DSA_DEPTH    descriptors in flight per range       (default 4)
//   COSORT_RLE          detector backends to register, by name:
//                       scalar,dml_sw,dsa_hw,dml_sw_async,dsa_hw_async
//                       (default: all five)
//   COSORT_DISCOVERY    post,incremental                      (default both)
//
// Scratch memory is slots * depth * 1.25 * region_bytes per detector, so a large
// COSORT_DSA_SLOTS with 512 KiB regions allocates hundreds of MiB. Raise slots
// only until rle_fallback_no_slot reaches zero.

#include <algorithm>
#include <cstdint>
#include <numeric>
#include <stdexcept>
#include <utility>

extern char ** environ;
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <random>
#include <string>
#include <vector>

#include <benchmark/benchmark.h>

#include "cluster_detection/dsa/dsa_async_run_detector.hpp"
#include "cluster_detection/dsa/dsa_run_detector.hpp"
#include "sorting/quicksort/multicolumn_quicksort.hpp"

namespace {

using DataType = std::uint32_t;
using Sorter = TslMultiColumnQuickSorter<DataType, TslPartitionKind::THREE_WAY, TslLeafKind::INSERTION>;
using SorterSimd = tsl::dataparallel::simd_for_t<tsl::dataparallel::native, DataType>;

// Parses a comma-separated axis: "1,2,3" is three values, not one combined
// value. Empty tokens are ignored. Matches parse_numeric_list in
// benchmark_multicolumn_gbench so both harnesses read the same syntax.
template <class Value>
auto parse_list(char const * text) -> std::vector<Value> {
  std::vector<Value> result;
  std::string const specification{text};
  std::size_t start = 0;
  while (start <= specification.size()) {
    auto const comma = specification.find(',', start);
    auto const token = specification.substr(start, comma - start);
    if (!token.empty()) {
      result.push_back(static_cast<Value>(std::strtoull(token.c_str(), nullptr, 0)));
    }
    if (comma == std::string::npos) {
      break;
    }
    start = comma + 1;
  }
  return result;
}

// One axis: the environment list when present, else the built-in default.
auto env_list(char const * name, std::vector<std::size_t> fallback) -> std::vector<std::size_t> {
  if (auto const * value = std::getenv(name)) {
    auto parsed = parse_list<std::size_t>(value);
    if (!parsed.empty()) {
      return parsed;
    }
  }
  return fallback;
}

// COSORT_SIZE_LEVELS wins; otherwise expand MIN..MAX the way the main
// benchmark's run_config does; otherwise the single default level.
auto resolve_size_levels() -> std::vector<std::size_t> {
  if (auto const * value = std::getenv("COSORT_SIZE_LEVELS")) {
    auto parsed = parse_list<std::size_t>(value);
    if (!parsed.empty()) {
      return parsed;
    }
  }
  auto const * min_text = std::getenv("COSORT_MIN_SIZE_LEVEL");
  auto const * max_text = std::getenv("COSORT_MAX_SIZE_LEVEL");
  if (min_text != nullptr || max_text != nullptr) {
    auto const low = min_text ? std::strtoull(min_text, nullptr, 0) : 0u;
    auto const high = max_text ? std::strtoull(max_text, nullptr, 0) : low;
    std::vector<std::size_t> levels;
    for (auto level = low; level <= high; ++level) {
      levels.push_back(static_cast<std::size_t>(level));
    }
    if (!levels.empty()) {
      return levels;
    }
  }
  return {4};
}

auto parse_text_list(char const * name, std::vector<std::string> fallback) -> std::vector<std::string> {
  auto const * value = std::getenv(name);
  if (value == nullptr) {
    return fallback;
  }
  std::vector<std::string> result;
  std::string const specification{value};
  std::size_t start = 0;
  while (start <= specification.size()) {
    auto const comma = specification.find(',', start);
    auto token = specification.substr(start, comma - start);
    if (!token.empty()) {
      result.push_back(std::move(token));
    }
    if (comma == std::string::npos) {
      break;
    }
    start = comma + 1;
  }
  return result.empty() ? fallback : result;
}

// Cache sizes from sysfs, mirroring how the main sweep derives its size levels
// so `size=` labels mean the same thing in both files.
struct cache_sizes {
  std::uint64_t l1 = 32u * 1024u;
  std::uint64_t l2 = 1024u * 1024u;
  std::uint64_t llc = 32u * 1024u * 1024u;
};

auto read_caches() -> cache_sizes {
  cache_sizes caches;
  for (int index = 0; index < 10; ++index) {
    auto const base = "/sys/devices/system/cpu/cpu0/cache/index" + std::to_string(index);
    std::ifstream level_file(base + "/level");
    std::ifstream size_file(base + "/size");
    std::ifstream type_file(base + "/type");
    if (!level_file || !size_file || !type_file) {
      continue;
    }
    int level = 0;
    std::string size_text;
    std::string type_text;
    level_file >> level;
    size_file >> size_text;
    type_file >> type_text;
    if (type_text == "Instruction") {
      continue;
    }
    std::uint64_t bytes = std::strtoull(size_text.c_str(), nullptr, 10);
    if (size_text.find('K') != std::string::npos) bytes *= 1024u;
    if (size_text.find('M') != std::string::npos) bytes *= 1024u * 1024u;
    if (level == 1) caches.l1 = bytes;
    if (level == 2) caches.l2 = bytes;
    if (level >= 3) caches.llc = bytes;
  }
  return caches;
}

struct size_level {
  char const * name;
  std::uint64_t per_column_bytes;
};

auto size_levels(cache_sizes const & caches) -> std::vector<size_level> {
  return {
    {"L1", caches.l1},
    {"L2", caches.l2},
    {"halfLLC", caches.llc / 2},
    {"LLC", caches.llc},
    {"2xLLC", caches.llc * 2},
  };
}

// One point of the benchmark matrix. Every field is a single value; the
// registrar walks the Cartesian product of the axis lists and builds one of
// these per combination.
struct config {
  std::size_t rows = 0;
  std::string size_name;
  std::size_t columns = 2;
  std::size_t workers = 12;
  std::size_t distinct = 4096;
  std::size_t task_threshold = 4096;
  std::size_t partition_threshold = 16384;
  std::size_t region_bytes = tsl_dsa_default_region_bytes;
  std::size_t min_offload = 4096;
  std::size_t dsa_slots = 16;
  std::size_t dsa_depth = 4;

  // 4096 distinct values per column is exactly the main sweep's `low_entropy`
  // shape, so keep the label identical when it matches and be explicit otherwise.
  auto dist_name() const -> std::string {
    return distinct == 4096 ? "low_entropy" : ("distinct" + std::to_string(distinct));
  }
};

// The axis lists, read once at startup.
struct matrix {
  // Accepts either the list form COSORT_SIZE_LEVELS=0,2,4 or the main
  // benchmark's range form COSORT_MIN_SIZE_LEVEL / COSORT_MAX_SIZE_LEVEL.
  std::vector<std::size_t> size_levels = resolve_size_levels();
  std::vector<std::size_t> rows = env_list("COSORT_ROWS", {});
  std::vector<std::size_t> columns = env_list("COSORT_COLUMNS", {2});
  std::vector<std::size_t> workers = env_list("COSORT_WORKERS", {12});
  std::vector<std::size_t> distinct = env_list("COSORT_DISTINCT", {4096});
  std::vector<std::size_t> task_thresholds = env_list("COSORT_TASK_THRESHOLD", {4096});
  std::vector<std::size_t> partition_thresholds = env_list("COSORT_PARTITION_THRESHOLD", {16384});
  std::vector<std::size_t> region_bytes = env_list("COSORT_REGION_BYTES", {tsl_dsa_default_region_bytes});
  std::vector<std::size_t> min_offload = env_list("COSORT_MIN_OFFLOAD", {4096});
  std::vector<std::size_t> dsa_slots = env_list("COSORT_DSA_SLOTS", {16});
  std::vector<std::size_t> dsa_depth = env_list("COSORT_DSA_DEPTH", {4});
  std::vector<std::string> backends =
    parse_text_list("COSORT_RLE", {"scalar", "dml_sw", "dsa_hw", "dml_sw_async", "dsa_hw_async"});
  std::vector<std::string> discovery =
    parse_text_list("COSORT_DISCOVERY", {"post", "incremental"});
};

class dataset {
  std::vector<std::vector<DataType>> pristine_;
  std::vector<std::vector<DataType>> work_;

 public:
  explicit dataset(config const & cfg) {
    std::mt19937_64 rng(0x5EED5A);
    pristine_.resize(cfg.columns);
    for (auto & column : pristine_) {
      column.resize(cfg.rows);
      for (auto & value : column) {
        value = static_cast<DataType>(rng() % cfg.distinct);
      }
    }
    work_ = pristine_;
  }

  void reset() { work_ = pristine_; }

  auto columns() -> std::vector<std::vector<DataType>> & { return work_; }

  auto specs() -> std::vector<TslSortColumn<DataType>> {
    std::vector<TslSortColumn<DataType>> out;
    out.reserve(work_.size());
    for (auto & column : work_) {
      out.push_back({column.data(), TslSortOrder::ASCENDING});
    }
    return out;
  }

  auto sorted() const -> bool {
    for (std::size_t row = 1; row < work_[0].size(); ++row) {
      for (std::size_t column = 0; column < work_.size(); ++column) {
        if (work_[column][row - 1] < work_[column][row]) break;
        if (work_[column][row - 1] > work_[column][row]) return false;
      }
    }
    return true;
  }
};

// Complete lexicographic row comparator, matching the main sweep's baseline so
// the two are the same measurement.
auto row_before(
  std::vector<std::vector<DataType>> const & columns,
  std::size_t left,
  std::size_t right
) -> bool {
  for (auto const & column : columns) {
    if (column[left] < column[right]) return true;
    if (column[right] < column[left]) return false;
  }
  return false;
}

void tag(benchmark::State & state, config const & cfg,
         TslMultiColumnSortMetrics const & sort_metrics,
         TslDsaRunDetectorMetrics const & rle_metrics) {
  using benchmark::Counter;
  auto const rows = double(cfg.rows);

  // `count` is mandatory: the visualizer drops any row without it, and derives
  // ns/row from it.
  state.counters["count"] = Counter(rows);
  state.counters["elem_bytes"] = Counter(double(sizeof(DataType)));
  state.counters["items_per_second"] =
    Counter(rows, Counter::kIsIterationInvariantRate, Counter::kIs1000);
  state.counters["bytes_per_second"] =
    Counter(rows * double(sizeof(DataType) * cfg.columns),
            Counter::kIsIterationInvariantRate, Counter::kIs1024);

  // Counter names the visualizer already understands.
  state.counters["rle_values_per_row"] = Counter(double(sort_metrics.rle_values_scanned) / rows);
  state.counters["direct_equal_bands"] = Counter(double(sort_metrics.direct_equal_bands));
  state.counters["direct_band_rows"] = Counter(double(sort_metrics.direct_equal_band_rows));
  state.counters["tasks_submitted"] = Counter(double(sort_metrics.tasks_submitted));
  state.counters["tasks_inline"] = Counter(double(sort_metrics.tasks_executed_inline));
  state.counters["max_outstanding"] = Counter(double(sort_metrics.max_outstanding_tasks));
  state.counters["partition_tasks"] = Counter(double(sort_metrics.partition_tasks_submitted));
  state.counters["idle_poll_wakeups"] = Counter(double(sort_metrics.idle_poll_wakeups));

  // Detector-specific counters.
  state.counters["rle_ranges"] = Counter(double(rle_metrics.ranges));
  state.counters["rle_elements"] = Counter(double(rle_metrics.elements));
  state.counters["rle_offloaded_elements"] = Counter(double(rle_metrics.offloaded_elements));
  state.counters["rle_offloaded_frac"] = Counter(
    rle_metrics.elements == 0 ? 0.0
      : double(rle_metrics.offloaded_elements) / double(rle_metrics.elements));
  state.counters["rle_descriptors"] = Counter(double(rle_metrics.descriptors));
  state.counters["rle_fired_blocks"] = Counter(double(rle_metrics.fired_blocks));
  state.counters["rle_refined_elements"] = Counter(double(rle_metrics.refined_elements));
  state.counters["rle_fallback_small"] = Counter(double(rle_metrics.fallback_small));
  state.counters["rle_spans"] = Counter(double(rle_metrics.spans_emitted));
  state.counters["rle_region_bytes"] = Counter(double(cfg.region_bytes));
}

// Asynchronous variant: the detector hands each range to the device and returns,
// so the worker goes back to sorting. No thread waits on the accelerator.
void run_async(benchmark::State & state, config const & cfg, TslRleBackend backend, TslRunDiscoveryKind discovery) {
  dataset data(cfg);
  Sorter sorter(0xC0FFEEu);

  TslMultiColumnSortMetrics sort_metrics{};
  TslDsaAsyncMetrics async_metrics{};

  for (auto _ : state) {
    state.PauseTiming();
    data.reset();
    auto specs = data.specs();
    TslDsaAsyncRunDetector<DataType> detector(
      backend, cfg.dsa_slots, cfg.dsa_depth, cfg.region_bytes, cfg.min_offload
    );
    state.ResumeTiming();

    sorter.sort_columns_parallel(
      specs.data(), specs.size(), cfg.rows, cfg.workers,
      cfg.task_threshold, cfg.partition_threshold, discovery, detector, &sort_metrics
    );

    state.PauseTiming();
    async_metrics = detector.metrics();
    state.ResumeTiming();
  }

  if (!data.sorted()) {
    state.SkipWithError("lexicographically unsorted output");
    return;
  }

  TslDsaRunDetectorMetrics as_sync{};
  as_sync.ranges = async_metrics.ranges;
  as_sync.elements = async_metrics.elements;
  as_sync.offloaded_elements = async_metrics.offloaded_elements;
  as_sync.descriptors = async_metrics.descriptors;
  as_sync.fired_blocks = async_metrics.fired_blocks;
  as_sync.fallback_small = async_metrics.fallback_small;
  as_sync.spans_emitted = async_metrics.spans_emitted;
  tag(state, cfg, sort_metrics, as_sync);
  state.counters["rle_async_jobs"] = benchmark::Counter(double(async_metrics.offloaded_ranges));
  state.counters["rle_fallback_no_slot"] = benchmark::Counter(double(async_metrics.fallback_no_slot));
  state.counters["rle_poll_calls"] = benchmark::Counter(double(async_metrics.poll_calls));
  state.counters["rle_poll_advances"] = benchmark::Counter(double(async_metrics.poll_advances));
  state.counters["rle_poll_empty"] = benchmark::Counter(double(async_metrics.poll_empty));
}

// Scalar reference: sort row indices with the full lexicographic comparator,
// then gather every column into that order. No TSL, no accelerator -- this is
// the `speedup_vs_std` denominator the visualizer needs, and BASELINE_KEYS
// (dtype, dist, order, cols, size) deliberately excludes workers and rle, so
// one baseline row serves every detector and worker count at that shape.
void run_std_baseline(benchmark::State & state, config const & cfg) {
  dataset data(cfg);
  std::vector<std::uint32_t> indices(cfg.rows);
  std::vector<DataType> gather(cfg.rows);

  for (auto _ : state) {
    state.PauseTiming();
    data.reset();
    auto & work = data.columns();
    state.ResumeTiming();

    std::iota(indices.begin(), indices.end(), 0u);
    std::sort(indices.begin(), indices.end(), [&](std::uint32_t left, std::uint32_t right) {
      return row_before(work, left, right);
    });
    for (std::size_t column = 0; column < cfg.columns; ++column) {
      for (std::size_t row = 0; row < cfg.rows; ++row) {
        gather[row] = work[column][indices[row]];
      }
      std::copy(gather.begin(), gather.end(), work[column].begin());
    }
    benchmark::DoNotOptimize(work.data());
    benchmark::ClobberMemory();
  }

  if (!data.sorted()) {
    state.SkipWithError("std argsort produced lexicographically unsorted output");
    return;
  }
  tag(state, cfg, TslMultiColumnSortMetrics{}, TslDsaRunDetectorMetrics{});
}

void run(benchmark::State & state, config const & cfg, TslRleBackend backend, TslRunDiscoveryKind discovery) {
  dataset data(cfg);
  Sorter sorter(0xC0FFEEu);

  TslMultiColumnSortMetrics sort_metrics{};
  TslDsaRunDetectorMetrics rle_metrics{};

  for (auto _ : state) {
    state.PauseTiming();
    data.reset();
    auto specs = data.specs();
    // Fresh fleet per iteration so its counters describe exactly one sort.
    TslDsaDetectorFleet<DataType> fleet(backend, cfg.workers, cfg.region_bytes, cfg.min_offload);
    state.ResumeTiming();

    sorter.sort_columns_parallel(
      specs.data(), specs.size(), cfg.rows, cfg.workers,
      cfg.task_threshold, cfg.partition_threshold, discovery, fleet, &sort_metrics
    );

    state.PauseTiming();
    rle_metrics = fleet.aggregate_metrics();
    state.ResumeTiming();
  }

  if (!data.sorted()) {
    state.SkipWithError("lexicographically unsorted output");
    return;
  }
  tag(state, cfg, sort_metrics, rle_metrics);
}

// Full dimension path so every axis the visualizer reads is populated, plus the
// DSA-specific axes. `async` is part of the rle value rather than a separate
// dimension, so scalar/sync/async are directly comparable on one axis.
auto benchmark_name(
  char const * algo,
  config const & cfg,
  std::string const & backend_name
) -> std::string {
  return std::string(algo)
    + "/u32"
    + "/lanes=" + std::to_string(SorterSimd::lane_count_v)
    + "/dist=" + cfg.dist_name()
    + "/order=asc"
    + "/cols=" + std::to_string(cfg.columns)
    + "/size=" + cfg.size_name
    + "/workers=" + std::to_string(cfg.workers)
    + "/threshold=" + std::to_string(cfg.task_threshold)
    + "/partitions=" + std::to_string(cfg.partition_threshold)
    + "/dsa_region=" + std::to_string(cfg.region_bytes)
    + "/dsa_slots=" + std::to_string(cfg.dsa_slots)
    + "/dsa_depth=" + std::to_string(cfg.dsa_depth)
    + "/dsa_min_offload=" + std::to_string(cfg.min_offload)
    + "/rle=" + backend_name;
}

// Maps the COSORT_RLE names onto a backend plus whether the async detector runs.
struct backend_choice {
  TslRleBackend backend;
  bool async;
};

auto parse_backend(std::string const & name) -> backend_choice {
  if (name == "scalar") return {TslRleBackend::SCALAR, false};
  if (name == "dml_sw") return {TslRleBackend::DML_SOFTWARE, false};
  if (name == "dsa_hw") return {TslRleBackend::DSA_HARDWARE, false};
  if (name == "dml_sw_async") return {TslRleBackend::DML_SOFTWARE, true};
  if (name == "dsa_hw_async") return {TslRleBackend::DSA_HARDWARE, true};
  throw std::invalid_argument("unknown COSORT_RLE backend: " + name);
}

auto parse_discovery(std::string const & name) -> std::pair<char const *, TslRunDiscoveryKind> {
  if (name == "post") {
    return {"deep_parallel_post_3way_ins", TslRunDiscoveryKind::POST_SORT};
  }
  if (name == "incremental") {
    return {"deep_parallel_incremental_3way_ins", TslRunDiscoveryKind::INCREMENTAL};
  }
  throw std::invalid_argument("unknown COSORT_DISCOVERY value: " + name);
}

// Silently ignoring a COSORT_* variable is how a run ends up measuring
// something other than what was asked for, so name every one this harness
// honours and complain about the rest.
void warn_about_unused_environment() {
  static char const * const known[] = {
    "COSORT_SIZE_LEVELS", "COSORT_MIN_SIZE_LEVEL", "COSORT_MAX_SIZE_LEVEL",
    "COSORT_ROWS", "COSORT_COLUMNS", "COSORT_WORKERS", "COSORT_DISTINCT",
    "COSORT_TASK_THRESHOLD", "COSORT_PARTITION_THRESHOLD",
    "COSORT_REGION_BYTES", "COSORT_MIN_OFFLOAD",
    "COSORT_DSA_SLOTS", "COSORT_DSA_DEPTH", "COSORT_RLE", "COSORT_DISCOVERY",
    "COSORT_BASELINE",
  };
  for (char ** entry = environ; *entry != nullptr; ++entry) {
    std::string const text{*entry};
    auto const equals = text.find('=');
    if (equals == std::string::npos) {
      continue;
    }
    auto const name = text.substr(0, equals);
    if (name.rfind("COSORT_", 0) != 0) {
      continue;
    }
    bool recognized = false;
    for (auto const * candidate : known) {
      if (name == candidate) {
        recognized = true;
        break;
      }
    }
    if (!recognized) {
      std::printf("warning: %s is not honoured by this benchmark and was ignored\n", name.c_str());
    }
  }
  if (std::getenv("COSORT_ROWS") != nullptr
      && (std::getenv("COSORT_SIZE_LEVELS") != nullptr
          || std::getenv("COSORT_MIN_SIZE_LEVEL") != nullptr
          || std::getenv("COSORT_MAX_SIZE_LEVEL") != nullptr)) {
    std::printf("warning: COSORT_ROWS overrides the size-level variables; "
                "size is labelled custom<rows> and will not join size=L1..2xLLC rows\n");
  }
}

void register_all() {
  warn_about_unused_environment();
  matrix const axes;
  auto const cache_levels = size_levels(read_caches());

  // Rows either come from an explicit COSORT_ROWS list or from size levels.
  struct size_point {
    std::size_t rows;
    std::string name;
  };
  std::vector<size_point> sizes;
  if (!axes.rows.empty()) {
    for (auto rows : axes.rows) {
      sizes.push_back({rows, "custom" + std::to_string(rows)});
    }
  } else {
    for (auto level : axes.size_levels) {
      auto const clamped = std::min<std::size_t>(level, cache_levels.size() - 1);
      sizes.push_back({
        std::size_t(cache_levels[clamped].per_column_bytes / sizeof(DataType)),
        cache_levels[clamped].name
      });
    }
  }

  std::size_t registered = 0;

  // One scalar reference per baseline shape. Name carries lanes=na and no
  // worker/threshold/partition/dsa/rle segments, matching how the main sweep
  // registers std_lex_argsort, so `speedup_vs_std` joins across every detector
  // and worker count at that shape.
  if (env_list("COSORT_BASELINE", {1}).front() != 0) {
    for (auto const & size : sizes) {
      for (auto columns : axes.columns) {
        for (auto distinct : axes.distinct) {
          config cfg;
          cfg.rows = size.rows;
          cfg.size_name = size.name;
          cfg.columns = std::max<std::size_t>(columns, 1);
          cfg.distinct = std::max<std::size_t>(distinct, 1);
          auto const name = std::string("std_lex_argsort/u32/lanes=na")
            + "/dist=" + cfg.dist_name()
            + "/order=asc"
            + "/cols=" + std::to_string(cfg.columns)
            + "/size=" + cfg.size_name;
          benchmark::RegisterBenchmark(
            name.c_str(),
            [cfg](benchmark::State & state) { run_std_baseline(state, cfg); }
          )->UseRealTime()->Unit(benchmark::kMillisecond);
          ++registered;
        }
      }
    }
  }

  for (auto const & discovery_name : axes.discovery) {
    auto const [algo, discovery] = parse_discovery(discovery_name);
    for (auto const & size : sizes) {
      for (auto columns : axes.columns) {
        for (auto workers : axes.workers) {
          for (auto distinct : axes.distinct) {
            for (auto task_threshold : axes.task_thresholds) {
              for (auto partition_threshold : axes.partition_thresholds) {
                for (auto region_bytes : axes.region_bytes) {
                  for (auto min_offload : axes.min_offload) {
                    for (auto slots : axes.dsa_slots) {
                      for (auto depth : axes.dsa_depth) {
                        config cfg;
                        cfg.rows = size.rows;
                        cfg.size_name = size.name;
                        cfg.columns = std::max<std::size_t>(columns, 1);
                        cfg.workers = std::max<std::size_t>(workers, 1);
                        cfg.distinct = std::max<std::size_t>(distinct, 1);
                        cfg.task_threshold = std::max<std::size_t>(task_threshold, 2);
                        cfg.partition_threshold = partition_threshold;
                        cfg.region_bytes = region_bytes;
                        cfg.min_offload = min_offload;
                        cfg.dsa_slots = std::max<std::size_t>(slots, 1);
                        cfg.dsa_depth = std::max<std::size_t>(depth, 1);

                        for (auto const & backend_name : axes.backends) {
                          auto const choice = parse_backend(backend_name);
                          // The synchronous detector ignores slots and depth, so
                          // registering it once per slots/depth value would just
                          // duplicate identical work.
                          if (!choice.async
                              && (slots != axes.dsa_slots.front()
                                  || depth != axes.dsa_depth.front())) {
                            continue;
                          }
                          benchmark::RegisterBenchmark(
                            benchmark_name(algo, cfg, backend_name).c_str(),
                            [cfg, choice, discovery](benchmark::State & state) {
                              if (choice.async) {
                                run_async(state, cfg, choice.backend, discovery);
                              } else {
                                run(state, cfg, choice.backend, discovery);
                              }
                            }
                          )->UseRealTime()->Unit(benchmark::kMillisecond);
                          ++registered;
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
  std::printf("registered %zu benchmark configurations\n", registered);
}

}  // namespace

int main(int argc, char ** argv) {
  register_all();
  benchmark::Initialize(&argc, argv);
  if (benchmark::ReportUnrecognizedArguments(argc, argv)) {
    return 1;
  }
  benchmark::RunSpecifiedBenchmarks();
  benchmark::Shutdown();
  return 0;
}
