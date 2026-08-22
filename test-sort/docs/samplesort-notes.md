# Samplesort co-sort: measured notes

What the implementation in `samplesort_cosort.hpp` / `samplesort_executor.hpp`
measured, which specified parameters changed, and which claims in the
specification did not survive being re-run.

Host: Intel Xeon w5-3425 (Sapphire Rapids), 24 cores, `performance` governor,
~4.1 GHz observed under load, clang 22, `-O3 -march=native`, TSL `v0.2.9`.
That is the machine the specification's numbers were taken on, so the
disagreements below are not a hardware difference.

All figures are medians of five, `n = 2^24`, single threaded.

## Headline

Single threaded:

| | u32 | u64 |
| --- | --- | --- |
| `TslMultiColumnQuickSorter::sort_key` + index, network leaf | **21.8 ns/element** | 42.9 |
| samplesort, network base case | 25.4 | **33.7** |
| `std::sort` over `(key, index)` pairs | 66.1 | 69.7 |

**On threads, against the playground's own parallel task tree on the identical
problem** -- `sort_key_parallel` with the index as its one payload:

| workers | samplesort u32 | quicksort u32 | samplesort u64 | quicksort u64 |
| --- | --- | --- | --- | --- |
| 1 | 25.43 | **21.85** | **34.02** | 42.93 |
| 2 | 15.83 | **12.37** | | |
| 4 | 8.79 | **6.92** | | |
| 8 | 5.25 | **4.68** | **6.16** | 8.86 |
| 16 | **3.31** | 4.13 | | |
| 24 | **3.11** | 3.53 | **3.01** | 7.14 |

**Samplesort scales better and crosses over.** 8.2x on 24 threads for u32 and
11.3x for u64, against 6.2x and 6.0x for the task tree, so it goes from 1.16x
behind at one thread to 12% ahead at 24, and from 1.26x ahead to 2.4x ahead for
u64. That is the structural argument the whole design rested on, and it is the
first measurement that supports it: phases 2 and 4 are independent per chunk and
the task list is explicit, where a quicksort partition is inherently sequential
within a range.

Per pass, u32, K=16: classification 1.01, distribution **1.16** (target 1.30),
combined 2.17. Chunked bookkeeping from 1 to 16 chunks single-threaded: +1.0%.

The first two rows are the playground's existing sorter on exactly this problem
-- one key column, the index as its single replayed payload -- so this is
like-for-like and not a comparison against a general-purpose sort.

On one thread samplesort still loses on u32: a tuned single-pass partition with
`compress`/`expand` beats a classify-then-scatter pass pair at this size. What
changes the answer is threads, above.

## Acting on the profile

The profile below said the two vector kernels are a third of the runtime and the
base case is nearly half. Two changes followed from it.

**A hybrid base case (45.6% -> 35.3%).** The bitonic leaf on its own was a 50%
regression, measured earlier: it pays its full capacity on ranges averaging 38
elements. Adding the same fill test the direct sorter's hybrid leaf uses -- take
the network only above `BaseFillPercent` of its capacity, insertion below --
turns it into the largest single win here. u32 end to end 30.7 -> 25.4, u64
36.9 -> 33.7.

Two things about it were counter-intuitive enough to be worth stating:

* **The network must be wide, not matched to the average range.** Sizing its
  capacity to the 38-element average (rows=4, capacity 64) measures 28.7 against
  25.4 for the full 256. The average is not what matters: the large ranges are
  few but hold most of the elements, and a narrow network hands exactly those
  back to the quadratic leaf. `BaseRows` is therefore derived as
  `BaseCase / lanes`, so the capacity always covers the whole base case.
* **`base_case` must not be clamped to the capacity.** Clamping buys an extra
  partition level wherever the capacity is smaller, which at u64 cost more than
  the network saved -- it was the difference between the network losing to
  insertion and beating it.

`TslCoSortBitonicLeaf` gained a defaulted `Rows` parameter to make this
measurable; every existing instantiation is unchanged.

**Cheaper sampling (16.2% -> 14.7%).** Two changes, one of which did nothing:

* Replacing `rng.next() % count` with Lemire's multiply-shift: **no measurable
  effect**. 128 divisions per step sounded expensive, but the draws are
  independent random loads and the divisions hide under their latency. Kept
  anyway, since it is strictly less work.
* Scaling the sample to the range (`max(2K, count/4)`, capped at `Oversample * K`):
  about 1.5%. Most partition steps sit near the bottom of the tree, where 128
  draws can be a quarter of the range and the splitter quality cannot matter --
  every bucket goes straight to the base case regardless.

Sampling is the one place where §4.1's claim that "the sample sort is not on the
critical path" is closest to wrong and still hardest to fix: it is 15% of the
runtime and neither change moved it much.

## Multi-column

`samplesort_multicolumn.hpp` is the column loop that turns the single-key
samplesort into a lexicographic co-sort, which is what makes the `rle=` detector
axis apply to it. Index movement necessarily -- samplesort's premise is that the
permutation lives in an index column -- so the loop is the indirect quicksort's:
materialise the active column through the index, samplesort it, detect the equal
runs, recurse into each on the next column. Level 0 is a copy rather than a
gather, and only rows inside a surviving range are ever materialised.

Against the indirect quicksort on the identical problem, 2^21 rows, four columns,
u32, `rle=scalar`, ns/element:

| shape | samplesort w=1 | quicksort w=1 | samplesort w=24 | quicksort w=24 |
| --- | --- | --- | --- | --- |
| `low_cardinality_d4` | 17.5 | **13.3** | 7.9 | **4.9** |
| `unique_last_g64` | 49.5 | **45.5** | **11.8** | 12.5 |
| `skewed_zipf_s1` | **57.4** | 95.2 | **15.0** | 31.1 |
| `unique_first` | 27.2 | **19.2** | 7.5 | **5.5** |

`std::sort` over row indices with a lexicographic comparator is 93 to 228 on the
same cases, so both are 4-15x that. Samplesort wins on the heavy-tailed shape by
1.7x at one thread and 2.1x on 24, loses on the others, and the split is the same
one the single-key numbers showed: it is better where the data punishes a binary
partition and worse where a tuned single-pass partition is already right.

### The parallel form needed two corrections, both measured

The obvious construction -- call the parallel samplesort for every range above a
size threshold -- was **slower than one thread**: 145 ns/element against 51 on
`unique_last_g64`, and monotonically worse with more workers. The parallel
executor builds a thread pool per call, and the driver was calling it 33 times.
The standalone samplesort benchmark calls it once, which is why this never
surfaced there.

So the driver is two phases, like the samplesort's own executor: fan a single
range across threads while one range dominates, then hand whole ranges to a
persistent pool that sorts each serially. That took `unique_last_g64` from 145 to
10.7 at 24 workers.

The second correction is the criterion for phase one. Fanning "until there are as
many ranges as workers" is the intuitive rule and it is wrong: a key with four
distinct values yields four children per split, so reaching 24 ranges takes eight
fans, each on a smaller range, and the pool per fan costs more than the split
gains -- 20.6 ns/element against 12.4. Fanning only a range that holds at least
half the rows left gives exactly one fan on every shape measured, and both shapes
then scale monotonically.

Ascending only: the samplesort compares keys directly and takes no order
argument, so a descending column needs the comparison inverted in the kernels
rather than a flag in the driver. `sort_index` rejects it rather than sorting
wrongly.

## Threading

`samplesort_parallel_executor.hpp` contains no kernel and no phase logic. It
calls the same `tsl_samplesort_partition_step` as the sequential executor and
differs only in who runs the chunk bodies and who pops the queue -- which is what
`TslSampleSortSerialChunks` and the `ChunkRunner` parameter exist for. Two stages,
because the task tree starts with a single task:

* **Descent.** One task at a time, its phases 2 and 4 fanned across `workers`
  chunks with the phase-3 reduction between them. Ends once the queue holds
  `workers` independent tasks, which at K=16 is two levels -- so it forks a few
  dozen times over a whole sort, not once per step.
* **Task parallel.** Every worker pops whole tasks and runs them with one chunk.
  Ranges are disjoint, so the workers share one `bucket_ids` array and keep only
  the per-step reduction arrays private.

One thing about stage 2 was worth an order of magnitude. Routing every task
through the shared queue **capped the whole sort at 1.04x on 24 threads**: a run
produces about 440k tasks, almost all of them base-case ranges, and a mutex plus a
`notify_all` per task is a thundering herd, not a scheduler. Each worker now keeps
a local LIFO stack and publishes only tasks at or above `base_case * K` -- the
ones that will fan out again. Small work stays where it was produced, which is
also where its data is warm. That single change took 24 threads from 1.04x to
8.2x.

The termination condition needed care for a related reason: the worker that
observes "every worker idle and the queue empty" must decrement the idle count on
its way out, which falsifies that same condition for everyone still waiting on it.
It is a latch, not a re-tested predicate.

Validation: 1685 checks, and the parallel runs are checked at 2, 3, 8 and 24
workers across nine input shapes. The permutation may legitimately differ from the
sequential one where keys tie, so the test demands the *sorted key image* match
exactly, which it does. Clean under ThreadSanitizer, and under
`-fsanitize=address,undefined`.

## Section 9.2: the stream cliff does not move, it stops mattering

`bench_samplesort_streams` runs the deferred experiment: T threads each
distributing their own chunk into their own output region with K buckets, timed
with and without the index column, so the difference is the second column's cost
-- which is what the original cliff was measured on.

**The cliff reproduces exactly at one thread.** u32 penalty in ns/element:
0.356 at K=8, 0.413 at K=16, 0.452 at K=32, then **1.938 at K=64**. That is a
4.3x jump at 128 streams, against the 3.3-3.9x the specification reports. u64 is
0.834 / 0.771 / 0.968 / **3.390**, a 3.5x jump. So the harness and the original
measurement agree.

**It does not track total streams.** The ratio of the K=64 penalty to the K=32
penalty, by thread count:

| threads | u32 | u64 | total streams at K=64 |
| --- | --- | --- | --- |
| 1 | 4.29x | 3.50x | 128 |
| 2 | 3.34x | 7.52x | 256 |
| 4 | 2.54x | 4.03x | 512 |
| 8 | 3.21x | 3.41x | 1024 |
| 16 | 1.22x | 1.49x | 2048 |
| 24 | **0.90x** | **0.99x** | 3072 |

At 24 threads and K=64 there are 3072 concurrent write streams -- 24 times past
the cliff the single-core measurement found -- and **there is no penalty at all**.
Meanwhile T=4/K=16 and T=8/K=8 both sit at exactly 128 total streams and show no
cliff either.

So `2*T*K` is the wrong statistic. The cliff tracks streams **per core**, which is
consistent with the specification's own guess at the mechanism -- L1
write-combine buffers, DTLB entries, store-buffer capacity -- and it is a
per-core resource that does not become a shared one. What happens instead is that
at high thread counts distribution goes bandwidth-bound and the per-core stream
limit stops being the binding constraint. The direction the specification worried
about, contention moving the constraint to LLC associativity or DRAM banks and
forcing K *down*, does not happen.

**And a larger K still does not pay, for an unrelated reason.** End to end:

| type | K | 1 worker | 8 workers | 24 workers |
| --- | --- | --- | --- | --- |
| u32 | 8 | **26.28** | 5.51 | 3.46 |
| u32 | 16 | 26.66 | **4.34** | **2.33** |
| u32 | 32 | 32.56 | 5.22 | 2.97 |
| u64 | 8 | 37.99 | | 4.31 |
| u64 | 16 | **33.51** | | 3.81 |
| u64 | 32 | 36.06 | | **3.69** |

K=16 wins at 8 and 24 workers for u32 and at one worker for u64; K=32 is within
3% of K=16 for u64 at 24 workers, which is noise. K=32 loses 22% at u32/T=1 and
that is nothing to do with streams -- 64 per thread is inside the flat region.
It is classification: 31 splitters instead of 15 roughly doubles the comparison
sweep, and the pass count only falls from 4.65 to 3.92.

**So K is set by classification cost against pass count, not by the write-stream
cliff.** The cliff only bites at K=64, which is outside the useful range for
other reasons. The `2 * K <= 64` assertion in the kernels is therefore a
single-core bound that measurement shows relaxes with thread count; it is kept
because nothing above K=32 is worth compiling anyway, not because it is the
binding constraint it was thought to be.

## In place

`TslSampleSortMovement::InPlace` replaces the scatter into a second pair with a
permutation inside the range: each element is carried to its bucket's cursor and
whatever was there is examined next, so every element is written at most once and
the range costs O(count) swaps. The bucket ids travel with the elements, because
they were computed for the original positions.

| | out of place | in place | |
| --- | --- | --- | --- |
| u32 end to end | 25.8 | 41.8 | +62.1% |
| u64 end to end | 34.0 | 45.7 | +34.3% |
| bytes per element | 16 | **8** | |
| copy-back | 0.65 elem/elem | **none** | |

So the simple in-place form is not a speed win at any size measured -- it trades
a vectorised scatter for a scalar element-at-a-time walk, and that costs far more
than the 1.8% the copy-back was worth. It buys exactly one thing: footprint. At
the specification's stated `n = 4e9` with 32-bit keys that is 32 GiB rather than
64, which can be the difference between fitting in a machine and not, so it is
kept as an option rather than removed.

It also gives up the chunk parallelism of phase 4: a whole-range cycle
permutation is not divisible into independent chunks, where the scatter is.
Recovering the vector width *and* the chunk split is precisely what IPS4o's block
permutation does -- distribute into per-bucket block buffers, then permute whole
blocks -- and this measurement is the price it would be paying for.

## Where the time actually goes

The two kernels the specification's performance section is about are 31% of the
runtime. Profiled build (`Profile = true` on the executor, which costs about 8%
in clock reads, so shares matter more than absolutes), u32, K=16, `n = 2^24`:

| phase | before | after | share now |
| --- | --- | --- | --- |
| base case | 15.02 | **10.74** | 35.3% |
| distribute | 5.51 | 6.91 | 22.7% |
| classify | 4.80 | 5.93 | 19.5% |
| splitter selection | 5.33 | **4.47** | 14.7% |
| queue and task admin | 1.80 | 1.86 | 6.1% |
| copy back | 0.50 | 0.55 | 1.8% |

("before" is the insertion base case and unscaled sampling; classify and
distribute rise only because the profiled total fell, their absolute cost is
unchanged. 440020 base-case ranges averaging 38.1 elements.)

u64 is the same shape: base case 38.8%, splitters 13.9%, the two kernels 41%.

Two consequences worth stating plainly.

**The base case dominates, and its ranges are nothing like `BASE_CASE`.** They
average 38 elements, not 256, because a range just above the threshold splits into
K buckets and each of those is a base case. That is why the base-case sweep looks
flat between 128 and 256 -- changing the threshold trades range count against
range size in almost exactly offsetting amounts -- and why the bitonic leaf was
catastrophic: it pays a fixed 256-element cost on a 38-element range. A sort
tuned for ~32-64 elements is the single largest available win in this
implementation, worth up to 10 ns/element of the 30.

**Splitter selection is not free.** 16% for 128 random draws plus a 128-element
`std::sort` per step, over 29364 steps. §4.1 says the sample sort "is not on the
critical path"; at this K and base case it is a sixth of the runtime. Sampling
strided rather than randomly, or scaling the sample with the range, is the second
largest win.

Against that, the two items usually named next:

* **In-place block permutation** removes the copy-back: 1.5%. Its real argument is
  halving peak memory, not speed.
* **Multithreading** divides every row above by the same factor. It changes the
  absolute numbers, not the ranking against a parallel competitor -- and the
  competitor here, `TslMultiColumnQuickSorter`, already has parallel and
  deep-parallel executors. Threading samplesort makes it comparable to those, not
  automatically better than them.

Both are still worth doing for their own reasons. Neither is where the 1.4x gap
on u32 lives.

## Claims that did not reproduce

### 1. The 0.40 ns/element classification target is missed, but there is no floor

**An earlier version of this file claimed 0.473 was a hard floor set by port 5.
That claim was wrong and is withdrawn.** It rested on a model its own control
case refutes: if `vpcmpud` + `vpmovm2d` are 30 forced-p5 uops per vector, then
merge-masked add -- `vpcmpud` plus `vpaddd zmm{k}`, which can issue on p0 -- has
15, and should have been about twice as fast. It measured identical. Either the
masked adds are pinned to p5 for a reason the model does not capture, or p5 is
not the binding constraint; without hardware port counters (`perf` is not
available here) the mechanism stays unidentified.

A formulation that touches no mask register at all settles the practical
question. `sign = (x - s) >> 31` is `-1` when `x < s`, so `S + sum(sign)` is
`count(x >= s)`: three uops per splitter, no k-registers, bit-identical output.

| working set | `vpmovm2d`+`vpsub` | merge-masked add | sign-shift |
| --- | --- | --- | --- |
| 32 KiB (L1) | 0.491 | 0.506 | **0.378** |
| 1 MiB (L2) | 0.484 | 0.469 | **0.377** |
| 64 MiB (DRAM) | 0.700 | 0.702 | 0.680 |

So 0.378 beats the supposed floor by 23% and comes within 11% of the target. Two
things keep it out of the shipped kernel for now:

* **It has a precondition.** `x - s` must not overflow, which needs the keys
  biased into a half-range. The bias itself is free -- one `vpsubd` per vector
  folded into the load, not per splitter -- but establishing the bias needs the
  range, i.e. one min/max pass over the input, amortised across levels.
* **At the size §9 specifies it does not matter.** All three forms converge
  within 3% at 64 MiB: classification there is memory-bound, not compute-bound.
  The form only pays at the deeper, cache-resident levels.

That memory bound is what the bucket-id width addresses instead, below.

### 2. Merge-masked add is not 1.8x slower

§5 rejects merge-masked add on a measurement of 0.637 against 0.341. Re-run as
the only difference between two otherwise identical kernels:

| working set | `vpmovm2d` + `vpsub` | merge-masked add |
| --- | --- | --- |
| 32 KiB | 0.473 | 0.462 |
| 1 MiB | 0.475 | 0.495 |
| 64 MiB | 0.792 | 0.795 |

They are the same to within noise, which is what the port analysis predicts:
both forms are limited by the 15 port-5 compares, and what follows the compare is
not the constraint. The implementation keeps the `vpmovm2d` form — clang
generates it from `tsl::mov_maskz` + `tsl::add` — but the stated reason for
preferring it does not hold on this machine.

### 3. A sorting network is not faster at the base case

§7 leaves a TODO saying a sorting network would beat the scalar insertion sort.
It does not, by a wide margin. `TslCoSortBitonicLeaf` — the playground's existing
branch-free leaf, capacity 256 for u32/AVX-512 — as the base case instead:

| base case | insertion | bitonic network |
| --- | --- | --- |
| 64 | 36.0 | 96.9 |
| 128 | 33.7 | 75.4 |
| 256 | 33.1 | 46.2 |

The network's cost does not depend on how full the range is, and a samplesort's
terminal ranges are mostly far below the capacity, so most of that fixed cost is
spent sorting padding. The gap narrows as the base case approaches the capacity,
which is the same fill-ratio effect measured in `bench_hybrid_leaf`. The TODO is
resolved: keep insertion. `TslSampleSortBase::Network` stays available because it
is the measurement, not because it is the answer.

### 4. Equality buckets must be adaptive, and then the stream budget is fine

§3.1 fixes K=16 from a stream cliff and concludes there is headroom for a third
column; §4.2 then prefers equality buckets, which would make the bucket count
`2S+1` and the stream count 62 rather than 32, removing that headroom.

The resolution is to allocate an equality bucket only for a splitter whose value
*actually* repeats, which the sample already knows: a value occupying more than
one splitter slot's worth of the sorted sample. A high-cardinality key then gets
none, and costs exactly what `Ordered` costs. Measured effect of making the
policy adaptive rather than unconditional, u32, `n = 2^24`:

| | unconditional | adaptive |
| --- | --- | --- |
| classification | 1.419 | 0.911 (= `Ordered`'s 0.905) |
| distribution | 1.523 | 1.377 |
| end to end | 33.9 | 32.5 |
| write streams | 62 always | 32 on random keys |

`max_buckets_used` and `equality_buckets_allocated` are published per run, so a
run reports where it actually landed rather than assuming the worst case. On
random keys it reports 16 buckets and zero equality buckets; on the
duplicate-heavy configurations it reports up to 22 buckets and 1.4 M equality
buckets allocated -- which is exactly when they are worth their streams.

### 5. The bucket-id width had to be measured in the phase that reads it

An earlier version of this file measured key-width bucket ids in classification,
found they cost nothing, and left it there. That was the wrong phase:
distribution *reads* that array, and at u64 it was reading 8 bytes of id per
element. Narrowing the ids to bytes, measured on distribution alone:

| | key-width id | byte id | |
| --- | --- | --- | --- |
| u32, 16 buckets | 1.545 | 1.275 | -17.5% |
| u64, 16 buckets | 3.022 | 2.442 | -19.2% |
| u64, 32 buckets | 3.203 | 2.307 | -28.0% |

Byte ids do cost classification about 0.10 ns/element -- the narrowing store is
an extra uop that key-width ids avoid -- and save about 0.22 in distribution, so
they are a net win of roughly 0.12 per pass. With them, **u32 distribution meets
its 1.30 target at 1.16**, and u64 end to end improves from 39.3 to 35.4.

TSL has no `convert_down` for a 32- or 64-bit lane to a byte lane on AVX-512, so
`tsl_samplesort_store_byte_ids` and `tsl_samplesort_load_byte_ids` are written
against `_mm512_cvtepi32_epi8` / `_mm512_cvtepu8_epi32` directly. They are the
only two functions in the sorter that leave TSL, and they are what a future TSL
primitive would replace. `TslSampleSortIds::KeyWidth` keeps the portable path for
any target where the narrowing pair is absent.

## Parameters changed, with the measurement

* **`BASE_CASE` stays 256.** Swept 16/32/64/128/256: 48.4, 40.5, 36.0, 33.7,
  33.1. Smaller is worse — the partition-step count rises faster than the
  quadratic leaf falls (432953 steps at 16 against 28821 at 256).
* **K is not a sharp optimum here.** End to end at K=8/16/32, ordered:
  33.5 / 32.8 / 32.8 for u32, and 39.3 (K=16) / 41.3 (K=32) for u64. §3.2 reports
  K=16 as the argmin of a per-pass cost model; on this build K=16 and K=32 are
  indistinguishable for u32. K=16 is kept, and it stays a template parameter.
* **Bucket ids are bytes by default** (`TslSampleSortIds::Byte`); see finding 5.
* **The per-chunk histogram uses four interleaved tallies** (§6.2's suggested
  fix). It made no measurable difference at K=16 and is kept because it is free
  and the dependency it removes grows with duplicate density.

## Targets met

* **Chunked bookkeeping: +0.9%** from 1 to 16 chunks single-threaded, against a
  budget of 5%. The phase-3 reduction walks bucket-outer/chunk-inner so each
  bucket's column of per-chunk counts is touched once.
* **Distribution: 1.52 ns/element/pass** (u32, K=16) against a 1.30 target — over,
  but under the 1.60 that §9 says should trigger a stream-count investigation.
  u64 is 2.79, which is over that line; 31 buckets is 62 streams and that is the
  first thing to check, per §3.1.

## What is not done

* Threading. The structure is in place — chunk-scoped kernels taking absolute
  positions, four separable phases, an explicit task queue — and the executor is
  138 lines that touch no kernel. The chunk-invariance test passes at 1, 2, 3 and
  7 chunks, which is what makes that structural claim testable rather than
  asserted.
* The deferred experiment of §9.2 (sweep T × K and find where the stream cliff
  moves) is still the first thing to run after threading. With adaptive equality
  buckets the typical stream count is `2·T·K` as §3.1 assumed, not double it.
* The mask-free classification form of finding 1, which needs the bias pass.
* **IPS4o's *block* permutation.** The simple in-place form is implemented and
  measured above; the block form is what would make in-place competitive rather
  than merely smaller, and it is the one piece of the original specification's
  "future work" still outstanding.
* An IPS4o baseline, which is the yardstick that matters now that the parallel
  numbers exist.
* The mask-free classification form of finding 1, which needs the bias pass.
* An IPS⁴o baseline. `std::sort` over pairs is the wrong yardstick for a
  samplesort and these numbers should not harden without it.
* In-place block permutation (IPS⁴o's technique).
* No CPUID dispatch for VPOPCNTDQ: choosing an implementation per extension is
  TSL's job, and `tsl::popcnt` resolves natively on this target. A host without
  VPOPCNTDQ gets TSL's composed form, correct and slower, decided when the sorter
  is instantiated rather than at run time.
