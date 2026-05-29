# M162 Execution Review Loop Prompt

This is the active follow-on prompt after M161. Execute it only when
`docs/agent/current-redesign-state.md` points here and records M161 as
accepted.

You are executing and reviewing the accepted next milestone after M161:

```text
Milestone 162: Generation Loop Region Discovery In Body Token Streams
```

Milestones 1 through 161 are accepted. M161 added an exact generation-loop
region fact for bodies shaped wholly as `loop<range>(...) { ... }`, with
optional immediately preceding `loop<unroll>(...)` metadata. Current corpus
bodies usually place such loops inside a larger body sequence, commonly after
`var<...>(...)` directives and before `emit_return(...)`.

M162 is an implementation milestone. It should make the M161 loop boundary
usable inside source-owned body token streams without executing loops,
substituting loop variables, parsing assignments, or rendering backend code.

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
- `tslgen/src/tslgen/lowering/generation_loops.py`
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`

## Goal

Recognize exact M161 loop regions embedded in a larger selected body token
stream:

```text
PREFIX_TOKENS
loop<unroll>(COUNT)
loop<range>(INDEX, START, END, STEP) {
  BODY_TOKENS
}
SUFFIX_TOKENS
```

The result should record source-owned prefix tokens, the lowered M161 loop
region, and source-owned suffix tokens, or the equivalent minimal typed
placement/slice contract needed to preserve token identity and diagnostics.

M162 must not execute the loop, unroll the body, substitute `INDEX` into raw
text, parse declarations, parse assignments or array access, lower
`emit_return(result)`, render target-language loops, or repair source text.

## Required Executor Task

Run exactly one write-capable executor for M162. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Inspect current corpus examples where `loop<range>` appears inside larger
   TSIL bodies, especially generic/vector fallback bodies with surrounding
   `var<...>` and `emit_return(...)` directives.
3. Add the smallest exact embedded-loop discovery boundary over
   `ImplementationBody.tokens` that can identify a top-level M161 loop region
   and preserve source-owned prefix/suffix token slices.
4. Reuse the accepted M161 loop-region lowering for the loop slice rather than
   adding a second loop parser or evaluator.
5. If multiple top-level exact M161 loop regions are present in one body, use a
   deterministic policy selected by the executor and covered by tests:
   either support all top-level exact regions in source order or emit a
   deterministic unsupported-multiple-regions diagnostic. Do not silently pick
   one by accident.
6. Preserve all non-loop tokens as opaque source-owned tokens. Raw helper
   calls, primitive-call islands, declarations, `emit_return(...)`, nested
   loops, generation-control branches, assignments, array indexing, casts, and
   intrinsics outside the discovered loop are not interpreted by M162.
7. Emit deterministic diagnostics for malformed embedded loop regions,
   unsupported loop bounds/selectors propagated from M161, ambiguous braces,
   nested or overlapping top-level region ambiguity, and no exact loop region
   when the caller explicitly asks for one.
8. Preserve M155-M161 accepted behavior, diagnostics, source locations,
   selected-branch handoff, helper raw preservation, and M161 whole-body loop
   lowering behavior.
9. Add focused tests for:
   - embedded `loop<range>` with prefix and suffix tokens;
   - embedded adjacent `loop<unroll>` plus `loop<range>`;
   - corpus-like `var<...>` prefix and `emit_return(result)` suffix remaining
     opaque;
   - propagated M161 bound/selector diagnostics;
   - no-region diagnostics;
   - deterministic handling of multiple top-level exact loop regions;
   - nested raw braces or nested loop body tokens remaining inside the
     selected loop body rather than being parsed;
   - determinism.
10. Update docs that describe the accepted M162 behavior and any newly
    discovered boundary details.
11. Leave final accepted-state updates to the orchestrator after read-only
    review returns `Accept` or `Accept With Follow-Ups`.

## Design Guardrails

- Treat this as token-region discovery over source-owned `BodyToken` values,
  not as a TSIL statement parser.
- Reuse the M161 exact loop-region lowerer for the region slice.
- Do not execute loops, perform unrolling, substitute loop variables, evaluate
  declarations, lower `emit_return(result)`, parse target-language statements,
  render backend code, schedule dependencies, read `tsldata`, `frozen`, or
  `tslgenold` at runtime, or add broad registries, dispatchers, worklists,
  callback maps, hidden backfeeds, or fixpoint machinery.

## Must Preserve

- M107-M161 accepted behavior, diagnostics, source locations, and generated
  bytes.
- M155 isolated generation-value query behavior.
- M156-M160 generation-control region and branch-chain behavior.
- M161 whole-body exact loop-region fact behavior.
- Accepted primitive-call resolver/collector behavior and helper raw
  preservation.

## Out Of Scope

Loop execution or unrolling; loop-variable substitution; declaration
semantics; non-type `let<...>` lowering; `var<...>` lowering; assignment,
array-access, cast, memory, I/O, intrinsic, primitive-call, backend-control,
or backend rendering; target-language `for` rendering; source repair;
dependency scheduling; output writing; runtime `tsldata`, `frozen`, or
`tslgenold` dependencies; broad registries, dispatchers, worklists, callback
maps, hidden backfeeds, or fixpoint mechanisms.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M162 adds only exact embedded-loop discovery
   over source-owned body tokens and avoids loop execution, body parsing,
   rendering, registries, dispatchers, worklists, source repair, and runtime
   data reads.
2. Boundary auditor: verify M155-M161 behavior remains intact and M161 loop
   lowering is reused rather than duplicated.
3. Evidence auditor: verify the embedded-loop direction is grounded in current
   `tsldata/**/*.tsl` body evidence and that surrounding declarations/returns
   remain opaque.
4. Test auditor: verify the tests cover prefix/suffix preservation, unroll
   metadata, propagated diagnostics, no-region behavior, multiple-region
   policy, nested/raw body opacity, and determinism.
5. Documentation auditor: verify roadmap, behavioral/domain docs, missing
   inventory, TSIL surface inventory, and current state are coherent.
6. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
find tslgen -type d -name __pycache__ -print
```

If the executor adds focused M162 test files, include them in the compileall
and targeted pytest commands. Remove validation-created `__pycache__`
directories before the final cache check if any are created.

## Completion Rules

If M162 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M162 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside
this prompt after M162 is accepted. Do not start M163 until the next prompt
explicitly selects it.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 163 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Executor summary.
3. Review/audit verdicts and any follow-ups.
4. Validation commands and exact results.
5. Next active prompt path.
