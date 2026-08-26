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
#include <map>

#include "sorting/quicksort/multicolumn_index_sort.hpp"
#include "sorting/sample_sort/samplesort_multicolumn.hpp"
#include "tsl_simd_for.hpp"
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
  constexpr auto net = TslSampleSortBase::Network;
  constexpr auto ins = TslSampleSortBase::Insertion;
  constexpr std::size_t lanes = Simd::lane_count_v;
  // The axes the descent settled: ordered buckets were 2.4x worse, key-width ids
  // and in-place movement both lost. A configuration asking for one of those is
  // reported rather than measured, because the descent already answered it.
  if (config.buckets != adaptive || config.ids != byte_ids
      || config.movement != oop) {
    return false;
  }
  // Bucket count, base case, base-case leaf and its fill threshold are all
  // dispatched, because Q0 varies all four and any of them can win. Until this
  // existed the bucket count produced a drop and the fill threshold was worse: the
  // dispatch hard-coded 50 and ignored what the tuner chose, so a fill=75 winner
  // ran as fill=50 and the row still said "(tuned)". A silent substitution is the
  // one failure mode a reader cannot detect.
#define TSL_TUNED_SS(K, BC, P, F)                                                  \
  run(TslSampleSortMultiColumn<Key, Simd, K, adaptive, 8, BC, P, byte_ids,          \
                               BC / lanes, F, oop, Profile>{})
#define TSL_TUNED_SS_FILL(K, BC)                                                   \
  do {                                                                             \
    if (config.base_policy == ins) { TSL_TUNED_SS(K, BC, ins, 50); return true; }   \
    if (config.fill_percent == 25) { TSL_TUNED_SS(K, BC, net, 25); return true; }   \
    if (config.fill_percent == 50) { TSL_TUNED_SS(K, BC, net, 50); return true; }   \
    if (config.fill_percent == 75) { TSL_TUNED_SS(K, BC, net, 75); return true; }   \
    return false;                                                                  \
  } while (false)
#define TSL_TUNED_SS_BASE(K)                                                       \
  do {                                                                             \
    if (config.base_case == 64) { TSL_TUNED_SS_FILL(K, 64); }                       \
    if (config.base_case == 128) { TSL_TUNED_SS_FILL(K, 128); }                     \
    if (config.base_case == 256) { TSL_TUNED_SS_FILL(K, 256); }                     \
    return false;                                                                  \
  } while (false)
  if (config.k == 8) { TSL_TUNED_SS_BASE(8); }
  if (config.k == 16) { TSL_TUNED_SS_BASE(16); }
  if (config.k == 32) { TSL_TUNED_SS_BASE(32); }
  return false;
#undef TSL_TUNED_SS_BASE
#undef TSL_TUNED_SS_FILL
#undef TSL_TUNED_SS
}

// The tuned configuration for the key width about to be measured.
//
// Q0 tunes each key width separately, because a lane holds half as many 8-byte
// elements and that moves the base case, the bucket count and the leaf capacity
// together. A reader that asks for the 4-byte configuration while measuring 8-byte
// keys gets a proxy and still labels the row "(tuned)" -- which is what these
// drivers did until the tuner learned about u64.
//
// Style and register width are fixed at Intrinsics/512 deliberately, and that is a
// measured choice rather than a default: across all nine cells the best
// configuration per cell spans 1.00x to 1.02x for seven of them, inside the noise
// floor, and the only two that separate are the narrow intrinsics cells at 1.43x
// and 2.03x -- both worse. 512 is the widest available, so no narrower cell can
// beat it. The other cells' configurations are Q0's design-space *answer*, printed
// in its report, not an input any reporting driver needs.
template <class Key>
void tsl_select_tuned(std::map<std::string, TslTunedConfig> const & tuned,
                      TslTunedConfig & samplesort, TslTunedConfig & quicksort,
                      std::size_t workers = 0) {
  // The cell this binary was *built* for, not a fixed one. The drivers now take
  // their SIMD type from `tsl_measure_simd_t`, so asking Q0 for Intrinsics/512
  // regardless meant a binary built for clang_bool/512 ran that code with the
  // configuration tuned for intrinsics -- the knobs and the instantiation
  // disagreeing, with the row still labelled "(tuned)".
  // And the worker count, because the tuner answers per worker count: passing 0
  // asks for the worker-agnostic entry, which is what a caller that measures one
  // thread count wants.
  samplesort = tsl_tuned_for(tuned, "samplesort", tsl_measure_style,
                             tsl_measure_width, sizeof(Key), workers);
  quicksort = tsl_tuned_for(tuned, "quicksort", tsl_measure_style,
                            tsl_measure_width, sizeof(Key), workers);
}
