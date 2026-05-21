# Post-M95 Acceptance Finalization Prompt

You are finalizing the accepted post-M95 planning result.

Do not implement code.

## Accepted Result

Post-M95 planning selected:

```text
Milestone 96: Stage-8 Lowering Completion Manifest Slice
```

Planning review returned:

```text
Accept With Follow-Ups
```

The accepted plan is a Stage 8 lowering-only manifest slice. It creates a
deterministic per-candidate completion/readiness manifest over accepted
`LoweringOperationPackageIr` facts and explicit unresolved dependency
references. "Completion" and "readiness" mean only accepted Stage 8
package/provenance assembly status, not semantic body completion, backend
readiness, renderer readiness, executable readiness, or generated-output
readiness.

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
- `tslgen/src/tslgen/lowering/_operation_package_selected_body.py`
- `tslgen/src/tslgen/lowering/_stage_contracts.py`
- `tslgen/src/tslgen/lowering/_pipeline.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Task

Update repository workflow state so the next action is M96 execution.

Update only if needed:

- `docs/agent/current-redesign-state.md`

It should state:

- Accepted through: Milestone 95.
- Post-M95 planning accepted.
- Current action: execute Milestone 96.
- Active executor milestone:
  `Milestone 96: Stage-8 Lowering Completion Manifest Slice`.
- Active run prompt:
  `docs/agent/runs/m96-execution-review-loop-prompt.md`.
- Next expected action: run the M96 execution-review loop.
- Boundary reminders:
  - M96 is Stage 8 lowering manifest/provenance work only.
  - M96 consumes accepted `LoweringOperationPackageIr` values as its primary
    input.
  - M96 may preserve M86 mini-TSIL leaf-return facts, M92 exact-array
    backend-handoff facts, and M95 selected-body direct-intrinsic facts only
    through accepted operation-package entries and already-preserved object
    references.
  - M96 may preserve accepted M92/M90 unresolved backend-handoff dependency
    references but must not resolve them.
  - M96 "completion" and "readiness" mean accepted Stage 8 package/provenance
    assembly status only.
  - Any package graph is an identity/provenance graph of accepted
    operation-package records and explicit unresolved dependency references
    only.
  - M96 must not re-enter raw M86 statements, M92 handoff assembly, M63
    envelopes, or the M90/M89/M72/M67 chain except to validate already
    preserved object references.
  - M96 must avoid adding ownership to `boundary.py` or
    `_operation_package_sources.py`.
  - No backend translation, backend map/catalog reads, backend-uninit
    resolution, Stage 9 backend planning, operation scheduling, primitive
    dependency closure, wrapper planning, artifact planning, renderer-ready IR,
    rendering, generated output, source repair, broad TSIL/body parsing,
    direct-intrinsic/SVE semantics, byte-size-to-token inference, registries,
    dispatchers, hidden backfeeds, fixpoint machinery, Rust, CLI/report/writer,
    or compiler execution work is in M96.

Create:

```text
docs/agent/runs/m96-execution-review-loop-prompt.md
```

The M96 execution prompt must use the orchestrated executor-review loop with
exactly one write-capable executor followed by read-only review/audit
subagents. It must include the selected M96 scope, out-of-scope items,
required inputs, expected outputs, tests, validation commands, revision loop,
and finalization rules.

Do not modify product code or tests.

## M96 Execution Prompt Requirements

The M96 execution-review-loop prompt must require:

- One write-capable executor only.
- Read-only reviewer, boundary auditor, extensibility auditor, validation
  auditor, and documentation auditor subagents after implementation.
- Focused private manifest ownership, such as
  `tslgen.lowering._lowering_completion_manifest`, with a split only if one
  file would approach the module-size guardrail.
- A narrowly named output model such as
  `Stage8LoweringCompletionManifestIr`.
- Consumption of accepted `LoweringOperationPackageIr` values as the primary
  input, not raw package source values.
- Support only for current accepted package families:
  `mini_tsil_leaf_return`, `exact_array_backend_handoff`, and
  `selected_body_direct_intrinsic`.
- Preservation of package object identity, package keys, source-family
  identity, candidate id, source locations, and unresolved dependency request
  references.
- No changes to accepted M86 mini-TSIL leaf-return, M92 exact-array
  backend-handoff, or M95 selected-body direct-intrinsic package behavior.
- No growth in `boundary.py` beyond the current 1,300-line pressure point and
  no growth in `_operation_package_sources.py` beyond the current 819-line
  pressure point unless the implementation first performs a behavior-preserving
  extraction that reduces that pressure.
- Tests for manifest construction from accepted package facts, deterministic
  manifest keys/order, object identity/provenance preservation, unresolved
  backend-dependency reference preservation, missing/duplicate/malformed/
  family-mismatched/candidate-mismatched/provenance-mismatched diagnostics,
  stage placement after `lowering_operation_package`, pipeline snapshot
  stability, import boundaries, line counts, and forbidden behaviors.

Required validation for the execution prompt:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_operation_package_sources.py tslgen/src/tslgen/lowering/_lowering_completion_manifest*.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_operation_package*.py tslgen/src/tslgen/lowering/_lowering_completion_manifest*.py tslgen/src/tslgen/lowering/_stage_contracts.py tslgen/src/tslgen/lowering/_pipeline.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m96 or completion_manifest or operation_package"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/post-m95-acceptance-finalization-prompt.md docs/agent/runs/m96-execution-review-loop-prompt.md
```

If other docs are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-ups recorded, if any.
4. Validation command and exact result.
5. Whether the repo is ready to execute M96.
