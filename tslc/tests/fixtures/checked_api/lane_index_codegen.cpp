#include "tsl_avx2.hpp"

#include <cstddef>
#include <cstdint>

using Vec = tsl::simd<std::int32_t, tsl::generic<4>>;

extern "C" __attribute__((noinline)) std::int32_t unchecked_lane(
    Vec::register_type data, std::size_t index) {
  return tsl::extract_value_at<Vec>(data, index);
}

extern "C" __attribute__((noinline)) std::int32_t checked_lane(
    Vec::register_type data, std::size_t index, tsl::precondition_error& error) {
  return tsl::extract_value_at_checked<Vec>(data, index, error);
}
