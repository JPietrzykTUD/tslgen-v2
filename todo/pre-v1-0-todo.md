# TSLc + TSL pre-v1.0 TODO

> **Working theme:** implementation-aware SIMD portability.
>
> pre-v1.0 should make TSL more than another portable SIMD wrapper library. The generated library should expose not only *whether* an operation exists, but *how* that exact specialization is realized, what it transitively depends on, which machine/compiler capabilities it requires, and which language-neutral semantics it guarantees. Applications should be able to turn those facts into enforceable portability contracts.

---

## 0. pre-v1.0 product thesis

The pre-v1.0 differentiator should be:

> **TSL is a compiler for implementation-aware SIMD libraries.**
>
> From one semantic corpus, `tslc` synthesizes target- and language-specific SIMD APIs while retaining machine-readable knowledge about implementation realization, transitive dependencies, requirements, semantics, and verification evidence.

This is intentionally different from a feature-count competition with Highway, xsimd, EVE, NSIMD, SIMDe, etc.

### pre-v1.0 should answer these questions exactly

For a concrete specialization such as:

```text
compress_store<ui32, avx2, cpp>
```

TSL should be able to answer:

1. Does it exist?
2. Where did its implementation come from?
3. Is it direct/native, composed, fallback, or unknown?
4. Which structural performance hazards are present?
5. Which primitives does it call, transitively?
6. Which target features does the complete live dependency closure require?
7. Which compiler capabilities does it require?
8. Which semantic guarantees apply?
9. Is its public call safe under the declared contract?
10. Does an equivalent capability exist in the other generated backends?
11. What evidence exists: lowered, compiled, executed, differential-tested, benchmarked?
12. Does this specialization satisfy a consumer-defined portability contract?

If pre-v1.0 can answer these deterministically, we have a coherent product/research identity.

---

# 1. Implementation Realization

**Priority: P0 / core pre-v1.0 feature**

Evolve the current `native | composed | fallback | unknown` state into a structured, queryable **implementation realization**.

The existing implementation-state lattice should remain available as a convenient coarse summary, but it must no longer be the entire model.

## 1.1 Target model

```text
implementation realization
│
├── origin
│   ├── intrinsic
│   ├── primitive_composition
│   ├── scalar_or_generic_fallback
│   └── backend_helper
│
├── hazards
│   ├── scalar_lane_loop
│   ├── memory_roundtrip
│   ├── temporary_buffer
│   ├── cross_register_shuffle
│   ├── helper_call
│   └── unknown_target_code
│
├── dependencies
│   └── exact transitive primitive graph
│
├── requirements
│   ├── target_features
│   └── compiler_capabilities
│
└── semantics
    ├── safety
    ├── arithmetic_contract
    ├── inactive_lane_behaviour
    └── representation_semantics
```

## 1.2 Origin

Add a typed origin classification for every emitted specialization.

Minimum values:

```text
intrinsic
primitive_composition
scalar_or_generic_fallback
backend_helper
unknown
```

Requirements:

- [ ] Infer origin from compiler-owned TSIL/lowering facts, not from rendered C++/Rust text.
- [ ] Preserve authored implementation source span/provenance.
- [ ] Preserve selected extension/profile/type/backend identity.
- [ ] Preserve compiler-alternative provenance when a compiler capability chooses among bodies.
- [ ] Define deterministic rules when several origins occur in one realization.
- [ ] Keep the existing coarse `ImplementationState` as a projection of realization facts.

Suggested rule:

```text
intrinsic only                         -> native
representation-compatible direct path -> native
primitive composition                 -> composed
explicit scalar/generic fallback      -> fallback
opaque/unclassified target code       -> unknown
```

Do **not** interpret `native` as “fast” or “one instruction”.

## 1.3 Structural hazards

Introduce a closed, typed set of structural hazards.

Initial pre-v1.0 set:

```text
scalar_lane_loop
memory_roundtrip
temporary_buffer
cross_register_shuffle
helper_call
unknown_target_code
```

Possible later additions:

```text
multiple_vector_passes
branch_per_lane
scalar_extract_insert_loop
mask_materialization
representation_conversion
wide_intermediate
noncontiguous_memory_access
```

Requirements:

- [ ] Hazards must be inferred from typed TSIL/compiler facts whenever possible.
- [ ] Do not parse rendered C++/Rust to infer hazards.
- [ ] If a hazard cannot be determined safely, record `unknown_target_code` rather than guessing.
- [ ] Propagate relevant hazards transitively through concrete `call<...>` dependencies.
- [ ] Preserve whether a hazard is direct or inherited from a callee.
- [ ] Preserve the dependency path that introduced each transitive hazard.
- [ ] Make hazard vocabulary backend-neutral where semantics are backend-neutral.
- [ ] Allow backend-specific evidence only behind backend-owned typed capability descriptors.

Important constraint:

> Hazards are structural facts, **not a numerical cost model**.

`scalar_lane_loop` is evidence of a possible performance cliff. It is not a promise that the implementation is slower than another implementation.

## 1.4 Dependency graph

Promote the already existing dependency closure into a first-class public analysis artifact.

Requirements:

- [ ] Exact concrete dependency graph per specialization.
- [ ] Preserve direct vs transitive dependencies.
- [ ] Preserve source/provenance for every edge.
- [ ] Preserve unresolved dependency reasons.
- [ ] Cycle-safe deterministic rendering.
- [ ] Queryable through `tslc analyze` / public Python API.
- [ ] Optional machine-readable JSON projection.
- [ ] Same graph must drive pruning, realization propagation, diagnostics, and certificates.
- [ ] No parallel dependency model maintained by renderers.

## 1.5 Requirements

Keep hardware requirements and compiler requirements explicitly separate.

```text
requirements
├── target_features
└── compiler_capabilities
```

Requirements:

- [ ] Preserve direct target features selected by the source body.
- [ ] Preserve transitively required target features after dependency closure.
- [ ] Preserve direct compiler capability requirements.
- [ ] Propagate compiler capability requirements correctly through alternatives/callees where meaningful.
- [ ] Explain why an implementation was not selected even when the CPU feature exists.
- [ ] Distinguish “hardware supports it” from “compiler exposes/proves it”.

Desired diagnostic shape:

```text
compress_store<ui32>
  hardware: sufficient
  compiler capability: missing intrinsic mask_compressstoreu
  selected alternative: composed implementation
  realization: composed
  hazard: scalar_lane_loop
```

## 1.6 Generated-library queries

C++ and Rust should expose equivalent realization facts where representable.

C++ conceptually:

```cpp
auto state = tsl::implementation_state_v<primitive::compress_store, Vec, ...>;
auto realization = tsl::implementation_realization_v<primitive::compress_store, Vec, ...>;

static_assert(!realization.has_hazard(tsl::hazard::scalar_lane_loop));
```

Rust conceptually:

```rust
const REALIZATION: ImplementationRealization =
    <Profile as ImplementationRealizationOf<CompressStore, Vec, Args>>::VALUE;
```

Do not force a large runtime object into the generated API if a compact compile-time representation is more appropriate. A generated enum/bitset/trait projection is sufficient; detailed provenance can remain in the compiler certificate/report.

## 1.7 Acceptance criteria

- [ ] Every emitted specialization has a deterministic realization summary.
- [ ] Existing `ImplementationState` can be derived from it.
- [ ] `compress_store` demonstrates at least three meaningfully different realizations across the supported profile matrix, e.g. direct intrinsic, composition, scalar/generic loop.
- [ ] Transitive state/hazard propagation is covered by tests with at least one multi-level call chain.
- [ ] C++ and Rust expose equivalent coarse realization queries.
- [ ] `tslc analyze` can show exact origin + hazards + dependency path + requirements for one concrete specialization.

---

# 2. Portability / Implementation Contracts

**Priority: P0 after realization model; core pre-v1.0 productization**

The realization model becomes materially useful when a consumer can **require** properties instead of merely inspecting them.

## 2.1 Goal

A consumer should be able to say:

> Generate the smallest TSL slice for these primitives/types/profiles/backends, but reject the request if any selected implementation violates my portability envelope.

Illustrative syntax only:

```toml
[contract]
roots = ["less_than", "compress_store", "gather_narrow", "to_integral"]
profiles = ["avx2", "sapphire_rapids", "sve"]
backends = ["cpp", "rust"]
types = ["ui32", "ui64"]

allowed_states = ["native", "composed"]
forbid_unknown = true
forbid_hazards = ["scalar_lane_loop", "memory_roundtrip"]
require_backend_parity = true
require_safe_public_call = true
```

## 2.2 pre-v1.0 contract vocabulary

Keep pre-v1.0 intentionally small.

Required dimensions:

- [ ] primitive roots
- [ ] types/type groups
- [ ] profiles
- [ ] backends
- [ ] allowed/forbidden implementation states
- [ ] forbidden hazards
- [ ] no unresolved dependencies
- [ ] optional backend parity
- [ ] safety requirement
- [ ] semantic guarantees already represented in typed catalog data

Do **not** introduce arbitrary user expressions or a policy programming language in pre-v1.0.

## 2.3 Contract evaluation

Contracts must run over the exact post-selection/post-lowering/post-pruning facts used for generation.

Pipeline:

```text
request
  -> select
  -> lower
  -> dependency closure
  -> realization propagation
  -> contract evaluation
  -> generate admitted slice OR fail closed
```

Requirements:

- [ ] Contract checker consumes compiler-owned typed facts.
- [ ] No parsing of generated target code.
- [ ] Fail closed on `unknown` when requested.
- [ ] Exact violation path from requested root to violating callee.
- [ ] Exact source provenance where available.
- [ ] Stable diagnostic identities for CI/editor use.
- [ ] Same result via CLI and public API.

Desired diagnostic:

```text
contract violation

root:        filter_store<ui32>
profile:     avx2
backend:     cpp
requirement: forbid hazard scalar_lane_loop

path:
  filter_store
    -> compress_store
      -> extract_value

selected realization:
  compress_store: composed
  inherited hazard: scalar_lane_loop

source:
  tsldata/primitives/load_store/pack_expand.tsl:...
```

## 2.4 Generated assertion helpers

Provide lightweight local assertions for users who do not need a full multi-profile contract.

C++ conceptually:

```cpp
static_assert(tsl::supports_v<primitive::compress_store, Vec>);
static_assert(!tsl::has_hazard_v<
    primitive::compress_store,
    Vec,
    tsl::hazard::scalar_lane_loop>);
```

Rust conceptually:

```rust
const _: () = assert_realization::<CompressStore, Vec, NoScalarLaneLoop>();
```

The compiler-level contract remains authoritative for transitive/multi-backend/multi-profile checks.

## 2.5 Acceptance criteria

- [ ] One contract can be evaluated over multiple profiles and both C++/Rust.
- [ ] Contract rejection includes exact root-to-callee path.
- [ ] Contract generation emits only the admitted dependency-closed slice.
- [ ] CI can run contract checks without building generated binaries.
- [ ] At least one regression test proves that API availability stays constant while a realization-quality regression is caught.

---

# 3. Language-Neutral Semantics

**Priority: P0/P1; central long-term differentiator**

TSL should continue moving semantics that matter for portability out of raw C++/Rust text and into language-neutral typed facts.

The goal is **not** to create a complete SIMD IR or parse arbitrary C++/Rust.

The goal is:

> Lift exactly the semantics required to guarantee that generated backends implement the same operation contract.

## 3.1 Existing direction to consolidate

Keep/strengthen typed semantic families such as:

```text
arithmetic semantics
memory semantics
conversion semantics
shift semantics
mask semantics
representation-change semantics
safety semantics
```

Examples of useful explicit guarantees:

```text
integer_wrapping
integer_quotient_toward_zero
integer_remainder_has_dividend_sign
integer_zero_divisor_fails
signed_min_div_neg_one_returns_min
floating_division_ieee754_values
inactive_lanes_do_not_participate
```

## 3.2 pre-v1.0 semantic contract model

For every primitive family where semantics matter across languages:

- [ ] Define closed typed semantic vocabulary.
- [ ] Validate contradictory guarantees at catalog construction.
- [ ] Bind semantic roles to actual parameters/types.
- [ ] Carry semantics into lowered specialization facts.
- [ ] Generate C++ and Rust implementations/tests from the same semantic source.
- [ ] Make semantic facts queryable through compiler analysis/certificates.
- [ ] Let portability contracts require selected semantic guarantees.

## 3.3 Inactive-lane behavior

Make masked-operation behavior explicit rather than implicit in implementation code.

Candidate vocabulary:

```text
inactive_lanes_preserved
inactive_lanes_zeroed
inactive_lanes_undefined
inactive_lanes_do_not_participate
inactive_lanes_not_accessed
```

This matters for:

- masked arithmetic exceptions;
- gather/scatter safety;
- reductions;
- where/select semantics;
- cross-language backend parity.

## 3.4 Representation semantics

Make representation-changing operations explicit.

Candidate facts:

```text
lane_count_preserved
lane_count_scaled
bit_pattern_preserved
numeric_value_preserved
saturating
wrapping
zero_extending
sign_extending
truncating
reinterpreting
mask_representation_change
```

Required for robust reasoning about:

- cast/reinterpret;
- widening/narrowing;
- mask <-> integral mask;
- scalable-vector representations;
- database mask/bitmap bridges.

## 3.5 Raw target-language boundary

Keep TSIL as an island language with raw target-language escape hatches, but make the boundary explicit.

Rules:

- [ ] Raw target-language text is allowed where semantic lifting is unnecessary.
- [ ] Raw text that hides a property needed by realization/contract reasoning introduces `unknown_target_code`.
- [ ] Do not infer semantic guarantees by parsing arbitrary target-language text.
- [ ] Add new typed TSIL regions only when a real portability/semantic obligation justifies them.

This preserves TSL's pragmatic design instead of turning `tslc` into Clang/rustc.

## 3.6 Cross-language parity

Add an explicit parity analysis.

For each requested capability compare C++ and Rust on:

- [ ] availability
- [ ] type/profile coverage
- [ ] implementation state
- [ ] structural hazards
- [ ] semantic guarantees
- [ ] safety facts
- [ ] required target features
- [ ] verification evidence

Output should distinguish:

```text
same semantics, different realization
same realization class, different compiler requirement
available only in C++
available only in Rust
semantic mismatch
unknown parity
```

Do not reduce parity to a single boolean internally.

## 3.7 Acceptance criteria

- [ ] Arithmetic semantics are fully typed for existing arithmetic primitives targeted for pre-v1.0.
- [ ] Masked/inactive-lane behavior is explicit for the main masked operation families.
- [ ] Core conversion/representation semantics are typed.
- [ ] C++ and Rust value tests are generated from the same semantic facts.
- [ ] At least one deliberate backend-semantic mismatch is detected by compiler validation/tests.

---

# 4. Capability Certificate

**Priority: P0/P1; highly recommended for pre-v1.0**

A successful generation should optionally emit a deterministic, versioned **capability certificate**.

This is the machine-readable product of items 1–3.

## 4.1 Certificate contents

Per generation request:

```text
compiler/version/input identity
requested roots/types/profiles/backends
emitted dependency closure

for each specialization:
  callable identity
  source provenance
  selected implementation
  realization origin
  coarse implementation state
  direct hazards
  transitive hazards + provenance paths
  direct dependencies
  transitive dependency identity
  target feature requirements
  compiler capability requirements
  safety facts
  semantic guarantees
  backend parity facts
  verification evidence
```

## 4.2 Evidence taxonomy

Never collapse evidence into `verified = true`.

Use explicit stages, e.g.:

```text
parsed
validated
selected
lowered
emitted
compiled
executed
value_tested
differentially_tested
benchmarked
```

Potential later evidence:

```text
emulated
sanitizer_tested
assembly_inspected
formal_equivalence_checked
```

## 4.3 Determinism

- [ ] Versioned JSON schema.
- [ ] Stable ordering.
- [ ] Input digest.
- [ ] `tslc` version.
- [ ] Machine-profile identity/digest.
- [ ] Backend policy identity/digest.
- [ ] No timestamps in canonical semantic content unless explicitly separated as non-deterministic run metadata.

## 4.4 Uses

The certificate should support:

- CI regression checks;
- downstream application contracts;
- release artifacts;
- compiler/toolchain comparison;
- architecture bring-up;
- research evaluation;
- editor/explorer views;
- future database/operator planning.

---

# 5. Implementation-Quality Regression Ratchet

**Priority: P0/P1; very high practical value**

Current coverage regression checks should evolve from:

```text
"does the specialization still exist?"
```

into:

```text
"did the specialization silently become worse?"
```

## 5.1 Regressions to detect

- [ ] native -> composed
- [ ] native/composed -> fallback
- [ ] known -> unknown
- [ ] new `scalar_lane_loop`
- [ ] new `memory_roundtrip`
- [ ] new `temporary_buffer`
- [ ] new target feature requirement
- [ ] new compiler capability requirement
- [ ] weakened safety property
- [ ] weakened semantic guarantee
- [ ] lost C++/Rust parity
- [ ] lost build/value-test evidence

## 5.2 Baseline policy

Not every change is an error.

Support:

```text
report
warn
fail
explicitly_accept_new_baseline
```

The ratchet should compare typed certificate/realization facts, not generated source strings.

## 5.3 Acceptance criteria

- [ ] Deterministic baseline file.
- [ ] Human-readable diff.
- [ ] Machine-readable diff.
- [ ] Exact specialization identity and reason for degradation.
- [ ] CI mode exits non-zero on forbidden regression.

---

# 6. Explainability / Inspection UX

**Priority: P1**

The compiler already owns unusually rich facts. pre-v1.0 should make them easy to consume.

## 6.1 `tslc explain`

For one specialization, show:

```text
selection
  candidate set
  winning source body
  rejected alternatives + reasons

realization
  state
  origin
  hazards

closure
  direct callees
  transitive callees
  propagated features
  propagated hazards
  propagated safety

semantics
  guarantees

backend
  exact generated type/callable
  compiler capabilities
```

## 6.2 `tslc analyze`

Support deterministic tree/graph output for a root or contract.

Useful modes:

```text
--format text
--format json
--show hazards
--show requirements
--show semantics
--show provenance
--show parity
```

## 6.3 Editor integration

Do not reimplement compiler semantics in the VS Code client.

Potential pre-v1.0 views:

- realization badge: native/composed/fallback/unknown;
- hazard list;
- “why?” drilldown;
- backend parity;
- contract violation lens;
- exact implementation/dependency navigation.

---

# 7. Hardware Capability vs Compiler Capability

**Priority: P1; consolidate rather than invent**

TSL already has the right conceptual split. pre-v1.0 should make it part of the public story and certificate schema.

```text
CPU / ISA capability
        !=
compiler capability
        !=
implementation realization
```

Example:

```text
AVX-512 instruction exists on CPU
    |
    +-- compiler exposes required intrinsic? no
            |
            +-- choose composed alternative
                    |
                    +-- realization differs despite same hardware
```

TODO:

- [ ] Ensure every compiler capability has typed ID, probe, evidence, and diagnostic.
- [ ] Keep compiler-version spelling/probe logic backend-owned.
- [ ] Expose requirement in certificate/explain output.
- [ ] Include compiler-capability differences in cross-language parity.
- [ ] Add regression checks for newly introduced compiler requirements.

---

# 8. Contract-Directed Minimal SDK Synthesis

**Priority: P1; mostly leverage existing dependency closure**

Given:

```text
roots + types + profiles + backends + contract
```

generate only the required admitted closure.

Potential benefits to measure:

- generated source size;
- downstream parse/compile time;
- package size;
- audit surface;
- test matrix size;
- bring-up effort for a new target.

TODO:

- [ ] Make minimal-root generation a stable public workflow.
- [ ] Ensure helper/algorithm dependencies participate correctly.
- [ ] Include exact closure in certificate.
- [ ] Ensure documentation/tests are also sliced consistently.
- [ ] Guarantee no semantically required dependency is omitted.

---

# 9. Empirical Validation of Realization Facts

**Priority: P1 research/evidence; do not turn into a runtime cost model**

Structural realization facts only matter if they correlate with real portability/performance cliffs.

Use the `research/realization-aware-selection-src` pilot as the first experiment.

Core hypothesis:

> Application decisions based on implementation realization can outperform decisions based only on ISA labels or operation availability.

## 9.1 Initial experiment

Candidate primitive:

```text
compress_store
```

Compare algorithm strategies across:

```text
AVX2
multiple AVX-512 profiles
NEON
SVE
RVV where executable
```

Vary:

- selectivity;
- input size/cache residency;
- element width;
- compiler;
- machine.

Measure whether facts such as:

```text
scalar_lane_loop
primitive_composition
direct_intrinsic
```

predict meaningful strategy changes.

## 9.2 Rule

Do not bake benchmark results into `tslc` as universal costs in pre-v1.0.

The benchmark validates whether structural facts are useful. It does not create a fragile architecture-specific cost database inside the compiler.

---

# 10. Workload Capability Profiles

**Priority: P2 / optional pre-v1.0 if cheap**

Allow downstream users to define named sets of roots + contracts.

Examples:

```text
relational_scan
bitmap_processing
selection_vector_pipeline
compression_decode
hash_probe
```

A database-oriented profile might require:

```text
less_than
to_integral
mask_population_count
compress_store
gather_narrow
```

and forbid:

```text
scalar_lane_loop
unknown_target_code
```

Important ownership rule:

> Domain-specific workload policies belong downstream or in supplementary packages, not in `tslc` core semantics.

`tslc` supplies generic contract machinery.

---

# 11. Out-of-Tree Target Packs

**Priority: P2 / post-v1.0 unless already nearly free**

Potentially valuable for hardware research, but scope carefully.

A future target pack should contain declarative:

- extension identities;
- profile facts;
- target features;
- primitive implementations;
- compiler capability requirements;
- tests/conformance facts;
- pack/compiler version compatibility.

Needs before declaring stable plugin support:

- [ ] collision rules;
- [ ] versioning;
- [ ] deterministic merge semantics;
- [ ] compatibility constraints;
- [ ] clear data-only vs compiler-code boundary;
- [ ] conformance requirements.

Do not turn pre-v1.0 into a general plugin framework just to claim extensibility.

---

# 12. What should NOT be a pre-v1.0 priority

These are useful features but are not the strongest differentiators.

## 12.1 C++ dynamic ISA dispatch

**Defer.**

Reasons:

- primarily solves binary-distribution rather than target-known HPC/database builds;
- requires baseline compilation discipline for the entire binary;
- dispatch belongs at kernel/algorithm boundaries, not primitive calls;
- Rust already has a narrow whole-algorithm implementation;
- considerable complexity for limited differentiation.

Revisit when there is a concrete distribution use case such as Python wheels, portable precompiled libraries, or heterogeneous fleet deployment.

## 12.2 More ISA breadth for its own sake

Do not add targets merely to increase a matrix count.

A new target is pre-v1.0-relevant when it validates one of:

- fixed vs scalable vector semantics;
- different mask representations;
- different realization paths;
- compiler-capability differences;
- meaningful contract/parity behavior.

## 12.3 More primitives for its own sake

Prefer closing semantic/realization evidence for important existing primitives over maximizing primitive count.

## 12.4 General numeric cost model

Do not assign invented costs to `native`, `composed`, etc.

If future work needs costs, build them downstream from measured evidence and explicit structural facts.

## 12.5 Full target-language AST / compiler frontend

Do not parse arbitrary C++ or Rust.

Keep the “minimal semantic lift” principle.

---

# 13. Proposed pre-v1.0 milestone order

## M1 — Freeze the pre-v1.0 identity

- [ ] Document “implementation-aware SIMD portability” as the pre-v1.0 thesis.
- [ ] Document non-goals.
- [ ] Freeze terminology: realization, origin, hazard, requirement, semantic guarantee, evidence, contract, certificate.

## M2 — Realization model

- [ ] Add typed realization model.
- [ ] Preserve compatibility projection to current implementation state.
- [ ] Add origin classification.
- [ ] Add initial hazard vocabulary.
- [ ] Add direct/transitive provenance.

## M3 — Closure propagation

- [ ] Propagate realization facts through exact live dependency graph.
- [ ] Preserve feature/safety/compiler-capability provenance.
- [ ] Add deterministic graph API.

## M4 — Semantic consolidation

- [ ] Finish arithmetic semantic coverage required for pre-v1.0.
- [ ] Add inactive-lane semantics.
- [ ] Add core representation/conversion semantics.
- [ ] Define raw-code -> unknown rules.

## M5 — C++/Rust realization parity

- [ ] Generated coarse realization query in both languages.
- [ ] Backend parity analysis.
- [ ] Shared semantic/value-test evidence.

## M6 — Capability certificate

- [ ] Versioned JSON schema.
- [ ] Deterministic certificate generation.
- [ ] Evidence taxonomy.
- [ ] Human-readable summary.

## M7 — Contracts

- [ ] Minimal contract schema.
- [ ] Post-closure checker.
- [ ] Exact failure path/provenance.
- [ ] Generated local assertion helpers.

## M8 — Regression ratchet

- [ ] Certificate/realization baseline.
- [ ] Detect implementation-quality regressions.
- [ ] CI integration.

## M9 — Explainability

- [ ] `tslc explain` realization view.
- [ ] `tslc analyze` graph/JSON view.
- [ ] Editor projections reuse compiler facts.

## M10 — Empirical evidence

- [ ] Run realization-aware selection experiment.
- [ ] Demonstrate at least one real API-availability/ISA-label blind spot.
- [ ] Measure false positives/false negatives of initial hazards.
- [ ] Refine hazard vocabulary only from evidence.

## M11 — pre-v1.0 stabilization

- [ ] Schema/versioning freeze.
- [ ] Migration notes.
- [ ] Full generated C++/Rust build gates.
- [ ] Cross-profile conformance matrix.
- [ ] Release artifact contains certificate + coverage/parity summary.
- [ ] Documentation positions TSL against existing SIMD libraries accurately.

---

# 14. pre-v1.0 release gates

A pre-v1.0 release should not happen until all of these are true.

## Correctness

- [ ] Generated C++ and Rust pass the supported build/value-test matrix.
- [ ] No unresolved dependency can appear in a successful contract-admitted slice.
- [ ] Semantic guarantees used by contracts are typed and tested.

## Realization

- [ ] Every emitted specialization has a realization state.
- [ ] Unknowns are explicit, never silently treated as native/composed.
- [ ] Hazard propagation has provenance.

## Contracts

- [ ] Contract checker fails closed deterministically.
- [ ] Exact violation paths are reported.
- [ ] Multi-profile and multi-backend contracts work.

## Evidence

- [ ] Certificate schema is versioned and deterministic.
- [ ] Build/test evidence is distinguished from semantic/compiler assertions.
- [ ] Regression ratchet runs in CI.

## Differentiation

- [ ] Documentation does not claim generator/runtime-dispatch/autotuning as unique.
- [ ] At least one empirical case shows why implementation-aware reasoning matters beyond ISA labels/API availability.
- [ ] Cross-language parity is demonstrated on a nontrivial primitive subset.

---

# 15. Research questions enabled by pre-v1.0

These are not all release blockers, but pre-v1.0 should make them answerable.

1. How often does API-level SIMD portability hide composed/fallback implementations?
2. How often do transitive dependencies introduce hidden fallback or additional ISA requirements?
3. Which structural hazards correlate with measured performance cliffs?
4. Can applications choose better algorithms from realization facts than from ISA names alone?
5. How often do C++ and Rust implementations diverge in semantics or realization despite sharing the same source corpus?
6. Can contracts prevent meaningful portability regressions without rejecting efficient compositions excessively?
7. Does contract-directed minimal generation materially reduce build time/package size/audit surface?
8. Does the semantic-corpus approach reduce the engineering cost of bringing up a genuinely different SIMD paradigm?

---

# 16. Short version: what belongs in pre-v1.0

If scope pressure becomes severe, keep these five things:

```text
1. implementation realization
   - origin
   - hazards
   - exact transitive dependencies
   - target/compiler requirements
   - semantics

2. portability contracts
   - fail closed on unacceptable realization
   - exact root-to-callee explanation

3. language-neutral semantic contracts
   - especially arithmetic, masks/inactive lanes, conversions/representations

4. capability certificate + regression ratchet
   - machine-readable, deterministic, evidence-aware

5. C++/Rust parity analysis
   - same capability/semantics, explicit realization differences
```

Everything else can follow.

---

# 17. One-sentence pre-v1.0 goal

> **TSL pre-v1.0 should let a systems developer express a SIMD capability once, generate native C++ and Rust implementations for multiple targets, inspect exactly how each specialization is realized, and fail the build when the transitive implementation or semantics fall outside the application's declared portability contract.**
