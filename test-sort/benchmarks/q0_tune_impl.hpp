#pragma once

// The coordinate-descent body, templated on (style, width) so one translation
// unit per pair can be compiled in parallel.
//
// -----------------------------------------------------------------------------
// Why the shape of the search is what it is
// -----------------------------------------------------------------------------
// Almost every knob is a template parameter, so a candidate configuration is a
// distinct instantiation and the search's cost in *compile* time is the number of
// candidates. A full grid over seven axes is 400-odd instantiations per style and
// width, which is unbuildable. A strict sequential descent is no better: round
// two's candidates depend on round one's winner, which is a runtime value, so
// every reachable configuration would have to be instantiated anyway.
//
// So: a small full cross over the axes that interact -- bucket count, base-case
// leaf, fill threshold -- and one-factor-at-a-time around the default for the
// axes that do not. The combined winner is then instantiated and measured, so if
// combining the individual winners is worse than the best single change, that is
// visible in the output rather than assumed away.
//
// What this cannot do is a second descent round: that needs `--base` set to the
// winner and a rebuild. `bench_q0_tune --rounds` prints the command when a second
// round would be worth running, which is when the combined winner beats the best
// cross member.

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <functional>
#include <string>
#include <vector>

#include "datagen/dataset_catalog.hpp"
#include "datagen/dataset_reference.hpp"
#include "datagen/dataset_source.hpp"
#include "paper_harness.hpp"
#include "sorting/quicksort/multicolumn_index_sort.hpp"
#include "sorting/sample_sort/samplesort_multicolumn.hpp"
#include "tsl_simd_for.hpp"
#include "tuned_config.hpp"


// What a unit tunes over: several shapes, so the result is not fitted to one
// dataset, and one worker count.
struct TslTuneProblem {
  std::vector<TslDatasetSpec> specs;
  std::size_t workers = 1;
};

// One measured candidate.
struct TslTuneCandidate {
  std::string axis;        // which coordinate this varies, "" for the combination
  std::string label;       // the value on that coordinate
  TslTunedConfig config;
  double score = 0.0;      // geometric mean ns/element; 0 means it sorted wrongly
};

// A unit is one (style, width): it runs the whole search and reports.
struct TslTuneUnit {
  TslStyle style;
  std::size_t width;
  std::function<std::vector<TslTuneCandidate>(TslTuneProblem const &)> samplesort;
  std::function<std::vector<TslTuneCandidate>(TslTuneProblem const &)> quicksort;
};

inline auto tsl_tune_units() -> std::vector<TslTuneUnit> & {
  static std::vector<TslTuneUnit> units;
  return units;
}


namespace tsl_tune_detail {

template <class Key>
auto image_matches(std::vector<std::vector<Key>> const & columns,
                   std::vector<std::vector<Key>> const & reference,
                   std::vector<Key> const & index) -> bool {
  for (std::size_t column = 0; column < columns.size(); ++column) {
    for (std::size_t at = 0; at < index.size(); ++at) {
      if (columns[column][static_cast<std::size_t>(index[at])]
          != reference[column][at]) {
        return false;
      }
    }
  }
  return true;
}

// Geometric mean over the shapes: the right average for a score that is compared
// as a ratio, and it stops one slow shape from deciding every axis.
template <class Key, class Run>
auto geometric_score(TslDatasetSource<Key> & source, TslTuneProblem const & problem,
                     Run && run) -> double {
  double logs = 0.0;
  std::size_t counted = 0;
  for (auto const & spec : problem.specs) {
    auto const pristine = source.pristine(spec);
    auto const reference = source.reference(spec, TslDirection::Ascending);
    std::vector<TslSortColumn<Key>> columns;
    for (auto const & column : *pristine) {
      columns.push_back(TslSortColumn<Key>{const_cast<Key *>(column.data()),
                                           TslSortOrder::ASCENDING});
    }
    std::vector<Key> index(spec.rows);
    auto const [ok, stats] = tsl_paper_measure(
      [&] { run(columns.data(), spec.columns, index.data(), spec.rows,
                problem.workers); },
      [&] { return image_matches(*pristine, *reference, index); }, spec.rows);
    if (!ok || stats.median <= 0.0) {
      return 0.0;  // a wrong candidate cannot win, whatever its time
    }
    logs += std::log(stats.median);
    ++counted;
  }
  return counted == 0 ? 0.0 : std::exp(logs / static_cast<double>(counted));
}

}  // namespace tsl_tune_detail


// --- samplesort ---------------------------------------------------------------

template <class Key, class Simd, int K, TslSampleSortBuckets B, TslSampleSortBase P,
          std::size_t BC, std::size_t F, TslSampleSortIds I,
          TslSampleSortMovement M>
auto tsl_tune_samplesort_point(TslDatasetSource<Key> & source,
                               TslTuneProblem const & problem) -> double {
  using Sorter = TslSampleSortMultiColumn<Key, Simd, K, B, 8, BC, P, I,
                                          BC / Simd::lane_count_v, F, M, false>;
  Sorter sorter;
  return tsl_tune_detail::geometric_score<Key>(
    source, problem,
    [&](TslSortColumn<Key> * columns, std::size_t column_count, Key * index,
        std::size_t rows, std::size_t workers) {
      TslIndexScalarDetector<Key> detector;
      if (workers > 1) {
        sorter.sort_index_parallel(columns, column_count, index, rows, detector,
                                   workers);
      } else {
        sorter.sort_index(columns, column_count, index, rows, detector);
      }
    });
}


// --- quicksort ----------------------------------------------------------------

template <class Key, class Simd, TslPartitionKind Partition, TslLeafKind Leaf,
          std::size_t Fill>
auto tsl_tune_quicksort_point(TslDatasetSource<Key> & source,
                              TslTuneProblem const & problem,
                              TslRunDiscoveryKind discovery,
                              std::size_t partition_threshold) -> double {
  using Sorter = TslMultiColumnIndexSorter<Key, Partition, Leaf, Simd, Fill>;
  Sorter sorter(0x5A3F1E77);
  return tsl_tune_detail::geometric_score<Key>(
    source, problem,
    [&](TslSortColumn<Key> * columns, std::size_t column_count, Key * index,
        std::size_t rows, std::size_t workers) {
      TslIndexScalarDetector<Key> detector;
      if (workers > 1) {
        sorter.sort_index_parallel(columns, column_count, index, rows, discovery,
                                   detector, workers, partition_threshold);
      } else {
        sorter.sort_index(columns, column_count, index, rows, discovery, detector);
      }
    });
}
