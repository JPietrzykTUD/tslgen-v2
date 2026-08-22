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
#include <cstdio>
#include <cstring>
#include <map>
#include <string>
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
  TslTuneCandidate best;
  std::map<std::string, TslTuneCandidate> per_axis;
};

auto summarise(std::vector<TslTuneCandidate> const & candidates) -> Outcome {
  Outcome outcome;
  for (auto const & candidate : candidates) {
    if (candidate.score <= 0.0) {
      continue;  // sorted wrongly; never a winner
    }
    if (outcome.best.score <= 0.0 || candidate.score < outcome.best.score) {
      outcome.best = candidate;
    }
    auto const existing = outcome.per_axis.find(candidate.axis);
    if (existing == outcome.per_axis.end() || candidate.score < existing->second.score) {
      outcome.per_axis[candidate.axis] = candidate;
    }
  }
  return outcome;
}

void report(char const * algorithm, TslStyle style, std::size_t width,
            std::vector<TslTuneCandidate> const & candidates, Outcome const & outcome) {
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
  for (auto const & candidate : sorted) {
    if (candidate.score <= 0.0) {
      std::printf("  %-12s %-24s %12s %8s\n", candidate.axis.c_str(),
                  candidate.label.c_str(), "INCORRECT", "-");
      continue;
    }
    std::printf("  %-12s %-24s %12.2f %7.2fx%s\n", candidate.axis.c_str(),
                candidate.label.c_str(), candidate.score,
                candidate.score / outcome.best.score,
                &candidate == &sorted.front() ? "  <- best" : "");
  }
}

}  // namespace

int main(int argc, char ** argv) {
  std::vector<std::string> shapes{"tpcds_q67_sf1", "skewed_zipf_s1",
                                  "low_cardinality_d4", "independent_uniform_c1024"};
  std::vector<std::string> style_names;
  std::vector<std::size_t> widths;
  std::size_t rows = 1u << 20;
  std::size_t columns = 4;
  std::vector<std::size_t> worker_counts{1, 24};
  std::string out_path = "best_config.tsv";
  std::string csv_path;

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

  // The problem every candidate is scored on. Several shapes so the winner is not
  // fitted to one, and the row count and column count fixed so the only thing
  // varying is the configuration.
  TslTuneProblem problem;
  auto const catalog = tsl_default_catalog(rows, columns, 4);
  for (auto const & shape : shapes) {
    auto const prefix = shape + "_u32_n";
    for (auto const & spec : catalog) {
      if (spec.id.rfind(prefix, 0) == 0) {
        problem.specs.push_back(spec);
        break;
      }
    }
  }
  if (problem.specs.empty()) {
    std::printf("none of the requested shapes exist at %zu rows and %zu columns\n",
                rows, columns);
    return 1;
  }
  std::printf("\ntuning on %zu shapes at %zu rows x %zu columns, u32\n",
              problem.specs.size(), rows, columns);
  for (auto const & spec : problem.specs) {
    std::printf("  %s\n", spec.id.c_str());
  }

  std::map<std::string, TslTunedConfig> tuned;

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
    for (auto const workers : worker_counts) {
      problem.workers = workers;
      std::printf("\n================ %s / %zu-bit / %zu worker%s\n",
                  tsl_style_name(unit.style), unit.width, workers,
                  workers == 1 ? "" : "s");

      auto const samplesort = unit.samplesort(problem);
      auto const sample_outcome = summarise(samplesort);
      report("samplesort", unit.style, unit.width, samplesort, sample_outcome);

      auto const quicksort = unit.quicksort(problem);
      auto const quick_outcome = summarise(quicksort);
      report("quicksort", unit.style, unit.width, quicksort, quick_outcome);

      // One row per algorithm per cell, with the workers folded into the key so a
      // serial and a parallel run can disagree about the best configuration --
      // which, given the thread count changes what a bucket costs, they may.
      if (workers == worker_counts.front()) {
        auto sample_config = sample_outcome.best.config;
        sample_config.from_file = true;
        tuned[tsl_tuned_key("samplesort", unit.style, unit.width, 4)] = sample_config;
        auto quick_config = quick_outcome.best.config;
        quick_config.from_file = true;
        tuned[tsl_tuned_key("quicksort", unit.style, unit.width, 4)] = quick_config;
      }

      for (auto const * pair : {&samplesort, &quicksort}) {
        auto const algorithm = pair == &samplesort ? "samplesort" : "quicksort";
        for (auto const & candidate : *pair) {
          auto row = results.make_row();
          row.shape = "tuning-set";
          row.shape_params = std::to_string(problem.specs.size()) + " shapes";
          row.rows = rows;
          row.columns = columns;
          row.element_bytes = 4;
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
  std::printf("\n%s\n", results.summary().c_str());
  if (!csv_path.empty()) {
    results.write_csv(csv_path);
  }
  return 0;
}
