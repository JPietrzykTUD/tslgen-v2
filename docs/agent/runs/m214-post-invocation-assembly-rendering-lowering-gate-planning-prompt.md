# M214 Post-Invocation Assembly Rendering/Lowering Gate Planning Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M213 as accepted.

This is a planning/documentation task. Do not implement production code or
tests. Use read-only subagents for evidence, architecture/boundary,
documentation, and validation audits. The orchestrator owns final state and
next-prompt updates.

## Accepted State

Accepted through:

```text
Milestone 213: Backend Intrinsic Invocation Assembly
```

M211 declared lowering complete by current contract after selected immediates.
M213 added typed backend intrinsic invocation assembly over accepted M166/M182
handoff requests and M195-M210 translated modifier results. It produces direct
and composed invocation values with intrinsic name text, ordered name parts,
opaque argument payloads, and typed immediate metadata.

M213 deliberately did not parse intrinsic arguments, reopen lowering, resolve
direct-name placeholders, render C++ or Rust calls, qualify Rust
`core::arch::*`, render C++ non-type template arguments, render Rust const
generics, execute dependency closure, or write generated projects.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/domain-model.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/tsil-surface-inventory.md`
- `docs/redesign/lowering-completeness-audit.md`
- `docs/redesign/missing-lowering-inventory.md`
- `tslgen/src/tslgen/backends/intrinsic_invocations.py`
- `tslgen/src/tslgen/backends/intrinsic_modifiers.py`
- M213 tests and the relevant M195-M210 tests.

## Goal

Plan the next smallest high-value milestone after M213.

The expected direction is backend/output rendering of already assembled
intrinsic invocation values. However, this prompt includes a narrow
lowering-readiness gate: if a concrete lowering-owned gap blocks rendering,
identify and select exactly that gap. If no such blocker exists, keep lowering
closed by current contract and select the backend/output rendering milestone.

## Planning Questions

Answer these before selecting the next milestone:

- What does a renderer need from `BackendDirectIntrinsicInvocation` and
  `BackendComposedIntrinsicInvocation` that is not already present?
- Can a first rendering slice consume invocation values without parsing
  argument payloads or deciding suffix/prefix/immediate semantics?
- Are Rust `core::arch::*` qualification, C++ non-type template arguments, and
  Rust const generics rendering policies over typed M213 values, or do they
  expose a missing lowering-owned fact?
- Should the next executable slice render only invocation calls that have no
  typed immediates, or should it explicitly include typed immediate rendering?
- Should direct placeholder resolution remain a later backend translation
  milestone instead of being bundled into call rendering?
- What diagnostics must protect renderer inputs from unresolved direct names,
  unsupported immediates, backend mismatches, or missing invocation assembly?

## Scope Options

Choose exactly one next milestone. Expected candidates:

- **No-immediate invocation call rendering.** Render already assembled direct
  and composed calls whose `immediates` tuple is empty, preserving opaque
  argument text and rejecting immediate-bearing calls with explicit
  diagnostics.
- **Typed immediate rendering policy.** If immediate-bearing calls are too
  common to defer, plan the smallest explicit C++ non-type template and Rust
  const-generic rendering boundary over M213 typed immediate metadata.
- **Rust intrinsic qualification policy.** If Rust call rendering cannot safely
  proceed without architecture/module qualification, plan a focused typed
  qualification boundary over backend/extension/invocation facts.
- **Concrete lowering gap.** Select this only if evidence shows rendering is
  impossible because a named lowering-owned fact is missing despite M211.

If a different backend/output prerequisite is higher value, record the
evidence and select only that one milestone.

## Guardrails

- Do not reopen lowering unless the plan names a concrete lowering-owned
  blocker and explains why M213 rendering cannot proceed without it.
- Do not parse or split intrinsic arguments.
- Do not resolve direct intrinsic placeholders unless selected as the one
  milestone.
- Do not render whole primitive bodies or generated projects.
- Do not execute dependency closure.
- Do not move backend semantic choices into templates.
- Do not hardcode intrinsic suffixes, prefixes, type spellings, feature gates,
  or Rust module paths in presentation templates.
- Do not use `frozen/` or `tslgenold/` as runtime dependencies.

## Required Review/Audit Subagents

Run read-only subagents:

1. Evidence auditor: M213 invocation values, current intrinsic corpus pressure,
   and whether immediates/qualification should be first.
2. Architecture/boundary auditor: lowering gate, renderer/template boundary,
   and no semantic decisions in templates.
3. Documentation auditor: roadmap/state/prompt consistency.
4. Validation auditor: required validation command and workspace hygiene.

If any auditor returns `Needs Revision`, make only focused documentation or
prompt fixes and rerun the relevant focused audit. If any returns
`Return To Planner` or `Reject`, record that result and create the appropriate
next prompt.

## Required Validation

Run:

```bash
git diff --check
find tslgen -type d -name __pycache__ -print
```

Report the exact result.

## Completion Rules

Before finishing:

- update `docs/redesign/implementation-roadmap.md` with the planning result;
- update `docs/agent/current-redesign-state.md`;
- create the next concrete prompt under `docs/agent/runs/`;
- update other redesign docs only if the planning decision changes or
  clarifies an accepted design boundary;
- do not start the next milestone.

## Final Report

Report:

1. Planning result.
2. Selected next milestone and why it is useful.
3. Review/audit verdicts.
4. Validation command and exact result.
5. Next active prompt path.
