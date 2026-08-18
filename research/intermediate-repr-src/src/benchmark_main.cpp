#include "intermediate_repr/kernel_templates.hpp"
#include "intermediate_repr/scenario.hpp"

#include <benchmark/benchmark.h>

#include <algorithm>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <limits>
#include <memory>
#include <mutex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace intermediate_repr {
enum class scaling_mode {
  strong,
  weak,
};

struct run_options {
  matrix_kind matrix{matrix_kind::smoke};
  std::vector<int> workers{1};
  std::vector<scaling_mode> scaling_modes{scaling_mode::strong};
  bool workers_explicit{false};
  bool scaling_explicit{false};
};

namespace {

class shared_dataset_fixture {
public:
  class lease {
  public:
    lease(shared_dataset_fixture &owner, std::shared_ptr<const dataset> data)
        : owner_(&owner), data_(std::move(data)) {}

    ~lease() {
      if (owner_ != nullptr) {
        owner_->release();
      }
    }

    lease(const lease &) = delete;
    lease &operator=(const lease &) = delete;
    lease(lease &&) = delete;
    lease &operator=(lease &&) = delete;

    const dataset &data() const noexcept { return *data_; }

  private:
    shared_dataset_fixture *owner_{};
    std::shared_ptr<const dataset> data_;
  };

  lease acquire(const scenario &value, int workers) {
    std::lock_guard<std::mutex> guard(mutex_);
    if (!data_) {
      data_ = std::make_shared<const dataset>(make_dataset(value));
      active_workers_ = workers;
      released_workers_ = 0;
    } else if (active_workers_ != workers) {
      throw std::logic_error("shared dataset worker-count mismatch");
    }
    return lease(*this, data_);
  }

private:
  void release() noexcept {
    std::lock_guard<std::mutex> guard(mutex_);
    ++released_workers_;
    if (released_workers_ == active_workers_) {
      data_.reset();
      active_workers_ = 0;
      released_workers_ = 0;
    }
  }

  std::mutex mutex_;
  std::shared_ptr<const dataset> data_;
  int active_workers_{};
  int released_workers_{};
};

columns_view view_of(const dataset &data, std::size_t offset,
                     std::size_t rows) {
  return {
      data.a.data() + offset,
      data.b.data() + offset,
      data.c.data() + offset,
      rows,
  };
}

struct row_partition {
  std::size_t offset{};
  std::size_t rows{};
};

row_partition partition_rows(std::size_t total_rows, int workers,
                             int worker_index) {
  const auto worker_count = static_cast<std::size_t>(workers);
  const auto index = static_cast<std::size_t>(worker_index);
  const auto base_rows = total_rows / worker_count;
  const auto remainder = total_rows % worker_count;
  return {
      index * base_rows + std::min(index, remainder),
      base_rows + (index < remainder ? 1 : 0),
  };
}

const char *scaling_name(scaling_mode value) noexcept {
  switch (value) {
  case scaling_mode::strong:
    return "strong";
  case scaling_mode::weak:
    return "weak";
  }
  return "unknown";
}

const char *matrix_name(matrix_kind value) noexcept {
  switch (value) {
  case matrix_kind::smoke:
    return "smoke";
  case matrix_kind::stage1:
    return "stage1";
  case matrix_kind::stage2:
    return "stage2";
  case matrix_kind::pressure:
    return "pressure";
  case matrix_kind::threading:
    return "threading";
  case matrix_kind::confirmation:
    return "confirmation";
  }
  return "unknown";
}

bool has_benchmark_filter(int argc, char **argv) {
  constexpr const char *prefix = "--benchmark_filter=";
  for (int index = 1; index < argc; ++index) {
    if (std::string(argv[index]).rfind(prefix, 0) == 0) {
      return true;
    }
  }
  return false;
}

std::vector<int> parse_worker_counts(const std::string &value) {
  if (value.empty()) {
    throw std::invalid_argument(
        "--irbench_workers requires a comma-separated list");
  }

  std::vector<int> result;
  std::size_t begin = 0;
  while (begin <= value.size()) {
    const auto end = value.find(',', begin);
    const auto token =
        value.substr(begin, end == std::string::npos ? end : end - begin);
    if (token.empty()) {
      throw std::invalid_argument(
          "worker counts must not contain empty entries");
    }
    std::size_t parsed_characters = 0;
    const auto parsed = std::stoul(token, &parsed_characters);
    if (parsed_characters != token.size() || parsed == 0 ||
        parsed > static_cast<unsigned long>(std::numeric_limits<int>::max())) {
      throw std::invalid_argument("worker counts must be positive integers");
    }
    result.push_back(static_cast<int>(parsed));
    if (end == std::string::npos) {
      break;
    }
    begin = end + 1;
  }
  std::sort(result.begin(), result.end());
  result.erase(std::unique(result.begin(), result.end()), result.end());
  return result;
}

std::vector<scaling_mode> parse_scaling_modes(const std::string &value) {
  if (value == "strong") {
    return {scaling_mode::strong};
  }
  if (value == "weak") {
    return {scaling_mode::weak};
  }
  if (value == "both") {
    return {scaling_mode::strong, scaling_mode::weak};
  }
  throw std::invalid_argument(
      "--irbench_scaling must be strong, weak, or both");
}

run_options take_run_options(int &argc, char **argv) {
  run_options selected;
  int output = 1;
  for (int input = 1; input < argc; ++input) {
    const std::string argument(argv[input]);
    constexpr const char *matrix_prefix = "--irbench_matrix=";
    constexpr const char *workers_prefix = "--irbench_workers=";
    constexpr const char *scaling_prefix = "--irbench_scaling=";
    if (argument.rfind(matrix_prefix, 0) == 0) {
      selected.matrix =
          parse_matrix_kind(argument.substr(std::strlen(matrix_prefix)));
      continue;
    }
    if (argument.rfind(workers_prefix, 0) == 0) {
      selected.workers =
          parse_worker_counts(argument.substr(std::strlen(workers_prefix)));
      selected.workers_explicit = true;
      continue;
    }
    if (argument.rfind(scaling_prefix, 0) == 0) {
      selected.scaling_modes =
          parse_scaling_modes(argument.substr(std::strlen(scaling_prefix)));
      selected.scaling_explicit = true;
      continue;
    }
    if (argument == "--irbench_help") {
      std::cout
          << "--irbench_matrix=smoke|stage1|stage2|pressure|threading|"
             "confirmation\n"
          << "--irbench_workers=1,2,4,... (required for threading)\n"
          << "--irbench_scaling=strong|weak|both (threading only)\n"
          << "Stage 2, pressure, threading, and confirmation require an "
             "explicit --benchmark_filter selecting retained scenarios.\n";
      std::exit(0);
    }
    argv[output++] = argv[input];
  }
  argc = output;

  if (selected.matrix == matrix_kind::threading) {
    if (!selected.workers_explicit) {
      throw std::invalid_argument(
          "threading requires explicit --irbench_workers");
    }
    if (!selected.scaling_explicit) {
      selected.scaling_modes = {scaling_mode::strong, scaling_mode::weak};
    }
  } else if (selected.workers_explicit || selected.scaling_explicit) {
    throw std::invalid_argument("worker counts and scaling modes are only "
                                "valid for the threading matrix");
  }
  return selected;
}

bool candidate_enabled(const candidate_descriptor &candidate,
                       matrix_kind matrix) {
  if (matrix != matrix_kind::pressure && candidate.aggregate_count != 1) {
    return false;
  }
  if (matrix != matrix_kind::stage1) {
    return true;
  }
  if (candidate.kind == candidate_kind::autovec_reference ||
      candidate.kind == candidate_kind::scalar_reference) {
    return true;
  }
  return candidate.realization == "hardware";
}

pipeline_result expected_for(columns_view columns, const scenario &source,
                             std::size_t aggregate_count) {
  if (aggregate_count != 1 && aggregate_count != 4 && aggregate_count != 8) {
    throw std::invalid_argument("aggregate count must be 1, 4, or 8");
  }

  pipeline_result result;
  for (std::size_t row = 0; row < columns.rows; ++row) {
    if (columns.a[row] < source.p1) {
      ++result.active_after_a;
      if (columns.b[row] < source.p2) {
        ++result.active_after_b;
        for (std::size_t aggregate = 0; aggregate < aggregate_count;
             ++aggregate) {
          result.sum += aggregate_value(columns.c[row], aggregate);
        }
      }
    }
  }
  return result;
}

bool result_matches(const pipeline_result &actual,
                    const pipeline_result &expected) {
  return actual.valid && actual.sum == expected.sum &&
         actual.active_after_a == expected.active_after_a &&
         actual.active_after_b == expected.active_after_b;
}

std::size_t total_relation_rows(const scenario &source, scaling_mode scaling,
                                int workers) {
  if (scaling == scaling_mode::strong) {
    return source.relation_rows;
  }
  const auto worker_count = static_cast<std::size_t>(workers);
  if (source.relation_rows >
      std::numeric_limits<std::size_t>::max() / worker_count) {
    throw std::overflow_error("weak-scaling relation size overflows size_t");
  }
  return source.relation_rows * worker_count;
}

std::string benchmark_name(const candidate_descriptor &candidate,
                           const scenario &value, scaling_mode scaling) {
  std::string result = "pipeline/profile=" IRBENCH_PROFILE_NAME;
  result += "/realization=";
  result += candidate.realization;
  result += "/vector_bits=" + std::to_string(candidate.vector_bits);
  result += "/mask_policy=";
  result += candidate.mask_policy;
  result += "/representation=";
  result += candidate.representation;
  result += "/aggregates=" + std::to_string(candidate.aggregate_count);
  result += "/scaling=";
  result += scaling_name(scaling);
  result += "/" + value.stable_name();
  return result;
}

void run_benchmark(benchmark::State &state, candidate_descriptor candidate,
                   scenario value, scaling_mode scaling,
                   shared_dataset_fixture &fixture) {
  const auto total_rows = total_relation_rows(value, scaling, state.threads());
  auto dataset_value = value;
  dataset_value.relation_rows = total_rows;
  const auto dataset_lease = fixture.acquire(dataset_value, state.threads());
  const auto partition =
      partition_rows(total_rows, state.threads(), state.thread_index());
  auto local_value = value;
  local_value.relation_rows = partition.rows;
  const auto columns =
      view_of(dataset_lease.data(), partition.offset, partition.rows);

  scratch_buffer scratch(candidate.scratch_bytes(value.batch_rows));
  std::memset(scratch.data(), 0xa5, scratch.size());
  const auto checked = candidate.run(columns, scratch.view(), value.batch_rows,
                                     local_value.p1, local_value.p2);
  const auto expected =
      expected_for(columns, local_value, candidate.aggregate_count);
  if (!result_matches(checked, expected)) {
    state.SkipWithError(
        "candidate failed per-worker correctness before timing");
    return;
  }

  for (auto _ : state) {
    (void)_;
    auto result = candidate.run(columns, scratch.view(), value.batch_rows,
                                local_value.p1, local_value.p2);
    benchmark::DoNotOptimize(result.sum);
    benchmark::DoNotOptimize(result.active_after_a);
    benchmark::DoNotOptimize(result.active_after_b);
    benchmark::ClobberMemory();
  }

  const auto iterations = static_cast<std::int64_t>(state.iterations());
  const auto rows = static_cast<std::int64_t>(local_value.relation_rows);
  state.SetItemsProcessed(iterations * rows);
  state.SetBytesProcessed(iterations * rows *
                          static_cast<std::int64_t>(3 * sizeof(std::int32_t)));
  state.counters["active_after_a"] =
      static_cast<double>(checked.active_after_a);
  state.counters["active_after_b"] =
      static_cast<double>(checked.active_after_b);
  state.counters["intermediate_bytes"] =
      static_cast<double>(checked.intermediate_bytes);
  state.counters["intermediate_bytes_per_row"] = benchmark::Counter(
      local_value.relation_rows == 0
          ? 0.0
          : static_cast<double>(checked.intermediate_bytes) /
                static_cast<double>(local_value.relation_rows),
      benchmark::Counter::kAvgThreads);
  state.counters["intermediate_bytes_per_survivor"] =
      benchmark::Counter(checked.active_after_a == 0
                             ? 0.0
                             : static_cast<double>(checked.intermediate_bytes) /
                                   static_cast<double>(checked.active_after_a),
                         benchmark::Counter::kAvgThreads);
  state.counters["scratch_allocation_bytes"] =
      static_cast<double>(scratch.size());
  state.counters["scratch_allocation_bytes_per_worker"] = benchmark::Counter(
      static_cast<double>(scratch.size()), benchmark::Counter::kAvgThreads);
  state.counters["scratch_capacity_bytes"] =
      static_cast<double>(candidate.scratch_bytes(value.batch_rows));
  state.counters["scratch_capacity_bytes_per_worker"] = benchmark::Counter(
      static_cast<double>(candidate.scratch_bytes(value.batch_rows)),
      benchmark::Counter::kAvgThreads);
  state.counters["realized_sA"] = benchmark::Counter(
      local_value.relation_rows == 0
          ? 0.0
          : static_cast<double>(checked.active_after_a) /
                static_cast<double>(local_value.relation_rows),
      benchmark::Counter::kAvgThreads);
  state.counters["realized_sBgA"] =
      benchmark::Counter(checked.active_after_a == 0
                             ? 0.0
                             : static_cast<double>(checked.active_after_b) /
                                   static_cast<double>(checked.active_after_a),
                         benchmark::Counter::kAvgThreads);
  state.counters["aggregate_count"] =
      benchmark::Counter(static_cast<double>(candidate.aggregate_count),
                         benchmark::Counter::kAvgThreads);
  state.counters["worker_rows"] =
      benchmark::Counter(static_cast<double>(local_value.relation_rows),
                         benchmark::Counter::kAvgThreads);
  state.counters["total_relation_rows"] = benchmark::Counter(
      static_cast<double>(total_rows), benchmark::Counter::kAvgThreads);
  state.counters["workers"] = benchmark::Counter(
      static_cast<double>(state.threads()), benchmark::Counter::kAvgThreads);
}

void add_context(matrix_kind matrix) {
  benchmark::AddCustomContext("irbench_matrix", matrix_name(matrix));
  benchmark::AddCustomContext("irbench_profile", IRBENCH_PROFILE_NAME);
  benchmark::AddCustomContext("irbench_tsl_source", IRBENCH_TSL_SOURCE_ID);
  benchmark::AddCustomContext("irbench_google_benchmark_source",
                              IRBENCH_GBENCH_SOURCE_ID);
  benchmark::AddCustomContext("build_mode", IRBENCH_BUILD_MODE);
  benchmark::AddCustomContext("compiler_id", IRBENCH_CXX_COMPILER_ID);
  benchmark::AddCustomContext("compiler_path", IRBENCH_CXX_COMPILER_PATH);
  benchmark::AddCustomContext("compiler_version", __VERSION__);
  benchmark::AddCustomContext(
      "clang_overlay", IRBENCH_HAS_CLANG_OVERLAY ? "enabled" : "disabled");
  benchmark::AddCustomContext("clang_boolean_mask", IRBENCH_HAS_CLANG_BOOLEAN
                                                        ? "available"
                                                        : "unavailable");
}

void register_benchmarks(matrix_kind matrix, const std::vector<int> &workers,
                         const std::vector<scaling_mode> &scaling_modes) {
  const auto candidates = compiled_candidates();
  const auto scenarios = scenarios_for(matrix);
  for (const auto scaling : scaling_modes) {
    for (const auto &value : scenarios) {
      for (const auto &candidate : candidates) {
        if (!candidate_enabled(candidate, matrix)) {
          continue;
        }
        for (const auto worker_count : workers) {
          const auto name = benchmark_name(candidate, value, scaling);
          auto fixture = std::make_shared<shared_dataset_fixture>();
          auto *registered = benchmark::RegisterBenchmark(
              name.c_str(),
              [candidate, value, scaling, fixture](benchmark::State &state) {
                run_benchmark(state, candidate, value, scaling, *fixture);
              });
          registered->Unit(benchmark::kNanosecond);
          if (matrix == matrix_kind::threading) {
            registered->Threads(worker_count);
            registered->UseRealTime();
          }
        }
      }
    }
  }
}

} // namespace
} // namespace intermediate_repr

int main(int argc, char **argv) {
  using namespace intermediate_repr;
  try {
    const bool filtered = has_benchmark_filter(argc, argv);
    const auto options = take_run_options(argc, argv);
    const auto matrix = options.matrix;
    if ((matrix == matrix_kind::stage2 || matrix == matrix_kind::pressure ||
         matrix == matrix_kind::threading ||
         matrix == matrix_kind::confirmation) &&
        !filtered) {
      throw std::invalid_argument(
          "stage2, pressure, threading, and confirmation require an "
          "explicit --benchmark_filter selecting precommitted scenarios");
    }
    benchmark::Initialize(&argc, argv);
    if (benchmark::ReportUnrecognizedArguments(argc, argv)) {
      return 1;
    }
    add_context(matrix);
    register_benchmarks(matrix, options.workers, options.scaling_modes);
    benchmark::RunSpecifiedBenchmarks();
    benchmark::Shutdown();
    return 0;
  } catch (const std::exception &error) {
    std::cerr << "irbench: " << error.what() << '\n';
    return 2;
  }
}
