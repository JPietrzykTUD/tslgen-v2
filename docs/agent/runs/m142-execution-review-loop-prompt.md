# M142 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M141:

```text
Milestone 142: Exact Type Alias And Backend-Type Query Lowering Slice
```

Milestones 1 through 141 are accepted. M141 added
`SelectedImplementationLoweringContext`, making selected implementation facts
available to lowering without rereading source files or legacy evidence.

M142 is an exact type-alias and type-query lowering milestone. It should use
the M141 context to lower selected-context type names, exact `let<type>(...)`
alias bindings, and exact backend-type query islands. It must not resolve
primitive-call selector targets yet.

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
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/src/tslgen/lowering/primitive_call_diagnostics.py`
- `tslgen/src/tslgen/pipeline/generator.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`

## Goal

Lower exact type-related islands against the M141 selected implementation
context:

- resolve the exact `Vec` symbol to a typed current-vector reference derived
  from selected extension plus selected type tag/datatype;
- seed a tiny selected-body type environment with exact context symbols such
  as `Vec` and the current scalar/base type symbol;
- lower exact `let<type>(AliasName, TypeExpr)` directives in body order and
  bind arbitrary alias names to lowered typed type expressions;
- resolve alias references such as `MaskVec` or `GenericVec` only through a
  preceding `let<type>(...)` binding, never as hardcoded names;
- represent exact `vector::as_extension(scalar)` as a typed vector transform
  request/fact over the current scalar/base type and selected extension
  context;
- represent exact `type<backend>(...)` as a typed backend type-spelling
  request over an already lowered typed semantic type value or prior alias
  binding;
- emit precise diagnostics for unsupported or malformed exact type/query
  islands instead of passing raw query text to renderers;
- preserve existing generated artifact bytes and M126-M141 diagnostics.

This milestone should make exact type/query lowering facts available for the
future M143 primitive-call selector resolution. It should not make
primitive-call selectors resolve targets.

## Required Executor Task

Run exactly one write-capable executor for M142. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Keep M126-M141 parser/catalog/body-token/selection/lowering behavior stable
   unless a focused test exposes a defect.
3. Add a small typed representation for selected-context type facts, ordered
   type-alias bindings, and backend type-spelling requests. Prefer obvious
   dataclasses and helper functions over broad request/result/worklist
   families, registries, dispatchers, or fixpoint machinery.
4. Build all type/query lowering from `SelectedImplementationLoweringContext`;
   do not read `.tsl` files, `tsldata`, `frozen`, or `tslgenold` from
   lowering. If the M141 context's recorded unresolved alias names would imply
   hardcoded `MaskVec` / `GenericVec` semantics, narrow or revise that context
   field inside this milestone so alias resolution is driven by
   `let<type>(...)` bindings instead.
5. Seed the selected-body type environment from exact selected-context symbols:
   - `Vec`;
   - the current scalar/base type symbol needed by
     `vector::as_extension(scalar)`.
6. Handle exact `let<type>(AliasName, TypeExpr)` directives as type-alias
   bindings in source/body order:
   - `AliasName` is an arbitrary source alias identifier, not a fixed list;
   - accepted `TypeExpr` forms are only the exact M142 type expressions;
   - alias references must resolve through an earlier binding in the current
     selected body;
   - `MaskVec` and `GenericVec` may appear in tests only as examples of
     aliases declared by `let<type>(...)`, not as built-ins.
7. Handle exact selected-context query islands:
   - `vector::as_extension(scalar)`;
   - `type<backend>(Vec)`;
   - `type<backend>(AliasName)` only when `AliasName` resolves through a
     preceding `let<type>(...)` binding;
   - `type<backend>(vector::as_extension(scalar))`.
8. Keep backend type spelling as a typed request/fact boundary. Do not render
   C++ or Rust type text from these requests in M142.
9. Preserve original raw query text only as diagnostic context. Renderers must
   not receive unresolved raw `type<backend>(...)` source text as semantic
   input.
10. Add focused tests for:
   - `Vec` lowering from selected extension plus type tag/datatype;
   - `let<type>(MaskVec, ...)` and `let<type>(GenericVec, ...)` lowering as
     source-defined aliases, plus at least one non-special arbitrary alias
     name to prove aliases are not hardcoded;
   - `vector::as_extension(scalar)` transform lowering;
   - each exact `type<backend>(...)` form listed above, including alias use
     after a prior binding;
   - unbound alias, alias use before definition, malformed `let<type>`, and
     unsupported query diagnostics;
   - no primitive-call target resolution for `call<primitive=@self[Vec]>(...)`
     or `call<primitive=NAME[Vec] attrs[...]>(...)`;
   - existing M126-M141 generated artifact bytes and diagnostics remain
     stable.
11. Update redesign docs if the type/query lowering boundary or diagnostic
    behavior is clarified.

## Out Of Scope

Primitive-call selector target resolution; dependency closure; lowering
dependency bodies; backend call rendering; rendering backend type text;
hardcoded `MaskVec` / `GenericVec` semantics; interpreting selector
`attrs[...]`; resolving call argument identifiers; broad generation/backend
query grammar; expression parsing; assignment or array-access lowering;
general block scoping, alias shadowing, or cross-body alias lookup; source
repair; complete TSIL grammar; runtime `tsldata` lookup; making `frozen` or
`tslgenold` a runtime dependency; broad template/signature validation; full
attribute validity checking; extension/type-group expansion; hardware/feature
requirements; registries; dispatchers; hidden backfeeds; fixpoint mechanisms;
or broad request/result/worklist families.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M142 is an exact selected-context type/query
   and type-alias binding boundary, not primitive-call selector resolution,
   dependency closure, backend rendering, or broad expression parsing. It must
   keep the type/query model small.
2. Boundary auditor: verify all type/query lowering is driven by the M141
   context, exact accepted source forms, prior `let<type>(...)` bindings, and
   typed facts/requests; verify raw source text remains diagnostic context
   only; verify `MaskVec` / `GenericVec` are not hardcoded semantic aliases;
   verify no primitive-call target matching, dependency closure, backend
   type-text rendering, runtime `tsldata`, `frozen`, or `tslgenold` dependency
   is introduced.
3. Documentation auditor: verify requirements/domain/roadmap/state docs
   accurately describe the M142 boundary and preserve the M143 primitive-call
   selector direction.
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

If M142 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M142 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside this
prompt after M142 is accepted. Select exactly one concrete M143 task from the
roadmap outline: primitive-call selector variant resolution using the M141
context and M142 typed specialization/type-query facts. Do not start
dependency closure or backend call rendering in M143 unless the accepted
review explicitly narrows that scope.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 143 implementation in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Scope confirmation.
3. Review verdict and subagent verdicts.
4. Follow-ups recorded, if any.
5. Next concrete run prompt created.
6. Validation command(s) and exact result.
