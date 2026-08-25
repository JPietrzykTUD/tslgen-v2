#pragma once

// Measured descriptor for one dataset, as defined in description_datasets.md.
//
// Everything here is computed from the column values, never from the generator's
// intent: the generator records these numbers for the array it wrote, and the
// verifier recomputes them from the bytes it read back. Disagreement means the
// container, the generator or this file is wrong.

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <numeric>
#include <string>
#include <vector>

// Group-size buckets. The edges are the structural boundaries of the sorter:
// singleton, then the 2L minimums (4..32), the network capacities (32..256), the
// insertion threshold (64), the default task threshold (4096) and the default
// partition threshold (16384). One histogram therefore serves every SIMD
// configuration; a configuration reads the buckets its own 2L and C fall on.
inline constexpr std::array<std::size_t, 11> tsl_group_bucket_upper = {
  1, 3, 7, 15, 31, 63, 127, 255, 4095, 16383, static_cast<std::size_t>(-1)
};

inline auto tsl_group_bucket_label(std::size_t bucket) -> std::string {
  static char const * const labels[] = {
    "1", "2-3", "4-7", "8-15", "16-31", "32-63",
    "64-127", "128-255", "256-4095", "4096-16383", ">=16384"
  };
  return labels[bucket];
}

inline auto tsl_group_bucket_of(std::size_t size) -> std::size_t {
  for (std::size_t bucket = 0; bucket < tsl_group_bucket_upper.size(); ++bucket) {
    if (size <= tsl_group_bucket_upper[bucket]) {
      return bucket;
    }
  }
  return tsl_group_bucket_upper.size() - 1;
}

// Network-leaf capacities across the six (element width, register width)
// configurations: C = 16 * lane count, deduplicated.
inline constexpr std::array<std::size_t, 4> tsl_network_capacities = {32, 64, 128, 256};

struct TslDatasetDescriptor {
  std::size_t rows = 0;
  std::size_t columns = 0;

  // D_j for j = 1 .. m, stored at index j-1.
  std::vector<std::size_t> distinct_prefixes;
  // R_j for j = 0 .. m, stored at index j; R_0 = rows.
  std::vector<std::size_t> tied_rows;
  // Group-size histogram and extremes per level j = 1 .. m.
  std::vector<std::array<std::size_t, tsl_group_bucket_upper.size()>> group_histogram;
  std::vector<std::size_t> max_group;
  std::vector<std::size_t> nontrivial_groups;
  // Distinct values in each column on its own (the marginal cardinality), and
  // the value range, which the extreme-value shape is checked against.
  std::vector<std::size_t> column_cardinality;
  std::vector<std::uint64_t> column_min;
  std::vector<std::uint64_t> column_max;
  // Fraction of adjacent input pairs whose first p columns are non-descending,
  // for p = 1 .. m at index p-1; the last entry is the full-order fraction.
  std::vector<double> prefix_in_order_fraction;
  // Mean fill ratio of the ranges a leaf of capacity C would sort directly,
  // one entry per entry of tsl_network_capacities.
  std::array<double, tsl_network_capacities.size()> leaf_fill_ratio{};
  std::array<std::size_t, tsl_network_capacities.size()> leaf_ranges{};

  double weighted_work = 0.0;          // W
  double scan_volume = 0.0;            // sum of R_j for j = 0 .. m-2
  std::size_t ascending_runs = 0;      // maximal non-descending runs in input order
  double kendall_normalized = 0.0;     // inversions / (N(N-1)/2) against the target order
  double mean_displacement = 0.0;      // L_disp
  double adjacency_fraction = 0.0;     // L_adj
  double duplicate_tuple_fraction = 0.0;  // rows whose full tuple is not unique
};

namespace tsl_descriptor_detail {

// Inversion count of a permutation, via a Fenwick tree over positions.
inline auto count_inversions(std::vector<std::size_t> const & permutation) -> std::uint64_t {
  auto const count = permutation.size();
  std::vector<std::uint32_t> tree(count + 1, 0);
  std::uint64_t inversions = 0;
  for (std::size_t index = 0; index < count; ++index) {
    auto position = permutation[index] + 1;
    std::uint64_t not_greater = 0;
    for (auto cursor = position; cursor > 0; cursor -= cursor & (~cursor + 1)) {
      not_greater += tree[cursor];
    }
    inversions += index - not_greater;
    for (auto cursor = position; cursor <= count; cursor += cursor & (~cursor + 1)) {
      ++tree[cursor];
    }
  }
  return inversions;
}

}  // namespace tsl_descriptor_detail

template <class DataType>
auto tsl_describe_dataset(std::vector<std::vector<DataType>> const & columns)
  -> TslDatasetDescriptor {
  TslDatasetDescriptor descriptor;
  if (columns.empty()) {
    return descriptor;
  }
  auto const rows = columns.front().size();
  auto const column_count = columns.size();
  descriptor.rows = rows;
  descriptor.columns = column_count;
  descriptor.tied_rows.assign(column_count + 1, 0);
  descriptor.tied_rows[0] = rows >= 2 ? rows : 0;
  if (rows == 0) {
    return descriptor;
  }

  // Target order: ascending lexicographic over all columns, stable so that the
  // induced permutation is well defined even for duplicate tuples.
  std::vector<std::size_t> order(rows);
  std::iota(order.begin(), order.end(), std::size_t{0});
  auto const row_before = [&columns, column_count](std::size_t left, std::size_t right) {
    for (std::size_t column = 0; column < column_count; ++column) {
      if (columns[column][left] != columns[column][right]) {
        return columns[column][left] < columns[column][right];
      }
    }
    return false;
  };
  std::stable_sort(order.begin(), order.end(), row_before);

  // Group structure per level, accumulated by refining the boundary set: a
  // prefix that already differs at level j-1 still differs at level j.
  std::vector<unsigned char> boundary(rows, 0);
  boundary[0] = 1;
  auto const level_work = [](std::vector<std::size_t> const & sizes) {
    double work = 0.0;
    for (auto size : sizes) {
      if (size >= 2) {
        work += static_cast<double>(size) * std::log2(static_cast<double>(size));
      }
    }
    return work;
  };

  std::vector<double> work_per_level(column_count + 1, 0.0);
  work_per_level[0] = rows >= 2 ? static_cast<double>(rows) * std::log2(static_cast<double>(rows)) : 0.0;

  std::array<std::size_t, tsl_network_capacities.size()> fill_sum{};
  std::array<std::size_t, tsl_network_capacities.size()> fill_count{};
  auto const account_submitted_range = [&](std::size_t size) {
    if (size < 2) {
      return;
    }
    for (std::size_t index = 0; index < tsl_network_capacities.size(); ++index) {
      if (size <= tsl_network_capacities[index]) {
        fill_sum[index] += size;
        ++fill_count[index];
      }
    }
  };
  account_submitted_range(rows);  // the level-1 sort receives the whole range

  for (std::size_t level = 1; level <= column_count; ++level) {
    auto const & column = columns[level - 1];
    for (std::size_t index = 1; index < rows; ++index) {
      if (boundary[index] == 0 && column[order[index]] != column[order[index - 1]]) {
        boundary[index] = 1;
      }
    }
    std::vector<std::size_t> sizes;
    sizes.reserve(64);
    std::size_t group_start = 0;
    for (std::size_t index = 1; index <= rows; ++index) {
      if (index == rows || boundary[index] != 0) {
        sizes.push_back(index - group_start);
        group_start = index;
      }
    }

    std::array<std::size_t, tsl_group_bucket_upper.size()> histogram{};
    std::size_t tied = 0;
    std::size_t largest = 0;
    std::size_t nontrivial = 0;
    for (auto size : sizes) {
      ++histogram[tsl_group_bucket_of(size)];
      largest = std::max(largest, size);
      if (size >= 2) {
        tied += size;
        ++nontrivial;
      }
    }
    descriptor.distinct_prefixes.push_back(sizes.size());
    descriptor.tied_rows[level] = tied;
    descriptor.group_histogram.push_back(histogram);
    descriptor.max_group.push_back(largest);
    descriptor.nontrivial_groups.push_back(nontrivial);
    work_per_level[level] = level_work(sizes);
    if (level < column_count) {
      for (auto size : sizes) {
        account_submitted_range(size);
      }
    }
  }

  for (std::size_t level = 1; level <= column_count; ++level) {
    descriptor.weighted_work +=
      static_cast<double>(column_count - level + 1) * work_per_level[level - 1];
  }
  for (std::size_t level = 0; level + 2 <= column_count; ++level) {
    descriptor.scan_volume += static_cast<double>(descriptor.tied_rows[level]);
  }
  descriptor.duplicate_tuple_fraction =
    static_cast<double>(descriptor.tied_rows[column_count]) / static_cast<double>(rows);

  for (std::size_t index = 0; index < tsl_network_capacities.size(); ++index) {
    descriptor.leaf_ranges[index] = fill_count[index];
    descriptor.leaf_fill_ratio[index] = fill_count[index] == 0
      ? 0.0
      : static_cast<double>(fill_sum[index])
        / (static_cast<double>(fill_count[index]) * static_cast<double>(tsl_network_capacities[index]));
  }

  // Marginal cardinality per column.
  for (auto const & column : columns) {
    std::vector<DataType> values(column);
    std::sort(values.begin(), values.end());
    values.erase(std::unique(values.begin(), values.end()), values.end());
    descriptor.column_cardinality.push_back(values.size());
    descriptor.column_min.push_back(static_cast<std::uint64_t>(values.front()));
    descriptor.column_max.push_back(static_cast<std::uint64_t>(values.back()));
  }

  // Presortedness of the input order, per prefix length.
  descriptor.prefix_in_order_fraction.assign(column_count, 0.0);
  std::vector<std::size_t> in_order(column_count, 0);
  for (std::size_t index = 0; index + 1 < rows; ++index) {
    std::size_t first_difference = column_count;
    bool ascending = true;
    for (std::size_t column = 0; column < column_count; ++column) {
      if (columns[column][index] != columns[column][index + 1]) {
        first_difference = column;
        ascending = columns[column][index] < columns[column][index + 1];
        break;
      }
    }
    for (std::size_t prefix = 0; prefix < column_count; ++prefix) {
      // Non-descending on the first prefix+1 columns: either they are all equal,
      // or the first difference inside the prefix goes upward.
      if (first_difference > prefix || ascending) {
        ++in_order[prefix];
      }
    }
  }
  auto const pairs = rows >= 2 ? static_cast<double>(rows - 1) : 1.0;
  for (std::size_t prefix = 0; prefix < column_count; ++prefix) {
    descriptor.prefix_in_order_fraction[prefix] = static_cast<double>(in_order[prefix]) / pairs;
  }

  descriptor.ascending_runs = 1;
  for (std::size_t index = 0; index + 1 < rows; ++index) {
    if (row_before(index + 1, index)) {
      ++descriptor.ascending_runs;
    }
  }

  // Induced permutation: position(i) is where input row i lands in target order.
  std::vector<std::size_t> position(rows, 0);
  for (std::size_t rank = 0; rank < rows; ++rank) {
    position[order[rank]] = rank;
  }
  std::uint64_t displacement = 0;
  std::size_t adjacent = 0;
  for (std::size_t index = 0; index < rows; ++index) {
    auto const target = position[index];
    displacement += target > index ? target - index : index - target;
    if (index + 1 < rows && position[index + 1] == target + 1) {
      ++adjacent;
    }
  }
  descriptor.mean_displacement = static_cast<double>(displacement) / static_cast<double>(rows);
  descriptor.adjacency_fraction = static_cast<double>(adjacent) / pairs;
  if (rows >= 2) {
    auto const inversions = tsl_descriptor_detail::count_inversions(position);
    auto const total_pairs = static_cast<double>(rows) * static_cast<double>(rows - 1) / 2.0;
    descriptor.kendall_normalized = static_cast<double>(inversions) / total_pairs;
  }
  return descriptor;
}
