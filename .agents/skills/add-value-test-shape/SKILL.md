---
name: add-value-test-shape
description: Extend typed generated value-test planning and rendering in tslc. Use when asked to support a new authored tests shape or signature, add a case kind or pattern, handle memory, mask, conversion, scalable, or differential cases, resolve authored_unplanned or backend_unsupported coverage, or add backend rendering for a planned case.
---

# Add Value-Test Shape

## Workflow

1. Read `AGENTS.md`, `CHARTER.md`, `PLANS.md`, `tslc/AGENTS.md`,
   `tslc/CHARTER.md`, the differential-value-test section of
   `tslc/DESCRIPTION.md`, the source primitive/tests, and the closest patterns,
   case planners, capabilities, renderers, and tests under
   `tslc/src/tslc/value_tests/`.
2. Define the authored contract and oracle first: signature/result kinds,
   parameter layout, fixed or scalable lanes, masks, memory/alignment/aliasing,
   immediates, representation changes, safety, and supported backends.
3. Reuse an existing case kind when its typed components express the contract.
   Add vocabulary only when the new case has distinct invariants or render
   requirements; do not create one case kind per primitive or signature.
4. Keep source data semantic. Do not embed C++/Rust harness code or renderer
   policy in `.tsl` tests.
5. Plan before rendering: the focused pattern owns acceptance and actionable
   unplanned reasons; case planners construct typed components;
   `case_capabilities.py` declares invariants; `patterns.py` owns deterministic
   registration. Do not let renderers rediscover source semantics.
6. Declare backend case-kind support through renderer capabilities and add
   focused backend rendering. Missing support must remain
   `backend_unsupported`, not fail through a late dispatch or template error.
7. Keep fixed, scalable, differential, memory, and conversion behavior
   explicit. A missing harness primitive or ambiguous oracle must produce
   `authored_unplanned` coverage or a structured diagnostic, not fabricated
   expected behavior.
8. Test accepted and nearby rejected forms, unplanned reasons, component
   invariants, backend capability validation, deterministic planning, and
   rendering. Run executable generated tests for every affected backend/profile
   that the available toolchains can verify.

## Checks

- Every authored case is planned, explicitly unplanned, or backend-unsupported
  with a deterministic reason.
- Planning remains backend-neutral until declared renderer capabilities and
  target-specific formatting are needed.
- Generated tests exercise the real primitive contract rather than merely
  proving that a harness compiles.

## Useful Commands

```bash
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_value_test_planning.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_backend_target_capability.py tslc/tests/test_value_tests.py
PYTHONPATH=tslc/src python -m pytest -q --run-generated-builds tslc/tests/test_value_tests.py
git diff --check
```
