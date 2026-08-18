#pragma once

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <new>
#include <string_view>

namespace intermediate_repr {

inline constexpr std::size_t max_aggregate_count = 8;
inline constexpr std::array<std::int32_t, max_aggregate_count>
    aggregate_xor_salts{{0, 1, 3, 7, 15, 31, 63, 127}};

template <std::size_t AggregateCount>
inline constexpr bool supported_aggregate_count_v =
    AggregateCount == 1 || AggregateCount == 4 || AggregateCount == 8;

inline std::int32_t aggregate_value(std::int32_t value,
                                    std::size_t aggregate_index) noexcept {
  return value ^ aggregate_xor_salts[aggregate_index];
}

struct columns_view {
  const std::int32_t *a{};
  const std::int32_t *b{};
  const std::int32_t *c{};
  std::size_t rows{};
};

struct scratch_view {
  std::byte *data{};
  std::size_t capacity_bytes{};
};

struct pipeline_result {
  std::int64_t sum{};
  std::size_t active_after_a{};
  std::size_t active_after_b{};
  std::size_t intermediate_bytes{};
  bool valid{true};
};

struct produced_batch {
  std::size_t units{};
  std::size_t bytes{};
  bool valid{true};
};

struct consumed_batch {
  std::int64_t sum{};
  std::size_t active_after_a{};
  std::size_t active_after_b{};
};

class scratch_buffer {
public:
  explicit scratch_buffer(std::size_t bytes)
      : capacity_bytes_(std::max<std::size_t>(bytes, 64)),
        data_(static_cast<std::byte *>(
            ::operator new(capacity_bytes_, std::align_val_t{64}))) {}

  ~scratch_buffer() { ::operator delete(data_, std::align_val_t{64}); }

  scratch_buffer(const scratch_buffer &) = delete;
  scratch_buffer &operator=(const scratch_buffer &) = delete;

  scratch_view view() noexcept { return {data_, capacity_bytes_}; }

  std::byte *data() noexcept { return data_; }

  std::size_t size() const noexcept { return capacity_bytes_; }

private:
  std::size_t capacity_bytes_{};
  std::byte *data_{};
};

using pipeline_fn = pipeline_result (*)(columns_view, scratch_view, std::size_t,
                                        std::int32_t, std::int32_t);
using scratch_bytes_fn = std::size_t (*)(std::size_t);

enum class candidate_kind {
  materialized,
  fused_reference,
  autovec_reference,
  scalar_reference,
};

struct candidate_descriptor {
  std::string_view realization;
  std::size_t vector_bits{};
  std::string_view mask_policy;
  std::string_view representation;
  std::size_t aggregate_count{};
  candidate_kind kind{candidate_kind::materialized};
  pipeline_fn run{};
  scratch_bytes_fn scratch_bytes{};
};

template <std::size_t AggregateCount>
pipeline_result run_scalar_autovec(columns_view, scratch_view, std::size_t,
                                   std::int32_t, std::int32_t);
template <std::size_t AggregateCount>
pipeline_result run_scalar_no_vector(columns_view, scratch_view, std::size_t,
                                     std::int32_t, std::int32_t);

inline std::size_t no_scratch(std::size_t) noexcept { return 0; }

inline bool is_materialized(candidate_kind kind) noexcept {
  return kind == candidate_kind::materialized;
}

} // namespace intermediate_repr
