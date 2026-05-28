# M160 Execution Review Loop Prompt

This is the active follow-on prompt after M159. Execute it only when
`docs/agent/current-redesign-state.md` points here and records M159 as
accepted.

You are executing and reviewing the accepted next milestone after M159:

```text
Milestone 160: Exact Generation Branch-Chain Region Selection
```

Milestones 1 through 159 are accepted. M155 added isolated selected-context
`value<generation>(...)` query lowering. M156 selected exact two-arm
`if<generation>` / `else<generation>` regions. M157 handed selected branches
to the existing body lowerer. M158 added exact integer comparisons. M159 added
explicit function-shaped generation arithmetic inside `value<generation>(...)`.

M160 is an implementation milestone. It should add the next TSIL control-flow
keyword shape: exact selected-body `else if<generation>` branch-chain
selection over source-owned body tokens.

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
- `tslgen/src/tslgen/lowering/generation_control.py`
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`

## Goal

Recognize exact selected generation-control branch chains shaped as:

```text
if<generation>(COND) {
  BODY_TOKENS
}
else if<generation>(COND) {
  BODY_TOKENS
}
else if<generation>(COND) {
  BODY_TOKENS
}
```

Evaluate branch conditions in source order through the already accepted
generation-control condition boundary. Select the first true branch and hand
only that branch's source-owned token slice to the existing body-lowering path.

This is not a general control-flow parser. It is a small branch-chain consumer
for already classified `if<generation>` directive tokens and raw brace tokens.

## Required Executor Task

Run exactly one write-capable executor for M160. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Inspect the body tokens produced for current `else if<generation>` corpus
   shapes and support the exact source-owned token representation already
   produced by M130/M131.
3. Add the smallest generation-control branch-chain lowering boundary for a
   leading `if<generation>(COND) { ... }` arm followed by one or more
   `else if<generation>(COND) { ... }` arms.
4. Reuse or extract the existing M156/M158/M159 condition lowering path rather
   than creating a second expression evaluator.
5. Select the first arm whose condition lowers to `True`.
6. Hand only the selected branch token slice to the existing body-lowering
   path, preserving M157 selected-branch behavior.
7. Keep unselected branch bodies opaque and silent, including unsupported
   primitive calls, raw helpers, malformed directives, or other unsupported
   body tokens.
8. Emit deterministic diagnostics for malformed branch-chain structure,
   condition diagnostics, ambiguous or missing braces, unsupported adjacent
   plain/final `else` forms, and no matching true arm in no-final-else chains.
9. Preserve M155 value-query behavior, M156 exact two-arm region behavior,
   M157 selected-branch handoff, M158 comparison behavior, and M159 arithmetic
   behavior.
10. Add focused tests for:
    - first, middle, and last matching branch selection;
    - first-true wins when later conditions are also true;
    - selected-branch handoff into an already accepted body-lowering path;
    - unselected branch opacity and silence;
    - condition diagnostics propagated from accepted M155/M158/M159 paths;
    - malformed branch-chain structure and missing/ambiguous brace diagnostics;
    - no matching true arm in a no-final-else chain;
    - rejection of unsupported plain/final `else` chain variants;
    - preservation of raw helper text inside unselected branches;
    - determinism.
11. Update docs that describe the accepted M160 behavior and any newly
    discovered boundary details.
12. Leave final accepted-state updates to the orchestrator after read-only
    review returns `Accept` or `Accept With Follow-Ups`.

## Design Guardrails

- Treat `else if<generation>` as an explicit TSIL generation-control keyword
  shape over source-owned body tokens.
- Reuse accepted generation condition lowering. Do not parse a new expression
  language for branch-chain conditions.
- Do not render branch bodies or repair raw source text.
- Do not add plain `else`, final `else<generation>` in a chain, recursive or
  nested generation-control lowering, loop/declaration/backend-control
  lowering, backend rendering, dependency scheduling, runtime reads from
  `tsldata`, `frozen`, or `tslgenold`, or broad registries, dispatchers,
  worklists, callback maps, hidden backfeeds, or fixpoint mechanisms.

## Must Preserve

- M107-M159 accepted behavior, diagnostics, source locations, and generated
  bytes.
- M155 isolated generation-value query behavior.
- M156 exact two-arm branch-region behavior.
- M157 selected-branch handoff behavior.
- M158 comparison predicate behavior.
- M159 explicit generation arithmetic behavior.
- Accepted primitive-call resolver/collector behavior and helper raw
  preservation.

## Out Of Scope

Plain `else`; final `else<generation>` in a chain; recursive or nested
generation-control lowering; broad control-flow parsing; raw expression
parsing; raw arithmetic operator parsing; right-hand value queries in
comparisons; branch-body rendering; loop execution; `loop<unroll>` or
`loop<range>` lowering; declaration lowering; non-type `let<...>` lowering;
backend-control `if<compile>`, `else<compile>`, or `switch<compile>`
lowering; casts, memory, I/O, intrinsics, backend rendering, dependency
scheduling, output writing, source repair, runtime `tsldata`, `frozen`, or
`tslgenold` dependencies; broad registries, dispatchers, worklists, callback
maps, hidden backfeeds, or fixpoint mechanisms.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M160 adds only exact
   `else if<generation>` branch-chain selection over source-owned body tokens
   and avoids raw expression parsing, broad control-flow parsing, registries,
   dispatchers, worklists, backend rendering, source repair, and runtime data
   reads.
2. Boundary auditor: verify M155 value queries, M156 two-arm regions, M157
   selected-branch handoff, M158 comparisons, M159 arithmetic, helper raw
   preservation, and unselected-branch opacity remain intact.
3. Evidence auditor: verify the selected branch-chain direction is grounded in
   current TSIL source/control evidence and that helper raw text remains raw.
4. Test auditor: verify the tests cover branch selection order, first-true
   wins, selected handoff, unselected silence, condition diagnostics,
   malformed structures, no-match diagnostics, unsupported `else` forms,
   helper preservation, and determinism.
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

If the executor adds focused M160 test files, include them in the compileall
and targeted pytest commands. Remove validation-created `__pycache__`
directories before the final cache check if any are created.

## Completion Rules

If M160 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M160 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside
this prompt after M160 is accepted. Do not start M161 until the next prompt
explicitly selects it.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 161 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Executor summary.
3. Review/audit verdicts and any follow-ups.
4. Validation commands and exact results.
5. Next active prompt path.
