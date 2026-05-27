# M143 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M142:

```text
Milestone 143: Primitive Call Selector Variant Resolution Slice
```

Milestones 1 through 142 are accepted. M142 added exact selected-context
type/query lowering: `Vec`, `scalar`, ordered source-defined
`let<type>(AliasName, TypeExpr)` aliases, exact
`vector::as_extension(scalar)`, and exact `type<backend>(...)` typed backend
type-spelling requests. M142 did not resolve primitive-call selector targets.

M143 is a primitive-call selector target resolution milestone. It should
resolve recognized `call<primitive=...>(...)` selector targets to typed
primitive-call target references or precise diagnostics. It must not lower
dependency bodies or render backend call text.

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
- `tslgen/src/tslgen/analysis/selection.py`
- `tslgen/src/tslgen/domain/catalog.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/type_queries.py`
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/src/tslgen/lowering/primitive_call_diagnostics.py`
- `tslgen/src/tslgen/pipeline/generator.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`

## Goal

Resolve recognized M135/M136 primitive-call selectors against selected
catalog facts:

- `call<primitive=@self>(...)` resolves to the current selected concrete
  primitive variant;
- `call<primitive=@self[...]>(...)` resolves to the current selected concrete
  primitive variant only when the specialization payload lowers through the
  M142 type/query boundary and matches the selected implementation context;
- `call<primitive=NAME>(...)` resolves to a named primitive present in the
  catalog with a matching implementation for the current selected backend,
  extension, and type tag;
- `call<primitive=NAME[...]>(...)` resolves to a named primitive present in the
  catalog only when the specialization payload lowers through the M142
  type/query boundary and identifies an available matching implementation;
- selector `attrs[...]` payloads match only concrete M140
  `Primitive.attributes` from the catalog, not declared/provenance-only
  attribute fields;
- unknown names, missing concrete attribute variants, unsupported or malformed
  specializations, and missing matching implementations produce precise
  diagnostics.

This milestone should produce typed primitive-call target references or
diagnostics. It should not execute or render the referenced call.

## Required Executor Task

Run exactly one write-capable executor for M143. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Keep M126-M142 parser/catalog/body-token/selection/lowering behavior stable
   unless a focused test exposes a defect.
3. Add the smallest typed primitive-call target reference needed to represent
   selector resolution. Prefer obvious dataclasses and helper functions over
   registries, dispatchers, dependency worklists, or fixpoint machinery.
4. Build selector resolution from already recognized `PrimitiveCall` selector
   objects, the selected `Catalog`, `SelectedImplementationLoweringContext`,
   and M142 type/query facts. Do not reread `.tsl` files, `tsldata`,
   `frozen`, or `tslgenold` from lowering.
5. Preserve original selector, specialization, attrs, payload, and source
   locations as diagnostic/provenance context only.
6. Resolve exact selector target forms:
   - `@self`;
   - `@self[...]`;
   - named primitive references;
   - named primitive references with specialization;
   - named primitive references with `attrs[...]`;
   - named primitive references with both specialization and `attrs[...]`.
7. For specialization payloads, consume only M142 exact type/query lowering
   results. Do not add a broader specialization grammar.
8. For selector attrs, parse only the exact concrete attribute forms selected
   by tests and match against concrete `Primitive.attributes`; do not use
   `Primitive.declared_attributes` or `PrimitiveAttribute.declared_value` as
   semantic matching inputs.
9. Keep call arguments opaque except for already accepted exact add-call
   behavior. Do not recursively lower arguments.
10. Add focused tests for:
    - `@self`;
    - `@self[Vec]`;
    - `@self[type<backend>(vector::as_extension(scalar))]`;
    - named primitive reference;
    - named primitive reference with `[Vec]`;
    - named primitive reference with selector `attrs[...]`;
    - named primitive reference with both specialization and `attrs[...]`;
    - unknown primitive name diagnostics;
    - missing concrete attribute variant diagnostics;
    - unsupported or malformed specialization diagnostics;
    - missing matching implementation/specialization diagnostics;
    - no dependency body lowering or backend call rendering.
11. Update redesign docs if the selector-resolution boundary or diagnostics
    are clarified.

## Out Of Scope

Dependency closure; selecting or lowering dependency implementation bodies;
recursive argument lowering; backend call rendering; backend type text
rendering; wrapper rendering; complete specialization grammar; broad
expression parsing; assignment/indexing; source repair; complete TSIL grammar;
runtime `tsldata` lookup; making `frozen` or `tslgenold` a runtime
dependency; broad template/signature validation; extension/type-group
expansion; hardware/feature requirements; registries; dispatchers; hidden
backfeeds; fixpoint mechanisms; or broad request/result/worklist families.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M143 is primitive-call selector target
   resolution only, not dependency closure, dependency body lowering, backend
   call rendering, recursive argument lowering, broad expression parsing, or
   broad machinery.
2. Boundary auditor: verify selector resolution consumes M135/M136 structured
   call selectors, M140 concrete attributes, M141 selected context, and M142
   typed specialization/type-query facts; verify no hardcoded primitive names
   beyond already accepted exact add-call behavior; verify no runtime
   `tsldata`, `frozen`, or `tslgenold` dependency is introduced.
3. Documentation auditor: verify requirements/domain/roadmap/state docs
   accurately describe M143 and preserve the next post-M143 direction without
   implying dependency closure or backend rendering happened.
4. Validation auditor: verify required validation ran and report exact command
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

Do not run the old `tslgenold` validation profile as proof of the clean
product slice. Remove validation-created `__pycache__` directories before the
final cache check if any are created.

## Completion Rules

If M143 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M143 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside this
prompt after M143 is accepted. Select exactly one concrete follow-up task from
the roadmap and current evidence. Do not start dependency closure or backend
call rendering unless M143 acceptance explicitly selects that next slice.

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
