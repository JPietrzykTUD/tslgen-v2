# Milestone 70 Execution Review Loop Prompt

You are the Codex orchestrator for the accepted M70 implementation and review
loop.

Read `docs/agent/current-redesign-state.md` first.

Do not start Milestone 71.

## Accepted State

Accepted through:

```text
Milestone 69
```

Post-M69 planning is accepted. It selected:

```text
Milestone 70: Exact Array Initialization Vector-Length Request Resolution Slice
```

Internal planning review returned:

```text
Accept With Follow-Ups
```

Human acceptance has been recorded. M70 execution is the active workflow
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
value<generation>(vector::length)
```

The resolution must run through the accepted M69 extracted
array-initialization stage pipeline and consume explicit typed vector-length
metadata supplied before lowering evaluation.

M70 is generation-time lowering request resolution only. It consumes lane facts
as typed inputs; it does not compute or infer them from raw text, SVE tokens,
extension names, vector-bit strings, selected type tags, scalar sizes, host CPU
state, catalog data, backend maps, renderer names, or `candidate_id` parsing.

## In Scope

- Consume accepted M67 `ExactArrayInitializationHelperRequestIr` request
  records through the accepted M68/M69 array-initialization pipeline after
  `array_initialization_base_type_request_resolution`.
- Select only the M67 request record whose kind/leaf identify the exact
  `value<generation>(vector::length)` helper.
- Introduce or consume explicit typed vector-length metadata input, supplied
  before lowering evaluation through `LoweringRequest`, `GenerationContext`,
  or an equivalent typed request/context value.
- Use typed candidate context fields such as candidate id, target extension,
  source extension, and selected type tag as structured fields.
- Produce a narrow typed result, for example
  `ExactArrayInitializationVectorLengthResolutionIr`, carrying:
  - the source M68 base-type resolution;
  - the source M67 vector-length request record;
  - a typed vector-length value or policy value;
  - remaining unresolved requests for vector alignment and backend uninit;
  - deterministic provenance including candidate, type, envelope/slot, and
    source location facts.
- Add one deterministic generation-lowering stage after
  `array_initialization_base_type_request_resolution`, for example
  `array_initialization_vector_length_request_resolution`.
- Preserve accepted M68 base-type behavior and accepted M69 stage-pipeline
  behavior.
- Add explicit pipeline-level M67 diagnostic propagation coverage because M70
  extends the extracted M69 pipeline.

## Out Of Scope

- Resolution of `value<generation>(vector::alignment)` or
  `value<backend>(uninit::array)`.
- Broad vector/register metadata semantics, SVE predicate semantics, register
  type lowering, byte-size-to-`svptrue_b*` inference, or lane-count inference
  from `vector_bits`, scalar byte size, selected type tag, extension name, SVE
  token text, backend id, renderer name, catalog data, `tsldata`, or host CPU
  state during lowering.
- Backend translation or backend rendering of vector length, including C++
  spellings such as `Vec::vector_element_count()`.
- Broad `var`, `array_type`, declaration, array allocation/lifetime, variable
  scope, store, return, `tmp.data()`, `emit_return`, direct-intrinsic
  semantics, loops, calls, casts, or broad TSIL parsing.
- Generic `value<generation>(...)` evaluator families, broad stage registries,
  broad vector metadata resolvers, raw helper-string dispatch, or semantic
  tables keyed by raw helper text, request ordinals, selected type tags, SVE
  tokens, backend ids, or renderer names.
- Generated C++ or Rust output, generated tests, golden output,
  CLI/reporting/writer behavior, compiler execution, lowering-time file/catalog
  reads, raw TSL parsing, `tsldata` reads during lowering evaluation, host CPU
  queries, or runtime `frozen/` use.

## Acceptance Criteria

- Direct resolver tests prove the M67/M68 vector-length request resolves from
  explicit typed vector-length metadata.
- Normal `lower_candidates` pipeline tests prove the M70 stage appears after
  `array_initialization_base_type_request_resolution` and preserves accepted
  M69 ordering and outputs.
- Static metadata and runtime/scalable metadata behavior is explicit. Runtime/
  scalable metadata must be represented as a typed value/policy or rejected
  with diagnostics; it must not become a fake fixed integer lane count.
- Diagnostics cover missing metadata, duplicate/conflicting metadata,
  unsupported runtime/scalable numeric resolution, mismatched selected
  candidate context, malformed/missing/multiple vector-length request records,
  unsupported source stage, and provenance mismatch.
- Determinism tests cover repeated runs and reversed metadata input order.
- Regression tests prove vector alignment and backend uninit remain unresolved.
- Regression tests prove accepted M68 base-type behavior is unchanged.
- Regression tests prove raw helper evaluators are not called on M67 leaf text,
  raw helper text is not parsed, and no catalog, `tsldata`, host CPU, backend
  translation, rendering, generated output, or golden-file behavior is
  introduced.
- Pipeline-level M67 diagnostic propagation coverage is explicit.

## Phase 1: Executor

If M70 is already implemented and awaiting review, skip implementation and go
directly to Phase 2.

If M70 is not implemented, spawn exactly one write-capable executor subagent.
Tell the executor:

- It is not alone in the codebase.
- It must not revert or overwrite edits made by others.
- It owns only the M70 implementation slice, directly related tests, and any
  necessary redesign-doc updates.
- It must not edit `docs/agent/current-redesign-state.md`.
- It must not create the next run prompt.
- It must keep M70 within the scope and out-of-scope boundaries above.
- It must consume typed M67/M68/M69 request/result values and explicit typed
  vector-length metadata supplied before lowering evaluation.
- It must not derive semantic vector-length values from raw helper text,
  M66 slot text, M67 leaf text, raw TSIL, raw TSL, `candidate_id`, SVE tokens,
  extension names, vector-bit strings, selected type tags, scalar sizes,
  backend ids, renderer names, catalog data, `tsldata`, host CPU state, or
  runtime `frozen/`.
- It must preserve vector alignment and backend uninit as unresolved.
- It must preserve accepted M68 base-type behavior and accepted M69
  stage-pipeline behavior.
- It must include pipeline-level M67 diagnostic propagation coverage.

The executor should report files changed, tests added or updated, validation
commands run, how typed metadata enters before lowering evaluation, how raw
helper dispatch and lane hardwiring are avoided, how scalable/runtime-lane
metadata is handled, how unresolved vector alignment/backend uninit requests
remain unresolved, and any follow-ups or blockers.

## Phase 2: Review And Audit Subagents

After execution, run read-only review/audit subagents using this workflow:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Validation auditor: verify required validation commands and assess test
   coverage for direct resolver behavior, normal `lower_candidates` pipeline
   behavior, stage order, explicit metadata input, runtime/scalable metadata
   policy or diagnostics, deterministic ordering, M67 diagnostic propagation,
   unchanged M68/M69 behavior, unresolved alignment/backend-uninit requests,
   no generated output/golden churn, and no raw helper/file/catalog/host CPU
   dependencies during lowering.
3. Boundary auditor: confirm M70 resolves only the exact vector-length request
   and does not add vector alignment/backend uninit resolution, broad vector
   metadata semantics, raw helper parsing/evaluation, backend translation,
   rendering, generated output, broad TSIL parsing, lowering-time file/catalog
   reads, `tsldata` reads during lowering evaluation, host CPU queries, or
   runtime `frozen/` use.
4. Extensibility auditor: confirm the integration uses the M69 extracted
   pipeline as a maintainable typed attachment point without introducing a
   broad registry, central dispatcher, raw-text evaluator, public IR expansion,
   or hardwired semantic shortcut.
5. Documentation auditor: check roadmap, lowering docs, behavioral spec, open
   questions, design decisions, target architecture, pipeline design, testing
   strategy, and parity baselines for required updates or stale claims.
6. Evidence auditor: confirm the implementation and tests are justified by
   accepted M67/M68/M69 behavior plus the exact `array.tsl:105` request, and
   that SVE/runtime-lane evidence and backend translation evidence remain
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

Do not broaden M70 during revision.

If the verdict is `Return To Planner` or `Reject`, stop implementation. Create
the appropriate next planning or rollback prompt under `docs/agent/runs/` and
update `docs/agent/current-redesign-state.md` to point at it.

## Phase 5: Next Prompt Generation

If the final verdict is `Accept` or `Accept With Follow-Ups`:

- Record any non-blocking follow-ups.
- Update `docs/agent/current-redesign-state.md` so M70 is accepted.
- Create the next concrete prompt under `docs/agent/runs/`.
- If no post-M70 plan has been accepted, create a post-M70
  planning-plus-review prompt. Do not start M71.

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
