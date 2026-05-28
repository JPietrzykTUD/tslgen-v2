# M155 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M154:

```text
Milestone 155: Selected-Context Generation Value Query Lowering Boundary
```

Milestones 1 through 154 are accepted. M154 created
`docs/redesign/generation-value-query-inventory.md`, which records 597 current
`value<generation>(...)` query islands across 24 `tsldata/**/*.tsl` files. It
selected the largest safe executable subset for the next lowering slice:
isolated selected-context generation value queries for current vector
metadata, selected base scalar type facts, and concrete primitive attributes.

M155 is an implementation milestone. It should implement only the selected
isolated query-island lowering boundary. Do not implement branch pruning, loop
execution, broad expression parsing, backend rendering, raw text replacement,
or surrounding TSIL consumers.

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
- `tslgen/src/tslgen/lowering/type_syntax.py`
- `tslgen/src/tslgen/lowering/type_queries.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/domain/catalog.py`
- `tslgen/src/tslgen/pipeline/extension_catalog.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`

## Goal

Add a focused selected-context generation value query lowering boundary for
these isolated query forms:

- `value<generation>(vector::length)`
- `value<generation>(vector::alignment)`
- `value<generation>(type::size_bytes(TYPE_EXPR))`
- `value<generation>(type::is_signed(TYPE_EXPR))`
- `value<generation>(type::is_same(TYPE_EXPR, TYPE_EXPR))`
- `value<generation>(primitive::attribute(KEY))`

The implementation should consume only explicit accepted facts: selected
implementation context, `CurrentVector` extension/type facts, selected scalar
`TypeTag`, extension metadata, and concrete selected primitive attributes.
For the type-query value families, M155 must recognize the outer
`type::size_bytes(...)`, `type::is_signed(...)`, and `type::is_same(...)`
families, lower each `TYPE_EXPR` argument through the already accepted type
lowering path first, and evaluate only supported lowered scalar type values.
It must not depend on exact raw nested strings such as
`type::size_bytes(type<generation>(base::in))`. Lowered vector/mask/generic
type values, including the observed `vector::imask` cases, remain precise
unsupported diagnostics unless M155 explicitly and narrowly supports a scalar
lowered value.

## Required Executor Task

Run exactly one write-capable executor for M155. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Add a small typed generation-value result boundary for isolated
   `value<generation>(...)` queries.
3. Reuse the existing TSIL/type syntax parsing utilities where practical; do
   not introduce a second parser for the same query syntax and do not
   raw-string match exact nested type-query text.
4. Resolve the selected forms only from explicit typed context and catalog
   facts.
5. Emit deterministic diagnostics for malformed queries, unsupported query
   families, unsupported lowered type values, missing vector metadata, missing
   scalar facts, and unknown or non-concrete primitive attributes.
6. Add focused tests that cover positive cases, malformed forms, unsupported
   families from the M154 inventory, missing context/facts, deterministic
   diagnostics, and no surrounding-context evaluation.
7. Update docs that describe the accepted M155 behavior and any newly
   discovered boundary details.
8. Leave final accepted-state updates to the orchestrator after read-only
   review returns `Accept` or `Accept With Follow-Ups`.

## Design Guardrails

- Keep ownership small and obvious. A focused module or focused additions to
  existing lowering modules are both acceptable if cohesion is clear.
- Prefer simple typed value records and pure evaluator functions over a new
  registry, dispatcher, worklist, or broad request/result family.
- Do not parse or evaluate surrounding raw syntax. The query may appear inside
  loops, branches, declarations, calls, casts, array indexes, arithmetic, or
  attributes in corpus evidence, but M155 lowers only the isolated query
  island selected by a caller/test.
- Do not hardwire target-language operator spellings or backend rendering.
- Do not read `tsldata`, `frozen`, or `tslgenold` at runtime from lowering.
- Preserve M153 helper raw preservation; `details::*` helpers are unrelated to
  generation-value lowering.

## Must Preserve

- M107-M154 accepted behavior, diagnostics, source locations, and generated
  bytes.
- The source-owned body-token model.
- Accepted type-query behavior for `type<generation>(...)` and
  `type<backend>(...)`.
- Accepted extension/register/mask catalog facts without adding host CPU
  detection or backend rendering.
- Accepted primitive attribute wildcard expansion and concrete target matching.

## Out Of Scope

Branch pruning; `if<generation>` / `else<generation>` region matching;
`if<compile>` or backend-control lowering; loop expansion; declaration
lowering; arithmetic such as `* 8` or comparisons such as `== 2`; selector
`attrs[...]` substitution; mask lane constants; vector mask type
size/signedness values; `generic::length(...)` and
`generic::runtime_length(...)`; casts, memory, I/O, intrinsics,
primitive-call rendering, backend type/value rendering, raw source rewriting,
source repair, runtime `tsldata`, `frozen`, or `tslgenold` dependencies;
broad registries, dispatchers, worklists, fixpoint mechanisms, or source-data
repair.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M155 adds only the selected value-query
   boundary and avoids parser/evaluator overgrowth, registries, dispatchers,
   worklists, backend rendering, and runtime data reads.
2. Boundary auditor: verify unsupported surrounding syntax remains out of
   scope and M153 helper raw preservation plus M107-M154 behavior remain
   untouched.
3. Evidence auditor: verify implemented positive/unsupported query families
   match the M154 inventory and exclusions.
4. Test auditor: verify tests cover selected positive cases, unsupported
   families, malformed forms, missing facts, deterministic diagnostics, and no
   surrounding-context evaluation.
5. Documentation auditor: verify roadmap, behavioral/domain docs, missing
   inventory, and current state are coherent.
6. Validation auditor: verify required validation ran and report exact
   command results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
find tslgen -type d -name __pycache__ -print
```

If the executor adds focused M155 test files, include them in the compileall
and targeted pytest commands. Remove validation-created `__pycache__`
directories before the final cache check if any are created.

## Completion Rules

If M155 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M155 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside
this prompt after M155 is accepted. Do not start M156 until the next prompt
explicitly selects it.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 156 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Executor summary.
3. Review/audit verdicts and any follow-ups.
4. Validation commands and exact results.
5. Next active prompt path.
