# M94 Execution Review Loop Prompt

You are executing and reviewing the accepted Milestone 94.

Milestones 1 through 93 are accepted. Post-M93 planning is accepted and
selected:

```text
Milestone 94: Lowering Operation Package Diagnostics and Provenance Ownership Split Slice
```

Use the orchestrated executor-review loop in this prompt. M94 is an
implementation milestone; one write-capable executor may implement the
selected slice. Do not start post-M94 planning until M94 review returns
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
- `tslgen/src/tslgen/lowering/_mini_tsil_lowering.py`
- `tslgen/src/tslgen/lowering/_array_body_backend_handoff.py`
- `tslgen/src/tslgen/lowering/_array_body_completion_package.py`
- `tslgen/src/tslgen/lowering/_array_body_package.py`
- `tslgen/src/tslgen/lowering/_array_body_pipeline.py`
- `tslgen/src/tslgen/lowering/_array_body_pipeline_results.py`
- `tslgen/src/tslgen/lowering/_array_body_stage_assembly.py`
- `tslgen/src/tslgen/lowering/_stage_contracts.py`
- `tslgen/src/tslgen/lowering/_pipeline.py`
- `tslgen/src/tslgen/lowering/__init__.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Goal

Keep the accepted M93 lowering operation package boundary maintainable before
any future package-family expansion.

M94 is behavior-preserving Stage 8 lowering architecture work. It splits M93
operation-package models, diagnostics, accepted-source narrowing, accepted M86
leaf-return package checks, and accepted M92/M90/M89/M88/M72/M67 provenance
validation into focused private modules. It must preserve accepted M93
behavior exactly.

## Scope

- Preserve accepted M93 behavior for exactly the two packageable source
  families:
  - accepted M86 mini-TSIL leaf return statements with selected-candidate
    context.
  - accepted M92 exact array backend-handoff requests with the accepted
    M90/M89/M88/M72/M67 provenance chain.
- Keep public `tslgen.lowering` and `tslgen.lowering.boundary`
  operation-package imports stable, including:
  - `lower_lowering_operation_package`
  - `LoweringOperationPackageIr`
  - `MiniTsilLeafReturnOperationPackageEntryIr`
  - `ExactArrayBackendHandoffOperationPackageEntryIr`
  - `LoweringOperationPackageSourceFamily`
- Split focused private ownership out of `_operation_package.py`, such as:
  - `_operation_package_models.py` for package/entry value models,
    source-family literal ownership, and deterministic keys.
  - `_operation_package_diagnostics.py` for M93 diagnostic constructors and
    source-location helper behavior.
  - `_operation_package_sources.py` for accepted source/stage/container
    narrowing and exactly-one-packageable-value checks.
  - `_operation_package_mini_tsil.py` for the accepted M86 leaf-return
    package contract and exact accepted-shape predicate.
  - `_operation_package_exact_array.py` for accepted M92/M90/M89/M88/M72/M67
    identity/provenance contract validation.
- Keep `_operation_package.py` as a narrow coordinator/facade over those
  focused modules, not as the owner of diagnostics, provenance validation, and
  source narrowing.
- Preserve accepted M93 diagnostics, diagnostic codes, diagnostic locations,
  package keys, stage name `lowering_operation_package`, stage ordering,
  snapshots, object identity, deterministic ordering, selected-branch-only
  behavior, public imports, and no-external-input boundaries.
- Add or update import-boundary and contract tests for the new modules,
  proving one-way private imports and public-surface stability.
- Include line-count validation proving `_operation_package.py` drops
  materially below the roughly 1,000-line guardrail and that no replacement
  operation-package module approaches the guardrail.

## Out Of Scope

- New operation package source families or placeholder package kinds.
- New semantic lowering behavior, broad package-family dispatch, generic
  operation registries, callback maps, plugin systems, semantic dispatchers,
  hidden backfeeds, fixpoint machinery, or token-keyed semantic maps.
- Backend-uninit resolution, backend map reads, backend catalog reads,
  `tsldata/detail/lang` reads, Stage 9 backend planning, backend translation,
  renderer-ready IR, rendering, generated C++ or Rust output, generated tests,
  CLI/report/writer behavior, compiler execution, or Rust.
- Primitive dependency closure, primitive-call discovery, operation
  scheduling, backend support filtering, wrapper-shape planning, artifact path
  planning, or backend operation DAG construction.
- Generic TSIL parsing, broad expression/body/return/call/store/declaration/
  array/variable/cast/loop/SVE semantics, generic backend-helper evaluation,
  broad direct-intrinsic semantics, or source-body repair.
- Changing accepted M86/M92 source-family narrowing, reparsing accepted values,
  normalizing M86 and M92 into shared body semantics, or hardwiring semantic
  outputs from primitive names, selected type tags, extension names, backend
  ids, helper text, SVE tokens, corpus line numbers, or request ordinals.
- Growing `boundary.py`, exact-array pipeline modules, `_stage_contracts.py`,
  or any new private operation-package module into a catch-all owner.

## Required Inputs

- Accepted M93 `LoweringOperationPackageIr` behavior and tests.
- Accepted M86 mini-TSIL leaf return statements and selected-candidate context.
- Accepted M92 exact array backend-handoff requests and their accepted
  M90/M89/M88/M72/M67 provenance chain.
- Current line-count evidence:
  - `tslgen/src/tslgen/lowering/boundary.py`: 1,280 physical lines.
  - `tslgen/src/tslgen/lowering/_operation_package.py`: 1,044 physical lines.

## Expected Outputs

- Focused private operation-package modules with one-way imports and explicit
  ownership.
- `_operation_package.py` reduced to a small coordinator/re-export surface
  while preserving accepted public imports and behavior.
- The same accepted M93 package outputs, diagnostics, keys, identities, stage
  outputs, and snapshots as before the split.
- Focused tests proving behavior preservation, diagnostic preservation,
  public-surface stability, import-boundary discipline, and line-count
  guardrails.

## Required Executor Task

Run exactly one write-capable executor for M94. The executor should:

1. Implement the behavior-preserving operation-package ownership split
   described above.
2. Keep `_operation_package.py` as the narrow coordinator/facade. If exact
   module names differ from the suggested names, document why the chosen names
   are clearer and include them consistently in tests, validation, state
   updates, and the final report.
3. Preserve accepted M93 object identity/provenance rather than reparsing
   source text, re-collecting facts, or normalizing M86 and M92 into fake
   common body semantics.
4. Preserve public import paths, stage name/order, package keys, diagnostics,
   source locations, pipeline snapshots, selected-branch-only behavior, and
   no-external-input boundaries.
5. Add focused tests for public-surface stability, import boundaries for each
   new private module, diagnostic preservation, provenance preservation,
   deterministic keys/order, and line-count guardrails.
6. Avoid all out-of-scope backend, rendering, generated-output, source-repair,
   broad-body-semantics, broad-protocol, registry/dispatcher, hidden-backfeed,
   fixpoint, and hardwiring behavior.
7. Run the required validation commands below.
8. Return a concise implementation summary, files changed, validation results,
   line counts, and any follow-ups.

## Required Tests

- Existing M93 positive, diagnostic, identity/provenance, determinism,
  integration, and snapshot tests must continue to pass unchanged or with only
  behavior-preserving test ownership updates.
- New or updated M94 import-boundary tests must cover each new private module,
  proving they do not import `boundary.py`, the `tslgen.lowering` package
  facade, backend modules, renderers, `tsldata`, or `frozen`.
- Contract tests must prove the public facade exports still point at the same
  operation-package API and that stage name/order/key behavior remains stable.
- Diagnostic tests must prove accepted M93 diagnostic codes and source
  locations are preserved across the split.
- Provenance tests must prove M92/M90/M89/M88/M72/M67 identity checks are still
  enforced by focused exact-array ownership.
- Negative assertions must prove no backend map/catalog reads, backend-uninit
  resolution, Stage 9 planning, renderer-ready IR, rendering, generated
  output, source repair, operation registry, semantic dispatcher, generic TSIL
  parsing, or generic backend-helper evaluation is introduced.

## Required Validation

Run:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_operation_package.py tslgen/src/tslgen/lowering/_operation_package_*.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_operation_package.py tslgen/src/tslgen/lowering/_operation_package_*.py tslgen/src/tslgen/lowering/_stage_contracts.py tslgen/src/tslgen/lowering/_pipeline.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m94 or operation_package or provenance or diagnostics"
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
2. Boundary auditor: verify M94 is behavior-preserving Stage 8 lowering
   maintainability work only and does not add backend resolution, backend
   maps/catalog reads, Stage 9 backend planning, backend translation,
   renderer-ready IR, rendering, generated output, broad TSIL/body semantics,
   source repair, new package families, registries/dispatchers, hidden
   backfeeds, fixpoint behavior, or hardwiring.
3. Extensibility auditor: verify the operation-package ownership split is
   cohesive, modules keep one-way imports where practical, `_operation_package.py`
   drops materially below the guardrail, no new module becomes a replacement
   monolith, no broad dispatcher/source protocol appears, and `boundary.py`
   does not absorb ownership.
4. Validation auditor: verify required commands ran, exact results are
   recorded, line counts are reported, and tests cover the declared M94 risks.
5. Documentation auditor: verify roadmap/state/testing/design docs match the
   implemented result and no stale post-M93 pending-acceptance wording remains.

Reviewers and auditors are read-only.

## Revision Loop

If review returns `Needs Revision`, run one focused write-capable revision
executor for only the blocking issues. Then run focused read-only re-review for
the affected issue class. Repeat only if the remaining issues are tightly
scoped local fixes.

If review returns `Return To Planner`, stop implementation and create a
planning prompt under `docs/agent/runs/` that describes the unresolved design
issue. Do not continue M94 implementation.

If review returns `Reject`, stop implementation and create the appropriate
rollback/redesign prompt under `docs/agent/runs/`. Do not continue M94
implementation.

## Finalization

If review returns `Accept` or `Accept With Follow-Ups`, update:

- `docs/agent/current-redesign-state.md`
- `docs/redesign/implementation-roadmap.md`
- any other redesign docs needed to reflect the accepted M94 result

Record:

- M94 accepted status and review verdict.
- Files changed.
- Line counts for touched lowering modules.
- Validation commands and exact results.
- Any non-blocking follow-ups.
- Boundary reminders for future lowering work.

Create the next concrete prompt:

```text
docs/agent/runs/post-m94-planning-plus-review-prompt.md
```

The post-M94 prompt must focus on the next highest-value redesign step, prefer
lowering when it remains the best path forward, use read-only planning/review
subagents, and must not implement M95 unless that future prompt explicitly
selects an executor task.

Do not start post-M94 planning in this prompt.

## Final Report

Report:

1. Files changed.
2. Implementation summary.
3. Review/audit verdicts and follow-ups.
4. Validation commands and exact results.
5. State transition made.
6. Next concrete prompt path created.
