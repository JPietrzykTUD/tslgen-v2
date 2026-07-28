#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

#include <tsl.hpp>

#include "multicolumn_quicksort.hpp"

// Legacy active-key microbenchmark: `column_count` is the number of passive
// payload columns. benchmark_multicolumn_gbench.cpp owns the true
// lexicographic multi-column comparison.

using DataType = std::uint32_t;

namespace {

auto constexpr kibibyte = std::size_t{1024};
auto constexpr mebibyte = kibibyte * kibibyte;

struct config {
  std::vector<std::size_t> column_counts{0, 1, 2, 4};
  std::size_t max_bytes = 4 * mebibyte;
  std::size_t trials = 5;
  std::uint64_t seed = 0x123456789abcdef0ULL;
};

using column_vectors = std::vector<std::vector<DataType>>;

auto now() -> std::chrono::steady_clock::time_point {
  return std::chrono::steady_clock::now();
}

auto elapsed_ns(std::chrono::steady_clock::time_point start, std::chrono::steady_clock::time_point stop) -> std::uint64_t {
  return static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(stop - start).count());
}

auto label_for(std::size_t bytes) -> std::string {
  if (bytes >= mebibyte && bytes % mebibyte == 0) {
    return std::to_string(bytes / mebibyte) + "MiB";
  }
  return std::to_string(bytes / kibibyte) + "KiB";
}

auto make_keys(std::size_t count, std::uint64_t seed) -> std::vector<DataType> {
  std::mt19937_64 rng(seed);
  std::vector<DataType> keys(count);
  for (auto & value : keys) {
    value = static_cast<DataType>(rng());
  }
  return keys;
}

auto make_low_entropy_keys(std::size_t count, std::uint64_t seed) -> std::vector<DataType> {
  std::mt19937_64 rng(seed);
  std::uniform_int_distribution<DataType> values(0, 4095);
  std::vector<DataType> keys(count);
  for (auto & value : keys) {
    value = values(rng);
  }
  return keys;
}

auto make_columns(std::size_t count, std::size_t column_count, std::uint64_t seed) -> column_vectors {
  std::mt19937_64 rng(seed);
  column_vectors columns(column_count, std::vector<DataType>(count));
  for (auto & column : columns) {
    for (auto & value : column) {
      value = static_cast<DataType>(rng());
    }
  }
  return columns;
}

auto column_pointers(column_vectors & columns) -> std::vector<DataType *> {
  std::vector<DataType *> pointers(columns.size());
  for (std::size_t index = 0; index < columns.size(); ++index) {
    pointers[index] = columns[index].data();
  }
  return pointers;
}

// Correctness: keys sorted and every payload column follows one permutation.
// Column 0 tracks the origin index; column j holds origin*(j+1)+j.
template <class Sorter>
void verify_cosort(std::vector<DataType> keys, std::size_t column_count, std::uint64_t seed) {
  auto const count = keys.size();
  auto const original_keys = keys;
  column_vectors columns(std::max<std::size_t>(column_count, 1), std::vector<DataType>(count));
  for (std::size_t index = 0; index < count; ++index) {
    for (std::size_t column = 0; column < columns.size(); ++column) {
      columns[column][index] = static_cast<DataType>(index * (column + 1) + column);
    }
  }
  auto pointers = column_pointers(columns);
  Sorter sorter(seed ^ 0xa5a5a5a5ULL);
  sorter(keys.data(), pointers.data(), columns.size(), count);

  if (!std::is_sorted(keys.begin(), keys.end())) {
    throw std::runtime_error("cosort: keys are not sorted");
  }
  std::vector<char> seen(count, 0);
  for (std::size_t position = 0; position < count; ++position) {
    auto const origin = columns[0][position];
    if (origin >= count || seen[origin]) {
      throw std::runtime_error("cosort: column 0 is not a permutation of input positions");
    }
    seen[origin] = 1;
    if (original_keys[origin] != keys[position]) {
      throw std::runtime_error("cosort: key does not match its tracked origin");
    }
    for (std::size_t column = 1; column < columns.size(); ++column) {
      if (columns[column][position] != static_cast<DataType>(origin * (column + 1) + column)) {
        throw std::runtime_error("cosort: payload column diverged from the key permutation");
      }
    }
  }
}

template <class Sorter>
auto run_cosort(
  std::vector<DataType> const & pristine_keys,
  column_vectors const & pristine_columns,
  std::vector<DataType> & work_keys,
  column_vectors & work_columns,
  std::size_t column_count,
  std::uint64_t seed
) -> std::uint64_t {
  work_keys = pristine_keys;
  for (std::size_t column = 0; column < column_count; ++column) {
    work_columns[column] = pristine_columns[column];
  }
  auto pointers = column_pointers(work_columns);
  Sorter sorter(seed);

  auto const start = now();
  sorter(work_keys.data(), pointers.data(), column_count, work_keys.size());
  auto const stop = now();
  if (!std::is_sorted(work_keys.begin(), work_keys.end())) {
    throw std::runtime_error("cosort produced unsorted keys");
  }
  return elapsed_ns(start, stop);
}

// Baseline: argsort the keys (std::sort on an index array) then gather every
// column by the resulting permutation.
auto run_argsort_gather(
  std::vector<DataType> const & pristine_keys,
  column_vectors const & pristine_columns,
  std::vector<DataType> & work_keys,
  column_vectors & work_columns,
  std::vector<std::uint32_t> & index,
  std::vector<DataType> & gather_buffer,
  std::size_t column_count
) -> std::uint64_t {
  auto const count = pristine_keys.size();
  work_keys = pristine_keys;
  for (std::size_t column = 0; column < column_count; ++column) {
    work_columns[column] = pristine_columns[column];
  }

  auto const start = now();
  std::iota(index.begin(), index.end(), 0u);
  std::sort(index.begin(), index.end(), [&](std::uint32_t a, std::uint32_t b) {
    return work_keys[a] < work_keys[b];
  });
  for (std::size_t position = 0; position < count; ++position) {
    gather_buffer[position] = work_keys[index[position]];
  }
  std::copy(gather_buffer.begin(), gather_buffer.end(), work_keys.begin());
  for (std::size_t column = 0; column < column_count; ++column) {
    for (std::size_t position = 0; position < count; ++position) {
      gather_buffer[position] = work_columns[column][index[position]];
    }
    std::copy(gather_buffer.begin(), gather_buffer.end(), work_columns[column].begin());
  }
  auto const stop = now();
  if (!std::is_sorted(work_keys.begin(), work_keys.end())) {
    throw std::runtime_error("argsort_gather produced unsorted keys");
  }
  return elapsed_ns(start, stop);
}

auto median(std::vector<std::uint64_t> values) -> double {
  std::sort(values.begin(), values.end());
  return static_cast<double>(values[values.size() / 2]);
}

template <class Sorter>
auto measure_variant(
  std::vector<DataType> const & pristine_keys,
  column_vectors const & pristine_columns,
  std::vector<DataType> & work_keys,
  column_vectors & work_columns,
  std::size_t column_count,
  std::size_t trials,
  std::uint64_t seed
) -> double {
  std::vector<std::uint64_t> samples;
  for (std::size_t trial = 0; trial < trials; ++trial) {
    samples.push_back(run_cosort<Sorter>(pristine_keys, pristine_columns, work_keys, work_columns, column_count, seed ^ (trial + 1)));
  }
  return median(samples);
}

using TwoWayInsertion = TslMultiColumnQuickSorter<DataType, TslPartitionKind::TWO_WAY, TslLeafKind::INSERTION>;
using TwoWayNetwork = TslMultiColumnQuickSorter<DataType, TslPartitionKind::TWO_WAY, TslLeafKind::NETWORK>;
using ThreeWayInsertion = TslMultiColumnQuickSorter<DataType, TslPartitionKind::THREE_WAY, TslLeafKind::INSERTION>;
using ThreeWayNetwork = TslMultiColumnQuickSorter<DataType, TslPartitionKind::THREE_WAY, TslLeafKind::NETWORK>;

} // namespace

int main(int argc, char ** argv) {
  try {
    config cfg;
    for (int arg = 1; arg < argc; ++arg) {
      auto const current = std::string(argv[arg]);
      auto require_value = [&]() -> char const * {
        if (arg + 1 >= argc) throw std::runtime_error("missing value for " + current);
        return argv[++arg];
      };
      if (current == "--max-bytes") {
        cfg.max_bytes = static_cast<std::size_t>(std::stoull(require_value())) * mebibyte;
      } else if (current == "--trials") {
        cfg.trials = static_cast<std::size_t>(std::stoull(require_value()));
      } else if (current == "--seed") {
        cfg.seed = static_cast<std::uint64_t>(std::stoull(require_value(), nullptr, 0));
      } else {
        throw std::runtime_error("unknown argument: " + current);
      }
    }

    std::vector<std::size_t> byte_sizes;
    for (auto const bytes : {256 * kibibyte, 1 * mebibyte, 4 * mebibyte, 16 * mebibyte}) {
      if (bytes <= cfg.max_bytes) {
        byte_sizes.push_back(bytes);
      }
    }

    auto const max_columns = *std::max_element(cfg.column_counts.begin(), cfg.column_counts.end());

    struct distribution {
      char const * name;
      std::vector<DataType> (*generate)(std::size_t, std::uint64_t);
    };
    std::array<distribution, 2> const distributions{{
      {"uniform", make_keys},
      {"low_entropy", make_low_entropy_keys}
    }};

    std::cerr << "verifying variants ..." << std::endl;
    for (auto const & dist : distributions) {
      for (auto const columns : cfg.column_counts) {
        for (auto const n : {std::size_t{4096}, std::size_t{200000}}) {
          verify_cosort<TwoWayInsertion>(dist.generate(n, cfg.seed), columns, cfg.seed);
          verify_cosort<TwoWayNetwork>(dist.generate(n, cfg.seed), columns, cfg.seed ^ 1);
          verify_cosort<ThreeWayInsertion>(dist.generate(n, cfg.seed), columns, cfg.seed ^ 2);
          verify_cosort<ThreeWayNetwork>(dist.generate(n, cfg.seed), columns, cfg.seed ^ 3);
        }
      }
    }
    std::cerr << "verification passed" << std::endl;

    std::cout << std::fixed << std::setprecision(3);
    std::cout << "method\tdistribution\tcolumns\tsize_label\telements\tns_per_key_element\tspeedup_vs_argsort\n";

    for (auto const bytes : byte_sizes) {
      auto const count = bytes / sizeof(DataType);
      for (auto const & dist : distributions) {
        auto const pristine_keys = dist.generate(count, cfg.seed ^ count);
        auto const pristine_columns = make_columns(count, max_columns, cfg.seed ^ (count * 3));

        std::vector<DataType> work_keys(count);
        column_vectors work_columns(max_columns, std::vector<DataType>(count));
        std::vector<std::uint32_t> index(count);
        std::vector<DataType> gather_buffer(count);

        for (auto const columns : cfg.column_counts) {
          std::vector<std::uint64_t> argsort_samples;
          for (std::size_t trial = 0; trial < cfg.trials; ++trial) {
            argsort_samples.push_back(run_argsort_gather(pristine_keys, pristine_columns, work_keys, work_columns, index, gather_buffer, columns));
          }
          auto const argsort_med = median(argsort_samples);
          auto const elems = static_cast<double>(count);

          auto emit = [&](char const * name, double ns) {
            std::cout << name << '\t' << dist.name << '\t' << columns << '\t' << label_for(bytes) << '\t' << count << '\t'
                      << (ns / elems) << '\t' << (argsort_med / ns) << "x\n";
          };
          emit("argsort_gather", argsort_med);
          emit("twoway_insertion", measure_variant<TwoWayInsertion>(pristine_keys, pristine_columns, work_keys, work_columns, columns, cfg.trials, cfg.seed ^ 11));
          emit("twoway_network", measure_variant<TwoWayNetwork>(pristine_keys, pristine_columns, work_keys, work_columns, columns, cfg.trials, cfg.seed ^ 22));
          emit("threeway_insertion", measure_variant<ThreeWayInsertion>(pristine_keys, pristine_columns, work_keys, work_columns, columns, cfg.trials, cfg.seed ^ 33));
          emit("threeway_network", measure_variant<ThreeWayNetwork>(pristine_keys, pristine_columns, work_keys, work_columns, columns, cfg.trials, cfg.seed ^ 44));
        }
      }
    }
    return 0;
  } catch (std::exception const & error) {
    std::cerr << "benchmark failed: " << error.what() << std::endl;
    return 1;
  }
}
