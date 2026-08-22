#pragma once

// Instantiating the configuration bench_q0_tune chose.
//
// Every knob of both sorters is a template parameter, so "use the tuned
// configuration" means selecting an instantiation at runtime. Only the axes the
// descent found decisive are dispatched; a configuration asking for anything else
// returns false so the caller can report a drop rather than silently measure
// something the file did not ask for.
//
// Shared rather than copied because hard-coding a knob in a driver is how this
// suite came to report the quicksort with a network leaf on keys where the
// insertion leaf is up to 6.6x faster -- a mis-configuration that reads as a
// result. One dispatch means one place for that to be right.

#include <cstddef>

#include "sorting/quicksort/multicolumn_index_sort.hpp"
#include "sorting/sample_sort/samplesort_multicolumn.hpp"
#include "tuned_config.hpp"

// Only the axes the descent found decisive are dispatched here; a configuration
// asking for anything else is reported rather than silently replaced.
// `Profile` instantiates the sorter with its phase timers on. Off by default, and
// that default is not a preference: the index sorter's timers sit on the per-task
// path, and a shape that produces a million task-tree nodes -- tpcds_q064 produces
// 986,867 over 2.65M rows -- pays two `steady_clock::now()` calls per phase per
// task. Measured on that key, the profiled build is 1.24x slower at one worker and
// 1.79x at two, so leaving it on would have put up to 79% of instrumentation into
// every published quicksort number, weighted differently at each thread count --
// which is worse than having no phase split at all, because it looks like data.
// Ask for it explicitly when attributing time, not when reporting it.
template <class Key, class Simd, bool Profile = false, class Run>
auto with_quicksort_leaf(TslTunedConfig const & config, Run && run) -> bool {
  constexpr auto three = TslPartitionKind::THREE_WAY;
  if (config.partition != three) {
    return false;
  }
  if (config.hybrid_leaf) {
    run(TslMultiColumnIndexSorter<Key, three, TslLeafKind::NETWORK, Simd,
                                  tsl_hybrid_auto_percent<Key, Simd>(), Profile>(
      0x5A3F1E77));
  } else if (config.leaf == TslLeafKind::INSERTION) {
    run(TslMultiColumnIndexSorter<Key, three, TslLeafKind::INSERTION, Simd, 0,
                                  Profile>(0x5A3F1E77));
  } else {
    run(TslMultiColumnIndexSorter<Key, three, TslLeafKind::NETWORK, Simd, 0,
                                  Profile>(0x5A3F1E77));
  }
  return true;
}

// Same default, same reason. The samplesort's timers sit per range in its column
// loop rather than per task, which is cheaper -- but tpcds_q064 produces 986,867
// ranges either way, and the measured overhead is 1.08x at one worker and 1.28x at
// two. Small enough to look harmless in a table and large enough to move a
// conclusion, which is the worst size for a systematic error.
template <class Key, class Simd, bool Profile = false, class Run>
auto with_samplesort(TslTunedConfig const & config, Run && run) -> bool {
  constexpr auto adaptive = TslSampleSortBuckets::Adaptive;
  constexpr auto byte_ids = TslSampleSortIds::Byte;
  constexpr auto oop = TslSampleSortMovement::OutOfPlace;
  constexpr std::size_t lanes = Simd::lane_count_v;
  if (config.k != 16 || config.buckets != adaptive || config.ids != byte_ids
      || config.movement != oop) {
    return false;
  }
  auto const net = config.base_policy == TslSampleSortBase::Network;
#define TSL_TUNED_SS(BC, P)                                                            run(TslSampleSortMultiColumn<Key, Simd, 16, adaptive, 8, BC, P, byte_ids,                                       BC / lanes, 50, oop, Profile>{})
  if (config.base_case == 64) {
    if (net) { TSL_TUNED_SS(64, TslSampleSortBase::Network); }
    else { TSL_TUNED_SS(64, TslSampleSortBase::Insertion); }
  } else if (config.base_case == 128) {
    if (net) { TSL_TUNED_SS(128, TslSampleSortBase::Network); }
    else { TSL_TUNED_SS(128, TslSampleSortBase::Insertion); }
  } else if (config.base_case == 256) {
    if (net) { TSL_TUNED_SS(256, TslSampleSortBase::Network); }
    else { TSL_TUNED_SS(256, TslSampleSortBase::Insertion); }
  } else {
    return false;
  }
#undef TSL_TUNED_SS
  return true;
}

