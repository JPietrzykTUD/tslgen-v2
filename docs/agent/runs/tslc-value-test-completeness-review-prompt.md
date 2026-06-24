# TSLc Value-Test Completeness Review Prompt

You are reviewing the implemented value-test completeness slice in `tslc/`.
Use `docs/agent/review-checklist.md` and the main design principles from
`AGENTS.md`.

## Context

The slice makes value-test completeness a typed planning contract:

- source tests promote inputs to typed `vector`, `mask`, or `scalar` arguments;
- source tests support `role "value"` and `role "compile"`;
- `ValueTestProjectPlan.coverage` records emitted, compile-only, missing,
  unplanned, and backend-unsupported outcomes;
- the full C++ AVX2 corpus test asserts zero missing/unplanned/unsupported
  applicable cases;
- C++ value-test planning covers new typed shapes without primitive-name
  classifiers;
- Rust remains narrower and must report unsupported kinds honestly;
- oversized value-test modules were split into `case_helpers.py` and
  `render_cpp_helpers.py`.

ADR-086 records the design decision.

## Files To Review

- `tslc/src/tslc/catalog/model.py`
- `tslc/src/tslc/catalog/builder.py`
- `tslc/src/tslc/catalog/validation/schema_validation.py`
- `tslc/src/tslc/render/project.py`
- `tslc/src/tslc/value_tests/model.py`
- `tslc/src/tslc/value_tests/coverage.py`
- `tslc/src/tslc/value_tests/planner.py`
- `tslc/src/tslc/value_tests/patterns.py`
- `tslc/src/tslc/value_tests/case_plans.py`
- `tslc/src/tslc/value_tests/case_helpers.py`
- `tslc/src/tslc/value_tests/render_cpp.py`
- `tslc/src/tslc/value_tests/render_cpp_helpers.py`
- `tslc/src/tslc/value_tests/render_rust.py`
- `tslc/tests/test_catalog_tests.py`
- `tslc/tests/test_value_test_planning.py`
- `tslc/tests/test_value_tests.py`
- affected `tsldata/primitives/**/*.tsl` test edits
- `docs/redesign/design-decisions.md`
- `docs/agent/tslc-vector-query-handoff.md`

## Review Focus

Prioritize findings where the implementation violates:

- primitive- and extension-agnostic behavior;
- KISS / prototype-first scope;
- typed boundaries after catalog promotion;
- DRY ownership of support policy, coverage, and render facts;
- semantic logic before rendering;
- diagnostics over silent behavior;
- deterministic plans, coverage, and generated names;
- maintainability/module-size guardrails;
- extensibility by typed source data rather than primitive-name branches.

Pay special attention to whether profile-specific authored tests are skipped
only when the selected typed specialization set truly does not contain that
case, and whether C++ renderers format already-decided `ValueTestCasePlan`
fields instead of inspecting catalog/source semantics.

## Suggested Validation

```bash
python -m compileall -q tslc/src/tslc
python -m pytest -q tslc/tests/test_catalog_tests.py tslc/tests/test_value_test_planning.py tslc/tests/test_value_tests.py::test_value_full_corpus_avx2_coverage_is_complete
python -m pytest -q tslc/tests/test_value_tests.py
./verify.sh
```

Architecture scan:

```bash
rg -n 'primitive_name ==|source_primitive_name ==|case\\.call_name ==|from_array|to_array|to_integral|avx2|avx512|sse|neon|_is_.*primitive|_is_.*case' tslc/src/tslc/value_tests tslc/src/tslc/render
```

Expected result: no production value-test behavior branches on known source
primitive or extension identities. Literal helper names supplied by plans, test
expectations, comments, and source data references are acceptable if they do not
drive semantic classification.

## Expected Verdict

Return `Accept`, `Accept With Follow-Ups`, `Needs Revision`, `Return To
Planner`, or `Reject`. Findings should include concrete file/line references
and distinguish blocking design issues from acceptable prototype debt.
