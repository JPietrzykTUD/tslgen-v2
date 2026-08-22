// One (style, width) of the coordinate descent. CMake compiles this file once per
// pair with TSL_Q0_STYLE and TSL_Q0_WIDTH set, so the nine instantiations build in
// parallel instead of serialising into one enormous translation unit.
//
// Each unit registers itself, so `bench_q0_tune` needs no table to keep in step.

#include <cstdio>

#include "q0_tune_impl.hpp"

#if !defined(TSL_Q0_STYLE) || !defined(TSL_Q0_WIDTH)
#error "compile this with -DTSL_Q0_STYLE=<TslStyle member> -DTSL_Q0_WIDTH=<bits>"
#endif

namespace {

using Key = std::uint32_t;
constexpr TslStyle style = TslStyle::TSL_Q0_STYLE;
constexpr std::size_t width = TSL_Q0_WIDTH;
using Simd = typename tsl_simd_for<Key, style, width>::type;

// The candidate set. The cross is over the axes measured to interact -- the
// base-case leaf only pays above a fill threshold, and both depend on how many
// buckets a level produces -- while the rest vary one at a time around the
// default. See q0_tune_impl.hpp for why it is not a full grid.
auto samplesort_candidates(TslTuneProblem const & problem)
  -> std::vector<TslTuneCandidate> {
  TslDatasetSource<Key> source(12ull << 30);
  std::vector<TslTuneCandidate> out;

  auto add = [&](std::string axis, std::string label, TslTunedConfig config,
                 TslTuneScore score) {
    std::printf("    samplesort %-10s %-22s %10.2f ns/elem%s\n", axis.c_str(),
                label.c_str(), score.score,
                score.over_budget ? "  (over budget)"
                                  : (score.failures.empty() ? "" : "  WRONG"));
    std::fflush(stdout);
    out.push_back(TslTuneCandidate{std::move(axis), std::move(label), config,
                                   score.score, std::move(score.per_shape),
                                   std::move(score.failures), score.over_budget});
  };

#define TSL_Q0_POINT(AXIS, LABEL, K, B, P, BC, F, I, M)                            \
  do {                                                                             \
    TslTunedConfig config;                                                          \
    config.k = (K); config.buckets = (B); config.base_policy = (P);                 \
    config.base_case = (BC); config.fill_percent = (F); config.ids = (I);           \
    config.movement = (M);                                                          \
    add(AXIS, LABEL,                                                                \
        config,                                                                     \
        (tsl_tune_samplesort_point<Key, Simd, K, B, P, BC, F, I, M>(source, problem))); \
  } while (false)

  // --- the cross: K x base-case leaf x fill -----------------------------------
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
  TSL_Q0_POINT("cross", "K16/net/f75", 16, adaptive, net, 256, 75, byte_ids, oop);
  TSL_Q0_POINT("cross", "K16/ins",     16, adaptive, ins, 256, 50, byte_ids, oop);
  TSL_Q0_POINT("cross", "K32/net/f25", 32, adaptive, net, 256, 25, byte_ids, oop);
  TSL_Q0_POINT("cross", "K32/net/f50", 32, adaptive, net, 256, 50, byte_ids, oop);
  TSL_Q0_POINT("cross", "K32/ins",     32, adaptive, ins, 256, 50, byte_ids, oop);

  // --- one factor at a time around the default --------------------------------
  TSL_Q0_POINT("buckets", "ordered", 16, TslSampleSortBuckets::Ordered, net, 256, 50,
               byte_ids, oop);
  TSL_Q0_POINT("ids", "keywidth", 16, adaptive, net, 256, 50,
               TslSampleSortIds::KeyWidth, oop);
  TSL_Q0_POINT("movement", "inplace", 16, adaptive, net, 256, 50, byte_ids,
               TslSampleSortMovement::InPlace);
  TSL_Q0_POINT("base_case", "64", 16, adaptive, net, 64, 50, byte_ids, oop);
  TSL_Q0_POINT("base_case", "128", 16, adaptive, net, 128, 50, byte_ids, oop);

#undef TSL_Q0_POINT
  return out;
}

auto quicksort_candidates(TslTuneProblem const & problem)
  -> std::vector<TslTuneCandidate> {
  TslDatasetSource<Key> source(12ull << 30);
  std::vector<TslTuneCandidate> out;
  // The hybrid leaf's threshold is derived from the width, so it changes with the
  // unit rather than being a knob of its own.
  constexpr std::size_t hybrid = tsl_hybrid_auto_percent<Key, Simd>();

#define TSL_Q0_QS(AXIS, LABEL, PART, LEAF, FILL, DISCOVERY)                        \
  do {                                                                             \
    TslTunedConfig config;                                                          \
    config.partition = (PART); config.leaf = (LEAF);                                \
    config.hybrid_leaf = ((FILL) != 0);                                             \
    config.discovery = (DISCOVERY);                                                 \
    auto score = tsl_tune_quicksort_point<Key, Simd, PART, LEAF, FILL>(             \
      source, problem, DISCOVERY, config.partition_threshold);                       \
    std::printf("    quicksort  %-10s %-22s %10.2f ns/elem%s\n", AXIS, LABEL,        \
                score.score, score.over_budget ? "  (over budget)"                    \
                  : (score.failures.empty() ? "" : "  WRONG"));                       \
    std::fflush(stdout);                                                              \
    out.push_back(TslTuneCandidate{AXIS, LABEL, config, score.score,                 \
                                   std::move(score.per_shape),                        \
                                   std::move(score.failures), score.over_budget});     \
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
  TSL_Q0_QS("cross", "2way/net/post", two, net_leaf, 0, post);
  TSL_Q0_QS("discovery", "3way/net/incremental", three, net_leaf, 0, incremental);
  TSL_Q0_QS("discovery", "3way/hyb/incremental", three, net_leaf, hybrid, incremental);

#undef TSL_Q0_QS
  return out;
}

struct Registrar {
  Registrar() {
    tsl_tune_units().push_back(TslTuneUnit{style, width, &samplesort_candidates,
                                          &quicksort_candidates});
  }
};
Registrar const registrar;

}  // namespace
