# Synthetic Dataset Shapes for Multi-Column Sort Evaluation

## Purpose

A multi-column co-sort has three cost sources that vary independently:

1. **Discrimination depth** — how many columns must be inspected before tuples
   are ordered, i.e. how much sorting work happens at each column level.
2. **Group structure** — how the rows that are still tied are distributed over
   equal-prefix groups, which sets both the per-group sort cost and the number
   of independent units of work.
3. **Data movement** — how many columns follow the active key at each level, and
   what permutation must be applied to them.

A dataset family is useful only if it varies one of these while holding the
others fixed. The shapes below are chosen on that basis. Unless stated
otherwise, all sort columns hold 32-bit or 64-bit unsigned integers of one
common width, all columns are sort keys, and rows are presented in random
order.

## Descriptor: what characterizes an instance

For a sort over $(K_1,\ldots,K_m)$ with $N$ rows, let

$$D_j = \bigl|\{(K_1,\ldots,K_j)\}\bigr|$$

be the number of distinct prefixes of length $j$, and let $G_j$ be the multiset
of **equal-prefix group sizes** at level $j$ (the sizes of the classes induced by
$(K_1,\ldots,K_j)$, so $|G_j| = D_j$ and $\sum G_j = N$), with $G_0 = \{N\}$
denoting the single undivided input range.

$D_j$ alone does not determine cost. Two instances with identical
$(D_1,\ldots,D_m)$ can differ by an order of magnitude:

```text
N = 1,000,000 rows, D_1 = 500,000 distinct first-column values

instance A:  500,000 groups of size 2
             -> level 2 sorts 1,000,000 rows in 500,000 tiny tasks

instance B:  499,999 singletons + 1 group of size 500,001
             -> level 2 sorts 500,001 rows in exactly 1 task
```

Both have the same $D_1$; A is dominated by per-task overhead, B by a single
large subsort that also determines whether parallel work is exposed at all. The
canonical descriptor is therefore $(D_j, G_j)$, from which two derived
quantities are reported per instance:

$$R_j = \sum_{g \in G_j,\; |g| \ge 2} |g|
\qquad\text{(rows still tied after $j$ columns, $R_0 = N$)}$$

$$W = \sum_{j=1}^{m}\;(m-j+1)\;\sum_{g \in G_{j-1},\; |g| \ge 2} |g|\log_2|g|$$

$R_j$ predicts run-discovery volume. Sorting column $j$ covers the nontrivial
groups of $G_{j-1}$, so a post-sort detector scans $R_{j-1}$ values at that
level and $\sum_{j=0}^{m-2} R_j$ in total — the last column is never scanned,
because no column follows it.

$W$ is a **column-weighted work estimate**: a sort at level $j$ moves the active
key plus the $m-j$ columns that follow it, and no earlier column, so work at
deeper levels is cheaper per row. This is why depth is not simply a multiplier —
`Unique-Last` spends its final level moving a single column, while
`Unique-First` does all of its work moving all $m$.

Presortedness needs its own descriptors, given as the fraction of adjacent
in-order pairs (or Kendall-tau distance to the target order) and, where the
shape prescribes it, the number of ascending runs.

Every instance is reported with $N$, $m$, key width, generator seed, the
measured $D_j$, a $G_j$ histogram bucketed against the *configuration's own*
thresholds below, $R_j$, and $W$. Measured, not intended: a generator bug that
changes $D_2$ silently invalidates a comparison, and the measured descriptor
makes results reproducible and cross-shape normalizable.

### Group sizes relative to implementation thresholds

Cost is not a smooth function of group size; the implementation has structural
breakpoints, and a group-size distribution should be positioned deliberately
against them rather than by accident:

| Regime | Boundary | Effect |
|---|---|---|
| singleton | 1 | no next-column work at all |
| sub-vector | $< 2 L$ | scalar partition tail only, the SIMD loop never runs |
| leaf | $\le 64$ insertion, $\le C$ network | sorted by the leaf, never partitioned |
| serial task | $<$ task threshold (default 4096) | executed inline, no queue entry |
| partition offload | $<$ partition threshold (default 16384) | stays on the producing worker |

Two datasets with the same $D_1$ but mean group sizes of 32 and 32,768 exercise
disjoint code paths. Each shape below therefore states its group-size regime,
and instances should be generated at several regimes rather than one.

Crucially, **two of those boundaries move with the SIMD configuration**, so a
group size is only meaningful relative to the configuration it runs on. With
lane count $L$ and a network leaf of $16$ register rows, the capacity is
$C = 16L$:

| element | register | $L$ | SIMD-loop minimum $2L$ | network capacity $C$ | insertion threshold |
|---|---|---|---|---|---|
| u32 | 128-bit | 4 | 8 | 64 | 64 |
| u32 | 256-bit | 8 | 16 | 128 | 64 |
| u32 | 512-bit | 16 | 32 | 256 | 64 |
| u64 | 128-bit | 2 | 4 | 32 | 64 |
| u64 | 256-bit | 4 | 8 | 64 | 64 |
| u64 | 512-bit | 8 | 16 | 128 | 64 |

The leaf boundary therefore spans $32 \ldots 256$ across the six
configurations — a factor of eight. A group-size distribution chosen as absolute
numbers lands in different regimes on different configurations, so a
cross-configuration comparison would be measuring regime changes rather than
implementation efficiency. **Group sizes are therefore specified as multiples of
the configuration's own $C$, $2L$ and task threshold**, and only the derived
absolute sizes differ per configuration.

### Network-leaf fill ratio

The network leaf sorts a fixed, padded block: a range of any length
$2 \le n \le C$ is padded to $C$ with the type maximum and run through the
complete Batcher network, so **its cost does not depend on $n$**. Per-row leaf
cost is proportional to $C/n$, which makes the fill ratio

$$\phi = \frac{\mathbb{E}[|g| \mid 2 \le |g| \le C]}{C}$$

a first-class dataset parameter rather than an implementation detail. A dataset
whose terminal groups average 40 rows runs at $\phi = 0.63$ on u32/128-bit and
$\phi = 0.16$ on u32/512-bit — the same data, a four-fold difference in wasted
leaf work — while on u64/128-bit those groups exceed $C = 32$ and are
partitioned instead. Sweeping $|g|/C \in \{0.25, 0.5, 1.0\}$ plus the boundary
$C+1$ (just above capacity, forcing a partition pass) is what makes the wide
configurations' padding cost visible.

This also confounds leaf-kind comparisons: the two leaf kinds do not share a
threshold, and their relation inverts across the matrix. At u32/128-bit and
u64/256-bit both thresholds are 64, so `ins` versus `net` is a clean comparison
of two algorithms on identical range lengths. At u32/512-bit the network leaf
absorbs ranges up to 256 that the insertion variant partitions; at u64/128-bit
the reverse holds, with the network leaf giving up at 32 while insertion
continues to 64. Any `ins`/`net` result therefore mixes leaf algorithm with leaf
threshold unless the effective threshold is reported alongside it, or a variant
pins the insertion threshold to $C$.

Two predictions follow that are worth checking as harness sanity tests: shapes
whose groups all fall below $2L$ execute entirely in the scalar tail, so
register width should have almost no effect on them; and on datasets with mean
group size well below $C$, wide configurations should *lose* to narrow ones at
the network leaf. If either fails to appear, the cause is in the harness or
elsewhere in the implementation, not in the data.

## Generation model

Column-at-a-time generation cannot express most of the shapes below: drawing
each column independently fixes $D_j$ only in expectation and cannot produce
nested, correlated, or prefix-presorted structure. Generate **top-down over the
group tree** instead:

```text
level 0:  one group of N rows
level j:  split each level-(j-1) group into b children,
          with child sizes drawn from the shape's size distribution,
          and assign K_j one distinct value per child
finally:  permute rows (identity for the presorted shapes)
```

This makes $D_j$ and $G_j$ exact by construction, keeps value domains explicit,
and reduces every shape to a choice of branching factor and size distribution
per level. Seeds are fixed per (shape, N, m, instance) so a run is reproducible
and so two algorithms see byte-identical input.

## Generator

`datagen/` implements this document. `generate_datasets` writes one binary file
per (shape, parameter set, element width) into `data/`; `verify_datasets` reads
them back, recomputes every descriptor above from the bytes on disk, and checks
the result against closed-form expectations derived from the shape parameters
rather than from the data:

```bash
cmake --build <build-dir> --target generate_datasets verify_datasets
<build-dir>/generate_datasets --rows 262144 --columns 3 --elements 4,8
<build-dir>/verify_datasets
```

The container is a 64-byte header — magic, version, element width, rows, columns,
seed — followed by column-major payload, so one column can be read straight into
an aligned buffer without consulting the manifest. `manifest.tsv` and
`manifest.json` record each instance's parameters, seed, payload checksum and
measured descriptor.

Generation is deterministic: the seed is derived from the instance identity
(shape, parameters, rows, columns, element width), so a repeated run reproduces
byte-identical files and two algorithms can be compared on the same input without
shipping the data. `--rows` and `--columns` scale the whole catalog; the
configuration-relative sizes are instantiated at their absolute values, so the
Unique-Last ladder covers 2, every $2L$, every $C$, every $C+1$ and the task
threshold across all six SIMD configurations in one directory.

---

## 1. Unique-First

The first column uniquely identifies every tuple, so

$$D_1 = D_2 = \cdots = D_m = N .$$

```text
K1: uniform permutation of [0, N)
K2 ... Km: arbitrary (fix them to a constant to make redundancy explicit)
```

All columns after $K_1$ are irrelevant to the ordering, but they still move with
every key exchange. This is the minimum-depth case, and it isolates the price of
supporting $m$ columns from the price of using them: one full-range sort, one
run-discovery pass that finds nothing, and $m-1$ payload replays per exchange.

$R_j = 0$ for all $j \ge 1$, so the single discovery pass over $R_0 = N$ values
returns nothing, and $W = m \cdot N \log_2 N$. Time should be linear in $m$ here;
a superlinear trend indicates per-column overhead beyond data movement.

**Primary property:** minimal prefix depth, maximal payload width per unit of
comparison work.

---

## 2. Unique-Last

Tuples stay tied until the final column. Parameterized by the **terminal group
size** $g$: level $m-1$ leaves $N/g$ groups of size $g$, each resolved only by
$K_m$.

```text
g = 2         N/2 groups of 2   -> maximal number of next-column tasks
g = 2L        at the SIMD-loop minimum: 4 .. 32 rows by configuration
g = C         fills the network leaf exactly: 32 .. 256 rows
g = C + 1     just above capacity: forces a partition pass
g = 4096      at the default task threshold, independent of configuration
```

The middle three are configuration-relative and therefore expand to different
absolute sizes per element and register width; the first and last are absolute
because they are set by the algorithm's structure rather than by the vector
length.

Intermediate levels split with a fixed branching factor, so
$D_j \approx (N/g)^{j/(m-1)}$ for $j < m$ and $D_m = N$.

The two ends of $g$ are different experiments, and conflating them is the main
weakness of an unparameterized "deep" dataset. Small $g$ makes per-task and
per-range fixed costs dominate — this is the regime in which eagerly seeding a
Mersenne Twister per range cost more than the sorting did, and where the
inline-vs-queue threshold is decided. Large $g$ keeps the same depth while
making each level's work substantial, which is where discovery strategy and
parallel exposure matter instead.

**Primary property:** maximal prefix depth, with the per-group work scale as an
explicit knob.

---

## 3. Independent Uniform (reference)

Each column is drawn independently, $K_i \sim U\{0,\ldots,c_i-1\}$, with the
cardinalities $c_i$ set explicitly. For equal cardinalities $c$, the *observed*
number of distinct prefixes is not $c^j$ but

$$\mathbb{E}[D_j] \;=\; c^{j}\left(1-\left(1-c^{-j}\right)^{N}\right)
\;\approx\; c^{j}\left(1-e^{-N/c^{j}}\right),$$

which matters precisely in the interesting region $c^j \approx N$, where the
naive $c^j$ overestimates $D_j$ by a constant factor. Group sizes at level $j$
are multinomial, hence concentrated around $N/c^j$ with $\Theta(\sqrt{\cdot})$
spread.

A **balanced variant** — exact branching factor, all groups equal in size,
generated by the group-tree model — removes that spread. Comparing the two
isolates the effect of group-size variance alone at fixed $(D_j)$, which is the
only thing that distinguished the "uniform hierarchy" and "independent uniform"
shapes of an earlier draft; they are one family with a variance knob, not two
shapes.

This is the conventional baseline that correlated, skewed and presorted shapes
are compared against.

**Primary property:** statistically independent keys, controlled per-column
cardinality, group-size variance as a sub-knob.

---

## 4. Skewed Prefix Groups

Group sizes at one or more levels follow a heavy-tailed distribution rather than
a uniform one. A Zipf exponent $s$ over $D_j$ groups gives a single continuous
knob:

```text
s = 0      uniform group sizes (degenerates to shape 3)
s ~ 1      realistic categorical skew
s >> 1     one dominant group + a long tail
```

The heavy-hitter special case is the same construction read at large $s$:

```text
90% of rows:   K1 = 0        (resolved by K2 ... Km)
10% of rows:   K1 spread over many values
```

and it extends to several levels (heavy group, heavy subgroup, and so on).

This shape separates **cardinality** from **group-size distribution**: two
instances with the same $D_1$ behave very differently when one has uniform
groups and the other a dominant one. It is also the case in which parallel
scaling is bounded by a single group rather than by thread count: until the
dominant group's own partitioning is offloaded, only one worker has work. Under
post-sort discovery on a non-final column, partitions cannot be offloaded at
all, so this shape is what makes that restriction visible.

**Primary property:** skewed prefix-group sizes; single-group parallel
bottleneck.

---

## 5. Low Cardinality and All-Equal

The duplicate-dominated extreme: $D_1 = d$ for small $d$, down to $d = 1$ (a
single group spanning the whole input), optionally with $D_j$ small at every
level so that nearly all rows reach the final column.

```text
d = 1        every row identical in K1 -> whole input descends to K2
d = 2 .. 16  a handful of very large groups
```

This is where three-way and two-way partitioning separate: a three-way
pivot-equal band removes duplicates from recursion and needs no run-discovery
scan, while two-way partitioning keeps re-partitioning them. Two-way behaviour
on a large all-equal input is quadratic in the equal-run length, which is a
property of the algorithm rather than a measurement artifact, so these instances
must be size-capped (or the two-way variants excluded) in a default sweep and
reported as a separate diagnostic rather than silently dropped.

Fully duplicate **tuples** — equal in every column — belong here too. They
terminate at the last column with nothing left to discriminate, and because the
sort is not stable their relative order is unspecified; validation must compare
tuple multisets, not row identities.

**Primary property:** duplicate-dominated input; discriminates partition kind.

---

## 6. Correlated Columns

Later columns carry less information than their marginal cardinalities suggest,
so $D_j \approx D_{j-1}$ even when each individual column has high cardinality.
The two directions of dependence are not equivalent and should be generated
separately:

```text
forward   K_{j+1} = f(K_j)        later column determined by earlier
          e.g. K2 = K1, K3 = floor(K1 / 16)
          -> D_{j+1} = D_j: the column adds no discrimination, yet is still
             co-sorted and (under post-sort discovery) still scanned

reverse   K_j = g(K_{j+1})        earlier column is a coarsening of a later one
          e.g. K1 = K2 >> 8
          -> the lexicographic order equals the order by K2 alone, and each
             K1-group holds a dense contiguous range of K2 values

noisy     K2 = K1 + noise         partial redundancy, tunable by noise width
```

The forward case measures pure wasted work: a column that costs a full co-sort
pass and changes nothing. The reverse case leaves the *amount* of discrimination
intact but changes the value distribution each next-column sort sees, from a
full-domain sample to a dense narrow range — which is what pivot selection and
any value-range-based optimization react to.

**Primary property:** inter-column dependence; distinguishes marginal column
properties from actually contributed discrimination.

---

## 7. Prefix-Presorted and Clustered

Input arrives already ordered, or partially ordered, with respect to a prefix of
the target order. Two independent knobs:

```text
p in [0, m]     input sorted by (K1 ... Kp), random within those groups
                p = 0 random input, p = m fully sorted (boundary case)

r               number of ascending runs, or the fraction of adjacent pairs
                already in order: models clustered arrival rather than
                exact prefix order (reverse-sorted input is the r = 1
                descending boundary)
```

Prefix order does not reduce the *work* this algorithm performs: every range is
still quicksorted and every equal run still rediscovered, and $D_j$, $G_j$, $R_j$
and $W$ are unchanged by permuting rows. What changes is pivot quality, branch
predictability and access locality. The shape therefore tests a hypothesis about
the implementation — that it does not exploit existing order — and quantifies
what that costs relative to a merge-based or run-detecting competitor that does.
Stating it that way is more honest than asking whether the algorithm "can
exploit" order.

**Primary property:** existing order with respect to the target key prefix, at
fixed intrinsic work.

---

## 8. Implementation-Targeted Probes

Statistical shapes exercise the cost model; these exercise named mechanisms in
the implementation:

```text
duplicates at     many values equal to the    stresses the pivot boundary:
the pivot         likely sampled median       equal values straddling a
                                              two-way partition must still
                                              end up in one maximal run
extreme values    keys equal to 0 and to      the network leaf pads with the
                  the type maximum            type maximum, so real maxima
                                              probe padding handling
```

The duplicates-at-pivot case has a correctness dimension as well as a
performance one: under two-way partitioning a maximal equal run may cross the
pivot, which is exactly why complete-range post-sort discovery is used there
instead of incremental discovery. A benchmark that never generates it cannot
observe the cost of that decision.

Note what is deliberately *absent*. The classic quicksort adversaries — organ
pipe, sawtooth, and other periodic or median-of-three killer sequences — attack
*deterministic* pivot selection. This implementation samples three random
indices per range, so those inputs carry no penalty: measured at $N = 262144$,
u32, three columns, an organ pipe sorts in 9.7 ms against 10.6 ms for
`Unique-Last` at $g = 2$, which has the same group structure, and a
1024-tooth sawtooth in 9.5 ms against 10.1 ms for independent uniform at
$c = 1024$. Both are *faster*, because their monotone runs help locality. They
are also not new shapes: each is an existing group structure combined with an
existing arrangement, so generating them separately adds files without adding
coverage. Reintroduce them only alongside a deterministic or strided pivot
sampler, which would make them adversarial again.

**Primary property:** mechanism-specific probes: two-way pivot boundaries and
network-leaf padding.

---

## 9. Permutation-Locality Stress (constrained)

The intent is to isolate the cost of *applying* an ordering to co-sorted columns
from the cost of *computing* it, by fixing key width, column count and row count
while varying the locality of the induced permutation:

```text
local       1,0,3,2,5,4,7,6, ...          mean displacement O(1)
blocked     contiguous blocks reordered   displacement O(block size)
random      pi = uniform permutation      displacement O(N)
```

quantified by mean displacement and the adjacency-preserving fraction

$$L_{\text{disp}} = \frac{1}{N}\sum_{i=0}^{N-1}\bigl|\pi(i)-i\bigr|,
\qquad
L_{\text{adj}} = \frac{\bigl|\{\,i : \pi(i+1) = \pi(i)+1\,\}\bigr|}{N-1}.$$

Two constraints limit what this shape can claim, and both should be stated
rather than discovered later:

- **The permutation is not a free parameter.** It is determined by the keys, so
  targeting a given $\pi$ means setting $K_1[i] = \pi(i)$, since the output
  position of a row is the rank of its key — which forces
  unique keys, making this a sub-family of `Unique-First` (and, for the local
  case, of the nearly-sorted variant of shape 7). With duplicate keys the
  permutation is not even well defined, because the sort is unstable.
- **Displacement of the final permutation is the wrong cost model for an
  in-place quicksort co-sort.** It never performs $\pi$ as one gather; it
  performs $O(\log N)$ streaming passes whose access pattern is sequential
  regardless of $L_{\text{disp}}$. Displacement *is* the right predictor for a
  materialized-permutation implementation — an index sort followed by a gather
  per column, i.e. the scalar baseline.

So this shape is retained as a **discriminator between implementation
strategies**, not as a workload dimension of the in-place sorter: it should
show a strong locality response in the gather-based baseline and a weak one in
the co-sorting quicksort. If both respond identically, that is evidence the
in-place implementation is bound by something other than the permutation it
realizes.

**Primary property:** locality of the induced permutation; separates gather-based
from in-place data movement.

---

## Orthogonal axes

These are benchmark parameters, not dataset shapes, and every shape should be
run across them:

| Axis | Values | Note |
|---|---|---|
| $N$ / working set | L1, L2, half LLC, LLC, $2\times$ LLC | per column, not aggregate |
| $m$ | 1, 2, 3, 5, up to the compiled column limit | $m=1$ is the degenerate no-discovery case |
| element width | u32, u64 | sets bytes moved per row and, at fixed footprint, $N$ |
| register width | 128, 256, 512 bit | sets $L$, hence $2L$ and $C = 16L$ |
| payload width | non-key columns that move but never sort | isolates movement from discrimination |
| direction pattern | all ascending, all descending, alternating | orthogonal to shape: equality — and therefore $D_j$, $G_j$, $R_j$ — is direction-invariant |
| workers, thresholds | worker count, task and partition thresholds | interact with $G_j$, see the threshold table |

Element width and register width give six configurations, and they are the two
axes that are *not* cleanly orthogonal to the dataset. Both move the structural
boundaries of the previous section, so the same nominal group-size distribution
occupies a different regime in each configuration; group sizes are specified
relative to $C$, $2L$ and the task threshold for exactly this reason.

Element width additionally forces a choice about what is held constant across a
comparison, and the choice must be stated with the result:

```text
fixed rows N          u64 moves twice the bytes of u32; W is identical
fixed bytes/column    u64 has half the rows of u32; W differs by ~2x
```

Neither is wrong, but they answer different questions — "what does a wider
element cost per row" versus "what does a wider element cost per byte of table"
— and a cross-width plot at fixed footprint conflates narrower keys with more
rows. Register width has no such issue: it changes neither $N$ nor bytes moved,
only how many lanes a pass processes, so it is the one axis on which a clean
speedup curve is expected.

The payload-width axis needs a distinct entry point: with all columns as sort
keys, the only way to add moved bytes is to add a sort column, which changes the
ordering problem at the same time. Varying payload width against a fixed
single-key sort separates the two effects.

## Reporting and normalization

- Report the measured descriptor with every result, not just the shape name.
- Normalize time by $W$ when comparing *across* shapes; raw ns/row is
  meaningless between `Unique-First` and `Unique-Last`, which differ in
  intrinsic work by orders of magnitude. Within a shape, ns/row is fine.
- Alternatively, choose parameters so $W$ is comparable across shapes, and then
  compare raw time; differences then reflect implementation efficiency rather
  than intrinsic difficulty.
- Report $\sum_{j=0}^{m-2} R_j$ alongside the measured run-discovery volume. A
  gap between them means discovery is scanning ranges it should not, or is
  rescanning ones it already covered.
- Cap or exclude the quadratic combinations (two-way with shape 5) explicitly
  and say so in the output; a silently dropped configuration reads as a covered
  one.
- Report the SIMD configuration as $(L, C)$, not only as a register width, and
  report the group-size histogram in configuration-relative buckets. Two rows
  labelled with the same nominal group size but different $C$ are not the same
  experiment, and a table that hides $C$ makes the network leaf's padding cost
  look like a register-width effect.

## Summary

| Dataset | Primary property | Discriminates |
|---|---|---|
| 1 Unique-First | minimal depth, max payload per comparison | per-column movement cost; leaf choice under wide payloads |
| 2 Unique-Last ($g$) | maximal depth, per-group scale as a knob | per-task fixed cost (small $g$); discovery strategy (large $g$) |
| 3 Independent Uniform | independent keys, controlled cardinality | reference point; group-size variance sub-knob |
| 4 Skewed Prefix Groups | heavy-tailed group sizes | parallel exposure; partition offload restrictions |
| 5 Low Cardinality / All-Equal | duplicate-dominated | two-way vs three-way partitioning; equal-band shortcut |
| 6 Correlated Columns | dependent, redundant keys | wasted per-column work; value-range effects on pivots |
| 7 Prefix-Presorted / Clustered | existing order at fixed work | whether order is exploited at all; locality and pivot quality |
| 8 Implementation Probes | mechanism-specific inputs | two-way pivot-boundary handling; network-leaf padding |
| 9 Permutation-Locality | locality of the induced permutation | in-place vs materialized-permutation implementations |

Shapes 1-2 vary discrimination depth, 3-6 vary group structure at controlled
depth, 7-9 vary arrangement and movement at controlled structure, and 8 probes
two named implementation mechanisms rather than a cost source. Together they
cover the three cost sources named at the top, plus the fourth that only appears
in a parallel implementation: how much *independent* work the structure exposes,
which is set by $|G_j|$ and its skew rather than by $N$.

Each shape is instantiated once per SIMD configuration, with its
configuration-relative sizes resolved against that configuration's $L$ and
$C$. The shapes that respond to those two axes are the ones whose group sizes
sit near a boundary — 2 (at $g \in \{2L, C, C+1\}$), 5 and the terminal levels
of 3 and 4; shapes 1, 6, 7 and 9 keep their character across the matrix because
their group structure is far from any boundary.
