# M165 Execution Review Loop Prompt

This is the active follow-on prompt after M164. Execute it only when
`docs/agent/current-redesign-state.md` points here and records M164 as
accepted.

You are executing and reviewing the accepted next milestone after M164:

```text
Milestone 165: Exact Backend-Control Directive Request Boundary
```

Milestones 1 through 164 are accepted. M164 records exact
`value<backend>(...)` islands as unresolved backend-owned value query requests
over source-owned text.

M165 is an implementation milestone. It should add the next backend-owned
lowering boundary for already classified backend-control directive tokens such
as `if<compile>(...)`, `else<compile>`, and `switch<compile>(...)`. These
directives are generation relevant, but M165 must not solve them at generation
time. It records unresolved backend-control directive requests and preserves
surrounding tokens.

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
- `tslgen/src/tslgen/lowering/backend_value_queries.py`
- `tslgen/src/tslgen/lowering/generation_variables.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`
- `tslgen/tests/test_m1625_tsil_lexical.py`
- `tslgen/tests/test_m163_generation_variables.py`
- `tslgen/tests/test_m164_backend_value_queries.py`

## Goal

Recognize exact backend-control directive request tokens in source-owned body
token streams:

```text
if<compile>(CONDITION_TEXT)
else<compile>
switch<compile>(SELECTOR_TEXT)
```

The result should record unresolved backend-control directive requests in
source order and preserve all non-request body tokens as source-owned opaque
spans. `CONDITION_TEXT` and `SELECTOR_TEXT` remain opaque backend-owned text
for later backend translation/rendering.

The accepted shape is the classified directive token itself, not any
surrounding corpus pattern, branch body, brace block, intrinsic call, raw
assignment, or generated target-language statement.

## Required Executor Task

Run exactly one write-capable executor for M165. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Inventory current backend-control forms across all `tsldata/**/*.tsl`
   files, including present `if<compile>`, `else<compile>`, and
   `switch<compile>` evidence plus the current absence or presence of
   `if<runtime>` / `else<runtime>`. Use corpus examples as evidence, not as
   accepted surrounding-shape templates.
3. Add the smallest exact backend-control directive request boundary over
   already classified `ImplementationBody.tokens`.
4. Accept only classified `LowerableDirective` tokens for the selected
   backend-control selector. For M165 the selected selector is `compile`.
5. Record directive name, selector, opaque payload/condition text when present,
   source text available from the token boundary, and source locations needed
   for diagnostics.
6. Preserve all non-backend-control tokens as source-owned opaque spans.
   Generation control, generation loops, declarations, primitive calls,
   backend value queries, type queries, returns, assignments, raw helper calls,
   array indexing, casts, intrinsics, raw braces, and branch bodies are not
   interpreted by M165.
7. Do not match or validate surrounding `{ ... }` blocks for M165 unless the
   already classified token boundary explicitly owns that text. Raw braces and
   body tokens remain opaque for later backend rendering/body integration.
8. Emit deterministic diagnostics for unsupported backend-control selectors
   when explicitly requested, malformed directive arity for the accepted
   selector/name pairs, and no exact backend-control directive when the caller
   explicitly asks for one.
9. Preserve M155-M164 accepted behavior, diagnostics, source locations,
   selected-branch handoff, helper raw preservation, loop discovery behavior,
   declaration request behavior, backend value query behavior, and generated
   bytes.
10. Add focused tests for:
    - `if<compile>(...)`, `else<compile>`, and `switch<compile>(...)`;
    - condition/selector payload opacity, including nested
      `value<backend>(...)`, `type<backend>(...)`, `value<generation>(...)`,
      primitive calls, operators, helper calls, and quoted text;
    - multiple backend-control directives in source order;
    - preservation of opaque prefix/suffix tokens and non-control classified
      directive tokens;
    - `runtime` selector rejection or documented absence behavior according
      to the corpus inventory;
    - malformed directive diagnostics;
    - no-control diagnostics;
    - determinism.
11. Update docs that describe the accepted M165 behavior and any newly
    discovered boundary details.
12. Leave final accepted-state updates to the orchestrator after read-only
    review returns `Accept` or `Accept With Follow-Ups`.

## Design Guardrails

- Treat this as directive-token request intake over source-owned body tokens,
  not as backend-control evaluation.
- The condition/selector payload is backend-owned opaque text in M165.
- Do not solve compile-time conditions, choose backend spellings, render
  `if constexpr` or any other target-language flow construct, select branches,
  parse or match branch bodies, execute switches, or infer control semantics.
- Do not recursively lower payloads, parse expressions/statements, execute
  loops, substitute variables, schedule dependencies, read `tsldata`,
  `frozen`, or `tslgenold` at runtime, or add broad registries, dispatchers,
  worklists, callback maps, hidden backfeeds, or fixpoint machinery.

## Must Preserve

- M107-M164 accepted behavior, diagnostics, source locations, and generated
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
- Accepted primitive-call resolver/collector behavior and helper raw
  preservation.

## Out Of Scope

Backend-control translation/results; backend-specific spelling; rendering;
branch selection; block matching; `if<runtime>` / `else<runtime>` support
unless explicitly selected by this milestone after corpus evidence demands it;
declaration rendering; type inference; symbol tables; initializer expression
evaluation; recursive payload lowering; `let<...>` lowering; loop execution or
unrolling; loop-variable substitution; assignment, array-access, cast, memory,
I/O, intrinsic, primitive-call, backend value/type query, or backend rendering;
source repair; dependency scheduling; output writing; runtime `tsldata`,
`frozen`, or `tslgenold` dependencies; broad registries, dispatchers,
worklists, callback maps, hidden backfeeds, or fixpoint mechanisms.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M165 adds only exact unresolved
   backend-control directive request facts over source-owned tokens and avoids
   backend evaluation, rendering, expression parsing, block parsing, branch
   selection, symbol tables, surrounding-token special cases, registries,
   dispatchers, worklists, source repair, and runtime data reads.
2. Boundary auditor: verify M155-M164 behavior remains intact, payloads remain
   opaque, and existing generation-control, loop, declaration, backend value
   query, type-query, and primitive-call behavior is not widened accidentally.
3. Evidence auditor: verify the accepted backend-control surface is grounded
   in current `tsldata/**/*.tsl` evidence without treating corpus neighbor
   patterns as accepted shapes.
4. Test auditor: verify tests cover directive families, payload opacity,
   multiple directives, opaque-token preservation, runtime selector behavior,
   diagnostics, and determinism.
5. Documentation auditor: verify roadmap, behavioral/domain docs, missing
   inventory, TSIL surface inventory, and current state are coherent.
6. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m1625_tsil_lexical.py tslgen/tests/test_m163_generation_variables.py tslgen/tests/test_m164_backend_value_queries.py
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m1625_tsil_lexical.py tslgen/tests/test_m163_generation_variables.py tslgen/tests/test_m164_backend_value_queries.py
find tslgen -type d -name __pycache__ -print
```

If the executor adds focused M165 test files, include them in the compileall
and targeted pytest commands. Remove validation-created `__pycache__`
directories before the final cache check if any are created.

## Completion Rules

If M165 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M165 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside
this prompt after M165 is accepted. Do not start M166 until the next prompt
explicitly selects it.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 166 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Executor summary.
3. Review/audit verdicts and any follow-ups.
4. Validation commands and exact results.
5. Next active prompt path.
