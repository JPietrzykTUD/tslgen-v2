# M175 Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M174 as accepted.

You are executing and reviewing:

```text
Milestone 175: Vector Member Generation Value Type Arguments
```

Milestones 1 through 174 are accepted. M173 added descriptor-backed vector
member type resolution for already lowered `LoweredVectorMemberType` values.
M174 completed the scalar descriptor table needed by real fixed lane-bitmask
member results such as `ui8`, `ui16`, and `ui64`. M175 should connect those
accepted facts to existing generation value type queries. It is a lowering
milestone, not a backend spelling, renderer, or expression-language milestone.

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
- `docs/redesign/design-decisions.md`
- `docs/redesign/missing-lowering-inventory.md`
- `tsldata/detail/types.tsl`
- `tsldata/extensions/extension.tsl`
- `tslgen/src/tslgen/lowering/generation_values.py`
- `tslgen/src/tslgen/lowering/type_queries.py`
- `tslgen/src/tslgen/lowering/vector_member_types.py`
- `tslgen/src/tslgen/lowering/scalar_types.py`
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`
- `tslgen/tests/test_m168_generic_generation_expressions.py`
- `tslgen/tests/test_m173_vector_member_type_resolution.py`
- `tslgen/tests/test_m174_scalar_descriptor_catalog.py`

## Goal

Allow existing generation value queries that consume scalar type arguments to
consume already lowered vector-member type facts when an explicit catalog is
available:

```text
value<generation>(type::size_bytes(type<generation>(vector::imask)))
value<generation>(type::is_signed(type<generation>(vector::imask)))
value<generation>(type::is_same(type<generation>(vector::imask), scalar::ui8))
```

The accepted path is:

```text
type<generation>(vector::imask)
-> LoweredVectorMemberType(...)
-> resolve_vector_member_scalar_type(..., catalog=...)
-> LoweredScalarTypeIdentity(TypeTag(...))
-> existing scalar descriptor lookup
```

## Required Executor Task

Run exactly one write-capable executor for M175. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Confirm the current behavior: `type<generation>(vector::imask)` lowers to
   `LoweredVectorMemberType`, M173 can resolve it with catalog metadata, and
   generation value scalar-type argument handling still rejects it.
3. Update generation value scalar-type argument handling so a lowered
   `LoweredVectorMemberType` resolves through
   `resolve_vector_member_scalar_type(...)` only when an explicit `Catalog` is
   supplied.
4. Preserve existing diagnostics when no catalog is supplied, when the vector
   member resolver reports unsupported/missing metadata, or when the resolved
   scalar tag has no accepted descriptor.
5. Keep existing `type::size_bytes(...)`, `type::is_signed(...)`, and
   `type::is_same(...)` query semantics. M175 should make their type arguments
   more complete, not add new value-query families.
6. Add focused tests, preferably in
   `tslgen/tests/test_m175_vector_member_generation_values.py`, covering:
   real fixed `avx2` positive cases for `vector::imask` or
   `vector::mask_underlying_t`;
   `type::size_bytes`, `type::is_signed`, and `type::is_same` consumption;
   no-catalog unsupported behavior; and at least one unsupported metadata
   boundary inherited from M173.
7. Update docs describing that generation value type queries can consume
   descriptor-backed vector member type facts when catalog metadata is
   supplied.
8. Leave final accepted-state updates to the orchestrator after read-only
   review returns `Accept` or `Accept With Follow-Ups`.

If the executor discovers that this requires backend type spelling, broad type
policy modeling, or renderer/source replacement behavior, stop with
`Return To Planner` and record the exact blocker instead of adding a
workaround.

## Design Guardrails

- This is a small connection between two accepted lowering capabilities:
  generation value scalar-type arguments and M173 vector-member scalar
  resolution.
- Do not infer scalar properties from raw tag spelling. Descriptor lookup
  remains the source of scalar facts.
- Do not parse target-language expressions or raw operators.
- Do not add a registry, dispatcher, worklist, request/result family, callback
  map, hidden backfeed, or fixpoint mechanism for this bridge.
- Do not make `tsldata`, `frozen`, or `tslgenold` a runtime dependency.

## Must Preserve

- M155 generation value query boundaries and diagnostics for unsupported
  query families.
- M168 generic generation-expression boundaries.
- M168.5-M172 selected-specialization and primitive-call selector behavior.
- M173 vector-member resolver policies and diagnostics.
- M174 scalar descriptor catalog facts and descriptor-driven operation
  compatibility.

## Out Of Scope

Backend type spelling; backend query translation; register/native-predicate
spelling; new vector member policies; new scalar descriptors; new generation
value query families; primitive-call matching changes; dependency scheduling;
recursive source-token rendering; branch, loop, declaration, backend-control,
intrinsic, cast, memory, or I/O rendering; source repair; output writing;
runtime `tsldata`, `frozen`, or `tslgenold` dependencies; broad expression
parsing; broad type-system redesign; registries, dispatchers, worklists,
callbacks, hidden backfeeds, or fixpoint machinery.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M175 is only the focused bridge from
   generation value type arguments to accepted vector-member resolution.
2. Boundary auditor: verify M155, M168-M174 behavior and diagnostics remain
   intact.
3. Evidence auditor: verify positive cases are grounded in current
   `tsldata/detail/types.tsl` and `tsldata/extensions/extension.tsl`, while
   descriptor facts remain lowering-owned.
4. Test auditor: verify positive, no-catalog, unsupported metadata, and
   regression coverage is sufficient.
5. Documentation auditor: verify roadmap, behavioral/domain docs, design
   decisions, inventories, and current state are coherent.
6. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m168_generic_generation_expressions.py tslgen/tests/test_m173_vector_member_type_resolution.py tslgen/tests/test_m174_scalar_descriptor_catalog.py tslgen/tests/test_m175_vector_member_generation_values.py
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m168_generic_generation_expressions.py tslgen/tests/test_m173_vector_member_type_resolution.py tslgen/tests/test_m174_scalar_descriptor_catalog.py tslgen/tests/test_m175_vector_member_generation_values.py
find tslgen -type d -name __pycache__ -print
```

Remove validation-created `__pycache__` directories before the final cache
check if any are created.

## Completion Rules

If M175 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M175 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside
this prompt after M175 is accepted. Do not start M176 until the next prompt
explicitly selects it.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 176 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Executor summary.
3. Review/audit verdicts and any follow-ups.
4. Validation commands and exact results.
5. Next active prompt path.
