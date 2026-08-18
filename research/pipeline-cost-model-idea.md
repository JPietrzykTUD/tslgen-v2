# Pipeline cost-model and optimizer idea

## Executive summary

`tslc` is a promising substrate for a database pipeline optimizer, but it is not
currently such an optimizer.

Today, `tsldata` provides primitive declarations, contracts, tests, benchmark
metadata, and implementation recipes. `tslc` parses and validates those inputs,
selects implementations for concrete targets, lowers typed TSIL regions,
resolves dependencies, and generates deterministic C++ and Rust libraries,
tests, and selected primitive-variant benchmarks.

A database-oriented optimizer would add a separate layer above this:

```text
database pipeline
        ↓
alternative physical representations and implementation recipes
        ↓
cost model informed by TSL capabilities and measurements
        ↓
globally selected pipeline
        ↓
generated or linked C++/Rust TSL implementation
```

The central research question is:

> Can a global optimizer use TSL's target capabilities and measured costs to
> choose predicate representations and SIMD implementation strategies more
> accurately than fixed policies or local per-operator decisions?

The important point is that `tslc` would remain the compiler for portable SIMD
building blocks. The pipeline representation, cost model, and database
optimization policy should belong to an independently packaged downstream
tool or database integration.

## What `tslc` currently does

It is fair to describe the project as source-driven, but `tslc` does more than
textually render `tsldata`.

The current flow is:

```text
tsldata sources and compiler assets
        ↓
parse and promote to typed catalog objects
        ↓
select implementation for primitive × type × target × backend
        ↓
scan and lower typed TSIL regions
        ↓
resolve and close primitive dependencies
        ↓
validate backend capabilities and plan artifacts
        ↓
generate C++/Rust source, tests, documentation, and optional benchmarks
```

The complete architecture is documented in
[`tslc/DESCRIPTION.md`](../tslc/DESCRIPTION.md). In particular, the existing
compiler already supplies several facts that would be valuable to a pipeline
optimizer:

- concrete primitive signatures and types;
- operation, operand-role, arithmetic, memory, conversion, shift, mask, and
  safety contracts;
- target and backend availability;
- required hardware features;
- target-specific vector and mask representations;
- selected implementation origin;
- native, composed, fallback, and unknown implementation state;
- exact typed dependencies produced by `call` regions;
- C++ and Rust callable projections;
- generated correctness tests;
- explicitly named implementation variants and benchmark scenarios.

The current optional
[`benchmark/`](../tslc/src/tslc/benchmark/) stage measures explicitly admitted
variants of individual primitive scenarios. It does not model an arbitrary
multi-operator database pipeline or choose its intermediate physical
representations.

That distinction is fundamental:

| Existing `tslc` decision | Missing database decision |
|---|---|
| Which primitive body applies to this target? | Which physical pipeline should the query use? |
| Can this specialization be emitted? | Should a predicate remain a mask or become row indexes? |
| Which dependencies and target features are required? | Is an early conversion worthwhile for later operators? |
| How is the operation expressed in C++ or Rust? | Which complete strategy is cheapest for this workload? |
| Which named primitive variant wins a benchmark? | Which combination of representations and variants wins globally? |

## Motivating example

Consider:

```sql
SELECT SUM(c)
FROM t
WHERE a < 10 AND b > 20;
```

Several semantically equivalent physical strategies are possible.

### Strategy A: retain a predicate mask

```text
load a
  → compare a < 10
  → mask₁

load b
  → compare b > 20
  → mask₂

mask₁ AND mask₂
  → masked load or masked aggregate over c
```

This can be attractive when predicates are dense, mask operations are native,
and later work supports masked execution efficiently.

### Strategy B: create a selection vector

```text
load a
  → compare a < 10
  → materialize matching row indexes

gather b at those indexes
  → compare b > 20
  → retain fewer indexes

gather and aggregate c
```

This can be attractive when the first predicate is highly selective: later
operators avoid processing most rows. It may be poor when gathers and index
materialization are expensive.

### Strategy C: compact values

```text
load a
  → compare a < 10
  → predicate mask
  → compact matching b and c values

process the remaining pipeline densely
```

This pays an early compression cost in exchange for dense downstream
execution.

### Why the choice is nontrivial

The best strategy can depend on:

- input cardinality;
- predicate selectivity and correlation;
- data type;
- vector width or scalable vector length;
- native mask and predicate support;
- gather, compress, and conversion performance;
- cache residency and memory bandwidth;
- number and kind of later operators;
- compiler and optimization settings;
- generated C++ versus Rust code quality;
- register pressure, fusion, and instruction overlap.

`tslc` can provide implementations of the constituent operations. It does not
currently represent or optimize these complete strategies.

## The four principal missing layers

## 1. A small database pipeline representation

The downstream optimizer needs a typed representation of the logical pipeline.
The first version need not represent arbitrary SQL or a complete relational
algebra. A deliberately narrow model is preferable:

```text
Scan(a, b, c)
  → Filter(a < 10)
  → Filter(b > 20)
  → AggregateSum(c)
```

Pipeline edges would carry physical properties such as:

- dense values;
- vector predicate mask;
- integral bitmask or bitmap;
- selection vector of row indexes;
- compacted values.

Operator nodes would state only database semantics and available physical
recipes. They should not reproduce TSL primitive selection, target capability,
or backend spelling rules.

### Ownership

This is database interpretation and belongs to a downstream tool or engine. It
should depend one way on public, typed `tslc` facts. `tslc` and `tsldata` should
not import the tool, register its operator kinds, or change normal generation
for it.

## 2. Alternative physical recipes

For each logical operator, the tool needs one or more ways to implement it.
Initially, these recipes can be authored explicitly.

| Logical operation | Possible physical recipe |
|---|---|
| Filter | comparison producing and retaining a vector mask |
| Filter | comparison followed by mask-to-index conversion |
| Filter | comparison followed by value compression |
| Subsequent filter | masked load and comparison |
| Subsequent filter | gather through a selection vector |
| Aggregate | masked reduction |
| Aggregate | dense reduction over compacted values |
| Representation change | mask to integral bitmap |
| Representation change | mask or bitmap to selection vector |
| Representation change | selection vector to compacted values |

Each recipe should identify:

- required TSL primitives;
- input and output physical representations;
- type and shape restrictions;
- semantic preconditions;
- workload parameters that influence cost;
- whether it can be fused with adjacent recipes.

Given a recipe, the tool should ask the compiler rather than infer:

- Are all required primitives available for this profile and backend?
- Are they native, composed, or generic fallbacks?
- Which target features are required?
- Which exact dependencies are pulled into the emitted profile?
- What mask representation does the target use?
- What generated callable identity should the recipe invoke?

Automatic recipe synthesis is a possible later compiler-research project. It
is not required for the first database experiment.

## 3. Measurements and a cost model

A cost model predicts the cost of a physical recipe in context. Conceptually:

```text
cost(
    recipe,
    machine,
    backend and compiler,
    data type,
    input size,
    selectivity,
    input representation,
    cache or memory scenario
)
```

The first model should be simple and inspectable. It does not require machine
learning. A measurement table with interpolation or fitted piecewise functions
is sufficient:

| Machine | Recipe | Selectivity | Rows | Memory scenario | Measured cost |
|---|---|---:|---:|---|---:|
| AVX2-like | retain mask | 1% | 1M | hot | … |
| AVX2-like | selection vector | 1% | 1M | hot | … |
| AVX2-like | retain mask | 90% | 1M | hot | … |
| AVX-512-like | retain native mask | 1% | 1M | hot | … |
| AVX-512-like | compact | 25% | 1M | streaming | … |

The model may then expose crossover rules, for example:

```text
on profile P:
    retain masks above selectivity threshold S₁
    use selection vectors below S₂
    compact only when at least K downstream operations reuse the result
```

These are examples, not claims about the actual hardware. The thresholds must
be measured.

### Primitive benchmarks are not enough

It would be tempting to estimate a pipeline by adding isolated costs for
`compare`, `mask_to_indexes`, `gather`, and `reduce`. That is unlikely to be
accurate because compiled pipelines exhibit:

- instruction overlap and dependencies;
- fusion and inlining;
- loop and remainder handling;
- register pressure;
- cache and prefetch behavior;
- materialization costs;
- branch or predicate behavior;
- compiler transformations;
- shared loads and eliminated intermediates.

The existing primitive benchmark infrastructure is useful for understanding
individual operations, validating candidates, and supplying priors. A credible
pipeline cost model also needs **generated micro-pipeline measurements**.

### Required evidence identity

Every measurement should be tied to:

- pipeline and recipe identity;
- TSL compiler and source digest;
- primitive and implementation identities;
- backend and compiler version;
- compilation flags;
- target profile and observed CPU facts;
- data generator and selectivity;
- input size and memory scenario;
- repeated raw samples and reduction method.

Without this identity, stale or incompatible measurements could silently
influence plan selection.

## 4. A global planner

Once representations, recipes, and costs exist, the optimizer chooses the
cheapest valid path through the pipeline.

For a linear pipeline, ordinary dynamic programming is sufficient:

1. At an operator, enumerate its legal output representations.
2. For every legal input representation, calculate:
   - accumulated cost so far;
   - required conversion cost;
   - operator-recipe cost.
3. Retain the cheapest known path to each output representation.
4. Continue to the next operator.
5. Select the cheapest complete path at the pipeline output.

Conceptually:

```text
                            ┌─ mask ──────── masked next operator
dense input → first filter ─┼─ selection ─── gathered next operator
                            └─ compacted ─── dense next operator
```

This is analogous to tracking physical properties in a query optimizer. The
novelty would not be dynamic programming itself. The research question is
whether exposing target-specific SIMD representations, conversions, and
implementation provenance creates a useful physical planning space.

### Later runtime adaptation

A later system could compile two or more safe plans and select among them at
runtime using observed selectivity. That should follow, not precede, a static
prototype. First establish that the plans have meaningful and predictable
crossover points.

## Proposed architecture and ownership

The clean dependency direction is:

```text
tsldata
   ↓
tslc typed catalog, selection, lowering, closure, and generated artifacts
   ↓
stable capability snapshot / generated callable manifest
   ↓
downstream pipeline optimizer
   ↓
database-engine adapter
```

| Component | Owned responsibility |
|---|---|
| `tsldata` | Primitive contracts, implementations, authored value tests, target-independent primitive benchmark metadata |
| `tslc` | Parsing, validation, target selection, dependency closure, backend generation, callable identities, primitive tests and benchmarks |
| Capability projection | Deterministic, read-only compiler facts needed by downstream consumers |
| Downstream optimizer | Pipeline IR, representations, physical recipes, measurements, cost model, plan search, diagnostics |
| Engine adapter | Logical-plan extraction, cardinality/selectivity estimates, execution and runtime observations |

The proposed tool must not:

- parse generated C++ or Rust to rediscover compiler facts;
- infer capabilities from primitive or target names;
- duplicate target-feature and dependency selection;
- mutate compiler registries or defaults;
- present measured database policies as compiler guarantees;
- put SQL or query-optimizer semantics into TSIL;
- put pipeline benchmark code into `tsldata`.

If the tool requires an unavailable compiler fact, the first response should be
to determine whether that fact is genuinely compiler-owned and
projection-neutral. Only such facts justify a focused public compiler
projection. Query selectivity, representation-planning policy, and pipeline
costs remain downstream facts.

## Minimal viable research prototype

The first experiment should be intentionally small enough that every complete
physical plan can also be measured as an oracle.

### Scope

- Pipeline: `filter → filter → aggregate`.
- Type: one integer type, such as 32-bit signed integers.
- Representations:
  - dense;
  - mask;
  - selection vector.
- Targets:
  - one AVX2-like profile;
  - one AVX-512-like or native-predicate profile.
- Backend: begin with whichever generated backend has the most complete
  required primitive and benchmark coverage.
- Recipes: explicit, handwritten physical alternatives.
- Cost model: lookup table plus interpolation or simple piecewise regression.
- Planner: dynamic programming.

### Experimental dimensions

- Selectivity: for example 1%, 5%, 10%, 25%, 50%, 75%, and 95%.
- Input size:
  - small/hot;
  - cache-sized;
  - streaming or larger-than-cache.
- Predicate relationship:
  - independent;
  - correlated, if the initial data generator can represent it cleanly.
- Pipeline depth: begin with two filters, then test whether additional
  downstream work changes the optimal materialization point.

### Baselines

1. Always retain masks.
2. Always materialize selection vectors.
3. Always compact after the first predicate.
4. Greedy local choice at each operator.
5. A simple manually chosen selectivity threshold.
6. Global cost-model planner.
7. Exhaustive measured oracle.

### Required metrics

- end-to-end runtime or cycles per input tuple;
- planner prediction error;
- regret relative to the exhaustive oracle;
- frequency with which each baseline chooses the wrong plan;
- planning overhead;
- generated code size and compile time;
- sensitivity to selectivity-estimation error;
- portability of thresholds across target profiles;
- contribution of conversion costs and downstream reuse.

### Success criterion

The exact numerical threshold should be chosen before evaluating the final
system, but the qualitative requirement is:

> The global planner must remain close to the measured oracle and must
> materially outperform fixed and local policies in regions where target
> capabilities and downstream reuse make their decisions suboptimal.

If a single local threshold performs equally well over the evaluated space,
the larger optimizer is not justified.

## Suggested implementation sequence

### Slice 1: capability inventory

For the selected pipeline, identify the exact TSL primitives, types, profiles,
representations, and backend callables already available. Record missing
combinations honestly.

No pipeline framework should be designed until this inventory shows that at
least two complete strategies can be generated and tested.

### Slice 2: one external micro-pipeline generator

Create one downstream executable or generated harness for the fixed
`filter → filter → aggregate` pipeline. Hard-code two physical recipes while
reusing compiler-owned callable and target facts.

This slice establishes the dependency boundary and measures whether the
strategies actually cross over.

### Slice 3: deterministic measurement records

Define the evidence schema and collect repeated measurements for the bounded
matrix. Keep the raw samples and all relevant identity fields. Do not introduce
a learned model yet.

### Slice 4: offline cost model

Fit or interpolate costs from a training subset. Evaluate predictions against
held-out measurements and quantify error by selectivity and target.

### Slice 5: dynamic-programming planner

Replace the hard-coded recipe choice with the smallest global planner. Validate
its choices against exhaustive enumeration.

### Slice 6: real engine integration

Only after the bounded prototype succeeds, connect it to one database engine or
research query compiler. The engine supplies pipeline structure and estimated
cardinalities; the downstream optimizer returns a physical strategy.

### Slice 7: broader research questions

Possible extensions include:

- integral bitmaps and compacted values;
- SVE or RVV predicates;
- runtime selectivity adaptation;
- joins and group-by pipelines;
- cross-language C++/Rust comparison;
- semantics-aware transfer of cost models between CPUs;
- counterfactual evaluation of missing ISA primitives.

Each extension should be justified by a demonstrated limitation of the smaller
model.

## What `tslc` saves and what remains

### Infrastructure already supplied

- portable SIMD primitive implementations;
- target and feature selection;
- native/composed/fallback provenance;
- exact primitive dependency closure;
- target-specific mask knowledge;
- C++ and Rust generation;
- generated correctness tests;
- primitive-variant benchmark planning;
- deterministic artifact and evidence identities.

### Substantial missing research work

- database pipeline representation;
- explicit physical properties;
- alternative operator recipes;
- generated micro-pipeline harnesses;
- workload-sensitive measurements;
- cost estimation;
- global plan selection;
- estimation-error handling;
- database-engine integration;
- end-to-end evaluation against existing execution strategies.

Therefore, the honest characterization is:

> `tslc` is a potentially valuable execution-variant and capability substrate
> for a database pipeline optimizer. It is not an optimizer that is nearly
> complete.

## Relation to richer semantic modeling

A complete executable semantic catalog or formal verifier is not a prerequisite
for the first prototype.

The initial optimizer can use explicitly authored physical recipes whose
correctness is covered by existing generated tests and end-to-end differential
checks. Richer semantics would later enable:

- automatic validation that a recipe preserves logical operator behavior;
- automatic discovery or synthesis of alternative recipes;
- safe composition of native and fallback primitives;
- stronger cross-language equivalence guarantees;
- more principled representation transformations.

This keeps the database project focused. Formal semantics can strengthen the
foundation later without becoming the central database contribution.

## Research contribution versus engineering contribution

The following would mainly be engineering:

- generating one filter pipeline with TSL primitives;
- adding a benchmark harness;
- fitting a cost table;
- choosing a strategy using a fixed threshold;
- replacing hand-written intrinsics in an existing engine.

A stronger scientific contribution requires evidence for a general claim such
as:

> Target-specific SIMD representation and capability facts must be visible to
> a global physical optimizer because their conversion costs and downstream
> effects make local execution choices systematically suboptimal.

The paper-worthy result would consist of:

- a clearly defined physical planning space;
- a planning method;
- an empirically validated cost model;
- cross-architecture evidence;
- comparison with fixed, local, and exhaustive-oracle strategies;
- a real database integration;
- insight into when and why representation choices change.

## Main risks and falsification conditions

### The plan space may be too small

A simple selectivity threshold may choose as well as a global optimizer.

**Response:** test this in the bounded prototype before expanding scope.

### Micro-pipeline costs may not transfer

Measurements from isolated generated kernels may fail to predict behavior
inside a database engine.

**Response:** retain engine-level calibration and report the transfer error;
do not present microbenchmark policies as universal.

### Cardinality error may dominate

The planner may select poor representations when selectivity estimates are
wrong.

**Response:** perform sensitivity analysis, consider robust plans, and later
support runtime switching.

### Existing engines may already express the same choice

The optimizer could be an ordinary physical-property search with TSL replacing
the implementation library.

**Response:** compare with the engine's current strategy and demonstrate which
new representation/capability facts or cross-architecture choices become
possible.

### Compiler differences may overwhelm the model

Generated C++ and Rust or different compiler versions may have inconsistent
crossovers.

**Response:** include compiler and backend identity in the evidence. Treat
cross-language transfer as an experimental question, not an assumption.

### TSL coverage may be insufficient

Required gather, mask conversion, compression, or reduction combinations may
not all be available and verified.

**Response:** start from an exact coverage inventory and choose the smallest
complete vertical slice. Missing coverage is a reported limitation, not a
reason to invent placeholder implementations.

## Final assessment

The idea is realistic, but it represents substantial new database research
above the current compiler.

The lowest-risk path is:

1. select one small filter pipeline;
2. enumerate two or three complete physical strategies;
3. generate and measure them on two meaningfully different target profiles;
4. establish whether their performance crosses over with selectivity or
   downstream reuse;
5. build the simplest cost model and global planner capable of predicting
   those crossovers;
6. stop if it does not outperform local rules;
7. integrate into a real engine only if the bounded result is promising.

This approach uses `tslc` for what it already does well—portable, typed,
target-aware generation of SIMD building blocks—while placing pipeline
semantics and cost-based optimization in the database layer where they belong.

