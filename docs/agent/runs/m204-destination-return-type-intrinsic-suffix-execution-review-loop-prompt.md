# M204 Destination Return-Type Intrinsic Suffix Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M203 as accepted.

This is an implementation milestone. Use the executor-review loop: one
write-capable executor, then read-only reviewer/auditor subagents, then one
focused revision executor only if the consolidated verdict is `Needs
Revision`. The orchestrator owns final state and next-prompt updates.

## Accepted State

Accepted through:

```text
M203: Post-Stream Intrinsic Modifier Planning
```

Selected milestone:

```text
Milestone 204: Destination Return-Type Intrinsic Suffix Translation
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
- `tslgen/src/tslgen/lowering/backend_value_queries.py`
- `tslgen/src/tslgen/lowering/backend_intrinsic_handoff.py`
- `tslgen/src/tslgen/lowering/selected_specializations.py`
- `tslgen/src/tslgen/backends/intrinsic_modifiers.py`
- `tslgen/src/tslgen/backends/_intrinsic_metadata_modifiers.py`
- `tslgen/tests/test_m197_type_derived_intrinsic_suffix_translation.py`
- `tslgen/tests/test_m198_intrinsic_prefix_modifier_translation.py`
- `tslgen/tests/test_m200_current_type_intrinsic_suffix_translation.py`
- `tslgen/tests/test_m202_stream_intrinsic_suffix_translation.py`

## Goal

Translate destination/return-type intrinsic suffix operands only when a
source-owned return-type base symbol has already lowered through typed selected
binding context to a scalar type identity.

This milestone is deliberately a lowering/context-driven slice. It must prove
that arbitrary primitive-local binding names flow through selected-binding
lowering into the existing backend modifier handoff before backend translation
uses them.

## Executor Scope

- Add focused tests, preferably in a new
  `tslgen/tests/test_m204_destination_return_type_intrinsic_suffix_translation.py`.
- Build fixtures with arbitrary return-type names such as `ResultBase`, not
  only `ToBase`.
- In fixtures, define a primitive-local return-type declaration equivalent to
  `return_type: base: ResultBase` and select a target with
  `TargetReturnTypeBaseBinding(name="ResultBase", type_tag=...)`.
- Exercise the accepted discovery/lowering path for exact backend intrinsic
  modifier fields:

```text
suffix=value<backend>(intrin::suffix(ResultBase))
infix=value<backend>(intrin::suffix(ResultBase))
```

- Assert that, with the selected binding environment, these payloads lower to
  `BackendValueTypeOperand(LoweredScalarTypeIdentity(...))`, not
  `BackendValueSymbolOperand`.
- Translate the typed suffix operands through the existing metadata-backed
  type-suffix rule path for C++ and Rust. Fragment text must come from active
  backend metadata, as in M197/M200/M202.
- Add only the narrow missing typed `infix` suffix support needed for
  `infix=value<backend>(intrin::suffix(ResultBase))`. The field name must still
  be preserved as `infix`; intrinsic-name assembly remains later.
- Preserve M195 literal modifier translation, M197 type-derived suffix
  translation, M198 prefix translation, M200 current-type suffix translation,
  and M202 stream named suffix translation.
- Update redesign docs only where behavior or decisions become accepted by the
  implementation.

## Required Negative Coverage

- An unbound arbitrary symbol such as `ResultBase` remains a
  `BackendValueSymbolOperand` and is not translated by backend modifier logic.
- A selected return-type binding without a matching primitive-local
  declaration, or with the wrong kind/name, produces the existing selected
  binding diagnostic rather than a raw-symbol translation.
- Raw `BackendValueSymbolOperand("ToBase")` is still unsupported.
- `infix=to_type_suffix` remains unsupported.
- FTF-002 `intrin::suffix(si?)` remains unsupported source-data debt.
- Symbol immediates such as `immediate(1)=index` and `immediate(1)=Index`
  remain unsupported.

## Corpus Expectations

The context-free M202 corpus characterization may still report the same 56
unsupported fields because it intentionally uses a fixture without selected
return-type bindings. Do not force the corpus-wide count to change by treating
`ToBase` as magic.

Add focused corpus/evidence tests only when they supply a selected context that
matches the observed primitive return-type declaration. If a broad corpus
selection context would be needed, keep that for a later planner milestone.

## Out Of Scope

- Treating `ToBase` as a magic string.
- Translating raw `BackendValueSymbolOperand` values.
- Deriving return-type values from nested `.tsl` implementation selector
  structure.
- Wildcard expansion or specialization-tree selection.
- Broad TSIL or target-language parsing.
- `infix=to_type_suffix`.
- Symbol immediate resolution for `index` or `Index`.
- FTF-002 `intrin::suffix(si?)`.
- Intrinsic-name assembly.
- Rust `core::arch::*` qualification.
- Rendering, generated output, artifact writing, or build verification.
- Dependency closure.
- Source repair.
- Runtime dependency on `frozen/` or `tslgenold`.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m204_destination_return_type_intrinsic_suffix_translation.py
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m197_type_derived_intrinsic_suffix_translation.py tslgen/tests/test_m198_intrinsic_prefix_modifier_translation.py tslgen/tests/test_m200_current_type_intrinsic_suffix_translation.py tslgen/tests/test_m202_stream_intrinsic_suffix_translation.py tslgen/tests/test_m204_destination_return_type_intrinsic_suffix_translation.py
find tslgen -type d -name __pycache__ -print
```

Remove validation-created `__pycache__` directories before final validation
reporting if any appear.

## Review Requirements

Use `docs/agent/review-checklist.md`.

Reviewers must verify:

- The implementation relies on typed selected-binding lowering, not raw
  spelling checks for `ToBase`.
- Arbitrary binding-name fixtures prove source ownership.
- Typed `infix` suffix support reuses the metadata-backed type-suffix rule
  path and preserves field identity.
- Metadata text remains in active C++/Rust backend metadata; Python only maps
  typed rule inputs to metadata keys.
- M195/M197/M198/M200/M202 behavior and diagnostics remain stable.
- No renderer, intrinsic-name assembly, source repair, dependency closure, or
  `frozen`/`tslgenold` runtime dependency is introduced.

## Final State Update

Before finishing an accepted run, update
`docs/agent/current-redesign-state.md`, update
`docs/redesign/implementation-roadmap.md` with the M204 result, and create the
next concrete prompt under `docs/agent/runs/` according to
`docs/agent/next-run-prompt-protocol.md`, unless review records an explicit
stop condition.

## Final Report

Report:

1. Executor/review verdict.
2. What M204 changed.
3. Files changed.
4. Validation commands with exact results.
5. Next active prompt path or stop condition.
