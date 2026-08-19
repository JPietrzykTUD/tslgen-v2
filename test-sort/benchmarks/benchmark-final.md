# Multi-column co-sort: benchmark plan

Authoritative plan for measuring the lexicographic multi-column co-sort. Every
decision here is settled and, where marked, implemented in `cosort_bench`.
[`benchmark.md`](benchmark.md) is the working draft this was distilled from and is
kept only for the reasoning behind these decisions.

## Settled decisions

| decision | rationale | state |
|---|---|---|
| Data comes from `TslDatasetSource` | the nine documented dataset shapes with measured descriptors ($D_j$, $G_j$, $R_j$, $W$), generated in memory and shared across cases, nothing on disk | implemented |
| Correctness is `memcmp` against the reference image | with every column a sort key the sorted image is unique however an unstable sort breaks ties, so the comparison is exact and names the first differing row | implemented |
| Registration goes through per-family predicates, selected by `COSORT_STAGE` | the full product is unrunnable and mostly redundant; each stage answers one question and reports what it dropped | implemented |
| clang 22 for everything | required by the generated clang profile header (`__builtin_elementwise_clzg`); the intrinsic families build with it too | implemented |
| Register width and implementation style are *variant* dimensions | both are template parameters of the sorter, not conditions it runs under | implemented |
| `rle=` is an axis of the one binary, with per-machine backends | the detector parameterizes a sort call; a host has DSA or IAA, and `rle=` records which produced a row | implemented |

## Variant space

A variant is one compiled sorter configuration. The algorithmic part is
`execution × discovery × partition × leaf` = 3 × 2 × 2 × 2 = **24**, and every cell
is implemented and registered:

```text
24 algorithm configurations x 2 styles (intr, clang) x 3 widths (128, 256, 512)
  = 144 sorter configurations, plus the width- and style-independent baseline
  = 145
```

The 25 names `cosort_bench` registers, at one (style, width):

```text
post_2way_ins                       post_2way_net
post_3way_ins                       post_3way_net
incremental_2way_ins                incremental_2way_net
incremental_3way_ins                incremental_3way_net
parallel_post_2way_ins              parallel_post_2way_net
parallel_post_3way_ins              parallel_post_3way_net
parallel_incremental_2way_ins       parallel_incremental_2way_net
parallel_incremental_3way_ins       parallel_incremental_3way_net
deep_parallel_post_2way_ins         deep_parallel_post_2way_net
deep_parallel_post_3way_ins         deep_parallel_post_3way_net
deep_parallel_incremental_2way_ins  deep_parallel_incremental_2way_net
deep_parallel_incremental_3way_ins  deep_parallel_incremental_3way_net
std_lex_argsort                     (scalar baseline, the normalizer)
```

`algo` IDs match the previous benchmark's enum so old JSON stays comparable, and
everything that enum lacked is **appended** rather than inserted: the two two-way
deep-parallel variants as 17 and 18, the six incremental two-way variants as 19 to
24. Inserting would renumber existing IDs and invalidate recorded results.

### How incremental two-way works

An earlier draft claimed a two-way fragment "cannot report self-contained runs".
That was wrong, and the variant is now implemented. The two-way partition produces

```text
[ strictly before pivot ] [ pivot ] [ not before pivot ]
 lo               p-1        p       p+1            hi-1
```

so the boundary status of every fragment is known exactly:

| fragment | left boundary | right boundary |
|---|---|---|
| root range of a column sort | closed — the enclosing equal-prefix group | closed |
| left part `[lo, p)` | inherits the parent's left boundary | **closed** — the pivot at `p` is strictly greater |
| the pivot at `p` | **closed** — the left part is strictly smaller | **open** — the right part may begin with equal values |
| right part `[p+1, hi)` | **open** — merges with the pivot | inherits the parent's right boundary |

A completed left part can therefore be scanned immediately, and the only place a
run can cross is the pivot into the head of its right part.

One bit of state per range is *not* enough, though, and that is the part worth
knowing. On duplicate-heavy input two-way peels one copy of a value per level with
an **empty left part**, so a run of `k` equal values becomes a chain of `k`
consecutive pivots; widening a fragment by one element covers only the nearest.
What `sort_impl` threads instead is the **start position of the run overlapping the
open edge**: everything in `[open_begin, range_begin)` is equal and already final,
so a fragment reports from there and the runs found inside are maximal. Three cases
complete it:

- a fragment reports `[open_begin, end)`, closed on both sides;
- an empty fragment reports nothing — its open run either continues into the
  sibling pivot, whose range covers it, or was reported where the chain ended;
- when a chain ends at a pivot that differs, the frame reports the chain itself,
  because no fragment below would cover it.

A range handed to another worker is *offered* from `open_begin` too, so it re-enters
as a root with a closed left edge. Those extra elements are final, no other worker
writes them, and a range beginning with its own minimum keeps it there — so
partition offload stays available for two-way incremental, and
`deep_parallel_incremental_2way_*` is a real variant rather than a relabelled
`parallel_` one.

**Validated** by comparing the emitted span set against a full-range scan of the
sorted output: no missed and no duplicated spans across both partition kinds, both
leaves, both directions, at row counts from 2 to 200,000 and cardinalities from 1
to 200,000 — and separately through the benchmark's `memcmp` oracle over 378 cases
at 1, 4 and 24 workers. A `memcmp` alone would not have been enough: a missed run
shows up as a wrong image, but a duplicated one only wastes work.

**And it does not pay.** At L2, `unique_last_g64`, u32, three columns:

| variant | time | `rle_values_per_row` |
|---|---|---|
| `post_2way_ins` | 94.63 ms | 2.00 |
| `incremental_2way_ins` | 98.64 ms | 2.00 |
| `post_3way_ins` | 16.53 ms | 2.00 |
| `incremental_3way_ins` | 16.43 ms | **0.37** |

The scan-volume win of incremental discovery comes entirely from three-way's
pivot-equal bands, which are emitted with **no scan at all**. Two-way has no bands,
so every element still has to be scanned by some fragment: incrementality alone
changes only *when* the scan happens and how early next-column work is exposed. Here
that cost about 4% in time. Keeping the variant is still worth it — it makes the
product complete, and it means "incremental" can be compared against "post" without
the partition kind confounding the answer.

## Axes

These are the axes of `cosort_bench`. The dataset shape replaces the eight inline
`dist=` distributions of the legacy `benchmark_multicolumn_gbench`, which is a
different binary and is not part of this plan.

| axis | name component | values | selected by |
|---|---|---|---|
| dataset shape | `shape=`, `sparams=` | any dataset id prefix from the generator catalog: `unique_first`, `unique_last_g64`, `independent_uniform_c1024`, `skewed_zipf_s1`, `low_cardinality_d4`, … | `COSORT_SHAPES` |
| element width | the `u32`/`u64` component | 4, 8 bytes | `COSORT_ELEMENTS` |
| sort columns | `cols=` | every column is a sort key | `COSORT_COLUMNS` |
| working set | `size=` | L1, L2, halfLLC, LLC, 2xLLC, 16xLLC — bytes **per column** | `COSORT_SIZE_LEVELS` |
| direction pattern | `order=` | asc, desc, alternating | `COSORT_DIRECTIONS` |
| detector | `rle=` | scalar, plus whatever the build has | `COSORT_RLE` |
| workers | `workers=` | scalar per process | `COSORT_WORKERS` |
| task threshold | `threshold=` | scalar per process | `COSORT_TASK_THRESHOLD` |
| partition threshold | `partitions=` | scalar per process, `deep_parallel_` only | `COSORT_PARTITION_THRESHOLD` |

Style and width appear in a name as `style=` and `lanes=` but are variant
dimensions, not axes. `style=` is mandatory because `avx512` and `clang_v512` have
the same lane count and would otherwise produce identical names.

A full benchmark name:

```text
deep_parallel_incremental_3way_net/u32/style=intr/lanes=16/shape=unique_last_g64/
sparams=g=64/order=asc/cols=3/size=LLC/stage=screen/rle=scalar/workers=12/
threshold=4096/partitions=16384/real_time
```

Worker count and both thresholds are scalar per process, so a scaling curve over
them needs one process per value, merged by `sweep_multicolumn_bench.py`.

## The staged programme

Each stage pins the axes its question does not need. Counts are measured with
`--benchmark_list_tests` on a 12-core host with the clang family available.

| stage | question | registered | drops reported |
|---|---|---|---|
| `screen` | which variants are viable at all? | 276 | 24 quadratic two-way |
| `tune` | what worker count and thresholds make the survivors fastest? | 86 | 8 out of variant set, 16 quadratic two-way |
| `characterize` | the numbers that get published | 5,712 unrestricted | 288 quadratic two-way |
| `attribute` | what do the native SIMD primitives buy? | 126 | 120 out of variant set, 24 quadratic two-way |

**`screen`** — all 25 names at one point per axis: u32, 512-bit intrinsics, `asc`,
`cols=3`, L2 and LLC, six representative shapes. 25 × 6 × 2 = 300 less 24 two-way
cases on a low-cardinality key. Minutes, one process. Output: a dominance ranking.

**`tune`** — the parallel survivors only, and **coordinate descent** over the three
per-process axes rather than a grid, because they interact weakly: the thresholds
decide what is worth queueing, the worker count decides how many consumers exist.

```text
workers   {1,2,4,8,16,24} at default thresholds     6 processes
task      {512,4096,32768} at the best worker count 3 processes
partition {0,4096,16384,65536} at the best of both  4 processes
                                                   13 processes
```

A full grid over the same values is 72 processes for information coordinate
descent recovers.

**`characterize`** — set `COSORT_VARIANTS` to the finalists from `screen`; the
binary warns when it is unset, because unrestricted it registers every variant.
With four algorithms: 40 dataset parameter sets × 3 sizes × 2 element widths ≈ 960
cases, plus targeted slices for lanes (72), direction (36) and column count (96).

**`attribute`** — the style experiment, deliberately separate: 4 algorithm
configurations (2way|3way × ins|net, serial post-sort) × 2 styles × 3 widths × 3
shapes × 2 sizes. Its answer is predictable, which is the point: it quantifies what
TSL's native `compress`/`expand`/`permute_lanes` are worth, and it is the
portability result, because on a target without a native compress the fallback is
what you get.

Whole programme: roughly 2,000 measured cases, one to two hours, against ~84,000
for the full Cartesian product. Completeness of the *questions* is the goal, not
completeness of the product.

## Builds

```bash
cmake --preset clang && cmake --build --preset clang          # any host
cmake --preset dsa   && cmake --build --preset dsa            # a DSA host
QPL_ROOT=<prefix> cmake --preset iaa && cmake --build --preset iaa   # an IAA host
```

The presets pin **both** `CMAKE_C_COMPILER` and `CMAKE_CXX_COMPILER`. That is not
cosmetic: DML calls `enable_language(C)`, and CMake takes the C compiler from the
environment, so a `CC` naming something unexpected breaks DML's AVX-512 kernels
deep inside the fetched tree. Prerequisites are checked at configure time and name
what is missing: `<uuid/uuid.h>` for DML's hardware dispatcher, and a C compiler
that accepts `-march=skylake-avx512`.

Adding the IAA backend on the IAA host means providing
`test-sort/iaa_run_detector.hpp` with `TslIaaRunDetector<T>` and
`TslIaaAsyncRunDetector<T>` satisfying the contract documented at the top of
`cosort_detectors.hpp`; configuring `TSL_COSORT_ENABLE_IAA=ON` without it fails at
configure time naming the file.

## Reporting conventions

- **Normalize by $W$ across shapes.** Raw ns/row between `unique_first` and
  `unique_last` is meaningless — they differ in intrinsic work by orders of
  magnitude. Within one shape, ns/row is fine. `COSORT_DESCRIBE=1` publishes
  `work_per_row`, `scan_per_row`, `distinct_first` and `duplicate_tuple_frac`.
- **Compare measured discovery volume against predicted $\sum R_j$.** A gap means
  discovery is scanning ranges it should not.
- **State the element-width convention.** Size levels hold bytes per column
  constant, so a u64 case has half the rows of the u32 case at the same level. A
  cross-width plot at fixed footprint conflates narrower keys with more rows.
- **Across machines, compare ratios, never absolute times.** A DSA host and an IAA
  host are different hardware; what transfers is each host's ratio of a backend to
  its own `rle=scalar` row at the same dataset, size and worker count.
  `sweep_multicolumn_bench.py` refuses to merge runs from different hosts, and that
  refusal should stay.
- **Every drop is reported.** A silently narrowed run reads as full coverage.

## Open items

1. **Element-width convention** — keep bytes-per-column constant, or add a
   fixed-row mode? Only affects how cross-width results are read.
2. **`16xLLC`** — a 5-column u64 case there is ~19 GiB after the working copy.
   Keep in the default range or require it explicitly?
3. **Incremental two-way costs about 4% and saves no scanning** — kept for
   completeness, but a candidate to drop from `screen` if the sweep needs
   trimming. Whether the earlier task exposure helps at higher worker counts or on
   the skewed shapes is unmeasured.
4. **`dsa_hw` fails on this host** with `DML_STATUS_BATCH_LIMITS_ERROR`, and so
   does the pre-existing `test_dsa_run_detector hw`, so the fault predates this
   harness. Until it is diagnosed a DSA host measures `scalar` and `dml_sw`.
5. **The dangling IAA plan** — `multi-column-sort-plan.md` defers Slice 9 to
   `iaa-rle-offload-plan.md`, which does not exist. Write it or restate Slice 9 as
   the DSA work that shipped.
