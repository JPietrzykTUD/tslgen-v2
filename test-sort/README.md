# test-sort

A standalone C++17 playground for SIMD lexicographic multi-column co-sorting on
generated TSL. Not part of the `tslc` compiler product: it consumes a generated
TSL release and is built by its own `CMakeLists.txt`.

## Layout

```
include/
  common/                   infrastructure that is neither sorting nor detection
  cluster_detection/        finding maximal equal runs in a sorted column
    scalar/                 the scan every other backend is compared against
    dsa/                    Intel DSA, synchronous and asynchronous
    iaa/                    Intel IAA: run detection, and the frequency-derived form
  sorting/
    common/                 pivot selection, shared types, the task executor
    primitives/             vector kernels shared by more than one algorithm:
                            the partition/replay step and the bitonic leaves
    quicksort/              the multi-column quicksort, direct and index movement
    sample_sort/            the samplesort co-sort, its two executors, and the
                            column loop that makes it multi-column
benchmarks/
  datagen/                  dataset generation, manifests and reference images
  visualization/            findings.py (the answers), report.py (one HTML page),
                            explore.py (the interactive app), and the sweep scripts
  paper_harness.hpp         the measurement method, once: verify then time,
                            median of nine with the IQR, machine state, drops
  bench_qN_*.cpp            one paper question each; see docs/benchmark-plan.md`) and the mechanism
(`docs/benchmark-workflow.md
  cosort_bench.cpp          the staged variant corpus
  bench_*.cpp               focused studies behind one decision each
  deprecated/               superseded, EXCLUDE_FROM_ALL, see its README
tests/                      one binary per subject
docs/                       plans, reports and measured notes
```

Every source includes by role, so a header says where it belongs:

```cpp
#include "sorting/quicksort/multicolumn_quicksort.hpp"
#include "cluster_detection/iaa/iaa_frequency_run_detector.hpp"
```

`include/`, `benchmarks/` and `benchmarks/datagen/` are the include roots.
Benchmark-local and dataset headers keep the bare names they use among
themselves.

## Why `common/` holds a borrow pool and not a thread pool

Three detector fleets had grown their own copy of the same object pool, and the
same bug had been found in two of them independently: a detector owns a device
job, so it cannot be shared, and giving each new thread a permanent slot needs as
many slots as (sorts x workers) rather than as many as run concurrently.
`common/borrow_pool.hpp` is that one concept, written down once.

The *executors* are deliberately not merged. `sorting/common/multicolumn_sort_tasks.hpp`
carries exception propagation off worker threads and the pending-work accounting
the asynchronous detectors need; the samplesort's executor carries per-worker
local stacks with a share threshold. Those are different schedulers, not two
copies of one, and the difference is measured: routing every task through a
shared queue -- which is what the task executor does -- capped the samplesort at
1.04x on 24 threads, against 8.2x with local stacks. Unifying them would mean
either giving up that, or reworking the scheduler every parallel quicksort
variant depends on. Four concurrency shapes exist in this tree and only the pool
was duplicated.

They do share one contract, and it is the smaller thing that was actually
missing. An asynchronous detector needs its host scheduler to keep the sort alive
while a device still owes it ranges, to poll rather than sleep when the only
outstanding work is on that device, and to accept a range from any thread.
`sorting/common/pending_range_queue.hpp` is that contract for a worklist
scheduler, the way `TslTaskExecutor` is for the task tree, so the samplesort
carries `rle=*_async` without routing its ranges through one shared queue -- which
is the thing that capped it at 1.04x.

## Why `primitives/` exists

Neither sorter owns the vector kernels. `cosort_network.hpp` holds the
partition/replay step and `cosort_bitonic_leaf.hpp` the branch-free leaf, and
both are used by the quicksort *and* by the samplesort, which takes the bitonic
leaf as its base case. Filing them under either algorithm would misdescribe them.

## Two lexicographic co-sorts

`sorting/quicksort/` and `sorting/sample_sort/` both solve the same problem --
order a table by several columns, leaving the columns untouched and the
permutation in an index -- and both take the same detector seam, so the `rle=`
backends apply to either. They disagree about the middle: a partition around one
pivot against a K-way split on sampled splitters. `docs/samplesort-notes.md` has
the head-to-head.

## Why there is no directory per variant axis

The benchmark corpus varies `execution × discovery × partition × leaf × movement`,
and it is tempting to give each axis a directory. That would describe something
the code does not do. Those axes are template parameters and runtime branches of
one class, `TslMultiColumnQuickSorter`: partition, leaf and the hybrid fill
threshold are template arguments, the three executions are member functions, and
discovery is an enum branched inside `sort_columns`. Only movement maps to
separate files, direct against index.

The variant space is written down once, as types, in
`benchmarks/cosort_plan.hpp` -- `TslVariant` plus `tsl_all_variants` is what
enumerates the registered algorithm names. A directory tree saying the same thing
would be a second representation that can drift from the first, and only one of
the two is checkable.

## Producing the paper's numbers

One command, from a clean checkout: it configures, generates the TPC-DS/DSB key
columns, builds and runs, skipping whatever is already done.

```bash
./run_all.sh                                  # results/$(hostname)
./run_all.sh results/<host> --quick           # prove the pipeline, ~10 min
./run_all.sh results/<host> --scale 10        # a larger scale factor
./run_all.sh results/<host> --no-baselines    # skip Q1's external libraries
```

The preset comes from what `/dev` actually has, and is always a *measurement*
preset: the sorters' counters are compiled out, so a published run collects nothing
while it measures. `run_paper.sh` refuses a build without that, which is why the
step below names a `bench*` preset and not `clang`.

`run_paper.sh` is self-contained: given a results directory it configures a build
tree from this checkout, builds it, measures, and writes the report.

```bash
./run_paper.sh --results results/<host>                          # everything
./run_paper.sh --results results/<host> --quick                  # prove the pipeline
./run_paper.sh --results results/<host> --stages q3_detection,report
./run_paper.sh --results results/<host> --cxx clang++ --profile sapphire_emerald_granite_rapids
./run_paper.sh --results results/<host> --scale 10               # real TPC-DS keys
./run_paper.sh --list-stages                                     # the stage names
./run_paper.sh --help                                            # every flag
```

The build tree defaults to `<results>/build`; `--build DIR` reuses an existing
one. `--source`, `--cxx`, `--cc`, `--profile`, `--tsl-version`, `--jobs`,
`--baselines` and `--reconfigure` cover the build; `--stages`, `--scale` /
`--datasets`, `--workers` and `--max-workers` cover the measurement. The TSL
profile is auto-detected; `--profile` is for overriding that deliberately. The older positional form
`run_paper.sh <build-dir> <results-dir>` still works.

It refuses to measure from a build whose fetched TSL is not the version it was
configured for, from an instrumented build, from a tree whose `TSL_PROFILE=auto`
resolved to the scalar profile, or on a machine that is not idle -- each of those
has produced a directory of numbers that looked fine and was not. `--allow-busy`
overrides the last one and says so in the output. Interference that arrives *after*
a run starts cannot be refused, only recorded: every row carries
`preempted_passes`, and the run ends by naming any CSV whose medians were measured
under contention.

Three ways to read a results directory, all over the same analysis, so none of
them can disagree with the others about what the numbers say:

```bash
python3 benchmarks/visualization/findings.py --results <results-dir>
python3 benchmarks/visualization/report.py   --results <results-dir> --out report.html
pip install streamlit pandas altair
streamlit run benchmarks/visualization/explore.py -- --results <results-dir>
```

`findings.py` prints each question's answer with the counts behind it; `report.py`
writes one self-contained page -- an answer, its figures and its caveats per
question, no network and no Python needed to read it; `explore.py` is the same
thing interactive, with a free-form pivot per question.

`docs/benchmark-plan.md` says which question each binary answers and under what
method. One CSV schema across all of them, so a figure is a query over the results
directory rather than a re-run, and the runner refuses to mix two hosts' numbers
in one directory.

## Checking a refactor

`snapshot.py` records test results with their exact check counts, a bounded set
of timings and the shape of the tree; `compare_snapshots.py` diffs two of those.
Read `compare_snapshots.py`'s header first: it says what that comparison can and
cannot resolve, measured rather than assumed. `snapshot-baseline.txt` is the
current reference.

```bash
./snapshot.py <build-dir> after.txt --dsa <dsa-build> --iaa <iaa-build>
./compare_snapshots.py snapshot-baseline.txt after.txt
```

## Building

Development presets keep the counters and diagnostics; `bench*` presets compile
them out and are the only ones `run_paper.sh` accepts.

```bash
cmake --preset clang && cmake --build --preset clang          # any host, counters on
cmake --preset dsa   && cmake --build --preset dsa            # a DSA host
QPL_ROOT=<prefix> cmake --preset iaa && cmake --build --preset iaa   # an IAA host

cmake --preset bench-dsa-baselines            # measurement, DSA, Q1 baselines
cmake --preset bench-iaa-baselines            # measurement, IAA, Q1 baselines
cmake --preset bench                          # measurement, no accelerator
cmake --preset phases                         # phase timers on; never for figures
```

**clang 22 or newer.** The generated TSL's clang implementation family needs clang
22's elementwise builtins; below that the style axis measures TSL's scalar
fallbacks rather than the styles. Newer is fine.

`run_all.sh` discovers the newest clang++ on `PATH` that is at least 22 and derives
the matching C compiler, because DML's kernels are C and a mismatched pair fails at
configure time. Override with `TSL_COSORT_CXX` / `TSL_COSORT_CC` -- deliberately not
`CXX`, which is often already set to something unrelated in a container.

The `clang` preset, and everything inheriting it, pins `clang++-22` and `clang-22`
by name, so on a host with only a newer clang a manual configure needs both
overridden:

```bash
cmake --preset bench-dsa-baselines \
      -DCMAKE_CXX_COMPILER=clang++-24 -DCMAKE_C_COMPILER=clang-24
```

`run_all.sh` passes both for you. It also removes a build directory whose
`CMakeCache.txt` records a different source path -- which happens when a tree is
copied between machines, and which cmake otherwise reports as a cache to "reedit"
rather than a directory to delete.

Q1's external baselines (`TSL_COSORT_ENABLE_BASELINES=ON`) fetch IPS4o and
x86-simd-sort at pinned commits and build oneTBB if the system has none; TBB and
libatomic are required because without them `std::sort(execution::par)` runs
serially and IPS4o loses its 16-byte atomics, either of which would weaken a
competitor rather than remove it. Arrow is optional -- `libarrow-dev` -- and its
absence shows up as drops naming the reason.

See `docs/benchmark-final.md` for what the corpus measures and why, and
`docs/samplesort-notes.md` for the samplesort's measured state.
