# Post-M82 Planning Acceptance Finalization Prompt

You are finalizing the accepted post-M82 planning update.

Do not implement product code.

## Accepted Result

The post-M82 planning update selected:

```text
Milestone 83: GenerationLoweringStage Output Contract Extraction Slice
```

The planning result was selected after the post-M82 planning plus review
workflow. Human acceptance has now been recorded in chat.

## Task

Update repository workflow state so the next action is M83 execution.

Read first:

- `docs/agent/current-redesign-state.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/generation-time-semantic-lowering.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/design-decisions.md`

## Required Changes

Update only workflow/docs files needed for the handoff:

- `docs/agent/current-redesign-state.md`
- create `docs/agent/runs/m83-execution-review-loop-prompt.md`

The state file should state:

- Accepted through: Milestone 82.
- Post-M82 planning accepted.
- Current action: execute Milestone 83.
- Active run prompt:
  `docs/agent/runs/m83-execution-review-loop-prompt.md`.
- Active executor milestone:
  `Milestone 83: GenerationLoweringStage Output Contract Extraction Slice`.
- Human acceptance recorded.

The M83 execution prompt must require the orchestrated executor-review loop:

```text
single write-capable executor
-> read-only reviewer/auditor subagents
-> focused revision executor if Needs Revision
-> focused re-review
-> next-run prompt generation
```

## M83 Boundary Reminders

- M83 is behavior-preserving lowering architecture work only.
- M83 must move or own only the accepted `GenerationLoweringStage`
  stage-name/output validation contract in a private typed lowering module.
- M83 must preserve accepted M42-M82 behavior, public imports, stage names,
  stage ordering, output identities, deterministic keys, pipeline snapshots,
  and invalid-stage/output exception behavior.
- `boundary.py` must remain the facade/coordinator for lower-candidate
  orchestration, source adapters, `LoweredImplementation`, `LoweringInput`,
  and `LoweringRequest`.
- Private stage-contract modules must not import `boundary.py` or the
  `tslgen.lowering` package facade.
- If import safety requires moving mini-TSIL value models, move only the
  minimal value-model dependency needed by the stage-output union; do not move
  mini-TSIL parsing or broad statement semantics.
- M83 must not add new stage names, new stage behavior, exact return-emission
  IR, store/call/body/return semantics, broad TSIL parsing, source adapters,
  broad pipeline payload rewrites, helper evaluation, raw helper dispatch,
  registries, dispatchers, runtime plugins, fixpoint/backfeed execution,
  backend translation, rendering, generated output, CLI/report/writer
  behavior, Rust, compiler execution, lowering-time file/catalog reads,
  `tsldata` reads, host CPU queries, backend map reads, or runtime `frozen/`
  use.

## Required M83 Validation In Execution Prompt

The generated M83 execution prompt must require at least:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_stage_contracts.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m83 or stage_contract or generation_lowering_stage"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

If the executor chooses a different private module name than
`_stage_contracts.py`, it must update the py-compile command accordingly and
explain the choice in the final report.

## Required Next Prompt Rule

The M83 execution-review-loop prompt must require creation of the next
concrete run prompt before completion:

- If M83 review returns `Accept` or `Accept With Follow-Ups`, create
  `docs/agent/runs/post-m83-planning-plus-review-prompt.md`.
- If review returns `Needs Revision`, run the focused revision path inside the
  execution-review loop.
- If review returns `Return To Planner` or `Reject`, stop implementation and
  create the appropriate planner/rollback prompt under `docs/agent/runs/`.

Do not create a Milestone 84 execution prompt from this finalization task.

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/post-m82-acceptance-finalization-prompt.md docs/agent/runs/m83-execution-review-loop-prompt.md
```

If other docs are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-up recorded, if any.
4. Validation command and exact result.
5. Whether the repo is ready to execute M83.
