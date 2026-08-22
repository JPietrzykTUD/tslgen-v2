#pragma once

// The measurement method every `bench_qN_*` driver shares, so it exists once.
//
// A driver declares its grid and its cases; this owns everything about *how* a
// number is produced: verify before timing, median of nine with the interquartile
// range beside it, machine state recorded with the results, drops reported rather
// than skipped, and one CSV schema so a figure is a query over `results/` instead
// of a re-run.
//
// -----------------------------------------------------------------------------
// Why median and IQR rather than mean and deviation
// -----------------------------------------------------------------------------
// Two baselines taken back to back on an idle host differed by up to 21% on
// serial rows and 40% on parallel ones. The distribution is skewed by scheduler
// outliers rather than symmetric around a centre, so the mean sits above the
// typical run and its standard deviation describes the outliers instead of the
// measurement. The median is the centre that survives them and the quartiles say
// how wide the bulk is. Nine repetitions puts a real quartile at each end.
//
// See `docs/benchmark-plan.md` for which question each driver answers.

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <string>
#include <unistd.h>
#include <vector>


inline constexpr int tsl_paper_repetitions = 9;


// Recorded with the results, because a figure whose host is unknown is not
// reproducible and this host's clock moves under load.
struct TslPaperMachine {
  std::string host = "unknown";
  std::string governor = "unknown";
  std::string compiler = "unknown";
  double clock_mhz = 0.0;
  std::size_t cores = 0;
  double load = 0.0;

  static auto probe() -> TslPaperMachine {
    TslPaperMachine machine;
    char name[256] = {};
    if (::gethostname(name, sizeof(name) - 1) == 0) {
      machine.host = name;
    }
    if (std::ifstream governor("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor");
        governor) {
      std::getline(governor, machine.governor);
    }
    // The highest current frequency across cores: the clock a busy core reaches,
    // which is what a timing is relative to.
    if (std::ifstream info("/proc/cpuinfo"); info) {
      std::string line;
      while (std::getline(info, line)) {
        if (line.rfind("cpu MHz", 0) == 0) {
          auto const colon = line.find(':');
          if (colon != std::string::npos) {
            machine.clock_mhz = std::max(machine.clock_mhz,
                                         std::atof(line.c_str() + colon + 1));
          }
        } else if (line.rfind("processor", 0) == 0) {
          ++machine.cores;
        }
      }
    }
    if (std::ifstream loadavg("/proc/loadavg"); loadavg) {
      loadavg >> machine.load;
    }
#if defined(__clang__)
    machine.compiler = "clang " + std::to_string(__clang_major__) + "."
                       + std::to_string(__clang_minor__);
#elif defined(__GNUC__)
    machine.compiler = "gcc " + std::to_string(__GNUC__) + "."
                       + std::to_string(__GNUC_MINOR__);
#endif
    return machine;
  }

  void print() const {
    std::printf("host=%s cores=%zu governor=%s clock=%.0fMHz load=%.2f compiler=%s\n",
                host.c_str(), cores, governor.c_str(), clock_mhz, load,
                compiler.c_str());
    if (load > 1.0) {
      std::printf("  !! load average above 1.0: another process is competing and "
                  "these numbers are not publishable\n");
    }
  }
};


struct TslPaperStats {
  double median = 0.0;
  double p25 = 0.0;
  double p75 = 0.0;

  // Spread as a fraction of the centre, which is what decides whether two rows
  // can be told apart.
  auto relative_iqr() const -> double {
    return median > 0.0 ? (p75 - p25) / median : 0.0;
  }
};


inline auto tsl_paper_stats(std::vector<double> samples) -> TslPaperStats {
  TslPaperStats stats;
  if (samples.empty()) {
    return stats;
  }
  std::sort(samples.begin(), samples.end());
  auto const at = [&](double fraction) {
    auto const index = static_cast<std::size_t>(
      std::llround(fraction * static_cast<double>(samples.size() - 1)));
    return samples[std::min(index, samples.size() - 1)];
  };
  stats.p25 = at(0.25);
  stats.median = at(0.50);
  stats.p75 = at(0.75);
  return stats;
}


// One published measurement.
struct TslPaperRow {
  std::string question;
  std::string binary;
  std::string shape;
  std::string shape_params;
  std::size_t rows = 0;
  std::size_t columns = 0;
  std::size_t element_bytes = 0;
  std::string algorithm;
  std::string variant;
  std::string detector;
  std::size_t workers = 0;
  int repetitions = 0;
  TslPaperStats ns_per_element;
  // Phase split where the driver has one, so a result can be attributed rather
  // than only reported. Zero where it does not.
  double ns_materialize = 0.0;
  double ns_sort = 0.0;
  double ns_detect = 0.0;
  bool verified = false;
  std::string drop_reason;
};


class TslPaperResults {
  std::string question_;
  std::string binary_;
  TslPaperMachine machine_;
  std::vector<TslPaperRow> rows_;
  bool header_printed_ = false;

 public:
  TslPaperResults(std::string question, std::string binary)
      : question_(std::move(question)), binary_(std::move(binary)),
        machine_(TslPaperMachine::probe()) {
    std::printf("%s / %s\n", question_.c_str(), binary_.c_str());
    machine_.print();
  }

  auto machine() const -> TslPaperMachine const & { return machine_; }

  auto make_row() const -> TslPaperRow {
    TslPaperRow row;
    row.question = question_;
    row.binary = binary_;
    row.repetitions = tsl_paper_repetitions;
    return row;
  }

  void add(TslPaperRow row) {
    if (!header_printed_) {
      std::printf("\n%-26s %-12s %5s %8s %-24s %-14s %7s %10s %8s\n", "shape",
                  "params", "cols", "rows", "algorithm", "detector", "workers",
                  "ns/elem", "iqr");
      header_printed_ = true;
    }
    if (!row.drop_reason.empty()) {
      std::printf("%-26s %-12s %5zu %8zu %-24s %-14s %7zu   dropped: %s\n",
                  row.shape.c_str(), row.shape_params.c_str(), row.columns, row.rows,
                  row.algorithm.c_str(), row.detector.c_str(), row.workers,
                  row.drop_reason.c_str());
    } else if (!row.verified) {
      std::printf("%-26s %-12s %5zu %8zu %-24s %-14s %7zu   INCORRECT\n",
                  row.shape.c_str(), row.shape_params.c_str(), row.columns, row.rows,
                  row.algorithm.c_str(), row.detector.c_str(), row.workers);
    } else {
      std::printf("%-26s %-12s %5zu %8zu %-24s %-14s %7zu %10.2f %7.1f%%\n",
                  row.shape.c_str(), row.shape_params.c_str(), row.columns, row.rows,
                  row.algorithm.c_str(), row.detector.c_str(), row.workers,
                  row.ns_per_element.median,
                  100.0 * row.ns_per_element.relative_iqr());
    }
    rows_.push_back(std::move(row));
  }

  // A configuration the grid asked for and could not run. Emitted rather than
  // skipped: a silently narrowed sweep reads as full coverage.
  void drop(TslPaperRow row, std::string reason) {
    row.drop_reason = std::move(reason);
    add(std::move(row));
  }

  void write_csv(std::string const & path) const {
    std::ofstream csv(path);
    if (!csv) {
      std::printf("could not write %s\n", path.c_str());
      return;
    }
    csv << "question,binary,shape,shape_params,rows,columns,element_bytes,"
           "algorithm,variant,detector,workers,repetitions,"
           "ns_per_element_median,ns_per_element_p25,ns_per_element_p75,"
           "ns_materialize,ns_sort,ns_detect,verified,drop_reason,"
           "host,governor,clock_mhz,compiler\n";
    for (auto const & row : rows_) {
      csv << row.question << ',' << row.binary << ',' << row.shape << ','
          << row.shape_params << ',' << row.rows << ',' << row.columns << ','
          << row.element_bytes << ',' << row.algorithm << ',' << row.variant << ','
          << row.detector << ',' << row.workers << ',' << row.repetitions << ','
          << row.ns_per_element.median << ',' << row.ns_per_element.p25 << ','
          << row.ns_per_element.p75 << ',' << row.ns_materialize << ','
          << row.ns_sort << ',' << row.ns_detect << ','
          << (row.verified ? 1 : 0) << ',' << row.drop_reason << ','
          << machine_.host << ',' << machine_.governor << ','
          << machine_.clock_mhz << ',' << machine_.compiler << '\n';
    }
    std::printf("\nwrote %s (%zu rows)\n", path.c_str(), rows_.size());
  }

  auto summary() const -> std::string {
    std::size_t dropped = 0;
    std::size_t wrong = 0;
    for (auto const & row : rows_) {
      if (!row.drop_reason.empty()) {
        ++dropped;
      } else if (!row.verified) {
        ++wrong;
      }
    }
    return std::to_string(rows_.size() - dropped - wrong) + " measured, "
           + std::to_string(dropped) + " dropped, " + std::to_string(wrong)
           + " incorrect";
  }
};


// Verifies once, then times `repetitions` times. `verify` returns true when the
// result is right; a false makes the row `INCORRECT` and produces no number, so a
// wrong configuration can never contribute a figure.
template <class Body, class Verify>
auto tsl_paper_measure(Body && body, Verify && verify, std::size_t elements,
                       double abandon_after_seconds = 0.0,
                       bool * abandoned = nullptr)
  -> std::pair<bool, TslPaperStats> {
  // The first pass is the verification pass, and timing it costs nothing extra.
  // A configuration whose single pass already exceeds the budget cannot become
  // competitive over nine of them, so it is abandoned rather than measured --
  // which is a different finding from sorting wrongly, hence the out-parameter.
  auto const first = std::chrono::steady_clock::now();
  body();
  auto const first_seconds =
    std::chrono::duration<double>(std::chrono::steady_clock::now() - first).count();
  if (!verify()) {
    return {false, TslPaperStats{}};
  }
  if (abandon_after_seconds > 0.0 && first_seconds > abandon_after_seconds) {
    if (abandoned != nullptr) {
      *abandoned = true;
    }
    return {false, TslPaperStats{}};
  }
  std::vector<double> samples;
  samples.reserve(tsl_paper_repetitions);
  for (int rep = 0; rep < tsl_paper_repetitions; ++rep) {
    auto const start = std::chrono::steady_clock::now();
    body();
    auto const stop = std::chrono::steady_clock::now();
    samples.push_back(std::chrono::duration<double, std::nano>(stop - start).count()
                      / static_cast<double>(elements == 0 ? 1 : elements));
  }
  return {true, tsl_paper_stats(std::move(samples))};
}
