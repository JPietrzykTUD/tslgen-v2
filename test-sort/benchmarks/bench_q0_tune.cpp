// Q0: the design-space exploration every later number depends on.
//
// This runs first. It searches the knob space per (style, width), writes the
// winner to a file, and every reporting driver reads that file — so the tuned
// values live in the results rather than in source, re-tuning on new hardware is
// a run rather than an edit, and the figures stay reproducible from one command.
//
// The search's shape and its one real limitation are documented in
// q0_tune_impl.hpp: a cross over the axes that interact, one-factor-at-a-time
// around the default for the rest, and no second descent round without a rebuild.
//
//   ./bench_q0_tune --out results/best_config.tsv
//   ./bench_q0_tune --shapes tpcds_q67_sf1,skewed_zipf_s1 --workers 24
//
// See docs/benchmark-plan.md.

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <map>
#include <string>
#include <tuple>
#include <vector>

#include "paper_harness.hpp"
#include "q0_tune_impl.hpp"

namespace {

auto split(std::string const & text, char separator) -> std::vector<std::string> {
  std::vector<std::string> parts;
  std::size_t start = 0;
  while (start <= text.size()) {
    auto const cut = text.find(separator, start);
    auto const end = cut == std::string::npos ? text.size() : cut;
    if (end > start) {
      parts.push_back(text.substr(start, end - start));
    }
    if (cut == std::string::npos) {
      break;
    }
    start = cut + 1;
  }
  return parts;
}

// The winner overall, plus the winner on each coordinate, which is what makes the
// output readable as a design-space answer rather than a single number.
struct Outcome {
  TslTuneCandidate best;                    // what is shipped
  TslTuneCandidate fastest;                 // the lowest number measured
  std::vector<TslTuneCandidate> tied;       // indistinguishable from `fastest`
  std::map<std::string, TslTuneCandidate> per_axis;
};

// The fastest candidate, everything statistically tied with it, and the one to
// ship. Shipping the default when it is tied is what makes the answer stable: the
// alternative is a configuration that changes between two runs of the same binary.
auto summarise(std::vector<TslTuneCandidate> const & candidates, double tie_margin)
  -> Outcome {
  Outcome outcome;
  for (auto const & candidate : candidates) {
    if (candidate.score <= 0.0) {
      continue;  // sorted wrongly; never a winner
    }
    if (outcome.fastest.score <= 0.0 || candidate.score < outcome.fastest.score) {
      outcome.fastest = candidate;
    }
    auto const existing = outcome.per_axis.find(candidate.axis);
    if (existing == outcome.per_axis.end() || candidate.score < existing->second.score) {
      outcome.per_axis[candidate.axis] = candidate;
    }
  }
  if (outcome.fastest.score <= 0.0) {
    return outcome;
  }
  auto const ceiling = outcome.fastest.score * (1.0 + tie_margin);
  for (auto const & candidate : candidates) {
    if (candidate.score > 0.0 && candidate.score <= ceiling) {
      outcome.tied.push_back(candidate);
    }
  }
  // Ship the default when it is among the tied; otherwise the fastest.
  outcome.best = outcome.fastest;
  for (auto const & candidate : outcome.tied) {
    if (candidate.is_default) {
      outcome.best = candidate;
      break;
    }
  }
  return outcome;
}

void report(char const * algorithm, TslStyle style, std::size_t width,
            std::vector<TslTuneCandidate> const & candidates, Outcome const & outcome,
            double tie_margin) {
  std::printf("\n%s, %s/%zu-bit — %zu candidates\n", algorithm,
              tsl_style_name(style), width, candidates.size());
  std::printf("  %-12s %-24s %12s %8s\n", "axis", "value", "ns/elem", "vs best");
  auto sorted = candidates;
  std::sort(sorted.begin(), sorted.end(),
            [](TslTuneCandidate const & a, TslTuneCandidate const & b) {
              if (a.score <= 0.0) return false;
              if (b.score <= 0.0) return true;
              return a.score < b.score;
            });
  auto const ceiling = outcome.fastest.score > 0.0
                         ? outcome.fastest.score * (1.0 + tie_margin) : 0.0;
  for (auto const & candidate : sorted) {
    if (!candidate.skipped.empty()) {
      std::printf("  %-12s %-24s %12s  %s\n", candidate.axis.c_str(),
                  candidate.label.c_str(), "SKIPPED", candidate.skipped.c_str());
      continue;
    }
    if (candidate.score <= 0.0 && candidate.over_budget) {
      std::printf("  %-12s %-24s %12s  %s\n", candidate.axis.c_str(),
                  candidate.label.c_str(), "OVER BUDGET",
                  "abandoned on time; cannot be a winner");
      continue;
    }
    if (candidate.score <= 0.0) {
      // Name the shape: an incorrect candidate is a bug to fix, and "which shape"
      // is the first thing needed to start.
      std::string where;
      for (auto const & shape : candidate.failures) {
        where += (where.empty() ? "" : ",") + shape;
      }
      std::printf("  %-12s %-24s %12s  %s\n", candidate.axis.c_str(),
                  candidate.label.c_str(), "INCORRECT",
                  where.empty() ? "-" : where.c_str());
      continue;
    }
    char const * mark = "";
    if (candidate.score <= ceiling) {
      mark = candidate.is_default ? "  <- tied, shipped (default)" : "  <- tied";
    }
    std::printf("  %-12s %-24s %12.2f %7.2fx%s\n", candidate.axis.c_str(),
                candidate.label.c_str(), candidate.score,
                candidate.score / outcome.fastest.score, mark);
  }
}


// Is the win in choosing the algorithm, or in tuning the algorithm you chose?
//
// The descent ranks configurations by their geometric mean over the shapes, which
// answers "what should we ship" and hides "does one answer even exist". This is
// the 2x2 that separates the two. Per shape, four costs:
//
//   fixed/fixed   one algorithm, one configuration -- what a paper reports as
//                 "our sort", the globally best single point across both
//   fixed/tuned   that same algorithm, re-tuned per shape
//   picked/fixed  algorithm picked per shape, each at its own global best config
//   picked/tuned  the per-shape best point anywhere in the space
//
// Read as geometric means over the shapes, `fixed/fixed / picked/fixed` is what
// dispatching on the algorithm buys, and `fixed/fixed / fixed/tuned` is what
// re-tuning buys. Whichever is larger is where the engineering belongs; if
// `picked/tuned` is much better than both, the two interact and neither alone is
// enough.
struct Decomposition {
  std::vector<std::string> shapes;
  std::vector<double> fixed_fixed, fixed_tuned, picked_fixed, picked_tuned;
  std::vector<char const *> fixed_algorithm, picked_algorithm;
  std::string global_label;
};

auto geomean(std::vector<double> const & values) -> double {
  double logs = 0.0;
  std::size_t counted = 0;
  for (auto const value : values) {
    if (value > 0.0) { logs += std::log(value); ++counted; }
  }
  return counted == 0 ? 0.0 : std::exp(logs / static_cast<double>(counted));
}

auto decompose(TslTuneProblem const & problem,
               std::vector<TslTuneCandidate> const & samplesort,
               std::vector<TslTuneCandidate> const & quicksort) -> Decomposition {
  Decomposition out;
  auto const shape_count = problem.specs.size();
  for (auto const & spec : problem.specs) {
    out.shapes.push_back(spec.id);
  }

  // A candidate only counts if it measured every shape correctly, so the four
  // costs are all drawn from the same population.
  auto usable = [&](TslTuneCandidate const & c) {
    return c.score > 0.0 && c.per_shape.size() == shape_count;
  };
  auto best_overall = [&](std::vector<TslTuneCandidate> const & set)
    -> TslTuneCandidate const * {
    TslTuneCandidate const * best = nullptr;
    for (auto const & c : set) {
      if (usable(c) && (best == nullptr || c.score < best->score)) { best = &c; }
    }
    return best;
  };

  auto const * sample_global = best_overall(samplesort);
  auto const * quick_global = best_overall(quicksort);
  if (sample_global == nullptr || quick_global == nullptr) {
    return out;  // one algorithm failed everywhere; nothing to decompose
  }

  // The single global point: one algorithm, one configuration, for all shapes.
  auto const * global = sample_global->score <= quick_global->score ? sample_global
                                                                   : quick_global;
  char const * global_algorithm =
    global == sample_global ? "samplesort" : "quicksort";
  out.global_label = std::string(global_algorithm) + " " + global->label;

  for (std::size_t at = 0; at < shape_count; ++at) {
    auto per_shape_best = [&](std::vector<TslTuneCandidate> const & set) {
      double best = 0.0;
      for (auto const & c : set) {
        if (usable(c) && (best == 0.0 || c.per_shape[at] < best)) {
          best = c.per_shape[at];
        }
      }
      return best;
    };
    auto const sample_tuned = per_shape_best(samplesort);
    auto const quick_tuned = per_shape_best(quicksort);
    auto const sample_at = sample_global->per_shape[at];
    auto const quick_at = quick_global->per_shape[at];

    out.fixed_fixed.push_back(global->per_shape[at]);
    out.fixed_algorithm.push_back(global_algorithm);
    // "the same algorithm, re-tuned": the algorithm the global point chose.
    out.fixed_tuned.push_back(global == sample_global ? sample_tuned : quick_tuned);
    out.picked_fixed.push_back(std::min(sample_at, quick_at));
    out.picked_algorithm.push_back(sample_at <= quick_at ? "samplesort" : "quicksort");
    out.picked_tuned.push_back(std::min(sample_tuned, quick_tuned));
  }
  return out;
}

void report_decomposition(Decomposition const & d) {
  if (d.shapes.empty() || d.fixed_fixed.empty()) {
    std::printf("\n  (no decomposition: an algorithm failed on the tuning set)\n");
    return;
  }
  std::printf("\nalgorithm choice vs configuration choice — ns/element\n");
  std::printf("  the one global point is %s\n", d.global_label.c_str());
  std::printf("  %-30s %11s %11s %11s %11s  %s\n", "shape", "fixed/fixed",
              "fixed/tuned", "pick/fixed", "pick/tuned", "picked");
  for (std::size_t at = 0; at < d.shapes.size(); ++at) {
    std::printf("  %-30s %11.2f %11.2f %11.2f %11.2f  %s\n", d.shapes[at].c_str(),
                d.fixed_fixed[at], d.fixed_tuned[at], d.picked_fixed[at],
                d.picked_tuned[at], d.picked_algorithm[at]);
  }
  auto const ff = geomean(d.fixed_fixed);
  auto const ft = geomean(d.fixed_tuned);
  auto const pf = geomean(d.picked_fixed);
  auto const pt = geomean(d.picked_tuned);
  std::printf("  %-30s %11.2f %11.2f %11.2f %11.2f\n", "geometric mean",
              ff, ft, pf, pt);
  if (ff > 0.0) {
    std::printf("\n  re-tuning the fixed algorithm per shape   %5.2fx\n", ff / ft);
    std::printf("  picking the algorithm per shape           %5.2fx\n", ff / pf);
    std::printf("  both                                     %5.2fx\n", ff / pt);
    auto const algorithm_wins = ff / pf >= ff / ft;
    std::printf("  --> %s is the larger lever here%s\n",
                algorithm_wins ? "algorithm choice" : "configuration",
                (ff / pt) > 1.15 * std::max(ff / ft, ff / pf)
                  ? "; they also interact, so neither alone suffices" : "");
  }
}

}  // namespace

int main(int argc, char ** argv) {
  std::vector<std::string> shapes{"tpcds_q67_sf1", "skewed_zipf_s1",
                                  "low_cardinality_d4", "independent_uniform_c1024"};
  // Intrinsics only, by default. Style is an axis to *compare*, not to choose --
  // `probe_paired_styles` is the instrument for it, and Q6 reports it -- so the
  // knobs of the clang cells are read by nothing. Tuning all nine cells spent six
  // ninths of a three-and-a-half-hour run producing configurations no driver looks
  // up. What Q0 must still decide is the register *width* at the built style, which
  // is three cells. Pass --styles to widen it when the cross-style knob comparison
  // is the question.
  std::vector<std::string> style_names{"intr"};
  std::vector<std::size_t> widths;
  // 0 means "derive it from the cache", which is what happens unless --rows says
  // otherwise. A literal here is how the tuner came to run entirely inside the LLC.
  std::size_t rows = 0;
  std::size_t columns = 4;
  std::vector<std::size_t> worker_counts{1, 24};
  std::string out_path = "best_config.tsv";
  std::string tpcds_dir;
  std::string csv_path;
  bool verify_only = false;
  double problem_seconds = 0.0;
  // How much better a cell must be to displace intrinsics at the widest width.
  // Default from the measured noise floor: the byte-identical control varied by
  // about 4% between runs, so 5% is the smallest gap worth acting on.
  double cell_margin = 0.05;
  double tie_margin = 0.04;

  for (int i = 1; i < argc; ++i) {
    auto const flag = std::string(argv[i]);
    auto const value = [&]() -> std::string { return i + 1 < argc ? argv[++i] : ""; };
    if (flag == "--shapes") {
      shapes = split(value(), ',');
    } else if (flag == "--styles") {
      style_names = split(value(), ',');
    } else if (flag == "--widths") {
      widths.clear();
      for (auto const & part : split(value(), ',')) {
        widths.push_back(std::strtoull(part.c_str(), nullptr, 10));
      }
    } else if (flag == "--rows") {
      rows = std::strtoull(value().c_str(), nullptr, 10);
    } else if (flag == "--cols") {
      columns = std::strtoull(value().c_str(), nullptr, 10);
    } else if (flag == "--workers") {
      worker_counts.clear();
      for (auto const & part : split(value(), ',')) {
        worker_counts.push_back(std::strtoull(part.c_str(), nullptr, 10));
      }
    } else if (flag == "--tpcds-dir") {
      tpcds_dir = value();
    } else if (flag == "--tie-margin") {
      tie_margin = std::strtod(value().c_str(), nullptr) / 100.0;
    } else if (flag == "--cell-margin") {
      cell_margin = std::strtod(value().c_str(), nullptr) / 100.0;
    } else if (flag == "--candidate-seconds") {
      problem_seconds = std::strtod(value().c_str(), nullptr);
    } else if (flag == "--verify-only") {
      verify_only = true;
      rows = 1u << 16;  // correctness does not need size; overridable with --rows
    } else if (flag == "--out") {
      out_path = value();
    } else if (flag == "--csv") {
      csv_path = value();
    } else {
      std::printf("unknown argument: %s\n", flag.c_str());
      return 2;
    }
  }

  TslPaperResults results("Q0 tuning", "bench_q0_tune");
  if (rows == 0) {
    // Big enough that the working set misses the last level by a comfortable
    // factor. Keys, the index and the out-of-place scratch are all live at once,
    // so the footprint is roughly (columns + 2) * rows * element_bytes; four times
    // the LLC puts every candidate in the regime the reported figures live in.
    auto const llc = results.machine().llc_bytes > 0
                       ? results.machine().llc_bytes
                       : 32ull * 1024 * 1024;
    auto const per_row = (columns + 2) * 4;   // the u32 pass; u64 is larger still
    auto const wanted = 4 * llc / per_row;
    rows = 1;
    while (rows < wanted) {
      rows *= 2;                              // the catalog offers powers of two
    }
    std::printf("rows not given: using %zu, about %zu MiB of live data against a "
                "%zu MiB LLC. Tuning inside the cache would choose knobs for a "
                "regime no reported figure measures.\n",
                rows, rows * per_row / (1024 * 1024), llc / (1024 * 1024));
  }

  // The problem every candidate is scored on. Several shapes so the winner is not
  // fitted to one, and the row count and column count fixed so the only thing
  // varying is the configuration.
  // One spec list per key width: a unit tunes one width, and the datasets it is
  // scored on must be that width.
  auto build_problem = [&](std::size_t element_bytes) {
    TslTuneProblem problem;
    problem.candidate_seconds = problem_seconds;
    problem.tie_margin = tie_margin;
    auto const catalog = tsl_default_catalog(rows, columns, element_bytes);
    auto const tail = "_u" + std::to_string(element_bytes * 8) + "_n";
    for (auto const & shape : shapes) {
      auto const prefix = shape + tail;
      for (auto const & spec : catalog) {
        if (spec.id.rfind(prefix, 0) == 0) {
          problem.specs.push_back(spec);
          break;
        }
      }
    }
    for (auto const & spec : tsl_external_catalog(tpcds_dir, element_bytes)) {
      problem.specs.push_back(spec);
    }
    return problem;
  };

  std::map<std::size_t, TslTuneProblem> problems;
  for (auto const element_bytes : {std::size_t{4}, std::size_t{8}}) {
    auto problem = build_problem(element_bytes);
    if (problem.specs.empty()) {
      std::printf("no datasets at %zu rows x %zu columns for u%zu; skipping that "
                  "key width\n", rows, columns, element_bytes * 8);
      continue;
    }
    std::printf("\nu%zu: tuning on %zu shapes\n", element_bytes * 8,
                problem.specs.size());
    for (auto const & spec : problem.specs) {
      std::printf("  %-42s %9zu rows x %2zu columns\n", spec.id.c_str(), spec.rows,
                  spec.columns);
    }
    problems.emplace(element_bytes, std::move(problem));
  }
  if (problems.empty()) {
    std::printf("nothing to tune\n");
    return 1;
  }

  // A correctness sweep is a different job from tuning and gets its own exit
  // code, so it can gate a commit. It visits every unit at every key width, not
  // just the ones a tuning run happens to be pointed at.
  if (verify_only) {
    std::size_t checked = 0;
    std::size_t broken = 0;
    for (auto const & unit : tsl_tune_units()) {
      if (!style_names.empty()
          && std::find(style_names.begin(), style_names.end(),
                       std::string(tsl_style_name(unit.style))) == style_names.end()) {
        continue;
      }
      if (!widths.empty()
          && std::find(widths.begin(), widths.end(), unit.width) == widths.end()) {
        continue;
      }
      auto const found = problems.find(unit.element_bytes);
      if (found == problems.end()) {
        continue;
      }
      auto problem = found->second;
      problem.verify_only = true;
      problem.workers = worker_counts.empty() ? 1 : worker_counts.back();
      std::printf("\n%s / %zu-bit / u%zu / %zu workers\n",
                  tsl_style_name(unit.style), unit.width, unit.element_bytes * 8,
                  problem.workers);
      for (auto const * set : {&unit.samplesort, &unit.quicksort}) {
        auto const algorithm = set == &unit.samplesort ? "samplesort" : "quicksort";
        for (auto const & candidate : (*set)(problem)) {
          if (!candidate.skipped.empty()) {
            continue;
          }
          ++checked;
          if (candidate.failures.empty()) {
            continue;
          }
          ++broken;
          std::printf("  WRONG  %-11s %-12s %-22s on", algorithm,
                      candidate.axis.c_str(), candidate.label.c_str());
          for (auto const & shape : candidate.failures) {
            std::printf(" %s", shape.c_str());
          }
          std::printf("\n");
        }
      }
      std::printf("  %zu configurations checked so far, %zu wrong\n", checked,
                  broken);
    }
    std::printf("\n%zu configurations checked, %zu sorted wrongly\n", checked,
                broken);
    if (checked == 0) {
      // A gate that passes having checked nothing is worse than no gate.
      std::printf("no unit matched the filters: nothing was verified\n");
      return 1;
    }
    return broken == 0 ? 0 : 1;
  }

  // 21 candidates per (style, width, key width) unit at each worker count.
  results.expect(tsl_tune_units().size() * worker_counts.size() * 21);

  std::map<std::string, TslTunedConfig> tuned;
  // Best score per (style, width, key width), so the cell the reporting drivers
  // were *built* for can be compared against the cell that actually won. Without
  // this the style and width axes are explored and then discarded: the drivers can
  // only be built for one cell, so the least they can do is say when it is wrong.
  std::map<std::tuple<std::string, std::size_t, std::size_t>, double> cell_best;

  for (auto const & unit : tsl_tune_units()) {
    if (!style_names.empty()
        && std::find(style_names.begin(), style_names.end(),
                     std::string(tsl_style_name(unit.style))) == style_names.end()) {
      continue;
    }
    if (!widths.empty()
        && std::find(widths.begin(), widths.end(), unit.width) == widths.end()) {
      continue;
    }
    auto const found = problems.find(unit.element_bytes);
    if (found == problems.end()) {
      continue;  // no datasets at this key width; already reported
    }
    auto problem = found->second;
    for (auto const workers : worker_counts) {
      problem.workers = workers;
      // Lanes, spelled out, because that is what the algorithm actually sees.
      // A sorting network holds `lanes * rows`; the base case, the bucket count
      // and the leaf capacity all scale with lanes. So register width and value
      // width are not two independent axes here -- their ratio is the axis, and
      // 256-bit/u32 is the same eight lanes as 512-bit/u64. Printing it makes that
      // checkable instead of hidden behind two numbers that look unrelated.
      auto const lanes = unit.width / (8 * unit.element_bytes);
      std::printf("\n================ %s / %zu-bit / u%zu = %zu lanes / %zu worker%s\n",
                  tsl_style_name(unit.style), unit.width, unit.element_bytes * 8,
                  lanes, workers, workers == 1 ? "" : "s");

      auto const samplesort = unit.samplesort(problem);
      auto const sample_outcome = summarise(samplesort, tie_margin);
      report("samplesort", unit.style, unit.width, samplesort, sample_outcome,
             tie_margin);

      auto const quicksort = unit.quicksort(problem);
      auto const quick_outcome = summarise(quicksort, tie_margin);
      report("quicksort", unit.style, unit.width, quicksort, quick_outcome,
             tie_margin);

      report_decomposition(decompose(problem, samplesort, quicksort));

      if (workers == worker_counts.front()) {
        auto const key = std::make_tuple(std::string(tsl_style_name(unit.style)),
                                         unit.width, unit.element_bytes);
        for (auto const * set : {&samplesort, &quicksort}) {
          for (auto const & candidate : *set) {
            if (candidate.score <= 0.0) {
              continue;
            }
            auto const found = cell_best.find(key);
            if (found == cell_best.end() || candidate.score < found->second) {
              cell_best[key] = candidate.score;
            }
          }
        }
      }

      // One row per algorithm per cell, with the workers folded into the key so a
      // serial and a parallel run can disagree about the best configuration --
      // which, given the thread count changes what a bucket costs, they may.
      // Only a configuration that actually sorted correctly may be published. An
      // outcome with no correct candidate carries a default-constructed config,
      // and writing that stamped `from_file` would hand the reporting drivers a
      // configuration nothing measured while labelling it tuned.
      if (workers == worker_counts.front()) {
        auto publish = [&](char const * algorithm, Outcome const & outcome) {
          if (outcome.best.score <= 0.0) {
            std::printf("  !! %s/%s/%zu-bit/u%zu: no candidate sorted correctly; "
                        "publishing nothing for this cell\n",
                        algorithm, tsl_style_name(unit.style), unit.width,
                        unit.element_bytes * 8);
            return;
          }
          auto config = outcome.best.config;
          config.from_file = true;
          tuned[tsl_tuned_key(algorithm, unit.style, unit.width,
                              unit.element_bytes)] = config;
        };
        publish("samplesort", sample_outcome);
        publish("quicksort", quick_outcome);
      }

      for (auto const * pair : {&samplesort, &quicksort}) {
        auto const algorithm = pair == &samplesort ? "samplesort" : "quicksort";
        for (auto const & candidate : *pair) {
          auto row = results.make_row();
          row.shape = "tuning-set";
          row.shape_params = std::to_string(problem.specs.size()) + " shapes";
          row.rows = rows;
          row.columns = columns;
          row.element_bytes = unit.element_bytes;
          row.algorithm = algorithm;
          row.variant = std::string(tsl_style_name(unit.style)) + "/"
                        + std::to_string(unit.width) + " " + candidate.axis + "="
                        + candidate.label;
          row.detector = "scalar";
          row.workers = workers;
          row.verified = candidate.score > 0.0;
          row.ns_per_element.median = candidate.score;
          row.ns_per_element.p25 = candidate.score;
          row.ns_per_element.p75 = candidate.score;
          results.add(std::move(row));
        }
      }
    }
  }

  tsl_write_tuned(out_path, tuned);
  std::printf("\nwrote %s (%zu configurations)\n", out_path.c_str(), tuned.size());
  for (auto const & [key, config] : tuned) {
    std::printf("  %-34s %s\n", key.c_str(),
                key.rfind("samplesort", 0) == 0 ? config.describe_samplesort().c_str()
                                                : config.describe_quicksort().c_str());
  }
  // Which cell won, and whether the reporting drivers were built for it.
  if (!cell_best.empty()) {
    std::printf("\nbest configuration per (style, width) cell\n");
    for (auto const element_bytes : {std::size_t{4}, std::size_t{8}}) {
      std::vector<std::pair<std::tuple<std::string, std::size_t, std::size_t>,
                            double>> cells;
      for (auto const & entry : cell_best) {
        if (std::get<2>(entry.first) == element_bytes) {
          cells.push_back(entry);
        }
      }
      if (cells.empty()) {
        continue;
      }
      std::sort(cells.begin(), cells.end(),
                [](auto const & a, auto const & b) { return a.second < b.second; });
      auto const & winner = cells.front();
      std::printf("  u%zu:", element_bytes * 8);
      for (auto const & cell : cells) {
        std::printf("  %s/%zu %.2f (%.2fx)", std::get<0>(cell.first).c_str(),
                    std::get<1>(cell.first), cell.second,
                    cell.second / winner.second);
      }
      std::printf("\n");
      auto const built = std::make_tuple(std::string(tsl_style_name(tsl_measure_style)),
                                         tsl_measure_width, element_bytes);
      auto const here = cell_best.find(built);
      if (here == cell_best.end()) {
        continue;
      }
      auto const penalty = here->second / winner.second;
      std::printf("       the reporting drivers are built for %s/%zu, %.2fx the "
                  "best cell (%s/%zu)\n",
                  std::get<0>(built).c_str(), std::get<1>(built), penalty,
                  std::get<0>(winner.first).c_str(), std::get<1>(winner.first));
      if (penalty > 1.10) {
        std::printf("  !! that is more than 10%% off: rebuild with "
                    "-DTSL_COSORT_MEASURE_STYLE=%s -DTSL_COSORT_MEASURE_WIDTH=%zu "
                    "before publishing, or the reported numbers understate the "
                    "sorter on this host\n",
                    std::get<0>(winner.first).c_str(), std::get<1>(winner.first));
      }
    }
  }

  // One machine-readable line naming the cell to build the reporting drivers for.
  // Combined across key widths by geometric mean, because the drivers are built
  // once and measure both: picking the u32 winner would be arbitrary where the two
  // disagree. `run_all.sh` reads this, then builds everything else for that cell.
  //
  // A cell only wins by a *margin*. Ranking nine cells by strict less-than made
  // this suite build every reporting driver for ClangBuiltin/128-bit -- a
  // four-lane configuration -- because it came out 2% ahead on a probe whose own
  // noise floor is wider than that. The byte-identical `intr` control in the TSL
  // A/B spanned 0.913x to 1.039x across runs, so a gap under about 4% carries no
  // information, and seven of the nine cells sat inside 2% of each other.
  //
  // So the incumbent is Intrinsics at the widest register, a tie goes to it, and a
  // challenger has to clear `cell_margin` to displace it. The full ranking is
  // printed either way: the design-space answer is the table, not the winner.
  if (!cell_best.empty()) {
    std::map<std::pair<std::string, std::size_t>, std::pair<double, int>> combined;
    for (auto const & entry : cell_best) {
      auto & slot = combined[{std::get<0>(entry.first), std::get<1>(entry.first)}];
      slot.first += std::log(entry.second);
      ++slot.second;
    }
    std::vector<std::pair<std::pair<std::string, std::size_t>, double>> ranked;
    for (auto const & entry : combined) {
      if (entry.second.second == 0) {
        continue;
      }
      ranked.push_back({entry.first,
                        std::exp(entry.second.first
                                 / static_cast<double>(entry.second.second))});
    }
    std::sort(ranked.begin(), ranked.end(),
              [](auto const & a, auto const & b) { return a.second < b.second; });

    // The incumbent: intrinsics at the widest register width measured.
    std::string incumbent_style = "intr";
    std::size_t incumbent_width = 0;
    double incumbent_score = 0.0;
    for (auto const & entry : ranked) {
      if (entry.first.first == incumbent_style
          && entry.first.second > incumbent_width) {
        incumbent_width = entry.first.second;
        incumbent_score = entry.second;
      }
    }

    if (!ranked.empty()) {
      std::printf("\ncell ranking, geometric mean over key widths (ns/element)\n");
      for (auto const & entry : ranked) {
        auto const relative = incumbent_score > 0.0 ? entry.second / incumbent_score
                                                    : 0.0;
        std::printf("  %-12s %4zu-bit %10.2f  %6.3fx vs incumbent%s\n",
                    entry.first.first.c_str(), entry.first.second, entry.second,
                    relative,
                    entry.first == std::make_pair(incumbent_style, incumbent_width)
                      ? "  <- incumbent" : "");
      }
    }

    auto const & winner = ranked.front();
    auto const gain = (incumbent_score > 0.0 && winner.second > 0.0)
                        ? incumbent_score / winner.second
                        : 1.0;
    auto chosen = winner.first;
    if (incumbent_width == 0) {
      std::printf("\nno intrinsics cell was measured; naming the ranking's "
                  "leader\n");
    } else if (gain < 1.0 + cell_margin) {
      chosen = {incumbent_style, incumbent_width};
      std::printf("\nleader %s/%zu-bit is only %.1f%% ahead of the incumbent "
                  "%s/%zu-bit, under the %.0f%% margin: keeping the incumbent. A "
                  "gap this size is inside the run-to-run noise and would pick a "
                  "cell at random.\n",
                  winner.first.first.c_str(), winner.first.second,
                  (gain - 1.0) * 100.0, incumbent_style.c_str(), incumbent_width,
                  cell_margin * 100.0);
    } else {
      std::printf("\n%s/%zu-bit beats the incumbent %s/%zu-bit by %.1f%%, clearing "
                  "the %.0f%% margin\n",
                  winner.first.first.c_str(), winner.first.second,
                  incumbent_style.c_str(), incumbent_width, (gain - 1.0) * 100.0,
                  cell_margin * 100.0);
    }
    std::printf("\nTSL_COSORT_BEST_CELL %s %zu %.4f\n", chosen.first.c_str(),
                chosen.second, winner.second);
  }

  std::printf("\n%s\n", results.summary().c_str());
  if (!csv_path.empty()) {
    results.write_csv(csv_path);
  }
  return 0;
}
