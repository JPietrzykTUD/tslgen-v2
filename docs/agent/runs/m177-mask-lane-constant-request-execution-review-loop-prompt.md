# M177 Mask Lane Constant Request Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M176 planning as accepted.

You are executing and reviewing:

```text
Milestone 177: Mask Lane Constant Support-Helper Request Boundary
```

Milestones 1 through 176 are accepted. M176 decided that exact
`value<generation>(mask::lane::all_true)` and
`value<generation>(mask::lane::all_false)` source islands behave like
backend/support-helper needs, not materialized generation values. M177 should
implement that boundary as typed request discovery only.

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
- `tsldata/primitives/bitwise/bit_ops.tsl`
- `tsldata/primitives/comparison/fundamental.tsl`
- `tsldata/primitives/conversion/mask_specific.tsl`
- `tsldata/primitives/mask/construct.tsl`
- `frozen/tsl-gen/tsl_gen/tsil_engine/expansion_support.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/backend_value_queries.py`
- `tslgen/src/tslgen/lowering/generation_values.py`
- `tslgen/src/tslgen/lowering/lowerer.py`

## Goal

Add a narrow typed request discovery boundary for exact mask lane constants:

```text
value<generation>(mask::lane::all_true)
value<generation>(mask::lane::all_false)
```

The request must record only:

- polarity: `all_true` or `all_false`;
- source text;
- source location.

It must not contain C++ helper text, Rust helper text, integer values,
Python booleans, selected mask representation guesses, or backend spelling
results.

## Required Executor Task

Run exactly one write-capable executor for M177. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Add small typed request/discovery values for mask lane constants. Use the
   existing backend value query discovery shape as a reference for source-owned
   text segmentation, not as a legacy dependency.
3. Discover exact request islands in one raw text fragment and in selected
   implementation bodies containing raw body-token text. Preserve surrounding
   raw text/tokens.
4. Accept only `mask::lane::all_true` and `mask::lane::all_false`.
5. Diagnose malformed `value<generation>(mask::lane::...)` islands with
   unbalanced outer delimiters.
6. Diagnose unknown mask-lane names such as `mask::lane::maybe` rather than
   treating them as opaque supported requests.
7. Keep `lower_generation_value_query(...)` materialized value behavior
   unchanged: mask lane constants must not become `LoweredGenerationValue`
   payloads and must not become branch/loop arithmetic values.
8. Export the new request/discovery values only through the normal lowering
   public surface if existing local patterns require it.
9. Add focused tests, preferably in
   `tslgen/tests/test_m177_mask_lane_constant_requests.py`, covering:
   exact `all_true` and `all_false` request discovery;
   multiple islands with surrounding raw text;
   representative corpus contexts: nested `set1(...)` call argument,
   `var<const_infer>` initializer pair, and direct assignment text;
   malformed delimiter diagnostics;
   unknown mask-lane diagnostics;
   no backend helper text in request values;
   `lower_generation_value_query(...)` still does not materialize these forms
   as `LoweredGenerationValue`.
10. Update redesign docs if implementation reveals a sharper boundary or
    diagnostic name.
11. Leave final accepted-state updates to the orchestrator after read-only
    review returns `Accept` or `Accept With Follow-Ups`.

## Design Guardrails

- This is a request/discovery boundary, not backend rendering.
- Do not add C++ or Rust helper text to lowering values.
- Do not infer selected mask representation, base type, lane count, or
  extension-specific helper shape.
- Do not treat mask lane constants as Python booleans, integers, or normal
  `LoweredGenerationValue` payloads.
- Do not parse surrounding primitive calls, declarations, assignments, loops,
  branch bodies, or expressions.
- Do not change `.tsl` source conventions in this milestone.
- Do not make `frozen`, `tslgenold`, or runtime `tsldata` a runtime
  dependency.
- Avoid registries, dispatchers, worklists, callback maps, hidden backfeeds,
  or broad expression parsers.

## Must Preserve

- M155/M168/M175.5 materialized generation value behavior.
- M164 backend value query request discovery behavior and diagnostics.
- M153 backend/support helper raw preservation for `details::*`.
- Existing source-owned raw token preservation and no source repair.

## Out Of Scope

Backend helper translation; renderer integration; generated output; primitive
call rendering; declaration rendering; assignment rendering; loop execution;
branch selection; source replacement; source convention migration; mask
representation semantics beyond request polarity; dependency scheduling;
runtime `tsldata`, `frozen`, or `tslgenold` dependencies; broad TSIL or
target-language expression parsing.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M177 is a small typed request/discovery
   boundary and does not create a renderer or semantic value family.
2. Boundary auditor: verify mask lane constants do not become
   `LoweredGenerationValue`, Python bool/int, or raw backend strings, and that
   M153/M155/M164/M175.5 behavior is preserved.
3. Evidence auditor: verify the accepted forms and contexts match the M176
   corpus evidence and frozen helper behavior is cited only as behavior
   evidence.
4. Test auditor: verify exact positive, malformed, unknown, context,
   no-backend-text, and no-materialized-generation-value tests cover the
   slice.
5. Documentation auditor: verify docs, roadmap, current state, and next prompt
   are coherent.
6. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m177_mask_lane_constant_requests.py
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m177_mask_lane_constant_requests.py
find tslgen -type d -name __pycache__ -print
```

Remove validation-created `__pycache__` directories before the final cache
check if any are created.

## Completion Rules

If M177 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M177 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt.

Do not start Milestone 178 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Executor summary.
3. Review/audit verdicts and any follow-ups.
4. Validation commands and exact results.
5. Next active prompt path.
