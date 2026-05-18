# Post-M72 Planning Acceptance Finalization Prompt

You are finalizing the accepted post-M72 planning update.

Do not implement code.

## Accepted Result

The post-M72 planning update selected:

```text
Milestone 73: Exact First-Slot Declaration-Shell Structural IR Slice
```

Internal Codex review returned:

```text
Accept With Follow-Ups
```

The follow-ups are non-blocking and must be carried into M73 execution
boundaries:

- M73 must be exact first-slot declaration-shell structural IR only, not
  generic declaration or array semantics.
- M73 must consume accepted M72
  `ExactArrayInitializationHelperSetCompletionIr` values, the
  `array_initialization_helper_set_completion` stage output, or a typed
  `LoweredImplementation` carrying exactly one accepted M72 completion.
- M73 must produce one typed structural IR value for the exact
  `array.tsl:105` `var<typed>(array_type<...>, tmp, ...)` shell, preserving
  accepted M68 base type, accepted M70 vector length, accepted M71 vector
  alignment, and the M72 deferred backend-uninit boundary.
- M73 must append one deterministic stage after
  `array_initialization_helper_set_completion`.
- M73 must use source text only as provenance/invariant evidence and must not
  reparse M66 slot text or M67 helper leaf text as semantic input.
- M73 must not translate or render backend uninit, query backend maps, create
  backend translation requests, produce renderer-ready IR, render C++/Rust/
  backend text, change generated output, parse generic `var` or `array_type`,
  model allocation/lifetime/initializer/variable scope semantics, lower stores
  or returns, interpret `tmp.data()`, lower `emit_return`, add
  direct-intrinsic/SVE semantics, parse broad TSIL, read `tsldata`/catalog/
  backend maps during lowering evaluation, or depend on `frozen/` at runtime.
- M73 should keep public IR additions narrow, preferably one genuinely
  consumed structural boundary value rather than a broad `VarIr` /
  `ArrayTypeIr` family or registry.

## Task

Update repository workflow state so the next action is M73 execution, and
create the concrete M73 execution-review prompt.

Do not start M73 execution in this prompt.

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
- create `docs/agent/runs/m73-execution-review-loop-prompt.md`

Do not modify implementation code or tests.

`docs/agent/current-redesign-state.md` should state:

- Accepted through: Milestone 72.
- Post-M72 planning accepted.
- Current action: execute Milestone 73.
- Active run prompt:
  `docs/agent/runs/m73-execution-review-loop-prompt.md`.
- Active executor milestone:
  `Milestone 73: Exact First-Slot Declaration-Shell Structural IR Slice`.

The generated M73 execution-review loop prompt must require:

- exactly one write-capable executor if M73 is not already implemented;
- read-only reviewer, validation-auditor, boundary-auditor,
  extensibility-auditor, documentation-auditor, and evidence-auditor
  subagents;
- a focused revision loop for `Needs Revision`;
- next-prompt generation after `Accept` or `Accept With Follow-Ups`.

## M73 Boundary Reminders

- M73 is generation-time lowering structural IR only.
- M73 consumes accepted M72 `ExactArrayInitializationHelperSetCompletionIr`
  values, the `array_initialization_helper_set_completion` stage output, or a
  typed `LoweredImplementation` carrying exactly one accepted M72 completion.
- M73 produces one typed exact first-slot declaration-shell structural IR
  value for the exact `array.tsl:105`
  `var<typed>(array_type<...>, tmp, ...)` shell.
- M73 preserves the accepted M68 base type, accepted M70 vector length,
  accepted M71 vector alignment, and the M72 deferred backend-uninit boundary.
- M73 appends one deterministic stage after
  `array_initialization_helper_set_completion`, for example
  `array_initialization_declaration_shell_lowering`.
- M73 must preserve accepted M66/M67/M68/M69/M70/M71/M72 behavior and outputs.
- M73 must use source text only as provenance/invariant evidence.
- M73 must not translate, resolve, or render `value<backend>(uninit::array)`
  to C++, Rust, backend text, initializer syntax, `{}`, `MaybeUninit`,
  backend translation requests, renderer-ready values, or generated output.
- M73 must not add backend manifests, backend maps, language maps, translation
  maps, renderer calls, generated artifacts, golden files, CLI/report/writer
  behavior, Rust behavior, compiler execution, or generated-test execution.
- M73 must not add generic `var`, generic `array_type`, generic declaration
  semantics, generic array semantics, array allocation/lifetime, variable
  binding/scope, initializer semantics, store, return, `tmp.data()`,
  `emit_return`, `assume_aligned`, aligned-store semantics,
  direct-intrinsic/SVE semantics, loops, calls, casts, broad TSIL parsing,
  lowering-time file/catalog reads, `tsldata` reads during lowering
  evaluation, host CPU queries, backend map reads, or runtime `frozen/` use.
- M73 must not create broad helper registries, raw helper-string dispatch,
  broad stage registries, broad declaration registries, or public `VarIr` /
  `ArrayTypeIr` families beyond the exact selected structural boundary value.

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/m73-execution-review-loop-prompt.md
```

If other docs are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-ups recorded, if any.
4. Next prompt created.
5. Validation command and exact result.
6. Whether the repo is ready to execute M73.
