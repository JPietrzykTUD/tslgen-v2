# M169 Execution Review Loop Prompt

This is the planned follow-on prompt after M168.5. Execute it only when
`docs/agent/current-redesign-state.md` points here and records M168.5 as
accepted.

You are executing and reviewing the accepted next milestone after M168.5:

```text
Milestone 169: Exact Selected Specialization Binding Boundary
```

Milestones 1 through 168.5 are accepted. M168 added exact
`generic::length(TYPE_EXPR)` and fixed-vector
`generic::runtime_length(TYPE_EXPR)` generation-expression lowering. M168.5
added primitive-local optional `return_type` binding declarations with
arbitrary source-defined names. Generic expressions can become concrete only
when `TYPE_EXPR` lowers to a concrete fixed vector, and current corpus aliases
often flow through selected specialization symbols declared by the primitive,
such as `ToBase` or `ToExtension`.

M169 is an implementation milestone. It should add the next lowering boundary
for resolving specialization symbols from explicit selected-target facts. It
must not parse or infer the full `.tsl` implementation selector tree.

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
- `docs/redesign/tsil-surface-inventory.md`
- `docs/redesign/missing-lowering-inventory.md`
- `tslgen/src/tslgen/analysis/selection.py`
- `tslgen/src/tslgen/domain/catalog.py`
- `tslgen/src/tslgen/syntax/ast.py`
- `tslgen/src/tslgen/syntax/parser.py`
- `tslgen/src/tslgen/pipeline/catalog_builder.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/type_queries.py`
- `tslgen/src/tslgen/lowering/selector_payload.py`
- `tslgen/src/tslgen/lowering/primitive_calls.py`
- `tslgen/src/tslgen/lowering/generation_generic.py`
- `tslgen/src/tslgen/lowering/generation_values.py`
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`
- `tslgen/tests/test_m1685_return_type_bindings.py`
- `tslgen/tests/test_m144_selector_payload.py`
- `tslgen/tests/test_m145_primitive_call_target_matching.py`
- `tslgen/tests/test_m168_generic_generation_expressions.py`

## Goal

Add explicit selected-specialization bindings to the type-lowering context so
primitive-declared specialization symbols can resolve to concrete typed facts
when the selected target supplies those facts.

Selected examples from current corpus:

```text
return_type base identifier       -> scalar/base type tag, such as f64
return_type extension identifier  -> extension name, such as sse
ToType-style derived value        -> concrete vector/type value, if needed by
                                     observed type queries
```

This should make type aliases such as these lowerable when explicit bindings
are present:

```text
let<type>(OutVec, type<generation>(vector::transform_extension(ToBase)))
let<type>(OutVec, type<generation>(vector::as_extension(ToExtension)))
```

M169 is not responsible for discovering all specialization manifestations from
the full source corpus. It creates the typed selected-value boundary that
future selector/catalog work can populate from M168.5 declarations and selected
implementation facts.

## Required Executor Task

Run exactly one write-capable executor for M169. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Inventory specialization symbol evidence across all `tsldata/**/*.tsl`.
   Classify at least:
   - primitive-declared return-type base symbols such as `ToBase`;
   - local type-alias symbols such as `UBase`;
   - vector/type symbols such as `ToType`;
   - primitive-declared return-type extension symbols such as `ToExtension`;
   - whether symbols appear in `return_type`, implementation-selector
     branches, `let<type>(...)`, `type<generation>(...)`,
     `type<backend>(...)`, `call<primitive=...>` selectors, or backend
     value/intrinsic payloads.
3. Add the smallest typed selected-specialization binding model needed by
   lowering. Prefer explicit domain/value objects over dictionaries past the
   boundary. Do not overload primitive attributes, stringly alias names, or
   body text.
   Bindings must be validated against the primitive-local declarations from
   M168.5 where the binding represents a declared return-type base or
   extension symbol.
4. Decide the narrow owner for supplied bindings. A small extension to
   `Target` / `SelectedImplementationLoweringContext` is acceptable if it
   keeps selection facts explicit and deterministic. Do not add a broad
   selector engine or manifest registry.
5. Extend type-expression lowering so a bound specialization symbol resolves
   through explicit selected facts before becoming
   `LoweredSpecializationTypeSymbol` or an unbound-alias diagnostic.
6. Support concrete scalar/base type bindings and concrete extension bindings.
   Support concrete vector/type bindings only if they are needed for observed
   `ToType`-style lowering and can reuse existing `LoweredTypeValue` shapes.
7. Ensure `vector::transform_extension(ToBase)` and
   `vector::as_extension(ToExtension)` can lower through aliases and can feed
   M168 `generic::length(...)` when fixed extension/type metadata exists.
8. Preserve existing behavior for unbound symbols: if no explicit binding is
   supplied, current M143/M168 unresolved-symbol or unbound-alias diagnostics
   remain deterministic.
9. Preserve M143, M144-M151, and M168 accepted behavior and diagnostics.
10. Add focused tests for:
    - positive scalar/base binding resolving a specialization symbol in a type
      expression;
    - positive extension binding resolving a specialization symbol in
      `vector::as_extension(...)`;
    - positive alias plus `generic::length(...)` using a bound `ToBase`;
    - positive alias plus `generic::length(...)` using a bound `ToExtension`;
    - unresolved/unbound symbol behavior when no binding is supplied;
    - wrong binding kind or malformed binding diagnostics, if the public model
      can represent invalid input;
    - deterministic ordering and equality of bindings/results;
    - preservation of existing M143, M144-M151, and M168 tests.
11. Update docs that describe the accepted M169 behavior and any newly
    discovered boundary details.
12. Leave final accepted-state updates to the orchestrator after read-only
    review returns `Accept` or `Accept With Follow-Ups`.

## Design Guardrails

- This is selected-context type/generation lowering, not full source selector
  parsing.
- Return-type binding names come from M168.5 primitive declarations and are
  arbitrary user-defined identifiers.
- Specialization resolution must come from explicit typed selected facts, not
  from raw name guesses such as "anything named ToBase is f64".
- Do not infer specialization values from raw body text, test names,
  backend helper payloads, intrinsic names, or surrounding assignment/loop
  syntax.
- Do not use primitive attributes as a hidden carrier for type or extension
  specialization values.
- Do not expand wildcards or enumerate all specialization manifestations from
  `.tsl` implementation trees in this milestone.
- Do not add a general expression parser, statement parser, source repair
  mechanism, dependency scheduler, broad registry, dispatcher, worklist,
  callback map, hidden backfeed, or fixpoint mechanism.

## Must Preserve

- M143 complete observed type lowering and ordered `let<type>(...)` alias
  visibility.
- M144 selector payload lowering behavior, including current unresolved
  specialization-symbol handling.
- M145-M151 primitive-call target matching, argument binding, inventory,
  dependency closure, expression, and consolidation behavior.
- M155-M168 generation-value, generation-expression, control, loop,
  declaration, backend query/control, intrinsic, source-operation, and
  primitive-call behavior.
- M168.5 primitive-local return-type binding declarations, including absent
  declaration behavior and arbitrary source-defined binding names.
- Existing diagnostics for unbound aliases, unsupported type expressions,
  unresolved generic vector types, missing generic vector metadata, and
  unsupported generic operations.

## Out Of Scope

Full `.tsl` implementation selector parsing; wildcard expansion; producing a
complete catalog of every specialization manifestation; automatic target
selection for `ToBase`/`ToExtension`; dependency closure changes; primitive
call rendering; backend value/control/intrinsic/source-operation translation;
loop execution or unrolling; branch selection changes; declaration rendering;
source replacement; backend rendering; type inference; arbitrary expression or
statement parsing; source repair; output writing; runtime `tsldata`,
`frozen`, or `tslgenold` dependencies; broad registries, dispatchers,
worklists, callback maps, hidden backfeeds, or fixpoint machinery.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M169 adds a small explicit selected
   specialization binding boundary and avoids broad selector parsing,
   wildcard expansion, registry/dispatcher/worklist machinery, raw-name
   inference, and renderer pressure.
2. Boundary auditor: verify M143, M144-M151, and M168 behavior remains intact
   and unbound symbols keep deterministic existing diagnostics.
3. Evidence auditor: verify the selected symbol classes and examples are
   grounded in current `tsldata/**/*.tsl` evidence without treating evidence
   as a full parser contract.
4. Test auditor: verify tests cover positive bound scalar/base and extension
   cases, M168 alias/generic-length integration, unbound behavior, invalid
   bindings where applicable, determinism, and preservation suites.
5. Documentation auditor: verify roadmap, behavioral/domain docs,
   generation/type inventories, missing inventory, and current state are
   coherent.
6. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py tslgen/tests/test_m148_primitive_call_dependency_closure.py tslgen/tests/test_m149_primitive_call_closure_lowering_package.py tslgen/tests/test_m150_primitive_call_expression.py tslgen/tests/test_m151_primitive_call_consolidation.py tslgen/tests/test_m168_generic_generation_expressions.py tslgen/tests/test_m1685_return_type_bindings.py
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py tslgen/tests/test_m148_primitive_call_dependency_closure.py tslgen/tests/test_m149_primitive_call_closure_lowering_package.py tslgen/tests/test_m150_primitive_call_expression.py tslgen/tests/test_m151_primitive_call_consolidation.py tslgen/tests/test_m168_generic_generation_expressions.py tslgen/tests/test_m1685_return_type_bindings.py
find tslgen -type d -name __pycache__ -print
```

If the executor adds focused M169 test files, include them in the compileall
and targeted pytest commands. Remove validation-created `__pycache__`
directories before the final cache check if any are created.

## Completion Rules

If M169 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M169 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside
this prompt after M169 is accepted. Do not start M170 until the next prompt
explicitly selects it.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 170 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Executor summary.
3. Review/audit verdicts and any follow-ups.
4. Validation commands and exact results.
5. Next active prompt path.
