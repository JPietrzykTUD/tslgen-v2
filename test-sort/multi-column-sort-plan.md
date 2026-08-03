# Multi-column co-sort implementation plan

## Plan objective

Implement the lexicographic multi-column co-sort described in
[`multi-column-sort.md`](multi-column-sort.md) on top of the existing SIMD
co-sorting quicksort prototype.

The completed CPU implementation must:

- accept a runtime list of same-typed columns;
- accept an ascending or descending direction for every sort column;
- sort the first column over the full row range;
- discover maximal equal runs in each sorted prefix range;
- sort the next column only inside nontrivial equal runs;
- apply every active-key permutation to the remaining row columns;
- support the existing two-way and three-way partitions;
- support insertion and bitonic-network leaves;
- provide a serial complete-range RLE reference path;
- provide a parallel task-queue path;
- provide an incremental three-way path that scans completed leaves and submits
  pivot-equal bands directly;
- remain deterministic for a fixed input, seed, configuration, and variant;
- validate lexicographic order and whole-row preservation.

Incremental two-way run discovery and DSA-backed run detection are planned
extensions with explicit gates. They must not complicate or weaken the serial
complete-range baseline.

## Implementation status and gate decisions

As of 2026-07-23, Slices 1 through 7 are implemented in `test-sort`:

- direction-aware, stateless active-key sorting;
- scalar equal-run spans;
- serial post-sort lexicographic sorting;
- a dedicated correctness target;
- a true multi-column Google Benchmark;
- a C++17 task executor and parallel post-sort sorting;
- serial and parallel incremental three-way discovery with structural probes;
- optional quicksort-partition offload, so one active range can be sorted by
  more than one worker.

The Slice 8 two-way-incremental gate is closed. Representative local `u32`,
16-lane measurements showed that the two conditions did not coincide:

- On uniform L2-sized input, two-way network sorting was competitive
  (`14.90 ms` versus `15.12 ms` for post-sort three-way), but incremental
  three-way reduced scanned values by less than one percent and did not show an
  RLE-driven total-time win.
- On low-entropy L2-sized input, incremental three-way insertion reduced RLE
  scanning from about `2.0` to `0.98` values per row and improved its matching
  post-sort path only slightly (`28.00 ms` to `27.77 ms`), while two-way
  insertion was materially slower (`37.31 ms`).

This does not establish post-sort RLE as a material bottleneck on a
competitively important two-way case, so two-way intentionally retains the
complete-range detector.

The Slice 9 DSA gate is also closed: the repository contains no concrete DSA
API, library integration, device capability contract, or injectable runner.
Scalar span detection remains the portable implementation. DSA can be added
later without changing span semantics when those external facts exist.

## Pre-implementation inventory

The implementation work started from these files:

| File | Original responsibility | Required evolution |
|---|---|---|
| [`multicolumn_quicksort.hpp`](multicolumn_quicksort.hpp) | Sort one ascending key and replay its permutation across payload columns | Add order-aware active-range sorting and lexicographic range orchestration |
| [`cosort_network.hpp`](cosort_network.hpp) | Build and replay SIMD partition plans for ascending partition predicates | Make the before/after-pivot logic direction-aware |
| [`cosort_bitonic_leaf.hpp`](cosort_bitonic_leaf.hpp) | Sort short key ranges ascending and replay exchange masks | Support descending output without allowing padded payload into the valid range |
| [`benchmark_cosort_network.cpp`](benchmark_cosort_network.cpp) | Directly benchmark the partition replay step and sorting networks | Preserve its explicit ascending microbenchmark when partition templates gain an order parameter |
| [`benchmark_multicolumn_gbench.cpp`](benchmark_multicolumn_gbench.cpp) | Benchmark one key plus passive payload columns | Benchmark true lexicographic sort columns and mixed directions |
| [`benchmark_multicolumn_sort.cpp`](benchmark_multicolumn_sort.cpp) | Standalone one-key co-sort benchmark and correctness smoke test | Retain temporarily as a legacy active-key microbenchmark; do not make it a second multi-column correctness oracle |
| [`CMakeLists.txt`](CMakeLists.txt) | Build one pairwise quicksort test and the benchmark executables | Add a dedicated multi-column correctness target and thread linkage when parallel execution is introduced |

Important constraints in the original code:

- The project is compiled as C++17; the plan must not depend on `std::span`,
  `std::jthread`, or other C++20 facilities.
- `TslMultiColumnQuickSorter` stores `rng` and `column_count` as mutable object
  state. A single instance is not safe for concurrent tasks.
- `MaxColumns` bounds the payload pointer array, but the public entry point does
  not currently reject a larger runtime count.
- Pivot selection, scalar partition tails, insertion leaves, and bitonic leaves
  all assume ascending order.
- `TslPartitionMode::LESS_THAN` encodes an ascending comparison in its name and
  behavior.
- `sort_impl` recursively processes the smaller side and iterates over the
  larger side. This bounds stack depth, but function returns alone do not
  describe all completed quicksort fragments.
- The existing Google Benchmark `columns` parameter counts passive payload
  columns in addition to a separate key. The target benchmark must count actual
  lexicographic sort columns.
- There is no project-owned task queue or thread pool in `test-sort`; downloaded
  dependencies under `test-sort/build` are not implementation dependencies.

The pinned TSL release version in `CMakeLists.txt` is unrelated to the
multi-column design and remains preserved.

## Scope and non-goals

### In scope

- Homogeneous columns using the existing `DataType` template.
- Runtime column count up to `MaxColumns`.
- Per-column ascending and descending order.
- In-place, unstable lexicographic sorting.
- Scalar span-only equal-run discovery.
- Two-way and three-way complete-range variants.
- Three-way incremental discovery.
- A small project-owned C++17 task executor for benchmark/prototype use.
- Deterministic task-local pivot generation.
- Dedicated correctness tests and updated benchmark baselines.
- An optional detector seam for a later DSA implementation.

### Out of scope for the initial CPU baseline

- Heterogeneous column types.
- Null ordering, locale-aware ordering, or floating-point NaN policy.
- Stable ordering of rows equal in every sort column.
- A general-purpose repository thread-pool framework.
- Per-worker queues, work stealing, or any join/continuation mechanism that
  would let a task wait for a completion condition it does not own.
- Offloading quicksort partitions of a non-final column under post-sort
  discovery, which would require exactly such a join before its RLE scan.
- A mandatory DSA runtime or host-specific test dependency.
- Changing compiler, source-data, or generated TSL semantics.
- Refactoring unrelated sorting prototypes.

## Target data contracts

Add literal domain types near the multi-column sorter. Exact names may follow
local style, but their responsibilities should remain distinct.

```cpp
enum class TslSortOrder {
  ASCENDING,
  DESCENDING,
};

template <class DataType>
struct TslSortColumn {
  DataType * data;
  TslSortOrder order;
};

struct TslRunSpan {
  std::size_t begin;
  std::size_t end;  // half-open
};

struct TslColumnSortTask {
  std::size_t column;
  std::size_t begin;
  std::size_t end;  // half-open
};
```

The sort direction belongs to immutable column metadata. It need not be copied
into every task unless doing so materially simplifies an executor interface.

The primary target entry point should be explicit:

```cpp
void sort_columns(
  TslSortColumn<DataType> const * columns,
  std::size_t column_count,
  std::size_t row_count
);
```

Expose one named active-key entry point so tests and microbenchmarks can select
either direction without going through lexicographic orchestration:

```cpp
void sort_key(
  DataType * keys,
  DataType * const * payload_columns,
  std::size_t payload_count,
  std::size_t row_count,
  TslSortOrder order
);
```

Retain the current key-plus-payload `operator()` as an ascending adapter to
`sort_key` while the legacy microbenchmarks use it:

```cpp
void operator()(
  DataType * keys,
  DataType * const * payload_columns,
  std::size_t payload_count,
  std::size_t row_count
);
```

Both entry points should call one internal active-range sort. They must not
maintain separate partition or leaf implementations.

At lexicographic level `k`:

- `columns[k] + begin` is the active key;
- columns `k + 1 .. column_count - 1` are payloads;
- columns `0 .. k - 1` need not move because they are equal throughout the
  submitted prefix range;
- the active key must never also occur in the payload pointer array.

If non-key payload columns are added later, they must be passed separately and
must follow every permutation at every level. That extension is not required
for the initial all-columns-are-keys API.

Validate public arguments once:

- `column_count == 0` is a no-op;
- `row_count < 2` is a no-op;
- `column_count > MaxColumns` is rejected deterministically;
- every participating column pointer is non-null when `row_count != 0`.

## Internal comparison model

Avoid a runtime function call or direction branch inside each SIMD lane
operation. Dispatch once per active range:

```cpp
if (order == TslSortOrder::ASCENDING) {
  sort_active_range<TslSortOrder::ASCENDING>(...);
} else {
  sort_active_range<TslSortOrder::DESCENDING>(...);
}
```

Define direction-aware scalar and SIMD concepts in terms of "before pivot" and
"after pivot":

```text
ASCENDING:
    before(a, b) := a < b
    after(a, b)  := a > b

DESCENDING:
    before(a, b) := a > b
    after(a, b)  := a < b
```

Rename `TslPartitionMode::LESS_THAN` to a direction-neutral name such as
`BEFORE_PIVOT`. Keep `EQUAL_TO` for the second three-way partition. The
direction parameter must affect:

- median-of-three selection;
- bad-left and bad-right SIMD masks for the before-pivot partition;
- scalar `left_good` and `right_good` predicates;
- the after-pivot predicate in the equal partition;
- insertion-leaf comparisons;
- bitonic-network result orientation.

The equal comparison remains `==` for the integer types currently in scope.

The bitonic leaf always uses its proven ascending network and maximum-value
padding. For descending output it replays the recorded payload exchanges and
then reverses only the valid key and payload ranges. A direct minimum-padded
descending network is unsafe because the padding value is in-band: an unstable
network can move padded payload ahead of a valid minimum key. Unit tests cover
real zero and maximum values at short leaf lengths.

## Randomness and determinism

Move mutable quicksort state out of the sorter object before adding parallel
execution:

- keep only an immutable root seed in the sorter;
- pass `payload_count` explicitly to active-range helpers;
- pass an `std::mt19937_64 &` explicitly to pivot selection and recursive
  quicksort;
- construct one RNG per logical column-range task.

Derive a task seed from:

```text
root seed, column index, absolute begin, absolute end
```

Use a fixed documented integer-mixing function rather than `std::hash`, whose
cross-process reproducibility is not the intended contract. This makes pivot
selection independent of worker scheduling and makes serial and parallel
variants easier to compare.

## Equal-run detector contract

Implement the scalar baseline as a no-allocation callback scan:

```cpp
template <class DataType, class Emit>
void for_each_equal_run(
  DataType const * values,
  std::size_t begin,
  std::size_t end,
  Emit && emit
);
```

Required behavior:

- input is already sorted in either direction;
- emitted spans use absolute half-open indices;
- only spans with length greater than one are emitted;
- spans are maximal within `[begin, end)`;
- spans are emitted in increasing index order;
- empty, singleton, and all-unique ranges emit nothing;
- an all-equal range emits exactly `[begin, end)`.

The callback form supports direct serial recursion and task submission without
first allocating a vector. It also keeps the initial implementation small.

Do not introduce a general detector class hierarchy in the scalar slice. When
a second implementation such as DSA exists, add the smallest strategy boundary
that both implementations actually need. Preserve the span semantics above.

## Implementation slices

Each slice below should compile and pass its focused tests before the next
slice starts. Avoid combining the task executor, incremental quicksort
callbacks, and hardware detection in one change.

```text
correctness harness
        |
        v
direction-aware active-key sort
        |
        v
scalar equal-run spans
        |
        v
serial post-sort lexicographic baseline
        |
        +--------------------+
        v                    v
true multi-column       C++17 task executor
benchmark                    |
        |                    v
        +------------> parallel post-sort
                             |
                             v
                  incremental three-way
                             |
               +-------------+-------------+
               v                           v
      optional two-way merge       optional DSA detector
```

## Slice 1: establish dedicated multi-column correctness tests

### Goal

Create a test target that can prove direction-aware active-key sorting,
lexicographic sorting, run detection, and row preservation as later slices are
added.

### Files

- Add `test_multicolumn_sort.cpp`.
- Update `CMakeLists.txt`.

### Work

1. Add an executable named `test_multicolumn_sort`.
2. Link it to `tsl::tsl` and require C++17.
3. Register it with CTest separately from the existing `test_sort`.
4. Build reusable test helpers:
   - convert columnar input to a vector of row tuples;
   - compare two rows using a runtime direction vector;
   - check adjacent output rows for lexicographic order;
   - sort input row tuples with the scalar reference comparator;
   - compare the target output with reference tuples;
   - report the first differing row and column.
5. Keep exact output comparison valid for unstable sorting by comparing values,
   not origin indices. Rows equal in every key column are indistinguishable.
6. Add a scalar reference run detector used only by tests.

### Initial cases

- zero columns;
- zero rows and one row;
- one ascending column;
- one descending column;
- `(ASC, DESC, ASC)` using the worked example from the design document;
- all columns equal;
- all values unique in the first column;
- duplicates that reach every later column;
- duplicate tuples;
- sizes immediately below, at, and above the insertion and network thresholds;
- inputs at supported SIMD lane boundaries.

### Exit criteria

- The new target builds and runs in the existing `test-sort` build.
- It can test the legacy ascending active-key API before the new API exists.
- Reference helpers do not assume stability.
- The existing `test_sort` target remains unchanged and passing.

## Slice 2: make the active-range co-sort direction-aware and stateless

### Goal

Support ascending and descending order for one key range without yet adding
recursive multi-column orchestration.

### Files

- Update `multicolumn_quicksort.hpp`.
- Update `cosort_network.hpp`.
- Update `cosort_bitonic_leaf.hpp`.
- Update `benchmark_cosort_network.cpp` only if its direct partition call must
  name the ascending order explicitly.
- Extend `test_multicolumn_sort.cpp`.

### Work

1. Add `TslSortOrder`.
2. Refactor the active-range helpers to receive `payload_count` and RNG
   explicitly rather than reading mutable members.
3. Dispatch once into an order-specialized active-range quicksort.
4. Rename the before-pivot partition mode and update SIMD stitch planning.
5. Implement descending two-way and three-way scalar/SIMD partition predicates.
6. Make median-of-three use the active order.
7. Make insertion leaves use the active order.
8. Add descending bitonic-leaf output through valid-range co-reversal after
   ascending exchange replay.
9. Preserve recorded exchange-mask replay for every payload column.
10. Reject runtime payload counts greater than `MaxColumns`.
11. Add the named `sort_key` entry point with a runtime direction that dispatches
    to the two order-specialized implementations.
12. Keep the current public adapter ascending by default so the existing
    standalone and Google benchmarks still compile.
13. Preserve an ascending default or explicit order at the direct partition
    microbenchmark call site.

### Focused tests

Run every combination:

```text
partition: two-way, three-way
leaf:      insertion, network
order:     ascending, descending
type:      u32, u64 where the selected SIMD width is supported
```

For each combination verify:

- keys have the requested order;
- all payload columns replay one consistent row permutation;
- duplicate-heavy data;
- ascending, descending, nearly sorted, organ-pipe, uniform, and all-equal
  inputs;
- values equal to `0` and `max()` at short network lengths;
- sizes around the leaf threshold;
- multiple fixed seeds.

### Exit criteria

- No mutable `column_count` remains on a shareable sorter object.
- No shared RNG is required by an active-range sort.
- All partition and leaf combinations sort correctly in both directions.
- Existing ascending benchmarks still build through the compatibility adapter.

## Slice 3: add scalar span-only equal-run discovery

### Goal

Provide a fully tested, direction-independent source of maximal equal spans.

### Files

- Prefer adding a small `equal_runs.hpp` if the helper and tests would make
  `multicolumn_quicksort.hpp` harder to trace.
- Otherwise keep the helper next to the lexicographic orchestrator.
- Extend `test_multicolumn_sort.cpp`.

### Work

1. Add `TslRunSpan`.
2. Implement `for_each_equal_run`.
3. Keep the scan read-only and allocation-free.
4. Emit absolute offsets so a caller never has to guess whether a span is
   relative to a leaf or to the full column.
5. Document that the caller supplies a complete equal-prefix range.
6. Do not scan the last sort column because there is no child column to sort.

### Focused tests

- empty and singleton inputs;
- all unique;
- all equal;
- a run only at the beginning;
- a run only at the end;
- multiple separated runs;
- descending input;
- a nonzero `begin` offset;
- duplicate values at both boundaries;
- randomized differential tests against the test-only reference detector.

### Exit criteria

- Every emitted range is maximal, nontrivial, half-open, and ordered.
- The helper has no dependency on quicksort partition kind or sort direction.
- The callback may synchronously invoke work on later columns without mutating
  the column currently being scanned.

## Slice 4: implement serial post-sort lexicographic co-sort

### Goal

Deliver the first complete and correct multi-column algorithm. This is the
reference implementation for every optimized variant.

### Files

- Update `multicolumn_quicksort.hpp`.
- Extend `test_multicolumn_sort.cpp`.

### Work

1. Add `TslSortColumn<DataType>` and the `sort_columns` entry point.
2. Validate column count and pointers once at entry.
3. Implement a recursive or explicit-stack column-range driver:

   ```text
   sort active column over [begin, end)
   if another column exists:
       scan active column for maximal equal runs
       sort next column in every nontrivial run
   ```

4. Build the payload pointer array from later columns only.
5. Use absolute task coordinates to derive the active range's deterministic
   pivot seed.
6. Make the base cases explicit:
   - fewer than two rows;
   - no columns;
   - last column;
   - no nontrivial runs.
7. Keep complete-range RLE available for both partition kinds and both leaves.
8. Preserve the low-level ascending adapter without duplicating sorting logic.

### Correctness matrix

Test at least:

```text
partition:       two-way, three-way
leaf:            insertion, network
column count:    0, 1, 2, 3, MaxColumns
directions:      all ASC, all DESC, alternating, seeded random
row count:       0, 1, threshold boundaries, medium randomized
entropy:         unique first key, low entropy, all-equal prefixes,
                 duplicates through the final column
```

Add a specific adversarial case in which a two-way pivot's equal values start
the sorted right subtree. The post-sort scan must emit one combined run that
includes the pivot.

### Exit criteria

- Output matches the scalar lexicographic reference for the full matrix.
- Column tuples are preserved exactly as a multiset.
- No later-column sort escapes its parent equal-prefix range.
- Serial two-way and three-way paths use the same run detector.
- The result is deterministic for a fixed seed.

## Slice 5: convert the Google Benchmark to true multi-column semantics

### Goal

Measure the serial reference algorithm and retain an honest scalar baseline
before adding parallel or incremental optimizations.

### Files

- Update `benchmark_multicolumn_gbench.cpp`.
- Update benchmark comments and environment-variable documentation in the same
  file.
- Update only the title/comments of `benchmark_multicolumn_sort.cpp` as needed
  to identify it as the legacy one-key-plus-payload microbenchmark; do not add
  a second lexicographic implementation there.

### Work

1. Replace separate `pristine_keys` and passive payload interpretation with a
   vector of sort columns.
2. Interpret the benchmark's `cols` value as total sort columns:

   ```text
   old cols=2: one key + two passive columns
   new cols=2: two lexicographic sort columns
   ```

3. Use a default sweep such as `1,2,3,5`; retain `0` only as an explicitly named
   no-op measurement if it provides useful harness overhead data.
4. Add immutable direction patterns:
   - all ascending;
   - all descending;
   - alternating ascending/descending.
5. Include the direction pattern in benchmark names and counters.
6. Generate data per column rather than only for a separate key.
7. Add distributions that drive deeper column work:
   - uniform all columns;
   - low entropy all columns;
   - all-equal first column with random later columns;
   - low-entropy prefix with a high-entropy final column.
   Cap all-equal two-way cases at a small diagnostic size or exclude them from
   the default large sweep because the expected repeated `0`/`N-1` split is
   quadratic.
8. Rewrite the `std::sort` index baseline to compare complete row tuples using
   the same direction vector, then gather every column.
9. Change correctness checks from `std::is_sorted(first_column)` to the shared
   lexicographic invariant. Keep correctness work outside timed regions.
10. Correct memory-footprint and bytes-processed accounting to use exactly the
    total column count.
11. Register clear algorithm names, initially:
    - `std_lex_argsort`;
    - `post_2way_ins`;
    - `post_2way_net`;
    - `post_3way_ins`;
    - `post_3way_net`.
12. Keep resets, allocation, reference checks, and input generation outside the
    timed loop.

### Benchmark smoke checks

- Run a small filtered case for every direction pattern.
- Run low-entropy two- and three-column cases.
- Confirm the benchmark reports errors for lexicographically incorrect output.
- Confirm memory-cap filtering uses the new footprint.

### Exit criteria

- Every timed algorithm performs the same lexicographic operation.
- The scalar baseline and target use identical direction metadata.
- Benchmark labels no longer describe passive payload columns as sort columns.
- Serial performance data is available before later optimizations.

## Slice 6: add a C++17 task executor and parallel post-sort variant

### Goal

Parallelize independent next-column ranges without yet integrating run
discovery into quicksort completion.

### Files

- Add a focused header such as `multicolumn_sort_tasks.hpp`.
- Update `multicolumn_quicksort.hpp` only at the scheduling boundary.
- Update `test_multicolumn_sort.cpp`.
- Update `benchmark_multicolumn_gbench.cpp`.
- Update `CMakeLists.txt` to link `Threads::Threads` where needed.

### Executor boundary

The executor is owned by this prototype and should implement only the behavior
the sort needs:

```text
submit(column, begin, end)
worker pop/execute
child submission
wait until queued + running == 0
propagate first exception
orderly shutdown and join
```

Do not build a repository-wide general task framework.

### Work

1. Implement workers using C++17 `std::thread`.
2. Protect the queue and outstanding count with a mutex and condition variable.
3. Increment outstanding work before publishing a task.
4. Allow a running task to enqueue children before decrementing its own
   outstanding count.
5. Notify completion only when:

   ```text
   queue empty && running count zero && no task can enqueue another child
   ```

6. Publish parent writes before a child becomes visible through the synchronized
   queue.
7. Capture the first worker exception, stop accepting work, wake workers, join,
   and rethrow on the caller thread.
8. Use task-coordinate seeds; do not share an RNG.
9. Add configurable:
   - worker count;
   - minimum queued-run size;
   - minimum offloaded partition size, zero to keep every partition local.
10. Execute smaller runs inline on the current worker. Decline a small partition
    range instead, leaving it to the caller's own recursion.
11. Start with one queue task per range. Add vector batching only if measurement
    shows queue overhead is material.
12. Do not require queue order to match index order. Serve the newest task
    first so partition offload follows the serial visit order and the queue
    stays proportional to depth rather than to the input size.

### Concurrency invariants

- A next-column child is submitted only after the run it covers is final: under
  post-sort discovery after the parent column is completely sorted and RLE has
  produced a maximal run, and under incremental three-way discovery when a
  pivot-equal band or a completed leaf reports it.
- A quicksort partition range is submitted only when finishing it imposes no
  obligation on the complete range it came from: either no column follows, or
  incremental three-way discovery already reports self-contained bands and
  leaves. Post-sort discovery over a non-final column keeps its partitions on
  the worker that owns the range.
- Sibling tasks have disjoint half-open ranges.
- No task writes a preceding column with non-equal values.
- Sorter configuration and column metadata are immutable.
- All active-range mutable state is on a worker stack or in task-local storage.
- A worker never waits synchronously for its own child tasks.

### Focused tests

- worker counts `1`, `2`, and a bounded value derived from available hardware;
- queue threshold larger than all runs, forcing inline execution;
- threshold `2`, forcing many tasks;
- many small runs;
- one large run per level;
- tasks that complete in reverse discovery order;
- repeated fixed-seed runs with byte-identical output;
- injected task exception to verify shutdown and propagation;
- thread sanitizer build where available.

### Benchmark additions

Add:

- worker count;
- queue threshold;
- tasks submitted;
- tasks executed inline;
- maximum outstanding tasks.

Register parallel post-sort variants separately from serial ones.

### Exit criteria

- One-worker parallel output matches the serial output.
- Multi-worker output matches the scalar reference for all direction patterns.
- No correctness condition depends on queue insertion or completion order.
- Thread sanitizer reports no races in the focused stress suite when available.
- Small-run task overhead is visible and controllable through the threshold.

## Slice 7: add incremental three-way discovery

### Goal

Avoid a complete post-sort scan for three-way quicksort by:

- scanning each terminal leaf exactly once;
- submitting every nontrivial pivot-equal band directly;
- exposing next-column work before the whole active range finishes.

### Files

- Update `multicolumn_quicksort.hpp`.
- Potentially add a small completion-sink type next to the active-range sorter.
- Extend `test_multicolumn_sort.cpp`.
- Update `benchmark_multicolumn_gbench.cpp`.

### Partition boundary cleanup

Before wiring callbacks, make three-way bounds explicit and half-open:

```cpp
struct TslThreeWayBounds {
  std::size_t left_end;     // left:  [0, left_end)
  std::size_t equal_begin;  // equal: [equal_begin, equal_end)
  std::size_t equal_end;
  std::size_t right_begin;  // right: [right_begin, count)
};
```

For the current layout, `equal_begin == left_end` and
`right_begin == equal_end`. The named result removes the existing
inclusive-pivot arithmetic from callback code and prevents off-by-one task
ranges.

### Completion sink

Allow an active-range three-way quicksort to report two events:

```text
on_equal_band(absolute_begin, absolute_end)
on_sorted_leaf(absolute_begin, absolute_end)
```

Thread an absolute base index through `sort_impl` even when key and payload
pointers advance into subranges.

### Work

1. Emit an equal-band event immediately after a three-way partition has fixed
   that band, including singleton bands needed by structural coverage tests.
2. Have the scheduling sink ignore equal bands of length one.
3. Emit a leaf event only after insertion or network sorting has completed.
4. RLE each leaf through the scalar run detector.
5. Submit next-column work directly for equal bands.
6. Ensure no complete-range RLE runs after incremental decomposition.
7. Prove and comment the disjoint coverage:

   ```text
   terminal leaves + internal equal bands = the complete active range
   ```

8. Keep the existing smaller-side recursion/larger-side loop if absolute-range
   events can be emitted correctly. Replace it with explicit frames only if the
   event bookkeeping becomes ambiguous.
9. Implement both execution policies:
   - serial sink calls the next column directly;
   - parallel sink enqueues the next-column task.
10. Keep two-way quicksort on the post-sort detector in this slice.

### Focused tests

Instrument the completion sink in tests and verify:

- leaf ranges and equal bands never overlap;
- their union covers the original active range;
- each equal band contains only one value;
- neighboring leaf/equal-band boundaries compare strictly;
- every emitted next-column span matches a scalar full-range RLE span;
- no span is emitted twice;
- ascending and descending partitions;
- all-equal input creates one direct equal band and no leaf scan at an internal
  node;
- all-unique input scans terminal leaves and emits no next-column work;
- serial and parallel incremental outputs match post-sort outputs by value.

### Benchmark additions

Record:

- values examined by leaf RLE;
- number and total size of direct equal bands;
- time or counters for RLE work;
- child tasks exposed before active-range completion.

Register names such as:

- `incremental_3way_ins`;
- `incremental_3way_net`;
- parallel variants with worker/threshold counters.

### Exit criteria

- Incremental three-way output matches the post-sort three-way reference.
- Every active-range element belongs to exactly one scanned leaf or direct equal
  band.
- No parent or ancestor rescan creates duplicate work.
- Parallel next-column work writes only ranges no longer touched by the active
  quicksort.

## Slice 8: evaluate and optionally implement incremental two-way discovery

### Gate

Do not implement this slice merely for variant symmetry. Proceed only if:

- two-way partitioning is competitively important in measured distributions;
- post-sort RLE is a measurable bottleneck;
- three-way incremental sorting does not already meet the target.

Record the benchmark evidence that opens this slice.

### Goal

Emit complete runs from two-way quicksort fragments without treating sorted
fragment boundaries as run boundaries.

### Required model

Each completed fragment returns:

```text
absolute fragment bounds
open first run
open last run
closed interior runs already emitted
whether first and last describe the same all-equal fragment
```

When sorted fragments become adjacent:

- merge the left suffix and right prefix if their values are equal;
- otherwise close the touching runs;
- retain only the combined fragment's outer prefix and suffix;
- emit a run once, at the first point where both boundaries are closed;
- close the remaining root prefix/suffix at the active equal-prefix range
  boundaries.

For a two-way node:

```text
sorted left (< pivot) | pivot | sorted right (>= pivot)
```

the left suffix cannot equal the pivot, while the pivot must merge with the
equal prefix of the right summary.

### Work

1. Add a focused `TslFragmentRunSummary`; do not reuse `TslRunSpan` for open
   boundaries.
2. Use explicit post-order frames if the current tail-recursive loop cannot
   combine child summaries directly and clearly.
3. Keep emitted interior spans absolute and disjoint.
4. Support the same serial and queue sinks as three-way incremental discovery.
5. Retain the complete-range two-way implementation as an oracle and fallback.

### Focused tests

- the pivot/right example from the design document;
- an equal run crossing several nested right-subtree boundaries;
- equal runs touching the active range's beginning and end;
- an all-equal input;
- alternating short leaves and pivot singletons;
- randomized comparison of emitted spans with full-range scalar RLE;
- proof that every maximal run is emitted once and only once.

### Exit criteria

- Incremental and post-sort two-way span sets are identical.
- No open boundary run reaches the next-column scheduler.
- Complexity and benchmark results justify retaining the additional code.
- If the gate fails, document that two-way intentionally remains post-sort.

## Slice 9: add an optional hardware run-detector boundary

Superseded by `iaa-rle-offload-plan.md`, which instantiates this slice against
IAA (`qpl_op_scan_eq`, multiple engines per run) and extends it with
asynchronous completion so workers keep sorting while a scan is in flight. The
contract below still governs: identical spans to the scalar detector, an
explicitly gated build option, and no hardware dependency in ordinary builds.

### Gate

This slice requires a concrete DSA API, toolchain, and execution environment.
Do not infer those details or add a mandatory dependency before they are
available.

### Goal

Allow large complete sorted ranges to use DSA-backed span discovery while
keeping scalar detection available everywhere.

### Work

1. Extract the smallest common detector interface from the scalar and DSA
   implementations.
2. Keep output as maximal absolute `[begin, end)` spans.
3. Add an explicit build option such as `ENABLE_DSA_RLE`, defaulting to `OFF`.
4. Detect missing headers, libraries, device access, or queue availability and
   report a clear skip or fall back according to the selected policy.
5. Make the size threshold configurable.
6. Use scalar detection for short incremental leaves unless measurements show
   hardware offload is beneficial.
7. If DSA completion is asynchronous, keep the input range immutable until the
   detector signals completion and publish spans through the same dependency
   rules as the CPU detector.
8. Differentially compare every hardware span result with scalar RLE in tests.
9. Report offload submissions, fallbacks, bytes scanned, and completion latency
   in benchmarks.

### Exit criteria

- Ordinary builds and tests do not require DSA hardware or software.
- Hardware and scalar detectors emit identical spans.
- Offload failure cannot silently produce partial runs.
- Benchmarks identify the range-size crossover rather than assuming offload is
  always faster.

## Test architecture

Keep correctness ownership in `test_multicolumn_sort.cpp`, not in benchmark
setup code.

### Reference lexicographic comparator

For row indices `a` and `b`:

```text
for each column k:
    if column[k][a] == column[k][b]:
        continue
    if order[k] == ASC:
        return column[k][a] < column[k][b]
    return column[k][a] > column[k][b]
return false
```

Use it to sort a row-oriented copy of the input. Reconstruct row tuples from the
target's columnar output and compare them to the reference. This simultaneously
checks order, row preservation, duplicates, and counts.

### Deterministic randomized matrix

Use fixed seeds and cap case sizes so CTest remains fast. Generate:

- high-cardinality random values;
- low-entropy values with configurable cardinality per column;
- correlated prefixes;
- already lexicographically sorted data;
- reverse lexicographic data;
- nearly sorted data;
- organ-pipe patterns;
- all equal data.

On failure, print:

- seed;
- type;
- partition and leaf kind;
- directions;
- row and column count;
- first mismatching output position.

### Structural event probes

Expose completion events to tests through a sink rather than adding permanent
debug output. Test probes should collect:

- scanned leaf spans;
- direct equal bands;
- child task spans;
- task start/completion order;
- maximum outstanding work.

The production fast path should compile out unused probes.

## Validation commands

Run from the repository root unless noted.

### Configure

Reuse the existing configured build when possible:

```bash
cmake -S test-sort -B test-sort/build \
  -DCMAKE_CXX_COMPILER=/usr/bin/c++ \
  -DTSL_PROFILE=auto
```

If a local generated TSL tree is required, use a workspace-local output under
`tslctmp` and pass `TSL_LOCAL_SOURCE_DIR`; do not create new generated output in
the repository root.

### Focused build and tests

```bash
cmake --build test-sort/build --target \
  test_sort \
  test_multicolumn_sort \
  benchmark_multicolumn_sort \
  benchmark_multicolumn_gbench

ctest --test-dir test-sort/build \
  --output-on-failure \
  -R 'test_sort|test_multicolumn_sort'
```

### Benchmark smoke test

Use a narrow filter and short minimum time during development:

```bash
test-sort/build/benchmark_multicolumn_gbench \
  --benchmark_filter='(post|incremental).*cols=(2|3).*low_entropy' \
  --benchmark_min_time=0.01s
```

Adjust the exact filter to the final benchmark naming scheme.

### Sanitizers

Use separate workspace-local build directories:

```bash
cmake -S test-sort -B tslctmp/test-sort-asan \
  -DCMAKE_BUILD_TYPE=Debug \
  -DENABLE_GBENCH=OFF \
  -DENABLE_VQSORT_BENCHMARK=OFF \
  -DCMAKE_CXX_FLAGS='-fsanitize=address,undefined -fno-omit-frame-pointer'

cmake --build tslctmp/test-sort-asan --target test_multicolumn_sort
ctest --test-dir tslctmp/test-sort-asan --output-on-failure
```

For the task executor, add a separate ThreadSanitizer build where supported:

```bash
cmake -S test-sort -B tslctmp/test-sort-tsan \
  -DCMAKE_BUILD_TYPE=Debug \
  -DENABLE_GBENCH=OFF \
  -DENABLE_VQSORT_BENCHMARK=OFF \
  -DCMAKE_CXX_FLAGS='-fsanitize=thread -fno-omit-frame-pointer'

cmake --build tslctmp/test-sort-tsan --target test_multicolumn_sort
ctest --test-dir tslctmp/test-sort-tsan --output-on-failure
```

Treat unavailable sanitizer runtimes as an explicit validation gap rather than
a passing result.

### Repository checks

```bash
git diff --check
```

## Benchmark comparison matrix

Do not run the full Cartesian product by default. Define a small required matrix
and allow environment variables or Google Benchmark filters to expand it.

Required comparison dimensions:

| Dimension | Required values |
|---|---|
| Algorithm | scalar lexicographic argsort, serial post-sort, parallel post-sort, incremental three-way |
| Partition | two-way and three-way where applicable |
| Leaf | insertion and network |
| Type | `u32`, `u64` |
| SIMD lanes | currently registered fixed widths |
| Columns | `1`, `2`, `3`, `5` |
| Directions | all ASC, all DESC, alternating |
| Entropy | uniform, low entropy, all-equal prefix, correlated prefix |
| Size | L1, L2, half LLC, LLC, above LLC |
| Workers | `1` and representative multi-worker counts |

Primary questions:

1. What is the cost of one additional lexicographic column as prefix entropy
   changes?
2. Does three-way partitioning win when duplicate bands are large?
3. How much memory traffic does post-sort RLE add?
4. How many values does incremental three-way RLE avoid scanning?
5. At what run size does queueing beat inline execution?
6. Does exposing equal-band tasks early improve utilization?
7. Does the network leaf remain beneficial as the number of co-moved columns
   increases?
8. If DSA is added, what is its size crossover and interaction with fragmented
   incremental ranges?

## Risks and mitigations

| Risk | Consequence | Mitigation |
|---|---|---|
| Direction reaches some but not all comparison sites | Locally plausible but globally incorrect output | Compile-time order specialization and full partition/leaf matrix tests |
| Active key appears in payload pointers | Double swaps or corrupted keys | Build payloads from later columns only and assert non-aliasing in tests |
| Runtime column count exceeds `MaxColumns` | Stack-array overwrite | Validate once at the public boundary |
| Two-way fragment treated as a complete run | Incorrect later-column ordering across a pivot | Use full-range RLE until boundary summaries are proven |
| Inclusive/exclusive pivot arithmetic leaks into task spans | Missing or overlapping rows | Return named half-open partition bounds |
| Incremental regions overlap or leave gaps | Duplicate tasks or unsorted rows | Structural event probe validates disjoint union |
| Shared sorter RNG or payload count | Parallel data race and nondeterminism | Task-local RNG and explicit helper parameters |
| Parent finishes before publishing all children | Premature executor shutdown | Outstanding count includes running parents and is updated under one synchronization protocol |
| Queue order assumed to define output order | Scheduler-dependent behavior | Fixed disjoint ranges; randomized completion-order tests |
| Too many small tasks | Parallel slowdown | Inline threshold, then optional batching based on measurement |
| Large all-equal input with two-way partitioning | Expected quadratic benchmark runtime | Keep correctness coverage bounded and exclude pathological sizes from default performance sweeps |
| Network padding mishandled in descending mode | Sentinel values enter valid output incorrectly | Keep maximum padding, co-reverse only valid output, and test zero/maximum values at every short length |
| Benchmark still measures passive payloads | Misleading performance claims | Rebuild workload and scalar baseline around complete row comparison |
| DSA becomes a hidden host dependency | Non-reproducible builds/tests | Default-off option, capability checks, scalar fallback or explicit skip |
| Standalone and Google benchmarks duplicate correctness logic | Drift between two semantic definitions | Dedicated test target owns correctness; standalone target remains legacy-only |

## Completion criteria

The core CPU goal is complete when:

- serial post-sort multi-column sorting passes the full correctness matrix;
- both sort directions work in partition, insertion, and network code;
- two-way and three-way partitions produce the same lexicographic result;
- the Google Benchmark compares true multi-column algorithms;
- the parallel post-sort variant passes stress and race-focused validation;
- incremental three-way discovery emits a disjoint leaf/equal-band
  decomposition and matches the post-sort oracle;
- performance counters distinguish RLE work, direct equal bands, and task
  overhead;
- all relevant CTest targets pass;
- `git diff --check` passes;
- documentation is updated if implementation decisions differ from
  `multi-column-sort.md`.

Incremental two-way discovery is complete only if its benchmark gate opens and
its emitted spans exactly match full-range RLE. DSA support is complete only
when a concrete optional integration passes scalar differential tests on
available hardware; neither extension blocks completion of the CPU core.

## Recommended change sequence

Keep review units aligned with the slices:

1. Tests and reference helpers.
2. Direction-aware stateless active-range co-sort.
3. Scalar equal-run detector.
4. Serial post-sort lexicographic orchestration.
5. True multi-column Google Benchmark.
6. C++17 task executor and parallel post-sort scheduling.
7. Incremental three-way completion events.
8. Evidence-gated incremental two-way summaries.
9. Environment-gated DSA detector.

Do not start a later optimization while the preceding reference path has
unresolved correctness failures.
