/**
 * @file cosort_bench.cpp
 * @brief Staged Google Benchmark driver for the lexicographic multi-column co-sort.
 *
 * Built on three decisions recorded in benchmark.md:
 *
 *  - data comes from `TslDatasetSource`, so the nine documented dataset shapes
 *    with measured descriptors are generated in memory and shared across every
 *    case that uses them, and nothing is materialized on disk;
 *  - correctness is a byte comparison against the reference image, which is exact
 *    because the sorted image is unique when every column is a sort key;
 *  - the variant space is registered through per-family predicates selected by
 *    `COSORT_STAGE`, and whatever a stage drops is counted and reported.
 *
 * Register width and implementation style are part of a variant, not axes it is
 * measured under: both are template parameters of the sorter.
 *
 *   COSORT_STAGE       screen | tune | characterize | attribute  (default screen)
 *   COSORT_STYLES      intr,clang,clang_bool      which implementation families
 *   COSORT_MOVEMENTS   direct,index               permute columns, or a row index
 *   COSORT_WIDTHS      128,256,512                register widths in bits
 *   COSORT_ELEMENTS    4,8                        element widths in bytes
 *   COSORT_SHAPES      dataset id prefixes, e.g. unique_last_g64; empty = all
 *   COSORT_SIZE_LEVELS 0..5                       L1,L2,halfLLC,LLC,2xLLC,16xLLC
 *   COSORT_COLUMNS     sort-column counts
 *   COSORT_DIRECTIONS  0 asc, 1 desc, 2 alternating
 *   COSORT_VARIANTS    algorithm names to keep, e.g. post_3way_ins; empty = stage default
 *   COSORT_SKIP_VARIANTS  name prefixes to drop, e.g. deep_parallel; empty = drop none
 *   COSORT_RLE         detector backends: scalar,dml_sw,dsa_hw,dml_sw_async,
 *                      dsa_hw_async,iaa_hw,iaa_hw_async -- whichever the build has
 *   COSORT_REGION_BYTES / COSORT_MIN_OFFLOAD / COSORT_DSA_SLOTS / COSORT_DSA_DEPTH
 *   COSORT_WORKERS / COSORT_TASK_THRESHOLD / COSORT_PARTITION_THRESHOLD
 *   COSORT_MEMORY_CAP_BYTES / COSORT_CACHE_BYTES / COSORT_DESCRIBE
 *
 * Every list replaces its stage default. Do not pin the process to one CPU when
 * measuring the parallel variants.
 */

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <chrono>
#include <cstdlib>
#include <numeric>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

#ifdef TSL_COSORT_WITH_GBENCH
#include <benchmark/benchmark.h>
#endif

#include "cosort_case.hpp"
#include "cosort_case_runner.hpp"
#include "sorting/sample_sort/samplesort_multicolumn.hpp"
#include "sorting/quicksort/multicolumn_index_sort.hpp"
#include "cosort_detectors.hpp"
#include "common/cpu_affinity.hpp"
#include "cosort_plan.hpp"
#include "datagen/dataset_catalog.hpp"
#include "datagen/dataset_descriptor.hpp"
#include "tsl_simd_for.hpp"

namespace {

constexpr auto tsl_style_available(TslStyle style) -> bool {
  switch (style) {
    // Every profile carries the scalar extension, so this is available wherever
    // the build is.
    case TslStyle::Scalar: return true;
    case TslStyle::Intrinsics: return true;
    case TslStyle::ClangBuiltin: return tsl_clang_style_available;
    case TslStyle::ClangBoolMask: return tsl_clang_bool_style_available;
  }
  return false;
}

// --- environment ------------------------------------------------------------

auto env_text(char const * name, std::string fallback) -> std::string {
  auto const * value = std::getenv(name);
  return value == nullptr ? std::move(fallback) : std::string{value};
}

auto env_u64(char const * name, std::uint64_t fallback) -> std::uint64_t {
  auto const * value = std::getenv(name);
  return value == nullptr ? fallback : std::strtoull(value, nullptr, 0);
}

auto split_list(std::string const & text) -> std::vector<std::string> {
  std::vector<std::string> items;
  std::size_t start = 0;
  while (start <= text.size()) {
    auto const comma = text.find(',', start);
    auto const token = text.substr(start, comma - start);
    if (!token.empty()) items.push_back(token);
    if (comma == std::string::npos) break;
    start = comma + 1;
  }
  return items;
}

template <class Value>
auto env_numeric_list(char const * name, std::vector<Value> fallback) -> std::vector<Value> {
  auto const * value = std::getenv(name);
  if (value == nullptr) return fallback;
  std::vector<Value> items;
  for (auto const & token : split_list(value)) {
    items.push_back(static_cast<Value>(std::strtoull(token.c_str(), nullptr, 10)));
  }
  return items.empty() ? fallback : items;
}

auto load_plan() -> TslStagePlan {
  auto plan = tsl_default_plan(tsl_stage_from_name(env_text("COSORT_STAGE", "screen")));
  if (auto const * value = std::getenv("COSORT_STYLES")) {
    plan.styles.clear();
    for (auto const & token : split_list(value)) {
      plan.styles.push_back(tsl_style_from_name(token));
    }
  }
  if (auto const * value = std::getenv("COSORT_MOVEMENTS")) {
    plan.movements.clear();
    for (auto const & token : split_list(value)) {
      plan.movements.push_back(tsl_movement_from_name(token));
    }
    if (plan.movements.empty()) plan.movements = {TslMovement::Direct};
  }
  plan.widths = env_numeric_list<std::size_t>("COSORT_WIDTHS", plan.widths);
  plan.element_bytes = env_numeric_list<std::size_t>("COSORT_ELEMENTS", plan.element_bytes);
  plan.size_levels = env_numeric_list<std::size_t>("COSORT_SIZE_LEVELS", plan.size_levels);
  // The key-width axis, overridable like every other. The attribute stage runs both
  // widths because lane count is what separates one style's codegen from another's,
  // which doubles it -- and without a knob there was no way to halve it again on a
  // host where that stage is the long pole.
  plan.element_bytes = env_numeric_list<std::size_t>("COSORT_ELEMENT_BYTES", plan.element_bytes);
  plan.columns = env_numeric_list<std::size_t>("COSORT_COLUMNS", plan.columns);
  plan.directions = env_numeric_list<int>("COSORT_DIRECTIONS", plan.directions);
  if (auto const * value = std::getenv("COSORT_SHAPES")) plan.shapes = split_list(value);
  plan.worker_count = static_cast<std::size_t>(env_u64(
    "COSORT_WORKERS",
    plan.worker_count == 0 ? tsl_usable_cpu_count() : plan.worker_count
  ));
  plan.task_threshold = static_cast<std::size_t>(env_u64("COSORT_TASK_THRESHOLD", plan.task_threshold));
  plan.partition_threshold =
    static_cast<std::size_t>(env_u64("COSORT_PARTITION_THRESHOLD", plan.partition_threshold));
  if (auto const * value = std::getenv("COSORT_RLE")) {
    plan.detectors.clear();
    for (auto const & token : split_list(value)) {
      plan.detectors.push_back(tsl_detector_from_name(token));
    }
  }
  plan.detector_config.region_bytes =
    static_cast<std::size_t>(env_u64("COSORT_REGION_BYTES", plan.detector_config.region_bytes));
  plan.detector_config.min_offload =
    static_cast<std::size_t>(env_u64("COSORT_MIN_OFFLOAD", plan.detector_config.min_offload));
  plan.detector_config.slots =
    static_cast<std::size_t>(env_u64("COSORT_DSA_SLOTS", plan.detector_config.slots));
  plan.detector_config.depth =
    static_cast<std::size_t>(env_u64("COSORT_DSA_DEPTH", plan.detector_config.depth));
  plan.memory_cap = env_u64("COSORT_MEMORY_CAP_BYTES", plan.memory_cap);
  plan.cache_bytes = static_cast<std::size_t>(env_u64("COSORT_CACHE_BYTES", plan.cache_bytes));
  plan.describe_datasets = env_u64("COSORT_DESCRIBE", plan.describe_datasets ? 1 : 0) != 0;
  plan.detector_config.workers = plan.worker_count;
  return plan;
}

// --- naming -----------------------------------------------------------------

auto direction_of(int id) -> TslDirection {
  switch (id) {
    case 1: return TslDirection::Descending;
    case 2: return TslDirection::Alternating;
    default: return TslDirection::Ascending;
  }
}

// The same metadata as `case_name`, as schema fields. Both exist while both paths
// do: the name is what Google Benchmark reports under, the row is what the CSV
// carries.
inline auto case_row(
  TslPaperResults & results,
  std::string const & algorithm,
  char const * style,
  std::string const & lanes,
  TslDatasetSpec const & spec,
  int direction,
  TslSizeLevel const & size,
  TslStagePlan const & plan,
  TslDetectorBackend backend,
  std::size_t element_bytes,
  std::size_t rows,
  bool parallel,
  TslMovement movement
) -> TslPaperRow {
  auto row = results.make_row();
  row.shape = tsl_dataset_label(spec);
  row.shape_params = tsl_dataset_params(spec);
  row.rows = rows;
  row.columns = spec.columns;
  row.element_bytes = element_bytes;
  row.algorithm = algorithm;
  // The direction belongs in the variant too: the corpus registers ascending and
  // descending cases, and without it two rows differing only by direction are
  // indistinguishable in the CSV -- which is how three identical-looking
  // samplesort rows turned up in the first paper-path run.
  row.variant = std::string("style=") + style + "/lanes=" + lanes
                + "/move=" + tsl_movement_name(movement)
                + "/order=" + tsl_direction_name(direction_of(direction));
  row.detector = tsl_detector_name(backend);
  row.workers = parallel ? plan.worker_count : 1;
  row.size_level = size.name;
  return row;
}

auto case_name(
  std::string const & algorithm,
  char const * type_name,
  char const * style,
  std::string const & lanes,
  TslDatasetSpec const & spec,
  int direction,
  TslSizeLevel const & size,
  TslStagePlan const & plan,
  TslDetectorBackend backend,
  bool parallel,
  bool deep,
  TslMovement movement
) -> std::string {
  auto name = algorithm
    + "/" + type_name
    + "/move=" + tsl_movement_name(movement)
    + "/style=" + style
    + "/lanes=" + lanes
    + "/shape=" + tsl_dataset_label(spec)
    + "/sparams=" + tsl_dataset_params(spec)
    + "/order=" + tsl_direction_name(direction_of(direction))
    + "/cols=" + std::to_string(spec.columns)
    + "/size=" + size.name
    + "/stage=" + tsl_stage_name(plan.stage)
    + "/rle=" + tsl_detector_name(backend);
  if (parallel) {
    name += "/workers=" + std::to_string(plan.worker_count)
          + "/threshold=" + std::to_string(plan.task_threshold);
  }
  if (deep) {
    name += "/partitions=" + std::to_string(plan.partition_threshold);
  }
  return name;
}

// --- counters ---------------------------------------------------------------
template <class Runner>
void publish(
  Runner & runner,
  std::size_t rows,
  std::size_t columns,
  std::size_t lanes,
  std::size_t element_bytes,
  int algorithm,
  TslMultiColumnSortMetrics const * metrics,
  TslDatasetDescriptor const * descriptor
) {
  // Items and bytes per second were Google Benchmark's own throughput lines. The
  // schema reports nanoseconds per row and every consumer divides from there, so
  // there is nothing left for them to say.
  runner.counters["count"] = static_cast<double>(rows);
  runner.counters["cols"] = static_cast<double>(columns);
  runner.counters["lanes"] = static_cast<double>(lanes);
  runner.counters["elem_bytes"] = static_cast<double>(element_bytes);
  runner.counters["algo"] = static_cast<double>(algorithm);
  if (metrics != nullptr && rows != 0) {
    runner.counters["rle_values_per_row"] =
      static_cast<double>(metrics->rle_values_scanned) / static_cast<double>(rows);
    runner.counters["direct_equal_bands"] = static_cast<double>(metrics->direct_equal_bands);
    runner.counters["direct_band_rows"] = static_cast<double>(metrics->direct_equal_band_rows);
    runner.counters["tasks_submitted"] = static_cast<double>(metrics->tasks_submitted);
    runner.counters["tasks_inline"] = static_cast<double>(metrics->tasks_executed_inline);
    runner.counters["max_outstanding"] = static_cast<double>(metrics->max_outstanding_tasks);
    runner.counters["partition_tasks"] = static_cast<double>(metrics->partition_tasks_submitted);
  }
  // Intrinsic-work descriptors, so time can be normalized across unlike shapes
  // instead of compared as raw ns/row. Optional because computing them costs a
  // reference sort of its own.
  if (descriptor != nullptr && rows != 0) {
    runner.counters["work_per_row"] =
      descriptor->weighted_work / static_cast<double>(rows);
    runner.counters["scan_per_row"] =
      descriptor->scan_volume / static_cast<double>(rows);
    runner.counters["distinct_first"] = descriptor->distinct_prefixes.empty()
      ? 0.0 : static_cast<double>(descriptor->distinct_prefixes.front());
    runner.counters["duplicate_tuple_frac"] = descriptor->duplicate_tuple_fraction;
  }
}

// --- the measured body ------------------------------------------------------

template <class Runner, class DataType, TslStyle Style, std::size_t Width,
          TslPartitionKind Partition, TslLeafKind Leaf, std::size_t FillPercent>
void run_case(
  Runner & runner,
  TslVariant variant,
  TslDatasetSpec spec,
  int direction,
  TslDetectorBackend backend,
  TslStagePlan plan
) {
  using Simd = typename tsl_simd_for<DataType, Style, Width>::type;
  using Sorter =
    TslMultiColumnQuickSorter<DataType, Partition, Leaf, 16, Simd, FillPercent>;

  TslBenchCase<DataType> data(spec, direction_of(direction), plan.cache_bytes);
  Sorter sorter(tsl_spec_seed(spec) ^ static_cast<std::uint64_t>(direction));
  TslMultiColumnSortMetrics metrics;
  // Filled by the verification pass inside `measure`, so the message survives to
  // the drop below.
  std::string failure;
  auto const partition_threshold =
    variant.execution == TslExecution::DeepParallel ? plan.partition_threshold : 0;

  if (variant.execution == TslExecution::Serial) {
    // The serial driver calls the scalar scan directly: there is no detector seam
    // on that path, which is why registration only offers it `rle=scalar`.
    runner.measure(
      // Untimed: an in-place sort consumes the table, and charging the copy that
      // gives it back to the sort would report a memcpy.
      [&] { data.reset(); },
      [&] {
        sorter.sort_columns(data.specs(), data.column_count(), data.rows(),
                            variant.discovery, &metrics);
        tsl_do_not_optimize(data.specs());
        tsl_clobber_memory();
      },
      [&] { failure = data.verify(); return failure.empty(); });
  } else {
    // One detector per case rather than per iteration: an accelerator fleet
    // allocates scratch proportional to slots x depth x region size, which would
    // dominate a short case. Its counters therefore accumulate over iterations and
    // are divided by the iteration count when published.
    tsl_with_detector<DataType>(backend, plan.detector_config, [&](auto & detector) {
      runner.measure(
        [&] { data.reset(); },
        [&] {
          sorter.sort_columns_parallel(data.specs(), data.column_count(), data.rows(),
                                      plan.worker_count, plan.task_threshold,
                                      partition_threshold, variant.discovery,
                                      detector, &metrics);
          tsl_do_not_optimize(data.specs());
          tsl_clobber_memory();
        },
        [&] { failure = data.verify(); return failure.empty(); });
      auto const iterations = std::max<std::int64_t>(static_cast<std::int64_t>(runner.iterations()), 1);
      tsl_publish_detector_metrics(detector, [&](char const * name, double value) {
        auto const ratio = std::string(name).find("frac") != std::string::npos;
        runner.counters[name] = ratio ? value : value / static_cast<double>(iterations);
      });
    });
  }

  if (!failure.empty()) {
    runner.fail("incorrect result: " + failure);
    return;
  }
  TslDatasetDescriptor descriptor;
  if (plan.describe_datasets) {
    descriptor = tsl_shared_source<DataType>(plan.cache_bytes).descriptor(spec);
  }
  publish(runner, data.rows(), data.column_count(), Simd::lane_count_v, sizeof(DataType),
          variant.algorithm_id(), &metrics, plan.describe_datasets ? &descriptor : nullptr);
  if constexpr (FillPercent != 0) {
    // The rule is derived from type and lane count, so record which one ran.
    runner.counters["hybrid_fill_percent"] = static_cast<double>(FillPercent);
  }
}

template <class Runner, class DataType>
void run_baseline(
  Runner & runner,
  TslDatasetSpec spec,
  int direction,
  TslStagePlan plan
) {
  TslBenchCase<DataType> data(spec, direction_of(direction), plan.cache_bytes);
  auto const ascending = tsl_direction_ascending(direction_of(direction), spec.columns);
  std::vector<std::uint32_t> order(data.rows());
  std::vector<DataType> gather(data.rows());

  std::string failure;
  runner.measure(
    [&] { data.reset(); },
    [&] {
    auto * specs = data.specs();
    std::iota(order.begin(), order.end(), 0u);
    std::sort(order.begin(), order.end(), [&](std::uint32_t left, std::uint32_t right) {
      for (std::size_t column = 0; column < spec.columns; ++column) {
        auto const a = specs[column].data[left];
        auto const b = specs[column].data[right];
        if (a != b) return ascending[column] ? a < b : a > b;
      }
      return false;
    });
    for (std::size_t column = 0; column < spec.columns; ++column) {
      for (std::size_t row = 0; row < data.rows(); ++row) {
        gather[row] = specs[column].data[order[row]];
      }
      std::copy(gather.begin(), gather.end(), specs[column].data);
    }
    tsl_do_not_optimize(data.specs());
    tsl_clobber_memory();
    },
    [&] { failure = data.verify(); return failure.empty(); });

  if (!failure.empty()) {
    runner.fail("incorrect result: " + failure);
    return;
  }
  publish(runner, data.rows(), spec.columns, 0, sizeof(DataType), 0, nullptr, nullptr);
}

// The indirect body: the columns stay read-only and the sort produces a row
// permutation, so the oracle is the value image the permutation selects.
template <class Runner, class DataType, TslStyle Style, std::size_t Width,
          TslPartitionKind Partition, TslLeafKind Leaf, std::size_t FillPercent>
void run_index_case(
  Runner & runner,
  TslVariant variant,
  TslDatasetSpec spec,
  int direction,
  TslDetectorBackend backend,
  TslStagePlan plan
) {
  using Simd = typename tsl_simd_for<DataType, Style, Width>::type;
  using Sorter =
    TslMultiColumnIndexSorter<DataType, Partition, Leaf, Simd, FillPercent>;

  TslBenchCase<DataType> data(spec, direction_of(direction), plan.cache_bytes);
  Sorter sorter(tsl_spec_seed(spec) ^ static_cast<std::uint64_t>(direction));
  TslIndexSortMetrics metrics;
  std::string failure;

  // Discovery runs between levels on the materialized key buffer, so the seam is
  // available on this serial path -- unlike the direct serial driver, which calls
  // the scalar scan directly. Both executions poll, so an asynchronous backend runs
  // here too: the parallel form from its task executor, the serial one at each
  // level boundary of its level loop.
  tsl_with_detector<DataType>(backend, plan.detector_config, [&](auto & detector) {
    auto const parallel = variant.execution != TslExecution::Serial;
    // No reset: this family leaves the columns read-only and writes a
    // permutation, so every pass starts from the same input already.
    runner.measure(
      [] {},
      [&] {
        if (parallel) {
          sorter.sort_index_parallel(data.specs(), data.column_count(), data.index(),
                                     data.rows(), variant.discovery, detector,
                                     plan.worker_count, &metrics);
        } else {
          sorter.sort_index(data.specs(), data.column_count(), data.index(), data.rows(),
                            variant.discovery, detector, &metrics);
        }
        tsl_do_not_optimize(data.index());
        tsl_clobber_memory();
      },
      [&] { failure = data.verify_index(); return failure.empty(); });
    // Same publication the direct path does: without it a frequency-backed row
    // shows a plausible ratio and no way to tell how much of its discovery
    // actually came from the counts.
    auto const iterations = std::max<std::int64_t>(static_cast<std::int64_t>(runner.iterations()), 1);
    tsl_publish_detector_metrics(detector, [&](char const * name, double value) {
      auto const ratio = std::string(name).find("coverage") != std::string::npos
        || std::string(name).find("frac") != std::string::npos;
      runner.counters[name] = ratio ? value : value / static_cast<double>(iterations);
    });
  });

  if (!failure.empty()) {
    runner.fail("incorrect result: " + failure);
    return;
  }

  auto const published_iterations = std::max<std::int64_t>(static_cast<std::int64_t>(runner.iterations()), 1);
  runner.counters["materialized_per_row"] = data.rows() == 0
    ? 0.0
    : static_cast<double>(metrics.materialized_elements)
      / static_cast<double>(published_iterations * static_cast<std::int64_t>(data.rows()));
  runner.counters["levels"] =
    static_cast<double>(metrics.levels) / static_cast<double>(published_iterations);
  runner.counters["ranges_sorted"] =
    static_cast<double>(metrics.ranges_sorted) / static_cast<double>(published_iterations);
  runner.counters["tasks"] =
    static_cast<double>(metrics.tasks) / static_cast<double>(published_iterations);
  runner.counters["levels_split"] =
    static_cast<double>(metrics.levels_split) / static_cast<double>(published_iterations);
  TslMultiColumnSortMetrics shared{};
  auto const per_iteration = static_cast<std::size_t>(published_iterations);
  shared.rle_values_scanned = metrics.rle_values_scanned / per_iteration;
  shared.direct_equal_bands = metrics.direct_equal_bands / per_iteration;
  shared.direct_equal_band_rows = metrics.direct_equal_band_rows / per_iteration;
  publish(runner, data.rows(), data.column_count(), Simd::lane_count_v, sizeof(DataType),
          variant.algorithm_id(), &shared, nullptr);
  if constexpr (FillPercent != 0) {
    runner.counters["hybrid_fill_percent"] = static_cast<double>(FillPercent);
  }
}


// --- samplesort, for the portability question ---------------------------------
//
// Q6 asks whether the implementation style and register width cost anything, and
// until now it answered that for the quicksort only -- so "TSL gives portable
// performance" rested on one of the two algorithms. The samplesort is not a point
// in the quicksort's variant space (its axes are bucket count, base case, base
// leaf, ids, movement), so it is registered separately, and with one
// configuration per cell rather than its own product: the question here is the
// cell, not the configuration. That configuration is the reference point the
// descent settled on, fixed in source deliberately -- this driver is a
// google-benchmark binary with no access to `best_config.tsv`, and a portability
// comparison wants the *same* configuration in every cell anyway, otherwise it
// measures tuning rather than portability.
template <class Runner, class DataType, TslStyle Style, std::size_t Width>
void run_samplesort_case(
  Runner & runner,
  TslDatasetSpec spec,
  int direction,
  TslDetectorBackend backend,
  TslStagePlan plan,
  bool parallel
) {
  using Simd = typename tsl_simd_for<DataType, Style, Width>::type;
  constexpr std::size_t base_case = 256;
  using Sorter = TslSampleSortMultiColumn<
    DataType, Simd, 16, TslSampleSortBuckets::Adaptive, 8, base_case,
    TslSampleSortBase::Network, TslSampleSortIds::Byte,
    base_case / Simd::lane_count_v, 50, TslSampleSortMovement::OutOfPlace, false>;

  TslBenchCase<DataType> data(spec, direction_of(direction), plan.cache_bytes);
  Sorter sorter;
  TslSampleSortColumnMetrics metrics;
  std::string failure;

  tsl_with_detector<DataType>(backend, plan.detector_config, [&](auto & detector) {
    // The sorter's worklist implements the pending-work contract at every worker
    // count, so an asynchronous backend runs here as well. "Nothing to overlap
    // with at one worker" was the earlier reasoning and it was wrong: a serial
    // samplesort still has the rest of its level to sort while a range is on the
    // device, and at sixteen times the last level that made the asynchronous
    // detector the fastest of the three at one worker.
    //
    // Index movement, so the columns are untouched and no reset is needed.
    runner.measure(
      [] {},
      [&] {
        if (parallel) {
          sorter.sort_index_parallel(data.specs(), data.column_count(), data.index(),
                                     data.rows(), detector, plan.worker_count,
                                     &metrics);
        } else {
          sorter.sort_index(data.specs(), data.column_count(), data.index(),
                            data.rows(), detector, &metrics);
        }
        tsl_do_not_optimize(data.index());
        tsl_clobber_memory();
      },
      [&] { failure = data.verify_index(); return failure.empty(); });
    auto const iterations = std::max<std::int64_t>(static_cast<std::int64_t>(runner.iterations()), 1);
    tsl_publish_detector_metrics(detector, [&](char const * name, double value) {
      auto const ratio = std::string(name).find("coverage") != std::string::npos
        || std::string(name).find("frac") != std::string::npos;
      runner.counters[name] = ratio ? value : value / static_cast<double>(iterations);
    });
  });

  if (!failure.empty()) {
    runner.fail("incorrect result: " + failure);
    return;
  }

  auto const published = std::max<std::int64_t>(static_cast<std::int64_t>(runner.iterations()), 1);
  runner.counters["materialized_per_row"] = data.rows() == 0
    ? 0.0
    : static_cast<double>(metrics.materialized_elements)
      / static_cast<double>(published * static_cast<std::int64_t>(data.rows()));
  runner.counters["ranges_sorted"] =
    static_cast<double>(metrics.ranges) / static_cast<double>(published);
  runner.counters["deepest_column"] = static_cast<double>(metrics.deepest_column);
  TslMultiColumnSortMetrics shared{};
  shared.rle_values_scanned =
    metrics.detected_elements / static_cast<std::size_t>(published);
  // 200-series ids: the index quicksort uses 100 + its algorithmic id, so the
  // samplesort starts above that and no published id moves.
  publish(runner, data.rows(), data.column_count(), Simd::lane_count_v,
          sizeof(DataType), parallel ? 201 : 200, &shared, nullptr);
}

// --- registration -----------------------------------------------------------

// One registered case in the paper path: the row it will fill, and how to run it.
// The metadata is carried as fields rather than parsed back out of a benchmark
// name, which is what the JSON round trip had to do -- and could not do for
// `verified`.
struct PaperCase {
  TslPaperRow row;
  std::size_t elements = 0;
  std::function<void(TslPaperRunner &)> run;
};

struct Registrar {
  TslStagePlan plan;
  std::vector<TslSizeLevel> levels;
  std::vector<std::string> keep_variants;   // COSORT_VARIANTS, empty keeps all
  // COSORT_SKIP_VARIANTS, matched as a prefix. COSORT_VARIANTS is an allow-list, so
  // excluding one family through it means naming the other twenty-four -- and
  // "run everything except the family I am currently debugging" is the common case,
  // not the rare one.
  std::vector<std::string> skip_variants;
  TslDropLog drops;
  std::size_t registered = 0;
  // Empty unless --paper-csv was given, in which case registration collects the
  // cases here instead of handing them to Google Benchmark.
  bool paper_mode = false;
  std::vector<PaperCase> cases;
  TslPaperResults * results = nullptr;

  auto wants(TslVariant const & variant) -> bool {
    if (!plan.admits(variant)) {
      drops.drop(TslDropReason::StageVariant);
      return false;
    }
    if (!keep_variants.empty()) {
      auto const name = variant.algorithm_name();
      if (std::find(keep_variants.begin(), keep_variants.end(), name) == keep_variants.end()) {
        drops.drop(TslDropReason::StageVariant);
        return false;
      }
    }
    if (!skip_variants.empty()) {
      auto const name = variant.algorithm_name();
      for (auto const & prefix : skip_variants) {
        if (!prefix.empty() && name.rfind(prefix, 0) == 0) {
          drops.drop(TslDropReason::StageVariant);
          return false;
        }
      }
    }
    if (!tsl_style_available(variant.style)) {
      drops.drop(TslDropReason::StyleUnavailable);
      return false;
    }
    if (!plan.scalar_width_ok(variant)) {
      // A scalar cell at three register widths is the same measurement three
      // times, so the other two are declined rather than run.
      drops.drop(TslDropReason::StageVariant);
      return false;
    }
    return true;
  }

  // Two-way peels one element per level out of an all-equal range, so it is
  // quadratic in the equal-run length. Registered only where that stays bounded;
  // the rule itself is `tsl_two_way_run_bounded` in cosort_case.hpp, shared with
  // the tuner so the two cannot disagree about which shapes are safe.
  auto two_way_allowed(TslDatasetSpec const & spec, TslSizeLevel const & size) -> bool {
    if (size.per_column_bytes <= plan.two_way_size_cap) {
      return true;   // small enough that even the quadratic case is cheap
    }
    return tsl_two_way_run_bounded(spec);
  }

  auto footprint_ok(TslDatasetSpec const & spec) -> bool {
    // pristine + reference + the working copy
    auto const bytes = static_cast<std::uint64_t>(3) * spec.columns * spec.rows * spec.element_bytes;
    return bytes <= plan.memory_cap;
  }
};

// Registers one case with whichever backend is active. The lambda is built once
// per path because their signatures differ; the body it calls is the same.
template <class Body>
void register_case(Registrar & registrar, std::string const & name,
                   TslPaperRow row, std::size_t elements, Body body) {
  if (registrar.paper_mode) {
    registrar.cases.push_back(PaperCase{std::move(row), elements,
                                        [body](TslPaperRunner & runner) {
                                          body(runner);
                                        }});
  } else {
#ifdef TSL_COSORT_WITH_GBENCH
    benchmark::RegisterBenchmark(
      name, [body](benchmark::State & state) {
        TslGbenchRunner runner(state);
        body(runner);
      })->Unit(benchmark::kNanosecond)->UseRealTime();
#else
    static_cast<void>(name);
#endif
  }
  ++registrar.registered;
}


template <class DataType, TslStyle Style, std::size_t Width,
          TslPartitionKind Partition, TslLeafKind Leaf, std::size_t FillPercent>
void register_leaf(Registrar & registrar, char const * type_name) {
  auto const & plan = registrar.plan;
  for (auto movement : plan.movements) {
   for (auto execution : {TslExecution::Serial, TslExecution::Parallel,
                         TslExecution::DeepParallel}) {
    for (auto discovery : {TslRunDiscoveryKind::POST_SORT, TslRunDiscoveryKind::INCREMENTAL}) {
      TslVariant const variant{execution, discovery, Partition, Leaf, Style, Width,
                               movement, FillPercent != 0};
      if (!tsl_variant_is_implementable(variant)) {
        registrar.drops.drop(TslDropReason::MovementUnsupported);
        continue;
      }
      if (!registrar.wants(variant)) {
        continue;
      }
      for (auto level : plan.size_levels) {
        if (level >= registrar.levels.size()) {
          registrar.drops.drop(TslDropReason::StageAxis);
          continue;
        }
        auto const size = registrar.levels[level];
        auto rows = static_cast<std::size_t>(size.per_column_bytes / sizeof(DataType));
        if (rows < 2) rows = 2;
        for (auto columns : plan.columns) {
          auto const catalog = tsl_default_catalog(rows, columns, sizeof(DataType));
          auto const chosen = tsl_select_datasets(catalog, plan.shapes, sizeof(DataType));
          for (auto const & spec : chosen) {
            if (!registrar.footprint_ok(spec)) {
              registrar.drops.drop(TslDropReason::FootprintCap);
              continue;
            }
            if (Partition == TslPartitionKind::TWO_WAY
                && !registrar.two_way_allowed(spec, size)) {
              registrar.drops.drop(TslDropReason::QuadraticTwoWay);
              continue;
            }
            for (auto direction : plan.directions) {
              for (auto backend : plan.detectors) {
                if (!tsl_detector_compiled(backend)) {
                  registrar.drops.drop(TslDropReason::DetectorUnavailable);
                  continue;
                }
                if (!plan.detector_applies(variant, backend, spec.columns, level)) {
                  registrar.drops.drop(TslDropReason::DetectorInapplicable);
                  continue;
                }
                auto const parallel = execution != TslExecution::Serial;
                auto const deep = execution == TslExecution::DeepParallel;
                auto const name = case_name(
                  variant.algorithm_name(), type_name, tsl_style_name(Style),
                  std::to_string(tsl_simd_for<DataType, Style, Width>::type::lane_count_v),
                  spec, direction, size, plan, backend, parallel, deep, movement
                );
                auto row = registrar.results == nullptr
                  ? TslPaperRow{}
                  : case_row(*registrar.results, variant.algorithm_name(),
                             tsl_style_name(Style),
                             std::to_string(
                               tsl_simd_for<DataType, Style, Width>::type::lane_count_v),
                             spec, direction, size, plan, backend,
                             sizeof(DataType), spec.rows, parallel, movement);
                if (movement == TslMovement::Index) {
                  register_case(
                    registrar, name, std::move(row), spec.rows,
                    [variant, spec, direction, backend, plan](auto & runner) {
                      run_index_case<std::decay_t<decltype(runner)>, DataType, Style,
                                     Width, Partition, Leaf, FillPercent>(
                        runner, variant, spec, direction, backend, plan
                      );
                    });
                } else {
                  register_case(
                    registrar, name, std::move(row), spec.rows,
                    [variant, spec, direction, backend, plan](auto & runner) {
                      run_case<std::decay_t<decltype(runner)>, DataType, Style, Width,
                               Partition, Leaf, FillPercent>(
                        runner, variant, spec, direction, backend, plan
                      );
                    });
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


// One samplesort per cell, serial and parallel. Only the stages that ask a
// style/width question register it; `screen` and `characterize` are about the
// quicksort's variant space.
template <class DataType, TslStyle Style, std::size_t Width>
void register_samplesort(Registrar & registrar, char const * type_name) {
  auto const & plan = registrar.plan;
  if (plan.stage != TslStage::Attribute) {
    return;
  }
  for (auto level : plan.size_levels) {
    if (level >= registrar.levels.size()) {
      registrar.drops.drop(TslDropReason::StageAxis);
      continue;
    }
    auto const size = registrar.levels[level];
    auto rows = static_cast<std::size_t>(size.per_column_bytes / sizeof(DataType));
    if (rows < 2) rows = 2;
    for (auto columns : plan.columns) {
      auto const catalog = tsl_default_catalog(rows, columns, sizeof(DataType));
      auto const chosen = tsl_select_datasets(catalog, plan.shapes, sizeof(DataType));
      for (auto const & spec : chosen) {
        if (!registrar.footprint_ok(spec)) {
          registrar.drops.drop(TslDropReason::FootprintCap);
          continue;
        }
        for (auto direction : plan.directions) {
          for (auto backend : plan.detectors) {
            if (!tsl_detector_compiled(backend)) {
              registrar.drops.drop(TslDropReason::DetectorUnavailable);
              continue;
            }
            // The attribute stage is serial by design -- style against style with
            // nothing else moving -- so only the serial form is registered, and
            // the detector predicate is asked about the equivalent quicksort
            // variant because the seam is the same one.
            TslVariant const equivalent{
              TslExecution::Serial, TslRunDiscoveryKind::POST_SORT,
              TslPartitionKind::THREE_WAY, TslLeafKind::NETWORK, Style, Width,
              TslMovement::Index, false};
            // Every gate the quicksort families get through `admits`, which this
            // family does not call: it builds its own variant rather than sweeping
            // them. Leaving them out was not cosmetic -- `tsl_simd_for` falls back
            // to the native type for a style this build could not compile, so 72
            // samplesort rows ran on that fallback while their `style=` column
            // said `clang` and `clang_bool`, in the one stage whose headline is
            // the style axis.
            if (!tsl_style_available(Style)) {
              registrar.drops.drop(TslDropReason::StyleUnavailable);
              continue;
            }
            if (!plan.scalar_width_ok(equivalent)) {
              registrar.drops.drop(TslDropReason::StageVariant);
              continue;
            }
            if (!plan.detector_applies(equivalent, backend, spec.columns, level)) {
              registrar.drops.drop(TslDropReason::DetectorInapplicable);
              continue;
            }
            auto const name = case_name(
              "samplesort", type_name, tsl_style_name(Style),
              std::to_string(tsl_simd_for<DataType, Style, Width>::type::lane_count_v),
              spec, direction, size, plan, backend, false, false, TslMovement::Index
            );
            register_case(
              registrar, name,
              registrar.results == nullptr
                ? TslPaperRow{}
                : case_row(*registrar.results, "samplesort", tsl_style_name(Style),
                           std::to_string(
                             tsl_simd_for<DataType, Style, Width>::type::lane_count_v),
                           spec, direction, size, plan, backend,
                           sizeof(DataType), spec.rows, false, TslMovement::Index),
              spec.rows,
              [spec, direction, backend, plan](auto & runner) {
                run_samplesort_case<std::decay_t<decltype(runner)>, DataType, Style,
                                    Width>(
                  runner, spec, direction, backend, plan, false
                );
              });
          }
        }
      }
    }
  }
}

template <class DataType, TslStyle Style, std::size_t Width>
void register_width(Registrar & registrar, char const * type_name) {
  register_samplesort<DataType, Style, Width>(registrar, type_name);
  using Simd = typename tsl_simd_for<DataType, Style, Width>::type;
  // The hybrid's threshold is derived from this type and width, not chosen, so it
  // is a constant here rather than an axis value.
  constexpr std::size_t hybrid = tsl_hybrid_auto_percent<DataType, Simd>();
  register_leaf<DataType, Style, Width, TslPartitionKind::TWO_WAY, TslLeafKind::INSERTION, 0>(registrar, type_name);
  register_leaf<DataType, Style, Width, TslPartitionKind::TWO_WAY, TslLeafKind::NETWORK, 0>(registrar, type_name);
  register_leaf<DataType, Style, Width, TslPartitionKind::TWO_WAY, TslLeafKind::NETWORK, hybrid>(registrar, type_name);
  register_leaf<DataType, Style, Width, TslPartitionKind::THREE_WAY, TslLeafKind::INSERTION, 0>(registrar, type_name);
  register_leaf<DataType, Style, Width, TslPartitionKind::THREE_WAY, TslLeafKind::NETWORK, 0>(registrar, type_name);
  register_leaf<DataType, Style, Width, TslPartitionKind::THREE_WAY, TslLeafKind::NETWORK, hybrid>(registrar, type_name);
}

template <class DataType, TslStyle Style>
void register_style(Registrar & registrar, char const * type_name) {
  auto const & widths = registrar.plan.widths;
  auto const has = [&widths](std::size_t width) {
    return std::find(widths.begin(), widths.end(), width) != widths.end();
  };
  if (has(128)) register_width<DataType, Style, 128>(registrar, type_name);
  if (has(256)) register_width<DataType, Style, 256>(registrar, type_name);
  if (has(512)) register_width<DataType, Style, 512>(registrar, type_name);
}

template <class DataType>
void register_type(Registrar & registrar, char const * type_name) {
  auto const & styles = registrar.plan.styles;
  auto const has = [&styles](TslStyle style) {
    return std::find(styles.begin(), styles.end(), style) != styles.end();
  };
  // The style axis, including the non-vector end of it: `TslStyle::Scalar` resolves
  // to `tsl::simd<DataType, tsl::scalar>`, which every profile carries, so it is
  // the same sorter sources at one lane rather than a second binary. Registered at
  // one register width only -- see `scalar_width_ok`, since one lane has no width.
  if (has(TslStyle::Scalar)) register_style<DataType, TslStyle::Scalar>(registrar, type_name);
  if (has(TslStyle::Intrinsics)) register_style<DataType, TslStyle::Intrinsics>(registrar, type_name);
  if (has(TslStyle::ClangBuiltin)) register_style<DataType, TslStyle::ClangBuiltin>(registrar, type_name);
  if (has(TslStyle::ClangBoolMask)) register_style<DataType, TslStyle::ClangBoolMask>(registrar, type_name);

  // The scalar baseline every speedup divides by: no SIMD implementation, so no
  // style and no lane count apply to it.
  auto const & plan = registrar.plan;
  for (auto level : plan.size_levels) {
    if (level >= registrar.levels.size()) continue;
    auto const size = registrar.levels[level];
    auto rows = static_cast<std::size_t>(size.per_column_bytes / sizeof(DataType));
    if (rows < 2) rows = 2;
    for (auto columns : plan.columns) {
      auto const catalog = tsl_default_catalog(rows, columns, sizeof(DataType));
      for (auto const & spec : tsl_select_datasets(catalog, plan.shapes, sizeof(DataType))) {
        if (!registrar.footprint_ok(spec)) continue;
        for (auto direction : plan.directions) {
          auto const name = case_name("std_lex_argsort", type_name, "na", "na",
                                      spec, direction, size, plan,
                                      TslDetectorBackend::Scalar, false, false,
                                      TslMovement::Direct);
          register_case(
            registrar, name,
            registrar.results == nullptr
              ? TslPaperRow{}
              : case_row(*registrar.results, "std_lex_argsort", "na", "na", spec,
                         direction, size, plan, TslDetectorBackend::Scalar,
                         sizeof(DataType), spec.rows, false, TslMovement::Direct),
            spec.rows,
            [spec, direction, plan](auto & runner) {
              run_baseline<std::decay_t<decltype(runner)>, DataType>(
                runner, spec, direction, plan);
            });
        }
      }
    }
  }
}

}  // namespace

int main(int argc, char ** argv) try {
  // `--paper-csv <path>` runs the registered cases through `paper_harness.hpp`
  // and writes the shared schema directly: verify then time, median of at least
  // nine with quartiles, resampled while the spread is wide, machine state per
  // row, drops carrying their reason. Without it the cases go to Google Benchmark
  // as before, so the two can be compared on one machine before the old path is
  // removed.
  std::string paper_csv;
  std::string question = "q5_variants";
  std::vector<char *> forwarded{argv[0]};
  for (int at = 1; at < argc; ++at) {
    auto const flag = std::string(argv[at]);
    if (flag == "--paper-csv" && at + 1 < argc) {
      paper_csv = argv[++at];
    } else if (flag == "--question" && at + 1 < argc) {
      question = argv[++at];
    } else {
      forwarded.push_back(argv[at]);
    }
  }

  Registrar registrar;
  registrar.plan = load_plan();
  TslPaperResults results(question, "cosort_bench");
  if (!paper_csv.empty()) {
    registrar.paper_mode = true;
    registrar.results = &results;
  }
  auto const caches = tsl_detect_caches();
  registrar.levels = tsl_size_levels(caches);
  registrar.keep_variants = split_list(env_text("COSORT_VARIANTS", ""));
  registrar.skip_variants = split_list(env_text("COSORT_SKIP_VARIANTS", ""));

  std::fprintf(stderr,
    "stage=%s  caches: L1=%lluKiB L2=%lluKiB LLC=%lluKiB\n",
    tsl_stage_name(registrar.plan.stage),
    static_cast<unsigned long long>(caches.l1 / 1024),
    static_cast<unsigned long long>(caches.l2 / 1024),
    static_cast<unsigned long long>(caches.llc / 1024));
  std::fprintf(stderr, "styles compiled in:");
  for (auto style : {TslStyle::Scalar, TslStyle::Intrinsics, TslStyle::ClangBuiltin,
                     TslStyle::ClangBoolMask}) {
    if (tsl_style_available(style)) std::fprintf(stderr, " %s", tsl_style_name(style));
  }
  std::fprintf(stderr, "\n");

  std::fprintf(stderr, "detectors compiled in:");
  for (auto backend : tsl_compiled_detectors()) {
    std::fprintf(stderr, " %s", tsl_detector_name(backend));
  }
  std::fprintf(stderr, "\n");

  auto const & elements = registrar.plan.element_bytes;
  if (std::find(elements.begin(), elements.end(), 4u) != elements.end()) {
    register_type<std::uint32_t>(registrar, "u32");
  }
  if (std::find(elements.begin(), elements.end(), 8u) != elements.end()) {
    register_type<std::uint64_t>(registrar, "u64");
  }

  std::fprintf(stderr, "registered %zu cases", registrar.registered);
  if (registrar.drops.total() != 0) {
    std::fprintf(stderr, "; dropped:");
    for (std::size_t reason = 0;
         reason < static_cast<std::size_t>(TslDropReason::DropReasonCount); ++reason) {
      auto const count = registrar.drops.counts[reason];
      if (count != 0) {
        std::fprintf(stderr, " %zu %s;", count,
                     tsl_drop_reason_name(static_cast<TslDropReason>(reason)));
      }
    }
  }
  std::fprintf(stderr, "\n");

  // The funnel's point is that `characterize` measures the *finalists* chosen by
  // `screen`. Left unrestricted it registers every variant, which is a much
  // larger run than intended and generates a dataset per shape and size level.
  if (registrar.plan.stage == TslStage::Characterize && registrar.keep_variants.empty()) {
    std::fprintf(stderr,
      "note: stage=characterize with no COSORT_VARIANTS registers every variant "
      "(%zu cases).\n"
      "      Set COSORT_VARIANTS to the finalists from stage=screen, e.g.\n"
      "      COSORT_VARIANTS=post_3way_net,deep_parallel_incremental_3way_net\n",
      registrar.registered);
  }

  if (registrar.paper_mode) {
    results.expect(registrar.cases.size());
    for (auto & entry : registrar.cases) {
      TslPaperRunner runner(entry.elements);
      entry.run(runner);
      auto row = entry.row;
      if (runner.dropped()) {
        results.drop(row, runner.reason());
        continue;
      }
      if (!runner.measured()) {
        results.drop(row, "the case registered but never ran");
        continue;
      }
      row.verified = runner.verified();
      row.ns_per_element = runner.stats();
      row.repetitions = runner.stats().repetitions;
      if (!row.verified) {
        results.drop(row, "verification failed");
        continue;
      }
      results.add(std::move(row));
    }
    std::fprintf(stderr, "\n%s\n", results.summary().c_str());
    results.write_csv(paper_csv);
    return 0;
  }

#ifdef TSL_COSORT_WITH_GBENCH
  int forwarded_count = static_cast<int>(forwarded.size());
  benchmark::Initialize(&forwarded_count, forwarded.data());
  if (benchmark::ReportUnrecognizedArguments(forwarded_count, forwarded.data())) {
    return 1;
  }
  benchmark::RunSpecifiedBenchmarks();
  benchmark::Shutdown();
  return 0;
#else
  std::fprintf(stderr, "built without Google Benchmark: pass --paper-csv <path>\n");
  return 2;
#endif
} catch (std::exception const & error) {
  std::fprintf(stderr, "cosort_bench failed: %s\n", error.what());
  return 1;
}
