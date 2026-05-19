# Post-M75 Planning Acceptance Finalization Prompt

You are finalizing the accepted post-M75 planning update.

Do not implement code.

## Accepted Result

The post-M75 planning update selected:

```text
Milestone 76: Exact Post-Branch Intrinsic Call-Site Structural Request IR Slice
```

The selected plan must remain:

- exact post-branch intrinsic call-site structural/request IR only;
- a typed lowering slice consuming accepted M75 predicate-path state;
- free of store semantics, ARM/SVE intrinsic semantics, memory behavior,
  pointer semantics, `tmp.data()` semantics, operand semantics, backend
  translation, rendering, generated output, variable scope, generic
  call/store/body IR, broad TSIL parsing, and hardwired semantic shortcuts.

## Task

Update repository workflow state so the next action is M76 execution, and
create the concrete M76 execution-review prompt.

Do not start M76 execution in this prompt.

Read first:

- `docs/agent/current-redesign-state.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/generation-time-semantic-lowering.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/open-questions.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/frozen-parity-baselines.md`

## Required Changes

Update:

- `docs/agent/current-redesign-state.md`
- create `docs/agent/runs/m76-execution-review-loop-prompt.md`

Do not modify implementation code or tests.

`docs/agent/current-redesign-state.md` should state:

- Accepted through: Milestone 75.
- Post-M75 planning accepted.
- Current action: execute Milestone 76.
- Active run prompt:
  `docs/agent/runs/m76-execution-review-loop-prompt.md`.
- Active executor milestone:
  `Milestone 76: Exact Post-Branch Intrinsic Call-Site Structural Request IR Slice`.

The generated M76 execution-review loop prompt must require:

- exactly one write-capable executor if M76 is not already implemented;
- read-only reviewer, validation-auditor, boundary-auditor,
  extensibility-auditor, documentation-auditor, and evidence-auditor
  subagents;
- a focused revision loop for `Needs Revision`;
- stop rules for `Return To Planner` and `Reject`;
- next-prompt generation after `Accept` or `Accept With Follow-Ups`.

## M76 Boundary Reminders

- M76 is generation-time lowering structural/request IR only.
- M76 consumes accepted M75 `ExactPredicatePathStructuralRequestIr` values, the
  `predicate_path_structural_request_lowering` stage output, or a typed
  `LoweredImplementation` carrying exactly one accepted M75 value.
- M76 consumes accepted M74 exact array-body structural sequence state and
  accepted M73 declaration-shell state only through the accepted M75/M74
  provenance chain.
- M76 produces one typed exact post-branch intrinsic call-site
  structural/request IR value for the exact `array.tsl:110` shape:

```text
intrin<svst1>(pg, tmp.data(), a);
```

- M76 records only:
  - the source M75 predicate-path value;
  - the source M74 structural sequence identity and exact post-branch slot
    identity for slot ordinal `3`;
  - structural call-head token `intrin`;
  - unresolved intrinsic token `svst1`;
  - argument ordinal `0` structural token `pg`, linked to accepted M75 slot-3
    predicate-token use;
  - argument ordinal `1` exact member-access-shaped structural token/path
    `tmp.data()`, linked only to accepted structural `tmp` provenance where
    already carried through M73/M74/M75;
  - argument ordinal `2` structural source operand token `a`;
  - deterministic provenance including candidate id, target/source extension
    where available, selected type tag, branch-chain id, M74/M75 identity, and
    source locations.
- M76 appends one deterministic generation-lowering stage after
  `predicate_path_structural_request_lowering`, for example
  `post_branch_intrinsic_call_site_structural_request_lowering`.
- M76 must preserve accepted M57/M58/M59/M60/M61/M62/M63/M64/M65/M66/M67/M68/
  M69/M70/M71/M72/M73/M74/M75 behavior and outputs, including selected-branch
  diagnostics from earlier branch-pruning/lowering slices.
- M76 must use source text only as exact structural shape/provenance evidence.
- M76 must not interpret `svst1`, `pg`, `tmp.data()`, `a`, `svbool_t`,
  `svptrue_b*`, ARM/SVE predicate/vector/register/intrinsic behavior, store
  semantics, memory behavior, alignment behavior, pointer semantics, operand
  semantics, variable scope/use-def/lifetime, declaration/array semantics,
  initializer behavior, return semantics, `emit_return`, `assume_aligned`,
  backend uninit, backend maps, backend translation, rendering, generated
  output, generic call/store/body semantics, broad TSIL parsing,
  lowering-time file/catalog reads, `tsldata` reads during lowering evaluation,
  host CPU queries, backend map reads, or runtime `frozen/` use.
- M76 must not add backend manifests, backend maps, language maps,
  translation maps, backend translation requests, renderer calls, generated
  artifacts, golden files, generated tests, CLI/report/writer behavior, Rust
  behavior, compiler execution, or generated-test execution.
- M76 must not create generic call IR, generic store IR, broad helper
  registries, broad slot-role registries, broad stage registries, central
  semantic dispatchers, raw helper-string dispatch, or hardwired semantic
  shortcuts keyed by helper text, intrinsic token text, selected type tags,
  SVE tokens, backend ids, renderer names, corpus line numbers, or request
  ordinals.

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/m76-execution-review-loop-prompt.md
```

If other docs are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-ups recorded, if any.
4. Next prompt created.
5. Validation command and exact result.
6. Whether the repo is ready to execute M76.
