// Differential test for the indirect (index-permutation) multi-column sort.
//
// The output is a permutation, and ties make it non-unique: the partition is not
// stable, so two correct runs may order tied rows differently. Every check here
// is therefore about the *values the permutation selects*, never the permutation
// itself:
//
//   1. it is a permutation at all -- every row id exactly once;
//   2. the value image matches a std::stable_sort reference position by position,
//      for every column;
//   3. the emitted order is lexicographically non-decreasing under the per-column
//      directions, which catches a reference and an implementation that are wrong
//      the same way.
//
// Runs the scalar detector always, and the synchronous IAA detector as well when
// the build has one -- the point of routing discovery through the detector seam
// is that `rle=` applies to this sorter too, and that is only proven by using it.

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <numeric>
#include <random>
#include <string>
#include <vector>

#include "multicolumn_index_sort.hpp"

#ifdef TSL_COSORT_ENABLE_IAA
#include "iaa_run_detector.hpp"
#endif

namespace {

std::size_t g_checks = 0;
std::size_t g_failures = 0;

enum class Direction { Ascending, Descending, Alternating };

auto direction_name(Direction direction) -> char const * {
  switch (direction) {
    case Direction::Ascending: return "asc";
    case Direction::Descending: return "desc";
    case Direction::Alternating: return "alt";
  }
  return "?";
}

auto ascending_flags(Direction direction, std::size_t column_count) -> std::vector<bool> {
  std::vector<bool> ascending(column_count, true);
  if (direction == Direction::Descending) {
    ascending.assign(column_count, false);
  } else if (direction == Direction::Alternating) {
    for (std::size_t column = 0; column < column_count; ++column) {
      ascending[column] = column % 2 == 0;
    }
  }
  return ascending;
}

// Columns whose first column has `cardinality` distinct values and whose later
// columns are progressively finer, so deep levels actually have work to do.
template <class T>
auto make_columns(std::size_t rows, std::size_t column_count, std::size_t cardinality,
                  std::uint64_t seed) -> std::vector<std::vector<T>> {
  std::vector<std::vector<T>> columns(column_count, std::vector<T>(rows));
  std::mt19937_64 rng(seed);
  for (std::size_t column = 0; column < column_count; ++column) {
    // Each column splits the previous one's groups a little further.
    auto const values = std::max<std::size_t>(cardinality * (column + 1), 1);
    std::uniform_int_distribution<std::uint64_t> dist(0, values - 1);
    for (std::size_t row = 0; row < rows; ++row) {
      columns[column][row] = static_cast<T>(dist(rng));
    }
  }
  return columns;
}

template <class T>
auto lexicographic_less(
  std::vector<std::vector<T>> const & columns,
  std::vector<bool> const & ascending,
  std::uint64_t left,
  std::uint64_t right
) -> bool {
  for (std::size_t column = 0; column < columns.size(); ++column) {
    auto const a = columns[column][left];
    auto const b = columns[column][right];
    if (a != b) {
      return ascending[column] ? a < b : a > b;
    }
  }
  return false;
}

template <class T, TslPartitionKind Partition, TslLeafKind Leaf, class Detector>
void check(
  std::string const & label,
  std::vector<std::vector<T>> const & columns,
  Direction direction,
  TslRunDiscoveryKind discovery,
  Detector & detector
) {
  ++g_checks;
  auto const rows = columns.empty() ? 0 : columns.front().size();
  auto const column_count = columns.size();
  auto const ascending = ascending_flags(direction, column_count);

  std::vector<TslSortColumn<T>> specs;
  specs.reserve(column_count);
  for (std::size_t column = 0; column < column_count; ++column) {
    specs.push_back(TslSortColumn<T>{
      const_cast<T *>(columns[column].data()),
      ascending[column] ? TslSortOrder::ASCENDING : TslSortOrder::DESCENDING
    });
  }

  std::vector<T> index(rows);
  TslIndexSortMetrics metrics;
  TslMultiColumnIndexSorter<T, Partition, Leaf> sorter(0x5EED ^ rows);
  sorter.sort_index(specs.data(), column_count, index.data(), rows, discovery, detector, &metrics);

  // 1. a permutation
  std::vector<unsigned char> seen(rows, 0);
  for (std::size_t position = 0; position < rows; ++position) {
    auto const row = static_cast<std::size_t>(index[position]);
    if (row >= rows || seen[row] != 0) {
      ++g_failures;
      std::printf("FAIL %s: index is not a permutation at position %zu\n",
                  label.c_str(), position);
      return;
    }
    seen[row] = 1;
  }

  // 2. same value image as the reference
  std::vector<std::uint64_t> reference(rows);
  std::iota(reference.begin(), reference.end(), 0ull);
  std::stable_sort(reference.begin(), reference.end(),
                   [&](std::uint64_t left, std::uint64_t right) {
                     return lexicographic_less(columns, ascending, left, right);
                   });
  for (std::size_t position = 0; position < rows; ++position) {
    for (std::size_t column = 0; column < column_count; ++column) {
      auto const ours = columns[column][index[position]];
      auto const theirs = columns[column][reference[position]];
      if (ours != theirs) {
        ++g_failures;
        std::printf(
          "FAIL %s: column %zu differs at position %zu: %llu vs %llu\n",
          label.c_str(), column, position,
          static_cast<unsigned long long>(ours), static_cast<unsigned long long>(theirs)
        );
        return;
      }
    }
  }

  // 3. the order invariant, independent of the reference
  for (std::size_t position = 0; position + 1 < rows; ++position) {
    if (lexicographic_less(columns, ascending, index[position + 1], index[position])) {
      ++g_failures;
      std::printf("FAIL %s: rows %zu and %zu are out of order\n",
                  label.c_str(), position, position + 1);
      return;
    }
  }

  // The metrics have to be consistent with having done the work.
  if (rows >= 2 && metrics.levels == 0) {
    ++g_failures;
    std::printf("FAIL %s: no level reported work\n", label.c_str());
  }
}

template <class T, TslPartitionKind Partition, TslLeafKind Leaf, class Detector>
void run_shapes(std::string const & tag, Detector & detector) {
  constexpr std::size_t leaf = TslMultiColumnIndexSorter<T, Partition, Leaf>::leaf_size_threshold();

  for (auto discovery : {TslRunDiscoveryKind::POST_SORT, TslRunDiscoveryKind::INCREMENTAL}) {
    auto const disc = discovery == TslRunDiscoveryKind::POST_SORT ? "post" : "incr";
    for (auto direction : {Direction::Ascending, Direction::Descending, Direction::Alternating}) {
      std::string const base = tag + "/" + disc + "/" + direction_name(direction);

      // Column-count sweep at a cardinality that guarantees deep ties.
      for (std::size_t column_count : {std::size_t{1}, std::size_t{2}, std::size_t{4}}) {
        auto const columns = make_columns<T>(4096 + 37, column_count, 8, 0xC01 + column_count);
        check<T, Partition, Leaf>(
          base + "/cols=" + std::to_string(column_count), columns, direction, discovery, detector);
      }

      // Cardinality sweep: one group over everything, through all-distinct.
      for (std::size_t cardinality : {std::size_t{1}, std::size_t{2}, std::size_t{17},
                                      std::size_t{4096}, std::size_t{1u << 20}}) {
        auto const columns = make_columns<T>(3000, 3, cardinality, 0xCA4D ^ cardinality);
        check<T, Partition, Leaf>(
          base + "/card=" + std::to_string(cardinality), columns, direction, discovery, detector);
      }

      // Row counts straddling the leaf threshold and the vector width.
      for (std::size_t rows : {std::size_t{2}, std::size_t{3}, leaf - 1, leaf, leaf + 1,
                               2 * leaf, 2 * leaf + 1, 8 * leaf + 5}) {
        auto const columns = make_columns<T>(rows, 3, 6, 0xB0A ^ rows);
        check<T, Partition, Leaf>(
          base + "/rows=" + std::to_string(rows), columns, direction, discovery, detector);
      }

      // Every row identical: every level sees one maximal tie and must terminate.
      {
        std::vector<std::vector<T>> columns(3, std::vector<T>(2000, static_cast<T>(7)));
        check<T, Partition, Leaf>(base + "/all-equal", columns, direction, discovery, detector);
      }
    }
  }
}

}  // namespace

int main() {
  {
    TslIndexScalarDetector<std::uint32_t> scalar32;
    TslIndexScalarDetector<std::uint64_t> scalar64;
    // One detector object cannot serve both widths, so the scalar pass runs the
    // per-width sweeps directly.
    std::printf("-- detector scalar --\n");
    run_shapes<std::uint32_t, TslPartitionKind::THREE_WAY, TslLeafKind::NETWORK>("scalar/u32/3way/net", scalar32);
    run_shapes<std::uint32_t, TslPartitionKind::THREE_WAY, TslLeafKind::INSERTION>("scalar/u32/3way/ins", scalar32);
    run_shapes<std::uint32_t, TslPartitionKind::TWO_WAY, TslLeafKind::NETWORK>("scalar/u32/2way/net", scalar32);
    run_shapes<std::uint64_t, TslPartitionKind::THREE_WAY, TslLeafKind::NETWORK>("scalar/u64/3way/net", scalar64);
    run_shapes<std::uint64_t, TslPartitionKind::TWO_WAY, TslLeafKind::INSERTION>("scalar/u64/2way/ins", scalar64);
  }

#ifdef TSL_COSORT_ENABLE_IAA
  {
    // The seam claim: an accelerator detector drives discovery here unchanged,
    // because the materialized key buffer is contiguous. Software path, so it
    // needs no device.
    std::printf("-- detector iaa_sw --\n");
    TslIaaRunDetector<std::uint32_t> iaa32(TslIaaPath::SOFTWARE, 64 * 1024, 0);
    TslIaaRunDetector<std::uint64_t> iaa64(TslIaaPath::SOFTWARE, 64 * 1024, 0);
    run_shapes<std::uint32_t, TslPartitionKind::THREE_WAY, TslLeafKind::NETWORK>("iaa/u32/3way/net", iaa32);
    run_shapes<std::uint64_t, TslPartitionKind::THREE_WAY, TslLeafKind::NETWORK>("iaa/u64/3way/net", iaa64);
  }
#else
  std::printf("-- detector iaa_sw skipped (build without TSL_COSORT_ENABLE_IAA) --\n");
#endif

  if (g_failures != 0) {
    std::printf("\nindex sort tests FAILED: %zu of %zu checks\n", g_failures, g_checks);
    return 1;
  }
  std::printf("\nindex sort tests passed (%zu checks)\n", g_checks);
  return 0;
}
