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
auto tsl_quicksort(
  DataType * data, std::size_t count, std::mt19937_64 & rng
) {
  using DataSimdStyle = tsl::dataparallel::simd_for_t<tsl::dataparallel::native, DataType>;
  // get pivot
  pivot_t<DataType, IndexType> pivot1(pivot_dist(rng), data);
  pivot_t<DataType, IndexType> pivot2(pivot_dist(rng), data);
  pivot_t<DataType, IndexType> pivot3(pivot_dist(rng), data);
  pivot_t<DataType, IndexType> median = std::max(
    std::min(pivot1, pivot2),
    std::min(
      std::max(pivot1, pivot2),
      pivot3
    )
  );
  std::swap(data[median.idx], data[count - 1]);
  auto const pivot_vec = tsl::set1<DataSimdStyle>(median.val);

  DataType * left_read_ptr = data;
  DataType * left_write_ptr = left_read_ptr;
  // get the last full simd register of the data (excluding the pivot)
  DataType * right_read_ptr = (data + count - 2) - (DataSimdStyle::lane_count_v);
  DataType * right_write_ptr = right_read_ptr;

  typename DataSimdStyle::register_type data_left_vec, data_right_vec;
  typename DataSimdStyle::mask_type left_illplaced_mask = tsl::mask_false<DataSimdStyle>();
  typename DataSimdStyle::mask_type right_illplaced_mask = tsl::mask_false<DataSimdStyle>();
  size_t left_illplaced_count = 0;
  size_t right_illplaced_count = 0;
  enum class advance_state {
    LEFT,
    RIGHT,
    BOTH
  };

  advance_state advance = advance_state::LEFT;

  while (left_read_ptr < right_read_ptr) {

    if (advance == advance_state::LEFT || advance == advance_state::BOTH) {
      // load data from the left of the partition
      data_left_vec = tsl::load<DataSimdStyle, false>(left_read_ptr);
      left_illplaced_mask = tsl::greater_than_or_equal<DataSimdStyle>(data_left_vec, pivot_vec);
      left_illplaced_count = tsl::mask_population_count<DataSimdStyle>(left_illplaced_mask);
      if (left_illplaced_count == 0) {
        // left all good --> we can't overwrite something --> increase the left read pointer and continue
        left_read_ptr += DataSimdStyle::lane_count_v;
        advance = advance_state::LEFT;
        continue;
      }
    }  
    // at this point, we have some ill-placed elements on the left side of the partition (we may can swap from right)

    if (advance == advance_state::RIGHT || advance == advance_state::BOTH) {
      data_right_vec = tsl::load<DataSimdStyle, false>(right_read_ptr);
      right_illplaced_mask = tsl::less_than<DataSimdStyle>(data_right_vec, pivot_vec);
      right_illplaced_count = tsl::mask_population_count<DataSimdStyle>(right_illplaced_mask);
      if (right_illplaced_count == 0) {
        // right all good --> we can't overwrite something --> decrease the right read pointer and continue
        right_read_ptr -= DataSimdStyle::lane_count_v;
        advance = advance_state::RIGHT;
        continue;
      }
    }
    // at this point, we have some ill-placed elements on the right side of the partition AND on the left side of the partition => WE SWAP
    
    // 1. get the minimum number of ill-placed elements on both sides
    auto const min_illplaced_count = std::min(left_illplaced_count, right_illplaced_count);
    // 2. compress right ill-placed elements to the front of the register (as they will overwrite the left part)
    auto const right_illplaced_compact_vec = tsl::compress<DataSimdStyle>(right_illplaced_mask, data_right_vec);

    auto const left_illplaced_compact_vec = tsl::compress<DataSimdStyle>(left_illplaced_mask, data_left_vec);
    
    // 3. create a mask for the low min_illplaced_count bits set to 1 (N > 0, thus not UB)
    // for 3 elements that would be 0b00000111
    auto const compact_imask = 
      tsl::shift_right_imask<DataSimdStyle>(
        tsl::to_integral<DataSimdStyle>(tsl::mask_true<DataSimdStyle>()),
        DataSimdStyle::lane_count_v - min_illplaced_count
      );
    // for 3 elements that would be 0b11111000
    auto const expand_imask = ~compact_imask;
    
    // 4. create a mask for the high min_illplaced_count bits set to 1
    // for 3 elements that would be 0b11100000
    auto const left_expand_imask = 
      tsl::shift_left_imask<DataSimdStyle>(
        compact_imask, 
        DataSimdStyle::lane_count_v - min_illplaced_count
      );
    
    // for 3 elements that would be 0b00011111
    auto const left_compact_imask = ~left_expand_imask;

    // LEFT
    // prepare the left vector for storing
    // compact the ill-placed elements to the front
    auto const tmp_illplaced_left_vec = tsl::compress<DataSimdStyle>(left_illplaced_mask, data_left_vec);
    auto const tmp_goodplaced_left_vec = tsl::compress<DataSimdStyle>(tsl::mask_binary_not<DataSimdStyle>(left_illplaced_mask), data_left_vec);
    // move the tmp_illplaced_left_vec valid lanes to the back of the vector
    auto const updated_illplaced_left_vec = tsl::expand<DataSimdStyle>(left_expand_imask, tmp_illplaced_left_vec);
    // blend the vectors
    auto const updated_left_vec = tsl::binary_or<DataSimdStyle>(updated_illplaced_left_vec, tmp_goodplaced_left_vec);

    // RIGHT
    // prepare the right vector for storing
    // compact the ill-placed elements to the front
    auto const tmp_illplaced_right_vec = tsl::compress<DataSimdStyle>(right_illplaced_mask, data_right_vec);
    
    
  }

}


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
