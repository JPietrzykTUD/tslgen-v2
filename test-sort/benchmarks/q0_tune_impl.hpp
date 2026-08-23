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
  // Measure only the documented default. Used to price a whole cell before
  // committing to tuning it: one candidate says whether the cell is in the running.
  bool probe_default_only = false;
  // Two-way partitioning is quadratic in the equal-run length, and this tuning set
  // is duplicate-heavy on purpose, so above a working-set size the candidate stops
  // being a measurement and becomes a hang: it was already 66x off the pace at
  // 2^20 rows and the full Q0 sat on it for over an hour at twenty-four workers.
  // The corpus driver has gated it this way for the same reason
  // (`TslStagePlan::two_way_size_cap`); Q0 did not.
  std::uint64_t two_way_size_cap = 256ull * 1024;
  // Abandon a candidate whose first pass already costs more than this multiple of
  // the best candidate measured so far. Relative rather than absolute, so it
  // calibrates itself to the shape and the machine instead of needing a wall-clock
  // guess: a configuration five times off the pace cannot win, and measuring it
  // nine times over five shapes is how a tuning run turns into an overnight hang.
  double abandon_factor = 5.0;
  // Two candidates whose scores differ by less than this are the same answer.
  //
  // Not a comfort setting. Running the identical candidate set twice on a quiet,
  // pinned machine moved individual scores by 1.0% at the median and 3.5% at the
  // worst, and that was enough to change which samplesort configuration "won":
  // K16/net/f50 at 44.09 and K16/net/f75 at 44.07 in one run, reversed in the
  // next. Four candidates sat within 0.2% of each other. Reporting one of them as
  // the optimum is reporting the noise.
  //
  // So the tuner reports a tied *set* and ships the documented default whenever the
  // default is in it. That makes the published configuration stable across runs
  // and across machines, and makes the claim defensible: not "these knobs are
  // optimal" but "nothing we measured beats the default by more than the
  // measurement's own drift".
  double tie_margin = 0.04;
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
  // Paired against the documented default, one shape at a time: `beats_default` is
  // true only where the upper quartile of the per-round ratio is below 1.0 on every
  // shape. A fixed percentage margin cannot do this job -- the default sits near
  // the boundary, so which side of it lands is itself a coin flip, and the shipped
  // configuration flipped between two interleaved runs. Asking whether the
  // *difference* is resolvable is the question that has a stable answer.
  bool beats_default = false;
  double ratio_to_default = 0.0;   // median over shapes, for the report
  bool over_budget = false;
  // Set when a candidate was deliberately not measured. Distinct from wrong and
  // from over-budget: this one was never going to be informative.
  std::string skipped;
  // The documented default configuration. When several candidates are
  // statistically tied, this is the one shipped: see `tie_margin`.
  bool is_default = false;
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

// Expected-best-first, so a cell that cannot compete is found early and cheaply.
//
// The order is not a guess: wider registers hold more lanes, and at a fixed width
// the packed-boolean-mask style is at least as fast as intrinsics on every shape
// measured while the lane-mask style is never faster and costs up to 46%
// (`probe_paired_styles`). So the sweep runs
//
//   clang_bool/512, intr/512, clang/512, clang_bool/256, intr/256, clang/256, ...
//
// and the first cell establishes a reference the rest are priced against. Without
// this the units come out in link order and the 128-bit cells -- three to four
// times slower here -- are tuned in full before anything knows they cannot win.
inline auto tsl_tune_unit_rank(TslTuneUnit const & unit) -> int {
  auto const style_rank = unit.style == TslStyle::ClangBoolMask ? 0
                        : unit.style == TslStyle::Intrinsics    ? 1
                                                               : 2;
  // Width descending, then style, then key width for a stable total order.
  return static_cast<int>((512 - unit.width) * 100 + style_rank * 10
                          + unit.element_bytes);
}

inline void tsl_sort_tune_units(std::vector<TslTuneUnit> & units) {
  std::stable_sort(units.begin(), units.end(),
                   [](TslTuneUnit const & a, TslTuneUnit const & b) {
                     return tsl_tune_unit_rank(a) < tsl_tune_unit_rank(b);
                   });
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
// `best_so_far` is the best per-element cost any candidate in this set has
// reached, or 0 before the first one finishes. It bounds every later candidate.
template <class Key, class Run>
auto geometric_score(TslDatasetSource<Key> & source, TslTuneProblem const & problem,
                     Run && run, double const * best_so_far = nullptr)
  -> TslTuneScore {
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
    // Two bounds, whichever bites first. The relative one is the useful one: at
    // `abandon_factor` times the best per-element cost seen so far, this shape's
    // single pass would take longer than any winner ever could, so there is
    // nothing to learn by finishing it. The absolute one stays as a backstop for
    // the first candidate, when there is no best yet.
    double per_shape_budget =
      problem.candidate_seconds > 0.0
        ? problem.candidate_seconds / static_cast<double>(problem.specs.size())
        : 0.0;
    if (best_so_far != nullptr && *best_so_far > 0.0
        && problem.abandon_factor > 0.0) {
      auto const relative = problem.abandon_factor * *best_so_far * 1e-9
                            * static_cast<double>(spec.rows);
      per_shape_budget = per_shape_budget > 0.0
                           ? std::min(per_shape_budget, relative)
                           : relative;
    }
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


// --- interleaved measurement ----------------------------------------------------
// Measuring candidate A to completion and then candidate B charges any drift
// between the two blocks to the A-B difference. On a quiet, pinned machine that
// drift is 1.0% at the median and 3.5% at the worst, which is larger than the
// differences the tuner exists to resolve: the top four samplesort candidates sat
// within 0.2% of each other, and two runs of the same binary named different
// winners. Interleaving -- one pass of every candidate, then the next round --
// removes drift slow relative to a round, which is what machine drift is.
//
// The cost is unchanged: the same number of passes per candidate, in a different
// order. What changes is that every candidate's sorter has to be live at once, so
// the sort is erased behind a callable rather than instantiated inside the loop.
template <class Key>
struct TslTuneEntrant {
  std::string axis;
  std::string label;
  TslTunedConfig config;
  bool is_default = false;
  // Sorts `index` for one dataset. Distinct types behind one signature, which is
  // the price of holding them all at once.
  std::function<void(TslSortColumn<Key> *, std::size_t, Key *, std::size_t,
                     std::size_t)> run;
};

namespace tsl_tune_detail {

// Interleave every entrant over one problem and return them as scored candidates.
template <class Key>
auto measure_interleaved(TslDatasetSource<Key> & source,
                         TslTuneProblem const & problem,
                         std::vector<TslTuneEntrant<Key>> const & entrants)
  -> std::vector<TslTuneCandidate> {
  std::vector<TslTuneCandidate> out;
  out.reserve(entrants.size());
  for (auto const & entrant : entrants) {
    TslTuneCandidate candidate;
    candidate.axis = entrant.axis;
    candidate.label = entrant.label;
    candidate.config = entrant.config;
    candidate.is_default = entrant.is_default;
    out.push_back(std::move(candidate));
  }
  // Per-shape medians, accumulated into a geometric mean at the end.
  std::vector<double> logs(entrants.size(), 0.0);
  std::vector<std::size_t> counted(entrants.size(), 0);
  std::vector<char> alive(entrants.size(), 1);
  // Which entrant is the documented default, and per-candidate evidence about
  // whether it is beaten. `wins` counts shapes where the ratio band clears 1.0,
  // `shapes` counts shapes where both ran, and the two must agree for a candidate
  // to displace the default.
  std::size_t default_at = entrants.size();
  for (std::size_t at = 0; at < entrants.size(); ++at) {
    if (entrants[at].is_default) {
      default_at = at;
    }
  }
  // Every per-round ratio against the default, pooled across shapes. Pooling
  // rather than requiring per-shape unanimity: unanimity is boundary-sensitive --
  // a candidate marginal on one shape is excluded in one run and admitted in the
  // next -- while pooling gives the quartile band more samples and a stabler
  // answer to the only question that matters, "is this resolvably faster".
  std::vector<std::vector<double>> ratios(entrants.size());

  // Pricing a cell: measure the default alone. One candidate is enough to say
  // whether a cell is within reach of the best cell so far, and fifteen are not
  // needed to say it is not.
  std::vector<char> priced(entrants.size(), 1);
  if (problem.probe_default_only && default_at < entrants.size()) {
    std::fill(priced.begin(), priced.end(), 0);
    priced[default_at] = 1;
    for (std::size_t at = 0; at < entrants.size(); ++at) {
      if (priced[at] == 0) {
        alive[at] = 0;
        out[at].skipped = "not measured: this cell was priced on its default alone";
      }
    }
  }

  for (auto const & spec : problem.specs) {
    auto const pristine = source.pristine(spec);
    auto const reference = source.reference(spec, TslDirection::Ascending);
    std::vector<TslSortColumn<Key>> columns;
    for (auto const & column : *pristine) {
      columns.push_back(TslSortColumn<Key>{const_cast<Key *>(column.data()),
                                           TslSortOrder::ASCENDING});
    }
    std::vector<Key> index(spec.rows);

    // One calibration pass each. It is the correctness check the harness would run
    // anyway, and timing it costs nothing extra -- so it also prices every
    // candidate before any of them is measured nine times. A candidate already
    // `abandon_factor` off the pace here cannot win, and is dropped before the
    // rounds rather than after them.
    std::vector<double> calibration(entrants.size(), 0.0);
    for (std::size_t at = 0; at < entrants.size(); ++at) {
      if (alive[at] == 0) {
        continue;
      }
      auto const start = std::chrono::steady_clock::now();
      entrants[at].run(columns.data(), spec.columns, index.data(), spec.rows,
                       problem.workers);
      calibration[at] = std::chrono::duration<double, std::nano>(
        std::chrono::steady_clock::now() - start).count()
        / static_cast<double>(spec.rows);
      if (!sorted_image_of_a_permutation(*pristine, *reference, index)) {
        out[at].failures.push_back(spec.id);
        alive[at] = 0;
      }
    }
    double best_calibration = 0.0;
    for (std::size_t at = 0; at < entrants.size(); ++at) {
      if (alive[at] != 0 && calibration[at] > 0.0
          && (best_calibration == 0.0 || calibration[at] < best_calibration)) {
        best_calibration = calibration[at];
      }
    }
    if (problem.abandon_factor > 0.0 && best_calibration > 0.0) {
      for (std::size_t at = 0; at < entrants.size(); ++at) {
        if (alive[at] != 0
            && calibration[at] > problem.abandon_factor * best_calibration) {
          out[at].over_budget = true;
          alive[at] = 0;
        }
      }
    }

    // The rounds. Every surviving candidate runs once per round, in a fixed order,
    // so a drift affecting one round affects all of them equally.
    std::vector<std::vector<double>> samples(entrants.size());
    for (int round = 0; round < tsl_paper_repetitions; ++round) {
      for (std::size_t at = 0; at < entrants.size(); ++at) {
        if (alive[at] == 0) {
          continue;
        }
        auto const start = std::chrono::steady_clock::now();
        entrants[at].run(columns.data(), spec.columns, index.data(), spec.rows,
                         problem.workers);
        samples[at].push_back(
          std::chrono::duration<double, std::nano>(
            std::chrono::steady_clock::now() - start).count()
          / static_cast<double>(spec.rows));
      }
    }
    // Paired ratios against the default, computed round by round *before* the
    // per-candidate samples are sorted: pairing only cancels drift while the rounds
    // still line up.
    if (default_at < entrants.size() && alive[default_at] != 0
        && !samples[default_at].empty()) {
      for (std::size_t at = 0; at < entrants.size(); ++at) {
        if (at == default_at || alive[at] == 0
            || samples[at].size() != samples[default_at].size()) {
          continue;
        }
        for (std::size_t round = 0; round < samples[at].size(); ++round) {
          if (samples[default_at][round] > 0.0) {
            ratios[at].push_back(samples[at][round] / samples[default_at][round]);
          }
        }
      }
    }
    for (std::size_t at = 0; at < entrants.size(); ++at) {
      if (alive[at] == 0 || samples[at].empty()) {
        continue;
      }
      std::sort(samples[at].begin(), samples[at].end());
      auto const median = samples[at][samples[at].size() / 2];
      out[at].per_shape.push_back(median);
      logs[at] += std::log(median);
      ++counted[at];
    }
  }

  for (std::size_t at = 0; at < entrants.size(); ++at) {
    if (counted[at] == 0 || !out[at].failures.empty() || out[at].over_budget) {
      out[at].score = 0.0;
      continue;
    }
    out[at].score = std::exp(logs[at] / static_cast<double>(counted[at]));
    if (!ratios[at].empty()) {
      auto & pooled = ratios[at];
      std::sort(pooled.begin(), pooled.end());
      out[at].ratio_to_default = pooled[pooled.size() / 2];
      // Resolvably faster: the upper quartile of the pooled ratio is below one, so
      // three quarters of the paired rounds had this candidate ahead.
      out[at].beats_default = pooled[(3 * pooled.size()) / 4] < 1.0;
    }
  }
  return out;
}

}  // namespace tsl_tune_detail

// --- samplesort ---------------------------------------------------------------

template <class Key, class Simd, int K, TslSampleSortBuckets B, TslSampleSortBase P,
          std::size_t BC, std::size_t F, TslSampleSortIds I,
          TslSampleSortMovement M>
auto tsl_tune_samplesort_point(TslDatasetSource<Key> & source,
                               TslTuneProblem const & problem,
                               double const * best_so_far = nullptr)
  -> TslTuneScore {
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
                              std::size_t partition_threshold,
                              double const * best_so_far = nullptr)
  -> TslTuneScore {
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
