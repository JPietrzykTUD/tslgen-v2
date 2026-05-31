# Post-M182 Lowering Planning Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M182 as accepted.

You are planning the next lowering milestone after:

```text
Milestone 182: Exact Intrinsic Modifier Semantic Handoff
```

Milestones 1 through 182 are accepted. M182 consumes exact M166
`BackendIntrinsicRequest` discovery segments and hands top-level
`intrin_compose<...>(...)` modifier fields to typed unresolved intrinsic
modifier facts while preserving direct `intrin<...>` names, intrinsic
arguments, opaque surroundings, and raw request identity. It reuses M181 only
when a modifier value is exactly one balanced `value<backend>(...)` island.
It does not translate intrinsic names or modifier values, split arguments,
render C++/Rust, read backend maps, recursively discover arbitrary payloads,
repair source, or parse broad TSIL/target-language expressions.

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

Select the next concrete M183 lowering milestone.

The selected milestone should be the highest-value remaining lowering slice
after M182. It should move the research prototype closer to generating code
from changing `.tsl` source data while staying small, source-grounded, and
reviewable.

Prefer a slice that:

- is grounded in actual `tsldata/**/*.tsl` source forms;
- builds on accepted M127-M182 boundaries;
- removes a real generation blocker rather than adding ceremony;
- avoids target-language interpretation, source repair, broad TSIL parsing,
  and renderer-side semantic inference;
- can be implemented and reviewed in one execution-review-loop prompt.

## Candidate Areas To Re-evaluate

Use the inventories and current code rather than this list as the final
authority, but consider at least:

- whether M182 intrinsic handoff facts should next feed a typed backend
  intrinsic translation request/result boundary, or whether that would cross
  too far into backend rendering for the next slice;
- whether source-operation request islands from M167 need an analogous handoff
  boundary before intrinsic/backend rendering work can be useful;
- whether backend value/type request facts from M180/M181 should feed explicit
  backend translation results before any body rendering milestone;
- declaration and loop gaps for `var<...>(...)`, `loop<range>(...)`, and
  `loop<unroll>(...)`;
- primitive-call completion, nested token-stream use, and deterministic
  body-token rendering policy.

Do not assume the largest corpus count is the best next milestone. Favor the
smallest slice that removes a real blocker without turning lowering into a
backend renderer or broad TSIL interpreter.

## Required Planning Task

This is a planning-only run. Do not edit production code or tests.

1. Inspect the accepted roadmap and lowering inventories.
2. Inventory the remaining generation/body/backend-query lowering gaps that
   still matter after M182.
3. Select exactly one M183 milestone, or record an explicit stop/return to
   planner condition if the next slice cannot be selected without a design
   decision.
4. Define M183 goal, scope, out-of-scope work, expected tests, required
   validation, and review/audit subagents.
5. Update `docs/redesign/implementation-roadmap.md`.
6. Update `docs/agent/current-redesign-state.md`.
7. Create the next concrete prompt under `docs/agent/runs/`, normally an
   `m183-...-execution-review-loop-prompt.md`.

## Required Planning Subagents

Use read-only planning/review subagents before finalizing the selected
milestone:

1. Evidence planner: inspect `tsldata/**/*.tsl` and redesign inventories to
   list the remaining lowering candidates and their corpus grounding.
2. Boundary/simplicity auditor: challenge the proposed M183 slice for
   overengineering, broad TSIL parsing, backend rendering, source repair,
   recursive all-context payload discovery, or another one-off request/result
   family without a durable boundary.
3. Documentation reviewer: verify the roadmap, state update, and next run
   prompt are coherent and follow the next-run prompt protocol.

The orchestrator owns final milestone selection, state updates, and next
prompt creation.

## Design Guardrails

- Keep the next task focused on lowering.
- Do not implement M183 in this prompt.
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

If planning review accepts the selected M183 milestone:

- update `docs/agent/current-redesign-state.md` to point at the new M183
  prompt;
- update `docs/redesign/implementation-roadmap.md` with the selected M183
  milestone;
- create the M183 concrete run prompt under `docs/agent/runs/`;
- record validation results.

If planning review finds the next slice is unclear, do not guess. Record the
blocking design question or stop condition in
`docs/agent/current-redesign-state.md` and create the appropriate follow-up
planning prompt.

Do not start M183 implementation in this prompt.

## Final Report

Report:

1. Selected M183 milestone and why it is useful.
2. Planning subagent verdicts and any follow-ups.
3. Files changed.
4. Validation command and exact result.
5. Next active prompt path.
