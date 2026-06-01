# M197 Type-Derived Intrinsic Suffix Translation Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M196 as accepted.

This is an implementation milestone. Use the orchestrated executor-review loop
defined in `PLANS.md` and `AGENTS.md`: one write-capable executor, then
read-only reviewer/auditor subagents, then focused revision only if needed.
The orchestrator owns final state and next-prompt updates.

## Accepted State

Accepted through:

```text
M196: Intrinsic Semantic Modifier Translation Planning
```

Selected milestone:

```text
Milestone 197: Type-Derived Intrinsic Suffix Translation
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
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/backend_intrinsic_handoff.py`
- `tslgen/src/tslgen/lowering/backend_value_queries.py`
- `tslgen/src/tslgen/backends/intrinsic_modifiers.py`
- `tslgen/src/tslgen/backends/type_spelling.py`
- `tslgen/src/tslgen/backends/value_translation.py`
- `tslgen/src/tslgen/domain/backend_metadata.py`
- `tslgen/src/tslgen/domain/catalog.py`
- `tslgen/src/tslgen/pipeline/backend_metadata.py`
- `tslgen/src/tslgen/pipeline/extension_catalog.py`
- `tslgen/tests/test_m195_literal_intrinsic_modifier_translation.py`
- `tslgen/tests/test_m143_1_extension_catalog.py`
- `tslgen/tests/test_m190_backend_metadata_catalog.py`
- `tsldata/extensions/extension.tsl`
- `tsldata/detail/lang/translate_cpp.tsl`
- `tsldata/detail/lang/translate_rust.tsl`
- `tsldata/primitives/**/*.tsl` as corpus evidence only

## Goal

Translate the M196-selected type-derived intrinsic suffix family from typed
lowering IR into typed backend modifier results.

The accepted source form is already lowered before this milestone:

```text
suffix=value<backend>(intrin::suffix(TYPE))
```

where `TYPE` is represented as:

```python
BackendIntrinsicModifierBackendValueOperand(
    request=BackendIntrinsicSuffixValueRequest(
        argument=BackendValueTypeOperand(
            value=LoweredScalarTypeIdentity(...),
            ...
        ),
        ...
    ),
    ...
)
```

This milestone must not parse the source text again. It should consume the
typed handoff values, selected extension context, typed extension metadata, and
typed backend metadata/rule input.

## Executor Scope

- Add exact backend metadata entries for type-derived intrinsic suffix
  fragments in the active C++ and Rust translation metadata. The entries
  should cover the selected style/type-tag combinations:
  - x86: `si8 -> epi8`, `si16 -> epi16`, `si32 -> epi32`,
    `si64 -> epi64`, `ui8 -> epu8`, `ui16 -> epu16`,
    `ui32 -> epu32`, `ui64 -> epu64`, `f32 -> ps`, `f64 -> pd`;
  - arm: `si8 -> s8`, `si16 -> s16`, `si32 -> s32`, `si64 -> s64`,
    `ui8 -> u8`, `ui16 -> u16`, `ui32 -> u32`, `ui64 -> u64`,
    `f32 -> f32`, `f64 -> f64`.
- Add typed suffix metadata/rule records in backend code that map
  `(intrinsic_style, type_tag)` to exact backend metadata keys. A typed rule
  table of metadata keys is acceptable; suffix fragment values themselves
  must come from typed backend metadata, not from a hidden Python value map.
- Consume only `BackendIntrinsicModifierField` values with:
  - `name == "suffix"`;
  - `value` as `BackendIntrinsicModifierBackendValueOperand`;
  - request as `BackendIntrinsicSuffixValueRequest`;
  - request argument as `BackendValueTypeOperand`;
  - argument value as `LoweredScalarTypeIdentity`.
- Resolve the selected extension's `intrinsic_style` through the accepted
  `ExtensionCatalog`.
- Return `BackendTranslatedIntrinsicModifier` values with
  `BackendIntrinsicLiteralFragment` suffix fragments, preserving
  field/request/metadata provenance and modifier order in any batch helper.
- Keep the implementation shaped as the reusable typed modifier translation
  pattern for later family-specific milestones: exact typed field matching,
  typed rule/metadata lookup, typed translated modifier results, stable
  diagnostics, and no renderer-side semantic decisions. This pattern must not
  broaden M197 into prefix, infix, intrinsic-name assembly, or rendering.
- Keep M195 literal translation behavior intact. The new semantic suffix
  translator may be a focused helper or an extension of the existing intrinsic
  modifier translation module, but it must not make literal translation depend
  on metadata.
- Add focused tests in
  `tslgen/tests/test_m197_type_derived_intrinsic_suffix_translation.py`.

## Required Diagnostics

Add stable diagnostics with codes and source locations for:

- missing backend metadata catalog;
- unsupported backend id;
- selected extension missing from the extension catalog;
- selected extension missing `intrinsic_style`;
- unsupported intrinsic style;
- unsupported type tag for the selected style;
- missing backend metadata entry for the typed suffix fragment key;
- metadata entries with unresolved placeholders if the active metadata loader
  exposes them as template text;
- unsupported modifier field or operand when the M197 helper is given
  no-argument, string-argument, symbol-argument, prefix, infix, symbol
  immediate, or direct intrinsic forms.

Diagnostics must not repair source, infer suffixes from raw text, or pass
unsupported backend-value operands through as text.

## Required Tests

Positive tests:

- translate x86 signed integer, unsigned integer, and floating type-derived
  suffixes through active C++ metadata;
- translate arm signed integer, unsigned integer, and floating type-derived
  suffixes through active C++ metadata;
- translate at least one x86 and one arm suffix through active Rust metadata
  when the metadata entry exists;
- preserve modifier order and field/request/metadata provenance in a batch
  helper if one is introduced;
- prove direct `type<generation>(...)` source text is not parsed by the
  backend translator by constructing typed requests directly.

Negative tests:

- diagnose missing backend metadata;
- diagnose unsupported backend;
- diagnose unknown selected extension;
- diagnose missing `intrinsic_style`;
- diagnose unsupported intrinsic style, such as `generic` or `scalar`;
- diagnose unsupported type tags;
- diagnose missing suffix metadata key;
- keep no-argument suffix requests unsupported;
- keep `intrin::suffix("stream")` unsupported;
- keep `intrin::suffix(ToBase)` and `intrin::suffix(si?)` unsupported;
- keep `prefix=value<backend>(intrin::prefix)` unsupported;
- keep backend-value `infix=value<backend>(intrin::suffix...)` unsupported;
- keep `infix=to_type_suffix` and symbol immediates unsupported.

Corpus characterization:

- scan `tsldata/primitives/**/*.tsl` through the accepted M182/M195 discovery
  and classification path;
- assert the current type-derived suffix family remains 181 modifier fields;
- assert the M197 translator can translate representative typed x86 and arm
  type-derived suffix requests from that family when supplied with explicit
  selected context, extension catalog, and backend metadata;
- assert all other M195 unsupported families remain named unsupported
  families, not accidental successes.
- assert the public helper shape is suitable for future prefix/infix modifier
  translators without implementing those families in M197.

## Out Of Scope

- Intrinsic name assembly.
- Rendering.
- Direct `intrin<...>(...)` name parsing.
- Intrinsic argument payload parsing.
- No-argument suffix resolution.
- `intrin::suffix("stream")` resolution.
- `intrin::suffix(ToBase)` resolution.
- Wildcard-looking `intrin::suffix(si?)` resolution.
- Prefix resolution.
- Backend-value infix suffix resolution.
- `infix=to_type_suffix` semantics.
- Symbol immediate resolution.
- M192 scalar type spelling changes.
- M193 value translation changes except preserving its unsupported boundary.
- Arbitrary backend metadata template formatting.
- Source repair.
- Dependency closure.
- Generated-project changes.
- Lowering changes. If the accepted M182/M181 typed handoff proves
  insufficient, stop and return to planner instead of changing lowering.
- Runtime dependency on `frozen/` or `tslgenold`.

## Required Review Subagents

After the executor finishes and validation has been run, use read-only
subagents:

1. Architecture/boundary reviewer: verify typed backend translation boundaries,
   no renderer/template semantics, no raw source parsing, no intrinsic-name
   assembly, no suffix-value hardcoding, and no lowering drift.
2. Evidence auditor: compare supported and unsupported families against the
   M196 inventory and representative `tsldata/primitives/**/*.tsl` cases.
3. Validation auditor: inspect test coverage and validation output.
4. Documentation auditor: verify roadmap/state/next prompt updates accurately
   record the result and follow-ups.

If reviewers return `Needs Revision`, use one focused write-capable revision
executor for the named issues and then run focused re-review. If reviewers
return `Return To Planner` or `Reject`, stop implementation and create the
appropriate planner/rollback prompt.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m197_type_derived_intrinsic_suffix_translation.py
find tslgen -type d -name __pycache__ -print
```

Remove validation-created `__pycache__` directories before final validation
reporting if any appear.

## Completion Rules

Before finishing an accepted M197 run:

- update `docs/redesign/implementation-roadmap.md` with the M197 result and
  selected next milestone;
- update redesign docs if implementation clarifies behavior, decisions, or
  open questions;
- update `docs/agent/current-redesign-state.md`;
- create the next concrete prompt under `docs/agent/runs/`;
- report exact validation results.

## Stop Rule

Do not start Milestone 198. Do not implement no-argument/string/symbol suffix
rules, prefix rules, semantic infix rules, symbol immediate resolution,
intrinsic-name assembly, rendering, dependency closure, or lowering code in
this milestone.

## Final Report

Report:

1. M197 review verdict.
2. Implemented files and docs changed.
3. Boundary decisions preserved.
4. Validation commands with exact results.
5. Review/audit verdicts.
6. Next active prompt path.
