# M171 Execution Review Loop Prompt

This is the planned follow-on prompt after M170. Execute it only when
`docs/agent/current-redesign-state.md` points here and records M170 as
accepted.

You are executing and reviewing the accepted next milestone after M170:

```text
Milestone 171: Return-Type Selector Binding Propagation In Primitive-Call Target Matching
```

Milestones 1 through 170 are accepted. M170 made explicit selected
specialization binding facts visible to primitive-call selector-payload
lowering. The next narrow gap is that target matching still consumes only a
single concrete vector specialization, so observed selector shapes such as
`call<primitive=cast[Vec, ToBase]>(...)` can lower their parts but cannot pass
the return-type selector value into the matched target's selected context.

M171 is an implementation milestone. It should extend primitive-call target
matching to carry exact selected return-type binding facts into the matched
target when the already lowered selector payload provides those facts. It must
not parse the full `.tsl` selector tree or add a general selector engine.

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
- `tslgen/src/tslgen/analysis/selection.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/selected_specializations.py`
- `tslgen/src/tslgen/lowering/selector_payload.py`
- `tslgen/src/tslgen/lowering/primitive_calls.py`
- `tslgen/tests/test_m145_primitive_call_target_matching.py`
- `tslgen/tests/test_m148_primitive_call_dependency_closure.py`
- `tslgen/tests/test_m169_selected_specialization_bindings.py`
- `tslgen/tests/test_m170_selector_payload_selected_bindings.py`

## Goal

Teach primitive-call target matching one exact selected-return binding shape:

```text
call<primitive=NAME[CONCRETE_VECTOR, RETURN_BINDING_VALUE]>(...)
```

where `CONCRETE_VECTOR` is already lowered by M144/M170 to a concrete
`CurrentVector`-compatible value and `RETURN_BINDING_VALUE` is already lowered
by M170 from an explicit selected binding:

- a scalar/base selected value for a target primitive that declares
  `return_type: base: <arbitrary name>`;
- an extension selected value for a target primitive that declares
  `return_type: extension: <arbitrary name>`.

The matched `SelectedImplementation.target.specialization_bindings` should
carry the target primitive's declaration name, not the caller's source
spelling. This keeps names source-owned and primitive-local.

Corpus-grounded examples include many conversion calls such as:

```text
call<primitive=cast[Vec, ToBase]>(...)
call<primitive=reinterpret[Vec, ToBase]>(...)
```

`ToBase` is evidence, not a generator keyword. Focused tests must use
arbitrary caller binding names and arbitrary target declaration names.

## Required Executor Task

Run exactly one write-capable executor for M171. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Inventory current `tsldata/**/*.tsl` evidence for primitive-call selector
   payloads that combine a concrete vector selector with a return-type base or
   extension selector. Use this only to ground the exact accepted source
   shape; do not build a corpus-wide selector parser.
3. Extend `PrimitiveCallResolver.match_target(...)` or a focused helper it
   owns so target matching accepts the exact two-entry shape:
   concrete vector selector plus selected return-type binding value.
4. For a matched target primitive with `return_type: base: TargetName`, map a
   scalar selected value to
   `TargetReturnTypeBaseBinding(name="TargetName", type_tag=...)` on the
   matched target.
5. For a matched target primitive with
   `return_type: extension: TargetName`, map an extension selected value to
   `TargetReturnTypeExtensionBinding(name="TargetName", extension=...)` on the
   matched target.
6. Preserve the existing no-specialization and single-concrete-vector
   matching behavior exactly.
7. Preserve existing unsupported diagnostics for raw symbols, literals,
   multiple unsupported selector dimensions, non-concrete vector values,
   return-binding values without a compatible target declaration, and wrong
   binding kind.
8. Ensure the matched selected implementation carries deterministic target
   sort keys when selected bindings are attached. Dependency inventory/closure
   may observe the decorated selected implementation naturally through the
   existing match result, but do not add new dependency scheduling or closure
   propagation machinery.
9. Add focused tests, preferably in
   `tslgen/tests/test_m171_primitive_call_return_binding_matching.py`, for:
   - arbitrary caller base binding name mapped to arbitrary target
     `return_type base` declaration name;
   - arbitrary caller extension binding name mapped to arbitrary target
     `return_type extension` declaration name;
   - existing single-vector selector matching remains unchanged;
   - raw unbound selector symbols remain unsupported in target matching;
   - scalar return-binding selector without target return-type declaration is
     diagnostic;
   - wrong binding kind for target declaration is diagnostic;
   - reference inventory or dependency closure preserves the decorated target
     binding through the existing primitive-call reference path.
10. Update docs that describe the accepted M171 behavior and any remaining
    follow-ups.
11. Leave final accepted-state updates to the orchestrator after read-only
    review returns `Accept` or `Accept With Follow-Ups`.

## Design Guardrails

- This is target matching over already lowered selector-payload values, not
  raw selector parsing.
- Return-type declaration names are primitive-local. The selected binding
  attached to the matched target must use the target primitive declaration
  name, not the caller's selector spelling.
- Do not infer values from raw names such as `ToBase`, `ToExtension`,
  `ResultBase`, or `TargetExtension`.
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
- M170 selected specialization binding visibility in selector payloads.

## Out Of Scope

Full `.tsl` implementation selector parsing; wildcard expansion; producing a
complete catalog of specialization manifestations; automatic target selection
for declared return-type identifiers; deriving `ToType`; forwarding arbitrary
selected bindings into dependency targets; broad dependency closure changes;
primitive-call rendering; backend value/control/intrinsic/source-operation
translation; loop execution or unrolling; branch selection changes;
declaration rendering; source replacement; backend rendering; type inference;
arbitrary expression or statement parsing; source repair; output writing;
runtime `tsldata`, `frozen`, or `tslgenold` dependencies; broad registries,
dispatchers, worklists, callback maps, hidden backfeeds, or fixpoint
machinery.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M171 remains target matching over typed
   selector payload values and does not add a selector engine, registry,
   scheduler, wildcard expansion, renderer pressure, or raw-name inference.
2. Boundary auditor: verify M144-M151, M168-M170 behavior remains intact and
   unsupported selector dimensions remain diagnostics.
3. Evidence auditor: verify the accepted two-entry shape is grounded in
   current `tsldata/**/*.tsl` evidence without treating corpus names as
   generator keywords.
4. Test auditor: verify focused M171 tests cover base and extension
   propagation, arbitrary names, no-declaration/wrong-kind diagnostics,
   preservation suites, and reference/closure visibility.
5. Documentation auditor: verify roadmap, behavioral/domain docs,
   inventories, design decisions, and current state are coherent.
6. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py tslgen/tests/test_m148_primitive_call_dependency_closure.py tslgen/tests/test_m149_primitive_call_closure_lowering_package.py tslgen/tests/test_m150_primitive_call_expression.py tslgen/tests/test_m151_primitive_call_consolidation.py tslgen/tests/test_m168_generic_generation_expressions.py tslgen/tests/test_m1685_return_type_bindings.py tslgen/tests/test_m169_selected_specialization_bindings.py tslgen/tests/test_m170_selector_payload_selected_bindings.py tslgen/tests/test_m171_primitive_call_return_binding_matching.py
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py tslgen/tests/test_m148_primitive_call_dependency_closure.py tslgen/tests/test_m149_primitive_call_closure_lowering_package.py tslgen/tests/test_m150_primitive_call_expression.py tslgen/tests/test_m151_primitive_call_consolidation.py tslgen/tests/test_m168_generic_generation_expressions.py tslgen/tests/test_m1685_return_type_bindings.py tslgen/tests/test_m169_selected_specialization_bindings.py tslgen/tests/test_m170_selector_payload_selected_bindings.py tslgen/tests/test_m171_primitive_call_return_binding_matching.py
find tslgen -type d -name __pycache__ -print
```

Remove validation-created `__pycache__` directories before the final cache
check if any are created.

## Completion Rules

If M171 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M171 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside
this prompt after M171 is accepted. Do not start M172 until the next prompt
explicitly selects it.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 172 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Executor summary.
3. Review/audit verdicts and any follow-ups.
4. Validation commands and exact results.
5. Next active prompt path.
