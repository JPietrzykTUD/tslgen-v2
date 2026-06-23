# Review Prompt: TSLc Design Follow-Up Cleanup

You are reviewing a focused cleanup that addresses three design-audit findings
from the recent `tslc` TSIL/value-test changes.

## Scope

The slice should only fix the three findings:

- make intrinsic selector splitting comma-only and reject
  `intrin<BASE build[...]>(...)`;
- remove source-extension-name branching from value-test differential planning;
- replace the `simple_case(kind=...)` value-test case construction hub with
  explicit per-kind builders.

## Files To Review

- `tslc/src/tslc/lower/_text.py`
- `tslc/src/tslc/lower/region_handlers/intrinsics.py`
- `tslc/src/tslc/value_tests/case_plans.py`
- `tslc/src/tslc/value_tests/patterns.py`
- `tslc/tests/test_lower_text.py`
- `tslc/tests/test_select_and_lower.py`
- `tslc/tests/test_value_test_planning.py`
- `docs/agent/current-redesign-state.md`
- `docs/agent/tslc-vector-query-handoff.md`

## Review Questions

- Does `split_selector_terms(...)` now split only on top-level commas while
  still preserving nested `build[...]` modifier lists, strings, and nested
  selectors?
- Does `IntrinLowerer` diagnose whitespace-separated selector clauses instead
  of treating them as direct intrinsic names?
- Does value-test differential planning use typed extension facts, not the
  source extension name `scalar`, to decide which candidates can be compared
  against the generic reference path?
- Are value-test case builders explicit and cohesive, without a
  string-dispatched `simple_case(kind=...)` hub?
- Are tests guarding the new boundaries without overfitting to current
  primitive names?
- Did the cleanup avoid introducing new source syntax, new backend semantics, or
  renderer-side semantic inference?

## Validation Already Run

```bash
python -m compileall -q tslc/src/tslc tslc/tests
python -m pytest -q tslc/tests/test_lower_text.py tslc/tests/test_select_and_lower.py::test_intrin_build_rejects_whitespace_separated_selector_terms tslc/tests/test_select_and_lower.py::test_intrin_build_supports_explicit_prefix_and_suffix tslc/tests/test_select_and_lower.py::test_intrin_build_suffix_and_infix_accept_type_values tslc/tests/test_select_and_lower.py::test_intrin_build_prefix_remains_text_only tslc/tests/test_value_test_planning.py
python -m pytest -q tslc/tests/test_value_test_planning.py tslc/tests/test_value_tests.py tslc/tests/test_tsil_scan.py tslc/tests/test_masks_and_calls.py tslc/tests/test_generation_conditionals.py tslc/tests/test_select_and_lower.py
python -m pytest -q tslc/tests/test_value_tests.py::test_value_full_corpus_avx2_builds tslc/tests/test_build_verify.py::test_load_store_builds tslc/tests/test_build_verify.py::test_convert_builds tslc/tests/test_build_verify.py::test_set_builds
env TSLC_VERIFY_WORKERS=1 ./verify.sh
git diff --check
```

Results: compile passed; focused cleanup tests passed with 14 tests; broader
TSIL/value-test tests passed with 68 tests; generated-build/value tests passed
with 4 tests; `verify.sh` passed with 179 non-build tests and 53
generated-build tests; final diff check passed.

## Expected Verdict

Return `Accept`, `Accept With Follow-Ups`, or `Needs Revision`.

Treat any production acceptance of whitespace-separated intrinsic selector
clauses, source-name-based scalar differential filtering, or resurrection of
`simple_case(kind=...)` as a likely blocker.
