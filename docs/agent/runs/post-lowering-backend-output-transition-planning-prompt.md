# Post-Lowering Backend/Output Transition Planning Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records the post-M187 lowering completion gate as accepted.

This is a planning/documentation task. Do not implement production code or
tests. Use read-only subagents for evidence, boundary/simplicity,
documentation, and validation audits. The orchestrator owns final state and
next-prompt updates.

## Accepted State

Accepted through:

```text
Post-M187 Lowering Completion Gate: lowering complete by current contract
```

Accepted lowering now provides typed facts, typed semantic values, typed
request islands, typed handoff values, and source-owned opaque text/token
segments for the current generation-relevant TSIL surface. Remaining known
work is backend/output-owned or broad/deferred.

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
- `docs/redesign/missing-lowering-inventory.md`
- `docs/redesign/lowering-completeness-audit.md`
- `docs/redesign/tsil-surface-inventory.md`
- Existing backend/output code and tests under `tslgen/src/tslgen/backends`,
  `tslgen/src/tslgen/pipeline`, and `tslgen/tests`.

## Goal

Select exactly one first backend/output milestone after lowering completion.

The selected milestone should move the research prototype closer to
deterministic generated C++/Rust artifacts from `.tsl` source data while
consuming accepted lowering outputs intentionally. Prefer the smallest
high-value slice that proves the backend/output boundary without reopening
lowering.

## Candidate Areas To Evaluate

Evaluate at least:

- backend type/value translation requests from accepted
  `type<backend>(...)` and `value<backend>(...)` handoffs;
- backend intrinsic request/handoff translation;
- source-operation request/handoff translation for `cast<...>`,
  `mem<...>`, and `io<...>`;
- backend-control request rendering for `if<compile>`, `else<compile>`, and
  `switch<compile>`;
- M185 mask keyword request translation;
- M187 backend/output request translation for `assume_aligned<...>(...)`,
  `array_type<...>`, and `pack<...>(...)`;
- raw body-token rendering policy around typed request islands;
- deterministic artifact planning/writing for one tiny selected fixture;
- supplementary static assets and render templates under the accepted
  `supplementary/` layout, with no backend semantics hidden in templates;
- data-driven backend metadata ingestion from `tsldata/detail/lang/**` and
  extension metadata without dictionary-shaped semantic shortcuts downstream.

The selected milestone may be a planning milestone if the evidence shows that
backend/output ownership needs one more design decision before execution.

## Guardrails

- Do not implement code in this planning prompt.
- Do not add new lowering semantics unless the prompt returns to a lowering
  planner because new `.tsl` evidence invalidates the post-M187 completion
  result.
- Do not make `frozen/` or `tslgenold/` a runtime dependency.
- Do not make renderers evaluate raw `type<generation>`,
  `value<generation>`, `type<backend>`, `value<backend>`, intrinsic,
  source-operation, mask, or backend/output island text.
- Do not choose a milestone that requires broad target-language parsing,
  arbitrary expression precedence, source repair, or recursive payload
  walking.
- Do not replace typed rules with ad-hoc raw-key dictionaries past
  parser/catalog boundaries.
- Keep the selected milestone small enough for one execution-review loop.

## Required Review/Audit Subagents

Run read-only subagents:

1. Evidence auditor: current backend/output code, tests, and corpus evidence.
2. Boundary/simplicity auditor: no lowering reopening, no renderer-side
   semantic inference, no broad parser.
3. Documentation auditor: roadmap/state/prompt consistency.
4. Validation auditor: required validation command and workspace hygiene.

If any auditor returns `Needs Revision`, make only focused documentation/prompt
fixes and re-run the relevant focused audit. If any returns `Return To
Planner` or `Reject`, record that result and create the appropriate next
prompt.

## Required Validation

Run:

```bash
git diff --check
```

Report the exact result.

## Completion Rules

Before finishing:

- update `docs/redesign/implementation-roadmap.md` with the selected
  backend/output milestone;
- update other redesign docs if the planning pass changes a behavior,
  decision, open question, or boundary classification;
- update `docs/agent/current-redesign-state.md`;
- create the next concrete prompt under `docs/agent/runs/`;
- do not start the selected milestone.

## Final Report

Report:

1. Selected backend/output milestone.
2. Why it is the highest-value first slice after lowering completion.
3. Review/audit verdicts.
4. Validation command and exact result.
5. Next active prompt path.
