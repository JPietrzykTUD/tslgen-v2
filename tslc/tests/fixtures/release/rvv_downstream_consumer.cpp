#include <cstddef>
#include <cstdint>
#include <vector>

#include <tsl.hpp>

namespace {

using Vec = tsl::simd<std::int32_t, tsl::rvv>;

auto scalar_expected_lane(std::int32_t left, std::int32_t right)
    -> std::int32_t {
  return (left + right) * 3;
}

}  // namespace

int main() {
  const std::size_t lanes = Vec::lane_count();
  std::vector<std::int32_t> left(lanes);
  std::vector<std::int32_t> right(lanes);
  std::vector<std::int32_t> ordinary(lanes, -1);
  std::vector<std::int32_t> checked(lanes, -1);
  for (std::size_t lane = 0; lane < lanes; ++lane) {
    left[lane] = static_cast<std::int32_t>(lane * 5 + 1);
    right[lane] = static_cast<std::int32_t>(17 - (lane % 7));
  }

  const auto left_vec = tsl::load<Vec, false>(left.data());
  const auto right_vec = tsl::load<Vec, false>(right.data());
  const auto factor = tsl::set1<Vec>(3);
  const auto ordinary_result =
      tsl::mul<Vec>(tsl::add<Vec>(left_vec, right_vec), factor);
  tsl::store<Vec, false>(ordinary.data(), ordinary_result);

  tsl::precondition_error error = tsl::precondition_error::none;
  const auto checked_left = tsl::load_checked<Vec, false>(
      tsl::span<std::int32_t const>(left.data(), left.size()), error);
  if (error != tsl::precondition_error::none) {
    return 1;
  }
  const auto checked_right = tsl::load_checked<Vec, false>(
      tsl::span<std::int32_t const>(right.data(), right.size()), error);
  if (error != tsl::precondition_error::none) {
    return 2;
  }
  const auto checked_result =
      tsl::mul<Vec>(tsl::add<Vec>(checked_left, checked_right), factor);
  if (tsl::store_checked<Vec, false>(
          tsl::span<std::int32_t>(checked.data(), checked.size()),
          checked_result) != tsl::precondition_error::none) {
    return 3;
  }

  for (std::size_t lane = 0; lane < lanes; ++lane) {
    const auto expected = scalar_expected_lane(left[lane], right[lane]);
    if (ordinary[lane] != expected || checked[lane] != expected) {
      return 4;
    }
  }

  const auto ignored = tsl::load_checked<Vec, false>(
      tsl::span<std::int32_t const>(left.data(), lanes - 1), error);
  (void)ignored;
  if (error != tsl::precondition_error::insufficient_extent) {
    return 5;
  }

  std::vector<std::int32_t> canary(lanes, 0x1234567);
  if (tsl::store_checked<Vec, false>(
          tsl::span<std::int32_t>(canary.data(), lanes - 1),
          ordinary_result) != tsl::precondition_error::insufficient_extent) {
    return 6;
  }
  for (const auto value : canary) {
    if (value != 0x1234567) {
      return 7;
    }
  }
  return 0;
}
