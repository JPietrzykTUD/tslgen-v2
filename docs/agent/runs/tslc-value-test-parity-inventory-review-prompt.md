# TSLc Value-Test Parity Review Prompt

## Goal

Review the current value-test completeness slice: typed C++/Rust AVX2 parity
for the full authored corpus, including coverage accounting, Rust renderer
parity, source-owned Rust warning cleanup, and the promoted full-corpus Rust
value-test execution gate.

## Scope

Files to inspect:

- `tslc/src/tslc/value_tests/model.py`
- `tslc/src/tslc/value_tests/coverage.py`
- `tslc/src/tslc/value_tests/__init__.py`
- `tslc/src/tslc/api.py`
- `tslc/src/tslc/cli.py`
- `tslc/src/tslc/pipeline.py`
- `tslc/src/tslc/value_tests/render_rust.py`
- `tslc/src/tslc/value_tests/_render_rust_helpers.py`
- `tslc/src/tslc/value_tests/_render_rust_memory.py`
- `tslc/src/tslc/value_tests/_render_rust_conversion.py`
- `tslc/src/tslc/value_tests/literals.py`
- `tslc/src/tslc/value_tests/case_helpers.py`
- `tslc/src/tslc/value_tests/_case_core.py`
- `tslc/tests/test_value_test_planning.py`
- `tslc/tests/test_value_tests.py`
- `tslc/tests/test_cli.py`
- `tsldata/primitives/load_store/sequence.tsl`
- `tsldata/primitives/misc/conflict.tsl`
- `tsldata/primitives/memory/copy.tsl`
- `tsldata/primitives/load_store/rnd_access.tsl`
- `tsldata/primitives/comparison/fundamental.tsl`
- `docs/redesign/design-decisions.md`
- `docs/agent/current-redesign-state.md`
- `docs/agent/tslc-vector-query-handoff.md`

Background files:

- `tslc/src/tslc/value_tests/planner.py`
- `tslc/src/tslc/value_tests/render_cpp.py`
- `tslc/src/tslc/value_tests/render_cpp_helpers.py`
- `tslc/src/tslc/value_tests/case_plans.py`
- `tslc/src/tslc/render/project.py`

## Expected Design

- Coverage status is a typed value-test planning concept, not renderer logic.
- Coverage records carry the planned case kind when a case was accepted by the
  planner, so later Rust parity slices can group gaps by typed plan kind.
- `ValueTestParityEntry` groups already-decided per-backend coverage outcomes
  for one authored test identity.
- `parity_inventory(...)` and `parity_gaps(...)` are deterministic helpers over
  existing `ValueTestCoverageEntry` records; they should not inspect the
  catalog, select primitives, or render source.
- The full-corpus AVX2 parity test requests C++ and Rust together and requires
  zero `missing_authored_tests`, zero `authored_unplanned`, zero
  `backend_unsupported`, matching emitted case counts, and no parity gaps.
- Rust supports every current planned full-corpus AVX2 case kind. Its declared
  support set must match the renderer dispatch table.
- Rust renderer modules are formatters of `ValueTestCasePlan`; they may know
  Rust syntax and helper names, but not primitive/source family semantics.
- Source-body warning fixes should stay source-owned. The renderer should not
  learn primitive-specific warning suppression or source repair.
- The split Rust renderer modules should remain cohesive and below monolith
  pressure; the main renderer should remain an orchestration/dispatch surface.
- C++ behavior and the existing full-corpus C++ value gate must remain intact.
- Omitting `--primitives` should exercise every loaded catalog primitive. The
  CLI should delegate that default to the API/pipeline rather than scanning
  source data itself.
- `--test` should fail on any verifier diagnostic, even when the underlying
  verifier records value-test command failures as warning-severity diagnostics
  for API callers.

## Validation Already Run

```bash
python -m compileall -q tslc/src/tslc/value_tests
```

Result: passed.

```bash
python -m pytest -q tslc/tests/test_cli.py
```

Result: `4 passed`.

```bash
python -m pytest -q tslc/tests/test_value_test_planning.py tslc/tests/test_value_tests.py
```

Result: `19 passed`.

Full Rust AVX2 value-test execution smoke over all 89 selected primitives:

```text
coverage: rust compile_only_emitted=1, rust emitted=1107
verify diagnostics: 0
warning markers: 0
```

```bash
./verify.sh
```

Result: passed all targeted validations, including 214 non-build tests and 53
generated-build tests.

## Review Questions

1. Does typed parity accounting stay inside the value-test planning/coverage
   boundary?
2. Is Rust parity genuinely enforced by typed plan data, rather than by
   generated-source regexes or primitive-name checks?
3. Are the Rust renderer modules cohesive formatting modules, or did semantic
   planning leak into them?
4. Are the source warning fixes legitimate source-body improvements rather than
   renderer/source repair shortcuts?
5. Does this remain KISS/DRY/OOP enough for the next value-test expansion?

## Expected Verdict

Return one of:

- `Accept`
- `Accept With Follow-Ups`
- `Needs Revision`
- `Return To Planner`
- `Reject`

For any non-`Accept` verdict, include concrete findings with file/line
references and the smallest recommended next action.
