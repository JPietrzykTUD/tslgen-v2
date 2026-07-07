#include <algorithm>
#include <array>
#include <cstdint>

#include <iostream>

#include <tsl.hpp>

using DataType = std::uint32_t;
using IndexType = std::size_t;

using SimdStyle = 
      tsl::dataparallel::simd_for_t<tsl::dataparallel::native, DataType>;


auto rake_quicksort(
  DataType * data, std::size_t count
) {
  
}


int main() {
  using Vec = tsl::simd<std::int32_t, tsl::scalar>;

  std::array<std::int32_t, 8> values{{13, -4, 7, 0, 42, 7, -9, 5}};
  for (auto &value : values) {
    value = tsl::add<Vec>(value, 0);
  }

  std::sort(values.begin(), values.end());
  if (!std::is_sorted(values.begin(), values.end())) {
    return 1;
  }

  using NativeVec =
      tsl::dataparallel::simd_for_t<tsl::dataparallel::native, std::int32_t>;
  std::cout << NativeVec::lane_count_v << std::endl;

  return values.front() == -9 && values.back() == 42 ? 0 : 1;
}
