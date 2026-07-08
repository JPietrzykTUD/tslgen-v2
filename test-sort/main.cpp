#include <algorithm>
#include <array>
#include <cstdint>

#include <iostream>
#include <random>


#include <tsl.hpp>

using _Test_DataType = std::uint32_t;
using _Test_IndexType = std::size_t;


template <class DataType = _Test_DataType, class IndexType = _Test_IndexType>
auto rake_quicksort(
  DataType * data, std::size_t count, std::mt19937_64 & rng
) {
  using IndexSimdStyle = tsl::dataparallel::simd_for_t<tsl::dataparallel::native, IndexType>;
  using DataSimdStyle = tsl::dataparallel::simd_for_t<tsl::dataparallel::fixed<IndexSimdStyle::lane_count_v>, DataType>;

  
  // get pivots (median of three)
  std::size_t const rake_size = count / IndexSimdStyle::lane_count_v;
  std::uniform_int_distribution<IndexType> pivot_dist(0, rake_size - 1);
  std::array<DataType, IndexSimdStyle::lane_count_v> pivots_val;
  struct pivot_t {
    IndexType idx;
    DataType val;
    constexpr pivot_t(IndexType idx, DataType const * data) : idx(idx), val(data[idx]) {}
    friend bool operator<(pivot_t const & lhs, pivot_t const & rhs) {
      return lhs.val < rhs.val;
    }
    friend bool operator>(pivot_t const & lhs, pivot_t const & rhs) {
      return lhs.val > rhs.val;
    }
  };
  for (auto i = 0; i < IndexSimdStyle::lane_count_v; ++i) {
    pivot_t pivot1(pivot_dist(rng), data);
    pivot_t pivot2(pivot_dist(rng), data);
    pivot_t pivot3(pivot_dist(rng), data);
    pivot_t median = std::max(
      std::min(pivot1, pivot2),
      std::min(
        std::max(pivot1, pivot2),
        pivot3
      )
    );
    pivots_val[i] = median.val;
    // swap the median to the back of the rake
    std::swap(data[median.idx], data[(i+1) * rake_size - 1]);
  }
  
  auto rake_indices_vec        = tsl::custom_sequence<IndexSimdStyle> indices(0, rake_size);
  auto const rake_increase_vec = tsl::set1<IndexSimdStyle>(IndexSimdStyle::lane_count_v);
  auto const pivots_vec        = tsl::load<DataSimdStyle, false>(pivots_val.data());

  for (std::size_t i = 0; i < rake_size; ++i) {
    auto const data_vec = tsl::gather<DataSimdStyle, false, >(data, rake_indices_vec);
  }


}


int main() {
  std::mt19937 rng(std::random_device{}());

  return 0;
}
