#include "intermediate_repr/kernel_templates.hpp"
#include "intermediate_repr/scenario.hpp"

#include <algorithm>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>

namespace intermediate_repr {
namespace {

columns_view view_of(const dataset &data) {
  return {data.a.data(), data.b.data(), data.c.data(), data.a.size()};
}

bool matches_expected(const pipeline_result &actual, const dataset &expected,
                      const scenario &source, std::size_t aggregate_count) {
  return actual.valid &&
         actual.sum == expected_sum_for(expected, source, aggregate_count) &&
         actual.active_after_a == expected.active_after_a &&
         actual.active_after_b == expected.active_after_b;
}

template <class Policy>
bool check_representation_invariants(const char *policy_name) {
  using vec = tsl::dataparallel::simd_for_t<Policy, std::int32_t>;
  constexpr std::size_t lanes = vec::vector_element_count;
  const scenario value{
      lanes + 3,     lanes + 3, 5000, 5000, distribution::alternating,
      0x12345678ULL, 0,         0,
  };
  const auto data = make_dataset(value);
  scratch_buffer scratch(position_scratch_bytes<Policy>(value.batch_rows));
  std::memset(scratch.data(), 0xa5, scratch.size());
  const auto positions = produce_position_batch<Policy>(
      data.a.data(), data.a.size(), value.p1, scratch.view());
  if (!positions.valid || positions.units != data.active_after_a) {
    std::cerr << policy_name << ": position producer count mismatch\n";
    return false;
  }
  const auto *indices = reinterpret_cast<const std::uint32_t *>(scratch.data());
  std::size_t expected_index = 0;
  for (std::size_t row = 0; row < data.a.size(); ++row) {
    if (data.a[row] < value.p1) {
      if (indices[expected_index] != row) {
        std::cerr << policy_name << ": position order mismatch\n";
        return false;
      }
      ++expected_index;
    }
  }
  if (positions.units < data.a.size() &&
      indices[positions.units] != 0xa5a5a5a5U) {
    std::cerr << policy_name << ": position producer overwrote its tail\n";
    return false;
  }

  std::memset(scratch.data(), 0xa5, scratch.size());
  const auto bits = produce_mask_batch<Policy, tsl::algo::mask_layout::bits>(
      data.a.data(), data.a.size(), value.p1, scratch.view());
  const auto expected_bit_bytes = (data.a.size() + 7) / 8;
  if (!bits.valid || bits.bytes != expected_bit_bytes) {
    std::cerr << policy_name << ": packed-bit size mismatch\n";
    return false;
  }
  const auto tail_lanes = data.a.size() % 8;
  if (tail_lanes != 0) {
    const auto allowed = static_cast<std::uint8_t>((1U << tail_lanes) - 1U);
    const auto last =
        std::to_integer<std::uint8_t>(scratch.data()[bits.bytes - 1]);
    if ((last & static_cast<std::uint8_t>(~allowed)) != 0) {
      std::cerr << policy_name << ": packed-bit tail is not zero\n";
      return false;
    }
  }

  std::cout << "policy=" << policy_name << " lanes=" << lanes
            << " vector_bytes=" << sizeof(typename vec::register_type)
            << " mask_bytes=" << sizeof(typename vec::mask_type)
            << " imask_bytes=" << sizeof(typename vec::imask_type) << '\n';
  return true;
}

bool check_all_policy_invariants() {
  bool ok = true;
  ok = check_representation_invariants<policies::native>("hardware") && ok;
#if IRBENCH_HAS_CLANG_OVERLAY
  ok = check_representation_invariants<policies::clang_128_comparison>(
           "clang128-comparison") &&
       ok;
  ok = check_representation_invariants<policies::clang_256_comparison>(
           "clang256-comparison") &&
       ok;
  ok = check_representation_invariants<policies::clang_512_comparison>(
           "clang512-comparison") &&
       ok;
#if IRBENCH_HAS_CLANG_BOOLEAN
  ok = check_representation_invariants<policies::clang_128_boolean>(
           "clang128-boolean") &&
       ok;
  ok = check_representation_invariants<policies::clang_256_boolean>(
           "clang256-boolean") &&
       ok;
  ok = check_representation_invariants<policies::clang_512_boolean>(
           "clang512-boolean") &&
       ok;
#endif
#endif
  return ok;
}

std::vector<scenario> correctness_scenarios(std::size_t lanes) {
  std::vector<scenario> result;
  const std::vector<std::size_t> row_counts{
      0, 1, lanes > 1 ? lanes - 1 : 1, lanes, lanes + 1, lanes + 3, 1003,
  };
  for (const auto rows : row_counts) {
    const auto batch_rows =
        rows == lanes + 3 ? lanes
                          : std::max<std::size_t>(1, std::min(rows, lanes + 3));
    for (const auto selectivity_a : {0U, 3333U, 5000U, 10000U}) {
      for (const auto selectivity_b : {0U, 5000U, 10000U}) {
        result.push_back({
            rows,
            batch_rows,
            selectivity_a,
            selectivity_b,
            selectivity_a == 5000U ? distribution::alternating
                                   : distribution::random,
            0x6a09e667ULL + rows,
            0,
            0,
        });
      }
    }
  }
  return result;
}

} // namespace
} // namespace intermediate_repr

int main() {
  using namespace intermediate_repr;
  if (!check_all_policy_invariants()) {
    return 1;
  }

  const auto candidates = compiled_candidates();
  for (const auto &candidate : candidates) {
    const auto lanes = std::max<std::size_t>(1, candidate.vector_bits / 32);
    for (const auto &value : correctness_scenarios(lanes)) {
      const auto data = make_dataset(value);
      scratch_buffer scratch(candidate.scratch_bytes(value.batch_rows));
      std::memset(scratch.data(), 0xa5, scratch.size());
      const auto actual = candidate.run(view_of(data), scratch.view(),
                                        value.batch_rows, value.p1, value.p2);
      if (!matches_expected(actual, data, value, candidate.aggregate_count)) {
        std::cerr << "correctness failure: realization="
                  << candidate.realization
                  << " vector_bits=" << candidate.vector_bits
                  << " mask_policy=" << candidate.mask_policy
                  << " representation=" << candidate.representation
                  << " aggregates=" << candidate.aggregate_count << ' '
                  << value.stable_name() << " expected(sum="
                  << expected_sum_for(data, value, candidate.aggregate_count)
                  << ",a=" << data.active_after_a
                  << ",b=" << data.active_after_b
                  << ") actual(sum=" << actual.sum
                  << ",a=" << actual.active_after_a
                  << ",b=" << actual.active_after_b << ",valid=" << actual.valid
                  << ")\n";
        return 2;
      }
      if (is_materialized(candidate.kind) && actual.active_after_a != 0 &&
          actual.intermediate_bytes == 0) {
        std::cerr << "materialized candidate reported zero bytes: "
                  << candidate.representation << '\n';
        return 3;
      }
      if (!is_materialized(candidate.kind) && actual.intermediate_bytes != 0) {
        std::cerr << "reference reported intermediate bytes: "
                  << candidate.representation << '\n';
        return 4;
      }
    }
  }

  std::cout << "all " << candidates.size()
            << " compiled candidates passed correctness\n";
  return 0;
}
