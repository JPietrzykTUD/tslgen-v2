---
name: design-review
description: Review tslc design health and detect drift from the repository and compiler charters, scoped AGENTS.md files, PLANS.md, and tslc/DESCRIPTION.md. Use when asked for a design review, architecture drift audit, extensibility review, maintainability review, KISS/DRY review, or a pre/post-check for compiler features, semantic projections, authoring/LSP work, maintenance tools, sibling exporters, or major pipeline changes.
---

# Design Review

## Operating Mode

Default to read-only. Do not edit files unless the user explicitly asks for a
fix after the review. If fixes are needed, recommend small coherent slices.

Review the active project shape, not historical intent. Treat `CHARTER.md`, the
root and applicable nested `AGENTS.md` files, `PLANS.md`, `tslc/CHARTER.md`,
`tslc/DESCRIPTION.md`, tests, `tslc/`, and `tsldata/` as the relevant design
evidence.

## Workflow

1. Read `AGENTS.md`, `CHARTER.md`, `PLANS.md`, `tslc/AGENTS.md`,
   `tslc/CHARTER.md`, `tslc/DESCRIPTION.md`, and `tsldata/AGENTS.md` when source
   data is in scope.
2. Identify the review scope from the user request. If no scope is given, scan
   `tslc/src/tslc/`, `tslc/tests/`, and the relevant `tsldata/` paths.
3. Inspect structure before details: package layout, dependency direction,
   public entry points, extension registries, typed model boundaries, and test
   organization.
4. Sample implementation details where drift is likely: parsing/catalog
   promotion, selection, TSIL scan/lowering, backend translation, render
   templates, diagnostics, authoring/LSP projections, maintenance tools,
   benchmark consumers, sibling exporters, and generated-output boundaries.
   For a projection, inventory every consumed fact, its canonical typed owner,
   and the decisions that legitimately remain local to the output format.
5. Report findings first, ordered by severity. Include file/line references and
   explain the design rule being violated.
6. For each finding, describe the smallest design correction and the tests that
   would prove it.
7. If no blocking drift is found, say so and list residual risks or areas that
   were not deeply inspected.

## Review Checklist

- **KISS**: control flow is direct, module names are literal, and abstractions
  are justified by delivered compiler behavior.
- **DRY with judgment**: shared compiler knowledge lives in one place, while
  small local repetition is allowed when it keeps unlike concepts separate.
- **Typed boundaries**: dictionaries and loose metadata do not leak past parser,
  config, or explicit metadata boundaries into domain logic.
- **Object ownership**: stateful concepts have small classes or protocols that
  own invariants; simple stateless transformations remain functions.
- **Projection ownership**: tools and derived views consume public typed facts
  from their owning compiler stages; they do not reimplement selection,
  capability, target-spelling, dependency, or validation decisions.
- **Extensibility**: adding a primitive, backend capability, or TSIL region
  mostly adds focused code rather than modifying unrelated stages.
- **Additive probe**: a synthetic next backend, family, namespace, region, or
  case kind exercises generic consumers without unrelated edits.
- **TSIL integrity**: body handling goes through the shared recursive segment
  and region path; new semantics become typed regions or lowered values, and
  opaque target text is never parsed or rewritten by a projection.
- **Backend boundary**: backend rules translate typed lowered values; templates
  only format decided render models.
- **Diagnostics**: malformed or unsupported input produces structured,
  actionable, deterministic diagnostics with source locations where practical.
- **Determinism**: selections, diagnostics, artifacts, plans, and generated
  text have stable ordering.
- **Module health**: files remain cohesive; large modules do not collect
  unrelated responsibilities.
- **Tests**: risky behavior has focused tests at the right boundary plus
  integration/golden coverage when output changes.
- **Guidance currency**: changes to ownership, workflow, or canonical commands
  update each affected task skill in the same slice.
- **Docs/code alignment**: project guides describe what the code actually does,
  and code does not rely on undocumented design exceptions.

## Output Shape

Use a code-review style:

1. Findings, ordered by severity, with file/line references.
2. Open questions or assumptions.
3. Design health summary.
4. Suggested next slices, if useful.

Prefer concrete findings over broad commentary. A good finding names the drift,
shows where it appears, explains why it weakens maintainability or
extensibility, and gives a small repair path.
