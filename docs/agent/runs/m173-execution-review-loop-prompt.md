# M173 Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M172 as accepted.

You are executing and reviewing the accepted next milestone after M172:

```text
Milestone 173: Vector Member Type Query Resolution Boundary
```

Milestones 1 through 172 are accepted. M172 made primitive-call target
matching consume already lowered concrete vector-transform aliases. The next
lowering gap exposed by that work is not another selector shape: it is the
already recognized current-vector member type query family, especially
`type<generation>(vector::mask_underlying_t)`, which appears in aliases such
as `MaskWord` and inside `MaskVec`.

M173 is an implementation milestone. It should resolve only exact
current-vector member type values that are already represented as typed
`LoweredVectorMemberType` facts, using explicit extension metadata from the
catalog. It must not parse arbitrary body syntax, infer from alias names, or
render backend type spellings.

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
- `docs/redesign/tsil-type-query-inventory.md`
- `docs/redesign/missing-lowering-inventory.md`
- `tsldata/extensions/extension.tsl`
- `tsldata/primitives/load_store/store.tsl`
- `tsldata/primitives/load_store/load.tsl`
- `tsldata/primitives/conversion/mask_specific.tsl`
- `tslgen/src/tslgen/domain/catalog.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/type_queries.py`
- `tslgen/src/tslgen/lowering/generation_generic.py`
- `tslgen/src/tslgen/lowering/generation_values.py`
- `tslgen/src/tslgen/lowering/primitive_calls.py`
- `tslgen/tests/test_m143_1_extension_catalog.py`
- `tslgen/tests/test_m144_selector_payload.py`
- `tslgen/tests/test_m145_primitive_call_target_matching.py`
- `tslgen/tests/test_m172_primitive_call_concrete_vector_alias_matching.py`

## Goal

Add a narrow resolver for exact current-vector member type values:

```text
type<generation>(vector::mask_underlying_t)
type<generation>(vector::mask_underlying)
type<generation>(vector::imask)
type<generation>(vector::mask)
```

The resolver consumes the accepted typed value:

```text
LoweredVectorMemberType(member=..., extension=..., type_tag=...)
```

plus explicit extension metadata from the selected catalog. It may produce a
concrete scalar type fact only when the catalog policy proves one at
generation time. Otherwise the member type remains an unresolved/backend-owned
typed fact or a precise diagnostic.

## Required Executor Task

Run exactly one write-capable executor for M173. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Inventory current `tsldata/**/*.tsl` evidence for vector member type
   queries, including aliases such as `MaskWord`, `MaskT`, and `MaskVec`.
3. Implement a focused vector-member type resolver over already lowered
   `LoweredVectorMemberType` values. Keep ownership small; a focused helper
   module is acceptable if it avoids growing `type_queries.py` or
   `primitive_calls.py` into a catch-all.
4. Use accepted catalog extension metadata only:
   - `mask_type_policy`
   - `integral_mask_type_policy`
   - `vector_bits`
   - selected scalar type facts
5. Resolve a member query to a concrete scalar `TypeTag` only when all needed
   facts are explicit and fixed at generation time. Supported examples should
   include lane-bitmask or unsigned-scalar policies only if they can be
   represented by accepted scalar descriptor facts without guessing backend
   spellings.
6. Preserve native predicate, size-parameter, scalable/runtime-lane, missing
   metadata, and unsupported policy cases as diagnostics or unresolved typed
   backend-owned facts. Do not synthesize a scalar type from an unknown policy.
7. Let any concrete scalar member resolution feed primitive-call selector
   matching only through the existing typed-value path used by M172. Do not
   add alias-name checks for `MaskVec`, `MaskWord`, or `MaskT`.
8. Preserve M143.1 extension catalog behavior, M144 selector payload lowering,
   M168 generation-value behavior, M171 return-binding provenance, and M172
   concrete-vector alias matching.
9. Add focused tests, preferably in
   `tslgen/tests/test_m173_vector_member_type_resolution.py`, for:
   - positive concrete scalar member resolution from explicit fixed metadata;
   - `MaskVec`-style vector transform over `vector::mask_underlying_t` matching
     only when the member resolves to a concrete scalar tag;
   - native predicate or backend-owned mask policies not being treated as
     scalar vector selectors;
   - missing extension metadata and unsupported policy diagnostics;
   - arbitrary alias names proving no semantic dependence on `MaskVec`,
     `MaskWord`, or `MaskT`;
   - preservation of M172 tests and diagnostics.
10. Update docs that describe the accepted M173 behavior and remaining
    follow-ups.
11. Leave final accepted-state updates to the orchestrator after read-only
    review returns `Accept` or `Accept With Follow-Ups`.

If the executor discovers that every safe positive case first requires a
broader scalar descriptor/catalog milestone, it must stop with
`Return To Planner` and record that prerequisite instead of adding speculative
member-type semantics.

## Design Guardrails

- This is lowering of exact TSIL type-query values already represented as
  typed values, not parsing arbitrary implementation-body surroundings.
- Alias names are source-local. Do not infer semantics from `MaskVec`,
  `MaskWord`, `MaskT`, `UVec`, or any other alias spelling.
- Do not model all target-language vector/member/register concepts merely
  because they are mentioned in `extension.tsl`.
- Do not render backend type spellings, Rust associated types, C++ aliases, or
  `typename Vec::...` text.
- Do not add selector engines, registries, dispatchers, worklists, callback
  maps, hidden backfeeds, dependency schedulers, or fixpoint machinery.
- Do not parse target-language expressions, loops, assignments, casts,
  declarations, or arbitrary statements.

## Must Preserve

- M143.1 extension catalog facts and inheritance behavior.
- M144 selector payload lowering and diagnostics.
- M145 single concrete-vector primitive-call target matching.
- M146-M151 primitive-call argument binding, reference inventory, dependency
  closure, expression lowering, and consolidation behavior.
- M168 exact `generic::*` generation-expression behavior and diagnostics.
- M168.5 primitive-local return-type declaration behavior.
- M169 selected specialization binding behavior.
- M170 selected specialization binding visibility in selector payloads.
- M171 vector-plus-selected-return-binding target matching.
- M172 concrete vector-transform alias matching.

## Out Of Scope

Backend type spelling; register-type spelling; complete mask/register backend
modeling; rendering `typename Vec::...` or Rust associated types; resolving
SVE runtime lanes; evaluating generic size parameters beyond already accepted
fixed facts; full `.tsl` selector-tree parsing; wildcard expansion; deriving
`ToType`; primitive-call rendering; backend value/control/intrinsic/source
operation translation; branch or loop execution; declaration rendering; source
replacement; source repair; output writing; runtime `tsldata`, `frozen`, or
`tslgenold` dependencies; broad registries, dispatchers, worklists, callback
maps, hidden backfeeds, or fixpoint machinery.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M173 remains exact vector-member type-query
   lowering over typed facts and explicit extension metadata, without
   renderer pressure or broad semantic machinery.
2. Boundary auditor: verify M143.1, M144-M151, and M168-M172 behavior remains
   intact and unsupported member/policy cases remain diagnostics or unresolved
   typed facts.
3. Evidence auditor: verify accepted member-query handling is grounded in
   current `tsldata/**/*.tsl` evidence and does not treat alias names as
   generator keywords.
4. Test auditor: verify focused M173 tests cover positive concrete metadata,
   `MaskVec`-style selector matching only through typed values, native
   predicate/backend-owned negatives, metadata diagnostics, and preservation
   suites.
5. Documentation auditor: verify roadmap, behavioral/domain docs, design
   decisions, inventories, and current state are coherent.
6. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py tslgen/tests/test_m148_primitive_call_dependency_closure.py tslgen/tests/test_m149_primitive_call_closure_lowering_package.py tslgen/tests/test_m150_primitive_call_expression.py tslgen/tests/test_m151_primitive_call_consolidation.py tslgen/tests/test_m168_generic_generation_expressions.py tslgen/tests/test_m1685_return_type_bindings.py tslgen/tests/test_m169_selected_specialization_bindings.py tslgen/tests/test_m170_selector_payload_selected_bindings.py tslgen/tests/test_m171_primitive_call_return_binding_matching.py tslgen/tests/test_m172_primitive_call_concrete_vector_alias_matching.py tslgen/tests/test_m173_vector_member_type_resolution.py
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py tslgen/tests/test_m148_primitive_call_dependency_closure.py tslgen/tests/test_m149_primitive_call_closure_lowering_package.py tslgen/tests/test_m150_primitive_call_expression.py tslgen/tests/test_m151_primitive_call_consolidation.py tslgen/tests/test_m168_generic_generation_expressions.py tslgen/tests/test_m1685_return_type_bindings.py tslgen/tests/test_m169_selected_specialization_bindings.py tslgen/tests/test_m170_selector_payload_selected_bindings.py tslgen/tests/test_m171_primitive_call_return_binding_matching.py tslgen/tests/test_m172_primitive_call_concrete_vector_alias_matching.py tslgen/tests/test_m173_vector_member_type_resolution.py
find tslgen -type d -name __pycache__ -print
```

Remove validation-created `__pycache__` directories before the final cache
check if any are created.

## Completion Rules

If M173 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M173 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside
this prompt after M173 is accepted. Do not start M174 until the next prompt
explicitly selects it.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 174 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Executor summary.
3. Review/audit verdicts and any follow-ups.
4. Validation commands and exact results.
5. Next active prompt path.
