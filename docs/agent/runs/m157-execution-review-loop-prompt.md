# M157 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M156:

```text
Milestone 157: Generation-Control Selected-Branch Body Handoff
```

Milestones 1 through 156 are accepted. M156 added exact full-body
generation-control branch-region lowering for
`if<generation>(VALUE_QUERY) { ... } else<generation> { ... }`, returning the
selected and unselected source-owned branch token slices without parsing or
rendering branch bodies.

M157 is an implementation milestone. It should make that selected branch slice
usable by the existing lowering entry point, but only by handing selected
branch tokens to already accepted body lowering capabilities.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/kiss-generator-restart.md`
- `docs/redesign/requirements.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/domain-model.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/tsil-surface-inventory.md`
- `docs/redesign/missing-lowering-inventory.md`
- `tslgen/src/tslgen/domain/catalog.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/generation_control.py`
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`

## Goal

When a selected implementation body is an exact M156 generation-control
region, lower only the selected branch body through the existing
`Lowerer.lower(...)` body capabilities. The unselected branch must remain an
opaque token slice and must not produce diagnostics.

This is a composition/handoff slice, not a new TSIL parser and not branch body
rendering.

## Required Executor Task

Run exactly one write-capable executor for M157. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Add the smallest handoff needed so `Lowerer.lower(...)` can consume an
   exact M156 region by evaluating the condition, constructing a temporary
   source-owned `ImplementationBody` from the selected branch tokens only, and
   lowering that body with the already accepted body lowering path.
3. Preserve existing direct body lowering behavior for non-generation-control
   bodies.
4. Propagate M156 region/condition diagnostics deterministically when the
   region is malformed, unsupported, non-boolean, or missing required M155
   facts.
5. Propagate existing selected-branch body lowering diagnostics when the
   selected branch itself is unsupported by the accepted body lowering path.
6. Prove the unselected branch is not inspected, parsed, rendered, repaired,
   or diagnosed.
7. Add tests for:
   - true-branch selected body lowering;
   - false-branch selected body lowering;
   - unselected branch containing unsupported primitive calls, malformed
     directives, raw helper text, or other unsupported content without
     diagnostics;
   - selected branch unsupported body diagnostics still surfacing from the
     existing lowering path;
   - M156 condition diagnostics propagating unchanged;
   - non-generation-control bodies preserving M126-M156 behavior.
8. Update docs that describe the accepted M157 behavior and any newly
   discovered boundary details.
9. Leave final accepted-state updates to the orchestrator after read-only
   review returns `Accept` or `Accept With Follow-Ups`.

## Design Guardrails

- Keep this as a selected-branch token handoff. Do not parse branch body
  contents in the generation-control module.
- Reuse existing lowering behavior for the selected branch. Do not duplicate
  operation, `emit_return`, or primitive-call lowering rules.
- Do not inspect the unselected branch beyond carrying its provenance in the
  M156 result.
- Avoid broad recursion. M157 does not need to support nested
  `if<generation>` regions inside selected branches unless the implementation
  can do so naturally without new machinery; if in doubt, diagnose/defer.
- Do not add registries, dispatchers, worklists, fixpoint mechanisms, backend
  rendering, body-token rendering, source repair, or runtime reads from
  `tsldata`, `frozen`, or `tslgenold`.

## Must Preserve

- M107-M156 accepted behavior, diagnostics, source locations, and generated
  bytes.
- The source-owned body-token model.
- M155 isolated generation-value query behavior.
- M156 exact branch-region result behavior and branch-body opacity.
- Accepted primitive-call resolver/collector behavior and helper raw
  preservation.

## Out Of Scope

Recursive or nested generation-control lowering; `else if<generation>` chains;
plain `else`; loop execution; `loop<unroll>` or `loop<range>` lowering;
declaration lowering; non-type `let<...>` lowering; body-token rendering; raw
text replacement; source repair; raw expression parsing; arithmetic or
comparison folding around generation values; selector-attribute substitution;
mask lane constants; generic vector lengths/runtime lengths; backend-control
`if<compile>`, `else<compile>`, or `switch<compile>` lowering; casts, memory,
I/O, intrinsics, primitive-call rendering beyond already accepted exact paths,
backend rendering, dependency scheduling, runtime `tsldata`, `frozen`, or
`tslgenold` dependencies; broad registries, dispatchers, worklists, callback
maps, hidden backfeeds, or fixpoint mechanisms.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M157 is only selected-branch body handoff
   into existing lowering, with no parser/evaluator overgrowth, registries,
   dispatchers, worklists, backend rendering, or runtime data reads.
2. Boundary auditor: verify unselected branches remain opaque, branch bodies
   are not parsed by generation-control lowering, and M153/M155/M156
   boundaries remain intact.
3. Evidence auditor: verify the selected handoff is justified by the existing
   M156 branch-region boundary and does not claim support for branch-chain,
   plain-else, loop, declaration, or backend-control corpus forms.
4. Test auditor: verify tests cover selected true/false handoff, unselected
   unsupported content staying silent, selected unsupported diagnostics,
   condition diagnostic propagation, determinism, and preservation of
   non-generation-control behavior.
5. Documentation auditor: verify roadmap, behavioral/domain docs, missing
   inventory, and current state are coherent.
6. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
find tslgen -type d -name __pycache__ -print
```

If the executor adds focused M157 test files, include them in the compileall
and targeted pytest commands. Remove validation-created `__pycache__`
directories before the final cache check if any are created.

## Completion Rules

If M157 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M157 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside
this prompt after M157 is accepted. Do not start M158 until the next prompt
explicitly selects it.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 158 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Executor summary.
3. Review/audit verdicts and any follow-ups.
4. Validation commands and exact results.
5. Next active prompt path.
