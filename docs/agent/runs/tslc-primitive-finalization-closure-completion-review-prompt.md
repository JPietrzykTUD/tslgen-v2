# TSLc Primitive Finalization Closure Completion Review Prompt

## Accepted State

The active implementation line is `tslc/` with source data under `tsldata/`.
Recent accepted work includes C++/Rust value-test parity, SDE-backed test
execution, default profile selection across all machine profiles, and the
primitive-by-primitive finalization campaign.

This review covers the closure-completion slice after the earlier
`reinterpret`, `compress`, `cast`, `hand`, `hor`, `lzc_scalar`, and `to_array`
micro-slices. The selected C++/Rust corpus now reports zero skipped slots in
the regenerated primitive coverage inventory.

## Read First

- `AGENTS.md`
- `PLANS.md`
- `docs/agent/current-redesign-state.md`
- `docs/agent/tslc-vector-query-handoff.md`
- `docs/redesign/primitive-coverage-inventory.md`
- `docs/agent/review-checklist.md`

## Review Scope

Review these files:

- `tsldata/primitives/misc/blend.tsl`
- `tsldata/primitives/mask/construct.tsl`
- `tsldata/primitives/conversion/mask_specific.tsl`
- `tsldata/primitives/bitwise/bit_ops.tsl`
- `tsldata/primitives/bitwise/horizontal.tsl`
- `tsldata/primitives/comparison/fundamental.tsl`
- `tslc/tests/test_coverage.py`
- `docs/redesign/primitive-coverage-inventory.md`
- `docs/agent/tslc-vector-query-handoff.md`
- `docs/agent/current-redesign-state.md`

The broader dirty worktree also contains earlier primitive-finalization
changes. Keep this review focused on the closure-completion additions unless a
new issue crosses the same boundary.

## What Changed

- `blend` has an AVX-only array-roundtrip fallback. This is used by
  AVX-profile masked `mov` composition and avoids adding `_vl` workaround
  bodies where base inheritance is sufficient.
- `mask_true` and `mask_false` no longer rely on an unsupported `default`
  requirement key for SSE. The SSE type groups are explicit.
- `to_integral` has an AVX2 arithmetic fallback that uses `mask<test>` over
  `vector::length`.
- AVX-512 float `binary_and`, `binary_or`, and `binary_xor` reinterpret through
  the signed carrier matching the current base width instead of hard-wiring a
  64-bit carrier.
- `inv` float requirements now match the AVX-capable callees it composes.
- SSE `equal` and `less_than` have SSE2-compatible 64-bit lane-array fallbacks.
  `nequal` now composes those comparisons on SSE64.
- SSE64 `to_mask` uses lane-array mask construction instead of requiring SSE4.1
  `cmpeq_epi64`.
- AVX-512 float `hor` bodies now use canonical
  `var<typed>(UnsignedT, result, ...)` TSIL declarations instead of raw C-style
  declarations that rendered invalid Rust once full-corpus build coverage
  reached those bodies.
- The regenerated primitive coverage inventory reports `89 verified, 0 lowers,
  0 partial, 0 none; 67232/67232 slots`.
- `test_coverage.py` now treats the selected `add`/`hadd`/`cast` sample as a
  no-gap coverage regression and asserts strict generation succeeds when no
  support gaps remain.

## Review Questions

- Are all changes source-owned data/body/requirement fixes rather than
  production compiler special cases?
- Does the slice respect the inheritance rule: `avx2_vl` inherits usable
  `avx2` bodies and `sse_vl` inherits usable `sse` bodies, with explicit child
  bodies reserved only for genuinely different AVX-512VL representations?
- Are AVX-only fallbacks justified by existing callees and requirements, not by
  widening a requirement beyond what the body can actually execute?
- Do the SSE64 comparison and `to_mask` fallbacks remain KISS: existing
  lane-array/from-array primitives, no new testing DSL, no renderer semantic
  inference?
- Does the `hor` declaration cleanup preserve source-body integrity by using
  accepted TSIL declaration forms instead of teaching Rust rendering to repair
  raw C-style declarations?
- Does the regenerated inventory prove zero selected-corpus skips for the
  current profile/backend/type probe, and is it generated rather than
  hand-edited?
- Are validation commands proportionate to the risk and do they cover both
  planning/coverage and actual generated C++/Rust test execution?

## Validation To Run

```bash
python -m compileall -q tslc/src/tslc
python -m pytest -q tslc/tests/test_build_verify.py::test_full_corpus_builds
python -m pytest -q tslc/tests/test_value_tests.py::test_value_full_corpus_avx2_coverage_is_complete tslc/tests/test_value_tests.py::test_value_full_corpus_avx2_rust_parity_inventory_is_explicit tslc/tests/test_build_verify.py::test_masked_memory_build tslc/tests/test_build_verify.py::test_to_mask_builds
PYTHONPATH=tslc/src python -m tslc.maintenance.coverage_inventory
git diff --check
./verify.sh
```

Runtime smoke already run during implementation and may be rerun:

```bash
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --primitives blend,mov,load,mask_true,mask_false,to_integral,to_mask,store_mask_repr,load_mask_repr,lzc_imask,tzc,binary_and,binary_or,binary_xor,inv,equal,nequal,less_than,hor --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --output-root ./tslctmp/TEST --test --value-test-warnings --sde /opt/intel-sde/sde64
```

Expected result: C++ and Rust value tests pass for all SDE-annotated x86
profiles; `neon` is visibly skipped because there is no x86 SDE chip alias.

The stronger all-primitive default-path smoke was also run:

```bash
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --output-root ./tslctmp/FULL --test --value-test-warnings --sde /opt/intel-sde/sde64
```

Expected result: omitting `--primitives` generates all primitives by default,
C++ and Rust value tests pass for SDE-annotated x86 profiles, `neon` is visibly
skipped, and the command reports `build/test-verified 152 commands`.

## Output Format

Return one of:

- `Accept`
- `Accept With Follow-Ups`
- `Needs Revision`
- `Return To Planner`

Lead with findings. If accepted, recommend the next primitive-finalization
target from the current coverage inventory or say explicitly that the current
inventory has no selected-corpus skips left.

## Stop Rule

Do not implement the next primitive in this review prompt. Do not modify
production code unless the user explicitly changes this from review to
revision.
