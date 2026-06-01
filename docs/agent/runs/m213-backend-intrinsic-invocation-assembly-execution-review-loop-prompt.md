# M213 Backend Intrinsic Invocation Assembly Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M212 as accepted.

This is an implementation task. Use the executor-review loop:

```text
single write-capable executor
-> read-only reviewer/auditor subagents
-> focused revision executor if Needs Revision
-> focused re-review
-> next-run prompt generation
```

The orchestrator owns final state and next-prompt updates.

## Accepted State

Accepted through:

```text
Milestone 212: Backend Intrinsic Invocation Assembly Planning
```

Lowering is complete by current contract after M211. M213 must not reopen
lowering, rescan raw TSIL for semantic facts, parse intrinsic arguments, or
move semantic decisions into templates.

M166 discovers exact `intrin<...>(...)` and `intrin_compose<...>(...)`
islands. M182 hands them to typed direct/composed intrinsic requests. M195-M210
translate composed-intrinsic modifier fields into typed backend modifier
results.

ADR-062 records the accepted boundary: invocation assembly is a backend/output
translation stage before language rendering.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/domain-model.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/tsil-surface-inventory.md`
- `docs/redesign/lowering-completeness-audit.md`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/backend_intrinsic_handoff.py`
- `tslgen/src/tslgen/backends/intrinsic_modifiers.py`
- `tslgen/src/tslgen/backends/_intrinsic_metadata_modifiers.py`
- M166, M182, and M195-M210 tests.

## Goal

Implement a typed backend intrinsic invocation assembly boundary that consumes
already accepted intrinsic handoff requests plus translated intrinsic modifier
results and produces invocation-shaped backend values for later rendering.

## Scope

Add a focused backend module, likely
`tslgen/src/tslgen/backends/intrinsic_invocations.py`, and focused unit tests,
likely `tslgen/tests/test_m213_backend_intrinsic_invocation_assembly.py`.

The implementation should:

- consume `BackendDirectIntrinsicHandoffRequest` and
  `BackendIntrinsicComposeHandoffRequest` values;
- consume explicit `BackendTranslatedIntrinsicModifier` values produced by
  the accepted modifier translation boundary;
- produce frozen typed values for assembled backend intrinsic invocations;
- represent direct and composed invocations distinctly;
- carry backend id, source/request provenance, intrinsic name text or ordered
  name parts, opaque argument payload text/source, and typed immediate
  metadata;
- assemble composed intrinsic names from translated `prefix`, base, `infix`,
  `suffix`, `post`, and `infix_sep` values with deterministic rules;
- preserve translated immediates as typed compile-time metadata, not as
  rendered argument syntax;
- preserve intrinsic arguments as one opaque payload string with source
  provenance;
- diagnose missing modifier translations, extra modifier translations, direct
  intrinsic names with unresolved placeholder/template-like payloads, and
  unsupported translated modifier value kinds.

## Accepted Assembly Rules

For composed invocations:

- The source `base_text` is a typed intrinsic base name fragment with source
  provenance.
- `prefix` fragments appear before the base.
- `infix` fragments appear after the base.
- `suffix` fragments appear after infix fragments.
- `post` fragments appear after suffix fragments.
- `infix_sep` controls the separator between the base and infix fragments;
  if no `infix_sep` is present, use `_` for that boundary.
- Use `_` between infix and suffix fragments, between base and suffix when no
  infix is present, and before `post` fragments.
- Preserve source order within repeated fields if repeated fields are ever
  accepted by the existing modifier translation boundary.
- If any source modifier field has no translated modifier result, diagnose and
  do not assemble that invocation.
- If a translated modifier does not belong to the request's modifier fields,
  diagnose and do not assemble that invocation.

For direct invocations:

- Accept only direct intrinsic angle payloads that are already literal backend
  intrinsic names.
- Diagnose direct intrinsic names containing unresolved placeholders or
  template-like payloads, such as `{{...}}` or embedded `value<backend>(...)`.
- Do not resolve direct-name placeholders in M213.

## Out Of Scope

- New lowering or raw TSIL source rescans.
- Parsing or splitting intrinsic argument expressions.
- Recursive payload discovery inside arguments.
- Direct-intrinsic placeholder resolution.
- Final C++ or Rust call rendering.
- Rust `core::arch::*` module qualification.
- C++ non-type template rendering.
- Rust const generic rendering.
- Primitive dependency closure or primitive body rendering.
- Whole generated project rendering, writing, or build verification.
- Template-side semantic decisions.
- Source repair.
- Runtime dependency on `frozen/` or `tslgenold`.

## Expected Tests

Add focused tests for:

- direct literal intrinsic invocation assembly with opaque arguments;
- direct placeholder/template-like intrinsic names diagnosed as unsupported;
- composed prefix/base/suffix name assembly;
- composed infix assembly with default `_` separator;
- composed infix assembly with `infix_sep=""`;
- composed `post` placement;
- typed immediate literal, selected-signature immediate, and selected-generic
  immediate preservation as compile-time metadata;
- missing modifier translation diagnostics;
- extra modifier translation diagnostics;
- arguments containing nested TSIL-looking text remaining opaque;
- public backend imports if the module exposes a new public API.

Do not add corpus-wide rendering or compile tests in M213. If a corpus
characterization test is useful, keep it read-only and focused on assembly
classification over already accepted handoff/modifier results.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m213_backend_intrinsic_invocation_assembly.py
find tslgen -type d -name __pycache__ -print
```

If validation creates `__pycache__` directories under `tslgen`, remove them
and rerun the final `find` command.

## Required Review/Audit Subagents

After implementation and validation, run read-only subagents:

1. Architecture/boundary reviewer: typed backend/output boundary, no lowering
   reopen, no renderer/template semantics.
2. Evidence reviewer: M166/M182/M195-M210 input compatibility and corpus
   pressure.
3. Test reviewer: coverage of accepted assembly rules and diagnostics.
4. Documentation reviewer: roadmap/state/design-doc consistency.
5. Validation auditor: exact validation results and workspace hygiene.

If any reviewer returns `Needs Revision`, make only focused fixes for the
blocking issues and rerun the relevant focused review. If any returns
`Return To Planner` or `Reject`, stop implementation and create the
appropriate next prompt.

## Completion Rules

Before finishing:

- update `docs/redesign/implementation-roadmap.md` with the execution result;
- update `docs/redesign/behavioral-spec.md` and `docs/redesign/domain-model.md`
  if the accepted implementation adds new public backend invocation values;
- update `docs/agent/current-redesign-state.md`;
- create the next concrete prompt under `docs/agent/runs/`;
- do not start the next milestone.

## Final Report

Report:

1. Implementation summary.
2. Review/audit verdicts.
3. Validation commands and exact results.
4. Any follow-ups.
5. Next active prompt path.
