#pragma once

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <random>
#include <type_traits>
#include <utility>

#include <tsl.hpp>

#include "cosort_network.hpp"
#include "cosort_bitonic_leaf.hpp"


enum class TslLeafKind { INSERTION, NETWORK };
enum class TslPartitionKind { TWO_WAY, THREE_WAY };


// -----------------------------------------------------------------------------
// Multi-column co-sorting quicksort (prototype).
//
// Sorts a key column and reorders a runtime number of payload columns in place
// so every column follows the key permutation. The vectorized partition reuses
// TslPartitionReplayStep: the compress/expand plan is derived from the keys once
// per swap and replayed on each payload column.
//
// Two policies select the variant:
//   PartitionKind: TWO_WAY (< | >=) or THREE_WAY (< | == | >, better on
//                  duplicates, matching the production partition).
//   LeafKind:      INSERTION (scalar co-sort, O(m) moves/element/column) or
//                  NETWORK (co-sorting bitonic leaf, SIMD replay per column).
// Median-of-three pivots and loop-on-larger recursion bound the stack depth.
// -----------------------------------------------------------------------------
template <
  class DataType = std::uint32_t,
  TslPartitionKind PartitionKind = TslPartitionKind::TWO_WAY,
  TslLeafKind LeafKind = TslLeafKind::INSERTION,
  std::size_t MaxColumns = 16,
  class SimdStyle = tsl::dataparallel::simd_for_t<tsl::dataparallel::native, DataType>
>
class TslMultiColumnQuickSorter {
  using DataSimdStyle = SimdStyle;
  static_assert(std::is_same_v<typename SimdStyle::base_type, DataType>,
                "SimdStyle::base_type must match DataType");
  using register_type = typename DataSimdStyle::register_type;
  using Partition = TslPartitionReplayStep<DataType, SimdStyle>;
  static constexpr std::size_t lane_count = DataSimdStyle::lane_count_v;
  static constexpr std::size_t compute_leaf_threshold() {
    if constexpr (LeafKind == TslLeafKind::NETWORK) {
      return TslCoSortBitonicLeaf<DataType, SimdStyle>::capacity;  // scales with the extension's lane count
    } else {
      return 64;
    }
  }
  static constexpr std::size_t leaf_threshold = compute_leaf_threshold();

  using column_pointers = std::array<DataType *, MaxColumns>;

  std::mt19937_64 rng;
  std::size_t column_count = 0;

  void swap_all(DataType * keys, column_pointers const & cols, std::size_t i, std::size_t j) {
    std::swap(keys[i], keys[j]);
    for (std::size_t column = 0; column < column_count; ++column) {
      std::swap(cols[column][i], cols[column][j]);
    }
  }

  auto get_pivot(DataType * keys, column_pointers const & cols, std::size_t count) -> DataType {
    auto const i0 = static_cast<std::size_t>(rng() % count);
    auto const i1 = static_cast<std::size_t>(rng() % count);
    auto const i2 = static_cast<std::size_t>(rng() % count);
    auto const a = keys[i0], b = keys[i1], c = keys[i2];
    std::size_t median_index;
    if (a < b) {
      median_index = (b < c) ? i1 : (a < c ? i2 : i0);
    } else {
      median_index = (a < c) ? i0 : (b < c ? i2 : i1);
    }
    swap_all(keys, cols, median_index, count - 1);
    return keys[count - 1];
  }

  // Partitions [0, count) around the pivot at keys[count - 1], co-moving every
  // payload column. Returns the index where the left region ends: for LESS_THAN
  // the first >= pivot, for EQUAL_TO the first > pivot.
  template <TslPartitionMode Mode>
  auto partition(DataType * keys, column_pointers const & cols, std::size_t count, DataType pivot_value) -> std::size_t {
    auto const pivot_vec = tsl::set1<DataSimdStyle>(pivot_value);
    DataType * left_ptr = keys;
    DataType * const pivot_ptr = keys + count - 1;
    DataType * scalar_end = pivot_ptr;

    register_type key_l{}, key_r{};
    std::size_t bad_l_count = 0;
    std::size_t bad_r_count = 0;
    enum class advance_state { LEFT, RIGHT, BOTH };
    advance_state advance = advance_state::BOTH;

    auto const bad_left = [&](register_type v) {
      if constexpr (Mode == TslPartitionMode::LESS_THAN) {
        return tsl::greater_than_or_equal<DataSimdStyle>(v, pivot_vec);
      } else {
        return tsl::greater_than<DataSimdStyle>(v, pivot_vec);
      }
    };
    auto const bad_right = [&](register_type v) {
      if constexpr (Mode == TslPartitionMode::LESS_THAN) {
        return tsl::less_than<DataSimdStyle>(v, pivot_vec);
      } else {
        return tsl::equal<DataSimdStyle>(v, pivot_vec);
      }
    };

    if (static_cast<std::size_t>(pivot_ptr - left_ptr) >= (2 * lane_count)) {
      DataType * right_ptr = pivot_ptr - lane_count;
      while ((right_ptr - left_ptr) >= static_cast<std::ptrdiff_t>(lane_count)) {
        if (advance == advance_state::LEFT || advance == advance_state::BOTH) {
          key_l = tsl::load<DataSimdStyle, false>(left_ptr);
          bad_l_count = tsl::mask_population_count<DataSimdStyle>(bad_left(key_l));
          if (bad_l_count == 0) {
            left_ptr += lane_count;
            advance = advance == advance_state::BOTH ? advance_state::BOTH : advance_state::LEFT;
            continue;
          }
        }
        if (advance == advance_state::RIGHT || advance == advance_state::BOTH) {
          key_r = tsl::load<DataSimdStyle, false>(right_ptr);
          bad_r_count = tsl::mask_population_count<DataSimdStyle>(bad_right(key_r));
          if (bad_r_count == 0) {
            right_ptr -= lane_count;
            advance = advance_state::RIGHT;
            continue;
          }
        }

        auto const left_off = static_cast<std::size_t>(left_ptr - keys);
        auto const right_off = static_cast<std::size_t>(right_ptr - keys);
        std::array<register_type, MaxColumns> pay_l, pay_r, pay_wl, pay_wr;
        for (std::size_t column = 0; column < column_count; ++column) {
          pay_l[column] = tsl::load<DataSimdStyle, false>(cols[column] + left_off);
          pay_r[column] = tsl::load<DataSimdStyle, false>(cols[column] + right_off);
        }
        register_type key_wl, key_wr;
        Partition::template step<Mode>(key_l, key_r, pay_l.data(), pay_r.data(), column_count, pivot_vec, key_wl, key_wr, pay_wl.data(), pay_wr.data());
        tsl::store<DataSimdStyle, false>(left_ptr, key_wl);
        tsl::store<DataSimdStyle, false>(right_ptr, key_wr);
        for (std::size_t column = 0; column < column_count; ++column) {
          tsl::store<DataSimdStyle, false>(cols[column] + left_off, pay_wl[column]);
          tsl::store<DataSimdStyle, false>(cols[column] + right_off, pay_wr[column]);
        }

        auto const swappable = std::min(bad_l_count, bad_r_count);
        left_ptr += swappable + (lane_count - bad_l_count);
        right_ptr -= swappable + (lane_count - bad_r_count);
        advance = advance_state::BOTH;
      }
      scalar_end = right_ptr + lane_count;
    }

    auto const left_good = [pivot_value](DataType v) {
      if constexpr (Mode == TslPartitionMode::LESS_THAN) {
        return v < pivot_value;
      } else {
        return v == pivot_value;
      }
    };
    auto const right_good = [pivot_value](DataType v) {
      if constexpr (Mode == TslPartitionMode::LESS_THAN) {
        return !(v < pivot_value);
      } else {
        return v > pivot_value;
      }
    };

    while (left_ptr < scalar_end) {
      while (left_ptr < scalar_end && left_good(*left_ptr)) {
        ++left_ptr;
      }
      while (left_ptr < scalar_end && right_good(*(scalar_end - 1))) {
        --scalar_end;
      }
      if (left_ptr < scalar_end) {
        swap_all(keys, cols, static_cast<std::size_t>(left_ptr - keys), static_cast<std::size_t>((scalar_end - 1) - keys));
        ++left_ptr;
        --scalar_end;
      }
    }
    return static_cast<std::size_t>(left_ptr - keys);
  }

  void insertion_leaf(DataType * keys, column_pointers const & cols, std::size_t count) {
    for (std::size_t i = 1; i < count; ++i) {
      auto const key = keys[i];
      std::array<DataType, MaxColumns> payload;
      for (std::size_t column = 0; column < column_count; ++column) {
        payload[column] = cols[column][i];
      }
      std::size_t j = i;
      while (j > 0 && key < keys[j - 1]) {
        keys[j] = keys[j - 1];
        for (std::size_t column = 0; column < column_count; ++column) {
          cols[column][j] = cols[column][j - 1];
        }
        --j;
      }
      keys[j] = key;
      for (std::size_t column = 0; column < column_count; ++column) {
        cols[column][j] = payload[column];
      }
    }
  }

  void leaf(DataType * keys, column_pointers const & cols, std::size_t count) {
    if constexpr (LeafKind == TslLeafKind::NETWORK) {
      TslCoSortBitonicLeaf<DataType, SimdStyle>::sort(keys, cols.data(), column_count, count);
    } else {
      insertion_leaf(keys, cols, count);
    }
  }

  void sort_impl(DataType * keys, column_pointers cols, std::size_t count) {
    while (count > leaf_threshold) {
      auto const pivot_value = get_pivot(keys, cols, count);
      std::size_t right_base;
      std::size_t left_n;
      std::size_t right_n;
      if constexpr (PartitionKind == TslPartitionKind::TWO_WAY) {
        auto const less_end = partition<TslPartitionMode::LESS_THAN>(keys, cols, count, pivot_value);
        swap_all(keys, cols, less_end, count - 1);
        left_n = less_end;
        right_base = less_end + 1;
        right_n = count - right_base;
      } else {
        auto const less_end = partition<TslPartitionMode::LESS_THAN>(keys, cols, count, pivot_value);
        column_pointers mid_cols;
        for (std::size_t column = 0; column < column_count; ++column) {
          mid_cols[column] = cols[column] + less_end;
        }
        auto const equal_end = less_end + partition<TslPartitionMode::EQUAL_TO>(keys + less_end, mid_cols, count - less_end, pivot_value);
        swap_all(keys, cols, equal_end, count - 1);
        left_n = less_end;
        right_base = equal_end + 1;
        right_n = count - right_base;
      }

      column_pointers right_cols;
      for (std::size_t column = 0; column < column_count; ++column) {
        right_cols[column] = cols[column] + right_base;
      }
      DataType * const right_keys = keys + right_base;
      if (left_n < right_n) {
        sort_impl(keys, cols, left_n);
        keys = right_keys;
        cols = right_cols;
        count = right_n;
      } else {
        sort_impl(right_keys, right_cols, right_n);
        count = left_n;
      }
    }
    if (count >= 2) {
      leaf(keys, cols, count);
    }
  }

 public:
  explicit TslMultiColumnQuickSorter(std::uint64_t seed) : rng(seed) {}

  void operator()(DataType * keys, DataType * const * columns, std::size_t columns_count, std::size_t count) {
    column_count = columns_count;
    column_pointers cols{};
    for (std::size_t column = 0; column < column_count; ++column) {
      cols[column] = columns[column];
    }
    sort_impl(keys, cols, count);
  }
};
