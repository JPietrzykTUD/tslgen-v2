// Correctness tests for the multi-column samplesort co-sort.
//
// The oracle is the value image: with the permutation applied to every column,
// the table must equal the reference sorted image. That image is unique whatever
// ties the sort broke, which is what makes it a usable oracle for an unstable
// sort -- the permutation itself is not unique, so comparing permutations would
// reject correct answers.
//
// Two properties beyond sortedness carry the weight here:
//
//  * **Lexicographic order.** Sorting the first column right proves nothing; the
//    test compares the whole materialised table, so a range where the second
//    column was left unsorted inside a tie of the first is caught.
//  * **Detector equivalence.** The same sort is run through the scalar detector
//    and through a deliberately awkward one that emits the same runs in the same
//    order but is written independently. Both must produce the same image, which
//    is what makes the `rle=` axis meaningful for this driver.

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <numeric>
#include <random>
#include <string>
#include <vector>

#include "dataset_catalog.hpp"
#include "dataset_reference.hpp"
#include "dataset_source.hpp"
#include "sorting/sample_sort/samplesort_multicolumn.hpp"

namespace {

std::size_t g_checks = 0;
std::size_t g_failures = 0;

void fail(std::string const & label, std::string const & why) {
  ++g_failures;
  std::printf("FAIL %-58s %s\n", label.c_str(), why.c_str());
}

// An independent detector over the same contract: finds maximal equal runs by
// binary-searching each run's end rather than walking. Slower, and that is the
// point -- it agrees with the scalar scan only if both read the contract the same
// way.
// Stateless on purpose: the parallel driver calls the detector from worker
// threads, so a counter here would be a data race rather than a measurement.
template <class DataType>
struct BisectingRunDetector {
  template <class Emit>
  void operator()(DataType const * values, std::size_t begin, std::size_t end,
                  Emit && emit) {
    auto at = begin;
    while (at < end) {
      auto const value = values[at];
      auto const stop = static_cast<std::size_t>(
        std::upper_bound(values + at, values + end, value) - values);
      if (stop - at >= 2) {
        emit(TslRunSpan{at, stop});
      }
      at = stop;
    }
  }
};

template <class Key>
auto image_of(std::vector<std::vector<Key>> const & columns,
              std::vector<typename TslSampleSortTraits<Key>::index_type> const & index)
  -> std::vector<std::vector<Key>> {
  std::vector<std::vector<Key>> out(columns.size());
  for (std::size_t column = 0; column < columns.size(); ++column) {
    out[column].resize(index.size());
    for (std::size_t row = 0; row < index.size(); ++row) {
      out[column][row] = columns[column][static_cast<std::size_t>(index[row])];
    }
  }
  return out;
}

// One (shape, rows, columns) case, both detectors, serial and parallel.
template <class Key, class Simd, int K, TslSampleSortBuckets Policy>
void run_case(char const * tag, TslDatasetSpec const & spec,
              std::vector<std::vector<Key>> const & pristine,
              std::vector<std::vector<Key>> const & reference,
              std::size_t workers) {
  using Sorter = TslSampleSortMultiColumn<Key, Simd, K, Policy>;
  using Idx = typename Sorter::index_type;
  auto const rows = pristine.front().size();
  auto const columns = pristine.size();
  auto const label = std::string(tag) + "/" + spec.id + "/w=" + std::to_string(workers);

  std::vector<TslSortColumn<Key>> specs;
  specs.reserve(columns);
  for (auto const & column : pristine) {
    specs.push_back(TslSortColumn<Key>{const_cast<Key *>(column.data()),
                                       TslSortOrder::ASCENDING});
  }

  for (int which = 0; which < 2; ++which) {
    ++g_checks;
    std::vector<Idx> index(rows);
    Sorter sorter;
    TslSampleSortColumnMetrics metrics;
    if (which == 0) {
      TslIndexScalarDetector<Key> detector;
      if (workers > 1) {
        sorter.sort_index_parallel(specs.data(), columns, index.data(), rows,
                                   detector, workers, &metrics);
      } else {
        sorter.sort_index(specs.data(), columns, index.data(), rows, detector,
                          &metrics);
      }
    } else {
      BisectingRunDetector<Key> detector;
      if (workers > 1) {
        sorter.sort_index_parallel(specs.data(), columns, index.data(), rows,
                                   detector, workers, &metrics);
      } else {
        sorter.sort_index(specs.data(), columns, index.data(), rows, detector,
                          &metrics);
      }
    }
    auto const * which_name = which == 0 ? "scalar" : "bisect";

    if (rows != 0) {
      std::vector<bool> seen(rows, false);
      for (auto const value : index) {
        auto const at = static_cast<std::size_t>(value);
        if (at >= rows || seen[at]) {
          fail(label + "/" + which_name, "index is not a permutation");
          return;
        }
        seen[at] = true;
      }
    }
    auto const got = image_of(pristine, index);
    if (got != reference) {
      for (std::size_t column = 0; column < columns; ++column) {
        for (std::size_t row = 0; row < rows; ++row) {
          if (got[column][row] != reference[column][row]) {
            fail(label + "/" + which_name,
                 "image differs at column " + std::to_string(column) + " row "
                   + std::to_string(row));
            return;
          }
        }
      }
      fail(label + "/" + which_name, "image differs");
      return;
    }
    // Every range handed to the detector must be one the recursion needed: the
    // driver only detects when a further column exists.
    if (columns == 1 && metrics.detected_ranges != 0) {
      fail(label + "/" + which_name, "detected runs with no further column to sort");
    }
  }
}

template <class Key, class Simd, int K, TslSampleSortBuckets Policy>
void run_shapes(char const * tag, std::vector<std::string> const & shapes,
                std::vector<std::size_t> const & column_counts,
                std::vector<std::size_t> const & row_counts,
                std::vector<std::size_t> const & worker_counts) {
  TslDatasetSource<Key> source(4ull << 30);
  auto const tail = "_u" + std::to_string(sizeof(Key) * 8) + "_n";
  for (auto const & shape : shapes) {
    for (auto const columns : column_counts) {
      for (auto const rows : row_counts) {
        auto const catalog = tsl_default_catalog(rows, columns, sizeof(Key));
        for (auto const & spec : catalog) {
          if (spec.id.rfind(shape + tail, 0) != 0) {
            continue;
          }
          auto const pristine = source.pristine(spec);
          auto const reference = source.reference(spec, TslDirection::Ascending);
          for (auto const workers : worker_counts) {
            run_case<Key, Simd, K, Policy>(tag, spec, *pristine, *reference, workers);
          }
          break;
        }
      }
    }
  }
}

}  // namespace

int main() {
  std::printf("-- multi-column samplesort co-sort --\n");

  // Shapes chosen for their range structure: a low-cardinality key recurses to
  // the last column, a terminal-group shape keeps ranges mid-sized, zipf is
  // heavy-tailed, and an all-distinct first column ends the recursion at once.
  std::vector<std::string> const shapes{
    "low_cardinality_d4", "unique_last_g64", "skewed_zipf_s1", "unique_first",
    "independent_uniform_c1024"
  };
  run_shapes<std::uint32_t, tsl::simd<std::uint32_t, tsl::avx512>, 16,
             TslSampleSortBuckets::Adaptive>(
    "u32/K=16/adaptive", shapes, {1, 2, 4}, {4095, 1u << 18}, {1, 4});
  run_shapes<std::uint32_t, tsl::simd<std::uint32_t, tsl::avx512>, 16,
             TslSampleSortBuckets::Ordered>(
    "u32/K=16/ordered", {"low_cardinality_d4", "skewed_zipf_s1"}, {3, 8},
    {4095, 1u << 18}, {1});
  run_shapes<std::uint64_t, tsl::simd<std::uint64_t, tsl::avx512>, 16,
             TslSampleSortBuckets::Adaptive>(
    "u64/K=16/adaptive", {"low_cardinality_d4", "unique_last_g64"}, {2, 5},
    {4095, 1u << 18}, {1, 8});
  // One larger case, deep enough to exercise the parallel range threshold.
  run_shapes<std::uint32_t, tsl::simd<std::uint32_t, tsl::avx512>, 16,
             TslSampleSortBuckets::Adaptive>(
    "u32/K=16/adaptive/large", {"low_cardinality_d4"}, {8}, {1u << 21}, {1, 24});

  if (g_failures != 0) {
    std::printf("\nmulti-column samplesort tests FAILED: %zu of %zu checks\n",
                g_failures, g_checks);
    return 1;
  }
  std::printf("\nmulti-column samplesort tests passed (%zu checks)\n", g_checks);
  return 0;
}
