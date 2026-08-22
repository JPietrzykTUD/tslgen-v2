# test-sort

A standalone C++17 playground for SIMD lexicographic multi-column co-sorting on
generated TSL. Not part of the `tslc` compiler product: it consumes a generated
TSL release and is built by its own `CMakeLists.txt`.

## Layout

```
include/
  cluster_detection/        finding maximal equal runs in a sorted column
    scalar/                 the scan every other backend is compared against
    dsa/                    Intel DSA, synchronous and asynchronous
    iaa/                    Intel IAA: run detection, and the frequency-derived form
  sorting/
    common/                 pivot selection, shared types, the task executor
    primitives/             vector kernels shared by more than one algorithm:
                            the partition/replay step and the bitonic leaves
    quicksort/              the multi-column quicksort, direct and index movement
    sample_sort/            the samplesort co-sort and its two executors
benchmarks/
  datagen/                  dataset generation, manifests and reference images
  visualization/            plotting and sweep scripts
  *.cpp                     benchmark binaries; cosort_bench is the staged corpus
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

## Why `primitives/` exists

Neither sorter owns the vector kernels. `cosort_network.hpp` holds the
partition/replay step and `cosort_bitonic_leaf.hpp` the branch-free leaf, and
both are used by the quicksort *and* by the samplesort, which takes the bitonic
leaf as its base case. Filing them under either algorithm would misdescribe them.

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

```bash
cmake --preset clang && cmake --build --preset clang          # any host
cmake --preset dsa   && cmake --build --preset dsa            # a DSA host
QPL_ROOT=<prefix> cmake --preset iaa && cmake --build --preset iaa   # an IAA host
```

See `docs/benchmark-final.md` for what the corpus measures and why, and
`docs/samplesort-notes.md` for the samplesort's measured state.
