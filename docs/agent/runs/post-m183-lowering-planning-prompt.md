# Post-M183 Lowering Planning Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M183 as accepted.

You are planning the next lowering milestone:

```text
Post-M183 lowering planning for Milestone 184:
Lowering Completeness Audit / Remaining TSIL Keyword Closure
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

Prepare M184 as a planning/audit milestone, not an implementation milestone:

```text
Milestone 184: Lowering Completeness Audit / Remaining TSIL Keyword Closure
```

The M184 milestone should identify the remaining generation-relevant TSIL
keyword/lowering surface, classify what is already covered, what is truly
lowering-owned, and what belongs to backend translation/rendering, then select
the next executable lowering slice after that audit.

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
3. Plan M184 as a read-only completeness audit / keyword-closure milestone.
4. Define the exact evidence M184 must gather:
   - remaining generation-relevant TSIL keyword families;
   - accepted discovery/classification/handoff coverage through M183;
   - gaps that are lowering-owned;
   - gaps that should be deferred to backend translation/rendering;
   - any gaps that would require broad parsing and should not be selected.
5. Pressure-test whether the audit itself would drift into overengineering:
   - Is it a durable semantic fact, request, result, inventory, provenance
     value, rule input, or stage envelope?
   - Is it only an inventory/planning artifact, or does it accidentally create
     another one-off runtime wrapper?
   - Would a simpler documentation inventory express the same contract?
   - Does it keep raw strings only at source-owned opaque/provenance
     boundaries or backend-owned unresolved text?
6. Write the concrete
   `docs/agent/runs/m184-lowering-completeness-audit-planning-prompt.md`.
   It must be planning/audit only and must not implement lowering code.
7. Update `docs/redesign/implementation-roadmap.md`,
   `docs/agent/current-redesign-state.md`, and any inventories/spec docs whose
   accepted planning state changes.

## Areas M184 Must Audit

M184 must audit these areas without selecting implementation prematurely:

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
evaluation; language map evaluation; source-operation translation
implementation; selecting source-operation translation before the audit
classifies whether any part is still lowering-owned; recursive payload
discovery through arbitrary contexts; argument splitting; broad TSIL
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
- create
  `docs/agent/runs/m184-lowering-completeness-audit-planning-prompt.md`;
- do not start M184 implementation.

If planning needs revision, create a focused planning-revision prompt. If the
boundary review returns `Return To Planner` or `Reject`, record that condition
and create the appropriate next prompt instead of selecting an executor slice.

## Final Report

Report:

1. Confirmation that M184 is planned as a lowering completeness audit /
   remaining TSIL keyword closure milestone.
2. Why that audit is useful and why it is not overengineering.
3. Review/audit verdicts.
4. Validation command and exact result.
5. Next active prompt path.
