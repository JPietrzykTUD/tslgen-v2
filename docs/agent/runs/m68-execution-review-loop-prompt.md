# Milestone 68 Execution Review Loop Prompt

You are executing and reviewing:

```text
Milestone 68: Exact Array Initialization Base-Type Helper Request Resolution Slice
```

Milestones 1 through 67 are accepted. Post-M67 planning is accepted and
selected M68. Do not start any later milestone.

User acceptance included an explicit condition: ensure no hardwiring. Treat
that as a blocking M68 boundary.

Use the orchestrated executor-review loop described here. Do not skip state or
next-prompt updates unless this prompt explicitly records a stop condition.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/codex-workflow.md`
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

## Milestone Scope

Implement the smallest generation-time/body-lowering request-resolution slice
that consumes accepted M67 exact array-initialization helper request IR and
resolves only the base-type request for `type<generation>(base::in)`.

M68 must:

- Consume accepted M67 `ExactArrayInitializationHelperRequestIr` values, the
  `array_initialization_helper_request_lowering` stage output, or a typed
  `LoweredImplementation` carrying exactly one accepted M67
  `array_initialization_helper_requests` entry.
- Select exactly the M67 base-type request record:
  - request ordinal `0`;
  - request kind `generation_type`;
  - helper leaf kind `type_generation_base_in`;
  - source text `type<generation>(base::in)` as provenance/invariant evidence
    only.
- Produce an immutable typed result value, for example
  `ExactArrayInitializationBaseTypeResolutionIr`, keyed to the M67 request IR
  and source base-type request record.
- Carry a typed base-type result equivalent to
  `GenerationTypeRef(kind="base.in", type_tag=<selected type tag>)`.
- Use accepted M43/M52/M53/M54 selected type context and concrete integer
  generation rule semantics through typed lowering request/context inputs.
- Preserve source M67 request IR, source request record, leaf source text as
  provenance only, source locations, candidate id, selected type tag,
  branch-chain identity, envelope identity, slot ordinal, variable token
  `tmp`, and deterministic result ordering.
- Preserve the remaining M67 requests for vector length, vector alignment, and
  backend uninit as unresolved request/provenance records.
- Append a distinct deterministic lowering stage after
  `array_initialization_helper_request_lowering`, for example
  `array_initialization_base_type_request_resolution`.
- Produce structured diagnostics for invalid M68 boundary/request state.

M68 is request-resolution only. It is not generic helper evaluation, vector
metadata resolution, backend uninit semantics, declaration/array semantics,
backend translation, renderer preparation, or output generation.

## No-Hardwiring Rule

M68 must not hardwire request resolution.

Hardwiring includes:

- raw text dispatch from `leaf_source_text`, `original_slot_text`, raw TSIL,
  raw TSL, or helper strings;
- ad-hoc tables or `if`/`elif` branches mapping raw helper text, selected type
  tags, or request ordinals directly to semantic outputs;
- bypassing accepted typed generation-rule/context inputs because the selected
  type tag "looks concrete";
- calling raw query-string helper evaluators on M67 leaf text as a shortcut;
- using `Catalog`, file reads, `tsldata`, or `frozen/` during lowering
  evaluation to reconstruct semantics.

The implementation must consume typed M67 request records and accepted typed
rule/context inputs. Source text is provenance and invariant evidence only.

## Acceptance Criteria

M68 must satisfy these criteria:

- Direct M68 lowering from an accepted M67
  `ExactArrayInitializationHelperRequestIr` produces exactly one typed
  base-type request-resolution IR value.
- The M68 result wraps or carries a typed value equivalent to
  `GenerationTypeRef(kind="base.in", type_tag=<selected type tag>)`.
- Normal `lower_candidates` with typed M65/M66/M67 input carries M68
  base-type resolution IR and appends
  `array_initialization_base_type_request_resolution` immediately after
  `array_initialization_helper_request_lowering`.
- Previous M57-M67 stage order remains unchanged before the new M68 stage.
- M68 consumes typed M67 request records, not raw M66 slot text, raw M67 leaf
  text, raw helper strings, raw TSIL, raw TSL, or catalog/file input.
- M68 uses accepted M43/M52/M53/M54 typed base-type semantics and selected
  type context supplied through lowering request/context inputs.
- M68 does not use hardcoded mappings from selected type tag, request ordinal,
  or helper text to semantic result.
- Vector length, vector alignment, and backend uninit M67 requests remain
  unresolved and unchanged.
- The output preserves source M67 request IR, source request record, leaf
  source text as provenance only, source locations, candidate id, selected
  type tag, branch-chain identity, envelope identity, slot ordinal, variable
  token `tmp`, and deterministic result ordering.
- Unsupported source stage/type, missing or multiple M67 request IR values,
  missing base-type request, duplicate base-type request, mismatched
  ordinal/kind/leaf kind, unsupported base-type request text, unsupported
  selected type, and provenance mismatch produce structured diagnostics with
  source locations and actionable messages.
- Existing M57/M58/M59/M60/M61/M62/M63/M64/M65/M66/M67 behavior remains
  unchanged.
- Backend translation still rejects raw unresolved generation helpers.
- Renderers still do not evaluate generation helpers.
- No generated output, generated tests, golden fixtures, CLI/report/writer,
  Rust, or compiler behavior changes.

## Out Of Scope

M68 must not add:

- Raw query-string evaluation of M67 leaf text.
- Raw helper parsing, raw string dispatch, broad helper-expression parsing, or
  a generic helper request resolver.
- Ad-hoc hardcoded tables or branch chains mapping selected type tags,
  request ordinals, or helper text directly to resolved values.
- Resolution of `base.signed_of`, `base.unsigned_of`, or any M43 type query
  family other than the exact M67 `type<generation>(base::in)` request.
- Resolution of `value<generation>(vector::length)`,
  `value<generation>(vector::alignment)`, or
  `value<backend>(uninit::array)`.
- `GenerationValue`, vector metadata values, backend uninit values, backend
  translation requests, renderer-ready IR, generated output, or generated
  tests.
- Generic `var` parsing, generic `array_type` parsing, broad declaration
  semantics, array allocation/lifetime semantics, variable binding/scope,
  array type/value semantics, or statement IR.
- Predicate-initialization slot lowering, selected-body slot changes, store
  slot lowering, return slot lowering, `tmp.data()` semantics, or
  `emit_return` semantics.
- SVE predicate/vector/register semantics, direct-intrinsic semantics,
  byte-size-to-`svptrue_b*` token inference, backend intrinsic IR, backend
  translation requests, translation-map evaluation, rendering, generated
  C++/Rust output, generated tests, CLI/reporting/writer behavior, compiler
  execution, or Rust.
- Producing or recognizing M66/M67 forms from raw payload text.
- Broad TSIL parsing, lowering-time file reads, catalog queries during
  evaluation, raw TSL parsing, runtime `frozen/` evidence, raw-string dispatch
  tables, or backend-specific branches.

## Evidence

Use accepted implementation and tests for:

- M43 `GenerationTypeRef(kind="base.in")` behavior.
- M52 concrete integer type/signedness expansion.
- M53 typed concrete integer generation rule source.
- M54 catalog-derived rule wiring into lowering inputs.
- M57 `GenerationPredicate(kind="type.size_bytes.equals")`.
- M58 typed `GenerationLoweringStage` records.
- M59 typed size-byte branch-chain pruning.
- M60 typed opaque selected-body handoff and no-selected-body behavior.
- M61 typed selected-body assignment-form recognition.
- M62 typed selected assignment/direct-intrinsic body IR and no-body-IR
  behavior.
- M63 typed selected-body envelope and no-body envelope behavior.
- M64 typed exact array-body skeleton/envelope assembly, opaque slot
  preservation, selected/no-body handling, deterministic stage construction,
  and boundary diagnostics.
- M65 normal lowering pipeline integration for
  `LoweredImplementation.array_body_envelopes`.
- M66 exact array-initialization slot form IR and unresolved helper leaves.
- M67 exact array-initialization helper request IR,
  `array_initialization_helper_request_lowering` stage output, and unresolved
  vector/backend request preservation.

Use current corpus evidence:

- `tsldata/primitives/load_store/array.tsl:105` for the exact first-slot
  `type<generation>(base::in)` helper request evidence.
- `tsldata/primitives/load_store/array.tsl:105-111` only as context that this
  slot is part of the accepted M64/M65 five-slot envelope.

No new `frozen/` evidence is required. Do not introduce any runtime dependency
on `frozen/`.

## Phase 1: Executor

If M68 is already implemented and awaiting review, skip implementation and go
directly to Phase 2.

If M68 is not implemented, spawn exactly one write-capable executor subagent.
Tell the executor:

- It is not alone in the codebase.
- It must not revert or overwrite edits made by others.
- It owns only the M68 implementation slice, directly related tests, and any
  necessary redesign-doc updates.
- It must not edit `docs/agent/current-redesign-state.md`.
- It must not create the next run prompt.
- It must keep M68 within the scope, no-hardwiring rule, and out-of-scope
  boundaries above.
- It must consume typed M67 request/stage outputs, not raw slot text or raw
  helper strings.
- It must resolve only the M67 base-type request record.
- It must use accepted typed generation rule/context inputs rather than
  hardcoded selected-type mappings.
- It must preserve vector length, vector alignment, and backend uninit
  requests as unresolved.
- It must add structured diagnostics/tests for unsupported source stage/type,
  missing or multiple M67 request IR values, missing base-type request,
  duplicate base-type request, mismatched ordinal/kind/leaf kind, unsupported
  base-type request text, unsupported selected type, provenance mismatch, and
  no-hardwiring/no-raw-helper-evaluation boundaries.
- It must not evaluate or resolve vector/backend helpers, call raw
  query-string helper evaluators on M67 leaf text, create backend translation
  requests, add broad declaration/array/variable semantics, lower store/return
  slots, add SVE/direct-intrinsic/backend semantics, render output, or parse
  broad TSIL.

The executor should report files changed, tests added or updated, validation
commands run, how typed M67 inputs are consumed, how hardwiring is avoided,
how raw helper dispatch is avoided, how unresolved requests remain
unresolved, and any follow-ups or blockers.

## Phase 2: Review And Audit Subagents

After execution, run read-only review/audit subagents using the specified
subagent workflow:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Validation auditor: verify the required validation commands and assess test
   coverage for direct/stage/`LoweredImplementation` M68 sources, exact
   base-type request resolution, no-hardwiring/no-raw-helper-evaluation
   boundaries, unsupported source/request/provenance diagnostics,
   deterministic stage ordering, unchanged M57-M67 behavior, backend
   raw-helper rejection, renderer non-evaluation, determinism, and no
   generated output/golden churn.
3. Boundary auditor: confirm M68 implements only typed base-type request
   resolution over M67 IR and does not add hardcoded mappings, raw helper
   parsing/evaluation, vector/backend helper resolution, broad
   declaration/array semantics, store/return lowering,
   SVE/direct-intrinsic/backend/rendering/output work, generated tests,
   CLI/reporting, writer behavior, Rust, compiler execution, runtime
   `frozen/`, or lowering-time file/catalog reads.
4. Extensibility auditor: confirm the integration keeps the staged body
   lowering pipeline maintainable, consumes M67 request IR, avoids central
   hardwired dispatchers, preserves M67 request provenance, and leaves future
   vector/backend helper resolver stages room to follow the same typed request
   pattern.
5. Documentation auditor: check roadmap, lowering docs, behavioral spec, open
   questions, design decisions, target architecture, pipeline design, testing
   strategy, and parity baselines for required updates or stale claims.
6. Evidence auditor: confirm the implementation and tests are justified by
   accepted M43/M52/M53/M54 and M57-M67 behavior plus `array.tsl:105`, and
   that leaf text is used only as typed M67 provenance.

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

Do not broaden M68 during revision.

If the verdict is `Return To Planner` or `Reject`, stop implementation. Create
the appropriate next planning or rollback prompt under `docs/agent/runs/` and
update `docs/agent/current-redesign-state.md` to point at it.

## Phase 5: Next Prompt Generation

If the final verdict is `Accept` or `Accept With Follow-Ups`:

- Record any non-blocking follow-ups.
- Update `docs/agent/current-redesign-state.md` so M68 is accepted.
- Create the next concrete prompt under `docs/agent/runs/`.
- If no post-M68 plan has been accepted, create a post-M68
  planning-plus-review prompt. Do not start M69.

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
