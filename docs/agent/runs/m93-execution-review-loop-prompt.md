# M93 Execution Review Loop Prompt

You are executing and reviewing the accepted Milestone 93.

Milestones 1 through 92 are accepted. Post-M92 planning is accepted and
selected:

```text
Milestone 93: Dual-Source Lowering Operation Package Boundary Slice
```

Use the orchestrated executor-review loop in this prompt. M93 is an
implementation milestone; one write-capable executor may implement the
selected slice. Do not start post-M93 planning until M93 review returns
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
- `tsldata/primitives/arithmetic/fundamental.tsl`
- `tsldata/primitives/load_store/array.tsl`
- `tslgen/src/tslgen/lowering/boundary.py`
- `tslgen/src/tslgen/lowering/_mini_tsil_lowering.py`
- `tslgen/src/tslgen/lowering/_array_body_backend_handoff.py`
- `tslgen/src/tslgen/lowering/_array_body_completion_package.py`
- `tslgen/src/tslgen/lowering/_array_body_pipeline.py`
- `tslgen/src/tslgen/lowering/_array_body_pipeline_results.py`
- `tslgen/src/tslgen/lowering/_array_body_stage_assembly.py`
- `tslgen/src/tslgen/lowering/_stage_contracts.py`
- `tslgen/src/tslgen/lowering/_pipeline.py`
- `tslgen/src/tslgen/lowering/__init__.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Goal

Create a backend-neutral typed lowering operation package boundary that can
carry either an accepted M86 mini-TSIL leaf return operation or an accepted M92
exact array backend-handoff operation as immutable typed/provenance data.

M93 should prove the lowering package boundary is not array-only while staying
narrow. It must preserve distinct source-family identity and must not pretend
that M86 and M92 share broad body semantics.

## Scope

- Add focused private ownership, such as
  `tslgen.lowering._operation_package`, for one lowering operation package
  type, two exact package entry variants, deterministic keys, source
  narrowing, provenance validation, and diagnostics.
- Consume only accepted M86 `TsilReturnStatement` /
  `selected_body_lowering` values with explicit candidate context, accepted
  M92 `ExactArrayBackendHandoffRequestIr` /
  `array_backend_handoff_request` values, or narrowly validated sources
  carrying exactly one packageable accepted value.
- Produce a deterministic typed package for `mini_tsil_leaf_return` entries
  that preserves the accepted M86 return statement object and candidate
  context.
- Produce a deterministic typed package for `exact_array_backend_handoff`
  entries that preserves the accepted M92 request object and its M90/M89/M88/
  M72/M67 identity/provenance chain.
- Expose the packages on `LoweredImplementation` and stage snapshots as a
  Stage 8 `lowering_operation_package` fact, without changing accepted M86 or
  M92 output identity or earlier stage order.
- Preserve accepted M57-M92 diagnostics, source locations, public imports,
  deterministic keys, selected-branch-only behavior, no-external-input
  boundaries, and pipeline snapshots.

## Out Of Scope

- Backend-uninit resolution, backend map reads, backend catalog reads,
  `tsldata/detail/lang` reads, Stage 9 backend planning, backend translation,
  renderer-ready IR, rendering, generated C++ or Rust output, generated tests,
  CLI/report/writer behavior, compiler execution, or Rust.
- Primitive dependency closure, primitive-call discovery, operation
  scheduling, backend support filtering, wrapper-shape planning, artifact path
  planning, or backend operation DAG construction.
- Generic operation registries, plugin systems, callback maps, semantic
  dispatchers, hidden backfeeds, fixpoint execution, or dispatch tables keyed
  by primitive name, raw helper text, backend id, extension id, selected type
  tag, SVE token, renderer name, corpus line number, or request ordinal.
- Hardwiring semantic outputs from primitive names, selected type tags,
  extension names, backend ids, helper text, SVE tokens, corpus line numbers,
  or request ordinals.
- Generic TSIL parsing, broad expression/body/return/call/store/declaration/
  array/variable/cast/loop/SVE semantics, broad `emit_return(...)`, broad
  direct-intrinsic semantics, generic `value<backend>(...)` or
  `type<backend>(...)` evaluation, or source-body repair.
- Placeholder operation package kinds for unimplemented primitive families.
  Future primitive families must be added by later milestones with their own
  accepted typed source facts, evidence, diagnostics, and tests.

## Required Inputs

- Accepted M86 `TsilReturnStatement` values and the selected-candidate context
  that produced them.
- Accepted M92 `ExactArrayBackendHandoffRequestIr` values.
- Accepted M92 source-chain references to M90/M89/M88/M72/M67 values.
- Corpus evidence:
  - `tsldata/primitives/arithmetic/fundamental.tsl:31`
  - `tsldata/primitives/arithmetic/fundamental.tsl:64`
  - `tsldata/primitives/load_store/array.tsl:105-111`

## Expected Outputs

- A typed lowering operation package with stable identity, source-family tag,
  candidate id, source location/provenance, source typed value reference, and
  deterministic key behavior.
- A mini-TSIL leaf-return operation package entry preserving the accepted M86
  `TsilReturnStatement` object and candidate context.
- An exact-array backend-handoff operation package entry preserving the
  accepted M92 request object and its unresolved dependency request/provenance
  records.
- A deterministic Stage 8 `lowering_operation_package` stage/snapshot entry
  without changing accepted earlier stage order or output identities.
- Structured diagnostics for unsupported source, missing packageable value,
  duplicate packageable values, malformed runtime entries, source-family
  mismatch, context mismatch, source-location mismatch, dependency/provenance
  mismatch, and package-source ambiguity.
- Stable public `tslgen.lowering` and `tslgen.lowering.boundary` imports.

## Required Executor Task

Run exactly one write-capable executor for M93. The executor should:

1. Implement the smallest coherent dual-source operation package boundary
   described above.
2. Prefer focused private module ownership for operation package data and
   assembly. If a module name other than
   `tslgen.lowering._operation_package` is chosen, document why it is the
   clearer ownership boundary and include it consistently in tests,
   validation, state updates, and the final report.
3. Preserve accepted M86 and M92 object identity/provenance rather than
   reparsing source text, re-collecting facts, or normalizing the source
   families into fake common body semantics.
4. Add the deterministic Stage 8 `lowering_operation_package` fact and expose
   packages through normal lowered implementation and snapshot surfaces while
   preserving earlier stage order and accepted output identity.
5. Add focused tests for positive package assembly, identity/provenance,
   diagnostics, deterministic keys/order, stage/snapshot integration, import
   boundaries, and out-of-scope negative assertions.
6. Avoid all out-of-scope backend, rendering, generated-output, source-repair,
   broad-body-semantics, broad-protocol, registry/dispatcher, hidden-backfeed,
   fixpoint, and hardwiring behavior.
7. Run the required validation commands below.
8. Return a concise implementation summary, files changed, validation results,
   line counts, and any follow-ups.

## Required Tests

- Positive M93 tests for direct M86 statement plus explicit candidate context,
  M86 stage-output/container input, direct M92 handoff request input, M92
  stage-output/container input, and normal `LoweredImplementation` /
  `LoweringPlan` integration.
- Identity/provenance tests proving package entries reference accepted M86 and
  M92 objects rather than duplicating, reparsing, or re-collecting facts.
- Negative diagnostics for unsupported source, missing packageable value,
  duplicate packageable values, malformed runtime entries, source-family
  mismatch, context mismatch, source-location mismatch, and M92 dependency/
  provenance mismatch.
- Determinism tests for package keys, reordered lowered implementations, and
  pipeline snapshots.
- Import-boundary tests proving the focused package module does not import
  `boundary.py`, `tslgen.lowering`, exact-array orchestration modules as
  dispatchers, backend modules, renderers, `tsldata`, or `frozen`.
- Negative assertions proving M93 does not read backend maps/catalogs, resolve
  `uninit::array`, create Stage 9 plans, produce renderer-ready values, render
  output, infer broad body semantics, repair source text, create operation
  registries/semantic dispatchers, or widen to generic TSIL/backend-helper
  evaluation.

## Required Validation

Run:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_operation_package.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_operation_package.py tslgen/src/tslgen/lowering/_stage_contracts.py tslgen/src/tslgen/lowering/_pipeline.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m93 or operation_package or mini_tsil or backend_handoff"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

If implementation chooses a different focused private module name, include
that file consistently in the line-count, py-compile, import-boundary tests,
`docs/agent/current-redesign-state.md`, and final report.

## Review And Audit Subagents

After the executor finishes, run read-only subagents:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Boundary auditor: verify M93 is Stage 8 lowering package-boundary work only
   and does not add backend resolution, backend maps/catalog reads, Stage 9
   backend planning, backend translation, renderer-ready IR, rendering,
   generated output, broad TSIL/body semantics, source repair, dependency
   closure, scheduling, registries/dispatchers, hidden backfeeds, fixpoint
   behavior, or hardwiring.
3. Extensibility auditor: verify focused package ownership, one-way imports
   where practical, no replacement monolith, no broad dispatcher, no facade
   back-imports, no registry/callback/plugin machinery, and no catch-all
   growth in existing lowering modules.
4. Validation auditor: verify required commands ran, exact results are
   recorded, line counts are reported, and tests cover the declared M93 risks.
5. Documentation auditor: verify roadmap/state/testing/design docs match the
   implemented result and no stale post-M92 pending-acceptance wording remains.
6. Evidence auditor: verify the implementation is supported by accepted
   M86/M92 behavior and the cited corpus evidence without claiming broader
   TSIL, backend, SVE, or generated-output support.

Reviewers and auditors are read-only.

## Revision Loop

If review returns `Needs Revision`, run one focused write-capable revision
executor for only the blocking issues. Then run focused read-only re-review for
the affected issue class. Repeat only if the remaining issues are tightly
scoped local fixes.

If review returns `Return To Planner`, stop implementation and create a
planning prompt under `docs/agent/runs/` that describes the unresolved design
issue. Do not continue M93 implementation.

If review returns `Reject`, stop implementation and create the appropriate
rollback/redesign prompt under `docs/agent/runs/`. Do not continue M93
implementation.

## Finalization

If review returns `Accept` or `Accept With Follow-Ups`, update:

- `docs/agent/current-redesign-state.md`
- `docs/redesign/implementation-roadmap.md`
- any other redesign docs needed to reflect the accepted M93 result

Record:

- M93 accepted status and review verdict.
- Files changed.
- Line counts for touched lowering modules.
- Validation commands and exact results.
- Any non-blocking follow-ups.
- Boundary reminders for future lowering work.

Create the next concrete prompt:

```text
docs/agent/runs/post-m93-planning-plus-review-prompt.md
```

The post-M93 prompt must focus on the next highest-value redesign step, use
read-only planning/review subagents, and must not implement M94 unless that
future prompt explicitly selects an executor task.

Do not start post-M93 planning in this prompt.

## Final Report

Report:

1. Files changed.
2. Implementation summary.
3. Review/audit verdicts and follow-ups.
4. Validation commands and exact results.
5. State transition made.
6. Next concrete prompt path created.
