# M200 Current-Type Intrinsic Suffix Translation Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M199 as accepted.

This is an execution milestone. Use the executor-review loop from `PLANS.md`:
one write-capable executor, then read-only reviewer/auditor subagents, then a
focused revision executor only if review returns `Needs Revision`. The
orchestrator owns final verdict consolidation, state updates, and next-prompt
creation.

## Accepted State

Accepted through:

```text
M199: Post-Prefix Intrinsic Modifier Planning
```

Selected milestone:

```text
Milestone 200: Current-Type Intrinsic Suffix Translation
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
- `tslgen/src/tslgen/backends/intrinsic_modifiers.py`
- `tslgen/src/tslgen/backends/_intrinsic_metadata_modifiers.py`
- `tslgen/src/tslgen/backends/__init__.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/backend_intrinsic_handoff.py`
- `tslgen/src/tslgen/lowering/backend_value_queries.py`
- `tslgen/tests/test_m195_literal_intrinsic_modifier_translation.py`
- `tslgen/tests/test_m197_type_derived_intrinsic_suffix_translation.py`
- `tslgen/tests/test_m198_intrinsic_prefix_modifier_translation.py`
- `tsldata/detail/lang/translate_cpp.tsl`
- `tsldata/detail/lang/translate_rust.tsl`
- `tsldata/extensions/extension.tsl`
- representative `tsldata/primitives/**/*.tsl` occurrences from the M199
  inventory

## Goal

Translate no-argument `intrin::suffix` backend modifier requests as suffix
fragments for the current selected implementation type.

The executable slice consumes accepted M182/M181 typed handoff values for:

```text
suffix=value<backend>(intrin::suffix)
infix=value<backend>(intrin::suffix)
```

The missing suffix argument means the selected current implementation
`TypeTag`, per ADR-057. The selected extension's `intrinsic_style` and active
backend metadata still determine the emitted suffix fragment.

## Scope

- Extend `BackendIntrinsicModifierTranslationContext` with an explicit typed
  selected/current `TypeTag`.
- Update all construction sites and tests for that context deliberately.
- Translate `BackendIntrinsicModifierField` values whose field name is
  `suffix` or `infix` and whose value carries
  `BackendIntrinsicSuffixValueRequest(argument=None)`.
- Reuse the existing metadata-backed type suffix machinery and active C++/Rust
  metadata entries. Python may contain typed rule records for metadata keys,
  but suffix fragment text must come from backend metadata.
- Preserve the output field name: a `suffix` field produces a translated
  `suffix` modifier, and an `infix` field produces a translated `infix`
  modifier. Do not assemble final intrinsic names.
- Preserve modifier order plus field/request/metadata provenance.
- Preserve accepted M195 literal translation, M197 type-derived suffix
  translation, and M198 prefix translation behavior.
- Keep the M198 shared metadata-backed evaluator shape small. A tiny refactor
  is allowed if it avoids duplicating suffix resolution, but do not introduce a
  broad registry, dispatcher, worklist, or new request/result family.
- Add focused tests for:
  - C++ no-argument suffix-as-suffix;
  - Rust no-argument suffix-as-suffix;
  - no-argument suffix-as-infix;
  - x86 and arm intrinsic styles;
  - selected/current type tag provenance through metadata keys;
  - missing metadata and missing metadata-entry diagnostics;
  - unsupported selected type or intrinsic style diagnostics;
  - no source-text parsing of the surrounding intrinsic;
  - corpus characterization showing 38 `suffix` no-argument requests and
    3 `infix` no-argument requests newly translate after M200.

## Required Corpus Accounting

Using the same accepted discovery/lowering path as M195-M198, characterize
`tsldata/primitives/**/*.tsl` after M200:

```text
643 total modifier fields
566 translated after M200:
  335 literal modifiers
  181 type-derived suffix modifiers
  9 prefix modifiers
  41 current-type no-argument suffix modifiers

77 still unsupported:
  21 suffix=value<backend>(intrin::suffix("stream"))
  20 suffix=value<backend>(intrin::suffix(SYMBOL))
     - 19 actionable ToBase cases
     - 1 FTF-002 intrin::suffix(si?) source-data flaw
  13 infix=value<backend>(intrin::suffix(ToBase))
  4  infix=to_type_suffix
  19 immediate(N)=symbol
```

If implementation evidence changes these counts, stop and explain whether the
source corpus changed, a matcher bug was found, or M199's inventory was wrong.

## Out Of Scope

- String suffixes such as `intrin::suffix("stream")`.
- Symbol suffixes such as `intrin::suffix(ToBase)`.
- FTF-002 `intrin::suffix(si?)`.
- Destination, return-type, or alias binding.
- `infix=to_type_suffix`.
- Symbol immediate resolution.
- Intrinsic-name assembly.
- Rendering or generated output.
- Rust `core::arch::*` qualification.
- Import-based Rust intrinsic rendering.
- Direct `intrin<...>(...)` parsing.
- Intrinsic argument payload parsing.
- Dependency closure.
- Source repair.
- Broad TSIL or target-language parsing.
- Lowering changes. If accepted typed handoff values cannot represent this
  family, stop and return to planner.
- Runtime dependency on `frozen/` or `tslgenold`.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m200_current_type_intrinsic_suffix_translation.py
find tslgen -type d -name __pycache__ -print
```

Remove validation-created `__pycache__` directories before final validation
reporting if any appear.

## Review Packet

After implementation and validation, provide reviewers:

- changed files;
- the accepted current-type binding rule and where it is encoded;
- corpus accounting before/after M200;
- diagnostics added or reused;
- confirmation that M195/M197/M198 behavior remains covered;
- confirmation that no renderer, source repair, dependency closure, or Rust
  module qualification work was added.

## Reviewer Focus

Reviewers must use `docs/agent/review-checklist.md` and focus on:

- whether M200 consumes typed handoff/context values rather than raw source;
- whether adding selected/current `TypeTag` to modifier context is the minimum
  needed context change;
- whether suffix fragment text still comes from backend metadata;
- whether `suffix` and `infix` field placement remains a typed modifier fact
  rather than intrinsic-name assembly;
- whether FTF-002 remains unsupported;
- whether remaining families stay explicitly unsupported;
- whether tests prove corpus counts and diagnostics.

## Next Prompt Requirement

Before finishing, update `docs/agent/current-redesign-state.md` and create the
next concrete prompt under `docs/agent/runs/`, unless the accepted review
records an explicit stop condition.
