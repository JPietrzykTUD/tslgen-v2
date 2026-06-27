# Prompt: Review C++ SVE Scalable Value-Test Slice

Do a thorough design review of the C++ SVE scalable value-test implementation.

## Context

The previous slice added the first real SVE lane value cases:

- SVE extension metadata now declares `test_runtime_lanes` for C++;
- value-test harness discovery now finds load/store helpers by typed
  signatures `v:=cptr` and `void:=(ptr,v)`;
- test-mode dependency closure includes those helpers;
- the planner emits `scalable_golden` for C++ scalable all-vector
  value-result cases;
- the C++ renderer uses runtime-sized buffers plus `tsl::load<Vec, false>` /
  `tsl::store<Vec, false>` instead of `array_for<simd<T, sve>>`;
- Rust SVE remains unsupported.

Validation evidence from the implementation slice:

```bash
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_value_test_planning.py::test_harness_discovery_uses_signatures_not_names tslc/tests/test_value_test_planning.py::test_renderers_consume_prebuilt_plans_without_catalog tslc/tests/test_profile_rendering.py::test_sve_profile_registers_scalable_cpp_simd_types
./dev.sh explain --primitive add --profile sve --type si32 --backend cpp --extension sve
TSLC_BACKENDS=cpp TSLC_OUTPUT_ROOT=/tmp/tslc-sve-add-values ./dev.sh test --profiles sve --primitives add --cpp-compiler "/opt/zig/zig c++" --cpp-target aarch64-linux-musl
rg -c 'using Vec = tsl::simd<.*tsl::sve>' /tmp/tslc-sve-add-values/cpp/tests/values_sve.cpp
./dev.sh ratchet
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_value_test_planning.py tslc/tests/test_profile_rendering.py tslc/tests/test_catalog.py tslc/tests/test_catalog_validation.py tslc/tests/test_generation_conditionals.py tslc/tests/test_select_and_lower.py
git diff --check
```

Result: SVE `add` value tests run through QEMU; `values_sve.cpp` contains `36`
true `tsl::simd<..., tsl::sve>` cases.

## Review Questions

- Does `test_runtime_lanes` belong in extension metadata, or should it move to
  a narrower value-test/profile capability object before broadening SVE?
- Does `scalable_golden` stay primitive- and extension-agnostic, or does it
  accidentally assume SVE beyond the source-owned runtime lane expression?
- Is the `HarnessPrimitiveNames` expansion to load/store still cohesive, or
  should harness capabilities become a separate typed value before more helper
  roles are added?
- Does test-mode dependency closure include only helpers needed for generated
  value tests, without changing normal build/generate closure semantics?
- Does the renderer format only render-ready plans, or does it infer semantic
  facts that should live in planning/catalog data?
- Are unsupported scalable shapes visible enough through coverage/diagnostics,
  especially masked cases and mask-result cases that still do not get native
  SVE value checks?
- Are the generated C++ buffers safe for runtime lane counts larger than the
  authored lane list, including integer/floating edge cases?

## Files To Inspect

- `tslc/src/tslc/catalog/model.py`
- `tslc/src/tslc/catalog/builder.py`
- `tslc/src/tslc/catalog/validation/schema_validation.py`
- `tslc/src/tslc/value_tests/harness.py`
- `tslc/src/tslc/value_tests/model.py`
- `tslc/src/tslc/value_tests/_case_core.py`
- `tslc/src/tslc/value_tests/_pattern_core.py`
- `tslc/src/tslc/value_tests/_render_cpp_core.py`
- `tslc/src/tslc/value_tests/_render_cpp_dispatch.py`
- `tslc/src/tslc/value_tests/render_cpp.py`
- `tslc/src/tslc/pipeline.py`
- `tsldata/extensions/extension.tsl`
- `tslc/tests/test_value_test_planning.py`
- `tslc/tests/test_profile_rendering.py`

## Required Checks

Run at least:

```bash
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_value_test_planning.py tslc/tests/test_profile_rendering.py tslc/tests/test_catalog.py tslc/tests/test_catalog_validation.py
TSLC_BACKENDS=cpp TSLC_OUTPUT_ROOT=/tmp/tslc-sve-review ./dev.sh test --profiles sve --primitives add --cpp-compiler "/opt/zig/zig c++" --cpp-target aarch64-linux-musl
rg -n -m 10 'using Vec = tsl::simd<.*tsl::sve>|svcntb\(\)|tsl::load<Vec, false>|tsl::store<Vec, false>' /tmp/tslc-sve-review/cpp/tests/values_sve.cpp
./dev.sh ratchet
git diff --check
```

## Expected Verdict

Return one of:

- `Accept`: design is sound enough to broaden SVE coverage.
- `Needs Revision`: list specific fixes required before broadening.
- `Return To Planner`: the slice chose the wrong boundary and needs redesign.

If accepted, propose the next implementation prompt: likely broadening C++ SVE
value tests to masked all-vector cases and mask-result cases without adding
primitive-name branches.
