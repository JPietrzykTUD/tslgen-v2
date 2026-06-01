# M193 Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M192 as accepted.

This is an implementation task. Use the executor-review loop: one
write-capable executor, then read-only architecture/boundary, evidence,
documentation, and validation audits. The orchestrator owns final state and
next-prompt updates.

## Accepted State

Accepted through:

```text
M192: Backend Type Spelling Translation Feeding Render Models
```

Selected milestone:

```text
Milestone 193: Backend Value Translation For Metadata-Only Requests
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
- `tslgen/src/tslgen/domain/backend_metadata.py`
- `tslgen/src/tslgen/pipeline/backend_metadata.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/backend_value_queries.py`
- `tslgen/src/tslgen/backends/type_spelling.py`
- `tslgen/tests/test_m181_backend_value_query_handoff.py`
- `tslgen/tests/test_m192_backend_type_spelling_translation.py`
- `tsldata/detail/lang/translate_cpp.tsl`
- `tsldata/detail/lang/translate_rust.tsl`

## Goal

Consume existing typed `BackendValueRequest` values from the accepted
lowering handoff and the M190 backend metadata catalog to produce typed
backend value translation results for metadata-only value requests.

This continues backend translation from typed requests and typed metadata, not
from raw `value<backend>(...)` text, renderer-local maps, or template-side
decisions.

## Scope

- Add a small backend value translation boundary that accepts a
  `BackendValueRequest` and `BackendMetadataCatalog`.
- Translate `BackendUninitValueRequest(kind="array")` through the active
  backend metadata entry `value_array_uninit` only when the metadata template
  has no unresolved placeholders. In the current active metadata this is
  expected for C++; Rust `value_array_uninit` contains `{type}` and must remain
  diagnostic until a typed type context is part of the request/rule input.
- Translate `BackendUninitValueRequest(kind="scalar")` through the active
  backend metadata entry `value_uninit`.
- Translate `BackendConstantValueRequest(name="x86::mm_fround_to_zero")`
  through the active backend metadata entry `value_mm_fround_to_zero`.
- Return typed backend translated value results with request source/provenance
  and metadata source/provenance.
- Add diagnostics for missing backend metadata, unsupported backend ids,
  missing metadata entries, unsupported request values, unsupported uninit
  selectors, unsupported constants, and metadata templates that require
  unresolved placeholders.
- Cover C++ and Rust focused metadata-only cases where the active metadata
  entry can be consumed without placeholder formatting.
- Preserve deterministic ordering if a collection helper is introduced.

## Out Of Scope

- Rendering.
- Formatting or evaluating arbitrary translation snippets.
- `BackendIntrinsicSuffixValueRequest` fulfillment.
- `BackendIntrinsicPrefixValueRequest` fulfillment.
- Type-operand suffix resolution.
- Intrinsic composition or intrinsic-name assembly.
- Source-operation translation.
- Backend control translation.
- Mask constant translation.
- Primitive-call rendering.
- Primitive body rendering.
- Dependency closure.
- Machine profile changes.
- Lowering changes.
- Runtime dependency on `frozen/` or `tslgenold`.

## Guardrails

- Do not rediscover or parse raw `value<backend>(...)` text. Consume the typed
  `BackendValueRequest` values that lowering already produces.
- Do not hardcode C++ or Rust value spelling tables in the translator; use the
  M190 `BackendMetadataCatalog`.
- Treat this as metadata-only translation. A translation template with no
  unresolved semantic inputs may be promoted into a typed value result, but the
  translator must not perform arbitrary placeholder formatting.
- Do not silently accept placeholder-bearing value templates as complete
  backend values. For example, Rust `value_array_uninit` contains `{type}` and
  should produce a diagnostic in this milestone rather than formatting or
  guessing a type.
- Do not broaden to suffix/prefix/intrinsic composition in this milestone.
- Do not make renderers or supplementary templates evaluate backend metadata.
- Do not modify M191 generated-project skeleton rendering, artifact writing,
  or build verification unless a narrowly scoped import/export adjustment is
  required.
- Do not reopen lowering or implementation-body parsing.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m193_backend_value_translation.py
find tslgen -type d -name __pycache__ -print
```

Remove validation-created `__pycache__` directories before final validation
reporting if any appear.

## Review Requirements

Run read-only review/audit subagents after the executor:

1. Architecture/boundary auditor: verify the translator consumes typed value
   requests plus typed metadata and does not become renderer-side inference,
   broad template evaluation, intrinsic composition, or a hardcoded backend
   value table.
2. Evidence auditor: verify metadata keys and spellings are grounded in
   current C++/Rust `tsldata/detail/lang/**` evidence and no `frozen/` or
   `tslgenold` runtime dependency is introduced.
3. Documentation auditor: verify roadmap, state, and redesign docs describe
   the accepted boundary and diagnostic codes.
4. Validation auditor: verify exact validation results and workspace hygiene.

If review returns `Needs Revision`, make only focused fixes and re-run focused
review. If review returns `Return To Planner` or `Reject`, stop and create the
appropriate next prompt instead of continuing implementation.

## Completion Rules

Before finishing:

- update `docs/redesign/implementation-roadmap.md` with the M193 result;
- update redesign docs if implementation clarifies behavior, decisions, or
  open questions;
- update `docs/agent/current-redesign-state.md`;
- create the next concrete prompt under `docs/agent/runs/`;
- report exact validation results.

## Final Report

Report:

1. M193 verdict.
2. Files changed.
3. Boundary created.
4. Tests and validation commands with exact results.
5. Review/audit verdicts.
6. Next active prompt path.
