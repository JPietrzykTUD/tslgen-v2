#include "tsl_avx2.hpp"

#include <cstddef>
#include <cstdint>

using Vec = tsl::simd<std::int32_t, tsl::avx2>;
using Register = typename Vec::register_type;

extern "C" __attribute__((noinline)) Register
unchecked_load_avx2(std::int32_t const* source) {
  return tsl::load<Vec, false>(source);
}

extern "C" __attribute__((noinline)) Register checked_load_avx2(
    std::int32_t const* source, std::size_t size,
    tsl::precondition_error& error) {
  return tsl::load_checked<Vec, false>(
      tsl::span<std::int32_t const>{source, size}, error);
}

extern "C" __attribute__((noinline)) void
unchecked_store_avx2(std::int32_t* destination, Register value) {
  tsl::store<Vec, false>(destination, value);
}
