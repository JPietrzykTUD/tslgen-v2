# Rust API Facade Hardening Plan

## Status and authority

This is a corrective follow-up to the implemented facade work described by
`todo/rust-api-plan-final.md`. The settled public API in
`todo/rust-api-plan.md` remains the product authority. This plan does not
reopen public spelling, ownership, mask behavior, fixed-width policy, overload
suffixes, runtime-dispatch design, or the lower-level generated API.

The work remains a compiler-owned Rust projection over typed TSL facts:

- `tsldata` owns primitive meaning, operand roles, overload meaning, memory
  behavior, conversion availability, safety, and implementations;
- catalog, selection, and lowering own validation and preservation of those
  facts;
- the Rust backend owns Rust-only API spelling, ownership adaptation, trait
  presentation, and exact target-selected call planning;
- renderers and templates format finalized records and do not classify source
  meaning or search for implementations.

The post-implementation review found that the facade follows this direction
but does not yet satisfy it completely. In particular, some typed facts are
collapsed into positional or name-based assumptions, and some decisions are
reconstructed during rendering. This plan closes those gaps before the
ordinary facade is treated as stable.

## Goal and completion criteria

Make the generated Rust facade an exact, maintainable projection of the
selected TSL corpus without recreating TSL semantics or maintaining a parallel
primitive registry.

The hardening work is complete when:

1. every lower call is ordered from finalized source indices and operand
   roles, not from a renderer's assumed parameter order;
2. fallback delegate ownership is retained from selected source facts, with no
   `"scalar"` or `"generic"` name heuristic used to locate an implementation;
3. target-vector conversions preserve the exact authored source/target matrix
   and never widen it to a Cartesian product;
4. contiguous memory facades are classified from typed operation, memory,
   role, overload, and signature facts, never from the primitive name;
5. every facade-representable signature kind has one Rust-facade-owned type and
   adaptation policy composed with the lower-level
   `RUST_SIGNATURE_TYPES` owner;
6. `RustFacadePlan` or focused records reachable from it contain every
   delegate, representation, argument, generic, type-adaptation, and trait
   decision required to render the facade;
7. Rust facade renderers format those records without importing catalog
   semantics, the facade planner, or scalar documentation metadata;
8. the planner is split into cohesive modules after behavior is correct, with
   deterministic output and source-oriented diagnostics unchanged;
9. synthetic rename, reordering, sparse-matrix, and additive probes protect the
   corrected extension points;
10. existing generic, hardware, external-consumer, warning, Clippy, rustdoc,
    packaging, and value-test gates remain green.

## Consolidated findings and disposition

| Priority | Finding | Required disposition |
| --- | --- | --- |
| High | Curated methods, traits, and core operations collect operand roles but render calls in assumed positional order. | Preserve an exact source-indexed invocation mapping through planning and consume it for every lower call. |
| High | Fallback delegate lookup guesses source extension IDs from lane count. | Retain the exact lower implementation owner separately from whether a representation is hardware-backed. |
| High | Target-vector result types are unioned and rendered as every same-lane source/target pair. | Plan exact conversion edges and exact implementation arms. |
| Medium-high | The shared memory facade keys on `load`/`store`; the Rust renderer discards the typed facade and branches on the function name. | Classify and render from typed operation and memory facts. |
| Medium | Comprehensive rendering repeats the facade kind-to-Rust-type vocabulary and intentionally widened integral-mask policy. | Establish one named facade type/adaptation policy without changing the lower-level type contract. |
| Medium | Rendering searches delegates, crosses representations, recognizes public names, and derives operator/equality behavior. | Finalize implementation arms and Rust policy flags before rendering. |
| Medium | `rust_api_planner.py` owns too many unrelated responsibilities. | Split it only after the corrected plan boundary is stable. |
| Low | Artifact rendering can replan and revalidate already-created semantic plans. | Remove render-time planning narrowly; do not introduce caching or a pipeline-wide handoff framework. |
| Test gap | Existing synthetic rename/additive tests do not exercise the fragile boundaries above. | Add focused role-permutation, fallback-rename, sparse-conversion, and memory-rename probes. |

The existing unknown-overload behavior is not changed here. A valid but
unrecognized overload axis remains a planning error until the project
separately decides whether strict facade completeness or graceful facade
exclusion is preferred.

## Fixed scope

### In scope

- typed Rust facade planning models and planners;
- Rust static-selection facts needed to retain exact lower ownership;
- the shared dataparallel primitive-facade classifier;
- ordinary and legacy Rust facade rendering;
- the existing C++ consumer of the shared memory classifier, only as required
  to preserve shared projection behavior;
- focused planner, renderer, structure, determinism, generated-build, and
  external-consumer tests;
- compiler architecture documentation when module ownership changes.

### Expected not to change

- `tsldata`: the required operation, operand-role, overload, memory,
  conversion, safety, and fallback-capability facts already exist;
- compiler-owned editor services: no source vocabulary is being added;
- lower primitive bodies and their selection/lowering behavior;
- public Rust API names and behavior;
- C++ public API design.

If an implementation slice discovers that a required distinction is not
available as a typed fact, it stops. Any new fact must be introduced in a
separate projection-neutral source/compiler slice, including authoring/editor
support where applicable. It must not be encoded as Rust-only metadata or a
primitive-name table.

### Out of scope

- adding new primitives, memory-addressing kinds, overload axes, or source
  annotations merely to exercise this cleanup;
- changing the settled `im`/`imt` public facade presentation as `u64`;
- changing fixed widths, native aliases, mask behavior, or runtime dispatch;
- stable layout, ABI, serialization, transmute, or FFI guarantees;
- parsing implementation bodies or target text;
- moving Python-rendered wrapper text into templates solely because it is
  multiline;
- a generic Rust syntax tree or render-node framework;
- process-global plan caches or a repository-wide validation/render handoff
  redesign;
- unrelated safety-reason string typing and consolidation of fixed-width
  constants.

## Canonical data flow and ownership

```text
tsldata declarations
        |
        v
typed catalog contracts
  operation / roles / overload / memory / conversion / safety
        |
        v
selected and lowered specializations
  exact source extension / source type / target type / parameter indices
        |
        +--------------------------------------+
        |                                      |
        v                                      v
RustStaticSelectionPlan        shared typed primitive-facade classification
        |                                      |
        v                                      v
finalized RustFacadePlan       C++/Rust algorithm facade renderers
  exact invocation mappings / delegate owners / conversion pairs /
  representation arms / type adaptations / Rust trait policy
        |
        v
ordinary Rust renderers and static assets
              formatting only
```

| Required fact | Canonical owner | Facade use |
| --- | --- | --- |
| Operation identity and operand roles | `LoweredPrimitiveSemantics.operation` | Receiver placement, canonical public ordering, and exact source-call ordering |
| Arithmetic identity, roles, and guarantees | `LoweredPrimitiveSemantics.arithmetic` | Trait eligibility and exact receiver/RHS mapping |
| Memory access and addressing | `LoweredPrimitiveSemantics.memory` | Contiguous read/write facade admission |
| Payload or count overload | `LoweredPrimitiveSemantics.overload` | Vector/scalar memory distinction and method suffix |
| Exact source and result type binding | `LoweredSpecialization.type_tag` and lowered type parameters | Exact conversion-pair availability |
| Exact implementation extension | `LoweredSpecialization.extension_name` plus selected fallback/profile inventory | Lower delegate binding |
| Hardware target requirement | `RustStaticSelectionPlan` | Exact cfg-selected representation arm |
| Lower Rust signature forms | `RUST_SIGNATURE_TYPES` | Lower call ABI spelling |
| Public Rust facade forms | one focused Rust facade type policy | Public/private spelling and boundary adaptation |
| Rust method and trait policy | Rust facade planner | Curated names, standard traits, forwarding, and annotations |

## Required end-state model invariants

The exact class names below are recommendations, not permission to introduce a
general rendering framework. Each added record must carry a real invariant
that is currently re-derived.

### Invocation mappings

A small frozen invocation-argument record should identify:

- the authored source parameter index;
- whether the public value comes from the receiver, an ordinary argument, a
  const generic, or a target-type binding;
- the public argument index where applicable;
- the typed boundary adaptation selected by the facade type policy.

The ordered lower-call argument sequence is derived from source indices. Public
receiver placement never changes authored lower-call order. Every runtime
source parameter must appear exactly once; missing, duplicate, out-of-range, or
kind-incompatible mappings are planning diagnostics.

### Exact delegate bindings

Logical representation and lower implementation ownership are distinct:

- a representation answers which private vector/mask type is active;
- a delegate binding answers which emitted primitive and source extension
  implements one planned call.

Do not overload `uses_hardware` or an optional hardware extension field with
both meanings. If one logical fallback representation can be implemented by
different source extensions for different primitives, retain the extension
owner per finalized delegate/implementation arm rather than forcing it onto
the logical shape.

### Exact conversion pairs

The plan must retain source-owned edges such as:

```text
(source type, target type, lane relation, primitive, delegate inventory)
```

An aggregate set of source tags and an aggregate set of target tags is not an
availability model. Comprehensive target-vector methods and curated `cast`
implementations consume the same exact pair inventory. Representation-specific
arms are derived only for an admitted pair.

### Typed memory facade classification

A contiguous memory facade requires all relevant typed facts:

- operation identity;
- `MemoryAccess.READ` or `MemoryAccess.WRITE`;
- `MemoryAddressing.CONTIGUOUS`;
- compatible memory/value operand roles;
- compatible result and parameter kinds;
- resolved payload overload where multiple payload shapes exist;
- a projection-neutral resolved alignment mode derived from the existing
  catalog-owned `[aligned]` wildcard axis.

Primitive name remains an emitted delegate identity, never a classifier.

The alignment decision for this plan is settled: `[aligned=*]` is already a
compiler-owned schema attribute, not an arbitrary primitive name. Slice 4
introduces or reuses one projection-neutral catalog/lowering helper that
resolves the concrete specialization to typed `ALIGNED`/`UNALIGNED` meaning.
The shared and ordinary facade planners consume that result; they do not each
compare a local string literal. This needs no tsldata or editor vocabulary
change. If the existing catalog/lowering evidence cannot support that resolver,
Slice 4 stops rather than adding a facade-specific heuristic.

### Facade type and adaptation policy

The facade needs one Rust-specific policy for each admitted signature kind:

- public parameter/result form;
- private trait/implementation form;
- direct versus wrapped/unwrapped vector or mask values;
- integral-mask narrowing before a lower call;
- integral-mask widening after a lower call.

This policy composes with `RUST_SIGNATURE_TYPES`. It does not redefine the
lower primitive ABI. In particular, the public `u64` integral-mask spelling is
an intentional facade boundary policy while a lower representation may use a
narrower integral-mask type.

### Finalized implementation arms

The planner should produce focused implementation-arm records for
comprehensive methods, curated methods, traits, equality, and conversions.
Each arm retains only the facts its renderer needs:

- source and optional target logical shape;
- source and optional target representation;
- already-proven target-selection predicate inputs;
- exact lower module/profile, delegate, and extension owner;
- exact argument and generic-argument mapping;
- exact type/result adaptations;
- caller-unsafety and Rust annotations or trait flags.

These records are not a Rust AST and do not contain complete function bodies.
Cfg syntax, identifiers, indentation, documentation layout, and wrapper text
remain rendering concerns.

## Diagnostic policy

Source or inventory defects must fail before rendering with deterministic,
source-oriented diagnostics:

- missing or ambiguous delegate owner;
- incomplete or invalid invocation mapping;
- incompatible operation, role, memory, or signature contracts;
- ambiguous conversion implementation for one exact pair;
- unsupported facade signature kind;
- impossible source/target representation pair;
- duplicate finalized implementation arm.

`ValueError` remains appropriate only for a corrupted frozen plan or an
internal invariant violation. A renderer must not be the first stage to
discover a valid-source availability problem.

## Implementation slices

Each slice is independently reviewable. Do not combine the semantic
corrections with the final mechanical module split.

### Slice 1 — preserve role-exact invocation order

**Outcome:** public Rust receiver/argument placement adapts ergonomics without
changing the authored lower primitive call order.

1. Inventory all lower-call construction paths:
   - comprehensive methods and free functions;
   - selection and comparison methods;
   - arithmetic, bitwise, mask, shift, and assignment traits;
   - core construction, lane, mask, and memory delegates;
   - conversion and bit-conversion calls.
2. Add the minimal frozen invocation mapping described above. Reuse
   `RustFacadeParameter.source_index` instead of creating an unrelated
   positional convention.
3. Derive the mapping from typed operation/arithmetic roles and the lowered
   parameter list. Role determines public receiver/argument meaning; source
   index determines lower-call order.
4. Preserve const-generic and overload-parameter positions separately from
   runtime argument positions.
5. Validate uniqueness, completeness, bounds, and kind compatibility during
   planning.
6. Change curated, trait, and core renderers to consume the mapping. Remove
   fixed argument tuples such as `(self, rhs)` and
   `(mask, true_values, false_values)` from semantic call construction.
7. Keep borrowed forwarding wrappers mechanical over the one canonical owned
   implementation.

**Likely owners:** `backend/rust_api_model.py`,
`backend/rust_api_planner.py`, `render/rust_facade.py`,
`render/rust_facade_comprehensive.py`, and focused Rust facade tests.

**Focused proof:**

- reorder source parameters for `select`, less-than, subtraction or division,
  contiguous store, and lane insertion;
- assert the finalized source-index mapping and rendered lower-call order;
- reject duplicate, missing, out-of-range, and kind-incompatible indices;
- assert every runtime source parameter is consumed exactly once;
- retain the wrapper audit forbidding lane loops, target intrinsics, and
  arithmetic repair.

**Acceptance:** all reordered fixtures preserve behavior without changing the
settled public method signatures, and no curated/core renderer decides operand
order.

### Slice 2 — retain exact fallback implementation ownership

**Outcome:** a capability-preserving fallback-extension rename is additive and
cannot break facade delegate lookup.

1. Inventory the two current meanings carried by
   `RustStaticVectorMapping.extension_name`: hardware representation identity
   and lower delegate-owner lookup.
2. Introduce a separate exact implementation-owner binding at the narrowest
   correct level:
   - on a static mapping only if source evidence proves one owner for every use;
   - otherwise on each finalized facade delegate/implementation arm.
3. Derive the owner from selected fallback specializations and typed extension
   capability (`implementation_fallback`), never from lane count.
4. Preserve the current `uses_hardware` meaning for representation selection.
5. Diagnose missing or ambiguous fallback owners during planning.
6. Remove fallback delegate-selection comparisons against the source IDs
   `"scalar"` and `"generic"` from planner and renderer helpers.
7. Keep `Scalar` and `Generic<N>` as legitimate Rust representation spellings;
   this slice changes source-owner lookup, not the public/private Rust type
   model.

**Likely owners:** `backend/rust_static_selection.py`,
`backend/rust_api_model.py`, the facade planner, `render/rust_facade_common.py`,
`render/rust_facade_comprehensive.py`, and static-selection/facade tests.

**Focused proof:**

- use novel capability-equivalent fallback extension IDs for lane-one and
  fixed-lane mappings;
- prove the exact IDs survive selection, representation/delegate planning, and
  the rendered lower call;
- use the same lane count with different fallback owners to prove lane count is
  not a classifier;
- reject a mapping with no matching emitted specialization;
- retain real-corpus scalar/SSE2/AVX2 selection tests.

**Acceptance:** delegate lookup works after a synthetic fallback rename and no
ordinary-facade lookup function guesses a source extension ID.

### Slice 3 — preserve the exact conversion matrix

**Outcome:** the generated facade exposes exactly the conversion pairs
supported by selected source specializations.

1. Retain the exact source type and resolved target type binding for every
   target-vector specialization during candidate normalization.
2. Replace union-only conversion availability with a frozen exact pair record.
3. Validate pair consistency with the source conversion contract, lane-count
   relation, generic baseline, safety, and delegate inventory.
4. Use the same pair inventory for:
   - comprehensive target-vector methods;
   - curated lane-preserving `cast`;
   - representation-specific conversion implementation arms.
5. Keep bit-pattern conversion pairs separate where their settled same-width
   policy differs, but make their availability exact as well.
6. Sort pairs and arms deterministically by source shape, target shape,
   profile, and delegate identity.
7. Remove source/target Cartesian-product expansion from both facade
   renderers.

**Likely owners:** `backend/rust_api_model.py`, candidate and curated planning,
`render/rust_facade.py`, `render/rust_facade_comprehensive.py`, and conversion
planner/render tests.

**Focused proof:**

- construct a sparse matrix containing only `si32 -> f32` and `ui32 -> f64`;
- assert that `si32 -> f64` and `ui32 -> f32` are neither planned nor rendered;
- cover more than one lane count/profile so type sets cannot accidentally
  rejoin through a shared lane count;
- reject ambiguous delegates for one exact pair;
- prove permutation-stable pair ordering;
- retain existing real-corpus cast, conversion, and bit-conversion value tests.

**Acceptance:** there is one rendered implementation per planned exact pair
and no unsupported pair can be invented during rendering.

### Slice 4 — replace name-keyed memory facade classification

**Outcome:** renamed contiguous load/store primitives continue to produce the
ordinary and algorithm facade surfaces from typed source meaning.

1. Include typed memory access/addressing in candidate and operation-binding
   facts used by the ordinary facade.
2. Require the complete typed contiguous-memory contract for curated core
   `from_slice`/`copy_to_slice` and raw-pointer delegate admission.
3. Update `RustFacadeCoreOperationRequirement` or its focused replacement to
   state required memory access/addressing rather than relying on operation and
   signature alone.
4. Resolve the existing catalog-owned `[aligned]` specialization axis once to
   a typed aligned/unaligned fact at the catalog/lowering boundary.
5. Rewrite `classify_dataparallel_primitive_facade` to classify contiguous
   memory from typed operation, memory contract, operand roles, payload
   overload, signature, and resolved alignment support.
6. Retain the classified memory access/operation on
   `DataparallelPrimitiveFacade`; enforce that it is present exactly for
   `CONTIGUOUS_MEMORY`.
7. Change the Rust algorithm renderer to branch on that typed value. Remove
   `del facade`, the `function_name == "load"/"store"` classifier, and the
   name-based assertion fallthrough.
8. Continue using the emitted primitive name when spelling the lower delegate.
9. Verify the shared classifier's C++ consumer still renders the same facade;
   this is not a C++ API redesign.
10. Diagnose internally inconsistent operation/access/role contracts before
    rendering. Treat a valid facade-incompatible shape as a typed exclusion;
    a future non-contiguous addressing kind must follow that path without a
    facade change. Reserve `ValueError` for a corrupted frozen plan.

**Likely owners:** `backend/primitive_facade.py`,
`backend/rust_api_model.py`, the Rust facade planner,
`backend/rust_facades.py`, the C++ facade consumer, and focused specialization,
planner, and render tests.

**Focused proof:**

- novel-name `READ + CONTIGUOUS` and `WRITE + CONTIGUOUS` primitives with
  compatible roles/signatures are admitted;
- identical signatures without a memory contract produce the expected
  planning diagnostic;
- valid facade-incompatible shapes produce deterministic typed exclusions;
- the exact `CONTIGUOUS` requirement is asserted so a future addressing kind
  joins the exclusion test without a facade code change;
- inconsistent operation/access/roles produce planning diagnostics;
- vector and scalar store payloads remain distinguished by resolved overload;
- masked and incompatible memory shapes are not accidentally admitted to the
  unmasked core boundary;
- both Rust and C++ shared-facade projections survive a semantic rename;
- existing slice, raw-pointer, masked-memory, and scalar-store consumer tests
  remain green.

**Acceptance:** primitive name is only an emitted identifier, and every
admitted typed memory facade has a total renderer case.

### Slice 5 — establish one Rust facade signature-type policy

**Outcome:** every admitted signature kind has one owner for facade spelling
and boundary adaptation while lower Rust ABI forms remain canonical.

1. Inventory the runtime contexts for `void`, `v`, `m`, `im`, `imt`, `s`,
   `usize`, `ptr`, and `cptr`. Keep `sImm` in const-generic planning rather than
   treating it as a runtime type.
2. Add one small focused Rust facade type-policy module or model keyed by typed
   signature kind.
3. Compose lower forms with `RUST_SIGNATURE_TYPES`; do not copy its complete
   owner/concrete vocabulary.
4. Represent boundary adaptation with a small typed enum or record:
   identity, unwrap/wrap vector, unwrap/wrap mask, narrow integral mask, and
   widen integral mask as applicable.
5. Keep `im`/`imt -> u64` explicit as facade policy. Validate narrowing/widening
   against each active representation's lower integral-mask spelling.
6. Resolve scalar Rust spellings from typed scalar/vector mapping facts, not
   `documentation_short_label`.
7. Replace the comprehensive renderer's parallel `_raw_type`,
   `_impl_raw_type`, `_public_type`, and result/call adaptation tables.
8. Replace the planner's separate representable-kind inventory with the one
   policy owner.
9. Reuse `RustStaticVectorMapping.vector_spelling` or a finalized descriptor
   rather than reconstructing representation spelling in rendering.

**Likely owners:** a focused module such as `backend/rust_api_types.py`,
`backend/signature_types.py` as the unchanged lower owner,
`backend/rust_api_model.py`, the facade planner, both facade renderers, and
signature/planner tests.

**Focused proof:**

- table-drive every admitted kind through public, private, lower-input, and
  lower-result contexts where applicable;
- cover lower `u8`, `u16`, `u32`, and `u64` integral masks adapting to public
  `u64`;
- diagnose unsupported runtime kinds during planning rather than raising a
  renderer `KeyError`;
- prove scalar RHS code uses Rust type spelling rather than documentation
  labels;
- add a structural assertion that comprehensive rendering contains no complete
  kind-to-type dictionary.

**Acceptance:** one facade type/adaptation policy exists, lower type ownership
is not duplicated, and renderers contain no independent signature vocabulary.

### Slice 6 — finalize all implementation arms before rendering

**Outcome:** rendering a valid `RustFacadePlan` cannot discover missing
delegates, incompatible representations, unsupported conversions, or
operation-specific behavior.

1. Inventory remaining decisions in `render/rust_facade.py`,
   `render/rust_facade_comprehensive.py`, and
   `render/rust_facade_common.py`.
2. Add focused, family-specific implementation-arm records for:
   - comprehensive private implementations;
   - curated methods;
   - operators and assignments;
   - equality;
   - numeric and bit conversions;
   - mask operators currently duplicated by the static template.
3. Finalize source/target representation compatibility in planning. Retain
   already-selected typed cfg predicate inputs for formatting.
4. Bind each arm to exactly one lower module/profile, delegate, extension
   owner, argument mapping, generic mapping, and type/result adaptation.
5. Derive overload generic placeholders from
   `delegate.overload_parameter_positions`; remove shift-specific generic
   arity guesses.
6. Finalize concrete RHS spelling, unary/binary shape, assignment trait/method,
   forwarding variants, `#[track_caller]`, `PartialEq`, and `Eq` eligibility in
   planning.
7. Replace renderer checks on public names such as `"cast"` and `"simd_eq"`
   with typed planned item kinds or dedicated records.
8. Make planned mask-trait implementation arms the sole owner of emitted mask
   operators and remove the duplicate template-owned implementations.
9. Keep cfg syntax, Rust identifiers, documentation layout, and wrapper body
   formatting in rendering.
10. Remove delegate and representation searches from render helpers once every
    caller consumes exact arms.

**Likely owners:** `backend/rust_api_model.py`, facade planner modules,
`render/rust_facade.py`, `render/rust_facade_comprehensive.py`,
`render/rust_facade_common.py`, `backend/assets/rust_facade.rs.tmpl`, and
planner/render/dispatch tests.

**Focused proof:**

- every planned arm contains exactly one delegate and a complete invocation;
- planned public items and implementation arms correspond one-to-one with
  emitted items;
- sparse conversions, reordered operands, fallback ownership, equality,
  assignment, shifts, and mask operators render without semantic lookup;
- tampered duplicate/incomplete arms fail model validation;
- architecture tests prohibit facade renderers from importing catalog
  operation/arithmetic enums, `SCALAR_TYPE_INFOS`, or
  `RUST_SIGNATURE_TYPES`, or `backend.rust_api_planner`;
- wrapper audits cover comprehensive methods, curated methods, core delegates,
  traits, equality, masks, and conversions.

**Acceptance:** no delegate search, representation cross-product, semantic
operation classification, or public-name classification remains under
`tslc/render/`.

### Slice 7 — split the facade planner by established responsibility

**Outcome:** `rust_api_planner.py` becomes a small public orchestration module
without changing plans, diagnostics, or generated Rust.

Use literal modules, with final names adjusted to existing local style:

- `rust_api_candidates.py`
  - candidate keys and normalization;
  - exact type/conversion/delegate inventory;
  - overload-position inventory and deterministic ordering.
- `rust_api_comprehensive.py`
  - comprehensive admission/exclusion;
  - public naming, receiver and parameter planning;
  - safety, panic, documentation, and coverage facts.
- `rust_api_curated.py`
  - curated methods, traits, equality, operation values, and conversion policy.
- `rust_api_surface.py`
  - logical shapes and native aliases;
  - core requirements;
  - exact representation/delegate/implementation-arm finalization;
  - completeness and collision diagnostics.
- `rust_api_planner.py`
  - public planning/validation/closure-seed APIs;
  - direct deterministic orchestration only.

1. Move one responsibility at a time after Slices 1-6 are green.
2. Keep `rust_api_model.py` and the facade type-policy module dependency roots.
3. Prevent child planner modules from importing the orchestration module.
4. Preserve public imports from `rust_api_planner.py` so callers do not learn
   the internal layout.
5. Move constants to their semantic owner rather than creating a general
   constants module.
6. Keep source-located diagnostics and sort keys byte-for-byte stable.
7. Split the existing planner test catch-all along the same behavioral
   boundaries where that improves reviewability.
8. Do not introduce request/result/handoff wrappers or a class hierarchy of
   planner stages.

**Focused proof:**

- record the parent-commit representative plan/artifact digest in the review
  packet and compare it after the mechanical extraction;
- run focused tests after each module move;
- run `compileall` and mypy for cycles and typed public interfaces;
- keep an ongoing test proving reversed input/profile order produces the same
  plan and rendered bytes.

**Acceptance:** each module has one stated responsibility, orchestration is
direct, and the structural split changes no generated behavior.

### Slice 8 — remove render-time replanning narrowly

**Outcome:** one artifact-rendering pass consumes the exact static, facade, and
dispatch plans constructed for that pass.

1. Keep `rust_backend_artifacts` as the production owner that constructs
   static selection, facade, dispatch, and consumption plans.
2. Make those semantic plans required inputs to a private/internal trusted
   project-rendering boundary. Tests that start from profiles must plan before
   calling it.
3. Remove calls to `plan_rust_facade` and `plan_rust_dispatch` from rendering.
4. Remove full semantic replan-and-equality validation from the render path.
   Successful construction by the compiler-owned production planner is its
   explicit precondition; the renderer is not a public foreign-plan API.
5. Retain expensive recompute-and-compare behavior only as an explicit
   planner/debug test if it remains useful.
6. Continue diagnosing invalid source inventories through backend validation
   and planners before artifact rendering.
7. Measure the remaining validation-pass versus artifact-pass duplication.
   Leave it in place if eliminating it would require changing the generic
   backend validation contract.
8. Add no cache, mutable singleton, object-identity shortcut, or wrapper-only
   backend snapshot type.

**Likely owners:** `backend/rust_capability.py`,
`backend/rust_validation.py`, facade/dispatch planners,
`render/rust_project.py`, and orchestration tests.

**Focused proof:**

- monkeypatch planners to fail after supplying finalized plans and prove the
  renderer still succeeds;
- count one construction of each Rust semantic render plan per artifact pass;
- retain model tests for corrupted, duplicate, or incomplete frozen records;
- prove the production entry point is the only non-test caller of the trusted
  project renderer;
- render twice from one plan and compare byte-identical artifacts.

**Acceptance:** the render package does no facade planning, while no broader
compiler-pipeline cache, provenance key, or handoff abstraction is introduced.

### Slice 9 — consolidate verification and architecture evidence

**Outcome:** all reviewed boundaries have focused evidence and the generated
crate remains warning-free, Rust-like, and behaviorally unchanged.

1. Re-run the owner-equivalence tests added with Slices 1-6 for comprehensive
   and curated methods, traits, core delegates, conversions, equality, and
   mask operators.
2. Re-run Slice 6's exact inventory assertion that every planned public item
   and implementation arm is emitted once and every lower call names one
   planned delegate.
3. Re-run Slice 7's expanded deterministic/hash-seed fixtures covering
   comparison, selection, conversion, and memory.
4. Exercise a representative generated family:
   - `add`, `sub`, `div`;
   - comparison and `select`;
   - `convert_lanes` and bit reinterpretation;
   - `load`, `store`, and lane insertion.
5. Run generic plus representative SSE2 and AVX2 compile targets. Hardware
   execution occurs only on a supporting runner; otherwise record compile-only
   evidence or an explicit skip.
6. Run no-std, `std`, runtime-dispatch, warning, Clippy, rustdoc, path-consumer,
   packaged/offline-consumer, and value-test gates.
7. Update `tslc/DESCRIPTION.md` to describe the actual modular planner and
   finalized render boundary. Update other instructions only if their commands
   or ownership rules changed.
8. Run the `design-review` skill again after focused validation and close every
   finding against code and tests.

**Acceptance:** each completion criterion has a named passing test or an
explicit toolchain/runner gap, and the post-implementation review finds no
primitive-name classifier, positional call inference, conversion widening, or
render-time semantic selection.

## Existing evidence and missing probes

| Area | Existing evidence | New proof required |
| --- | --- | --- |
| Roles | Receiver/const placement and select-receiver planner tests | Permuted source signatures plus final lower-call assertions |
| Rename/additivity | Arithmetic semantic rename and synthetic unknown primitive | Renamed memory primitive and fallback extension |
| Memory facade | Shared classifier test for current `store` spelling | Typed novel-name read/write classification and rendering |
| Conversion | Real-corpus conversion and cast coverage | Sparse exact source/target matrix |
| Signature projection | Lower algorithm facade uses `RUST_SIGNATURE_TYPES` | Exhaustive ordinary-facade type/adaptation policy |
| Planner/render boundary | Comprehensive wrapper audit | Curated/core/trait/mask/conversion one-to-one audit |
| External consumer | Broad public API behavior | Corrected families included explicitly in closure |
| Determinism | Artifact/hash-seed tests over a small family | Comparison, selection, conversion, and memory inventory |

The existing synthetic tests remain useful and should not be replaced by copied
or renamed production `tsldata`. The new probes operate on typed lowered
fixtures so they isolate projection behavior.

## Validation matrix

Run the smallest owning test after each edit. The focused suite for Slices 1-6
should include, with test files split if the current planner test becomes less
cohesive:

```bash
PYTHONPATH=tslc/src python -m pytest -q \
  tslc/tests/test_rust_api_planner.py \
  tslc/tests/test_rust_static_selection.py \
  tslc/tests/test_rust_dispatch.py \
  tslc/tests/test_backend_signature_types.py \
  tslc/tests/test_specialization.py \
  tslc/tests/test_pipeline_structure.py \
  tslc/tests/test_determinism.py
```

Run typed compiler checks after model or module-boundary changes:

```bash
python -m compileall -q tslc/src/tslc
(cd tslc && python -m mypy)
```

Run the complete Python suite after each semantic slice and after the planner
split:

```bash
PYTHONPATH=tslc/src python -m pytest -q tslc/tests
```

Use `./dev.sh` for the smallest useful generated Rust matrix, adjusting the
comparison and lane primitive names to the live corpus inventory:

```bash
./dev.sh build \
  --primitives add,sub,div,less_than,select,convert_lanes,reinterpret,load,store,insert_value_at \
  --profiles scalar,sse2,avx2 \
  --backends rust
```

Generated release evidence after Slices 1-6 and again after Slice 9:

```bash
PYTHONPATH=tslc/src python -m pytest -q --run-generated-builds \
  tslc/tests/test_build_verify.py \
  tslc/tests/test_value_tests.py
```

The generated/project fixtures must cover:

- `cargo check --no-default-features`;
- an external no-std consumer;
- the `std` feature;
- the `runtime-dispatch` feature;
- `cargo clippy -- -D warnings`;
- `RUSTDOCFLAGS="-D warnings" cargo doc`;
- path-dependency consumer execution;
- packaged/offline consumer execution;
- representative compile-target selection.

Always finish each slice with:

```bash
git diff --check
```

Unavailable Cargo components, cross-target toolchains, emulators, or hardware
remain explicit skips or compile-only gaps. They are not reported as successful
runtime verification.

## Cross-cutting design-review guardrails

Apply these checks to every slice:

- No facade module reads or imports `tsldata`.
- No primitive name, parameter name, source prose, or target text classifies
  semantic meaning.
- Names remain legal outputs: emitted primitive/delegate identifiers and
  settled Rust public spelling.
- No new source fact is added for Rust alone.
- No source selection, dependency closure, lowering, arithmetic rule, shift
  normalization, conversion algorithm, or mask representation is duplicated.
- Public wrapper bodies contain only Rust boundary checks/adaptation and one
  source-owned delegate/composition.
- Renderers format typed decisions; they do not search or classify.
- New records are frozen, deterministic, and justified by an invariant.
- Diagnostics are emitted before rendering and retain a source span where
  practical.
- The next capability-equivalent fallback extension, reordered signature,
  sparse conversion family, and renamed primitive are additive.
- C++ behavior changes only where the shared typed classifier must stop using a
  source name.
- The lower-level generated Rust API remains available and behaviorally
  unchanged.

## Stop conditions

Stop the current slice rather than adding another heuristic if:

- operand roles do not uniquely map every runtime parameter;
- selected/lowered facts cannot identify the exact fallback implementation
  owner;
- conversion target bindings are absent or ambiguous after lowering;
- contiguous versus another memory behavior cannot be distinguished through
  the typed memory contract;
- alignment-control meaning is available only by adding a new facade-local
  source-name literal;
- a renderer would still need to inspect an operation enum, scalar catalog
  metadata, candidate inventory, or a delegate set to choose behavior;
- exact arm planning would require a generic Rust AST or complete body strings;
- removing validation/artifact double planning requires a pipeline-wide
  request/result wrapper or cache;
- preserving the current public or lower-level API conflicts with correctness.

## Deferred decisions

The following remain separate decisions and must not change incidentally:

- whether an unknown valid overload axis excludes only that facade item or
  rejects the Rust facade plan;
- adding non-contiguous memory-addressing kinds;
- moving multiline wrapper formatting into assets;
- typing implementation safety-reason labels;
- consolidating the repeated fixed-width set;
- publishing or ratcheting facade coverage as a separate artifact;
- eliminating validation-pass/artifact-pass planning duplication across the
  generic backend pipeline;
- any broader algorithm-facade redesign beyond typed contiguous-memory
  classification.

## Delivery strategy

Land one slice per reviewable commit unless two adjacent steps are inseparable
to keep the generated crate compiling. Slices 1-6 change behavior or ownership;
Slice 7 is intentionally mechanical; Slice 8 is a narrow lifecycle cleanup;
Slice 9 is the release/design gate.

Every review packet states:

- the single outcome delivered;
- typed facts consumed and their owners;
- models, planners, renderers, or shared classifiers changed;
- focused and broad tests run;
- generated toolchain/hardware skips;
- stop conditions encountered;
- follow-ups deliberately deferred.

Do not begin the planner split until role ordering, fallback ownership,
conversion pairs, typed memory classification, signature policy, and finalized
implementation arms are all covered by focused passing tests.
