# M158 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M157:

```text
Milestone 158: Exact Generation Integer Comparison Condition Boundary
```

Milestones 1 through 157 are accepted. M155 added isolated selected-context
`value<generation>(...)` query lowering. M156 added exact two-arm
generation-control region lowering for boolean conditions. M157 handed the
selected M156 branch tokens into the existing direct body lowerer.

M158 is an implementation milestone. It should add only the next narrow
condition-lowering boundary needed by current generation-control corpus forms:
exact integer comparisons over isolated M155 integer generation value queries.

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
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`

## Goal

Allow exact generation-control conditions shaped as:

```text
value<generation>(QUERY) COMPARISON INTEGER_LITERAL
```

where `COMPARISON` is exactly one of `==`, `!=`, `<`, `<=`, `>`, or `>=`, and
`QUERY` already lowers through M155 to an integer generation value. The result
is a boolean condition that M156/M157 can consume.

This is not a general expression parser. It is a single exact predicate family
over typed M155 generation values.

## Required Executor Task

Run exactly one write-capable executor for M158. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Add the smallest condition-lowering boundary needed so M156
   generation-control regions accept exact integer comparison predicates of
   the form `value<generation>(QUERY) COMPARISON INTEGER_LITERAL`, where
   `COMPARISON` is one of `==`, `!=`, `<`, `<=`, `>`, or `>=`.
3. Lower the left side through M155 first; do not raw-string match nested query
   text such as `type::size_bytes(type<generation>(base::in))`.
4. Require the left lowered value to be an integer generation value and require
   the right side to be a base-10 integer literal.
5. Preserve existing M155 boolean condition behavior for
   `primitive::attribute(KEY)`, `type::is_signed(TYPE_EXPR)`, and
   `type::is_same(TYPE_EXPR, TYPE_EXPR)`.
6. Propagate M155 missing-fact diagnostics unchanged when the left query cannot
   be lowered.
7. Emit deterministic diagnostics for malformed comparison predicates,
   unsupported/non-integer left values, non-integer literals, multiple or
   ambiguous top-level comparison operators, raw arithmetic operator text, and
   unsupported neighboring expression text.
8. Add focused tests for:
   - true and false outcomes for representative
     `value<generation>(type::size_bytes(TYPE_EXPR)) COMPARISON INTEGER_LITERAL`
     conditions across all six accepted comparison operators;
   - M156/M157 branch selection using this comparison condition;
   - non-integer left values, such as boolean primitive attributes;
   - malformed predicates and unsupported raw arithmetic operator text such as
     `+`, `-`, `*`, `/`, and `%`;
   - propagation of M155 missing-fact diagnostics;
   - preservation of existing boolean condition behavior.
9. Update docs that describe the accepted M158 behavior and any newly
   discovered boundary details.
10. Leave final accepted-state updates to the orchestrator after read-only
    review returns `Accept` or `Accept With Follow-Ups`.

## Design Guardrails

- Treat comparison spellings here as exact generation predicate delimiters,
  not as a C/C++/Rust target-language operator model.
- Do not add precedence, associativity, raw arithmetic operators, nested
  expressions, right-hand value queries, boolean equality, or broad expression
  parsing.
- Do not add generation-time arithmetic functions in M158. The planned M159
  direction is function-shaped `arith<generation>::add/sub/mul/div/rem(...)`
  inside `value<generation>(...)`, deliberately separate from raw `+`, `-`,
  `*`, `/`, or `%` parsing and from backend helper calls such as
  `details::arith_mul(...)`.
- Do not add branch-chain `else if<generation>` support in M158. This
  milestone only makes exact integer comparison conditions available to the
  already accepted two-arm branch-region lowering.
- Do not add registries, dispatchers, worklists, fixpoint mechanisms, backend
  rendering, body-token rendering, source repair, or runtime reads from
  `tsldata`, `frozen`, or `tslgenold`.

## Must Preserve

- M107-M157 accepted behavior, diagnostics, source locations, and generated
  bytes.
- M155 isolated generation-value query behavior.
- M156 exact branch-region result behavior and branch-body opacity.
- M157 selected-branch handoff behavior and unselected-branch silence.
- Accepted primitive-call resolver/collector behavior and helper raw
  preservation.

## Out Of Scope

Branch-chain `else if<generation>` selection; plain `else`; recursive or
nested generation-control lowering; loop execution; `loop<unroll>` or
`loop<range>` lowering; declaration lowering; non-type `let<...>` lowering;
body-token rendering; raw text replacement; source repair; general expression
parsing; raw arithmetic operators; generation-time arithmetic functions;
precedence; right-hand value queries; boolean equality; selector-attribute
substitution; mask lane constants; generic vector lengths/runtime lengths;
backend-control
`if<compile>`, `else<compile>`, or `switch<compile>` lowering; casts, memory,
I/O, intrinsics, primitive-call rendering beyond already accepted exact paths,
backend rendering, dependency scheduling, runtime `tsldata`, `frozen`, or
`tslgenold` dependencies; broad registries, dispatchers, worklists, callback
maps, hidden backfeeds, or fixpoint mechanisms.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M158 adds only the exact integer comparison
   condition boundary over M155 integer generation values and avoids general
   expression parsing, raw arithmetic operators, generation-time arithmetic
   functions, registries, dispatchers, worklists, backend rendering, and
   runtime data reads.
2. Boundary auditor: verify existing M155 boolean conditions, M156 exact region
   behavior, M157 selected-branch handoff, helper raw preservation, and
   unselected-branch opacity remain intact.
3. Evidence auditor: verify the selected exact condition family is a compact
   typed predicate boundary motivated by current size-byte equality branch
   evidence, while branch-chain support itself remains out of scope.
4. Test auditor: verify tests cover true/false comparison outcomes across all
   accepted comparison operators, M156/M157 consumption, malformed predicates,
   raw arithmetic operator rejection, non-integer left values, M155 diagnostic
   propagation, determinism, and preservation of boolean conditions.
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

If the executor adds focused M158 test files, include them in the compileall
and targeted pytest commands. Remove validation-created `__pycache__`
directories before the final cache check if any are created.

## Completion Rules

If M158 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M158 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create or update the next concrete run prompt under `docs/agent/runs/`.
  The expected next prompt is M159 for generation arithmetic value functions
  shaped as `arith<generation>::add/sub/mul/div/rem(...)` inside
  `value<generation>(...)`, not raw operator parsing.

To keep planning and execution integrated, do the next-run planning inside
this prompt after M158 is accepted. Do not start M159 until the next prompt
explicitly selects it.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 159 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Executor summary.
3. Review/audit verdicts and any follow-ups.
4. Validation commands and exact results.
5. Next active prompt path.
