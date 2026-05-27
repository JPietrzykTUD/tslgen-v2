# M141 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M140:

```text
Milestone 141: Selected Implementation Lowering Context Slice
```

Milestones 1 through 140 are accepted. M140 made explicit target selection
attribute-aware by selecting concrete catalog primitive variants from
`Target.attributes` and concrete `Primitive.attributes`.

M141 is a lowering-context milestone. It should create the small typed context
that later exact type-query and primitive-call selector milestones can consume.
It must not lower type aliases or resolve primitive-call selectors yet.

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
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/primitive_call_diagnostics.py`
- `tslgen/src/tslgen/pipeline/generator.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`

## Goal

Create the selected implementation lowering context:

- carry the selected primitive identity, including concrete selected catalog
  attributes from M140;
- carry selected backend, extension, datatype/type tag, signature, template,
  parameter names, and implementation source provenance;
- represent `Vec` as the current implementation vector keyword derived from
  selected extension plus datatype, not as a primitive specialization or
  catalog attribute;
- record that `MaskVec` and `GenericVec` are implementation-body type aliases
  to be resolved by lowering, not primitive declarations;
- make this context available to lowering code in a small typed form that
  future M142 type-query lowering can consume;
- preserve existing generated artifact bytes and M126-M140 diagnostics.

This milestone should make selected-context facts explicit. It should not
pretend to understand implementation-body expressions.

## Required Executor Task

Run exactly one write-capable executor for M141. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Keep M126-M140 parser/catalog/body-token/selection/lowering behavior stable
   unless a focused test exposes a defect.
3. Add one small typed lowering-context value or helper owned by the lowering
   boundary. Prefer an obvious dataclass over request/result/worklist,
   registry, dispatcher, or fixpoint machinery.
4. Build the context from the already selected `SelectedImplementation`; do
   not read `.tsl` files, `tsldata`, `frozen`, or `tslgenold` from lowering.
5. Preserve selected primitive object identity and concrete
   `Primitive.attributes`; do not copy or match against
   `Primitive.declared_attributes` or `PrimitiveAttribute.declared_value` as
   semantic matching inputs.
6. Carry enough selected implementation facts for future exact type-query
   lowering: backend, extension, type tag/datatype, signature, template,
   parameters, primitive source, implementation source, and selected target.
7. Represent current implementation type names as context facts:
   - `Vec` is the current vector keyword for the selected extension and
     datatype/type tag.
   - `MaskVec` and `GenericVec` are known unresolved implementation-body type
     aliases for later lowering.
8. Thread or expose the context through the lowerer in the smallest useful way
   without changing emitted C++/Rust bytes for current successful cases.
9. Add focused tests for:
   - context construction from a no-attribute selected implementation;
   - context construction from an M140 attribute-selected implementation;
   - concrete attributes preserved while provenance-only declaration fields
     remain non-semantic;
   - backend, extension, type tag/datatype, signature, parameters, primitive
     source, and implementation source are carried;
   - `Vec` is recorded as current vector keyword and `MaskVec` / `GenericVec`
     are recorded as unresolved aliases, not catalog specialization keys;
   - existing M126-M140 generated artifact bytes and diagnostics remain
     stable.
10. Update redesign docs if the lowering-context ownership or alias boundary
    is clarified.

## Out Of Scope

Resolving `Vec`, `MaskVec`, `GenericVec`, `type<backend>(...)`, or
`vector::as_extension(scalar)` into backend text; primitive-call candidate
matching; dependency closure; lowering dependency bodies; backend call
rendering; interpreting selector specialization or selector `attrs[...]`;
resolving argument identifiers; expression parsing; assignment or array-access
lowering; source repair; complete TSIL grammar; runtime `tsldata` lookup;
making `frozen` or `tslgenold` a runtime dependency; broad template/signature
validation; full attribute validity checking; extension/type-group expansion;
hardware/feature requirements; registries; dispatchers; hidden backfeeds;
fixpoint mechanisms; or new request/result/worklist families.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M141 is a selected lowering-context boundary,
   not type-query lowering, primitive-call matching, dependency closure, or
   backend rendering. It must keep the context model small and avoid broad IR
   machinery, request/result/worklist families, registries, dispatchers, or
   fixpoint mechanisms.
2. Boundary auditor: verify the context is built only from selected catalog /
   target facts, carries concrete M140 attributes, treats `Vec` as current
   selected-context keyword, treats `MaskVec` / `GenericVec` as unresolved
   aliases, and does not evaluate raw source text or resolve type/backend
   queries.
3. Documentation auditor: verify requirements/domain/roadmap/state docs
   accurately describe the M141 context boundary and preserve M140 and the
   post-M141 M142/M143 direction.
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

If M141 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M141 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside this
prompt after M141 is accepted. Select exactly one concrete M142 task from the
roadmap outline: exact type alias and backend-type query lowering for `Vec`,
`MaskVec`, `GenericVec`, `type<backend>(...)`, and
`vector::as_extension(scalar)` in selected context. Do not jump directly to
primitive-call selector variant resolution in M142.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 142 implementation in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Scope confirmation.
3. Review verdict and subagent verdicts.
4. Follow-ups recorded, if any.
5. Next concrete run prompt created.
6. Validation command(s) and exact result.
