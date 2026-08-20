#pragma once

#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <cstddef>
#include <random>
#include <utility>



#include <tsl.hpp>
#include "bitonic_sort.hpp"
#include "sort_helpers.hpp"


struct TslPairWiseSwapQuickSortPartitionTrace {
  std::uint64_t calls = 0;
  std::uint64_t input_elements = 0;
  std::uint64_t elapsed_ns = 0;
  std::uint64_t vectorized_calls = 0;
  std::uint64_t vector_iterations = 0;
  std::uint64_t left_loads = 0;
  std::uint64_t right_loads = 0;
  std::uint64_t left_all_good = 0;
  std::uint64_t right_all_good = 0;
  std::uint64_t swap_iterations = 0;
  std::uint64_t swappable_lanes = 0;
  std::uint64_t good_left_lanes = 0;
  std::uint64_t good_right_lanes = 0;
  std::uint64_t carry_left_lanes = 0;
  std::uint64_t carry_right_lanes = 0;
  std::uint64_t left_progress_elements = 0;
  std::uint64_t right_progress_elements = 0;
  std::uint64_t scalar_span_elements = 0;
  std::uint64_t scalar_left_steps = 0;
  std::uint64_t scalar_right_steps = 0;
  std::uint64_t scalar_swaps = 0;
  std::array<std::uint64_t, 65> left_bad_lane_histogram{};
  std::array<std::uint64_t, 65> right_bad_lane_histogram{};
};

struct TslPairWiseSwapQuickSortTrace {
  std::uint64_t sort_calls = 0;
  std::uint64_t trivial_calls = 0;
  std::uint64_t max_depth = 0;
  std::uint64_t max_sort_elements = 0;
  std::uint64_t leaf_sort_calls = 0;
  std::uint64_t leaf_sort_elements = 0;
  std::uint64_t leaf_sort_ns = 0;
  std::uint64_t pivot_calls = 0;
  std::uint64_t pivot_elements = 0;
  std::uint64_t pivot_ns = 0;
  TslPairWiseSwapQuickSortPartitionTrace less_than_pivot;
  TslPairWiseSwapQuickSortPartitionTrace equal_to_pivot;
};

template <class DataType = std::uint32_t, class IndexType = std::size_t>
class TslPairWiseSwapQuickSorter {
 private:
  enum class advance_state {
    LEFT,
    RIGHT,
    BOTH
  };
  enum class partition_mode {
    LESS_THAN_PIVOT,
    EQUAL_TO_PIVOT
  };
  TslPivotRng rng;
 public:
  TslPairWiseSwapQuickSorter() : rng(std::random_device{}()) {}
  explicit TslPairWiseSwapQuickSorter(std::uint64_t seed) : rng(seed) {}
 private:
  static auto elapsed_nanoseconds(
    std::chrono::steady_clock::time_point start,
    std::chrono::steady_clock::time_point stop
  ) -> std::uint64_t {
    return static_cast<std::uint64_t>(
      std::chrono::duration_cast<std::chrono::nanoseconds>(stop - start).count()
    );
  }

  static void record_lane_histogram(std::array<std::uint64_t, 65> & histogram, std::size_t lane_count) {
    ++histogram[std::min<std::size_t>(lane_count, histogram.size() - 1)];
  }

  template <partition_mode PartitionMode>
  static auto partition_trace(TslPairWiseSwapQuickSortTrace & trace) -> TslPairWiseSwapQuickSortPartitionTrace & {
    if constexpr (PartitionMode == partition_mode::LESS_THAN_PIVOT) {
      return trace.less_than_pivot;
    } else {
      return trace.equal_to_pivot;
    }
  }

  // Moves the chosen element to data[count - 1], where both partition modes
  // expect it, and returns its value. The rule lives in sort_helpers.hpp.
  auto get_pivot(DataType * data, std::size_t count) -> DataType {
    auto const pivot_index = tsl_pivot_index_of(data, count, rng.next());
    std::swap(data[pivot_index], data[count - 1]);
    return data[count - 1];
  }

  template <bool TraceEnabled>
  auto get_pivot_for_sort(DataType * data, std::size_t count, TslPairWiseSwapQuickSortTrace * trace) -> DataType {
    if constexpr (TraceEnabled) {
      ++trace->pivot_calls;
      trace->pivot_elements += count;
      auto const pivot_start = std::chrono::steady_clock::now();
      auto const pivot = get_pivot(data, count);
      trace->pivot_ns += elapsed_nanoseconds(pivot_start, std::chrono::steady_clock::now());
      return pivot;
    } else {
      return get_pivot(data, count);
    }
  }

  template <class DataSimdStyle>
  static auto low_lane_mask(std::size_t count) {
    auto constexpr lane_count = DataSimdStyle::lane_count_v;
    auto const full_mask = tsl::to_integral<DataSimdStyle>(tsl::mask_true<DataSimdStyle>());
    return tsl::shift_right_imask<DataSimdStyle>(
      full_mask,
      lane_count - count
    );
  }

  template <class DataSimdStyle>
  static auto lane_mask(std::size_t offset, std::size_t count) {
    return tsl::shift_left_imask<DataSimdStyle>(
      low_lane_mask<DataSimdStyle>(count),
      offset
    );
  }

  template <class DataSimdStyle>
  static auto expand_three_compacted_groups(
    typename tsl::reg_param<DataSimdStyle>::type first_vec,
    std::size_t first_count,
    typename tsl::reg_param<DataSimdStyle>::type second_vec,
    std::size_t second_count,
    typename tsl::reg_param<DataSimdStyle>::type third_vec,
    std::size_t third_count
  ) -> typename DataSimdStyle::register_type {
    auto result = first_vec;
    result = tsl::expand<DataSimdStyle>(
      lane_mask<DataSimdStyle>(first_count, second_count),
      result,
      second_vec
    );
    result = tsl::expand<DataSimdStyle>(
      lane_mask<DataSimdStyle>(first_count + second_count, third_count),
      result,
      third_vec
    );
    return result;
  }

  template <class DataSimdStyle, partition_mode PartitionMode, bool TraceEnabled>
  auto quicksort_partition(
    DataType * left_ptr,
    DataType * right_ptr,
    typename tsl::reg_param<DataSimdStyle>::type pivot_vec,
    DataType pivot_value,
    TslPairWiseSwapQuickSortTrace * trace
  ) -> DataType * {
    std::chrono::steady_clock::time_point partition_start{};
    if constexpr (TraceEnabled) {
      auto & current_trace = partition_trace<PartitionMode>(*trace);
      ++current_trace.calls;
      current_trace.input_elements += static_cast<std::uint64_t>(right_ptr - left_ptr);
      partition_start = std::chrono::steady_clock::now();
    }

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
      if constexpr (TraceEnabled) {
        ++partition_trace<PartitionMode>(*trace).vectorized_calls;
      }
      right_ptr = pivot_ptr - lane_count;

      while ((right_ptr - left_ptr) >= static_cast<std::ptrdiff_t>(lane_count)) {
        if constexpr (TraceEnabled) {
          ++partition_trace<PartitionMode>(*trace).vector_iterations;
        }

        if (advance == advance_state::LEFT || advance == advance_state::BOTH) {
          // load data from the left of the partition
          data_left_vec = tsl::load<DataSimdStyle, false>(left_ptr);
          if constexpr (TraceEnabled) {
            ++partition_trace<PartitionMode>(*trace).left_loads;
          }
          if constexpr (PartitionMode == partition_mode::LESS_THAN_PIVOT) {
            bad_lanes_l_mask = tsl::greater_than_or_equal<DataSimdStyle>(data_left_vec, pivot_vec);
          } else {
            bad_lanes_l_mask = tsl::greater_than<DataSimdStyle>(data_left_vec, pivot_vec);
          }
          bad_lanes_l_count = tsl::mask_population_count<DataSimdStyle>(bad_lanes_l_mask);
          if constexpr (TraceEnabled) {
            record_lane_histogram(partition_trace<PartitionMode>(*trace).left_bad_lane_histogram, bad_lanes_l_count);
          }
          if (bad_lanes_l_count == 0) {
            // left all good --> we can't overwrite something --> increase the left read pointer and continue
            left_ptr += lane_count;
            if constexpr (TraceEnabled) {
              auto & current_trace = partition_trace<PartitionMode>(*trace);
              ++current_trace.left_all_good;
              current_trace.left_progress_elements += lane_count;
            }
            advance = advance == advance_state::BOTH ? advance_state::BOTH : advance_state::LEFT;
            continue;
          }
        }
        // at this point, we have some ill-placed elements on the left side of the partition (we may can swap from right)

        if (advance == advance_state::RIGHT || advance == advance_state::BOTH) {
          data_right_vec = tsl::load<DataSimdStyle, false>(right_ptr);
          if constexpr (TraceEnabled) {
            ++partition_trace<PartitionMode>(*trace).right_loads;
          }
          if constexpr (PartitionMode == partition_mode::LESS_THAN_PIVOT) {
            bad_lanes_r_mask = tsl::less_than<DataSimdStyle>(data_right_vec, pivot_vec);
          } else {
            bad_lanes_r_mask = tsl::equal<DataSimdStyle>(data_right_vec, pivot_vec);
          }
          bad_lanes_r_count = tsl::mask_population_count<DataSimdStyle>(bad_lanes_r_mask);
          if constexpr (TraceEnabled) {
            record_lane_histogram(partition_trace<PartitionMode>(*trace).right_bad_lane_histogram, bad_lanes_r_count);
          }
          if (bad_lanes_r_count == 0) {
            // right all good --> we can't overwrite something --> decrease the right read pointer and continue
            right_ptr -= lane_count;
            if constexpr (TraceEnabled) {
              auto & current_trace = partition_trace<PartitionMode>(*trace);
              ++current_trace.right_all_good;
              current_trace.right_progress_elements += lane_count;
            }
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
        auto const swap_mask              = low_lane_mask<DataSimdStyle>(swappable_lanes_count);
        auto const carry_l_count          = bad_lanes_l_count - swappable_lanes_count;
        auto const carry_r_count          = bad_lanes_r_count - swappable_lanes_count;
        auto const good_l_count           = lane_count - bad_lanes_l_count;
        auto const good_r_count           = lane_count - bad_lanes_r_count;
        if constexpr (TraceEnabled) {
          auto & current_trace = partition_trace<PartitionMode>(*trace);
          ++current_trace.swap_iterations;
          current_trace.swappable_lanes += swappable_lanes_count;
          current_trace.good_left_lanes += good_l_count;
          current_trace.good_right_lanes += good_r_count;
          current_trace.carry_left_lanes += carry_l_count;
          current_trace.carry_right_lanes += carry_r_count;
          current_trace.left_progress_elements += swappable_lanes_count + good_l_count;
          current_trace.right_progress_elements += swappable_lanes_count + good_r_count;
        }
        auto const carry_l_select_mask    = tsl::mask_binary_xor<DataSimdStyle>(swap_mask, low_lane_mask<DataSimdStyle>(bad_lanes_l_count));
        auto const carry_r_select_mask    = tsl::mask_binary_xor<DataSimdStyle>(swap_mask, low_lane_mask<DataSimdStyle>(bad_lanes_r_count));

        auto const compact_carry_l_vec    = tsl::compress<DataSimdStyle>(carry_l_select_mask, compact_bad_l_vec);
        auto const compact_carry_r_vec    = tsl::compress<DataSimdStyle>(carry_r_select_mask, compact_bad_r_vec);

        auto const left_write_vec         = expand_three_compacted_groups<DataSimdStyle>(
                                              compact_bad_r_vec,
                                              swappable_lanes_count,
                                              compact_good_l_vec,
                                              good_l_count,
                                              compact_carry_l_vec,
                                              carry_l_count
                                            );
        auto const right_write_vec        = expand_three_compacted_groups<DataSimdStyle>(
                                              compact_carry_r_vec,
                                              carry_r_count,
                                              compact_bad_l_vec,
                                              swappable_lanes_count,
                                              compact_good_r_vec,
                                              good_r_count
                                            );
        tsl::store<DataSimdStyle, false>(left_ptr, left_write_vec);
        tsl::store<DataSimdStyle, false>(right_ptr, right_write_vec);

        right_ptr -= swappable_lanes_count + (lane_count - bad_lanes_r_count);
        left_ptr += swappable_lanes_count + (lane_count - bad_lanes_l_count);
        advance = advance_state::BOTH;
      }
      scalar_end = right_ptr + lane_count;
    }

    if constexpr (TraceEnabled) {
      partition_trace<PartitionMode>(*trace).scalar_span_elements += static_cast<std::uint64_t>(scalar_end - left_ptr);
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
        if constexpr (TraceEnabled) {
          ++partition_trace<PartitionMode>(*trace).scalar_left_steps;
        }
      }
      while (left_ptr < scalar_end && right_value_is_good(*(scalar_end - 1))) {
        --scalar_end;
        if constexpr (TraceEnabled) {
          ++partition_trace<PartitionMode>(*trace).scalar_right_steps;
        }
      }
      if (left_ptr < scalar_end) {
        std::swap(*left_ptr, *(scalar_end - 1));
        ++left_ptr;
        --scalar_end;
        if constexpr (TraceEnabled) {
          ++partition_trace<PartitionMode>(*trace).scalar_swaps;
        }
      }
    }
    if constexpr (TraceEnabled) {
      partition_trace<PartitionMode>(*trace).elapsed_ns += elapsed_nanoseconds(
        partition_start,
        std::chrono::steady_clock::now()
      );
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
  void bitonic_merge_sort(DataType * data, std::size_t count) {
    avx512_sort::sort_u32_up_to_256(
        data,
        count
    );
  }

  template <bool TraceEnabled>
  void sort_impl(DataType * data, std::size_t count, TslPairWiseSwapQuickSortTrace * trace, std::size_t depth) {
    if constexpr (TraceEnabled) {
      ++trace->sort_calls;
      trace->max_depth = std::max<std::uint64_t>(trace->max_depth, static_cast<std::uint64_t>(depth));
      trace->max_sort_elements = std::max<std::uint64_t>(trace->max_sort_elements, static_cast<std::uint64_t>(count));
    }
    if (count < 2) {
      if constexpr (TraceEnabled) {
        ++trace->trivial_calls;
      }
      return;
    }
    using DataSimdStyle = tsl::dataparallel::simd_for_t<tsl::dataparallel::native, DataType>;
    auto constexpr insertion_sort_threshold = std::max<std::size_t>(
      256,
      2 * DataSimdStyle::lane_count_v
    );
    if (count <= insertion_sort_threshold) {
      if constexpr (TraceEnabled) {
        ++trace->leaf_sort_calls;
        trace->leaf_sort_elements += count;
        auto const leaf_start = std::chrono::steady_clock::now();
        bitonic_merge_sort(data, count);
        trace->leaf_sort_ns += elapsed_nanoseconds(leaf_start, std::chrono::steady_clock::now());
      } else {
        bitonic_merge_sort(data, count);
      }
      return;
    }

    auto const pivot = get_pivot_for_sort<TraceEnabled>(data, count, trace);
    auto const pivot_vec = tsl::set1<DataSimdStyle>(pivot);
    auto * less_end = quicksort_partition<DataSimdStyle, partition_mode::LESS_THAN_PIVOT, TraceEnabled>(
      data,
      data + count,
      pivot_vec,
      pivot,
      trace
    );
    auto * equal_end = quicksort_partition<DataSimdStyle, partition_mode::EQUAL_TO_PIVOT, TraceEnabled>(
      less_end,
      data + count,
      pivot_vec,
      pivot,
      trace
    );

    std::swap(*equal_end, data[count - 1]);
    sort_impl<TraceEnabled>(data, static_cast<std::size_t>(less_end - data), trace, depth + 1);
    sort_impl<TraceEnabled>(equal_end + 1, static_cast<std::size_t>((data + count) - (equal_end + 1)), trace, depth + 1);
  }

 public:
  void operator()(DataType * data, std::size_t count) {
    sort_impl<false>(data, count, nullptr, 0);
  }

  void sort_with_trace(DataType * data, std::size_t count, TslPairWiseSwapQuickSortTrace & trace) {
    sort_impl<true>(data, count, &trace, 0);
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
