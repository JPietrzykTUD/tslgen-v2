# Portable Semantic Tests and Targeted Implementation Harness

## Status and intent

This document records the current problems and a proposed direction for value
tests authored under `tsldata/primitives/**/*.tsl`.

The central conclusion is:

> A primitive should normally have one architecture-independent semantic
> contract. Architecture-specific machinery is necessary to execute that
> contract on different representations and implementations, but
> architecture-specific expected behavior should be rare, explicit, and
> treated as a contract decision rather than an ordinary testing convenience.

The current corpus mixes two different responsibilities in the same `tests:`
blocks:

1. **semantic conformance** — whether a primitive satisfies its declared
   operation for a set of inputs; and
2. **implementation coverage** — whether a particular NEON, SVE, RVV, x86, or
   other specialization satisfies that shared operation.

That mixture explains many of the authored `extension "neon"`, `extension
"sve"`, and `extension "rvv"` cases. It also creates avoidable duplication and
occasionally conceals an underspecified primitive contract.

As of the current source snapshot, a textual inventory finds 41 NEON-pinned,
11 SVE-pinned, and 19 RVV-pinned authored cases. These counts are descriptive,
not acceptance criteria; a compiler-owned inventory should replace textual
counting before implementation work begins.

## Current model

An authored test becomes a typed `TestCase`. Its `extension` field is a
specific subject-extension selector, while `to_type` and `to_extension`
describe representation-change targets:

- [`tslc/src/tslc/catalog/model.py`](../tslc/src/tslc/catalog/model.py) owns the
  typed test case.
- [`tslc/src/tslc/catalog/test_cases.py`](../tslc/src/tslc/catalog/test_cases.py)
  owns stable case naming and lane-count inference.
- [`tslc/src/tslc/value_tests/planner.py`](../tslc/src/tslc/value_tests/planner.py)
  skips an extension-pinned case when that extension/type specialization is not
  selected.
- [`tslc/src/tslc/value_tests/case_helpers.py`](../tslc/src/tslc/value_tests/case_helpers.py)
  uses `extension`, `to_type`, and `to_extension` to find exact conversion and
  representation specializations.

Therefore, `extension "neon"` does not inherently mean “NEON has different
semantics.” It normally means “plan this case only where the NEON
specialization is present,” or “use NEON as the concrete source
representation.”

For ordinary fixed-lane cases, the generated golden test uses `generic<N>` as
the reference representation. For supported simple shapes, the planner also
derives hardware-versus-generic differential cases. The current machinery is
implemented primarily in:

- [`tslc/src/tslc/value_tests/_pattern_core.py`](../tslc/src/tslc/value_tests/_pattern_core.py);
- [`tslc/src/tslc/value_tests/_case_core.py`](../tslc/src/tslc/value_tests/_case_core.py);
- [`tslc/src/tslc/value_tests/_case_conversion.py`](../tslc/src/tslc/value_tests/_case_conversion.py);
- [`tslc/src/tslc/value_tests/_render_cpp_core.py`](../tslc/src/tslc/value_tests/_render_cpp_core.py);
- [`tslc/src/tslc/value_tests/_render_rust_core.py`](../tslc/src/tslc/value_tests/_render_rust_core.py).

This is already the beginning of the desired model: one semantic case can
produce a reference test and one or more specialization-conformance tests.
However, that expansion currently covers only a subset of signatures and
representations.

## Why target-specific cases currently exist

### 1. Exercising a distinct implementation body

Different extensions frequently implement the same operation with unrelated
intrinsics or TSIL compositions. A generic test proves the reference body; it
does not by itself prove that the NEON, RVV, or SVE implementation was selected
and executed.

For example, the NEON and RVV `ui64`/`si64` multiplication cases in
[`tsldata/primitives/arithmetic/complex.tsl`](../tsldata/primitives/arithmetic/complex.tsl)
use the same inputs and expected results. Their apparent purpose is
implementation coverage, not distinct semantics.

Ensuring that every implementation path is tested is necessary. Hand-copying
the semantic case for each implementation is generally not.

### 2. Fixed register width and explicit literal lane arrays

The current test language commonly authors complete literal vectors. A
128-bit `ui32` implementation has four lanes, a 256-bit implementation has
eight, and a 512-bit implementation has sixteen. Conversion operations may
also change the number of result lanes.

The current differential planner only instantiates a fixed-width hardware case
when the hardware lane count matches the authored case lane count. Consequently
one literal case often cannot cover 128-, 256-, and 512-bit implementations.

This is a limitation of the authored input/oracle representation, not evidence
that lane-wise arithmetic should have different semantics at different widths.

### 3. Runtime-scalable SVE and RVV vectors

SVE and RVV do not have one source-time vector length:

- SVE obtains its lane count from `svcntb() / sizeof(base_type)`;
- RVV obtains it from `__riscv_vlenb() / sizeof(base_type)`.

Their extension records provide backend-specific runtime-lane,
mask-construction, mask-check, and support-header facts in
[`tsldata/extensions/extension.tsl`](../tsldata/extensions/extension.tsl).

The value-test planner can tile an authored fixed-length pattern across the
runtime lane count when the primitive is lane-local. This is valid only when
output lane `i` depends solely on input lane `i`. The invariant is owned by:

- [`tslc/src/tslc/value_tests/lane_math.py`](../tslc/src/tslc/value_tests/lane_math.py);
- [`tslc/src/tslc/value_tests/lane_model.py`](../tslc/src/tslc/value_tests/lane_model.py);
- [`tslc/src/tslc/value_tests/_case_scalable_common.py`](../tslc/src/tslc/value_tests/_case_scalable_common.py).

Reductions, shuffles, compress/expand, conflicts, sequences, and other
cross-lane operations cannot be tested correctly by blindly repeating a short
pattern. They require a runtime-length oracle or a deliberately chosen concrete
vector-length configuration.

The scalable harness is therefore genuinely target-specific. The semantic
case usually need not be.

### 4. Native predicate and mask representation

Masks have different physical representations:

- a fixed-width lane bitmask;
- an AVX-512-style predicate scalar;
- an SVE `svbool_t`;
- an RVV predicate type selected by element width;
- an unpacked vector mask on some targets.

SVE predicates in particular cannot be checked as ordinary flat arrays. The
extension must supply a way to construct a mask from authored bits and a way to
check returned predicate bits.

For example, `mask_true` currently has:

- an SVE case with 16 authored lanes and expected integral bits `65535`;
- an RVV case with 4 authored lanes and expected integral bits `15`.

Both cases mean “all existing lanes are active.” The differing literal is
caused by lane count and representation, not a different logical operation.
This should be expressible as a lane-count-dependent oracle such as
`all_active`, instead of two manually calculated constants.

Representative source:

- [`tsldata/primitives/mask/construct.tsl`](../tsldata/primitives/mask/construct.tsl);
- [`tsldata/primitives/mask/bitwise.tsl`](../tsldata/primitives/mask/bitwise.tsl);
- [`tsldata/primitives/conversion/mask_specific.tsl`](../tsldata/primitives/conversion/mask_specific.tsl).

### 5. Representation-changing operations

Operations such as widening, narrowing, extraction, insertion, resizing, and
cross-extension conversion are parameterized by source and target
representations. Register widths determine:

- source and destination lane counts;
- which source or destination chunk an immediate index denotes;
- zero-filled or undefined regions;
- whether the selected specialization exists at all.

For these cases, a source extension or `to_extension` can be an operand of the
test rather than merely a request to exercise an implementation. Removing that
axis would remove part of the operation being tested.

The required axis should nevertheless be representation-oriented rather than
silently interpreted as permission for arbitrary ISA-dependent behavior.

### 6. Intrinsic-specific edge and regression coverage

Some tests are clearly aimed at implementation-sensitive edges:

- NEON bit-pattern shifts of floating-point registers using subnormal values;
- exact byte placement through multistep widening or narrowing;
- direct NEON horizontal reductions;
- RVV `ui64` bitwise and masked cases;
- saturation and cross-signed narrowing paths.

Such cases are useful when an intrinsic path has unique failure modes or
previously contained a bug. They should be marked as implementation regressions
with a reason. A bare architecture tag does not currently distinguish a known
regression from routine duplicated coverage.

### 7. Deliberately relaxed, backend-dependent semantics

Some primitive contracts currently permit different observable results across
backends. In those cases target-specific expected results may be genuinely
necessary, but the necessity exposes a semantic problem.

`convert_down` is the clearest example. Its documentation states that
saturation, clamping, rounding, and out-of-range behavior follow the selected
backend and type-conversion path:

- [`tsldata/primitives/conversion/repr_change.tsl`](../tsldata/primitives/conversion/repr_change.tsl).

Under that contract, the same primitive name does not provide one portable
meaning for out-of-range inputs.

Floating-point horizontal reductions are another partially relaxed case. Their
exact association follows the selected implementation, so different vector
widths or reduction trees can produce different rounding:

- [`tsldata/primitives/arithmetic/horizontal.tsl`](../tsldata/primitives/arithmetic/horizontal.tsl).

These differences must not be hidden as test-harness details. They should
become explicit semantic policies, distinct primitive operations, or clearly
documented relaxed guarantees.

## Problems in the current approach

### Semantic specification and implementation selection are conflated

The same record currently carries:

- the semantic inputs and oracle;
- a desired type and lane shape;
- an optional exact implementation extension;
- representation-change axes;
- tags that may describe behavior, coverage intent, or architecture.

This makes it difficult to answer whether a target pin is semantically
necessary or merely forces coverage.

### Architecture duplication obscures the real contract

Identical or near-identical input/expected pairs are repeated for multiple
extensions. Examples include:

- NEON and RVV multiplication edge cases;
- WASM and NEON cross-signed saturating `convert_down` cases;
- SVE and RVV mask logic expressed with different literal bit widths.

Duplicated expected values can drift independently. A future semantic change
may update one architecture and leave another silently inconsistent.

### Literal vectors do not describe reusable test intent

A full lane array answers “what are these 8 values?” but often fails to capture
the intended property:

- alternating active lanes;
- all lanes active;
- a ramp by lane index;
- signed extrema followed by ordinary values;
- values immediately below, at, and above a narrowing boundary;
- a repeating bit pattern;
- a zero divisor only in inactive lanes.

Without reusable pattern and oracle vocabulary, the corpus repeatedly encodes
the same idea at several widths.

### Generalized specialization coverage is incomplete

The compiler already emits generic golden, fixed-width differential, optional
fuzz-differential, and some scalable cases. It cannot yet automatically apply
one semantic case to every relevant shape:

- conversions and representation changes;
- many memory operations;
- cross-lane operations;
- all immediate and overload forms;
- runtime-scalable reductions and shuffles;
- every mask representation;
- backend-specific failure behavior.

Explicit extension cases partly compensate for those coverage gaps.

### Backend-dependent semantics weaken portability

If `primitive + semantic policy + inputs` does not determine one result or one
documented result class, TSL is exposing implementation behavior rather than
abstracting it.

The current `convert_down` contract is especially problematic. A user cannot
reason portably about saturation versus truncation from the primitive name and
arguments alone.

### Architecture tags do not explain why targeting is required

Tags such as `neon`, `rvv`, `direct`, or `edge` are useful labels but do not
record:

- a known regression identifier or failure mode;
- whether the case is a semantic exception;
- whether only the representation is target-specific;
- whether the pin is temporary pending generalized planner support;
- which implementation leaf or capability the case is intended to cover.

### The generic implementation is useful but not an infallible oracle

Differential comparison against `generic<N>` is powerful, but agreement with
the generic implementation alone is not proof of correctness. The generic and
hardware bodies can share a mistaken semantic assumption.

Authored expected values or an independent scalar/reference oracle must remain
the authority. Differential tests should amplify semantic cases, not replace
them.

### Broad slot counts are not semantic evidence

Compiling or executing every emitted specialization proves availability and
basic conformance only to the cases actually instantiated. It does not prove:

- complete edge-domain coverage;
- consistent floating-point exceptional behavior;
- correct inactive-lane behavior;
- correct lane ordering;
- mask-representation equivalence;
- correct runtime-VL behavior at several vector lengths.

Coverage reporting must distinguish implementation reachability from semantic
case adequacy.

## Desired testing model

The harness should separate three concepts.

### 1. Architecture-neutral semantic case

A semantic case describes:

- primitive contract or semantic operation;
- scalar type or type relation;
- semantic policy, when applicable;
- input pattern or concrete input values;
- expected values, expected relation, or independent oracle;
- comparison policy;
- applicable preconditions and failure behavior.

It should not normally name an ISA.

### 2. Instantiation policy

The compiler decides which compatible emitted specializations receive the
case. Eligibility should derive from typed facts:

- signature and parameter kinds;
- source and target type relationships;
- fixed versus scalable vector capability;
- mask representation capability;
- immediate and generic axes;
- backend renderer support;
- required harness primitives;
- selected profile and extension availability.

This is implementation coverage policy, not authored semantic behavior.

### 3. Explicit implementation regression

A targeted regression may name an extension when the target itself is the
subject of the test. It should also carry:

- a concise reason;
- the semantic case or property it refines;
- the implementation capability or edge being exercised;
- whether the pin is permanent or removable after planner support improves.

An architecture pin without such intent should be rejected by validation or at
least reported by a maintenance audit.

## Proposed capabilities

The following syntax is illustrative only. It is not current `.tsl` syntax and
must not be introduced without typed parser, catalog, validation, planning,
rendering, and coverage support.

### Reusable lane patterns

Potential architecture-neutral input patterns include:

- `repeat(value)`;
- `cycle(values...)`;
- `ramp(start, step)`;
- `alternating(a, b)`;
- `lane_index`;
- `edge_values(type)`;
- `narrowing_boundaries(source_type, target_type)`;
- `mask_all`;
- `mask_none`;
- `mask_alternating`;
- `mask_first`, `mask_last`, and chosen-density patterns.

The planner would materialize the pattern for the concrete fixed lane count or
runtime vector length.

### Computed semantic oracles

Extend the existing `expected_rule` idea with typed, operation-owned oracles,
for example:

- `all_active`;
- `all_inactive`;
- lane-wise arithmetic or bitwise evaluation;
- saturating or truncating conversion;
- scalar reference reduction over the actual runtime lane count;
- mask population and mask-to-vector conversion;
- stable lane permutation from an index rule;
- expected failure predicates.

The oracle must be independent of the implementation under test. Backend
renderers should format an already planned oracle, not decide its semantics.

### Automatic compatible-specialization expansion

One semantic case should expand across every selected compatible specialization
unless the case explicitly narrows its applicability.

For fixed-width targets, the planner should materialize inputs for the target
lane count and compare the concrete implementation against the authored or
computed oracle.

For scalable targets, it should query runtime lanes and materialize the same
semantic pattern at runtime.

The expansion report should state why a case was:

- emitted;
- inapplicable;
- blocked by missing harness capability;
- intentionally excluded;
- pinned as an implementation regression.

### Runtime-length cross-lane references

Cross-lane operations cannot use simple tiling. Their scalable tests need
reference algorithms over the actual runtime lane count:

- reductions iterate over all runtime lanes with the declared arithmetic
  policy;
- compress/expand derive positions from the runtime mask;
- conflict detection uses all prior runtime lanes;
- permutations compute expected source indices;
- sequence/iota derives expected values from the runtime lane index.

This is more work than lane-local tiling, but it is the correct way to test SVE
and RVV without fixing one arbitrary vector length.

### Explicit semantic policies

Operations whose results currently follow the selected backend should gain
portable policy vocabulary or be split into distinct operations.

For narrowing, plausible semantic operations include:

- truncating narrowing;
- saturating narrowing;
- rounding narrowing with an explicit rounding mode;
- checked narrowing with an explicit failure contract.

For floating reductions, distinguish at least:

- relaxed/backend-associated reduction;
- reproducible fixed-association reduction, if the project chooses to support
  it.

Tests should bind to the semantic policy. Implementations should be admitted
only when they satisfy it.

### Semantic coverage matrix

Add a compiler-owned report keyed by at least:

- source primitive and emitted operation;
- semantic policy;
- backend and profile;
- extension and type;
- fixed or scalable lane model;
- mask policy;
- conversion target;
- authored case/property;
- planning and execution status.

The report should distinguish:

- semantic case missing;
- semantic case exists but no concrete instantiation;
- concrete instantiation generated;
- generated case compiled;
- generated case executed;
- targeted regression only;
- unsupported harness shape.

## Rules for retaining an explicit extension pin

An authored `extension` selector is justified when at least one of the
following is true:

1. the source or target representation is an explicit operand of the
   operation;
2. the case is a documented regression for one specialization;
3. the extension exposes a semantic policy not shared by other
   implementations, pending contract normalization;
4. the case requires target-specific behavior that cannot yet be expressed by
   typed test capabilities, and the pin is marked as temporary;
5. the test checks a target ABI, representation, intrinsic precondition, or
   compile-time capability rather than the portable primitive result.

An extension pin is not justified merely because:

- an implementation is written with different intrinsics;
- the register contains a different number of lanes;
- SVE or RVV determines lane count at runtime;
- the author wants to ensure broad implementation coverage;
- copying an existing literal case is easier than extending the planner.

Those concerns should normally be handled by automatic instantiation and
target-owned harness facts.

## Prioritized implementation plan

### Phase 0: inventory and classification

Add a read-only maintenance report over typed catalog cases. For every explicit
extension selector, classify or report:

- representation operand;
- implementation regression;
- relaxed semantic exception;
- planner/harness workaround;
- unexplained pin.

Do not infer classifications from tags alone. Initially allow an explicit
source field or a reviewed side classification until the source vocabulary is
settled.

Acceptance criteria:

- every current extension-pinned case appears exactly once;
- the report links each case to compatible emitted specialization slots;
- unexplained and duplicate pins are visible;
- no source or generated artifact is changed by the report.

### Phase 1: low-effort deduplication

Start with cases whose semantic data are already identical:

- NEON/RVV multiplication edges;
- WASM/NEON cross-signed narrowing cases where the promised policy is
  identical;
- repeated fixed-width mask logic patterns;
- width-only all-true/all-false mask constants.

Before deleting any targeted case, prove that the generalized case is emitted
and executed for every previously covered specialization.

Potential small capabilities:

- allow one semantic case to request all compatible implementations;
- add `all_active`/`all_inactive` computed mask oracles;
- add `cycle`/`alternating` lane patterns;
- emit coverage diagnostics when a formerly covered target loses its case.

### Phase 2: broaden generated differential cases

Extend the existing generic-versus-hardware machinery to additional typed
shapes:

- immediate operations;
- scalar-result operations where an independent expected oracle exists;
- mask constants, mask logic, and conversions;
- memory operations with explicit safe buffers;
- fixed-width representation changes.

Do not use the generic implementation as the sole oracle. Each differential
case must remain linked to an authored or independently computed semantic
expectation.

### Phase 3: scalable semantic instantiation

Generalize SVE and RVV lane-local cases using runtime materialization:

- input patterns are generated for runtime lanes;
- mask patterns are generated through extension capabilities;
- value and mask results use the same architecture-neutral oracle;
- several available vector-length configurations are exercised where CI
  runners support them.

Preserve target-owned runtime-lane and predicate conversion templates; remove
duplicated semantic literals where they no longer add coverage.

### Phase 4: runtime cross-lane oracles

Implement typed reference plans for reductions, shuffles, compress/expand,
conflict detection, and other `cross_lane` operations.

The planner must reject unsound tiling and report a clear unsupported reason
until the relevant reference shape exists.

### Phase 5: normalize weak primitive contracts

Audit every primitive whose documentation permits backend-dependent observable
results. Begin with:

- `convert_down`;
- floating horizontal reductions;
- floating min/max and NaN/signed-zero behavior;
- conversions with rounding, saturation, or out-of-range ambiguity.

For each primitive:

1. define explicit semantic alternatives;
2. assign each implementation to an alternative;
3. split or parameterize the public operation;
4. attach shared semantic tests to each alternative;
5. retain a relaxed operation only if its value is intentional and documented.

This phase is not merely test cleanup. It changes the portability contract and
requires separate review.

## Acceptance criteria for the end state

1. Every non-relaxed primitive/policy has one architecture-independent
   observable contract.
2. Every emitted compatible specialization receives at least one semantic
   conformance instantiation or a structured exclusion reason.
3. A fixed-width change does not require copying a complete test vector solely
   to alter lane count.
4. Lane-local cases execute on runtime-scalable targets without authored
   SVE/RVV duplicates.
5. Cross-lane scalable cases use runtime-length reference logic and are never
   tested by unsound pattern tiling.
6. Mask tests describe logical lane activity independently of native predicate
   representation.
7. Representation-change cases retain source/target representation axes without
   using those axes as implicit semantic policies.
8. Every explicit extension pin has a machine-readable justification.
9. Generic-versus-hardware differential tests remain connected to an
   independent semantic oracle.
10. Coverage reports distinguish authored semantic coverage, generated
    instantiation, compilation, and execution.
11. CI runs the relevant generated tests on the required native runner or
    emulator and reports unavailable execution explicitly.
12. No backend renderer infers semantic expectations from an extension name,
    primitive name, intrinsic spelling, or implementation text.

## Non-goals

- Do not require every specialization to have unique hand-authored inputs.
- Do not pretend that compiling a specialization proves value correctness.
- Do not erase target-specific ABI, feature, representation, runner, or
  toolchain requirements.
- Do not generalize cross-lane scalable tests by repeating fixed-size expected
  arrays.
- Do not silently normalize a deliberately relaxed primitive in the test
  renderer.
- Do not introduce raw C++ or Rust expressions into semantic test data.
- Do not remove regression cases until equivalent target coverage is proven.

## Principal risks

- Automatic expansion can create an impractically large test matrix. The
  planner will need semantic equivalence classes and explicit CI coverage
  policy without weakening the contract.
- A generated scalar oracle can reproduce the same mistaken specification as
  the implementation. Important edges still need reviewed concrete examples.
- Floating-point comparisons require explicit policy for NaNs, signed zero,
  infinities, tolerance, and exact-bit checks.
- Runtime-scalable CI may exercise only one emulated vector length unless the
  runner matrix deliberately varies it.
- Representation-change generalization can accidentally compare operations
  with different lane-placement or saturation policies.
- Removing extension pins without coverage accounting can silently stop
  exercising an implementation body.

The migration must therefore be coverage-preserving first and
duplication-reducing second.
