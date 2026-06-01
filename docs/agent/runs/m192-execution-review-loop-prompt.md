# M192 Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M191 as accepted.

This is an implementation task. Use the executor-review loop: one
write-capable executor, then read-only architecture/boundary, evidence,
documentation, and validation audits. The orchestrator owns final state and
next-prompt updates.

## Accepted State

Accepted through:

```text
M191: Profile-Aware Generated Project Skeleton And Smoke Verification Boundary
```

Selected milestone:

```text
Milestone 192: Backend Type Spelling Translation Feeding Render Models
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
- `tslgen/src/tslgen/lowering/backend_type_queries.py`
- `tslgen/tests/test_m180_backend_type_query_handoff.py`
- `tsldata/detail/lang/types/types_cpp.tsl`
- `tsldata/detail/lang/types/types_rust.tsl`
- `tsldata/detail/lang/translate_cpp.tsl`
- `tsldata/detail/lang/translate_rust.tsl`

## Goal

Consume existing typed `BackendTypeSpellingRequest` values from the accepted
lowering handoff and the M190 backend metadata catalog to produce typed backend
type spelling translation results that can later feed M191-style typed render
models.

This starts backend translation from typed requests and typed metadata, not
from raw `type<backend>(...)` text, renderer-local type tables, or
template-side decisions.

## Scope

- Add a small backend type spelling translation boundary that accepts a
  `BackendTypeSpellingRequest` and `BackendMetadataCatalog`.
- Resolve exact scalar type identity requests such as `si32`, `ui32`, `f32`,
  and `f64` through the active backend language maps.
- Document and test the accepted source type-tag to language-key
  normalization rule, such as `si32 -> s32` and `ui32 -> u32`.
- Resolve `LoweredSizeType()` through the backend translation metadata entry
  `type_size`.
- Return typed backend type spelling results with request source/provenance.
- Add diagnostics for missing backend metadata, missing scalar type spellings,
  unsupported request values, and unsupported backend ids.
- Cover C++ and Rust focused cases and preserve deterministic ordering if a
  collection helper is introduced.

## Out Of Scope

- Rendering.
- Formatting or evaluating arbitrary translation snippets.
- Primitive body rendering.
- Vector register, vector mask, vector member, `CurrentVector`, or
  `LoweredVectorAsExtensionType` fulfillment.
- Backend value, intrinsic, control, mask, source-operation, or primitive-call
  translation.
- Dependency closure.
- Machine profile changes.
- Lowering changes.
- Runtime dependency on `frozen/` or `tslgenold`.

## Guardrails

- Do not rediscover or parse raw `type<backend>(...)` text. Consume the typed
  `BackendTypeSpellingRequest` values that lowering already produces.
- Do not hardcode C++ or Rust scalar spelling tables in the translator; use
  the M190 `BackendMetadataCatalog`.
- Keep the `si*/ui*` to `s*/u*` normalization rule explicit, tiny, and tested.
- Do not broaden to vector/register/mask spelling semantics in this milestone.
- Do not make renderers or supplementary templates evaluate backend metadata.
- Do not modify M191 generated-project skeleton rendering, artifact writing,
  or build verification unless a narrowly scoped integration test requires an
  import/export adjustment.
- Do not reopen lowering or implementation-body parsing.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m192_backend_type_spelling_translation.py
find tslgen -type d -name __pycache__ -print
```

Remove validation-created `__pycache__` directories before final validation
reporting if any appear.

## Review Requirements

Run read-only review/audit subagents after the executor:

1. Architecture/boundary auditor: verify the translator consumes typed
   requests plus typed metadata and does not become renderer-side inference,
   broad template evaluation, or a hardcoded backend table.
2. Evidence auditor: verify scalar spellings and `type_size` are grounded in
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

- update `docs/redesign/implementation-roadmap.md` with the M192 result;
- update redesign docs if implementation clarifies behavior, decisions, or
  open questions;
- update `docs/agent/current-redesign-state.md`;
- create the next concrete prompt under `docs/agent/runs/`;
- report exact validation results.

## Final Report

Report:

1. M192 verdict.
2. Files changed.
3. Boundary created.
4. Tests and validation commands with exact results.
5. Review/audit verdicts.
6. Next active prompt path.
