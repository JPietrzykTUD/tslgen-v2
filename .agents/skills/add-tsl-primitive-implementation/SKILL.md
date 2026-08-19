---
name: add-tsl-primitive-implementation
description: Add, complete, or refactor a specialization of an existing TSL primitive. Use when asked to add an implementation body for a specific extension, profile, type group, or backend; replace scattered intrinsic recipes with semantic TSL-primitive composition; close a missing coverage slot; or fix generated build/value-test gaps in existing primitive source data.
---

# Add TSL Primitive Implementation

## Semantic Boundary Rule

- Let the primitive being implemented own an exact intrinsic that implements its complete contract.
- Otherwise split the recipe into semantic operations and irreducible target mechanics. Express every semantic operation through a TSL primitive; do not inline that primitive's intrinsic recipe in the caller.
- Keep representation shuffles, lane plumbing, mask packing, ABI adaptation, and immediate-only mechanics local when they have no useful target-independent contract.
- Add a precursor primitive only for a stable, independently testable semantic operation. Repetition is evidence, not sufficient justification; never add a primitive merely to name an intrinsic sequence.
- Treat adding a primitive as a public-corpus decision. Propose its contract and semantic names, but obtain TSL-maintainer approval before adding it unless the user has already authorized that prerequisite explicitly.

## Workflow

1. Read `AGENTS.md`, `CHARTER.md`, `PLANS.md`, `tsldata/AGENTS.md`,
   `tslc/AGENTS.md`, `tslc/CHARTER.md`, the target primitive source file, and
   the closest existing implementations for the same primitive family and
   extension family.
2. Identify the exact coverage gap: primitive, signature shape, attributes, mask policy, extension/profile, data type or type group, backend, and failing render/build/value evidence.
3. Audit the supported matrix from current catalog data, the real `Selector`,
   support policy, generated profiles, and backend capabilities. Implement and
   verify the requested affected slots; broaden only when an honest shared
   abstraction requires it. Keep every other unsupported combination explicit
   rather than pretending it works.
4. Choose the implementation strategy in this priority order:
   - A direct exact leaf when one operation implements the complete primitive
     contract for the concrete extension/type/backend: a hardware intrinsic for
     a hardware extension, or a compiler-capability-gated builtin for a
     compiler-vector overlay.
   - For the fixed-width C++ compiler-vector overlays (`clang_v128`,
     `clang_v256`, `clang_v512`, and their `_bool` mask-policy variants), use
     an exact compiler builtin under the first rule when one is available.
     Otherwise, always prefer a feature-gated call through the selector's
     exact-width `vector::fixed` hardware facade when that hardware primitive
     has a native leaf. Keep an overlay-owned lane/generic body as the final
     fallback for profiles without that native leaf. Declare all affected
     widths and mask-policy identities explicitly: do not rely on extension
     inheritance, because a wider or alternate-mask overlay could otherwise
     select a narrower ancestor's satisfied native requirements. Preserve any
     independently typed vector operand with `vector::fixed(Base)` before the
     semantic primitive call.
   - Otherwise, decompose the implementation into independently meaningful, target-independent semantic operations. Call an existing TSL primitive for every such operation, preserving signedness, floating behavior, masks, lanes, safety, undefined-behavior rules, immediates, and attributes. Do not reproduce that primitive's intrinsic implementation in the parent body.
   - When a required semantic operation is absent, search for aliases and near-duplicates, then propose it as a precursor primitive. Specify its observable contract, signature, attributes, tests, dependency direction, and candidate semantic names; obtain the approval required by step 6; add, implement, and verify it before returning to the requested specialization.
   - A documented target-local intrinsic sequence only for irreducible mechanics that cannot be represented honestly by existing primitives and do not define a useful independent TSL operation. Keep the sequence in the primitive that owns those semantics, state why no semantic primitive fits, and keep each exact intrinsic use at the lowest possible leaf. Do not create a public primitive solely to hide an ISA-specific recipe.
   - Explicit fallback through the generic extension, using the repo's existing array round-trip/generic-call pattern only when `to_array`, `from_array`, generic dispatch, and the target backend are available for the slot.
   - Deterministic unsupported diagnostic or skip explaining why the specialization cannot be implemented.
5. Sketch the primitive-call dependency direction before editing and identify which implementations terminate in exact intrinsic or generic leaves. Keep the graph acyclic: a precursor must not directly or transitively depend on the primitive being implemented. If implementing `A` through new primitive `B` would produce `A -> B -> A`, do not add `B` as a wrapper. Instead factor a lower-level operation below both, make one side an honest leaf, use an existing generic fallback, or stop and report the missing abstraction. Never rely on profile, type, backend, or selection conditions to make a catalog cycle harmless.
6. Treat a new primitive as public domain vocabulary. Name it after observable semantics, never after an intrinsic, ISA, register shape, algorithm, or implementation recipe. The skill may recommend a contract, signature, attributes, and preferred name, but a TSL maintainer owns the decision to add it. Proceed without another checkpoint only when the user already authorized the prerequisite primitive explicitly.
7. Update `.tsl` source data first. Do not add renderer or backend hacks to compensate for missing primitive bodies, malformed source, or unsupported semantics.
8. Add or update value tests that exercise the specialization's real edge cases: width, sign, floating corner behavior, masks, zero/pass-through policy, shift counts, immediates, lane order, and aliasing or alignment when relevant.
9. Verify the implementation renders, builds, and passes generated value tests
   for every backend/language/profile/type affected by the change. Treat skipped
   generated cases as verification gaps that must be summarized, not as silent
   success. Preserve shared selected/skipped ordering and coverage identity.

## Checks

- Complete supported coverage is the target; unsupported coverage must remain explicit, deterministic, and explainable.
- Prefer an exact intrinsic at a semantic leaf, but do not use an intrinsic unless its semantics match the TSL primitive contract.
- For each fixed-width Clang overlay and `_bool` variant, verify the ordered
  choice directly: capability-gated exact builtin, otherwise feature-gated
  exact-width native facade, otherwise an overlay-owned portable fallback.
  Include selection provenance plus generated Clang value evidence for both
  comparison-vector and Boolean-vector mask policies.
- Primitive composition must go through `call<...>` or other typed TSIL regions, not raw target-language rewrites.
- Do not duplicate the intrinsic implementation of an operation that already has a suitable TSL primitive.
- Do not create one primitive per intrinsic. Promote independently meaningful target-independent operations; keep representation shuffles, lane plumbing, and mask packing local when they have no honest standalone contract.
- Treat a proposed composed primitive as domain vocabulary, not code deduplication. Add it when the combination itself has stable target-independent semantics, an independently testable contract, useful meaning beyond hiding one ISA recipe, and an acyclic dependency direction. Recurrence is supporting evidence, not the definition, and an arbitrary second call site is not required when the semantic boundary is already clear.
- Keep an algorithmic recipe in the parent primitive when the combination has no useful semantics of its own.
- Search for semantic aliases and near-duplicates before adding a primitive. Keep primitive names independent of the implementation technology.
- Generic fallback is a last-resort implementation strategy, not a substitute for available hardware semantics.
- Do not broaden a slice into a primitive-family rewrite unless the missing helper primitive or source shape is required to make the requested specialization honest.
- Keep generated output deterministic and source-located diagnostics actionable for TSL authors.

## Intrinsic Research

- Look at nearby `.tsl` implementations first; local source data often shows established suffixes, masks, type groups, and extension fallbacks.
- Check existing backend helpers and translation data under `tslc/src/tslc/backend/` before inventing new intrinsic spelling or feature-gating conventions.
- Use official vendor references for semantics:
  - Intel Intrinsics Guide for x86, SSE, AVX, AVX2, and AVX-512.
  - Arm ACLE and Arm Neon/SVE intrinsic references for NEON and SVE.
  - Intel oneAPI, DPC++, SYCL, and FPGA documentation for oneAPI FPGA-oriented implementations.
- Use compiler headers and generated build errors to confirm availability or spelling, not as the primary semantic source.
- Verify signedness, overflow, saturation, rounding, NaN behavior, masks, lane order, shift-count behavior, immediate constraints, and undefined-behavior edges against the TSL contract and value tests.
- If intrinsic semantics or availability are uncertain, consult current official documentation before implementing and mention the source in the final reasoning when it materially affects the choice.

## Stop Conditions

- The requested specialization depends on a missing helper primitive or TSIL/source shape that is larger than the current slice.
- A proposed helper would directly or transitively introduce a primitive-call cycle and no honest lower-level semantic split is clear.
- A new primitive's semantic boundary, public contract, or name is novel or ambiguous and a TSL maintainer has not approved it.
- A proposed primitive would only give a name to one target-specific intrinsic recipe without defining a useful target-independent operation; keep it as a documented leaf implementation or report it as unsupported instead.
- Available intrinsics differ from the primitive's signedness, overflow, floating, mask, lane, or UB semantics and no safe composition exists.
- The value-test oracle is missing or ambiguous for the affected type/profile/backend.
- Required hardware/toolchain verification is unavailable and cannot be covered by SDE, QEMU, FPGA tooling, or an explicit injectable runner.

## Useful Commands

```bash
rg -n "prim<.* NAME|NAME\\(" tsldata/primitives tslc/tests
./dev.sh explain --primitive NAME --profile PROFILE --type TYPE --backend cpp
./dev.sh dump --stage lowered --primitive NAME --profile PROFILE --type TYPE --backend cpp
./dev.sh check --primitive NAME --profile PROFILE --backend cpp --type TYPE
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_catalog_validation.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_select_and_lower*.py tslc/tests/test_lower_text.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_masks_and_calls.py tslc/tests/test_coverage.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_value_test_planning.py
PYTHONPATH=tslc/src python -m pytest -q --run-generated-builds tslc/tests/test_build_verify.py tslc/tests/test_value_tests.py
./dev.sh build --primitives NAME --profiles PROFILE --backends cpp,rust
./dev.sh test --primitives NAME --profiles PROFILE --backends cpp,rust
```
