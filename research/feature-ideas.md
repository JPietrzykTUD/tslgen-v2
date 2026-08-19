# Scientific killer-feature ideas for `tslc`

## Executive answer

`tslc` is worthwhile, but it will not become scientifically outstanding merely
by supporting more primitives, more instruction sets, or a third output
language. Those are useful product improvements and evidence of engineering
quality. They are not, by themselves, new research.

The project's unusual opportunity is that it sits at a junction that most
systems occupy only partially:

- it has a source-level catalog of domain primitives and implementation
  alternatives;
- it represents operation, arithmetic, memory, conversion, mask, safety,
  feature, and dependency facts before rendering;
- it generates idiomatic artifacts for two materially different languages,
  C++ and Rust;
- it spans fixed-width and scalable vector architectures;
- it can expose whether an implementation is native, composed, inherited,
  generic, or unavailable;
- it already plans differential value tests and benchmarkable variants.

This is visible in the [compiler architecture](../tslc/DESCRIPTION.md), the
typed [operation contracts](../tslc/src/tslc/catalog/semantics.py),
[arithmetic contracts](../tslc/src/tslc/catalog/arithmetic.py),
[memory contracts](../tslc/src/tslc/catalog/memory.py), and
[conversion contracts](../tslc/src/tslc/catalog/conversion.py), the propagated
[dependency closure](../tslc/src/tslc/_pipeline_closure.py), the
[benchmarking design](../docs/variant-benchmarking.md), and the
[value-test planner](../tslc/src/tslc/value_tests/).

That combination could make TSL a **semantic control plane for data-parallel
software**: a system that can prove which implementations are equivalent,
generate new ones, learn when each one wins, and expose those choices to a
database optimizer. Ordinary SIMD libraries mostly offer a portable API.
General-purpose compilers mostly optimize one program after it has been
written. Autotuners usually treat implementations as opaque alternatives.
Query engines normally assume that the hardware library and its primitive
choices already exist. TSL could connect all four layers.

The strongest possible elevator pitch is:

- **One semantic primitive definition becomes a family of C++ and Rust
  implementations across fixed and scalable vector ISAs.**
- **Every admitted implementation carries explicit correctness and provenance
  evidence, rather than merely passing a few examples.**
- **Missing or slow implementations can be synthesized as compositions of
  existing primitives and ISA operations.**
- **A semantics-aware tuner learns robust policies with far fewer measurements
  than an exhaustive black-box search.**
- **A database planner jointly chooses predicate representation, primitive
  variant, and execution strategy across an entire query pipeline.**
- **The result is not just a portable SIMD library: it is a verified,
  self-expanding, workload-adaptive data-parallel substrate.**

No single bullet above is currently an established contribution in the
repository. The current compiler is a strong foundation for them. The research
would be in constructing and validating the new mechanisms.

## How the ideas were selected

A feature is treated as scientifically strong here only if it creates a
falsifiable claim about correctness, optimization, portability, hardware
design, or software evolution. “It supports more things” is not enough. A
credible feature should answer at least one question that matters outside this
repository:

1. Can a new method prove, synthesize, or select implementations better than
   existing methods?
2. Does the method reveal a general law or trade-off about SIMD, scalable
   vectors, query execution, or generative software?
3. Does it enable an experiment that could not reasonably be conducted with an
   ordinary hand-written abstraction library?
4. Could a negative experimental result falsify the central claim?

The related-work check was targeted rather than exhaustive. In particular,
[Alive2](https://web.ist.utl.pt/nuno.lopes/pubs.php?id=alive2-pldi21),
[Hydride](https://hydride.cs.illinois.edu/files/2024/05/Hydride.pdf),
[Minotaur](https://users.cs.utah.edu/~regehr/minotaur-oopsla24.pdf),
[egg](https://popl21.sigplan.org/details/POPL-2021-research-papers/23/egg-Fast-and-Extensible-Equality-Saturation),
[FFTW](https://www.fftw.org/fftw-paper-icassp.pdf),
[TVM](https://www.usenix.org/conference/osdi18/presentation/chen),
[HybridSIMD](https://conf.researchr.org/details/ase-2025/ase-2025-papers/186/HybridSIMD-A-Super-C-SIMD-Library-with-Integrated-Auto-tuning-Capabilities),
[TVL](https://www.vldb.org/cidrdb/papers/2020/p28-ungethuem-cidr20.pdf),
[VOILA](https://www.vldb.org/pvldb/vol14/p1067-gubner.pdf), and
[Excalibur](https://www.vldb.org/pvldb/vol16/p829-boncz.pdf) materially limit
what can honestly be claimed as new. Each idea below states its nearest
collision rather than treating a missing identical implementation as proof of
novelty.

## Ranked map

| Rank | Feature | Scientific ceiling | Relative effort | Best scientific role |
|---:|---|---|---|---|
| 1 | Proof-carrying primitive catalog | Very high | High | Foundational PL/systems contribution |
| 2 | Verified synthesis of missing and alternative variants | Very high | Very high | Compiler/architecture contribution |
| 3 | Global representation-and-variant optimizer for query pipelines | Very high | High | Strongest database-paper direction |
| 4 | Semantics-aware, transferable autotuning | High | Medium–high | Systems/database optimization |
| 5 | Vector-length-parametric verification | High | Medium–high | Scalable-vector/compiler research |
| 6 | Counterfactual ISA economics laboratory | Very high | Very high | Architecture/database co-design |
| 7 | Cross-language SIMD compiler observatory | High, conditional on findings | Medium | Compiler testing/empirical study |
| 8 | Fleet-aware library product-line synthesis | Medium–high | Medium–high | Systems and deployment optimization |
| 9 | Semantic-debt and change-amplification profiler | Medium | Low–medium | Empirical software/compiler study |

The rankings are not implementation order. Ideas 1 and 2 have the greatest
long-term scientific moat. Idea 3 is the most direct route to a database venue.
Ideas 7 and 9 are the most plausible early empirical wins.

---

## Idea 1: A proof-carrying primitive catalog

### Feature

Give a tractable subset of TSL primitives executable, language-neutral
semantics and generate a verification obligation for every emitted
specialization. The generated artifact would include a proof/evidence manifest
whose entries distinguish:

- proved equivalent;
- bounded translation-validated;
- compositionally proved from verified callees;
- differentially tested only;
- unverified because the source or target semantics are opaque.

Each entry should bind the result to the primitive contract, specialization,
implementation-body digest, backend, compiler/toolchain identity, target
features, and verifier version. A failed obligation should produce a concrete
counterexample wherever possible.

This would extend the current contracts, not mislabel them. For example,
`PrimitiveSemanticContract` currently identifies an operation and operand
roles, while `ArithmeticContract` records operations and selected guarantees.
Those are valuable semantic facts, but they are not yet a complete denotational
specification capable of proving that arbitrary generated code implements the
primitive.

### Why this is a good fit for TSL

TSL already has several properties that a verification project would otherwise
need to reconstruct:

- a catalog identity for each primitive and concrete specialization;
- explicit type, mask, conversion, memory, arithmetic, and safety facts;
- a typed `call` region and an exact dependency graph for composed
  implementations;
- a generic implementation that can often serve as an executable reference;
- C++ and Rust projections of the same lowered semantic selection;
- generated golden and generic-differential tests.

The first research slice should deliberately exclude difficult cases. Pure
integer lane-wise arithmetic, comparisons, bitwise operations, shifts, splats,
and selects are much more realistic than floating-point reductions, arbitrary
memory, faulting behavior, or target-specific status outputs.

The compiler must not become a C++ or Rust parser. Typed semantics belong in
the catalog and TSIL regions. A separate verification adapter can compile a
generated function to LLVM IR and invoke an external verifier. Raw target text
that cannot be related to a known intrinsic or verified IR remains honestly
unverified.

### Scientific hypothesis

The central claim could be:

> A catalog-level, compositional semantic model can automatically establish
> cross-language and cross-ISA equivalence for most pure SIMD-library
> specializations, while localizing unverifiable behavior and producing useful
> counterexamples at product-line scale.

That is stronger than “the tests pass.” It is falsified if verification covers
only trivial wrappers, cannot scale across the catalog, or finds no advantage
over checking each generated function independently.

### What it enables

- Safe autotuning: a policy may select only variants in the same proved
  equivalence class.
- Safe synthesis: generated candidates can be rejected before benchmarking.
- Cross-language conformance: C++ and Rust are checked against one contract,
  not merely against each other.
- Trustworthy fallbacks: a composed or generic implementation can carry
  evidence through its dependency closure.
- Research on semantic coverage: which SIMD operations are easy or hard to
  specify and verify, and why?
- A reusable proof artifact for downstream database or safety-conscious users.

### Minimum credible research version

1. Define executable semantics for roughly one coherent family, such as
   integer bitwise/arithmetic/comparison operations and masks.
2. Cover at least two substantially different ISA families and both C++ and
   Rust.
3. Verify native, generic, and composed implementations.
4. Measure proof coverage, verification time, failure causes, and compositional
   reuse.
5. Seed realistic mutations and report detection rate; ideally discover real
   defects or contract ambiguities.
6. Compare whole-catalog compositional verification with isolated
   per-function translation validation.

### Novelty collision and risk

[Alive2](https://web.ist.utl.pt/nuno.lopes/pubs.php?id=alive2-pldi21) already
performs bounded translation validation for LLVM IR and found dozens of LLVM
bugs. [Minotaur](https://users.cs.utah.edu/~regehr/minotaur-oopsla24.pdf) adds
formal semantics for many x86 SIMD intrinsics and verifies synthesized
optimizations. [Hydride](https://hydride.cs.illinois.edu/files/2024/05/Hydride.pdf)
generates formal instruction semantics and uses synthesis across several
architectures.

Consequently, “we call Alive2 on generated code” is not a contribution. The
potentially new part is product-line-scale, compositional verification of a
stable, multi-language SIMD library catalog, including typed provenance,
fallback closure, and honest coverage boundaries. This remains a high-risk
claim until a deeper formal-methods literature review and a working prototype
show that the catalog structure provides a measurable advantage.

### Realism

High effort, but technically coherent. This is the best foundational feature
because it makes several later ideas safe and scientifically sharper. It should
start with a deliberately small semantic core rather than trying to formalize
the entire corpus.

---

## Idea 2: Verified synthesis of missing and alternative variants

### Feature

Turn TSL from a generator of authored variants into a system that can propose
new implementations. Given a primitive contract, target capabilities, and a
library of already verified primitive operations, search for:

- a composed fallback when an ISA lacks a direct instruction;
- a cheaper composition than the authored default;
- an implementation for a newly added ISA profile;
- a representation conversion sequence;
- an alternative sequence with a different latency, throughput, code-size, or
  feature requirement.

A realistic design would use a small typed expression IR for the semantic
subset, equality saturation or enumerative/CEGIS search to construct
candidates, a verifier to establish equivalence, and measured or modeled cost
to rank them. The result should be emitted as a proposed TSL implementation
with provenance, not silently inserted as opaque target text.

The search engine is likely best kept as a one-way downstream research tool:
it consumes typed compiler facts and emits candidate source data for review.
`tslc` remains the deterministic compiler and validator.

### Why this is a good fit for TSL

The existing compiler knows the concrete primitive signature, type, extension,
required features, dependency graph, native/composed/fallback state, and
backend translation. This gives synthesis a smaller and more meaningful search
space than arbitrary C++ or Rust. A verified `call` composition also has a
stable meaning across output languages.

This feature would turn “fast-paced integration of new paradigms” from a
maintainability assertion into an algorithmic capability. Instead of requiring
an author to hand-map every primitive immediately, a new target could begin
with machine-readable capabilities and a small native seed. The synthesizer
would propose the remainder and identify irreducible semantic gaps.

### Scientific hypothesis

> TSL's catalog semantics, type constraints, and dependency closure reduce the
> synthesis search enough to generate correct, competitive SIMD-library
> implementations for new targets with substantially less target-specific
> authoring than hand-written or compiler-IR-only approaches.

The claim fails if the system merely rediscovers obvious one-instruction
wrappers, requires a hand-written sketch for every result, or produces code
that optimizing compilers already generate from the generic implementation.

### What it enables

- A self-expanding primitive corpus.
- Rapid bootstrap of a new ISA, scalable-vector family, or compiler-vector
  overlay.
- Multiple Pareto candidates per primitive rather than one hand-selected body.
- Systematic discovery of missing abstractions: repeated synthesis failures
  reveal where the semantic vocabulary is inadequate.
- A defensible answer to “why a generator rather than a hand-written
  portability layer?”
- Later use of stochastic or learned candidate proposal, including LLMs,
  without trusting unverified generated code.

### Minimum credible research version

1. Depend on the semantic/proof core from Idea 1.
2. Restrict the first grammar to pure integer and mask operations.
3. Hold out a meaningful set of existing implementations and ask the system to
   reconstruct them without seeing their bodies.
4. Add one genuinely new or deliberately hidden target slice.
5. Compare with compiler lowering from generic scalar/vector code, hand-written
   TSL bodies, e-graph extraction, and an established synthesis approach.
6. Measure synthesis success, search time, proof time, generated instruction
   cost, runtime, and human authoring effort.
7. Evaluate whether synthesized compositions remain useful in both C++ and
   Rust after normal optimization.

### Novelty collision and risk

This is the idea with the most dangerous related work.
[Hydride](https://hydride.cs.illinois.edu/files/2024/05/Hydride.pdf) generates
a target-independent IR and formal semantics from vendor ISA pseudocode and
synthesizes performant code across x86, Arm, and Hexagon.
[Minotaur](https://users.cs.utah.edu/~regehr/minotaur-oopsla24.pdf) is a
verified SIMD-oriented superoptimizer.
[From Relational Verification to SIMD Loop Synthesis](https://www.microsoft.com/en-us/research/publication/relational-verification-simd-loop-synthesis/)
already combined proof and synthesis for vectorization, while
[egg](https://popl21.sigplan.org/details/POPL-2021-research-papers/23/egg-Fast-and-Extensible-Equality-Saturation)
provides established equality-saturation machinery. Work has also synthesized
[instruction-selection rules from RTL](http://theory.stanford.edu/~barrett/pubs/DDM%2B22-abstract.html).

The differentiator cannot be “we synthesize SIMD.” It must be the stable
library-product-line problem: synthesizing reusable, compositional variants
with cross-language projection, feature/fallback provenance, generated tests,
and policies. Whether that is fundamental enough for a top paper is uncertain.
A prototype must demonstrate a result that Hydride or Minotaur cannot obtain
without substantial redesign.

### Realism

Very high effort and unsuitable as the first change. It becomes realistic after
a small executable semantic core and proof adapter exist. It is a potential
killer feature, not a low-effort win.

---

## Idea 3: A global representation-and-variant optimizer for query pipelines

### Feature

Build a downstream database-oriented optimizer that uses TSL facts to jointly
choose, across an entire operator pipeline:

- native predicate masks, lane masks, integral bitmasks, or selection vectors;
- masked execution, dense execution, or compress-then-process;
- fixed-width, scalable, or generic profiles;
- primitive implementation variants;
- when to materialize or convert a representation;
- static versus runtime decisions based on selectivity or data density.

Model a query micro-pipeline as a graph. Each edge has a physical
representation; each operator has TSL-backed implementations and capability
requirements; representation conversions have costs; the chosen sequence must
be semantically valid. Dynamic programming, a Cascades-style search, or an
e-graph can then optimize the complete path rather than choosing the fastest
primitive in isolation.

This should be a downstream database compiler or engine integration. It may
consume compiler-owned semantic, representation, capability, and measured-cost
facts, but it should not put query-optimizer policy into `tslc`.

### Why this is a good fit for TSL

TSL already distinguishes masks and integral masks, models target-specific mask
policies, represents conversions, exposes primitive semantics and dependency
closure, and can benchmark alternative implementations. That is unusually
close to the information a physical query optimizer needs.

Existing query engines often make representation and execution choices in a
different layer from the ISA abstraction. Existing SIMD libraries offer
operations but do not expose a typed explanation of native versus composed
support. TSL can make representation feasibility and conversion consequences
explicit across x86, Arm, fixed-width, and scalable-vector targets.

### Scientific hypothesis

> Jointly optimizing predicate representation and SIMD implementation across a
> query pipeline produces robust performance improvements over operator-local
> choices, fixed representation policies, and black-box primitive tuning,
> especially when selectivity and target mask capabilities vary.

This is falsifiable: the global planner may add complexity but choose no better
than simple density thresholds or an existing query compiler.

### What it enables

- A direct database-systems research story rather than a library-only paper.
- Hardware-aware decisions without hard-coding x86 or Arm rules in the query
  engine.
- Principled use of SVE/RVV predicates versus AVX integral masks and selection
  vectors.
- Cross-operator optimization of filtering, projection, aggregation,
  compression, and possibly joins.
- Runtime switching points derived from calibrated costs rather than fixed
  folklore.
- A reusable bridge from a query IR to generated C++ or Rust SIMD libraries.

### Minimum credible research version

1. Start with selection/projection/aggregation pipelines, not a complete DBMS.
2. Model at least three representations: dense vectors, masks/bitmasks, and
   selection vectors.
3. Include conversion costs and selectivity-dependent costs.
4. Integrate into one real engine or research query compiler.
5. Evaluate on several microarchitectures from at least two ISA families and
   over wide selectivity distributions.
6. Compare against:
   - a fixed representation;
   - greedy per-operator selection;
   - exhaustive oracle plans for small pipelines;
   - the engine's existing strategy;
   - relevant vectorized/data-centric systems.
7. Use end-to-end workloads in addition to primitive microbenchmarks, and
   report planning, compilation, code-size, and runtime overheads.
8. Ablate representation planning, primitive-variant planning, runtime
   adaptivity, and the TSL capability model separately.

### Novelty collision and risk

[TVL](https://www.vldb.org/cidrdb/papers/2020/p28-ungethuem-cidr20.pdf)
already provides hardware-oblivious, database-specific vector primitives.
[VOILA](https://www.vldb.org/pvldb/vol14/p1067-gubner.pdf) explores a query
execution design space, and
[Excalibur](https://www.vldb.org/pvldb/vol16/p829-boncz.pdf) dynamically chooses
fine-grained generated execution variants, including whether to ignore a
selection vector. Database studies have long compared bitmasks and selection
vectors. Therefore, neither portable query primitives nor adaptive variant
choice is new alone.

The plausible novelty is **global typed representation-flow planning joined
with the live SIMD capability/dependency graph and measured variant costs**.
The most damaging review would show that Excalibur or a standard physical
property optimizer can express the same choices with an ordinary cost model.
The project must demonstrate a new search space, a better planning method, or a
general cross-architecture insight—not merely replace hand-written intrinsics
with TSL calls.

### Realism

High effort, but this is the most credible top-tier database direction. A
filter-pipeline prototype is realistic. A competitive end-to-end paper requires
a real database integration and substantial evaluation.

---

## Idea 4: Semantics-aware, transferable autotuning

### Feature

Upgrade variant selection from “benchmark all admitted candidates and retain a
local policy” to a tuner that exploits compiler semantics and transfers
evidence across the product line.

Candidate features could include:

- operation kind and type;
- native/composed/fallback state;
- dependency DAG and conversion count;
- required target features;
- fixed or scalable lane structure;
- mask representation;
- compiler/backend/language identity;
- microarchitecture and scenario facts;
- uncertainty and measurement noise.

The tuner should prune impossible and provably dominated candidates before
measurement, use sparse measurements to predict related slots, retain
confidence intervals, and fall back safely when evidence is insufficient. A
strong version would learn from C++ to Rust, from one type width to another, or
from known CPUs to a new CPU while explicitly measuring transfer error.

The current benchmark planner and policy validation remain the trusted
compiler boundary. Search, statistics, and experimental policy construction
can live in a downstream tuner that consumes typed reports and produces a
policy the compiler validates.

### Why this is a good fit for TSL

The repository already has named variants, typed scenarios, correctness gates,
body hashes, machine profiles, build-context identity, and conservative policy
handling. Its [benchmarking documentation](../docs/variant-benchmarking.md)
also states current limitations, including native-only autotuning and explicit
backend/profile admission. This is far beyond starting from opaque command-line
parameters.

The scientific opportunity is not the existence of autotuning. It is whether
semantic and dependency structure can make tuning cheaper, safer, and more
transferable.

### Scientific hypothesis

> A tuner informed by semantic equivalence, implementation provenance, and
> dependency structure reaches low regret with substantially fewer
> measurements than black-box tuning and produces policies that transfer
> predictably across languages, compilers, types, and related
> microarchitectures.

### What it enables

- Practical calibration across a large primitive × type × ISA × compiler ×
  language matrix.
- Robust policies rather than “winner of one noisy run.”
- Detection of systematic compiler or backend effects.
- A quantitative account of where one source definition really does or does
  not yield portable performance.
- Cost inputs for the database planner in Idea 3.
- Evidence-driven choice among synthesized candidates from Idea 2.

### Minimum credible research version

1. Collect an exhaustive ground-truth matrix for a bounded but diverse subset.
2. Compare random search, generic Bayesian/evolutionary tuning, authored
   defaults, and the semantics-aware method.
3. Report sample efficiency, simple and cumulative regret, confidence
   calibration, tuning wall time, and policy stability.
4. Use multiple compilers, several CPUs from at least two ISA families, and
   both output languages.
5. Hold out complete CPUs, compiler versions, types, or a language to test
   transfer rather than interpolation.
6. Include negative transfer and fail-safe behavior.
7. Measure end-to-end impact in a real workload; primitive wins alone do not
   establish significance.

### Novelty collision and risk

Automatic tuning is mature. [FFTW](https://www.fftw.org/fftw-paper-icassp.pdf)
combined generated codelets with runtime planning decades ago.
[TVM](https://www.usenix.org/conference/osdi18/presentation/chen) uses
learning-based cost models for hardware-specific program optimization.
[HybridSIMD](https://conf.researchr.org/details/ase-2025/ase-2025-papers/186/HybridSIMD-A-Super-C-SIMD-Library-with-Integrated-Auto-tuning-Capabilities)
is already a unified, autotunable SIMD library.

Thus “TSL now autotunes” is scientifically weak. The contribution must be a
new structured search/transfer method and convincing evidence that TSL's
semantic facts reduce calibration cost or improve robustness. If the semantic
features do not beat a well-tuned black-box baseline, this should remain an
engineering feature rather than a paper claim.

### Realism

Medium–high effort. This is one of the best extensions of the existing system
because the benchmark and policy infrastructure already provides a disciplined
starting point. It is also separable from formal verification, although proved
equivalence would make it much safer.

---

## Idea 5: Vector-length-parametric verification

### Feature

Add a verification mode that reasons about scalable vectors for **all legal
vector lengths**, rather than testing a few fixed SVE/RVV configurations.

The system would classify semantic structures and discharge different proof
obligations:

- lane-local operations: prove one arbitrary active lane and independence from
  other lanes;
- mask operations: prove active/inactive and tail behavior;
- reductions: prove a monoid or ordered fold property plus an induction over
  active lanes;
- conversions: prove the relation between element width, lane count, and
  register grouping;
- permutations: prove a symbolic lane-index map;
- memory operations: prove bounds and inactive-lane non-access under a defined
  memory model.

A failure should report a concrete vector length, active-lane count, mask, and
input values. The manifest should distinguish a universal proof from finite
testing.

### Why this is a good fit for TSL

The compiler already carries a typed
[`LaneCount`](../tslc/src/tslc/lane_count.py), supports scalable and sized
profiles, models target-specific predicate representations, records whether an
operation is cross-lane, and plans scalable value-test harness facts. The
architecture documentation also makes an honest distinction: neutral lowering
can retain symbolic lane counts while some backends require them to be
monomorphized or reject them.

That gives TSL a concrete route to study a problem that fixed-width libraries
largely avoid: whether one semantic implementation is correct independently of
the runtime vector length.

### Scientific hypothesis

> A small set of structural proof rules can establish vector-length-independent
> correctness for a large fraction of scalable SIMD-library primitives, while
> isolating the cross-lane, memory, and representation operations that require
> richer reasoning.

### What it enables

- Stronger SVE and RVV support than “we ran at 128 and 256 bits.”
- Detection of hidden fixed-width assumptions in composed implementations.
- A principled relationship between fixed, sized, and fully scalable profiles.
- Reusable correctness conditions for vector-length-agnostic libraries.
- A scientific taxonomy of which primitives scale semantically and which only
  scale operationally.
- Safer reuse of one implementation across future hardware vector lengths.

### Minimum credible research version

1. Begin with lane-local integer, comparison, and mask operations.
2. Support both SVE-style predicates and an RVV-style active vector length.
3. Prove a universal result and validate it against generated executions at
   many concrete lengths.
4. Inject fixed-width and tail-policy defects and show minimal
   counterexamples.
5. Extend to at least one hard class, such as reductions, conversions, or
   permutations.
6. Compare proof coverage and effort with bounded unrolling over selected
   vector lengths.

### Novelty collision and risk

Arm's peer-reviewed
[SVE paper](https://ieeexplore.ieee.org/document/7924233) establishes the
vector-length-agnostic programming model. LLVM has
[scalable vector types](https://llvm.org/docs/LangRef.html) and specific
[RVV lowering support](https://llvm.org/docs/RISCV/RISCVVectorExtension.html).
Formal ISA and hardware verification for RISC-V also exists. Hydride exploits
lane structure to accelerate synthesis and verification.

The targeted search did not identify an exact catalog-scale counterpart for
proving multi-language SIMD-library primitives correct for all scalable vector
lengths, but that is not proof of novelty. A dedicated formal-methods and
scalable-vector literature review is mandatory. The project must also avoid a
trivial result in which every interesting cross-lane or memory primitive is
declared unsupported.

### Realism

Medium–high effort and narrower than general proof-carrying semantics. It could
be an excellent thesis-sized slice or a distinguishing part of Idea 1. It is
especially attractive if scalable-vector support is strategically important to
the project.

---

## Idea 6: A counterfactual ISA economics laboratory

### Feature

Let researchers add a **hypothetical native operation**—its semantics,
supported types, feature gate, estimated latency/throughput, and optional
area/energy cost—without pretending that hardware exists. Recompute:

- which generic or composed implementations become native;
- which dependency subgraphs collapse;
- which query/operator pipelines change;
- how much estimated critical-path or instruction cost disappears;
- which workloads and languages benefit;
- whether two proposed instructions are redundant or complementary.

The system could also run the inverse experiment: hide an existing instruction
or ISA feature and measure the semantic and performance debt that reappears.
Candidate instruction sets could then be selected under an area, encoding, or
complexity budget.

The counterfactual model and hardware-cost policy should live in a downstream
co-design tool. `tslc` supplies real semantic closure and generated emulation
paths; it should not invent microarchitectural facts.

### Why this is a good fit for TSL

Instruction counts alone do not reveal an instruction's value. One instruction
may replace a large, frequently reused primitive dependency subgraph or unlock
a better predicate representation. TSL can observe that effect at the semantic
library level across multiple output languages and workloads.

The existing native/composed/fallback/unknown propagation is the key asset.
It can answer a more interesting question than “how often did an opcode occur?”:
**what portable software capability becomes cheaper or newly expressible if
the ISA acquires this semantic operation?**

### Scientific hypothesis

> Workload frequency combined with semantic dependency closure predicts the
> marginal value of proposed vector instructions more accurately and more
> portably than static opcode frequency or isolated kernel speedups.

### What it enables

- Database-driven proposals for future RISC-V, Arm, or accelerator operations.
- Quantitative prioritization of compress/expand, gather/scatter, conflict,
  mask-conversion, permutation, and reduction capabilities.
- Early software emulation and API design before silicon exists.
- Multi-language evidence that an instruction solves a semantic need rather
  than one compiler's pattern-matching accident.
- Study of instruction complementarity and diminishing returns.
- A bridge between database workloads, compiler libraries, and architecture
  design.

### Minimum credible research version

1. Validate the method with **counterfactual removal**: hide existing
   instructions/features and compare predicted losses with measured losses
   under compiler flags or hardware profiles.
2. Trace primitive demand from at least one real database engine and one
   non-database workload.
3. Compare semantic-closure ranking with opcode-frequency, static instruction
   count, and microbenchmark-only ranking.
4. Model interactions among instruction candidates, not just independent
   benefits.
5. Validate at least one proposed operation in an emulator, gem5-like model,
   FPGA, or custom RISC-V extension.
6. Report prediction error, workload sensitivity, area/energy assumptions, and
   compiler dependence.

### Novelty collision and risk

Automatic instruction-set extension and compiler-retargeting research is
extensive. Hydride is again a major comparator. Researchers have also
synthesized instruction-selection rules from formal hardware descriptions, and
DSL-based RISC-V extension flows already target compiler, simulator, and
hardware integration.

The new claim would not be “TSL can describe another instruction.” It would be
semantic, multi-workload **marginal-value analysis** using library dependency
closure and downstream query plans. The largest risk is inaccurate performance
and hardware-cost modeling. Without validation against real or simulated
hardware, the result is only an attractive dashboard.

### Realism

Very high effort for a defensible architecture paper. A coverage-only
counterfactual ablation is easy and useful, but performance/area claims require
a major collaboration or hardware model.

---

## Idea 7: A cross-language SIMD compiler observatory

### Feature

Turn the current value-test machinery into a semantics-directed generator of
compiler and intrinsic tests across:

- C++ and Rust;
- multiple compilers and versions;
- optimization levels and target-feature combinations;
- native hardware and emulators;
- fixed and scalable vectors;
- generic, native, composed, and synthesized implementations.

Generate boundary and metamorphic cases from contracts rather than relying
only on manually authored examples. Examples include:

- `x xor x = 0`;
- select with all-true/all-false predicates;
- conversion round trips when the contract permits them;
- masked operations preserving inactive lanes;
- shift-count and integer-overflow boundaries;
- equivalent composed and native paths;
- the same semantic operation projected through C++ and Rust.

Automatically minimize any disagreement to a primitive, type, profile, inputs,
compiler flags, and small generated function. Retain a longitudinal,
reproducible corpus of failures and fixes.

### Why this is a good fit for TSL

The repository already produces executable golden and generic-differential
tests, preserves exact bit patterns when requested, represents many input
domains, and can execute under SDE or QEMU. It also has a single source catalog
that can generate semantically related programs in two languages. Generic
compiler fuzzers do not start with this domain-specific equivalence relation.

The feature turns “single source, multiple languages” into a scientific
instrument: the two generated ecosystems become independent observations of
the same semantic contract.

### Scientific hypothesis

> Semantics-directed generation over a cross-language SIMD product line finds
> classes of compiler, intrinsic, and library defects that general random
> program generators and hand-authored SIMD tests miss.

### What it enables

- Discovery of real compiler and intrinsic bugs.
- Empirical comparison of C++ and Rust SIMD code generation and semantic
  hazards.
- A public SIMD regression corpus.
- Evidence about compiler-vector versus platform-intrinsic reliability.
- Automatic validation of new backends and ISA extensions.
- A lower-risk path to publication than full formal verification if the system
  finds important accepted bugs.

### Minimum credible research version

1. Define a precise, undefined-behavior-free generation model.
2. Generate both self-checking and differential/metamorphic tests.
3. Cover several compilers, versions, optimization levels, and two ISA
   families.
4. Minimize and independently validate failures.
5. Compare bug yield and semantic coverage with existing compiler fuzzers or
   randomly generated intrinsic tests.
6. Report unique root causes, accepted upstream bugs, false-positive rate, and
   time-to-bug.
7. Separate compiler bugs, incorrect source data, incorrect generic oracles,
   emulator issues, and underspecified semantics.

### Novelty collision and risk

[Csmith](https://users.cs.utah.edu/~regehr/papers/pldi11-preprint.pdf)
demonstrated the scientific value of undefined-behavior-free random compiler
testing and reported hundreds of bugs. Alive2 and other differential,
metamorphic, and target-specific compiler testers are strong baselines.
Generating lots of SIMD tests is not novel by itself.

The differentiator must be the semantic fault model: cross-language projection,
native/composed/generic equivalence, mask and scalable-vector behavior, and
product-line provenance. Publication potential is strongly outcome-dependent.
If the tool finds no important bugs and yields no new empirical insight, it is
excellent QA rather than a research contribution.

### Realism

Medium effort relative to the other ideas because much of the planning and
execution foundation already exists. This is one of the best early bets.

---

## Idea 8: Fleet-aware library product-line synthesis

### Feature

Given:

- a workload manifest or trace of required primitives, types, and scenarios;
- a target fleet distribution;
- performance, binary-size, compile-time, tuning-time, and portability
  constraints;
- native, composed, and fallback implementations plus their dependencies;

synthesize a **portfolio of generated library products**. The optimizer may
choose which profiles and variants to ship, which operations may use compact
fallbacks, which machine classes share one artifact, and where a specialized
artifact is worth its deployment cost.

This is more than dead-code elimination. It can choose a slower composition to
save code size, preserve a generic recovery path, share one implementation
across related profiles, or include a specialized variant only when its fleet
benefit justifies compilation and calibration cost.

### Why this is a good fit for TSL

The compiler already computes exact selected and transitive dependencies,
machine profiles, backend artifacts, variant identities, and coverage gaps.
Those facts define a product-line optimization problem naturally. A
hand-written library or linker sees code reachability, but not semantic
substitutability, fallback provenance, or expected policy benefit.

### Scientific hypothesis

> Optimizing a SIMD library as a semantic product line yields better
> performance/size/compile-time/deployment Pareto frontiers than generate-all,
> fastest-only, per-target, and linker-dead-stripping strategies.

### What it enables

- Small generated libraries for embedded, serverless, plugin, or enclave
  deployments.
- Rational selection of fat-binary profiles for heterogeneous fleets.
- Workload-specific database execution libraries.
- Explicit trade-offs between portability insurance and specialization.
- Reproducible artifacts whose included capabilities follow from a declared
  workload and target model.
- Study of how much of a broad SIMD abstraction a real workload actually uses.

### Minimum credible research version

1. Define an auditable workload and fleet manifest.
2. Formulate the selection problem as ILP, dynamic programming, or another
   reproducible optimization method.
3. Compare against generate-all, one-build-per-target, fastest-per-slot,
   generic-only, and ordinary dead stripping.
4. Measure runtime, binary size, compile time, artifact count, tuning cost, and
   fallback coverage.
5. Use at least one real database or analytics workload and one constrained
   deployment scenario.
6. Perform sensitivity analysis over fleet mix and workload drift.

### Novelty collision and risk

Software product-line optimization, multi-versioning, library specialization,
debloating, and fleet-aware compilation are established areas. If the result
is merely “generate only called primitives,” it is non-novel.

The defensible distinction is optimization over **semantically substitutable
implementations and exact fallback/dependency closure**, with measured
performance and portability constraints. Its scientific ceiling is lower than
Ideas 1–6 unless the optimizer reveals a strong general result or enables a
compelling database deployment study.

### Realism

Medium–high effort. The closure foundation makes a prototype plausible, but
obtaining realistic workload/fleet data and measuring deployment costs is the
hard part.

---

## Idea 9: A semantic-debt and change-amplification profiler

### Feature

Make TSL's central engineering claim measurable. Add a compiler-owned,
read-only research projection that reports:

- how much primitive behavior is represented by typed semantics versus opaque
  raw target text;
- backend-specific duplication;
- unsupported source forms and their reasons;
- native/composed/fallback coverage;
- dependency and test coverage;
- which semantic facts each backend consumes;
- the source modules and compiler stages touched by a new primitive, ISA,
  backend, language, mask model, or scalable-vector feature;
- marginal change amplification as the product line grows.

Combine this with controlled case studies or repository-history analysis. A
particularly strong pressure test would add one **unlike** target model rather
than another C++-shaped fixed-width SIMD backend. The experiment must respect
the architecture: an incompatible SIMT/tensor paradigm may need to remain a
downstream consumer instead of being forced into the compiler contract.

### Why this is a good fit for TSL

The current project explicitly values additive change, typed semantics,
coverage rather than fantasy completeness, and one-way downstream tools. Those
are hypotheses about maintainability. Today they are primarily design
principles. A profiler can turn them into longitudinal evidence.

This feature directly addresses the “single code base, multiple languages” and
“fast-paced integration of new paradigms” arguments. Those claims become
scientific only when “single source” and “fast” are operationalized and
compared.

### Scientific hypothesis

> Centralizing semantic decisions in typed compiler facts causes sublinear
> marginal change amplification across languages and target families, while
> opaque target-text islands predict integration defects and duplicated work.

### What it enables

- An empirical answer to whether adding Rust actually reused semantics or
  duplicated them elsewhere.
- Identification of the next semantic region worth lifting.
- Quantitative planning for new ISA or backend work.
- Comparison with hand-written SIMD libraries or simpler template generators.
- A reusable benchmark for generative software maintainability.
- Honest detection of cases where the architecture does **not** generalize.

### Minimum credible research version

1. Define metrics before examining desired outcomes.
2. Reconstruct several historical feature slices from version control.
3. Record semantic changes separately from mechanical generated or rendered
   changes.
4. Compare primitive, ISA, and backend additions.
5. Conduct at least one prospective pressure-test extension.
6. Include defect density, review effort, test changes, and time-to-verified
   coverage where reliable data exists; lines changed alone are inadequate.
7. Compare against at least one external system or controlled alternative
   architecture.

### Novelty collision and risk

Change-impact analysis and software-evolution metrics are established software
engineering topics. A dashboard of line counts is not publishable. Historical
data may also be confounded by author experience, simultaneous refactoring, and
changing project maturity.

The research value would come from a domain-specific formalization of semantic
versus projection work, a controlled pressure test, and results that generalize
to other generative systems. This is unlikely to carry a top database paper by
itself, but it can provide crucial evidence for a compiler, artifact, or
software-engineering paper.

### Realism

Low–medium effort for an initial report and therefore a genuine low-effort
research win. A rigorous comparative study is still substantial.

---

## The strongest combined research programs

These features should not all be implemented at once. They form three coherent
programs with different audiences.

### Program A: Verified adaptive TSL

Combine Ideas 1, 2, and 4:

1. **Specify** a semantic core.
2. **Prove** authored implementations.
3. **Synthesize** missing or alternative implementations.
4. **Measure and select** among proved equivalents.

This is the deepest compiler/systems story:

> TSL is a self-expanding, self-tuning SIMD library compiler in which every
> selected implementation is tied to a common semantic contract.

It is also the riskiest program because Hydride, Minotaur, Alive2, and mature
autotuning work make each component individually non-novel. The contribution
must arise from their product-line-scale integration and from results that the
component systems cannot already produce.

### Program B: TSL-Q, a physical SIMD optimizer for databases

Combine Ideas 3 and 4, using Idea 1 for safety where feasible:

1. derive candidate representations and variants from TSL capabilities;
2. calibrate a structured cost model;
3. optimize an entire query micro-pipeline;
4. generate or call the selected C++/Rust implementation;
5. adapt at runtime when density/selectivity changes.

This is the strongest database elevator pitch:

> Current database optimizers choose relational plans while treating SIMD
> representation and instruction-level implementation as fixed library facts.
> TSL-Q makes masks, selection vectors, conversions, fixed/scalable profiles,
> and native/composed implementations physical properties in one costed plan
> space.

The make-or-break requirement is an end-to-end database integration showing
plan choices and performance effects that existing vectorized or adaptive
engines do not already capture.

### Program C: TSL as an ISA co-design instrument

Combine Ideas 5, 6, and selected parts of 7:

1. give scalable-vector behavior a precise contract;
2. emulate proposed operations with verified fallbacks;
3. estimate how they alter workload closure and query plans;
4. validate predictions through feature removal, simulation, or prototype
   hardware;
5. use the test observatory to validate toolchains and implementations.

This can teach hardware and database communities which vector capabilities have
the greatest cross-workload semantic value. It requires architecture expertise
and access to credible cost models.

## Low-effort wins

“Low effort” is relative to the major projects above. None of these is a
top-tier paper on its own, but each can cheaply test whether a larger direction
has evidence behind it.

### 1. Semantic-readiness inventory

Add a read-only report that classifies every primitive/specialization by:

- available typed semantic facts;
- executable reference availability;
- pure versus memory/cross-lane/status behavior;
- typed-call composition versus opaque target text;
- current differential-test and benchmark coverage.

This reveals the realistic proof/synthesis frontier before committing to a
solver. It also produces an honest denominator for later “verified coverage”
claims.

### 2. Proof manifest without proofs

Define the evidence schema and stable semantic/body identities first. Populate
it with current states such as `golden-tested`, `generic-differential`,
`build-only`, and `unsupported`. This is useful infrastructure immediately and
tests whether evidence can remain deterministic across both backends.

It must not call testing “proof.”

### 3. Metamorphic tests for one semantic family

Generate algebraic and mask properties for the existing integer bitwise core
and run them through the current value-test pipeline in future experimental
work. This probes whether the contracts contain enough information for
automatic test generation and may find defects early.

### 4. Offline tuner replay

For one bounded candidate matrix, obtain exhaustive measurements and replay
different sampling strategies offline. Compare a black-box strategy with one
using native/composed/fallback state and dependency features. This can falsify
the semantics-aware tuning idea before building an online system.

### 5. Counterfactual capability ablation

Using the existing closure, hide one native implementation or feature in an
analysis-only model and report which primitives become composed, generic, or
unavailable. This does not establish performance value, but it tests whether
semantic closure produces useful instruction-value signals.

### 6. Filter-chain representation prototype

Implement a small external planner for a chain of predicates with only dense,
mask, and selection-vector states. Use synthetic costs first, then measured
costs. If global choices never differ materially from a simple local threshold,
stop before attempting a full database integration.

### 7. Historical change-amplification case study

Mine the already-existing addition of the Rust backend, scalable-vector
support, or a target family. Separate semantic source changes from backend
projection and test changes. The result will show whether the “single code
base” claim is measurable and where the current history is too confounded.

## Ideas that sound impressive but are not enough

The following may be valuable engineering tasks, but should not be presented as
scientific killer features without a stronger mechanism and evaluation:

- **Add a third language.** This proves extensibility only if change
  amplification, semantic parity, and generated quality are measured against a
  credible alternative.
- **Add more ISAs or primitives.** Coverage and artifact value improve, but the
  scientific idea does not.
- **Import vendor intrinsic descriptions.** Automated import is useful, but
  Hydride and ISA-description/compiler-generation work make a simple importer
  an incremental contribution.
- **Benchmark every variant and select the fastest.** FFTW, TVM, OpenTuner-like
  work, and HybridSIMD make black-box autotuning established practice.
- **Use machine learning or an LLM to generate intrinsic code.** Candidate
  generation is not a contribution unless the search formulation, correctness
  gate, and empirical result are new. An LLM can be an optional proposal
  engine behind a verifier.
- **Generate more tests.** The scientific question is whether a new semantic
  generation method finds important bugs or establishes stronger coverage.
- **Build a coverage dashboard.** A visualization is an artifact unless it
  supports a validated analysis method.
- **Claim performance portability because the code compiles everywhere.**
  Portability of behavior, performance, and maintenance are different claims
  and require different evidence.

## Recommended sequence

### Step 1: establish semantic observability

Build the semantic-readiness and evidence inventories from the low-effort
list. Select a small integer/mask core with high typed coverage and little
memory or floating-point ambiguity.

**Kill gate:** if most implementations remain opaque raw target text or the
same behavior cannot be specified cleanly across current profiles, do not start
general verification or synthesis. Improve the semantic model first.

### Step 2: run two small, competing pilots

- **Compiler pilot:** translation-validate the selected semantic core for C++
  and Rust, including one composed implementation.
- **Database pilot:** optimize representation flow for a short filter pipeline
  using current mask/conversion facts and measured candidate costs.

These answer different questions. The first tests whether TSL can become a
verified semantic catalog. The second tests whether its facts improve a real
database decision.

### Step 3: choose the research identity based on evidence

- If verification coverage is high and exposes real defects or compositional
  savings, pursue Program A and add synthesis.
- If global representation choices materially affect end-to-end query
  performance, pursue Program B and integrate with a real engine.
- If capability ablations predict meaningful workload effects and hardware
  collaboration is available, pursue Program C.
- If none of these pilots produces a strong delta over simpler alternatives,
  retain TSL as a high-quality engineering artifact and avoid forcing a
  scientific story.

### Step 4: add the expensive feature only after its prerequisite claim holds

- Do not build synthesis before equivalence checking is credible.
- Do not build a learned tuner before an exhaustive bounded matrix shows
  transferable structure.
- Do not build a full query optimizer before a small representation planner
  beats local rules.
- Do not make ISA value claims before counterfactual removal predicts real
  measurements.

## Final recommendation

The single most important scientific feature is the **proof-carrying primitive
catalog**, because it converts TSL's declarative source from a code-generation
input into a trustworthy semantic asset and enables safe synthesis and tuning.
The single most promising top-tier database feature is the **global
representation-and-variant optimizer**, because it uses TSL to expose a new
physical planning space rather than asking reviewers to care about a library
for its own sake.

If only one ambitious research program can be attempted, choose based on the
target community:

- for database systems, pursue TSL-Q: Idea 3 plus the structured tuner in Idea
  4;
- for compilers/systems, pursue proof-carrying TSL: Idea 1, followed only then
  by Idea 2;
- for a lower-risk early result, pursue the cross-language compiler observatory
  in Idea 7 and the semantic-debt metrics in Idea 9.

The project becomes outstanding when the same semantic source is not merely
rendered several ways, but is used to **reason** across those ways: to prove
equivalence, synthesize alternatives, transfer performance knowledge, optimize
query representation, or quantify the value of future hardware. That is the
scientific leverage ordinary SIMD libraries do not have.

