# Milestone 75 Execution Review Loop Prompt

You are the Codex orchestrator for the accepted M75 implementation and review
loop.

Read `docs/agent/current-redesign-state.md` first.

Do not start Milestone 76.

## Accepted State

Accepted through:

```text
Milestone 74
```

Post-M74 planning is accepted. It selected:

```text
Milestone 75: Exact Predicate Path Structural Request IR Slice
```

Human acceptance has been recorded. M75 execution is the active workflow
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

Consume accepted M74 exact array-body structural sequence state and produce one
typed predicate-path structural/request IR for the exact `array.tsl:106-110`
predicate path:

```text
slot 1: svbool_t pg = intrin<svptrue_b8>();
slot 2: accepted selected-body assignment envelope for pg = intrin<svptrue_b*>();
slot 3: intrin<svst1>(pg, tmp.data(), a);
```

M75 should connect the exact predicate initialization, accepted selected/no-body
predicate update evidence, and post-branch predicate-token use as typed
lowering state only. It must not define SVE predicate semantics, byte-size-to-
token inference, variable scope, store semantics, backend translation,
renderer-ready IR, or generated output.

## In Scope

- Consume accepted typed M74 `ExactArrayBodyStructuralSequenceIr` values, the
  `array_body_structural_sequence_classification` stage output, or a typed
  `LoweredImplementation` carrying exactly one accepted M74 structural
  sequence.
- Consume the accepted M63/M64 selected/no-body envelope reachable through the
  M74 selected-body role and the accepted M61/M62 selected assignment/direct-
  intrinsic body IR when present.
- Produce one typed IR value such as
  `ExactPredicatePathStructuralRequestIr`, carrying:
  - the source M74 structural sequence;
  - slot ordinal `1` as the exact predicate-init-shaped structural request
    source;
  - structural tokens `svbool_t`, `pg`, and unresolved direct-intrinsic
    request token `svptrue_b8` from the exact predicate-init shape;
  - the accepted selected-body predicate update request from the M63 selected
    body envelope when a selected body exists, preserving the already accepted
    unresolved token such as `svptrue_b16`, `svptrue_b32`, or `svptrue_b64`;
  - an explicit no-update state for accepted `NoSelectedBodyEnvelopeIr` cases;
  - slot ordinal `3` as the exact post-branch store-call-shaped structural
    source, recording only that the predicate argument token is the same `pg`;
  - deterministic provenance including candidate id, target/source extension
    where available, selected type tag, branch-chain id, M74 role identity,
    envelope/slot identity, and source locations.
- Append one deterministic stage after
  `array_body_structural_sequence_classification`, for example
  `predicate_path_structural_request_lowering`.
- Preserve accepted M57/M58/M59/M60/M61/M62/M63/M64/M65/M66/M67/M68/M69/M70/
  M71/M72/M73/M74 behavior and outputs.
- Use source text only as exact structural shape/provenance evidence. M75 must
  derive path membership from accepted M74 role identity and accepted M63/M62
  selected-body state, not from raw corpus line numbers, SVE token semantics,
  backend ids, renderer names, catalog data, or helper-string dispatch.
- Keep public IR additions narrow: at most one exact public predicate-path
  structural/request IR value and one exact stage/output pairing.

## Out Of Scope

- Interpreting `svbool_t`, `pg`, `intrin<svptrue_b8>`, selected
  `svptrue_b16/b32/b64`, `intrin<svst1>`, `tmp.data()`, `a`, `emit_return`,
  `assume_aligned`, stores, returns, direct intrinsics, SVE predicate/vector/
  register semantics, byte-size-to-token relationships, lane masks, backend
  uninit, backend maps, rendering, generated output, generic body/declaration/
  array semantics, allocation/lifetime, initializer behavior, variable scope,
  broad TSIL parsing, lowering-time file/catalog reads, `tsldata` reads during
  lowering evaluation, host CPU queries, backend map reads, or runtime
  dependency on `frozen/`.
- Generic predicate IR, broad variable/use-def analysis, generic call
  semantics, generic store-call IR, generic direct-intrinsic semantics,
  backend translation requests, renderer-ready values, generated artifacts,
  golden files, CLI/report/writer behavior, Rust behavior, compiler
  execution, or generated-test execution.
- Broad helper registries, raw helper-string dispatch, broad slot-role
  registries, broad stage registries, central semantic dispatchers, generic
  predicate/body/store registries, slot-role registries, public IR families
  beyond one exact predicate-path structural/request boundary, or hardwired
  semantic shortcuts keyed by helper text, selected type tags, SVE tokens,
  backend ids, renderer names, corpus line numbers, or request ordinals.

## Acceptance Criteria

- Direct resolver tests prove M75 consumes accepted M74 structural sequence
  state and produces the exact predicate-path structural/request IR.
- Normal `lower_candidates` pipeline tests prove the M75 stage appears after
  `array_body_structural_sequence_classification` and preserves M57-M74 stage
  ordering and outputs.
- Tests prove slot-1 predicate init, slot-2 accepted selected/no-body
  predicate update, and slot-3 predicate-token use all reference the same
  structural `pg` token without variable-scope, use-def, store, or SVE
  predicate semantics.
- Tests prove selected-body update request preservation for selected
  `svptrue_b16/b32/b64` tokens and explicit no-update preservation for
  `NoSelectedBodyEnvelopeIr` cases.
- Diagnostics cover unsupported source/container shapes, missing or duplicate
  M74 values, context mismatch, provenance mismatch, malformed exact
  predicate-init shape, malformed exact store-call predicate-token shape,
  selected-body target-token mismatch, selected-body provenance mismatch, and
  unsupported non-exact predicate-path shapes.
- Determinism tests cover repeated runs and reordered inputs.
- Regression tests prove M57-M74 behavior is unchanged.
- Regression tests prove no backend translation, rendering, generated output,
  golden-file churn, broad body/declaration/array/predicate/store lowering,
  generic parser, raw helper evaluator calls, raw helper parsing, catalog
  reads, `tsldata` reads, host CPU queries, backend map reads, or runtime
  `frozen/` use is introduced.

## Phase 1: Executor

If M75 is already implemented and awaiting review, skip implementation and go
directly to Phase 2.

If M75 is not implemented, spawn exactly one write-capable executor subagent.
Tell the executor:

- It is not alone in the codebase.
- It must not revert or overwrite edits made by others.
- It owns only the M75 implementation slice, directly related tests, and any
  necessary redesign-doc updates.
- It must not edit `docs/agent/current-redesign-state.md`.
- It must not create the next run prompt.
- It must keep M75 within the scope and out-of-scope boundaries above.
- It must consume accepted typed M74 structural sequence state and accepted
  M63/M62 selected/no-body predicate update evidence, not raw body text, line
  numbers, helper strings, SVE tokens, backend ids, renderer names, catalog
  data, or request ordinals as semantic dispatch keys.
- It must record only exact structural/request tokens and provenance for
  `svbool_t`, `pg`, `svptrue_b8`, selected `svptrue_b16/b32/b64`, and slot-3
  `pg`.
- It must keep the no-selected-body case explicit and must not synthesize a
  selected update for no-match cases.
- It must not infer byte-size-to-`svptrue_b*` relationships, SVE predicate
  meaning, variable scope, store semantics, `svst1`, `tmp.data()`, `a`,
  backend behavior, renderer-ready values, or generated output.
- It must avoid broad predicate/body/store IR, broad helper registries, raw
  helper-string dispatch, broad slot-role registries, broad stage registries,
  central semantic dispatchers, or hardwired semantic shortcuts.
- It must preserve accepted M57-M74 behavior and outputs.
- It must include explicit no-catalog-read, no-`tsldata`-read, no-host-CPU,
  no-backend-map, no-renderer, and no-`frozen/` coverage where practical
  during predicate-path structural request lowering.

The executor should report files changed, tests added or updated, validation
commands run, how the typed predicate-path structural/request IR is produced,
how structural tokens remain non-semantic provenance, how no hardwiring is
avoided, how M57-M74 behavior is preserved, and any follow-ups or blockers.

## Phase 2: Review And Audit Subagents

After execution, run read-only review/audit subagents using this workflow:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Validation auditor: verify required validation commands and assess test
   coverage for direct predicate-path structural/request lowering, normal
   `lower_candidates` pipeline behavior, stage order after M74, typed M74 and
   M63/M62 consumption, slot-1/slot-2/slot-3 `pg` path preservation,
   selected-body and no-selected-body cases, diagnostics, determinism,
   unchanged M57-M74 behavior, no generated output/golden churn, and no raw
   helper/file/catalog/`tsldata`/host CPU/backend-map/renderer/`frozen/`
   dependencies during lowering.
3. Boundary auditor: confirm M75 only produces exact predicate-path
   structural/request IR and does not add SVE predicate semantics,
   byte-size-to-token inference, variable scope, use-def analysis, store
   semantics, direct-intrinsic semantics, generic predicate/body/store IR,
   backend translation, backend maps, rendering, generated output, broad TSIL
   parsing, lowering-time file/catalog reads, `tsldata` reads during lowering
   evaluation, host CPU queries, or runtime `frozen/` use.
4. Extensibility auditor: confirm the integration uses accepted M74/M63/M62
   typed boundaries as maintainable attachment points without introducing
   broad IR families, broad registries, central dispatchers, raw-text
   evaluators, request-ordinal dispatch, or hardwired semantic shortcuts.
5. Documentation auditor: check roadmap, lowering docs, behavioral spec, open
   questions, design decisions, target architecture, pipeline design, testing
   strategy, and parity baselines for required updates or stale claims.
6. Evidence auditor: confirm the implementation and tests are justified by
   accepted M57-M74 behavior plus the exact `array.tsl:106-110` predicate-path
   evidence, and that source text is used only as provenance/invariant
   evidence rather than runtime semantic input.

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

Do not broaden M75 during revision.

If the verdict is `Return To Planner` or `Reject`, stop implementation. Create
the appropriate next planning or rollback prompt under `docs/agent/runs/` and
update `docs/agent/current-redesign-state.md` to point at it.

## Phase 5: Next Prompt Generation

If the final verdict is `Accept` or `Accept With Follow-Ups`:

- Record any non-blocking follow-ups.
- Update `docs/agent/current-redesign-state.md` so M75 is accepted.
- Create the next concrete prompt under `docs/agent/runs/`.
- If no post-M75 plan has been accepted, create a post-M75
  planning-plus-review prompt. Do not start M76.

The next prompt must follow `docs/agent/next-run-prompt-protocol.md`.

## Required Validation

Run targeted validation selected by the executor plus:

```bash
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

The final docs/state update in this prompt must also pass:

```bash
git diff --check
```

## Final Report

Report:

1. Whether implementation was skipped or exactly one write-capable executor
   was used.
2. Review/audit subagents used and consolidated verdict.
3. Files changed.
4. Validation commands and exact results.
5. Follow-ups recorded, if any.
6. Next prompt created.
7. Whether the repo is ready for the next workflow action.
