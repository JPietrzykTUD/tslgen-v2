# Milestone 69 Execution Review Loop Prompt

You are the Codex orchestrator for the accepted M69 implementation and review
loop.

Read `docs/agent/current-redesign-state.md` first.

Do not start Milestone 70.

## Accepted State

Accepted through:

```text
Milestone 68
```

Post-M68 planning is accepted. It selected:

```text
Milestone 69: Exact Array Initialization Stage Pipeline Extraction Slice
```

Internal planning review returned:

```text
Accept With Follow-Ups
```

Human acceptance has been recorded. M69 execution is the active workflow
action.

## Read First

- `AGENTS.md`
- `PLANS.md`
- `docs/agent/current-redesign-state.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/agent/review-checklist.md`
- `docs/agent/subagents/`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/generation-time-semantic-lowering.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/open-questions.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/frozen-parity-baselines.md`

## Goal

Extract the accepted M64-M68 exact array-initialization stage assembly tail from
`_lower_input` into a small typed helper or private pipeline result while
preserving accepted M68 behavior exactly.

M69 is behavior-preserving lowering-pipeline maintainability work only. It
creates a clearer typed attachment point for later vector length, vector
alignment, backend uninit, or array/declaration slices, but it does not
implement any of those semantics.

## In Scope

- Extract only the exact array-initialization stage sequence currently
  assembled inline after selected-body envelope lowering:
  - accepted M64 array-body envelope assembly;
  - accepted M66 exact array-initialization slot form lowering;
  - accepted M67 exact helper-request IR lowering;
  - accepted M68 exact base-type request resolution.
- Introduce a small private typed helper/result if useful, for example
  `ExactArrayInitializationStagePipelineResult`, carrying the same existing
  output tuples and `GenerationLoweringStage` records.
- Preserve the same public `LoweredImplementation` fields, stage names, stage
  order, typed outputs, diagnostics, source locations, deterministic ordering,
  no-skeleton/no-body behavior, and generated-output state as accepted M68.
- Keep the accepted calls to M64/M66/M67/M68 lowering functions in the same
  order and with the same typed inputs.
- Keep M66 slot text and M67 leaf text as provenance/invariant evidence only.
- Preserve unresolved vector length, vector alignment, and backend uninit
  requests exactly as accepted M68.
- Add focused tests proving the extraction preserves behavior and improves the
  typed stage-pipeline boundary without broadening semantics.

## Out Of Scope

- New semantic helper resolution.
- Resolution of `value<generation>(vector::length)`,
  `value<generation>(vector::alignment)`, or
  `value<backend>(uninit::array)`.
- Generic helper resolver families, broad stage registries, raw helper-string
  dispatch, raw query-string helper evaluation, or semantic tables keyed by
  source text, request ordinals, selected type tags, SVE tokens, backend ids,
  or renderer names.
- New public IR, new `LoweredImplementation` fields, new stage names,
  renderer-facing values, generated artifacts, or golden-file churn.
- New slot-specific lowering beyond the existing exact ordinal-0
  array-initialization slot. Predicate initialization, selected-body, store,
  and return slots remain untouched and opaque.
- Broad `var`, `array_type`, declaration, array allocation/lifetime, variable,
  store, return, SVE/direct-intrinsic, backend translation, rendering,
  generated output, generated tests, CLI/report/writer behavior, Rust,
  compiler execution, broad TSIL parsing, lowering-time file/catalog reads,
  raw TSL parsing, `tsldata` reads during lowering evaluation, or runtime
  `frozen/` use.
- `GenerationLoweringStage.__post_init__` table cleanup and
  `_ExactArrayInitializationBaseTypeRequestRule.result_kind` cleanup, unless a
  purely mechanical touch is required and does not broaden M69.

## Acceptance Criteria

- Direct helper/private pipeline tests cover selected `svptrue_b16`,
  `svptrue_b32`, and `svptrue_b64` paths plus no-body paths such as
  `si8`/`ui8`.
- Normal `lower_candidates` tests prove identical `LoweredImplementation`
  fields and the same stage sequence:
  `array_body_envelope_slot_assembly`,
  `array_initialization_slot_form_lowering`,
  `array_initialization_helper_request_lowering`, and
  `array_initialization_base_type_request_resolution`.
- Representative failure-propagation tests prove M64/M66/M67/M68 diagnostics
  retain their codes, severity, source locations, and actionable message
  intent.
- Determinism tests compare repeated runs and, where nearby skeleton inputs are
  touched, reversed skeleton ordering.
- Regression tests prove no raw helper parsing, no raw query-string helper
  evaluation on M67 leaf text, no vector/backend request resolution, no backend
  translation/rendering, and no generated output or golden-file changes.

## Phase 1: Executor

If M69 is already implemented and awaiting review, skip implementation and go
directly to Phase 2.

If M69 is not implemented, spawn exactly one write-capable executor subagent.
Tell the executor:

- It is not alone in the codebase.
- It must not revert or overwrite edits made by others.
- It owns only the M69 implementation slice, directly related tests, and any
  necessary redesign-doc updates.
- It must not edit `docs/agent/current-redesign-state.md`.
- It must not create the next run prompt.
- It must keep M69 behavior-preserving and within the boundaries above.
- It must extract the accepted M64/M66/M67/M68 array-initialization stage tail
  from `_lower_input` into a typed helper or private pipeline result.
- It must preserve existing public outputs, stage names/order, diagnostics,
  source locations, deterministic ordering, no-skeleton/no-body behavior, and
  generated-output state.
- It must not add a broad stage registry, generic helper dispatcher, semantic
  resolver, vector metadata resolver, backend uninit resolver, declaration or
  array semantics, renderer path, generated output, or runtime `frozen/` use.

The executor should report files changed, tests added or updated, validation
commands run, how behavior preservation was proven, how the extracted boundary
stays typed and maintainable, and any follow-ups or blockers.

## Phase 2: Review And Audit Subagents

After execution, run read-only review/audit subagents using this workflow:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Validation auditor: verify the required validation commands and assess test
   coverage for behavior preservation, direct helper/private pipeline output,
   normal `lower_candidates` output, stage order, representative diagnostic
   propagation, determinism, no generated output/golden churn, and unchanged
   M64-M68 behavior.
3. Boundary auditor: confirm M69 extracts only the exact accepted
   array-initialization stage assembly tail and does not add semantic helper
   resolution, vector/backend request resolution, raw helper parsing, backend
   translation, rendering, generated output, broad TSIL parsing,
   lowering-time file/catalog reads, `tsldata` reads during lowering
   evaluation, or runtime `frozen/` use.
4. Extensibility auditor: confirm the extraction creates a maintainable typed
   attachment point for future sibling resolver stages without introducing a
   broad registry, central dispatcher, raw-text evaluator, or public IR
   expansion.
5. Documentation auditor: check roadmap, lowering docs, behavioral spec, open
   questions, design decisions, target architecture, pipeline design, testing
   strategy, and parity baselines for required updates or stale claims.
6. Evidence auditor: confirm the implementation and tests are justified by
   accepted M64-M68 behavior plus `tsldata/primitives/load_store/array.tsl`
   context, and that M66 slot text and M67 leaf text remain provenance only.

Review and audit subagents are read-only unless a later revision task
explicitly assigns one focused write-capable executor.

## Phase 3: Consolidated Verdict

The orchestrator must consolidate subagent results into one verdict:

- `Accept`
- `Accept With Follow-Ups`
- `Needs Revision`
- `Return To Planner`
- `Reject`

Findings must be specific and file/line grounded where applicable.

## Phase 4: Revision Loop If Needed

If the consolidated verdict is `Needs Revision`, run exactly one focused
write-capable revision executor for the blocking issues only. Then run focused
read-only re-review for the changed areas.

Do not broaden M69 during revision.

If the verdict is `Return To Planner` or `Reject`, stop implementation. Create
the appropriate next planning or rollback prompt under `docs/agent/runs/` and
update `docs/agent/current-redesign-state.md` to point at it.

## Phase 5: Next Prompt Generation

If the final verdict is `Accept` or `Accept With Follow-Ups`:

- Record any non-blocking follow-ups.
- Update `docs/agent/current-redesign-state.md` so M69 is accepted.
- Create the next concrete prompt under `docs/agent/runs/`.
- If no post-M69 plan has been accepted, create a post-M69
  planning-plus-review prompt. Do not start M70.

The next prompt must follow `docs/agent/next-run-prompt-protocol.md`.

## Required Validation

Run targeted validation selected by the executor plus:

```bash
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

If Python implementation files change, also run an appropriate compile or
static check for those files. Include exact commands and exact results in the
final report.

## Final Report

Report:

1. Executor status.
2. Files changed.
3. Validation commands and exact results.
4. Review/audit subagents used.
5. Consolidated verdict.
6. Follow-ups recorded, if any.
7. Next prompt created.
8. Whether the repo is ready for the next workflow action.
