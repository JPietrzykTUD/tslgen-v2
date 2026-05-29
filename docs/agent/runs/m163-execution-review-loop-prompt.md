# M163 Execution Review Loop Prompt

This is the active follow-on prompt after M162. Execute it only when
`docs/agent/current-redesign-state.md` points here and records M162 as
accepted.

You are executing and reviewing the accepted next milestone after M162:

```text
Milestone 163: Exact Generation Variable Declaration Fact Boundary
```

Milestones 1 through 162 are accepted. M161 added exact loop-region facts for
whole-body loop regions. M162 discovers every exact top-level M161 loop region
inside arbitrary source-owned body token streams while preserving non-loop
tokens as opaque spans.

M163 is an implementation milestone. It should add the next generation-keyword
lowering fact for exact top-level `var<...>(...)` declaration directives in
arbitrary source-owned body token streams. It must not render declarations,
infer types, evaluate initializer expressions, or special-case surrounding
body-token patterns.

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
- `tslgen/src/tslgen/lowering/generation_loops.py`
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`

## Goal

Recognize every exact top-level generation variable declaration directive in
an arbitrary selected body token stream:

```text
OPAQUE_TOKENS
var<init_register>(NAME)
var<infer>(NAME, VALUE)
var<const_infer>(NAME, VALUE)
var<typed>(TYPE_TEXT, NAME, VALUE)
OPAQUE_TOKENS
```

The result should record source-owned non-var token spans and lowered
declaration facts in source order, or the equivalent minimal typed
placement/slice contract needed to preserve token identity and diagnostics.
Initializer and explicit type payloads remain opaque source-owned text. The
accepted shape is the declaration directive itself, not any surrounding
corpus sequence such as `var -> loop -> emit_return`.

## Required Executor Task

Run exactly one write-capable executor for M163. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Inventory current `var<...>` selector and payload forms across all
   `tsldata/**/*.tsl` files. Use corpus examples as evidence, not as accepted
   surrounding-shape templates.
3. Add the smallest exact variable-declaration fact boundary over
   `ImplementationBody.tokens` that can identify every top-level
   `var<...>(...)` directive and preserve source-owned non-var token slices.
4. Accept exact selector/payload shapes for the current corpus family:
   - `var<init_register>(NAME)`
   - `var<infer>(NAME, VALUE)`
   - `var<const_infer>(NAME, VALUE)`
   - `var<typed>(TYPE_TEXT, NAME, VALUE)`
5. Split declaration payloads only on top-level commas, respecting nested
   parentheses, square brackets, and angle brackets. Do not parse
   initializer/type expressions beyond that delimiter boundary.
6. Preserve initializer text and explicit type text as source-owned opaque
   values. Nested `call<primitive=...>`, `type<generation>(...)`,
   `value<backend>(...)`, casts, intrinsics, array indexing, and operators
   inside payloads are not interpreted by M163.
7. Use conservative top-level discovery consistent with M162: a `var`
   directive inside unrelated opaque raw-brace scope is not a top-level
   declaration fact.
8. Preserve all non-var tokens as opaque source-owned tokens. Loops,
   generation branches, returns, raw helper calls, assignments, array indexing,
   casts, intrinsics, primitive calls, backend-control directives, and
   declarations outside the accepted var shape are not interpreted by M163.
9. Emit deterministic diagnostics for unsupported selectors, malformed arity,
   invalid variable names, malformed top-level comma structure, and no exact
   declaration when the caller explicitly asks for one.
10. Preserve M155-M162 accepted behavior, diagnostics, source locations,
    selected-branch handoff, helper raw preservation, M161 whole-body loop
    lowering, and M162 loop discovery behavior.
11. Add focused tests for:
    - each accepted selector shape;
    - nested delimiter payload splitting without initializer/type parsing;
    - arbitrary opaque tokens before, between, and after declarations;
    - multiple declarations in source order;
    - `var` inside unrelated opaque raw-brace scope not being discovered;
    - unsupported selector diagnostics;
    - malformed arity, malformed comma structure, invalid name, and no-var
      diagnostics;
    - determinism.
12. Update docs that describe the accepted M163 behavior and any newly
    discovered boundary details.
13. Leave final accepted-state updates to the orchestrator after read-only
    review returns `Accept` or `Accept With Follow-Ups`.

## Design Guardrails

- Treat this as token-region discovery and declaration-fact lowering over
  source-owned `BodyToken` values, not as a TSIL statement parser.
- The accepted shape is the `var<...>(...)` directive itself. No behavior may
  depend on the identity, order, or semantics of surrounding non-var tokens.
- Do not render declarations, infer types, evaluate initializer expressions,
  resolve symbols, lower `let<...>`, execute loops, substitute loop variables,
  parse target-language statements, render backend code, schedule
  dependencies, read `tsldata`, `frozen`, or `tslgenold` at runtime, or add
  broad registries, dispatchers, worklists, callback maps, hidden backfeeds,
  or fixpoint machinery.

## Must Preserve

- M107-M162 accepted behavior, diagnostics, source locations, and generated
  bytes.
- M155 isolated generation-value query behavior.
- M156-M160 generation-control region and branch-chain behavior.
- M161 whole-body exact loop-region fact behavior.
- M162 embedded loop-region discovery behavior.
- Accepted primitive-call resolver/collector behavior and helper raw
  preservation.

## Out Of Scope

Declaration rendering; type inference; symbol tables; initializer expression
evaluation; recursive lowering of initializer/type payloads; `let<...>`
lowering; loop execution or unrolling; loop-variable substitution;
assignment, array-access, cast, memory, I/O, intrinsic, primitive-call,
backend-control, or backend rendering; target-language declaration rendering;
source repair; dependency scheduling; output writing; runtime `tsldata`,
`frozen`, or `tslgenold` dependencies; broad registries, dispatchers,
worklists, callback maps, hidden backfeeds, or fixpoint mechanisms.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M163 adds only exact top-level var
   declaration facts over source-owned body tokens and avoids rendering,
   expression parsing, symbol tables, type inference, surrounding-token
   special cases, registries, dispatchers, worklists, source repair, and
   runtime data reads.
2. Boundary auditor: verify M155-M162 behavior remains intact, M162 top-level
   raw-brace guarding is preserved for declaration discovery, and initializer
   payloads remain opaque.
3. Evidence auditor: verify the accepted var selector family is grounded in
   current `tsldata/**/*.tsl` evidence without treating corpus-neighbor
   patterns as accepted shapes.
4. Test auditor: verify the tests cover selector shapes, nested delimiter
   payloads, opacity, multiple declarations, raw-brace non-discovery,
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
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
find tslgen -type d -name __pycache__ -print
```

If the executor adds focused M163 test files, include them in the compileall
and targeted pytest commands. Remove validation-created `__pycache__`
directories before the final cache check if any are created.

## Completion Rules

If M163 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M163 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside
this prompt after M163 is accepted. Do not start M164 until the next prompt
explicitly selects it.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 164 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Executor summary.
3. Review/audit verdicts and any follow-ups.
4. Validation commands and exact results.
5. Next active prompt path.
