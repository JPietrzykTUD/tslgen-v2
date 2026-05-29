# M161 Execution Review Loop Prompt

This is the active follow-on prompt after M160. Execute it only when
`docs/agent/current-redesign-state.md` points here and records M160 as
accepted.

You are executing and reviewing the accepted next milestone after M160:

```text
Milestone 161: Exact Generation Loop Region Lowering Boundary
```

Milestones 1 through 160 are accepted. M155-M159 provide selected-context
generation values, comparisons, and explicit generation arithmetic. M156-M160
provide exact generation branch selection over source-owned body tokens,
including classified inline `else if<generation>` branch chains.

M161 is an implementation milestone. It should add the next generation-control
keyword boundary for exact `loop<range>(...)` regions, with an optional
immediately preceding `loop<unroll>(...)` annotation, without executing loops
or parsing target-language statements.

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
- `tslgen/src/tslgen/pipeline/_tsil_directives.py`
- `tslgen/src/tslgen/lowering/generation_values.py`
- `tslgen/src/tslgen/lowering/generation_control.py`
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`

## Goal

Recognize exact selected generation loop regions shaped as source-owned body
tokens:

```text
loop<range>(INDEX, START, END, STEP) {
  BODY_TOKENS
}
```

Also recognize the exact adjacent annotation:

```text
loop<unroll>(COUNT)
loop<range>(INDEX, START, END, STEP) {
  BODY_TOKENS
}
```

M161 should lower this envelope into a typed generation-loop region fact that
records the loop variable name, accepted bound values, optional unroll count,
body token slice, and source locations. It must not expand iterations,
substitute `INDEX` into raw body text, render target-language loops, or parse
assignments, array access, calls, casts, declarations, or intrinsics inside the
body.

## Required Executor Task

Run exactly one write-capable executor for M161. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Inventory current `loop<unroll>` and `loop<range>` forms across all
   `tsldata/**/*.tsl` files, including single-line and multiline brace
   representations produced by the directive classifier.
3. Add the smallest exact loop-region lowering boundary for a leading
   `loop<range>(INDEX, START, END, STEP) { ... }` token region.
4. Add optional recognition of one immediately preceding
   `loop<unroll>(COUNT)` directive as metadata for that exact range loop.
5. Lower `START`, `END`, `STEP`, and `COUNT` only when each is either a
   base-10 integer literal or an accepted integer generation value through the
   existing M155/M159 generation-value path.
6. Emit deterministic diagnostics for malformed loop payloads, malformed or
   unsupported bound expressions, missing or ambiguous braces, unsupported
   loop selectors, unsupported variable-dependent bounds such as an inner
   loop ending at an outer loop variable, and extra tokens around the exact
   region.
7. Preserve the loop body as source-owned `BodyToken` values. Raw helper text,
   primitive-call islands, generation-control directives, nested loops,
   assignments, and array indexing inside the body are opaque to M161.
8. Reuse existing delimiter/boundary helpers where practical, but do not add a
   generic TSIL statement parser, expression AST, registry, dispatcher,
   worklist, renderer-ready IR, or source-repair pass.
9. Preserve M155-M160 accepted behavior, diagnostics, source locations,
   selected-branch handoff, helper raw preservation, and inline
   generation-branch classification.
10. Add focused tests for:
    - exact multiline `loop<range>` region classification/lowering;
    - exact inline or catalog-classified loop-region representation if present
      in current corpus evidence;
    - optional `loop<unroll>(COUNT)` metadata;
    - integer literal and accepted generation-value bounds;
    - malformed range payload arity and invalid index names;
    - unsupported selector diagnostics;
    - unsupported variable-dependent bounds;
    - missing/ambiguous brace diagnostics;
    - body-token opacity, including raw helper/call tokens remaining in the
      loop body;
    - determinism.
11. Update docs that describe the accepted M161 behavior and any newly
    discovered boundary details.
12. Leave final accepted-state updates to the orchestrator after read-only
    review returns `Accept` or `Accept With Follow-Ups`.

## Design Guardrails

- Treat generation loops as TSIL directive envelopes over source-owned tokens,
  not as C++/Rust `for` loops.
- This milestone creates a typed lowering fact for exact loop regions. It does
  not execute the loop or interpret the body.
- Integer literals are accepted only in this loop-bound context and must not
  become standalone top-level `value<generation>(8)` queries.
- Do not support nested loop execution, loop-variable substitution, assignment
  parsing, array-index parsing, declaration lowering, backend-control
  lowering, backend rendering, dependency scheduling, runtime reads from
  `tsldata`, `frozen`, or `tslgenold`, or broad registries, dispatchers,
  worklists, callback maps, hidden backfeeds, or fixpoint machinery.

## Must Preserve

- M107-M160 accepted behavior, diagnostics, source locations, and generated
  bytes.
- M155 isolated generation-value query behavior.
- M156-M160 generation-control region and branch-chain behavior.
- M157 selected-branch handoff behavior.
- M158 comparison predicate behavior.
- M159 explicit generation arithmetic behavior.
- Accepted primitive-call resolver/collector behavior and helper raw
  preservation.

## Out Of Scope

Loop execution or unrolling; loop-variable substitution; nested loop
semantics; variable declarations; non-type `let<...>` lowering; assignment,
array-access, cast, memory, I/O, intrinsic, or primitive-call rendering;
backend-control `if<compile>`, `else<compile>`, or `switch<compile>` lowering;
target-language `for` rendering; source repair; dependency scheduling; output
writing; runtime `tsldata`, `frozen`, or `tslgenold` dependencies; broad
registries, dispatchers, worklists, callback maps, hidden backfeeds, or
fixpoint mechanisms.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M161 adds only exact generation-loop region
   lowering facts over source-owned body tokens and avoids loop execution,
   body parsing, rendering, registries, dispatchers, worklists, source repair,
   and runtime data reads.
2. Boundary auditor: verify M155-M160 behavior remains intact, integer
   literals do not leak into general generation-value queries, and loop body
   tokens remain opaque.
3. Evidence auditor: verify the selected loop-region direction is grounded in
   current `tsldata/**/*.tsl` loop evidence and that unsupported forms are
   diagnostic boundaries.
4. Test auditor: verify the tests cover accepted loop forms, unroll metadata,
   bound lowering, malformed/unsupported diagnostics, body opacity, and
   determinism.
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

If the executor adds focused M161 test files, include them in the compileall
and targeted pytest commands. Remove validation-created `__pycache__`
directories before the final cache check if any are created.

## Completion Rules

If M161 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M161 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside
this prompt after M161 is accepted. Do not start M162 until the next prompt
explicitly selects it.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 162 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Executor summary.
3. Review/audit verdicts and any follow-ups.
4. Validation commands and exact results.
5. Next active prompt path.
