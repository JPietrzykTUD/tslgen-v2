# M186 Typed Generation Boolean Condition Grammar Execution-Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records the post-M185 lowering completion gate as accepted.

## Selected Milestone

```text
Milestone 186: Typed Generation Boolean Condition Grammar Boundary
```

## Accepted State

Accepted through M185. The post-M185 completion gate found one remaining
lowering-owned corpus gap: some `if<generation>(...)` conditions use bare
generation predicate expressions rather than the accepted
`value<generation>(...)` wrapper.

Current corpus evidence:

- 15 `if<generation>(type::is_same(...))` conditions in
  `tsldata/primitives/**/*.tsl`;
- 3 of those use the exact two-term top-level disjunction form
  `type::is_same(...) || type::is_same(...)`;
- the remaining post-M185 candidates `assume_aligned<...>`,
  `array_type<...>`, `pack<...>`, `details::*`, recursive payload discovery,
  loop execution/substitution, declaration/body rendering, and backend
  translation/rendering are not selected lowering work for M186.

Interactive product review broadened M186 from a one-off `type::is_same(...)`
matcher to a small typed generation boolean condition grammar. This is still
lowering-owned and still bounded: every leaf must lower through accepted
generation expression/value semantics.

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
- `docs/redesign/missing-lowering-inventory.md`
- `docs/redesign/lowering-completeness-audit.md`
- `docs/redesign/tsil-surface-inventory.md`
- `tslgen/src/tslgen/lowering/generation_control.py`
- `tslgen/src/tslgen/lowering/generation_values.py`
- `tslgen/src/tslgen/lowering/type_queries.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`

Use `tsldata/**/*.tsl` as evidence only. Do not read `frozen/` or
`tslgenold/` unless a blocker cannot be resolved from current docs plus
current `tsldata`, and record why that evidence was needed.

## Executor Task

Implement one narrow lowering slice:

1. Extend generation-control condition lowering so `if<generation>(COND)`
   consumes a typed TSIL generation boolean condition grammar:

   ```text
   GenerationCondition = BoolExpr

   BoolExpr =
     Predicate
     !BoolExpr
     BoolExpr && BoolExpr
     BoolExpr || BoolExpr
     (BoolExpr)

   Predicate =
     accepted boolean generation expression
     accepted integer generation expression compared to an integer literal
   ```

2. Accepted boolean leaves must reuse existing typed generation expression /
   value semantics. At minimum this includes:
   - `value<generation>(...)` when the accepted expression lowers to bool;
   - bare `type::is_same(TYPE_EXPR, TYPE_EXPR)`;
   - bare `type::is_signed(TYPE_EXPR)`;
   - bare `primitive::attribute(KEY)`.
3. Accepted integer comparison leaves must preserve the existing comparison
   boundary over accepted integer generation values, including current
   `value<generation>(...) == INT` / `!=` / `<` / `<=` / `>` / `>=` forms.
4. Boolean operators are TSIL generation-condition operators only. Parse `!`,
   `&&`, `||`, and parentheses for boolean grouping over accepted leaves; do
   not parse arbitrary target-language expressions.
5. Preserve existing accepted behavior for:
   - `value<generation>(primitive::attribute(KEY))`;
   - `value<generation>(type::is_signed(TYPE_EXPR))`;
   - `value<generation>(type::is_same(TYPE_EXPR, TYPE_EXPR))`;
   - integer comparisons over accepted generation integer values;
   - M159 explicit `arith<generation>::...` values;
   - M168 `generic::*` values.
6. Add focused tests for positive, false-branch, malformed, unsupported, and
   no-broad-expression behavior.
7. Update redesign docs only where the accepted behavior changes.

## Scope

In scope:

- a small typed TSIL generation boolean condition parser/evaluator for
  `if<generation>(COND)`;
- boolean `!`, `&&`, `||`, and parentheses, with explicit deterministic
  precedence/associativity documented by tests;
- accepted boolean generation expression leaves, including bare
  `type::is_same(...)`, bare `type::is_signed(...)`, bare
  `primitive::attribute(...)`, and wrapped `value<generation>(...)` boolean
  values;
- accepted integer generation comparison leaves using the already accepted
  comparison operators and integer literal right-hand values;
- deterministic diagnostics for malformed or unsupported forms;
- a focused helper module if that is cleaner than growing
  `generation_control.py`, especially because `generation_values.py` is
  already near/over the module-size guardrail.

Out of scope:

- a general C, C++, Rust, or target-language expression parser;
- arbitrary function-call predicates outside accepted generation expression
  families;
- raw comparisons between arbitrary source text such as `left == right`,
  pointer checks, array indexing predicates, or helper-call semantics;
- raw arithmetic/operator parsing beyond already accepted generation-value
  semantics and integer comparison leaves;
- recursive generation-control lowering;
- plain target-language `else`;
- branch/body rendering;
- loop execution or substitution;
- declaration rendering or body-token rendering policy;
- `assume_aligned<...>`, `array_type<...>`, `pack<...>`, or `details::*`
  semantic lowering;
- backend-control, backend-value/type, intrinsic, source-operation, or mask
  translation/rendering;
- raw target-language assignment/indexing/operator parsing;
- source repair;
- runtime `tsldata`, `frozen`, or `tslgenold` dependencies;
- registries, dispatchers, plugin maps, worklists, recursive payload walkers,
  or per-keyword frameworks.

## Required Subagents

Use the executor-review loop:

1. One write-capable executor for the implementation.
2. Read-only architecture reviewer.
3. Read-only boundary/simplicity auditor.
4. Read-only evidence auditor.
5. Read-only test auditor.
6. Read-only documentation auditor.
7. Read-only validation auditor.

If review returns `Needs Revision`, use one focused revision executor limited
to the blocking issues, then run focused re-review. If review returns
`Return To Planner` or `Reject`, stop implementation and create the
appropriate next prompt instead of continuing.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m186_generation_condition_expressions.py
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m186_generation_condition_expressions.py
find tslgen -type d -name __pycache__ -print
```

If `compileall` or pytest creates `__pycache__`, remove validation-created
cache directories before the final `find` check and report both the cleanup
and final `find` result.

## Completion Rules

If M186 is accepted:

- update `docs/agent/current-redesign-state.md`;
- record the accepted behavior in `docs/redesign/implementation-roadmap.md`;
- update behavioral/domain/inventory docs as needed;
- create the next concrete run prompt under `docs/agent/runs/`;
- do not start the next milestone.

## Final Report

Report:

1. Implementation summary.
2. Whether M186 was accepted or needs revision.
3. Review/audit verdicts.
4. Validation commands and exact results.
5. Next active prompt path.
