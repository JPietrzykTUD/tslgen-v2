# M194 Intrinsic Modifier Translation Planning Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M193 as accepted.

This is a planning task. Use a read-only planning/audit workflow. Do not
implement code. The orchestrator owns final state and next-prompt updates.

## Accepted State

Accepted through:

```text
M193: Backend Value Translation For Metadata-Only Requests
```

Selected milestone:

```text
Milestone 194: Intrinsic Modifier Translation Boundary Planning
```

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/domain-model.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/design-decisions.md`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/backend_intrinsic_handoff.py`
- `tslgen/src/tslgen/backends/type_spelling.py`
- `tslgen/src/tslgen/backends/value_translation.py`
- `tslgen/tests/test_m182_intrinsic_modifier_handoff.py`
- `tslgen/tests/test_m192_backend_type_spelling_translation.py`
- `tslgen/tests/test_m193_backend_value_translation.py`
- `tsldata/**/*.tsl` as source-corpus evidence only
- `tsldata/detail/lang/translate_cpp.tsl`
- `tsldata/detail/lang/translate_rust.tsl`
- `tsldata/extensions/extension.tsl`

## Goal

Plan the next executable backend translation slice for intrinsic modifier
values after M193.

The planning question is: which subset of accepted M182 intrinsic modifier
handoff values can be translated next from already accepted typed facts and
typed metadata without falling back into source parsing, renderer-side
inference, arbitrary template formatting, or broad intrinsic-name assembly?

## Scope

- Inventory current `intrin_compose<...>` modifier operands in
  `tsldata/**/*.tsl`, including:
  - `suffix=value<backend>(intrin::suffix)`;
  - `suffix=value<backend>(intrin::suffix(ARG))`;
  - `prefix=value<backend>(intrin::prefix)`;
  - literal/symbol `post`, `infix`, `infix_sep`, and `immediate(N)` fields.
- Classify each family by required inputs:
  - M182 intrinsic modifier handoff facts;
  - M192 backend type spelling results;
  - M193 backend value results;
  - extension/type context from accepted catalogs;
  - backend metadata keys;
  - additional typed rule inputs not yet present.
- Select exactly one next implementation milestone:
  - prefer the largest safe subset that can be translated from existing typed
    facts;
  - reject subsets that require guessing intrinsic semantics, direct intrinsic
    name parsing, or formatting placeholder-bearing templates without typed
    inputs.
- Define the selected milestone's typed result shape, diagnostics, positive
  tests, negative tests, validation command, and out-of-scope boundary.
- Create the next concrete execution prompt under `docs/agent/runs/`.

## Out Of Scope

- Implementation code.
- Rendering.
- Primitive body rendering.
- Direct `intrin<...>(...)` name parsing.
- Intrinsic argument payload parsing.
- Broad intrinsic-name assembly.
- Arbitrary placeholder formatting.
- Backend source-operation, control, mask, or primitive-call translation.
- Dependency closure.
- Machine profile changes.
- Lowering changes unless the plan finds a true blocker.
- Runtime dependency on `frozen/` or `tslgenold`.

## Guardrails

- Treat `tsldata/**/*.tsl` as ground truth for source forms.
- Do not make the next implementation milestone a semantic validator or source
  repair step.
- Do not select a milestone that needs hidden renderer/template decisions.
- Keep direct intrinsic names and intrinsic argument payloads opaque. M194
  must not select direct `intrin<...>` name parsing or intrinsic argument
  parsing as the next executable milestone.
- Prefer typed rule values over ad-hoc dictionaries. If a lookup table is
  needed, plan it as typed rule records with documented supported cases and
  diagnostics.
- Keep the next implementation slice small enough to review and useful enough
  to move generated primitive bodies closer.

## Required Planning Subagents

Use read-only subagents:

1. Evidence auditor: inventory representative modifier forms and identify
   required typed inputs from `tsldata`.
2. Architecture/boundary auditor: pressure-check the proposed next slice
   against backend translation, renderer/template, and no-source-repair
   boundaries.
3. Documentation auditor: verify the resulting roadmap/state/next prompt
   accurately record the decision and validation.

If the auditors return `Needs Revision`, make only focused documentation and
prompt fixes. If they return `Return To Planner` or `Reject`, record the
blocker and create an appropriate follow-up planning prompt.

## Required Validation

Run:

```bash
git diff --check
find tslgen -type d -name __pycache__ -print
```

Remove validation-created `__pycache__` directories before final validation
reporting if any appear.

## Completion Rules

Before finishing:

- update `docs/redesign/implementation-roadmap.md` with the M194 planning
  result and selected next implementation milestone;
- update redesign docs if planning clarifies behavior, decisions, or open
  questions;
- update `docs/agent/current-redesign-state.md`;
- create the next concrete prompt under `docs/agent/runs/`;
- report exact validation results.

## Final Report

Report:

1. M194 planning verdict.
2. Selected next milestone.
3. Why that milestone is useful.
4. Files changed.
5. Validation commands with exact results.
6. Review/audit verdicts.
7. Next active prompt path.
