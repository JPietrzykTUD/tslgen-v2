# M196 Intrinsic Semantic Modifier Translation Planning Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M195 as accepted.

This is a planning milestone. Use the orchestrated planning/review workflow in
`PLANS.md` and `AGENTS.md`: the main thread plans, read-only subagents audit
evidence, boundaries, and documentation, and the orchestrator owns the final
state and next-prompt updates. Do not implement code in this milestone.

## Accepted State

Accepted through:

```text
M195: Literal Intrinsic Modifier Translation For Compose Handoff
```

Selected milestone:

```text
Milestone 196: Intrinsic Semantic Modifier Translation Planning
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
- `tslgen/src/tslgen/backends/intrinsic_modifiers.py`
- `tslgen/src/tslgen/backends/type_spelling.py`
- `tslgen/src/tslgen/backends/value_translation.py`
- `tslgen/tests/test_m195_literal_intrinsic_modifier_translation.py`
- `tsldata/primitives/**/*.tsl` as source-corpus evidence only
- `tsldata/extensions/extension.tsl`
- `tsldata/detail/lang/**/*.tsl`

## Goal

Plan the next executable backend translation slice for the intrinsic modifier
families that M195 intentionally diagnosed instead of translating.

The output of this milestone is a concrete next implementation prompt, not
code. The plan should identify which semantic modifier family can be handled
next from already accepted typed facts and which typed rule input, if any, must
be introduced before implementation.

## Planning Scope

- Inventory all remaining M195 unsupported modifier families in
  `tsldata/primitives/**/*.tsl`, including:
  - no-argument `suffix=value<backend>(intrin::suffix)`;
  - type-derived `suffix=value<backend>(intrin::suffix(type<generation>(...)))`;
  - string-argument `suffix=value<backend>(intrin::suffix("stream"))`;
  - symbol-argument `suffix=value<backend>(intrin::suffix(ToBase))`;
  - `prefix=value<backend>(intrin::prefix)`;
  - backend-value `infix=value<backend>(intrin::suffix...)`;
  - semantic `infix=to_type_suffix`;
  - wildcard-looking direct suffixes such as `suffix=si?`;
  - symbol immediates such as `immediate(1)=index` and `immediate(1)=Index`.
- For each family, identify the typed inputs required before translation:
  selected backend, extension, type tag, current vector/type context, return
  type bindings, extension metadata, backend metadata, M192 type spelling
  results, M193 value results, or new typed intrinsic modifier rule records.
- Determine whether any family can be translated in the next executable slice
  without raw source parsing, intrinsic-name assembly, renderer-side inference,
  dependency closure, or broad TSIL expression parsing.
- Select exactly one next executable milestone. Prefer the largest safe subset
  that shares one clear typed input contract; do not combine unrelated semantic
  families merely because they are all currently unsupported.
- Define that next milestone's:
  - typed input and result shape;
  - diagnostics;
  - positive, negative, corpus, and boundary tests;
  - documentation updates;
  - validation command.

## Boundary Questions

Answer these explicitly in the plan:

- Which remaining modifier family is product-useful enough to implement next?
- Does the family require new typed intrinsic suffix/prefix rule records, or
  can it reuse accepted M190/M192/M193 facts directly?
- Does the family require extension metadata from `extension.tsl`, current
  selected implementation context, return-type bindings, or argument identity?
- What must remain opaque until a later milestone?
- How does the proposed next slice avoid intrinsic-name assembly and
  renderer-side semantic decisions?

## Out Of Scope

- Implementation code.
- Intrinsic name assembly.
- Rendering or generated-project changes.
- Direct `intrin<...>(...)` name parsing.
- Intrinsic argument payload parsing except as evidence for why a future rule
  may need typed argument identity.
- Source repair.
- Dependency closure.
- Broad backend metadata template evaluation.
- Broad TSIL expression parsing.
- Lowering changes unless planning proves the accepted M182 handoff is a true
  blocker.
- Runtime dependency on `frozen/` or `tslgenold`.

## Required Review Subagents

Use read-only subagents after the planner draft is written:

1. Evidence auditor: verify the unsupported-family inventory against
   `tsldata/primitives/**/*.tsl`.
2. Architecture/boundary auditor: verify the selected next slice preserves
   typed backend translation boundaries and does not drift into rendering,
   source parsing, intrinsic-name assembly, or dependency closure.
3. Documentation auditor: verify roadmap/state/next-prompt updates accurately
   record the accepted planning result and follow-ups.

If review returns `Needs Revision`, make a focused documentation-only planning
revision and rerun focused re-review. If review returns `Return To Planner` or
`Reject`, record the blocker and create the appropriate next prompt instead of
selecting an executor.

## Required Validation

Run:

```bash
git diff --check
find tslgen -type d -name __pycache__ -print
```

## Completion Rules

Before finishing an accepted M196 planning run:

- update `docs/redesign/implementation-roadmap.md` with the M196 planning
  result and selected next executable milestone;
- update redesign docs if planning clarifies behavior, decisions, or open
  questions;
- update `docs/agent/current-redesign-state.md`;
- create the next concrete prompt under `docs/agent/runs/`;
- report exact validation results.

## Stop Rule

Do not implement M197. Do not add semantic suffix/prefix rules, symbol
immediate resolution, intrinsic-name assembly, rendering, dependency closure,
or lowering code in this planning milestone.

## Final Report

Report:

1. M196 planning verdict.
2. Selected next milestone and why it is useful.
3. Boundary decisions preserved.
4. Validation commands with exact results.
5. Review/audit verdicts.
6. Next active prompt path.
