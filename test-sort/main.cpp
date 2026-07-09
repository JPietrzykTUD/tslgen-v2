#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <random>
#include <vector>


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
class TslPairWiseSwapQuickSorter {
 private:
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
  enum class advance_state {
    LEFT,
    RIGHT,
    BOTH
  };
  std::mt19937_64 rng;
 public:
  TslPairWiseSwapQuickSorter() : rng(std::random_device{}()) {}
 private:
  pivot_t<DataType, IndexType> get_pivot(DataType * data, std::size_t count) {
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
    return median;
  }

  template <class DataSimdStyle>
  auto quicksort_partition(
    DataType * left_ptr,
    DataType * right_ptr,
    typename tsl::reg_param<Vec>::type pivot_vec
  ) -> std::pair<DataType *, DataType *> {
    typename DataSimdStyle::register_type data_left_vec, data_right_vec;
    typename DataSimdStyle::mask_type bad_lanes_l_mask = tsl::mask_false<DataSimdStyle>();
    typename DataSimdStyle::mask_type bad_lanes_r_mask = tsl::mask_false<DataSimdStyle>();
    size_t bad_lanes_l_count = 0;
    size_t bad_lanes_r_count = 0;
    advance_state advance = advance_state::LEFT;
    
    while ((left_ptr + DataSimdStyle::lane_count_v) <= right_ptr) {

      if (advance == advance_state::LEFT || advance == advance_state::BOTH) {
        // load data from the left of the partition
        data_left_vec = tsl::load<DataSimdStyle, false>(left_ptr);
        bad_lanes_l_mask = tsl::greater_than_or_equal<DataSimdStyle>(data_left_vec, pivot_vec);
        bad_lanes_l_count = tsl::mask_population_count<DataSimdStyle>(bad_lanes_l_mask);
        if (bad_lanes_l_count == 0) {
          // left all good --> we can't overwrite something --> increase the left read pointer and continue
          left_ptr += DataSimdStyle::lane_count_v;
          advance = advance_state::LEFT;
          continue;
        }
      }  
      // at this point, we have some ill-placed elements on the left side of the partition (we may can swap from right)

      if (advance == advance_state::RIGHT || advance == advance_state::BOTH) {
        data_right_vec = tsl::load<DataSimdStyle, false>(right_ptr);
        bad_lanes_r_mask = tsl::less_than<DataSimdStyle>(data_right_vec, pivot_vec);
        bad_lanes_r_count = tsl::mask_population_count<DataSimdStyle>(bad_lanes_r_mask);
        if (bad_lanes_r_count == 0) {
          // right all good --> we can't overwrite something --> decrease the right read pointer and continue
          right_ptr -= DataSimdStyle::lane_count_v;
          advance = advance_state::RIGHT;
          continue;
        }
      }
      // at this point, we have some ill-placed elements on the right side of the partition AND on the left side of the partition => WE SWAP
      
      auto const compact_bad_l_vec      = compress<DataSimdStyle>(bad_lanes_l_mask, data_left_vec);
      auto const compact_good_l_vec     = compress<DataSimdStyle>(tsl::mask_binary_not<DataSimdStyle>(bad_lanes_l_mask), data_left_vec);
      auto const compact_bad_r_vec      = compress<DataSimdStyle>(bad_lanes_r_mask, data_right_vec);
      auto const compact_good_r_vec     = compress<DataSimdStyle>(tsl::mask_binary_not<DataSimdStyle>(bad_lanes_r_mask), data_right_vec);

      auto const swappable_lanes_count  = std::min(bad_lanes_l_count, bad_lanes_r_count);
      auto const swap_mask              = tsl::shift_right_imask<DataSimdStyle>(
                                            tsl::to_integral<DataSimdStyle>(tsl::mask_true<DataSimdStyle>()),
                                            DataSimdStyle::lane_count_v - swappable_lanes_count
                                          );
      auto const swap_tmp_l_mask        = tsl::shift_right_imask<DataSimdStyle>(
                                            tsl::to_integral<DataSimdStyle>(tsl::mask_true<DataSimdStyle>()),
                                            DataSimdStyle::lane_count_v - bad_lanes_l_count
                                          );
      auto const carry_l_mask           = tsl::mask_binary_xor<DataSimdStyle>(swap_mask, swap_tmp_l_mask);
      auto const swap_tmp_r_mask        = tsl::shift_right_imask<DataSimdStyle>(
                                            tsl::to_integral<DataSimdStyle>(tsl::mask_true<DataSimdStyle>()),
                                            DataSimdStyle::lane_count_v - bad_lanes_r_count
                                          );
      auto const carry_r_mask           = tsl::mask_binary_xor<DataSimdStyle>(swap_mask, swap_tmp_r_mask);

      auto const compact_carry_l_vec    = tsl::compress<DataSimdStyle>(carry_l_mask, compact_bad_l_vec);
      auto const compact_carry_r_vec    = tsl::compress<DataSimdStyle>(carry_r_mask, compact_bad_r_vec);
      
      auto const keep_mask              = tsl::mask_binary_not(swap_mask);

      auto const left_write_vec         = tsl::expand<DataSimdStyle>(
                                            tsl::expand<DataSimdStyle>(
                                              tsl::shift_right_imask<DataSimdStyle>(
                                                tsl::to_integral<DataSimdStyle>(keep_mask),
                                                bad_lanes_l_count - swappable_lanes_count
                                              ),
                                              compact_good_l_vec,
                                              compact_carry_l_vec
                                            ),
                                            keep_mask,
                                            compact_bad_r_vec      
                                          );
      auto const right_write_vec        = tsl::expand<DataSimdStyle>(
                                            tsl::expand<DataSimdStyle>(
                                              tsl::shift_left_imask<DataSimdStyle>(
                                                tsl::to_integral<DataSimdStyle>(tsl::mask_true<DataSimdStyle>()),
                                                bad_lanes_r_count - swappable_lanes_count
                                              ),
                                              compact_carry_r_vec,
                                              compact_good_r_vec
                                            ),
                                            keep_mask,
                                            compact_bad_l_vec      
                                          );
      tsl::store<DataSimdStyle, false>(left_ptr, left_write_vec);
      tsl::store<DataSimdStyle, false>(right_ptr, right_write_vec);

      right_ptr -= swappable_lanes_count + (DataSimdStyle::lane_count_v - bad_lanes_r_count);
      left_ptr += swappable_lanes_count + (DataSimdStyle::lane_count_v - bad_lanes_l_count);
    }
    return std::make_pair(left_ptr, right_ptr);
  }

 public:
   void operator()(DataType * data, std::size_t count) {
    auto const pivot = get_pivot(data, count);
    using DataSimdStyle = tsl::dataparallel::simd_for_t<tsl::dataparallel::native, DataType>;
    using DataScalarStyle = tsl::dataparallel::simd_for_t<tsl::dataparallel::fixed<1>, DataType>;
    auto const pivot_vec = tsl::set1<DataSimdStyle>(pivot.val);
    auto [left_ptr, right_ptr] = quicksort_partition<DataSimdStyle>(data, data + count - 2, pivot_vec);
    if (left_ptr < right_ptr) {
      [left_ptr, right_ptr] = quicksort_partition<DataScalarStyle>(left_ptr, right_ptr, pivot.val);
    }
    (*this)(data, left_ptr - data);
    (*this)(right_ptr + 1, (data + count - 1) - (right_ptr + 1));
  }
};


int main() {
  std::mt19937_64 rng(std::random_device{}());

  // create some random data
  std::vector<_Test_DataType> data(1000);
  std::generate(data.begin(), data.end(), [&rng]() { return rng(); });
  std::vector<_Test_DataType> data_copy = data;

  TslPairWiseSwapQuickSorter<_Test_DataType, _Test_IndexType> sorter;
  sorter(data.data(), data.size());

  std::sort(data_copy.begin(), data_copy.end());

  for (std::size_t i = 0; i < data.size(); ++i) {
    if (data[i] != data_copy[i]) {
      std::cerr << "Mismatch at index " << i << ": " << data[i] << " != " << data_copy[i] << std::endl;
      return 1;
    }
  }

  return 0;
}


// template <class DataType = _Test_DataType, class IndexType = _Test_IndexType>
// auto tsl_quicksort(
//   DataType * data, std::size_t count, std::mt19937_64 & rng
// ) -> std::pair<DataType *, DataType *> {

//   TslPairWiseSwapQuickSorter<DataType, IndexType> sorter;
//   // get pivot
//   pivot_t<DataType, IndexType> pivot1(pivot_dist(rng), data);
//   pivot_t<DataType, IndexType> pivot2(pivot_dist(rng), data);
//   pivot_t<DataType, IndexType> pivot3(pivot_dist(rng), data);
//   pivot_t<DataType, IndexType> median = std::max(
//     std::min(pivot1, pivot2),
//     std::min(
//       std::max(pivot1, pivot2),
//       pivot3
//     )
//   );
//   std::swap(data[median.idx], data[count - 1]);
//   auto const pivot_vec = tsl::set1<DataSimdStyle>(median.val);

//   DataType * left_ptr = data;
//   // get the last full simd register of the data (excluding the pivot)
//   DataType * right_ptr = (data + count - 2) - (DataSimdStyle::lane_count_v);

//   typename DataSimdStyle::register_type data_left_vec, data_right_vec;
//   typename DataSimdStyle::mask_type bad_lanes_l_mask = tsl::mask_false<DataSimdStyle>();
//   typename DataSimdStyle::mask_type bad_lanes_r_mask = tsl::mask_false<DataSimdStyle>();
//   size_t bad_lanes_l_count = 0;
//   size_t bad_lanes_r_count = 0;
//   enum class advance_state {
//     LEFT,
//     RIGHT,
//     BOTH
//   };

//   advance_state advance = advance_state::LEFT;

//   while ((left_ptr + DataSimdStyle::lane_count_v) <= right_ptr) {

//     if (advance == advance_state::LEFT || advance == advance_state::BOTH) {
//       // load data from the left of the partition
//       data_left_vec = tsl::load<DataSimdStyle, false>(left_ptr);
//       bad_lanes_l_mask = tsl::greater_than_or_equal<DataSimdStyle>(data_left_vec, pivot_vec);
//       bad_lanes_l_count = tsl::mask_population_count<DataSimdStyle>(bad_lanes_l_mask);
//       if (bad_lanes_l_count == 0) {
//         // left all good --> we can't overwrite something --> increase the left read pointer and continue
//         left_ptr += DataSimdStyle::lane_count_v;
//         advance = advance_state::LEFT;
//         continue;
//       }
//     }  
//     // at this point, we have some ill-placed elements on the left side of the partition (we may can swap from right)

//     if (advance == advance_state::RIGHT || advance == advance_state::BOTH) {
//       data_right_vec = tsl::load<DataSimdStyle, false>(right_ptr);
//       bad_lanes_r_mask = tsl::less_than<DataSimdStyle>(data_right_vec, pivot_vec);
//       bad_lanes_r_count = tsl::mask_population_count<DataSimdStyle>(bad_lanes_r_mask);
//       if (bad_lanes_r_count == 0) {
//         // right all good --> we can't overwrite something --> decrease the right read pointer and continue
//         right_ptr -= DataSimdStyle::lane_count_v;
//         advance = advance_state::RIGHT;
//         continue;
//       }
//     }
//     // at this point, we have some ill-placed elements on the right side of the partition AND on the left side of the partition => WE SWAP
    
//     auto const compact_bad_l_vec      = compress<DataSimdStyle>(bad_lanes_l_mask, data_left_vec);
//     auto const compact_good_l_vec     = compress<DataSimdStyle>(tsl::mask_binary_not<DataSimdStyle>(bad_lanes_l_mask), data_left_vec);
//     auto const compact_bad_r_vec      = compress<DataSimdStyle>(bad_lanes_r_mask, data_right_vec);
//     auto const compact_good_r_vec     = compress<DataSimdStyle>(tsl::mask_binary_not<DataSimdStyle>(bad_lanes_r_mask), data_right_vec);

//     auto const swappable_lanes_count  = std::min(bad_lanes_l_count, bad_lanes_r_count);
//     auto const swap_mask              = tsl::shift_right_imask<DataSimdStyle>(
//                                           tsl::to_integral<DataSimdStyle>(tsl::mask_true<DataSimdStyle>()),
//                                           DataSimdStyle::lane_count_v - swappable_lanes_count
//                                         );
//     auto const swap_tmp_l_mask        = tsl::shift_right_imask<DataSimdStyle>(
//                                           tsl::to_integral<DataSimdStyle>(tsl::mask_true<DataSimdStyle>()),
//                                           DataSimdStyle::lane_count_v - bad_lanes_l_count
//                                         );
//     auto const carry_l_mask           = tsl::mask_binary_xor<DataSimdStyle>(swap_mask, swap_tmp_l_mask);
//     auto const swap_tmp_r_mask        = tsl::shift_right_imask<DataSimdStyle>(
//                                           tsl::to_integral<DataSimdStyle>(tsl::mask_true<DataSimdStyle>()),
//                                           DataSimdStyle::lane_count_v - bad_lanes_r_count
//                                         );
//     auto const carry_r_mask           = tsl::mask_binary_xor<DataSimdStyle>(swap_mask, swap_tmp_r_mask);

//     auto const compact_carry_l_vec    = tsl::compress<DataSimdStyle>(carry_l_mask, compact_bad_l_vec);
//     auto const compact_carry_r_vec    = tsl::compress<DataSimdStyle>(carry_r_mask, compact_bad_r_vec);
    
//     auto const keep_mask              = tsl::mask_binary_not(swap_mask);

//     auto const left_write_vec         = tsl::expand<DataSimdStyle>(
//                                           tsl::expand<DataSimdStyle>(
//                                             tsl::shift_right_imask<DataSimdStyle>(
//                                               tsl::to_integral<DataSimdStyle>(keep_mask),
//                                               bad_lanes_l_count - swappable_lanes_count
//                                             ),
//                                             compact_good_l_vec,
//                                             compact_carry_l_vec
//                                           ),
//                                           keep_mask,
//                                           compact_bad_r_vec      
//                                         );
//     auto const right_write_vec        = tsl::expand<DataSimdStyle>(
//                                           tsl::expand<DataSimdStyle>(
//                                             tsl::shift_left_imask<DataSimdStyle>(
//                                               tsl::to_integral<DataSimdStyle>(tsl::mask_true<DataSimdStyle>()),
//                                               bad_lanes_r_count - swappable_lanes_count
//                                             ),
//                                             compact_carry_r_vec,
//                                             compact_good_r_vec
//                                           ),
//                                           keep_mask,
//                                           compact_bad_l_vec      
//                                         );
//     tsl::store<DataSimdStyle, false>(left_ptr, left_write_vec);
//     tsl::store<DataSimdStyle, false>(right_ptr, right_write_vec);

//     right_ptr -= swappable_lanes_count + (DataSimdStyle::lane_count_v - bad_lanes_r_count);
//     left_ptr += swappable_lanes_count + (DataSimdStyle::lane_count_v - bad_lanes_l_count);
//   }

//   return std::make_pair(left_ptr, right_ptr);
// }
