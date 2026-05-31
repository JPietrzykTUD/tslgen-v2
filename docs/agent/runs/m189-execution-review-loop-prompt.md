# M189 Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M188 as accepted.

This is an implementation task. Use the executor-review loop: one
write-capable executor, then read-only architecture/boundary, evidence,
documentation, and validation audits. The orchestrator owns final state and
next-prompt updates.

## Accepted State

Accepted through:

```text
M188: Supplementary Asset And Template Boundary For C++/Rust Project Skeletons
```

Selected milestone:

```text
Milestone 189: Typed Backend Language And Translation Metadata Catalog
```

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/requirements.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/domain-model.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/design-decisions.md`
- `tsldata/detail/lang/types/types_cpp.tsl`
- `tsldata/detail/lang/types/types_rust.tsl`
- `tsldata/detail/lang/translate_cpp.tsl`
- `tsldata/detail/lang/translate_rust.tsl`
- existing parser/catalog code under `tslgen/src/tslgen/syntax`,
  `tslgen/src/tslgen/domain`, and `tslgen/src/tslgen/pipeline`

## Goal

Add the first typed catalog boundary for backend language/type maps and
translation maps from `tsldata/detail/lang/**`, focused on current C++ and
Rust evidence.

The milestone should make backend metadata available as typed facts without
evaluating snippets, rendering code, replacing existing tiny emitters, or
reopening lowering.

## Scope

- Parse and catalog exact `language <backend>:` type-spelling entries from the
  current `tsldata/detail/lang/types/types_*.tsl` shape, for example:

  ```text
  language cpp:
    s32 {type "int32_t"}
  ```

- Parse and catalog exact `translation <backend>:` template entries from the
  current `tsldata/detail/lang/translate_*.tsl` shape, for example:

  ```text
  translation cpp:
    call "::tsl::{name}<Vec>({args})"
  ```

- Store metadata as typed immutable domain/catalog values with deterministic
  ordering and source-aware diagnostics.
- Cover active C++ and Rust metadata in focused tests. C17 remains deferred
  evidence and must not become an active backend.
- Add diagnostics for malformed entries and duplicate entries within a backend
  language or translation map.

## Out Of Scope

- Evaluating translation snippets.
- Replacing existing scalar/operator backend emitter tables.
- Backend type/value/intrinsic/source-operation translation.
- Rendering primitive bodies.
- Jinja/template rendering.
- Supplementary asset changes.
- Lowering changes.
- Dependency closure.
- Runtime dependency on `frozen/` or `tslgenold`.

## Guardrails

- Do not treat raw dictionary metadata as the semantic model downstream.
  Dictionary-like parser details must be promoted into typed catalog/domain
  values before backend/output stages consume them.
- Do not introduce raw-key semantic shortcuts such as
  `(backend, operation, type) -> emitted text`.
- Do not make renderers evaluate translation strings in this milestone.
- Keep the parser support exact to the observed language/translation metadata
  forms; malformed or nearby forms should be diagnostics, not source repair.
- Preserve the M188 supplementary/template boundary. Do not move backend
  semantics into `supplementary/` templates.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m189_backend_metadata_catalog.py
find tslgen -type d -name __pycache__ -print
```

Remove validation-created `__pycache__` directories before final validation
reporting if any appear.

## Review Requirements

Run read-only review/audit subagents after the executor:

1. Architecture/boundary auditor: verify typed metadata cataloging does not
   become backend semantic evaluation or renderer-side inference.
2. Evidence auditor: verify C++/Rust language and translation fixtures are
   grounded in current `tsldata/detail/lang/**` evidence and no `frozen/` or
   `tslgenold` runtime dependency is introduced.
3. Documentation auditor: verify roadmap, state, and redesign docs describe
   the accepted boundary and any diagnostic codes.
4. Validation auditor: verify exact validation results and workspace hygiene.

If review returns `Needs Revision`, make only focused fixes and re-run focused
review. If review returns `Return To Planner` or `Reject`, stop and create the
appropriate next prompt instead of continuing implementation.

## Completion Rules

Before finishing:

- update `docs/redesign/implementation-roadmap.md` with the M189 result;
- update redesign docs if implementation clarifies behavior, decisions, or
  open questions;
- update `docs/agent/current-redesign-state.md`;
- create the next concrete prompt under `docs/agent/runs/`;
- report exact validation results.

## Final Report

Report:

1. M189 verdict.
2. Files changed.
3. Boundary created.
4. Tests and validation commands with exact results.
5. Review/audit verdicts.
6. Next active prompt path.
