# Post-M185 Lowering Planning Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M185 as accepted.

You are planning the next lowering-focused milestone after:

```text
Milestone 185: Exact Mask Keyword Request / Selector Boundary
```

M185 closed the `mask<...>(...)` keyword-family gap identified by the M184
lowering completeness audit. The next task must stay focused on lowering, but
it must not invent another implementation slice if the remaining work is
really backend translation, rendering, output integration, or broad TSIL/body
parsing.

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
- M185 implementation files:
  - `tslgen/src/tslgen/lowering/mask_keywords.py`
  - `tslgen/src/tslgen/lowering/lowerer.py`
  - `tslgen/src/tslgen/lowering/__init__.py`
  - `tslgen/tests/test_m185_mask_keyword_requests.py`

Use `tsldata/**/*.tsl` as corpus evidence only. Use `frozen/` or
`tslgenold/` only if a planning question cannot be answered from current docs
plus current `tsldata`, and record why that extra evidence was needed.

## Goal

Select exactly one next concrete milestone after M185, or record a
return-to-planner/stop condition if no safe lowering-owned milestone remains.

The planning result must answer:

1. Which generation-relevant TSIL keyword families remain unaccepted after
   M185?
2. Which remaining gaps are truly lowering-owned rather than backend
   translation/rendering/output work?
3. Which tempting candidates would recreate broad parsing, recursive payload
   walking, or per-family middleware?
4. What is the next highest-value executable lowering slice, if one exists?

## Required Planning Task

Run this as a planning milestone. Do not implement production code or tests.

1. Inspect accepted M155-M185 lowering coverage in the roadmap, behavior docs,
   domain model, and inventories.
2. Reconcile the M184 audit with the accepted M185 implementation.
3. Re-check the current corpus for any generation-relevant TSIL keyword family
   still missing from accepted lowering coverage.
4. Explicitly pressure-test these candidate areas:
   - `assume_aligned<...>(...)`;
   - `array_type<...>`;
   - `pack<...>(...)`;
   - recursive discovery of accepted islands inside arbitrary opaque payload
     carriers;
   - loop execution/substitution;
   - declaration rendering / body-token rendering policy;
   - backend-control, backend-value/type, intrinsic, source-operation, and
     mask translation/rendering;
   - support-helper calls such as `details::*`.
5. Classify each candidate as one of:
   - next lowering-owned executable slice;
   - backend translation/rendering/output-owned;
   - broad parsing/deferred;
   - source-convention follow-up;
   - no current corpus evidence.
6. Select exactly one next milestone. If the next safe step is planning rather
   than implementation, say so and create that prompt. If it is executable,
   create an execution-review-loop prompt.
7. Update `docs/redesign/implementation-roadmap.md` and
   `docs/agent/current-redesign-state.md`.
8. Create the next concrete run prompt under `docs/agent/runs/`.

## Guardrails

- Keep focus on lowering. Do not start backend rendering or generated output.
- Do not treat `details::*` support helpers as semantic lowering by default.
- Do not parse raw target-language assignments, indexing, operators,
  templates, or loops.
- Do not add a registry, dispatcher, plugin map, worklist, recursive payload
  walker, or per-keyword framework as a planning default.
- Do not reopen M185 unless evidence shows a concrete blocker.
- If the honest next step is not lowering-owned, record that boundary instead
  of forcing a lowering implementation milestone.

## Required Subagents

Use read-only subagents:

1. Evidence auditor: verify the remaining-candidate classification against
   current `tsldata/**/*.tsl`.
2. Boundary/simplicity auditor: challenge the selected next milestone for
   backend/rendering leakage, broad parsing, or overengineering.
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
- do not start the next milestone.

If review returns `Needs Revision`, make only focused documentation/planning
revisions and re-run the necessary read-only review. If review returns
`Return To Planner` or `Reject`, stop and create the appropriate next prompt.

## Final Report

Report:

1. Selected next milestone or stop/return-to-planner decision.
2. Why the selected step is useful and still in scope.
3. Review/audit verdicts.
4. Validation command and exact result.
5. Next active prompt path.
