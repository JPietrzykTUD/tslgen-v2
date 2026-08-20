#pragma once

// Standalone "leashed" variant of the multicolumn sort (experiment).
//
// This is a SELF-CONTAINED header, deliberately independent of the shared
// `multicolumn_quicksort.hpp` so the experiment never touches that file. The
// leash pre-partition is the *sole* partition behavior here -- there is no
// plain-partition baseline path and no on/off flag. It reuses the shared leaf,
// task, run-discovery and type headers unchanged.
//
// Sorter class: `TslMultiColumnLeashedSorter` (renamed from the shared sorter so
// the two headers can coexist without an ODR clash). Leash tuning knobs are the
// `chunk_lanes` / `leash_lanes` statics. See benchmarks/leashed_bench.cpp.

#include <algorithm>
#include <array>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <random>
#include <stdexcept>
#include <type_traits>
#include <utility>

#include <tsl.hpp>

#include "cosort_bitonic_leaf.hpp"
#include "cosort_network.hpp"
#include "equal_runs.hpp"
#include "multicolumn_sort_types.hpp"
#include "multicolumn_sort_tasks.hpp"


// Deferred pivot generator.
//
// Only `get_pivot` reads the generator, and only a range above the leaf
// threshold ever partitions, so a range that goes straight to its leaf never
// needs one. Seeding `std::mt19937_64` eagerly per task therefore initialized
// 2496 bytes of state (~400ns) for nothing on every small next-column task --
// and low-cardinality inputs produce millions of those. Holding the seed and
// materializing on first use keeps the generated sequence identical for any
// range that does partition.
//
// Unsynchronized on purpose: like the generator it replaces, one instance is a
// local of a single sort call and is only ever reached from that call's own
// thread. A worker that takes over a partition receives a task descriptor and
// seeds its own instance from task_seed. Do not promote this to a member or
// share one across workers -- the check-then-emplace in get() would then race.
class TslLazyPivotRng {
  std::uint64_t seed_;
  std::optional<std::mt19937_64> rng_;

 public:
  explicit TslLazyPivotRng(std::uint64_t seed) : seed_(seed) {}

  auto get() -> std::mt19937_64 & {
    if (!rng_.has_value()) {
      rng_.emplace(seed_);
    }
    return *rng_;
  }
};


// True when a run detector participates in executor accounting, i.e. exposes
// bind(TslPendingWork&) and poll(). Synchronous detectors do not, and are wired
// as plain callables.
template <class Detector, class = void>
struct tsl_detector_wants_executor : std::false_type {};

template <class Detector>
struct tsl_detector_wants_executor<
  Detector,
  decltype(
    std::declval<Detector &>().bind(std::declval<TslPendingWork &>()),
    std::declval<Detector &>().poll(),
    void()
  )
> : std::true_type {};


enum class TslLeafKind { INSERTION, NETWORK };
enum class TslPartitionKind { TWO_WAY, THREE_WAY };


// Sorts one active key while replaying its permutation on a runtime number of
// payload columns. sort_columns builds a lexicographic sort from that primitive
// by sorting the next column only inside complete equal runs of the active key.
template <
  class DataType = std::uint32_t,
  TslPartitionKind PartitionKind = TslPartitionKind::TWO_WAY,
  TslLeafKind LeafKind = TslLeafKind::INSERTION,
  std::size_t MaxColumns = 16,
  class SimdStyle = tsl::dataparallel::simd_for_t<tsl::dataparallel::native, DataType>
>
class TslMultiColumnLeashedSorter {
  using DataSimdStyle = SimdStyle;
  static_assert(std::is_same_v<typename SimdStyle::base_type, DataType>,
                "SimdStyle::base_type must match DataType");
  using register_type = typename DataSimdStyle::register_type;
  using Partition = TslPartitionReplayStep<DataType, SimdStyle>;
  static constexpr std::size_t lane_count = DataSimdStyle::lane_count_v;
  static constexpr std::size_t compute_leaf_threshold() {
    if constexpr (LeafKind == TslLeafKind::NETWORK) {
      return TslCoSortBitonicLeaf<DataType, SimdStyle>::capacity;
    } else {
      return 64;
    }
  }
  static constexpr std::size_t leaf_threshold = compute_leaf_threshold();

  using column_pointers = std::array<DataType *, MaxColumns>;

 public:
  // --- Leash tuning knobs (see the partition method). Static so a benchmark
  // can sweep them without recompiling. Sizes are in SIMD lanes; the element
  // size is lane * lane_count.
  //   chunk_lanes : size of each pre-partitioned chunk
  //   leash_lanes : how far ahead of the outer cursor a chunk is seeded
  // Defaults keep a chunk near L1/L2 residency; tune on the target CPU.
  // leash_enabled toggles the pre-partitioning at runtime.
  static inline bool leash_enabled = true;
  static inline std::size_t chunk_lanes = 256;
  static inline std::size_t leash_lanes = 256;

 private:
  struct three_way_bounds {
    std::size_t left_end;
    std::size_t equal_begin;
    std::size_t equal_end;
    std::size_t right_begin;
  };

  std::uint64_t const seed_;

  static auto mix_seed(std::uint64_t value) -> std::uint64_t {
    value += 0x9e3779b97f4a7c15ULL;
    value = (value ^ (value >> 30)) * 0xbf58476d1ce4e5b9ULL;
    value = (value ^ (value >> 27)) * 0x94d049bb133111ebULL;
    return value ^ (value >> 31);
  }

  auto task_seed(
    std::size_t column,
    std::size_t begin,
    std::size_t end
  ) const -> std::uint64_t {
    auto value = seed_;
    value ^= mix_seed(static_cast<std::uint64_t>(column));
    value ^= mix_seed(static_cast<std::uint64_t>(begin));
    value ^= mix_seed(static_cast<std::uint64_t>(end));
    return mix_seed(value);
  }

  template <TslSortOrder Order>
  static auto before(DataType left, DataType right) -> bool {
    if constexpr (Order == TslSortOrder::ASCENDING) {
      return left < right;
    } else {
      return left > right;
    }
  }

  static void swap_all(
    DataType * keys,
    column_pointers const & columns,
    std::size_t payload_count,
    std::size_t left,
    std::size_t right
  ) {
    std::swap(keys[left], keys[right]);
    for (std::size_t column = 0; column < payload_count; ++column) {
      std::swap(columns[column][left], columns[column][right]);
    }
  }

  template <TslSortOrder Order>
  static auto get_pivot(
    DataType * keys,
    column_pointers const & columns,
    std::size_t payload_count,
    std::size_t count,
    std::mt19937_64 & rng
  ) -> DataType {
    auto const i0 = static_cast<std::size_t>(rng() % count);
    auto const i1 = static_cast<std::size_t>(rng() % count);
    auto const i2 = static_cast<std::size_t>(rng() % count);
    auto const a = keys[i0];
    auto const b = keys[i1];
    auto const c = keys[i2];
    std::size_t median_index;
    if (before<Order>(a, b)) {
      median_index = before<Order>(b, c) ? i1 : (before<Order>(a, c) ? i2 : i0);
    } else {
      median_index = before<Order>(a, c) ? i0 : (before<Order>(b, c) ? i2 : i1);
    }
    swap_all(keys, columns, payload_count, median_index, count - 1);
    return keys[count - 1];
  }

  // Partition. The pivot remains at keys[count - 1]. BEFORE_PIVOT returns the
  // first element not ordered before it; EQUAL_TO returns the first element
  // ordered after it within a range known to contain only equal/after values.
  //
  // A bidirectional SIMD Hoare partition with two extra twists layered on:
  //
  // LEASH: while the outer left/right cursors converge it also runs up to two
  // inner "leash" streams. Each leash pre-partitions a small chunk -- sized
  // (chunk_lanes) to stay cache-resident -- seeded a short distance
  // (leash_lanes) ahead of an outer cursor, against the *same* pivot. By the
  // time the outer cursor reaches that chunk it is already [before-pivot |
  // not-before-pivot], so the outer loop loads mostly homogeneous registers and
  // takes its fast (advance / bulk-move) path far more often. The extra inner
  // work is independent of the outer work, exposing ILP/MLP within this single
  // thread.
  //
  // JUMP: when a leash retires it records the region it has already made "good";
  // the outer cursor pointer-jumps over that region instead of re-scanning it,
  // guarded by a per-side dirty flag (the outer partition may write into a
  // recorded region as it arrives, which invalidates the jump).
  //
  // Correctness (why the leashes are invisible to the result):
  //   * A leash only ever *reorders elements within its own chunk*; it never
  //     moves an element out of the chunk, so the multiset of values in the
  //     array is unchanged and the final split index is identical.
  //   * The outer partition's result depends only on element *values*, never on
  //     their order within any not-yet-processed region -- so reordering a
  //     disjoint chunk cannot change what the outer pass computes.
  //   * Single-threaded: the streams are one instruction stream, so there is no
  //     data race, only ordering. A chunk is stepped only while it is provably
  //     disjoint from both outer cursors and from the other leash (checked
  //     against the current cursor positions each iteration). A leash that can
  //     no longer sit safely between the cursors is switched OFF rather than
  //     re-seeded across the midpoint -- it never jumps into the region the
  //     opposite cursor is finalizing (the array midpoint `mid` is the fence).
  template <TslSortOrder Order, TslPartitionMode Mode>
  static auto partition(
    DataType * keys,
    column_pointers const & columns,
    std::size_t payload_count,
    std::size_t count,
    DataType pivot_value
  ) -> std::size_t {
    auto const pivot_vec = tsl::set1<DataSimdStyle>(pivot_value);
    DataType * const pivot_ptr = keys + count - 1;

    enum class advance_state { RIGHT, BOTH };
    struct Stream {
      DataType * left_ptr = nullptr;
      DataType * right_ptr = nullptr;
      DataType * chunk_begin = nullptr;  // fixed bounds of the chunk being
      DataType * chunk_end = nullptr;    // pre-partitioned (leash streams only)
      register_type key_l{};
      register_type key_r{};
      std::size_t bad_l_count = 0;
      std::size_t bad_r_count = 0;
      advance_state advance = advance_state::BOTH;
      bool active = false;
    };

    auto const bad_left = [&](register_type value) {
      if constexpr (Mode == TslPartitionMode::BEFORE_PIVOT) {
        if constexpr (Order == TslSortOrder::ASCENDING) {
          return tsl::greater_than_or_equal<DataSimdStyle>(value, pivot_vec);
        } else {
          return tsl::less_than_or_equal<DataSimdStyle>(value, pivot_vec);
        }
      } else if constexpr (Order == TslSortOrder::ASCENDING) {
        return tsl::greater_than<DataSimdStyle>(value, pivot_vec);
      } else {
        return tsl::less_than<DataSimdStyle>(value, pivot_vec);
      }
    };
    auto const bad_right = [&](register_type value) {
      if constexpr (Mode == TslPartitionMode::BEFORE_PIVOT) {
        if constexpr (Order == TslSortOrder::ASCENDING) {
          return tsl::less_than<DataSimdStyle>(value, pivot_vec);
        } else {
          return tsl::greater_than<DataSimdStyle>(value, pivot_vec);
        }
      } else {
        return tsl::equal<DataSimdStyle>(value, pivot_vec);
      }
    };

    auto const alive = [&](Stream const & s) {
      return (s.right_ptr - s.left_ptr) >= static_cast<std::ptrdiff_t>(lane_count);
    };

    // Which branch a `step` took. The jump variant needs to know whether an
    // outer step STORED into a pre-partitioned region (a stitch) versus just
    // scanned past an all-good register (an advance, no store), so it can tell
    // whether a recorded good region is still pristine.
    enum class StepKind { LeftAdvance, RightAdvance, Stitch };

    // One iteration of the converging SIMD partition for stream `s`, reading and
    // writing only the lane at s.left_ptr and the lane at s.right_ptr. The outer
    // cursor and each leash stream all advance by stepping this same body.
    auto const step = [&](Stream & s) -> StepKind {
      if (s.advance == advance_state::BOTH) {
        s.key_l = tsl::load<DataSimdStyle, false>(s.left_ptr);
        s.bad_l_count =
          tsl::mask_population_count<DataSimdStyle>(bad_left(s.key_l));
        if (s.bad_l_count == 0) {
          s.left_ptr += lane_count;
          return StepKind::LeftAdvance;
        }
      }
      if (s.advance == advance_state::RIGHT || s.advance == advance_state::BOTH) {
        s.key_r = tsl::load<DataSimdStyle, false>(s.right_ptr);
        s.bad_r_count =
          tsl::mask_population_count<DataSimdStyle>(bad_right(s.key_r));
        if (s.bad_r_count == 0) {
          s.right_ptr -= lane_count;
          s.advance = advance_state::RIGHT;
          return StepKind::RightAdvance;
        }
      }
      auto const left_offset = static_cast<std::size_t>(s.left_ptr - keys);
      auto const right_offset = static_cast<std::size_t>(s.right_ptr - keys);
      // Uninitialized on purpose: only [0, payload_count) is ever written or
      // read. Value-initializing them made every swap iteration memset
      // 4 * MaxColumns * sizeof(register_type) bytes of stack.
      std::array<register_type, MaxColumns> payload_l;
      std::array<register_type, MaxColumns> payload_r;
      std::array<register_type, MaxColumns> payload_write_l;
      std::array<register_type, MaxColumns> payload_write_r;
      for (std::size_t column = 0; column < payload_count; ++column) {
        payload_l[column] =
          tsl::load<DataSimdStyle, false>(columns[column] + left_offset);
        payload_r[column] =
          tsl::load<DataSimdStyle, false>(columns[column] + right_offset);
      }
      register_type key_write_l;
      register_type key_write_r;
      Partition::template step<Mode, Order>(
        s.key_l,
        s.key_r,
        payload_l.data(),
        payload_r.data(),
        payload_count,
        pivot_vec,
        key_write_l,
        key_write_r,
        payload_write_l.data(),
        payload_write_r.data()
      );
      tsl::store<DataSimdStyle, false>(s.left_ptr, key_write_l);
      tsl::store<DataSimdStyle, false>(s.right_ptr, key_write_r);
      for (std::size_t column = 0; column < payload_count; ++column) {
        tsl::store<DataSimdStyle, false>(
          columns[column] + left_offset, payload_write_l[column]);
        tsl::store<DataSimdStyle, false>(
          columns[column] + right_offset, payload_write_r[column]);
      }
      auto const swappable = std::min(s.bad_l_count, s.bad_r_count);
      s.left_ptr += swappable + (lane_count - s.bad_l_count);
      s.right_ptr -= swappable + (lane_count - s.bad_r_count);
      s.advance = advance_state::BOTH;
      return StepKind::Stitch;
    };

    Stream outer;
    outer.left_ptr = keys;
    DataType * scalar_end = pivot_ptr;

    if (static_cast<std::size_t>(pivot_ptr - keys) >= 2 * lane_count) {
      outer.right_ptr = pivot_ptr - lane_count;

      std::size_t const margin = lane_count;
      std::size_t const chunk =
        std::max<std::size_t>(1, chunk_lanes) * lane_count;
      std::size_t const leash =
        std::max<std::size_t>(1, leash_lanes) * lane_count;
      // Smallest live region that can host two disjoint chunks plus cursor
      // margins. Below this the leash block is skipped entirely, which also
      // keeps every pointer we form well inside the array.
      std::size_t const min_region = 2 * (leash + chunk) + 4 * margin;

      auto const align_down = [&](DataType * p) {
        auto const idx = static_cast<std::size_t>(p - keys);
        return keys + (idx / lane_count) * lane_count;
      };

      Stream left_leash;
      Stream right_leash;

      // Jump bookkeeping. When a leash retires it records its
      // guaranteed-good region, and the outer cursor pointer-jumps over it
      // instead of re-scanning: left good prefix [l_jb, l_js) is all
      // "good-for-left" (before-pivot / equal, per Mode); right good suffix
      // [r_js, r_je) is all "good-for-right". Reseeding a side is gated while a
      // jump is pending, so there is at most one pending region per side.
      //
      // A recorded region is only pristine until the outer cursor's OWN stitch
      // stores start writing into it: the outer and chunk register grids are
      // not aligned, so the register straddling the region boundary is stitched
      // and deposits an as-yet-unplaced (carry) element into the good part.
      // The `*_dirty` flags track exactly that -- a jump is only sound while its
      // region is still clean, so we drop the jump the moment a stitch touches
      // it. (A dropped jump just means normal scanning: always correct.)
      bool l_jump_pending = false;
      bool r_jump_pending = false;
      bool l_region_dirty = false;
      bool r_region_dirty = false;
      DataType * l_jb = nullptr;
      DataType * l_js = nullptr;
      DataType * r_js = nullptr;
      DataType * r_je = nullptr;

      while (alive(outer)) {
        DataType * const pre_l = outer.left_ptr;
        DataType * const pre_r = outer.right_ptr;
        StepKind const kind = step(outer);

        {  // consume any pending leash-jump over an already-good region
          // A stitch stores the compressed registers back to [pre_l, pre_l+lane)
          // and [pre_r, pre_r+lane). If either store overlaps a pending region,
          // that region now holds a carry element and is no longer pristine.
          if (kind == StepKind::Stitch) {
            if (l_jump_pending && pre_l < l_js && pre_l + lane_count > l_jb)
              l_region_dirty = true;
            if (r_jump_pending && pre_r < r_je && pre_r + lane_count > r_js)
              r_region_dirty = true;
          }

          // Consume the pending left good-prefix. Sound iff the region is still
          // pristine (!l_region_dirty) and the current register sits fully
          // inside it -- then every element in [left_ptr, l_js) is good-for-left
          // and can be skipped. Works in either advance state: a pending left
          // register (RIGHT state) is preserved across the pointer jump and
          // finds its swap partner past the split. Drop the jump if it can no
          // longer be taken (region consumed/crossed/dirtied).
          if (l_jump_pending) {
            bool const clean_inside =
              !l_region_dirty && outer.left_ptr >= l_jb &&
              outer.left_ptr + lane_count <= l_js && l_js < outer.right_ptr;
            if (clean_inside) {
#ifdef TSL_LEASH_JUMP_DEBUG
              for (DataType * p = outer.left_ptr; p < l_js; ++p) {
                bool good;
                if constexpr (Mode == TslPartitionMode::BEFORE_PIVOT)
                  good = before<Order>(*p, pivot_value);
                else
                  good = (*p == pivot_value);
                if (!good) {
                  std::fprintf(stderr,
                    "LEFT JUMP BAD idx=%td val=%u pivot=%u [l_jb=%td l_js=%td]\n",
                    p - keys, (unsigned)*p, (unsigned)pivot_value,
                    l_jb - keys, l_js - keys);
                  std::abort();
                }
              }
#endif
              outer.left_ptr = l_js;
              l_jump_pending = false;
            } else if (l_region_dirty || outer.left_ptr >= l_js ||
                       l_js >= outer.right_ptr) {
              l_jump_pending = false;
            }
          }
          // Symmetric right good-suffix consume.
          if (r_jump_pending) {
            bool const clean_inside =
              !r_region_dirty && outer.right_ptr + lane_count <= r_je &&
              outer.right_ptr >= r_js && r_js - lane_count > outer.left_ptr;
            if (clean_inside) {
#ifdef TSL_LEASH_JUMP_DEBUG
              for (DataType * p = r_js; p < outer.right_ptr + lane_count; ++p) {
                bool good;
                if constexpr (Mode == TslPartitionMode::BEFORE_PIVOT)
                  good = !before<Order>(*p, pivot_value);
                else
                  good = before<Order>(pivot_value, *p);
                if (!good) {
                  std::fprintf(stderr,
                    "RIGHT JUMP BAD idx=%td val=%u pivot=%u [r_js=%td r_je=%td]\n",
                    p - keys, (unsigned)*p, (unsigned)pivot_value,
                    r_js - keys, r_je - keys);
                  std::abort();
                }
              }
#endif
              outer.right_ptr = r_js - lane_count;
              r_jump_pending = false;
            } else if (r_region_dirty || outer.right_ptr < r_js ||
                       r_js - lane_count <= outer.left_ptr) {
              r_jump_pending = false;
            }
          }
        }

        bool const region_ok =
          leash_enabled &&
          (outer.right_ptr - outer.left_ptr) >=
            static_cast<std::ptrdiff_t>(min_region);
        if (!region_ok) {
          left_leash.active = false;
          right_leash.active = false;
          continue;
        }

        // Fence: neither leash may cross the midpoint of the live region, so the
        // two leashes stay in opposite halves and never collide, and neither
        // wanders into the region the opposite cursor is consuming.
        DataType * const mid =
          outer.left_ptr + (outer.right_ptr - outer.left_ptr) / 2;

        // ---- left leash: chunk seeded `leash` ahead of the left cursor ----
        // [chunk_begin, left_ptr) is all good-for-left at every step (partition
        // invariant), so recording it on retirement is valid whether the leash
        // fully converged or was retired early.
        auto const retire_left = [&]() {
          l_jump_pending = true;
          l_region_dirty = false;
          l_jb = left_leash.chunk_begin;
          l_js = left_leash.left_ptr;
          left_leash.active = false;
        };
        if (left_leash.active &&
            !(outer.left_ptr + margin <= left_leash.chunk_begin &&
              left_leash.chunk_end + margin <= mid &&
              alive(left_leash))) {
          retire_left();  // cursor closing in / no longer safe
        }
        if (left_leash.active) {
          step(left_leash);
          if (!alive(left_leash)) retire_left();  // chunk done
        }
        if (!left_leash.active && !l_jump_pending) {
          DataType * const begin = align_down(outer.left_ptr + leash);
          DataType * const end = begin + chunk;
          if (begin >= outer.left_ptr + margin && end + margin <= mid) {
            left_leash = Stream{};
            left_leash.chunk_begin = begin;
            left_leash.chunk_end = end;
            left_leash.left_ptr = begin;
            left_leash.right_ptr = end - lane_count;
            left_leash.active = alive(left_leash);
          }
        }

        // ---- right leash: chunk seeded `leash` ahead of the right cursor ----
        // [right_ptr + lane_count, chunk_end) is all good-for-right at every
        // step, so recording it on retirement is valid either way.
        auto const retire_right = [&]() {
          r_jump_pending = true;
          r_region_dirty = false;
          r_js = right_leash.right_ptr + lane_count;
          r_je = right_leash.chunk_end;
          right_leash.active = false;
        };
        if (right_leash.active &&
            !(right_leash.chunk_end + margin <= outer.right_ptr &&
              right_leash.chunk_begin >= mid + margin &&
              alive(right_leash))) {
          retire_right();
        }
        if (right_leash.active) {
          step(right_leash);
          if (!alive(right_leash)) retire_right();
        }
        if (!right_leash.active && !r_jump_pending) {
          DataType * const end = align_down(outer.right_ptr - leash);
          DataType * const begin = end - chunk;
          if (end + margin <= outer.right_ptr && begin >= mid + margin) {
            right_leash = Stream{};
            right_leash.chunk_begin = begin;
            right_leash.chunk_end = end;
            right_leash.left_ptr = begin;
            right_leash.right_ptr = end - lane_count;
            right_leash.active = alive(right_leash);
          }
        }
      }

      scalar_end = outer.right_ptr + lane_count;
    }

    // Scalar cleanup of the < 2*lane_count middle.
    auto const left_good = [pivot_value](DataType value) {
      if constexpr (Mode == TslPartitionMode::BEFORE_PIVOT) {
        return before<Order>(value, pivot_value);
      } else {
        return value == pivot_value;
      }
    };
    auto const right_good = [pivot_value](DataType value) {
      if constexpr (Mode == TslPartitionMode::BEFORE_PIVOT) {
        return !before<Order>(value, pivot_value);
      } else {
        return before<Order>(pivot_value, value);
      }
    };

    DataType * left_ptr = outer.left_ptr;
    while (left_ptr < scalar_end) {
      while (left_ptr < scalar_end && left_good(*left_ptr)) {
        ++left_ptr;
      }
      while (left_ptr < scalar_end && right_good(*(scalar_end - 1))) {
        --scalar_end;
      }
      if (left_ptr < scalar_end) {
        swap_all(
          keys,
          columns,
          payload_count,
          static_cast<std::size_t>(left_ptr - keys),
          static_cast<std::size_t>((scalar_end - 1) - keys)
        );
        ++left_ptr;
        --scalar_end;
      }
    }
    return static_cast<std::size_t>(left_ptr - keys);
  }

  template <TslSortOrder Order>
  static void insertion_leaf(
    DataType * keys,
    column_pointers const & columns,
    std::size_t payload_count,
    std::size_t count
  ) {
    for (std::size_t index = 1; index < count; ++index) {
      auto const key = keys[index];
      std::array<DataType, MaxColumns> payload{};
      for (std::size_t column = 0; column < payload_count; ++column) {
        payload[column] = columns[column][index];
      }
      auto destination = index;
      while (destination > 0 && before<Order>(key, keys[destination - 1])) {
        keys[destination] = keys[destination - 1];
        for (std::size_t column = 0; column < payload_count; ++column) {
          columns[column][destination] = columns[column][destination - 1];
        }
        --destination;
      }
      keys[destination] = key;
      for (std::size_t column = 0; column < payload_count; ++column) {
        columns[column][destination] = payload[column];
      }
    }
  }

  template <TslSortOrder Order>
  static void leaf(
    DataType * keys,
    column_pointers const & columns,
    std::size_t payload_count,
    std::size_t count
  ) {
    if constexpr (LeafKind == TslLeafKind::NETWORK) {
      TslCoSortBitonicLeaf<DataType, SimdStyle>::template sort<Order>(
        keys,
        columns.data(),
        payload_count,
        count
      );
    } else {
      insertion_leaf<Order>(keys, columns, payload_count, count);
    }
  }

  // `range_sink` receives the absolute bounds of the partition side that would
  // otherwise become an inline recursive call. Returning true transfers
  // ownership of that range and this call skips it; returning false keeps the
  // recursion. The larger side is always continued in the loop, so recursion
  // depth stays logarithmic whether or not ranges are offloaded.
  //
  // Offering the smaller side is deliberate. Either choice publishes one
  // independent range per level, but keeping the larger side leaves this worker
  // with real work; publishing it instead would leave this worker with a
  // remainder it finishes immediately, and a newest-first queue would then very
  // likely hand the same large range straight back to it.
  template <
    TslSortOrder Order,
    bool ReportCompletion,
    class EqualBandSink,
    class LeafSink,
    class RangeSink
  >
  static void sort_impl(
    DataType * keys,
    column_pointers columns,
    std::size_t payload_count,
    std::size_t count,
    TslLazyPivotRng & rng,
    std::size_t absolute_begin,
    // Start of the maximal equal run overlapping this range's left edge when that
    // edge is open; equal to `absolute_begin` when it is closed.
    std::size_t open_begin,
    EqualBandSink & equal_band_sink,
    LeafSink & leaf_sink,
    RangeSink & range_sink
  ) {
    while (count > leaf_threshold) {
      auto const pivot_value =
        get_pivot<Order>(keys, columns, payload_count, count, rng.get());
      std::size_t left_count;
      std::size_t right_begin;
      std::size_t right_count;

      if constexpr (PartitionKind == TslPartitionKind::TWO_WAY) {
        auto const before_end = partition<Order, TslPartitionMode::BEFORE_PIVOT>(
          keys,
          columns,
          payload_count,
          count,
          pivot_value
        );
        swap_all(keys, columns, payload_count, before_end, count - 1);
        left_count = before_end;
        right_begin = before_end + 1;
        right_count = count - right_begin;
      } else {
        auto const before_end = partition<Order, TslPartitionMode::BEFORE_PIVOT>(
          keys,
          columns,
          payload_count,
          count,
          pivot_value
        );
        column_pointers middle_columns{};
        for (std::size_t column = 0; column < payload_count; ++column) {
          middle_columns[column] = columns[column] + before_end;
        }
        auto const equal_pivot_position = before_end + partition<Order, TslPartitionMode::EQUAL_TO>(
          keys + before_end,
          middle_columns,
          payload_count,
          count - before_end,
          pivot_value
        );
        swap_all(keys, columns, payload_count, equal_pivot_position, count - 1);
        three_way_bounds const bounds{
          before_end,
          before_end,
          equal_pivot_position + 1,
          equal_pivot_position + 1,
        };
        left_count = bounds.left_end;
        right_begin = bounds.right_begin;
        right_count = count - right_begin;
        if constexpr (ReportCompletion) {
          equal_band_sink(
            absolute_begin + bounds.equal_begin,
            absolute_begin + bounds.equal_end
          );
        }
      }

      // Boundary state of the two children. A three-way partition closes every
      // boundary it creates -- the equal band lies strictly between the two sides --
      // which is why three-way incremental discovery needs no bookkeeping. A
      // two-way partition leaves
      //
      //   [ strictly before pivot ] [ pivot ] [ not before pivot ]
      //
      // so the left part's right boundary is closed by the pivot while the right
      // part's left boundary is open: a maximal run may span the pivot and the head
      // of the right part. Right boundaries are always closed -- the root's is, a
      // left part's is the pivot, a right part inherits it -- so only the left edge
      // needs tracking.
      //
      // One bit does not suffice. On duplicate-heavy input two-way peels one copy per
      // level with an empty left part, so a run of k equal values becomes a chain of
      // k consecutive pivots, and widening a fragment by one element would cover only
      // the nearest. Carrying the *start* of the run that overlaps the left edge
      // covers a chain of any length: everything in [open_begin, absolute_begin) is
      // equal and already final, so a fragment reporting from there finds a maximal
      // run.
      //
      // A range handed to another worker re-enters as a root with a closed left edge,
      // so the open run travels with it: the range is offered from the run's start.
      // Those extra elements are final and no other worker writes them, and a range
      // beginning with its own minimum keeps it there, so the offer is
      // self-contained.
      constexpr bool two_way = PartitionKind == TslPartitionKind::TWO_WAY;
      auto right_open_begin = absolute_begin + right_begin;
      auto left_open_begin = absolute_begin;
      if constexpr (two_way) {
        left_open_begin = open_begin;
        right_open_begin = absolute_begin + left_count;   // the pivot's position
        if (left_count == 0 && open_begin < absolute_begin) {
          // The left part is empty, so the pivot sits immediately right of the open
          // run. Reading keys[-1] is safe: it is inside the column and final.
          if (keys[-1] == keys[0]) {
            right_open_begin = open_begin;                // the chain continues
          } else if (ReportCompletion && absolute_begin - open_begin >= 2) {
            // The chain ends here: a complete all-equal range that no fragment of
            // this subtree would otherwise cover.
            leaf_sink(open_begin, absolute_begin);
          }
        }
      }

      column_pointers right_columns{};
      for (std::size_t column = 0; column < payload_count; ++column) {
        right_columns[column] = columns[column] + right_begin;
      }
      auto * const right_keys = keys + right_begin;
      if (left_count < right_count) {
        if (!range_sink(left_open_begin, absolute_begin + left_count)) {
          sort_impl<Order, ReportCompletion>(
            keys,
            columns,
            payload_count,
            left_count,
            rng,
            absolute_begin,
            left_open_begin,
            equal_band_sink,
            leaf_sink,
            range_sink
          );
        }
        keys = right_keys;
        columns = right_columns;
        count = right_count;
        absolute_begin += right_begin;
        open_begin = right_open_begin;
      } else {
        if (!range_sink(right_open_begin, absolute_begin + count)) {
          sort_impl<Order, ReportCompletion>(
            right_keys,
            right_columns,
            payload_count,
            right_count,
            rng,
            absolute_begin + right_begin,
            right_open_begin,
            equal_band_sink,
            leaf_sink,
            range_sink
          );
        }
        count = left_count;
        open_begin = left_open_begin;
      }
    }

    if (count >= 2) {
      leaf<Order>(keys, columns, payload_count, count);
    }
    if constexpr (ReportCompletion) {
      // Reporting from `open_begin` makes every reported range closed on both sides,
      // so the runs a consumer finds in it are maximal. An empty fragment reports
      // nothing: its open run either continues into the sibling pivot, whose range
      // covers it, or was already reported where the chain ended.
      auto const report_end = absolute_begin + count;
      if (count != 0 && report_end - open_begin >= 2) {
        leaf_sink(open_begin, report_end);
      }
    }
  }

  template <
    bool ReportCompletion,
    class EqualBandSink,
    class LeafSink,
    class RangeSink
  >
  static void sort_active_range(
    DataType * keys,
    column_pointers const & columns,
    std::size_t payload_count,
    std::size_t count,
    TslSortOrder order,
    TslLazyPivotRng & rng,
    std::size_t absolute_begin,
    EqualBandSink & equal_band_sink,
    LeafSink & leaf_sink,
    RangeSink & range_sink
  ) {
    if (count < 2) {
      if constexpr (ReportCompletion) {
        if (count == 1) {
          leaf_sink(absolute_begin, absolute_begin + 1);
        }
      }
      return;
    }
    if (order == TslSortOrder::ASCENDING) {
      sort_impl<TslSortOrder::ASCENDING, ReportCompletion>(
        keys,
        columns,
        payload_count,
        count,
        rng,
        absolute_begin,
        absolute_begin,  // the root of a column sort is closed on both sides
        equal_band_sink,
        leaf_sink,
        range_sink
      );
    } else {
      sort_impl<TslSortOrder::DESCENDING, ReportCompletion>(
        keys,
        columns,
        payload_count,
        count,
        rng,
        absolute_begin,
        absolute_begin,
        equal_band_sink,
        leaf_sink,
        range_sink
      );
    }
  }

  // Serial entry points never transfer a partition range to another worker.
  static auto keep_range_local() {
    return [](std::size_t, std::size_t) { return false; };
  }

  static auto payload_columns_for(
    TslSortColumn<DataType> const * columns,
    std::size_t column_count,
    std::size_t active_column,
    std::size_t begin
  ) -> column_pointers {
    column_pointers payloads{};
    for (auto column = active_column + 1; column < column_count; ++column) {
      payloads[column - active_column - 1] = columns[column].data + begin;
    }
    return payloads;
  }

  template <TslRunDiscoveryKind Discovery>
  void sort_columns_impl(
    TslSortColumn<DataType> const * columns,
    std::size_t column_count,
    std::size_t active_column,
    std::size_t begin,
    std::size_t end,
    TslMultiColumnSortMetrics * metrics
  ) const {
    if (end - begin < 2 || active_column >= column_count) {
      return;
    }

    auto const payload_count = column_count - active_column - 1;
    auto const payloads = payload_columns_for(columns, column_count, active_column, begin);
    auto rng = TslLazyPivotRng(task_seed(active_column, begin, end));
    auto no_equal_band = [](std::size_t, std::size_t) {};
    auto no_leaf = [](std::size_t, std::size_t) {};
    auto no_range = keep_range_local();

    if constexpr (Discovery == TslRunDiscoveryKind::INCREMENTAL) {
      if (active_column + 1 == column_count) {
        sort_active_range<false>(
          columns[active_column].data + begin,
          payloads,
          payload_count,
          end - begin,
          columns[active_column].order,
          rng,
          begin,
          no_equal_band,
          no_leaf,
          no_range
        );
        return;
      }

      auto on_equal_band = [&](std::size_t band_begin, std::size_t band_end) {
        if (band_end - band_begin < 2) {
          return;
        }
        if (metrics != nullptr) {
          ++metrics->direct_equal_bands;
          metrics->direct_equal_band_rows += band_end - band_begin;
        }
        sort_columns_impl<Discovery>(
          columns,
          column_count,
          active_column + 1,
          band_begin,
          band_end,
          metrics
        );
      };
      auto on_leaf = [&](std::size_t leaf_begin, std::size_t leaf_end) {
        if (leaf_end - leaf_begin < 2) {
          return;
        }
        if (metrics != nullptr) {
          metrics->rle_values_scanned += leaf_end - leaf_begin;
        }
        tsl_for_each_equal_run(
          columns[active_column].data,
          leaf_begin,
          leaf_end,
          [&](TslRunSpan span) {
            sort_columns_impl<Discovery>(
              columns,
              column_count,
              active_column + 1,
              span.begin,
              span.end,
              metrics
            );
          }
        );
      };
      sort_active_range<true>(
        columns[active_column].data + begin,
        payloads,
        payload_count,
        end - begin,
        columns[active_column].order,
        rng,
        begin,
        on_equal_band,
        on_leaf,
        no_range
      );
      return;
    }

    sort_active_range<false>(
      columns[active_column].data + begin,
      payloads,
      payload_count,
      end - begin,
      columns[active_column].order,
      rng,
      begin,
      no_equal_band,
      no_leaf,
      no_range
    );
    if (active_column + 1 == column_count) {
      return;
    }
    if (metrics != nullptr) {
      metrics->rle_values_scanned += end - begin;
    }
    tsl_for_each_equal_run(
      columns[active_column].data,
      begin,
      end,
      [&](TslRunSpan span) {
        sort_columns_impl<Discovery>(
          columns,
          column_count,
          active_column + 1,
          span.begin,
          span.end,
          metrics
        );
      }
    );
  }

  struct concurrent_sort_metrics {
    std::atomic<std::size_t> rle_values_scanned{0};
    std::atomic<std::size_t> direct_equal_bands{0};
    std::atomic<std::size_t> direct_equal_band_rows{0};
    std::atomic<std::size_t> partition_tasks{0};
  };

  template <
    TslRunDiscoveryKind Discovery,
    class Schedule,
    class Offload,
    class DetectRuns,
    class MakeEmit
  >
  void process_parallel_task(
    TslSortColumn<DataType> const * columns,
    std::size_t column_count,
    TslColumnSortTask task,
    Schedule & schedule,
    Offload & offload,
    DetectRuns & detect_runs,
    MakeEmit & make_emit,
    concurrent_sort_metrics * metrics
  ) const {
    if (task.end - task.begin < 2 || task.column >= column_count) {
      return;
    }

    auto const payload_count = column_count - task.column - 1;
    auto const payloads = payload_columns_for(
      columns,
      column_count,
      task.column,
      task.begin
    );
    auto rng = TslLazyPivotRng(task_seed(task.column, task.begin, task.end));
    auto no_equal_band = [](std::size_t, std::size_t) {};
    auto no_leaf = [](std::size_t, std::size_t) {};

    // A partition subrange may be finished by a different worker only when this
    // task owes nothing to its complete range. Incremental discovery qualifies for
    // either partition kind: three-way closes every boundary it creates, and
    // two-way hands an open left edge to the receiving worker by widening the
    // offered range to include the pivot, so each partition reports self-contained
    // work no matter who sorts it. A final column qualifies because no column
    // follows it. Post-sort discovery over a non-final column does not: its RLE
    // scan needs the whole sorted range, and an equal run may cross a partition
    // boundary, so those partitions stay on this worker.
    constexpr bool discovery_is_partition_local =
      Discovery == TslRunDiscoveryKind::INCREMENTAL;
    auto offload_range = [&](std::size_t range_begin, std::size_t range_end) {
      if (!discovery_is_partition_local && task.column + 1 != column_count) {
        return false;
      }
      if (!offload(TslColumnSortTask{task.column, range_begin, range_end})) {
        return false;
      }
      if (metrics != nullptr) {
        metrics->partition_tasks.fetch_add(1, std::memory_order_relaxed);
      }
      return true;
    };

    if constexpr (Discovery == TslRunDiscoveryKind::INCREMENTAL) {
      if (task.column + 1 == column_count) {
        sort_active_range<false>(
          columns[task.column].data + task.begin,
          payloads,
          payload_count,
          task.end - task.begin,
          columns[task.column].order,
          rng,
          task.begin,
          no_equal_band,
          no_leaf,
          offload_range
        );
        return;
      }

      auto on_equal_band = [&](std::size_t band_begin, std::size_t band_end) {
        if (band_end - band_begin < 2) {
          return;
        }
        if (metrics != nullptr) {
          metrics->direct_equal_bands.fetch_add(1, std::memory_order_relaxed);
          metrics->direct_equal_band_rows.fetch_add(
            band_end - band_begin,
            std::memory_order_relaxed
          );
        }
        schedule(TslColumnSortTask{task.column + 1, band_begin, band_end});
      };
      auto on_leaf = [&](std::size_t leaf_begin, std::size_t leaf_end) {
        if (leaf_end - leaf_begin < 2) {
          return;
        }
        if (metrics != nullptr) {
          metrics->rle_values_scanned.fetch_add(
            leaf_end - leaf_begin,
            std::memory_order_relaxed
          );
        }
        // make_emit, not a [&] lambda: an asynchronous detector retains this
        // callable past the end of this task, so it must own what it needs.
        detect_runs(
          columns[task.column].data,
          leaf_begin,
          leaf_end,
          make_emit(task.column + 1)
        );
      };
      sort_active_range<true>(
        columns[task.column].data + task.begin,
        payloads,
        payload_count,
        task.end - task.begin,
        columns[task.column].order,
        rng,
        task.begin,
        on_equal_band,
        on_leaf,
        offload_range
      );
      return;
    }

    sort_active_range<false>(
      columns[task.column].data + task.begin,
      payloads,
      payload_count,
      task.end - task.begin,
      columns[task.column].order,
      rng,
      task.begin,
      no_equal_band,
      no_leaf,
      offload_range
    );
    if (task.column + 1 == column_count) {
      return;
    }
    if (metrics != nullptr) {
      metrics->rle_values_scanned.fetch_add(
        task.end - task.begin,
        std::memory_order_relaxed
      );
    }
    detect_runs(
      columns[task.column].data,
      task.begin,
      task.end,
      make_emit(task.column + 1)
    );
  }

  static void validate_columns(
    TslSortColumn<DataType> const * columns,
    std::size_t column_count,
    std::size_t row_count
  ) {
    if (column_count > MaxColumns) {
      throw std::invalid_argument("sort column count exceeds MaxColumns");
    }
    if (column_count == 0) {
      return;
    }
    if (row_count == 0) {
      return;
    }
    if (columns == nullptr) {
      throw std::invalid_argument("sort columns pointer is null");
    }
    for (std::size_t column = 0; column < column_count; ++column) {
      if (columns[column].data == nullptr) {
        throw std::invalid_argument("sort column data pointer is null");
      }
      for (std::size_t previous = 0; previous < column; ++previous) {
        if (columns[column].data == columns[previous].data) {
          throw std::invalid_argument("sort columns must not alias");
        }
      }
    }
  }

 public:
  explicit TslMultiColumnLeashedSorter(std::uint64_t seed) : seed_(seed) {}

  static constexpr auto leaf_size_threshold() -> std::size_t {
    return leaf_threshold;
  }

  void sort_key(
    DataType * keys,
    DataType * const * payload_columns,
    std::size_t payload_count,
    std::size_t count,
    TslSortOrder order
  ) const {
    if (payload_count > MaxColumns) {
      throw std::invalid_argument("payload column count exceeds MaxColumns");
    }
    if (count == 0) {
      return;
    }
    if (count != 0 && keys == nullptr) {
      throw std::invalid_argument("key pointer is null");
    }
    if (payload_count != 0 && payload_columns == nullptr) {
      throw std::invalid_argument("payload columns pointer is null");
    }

    column_pointers columns{};
    for (std::size_t column = 0; column < payload_count; ++column) {
      if (count != 0 && payload_columns[column] == nullptr) {
        throw std::invalid_argument("payload column data pointer is null");
      }
      if (payload_columns[column] == keys) {
        throw std::invalid_argument("active key must not alias a payload column");
      }
      for (std::size_t previous = 0; previous < column; ++previous) {
        if (payload_columns[column] == payload_columns[previous]) {
          throw std::invalid_argument("payload columns must not alias");
        }
      }
      columns[column] = payload_columns[column];
    }
    auto rng = TslLazyPivotRng(task_seed(0, 0, count));
    auto no_equal_band = [](std::size_t, std::size_t) {};
    auto no_leaf = [](std::size_t, std::size_t) {};
    auto no_range = keep_range_local();
    sort_active_range<false>(
      keys,
      columns,
      payload_count,
      count,
      order,
      rng,
      0,
      no_equal_band,
      no_leaf,
      no_range
    );
  }

  void operator()(
    DataType * keys,
    DataType * const * payload_columns,
    std::size_t payload_count,
    std::size_t count
  ) const {
    sort_key(
      keys,
      payload_columns,
      payload_count,
      count,
      TslSortOrder::ASCENDING
    );
  }

  template <class EqualBandSink, class LeafSink>
  void sort_key_with_completion_events(
    DataType * keys,
    DataType * const * payload_columns,
    std::size_t payload_count,
    std::size_t count,
    TslSortOrder order,
    std::size_t absolute_begin,
    EqualBandSink & equal_band_sink,
    LeafSink & leaf_sink
  ) const {
    // Both partition kinds report completion. Three-way emits pivot-equal bands
    // directly and closes every boundary; two-way emits none and instead widens a
    // fragment whose left edge is open, so a consumer sees closed ranges either
    // way.
    if (payload_count > MaxColumns) {
      throw std::invalid_argument("payload column count exceeds MaxColumns");
    }
    if (count == 0) {
      return;
    }
    if (count != 0 && keys == nullptr) {
      throw std::invalid_argument("key pointer is null");
    }
    if (payload_count != 0 && payload_columns == nullptr) {
      throw std::invalid_argument("payload columns pointer is null");
    }
    column_pointers columns{};
    for (std::size_t column = 0; column < payload_count; ++column) {
      if (count != 0 && payload_columns[column] == nullptr) {
        throw std::invalid_argument("payload column data pointer is null");
      }
      if (payload_columns[column] == keys) {
        throw std::invalid_argument("active key must not alias a payload column");
      }
      for (std::size_t previous = 0; previous < column; ++previous) {
        if (payload_columns[column] == payload_columns[previous]) {
          throw std::invalid_argument("payload columns must not alias");
        }
      }
      columns[column] = payload_columns[column];
    }
    auto rng = TslLazyPivotRng(task_seed(
      0,
      absolute_begin,
      absolute_begin + count
    ));
    auto no_range = keep_range_local();
    sort_active_range<true>(
      keys,
      columns,
      payload_count,
      count,
      order,
      rng,
      absolute_begin,
      equal_band_sink,
      leaf_sink,
      no_range
    );
  }

  void sort_columns(
    TslSortColumn<DataType> const * columns,
    std::size_t column_count,
    std::size_t row_count,
    TslRunDiscoveryKind discovery = TslRunDiscoveryKind::POST_SORT,
    TslMultiColumnSortMetrics * metrics = nullptr
  ) const {
    validate_columns(columns, column_count, row_count);
    if (metrics != nullptr) {
      *metrics = {};
    }
    if (column_count == 0 || row_count < 2) {
      return;
    }
    if (discovery == TslRunDiscoveryKind::INCREMENTAL) {
      sort_columns_impl<TslRunDiscoveryKind::INCREMENTAL>(
        columns,
        column_count,
        0,
        0,
        row_count,
        metrics
      );
    } else {
      sort_columns_impl<TslRunDiscoveryKind::POST_SORT>(
        columns,
        column_count,
        0,
        0,
        row_count,
        metrics
      );
    }
  }

  // `partition_threshold` is zero to keep every quicksort partition on the
  // worker that produced it, or the smallest partition row count worth handing
  // to another worker. It is deliberately separate from `task_threshold`: a
  // next-column task pays for run discovery plus a whole subtree, while a
  // partition task pays for one partition pass.
  // Default equal-run detector: the scalar linear pass. `sort_columns_parallel`
  // accepts a replacement so an accelerator-backed detector can be substituted
  // without this header knowing anything about the accelerator.
  struct scalar_run_detector {
    template <class Emit>
    void operator()(
      DataType const * values,
      std::size_t begin,
      std::size_t end,
      Emit && emit
    ) const {
      tsl_for_each_equal_run(values, begin, end, std::forward<Emit>(emit));
    }
  };

  void sort_columns_parallel(
    TslSortColumn<DataType> const * columns,
    std::size_t column_count,
    std::size_t row_count,
    std::size_t worker_count,
    std::size_t task_threshold,
    std::size_t partition_threshold,
    TslRunDiscoveryKind discovery = TslRunDiscoveryKind::POST_SORT,
    TslMultiColumnSortMetrics * metrics = nullptr
  ) const {
    scalar_run_detector detector;
    sort_columns_parallel(
      columns, column_count, row_count, worker_count, task_threshold,
      partition_threshold, discovery, detector, metrics
    );
  }

  template <class DetectRuns>
  void sort_columns_parallel(
    TslSortColumn<DataType> const * columns,
    std::size_t column_count,
    std::size_t row_count,
    std::size_t worker_count,
    std::size_t task_threshold,
    std::size_t partition_threshold,
    TslRunDiscoveryKind discovery,
    DetectRuns & detect_runs,
    TslMultiColumnSortMetrics * metrics = nullptr
  ) const {
    validate_columns(columns, column_count, row_count);
    if (metrics != nullptr) {
      *metrics = {};
    }
    if (column_count == 0 || row_count < 2) {
      return;
    }
    if (worker_count == 0) {
      throw std::invalid_argument("parallel sort requires at least one worker");
    }
    task_threshold = std::max<std::size_t>(task_threshold, 2);
    if (partition_threshold != 0) {
      // A range at or below the leaf threshold is never partitioned, so a
      // smaller value would only queue ranges that cannot produce children.
      partition_threshold = std::max(partition_threshold, leaf_threshold + 1);
    }

    concurrent_sort_metrics algorithm_metrics;
    auto worker = [&](TslColumnSortTask const & task, auto & executor) {
      auto schedule = [&](TslColumnSortTask child) {
        if (child.end - child.begin < task_threshold) {
          executor.run_inline(child);
        } else {
          executor.submit(std::move(child));
        }
      };
      // Unlike a next-column child, a partition range below the threshold is
      // declined rather than run inline: the caller still holds it and its own
      // recursion is cheaper than re-entering a task.
      auto offload = [&](TslColumnSortTask child) {
        if (
          partition_threshold == 0
          || child.end - child.begin < partition_threshold
        ) {
          return false;
        }
        executor.submit(std::move(child));
        return true;
      };
      // Produces a next-column emitter that captures nothing task-local: the
      // executor by pointer (it outlives the whole sort) and the threshold and
      // column by value. An asynchronous detector may invoke the result on
      // another worker long after this task returned, so a [&] capture of
      // `schedule` or `task` would dangle. Same scheduling policy as `schedule`.
      auto make_emit = [&executor, task_threshold](std::size_t next_column) {
        return [target = &executor, task_threshold, next_column](TslRunSpan span) {
          TslColumnSortTask child{next_column, span.begin, span.end};
          if (child.end - child.begin < task_threshold) {
            target->run_inline(child);
          } else {
            target->submit(std::move(child));
          }
        };
      };
      if (discovery == TslRunDiscoveryKind::INCREMENTAL) {
        process_parallel_task<TslRunDiscoveryKind::INCREMENTAL>(
          columns,
          column_count,
          task,
          schedule,
          offload,
          detect_runs,
          make_emit,
          metrics != nullptr ? &algorithm_metrics : nullptr
        );
      } else {
        process_parallel_task<TslRunDiscoveryKind::POST_SORT>(
          columns,
          column_count,
          task,
          schedule,
          offload,
          detect_runs,
          make_emit,
          metrics != nullptr ? &algorithm_metrics : nullptr
        );
      }
    };

    TslTaskExecutor<TslColumnSortTask, decltype(worker)> executor(
      worker_count,
      worker
    );
    // An asynchronous detector needs the executor to hold a pending unit per
    // in-flight range and needs its completions checked from worker threads.
    // Both are wired here, before the first task exists, so nothing can run
    // against a half-connected detector. Detectors without these members are
    // unaffected.
    if constexpr (tsl_detector_wants_executor<DetectRuns>::value) {
      detect_runs.bind(executor);
      executor.set_poller([&detect_runs] { detect_runs.poll(); });
    }
    executor.submit(TslColumnSortTask{0, 0, row_count});
    executor.wait();

    if (metrics != nullptr) {
      auto const task_metrics = executor.metrics();
      metrics->rle_values_scanned =
        algorithm_metrics.rle_values_scanned.load(std::memory_order_relaxed);
      metrics->direct_equal_bands =
        algorithm_metrics.direct_equal_bands.load(std::memory_order_relaxed);
      metrics->direct_equal_band_rows =
        algorithm_metrics.direct_equal_band_rows.load(std::memory_order_relaxed);
      metrics->partition_tasks_submitted =
        algorithm_metrics.partition_tasks.load(std::memory_order_relaxed);
      metrics->tasks_submitted = task_metrics.tasks_submitted;
      metrics->tasks_executed_inline = task_metrics.tasks_executed_inline;
      metrics->max_outstanding_tasks = task_metrics.max_outstanding_tasks;
      metrics->idle_poll_wakeups = task_metrics.idle_poll_wakeups;
    }
  }
};
