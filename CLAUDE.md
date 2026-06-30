# CLAUDE.md

This is the concise Claude Code project memory for `tslc`.

## Claude-Specific Notes

- Keep this file under 200 lines. It intentionally does not import
  `AGENTS.md` or `PLANS.md`, because those files are longer-form guidance.
- Treat `AGENTS.md` as the canonical full project contract when deeper context
  is needed.
- Treat `PLANS.md` as the full planning and pressure-check protocol for
  substantial implementation, review, and revision work.
- Use `.claude/rules/` only for future path-specific or mode-specific Claude
  rules that would make this file noisy.

## Project Principles

- `tslc` is a compact Python compiler for TSL data, not a broad framework.
- Active compiler code lives under `tslc/`; source data lives under `tsldata/`;
  reusable assets live under `supplementary/`; scratch output belongs under
  `tslctmp/`.
- `tsldata/` is authored source data, not generated output. Do not treat corpus
  edits as generated artifact churn.
- New primitive or extension support should usually come from `tsldata/` plus
  typed compiler support. Avoid Python branches that special-case primitive or
  extension names.
- Keep slices small, coherent, and reviewable.
- Inspect local code and source data before deciding the design.
- Prefer typed models and explicit ownership after parsing.
- Keep parser/catalog/lowering/render/output side-effect boundaries clear.
- Backends and templates format already-decided values; they must not select
  primitives, repair TSIL, infer semantics, or duplicate support policy.
- Maintainability means a behavior can be understood and changed through a
  small number of clearly owned modules.
- If changing a behavior requires following many helper layers, string
  conventions, or duplicated facts, the boundary is probably unclear.
- Extensibility means the next similar feature mostly adds focused code at an
  owned extension point, rather than editing scattered classifiers, validators,
  renderers, and string special cases.
- If a feature requires scattered edits across classifiers, validators,
  renderers, and policies, fix the extension point first.
- Broad refactors are acceptable only when they reduce future touch points or
  shorten the next read/debug/change path.

## Design Pressure Checks

- Primitive and extension agnostic: compiler code should not know that `add`,
  `from_array`, `avx2`, `neon`, or similar source names are special.
- Typed boundaries: raw parsed data may be loose at the edge, but downstream
  stages should consume typed catalog, selection, lowering, planning,
  diagnostic, and render values.
- DRY through ownership: support policy, catalog-derived views, TSIL regions,
  backend dialects, and render models should each have one clear home.
- Semantic logic before rendering: renderers and templates should format
  decisions made earlier, not rediscover semantics.
- Diagnostics over silent behavior: malformed or unsupported source forms
  should produce structured diagnostics or explicit deferred coverage.
- Determinism: selection order, diagnostics, artifacts, generated tests, and
  reports should be stable and repeatable.
- KISS: do not add registries, broad IR families, compatibility wrappers, or
  general DSL machinery until at least two real slices need the concept.

## Working Rules

- Do not revert unrelated user changes.
- Use `rg`/`rg --files` for searches when available.
- Use `apply_patch` for manual edits.
- Do not edit generated output unless the user explicitly asks.
- Do not commit generated scratch output under `tslctmp/`.
- Do not hide filesystem writes in parsing, validation, selection, lowering, or
  rendering logic.
- Keep new modules small and cohesive; split before creating catch-all hubs.
- Use `./dev.sh` for generated workflows:
  - `./dev.sh generate`
  - `./dev.sh build`
  - `./dev.sh test`
  - `./dev.sh document`
- Prefer focused validation first, then broaden when a change crosses module
  boundaries.

## Validation

- Always consider `git diff --check`.
- Python/compiler changes: run `python -m compileall -q tslc/src/tslc` plus
  focused pytest for the touched boundary.
- Parser/catalog/validation changes:
  `PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_catalog.py tslc/tests/test_catalog_validation.py`
- TSIL/lowering changes:
  `PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_tsil_scan.py tslc/tests/test_lower_text.py tslc/tests/test_select_and_lower.py`
- Backend/render/output changes:
  `PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_render_model.py tslc/tests/test_generation_conditionals.py tslc/tests/test_output_format.py`
- Generated project layout or verification changes: use `./dev.sh build` or
  `./dev.sh test` with the smallest useful primitive/profile/backend subset.
- Documentation tooling changes: use focused documentation tests or
  `./dev.sh document`.

## Reviews

- Lead with findings, ordered by severity, with file/line references.
- Focus on boundary violations, weak extension points, unclear ownership,
  raw dictionaries or strings leaking past parser/catalog edges, missing
  diagnostics, nondeterminism, and missing tests.
- If there are no blocking findings, say so and name residual risks or test
  gaps.
