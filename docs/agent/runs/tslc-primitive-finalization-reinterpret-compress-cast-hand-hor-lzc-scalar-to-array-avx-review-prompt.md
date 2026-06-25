# TSLc Primitive Finalization Review Prompt

## Accepted State

The active implementation line is `tslc/` with source data under `tsldata/`.
Recent accepted work includes value-test parity, SDE-backed test execution,
default profile selection across all machine profiles, and the primitive-by-
primitive finalization campaign.

This review covers finalized primitives `reinterpret`, `compress`, `cast`,
`hand`, `hor`, `lzc_scalar`, and the AVX-profile `to_array` requirement fix.
The `cast` slice also removes the same call-type-args gap from `convert_down`.

## Read First

- `AGENTS.md`
- `PLANS.md`
- `docs/agent/current-redesign-state.md`
- `docs/agent/tslc-vector-query-handoff.md`
- `docs/redesign/primitive-coverage-inventory.md`
- `docs/agent/review-checklist.md`

## Review Scope

Review these files:

- `tslc/src/tslc/syntax/parser.py`
- `tslc/src/tslc/lower/region_handlers/calls.py`
- `tslc/src/tslc/lower/queries.py`
- `tslc/src/tslc/backend/rust_translation.py`
- `tslc/src/tslc/maintenance/coverage_inventory.py`
- `tslc/tests/test_parse_arithmetic.py`
- `tslc/tests/test_masks_and_calls.py`
- `tslc/tests/test_select_and_lower.py`
- `tslc/tests/test_generation_conditionals.py`
- `tslc/tests/test_build_verify.py`
- `tsldata/primitives/bitwise/bit_counts.tsl`
- `tsldata/primitives/conversion/cast.tsl`
- `tsldata/primitives/load_store/array.tsl`
- `tsldata/primitives/misc/compress.tsl`
- `docs/redesign/primitive-coverage-inventory.md`
- `docs/agent/tslc-vector-query-handoff.md`
- `docs/agent/current-redesign-state.md`

## What Changed

- Inline implementation body envelopes now use decoded scalar text for
  `payload_text`, while preserving raw `payload_source` spans for diagnostics.
- The x86 `reinterpret` `f? -> f?` body now uses the no-instruction bitcast
  path instead of non-existent same-type cast intrinsics.
- The scalar `compress` body now uses `complete(result)` instead of raw
  target-language `return` statements.
- `compress` has an AVX-512VL byte/word fallback that converts native predicate
  masks through `to_integral[Vec]` before testing bits.
- `CallLowerer` now accepts decimal integer call-bracket entries as forwarded
  template/const arguments.
- `QueryEvaluator` resolves zero-argument `x86::...` backend value leaves
  through backend translation templates named `value_...`.
- `cast` uses portable array round-trip fallbacks for AVX2 `f32 -> ui32` and
  SSE `f32/f64 -> ?i32` paths where previous bodies used unavailable AVX-512VL
  or SSE4.1 instructions.
- `QueryEvaluator` now supports narrow typed `select(cond, then, else)` folding
  for generation-time values. This clears float carrier-type queries in `hand`,
  `hor`, and `lzc_scalar`.
- Rust pointer casts of address expressions now render through
  `core::ptr::addr_of!` / `addr_of_mut!` before byte-casting, while ordinary
  pointer expressions keep the existing raw-pointer cast path.
- `lzc_scalar` no longer depends on a `vector::offset_base` query. Its float
  source path initializes an unsigned carrier with `var<infer>`, bit-copies the
  float scalar into that carrier, and calls the width-aware `details::clz(bits)`
  helper directly.
- `to_array` under the `avx2` extension now requires `[avx]` for every integer
  type tag. Its implementation delegates to `store`, which already has AVX-only
  support for every AVX2 integer width, so the previous byte/word `avx2`
  requirement was stricter than the actual implementation.
- The regenerated coverage inventory reports all 89 primitives as `VERIFIED`,
  with `66722 / 67070` lowered slots. Remaining closure-pruned slots dropped
  from 468 to 348.

## Review Questions

- Does using decoded inline scalar text for
  `ParsedImplementationBodyEnvelope.payload_text` preserve the source-body
  integrity boundary?
- Does the parser still keep diagnostics anchored to raw source spans through
  `payload_source`?
- Are the primitive body changes source-owned data fixes rather than compiler
  special casing?
- Are child-extension bodies justified by real representation or capability
  differences? In particular, `avx2_vl` / `sse_vl` inherit usable `avx2` /
  `sse` implementations, so new child bodies should exist only when AVX-512VL
  representation or a better intrinsic path genuinely requires an override.
- Do the `compress`, `cast`, and `to_array` fixes reuse typed primitive calls
  and existing requirement/safety propagation instead of adding renderer or
  lowerer policy?
- Are the `cast` call type-argument, backend value-query, and `select(...)`
  additions generic TSIL/lowering capabilities, not primitive-specific
  branches?
- Is Rust address-expression pointer casting a syntax-only backend spelling
  fix, without changing source semantics or hiding memory behavior in the
  renderer?
- Is dropping the obsolete `lzc_scalar` `vector::offset_base` helper argument
  preferable to adding another compiler query for a value the helpers no longer
  need?
- Does the `to_array` AVX requirement match its delegated `store` callee, and
  does the added `avx` generated-build coverage prove that boundary?
- Did any primitive- or extension-specific behavior leak into `tslc` production
  code?
- Are the updated inventory numbers deterministic and generated by the
  maintenance tool rather than hand-edited?
- Are tests and per-primitive SDE runs proportionate to the risk of these
  changes?

## Validation To Run

```bash
python -m compileall -q tslc/src/tslc/syntax tslc/src/tslc/lower tslc/src/tslc/backend tslc/src/tslc/maintenance
python -m pytest -q tslc/tests/test_parse_arithmetic.py tslc/tests/test_masks_and_calls.py::test_call_type_args_accept_extension_and_literal_index tslc/tests/test_select_and_lower.py::test_backend_value_query_uses_backend_translation_template tslc/tests/test_generation_conditionals.py tslc/tests/test_build_verify.py::test_to_from_array_roundtrip_builds
git diff --check
```

Runtime smokes already run during implementation and may be rerun:

```bash
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --primitives reinterpret --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --output-root ./tslctmp/TEST --test --value-test-warnings --sde /opt/intel-sde/sde64
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --primitives compress --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --output-root ./tslctmp/TEST --test --value-test-warnings --sde /opt/intel-sde/sde64
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --primitives cast --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --output-root ./tslctmp/TEST --test --value-test-warnings --sde /opt/intel-sde/sde64
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --primitives hand --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --output-root ./tslctmp/TEST --test --value-test-warnings --sde /opt/intel-sde/sde64
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --primitives lzc_scalar --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --output-root ./tslctmp/TEST --test --value-test-warnings --sde /opt/intel-sde/sde64
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --primitives to_array,from_array --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --output-root ./tslctmp/TEST --test --value-test-warnings --sde /opt/intel-sde/sde64
```

Expected result: C++ and Rust value tests pass for all SDE-annotated x86
profiles; `neon` is visibly skipped because there is no x86 SDE chip alias.

## Output Format

Return one of:

- `Accept`
- `Accept With Follow-Ups`
- `Needs Revision`
- `Return To Planner`

Lead with findings. If accepted, recommend the next primitive-finalization
target from the current coverage inventory. The current inventory has no
non-closure skip category left; remaining skips are dependency-closure drops.

## Stop Rule

Do not implement the next primitive in this review prompt. Do not modify
production code unless the user explicitly changes this from review to
revision.
