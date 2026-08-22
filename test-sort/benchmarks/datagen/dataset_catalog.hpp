#pragma once

// The dataset shapes of description_datasets.md, their generators, and the
// analytic expectations a verifier checks them against.
//
// Generation follows the document's group-tree model: a shape is a choice of
// splitter (how a level-(j-1) group divides into level-j children) plus an
// arrangement (what row order the instance is presented in). Values are assigned
// per parent, so a column's marginal cardinality equals its maximum branching
// factor while D_j stays exact by construction.
//
// The expectations here are closed forms derived from the shape parameters, not
// from the generated array. That is what makes verification meaningful: a
// generator bug that shifts D_2 cannot also shift the number it is compared to.

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <functional>
#include <limits>
#include <map>
#include <numeric>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#include "dataset_descriptor.hpp"

enum class TslShape {
  UniqueFirst,
  UniqueLast,
  IndependentUniform,
  BalancedHierarchy,
  SkewedZipf,
  HeavyHitter,
  LowCardinality,
  AllEqualPrefix,
  CorrelatedForward,
  CorrelatedReverse,
  CorrelatedNoisy,
  PrefixPresorted,
  ClusteredRuns,
  ReverseSorted,
  OrganPipe,
  Sawtooth,
  DuplicatesAtPivot,
  ExtremeValues,
  PermutationLocal,
  PermutationBlocked,
  PermutationRandom,
  TpcdsQ67,
};

inline auto tsl_shape_name(TslShape shape) -> std::string {
  switch (shape) {
    case TslShape::UniqueFirst: return "unique_first";
    case TslShape::UniqueLast: return "unique_last";
    case TslShape::TpcdsQ67: return "tpcds_q67";
    case TslShape::IndependentUniform: return "independent_uniform";
    case TslShape::BalancedHierarchy: return "balanced_hierarchy";
    case TslShape::SkewedZipf: return "skewed_zipf";
    case TslShape::HeavyHitter: return "heavy_hitter";
    case TslShape::LowCardinality: return "low_cardinality";
    case TslShape::AllEqualPrefix: return "all_equal_prefix";
    case TslShape::CorrelatedForward: return "correlated_forward";
    case TslShape::CorrelatedReverse: return "correlated_reverse";
    case TslShape::CorrelatedNoisy: return "correlated_noisy";
    case TslShape::PrefixPresorted: return "prefix_presorted";
    case TslShape::ClusteredRuns: return "clustered_runs";
    case TslShape::ReverseSorted: return "reverse_sorted";
    case TslShape::OrganPipe: return "organ_pipe";
    case TslShape::Sawtooth: return "sawtooth";
    case TslShape::DuplicatesAtPivot: return "duplicates_at_pivot";
    case TslShape::ExtremeValues: return "extreme_values";
    case TslShape::PermutationLocal: return "permutation_local";
    case TslShape::PermutationBlocked: return "permutation_blocked";
    case TslShape::PermutationRandom: return "permutation_random";
  }
  return "unknown";
}

inline auto tsl_shape_from_name(std::string const & name) -> TslShape {
  static TslShape const all[] = {
    TslShape::UniqueFirst, TslShape::UniqueLast, TslShape::IndependentUniform,
    TslShape::BalancedHierarchy, TslShape::SkewedZipf, TslShape::HeavyHitter,
    TslShape::LowCardinality, TslShape::AllEqualPrefix, TslShape::CorrelatedForward,
    TslShape::CorrelatedReverse, TslShape::CorrelatedNoisy, TslShape::PrefixPresorted,
    TslShape::ClusteredRuns, TslShape::ReverseSorted, TslShape::OrganPipe,
    TslShape::Sawtooth, TslShape::DuplicatesAtPivot, TslShape::ExtremeValues,
    TslShape::PermutationLocal, TslShape::PermutationBlocked, TslShape::PermutationRandom,
  };
  for (auto shape : all) {
    if (tsl_shape_name(shape) == name) {
      return shape;
    }
  }
  throw std::invalid_argument("unknown dataset shape: " + name);
}

// Which document section a shape belongs to, so a report can be grouped the way
// the document is.
inline auto tsl_shape_section(TslShape shape) -> int {
  switch (shape) {
    case TslShape::UniqueFirst: return 1;
    case TslShape::UniqueLast: return 2;
    case TslShape::IndependentUniform:
    case TslShape::BalancedHierarchy:
    case TslShape::TpcdsQ67: return 3;
    case TslShape::SkewedZipf:
    case TslShape::HeavyHitter: return 4;
    case TslShape::LowCardinality:
    case TslShape::AllEqualPrefix: return 5;
    case TslShape::CorrelatedForward:
    case TslShape::CorrelatedReverse:
    case TslShape::CorrelatedNoisy: return 6;
    case TslShape::PrefixPresorted:
    case TslShape::ClusteredRuns:
    case TslShape::ReverseSorted: return 7;
    case TslShape::OrganPipe:
    case TslShape::Sawtooth:
    case TslShape::DuplicatesAtPivot:
    case TslShape::ExtremeValues: return 8;
    case TslShape::PermutationLocal:
    case TslShape::PermutationBlocked:
    case TslShape::PermutationRandom: return 9;
  }
  return 0;
}

struct TslDatasetSpec {
  std::string id;
  TslShape shape = TslShape::UniqueFirst;
  std::size_t rows = 0;
  std::size_t columns = 0;
  std::size_t element_bytes = 4;
  std::map<std::string, double> params;

  auto param(std::string const & name, double fallback) const -> double {
    auto const found = params.find(name);
    return found == params.end() ? fallback : found->second;
  }
  auto integer_param(std::string const & name, std::size_t fallback) const -> std::size_t {
    auto const found = params.find(name);
    return found == params.end() ? fallback : static_cast<std::size_t>(found->second + 0.5);
  }
};

// Deterministic seed from the identity of the instance. Any change to shape,
// parameters, size or width produces a different stream; an unchanged spec
// reproduces the same bytes on any machine.
inline auto tsl_mix64(std::uint64_t value) -> std::uint64_t {
  value += 0x9e3779b97f4a7c15ull;
  value = (value ^ (value >> 30)) * 0xbf58476d1ce4e5b9ull;
  value = (value ^ (value >> 27)) * 0x94d049bb133111ebull;
  return value ^ (value >> 31);
}

inline auto tsl_spec_seed(TslDatasetSpec const & spec) -> std::uint64_t {
  std::uint64_t seed = 0x5eed5eed5eed5eedull;
  for (char character : spec.id) {
    seed = tsl_mix64(seed ^ static_cast<std::uint64_t>(static_cast<unsigned char>(character)));
  }
  seed = tsl_mix64(seed ^ static_cast<std::uint64_t>(spec.rows));
  seed = tsl_mix64(seed ^ static_cast<std::uint64_t>(spec.columns));
  seed = tsl_mix64(seed ^ static_cast<std::uint64_t>(spec.element_bytes));
  return seed;
}

// --- splitters --------------------------------------------------------------

// Sizes as equal as possible, largest remainder first, summing to `total`.
inline auto tsl_split_balanced(std::size_t total, std::size_t parts) -> std::vector<std::size_t> {
  if (parts == 0 || total == 0) {
    return {};
  }
  parts = std::min(parts, total);
  std::vector<std::size_t> sizes(parts, total / parts);
  auto remainder = total % parts;
  for (std::size_t index = 0; index < remainder; ++index) {
    ++sizes[index];
  }
  return sizes;
}

// Groups of exactly `size_each`, with any remainder as one final smaller group.
// Keeping the full groups exact is what makes "at the capacity" and "one above
// the capacity" distinct experiments.
inline auto tsl_split_fixed(std::size_t total, std::size_t size_each) -> std::vector<std::size_t> {
  if (size_each == 0) {
    return {total};
  }
  if (total <= size_each) {
    return {total};
  }
  std::vector<std::size_t> sizes(total / size_each, size_each);
  if (auto const remainder = total % size_each; remainder != 0) {
    sizes.push_back(remainder);
  }
  return sizes;
}

// Balanced sizes that are whole multiples of `unit`, so that a later split into
// groups of exactly `unit` leaves no remainder per parent. Without this, every
// intermediate group contributes its own short remainder group and the terminal
// group size stops being exact.
inline auto tsl_split_balanced_multiple(std::size_t total, std::size_t parts, std::size_t unit)
  -> std::vector<std::size_t> {
  if (unit <= 1) {
    return tsl_split_balanced(total, parts);
  }
  auto const units = (total + unit - 1) / unit;
  auto const unit_sizes = tsl_split_balanced(units, parts);
  std::vector<std::size_t> sizes;
  sizes.reserve(unit_sizes.size());
  std::size_t assigned = 0;
  for (auto count : unit_sizes) {
    auto const size = std::min(count * unit, total - assigned);
    if (size == 0) {
      break;
    }
    sizes.push_back(size);
    assigned += size;
  }
  if (assigned < total && !sizes.empty()) {
    sizes.back() += total - assigned;
  }
  return sizes;
}

// Zipf-distributed sizes: weight of group i is (i+1)^-exponent, scaled to sum to
// `total` by largest remainder, with every group at least one row.
inline auto tsl_split_zipf(std::size_t total, std::size_t parts, double exponent)
  -> std::vector<std::size_t> {
  parts = std::min(parts, total);
  if (parts == 0) {
    return {};
  }
  std::vector<double> weights(parts);
  double weight_sum = 0.0;
  for (std::size_t index = 0; index < parts; ++index) {
    weights[index] = std::pow(static_cast<double>(index + 1), -exponent);
    weight_sum += weights[index];
  }
  std::vector<std::size_t> sizes(parts, 1);
  auto assigned = parts;
  std::vector<std::pair<double, std::size_t>> remainders;
  remainders.reserve(parts);
  for (std::size_t index = 0; index < parts; ++index) {
    auto const share = weights[index] / weight_sum * static_cast<double>(total - parts);
    auto const whole = static_cast<std::size_t>(share);
    sizes[index] += whole;
    assigned += whole;
    remainders.emplace_back(share - static_cast<double>(whole), index);
  }
  std::sort(remainders.begin(), remainders.end(), [](auto const & left, auto const & right) {
    return left.first > right.first;
  });
  for (std::size_t index = 0; assigned < total; ++index, ++assigned) {
    ++sizes[remainders[index % remainders.size()].second];
  }
  return sizes;
}

using TslSplitter = std::function<std::vector<std::size_t>(std::size_t, std::size_t)>;
using TslValueMap = std::function<std::uint64_t(std::size_t, std::size_t, std::size_t)>;

inline auto tsl_default_value_map() -> TslValueMap {
  return [](std::size_t, std::size_t child, std::size_t) -> std::uint64_t { return child; };
}

// Fills columns[level ..] for rows [lo, hi) by splitting the range into children,
// giving each child one distinct value in this column, and recursing. A singleton
// needs no further discrimination, so its remaining columns are left at zero.
template <class DataType>
void tsl_build_tree(
  std::vector<std::vector<DataType>> & columns,
  std::size_t level,
  std::size_t lo,
  std::size_t hi,
  TslSplitter const & splitter,
  TslValueMap const & value_map
) {
  if (level >= columns.size() || hi <= lo) {
    return;
  }
  if (hi - lo == 1) {
    for (auto rest = level; rest < columns.size(); ++rest) {
      columns[rest][lo] = DataType{0};
    }
    return;
  }
  auto const sizes = splitter(level, hi - lo);
  std::size_t cursor = lo;
  for (std::size_t child = 0; child < sizes.size(); ++child) {
    auto const value = static_cast<DataType>(value_map(level, child, sizes.size()));
    std::fill(
      columns[level].begin() + static_cast<std::ptrdiff_t>(cursor),
      columns[level].begin() + static_cast<std::ptrdiff_t>(cursor + sizes[child]),
      value
    );
    tsl_build_tree(columns, level + 1, cursor, cursor + sizes[child], splitter, value_map);
    cursor += sizes[child];
  }
}

// --- arrangement ------------------------------------------------------------

template <class DataType>
void tsl_apply_permutation(std::vector<std::vector<DataType>> & columns,
                           std::vector<std::size_t> const & permutation) {
  std::vector<DataType> scratch(permutation.size());
  for (auto & column : columns) {
    for (std::size_t index = 0; index < permutation.size(); ++index) {
      scratch[index] = column[permutation[index]];
    }
    column.swap(scratch);
  }
}

template <class DataType>
void tsl_shuffle_rows(std::vector<std::vector<DataType>> & columns, std::mt19937_64 & rng) {
  auto const rows = columns.front().size();
  std::vector<std::size_t> permutation(rows);
  std::iota(permutation.begin(), permutation.end(), std::size_t{0});
  for (std::size_t index = rows; index > 1; --index) {
    auto const pick = static_cast<std::size_t>(rng() % index);
    std::swap(permutation[index - 1], permutation[pick]);
  }
  tsl_apply_permutation(columns, permutation);
}

// Shuffles only inside groups that agree on the first `prefix` columns. Applied
// to a tree-generated (hence sorted) instance it yields exactly "sorted by the
// first p columns, random within".
template <class DataType>
void tsl_shuffle_within_prefix(
  std::vector<std::vector<DataType>> & columns,
  std::size_t prefix,
  std::mt19937_64 & rng
) {
  auto const rows = columns.front().size();
  std::vector<std::size_t> permutation(rows);
  std::iota(permutation.begin(), permutation.end(), std::size_t{0});
  std::size_t group_start = 0;
  auto const same_prefix = [&](std::size_t left, std::size_t right) {
    for (std::size_t column = 0; column < prefix; ++column) {
      if (columns[column][left] != columns[column][right]) {
        return false;
      }
    }
    return true;
  };
  for (std::size_t index = 1; index <= rows; ++index) {
    if (index == rows || !same_prefix(index - 1, index)) {
      for (std::size_t position = index; position > group_start + 1; --position) {
        auto const span = position - group_start;
        auto const pick = group_start + static_cast<std::size_t>(rng() % span);
        std::swap(permutation[position - 1], permutation[pick]);
      }
      group_start = index;
    }
  }
  tsl_apply_permutation(columns, permutation);
}

template <class DataType>
void tsl_sort_blocks(std::vector<std::vector<DataType>> & columns, std::size_t blocks) {
  auto const rows = columns.front().size();
  auto const column_count = columns.size();
  auto const row_before = [&columns, column_count](std::size_t left, std::size_t right) {
    for (std::size_t column = 0; column < column_count; ++column) {
      if (columns[column][left] != columns[column][right]) {
        return columns[column][left] < columns[column][right];
      }
    }
    return false;
  };
  std::vector<std::size_t> permutation(rows);
  std::iota(permutation.begin(), permutation.end(), std::size_t{0});
  auto const sizes = tsl_split_balanced(rows, blocks);
  std::size_t cursor = 0;
  for (auto size : sizes) {
    std::stable_sort(
      permutation.begin() + static_cast<std::ptrdiff_t>(cursor),
      permutation.begin() + static_cast<std::ptrdiff_t>(cursor + size),
      row_before
    );
    cursor += size;
  }
  tsl_apply_permutation(columns, permutation);
}

// --- generation -------------------------------------------------------------

// Balanced tree whose branching makes every tuple distinct, used by the shapes
// that vary arrangement rather than group structure.
inline auto tsl_unique_tuple_branching(std::size_t rows, std::size_t columns) -> std::size_t {
  auto branching = static_cast<std::size_t>(
    std::ceil(std::pow(static_cast<double>(rows), 1.0 / static_cast<double>(columns)))
  );
  return std::max<std::size_t>(branching, 2);
}

template <class DataType>
auto tsl_generate_dataset(TslDatasetSpec const & spec) -> std::vector<std::vector<DataType>> {
  auto const rows = spec.rows;
  auto const column_count = spec.columns;
  if (rows == 0 || column_count == 0) {
    throw std::invalid_argument("dataset needs rows and columns");
  }
  std::vector<std::vector<DataType>> columns(column_count, std::vector<DataType>(rows, DataType{0}));
  std::mt19937_64 rng(tsl_spec_seed(spec));
  auto const last = column_count - 1;
  auto const type_max = std::numeric_limits<DataType>::max();

  auto const uniform = [&rng](std::uint64_t cardinality) -> std::uint64_t {
    return cardinality == 0 ? 0 : rng() % cardinality;
  };
  auto const fill_random_tail = [&](std::size_t from_column, std::uint64_t cardinality) {
    for (std::size_t column = from_column; column < column_count; ++column) {
      for (auto & value : columns[column]) {
        value = static_cast<DataType>(uniform(cardinality));
      }
    }
  };

  switch (spec.shape) {
    case TslShape::UniqueFirst: {
      TslSplitter splitter = [](std::size_t level, std::size_t size) {
        return level == 0 ? std::vector<std::size_t>(size, 1) : std::vector<std::size_t>{size};
      };
      tsl_build_tree(columns, 0, 0, rows, splitter, tsl_default_value_map());
      tsl_shuffle_rows(columns, rng);
      break;
    }
    case TslShape::UniqueLast: {
      auto const group = std::max<std::size_t>(spec.integer_param("g", 2), 1);
      auto const levels = column_count >= 2 ? column_count - 1 : 1;
      auto const groups_needed = std::max<std::size_t>(rows / std::max<std::size_t>(group, 1), 1);
      auto const branching = std::max<std::size_t>(
        static_cast<std::size_t>(std::llround(
          std::pow(static_cast<double>(groups_needed), 1.0 / static_cast<double>(levels))
        )),
        2
      );
      TslSplitter splitter = [=](std::size_t level, std::size_t size) -> std::vector<std::size_t> {
        if (column_count == 1 || level == last) {
          return std::vector<std::size_t>(size, 1);
        }
        if (level + 2 == column_count) {
          return tsl_split_fixed(size, group);
        }
        return tsl_split_balanced_multiple(size, branching, group);
      };
      tsl_build_tree(columns, 0, 0, rows, splitter, tsl_default_value_map());
      tsl_shuffle_rows(columns, rng);
      break;
    }
    case TslShape::IndependentUniform: {
      auto const cardinality = std::max<std::size_t>(spec.integer_param("c", 4096), 1);
      for (auto & column : columns) {
        for (auto & value : column) {
          value = static_cast<DataType>(uniform(cardinality));
        }
      }
      break;
    }
    case TslShape::TpcdsQ67: {
      // The grouping key of TPC-DS query 67, which rolls up over
      //
      //   i_category, i_class, i_brand, i_product_name,
      //   d_year, d_qoy, d_moy, s_store_id
      //
      // and is the widest co-sort key in this benchmark. Two structures meet in
      // it, which is what makes it worth having: the first four columns are a
      // strict hierarchy, each nested in the one before, while the last four come
      // from other dimension tables and are independent of them and of each
      // other. A leading column of ten distinct values means the first sort
      // produces very few, very large equal runs and everything after it is
      // decided inside those.
      //
      // The cardinalities are *modelled* on the schema's and scaled by `sf`, not
      // produced by dsdgen: item and store scale with the square root of the
      // scale factor, category, class and brand counts are fixed, and query 67
      // filters a twelve-month window so at most two years appear. Calibrating
      // them against a real dsdgen run is worth doing before they are cited as
      // TPC-DS numbers rather than as its shape.
      auto const scale = std::max(spec.param("sf", 1.0), 0.01);
      auto const root = std::sqrt(scale);
      auto const brands = std::size_t{1000};
      auto const products =
        std::max<std::size_t>(static_cast<std::size_t>(18000.0 * root), brands);
      auto const stores =
        std::max<std::size_t>(static_cast<std::size_t>(12.0 * root), 1);
      auto const per_brand = std::max<std::size_t>(products / brands, 1);
      auto const per_class = std::max<std::size_t>(brands / 100u, 1);
      auto const per_category = std::max<std::size_t>(100u / 10u, 1);

      for (std::size_t row = 0; row < rows; ++row) {
        // One draw fixes the whole hierarchy, so the nesting is exact rather than
        // approximate: a brand belongs to one class and a class to one category,
        // as in the schema.
        auto const product = uniform(products);
        auto const brand = product / per_brand;
        auto const item_class = brand / per_class;
        auto const category = item_class / per_category;
        std::size_t const key[8] = {category, item_class, brand, product,
                                    uniform(2), uniform(4), uniform(12),
                                    uniform(stores)};
        for (std::size_t column = 0; column < column_count; ++column) {
          columns[column][row] = static_cast<DataType>(
            // Past the rollup key a real query has nothing left to order by, so
            // the extra columns are a unique tie-break.
            column < 8 ? key[column] : row);
        }
      }
      break;
    }
    case TslShape::BalancedHierarchy: {
      auto const cardinality = std::max<std::size_t>(spec.integer_param("c", 16), 2);
      TslSplitter splitter = [=](std::size_t, std::size_t size) {
        return tsl_split_balanced(size, cardinality);
      };
      tsl_build_tree(columns, 0, 0, rows, splitter, tsl_default_value_map());
      tsl_shuffle_rows(columns, rng);
      break;
    }
    case TslShape::SkewedZipf: {
      auto const groups = std::max<std::size_t>(spec.integer_param("d1", 1024), 1);
      auto const exponent = spec.param("s", 1.0);
      auto const branching = spec.integer_param("b", 0);
      TslSplitter splitter = [=](std::size_t level, std::size_t size) {
        if (level == 0) {
          return tsl_split_zipf(size, groups, exponent);
        }
        // b = 0 means "resolve by the last column": branch by the root of the
        // remaining depth so a group becomes singletons exactly at level m.
        auto const parts = branching != 0
          ? branching
          : tsl_unique_tuple_branching(size, column_count - level);
        return tsl_split_balanced(size, parts);
      };
      tsl_build_tree(columns, 0, 0, rows, splitter, tsl_default_value_map());
      tsl_shuffle_rows(columns, rng);
      break;
    }
    case TslShape::HeavyHitter: {
      auto const fraction = spec.param("frac", 0.9);
      auto const branching = spec.integer_param("b", 0);
      auto const heavy = static_cast<std::size_t>(
        std::llround(fraction * static_cast<double>(rows))
      );
      TslSplitter splitter = [=](std::size_t level, std::size_t size) -> std::vector<std::size_t> {
        if (level != 0) {
          auto const parts = branching != 0
            ? branching
            : tsl_unique_tuple_branching(size, column_count - level);
          return tsl_split_balanced(size, parts);
        }
        std::vector<std::size_t> sizes;
        sizes.push_back(heavy);
        sizes.insert(sizes.end(), size - heavy, std::size_t{1});
        return sizes;
      };
      tsl_build_tree(columns, 0, 0, rows, splitter, tsl_default_value_map());
      tsl_shuffle_rows(columns, rng);
      break;
    }
    case TslShape::LowCardinality: {
      auto const distinct = std::max<std::size_t>(spec.integer_param("d", 4), 1);
      TslSplitter splitter = [=](std::size_t, std::size_t size) {
        return distinct == 1 ? std::vector<std::size_t>{size}
                             : tsl_split_balanced(size, distinct);
      };
      tsl_build_tree(columns, 0, 0, rows, splitter, tsl_default_value_map());
      tsl_shuffle_rows(columns, rng);
      break;
    }
    case TslShape::AllEqualPrefix: {
      TslSplitter splitter = [](std::size_t level, std::size_t size) -> std::vector<std::size_t> {
        if (level == 0) {
          return {size};
        }
        if (level == 1) {
          return std::vector<std::size_t>(size, 1);
        }
        return {size};
      };
      tsl_build_tree(columns, 0, 0, rows, splitter, tsl_default_value_map());
      tsl_shuffle_rows(columns, rng);
      break;
    }
    case TslShape::CorrelatedForward: {
      auto const cardinality = std::max<std::size_t>(spec.integer_param("c", 4096), 1);
      auto const shift = spec.integer_param("shift", 4);
      for (std::size_t row = 0; row < rows; ++row) {
        auto const base = uniform(cardinality);
        columns[0][row] = static_cast<DataType>(base);
        for (std::size_t column = 1; column < column_count; ++column) {
          columns[column][row] = static_cast<DataType>(base >> (shift * (column - 1)));
        }
      }
      break;
    }
    case TslShape::CorrelatedReverse: {
      auto const shift = spec.integer_param("shift", 8);
      auto const cardinality = std::max<std::size_t>(spec.integer_param("c", rows * 4), 2);
      for (std::size_t row = 0; row < rows; ++row) {
        auto const fine = uniform(cardinality);
        columns[last][row] = static_cast<DataType>(fine);
        for (std::size_t column = last; column-- > 0;) {
          columns[column][row] =
            static_cast<DataType>(fine >> (shift * (last - column)));
        }
      }
      break;
    }
    case TslShape::CorrelatedNoisy: {
      auto const cardinality = std::max<std::size_t>(spec.integer_param("c", 4096), 2);
      auto const noise = std::max<std::size_t>(spec.integer_param("noise", 16), 1);
      for (std::size_t row = 0; row < rows; ++row) {
        auto const base = uniform(cardinality);
        columns[0][row] = static_cast<DataType>(base);
        if (column_count > 1) {
          auto const offset = static_cast<std::int64_t>(uniform(2 * noise + 1)) -
                              static_cast<std::int64_t>(noise);
          auto shifted = static_cast<std::int64_t>(base) + offset;
          shifted = std::max<std::int64_t>(0, std::min<std::int64_t>(
            shifted, static_cast<std::int64_t>(cardinality) - 1));
          columns[1][row] = static_cast<DataType>(shifted);
        }
        for (std::size_t column = 2; column < column_count; ++column) {
          columns[column][row] = static_cast<DataType>(uniform(cardinality));
        }
      }
      break;
    }
    case TslShape::PrefixPresorted:
    case TslShape::ClusteredRuns:
    case TslShape::ReverseSorted: {
      auto const branching = tsl_unique_tuple_branching(rows, column_count);
      TslSplitter splitter = [=](std::size_t, std::size_t size) {
        return tsl_split_balanced(size, branching);
      };
      tsl_build_tree(columns, 0, 0, rows, splitter, tsl_default_value_map());
      if (spec.shape == TslShape::PrefixPresorted) {
        auto const prefix = std::min(spec.integer_param("p", 1), column_count);
        if (prefix == 0) {
          tsl_shuffle_rows(columns, rng);
        } else if (prefix < column_count) {
          tsl_shuffle_within_prefix(columns, prefix, rng);
        }
        // prefix == column_count leaves the fully sorted order in place.
      } else if (spec.shape == TslShape::ClusteredRuns) {
        auto const runs = std::max<std::size_t>(spec.integer_param("r", 64), 1);
        tsl_shuffle_rows(columns, rng);
        tsl_sort_blocks(columns, runs);
      } else {
        std::vector<std::size_t> reversed(rows);
        for (std::size_t index = 0; index < rows; ++index) {
          reversed[index] = rows - 1 - index;
        }
        tsl_apply_permutation(columns, reversed);
      }
      break;
    }
    case TslShape::OrganPipe: {
      auto const half = (rows + 1) / 2;
      for (std::size_t row = 0; row < rows; ++row) {
        columns[0][row] = static_cast<DataType>(row < half ? row : rows - 1 - row);
      }
      fill_random_tail(1, std::max<std::size_t>(spec.integer_param("c", 4096), 1));
      break;
    }
    case TslShape::Sawtooth: {
      auto const teeth = std::max<std::size_t>(spec.integer_param("k", 1024), 1);
      for (std::size_t row = 0; row < rows; ++row) {
        columns[0][row] = static_cast<DataType>(row % teeth);
      }
      fill_random_tail(1, std::max<std::size_t>(spec.integer_param("c", 4096), 1));
      break;
    }
    case TslShape::DuplicatesAtPivot: {
      auto const fraction = spec.param("frac", 0.5);
      auto const heavy = static_cast<std::size_t>(std::llround(fraction * static_cast<double>(rows)));
      auto const middle = static_cast<DataType>(type_max / 2);
      for (std::size_t row = 0; row < rows; ++row) {
        if (row < heavy) {
          columns[0][row] = middle;
        } else {
          auto value = static_cast<DataType>(rng());
          if (value == middle) {
            value = static_cast<DataType>(middle + 1);
          }
          columns[0][row] = value;
        }
      }
      fill_random_tail(1, std::max<std::size_t>(spec.integer_param("c", 4096), 1));
      tsl_shuffle_rows(columns, rng);
      break;
    }
    case TslShape::ExtremeValues: {
      auto const group = std::max<std::size_t>(spec.integer_param("g", 64), 2);
      auto const levels = column_count >= 2 ? column_count - 1 : 1;
      auto const groups_needed = std::max<std::size_t>(rows / group, 1);
      auto const branching = std::max<std::size_t>(
        static_cast<std::size_t>(std::llround(
          std::pow(static_cast<double>(groups_needed), 1.0 / static_cast<double>(levels))
        )),
        2
      );
      TslSplitter splitter = [=](std::size_t level, std::size_t size) -> std::vector<std::size_t> {
        if (column_count == 1 || level == last) {
          return std::vector<std::size_t>(size, 1);
        }
        if (level + 2 == column_count) {
          return tsl_split_fixed(size, group);
        }
        return tsl_split_balanced_multiple(size, branching, group);
      };
      // The final column takes half of its distinct values from the bottom of
      // the domain and half from the top, so every leaf-sized range holds real
      // zeros and real type maxima -- the value the network leaf pads with.
      TslValueMap value_map = [=](std::size_t level, std::size_t child, std::size_t children)
        -> std::uint64_t {
        if (level != last) {
          return child;
        }
        auto const half = (children + 1) / 2;
        if (child < half) {
          return child;
        }
        return static_cast<std::uint64_t>(type_max) - (children - 1 - child);
      };
      tsl_build_tree(columns, 0, 0, rows, splitter, value_map);
      tsl_shuffle_rows(columns, rng);
      break;
    }
    case TslShape::PermutationLocal: {
      for (std::size_t row = 0; row < rows; ++row) {
        auto const partner = row ^ std::size_t{1};
        columns[0][row] = static_cast<DataType>(partner < rows ? partner : row);
      }
      break;
    }
    case TslShape::PermutationBlocked: {
      auto const block = std::max<std::size_t>(spec.integer_param("block", 4096), 1);
      if (rows % block != 0) {
        throw std::invalid_argument("permutation_blocked needs block to divide rows");
      }
      auto const blocks = rows / block;
      std::vector<std::size_t> order(blocks);
      std::iota(order.begin(), order.end(), std::size_t{0});
      for (std::size_t index = blocks; index > 1; --index) {
        std::swap(order[index - 1], order[static_cast<std::size_t>(rng() % index)]);
      }
      for (std::size_t row = 0; row < rows; ++row) {
        columns[0][row] = static_cast<DataType>(order[row / block] * block + row % block);
      }
      break;
    }
    case TslShape::PermutationRandom: {
      std::vector<std::size_t> order(rows);
      std::iota(order.begin(), order.end(), std::size_t{0});
      for (std::size_t index = rows; index > 1; --index) {
        std::swap(order[index - 1], order[static_cast<std::size_t>(rng() % index)]);
      }
      for (std::size_t row = 0; row < rows; ++row) {
        columns[0][row] = static_cast<DataType>(order[row]);
      }
      break;
    }
  }
  return columns;
}

// --- expectations -----------------------------------------------------------

enum class TslCheckMode { Equal, AtMost, AtLeast };

struct TslCheck {
  std::string name;
  double expected = 0.0;
  double actual = 0.0;
  double tolerance = 0.0;  // absolute
  TslCheckMode mode = TslCheckMode::Equal;

  auto passed() const -> bool {
    switch (mode) {
      case TslCheckMode::Equal: return std::abs(actual - expected) <= tolerance;
      case TslCheckMode::AtMost: return actual <= expected + tolerance;
      case TslCheckMode::AtLeast: return actual >= expected - tolerance;
    }
    return false;
  }
};

// Closed-form expectations from the spec, compared against the measured
// descriptor. Only properties the shape actually promises are asserted.
inline auto tsl_expected_checks(
  TslDatasetSpec const & spec,
  TslDatasetDescriptor const & measured
) -> std::vector<TslCheck> {
  std::vector<TslCheck> checks;
  auto const rows = static_cast<double>(spec.rows);
  auto const columns = spec.columns;
  auto const last = columns - 1;
  auto const add = [&checks](std::string name, double expected, double actual,
                             double tolerance = 0.0, TslCheckMode mode = TslCheckMode::Equal) {
    checks.push_back(TslCheck{std::move(name), expected, actual, tolerance, mode});
  };
  auto const distinct = [&measured](std::size_t level) -> double {
    return level >= 1 && level <= measured.distinct_prefixes.size()
      ? static_cast<double>(measured.distinct_prefixes[level - 1])
      : -1.0;
  };

  add("rows", rows, static_cast<double>(measured.rows));
  add("columns", static_cast<double>(columns), static_cast<double>(measured.columns));

  switch (spec.shape) {
    case TslShape::UniqueFirst: {
      add("D_1 == N", rows, distinct(1));
      add("R_1 == 0", 0.0, static_cast<double>(measured.tied_rows[1]));
      add("W == m*N*log2(N)", static_cast<double>(columns) * rows * std::log2(rows),
          measured.weighted_work, 1e-6 * static_cast<double>(columns) * rows * std::log2(rows));
      break;
    }
    case TslShape::UniqueLast: {
      auto const group = std::max<std::size_t>(spec.integer_param("g", 2), 1);
      add("D_m == N", rows, distinct(columns));
      if (columns >= 2) {
        auto const expected_groups = static_cast<double>(
          spec.rows / group + (spec.rows % group != 0 ? 1 : 0)
        );
        add("D_{m-1} == ceil(N/g)", expected_groups, distinct(columns - 1));
        add("max group at level m-1 == g", static_cast<double>(group),
            static_cast<double>(measured.max_group[columns - 2]));
        add("R_{m-1} >= N - g", rows - static_cast<double>(group),
            static_cast<double>(measured.tied_rows[columns - 1]), 0.0, TslCheckMode::AtLeast);
      }
      break;
    }
    case TslShape::IndependentUniform: {
      auto const cardinality = static_cast<double>(std::max<std::size_t>(spec.integer_param("c", 4096), 1));
      // The document's saturation formula, not the naive c^j.
      auto const predicted = cardinality * (1.0 - std::exp(-rows / cardinality));
      add("D_1 == c(1-exp(-N/c))", predicted, distinct(1), 0.02 * predicted);
      break;
    }
    case TslShape::BalancedHierarchy: {
      auto const cardinality = std::max<std::size_t>(spec.integer_param("c", 16), 2);
      double product = 1.0;
      for (std::size_t level = 1; level <= columns; ++level) {
        product *= static_cast<double>(cardinality);
        add("D_" + std::to_string(level) + " == min(c^j, N)", std::min(product, rows),
            distinct(level));
      }
      break;
    }
    case TslShape::SkewedZipf: {
      auto const groups = std::max<std::size_t>(spec.integer_param("d1", 1024), 1);
      auto const sizes = tsl_split_zipf(spec.rows, groups, spec.param("s", 1.0));
      add("D_1 == d1", static_cast<double>(sizes.size()), distinct(1));
      add("largest level-1 group == zipf top",
          static_cast<double>(*std::max_element(sizes.begin(), sizes.end())),
          static_cast<double>(measured.max_group[0]));
      break;
    }
    case TslShape::HeavyHitter: {
      auto const heavy = std::llround(spec.param("frac", 0.9) * rows);
      add("largest level-1 group == frac*N", static_cast<double>(heavy),
          static_cast<double>(measured.max_group[0]));
      break;
    }
    case TslShape::LowCardinality: {
      auto const distinct_values = std::max<std::size_t>(spec.integer_param("d", 4), 1);
      add("D_1 == d", static_cast<double>(std::min(distinct_values, spec.rows)), distinct(1));
      auto const tuples = std::pow(static_cast<double>(distinct_values), static_cast<double>(columns));
      if (tuples * 2.0 <= rows) {
        add("all tuples duplicated", 1.0, measured.duplicate_tuple_fraction);
      }
      break;
    }
    case TslShape::AllEqualPrefix: {
      add("D_1 == 1", 1.0, distinct(1));
      if (columns >= 2) {
        add("D_2 == N", rows, distinct(2));
      }
      break;
    }
    case TslShape::CorrelatedForward: {
      if (columns >= 2) {
        add("D_2 == D_1", distinct(1), distinct(2));
        add("D_m == D_1", distinct(1), distinct(columns));
      }
      break;
    }
    case TslShape::CorrelatedReverse: {
      add("D_m == cardinality of finest column",
          static_cast<double>(measured.column_cardinality[last]), distinct(columns));
      add("coarsest column is coarser",
          static_cast<double>(measured.column_cardinality[last]),
          static_cast<double>(measured.column_cardinality[0]), 0.0, TslCheckMode::AtMost);
      break;
    }
    case TslShape::CorrelatedNoisy: {
      if (columns >= 2) {
        add("D_2 > D_1", distinct(1), distinct(2), 0.0, TslCheckMode::AtLeast);
      }
      break;
    }
    case TslShape::PrefixPresorted: {
      auto const prefix = std::min(spec.integer_param("p", 1), columns);
      if (prefix >= 1) {
        add("prefix " + std::to_string(prefix) + " fully in order", 1.0,
            measured.prefix_in_order_fraction[prefix - 1]);
      }
      if (prefix < columns) {
        add("full order not sorted", 1.0, measured.prefix_in_order_fraction[last],
            0.0, TslCheckMode::AtMost);
      }
      break;
    }
    case TslShape::ClusteredRuns: {
      auto const runs = std::max<std::size_t>(spec.integer_param("r", 64), 1);
      add("ascending runs == r", static_cast<double>(runs),
          static_cast<double>(measured.ascending_runs));
      break;
    }
    case TslShape::ReverseSorted: {
      add("no adjacent pair in order", 0.0, measured.prefix_in_order_fraction[last]);
      add("kendall distance == 1", 1.0, measured.kendall_normalized, 1e-9);
      break;
    }
    case TslShape::OrganPipe: {
      add("D_1 == ceil(N/2)", std::ceil(rows / 2.0), distinct(1));
      add("max level-1 group == 2", 2.0, static_cast<double>(measured.max_group[0]));
      break;
    }
    case TslShape::Sawtooth: {
      auto const teeth = std::max<std::size_t>(spec.integer_param("k", 1024), 1);
      add("D_1 == k", static_cast<double>(teeth), distinct(1));
      add("ascending runs == N/k", std::ceil(rows / static_cast<double>(teeth)),
          static_cast<double>(measured.ascending_runs));
      break;
    }
    case TslShape::DuplicatesAtPivot: {
      auto const heavy = std::llround(spec.param("frac", 0.5) * rows);
      add("largest level-1 group == frac*N", static_cast<double>(heavy),
          static_cast<double>(measured.max_group[0]));
      break;
    }
    case TslShape::ExtremeValues: {
      auto const group = std::max<std::size_t>(spec.integer_param("g", 64), 2);
      if (columns >= 2) {
        add("max group at level m-1 == g", static_cast<double>(group),
            static_cast<double>(measured.max_group[columns - 2]));
      }
      add("final column reaches zero", 0.0, static_cast<double>(measured.column_min[last]));
      auto const type_max = spec.element_bytes == 4
        ? static_cast<double>(std::numeric_limits<std::uint32_t>::max())
        : static_cast<double>(std::numeric_limits<std::uint64_t>::max());
      add("final column reaches the type maximum", type_max,
          static_cast<double>(measured.column_max[last]), 1.0);
      break;
    }
    case TslShape::PermutationLocal: {
      add("D_1 == N", rows, distinct(1));
      add("mean displacement == 1", 1.0, measured.mean_displacement, 1e-9);
      add("adjacency fraction == 0", 0.0, measured.adjacency_fraction, 1e-9);
      break;
    }
    case TslShape::PermutationBlocked: {
      auto const block = static_cast<double>(std::max<std::size_t>(spec.integer_param("block", 4096), 1));
      add("D_1 == N", rows, distinct(1));
      add("adjacency fraction == (block-1)/block", (block - 1.0) / block,
          measured.adjacency_fraction, 0.01);
      break;
    }
    case TslShape::PermutationRandom: {
      add("D_1 == N", rows, distinct(1));
      add("mean displacement == N/3", rows / 3.0, measured.mean_displacement, 0.05 * rows / 3.0);
      // A uniform permutation keeps an adjacent pair adjacent with probability
      // 1/N, so the expectation is 1/N rather than zero.
      add("adjacency fraction ~ 1/N", 0.0, measured.adjacency_fraction, 20.0 / rows);
      break;
    }
  }
  return checks;
}

// --- default catalog --------------------------------------------------------

inline auto tsl_default_catalog(std::size_t rows, std::size_t columns, std::size_t element_bytes)
  -> std::vector<TslDatasetSpec> {
  std::vector<TslDatasetSpec> catalog;
  auto const add = [&](TslShape shape, std::map<std::string, double> params,
                       std::string const & suffix) {
    TslDatasetSpec spec;
    spec.shape = shape;
    spec.rows = rows;
    spec.columns = columns;
    spec.element_bytes = element_bytes;
    spec.params = std::move(params);
    std::ostringstream id;
    id << tsl_shape_name(shape);
    if (!suffix.empty()) {
      id << '_' << suffix;
    }
    id << "_u" << (element_bytes * 8) << "_n" << rows << "_m" << columns;
    spec.id = id.str();
    catalog.push_back(std::move(spec));
  };

  add(TslShape::UniqueFirst, {}, "");
  // 2 is the smallest nontrivial group; 8..32 span 2L, 32..256 span the network
  // capacity C, the +1 values sit just above a capacity, and 4096 is the task
  // threshold. Together they cover every boundary of the six configurations.
  // Terminal group sizes: 2 is the smallest nontrivial group and 4096 the
  // default task threshold, both configuration-independent. The rest are the
  // 2L, C and C+1 of every (element width, register width) configuration:
  //
  //   u32/128 L=4  2L=8   C=64  C+1=65     u64/128 L=2  2L=4   C=32  C+1=33
  //   u32/256 L=8  2L=16  C=128 C+1=129    u64/256 L=4  2L=8   C=64  C+1=65
  //   u32/512 L=16 2L=32  C=256 C+1=257    u64/512 L=8  2L=16  C=128 C+1=129
  //
  // Register width therefore adds values here, never files: one directory
  // serves all six configurations. A size is only realizable if the levels
  // above it can still branch, hence room for at least eight groups.
  for (std::size_t group :
       {2u, 4u, 8u, 16u, 32u, 33u, 64u, 65u, 128u, 129u, 256u, 257u, 4096u}) {
    if (group * 8 <= rows) {
      add(TslShape::UniqueLast, {{"g", static_cast<double>(group)}}, "g" + std::to_string(group));
    }
  }
  for (std::size_t cardinality : {16u, 1024u, 65536u}) {
    add(TslShape::IndependentUniform, {{"c", static_cast<double>(cardinality)}},
        "c" + std::to_string(cardinality));
  }
  for (std::size_t cardinality : {16u, 64u}) {
    add(TslShape::BalancedHierarchy, {{"c", static_cast<double>(cardinality)}},
        "c" + std::to_string(cardinality));
  }
  add(TslShape::SkewedZipf, {{"d1", 1024}, {"s", 0.5}}, "s0.5");
  add(TslShape::SkewedZipf, {{"d1", 1024}, {"s", 1.0}}, "s1");
  add(TslShape::SkewedZipf, {{"d1", 1024}, {"s", 2.0}}, "s2");
  add(TslShape::HeavyHitter, {{"frac", 0.9}}, "f90");
  for (std::size_t distinct_values : {1u, 4u, 16u}) {
    add(TslShape::LowCardinality, {{"d", static_cast<double>(distinct_values)}},
        "d" + std::to_string(distinct_values));
  }
  add(TslShape::AllEqualPrefix, {}, "");
  // The query-67 rollup key. Only meaningful with enough columns to carry a
  // recognisable prefix of it.
  if (columns >= 4) {
    add(TslShape::TpcdsQ67, {{"sf", 1.0}}, "sf1");
    add(TslShape::TpcdsQ67, {{"sf", 100.0}}, "sf100");
  }
  add(TslShape::CorrelatedForward, {{"c", 4096}, {"shift", 4}}, "");
  add(TslShape::CorrelatedReverse, {{"shift", 4}}, "");
  add(TslShape::CorrelatedNoisy, {{"c", 4096}, {"noise", 16}}, "");
  add(TslShape::PrefixPresorted, {{"p", 1}}, "p1");
  if (columns >= 2) {
    add(TslShape::PrefixPresorted, {{"p", 2}}, "p2");
  }
  add(TslShape::PrefixPresorted, {{"p", static_cast<double>(columns)}}, "full");
  add(TslShape::ClusteredRuns, {{"r", 64}}, "r64");
  add(TslShape::ReverseSorted, {}, "");
  // OrganPipe and Sawtooth are implemented above but deliberately absent from the
  // default catalog: each is an existing group structure plus an existing
  // arrangement rather than new coverage, and neither is a pivot killer here.
  // Pivot selection (../sort_helpers.hpp) takes the pseudomedian of nine
  // samples, one per evenly spaced range with the offset inside each range
  // drawn from the task seed, so it has neither the fixed positions organ-pipe
  // data defeats nor a fixed stride a sawtooth period can align to. The legacy
  // benchmark keeps its own organ-pipe generator, so comparability is
  // unaffected.
  add(TslShape::DuplicatesAtPivot, {{"frac", 0.5}, {"c", 4096}}, "f50");
  add(TslShape::ExtremeValues, {{"g", 64}}, "g64");
  add(TslShape::PermutationLocal, {}, "");
  add(TslShape::PermutationBlocked, {{"block", 4096}}, "b4096");
  add(TslShape::PermutationRandom, {}, "");
  return catalog;
}
