# Review Prompt: Native NEON Fixed-Width Codegen Slice

You are reviewing the completed `tslc` native NEON codegen slice.

## Scope Under Review

The slice should make `neon` actually emit native fixed-width extension
substrates:

- C++: `tsl::simd<T, tsl::neon>` with register types from
  `vector_register_types` and `<arm_neon.h>`;
- Rust: `Simd<T, Neon>` with register types from `vector_register_types` and
  ARM arch imports;
- support policy admits fixed-width `arm` extension substrates;
- SVE/scalable-vector emission remains deferred.

## Files To Inspect

- `tslc/src/tslc/catalog/model.py`
- `tslc/src/tslc/catalog/builder.py`
- `tslc/src/tslc/backend/translation_common.py`
- `tslc/src/tslc/backend/rust_translation.py`
- `tslc/src/tslc/lower/lowerer.py`
- `tslc/src/tslc/lower/region_handlers/intrinsics.py`
- `tslc/src/tslc/render/_common.py`
- `tslc/src/tslc/render/cpp_project.py`
- `tslc/src/tslc/render/rust_project.py`
- `tslc/src/tslc/select/selector.py`
- `tslc/src/tslc/support_policy.py`
- `tsldata/primitives/conversion/cast.tsl`
- `tsldata/primitives/load_store/construct.tsl`
- `tsldata/primitives/misc/blend.tsl`
- `tslc/tests/test_catalog.py`
- `tslc/tests/test_profile_rendering.py`
- `docs/redesign/design-decisions.md`
- `docs/agent/tslc-vector-query-handoff.md`
- `docs/agent/current-redesign-state.md`

## Review Questions

- Does native extension register spelling flow from typed catalog metadata
  instead of hard-coded extension names?
- Do C++ and Rust renderers only format already-decided register/header facts,
  rather than classifying primitive or extension semantics locally?
- Is enabling `arm` constrained to fixed-width substrates, with SVE/scalable
  vectors still deferred?
- Is `LoweredSpecialization.register_spelling` a justified lowered fact rather
  than another broad catch-all field?
- Are the source-data fixes (`blend`, `reinterpret`, `set_undef`) semantic TSIL
  cleanups rather than renderer/source-repair hacks?
- Are diagnostics and skips still explicit for unsupported scalable-vector
  cases?
- Are the tests sufficient to prevent regression to fallback-only NEON
  coverage?

## Required Validation

Run or verify current evidence for:

```bash
python -m compileall -q tslc/src/tslc
python -m pytest -q tslc/tests/test_catalog.py tslc/tests/test_profile_rendering.py tslc/tests/test_value_test_planning.py tslc/tests/test_safety_contract.py
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --profiles neon --primitives add --backends rust --output-root /tmp/tslc-neon-native-test --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64
./verify.sh
git diff --check
```

Note: C++ NEON runtime verification is not expected to pass in this environment
unless a clang-compatible aarch64 C++ sysroot is installed. The C++ requirement
for this slice is native artifact generation and render-shape regression
coverage.

## Verdict Format

Return one of:

- `Accept`
- `Accept With Follow-Ups`
- `Needs Revision`
- `Return To Planner`
- `Reject`

List findings first, ordered by severity, with file/line references. Then give
the verdict and any required follow-up prompts.
