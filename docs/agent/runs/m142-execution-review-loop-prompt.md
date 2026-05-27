# M142 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M141:

```text
Milestone 142: Exact Type Alias And Backend-Type Query Lowering Slice
```

Milestones 1 through 141 are accepted. M141 added
`SelectedImplementationLoweringContext`, making selected implementation facts
available to lowering without rereading source files or legacy evidence.

M142 is an exact type-alias and type-query lowering milestone. It should use
the M141 context to lower selected-context type names and exact backend-type
query islands. It must not resolve primitive-call selector targets yet.

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
- resolve exact implementation-body aliases `MaskVec` and `GenericVec` to
  typed alias references in the selected context, without rendering backend
  text;
- represent exact `vector::as_extension(scalar)` as a typed vector transform
  request/fact over the current scalar/base type and selected extension
  context;
- represent exact `type<backend>(...)` as a typed backend type-spelling
  request over an already typed semantic type value;
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
3. Add a small typed representation for selected-context type facts and
   backend type-spelling requests. Prefer obvious dataclasses and helper
   functions over request/result/worklist families, registries, dispatchers,
   or fixpoint machinery.
4. Build all type/query lowering from `SelectedImplementationLoweringContext`;
   do not read `.tsl` files, `tsldata`, `frozen`, or `tslgenold` from
   lowering.
5. Handle exact selected-context symbols:
   - `Vec`;
   - `MaskVec`;
   - `GenericVec`.
6. Handle exact selected-context query islands:
   - `vector::as_extension(scalar)`;
   - `type<backend>(Vec)`;
   - `type<backend>(MaskVec)`;
   - `type<backend>(GenericVec)`;
   - `type<backend>(vector::as_extension(scalar))`.
7. Keep backend type spelling as a typed request/fact boundary. Do not render
   C++ or Rust type text from these requests in M142.
8. Preserve original raw query text only as diagnostic context. Renderers must
   not receive unresolved raw `type<backend>(...)` source text as semantic
   input.
9. Add focused tests for:
   - `Vec` lowering from selected extension plus type tag/datatype;
   - `MaskVec` and `GenericVec` alias lowering as unresolved aliases;
   - `vector::as_extension(scalar)` transform lowering;
   - each exact `type<backend>(...)` form listed above;
   - malformed and unsupported query diagnostics;
   - no primitive-call target resolution for `call<primitive=@self[Vec]>(...)`
     or `call<primitive=NAME[Vec] attrs[...]>(...)`;
   - existing M126-M141 generated artifact bytes and diagnostics remain
     stable.
10. Update redesign docs if the type/query lowering boundary or diagnostic
    behavior is clarified.

## Out Of Scope

Primitive-call selector target resolution; dependency closure; lowering
dependency bodies; backend call rendering; rendering backend type text;
interpreting selector `attrs[...]`; resolving argument identifiers; broad
generation/backend query grammar; expression parsing; assignment or
array-access lowering; source repair; complete TSIL grammar; runtime
`tsldata` lookup; making `frozen` or `tslgenold` a runtime dependency; broad
template/signature validation; full attribute validity checking;
extension/type-group expansion; hardware/feature requirements; registries;
dispatchers; hidden backfeeds; fixpoint mechanisms; or broad request/result/
worklist families.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M142 is an exact selected-context type/query
   lowering boundary, not primitive-call selector resolution, dependency
   closure, backend rendering, or broad expression parsing. It must keep the
   type/query model small.
2. Boundary auditor: verify all type/query lowering is driven by the M141
   context, exact accepted source forms, and typed facts/requests; verify raw
   source text remains diagnostic context only; verify no primitive-call target
   matching, dependency closure, backend type-text rendering, runtime
   `tsldata`, `frozen`, or `tslgenold` dependency is introduced.
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
