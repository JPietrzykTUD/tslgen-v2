# Milestone 76 Execution Review Loop Prompt

You are the Codex orchestrator for the accepted M76 implementation and review
loop.

Read `docs/agent/current-redesign-state.md` first.

Do not start Milestone 77.

## Accepted State

Accepted through:

```text
Milestone 75
```

Post-M75 planning is accepted. It selected:

```text
Milestone 76: Exact Post-Branch Intrinsic Call-Site Structural Request IR Slice
```

Human acceptance has been recorded. M76 execution is the active workflow
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

Consume accepted M75 exact predicate-path structural/request IR and produce one
typed structural/request IR value for the exact post-branch call-site shape at
`array.tsl:110`:

```text
intrin<svst1>(pg, tmp.data(), a);
```

M76 records only that the accepted post-branch slot is an exact
`intrin<...>(...)` call-shaped site with structural argument tokens and
provenance. It must not define store semantics, ARM/SVE intrinsic semantics,
memory behavior, `tmp.data()` semantics, operand semantics, backend
translation, renderer-ready IR, or generated output.

## In Scope

- Consume accepted typed M75 `ExactPredicatePathStructuralRequestIr` values,
  the `predicate_path_structural_request_lowering` stage output, or a typed
  `LoweredImplementation` carrying exactly one accepted M75 value.
- Consume accepted M74 exact array-body structural sequence state and accepted
  M73 declaration-shell state only through the accepted M75/M74 provenance
  chain.
- Produce one typed IR value such as
  `ExactPostBranchIntrinsicCallSiteStructuralRequestIr`, carrying:
  - the source M75 predicate-path value;
  - the source M74 structural sequence identity and exact post-branch slot
    identity for slot ordinal `3`;
  - structural call-head token `intrin`;
  - unresolved intrinsic token `svst1` as source evidence only;
  - argument ordinal `0` as structural token `pg`, linked to accepted M75
    slot-3 predicate-token use;
  - argument ordinal `1` as exact member-access-shaped structural token/path
    `tmp.data()`, linked only to accepted structural provenance for `tmp`
    where that provenance is already carried through M73/M74/M75;
  - argument ordinal `2` as structural source operand token `a`;
  - deterministic provenance including candidate id, target/source extension
    where available, selected type tag, branch-chain id, M74/M75 identity, and
    source locations.
- Append one deterministic generation-lowering stage after
  `predicate_path_structural_request_lowering`, for example
  `post_branch_intrinsic_call_site_structural_request_lowering`.
- Preserve accepted M57/M58/M59/M60/M61/M62/M63/M64/M65/M66/M67/M68/M69/M70/
  M71/M72/M73/M74/M75 behavior and outputs, including selected-branch
  diagnostics from earlier branch-pruning/lowering slices.
- Use source text only as exact structural shape/provenance evidence. M76 may
  enforce the selected exact corpus shape as an invariant for this slice, but
  it must not dispatch semantic behavior from raw helper text, intrinsic token
  text, SVE token text, backend ids, renderer names, catalog data, corpus line
  numbers, or request ordinals.
- Keep public IR additions narrow: at most one exact public call-site
  structural/request IR value and one exact stage/output pairing.

## Out Of Scope

- Store semantics, memory writes, alignment behavior, pointer semantics,
  operand semantics, variable scope/use-def/lifetime, declaration/array
  semantics, initializer behavior, return semantics, `emit_return`, or
  `assume_aligned`.
- Interpreting `svst1`, `pg`, `tmp.data()`, `a`, `svbool_t`, `svptrue_b*`, or
  any ARM/SVE predicate/vector/register/intrinsic behavior.
- Generic call IR, broad direct-intrinsic semantics, generic store-call IR,
  generic body IR, broad slot-role registries, broad helper registries, broad
  stage registries, central semantic dispatchers, or raw helper-string
  dispatch.
- Backend manifests, backend maps, language maps, translation maps, backend
  translation requests, renderer-ready values, generated artifacts, golden
  files, generated tests, CLI/report/writer behavior, Rust behavior, compiler
  execution, generated-test execution, broad TSIL parsing, lowering-time
  file/catalog reads, `tsldata` reads during lowering evaluation, host CPU
  queries, backend map reads, or runtime dependency on `frozen/`.
- Hardwired semantic shortcuts keyed by helper text, intrinsic token text,
  selected type tags, SVE tokens, backend ids, renderer names, corpus line
  numbers, or request ordinals.

## Acceptance Criteria

- Direct resolver tests prove M76 consumes accepted M75 predicate-path state
  and produces the exact post-branch intrinsic call-site structural/request IR.
- Normal `lower_candidates` pipeline tests prove the M76 stage appears after
  `predicate_path_structural_request_lowering` and preserves M57-M75 stage
  ordering and outputs.
- Tests prove argument `0` `pg` links to the accepted M75 slot-3 predicate
  token without predicate, SVE, or store semantics.
- Tests prove `svst1`, `tmp.data()`, and `a` are recorded only as structural
  tokens/provenance, with no ARM/SVE, memory, pointer, operand, variable-scope,
  or backend meaning.
- Diagnostics cover unsupported source/container shapes, missing or duplicate
  M75 values, context mismatch, provenance mismatch, missing M74 sequence
  provenance, malformed exact post-branch call shape, call-head token mismatch,
  unresolved intrinsic-token mismatch, argument-count mismatch,
  predicate-argument mismatch against M75, unsupported `tmp.data()` structural
  shape, unsupported source-operand token shape, and unsupported non-exact
  call-site shapes.
- Determinism tests cover repeated runs and reordered inputs.
- Regression tests prove M57-M75 behavior is unchanged, including
  selected-branch-only diagnostics.
- Regression tests prove no backend translation, rendering, generated output,
  golden-file churn, broad body/declaration/array/call/store lowering, generic
  parser, raw helper evaluator calls, raw helper parsing, catalog reads,
  `tsldata` reads, host CPU queries, backend map reads, or runtime `frozen/`
  use is introduced.

## Phase 1: Executor

If M76 is already implemented and awaiting review, skip implementation and go
directly to Phase 2.

If M76 is not implemented, spawn exactly one write-capable executor subagent.
Tell the executor:

- It is not alone in the codebase.
- It must not revert or overwrite edits made by others.
- It owns only the M76 implementation slice, directly related tests, and any
  necessary redesign-doc updates.
- It must not edit `docs/agent/current-redesign-state.md`.
- It must not create the next run prompt.
- It must keep M76 within the scope and out-of-scope boundaries above.
- It must consume accepted typed M75 predicate-path state and accepted M74/M73
  provenance, not raw body text, line numbers, helper strings, intrinsic text,
  SVE tokens, backend ids, renderer names, catalog data, or request ordinals
  as semantic dispatch keys.
- It must record only exact structural/request tokens and provenance for
  `intrin`, `svst1`, `pg`, `tmp.data()`, and `a`.
- It must link `pg` only to accepted M75 slot-3 predicate-token use.
- It must link `tmp.data()` only to accepted structural `tmp` provenance where
  that provenance is already carried through M73/M74/M75.
- It must not infer store semantics, ARM/SVE intrinsic meaning, memory
  behavior, pointer semantics, operand semantics, variable scope, backend
  behavior, renderer-ready values, or generated output.
- It must avoid generic call IR, generic store IR, broad helper registries, raw
  helper-string dispatch, broad slot-role registries, broad stage registries,
  central semantic dispatchers, or hardwired semantic shortcuts.
- It must preserve accepted M57-M75 behavior and outputs.
- It must include explicit no-catalog-read, no-`tsldata`-read, no-host-CPU,
  no-backend-map, no-renderer, and no-`frozen/` coverage where practical
  during post-branch intrinsic call-site structural request lowering.

The executor should report files changed, tests added or updated, validation
commands run, how the typed call-site structural/request IR is produced, how
structural tokens remain non-semantic provenance, how no hardwiring is avoided,
how M57-M75 behavior is preserved, and any follow-ups or blockers.

## Phase 2: Review And Audit Subagents

After execution, run read-only review/audit subagents using this workflow:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Validation auditor: verify required validation commands and assess test
   coverage for direct M76 call-site structural/request lowering, normal
   `lower_candidates` pipeline behavior, stage order after M75, typed M75 and
   M74/M73 provenance consumption, `pg` argument linkage, structural-only
   `svst1` / `tmp.data()` / `a` recording, diagnostics, determinism,
   unchanged M57-M75 behavior, selected-branch-only diagnostics, no generated
   output/golden churn, and no raw helper/file/catalog/`tsldata`/host CPU/
   backend-map/renderer/`frozen/` dependencies during lowering.
3. Boundary auditor: confirm M76 only produces exact post-branch intrinsic
   call-site structural/request IR and does not add store semantics, ARM/SVE
   intrinsic semantics, memory behavior, pointer semantics, operand semantics,
   variable scope/use-def analysis, generic call/store/body IR, backend
   translation, backend maps, rendering, generated output, broad TSIL parsing,
   lowering-time file/catalog reads, `tsldata` reads during lowering
   evaluation, host CPU queries, or runtime `frozen/` use.
4. Extensibility auditor: confirm the integration uses accepted M75/M74/M73
   typed boundaries as maintainable attachment points without introducing
   generic IR families, broad registries, central dispatchers, raw-text
   evaluators, request-ordinal dispatch, or hardwired semantic shortcuts.
5. Documentation auditor: check roadmap, lowering docs, behavioral spec, open
   questions, design decisions, target architecture, pipeline design, testing
   strategy, and parity baselines for required updates or stale claims.
6. Evidence auditor: confirm the implementation and tests are justified by
   accepted M57-M75 behavior plus the exact `array.tsl:110` call-site evidence,
   and that source text is used only as provenance/invariant evidence rather
   than runtime semantic input.

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

Do not broaden M76 during revision.

If the verdict is `Return To Planner` or `Reject`, stop implementation. Create
the appropriate next planning or rollback prompt under `docs/agent/runs/` and
update `docs/agent/current-redesign-state.md` to point at it.

## Phase 5: Next Prompt Generation

If the final verdict is `Accept` or `Accept With Follow-Ups`:

- Record any non-blocking follow-ups.
- Update `docs/agent/current-redesign-state.md` so M76 is accepted.
- Create the next concrete prompt under `docs/agent/runs/`.
- If no post-M76 plan has been accepted, create a post-M76
  planning-plus-review prompt. Do not start M77.

## Required Validation

Run at minimum:

```bash
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

Also run a focused M76 exact post-branch intrinsic call-site
structural/request test command selected by the executor.

## Final Report

Report:

1. Executor used, or whether implementation was skipped because M76 was already
   implemented and awaiting review.
2. Review/audit subagents used.
3. Files changed.
4. Tests and validation commands with exact results.
5. Consolidated verdict.
6. Follow-ups recorded, if any.
7. Next prompt created.
8. State transition made.
9. Whether the repo is ready for the next action.
