# Evaluation plan: relational truth-table execution

## Purpose

This plan defines the evidence needed to accept, narrow, or reject the proposal
in [`idea.md`](idea.md). The evaluation concerns a bounded SQL/relational model
checker, not ordinary analytical-query throughput and not only the speed of
bitwise SIMD primitives.

Three distinctions govern every result:

1. **counterexample versus bounded proof:** stopping at the first difference
   and exhausting the entire scope are separate workloads;
2. **semantic coverage versus speed:** a faster checker supporting a weaker
   query fragment is not automatically better; and
3. **bounded versus unrestricted equivalence:** exhausting one finite scope
   never becomes an unqualified proof unless a separate small-model theorem
   applies.

Correctness is a gate. Performance measurements from a configuration with an
unexplained semantic mismatch are invalid.

## Research questions

- **RQ1 — representation feasibility:** For which finite schemas, domains, and
  set-relational plans can a tiled truth-table executor exhaust useful bounds
  before exponential growth or intermediate-tuple expansion dominates?
- **RQ2 — data-parallel value:** How much do scalar word parallelism, explicit
  TSL SIMD, vector width, fusion, and tile size contribute to complete checker
  performance?
- **RQ3 — symbolic crossover:** On which query and scope classes does
  truth-table execution find counterexamples or complete bounded checking more
  efficiently than VeriEQL or another strong SMT-based method?
- **RQ4 — testing value:** Under equal resource budgets, does exhaustive
  small-scope execution expose seeded or historical optimizer errors missed by
  randomized concrete testing?
- **RQ5 — semantic expansion:** How do integrity constraints, SQL
  three-valued logic, bags, and aggregation change time, memory, maximum scope,
  and useful bug coverage?
- **RQ6 — performance portability:** Can one semantic TSL implementation
  remain correct and beneficial across fixed- and scalable-vector
  architectures without target-specific relational algorithms?
- **RQ7 — hybrid value:** Do exhaustive and symbolic checking have sufficiently
  complementary winning regions for a simple hybrid to improve solved cases or
  time to counterexample?

## Pilot questions versus confirmatory hypotheses

The first implementation is exploratory because no measurements yet establish
reasonable scope and time thresholds. The pilot must freeze:

- supported semantic fragment;
- query and schema strata;
- fact-count bounds;
- tile-size candidates;
- memory and timeout budgets;
- external-tool revisions; and
- primary effect-size thresholds.

Only an untouched held-out corpus may be used for confirmatory claims. The
proposed thresholds below are go/no-go targets. They may be revised once after
the pilot, before held-out evaluation, with the revision and rationale retained.

## Proposed confirmatory hypotheses

### H1: semantic exactness

For every supported scope small enough for explicit per-world enumeration, the
scalar word-parallel and TSL SIMD engines produce exactly the same
intermediate-tuple memberships, legal-world mask, final result, and
counterexample as the independent reference evaluator.

Acceptance requires:

- zero unexplained bit mismatches;
- zero replay failures attributable to the checker;
- zero padding/tail bits reported as worlds; and
- deterministic results across repetitions and supported backends.

H1 has no tolerated error rate.

### H2: data-parallel execution creates material headroom

On the preregistered compute-relevant set-SPJUD scenarios:

1. the strongest TSL SIMD implementation is at least **1.5x** faster than the
   strongest scalar-word implementation, including its normal compiler
   auto-vectorization, on at least two materially different operator strata;
2. the lower bound of the paired 95% bootstrap interval exceeds **1.2x** for
   those strata; and
3. the TSL implementation is within **15%** of a carefully optimized native
   primary-ISA diagnostic for the same mask kernels.

Separately, complete world-parallel checking should be at least **10x** faster
than explicit per-world reference execution at the largest scope both can
complete. This latter comparison establishes the value of transposition but is
too weak by itself for publication.

If the complete checker is memory- or tuple-planning-bound, mask-kernel speedup
does not satisfy H2. Report both kernel and end-to-end effects.

### H3: exhaustive checking has a meaningful SMT winning region

Partition compatible query pairs before measurement by plan shape, operator
count, expected smallest-counterexample scope, constraints, and result type.
H3 holds if at least one preregistered stratum containing at least **100 query
pairs** and at least **20% of the held-out compatible corpus** satisfies both:

- geometric-mean time-to-valid-counterexample is at least **2x** lower than
  pinned VeriEQL, with the lower 95% paired-bootstrap bound above **1.25x**; and
- the truth-table checker returns no fewer valid outcomes under the common
  timeout and memory budget.

Bounded-equivalent pairs are evaluated separately. For them, the relevant
metric is time to exhaust the same semantic scope, not time to an unrestricted
proof that the truth-table engine cannot provide.

H3 does not require the proposed engine to dominate overall. A stable,
explainable crossover is more interesting than a favorable aggregate average.

### H4: exhaustive coverage adds testing value

Construct a held-out mutant suite in which each mutation changes one optimizer
rewrite or relational operator and the independent oracle establishes whether
a counterexample exists within the declared scope. Include a rare-witness
stratum whose distinguishing worlds form a small fraction of legal worlds.

Under equal wall-clock and CPU budgets, the truth-table checker should detect
at least **25% more** bounded-falsifiable mutations than schema-aware random
world generation in the rare-witness stratum, with no replay-invalid
counterexamples. Report common detections, unique detections, and time to first
counterexample rather than only the total.

The exhaustive checker is expected to detect every supported mutant whose
counterexample is inside a completely exhausted scope. A miss in that category
is a correctness failure, not ordinary statistical variation.

### H5: richer SQL semantics retain a useful scope

After adding bags and either `NULL` or integrity constraints, the checker
should:

- support at least **100 held-out query pairs** exercising the new semantics;
- exhaust a preregistered scope with at least **12 independent bounded input
  decisions** for representative join/projection queries within the common
  resource budget; and
- expose at least one seeded or historical error that the set/non-null fragment
  cannot express.

The exact count of independent decisions for a bit-sliced bag representation
must be defined in the scope manifest; it cannot be made to look larger by
counting redundant tuple slots.

If richer semantics reduce the method to hand-sized examples without adding
bug coverage, H5 fails and the paper must remain explicitly about a smaller
relational fragment.

### H6: semantic portability

The same relational evaluator, world layout, and TSL kernel source should:

- pass identical correctness suites on at least two materially different
  vector families;
- outperform the scalar-word backend by at least **1.3x** end to end in one
  compute-relevant stratum on each real machine; and
- require no target-specific change to query semantics, tuple enumeration, or
  counterexample decoding.

A fixed-width x86 result plus SVE/RVV emulation establishes build coverage, not
H6. Profile-specific generated code and tile-size selection are permitted;
forking the relational algorithm is not.

### H7: simple hybrid complementarity

This is conditional on H3. Under a common resource budget, a frozen two-stage
policy—truth-table checking through bound `B`, followed by VeriEQL when
required—should either:

- complete at least **10% more** query pairs than the better single method; or
- reduce geometric-mean time to valid outcome by at least **20%** without
  reducing completed cases.

If one method dominates, reject H7 and retain the simpler system.

## Systems and algorithmic baselines

| ID | Baseline or candidate | Role |
| --- | --- | --- |
| **B0** | Explicit per-world set-relational reference | Independent semantic oracle and naive exhaustive baseline. |
| **B1** | Pinned DuckDB or another DBMS replay path | External dialect/engine validation for concrete counterexamples. Not the primary high-throughput oracle. |
| **B2** | Scalar `uint64_t` truth-table engine with vectorization disabled | Isolates ordinary word-level bit parallelism. |
| **B3** | Scalar-source truth-table engine with normal optimizer and auto-vectorization | Strong compiler-generated CPU baseline. |
| **C1** | TSL explicit-SIMD truth-table engine | Primary candidate. |
| **C2** | TSL SIMD with fused output comparison and selected operator fusion | Measures safe fusion after the unfused implementation is frozen. |
| **B4** | Limited native-intrinsics primary-ISA kernels | Measures TSL abstraction overhead; not a second system. |
| **B5** | Pinned VeriEQL with pinned SMT solver | Primary bounded symbolic baseline. |
| **B6** | Schema-aware random world/query-pair tester | Concrete-testing baseline under equal budgets. |
| **B7** | Optional second equivalence tool on its supported subset | Robustness check; results are not merged across different semantic contracts. |
| **C3** | Simple truth-table-then-SMT hybrid | Conditional candidate after pure-method results. |

If a baseline does not support exactly the same semantics, restrict the
comparison or label it as coverage evidence. Do not translate bags to sets,
drop constraints, remove nulls, or reduce domains silently to manufacture a
common denominator.

## Candidate variants and ablations

### World-space variants

- full-universe materialization versus tiled streaming;
- binary world order versus Hamming-weight/scope order;
- post-generation validity mask versus constraint-aware enumeration;
- no symmetry reduction versus each proved symmetry rule; and
- fixed tile size versus a small frozen tile policy.

### Relational variants

- tuple-pair nested join versus key-indexed ground join;
- materialized intermediate masks versus liveness-based arena reuse;
- separate operator loops versus safe fused Boolean DAGs;
- static output-universe construction versus zero-mask pruning; and
- set membership versus bit-sliced bounded multiplicity.

### Hardware variants

- scalar machine words;
- normal compiler auto-vectorization;
- TSL fixed-width SIMD;
- TSL scalable-vector SIMD where real hardware is available; and
- native primary-ISA diagnostic.

Each ablation changes one mechanism at a time. A final “all optimizations”
configuration without isolated effects cannot explain the result.

## Workload design

Use four complementary workload families.

### 1. Exhaustive semantic micro-suite

Small schemas permit complete comparison of every intermediate bit with B0.
Cover:

- empty and singleton relations;
- all selection truth outcomes;
- many-to-one projection;
- join with zero, one, and several witnesses;
- self-join and repeated relation references;
- union, intersection, and difference;
- constraint-valid and constraint-invalid worlds;
- equivalent identities and one-rule-invalid variants; and
- final tiles at every relevant bit/vector boundary.

This suite establishes H1; it is not a performance corpus.

### 2. Controlled scaling scenarios

Generate relational plans with independent control over:

- number of base facts `N` and worlds `2^N`;
- finite-domain cardinality and relation arity;
- number of plan nodes and live intermediate tuples;
- join-key cardinality and possible witness fanout;
- projection collision rate;
- legal-world density under constraints;
- location and density of differentiating worlds;
- bounded-equivalent versus inequivalent pairs; and
- tile size and early-exit position.

Primary plots should use `N`, worlds, live tuple masks, and Boolean bytes
processed rather than vague labels such as “small” and “large.”

### 3. Published query-equivalence corpora

Pin and classify the VeriEQL benchmark corpus and any legally usable Cosette,
SPES, Qex, HoTTSQL, or educational query-pair corpora. Before looking at
performance, publish a coverage table:

```text
total pairs
parsed pairs
semantic-contract-compatible pairs
unsupported by feature and reason
counterexample within tested scope
bounded equivalent at tested scope
timeout / out of memory / internal error
replay valid / replay invalid
```

Use a development split for adapters and tuning and an untouched held-out
split for H3.

### 4. Optimizer mutation and regression corpus

Construct query pairs from:

- individual DuckDB, Calcite, or another engine's logical rewrite rules;
- historical wrong-result optimizer bugs with reproducible licenses/sources;
- deliberately mutated side conditions of valid rewrite rules; and
- generated plan pairs whose equivalence status is independently known.

Examples should exercise join elimination, predicate movement, projection and
duplicate handling, semijoin/antijoin transformations, and later nullable/bag
rules. Keep authentic historical bugs distinct from seeded mutants.

## Correctness evaluation

### 1. World enumeration

For small `N`, unpack every generated base mask and verify that bit `w` matches
the fact membership obtained by decoding world `w`. Test arbitrary tile starts,
tile sizes, powers of two, and final tails.

### 2. Operator differential testing

For every world and possible output tuple, compare each truth-table operator
with B0. On mismatch, record:

```text
scope and world ID
decoded database
plan node and operator
ground output tuple
expected and actual membership/multiplicity
backend and target profile
```

### 3. Algebraic tests

Within the declared semantics, test identities such as:

- selection composition;
- projection idempotence where types permit;
- union commutativity and associativity;
- difference self-elimination;
- join commutativity under canonical column remapping;
- distributivity cases that are valid under sets; and
- deliberately invalid identities under bags or nulls once supported.

Metamorphic identities are supplementary. They do not replace the independent
per-world oracle.

### 4. Constraint masks

Compare `V_Gamma` with explicit constraint validation for every small world.
Include composite keys, nullable cases when supported, cyclic foreign keys,
empty referenced relations, and constraints that leave zero or one legal
world.

### 5. Bag and arithmetic safety

For bit-sliced counters, exhaust all input bit patterns for each adder,
subtractor, comparator, multiplier width, and overflow condition. Compare bag
outputs including multiplicity, not only distinct tuples. Overflow must be
observable and fail closed.

### 6. SQL three-valued logic

Exhaust complete `TRUE`/`FALSE`/`UNKNOWN` truth tables and nullable-domain
queries. Include `NOT IN`, `NOT EXISTS`, `IS DISTINCT FROM`, nullable joins,
outer-join cases if admitted, and `WHERE`'s rule of retaining only true.

### 7. Replay

Execute every retained counterexample against the pinned reference engine.
Compare complete outputs, including duplicates and nulls. Diagnose dialect or
type differences explicitly. A checksum may summarize large outputs only after
full comparison has been validated on the bounded sizes.

### 8. Sanitizers and determinism

Run address/undefined-behavior sanitizers, checked allocation arithmetic, and
guarded tail buffers. Repeat the same configuration and require byte-identical
counterexample and summary artifacts.

## Primary performance metrics

### Checker-level metrics

- wall-clock and CPU time to first valid counterexample;
- wall-clock and CPU time to exhaust a bounded scope;
- total and legal worlds evaluated per second;
- maximum completely exhausted `N` under the budget;
- peak resident memory and mask-arena high-water mark;
- translated, supported, completed, timeout, and failure counts;
- counterexample fact count before and after minimization;
- preprocessing, domain construction, evaluation, comparison, decoding, and
  replay time; and
- cold and warm execution time when plan/kernel compilation is cached.

### Mechanism metrics

- logical mask bytes and physical memory bytes processed;
- bitwise operations and vector blocks executed;
- live intermediate ground-tuple count per plan node;
- join witness-pair count;
- fraction of time in mask kernels versus tuple planning/allocation;
- legal-world and counterexample-world density;
- early-exit tile position;
- hardware counters for cycles, instructions, branches, cache misses, and
  memory bandwidth where reliable; and
- generated code size and compilation time per profile.

### Portability metrics

- exact generated TSL dependency closure and implementation state;
- source and semantic differences between targets;
- speedup relative to the strongest local scalar backend;
- regret relative to the best valid implementation on each machine; and
- TSL overhead relative to the limited native diagnostic.

## Experimental protocol

### Hardware and software

Record CPU model, microcode, memory, NUMA topology, operating system, compiler,
flags, TSL/tslc revision, DBMS revision, VeriEQL revision, SMT solver and
version, and relevant environment settings. Use real hardware for performance
claims. Pin threads and memory placement; disable avoidable frequency variance
or record it.

### Timing

- separate one-time parse/domain/compile cost from repeated evaluation;
- report both cold and warm modes when caching is realistic;
- randomize paired candidate/baseline run order;
- warm up before timed repetitions;
- choose repetitions from pilot variance, not convenience;
- retain raw per-run measurements; and
- include counterexample validation/minimization only in metrics that claim
  complete user-visible latency.

### Statistical analysis

Use paired comparisons on identical query/scope instances. Report medians,
geometric means where ratios are aggregated, percentile distributions, and
paired bootstrap confidence intervals. Never discard timeouts from the
denominator; use solved-count curves and capped-time analyses in addition to
ratios over mutually solved cases.

For scaling curves, show individual query shapes or stratified summaries so
that one easy bulk stratum cannot hide join-heavy failures. Correct for multiple
confirmatory hypotheses or designate one primary outcome per RQ before the
held-out run.

### Resource budgets

Freeze wall-time, CPU-time, and memory limits per checker. If one system is
multi-threaded, either give all systems the same resources or report separate
single-thread and equal-machine experiments. A bit-parallel method must not be
credited with 32 cores against a single-thread solver without an explicitly
different scaling experiment.

## Experiment sequence

### E0: semantic smoke

Run the four-world example from `idea.md` and a small identity/invalid-rewrite
suite through B0, B2/B3, and C1. Inspect every output bit manually and through
the automated oracle.

**Breakthrough:** a complete counterexample round trip works.

**Stop:** any ambiguity remains between a bit index and its decoded database.

### E1: set-operator exhaustive correctness

Exhaust all worlds for tiny select/project/join/union/difference plans and
compare every plan node with B0.

**Breakthrough:** H1 holds for the initial fragment.

**Stop:** operator semantics require query-specific exceptions rather than
compositional rules.

### E2: representation and tile scaling

Sweep `N`, plan shape, live tuples, and tile size for B2, B3, C1, C2, and B4.
Locate compute-, memory-, tuple-planning-, and allocation-bound regions.

**Breakthrough:** H2 has plausible confirmatory regions and at least one
representative SPJUD case reaches the pilot bound.

**Stop:** useful joins fail below the frozen small scope or explicit SIMD is
incidental end to end.

### E3: SMT crossover pilot

Run compatible development query pairs through C1/C2 and B5 with identical
bounds and resource budgets. Stratify inequivalent and bounded-equivalent
cases.

**Breakthrough:** a stable feature-defined winning region exists.

**Stop:** B5 dominates all meaningful small-scope strata and truth-table
execution adds no robustness or coverage.

### E4: constraint and symmetry experiment

Measure validity-mask overhead and legal density, then evaluate each symmetry
or constraint-aware optimization against the unreduced reference.

**Breakthrough:** a proved reduction materially extends exhausted scope or
reduces time without changing outcomes.

**Stop:** reductions add complexity without moving the crossover.

### E5: randomized-testing comparison

Use the frozen mutant suite and equal budgets for C1/C2 and B6. Vary
counterexample density without exposing held-out answers to either method.

**Breakthrough:** H4 holds and unique findings replay.

**Stop:** random testing finds the same failures faster in every useful
stratum.

### E6: bag/null semantic expansion

Repeat correctness, scaling, solver, and mutation experiments for the admitted
richer fragment.

**Breakthrough:** H5 holds.

**Stop:** richer state destroys useful bounded coverage or correctness cannot
be independently validated.

### E7: engine replay and optimizer rules

Translate real rewrite pairs, generate worlds, and replay counterexamples in
the pinned engine. Report the complete translation and outcome denominator.

**Breakthrough:** real or realistic optimizer validation gains justify `G5`.

**Stop:** adapters support only synthetic expressions or dialect gaps dominate.

### E8: second architecture

Run the frozen correctness and performance matrix on a materially different
real vector family.

**Breakthrough:** H6 holds.

**Stop:** the semantic implementation forks or loses to scalar throughout.

### E9: held-out confirmation

Freeze source, configs, hypotheses, and analysis scripts before running the
held-out corpus. Preserve all outcomes, including negative and unsupported
ones.

## Required reporting views

At minimum, the final evaluation should include:

1. a semantic-feature coverage table for every system;
2. time-to-counterexample distributions for inequivalent pairs;
3. time-to-exhaust-bound distributions for bounded-equivalent pairs;
4. maximum completed scope versus query/intermediate complexity;
5. peak memory versus live tuple masks and world count;
6. a winner/crossover map against VeriEQL;
7. mutation detections shared and unique to exhaustive/random/SMT methods;
8. ablations for tiling, fusion, constraints, and symmetry;
9. per-target scalar/TSL/native performance; and
10. every unexplained failure, timeout, unsupported feature, and replay
    mismatch in the denominator.

## Interpretation and publication decisions

### Strong positive result

The strongest result would show that relational truth-table execution is exact,
finds small SQL/optimizer counterexamples substantially faster in an
explainable region, complements SMT outside that region, survives at least one
richer SQL semantic dimension, and transfers through TSL to another vector
family.

### Useful narrower result

A publishable narrower result could establish a new high-throughput bounded
checker for set-relational optimizer rules, accompanied by a rigorous crossover
and real counterexamples, even if bags or scalable vectors remain future work.
The title and claims must state that scope.

### Useful negative result

A negative result is scientifically meaningful if it rigorously identifies the
limiting mechanism—for example, intermediate ground-tuple growth makes direct
truth tables inferior to symbolic encodings beyond trivial joins—and maps that
boundary across workloads. A collection of slow microbenchmarks without such
an explanation is not enough.

### Stop result

Stop the project as a flagship paper if the novelty audit finds the mechanism,
the initial fragment cannot pass exhaustive differential validation, no
meaningful SMT or testing winning region exists, or TSL affects only an
insignificant kernel while database-level work dominates.
