#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

#include <tsl.hpp>

#include "cosort_network.hpp"

using BenchmarkDataType = std::uint32_t;

namespace {

struct config {
  std::size_t network_elements = 8192 * 256;  // total key elements per network pass
  std::size_t partition_pairs = 65536;         // vector pairs per partition pass
  std::size_t max_columns = 6;                  // sweep 0 .. max_columns payload columns
  std::size_t trials = 7;
  std::uint64_t seed = 0x9e3779b97f4a7c15ULL;
};

using Network8 = TslCoSortNetwork<BenchmarkDataType, 8>;
using Network16 = TslCoSortNetwork<BenchmarkDataType, 16>;
using Partition = TslPartitionReplayStep<BenchmarkDataType>;
using PartitionSimdStyle = tsl::dataparallel::simd_for_t<tsl::dataparallel::native, BenchmarkDataType>;

auto constexpr partition_lanes = PartitionSimdStyle::lane_count_v;
auto constexpr max_stack_columns = std::size_t{16};

struct measurement {
  std::uint64_t elapsed_ns;
  std::uint64_t checksum;
};

auto parse_args(int argc, char ** argv) -> config {
  config result;
  for (int arg = 1; arg < argc; ++arg) {
    auto const current = std::string(argv[arg]);
    auto require_value = [&](char const * option) -> char const * {
      if (arg + 1 >= argc) {
        throw std::runtime_error(std::string("missing value for ") + option);
      }
      return argv[++arg];
    };
    if (current == "--elements") {
      result.network_elements = static_cast<std::size_t>(std::stoull(require_value("--elements")));
    } else if (current == "--pairs") {
      result.partition_pairs = static_cast<std::size_t>(std::stoull(require_value("--pairs")));
    } else if (current == "--max-columns") {
      result.max_columns = static_cast<std::size_t>(std::stoull(require_value("--max-columns")));
    } else if (current == "--trials") {
      result.trials = static_cast<std::size_t>(std::stoull(require_value("--trials")));
    } else if (current == "--seed") {
      result.seed = static_cast<std::uint64_t>(std::stoull(require_value("--seed"), nullptr, 0));
    } else if (current == "-h" || current == "--help") {
      std::cout << "Usage: benchmark_cosort_network [--elements N] [--pairs N] [--max-columns N] [--trials N] [--seed N]\n";
      std::exit(0);
    } else {
      throw std::runtime_error("unknown argument: " + current);
    }
  }
  if (result.max_columns > max_stack_columns) {
    throw std::runtime_error("--max-columns exceeds the compiled maximum");
  }
  return result;
}

auto now() -> std::chrono::steady_clock::time_point {
  return std::chrono::steady_clock::now();
}

auto elapsed_ns(std::chrono::steady_clock::time_point start, std::chrono::steady_clock::time_point stop) -> std::uint64_t {
  return static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(stop - start).count());
}

auto fnv1a(std::uint64_t hash, std::uint64_t value) -> std::uint64_t {
  return (hash ^ value) * 1099511628211ULL;
}

// ---------------------------------------------------------------------------
// Correctness: keys sorted per lane column, and every payload column follows.
// ---------------------------------------------------------------------------
template <class Net>
void verify_network(std::uint64_t seed) {
  auto constexpr elements = Net::element_count;
  auto constexpr rows = Net::element_count / Net::lane_count;
  std::size_t const columns = 3;
  std::mt19937_64 rng(seed);
  for (std::size_t sample = 0; sample < 2048; ++sample) {
    std::vector<BenchmarkDataType> keys(elements), pristine(elements);
    for (auto & value : keys) {
      value = static_cast<BenchmarkDataType>(rng());
    }
    pristine = keys;
    // column j holds origin * (j + 1) so every column must undergo one permutation
    std::vector<std::vector<BenchmarkDataType>> pays(columns, std::vector<BenchmarkDataType>(elements));
    for (std::size_t column = 0; column < columns; ++column) {
      for (std::size_t index = 0; index < elements; ++index) {
        pays[column][index] = static_cast<BenchmarkDataType>(index * (column + 1));
      }
    }
    std::vector<BenchmarkDataType *> pay_ptr(columns);
    for (std::size_t column = 0; column < columns; ++column) {
      pay_ptr[column] = pays[column].data();
    }
    Net::run(keys.data(), pay_ptr.data(), columns);

    for (std::size_t lane = 0; lane < Net::lane_count; ++lane) {
      for (std::size_t row = 1; row < rows; ++row) {
        if (keys[row * Net::lane_count + lane] < keys[(row - 1) * Net::lane_count + lane]) {
          throw std::runtime_error("network: lane column is not ascending");
        }
      }
    }
    for (std::size_t position = 0; position < elements; ++position) {
      auto const origin = pays[0][position];  // column 0 == origin index
      if (origin >= elements || pristine[origin] != keys[position]) {
        throw std::runtime_error("network: payload column 0 does not track its key");
      }
      for (std::size_t column = 1; column < columns; ++column) {
        if (pays[column][position] != static_cast<BenchmarkDataType>(origin * (column + 1))) {
          throw std::runtime_error("network: payload column diverged from the key permutation");
        }
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Correctness: payload columns initialised with the keys reproduce the key
// writes bit-for-bit, for every column.
// ---------------------------------------------------------------------------
void verify_partition(std::uint64_t seed) {
  std::size_t const columns = 3;
  std::mt19937_64 rng(seed);
  auto const pivot_vec = tsl::set1<PartitionSimdStyle>(static_cast<BenchmarkDataType>(1u << 31));
  for (std::size_t sample = 0; sample < 100'000; ++sample) {
    alignas(64) std::array<BenchmarkDataType, partition_lanes> left{}, right{};
    for (std::size_t lane = 0; lane < partition_lanes; ++lane) {
      left[lane] = static_cast<BenchmarkDataType>(rng());
      right[lane] = static_cast<BenchmarkDataType>(rng());
    }
    auto const key_l = tsl::load<PartitionSimdStyle, false>(left.data());
    auto const key_r = tsl::load<PartitionSimdStyle, false>(right.data());

    std::array<typename PartitionSimdStyle::register_type, max_stack_columns> pay_l, pay_r, pay_wl, pay_wr;
    for (std::size_t column = 0; column < columns; ++column) {
      pay_l[column] = key_l;
      pay_r[column] = key_r;
    }
    typename PartitionSimdStyle::register_type key_wl, key_wr;
    Partition::step(key_l, key_r, pay_l.data(), pay_r.data(), columns, pivot_vec, key_wl, key_wr, pay_wl.data(), pay_wr.data());

    alignas(64) std::array<BenchmarkDataType, partition_lanes> key_wl_lanes{}, key_wr_lanes{}, pay_lanes{};
    tsl::store<PartitionSimdStyle, false>(key_wl_lanes.data(), key_wl);
    tsl::store<PartitionSimdStyle, false>(key_wr_lanes.data(), key_wr);
    for (std::size_t column = 0; column < columns; ++column) {
      tsl::store<PartitionSimdStyle, false>(pay_lanes.data(), pay_wl[column]);
      if (pay_lanes != key_wl_lanes) {
        throw std::runtime_error("partition: payload left write does not match the key write");
      }
      tsl::store<PartitionSimdStyle, false>(pay_lanes.data(), pay_wr[column]);
      if (pay_lanes != key_wr_lanes) {
        throw std::runtime_error("partition: payload right write does not match the key write");
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Network throughput with `columns` payload columns streamed from memory.
// ---------------------------------------------------------------------------
template <class Net>
auto measure_network(
  std::vector<BenchmarkDataType> const & pristine_keys,
  std::vector<BenchmarkDataType> & work_keys,
  std::vector<std::vector<BenchmarkDataType>> & payloads,
  std::size_t columns
) -> measurement {
  auto constexpr block = Net::element_count;
  auto const blocks = work_keys.size() / block;
  work_keys = pristine_keys;

  std::array<BenchmarkDataType *, max_stack_columns> pay_ptr{};
  auto const start = now();
  for (std::size_t index = 0; index < blocks; ++index) {
    for (std::size_t column = 0; column < columns; ++column) {
      pay_ptr[column] = payloads[column].data() + index * block;
    }
    Net::run(work_keys.data() + index * block, pay_ptr.data(), columns);
  }
  auto const stop = now();

  std::uint64_t checksum = 1469598103934665603ULL;
  for (std::size_t index = 0; index < blocks * block; index += Net::lane_count) {
    checksum = fnv1a(checksum, work_keys[index]);
    for (std::size_t column = 0; column < columns; ++column) {
      checksum = fnv1a(checksum, payloads[column][index]);
    }
  }
  return {elapsed_ns(start, stop), checksum};
}

// ---------------------------------------------------------------------------
// Partition throughput: swap step over `pairs` vector pairs, `columns` payload
// columns streamed from memory.
// ---------------------------------------------------------------------------
struct partition_keys {
  typename PartitionSimdStyle::register_type key_l;
  typename PartitionSimdStyle::register_type key_r;
};

auto measure_partition(
  std::vector<partition_keys> const & keys,
  std::vector<std::vector<BenchmarkDataType>> & payload_l,
  std::vector<std::vector<BenchmarkDataType>> & payload_r,
  std::size_t columns
) -> measurement {
  auto const pivot_vec = tsl::set1<PartitionSimdStyle>(static_cast<BenchmarkDataType>(1u << 31));
  auto accumulator = tsl::set1<PartitionSimdStyle>(0u);
  std::array<typename PartitionSimdStyle::register_type, max_stack_columns> pay_l, pay_r, pay_wl, pay_wr;

  auto const start = now();
  for (std::size_t pair = 0; pair < keys.size(); ++pair) {
    auto const offset = pair * partition_lanes;
    for (std::size_t column = 0; column < columns; ++column) {
      pay_l[column] = tsl::load<PartitionSimdStyle, false>(payload_l[column].data() + offset);
      pay_r[column] = tsl::load<PartitionSimdStyle, false>(payload_r[column].data() + offset);
    }
    typename PartitionSimdStyle::register_type key_wl, key_wr;
    Partition::step(keys[pair].key_l, keys[pair].key_r, pay_l.data(), pay_r.data(), columns, pivot_vec, key_wl, key_wr, pay_wl.data(), pay_wr.data());
    accumulator = tsl::binary_xor<PartitionSimdStyle>(accumulator, key_wl);
    accumulator = tsl::binary_xor<PartitionSimdStyle>(accumulator, key_wr);
    for (std::size_t column = 0; column < columns; ++column) {
      tsl::store<PartitionSimdStyle, false>(payload_l[column].data() + offset, pay_wl[column]);
      tsl::store<PartitionSimdStyle, false>(payload_r[column].data() + offset, pay_wr[column]);
      accumulator = tsl::binary_xor<PartitionSimdStyle>(accumulator, pay_wl[column]);
      accumulator = tsl::binary_xor<PartitionSimdStyle>(accumulator, pay_wr[column]);
    }
  }
  auto const stop = now();

  alignas(64) std::array<BenchmarkDataType, partition_lanes> lanes{};
  tsl::store<PartitionSimdStyle, false>(lanes.data(), accumulator);
  std::uint64_t checksum = 1469598103934665603ULL;
  for (auto const value : lanes) {
    checksum = fnv1a(checksum, value);
  }
  return {elapsed_ns(start, stop), checksum};
}

auto median(std::vector<double> values) -> double {
  std::sort(values.begin(), values.end());
  return values[values.size() / 2];
}

} // namespace

int main(int argc, char ** argv) {
  try {
    auto const cfg = parse_args(argc, argv);

    std::cerr << "verifying network co-sort ..." << std::endl;
    verify_network<Network8>(cfg.seed);
    verify_network<Network16>(cfg.seed ^ 0x1111ULL);
    std::cerr << "verifying partition replay ..." << std::endl;
    verify_partition(cfg.seed ^ 0xbf58476d1ce4e5b9ULL);
    std::cerr << "verification passed" << std::endl;

    std::mt19937_64 rng(cfg.seed ^ 0x94d049bb133111ebULL);

    // network buffers
    std::vector<BenchmarkDataType> pristine_keys(cfg.network_elements), work_keys(cfg.network_elements);
    for (auto & value : pristine_keys) {
      value = static_cast<BenchmarkDataType>(rng());
    }
    std::vector<std::vector<BenchmarkDataType>> net_payloads(cfg.max_columns, std::vector<BenchmarkDataType>(cfg.network_elements));
    for (auto & column : net_payloads) {
      for (auto & value : column) {
        value = static_cast<BenchmarkDataType>(rng());
      }
    }

    // partition buffers
    std::vector<partition_keys> part_keys(cfg.partition_pairs);
    {
      alignas(64) std::array<BenchmarkDataType, partition_lanes> left{}, right{};
      for (auto & entry : part_keys) {
        for (std::size_t lane = 0; lane < partition_lanes; ++lane) {
          left[lane] = static_cast<BenchmarkDataType>(rng());
          right[lane] = static_cast<BenchmarkDataType>(rng());
        }
        entry.key_l = tsl::load<PartitionSimdStyle, false>(left.data());
        entry.key_r = tsl::load<PartitionSimdStyle, false>(right.data());
      }
    }
    auto const partition_span = cfg.partition_pairs * partition_lanes;
    std::vector<std::vector<BenchmarkDataType>> part_pay_l(cfg.max_columns, std::vector<BenchmarkDataType>(partition_span));
    std::vector<std::vector<BenchmarkDataType>> part_pay_r(cfg.max_columns, std::vector<BenchmarkDataType>(partition_span));
    for (std::size_t column = 0; column < cfg.max_columns; ++column) {
      for (std::size_t index = 0; index < partition_span; ++index) {
        part_pay_l[column][index] = static_cast<BenchmarkDataType>(rng());
        part_pay_r[column][index] = static_cast<BenchmarkDataType>(rng());
      }
    }

    std::uint64_t sink = 0;
    auto keep = [&sink](measurement const & m) { sink ^= m.checksum; return static_cast<double>(m.elapsed_ns); };

    auto const net_elems = static_cast<double>(cfg.network_elements);
    auto const part_elems = static_cast<double>(cfg.partition_pairs * 2 * partition_lanes);

    std::cout << std::fixed << std::setprecision(3);
    std::cout << "kernel\tcolumns\tns_per_key_element\toverhead_vs_0\tmarginal_per_column\n";

    auto sweep = [&](char const * name, auto measure_one, double elems) {
      std::vector<double> base_samples;
      double base = 0.0;
      for (std::size_t columns = 0; columns <= cfg.max_columns; ++columns) {
        std::vector<double> samples;
        for (std::size_t trial = 0; trial < cfg.trials; ++trial) {
          samples.push_back(keep(measure_one(columns)));
        }
        auto const ns = median(samples);
        if (columns == 0) {
          base = ns;
        }
        auto const per_element = ns / elems;
        auto const overhead = base > 0 ? ns / base : 0.0;
        auto const marginal = columns > 0 ? (ns - base) / static_cast<double>(columns) / elems : 0.0;
        std::cout << name << '\t' << columns << '\t' << per_element << '\t' << overhead << "x\t" << marginal << '\n';
      }
    };

    sweep("network_8reg", [&](std::size_t columns) { return measure_network<Network8>(pristine_keys, work_keys, net_payloads, columns); }, net_elems);
    sweep("network_16reg", [&](std::size_t columns) { return measure_network<Network16>(pristine_keys, work_keys, net_payloads, columns); }, net_elems);
    sweep("partition", [&](std::size_t columns) { return measure_partition(part_keys, part_pay_l, part_pay_r, columns); }, part_elems);

    std::cerr << "checksum sink=" << sink << std::endl;
    return 0;
  } catch (std::exception const & error) {
    std::cerr << "benchmark failed: " << error.what() << std::endl;
    return 1;
  }
}
