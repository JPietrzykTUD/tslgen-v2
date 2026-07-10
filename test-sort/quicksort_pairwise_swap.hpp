#pragma once

#include <algorithm>
#include <cstdint>
#include <cstddef>
#include <random>
#include <utility>



#include <tsl.hpp>


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


template <class DataType = std::uint32_t, class IndexType = std::size_t>
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
  enum class partition_mode {
    LESS_THAN_PIVOT,
    EQUAL_TO_PIVOT
  };
  std::mt19937_64 rng;
 public:
  TslPairWiseSwapQuickSorter() : rng(std::random_device{}()) {}
  explicit TslPairWiseSwapQuickSorter(std::uint64_t seed) : rng(seed) {}
 private:
  pivot_t get_pivot(DataType * data, std::size_t count) {
    std::uniform_int_distribution<IndexType> pivot_dist(0, count - 1);
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
    std::swap(data[median.idx], data[count - 1]);
    return median;
  }

  template <class DataSimdStyle, partition_mode PartitionMode>
  auto quicksort_partition(
    DataType * left_ptr,
    DataType * right_ptr,
    typename tsl::reg_param<DataSimdStyle>::type pivot_vec,
    DataType pivot_value
  ) -> DataType * {
    typename DataSimdStyle::register_type data_left_vec, data_right_vec;
    typename DataSimdStyle::mask_type bad_lanes_l_mask = tsl::mask_false<DataSimdStyle>();
    typename DataSimdStyle::mask_type bad_lanes_r_mask = tsl::mask_false<DataSimdStyle>();
    std::size_t bad_lanes_l_count = 0;
    std::size_t bad_lanes_r_count = 0;
    advance_state advance = advance_state::BOTH;

    DataType * const pivot_ptr = right_ptr - 1;
    DataType * scalar_end = pivot_ptr;
    auto constexpr lane_count = DataSimdStyle::lane_count_v;

    if (static_cast<std::size_t>(pivot_ptr - left_ptr) >= (2 * lane_count)) {
      right_ptr = pivot_ptr - lane_count;

      while ((right_ptr - left_ptr) >= static_cast<std::ptrdiff_t>(lane_count)) {

        if (advance == advance_state::LEFT || advance == advance_state::BOTH) {
          // load data from the left of the partition
          data_left_vec = tsl::load<DataSimdStyle, false>(left_ptr);
          if constexpr (PartitionMode == partition_mode::LESS_THAN_PIVOT) {
            bad_lanes_l_mask = tsl::greater_than_or_equal<DataSimdStyle>(data_left_vec, pivot_vec);
          } else {
            bad_lanes_l_mask = tsl::greater_than<DataSimdStyle>(data_left_vec, pivot_vec);
          }
          bad_lanes_l_count = tsl::mask_population_count<DataSimdStyle>(bad_lanes_l_mask);
          if (bad_lanes_l_count == 0) {
            // left all good --> we can't overwrite something --> increase the left read pointer and continue
            left_ptr += lane_count;
            advance = advance == advance_state::BOTH ? advance_state::BOTH : advance_state::LEFT;
            continue;
          }
        }
        // at this point, we have some ill-placed elements on the left side of the partition (we may can swap from right)

        if (advance == advance_state::RIGHT || advance == advance_state::BOTH) {
          data_right_vec = tsl::load<DataSimdStyle, false>(right_ptr);
          if constexpr (PartitionMode == partition_mode::LESS_THAN_PIVOT) {
            bad_lanes_r_mask = tsl::less_than<DataSimdStyle>(data_right_vec, pivot_vec);
          } else {
            bad_lanes_r_mask = tsl::equal<DataSimdStyle>(data_right_vec, pivot_vec);
          }
          bad_lanes_r_count = tsl::mask_population_count<DataSimdStyle>(bad_lanes_r_mask);
          if (bad_lanes_r_count == 0) {
            // right all good --> we can't overwrite something --> decrease the right read pointer and continue
            right_ptr -= lane_count;
            advance = advance_state::RIGHT;
            continue;
          }
        }
        // at this point, we have some ill-placed elements on the right side of the partition AND on the left side of the partition => WE SWAP

        auto const compact_bad_l_vec      = tsl::compress<DataSimdStyle>(bad_lanes_l_mask, data_left_vec);
        auto const compact_good_l_vec     = tsl::compress<DataSimdStyle>(tsl::mask_binary_not<DataSimdStyle>(bad_lanes_l_mask), data_left_vec);
        auto const compact_bad_r_vec      = tsl::compress<DataSimdStyle>(bad_lanes_r_mask, data_right_vec);
        auto const compact_good_r_vec     = tsl::compress<DataSimdStyle>(tsl::mask_binary_not<DataSimdStyle>(bad_lanes_r_mask), data_right_vec);

        auto const swappable_lanes_count  = std::min(bad_lanes_l_count, bad_lanes_r_count);
        auto const full_mask              = tsl::to_integral<DataSimdStyle>(tsl::mask_true<DataSimdStyle>());
        auto const low_lane_mask          = [full_mask](std::size_t count) {
                                              return tsl::shift_right_imask<DataSimdStyle>(
                                                full_mask,
                                                lane_count - count
                                              );
                                            };
        auto const lane_mask              = [&low_lane_mask](std::size_t offset, std::size_t count) {
                                              return tsl::shift_left_imask<DataSimdStyle>(
                                                low_lane_mask(count),
                                                offset
                                              );
                                            };
        auto const swap_mask              = low_lane_mask(swappable_lanes_count);
        auto const carry_l_count          = bad_lanes_l_count - swappable_lanes_count;
        auto const carry_r_count          = bad_lanes_r_count - swappable_lanes_count;
        auto const good_l_count           = lane_count - bad_lanes_l_count;
        auto const good_r_count           = lane_count - bad_lanes_r_count;
        auto const carry_l_select_mask    = tsl::mask_binary_xor<DataSimdStyle>(swap_mask, low_lane_mask(bad_lanes_l_count));
        auto const carry_r_select_mask    = tsl::mask_binary_xor<DataSimdStyle>(swap_mask, low_lane_mask(bad_lanes_r_count));

        auto const compact_carry_l_vec    = tsl::compress<DataSimdStyle>(carry_l_select_mask, compact_bad_l_vec);
        auto const compact_carry_r_vec    = tsl::compress<DataSimdStyle>(carry_r_select_mask, compact_bad_r_vec);

        auto const left_good_mask         = lane_mask(swappable_lanes_count, good_l_count);
        auto const carry_l_write_mask     = lane_mask(swappable_lanes_count + good_l_count, carry_l_count);
        auto const carry_r_write_mask     = low_lane_mask(carry_r_count);
        auto const right_swap_mask        = lane_mask(carry_r_count, swappable_lanes_count);
        auto const right_good_mask        = lane_mask(carry_r_count + swappable_lanes_count, good_r_count);
        auto left_write_vec               = compact_bad_r_vec;
        left_write_vec                    = tsl::expand<DataSimdStyle>(
                                              left_good_mask,
                                              left_write_vec,
                                              compact_good_l_vec
                                            );
        left_write_vec                    = tsl::expand<DataSimdStyle>(
                                              carry_l_write_mask,
                                              left_write_vec,
                                              compact_carry_l_vec
                                            );
        auto right_write_vec              = compact_carry_r_vec;
        right_write_vec                   = tsl::expand<DataSimdStyle>(
                                              right_swap_mask,
                                              right_write_vec,
                                              compact_bad_l_vec
                                            );
        right_write_vec                   = tsl::expand<DataSimdStyle>(
                                              right_good_mask,
                                              right_write_vec,
                                              compact_good_r_vec
                                            );
        tsl::store<DataSimdStyle, false>(left_ptr, left_write_vec);
        tsl::store<DataSimdStyle, false>(right_ptr, right_write_vec);

        right_ptr -= swappable_lanes_count + (lane_count - bad_lanes_r_count);
        left_ptr += swappable_lanes_count + (lane_count - bad_lanes_l_count);
        advance = advance_state::BOTH;
      }
      scalar_end = right_ptr + lane_count;
    }

    auto const left_value_is_good = [pivot_value](DataType value) {
      if constexpr (PartitionMode == partition_mode::LESS_THAN_PIVOT) {
        return value < pivot_value;
      } else {
        return value == pivot_value;
      }
    };
    auto const right_value_is_good = [pivot_value](DataType value) {
      if constexpr (PartitionMode == partition_mode::LESS_THAN_PIVOT) {
        return value >= pivot_value;
      } else {
        return value > pivot_value;
      }
    };

    while (left_ptr < scalar_end) {
      while (left_ptr < scalar_end && left_value_is_good(*left_ptr)) {
        ++left_ptr;
      }
      while (left_ptr < scalar_end && right_value_is_good(*(scalar_end - 1))) {
        --scalar_end;
      }
      if (left_ptr < scalar_end) {
        std::swap(*left_ptr, *(scalar_end - 1));
        ++left_ptr;
        --scalar_end;
      }
    }
    return left_ptr;
  }

  void insertion_sort(DataType * data, std::size_t count) {
    for (std::size_t i = 1; i < count; ++i) {
      auto value = data[i];
      std::size_t j = i;
      while (j > 0 && value < data[j - 1]) {
        data[j] = data[j - 1];
        --j;
      }
      data[j] = value;
    }
  }

 public:
  void operator()(DataType * data, std::size_t count) {
    if (count < 2) {
      return;
    }
    using DataSimdStyle = tsl::dataparallel::simd_for_t<tsl::dataparallel::native, DataType>;
    if (count <= (2 * DataSimdStyle::lane_count_v)) {
      insertion_sort(data, count);
      return;
    }

    auto const pivot = get_pivot(data, count);
    auto const pivot_vec = tsl::set1<DataSimdStyle>(pivot.val);
    auto * less_end = quicksort_partition<DataSimdStyle, partition_mode::LESS_THAN_PIVOT>(
      data,
      data + count,
      pivot_vec,
      pivot.val
    );
    auto * equal_end = quicksort_partition<DataSimdStyle, partition_mode::EQUAL_TO_PIVOT>(
      less_end,
      data + count,
      pivot_vec,
      pivot.val
    );

    std::swap(*equal_end, data[count - 1]);
    (*this)(data, static_cast<std::size_t>(less_end - data));
    (*this)(equal_end + 1, static_cast<std::size_t>((data + count) - (equal_end + 1)));
  }
};


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
