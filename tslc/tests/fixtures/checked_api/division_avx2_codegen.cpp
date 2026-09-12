#include "tsl_avx2.hpp"

#include <cstdint>
#include <immintrin.h>

#if defined(_MSC_VER)
#define TSL_TEST_NOINLINE __declspec(noinline)
#else
#define TSL_TEST_NOINLINE __attribute__((noinline))
#endif

using Vec = tsl::simd<std::int32_t, tsl::avx2>;

extern "C" TSL_TEST_NOINLINE auto checked_divide_avx2(
    __m256i dividend,
    __m256i divisor,
    tsl::precondition_error& error) noexcept -> __m256i {
  return tsl::div_checked<Vec>(dividend, divisor, error);
}

extern "C" TSL_TEST_NOINLINE auto consume_unchecked_divide_avx2(
    __m256i dividend, __m256i divisor) noexcept -> __m256i {
  const auto quotient = tsl::div<Vec>(dividend, divisor);
  return tsl::add<Vec>(quotient, _mm256_set1_epi32(1));
}

extern "C" TSL_TEST_NOINLINE auto consume_checked_divide_avx2(
    __m256i dividend, __m256i divisor) noexcept -> __m256i {
  tsl::precondition_error error = tsl::precondition_error::zero_divisor;
  const auto quotient = tsl::div_checked<Vec>(dividend, divisor, error);
  if (error != tsl::precondition_error::none) {
    return _mm256_setzero_si256();
  }
  return tsl::add<Vec>(quotient, _mm256_set1_epi32(1));
}
