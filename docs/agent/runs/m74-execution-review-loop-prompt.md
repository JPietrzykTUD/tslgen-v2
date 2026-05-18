# Milestone 74 Execution Review Loop Prompt

You are the Codex orchestrator for the accepted M74 implementation and review
loop.

Read `docs/agent/current-redesign-state.md` first.

Do not start Milestone 75.

## Accepted State

Accepted through:

```text
Milestone 73
```

Post-M73 planning is accepted. It selected:

```text
Milestone 74: Exact Array Body Structural Sequence And Slot-Role Classification Slice
```

Internal planning review returned:

```text
Accept With Follow-Ups
```

Human acceptance has been recorded. M74 execution is the active workflow
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

Consume accepted M64/M65 exact array-body envelope state and the accepted M73
first-slot declaration-shell IR, then produce one typed source-ordered
structural sequence for the exact `array.tsl:105-111` body:

```text
slot 0: first-slot declaration shell from M73
slot 1: opaque predicate-init-shaped structural role
slot 2: selected-body envelope structural role
slot 3: opaque post-branch store-call-shaped structural role
slot 4: opaque return-emission-shaped structural role
```

M74 is generation-time lowering structural/provenance IR only. Slot-role
classification names accepted exact body positions; it must not define
executable statement kinds, generic body IR, declaration/array semantics,
variable scope, allocation/lifetime, initializer behavior, predicate
semantics, store/return semantics, direct-intrinsic/SVE semantics, backend
translation, renderer-ready IR, or generated output.

## In Scope

- Consume accepted typed M64/M65 `ExactArrayBodyEnvelopeIr` values, the
  `array_body_envelope_slot_assembly` stage output, accepted typed M73
  `ExactArrayInitializationDeclarationShellIr` values, the
  `array_initialization_declaration_shell_lowering` stage output, or a typed
  `LoweredImplementation` carrying exactly one matching M64/M65 envelope and
  one matching M73 declaration shell.
- Produce one typed structural IR value such as
  `ExactArrayBodyStructuralSequenceIr`, carrying:
  - the source M64/M65 exact array-body envelope;
  - the accepted M73 declaration-shell IR attached only to slot ordinal `0`;
  - the accepted M63 selected/no-body envelope through the M64 selected-body
    envelope slot;
  - one source-ordered five-entry structural/provenance role sequence;
  - role labels for first-slot declaration shell, opaque predicate-init-shaped
    slot, selected-body envelope slot, opaque post-branch store-call-shaped
    slot, and opaque return-emission-shaped slot;
  - opaque source/provenance for the non-first slots without interpreting
    their text;
  - deterministic provenance including candidate id, selected type tag,
    target/source extension where available, branch-chain id, envelope/slot
    identity, role ordinal, and source locations.
- Append one deterministic stage after
  `array_initialization_declaration_shell_lowering`, for example
  `array_body_structural_sequence_classification`.
- Preserve accepted M63/M64/M65/M66/M67/M68/M69/M70/M71/M72/M73 behavior and
  outputs.
- Use source text only as provenance/invariant evidence. M74 must derive
  roles from accepted typed envelope slot identity and provenance, not from
  raw body text, corpus line numbers, SVE tokens, backend ids, renderer names,
  catalog data, or helper strings.
- Keep public IR additions narrow: at most one exact public structural
  sequence IR value and one exact stage/output pairing.

## Out Of Scope

- Interpreting `svbool_t`, `pg`, `intrin<svptrue_b8>`, selected
  `svptrue_b16/b32/b64`, `intrin<svst1>`, `tmp.data()`, `a`,
  `emit_return(tmp)`, `assume_aligned`, stores, returns, direct intrinsics,
  SVE predicate/vector/register semantics, byte-size-to-token inference, or
  branch-body semantics beyond accepted M57-M63.
- Generic body IR, broad TSIL parsing, generic declaration semantics, generic
  array semantics, generic variable semantics, allocation/lifetime, variable
  binding/scope, initializer semantics, statement execution order semantics,
  store semantics, return semantics, or multi-statement lowering.
- Backend manifests, backend maps, language maps, translation maps, backend
  uninit translation, backend translation requests, renderer-ready values,
  renderer calls, generated artifacts, golden files, CLI/report/writer
  behavior, Rust behavior, compiler execution, or generated-test execution.
- Broad helper registries, raw helper-string dispatch, broad body/slot
  registries, slot-role registries, broad stage registries, semantic
  dispatchers, lowering-time file/catalog reads, raw TSL parsing, `tsldata`
  reads during lowering evaluation, host CPU queries, backend map reads, or
  runtime dependency on `frozen/`.
- Public IR families beyond the exact selected structural sequence boundary
  value, including generic `BodyIr`, generic declaration/array IR families,
  per-role public tuples, or registry-backed role systems.

## Acceptance Criteria

- Direct resolver tests prove M74 consumes accepted M64/M65 envelope state plus
  accepted M73 declaration-shell IR and produces the exact array-body
  structural sequence IR.
- Normal `lower_candidates` pipeline tests prove the M74 stage appears after
  `array_initialization_declaration_shell_lowering` and preserves M63-M73
  ordering and outputs.
- Tests prove exact five-entry role order, M73 shell linkage only to slot `0`,
  M63 selected/no-body envelope linkage only to the selected-body slot, and
  opaque preservation of predicate-init, post-branch store-call, and
  return-emission slot text/provenance without interpreting it.
- Diagnostics cover unsupported source/container shapes, missing or duplicate
  envelope/declaration-shell values, context mismatch, provenance mismatch,
  role/order mismatch, malformed exact five-slot sequence invariants, and
  unsupported non-exact body shapes.
- Determinism tests cover repeated runs and reordered inputs.
- Regression tests prove M63/M64/M65/M66/M67/M68/M70/M71/M72/M73 behavior is
  unchanged.
- Regression tests prove no backend translation, rendering, generated output,
  golden-file churn, broad body/declaration/array lowering, generic parser,
  raw helper evaluator calls, raw helper parsing, catalog reads, `tsldata`
  reads, host CPU queries, backend map reads, or runtime `frozen/` use is
  introduced.

## Phase 1: Executor

If M74 is already implemented and awaiting review, skip implementation and go
directly to Phase 2.

If M74 is not implemented, spawn exactly one write-capable executor subagent.
Tell the executor:

- It is not alone in the codebase.
- It must not revert or overwrite edits made by others.
- It owns only the M74 implementation slice, directly related tests, and any
  necessary redesign-doc updates.
- It must not edit `docs/agent/current-redesign-state.md`.
- It must not create the next run prompt.
- It must keep M74 within the scope and out-of-scope boundaries above.
- It must consume accepted typed M64/M65 envelope state and accepted typed M73
  declaration-shell IR, not raw body text, line numbers, helper strings, SVE
  tokens, backend ids, renderer names, or catalog data.
- It must attach the accepted M73 declaration shell only to slot ordinal `0`
  and preserve the accepted M63/M64 selected/no-body envelope only in the
  selected-body slot.
- It must preserve non-first slots as opaque/unresolved structural evidence.
- It must not interpret predicate-init, selected-body, store-call, or
  return-emission roles as executable statements, SVE/direct-intrinsic
  semantics, store semantics, return semantics, variable scope, allocation,
  lifetime, initializer semantics, backend translation, rendering, or
  generated output.
- It must avoid broad `BodyIr` public families, per-role public tuple
  families, slot-role registries, broad body/slot registries, broad stage
  registries, raw helper-string dispatch, or central semantic shortcuts.
- It must preserve accepted M63/M64/M65/M66/M67/M68/M69/M70/M71/M72/M73
  behavior and outputs.
- It must include explicit no-catalog-read, no-`tsldata`-read, no-host-CPU,
  no-backend-map, no-renderer, and no-`frozen/` coverage where practical
  during structural sequence classification.

The executor should report files changed, tests added or updated, validation
commands run, how the typed structural sequence IR is produced, how role labels
stay structural/provenance-only, how non-first slots remain opaque, how raw
helper dispatch and hardwiring are avoided, how M63-M73 behavior is preserved,
and any follow-ups or blockers.

## Phase 2: Review And Audit Subagents

After execution, run read-only review/audit subagents using this workflow:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Validation auditor: verify required validation commands and assess test
   coverage for direct structural sequence lowering, normal
   `lower_candidates` pipeline behavior, stage order after M73, typed
   M64/M65/M73 consumption, exact five-entry role order, M73 shell slot-0
   linkage, selected-body envelope linkage, opaque non-first-slot
   preservation, diagnostics, determinism, unchanged M63/M64/M65/M66/M67/M68/
   M69/M70/M71/M72/M73 behavior, no generated output/golden churn, and no raw
   helper/file/catalog/`tsldata`/host CPU/backend-map/renderer/`frozen/`
   dependencies during lowering.
3. Boundary auditor: confirm M74 only produces exact array-body
   structural/provenance sequence IR and does not add executable statement
   semantics, generic body IR, declaration/array semantics, variable scope,
   allocation/lifetime, initializer behavior, predicate semantics,
   store/return semantics, `tmp.data()`, `emit_return`, `assume_aligned`,
   direct-intrinsic/SVE semantics, backend-uninit translation, backend maps,
   backend rendering, generated output, broad TSIL parsing, lowering-time
   file/catalog reads, `tsldata` reads during lowering evaluation, host CPU
   queries, or runtime `frozen/` use.
4. Extensibility auditor: confirm the integration uses the M64/M65/M73 typed
   boundaries as maintainable attachment points without introducing broad IR
   families, per-role public tuples, slot-role registries, broad stage
   registries, central dispatchers, raw-text evaluators, or hardwired semantic
   shortcuts.
5. Documentation auditor: check roadmap, lowering docs, behavioral spec, open
   questions, design decisions, target architecture, pipeline design, testing
   strategy, and parity baselines for required updates or stale claims.
6. Evidence auditor: confirm the implementation and tests are justified by
   accepted M63/M64/M65/M66/M67/M68/M69/M70/M71/M72/M73 behavior plus the
   exact `array.tsl:105-111` body evidence, and that source text is used only
   as provenance/invariant evidence rather than runtime semantic input.

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

Do not broaden M74 during revision.

If the verdict is `Return To Planner` or `Reject`, stop implementation. Create
the appropriate next planning or rollback prompt under `docs/agent/runs/` and
update `docs/agent/current-redesign-state.md` to point at it.

## Phase 5: Next Prompt Generation

If the final verdict is `Accept` or `Accept With Follow-Ups`:

- Record any non-blocking follow-ups.
- Update `docs/agent/current-redesign-state.md` so M74 is accepted.
- Create the next concrete prompt under `docs/agent/runs/`.
- If no post-M74 plan has been accepted, create a post-M74
  planning-plus-review prompt. Do not start M75.

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
