# M143 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M142:

```text
Milestone 143: Complete Observed TSIL Type Lowering Model
```

Milestones 1 through 142 are accepted. M142 added a narrow starter type/query
boundary for `Vec`, `scalar`, ordered source-defined
`let<type>(AliasName, TypeExpr)` aliases, exact
`vector::as_extension(scalar)`, and exact `type<backend>(...)` typed backend
type-spelling requests.

M143 deliberately stops before primitive-call selector target resolution. The
next big prerequisite is the observed TSIL type language itself. This milestone
should complete type lowering for the forms actually present in the current
`tsldata/**/*.tsl` corpus, rather than selecting another tiny synthetic type
slice.

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
- `frozen/tsl-gen/tsl_gen/tsil_engine/expansion_support.py`
- `frozen/tsl-gen/tsl_gen/tsil_engine/passes/types.py`
- `frozen/tsl/detail/lang/translate_cpp.tsl`
- `frozen/tsl/detail/lang/translate_rust.tsl`
- `frozen/tsl/detail/lang/translate_c17.tsl`
- `tslgen/src/tslgen/analysis/selection.py`
- `tslgen/src/tslgen/domain/catalog.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/type_queries.py`
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/src/tslgen/pipeline/generator.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`

## Goal

Realize the observed TSIL type language as typed semantic type values and typed
backend type-spelling requests:

- inventory every unique observed `let<type>(...)`, `type<generation>(...)`,
  and `type<backend>(...)` form across `tsldata/**/*.tsl`;
- classify each observed form by semantic type category;
- lower context-given generation types such as `base::in`,
  `vector::register`, `vector::mask`, `vector::imask`,
  `vector::mask_underlying_t`, and `vector::offset_base`;
- lower type transforms such as `base::signed_of(...)`,
  `base::unsigned_of(...)`, `base::generic(...)`,
  `register::generic(...)`, `vector::transform(...)`,
  `vector::transform_extension(...)`, and `vector::as_extension(...)`;
- lower independent backend/scalar type identities such as `size_t`,
  `intrin::vector::imask`, and the observed `scalar::...` backend type names;
- lower ordered source-defined aliases from
  `let<type>(AliasName, TypeExpr)` through the same semantic type model;
- keep `type<generation>(...)` as semantic type identity lowering;
- keep `type<backend>(...)` as backend type-spelling requests over already
  lowered semantic type values;
- preserve existing generated artifact bytes and M126-M142 diagnostics unless
  a focused type-boundary diagnostic is deliberately added.

This milestone should make type payloads fully resolved as semantic type
identities. It should not render backend type text.

## Required Executor Task

Run exactly one write-capable executor for M143. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Keep M126-M142 parser/catalog/body-token/selection/lowering behavior stable
   unless a focused test exposes a defect.
3. Create or update a documented type-query inventory under `docs/redesign/`
   with:
   - total counts and unique counts for `let<type>(...)`,
     `type<generation>(...)`, and `type<backend>(...)`;
   - every unique observed form grouped by category;
   - representative source locations;
   - forms covered by M143 and any explicitly unsupported/open forms.
4. Use `tsldata/**/*.tsl` as corpus ground truth. Use `frozen/` only as
   historical evidence to understand unclear semantics such as
   `register::generic(...)`; do not make `frozen` a runtime dependency.
5. Extend the M142 type model into a coherent observed-corpus type model.
   Prefer obvious dataclasses and helper functions over registries,
   dispatchers, dependency worklists, or fixpoint machinery.
6. Support observed context-given generation type families:
   - `base::in`;
   - `vector::register`;
   - `vector::mask`;
   - `vector::imask`;
   - `vector::mask_underlying_t` and `vector::mask_underlying`;
   - `vector::offset_base`.
7. Support observed type transform families:
   - `base::signed_of(TypeExpr)`;
   - `base::unsigned_of(TypeExpr)`;
   - `base::generic(TypeExpr)`;
   - `register::generic(TypeExpr)`;
   - `base::id(TypeExpr)` if present in observed nested forms or frozen
     evidence requires it for normalization;
   - `vector::transform(TypeExpr)`;
   - `vector::transform_extension(TypeExpr)`;
   - `vector::as_extension(...)` with the observed arities and argument
     shapes.
8. Support observed independent backend/scalar type families:
   - `size_t`;
   - `intrin::vector::imask`;
   - observed `scalar::...` backend types such as unsigned, signed, and float
     scalar names if present.
9. Preserve and extend ordered alias behavior:
   - alias names are arbitrary source identifiers;
   - aliases are visible only after their `let<type>(...)` binding in the same
     selected body;
   - aliases may refer to previously resolved aliases and all supported type
     families;
   - aliases are never context built-ins.
10. Add focused positive and negative tests for each supported family,
    including nested observed forms such as:
    - `type<generation>(base::unsigned_of(type<generation>(base::in)))`;
    - `type<generation>(register::generic(OutVec))`;
    - `type<generation>(vector::transform_extension(ToBase))`;
    - `type<generation>(vector::as_extension(sse, type<generation>(base::in)))`;
    - `type<backend>(vector::as_extension(generic))`;
    - `type<backend>(scalar::ui8)`;
    - ordered aliases that compose these values.
11. Add diagnostics for unsupported observed type forms only when the form is
    deliberately left unsupported after inventory evidence. Unsupported forms
    must remain typed diagnostics, not raw renderer fallthrough.
12. Update redesign docs if the type taxonomy, type-query ownership, or
    diagnostics are clarified.

## Out Of Scope

Primitive-call selector target resolution; dependency closure; selecting or
lowering dependency implementation bodies; recursive call argument lowering;
backend call rendering; backend type text rendering; value query lowering
except as an explicit unsupported boundary inside observed type forms; broad
non-type expression parsing; assignment/indexing; source repair; complete TSIL
statement grammar; runtime `tsldata` lookup from product lowering; making
`frozen` or `tslgenold` a runtime dependency; broad template/signature
validation; extension/type-group expansion beyond what observed type values
need to represent identity; hardware/feature requirements; registries;
dispatchers; hidden backfeeds; fixpoint mechanisms; or broad
request/result/worklist families.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M143 completes the observed type-lowering
   model without becoming primitive-call selector resolution, dependency
   closure, backend rendering, broad expression parsing, or broad machinery.
2. Boundary auditor: verify type lowering consumes selected context, ordered
   aliases, and exact observed type forms; verify backend type queries produce
   typed requests over semantic type values; verify raw source text remains
   diagnostic/provenance context only; verify no runtime `tsldata`, `frozen`,
   or `tslgenold` dependency is introduced.
3. Evidence auditor: verify the inventory is grounded in every current
   `tsldata/**/*.tsl` file and that frozen evidence is used only for semantic
   clarification.
4. Documentation auditor: verify requirements/domain/roadmap/state docs
   accurately describe the M143 type model and defer primitive-call selector
   resolution.
5. Validation auditor: verify required validation ran and report exact command
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
prompt after M143 is accepted. Only then reconsider primitive-call selector
resolution, and only if the accepted M143 type model gives selectors fully
lowered semantic type identities.

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
