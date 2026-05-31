# Post-M186 Lowering Completion Gate Planning Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M186 as accepted.

This is a planning-only milestone. Do not implement production code or tests.
The purpose is to decide whether the lowering surface is now complete by
contract after M186, or whether exactly one concrete lowering-owned gap remains.

## Accepted State

Accepted through:

```text
Milestone 186: Typed Generation Boolean Condition Grammar Boundary
```

M186 accepted a finite typed generation-condition grammar for
`if<generation>(COND)` / `else if<generation>(COND)`. Conditions now consume
accepted boolean generation leaves, integer-comparison leaves, `!`, `&&`,
`||`, and parentheses. It preserved existing M156-M160 branch selection and
M158 diagnostic precedence.

M186 deliberately did not add target-language expression parsing, raw operator
semantics, pointer/index predicates, helper-call semantics, recursive
generation-control lowering, rendering, backend translation, runtime
`tsldata`, `frozen`, or `tslgenold` dependencies, registries, dispatchers,
worklists, or recursive payload walkers.

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
- Accepted M155-M186 lowering implementation/tests as needed for facts, not
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
precedence, or every possible nesting context. Do not reopen accepted lowering
boundaries merely because backend/output integration still needs to consume
their facts or requests.

## Required Planning Task

1. Re-scan `tsldata/**/*.tsl` for generation-relevant TSIL keyword families
   and reconcile the result with accepted M155-M186 coverage.
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
   - a concrete M187 lowering implementation milestone, only if a real
     lowering-owned gap remains;
   - a docs-only M187 lowering-completion contract milestone, only if the
     classification itself needs to be made binding before leaving lowering;
   - a backend/output transition milestone, if lowering is complete by
     contract and the remaining work belongs to translation/rendering/output.
5. Update `docs/redesign/implementation-roadmap.md` with the planning result.
6. Update `docs/agent/current-redesign-state.md` to point at the next concrete
   prompt.
7. Create the next concrete prompt under `docs/agent/runs/`.

## Guardrails

- Keep focus on lowering completion, not implementation.
- Do not start M187 implementation in this prompt.
- Do not treat `details::*` support helpers as semantic lowering by default.
- Do not parse raw target-language assignments, indexing, operators,
  templates, loops, or helper bodies.
- Do not add or recommend a registry, dispatcher, plugin map, worklist,
  recursive payload walker, per-keyword framework, or broad TSIL parser unless
  the completion matrix proves that no smaller boundary can work.
- Do not force a lowering-owned milestone if the remaining gap is backend
  translation, rendering, artifact output, source convention, or broad parsing.
- Do not reopen M186 unless concrete evidence shows an accepted behavior
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
