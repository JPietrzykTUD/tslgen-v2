#include "tsl_scalar.hpp"

#include <cstddef>
#include <cstdint>
#include <limits>

using Vec = tsl::simd<std::int32_t, tsl::generic<4>>;

int main() {
  const Vec::register_type data{11, 22, 33, 44};
  tsl::precondition_error error = tsl::precondition_error::none;

  if (tsl::extract_value_at_checked<Vec>(data, 0, error) != 11 ||
      error != tsl::precondition_error::none) {
    return 1;
  }
  if (tsl::extract_value_at_checked<Vec>(data, Vec::lane_count() - 1, error) !=
          44 ||
      error != tsl::precondition_error::none) {
    return 2;
  }
  (void)tsl::extract_value_at_checked<Vec>(data, Vec::lane_count(), error);
  if (error != tsl::precondition_error::index_out_of_bounds) {
    return 3;
  }
  (void)tsl::extract_value_at_checked<Vec>(
      data, std::numeric_limits<std::size_t>::max(), error);
  if (error != tsl::precondition_error::index_out_of_bounds) {
    return 4;
  }

  const auto inserted = tsl::insert_value_at_checked<Vec>(data, 0, 99, error);
  if (inserted[0] != 99 || error != tsl::precondition_error::none) {
    return 5;
  }
  (void)tsl::insert_value_at_checked<Vec>(data, Vec::lane_count(), 99, error);
  if (error != tsl::precondition_error::index_out_of_bounds) {
    return 6;
  }

  (void)tsl::set_mask_lane_checked<Vec>(false, Vec::lane_count(), 1, error);
  if (error != tsl::precondition_error::index_out_of_bounds) {
    return 7;
  }
  return 0;
}
