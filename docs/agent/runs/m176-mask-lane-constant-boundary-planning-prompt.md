# M176 Mask Lane Constant Boundary Planning Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M175.5 as accepted.

You are planning and reviewing:

```text
Milestone 176: Mask Lane Constant Lowering Boundary Planning
```

Milestones 1 through 175.5 are accepted. M175 completed the
descriptor-backed vector-member type argument bridge for existing generation
value `type::*` queries, and M175.5 added fixed byte-size lowering for
register and mask vector members where explicit extension metadata proves the
size. The next remaining generation-value family in the current corpus is
`mask::lane::all_true` / `mask::lane::all_false`, but legacy evidence suggests
these are backend helper expressions rather than plain generator-time boolean
values. M176 must settle the boundary before any implementation.

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
- `docs/redesign/flaws-to-fix.md`
- `docs/redesign/missing-lowering-inventory.md`
- `docs/redesign/generation-value-query-inventory.md`
- `docs/redesign/generation-time-semantic-lowering.md`
- `tsldata/primitives/**/*.tsl`
- `frozen/tsl-gen/tsl_gen/tsil_engine/expansion_support.py`
- `tslgen/src/tslgen/lowering/generation_values.py`
- `tslgen/src/tslgen/lowering/model.py`

## Goal

Decide the correct next lowering boundary for:

```text
value<generation>(mask::lane::all_true)
value<generation>(mask::lane::all_false)
```

The plan must answer whether a future executor should produce:

- a typed backend-literal request;
- a symbolic generation value that later backend stages translate;
- a raw backend-owned handoff;
- or a documented deferral because the required mask representation facts are
  not yet available.

## Required Planning Task

Do not implement production code in M176. The planning executor may edit only
redesign docs, current state, and the next run prompt.

The planner should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Inventory current `tsldata/**/*.tsl` occurrences of
   `mask::lane::all_true` and `mask::lane::all_false`, grouped by surrounding
   context such as primitive-call argument, declaration initializer, and raw
   assignment.
3. Inspect `frozen/tsl-gen/tsl_gen/tsil_engine/expansion_support.py` only as
   behavior evidence. Record the observed C++ and Rust helper expression
   behavior without porting legacy structure.
4. Compare the evidence to current clean lowering models:
   `LoweredGenerationValue`, backend request discovery, source-owned raw
   tokens, and deferred rendering.
5. Account explicitly for FTF-001 in `docs/redesign/flaws-to-fix.md`: explain
   whether the next slice preserves the mismatch, narrows it into a typed
   backend/support-helper request, or defers because the mismatch should be
   fixed by a later source convention.
6. Decide the smallest safe executable follow-up. Prefer a narrow typed value
   or request boundary only if it avoids backend text guessing and helps
   future rendering.
7. Update redesign docs with the boundary decision, open questions, or
   deferral rationale.
8. Create the next concrete prompt under `docs/agent/runs/`. If the decision
   selects implementation, create an M177 execution-review-loop prompt. If the
   decision is blocked, create the appropriate planner/finalization prompt and
   record the stop or blocker in current state.

## Design Guardrails

- Do not treat `mask::lane::all_true` and `mask::lane::all_false` as Python
  booleans unless the plan proves that is the backend-neutral semantic value.
- Do not inject backend helper text into generation lowering.
- Do not hide the mismatch with `details::*` support-helper handling. M176
  must either preserve it deliberately as a typed deferred request or record
  why implementation is deferred until the source/lowering convention is made
  consistent.
- Do not add production code, renderer code, generated output, parser
  behavior, primitive-call rendering, declaration rendering, loop execution,
  source replacement, or broad expression parsing in M176.
- Do not make `frozen`, `tslgenold`, or runtime `tsldata` a runtime
  dependency.
- Keep this as a lowering-boundary decision, not a legacy migration map.

## Required Review/Audit Subagents

Use read-only subagents before accepting the plan:

1. Evidence auditor: verify corpus counts/contexts and frozen behavior
   evidence.
2. Boundary auditor: verify the proposed boundary does not guess backend text
   or broaden generation value semantics incorrectly.
3. Architecture reviewer: verify the next executable slice, if any, is small,
   typed, and aligned with the clean restart simplicity policy.
4. Documentation auditor: verify roadmap, behavioral specs, decisions,
   inventory, and current state are coherent.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
```

## Completion Rules

If M176 planning review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M176 planning accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

If review returns `Needs Revision`, perform one focused docs-only revision and
then a focused re-review. If review returns `Return To Planner` or `Reject`,
record the blocker and create the appropriate planner/rollback prompt.

Do not start implementation in M176.

## Final Report

Report:

1. Files changed.
2. Planning summary and selected boundary.
3. Review/audit verdicts and follow-ups.
4. Validation command and exact result.
5. Next active prompt path.
