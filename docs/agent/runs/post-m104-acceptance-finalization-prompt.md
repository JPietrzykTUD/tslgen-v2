# Post-M104 Planning Acceptance Finalization Prompt

You are finalizing the accepted post-M104 planning update.

Do not implement product code.

## Accepted Result

The post-M104 planning update selected:

```text
Milestone 105: Clean KISS Generator Restart Charter Slice
```

Planning review returned:

```text
Accept With Follow-Ups
```

The accepted plan intentionally pivots away from extending the accumulated
M57-M104 lowering micro-IR chain. That chain remains evidence for requirements,
diagnostics, and regression risks, but it is not the default architecture for
the next implementation path.

A user correction adds a hard repository-layout requirement: the current
top-level `tslgen/` tree is old-state evidence and should move to
`tslgenold/`; the clean restart implementation owns the top-level `tslgen/`
path.

## Task

Update repository workflow state so the next action is M105 execution.

Read first:

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/missing-lowering-inventory.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/open-questions.md`

## Required Changes

Update only if needed:

- `docs/agent/current-redesign-state.md`

It should state:

- Accepted through: Milestone 104.
- Post-M104 planning accepted.
- Current action: execute Milestone 105.
- Active executor milestone:
  `Milestone 105: Clean KISS Generator Restart Charter Slice`.
- Active run prompt:
  `docs/agent/runs/m105-execution-review-loop-prompt.md`.
- Boundary reminders:
  - M105 is documentation/architecture work only.
  - M105 must create a KISS restart charter under `docs/redesign/`.
  - M105 must treat M57-M104 lowering/request/result/worklist artifacts as
    evidence, not as the implementation path to keep extending.
  - M105 must define a simple object-oriented generator architecture for
    `.tsl` source data to validated catalog to selected implementations to
    deterministic C++ and Rust library artifacts.
  - M105 must define the repository-layout reset: move the current `tslgen/`
    tree to `tslgenold/` as old-state evidence before adding new restart
    product code, then reserve `tslgen/` for the clean implementation.
  - M105 must define the first restart implementation slice and its acceptance
    criteria.
  - M105 must not implement product code, tests, parser changes, generator
    changes, renderer changes, artifact writing, CLI behavior, or generated
    output.
  - M105 must not extend `boundary.py`, M57-M104 lowering modules,
    `_lowering_ir_contracts.py`, M99-M104 backend request/result/worklist/
    expansion modules, or the micro-IR taxonomy.
  - M105 must reject new request/result/worklist/provenance wrappers,
    registries, dispatchers, hidden backfeeds, fixpoint machinery, and
    renderer-side semantic inference unless the charter justifies them for at
    least two concrete accepted stages.

Create the M105 execution-review-loop prompt under:

```text
docs/agent/runs/m105-execution-review-loop-prompt.md
```

The M105 prompt must specify:

- one write-capable documentation executor;
- read-only reviewer/auditor subagents;
- docs-only scope;
- creation of `docs/redesign/kiss-generator-restart.md`;
- updates to roadmap/state/design docs as needed;
- the KISS restart product path:
  `.tsl -> validated catalog -> selected implementations -> C++ and Rust
  library artifacts`;
- the repository-layout reset:
  `tslgen/` old state -> `tslgenold/`, then new clean implementation under
  `tslgen/`;
- stable restart concepts and ownership boundaries;
- anti-complexity guardrails for IR, requests/results, worklists,
  provenance, registries, dispatchers, and file-size/module ownership;
- first restart implementation-slice acceptance criteria;
- a required next structural milestone or first-slice rule that performs the
  `tslgen/` to `tslgenold/` quarantine before new product code is added;
- validation with `git diff --check`;
- finalization rules to update state/docs and create the next concrete prompt.

Do not modify implementation code or tests.

## Validation

Run:

```bash
git diff --check
```

If other docs are changed, include them in the diff-check by running the same
repository-wide command.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-ups recorded, if any.
4. Validation command and exact result.
5. Whether the repo is ready to execute M105 after acceptance finalization.
