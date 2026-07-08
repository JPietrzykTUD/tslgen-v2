#include <algorithm>
#include <array>
#include <cstdint>

#include <iostream>
#include <random>


#include <tsl.hpp>

using _Test_DataType = std::uint32_t;
using _Test_IndexType = std::size_t;

template <typename DataType, typename IndexType>
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

template <class DataType = _Test_DataType, class IndexType = _Test_IndexType>
auto rake_quicksort(
  DataType * data, IndexType * indices, std::size_t count, std::mt19937_64 & rng
) {
  using IndexSimdStyle = tsl::dataparallel::simd_for_t<tsl::dataparallel::native, IndexType>;
  // using DataSimdStyle = tsl::dataparallel::simd_for_t<tsl::dataparallel::fixed<IndexSimdStyle::lane_count_v>, DataType>;
  using DataSimdStyle = tsl::dataparallel::simd_for_t<tsl::dataparallel::native, DataType>;

  
  // get pivots (median of three)
  std::size_t const rake_size = count / DataSimdStyle::lane_count_v;
  std::uniform_int_distribution<IndexType> pivot_dist(0, rake_size - 1);
  std::array<DataType, DataSimdStyle::lane_count_v> pivot_vals;
  std::array<IndexType, DataSimdStyle::lane_count_v> gather_lo_idxs;
  std::array<IndexType, DataSimdStyle::lane_count_v> gather_hi_idxs;
  
  for (auto i = 0; i < DataSimdStyle::lane_count_v; ++i) {
    std::span<DataType> rake_span(data + i * rake_size, rake_size);
    pivot_t<DataType, IndexType> pivot1(pivot_dist(rng), rake_span.data());
    pivot_t<DataType, IndexType> pivot2(pivot_dist(rng), rake_span.data());
    pivot_t<DataType, IndexType> pivot3(pivot_dist(rng), rake_span.data());
    pivot_t<DataType, IndexType> median = std::max(
      std::min(pivot1, pivot2),
      std::min(
        std::max(pivot1, pivot2),
        pivot3
      )
    );
    pivot_vals[i] = median.val;
    // swap the median to the back of the rake
    std::swap(rake_span[median.idx], rake_span.back());
    gather_lo_idxs[i] = i * rake_size;
    gather_hi_idxs[i] = last_idx;
  }
  
  auto rake_indices_vec        = tsl::custom_sequence<IndexSimdStyle> indices(0, rake_size);
  auto const rake_increase_vec = tsl::set1<IndexSimdStyle>(IndexSimdStyle::lane_count_v);
  auto const pivots_vec        = tsl::load<DataSimdStyle, false>(pivot_vals.data());

  for (std::size_t i = 0; i < rake_size; ++i) {
    auto const data_vec = tsl::gather<DataSimdStyle, false, >(data, rake_indices_vec);
  }


}


int main() {
  std::mt19937 rng(std::random_device{}());

  return 0;
}
