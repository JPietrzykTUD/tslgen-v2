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
  // Price a cell without tuning it: run every candidate's calibration pass on the
  // first shape and stop. One pass each, no timed rounds.
  //
  // Not "measure the default and judge the cell by it" -- the default is not
  // guaranteed representative, and excluding fourteen candidates on a fifteenth's
  // number is the weakest step in the whole search. Every candidate is priced on its
  // own measurement, which is also *cheaper* than the default's full measurement was:
  // twenty-one single passes against one candidate's forty.
  bool probe_calibration_only = false;
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
  // An absolute wall-clock bound per candidate, checked *between* passes. It is a
  // backstop for the one case the relative rule cannot cover: the first candidate
  // measured, and the default-only probe, where there is no better candidate yet to
  // be five times worse than.
  //
  // What it cannot do is interrupt a pass in flight. A single sort is the indivisible
  // unit here, so a candidate that is pathological on its first pass runs that pass
  // to completion whatever this is set to -- which is why the quadratic two-way
  // candidate is excluded structurally, on the working-set size, rather than left to
  // a timeout to catch. 0 disables it.
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

    // Pricing mode stops here: every candidate has one measured pass on this shape,
    // which is what the caller asked for. The score is left at zero -- a single pass
    // is not a measurement -- and the calibration is reported through `per_shape` so
    // the caller can price the cell without mistaking it for a tuning result.
    if (problem.probe_calibration_only) {
      for (std::size_t at = 0; at < entrants.size(); ++at) {
        if (alive[at] != 0 && calibration[at] > 0.0) {
          out[at].per_shape.push_back(calibration[at]);
        }
        out[at].skipped = "priced only: one calibration pass, no timed rounds";
      }
      return out;
    }

    // The absolute bound, applied to what the calibration pass revealed. Checked
    // here rather than during a pass, because a pass cannot be interrupted.
    if (problem.candidate_seconds > 0.0) {
      auto const per_shape =
        problem.candidate_seconds / static_cast<double>(problem.specs.size());
      for (std::size_t at = 0; at < entrants.size(); ++at) {
        // The calibration is per element; one pass over this shape is that times the
        // rows. If a single pass already exceeds the share, nine rounds cannot fit.
        auto const one_pass = calibration[at] * 1e-9
                              * static_cast<double>(spec.rows);
        if (alive[at] != 0 && calibration[at] > 0.0
            && one_pass * tsl_paper_repetitions > per_shape) {
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
