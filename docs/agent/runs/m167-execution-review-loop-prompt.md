# M167 Execution Review Loop Prompt

This is the active follow-on prompt after M166. Execute it only when
`docs/agent/current-redesign-state.md` points here and records M166 as
accepted.

You are executing and reviewing the accepted next milestone after M166:

```text
Milestone 167: Exact Cast/Memory/I/O Request-Island Boundary
```

Milestones 1 through 166 are accepted. M166 records exact
`intrin<...>(...)` and `intrin_compose<...>(...)` islands as unresolved
backend intrinsic requests over source-owned text and contiguous raw
body-token runs while preserving payloads and surrounding tokens opaque.

M167 is an implementation milestone. It should add the next source/backend
lowering boundary for exact keyword islands that share the same outer TSIL
shape:

```text
cast<CAST_MODE_TEXT>(ARGUMENT_TEXT)
mem<MEMORY_OPERATION_TEXT>(ARGUMENT_TEXT)
io<IO_OPERATION_TEXT>(ARGUMENT_TEXT)
```

These islands are generation relevant, but M167 must not solve them at
generation time. It records unresolved request islands and preserves
surrounding source text/tokens.

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
- `tslgen/src/tslgen/syntax/tsil_lexical.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/src/tslgen/lowering/backend_intrinsics.py`
- `tslgen/src/tslgen/lowering/backend_value_queries.py`
- `tslgen/src/tslgen/lowering/backend_control.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`
- `tslgen/tests/test_m1625_tsil_lexical.py`
- `tslgen/tests/test_m163_generation_variables.py`
- `tslgen/tests/test_m164_backend_value_queries.py`
- `tslgen/tests/test_m165_backend_control.py`
- `tslgen/tests/test_m166_backend_intrinsics.py`

## Goal

Recognize exact request islands in source-owned text and body token streams:

```text
cast<CAST_MODE_TEXT>(ARGUMENT_TEXT)
mem<MEMORY_OPERATION_TEXT>(ARGUMENT_TEXT)
io<IO_OPERATION_TEXT>(ARGUMENT_TEXT)
```

The result should record unresolved requests in source order and preserve all
non-request text/tokens as source-owned opaque spans. The keyword kind, angle
payload text, and argument payload text remain opaque for later typed
translation/rendering work.

The accepted shape is the keyword island itself, not any surrounding corpus
pattern, return directive, declaration, assignment, branch body, loop body,
primitive-call argument, intrinsic argument, backend-control payload, raw
target-language statement, or generated target-language line.

## Required Executor Task

Run exactly one write-capable executor for M167. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Inventory current `cast<...>(...)`, `mem<...>(...)`, and `io<...>(...)`
   evidence across all `tsldata/**/*.tsl` files. Use corpus examples as
   evidence for the keyword surface, not as accepted surrounding-shape
   templates.
3. Add the smallest exact request-island boundary over source-owned text and
   `ImplementationBody.tokens`.
4. Recognize only balanced outer islands whose keyword is exactly `cast`,
   `mem`, or `io`, followed by `<...>` and then `(...)`.
5. Preserve keyword kind, opaque angle payload text, opaque call argument
   text, source text available from the island boundary, and source locations
   needed for diagnostics.
6. Preserve all non-island text and non-raw body tokens as source-owned opaque
   spans.
7. Handle islands split across contiguous `RawStringToken` runs, as accepted
   by M166. Non-raw tokens remain barriers and are preserved opaque.
8. Avoid context-specific consumers. The same text-fragment helper should be
   usable wherever source-owned text appears, so M167 does not need a separate
   implementation for `emit_return(...)`, `var<...>(...)`, assignments,
   primitive-call arguments, intrinsic arguments, backend-control payloads,
   loops, casts, memory calls, I/O calls, or branch text.
9. Keep payload text opaque. Nested `value<backend>(...)`,
   `value<generation>(...)`, `type<generation>(...)`, `type<backend>(...)`,
   `call<primitive=...>(...)`, `intrin<...>(...)`,
   `intrin_compose<...>(...)`, `cast<...>(...)`, `mem<...>(...)`,
   `io<...>(...)`, raw operators, helper calls, target identifiers, target
   literals, and quoted text inside payloads are not interpreted by M167.
10. Emit deterministic diagnostics for malformed outer islands and no exact
    selected island when the caller explicitly asks for one.
11. Preserve M155-M166 accepted behavior, diagnostics, source locations,
    selected-branch handoff, helper raw preservation, loop discovery,
    declaration requests, backend value queries, backend-control requests,
    intrinsic requests, and generated bytes.
12. Add focused tests for:
    - `cast<...>(...)`, `mem<...>(...)`, and `io<...>(...)`;
    - payload opacity, including backend/generation queries, primitive calls,
      intrinsic calls, nested cast/mem/io text, operators, helper calls, and
      quoted text;
    - multiple selected islands in source order;
    - preservation of opaque prefix/suffix text and non-raw body tokens;
    - contiguous raw-token split islands;
    - use from body-token streams without overfitting to `emit_return`,
      declarations, assignments, branches, loops, or intrinsic arguments;
    - malformed island diagnostics;
    - no-island diagnostics;
    - determinism.
13. Update docs that describe the accepted M167 behavior and any newly
    discovered boundary details.
14. Leave final accepted-state updates to the orchestrator after read-only
    review returns `Accept` or `Accept With Follow-Ups`.

## Design Guardrails

- Treat this as request intake over source-owned text, not as cast/memory/I/O
  translation.
- Do not maintain a list of allowed cast modes, memory operation names, or I/O
  operation names unless the corpus inventory discovers that exact keyword
  spelling itself is malformed.
- Do not split arguments, parse expressions/statements, lower types inside
  payloads, evaluate backend/generation queries, lower nested payloads, choose
  backend spellings, render calls, infer types, match raw statements, execute
  loops, select branches, schedule dependencies, read `tsldata`, `frozen`, or
  `tslgenold` at runtime, or add broad registries, dispatchers, worklists,
  callback maps, hidden backfeeds, or fixpoint machinery.
- Preserve `details::arith_add`, `details::arith_mul`,
  `details::arith_rem`, `details::popcount`, `details::clz`,
  `details::clz_recursive`, `details::ctz`, and `details::mask_test` as raw
  helper calls. They are not M167 keyword islands.

## Must Preserve

- M107-M166 accepted behavior, diagnostics, source locations, and generated
  bytes.
- M155 isolated generation-value query behavior.
- M156-M160 generation-control region and branch-chain behavior.
- M161 whole-body exact loop-region fact behavior.
- M162 embedded loop-region discovery behavior.
- M162.5 shared lexical-helper behavior and migrated keyword/classifier
  boundaries.
- M163 exact top-level generation variable declaration request discovery.
- M164 exact backend value query request discovery and quote-aware payload
  preservation.
- M165 exact classified backend-control directive request discovery.
- M166 exact backend intrinsic request-island discovery, including contiguous
  raw-token split islands.
- Accepted primitive-call resolver/collector behavior and helper raw
  preservation.

## Out Of Scope

Cast translation/results; memory/I/O translation/results; validation of cast
modes or operation names; type lowering inside payloads; argument splitting;
pointer arithmetic; expression or statement parsing; generation/backend query
evaluation; intrinsic, primitive-call, backend-control, declaration, loop, or
return rendering; source repair; dependency scheduling; output writing;
runtime `tsldata`, `frozen`, or `tslgenold` dependencies; broad registries,
dispatchers, worklists, callback maps, hidden backfeeds, or fixpoint
mechanisms.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M167 adds only exact unresolved cast/memory/I/O
   request facts over source-owned text/tokens and avoids translation,
   operation-name validation, argument splitting, type lowering, expression
   parsing, context-specific consumers, registries, dispatchers, worklists,
   source repair, and runtime data reads.
2. Boundary auditor: verify M155-M166 behavior remains intact, payloads remain
   opaque, helper calls stay raw, and existing generation-control, loop,
   declaration, backend value query, backend-control, intrinsic, type-query,
   and primitive-call behavior is not widened accidentally.
3. Evidence auditor: verify the accepted cast/memory/I/O keyword surface is
   grounded in current `tsldata/**/*.tsl` evidence without treating corpus
   neighbor patterns as accepted shapes.
4. Test auditor: verify tests cover all selected keyword families, payload
   opacity, multiple islands, opaque preservation, raw-token split islands,
   non-overfit body-token usage, diagnostics, and determinism.
5. Documentation auditor: verify roadmap, behavioral/domain docs, missing
   inventory, TSIL surface inventory, and current state are coherent.
6. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m1625_tsil_lexical.py tslgen/tests/test_m163_generation_variables.py tslgen/tests/test_m164_backend_value_queries.py tslgen/tests/test_m165_backend_control.py tslgen/tests/test_m166_backend_intrinsics.py
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m1625_tsil_lexical.py tslgen/tests/test_m163_generation_variables.py tslgen/tests/test_m164_backend_value_queries.py tslgen/tests/test_m165_backend_control.py tslgen/tests/test_m166_backend_intrinsics.py
find tslgen -type d -name __pycache__ -print
```

If the executor adds focused M167 test files, include them in the compileall
and targeted pytest commands. Remove validation-created `__pycache__`
directories before the final cache check if any are created.

## Completion Rules

If M167 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M167 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside
this prompt after M167 is accepted. Do not start M168 until the next prompt
explicitly selects it.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 168 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Executor summary.
3. Review/audit verdicts and any follow-ups.
4. Validation commands and exact results.
5. Next active prompt path.
