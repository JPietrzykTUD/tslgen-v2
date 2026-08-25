---
name: add-tsl-primitive
description: Add or update a TSL primitive in tsldata and the tslc compiler. Use when asked to add a new primitive, change primitive signatures/tests/bodies, support a new primitive shape, or make primitive source data compile through parsing, validation, selection, lowering, rendering, and generated value tests.
---

# Add TSL Primitive

## Workflow

1. Read `AGENTS.md`, `CHARTER.md`, `PLANS.md`, `tsldata/AGENTS.md`,
   `tslc/AGENTS.md`, `tslc/CHARTER.md`, and the closest existing primitive
   examples under `tsldata/primitives/`.
2. Identify the primitive family, signatures, type groups, extension coverage, masks, immediate parameters, and value-test needs before editing.
3. Add or update source data in `tsldata/` first. Keep source forms explicit;
   reject obsolete forms immediately rather than preserving aliases or silently
   repairing malformed `.tsl`.
4. If the current parser/catalog/schema does not accept the needed shape, add
   typed validation and promotion through the shared syntax accessors, parameter
   type vocabulary, and region syntax at the parser/catalog boundary. Pointer
   overrides use exact `ptr(...)` / `cptr(...)` expressions; address intent uses
   `address<of|borrow_mut>` rather than raw C++/Rust address tokens.
5. If selection or lowering needs new behavior, add typed domain/lowering
   values. Avoid raw string rewrites and avoid leaking dictionaries past catalog
   boundaries. Compiler-specific alternatives use semantic capability-selected
   implementations plus an unconditional fallback, never raw preprocessor
   selection in implementation text. For fixed-width compiler-vector overlays,
   prefer an exact compiler operation first, including a documented vector
   operator as well as a named builtin. Only when no exact compiler operation
   exists may the source opt into the exact-width native `vector::fixed` facade;
   retain an overlay-owned portable body for profiles without a native leaf.
   Do not set `prefer_fixed_native` on an exact compiler-operation body because
   native delegation runs before the authored body.
6. If rendering or value tests need support, add backend capability checks before render-time surprises.
7. When a schema, selector, region, or query vocabulary changes, also use
   `extend-tslc-authoring` and prove completion/index/query projection from the
   same owner. Add focused tests and full-span diagnostics at the touched
   boundary, then broaden to generated-output or value-test coverage when
   behavior crosses lowering/rendering.

## Checks

- Verify diagnostics for malformed or unsupported nearby source forms.
- Verify deterministic ordering for any added source traversal, selected slots, artifacts, or diagnostics.
- Verify extension-point behavior: the next similar primitive should not require edits in unrelated modules.
- Prefer one representative primitive fixture plus corpus coverage when the primitive family affects many existing paths.

## Useful Commands

```bash
PYTHONPATH=tslc/src python -m tslc check
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_catalog.py tslc/tests/test_catalog_validation.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_select_and_lower*.py tslc/tests/test_lower_text.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_value_test_planning.py tslc/tests/test_diagnostic_provenance.py
PYTHONPATH=tslc/src python -m pytest -q --run-generated-builds tslc/tests/test_build_verify.py tslc/tests/test_value_tests.py
./dev.sh build --primitives NAME --profiles scalar,avx2 --backends cpp,rust
./dev.sh test --primitives NAME --profiles scalar,avx2 --backends cpp,rust
```
