# Post-M185 Lowering Completion Gate Planning Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M185 as accepted.

This is a planning-only milestone. Do not implement production code or tests.
The purpose is to decide whether lowering still has a concrete missing
generation-relevant TSIL keyword family, or whether lowering is complete by
contract and the workflow should move to backend/output integration.

## Accepted State

Accepted through:

```text
Milestone 185: Exact Mask Keyword Request / Selector Boundary
```

M185 accepted exact `mask<...>(...)` source-island discovery and typed selector
classification for `zero`, `test`, `set`, and `set:1`. It deliberately keeps
arguments opaque and does not translate masks, render backend helpers, split
arguments, recursively lower payloads, or parse target-language expressions.

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
- `docs/redesign/missing-lowering-inventory.md`
- `docs/redesign/lowering-completeness-audit.md`
- `docs/redesign/tsil-surface-inventory.md`
- `docs/redesign/flaws-to-fix.md`
- Accepted M155-M185 lowering implementation/tests as needed for facts, not
  as a reason to extend the middleware shape.

Use `tsldata/**/*.tsl` as the ground-truth corpus. Use `frozen/` or
`tslgenold/` only if a planning question cannot be answered from current docs
plus current `tsldata`, and record why that extra evidence was necessary.

## Completion Definition

For this prompt, lowering is complete enough when every generation-relevant
TSIL keyword family observed in `tsldata/**/*.tsl` is classified as one of:

- accepted typed semantic fact/value lowering;
- accepted typed unresolved request/handoff for a later backend/output stage;
- source-authored raw text or support helper that lowering must preserve;
- backend translation/rendering/output-owned work;
- broad parsing/deferred work that must not be pulled into lowering;
- no current corpus evidence.

Lowering is not required to understand arbitrary target-language-looking
assignments, indexing, loops, operators, helper-call bodies, expression
precedence, or every possible nesting context.

## Required Planning Task

1. Re-scan `tsldata/**/*.tsl` for generation-relevant TSIL keyword families
   and reconcile the result with accepted M155-M185 coverage.
2. Produce a concise completion matrix that names every remaining family and
   classifies it under the completion definition above.
3. Pressure-test the known tempting candidates explicitly:
   - `assume_aligned<...>(...)`;
   - `array_type<...>`;
   - `pack<...>(...)`;
   - recursive discovery inside arbitrary opaque payload carriers;
   - loop execution/substitution;
   - declaration rendering / body-token rendering policy;
   - backend-control translation/rendering;
   - backend value/type translation/rendering;
   - intrinsic translation/rendering;
   - source-operation translation/rendering for `cast<...>`, `mem<...>`,
     and `io<...>`;
   - mask keyword translation/rendering;
   - support-helper calls such as `details::*`.
4. Decide exactly one of:
   - a concrete M186 lowering implementation milestone, only if a real
     lowering-owned gap remains;
   - a docs-only M186 lowering-completion contract milestone, only if the
     classification itself needs to be made binding before leaving lowering;
   - a backend/output transition milestone, if lowering is complete by
     contract and the remaining work belongs to translation/rendering/output.
5. Update `docs/redesign/implementation-roadmap.md` with the planning result.
6. Update `docs/agent/current-redesign-state.md` to point at the next concrete
   prompt.
7. Create the next concrete prompt under `docs/agent/runs/`.

## Guardrails

- Keep focus on lowering completion, not implementation.
- Do not start M186 implementation in this prompt.
- Do not treat `details::*` support helpers as semantic lowering by default.
- Do not parse raw target-language assignments, indexing, operators,
  templates, loops, or helper bodies.
- Do not add or recommend a registry, dispatcher, plugin map, worklist,
  recursive payload walker, per-keyword framework, or broad TSIL parser unless
  the completion matrix proves that no smaller boundary can work.
- Do not force a lowering-owned milestone if the remaining gap is backend
  translation, rendering, artifact output, source convention, or broad parsing.
- Do not reopen M185 unless concrete evidence shows an accepted behavior
  blocker.

## Required Subagents

Use read-only subagents:

1. Evidence auditor: verify the completion matrix against current
   `tsldata/**/*.tsl`.
2. Boundary/simplicity auditor: challenge the decision for backend/rendering
   leakage, broad parsing, or overengineering.
3. Documentation auditor: verify roadmap/state/next-prompt coherence with
   `docs/agent/next-run-prompt-protocol.md`.

Subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
```

## Completion Rules

If planning is accepted:

- update `docs/agent/current-redesign-state.md`;
- record the planning result in `docs/redesign/implementation-roadmap.md`;
- create the next concrete run prompt under `docs/agent/runs/`;
- do not start the selected next milestone.

If review returns `Needs Revision`, make only focused documentation/planning
revisions and re-run the necessary read-only review. If review returns
`Return To Planner` or `Reject`, stop and create the appropriate next prompt.

## Final Report

Report:

1. Whether lowering is complete by contract or which lowering-owned gap remains.
2. Selected next milestone or backend/output transition decision.
3. Why the selected step avoids the slippery path.
4. Review/audit verdicts.
5. Validation command and exact result.
6. Next active prompt path.
