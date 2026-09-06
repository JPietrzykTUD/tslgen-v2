#include "tsl_avx2.hpp"

#include <algorithm>
#include <cstddef>
#include <cstdint>

int check_scalar_load() {
  using Vec = tsl::simd<std::uint32_t, tsl::avx2>;
  const std::uint32_t input[] = {42};
  tsl::precondition_error error = tsl::precondition_error::misaligned;
  const auto value = tsl::load_scalar_checked<Vec>(
      tsl::span<std::uint32_t const>{input, 1}, error);
  if (error != tsl::precondition_error::none || value != 42) {
    return 1;
  }
  (void)tsl::load_scalar_checked<Vec>(
      tsl::span<std::uint32_t const>{nullptr, 0}, error);
  return error == tsl::precondition_error::insufficient_extent ? 0 : 2;
}

int check_converting_load() {
  using Vec = tsl::simd<std::int8_t, tsl::avx2>;
  using ToVec = tsl::simd<std::int32_t, tsl::avx2>;
  const std::int8_t input[] = {1, -2, 3, -4, 5, -6, 7, -8};
  tsl::precondition_error error = tsl::precondition_error::misaligned;
  const auto value = tsl::load_convert_up_checked<Vec, ToVec>(
      tsl::span<std::int8_t const>{input, ToVec::lane_count()}, error);
  if (error != tsl::precondition_error::none) {
    return 1;
  }
  const auto lanes = tsl::to_array<ToVec>(value);
  for (std::size_t lane = 0; lane < ToVec::lane_count(); ++lane) {
    if (lanes[lane] != input[lane]) {
      return 2;
    }
  }
  (void)tsl::load_convert_up_checked<Vec, ToVec>(
      tsl::span<std::int8_t const>{input, ToVec::lane_count() - 1}, error);
  return error == tsl::precondition_error::insufficient_extent ? 0 : 3;
}

int check_random_output() {
  tsl::precondition_error error = tsl::precondition_error::none;
  (void)tsl::random_step_checked(
      tsl::span<std::uint64_t>{nullptr, 0}, error);
  if (error != tsl::precondition_error::insufficient_extent) {
    return 1;
  }
#if defined(__GNUC__) || defined(__clang__)
  if (__builtin_cpu_supports("rdrnd")) {
    std::uint64_t output = 0;
    const auto status = tsl::random_step_checked(
        tsl::span<std::uint64_t>{&output, 1}, error);
    if (error != tsl::precondition_error::none || status > 1) {
      return 2;
    }
  }
#endif
  return 0;
}

int main() {
  return check_scalar_load() | check_converting_load() | check_random_output();
}
