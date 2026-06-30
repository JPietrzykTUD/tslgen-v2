---
name: design-review
description: Review tslc design health and detect drift from AGENTS.md, PLANS.md, tslc/CHARTER.md, and tslc/DESCRIPTION.md. Use when Codex is asked for a design review, architecture drift audit, extensibility review, maintainability review, KISS/DRY review, or pre/post-check after adding primitives, TSIL regions, backend support, or major compiler pipeline changes.
---

# Design Review

## Operating Mode

Default to read-only. Do not edit files unless the user explicitly asks for a
fix after the review. If fixes are needed, recommend small coherent slices.

Review the active project shape, not historical intent. Treat `AGENTS.md`,
`PLANS.md`, `tslc/CHARTER.md`, `tslc/DESCRIPTION.md`, tests, `tslc/`, and
`tsldata/` as the relevant design evidence.

## Workflow

1. Read `AGENTS.md`, `PLANS.md`, `tslc/CHARTER.md`, and
   `tslc/DESCRIPTION.md`.
2. Identify the review scope from the user request. If no scope is given, scan
   `tslc/src/tslc/`, `tslc/tests/`, and the relevant `tsldata/` paths.
3. Inspect structure before details: package layout, dependency direction,
   public entry points, extension registries, typed model boundaries, and test
   organization.
4. Sample implementation details where drift is likely: parsing/catalog
   promotion, selection, TSIL scan/lowering, backend translation, render
   templates, diagnostics, maintenance tools, and generated-output boundaries.
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
- **Extensibility**: adding a primitive, backend capability, or TSIL region
  mostly adds focused code rather than modifying unrelated stages.
- **TSIL integrity**: body handling goes through the shared recursive segment
  and region path; new semantics become typed regions or lowered values.
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
