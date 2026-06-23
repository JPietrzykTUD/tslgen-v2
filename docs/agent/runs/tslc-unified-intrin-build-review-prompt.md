# TSLc Unified Intrinsic Build Review

## Scope Under Review

Review the TSIL intrinsic keyword unification.

The intended final state:

- `intrin<NAME>(...)` remains the direct intrinsic-call form.
- `intrin<BASE, build>(...)` replaces the old default composed intrinsic form.
- `intrin<BASE, build[prefix=..., infix=..., suffix=..., post=..., immediate(N)=...]>(...)`
  replaces composed intrinsic calls with explicit modifiers.
- Missing build fields use backend/extension defaults; explicit fields override
  those defaults.
- `intrin::prefix` is a normal typed query resolved from selected backend and
  extension facts.
- Production scanner/registry/lowering no longer contains an `intrin_compose`
  keyword or lowerer.
- Primitive TSIL data under `tsldata/primitives` no longer uses
  `intrin_compose<...>`.

## Review Checklist

Use `docs/agent/review-checklist.md`. Pay special attention to:

- direct `intrin<NAME>` calls still render as direct calls and only receive
  backend qualification where appropriate;
- `build[...]` preserves existing composed intrinsic behavior, including
  default suffixes, explicit suffixes, infix/infix separator handling,
  `post=mask`, and `immediate(N)=...`;
- explicit `prefix=...` is handled through typed query/backend facts rather
  than source-name or backend-id branches;
- the corpus rewrite is mechanical and does not alter non-intrinsic TSIL body
  structure;
- historical documentation may mention `intrin_compose` as evidence, but
  current production source/tests should not depend on it.

## Suggested Validation

```bash
python -m compileall -q tslc/src/tslc tslc/tests
python -m pytest -q tslc/tests/test_tsil_statement_terminators.py tslc/tests/test_tsil_scan.py tslc/tests/test_parse_arithmetic.py tslc/tests/test_diagnostic_provenance.py tslc/tests/test_select_and_lower.py tslc/tests/test_generation_conditionals.py tslc/tests/test_masks_and_calls.py
python -m pytest -q tslc/tests/test_build_verify.py::test_set_builds tslc/tests/test_value_tests.py::test_value_full_corpus_avx2_builds
git diff --check
./verify.sh
```

Recommended source-boundary scan:

```bash
rg -n 'intrin_compose<|IntrinComposeLowerer|ComposeModifiers' tsldata/primitives tslc/src/tslc tslc/tests
```

Only the corpus guard test should mention `intrin_compose<` in current
production/test files.

## Expected Verdict

Return one of:

- `Accept`
- `Accept With Follow-Ups`
- `Needs Revision`
- `Return To Planner`
