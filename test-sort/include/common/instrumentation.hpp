#pragma once

#include <atomic>

// One switch for everything a measured run must not pay for.
//
// The sorters collect two kinds of bookkeeping. Phase *timers* are a template
// parameter (`Profile`), because reading a clock per range changes the shape of
// the thing being timed and a caller has to opt in deliberately. Element and range
// *counters* are cheaper and are requested by passing a metrics pointer -- but
// "cheaper" is not "free": on the parallel index-sort path they are twenty atomic
// increments per task, and a shape producing ~10^6 task-tree nodes pays 17% for
// them at twenty-four workers.
//
// Rather than gate twenty sites, the entry points funnel the caller's pointer
// through `tsl_metrics_or_null`. With instrumentation compiled out that returns a
// null pointer whose value the optimizer knows, so every `metrics != nullptr`
// branch behind it folds away and the increments disappear from the object code.
//
// Define TSL_COSORT_NO_INSTRUMENTATION=1 to compile it out. This is deliberately a
// build-level switch rather than a runtime flag: a published measurement should
// not depend on a driver remembering to pass nullptr, and a build made for
// measuring should be incapable of collecting. The `bench` CMake preset sets it.
// Tests and diagnostic tools are built without it and keep their counters.

#if defined(TSL_COSORT_NO_INSTRUMENTATION) && TSL_COSORT_NO_INSTRUMENTATION
inline constexpr bool tsl_cosort_instrumentation = false;
#else
inline constexpr bool tsl_cosort_instrumentation = true;
#endif

// The caller's metrics pointer, or a statically-known null when instrumentation is
// compiled out.
template <class Metrics>
constexpr auto tsl_metrics_or_null(Metrics * metrics) -> Metrics * {
  if constexpr (tsl_cosort_instrumentation) {
    return metrics;
  } else {
    return nullptr;
  }
}

// Counter updates that vanish when instrumentation is compiled out.
//
// Gating at the entry point is not enough on the parallel path: the shared
// counters are reached through a pointer handed to a task body, and across that
// call boundary the compiler can no longer prove the pointer is null, so the
// atomics survive. Checking `tsl_cosort_instrumentation` at the increment itself
// is what actually removes them.
template <class T, class By>
constexpr void tsl_count_add(std::atomic<T> & counter, By by) {
  if constexpr (tsl_cosort_instrumentation) {
    counter.fetch_add(static_cast<T>(by), std::memory_order_relaxed);
  }
}

template <class T, class By>
constexpr void tsl_count_add(T & counter, By by) {
  if constexpr (tsl_cosort_instrumentation) {
    counter += static_cast<T>(by);
  }
}
