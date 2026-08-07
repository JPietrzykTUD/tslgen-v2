#include <algorithm>
#include <array>
#include <atomic>
#include <condition_variable>
#include <cstddef>
#include <cstdint>
#include <functional>
#include <iostream>
#include <limits>
#include <mutex>
#include <numeric>
#include <random>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include <tsl.hpp>

#include "equal_runs.hpp"
#include "multicolumn_quicksort.hpp"
#include "multicolumn_sort_tasks.hpp"


namespace {

template <class DataType>
using columns_type = std::vector<std::vector<DataType>>;

void require(bool condition, std::string const & message) {
  if (!condition) {
    throw std::runtime_error(message);
  }
}

template <class DataType>
auto rows_from_columns(columns_type<DataType> const & columns)
  -> std::vector<std::vector<DataType>> {
  if (columns.empty()) {
    return {};
  }
  auto const row_count = columns.front().size();
  std::vector<std::vector<DataType>> rows(
    row_count,
    std::vector<DataType>(columns.size())
  );
  for (std::size_t column = 0; column < columns.size(); ++column) {
    require(columns[column].size() == row_count, "column lengths differ");
    for (std::size_t row = 0; row < row_count; ++row) {
      rows[row][column] = columns[column][row];
    }
  }
  return rows;
}

template <class DataType>
auto row_before(
  std::vector<DataType> const & left,
  std::vector<DataType> const & right,
  std::vector<TslSortOrder> const & orders
) -> bool {
  for (std::size_t column = 0; column < orders.size(); ++column) {
    if (left[column] == right[column]) {
      continue;
    }
    return orders[column] == TslSortOrder::ASCENDING
      ? left[column] < right[column]
      : left[column] > right[column];
  }
  return false;
}

template <class DataType>
auto column_specs(
  columns_type<DataType> & columns,
  std::vector<TslSortOrder> const & orders
) -> std::vector<TslSortColumn<DataType>> {
  require(columns.size() == orders.size(), "direction count differs from column count");
  std::vector<TslSortColumn<DataType>> result(columns.size());
  for (std::size_t column = 0; column < columns.size(); ++column) {
    result[column] = {columns[column].data(), orders[column]};
  }
  return result;
}

template <class Sorter, class DataType>
void verify_lexicographic_case(
  columns_type<DataType> input,
  std::vector<TslSortOrder> const & orders,
  TslRunDiscoveryKind discovery,
  std::string const & label
) {
  auto expected = rows_from_columns(input);
  std::sort(
    expected.begin(),
    expected.end(),
    [&](auto const & left, auto const & right) {
      return row_before(left, right, orders);
    }
  );

  auto specs = column_specs(input, orders);
  Sorter sorter(0x123456789abcdef0ULL);
  TslMultiColumnSortMetrics metrics;
  auto const row_count = input.empty() ? 0 : input.front().size();
  sorter.sort_columns(
    specs.data(),
    specs.size(),
    row_count,
    discovery,
    &metrics
  );
  auto const actual = rows_from_columns(input);
  if (actual != expected) {
    auto mismatch = std::mismatch(actual.begin(), actual.end(), expected.begin());
    auto const row = static_cast<std::size_t>(mismatch.first - actual.begin());
    auto format_row = [](auto const & values) {
      auto result = std::string{"["};
      for (std::size_t column = 0; column < values.size(); ++column) {
        if (column != 0) {
          result += ",";
        }
        result += std::to_string(values[column]);
      }
      return result + "]";
    };
    throw std::runtime_error(
      label + ": lexicographic mismatch at row " + std::to_string(row)
      + ", actual=" + format_row(*mismatch.first)
      + ", expected=" + format_row(*mismatch.second)
    );
  }
}

template <class Sorter, class DataType>
auto verify_parallel_case(
  columns_type<DataType> input,
  std::vector<TslSortOrder> const & orders,
  TslRunDiscoveryKind discovery,
  std::size_t worker_count,
  std::size_t task_threshold,
  std::string const & label,
  std::size_t partition_threshold = 0
) -> TslMultiColumnSortMetrics {
  auto expected = rows_from_columns(input);
  std::sort(
    expected.begin(),
    expected.end(),
    [&](auto const & left, auto const & right) {
      return row_before(left, right, orders);
    }
  );

  auto specs = column_specs(input, orders);
  Sorter sorter(0x123456789abcdef0ULL);
  TslMultiColumnSortMetrics metrics;
  auto const row_count = input.empty() ? 0 : input.front().size();
  sorter.sort_columns_parallel(
    specs.data(),
    specs.size(),
    row_count,
    worker_count,
    task_threshold,
    partition_threshold,
    discovery,
    &metrics
  );
  require(rows_from_columns(input) == expected, label + ": parallel result differs");
  if (row_count >= 2 && !input.empty()) {
    require(metrics.tasks_submitted >= 1, label + ": root task was not counted");
    require(metrics.max_outstanding_tasks >= 1, label + ": no outstanding task recorded");
    if (task_threshold > row_count && input.size() > 1) {
      require(
        metrics.tasks_executed_inline >= 1,
        label + ": large threshold did not execute child work inline"
      );
    }
    if (partition_threshold == 0) {
      require(
        metrics.partition_tasks_submitted == 0,
        label + ": partitions were offloaded without a partition threshold"
      );
    }
    require(
      metrics.partition_tasks_submitted <= metrics.tasks_submitted,
      label + ": partition tasks exceed submitted tasks"
    );
  }
  return metrics;
}

// Sealed discovery. The lexicographic comparison is a sufficient oracle for run
// decomposition: a missed run leaves the next column unsorted inside it, and a
// duplicated run sorts a range twice, which a wrong-order check would catch.
template <class Sorter, class DataType>
auto verify_sealed_case(
  columns_type<DataType> input,
  std::vector<TslSortOrder> const & orders,
  std::size_t worker_count,
  std::size_t task_threshold,
  std::size_t seal_threshold,
  std::string const & label
) -> TslMultiColumnSortMetrics {
  auto expected = rows_from_columns(input);
  std::sort(
    expected.begin(),
    expected.end(),
    [&](auto const & left, auto const & right) {
      return row_before(left, right, orders);
    }
  );

  auto specs = column_specs(input, orders);
  Sorter sorter(0x123456789abcdef0ULL);
  TslMultiColumnSortMetrics metrics;
  auto const row_count = input.empty() ? 0 : input.front().size();
  sorter.sort_columns_sealed_parallel(
    specs.data(),
    specs.size(),
    row_count,
    worker_count,
    task_threshold,
    seal_threshold,
    &metrics
  );
  require(rows_from_columns(input) == expected, label + ": sealed result differs");
  if (row_count >= 2 && input.size() > 1) {
    // Every row of a non-final column reaches the next column either through a
    // pivot-equal band or through a sealed scan. Neither counter may exceed the
    // row count of the column that produced it, and a scan that never happened
    // means the whole range was published as bands.
    require(
      metrics.sealed_ranges == 0
        || metrics.sealed_range_rows >= metrics.sealed_ranges * 2,
      label + ": sealed ranges smaller than the minimum run length"
    );
    require(
      metrics.rle_values_scanned == metrics.sealed_range_rows,
      label + ": scanned values disagree with sealed range rows"
    );
    require(
      metrics.partition_tasks_submitted <= metrics.tasks_submitted,
      label + ": partition tasks exceed submitted tasks"
    );
  }
  return metrics;
}

template <class Sorter, class DataType>
void verify_active_key_case(
  std::vector<DataType> keys,
  TslSortOrder order,
  std::string const & label,
  std::uint64_t seed = 0x9e3779b97f4a7c15ULL
) {
  auto const original_keys = keys;
  std::vector<DataType> row_id(keys.size());
  std::vector<DataType> derived(keys.size());
  for (std::size_t index = 0; index < keys.size(); ++index) {
    row_id[index] = static_cast<DataType>(index);
    derived[index] = static_cast<DataType>(index * 3 + 1);
  }
  std::array<DataType *, 2> payloads{row_id.data(), derived.data()};
  Sorter sorter(seed);
  sorter.sort_key(keys.data(), payloads.data(), payloads.size(), keys.size(), order);

  auto const sorted = order == TslSortOrder::ASCENDING
    ? std::is_sorted(keys.begin(), keys.end())
    : std::is_sorted(keys.begin(), keys.end(), std::greater<DataType>{});
  require(sorted, label + ": active key has the wrong order");
  std::vector<char> seen(keys.size(), 0);
  for (std::size_t position = 0; position < keys.size(); ++position) {
    auto const origin = static_cast<std::size_t>(row_id[position]);
    require(origin < keys.size(), label + ": invalid row id");
    require(!seen[origin], label + ": duplicate row id");
    seen[origin] = 1;
    require(keys[position] == original_keys[origin], label + ": key/payload split");
    require(
      derived[position] == static_cast<DataType>(origin * 3 + 1),
      label + ": payloads used different permutations"
    );
  }
}

void test_equal_runs() {
  auto verify = [](
    std::vector<std::uint32_t> const & values,
    std::size_t begin,
    std::size_t end,
    std::vector<TslRunSpan> const & expected
  ) {
    std::vector<TslRunSpan> actual;
    tsl_for_each_equal_run(values.data(), begin, end, [&](TslRunSpan span) {
      actual.push_back(span);
    });
    require(actual.size() == expected.size(), "equal-run span count differs");
    for (std::size_t index = 0; index < actual.size(); ++index) {
      require(
        actual[index].begin == expected[index].begin
          && actual[index].end == expected[index].end,
        "equal-run span differs"
      );
    }
  };

  verify({}, 0, 0, {});
  verify({7}, 0, 1, {});
  verify({1, 2, 3, 4}, 0, 4, {});
  verify({5, 5, 5, 5}, 0, 4, {{0, 4}});
  verify({1, 1, 2, 3}, 0, 4, {{0, 2}});
  verify({1, 2, 3, 3}, 0, 4, {{2, 4}});
  verify({9, 9, 8, 7, 7, 6}, 0, 6, {{0, 2}, {3, 5}});
  verify({0, 4, 4, 3, 2, 2, 1, 0}, 1, 7, {{1, 3}, {4, 6}});

  std::mt19937_64 rng(0xeeeeULL);
  for (std::size_t trial = 0; trial < 100; ++trial) {
    std::vector<std::uint32_t> values(3 + rng() % 300);
    for (auto & value : values) {
      value = static_cast<std::uint32_t>(rng() % (1 + trial % 23));
    }
    std::sort(values.begin(), values.end());
    if (trial % 2 != 0) {
      std::reverse(values.begin(), values.end());
    }
    auto const begin = std::size_t{1};
    auto const end = values.size() - 1;
    std::vector<TslRunSpan> actual;
    tsl_for_each_equal_run(values.data(), begin, end, [&](TslRunSpan span) {
      actual.push_back(span);
    });
    std::vector<TslRunSpan> expected;
    auto cursor = begin;
    while (cursor < end) {
      auto run_end = cursor + 1;
      while (run_end < end && values[run_end] == values[cursor]) {
        ++run_end;
      }
      if (run_end - cursor > 1) {
        expected.push_back({cursor, run_end});
      }
      cursor = run_end;
    }
    require(actual.size() == expected.size(), "random equal-run count differs");
    for (std::size_t index = 0; index < actual.size(); ++index) {
      require(
        actual[index].begin == expected[index].begin
          && actual[index].end == expected[index].end,
        "random equal-run span differs"
      );
    }
  }
}

template <class DataType>
auto make_random_columns(
  std::size_t column_count,
  std::size_t row_count,
  std::uint64_t seed,
  std::uint64_t cardinality
) -> columns_type<DataType> {
  std::mt19937_64 rng(seed);
  columns_type<DataType> columns(column_count, std::vector<DataType>(row_count));
  for (std::size_t column = 0; column < column_count; ++column) {
    for (auto & value : columns[column]) {
      value = static_cast<DataType>(
        cardinality == 0 ? rng() : rng() % cardinality
      );
    }
  }
  return columns;
}

template <class Sorter>
void run_sorter_matrix(std::string const & name, bool incremental) {
  using DataType = std::uint32_t;
  auto const post = TslRunDiscoveryKind::POST_SORT;
  auto const discovery = incremental ? TslRunDiscoveryKind::INCREMENTAL : post;

  verify_active_key_case<Sorter, DataType>(
    {9, 1, 4, 4, 0, std::numeric_limits<DataType>::max(), 7, 1},
    TslSortOrder::ASCENDING,
    name + "/active-asc"
  );
  verify_active_key_case<Sorter, DataType>(
    {9, 1, 4, 4, 0, std::numeric_limits<DataType>::max(), 7, 1},
    TslSortOrder::DESCENDING,
    name + "/active-desc"
  );
  verify_active_key_case<Sorter, DataType>(
    make_random_columns<DataType>(
      1,
      Sorter::leaf_size_threshold() + 19,
      0x515151ULL,
      17
    )[0],
    TslSortOrder::ASCENDING,
    name + "/active-second-seed",
    0x0123456789abcdefULL
  );
  verify_lexicographic_case<Sorter>(
    columns_type<DataType>{{4, 1, 4, 0, 9, 2}},
    {TslSortOrder::ASCENDING},
    discovery,
    name + "/one-column-asc"
  );
  verify_lexicographic_case<Sorter>(
    columns_type<DataType>{{4, 1, 4, 0, 9, 2}},
    {TslSortOrder::DESCENDING},
    discovery,
    name + "/one-column-desc"
  );

  columns_type<DataType> worked{
    {2, 1, 1, 1, 2, 1},
    {1, 3, 3, 2, 1, 2},
    {7, 9, 4, 8, 5, 6},
  };
  verify_lexicographic_case<Sorter>(
    worked,
    {
      TslSortOrder::ASCENDING,
      TslSortOrder::DESCENDING,
      TslSortOrder::ASCENDING,
    },
    discovery,
    name + "/worked"
  );
  verify_lexicographic_case<Sorter>(
    worked,
    std::vector<TslSortOrder>(3, TslSortOrder::DESCENDING),
    discovery,
    name + "/worked-all-desc"
  );

  auto all_equal = columns_type<DataType>(
    3,
    std::vector<DataType>(129, DataType{7})
  );
  verify_lexicographic_case<Sorter>(
    all_equal,
    {
      TslSortOrder::ASCENDING,
      TslSortOrder::DESCENDING,
      TslSortOrder::ASCENDING,
    },
    discovery,
    name + "/all-equal"
  );

  auto pivot_crossing = columns_type<DataType>(
    3,
    std::vector<DataType>(Sorter::leaf_size_threshold() + 33)
  );
  std::fill(pivot_crossing[0].begin(), pivot_crossing[0].end(), 2);
  for (std::size_t row = 0; row < pivot_crossing[0].size(); ++row) {
    pivot_crossing[1][row] = static_cast<DataType>(
      pivot_crossing[0].size() - row
    );
    pivot_crossing[2][row] = static_cast<DataType>(row);
  }
  verify_lexicographic_case<Sorter>(
    pivot_crossing,
    {
      TslSortOrder::ASCENDING,
      TslSortOrder::DESCENDING,
      TslSortOrder::ASCENDING,
    },
    discovery,
    name + "/pivot-crossing-run"
  );

  std::vector<std::size_t> sizes{
    0,
    1,
    2,
    3,
    4,
    5,
    7,
    8,
    9,
    15,
    16,
    17,
    63,
    64,
    65,
    Sorter::leaf_size_threshold() - 1,
    Sorter::leaf_size_threshold(),
    Sorter::leaf_size_threshold() + 1,
    513,
  };
  std::sort(sizes.begin(), sizes.end());
  sizes.erase(std::unique(sizes.begin(), sizes.end()), sizes.end());
  for (auto const size : sizes) {
    auto const columns = make_random_columns<DataType>(
      3,
      size,
      0xc0ffeeULL ^ size,
      size % 2 == 0 ? 11 : 0
    );
    verify_lexicographic_case<Sorter>(
      columns,
      {
        TslSortOrder::ASCENDING,
        TslSortOrder::DESCENDING,
        TslSortOrder::ASCENDING,
      },
      discovery,
      name + "/size-" + std::to_string(size)
    );
  }

  for (auto const cardinality : {std::uint64_t{0}, std::uint64_t{4}, std::uint64_t{32}}) {
    auto const columns = make_random_columns<DataType>(
      5,
      1024,
      0x5eedULL ^ cardinality,
      cardinality
    );
    verify_lexicographic_case<Sorter>(
      columns,
      std::vector<TslSortOrder>(5, TslSortOrder::ASCENDING),
      discovery,
      name + "/random-asc-" + std::to_string(cardinality)
    );
    verify_lexicographic_case<Sorter>(
      columns,
      {
        TslSortOrder::DESCENDING,
        TslSortOrder::ASCENDING,
        TslSortOrder::DESCENDING,
        TslSortOrder::ASCENDING,
        TslSortOrder::DESCENDING,
      },
      discovery,
      name + "/random-alternating-" + std::to_string(cardinality)
    );
    verify_lexicographic_case<Sorter>(
      columns,
      {
        TslSortOrder::DESCENDING,
        TslSortOrder::DESCENDING,
        TslSortOrder::ASCENDING,
        TslSortOrder::DESCENDING,
        TslSortOrder::ASCENDING,
      },
      discovery,
      name + "/random-directions-" + std::to_string(cardinality)
    );
  }

  auto patterned = columns_type<DataType>(3, std::vector<DataType>(257));
  for (std::size_t row = 0; row < 257; ++row) {
    patterned[0][row] = static_cast<DataType>(row);
    patterned[1][row] = static_cast<DataType>(row % 17);
    patterned[2][row] = static_cast<DataType>((row * 7) % 23);
  }
  verify_lexicographic_case<Sorter>(
    patterned,
    {
      TslSortOrder::ASCENDING,
      TslSortOrder::DESCENDING,
      TslSortOrder::ASCENDING,
    },
    discovery,
    name + "/ascending"
  );
  std::reverse(patterned[0].begin(), patterned[0].end());
  verify_lexicographic_case<Sorter>(
    patterned,
    {
      TslSortOrder::ASCENDING,
      TslSortOrder::DESCENDING,
      TslSortOrder::ASCENDING,
    },
    discovery,
    name + "/descending"
  );
  std::swap(patterned[0][31], patterned[0][32]);
  std::swap(patterned[0][190], patterned[0][193]);
  verify_lexicographic_case<Sorter>(
    patterned,
    {
      TslSortOrder::ASCENDING,
      TslSortOrder::DESCENDING,
      TslSortOrder::ASCENDING,
    },
    discovery,
    name + "/nearly-sorted"
  );
  for (std::size_t row = 0; row < 257; ++row) {
    patterned[0][row] = static_cast<DataType>(
      row <= 128 ? row : 256 - row
    );
  }
  verify_lexicographic_case<Sorter>(
    patterned,
    {
      TslSortOrder::ASCENDING,
      TslSortOrder::DESCENDING,
      TslSortOrder::ASCENDING,
    },
    discovery,
    name + "/organ-pipe"
  );

  verify_lexicographic_case<Sorter>(
    make_random_columns<DataType>(16, 128, 0x1616ULL, 5),
    std::vector<TslSortOrder>{
      TslSortOrder::ASCENDING, TslSortOrder::DESCENDING,
      TslSortOrder::ASCENDING, TslSortOrder::DESCENDING,
      TslSortOrder::ASCENDING, TslSortOrder::DESCENDING,
      TslSortOrder::ASCENDING, TslSortOrder::DESCENDING,
      TslSortOrder::ASCENDING, TslSortOrder::DESCENDING,
      TslSortOrder::ASCENDING, TslSortOrder::DESCENDING,
      TslSortOrder::ASCENDING, TslSortOrder::DESCENDING,
      TslSortOrder::ASCENDING, TslSortOrder::DESCENDING,
    },
    discovery,
    name + "/max-columns"
  );
}

void test_argument_validation() {
  using Sorter = TslMultiColumnQuickSorter<
    std::uint32_t,
    TslPartitionKind::THREE_WAY,
    TslLeafKind::INSERTION,
    4
  >;
  Sorter sorter(1);
  sorter.sort_columns(nullptr, 0, 100);
  sorter.sort_columns(nullptr, 3, 0);
  sorter.sort_key(nullptr, nullptr, 3, 0, TslSortOrder::ASCENDING);

  std::array<std::vector<std::uint32_t>, 5> values;
  std::array<TslSortColumn<std::uint32_t>, 5> columns{};
  for (std::size_t column = 0; column < columns.size(); ++column) {
    values[column].resize(2);
    columns[column] = {values[column].data(), TslSortOrder::ASCENDING};
  }
  auto rejected = false;
  try {
    sorter.sort_columns(columns.data(), columns.size(), 2);
  } catch (std::invalid_argument const &) {
    rejected = true;
  }
  require(rejected, "column count above MaxColumns was accepted");

  rejected = false;
  try {
    sorter.sort_columns(nullptr, 1, 2);
  } catch (std::invalid_argument const &) {
    rejected = true;
  }
  require(rejected, "null sort-column array was accepted");

  auto null_column = TslSortColumn<std::uint32_t>{
    nullptr,
    TslSortOrder::ASCENDING,
  };
  rejected = false;
  try {
    sorter.sort_columns(&null_column, 1, 2);
  } catch (std::invalid_argument const &) {
    rejected = true;
  }
  require(rejected, "null column data was accepted");

  std::array<std::uint32_t *, 5> payloads{};
  std::array<std::uint32_t, 2> keys{};
  rejected = false;
  try {
    sorter.sort_key(
      keys.data(),
      payloads.data(),
      payloads.size(),
      keys.size(),
      TslSortOrder::ASCENDING
    );
  } catch (std::invalid_argument const &) {
    rejected = true;
  }
  require(rejected, "payload count above MaxColumns was accepted");

  std::array<std::uint32_t *, 1> alias{keys.data()};
  rejected = false;
  try {
    sorter.sort_key(
      keys.data(),
      alias.data(),
      alias.size(),
      keys.size(),
      TslSortOrder::ASCENDING
    );
  } catch (std::invalid_argument const &) {
    rejected = true;
  }
  require(rejected, "active key/payload alias was accepted");

  std::array<std::uint32_t, 2> payload{};
  std::array<std::uint32_t *, 2> duplicate_payloads{
    payload.data(),
    payload.data(),
  };
  rejected = false;
  try {
    sorter.sort_key(
      keys.data(),
      duplicate_payloads.data(),
      duplicate_payloads.size(),
      keys.size(),
      TslSortOrder::ASCENDING
    );
  } catch (std::invalid_argument const &) {
    rejected = true;
  }
  require(rejected, "duplicate payload aliases were accepted");

  std::array<TslSortColumn<std::uint32_t>, 2> duplicate_columns{{
    {keys.data(), TslSortOrder::ASCENDING},
    {keys.data(), TslSortOrder::DESCENDING},
  }};
  rejected = false;
  try {
    sorter.sort_columns(duplicate_columns.data(), duplicate_columns.size(), keys.size());
  } catch (std::invalid_argument const &) {
    rejected = true;
  }
  require(rejected, "duplicate sort-column aliases were accepted");

  rejected = false;
  try {
    sorter.sort_columns_parallel(
      columns.data(),
      2,
      2,
      0,
      2,
      0,
      TslRunDiscoveryKind::POST_SORT
    );
  } catch (std::invalid_argument const &) {
    rejected = true;
  }
  require(rejected, "zero-worker parallel sort was accepted");
}

void test_discovery_fallback_and_last_column_scan() {
  using Sorter = TslMultiColumnQuickSorter<
    std::uint32_t,
    TslPartitionKind::TWO_WAY,
    TslLeafKind::INSERTION
  >;
  auto columns = make_random_columns<std::uint32_t>(3, 513, 0xfafaULL, 7);
  auto const orders = std::vector<TslSortOrder>{
    TslSortOrder::ASCENDING,
    TslSortOrder::DESCENDING,
    TslSortOrder::ASCENDING,
  };
  verify_lexicographic_case<Sorter>(
    columns,
    orders,
    TslRunDiscoveryKind::INCREMENTAL,
    "two-way/incremental-falls-back-to-post"
  );

  auto one_column = make_random_columns<std::uint32_t>(1, 513, 0xaaaaULL, 4);
  auto specs = column_specs(
    one_column,
    std::vector<TslSortOrder>{TslSortOrder::ASCENDING}
  );
  Sorter sorter(1);
  TslMultiColumnSortMetrics metrics;
  sorter.sort_columns(
    specs.data(),
    specs.size(),
    one_column.front().size(),
    TslRunDiscoveryKind::POST_SORT,
    &metrics
  );
  require(metrics.rle_values_scanned == 0, "last sort column was unnecessarily scanned");
}

void test_u64_network() {
  using DataType = std::uint64_t;
  using Sorter = TslMultiColumnQuickSorter<
    DataType,
    TslPartitionKind::THREE_WAY,
    TslLeafKind::NETWORK
  >;
  auto columns = make_random_columns<DataType>(
    3,
    Sorter::leaf_size_threshold() + 17,
    0xabcdefULL,
    13
  );
  verify_lexicographic_case<Sorter>(
    columns,
    {
      TslSortOrder::DESCENDING,
      TslSortOrder::ASCENDING,
      TslSortOrder::DESCENDING,
    },
    TslRunDiscoveryKind::INCREMENTAL,
    "u64/three-way-network"
  );
}

void test_u64_variants() {
  using DataType = std::uint64_t;
  using TwoWayInsertion = TslMultiColumnQuickSorter<
    DataType,
    TslPartitionKind::TWO_WAY,
    TslLeafKind::INSERTION
  >;
  using TwoWayNetwork = TslMultiColumnQuickSorter<
    DataType,
    TslPartitionKind::TWO_WAY,
    TslLeafKind::NETWORK
  >;
  using ThreeWayInsertion = TslMultiColumnQuickSorter<
    DataType,
    TslPartitionKind::THREE_WAY,
    TslLeafKind::INSERTION
  >;
  using ThreeWayNetwork = TslMultiColumnQuickSorter<
    DataType,
    TslPartitionKind::THREE_WAY,
    TslLeafKind::NETWORK
  >;
  auto const columns = make_random_columns<DataType>(3, 513, 0x6464ULL, 19);
  auto const orders = std::vector<TslSortOrder>{
    TslSortOrder::DESCENDING,
    TslSortOrder::ASCENDING,
    TslSortOrder::DESCENDING,
  };
  verify_lexicographic_case<TwoWayInsertion>(
    columns, orders, TslRunDiscoveryKind::POST_SORT, "u64/two-way-insertion"
  );
  verify_lexicographic_case<TwoWayNetwork>(
    columns, orders, TslRunDiscoveryKind::POST_SORT, "u64/two-way-network"
  );
  verify_lexicographic_case<ThreeWayInsertion>(
    columns, orders, TslRunDiscoveryKind::POST_SORT, "u64/three-way-insertion/post"
  );
  verify_lexicographic_case<ThreeWayNetwork>(
    columns, orders, TslRunDiscoveryKind::POST_SORT, "u64/three-way-network/post"
  );
  verify_lexicographic_case<ThreeWayInsertion>(
    columns,
    orders,
    TslRunDiscoveryKind::INCREMENTAL,
    "u64/three-way-insertion/incremental"
  );
  verify_lexicographic_case<ThreeWayNetwork>(
    columns,
    orders,
    TslRunDiscoveryKind::INCREMENTAL,
    "u64/three-way-network/incremental"
  );
}

template <class Sorter>
void run_sealed_matrix(std::string const & name) {
  auto const orders = std::vector<TslSortOrder>{
    TslSortOrder::ASCENDING,
    TslSortOrder::DESCENDING,
    TslSortOrder::ASCENDING,
    TslSortOrder::DESCENDING,
  };
  auto const leaf = Sorter::leaf_size_threshold();
  // Seals spanning the clamp boundary, a mid-range value, the whole input, and
  // more than the whole input: the last two must degenerate to one sealed range
  // rather than fail.
  std::vector<std::size_t> const seals{
    1, leaf, leaf + 1, 257, 2048, 4096
  };
  for (auto const workers : {std::size_t{1}, std::size_t{2}, std::size_t{4}}) {
    for (auto const threshold : {std::size_t{2}, std::size_t{100000}}) {
      for (auto const seal : seals) {
        verify_sealed_case<Sorter>(
          make_random_columns<std::uint32_t>(4, 2048, 0x77ULL, 8),
          orders,
          workers,
          threshold,
          seal,
          name + "/workers-" + std::to_string(workers)
            + "/threshold-" + std::to_string(threshold)
            + "/seal-" + std::to_string(seal)
        );
      }
    }
  }

  // Cardinality extremes. All-equal keys make every range one pivot-equal band,
  // so no scan should ever run; all-distinct keys make every range a seal.
  auto all_equal = make_random_columns<std::uint32_t>(4, 2048, 0x88ULL, 0);
  for (auto & column : all_equal) {
    std::fill(column.begin(), column.end(), 7);
  }
  auto const equal_metrics = verify_sealed_case<Sorter>(
    all_equal, orders, 4, 2, 257, name + "/all-equal"
  );
  require(
    equal_metrics.direct_equal_bands >= 1,
    name + "/all-equal: no pivot-equal band was published"
  );

  auto distinct = make_random_columns<std::uint32_t>(4, 2048, 0x99ULL, 0);
  verify_sealed_case<Sorter>(distinct, orders, 4, 2, 257, name + "/all-distinct");

  // Degenerate ranges.
  verify_sealed_case<Sorter>(
    make_random_columns<std::uint32_t>(2, 0, 0xA1ULL, 4), {
      TslSortOrder::ASCENDING, TslSortOrder::ASCENDING
    }, 2, 2, 257, name + "/empty"
  );
  verify_sealed_case<Sorter>(
    make_random_columns<std::uint32_t>(2, 1, 0xA2ULL, 4), {
      TslSortOrder::ASCENDING, TslSortOrder::ASCENDING
    }, 2, 2, 257, name + "/single-row"
  );
  verify_sealed_case<Sorter>(
    make_random_columns<std::uint32_t>(1, 4096, 0xA3ULL, 16), {
      TslSortOrder::ASCENDING
    }, 4, 2, 257, name + "/single-column"
  );

  // The design claim: a seal well below the row count must both distribute
  // partitions and produce many scan ranges. Without this a silent degeneration
  // to one serial seal would still pass every ordering check above.
  auto const three_orders = std::vector<TslSortOrder>{
    TslSortOrder::ASCENDING,
    TslSortOrder::DESCENDING,
    TslSortOrder::ASCENDING,
  };
  auto wide = make_random_columns<std::uint32_t>(3, 200000, 0xB1ULL, 512);
  auto const wide_metrics = verify_sealed_case<Sorter>(
    wide, three_orders, 4, 4096, 8192, name + "/distributed"
  );
  require(
    wide_metrics.partition_tasks_submitted >= 2,
    name + "/distributed: partitions were not offloaded to other workers"
  );
  require(
    wide_metrics.sealed_ranges >= 2,
    name + "/distributed: the range was not split into several sealed scans"
  );
  require(
    wide_metrics.sealed_range_rows / wide_metrics.sealed_ranges > leaf,
    name + "/distributed: mean sealed range collapsed to leaf size"
  );

  // A seal at or above the row count leaves exactly one sealed range and no
  // partition offload: correct, just serial.
  auto const two_orders = std::vector<TslSortOrder>{
    TslSortOrder::ASCENDING,
    TslSortOrder::DESCENDING,
  };
  auto whole = make_random_columns<std::uint32_t>(2, 4096, 0xB2ULL, 64);
  auto const whole_metrics = verify_sealed_case<Sorter>(
    whole, two_orders, 4, 100000, 1u << 20, name + "/seal-exceeds-input"
  );
  require(
    whole_metrics.partition_tasks_submitted == 0,
    name + "/seal-exceeds-input: partitions offloaded below the seal threshold"
  );
  require(
    whole_metrics.sealed_ranges == 1,
    name + "/seal-exceeds-input: expected exactly one sealed range"
  );
}

template <class Sorter>
void run_parallel_matrix(
  std::string const & name,
  TslRunDiscoveryKind discovery
) {
  auto const orders = std::vector<TslSortOrder>{
    TslSortOrder::ASCENDING,
    TslSortOrder::DESCENDING,
    TslSortOrder::ASCENDING,
    TslSortOrder::DESCENDING,
  };
  for (auto const workers : {std::size_t{1}, std::size_t{2}, std::size_t{4}}) {
    for (auto const threshold : {std::size_t{2}, std::size_t{100000}}) {
      for (auto const partitions : {std::size_t{0}, std::size_t{2}}) {
        verify_parallel_case<Sorter>(
          make_random_columns<std::uint32_t>(4, 2048, 0x77ULL, 8),
          orders,
          discovery,
          workers,
          threshold,
          name + "/workers-" + std::to_string(workers)
            + "/threshold-" + std::to_string(threshold)
            + "/partitions-" + std::to_string(partitions),
          partitions
        );
      }
    }
  }

  auto one_large_run = make_random_columns<std::uint32_t>(4, 1024, 0x88ULL, 0);
  std::fill(one_large_run[0].begin(), one_large_run[0].end(), 3);
  std::fill(one_large_run[1].begin(), one_large_run[1].end(), 5);
  for (auto const partitions : {std::size_t{0}, std::size_t{2}}) {
    verify_parallel_case<Sorter>(
      one_large_run,
      orders,
      discovery,
      4,
      2,
      name + "/large-prefix-run/partitions-" + std::to_string(partitions),
      partitions
    );
  }

  // A single column is the final column, so its partitions carry no whole-range
  // obligation and are offloaded under every discovery mode. This is the only
  // source of parallelism for a one-column sort.
  auto single = make_random_columns<std::uint32_t>(1, 8192, 0x99ULL, 0);
  auto single_specs = column_specs(single, std::vector<TslSortOrder>{
    TslSortOrder::ASCENDING,
  });
  Sorter single_sorter(0x123456789abcdef0ULL);
  TslMultiColumnSortMetrics single_metrics;
  single_sorter.sort_columns_parallel(
    single_specs.data(),
    single_specs.size(),
    single.front().size(),
    4,
    2,
    2,
    discovery,
    &single_metrics
  );
  require(
    std::is_sorted(single.front().begin(), single.front().end()),
    name + "/single-column: output is unsorted"
  );
  require(
    single_metrics.partition_tasks_submitted >= 1,
    name + "/single-column: no partition range was offloaded"
  );
}

void test_task_executor() {
  std::atomic<int> sum{0};
  auto worker = [&](int task, auto &) {
    sum.fetch_add(task, std::memory_order_relaxed);
  };
  TslTaskExecutor<int, decltype(worker)> executor(3, worker);
  for (auto task = 1; task <= 20; ++task) {
    executor.submit(task);
  }
  executor.wait();
  require(sum.load(std::memory_order_relaxed) == 210, "task executor lost work");
  require(executor.metrics().tasks_submitted == 20, "task submission metric differs");

  auto failing_worker = [](int task, auto &) {
    if (task == 7) {
      throw std::runtime_error("injected task failure");
    }
  };
  auto propagated = false;
  try {
    TslTaskExecutor<int, decltype(failing_worker)> failing(2, failing_worker);
    failing.submit(7);
    failing.wait();
  } catch (std::runtime_error const & error) {
    propagated = std::string{error.what()} == "injected task failure";
  }
  require(propagated, "task executor did not propagate the worker exception");

  std::mutex completion_mutex;
  std::condition_variable completion_ready;
  bool second_finished = false;
  std::vector<int> completion_order;
  auto reordered_worker = [&](int task, auto &) {
    if (task == 0) {
      std::unique_lock<std::mutex> lock(completion_mutex);
      completion_ready.wait(lock, [&] { return second_finished; });
      completion_order.push_back(0);
    } else {
      {
        std::lock_guard<std::mutex> lock(completion_mutex);
        second_finished = true;
        completion_order.push_back(1);
      }
      completion_ready.notify_one();
    }
  };
  TslTaskExecutor<int, decltype(reordered_worker)> reordered(2, reordered_worker);
  reordered.submit(0);
  reordered.submit(1);
  reordered.wait();
  require(
    completion_order == std::vector<int>({1, 0}),
    "task executor depended on discovery-order completion"
  );
}

template <class Sorter>
void verify_incremental_decomposition(
  std::vector<std::uint32_t> keys,
  TslSortOrder order,
  std::string const & label
) {
  struct piece {
    std::size_t begin;
    std::size_t end;
    bool equal_band;
  };

  auto constexpr absolute_begin = std::size_t{17};
  std::vector<piece> pieces;
  std::vector<TslRunSpan> incremental_runs;
  auto on_equal_band = [&](std::size_t begin, std::size_t end) {
    pieces.push_back({begin, end, true});
    if (end - begin > 1) {
      incremental_runs.push_back({begin, end});
    }
  };
  auto on_leaf = [&](std::size_t begin, std::size_t end) {
    pieces.push_back({begin, end, false});
  };

  Sorter sorter(0x1111222233334444ULL);
  sorter.sort_key_with_completion_events(
    keys.data(),
    nullptr,
    0,
    keys.size(),
    order,
    absolute_begin,
    on_equal_band,
    on_leaf
  );

  auto const sorted = order == TslSortOrder::ASCENDING
    ? std::is_sorted(keys.begin(), keys.end())
    : std::is_sorted(keys.begin(), keys.end(), std::greater<std::uint32_t>{});
  require(sorted, label + ": structurally observed key is not sorted");

  std::sort(pieces.begin(), pieces.end(), [](piece const & left, piece const & right) {
    return left.begin < right.begin;
  });
  auto cursor = absolute_begin;
  for (std::size_t index = 0; index < pieces.size(); ++index) {
    auto const current = pieces[index];
    require(current.begin == cursor, label + ": completion pieces overlap or have a gap");
    require(current.end > current.begin, label + ": empty completion piece");
    if (current.equal_band) {
      auto const local_begin = current.begin - absolute_begin;
      auto const local_end = current.end - absolute_begin;
      require(
        std::all_of(
          keys.begin() + static_cast<std::ptrdiff_t>(local_begin),
          keys.begin() + static_cast<std::ptrdiff_t>(local_end),
          [&](std::uint32_t value) { return value == keys[local_begin]; }
        ),
        label + ": reported equal band contains different keys"
      );
    } else if (current.end - current.begin > 1) {
      tsl_for_each_equal_run(
        keys.data(),
        current.begin - absolute_begin,
        current.end - absolute_begin,
        [&](TslRunSpan span) {
          incremental_runs.push_back({
            span.begin + absolute_begin,
            span.end + absolute_begin,
          });
        }
      );
    }
    if (index + 1 < pieces.size()) {
      auto const next = pieces[index + 1];
      require(
        keys[current.end - absolute_begin - 1]
          != keys[next.begin - absolute_begin],
        label + ": equal values cross completion-piece boundaries"
      );
    }
    cursor = current.end;
  }
  require(
    cursor == absolute_begin + keys.size(),
    label + ": completion pieces do not cover the key range"
  );

  std::vector<TslRunSpan> reference_runs;
  tsl_for_each_equal_run(keys.data(), 0, keys.size(), [&](TslRunSpan span) {
    reference_runs.push_back({
      span.begin + absolute_begin,
      span.end + absolute_begin,
    });
  });
  auto span_before = [](TslRunSpan left, TslRunSpan right) {
    return left.begin < right.begin;
  };
  std::sort(incremental_runs.begin(), incremental_runs.end(), span_before);
  require(
    incremental_runs.size() == reference_runs.size(),
    label + ": incremental run count differs from full RLE"
  );
  for (std::size_t index = 0; index < reference_runs.size(); ++index) {
    require(
      incremental_runs[index].begin == reference_runs[index].begin
        && incremental_runs[index].end == reference_runs[index].end,
      label + ": incremental span differs from full RLE"
    );
  }
}

void test_incremental_decomposition() {
  using Insertion = TslMultiColumnQuickSorter<
    std::uint32_t,
    TslPartitionKind::THREE_WAY,
    TslLeafKind::INSERTION
  >;
  using Network = TslMultiColumnQuickSorter<
    std::uint32_t,
    TslPartitionKind::THREE_WAY,
    TslLeafKind::NETWORK
  >;
  for (auto const order : {
    TslSortOrder::ASCENDING,
    TslSortOrder::DESCENDING,
  }) {
    verify_incremental_decomposition<Insertion>(
      make_random_columns<std::uint32_t>(
        1,
        Insertion::leaf_size_threshold() * 8 + 7,
        0x1234ULL,
        13
      )[0],
      order,
      "decomposition/insertion"
    );
    verify_incremental_decomposition<Network>(
      make_random_columns<std::uint32_t>(
        1,
        Network::leaf_size_threshold() * 3 + 7,
        0x5678ULL,
        17
      )[0],
      order,
      "decomposition/network"
    );
    verify_incremental_decomposition<Insertion>(
      std::vector<std::uint32_t>(257, 9),
      order,
      "decomposition/all-equal"
    );
    auto unique = std::vector<std::uint32_t>(
      Insertion::leaf_size_threshold() * 4 + 3
    );
    std::iota(unique.begin(), unique.end(), 0u);
    std::mt19937 shuffle_rng(123);
    std::shuffle(unique.begin(), unique.end(), shuffle_rng);
    verify_incremental_decomposition<Insertion>(
      unique,
      order,
      "decomposition/all-unique"
    );
  }
}

// Post-sort discovery must keep partitions of a non-final column on the worker
// that owns the range, because its RLE scan needs the complete sorted range and
// an equal run may cross a partition boundary. Incremental three-way discovery
// has no such obligation and offloads them.
//
// Both columns are high cardinality, so the first column carries essentially all
// the partition work and the second column's discovered runs are too short to
// offload. Post-sort must therefore report no offloaded partition at all, while
// incremental reports several from the same input.
void test_partition_offload_gating() {
  using Sorter = TslMultiColumnQuickSorter<
    std::uint32_t,
    TslPartitionKind::THREE_WAY,
    TslLeafKind::NETWORK
  >;
  auto const input = make_random_columns<std::uint32_t>(2, 8192, 0xa5a5ULL, 0);
  auto const orders = std::vector<TslSortOrder>{
    TslSortOrder::ASCENDING,
    TslSortOrder::DESCENDING,
  };

  auto const post = verify_parallel_case<Sorter>(
    input,
    orders,
    TslRunDiscoveryKind::POST_SORT,
    4,
    2,
    "gating/post",
    2
  );
  require(
    post.partition_tasks_submitted == 0,
    "gating/post: a non-final-column partition was offloaded"
  );

  auto const incremental = verify_parallel_case<Sorter>(
    input,
    orders,
    TslRunDiscoveryKind::INCREMENTAL,
    4,
    2,
    "gating/incremental",
    2
  );
  require(
    incremental.partition_tasks_submitted >= 1,
    "gating/incremental: non-final-column partitions were not offloaded"
  );
}

void test_parallel_determinism() {
  using Sorter = TslMultiColumnQuickSorter<
    std::uint32_t,
    TslPartitionKind::THREE_WAY,
    TslLeafKind::NETWORK
  >;
  auto input = make_random_columns<std::uint32_t>(4, 4096, 0xdeadbeefULL, 8);
  std::iota(input.back().begin(), input.back().end(), 0u);
  auto const orders = std::vector<TslSortOrder>{
    TslSortOrder::ASCENDING,
    TslSortOrder::DESCENDING,
    TslSortOrder::ASCENDING,
    TslSortOrder::DESCENDING,
  };
  // Offloading a partition re-seeds from its own range coordinates, so the
  // pivot sequence must depend on the input and the thresholds alone, never on
  // which worker picked the range up.
  for (auto const partitions : {std::size_t{0}, std::size_t{2}}) {
    auto first = input;
    auto second = input;
    auto first_specs = column_specs(first, orders);
    auto second_specs = column_specs(second, orders);
    Sorter sorter(0x424242ULL);
    sorter.sort_columns_parallel(
      first_specs.data(),
      first_specs.size(),
      first.front().size(),
      4,
      2,
      partitions,
      TslRunDiscoveryKind::INCREMENTAL
    );
    sorter.sort_columns_parallel(
      second_specs.data(),
      second_specs.size(),
      second.front().size(),
      1,
      2,
      partitions,
      TslRunDiscoveryKind::INCREMENTAL
    );
    require(
      first == second,
      "fixed-seed parallel output is not deterministic for partitions-"
        + std::to_string(partitions)
    );
  }
}

}  // namespace

int main() {
  try {
    test_equal_runs();
    test_argument_validation();
    test_discovery_fallback_and_last_column_scan();

    using TwoWayInsertion = TslMultiColumnQuickSorter<
      std::uint32_t,
      TslPartitionKind::TWO_WAY,
      TslLeafKind::INSERTION
    >;
    using TwoWayNetwork = TslMultiColumnQuickSorter<
      std::uint32_t,
      TslPartitionKind::TWO_WAY,
      TslLeafKind::NETWORK
    >;
    using ThreeWayInsertion = TslMultiColumnQuickSorter<
      std::uint32_t,
      TslPartitionKind::THREE_WAY,
      TslLeafKind::INSERTION
    >;
    using ThreeWayNetwork = TslMultiColumnQuickSorter<
      std::uint32_t,
      TslPartitionKind::THREE_WAY,
      TslLeafKind::NETWORK
    >;

    run_sorter_matrix<TwoWayInsertion>("two-way/insertion", false);
    run_sorter_matrix<TwoWayNetwork>("two-way/network", false);
    run_sorter_matrix<ThreeWayInsertion>("three-way/insertion/post", false);
    run_sorter_matrix<ThreeWayNetwork>("three-way/network/post", false);
    run_sorter_matrix<ThreeWayInsertion>("three-way/insertion/incremental", true);
    run_sorter_matrix<ThreeWayNetwork>("three-way/network/incremental", true);
    test_u64_network();
    test_u64_variants();
    test_task_executor();
    test_incremental_decomposition();
    test_partition_offload_gating();
    test_parallel_determinism();

    run_parallel_matrix<TwoWayInsertion>(
      "parallel/two-way/insertion/post",
      TslRunDiscoveryKind::POST_SORT
    );
    run_parallel_matrix<TwoWayNetwork>(
      "parallel/two-way/network/post",
      TslRunDiscoveryKind::POST_SORT
    );
    run_parallel_matrix<ThreeWayInsertion>(
      "parallel/three-way/insertion/post",
      TslRunDiscoveryKind::POST_SORT
    );
    run_parallel_matrix<ThreeWayNetwork>(
      "parallel/three-way/network/post",
      TslRunDiscoveryKind::POST_SORT
    );
    run_parallel_matrix<ThreeWayInsertion>(
      "parallel/three-way/insertion/incremental",
      TslRunDiscoveryKind::INCREMENTAL
    );
    run_parallel_matrix<ThreeWayNetwork>(
      "parallel/three-way/network/incremental",
      TslRunDiscoveryKind::INCREMENTAL
    );

    run_sealed_matrix<ThreeWayInsertion>("sealed/three-way/insertion");
    run_sealed_matrix<ThreeWayNetwork>("sealed/three-way/network");

    std::cout << "multi-column sort tests passed\n";
    return 0;
  } catch (std::exception const & error) {
    std::cerr << "multi-column sort test failed: " << error.what() << '\n';
    return 1;
  }
}
