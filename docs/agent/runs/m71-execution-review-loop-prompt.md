# Milestone 71 Execution Review Loop Prompt

You are the Codex orchestrator for the accepted M71 implementation and review
loop.

Read `docs/agent/current-redesign-state.md` first.

Do not start Milestone 72.

## Accepted State

Accepted through:

```text
Milestone 70
```

Post-M70 planning is accepted. It selected:

```text
Milestone 71: Exact Array Initialization Vector-Alignment Request Resolution Slice
```

Internal planning review returned:

```text
Accept With Follow-Ups
```

Human acceptance has been recorded. M71 execution is the active workflow
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

Resolve exactly the accepted M67 array-initialization helper request for:

```text
value<generation>(vector::alignment)
```

The resolution must run through the accepted M69/M70 extracted
array-initialization stage pipeline and consume explicit typed
vector-alignment metadata supplied before lowering evaluation.

M71 is generation-time lowering request resolution only. It consumes alignment
facts as typed inputs; it does not compute or infer them from vector length,
vector bits, scalar byte size, selected type tags, SVE token text, extension
names, backend ids, renderer names, host CPU features, backend maps,
catalog/file reads, `tsldata`, raw helper text, or `candidate_id` parsing.

## In Scope

- Consume accepted M70 vector-length request-resolution output, accepted M68
  base-type resolution, accepted M67 helper-request IR, and accepted M69
  extracted array-initialization stage pipeline values.
- Select only the remaining M67 request record whose typed kind/leaf/ordinal
  identify the exact `value<generation>(vector::alignment)` helper from the
  first array-initialization slot.
- Introduce or consume explicit typed vector-alignment metadata input,
  supplied before lowering evaluation through `LoweringRequest`,
  `GenerationContext`, or an equivalent typed request/context value.
- Use typed candidate context fields such as candidate id, target extension,
  source extension, and selected type tag as structured fields.
- Produce a narrow typed result, for example
  `ExactArrayInitializationVectorAlignmentResolutionIr`, carrying:
  - the source M70 vector-length resolution;
  - the source M67 vector-alignment request record;
  - a typed alignment value or explicit unsupported-policy diagnostic;
  - the remaining unresolved backend-uninit request;
  - deterministic provenance including candidate, type, envelope/slot, and
    source location facts.
- Add one deterministic generation-lowering stage after
  `array_initialization_vector_length_request_resolution`, for example
  `array_initialization_vector_alignment_request_resolution`.
- Preserve accepted M68 base-type behavior, accepted M69 stage-pipeline
  behavior, and accepted M70 vector-length behavior.
- Include the M70 validation hardening follow-up by explicitly guarding that
  catalog reads, `tsldata` reads, and host CPU queries are not used during M71
  request resolution.

## Out Of Scope

- Resolution of `value<backend>(uninit::array)`.
- Broad vector/register metadata semantics, vector register type lowering, SVE
  predicate semantics, aligned load/store semantics, `assume_aligned`
  rendering, byte-size-to-`svptrue_b*` inference, or alignment inference from
  vector length, vector bits, scalar byte size, selected type tag, extension
  name, SVE token text, backend id, renderer name, catalog data, `tsldata`, or
  host CPU state during lowering.
- Backend translation or backend rendering of vector alignment, including C++
  spellings such as `Vec::vector_alignment()`.
- Broad `var`, `array_type`, declaration, array allocation/lifetime, variable
  scope, store, return, `tmp.data()`, `emit_return`, direct-intrinsic
  semantics, loops, calls, casts, or broad TSIL parsing.
- Generic `value<generation>(...)` or `value<backend>(...)` evaluator
  families, broad stage registries, broad vector metadata resolvers, raw
  helper-string dispatch, or semantic tables keyed by raw helper text, request
  ordinals alone, selected type tags, SVE tokens, backend ids, or renderer
  names.
- Generated C++ or Rust output, generated tests, golden output,
  CLI/reporting/writer behavior, compiler execution, lowering-time file/catalog
  reads, raw TSL parsing, `tsldata` reads during lowering evaluation, host CPU
  queries, or runtime `frozen/` use.

## Acceptance Criteria

- Direct resolver tests prove the M67/M70 vector-alignment request resolves
  from explicit typed vector-alignment metadata.
- Normal `lower_candidates` pipeline tests prove the M71 stage appears after
  `array_initialization_vector_length_request_resolution` and preserves
  accepted M69/M70 ordering and outputs.
- Static alignment metadata and unsupported-policy behavior are explicit.
  Unsupported alignment metadata must be represented as typed diagnostics; it
  must not become a fake inferred alignment value.
- Diagnostics cover missing metadata, duplicate/conflicting metadata,
  unsupported alignment policy, mismatched selected candidate context,
  malformed/missing/multiple vector-alignment request records, unsupported
  source stage, and provenance mismatch.
- Determinism tests cover repeated runs and reversed metadata input order.
- Regression tests prove backend uninit remains unresolved.
- Regression tests prove accepted M68 base-type behavior and accepted M70
  vector-length behavior are unchanged.
- Regression tests prove raw helper evaluators are not called on M67 leaf text,
  raw helper text is not parsed, and no catalog, `tsldata`, host CPU, backend
  translation, rendering, generated output, or golden-file behavior is
  introduced.

## Phase 1: Executor

If M71 is already implemented and awaiting review, skip implementation and go
directly to Phase 2.

If M71 is not implemented, spawn exactly one write-capable executor subagent.
Tell the executor:

- It is not alone in the codebase.
- It must not revert or overwrite edits made by others.
- It owns only the M71 implementation slice, directly related tests, and any
  necessary redesign-doc updates.
- It must not edit `docs/agent/current-redesign-state.md`.
- It must not create the next run prompt.
- It must keep M71 within the scope and out-of-scope boundaries above.
- It must consume typed M67/M68/M69/M70 request/result values and explicit
  typed vector-alignment metadata supplied before lowering evaluation.
- It must not derive semantic vector-alignment values from vector length,
  vector bits, scalar byte size, raw helper text, M66 slot text, M67 leaf text,
  raw TSIL, raw TSL, `candidate_id`, SVE tokens, extension names, selected type
  tags, backend ids, backend vector-alignment spellings, renderer names,
  catalog data, `tsldata`, host CPU state, or runtime `frozen/`.
- It must preserve backend uninit as unresolved.
- It must preserve accepted M68 base-type behavior, accepted M69 stage-pipeline
  behavior, and accepted M70 vector-length behavior.
- It must include explicit no-catalog-read, no-`tsldata`-read, and no-host-CPU
  coverage during request resolution.

The executor should report files changed, tests added or updated, validation
commands run, how typed metadata enters before lowering evaluation, how raw
helper dispatch and alignment hardwiring are avoided, how unresolved backend
uninit remains unresolved, how M70 vector-length behavior is preserved, and
any follow-ups or blockers.

## Phase 2: Review And Audit Subagents

After execution, run read-only review/audit subagents using this workflow:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Validation auditor: verify required validation commands and assess test
   coverage for direct resolver behavior, normal `lower_candidates` pipeline
   behavior, stage order after M70, explicit metadata input, unsupported-policy
   diagnostics, deterministic ordering, unchanged M68/M69/M70 behavior,
   unresolved backend-uninit request, no generated output/golden churn, and no
   raw helper/file/catalog/`tsldata`/host CPU dependencies during lowering.
3. Boundary auditor: confirm M71 resolves only the exact vector-alignment
   request and does not add backend uninit resolution, broad vector metadata
   semantics, raw helper parsing/evaluation, aligned load/store semantics,
   declaration/array semantics, backend translation, rendering, generated
   output, broad TSIL parsing, lowering-time file/catalog reads, `tsldata`
   reads during lowering evaluation, host CPU queries, or runtime `frozen/`
   use.
4. Extensibility auditor: confirm the integration uses the M69/M70 extracted
   pipeline as a maintainable typed attachment point without introducing a
   broad registry, central dispatcher, raw-text evaluator, public IR expansion,
   or hardwired semantic shortcut.
5. Documentation auditor: check roadmap, lowering docs, behavioral spec, open
   questions, design decisions, target architecture, pipeline design, testing
   strategy, and parity baselines for required updates or stale claims.
6. Evidence auditor: confirm the implementation and tests are justified by
   accepted M67/M68/M69/M70 behavior plus the exact `array.tsl:105` request,
   and that aligned load/store evidence and backend translation evidence remain
   boundary constraints rather than runtime dependencies or output behavior.

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

Do not broaden M71 during revision.

If the verdict is `Return To Planner` or `Reject`, stop implementation. Create
the appropriate next planning or rollback prompt under `docs/agent/runs/` and
update `docs/agent/current-redesign-state.md` to point at it.

## Phase 5: Next Prompt Generation

If the final verdict is `Accept` or `Accept With Follow-Ups`:

- Record any non-blocking follow-ups.
- Update `docs/agent/current-redesign-state.md` so M71 is accepted.
- Create the next concrete prompt under `docs/agent/runs/`.
- If no post-M71 plan has been accepted, create a post-M71
  planning-plus-review prompt. Do not start M72.

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
3. Review/audit subagents used.
4. Consolidated verdict.
5. Follow-ups recorded, if any.
6. Next prompt created.
7. State transition made.
8. Validation commands and exact results.
9. Whether the repo is ready for the next workflow action.
