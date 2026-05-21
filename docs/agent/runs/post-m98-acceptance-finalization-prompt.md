# Post-M98 Acceptance Finalization Prompt

You are finalizing the accepted post-M98 planning result.

Do not implement code.

## Accepted Result

Post-M98 planning selected:

```text
Milestone 99: Operation Package Backend-Translation Request Inventory Slice
```

Planning review returned:

```text
Accept With Follow-Ups
```

The accepted plan is Stage 8 lowering inventory/provenance work only. It
creates a typed inventory of accepted backend-scoped request facts visible from
accepted operation packages, completion manifests, and gap inventories. It does
not translate backend values, evaluate backend maps, create Stage 9 plans,
schedule operations, solve dependencies, render output, scan raw source bodies,
repair source bodies, or infer direct-intrinsic/SVE semantics.

The non-blocking follow-ups are:

- M99 execution must keep "backend-translation request inventory" wording
  anchored to Stage 8 inventory/provenance only.
- Future lowering milestones should update
  `docs/redesign/missing-lowering-inventory.md` when they accept, resolve,
  narrow, or discover lowering gaps.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/agent/review-checklist.md`
- `docs/agent/subagents/`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/missing-lowering-inventory.md`
- `docs/redesign/generation-time-semantic-lowering.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/open-questions.md`
- `tslgen/src/tslgen/lowering/boundary.py`
- `tslgen/src/tslgen/lowering/_lowering_stage_assembly.py`
- `tslgen/src/tslgen/lowering/_lowering_completion_gap_inventory.py`
- `tslgen/src/tslgen/lowering/_lowering_completion_manifest.py`
- `tslgen/src/tslgen/lowering/_operation_package.py`
- `tslgen/src/tslgen/lowering/_operation_package_sources.py`
- `tslgen/src/tslgen/lowering/_operation_package_models.py`
- `tslgen/src/tslgen/lowering/_stage_contracts.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Task

Update repository workflow state so the next action is M99 execution.

Update only if needed:

- `docs/agent/current-redesign-state.md`

It should state:

- Accepted through: Milestone 98.
- Post-M98 planning accepted.
- Current action: execute Milestone 99.
- Active executor milestone:
  `Milestone 99: Operation Package Backend-Translation Request Inventory Slice`.
- Active run prompt:
  `docs/agent/runs/m99-execution-review-loop-prompt.md`.
- Next expected action: run the M99 execution-review loop.
- Boundary reminders:
  - M99 is Stage 8 lowering inventory/provenance work only.
  - M99 consumes only accepted typed Stage 8 facts from M93-M98 operation
    packages, completion manifests, gap inventories, stage assembly, and their
    preserved object references.
  - "Backend-translation request inventory" means typed inventory of accepted
    deferred/backend-scoped request facts. It must not translate, resolve,
    evaluate, plan, schedule, or render those facts.
  - Package families without accepted backend-scoped request facts must produce
    explicit no-accepted-request / no-known-request inventory state, not
    inferred requests.
  - M99 must not parse raw `.tsl` source text, repair source bodies, normalize
    source bodies, infer package-family requests, or treat source locations,
    backend ids, extension ids, type tags, primitive names, selected literals,
    `svptrue_b*`, `pg`, or direct-intrinsic token text as semantic dispatch
    keys.
  - M99 must not add backend map/catalog/lang reads, backend manifest reads,
    `tsldata/detail/lang` reads, backend-uninit resolution, generic
    `value<backend>(...)` / `type<backend>(...)` evaluation, Stage 9 planning,
    backend support decisions, operation scheduling, dependency solving,
    dependency closure, operation DAGs, wrapper planning, artifact planning,
    renderer-ready IR, rendering, generated output, generated tests, Rust,
    CLI/report/writer behavior, compiler execution, host hardware dependency,
    registries, dispatchers, callback maps, plugin systems, hidden backfeeds,
    fixpoint machinery, or hardwiring.
  - `docs/redesign/missing-lowering-inventory.md` is documentation-only and
    must not become runtime input, generated output, source scanner,
    dependency-closure plan, or completeness oracle.

Create:

```text
docs/agent/runs/m99-execution-review-loop-prompt.md
```

The M99 execution prompt must use the orchestrated executor-review loop with
exactly one write-capable executor followed by read-only review/audit
subagents. It must include the selected M99 scope, out-of-scope items,
required inputs, expected outputs, tests, validation commands, revision loop,
and finalization rules.

Do not modify product code or tests.

## M99 Execution Prompt Requirements

The M99 execution-review-loop prompt must require:

- One write-capable executor only.
- Read-only reviewer, boundary auditor, extensibility auditor, validation
  auditor, and documentation auditor subagents after implementation.
- A focused private module, preferably
  `tslgen.lowering._lowering_backend_translation_request_inventory`, for typed
  inventory models, diagnostics, validation, deterministic keys, and assembly.
- The new Stage 8 stage should follow `lowering_completion_gap_inventory`.
- Inputs must be accepted typed M93-M98 facts and preserved object references,
  not raw source text.
- Inventory records must cover:
  - exact-array `value<backend>(uninit::array)` deferred backend-value request
    facts from accepted M92/M96/M97 state;
  - selected-body direct-intrinsic package handoff/request facts from accepted
    M62/M63/M95 state without interpreting direct-intrinsic or SVE semantics;
  - explicit no-accepted-request / no-known-request states for package
    families with no accepted backend-scoped request facts.
- Preservation of accepted M57-M98 diagnostics, stage names, stage ordering,
  stage keys, deterministic ordering, output identities, source locations,
  object identities, selected-branch-only diagnostics, public imports, and
  no-external-input boundaries.
- Focused tests for exact-array request records, selected-body direct-intrinsic
  request/handoff records, no-accepted-request states, mixed inventories,
  object-identity preservation, deterministic keys/order, stage placement,
  diagnostics, import boundaries, line-count guardrails, and forbidden
  behaviors.
- Import-boundary tests proving the new module does not import `boundary.py`,
  the `tslgen.lowering` package facade, backend modules, renderers, `tsldata`,
  or `frozen`.
- Line-count guardrails for `boundary.py`, `_operation_package_sources.py`,
  `_lowering_completion_manifest.py`, `_lowering_completion_gap_inventory.py`,
  `_lowering_stage_assembly.py`, and the new request-inventory module. Prefer
  a new focused test file if adding all M99 coverage to
  `test_lowering_boundary.py` would make that file harder to maintain.

Required validation for the execution prompt:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_operation_package_sources.py tslgen/src/tslgen/lowering/_lowering_completion_manifest.py tslgen/src/tslgen/lowering/_lowering_completion_gap_inventory.py tslgen/src/tslgen/lowering/_lowering_stage_assembly.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_inventory.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_stage_contracts.py tslgen/src/tslgen/lowering/_lowering_stage_assembly.py tslgen/src/tslgen/lowering/_lowering_completion_manifest.py tslgen/src/tslgen/lowering/_lowering_completion_gap_inventory.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_inventory.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m99 or backend_translation_request_inventory or completion_gap_inventory or completion_manifest or operation_package"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

If implementation chooses a different focused private module name, include
that file consistently in the line-count, py-compile, import-boundary tests,
`docs/agent/current-redesign-state.md`, and final report.

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/post-m98-acceptance-finalization-prompt.md docs/agent/runs/m99-execution-review-loop-prompt.md docs/redesign/README.md docs/redesign/behavioral-spec.md docs/redesign/design-decisions.md docs/redesign/generation-time-semantic-lowering.md docs/redesign/implementation-roadmap.md docs/redesign/missing-lowering-inventory.md docs/redesign/open-questions.md docs/redesign/pipeline-design.md docs/redesign/target-architecture.md docs/redesign/testing-strategy.md
```

If other docs are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-ups recorded, if any.
4. Validation command and exact result.
5. Whether the repo is ready to execute M99.
