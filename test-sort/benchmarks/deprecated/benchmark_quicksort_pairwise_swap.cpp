#include <algorithm>
#include <array>
#include <cctype>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <exception>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <iterator>
#include <limits>
#include <memory>
#include <random>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#if defined(HAVE_HIGHWAY_VQSORT)
#include "hwy/contrib/sort/vqsort.h"
#endif

#include "sorting/quicksort/quicksort_pairwise_swap.hpp"

using BenchmarkDataType = std::uint32_t;
using BenchmarkIndexType = std::size_t;

namespace {

auto constexpr kibibyte = 1024ULL;
auto constexpr mebibyte = kibibyte * kibibyte;
auto constexpr gibibyte = kibibyte * mebibyte;

struct benchmark_config {
  std::string output_path = "quicksort_pairwise_swap_benchmark.tsv";
  std::string trace_output_path;
  std::size_t trials = 7;
  std::uint64_t max_bytes = 64 * mebibyte;
  std::uint64_t seed = 0x123456789abcdef0ULL;
  bool list_sizes = false;
};

struct size_case {
  std::size_t elements;
  std::uint64_t bytes;
  std::string label;
};

struct distribution_case {
  char const * name;
  auto (* make)(std::size_t, std::uint64_t) -> std::vector<BenchmarkDataType>;
};

struct measurement {
  std::uint64_t elapsed_ns;
  std::uint64_t checksum;
};

auto parse_unsigned(char const * text, char const * option_name) -> std::uint64_t {
  std::string value(text);
  std::size_t parsed = 0;
  auto const result = std::stoull(value, &parsed, 0);
  if (parsed != value.size()) {
    throw std::invalid_argument(std::string(option_name) + " expects an unsigned integer");
  }
  return result;
}

auto lower_ascii(std::string text) -> std::string {
  for (auto & character : text) {
    character = static_cast<char>(std::tolower(static_cast<unsigned char>(character)));
  }
  return text;
}

auto parse_bytes(char const * text, char const * option_name) -> std::uint64_t {
  std::string value(text);
  std::size_t parsed = 0;
  auto const number = std::stoull(value, &parsed, 0);
  auto const suffix = lower_ascii(value.substr(parsed));

  std::uint64_t multiplier = 1;
  if (suffix.empty() || suffix == "b") {
    multiplier = 1;
  } else if (suffix == "k" || suffix == "kb" || suffix == "kib") {
    multiplier = kibibyte;
  } else if (suffix == "m" || suffix == "mb" || suffix == "mib") {
    multiplier = mebibyte;
  } else if (suffix == "g" || suffix == "gb" || suffix == "gib") {
    multiplier = gibibyte;
  } else {
    throw std::invalid_argument(std::string(option_name) + " has an unsupported byte suffix: " + suffix);
  }

  if (number > (std::numeric_limits<std::uint64_t>::max() / multiplier)) {
    throw std::overflow_error(std::string(option_name) + " is too large");
  }
  return number * multiplier;
}

auto bytes_from_elements(std::uint64_t elements, char const * option_name) -> std::uint64_t {
  if (elements > (std::numeric_limits<std::uint64_t>::max() / sizeof(BenchmarkDataType))) {
    throw std::overflow_error(std::string(option_name) + " is too large");
  }
  return elements * sizeof(BenchmarkDataType);
}

auto element_count_from_bytes(std::uint64_t bytes) -> std::size_t {
  auto const elements = std::max<std::uint64_t>(1, bytes / sizeof(BenchmarkDataType));
  if (elements > static_cast<std::uint64_t>(std::numeric_limits<std::size_t>::max())) {
    throw std::overflow_error("benchmark size does not fit in std::size_t");
  }
  return static_cast<std::size_t>(elements);
}

auto format_size_label(std::uint64_t bytes) -> std::string {
  if ((bytes % gibibyte) == 0 && bytes >= gibibyte) {
    return std::to_string(bytes / gibibyte) + "GiB";
  }
  if ((bytes % mebibyte) == 0 && bytes >= mebibyte) {
    return std::to_string(bytes / mebibyte) + "MiB";
  }
  if ((bytes % kibibyte) == 0 && bytes >= kibibyte) {
    return std::to_string(bytes / kibibyte) + "KiB";
  }
  return std::to_string(bytes) + "B";
}

void print_usage(char const * program_name) {
  std::cout
    << "Usage: " << program_name << " [output.tsv] [options]\n"
    << "\n"
    << "Options:\n"
    << "  -o, --output PATH   TSV output path (default: quicksort_pairwise_swap_benchmark.tsv)\n"
    << "      --trace-output PATH\n"
    << "                      Optional pairwise-swap trace TSV path; disabled by default\n"
    << "      --trials N      Trials per algorithm/distribution/size (default: 7)\n"
    << "      --max-size N    Largest benchmark size in elements\n"
    << "      --max-bytes N   Largest benchmark footprint, accepts KiB/MiB/GiB suffixes (default: 64MiB)\n"
    << "      --include-low-gb\n"
    << "                      Include built-in sizes through 1GiB\n"
    << "      --list-sizes    Print the selected input sizes and exit\n"
    << "      --seed N        Base input seed (default: 0x123456789abcdef0)\n"
    << "  -h, --help          Show this help text\n";
}

auto parse_args(int argc, char ** argv) -> benchmark_config {
  benchmark_config config;
  bool positional_output_used = false;

  for (int i = 1; i < argc; ++i) {
    std::string arg(argv[i]);
    auto const require_value = [&](char const * option_name) -> char const * {
      if ((i + 1) >= argc) {
        throw std::invalid_argument(std::string(option_name) + " requires a value");
      }
      ++i;
      return argv[i];
    };

    if (arg == "-h" || arg == "--help") {
      print_usage(argv[0]);
      std::exit(0);
    } else if (arg == "-o" || arg == "--output") {
      config.output_path = require_value(arg.c_str());
    } else if (arg == "--trace-output") {
      config.trace_output_path = require_value(arg.c_str());
    } else if (arg == "--trials") {
      config.trials = static_cast<std::size_t>(parse_unsigned(require_value(arg.c_str()), arg.c_str()));
      if (config.trials == 0) {
        throw std::invalid_argument("--trials must be greater than zero");
      }
    } else if (arg == "--max-size") {
      auto const elements = parse_unsigned(require_value(arg.c_str()), arg.c_str());
      if (elements == 0) {
        throw std::invalid_argument("--max-size must be greater than zero");
      }
      config.max_bytes = bytes_from_elements(elements, arg.c_str());
    } else if (arg == "--max-bytes") {
      config.max_bytes = parse_bytes(require_value(arg.c_str()), arg.c_str());
      if (config.max_bytes == 0) {
        throw std::invalid_argument("--max-bytes must be greater than zero");
      }
    } else if (arg == "--include-low-gb") {
      config.max_bytes = std::max<std::uint64_t>(config.max_bytes, gibibyte);
    } else if (arg == "--list-sizes") {
      config.list_sizes = true;
    } else if (arg == "--seed") {
      config.seed = parse_unsigned(require_value(arg.c_str()), arg.c_str());
    } else if (!positional_output_used && !arg.empty() && arg[0] != '-') {
      config.output_path = arg;
      positional_output_used = true;
    } else {
      throw std::invalid_argument("unknown argument: " + arg);
    }
  }

  return config;
}

auto make_sizes(std::uint64_t max_bytes) -> std::vector<size_case> {
  std::vector<size_case> sizes;
  for (auto const bytes : {
         1 * kibibyte,
         4 * kibibyte,
         16 * kibibyte,
         64 * kibibyte,
         256 * kibibyte,
         1 * mebibyte,
         4 * mebibyte,
         16 * mebibyte,
         64 * mebibyte,
         256 * mebibyte,
         1 * gibibyte
       }) {
    if (bytes <= max_bytes) {
      sizes.push_back({element_count_from_bytes(bytes), bytes, format_size_label(bytes)});
    }
  }

  auto const max_elements = element_count_from_bytes(max_bytes);
  auto const rounded_max_bytes = static_cast<std::uint64_t>(max_elements) * sizeof(BenchmarkDataType);
  auto const already_present = std::any_of(sizes.begin(), sizes.end(), [max_elements](size_case const & size) {
    return size.elements == max_elements;
  });
  if (!already_present) {
    sizes.push_back({max_elements, rounded_max_bytes, format_size_label(rounded_max_bytes)});
  }

  std::sort(sizes.begin(), sizes.end(), [](size_case const & lhs, size_case const & rhs) {
    return lhs.elements < rhs.elements;
  });
  sizes.erase(
    std::unique(
      sizes.begin(),
      sizes.end(),
      [](size_case const & lhs, size_case const & rhs) {
        return lhs.elements == rhs.elements;
      }
    ),
    sizes.end()
  );
  return sizes;
}

void print_sizes(std::vector<size_case> const & sizes) {
  std::cout << "size_label\tsize\tbytes\n";
  for (auto const & size : sizes) {
    std::cout << size.label << '\t' << size.elements << '\t' << size.bytes << '\n';
  }
}

auto make_ascending_case(std::size_t count, std::uint64_t) -> std::vector<BenchmarkDataType> {
  std::vector<BenchmarkDataType> data(count);
  for (std::size_t i = 0; i < count; ++i) {
    data[i] = static_cast<BenchmarkDataType>(i);
  }
  return data;
}

auto make_descending_case(std::size_t count, std::uint64_t) -> std::vector<BenchmarkDataType> {
  std::vector<BenchmarkDataType> data(count);
  for (std::size_t i = 0; i < count; ++i) {
    data[i] = static_cast<BenchmarkDataType>(count - i);
  }
  return data;
}

auto make_uniform_random_case(std::size_t count, std::uint64_t seed) -> std::vector<BenchmarkDataType> {
  std::mt19937_64 rng(seed);
  std::vector<BenchmarkDataType> data(count);
  std::generate(data.begin(), data.end(), [&rng]() {
    return static_cast<BenchmarkDataType>(rng());
  });
  return data;
}

auto make_low_entropy_case(std::size_t count, std::uint64_t seed) -> std::vector<BenchmarkDataType> {
  std::mt19937_64 rng(seed);
  std::uniform_int_distribution<BenchmarkDataType> values(0, 4095);
  std::vector<BenchmarkDataType> data(count);
  std::generate(data.begin(), data.end(), [&rng, &values]() {
    return values(rng);
  });
  return data;
}

auto make_nearly_sorted_case(std::size_t count, std::uint64_t seed) -> std::vector<BenchmarkDataType> {
  auto data = make_ascending_case(count, seed);
  if (count < 2) {
    return data;
  }

  std::mt19937_64 rng(seed);
  std::uniform_int_distribution<std::size_t> positions(0, count - 1);
  auto const swaps = std::max<std::size_t>(1, count / 100);
  for (std::size_t i = 0; i < swaps; ++i) {
    std::swap(data[positions(rng)], data[positions(rng)]);
  }
  return data;
}

auto make_organ_pipe_case(std::size_t count, std::uint64_t) -> std::vector<BenchmarkDataType> {
  std::vector<BenchmarkDataType> data(count);
  auto const midpoint = (count + 1) / 2;
  for (std::size_t i = 0; i < midpoint; ++i) {
    data[i] = static_cast<BenchmarkDataType>(i);
  }
  for (std::size_t i = midpoint; i < count; ++i) {
    data[i] = static_cast<BenchmarkDataType>(count - i);
  }
  return data;
}

auto checksum(std::vector<BenchmarkDataType> const & data) -> std::uint64_t {
  std::uint64_t result = 1469598103934665603ULL;
  for (auto const value : data) {
    result ^= value;
    result *= 1099511628211ULL;
  }
  return result;
}

auto measure_std_sort(std::vector<BenchmarkDataType> & data) -> measurement {
  auto const start = std::chrono::steady_clock::now();
  std::sort(data.begin(), data.end());
  auto const stop = std::chrono::steady_clock::now();
  if (!std::is_sorted(data.begin(), data.end())) {
    throw std::runtime_error("std::sort produced unsorted output");
  }

  auto const elapsed = std::chrono::duration_cast<std::chrono::nanoseconds>(stop - start).count();
  return {static_cast<std::uint64_t>(elapsed), checksum(data)};
}

auto measure_pairwise_swap_sort(std::vector<BenchmarkDataType> & data, std::uint64_t sort_seed) -> measurement {
  TslPairWiseSwapQuickSorter<BenchmarkDataType, BenchmarkIndexType> sorter(sort_seed);
  auto const start = std::chrono::steady_clock::now();
  sorter(data.data(), data.size());
  auto const stop = std::chrono::steady_clock::now();
  if (!std::is_sorted(data.begin(), data.end())) {
    throw std::runtime_error("TslPairWiseSwapQuickSorter produced unsorted output");
  }

  auto const elapsed = std::chrono::duration_cast<std::chrono::nanoseconds>(stop - start).count();
  return {static_cast<std::uint64_t>(elapsed), checksum(data)};
}

auto measure_pairwise_swap_sort_with_trace(
  std::vector<BenchmarkDataType> & data,
  std::uint64_t sort_seed,
  TslPairWiseSwapQuickSortTrace & trace
) -> measurement {
  TslPairWiseSwapQuickSorter<BenchmarkDataType, BenchmarkIndexType> sorter(sort_seed);
  auto const start = std::chrono::steady_clock::now();
  sorter.sort_with_trace(data.data(), data.size(), trace);
  auto const stop = std::chrono::steady_clock::now();
  if (!std::is_sorted(data.begin(), data.end())) {
    throw std::runtime_error("TslPairWiseSwapQuickSorter produced unsorted output");
  }

  auto const elapsed = std::chrono::duration_cast<std::chrono::nanoseconds>(stop - start).count();
  return {static_cast<std::uint64_t>(elapsed), checksum(data)};
}

#if defined(HAVE_HIGHWAY_VQSORT)
auto measure_vqsort(std::vector<BenchmarkDataType> & data) -> measurement {
  auto const start = std::chrono::steady_clock::now();
  hwy::VQSort(data.data(), data.size(), hwy::SortAscending{});
  auto const stop = std::chrono::steady_clock::now();
  if (!std::is_sorted(data.begin(), data.end())) {
    throw std::runtime_error("hwy::VQSort produced unsorted output");
  }

  auto const elapsed = std::chrono::duration_cast<std::chrono::nanoseconds>(stop - start).count();
  return {static_cast<std::uint64_t>(elapsed), checksum(data)};
}
#endif

void verify_equal_results(
  std::vector<BenchmarkDataType> const & expected,
  std::vector<BenchmarkDataType> const & actual,
  char const * distribution,
  size_case const & size,
  std::size_t trial
) {
  if (expected.size() != actual.size()) {
    throw std::runtime_error(
      std::string("verification size mismatch for ")
      + distribution
      + " "
      + size.label
      + " trial "
      + std::to_string(trial)
    );
  }

  auto const mismatch = std::mismatch(expected.begin(), expected.end(), actual.begin());
  if (mismatch.first != expected.end()) {
    auto const index = static_cast<std::size_t>(std::distance(expected.begin(), mismatch.first));
    throw std::runtime_error(
      std::string("verification mismatch for ")
      + distribution
      + " "
      + size.label
      + " trial "
      + std::to_string(trial)
      + " at index "
      + std::to_string(index)
      + ": expected "
      + std::to_string(*mismatch.first)
      + " got "
      + std::to_string(*mismatch.second)
    );
  }
}

void write_result(
  std::ofstream & output,
  char const * algorithm,
  char const * distribution,
  size_case const & size,
  std::size_t trial,
  std::uint64_t input_seed,
  std::uint64_t sort_seed,
  measurement const & result
) {
  auto const ns_per_element = static_cast<double>(result.elapsed_ns) / static_cast<double>(size.elements);
  auto const elapsed_seconds = static_cast<double>(result.elapsed_ns) / 1'000'000'000.0;
  auto const mib_per_second =
    result.elapsed_ns == 0
      ? 0.0
      : (static_cast<double>(size.bytes) / static_cast<double>(mebibyte)) / elapsed_seconds;
  output << algorithm << '\t'
         << distribution << '\t'
         << size.elements << '\t'
         << size.bytes << '\t'
         << size.label << '\t'
         << trial << '\t'
         << input_seed << '\t'
         << sort_seed << '\t'
         << result.elapsed_ns << '\t'
         << ns_per_element << '\t'
         << mib_per_second << '\t'
         << result.checksum << '\n';
}

void write_histogram_value(std::ofstream & output, std::array<std::uint64_t, 65> const & histogram) {
  bool wrote_value = false;
  for (std::size_t lane_count = 0; lane_count < histogram.size(); ++lane_count) {
    if (histogram[lane_count] == 0) {
      continue;
    }
    if (wrote_value) {
      output << ';';
    }
    output << lane_count << ':' << histogram[lane_count];
    wrote_value = true;
  }
  if (!wrote_value) {
    output << "empty";
  }
}

void write_partition_trace_header(std::ofstream & output, char const * prefix) {
  output << '\t' << prefix << "_calls"
         << '\t' << prefix << "_input_elements"
         << '\t' << prefix << "_elapsed_ns"
         << '\t' << prefix << "_vectorized_calls"
         << '\t' << prefix << "_vector_iterations"
         << '\t' << prefix << "_left_loads"
         << '\t' << prefix << "_right_loads"
         << '\t' << prefix << "_left_all_good"
         << '\t' << prefix << "_right_all_good"
         << '\t' << prefix << "_swap_iterations"
         << '\t' << prefix << "_swappable_lanes"
         << '\t' << prefix << "_good_left_lanes"
         << '\t' << prefix << "_good_right_lanes"
         << '\t' << prefix << "_carry_left_lanes"
         << '\t' << prefix << "_carry_right_lanes"
         << '\t' << prefix << "_left_progress_elements"
         << '\t' << prefix << "_right_progress_elements"
         << '\t' << prefix << "_scalar_span_elements"
         << '\t' << prefix << "_scalar_left_steps"
         << '\t' << prefix << "_scalar_right_steps"
         << '\t' << prefix << "_scalar_swaps"
         << '\t' << prefix << "_left_bad_lane_histogram"
         << '\t' << prefix << "_right_bad_lane_histogram";
}

void write_trace_header(std::ofstream & output) {
  output << "algorithm\tdistribution\tsize\tbytes\tsize_label\ttrial\tinput_seed\tsort_seed\telapsed_ns\tchecksum"
         << "\tsimd_lanes"
         << "\tsort_calls"
         << "\ttrivial_calls"
         << "\tmax_depth"
         << "\tmax_sort_elements"
         << "\tleaf_sort_calls"
         << "\tleaf_sort_elements"
         << "\tleaf_sort_ns"
         << "\tpivot_calls"
         << "\tpivot_elements"
         << "\tpivot_ns";
  write_partition_trace_header(output, "less");
  write_partition_trace_header(output, "equal");
  output << '\n';
}

void write_partition_trace(std::ofstream & output, TslPairWiseSwapQuickSortPartitionTrace const & trace) {
  output << '\t' << trace.calls
         << '\t' << trace.input_elements
         << '\t' << trace.elapsed_ns
         << '\t' << trace.vectorized_calls
         << '\t' << trace.vector_iterations
         << '\t' << trace.left_loads
         << '\t' << trace.right_loads
         << '\t' << trace.left_all_good
         << '\t' << trace.right_all_good
         << '\t' << trace.swap_iterations
         << '\t' << trace.swappable_lanes
         << '\t' << trace.good_left_lanes
         << '\t' << trace.good_right_lanes
         << '\t' << trace.carry_left_lanes
         << '\t' << trace.carry_right_lanes
         << '\t' << trace.left_progress_elements
         << '\t' << trace.right_progress_elements
         << '\t' << trace.scalar_span_elements
         << '\t' << trace.scalar_left_steps
         << '\t' << trace.scalar_right_steps
         << '\t' << trace.scalar_swaps
         << '\t';
  write_histogram_value(output, trace.left_bad_lane_histogram);
  output << '\t';
  write_histogram_value(output, trace.right_bad_lane_histogram);
}

void write_trace_result(
  std::ofstream & output,
  char const * distribution,
  size_case const & size,
  std::size_t trial,
  std::uint64_t input_seed,
  std::uint64_t sort_seed,
  measurement const & result,
  TslPairWiseSwapQuickSortTrace const & trace
) {
  using DataSimdStyle = tsl::dataparallel::simd_for_t<tsl::dataparallel::native, BenchmarkDataType>;
  output << "tsl_pairwise_swap" << '\t'
         << distribution << '\t'
         << size.elements << '\t'
         << size.bytes << '\t'
         << size.label << '\t'
         << trial << '\t'
         << input_seed << '\t'
         << sort_seed << '\t'
         << result.elapsed_ns << '\t'
         << result.checksum << '\t'
         << DataSimdStyle::lane_count_v << '\t'
         << trace.sort_calls << '\t'
         << trace.trivial_calls << '\t'
         << trace.max_depth << '\t'
         << trace.max_sort_elements << '\t'
         << trace.leaf_sort_calls << '\t'
         << trace.leaf_sort_elements << '\t'
         << trace.leaf_sort_ns << '\t'
         << trace.pivot_calls << '\t'
         << trace.pivot_elements << '\t'
         << trace.pivot_ns;
  write_partition_trace(output, trace.less_than_pivot);
  write_partition_trace(output, trace.equal_to_pivot);
  output << '\n';
}

} // namespace

int main(int argc, char ** argv) {
  try {
    auto const config = parse_args(argc, argv);
    auto const sizes = make_sizes(config.max_bytes);
    if (config.list_sizes) {
      print_sizes(sizes);
      return 0;
    }

    std::ofstream output(config.output_path);
    if (!output) {
      throw std::runtime_error("could not open TSV output: " + config.output_path);
    }
    output << std::setprecision(12);
    output << "algorithm\tdistribution\tsize\tbytes\tsize_label\ttrial\tinput_seed\tsort_seed\telapsed_ns\tns_per_element\tmib_per_second\tchecksum\n";

    std::ofstream trace_output;
    if (!config.trace_output_path.empty()) {
      trace_output.open(config.trace_output_path);
      if (!trace_output) {
        throw std::runtime_error("could not open trace TSV output: " + config.trace_output_path);
      }
      trace_output << std::setprecision(12);
      write_trace_header(trace_output);
    }

    std::vector<distribution_case> const distributions{
      {"uniform_random", make_uniform_random_case},
      {"ascending", make_ascending_case},
      {"descending", make_descending_case},
      {"nearly_sorted", make_nearly_sorted_case},
      {"low_entropy", make_low_entropy_case},
      {"organ_pipe", make_organ_pipe_case}
    };

    std::size_t rows_written = 0;
    for (std::size_t distribution_index = 0; distribution_index < distributions.size(); ++distribution_index) {
      auto const & distribution = distributions[distribution_index];
      for (auto const size : sizes) {
        for (std::size_t trial = 0; trial < config.trials; ++trial) {
          std::cerr << "running\t"
                    << distribution.name << '\t'
                    << size.label << '\t'
                    << "trial " << (trial + 1) << '/' << config.trials
                    << std::endl;
          auto const input_seed =
            config.seed
            ^ (0x9e3779b97f4a7c15ULL * static_cast<std::uint64_t>(trial + 1))
            ^ (0xbf58476d1ce4e5b9ULL * static_cast<std::uint64_t>(distribution_index + 1))
            ^ static_cast<std::uint64_t>(size.elements);
          auto const sort_seed = input_seed ^ 0x94d049bb133111ebULL;
          auto input = distribution.make(size.elements, input_seed);
          auto std_data = input;
#if defined(HAVE_HIGHWAY_VQSORT)
          auto vqsort_data = input;
#endif
          auto pairwise_data = std::move(input);

          auto const std_result = measure_std_sort(std_data);
#if defined(HAVE_HIGHWAY_VQSORT)
          auto const vqsort_result = measure_vqsort(vqsort_data);
#endif
          std::unique_ptr<TslPairWiseSwapQuickSortTrace> pairwise_trace;
          measurement pairwise_result{};
          if (trace_output.is_open()) {
            pairwise_trace = std::make_unique<TslPairWiseSwapQuickSortTrace>();
            pairwise_result = measure_pairwise_swap_sort_with_trace(pairwise_data, sort_seed, *pairwise_trace);
          } else {
            pairwise_result = measure_pairwise_swap_sort(pairwise_data, sort_seed);
          }
#if defined(HAVE_HIGHWAY_VQSORT)
          verify_equal_results(std_data, vqsort_data, distribution.name, size, trial);
#endif
          verify_equal_results(std_data, pairwise_data, distribution.name, size, trial);

          write_result(output, "std_sort", distribution.name, size, trial, input_seed, 0, std_result);
#if defined(HAVE_HIGHWAY_VQSORT)
          write_result(output, "vqsort", distribution.name, size, trial, input_seed, 0, vqsort_result);
#endif
          write_result(output, "tsl_pairwise_swap", distribution.name, size, trial, input_seed, sort_seed, pairwise_result);
          output.flush();
          if (pairwise_trace) {
            write_trace_result(
              trace_output,
              distribution.name,
              size,
              trial,
              input_seed,
              sort_seed,
              pairwise_result,
              *pairwise_trace
            );
            trace_output.flush();
          }
#if defined(HAVE_HIGHWAY_VQSORT)
          rows_written += 3;
#else
          rows_written += 2;
#endif

          std::cerr << "done\t"
                    << distribution.name << '\t'
                    << size.label << '\t'
                    << "trial " << (trial + 1) << '/' << config.trials
                    << "\tstd_sort="
                    << (static_cast<double>(std_result.elapsed_ns) / 1'000'000'000.0)
                    << 's'
#if defined(HAVE_HIGHWAY_VQSORT)
                    << "\tvqsort="
                    << (static_cast<double>(vqsort_result.elapsed_ns) / 1'000'000'000.0)
                    << 's'
#endif
                    << "\ttsl_pairwise_swap="
                    << (static_cast<double>(pairwise_result.elapsed_ns) / 1'000'000'000.0)
                    << 's'
                    << std::endl;
        }
      }
    }

    std::cout << "Wrote " << rows_written << " benchmark rows to " << config.output_path << std::endl;
    if (trace_output.is_open()) {
      std::cout << "Wrote pairwise trace rows to " << config.trace_output_path << std::endl;
    }
    return 0;
  } catch (std::exception const & error) {
    std::cerr << "benchmark failed: " << error.what() << std::endl;
    return 1;
  }
}
