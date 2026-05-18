# Milestone 73 Execution Review Loop Prompt

You are the Codex orchestrator for the accepted M73 implementation and review
loop.

Read `docs/agent/current-redesign-state.md` first.

Do not start Milestone 74.

## Accepted State

Accepted through:

```text
Milestone 72
```

Post-M72 planning is accepted. It selected:

```text
Milestone 73: Exact First-Slot Declaration-Shell Structural IR Slice
```

Internal planning review returned:

```text
Accept With Follow-Ups
```

Human acceptance has been recorded. M73 execution is the active workflow
action.

## Read First

- `AGENTS.md`
- `PLANS.md`
- `docs/agent/current-redesign-state.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/agent/review-checklist.md`
- `docs/agent/subagents/`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/generation-time-semantic-lowering.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/open-questions.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/frozen-parity-baselines.md`

## Goal

Consume accepted M72 helper-set completions and produce one typed structural
lowering value for the exact `array.tsl:105` first-slot declaration shell:

```text
var<typed>(
  array_type<base type, vector length, vector alignment>,
  tmp,
  deferred backend uninit
)
```

M73 is generation-time lowering structural IR only. It must preserve the
accepted M68 base type, accepted M70 vector length, accepted M71 vector
alignment, and M72 deferred backend-uninit boundary without defining generic
declaration semantics, generic array semantics, allocation/lifetime,
initializer behavior, variable scope, backend translation, renderer-ready IR,
or generated output.

## In Scope

- Consume only accepted M72 `ExactArrayInitializationHelperSetCompletionIr`
  values, the `array_initialization_helper_set_completion` stage output, or a
  typed `LoweredImplementation` carrying exactly one accepted M72 helper-set
  completion.
- Produce one typed structural IR value such as
  `ExactArrayInitializationDeclarationShellIr`, carrying:
  - the source M72 helper-set completion;
  - accepted M66 slot-form and M65 envelope provenance reachable through the
    M72 source chain;
  - exact structural declaration kind `var<typed>`;
  - exact structural array-type shape using the accepted M68 base type,
    accepted M70 vector length, and accepted M71 vector alignment facts;
  - variable token `tmp` as preserved M66/M67/M72 provenance;
  - the accepted M72 deferred backend-uninit boundary/policy;
  - deterministic provenance including candidate id, target/source extension,
    selected type tag, branch-chain id, envelope/slot identity, variable token,
    and source locations.
- Append one deterministic stage after
  `array_initialization_helper_set_completion`, for example
  `array_initialization_declaration_shell_lowering`.
- Preserve accepted M66/M67/M68/M69/M70/M71/M72 behavior and outputs.
- Use source text only as provenance/invariant evidence. M73 must consume
  typed M72 helper-set facts rather than reparsing M66 slot text or M67 helper
  leaf text as semantics.
- Keep public IR additions narrow: prefer one genuinely consumed structural
  boundary value over broad `VarIr` / `ArrayTypeIr` families or registries.

## Out Of Scope

- Translating, resolving, or rendering `value<backend>(uninit::array)` to C++,
  Rust, backend text, initializer syntax, `{}`, `MaybeUninit`, backend
  translation requests, renderer-ready values, or generated output.
- Backend manifests, backend maps, language maps, translation maps, renderer
  calls, generated artifacts, golden files, CLI/report/writer behavior, Rust
  behavior, compiler execution, or generated-test execution.
- Generic `var`, generic `array_type`, generic declaration semantics, generic
  array semantics, array allocation/lifetime, variable binding/scope,
  initializer semantics, store, return, `tmp.data()`, `emit_return`,
  `assume_aligned`, aligned-store semantics, direct-intrinsic/SVE semantics,
  loops, calls, casts, multi-statement lowering, or broad TSIL parsing.
- Broad helper registries, raw helper-string dispatch, broad stage registries,
  broad declaration registries, lowering-time file/catalog reads, raw TSL
  parsing, `tsldata` reads during lowering evaluation, host CPU queries,
  backend map reads, or runtime dependency on `frozen/`.

## Acceptance Criteria

- Direct resolver tests prove M73 consumes accepted M72 helper-set completion
  values and produces the exact first-slot declaration-shell structural IR.
- Normal `lower_candidates` pipeline tests prove the M73 stage appears after
  `array_initialization_helper_set_completion` and preserves M66-M72 ordering
  and outputs.
- Tests prove the structural shell consumes typed M72 facts and preserves the
  M72 deferred backend-uninit policy without translating it.
- Diagnostics cover unsupported source/container shapes, missing M72
  completion, duplicate M72 completions, context mismatch, provenance
  mismatch, malformed exact shell invariants, and backend-uninit policy
  mismatch.
- Determinism tests cover repeated runs and reordered inputs.
- Regression tests prove M66/M67/M68/M70/M71/M72 behavior is unchanged.
- Regression tests prove no backend translation, rendering, generated output,
  golden-file churn, broad declaration/array lowering, generic `var` /
  `array_type` parsing, raw helper evaluator calls, raw helper parsing,
  catalog reads, `tsldata` reads, host CPU queries, backend map reads, or
  runtime `frozen/` use is introduced.

## Phase 1: Executor

If M73 is already implemented and awaiting review, skip implementation and go
directly to Phase 2.

If M73 is not implemented, spawn exactly one write-capable executor subagent.
Tell the executor:

- It is not alone in the codebase.
- It must not revert or overwrite edits made by others.
- It owns only the M73 implementation slice, directly related tests, and any
  necessary redesign-doc updates.
- It must not edit `docs/agent/current-redesign-state.md`.
- It must not create the next run prompt.
- It must keep M73 within the scope and out-of-scope boundaries above.
- It must consume typed M72 helper-set completion values, not raw helper text.
- It must keep source text as provenance/invariant evidence only.
- It must preserve accepted M68 base type, accepted M70 vector length,
  accepted M71 vector alignment, and the M72 deferred backend-uninit boundary.
- It must not translate or render backend uninit, query backend maps, create
  backend translation requests, produce renderer-ready values, lower generic
  declaration/array semantics, or change generated output.
- It must avoid broad `VarIr` / `ArrayTypeIr` public families, broad helper
  registries, raw helper-string dispatch, broad stage registries, broad
  declaration registries, or central semantic shortcuts.
- It must preserve accepted M66/M67/M68/M69/M70/M71/M72 behavior and outputs.
- It must include explicit no-catalog-read, no-`tsldata`-read, no-host-CPU,
  no-backend-map, no-renderer, and no-`frozen/` coverage where practical
  during declaration-shell structural lowering.

The executor should report files changed, tests added or updated, validation
commands run, how the typed declaration-shell structural IR is produced, how
backend uninit remains deferred and non-rendering, how raw helper dispatch and
hardwiring are avoided, how M66-M72 behavior is preserved, and any follow-ups
or blockers.

## Phase 2: Review And Audit Subagents

After execution, run read-only review/audit subagents using this workflow:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Validation auditor: verify required validation commands and assess test
   coverage for direct declaration-shell structural IR lowering, normal
   `lower_candidates` pipeline behavior, stage order after M72, typed M72
   consumption, diagnostics, determinism, unchanged M66/M67/M68/M69/M70/M71/
   M72 behavior, no generated output/golden churn, and no raw helper/file/
   catalog/`tsldata`/host CPU/backend-map/renderer/`frozen/` dependencies
   during lowering.
3. Boundary auditor: confirm M73 only produces exact first-slot
   declaration-shell structural IR and does not add backend-uninit
   translation, backend maps, backend rendering, generic declaration/array
   semantics, allocation/lifetime, initializer behavior, variable scope, store
   or return semantics, `tmp.data()`, `emit_return`, direct-intrinsic/SVE
   semantics, broad helper evaluation, raw helper parsing/evaluation, broad
   TSIL parsing, generated output, lowering-time file/catalog reads,
   `tsldata` reads during lowering evaluation, host CPU queries, or runtime
   `frozen/` use.
4. Extensibility auditor: confirm the integration uses the M69-M72 extracted
   pipeline as a maintainable typed attachment point without introducing a
   broad registry, central dispatcher, raw-text evaluator, public IR bloat, or
   hardwired semantic shortcut.
5. Documentation auditor: check roadmap, lowering docs, behavioral spec, open
   questions, design decisions, target architecture, pipeline design, testing
   strategy, and parity baselines for required updates or stale claims.
6. Evidence auditor: confirm the implementation and tests are justified by
   accepted M66/M67/M68/M69/M70/M71/M72 behavior plus the exact
   `array.tsl:105` first-slot declaration shell, and that backend translation
   map evidence remains a boundary constraint rather than a runtime dependency
   or output behavior.

Review and audit subagents are read-only unless a later revision task
explicitly assigns one focused write-capable executor.

## Phase 3: Consolidated Verdict

The orchestrator must consolidate subagent results into one verdict:

- `Accept`
- `Accept With Follow-Ups`
- `Needs Revision`
- `Return To Planner`
- `Reject`

Findings must be specific and file/line grounded where applicable.

## Phase 4: Revision Loop If Needed

If the consolidated verdict is `Needs Revision`, run exactly one focused
write-capable revision executor for the blocking issues only. Then run focused
read-only re-review for the changed areas.

Do not broaden M73 during revision.

If the verdict is `Return To Planner` or `Reject`, stop implementation. Create
the appropriate next planning or rollback prompt under `docs/agent/runs/` and
update `docs/agent/current-redesign-state.md` to point at it.

## Phase 5: Next Prompt Generation

If the final verdict is `Accept` or `Accept With Follow-Ups`:

- Record any non-blocking follow-ups.
- Update `docs/agent/current-redesign-state.md` so M73 is accepted.
- Create the next concrete prompt under `docs/agent/runs/`.
- If no post-M73 plan has been accepted, create a post-M73
  planning-plus-review prompt. Do not start M74.

The next prompt must follow `docs/agent/next-run-prompt-protocol.md`.

## Required Validation

Run targeted validation selected by the executor plus:

```bash
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

The final docs/state update in this prompt must also pass:

```bash
git diff --check
```

## Final Report

Report:

1. Whether implementation was skipped or exactly one write-capable executor
   was used.
2. Review/audit subagents used and consolidated verdict.
3. Files changed.
4. Validation commands and exact results.
5. Follow-ups recorded, if any.
6. Next prompt created.
7. Whether the repo is ready for the next workflow action.
