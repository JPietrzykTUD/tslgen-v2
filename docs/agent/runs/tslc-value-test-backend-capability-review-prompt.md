# TSLc Value-Test Backend Capability Review

## Scope Under Review

Review the value-test backend capability cleanup layered on top of the
lane-list `set` migration.

The intended final state:

- `ValueTestPattern` remains semantic and backend-agnostic.
- Patterns do not carry `backend_ids` or concrete backend names.
- Backend renderers declare `ValueTestBackendSupport` values describing the
  `ValueTestCasePlan.kind` variants they can consume.
- Differential value tests are enabled by backend capability rather than a
  language-name branch in generic planning.
- `ValueTestProjectPlan` stores backend profile plans generically, and artifact
  assembly asks for plans by backend ID.
- Concrete C++/Rust wiring remains only in generated-project assembly and
  renderer modules.

## Review Checklist

Use `docs/agent/review-checklist.md`. Pay special attention to:

- no semantic value-test pattern depends on `cpp` or `rust`;
- planner diagnostics and duplicate detection remain deterministic;
- C++/Rust value-test coverage is unchanged;
- `render/tests_project.py` remains an assembler only;
- the cleanup does not hide backend selection or rendering behind patterns.

## Suggested Validation

```bash
python -m compileall -q tslc/src/tslc tslc/tests
python -m pytest -q tslc/tests/test_value_test_planning.py
python -m pytest -q tslc/tests/test_value_test_planning.py tslc/tests/test_value_tests.py tslc/tests/test_lane_lists.py tslc/tests/test_support_policy.py tslc/tests/test_build_verify.py::test_set_builds
git diff --check
```

Run a source scan:

```bash
rg -n "backend_ids|backend_id == \"cpp\"|backend_id == \"rust\"|cpp_profiles|rust_profiles" tslc/src/tslc/value_tests tslc/src/tslc/render/tests_project.py
```

The scan should have no production hits in semantic value-test planning.

## Expected Verdict

Return one of:

- `Accept`
- `Accept With Follow-Ups`
- `Needs Revision`
- `Return To Planner`
