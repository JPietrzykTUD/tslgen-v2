# M144 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M143:

```text
Milestone 144: Typed Primitive-Call Selector Payload Lowering Boundary
```

Milestones 1 through 143 are accepted. M143 completed the observed TSIL type
lowering model for the current `tsldata/**/*.tsl` corpus. It lowered observed
`let<type>(...)`, `type<generation>(...)`, and `type<backend>(...)` forms into
typed semantic type values and backend type-spelling requests, while still
deferring primitive-call selector target resolution, dependency closure, and
backend rendering.

M144 should use that type model to lower recognized primitive-call selector
payloads into typed selector payload values. It must still stop before
matching primitive-call targets or selecting/lowering dependency bodies.

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
- `docs/redesign/tsil-type-query-inventory.md`
- `tslgen/src/tslgen/domain/catalog.py`
- `tslgen/src/tslgen/analysis/selection.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/type_queries.py`
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/src/tslgen/lowering/primitive_call_diagnostics.py`
- `tslgen/src/tslgen/pipeline/_tsil_primitive_calls.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`

## Goal

Lower the already recognized M135/M136
`call<primitive=...>(...)` selector payload data into typed selector payload
values:

- preserve the existing structured base target distinction between `@self`
  and named primitive references;
- split optional specialization payloads such as `[Vec]`,
  `[type<backend>(vector::as_extension(scalar))]`,
  `[ChunkVec, avx2, index]`, and
  `[type<backend>(vector::as_extension(scalar)), PreserveSign]` by top-level
  commas while respecting nested parentheses and brackets;
- lower type-valued specialization entries through the M143 selected type
  environment, including source-defined aliases visible before the call;
- preserve explicitly non-type selector entries as typed selector symbols or
  literals with source/provenance, not as semantic matches;
- parse `attrs[...]` payloads into typed concrete selector attributes using
  the same key, optional key-argument, and value semantics as catalog/target
  attributes;
- add diagnostics for malformed specialization or attrs payloads and for
  failed type-valued selector lowering.

The desired result is a typed selector boundary that later selector matching
can consume without reparsing raw selector strings.

## Required Executor Task

Run exactly one write-capable executor for M144. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Keep M126-M143 parser/catalog/body-token/selection/lowering behavior stable
   unless a focused test exposes a defect.
3. Add a small typed selector-payload model in the existing lowering/domain
   ownership area. Prefer obvious dataclasses and helper functions over
   registries, dispatchers, dependency worklists, or fixpoint machinery.
4. Add a lowerer entry point that consumes a selected implementation context,
   a recognized `PrimitiveCall`, and the selected type environment, then
   returns typed selector payload values plus diagnostics.
5. Lower selector specialization entries through M143 type lowering only when
   the entry is an exact supported type expression or type query. Examples:
   - `Vec`;
   - `type<backend>(vector::as_extension(scalar))`;
   - `type<backend>(vector::as_extension(generic))`;
   - aliases such as `ChunkVec` or `OutVec` only when a preceding
     `let<type>(...)` in the same selected body has bound them before the call.
6. Preserve non-type specialization entries as typed selector symbols or
   literals with source/provenance. Examples include observed selector
   dimensions such as `shift`, `PreserveSign`, `sse`, `avx2`, `index`, and
   numeric index-like values. M144 must not assign these entries semantic
   meaning or match them against implementation variants.
7. Parse `attrs[...]` payloads into typed concrete selector attributes using
   the same syntax shape as declaration/target attributes:
   `key=value` or `key(argument)=value`, comma separated. Wildcard source
   values in selector attrs are unsupported unless an explicit corpus-backed
   reason and tests are added.
8. Add malformed or unsupported diagnostics that keep source text as
   provenance only. Diagnostics should distinguish malformed selector
   specialization payloads, malformed selector attrs, unbound type aliases,
   and unsupported type-valued selector entries where practical.
9. Address the M143 extension-operand follow-up by either:
   - introducing a typed extension/specialization/source-symbol operand for
     `vector::as_extension(...)` and selector entries; or
   - explicitly documenting why the current source-symbol string contract is
     still intentional for M144 and what must happen before selector matching
     relies on it.
10. Add focused positive and negative tests, including:
    - `@self[Vec]`;
    - `@self[type<backend>(vector::as_extension(scalar))]`;
    - `@self[type<backend>(vector::as_extension(scalar)), PreserveSign]`;
    - named calls with aliases and symbols such as
      `insert[ChunkVec, avx2, index]`;
    - attrs-only and specialization-plus-attrs calls such as
      `sub attrs[mask=zero]` and `sub[Vec] attrs[mask=zero]`;
    - malformed attrs syntax;
    - malformed specialization bracket syntax;
    - an unbound alias in a type-valued selector position;
    - malformed or wrong-arity M143 type-query/type-transform forms that
      selector lowering depends on.
11. Update redesign docs if selector-payload ownership, diagnostics,
    extension operands, or out-of-scope selector matching are clarified.

## Out Of Scope

Primitive-call target candidate matching; selecting dependency
implementations; dependency closure; dependency-body lowering; recursive call
argument lowering; backend call rendering; backend type text rendering;
semantic interpretation of non-type selector symbols such as `shift`,
`PreserveSign`, `sse`, `avx2`, `index`, or numeric index-like values; broad
TSIL expression parsing; assignment/indexing lowering; source repair; runtime
`tsldata`, `frozen`, or `tslgenold` dependencies; registries, dispatchers,
fixpoint mechanisms, broad request/result/worklist families, or source-data
repair.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M144 adds only a typed selector-payload
   boundary and does not become primitive-call target matching, dependency
   closure, backend rendering, broad expression parsing, or broad machinery.
2. Boundary auditor: verify selector lowering consumes selected context,
   ordered aliases, M143 type values, and concrete selector attrs; verify raw
   selector text remains diagnostic/provenance context only; verify no runtime
   `tsldata`, `frozen`, or `tslgenold` dependency is introduced.
3. Evidence auditor: verify the supported positive cases are grounded in
   observed selector forms from `tsldata/**/*.tsl` or existing clean-restart
   tests, and that unsupported cases are explicit diagnostics.
4. Documentation auditor: verify behavioral/domain/roadmap/state docs
   accurately describe typed selector payload lowering and defer selector
   target matching.
5. Validation auditor: verify required validation ran and report exact
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

Do not run the old `tslgenold` validation profile as proof of the clean
product slice. Remove validation-created `__pycache__` directories before the
final cache check if any are created.

## Completion Rules

If M144 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M144 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside
this prompt after M144 is accepted. Only then reconsider primitive-call target
matching, and only if selector payloads now have typed type values and typed
attrs.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start the next milestone implementation in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Scope confirmation.
3. Review verdict and subagent verdicts.
4. Follow-ups recorded, if any.
5. Next concrete run prompt created.
6. Validation command(s) and exact result.
