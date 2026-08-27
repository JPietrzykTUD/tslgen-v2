#pragma once

#include <sched.h>
#include <string>
#include <thread>
#include <unistd.h>

// How many CPUs this process may actually run on.
//
// `std::thread::hardware_concurrency()` is the wrong number under a pin. On
// libstdc++ it is `sysconf(_SC_NPROCESSORS_ONLN)` -- what the machine has, not what
// the caller is allowed -- so a process confined to six CPUs by
// `numactl --physcpubind=0-5` still reports twenty-four. A benchmark that sizes its
// thread pool from it then runs four threads per core and measures contention:
// the corpus stage did exactly that, and its parallel variants carry `workers=24`
// in their names while six CPUs were available.
//
// The affinity mask is the honest answer, and it is what `numactl`, `taskset`,
// cgroups and a container CPU limit all set.
inline auto tsl_usable_cpu_count() -> std::size_t {
  cpu_set_t allowed;
  CPU_ZERO(&allowed);
  if (sched_getaffinity(0, sizeof(allowed), &allowed) == 0) {
    auto const count = CPU_COUNT(&allowed);
    if (count > 0) {
      return static_cast<std::size_t>(count);
    }
  }
  auto const reported = std::thread::hardware_concurrency();
  return reported == 0 ? 1 : static_cast<std::size_t>(reported);
}


// The affinity mask itself, as a compact list -- "0-5,12-17".
//
// The count alone is not enough, and that gap has cost real time: a results
// directory recording `pinned_cpus 6` cannot say *which* six, so it cannot say
// whether those six were six physical cores or three cores and their SMT
// siblings. The difference makes every parallel figure either right or worthless,
// and it is not recoverable afterwards from a count.
inline auto tsl_usable_cpu_list() -> std::string {
  cpu_set_t allowed;
  CPU_ZERO(&allowed);
  if (sched_getaffinity(0, sizeof(allowed), &allowed) != 0) {
    return "";
  }
  std::string out;
  int run_start = -1;
  auto flush = [&](int end) {
    if (run_start < 0) {
      return;
    }
    if (!out.empty()) {
      out += ',';
    }
    out += std::to_string(run_start);
    if (end > run_start) {
      out += '-' + std::to_string(end);
    }
    run_start = -1;
  };
  int previous = -2;
  for (int cpu = 0; cpu < CPU_SETSIZE; ++cpu) {
    if (CPU_ISSET(cpu, &allowed)) {
      if (cpu != previous + 1) {
        flush(previous);
        run_start = cpu;
      }
      previous = cpu;
    }
  }
  flush(previous);
  return out;
}
