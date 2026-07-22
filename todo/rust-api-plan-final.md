# Rust API Facade Implementation Plan

## Status and authority

This plan implements the public contract settled in
`todo/rust-api-plan.md`. That file remains the product authority if this
implementation plan is ambiguous. This document orders the work, assigns
ownership, names review gates, and defines completion evidence; it does not
reopen the settled API.

The feature is a compiler-owned Rust projection over TSL. It is not a second
SIMD implementation layer:

- `tsldata` owns operations, exact behavior, operand roles, overload meaning,
  safety, implementations, tests, and availability;
- compiler core owns typed promotion, validation, selection, lowering, and
  propagation of those facts;
- compiler-owned authoring services project the same typed source vocabulary to
  the editor;
- the Rust backend owns Rust spelling, ownership adaptation, public type
  presentation, packaging, and algorithm-level dispatch presentation;
- templates format a finalized render model and make no semantic decisions.

Every new source primitive or contract is delivered and verified through the
ordinary generated C++ and lower-level Rust primitive APIs before the Rust
facade consumes it. A facade wrapper may perform Rust boundary work such as a
length or bounds check, ownership forwarding, a scalar reduction check, or
logical formatting. It may not implement a lane algorithm, arithmetic edge
case, shift-count rule, conversion rule, mask representation, primitive
selection rule, or ISA recipe.

## Goal and completion criteria

Generate one pre-generated, warning-free, sound Cargo library whose ordinary
surface uses logical values:

```rust
use tsl::{Mask, NativeMask, NativeSimd, Simd};

let a = Simd::<i32, 8>::from_slice(&left);
let b = Simd::<i32, 8>::from_slice(&right);
let sum = a + b;
sum.copy_to_slice(&mut output);
```

The work is complete when:

1. the generated Rust contains no invalid values, unconstrained safe bit casts,
   unsealed representation contracts, or executable unsupported instructions;
2. `Simd<T, N>`, `Mask<T, N>`, native aliases, the curated Rust traits and
   methods, and comprehensive coherent primitive methods match the settled
   contract;
3. a default consumer gets a `no_std` generic fallback with no profile/ISA
   Cargo feature and never runs `tslc`;
4. compile-target features select an exact generated hardware mapping when one
   is valid, without changing the public value type at runtime;
5. optional runtime dispatch selects whole-algorithm entry points once and
   never leaks profile vector types into public signatures;
6. facade eligibility, names, and delegates are derived only from typed source
   and compiler facts;
7. external-consumer, compile-failure, value, warning, rustdoc, and dispatch
   tests cover the public contract.

## Fixed scope

### In scope

- correcting the current generated Rust safety and warning defects;
- projection-neutral source contracts and primitives required by the facade;
- corresponding catalog, validation, lowering, value-test, and editor support;
- a typed Rust facade planning and validation stage;
- logical fixed and fixed-native public values and masks;
- static compile-target selection with a generic fallback;
- the settled curated methods, standard traits, comprehensive primitive
  methods, package layout, and optional algorithm-level dispatch;
- preserving the existing lower-level generated primitive API.

### Out of scope

- scalable or runtime-sized native vector values;
- a stable representation, ABI, serialization, transmute, or direct FFI
  promise for vectors or masks;
- composed fixed values made from multiple narrower hardware registers;
- per-vector or per-operation runtime dispatch;
- profile/ISA Cargo features;
- a Rust facade alias for every TSL primitive;
- `Index`, `IndexMut`, slice-reference views, iteration, hashing, vector
  ordering, fallible slice methods, or aligned raw-pointer methods;
- changing the C++ facade merely to resemble Rust;
- parsing or rewriting raw C++, Rust, intrinsic, or TSIL body text to infer API
  semantics;
- removing or redesigning the current lower-level generated primitive entry
  points unless a separately reviewed soundness correction requires it.

## Pre-implementation findings and guardrails

There is no remaining public-API decision gate. The following implementation
risks must nevertheless be resolved in the named slices.

1. **The current Rust package selects profiles with mutually exclusive Cargo
   features.** `render/rust_project.py`, its Cargo/lib templates, the verifier,
   compile-failure cases, and benchmarks currently rely on that model. Static
   target selection must replace it as one coordinated slice; do not leave two
   profile-selection mechanisms active.
2. **The current dataparallel facade recognizes `load` and `store` by primitive
   name.** Do not extend that classifier for the new value facade. Migrate the
   affected behavior to typed memory/operand facts before reusing it, or keep
   the old algorithm facade isolated until it can be migrated safely.
3. **The implemented overload model currently stops at `Catalog`.** Resolve it
   through `Catalog.resolve_primitive_overload(...)` and carry
   `ResolvedPrimitiveOverload | None` through lowering before facade naming.
4. **Source prose is not semantic input.** Existing `semantics` and description
   text may document behavior, but facade planning may consume only typed,
   validated contracts.
5. **Not every curated operation has all required typed source facts yet.** Add
   the smallest language-neutral contracts needed by an actual source family;
   do not introduce a Rust-specific `operator`, `method_name`, or `facade`
   field in `tsldata`.
6. **Runtime dispatch crosses Rust monomorphization and target-feature
   boundaries.** Prove one binary built-in and one stateful operation through a
   generic and hardware entry point before generating the full dispatch
   surface. Do not solve a failed prototype with `Any`, heap allocation,
   runtime vector enums, or erased public vector storage.
7. **The root `tsl_core.rs` currently exposes representation machinery.** The
   new root `Simd<T, N>` may wrap existing lower-level machinery, but private
   storage and sealed public bounds must not leak an extension tag or permit a
   downstream representation implementation.

## Canonical compiler data flow

```text
tsldata primitive declarations and implementations
                |
                v
typed Catalog contracts and source spans
        |                       |
        |                       +--> compiler-owned authoring/LSP facts
        v
SelectedImplementation
        |
        v
LoweredSpecialization + resolved semantic facts
        |
        v
RustFacadePlan + RustStaticSelectionPlan + RustDispatchPlan
        |
        v
render models and templates
        |
        v
one generated Cargo package
```

The Rust planners may map a language-neutral enum to a Rust spelling, such as
`per_lane -> _each` or arithmetic addition to `core::ops::Add`. They may not
map a primitive name to meaning. Raw implementation text remains opaque at
every planning boundary.

## Required typed facts

Before facade planning, the compiler must be able to answer the following from
typed objects. Extend existing owners where they fit; add a small focused
contract where they do not. Do not create one catch-all facade metadata record
in source data.

| Question | Typed owner |
| --- | --- |
| What operation and exact guarantees does this declaration provide? | Existing arithmetic contract for arithmetic; focused language-neutral operation contracts for comparison, bitwise, mask, memory, or conversion behavior actually consumed by the facade |
| Which operand is the primary logical value, control mask, pass-through value, destination, source, count, or conversion target? | Source-authored operand-role bindings validated against the typed signature |
| Which sibling is uniform, immediate, per-lane, vector-payload, or scalar-payload? | Existing source-owned overload registry and resolved primitive overload |
| Is the call safe for the caller and what preconditions survive? | Existing implementation/caller safety model and source safety contracts |
| Does the operation preserve lane count or target another logical vector? | Typed conversion/result-target contract, including an explicit target SIMD type and lane relation |
| Is there a generic baseline and which hardware specializations are valid? | Selection/lowering and emitted-profile facts, never source-name inference |
| Which fixed logical shapes exist? | Source-authored fixed extension/profile widths plus scalar type widths |
| Which scalar count types are admitted? | Typed signature/count capability owned by the wrapping-shift source family |

If a required answer is absent, stop that facade item and add a
projection-neutral source/compiler slice. Do not compensate in the Rust
planner.

## Implementation slices

Each slice below is independently reviewable and must pass its acceptance gate
before the next dependent slice starts. Source, compiler, editor, and backend
changes may cross directories when they deliver the single named outcome.

### Slice 1 — establish Rust safety and warning gates

**Outcome:** current defects fail deterministically before later facade code can
hide them.

1. Add focused generated-project checks for:
   - compiler warnings;
   - rustdoc warnings;
   - the selected Clippy safety/correctness groups;
   - invalid-value diagnostics;
   - target-feature/profile mismatches;
   - private-interface and unsealed representation warnings.
2. Keep `#![deny(warnings)]` out of the distributed crate. CI/verifier commands
   apply `-D warnings`; generated source carries only narrow, documented lint
   attributes required by generated naming or unreachable profile code.
3. Remove broad crate-level `allow(dead_code)`, `allow(non_camel_case_types)`,
   and similar suppressions only after generator-owned warnings have focused
   fixes or item-level justification.
4. Extend Rust verifier command-model tests before changing command execution.
   A missing optional Clippy component is a recorded verification gap, not a
   silent pass.
5. Add one minimal external-consumer fixture now; later slices grow it rather
   than relying only on generated crate-internal tests.

**Likely owners:** `output/_verify_rust*.py`, `render/rust_project.py`, Rust
assets/templates, `test_build_verify*.py`, `test_profile_rendering.py`, and a
new focused Rust consumer test module.

**Acceptance:** a deliberately warned, invalid-value, or unguarded fixture
fails the intended gate, while the unchanged generated baseline reports all
current failures explicitly.

### Slice 2 — remove invalid uninitialized values

**Outcome:** no generated safe or unsafe Rust creates an invalid initialized
value merely as temporary storage.

1. Inventory `uninitialized`, zeroed placeholders, `assume_init`, `set_undef`,
   deferred output buffers, and generated test scratch values.
2. Represent deferred storage as `MaybeUninit<T>` until every path initializes
   it. Keep initialization state local and obvious; do not add a general
   typestate framework.
3. Give `set_undef` a valid Rust contract. If its TSL meaning cannot produce a
   valid Rust value for all admitted types, keep it internal/unsafe or reject
   that specialization rather than pretending it is safe.
4. Prove initialization on ordinary return, early return, variant bodies, and
   failure/panic paths. Avoid reading or dropping uninitialized storage.
5. Add generated build/value tests for generic and one hardware profile.

**Acceptance:** invalid-value lints are clean, no unconstrained
`MaybeUninit::assume_init` remains, and focused behavior tests still match the
source primitive.

### Slice 3 — constrain bit reinterpretation and seal representation traits

**Outcome:** downstream Rust cannot invoke an unsound arbitrary bit cast or
implement a trait whose hidden invariants the compiler relies on.

1. Remove the safe unconstrained public `bit_cast` from `tsl_core.rs`.
2. Model compiler-proven reinterpretation pairs explicitly and keep their
   helper private or `pub(crate)`. Check equal size and valid-bit-pattern
   requirements at the typed backend boundary, not with a generic transmute
   promise.
3. Expose only settled same-width `to_bits`/`from_bits` facade pairs later;
   existing lower-level general reinterpretation keeps its current explicit
   safety boundary.
4. Seal `SimdVector`, static-vector, rebinding, mask-layout, supported-shape,
   and native-element traits wherever compiler-generated implementations rely
   on representation invariants. Public traits used as bounds may remain
   nameable, but downstream implementations must be impossible.
5. Remove public associated items that reveal register, mask, alignment, or
   extension layout unless the lower-level API already requires them; keep such
   compatibility items out of the ordinary root facade and rustdoc.
6. Add compile-failure tests for downstream trait implementations and invalid
   bit-cast pairs.

**Acceptance:** Miri is not required as proof, but all unsafe blocks have a
local invariant, compile-failure probes prevent downstream invariant forgery,
and public rustdoc makes no stable-layout claim.

### Slice 4 — replace profile features with a safe compile-target contract

**Outcome:** one compiled artifact has one static representation mapping, uses
an exact hardware specialization only when rustc is compiling for it, and
otherwise uses `Generic<N>`.

1. Add a frozen `RustStaticSelectionPlan` (or equivalently focused typed model)
   built from emitted profiles, target-family capabilities, extension widths,
   scalar widths, required target features, and generic coverage.
2. Validate every hardware candidate against the Rust target architecture and
   feature spellings before rendering. Reject impossible or ambiguous mappings
   with source/profile diagnostics.
3. Rank only source-declared compatible profiles. For each admitted `(T, N)`,
   select one exact-width hardware representation or the exact generic
   baseline; never synthesize multiple narrower registers.
4. Generate compile-time cfg predicates from typed target facts. A build script
   may translate Cargo-provided target architecture/features into one generated
   profile cfg, but it performs no host CPU detection and contains no profile
   name heuristics.
5. Gate every intrinsic-bearing module and call with the same finalized target
   requirement. An unsupported function may be compiled behind a target
   feature or retained only as an unsafe lower-level target-feature function;
   it is never reachable from the safe facade on an unsupported target.
6. Remove profile/ISA Cargo features and the current default-profile feature
   selection. Adapt verifier, benchmark, value-test, and compile-failure
   planning to pass compiler target settings instead.
7. Test target configurations as compile-only when the executing CPU is not
   known to support them. Runtime value tests use an injected runner/emulator or
   report a skip.

**Acceptance:** default target compilation chooses generic, an AVX2 compile
target chooses the exact AVX2 mapping where source coverage exists, a target
with only SSE/NEON does not enter AVX2, and an admitted unsupported-width shape
falls back to `Generic<N>` rather than failing or composing registers.

### Slice 5 — make the lower-level generated Rust warning-clean

**Outcome:** the existing primitive API passes the gates before the new facade
adds more generated code.

1. Fix warnings at the backend/model/template that creates them.
2. Add `#[must_use]`, `#[inline]`, `#[track_caller]`, safety comments, and
   rustdoc only where the current lower-level contract justifies them; do not
   bulk-annotate all generated items.
3. Keep narrow allowances beside the generated construct that needs them and
   document the generator invariant.
4. Run generic plus representative hardware generated builds and rustdoc.

**Acceptance:** the current lower-level crate is compiler-, rustdoc-, and
selected-Clippy-clean under the external gates, with no broad new suppression.

### Slice 6 — complete source semantic ownership and editor projection

**Outcome:** every fact used to admit or spell a curated Rust item has a
language-neutral source owner, a typed compiler model, validation, and editor
support.

1. Inventory curated operations against the required-facts table above. Reuse
   existing typed arithmetic, overload, safety, mask-policy, attributes, and
   result-target models.
2. Add only missing domain facts, in small contracts:
   - explicit operation identity and applicable guarantees;
   - operand-role bindings, including primary vector, control mask,
     pass-through, memory source/destination, and count where needed;
   - memory access/payload meaning not already expressed by typed attributes and
     `payload_extent`;
   - conversion kind, target-vector relation, and lane-count guarantee.
3. In the current corpus, explicitly cover the curated families: wrapping
   integer add/sub/mul; the existing division/remainder contracts; comparison;
   mask logic/reduction; selection; shifts; lane access; contiguous memory; and
   lane-preserving/bit-pattern conversion. This is an annotation and validation
   inventory, not permission to restate implementations in metadata.
4. Validate role names against actual signature positions and kinds, validate
   same-name family consistency, and retain source spans. Do not infer a role
   from being “the first `v`” or from a parameter name.
5. Extend semantic enum descriptions, catalog indexing, CLI/dump projection,
   completion, hover, navigation/references, semantic tokens, and diagnostics
   from the same compiler-owned records. The TypeScript client remains a thin
   protocol renderer and receives no duplicate vocabulary.
6. Add a synthetic rename probe: change a primitive name while preserving its
   typed operation/roles and prove that the typed projection is unchanged.
7. Add an additive unknown-operation probe: an ordinary representable primitive
   may still receive a comprehensive method, but no curated Rust trait appears
   unless a known typed operation authorizes it.

**Likely owners:** focused modules under `catalog/`, builder/schema/invariant
modules, `catalog_index.py`, `authoring_completion.py`, LSP tests, and relevant
`tsldata/primitives/**` declarations. Avoid expanding
`backend/primitive_facade.py` during this slice.

**Acceptance:** batch `tslc check` and editor diagnostics agree; editor
completion/hover derives from compiler enums; no primitive-name, parameter-name,
documentation, or target-text classifier exists.

### Slice 7 — carry resolved source facts through lowering

**Outcome:** the Rust backend receives finalized semantic facts without
reopening the catalog or reconstructing declarations.

1. Resolve `Primitive.overload` through
   `Catalog.resolve_primitive_overload(...)` while lowering the selected
   declaration.
2. Add `ResolvedPrimitiveOverload | None` and the minimal typed semantic
   contracts needed by the facade to `LoweredSpecialization`, or to one focused
   backend-neutral lowered semantic record referenced by it.
3. Preserve those fields through specialization replacement, variant handling,
   dependency closure, grouping, documentation planning, and test/benchmark
   projections.
4. Do not copy the overload registry into lowering. Carry only the resolved
   declaration fact.
5. Dump the carried values in the lowered debug stage so source authors can
   inspect them.

**Acceptance:** uniform runtime, uniform immediate, masked uniform, per-lane,
vector-payload, and scalar-payload fixtures retain the correct resolved fact;
changing raw target text does not change it.

### Slice 8 — normalize the source selection primitive

**Outcome:** active-lane selection has the settled language-neutral spelling and
argument order before the Rust method is generated.

1. Replace the current `blend(mask, false_values, true_values)` declaration
   with `select(mask, true_values, false_values)` so an active lane selects the
   first value operand.
2. Update source descriptions, typed operand roles, implementations, TSIL call
   sites, dependency resolution, tests, and lower-level generated C++/Rust
   calls together. Do not compensate by reversing arguments in either backend.
3. Treat this as a source primitive contract migration, not a Rust alias. If a
   compatibility alias is required for an already published lower-level API,
   make it an explicit source-level forwarding primitive with a deprecation
   plan; do not retain two semantic owners indefinitely.
4. Add asymmetric lane values and all-false/all-true/mixed masks so an argument
   reversal cannot pass accidentally.

**Acceptance:** ordinary C++ and Rust primitive tests prove the new order, all
typed dependencies call `select` in that order, and no Rust facade/backend
argument flip exists.

### Slice 9 — add and verify target-independent negation

**Outcome:** `neg` is a normal TSL primitive whose ordinary C++ and Rust APIs
own all negation behavior.

1. Add the `neg` primitive and typed operation/guarantee contract for signed
   integers and floating types.
2. Provide a generic baseline. Add hardware implementations only where they are
   exact optimizations of the same contract.
3. Specify and test signed wrapping `MIN -> MIN` and floating sign-bit toggle,
   including signed zero, infinities, and preserved NaN payload bits.
4. Reject unsigned types through normal source/type selection rather than a
   Rust facade condition.
5. Complete source documentation and value tests before exposing `Neg`.

**Acceptance:** generic and representative hardware C++/Rust primitive value
tests agree bit-for-bit on the edge corpus.

### Slice 10 — add and verify wrapping shifts

**Outcome:** Rust shift operators can delegate without normalizing counts in
the facade.

1. Add `shift_left_wrapping` and `shift_right_wrapping` source families for
   uniform and per-lane counts; add immediate forms only if the settled source
   vocabulary requires them outside operators.
2. Reuse the source-owned `count_distribution` overload axis and primary
   resolution.
3. Model supported scalar count types explicitly in the typed signature/count
   capability. Do not hard-code the Rust scalar vocabulary in the facade.
4. Specify effective count as the unsigned count bit pattern modulo lane width,
   including negative signed counts; specify signed arithmetic right shift and
   unsigned logical right shift.
5. Keep existing zeroing large-count `shift_left`/`shift_right` primitives and
   comprehensive method names unchanged.
6. Add generic and hardware value cases for zero, width-1, width, width+1,
   negative signed counts, very large counts, and per-lane mixtures.

**Acceptance:** both generated primitive backends pass; generated Rust operator
wrappers are not yet involved and no backend helper normalizes a count.

### Slice 11 — add runtime lane and mask mutation primitives

**Outcome:** runtime observation/mutation has a target-independent primitive
owner.

1. Add `extract_value_at(data, index)` and
   `insert_value_at(data, index, value)` while preserving the compile-time
   `extract_value`/`insert_value` family.
2. Add value-returning `set_mask_lane(mask, index, value)`.
3. Define valid-index behavior in source. Bounds checking and Rust panic
   presentation belong to the facade; the primitive is called only after the
   check.
4. Reuse existing integral-mask and `test_imask` contracts for mask testing;
   add a source primitive only if the existing typed contracts cannot express
   a representation-independent logical lane test.
5. Verify first/last lanes, all supported element widths, true/false mask
   mutation, and generic/hardware equivalence.

**Acceptance:** C++ and lower-level Rust generated APIs build and pass value
tests for all three new primitives before `lane`, `set_lane`, or `Mask::set`
is emitted.

### Slice 12 — add lane-preserving numeric conversion

**Outcome:** `convert_lanes` owns the exact per-lane contract needed by
`Simd::cast::<U>()`.

1. Extend the source/compiler result model to identify an explicit target SIMD
   type, not merely a target base type under the source extension.
2. Validate equal logical lane counts and admitted source/target shapes before
   lowering. Add the minimal backend capability for spelling the target vector.
3. Add a generic `convert_lanes` implementation plus exact hardware
   specializations where available.
4. Encode the settled scalar-`as`-equivalent rules in source contracts and
   tests: integer truncation/extension, integer/float rounding, saturating
   truncating float-to-integer conversion, and `NaN -> 0`.
5. Keep the existing register-width `cast` behavior and public lower-level name
   separate.
6. Extend value-test planning/rendering only for this proven target-vector
   shape; do not add a general conversion framework.

**Acceptance:** C++ and Rust generated primitive tests cover boundary values,
NaN/infinity, lane-count rejection, and generic/hardware equivalence.

### Slice 13 — introduce the typed Rust facade planner

**Outcome:** the compiler can finalize the ordinary Rust API and diagnose it
without rendering Rust text.

1. Add small frozen backend records, for example:
   - admitted logical vector/mask shapes and their selected representations;
   - finalized method/free-function receiver and parameter placement;
   - finalized curated trait implementation;
   - finalized comprehensive primitive method;
   - native alias and operation value;
   - public name, safety, documentation, cfg, and delegate identity.
2. Build the plan from lowered semantic facts, generic/hardware availability,
   fixed-shape facts, and the static selection plan.
3. Finalize receiver placement before naming. A control mask remains explicit;
   the source-authored primary vector becomes `self`; pass-through and
   destination roles retain their validated meaning.
4. Finalize names once in the settled order: overload (`_each`), immediate
   (`_imm`), then mask policy (`_masked`/`_masked_zero`). The primary uniform
   overload has no suffix.
5. Map known semantic operations to Rust traits/methods by enum, never by
   primitive name. Curated names are reserved before comprehensive method
   names are admitted.
6. Admit a comprehensive inherent method only when it has a coherent receiver,
   representable Rust signature, generic baseline, and preserved safety
   contract. Hardware-only primitives remain lower-level.
7. Reject before rendering:
   - missing source prerequisites or generic baselines;
   - unresolved/unknown overload values;
   - invalid role/signature combinations;
   - unsafe/safe mismatches;
   - unsupported target or target-vector shapes;
   - duplicate public names after suffix composition;
   - curated/comprehensive collisions.
8. Have Rust source, rustdoc, external-consumer fixtures, benchmarks, and
   dispatch planning consume the same finalized records.

**Likely owners:** new focused modules such as `backend/rust_api_model.py` and
`backend/rust_api_planner.py`, with validation routed from
`backend/rust_validation.py`. Keep rendering out of the planner and avoid
turning `backend/rust.py` into another catch-all.

**Acceptance:** model tests cover every naming combination, receiver shape,
safety class, missing-baseline rejection, collision, rename probe, and additive
unknown primitive. No generated source is required for planner tests.

### Slice 14 — render the crate root, package, and logical owned types

**Outcome:** an external crate can name and move supported logical values
without importing an extension or profile.

1. Render `#![no_std]` unconditionally and expose from the crate root:
   `Simd`, `Mask`, `NativeSimd`, `NativeMask`, `SimdElement`, and
   `SupportedSimd`.
2. Implement opaque owned `Simd<T, N>` and `Mask<T, N>` over the statically
   selected private representation. Keep extension tags, register types, and
   layout traits under the lower-level/detail modules.
3. Generate sealed `SupportedSimd<N>` implementations only for `N == 1` or
   source-authored fixed 128/256/512-bit shapes. Generate sealed
   `SimdElement`/native mappings only for fixed native profiles.
4. Ensure the public representation type is well formed under every cfg:
   exactly one selected hardware representation or exact generic fallback.
5. Derive or implement `Copy`, `Clone`, `Unpin`, `Send`, `Sync`, and `'static`
   only when the private representation naturally supports them. Add no manual
   unsafe auto-trait implementations.
6. Replace the generated manifest feature layout with exactly the ordinary
   additive surface:

   ```toml
   [features]
   default = []
   std = []
   runtime-dispatch = ["std"]
   ```

   Test/benchmark-only switches must not masquerade as ISA/profile features;
   use test cfgs, unpublished verification artifacts, or verifier-owned
   compiler cfgs as appropriate.
7. Add typed release configuration for package name/version, edition,
   `rust-version`, license, repository, documentation URL, and README. Do not
   hard-code repository-local release facts in a template.
8. Preserve the existing generated primitive modules and entry points; the new
   root facade is additive.

**Acceptance:** an external `no_std` consumer compiles `Simd<T, N>` generic
bounds, unsupported shapes fail at compile time, profile/extension names do not
appear in ordinary signatures or docs, and `cargo package` contains generated
sources without any `tslc` build dependency.

### Slice 15 — render construction, observation, masks, and memory

**Outcome:** the core logical-value API is usable without raw extension types.

1. Generate vector construction/observation:
   - `LANES`, `splat`, `from_array`, `to_array`, `lane`, `set_lane`;
   - array `From` conversions;
   - logical `Debug`, zero `Default`, whole-vector `PartialEq`, and integer
     `Eq`.
2. Generate mask construction/observation:
   - `splat`, `from_array`, `to_array`, `test`, `set`, `any`, `all`,
     `count_ones`, `from_bitmask`, `to_bitmask`, equal-lane `cast`;
   - logical mask traits and mask bit operators.
   Native mask conversion is emitted only when the resolved source and target
   lane counts are equal.
3. Keep bit `i` to lane `i` and high-bit clearing behavior owned by the typed
   mask/bitmask source contract. Rust bool-array packing may be scalar boundary
   adaptation, but it must delegate mask creation/observation to those source
   primitives and may not inspect private mask storage.
4. Generate safe memory methods `from_slice`/`copy_to_slice` with first-`N`
   semantics, `#[track_caller]`, and a panic on a short slice. Delegate to the
   unaligned source primitive.
5. Generate unsafe `from_ptr`/`copy_to_ptr` with exact `N` initialized `T`
   elements and ordinary `T` alignment documented in `# Safety`. Do not expose
   an aligned private-representation variant.
6. Leave scalar-payload `store` as an unsafe generated free function based on
   its typed payload overload/roles.
7. Mark returned logical values/observations `#[must_use]`; do not mark
   mutation or stores returning `()`.

**Acceptance:** external-consumer and value tests cover long/short slices,
misaligned slice addresses, untouched long-slice tails, first/last/OOB lanes,
mask bit order/high bits, logical debug output, and no references into private
storage.

### Slice 16 — render comparisons, selection, conversion, and operators

**Outcome:** the ordinary Rust expression surface delegates to source-owned
semantics.

1. Generate `simd_eq`, `simd_ne`, `simd_lt`, `simd_le`, `simd_gt`, and
   `simd_ge` returning `Mask<T, N>`.
2. Implement whole-vector `PartialEq` by composing the source comparison and
   mask reduction contracts. This scalar Rust trait adaptation is allowed; no
   per-lane comparison loop is generated. Do not implement `PartialOrd`.
3. Generate `Mask::select(true_values, false_values)` and verify that active
   lanes choose the first argument. Delegate to the source `select` order; do
   not flip arguments in the backend.
4. Generate `cast::<U>()` only from `convert_lanes` with equal admitted lane
   counts. Generate only settled same-width `to_bits`/`from_bits` pairs.
5. Generate canonical owned standard operators from typed operation and
   guarantee facts:
   - numeric `Add`, `Sub`, `Mul`, `Div`, `Rem`;
   - signed/floating `Neg`;
   - integer `BitAnd`, `BitOr`, `BitXor`, `Not`, `Shl`, `Shr`;
   - corresponding assignment traits.
6. Generate borrowed forwarding matrices mechanically from the canonical
   owned implementation for vectors and fixed masks: owned/owned,
   borrowed/owned, owned/borrowed, and borrowed/borrowed. Assignment accepts an
   owned or borrowed right-hand side; unary negation accepts an owned or
   borrowed value. Forwarding wrappers call the canonical method and do not
   duplicate primitive selection.
7. Emit shifts only from wrapping-shift source primitives. Scalar RHS types
   come from the typed count capability and accept owned or borrowed values;
   per-lane RHS uses the same owned/borrowed vector matrix as other binary
   operators. Shift assignment accepts the corresponding owned or borrowed
   scalar and per-lane forms.
8. Confirm exact wrapping add/sub/mul and the existing division/remainder
   guarantees in source before admitting their traits.
9. Keep floating bit operations as named methods and keep existing zeroing
   large-count shifts as comprehensive methods.
10. Apply `#[track_caller]` to the settled panicking arithmetic boundaries as
    well as facade bounds/length checks, without moving the arithmetic
    precondition or failure semantics out of the source primitive.

**Acceptance:** value tests cover ownership combinations, assignments,
overflow, `MIN` negation/division/remainder, zero divisors, NaN payloads,
signed zero, conversion boundaries, selection order, and all wrapping-shift
count edges. Wrapper-source tests show only forwarding/delegation and permitted
scalar trait adaptation.

### Slice 17 — render comprehensive primitive methods and rustdoc

**Outcome:** every representable, safe-to-project primitive with a coherent
receiver has a predictable inherent method, without bespoke Rust aliases.

1. Render one inherent method per admitted planner record. Preserve const
   immediates, explicit control masks, target type generics, caller safety, and
   finalized suffixes.
2. Render a free function when there is no coherent receiver; do not force an
   arbitrary `self` merely to make the API method-shaped.
3. Keep unsafe primitives unsafe and copy the typed preconditions into a
   generated `# Safety` section.
4. Use `#[inline]` for thin delegates. Require a demonstrated code-generation
   reason before `#[inline(always)]`.
5. Generate rustdoc from the finalized plan and source documentation. Include
   accurate examples, `# Panics`, `# Safety`, and logical types. Hide profile
   modules and private storage from ordinary navigation.
6. Reserve curated names and report a source-located collision rather than
   silently renaming either method.
7. Migrate the current name-based load/store algorithm facade to typed memory
   facts when it shares this projection. If migration is not required for the
   ordinary facade, leave it isolated and file no new name-special cases.

**Acceptance:** representative unmasked, masked, masked-zero, immediate,
per-lane, conversion-target, memory, unsafe, and free-function primitives have
the settled names; a synthetic renamed primitive produces the same role-based
shape; rustdoc is warning-free.

### Slice 18 — prove and model runtime algorithm dispatch

**Outcome:** the compiler has a verified typed dispatch design before the full
runtime feature is emitted.

1. Build a minimal vertical prototype for one binary built-in operation and one
   stateful mutable operation across generic plus one hardware profile.
2. Keep public slices and operation values outside the profile-specific entry
   points. Construct profile vector values only inside the selected whole-loop
   function.
3. Detect CPU facts once, select one table once, and execute one indirect entry
   per algorithm call. No detection or dispatch occurs inside the vector loop.
4. Use the existing typed algorithm-kernel contracts. Operation values are ZSTs
   for generated built-ins and mutable references for stateful operations.
5. Make generic coverage mandatory for every dispatch slot.
6. Define an injectable detector/profile selector for tests. The production
   detector exists only under `runtime-dispatch`/`std` and uses supported
   architecture detection APIs.
7. Represent the result as frozen `RustDispatchPlan` records containing
   algorithm identity, operation/kernel requirements, ordered candidate entry
   points, generic baseline, feature requirements, and public signature.
8. Stop the slice if the prototype requires runtime vector enums, public type
   erasure, heap allocation, per-operation detection, or a primitive-name list;
   return to the typed algorithm boundary rather than weakening the API.

**Acceptance:** tests prove one-time detection/selection, one dispatch per
algorithm call, state propagation, generic fallback, and that an unsupported
hardware entry point is never entered.

### Slice 19 — generate the complete optional dispatcher

**Outcome:** the settled explicit and convenience runtime APIs are available
behind one additive feature.

1. Generate `Dispatcher::new()` as infallible because every emitted table has
   a generic baseline.
2. Generate explicit methods such as:

   ```rust
   dispatcher.transform_binary(tsl::ops::Add, &left, &right, &mut output);
   ```

3. Generate built-in operation values under `tsl::ops` from the same typed
   operation/kernel facts used by the static algorithm facade.
4. Generate `tsl::algorithms::*` convenience functions over one process-global
   cached dispatcher. They delegate to the explicit dispatcher and own no
   second detector or table.
5. Keep `std` absent unless the `std` feature is enabled; gate the entire
   runtime surface with `runtime-dispatch = ["std"]`.
6. Emit only algorithm/profile combinations with complete typed requirements
   and a generic baseline. Report skipped combinations during planning.

**Acceptance:** explicit and convenience APIs are behaviorally identical;
injected CPU matrices select the best supported entry or generic fallback;
profile types do not appear in public signatures; `--no-default-features`
still builds without `std`.

### Slice 20 — consolidate verification and release evidence

**Outcome:** the distributed artifact is demonstrably sound, Rust-like, and
independent of the generator at consumer build time.

1. Expand the external-consumer fixture to exercise every public category and
   its generic bounds from a separate crate.
2. Add compile-failure cases for unsupported shapes, downstream sealed-trait
   implementations, mask lane mismatches, invalid bit conversions, absent
   hardware-only facade methods, unsafe calls without `unsafe`, and short-lived
   references if any accidental storage view appears.
3. Add owner-equivalence tests between source facts, lowered facts, facade
   records, rendered names, rustdoc, and benchmark/test call sites.
4. Add wrapper audits proving no generated facade body contains a lane loop,
   target-text rewrite, intrinsic, arithmetic correction, count normalization,
   or profile-name branch.
5. Run the target matrix:
   - default generic, no default features;
   - `std`;
   - `runtime-dispatch`;
   - representative x86 fixed hardware compile target;
   - representative Arm fixed hardware compile target when the toolchain is
     available;
   - invalid/unsupported target-feature configurations.
6. Run generic/hardware differential value tests for all curated semantic edge
   cases.
7. Generate package contents and rustdoc, then consume the packaged crate from
   a clean scratch project with no workspace import and no `tslc` dependency.
8. Perform the required post-implementation design review. Check KISS/DRY,
   typed ownership, deterministic ordering, diagnostics, no reverse editor
   ownership, and no duplicate registry.

**Acceptance:** every completion criterion has a named passing test or an
explicit toolchain/hardware skip; no known safety, API, or ownership defect is
deferred behind the facade.

## Test and validation matrix

Use the smallest focused command after each edit, then broaden at each slice
gate. Exact profile/type filters may be narrowed to the changed primitive.

### Source and compiler slices

```bash
./dev.sh check
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests
(cd tslc && python -m mypy)
```

For new source primitives, run ordinary backend verification before facade
tests, for example:

```bash
./dev.sh build --primitives neg --profiles scalar,avx2 --backends cpp,rust
./dev.sh test --primitives neg --profiles scalar,avx2 --backends cpp,rust
PYTHONPATH=tslc/src python -m pytest -q --run-generated-builds \
  tslc/tests/test_build_verify.py tslc/tests/test_value_tests.py
```

Substitute the primitive and a valid representative profile when AVX2 is not
applicable. Cross-target execution requires an injected runner or is reported
as skipped.

### Authoring/editor slices

```bash
PYTHONPATH=tslc/src python -m pytest -q \
  tslc/tests/test_authoring_completion.py \
  tslc/tests/test_catalog_index_authoring.py \
  tslc/tests/test_lsp_protocol.py \
  tslc/tests/test_lsp_workspace.py
(cd editors/vscode-tsl && npm test)
```

Run VS Code integration only when the protocol/client or packaged grammar
changes. Pure Python semantic changes do not justify TypeScript duplication.

### Generated Rust facade/package slices

Generate into `tslctmp/` and exercise at least:

```bash
cargo check --manifest-path tslctmp/generated/rust/Cargo.toml --no-default-features
cargo check --manifest-path tslctmp/generated/rust/Cargo.toml \
  --no-default-features --features std
cargo check --manifest-path tslctmp/generated/rust/Cargo.toml \
  --no-default-features --features runtime-dispatch
cargo clippy --manifest-path tslctmp/generated/rust/Cargo.toml \
  --no-default-features -- -D warnings
RUSTDOCFLAGS="-D warnings" cargo doc \
  --manifest-path tslctmp/generated/rust/Cargo.toml --no-default-features
```

Use verifier-owned target flags and target directories for hardware compile
targets; do not reintroduce profile features in these commands.

### Final repository checks

```bash
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests
(cd tslc && python -m mypy)
PYTHONPATH=tslc/src python -m pytest -q --run-generated-builds \
  tslc/tests/test_build_verify.py tslc/tests/test_value_tests.py
git diff --check
```

## Cross-cutting review checklist

Apply this checklist to every slice that changes source meaning, lowering, or
the Rust projection.

- Is each semantic fact authored in `tsldata` or derived from an existing typed
  compiler fact?
- Does the editor consume the compiler fact rather than copy its vocabulary?
- Does selection/lowering preserve the fact without a raw dictionary?
- Does the Rust planner consume enums/roles instead of names, prose, position
  guesses, or target text?
- Is generic fallback source-backed and exact-width?
- Is every hardware call guarded by the same finalized target requirement used
  for selection?
- Does each public wrapper contain only Rust boundary adaptation and delegate
  to source-owned primitives?
- Are all unsafe blocks local, documented, and backed by a typed invariant?
- Are diagnostics deterministic, source-located where practical, and emitted
  before templates?
- Do source prerequisites pass ordinary C++ and Rust tests before the facade
  uses them?
- Does a rename/additive probe show that no parallel primitive registry was
  introduced?
- Are existing lower-level primitive entry points preserved?

## Stop conditions

Stop the current slice and report the issue rather than adding facade logic if:

- a required operation, role, guarantee, memory, conversion, or safety fact is
  absent from typed source data;
- an admitted facade operation lacks a generic implementation;
- exact hardware mapping would require composing registers or changing a
  value's representation at runtime;
- Rust target features cannot be matched safely to a source profile;
- a wrapper would need to normalize shift counts, repair arithmetic, implement
  conversion, inspect mask storage, or parse target text;
- runtime dispatch would require per-vector branching or a public runtime
  representation enum;
- a template would have to choose semantics;
- a source schema change cannot be exposed coherently through compiler-owned
  authoring/editor services;
- a generated hardware test cannot run and has neither an injected runner nor
  an explicit compile-only/skip result;
- preserving the current lower-level API conflicts with soundness. Treat that
  as a separate, explicit compatibility decision rather than hiding it in the
  facade slice.

## Delivery strategy

Land the slices in order, with one coherent review packet per slice. Do not
hold source primitives, safety fixes, package selection, and the full facade in
one branch-sized change. Each packet reports:

- the delivered user-visible or compiler behavior;
- the source/compiler/backend/editor ownership boundaries touched;
- tests added and commands run;
- generated toolchain or hardware skips;
- follow-ups intentionally excluded.

The first publishable facade release occurs only after Slice 20. Intermediate
slices may improve the lower-level Rust product, but they do not advertise the
ordinary `Simd<T, N>` API as stable until all soundness, static-selection, and
external-consumer gates pass.
