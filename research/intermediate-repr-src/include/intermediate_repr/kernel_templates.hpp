#pragma once

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <type_traits>
#include <vector>

#include <tsl.hpp>

#include "intermediate_repr/kernel_api.hpp"

#if defined(__GNUC__) || defined(__clang__)
#define IRBENCH_NOINLINE __attribute__((noinline))
#else
#define IRBENCH_NOINLINE
#endif

#if IRBENCH_HAS_CLANG_OVERLAY && defined(__clang__)
#if __has_feature(ext_vector_type_boolean)
#define IRBENCH_HAS_CLANG_BOOLEAN 1
#else
#define IRBENCH_HAS_CLANG_BOOLEAN 0
#endif
#else
#define IRBENCH_HAS_CLANG_BOOLEAN 0
#endif

namespace intermediate_repr {

namespace policies {

using native = tsl::dataparallel::fixed<IRBENCH_NATIVE_LANES>;

#if IRBENCH_HAS_CLANG_OVERLAY
using clang_128_comparison = tsl::dataparallel::clang_fixed<4>;
using clang_256_comparison = tsl::dataparallel::clang_fixed<8>;
using clang_512_comparison = tsl::dataparallel::clang_fixed<16>;
#if IRBENCH_HAS_CLANG_BOOLEAN
using clang_128_boolean = tsl::dataparallel::clang_fixed<
    4, tsl::dataparallel::clang_mask::boolean_vector>;
using clang_256_boolean = tsl::dataparallel::clang_fixed<
    8, tsl::dataparallel::clang_mask::boolean_vector>;
using clang_512_boolean = tsl::dataparallel::clang_fixed<
    16, tsl::dataparallel::clang_mask::boolean_vector>;
#endif
#endif

} // namespace policies

struct less_than_threshold {
  std::int32_t threshold{};

  template <class Vec>
  typename Vec::mask_type
  operator()(typename tsl::reg_param<Vec>::type value) const {
    return tsl::less_than<Vec>(
        value, tsl::set1<Vec>(static_cast<typename Vec::base_type>(threshold)));
  }
};

template <class MainVec, std::size_t AggregateCount> struct filter_aggregate {
  static_assert(supported_aggregate_count_v<AggregateCount>,
                "aggregate count must be 1, 4, or 8");

  using register_type = typename MainVec::register_type;

  explicit filter_aggregate(std::int32_t value) : threshold(value) {
    for (auto &sum : vector_sums) {
      sum = tsl::set_zero<MainVec>();
    }
  }

  std::int32_t threshold{};
  register_type vector_sums[AggregateCount]{};
  std::array<std::int64_t, AggregateCount> scalar_sums{};
  consumed_batch result{};

  template <class Vec>
  void operator()(typename Vec::mask_type active_a,
                  typename tsl::reg_param<Vec>::type b,
                  typename tsl::reg_param<Vec>::type c) {
    result.active_after_a += tsl::mask_population_count<Vec>(active_a);
    const auto threshold_vec =
        tsl::set1<Vec>(static_cast<typename Vec::base_type>(threshold));
    const auto active_b = tsl::less_than<Vec>(b, threshold_vec);
    const auto active = tsl::mask_binary_and<Vec>(active_a, active_b);
    result.active_after_b += tsl::mask_population_count<Vec>(active);
    const auto zero = tsl::set_zero<Vec>();

    for (std::size_t aggregate = 0; aggregate < AggregateCount; ++aggregate) {
      const auto salt = tsl::set1<Vec>(aggregate_xor_salts[aggregate]);
      const auto transformed = tsl::binary_xor<Vec>(c, salt);
      const auto selected = tsl::select<Vec>(active, transformed, zero);
      if constexpr (std::is_same<Vec, MainVec>::value) {
        vector_sums[aggregate] =
            tsl::add<Vec>(vector_sums[aggregate], selected);
      } else {
        scalar_sums[aggregate] +=
            static_cast<std::int64_t>(tsl::hadd<Vec>(selected));
      }
    }
  }

  consumed_batch finalize() const {
    auto final = result;
    for (std::size_t aggregate = 0; aggregate < AggregateCount; ++aggregate) {
      final.sum +=
          static_cast<std::int64_t>(tsl::hadd<MainVec>(vector_sums[aggregate]));
      final.sum += scalar_sums[aggregate];
    }
    return final;
  }
};

template <class Policy, class MaskLayout>
inline std::size_t mask_scratch_bytes(std::size_t batch_rows) {
  using storage_type =
      tsl::algo::mask_storage_type<MaskLayout, Policy, std::int32_t>;
  return tsl::algo::mask_chunk_count<MaskLayout, Policy, std::int32_t>(
             batch_rows) *
         sizeof(storage_type);
}

template <class Policy>
inline std::size_t position_scratch_bytes(std::size_t batch_rows) {
  (void)sizeof(Policy);
  return batch_rows * sizeof(std::uint32_t);
}

template <class Policy, class MaskLayout>
IRBENCH_NOINLINE produced_batch produce_mask_batch(const std::int32_t *a,
                                                   std::size_t rows,
                                                   std::int32_t p1,
                                                   scratch_view scratch) {
  using storage_type =
      tsl::algo::mask_storage_type<MaskLayout, Policy, std::int32_t>;
  const std::size_t required = mask_scratch_bytes<Policy, MaskLayout>(rows);
  if (required > scratch.capacity_bytes) {
    return {0, required, false};
  }
  auto *masks = reinterpret_cast<storage_type *>(scratch.data);
  less_than_threshold predicate{p1};
  const auto produced =
      tsl::algo::predicate_unary<Policy, tsl::algo::alignment::unaligned,
                                 MaskLayout>(predicate, a, masks, rows);
  const auto expected_units =
      tsl::algo::mask_chunk_count<MaskLayout, Policy, std::int32_t>(rows);
  return {produced, required, produced == expected_units};
}

template <class Policy, class MaskLayout, std::size_t AggregateCount>
IRBENCH_NOINLINE consumed_batch consume_mask_batch(const std::int32_t *b,
                                                   const std::int32_t *c,
                                                   std::size_t rows,
                                                   std::int32_t p2,
                                                   scratch_view scratch) {
  using vec = tsl::dataparallel::simd_for_t<Policy, std::int32_t>;
  using storage_type =
      tsl::algo::mask_storage_type<MaskLayout, Policy, std::int32_t>;
  const auto *masks = reinterpret_cast<const storage_type *>(scratch.data);
  return tsl::algo::aggregate_masked_binary<
      Policy, tsl::algo::alignment::unaligned, MaskLayout>(
      filter_aggregate<vec, AggregateCount>{p2}, b, c, masks, rows);
}

template <class Policy>
IRBENCH_NOINLINE produced_batch produce_position_batch(const std::int32_t *a,
                                                       std::size_t rows,
                                                       std::int32_t p1,
                                                       scratch_view scratch) {
  const std::size_t required = position_scratch_bytes<Policy>(rows);
  if (required > scratch.capacity_bytes) {
    return {0, required, false};
  }
  auto *positions = reinterpret_cast<std::uint32_t *>(scratch.data);
  less_than_threshold predicate{p1};
  const auto selected =
      tsl::algo::select_indices_unary<Policy, tsl::algo::alignment::unaligned>(
          predicate, a, positions, rows);
  return {selected, selected * sizeof(std::uint32_t), selected <= rows};
}

template <class Policy, std::size_t AggregateCount>
IRBENCH_NOINLINE consumed_batch consume_position_batch(const std::int32_t *b,
                                                       const std::int32_t *c,
                                                       std::size_t selected,
                                                       std::int32_t p2,
                                                       scratch_view scratch) {
  static_assert(supported_aggregate_count_v<AggregateCount>,
                "aggregate count must be 1, 4, or 8");
  using vec = tsl::dataparallel::simd_for_t<Policy, std::int32_t>;
  using index_vec = typename vec::template with_base_type<std::uint32_t>;
  static_assert(vec::has_static_lane_count_v,
                "position consumer requires fixed lanes");
  constexpr std::size_t lanes = vec::vector_element_count;
  const auto *positions = reinterpret_cast<const std::uint32_t *>(scratch.data);
  const auto threshold = tsl::set1<vec>(static_cast<std::int32_t>(p2));
  const auto zero = tsl::set_zero<vec>();
  typename vec::register_type vector_sums[AggregateCount]{};
  for (auto &sum : vector_sums) {
    sum = zero;
  }

  consumed_batch result{};
  result.active_after_a = selected;
  std::size_t i = 0;
  for (; i + lanes <= selected; i += lanes) {
    const auto b_values =
        tsl::gather_narrow<vec, index_vec,
                           static_cast<std::uint32_t>(sizeof(std::int32_t))>(
            b, positions + i);
    const auto c_values =
        tsl::gather_narrow<vec, index_vec,
                           static_cast<std::uint32_t>(sizeof(std::int32_t))>(
            c, positions + i);
    const auto active = tsl::less_than<vec>(b_values, threshold);
    result.active_after_b += tsl::mask_population_count<vec>(active);
    for (std::size_t aggregate = 0; aggregate < AggregateCount; ++aggregate) {
      const auto salt = tsl::set1<vec>(aggregate_xor_salts[aggregate]);
      const auto transformed = tsl::binary_xor<vec>(c_values, salt);
      const auto selected_values = tsl::select<vec>(active, transformed, zero);
      vector_sums[aggregate] =
          tsl::add<vec>(vector_sums[aggregate], selected_values);
    }
  }
  for (; i < selected; ++i) {
    const auto row = static_cast<std::size_t>(positions[i]);
    if (b[row] < p2) {
      ++result.active_after_b;
      for (std::size_t aggregate = 0; aggregate < AggregateCount; ++aggregate) {
        result.sum += aggregate_value(c[row], aggregate);
      }
    }
  }
  for (std::size_t aggregate = 0; aggregate < AggregateCount; ++aggregate) {
    result.sum +=
        static_cast<std::int64_t>(tsl::hadd<vec>(vector_sums[aggregate]));
  }
  return result;
}

template <class Policy, class MaskLayout, std::size_t AggregateCount>
pipeline_result run_mask_pipeline(columns_view columns, scratch_view scratch,
                                  std::size_t batch_rows, std::int32_t p1,
                                  std::int32_t p2) {
  if (batch_rows == 0 ||
      mask_scratch_bytes<Policy, MaskLayout>(
          std::min(batch_rows, columns.rows)) > scratch.capacity_bytes) {
    return {0, 0, 0, 0, false};
  }

  pipeline_result result{};
  for (std::size_t offset = 0; offset < columns.rows; offset += batch_rows) {
    const auto rows = std::min(batch_rows, columns.rows - offset);
    const auto produced = produce_mask_batch<Policy, MaskLayout>(
        columns.a + offset, rows, p1, scratch);
    const auto consumed =
        consume_mask_batch<Policy, MaskLayout, AggregateCount>(
            columns.b + offset, columns.c + offset, rows, p2, scratch);
    result.sum += consumed.sum;
    result.active_after_a += consumed.active_after_a;
    result.active_after_b += consumed.active_after_b;
    result.intermediate_bytes += produced.bytes;
    result.valid = result.valid && produced.valid;
  }
  return result;
}

template <class Policy, std::size_t AggregateCount>
pipeline_result run_position_pipeline(columns_view columns,
                                      scratch_view scratch,
                                      std::size_t batch_rows, std::int32_t p1,
                                      std::int32_t p2) {
  if (batch_rows == 0 ||
      position_scratch_bytes<Policy>(std::min(batch_rows, columns.rows)) >
          scratch.capacity_bytes) {
    return {0, 0, 0, 0, false};
  }

  pipeline_result result{};
  for (std::size_t offset = 0; offset < columns.rows; offset += batch_rows) {
    const auto rows = std::min(batch_rows, columns.rows - offset);
    const auto produced =
        produce_position_batch<Policy>(columns.a + offset, rows, p1, scratch);
    const auto consumed = consume_position_batch<Policy, AggregateCount>(
        columns.b + offset, columns.c + offset, produced.units, p2, scratch);
    result.sum += consumed.sum;
    result.active_after_a += consumed.active_after_a;
    result.active_after_b += consumed.active_after_b;
    result.intermediate_bytes += produced.bytes;
    result.valid = result.valid && produced.valid;
  }
  return result;
}

template <class Policy, std::size_t AggregateCount>
IRBENCH_NOINLINE pipeline_result run_fused_pipeline(columns_view, scratch_view,
                                                    std::size_t, std::int32_t,
                                                    std::int32_t);

template <class Policy, std::size_t AggregateCount>
inline void append_policy_candidates(std::vector<candidate_descriptor> &result,
                                     std::string_view realization,
                                     std::size_t vector_bits,
                                     std::string_view mask_policy) {
  static_assert(supported_aggregate_count_v<AggregateCount>,
                "aggregate count must be 1, 4, or 8");
  result.push_back({
      realization,
      vector_bits,
      mask_policy,
      "native",
      AggregateCount,
      candidate_kind::materialized,
      &run_mask_pipeline<Policy, tsl::algo::mask_layout::native,
                         AggregateCount>,
      &mask_scratch_bytes<Policy, tsl::algo::mask_layout::native>,
  });
  result.push_back({
      realization,
      vector_bits,
      mask_policy,
      "integral",
      AggregateCount,
      candidate_kind::materialized,
      &run_mask_pipeline<Policy, tsl::algo::mask_layout::integral,
                         AggregateCount>,
      &mask_scratch_bytes<Policy, tsl::algo::mask_layout::integral>,
  });
  result.push_back({
      realization,
      vector_bits,
      mask_policy,
      "bits",
      AggregateCount,
      candidate_kind::materialized,
      &run_mask_pipeline<Policy, tsl::algo::mask_layout::bits, AggregateCount>,
      &mask_scratch_bytes<Policy, tsl::algo::mask_layout::bits>,
  });
  result.push_back({
      realization,
      vector_bits,
      mask_policy,
      "positions",
      AggregateCount,
      candidate_kind::materialized,
      &run_position_pipeline<Policy, AggregateCount>,
      &position_scratch_bytes<Policy>,
  });
  result.push_back({
      realization,
      vector_bits,
      mask_policy,
      "fused",
      AggregateCount,
      candidate_kind::fused_reference,
      &run_fused_pipeline<Policy, AggregateCount>,
      &no_scratch,
  });
}

template <class Policy>
inline void append_policy_aggregate_counts(
    std::vector<candidate_descriptor> &result, std::string_view realization,
    std::size_t vector_bits, std::string_view mask_policy) {
  append_policy_candidates<Policy, 1>(result, realization, vector_bits,
                                      mask_policy);
  append_policy_candidates<Policy, 4>(result, realization, vector_bits,
                                      mask_policy);
  append_policy_candidates<Policy, 8>(result, realization, vector_bits,
                                      mask_policy);
}

template <std::size_t AggregateCount>
inline void
append_scalar_candidates(std::vector<candidate_descriptor> &result) {
  result.push_back({
      "compiler",
      0,
      "n/a",
      "autovec",
      AggregateCount,
      candidate_kind::autovec_reference,
      &run_scalar_autovec<AggregateCount>,
      &no_scratch,
  });
  result.push_back({
      "scalar",
      0,
      "n/a",
      "scalar",
      AggregateCount,
      candidate_kind::scalar_reference,
      &run_scalar_no_vector<AggregateCount>,
      &no_scratch,
  });
}

inline std::vector<candidate_descriptor> compiled_candidates() {
  std::vector<candidate_descriptor> result;
  append_policy_aggregate_counts<policies::native>(
      result, "hardware", IRBENCH_NATIVE_LANES * 32, "hardware");
#if IRBENCH_HAS_CLANG_OVERLAY
  append_policy_aggregate_counts<policies::clang_128_comparison>(
      result, "clang_builtin", 128, "comparison");
  append_policy_aggregate_counts<policies::clang_256_comparison>(
      result, "clang_builtin", 256, "comparison");
  append_policy_aggregate_counts<policies::clang_512_comparison>(
      result, "clang_builtin", 512, "comparison");
#if IRBENCH_HAS_CLANG_BOOLEAN
  append_policy_aggregate_counts<policies::clang_128_boolean>(
      result, "clang_builtin", 128, "boolean");
  append_policy_aggregate_counts<policies::clang_256_boolean>(
      result, "clang_builtin", 256, "boolean");
  append_policy_aggregate_counts<policies::clang_512_boolean>(
      result, "clang_builtin", 512, "boolean");
#endif
#endif
  append_scalar_candidates<1>(result);
  append_scalar_candidates<4>(result);
  append_scalar_candidates<8>(result);
  return result;
}

#define IRBENCH_FOR_EACH_MASK_LAYOUT(M, POLICY)                                \
  M(POLICY, tsl::algo::mask_layout::native)                                    \
  M(POLICY, tsl::algo::mask_layout::integral)                                  \
  M(POLICY, tsl::algo::mask_layout::bits)

#define IRBENCH_FOR_EACH_POLICY(M)                                             \
  M(policies::native)                                                          \
  IRBENCH_FOR_EACH_CLANG_POLICY(M)

#if IRBENCH_HAS_CLANG_OVERLAY
#if IRBENCH_HAS_CLANG_BOOLEAN
#define IRBENCH_FOR_EACH_CLANG_POLICY(M)                                       \
  M(policies::clang_128_comparison)                                            \
  M(policies::clang_256_comparison)                                            \
  M(policies::clang_512_comparison)                                            \
  M(policies::clang_128_boolean)                                               \
  M(policies::clang_256_boolean)                                               \
  M(policies::clang_512_boolean)
#else
#define IRBENCH_FOR_EACH_CLANG_POLICY(M)                                       \
  M(policies::clang_128_comparison)                                            \
  M(policies::clang_256_comparison)                                            \
  M(policies::clang_512_comparison)
#endif
#else
#define IRBENCH_FOR_EACH_CLANG_POLICY(M)
#endif

#define IRBENCH_EXTERN_MASK_CONSUMER(POLICY, LAYOUT, COUNT)                    \
  extern template consumed_batch consume_mask_batch<POLICY, LAYOUT, COUNT>(    \
      const std::int32_t *, const std::int32_t *, std::size_t, std::int32_t,   \
      scratch_view);

#define IRBENCH_EXTERN_MASK(POLICY, LAYOUT)                                    \
  extern template produced_batch produce_mask_batch<POLICY, LAYOUT>(           \
      const std::int32_t *, std::size_t, std::int32_t, scratch_view);          \
  IRBENCH_EXTERN_MASK_CONSUMER(POLICY, LAYOUT, 1)                              \
  IRBENCH_EXTERN_MASK_CONSUMER(POLICY, LAYOUT, 4)                              \
  IRBENCH_EXTERN_MASK_CONSUMER(POLICY, LAYOUT, 8)

#define IRBENCH_EXTERN_POSITION(POLICY, COUNT)                                 \
  extern template consumed_batch consume_position_batch<POLICY, COUNT>(        \
      const std::int32_t *, const std::int32_t *, std::size_t, std::int32_t,   \
      scratch_view);

#define IRBENCH_EXTERN_FUSED(POLICY, COUNT)                                    \
  extern template pipeline_result run_fused_pipeline<POLICY, COUNT>(           \
      columns_view, scratch_view, std::size_t, std::int32_t, std::int32_t);

#define IRBENCH_EXTERN_POLICY(POLICY)                                          \
  IRBENCH_FOR_EACH_MASK_LAYOUT(IRBENCH_EXTERN_MASK, POLICY)                    \
  extern template produced_batch produce_position_batch<POLICY>(               \
      const std::int32_t *, std::size_t, std::int32_t, scratch_view);          \
  IRBENCH_EXTERN_POSITION(POLICY, 1)                                           \
  IRBENCH_EXTERN_POSITION(POLICY, 4)                                           \
  IRBENCH_EXTERN_POSITION(POLICY, 8)                                           \
  IRBENCH_EXTERN_FUSED(POLICY, 1)                                              \
  IRBENCH_EXTERN_FUSED(POLICY, 4)                                              \
  IRBENCH_EXTERN_FUSED(POLICY, 8)

IRBENCH_FOR_EACH_POLICY(IRBENCH_EXTERN_POLICY)

#undef IRBENCH_EXTERN_POLICY
#undef IRBENCH_EXTERN_FUSED
#undef IRBENCH_EXTERN_POSITION
#undef IRBENCH_EXTERN_MASK_CONSUMER
#undef IRBENCH_EXTERN_MASK

} // namespace intermediate_repr
