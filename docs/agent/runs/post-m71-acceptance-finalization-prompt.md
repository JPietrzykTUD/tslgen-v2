# Post-M71 Planning Acceptance Finalization Prompt

You are finalizing the accepted post-M71 planning update.

Do not implement code.

## Accepted Result

The post-M71 planning update selected:

```text
Milestone 72: Exact Array Initialization Helper-Set Completion IR Slice
```

Internal Codex review returned:

```text
Accept With Follow-Ups
```

The follow-ups are non-blocking and must be carried into M72 execution
boundaries:

- M72 must consume the accepted M71 vector-alignment resolution for the exact
  first array-initialization slot.
- M72 must package the complete exact helper set into one typed aggregate:
  accepted M68 base type, accepted M70 vector length, accepted M71 vector
  alignment, and the remaining exact M67
  `value<backend>(uninit::array)` request.
- M72 must keep backend uninit as a typed deferred backend-value request
  boundary. It must not translate or render backend uninit, create backend
  translation requests, create renderer-ready values, query backend maps, or
  change generated output.
- M72 must not add declaration/array semantics, broad `var`, `array_type`,
  allocation/lifetime, variable binding/scope, initializer semantics, store,
  return, `tmp.data()`, `emit_return`, `assume_aligned`, direct-intrinsic/SVE
  semantics, loops, calls, casts, broad TSIL parsing, or generated-output
  behavior.
- M72 validation should include relevant M69/M71 hardening where practical:
  pipeline-level M67 diagnostic propagation coverage and explicit guards
  against catalog reads, `tsldata` reads, host CPU queries, backend map reads,
  renderer calls, and runtime `frozen/` use during lowering evaluation.

## Task

Update repository workflow state so the next action is M72 execution, and
create the concrete M72 execution-review prompt.

Do not start M72 execution in this prompt.

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
- create `docs/agent/runs/m72-execution-review-loop-prompt.md`

Do not modify implementation code or tests.

`docs/agent/current-redesign-state.md` should state:

- Accepted through: Milestone 71.
- Post-M71 planning accepted.
- Current action: execute Milestone 72.
- Active run prompt:
  `docs/agent/runs/m72-execution-review-loop-prompt.md`.
- Active executor milestone:
  `Milestone 72: Exact Array Initialization Helper-Set Completion IR Slice`.

The generated M72 execution-review loop prompt must require:

- exactly one write-capable executor if M72 is not already implemented;
- read-only reviewer, validation-auditor, boundary-auditor,
  extensibility-auditor, documentation-auditor, and evidence-auditor
  subagents;
- a focused revision loop for `Needs Revision`;
- next-prompt generation after `Accept` or `Accept With Follow-Ups`.

## M72 Boundary Reminders

- M72 is generation-time lowering helper-set completion only.
- M72 consumes accepted M71
  `ExactArrayInitializationVectorAlignmentResolutionIr` values, the
  `array_initialization_vector_alignment_request_resolution` stage output, or
  a typed `LoweredImplementation` carrying exactly one accepted M71
  vector-alignment resolution.
- M72 selects only the remaining exact M67 backend-uninit request record with
  request ordinal `3`, request kind `backend_value`, and helper leaf kind
  `value_backend_uninit_array`.
- M72 records backend uninit only as a typed deferred backend-value request
  boundary or policy. Source text may be preserved only as
  provenance/invariant evidence.
- M72 produces one typed aggregate such as
  `ExactArrayInitializationHelperSetCompletionIr`, carrying the accepted M68
  base-type resolution, accepted M70 vector-length resolution, accepted M71
  vector-alignment resolution, source M67 backend-uninit request record, typed
  deferred backend-uninit boundary, and deterministic provenance.
- M72 appends one deterministic stage after
  `array_initialization_vector_alignment_request_resolution`, for example
  `array_initialization_helper_set_completion`.
- M72 must preserve accepted M68 base-type behavior, accepted M69
  stage-pipeline behavior, accepted M70 vector-length behavior, and accepted
  M71 vector-alignment behavior.
- M72 must not translate, resolve, or render `value<backend>(uninit::array)`
  to C++, Rust, backend text, initializer syntax, `{}`, `MaybeUninit`,
  backend translation requests, renderer-ready values, or generated output.
- M72 must not add backend manifests, backend maps, language maps, translation
  maps, renderer calls, generated artifacts, golden files, CLI/report/writer
  behavior, Rust behavior, compiler execution, or generated-test execution.
- M72 must not add broad `var`, `array_type`, declaration, array
  allocation/lifetime, variable binding/scope, initializer semantics, store,
  return, `tmp.data()`, `emit_return`, `assume_aligned`,
  direct-intrinsic/SVE semantics, loops, calls, casts, broad TSIL parsing,
  lowering-time file/catalog reads, `tsldata` reads during lowering
  evaluation, host CPU queries, or runtime `frozen/` use.
- M72 must not create a generic `value<backend>(...)`,
  `type<backend>(...)`, `value<generation>(...)`, or `type<generation>(...)`
  evaluator family, broad helper registry, raw helper-string dispatcher, or
  broad stage registry.

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/m72-execution-review-loop-prompt.md
```

If other docs are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-ups recorded, if any.
4. Next prompt created.
5. Validation command and exact result.
6. Whether the repo is ready to execute M72.
