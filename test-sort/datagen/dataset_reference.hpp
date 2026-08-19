#pragma once

// The reference oracle: direction patterns and the sorted image they imply.
//
// This is the single implementation of "what the correct output is". The
// standalone `reference` tool writes it to disk, the benchmark compares against
// it in memory, and the dataset verifier checks it -- all through this header, so
// there is no second definition to drift.
//
// Deliberately the most literal reading of ORDER BY that can be written: sort an
// index vector with std::stable_sort under a plain per-column comparator, then
// gather. It shares nothing with the implementation under test.

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <numeric>
#include <utility>
#include <stdexcept>
#include <string>
#include <vector>

enum class TslDirection { Ascending, Descending, Alternating };

inline auto tsl_direction_name(TslDirection direction) -> std::string {
  switch (direction) {
    case TslDirection::Ascending: return "asc";
    case TslDirection::Descending: return "desc";
    case TslDirection::Alternating: return "alternating";
  }
  return "unknown";
}

inline auto tsl_direction_from_name(std::string const & name) -> TslDirection {
  if (name == "asc") return TslDirection::Ascending;
  if (name == "desc") return TslDirection::Descending;
  if (name == "alternating" || name == "alt") return TslDirection::Alternating;
  throw std::runtime_error("unknown direction pattern: " + name);
}

// Column j is ascending unless the pattern says otherwise. Alternating starts
// ascending at column 0, matching make_orders in benchmark_multicolumn_gbench.
inline auto tsl_direction_ascending(TslDirection direction, std::size_t columns)
  -> std::vector<bool> {
  std::vector<bool> ascending(columns, true);
  if (direction == TslDirection::Descending) {
    ascending.assign(columns, false);
  } else if (direction == TslDirection::Alternating) {
    for (std::size_t column = 0; column < columns; ++column) {
      ascending[column] = column % 2 == 0;
    }
  }
  return ascending;
}

// Sorts row indices under the per-column directions and gathers every column.
template <class DataType>
auto tsl_sorted_image(std::vector<std::vector<DataType>> const & source,
                      std::vector<bool> const & ascending)
  -> std::vector<std::vector<DataType>> {
  if (source.empty()) {
    return {};
  }
  auto const rows = source.front().size();
  auto const columns = source.size();
  std::vector<std::uint32_t> order(rows);
  std::iota(order.begin(), order.end(), 0u);
  std::stable_sort(order.begin(), order.end(),
                   [&source, &ascending, columns](std::uint32_t left, std::uint32_t right) {
    for (std::size_t column = 0; column < columns; ++column) {
      auto const a = source[column][left];
      auto const b = source[column][right];
      if (a != b) {
        return ascending[column] ? a < b : a > b;
      }
    }
    return false;
  });

  // The gather must consume every input row exactly once.
  std::vector<unsigned char> seen(rows, 0);
  for (auto index : order) {
    if (seen[index] != 0) {
      throw std::runtime_error("reference order is not a permutation");
    }
    seen[index] = 1;
  }

  std::vector<std::vector<DataType>> image(columns, std::vector<DataType>(rows));
  for (std::size_t column = 0; column < columns; ++column) {
    for (std::size_t row = 0; row < rows; ++row) {
      image[column][row] = source[column][order[row]];
    }
  }
  return image;
}

// Independent of how an image was produced: adjacent rows must be ordered.
template <class DataType>
void tsl_require_ordered(std::vector<std::vector<DataType>> const & image,
                         std::vector<bool> const & ascending) {
  if (image.empty()) {
    return;
  }
  auto const rows = image.front().size();
  auto const columns = image.size();
  for (std::size_t row = 0; row + 1 < rows; ++row) {
    for (std::size_t column = 0; column < columns; ++column) {
      auto const a = image[column][row];
      auto const b = image[column][row + 1];
      if (a == b) {
        continue;
      }
      if (!(ascending[column] ? a < b : a > b)) {
        throw std::runtime_error("image is not ordered at row " + std::to_string(row));
      }
      break;
    }
  }
}

// First differing (column, row) between two images, or {columns, 0} when equal.
// This is what a benchmark reports when its memcmp against the reference fails.
template <class DataType>
auto tsl_first_difference(std::vector<std::vector<DataType>> const & left,
                          std::vector<std::vector<DataType>> const & right)
  -> std::pair<std::size_t, std::size_t> {
  for (std::size_t column = 0; column < left.size(); ++column) {
    auto const bytes = left[column].size() * sizeof(DataType);
    if (std::memcmp(left[column].data(), right[column].data(), bytes) == 0) {
      continue;
    }
    std::size_t row = 0;
    while (row < left[column].size() && left[column][row] == right[column][row]) {
      ++row;
    }
    return {column, row};
  }
  return {left.size(), 0};
}
