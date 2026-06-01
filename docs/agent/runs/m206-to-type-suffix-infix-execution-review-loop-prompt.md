# M206 To-Type Suffix Infix Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M205 as accepted.

This is an implementation milestone. Use the executor-review loop: one
write-capable executor, then read-only reviewer/auditor subagents, then one
focused revision executor only if the consolidated verdict is `Needs
Revision`. The orchestrator owns final state and next-prompt updates.

## Accepted State

Accepted through:

```text
M205: Post-Destination Intrinsic Modifier Planning
```

Selected milestone:

```text
Milestone 206: To-Type Suffix Infix Marker Translation
```

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/domain-model.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/flaws-to-fix.md`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/backend_intrinsic_handoff.py`
- `tslgen/src/tslgen/lowering/backend_value_queries.py`
- `tslgen/src/tslgen/lowering/selected_specializations.py`
- `tslgen/src/tslgen/backends/intrinsic_modifiers.py`
- `tslgen/src/tslgen/backends/_intrinsic_metadata_modifiers.py`
- `tslgen/tests/test_m195_literal_intrinsic_modifier_translation.py`
- `tslgen/tests/test_m197_type_derived_intrinsic_suffix_translation.py`
- `tslgen/tests/test_m198_intrinsic_prefix_modifier_translation.py`
- `tslgen/tests/test_m200_current_type_intrinsic_suffix_translation.py`
- `tslgen/tests/test_m202_stream_intrinsic_suffix_translation.py`
- `tslgen/tests/test_m204_destination_return_type_intrinsic_suffix_translation.py`
- `tsldata/primitives/conversion/cast.tsl`

## Goal

Lower and translate the exact intrinsic compose marker:

```text
infix=to_type_suffix
```

through selected destination/return-type context. The marker must not become a
backend magic string, and backend translation must not infer semantics from raw
`BackendIntrinsicModifierSymbolOperand("to_type_suffix")`. FTF-003 records
this marker as legacy shorthand/source-convention debt; M206 is a bounded
compatibility bridge, not a preferred new syntax.

## Executor Scope

- Add focused tests, preferably in a new
  `tslgen/tests/test_m206_to_type_suffix_infix_translation.py`.
- Accept only the exact modifier field/value shape `infix=to_type_suffix`.
- Require selected context with:
  - a primitive-local `return_type: base: NAME` declaration;
  - a matching `TargetReturnTypeBaseBinding(name=NAME, type_tag=...)`.
- Use arbitrary binding names such as `ResultBase` in tests to prove the rule
  does not special-case `ToBase`.
- Lower the marker into typed destination-type suffix information before
  backend modifier translation. The selected destination scalar type should
  reuse the existing metadata-backed type-suffix rule path for C++ and Rust.
- Preserve the source field name as `infix`; intrinsic-name assembly remains a
  later renderer/call-translation problem.
- Preserve useful source provenance for diagnostics. Do not fake a
  `value<backend>(...)` island if the existing operand shape cannot represent
  the exact marker honestly. If a new value is needed, add only the smallest
  named semantic modifier fact/operand for this selected destination-type
  suffix marker; do not introduce a new broad request/result family,
  dispatcher, inventory, worklist, or parser layer.
- Add corpus/evidence coverage that finds all four currently observed
  `infix=to_type_suffix` occurrences in
  `tsldata/primitives/conversion/cast.tsl` and verifies the assumption is
  still exact.
- Preserve existing behavior for M195 literal modifiers, M197 type-derived
  suffixes, M198 prefixes, M200 current-type suffixes, M202 stream suffixes,
  and M204 explicit destination/return-type suffix operands.
- Update redesign docs only where behavior or decisions become accepted by the
  implementation.

## Required Negative Coverage

- Without a primitive-local `return_type: base: NAME` declaration, the exact
  marker is not translated and produces a deterministic diagnostic.
- With a declaration but no matching selected return-type base binding, the
  marker is not translated and produces a selected-binding diagnostic.
- A mismatched selected binding name or wrong return-type binding kind remains
  a selected-binding diagnostic.
- Raw `BackendIntrinsicModifierSymbolOperand("to_type_suffix")` is not
  translated by backend modifier logic.
- `infix=value<backend>(intrin::suffix(ResultBase))` from M204 still works and
  remains distinct from the exact marker.
- `immediate(1)=index` and `immediate(1)=Index` remain unsupported symbol
  immediates.
- FTF-002 `intrin::suffix(si?)` remains unsupported source-data debt.
- FTF-003 remains a source-convention flaw: the implementation may support the
  exact marker for compatibility, but must not generalize the shorthand.

## Corpus Expectations

Context-free corpus accounting may still leave raw `ToBase` symbol suffixes
untranslated when no selected binding context is supplied. Do not force
corpus-wide counts to change by treating source-owned names as magic.

M206 should prove the selected-context behavior for `infix=to_type_suffix` on
focused fixtures and should keep the corpus evidence check limited to the
exact four observed marker occurrences.

## Out Of Scope

- Treating `to_type_suffix`, `ToBase`, `index`, or `Index` as magic raw
  strings.
- Symbol immediate resolution.
- Selected generic/immediate-parameter modeling.
- Broad TSIL or target-language parsing.
- Intrinsic-name assembly.
- Rust `core::arch::*` qualification.
- Rendering, generated output, artifact writing, or build verification.
- Dependency closure.
- Source repair.
- FTF-002 `intrin::suffix(si?)`.
- Runtime dependency on `frozen/` or `tslgenold`.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m206_to_type_suffix_infix_translation.py
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m195_literal_intrinsic_modifier_translation.py tslgen/tests/test_m197_type_derived_intrinsic_suffix_translation.py tslgen/tests/test_m198_intrinsic_prefix_modifier_translation.py tslgen/tests/test_m200_current_type_intrinsic_suffix_translation.py tslgen/tests/test_m202_stream_intrinsic_suffix_translation.py tslgen/tests/test_m204_destination_return_type_intrinsic_suffix_translation.py tslgen/tests/test_m206_to_type_suffix_infix_translation.py
find tslgen -type d -name __pycache__ -print
```

Remove validation-created `__pycache__` directories before final validation
reporting if any appear.

## Review Requirements

Use `docs/agent/review-checklist.md`.

Reviewers must verify:

- The implementation lowers `infix=to_type_suffix` through selected
  return-type base context before backend translation.
- `to_type_suffix` is not interpreted as a raw backend string or direct
  literal fragment.
- Arbitrary binding-name fixtures prove source ownership.
- Any new typed value belongs to a stable semantic category and does not create
  a new broad request/result family.
- Metadata text remains in active C++/Rust backend metadata; Python maps typed
  rule inputs to metadata keys.
- M195/M197/M198/M200/M202/M204 behavior and diagnostics remain stable.
- No renderer, intrinsic-name assembly, source repair, dependency closure, or
  `frozen`/`tslgenold` runtime dependency is introduced.

## Final State Update

Before finishing an accepted run, update
`docs/agent/current-redesign-state.md`, update
`docs/redesign/implementation-roadmap.md` with the M206 result, and create the
next concrete prompt under `docs/agent/runs/` according to
`docs/agent/next-run-prompt-protocol.md`, unless review records an explicit
stop condition.

## Final Report

Report:

1. Executor/review verdict.
2. What M206 changed.
3. Files changed.
4. Validation commands with exact results.
5. Next active prompt path or stop condition.
