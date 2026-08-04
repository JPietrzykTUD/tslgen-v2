#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace intermediate_repr {

enum class distribution {
  random,
  clustered,
  alternating,
};

enum class matrix_kind {
  smoke,
  stage1,
  stage2,
  pressure,
  threading,
  confirmation,
};

struct scenario {
  std::size_t relation_rows{};
  std::size_t batch_rows{};
  std::uint32_t selectivity_a_bp{};
  std::uint32_t selectivity_b_given_a_bp{};
  distribution match_distribution{distribution::random};
  std::uint64_t seed{};
  std::int32_t p1{};
  std::int32_t p2{};

  std::string stable_name() const;
};

struct dataset {
  std::vector<std::int32_t> a;
  std::vector<std::int32_t> b;
  std::vector<std::int32_t> c;
  std::int64_t expected_sum{};
  std::size_t active_after_a{};
  std::size_t active_after_b{};
};

const char *distribution_name(distribution value) noexcept;
matrix_kind parse_matrix_kind(const std::string &value);
dataset make_dataset(const scenario &value);
std::int64_t expected_sum_for(const dataset &value, const scenario &source,
                              std::size_t aggregate_count);
std::vector<scenario> scenarios_for(matrix_kind matrix);

} // namespace intermediate_repr
