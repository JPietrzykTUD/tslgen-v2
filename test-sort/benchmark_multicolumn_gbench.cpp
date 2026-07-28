/**
 * @file benchmark_multicolumn_gbench.cpp
 * @brief Google Benchmark driver for the lexicographic multi-column co-sort.
 *
 * ## What is being sorted?
 *
 * The input is columnar: `column_count` arrays together represent a table with
 * `count` logical rows. Every column is a sort key. A benchmark configured with
 * three columns therefore computes:
 *
 * ```text
 * ORDER BY column_0 <direction_0>,
 *          column_1 <direction_1>,
 *          column_2 <direction_2>
 * ```
 *
 * Column 0 is sorted over the complete row range. Column 1 is sorted only
 * inside equal-value runs of column 0. Column 2 is sorted only where both
 * preceding columns are equal. Whenever an active key moves, every later
 * column follows the same permutation so logical rows remain intact.
 *
 * ## Algorithms in the benchmark
 *
 * Names encode four independent choices:
 *
 * - `post` versus `incremental`: discover equal runs after a complete active
 *   range is sorted, or discover work from completed three-way quicksort
 *   leaves and pivot-equal bands;
 * - `2way` versus `3way`: quicksort partitioning policy;
 * - `ins` versus `net`: scalar insertion or SIMD bitonic-network leaf;
 * - optional `parallel_`: submit independent next-column ranges to the
 *   project-owned task executor.
 *
 * Registered target names are:
 *
 * ```text
 * post_2way_ins                   post_2way_net
 * post_3way_ins                   post_3way_net
 * incremental_3way_ins            incremental_3way_net
 * parallel_post_2way_ins          parallel_post_2way_net
 * parallel_post_3way_ins          parallel_post_3way_net
 * parallel_incremental_3way_ins   parallel_incremental_3way_net
 * ```
 *
 * Incremental two-way discovery is intentionally absent: a maximal equal run
 * may cross a two-way pivot or leaf boundary, so a correct implementation
 * needs boundary-summary merging. Complete-range post-sort RLE is the
 * two-way reference and parallel implementation.
 *
 * `std_lex_argsort` is the scalar baseline. It sorts row indices with the same
 * complete lexicographic comparator and gathers every column into that order.
 *
 * ## Dimensions and benchmark names
 *
 * A complete name looks like:
 *
 * ```text
 * parallel_incremental_3way_net/u32/lanes=16/dist=low_entropy/
 * order=alternating/cols=3/size=L2/workers=4/threshold=4096/real_time
 * ```
 *
 * The executable registers `u32` at 4/8/16 fixed SIMD lanes and `u64` at
 * 2/4/8 lanes. Size labels are detected from the host cache hierarchy and
 * describe bytes **per column**, not the aggregate table footprint.
 *
 * ## Environment configuration
 *
 * List-valued variables expand the benchmark matrix. For example,
 * `COSORT_COLUMNS=1,2,3,5` registers four separate column-count cases; the
 * numbers are not added together.
 *
 * ```text
 * COSORT_COLUMNS             comma list of total sort-column counts (0..16)
 * COSORT_DISTRIBUTIONS       comma list of distribution IDs (0..7)
 * COSORT_DIRECTIONS          comma list of direction-pattern IDs (0..2)
 * COSORT_MIN_SIZE_LEVEL      first cache-size level (0..5)
 * COSORT_MAX_SIZE_LEVEL      last cache-size level, inclusive (0..5)
 * COSORT_MEMORY_CAP_BYTES    skip cases above this estimated allocation
 * COSORT_WORKERS             worker count for every parallel variant
 * COSORT_TASK_THRESHOLD      queue runs of at least this many rows
 * ```
 *
 * Distribution IDs:
 *
 * ```text
 * 0 uniform random       1 ascending          2 descending
 * 3 nearly sorted        4 low entropy        5 organ pipe
 * 6 all-equal column 0   7 low-entropy prefix, random final column
 * ```
 *
 * Direction IDs:
 *
 * ```text
 * 0 all ascending        1 all descending     2 ASC/DESC alternating
 * ```
 *
 * Size IDs:
 *
 * ```text
 * 0 L1   1 L2   2 half LLC   3 LLC   4 twice LLC   5 sixteen times LLC
 * ```
 *
 * `COSORT_WORKERS` and `COSORT_TASK_THRESHOLD` are scalar per process. Run
 * the executable more than once to compare several worker counts or task
 * thresholds.
 *
 * ## Timing and validation
 *
 * Input generation, allocation, and restoration from pristine columns are
 * outside the timed region. The co-sort call itself is timed. Parallel cases
 * include task-executor construction and destruction for each sort call.
 * The scalar baseline times index initialization, lexicographic index sort,
 * and gathering all columns.
 *
 * Every benchmark uses `UseRealTime()` because parallel variants must be
 * compared using wall time. After the timed iterations, output is checked for
 * lexicographic order. Full row-preservation and structural correctness belong
 * to `test_multicolumn_sort.cpp`, keeping this performance driver lightweight.
 *
 * The target also reports RLE values examined, direct three-way equal bands,
 * submitted/inline tasks, and maximum outstanding tasks. The companion
 * `visualize_multicolumn_bench.py` reads these counters from JSON.
 *
 * ## Typical invocation
 *
 * From the repository root:
 *
 * ```text
 * cmake -S test-sort -B test-sort/build -DCMAKE_BUILD_TYPE=Release \
 *   -DENABLE_GBENCH=ON -DENABLE_VQSORT_BENCHMARK=OFF
 * cmake --build test-sort/build --target benchmark_multicolumn_gbench
 *
 * COSORT_COLUMNS=2,3 COSORT_DISTRIBUTIONS=0,4,6,7 \
 * COSORT_DIRECTIONS=0,1,2 COSORT_MIN_SIZE_LEVEL=0 \
 * COSORT_MAX_SIZE_LEVEL=1 COSORT_WORKERS=4 \
 * COSORT_TASK_THRESHOLD=4096 \
 * test-sort/build/benchmark_multicolumn_gbench \
 *   --benchmark_out=test-sort/build/mc_gbench.json \
 *   --benchmark_out_format=json
 *
 * python -m streamlit run test-sort/visualize_multicolumn_bench.py
 * ```
 *
 * Do not bind the process to one CPU when measuring the parallel variants.
 */

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <numeric>
#include <random>
#include <string>
#include <thread>
#include <vector>

#include <benchmark/benchmark.h>
#include <tsl.hpp>

#include "multicolumn_quicksort.hpp"


namespace {

/// Input-shape IDs accepted by `COSORT_DISTRIBUTIONS`.
enum distribution_kind {
  UNIFORM_RANDOM,     ///< Full-width random values in every column.
  ASCENDING,          ///< Each column begins in ascending physical-row order.
  DESCENDING,         ///< Each column begins in descending physical-row order.
  NEARLY_SORTED,      ///< Ascending data with approximately one percent swaps.
  LOW_ENTROPY,        ///< Every column draws from 4096 distinct values.
  ORGAN_PIPE,         ///< Values increase to the middle, then decrease.
  ALL_EQUAL_PREFIX,   ///< Column 0 is equal; all later columns are random.
  LOW_ENTROPY_PREFIX, ///< Prefix columns draw from 16 values; final is random.
  DISTRIBUTION_COUNT,
};

/// Per-column order patterns accepted by `COSORT_DIRECTIONS`.
enum direction_kind {
  ALL_ASCENDING, ///< Every column sorts ascending.
  ALL_DESCENDING, ///< Every column sorts descending.
  ALTERNATING, ///< Column 0 ASC, column 1 DESC, and so on.
  DIRECTION_COUNT,
};

/// Numeric algorithm IDs exported as the `algo` Google Benchmark counter.
enum algorithm_kind {
  STD_LEX_ARGSORT,
  POST_TWOWAY_INSERTION,
  POST_THREEWAY_INSERTION,
  POST_TWOWAY_NETWORK,
  POST_THREEWAY_NETWORK,
  INCREMENTAL_THREEWAY_INSERTION,
  INCREMENTAL_THREEWAY_NETWORK,
  PARALLEL_POST_TWOWAY_INSERTION,
  PARALLEL_POST_THREEWAY_INSERTION,
  PARALLEL_POST_TWOWAY_NETWORK,
  PARALLEL_POST_THREEWAY_NETWORK,
  PARALLEL_INCREMENTAL_THREEWAY_INSERTION,
  PARALLEL_INCREMENTAL_THREEWAY_NETWORK,
};

auto distribution_name(int kind) -> char const * {
  switch (kind) {
    case UNIFORM_RANDOM: return "uniform";
    case ASCENDING: return "ascending";
    case DESCENDING: return "descending";
    case NEARLY_SORTED: return "nearly_sorted";
    case LOW_ENTROPY: return "low_entropy";
    case ORGAN_PIPE: return "organ_pipe";
    case ALL_EQUAL_PREFIX: return "all_equal_prefix";
    case LOW_ENTROPY_PREFIX: return "low_entropy_prefix";
    default: return "unknown";
  }
}

auto direction_name(int kind) -> char const * {
  switch (kind) {
    case ALL_ASCENDING: return "asc";
    case ALL_DESCENDING: return "desc";
    case ALTERNATING: return "alternating";
    default: return "unknown";
  }
}

/**
 * Expands a direction-pattern ID into immutable order metadata for every
 * column. Alternating order always starts with ascending at column 0.
 */
auto make_orders(std::size_t column_count, int kind) -> std::vector<TslSortOrder> {
  std::vector<TslSortOrder> orders(column_count, TslSortOrder::ASCENDING);
  if (kind == ALL_DESCENDING) {
    std::fill(orders.begin(), orders.end(), TslSortOrder::DESCENDING);
  } else if (kind == ALTERNATING) {
    for (std::size_t column = 0; column < column_count; ++column) {
      orders[column] = column % 2 == 0
        ? TslSortOrder::ASCENDING
        : TslSortOrder::DESCENDING;
    }
  }
  return orders;
}

/**
 * Generates one column for a benchmark workload.
 *
 * Every column receives a deterministic but distinct seed. Prefix-oriented
 * distributions use `column` and `column_count` to decide whether this is a
 * low-entropy prefix key or the high-cardinality final tie-breaker.
 */
template <class DataType>
auto make_column(
  int distribution,
  std::size_t column,
  std::size_t column_count,
  std::size_t count,
  std::uint64_t seed
) -> std::vector<DataType> {
  std::vector<DataType> values(count);
  std::mt19937_64 rng(seed);
  switch (distribution) {
    case UNIFORM_RANDOM:
      for (auto & value : values) value = static_cast<DataType>(rng());
      break;
    case ASCENDING:
      for (std::size_t index = 0; index < count; ++index)
        values[index] = static_cast<DataType>(index + column);
      break;
    case DESCENDING:
      for (std::size_t index = 0; index < count; ++index)
        values[index] = static_cast<DataType>(count - index + column);
      break;
    case NEARLY_SORTED: {
      for (std::size_t index = 0; index < count; ++index)
        values[index] = static_cast<DataType>(index + column);
      auto const swaps = std::max<std::size_t>(1, count / 100);
      std::uniform_int_distribution<std::size_t> position(0, count - 1);
      for (std::size_t index = 0; index < swaps; ++index)
        std::swap(values[position(rng)], values[position(rng)]);
      break;
    }
    case LOW_ENTROPY:
      for (auto & value : values) value = static_cast<DataType>(rng() % 4096);
      break;
    case ORGAN_PIPE: {
      auto const middle = (count + 1) / 2;
      for (std::size_t index = 0; index < middle; ++index)
        values[index] = static_cast<DataType>(index + column);
      for (std::size_t index = middle; index < count; ++index)
        values[index] = static_cast<DataType>(count - index + column);
      break;
    }
    case ALL_EQUAL_PREFIX:
      if (column == 0) {
        std::fill(values.begin(), values.end(), DataType{0});
      } else {
        for (auto & value : values) value = static_cast<DataType>(rng());
      }
      break;
    case LOW_ENTROPY_PREFIX:
      if (column + 1 < column_count) {
        for (auto & value : values) value = static_cast<DataType>(rng() % 16);
      } else {
        for (auto & value : values) value = static_cast<DataType>(rng());
      }
      break;
    default:
      break;
  }
  return values;
}

struct cache_sizes {
  std::uint64_t l1 = 32 * 1024;
  std::uint64_t l2 = 1024 * 1024;
  std::uint64_t llc = 8 * 1024 * 1024;
};

/// Converts Linux sysfs cache sizes such as `48K` or `30M` into bytes.
auto parse_cache_size(std::string const & text) -> std::uint64_t {
  if (text.empty()) return 0;
  auto const value = std::strtoull(text.c_str(), nullptr, 10);
  auto const suffix = text.back();
  if (suffix == 'K' || suffix == 'k') return value * 1024ULL;
  if (suffix == 'M' || suffix == 'm') return value * 1024ULL * 1024ULL;
  if (suffix == 'G' || suffix == 'g') return value * 1024ULL * 1024ULL * 1024ULL;
  return value;
}

auto read_file(std::string const & path) -> std::string {
  std::ifstream stream(path);
  std::string value;
  if (stream) std::getline(stream, value);
  return value;
}

/**
 * Detects the cache hierarchy used to define benchmark sizes.
 *
 * Linux sysfs values replace conservative L1/L2/LLC defaults. Failure to read
 * a cache entry is nonfatal, which keeps the benchmark portable to hosts
 * without `/sys/devices/system/cpu`.
 */
auto detect_caches() -> cache_sizes {
  cache_sizes result;
  for (int index = 0; index < 10; ++index) {
    auto const base = std::string{"/sys/devices/system/cpu/cpu0/cache/index"}
      + std::to_string(index);
    auto const level_text = read_file(base + "/level");
    if (level_text.empty()) continue;
    auto const level = std::strtol(level_text.c_str(), nullptr, 10);
    auto const type = read_file(base + "/type");
    auto const size = parse_cache_size(read_file(base + "/size"));
    if (size == 0) continue;
    if (level == 1 && type == "Data") result.l1 = size;
    else if (level == 2) result.l2 = size;
    else if (level >= 3) result.llc = size;
  }
  return result;
}

struct size_level {
  char const * name;
  std::uint64_t per_column_bytes;
};

/**
 * Maps numeric size levels to bytes per column. `count` is later computed as
 * `per_column_bytes / sizeof(DataType)`, so u32 and u64 cases occupy comparable
 * bytes per column rather than containing the same number of rows.
 */
auto make_size_levels(cache_sizes const & caches) -> std::vector<size_level> {
  return {
    {"L1", caches.l1},
    {"L2", caches.l2},
    {"halfLLC", caches.llc / 2},
    {"LLC", caches.llc},
    {"2xLLC", caches.llc * 2},
    {"16xLLC", caches.llc * 16},
  };
}

/**
 * Benchmark-matrix defaults after environment parsing.
 *
 * The vector fields are independent axes whose Cartesian product is
 * registered. A list such as `{1, 2, 3, 5}` therefore means four benchmark
 * configurations, not eleven columns in one configuration.
 *
 * Worker count and task threshold are intentionally scalar: one process
 * compares every parallel algorithm at one executor configuration.
 */
struct run_config {
  std::vector<std::size_t> columns{1, 2, 3, 5};
  std::vector<int> distributions{
    UNIFORM_RANDOM,
    LOW_ENTROPY,
    ALL_EQUAL_PREFIX,
    LOW_ENTROPY_PREFIX,
  };
  std::vector<int> directions{ALL_ASCENDING, ALTERNATING};
  std::size_t min_level = 0;
  std::size_t max_level = 5;
  std::uint64_t memory_cap = 64ULL * 1024 * 1024 * 1024;
  std::size_t worker_count = std::max(1u, std::thread::hardware_concurrency());
  std::size_t task_threshold = 4096;
};

/// Reads one unsigned scalar variable; `base=0` also accepts `0x...` values.
auto env_u64(char const * name, std::uint64_t fallback) -> std::uint64_t {
  auto const * value = std::getenv(name);
  return value ? std::strtoull(value, nullptr, 0) : fallback;
}

/**
 * Parses a comma-separated benchmark axis.
 *
 * `1,2,3,5` becomes four values `{1, 2, 3, 5}`. It does not describe one
 * combined value. Empty tokens are ignored.
 */
template <class Value>
auto parse_numeric_list(char const * text) -> std::vector<Value> {
  std::vector<Value> result;
  auto const specification = std::string{text};
  std::size_t start = 0;
  while (start <= specification.size()) {
    auto const comma = specification.find(',', start);
    auto const token = specification.substr(start, comma - start);
    if (!token.empty()) {
      result.push_back(static_cast<Value>(std::strtoull(token.c_str(), nullptr, 10)));
    }
    if (comma == std::string::npos) break;
    start = comma + 1;
  }
  return result;
}

/**
 * Loads the benchmark matrix from `COSORT_*` variables.
 *
 * `COSORT_COLUMNS`, `COSORT_DISTRIBUTIONS`, and `COSORT_DIRECTIONS` replace
 * their complete default vectors when present. The remaining variables replace
 * scalar fields. Max size is clamped to the six available levels, worker count
 * to at least one, and the queue threshold to at least two.
 *
 * The lightweight parser assumes documented nonnegative numeric values.
 * Out-of-range distribution/direction IDs are not intended inputs.
 */
auto load_config() -> run_config {
  run_config config;
  config.min_level = env_u64("COSORT_MIN_SIZE_LEVEL", config.min_level);
  config.max_level = std::min<std::uint64_t>(
    env_u64("COSORT_MAX_SIZE_LEVEL", config.max_level),
    5
  );
  config.memory_cap = env_u64("COSORT_MEMORY_CAP_BYTES", config.memory_cap);
  config.worker_count = std::max<std::uint64_t>(
    1,
    env_u64("COSORT_WORKERS", config.worker_count)
  );
  config.task_threshold = std::max<std::uint64_t>(
    2,
    env_u64("COSORT_TASK_THRESHOLD", config.task_threshold)
  );
  if (auto const * value = std::getenv("COSORT_COLUMNS")) {
    config.columns = parse_numeric_list<std::size_t>(value);
  }
  if (auto const * value = std::getenv("COSORT_DISTRIBUTIONS")) {
    config.distributions = parse_numeric_list<int>(value);
  }
  if (auto const * value = std::getenv("COSORT_DIRECTIONS")) {
    config.directions = parse_numeric_list<int>(value);
  }
  return config;
}

/**
 * Owns the deterministic input and mutable columns for one benchmark case.
 *
 * `pristine_columns` is never sorted. `reset()` copies it to `work_columns`
 * while timing is paused and refreshes the raw pointers in `specs` because
 * vector assignment is allowed to change a column's allocation.
 */
template <class DataType>
struct workload {
  std::vector<std::vector<DataType>> pristine_columns;
  std::vector<std::vector<DataType>> work_columns;
  std::vector<TslSortOrder> orders;
  std::vector<TslSortColumn<DataType>> specs;

  workload(
    int distribution,
    int direction,
    std::size_t column_count,
    std::size_t count,
    std::uint64_t seed
  )
      : pristine_columns(column_count),
        work_columns(column_count, std::vector<DataType>(count)),
        orders(make_orders(column_count, direction)),
        specs(column_count) {
    for (std::size_t column = 0; column < column_count; ++column) {
      pristine_columns[column] = make_column<DataType>(
        distribution,
        column,
        column_count,
        count,
        seed ^ (0x9e3779b97f4a7c15ULL * (column + 1))
      );
      specs[column] = {work_columns[column].data(), orders[column]};
    }
  }

  void reset() {
    for (std::size_t column = 0; column < work_columns.size(); ++column) {
      work_columns[column] = pristine_columns[column];
      specs[column].data = work_columns[column].data();
    }
  }
};

/**
 * Complete row comparator used by both the scalar baseline and validation.
 * It advances through columns until it finds the first unequal key, then
 * applies that column's direction.
 */
template <class DataType>
auto row_before(
  std::vector<std::vector<DataType>> const & columns,
  std::vector<TslSortOrder> const & orders,
  std::size_t left,
  std::size_t right
) -> bool {
  for (std::size_t column = 0; column < columns.size(); ++column) {
    auto const left_value = columns[column][left];
    auto const right_value = columns[column][right];
    if (left_value == right_value) continue;
    return orders[column] == TslSortOrder::ASCENDING
      ? left_value < right_value
      : left_value > right_value;
  }
  return false;
}

/// Checks adjacent output rows against the complete lexicographic comparator.
template <class DataType>
auto lexicographically_sorted(
  std::vector<std::vector<DataType>> const & columns,
  std::vector<TslSortOrder> const & orders
) -> bool {
  if (columns.empty() || columns.front().size() < 2) return true;
  for (std::size_t row = 1; row < columns.front().size(); ++row) {
    if (row_before(columns, orders, row, row - 1)) return false;
  }
  return true;
}

/**
 * Produces reproducible input and pivot seeds for one point in the benchmark
 * matrix. Scheduling never contributes to the seed.
 */
auto seed_for(
  int distribution,
  int direction,
  std::size_t count,
  std::size_t columns
) -> std::uint64_t {
  return 0xc0ffeeULL
    ^ (static_cast<std::uint64_t>(distribution) * 0x9e3779b97f4a7c15ULL)
    ^ (static_cast<std::uint64_t>(direction) * 0xd6e8feb86659fd93ULL)
    ^ (static_cast<std::uint64_t>(count) * 0xbf58476d1ce4e5b9ULL)
    ^ (static_cast<std::uint64_t>(columns) * 0x94d049bb133111ebULL);
}

/**
 * Publishes common throughput and diagnostic counters.
 *
 * One "item" is one logical row regardless of column count. Byte throughput
 * counts every sort column once. Algorithm metrics describe the final timed
 * iteration; the input and seed are identical across iterations, so the work
 * decomposition is deterministic for a fixed configuration.
 */
void tag(
  benchmark::State & state,
  std::size_t count,
  std::size_t columns,
  std::size_t lanes,
  std::size_t element_bytes,
  int distribution,
  int direction,
  int algorithm,
  TslMultiColumnSortMetrics const * metrics = nullptr
) {
  state.SetItemsProcessed(
    static_cast<std::int64_t>(state.iterations())
    * static_cast<std::int64_t>(count)
  );
  state.SetBytesProcessed(
    static_cast<std::int64_t>(state.iterations())
    * static_cast<std::int64_t>(count)
    * static_cast<std::int64_t>(columns)
    * static_cast<std::int64_t>(element_bytes)
  );
  state.counters["count"] = static_cast<double>(count);
  state.counters["cols"] = static_cast<double>(columns);
  state.counters["lanes"] = static_cast<double>(lanes);
  state.counters["elem_bytes"] = static_cast<double>(element_bytes);
  state.counters["dist"] = static_cast<double>(distribution);
  state.counters["order"] = static_cast<double>(direction);
  state.counters["algo"] = static_cast<double>(algorithm);
  if (metrics != nullptr && count != 0) {
    state.counters["rle_values_per_row"] =
      static_cast<double>(metrics->rle_values_scanned) / static_cast<double>(count);
    state.counters["direct_equal_bands"] =
      static_cast<double>(metrics->direct_equal_bands);
    state.counters["direct_band_rows"] =
      static_cast<double>(metrics->direct_equal_band_rows);
    state.counters["tasks_submitted"] =
      static_cast<double>(metrics->tasks_submitted);
    state.counters["tasks_inline"] =
      static_cast<double>(metrics->tasks_executed_inline);
    state.counters["max_outstanding"] =
      static_cast<double>(metrics->max_outstanding_tasks);
  }
}

/**
 * Measures one co-sort specialization.
 *
 * Template parameters choose the element type, fixed SIMD width, partition
 * policy, and leaf policy. Runtime arguments choose the remaining benchmark
 * axes and whether run discovery is complete-range or incremental.
 *
 * `worker_count == 0` selects the serial public API. A positive worker count
 * selects the parallel API and makes `task_threshold` the boundary between
 * inline child execution and queue submission.
 *
 * Allocation, data generation, and reset are not timed. The sort call is
 * timed; for a parallel case that includes executor startup and shutdown.
 */
template <
  class DataType,
  std::size_t Lanes,
  TslPartitionKind PartitionKind,
  TslLeafKind LeafKind
>
void bm_cosort(
  benchmark::State & state,
  int distribution,
  int direction,
  std::size_t columns,
  size_level level,
  std::uint64_t memory_cap,
  int algorithm,
  TslRunDiscoveryKind discovery,
  std::size_t worker_count = 0,
  std::size_t task_threshold = 2
) {
  auto count = level.per_column_bytes / sizeof(DataType);
  if (count < 2) count = 2;
  auto const footprint = static_cast<std::uint64_t>(2)
    * columns * count * sizeof(DataType);
  if (footprint > memory_cap) {
    state.SkipWithError("footprint exceeds COSORT_MEMORY_CAP_BYTES");
    return;
  }

  auto const seed = seed_for(distribution, direction, count, columns);
  workload<DataType> data(distribution, direction, columns, count, seed);
  using Simd = tsl::dataparallel::simd_for_t<
    tsl::dataparallel::fixed<Lanes>,
    DataType
  >;
  using Sorter = TslMultiColumnQuickSorter<
    DataType,
    PartitionKind,
    LeafKind,
    16,
    Simd
  >;
  Sorter sorter(seed);
  TslMultiColumnSortMetrics metrics;

  for (auto _ : state) {
    state.PauseTiming();
    data.reset();
    state.ResumeTiming();
    if (worker_count == 0) {
      sorter.sort_columns(
        data.specs.data(),
        data.specs.size(),
        count,
        discovery,
        &metrics
      );
    } else {
      sorter.sort_columns_parallel(
        data.specs.data(),
        data.specs.size(),
        count,
        worker_count,
        task_threshold,
        discovery,
        &metrics
      );
    }
    benchmark::DoNotOptimize(data.work_columns.data());
    benchmark::ClobberMemory();
  }
  if (!lexicographically_sorted(data.work_columns, data.orders)) {
    state.SkipWithError("lexicographically unsorted output");
    return;
  }
  tag(
    state,
    count,
    columns,
    Lanes,
    sizeof(DataType),
    distribution,
    direction,
    algorithm,
    &metrics
  );
}

/**
 * Measures the scalar lexicographic argsort baseline.
 *
 * The timed work initializes row indices, sorts them with `row_before`, and
 * gathers every column through the resulting permutation. This performs the
 * same logical operation as the co-sort variants rather than sorting only the
 * first column.
 */
template <class DataType>
void bm_std(
  benchmark::State & state,
  int distribution,
  int direction,
  std::size_t columns,
  size_level level,
  std::uint64_t memory_cap,
  int algorithm
) {
  auto count = level.per_column_bytes / sizeof(DataType);
  if (count < 2) count = 2;
  auto const footprint = static_cast<std::uint64_t>(2)
    * columns * count * sizeof(DataType)
    + count * (sizeof(std::uint32_t) + sizeof(DataType));
  if (footprint > memory_cap) {
    state.SkipWithError("footprint exceeds COSORT_MEMORY_CAP_BYTES");
    return;
  }

  auto const seed = seed_for(distribution, direction, count, columns);
  workload<DataType> data(distribution, direction, columns, count, seed);
  std::vector<std::uint32_t> indices(count);
  std::vector<DataType> gather(count);

  for (auto _ : state) {
    state.PauseTiming();
    data.reset();
    state.ResumeTiming();
    std::iota(indices.begin(), indices.end(), 0u);
    std::sort(indices.begin(), indices.end(), [&](std::uint32_t left, std::uint32_t right) {
      return row_before(data.work_columns, data.orders, left, right);
    });
    for (std::size_t column = 0; column < columns; ++column) {
      for (std::size_t row = 0; row < count; ++row) {
        gather[row] = data.work_columns[column][indices[row]];
      }
      std::copy(gather.begin(), gather.end(), data.work_columns[column].begin());
    }
    benchmark::DoNotOptimize(data.work_columns.data());
    benchmark::ClobberMemory();
  }
  if (!lexicographically_sorted(data.work_columns, data.orders)) {
    state.SkipWithError("std argsort produced lexicographically unsorted output");
    return;
  }
  tag(
    state,
    count,
    columns,
    0,
    sizeof(DataType),
    distribution,
    direction,
    algorithm
  );
}

/**
 * Builds a self-describing Google Benchmark name. The Streamlit parser treats
 * these path components as dimensions, so spelling is part of the JSON
 * interchange contract.
 */
auto benchmark_name(
  char const * algorithm,
  char const * type_name,
  std::string const & lanes,
  int distribution,
  int direction,
  std::size_t columns,
  size_level const & size,
  std::size_t worker_count = 0,
  std::size_t task_threshold = 0
) -> std::string {
  return std::string{algorithm}
    + "/" + type_name
    + "/lanes=" + lanes
    + "/dist=" + distribution_name(distribution)
    + "/order=" + direction_name(direction)
    + "/cols=" + std::to_string(columns)
    + "/size=" + size.name
    + (worker_count == 0
      ? std::string{}
      : "/workers=" + std::to_string(worker_count)
        + "/threshold=" + std::to_string(task_threshold));
}

/**
 * Registers every target algorithm for one `(DataType, Lanes)` specialization.
 *
 * The nested loops expand distribution × direction × column count × size.
 * Algorithm choices are registered inside that product. `UseRealTime()` is
 * required because CPU time is not meaningful for multi-worker variants.
 *
 * Large all-equal two-way cases are omitted: repeated `0`/`N-1` partitions are
 * expected to be quadratic and would dominate the sweep without yielding a
 * useful performance comparison.
 */
template <class DataType, std::size_t Lanes>
void register_lane(
  char const * type_name,
  run_config const & config,
  std::vector<size_level> const & levels
) {
  auto const lanes = std::to_string(Lanes);
  for (auto const distribution : config.distributions) {
    for (auto const direction : config.directions) {
      for (auto const columns : config.columns) {
        for (
          auto level = config.min_level;
          level <= config.max_level && level < levels.size();
          ++level
        ) {
          auto const size = levels[level];
          auto const cap = config.memory_cap;
          auto register_case = [&](
            char const * name,
            auto function,
            std::size_t workers = 0,
            std::size_t threshold = 0
          ) {
            benchmark::RegisterBenchmark(
              benchmark_name(
                name,
                type_name,
                lanes,
                distribution,
                direction,
                columns,
                size,
                workers,
                threshold
              ),
              function
            )->Unit(benchmark::kNanosecond)->UseRealTime();
          };

          auto const allow_pathological_two_way =
            distribution != ALL_EQUAL_PREFIX
            || size.per_column_bytes <= 256 * 1024;
          if (allow_pathological_two_way) {
            register_case("post_2way_ins", [=](benchmark::State & state) {
              bm_cosort<
                DataType,
                Lanes,
                TslPartitionKind::TWO_WAY,
                TslLeafKind::INSERTION
              >(
                state,
                distribution,
                direction,
                columns,
                size,
                cap,
                POST_TWOWAY_INSERTION,
                TslRunDiscoveryKind::POST_SORT
              );
            });
            register_case("post_2way_net", [=](benchmark::State & state) {
              bm_cosort<
                DataType,
                Lanes,
                TslPartitionKind::TWO_WAY,
                TslLeafKind::NETWORK
              >(
                state,
                distribution,
                direction,
                columns,
                size,
                cap,
                POST_TWOWAY_NETWORK,
                TslRunDiscoveryKind::POST_SORT
              );
            });
            register_case(
              "parallel_post_2way_ins",
              [=](benchmark::State & state) {
                bm_cosort<
                  DataType,
                  Lanes,
                  TslPartitionKind::TWO_WAY,
                  TslLeafKind::INSERTION
                >(
                  state,
                  distribution,
                  direction,
                  columns,
                  size,
                  cap,
                  PARALLEL_POST_TWOWAY_INSERTION,
                  TslRunDiscoveryKind::POST_SORT,
                  config.worker_count,
                  config.task_threshold
                );
              },
              config.worker_count,
              config.task_threshold
            );
            register_case(
              "parallel_post_2way_net",
              [=](benchmark::State & state) {
                bm_cosort<
                  DataType,
                  Lanes,
                  TslPartitionKind::TWO_WAY,
                  TslLeafKind::NETWORK
                >(
                  state,
                  distribution,
                  direction,
                  columns,
                  size,
                  cap,
                  PARALLEL_POST_TWOWAY_NETWORK,
                  TslRunDiscoveryKind::POST_SORT,
                  config.worker_count,
                  config.task_threshold
                );
              },
              config.worker_count,
              config.task_threshold
            );
          }
          register_case("post_3way_ins", [=](benchmark::State & state) {
            bm_cosort<
              DataType,
              Lanes,
              TslPartitionKind::THREE_WAY,
              TslLeafKind::INSERTION
            >(
              state,
              distribution,
              direction,
              columns,
              size,
              cap,
              POST_THREEWAY_INSERTION,
              TslRunDiscoveryKind::POST_SORT
            );
          });
          register_case("post_3way_net", [=](benchmark::State & state) {
            bm_cosort<
              DataType,
              Lanes,
              TslPartitionKind::THREE_WAY,
              TslLeafKind::NETWORK
            >(
              state,
              distribution,
              direction,
              columns,
              size,
              cap,
              POST_THREEWAY_NETWORK,
              TslRunDiscoveryKind::POST_SORT
            );
          });
          register_case("incremental_3way_ins", [=](benchmark::State & state) {
            bm_cosort<
              DataType,
              Lanes,
              TslPartitionKind::THREE_WAY,
              TslLeafKind::INSERTION
            >(
              state,
              distribution,
              direction,
              columns,
              size,
              cap,
              INCREMENTAL_THREEWAY_INSERTION,
              TslRunDiscoveryKind::INCREMENTAL
            );
          });
          register_case("incremental_3way_net", [=](benchmark::State & state) {
            bm_cosort<
              DataType,
              Lanes,
              TslPartitionKind::THREE_WAY,
              TslLeafKind::NETWORK
            >(
              state,
              distribution,
              direction,
              columns,
              size,
              cap,
              INCREMENTAL_THREEWAY_NETWORK,
              TslRunDiscoveryKind::INCREMENTAL
            );
          });
          register_case(
            "parallel_post_3way_ins",
            [=](benchmark::State & state) {
              bm_cosort<
                DataType,
                Lanes,
                TslPartitionKind::THREE_WAY,
                TslLeafKind::INSERTION
              >(
                state,
                distribution,
                direction,
                columns,
                size,
                cap,
                PARALLEL_POST_THREEWAY_INSERTION,
                TslRunDiscoveryKind::POST_SORT,
                config.worker_count,
                config.task_threshold
              );
            },
            config.worker_count,
            config.task_threshold
          );
          register_case(
            "parallel_post_3way_net",
            [=](benchmark::State & state) {
              bm_cosort<
                DataType,
                Lanes,
                TslPartitionKind::THREE_WAY,
                TslLeafKind::NETWORK
              >(
                state,
                distribution,
                direction,
                columns,
                size,
                cap,
                PARALLEL_POST_THREEWAY_NETWORK,
                TslRunDiscoveryKind::POST_SORT,
                config.worker_count,
                config.task_threshold
              );
            },
            config.worker_count,
            config.task_threshold
          );
          register_case(
            "parallel_incremental_3way_ins",
            [=](benchmark::State & state) {
              bm_cosort<
                DataType,
                Lanes,
                TslPartitionKind::THREE_WAY,
                TslLeafKind::INSERTION
              >(
                state,
                distribution,
                direction,
                columns,
                size,
                cap,
                PARALLEL_INCREMENTAL_THREEWAY_INSERTION,
                TslRunDiscoveryKind::INCREMENTAL,
                config.worker_count,
                config.task_threshold
              );
            },
            config.worker_count,
            config.task_threshold
          );
          register_case(
            "parallel_incremental_3way_net",
            [=](benchmark::State & state) {
              bm_cosort<
                DataType,
                Lanes,
                TslPartitionKind::THREE_WAY,
                TslLeafKind::NETWORK
              >(
                state,
                distribution,
                direction,
                columns,
                size,
                cap,
                PARALLEL_INCREMENTAL_THREEWAY_NETWORK,
                TslRunDiscoveryKind::INCREMENTAL,
                config.worker_count,
                config.task_threshold
              );
            },
            config.worker_count,
            config.task_threshold
          );
        }
      }
    }
  }
}

/**
 * Registers the lanes-independent scalar baseline once per data type and for
 * the same distribution, direction, column-count, and size matrix.
 */
template <class DataType>
void register_std(
  char const * type_name,
  run_config const & config,
  std::vector<size_level> const & levels
) {
  for (auto const distribution : config.distributions) {
    for (auto const direction : config.directions) {
      for (auto const columns : config.columns) {
        for (
          auto level = config.min_level;
          level <= config.max_level && level < levels.size();
          ++level
        ) {
          auto const size = levels[level];
          auto const cap = config.memory_cap;
          benchmark::RegisterBenchmark(
            benchmark_name(
              "std_lex_argsort",
              type_name,
              "na",
              distribution,
              direction,
              columns,
              size
            ),
            [=](benchmark::State & state) {
              bm_std<DataType>(
                state,
                distribution,
                direction,
                columns,
                size,
                cap,
                STD_LEX_ARGSORT
              );
            }
          )->Unit(benchmark::kNanosecond)->UseRealTime();
        }
      }
    }
  }
}

}  // namespace

/**
 * Detects configuration and registers the complete benchmark matrix before
 * handing command-line filtering, repetitions, and JSON output to Google
 * Benchmark.
 *
 * The explicit lane registrations are compile-time SIMD specializations, not
 * worker counts. Parallel worker configuration remains the runtime
 * `COSORT_WORKERS` value embedded in each parallel benchmark name.
 */
int main(int argc, char ** argv) {
  auto const config = load_config();
  auto const caches = detect_caches();
  auto const levels = make_size_levels(caches);

  std::fprintf(
    stderr,
    "caches: L1=%lluKiB L2=%lluKiB LLC=%lluKiB\n",
    static_cast<unsigned long long>(caches.l1 / 1024),
    static_cast<unsigned long long>(caches.l2 / 1024),
    static_cast<unsigned long long>(caches.llc / 1024)
  );

  register_std<std::uint32_t>("u32", config, levels);
  register_std<std::uint64_t>("u64", config, levels);
  register_lane<std::uint32_t, 4>("u32", config, levels);
  register_lane<std::uint32_t, 8>("u32", config, levels);
  register_lane<std::uint32_t, 16>("u32", config, levels);
  register_lane<std::uint64_t, 2>("u64", config, levels);
  register_lane<std::uint64_t, 4>("u64", config, levels);
  register_lane<std::uint64_t, 8>("u64", config, levels);

  benchmark::Initialize(&argc, argv);
  benchmark::RunSpecifiedBenchmarks();
  benchmark::Shutdown();
  return 0;
}
