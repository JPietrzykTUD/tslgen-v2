# M170 Execution Review Loop Prompt

This is the planned follow-on prompt after M169. Execute it only when
`docs/agent/current-redesign-state.md` points here and records M169 as
accepted.

You are executing and reviewing the accepted next milestone after M169:

```text
Milestone 170: Selected Binding Visibility In Primitive-Call Selectors
```

Milestones 1 through 169 are accepted. M169 added explicit selected
specialization binding facts on `Target`, copied them into the selected
lowering context, and resolved them in type/generation type lowering. Review
recorded one remaining boundary: primitive-call selector payload lowering
still classifies bare selector parts using only current keywords, aliases,
known prefixes, catalog extensions, literals, and raw selector symbols.

M170 is an implementation milestone. It should make already supplied M169
selected binding facts visible to the existing primitive-call selector-payload
lowering boundary. It must not parse the full `.tsl` selector tree, expand
wildcards, or change dependency closure semantics.

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
- `docs/redesign/generation-value-query-inventory.md`
- `docs/redesign/tsil-type-query-inventory.md`
- `docs/redesign/missing-lowering-inventory.md`
- `tslgen/src/tslgen/analysis/selection.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/type_queries.py`
- `tslgen/src/tslgen/lowering/selector_payload.py`
- `tslgen/src/tslgen/lowering/primitive_calls.py`
- `tslgen/tests/test_m144_selector_payload.py`
- `tslgen/tests/test_m143_1_extension_catalog.py`
- `tslgen/tests/test_m145_primitive_call_target_matching.py`
- `tslgen/tests/test_m169_selected_specialization_bindings.py`

## Goal

Extend the existing primitive-call selector payload lowerer so exact selector
parts can consume explicit selected binding facts:

```text
call<primitive=NAME[ResultBase]>(...)
call<primitive=NAME[TargetExtension]>(...)
call<primitive=NAME[ToType]>(...)
```

where `ResultBase`, `TargetExtension`, and `ToType` are examples of selected
binding names supplied by `Target.specialization_bindings`, not generator
keywords.

M170 should also reduce the M169 module-size pressure by extracting the
selected-binding validation/resolution helper block out of `type_queries.py`
into one focused lowering module if that is the safest way to share it with
`selector_payload.py`.

## Required Executor Task

Run exactly one write-capable executor for M170. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Add or extract a small focused selected-specialization helper module only if
   needed to share M169 binding validation/resolution between type-query
   lowering and selector-payload lowering. This helper must remain a lowering
   utility, not a registry, dispatcher, worklist, selector engine, or parser.
3. Preserve M169 type/generation lowering behavior and diagnostics exactly.
4. Extend `lower_primitive_call_selector_payload(...)` so a bare selector part
   that names an explicit selected return-type base binding lowers to the same
   concrete scalar type value used by M169 type lowering.
5. Extend selector payload lowering so a bare selector part that names an
   explicit selected return-type extension binding lowers to an
   `ExtensionOperand` for the supplied concrete extension.
6. Extend selector payload lowering so a bare selector part that names an
   explicit vector/type binding lowers to the concrete `CurrentVector` fact.
7. Keep existing raw selector-symbol behavior for unbound arbitrary names that
   are not context keywords, not aliases, not known extensions, not integer
   literals, not type-valued prefixes, and not selected binding names.
8. Preserve existing M144 selector payload behavior, M145-M151 primitive-call
   behavior, M168 generic-expression behavior, and M169 selected binding
   behavior.
9. Add focused tests, preferably in
   `tslgen/tests/test_m170_selector_payload_selected_bindings.py`, for:
   - arbitrary base binding name in `call<primitive=... [NAME]>(...)`;
   - arbitrary extension binding name in selector payload;
   - explicit vector/type binding name in selector payload;
   - unbound arbitrary selector symbol remains `SelectorSymbol`;
   - declared extension binding without supplied selected fact produces the
     accepted selected-binding diagnostic, not a raw extension fallback;
   - malformed/duplicate/mismatched selected bindings preserve M169 diagnostics
     with code, severity, and location;
   - existing alias/current-keyword/prefix selector payload behavior remains
     intact;
   - existing target matching can consume the vector/type case only through
     the already accepted concrete-vector path.
10. Update docs that describe the accepted M170 behavior and remaining
    follow-ups.
11. Leave final accepted-state updates to the orchestrator after read-only
    review returns `Accept` or `Accept With Follow-Ups`.

## Design Guardrails

- This is selector-payload lowering over already classified primitive-call
  selector islands, not full source selector parsing.
- Selected binding names come from explicit M169 target facts. Do not infer
  values from raw names such as `ToBase`, branch labels, tests, primitive
  attributes, backend helper payloads, intrinsic names, or surrounding code.
- Do not expand wildcards, enumerate selector manifestations, derive `ToType`,
  or parse the nested `.tsl` implementation selector tree.
- Do not add a broad registry, dispatcher, worklist, callback map, hidden
  backfeed, dependency scheduler, or fixpoint mechanism.
- Do not change primitive-call dependency closure or propagate selected
  bindings into dependency targets in this milestone. Record that as a future
  follow-up if evidence requires it.
- Do not add backend rendering, source replacement, source repair, arbitrary
  expression parsing, or statement parsing.

## Must Preserve

- M144 selector payload lowering, including current keywords, aliases,
  type-valued prefixes, known extension operands, literals, selector symbols,
  attrs parsing, and diagnostics.
- M145-M151 primitive-call target matching, argument binding, reference
  inventory, dependency closure, expression lowering, and consolidation
  behavior.
- M168 exact `generic::*` generation-expression behavior and diagnostics.
- M168.5 primitive-local return-type declaration behavior.
- M169 selected specialization binding behavior in type/generation type
  lowering, including arbitrary names, validation against declarations,
  explicit vector/type bindings, invalid-binding diagnostics, and unbound
  behavior.

## Out Of Scope

Full `.tsl` implementation selector parsing; wildcard expansion; producing a
complete catalog of specialization manifestations; automatic target selection
for declared return-type identifiers; deriving `ToType`; dependency closure
changes; forwarding selected bindings into dependency targets; primitive-call
rendering; backend value/control/intrinsic/source-operation translation; loop
execution or unrolling; branch selection changes; declaration rendering;
source replacement; backend rendering; type inference; arbitrary expression or
statement parsing; source repair; output writing; runtime `tsldata`,
`frozen`, or `tslgenold` dependencies; broad registries, dispatchers,
worklists, callback maps, hidden backfeeds, or fixpoint machinery.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M170 shares the selected-binding boundary
   without adding selector-engine, registry/dispatcher/worklist, wildcard, or
   renderer pressure.
2. Boundary auditor: verify M144-M151, M168, and M169 behavior remains intact;
   unbound raw selector symbols stay raw symbols unless they are selected
   binding names.
3. Evidence auditor: verify selector examples and follow-ups are grounded in
   current `tsldata/**/*.tsl` evidence without treating examples as keywords.
4. Test auditor: verify focused M170 tests cover base, extension, vector/type,
   raw-symbol preservation, diagnostics with locations, and preservation
   suites.
5. Documentation auditor: verify roadmap, behavioral/domain docs,
   generation/type inventories, missing inventory, design decisions, and
   current state are coherent.
6. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py tslgen/tests/test_m148_primitive_call_dependency_closure.py tslgen/tests/test_m149_primitive_call_closure_lowering_package.py tslgen/tests/test_m150_primitive_call_expression.py tslgen/tests/test_m151_primitive_call_consolidation.py tslgen/tests/test_m168_generic_generation_expressions.py tslgen/tests/test_m1685_return_type_bindings.py tslgen/tests/test_m169_selected_specialization_bindings.py tslgen/tests/test_m170_selector_payload_selected_bindings.py
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py tslgen/tests/test_m148_primitive_call_dependency_closure.py tslgen/tests/test_m149_primitive_call_closure_lowering_package.py tslgen/tests/test_m150_primitive_call_expression.py tslgen/tests/test_m151_primitive_call_consolidation.py tslgen/tests/test_m168_generic_generation_expressions.py tslgen/tests/test_m1685_return_type_bindings.py tslgen/tests/test_m169_selected_specialization_bindings.py tslgen/tests/test_m170_selector_payload_selected_bindings.py
find tslgen -type d -name __pycache__ -print
```

Remove validation-created `__pycache__` directories before the final cache
check if any are created.

## Completion Rules

If M170 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M170 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside
this prompt after M170 is accepted. Do not start M171 until the next prompt
explicitly selects it.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 171 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Executor summary.
3. Review/audit verdicts and any follow-ups.
4. Validation commands and exact results.
5. Next active prompt path.
