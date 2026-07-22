#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <numeric>
#include <random>
#include <string>
#include <type_traits>
#include <vector>

#include <benchmark/benchmark.h>
#include <tsl.hpp>

#include "multicolumn_quicksort.hpp"

namespace {

// ---------------------------------------------------------------------------
// Dimension: sort algorithm (the primary dimension).
//   std_sort      : std::sort of keys (cols==0) / argsort(std::sort)+gather (cols>0)
//   2way+ins/net  : co-sorting quicksort, 2-way partition, insertion / network leaf
//   3way+ins/net  : co-sorting quicksort, 3-way partition, insertion / network leaf
// The network leaf is u32-only.
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Dimension: data distributions.
// ---------------------------------------------------------------------------
enum distribution_kind {
  UNIFORM_RANDOM, ASCENDING, DESCENDING, NEARLY_SORTED, LOW_ENTROPY, ORGAN_PIPE, DISTRIBUTION_COUNT
};

char const * distribution_name(int kind) {
  switch (kind) {
    case UNIFORM_RANDOM: return "uniform_random";
    case ASCENDING: return "ascending";
    case DESCENDING: return "descending";
    case NEARLY_SORTED: return "nearly_sorted";
    case LOW_ENTROPY: return "low_entropy";
    case ORGAN_PIPE: return "organ_pipe";
    default: return "unknown";
  }
}

template <class DataType>
auto make_keys(int kind, std::size_t count, std::uint64_t seed) -> std::vector<DataType> {
  std::vector<DataType> keys(count);
  std::mt19937_64 rng(seed);
  switch (kind) {
    case UNIFORM_RANDOM:
      for (auto & value : keys) value = static_cast<DataType>(rng());
      break;
    case ASCENDING:
      for (std::size_t i = 0; i < count; ++i) keys[i] = static_cast<DataType>(i);
      break;
    case DESCENDING:
      for (std::size_t i = 0; i < count; ++i) keys[i] = static_cast<DataType>(count - i);
      break;
    case NEARLY_SORTED: {
      for (std::size_t i = 0; i < count; ++i) keys[i] = static_cast<DataType>(i);
      auto const swaps = std::max<std::size_t>(1, count / 100);
      std::uniform_int_distribution<std::size_t> pos(0, count - 1);
      for (std::size_t i = 0; i < swaps; ++i) std::swap(keys[pos(rng)], keys[pos(rng)]);
      break;
    }
    case LOW_ENTROPY: {
      std::uniform_int_distribution<std::uint64_t> values(0, 4095);
      for (auto & value : keys) value = static_cast<DataType>(values(rng));
      break;
    }
    case ORGAN_PIPE: {
      auto const mid = (count + 1) / 2;
      for (std::size_t i = 0; i < mid; ++i) keys[i] = static_cast<DataType>(i);
      for (std::size_t i = mid; i < count; ++i) keys[i] = static_cast<DataType>(count - i);
      break;
    }
    default: break;
  }
  return keys;
}

// ---------------------------------------------------------------------------
// Dimension: column sizes anchored to the cache hierarchy.
// ---------------------------------------------------------------------------
struct cache_sizes {
  std::uint64_t l1 = 32 * 1024;
  std::uint64_t l2 = 1024 * 1024;
  std::uint64_t llc = 8 * 1024 * 1024;
};

auto parse_cache_size(std::string const & text) -> std::uint64_t {
  if (text.empty()) return 0;
  auto const value = std::strtoull(text.c_str(), nullptr, 10);
  char const suffix = text.back();
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

auto detect_caches() -> cache_sizes {
  cache_sizes result;
  for (int index = 0; index < 10; ++index) {
    std::string const base = "/sys/devices/system/cpu/cpu0/cache/index" + std::to_string(index);
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

auto make_size_levels(cache_sizes const & caches) -> std::vector<size_level> {
  return {
    {"L1", caches.l1}, {"L2", caches.l2}, {"halfLLC", caches.llc / 2},
    {"LLC", caches.llc}, {"2xLLC", caches.llc * 2}, {"16xLLC", caches.llc * 16},
  };
}

struct run_config {
  std::vector<std::size_t> columns{0, 1, 2, 4};
  std::size_t min_level = 0;
  std::size_t max_level = 5;
  std::uint64_t memory_cap = 64ULL * 1024 * 1024 * 1024;
};

auto env_u64(char const * name, std::uint64_t fallback) -> std::uint64_t {
  char const * value = std::getenv(name);
  return value ? std::strtoull(value, nullptr, 0) : fallback;
}

auto load_config() -> run_config {
  run_config config;
  config.min_level = env_u64("COSORT_MIN_SIZE_LEVEL", config.min_level);
  config.max_level = std::min<std::uint64_t>(env_u64("COSORT_MAX_SIZE_LEVEL", config.max_level), 5);
  config.memory_cap = env_u64("COSORT_MEMORY_CAP_BYTES", config.memory_cap);
  if (char const * cols = std::getenv("COSORT_COLUMNS")) {
    config.columns.clear();
    std::string spec(cols);
    std::size_t start = 0;
    while (start <= spec.size()) {
      auto const comma = spec.find(',', start);
      auto const token = spec.substr(start, comma - start);
      if (!token.empty()) config.columns.push_back(static_cast<std::size_t>(std::strtoull(token.c_str(), nullptr, 10)));
      if (comma == std::string::npos) break;
      start = comma + 1;
    }
  }
  return config;
}

// Shared input construction for a benchmark instance.
template <class DataType>
struct workload {
  std::vector<DataType> pristine_keys;
  std::vector<std::vector<DataType>> pristine_columns;
  std::vector<DataType> work_keys;
  std::vector<std::vector<DataType>> work_columns;
  std::vector<DataType *> pointers;

  workload(int distribution, std::size_t columns, std::size_t count, std::uint64_t seed)
      : pristine_columns(columns, std::vector<DataType>(count)),
        work_keys(count),
        work_columns(columns, std::vector<DataType>(count)),
        pointers(columns) {
    pristine_keys = make_keys<DataType>(distribution, count, seed);
    std::mt19937_64 rng(seed ^ 0xabcdefULL);
    for (auto & column : pristine_columns)
      for (auto & value : column) value = static_cast<DataType>(rng());
    for (std::size_t column = 0; column < columns; ++column) pointers[column] = work_columns[column].data();
  }

  void reset() {
    work_keys = pristine_keys;
    for (std::size_t column = 0; column < work_columns.size(); ++column) work_columns[column] = pristine_columns[column];
  }
};

auto seed_for(int distribution, std::size_t count, std::size_t columns) -> std::uint64_t {
  return 0xC0FFEEULL
    ^ (static_cast<std::uint64_t>(distribution) * 0x9e3779b97f4a7c15ULL)
    ^ (static_cast<std::uint64_t>(count) * 0xbf58476d1ce4e5b9ULL)
    ^ (static_cast<std::uint64_t>(columns) * 0x94d049bb133111ebULL);
}

void tag(benchmark::State & state, std::size_t count, std::size_t columns, std::size_t lanes, std::size_t elem_bytes, int distribution, int algo) {
  state.SetItemsProcessed(static_cast<std::int64_t>(state.iterations()) * static_cast<std::int64_t>(count));
  state.SetBytesProcessed(static_cast<std::int64_t>(state.iterations()) * static_cast<std::int64_t>(count) * elem_bytes * (columns + 1));
  state.counters["count"] = static_cast<double>(count);
  state.counters["cols"] = static_cast<double>(columns);
  state.counters["lanes"] = static_cast<double>(lanes);
  state.counters["elem_bytes"] = static_cast<double>(elem_bytes);
  state.counters["dist"] = static_cast<double>(distribution);
  state.counters["algo"] = static_cast<double>(algo);
}

// ---------------------------------------------------------------------------
// Co-sorting quicksort variants (partition x leaf).
// ---------------------------------------------------------------------------
template <class DataType, std::size_t Lanes, TslPartitionKind PK, TslLeafKind LK>
void bm_cosort(benchmark::State & state, int distribution, std::size_t columns, size_level level, std::uint64_t memory_cap, int algo) {
  auto count = level.per_column_bytes / sizeof(DataType);
  if (count < 2) count = 2;
  std::uint64_t const footprint = static_cast<std::uint64_t>(2) * (columns + 1) * count * sizeof(DataType);
  if (footprint > memory_cap) { state.SkipWithError("footprint exceeds COSORT_MEMORY_CAP_BYTES"); return; }

  auto const seed = seed_for(distribution, count, columns);
  workload<DataType> data(distribution, columns, count, seed);

  using Simd = tsl::dataparallel::simd_for_t<tsl::dataparallel::fixed<Lanes>, DataType>;
  using Sorter = TslMultiColumnQuickSorter<DataType, PK, LK, 16, Simd>;
  Sorter sorter(seed);

  for (auto _ : state) {
    state.PauseTiming();
    data.reset();
    state.ResumeTiming();
    sorter(data.work_keys.data(), data.pointers.data(), columns, count);
    benchmark::DoNotOptimize(data.work_keys.data());
    benchmark::ClobberMemory();
  }
  if (!std::is_sorted(data.work_keys.begin(), data.work_keys.end())) { state.SkipWithError("unsorted keys"); return; }
  tag(state, count, columns, Lanes, sizeof(DataType), distribution, algo);
}

// ---------------------------------------------------------------------------
// std::sort baseline: plain sort (cols==0) or argsort(std::sort)+gather (cols>0).
// ---------------------------------------------------------------------------
template <class DataType>
void bm_std(benchmark::State & state, int distribution, std::size_t columns, size_level level, std::uint64_t memory_cap, int algo) {
  auto count = level.per_column_bytes / sizeof(DataType);
  if (count < 2) count = 2;
  std::uint64_t const footprint = static_cast<std::uint64_t>(2) * (columns + 1) * count * sizeof(DataType) + count * (4 + sizeof(DataType));
  if (footprint > memory_cap) { state.SkipWithError("footprint exceeds COSORT_MEMORY_CAP_BYTES"); return; }

  auto const seed = seed_for(distribution, count, columns);
  workload<DataType> data(distribution, columns, count, seed);
  std::vector<std::uint32_t> index(count);
  std::vector<DataType> gather(count);

  for (auto _ : state) {
    state.PauseTiming();
    data.reset();
    state.ResumeTiming();
    if (columns == 0) {
      std::sort(data.work_keys.begin(), data.work_keys.end());
    } else {
      std::iota(index.begin(), index.end(), 0u);
      auto const & keys = data.work_keys;
      std::sort(index.begin(), index.end(), [&keys](std::uint32_t a, std::uint32_t b) { return keys[a] < keys[b]; });
      for (std::size_t i = 0; i < count; ++i) gather[i] = data.work_keys[index[i]];
      std::copy(gather.begin(), gather.end(), data.work_keys.begin());
      for (std::size_t c = 0; c < columns; ++c) {
        for (std::size_t i = 0; i < count; ++i) gather[i] = data.work_columns[c][index[i]];
        std::copy(gather.begin(), gather.end(), data.work_columns[c].begin());
      }
    }
    benchmark::DoNotOptimize(data.work_keys.data());
    benchmark::ClobberMemory();
  }
  if (!std::is_sorted(data.work_keys.begin(), data.work_keys.end())) { state.SkipWithError("unsorted keys"); return; }
  tag(state, count, columns, 0, sizeof(DataType), distribution, algo);
}

// algorithm identifiers (index used for the "algo" counter)
enum algorithm_kind { STD_SORT, TWOWAY_INS, TWOWAY_NET, THREEWAY_INS, THREEWAY_NET };

std::string bench_name(char const * algo, char const * type_name, std::string const & lanes, int distribution, std::size_t columns, size_level const & size) {
  return std::string("sort/algo=") + algo + "/type=" + type_name + "/lanes=" + lanes
    + "/dist=" + distribution_name(distribution) + "/cols=" + std::to_string(columns) + "/size=" + size.name;
}

template <class DataType, std::size_t Lanes>
void register_lane(char const * type_name, run_config const & config, std::vector<size_level> const & levels) {
  auto const lanes = std::to_string(Lanes);
  for (int distribution = 0; distribution < DISTRIBUTION_COUNT; ++distribution) {
    for (auto const columns : config.columns) {
      for (std::size_t level = config.min_level; level <= config.max_level && level < levels.size(); ++level) {
        auto const size = levels[level];
        auto const cap = config.memory_cap;
        benchmark::RegisterBenchmark(bench_name("2way_ins", type_name, lanes, distribution, columns, size),
          [=](benchmark::State & s) { bm_cosort<DataType, Lanes, TslPartitionKind::TWO_WAY, TslLeafKind::INSERTION>(s, distribution, columns, size, cap, TWOWAY_INS); })
          ->Unit(benchmark::kNanosecond)->UseRealTime();
        benchmark::RegisterBenchmark(bench_name("3way_ins", type_name, lanes, distribution, columns, size),
          [=](benchmark::State & s) { bm_cosort<DataType, Lanes, TslPartitionKind::THREE_WAY, TslLeafKind::INSERTION>(s, distribution, columns, size, cap, THREEWAY_INS); })
          ->Unit(benchmark::kNanosecond)->UseRealTime();
        benchmark::RegisterBenchmark(bench_name("2way_net", type_name, lanes, distribution, columns, size),
          [=](benchmark::State & s) { bm_cosort<DataType, Lanes, TslPartitionKind::TWO_WAY, TslLeafKind::NETWORK>(s, distribution, columns, size, cap, TWOWAY_NET); })
          ->Unit(benchmark::kNanosecond)->UseRealTime();
        benchmark::RegisterBenchmark(bench_name("3way_net", type_name, lanes, distribution, columns, size),
          [=](benchmark::State & s) { bm_cosort<DataType, Lanes, TslPartitionKind::THREE_WAY, TslLeafKind::NETWORK>(s, distribution, columns, size, cap, THREEWAY_NET); })
          ->Unit(benchmark::kNanosecond)->UseRealTime();
      }
    }
  }
}

template <class DataType>
void register_std(char const * type_name, run_config const & config, std::vector<size_level> const & levels) {
  for (int distribution = 0; distribution < DISTRIBUTION_COUNT; ++distribution) {
    for (auto const columns : config.columns) {
      for (std::size_t level = config.min_level; level <= config.max_level && level < levels.size(); ++level) {
        auto const size = levels[level];
        auto const cap = config.memory_cap;
        benchmark::RegisterBenchmark(bench_name("std_sort", type_name, "na", distribution, columns, size),
          [=](benchmark::State & s) { bm_std<DataType>(s, distribution, columns, size, cap, STD_SORT); })
          ->Unit(benchmark::kNanosecond)->UseRealTime();
      }
    }
  }
}

} // namespace

int main(int argc, char ** argv) {
  auto const config = load_config();
  auto const caches = detect_caches();
  auto const levels = make_size_levels(caches);

  std::fprintf(stderr, "caches: L1=%lluKiB L2=%lluKiB LLC=%lluKiB\n",
               (unsigned long long)(caches.l1 / 1024), (unsigned long long)(caches.l2 / 1024), (unsigned long long)(caches.llc / 1024));

  // Dimension: algorithm x data type x data-level parallelism.
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
