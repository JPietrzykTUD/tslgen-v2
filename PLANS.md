# Planning And Execution Guide

This file is the lightweight planning protocol for active `tslc/` work. It
replaces the old milestone-era workflow. Use it to keep changes small,
reviewable, and pointed at working compiler behavior.

## What Counts As A Slice

A slice is one coherent change that a reviewer can understand without reading a
historical milestone log. Good slices usually do one of these:

- make one source-data form parse, validate, lower, render, or verify;
- add one backend or backend capability boundary;
- add one primitive or primitive-shape family to `tsldata/` and generation;
- improve one diagnostic family;
- remove one obsolete dependency or simplify one boundary;
- strengthen one extension point with focused tests.

Avoid slices that mix unrelated parser, catalog, lowering, backend, docs, and
cleanup work. If a change is hard to name in one sentence, split it.

## Planning Checklist

Before substantial implementation, write down or hold in working memory:

- **Goal**: the user-visible behavior or cleanup result.
- **Scope**: files/modules likely to change.
- **Out of scope**: adjacent tempting work to leave alone.
- **Boundary**: parser, catalog, validation, selection, IR/TSIL, lowering,
  backend, rendering, output, verification, maintenance, or docs.
- **Data model**: domain objects or typed records involved.
- **Extension point**: what future backend/primitive/region becomes easier.
- **Validation**: exact tests and commands to run.
- **Risk**: likely regressions, nondeterminism, or diagnostic gaps.

For tiny mechanical changes, this can be a mental checklist. For broad changes,
state the plan before editing.

## Execution Loop

1. Read the relevant current guidance: `AGENTS.md`, this file, and the nearest
   `tslc/` package docs.
2. Inspect the local code before deciding the design.
3. Make the smallest change that completes the slice.
4. Add or update tests at the same boundary as the behavior.
5. Run targeted validation.
6. Broaden validation when the change crosses module boundaries.
7. Update root/package guidance only when behavior or workflow changed.
8. Report the result, validation, and meaningful follow-ups.

Use top-level `docs/` for human-authored project documentation only, not
workflow or prompt machinery. Historical prompt machinery is retired.

## Architecture Pressure Checks

Use these checks before adding new concepts.

### Maintainability Check

- Can a reader understand, debug, and safely change this behavior by following
  a small number of clearly owned modules?
- Does this change shorten the next read/debug/change path, or merely
  redistribute complexity behind new names?
- Are helper layers, facades, compatibility wrappers, string conventions, and
  duplicated facts necessary and locally owned?
- Would a future maintainer know where this behavior lives without searching
  unrelated parser, catalog, lowering, backend, render, and verification code?

### Extension Point Check

- Would adding the next backend, primitive, source field, or TSIL region mostly
  add code in one focused area?
- If the next similar feature would require edits across scattered classifiers,
  validators, renderers, policy branches, and string special cases, is there a
  weak or missing extension point that should be fixed first?
- If this slice is cross-cutting because it introduces a typed boundary, will it
  reduce the number of unrelated locations the next similar feature must touch?
- Are supported cases declared through typed capabilities, descriptors, or
  policies rather than scattered string literals?
- Are unsupported cases diagnosed before rendering or writing artifacts?
- Is there a test proving that future IDs or cases can be admitted additively?

### Domain Model Check

- Is this value a real domain concept, or just a wrapper around another value?
- Can it be immutable?
- Does it carry only the provenance needed for diagnostics?
- Can downstream code consume typed fields instead of raw dictionaries?

### TSIL Body Check

- Is the accepted source form exact and documented by tests?
- Are malformed nearby forms diagnosed rather than repaired?
- Does scanning use the shared recursive segment/region boundary?
- Does lowering produce typed values before backend rendering?
- Are raw-text assumptions explicit?

### Backend And Rendering Check

- Are semantic decisions complete before templates run?
- Are backend capabilities explicit and validated?
- Does artifact writing only write already-rendered artifacts?
- Would a backend with different expression syntax fail clearly instead of
  receiving accidental raw text?

### Determinism Check

- Are filesystem traversal and maps sorted at boundaries?
- Are diagnostics emitted in stable order?
- Are artifacts and manifests deterministic across repeated runs?
- Do tests avoid host CPU feature assumptions?

## Validation Matrix

Choose the smallest useful validation first:

- Parser/catalog/validation:
  `PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_catalog.py tslc/tests/test_catalog_validation.py`
- TSIL scanning/lowering:
  `PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_tsil_scan.py tslc/tests/test_lower_text.py tslc/tests/test_select_and_lower.py`
- Target-text/backend/render model:
  `PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_render_model.py tslc/tests/test_generation_conditionals.py`
- Output/verification/config:
  `PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_build_verify_config.py tslc/tests/test_output_format.py`
- Documentation maintenance:
  `PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_maintenance_documentation.py`
- Full Python logic suite:
  `PYTHONPATH=tslc/src python -m pytest -q tslc/tests`
- Generated build/value pytest gates:
  `PYTHONPATH=tslc/src python -m pytest -q --run-generated-builds tslc/tests/test_build_verify.py tslc/tests/test_value_tests.py`

Always consider:

```bash
python -m compileall -q tslc/src/tslc
git diff --check
```

Generated build/value-test gates are opt-in and expensive; run them when the slice
touches generated project layout, backend codegen, verification, or value-test
planning.

## Review Packet

For a non-trivial change, the final report should make review cheap:

- what changed;
- why it belongs in this slice;
- files touched;
- tests added or changed;
- commands run and results;
- known limitations;
- follow-ups that should not be hidden in the current change.

## Stop Conditions

Stop and ask or report a blocker when:

- required behavior conflicts across active source/data evidence;
- a backend contract cannot be inferred from typed data or current assets;
- a proposed abstraction depends mostly on guessed future needs;
- a test would require unavailable hardware without an injectable substitute;
- the slice starts turning into a broad rewrite;
- deleting historical evidence would remove the only copy of active behavior or
  generated baseline data.

## Cleanup Policy

Cleanup is valuable when it reduces active complexity. It should still be
scoped:

- remove retired dependencies from active code and workflow;
- keep generated baselines such as `coverage/baseline.json` and
  `coverage/primitive-coverage-inventory.md`;
- preserve `supplementary/docs/`; it contains generated-TSL documentation
  assets;
- do not mix large deletion-only cleanup with semantic generator changes unless
  the deletion is necessary for the slice.
