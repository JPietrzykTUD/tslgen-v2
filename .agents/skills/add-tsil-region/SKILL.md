---
name: add-tsil-region
description: Add a TSIL keyword region to tslc. Use when asked to recognize a new TSIL keyword, validate region shell syntax, lower a new body island, support nested TSIL regions, or replace raw implementation text with typed TSIL semantics.
---

# Add TSIL Region

## Workflow

1. Read `AGENTS.md`, `CHARTER.md`, `PLANS.md`, `tslc/AGENTS.md`,
   `tslc/CHARTER.md`, and the existing `tslc/src/tslc/ir/`,
   `tslc/src/tslc/catalog/validation/body_validation.py`, and
   `tslc/src/tslc/lower/region_handlers/` patterns. Read `tsldata/AGENTS.md`
   when source bodies are in scope.
2. Define the exact accepted source forms and nearby malformed forms before editing.
3. Add lexical and authoring facts to `ir/region_registry.py`, structural body
   parsing to `ir/scan.py` only when a new shape requires it, and lowering plus
   implementation-state effects to `lower/region_handlers/registry.py`. Keep
   their existing cross-checks exact rather than creating another keyword list.
4. Keep scanning lexical: delimiters, nesting, spans, and recursive segments only. Do not add expression semantics to the scanner.
5. Add shell validation separately from lowering when the selector/body shape can be checked without backend semantics.
6. Add a focused lowerer that consumes `Region` and typed context values. Do not bypass the recursive segment boundary or scan raw implementation strings independently.
7. Define statement-position traversal through `Region.statement_blocks()` and
   all-child recursive traversal through `Region.child_sequences()`. Add tests
   for valid, malformed, unsupported, nested, authoring, hover,
   implementation-state, full-span diagnostic, and no-raw-passthrough behavior.

## Checks

- The next TSIL keyword should require a descriptor plus a focused validator/lowerer, not edits in scattered keyword lists.
- Malformed source must produce structured diagnostics with source locations where available.
- Every scanner, validator, authoring, and implementation-state walker must use
  the appropriate region-owned statement-block or all-child contract.
- Renderer code must consume lowered typed values rather than re-parsing source text.
- Existing raw text behavior should remain explicit and tested.

## Useful Commands

```bash
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_tsil_scan.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_lower_text.py tslc/tests/test_select_and_lower*.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_catalog_validation.py tslc/tests/test_implementation_state.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_authoring_completion.py tslc/tests/test_catalog_hover.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_safety_contract.py tslc/tests/test_diagnostic_provenance.py
```
