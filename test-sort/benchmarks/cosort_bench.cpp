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
#include <cstdlib>
#include <numeric>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

#include <benchmark/benchmark.h>

#include "cosort_case.hpp"
#include "sorting/sample_sort/samplesort_multicolumn.hpp"
#include "sorting/quicksort/multicolumn_index_sort.hpp"
#include "cosort_detectors.hpp"
#include "common/cpu_affinity.hpp"
#include "cosort_plan.hpp"
#include "datagen/dataset_catalog.hpp"
#include "datagen/dataset_descriptor.hpp"
#include "tsl_simd_for.hpp"

namespace {

// The longest equal run two-way partitioning may face above the size cap. Eight is
// generous: at that length the quadratic term is 32 comparisons per run, which is
// inside the noise, while the 512-long runs of independent_uniform_c1024 are not.
inline constexpr double tsl_two_way_run_cap = 8.0;

constexpr auto tsl_style_available(TslStyle style) -> bool {
  switch (style) {
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

void publish(
  benchmark::State & state,
  std::size_t rows,
  std::size_t columns,
  std::size_t lanes,
  std::size_t element_bytes,
  int algorithm,
  TslMultiColumnSortMetrics const * metrics,
  TslDatasetDescriptor const * descriptor
) {
  state.SetItemsProcessed(static_cast<std::int64_t>(state.iterations() * rows));
  state.SetBytesProcessed(
    static_cast<std::int64_t>(state.iterations() * rows * columns * element_bytes)
  );
  state.counters["count"] = static_cast<double>(rows);
  state.counters["cols"] = static_cast<double>(columns);
  state.counters["lanes"] = static_cast<double>(lanes);
  state.counters["elem_bytes"] = static_cast<double>(element_bytes);
  state.counters["algo"] = static_cast<double>(algorithm);
  if (metrics != nullptr && rows != 0) {
    state.counters["rle_values_per_row"] =
      static_cast<double>(metrics->rle_values_scanned) / static_cast<double>(rows);
    state.counters["direct_equal_bands"] = static_cast<double>(metrics->direct_equal_bands);
    state.counters["direct_band_rows"] = static_cast<double>(metrics->direct_equal_band_rows);
    state.counters["tasks_submitted"] = static_cast<double>(metrics->tasks_submitted);
    state.counters["tasks_inline"] = static_cast<double>(metrics->tasks_executed_inline);
    state.counters["max_outstanding"] = static_cast<double>(metrics->max_outstanding_tasks);
    state.counters["partition_tasks"] = static_cast<double>(metrics->partition_tasks_submitted);
  }
  // Intrinsic-work descriptors, so time can be normalized across unlike shapes
  // instead of compared as raw ns/row. Optional because computing them costs a
  // reference sort of its own.
  if (descriptor != nullptr && rows != 0) {
    state.counters["work_per_row"] =
      descriptor->weighted_work / static_cast<double>(rows);
    state.counters["scan_per_row"] =
      descriptor->scan_volume / static_cast<double>(rows);
    state.counters["distinct_first"] = descriptor->distinct_prefixes.empty()
      ? 0.0 : static_cast<double>(descriptor->distinct_prefixes.front());
    state.counters["duplicate_tuple_frac"] = descriptor->duplicate_tuple_fraction;
  }
}

// --- the measured body ------------------------------------------------------

template <class DataType, TslStyle Style, std::size_t Width,
          TslPartitionKind Partition, TslLeafKind Leaf, std::size_t FillPercent>
void run_case(
  benchmark::State & state,
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
  auto const partition_threshold =
    variant.execution == TslExecution::DeepParallel ? plan.partition_threshold : 0;

  if (variant.execution == TslExecution::Serial) {
    // The serial driver calls the scalar scan directly: there is no detector seam
    // on that path, which is why registration only offers it `rle=scalar`.
    for (auto _ : state) {
      state.PauseTiming();
      data.reset();
      state.ResumeTiming();
      sorter.sort_columns(data.specs(), data.column_count(), data.rows(),
                          variant.discovery, &metrics);
      benchmark::DoNotOptimize(data.specs());
      benchmark::ClobberMemory();
    }
  } else {
    // One detector per case rather than per iteration: an accelerator fleet
    // allocates scratch proportional to slots x depth x region size, which would
    // dominate a short case. Its counters therefore accumulate over iterations and
    // are divided by the iteration count when published.
    tsl_with_detector<DataType>(backend, plan.detector_config, [&](auto & detector) {
      for (auto _ : state) {
        state.PauseTiming();
        data.reset();
        state.ResumeTiming();
        sorter.sort_columns_parallel(data.specs(), data.column_count(), data.rows(),
                                    plan.worker_count, plan.task_threshold,
                                    partition_threshold, variant.discovery,
                                    detector, &metrics);
        benchmark::DoNotOptimize(data.specs());
        benchmark::ClobberMemory();
      }
      auto const iterations = std::max<std::int64_t>(state.iterations(), 1);
      tsl_publish_detector_metrics(detector, [&](char const * name, double value) {
        auto const ratio = std::string(name).find("frac") != std::string::npos;
        state.counters[name] = ratio ? value : value / static_cast<double>(iterations);
      });
    });
  }

  if (auto const error = data.verify(); !error.empty()) {
    state.SkipWithError(error.c_str());
    return;
  }
  TslDatasetDescriptor descriptor;
  if (plan.describe_datasets) {
    descriptor = tsl_shared_source<DataType>(plan.cache_bytes).descriptor(spec);
  }
  publish(state, data.rows(), data.column_count(), Simd::lane_count_v, sizeof(DataType),
          variant.algorithm_id(), &metrics, plan.describe_datasets ? &descriptor : nullptr);
  if constexpr (FillPercent != 0) {
    // The rule is derived from type and lane count, so record which one ran.
    state.counters["hybrid_fill_percent"] = static_cast<double>(FillPercent);
  }
}

template <class DataType>
void run_baseline(
  benchmark::State & state,
  TslDatasetSpec spec,
  int direction,
  TslStagePlan plan
) {
  TslBenchCase<DataType> data(spec, direction_of(direction), plan.cache_bytes);
  auto const ascending = tsl_direction_ascending(direction_of(direction), spec.columns);
  std::vector<std::uint32_t> order(data.rows());
  std::vector<DataType> gather(data.rows());

  for (auto _ : state) {
    state.PauseTiming();
    data.reset();
    auto * specs = data.specs();
    state.ResumeTiming();
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
    benchmark::DoNotOptimize(data.specs());
    benchmark::ClobberMemory();
  }

  if (auto const error = data.verify(); !error.empty()) {
    state.SkipWithError(error.c_str());
    return;
  }
  publish(state, data.rows(), spec.columns, 0, sizeof(DataType), 0, nullptr, nullptr);
}

// The indirect body: the columns stay read-only and the sort produces a row
// permutation, so the oracle is the value image the permutation selects.
template <class DataType, TslStyle Style, std::size_t Width,
          TslPartitionKind Partition, TslLeafKind Leaf, std::size_t FillPercent>
void run_index_case(
  benchmark::State & state,
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

  // Discovery runs between levels on the materialized key buffer, so the seam is
  // available on this serial path -- unlike the direct serial driver, which calls
  // the scalar scan directly. Asynchronous backends are excluded at registration.
  tsl_with_detector<DataType>(backend, plan.detector_config, [&](auto & detector) {
    if constexpr (tsl_detector_wants_executor<std::decay_t<decltype(detector)>>::value) {
      state.SkipWithError("asynchronous detectors have no indirect form");
    } else {
      auto const parallel = variant.execution != TslExecution::Serial;
      for (auto _ : state) {
        if (parallel) {
          sorter.sort_index_parallel(data.specs(), data.column_count(), data.index(),
                                     data.rows(), variant.discovery, detector,
                                     plan.worker_count, &metrics);
        } else {
          sorter.sort_index(data.specs(), data.column_count(), data.index(), data.rows(),
                            variant.discovery, detector, &metrics);
        }
        benchmark::DoNotOptimize(data.index());
        benchmark::ClobberMemory();
      }
      // Same publication the direct path does: without it a frequency-backed row
      // shows a plausible ratio and no way to tell how much of its discovery
      // actually came from the counts.
      auto const iterations = std::max<std::int64_t>(state.iterations(), 1);
      tsl_publish_detector_metrics(detector, [&](char const * name, double value) {
        auto const ratio = std::string(name).find("coverage") != std::string::npos
          || std::string(name).find("frac") != std::string::npos;
        state.counters[name] = ratio ? value : value / static_cast<double>(iterations);
      });
    }
  });

  if (auto const error = data.verify_index(); !error.empty()) {
    state.SkipWithError(error.c_str());
    return;
  }

  auto const published_iterations = std::max<std::int64_t>(state.iterations(), 1);
  state.counters["materialized_per_row"] = data.rows() == 0
    ? 0.0
    : static_cast<double>(metrics.materialized_elements)
      / static_cast<double>(published_iterations * static_cast<std::int64_t>(data.rows()));
  state.counters["levels"] =
    static_cast<double>(metrics.levels) / static_cast<double>(published_iterations);
  state.counters["ranges_sorted"] =
    static_cast<double>(metrics.ranges_sorted) / static_cast<double>(published_iterations);
  state.counters["tasks"] =
    static_cast<double>(metrics.tasks) / static_cast<double>(published_iterations);
  state.counters["levels_split"] =
    static_cast<double>(metrics.levels_split) / static_cast<double>(published_iterations);
  TslMultiColumnSortMetrics shared{};
  auto const per_iteration = static_cast<std::size_t>(published_iterations);
  shared.rle_values_scanned = metrics.rle_values_scanned / per_iteration;
  shared.direct_equal_bands = metrics.direct_equal_bands / per_iteration;
  shared.direct_equal_band_rows = metrics.direct_equal_band_rows / per_iteration;
  publish(state, data.rows(), data.column_count(), Simd::lane_count_v, sizeof(DataType),
          variant.algorithm_id(), &shared, nullptr);
  if constexpr (FillPercent != 0) {
    state.counters["hybrid_fill_percent"] = static_cast<double>(FillPercent);
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
template <class DataType, TslStyle Style, std::size_t Width>
void run_samplesort_case(
  benchmark::State & state,
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

  tsl_with_detector<DataType>(backend, plan.detector_config, [&](auto & detector) {
    if constexpr (tsl_detector_wants_executor<std::decay_t<decltype(detector)>>::value) {
      state.SkipWithError("asynchronous detectors have no samplesort form");
    } else {
      for (auto _ : state) {
        if (parallel) {
          sorter.sort_index_parallel(data.specs(), data.column_count(), data.index(),
                                     data.rows(), detector, plan.worker_count,
                                     &metrics);
        } else {
          sorter.sort_index(data.specs(), data.column_count(), data.index(),
                            data.rows(), detector, &metrics);
        }
        benchmark::DoNotOptimize(data.index());
        benchmark::ClobberMemory();
      }
      auto const iterations = std::max<std::int64_t>(state.iterations(), 1);
      tsl_publish_detector_metrics(detector, [&](char const * name, double value) {
        auto const ratio = std::string(name).find("coverage") != std::string::npos
          || std::string(name).find("frac") != std::string::npos;
        state.counters[name] = ratio ? value : value / static_cast<double>(iterations);
      });
    }
  });

  if (auto const error = data.verify_index(); !error.empty()) {
    state.SkipWithError(error.c_str());
    return;
  }

  auto const published = std::max<std::int64_t>(state.iterations(), 1);
  state.counters["materialized_per_row"] = data.rows() == 0
    ? 0.0
    : static_cast<double>(metrics.materialized_elements)
      / static_cast<double>(published * static_cast<std::int64_t>(data.rows()));
  state.counters["ranges_sorted"] =
    static_cast<double>(metrics.ranges) / static_cast<double>(published);
  state.counters["deepest_column"] = static_cast<double>(metrics.deepest_column);
  TslMultiColumnSortMetrics shared{};
  shared.rle_values_scanned =
    metrics.detected_elements / static_cast<std::size_t>(published);
  // 200-series ids: the index quicksort uses 100 + its algorithmic id, so the
  // samplesort starts above that and no published id moves.
  publish(state, data.rows(), data.column_count(), Simd::lane_count_v,
          sizeof(DataType), parallel ? 201 : 200, &shared, nullptr);
}

// --- registration -----------------------------------------------------------

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
    return true;
  }

  // Two-way peels one element per level out of an all-equal range, so it is
  // quadratic in the equal-run length. Registered only where that stays bounded.
  // Two-way partitioning is quadratic in the *equal-run length*: a run of r costs
  // about r^2/2, and there are rows/r of them, so the whole column costs rows*r/2.
  // What decides that is the distinct-value count, which every generated spec
  // carries -- `d` for the low-cardinality family, `c` for the uniform and
  // hierarchy ones.
  //
  // This used to test the dataset's *name* instead: only labels beginning
  // "low_cardinality" or "all_equal" were gated. `independent_uniform_c1024` was
  // therefore admitted at every size, and at 524,288 rows over 1024 values its runs
  // are 512 long. One such case ran for eleven and a half hours in the screen stage
  // before it was killed -- a name-based test for a numeric property, and the
  // property was right there in the spec.
  auto two_way_allowed(TslDatasetSpec const & spec, TslSizeLevel const & size) -> bool {
    if (size.per_column_bytes <= plan.two_way_size_cap) {
      return true;   // small enough that even the quadratic case is cheap
    }
    // Families whose duplication is the point of the shape rather than a parameter
    // of it. A heavy-tailed distribution has no cardinality to read -- Zipf carries
    // only its exponent -- but its head is a long equal run by construction, which
    // is precisely what two-way cannot partition. Naming them is right here; naming
    // them *instead of* reading the parameter where one exists was the bug.
    auto const label = tsl_dataset_label(spec);
    for (auto const * family : {"low_cardinality", "all_equal", "skewed_zipf",
                                "heavy_hitter", "duplicates_at_pivot"}) {
      if (label.rfind(family, 0) == 0) {
        return false;
      }
    }
    // The distinct-value count under any of the names the generator uses: `d` for
    // the low-cardinality family, `d1` for the hierarchical and skewed ones, `c`
    // for the uniform and correlated ones.
    auto distinct = spec.param("d", 0.0);
    if (distinct <= 0.0) {
      distinct = spec.param("d1", 0.0);
    }
    if (distinct <= 0.0) {
      distinct = spec.param("c", 0.0);
    }
    if (distinct <= 0.0) {
      return true;   // no cardinality and not a skewed family: treat as unique
    }
    auto const run = static_cast<double>(spec.rows) / distinct;
    return run <= tsl_two_way_run_cap;
  }

  auto footprint_ok(TslDatasetSpec const & spec) -> bool {
    // pristine + reference + the working copy
    auto const bytes = static_cast<std::uint64_t>(3) * spec.columns * spec.rows * spec.element_bytes;
    return bytes <= plan.memory_cap;
  }
};

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
                if (movement == TslMovement::Index) {
                  benchmark::RegisterBenchmark(
                    name,
                    [variant, spec, direction, backend, plan](benchmark::State & state) {
                      run_index_case<DataType, Style, Width, Partition, Leaf,
                                     FillPercent>(
                        state, variant, spec, direction, backend, plan
                      );
                    }
                  )->Unit(benchmark::kNanosecond)->UseRealTime();
                } else {
                  benchmark::RegisterBenchmark(
                    name,
                    [variant, spec, direction, backend, plan](benchmark::State & state) {
                      run_case<DataType, Style, Width, Partition, Leaf, FillPercent>(
                        state, variant, spec, direction, backend, plan
                      );
                    }
                  )->Unit(benchmark::kNanosecond)->UseRealTime();
                }
                ++registrar.registered;
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
            if (!plan.detector_applies(equivalent, backend, spec.columns, level)) {
              registrar.drops.drop(TslDropReason::DetectorInapplicable);
              continue;
            }
            auto const name = case_name(
              "samplesort", type_name, tsl_style_name(Style),
              std::to_string(tsl_simd_for<DataType, Style, Width>::type::lane_count_v),
              spec, direction, size, plan, backend, false, false, TslMovement::Index
            );
            benchmark::RegisterBenchmark(
              name,
              [spec, direction, backend, plan](benchmark::State & state) {
                run_samplesort_case<DataType, Style, Width>(
                  state, spec, direction, backend, plan, false
                );
              }
            )->Unit(benchmark::kNanosecond)->UseRealTime();
            ++registrar.registered;
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
          benchmark::RegisterBenchmark(
            name,
            [spec, direction, plan](benchmark::State & state) {
              run_baseline<DataType>(state, spec, direction, plan);
            }
          )->Unit(benchmark::kNanosecond)->UseRealTime();
          ++registrar.registered;
        }
      }
    }
  }
}

}  // namespace

int main(int argc, char ** argv) try {
  Registrar registrar;
  registrar.plan = load_plan();
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
  for (auto style : {TslStyle::Intrinsics, TslStyle::ClangBuiltin, TslStyle::ClangBoolMask}) {
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

  benchmark::Initialize(&argc, argv);
  if (benchmark::ReportUnrecognizedArguments(argc, argv)) return 1;
  benchmark::RunSpecifiedBenchmarks();
  benchmark::Shutdown();
  return 0;
} catch (std::exception const & error) {
  std::fprintf(stderr, "cosort_bench failed: %s\n", error.what());
  return 1;
}
