# Conflict as Data: Prefix-Scannable Transactions

**Status:** high-risk research proposal, not an established result

**Assessment date:** 2026-08-19

**Working system name:** ScanTX

**Decision:** perform a short algebra-and-kernel pilot before building a DBMS

## Executive assessment

Database systems normally extract data-level parallelism from independent
rows, keys, queries, or transactions. Transactions contending on the same
record are treated as the point at which parallelism ends: the system avoids
the conflict, reorders it, aggregates commutative updates, speculates and
repairs, or executes the transactions serially.

This proposal investigates a different possibility:

> Put an ordered sequence of mutually conflicting transactions into SIMD
> lanes and compute the serialization chain itself with a parallel prefix
> network.

The technique applies when each transaction can be compiled into a bounded
state-transformer summary and ordered composition of summaries is
associative. Composition need not be commutative. An exclusive prefix scan
then gives every lane the exact database state that its transaction would see
in a chosen serial execution. Each lane can calculate its own return value and
derived effects, while the full prefix gives the final shared state.

This changes the data-parallel dimension. Lanes do not represent independent
tuples. They represent positions in a true serial dependency chain. The
proposal therefore asks whether conflict itself can become vector data without
weakening isolation, changing transaction order, or discarding individual
results.

The preliminary literature search found all of the ingredients separately:
parallel prefix algorithms, state-transformer composition, transaction
batching, commutative reconciliation, hot-row grouping, and transaction
merging. It did not find a database execution model that compiles ordered,
potentially noncommutative transactions into bounded summaries and evaluates
their exact serial prefixes in SIMD lanes. This is a novelty hypothesis, not a
certificate that nobody has considered the idea. A formal literature, patent,
and production-system audit is the first stop gate.

## Research question

The main research question is:

> **Can a database compiler identify useful classes of transactions whose
> ordered state transformations have bounded, associative summaries, and can
> a DBMS use portable SIMD prefix execution to outperform optimized serial
> processing of hot-record conflicts while preserving exact transaction
> results and strict serializability?**

This decomposes into four scientific questions:

1. **Expressiveness:** Which practical transaction programs are
   prefix-scannable with a summary whose size is independent of cohort length?
2. **Compilation:** Can the property and composition law be recognized or
   certified from a restricted transaction language?
3. **Architecture:** When does the logarithmic dependency depth of a SIMD
   prefix network outweigh cross-lane movement, extra work, and cohorting
   latency?
4. **Database semantics:** Can individual return values, rejection behavior,
   durability, and external visibility remain identical to a legal serial
   execution?

## Formal model

Consider a key-local state space \(S\). A transaction instance with parameters
\(p\) has exact serial semantics

\[
T_p(s) = \bigl(F_p(s), R_p(s)\bigr),
\]

where \(F_p(s)\) is the new shared state and \(R_p(s)\) is the result returned
to that transaction.

A transaction family is **prefix-scannable** when there is a summary domain
\(A\) with:

- an encoder \(\eta(p) \in A\);
- an identity summary \(e\);
- an associative ordered-composition operator \(\otimes\);
- a denotation \(\llbracket a \rrbracket : S \rightarrow S\); and
- a bounded representation size that does not grow with the number of
  composed transactions.

The required homomorphism is

\[
\llbracket a \otimes b \rrbracket
  = \llbracket b \rrbracket \circ \llbracket a \rrbracket.
\]

The orientation says that `a` occurs before `b`. Neither the summaries nor
their transformations need to commute.

For a cohort \(p_0,\ldots,p_{n-1}\), an exclusive scan computes

\[
P_0=e, \qquad
P_i=\eta(p_0)\otimes\cdots\otimes\eta(p_{i-1}).
\]

Given the cohort's initial state \(s_0\), lane \(i\) obtains

\[
s_i=\llbracket P_i\rrbracket(s_0)
\]

and returns \(R_{p_i}(s_i)\). The inclusive prefix in the last active lane
denotes the final state. By induction on the prefix length, every pre-state,
return value, and the final state equal ordinary serial execution in cohort
order.

The algebra is not sufficient by itself. The representation must also stay
small. Arbitrary functions compose associatively, but storing their full
syntax or lookup table can grow with the cohort and provide no useful
acceleration. Bounded summary complexity is the central tractability
condition.

## Worked noncommutative example

Let the hot state be an integer \(x\), and let a transaction summary be an
affine transformer

\[
f_{a,b}(x)=ax+b.
\]

Ordered composition is

\[
(a_1,b_1)\otimes(a_2,b_2)
  = (a_2a_1, a_2b_1+b_2).
\]

This operation is associative and generally noncommutative. Consider an
initial state `x = 10`:

| Lane | Transaction | Summary | Serial pre-state | Serial post-state |
| ---: | --- | --- | ---: | ---: |
| 0 | `x += 3` | `(1, 3)` | 10 | 13 |
| 1 | `x *= 2` | `(2, 0)` | 13 | 26 |
| 2 | `x = 7` | `(0, 7)` | 26 | 7 |

Changing the order changes the answer. Nevertheless, one exclusive scan of
the summaries constructs prefix transformers whose application to `10`
produces the three pre-states `[10, 13, 26]`; the full prefix produces `7`.
No lane speculates, and no transaction is treated as conflict-free.

For \(W\) SIMD lanes, a Hillis--Steele-style network has
\(\lceil\log_2 W\rceil\) dependent composition stages. It performs more total
logical work than a work-efficient scalar chain, but carries that work in
vector instructions. Whether this wins on real machines is an empirical
question and one of the earliest kill tests.

## Candidate transaction classes

The first study should characterize families rather than claim support for
arbitrary SQL.

### 1. Affine vector state

For a small state vector, a transaction can have the form

\[
F(x)=Ax+b.
\]

The summary `(A, b)` is closed under composition. Matrix composition makes
the family order-sensitive even when individual scalar additions would
commute. Candidate applications include coupled accounting fields, sequence
state, weighted counters, and small control-state updates. Exact machine
integer overflow semantics must be part of the algebra.

### 2. Bounded and saturating transformations

Transformations of the form

\[
F(x)=\operatorname{clamp}(x+d, l, u)
\]

appear to admit constant-size closure under composition and are candidates for
token buckets, bounded counters, quotas, and rate-state maintenance. This
closure law must be proved and mechanically tested before it is treated as a
supported family.

An all-or-nothing inventory reservation is harder: repeated conditional
reservations may introduce a growing number of breakpoints. That is not a
minor implementation problem. Determining whether useful conditional classes
retain bounded summaries is part of the research.

### 3. Bit-field transformers

Per-bit transformations such as keep, clear, set, and toggle form a small
closed function family. A compact summary can represent ordered updates to
flags, capabilities, and status bitsets. These operations can be
noncommutative—for example, toggle followed by clear differs from clear
followed by toggle—while their summaries remain bounded.

### 4. Small finite-state procedures

For a workflow with a genuinely small state domain, a summary can be a
transition table mapping every input state to its output state. Function-table
composition is associative and bounded by the state-domain size. The
exclusive prefix gives every transaction its exact input state, from which it
can derive success, failure, and other return values. Possible examples are
order-state machines, leases with a small phase space, and bounded protocol
metadata.

### 5. Piecewise and guarded transformers

Piecewise-affine or guarded procedures are scientifically interesting because
they expose the boundary. Composition may remain compact for some restricted
guard structures and explode for others. The compiler should reject a family
when its summary cannot be bounded; it must not hide growing symbolic programs
inside a value called a summary.

If only additive counters and sequence-number allocation survive this
analysis, the proposal fails its originality test. Those cases are already
covered by combining and transaction-merging techniques.

## SIMD prefix kernel

For each summary field, the runtime holds one vector whose lane `i` contains
the field for transaction `i`. At scan distance `d = 1, 2, 4, ...` it:

1. shifts or aligns each summary vector by `d` lanes, inserting the identity;
2. constructs a mask for lanes with a predecessor at that distance;
3. composes shifted summaries with the current summaries in order; and
4. selects the composed value only in active lanes.

Fixed-width ISAs can unroll the stages. Scalable-vector implementations loop
until the offset reaches the runtime vector length. A later extension can use
a segmented scan to place transactions for several hot keys in one vector,
but a one-key cohort is the correct first experiment because it isolates the
central claim.

TSL is not incidental here. The kernel depends on cross-lane movement, masks,
selection, arithmetic over several summary fields, runtime vector length, and
tail handling. TSL already exposes the central cross-lane operation
[`align_right_lanes`](../tsldata/primitives/misc/swizzle.tsl). The same semantic
kernel can therefore be tested across AVX2, AVX-512, SVE, and RVV without
making one ISA's shuffle structure the research algorithm.

GPU warp scans and FPGA prefix networks are plausible later mappings. They
should not be used to justify turning TSL into a general accelerator framework
before the CPU experiment establishes that prefix-scannable transactions are
valuable.

## Minimal database architecture

The first prototype should be an in-memory, partitioned transaction engine,
not a modification of a full SQL DBMS.

### Compile time

A restricted deterministic transaction DSL describes key-local state,
parameters, updates, and results. For each admitted transaction family, the
compiler emits:

- `encode(parameters) -> summary`;
- `compose(earlier, later) -> summary`;
- `apply(summary, initial_state) -> state`;
- `result(parameters, serial_pre_state) -> response`; and
- a certificate or executable proof obligation relating composition to serial
  semantics.

Initially, recognition can target a small registry of known algebraic forms.
SMT-based bit-vector checking or exhaustive bounded checking can validate the
authored composition law. Automatically synthesizing arbitrary transformer
algebras is a later question, not a prerequisite for the kernel pilot.

### Run time

1. Requests are routed by their hot key or partition.
2. The owner collects only requests whose invocations overlap, preserving a
   declared order such as arrival sequence.
3. The owner reads the shared state once and prevents external access from
   observing an intermediate cohort state.
4. A TSL exclusive scan computes every serial pre-state and the final state.
5. Lanes derive individual responses and transaction-private or append-only
   effects.
6. The engine appends one ordered cohort record to the write-ahead log and
   installs the final shared state atomically.
7. Responses are released only after the required durability point.

At low load the engine bypasses cohorting and executes a request directly.
Unsupported procedures use the ordinary serial or concurrency-control path.

### Correctness boundary

The first system supports one mutable key-local state object plus results and
staged append-only effects. General multi-key transactions are out of scope.
They introduce distributed ownership and atomic publication questions that
would obscure the new mechanism.

Because a cohort contains overlapping invocations, its fixed order can be a
linearization and strict-serialization order. Other transactions observe the
state before or after the isolated cohort. A state-dependent application
rejection must be represented by the exact transformer—for example, a no-op
state change and a failure response for the states in which it rejects. A
runtime exception that cannot be modeled safely aborts or falls back for the
cohort.

Group commit, batching, and a single final record write are useful engineering
effects, but they are not the claimed contribution. Baselines must receive the
same grouping opportunities so the evaluation isolates parallel execution of
the semantic dependency chain.

## Closest work and novelty boundary

The novelty claim must be narrower than “batch contending transactions” or
“use SIMD in OLTP.” Both are occupied.

| Closest work | What it already does | Boundary of this proposal |
| --- | --- | --- |
| [Strife](https://arxiv.org/abs/1810.01997) | Partitions a batch into conflict-free clusters and residual transactions; residual conflicts remain serial or use concurrency control. | ScanTX targets the ordered conflicting chain itself. |
| [Doppel / phase reconciliation](https://pdos.csail.mit.edu/archive/doppel/) | Executes updates to replicated contended state and reconciles them when the operations commute. | ScanTX preserves order and targets noncommutative transformers with exact individual results. |
| [Batched OCC with operation reordering](https://www.vldb.org/pvldb/vol12/p169-ding.pdf) | Reorders operations in batches to reduce conflict and improve locality. | ScanTX does not obtain its parallelism by eliminating or reordering the dependency chain. |
| [Transaction Repair](https://arxiv.org/abs/1403.5645) | Speculatively executes transaction branches and incrementally repairs conflicts to a fixpoint. | ScanTX uses a certified closed representation and no speculative repair. |
| [TransactionMerger](https://arxiv.org/abs/2601.10596) | Merges structurally similar statements and precomputes aggregated effects of contending updates. It manually derives individual sequence IDs from one aggregated counter update. | Counter aggregation and ID offsets are prior art, not contributions. ScanTX asks for a general bounded transformer class, ordered noncommutative composition, compiler certification, and SIMD prefix execution. |
| [PolarDB hot-row grouping](https://www.alibabacloud.com/help/en/polardb/polardb-for-mysql/user-guide/hot-row-optimization) | Groups hot-row updates, shares row lookup, reduces lock overhead, and pipelines group collection and commit. | ScanTX reduces the semantic dependency depth within a group rather than only its access and locking overhead. |
| [Parallel Prefix Sum with SIMD](https://arxiv.org/abs/2312.14874) | Studies SIMD and multicore prefix algorithms, including database-operator uses. | The scan algorithm is established; the proposed contribution is the transaction class, compilation, serial semantics, and database execution model. |

State transformations forming a monoid under composition are standard
mathematics. The research claim is not the discovery of function composition
or prefix scan. The candidate first claim is:

> **To our knowledge, this is the first database execution model that maps an
> ordered cohort of conflicting transactions to SIMD lanes and computes every
> transaction's exact serial state and result through a prefix scan over
> bounded, potentially noncommutative state-transformer summaries.**

This sentence must remain marked “to our knowledge” until searches of DBLP,
ACM DL, IEEE Xplore, arXiv, Google Patents, dissertations, blockchain state
execution, stream processors, SIMD libraries, and relevant production DBMS
code have been recorded. An equivalent mechanism found in that audit stops or
substantially narrows the project.

## Falsifiable hypotheses

Thresholds should be frozen before confirmatory measurements.

- **H1 — algebraic usefulness.** At least three practically motivated
  transaction families, including one noncommutative family and one family
  with state-dependent results, have exact summaries bounded independently of
  cohort length.
- **H2 — kernel value.** Including summary encoding and result derivation, a
  TSL prefix kernel achieves at least **1.5x** the throughput of an optimized
  scalar serial chain for a preregistered region of cohort sizes on at least
  one CPU.
- **H3 — abstraction cost.** The generated TSL kernel remains within **20%**
  of a carefully tuned native-intrinsics implementation on the primary
  machine.
- **H4 — system value.** At high hot-key contention, a complete prototype
  including queueing, isolation, result construction, and logging improves
  throughput by at least **1.5x** over the strongest serial/batched baseline
  at matched durability, without materially worse tail latency at matched
  offered load.
- **H5 — semantic portability.** One transaction algebra and TSL kernel
  remains beneficial on two materially different vector models, preferably
  one fixed-width and one scalable-vector target.
- **H6 — exactness.** Exhaustive small-domain and randomized differential
  testing finds zero mismatches in final state, per-transaction results,
  rejection behavior, and crash replay relative to serial execution.

## Early stop gates

### Gate 0: collision audit

**Work:** one to two weeks before implementation.

Search publications, patents, theses, blockchain execution engines, stored-
procedure compilers, hot-record optimizations, combining data structures, and
parallel-scan applications. Record queries and exclusion reasoning.

**Continue if:** no work contains the complete mechanism and the remaining
claim is more substantial than applying a known scan to sequence numbers.

**Stop or redefine if:** a system already performs ordered prefix composition
of transaction transformers with exact individual results.

### Gate 1: algebra portfolio

**Work:** formalize affine, saturating, bit-field, and finite-state families;
prove or mechanically validate closure; attempt representative guarded
transactions.

**Continue if:** H1 is plausible and at least one useful family is genuinely
noncommutative.

**Stop if:** only sums, counters, and ID allocation remain. In that case the
idea is an incremental form of transaction combining.

### Gate 2: register-only kernel

**Work:** implement scalar, compiler-auto-vectorized, native-intrinsics, and
TSL scan kernels. Measure dependency depth, cycles per transaction, cohort
size, summary width, and cross-lane costs on AVX2 and AVX-512 if available.

**Continue if:** H2 and H3 hold in a meaningful region rather than at one
contrived point.

**Stop if:** shuffle latency, summary width, or extra \(O(W\log W)\) work
eliminates the gain. Do not build a DBMS around a losing primitive.

### Gate 3: exact result semantics

**Work:** add one conditional or finite-state transaction, individual return
values, rejection, and exhaustive differential tests.

**Continue if:** the system produces all logical transaction results without
serial re-execution.

**Stop if:** realistic results require replaying the chain sequentially or
summary representations grow with every transaction.

### Gate 4: minimal durable engine

**Work:** implement routing, cohort formation, strict ownership, a WAL, replay,
direct low-load execution, and equivalent batching for baselines.

**Continue if:** H4 holds and the performance gain is still attributable to
prefix execution after amortized batching effects are removed.

**Stop or publish only the boundary result if:** logging dominates all
variants, cohort delay destroys tail latency, or eligible transactions are too
rare.

### Gate 5: portability

Only after the preceding gates pass, evaluate scalable vectors and consider a
segmented multi-key scan, GPU warp, or FPGA prefix network. Cross-device work
must test the scientific mechanism, not become a generic accelerator-library
project.

## Evaluation outline

### Baselines

- direct optimized serial execution under exclusive key ownership;
- scalar batched execution with one read, one final write, and the same group
  commit policy;
- compiler auto-vectorization where applicable;
- hand-written AVX2/AVX-512 kernels;
- a locking and an OCC engine under matched durability;
- conflict-free scheduling where relevant;
- commutative reconciliation for workloads it supports; and
- a TransactionMerger-style implementation for mergeable workloads.

The scalar batched baseline is essential. Otherwise, savings from lock
acquisition, tree traversal, logging, or request dispatch could be incorrectly
attributed to SIMD prefix execution.

### Independent variables

- cohort size and vector length;
- summary representation width;
- hot-key frequency and number of hot keys;
- arrival rate and cohort wait budget;
- mixture of admitted and fallback transactions;
- transaction family and branch complexity;
- durability mode and log flush latency;
- AVX2, AVX-512, SVE, and RVV where hardware is available; and
- fixed versus segmented scans.

### Measurements

- cycles and instructions per logical transaction;
- cross-lane instruction count and dependency depth;
- throughput, median latency, and p95/p99 latency;
- cohort occupancy and waiting time;
- fraction of procedures and dynamic requests admitted;
- summary size and any representation growth;
- TSL-to-native performance gap;
- final-state and response mismatches; and
- recovery time and replay equivalence.

Synthetic microbenchmarks are necessary for mechanism isolation, but the
study also needs procedures derived from BenchBase applications and at least
one real hot-state motif. Any procedure translated into the restricted model
must retain its original result and failure semantics.

## Principal risks

1. **The tractable class may be too small.** Function composition is universal;
   compact closure is not. This is the largest scientific risk.
2. **SIMD scan may lose to a short scalar chain.** Cross-lane permutations are
   expensive, especially for multi-register summaries and across x86
   sublanes.
3. **TransactionMerger may absorb the practical contribution.** The work must
   demonstrate cases beyond aggregation and manually assigned offsets.
4. **Batch formation adds latency.** The mechanism is intended for saturated
   hot records; low-load bypass is mandatory.
5. **The log may dominate.** Baselines need equal group-commit opportunities,
   and kernel value must be measured separately.
6. **Multi-key scope can explode.** The first paper should resist general
   distributed transactions unless the one-key mechanism succeeds.
7. **A neighboring field may contain the idea under different terminology.**
   Blockchain execution, combining concurrent objects, parallel recurrences,
   and finite-state transducers require deliberate searching.

## Intended contribution and publication shape

A successful project would contribute:

1. the definition and semantic characterization of prefix-scannable
   transactions;
2. a compiler or checker for several bounded transformer families;
3. a portable TSL implementation of ordered transaction-prefix execution;
4. a strictly serializable, durable hot-state prototype with exact individual
   results;
5. an empirical map of when the mechanism wins across transaction families
   and vector architectures; and
6. a negative boundary showing which guards or state representations cause
   summary explosion.

The concept plus algebra portfolio and kernel evidence could form a CIDR-style
paper. A compiler, ACID prototype, real procedures, and cross-architecture
evaluation would be needed for a stronger systems paper.

## Final judgment

This proposal is riskier than optimizing a Parquet decoder or adding another
adaptive representation decision, but it has a more fundamental potential
contribution. It attempts to expose data-level parallelism in work that
database systems currently define as serial: an ordered chain of true
conflicts.

It is worth a bounded pilot because it can fail cheaply. The collision audit,
algebra portfolio, and register-only kernel can determine whether the idea is
both new enough and fast enough before a transaction engine is built. It
should be abandoned if it collapses to commutative counters, loses to the
scalar chain, or requires summaries that grow with the cohort.
