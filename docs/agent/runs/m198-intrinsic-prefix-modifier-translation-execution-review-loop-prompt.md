# M198 Intrinsic Prefix Modifier Translation Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M197 as accepted.

This is an implementation milestone. Use the orchestrated executor-review loop
defined in `PLANS.md` and `AGENTS.md`: one write-capable executor, then
read-only reviewer/auditor subagents, then focused revision only if needed.
The orchestrator owns final state and next-prompt updates.

## Accepted State

Accepted through:

```text
M197: Type-Derived Intrinsic Suffix Translation
```

Selected milestone:

```text
Milestone 198: Intrinsic Prefix Modifier Translation
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
- `tslgen/src/tslgen/backends/intrinsic_modifiers.py`
- `tslgen/src/tslgen/domain/backend_metadata.py`
- `tslgen/src/tslgen/domain/catalog.py`
- `tslgen/src/tslgen/pipeline/backend_metadata.py`
- `tslgen/src/tslgen/pipeline/extension_catalog.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/backend_intrinsic_handoff.py`
- `tslgen/src/tslgen/lowering/backend_value_queries.py`
- `tslgen/tests/test_m195_literal_intrinsic_modifier_translation.py`
- `tslgen/tests/test_m197_type_derived_intrinsic_suffix_translation.py`
- `tsldata/extensions/extension.tsl`
- `tsldata/detail/lang/translate_cpp.tsl`
- `tsldata/detail/lang/translate_rust.tsl`
- `tsldata/primitives/**/*.tsl` as corpus evidence only

## Goal

Translate the observed intrinsic prefix modifier family from typed lowering IR
into typed backend modifier results using the M197 context-aware modifier
translation pattern.

The accepted source form is already lowered before this milestone:

```text
prefix=value<backend>(intrin::prefix)
```

where the modifier operand carries:

```python
BackendIntrinsicModifierBackendValueOperand(
    request=BackendIntrinsicPrefixValueRequest(...),
    ...
)
```

This milestone must not parse source text again. It should consume the typed
handoff field, selected extension context, typed extension metadata, and typed
backend metadata/rule input.

## Executor Scope

- Add exact backend metadata entries for selected intrinsic prefix fragments in
  the active C++ and Rust translation metadata. The selected x86-family
  extension mappings are:
  - `sse -> _mm_`
  - `sse_vl -> _mm_`
  - `avx2 -> _mm256_`
  - `avx2_vl -> _mm256_`
  - `avx512 -> _mm512_`
- Add typed prefix metadata/rule records in backend code that map selected
  extension names to exact backend metadata keys. Prefix fragment values must
  come from typed backend metadata, not from a hidden Python value map.
- Consume only `BackendIntrinsicModifierField` values with:
  - `name == "prefix"`;
  - `value` as `BackendIntrinsicModifierBackendValueOperand`;
  - request as `BackendIntrinsicPrefixValueRequest`.
- Resolve the selected extension through the accepted `ExtensionCatalog`.
- Return existing typed `BackendTranslatedIntrinsicModifier` values with
  `BackendIntrinsicLiteralFragment` prefix fragments, preserving
  field/request/metadata provenance and modifier order.
- Reuse the M197 context-aware helper shape where practical. The result should
  make later infix and string/no-argument suffix milestones easier without
  implementing those families in M198.
- Apply the M197 architecture review follow-up before adding prefix logic:
  `tslgen/src/tslgen/backends/intrinsic_modifiers.py` is already substantial.
  If the prefix implementation would push it toward a catch-all module or over
  the module-size guardrail, split typed rule-family helpers into focused
  private modules while preserving public imports and M195/M197 behavior.
- Keep M195 literal translation and M197 type-derived suffix translation
  behavior intact.
- Add focused tests in
  `tslgen/tests/test_m198_intrinsic_prefix_modifier_translation.py`.

## Required Diagnostics

Add stable diagnostics with codes and source locations for:

- missing backend metadata catalog;
- unsupported backend id;
- selected extension missing from the extension catalog;
- selected extension without a supported prefix rule;
- missing backend metadata entry for the typed prefix fragment key;
- metadata entries with unresolved placeholders;
- unsupported modifier field or operand when the M198 helper is given suffix,
  infix, symbol immediate, direct intrinsic, or literal prefix forms outside
  this selected typed backend-value prefix family.

Diagnostics must not repair source, infer prefixes from raw text, assemble
intrinsic names, or pass unsupported backend-value operands through as text.

## Required Tests

Positive tests:

- translate `prefix=value<backend>(intrin::prefix)` for `sse`, `sse_vl`,
  `avx2`, `avx2_vl`, and `avx512` through active C++ metadata;
- translate at least one selected prefix through active Rust metadata;
- preserve modifier order and metadata provenance when a compose request
  contains both an M197 type-derived suffix and an M198 prefix;
- prove direct source text is not parsed by constructing typed requests
  directly.

Negative tests:

- diagnose missing backend metadata;
- diagnose unsupported backend;
- diagnose unknown selected extension;
- diagnose selected extensions without prefix rules, such as `generic`,
  `scalar`, `neon`, or `sve`;
- diagnose missing prefix metadata key;
- diagnose unresolved placeholders in prefix metadata;
- keep no-argument suffix requests unsupported;
- keep `intrin::suffix("stream")`, `intrin::suffix(ToBase)`, and
  `intrin::suffix(si?)` unsupported;
- keep backend-value `infix=value<backend>(intrin::suffix...)` unsupported;
- keep `infix=to_type_suffix` and symbol immediates unsupported;
- keep direct `intrin<...>(...)` requests opaque.

Corpus characterization:

- scan `tsldata/primitives/**/*.tsl` through the accepted M182/M195/M197
  discovery and classification path;
- assert the current prefix family remains 9 modifier fields;
- assert representative typed prefix requests from that family translate when
  supplied selected x86 extension context, extension catalog, and backend
  metadata;
- assert all other unsupported families remain named unsupported families, not
  accidental successes.

## Out Of Scope

- Intrinsic name assembly.
- Rendering.
- Direct `intrin<...>(...)` name parsing.
- Intrinsic argument payload parsing.
- No-argument suffix resolution.
- `intrin::suffix("stream")` resolution.
- `intrin::suffix(ToBase)` resolution.
- Wildcard-looking `intrin::suffix(si?)` resolution.
- Backend-value infix suffix resolution.
- `infix=to_type_suffix` semantics.
- Symbol immediate resolution.
- M192 scalar type spelling changes.
- M193 value translation changes except preserving its unsupported boundary.
- M197 type-derived suffix behavior changes except shared helper reuse.
- Source repair.
- Dependency closure.
- Generated-project changes.
- Lowering changes. If the accepted M182/M181 typed handoff proves
  insufficient, stop and return to planner instead of changing lowering.
- Runtime dependency on `frozen/` or `tslgenold`.

## Required Review Subagents

After the executor finishes and validation has been run, use read-only
subagents:

1. Architecture/boundary reviewer: verify typed backend translation
   boundaries, no renderer/template semantics, no raw source parsing, no
   intrinsic-name assembly, no prefix-value hardcoding, and no lowering drift.
2. Evidence auditor: compare supported and unsupported prefix families against
   representative `tsldata/primitives/**/*.tsl` cases.
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
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m198_intrinsic_prefix_modifier_translation.py
find tslgen -type d -name __pycache__ -print
```

Remove validation-created `__pycache__` directories before final validation
reporting if any appear.

## Completion Rules

Before finishing an accepted M198 run:

- update `docs/redesign/implementation-roadmap.md` with the M198 result and
  selected next milestone;
- update redesign docs if implementation clarifies behavior, decisions, or
  open questions;
- update `docs/agent/current-redesign-state.md`;
- create the next concrete prompt under `docs/agent/runs/`;
- report exact validation results.

## Stop Rule

Do not start Milestone 199. Do not implement suffix string/no-argument/symbol
rules, infix rules, symbol immediate resolution, intrinsic-name assembly,
rendering, dependency closure, or lowering code in this milestone.

## Final Report

Report:

1. M198 review verdict.
2. Implemented files and docs changed.
3. Boundary decisions preserved.
4. Validation commands with exact results.
5. Review/audit verdicts.
6. Next active prompt path.
