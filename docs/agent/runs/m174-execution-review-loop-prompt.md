# M174 Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M173 as accepted.

You are executing and reviewing:

```text
Milestone 174: Scalar Descriptor Catalog Completion For Current Type Tags
```

Milestones 1 through 173 are accepted. M173 proved that vector member type
queries can resolve through explicit extension metadata, but real fixed
lane-bitmask cases still diagnose when the produced exact unsigned scalar tag
such as `ui8`, `ui16`, or `ui64` has no accepted scalar descriptor. M174 closes
that descriptor gap. It is a lowering milestone, not a parser, renderer, or
operator-language milestone.

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
- `tslgen/src/tslgen/lowering/scalar_types.py`
- `tslgen/src/tslgen/lowering/operation_type_compatibility.py`
- `tslgen/src/tslgen/lowering/type_queries.py`
- `tslgen/src/tslgen/lowering/generation_values.py`
- `tslgen/src/tslgen/lowering/generation_generic.py`
- `tslgen/src/tslgen/lowering/vector_member_types.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`
- `tslgen/tests/test_m168_generic_generation_expressions.py`
- `tslgen/tests/test_m173_vector_member_type_resolution.py`

## Goal

Broaden the accepted scalar descriptor catalog from the tiny representative
set to the current concrete scalar tags used by the TSL data:

```text
si8, ui8, si16, ui16, si32, ui32, si64, ui64, f32, f64
```

Each accepted tag must have explicit typed facts: family, signedness, and bit
width. Downstream lowering must consume those facts, not infer properties from
raw tag spelling.

## Required Executor Task

Run exactly one write-capable executor for M174. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Inventory current scalar tag evidence from `tsldata/detail/types.tsl` and
   the existing descriptor consumers.
3. Expand `SUPPORTED_SCALAR_TYPE_DESCRIPTORS` with explicit descriptors for
   `si8`, `ui8`, `si16`, `ui16`, `si32`, `ui32`, `si64`, `ui64`, `f32`, and
   `f64`. Keep deterministic ordering and avoid deriving facts from spelling
   in lookup/evaluation code.
4. Update tests that intentionally assert descriptor availability,
   supported-tag ordering, byte size, signedness, signed/unsigned transforms,
   type equality, generic length/runtime-length, and operation compatibility.
5. Add a focused `test_m174_scalar_descriptor_catalog.py` if that keeps the
   new catalog-completion assertions clearer than growing M107 further.
6. Update M173 tests so at least one real current lane-bitmask member result
   that previously diagnosed because of a missing exact unsigned descriptor
   now resolves through accepted descriptors. Preserve native-predicate,
   runtime/scalable, backend-owned, and unsupported-policy negatives.
7. If broadening descriptors changes operation compatibility, make that
   behavior explicit in tests and docs. Do not add or remove operation
   identifiers in this milestone.
8. Update docs describing current scalar descriptor coverage and the resolved
   M173 follow-up.
9. Leave final accepted-state updates to the orchestrator after read-only
   review returns `Accept` or `Accept With Follow-Ups`.

If the executor discovers that scalar tags cannot be broadened without a new
catalog/type-system design decision, stop with `Return To Planner` and record
the specific blocker instead of adding a workaround.

## Design Guardrails

- This is descriptor catalog completion for known scalar tags, not a general
  type parser or target-language model.
- Do not infer scalar properties from TypeTag spelling in semantic lowering
  code. The descriptors are the facts.
- Do not introduce a registry, dispatcher, worklist, request/result family, or
  runtime data dependency just to store these fixed descriptor facts.
- Do not change primitive-call selector shapes, dependency closure, rendering,
  backend translation, or output writing.
- Do not parse C, C++, or Rust operators or expressions.

## Must Preserve

- M143.1 extension catalog facts and inheritance behavior.
- M144-M151 primitive-call selector payload, matching, binding, inventory,
  closure, expression, and consolidation behavior.
- M168 generic generation-expression boundaries.
- M168.5-M171 return-type binding and selected-specialization behavior.
- M172 concrete vector-transform alias matching.
- M173 vector-member type resolution boundaries and diagnostics.

## Out Of Scope

New scalar categories beyond the current concrete TSL scalar tags; new
operation identifiers; target-language operator parsing; backend type
spelling; register/native-predicate spelling; wildcard expansion; dependency
scheduling; branch, loop, declaration, or primitive-call rendering; source
repair; output writing; runtime `tsldata`, `frozen`, or `tslgenold`
dependencies; broad registries, dispatchers, worklists, callback maps, hidden
backfeeds, or fixpoint machinery.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M174 is descriptor catalog completion only,
   with no spelling inference, parser expansion, renderer pressure, or broad
   machinery.
2. Boundary auditor: verify M143.1, M144-M151, M168-M173 behavior remains
   intact and descriptor-driven changes are explicit.
3. Evidence auditor: verify the accepted scalar tags are grounded in current
   `tsldata/detail/types.tsl` and extension/member evidence.
4. Test auditor: verify descriptor, generation-value, generic, operation
   compatibility, and M173 real-member-resolution tests cover the change.
5. Documentation auditor: verify roadmap, behavioral/domain docs, design
   decisions, inventories, and current state are coherent.
6. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m168_generic_generation_expressions.py tslgen/tests/test_m173_vector_member_type_resolution.py tslgen/tests/test_m174_scalar_descriptor_catalog.py
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m168_generic_generation_expressions.py tslgen/tests/test_m173_vector_member_type_resolution.py tslgen/tests/test_m174_scalar_descriptor_catalog.py
find tslgen -type d -name __pycache__ -print
```

Remove validation-created `__pycache__` directories before the final cache
check if any are created.

## Completion Rules

If M174 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M174 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside
this prompt after M174 is accepted. Do not start M175 until the next prompt
explicitly selects it.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 175 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Executor summary.
3. Review/audit verdicts and any follow-ups.
4. Validation commands and exact results.
5. Next active prompt path.
