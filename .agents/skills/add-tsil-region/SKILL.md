---
name: add-tsil-region
description: Add a TSIL keyword region to tslc. Use when Codex is asked to recognize a new TSIL keyword, validate region shell syntax, lower a new body island, support nested TSIL regions, or replace raw implementation text with typed TSIL semantics.
---

# Add TSIL Region

## Workflow

1. Read `AGENTS.md`, `PLANS.md`, `tslc/CHARTER.md`, and the existing `tslc/src/tslc/ir/`, `catalog/validation/body_validation.py`, and `lower/region_handlers/` patterns.
2. Define the exact accepted source forms and nearby malformed forms before editing.
3. Add the keyword to the region descriptor/registry path so scanning, validation, and lowerer registration share one source of truth.
4. Keep scanning lexical: delimiters, nesting, spans, and recursive segments only. Do not add expression semantics to the scanner.
5. Add shell validation separately from lowering when the selector/body shape can be checked without backend semantics.
6. Add a focused lowerer that consumes `Region` and typed context values. Do not bypass the recursive segment boundary or scan raw implementation strings independently.
7. Add tests for valid forms, malformed forms, unsupported forms, nested forms, diagnostics, and no raw passthrough when semantics should be typed.

## Checks

- The next TSIL keyword should require a descriptor plus a focused validator/lowerer, not edits in scattered keyword lists.
- Malformed source must produce structured diagnostics with source locations where available.
- Renderer code must consume lowered typed values rather than re-parsing source text.
- Existing raw text behavior should remain explicit and tested.

## Useful Commands

```bash
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_tsil_scan.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_lower_text.py tslc/tests/test_select_and_lower.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_safety_contract.py
```
