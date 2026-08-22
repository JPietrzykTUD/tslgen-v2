#pragma once

#include "tsl_simd_for.hpp"
#include "common/instrumentation.hpp"

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

// Nine is the floor, not the answer. Measured across 335 rows collected on this
// machine, the relative inter-quartile range is 1.81% at the median and 5.80% at
// the ninetieth percentile -- but 3.6% of rows exceed 10% and the worst reached
// 40.8%, all of them parallel. For those, nine samples put a quartile inside the
// noise and the median is not a number worth publishing.
//
// So a measurement that comes out wide is repeated: batches of four more until the
// relative IQR falls under the target or the ceiling is reached. The row records
// how many it actually took, so a reader can see which measurements were hard.
//
// This is not what Google Benchmark would fix. Its contribution is auto-tuning the
// *iteration count* so a sub-millisecond kernel is timed above the clock's
// resolution -- our sorts run tens to hundreds of milliseconds, where one
// iteration per repetition is already right and gbench would choose the same. Its
// aggregates are mean and standard deviation over repetitions, which is what we do
// with the median and quartiles, and the quartiles are the more robust pair for a
// distribution skewed by an occasional slow run. What neither addresses is the
// dominant term: the same binary re-run in a fresh process varies by 21-40% here
// against 1-5% within one process. That is machine state, and no harness fixes it.
inline constexpr int tsl_paper_max_repetitions = 33;
inline constexpr double tsl_paper_target_spread = 0.05;


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
    // Whether this binary can collect anything while it measures. Printed rather
    // than assumed: the counters cost enough on the parallel index-sort path to
    // move a comparison, and a run has no other way to say which build produced
    // it. `run_paper.sh` reads this line.
    if constexpr (tsl_cosort_instrumentation) {
      std::printf("  !! instrumentation is compiled in: counter collection is "
                  "active and these numbers carry its cost. Configure with "
                  "--preset bench (TSL_COSORT_NO_INSTRUMENTATION=ON) to publish.\n");
    } else {
      std::printf("instrumentation=off (counters compiled out)\n");
    }
    // Which (style, register width) cell this binary was built for. A results
    // directory holds one build's numbers, so recording it once per run is enough
    // -- but recording it nowhere would leave a figure unable to say what produced
    // it, and the cell is chosen per host by `run_all.sh`.
    std::printf("measure-cell=%s/%zu-bit\n", tsl_style_name(tsl_measure_style),
                tsl_measure_width);
    // `TSL_PROFILE=auto` probes the compiler and falls back to the scalar profile
    // when the probe fails, and nothing downstream complains: the intrinsics style
    // still compiles, the drivers still run, and every number is a TSL scalar
    // fallback. It happened here -- a build directory reconfigured while a build
    // was in flight came out scalar, and the only symptom was an unrelated compile
    // error in a header assuming `tsl::avx512` exists. Checked at runtime rather
    // than in CMake because this is where the define is definitionally visible.
#if defined(TSL_PROFILE_SCALAR)
    std::printf("  !! TSL profile is SCALAR: every number here is a scalar "
                "fallback, whatever the style column says. Delete the build "
                "directory and configure it again; the usual cause is "
                "reconfiguring while a build is running.\n");
#endif
  }
};


struct TslPaperStats {
  double median = 0.0;
  double p25 = 0.0;
  double p75 = 0.0;
  // How many samples this actually took. Adaptive, so it varies per row, and a
  // reader can see which measurements needed persuading.
  int repetitions = 0;

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
  stats.repetitions = static_cast<int>(samples.size());
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
  std::size_t unsettled_ = 0;   // rows still wide after the repetition ceiling
  bool header_printed_ = false;
  // Progress. A full run is six to eight hours across six drivers, and without
  // this the only sign of life is a table that grows in bursts -- a shape that
  // takes twenty minutes looks identical to one that has hung. Written to stderr
  // so the tables on stdout stay clean enough to read afterwards.
  std::chrono::steady_clock::time_point started_ = std::chrono::steady_clock::now();
  std::size_t expected_ = 0;    // 0 when the driver cannot cheaply say
  std::string stage_;           // the outer loop's current position

 public:
  TslPaperResults(std::string question, std::string binary)
      : question_(std::move(question)), binary_(std::move(binary)),
        machine_(TslPaperMachine::probe()) {
    std::printf("%s / %s\n", question_.c_str(), binary_.c_str());
    machine_.print();
  }

  // How many rows this run intends to produce, when the driver knows. It only
  // feeds the estimate, so being approximate is better than staying silent: a
  // wrong total still tells you whether you are a tenth or nine tenths through.
  void expect(std::size_t rows) { expected_ = rows; }

  // Where the outer loop is, for runs whose rows are not self-describing.
  void stage(std::string where) { stage_ = std::move(where); }

  static auto duration_text(double seconds) -> std::string {
    if (seconds < 0.0) {
      seconds = 0.0;
    }
    auto const total = static_cast<long long>(seconds);
    char text[32];
    if (total >= 3600) {
      std::snprintf(text, sizeof text, "%lldh%02lldm", total / 3600,
                    (total % 3600) / 60);
    } else if (total >= 60) {
      std::snprintf(text, sizeof text, "%lldm%02llds", total / 60, total % 60);
    } else {
      std::snprintf(text, sizeof text, "%llds", total);
    }
    return text;
  }

  void report_progress() const {
    auto const elapsed = std::chrono::duration<double>(
      std::chrono::steady_clock::now() - started_).count();
    auto const done = rows_.size();
    if (expected_ == 0) {
      std::fprintf(stderr, "\r[%s] %zu rows, %s elapsed%s%s   ",
                   binary_.c_str(), done, duration_text(elapsed).c_str(),
                   stage_.empty() ? "" : " | ", stage_.c_str());
    } else {
      auto const fraction = static_cast<double>(done)
                          / static_cast<double>(expected_ < done ? done : expected_);
      auto const remaining = fraction > 0.0 ? elapsed / fraction - elapsed : 0.0;
      std::fprintf(stderr, "\r[%s] %zu/%zu (%.0f%%) %s elapsed, ~%s left%s%s   ",
                   binary_.c_str(), done, expected_, fraction * 100.0,
                   duration_text(elapsed).c_str(), duration_text(remaining).c_str(),
                   stage_.empty() ? "" : " | ", stage_.c_str());
    }
    std::fflush(stderr);
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
    // A carriage-returned progress line and a table on stdout would overwrite each
    // other, so the line is cleared before the row is printed and redrawn after.
    std::fprintf(stderr, "\r%78s\r", "");
    std::fflush(stderr);
    // The measurement knows how many samples it took; the row should not have to
    // be told separately, because a driver that forgot would report nine.
    if (row.ns_per_element.repetitions > 0) {
      row.repetitions = row.ns_per_element.repetitions;
    }
    // A row that stayed wide after the ceiling is a measurement the machine would
    // not settle, not a number. Said out loud here as well as recorded, because a
    // console reader should not have to open the CSV to notice.
    if (row.repetitions >= tsl_paper_max_repetitions
        && row.ns_per_element.relative_iqr() > tsl_paper_target_spread) {
      ++unsettled_;
    }
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
    report_progress();
  }

  // A configuration the grid asked for and could not run. Emitted rather than
  // skipped: a silently narrowed sweep reads as full coverage.
  void drop(TslPaperRow row, std::string reason) {
    row.drop_reason = std::move(reason);
    add(std::move(row));
  }

  // RFC 4180 quoting. Not pedantry: a variant like "execution::par, library-chosen
  // threads" and a drop reason like "x86-simd-sort, 8-byte indices" both contain a
  // comma, and an unquoted comma shifts every later column of that row -- so a
  // reader silently sees the detector where the worker count should be. This was
  // corrupting rows rather than failing loudly.
  static auto csv_field(std::string const & text) -> std::string {
    if (text.find_first_of(",\"\n\r") == std::string::npos) {
      return text;
    }
    std::string quoted = "\"";
    for (auto const character : text) {
      if (character == '"') {
        quoted += '"';  // a literal quote is doubled
      }
      quoted += character;
    }
    quoted += '"';
    return quoted;
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
      csv << csv_field(row.question) << ',' << csv_field(row.binary) << ','
          << csv_field(row.shape) << ',' << csv_field(row.shape_params) << ','
          << row.rows << ',' << row.columns << ',' << row.element_bytes << ','
          << csv_field(row.algorithm) << ',' << csv_field(row.variant) << ','
          << csv_field(row.detector) << ',' << row.workers << ','
          << row.repetitions << ','
          << row.ns_per_element.median << ',' << row.ns_per_element.p25 << ','
          << row.ns_per_element.p75 << ',' << row.ns_materialize << ','
          << row.ns_sort << ',' << row.ns_detect << ','
          << (row.verified ? 1 : 0) << ',' << csv_field(row.drop_reason) << ','
          << csv_field(machine_.host) << ',' << csv_field(machine_.governor) << ','
          << machine_.clock_mhz << ',' << csv_field(machine_.compiler) << '\n';
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
    auto text = std::to_string(rows_.size() - dropped - wrong) + " measured, "
                + std::to_string(dropped) + " dropped, " + std::to_string(wrong)
                + " incorrect";
    if (unsettled_ > 0) {
      text += "\n  !! " + std::to_string(unsettled_)
              + " row(s) still spread wider than "
              + std::to_string(static_cast<int>(tsl_paper_target_spread * 100))
              + "% after " + std::to_string(tsl_paper_max_repetitions)
              + " repetitions: the machine would not settle on those, and their"
              " medians should not be compared at fine margins";
    }
    return text;
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
  samples.reserve(tsl_paper_max_repetitions);
  for (int rep = 0; rep < tsl_paper_repetitions; ++rep) {
    auto const start = std::chrono::steady_clock::now();
    body();
    auto const stop = std::chrono::steady_clock::now();
    samples.push_back(std::chrono::duration<double, std::nano>(stop - start).count()
                      / static_cast<double>(elements == 0 ? 1 : elements));
  }
  // Widen the sample until the bulk is tight or the ceiling stops us.
  auto stats = tsl_paper_stats(samples);
  while (static_cast<int>(samples.size()) < tsl_paper_max_repetitions
         && stats.median > 0.0
         && (stats.p75 - stats.p25) / stats.median > tsl_paper_target_spread) {
    for (int extra = 0; extra < 4; ++extra) {
      auto const start = std::chrono::steady_clock::now();
      body();
      auto const stop = std::chrono::steady_clock::now();
      samples.push_back(std::chrono::duration<double, std::nano>(stop - start).count()
                        / static_cast<double>(elements == 0 ? 1 : elements));
    }
    stats = tsl_paper_stats(samples);
  }
  return {true, stats};
}
