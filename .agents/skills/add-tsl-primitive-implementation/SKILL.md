---
name: add-tsl-primitive-implementation
description: Add or complete a specialization of an existing TSL primitive. Use when Codex is asked to add a primitive implementation body for a specific extension, profile, type group, backend, or missing coverage slot, or to close generated build/value-test gaps for existing primitive source data.
---

# Add TSL Primitive Implementation

## Workflow

1. Read `AGENTS.md`, `PLANS.md`, `tslc/CHARTER.md`, the target primitive source file, and the closest existing implementations for the same primitive family and extension family.
2. Identify the exact coverage gap: primitive, signature shape, attributes, mask policy, extension/profile, data type or type group, backend, and failing render/build/value evidence.
3. Define the supported matrix from current catalog data, support policy, generated profiles, and existing backend capabilities. Aim to cover every supported extension/profile and data type, but produce explicit diagnostics or skips for unsupported combinations rather than pretending they work.
4. Choose the implementation strategy in this priority order:
   - Direct hardware intrinsic call, when an available intrinsic exactly matches the primitive semantics for the concrete extension/type/backend.
   - Composition of existing primitives, preserving signedness, floating behavior, masks, lanes, safety, undefined-behavior rules, immediates, and attributes. If required helper primitives are missing, add those first as a separate precursor slice unless the dependency is tiny and clearly in scope.
   - Explicit fallback through the generic extension, using the repo's existing array round-trip/generic-call pattern only when `to_array`, `from_array`, generic dispatch, and the target backend are available for the slot.
   - Deterministic unsupported diagnostic or skip explaining why the specialization cannot be implemented.
5. Update `.tsl` source data first. Do not add renderer or backend hacks to compensate for missing primitive bodies, malformed source, or unsupported semantics.
6. Add or update value tests that exercise the specialization's real edge cases: width, sign, floating corner behavior, masks, zero/pass-through policy, shift counts, immediates, lane order, and aliasing or alignment when relevant.
7. Verify the implementation renders, builds, and passes generated value tests for every supported backend/language/profile/type affected by the change. Treat skipped generated cases as verification gaps that must be summarized, not as silent success.

## Checks

- Complete supported coverage is the target; unsupported coverage must remain explicit, deterministic, and explainable.
- Prefer exact intrinsics over clever compositions, but do not use an intrinsic unless the semantics match the TSL primitive contract.
- Primitive composition must go through `call<...>` or other typed TSIL regions, not raw target-language rewrites.
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
- Available intrinsics differ from the primitive's signedness, overflow, floating, mask, lane, or UB semantics and no safe composition exists.
- The value-test oracle is missing or ambiguous for the affected type/profile/backend.
- Required hardware/toolchain verification is unavailable and cannot be covered by SDE, QEMU, FPGA tooling, or an explicit injectable runner.

## Useful Commands

```bash
rg -n "prim<.* NAME|NAME\\(" tsldata/primitives tslc/tests
./dev.sh explain --primitive NAME --profile PROFILE --type TYPE --backend cpp
./dev.sh dump --stage lowered --primitive NAME --profile PROFILE --type TYPE --backend cpp
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_catalog_validation.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_select_and_lower.py tslc/tests/test_lower_text.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_value_test_planning.py
PYTHONPATH=tslc/src python -m pytest -q --run-generated-builds tslc/tests/test_build_verify.py tslc/tests/test_value_tests.py
./dev.sh build --primitives NAME --profiles PROFILE --backends cpp,rust
./dev.sh test --primitives NAME --profiles PROFILE --backends cpp,rust
```
