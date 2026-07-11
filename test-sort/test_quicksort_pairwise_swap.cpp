#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <limits>
#include <random>
#include <utility>
#include <vector>


#include <tsl.hpp>

#include "quicksort_pairwise_swap.hpp"

using _Test_DataType = std::uint32_t;
using _Test_IndexType = std::size_t;


namespace {

auto make_ascending_case(std::size_t count) -> std::vector<_Test_DataType> {
  std::vector<_Test_DataType> data(count);
  for (std::size_t i = 0; i < count; ++i) {
    data[i] = static_cast<_Test_DataType>(i);
  }
  return data;
}

auto make_descending_case(std::size_t count) -> std::vector<_Test_DataType> {
  std::vector<_Test_DataType> data(count);
  for (std::size_t i = 0; i < count; ++i) {
    data[i] = static_cast<_Test_DataType>(count - i);
  }
  return data;
}

auto make_repeating_case(std::size_t count, _Test_DataType period) -> std::vector<_Test_DataType> {
  std::vector<_Test_DataType> data(count);
  for (std::size_t i = 0; i < count; ++i) {
    data[i] = static_cast<_Test_DataType>(i % period);
  }
  return data;
}

auto make_random_case(std::size_t count, std::uint64_t seed) -> std::vector<_Test_DataType> {
  std::mt19937_64 rng(seed);
  std::vector<_Test_DataType> data(count);
  std::generate(data.begin(), data.end(), [&rng]() {
    return static_cast<_Test_DataType>(rng());
  });
  return data;
}

auto verify_sort_case(std::vector<_Test_DataType> data, char const * case_name) -> bool {
  auto const original_size = data.size();
  auto expected = data;

  TslPairWiseSwapQuickSorter<_Test_DataType, _Test_IndexType> sorter(0x5eededULL);
  sorter(data.data(), data.size());

  std::sort(expected.begin(), expected.end());
  for (std::size_t i = 0; i < data.size(); ++i) {
    if (data[i] != expected[i]) {
      std::cerr << "Mismatch in " << case_name << " (size " << original_size << ") at index " << i
                << ": " << data[i] << " != " << expected[i] << std::endl;
      return false;
    }
  }
  return true;
}

} // namespace

int main() {
  using DataSimdStyle = tsl::dataparallel::simd_for_t<tsl::dataparallel::native, _Test_DataType>;
  auto constexpr lane_count = DataSimdStyle::lane_count_v;
  auto constexpr max_value = std::numeric_limits<_Test_DataType>::max();
  auto constexpr min_value = std::numeric_limits<_Test_DataType>::min();

  bool all_passed = true;
  std::size_t tests_run = 0;
  auto run_case = [&all_passed, &tests_run](char const * case_name, std::vector<_Test_DataType> data) {
    ++tests_run;
    all_passed = verify_sort_case(std::move(data), case_name) && all_passed;
  };

  run_case("empty", {});
  run_case("single", {42});
  run_case("pair sorted", {1, 2});
  run_case("pair reversed", {2, 1});
  run_case("pair equal", {7, 7});
  run_case("small mixed", {5, 1, 4, 1, 3, 9, 2, 6});
  run_case("all equal", std::vector<_Test_DataType>(2 * lane_count + 3, 17));
  run_case("all equal large", std::vector<_Test_DataType>((64 * lane_count) + 17, 17));
  run_case("two value duplicates", make_repeating_case((64 * lane_count) + 13, 2));
  run_case("three value duplicates", make_repeating_case((64 * lane_count) + 29, 3));
  run_case("extreme values", {max_value, min_value, 1, max_value - 1, min_value, 42, max_value});
  run_case("alternating extremes", {max_value, min_value, max_value, min_value, 9, 9, max_value, min_value});

  std::array<std::size_t, 8> const boundary_sizes{
    lane_count - 1,
    lane_count,
    lane_count + 1,
    (2 * lane_count) - 1,
    2 * lane_count,
    (2 * lane_count) + 1,
    (3 * lane_count) + 1,
    1000
  };

  for (auto const size : boundary_sizes) {
    run_case("ascending boundary", make_ascending_case(size));
    run_case("descending boundary", make_descending_case(size));
    run_case("repeating boundary", make_repeating_case(size, 5));
  }

  std::array<std::size_t, 6> const random_sizes{
    3,
    lane_count + 2,
    (2 * lane_count) + 5,
    (8 * lane_count) + 3,
    1000,
    4096
  };

  std::uint64_t seed = 0x12345678ULL;
  for (auto const size : random_sizes) {
    run_case("random", make_random_case(size, seed));
    seed += 0x9e3779b97f4a7c15ULL;
  }

  if (!all_passed) {
    return 1;
  }

  std::cout << tests_run << " sort tests passed" << std::endl;
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
