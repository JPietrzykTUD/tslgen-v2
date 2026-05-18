# Milestone 72 Execution Review Loop Prompt

You are the Codex orchestrator for the accepted M72 implementation and review
loop.

Read `docs/agent/current-redesign-state.md` first.

Do not start Milestone 73.

## Accepted State

Accepted through:

```text
Milestone 71
```

Post-M71 planning is accepted. It selected:

```text
Milestone 72: Exact Array Initialization Helper-Set Completion IR Slice
```

Internal planning review returned:

```text
Accept With Follow-Ups
```

Human acceptance has been recorded. M72 execution is the active workflow
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

Consume the accepted M71 vector-alignment resolution for the exact first
array-initialization slot and package the complete helper set into one typed
aggregate IR:

- accepted M68 base-type resolution;
- accepted M70 vector-length resolution;
- accepted M71 vector-alignment resolution;
- the remaining exact M67 `value<backend>(uninit::array)` request as a typed
  unresolved backend-value request boundary.

M72 is generation-time lowering helper-set completion only. It must not
resolve backend uninit into backend text, backend translation requests,
renderer-ready values, generated output, or declaration/array semantics.

## In Scope

- Consume only accepted M71
  `ExactArrayInitializationVectorAlignmentResolutionIr` values, the
  `array_initialization_vector_alignment_request_resolution` stage output, or
  a typed `LoweredImplementation` carrying exactly one accepted M71
  vector-alignment resolution.
- Select only the remaining M67 request record whose typed fields identify the
  exact backend-uninit helper from the first array-initialization slot:
  request ordinal `3`, request kind `backend_value`, and helper leaf kind
  `value_backend_uninit_array`.
- Model that backend-uninit request only as a typed deferred backend-value
  request boundary or policy value. Source text may be preserved only as
  provenance/invariant evidence.
- Produce one typed aggregate such as
  `ExactArrayInitializationHelperSetCompletionIr`, carrying:
  - the source M71 vector-alignment resolution;
  - the accepted M70 vector-length resolution;
  - the accepted M68 base-type resolution;
  - the source M67 backend-uninit request record;
  - the typed unresolved backend-uninit boundary/policy;
  - deterministic provenance including candidate id, target/source extension,
    selected type tag, branch-chain id, envelope/slot identity, variable token,
    and source locations.
- Append one deterministic stage after
  `array_initialization_vector_alignment_request_resolution`, for example
  `array_initialization_helper_set_completion`.
- Preserve accepted M68 base-type behavior, accepted M69 stage-pipeline
  behavior, accepted M70 vector-length behavior, and accepted M71
  vector-alignment behavior.
- Include M69/M71 hardening follow-ups where practical:
  - pipeline-level M67 diagnostic propagation coverage for the extracted
    array-initialization stage pipeline;
  - guards that M72 lowering does not read catalog data, `tsldata`, host CPU
    state, backend maps, or `frozen/` at evaluation time.

## Out Of Scope

- Translating, resolving, or rendering `value<backend>(uninit::array)` to C++,
  Rust, backend text, initializer syntax, `{}`, `MaybeUninit`, backend
  translation requests, renderer-ready values, or generated output.
- Backend manifests, backend maps, language maps, translation maps,
  renderer calls, generated artifacts, golden files, CLI/report/writer
  behavior, Rust behavior, compiler execution, or generated-test execution.
- Broad `var`, `array_type`, declaration, array allocation/lifetime,
  variable binding/scope, initializer semantics, store, return, `tmp.data()`,
  `emit_return`, `assume_aligned`, direct-intrinsic/SVE semantics, loops,
  calls, casts, or multi-statement lowering.
- Generic `value<backend>(...)`, `type<backend>(...)`,
  `value<generation>(...)`, or `type<generation>(...)` evaluator families.
- Broad helper registries, raw helper-string dispatch, broad stage registries,
  broad TSIL parsing, lowering-time file/catalog reads, raw TSL parsing,
  `tsldata` reads during lowering evaluation, host CPU queries, or runtime
  dependency on `frozen/`.

## Acceptance Criteria

- Direct resolver tests prove M72 consumes accepted M71 vector-alignment
  resolution values and produces the exact helper-set completion aggregate.
- Normal `lower_candidates` pipeline tests prove the M72 stage appears after
  `array_initialization_vector_alignment_request_resolution` and preserves
  M68/M69/M70/M71 ordering and outputs.
- Tests prove the backend-uninit request is identified by typed M67 fields:
  request ordinal `3`, request kind `backend_value`, and helper leaf kind
  `value_backend_uninit_array`. Source text is provenance/invariant evidence
  only.
- Diagnostics cover missing, duplicate, wrong-kind, wrong-ordinal,
  unsupported leaf text, unsupported source/container, context mismatch, and
  provenance mismatch.
- Determinism tests cover repeated runs and reordered inputs.
- Regression tests prove M68 base-type behavior, M70 vector-length behavior,
  and M71 vector-alignment behavior are unchanged.
- Regression tests prove no backend translation, rendering, generated output,
  golden-file churn, declaration/array lowering, raw helper evaluator calls,
  raw helper parsing, catalog reads, `tsldata` reads, host CPU queries,
  backend map reads, or runtime `frozen/` use is introduced.
- Pipeline-level M67 diagnostic propagation coverage is included if M72
  touches the extracted array-initialization stage pipeline in a way that can
  exercise it.

## Phase 1: Executor

If M72 is already implemented and awaiting review, skip implementation and go
directly to Phase 2.

If M72 is not implemented, spawn exactly one write-capable executor subagent.
Tell the executor:

- It is not alone in the codebase.
- It must not revert or overwrite edits made by others.
- It owns only the M72 implementation slice, directly related tests, and any
  necessary redesign-doc updates.
- It must not edit `docs/agent/current-redesign-state.md`.
- It must not create the next run prompt.
- It must keep M72 within the scope and out-of-scope boundaries above.
- It must consume typed M67/M68/M69/M70/M71 request/result/pipeline values.
- It must identify backend uninit only by typed M67 request fields and must
  keep source text as provenance/invariant evidence only.
- It must keep backend uninit as a typed deferred backend-value boundary.
- It must not translate or render backend uninit, query backend maps, create
  backend translation requests, produce renderer-ready values, lower
  declaration/array semantics, or change generated output.
- It must preserve accepted M68 base-type behavior, accepted M69
  stage-pipeline behavior, accepted M70 vector-length behavior, and accepted
  M71 vector-alignment behavior.
- It must include explicit no-catalog-read, no-`tsldata`-read, no-host-CPU,
  no-backend-map, no-renderer, and no-`frozen/` coverage where practical
  during request resolution/helper-set completion.

The executor should report files changed, tests added or updated, validation
commands run, how the typed helper-set aggregate is produced, how backend
uninit remains deferred and non-rendering, how raw helper dispatch and
hardwiring are avoided, how M68/M70/M71 behavior is preserved, and any
follow-ups or blockers.

## Phase 2: Review And Audit Subagents

After execution, run read-only review/audit subagents using this workflow:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Validation auditor: verify required validation commands and assess test
   coverage for direct helper-set completion, normal `lower_candidates`
   pipeline behavior, stage order after M71, typed backend-uninit request
   identity, diagnostics, determinism, unchanged M68/M69/M70/M71 behavior,
   no generated output/golden churn, and no raw helper/file/catalog/`tsldata`/
   host CPU/backend-map/renderer/`frozen/` dependencies during lowering.
3. Boundary auditor: confirm M72 only completes the exact first-slot helper
   set and does not add backend-uninit translation, backend maps, backend
   rendering, declaration/array semantics, broad helper evaluation, raw helper
   parsing/evaluation, broad TSIL parsing, generated output, lowering-time
   file/catalog reads, `tsldata` reads during lowering evaluation, host CPU
   queries, or runtime `frozen/` use.
4. Extensibility auditor: confirm the integration uses the M69/M70/M71
   extracted pipeline as a maintainable typed attachment point without
   introducing a broad registry, central dispatcher, raw-text evaluator, public
   IR bloat, or hardwired semantic shortcut.
5. Documentation auditor: check roadmap, lowering docs, behavioral spec, open
   questions, design decisions, target architecture, pipeline design, testing
   strategy, and parity baselines for required updates or stale claims.
6. Evidence auditor: confirm the implementation and tests are justified by
   accepted M67/M68/M69/M70/M71 behavior plus the exact `array.tsl:105`
   backend-uninit request, and that backend translation map evidence remains
   a boundary constraint rather than a runtime dependency or output behavior.

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

Do not broaden M72 during revision.

If the verdict is `Return To Planner` or `Reject`, stop implementation. Create
the appropriate next planning or rollback prompt under `docs/agent/runs/` and
update `docs/agent/current-redesign-state.md` to point at it.

## Phase 5: Next Prompt Generation

If the final verdict is `Accept` or `Accept With Follow-Ups`:

- Record any non-blocking follow-ups.
- Update `docs/agent/current-redesign-state.md` so M72 is accepted.
- Create the next concrete prompt under `docs/agent/runs/`.
- If no post-M72 plan has been accepted, create a post-M72
  planning-plus-review prompt. Do not start M73.

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
