# Prompt: Native Register Metadata Guardrail

You are implementing a focused follow-up after the native NEON fixed-width
codegen review.

## Context

The NEON slice was accepted with follow-ups. It correctly promotes
`vector_register_types` and backend headers into typed `Extension` metadata and
uses that data to render native fixed-width NEON C++/Rust substrates.

The review found one maintainability guardrail to add before more non-x86
fixed-width extensions appear: `SupportPolicy.supports_extension(...)` admits
fixed-width `arm` extensions, but backend lowering/rendering should fail early
and diagnostically if a selected non-x86 native extension lacks required
backend register metadata.

Today this is not a runtime defect because the corpus has only fixed-width
`neon` and scalable `sve`; `neon` has metadata and `sve` is deferred. The next
slice should make that invariant explicit.

## Goal

Make native fixed-width extension emission require declared backend register
metadata before lower/render can produce fallback-shaped or late-failing
artifacts.

## Scope

- Add a typed support or validation guard for selected fixed-width non-x86
  native extensions whose `vector_register_types` are missing for an emitted
  backend/type.
- Prefer structured diagnostics at selection/lowering/catalog-validation time
  over render-time surprises or generated-code failures.
- Keep x86 behavior unchanged: x86 register types may continue using the
  existing backend width helpers.
- Keep `scalar`, `generic_like`, and sized-vector substrates unchanged.
- Keep SVE/scalable-vector emission deferred.

## Suggested Tests

- Tiny fake-catalog test: a fixed-width `arm` extension without a Rust or C++
  register spelling should not silently lower to scalar/base register text.
- Regression test: `neon` still emits native C++/Rust register types from
  `vector_register_types`.
- Regression test: `sve` remains skipped/deferred because it is scalable, not
  because of missing register metadata.

## Validation

Run at least:

```bash
python -m compileall -q tslc/src/tslc
python -m pytest -q tslc/tests/test_catalog.py tslc/tests/test_profile_rendering.py tslc/tests/test_select_and_lower.py
git diff --check
```

Run `./verify.sh` if production support/selection/lowering behavior changes
beyond a narrow diagnostic-only guard.

## Out Of Scope

- Do not implement SVE.
- Do not add a C++ aarch64 sysroot installation workflow.
- Do not broaden ARM primitive coverage.
- Do not add renderer-side semantic inference.
