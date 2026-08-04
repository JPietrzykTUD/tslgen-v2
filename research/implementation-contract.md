# Implementation contracts: making SIMD portability explicit

## Executive answer

The strongest near-term differentiator for TSL is not another SIMD primitive,
vector type, target, or output language. It is the ability to make portability
compromises explicit and enforceable:

> **TSL could become the SIMD system in which an application declares the
> implementation and semantic properties it requires, and `tslc` either
> generates a dependency-closed C++ and Rust library satisfying them or rejects
> the request with an exact explanation.**

Most SIMD abstractions tend toward one of three positions:

- expose a conservative common API intended to avoid large performance cliffs;
- expose a broad API and emulate unsupported operations;
- expose ISA-shaped operations and leave portability to the application.

These choices trade expressiveness, portability, and performance predictability
against one another. TSL can support a fourth position: retain a broad
operation set, but make each selected implementation's quality, dependencies,
semantics, and evidence visible to the consumer. The consumer can then decide
which compromises are acceptable.

This would be a genuinely useful artifact feature. A contract file and checker
would not, by themselves, constitute a top-tier scientific result. The
scientific opportunity is to test whether transitive, semantically aware
contracts detect and prevent performance or correctness cliffs that ordinary
API portability leaves hidden.

## What established libraries already provide

The basic SIMD-library design space is already crowded:

- [Highway](https://google.github.io/highway/en/master/README.html) provides
  length-agnostic operations, static and dynamic dispatch, and an instruction
  matrix indicating static instruction counts for operations.
- [xsimd](https://xsimd.readthedocs.io/en/latest/api/arch.html) exposes
  compile-time support, runtime availability, architecture selection, emulated
  operation, and architecture dispatch.
- [NSIMD](https://agenium-scale.github.io/nsimd/) is itself generator-backed,
  provides multiple C and C++ APIs, supports fixed and scalable vector
  architectures, and includes additional GPU-oriented programming paradigms.
- [SIMDe](https://github.com/simd-everywhere/simde) provides extensive portable
  implementations of native intrinsic interfaces, including cross-architecture
  fallbacks.
- [EVE](https://github.com/jfalcou/eve) offers a rich, expressive C++20
  abstraction with broad operation and architecture support.
- [HybridSIMD](https://conf.researchr.org/details/ase-2025/ase-2025-papers/186/HybridSIMD-A-Super-C-SIMD-Library-with-Integrated-Auto-tuning-Capabilities)
  already makes integrated SIMD-library autotuning an explicit peer-reviewed
  contribution.

Consequently, the following are not convincing standalone novelty claims:

- a portable SIMD API;
- static or runtime ISA dispatch;
- automatic generation of wrappers;
- multiple C or C++ API variants;
- scalable-vector support;
- scalar or cross-ISA fallback;
- adding autotuning to a SIMD library.

In the official interfaces and documentation reviewed here, the individual
pieces of implementation visibility exist in places, but an equivalent
end-to-end contract combining all of the following was not found:

- operation-level implementation quality;
- transitive dependency provenance;
- semantic requirements;
- cross-language capability parity;
- consumer-defined acceptance policy;
- generation failure when the complete requested slice violates that policy.

This targeted comparison is not an exhaustive novelty search. Failure to find
an identical feature is not proof that the idea is unpublished.

## Why TSL is unusually well positioned

The repository already contains most of the compiler facts needed to implement
such a contract without introducing a new optimizer or parsing generated
target-language text:

- Root-oriented generation and profile-scoped dependency closure begin with
  requested primitives and pull in only required callees in
  [`pipeline.py`](../tslc/src/tslc/pipeline.py) and
  [`_pipeline_closure.py`](../tslc/src/tslc/_pipeline_closure.py).
- The typed implementation-state lattice distinguishes `native`, `composed`,
  `fallback`, and `unknown` in
  [`implementation_facts.py`](../tslc/src/tslc/lower/implementation_facts.py).
- Dependency closure conservatively propagates implementation state, safety,
  and required target features through live concrete call edges.
- [`concrete_analysis.py`](../tslc/src/tslc/concrete_analysis.py) already
  produces an exact, deterministic dependency analysis for a concrete
  specialization.
- Generated C++ and Rust artifacts already expose implementation-state queries
  through [`cpp.py`](../tslc/src/tslc/backend/cpp.py) and
  [`rust_implementation_state.py`](../tslc/src/tslc/backend/rust_implementation_state.py).
- Arithmetic, operation, memory, conversion, shift, mask, and safety facts are
  promoted into typed catalog or lowered values. For example,
  [`arithmetic.py`](../tslc/src/tslc/catalog/arithmetic.py) includes explicit
  guarantees such as integer wrapping and exceptional division behavior.
- C++ and Rust value-test planning is driven from the same authored corpus.
- Input digests, generation snapshots, coverage reports, and a lowering
  coverage ratchet already exist.

This means the first useful version is principally a new compiler-owned
projection and policy check over existing post-closure facts. It does not
require an instruction-level cost model or a new target-language AST.

## Proposed feature: a TSL portability contract

### Contract input

A consumer supplies a contract describing:

- primitive roots;
- type families;
- target profiles;
- output backends;
- allowed implementation states;
- forbidden implementation states;
- required semantic guarantees;
- safety requirements;
- representation constraints where relevant;
- whether corresponding capabilities must exist in every requested language.

An illustrative contract might express:

```toml
# Illustrative syntax; this is not a currently supported tslc.toml schema.
[contract]
roots = ["less", "to_integral", "compress_store"]
profiles = ["avx2", "avx512", "sve"]
backends = ["cpp", "rust"]
allowed_states = ["native", "composed"]
forbid_unknown = true
require_backend_parity = true
require_safe_public_call = true
```

State requirements should be configurable. Requiring every operation to be
`native` would often be unnecessarily strict: a short composition can be both
correct and fast, while a nominally native intrinsic may still expand poorly.

### Compiler behavior

For each requested root, type, profile, and backend, `tslc` would:

1. run ordinary selection, lowering, and dependency closure;
2. inspect the exact post-pruning specialization and its transitive callees;
3. evaluate the contract against typed compiler facts;
4. generate the minimal admitted library slice when the contract holds;
5. reject the request with a deterministic dependency path and source
   provenance when it does not.

An illustrative rejection could say:

```text
contract violation:
  root:       filter_store<ui32>
  profile:    avx2
  backend:    rust
  requirement: allowed implementation states = {native, composed}
  selected state: fallback
  path:       filter_store -> compress_store -> compress
  origin:     selected implementation and exact authored source location
```

This example is a desired diagnostic shape, not a claim about the actual state
of those corpus specializations.

### Capability certificate

Every successful request should optionally produce a machine-readable
certificate containing:

- input digest and compiler version;
- requested roots and complete emitted closure;
- exact primitive, variant, type, profile, representation target, and backend
  identities;
- selected implementation origins;
- implementation states and their provenance;
- concrete call dependencies;
- required target features;
- propagated safety properties;
- mask and integral-mask representations;
- available typed semantic guarantees;
- cross-backend availability and parity;
- explicit `unknown` or unsupported facts;
- verification evidence only when the corresponding build or value-test step
  actually ran.

The certificate must distinguish assertions from evidence. “Lowered,”
“compiled,” “executed,” “differentially tested,” and “proved equivalent” are
different claims and must never be collapsed into a single `verified` flag.

## Why this is genuinely useful

### No silent portability cliffs

An application could use a broad operation set without silently accepting a
generic or scalar path on a target where that path is unacceptable. The
compiler would identify the complete transitive reason rather than reporting
only that the public root exists.

### Application-specific SIMD library synthesis

`tslc` already accepts a requested primitive subset and computes its
dependencies. A contract turns that mechanism into an application-facing
product:

> Given an operation set, target matrix, and language set, synthesize the
> smallest SIMD SDK satisfying the application's portability envelope.

Compared with shipping a full header-oriented abstraction library, this may
reduce parsing, compilation, documentation, testing, package size, and audit
surface. These benefits are plausible, not currently demonstrated; they
require measurement.

### Cross-language parity as a property

Generating C++ and Rust from the same corpus is interesting only if the system
can say precisely where the two generated products agree or diverge. A
contract can require matching:

- requested operation availability;
- typed semantics;
- implementation-quality class;
- supported type and target combinations;
- generated test coverage.

That is stronger than claiming that the compiler can render two syntaxes.

### Faster target bring-up

A hardware vendor or architecture researcher could define the capability
contract required by a workload and immediately obtain:

- the smallest primitive basis that must be supported;
- which implementations are already native, composed, or fallback;
- the dependencies responsible for gaps;
- generated C++ and Rust surface coverage;
- a conformance and regression target.

This makes “fast integration of a new paradigm” concrete and measurable rather
than relying on source-line counts or anecdotal development effort.

## The most credible low-effort wins

### 1. Extend the coverage ratchet to implementation quality

The existing
[`coverage_ratchet.py`](../tslc/src/tslc/maintenance/coverage_ratchet.py)
detects when an emitted slot disappears or loses emitted variants. Its own
documentation correctly states that lowering is not a compile guarantee.

Extend the baseline identity sufficiently to detect:

- `native` to `composed`;
- `native` or `composed` to `fallback`;
- known to `unknown`;
- loss of C++/Rust parity;
- new required target features;
- weakened typed semantic guarantees;
- newly unsafe public behavior.

This is immediately useful even before a user-facing contract syntax exists.
It prevents a project change from retaining API coverage while degrading the
quality of the selected implementation.

### 2. Preserve implementation-state provenance

The current state enum is useful but coarse. A certificate should explain why
a specialization is classified as it is:

- direct intrinsic;
- representation-compatible return;
- primitive composition;
- backend loop;
- inherited or generic fallback;
- transitive degradation from a callee;
- opaque or otherwise unclassified implementation.

Preserving those typed reasons through lowering and closure would make
diagnostics, reports, and future empirical work substantially more credible.

### 3. Add a post-closure contract checker

The checker should consume the same selected and lowered facts used by
generation. It must not reimplement selection, infer dependencies from emitted
symbols, or parse rendered C++ or Rust.

The first contract version only needs:

- roots, profiles, types, and backends;
- allowed implementation states;
- no unresolved dependency;
- no `unknown`, optionally;
- backend parity;
- safety constraints.

Typed semantic requirements can be added only for contract families already
represented explicitly in the catalog.

### 4. Emit a capability certificate

Consolidate existing analysis, coverage, semantic, and digest facts into a
stable JSON projection plus a concise human-readable report. The schema should
be deterministic and versioned.

This is not merely documentation generation. The JSON becomes an input to CI,
packaging, downstream workload profiles, target bring-up, and later database
optimization tools.

### 5. Provide generated assertion helpers

The generated libraries already expose implementation-state queries. Small
idiomatic helpers could let consumers assert requirements directly:

- a C++ `static_assert`-friendly predicate;
- a Rust compile-time trait or constant assertion;
- a clear failure pointing back to the compiler-generated capability report.

Compiler-level checking remains necessary for complete multi-profile and
cross-backend contracts, but local assertions improve usability.

### 6. Define workload capability profiles

A profile is a named set of primitive roots plus a contract. Examples might
include:

- relational scan;
- bitmap processing;
- compression/decompression;
- hash probing;
- image-processing kernels.

The generic profile mechanism could be supported by `tslc`, but named
database-specific policies should live in a downstream package or
supplementary data. They are consumer decisions, not compiler semantics.

The first database profile could answer:

> Which profiles and languages provide a non-fallback implementation closure
> for the primitive basis of a vectorized relational scan?

That is a small artifact addition and a useful precursor to a database study.

## Stronger moderate-effort extensions

### Performance-hazard contracts

`native` and `composed` are too coarse to predict cost. Add conservative typed
hazard facts such as:

- scalar lane loop;
- memory round trip or temporary buffer;
- helper call;
- cross-register operation;
- generic fallback;
- unresolved opaque target-language behavior.

Propagate these facts through concrete dependencies and allow contracts to
forbid them. This is more defensible than assigning an invented numerical cost.
If a hazard cannot be determined without parsing raw target-language text, it
must remain `unknown` until the corresponding behavior has a typed TSIL owner.

### Semantic parity and conformance packs

Generate a sliceable conformance package for one contract and target matrix:

- common authored cases for C++ and Rust;
- generic differential cases where applicable;
- exact bitwise cases for representation-sensitive behavior;
- normalized result reporting across compilers and runners;
- explicit coverage and skip reasons.

This could turn TSL into a cross-language SIMD compiler and toolchain
observatory. Its scientific value would depend on discovering and
systematically characterizing real semantic or compiler discrepancies.

### Out-of-tree target packs

The compiler already accepts multiple `.tsl` source paths, but a stable
third-party target-pack product would additionally need:

- pack identity and versioning;
- compiler compatibility constraints;
- declarative extension and profile inputs;
- collision and dependency rules;
- conformance requirements;
- deterministic coverage reports;
- a clear boundary between data-only additions and compiler capabilities that
  still require code changes.

This could be valuable for hardware research and new-ISA prototyping, but it is
not a trivial plugin mechanism and should not turn `tslc` into a general
framework.

### Database mask, bitmap, and selection-vector bridge

The corpus already contains `to_integral`, `to_mask`, `compress`, `expand`,
`compress_store`, and mask-population operations. A downstream database layer
could define capability contracts for transitions among:

- native predicate masks;
- vector comparison masks;
- dense integral bitmaps;
- selection vectors;
- compacted value streams.

This is the most promising bridge from implementation contracts to the
pipeline cost-model direction. The representation alternatives and database
policy belong downstream; `tslc` should expose their primitive capabilities and
evidence without becoming a query optimizer.

## Important limitation: `native` is not a cost

The current `ImplementationState.NATIVE` classification is structural. It
roughly identifies a direct intrinsic or representation-compatible return
rather than an implementation containing visible composition. It does not
prove:

- that the compiler emits one machine instruction;
- low latency or high throughput;
- absence of compiler expansion;
- good scheduling or register allocation;
- superiority over a composed implementation;
- stable behavior across compiler versions.

Therefore, this feature should be described as an **implementation contract**,
**portability envelope**, or **structural portability certificate**. It should
not initially be marketed as a cost model or a performance guarantee.

Measured instruction counts, latency, throughput, code size, and complete
kernel performance belong to later empirical evidence. A structural contract
can reject a known fallback; it cannot promise that the admitted code is fast.

## Scientific storyline

### Central thesis

> Transitive, semantically aware implementation contracts allow applications
> to use a broader SIMD operation set while detecting portability,
> implementation-quality, and cross-language regressions that API-level
> portability does not expose.

### Research questions

1. How often do operation availability checks hide composed, fallback, opaque,
   or semantically divergent implementations across targets?
2. How accurately do TSL's structural states and hazard facts identify measured
   performance cliffs?
3. Can contracts prevent meaningful regressions without rejecting efficient
   compositions excessively?
4. Does contract-directed minimal generation reduce build time, package size,
   and audit surface compared with full-library integration?
5. Can one workload contract materially reduce the effort required to bring a
   new target to useful database-kernel coverage?
6. Does a shared contract expose C++/Rust backend or toolchain discrepancies
   that language-specific testing misses?

### Required evaluation

A credible evaluation would need:

- representative operations, including comparisons, masks, conversions,
  gathers, scatters, compression, expansion, and reductions;
- fixed-width and scalable targets;
- multiple microarchitectures rather than one representative CPU per ISA;
- C++ and Rust toolchains;
- comparison with Highway, xsimd, NSIMD, SIMDe, or other appropriate
  libraries at the level each supports;
- real database kernels or a database-system integration;
- measured latency, throughput, code size, and compile-time behavior;
- false-positive and false-negative analysis for structural hazard
  classifications;
- ablations separating dependency closure, state enforcement, semantic
  constraints, and minimal package synthesis;
- reproducible target, compiler, flags, workload, and measurement records.

The strongest database evaluation would use scan, filter, bitmap, aggregation,
and hash-probe kernels and ask whether a workload contract predicts or prevents
unacceptable implementations across target profiles.

### Results that would weaken or falsify the thesis

The idea would not support a strong paper if:

- existing libraries already expose equivalent transitive contracts;
- most useful TSL implementations remain `unknown`;
- the state or hazard model correlates poorly with real performance cliffs;
- contracts reject many efficient implementations and therefore force manual
  exceptions;
- cross-language parity is automatic and reveals no meaningful engineering or
  scientific issue;
- minimal generation produces negligible build or artifact benefits;
- the database integration does not use the contract for a real decision.

Negative findings should be reported rather than converting the feature into a
novelty claim by terminology.

## Database relevance and architectural boundary

The basic implementation contract is a systems/compiler artifact. It becomes
database research when a database consumer uses it to make or validate a
decision, for example:

- admitting only target profiles with a non-fallback scan substrate;
- selecting a mask, bitmap, selection-vector, or compacted representation;
- determining whether a physical operator implementation is available on a
  deployment target;
- rejecting a generated query plan whose primitive closure violates a
  portability service-level objective;
- guiding which primitives should be implemented first for a new database
  hardware target.

The compiler boundary should remain strict:

- `tslc` owns selected, lowered, dependency, semantic, safety, feature, and
  evidence facts;
- a compiler-owned certificate projects those facts without re-deriving them;
- generic contract evaluation may live in the compiler;
- named database workloads, cost models, and plan-selection policy live
  downstream;
- no cost or hazard should be inferred by parsing rendered C++ or Rust;
- opaque implementation behavior remains explicitly unknown.

This boundary follows the repository's compact-compiler design: backends format
decided semantics, and downstream tools consume compiler facts without causing
the compiler to learn database policy.

## Crisp elevator pitch

- **Declare the SIMD operations, targets, types, and languages an application
  requires.**
- **Generate only their exact transitive implementation closure.**
- **Reject hidden fallback, unknown behavior, unsafe calls, or backend
  divergence according to an explicit policy.**
- **Explain every selected implementation and dependency with deterministic
  source provenance.**
- **Attach semantic guarantees and clearly labelled correctness evidence to the
  generated package.**
- **Ratchet those properties in CI so API-preserving implementation regressions
  cannot pass unnoticed.**
- **Use workload profiles to turn new-target integration into a measurable
  capability-closure problem.**

The shortest positioning is:

> **TSL is the SIMD abstraction that does not merely promise portability; it
> states exactly what portability cost was accepted, and lets the consumer
> refuse it.**

## Recommendation

Implement this as one coherent sequence:

1. extend the existing coverage ratchet with implementation-state and
   cross-backend regressions;
2. preserve typed state provenance through lowering and dependency closure;
3. emit a deterministic capability certificate from post-closure facts;
4. add a simple allowed-state and safety contract checker;
5. define one external relational-scan capability profile;
6. evaluate whether the contract predicts real portability cliffs before
   adding richer hazard classes or performance claims.

The first four items are credible low-effort or low-to-moderate-effort wins
because they expose and enforce facts already owned by the compiler. Together
they could make TSL an unusually transparent and useful SIMD artifact.

They do not automatically create a scientific contribution. The publication
opportunity rests on demonstrating that the contracts reveal and prevent
important behavior that established abstractions fail to make actionable.
