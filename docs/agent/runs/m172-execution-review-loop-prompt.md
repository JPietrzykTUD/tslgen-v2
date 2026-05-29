# M172 Execution Review Loop Prompt

This is the planned follow-on prompt after M171. Execute it only when
`docs/agent/current-redesign-state.md` points here and records M171 as
accepted.

You are executing and reviewing the accepted next milestone after M171:

```text
Milestone 172: Concrete Vector Alias Selector Matching
```

Milestones 1 through 171 are accepted. M171 made primitive-call target
matching carry explicit selected return-type binding values into matched
targets, guarded by selector-entry provenance. The next narrow gap is that
target matching still recognizes only a small subset of already-lowered
concrete vector values. Current corpus calls use type aliases such as
`StepVec`, `UVec`, `OutVec`, and `InVec` as selector entries after
`let<type>(...)` lowers them to vector transform values.

M172 is an implementation milestone. It should extend the existing
concrete-vector extraction boundary used by primitive-call target matching.
It must not parse the full `.tsl` selector tree or add a selector engine.

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
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/type_queries.py`
- `tslgen/src/tslgen/lowering/selector_payload.py`
- `tslgen/src/tslgen/lowering/primitive_calls.py`
- `tslgen/tests/test_m144_selector_payload.py`
- `tslgen/tests/test_m145_primitive_call_target_matching.py`
- `tslgen/tests/test_m169_selected_specialization_bindings.py`
- `tslgen/tests/test_m170_selector_payload_selected_bindings.py`
- `tslgen/tests/test_m171_primitive_call_return_binding_matching.py`

## Goal

Teach primitive-call target matching one additional already-lowered concrete
vector value family:

```text
let<type>(Alias, type<generation>(vector::transform_extension(CONCRETE_BASE)))
call<primitive=NAME[Alias]>(...)
```

and the same concrete-vector value in the M171 two-entry shape:

```text
call<primitive=NAME[Alias, RETURN_BINDING_VALUE]>(...)
```

The accepted value is not the alias name itself. It is the already lowered
typed value, such as `LoweredVectorTransformType`, only when its extension is
concrete and its base type resolves to a concrete scalar `TypeTag` through
accepted typed lowering facts.

Corpus-grounded examples include:

- `call<primitive=cast[StepVec, ToBase]>(...)` in conversion/cast bodies;
- `call<primitive=reinterpret[Vec, UVec]>(...)` where `UVec` is a vector
  transform alias;
- `call<primitive=load[UVec] attrs[...]>(...)` in load/store bodies.

`StepVec`, `UVec`, and `ToBase` are evidence, not generator keywords. Focused
tests must use arbitrary alias names and arbitrary return-binding names.

## Required Executor Task

Run exactly one write-capable executor for M172. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Inventory current `tsldata/**/*.tsl` evidence for primitive-call selector
   payloads that use type aliases as vector selector entries. Use this only to
   ground accepted shapes; do not build a corpus-wide selector parser.
3. Extend the existing concrete-vector extraction helper owned by
   `PrimitiveCallResolver` so it accepts `LoweredVectorTransformType` values
   when:
   - the vector transform carries a concrete extension from the selected
     context; and
   - the transform base type can be reduced to a concrete scalar `TypeTag`
     through already accepted typed lowering values, including
     `LoweredBackendTypeReference` wrapping scalar identities.
4. Preserve existing behavior for `CurrentVector`,
   `LoweredBackendTypeReference`, and `LoweredVectorAsExtensionType`.
5. Preserve M171 selected-return-binding provenance. A two-entry selector must
   still require the second entry to come from an explicit selected
   return-type binding.
6. Preserve unsupported diagnostics for unresolved specialization symbols, raw
   selector symbols, literals, raw extension operands in vector position,
   non-concrete vector values, mask/member vector aliases, and wrong
   return-binding provenance.
7. Add focused tests, preferably in
   `tslgen/tests/test_m172_primitive_call_concrete_vector_alias_matching.py`,
   for:
   - arbitrary alias names over `vector::transform_extension(scalar::...)`
     matching a target implementation by the alias' concrete type tag;
   - aliases whose base comes through `type<backend>(scalar::...)`;
   - aliases whose base comes through an already resolved signed/unsigned base
     transform;
   - the M171 two-entry alias-plus-return-binding shape preserving target
     return binding decoration;
   - existing `Vec`, `vector::as_extension(...)`, and single-vector behavior
     remain unchanged;
   - raw symbols, literals, catalog extension operands, unresolved
     specialization symbols, and mask/member aliases remain diagnostics.
8. Update docs that describe the accepted M172 behavior and any remaining
   follow-ups.
9. Leave final accepted-state updates to the orchestrator after read-only
   review returns `Accept` or `Accept With Follow-Ups`.

## Design Guardrails

- This is target matching over already lowered type values, not raw selector
  parsing.
- Alias names are source-local. Do not infer semantics from names such as
  `StepVec`, `UVec`, `MaskVec`, `OutVec`, or `InVec`.
- Do not solve mask/member/register backend types in this milestone unless
  they already expose a concrete scalar type tag through accepted typed facts.
- Do not derive `ToType`, expand wildcards, enumerate selector
  manifestations, or parse the nested `.tsl` implementation selector tree.
- Do not add a selector engine, registry, dispatcher, worklist, callback map,
  hidden backfeed, dependency scheduler, or fixpoint mechanism.
- Do not add backend rendering, primitive-call rendering, source replacement,
  source repair, arbitrary expression parsing, or statement parsing.

## Must Preserve

- M144 selector payload lowering, including current keywords, aliases,
  type-valued prefixes, known extension operands, literals, selector symbols,
  attrs parsing, and diagnostics.
- M145 single concrete-vector primitive-call target matching.
- M146-M151 primitive-call argument binding, reference inventory, dependency
  closure, expression lowering, and consolidation behavior.
- M168 exact `generic::*` generation-expression behavior and diagnostics.
- M168.5 primitive-local return-type declaration behavior.
- M169 selected specialization binding behavior in type/generation type
  lowering.
- M170 selected specialization binding visibility and provenance in selector
  payloads.
- M171 vector-plus-selected-return-binding target matching.

## Out Of Scope

Full `.tsl` implementation selector parsing; wildcard expansion; producing a
complete catalog of specialization manifestations; automatic target selection
for declared return-type identifiers; deriving `ToType`; solving
mask/member/register backend type aliases; broad dependency closure changes;
primitive-call rendering; backend value/control/intrinsic/source-operation
translation; loop execution or unrolling; branch selection changes;
declaration rendering; source replacement; backend rendering; type inference;
arbitrary expression or statement parsing; source repair; output writing;
runtime `tsldata`, `frozen`, or `tslgenold` dependencies; broad registries,
dispatchers, worklists, callback maps, hidden backfeeds, or fixpoint
machinery.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M172 remains concrete-vector extraction over
   typed selector payload values and does not add a selector engine, registry,
   scheduler, wildcard expansion, renderer pressure, or raw-name inference.
2. Boundary auditor: verify M144-M151 and M168-M171 behavior remains intact
   and unsupported selector dimensions remain diagnostics.
3. Evidence auditor: verify the accepted alias/vector-transform shape is
   grounded in current `tsldata/**/*.tsl` evidence without treating alias
   names as generator keywords.
4. Test auditor: verify focused M172 tests cover positive vector-transform
   aliases, M171 return-binding preservation, preservation suites, and
   negative unresolved/raw/mask-member cases.
5. Documentation auditor: verify roadmap, behavioral/domain docs,
   inventories, design decisions, and current state are coherent.
6. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py tslgen/tests/test_m148_primitive_call_dependency_closure.py tslgen/tests/test_m149_primitive_call_closure_lowering_package.py tslgen/tests/test_m150_primitive_call_expression.py tslgen/tests/test_m151_primitive_call_consolidation.py tslgen/tests/test_m168_generic_generation_expressions.py tslgen/tests/test_m1685_return_type_bindings.py tslgen/tests/test_m169_selected_specialization_bindings.py tslgen/tests/test_m170_selector_payload_selected_bindings.py tslgen/tests/test_m171_primitive_call_return_binding_matching.py tslgen/tests/test_m172_primitive_call_concrete_vector_alias_matching.py
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py tslgen/tests/test_m148_primitive_call_dependency_closure.py tslgen/tests/test_m149_primitive_call_closure_lowering_package.py tslgen/tests/test_m150_primitive_call_expression.py tslgen/tests/test_m151_primitive_call_consolidation.py tslgen/tests/test_m168_generic_generation_expressions.py tslgen/tests/test_m1685_return_type_bindings.py tslgen/tests/test_m169_selected_specialization_bindings.py tslgen/tests/test_m170_selector_payload_selected_bindings.py tslgen/tests/test_m171_primitive_call_return_binding_matching.py tslgen/tests/test_m172_primitive_call_concrete_vector_alias_matching.py
find tslgen -type d -name __pycache__ -print
```

Remove validation-created `__pycache__` directories before the final cache
check if any are created.

## Completion Rules

If M172 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M172 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside
this prompt after M172 is accepted. Do not start M173 until the next prompt
explicitly selects it.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 173 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Executor summary.
3. Review/audit verdicts and any follow-ups.
4. Validation commands and exact results.
5. Next active prompt path.
