# TSLc Lane-List `set` Migration Review

## Scope Under Review

Review the completed lane-list `set` migration in `tslc/` and `tsldata/`.

The intended final state:

- `set` is authored as `prim<v:=(lanes<s>)> set(values):`.
- `lanes<s>` is one named lane-list parameter, not a generated parameter pack.
- `lanes<at>(values, N)` accepts generation-time integer indexes, including
  symbols bound by `loop<generation>`.
- `loop<generation>(i, start, end, step) { ... }` expands in the generator and
  leaves `loop<range>` semantics unchanged.
- Current reverse `set` value behavior is preserved explicitly in source.
- C++ no longer exposes a public variadic `set` wrapper.
- Rust receives the same array-like lane-list argument shape.
- Value-test planning includes `v:=(lanes<s>)`.
- Old `s...`, `arg_count(...)`, `pack<expand>`, and `pack<first>` production
  paths are removed or quarantined.

## Review Checklist

Use `docs/agent/review-checklist.md`. Pay special attention to:

- no primitive-name or extension-name special casing in generic compiler stages;
- no hidden renderer-side semantic inference for lane-list behavior;
- generation-time integer evaluation is narrow and diagnostic-driven;
- `loop<generation>` does not change `loop<range>`;
- source migration did not reduce value-test coverage for `set`;
- old variadic paths are genuinely gone from active production flow.

## Suggested Validation

```bash
python -m compileall -q tslc/src/tslc tslc/tests
python -m pytest -q tslc/tests/test_lane_lists.py
python -m pytest -q tslc/tests/test_value_test_planning.py tslc/tests/test_value_tests.py
python -m pytest -q tslc/tests/test_select_and_lower.py tslc/tests/test_masks_and_calls.py
python -m pytest -q tslc/tests/test_support_policy.py tslc/tests/test_catalog_validation.py
python -m pytest -q tslc/tests/test_build_verify.py::test_set_builds
git diff --check
```

Also run source scans for old transition forms:

```bash
rg -n "arg_count\\(|pack<expand>|pack<first>|variadic_scalar_kind|variadic_lanes|render_pack" tslc/src tslc/tests tsldata
rg -n "prim<v:=s\\.\\.\\.>|s\\.\\.\\." tsldata tslc/src
```

The only acceptable remaining old-form references should be explicit rejection
tests or quarantine notes.

## Expected Verdict

Return one of:

- `Accept`
- `Accept With Follow-Ups`
- `Needs Revision`
- `Return To Planner`

If accepted, prepare a small follow-up prompt only if review finds worthwhile
cleanup beyond the current goal.
