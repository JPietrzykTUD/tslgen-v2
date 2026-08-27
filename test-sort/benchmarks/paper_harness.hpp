#pragma once

#include "tsl_simd_for.hpp"
#include "common/cpu_affinity.hpp"
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
#include <sched.h>
#include <sys/resource.h>
#include <set>
#include <filesystem>
#include <system_error>
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
  std::size_t cores = 0;            // logical CPUs the machine has
  // Which CPUs this process may run on, not just how many. See
  // `tsl_usable_cpu_list`: a count cannot distinguish six physical cores from
  // three cores and their SMT siblings, and that distinction decides whether a
  // parallel figure means anything.
  std::string cpu_list;
  std::size_t allowed_cpus = 0;     // logical CPUs this process may run on
  std::size_t physical_per_node = 0;// physical cores in one NUMA node
  std::size_t numa_nodes = 0;
  bool pinned = false;              // affinity is one node's physical cores
  std::size_t llc_bytes = 0;        // largest cache level, for sizing datasets
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
    // What this process may actually run on, which is the number that matters:
    // a worker count above it oversubscribes whatever `numactl` allowed.
    machine.allowed_cpus = tsl_usable_cpu_count();
    machine.cpu_list = tsl_usable_cpu_list();
    // Physical cores per NUMA node, from sysfs: one entry per logical cpu, and
    // `thread_siblings_list` names the SMT group so each physical core is counted
    // once. Nodes come from the `node*` directories.
    {
      std::set<std::string> node_zero_cores;
      for (std::size_t cpu = 0; cpu < machine.cores; ++cpu) {
        auto const base = "/sys/devices/system/cpu/cpu" + std::to_string(cpu);
        std::ifstream node_list(base + "/topology/physical_package_id");
        std::ifstream siblings(base + "/topology/thread_siblings_list");
        std::ifstream core_id(base + "/topology/core_id");
        std::string siblings_text;
        std::string core_text;
        if (siblings) {
          std::getline(siblings, siblings_text);
        }
        if (core_id) {
          std::getline(core_id, core_text);
        }
        // Which NUMA node owns this cpu.
        std::size_t which_node = 0;
        bool found_node = false;
        for (std::size_t node = 0; node < 16 && !found_node; ++node) {
          std::error_code ignored;
          if (std::filesystem::exists(
                base + "/node" + std::to_string(node), ignored)) {
            which_node = node;
            found_node = true;
          }
        }
        if (found_node) {
          machine.numa_nodes = std::max(machine.numa_nodes, which_node + 1);
          if (which_node == 0) {
            // What identifies the *physical* core this logical cpu belongs to.
            // `thread_siblings_list` names the whole SMT group and is the best
            // answer, but it is not guaranteed readable -- and when it came back
            // empty this counted nothing at all, leaving `physical_per_node` at
            // zero, which `parallel_width()` reads as one core. The result was a
            // suite that measured only its serial configurations on a machine with
            // plenty of them, with no diagnostic anywhere. `core_id` was already
            // being read for this and never used; the cpu index is the last resort,
            // which over-counts SMT siblings but is never zero.
            std::string key = siblings_text;
            if (key.empty() && !core_text.empty()) {
              std::string package;
              if (std::ifstream package_file(base + "/topology/physical_package_id");
                  package_file) {
                std::getline(package_file, package);
              }
              key = package + ":" + core_text;
            }
            if (key.empty()) {
              key = "cpu" + std::to_string(cpu);
            }
            node_zero_cores.insert(key);
          }
        }
      }
      machine.physical_per_node = node_zero_cores.size();
    }
    // Largest cache level. A tuning run whose working set fits in it is tuning
    // for a regime no reported figure measures: the knobs that trade passes
    // against concurrent output streams only start paying once the streams miss.
    for (std::size_t index = 0; index < 8; ++index) {
      auto const dir = "/sys/devices/system/cpu/cpu0/cache/index"
                       + std::to_string(index);
      std::ifstream size_file(dir + "/size");
      if (!size_file) {
        continue;
      }
      std::string text;
      std::getline(size_file, text);
      if (text.empty()) {
        continue;
      }
      auto const unit = text.back();
      auto const value = std::strtoull(text.c_str(), nullptr, 10);
      std::size_t bytes = value;
      if (unit == 'K' || unit == 'k') {
        bytes = value * 1024;
      } else if (unit == 'M' || unit == 'm') {
        bytes = value * 1024 * 1024;
      }
      machine.llc_bytes = std::max(machine.llc_bytes, bytes);
    }
    machine.pinned = machine.physical_per_node > 0
                     && machine.allowed_cpus > 0
                     && machine.allowed_cpus <= machine.physical_per_node;
#if defined(__clang__)
    machine.compiler = "clang " + std::to_string(__clang_major__) + "."
                       + std::to_string(__clang_minor__);
#elif defined(__GNUC__)
    machine.compiler = "gcc " + std::to_string(__GNUC__) + "."
                       + std::to_string(__GNUC_MINOR__);
#endif
    return machine;
  }

  // The largest worker count a measurement may ask for: one thread per physical core
  // of one NUMA node, and never more than the affinity mask allows. The two limits
  // answer different questions -- `physical_per_node` comes from sysfs and describes
  // the machine, `allowed_cpus` describes this process -- and a run pinned to fewer
  // CPUs than a node has would oversubscribe them if only the first were consulted.
  auto parallel_width() const -> std::size_t {
    // No topology at all -- an unreadable sysfs, a kernel that does not expose
    // `node0`, a container that hides it -- must not mean "serial". Everything
    // parallel in this suite is derived from this number, so a probe that fails
    // silently turns a twelve-core host into a one-worker run and reports nothing.
    // Falling back to what the process is allowed to use over-counts SMT siblings,
    // which is a worse *pinning* than one thread per physical core and a far better
    // answer than measuring no parallelism at all.
    auto width = physical_per_node > 0 ? physical_per_node
                 : (allowed_cpus > 0 ? allowed_cpus : cores);
    if (allowed_cpus > 0) {
      width = std::min(width, allowed_cpus);
    }
    return std::max<std::size_t>(std::size_t{1}, width);
  }

  void print() const {
    std::printf("host=%s cores=%zu governor=%s clock=%.0fMHz load=%.2f compiler=%s\n",
                host.c_str(), cores, governor.c_str(), clock_mhz, load,
                compiler.c_str());
    // Topology, because "24 cores" on this class of machine is twelve physical
    // cores with SMT siblings spread over two NUMA nodes, and a memory-bound
    // co-sort run across all of them measures cache thrashing and cross-node
    // latency rather than the sort. The honest full-machine number is one thread
    // per physical core within one node.
    std::printf("topology: %zu NUMA node(s), %zu physical core(s) per node, "
                "%zu logical cpu(s) available to this process%s, LLC %zu MiB\n",
                numa_nodes, physical_per_node, allowed_cpus,
                pinned ? " [pinned]" : "", llc_bytes / (1024 * 1024));
    // The mask, spelled out. "six cpus" is not the same claim as "cpus 0-5", and
    // only the second one can be checked against the machine's topology after the
    // fact.
    std::printf("cpus available: %s\n",
                cpu_list.empty() ? "unknown" : cpu_list.c_str());
    // The number every parallel figure is derived from, said out loud. A run whose
    // thread axis silently collapsed to one worker looks exactly like a run of a
    // machine that has one core, and the difference is six hours of measuring the
    // serial configurations twice.
    std::printf("parallel width: %zu (thread axis: 1..%zu)\n",
                parallel_width(), parallel_width());
    if (parallel_width() == 1 && allowed_cpus > 1) {
      std::printf("  !! the thread axis collapsed to one worker although %zu cpus "
                  "are available. physical_per_node came out %zu, so the sysfs "
                  "topology probe found nothing usable under "
                  "/sys/devices/system/cpu/cpu*/topology. Every parallel row will "
                  "be a repeat of the serial one.\n",
                  allowed_cpus, physical_per_node);
    }
    if (!pinned && physical_per_node > 0 && allowed_cpus > physical_per_node) {
      std::printf("  !! not pinned: this process may use SMT siblings and both "
                  "NUMA nodes. Run under `numactl --cpunodebind=0 --membind=0` "
                  "with at most %zu workers, or the parallel numbers include "
                  "contention that has nothing to do with the sort.\n",
                  physical_per_node);
    }
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


// How many times the kernel took a CPU away from this process, across every
// thread of it.
//
// The load average in `TslPaperMachine` is read once, when a run starts, so it
// screens the machine and nothing more: a run that starts on a quiet host and is
// joined at minute forty by something else looks clean in every column. That is
// the case this counts. `ru_nivcsw` rises when the scheduler preempts a thread --
// exactly what happens when another runnable process wants a core this run is
// using -- so a delta of zero across a timed pass means the pass had the cores to
// itself, and a nonzero delta names the pass that did not.
//
// Voluntary switches are deliberately not counted: a worker blocking on a
// condition variable is this sort's own behaviour, not interference.
inline auto tsl_involuntary_switches() -> long {
  rusage usage{};
  if (getrusage(RUSAGE_SELF, &usage) != 0) {
    return 0;
  }
  return usage.ru_nivcsw;
}


struct TslPaperStats {
  double median = 0.0;
  double p25 = 0.0;
  double p75 = 0.0;
  // How many samples this actually took. Adaptive, so it varies per row, and a
  // reader can see which measurements needed persuading.
  int repetitions = 0;
  // Of those samples, how many were taken while the kernel was also running
  // something else on these cores, and how many times it switched.
  //
  // A minority is what the median is for: a preempted pass is a slow pass, the
  // quartiles show it, and resampling widens until the bulk is tight again. A
  // majority is different -- then the median itself is a contended number, and no
  // amount of resampling recovers the quiet one. `contaminated()` is that line.
  int preempted_passes = 0;
  long involuntary_switches = 0;

  // Spread as a fraction of the centre, which is what decides whether two rows
  // can be told apart.
  auto relative_iqr() const -> double {
    return median > 0.0 ? (p75 - p25) / median : 0.0;
  }

  // Involuntary switches per timed pass. The rate is the honest statistic; the
  // count of passes that saw *any* is not, because on a real machine every pass
  // sees a few -- the timer tick, a kworker, an IRQ -- and those are unavoidable
  // rather than interference.
  auto switches_per_pass() const -> double {
    return repetitions > 0
      ? static_cast<double>(involuntary_switches) / repetitions : 0.0;
  }

  // True when the kernel took the CPU away often enough to move the median.
  //
  // The threshold was "any involuntary switch in more than half the passes",
  // which is a detector with its threshold at zero: measured across a full suite
  // on an exclusively-partitioned host, the median row saw 2 to 12 switches per
  // pass and 1600 of 2270 rows tripped the flag, while only about ten had a rate
  // high enough to matter. A flag that fires on almost everything is worse than
  // no flag, because it trains a reader to skip the line that would have caught
  // the real case.
  //
  // A switch costs a few microseconds. A pass is a good fraction of a second, so
  // a hundred of them is well under a tenth of a percent and beneath anything
  // this harness can resolve; a thousand starts to be visible against a 1-5%
  // spread. The line is drawn where the cost approaches the resolution.
  static constexpr double disturbed_switches_per_pass = 100.0;

  auto contaminated() const -> bool {
    return switches_per_pass() > disturbed_switches_per_pass;
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
  // The cache tier a row count was derived from -- L2, LLC, 2xLLC. The corpus
  // sizes its cases that way and the row count alone does not say it, so the
  // schema carries it: it was the one field the corpus's CSVs had and the
  // reporting drivers' did not, which is the whole of the "one schema" claim's
  // exception. Empty where a driver sizes by rows directly.
  std::string size_level;
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
  bool quiet_ = false;
  mutable std::chrono::steady_clock::time_point last_progress_{};
  std::size_t unsettled_ = 0;   // rows still wide after the repetition ceiling
  std::size_t contended_ = 0;   // rows whose median was measured under preemption
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

  // A live progress line is for a terminal. Redirected to a file the carriage
  // returns erase nothing, so every update is appended and the log fills with
  // hundred-line rows of overwritten progress spliced through the middle of the
  // tables -- which is exactly what a `> bench_sorting.log 2>&1` run produced. When
  // stderr is not a terminal the line is emitted once per interval as an ordinary
  // line instead, rare enough to read and frequent enough to see progress.
  static auto stderr_is_terminal() -> bool {
    static bool const answer = isatty(fileno(stderr)) != 0;
    return answer;
  }

  void report_progress() const {
    auto const now = std::chrono::steady_clock::now();
    auto const elapsed = std::chrono::duration<double>(now - started_).count();
    auto const done = rows_.size();
    // A terminal can take an update per row, because each one overwrites the last.
    // A file cannot, so it gets one line every half minute: often enough to watch a
    // seven-hour run, rare enough that the log is still mostly results.
    if (!stderr_is_terminal()) {
      auto const since = std::chrono::duration<double>(now - last_progress_).count();
      if (since < 30.0 && done != expected_) {
        return;
      }
      last_progress_ = now;
    }
    if (expected_ == 0) {
      std::fprintf(stderr, "%s[%s] %zu rows, %s elapsed%s%s   %s",
                   stderr_is_terminal() ? "\r" : "", binary_.c_str(), done,
                   duration_text(elapsed).c_str(),
                   stage_.empty() ? "" : " | ", stage_.c_str(),
                   stderr_is_terminal() ? "" : "\n");
    } else {
      auto const fraction = static_cast<double>(done)
                          / static_cast<double>(expected_ < done ? done : expected_);
      auto const remaining = fraction > 0.0 ? elapsed / fraction - elapsed : 0.0;
      std::fprintf(stderr, "%s[%s] %zu/%zu (%.0f%%) %s elapsed, ~%s left%s%s   %s",
                   stderr_is_terminal() ? "\r" : "", binary_.c_str(), done,
                   expected_, fraction * 100.0,
                   duration_text(elapsed).c_str(), duration_text(remaining).c_str(),
                   stage_.empty() ? "" : " | ", stage_.c_str(),
                   stderr_is_terminal() ? "" : "\n");
    }
    std::fflush(stderr);
  }

  auto machine() const -> TslPaperMachine const & { return machine_; }

  // Stop echoing every row. A driver whose readable output is its own tables --
  // Q0 prints one per cell, with every candidate, its label and its ratio -- gains
  // nothing from also dumping the same numbers as rows whose only distinguishing
  // column is `detector=scalar`, which reads as though the sort were scalar. The
  // CSV is written either way.
  void set_quiet(bool quiet) { quiet_ = quiet; }

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
    if (stderr_is_terminal()) {
      std::fprintf(stderr, "\r%78s\r", "");
    }
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
    // And a row whose *majority* of passes were preempted, which the start-of-run
    // load average cannot see because the interference arrived later.
    if (row.ns_per_element.contaminated()) {
      ++contended_;
    }
    if (quiet_) {
      rows_.push_back(std::move(row));
      return;
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
           "algorithm,variant,detector,workers,size_level,repetitions,"
           "ns_per_element_median,ns_per_element_p25,ns_per_element_p75,"
           "preempted_passes,involuntary_switches,"
           "ns_materialize,ns_sort,ns_detect,verified,drop_reason,"
           "host,governor,clock_mhz,compiler,start_load,pinned_cpus,cpu_list\n";
    for (auto const & row : rows_) {
      csv << csv_field(row.question) << ',' << csv_field(row.binary) << ','
          << csv_field(row.shape) << ',' << csv_field(row.shape_params) << ','
          << row.rows << ',' << row.columns << ',' << row.element_bytes << ','
          << csv_field(row.algorithm) << ',' << csv_field(row.variant) << ','
          << csv_field(row.detector) << ',' << row.workers << ','
          << csv_field(row.size_level) << ',' << row.repetitions << ','
          << row.ns_per_element.median << ',' << row.ns_per_element.p25 << ','
          << row.ns_per_element.p75 << ','
          << row.ns_per_element.preempted_passes << ','
          << row.ns_per_element.involuntary_switches << ','
          << row.ns_materialize << ','
          << row.ns_sort << ',' << row.ns_detect << ','
          << (row.verified ? 1 : 0) << ',' << csv_field(row.drop_reason) << ','
          << csv_field(machine_.host) << ',' << csv_field(machine_.governor) << ','
          << machine_.clock_mhz << ',' << csv_field(machine_.compiler) << ','
          // The load average when the run started, and how many CPUs it was
          // allowed. Printed as a warning already, but a warning scrolls past and a
          // column does not: a run that shared its cores with something else is
          // otherwise indistinguishable afterwards from a clean one. This is not
          // hypothetical -- a stray pinned job took one of six cores from the first
          // minutes of a real run, and nothing in the results would have said so.
          << machine_.load << ',' << machine_.allowed_cpus << ','
          << csv_field(machine_.cpu_list) << '\n';
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
    if (contended_ > 0) {
      text += "\n  !! " + std::to_string(contended_)
              + " row(s) lost the cpu to the kernel more than "
              + std::to_string(static_cast<int>(
                  TslPaperStats::disturbed_switches_per_pass))
              + " times per timed pass: something else was competing for these"
              " cores. A handful of switches per pass is the timer tick and is"
              " normal; this is not. Check involuntary_switches before publishing"
              " those rows";
    }
    return text;
  }
};


// Verifies once, then times `repetitions` times. `verify` returns true when the
// result is right; a false makes the row `INCORRECT` and produces no number, so a
// wrong configuration can never contribute a figure.
// Same, for a body that consumes what it sorts.
//
// Every reporting driver so far sorts an index and leaves the columns alone, so
// one body could be run nine times over. An in-place sort cannot: it has to be
// handed its data back between passes, and a copy of the table charged to the sort
// would report a memcpy. `prepare` runs before every pass, outside the timing --
// which is what `state.PauseTiming()` was doing for the corpus under Google
// Benchmark, and the reason the corpus could not use this harness before.
template <class Prepare, class Body, class Verify>
auto tsl_paper_measure_reset(Prepare && prepare, Body && body, Verify && verify,
                             std::size_t elements,
                             double abandon_after_seconds = 0.0,
                             bool * abandoned = nullptr)
  -> std::pair<bool, TslPaperStats>;

template <class Body, class Verify>
auto tsl_paper_measure(Body && body, Verify && verify, std::size_t elements,
                       double abandon_after_seconds = 0.0,
                       bool * abandoned = nullptr)
  -> std::pair<bool, TslPaperStats> {
  return tsl_paper_measure_reset([] {}, std::forward<Body>(body),
                                 std::forward<Verify>(verify), elements,
                                 abandon_after_seconds, abandoned);
}

template <class Prepare, class Body, class Verify>
auto tsl_paper_measure_reset(Prepare && prepare, Body && body, Verify && verify,
                             std::size_t elements,
                             double abandon_after_seconds,
                             bool * abandoned)
  -> std::pair<bool, TslPaperStats> {
  // The first pass is the verification pass, and timing it costs nothing extra.
  // A configuration whose single pass already exceeds the budget cannot become
  // competitive over nine of them, so it is abandoned rather than measured --
  // which is a different finding from sorting wrongly, hence the out-parameter.
  prepare();
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
  int preempted = 0;
  long switches = 0;
  // One timed pass: reset, time, and note whether the kernel interrupted it.
  auto timed_pass = [&] {
    prepare();
    auto const before = tsl_involuntary_switches();
    auto const start = std::chrono::steady_clock::now();
    body();
    auto const stop = std::chrono::steady_clock::now();
    auto const taken = tsl_involuntary_switches() - before;
    if (taken > 0) {
      ++preempted;
      switches += taken;
    }
    samples.push_back(std::chrono::duration<double, std::nano>(stop - start).count()
                      / static_cast<double>(elements == 0 ? 1 : elements));
  };
  for (int rep = 0; rep < tsl_paper_repetitions; ++rep) {
    timed_pass();
  }
  // Widen the sample until the bulk is tight or the ceiling stops us.
  auto stats = tsl_paper_stats(samples);
  while (static_cast<int>(samples.size()) < tsl_paper_max_repetitions
         && stats.median > 0.0
         && (stats.p75 - stats.p25) / stats.median > tsl_paper_target_spread) {
    for (int extra = 0; extra < 4; ++extra) {
      timed_pass();
    }
    stats = tsl_paper_stats(samples);
  }
  stats.preempted_passes = preempted;
  stats.involuntary_switches = switches;
  return {true, stats};
}

// Paired, interleaved comparison.
//
// `tsl_paper_measure` runs one body to completion, which is right for reporting a
// cost but wrong for comparing two costs that differ by less than the machine's
// drift. Measuring all of A and then all of B charges whatever drifted between the
// two blocks to the A-B difference, and on this machine that drift is 1.0% at the
// median and 3.5% at the worst -- enough to reverse a comparison of two sorter
// configurations sitting 0.2% apart, which is how the tuner came to name a
// different winner on two runs of the same binary.
//
// Interleaving A,B,C,A,B,C,... and reducing the *per-round ratios* removes drift
// slow relative to one round, which is what machine drift is. What comes back is a
// ratio against the first entrant with a quartile band: when the band excludes
// 1.0, the difference is real. Two things that could not be measured any other way
// came out of this -- that TSL's packed-boolean-mask style beats hand-written
// intrinsics by 2-5% while its lane-mask style costs up to 46%, and that a knob's
// response curve is *not* a function of lane count alone.
//
// Each entrant must be idempotent and must leave the input unchanged, exactly as
// for `tsl_paper_measure`; correctness is the caller's to check once before
// comparing.
struct TslPaperRatio {
  double median = 0.0;   // per-round ratio against entrant 0
  double p25 = 0.0;
  double p75 = 0.0;
  double median_ms = 0.0;
  auto distinguishable() const -> bool { return p25 > 1.0 || p75 < 1.0; }
};

template <class Body>
auto tsl_paper_compare(std::vector<Body> & entrants, int rounds)
  -> std::vector<TslPaperRatio> {
  std::vector<std::vector<double>> times(entrants.size());
  for (int round = 0; round < rounds; ++round) {
    for (std::size_t at = 0; at < entrants.size(); ++at) {
      auto const start = std::chrono::steady_clock::now();
      entrants[at]();
      times[at].push_back(std::chrono::duration<double, std::milli>(
        std::chrono::steady_clock::now() - start).count());
    }
  }
  auto quantile = [](std::vector<double> values, double fraction) {
    std::sort(values.begin(), values.end());
    auto const index = static_cast<std::size_t>(
      std::llround(fraction * static_cast<double>(values.size() - 1)));
    return values[std::min(index, values.size() - 1)];
  };
  std::vector<TslPaperRatio> out;
  for (std::size_t at = 0; at < entrants.size(); ++at) {
    std::vector<double> ratios;
    for (int round = 0; round < rounds; ++round) {
      if (times[0][round] > 0.0) {
        ratios.push_back(times[at][round] / times[0][round]);
      }
    }
    TslPaperRatio ratio;
    if (!ratios.empty()) {
      ratio.median = quantile(ratios, 0.50);
      ratio.p25 = quantile(ratios, 0.25);
      ratio.p75 = quantile(ratios, 0.75);
    }
    ratio.median_ms = quantile(times[at], 0.50);
    out.push_back(ratio);
  }
  return out;
}

// --- machine-derived defaults ---------------------------------------------------
// A literal row count or worker count is a statement about one machine. These turn
// the intent -- "enough data to miss the last level", "one thread per physical core
// of one node" -- into a number wherever the suite runs.

// The smallest power of two whose live footprint reaches `target_bytes`. Keys, the
// index and the out-of-place scratch are all resident at once, so the footprint per
// row is `(columns + 2) * element_bytes`.
inline auto tsl_rows_for_bytes(std::size_t target_bytes, std::size_t columns,
                               std::size_t element_bytes) -> std::size_t {
  auto const per_row = (columns + 2) * element_bytes;
  auto const wanted = per_row == 0 ? 0 : target_bytes / per_row;
  std::size_t rows = 1;
  while (rows < wanted) {
    rows *= 2;   // the generator's catalog is offered at powers of two
  }
  return rows;
}

// Comfortably outside the last level: the regime every reported figure lives in.
inline auto tsl_rows_out_of_cache(TslPaperMachine const & machine,
                                  std::size_t columns, std::size_t element_bytes)
  -> std::size_t {
  auto const llc = machine.llc_bytes > 0 ? machine.llc_bytes
                                         : 32ull * 1024 * 1024;
  return tsl_rows_for_bytes(4 * llc, columns, element_bytes);
}

// Inside it, for a driver that deliberately sweeps both regimes. Half the LLC, so
// the working set still fits once the index and scratch are counted.
inline auto tsl_rows_in_cache(TslPaperMachine const & machine, std::size_t columns,
                              std::size_t element_bytes) -> std::size_t {
  auto const llc = machine.llc_bytes > 0 ? machine.llc_bytes
                                         : 32ull * 1024 * 1024;
  return tsl_rows_for_bytes(llc / 2, columns, element_bytes);
}

// Serial, and one thread per physical core of one NUMA node. Never the logical
// count: SMT siblings share an L1 and a memory-bound co-sort spends the second
// thread evicting the first one's lines.
inline auto tsl_default_workers(TslPaperMachine const & machine)
  -> std::vector<std::size_t> {
  auto const many = machine.parallel_width();
  if (many <= 1) {
    return {1};
  }
  return {1, many};
}
