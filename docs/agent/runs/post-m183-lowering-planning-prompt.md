# Post-M183 Lowering Planning Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M183 as accepted.

You are planning the next lowering milestone:

```text
Post-M183 lowering planning for Milestone 184
```

Milestones 1 through 183 are accepted. M183 added a focused semantic handoff
from accepted M167 `cast<...>(...)`, `mem<...>(...)`, and `io<...>(...)`
source-operation request islands to finite typed selector values while keeping
arguments opaque and source-owned.

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
- `docs/redesign/tsil-surface-inventory.md`
- `docs/redesign/flaws-to-fix.md` if present
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/source_operation_handoff.py`
- `tslgen/src/tslgen/lowering/backend_intrinsic_handoff.py`

Use `tsldata/**/*.tsl` only as corpus evidence for remaining lowering surface.
Do not read `frozen/` or `tslgenold/` unless the planner needs historical
syntax evidence that cannot be answered from redesign docs or current
`tsldata`.

## Goal

Select exactly one next M184 milestone that gets the research prototype closer
to complete generation support while staying on the lowering side of the
architecture.

The planner must actively avoid the repeated slippery path:

- do not invent a broad TSIL expression/statement parser;
- do not add a new request/result family merely because the previous
  milestone did;
- do not treat backend translation or rendering as lowering unless the
  proposed boundary is explicitly an unresolved typed handoff over accepted
  lowering facts;
- do not parse source-operation arguments, intrinsic arguments, declarations,
  or raw target-language expressions unless the selected milestone names one
  exact accepted source form and explains why it is still lowering-owned.

## Required Planning Task

Run a planning pass, not an executor:

1. Inspect current accepted M127-M183 lowering coverage.
2. Re-inventory the remaining generation-relevant TSIL/lowering gaps from
   `docs/redesign/missing-lowering-inventory.md` and current `tsldata`.
3. Identify the highest-value next lowering-owned slice for M184.
4. Pressure-test whether the candidate would be overengineering:
   - Is it a durable semantic fact, request, result, inventory, provenance
     value, rule input, or stage envelope?
   - Is it needed by at least two concrete accepted/forthcoming stages, or is
     it a one-off wrapper?
   - Would a simpler class/protocol boundary express the same contract?
   - Does it keep raw strings only at source-owned opaque/provenance
     boundaries or backend-owned unresolved text?
5. If M184 should be an executor milestone, write the concrete
   `docs/agent/runs/m184-...-execution-review-loop-prompt.md`.
6. If no safe executor milestone is ready, write a concrete planner or
   return-to-planner prompt instead and record why.
7. Update `docs/redesign/implementation-roadmap.md`,
   `docs/agent/current-redesign-state.md`, and any inventories/spec docs whose
   accepted planning state changes.

## Candidate Areas To Consider

Consider, but do not assume, these areas:

- Remaining lowering-owned handoffs for accepted backend/source operation
  facts that still need typed unresolved requests before backend translation.
- Whether source-operation translation is now backend-owned and should be
  deferred rather than planned as lowering.
- Whether body-token rendering policy is actually output/backend work rather
  than lowering.
- Whether `model.py` size should trigger a focused model-boundary split before
  another semantic handoff adds more public model objects.
- Remaining generation query/control/declaration gaps that block source-to-
  artifact prototype work without requiring broad parsing.
- Any missing TSIL keyword surface from the inventory that is still
  generation-relevant and not yet discovered/classified.

## Out Of Scope

M184 implementation; backend rendering; generated artifacts; backend map
evaluation; language map evaluation; source-operation translation unless the
planner explicitly defines a lowering-owned unresolved handoff; recursive
payload discovery through arbitrary contexts; argument splitting; broad TSIL
expression or statement parsing; target-language parsing; source repair;
dependency scheduling; runtime `tsldata`, `frozen`, or `tslgenold`
dependencies; registries, dispatchers, plugin maps, worklists, or broad
frameworks.

## Required Planning/Audit Subagents

Use read-only subagents:

1. Evidence planner/auditor: identify remaining lowering-relevant TSIL keyword
   families from current `tsldata/**/*.tsl` and docs, excluding backend
   translation metadata false positives.
2. Boundary/simplicity auditor: challenge the selected M184 candidate for
   overengineering, backend/rendering leakage, raw-string leakage, and
   unnecessary request/result layering.
3. Documentation auditor: verify the roadmap/state/next-prompt transition is
   coherent and the next prompt follows
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
- mark post-M183 lowering planning accepted in
  `docs/redesign/implementation-roadmap.md`;
- create the next concrete prompt under `docs/agent/runs/`;
- do not start M184 implementation.

If planning needs revision, create a focused planning-revision prompt. If the
boundary review returns `Return To Planner` or `Reject`, record that condition
and create the appropriate next prompt instead of selecting an executor slice.

## Final Report

Report:

1. Selected M184 candidate or stop/return-to-planner decision.
2. Why the candidate is useful and why it is not overengineering.
3. Review/audit verdicts.
4. Validation command and exact result.
5. Next active prompt path.
