---
name: add-tsl-primitive
description: Add or update a TSL primitive in tsldata and the tslc compiler. Use when Codex is asked to add a new primitive, change primitive signatures/tests/bodies, support a new primitive shape, or make primitive source data compile through parsing, validation, selection, lowering, rendering, and generated value tests.
---

# Add TSL Primitive

## Workflow

1. Read `AGENTS.md`, `PLANS.md`, `tslc/CHARTER.md`, and the closest existing primitive examples under `tsldata/primitives/`.
2. Identify the primitive family, signatures, type groups, extension coverage, masks, immediate parameters, and value-test needs before editing.
3. Add or update source data in `tsldata/` first. Keep source forms explicit; do not make the compiler silently repair malformed `.tsl`.
4. If the current parser/catalog/schema does not accept the needed shape, add typed validation and promotion at the parser/catalog boundary.
5. If selection or lowering needs new behavior, add typed domain/lowering values. Avoid raw string rewrites and avoid leaking dictionaries past catalog boundaries.
6. If rendering or value tests need support, add backend capability checks before render-time surprises.
7. Add focused tests at the touched boundary, then broaden to generated-output or value-test coverage when behavior crosses lowering/rendering.

## Checks

- Verify diagnostics for malformed or unsupported nearby source forms.
- Verify deterministic ordering for any added source traversal, selected slots, artifacts, or diagnostics.
- Verify extension-point behavior: the next similar primitive should not require edits in unrelated modules.
- Prefer one representative primitive fixture plus corpus coverage when the primitive family affects many existing paths.

## Useful Commands

```bash
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_catalog_validation.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_select_and_lower*.py tslc/tests/test_lower_text.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_value_test_planning.py tslc/tests/test_value_tests.py
./dev.sh build --primitives NAME --profiles scalar,avx2 --backends cpp,rust
```
