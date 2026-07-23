# Multi-column co-sort with equal-run discovery

## Purpose and scope

This document describes the target multi-column co-sort algorithm built around
the prototype in:

- [`multicolumn_quicksort.hpp`](multicolumn_quicksort.hpp)
- [`benchmark_multicolumn_gbench.cpp`](benchmark_multicolumn_gbench.cpp)

The current prototype sorts one key column in ascending order and applies every
key exchange to a runtime number of payload columns. The target algorithm makes
each column a sort key with its own direction and produces a lexicographic
ordering across all columns.

For example, given these directions:

```text
column 0: ascending
column 1: descending
column 2: ascending
```

the result is ordered by column 0 first. Rows with equal column-0 values are
ordered by column 1. Rows that are also equal in column 1 are ordered by column
2. A column after the first one is therefore sorted only within ranges that are
equal in every preceding column; it is not expected to be globally sorted
independently of those columns.

Run-length encoding (RLE) discovers those equal ranges. The algorithm does not
need encoded values or run counts as persistent output. It only needs the
half-open spans `[begin, end)` of runs whose length is greater than one.

## Terms

**Active column**
: The column currently used as the quicksort key.

**Payload columns**
: Columns that must undergo exactly the same permutation as the active column
  so that values belonging to one logical row remain together.

**Prefix**
: The columns preceding the active column. All prefix values are equal inside
  a range submitted to the active column.

**Equal run**
: A maximal contiguous range, within the current equal-prefix range, in which
  all values of the active column compare equal. "Maximal" matters: two
  adjacent pieces of the same value are one run, not two independent runs.

**Closed run**
: An equal run whose boundaries are known. Either it reaches the boundary of
  the range being sorted, or the value immediately outside it is known to be
  different. Only a closed run may be submitted to the next column.

**Leaf**
: A small quicksort subrange handled by the insertion-sort or bitonic-network
  leaf implementation.

**Co-sort**
: Sort one key column while applying its permutation to every payload column.

## Required result and invariants

Let `order[k]` be the direction of column `k`. The final rows must satisfy the
lexicographic comparison:

```text
compare row a with row b:
    for k = 0 .. column_count - 1:
        if a[k] and b[k] are equal:
            continue
        return a[k] comes before b[k] according to order[k]
    return equivalent
```

The implementation must preserve these invariants:

1. **Lexicographic ordering**: a later column breaks ties only inside an equal
   run of the complete preceding prefix.
2. **Row integrity**: whenever the active key moves, all values that belong to
   that row and are still represented as payload move with it.
3. **Maximal run spans**: a range sent to the next column covers the complete
   equal run, including equal values that meet at quicksort partition or leaf
   boundaries.
4. **Range isolation**: a next-column sort writes only inside the run that
   created it.
5. **Dependency ordering**: a child range is created only after its active
   parent column is completely ordered in that range, or after quicksort has
   otherwise proved that the child range is final and will not be touched
   again.
6. **Direction-independent equality**: ascending versus descending changes
   which unequal value comes first, but does not change which values belong to
   the same run.

The quicksort is not required to be stable. Rows equal in every sort column may
appear in any order unless stability is added as a separate requirement.

## Worked lexicographic example

Consider six logical rows and the directions `(ASC, DESC, ASC)`:

```text
row     column 0     column 1     column 2
 r0         2            1            7
 r1         1            3            9
 r2         1            3            4
 r3         1            2            8
 r4         2            1            5
 r5         1            2            6
```

First, column 0 is co-sorted ascending. The other columns and the row identity
follow the same permutation:

```text
range          rows after column-0 sort

[0, 4)         r1  r2  r3  r5       column 0 == 1
[4, 6)         r0  r4               column 0 == 2
```

RLE of column 0 returns the two nontrivial runs `[0, 4)` and `[4, 6)`. Column 1
is sorted descending independently inside each range:

```text
column-0 run   rows after column-1 sort       column-1 runs

[0, 4)         r1  r2 | r3  r5               [0, 2): 3, [2, 4): 2
[4, 6)         r0  r4                         [4, 6): 1
```

The three column-1 runs are then sorted by column 2 ascending:

```text
[0, 2)         r2  r1       column 2: 4, 9
[2, 4)         r5  r3       column 2: 6, 8
[4, 6)         r4  r0       column 2: 5, 7
```

The final order is:

```text
row     column 0 ASC     column 1 DESC     column 2 ASC
 r2           1                3                 4
 r1           1                3                 9
 r5           1                2                 6
 r3           1                2                 8
 r4           2                1                 5
 r0           2                1                 7
```

The hierarchy of work is:

```text
column 0, [0, 6)
|
+-- value 1, [0, 4)  --> column 1 DESC
|   |
|   +-- value 3, [0, 2) --> column 2 ASC
|   `-- value 2, [2, 4) --> column 2 ASC
|
`-- value 2, [4, 6)  --> column 1 DESC
    |
    `-- value 1, [4, 6) --> column 2 ASC
```

Every node at one column owns a disjoint range. Its children are the equal runs
found in that range and use the next column.

## Core recursive algorithm

The simplest formulation sorts a complete active range, discovers all equal
runs, and recursively sorts the next column:

```text
multi_column_sort(columns, directions, column, begin, end):
    if end - begin < 2:
        return

    co_quicksort(
        key = columns[column][begin:end],
        payloads = row-associated columns other than the active key,
        direction = directions[column]
    )

    if column + 1 == columns.size:
        return

    for [run_begin, run_end) in equal_runs(columns[column], begin, end):
        if run_end - run_begin > 1:
            multi_column_sort(
                columns,
                directions,
                column + 1,
                run_begin,
                run_end
            )
```

The initial call is:

```text
multi_column_sort(columns, directions, 0, 0, row_count)
```

At recursion level `k`, every preceding column `0 .. k-1` is constant in the
submitted range. Sorting column `k` therefore cannot disturb the established
prefix ordering.

The active key must not also appear as a payload pointer. At minimum, every
later sort column must move with the active key. Earlier sort columns may be
omitted from the payload set because they are equal throughout the current
range. Any associated non-key payload, such as a row identifier, must continue
to move even though it will never become an active sort key.

## Co-sort mechanics in the current prototype

The current quicksort already provides the central row-permutation mechanism:

1. Choose and move a pivot in the key column.
2. Derive partition masks and a compress/expand stitch from key values.
3. Replay that partition plan on each payload column.
4. Recurse into the resulting key ranges.
5. Sort small ranges with either a scalar insertion leaf or a SIMD bitonic
   network leaf.

The bitonic leaf similarly records the key exchange masks and replays those
exchanges on one payload column at a time. This keeps the runtime column count
from turning into simultaneous register pressure.

The target algorithm reuses this operation at every column level. For a task on
column `k`, `columns[k]` becomes the key and the other relevant row columns
become payloads. The resulting permutation is local to the task's
`[begin, end)` range.

## Sort directions

Each column has one direction:

```text
comes_before(a, b, ASC)  := a < b
comes_before(a, b, DESC) := a > b
```

That direction must be applied consistently throughout the active quicksort:

- median-of-three pivot selection;
- SIMD and scalar partition predicates;
- insertion-leaf comparisons;
- bitonic-network compare/exchange decisions;
- padding sentinels used by short network leaves;
- reference validation in tests and benchmarks.

For three-way partitioning, the logical regions are:

```text
ASC:   values < pivot | values == pivot | values > pivot
DESC:  values > pivot | values == pivot | values < pivot
```

RLE uses equality only, so the same run discovery works for both directions.
For the integer types used by the prototype, equality can be direct `==`. If
the algorithm later accepts types with a custom ordering, run equality must
use the ordering's equivalence relation rather than an unrelated equality
definition.

## Run discovery output

A run-discovery operation consumes an already sorted range and emits only
nontrivial equal spans:

```text
input values:  1 1 1 2 3 3 4 5 5 5
indices:       0 1 2 3 4 5 6 7 8 9

output spans:
    [0, 3)     value 1
    [4, 6)     value 3
    [7, 10)    value 5
```

Singletons are discarded because sorting one row by another column cannot
change the result. Values and counts need not be retained after the span has
been constructed.

This narrow interface permits different implementations:

- a scalar transition scan;
- a SIMD comparison-and-mask scan;
- a DSA-backed or other hardware-accelerated run detector;
- an asynchronous detector that emits spans into the task system.

The sort algorithm should consume spans without depending on how they were
produced. A hardware implementation may also need a minimum range size so that
offload setup does not dominate short scans.

## Variant axis 1: when equal runs are discovered

### Variant A: post-sort RLE of the complete active range

This is the direct recursive algorithm shown above:

```text
co-sort complete range by column k
                |
                v
RLE complete sorted range
                |
                v
sort each nontrivial run by column k + 1
```

Example:

```text
before column 0:
    3 1 2 1 3 2 1

after complete column-0 quicksort:
    1 1 1 2 2 3 3

RLE:
    [0, 3) [3, 5) [5, 7)
```

Why use this variant:

- It is structurally simple.
- It works unchanged with two-way and three-way quicksort partitioning.
- Every run is maximal within the current lexicographic-prefix range.
- Run discovery is independent of quicksort's recursion and tail-recursion
  strategy.
- Large contiguous scans may be better suited to hardware offload.
- It provides a clear correctness baseline for more integrated variants.

Its cost is one additional linear pass over every range that reaches a column.
At a fixed column level those ranges are disjoint, so their total scanned
length is at most the original row count. Across `C` columns, run discovery is
therefore at most `O(C * N)`, and often less because singleton groups stop
recursing.

The main performance risk is reading a range again after quicksort has stopped
touching it, potentially after its data has left the closest caches.

### Variant B: incremental discovery from completed quicksort regions

This variant integrates run discovery with quicksort completion. Once a region
of the active column is fully sorted and quicksort will not modify it again,
the algorithm discovers or directly identifies equal runs in that region and
starts next-column work early.

A conceptual three-way quicksort tree is:

```text
                         [current range]
                    /          |          \
               Left 1       Equal 1      Right 1
              (< p1)         (== p1)      (> p1)
             /   |   \                    /   |   \
        Left 2 Equal 2 Right 2       Left 3 Equal 3 Right 3
```

For descending order, "left" means values that come before the pivot, so the
inequalities reverse while the equal regions remain equal.

Completed leaves whose outer boundaries are known to be closed can be scanned
while their data is still hot. The three-way decomposition described below
provides those boundaries; the two-way case needs the additional boundary
handling described later.

```text
leaf sorted
    |
    +-- scan leaf for equal runs
    |
    `-- submit those runs to column k + 1
```

Three-way equal bands need no RLE:

```text
partition complete
    |
    +-- left child: sort recursively
    |
    +-- equal band: already one complete run
    |       `-- if length > 1, submit directly to column k + 1
    |
    `-- right child: sort recursively
```

An equal band is final as soon as partitioning has placed every pivot-equal
value into it. Subsequent quicksort operations are restricted to the disjoint
left and right ranges, so next-column work on the equal band may begin without
waiting for the whole current range.

Why use this variant:

- It can discover runs while completed data is still cache-resident.
- Three-way pivot-equal bands bypass RLE entirely.
- It exposes next-column tasks before the current column has finished globally.
- Run discovery, sorting, and task execution can overlap.

The implementation must avoid scanning overlapping completed regions. A useful
three-way decomposition is:

```text
all terminal leaves + all internal pivot-equal bands = disjoint full output
```

RLE scans each terminal leaf once, and each internal equal band is emitted
directly once. A terminal leaf boundary is either the boundary of the current
equal-prefix range or is separated from neighboring output by an ancestor's
strict pivot boundary, so a leaf run cannot silently continue into another
piece of this decomposition. Scanning every leaf, then every parent, then every
ancestor would repeat work and generate duplicate child tasks.

The current prototype's `sort_impl` recursively handles the smaller partition
and iterates over the larger partition to bound stack depth. Incremental
completion therefore needs either explicit quicksort frames, completion
callbacks, or equivalent bookkeeping; a C++ function return alone does not
identify every logically completed region.

## Variant axis 2: two-way versus three-way partitioning

### Three-way partitioning

A three-way partition creates:

```text
values before pivot | values equal to pivot | values after pivot
```

For ascending order:

```text
        < pivot      |      == pivot      |      > pivot
```

For descending order:

```text
        > pivot      |      == pivot      |      < pivot
```

The equal band is maximal for that pivot inside the partitioned range. Its
neighbors are strictly different, so it is a closed run and can immediately
become a next-column task.

Three-way partitioning is particularly attractive for low-entropy data:

- a large duplicate band is removed from further quicksort recursion;
- the band does not need an RLE scan;
- it creates a potentially substantial next-column task early;
- recursive subranges are separated from the equal band by strict
  inequalities.

Terminal leaves still need RLE because a leaf may contain several different
values and several equal runs.

### Two-way partitioning

A two-way quicksort partition has the logical form:

```text
values before pivot | pivot | values not before pivot
```

For ascending order this is:

```text
        < pivot      | pivot |       >= pivot
```

The recursively sorted right range may begin with more values equal to the
pivot:

```text
sorted left     pivot     sorted right
    1             2          2 2 3
                              ^

complete value-2 run:          [pivot, first value > 2)
```

The right range is sorted, but its leading value-2 run is not a complete run by
itself. The pivot belongs to it. Sorting the next column in only the right-hand
piece can produce the wrong lexicographic result:

```text
column 0:       2 | 2 2
column 1:       9 | 1 2

sorting only the right piece by column 1 leaves:
                9 | 1 2       not ordered across the complete column-0 run
```

This distinction is important:

```text
"the fragment is sorted" does not imply "its boundary run is complete"
```

Two-way partitioning is fully compatible with complete-range post-sort RLE.
After the top-level quicksort for the current prefix range finishes, scanning
that whole range sees every pivot and every adjacent equal value.

Incremental two-way discovery needs additional boundary handling. Two possible
designs are:

1. **Defer open boundary runs.** A completed fragment emits only closed
   interior runs. It returns descriptions of its first and last runs to its
   parent. When adjacent sorted fragments are joined, equal boundary
   descriptions are merged. The root range closes any remaining boundary run.
2. **Use a later enclosing scan.** Do not emit runs from fragments whose
   boundaries may be open. Scan a completed enclosing range once its boundaries
   are proven, accepting less early overlap.

A generic fragment summary can be visualized as:

```text
completed sorted fragment

| open/unknown prefix | closed interior runs | open/unknown suffix |
```

When two adjacent fragments are combined:

```text
left suffix value == right prefix value
        -> merge into one boundary run

left suffix value != right prefix value
        -> the touching boundaries close each other
```

For the two-way pivot boundary specifically, the left range is strictly before
the pivot and cannot join the pivot run. The pivot must be merged with the
equal prefix of the sorted right range. Open-boundary propagation is required
recursively because that merged run may itself touch an inherited partition
boundary.

This bookkeeping is the main reason three-way partitioning is the cleaner
incremental-RLE variant.

## Variant axis 3: serial versus parallel execution

Run discovery and partition choice are independent of how child ranges are
executed.

### Serial execution

The serial algorithm directly calls the next column for each equal run:

```text
sort column k in [begin, end)
for each equal run in increasing index order:
    sort column k + 1 in that run
```

Advantages:

- simplest control flow and ownership;
- no queue, synchronization, or termination protocol;
- deterministic traversal order;
- best baseline for correctness and performance comparisons;
- avoids task overhead for small runs.

The order in which disjoint sibling runs are processed does not affect the
final values. Increasing index order is nevertheless natural and usually
provides predictable locality.

### Parallel task-queue execution

A logical work item is:

```text
SortTask {
    column_index,
    begin,
    end,
    direction
}
```

The direction may instead be read from immutable column metadata using
`column_index`. A queue entry may contain one descriptor or a small vector of
`(column_index, begin, end, direction)` descriptors to amortize queue
overhead.

A worker performs:

```text
worker(task):
    co-sort task range by task.column_index

    if another column exists:
        discover complete equal runs
        enqueue one child task per nontrivial run

    mark task complete
```

The dependency graph is:

```text
parent sort on column k
        |
        +-- child run A on column k + 1
        +-- child run B on column k + 1
        `-- child run C on column k + 1
```

Sibling tasks are safe to execute concurrently because their index ranges are
disjoint. With incremental three-way quicksort, an equal-band child may also
run concurrently with ongoing quicksort work in the disjoint left and right
subranges.

Queue insertion order is not a correctness requirement. Each task writes to a
fixed range determined by the preceding column, so a task for a later range may
finish before a task for an earlier range without changing output order:

```text
fixed output:    [ run A ][ run B ][ run C ]
execution:          C         A         B       is still correct
```

Preserving discovery order can still help reproducible traces and locality.
The true correctness requirements are:

- enqueue a child only after the parent has finalized that exact range;
- never enqueue partial or overlapping equal runs;
- publish parent writes before another worker consumes the child task;
- keep all mutable quicksort state task-local or synchronized;
- count both queued and running work so completion is detected only when no
  task can create another task.

Workers should not block waiting for their own child tasks; they should enqueue
children and return to the pool. A global outstanding-task count or equivalent
structured task-group mechanism can provide termination.

The current sorter object contains mutable `rng` and `column_count` members.
Sharing one instance across workers would introduce data races. Parallel work
needs task-local sorter state, immutable column metadata, and either
deterministic task-local pivot seeds or an explicitly synchronized random
source.

Task creation should normally have a size threshold. Very small equal runs are
better processed serially by the current worker, while larger runs provide
enough work to amortize queue and synchronization costs.

## Variant axis 4: leaf implementation

The existing leaf choices remain orthogonal to run discovery:

### Insertion leaf

- simple scalar comparisons and row moves;
- naturally supports arbitrary short lengths;
- direction support requires changing the insertion comparison;
- RLE can scan the sorted leaf immediately afterward.

### Bitonic-network leaf

- sorts a fixed-capacity padded key block with SIMD operations;
- records exchange masks and replays them on payload columns;
- direction support affects comparator decisions and the padding sentinel;
- RLE can scan the valid, unpadded portion after the leaf completes.

The leaf threshold determines the granularity of incremental RLE. Smaller
leaves expose work earlier but create more fragments and more scheduling or
boundary-management overhead. Larger network leaves provide fewer, longer RLE
scans.

## Complete variant matrix

The principal choices can be combined as follows:

| Run discovery | Partition | Execution | Main property |
|---|---|---|---|
| Complete-range post-sort RLE | Two-way | Serial | Simplest correctness baseline |
| Complete-range post-sort RLE | Three-way | Serial | Simple and duplicate-friendly sort |
| Complete-range post-sort RLE | Two-way or three-way | Parallel | Parallelism begins after each complete active-range sort |
| Incremental | Three-way | Serial | Scan leaves and directly process equal bands |
| Incremental | Three-way | Parallel | Earliest safe overlap of columns and disjoint partitions |
| Incremental with boundary summaries | Two-way | Serial or parallel | Preserves two-way partitioning at higher bookkeeping cost |

Insertion and network leaves can be benchmarked with every applicable row.

## Cost model

For a prefix group of size `m`, quicksorting the next column costs approximately
`O(m log m)` in the ordinary case. At column `k`, all prefix groups are
disjoint. The total sort work is:

```text
sum over columns k:
    sum over equal-prefix groups g at column k:
        sort_cost(size(g))
```

The data distribution strongly affects this cost:

- **High-cardinality first column**: most runs are singletons, so later columns
  do little or no work.
- **Low-entropy first column**: large runs reach later columns, producing more
  sorting work and more useful parallel tasks.
- **All values equal in preceding columns**: every later column may sort almost
  the full input.

Complete-range RLE scans at most `N` elements per column level because ranges at
that level are disjoint. Incremental three-way discovery may scan fewer values
because internal pivot-equal bands are already known, and it can improve cache
locality. It does not automatically reduce work if completed regions are
rescanned at multiple tree levels; the regions selected for RLE must form a
non-overlapping decomposition.

Parallel speedup is bounded by the number and size of independent equal runs.
A data set with almost no duplicates creates little next-column work. A data
set with one enormous run exposes only one task until its next-column quicksort
partitions or produces multiple runs. Task thresholds, RLE/offload thresholds,
and the quicksort's own parallel granularity should therefore be measured
rather than fixed from the column count alone.

## Edge cases

The algorithm should define these cases explicitly:

- zero rows or one row: return without sorting or RLE;
- zero columns: no work;
- one column: co-sort once; no RLE is required unless spans are requested for
  another consumer;
- singleton run: do not create a next-column task;
- all values equal: the complete range proceeds to the next column;
- all columns equal: final row order is unspecified unless stability is added;
- mixed directions: direction changes at each column task;
- range exactly at, below, or above the leaf threshold;
- number of columns at the compiled `MaxColumns` limit;
- a run crossing a two-way pivot or leaf boundary;
- parallel tasks that finish in a different order from discovery order.

For future non-integer data, special values such as floating-point NaNs require
an explicit total-order and equality policy before RLE can be correct.

## Correctness validation

Checking only that column 0 is sorted is insufficient. Validation should
include:

1. **Lexicographic reference comparison.** Copy the input rows, sort the copy
   with a scalar comparator using the same per-column directions, and compare
   key tuples with the co-sort result.
2. **Row-permutation preservation.** Include a unique row identifier or
   reconstructible payload and verify that no row is split, duplicated, or
   lost.
3. **Run maximality.** Compare emitted spans with a scalar full-range RLE,
   especially at leaf and partition boundaries.
4. **Two-way boundary adversaries.** Force duplicates equal to a pivot into the
   right subtree and verify that the pivot joins the same next-column task.
5. **Direction combinations.** Exercise all-ascending, all-descending, and
   alternating directions.
6. **Sizes around structural boundaries.** Cover zero, one, SIMD lane widths,
   leaf capacity, and values immediately around each threshold.
7. **Distributions.** Include uniform random, ascending, descending, nearly
   sorted, low entropy, organ-pipe, all equal, and duplicate-heavy boundary
   cases.
8. **Parallel stress.** Vary worker count and scheduling order and, where
   available, run a data-race detector.

Exact row order should not be compared for tuples equal in every sort column
unless stability becomes part of the contract.

## Benchmarking the variants

The benchmark should distinguish the number of lexicographic sort columns from
the old interpretation of one key plus a number of passive payload columns. A
benchmark case needs:

- column count;
- direction per column or a named direction pattern;
- partition kind;
- leaf kind;
- run-discovery strategy;
- serial or task-pool execution;
- element count and cache-size class;
- data distribution and per-column entropy;
- worker count and task threshold;
- RLE implementation and hardware-offload threshold.

Useful measurements include:

- total time and time per row;
- quicksort time versus run-discovery time;
- values examined by RLE;
- equal bands emitted without scanning;
- tasks created and tasks executed inline;
- task-size distribution;
- maximum outstanding tasks;
- queue and synchronization overhead;
- speedup over scalar lexicographic row/index sorting.

Low-entropy data is essential because it exercises the behavior that
differentiates a true multi-column sort from the current one-key co-sort.

## Suggested implementation progression

A staged implementation keeps correctness evidence available while optimizing:

1. Add per-column metadata and mixed-direction comparison support to every
   quicksort and leaf operation.
2. Implement serial complete-range post-sort RLE and compare against a scalar
   lexicographic reference.
3. Add task-queue execution using the same complete-range span producer.
4. Add incremental three-way discovery using disjoint leaf scans and direct
   equal-band tasks.
5. Add incremental two-way boundary summaries only if benchmarks justify the
   extra complexity.
6. Introduce SIMD or DSA-backed span discovery behind the same run-span
   interface and benchmark its range-size threshold.

This order leaves the post-sort serial algorithm as a reference path for
testing every more aggressive variant.
