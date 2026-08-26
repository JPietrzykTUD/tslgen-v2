// One (style, register width) of the coordinate descent, at both key widths. CMake
// compiles this file once per pair with TSL_Q0_STYLE and TSL_Q0_WIDTH set, so the
// nine instantiations build in parallel instead of serialising into one enormous
// translation unit.
//
// Both 4-byte and 8-byte keys are tuned, separately. A configuration found on
// 32-bit keys is not a tuned configuration for 64-bit keys: the lane holds half as
// many elements, which moves the base case, the bucket count and the leaf capacity
// together. Reusing the narrow answer for the wide key and still labelling the row
// "(tuned)" is the sort of quiet substitution this file exists to prevent.
//
// Each unit registers itself, so `bench_q0_tune` needs no table to keep in step.

#include <cstdio>

#include "cosort_case.hpp"
#include "q0_tune_impl.hpp"

#if !defined(TSL_Q0_STYLE) || !defined(TSL_Q0_WIDTH)
#error "compile this with -DTSL_Q0_STYLE=<TslStyle member> -DTSL_Q0_WIDTH=<bits>"
#endif

namespace {

constexpr TslStyle style = TslStyle::TSL_Q0_STYLE;
constexpr std::size_t width = TSL_Q0_WIDTH;

// The candidate set. The cross is over the axes measured to interact -- the
// base-case leaf only pays above a fill threshold, and both depend on how many
// buckets a level produces -- while the rest vary one at a time around the
// default. See q0_tune_impl.hpp for why it is not a full grid.
template <class Key>
auto samplesort_candidates(TslTuneProblem const & problem)
  -> std::vector<TslTuneCandidate> {
  using Simd = typename tsl_simd_for<Key, style, width>::type;
  TslDatasetSource<Key> source(12ull << 30);
  std::vector<TslTuneEntrant<Key>> entrants;

  // Each point contributes a *callable*, not a measurement: they are all measured
  // together afterwards, one pass each per round, so drift cannot land on one
  // candidate rather than another. The sorter is captured by value in a shared_ptr
  // because every candidate's buffers stay live for the whole interleaved run.
#define TSL_Q0_POINT(AXIS, LABEL, K, B, P, BC, F, I, M)                            \
  do {                                                                             \
    TslTunedConfig config;                                                          \
    config.k = (K); config.buckets = (B); config.base_policy = (P);                 \
    config.base_case = (BC); config.fill_percent = (F); config.ids = (I);           \
    config.movement = (M);                                                          \
    using Sorter = TslSampleSortMultiColumn<Key, Simd, K, B, 8, BC, P, I,            \
                                            BC / Simd::lane_count_v, F, M, false>;   \
    auto sorter = std::make_shared<Sorter>();                                        \
    entrants.push_back(TslTuneEntrant<Key>{                                          \
      AXIS, LABEL, config, false,                                                    \
      [sorter](TslSortColumn<Key> * columns, std::size_t column_count,               \
               Key * index, std::size_t rows, std::size_t workers) {                 \
        TslIndexScalarDetector<Key> detector;                                        \
        if (workers > 1) {                                                           \
          sorter->sort_index_parallel(columns, column_count, index, rows, detector,   \
                                      workers);                                      \
        } else {                                                                     \
          sorter->sort_index(columns, column_count, index, rows, detector);           \
        }                                                                            \
      }});                                                                           \
  } while (false)

  constexpr auto adaptive = TslSampleSortBuckets::Adaptive;
  constexpr auto byte_ids = TslSampleSortIds::Byte;
  constexpr auto oop = TslSampleSortMovement::OutOfPlace;
  constexpr auto net = TslSampleSortBase::Network;
  constexpr auto ins = TslSampleSortBase::Insertion;

  TSL_Q0_POINT("cross", "K8/net/f25",   8, adaptive, net, 256, 25, byte_ids, oop);
  TSL_Q0_POINT("cross", "K8/net/f50",   8, adaptive, net, 256, 50, byte_ids, oop);
  TSL_Q0_POINT("cross", "K8/ins",       8, adaptive, ins, 256, 50, byte_ids, oop);
  TSL_Q0_POINT("cross", "K16/net/f25", 16, adaptive, net, 256, 25, byte_ids, oop);
  TSL_Q0_POINT("cross", "K16/net/f50", 16, adaptive, net, 256, 50, byte_ids, oop);
  entrants.back().is_default = true;   // the documented default samplesort
  TSL_Q0_POINT("cross", "K16/net/f75", 16, adaptive, net, 256, 75, byte_ids, oop);
  TSL_Q0_POINT("cross", "K16/ins",     16, adaptive, ins, 256, 50, byte_ids, oop);
  TSL_Q0_POINT("cross", "K32/net/f25", 32, adaptive, net, 256, 25, byte_ids, oop);
  TSL_Q0_POINT("cross", "K32/net/f50", 32, adaptive, net, 256, 50, byte_ids, oop);
  TSL_Q0_POINT("cross", "K32/ins",     32, adaptive, ins, 256, 50, byte_ids, oop);
  TSL_Q0_POINT("buckets", "ordered", 16, TslSampleSortBuckets::Ordered, net, 256, 50,
               byte_ids, oop);
  TSL_Q0_POINT("ids", "keywidth", 16, adaptive, net, 256, 50,
               TslSampleSortIds::KeyWidth, oop);
  TSL_Q0_POINT("movement", "inplace", 16, adaptive, net, 256, 50, byte_ids,
               TslSampleSortMovement::InPlace);
  TSL_Q0_POINT("base_case", "64", 16, adaptive, net, 64, 50, byte_ids, oop);
  TSL_Q0_POINT("base_case", "128", 16, adaptive, net, 128, 50, byte_ids, oop);

#undef TSL_Q0_POINT
  return tsl_tune_detail::measure_interleaved<Key>(source, problem, entrants);
}

template <class Key>
auto quicksort_candidates(TslTuneProblem const & problem)
  -> std::vector<TslTuneCandidate> {
  using Simd = typename tsl_simd_for<Key, style, width>::type;
  TslDatasetSource<Key> source(12ull << 30);
  std::vector<TslTuneEntrant<Key>> entrants;
  std::vector<TslTuneCandidate> skipped;
  // The hybrid leaf's threshold is derived from the width, so it changes with the
  // unit rather than being a knob of its own.
  constexpr std::size_t hybrid = tsl_hybrid_auto_percent<Key, Simd>();
  // Whether the quadratic two-way candidate is measurable on this problem or a
  // trap. A candidate is scored across every shape, so one duplicate-heavy shape
  // disqualifies it for the whole problem -- but only a duplicate-heavy one.
  //
  // This used to be a working-set size test, `working_set > two_way_size_cap`, and
  // that was the wrong property. Two-way is quadratic in the equal-run *length*,
  // not in the table size, and where runs are short it is the faster scheme: 0.93x
  // to 0.97x of three-way across the attribute stage, with the margin growing at
  // the larger working set rather than shrinking. The size test therefore did not
  // buy safety, it forfeited that win -- and unconditionally, because every shape
  // this tuner runs on is larger than the cap, so two-way was skipped in every cell
  // of every run and `partition=3way` was shipped by default rather than by
  // measurement. The run-length rule is the corpus registrar's, shared so the two
  // cannot disagree about which shapes are safe.
  bool two_way_measurable = true;
  std::string two_way_blocker;
  for (auto const & spec : problem.specs) {
    if (!tsl_two_way_run_bounded(spec)) {
      two_way_measurable = false;
      two_way_blocker = tsl_dataset_label(spec);
      break;
    }
  }

#define TSL_Q0_QS(AXIS, LABEL, PART, LEAF, FILL, DISCOVERY)                        \
  do {                                                                             \
    TslTunedConfig config;                                                          \
    config.partition = (PART); config.leaf = (LEAF);                                \
    config.hybrid_leaf = ((FILL) != 0);                                             \
    config.discovery = (DISCOVERY);                                                 \
    if ((PART) == TslPartitionKind::TWO_WAY && !two_way_measurable) {                 \
      TslTuneCandidate gated;                                                        \
      gated.axis = AXIS;                                                             \
      gated.label = LABEL;                                                           \
      gated.skipped = "two-way is quadratic in the equal-run length, and "           \
                      + two_way_blocker + " has runs longer than the cap";           \
      skipped.push_back(std::move(gated));                                           \
      break;                                                                         \
    }                                                                                \
    using Sorter = TslMultiColumnIndexSorter<Key, PART, LEAF, Simd, FILL>;           \
    auto sorter = std::make_shared<Sorter>(0x5A3F1E77);                              \
    auto const discovery = (DISCOVERY);                                              \
    auto const threshold = config.partition_threshold;                               \
    entrants.push_back(TslTuneEntrant<Key>{                                          \
      AXIS, LABEL, config, false,                                                    \
      [sorter, discovery, threshold](                                                \
        TslSortColumn<Key> * columns, std::size_t column_count, Key * index,          \
        std::size_t rows, std::size_t workers) {                                      \
        TslIndexScalarDetector<Key> detector;                                        \
        if (workers > 1) {                                                           \
          sorter->sort_index_parallel(columns, column_count, index, rows, discovery,  \
                                      detector, workers, threshold);                 \
        } else {                                                                     \
          sorter->sort_index(columns, column_count, index, rows, discovery, detector);\
        }                                                                            \
      }});                                                                           \
  } while (false)

  constexpr auto three = TslPartitionKind::THREE_WAY;
  constexpr auto two = TslPartitionKind::TWO_WAY;
  constexpr auto net_leaf = TslLeafKind::NETWORK;
  constexpr auto ins_leaf = TslLeafKind::INSERTION;
  constexpr auto post = TslRunDiscoveryKind::POST_SORT;
  constexpr auto incremental = TslRunDiscoveryKind::INCREMENTAL;

  TSL_Q0_QS("cross", "3way/net/post", three, net_leaf, 0, post);
  TSL_Q0_QS("cross", "3way/ins/post", three, ins_leaf, 0, post);
  TSL_Q0_QS("cross", "3way/hyb/post", three, net_leaf, hybrid, post);
  entrants.back().is_default = true;   // the documented default quicksort
  TSL_Q0_QS("cross", "2way/net/post", two, net_leaf, 0, post);
  TSL_Q0_QS("discovery", "3way/net/incremental", three, net_leaf, 0, incremental);
  TSL_Q0_QS("discovery", "3way/hyb/incremental", three, net_leaf, hybrid, incremental);

#undef TSL_Q0_QS
  auto measured = tsl_tune_detail::measure_interleaved<Key>(source, problem, entrants);
  for (auto & gated : skipped) {
    measured.push_back(std::move(gated));
  }
  return measured;
}

struct Registrar {
  Registrar() {
    tsl_tune_units().push_back(
      TslTuneUnit{style, width, 4, &samplesort_candidates<std::uint32_t>,
                  &quicksort_candidates<std::uint32_t>});
    tsl_tune_units().push_back(
      TslTuneUnit{style, width, 8, &samplesort_candidates<std::uint64_t>,
                  &quicksort_candidates<std::uint64_t>});
  }
};
Registrar const registrar;

}  // namespace
