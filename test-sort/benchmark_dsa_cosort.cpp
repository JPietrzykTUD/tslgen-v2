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
//   COSORT_SEAL         sealed-discovery scan range size      (default 65536)
//   COSORT_RLE          detector backends to register, by name:
//                       scalar,dml_sw,dsa_hw,dml_sw_async,dsa_hw_async
//                       (default: all five)
//   COSORT_DISCOVERY    post,incremental,sealed               (default all three)
//   COSORT_TYPES        u32,u64                               (default both)
//   COSORT_LANES        fixed SIMD lane counts                (default 2,4,8,16)
//
// Element type and lane count are compile-time specializations, registered the
// same way benchmark_multicolumn_gbench's register_lane does: u32 at 4/8/16 lanes
// and u64 at 2/4/8, i.e. SSE/AVX2/AVX512 for each. COSORT_LANES filters that set
// per type, so a lane count one type does not provide is skipped rather than an
// error -- note that 8 lanes means AVX2 for u32 but AVX512 for u64.
//
// Size levels describe bytes *per column*, so at one label u64 gets half the rows
// of u32. An explicit COSORT_ROWS is taken literally and doubles u64's footprint.
//
// The three discovery modes differ in what the detector ever sees. `post` scans
// one whole column per range but cannot offload partitions, so it is effectively
// serial. `incremental` offloads partitions but reports leaf-sized ranges, which
// fall below COSORT_MIN_OFFLOAD and never reach the device. `sealed` does both:
// partitions are distributed and each is scanned whole at COSORT_SEAL grain.
// COSORT_SEAL bounds a scan range from above only -- read `sealed_rows_mean` for
// what was achieved, and note that it governs the first column, since deeper
// columns arrive as ranges already smaller than the threshold.
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

#include "dsa_async_run_detector.hpp"
#include "dsa_run_detector.hpp"
#include "multicolumn_quicksort.hpp"

namespace {

// Element type and SIMD width are template parameters, so every (type, lanes)
// pair is its own instantiation -- exactly how benchmark_multicolumn_gbench's
// register_lane works. `fixed<N>` selects the extension providing N lanes for
// that type: u32 at 4/8/16 is SSE/AVX2/AVX512, u64 at 2/4/8 the same three.
template <class DataType, std::size_t Lanes>
using sorter_for = TslMultiColumnQuickSorter<
  DataType,
  TslPartitionKind::THREE_WAY,
  TslLeafKind::INSERTION,
  16,
  tsl::dataparallel::simd_for_t<tsl::dataparallel::fixed<Lanes>, DataType>
>;

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
  // Sealed discovery only. 65536 u32 elements is 256 KiB, i.e. one DSA region,
  // and leaves ~240 sealed ranges over a 16M-row column -- enough independent
  // scans for a 12-worker pool. Ignored by post and incremental discovery.
  std::size_t seal = 65536;

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
  std::vector<std::size_t> seal = env_list("COSORT_SEAL", {65536});
  std::vector<std::string> backends =
    parse_text_list("COSORT_RLE", {"scalar", "dml_sw", "dsa_hw", "dml_sw_async", "dsa_hw_async"});
  std::vector<std::string> discovery =
    parse_text_list("COSORT_DISCOVERY", {"post", "incremental", "sealed"});
  std::vector<std::string> types = parse_text_list("COSORT_TYPES", {"u32", "u64"});
  // Lane counts are per type: 8 is AVX2 for u32 but AVX512 for u64. The union of
  // both types' valid widths is the default, and each type keeps only its own.
  std::vector<std::size_t> lanes = env_list("COSORT_LANES", {2, 4, 8, 16});
};

// Which recursion runs. `sealed` is not a TslRunDiscoveryKind: it dispatches to
// its own entry point, so it cannot be folded into that enum.
enum class cosort_algorithm { POST, INCREMENTAL, SEALED };

template <class DataType>
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
template <class DataType>
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

// Single place that maps an algorithm choice onto a sorter call, so the
// synchronous and asynchronous benchmark bodies cannot drift apart.
// `specs` is passed in rather than built here: building it allocates, and every
// caller builds it while timing is paused.
template <class DataType, std::size_t Lanes, class Detector>
void run_sort(
  sorter_for<DataType, Lanes> const & sorter,
  std::vector<TslSortColumn<DataType>> & specs,
  config const & cfg,
  cosort_algorithm algorithm,
  Detector & detector,
  TslMultiColumnSortMetrics * metrics
) {
  if (algorithm == cosort_algorithm::SEALED) {
    sorter.sort_columns_sealed_parallel(
      specs.data(), specs.size(), cfg.rows, cfg.workers,
      cfg.task_threshold, cfg.seal, detector, metrics
    );
    return;
  }
  sorter.sort_columns_parallel(
    specs.data(), specs.size(), cfg.rows, cfg.workers,
    cfg.task_threshold, cfg.partition_threshold,
    algorithm == cosort_algorithm::INCREMENTAL
      ? TslRunDiscoveryKind::INCREMENTAL
      : TslRunDiscoveryKind::POST_SORT,
    detector, metrics
  );
}

template <class DataType>
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

  // Sealed discovery: zero on the other two paths. `sealed_rows_mean` is what the
  // seal threshold actually achieved, which it only bounds from above.
  state.counters["sealed_ranges"] = Counter(double(sort_metrics.sealed_ranges));
  state.counters["sealed_rows_mean"] = Counter(
    sort_metrics.sealed_ranges == 0 ? 0.0
      : double(sort_metrics.sealed_range_rows) / double(sort_metrics.sealed_ranges));

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
template <class DataType, std::size_t Lanes>
void run_async(benchmark::State & state, config const & cfg, TslRleBackend backend, cosort_algorithm algorithm) {
  dataset<DataType> data(cfg);
  sorter_for<DataType, Lanes> sorter(0xC0FFEEu);

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

    run_sort<DataType, Lanes>(sorter, specs, cfg, algorithm, detector, &sort_metrics);

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
  tag<DataType>(state, cfg, sort_metrics, as_sync);
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
template <class DataType>
void run_std_baseline(benchmark::State & state, config const & cfg) {
  dataset<DataType> data(cfg);
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
  tag<DataType>(state, cfg, TslMultiColumnSortMetrics{}, TslDsaRunDetectorMetrics{});
}

template <class DataType, std::size_t Lanes>
void run(benchmark::State & state, config const & cfg, TslRleBackend backend, cosort_algorithm algorithm) {
  dataset<DataType> data(cfg);
  sorter_for<DataType, Lanes> sorter(0xC0FFEEu);

  TslMultiColumnSortMetrics sort_metrics{};
  TslDsaRunDetectorMetrics rle_metrics{};

  for (auto _ : state) {
    state.PauseTiming();
    data.reset();
    auto specs = data.specs();
    // Fresh fleet per iteration so its counters describe exactly one sort.
    TslDsaDetectorFleet<DataType> fleet(backend, cfg.workers, cfg.region_bytes, cfg.min_offload);
    state.ResumeTiming();

    run_sort<DataType, Lanes>(sorter, specs, cfg, algorithm, fleet, &sort_metrics);

    state.PauseTiming();
    rle_metrics = fleet.aggregate_metrics();
    state.ResumeTiming();
  }

  if (!data.sorted()) {
    state.SkipWithError("lexicographically unsorted output");
    return;
  }
  tag<DataType>(state, cfg, sort_metrics, rle_metrics);
}

// Full dimension path so every axis the visualizer reads is populated, plus the
// DSA-specific axes. `async` is part of the rle value rather than a separate
// dimension, so scalar/sync/async are directly comparable on one axis.
auto benchmark_name(
  char const * algo,
  char const * type_name,
  std::size_t lanes,
  config const & cfg,
  cosort_algorithm algorithm,
  std::string const & backend_name
) -> std::string {
  auto const sealed = algorithm == cosort_algorithm::SEALED;
  // Sealed discovery has no partition threshold and the other two have no seal,
  // so each emits zero for the knob it does not own. The visualizer already reads
  // zero on a numeric dimension as "not applicable", which keeps rows joinable.
  return std::string(algo)
    + "/" + type_name
    + "/lanes=" + std::to_string(lanes)
    + "/dist=" + cfg.dist_name()
    + "/order=asc"
    + "/cols=" + std::to_string(cfg.columns)
    + "/size=" + cfg.size_name
    + "/workers=" + std::to_string(cfg.workers)
    + "/threshold=" + std::to_string(cfg.task_threshold)
    + "/partitions=" + std::to_string(sealed ? 0 : cfg.partition_threshold)
    + "/seal=" + std::to_string(sealed ? cfg.seal : 0)
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

auto parse_discovery(std::string const & name) -> std::pair<char const *, cosort_algorithm> {
  if (name == "post") {
    return {"deep_parallel_post_3way_ins", cosort_algorithm::POST};
  }
  if (name == "incremental") {
    return {"deep_parallel_incremental_3way_ins", cosort_algorithm::INCREMENTAL};
  }
  if (name == "sealed") {
    return {"deep_parallel_sealed_3way_ins", cosort_algorithm::SEALED};
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
    "COSORT_BASELINE", "COSORT_SEAL", "COSORT_TYPES", "COSORT_LANES",
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

// Rows per column for one element type. Size levels describe bytes *per column*,
// so u64 gets half the rows of u32 at the same label -- the same semantics as
// make_size_levels in the main benchmark. An explicit COSORT_ROWS is taken
// literally, which does mean equal rows and double the bytes for u64.
struct size_point {
  std::size_t rows;
  std::string name;
};

template <class DataType>
auto size_points(matrix const & axes, std::vector<size_level> const & cache_levels)
  -> std::vector<size_point> {
  std::vector<size_point> sizes;
  if (!axes.rows.empty()) {
    for (auto rows : axes.rows) {
      sizes.push_back({rows, "custom" + std::to_string(rows)});
    }
    return sizes;
  }
  for (auto level : axes.size_levels) {
    auto const clamped = std::min<std::size_t>(level, cache_levels.size() - 1);
    sizes.push_back({
      std::size_t(cache_levels[clamped].per_column_bytes / sizeof(DataType)),
      cache_levels[clamped].name
    });
  }
  return sizes;
}

// One scalar reference per (type, shape). Lanes-independent, so it is registered
// once per requested element type rather than per lane count -- tying it to a
// particular lane count would drop it whenever that count is not requested.
// Name carries lanes=na and no worker/threshold/partition/dsa/rle segments,
// matching how the main sweep registers std_lex_argsort, so `speedup_vs_std`
// joins across every detector, lane count and worker count at that shape.
template <class DataType>
auto register_baseline(
  char const * type_name,
  matrix const & axes,
  std::vector<size_level> const & cache_levels
) -> std::size_t {
  if (env_list("COSORT_BASELINE", {1}).front() == 0) {
    return 0;
  }
  auto const sizes = size_points<DataType>(axes, cache_levels);
  std::size_t registered = 0;
  {
    for (auto const & size : sizes) {
      for (auto columns : axes.columns) {
        for (auto distinct : axes.distinct) {
          config cfg;
          cfg.rows = size.rows;
          cfg.size_name = size.name;
          cfg.columns = std::max<std::size_t>(columns, 1);
          cfg.distinct = std::max<std::size_t>(distinct, 1);
          auto const name = std::string("std_lex_argsort/") + type_name + "/lanes=na"
            + "/dist=" + cfg.dist_name()
            + "/order=asc"
            + "/cols=" + std::to_string(cfg.columns)
            + "/size=" + cfg.size_name;
          benchmark::RegisterBenchmark(
            name.c_str(),
            [cfg](benchmark::State & state) { run_std_baseline<DataType>(state, cfg); }
          )->UseRealTime()->Unit(benchmark::kMillisecond);
          ++registered;
        }
      }
    }
  }
  return registered;
}

// Registers every algorithm x detector combination for one (type, lanes)
// specialization, mirroring register_lane in benchmark_multicolumn_gbench.
template <class DataType, std::size_t Lanes>
auto register_variant(
  char const * type_name,
  matrix const & axes,
  std::vector<size_level> const & cache_levels
) -> std::size_t {
  auto const sizes = size_points<DataType>(axes, cache_levels);
  std::size_t registered = 0;

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
                       for (auto seal : axes.seal) {
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
                        cfg.seal = std::max<std::size_t>(seal, 1);

                        // Each algorithm owns one of the two range knobs and
                        // ignores the other, so sweeping the ignored one would
                        // register byte-different names for identical work.
                        auto const sealed = discovery == cosort_algorithm::SEALED;
                        if (sealed && partition_threshold != axes.partition_thresholds.front()) {
                          continue;
                        }
                        if (!sealed && seal != axes.seal.front()) {
                          continue;
                        }

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
                            benchmark_name(
                              algo, type_name, Lanes, cfg, discovery, backend_name
                            ).c_str(),
                            [cfg, choice, discovery](benchmark::State & state) {
                              if (choice.async) {
                                run_async<DataType, Lanes>(state, cfg, choice.backend, discovery);
                              } else {
                                run<DataType, Lanes>(state, cfg, choice.backend, discovery);
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
  }
  return registered;
}

// Skips a (type, lanes) pair the environment did not ask for. A lane count that
// this type does not provide is simply not registered.
template <class DataType, std::size_t Lanes>
auto register_if_requested(
  char const * type_name,
  matrix const & axes,
  std::vector<size_level> const & cache_levels
) -> std::size_t {
  auto const wants_type = std::find(axes.types.begin(), axes.types.end(), type_name)
    != axes.types.end();
  auto const wants_lanes = std::find(axes.lanes.begin(), axes.lanes.end(), Lanes)
    != axes.lanes.end();
  if (!wants_type || !wants_lanes) {
    return 0;
  }
  return register_variant<DataType, Lanes>(type_name, axes, cache_levels);
}

void register_all() {
  warn_about_unused_environment();
  matrix const axes;
  auto const cache_levels = size_levels(read_caches());
  for (auto const & type : axes.types) {
    if (type != "u32" && type != "u64") {
      throw std::invalid_argument("unknown COSORT_TYPES value: " + type);
    }
  }

  std::size_t registered = 0;
  // Counted apart from the baseline: a lane count no requested type provides
  // leaves the baseline registered and every sorter row missing, which reads as a
  // finished run with no data unless it is called out.
  std::size_t variants = 0;
  // Same six specializations as the main benchmark: u32 at 4/8/16 lanes and u64
  // at 2/4/8, i.e. SSE/AVX2/AVX512 for each. COSORT_TYPES and COSORT_LANES
  // narrow the set; a lane count that no requested type provides simply matches
  // nothing, which the summary below makes visible.
  for (auto const & type : axes.types) {
    if (type == "u32") {
      registered += register_baseline<std::uint32_t>("u32", axes, cache_levels);
    } else {
      registered += register_baseline<std::uint64_t>("u64", axes, cache_levels);
    }
  }
  variants += register_if_requested<std::uint32_t, 4>("u32", axes, cache_levels);
  variants += register_if_requested<std::uint32_t, 8>("u32", axes, cache_levels);
  variants += register_if_requested<std::uint32_t, 16>("u32", axes, cache_levels);
  variants += register_if_requested<std::uint64_t, 2>("u64", axes, cache_levels);
  variants += register_if_requested<std::uint64_t, 4>("u64", axes, cache_levels);
  variants += register_if_requested<std::uint64_t, 8>("u64", axes, cache_levels);

  if (variants == 0) {
    std::printf(
      "warning: COSORT_TYPES/COSORT_LANES selected no sort configuration; only "
      "the std::sort baseline will run. Valid lane counts are 4,8,16 for u32 "
      "and 2,4,8 for u64.\n"
    );
  }
  std::printf(
    "registered %zu benchmark configurations (%zu sort, %zu baseline)\n",
    registered + variants, variants, registered
  );
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
