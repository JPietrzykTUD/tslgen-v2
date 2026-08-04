#include "intermediate_repr/kernel_templates.hpp"

#include <algorithm>

namespace intermediate_repr {

#if defined(IRBENCH_BUILD_SCALAR_REFERENCE)

template <std::size_t AggregateCount>
IRBENCH_NOINLINE
    pipeline_result IRBENCH_SCALAR_FUNCTION(columns_view columns, scratch_view,
                                            std::size_t batch_rows,
                                            std::int32_t p1, std::int32_t p2) {
  static_assert(supported_aggregate_count_v<AggregateCount>,
                "aggregate count must be 1, 4, or 8");
  if (batch_rows == 0) {
    return {0, 0, 0, 0, false};
  }
  pipeline_result result{};
  for (std::size_t offset = 0; offset < columns.rows; offset += batch_rows) {
    const auto rows = std::min(batch_rows, columns.rows - offset);
    for (std::size_t i = 0; i < rows; ++i) {
      const auto row = offset + i;
      if (columns.a[row] < p1) {
        ++result.active_after_a;
        if (columns.b[row] < p2) {
          ++result.active_after_b;
          for (std::size_t aggregate = 0; aggregate < AggregateCount;
               ++aggregate) {
            result.sum += aggregate_value(columns.c[row], aggregate);
          }
        }
      }
    }
  }
  return result;
}

#define IRBENCH_INSTANTIATE_SCALAR(COUNT)                                      \
  template pipeline_result IRBENCH_SCALAR_FUNCTION<COUNT>(                     \
      columns_view, scratch_view, std::size_t, std::int32_t, std::int32_t);

IRBENCH_INSTANTIATE_SCALAR(1)
IRBENCH_INSTANTIATE_SCALAR(4)
IRBENCH_INSTANTIATE_SCALAR(8)

#undef IRBENCH_INSTANTIATE_SCALAR

#elif defined(IRBENCH_BUILD_TSL_REFERENCES)

template <class Policy, std::size_t AggregateCount>
IRBENCH_NOINLINE
    pipeline_result run_fused_pipeline(columns_view columns, scratch_view,
                                       std::size_t batch_rows, std::int32_t p1,
                                       std::int32_t p2) {
  static_assert(supported_aggregate_count_v<AggregateCount>,
                "aggregate count must be 1, 4, or 8");
  using vec = tsl::dataparallel::simd_for_t<Policy, std::int32_t>;
  using scalar_vec = tsl::simd<std::int32_t, tsl::scalar>;
  static_assert(vec::has_static_lane_count_v,
                "fused reference requires fixed lanes");
  constexpr std::size_t lanes = vec::vector_element_count;
  if (batch_rows == 0) {
    return {0, 0, 0, 0, false};
  }

  const auto p1_vec = tsl::set1<vec>(p1);
  const auto p1_scalar = tsl::set1<scalar_vec>(p1);
  pipeline_result result{};
  for (std::size_t offset = 0; offset < columns.rows; offset += batch_rows) {
    const auto rows = std::min(batch_rows, columns.rows - offset);
    filter_aggregate<vec, AggregateCount> aggregate{p2};
    std::size_t i = 0;
    for (; i + lanes <= rows; i += lanes) {
      const auto a = tsl::load<vec, false>(columns.a + offset + i);
      const auto b = tsl::load<vec, false>(columns.b + offset + i);
      const auto c = tsl::load<vec, false>(columns.c + offset + i);
      const auto active_a = tsl::less_than<vec>(a, p1_vec);
      aggregate.template operator()<vec>(active_a, b, c);
    }
    for (; i < rows; ++i) {
      const auto row = offset + i;
      const auto a = tsl::load<scalar_vec, false>(columns.a + row);
      const auto b = tsl::load<scalar_vec, false>(columns.b + row);
      const auto c = tsl::load<scalar_vec, false>(columns.c + row);
      const auto active_a = tsl::less_than<scalar_vec>(a, p1_scalar);
      aggregate.template operator()<scalar_vec>(active_a, b, c);
    }
    const auto consumed = aggregate.finalize();
    result.sum += consumed.sum;
    result.active_after_a += consumed.active_after_a;
    result.active_after_b += consumed.active_after_b;
  }
  return result;
}

#define IRBENCH_INSTANTIATE_FUSED_COUNT(POLICY, COUNT)                         \
  template pipeline_result run_fused_pipeline<POLICY, COUNT>(                  \
      columns_view, scratch_view, std::size_t, std::int32_t, std::int32_t);

#define IRBENCH_INSTANTIATE_FUSED(POLICY)                                      \
  IRBENCH_INSTANTIATE_FUSED_COUNT(POLICY, 1)                                   \
  IRBENCH_INSTANTIATE_FUSED_COUNT(POLICY, 4)                                   \
  IRBENCH_INSTANTIATE_FUSED_COUNT(POLICY, 8)

IRBENCH_FOR_EACH_POLICY(IRBENCH_INSTANTIATE_FUSED)

#undef IRBENCH_INSTANTIATE_FUSED
#undef IRBENCH_INSTANTIATE_FUSED_COUNT

#else
#error "references.cpp requires one explicit build mode"
#endif

} // namespace intermediate_repr
