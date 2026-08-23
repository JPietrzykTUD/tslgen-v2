# What the benchmark actually does

One pass through `run_all.sh`, in order, with what is built when, what is measured,
and where each measurement goes. The rationale for the *axes* is in
[benchmark-plan.md](benchmark-plan.md); this file is the mechanism.

Nothing here is a literal about one machine. Row counts come from the probed last
level cache, worker counts from the physical cores of one NUMA node, and the
measurement cell from Q0. A second host needs the same command.

## The graph

```
                        ┌──────────────────────────────────────┐
                        │ 0. probe the host                    │
                        │    /dev/dsa, /dev/iax  → preset      │
                        │    lscpu topology      → cpu list    │
                        │    sysfs LLC           → row counts  │
                        └───────────────┬──────────────────────┘
                                        │
                        ┌───────────────▼──────────────────────┐
                        │ 1. configure + build bench_q0_tune   │
                        │    preset: counters compiled out,    │
                        │    phase timers off, DSA/IAA/baselines│
                        │    per what step 0 found             │
                        └───────────────┬──────────────────────┘
                                        │
                        ┌───────────────▼──────────────────────┐
                        │ 2. correctness gate                  │
                        │    every compiled cell, both key     │
                        │    widths, 2^16 rows, no timing      │
                        │    FAILS THE RUN if anything sorts   │
                        │    wrongly                           │
                        └───────────────┬──────────────────────┘
                                        │
                        ┌───────────────▼──────────────────────┐
                        │ 3. Q0: tune, once, in full           │
                        │    pinned, 4x LLC of data, all       │
                        │    compiled cells, interleaved       │
                        │                                      │
                        │    emits ──► best_config.tsv         │
                        │          └─► TSL_COSORT_BEST_CELL    │
                        └───────────────┬──────────────────────┘
                                        │
                        ┌───────────────▼──────────────────────┐
                        │ 4. re-configure for the chosen cell  │
                        │    -DTSL_COSORT_MEASURE_STYLE=…      │
                        │    -DTSL_COSORT_MEASURE_WIDTH=…      │
                        │    build every reporting driver      │
                        └───────────────┬──────────────────────┘
                                        │
       ┌───────────────┬────────────────┼────────────────┬───────────────┐
       │               │                │                │               │
┌──────▼─────┐ ┌───────▼──────┐ ┌───────▼──────┐ ┌───────▼─────┐ ┌───────▼──────┐
│ Q1         │ │ Q2           │ │ Q3           │ │ Q4          │ │ Q5 / Q6      │
│ baselines  │ │ algorithms   │ │ detection    │ │ scaling     │ │ corpus stages│
│            │ │              │ │              │ │             │ │              │
│ ours vs    │ │ quicksort vs │ │ scalar vs    │ │ threads,    │ │ every variant│
│ std::sort, │ │ samplesort   │ │ this host's  │ │ rows,       │ │ x style      │
│ IPS4o,     │ │ over the     │ │ accelerator  │ │ columns     │ │ x width      │
│ argsort,   │ │ shape grid   │ │              │ │             │ │ (gbench)     │
│ Arrow      │ │              │ │              │ │             │ │              │
└──────┬─────┘ └───────┬──────┘ └───────┬──────┘ └───────┬─────┘ └───────┬──────┘
       └───────────────┴────────────────┼────────────────┴───────────────┘
                                        │
                        ┌───────────────▼──────────────────────┐
                        │ 5. one CSV per question, one schema  │
                        │    results/<host>/q*.csv             │
                        └──────────────────────────────────────┘
```

## Step by step

### 0. Probe the host

`run_all.sh`, before anything is built:

| probe | source | decides |
| --- | --- | --- |
| accelerator | `/dev/dsa`, `/dev/iax` | which preset, and Q3's `--detectors` |
| physical cores per node | `lscpu -p=CPU,CORE,NODE` | the `numactl` cpu list and every worker count |
| last level cache | `/sys/.../cache/index*/size` | every row count |

The cpu list is the *first thread of each core on node 0* — one thread per physical
core, one NUMA node. Everything downstream runs under
`numactl --physcpubind=<list> --membind=0`. Without it a memory-bound co-sort across
24 logical CPUs measures SMT siblings evicting each other and gathers crossing a
node boundary; that is what made the parallel numbers appear to degrade past four
workers.

### 1. Build the tuner only

The preset is always a *measurement* preset: `TSL_COSORT_NO_INSTRUMENTATION=ON`, so
the sorters' counters compile out, and `TSL_COSORT_PHASES` unset, so the phase
timers do not exist. Both cost enough to move a comparison — the counters 1.17x on
the parallel index-sort path, the timers up to 1.79x — and `run_paper.sh` refuses to
write results from a build that has them.

Only `bench_q0_tune` is built here, because the cell the others are built *for* is
not known yet.

### 2. Correctness gate

`bench_q0_tune --verify-only`. Every compiled cell, both key widths, 2^16 rows,
nothing timed. It checks that the index is a permutation *and* that applying it
reproduces the reference image — the permutation half is not redundant, because a
value-only check accepts an index that repeats one row and drops another whenever
the two hold equal keys, and the tuning set is duplicate-heavy by design.

A failure fails the whole run. This is what caught the hybrid leaf handing a
64-element range to a 32-element network at 128-bit with 8-byte keys.

### 3. Q0 — tune once, in full

Pinned, `4 x LLC` of live data, every compiled (style, register width, key width)
cell, and **interleaved**: each candidate contributes a callable, all of them stay
live, and one pass of each runs per round. Sequential measurement charges drift
between candidate blocks to their difference, and that drift (1.0% median, 3.5%
worst) is larger than the differences being resolved.

Per cell it emits:

* **`best_config.tsv`** — one line per `algorithm | style | width | element_bytes`.
  The shipped configuration is the documented default unless a candidate resolvably
  beats it: pooled per-round ratio against the default with an upper quartile below
  1.0. Ties are reported, not broken silently.
* **`TSL_COSORT_BEST_CELL <style> <width>`** — the cell to build the reporting
  drivers for. Intrinsics at the widest width is the incumbent and a challenger must
  clear 5% to displace it, because seven of nine cells sit inside the noise floor
  and ranking them by strict less-than once chose a four-lane cell to measure an
  AVX-512 paper with.

Two guards on cost: the quadratic two-way candidate is skipped above a working-set
cap (it is 66x off the pace and once consumed an hour), and any candidate whose
calibration pass exceeds 5x the best is abandoned before its rounds.

### 4. Build the reporting drivers for that cell

`run_all.sh` re-configures with `TSL_COSORT_MEASURE_STYLE` and
`TSL_COSORT_MEASURE_WIDTH`, then builds everything. Each driver's `Simd` type is
`tsl_measure_simd_t<Key>` and each looks up `best_config.tsv` for
*that* cell and *the key width it is currently measuring* — `tsl_select_tuned<Key>`.
Instantiation and configuration have to agree; when they did not, a binary built for
one cell ran with another cell's knobs and still labelled the row `(tuned)`.

### 5. The five questions

| | question | reads | sweeps |
| --- | --- | --- | --- |
| Q1 | is the serial advantage real against sorts other people wrote | `best_config.tsv` | shapes, columns, key widths, workers |
| Q2 | quicksort against samplesort | `best_config.tsv` | shapes, rows in *and* out of cache, columns, key widths, workers |
| Q3 | what does cluster detection cost, and does offloading pay | `best_config.tsv` | cardinality, columns, key widths, workers, detectors |
| Q4 | how does it scale | `best_config.tsv` | threads 1..cores-per-node, rows, columns |
| Q5/Q6 | which variants are viable; what does the style cost | nothing — enumerates every variant itself | the corpus grid |

`run_paper.sh` reuses the `best_config.tsv` step 3 wrote rather than running Q0
again: two runs of the tuner could disagree, and the cheaper one used to decide what
got built.

Every row records the configuration it used and whether it came from the file, its
repetition count (adaptive: nine, then batches of four while the inter-quartile
range exceeds 5%, to a ceiling of 33), and the machine it ran on. A row still wide at
the ceiling is counted and called out in the summary.

## What is measured outside this flow

Two questions need paired measurement rather than reporting, so they are probes built
with `EXCLUDE_FROM_ALL` and run by hand:

* `probe_paired_styles` — the three implementation styles at a fixed lane count.
  This is how the style ordering was established: packed boolean masks beat
  hand-written intrinsics by 2-5%, lane-wide masks cost up to 46%.
* `probe_lane_curves` — whether a knob's response curve depends on lane count alone.
  It does not: the two eight-lane cells respond to the bucket count in opposite
  directions, because stream pressure is set by bytes rather than lanes.

## Running it

```bash
# on any host, after ./benchmarks/datagen/tpcds/{build_generator,generate}.sh
./run_all.sh                       # probes, builds, tunes, measures, writes CSVs
./run_all.sh --quick               # the same shape, narrowed, for checking the pipeline
```

Overrides worth knowing: `--styles` narrows Q0's cells on a slow host,
`--candidate-seconds` bounds a candidate absolutely, `COSORT_Q3_DETECTORS` forces a
detector list, `TSL_COSORT_ARROW_FETCH=ON` pins Arrow instead of using the system
one, and `-DTSL_COSORT_PHASES=true` builds a phase-attribution binary that must
never be used for published numbers.
