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
template <class Key, class Simd, class Run>
auto with_quicksort_leaf(TslTunedConfig const & config, Run && run) -> bool {
  constexpr auto three = TslPartitionKind::THREE_WAY;
  if (config.partition != three) {
    return false;
  }
  if (config.hybrid_leaf) {
    run(TslMultiColumnIndexSorter<Key, three, TslLeafKind::NETWORK, Simd,
                                  tsl_hybrid_auto_percent<Key, Simd>()>(0x5A3F1E77));
  } else if (config.leaf == TslLeafKind::INSERTION) {
    run(TslMultiColumnIndexSorter<Key, three, TslLeafKind::INSERTION, Simd>(0x5A3F1E77));
  } else {
    run(TslMultiColumnIndexSorter<Key, three, TslLeafKind::NETWORK, Simd>(0x5A3F1E77));
  }
  return true;
}

template <class Key, class Simd, class Run>
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
#define TSL_TUNED_SS(BC, P)                                                            run(TslSampleSortMultiColumn<Key, Simd, 16, adaptive, 8, BC, P, byte_ids,                                       BC / lanes, 50, oop, true>{})
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

