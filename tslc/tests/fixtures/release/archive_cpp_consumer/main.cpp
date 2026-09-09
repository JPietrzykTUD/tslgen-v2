#include <array>
#include <cstdint>

#include <tsl.hpp>

int main() {
  using Vec = tsl::simd<std::int32_t, tsl::scalar>;
  std::array<std::int32_t, 1> left{20};
  std::array<std::int32_t, 1> right{22};
  std::array<std::int32_t, 1> output{-1};

  tsl::precondition_error error = tsl::precondition_error::none;
  const auto left_value = tsl::load_checked<Vec, false>(
      tsl::span<std::int32_t const>(left.data(), left.size()), error);
  if (error != tsl::precondition_error::none) {
    return 1;
  }
  const auto right_value = tsl::load<Vec, false>(right.data());
  error = tsl::store_checked<Vec, false>(
      tsl::span<std::int32_t>(output.data(), output.size()),
      tsl::add<Vec>(left_value, right_value));
  return error == tsl::precondition_error::none && output[0] == 42 ? 0 : 2;
}
