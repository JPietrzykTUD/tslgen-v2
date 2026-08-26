#pragma once

// What drives one registered corpus case: Google Benchmark, or the paper harness.
//
// The corpus and the paper drivers measured the same sorts two different ways, and
// the difference was not cosmetic. Google Benchmark gives a mean and a standard
// deviation over a fixed repetition count; `paper_harness.hpp` gives the median of
// at least nine with quartiles, resampled while the spread stays above 5%, after a
// verification pass against the reference image, with the machine state and the
// drop reasons on every row. Q5 and Q6 therefore could not carry the method the
// other five questions are held to, and their rows reached the schema through a
// JSON round trip that had to invent the fields it could not recover -- including
// `verified`, which it hardcoded to 1.
//
// The fix is not a second copy of the sort bodies. A case body says *what* to
// measure by calling `measure(prepare, body)` on whichever runner it was handed;
// the runner decides how. One body, two backends, and the bodies no longer name
// Google Benchmark at all.

#include "paper_harness.hpp"

#include <cstddef>
#include <string>
#include <utility>

#ifdef TSL_COSORT_WITH_GBENCH
#include <benchmark/benchmark.h>
#endif


// The two compiler barriers the bodies need, without depending on a benchmark
// library for them. `DoNotOptimize` keeps a value the sort produced observable;
// `ClobberMemory` stops stores being sunk past the end of a timed pass.
template <class T>
inline void tsl_do_not_optimize(T const & value) {
  asm volatile("" : : "r,m"(value) : "memory");
}

inline void tsl_clobber_memory() { asm volatile("" : : : "memory"); }


// Accepts what the corpus publishes per case and keeps none of it.
//
// The paper schema carries the fields that identify a case -- rows, columns, key
// width, lanes through `variant` -- and has nowhere for a free-form counter, so
// these are discarded rather than smuggled into a string. Assignable, so a body
// writes `counters["x"] = v` whichever runner it was handed.
class TslDiscardedCounters {
 public:
  auto operator[](char const *) -> double & { return sink_; }
  auto operator[](std::string const &) -> double & { return sink_; }

 private:
  double sink_ = 0.0;
};


// Runs a case through `paper_harness.hpp` and reports what it found.
class TslPaperRunner {
 public:
  explicit TslPaperRunner(std::size_t elements) : elements_(elements) {}

  // `prepare` restores whatever the body consumes and is never timed; `verify`
  // decides whether the case produced the right answer at all.
  template <class Prepare, class Body, class Verify>
  void measure(Prepare && prepare, Body && body, Verify && verify) {
    auto const measured = tsl_paper_measure_reset(
      std::forward<Prepare>(prepare), std::forward<Body>(body),
      std::forward<Verify>(verify), elements_);
    verified_ = measured.first;
    stats_ = measured.second;
    measured_ = true;
  }

  // A case the corpus refuses: an unavailable backend, a shape a variant cannot
  // express. A drop with a reason, which is what the other five questions do.
  void fail(std::string reason) {
    dropped_ = true;
    reason_ = std::move(reason);
  }

  TslDiscardedCounters counters;

  // One pass is one sort here, so a counter the corpus normalises by the
  // iteration count is already per-sort.
  auto iterations() const -> std::size_t { return 1; }

  auto measured() const -> bool { return measured_; }
  auto verified() const -> bool { return verified_; }
  auto dropped() const -> bool { return dropped_; }
  auto reason() const -> std::string const & { return reason_; }
  auto stats() const -> TslPaperStats const & { return stats_; }

 private:
  std::size_t elements_;
  TslPaperStats stats_{};
  std::string reason_;
  bool measured_ = false;
  bool verified_ = false;
  bool dropped_ = false;
};


#ifdef TSL_COSORT_WITH_GBENCH
// The original path, kept so the two can be compared on one machine before the
// old one is removed: a statistic that changes when the harness under it changes
// is worth seeing side by side once.
class TslGbenchRunner {
 public:
  explicit TslGbenchRunner(benchmark::State & state)
      : counters(state.counters), state_(state) {}

  // The library's own map, so the counters keep reaching its report.
  benchmark::UserCounters & counters;

  template <class Prepare, class Body, class Verify>
  void measure(Prepare && prepare, Body && body, Verify && verify) {
    for (auto _ : state_) {
      state_.PauseTiming();
      prepare();
      state_.ResumeTiming();
      body();
    }
    if (!verify()) {
      state_.SkipWithError("verification failed");
    }
  }

  void fail(std::string reason) { state_.SkipWithError(reason.c_str()); }

  auto iterations() const -> std::size_t {
    return static_cast<std::size_t>(state_.iterations() < 1 ? 1
                                                            : state_.iterations());
  }

  auto state() -> benchmark::State & { return state_; }

 private:
  benchmark::State & state_;
};
#endif
