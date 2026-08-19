# Multi-column co-sort benchmark: working draft

> **Superseded.** [`benchmark-final.md`](benchmark-final.md) is the authoritative
> plan. This file is the working draft it was distilled from, kept for the
> reasoning and the measurements behind those decisions. Where the two disagree,
> the final document wins.

Working document for the benchmark setup: what
[`benchmark_multicolumn_gbench.cpp`](../benchmark_multicolumn_gbench.cpp)
registers today, what the variant space actually is, and how to measure it without
running a product nobody can run.

## Status

The sections below were written in discussion order, so two of them are superseded
by later ones. Read this table first; it is the authoritative state.

| item | state | where |
|---|---|---|
| Variant inventory, 17 registered | current | [Variants](#variants) |
| `style=` in every benchmark name | **implemented** | [Naming hazard](#naming-hazard--fixed) |
| Variant space is 108 + baseline, not 19 | current — **supersedes** "Variants stay at 19" | [Correction](#correction-register-width-and-code-style-are-variants-not-axes) |
| Detector is "not a variant, a second binary" | **superseded** by the `rle=` axis proposal | [Run-detector backends](#run-detector-backends-a-second-binary-not-a-variant) |
| Two-way deep-parallel variants | proposed, not implemented | [rows 18-19](#variants) |
| `rle=` as an axis of the main binary | proposed, not implemented | [Proposal](#proposal-rle-as-a-first-class-axis) |
| Staged funnel with per-family predicates | **implemented** in `cosort_bench` | [Harness](#harness-cosort_bench) |
| `memcmp` oracle against the reference image | **implemented**, with a negative control | [Harness](#harness-cosort_bench) |
| Dataset source from `TslDatasetSource` | **implemented** | [Harness](#harness-cosort_bench) |
| Style axis in the variant model | **implemented**; the clang family needs clang 22 | [Harness](#harness-cosort_bench) |
| Style/width experiment E2 | runnable as `COSORT_STAGE=attribute`, intrinsics half only | [Harness](#harness-cosort_bench) |
| `rle=` as an axis of the main binary | `rle=scalar` emitted; accelerator backends not wired | [Proposal](#proposal-rle-as-a-first-class-axis) |

`cosort_bench` implements the four decisions; the original
`benchmark_multicolumn_gbench` is untouched and still registers its flat 16,896
cases with the order-invariant check.

## Harness: `cosort_bench`

```bash
cmake -S test-sort -B <build> -DCMAKE_CXX_COMPILER=clang++ -DCMAKE_BUILD_TYPE=Release
cmake --build <build> --target cosort_bench
COSORT_STAGE=screen <build>/cosort_bench --benchmark_min_time=0.05s
```

| file | role |
|---|---|
| `cosort_plan.hpp` | variant model (execution × discovery × partition × leaf × style × width), stable `algo` IDs, per-stage admission predicates, drop-reason log |
| `cosort_case.hpp` | cache detection and size levels, dataset selection from the catalog, and one measured case: pristine handle, working copy, reference handle, `memcmp` oracle |
| `cosort_bench.cpp` | style/width to TSL vector type, environment parsing, registration, counters, `main` |

Measured registration counts, with what each stage drops:

| stage | cases | drops reported |
|---|---|---|
| `screen` | 216 | 12 quadratic two-way |
| `tune` | 70 | 6 out of variant set, 8 quadratic two-way |
| `characterize` | 4,416 | 144 quadratic two-way (unrestricted; set `COSORT_VARIANTS`) |
| `attribute` | 66 | 84 out of variant set, 12 style unavailable, 12 quadratic two-way |

`screen` is 19 variants × 6 shapes × 2 sizes = 228 less the 12 two-way cases on a
low-cardinality key, exactly as planned. Every drop is counted by reason and
printed at startup, so a narrowed run cannot read as a complete one.

The oracle was checked against three cases: a correct sort verifies clean, a
single flipped bit is reported as `column 2, row 4242`, and a plausible-but-wrong
result — sorted by the first column only — is reported at `column 1, row 0`.

## Naming scheme

A target name encodes four independent choices:

```text
[execution_]discovery_partition_leaf

execution   (none)          serial: next-column ranges recurse inline
            parallel_       next-column ranges are queued to the task executor
            deep_parallel_  additionally queues quicksort partition ranges
discovery   post            scan a complete sorted active range for equal runs
            incremental     take equal bands and completed leaves from the
                            three-way partition as they are finalized
partition   2way | 3way     quicksort partitioning policy
leaf        ins | net       scalar insertion or SIMD bitonic-network leaf
```

The full benchmark name adds the configuration:

```text
deep_parallel_incremental_3way_net/u32/style=intr/lanes=16/dist=low_entropy/
order=alternating/cols=3/size=L2/workers=4/threshold=4096/
partitions=16384/real_time
```

`workers=`/`threshold=` appear only for parallel targets, `partitions=` only for
`deep_parallel_` targets. `style=` is always present; see
[Naming hazard](#naming-hazard--fixed).

## Variants

`algo` is the numeric ID published as a Google Benchmark counter and consumed by
`visualize_multicolumn_bench.py`. "Registrations" is how many benchmark cases the
variant contributes under the default matrix.

| # | variant | algo | discovery | partition | leaf | execution | registrations | status |
|---|---|---|---|---|---|---|---|---|
| 1 | `std_lex_argsort` | 0 | — | — | — | scalar baseline | 384 | registered |
| 2 | `post_2way_ins` | 1 | post | 2-way | insertion | serial | 672 | registered |
| 3 | `post_2way_net` | 3 | post | 2-way | network | serial | 672 | registered |
| 4 | `post_3way_ins` | 2 | post | 3-way | insertion | serial | 1152 | registered |
| 5 | `post_3way_net` | 4 | post | 3-way | network | serial | 1152 | registered |
| 6 | `incremental_3way_ins` | 5 | incremental | 3-way | insertion | serial | 1152 | registered |
| 7 | `incremental_3way_net` | 6 | incremental | 3-way | network | serial | 1152 | registered |
| 8 | `parallel_post_2way_ins` | 7 | post | 2-way | insertion | parallel | 672 | registered |
| 9 | `parallel_post_2way_net` | 9 | post | 2-way | network | parallel | 672 | registered |
| 10 | `parallel_post_3way_ins` | 8 | post | 3-way | insertion | parallel | 1152 | registered |
| 11 | `parallel_post_3way_net` | 10 | post | 3-way | network | parallel | 1152 | registered |
| 12 | `parallel_incremental_3way_ins` | 11 | incremental | 3-way | insertion | parallel | 1152 | registered |
| 13 | `parallel_incremental_3way_net` | 12 | incremental | 3-way | network | parallel | 1152 | registered |
| 14 | `deep_parallel_post_3way_ins` | 13 | post | 3-way | insertion | deep parallel | 1152 | registered |
| 15 | `deep_parallel_post_3way_net` | 14 | post | 3-way | network | deep parallel | 1152 | registered |
| 16 | `deep_parallel_incremental_3way_ins` | 15 | incremental | 3-way | insertion | deep parallel | 1152 | registered |
| 17 | `deep_parallel_incremental_3way_net` | 16 | incremental | 3-way | network | deep parallel | 1152 | registered |
| 18 | `deep_parallel_post_2way_ins` | 17? | post | 2-way | insertion | deep parallel | 672 | **proposed** |
| 19 | `deep_parallel_post_2way_net` | 18? | post | 2-way | network | deep parallel | 672 | **proposed** |

Note that the `algo` IDs are not in name order: the enum interleaves two-way and
three-way, so `post_3way_ins` is 2 while `post_2way_net` is 3. The two proposed
variants must therefore be **appended** (17, 18) rather than inserted next to
their siblings — inserting would renumber every later ID and invalidate the
`algo` counter in existing JSON results.

## The 24-cell product and what is absent

3 execution modes × 2 discovery × 2 partition × 2 leaf = 24. Seventeen exist
today, nineteen with the proposal, and six remain out of reach:

| cell | count | status |
|---|---|---|
| incremental + 2-way (serial, parallel, deep parallel × ins/net) | 6 | **impossible as implemented** |
| deep parallel + post + 2-way × ins/net | 2 | **proposed here** |
| everything else | 16 | registered |

**Why incremental + 2-way is unimplemented — this claim was wrong.** An earlier
version of this section said a completed two-way fragment "cannot report
self-contained runs". It can. The partition leaves
`[strictly before pivot] [pivot] [not before pivot]`, so a completed left part is
bounded on the right by the pivot, which is strictly greater: its runs are closed
there. Only the pivot and the leading equal run of its sorted right part ever need
merging, and the rest of the boundary state is inherited. See
[benchmark-final.md](benchmark-final.md#incremental-two-way-is-possible-not-impossible)
for the boundary table. The reason not to build it is economic — incremental
three-way buys little (2.0 to 0.98 scanned values per row, 28.00 to 27.77 ms) —
not structural.

**Why deep parallel + post + 2-way is legitimate.** Partition offload is
governed by whether finishing a partition on another worker leaves an obligation
to the enclosing range, and the rule in
[`multicolumn_quicksort.hpp`](../multicolumn_quicksort.hpp) is independent of
partition kind:

```text
offload a partition range when
    incremental discovery AND three-way    -> any column
 or task.column + 1 == column_count        -> the final column only
```

Post-sort discovery over a non-final column keeps its partitions local because
its RLE scan needs the whole sorted range. That restriction applies identically
to two-way and three-way, so `deep_parallel_post_2way_*` is measurable with no
change to the sorter: it offloads partitions of the final column exactly as
`deep_parallel_post_3way_*` does. A one-column case is where it matters most —
there the only available parallelism *is* partition offload, so `parallel_`
leaves every worker but one idle and only `deep_parallel_` scales. Without these
two variants, two-way has no measurable partition-parallel path at all, and the
one-column comparison between partition kinds is missing half its data.

## Axes that multiply every variant

> These are the axes of the **legacy** `benchmark_multicolumn_gbench`. Its eight
> inline `dist=` distributions are not the generator's dataset shapes;
> `cosort_bench` replaced that axis with `shape=`/`sparams=` from
> `TslDatasetSource`. For the current axes see
> [benchmark-final.md](benchmark-final.md#axes).

| axis | values | default | notes |
|---|---|---|---|
| element type × lanes | u32 @ 4/8/16, u64 @ 2/4/8 | all six | compile-time SIMD specializations; the baseline registers per type with `lanes=na` |
| distribution | 8 IDs | uniform, low_entropy, all_equal_prefix, low_entropy_prefix | `COSORT_DISTRIBUTIONS` |
| direction | asc, desc, alternating | asc, alternating | `COSORT_DIRECTIONS` |
| sort columns | any | 1, 2, 3, 5 | `COSORT_COLUMNS`; every column is a sort key |
| size level | L1, L2, halfLLC, LLC, 2xLLC, 16xLLC | all six | bytes **per column**, from sysfs cache sizes |
| workers | scalar per process | `hardware_concurrency()` | `COSORT_WORKERS` |
| task threshold | scalar per process | 4096 rows | `COSORT_TASK_THRESHOLD` |
| partition threshold | scalar per process | 16384 rows | `COSORT_PARTITION_THRESHOLD`, `deep_parallel_` only |

Because the last three are scalar, a scaling curve over workers or thresholds
needs one process per value, merged by `sweep_multicolumn_bench.py`.

**Default registration count: 16,896** benchmarks (verified with
`--benchmark_list_tests`), rising to 18,240 with the two proposed variants.
Running unfiltered is not viable; `--benchmark_filter` and the `COSORT_*` axes
are mandatory in practice.

## Conditional omission of two-way

Two-way partitioning peels one element per level out of an all-equal range — the
split is always 0/(n−1) — so a key column with very few distinct values is
quadratic in its equal-run length (measured ~3.8× per doubling of rows, 26×
slower than three-way by 256Ki rows). All four two-way targets are therefore
skipped for `all_equal_prefix` and `low_entropy_prefix` above 256 KiB per
column, which is why they register 672 cases against three-way's 1152. The
omission is counted and reported on stderr at startup. The two proposed
variants would inherit the same rule.

## Run-detector backends: a second binary, not a variant

The equal-run detector is **absent from the table above** because it is not a
partition/leaf/discovery choice. It is injected through the templated
`sort_columns_parallel(..., DetectRuns &, ...)` overload, so it parameterizes a
sort call rather than selecting an algorithm, and
`benchmark_multicolumn_gbench` always takes the default `scalar_run_detector`.

Accelerator-backed detection lives in a separate executable,
[`benchmark_dsa_cosort.cpp`](../benchmark_dsa_cosort.cpp), gated behind
`TSL_COSORT_ENABLE_DSA` (default **OFF**) plus `ENABLE_GBENCH`, and linking Intel
DML. It is not built by an ordinary configure, which is why none of it appears in
the 16,896 registrations above.

| `rle=` value | detector | completion |
|---|---|---|
| `scalar` | `tsl_for_each_equal_run`, the portable linear scan | synchronous |
| `dml_sw` | DML `create_delta` on the software path — no accelerator needed | synchronous |
| `dsa_hw` | DML `create_delta` on real DSA hardware | synchronous |
| `dml_sw_async` | same software path | asynchronous, polled at task boundaries |
| `dsa_hw_async` | same hardware path | asynchronous, polled at task boundaries |

That harness holds almost everything else fixed — u32, native lanes, three-way,
insertion leaf, `order=asc`, one distribution parameterized by
`COSORT_DISTINCT` — and registers only two algorithm names,
`deep_parallel_post_3way_ins` and `deep_parallel_incremental_3way_ins`, chosen by
`COSORT_DISCOVERY`. Under its defaults that is two names × five backends × two
discovery kinds plus one baseline. It adds four accelerator axes on top:
`dsa_region`, `dsa_slots`, `dsa_depth` and `dsa_min_offload`, and its own
`rle_*` counters (`rle_offloaded_frac`, `rle_descriptors`, `rle_fired_blocks`,
`rle_fallback_no_slot`, `rle_poll_*`).

**Name collision is deliberate and is a hazard.** The DSA harness reuses the two
`gbench` names verbatim so that `visualize_multicolumn_bench.py` can read both
JSONs and compare rows. The only thing distinguishing them is the trailing
`rle=` component, which `gbench` rows do not carry at all. A merged dataset
therefore contains rows where `rle` is absent alongside rows where it is
`scalar`, and whether those denote the same configuration is a convention held
only in the visualizer.

**IAA does not exist.** `multi-column-sort-plan.md` states that Slice 9 is
"superseded by `iaa-rle-offload-plan.md`", which instantiates the detector
against IAA (`qpl_op_scan_eq`). That file is not in the repository or in its
history, and there is no QPL or IAA code anywhere under `test-sort/`. The two
accelerator paths that exist are DML software emulation and DSA hardware, each
synchronous or asynchronous.

## Counters published per case

`count`, `cols`, `lanes`, `elem_bytes`, `dist`, `order`, `algo`, plus, for the
co-sort variants, `rle_values_per_row`, `direct_equal_bands`, `direct_band_rows`,
`tasks_submitted`, `tasks_inline`, `max_outstanding` and `partition_tasks`.
Items are logical rows; bytes count every sort column once.

## Timing and validation as they stand

- Generation, allocation and the per-iteration reset from pristine columns are
  outside the timed region; the sort call is timed, including executor startup
  and shutdown for parallel cases.
- Every target uses `UseRealTime()`, because CPU time is meaningless for
  multi-worker variants.
- Correctness after the timed loop is only the **lexicographic order invariant**
  over adjacent rows. That cannot detect a lost row, a duplicated row, or a
  column permuted independently of the others while staying ordered.

## Open questions for the setup discussion

> Items 1, 2, 3 and 7 are **settled and implemented** in `cosort_bench`; 5 is
> implemented too (both two-way deep-parallel variants are registered). The list is
> kept as written for the reasoning. The genuinely open items are collected in
> [benchmark-final.md](benchmark-final.md#open-items).

1. **Oracle.** Replace the order invariant with `memcmp` against the reference
   image from `datagen/dataset_reference.hpp`. With every column a sort key the
   sorted image is unique, so this is exact, and it also catches row loss and
   per-column divergence. Confirmed byte-identical across partition kinds,
   leaves, lane counts, worker counts and discovery strategies.
2. **Data source.** The benchmark generates its eight distributions inline.
   `TslDatasetSource` offers the nine documented shapes with measured
   descriptors ($D_j$, $G_j$, $R_j$, $W$) so results can be normalized by
   intrinsic work instead of compared as raw ns/row across unlike shapes.
3. **Matrix size.** 16,896 default registrations is a sweep nobody runs. Is the
   default worth narrowing to a defensible core, with the full product reachable
   only through `COSORT_*`?
4. **Element-width convention.** Size levels hold bytes per column constant, so
   u64 cases have half the rows of u32. State it with every cross-width plot, or
   add a fixed-row mode.
5. **The two proposed variants.** Add them, appending `algo` IDs 17 and 18?
6. **`16xLLC`.** Level 5 is registered by default but a 5-column u64 case there
   is ~19 GiB after the working copy; the 64 GiB memory cap admits it. Keep,
   or drop it from the default range?
7. **Promote `rle=` to an axis of the main binary.** See the proposal below.
8. **The dangling IAA plan.** `multi-column-sort-plan.md` defers Slice 9 to a
   document that does not exist. Either write it, or restate Slice 9 as the DSA
   work that actually shipped.

## Proposal: `rle=` as a first-class axis

The detector is orthogonal to partition, leaf and discovery in the code, so it
should be an axis rather than a second binary. Two things make it not a plain
Cartesian product.

**Constraint 1 — only the parallel path has a seam.** `sort_columns_impl` calls
`tsl_for_each_equal_run` directly, while only `sort_columns_parallel` accepts a
`DetectRuns &`. The 6 serial variants therefore have no detector to select, and
the two asynchronous backends could not work there regardless: they need the
executor for `bind`/`poll` and for pending-work accounting. Either give the
serial path the same template seam — which would admit `scalar` and the two
synchronous backends, not the asynchronous ones — or accept that `rle=` is
parallel-only and register accordingly.

**Constraint 2 — most of the matrix cannot engage the accelerator.** No
discovery happens at `cols=1`, and offload needs at least `min_offload` elements
in a region of up to 512 KiB, so at L1 and L2 the accelerator is pure overhead.
Registering non-scalar backends there would multiply rows that measure nothing.

### Suggested scoping

```text
always            rle= appears in every benchmark name, so a row is explicit
                  about its detector and no join convention is needed;
                  scalar is the only value unless TSL_COSORT_ENABLE_DSA is on

non-scalar        only for the parallel_ and deep_parallel_ families (12 of 19)
backends          only at cols >= 2        (below that nothing is discovered)
                  only at size >= halfLLC  (below that offload cannot pay)
                  only at native lane width (the detector does not depend on
                  lane count; the sort does, so one width is enough to see
                  the RLE fraction)

accelerator       dsa_region, dsa_slots, dsa_depth and dsa_min_offload stay out
tuning            of the main matrix and remain in benchmark_dsa_cosort, where
                  every other axis is pinned. Tuning the offload and comparing
                  algorithms are different experiments.
```

That adds roughly 2 element widths × 4 distributions × 2 directions × 3 column
counts × 3 size levels = 144 cells × 12 variants × 4 non-scalar backends ≈ 6,900
registrations, and only when DSA is compiled in. Restricting non-scalar to the 6
`deep_parallel_*` variants instead would bring it to ≈ 3,500.

Note the element width is worth keeping in that product: the detector's
block-shift trick uses `g = 8 / sizeof(T)`, so u32 needs a two-element CPU
refinement per fired block while u64 needs none. That is a real difference in
the detector itself, not just in the surrounding sort.

### What this buys

- The accelerator is measured against 12 variants instead of 2, and across
  columns and sizes instead of at one point.
- `rle=scalar` becomes explicit, so `visualize_multicolumn_bench.py` no longer
  needs the convention that a missing component means scalar.
- The two harnesses stop sharing algorithm names for different things.

### Risk to handle

With `TSL_COSORT_ENABLE_DSA=ON` the main benchmark is a *different binary with
the same name*, and two sweeps from different builds could be merged silently.
Emitting `rle=` unconditionally is most of the mitigation; the startup line that
already reports cache sizes should also report whether accelerator backends were
compiled in.


## The final matrix: three staged experiments, not one product

The full product is roughly 84,000 cases with `rle=` included, which is neither
runnable nor meaningful: most of it re-answers questions already settled at other
points. Replace it with a funnel. Each stage pins the axes its question does not
need, and its result decides the next stage's scope.

### Variants stay at 19; the *registration scope per variant* is what shrinks

No variant is dropped. What changes is where each one is registered:

| variant family | count | registered across |
|---|---|---|
| `std_lex_argsort` | 1 | every data point, always — it is the normalizer |
| serial `post_*`, `incremental_*` | 6 | full data matrix; no worker or threshold axis applies |
| `parallel_*` | 6 | worker and threshold axes; `rle=` where applicable |
| `deep_parallel_*` (incl. the 2 proposed) | 6 | as above, plus the partition-threshold axis |
| non-scalar `rle=` backends | ×4 | only the 12 parallel variants, `cols >= 2`, `size >= halfLLC`, native lanes |

Two evidence-based scope cuts on top of that:

- **Two-way only needs high-cardinality data.** It is already known to lose on
  duplicates — quadratic on all-equal, 26× slower than three-way by 256Ki rows,
  which is why pathological cases are excluded — and known to be *competitive* on
  uniform input (14.90 ms versus 15.12 ms at L2). So measure it on the
  high-cardinality shapes, where the question is still open, and stop paying for
  it on the low-cardinality ones where it is settled.
- **Direction carries almost no information.** Equality is direction-invariant, so
  $D_j$, $G_j$, $R_j$ and $W$ do not change, and the sorter dispatches once per
  range on a compile-time order. The only asymmetric path is the network leaf's
  co-reverse for descending output. Pin the sweep to `asc` and spend one small
  slice confirming `desc`/`alternating` show no anomaly, particularly for `net`.

### Stage A — screening: which variants are viable at all?

All 19 variants, one point per axis: u32, native lanes, `asc`, `cols=3`, two size
levels (L2 and LLC), default workers and thresholds, six representative dataset
shapes (unique_first, unique_last at `g=2` and `g=C`, independent_uniform,
skewed_zipf, low_cardinality).

```text
19 variants x 6 shapes x 2 sizes = 228 cases, one process, minutes
```

Output: a dominance ranking. Variants that lose everywhere here do not enter
Stage B.

### Stage B — tuning: what configuration makes the survivors fastest?

Only the parallel survivors, and **coordinate descent rather than a grid** over
the three per-process axes, because each value needs its own process:

```text
sweep workers   {1,2,4,8,16,24} at default thresholds        6 processes
then task       {512,4096,32768} at the best worker count    3 processes
then partition  {0,4096,16384,65536} at the best of both     4 processes
                                                            13 processes
6 survivors x 3 shapes x 2 sizes = 36 cases each -> 468 cases
```

A full grid over the same values would be 72 processes and ~2,600 cases for
information coordinate descent recovers, because worker count and the thresholds
interact weakly: the thresholds decide what is worth queueing, the worker count
decides how many consumers exist.

### Stage C — characterization: the numbers that get published

The two or three finalists plus the baseline, across the real data matrix:

```text
4 algorithms x 40 dataset parameter sets x 3 sizes x 2 element widths   960
  (native lanes, asc, cols=3)
lanes slice:      2 algorithms x 6 (type,lanes) x 3 shapes x 2 sizes     72
direction slice:  4 algorithms x 3 directions x 3 shapes x 1 size        36
column slice:     4 algorithms x 4 column counts x 3 shapes x 2 sizes    96
                                                                      1,164
```

### Total

```text
Stage A     228 cases,  1 process
Stage B     468 cases, 13 processes
Stage C   1,164 cases,  1-2 processes
        ~1,860 cases -- one to two hours, against ~84,000 for the full product
```

Every question in the design has a slice that answers it, and no slice re-answers
another's question. That is a defensible substitute for exhaustive exploration:
completeness of the *product* was never the goal, completeness of the *questions*
is.

### What this requires from the harness

1. Registration predicates per variant family, so scope restrictions live in the
   registrar rather than in a filter string the reader never sees. The two-way
   omission already works this way and reports what it dropped; the same
   mechanism generalizes.
2. A named stage selector, e.g. `COSORT_STAGE=screen|tune|characterize`, so a run
   is reproducible from one variable instead of a dozen.
3. Whatever a stage drops must be *reported*, as the two-way omission already is.
   A silently narrowed default reads as full coverage.


## Correction: register width and code style are variants, not axes

The 19 above counts only *algorithmic* choices. Register width and
implementation style are properties of the compiled sorter — template parameters,
exactly like partition and leaf kind — so they belong in the variant space. TSL
provides both, and the earlier framing of "lanes" as a workload axis was wrong.

### What TSL offers

`TSL_ENABLE_CLANG` is **additive**: `tsl.hpp` includes the `_clang` profile header
in a separate `#if`, not as part of the profile chain, so `tsl::avx512` and
`tsl::clang_v512` coexist in one translation unit. Style is therefore a template
parameter, not a second binary:

```cpp
using Intr  = tsl::simd<std::uint32_t, tsl::avx512>;       // 512-bit intrinsics
using Clang = tsl::simd<std::uint32_t, tsl::clang_v512>;   // 512-bit builtins
using Sorter = TslMultiColumnQuickSorter<u32, Partition, Leaf, 16, Style>;
```

Every primitive the co-sort needs exists for `clang_v128/256/512`, so all six
(style × width) combinations instantiate.

### The honest size of the variant space

```text
18 algorithm configurations (16 registered + 2 proposed)
 x 2 styles   (intrinsics, clang builtins)
 x 3 widths   (128, 256, 512 bit)
 = 108, plus the width-independent baseline               = 109

with rle: 12 parallel families x 2 styles x 3 widths x 4 non-scalar backends
 = 288 more                                              ~ 400 total
```

So 19 was low by a factor of six. What follows is *not* that the matrix must grow
sixfold, because the two new dimensions are not alike.

### Width is an open question; style is a known mechanism

**Width has no predetermined answer.** Wider is usually better, but the network
leaf sorts a fixed padded block of `C = 16L` elements regardless of range length,
so at low fill ratio a wider register does strictly more wasted work — the
dataset document's $\phi$ predicts exactly where 512-bit should lose to 128-bit.
Width therefore stays in the product for the finalists.

**Style has a known mechanism and a predictable direction.** For the two
primitives the co-sort is built on, the clang family is not a different codegen —
it is an emulation:

| primitive | `avx512` | `clang_v512` |
|---|---|---|
| `permute_lanes` | `_mm512_permutexvar_epi32`, one instruction | 16-iteration scalar extract/insert loop (`implementation_state::fallback`) |
| `compress` | `_mm512_maskz_compress_epi32`, one instruction | 16 sequential branches doing scalar compaction (`composed`) |
| `expand` | native | `composed` |
| `min`, `max` | native | native |

The partition stitch issues six compresses and four expands per column per
iteration, and the network leaf one permute per comparator, so the clang style is
expected to lose heavily and for a reason that is already understood. It is not a
candidate for "fastest variant".

### Consequence: two experiment families, not one matrix

Mixing these questions is what made the matrix explode. Separate them:

**E1 — algorithm comparison.** "Which sort strategy wins?" Style pinned to
intrinsics; width swept for the finalists only. This is the funnel of the previous
section, unchanged.

**E2 — primitive attribution.** "What do TSL's native `compress`/`expand`/
`permute_lanes` buy, and how does that scale with register width?" A small,
self-contained experiment with a predicted direction:

```text
4 algorithm configurations (2way|3way x ins|net, serial)
 x 2 styles x 3 widths x 3 dataset shapes x 2 sizes = 144 cases
```

E2 is worth running precisely because its answer is predictable: it quantifies the
value of the native specializations, and it is the portability result — on a target
without a native compress, the fallback is what you actually get. It also isolates
the one place the two styles might *not* order predictably: the network leaf
depends on `permute_lanes`, whose clang fallback is far worse than its composed
`compress`, so `net` should degrade more than `ins`. If that ordering does not
appear, the mechanism is not understood.

Adding E2's 144 cases to the ~1,860 of the funnel keeps the whole programme near
2,000 cases.

### Naming hazard — fixed

`lanes=16` alone is ambiguous once `TSL_ENABLE_CLANG` is on, because `avx512` and
`clang_v512` both have 16 `u32` lanes: two different variants would produce
identical names and silently merge in the JSON. The name grammar now carries a
style component, emitted unconditionally:

```text
post_3way_net/u32/style=intr/lanes=16/...      SIMD variants
std_lex_argsort/u32/style=na/lanes=na/...      scalar baseline
```

All 16,896 registrations carry it (16,512 `intr`, 384 `na`) and the count is
unchanged. Three consumers were updated with it:

- `visualize_multicolumn_bench.py` gained `style` as a pinnable dimension with
  `STYLE_ORDER = [na, intr, clang]`, and treats it as optional-categorical like
  `rle`, so a `style=na` baseline survives a pin on any style. Names recorded
  before the axis existed default to `intr`, which is what they were, so old
  sweeps stay joinable.
- `sweep_multicolumn_bench.py` relaxes `style=` for the baseline phase exactly as
  it already relaxed `lanes=`, otherwise narrowing a sweep to one family would
  silently drop the baseline that every speedup metric divides by.
- A hand-written `--narrow` must not hard-code the type/lanes adjacency any more:
  write `u32.*lanes=16`, not `u32/lanes=16`.

### Build constraint on the clang family

`tsl_<profile>_clang.hpp` opens with `#if defined(__clang__)`, so `tsl::clang_v*`
does not exist under GCC — the header compiles to nothing. `test-sort` currently
configures with `/usr/bin/c++` (GCC), so **E2 requires a clang++ build of the
benchmark target**, either a second build directory or a per-target compiler
override. This does not affect E1, and it is a further reason to keep the two
experiments separate: they do not even share a binary.


## Per-machine builds: DSA here, IAA elsewhere

The two accelerators are independent build options because a host has one or the
other. `rle=` is part of every benchmark name, so rows from differently-equipped
machines never collide, and the detector a result came from is never implicit.

```bash
# any host, no accelerator
cmake --preset clang && cmake --build --preset clang

# a DSA host: DML is fetched and built in-tree, one step
cmake --preset dsa && cmake --build --preset dsa

# an IAA host
QPL_ROOT=<prefix> cmake --preset iaa && cmake --build --preset iaa
```

Set `DML_ROOT` to consume a pre-built DML instead of building it in-tree; the
in-tree build is the default because it needs no separate step.

`COSORT_RLE` then selects backends from whatever the build has:
`scalar,dml_sw,dsa_hw,dml_sw_async,dsa_hw_async` on a DSA build,
`scalar,iaa_hw,iaa_hw_async` on an IAA build. The binary prints which backends it
was compiled with, and registration drops the rest with the reason
"detector backend not compiled in" rather than omitting them silently.

### Adding the IAA backend

`benchmarks/cosort_detectors.hpp` documents the whole contract. The IAA host needs
`test-sort/iaa_run_detector.hpp` providing

```cpp
template <class DataType> class TslIaaRunDetector;       // (values, begin, end, emit)
template <class DataType> class TslIaaAsyncRunDetector;  // + bind(TslPendingWork&), poll()
```

emitting maximal equal runs of length > 1 as absolute half-open spans in
increasing order — the `tsl_for_each_equal_run` contract — and optionally
`aggregate_metrics()` for the `rle_*` counters. Configuring with
`TSL_COSORT_ENABLE_IAA=ON` without that header fails at configure time with a
message naming it, rather than deep in a compile.

### Where a non-scalar detector is registered

`cosort_plan.hpp::detector_applies` keeps accelerator backends to cases where they
can do something: the parallel execution path (the serial driver calls the scalar
scan directly, and an asynchronous detector needs the executor for its
pending-work accounting), at least two columns (nothing is discovered at one),
`halfLLC` and above (below that an offload cannot pay for itself), and the native
register width (the detector does not depend on lane count). On this host that
turns 73 candidate cases into 55 registered plus 18 reported as
"detector cannot engage here".

### Prerequisites this uncovered, now diagnosed at configure time

- **DML needs `<uuid/uuid.h>`** for its hardware dispatcher. Without it the build
  fails inside the fetched DML tree; CMake now checks and names `uuid-dev` /
  `libuuid-devel`.
- **Both compilers must be pinned.** DML calls `enable_language(C)`, and CMake
  takes the C compiler from the environment rather than from the C++ one this
  project was configured with. On a host where `CC` names something unexpected --
  here it was `zig cc` -- DML's AVX-512 kernels fail on `-march=skylake-avx512`,
  which zig parses as arch `skylake` plus an unknown feature `avx512`, deep inside
  the fetched tree and with no file or line in the diagnostic. The presets pin
  `CMAKE_C_COMPILER` alongside `CMAKE_CXX_COMPILER`, and CMake now probes the flag
  and names the compiler that rejected it. DML itself builds cleanly with clang 22;
  an earlier note here claiming it needed GCC was wrong.

### Cross-machine comparison

Absolute times from two different machines are not comparable. What is comparable
is each machine's ratio of a backend to its own `rle=scalar` row at the same
dataset, size and worker count. `sweep_multicolumn_bench.py` already refuses to
merge runs from different hosts, and that refusal should stay: merge per host,
compare ratios across hosts.

### Status of the DSA hardware path on this host

`scalar` and `dml_sw` both work through the new axis. `dsa_hw` fails with
`create_delta failed with DML status 16` (`DML_STATUS_BATCH_LIMITS_ERROR`) — and so
does the pre-existing `test_dsa_run_detector hw`, at a smaller transfer size, so
the fault is in the detector or its DML/work-queue expectations rather than in the
benchmark wiring. The device itself is enabled with a shared and a dedicated user
work queue. Diagnosing that is separate work; until then a DSA host measures
`scalar` and `dml_sw`, which is still the software-path comparison the harness was
built for.
