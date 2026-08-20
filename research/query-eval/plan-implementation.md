# Implementation plan: relational truth-table execution

## Objective

Build the smallest trustworthy system that can answer the following question:

> Can two relational expressions be evaluated over every database in a small,
> finite scope by representing database instances as bit positions and applying
> relational operators to those bitsets?

The initial deliverable is a bounded model checker and counterexample
generator, not a general SQL engine. It should accept a typed relational query
pair, a finite-domain schema, and optional integrity constraints; exhaust the
declared world space in tiles; and return a replayable counterexample or a
precisely scoped bounded-equivalence result.

## Ownership and repository boundary

The prototype should be an independently owned research consumer of generated
TSL C++. It owns:

- the bounded schema and finite-domain model;
- relational and SQL semantics;
- world enumeration, tiling, and symmetry policies;
- scalar and SIMD truth-table execution;
- query-pair and corpus adapters;
- constraint evaluation;
- counterexample decoding and DBMS replay;
- benchmark scenarios, measurement records, and reports.

`tslc` and `tsldata` continue to own primitive semantics, extension/profile
selection, lowering, dependency closure, generation, and generated
verification. They must not learn about SQL, possible worlds, query
equivalence, or the prototype's command line.

If a required general-purpose primitive is absent, first use a simple local
implementation or an existing generated composition. Propose any TSL primitive
change as a separate, projection-neutral slice with its own justification and
tests. Do not add a `query_eval` or `world_join` primitive to the core library.

## Explicitly out of scope for the first slice

- unrestricted SQL equivalence;
- parsing the full SQL grammar;
- arbitrary strings, decimals, dates, or user-defined functions;
- bag semantics, `NULL`, aggregation, ordering, and recursion;
- optimizer integration inside a production DBMS;
- distributed checking;
- GPU, SIMT, or FPGA backends;
- automatic rewrite discovery; and
- changes to `tslc` architecture.

These items are conditional milestones, not implicit requirements of the
prototype.

## Breakthrough and stop gates

Each gate should have a dated record containing the exact artifact revision,
inputs, commands, output, and decision. Passing a later gate does not erase a
failure or scope change at an earlier one.

| Gate | Question | Evidence to continue | Stop or reframe when |
| --- | --- | --- | --- |
| **G0: novelty** | Is the physical method unreported in database work? | A closest-work ledger leaves a clear delta: exhaustive bounded database worlds as bit positions, relational truth-table execution, and counterexample decoding. | Equivalent published, patented, or production work is found, or the remaining delta is only “implemented using TSL.” |
| **G1: semantic kernel** | Does the representation compute correct set-relational semantics? | Every query pair in an exhaustive tiny oracle suite matches explicit per-world evaluation, and a found bit decodes to a replayable counterexample. | Tuple universes or operator definitions cannot be made compositional and deterministic. |
| **G2: data-parallel headroom** | Does transposition create material execution headroom? | On frozen small-scope SPJUD scenarios, the tiled bit-parallel engine materially outperforms explicit per-world evaluation and explicit SIMD improves the scalar word-parallel implementation in compute-relevant regions. | State construction dominates, SIMD gives negligible benefit, or useful joins already exhaust memory below the preregistered pilot scope. |
| **G3: competitive counterexamples** | Is the engine useful beside SMT? | It wins time to counterexample or completed bounded coverage on a meaningful, predeclared subset of VeriEQL-compatible pairs. | VeriEQL or another strong solver dominates every compatible small-scope class after fair tuning. |
| **G4: SQL viability** | Do bags, `NULL`, and constraints preserve a useful region? | At least bags plus `NULL` or bags plus constraints remain exact and leave practical scopes large enough to expose seeded and historical bugs. | Richer semantics collapse the bound to toy cases or require unsound approximations. |
| **G5: database value** | Does it improve real optimizer validation? | Counterexamples replay against a real engine, and equal-time comparison shows additional deterministic coverage or bugs relative to randomized testing and solver-only checking. | The system cannot consume realistic plan pairs or provides no incremental bug-finding/validation value. |
| **G6: publication** | Is the result more than a fast Boolean kernel? | The work establishes a new relational execution model, a useful empirical crossover, exact SQL semantics for a meaningful fragment, and a reproducible artifact. | Only microbenchmark speedups remain, with no database-level capability or boundary result. |

The first bounded pilot targets `G0` through `G3`. No production DBMS patch or
accelerator expansion is justified before `G3`.

## Proposed source layout

Create the source tree only after `G0` records a continue decision:

```text
research/query-eval-src/
  AGENTS.md                       # prototype-local rules and commands
  CHARTER.md                      # semantic guarantees and non-goals
  README.md                       # build, run, and supported-scope summary
  CMakeLists.txt
  cmake/
  include/query_eval/
    types.hpp                     # typed values and finite domains
    schema.hpp                    # relations, attributes, constraints
    ground_tuple.hpp              # canonical tuple identity and ordering
    query.hpp                     # typed relational-algebra AST
    scope.hpp                     # complete bounded semantic manifest
    world_tile.hpp                # world range and tail contract
    world_mask.hpp                # backend-independent mask view
    world_relation.hpp            # tuple -> world-mask relation
    counterexample.hpp            # decoded database and replay artifact
    result.hpp                    # tri-state checker result
  src/
    domain_builder.cpp
    query_validation.cpp
    ground_universe.cpp
    world_enumerator.cpp
    constraint_masks.cpp
    scalar_reference.cpp
    scalar_word_backend.cpp
    tsl_simd_backend.cpp
    relational_evaluator.cpp
    output_compare.cpp
    counterexample.cpp
    report.cpp
  adapters/
    json_query_pair.cpp            # first stable interchange
    verieql_corpus.cpp             # conditional corpus adapter
    duckdb_replay.cpp              # later replay/integration boundary
  tests/
    unit/
    exhaustive/
    differential/
    replay/
  benchmarks/
    kernels/
    checker/
    scenarios/
  configs/
    smoke.json
    pilot.json
    confirmatory.json
  tools/
    run_matrix.py
    summarize.py
  manifests/
    dependencies.lock
    corpora.toml
    experiments.toml
```

Generated TSL projects, builds, downloaded corpora, and measurements belong
under `./tslctmp/query-eval/...`. Commit small hand-authored fixtures, manifests,
schemas, and deterministic summaries; do not commit host-specific build trees.

## Core data model

Use explicit typed objects rather than passing JSON dictionaries beyond the
adapter boundary.

### Semantic scope

Every result carries an immutable scope record:

```text
SemanticScope
  schema_digest
  query_pair_digest
  relation_semantics          # set, later bounded bag
  finite_domain_per_type
  base_multiplicity_bound     # one for sets; explicit for bags
  null_semantics
  integer_width_and_overflow
  constraints
  ground_fact_count
  world_count
  enumeration_order
  symmetry_rules
  supported_operator_set
  dialect_or_algebra_version
```

Two bounded-equivalence results are comparable only when these fields match.

### Ground universe

```text
GroundTuple
  relation_id
  ordered typed values
  stable fact index            # base facts only

GroundUniverse
  schema
  base tuples per relation
  possible intermediate/output tuples per plan node
```

Canonical tuple ordering is part of deterministic output and counterexample
decoding.

### World masks and relations

```text
WorldTile
  first_world
  world_count
  storage_bits                 # rounded to backend block size
  tail_mask

WorldMaskView
  pointer
  logical_world_count
  storage_word_count

WorldRelation
  output_schema
  ordered tuple entries
  one WorldMaskView per tuple
```

The arena owning mask storage is separate from the views. Operator evaluation
must release dead intermediates deterministically to keep memory proportional
to live plan state.

## Milestone 0: freeze the novelty and semantic claims

### 0.1 Build a closest-prior-art ledger

Search and record at least:

- bounded SQL equivalence and containment tools, including VeriEQL, Cosette,
  Qex, SPES, HoTTSQL, and table/relation theories;
- SQL and optimizer testing, including SQLancer and differential-plan testing;
- finite relational model finders, Alloy/Kodkod, SAT, BDD, and exhaustive
  truth-table evaluation;
- provenance semirings, lineage circuits, probabilistic databases, and
  possible-world representations;
- SIMD-PAC-DB and any bitmask-across-databases execution;
- bit-parallel circuit simulation and equivalence checking;
- deductive database and semantic query-optimization systems;
- theses, patents, and production optimizer validation tools.

For every source, record the represented dimension, whether the state space is
sampled or exhaustive, the supported query semantics, how counterexamples are
generated, the physical execution mechanism, and the exact overlap with this
proposal.

### 0.2 Freeze the first semantic fragment

Specify:

- typed finite integers and booleans;
- set-valued base relations;
- selection, projection, rename, product/equijoin, union, intersection, and
  difference;
- equality and ordered scalar predicates;
- no `NULL`, bags, arithmetic overflow, or aggregation;
- optional primary-key and finite-domain check constraints only; and
- exact output comparison without ordering.

### 0.3 Freeze result language

Define the exact meaning and serialization of `COUNTEREXAMPLE`,
`BOUNDED_EQUIVALENT`, and `UNSUPPORTED`. Write examples of statements the tool
must reject, such as “the queries are equivalent” without a qualifying bound.

### Deliverables and gate

- closest-work ledger;
- one-page claim matrix;
- semantic scope specification;
- hand-worked truth tables for at least five operator combinations; and
- recorded `G0` decision.

If `G0` fails, do not create the implementation source tree.

## Milestone 1: independent explicit-world reference

### 1.1 Implement the typed schema and query AST

Start with a programmatic or small JSON relational-algebra representation. Do
not begin by parsing arbitrary SQL. Validation must reject schema mismatches,
unsupported operators, invalid predicates, unbounded domains, and incompatible
query outputs before execution.

### 1.2 Construct finite ground universes

Enumerate base and possible output tuples with stable IDs. Add size estimates
and refuse a configuration that exceeds an explicit tuple/world/memory budget.
The refusal must report which relation, domain, or plan node caused growth.

### 1.3 Implement explicit per-world semantics

For small scopes, enumerate one concrete database at a time and evaluate the
typed relational algebra using ordinary set containers. This is the semantic
oracle, not a performance baseline to optimize aggressively.

### 1.4 Implement query comparison and decoding

Compare complete outputs, decode differing worlds, serialize a replay artifact,
and deterministically minimize by deleting base tuples while preserving the
difference.

### Validation

- unit tests for every operator;
- exhaustive tests of all worlds for schemas with up to approximately eight
  independent facts;
- algebraic identities and deliberately invalid rewrites;
- deterministic artifact snapshots; and
- optional replay in DuckDB for the compatible set-semantics subset.

## Milestone 2: scalar word-parallel truth-table engine

### 2.1 Generate base masks by world range

Implement procedural truth-table-variable generation for arbitrary tile start
and length. Test patterns around powers of two, non-aligned starts, final tails,
zero worlds, and maximum configured fact index.

### 2.2 Implement a scalar `uint64_t` mask backend

Provide AND, OR, XOR, AND-NOT, zero/any, first-set, copy, and tail clearing over
arrays of 64-bit words. Keep this backend separate from relational planning so
it remains the portable algorithmic baseline.

### 2.3 Implement world relations and set operators

Implement each formula from [`fundamentals.md`](fundamentals.md). Use key-based
indexes for joins and deterministic tuple maps. Begin without cross-node
optimizations; correctness and memory accounting matter more than fusion.

### 2.4 Add tiled comparison and early exit

Evaluate both queries over one tile, compute the relational miter, release tile
memory, and continue. The configured traversal order must determine which
counterexample is returned.

### 2.5 Cross-check every mask

For tiny scopes, unpack each result bit and compare it with the explicit-world
reference at every plan node, not only at final output. Diagnostics should name
the operator, tuple, world, expected membership, and actual membership.

### Deliverables and `G1`

- all set operators pass exhaustive differential validation;
- the examples in `idea.md` are executable tests;
- valid-world masking passes an exhaustive primary-key/check-constraint suite;
- every counterexample replays in the independent oracle; and
- `G1` is recorded before SIMD work begins.

## Milestone 3: TSL SIMD backend and performance sanity

### 3.1 Inventory generated TSL capabilities

For the selected profiles, record availability and verification for bitwise
operations, vector loads/stores, comparison or mask reduction, and safe tail
handling. Use public `tslc` or `dev.sh` inspection and generation paths. Do not
assume that a primitive declaration implies a native implementation.

### 3.2 Define a narrow kernel interface

Vectorize long world-mask loops, not relational tuple planning. The first TSL
kernels should implement:

- `and`, `or`, `xor`, and `and_not` into aligned mask arrays;
- fused XOR-OR output comparison;
- zero/any reduction; and
- optional population-count summaries.

First-set-bit decoding may remain a scalar operation on the first nonzero
machine word. Avoid expanding the TSL surface merely to eliminate negligible
scalar control.

### 3.3 Instantiate fixed and scalable profiles

Start with the best available local x86 profile plus scalar. Add a second
materially different vector family only when real hardware or an executable
runner is available. Emulation can prove build/correctness coverage but not
performance portability.

### 3.4 Add a limited native diagnostic

Implement one carefully optimized native-intrinsics kernel for the primary ISA
to measure TSL abstraction overhead. It is a benchmark oracle, not a second
relational engine.

### 3.5 Profile the complete checker

Measure mask generation, tuple-universe construction, join indexing, Boolean
kernels, allocation, comparison, and decoding separately. A fast bitwise loop
does not pass `G2` if tuple planning or memory dominates end to end.

### `G2` decision

Continue only if:

- explicit SIMD gives a repeatable benefit in at least the compute-relevant
  preregistered regions;
- complete checker time materially beats explicit per-world evaluation;
- a representative SPJUD pair reaches the frozen pilot bound without exceeding
  its memory budget; and
- the TSL implementation remains close enough to the native diagnostic that
  portability is not purchased by losing the central gain.

Exact thresholds and scenarios are defined in
[`plan-evaluation.md`](plan-evaluation.md) and frozen after exploratory tuning.

## Milestone 4: constraints, symmetry, and search order

### 4.1 General validity masks

Add unique, foreign-key, `NOT NULL`-ready, and simple cross-relation
constraints one at a time. Compare mask-based validation with explicit-world
validation exhaustively.

### 4.2 Measure legal-world density

Record total worlds, legal worlds, validation cost, and wasted Boolean work.
Do not introduce a constraint-aware generator until a frozen scenario shows
that post-generation masking is a material bottleneck.

### 4.3 Add proved symmetry breaking

Begin with canonical fresh-domain values or row-slot permutations whose
isomorphism is easy to state. For tiny scopes, compare the reduced and
unreduced result sets to establish coverage preservation.

### 4.4 Implement small-counterexample order

Compare scope iteration, Hamming-weight enumeration, and post-hoc minimization.
Keep bounded-proof throughput and human-readable counterexample size as
separate objectives.

## Milestone 5: strong solver and corpus comparison

### 5.1 Build a compatible query-pair importer

Import only the subset whose semantics match the prototype. Every exclusion
must have a structured reason: unsupported syntax, domain construction,
dialect, bag/null requirement, constraint form, or bound mismatch.

### 5.2 Pin VeriEQL and other baselines

Record revisions, solver versions, encodings, bounds, timeouts, hardware, and
whether parsing/translation is included. Validate generated counterexamples by
replay under the same semantic contract.

### 5.3 Separate inequivalence and bounded-equivalence workloads

Time to first counterexample and time to exhaust the bound are different
problems. Report them separately and never credit a timeout as equivalence.

### 5.4 Explore a simple hybrid

Only after pure results are frozen, test a deterministic policy such as:

```text
truth-table checker through bound B;
if no counterexample and more reasoning is requested, invoke VeriEQL.
```

Do not begin with a learned selector. The first question is whether the two
methods have complementary winning regions.

### `G3` decision

The project needs a meaningful region in which it improves time to a valid
counterexample, bounded coverage per unit time, or timeout robustness. Beating
only explicit per-world DBMS invocation is insufficient for a research claim.

## Milestone 6: SQL bag semantics and `NULL`

This milestone begins only after `G3`.

### 6.1 Add SQL three-valued predicates

Implement true/unknown masks and test complete Kleene truth tables. Add nullable
domains, `IS NULL`, `IS DISTINCT FROM`, conjunction, disjunction, and negation
before `IN`, `NOT IN`, or outer joins.

### 6.2 Choose and implement one bag representation

Prototype bit-sliced bounded multiplicities first. Implement nonzero,
comparison, addition, and projection before join multiplication. Every
operation carries an overflow mask and fails closed when the configured bound
is insufficient.

Replace Boolean world numbering with a tested mixed-radix enumeration of all
base multiplicities from zero through the declared input bound. Record both
the input multiplicity bound and sound per-node counter widths in the semantic
scope. The bag checker is not exhaustive unless it covers every such bounded
assignment.

Compare the bit-sliced approach against a slot-based reference on very small
scopes. Do not support both as permanent optimized paths unless measurements
show genuinely different useful regions.

### 6.3 Add one difficult semantic discriminator

Suitable targets include:

- `DISTINCT` removal under bags;
- `NOT IN` versus `NOT EXISTS` with nullable keys;
- projection across duplicate join witnesses; or
- `EXCEPT` versus `EXCEPT ALL`.

The feature should be selected because it represents real optimizer risk, not
because it is easy to encode.

### 6.4 Add bounded `COUNT`

`COUNT` is the first aggregation target. Specify empty-input behavior, null
elimination, result width, grouping, and overflow. Defer general `SUM`, decimal,
and floating-point semantics.

### `G4` decision

Record whether the practical world/fact bound remains useful and whether
historical or seeded SQL bugs require the newly supported semantics. If bag and
null support leaves only trivial worlds, retain the set fragment as the honest
result rather than claiming general SQL verification.

## Milestone 7: optimizer validation integration

### 7.1 Choose one engine boundary

Prefer a stable logical-plan interchange or exported rewrite-rule corpus. An
isolated DuckDB or Calcite adapter is acceptable; modifying the production
optimizer is not required. Translate original and rewritten plans into the
prototype's typed algebra with a fail-closed coverage report.

### 7.2 Replay counterexamples

For every model-checker counterexample:

1. create a fresh database under the pinned engine and dialect;
2. install declared constraints where relevant;
3. execute original and rewritten queries with complete result capture;
4. distinguish checker bugs, dialect differences, and confirmed engine bugs;
5. minimize only while replay continues to differ; and
6. store a deterministic regression artifact.

### 7.3 Compare equal resource budgets

Compare against randomized and solver-based validation with the same wall-time
or CPU budget. Count the full denominator: translated, unsupported, completed,
timed out, counterexample, spurious, and replay-confirmed cases.

### `G5` and `G6`

Proceed toward a paper only if the system demonstrates database-level value:
new confirmed counterexamples, stronger bounded coverage, a robust performance
crossover, or a clear negative boundary explaining when exhaustive relational
execution cannot work.

## Milestone 8: conditional accelerator study

GPU or FPGA work is not part of the first paper plan. It becomes justified only
if CPU truth-table execution is useful and profiling shows a stable streaming
mask algebra worth offloading.

Possible follow-on questions are:

- whether SIMT should assign one tile or tuple mask to each warp;
- whether an FPGA pipeline can fuse a fixed relational mask DAG;
- whether transfer and compilation costs erase the increased bit throughput;
- whether the same semantic DAG can remain shared while scheduling is
  accelerator-specific; and
- which portion of TSL should remain an instruction abstraction versus a
  separate accelerator backend.

The follow-on should compare strong native implementations. Sharing source
syntax alone is not a performance-portability result.

## Implementation quality requirements

### Determinism

- stable schema, tuple, plan, and world ordering;
- byte-identical reports and fixtures for identical inputs;
- recorded seeds only for explicitly randomized apparatus;
- no unordered-container iteration in artifacts; and
- deterministic counterexample selection under one policy.

### Diagnostics

Errors should identify the query node, schema item, domain, requested bound,
estimated world/tuple/memory size, and actionable remedy. Unsupported semantics
are first-class results, not assertions or silently changed behavior.

### Memory safety

Use checked size arithmetic, explicit allocation budgets, aligned storage, and
tail masks. Exercise sanitizer builds, zero-length inputs, one-bit tails,
vector-boundary tails, all-zero/all-one masks, and allocation failure.

### Reproducibility

Pin external tools and corpora in manifests. Network fetching must be explicit,
versioned, checksum-verified, and outside ordinary tests. Hardware detection is
recorded and skippable; unavailable machines produce gaps, not fabricated
portability evidence.

## Validation commands once a source tree exists

The exact commands should be owned by the future prototype's `AGENTS.md` and
README. At minimum the workflow should provide:

```text
configure and build scalar reference
run unit and exhaustive semantic tests
generate the smallest required TSL project
build and run the TSL backend
run differential tests across backends
run the smoke benchmark matrix
validate replay artifacts in the pinned DBMS
check deterministic summaries
```

For this documentation-only slice, validation is limited to path/link review,
cross-document terminology review, and `git diff --check`.
