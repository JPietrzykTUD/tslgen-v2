#pragma once

#include <sched.h>
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
