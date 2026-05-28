# M159 Execution Review Loop Prompt

This is the active follow-on prompt after M158. Execute it only when
`docs/agent/current-redesign-state.md` points here and records M158 as
accepted.

You are executing and reviewing the accepted next milestone after M158:

```text
Milestone 159: Generation Arithmetic Value Function Boundary
```

Milestones 1 through 158 are accepted. M155 added isolated selected-context
`value<generation>(...)` query lowering. M156 and M157 made selected
generation-control branches consume lowered boolean conditions. M158 added
exact integer comparison predicates over lowered integer generation values.

M159 is an implementation milestone. It should add explicit function-shaped
generation-time integer arithmetic inside `value<generation>(...)`, without
parsing raw target-language arithmetic operators.

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
- `docs/redesign/generation-value-query-inventory.md`
- `tslgen/src/tslgen/lowering/generation_values.py`
- `tslgen/src/tslgen/lowering/generation_control.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`

## Goal

Allow exact generation-value calls shaped as:

```text
value<generation>(arith<generation>::OP(ARG, ARG))
```

where `OP` is one of `add`, `sub`, `mul`, `div`, or `rem`, and each `ARG` is
recursively lowered as an integer generation value.

This is not a general expression parser. It is a small typed generation-value
function family, deliberately separate from raw `+`, `-`, `*`, `/`, or `%`
source text and from backend helper calls such as `details::arith_mul(...)`.

## Required Executor Task

Run exactly one write-capable executor for M159. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Add the smallest generation-value lowering boundary for
   `arith<generation>::add/sub/mul/div/rem(ARG, ARG)` inside
   `value<generation>(...)`.
3. Lower both arguments recursively through the generation-value lowering
   boundary. Supported integer arguments include integer literals, already
   accepted integer queries such as `vector::length` and
   `type::size_bytes(TYPE_EXPR)`, and nested accepted
   `arith<generation>::...` calls.
4. Require both lowered operands to be integer generation values.
5. Emit deterministic diagnostics for malformed arithmetic calls, unsupported
   operation names, wrong arity, unsupported/non-integer operands, and
   division or remainder by zero.
6. Preserve existing M155 value-query behavior, M156/M157 branch selection,
   and M158 comparison predicate behavior.
7. Add focused tests for:
   - each accepted arithmetic operation;
   - nested arithmetic calls;
   - arithmetic values consumed by an M158 comparison predicate;
   - non-integer operands such as boolean primitive attributes;
   - wrong arity, unsupported operation names, malformed calls, and
     division/remainder by zero;
   - rejection or opacity of raw arithmetic operator text;
   - preservation of backend helper raw text such as `details::arith_mul(...)`.
8. Update docs that describe the accepted M159 behavior and any newly
   discovered boundary details.
9. Leave final accepted-state updates to the orchestrator after read-only
   review returns `Accept` or `Accept With Follow-Ups`.

## Design Guardrails

- Treat `arith<generation>::...` as explicit TSIL generation-time arithmetic.
- Do not parse raw `+`, `-`, `*`, `/`, or `%` expressions.
- Do not rewrite, substitute, or semantically interpret backend helper calls
  such as `details::arith_add`, `details::arith_mul`, or
  `details::arith_rem`.
- Do not add precedence, associativity, algebraic simplification,
  target-language runtime arithmetic semantics, floating arithmetic, boolean
  arithmetic, branch-chain selection, loop/declaration lowering, backend
  rendering, body-token rendering, source repair, or runtime reads from
  `tsldata`, `frozen`, or `tslgenold`.

## Must Preserve

- M107-M158 accepted behavior, diagnostics, source locations, and generated
  bytes.
- M155 isolated generation-value query behavior.
- M156 exact branch-region result behavior and branch-body opacity.
- M157 selected-branch handoff behavior and unselected-branch silence.
- M158 comparison predicate behavior.
- Accepted primitive-call resolver/collector behavior and helper raw
  preservation.

## Out Of Scope

Raw arithmetic operator parsing; precedence or associativity; broad expression
parsing; right-hand value queries beyond M158 accepted behavior; boolean or
floating arithmetic; target-language runtime arithmetic policy; branch-chain
`else if<generation>` selection; plain `else`; recursive or nested
generation-control lowering; loop execution; `loop<unroll>` or `loop<range>`
lowering; declaration lowering; non-type `let<...>` lowering; body-token
rendering; raw text replacement; source repair; selector-attribute
substitution; mask lane constants; generic vector lengths/runtime lengths;
backend-control `if<compile>`, `else<compile>`, or `switch<compile>`
lowering; casts, memory, I/O, intrinsics, primitive-call rendering beyond
already accepted exact paths, backend rendering, dependency scheduling,
runtime `tsldata`, `frozen`, or `tslgenold` dependencies; broad registries,
dispatchers, worklists, callback maps, hidden backfeeds, or fixpoint
mechanisms.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M159 adds only the explicit
   `arith<generation>::...` generation-value function family and avoids raw
   operator parsing, general expressions, registries, dispatchers, worklists,
   backend rendering, and runtime data reads.
2. Boundary auditor: verify M155 value queries, M156 exact region behavior,
   M157 selected-branch handoff, M158 comparison predicates, helper raw
   preservation, and unselected-branch opacity remain intact.
3. Evidence auditor: verify this direction is recorded as explicit TSIL
   generation arithmetic for future `.tsl` source data, and that current
   `details::arith_*` backend helpers remain raw support-helper text.
4. Test auditor: verify tests cover all accepted operations, recursive nested
   calls, M158 comparison consumption, malformed forms, non-integer operands,
   zero divisors, raw operator rejection, helper raw preservation, and
   determinism.
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

If the executor adds focused M159 test files, include them in the compileall
and targeted pytest commands. Remove validation-created `__pycache__`
directories before the final cache check if any are created.

## Completion Rules

If M159 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M159 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside
this prompt after M159 is accepted. Do not start M160 until the next prompt
explicitly selects it.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 160 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Executor summary.
3. Review/audit verdicts and any follow-ups.
4. Validation commands and exact results.
5. Next active prompt path.
