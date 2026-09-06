#include "tsl_avx2.hpp"

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <limits>

template <class Vec>
auto register_from(const typename Vec::base_type* values)
    -> typename Vec::register_type {
  typename tsl::array_for<Vec>::type lanes{};
  for (std::size_t lane = 0; lane < Vec::lane_count(); ++lane) {
    lanes[lane] = values[lane];
  }
  return tsl::from_array<Vec>(lanes);
}

template <class Vec>
auto two_lane_mask() -> typename Vec::mask_type {
  auto mask = tsl::mask_false<Vec>();
  tsl::precondition_error error = tsl::precondition_error::none;
  mask = tsl::set_mask_lane_checked<Vec>(mask, 1, 1, error);
  if (error != tsl::precondition_error::none) {
    return tsl::mask_false<Vec>();
  }
  return tsl::set_mask_lane_checked<Vec>(mask, 3, 1, error);
}

int check_indexed() {
  using Vec = tsl::simd<std::int32_t, tsl::avx2>;
  using Wide = tsl::simd<std::int64_t, tsl::avx2>;
  alignas(64) std::int32_t input[Vec::lane_count()] = {
      10, 11, 12, 13, 14, 15, 16, 17};
  const std::int32_t ordered[] = {0, 1, 2, 3, 4, 5, 6, 7};
  auto indices = register_from<Vec>(ordered);
  tsl::precondition_error error = tsl::precondition_error::misaligned;
  auto value = tsl::gather_checked<Vec, Vec, 4>(
      tsl::span<std::int32_t const>{input, Vec::lane_count()}, indices, error);
  if (error != tsl::precondition_error::none) {
    return 1;
  }
  const auto gathered = tsl::to_array<Vec>(value);
  for (std::size_t lane = 0; lane < Vec::lane_count(); ++lane) {
    if (gathered[lane] != input[lane]) {
      return 2;
    }
  }

  const std::int64_t partial_index_values[] = {1, 3, 5, 7};
  const auto partial_indices = register_from<Wide>(partial_index_values);
  const auto partial = tsl::gather_narrow_partial_checked<Vec, Wide, 4>(
      tsl::span<std::int32_t const>{input, Vec::lane_count()}, partial_indices,
      error);
  if (error != tsl::precondition_error::none) {
    return 10;
  }
  const auto partial_lanes = tsl::to_array<Vec>(partial);
  for (std::size_t lane = 0; lane < Vec::lane_count(); ++lane) {
    const auto expected = lane < Wide::lane_count()
                              ? input[partial_index_values[lane]]
                              : 0;
    if (partial_lanes[lane] != expected) {
      return 11;
    }
  }

  std::int32_t negative_values[Vec::lane_count()]{};
  negative_values[0] = -1;
  indices = register_from<Vec>(negative_values);
  (void)tsl::gather_checked<Vec, Vec, 4>(
      tsl::span<std::int32_t const>{input, Vec::lane_count()}, indices, error);
  if (error != tsl::precondition_error::index_out_of_bounds) {
    return 3;
  }

  std::int32_t one_values[Vec::lane_count()]{};
  one_values[0] = 1;
  indices = register_from<Vec>(one_values);
  (void)tsl::gather_checked<Vec, Vec, 2>(
      tsl::span<std::int32_t const>{input, Vec::lane_count()}, indices, error);
  if (error != tsl::precondition_error::misaligned) {
    return 4;
  }

  std::int64_t huge_values[Wide::lane_count()];
  std::fill_n(huge_values, Wide::lane_count(),
              (std::numeric_limits<std::int64_t>::max)());
  const auto huge = register_from<Wide>(huge_values);
  alignas(64) std::int64_t wide_input[1] = {42};
  (void)tsl::gather_checked<Wide, Wide,
                            (std::numeric_limits<std::uint32_t>::max)()>(
      tsl::span<std::int64_t const>{wide_input, 1}, huge, error);
  if (error != tsl::precondition_error::address_overflow) {
    return 5;
  }

  const auto inactive = tsl::mask_false<Vec>();
  const std::int32_t pass_values[] = {20, 21, 22, 23, 24, 25, 26, 27};
  const auto pass = register_from<Vec>(pass_values);
  value = tsl::gather_mask_checked<Vec, Vec, 4>(
      inactive, tsl::span<std::int32_t const>{nullptr, 0},
      register_from<Vec>(negative_values), pass, error);
  if (error != tsl::precondition_error::none) {
    return 6;
  }
  const auto preserved = tsl::to_array<Vec>(value);
  for (std::size_t lane = 0; lane < Vec::lane_count(); ++lane) {
    if (preserved[lane] != pass_values[lane]) {
      return 7;
    }
  }

  alignas(64) std::int32_t output[Vec::lane_count() + 2];
  std::fill_n(output, Vec::lane_count() + 2, -7);
  auto status = tsl::scatter_checked<Vec, Vec, 4>(
      tsl::span<std::int32_t>{output + 1, Vec::lane_count()},
      register_from<Vec>(negative_values), pass);
  if (status != tsl::precondition_error::index_out_of_bounds ||
      std::any_of(output, output + Vec::lane_count() + 2,
                  [](std::int32_t lane) { return lane != -7; })) {
    return 8;
  }
  status = tsl::scatter_maskz_checked<Vec, Vec, 4>(
      inactive, tsl::span<std::int32_t>{nullptr, 0},
      register_from<Vec>(negative_values), pass);
  if (status != tsl::precondition_error::none) {
    return 9;
  }
  return 0;
}

int check_compacted() {
  using Vec = tsl::simd<std::int32_t, tsl::avx2>;
  const std::int32_t values[] = {10, 11, 12, 13, 14, 15, 16, 17};
  const auto value = register_from<Vec>(values);
  const auto mask = two_lane_mask<Vec>();
  std::int32_t output[4] = {-7, -7, -7, -7};

  auto status = tsl::compress_store_checked<Vec>(
      mask, tsl::span<std::int32_t>{output + 1, 1}, value);
  if (status != tsl::precondition_error::insufficient_extent ||
      std::any_of(output, output + 4,
                  [](std::int32_t lane) { return lane != -7; })) {
    return 1;
  }
  status = tsl::compress_store_checked<Vec>(
      mask, tsl::span<std::int32_t>{output + 1, 2}, value);
  if (status != tsl::precondition_error::none || output[0] != -7 ||
      output[1] != 11 || output[2] != 13 || output[3] != -7) {
    return 2;
  }

  tsl::precondition_error error = tsl::precondition_error::none;
  const std::int32_t packed[] = {31, 33};
  (void)tsl::expand_load_checked<Vec>(
      mask, tsl::span<std::int32_t const>{packed, 1}, error);
  if (error != tsl::precondition_error::insufficient_extent) {
    return 3;
  }
  const auto expanded = tsl::expand_load_checked<Vec>(
      mask, tsl::span<std::int32_t const>{packed, 2}, error);
  if (error != tsl::precondition_error::none) {
    return 4;
  }
  const auto expanded_lanes = tsl::to_array<Vec>(expanded);
  for (std::size_t lane = 0; lane < Vec::lane_count(); ++lane) {
    const auto expected = lane == 1 ? 31 : lane == 3 ? 33 : 0;
    if (expanded_lanes[lane] != expected) {
      return 5;
    }
  }

  const auto inactive = tsl::mask_false<Vec>();
  status = tsl::compress_store_checked<Vec>(
      inactive, tsl::span<std::int32_t>{nullptr, 0}, value);
  if (status != tsl::precondition_error::none) {
    return 6;
  }
  const auto zero = tsl::expand_load_checked<Vec>(
      inactive, tsl::span<std::int32_t const>{nullptr, 0}, error);
  if (error != tsl::precondition_error::none) {
    return 7;
  }
  const auto zero_lanes = tsl::to_array<Vec>(zero);
  if (std::any_of(zero_lanes._storage.begin(), zero_lanes._storage.end(),
                  [](std::int32_t lane) { return lane != 0; })) {
    return 8;
  }
  return 0;
}

int main() { return check_indexed() | check_compacted(); }
