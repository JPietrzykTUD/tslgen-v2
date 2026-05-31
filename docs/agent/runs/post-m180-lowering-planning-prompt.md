# Post-M180 Lowering Planning Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M180 as accepted.

You are planning the next lowering milestone after:

```text
Milestone 180: Exact Backend Type Query Island Semantic Handoff
```

Milestones 1 through 180 are accepted. M180 consumes exact M179
`BackendTypeQueryRequestIsland` segments and hands them to the existing
selected-context `lower_backend_type_query(...)` semantic boundary, producing
existing `BackendTypeSpellingRequest` values while preserving opaque
surrounding text/tokens. It did not translate backend type spellings, render
output, infer aliases from raw surroundings, recursively discover payloads, or
parse surrounding TSIL/target-language syntax.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/kiss-generator-restart.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/domain-model.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/missing-lowering-inventory.md`
- `docs/redesign/generation-time-semantic-lowering.md`
- `docs/redesign/generation-value-query-inventory.md`
- `docs/redesign/tsil-surface-inventory.md`
- `docs/redesign/tsil-type-query-inventory.md`
- `tslgen/src/tslgen/lowering/`
- `tslgen/tests/`
- `tsldata/**/*.tsl` only as corpus evidence for source forms and frequency.

## Goal

Select the next concrete M181 lowering milestone.

The selected milestone should be the highest-value remaining lowering slice
after M180. It should move the research prototype closer to generating code
from changing `.tsl` source data while staying small, source-grounded, and
reviewable.

Prefer a slice that:

- is grounded in actual `tsldata/**/*.tsl` source forms;
- builds on accepted M127-M180 boundaries;
- avoids target-language interpretation and broad TSIL parsing;
- reduces a real generation blocker rather than adding another one-off
  request/result family;
- can be implemented and reviewed in one execution-review-loop prompt.

## Candidate Areas To Re-evaluate

Use the inventories and current code rather than this list as the final
authority, but consider at least:

- backend value query payload semantics such as
  `value<backend>(intrin::suffix(...))`, `value<backend>(intrin::prefix)`,
  and `value<backend>(uninit::...)`;
- backend intrinsic request semantics for `intrin<...>(...)` and
  `intrin_compose<...>(...)`, especially where modifiers depend on backend
  value requests;
- source-operation request semantics for `cast<...>`, `mem<...>`, and
  `io<...>`;
- declaration and loop execution/rendering gaps for `var<...>(...)` and
  `loop<...>(...)`;
- primitive-call completion/rendering and deterministic body-token rendering
  policy.

Do not assume the largest corpus count is the best next milestone. Favor the
smallest slice that removes a real blocker without turning lowering into a
backend renderer or broad TSIL interpreter.

## Required Planning Task

This is a planning-only run. Do not edit production code or tests.

1. Inspect the accepted roadmap and lowering inventories.
2. Inventory the remaining generation/body/backend-query lowering gaps that
   still matter after M180.
3. Select exactly one M181 milestone, or record an explicit stop/return to
   planner condition if the next slice cannot be selected without a design
   decision.
4. Define M181 goal, scope, out-of-scope work, expected tests, required
   validation, and review/audit subagents.
5. Update `docs/redesign/implementation-roadmap.md`.
6. Update `docs/agent/current-redesign-state.md`.
7. Create the next concrete prompt under `docs/agent/runs/`, normally an
   `m181-...-execution-review-loop-prompt.md`.

## Required Planning Subagents

Use read-only planning/review subagents before finalizing the selected
milestone:

1. Evidence planner: inspect `tsldata/**/*.tsl` and redesign inventories to
   list the remaining lowering candidates and their corpus grounding.
2. Boundary/simplicity auditor: challenge the proposed M181 slice for
   overengineering, broad TSIL parsing, backend rendering, source repair,
   recursive all-context payload discovery, or another one-off request/result
   family.
3. Documentation reviewer: verify the roadmap, state update, and next run
   prompt are coherent and follow the next-run prompt protocol.

The orchestrator owns final milestone selection, state updates, and next
prompt creation.

## Design Guardrails

- Keep the next task focused on lowering.
- Do not implement M181 in this prompt.
- Do not introduce a broad TSIL grammar, expression interpreter, backend
  renderer, source rewriter, dependency scheduler, registry, dispatcher,
  plugin map, or worklist unless the selected milestone proves it is required
  by at least two accepted boundaries.
- Do not treat target-language-like raw text as semantics.
- Do not make `frozen`, `tslgenold`, or runtime `tsldata` a runtime
  dependency.
- Prefer source-owned exact keyword/request islands and typed facts over
  ad-hoc string rewriting.

## Validation

Run:

```bash
git diff --check
```

## Completion Rules

If planning review accepts the selected M181 milestone:

- update `docs/agent/current-redesign-state.md` to point at the new M181
  prompt;
- update `docs/redesign/implementation-roadmap.md` with the selected M181
  milestone;
- create the M181 concrete run prompt under `docs/agent/runs/`;
- record validation results.

If planning review finds the next slice is unclear, do not guess. Record the
blocking design question or stop condition in `docs/agent/current-redesign-state.md`
and create the appropriate follow-up planning prompt.

Do not start M181 implementation in this prompt.

## Final Report

Report:

1. Selected M181 milestone and why it is useful.
2. Planning subagent verdicts and any follow-ups.
3. Files changed.
4. Validation command and exact result.
5. Next active prompt path.
