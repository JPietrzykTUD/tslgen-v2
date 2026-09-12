#pragma once

#include "tsl_algorithm.hpp"

namespace tsl::algo {

namespace detail {

template <class Range>
using checked_range_element_t = typename std::remove_cv<
    typename std::remove_pointer<decltype(range_data(
        std::declval<Range&>()))>::type>::type;

template <class LeftRange, class RightRange>
inline bool ranges_share_start(
    const LeftRange& left,
    const RightRange& right) noexcept {
  return reinterpret_cast<std::uintptr_t>(range_data(left)) ==
         reinterpret_cast<std::uintptr_t>(range_data(right));
}

template <class LeftRange, class RightRange>
inline bool range_prefixes_overlap(
    const LeftRange& left,
    std::size_t left_count,
    const RightRange& right,
    std::size_t right_count) noexcept {
  if (left_count == 0 || right_count == 0) {
    return false;
  }
  using left_element = checked_range_element_t<LeftRange>;
  using right_element = checked_range_element_t<RightRange>;
  constexpr auto max_address = (std::numeric_limits<std::uintptr_t>::max)();
  if (left_count > max_address / sizeof(left_element) ||
      right_count > max_address / sizeof(right_element)) {
    return true;
  }
  const auto left_begin = reinterpret_cast<std::uintptr_t>(range_data(left));
  const auto right_begin = reinterpret_cast<std::uintptr_t>(range_data(right));
  const auto left_bytes = left_count * sizeof(left_element);
  const auto right_bytes = right_count * sizeof(right_element);
  if (left_begin <= right_begin) {
    return right_begin - left_begin < left_bytes;
  }
  return left_begin - right_begin < right_bytes;
}

template <std::size_t Scale, class InputRange, class IndexRange>
inline ::tsl::precondition_error selected_address_error(
    const InputRange& input,
    const IndexRange& indices) noexcept {
  using input_element = checked_range_element_t<InputRange>;
  using index_element = checked_range_element_t<IndexRange>;
  static_assert(std::is_integral<index_element>::value,
                "checked selected-row indices must be integral");
  static_assert(Scale == 0 || Scale <= 0xffffffffu,
                "selected-row scale must fit the generated gather immediate");
  constexpr std::size_t effective_scale =
      Scale == 0 ? sizeof(input_element) : Scale;
  constexpr auto max_size = (std::numeric_limits<std::size_t>::max)();
  const auto input_count = range_size(input);
  if (input_count > max_size / sizeof(input_element)) {
    return ::tsl::precondition_error::address_overflow;
  }
  const auto input_bytes = input_count * sizeof(input_element);
  const auto* index_data = range_data(indices);
  for (std::size_t position = 0; position < range_size(indices); ++position) {
    const auto raw_index = index_data[position];
    if constexpr (std::is_signed<index_element>::value) {
      if (raw_index < 0) {
        return ::tsl::precondition_error::index_out_of_bounds;
      }
    }
    using unsigned_index = typename std::make_unsigned<index_element>::type;
    const auto unsigned_raw = static_cast<unsigned_index>(raw_index);
    if constexpr (sizeof(unsigned_index) > sizeof(std::size_t)) {
      if (unsigned_raw > static_cast<unsigned_index>(max_size)) {
        return ::tsl::precondition_error::address_overflow;
      }
    }
    const auto index = static_cast<std::size_t>(unsigned_raw);
    if (index > max_size / effective_scale) {
      return ::tsl::precondition_error::address_overflow;
    }
    const auto offset = index * effective_scale;
    if (offset % alignof(input_element) != 0) {
      return ::tsl::precondition_error::misaligned;
    }
    if (offset > input_bytes || sizeof(input_element) > input_bytes - offset) {
      return ::tsl::precondition_error::index_out_of_bounds;
    }
  }
  return ::tsl::precondition_error::none;
}

}  // namespace detail

@{checked_algorithm_definitions}

}  // namespace tsl::algo
