---
name: design-review
description: Review tslc design health and detect drift from repository and compiler charters, scoped AGENTS.md files, PLANS.md, and tslc/DESCRIPTION.md. Use for design reviews, architecture drift or extensibility audits, KISS/DRY reviews, and pre/post-checks of compiler features, semantic projections, authoring/LSP work, maintenance tools, independently packaged downstream tools, or major pipeline changes.
---

# Design Review

## Operating Mode

Default to read-only. Do not edit files unless the user explicitly asks for a
fix after the review. If fixes are needed, recommend small coherent slices.

Review the active project shape, not historical intent. Treat `CHARTER.md`, the
root and applicable nested `AGENTS.md` files, `PLANS.md`, `tslc/CHARTER.md`,
`tslc/DESCRIPTION.md`, tests, `tslc/`, `tsldata/`, and any downstream tool in
scope as the relevant design evidence.

## Workflow

1. Read `AGENTS.md`, `CHARTER.md`, `PLANS.md`, `tslc/AGENTS.md`,
   `tslc/CHARTER.md`, `tslc/DESCRIPTION.md`, and `tsldata/AGENTS.md` when source
   data is in scope.
2. Classify the work as compiler behavior, a compiler-owned projection, or an
   independently packaged downstream tool. Read the applicable tool-local
   `AGENTS.md` and charter for the third case.
3. Identify the review scope from the user request. If no scope is given, scan
   `tslc/src/tslc/`, `tslc/tests/`, and the relevant `tsldata/` or `tools/`
   paths.
4. Inspect structure before details: package layout, dependency direction,
   public entry points, extension registries, typed model boundaries, and test
   organization.
5. Sample implementation details where drift is likely: parsing/catalog
   promotion, selection, TSIL scan/lowering, backend translation, render
   templates, diagnostics, authoring/LSP projections, maintenance tools,
   benchmark consumers, downstream tools, and generated-output boundaries. For
   a compiler-owned projection, inventory every consumed fact, its canonical
   typed owner, and the decisions that legitimately remain local. For a
   downstream tool, also inventory every compiler API or class it imports,
   whether that dependency is public or explicitly lockstep, and every
   interpretation owned by the tool.
6. Report findings first, ordered by severity. Include file/line references and
   explain the design rule being violated.
7. For each finding, describe the smallest design correction and the tests that
   would prove it.
8. If no blocking drift is found, say so and list residual risks or areas that
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
- **Projection ownership**: compiler-owned derived views consume public typed
  facts from their owning compiler stages; they do not reimplement selection,
  capability, target-spelling, dependency, or validation decisions.
- **Downstream isolation**: an independently packaged tool depends on `tslc`
  one way, owns its package/CLI/tests/docs, does not mutate compiler registries
  or defaults, and treats private compiler imports as explicit lockstep
  dependencies. Tool-local interpretations are not presented as compiler facts.
- **Extensibility**: adding a primitive, backend capability, or TSIL region
  mostly adds focused code rather than modifying unrelated stages.
- **Additive probe**: a synthetic next backend, family, namespace, region, or
  case kind exercises generic consumers without unrelated edits.
- **TSIL integrity**: compiler and compiler-owned projection body handling goes
  through the shared recursive segment and region path; new shared semantics
  become typed regions or lowered values, and opaque target text is never
  parsed or rewritten there.
- **Downstream target text**: a declared downstream tool may parse target text
  only inside its package and under its charter. Its parser is bounded and
  fail-closed, distinguishes binding contexts safely, has adversarial and
  golden or differential tests, and cannot feed interpretations back into
  compiler semantics.
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
- **Coverage evidence**: downstream output ratchets exact identities and
  relevant content hashes; aggregate counts alone cannot hide replacement.
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
