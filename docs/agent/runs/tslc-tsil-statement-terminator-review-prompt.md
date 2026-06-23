# TSLc TSIL Statement Terminator Review

## Scope Under Review

Review the TSIL statement terminator cleanup.

The intended final state:

- The shared TSIL scanner consumes a source `;` after recognized regions only
  in statement streams.
- Nested keyword payloads remain expression streams, so nested expression atoms
  do not claim punctuation from the surrounding expression.
- `Region.has_statement_terminator` records consumed source semicolons.
- Lowering renders a consumed terminator exactly once: the renderer appends one
  target `;` by default for ordinary non-block regions, while keyword lowerers
  own keyword-specific finalization.
- `var<...>` does not receive an extra semicolon because `VarLowerer` keeps the
  current backend declaration templates unchanged.
- `let<type>(...)` may consume a source semicolon while `LetLowerer` continues
  to render no target statement.
- Block forms such as `if`, `loop<range>`, and `switch<compile>` do not gain
  target semicolons.
- `tsldata/primitives` is normalized so accepted `let<type>` and `var<...>`
  statement regions carry source semicolons.
- A corpus guard test fails if accepted statement keyword families are missing
  source semicolons in primitive TSIL bodies.

## Review Checklist

Use `docs/agent/review-checklist.md`. Pay special attention to:

- source semicolon handling remains lexical and does not become a broad TSIL
  parser;
- raw target-like statements keep their raw punctuation;
- expression regions inside payloads remain unaffected;
- generated C++ and Rust bodies do not lose required statement terminators;
- handler-owned finalization does not introduce duplicate `;;` for
  template-terminated declarations or stray `;` for elided aliases.
- the corpus rewrite does not add semicolons to expression atoms embedded in
  larger raw expressions.

## Suggested Validation

```bash
python -m compileall -q tslc/src/tslc tslc/tests
python -m pytest -q tslc/tests/test_tsil_statement_terminators.py tslc/tests/test_tsil_scan.py tslc/tests/test_select_and_lower.py tslc/tests/test_lane_lists.py
python -m pytest -q tslc/tests/test_build_verify.py::test_set_builds tslc/tests/test_value_tests.py::test_value_full_corpus_avx2_builds
git diff --check
./verify.sh
```

## Expected Verdict

Return one of:

- `Accept`
- `Accept With Follow-Ups`
- `Needs Revision`
- `Return To Planner`
