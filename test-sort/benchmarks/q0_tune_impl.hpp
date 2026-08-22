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
#include <chrono>
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
  // Correctness sweep rather than a tuning run: check every shape instead of
  // stopping at the first failure, and do not time anything. A configuration that
  // sorts wrongly is a bug in the sorter, not a slow candidate, so the question
  // "does every (style, width, configuration) still sort correctly" deserves to be
  // askable on its own and cheaply -- not answered incidentally by whichever cells
  // a tuning run happens to visit.
  bool verify_only = false;
  // Seconds a single candidate may spend before it is abandoned. A configuration
  // 66x off the pace can never win, and on duplicate-heavy real keys the two-way
  // partition is quadratic -- one such candidate consumed two hours of a run whose
  // useful part was fourteen minutes. Abandoning it is not the same as calling it
  // wrong, and the report says which. 0 means unlimited.
  double candidate_seconds = 0.0;
};

// A candidate's measured cost: the geometric mean the descent ranks on, and the
// per-shape times behind it. The descent only needs the mean, but collapsing to it
// answers "which configuration wins on average" while destroying the evidence for
// "does the winner depend on the shape" -- which is the more interesting question,
// so both are kept.
struct TslTuneScore {
  double score = 0.0;               // geometric mean ns/element; 0 means incorrect
  std::vector<double> per_shape;    // parallel to TslTuneProblem::specs
  std::vector<std::string> failures; // shape ids this candidate sorted wrongly
  bool over_budget = false;          // abandoned on time, not incorrect
};

// One measured candidate.
struct TslTuneCandidate {
  std::string axis;        // which coordinate this varies, "" for the combination
  std::string label;       // the value on that coordinate
  TslTunedConfig config;
  double score = 0.0;      // geometric mean ns/element; 0 means it sorted wrongly
  std::vector<double> per_shape;
  std::vector<std::string> failures;
  bool over_budget = false;
};

// A unit is one (style, register width, key width): it runs the whole search and
// reports. The key width is part of the identity because a configuration tuned on
// 4-byte keys is not a tuned configuration for 8-byte keys -- the lane holds half
// as many elements, so the base case, the bucket count and the leaf capacity all
// shift -- and `best_config.tsv` is already keyed on element bytes.
struct TslTuneUnit {
  TslStyle style;
  std::size_t width;
  std::size_t element_bytes = 4;
  std::function<std::vector<TslTuneCandidate>(TslTuneProblem const &)> samplesort;
  std::function<std::vector<TslTuneCandidate>(TslTuneProblem const &)> quicksort;
};

inline auto tsl_tune_units() -> std::vector<TslTuneUnit> & {
  static std::vector<TslTuneUnit> units;
  return units;
}


namespace tsl_tune_detail {

// Correctness of one candidate: the index must be a permutation of the rows, and
// applying it to every column must reproduce the reference image.
//
// The permutation half is not redundant. Comparing values alone passes an index
// that repeats one row and drops another whenever the two hold equal keys -- and
// the tuning set is chosen to be duplicate-heavy, so `low_cardinality_d4` at four
// distinct values would accept almost any garbage. For an index co-sort, "the
// values came out sorted" and "no row was lost" are different claims and the
// second is the one a caller depends on.
template <class Key>
auto sorted_image_of_a_permutation(std::vector<std::vector<Key>> const & columns,
                                   std::vector<std::vector<Key>> const & reference,
                                   std::vector<Key> const & index) -> bool {
  std::vector<char> seen(index.size(), 0);
  for (auto const row : index) {
    auto const at = static_cast<std::size_t>(row);
    if (at >= seen.size() || seen[at] != 0) {
      return false;  // out of range, or a row delivered twice
    }
    seen[at] = 1;
  }
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
                     Run && run) -> TslTuneScore {
  TslTuneScore out;
  double logs = 0.0;
  std::size_t counted = 0;
  auto const started = std::chrono::steady_clock::now();
  for (auto const & spec : problem.specs) {
    if (problem.candidate_seconds > 0.0) {
      auto const spent = std::chrono::duration<double>(
        std::chrono::steady_clock::now() - started).count();
      if (spent > problem.candidate_seconds) {
        out.over_budget = true;
        break;
      }
    }
    auto const pristine = source.pristine(spec);
    auto const reference = source.reference(spec, TslDirection::Ascending);
    std::vector<TslSortColumn<Key>> columns;
    for (auto const & column : *pristine) {
      columns.push_back(TslSortColumn<Key>{const_cast<Key *>(column.data()),
                                           TslSortOrder::ASCENDING});
    }
    std::vector<Key> index(spec.rows);
    auto const body = [&] {
      run(columns.data(), spec.columns, index.data(), spec.rows, problem.workers);
    };
    auto const correct = [&] {
      return sorted_image_of_a_permutation(*pristine, *reference, index);
    };
    if (problem.verify_only) {
      body();
      if (!correct()) {
        out.failures.push_back(spec.id);
      }
      continue;  // nothing is timed in a correctness sweep
    }
    // Split the budget across the shapes so no single one can consume it all.
    auto const per_shape_budget =
      problem.candidate_seconds > 0.0
        ? problem.candidate_seconds / static_cast<double>(problem.specs.size())
        : 0.0;
    bool abandoned = false;
    auto const [ok, stats] =
      tsl_paper_measure(body, correct, spec.rows, per_shape_budget, &abandoned);
    if (abandoned) {
      out.over_budget = true;
      break;
    }
    if (!ok || stats.median <= 0.0) {
      out.failures.push_back(spec.id);
      return out;  // a wrong candidate cannot win, whatever its time
    }
    out.per_shape.push_back(stats.median);
    logs += std::log(stats.median);
    ++counted;
  }
  out.score = (counted == 0 || !out.failures.empty() || out.over_budget)
                ? 0.0
                : std::exp(logs / static_cast<double>(counted));
  return out;
}

}  // namespace tsl_tune_detail


// --- samplesort ---------------------------------------------------------------

template <class Key, class Simd, int K, TslSampleSortBuckets B, TslSampleSortBase P,
          std::size_t BC, std::size_t F, TslSampleSortIds I,
          TslSampleSortMovement M>
auto tsl_tune_samplesort_point(TslDatasetSource<Key> & source,
                               TslTuneProblem const & problem) -> TslTuneScore {
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
                              std::size_t partition_threshold) -> TslTuneScore {
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
