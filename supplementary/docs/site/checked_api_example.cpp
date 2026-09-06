#include <cstddef>
#include <cstdint>

#include "tsl.hpp"

using example_vec = tsl::simd<std::int32_t, tsl::scalar>;

std::int32_t unchecked_lane(std::int32_t value, std::size_t index) {
  // The caller promises index < example_vec::lane_count().
  return tsl::extract_value_at<example_vec>(value, index);
}

bool checked_lane(std::int32_t value, std::size_t index,
                  std::int32_t& output) {
  tsl::precondition_error error = tsl::precondition_error::none;
  const auto candidate =
      tsl::extract_value_at_checked<example_vec>(value, index, error);
  if (error != tsl::precondition_error::none) {
    return false;
  }
  output = candidate;
  return true;
}
