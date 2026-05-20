# M95 Execution Review Loop Prompt

You are executing and reviewing the accepted Milestone 95.

Milestones 1 through 94 are accepted. Post-M94 planning is accepted and
selected:

```text
Milestone 95: Selected-Body Direct-Intrinsic Operation Package Slice
```

Use the orchestrated executor-review loop in this prompt. M95 is an
implementation milestone; one write-capable executor may implement the
selected slice. Do not start post-M95 planning until M95 review returns
`Accept` or `Accept With Follow-Ups`.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/agent/review-checklist.md`
- `docs/agent/subagents/`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/generation-time-semantic-lowering.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/open-questions.md`
- `tslgen/src/tslgen/lowering/boundary.py`
- `tslgen/src/tslgen/lowering/_operation_package.py`
- `tslgen/src/tslgen/lowering/_operation_package_sources.py`
- `tslgen/src/tslgen/lowering/_operation_package_models.py`
- `tslgen/src/tslgen/lowering/_operation_package_diagnostics.py`
- `tslgen/src/tslgen/lowering/_operation_package_mini_tsil.py`
- `tslgen/src/tslgen/lowering/_operation_package_exact_array.py`
- `tslgen/src/tslgen/lowering/_selected_body_models.py`
- `tslgen/src/tslgen/lowering/_selected_body_lowering.py`
- `tslgen/src/tslgen/lowering/_stage_contracts.py`
- `tslgen/src/tslgen/lowering/_pipeline.py`
- `tslgen/src/tslgen/lowering/__init__.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Goal

Add one focused Stage 8 lowering operation-package family for already accepted
selected-body direct-intrinsic facts.

M95 proves the post-M94 operation-package design can grow by family-specific
typed ownership without turning `_operation_package_sources.py` into a generic
source protocol, callback map, registry, or dispatcher.

## Scope

- Consume only accepted M63 `SelectedBodyEnvelopeIr` values from the
  `selected_body_envelope_lowering` stage or equivalent narrow typed
  container input.
- Preserve the enclosed accepted M62 `SelectedAssignmentDirectIntrinsicBodyIr`
  as the source of typed selected-body direct-intrinsic provenance.
- Add exactly one operation-package source family, such as
  `selected_body_direct_intrinsic`, with one focused package entry for the
  exact singleton selected-body assignment/direct-intrinsic envelope already
  accepted by M62/M63.
- Preserve candidate id, selected type tag, selected literal, originating
  branch-chain id, assignment target text, direct-intrinsic token text,
  original selected body text, source location, and deterministic keys as
  typed provenance.
- Produce no selected-body direct-intrinsic package for
  `NoSelectedBodyEnvelopeIr`, except a clear diagnostic when that source family
  is explicitly requested.
- Keep existing M86 mini-TSIL leaf-return and M92 exact-array backend-handoff
  package behavior, public imports, package keys, diagnostics, stage ordering,
  snapshots, object identity, deterministic ordering, selected-branch-only
  behavior, and no-external-input boundaries stable.
- Put selected-body package validation and entry ownership in a focused module
  such as `_operation_package_selected_body.py`; `_operation_package_sources.py`
  may receive only narrow explicit integration and must not become a generic
  source dispatcher or protocol.

## Out Of Scope

- Backend translation, backend map/catalog reads, backend-uninit resolution,
  Stage 9 backend planning, renderer-ready IR, rendering, generated C++ or
  Rust output, generated tests, CLI/report/writer behavior, compiler
  execution, or Rust.
- Direct-intrinsic/SVE predicate semantics, `pg` type/scope proof, byte-size
  to `svptrue_b*` inference, vector metadata, store/return semantics, primitive
  dependency closure, operation scheduling, wrapper planning, or artifact
  planning.
- Raw selected-body text parsing, source-body repair, nearby malformed body
  acceptance, broad TSIL/body parsing, generic operation registries, callback
  maps, package-family registries, semantic dispatchers, hidden backfeeds,
  fixpoint machinery, or placeholder package kinds for future families.
- Treating `svptrue_b16`, `svptrue_b32`, `svptrue_b64`, `pg`, selected
  literals, selected type tags, branch ids, extension ids, primitive names,
  backend ids, or source locations as semantic dispatch keys.
- Changing accepted M62/M63 selected-body lowering behavior, changing accepted
  M86/M92 package behavior, or normalizing selected-body facts into broad body
  semantics.

## Required Inputs

- Accepted M62 `SelectedAssignmentDirectIntrinsicBodyIr` and
  `NoSelectedAssignmentDirectIntrinsicBodyIr` behavior and diagnostics.
- Accepted M63 `SelectedBodyEnvelopeIr` and `NoSelectedBodyEnvelopeIr`
  behavior, source locations, deterministic keys, and stage output contracts.
- Accepted M93/M94 `LoweringOperationPackageIr` behavior, package source-family
  distinction, facade imports, diagnostics, and module-size/import guardrails.
- Current M94 line-count evidence:
  - `tslgen/src/tslgen/lowering/boundary.py`: 1,280 physical lines.
  - `tslgen/src/tslgen/lowering/_operation_package.py`: 19 physical lines.
  - `tslgen/src/tslgen/lowering/_operation_package_sources.py`: 604 physical
    lines.

## Expected Outputs

- A focused selected-body direct-intrinsic operation-package entry/family over
  accepted M63/M62 typed values.
- Stable public operation-package facade imports for the new family, if a
  public import is added.
- Deterministic package keys and stage/snapshot integration that preserve
  source-family identity and object provenance.
- Diagnostics for unsupported source, wrong stage/source family, no selected
  body, malformed/non-singleton selected-body envelope state, context/source
  location mismatch, and M62/M63 provenance mismatch.
- Focused selected-body package ownership that keeps private operation-package
  modules below the line-count guardrail and keeps imports one-way.

## Required Executor Task

Run exactly one write-capable executor for M95. The executor should:

1. Implement the selected-body direct-intrinsic operation-package family
   described above.
2. Add focused selected-body package ownership, preferably in
   `tslgen.lowering._operation_package_selected_body`.
3. Keep `_operation_package.py` as a narrow facade/re-export surface.
4. Keep `_operation_package_sources.py` to narrow explicit integration only;
   do not create a generic source protocol, callback map, registry, or
   dispatcher.
5. Preserve accepted M62/M63 source object identity/provenance rather than
   reparsing selected-body text or interpreting direct-intrinsic tokens.
6. Preserve accepted M86 mini-TSIL leaf-return and accepted M92 exact-array
   backend-handoff package behavior exactly.
7. Preserve public import paths, stage name/order, package keys, diagnostics,
   source locations, pipeline snapshots, selected-branch-only behavior, and
   no-external-input boundaries.
8. Add focused tests for positive package creation, diagnostics, deterministic
   keys/order, pipeline/stage integration, public-surface stability, import
   boundaries, and line-count guardrails.
9. Avoid all out-of-scope backend, rendering, generated-output, source-repair,
   broad-body-semantics, broad-protocol, registry/dispatcher, hidden-backfeed,
   fixpoint, and hardwiring behavior.
10. Run the required validation commands below.
11. Return a concise implementation summary, files changed, validation
    results, line counts, and any follow-ups.

## Required Tests

- Positive tests for accepted direct M63 `SelectedBodyEnvelopeIr` input, the
  `selected_body_envelope_lowering` stage input, and narrow
  lowered-implementation/container input where applicable.
- Tests proving the selected-body package preserves the accepted M62 body IR
  object identity and M63 envelope provenance.
- Negative tests for `NoSelectedBodyEnvelopeIr`, unsupported source, wrong
  stage/source family, malformed/non-singleton selected-body envelope state,
  candidate/source-location mismatch, and M62/M63 provenance mismatch.
- Determinism tests for package keys and reordered typed inputs.
- Pipeline/stage tests proving selected-body packages append after
  `selected_body_envelope_lowering` without changing existing M86/M92 package
  behavior.
- Existing M86/M92 positive, diagnostic, identity/provenance, determinism,
  integration, and snapshot tests must continue to pass unchanged or with only
  behavior-preserving test ownership updates.
- Import-boundary and public-facade tests for any new selected-body package
  module, proving private operation-package modules do not import `boundary.py`,
  the `tslgen.lowering` package facade, backend modules, renderers, `tsldata`,
  or `frozen`.
- Line-count tests proving no operation-package private module becomes a
  replacement monolith.
- Negative assertions proving M95 does not parse raw selected-body text,
  interpret `svptrue_b*` or `pg`, infer byte size/vector width/predicate
  meaning/backend support, read backend maps/catalogs, create Stage 9 plans,
  create renderer-ready IR, render output, generate artifacts, repair source
  text, introduce registries/dispatchers, hidden backfeeds, or fixpoint
  machinery.

## Required Validation

Run:

```bash
wc -l tslgen/src/tslgen/lowering/_operation_package.py tslgen/src/tslgen/lowering/_operation_package_*.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_operation_package.py tslgen/src/tslgen/lowering/_operation_package_*.py tslgen/src/tslgen/lowering/_selected_body_models.py tslgen/src/tslgen/lowering/_stage_contracts.py tslgen/src/tslgen/lowering/_pipeline.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m95 or operation_package or selected_body"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

If implementation chooses different focused private module names, include
those files consistently in the line-count, py-compile, import-boundary tests,
`docs/agent/current-redesign-state.md`, and final report.

## Review And Audit Subagents

After the executor finishes, run read-only subagents:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Boundary auditor: verify M95 is Stage 8 lowering operation-package work
   only and does not add raw selected-body text parsing, source repair,
   SVE/direct-intrinsic semantics, byte-size-to-token inference, backend
   resolution, backend maps/catalog reads, Stage 9 planning, backend
   translation, renderer-ready IR, rendering, generated output, broad TSIL/body
   semantics, registries/dispatchers, hidden backfeeds, fixpoint behavior, or
   hardwiring.
3. Extensibility auditor: verify selected-body package ownership is cohesive,
   private modules keep one-way imports where practical, `_operation_package.py`
   remains a facade, `_operation_package_sources.py` does not become a generic
   source protocol/dispatcher, no new module becomes a replacement monolith,
   and `boundary.py` does not absorb ownership.
4. Validation auditor: verify required commands ran, exact results are
   recorded, line counts are reported, and tests cover the declared M95 risks.
5. Documentation auditor: verify roadmap/state/testing/design docs match the
   implemented result and no stale post-M94 pending-acceptance wording remains.

Reviewers and auditors are read-only.

## Revision Loop

If review returns `Needs Revision`, run one focused write-capable revision
executor for only the blocking issues. Then run focused read-only re-review for
the affected issue class. Repeat only if the remaining issues are tightly
scoped local fixes.

If review returns `Return To Planner`, stop implementation and create a
planning prompt under `docs/agent/runs/` that describes the unresolved design
issue. Do not continue M95 implementation.

If review returns `Reject`, stop implementation and create the appropriate
rollback/redesign prompt under `docs/agent/runs/`. Do not continue M95
implementation.

## Finalization

If review returns `Accept` or `Accept With Follow-Ups`, update:

- `docs/agent/current-redesign-state.md`
- `docs/redesign/implementation-roadmap.md`
- any other redesign docs needed to reflect the accepted M95 result

Record:

- M95 accepted status and review verdict.
- Files changed.
- Line counts for touched lowering modules.
- Validation commands and exact results.
- Any non-blocking follow-ups.
- Boundary reminders for future lowering work.

Then create:

```text
docs/agent/runs/post-m95-planning-plus-review-prompt.md
```

The next prompt should plan the next milestone after M95 with a lowering focus
unless M95 review records a stop condition.

Do not start M96 implementation.

## Final Report

Report:

1. Implementation summary.
2. Review/audit subagent verdicts.
3. Files changed.
4. Validation commands and exact results.
5. Follow-ups recorded, if any.
6. Next prompt created.
7. Whether M95 is accepted or whether revision/planning/rollback is required.
