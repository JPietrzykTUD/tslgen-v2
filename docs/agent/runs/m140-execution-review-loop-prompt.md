# M140 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M139:

```text
Milestone 140: Explicit Target Attribute Variant Selection Boundary Slice
```

Milestones 1 through 139 are accepted. M139 lets the catalog contain multiple
same-name primitive variants distinguished by concrete declaration attributes,
including variants materialized from wildcard declaration attributes. Before
lowering can correctly match `call<primitive=... attrs[...]>(...)` selectors
against catalog variants, explicit target selection must stop treating
primitive name alone as sufficient.

M140 is a selection prerequisite for correct lowering. It must not perform
primitive-call candidate lookup or dependency lowering.

Keep the post-M140 lowering track explicit: M141 should introduce selected
implementation lowering context, M142 should lower exact type alias/backend-type
query islands (`Vec`, `MaskVec`, `GenericVec`, `type<backend>(...)`,
`vector::as_extension(scalar)`) in that context, and M143 should resolve
primitive-call selector variants against the catalog. Do not collapse those
tasks into M140.

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
- `tslgen/src/tslgen/domain/catalog.py`
- `tslgen/src/tslgen/analysis/selection.py`
- `tslgen/src/tslgen/pipeline/catalog_builder.py`
- `tslgen/src/tslgen/pipeline/generator.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`

## Goal

Select primitive variants by explicit concrete target attributes:

- extend the explicit `Target` selection request with concrete primitive
  attributes while preserving existing no-attribute target construction;
- make empty target attributes match only catalog variants whose concrete
  `Primitive.attributes` are empty;
- make nonempty target attributes match catalog variants by primitive name,
  signature where applicable, and concrete `Primitive.attributes`;
- ignore provenance-only fields such as `Primitive.declared_attributes` and
  `PrimitiveAttribute.declared_value` during matching;
- report precise diagnostics when a primitive name exists but no concrete
  attribute variant matches;
- preserve deterministic selection ordering and existing no-attribute
  generation behavior.

This milestone should make the current selected primitive identity attribute
aware, so a later lowering slice can match recognized
`call<primitive=... attrs[...]>(...)` selectors against concrete catalog
variants without relying on name-only shortcuts.

## Required Executor Task

Run exactly one write-capable executor for M140. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Keep M126-M139 parser/catalog/body-token/lowering behavior stable unless a
   focused test exposes a defect.
3. Add a small typed representation for target concrete attributes, or reuse
   the existing catalog attribute value shape if that is simpler and keeps the
   selection API clear.
4. Extend `Target` so existing callers can still construct no-attribute
   targets without edits. No-attribute targets must select only primitives
   whose concrete `Primitive.attributes` are empty.
5. Update `Selector` to select primitive variants by name plus concrete target
   attributes before implementation extension/type selection.
6. Match only `Primitive.attributes`. Do not match against
   `Primitive.declared_attributes`, `PrimitiveAttribute.declared_value`, source
   spans, or other provenance fields.
7. When a primitive name exists but no concrete attribute variant matches,
   emit a precise diagnostic at the best available primitive source location
   and list the requested concrete attributes and available concrete variants.
8. Preserve existing unsupported-backend, unknown-primitive, and
   no-implementation diagnostics outside the deliberately refined variant
   matching path.
9. Preserve existing generated artifact bytes for no-attribute targets.
10. Add focused tests for:
    - existing no-attribute targets still selecting no-attribute variants;
    - empty target attributes not matching attr-bearing variants;
    - explicit literal attribute target selection, such as `mask=zero`;
    - wildcard-expanded concrete variants selected by concrete attributes,
      such as `aligned=true` and `packed=false`;
    - missing concrete attribute variant diagnostics;
    - provenance fields being ignored for matching;
    - deterministic behavior across repeated source/target orderings;
    - existing M126-M139 diagnostics and artifact-byte stability.
11. Update redesign docs if the target attribute model, selection diagnostic
    behavior, or matching boundary is clarified.

## Out Of Scope

Primitive-call candidate lookup; dependency closure; lowering dependency
bodies; rendering backend call text; resolving `call<primitive=...>`
selectors; interpreting selector specialization or selector `attrs[...]`;
resolving argument identifiers; recursively lowering argument expressions;
expression parsing; assignment or array-access lowering; source repair;
complete TSIL grammar; runtime `tsldata` semantic lookup; making `frozen` or
`tslgenold` a runtime dependency; broad template/signature validation; full
attribute validity checking; extension/type-group expansion; hardware/feature
requirements; registries; dispatchers; hidden backfeeds; fixpoint mechanisms;
or new request/result/worklist families.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M140 is an explicit target-selection variant
   boundary, not a lowering/call-matching slice. It must preserve M126-M139
   behavior, keep the target/selection model small, and avoid broad IR
   machinery, request/result/worklist families, registries, dispatchers, or
   fixpoint mechanisms.
2. Boundary auditor: verify selection matches only concrete
   `Primitive.attributes` and ignores provenance fields; verify empty target
   attributes do not match attr-bearing variants; verify no primitive-call
   candidate lookup, dependency closure, backend rendering, runtime `tsldata`
   shortcut, `frozen` runtime dependency, or `tslgenold` runtime dependency is
   introduced.
3. Documentation auditor: verify requirements/domain/roadmap/state docs
   accurately describe the M140 selection boundary and preserve M128-M139
   lowering/catalog boundaries.
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

If M140 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M140 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside this
prompt after M140 is accepted. Select exactly one concrete M141 task that uses
the roadmap outline for selected implementation lowering context. M141 should
preserve the distinction between catalog attributes and implementation type
aliases: `Vec` is the current vector keyword derived from selected extension
plus datatype, while `MaskVec` and `GenericVec` are aliases to be resolved by
lowering. Do not jump directly to primitive-call selector matching in M141. Do
not create a separate post-M140 planning prompt unless review returns
`Return To Planner`, `Reject`, or an explicit stop condition is recorded.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 141 implementation in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Scope confirmation.
3. Review verdict and subagent verdicts.
4. Follow-ups recorded, if any.
5. Next concrete run prompt created.
6. Validation command(s) and exact result.
