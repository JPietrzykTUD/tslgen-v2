#include "intermediate_repr/kernel_api.hpp"
#include "intermediate_repr/scenario.hpp"

#include <algorithm>
#include <numeric>
#include <sstream>
#include <stdexcept>

namespace intermediate_repr {
namespace {

class splitmix64 {
public:
  explicit splitmix64(std::uint64_t seed) : state_(seed) {}

  std::uint64_t next() noexcept {
    std::uint64_t value = (state_ += 0x9e3779b97f4a7c15ULL);
    value = (value ^ (value >> 30U)) * 0xbf58476d1ce4e5b9ULL;
    value = (value ^ (value >> 27U)) * 0x94d049bb133111ebULL;
    return value ^ (value >> 31U);
  }

private:
  std::uint64_t state_;
};

std::size_t rounded_count(std::size_t total, std::uint32_t basis_points) {
  return static_cast<std::size_t>(
      (static_cast<std::uint64_t>(total) * basis_points + 5000ULL) / 10000ULL);
}

template <class T> void shuffle(std::vector<T> &values, splitmix64 &random) {
  for (std::size_t i = values.size(); i > 1; --i) {
    const auto other = static_cast<std::size_t>(random.next() % i);
    std::swap(values[i - 1], values[other]);
  }
}

std::vector<std::size_t> make_order(std::size_t rows,
                                    distribution match_distribution,
                                    splitmix64 &random) {
  std::vector<std::size_t> order;
  order.reserve(rows);

  if (match_distribution == distribution::alternating) {
    for (std::size_t row = 0; row < rows; row += 2) {
      order.push_back(row);
    }
    for (std::size_t row = 1; row < rows; row += 2) {
      order.push_back(row);
    }
    return order;
  }

  if (match_distribution == distribution::clustered) {
    constexpr std::size_t block_rows = 64;
    const auto block_count = (rows + block_rows - 1) / block_rows;
    std::vector<std::size_t> blocks(block_count);
    std::iota(blocks.begin(), blocks.end(), std::size_t{0});
    shuffle(blocks, random);
    for (const auto block : blocks) {
      const auto begin = block * block_rows;
      const auto end = std::min(rows, begin + block_rows);
      for (std::size_t row = begin; row < end; ++row) {
        order.push_back(row);
      }
    }
    return order;
  }

  order.resize(rows);
  std::iota(order.begin(), order.end(), std::size_t{0});
  shuffle(order, random);
  return order;
}

void add_scenario(std::vector<scenario> &result, std::size_t relation_rows,
                  std::size_t batch_rows, std::uint32_t selectivity_a_bp,
                  std::uint32_t selectivity_b_given_a_bp,
                  distribution match_distribution, std::uint64_t seed) {
  if (batch_rows <= relation_rows) {
    result.push_back({
        relation_rows,
        batch_rows,
        selectivity_a_bp,
        selectivity_b_given_a_bp,
        match_distribution,
        seed,
        0,
        0,
    });
  }
}

} // namespace

const char *distribution_name(distribution value) noexcept {
  switch (value) {
  case distribution::random:
    return "random";
  case distribution::clustered:
    return "clustered";
  case distribution::alternating:
    return "alternating";
  }
  return "unknown";
}

std::string scenario::stable_name() const {
  std::ostringstream out;
  out << "N=" << relation_rows << "/B=" << batch_rows
      << "/sA_bp=" << selectivity_a_bp
      << "/sBgA_bp=" << selectivity_b_given_a_bp
      << "/distribution=" << distribution_name(match_distribution)
      << "/seed=" << seed;
  return out.str();
}

matrix_kind parse_matrix_kind(const std::string &value) {
  if (value == "smoke") {
    return matrix_kind::smoke;
  }
  if (value == "stage1") {
    return matrix_kind::stage1;
  }
  if (value == "stage2") {
    return matrix_kind::stage2;
  }
  if (value == "pressure") {
    return matrix_kind::pressure;
  }
  if (value == "threading") {
    return matrix_kind::threading;
  }
  if (value == "confirmation") {
    return matrix_kind::confirmation;
  }
  throw std::invalid_argument("unknown matrix '" + value +
                              "' (expected smoke, stage1, stage2, pressure, "
                              "threading, or confirmation)");
}

dataset make_dataset(const scenario &value) {
  if (value.selectivity_a_bp > 10000 ||
      value.selectivity_b_given_a_bp > 10000) {
    throw std::invalid_argument("selectivity basis points must be <= 10000");
  }

  dataset result;
  result.a.resize(value.relation_rows);
  result.b.resize(value.relation_rows);
  result.c.resize(value.relation_rows);

  splitmix64 random(value.seed);
  auto order =
      make_order(value.relation_rows, value.match_distribution, random);
  const auto active_a =
      rounded_count(value.relation_rows, value.selectivity_a_bp);
  const auto active_b = rounded_count(active_a, value.selectivity_b_given_a_bp);
  std::vector<std::uint8_t> membership(value.relation_rows, 0);
  for (std::size_t i = 0; i < active_a; ++i) {
    membership[order[i]] = 1;
  }
  for (std::size_t i = 0; i < active_b; ++i) {
    membership[order[i]] = 2;
  }

  for (std::size_t row = 0; row < value.relation_rows; ++row) {
    const auto noise_a = static_cast<std::int32_t>(random.next() % 1024ULL);
    const auto noise_b = static_cast<std::int32_t>(random.next() % 1024ULL);
    result.a[row] =
        membership[row] != 0 ? value.p1 - 1 - noise_a : value.p1 + 1 + noise_a;
    result.b[row] =
        membership[row] == 2 ? value.p2 - 1 - noise_b : value.p2 + 1 + noise_b;
    auto aggregate_value =
        static_cast<std::int32_t>(random.next() % 2001ULL) - 1000;
    if (aggregate_value == 0) {
      aggregate_value = 1;
    }
    result.c[row] = aggregate_value;

    if (result.a[row] < value.p1) {
      ++result.active_after_a;
      if (result.b[row] < value.p2) {
        ++result.active_after_b;
        result.expected_sum += result.c[row];
      }
    }
  }
  return result;
}

std::int64_t expected_sum_for(const dataset &value, const scenario &source,
                              std::size_t aggregate_count) {
  if (aggregate_count != 1 && aggregate_count != 4 && aggregate_count != 8) {
    throw std::invalid_argument("aggregate count must be 1, 4, or 8");
  }
  if (value.a.size() != value.b.size() || value.a.size() != value.c.size()) {
    throw std::invalid_argument("dataset columns must have equal lengths");
  }

  std::int64_t result = 0;
  for (std::size_t row = 0; row < value.a.size(); ++row) {
    if (value.a[row] < source.p1 && value.b[row] < source.p2) {
      for (std::size_t aggregate = 0; aggregate < aggregate_count;
           ++aggregate) {
        result += aggregate_value(value.c[row], aggregate);
      }
    }
  }
  return result;
}

std::vector<scenario> scenarios_for(matrix_kind matrix) {
  std::vector<scenario> result;
  constexpr std::uint64_t first_seed = 0x9f4a7c15ULL;
  constexpr std::uint64_t second_seed = 0xbf58476dULL;

  if (matrix == matrix_kind::smoke) {
    for (const auto selectivity_a : {100U, 5000U, 9000U}) {
      for (const auto selectivity_b : {1000U, 9000U}) {
        add_scenario(result, 1003, 257, selectivity_a, selectivity_b,
                     distribution::random, first_seed);
      }
    }
    add_scenario(result, 65536, 1024, 100U, 1000U, distribution::random,
                 first_seed);
    add_scenario(result, 65536, 16384, 9000U, 9000U, distribution::random,
                 first_seed);
    return result;
  }

  if (matrix == matrix_kind::stage1 || matrix == matrix_kind::stage2 ||
      matrix == matrix_kind::pressure || matrix == matrix_kind::threading) {
    for (const auto relation_rows :
         {std::size_t{1} << 16, std::size_t{1} << 24}) {
      for (const auto batch_rows :
           {std::size_t{1} << 10, std::size_t{1} << 14, std::size_t{1} << 18}) {
        for (const auto selectivity_a : {100U, 1000U, 5000U, 9000U}) {
          for (const auto selectivity_b : {1000U, 9000U}) {
            add_scenario(result, relation_rows, batch_rows, selectivity_a,
                         selectivity_b, distribution::random, first_seed);
          }
        }
      }
    }
    return result;
  }

  for (const auto relation_rows :
       {std::size_t{1} << 16, std::size_t{1} << 24}) {
    for (const auto batch_rows : {std::size_t{1} << 10, std::size_t{1} << 18}) {
      for (const auto selectivity_a : {100U, 9000U}) {
        for (const auto selectivity_b : {1000U, 5000U, 9000U}) {
          for (const auto match_distribution :
               {distribution::random, distribution::clustered}) {
            for (const auto seed : {first_seed, second_seed}) {
              add_scenario(result, relation_rows, batch_rows, selectivity_a,
                           selectivity_b, match_distribution, seed);
            }
          }
        }
      }
    }
  }
  return result;
}

} // namespace intermediate_repr
