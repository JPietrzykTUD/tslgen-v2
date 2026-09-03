#include "tsl_avx2.hpp"

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <type_traits>

static_assert(std::is_trivially_copyable_v<tsl::span<std::int32_t>>);
static_assert(sizeof(tsl::span<std::int32_t>) ==
              sizeof(std::int32_t*) + sizeof(std::size_t));
static_assert(std::is_convertible_v<tsl::span<std::int32_t>,
                                    tsl::span<std::int32_t const>>);
static_assert(!std::is_convertible_v<tsl::span<std::int32_t const>,
                                     tsl::span<std::int32_t>>);

template <class Vec>
int check_common() {
  using T = typename Vec::base_type;
  constexpr std::size_t lanes = Vec::lane_count();
  alignas(64) T input[lanes + 2]{};
  for (std::size_t lane = 0; lane < lanes + 2; ++lane) {
    input[lane] = static_cast<T>(10 + lane);
  }

  tsl::precondition_error error = tsl::precondition_error::misaligned;
  (void)tsl::load_checked<Vec, false>(tsl::span<T const>{nullptr, 0}, error);
  if (error != tsl::precondition_error::insufficient_extent) {
    return 1;
  }
  (void)tsl::load_checked<Vec, false>(
      tsl::span<T const>{input, lanes - 1}, error);
  if (error != tsl::precondition_error::insufficient_extent) {
    return 2;
  }

  const auto exact = tsl::load_checked<Vec, false>(
      tsl::span<T const>{input + 1, lanes}, error);
  if (error != tsl::precondition_error::none) {
    return 3;
  }
  (void)tsl::load_checked<Vec, false>(
      tsl::span<T const>{input, lanes + 2}, error);
  if (error != tsl::precondition_error::none) {
    return 4;
  }

  alignas(64) T output[lanes + 2];
  std::fill_n(output, lanes + 2, T{-7});
  auto status = tsl::store_checked<Vec, false>(
      tsl::span<T>{output + 1, lanes - 1}, exact);
  if (status != tsl::precondition_error::insufficient_extent ||
      std::any_of(output, output + lanes + 2, [](T value) { return value != T{-7}; })) {
    return 5;
  }
  status = tsl::store_checked<Vec, false>(
      tsl::span<T>{output + 1, lanes}, exact);
  if (status != tsl::precondition_error::none) {
    return 6;
  }
  for (std::size_t lane = 0; lane < lanes; ++lane) {
    if (output[lane + 1] != input[lane + 1]) {
      return 7;
    }
  }
  if (output[0] != T{-7} || output[lanes + 1] != T{-7}) {
    return 8;
  }

  status = tsl::store_checked<Vec, false>(tsl::span<T>{output, 0}, T{99});
  if (status != tsl::precondition_error::insufficient_extent || output[0] != T{-7}) {
    return 9;
  }
  status = tsl::store_checked<Vec, false>(tsl::span<T>{output, 1}, T{99});
  if (status != tsl::precondition_error::none || output[0] != T{99}) {
    return 10;
  }

  const auto no_lanes = tsl::mask_false<Vec>();
  (void)tsl::load_maskz_checked<Vec, false>(
      no_lanes, tsl::span<T const>{input, lanes - 1}, error);
  if (error != tsl::precondition_error::insufficient_extent) {
    return 11;
  }
  std::fill_n(output, lanes + 2, T{-7});
  status = tsl::store_mask_checked<Vec, false>(
      no_lanes, tsl::span<T>{output, lanes - 1}, exact);
  if (status != tsl::precondition_error::insufficient_extent ||
      std::any_of(output, output + lanes + 2, [](T value) { return value != T{-7}; })) {
    return 12;
  }
  return 0;
}

int check_native_alignment() {
  using Vec = tsl::simd<std::int32_t, tsl::avx2>;
  constexpr std::size_t lanes = Vec::lane_count();
  alignas(64) std::int32_t input[lanes + 1]{};
  tsl::precondition_error error = tsl::precondition_error::none;

  (void)tsl::load_checked<Vec, true>(
      tsl::span<std::int32_t const>{input + 1, lanes}, error);
  if (error != tsl::precondition_error::misaligned) {
    return 1;
  }
  (void)tsl::load_checked<Vec, true>(
      tsl::span<std::int32_t const>{input + 1, lanes - 1}, error);
  if (error != tsl::precondition_error::insufficient_extent) {
    return 2;
  }
  (void)tsl::load_checked<Vec, true>(
      tsl::span<std::int32_t const>{input, lanes}, error);
  if (error != tsl::precondition_error::none) {
    return 3;
  }

  const auto value = tsl::load<Vec, false>(input);
  alignas(64) std::int32_t output[lanes + 1];
  std::fill_n(output, lanes + 1, -7);
  auto status = tsl::store_checked<Vec, true>(
      tsl::span<std::int32_t>{output + 1, lanes}, value);
  if (status != tsl::precondition_error::misaligned ||
      std::any_of(output, output + lanes + 1,
                  [](std::int32_t lane) { return lane != -7; })) {
    return 4;
  }
  status = tsl::store_checked<Vec, true>(
      tsl::span<std::int32_t>{output + 1, lanes - 1}, value);
  if (status != tsl::precondition_error::insufficient_extent ||
      std::any_of(output, output + lanes + 1,
                  [](std::int32_t lane) { return lane != -7; })) {
    return 5;
  }
  status = tsl::store_mask_checked<Vec, true>(
      tsl::mask_false<Vec>(),
      tsl::span<std::int32_t>{output + 1, lanes}, value);
  if (status != tsl::precondition_error::misaligned ||
      std::any_of(output, output + lanes + 1,
                  [](std::int32_t lane) { return lane != -7; })) {
    return 6;
  }
  return 0;
}

int main() {
  using Generic = tsl::simd<std::int32_t, tsl::generic<4>>;
  using Native = tsl::simd<std::int32_t, tsl::avx2>;
  return check_common<Generic>() | check_common<Native>() |
         check_native_alignment();
}
