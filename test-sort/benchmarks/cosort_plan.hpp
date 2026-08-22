#pragma once

// The variant space and the staged measurement plan of benchmark.md.
//
// A *variant* is one compiled sorter configuration: execution mode, discovery
// strategy, partition kind, leaf kind, implementation style and register width.
// An *axis* is a condition it is measured under: dataset shape, column count,
// working-set size, direction, worker count, thresholds.
//
// A stage names one question and pins every axis its question does not need. The
// full product is unrunnable and mostly redundant, so `COSORT_STAGE` selects a
// question instead:
//
//   screen        which variants are viable at all
//   tune          what worker count and thresholds make the survivors fastest
//   characterize  the finalists across the real data matrix
//   attribute     what the native SIMD primitives buy, intrinsics versus builtins
//
// Every axis remains overridable by environment variable, so a stage is a set of
// defaults rather than a cage. Whatever a stage drops is counted and reported;
// a silently narrowed run would read as full coverage.

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

#include "cosort_detectors.hpp"
#include "sorting/quicksort/multicolumn_quicksort.hpp"

enum class TslExecution { Serial, Parallel, DeepParallel };
// Two clang implementation families, distinguished by mask representation:
// `clang_v*` masks are lane-wide compare results, `clang_v*_bool` masks are
// packed boolean vectors that lower to a k-register like the intrinsic families.
// Both use the same builtins for everything else, so the pair isolates the cost
// of the mask representation alone.
enum class TslStyle { Intrinsics, ClangBuiltin, ClangBoolMask };
enum class TslStage { Screen, Tune, Characterize, Attribute };

// How rows are moved. `Direct` permutes the key column and every payload column
// in place. `Index` permutes only a row-index array and materializes the active
// column through it per level (multicolumn_index_sort.hpp), so the columns stay
// read-only and the moved bytes stop scaling with the column count.
enum class TslMovement { Direct, Index };

inline auto tsl_movement_name(TslMovement movement) -> char const * {
  return movement == TslMovement::Index ? "index" : "direct";
}

inline auto tsl_movement_from_name(std::string const & name) -> TslMovement {
  return name == "index" ? TslMovement::Index : TslMovement::Direct;
}

inline auto tsl_execution_prefix(TslExecution execution) -> char const * {
  switch (execution) {
    case TslExecution::Serial: return "";
    case TslExecution::Parallel: return "parallel_";
    case TslExecution::DeepParallel: return "deep_parallel_";
  }
  return "";
}

inline auto tsl_style_name(TslStyle style) -> char const * {
  switch (style) {
    case TslStyle::Intrinsics: return "intr";
    case TslStyle::ClangBuiltin: return "clang";
    case TslStyle::ClangBoolMask: return "clang_bool";
  }
  return "intr";
}

inline auto tsl_style_from_name(std::string const & name) -> TslStyle {
  if (name == "clang") return TslStyle::ClangBuiltin;
  if (name == "clang_bool") return TslStyle::ClangBoolMask;
  return TslStyle::Intrinsics;
}

inline auto tsl_stage_name(TslStage stage) -> char const * {
  switch (stage) {
    case TslStage::Screen: return "screen";
    case TslStage::Tune: return "tune";
    case TslStage::Characterize: return "characterize";
    case TslStage::Attribute: return "attribute";
  }
  return "unknown";
}

inline auto tsl_stage_from_name(std::string const & name) -> TslStage {
  if (name == "screen") return TslStage::Screen;
  if (name == "tune") return TslStage::Tune;
  if (name == "characterize") return TslStage::Characterize;
  if (name == "attribute") return TslStage::Attribute;
  throw std::invalid_argument("unknown COSORT_STAGE: " + name);
}

// One compiled sorter configuration. Style and width are part of the identity
// because they are template parameters of the sorter, not conditions it runs
// under; `lanes` is derived from width and element size.
struct TslVariant {
  TslExecution execution = TslExecution::Serial;
  TslRunDiscoveryKind discovery = TslRunDiscoveryKind::POST_SORT;
  TslPartitionKind partition = TslPartitionKind::THREE_WAY;
  TslLeafKind leaf = TslLeafKind::INSERTION;
  TslStyle style = TslStyle::Intrinsics;
  std::size_t width_bits = 512;
  TslMovement movement = TslMovement::Direct;
  // The third value of the `leaf` axis: the network leaf, but a leaf too sparse
  // to be worth its fixed cost goes to insertion instead, and one too sparse for
  // the network yet longer than insertion's threshold keeps partitioning. Only
  // meaningful with `leaf == NETWORK`, which is how it is enumerated. The
  // percentage itself depends on type and lane count, so it is a template
  // argument at registration and published as `hybrid_fill_percent`.
  bool hybrid_leaf = false;

  auto algorithm_name() const -> std::string {
    std::string name = tsl_execution_prefix(execution);
    name += discovery == TslRunDiscoveryKind::POST_SORT ? "post_" : "incremental_";
    name += partition == TslPartitionKind::TWO_WAY ? "2way_" : "3way_";
    name += hybrid_leaf ? "hyb" : (leaf == TslLeafKind::INSERTION ? "ins" : "net");
    return name;
  }

  // Numeric ID published as the `algo` counter. The values match the enum of the
  // previous benchmark so that old JSON stays comparable, which is why they are
  // written out rather than computed: the old enum interleaved two-way and
  // three-way. Everything that enum did not have is appended -- the two two-way
  // deep-parallel variants as 17 and 18, the six incremental two-way variants as
  // 19 to 24 -- because inserting would renumber existing IDs.
  // The indirect sorter reuses the algorithmic IDs offset by 100, so a `move=`
  // pair stays recognizable as the same algorithm and no existing ID moves.
  auto algorithm_id() const -> int {
    return base_algorithm_id() + (movement == TslMovement::Index ? 100 : 0);
  }

 private:
  auto base_algorithm_id() const -> int {
    auto const post = discovery == TslRunDiscoveryKind::POST_SORT;
    auto const two = partition == TslPartitionKind::TWO_WAY;
    auto const ins = leaf == TslLeafKind::INSERTION;
    // The hybrid leaf is appended as 25 to 36 for the same reason as everything
    // else above: inserting it next to its network sibling would renumber IDs
    // that published JSON already uses.
    if (hybrid_leaf) {
      switch (execution) {
        case TslExecution::Serial:       return post ? (two ? 25 : 26) : (two ? 27 : 28);
        case TslExecution::Parallel:     return post ? (two ? 29 : 30) : (two ? 31 : 32);
        case TslExecution::DeepParallel: return post ? (two ? 33 : 34) : (two ? 35 : 36);
      }
      return -1;
    }
    switch (execution) {
      case TslExecution::Serial:
        if (post) return two ? (ins ? 1 : 3) : (ins ? 2 : 4);
        return two ? (ins ? 19 : 20) : (ins ? 5 : 6);
      case TslExecution::Parallel:
        if (post) return two ? (ins ? 7 : 9) : (ins ? 8 : 10);
        return two ? (ins ? 21 : 22) : (ins ? 11 : 12);
      case TslExecution::DeepParallel:
        if (post) return two ? (ins ? 17 : 18) : (ins ? 13 : 14);
        return two ? (ins ? 23 : 24) : (ins ? 15 : 16);
    }
    return -1;
  }
};

// Every cell of the product is implemented. Incremental discovery needs each
// completed fragment to report self-contained equal runs; three-way gets that for
// free because its equal band closes every boundary it creates, and two-way gets it
// by carrying the start of the run that overlaps a fragment's open left edge, so a
// fragment reports from there and the runs found in it are maximal.
inline auto tsl_variant_is_implementable(TslVariant const & variant) -> bool {
  // The indirect driver runs a task tree and already splits column 0's partitions
  // across workers, so `parallel_` exists. `deep_parallel_` does not: its split is
  // a nested executor rather than tasks in the same tree, and applying it to the
  // deeper single-range levels measured slower than leaving them serial.
  if (variant.movement == TslMovement::Index) {
    return variant.execution != TslExecution::DeepParallel;
  }
  return true;
}

// Every implementable variant, in a stable order.
inline auto tsl_all_variants(std::vector<TslStyle> const & styles,
                            std::vector<std::size_t> const & widths,
                            std::vector<TslMovement> const & movements)
  -> std::vector<TslVariant> {
  std::vector<TslVariant> variants;
  for (auto movement : movements) {
   for (auto style : styles) {
    for (auto width : widths) {
      for (auto execution : {TslExecution::Serial, TslExecution::Parallel,
                             TslExecution::DeepParallel}) {
        for (auto discovery : {TslRunDiscoveryKind::POST_SORT,
                               TslRunDiscoveryKind::INCREMENTAL}) {
          for (auto partition : {TslPartitionKind::TWO_WAY, TslPartitionKind::THREE_WAY}) {
            // The leaf axis: insertion, network, and the network with sparse
            // leaves diverted. The third is a variation of the network leaf, so
            // it is enumerated as one rather than as a fourth enum value.
            struct leaf_choice { TslLeafKind kind; bool hybrid; };
            for (auto choice : {leaf_choice{TslLeafKind::INSERTION, false},
                                leaf_choice{TslLeafKind::NETWORK, false},
                                leaf_choice{TslLeafKind::NETWORK, true}}) {
              TslVariant variant{execution, discovery, partition, choice.kind,
                                 style, width, movement, choice.hybrid};
              if (tsl_variant_is_implementable(variant)) {
                variants.push_back(variant);
              }
            }
          }
        }
      }
    }
   }
  }
  return variants;
}

// --- registration predicates ------------------------------------------------

// Why a case was not registered. Counted per reason and reported at startup so
// that a narrowed run never reads as a complete one.
enum class TslDropReason {
  StageVariant,        // the stage does not ask this variant family
  StageAxis,           // the stage does not ask this axis value
  MovementUnsupported, // no indirect form of this execution yet
  StyleUnavailable,    // a clang family needs a clang build of a new enough clang
  QuadraticTwoWay,     // two-way on a low-cardinality key above the size cap
  DetectorInapplicable,// non-scalar detector where no discovery happens
  DetectorUnavailable, // backend not compiled into this binary
  FootprintCap,        // estimated allocation above the memory cap
  DropReasonCount,
};

inline auto tsl_drop_reason_name(TslDropReason reason) -> char const * {
  switch (reason) {
    case TslDropReason::StageVariant: return "not in this stage's variant set";
    case TslDropReason::StageAxis: return "not in this stage's axis set";
    case TslDropReason::MovementUnsupported: return "no indirect form of this execution";
    case TslDropReason::StyleUnavailable: return "implementation style unavailable in this build";
    case TslDropReason::QuadraticTwoWay: return "two-way is quadratic on this key column";
    case TslDropReason::DetectorInapplicable: return "detector cannot engage here";
    case TslDropReason::DetectorUnavailable: return "detector backend not compiled in";
    case TslDropReason::FootprintCap: return "footprint above the memory cap";
    default: return "unknown";
  }
}

struct TslDropLog {
  std::size_t counts[static_cast<std::size_t>(TslDropReason::DropReasonCount)] = {};
  void drop(TslDropReason reason) { ++counts[static_cast<std::size_t>(reason)]; }
  auto total() const -> std::size_t {
    std::size_t sum = 0;
    for (auto count : counts) sum += count;
    return sum;
  }
};

// The stage plan. Vectors are axes whose Cartesian product is registered; the
// scalar fields are pinned per process, because the executor configuration
// cannot vary within one binary run.
struct TslStagePlan {
  TslStage stage = TslStage::Screen;
  std::vector<TslStyle> styles{TslStyle::Intrinsics};
  std::vector<TslMovement> movements{TslMovement::Direct};
  std::vector<std::size_t> widths{512};
  std::vector<std::size_t> element_bytes{4};
  std::vector<std::string> shapes;          // dataset selectors, see cosort_case.hpp
  std::vector<std::size_t> size_levels{1, 3};
  std::vector<std::size_t> columns{3};
  std::vector<int> directions{0};           // 0 asc, 1 desc, 2 alternating
  // The `rle=` axis. Scalar is always present; accelerator backends appear only
  // in a build configured for that machine's accelerator.
  std::vector<TslDetectorBackend> detectors{TslDetectorBackend::Scalar};
  TslDetectorConfig detector_config;
  std::size_t worker_count = 0;
  std::size_t task_threshold = 4096;
  std::size_t partition_threshold = 16384;
  std::uint64_t memory_cap = 64ull * 1024 * 1024 * 1024;
  std::size_t cache_bytes = 8ull * 1024 * 1024 * 1024;
  bool describe_datasets = false;
  // Two-way on a low-cardinality key is quadratic in the equal-run length, so it
  // is registered only below this working-set size.
  std::uint64_t two_way_size_cap = 256 * 1024;

  // A non-scalar detector needs a seam, work to discover, and a range large
  // enough for an offload to pay for itself. Only the parallel path has the seam:
  // the serial driver calls the scalar scan directly, and an asynchronous detector
  // needs the executor for pending-work accounting regardless.
  auto detector_applies(TslVariant const & variant, TslDetectorBackend backend,
                        std::size_t column_count, std::size_t size_level) const -> bool {
    if (backend == TslDetectorBackend::Scalar) {
      return true;
    }
    // The indirect driver reaches the detector from both its executions, on the
    // contiguous materialized key buffer. Its parallel form calls discovery from
    // worker threads, which a fleet handles, but it never polls, so an
    // asynchronous backend would not complete.
    auto const frequency = backend == TslDetectorBackend::IaaFrequencySoftware
      || backend == TslDetectorBackend::IaaFrequencyHardware;
    // Frequency discovery needs a range handed over before it is sorted. Only the
    // indirect sorter's post-sort path does that -- incremental reports leaves
    // discovered during the sort, so there is no such moment.
    if (frequency
        && (variant.movement != TslMovement::Index
            || variant.discovery != TslRunDiscoveryKind::POST_SORT)) {
      return false;
    }
    auto const has_seam = variant.movement == TslMovement::Index
      ? !tsl_detector_is_async(backend)
      : variant.execution != TslExecution::Serial;
    return has_seam
        && column_count >= 2
        && size_level >= 2            // halfLLC and above
        && variant.width_bits == 512; // the detector does not depend on lane count
  }

  // Does the stage ask for this variant at all? This is the per-family predicate:
  // scope restrictions live here, in the registrar, rather than in a filter
  // string a reader of the results never sees.
  auto admits(TslVariant const & variant) const -> bool {
    switch (stage) {
      case TslStage::Screen:
        // Every variant, one point per axis: the question is viability.
        return true;
      case TslStage::Tune:
        // Only the executor configuration matters here, so only variants that
        // have one.
        return variant.execution != TslExecution::Serial;
      case TslStage::Characterize:
        // Finalists only; the caller supplies them by name.
        return true;
      case TslStage::Attribute:
        // Style comparison against the simplest possible surroundings: serial,
        // post-sort, so nothing but the primitives differs.
        return variant.execution == TslExecution::Serial
            && variant.discovery == TslRunDiscoveryKind::POST_SORT;
    }
    return false;
  }
};

// Dataset selectors used by the stages. These are prefixes of the generated
// dataset ids, so they name a shape together with its parameters.
inline auto tsl_screen_shapes() -> std::vector<std::string> {
  return {
    "unique_first",              // minimal depth, all payload movement
    "unique_last_g2",            // maximal depth, per-task cost dominates
    "unique_last_g64",           // maximal depth, leaf-sized terminal groups
    "independent_uniform_c1024", // the conventional reference
    "skewed_zipf_s1",            // heavy-tailed group sizes
    "low_cardinality_d4",        // duplicate dominated, separates partition kinds
  };
}

inline auto tsl_tune_shapes() -> std::vector<std::string> {
  return {"unique_last_g64", "independent_uniform_c1024", "low_cardinality_d4"};
}

inline auto tsl_attribute_shapes() -> std::vector<std::string> {
  return {"unique_first", "unique_last_g64", "low_cardinality_d4"};
}

// `characterize` uses the whole catalog: an empty selector list means "every
// dataset the generator offers at this size and column count".
inline auto tsl_characterize_shapes() -> std::vector<std::string> { return {}; }

inline auto tsl_default_plan(TslStage stage) -> TslStagePlan {
  TslStagePlan plan;
  plan.stage = stage;
  switch (stage) {
    case TslStage::Screen:
      plan.shapes = tsl_screen_shapes();
      plan.size_levels = {1, 3};              // L2 and LLC
      plan.describe_datasets = false;
      // The indirect family is a viability question like any other. It has the
      // serial and parallel executions, so it costs sixteen names here.
      plan.movements = {TslMovement::Direct, TslMovement::Index};
      break;
    case TslStage::Tune:
      plan.shapes = tsl_tune_shapes();
      plan.size_levels = {1, 3};
      break;
    case TslStage::Characterize:
      plan.shapes = tsl_characterize_shapes();
      plan.size_levels = {1, 3, 4};           // L2, LLC, 2xLLC
      plan.element_bytes = {4, 8};
      plan.describe_datasets = true;
      break;
    case TslStage::Attribute:
      plan.shapes = tsl_attribute_shapes();
      plan.styles = {
        TslStyle::Intrinsics, TslStyle::ClangBuiltin, TslStyle::ClangBoolMask
      };
      plan.widths = {128, 256, 512};
      // Both key widths. A style comparison on 4-byte keys only would leave the
      // case where a register holds half as many elements unmeasured, and lane
      // count is exactly what separates one style's codegen from another's.
      plan.element_bytes = {4, 8};
      plan.size_levels = {1, 3};
      break;
  }
  return plan;
}
