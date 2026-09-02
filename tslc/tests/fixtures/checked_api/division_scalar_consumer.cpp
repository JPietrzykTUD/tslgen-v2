#include "tsl_scalar.hpp"

#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <type_traits>
#include <utility>

template <class Vec, class = void>
struct has_div_checked : std::false_type {};

template <class Vec>
struct has_div_checked<
    Vec,
    std::void_t<decltype(tsl::div_checked<Vec>(
        std::declval<typename Vec::register_type>(),
        std::declval<typename Vec::register_type>(),
        std::declval<tsl::precondition_error&>()))>> : std::true_type {};

static_assert(
    has_div_checked<tsl::simd<std::int32_t, tsl::generic<4>>>::value);
static_assert(
    !has_div_checked<tsl::simd<float, tsl::generic<4>>>::value);

template <class T>
int check_integer() {
  constexpr std::size_t lanes = 16 / sizeof(T);
  using Vec = tsl::simd<T, tsl::generic<lanes>>;
  typename Vec::register_type dividend{};
  typename Vec::register_type divisor{};
  for (std::size_t lane = 0; lane < lanes; ++lane) {
    dividend[lane] = static_cast<T>(12 + lane);
    divisor[lane] = static_cast<T>(2);
  }

  tsl::precondition_error error = tsl::precondition_error::zero_divisor;
  const auto quotient = tsl::div_checked<Vec>(dividend, divisor, error);
  if (error != tsl::precondition_error::none || quotient[0] != T{6}) {
    return 1;
  }
  const auto remainder = tsl::mod_checked<Vec>(dividend, divisor, error);
  if (error != tsl::precondition_error::none || remainder[0] != T{0}) {
    return 2;
  }

  divisor[0] = T{0};
  (void)tsl::div_checked<Vec>(dividend, divisor, error);
  if (error != tsl::precondition_error::zero_divisor) {
    return 3;
  }
  (void)tsl::mod_checked<Vec>(dividend, divisor, error);
  if (error != tsl::precondition_error::zero_divisor) {
    return 4;
  }

  const typename Vec::mask_type lane_one_only = typename Vec::mask_type{2};
  const auto masked = tsl::div_mask_checked<Vec>(
      lane_one_only, dividend, divisor, error);
  if (error != tsl::precondition_error::none || masked[0] != dividend[0]) {
    return 5;
  }
  const auto masked_zero = tsl::mod_maskz_checked<Vec>(
      lane_one_only, dividend, divisor, error);
  if (error != tsl::precondition_error::none || masked_zero[0] != T{0}) {
    return 6;
  }

  divisor[1] = T{0};
  (void)tsl::div_mask_checked<Vec>(lane_one_only, dividend, divisor, error);
  if (error != tsl::precondition_error::zero_divisor) {
    return 7;
  }
  return 0;
}

template <class T>
int check_floating() {
  constexpr std::size_t lanes = 16 / sizeof(T);
  using Vec = tsl::simd<T, tsl::generic<lanes>>;
  typename Vec::register_type dividend{};
  typename Vec::register_type divisor{};
  dividend.fill(T{1});
  divisor.fill(T{0});

  const auto quotient = tsl::div<Vec>(dividend, divisor);
  if (!std::isinf(quotient[0])) {
    return 1;
  }
  const auto remainder = tsl::mod<Vec>(dividend, divisor);
  if (!std::isnan(remainder[0])) {
    return 2;
  }
  return 0;
}

int main() {
  int result = 0;
  result |= check_integer<std::int8_t>();
  result |= check_integer<std::uint8_t>();
  result |= check_integer<std::int16_t>();
  result |= check_integer<std::uint16_t>();
  result |= check_integer<std::int32_t>();
  result |= check_integer<std::uint32_t>();
  result |= check_integer<std::int64_t>();
  result |= check_integer<std::uint64_t>();
  result |= check_floating<float>();
  result |= check_floating<double>();
  return result;
}
